from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from . import scheduler
from .repository import LotteryRepository


PROVIDER_ORDER = ("cwl", "sports")
DEFAULT_INTERVAL_SECONDS = 21600
MIN_INTERVAL_SECONDS = 900
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoUpdateConfig:
    enabled: bool
    interval_seconds: int


def config_from_env() -> AutoUpdateConfig:
    enabled = (
        os.getenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "").strip().lower()
        in _TRUTHY_ENV_VALUES
    )
    return AutoUpdateConfig(
        enabled=enabled,
        interval_seconds=max(
            MIN_INTERVAL_SECONDS,
            _safe_int(
                os.getenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS"),
                DEFAULT_INTERVAL_SECONDS,
            ),
        ),
    )


def run_due_updates(
    *,
    now: datetime,
    interval_seconds: int,
    latest_runs: dict[str, Any],
    runner: Callable[[str], Any],
) -> dict[str, list[Any]]:
    current = _aware_datetime(now)
    ran: list[Any] = []
    skipped: list[str] = []
    for provider in PROVIDER_ORDER:
        finished_at = _latest_finished_at(latest_runs.get(provider))
        if finished_at is not None and (current - finished_at).total_seconds() < interval_seconds:
            skipped.append(provider)
            continue
        ran.append(runner(provider))
    return {"ran": ran, "skipped": skipped}


def run_repository_updates(
    *,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    repo: LotteryRepository | None = None,
) -> dict[str, list[Any]]:
    with scheduler.crawl_dispatch_guard():
        repository = repo or LotteryRepository()
        latest_runs = _latest_successful_runs(repository)

        def runner(provider: str) -> dict[str, Any]:
            result = scheduler.run_once(
                provider=provider,
                games=scheduler.PROVIDER_DEFAULT_GAMES[provider],
                repo=repository,
            )
            return {"provider": provider, **result}

        return run_due_updates(
            now=datetime.now(timezone.utc),
            interval_seconds=max(MIN_INTERVAL_SECONDS, int(interval_seconds)),
            latest_runs=latest_runs,
            runner=runner,
        )


async def update_loop(
    config: AutoUpdateConfig,
    stop_event: asyncio.Event,
    *,
    runner: Callable[..., dict[str, list[Any]]] | None = None,
    sleep_seconds: float | None = None,
) -> None:
    wait_seconds = sleep_seconds if sleep_seconds is not None else config.interval_seconds
    update_runner = runner or run_repository_updates
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(update_runner, interval_seconds=config.interval_seconds)
        except Exception:
            logger.exception("automatic data update failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_seconds)
        except TimeoutError:
            continue


def _latest_successful_runs(repo: LotteryRepository) -> dict[str, str]:
    latest: dict[str, str] = {}
    for task in repo.recent_tasks(limit=100):
        provider = str(task.get("provider") or "").strip().lower()
        if provider not in PROVIDER_ORDER or provider in latest:
            continue
        if str(task.get("kind") or "") != "crawl":
            continue
        if str(task.get("status") or "").lower() != "success":
            continue
        latest[provider] = str(task.get("finished_at") or "")
    return latest


def _latest_finished_at(value: Any) -> datetime | None:
    if isinstance(value, dict):
        value = value.get("finished_at")
    if not value:
        return None
    try:
        return _parse_iso_datetime(str(value))
    except ValueError:
        return None


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    return _aware_datetime(parsed)


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
