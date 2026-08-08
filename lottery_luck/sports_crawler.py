from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from .crawler import _json_stringify, _split_draw_date, _stringify, upsert_new_draws
from .data_health import duration_ms, record_crawl_log, utc_now_iso
from .database import connect_database
from .rules import GAME_RULES


SPORTS_API_BASE_URL = "https://webapi.sporttery.cn"
SPORTS_API_PATH = "/gateway/lottery/getHistoryPageListV1.qry"
SPORTS_MIRROR_API_URL = "https://api.huiniao.top/interface/home/lotteryHistory"
SPORTS_GAME_NUMBERS = {
    "dlt": "85",
    "pl3": "35",
    "pl5": "350133",
}
SPORTS_PAGE_KEYS = {
    "dlt": "dlt",
    "pl3": "pls",
    "pl5": "plw",
}
SPORTS_MIRROR_TYPES = {
    "dlt": "dlt",
    "pl3": "pls",
    "pl5": "plw",
}
SPORTS_MIRROR_NUMBER_FIELDS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
)
USER_AGENT = "lottery-luck-sports-crawler/0.1 (+https://www.lottery.gov.cn)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _first_value(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return default


def _require_sports_game(game_key: str) -> str:
    game = game_key.strip().lower()
    if game not in SPORTS_GAME_NUMBERS:
        raise ValueError(f"unsupported sports game_key: {game}")
    return game


def official_history_page_url(game_key: str) -> str:
    game = _require_sports_game(game_key)
    return f"https://www.lottery.gov.cn/kj/kjlb.html?{SPORTS_PAGE_KEYS[game]}"


def _split_result_tokens(value: Any, expected_count: int, pair_digits: bool = False) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_stringify(item).strip() for item in value if _stringify(item).strip()]

    text = _stringify(value).strip()
    if not text:
        return []

    tokens = re.findall(r"\d+", text)
    if len(tokens) == 1:
        raw = tokens[0]
        if pair_digits and len(raw) >= expected_count * 2:
            return [raw[index : index + 2] for index in range(0, expected_count * 2, 2)]
        if not pair_digits and len(raw) >= expected_count:
            return list(raw[:expected_count])
    return tokens


def _normalize_number_tokens(game_key: str, tokens: list[str]) -> list[str]:
    if game_key == "dlt":
        return [token.zfill(2) for token in tokens]
    return [str(int(token)) if token.isdigit() else token for token in tokens]


def normalize_sports_row(game_key: str, row: dict[str, Any]) -> dict[str, Any]:
    game = _require_sports_game(game_key)
    rule = GAME_RULES[game]
    draw_date, parsed_week = _split_draw_date(
        _first_value(row, "lotteryDrawTime", "draw_date", "drawDate", "date")
    )
    week = _stringify(_first_value(row, "week", "weekday", default=parsed_week))

    explicit_main = _split_result_tokens(
        _first_value(row, "red_numbers", "redNumbers", "frontWinningNum", "frontArea"),
        rule.main_count,
        game == "dlt",
    )
    explicit_special = _split_result_tokens(
        _first_value(row, "blue_number", "blueNumber", "backWinningNum", "backArea"),
        rule.special_count,
        game == "dlt",
    )
    if explicit_main:
        main_tokens = explicit_main[: rule.main_count]
        special_tokens = explicit_special[: rule.special_count]
    else:
        expected = rule.main_count + rule.special_count
        result_tokens = _split_result_tokens(
            _first_value(row, "lotteryDrawResult", "draw_result", "drawResult", "result"),
            expected,
            game == "dlt",
        )
        main_tokens = result_tokens[: rule.main_count]
        special_tokens = result_tokens[rule.main_count : rule.main_count + rule.special_count]

    prizegrades = _first_value(row, "prizeLevelList", "prizegrades", "prizeGrades", default=[])
    content_parts = [
        _stringify(_first_value(row, "lotterySaleEndtime", "saleEndTime")),
        _stringify(_first_value(row, "lotteryDrawStatus", "drawStatus")),
    ]
    content = " / ".join(part for part in content_parts if part)

    return {
        "game_key": game,
        "issue": _stringify(_first_value(row, "lotteryDrawNum", "issue", "code")),
        "game_name": _stringify(
            _first_value(row, "lotteryGameName", "game_name", "name", default=rule.name)
        ),
        "draw_date": draw_date,
        "week": week,
        "red_numbers": ",".join(_normalize_number_tokens(game, main_tokens)),
        "blue_number": ",".join(_normalize_number_tokens(game, special_tokens)),
        "sales": _stringify(_first_value(row, "totalSaleAmount", "sales")),
        "pool_money": _stringify(_first_value(row, "poolBalanceAfterdraw", "pool_money", "poolMoney")),
        "content": content,
        "prizegrades_json": _json_stringify(prizegrades),
        "raw_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if payload.get("errorCode") not in (None, 0, "0"):
            raise ValueError(f"sports api returned errorCode={payload.get('errorCode')}")
        value = payload.get("value", payload.get("result", payload.get("data")))
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get("list"), list):
            return value["list"]
        if isinstance(payload.get("list"), list):
            return payload["list"]
    raise ValueError("unexpected sports payload shape")


def _api_url(base_url: str | None = None) -> str:
    base = (base_url or os.getenv("SPORTS_LOTTERY_API_BASE_URL") or SPORTS_API_BASE_URL).rstrip("/")
    return f"{base}{SPORTS_API_PATH}"


def _api_params(game_key: str, page_size: int, page_no: int) -> dict[str, str]:
    game = _require_sports_game(game_key)
    return {
        "gameNo": SPORTS_GAME_NUMBERS[game],
        "provinceId": "0",
        "pageSize": str(page_size),
        "pageNo": str(page_no),
        "isVerify": "1",
    }


def fetch_game_rows(
    game_key: str,
    page_size: int = 30,
    page_no: int = 1,
    client: httpx.Client | None = None,
    base_url: str | None = None,
) -> list[dict[str, Any]]:
    game = _require_sports_game(game_key)
    request_client = client or httpx.Client(timeout=20.0)
    should_close = client is None
    try:
        response = request_client.get(
            _api_url(base_url),
            params=_api_params(game, page_size, page_no),
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.lottery.gov.cn/kj/kjlb.html",
            },
        )
        response.raise_for_status()
        return _extract_rows(response.json())
    finally:
        if should_close:
            request_client.close()


def fetch_game_rows_mirror(
    game_key: str,
    page_size: int = 30,
    page_no: int = 1,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    game = _require_sports_game(game_key)
    request_client = client or httpx.Client(timeout=20.0)
    should_close = client is None
    try:
        response = request_client.get(
            SPORTS_MIRROR_API_URL,
            params={
                "type": SPORTS_MIRROR_TYPES[game],
                "page": str(page_no),
                "limit": str(page_size),
            },
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (1, "1"):
            raise ValueError(f"sports mirror returned code={payload.get('code')}")
        rows = (((payload.get("data") or {}).get("data") or {}).get("list"))
        if not isinstance(rows, list):
            raise ValueError("unexpected sports mirror payload shape")

        number_count = 7 if game == "dlt" else 3
        return [
            {
                "lotteryDrawNum": row.get("code"),
                "lotteryDrawTime": row.get("day"),
                "lotteryDrawResult": " ".join(
                    _stringify(row.get(field)).zfill(2 if game == "dlt" else 1)
                    for field in SPORTS_MIRROR_NUMBER_FIELDS[:number_count]
                ),
                "lotteryGameName": GAME_RULES[game].name,
                "mirrorPayload": row,
            }
            for row in rows
            if isinstance(row, dict)
        ]
    finally:
        if should_close:
            request_client.close()


BrowserPayloadRunner = Callable[[str, str, dict[str, str], int, bool], Any]


def fetch_game_rows_browser(
    game_key: str,
    page_size: int = 30,
    page_no: int = 1,
    base_url: str | None = None,
    timeout_ms: int = 30000,
    headless: bool = True,
    runner: BrowserPayloadRunner | None = None,
) -> list[dict[str, Any]]:
    game = _require_sports_game(game_key)
    page_url = official_history_page_url(game)
    api_url = _api_url(base_url)
    params = _api_params(game, page_size, page_no)
    payload = (
        runner(page_url, api_url, params, timeout_ms, headless)
        if runner is not None
        else _playwright_fetch_payload(page_url, api_url, params, timeout_ms, headless)
    )
    return _extract_rows(payload)


def fetch_game_rows_auto(
    game_key: str,
    page_size: int = 30,
    page_no: int = 1,
    client: httpx.Client | None = None,
    base_url: str | None = None,
    timeout_ms: int = 30000,
    headless: bool = True,
) -> list[dict[str, Any]]:
    try:
        return fetch_game_rows(
            game_key,
            page_size=page_size,
            page_no=page_no,
            client=client,
            base_url=base_url,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response is None or exc.response.status_code != 403:
            raise
        return fetch_game_rows_browser(
            game_key,
            page_size=page_size,
            page_no=page_no,
            base_url=base_url,
            timeout_ms=timeout_ms,
            headless=headless,
        )


def _playwright_fetch_payload(
    page_url: str,
    api_url: str,
    params: dict[str, str],
    timeout_ms: int,
    headless: bool,
) -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright 未安装，无法使用官方页面浏览器态爬取。"
            "请先执行：pip install playwright && python -m playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(user_agent=BROWSER_USER_AGENT, locale="zh-CN")
            page = context.new_page()
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_function(
                    "() => { const frame = document.querySelector('#iFrame1');"
                    " return frame && frame.src && frame.src.includes('/html/kj/'); }",
                    timeout=timeout_ms,
                )
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass

            target_frame = next(
                (frame for frame in page.frames if "/html/kj/" in frame.url),
                page.main_frame,
            )
            return target_frame.evaluate(
                """
                async ({ apiUrl, params }) => {
                  const jq = window.jQuery || window.$;
                  if (!jq) {
                    throw new Error("official sports page did not load jQuery");
                  }
                  return await new Promise((resolve, reject) => {
                    jq.ajax({
                      url: apiUrl,
                      type: "get",
                      dataType: "json",
                      data: params,
                      success: resolve,
                      error: (xhr, status, error) => {
                        const body = xhr && xhr.responseText ? xhr.responseText.slice(0, 200) : "";
                        reject(new Error(`official sports API ${xhr && xhr.status}: ${status} ${error || ""} ${body}`));
                      }
                    });
                  });
                }
                """,
                {"apiUrl": api_url, "params": params},
            )
        finally:
            browser.close()


def _parse_games(value: str) -> list[str]:
    return [game.strip().lower() for game in value.split(",") if game.strip()]


def crawl_sports_games(
    games: list[str],
    *,
    source: str = "auto",
    page_size: int = 30,
    page_no: int = 1,
    pages: int = 1,
    base_url: str | None = None,
    timeout_ms: int = 30000,
    headless: bool = True,
    db_path: Path | str | None = None,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    wrote_count = 0
    failed_games = []
    results = []
    if connection_factory is not None:
        factory = connection_factory
    elif db_path is not None:
        factory = lambda: connect_database(db_path)
    else:
        factory = connect_database
    with factory() as connection:
        for game_key in games:
            game = _require_sports_game(game_key)
            started_at = utc_now_iso()
            game_wrote_count = 0
            status = "success"
            error = ""
            try:
                rows = []
                for page_offset in range(max(1, pages)):
                    current_page = page_no + page_offset
                    rows.extend(
                        _fetch_rows_by_source(
                            game,
                            source=source,
                            page_size=page_size,
                            page_no=current_page,
                            base_url=base_url,
                            timeout_ms=timeout_ms,
                            headless=headless,
                        )
                    )
                draws = [normalize_sports_row(game, row) for row in rows]
                game_wrote_count = upsert_new_draws(connection, draws)
            except Exception as exc:
                connection.rollback()
                status = "failed"
                error = str(exc)
                failed_games.append(game)
                game_wrote_count = 0
            finished_at = utc_now_iso()
            record_crawl_log(
                connection,
                provider="sports",
                game_key=game,
                source=source,
                page_size=page_size,
                pages=max(1, pages),
                wrote_count=game_wrote_count,
                status=status,
                error=error,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms(started_at, finished_at),
            )
            connection.commit()
            results.append(
                {
                    "game_key": game,
                    "status": status,
                    "wrote_count": game_wrote_count,
                    "error": error,
                }
            )
            wrote_count += game_wrote_count

    return {
        "provider": "sports",
        "source": source,
        "wrote_count": wrote_count,
        "failed_games": failed_games,
        "games": results,
    }


def _fetch_rows_by_source(
    game_key: str,
    *,
    source: str,
    page_size: int,
    page_no: int,
    base_url: str | None,
    timeout_ms: int,
    headless: bool,
) -> list[dict[str, Any]]:
    if source == "browser":
        return fetch_game_rows_browser(
            game_key,
            page_size=page_size,
            page_no=page_no,
            base_url=base_url,
            timeout_ms=timeout_ms,
            headless=headless,
        )
    if source == "direct":
        return fetch_game_rows(
            game_key,
            page_size=page_size,
            page_no=page_no,
            base_url=base_url,
        )
    if source == "mirror":
        return fetch_game_rows_mirror(
            game_key,
            page_size=page_size,
            page_no=page_no,
        )
    return fetch_game_rows_auto(
        game_key,
        page_size=page_size,
        page_no=page_no,
        base_url=base_url,
        timeout_ms=timeout_ms,
        headless=headless,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch latest sports lottery draw notices.")
    parser.add_argument("--games", default="dlt,pl3,pl5")
    parser.add_argument("--page-size", type=int, default=30)
    parser.add_argument("--page-no", type=int, default=1)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--source",
        choices=["auto", "direct", "browser", "mirror"],
        default="auto",
    )
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--browser-headed", action="store_true")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args(argv)

    result = crawl_sports_games(
        _parse_games(args.games),
        source=args.source,
        page_size=args.page_size,
        page_no=args.page_no,
        pages=args.pages,
        base_url=args.base_url,
        timeout_ms=args.timeout_ms,
        headless=not args.browser_headed,
        db_path=args.db_path,
    )

    for game in result["games"]:
        if game["status"] == "failed":
            print(f"{game['game_key']}: failed: {game['error']}", file=sys.stderr)
    print(f"wrote {result['wrote_count']} sports draws")
    if result["failed_games"]:
        print(f"failed games: {', '.join(result['failed_games'])}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
