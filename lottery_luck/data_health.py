from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .rules import GAME_RULES, candidate_draw_dates


CREATE_CRAWL_LOGS_SQL = """
CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    game_key TEXT NOT NULL,
    source TEXT NOT NULL,
    page_size INTEGER NOT NULL DEFAULT 0,
    pages INTEGER NOT NULL DEFAULT 0,
    wrote_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0
)
"""


def ensure_crawl_logs_table(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_CRAWL_LOGS_SQL)


def record_crawl_log(
    connection: sqlite3.Connection,
    *,
    provider: str,
    game_key: str,
    source: str,
    page_size: int,
    pages: int,
    wrote_count: int,
    status: str,
    error: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
) -> None:
    ensure_crawl_logs_table(connection)
    connection.execute(
        """
        INSERT INTO crawl_logs (
            provider, game_key, source, page_size, pages, wrote_count,
            status, error, started_at, finished_at, duration_ms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider,
            game_key,
            source,
            int(page_size),
            int(pages),
            int(wrote_count),
            status,
            error,
            started_at,
            finished_at,
            int(duration_ms),
        ),
    )


def recent_crawl_logs(connection: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    ensure_crawl_logs_table(connection)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, provider, game_key, source, page_size, pages, wrote_count,
               status, error, started_at, finished_at, duration_ms
        FROM crawl_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def recent_crawl_logs_by_game(
    connection: sqlite3.Connection,
    game_keys: list[str],
    limit_per_game: int = 20,
) -> list[dict[str, Any]]:
    ensure_crawl_logs_table(connection)
    normalized_keys = sorted(
        {
            normalized
            for key in game_keys
            if (normalized := str(key).strip().lower())
        }
    )
    if not normalized_keys or limit_per_game <= 0:
        return []

    connection.row_factory = sqlite3.Row
    placeholders = ", ".join("?" for _ in normalized_keys)
    rows = connection.execute(
        f"""
        WITH ranked AS (
            SELECT id, provider, game_key, source, page_size, pages, wrote_count,
                   status, error, started_at, finished_at, duration_ms,
                   ROW_NUMBER() OVER (
                       PARTITION BY lower(trim(game_key))
                       ORDER BY julianday(finished_at) IS NULL,
                                julianday(finished_at) DESC,
                                id DESC
                   ) AS row_number
            FROM crawl_logs
            WHERE lower(trim(game_key)) IN ({placeholders})
        )
        SELECT id, provider, game_key, source, page_size, pages, wrote_count,
               status, error, started_at, finished_at, duration_ms
        FROM ranked
        WHERE row_number <= ?
        ORDER BY lower(trim(game_key)),
                 julianday(finished_at) IS NULL,
                 julianday(finished_at) DESC,
                 id DESC
        """,
        (*normalized_keys, int(limit_per_game)),
    ).fetchall()
    return [dict(row) for row in rows]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def duration_ms(started_at: str, finished_at: str) -> int:
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds() * 1000))


def build_data_health_report(
    games: list[dict[str, Any]],
    draw_dates_by_game: dict[str, list[str]],
    crawl_logs: list[dict[str, Any]],
    today: str | None = None,
) -> dict[str, Any]:
    current_day = date.fromisoformat(today or date.today().isoformat())
    rows = []
    for game in games:
        key = str(game.get("game_key") or "").strip().lower()
        if key not in GAME_RULES:
            continue
        draw_dates = sorted({str(value) for value in draw_dates_by_game.get(key, []) if value}, reverse=True)
        latest_expected = _latest_expected_draw_date(key, current_day)
        next_draw = _next_draw_date(key, current_day)
        missing = _recent_missing_dates(key, current_day, draw_dates)
        draw_count = int(game.get("draw_count") or 0)
        latest_date = str(game.get("latest_date") or "")
        status = _game_status(draw_count, latest_date, latest_expected)
        staleness = _staleness_days(latest_date, current_day)
        rows.append(
            {
                "game_key": key,
                "game_name": game.get("game_name") or GAME_RULES[key].name,
                "provider": game.get("provider") or GAME_RULES[key].provider,
                "draw_count": draw_count,
                "earliest_date": game.get("earliest_date") or "",
                "latest_date": latest_date,
                "latest_issue": game.get("latest_issue") or "",
                "latest_expected_draw_date": latest_expected,
                "next_draw_date": next_draw,
                "status": status,
                "status_tone": _status_tone(status),
                "staleness_days": staleness,
                "missing_recent_count": len(missing),
                "missing_trend": _missing_trend(len(missing), staleness),
                "recent_missing_dates": missing[:8],
                "advice": _advice(status, missing),
            }
        )

    kpis = {
        "total_games": len(rows),
        "healthy_games": sum(1 for row in rows if row["status"] == "healthy"),
        "attention_games": sum(1 for row in rows if row["status"] == "attention"),
        "empty_games": sum(1 for row in rows if row["status"] == "empty"),
        "total_draws": sum(row["draw_count"] for row in rows),
        "latest_crawl_at": max(
            (str(log.get("finished_at") or "") for log in crawl_logs if log.get("finished_at")),
            default="",
        ),
    }
    return {
        "today": current_day.isoformat(),
        "kpis": kpis,
        "games": rows,
        "logs": crawl_logs,
        "failure_summary": _failure_summary(crawl_logs),
        "commands": {
            "sports_browser": "python -m lottery_luck.sports_crawler --games dlt,pl3 --source browser --page-size 100 --pages 3",
            "cwl": "python -m lottery_luck.crawler --games ssq,3d,kl8 --page-size 100",
        },
    }


def build_public_freshness(
    game: dict[str, Any],
    *,
    today: date | str | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current_day = _current_day(today)
    latest_issue = str(game.get("latest_issue") or "")
    latest_date = str(game.get("latest_date") or "")
    staleness = _staleness_days(latest_date, current_day)
    if not latest_date:
        status = "empty"
    elif staleness is not None and staleness <= 2:
        status = "fresh"
    elif staleness is not None and staleness <= 4:
        status = "attention"
    else:
        status = "stale"

    can_claim_current = status in {"fresh", "attention"}
    if status in {"fresh", "attention"}:
        message = f"数据已更新至第{latest_issue}期"
    elif status == "stale":
        message = f"数据停留在第{latest_issue}期，暂不提供本期结论"
    else:
        message = "暂无可用开奖数据"

    game_key = str(game.get("game_key") or "").strip().lower()
    game_logs = [
        log
        for log in logs or []
        if str(log.get("game_key") or "").strip().lower() == game_key
    ]
    newest_log = max(
        (log for log in game_logs if log.get("finished_at")),
        key=_finished_at_sort_key,
        default=None,
    )
    latest_success = max(
        (
            log
            for log in game_logs
            if _is_successful_log(log) and log.get("finished_at")
        ),
        key=_finished_at_sort_key,
        default=None,
    )
    return {
        "status": status,
        "latest_issue": latest_issue,
        "latest_date": latest_date,
        "staleness_days": staleness,
        "can_claim_current": can_claim_current,
        "message": message,
        "last_successful_update": (
            str(latest_success.get("finished_at") or "") if latest_success else ""
        ),
        "sync_error": (
            _sanitize_sync_error(newest_log.get("error"))
            if newest_log and not _is_successful_log(newest_log)
            else ""
        ),
    }


def _current_day(today: date | str | None) -> date:
    if isinstance(today, date):
        return today
    return date.fromisoformat(today or date.today().isoformat())


def _is_successful_log(log: dict[str, Any]) -> bool:
    return str(log.get("status") or "").lower() in {"success", "ok", "completed"}


def _finished_at_sort_key(log: dict[str, Any]) -> datetime:
    parsed = _parse_finished_at(log.get("finished_at"))
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _parse_finished_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sanitize_sync_error(error: Any) -> str:
    return " ".join(str(error or "").split())[:160]


def _game_status(draw_count: int, latest_date: str, latest_expected: str) -> str:
    if draw_count <= 0 or not latest_date:
        return "empty"
    if latest_expected and latest_date < latest_expected:
        return "attention"
    return "healthy"


def _status_tone(status: str) -> str:
    return {"healthy": "good", "attention": "warning", "empty": "danger"}.get(status, "warning")


def _missing_trend(missing_count: int, staleness_days: int | None) -> str:
    if missing_count >= 2 or (staleness_days is not None and staleness_days >= 5):
        return "widening"
    if missing_count == 1:
        return "watch"
    return "stable"


def _failure_summary(crawl_logs: list[dict[str, Any]]) -> dict[str, Any]:
    failed = next(
        (
            log
            for log in crawl_logs
            if str(log.get("status") or "").lower() not in {"success", "ok", "completed"}
        ),
        None,
    )
    if not failed:
        return {"has_failure": False, "message": "暂无失败日志。"}

    game_key = str(failed.get("game_key") or "")
    provider = str(failed.get("provider") or "")
    error = str(failed.get("error") or "未知错误")
    return {
        "has_failure": True,
        "provider": provider,
        "game_key": game_key,
        "finished_at": str(failed.get("finished_at") or ""),
        "message": f"{provider}:{game_key} 最近失败：{error}",
    }


def _latest_expected_draw_date(game_key: str, current_day: date) -> str:
    start = current_day - timedelta(days=14)
    dates = [
        draw_date
        for draw_date in candidate_draw_dates(game_key, start.isoformat(), 15)
        if draw_date < current_day
    ]
    return dates[-1].isoformat() if dates else ""


def _next_draw_date(game_key: str, current_day: date) -> str:
    dates = candidate_draw_dates(game_key, current_day.isoformat(), 14)
    return dates[0].isoformat() if dates else current_day.isoformat()


def _recent_missing_dates(game_key: str, current_day: date, draw_dates: list[str]) -> list[str]:
    start = current_day - timedelta(days=30)
    expected = [
        draw_date.isoformat()
        for draw_date in candidate_draw_dates(game_key, start.isoformat(), 31)
        if draw_date < current_day
    ]
    present = set(draw_dates)
    return [draw_date for draw_date in reversed(expected) if draw_date not in present]


def _staleness_days(latest_date: str, current_day: date) -> int | None:
    if not latest_date:
        return None
    try:
        return max(0, (current_day - date.fromisoformat(latest_date)).days)
    except ValueError:
        return None


def _advice(status: str, missing: list[str]) -> str:
    if status == "empty":
        return "暂无历史数据，建议先补采。"
    if status == "attention":
        return "最新开奖可能未同步，建议执行补采。"
    if missing:
        return "近期存在日期缺口，可按需补采核对。"
    return "数据状态正常。"
