import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import CW_API_URL
from .data_health import duration_ms, record_crawl_log, utc_now_iso
from .database import connect_database


USER_AGENT = "lottery-luck-crawler/0.1 (+https://www.cwl.gov.cn)"


def _first_value(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return default


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def _json_stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _split_draw_date(value: Any) -> tuple[str, str]:
    text = _stringify(value).strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:[（(]\s*([^）)]+?)\s*[）)])?$", text)
    if not match:
        return text, ""
    return match.group(1), match.group(2) or ""


def normalize_api_row(game_key: str, row: dict[str, Any]) -> dict[str, Any]:
    draw_date, parsed_week = _split_draw_date(
        _first_value(row, "date", "draw_date", "drawDate")
    )
    week = _stringify(_first_value(row, "week", "weekday", default=parsed_week))

    return {
        "game_key": game_key,
        "issue": _stringify(_first_value(row, "code", "issue")),
        "game_name": _stringify(_first_value(row, "name", "game_name", "gameName")),
        "draw_date": draw_date,
        "week": week,
        "red_numbers": _stringify(_first_value(row, "red", "red_numbers", "redNumbers")),
        "blue_number": _stringify(_first_value(row, "blue", "blue_number", "blueNumber")),
        "sales": _stringify(_first_value(row, "sales")),
        "pool_money": _stringify(_first_value(row, "poolmoney", "pool_money", "poolMoney")),
        "content": _stringify(_first_value(row, "content")),
        "details_url": _stringify(
            _first_value(row, "detailsLink", "details_url", "detailsUrl")
        ),
        "video_url": _stringify(_first_value(row, "videoLink", "video_url", "videoUrl")),
        "blue2": _stringify(_first_value(row, "blue2")),
        "prizegrades_json": _json_stringify(
            _first_value(row, "prizegrades", "prizeGrades")
        ),
        "special_rule_info": _stringify(
            _first_value(row, "specialRuleInfo", "special_rule_info")
        ),
        "prize_special_info": _stringify(
            _first_value(row, "prizeSpecialInfo", "prize_special_info")
        ),
        "comp_limit_info": _stringify(
            _first_value(row, "compLimitInfo", "comp_limit_info")
        ),
        "fyj_count": _stringify(_first_value(row, "fyjCount", "fyj_count")),
        "fyj_money": _stringify(_first_value(row, "fyjMoney", "fyj_money")),
        "raw_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _draw_columns(connection: sqlite3.Connection) -> list[str]:
    return [row[1] for row in connection.execute("PRAGMA table_info(draws)")]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def upsert_draw(connection: sqlite3.Connection, draw: dict[str, Any]) -> None:
    columns = [column for column in _draw_columns(connection) if column in draw]
    if "game_key" not in columns or "issue" not in columns:
        raise ValueError("draws table and draw data must include game_key and issue")

    game_key = _stringify(draw.get("game_key")).strip()
    issue = _stringify(draw.get("issue")).strip()
    if not game_key:
        raise ValueError("game_key must be non-empty")
    if not issue:
        raise ValueError("issue must be non-empty")

    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    update_columns = [column for column in columns if column not in {"game_key", "issue"}]

    if update_columns:
        update_sql = ", ".join(
            f"{_quote_identifier(column)} = excluded.{_quote_identifier(column)}"
            for column in update_columns
        )
        conflict_sql = f"DO UPDATE SET {update_sql}"
    else:
        conflict_sql = "DO NOTHING"

    sql = f"""
    INSERT INTO draws ({column_sql})
    VALUES ({placeholders})
    ON CONFLICT(game_key, issue) {conflict_sql}
    """
    values = []
    for column in columns:
        if column == "game_key":
            values.append(game_key)
        elif column == "issue":
            values.append(issue)
        else:
            values.append(_stringify(draw[column]))
    connection.execute(sql, values)


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "result" in payload:
            result = payload["result"]
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and isinstance(result.get("list"), list):
                return result["list"]
            raise ValueError("unexpected result payload shape")
        if "data" in payload:
            data = payload["data"]
            if isinstance(data, list):
                return data
            raise ValueError("unexpected data payload shape")
    raise ValueError("unexpected payload shape")


def fetch_game_rows(
    game_key: str,
    page_size: int = 100,
    page_no: int = 1,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    request_client = client or httpx.Client(timeout=20.0)
    should_close = client is None
    try:
        response = request_client.get(
            CW_API_URL,
            params={"name": game_key, "pageNo": page_no, "pageSize": page_size},
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
        return _extract_rows(response.json())
    finally:
        if should_close:
            request_client.close()


def crawl_cwl_games(
    games: list[str],
    *,
    page_size: int = 100,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    normalized_games = [game.strip().lower() for game in games if game.strip()]
    if not normalized_games:
        normalized_games = ["ssq", "3d", "kl8"]

    result_rows: list[dict[str, Any]] = []
    failed_games: list[str] = []
    total_wrote = 0

    factory = connection_factory or connect_database
    with factory() as connection:
        for index, game_key in enumerate(normalized_games):
            started_at = utc_now_iso()
            status = "success"
            error = ""
            wrote_count = 0
            savepoint_name = f"cwl_{index}"
            connection.execute(f"SAVEPOINT {savepoint_name}")
            try:
                rows = fetch_game_rows(game_key, page_size=page_size, page_no=1)
                for row in rows:
                    draw = normalize_api_row(game_key, row)
                    upsert_draw(connection, draw)
                    wrote_count += 1
            except Exception as exc:
                connection.execute(f"ROLLBACK TO {savepoint_name}")
                status = "failed"
                error = str(exc)
                failed_games.append(game_key)
                wrote_count = 0
            finally:
                connection.execute(f"RELEASE {savepoint_name}")
                finished_at = utc_now_iso()
                record_crawl_log(
                    connection,
                    provider="cwl",
                    game_key=game_key,
                    source="api",
                    page_size=page_size,
                    pages=1,
                    wrote_count=wrote_count,
                    status=status,
                    error=error,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms(started_at, finished_at),
                )
                result_rows.append(
                    {
                        "game_key": game_key,
                        "status": status,
                        "wrote_count": wrote_count,
                        "error": error,
                    }
                )
                total_wrote += wrote_count
        connection.commit()

    return {
        "provider": "cwl",
        "source": "api",
        "wrote_count": total_wrote,
        "failed_games": failed_games,
        "games": result_rows,
    }


def _parse_games(value: str) -> list[str]:
    return [game.strip() for game in value.split(",") if game.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch latest CWL draw notices.")
    parser.add_argument("--games", default="ssq,3d,qlc,kl8")
    parser.add_argument("--since-latest", action="store_true")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args(argv)

    db_path = Path(args.db_path) if args.db_path else None
    factory = (lambda: connect_database(db_path)) if db_path is not None else None
    result = crawl_cwl_games(
        _parse_games(args.games),
        page_size=args.page_size,
        connection_factory=factory,
    )

    for game in result["games"]:
        if game["status"] == "failed":
            print(f"{game['game_key']}: failed: {game['error']}", file=sys.stderr)
    print(f"wrote {result['wrote_count']} draws")
    if result["failed_games"]:
        print(f"failed games: {', '.join(result['failed_games'])}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
