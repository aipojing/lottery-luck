from __future__ import annotations

import argparse
import json
import sys
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any, Callable

from .crawler import crawl_cwl_games
from .repository import LotteryRepository
from .sports_crawler import crawl_sports_games


PROVIDER_DEFAULT_GAMES = {
    "cwl": ["ssq", "3d", "kl8"],
    "sports": ["dlt", "pl3", "pl5"],
}
_CRAWL_DISPATCH_LOCK = threading.RLock()


class CrawlInProgressError(RuntimeError):
    pass


@contextmanager
def crawl_dispatch_guard() -> Iterator[None]:
    if not _CRAWL_DISPATCH_LOCK.acquire(blocking=False):
        raise CrawlInProgressError("crawl already in progress")
    try:
        yield
    finally:
        _CRAWL_DISPATCH_LOCK.release()


def normalize_scheduler_games(provider: str, games: str | list[str]) -> list[str]:
    provider_key = provider.strip().lower()
    allowed = set(PROVIDER_DEFAULT_GAMES[provider_key])
    if isinstance(games, str):
        raw = games.replace("，", ",").replace("、", ",").replace("/", ",").split(",")
    else:
        raw = games
    selected = [str(game).strip().lower() for game in raw if str(game).strip().lower() in allowed]
    return selected or list(PROVIDER_DEFAULT_GAMES[provider_key])


def run_once(
    *,
    provider: str,
    games: str | list[str],
    source: str = "auto",
    page_size: int = 100,
    page_no: int = 1,
    pages: int = 1,
    timeout_ms: int = 30000,
    browser_headed: bool = False,
    repo: LotteryRepository | None = None,
    cwl_runner: Callable[..., dict[str, Any]] | None = None,
    sports_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    with crawl_dispatch_guard():
        provider_key = provider.strip().lower()
        selected_games = normalize_scheduler_games(provider_key, games)
        repository = repo or LotteryRepository()
        task = repository.create_task(
            kind="crawl",
            provider=provider_key,
            game_keys=selected_games,
            payload={
                "provider": provider_key,
                "games": selected_games,
                "source": source,
                "page_size": page_size,
                "page_no": page_no,
                "pages": pages,
                "timeout_ms": timeout_ms,
                "browser_headed": browser_headed,
            },
        )
        repository.start_task(task["id"])
        try:
            if provider_key == "cwl":
                result = (cwl_runner or crawl_cwl_games)(selected_games, page_size=page_size)
            else:
                result = (sports_runner or crawl_sports_games)(
                    selected_games,
                    source=source,
                    page_size=page_size,
                    page_no=page_no,
                    pages=pages,
                    timeout_ms=timeout_ms,
                    headless=not browser_headed,
                )
            status = "failed" if result.get("failed_games") else "success"
            error = _crawl_error_summary(result)
            finished = repository.finish_task(task["id"], status=status, result=result, error=error)
        except Exception as exc:
            error = str(exc)
            result = _exception_crawl_result(provider_key, selected_games, error)
            finished = repository.finish_task(
                task["id"],
                status="failed",
                result=result,
                error=error,
            )
        return {"task": finished}


def _crawl_error_summary(result: dict[str, Any]) -> str:
    rows = []
    for row in result.get("games") or []:
        if str(row.get("status") or "").lower() not in {"failed", "error"}:
            continue
        game_key = str(row.get("game_key") or "").strip()
        error = str(row.get("error") or "").strip()
        rows.append(f"{game_key}: {error}" if error else game_key)
    if rows:
        return "; ".join(rows)
    return "; ".join(str(item) for item in result.get("failed_games") or [])


def _exception_crawl_result(provider: str, games: list[str], error: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": "failed",
        "wrote_count": 0,
        "failed_games": list(games),
        "error": error,
        "games": [
            {
                "game_key": game,
                "status": "failed",
                "wrote_count": 0,
                "error": error,
            }
            for game in games
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lottery crawl scheduler tasks.")
    parser.add_argument("--once", action="store_true", help="Run one crawl task immediately.")
    parser.add_argument("--provider", choices=["cwl", "sports"], default="cwl")
    parser.add_argument("--games", default="")
    parser.add_argument("--source", choices=["auto", "direct", "browser"], default="auto")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--browser-headed", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.once:
        parser.error("only --once is supported in scheduler V1")
    try:
        result = run_once(
            provider=args.provider,
            games=args.games,
            source=args.source,
            page_size=args.page_size,
            pages=args.pages,
            timeout_ms=args.timeout_ms,
            browser_headed=args.browser_headed,
        )
    except CrawlInProgressError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
