import asyncio
import sys
import threading
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from lottery_luck import scheduler
from lottery_luck.api import app, lifespan
from lottery_luck.auto_update import (
    AutoUpdateConfig,
    config_from_env,
    run_due_updates,
    run_repository_updates,
    update_loop,
)


class SchedulerRepo:
    def __init__(self):
        self.next_id = 1
        self.finished = []

    def recent_tasks(self, limit=100):
        return []

    def create_task(self, *, kind, provider, game_keys, payload):
        task = {
            "id": self.next_id,
            "kind": kind,
            "provider": provider,
            "game_keys": game_keys,
            "payload": payload,
        }
        self.next_id += 1
        return task

    def start_task(self, task_id):
        return {"id": task_id, "status": "running"}

    def finish_task(self, task_id, *, status, result=None, error=""):
        task = {"id": task_id, "status": status, "result": result or {}, "error": error}
        self.finished.append(task)
        return task


def test_config_from_env_defaults_disabled_and_clamps_interval(monkeypatch):
    monkeypatch.delenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", raising=False)
    monkeypatch.delenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS", raising=False)

    default_config = config_from_env()

    assert default_config == AutoUpdateConfig(enabled=False, interval_seconds=21600)

    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "yes")
    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS", "42")

    enabled_config = config_from_env()

    assert enabled_config == AutoUpdateConfig(enabled=True, interval_seconds=900)


def test_run_due_updates_skips_recent_and_runs_stale_in_provider_order():
    calls = []

    result = run_due_updates(
        now=datetime.fromisoformat("2026-07-12T02:00:00+00:00"),
        interval_seconds=21600,
        latest_runs={
            "cwl": "2026-07-12T01:30:00+00:00",
            "sports": "2026-07-11T20:00:00+00:00",
        },
        runner=lambda provider: calls.append(provider) or {"provider": provider},
    )

    assert result == {"ran": [{"provider": "sports"}], "skipped": ["cwl"]}
    assert calls == ["sports"]


def test_run_due_updates_treats_malformed_timestamp_as_due_and_orders_providers():
    calls = []

    result = run_due_updates(
        now=datetime.fromisoformat("2026-07-12T08:00:00+00:00"),
        interval_seconds=21600,
        latest_runs={"sports": "not-a-date"},
        runner=lambda provider: calls.append(provider) or {"provider": provider},
    )

    assert result == {"ran": [{"provider": "cwl"}, {"provider": "sports"}], "skipped": []}
    assert calls == ["cwl", "sports"]


def test_run_repository_updates_uses_scheduler_defaults_and_single_flight(monkeypatch):
    calls = []

    def fake_run_once(**kwargs):
        calls.append(kwargs)
        time.sleep(0.05)
        return {"task": {"provider": kwargs["provider"], "status": "success"}}

    monkeypatch.setattr("lottery_luck.auto_update.scheduler.run_once", fake_run_once)
    monkeypatch.setattr(
        "lottery_luck.auto_update._latest_successful_runs",
        lambda repo: {"cwl": "", "sports": ""},
    )

    async def run_two_calls():
        return await asyncio.gather(
            asyncio.to_thread(run_repository_updates, interval_seconds=900, repo=object()),
            asyncio.to_thread(run_repository_updates, interval_seconds=900, repo=object()),
            return_exceptions=True,
        )

    first, second = asyncio.run(run_two_calls())

    failures = [item for item in (first, second) if isinstance(item, scheduler.CrawlInProgressError)]
    assert len(failures) == 1
    completed = next(item for item in (first, second) if not isinstance(item, Exception))
    assert completed == {
        "ran": [
            {"provider": "cwl", "task": {"provider": "cwl", "status": "success"}},
            {"provider": "sports", "task": {"provider": "sports", "status": "success"}},
        ],
        "skipped": [],
    }
    assert completed["ran"][0]["provider"] == "cwl"
    assert [(call["provider"], call["games"]) for call in calls] == [
        ("cwl", scheduler.PROVIDER_DEFAULT_GAMES["cwl"]),
        ("sports", scheduler.PROVIDER_DEFAULT_GAMES["sports"]),
    ]


def test_scheduler_run_once_rejects_competing_manual_dispatch(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    repo = SchedulerRepo()

    def blocking_cwl(games, **kwargs):
        entered.set()
        release.wait(timeout=1)
        return {"provider": "cwl", "failed_games": [], "wrote_count": 1}

    monkeypatch.setattr("lottery_luck.scheduler.crawl_cwl_games", blocking_cwl)

    worker = threading.Thread(
        target=lambda: scheduler.run_once(provider="cwl", games=["ssq"], repo=repo),
        daemon=True,
    )
    worker.start()
    assert entered.wait(timeout=1)
    try:
        try:
            scheduler.run_once(provider="cwl", games=["ssq"], repo=repo)
        except scheduler.CrawlInProgressError as exc:
            assert "crawl already in progress" in str(exc)
        else:
            raise AssertionError("competing crawl should fail")
    finally:
        release.set()
        worker.join(timeout=1)


def test_auto_batch_holds_scheduler_guard_and_allows_reentrant_run_once(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    repo = SchedulerRepo()
    calls = []

    monkeypatch.setattr("lottery_luck.auto_update._latest_successful_runs", lambda repo: {})

    def cwl_runner(games, **kwargs):
        calls.append(("cwl", games))
        entered.set()
        release.wait(timeout=1)
        return {"provider": "cwl", "failed_games": [], "wrote_count": 1}

    def sports_runner(games, **kwargs):
        calls.append(("sports", games))
        return {"provider": "sports", "failed_games": [], "wrote_count": 1}

    monkeypatch.setattr("lottery_luck.scheduler.crawl_cwl_games", cwl_runner)
    monkeypatch.setattr("lottery_luck.scheduler.crawl_sports_games", sports_runner)

    results = []
    worker = threading.Thread(
        target=lambda: results.append(run_repository_updates(interval_seconds=900, repo=repo)),
        daemon=True,
    )
    worker.start()
    assert entered.wait(timeout=1)
    try:
        try:
            scheduler.run_once(provider="sports", games=["dlt"], repo=repo)
        except scheduler.CrawlInProgressError:
            pass
        else:
            raise AssertionError("manual crawl should not overlap auto batch")
    finally:
        release.set()
        worker.join(timeout=1)

    assert [item["provider"] for item in results[0]["ran"]] == ["cwl", "sports"]
    assert calls == [
        ("cwl", scheduler.PROVIDER_DEFAULT_GAMES["cwl"]),
        ("sports", scheduler.PROVIDER_DEFAULT_GAMES["sports"]),
    ]


def test_update_loop_stops_promptly_and_survives_runner_failure():
    stop_event = asyncio.Event()
    calls = []

    def runner(**kwargs):
        calls.append("call")
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        stop_event.set()
        return {"ran": [], "skipped": []}

    async def exercise():
        await update_loop(
            AutoUpdateConfig(enabled=True, interval_seconds=900),
            stop_event,
            runner=runner,
            sleep_seconds=0.01,
        )

    asyncio.run(asyncio.wait_for(exercise(), timeout=1))

    assert calls == ["call", "call"]


def test_disabled_lifespan_does_not_start_auto_update(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "false")
    monkeypatch.setattr(
        "lottery_luck.api.auto_update.run_repository_updates",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not crawl")),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code in {200, 503}


def test_enabled_lifespan_starts_and_stops_auto_update(monkeypatch):
    calls = []

    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "true")
    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS", "900")

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return {"ran": [], "skipped": []}

    monkeypatch.setattr("lottery_luck.api.auto_update.run_repository_updates", fake_runner)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code in {200, 503}
    assert calls


def test_lifespan_shutdown_does_not_wait_forever_for_blocking_runner(monkeypatch):
    release = threading.Event()

    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "true")
    monkeypatch.setenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS", "900")
    monkeypatch.setattr("lottery_luck.api.AUTO_UPDATE_SHUTDOWN_TIMEOUT_SECONDS", 0.05, raising=False)
    monkeypatch.setattr(
        "lottery_luck.api.auto_update.run_repository_updates",
        lambda **kwargs: release.wait(timeout=5),
    )

    async def exercise():
        manager = lifespan(app)
        await manager.__aenter__()
        started = time.monotonic()
        try:
            await asyncio.wait_for(manager.__aexit__(None, None, None), timeout=0.3)
        finally:
            release.set()
        assert time.monotonic() - started < 0.25

    asyncio.run(exercise())


def test_scheduler_run_once_is_compatible_with_canonical_runner(monkeypatch):
    calls = []

    def fake_cwl(games, **kwargs):
        calls.append(("cwl", games, kwargs))
        return {"provider": "cwl", "failed_games": [], "wrote_count": 1}

    class Repo:
        def create_task(self, **kwargs):
            return {"id": 12, **kwargs}

        def start_task(self, task_id):
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            return {"id": task_id, "status": status, "result": result or {}, "error": error}

    monkeypatch.setattr("lottery_luck.scheduler.crawl_cwl_games", fake_cwl)

    result = scheduler.run_once(provider="cwl", games="", page_size=50, repo=Repo())

    assert result["task"]["status"] == "success"
    assert calls == [("cwl", ["ssq", "3d", "kl8"], {"page_size": 50})]


def test_scheduler_cli_surfaces_crawl_in_progress(monkeypatch, capsys):
    def busy(**kwargs):
        raise scheduler.CrawlInProgressError("crawl already in progress")

    monkeypatch.setattr(sys, "argv", ["scheduler", "--once", "--provider", "cwl"])
    monkeypatch.setattr("lottery_luck.scheduler.run_once", busy)

    with pytest.raises(SystemExit) as exc:
        scheduler.main()

    assert exc.value.code == 1
    assert "crawl already in progress" in capsys.readouterr().err
