from __future__ import annotations

import hashlib
import json
import re
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import Page, sync_playwright

from lottery_luck.api import app, get_repository
from lottery_luck.config import DB_PATH
from lottery_luck.data_health import build_public_freshness, record_crawl_log
from lottery_luck.repository import LotteryRepository


TODAY = date(2026, 7, 13)
LATEST_DRAW_DATE = date(2026, 7, 12)
LATEST_ISSUE = "2026193"
TARGET_ISSUE = "2026194"
TARGET_DRAW_DATE = "2026-07-13"
CLIENT_ID = "task15-retention-client"
OTHER_CLIENT_ID = "task15-other-client"
PRIVATE_VALUES = [
    "测试用户",
    "1990-01-01",
    "杭州",
    "上海",
    "client_id",
    "birth_date",
    "birth_hour",
    "birth_place",
    "current_city",
]


@dataclass(frozen=True)
class RepoFingerprint:
    path: Path
    mtime_ns: int | None
    digest: str | None


@pytest.fixture()
def isolated_repo(tmp_path: Path):
    repo = _build_isolated_repo(tmp_path / "retention-flow.sqlite")
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def live_server_url(isolated_repo: LotteryRepository, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOTTERY_LUCK_AI_ENABLED", "0")
    monkeypatch.setattr(
        "lottery_luck.api.PredictionEngine.predict",
        _mock_prediction,
    )
    monkeypatch.setattr(
        "lottery_luck.api.build_public_freshness",
        _build_public_freshness_for_retention_today,
    )
    app.dependency_overrides[get_repository] = lambda: isolated_repo
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            server.should_exit = True
            raise RuntimeError("uvicorn test server did not start")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        app.dependency_overrides.clear()


@pytest.fixture()
def browser_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            yield page
        finally:
            browser.close()


def test_retention_fixture_is_isolated_and_fresh(isolated_repo: LotteryRepository):
    before = _fingerprint_repo_sqlite()
    client = TestClient(app)

    health = client.get(f"/api/health?today={TODAY.isoformat()}")
    summary = client.get(
        f"/api/workbench/3d/summary?window=30&today={TODAY.isoformat()}",
        headers={"X-Lottery-Client-Id": CLIENT_ID},
    )
    after = _fingerprint_repo_sqlite()

    assert isolated_repo.db_path.parent.name.startswith("test_")
    assert isolated_repo.db_path != DB_PATH
    assert str(isolated_repo.db_path).startswith("/private/") or "/pytest-" in str(
        isolated_repo.db_path
    )
    assert before == after

    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["data"]["3d"]["latest_issue"] == LATEST_ISSUE
    assert health_payload["data"]["3d"]["latest_date"] == LATEST_DRAW_DATE.isoformat()
    assert health_payload["data"]["3d"]["status"] == "fresh"
    assert health_payload["data"]["3d"]["can_claim_current"] is True
    assert health_payload["data"]["3d"]["sync_error"] == ""

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["freshness"]["status"] == "fresh"
    assert summary_payload["current_target"] == {
        "target_issue": TARGET_ISSUE,
        "target_draw_date": TARGET_DRAW_DATE,
    }
    assert len(summary_payload["recent_draws"]) == 10
    assert summary_payload["recent_draws"][0]["issue"] == LATEST_ISSUE
    assert summary_payload["actions"]["can_save_current"] is True
    assert summary_payload["actions"]["can_filter_current"] is True
    assert summary_payload["active_plan_count"] == 0


def test_3d_retention_flow_preserves_plan_snapshot_review_and_events(
    isolated_repo: LotteryRepository,
    live_server_url: str,
    browser_page: Page,
):
    _install_client_id(browser_page, live_server_url, CLIENT_ID)
    _complete_real_3d_prediction(browser_page, live_server_url)

    events_before_save = _event_names(isolated_repo)
    assert events_before_save == ["prediction_completed"]

    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => !document.querySelector('#savedPlanLink').hidden",
        timeout=5000,
    )
    saved_id = _href_plan_id(browser_page.locator("#savedPlanLink").get_attribute("href"))
    fortune_plan = _plan_by_id(isolated_repo, saved_id)
    assert fortune_plan["client_id"] == CLIENT_ID
    assert fortune_plan["source_type"] == "fortune"
    assert fortune_plan["target_issue"] == TARGET_ISSUE
    assert fortune_plan["target_draw_date"] == TARGET_DRAW_DATE
    assert fortune_plan["condition_snapshot"]["mode"] == "simple"
    assert fortune_plan["condition_snapshot"]["latest_data_issue"] == LATEST_ISSUE
    assert fortune_plan["review"] is None

    browser_page.goto(
        f"{live_server_url}/analysis.html?game=3d&tool=reduction&window=120&today={TODAY.isoformat()}"
    )
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDManualSave')?.disabled === false",
        timeout=5000,
    )
    assert browser_page.locator('[data-three-d-tool-panel="reduction"]').is_visible()
    assert "本期 2026194 / 2026-07-13" in browser_page.locator("#threeDTargetLabel").inner_text()

    browser_page.locator("#threeDSumMin").fill("6")
    browser_page.locator("#threeDSumMax").fill("18")
    browser_page.locator("#threeDSpanMin").fill("1")
    browser_page.locator("#threeDSpanMax").fill("8")
    browser_page.locator('#threeDTypeGroup input[value="组六"]').check()
    browser_page.locator('#threeDOddGroup input[value="2"]').check()
    browser_page.locator("#threeDPositionInclude0").fill("1")
    browser_page.locator("#threeDPositionExclude1").fill("9")
    browser_page.locator("#threeDPositionInclude2").fill("3")

    with browser_page.expect_response(re.compile(r"/api/3d/filter(?:\\?|$)")):
        browser_page.locator("#threeDFilterForm button[type='submit']").click()
    browser_page.wait_for_function(
        "() => document.querySelectorAll('[data-candidate-number]').length > 0",
        timeout=5000,
    )
    # The reduction states the scale it really achieved against the real backend: the whole
    # three-digit space in, and the server's own total out — not the length of the capped list.
    reduction_result = browser_page.locator("#threeDFilterResult").inner_text()
    assert "原始范围 1000 组" in reduction_result
    reduced_total = int(re.search(r"筛后候选 (\d+) 组", reduction_result).group(1))
    shown = browser_page.locator("[data-candidate-number]").count()
    assert 0 < shown <= reduced_total < 1000

    first_candidate = browser_page.locator("[data-candidate-number]").nth(0)
    candidate_number = first_candidate.get_attribute("data-candidate-number")
    first_candidate.check()
    browser_page.locator("#threeDFilterSave").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDFilterStatus').textContent.includes('已保存')",
        timeout=5000,
    )
    filter_plan_id = _latest_plan_id_by_source(isolated_repo, "filter")
    filter_plan = _plan_by_id(isolated_repo, filter_plan_id)
    assert filter_plan["source_type"] == "filter"
    assert filter_plan["target_issue"] == TARGET_ISSUE
    assert filter_plan["review"] is None
    assert filter_plan["entries"][0]["main_numbers"] == [int(char) for char in candidate_number]
    snapshot = filter_plan["condition_snapshot"]
    assert snapshot["mode"] == "pro"
    assert snapshot["analysis_window"] == 120
    assert snapshot["latest_data_issue"] == LATEST_ISSUE
    assert snapshot["conditions_json"]["sum_min"] == 6
    assert snapshot["conditions_json"]["sum_max"] == 18
    assert snapshot["conditions_json"]["span_min"] == 1
    assert snapshot["conditions_json"]["span_max"] == 8
    assert snapshot["conditions_json"]["types"] == ["组六"]
    assert snapshot["conditions_json"]["odd_counts"] == [2]
    assert snapshot["conditions_json"]["position_include"] == {"0": [1], "2": [3]}
    assert snapshot["conditions_json"]["position_exclude"] == {"1": [9]}

    _insert_draw(isolated_repo.db_path, TARGET_ISSUE, TARGET_DRAW_DATE, [1, 2, 3])
    pending_review = TestClient(app).patch(
        f"/api/plans/{filter_plan_id}",
        headers={"X-Lottery-Client-Id": CLIENT_ID},
        json={"status": "pending_review"},
    )
    assert pending_review.status_code == 200
    assert _plan_by_id(isolated_repo, filter_plan_id)["status"] == "pending_review"
    browser_page.add_init_script(
        """
        window.IntersectionObserver = class {
          constructor(callback) {
            this.callback = callback;
          }
          observe(target) {
            this.callback([{isIntersecting: true, target}], this);
          }
          disconnect() {}
        };
        """
    )
    with browser_page.expect_response(f"{live_server_url}/api/plans/{filter_plan_id}/review") as review_response:
        browser_page.goto(f"{live_server_url}/result.html?id={filter_plan_id}")
    assert review_response.value.status == 200
    browser_page.wait_for_function(
        "() => document.querySelector('#resultStatus').textContent.includes('已复盘')",
        timeout=5000,
    )
    reviewed = _plan_by_id(isolated_repo, filter_plan_id)
    assert reviewed["status"] == "reviewed"
    assert reviewed["review"]["review_status"] == "direct_hit"
    assert reviewed["review"]["direct_hit"] is True
    assert reviewed["review"]["draw_issue"] == TARGET_ISSUE

    with browser_page.expect_response(
        f"{live_server_url}/api/plans/{filter_plan_id}/carry-forward"
    ) as carry_response:
        browser_page.locator("#carryForwardAction").click()
    assert carry_response.value.status == 200
    carried_id = _latest_plan_id_by_source(isolated_repo, "carried")
    browser_page.wait_for_url(f"**/result.html?id={carried_id}", timeout=5000)
    carried = _plan_by_id(isolated_repo, carried_id)
    assert carried["source_type"] == "carried"
    assert carried["carried_from_plan_id"] == filter_plan_id
    assert carried["target_issue"] == "2026195"
    assert carried["target_draw_date"] == "2026-07-14"
    assert carried["review"] is None
    assert carried["condition_snapshot"]["mode"] == "pro"
    assert carried["condition_snapshot"]["conditions_json"] == snapshot["conditions_json"]

    server_summary = TestClient(app).get(
        f"/api/workbench/3d/summary?window=120&today={TODAY.isoformat()}",
        headers={"X-Lottery-Client-Id": CLIENT_ID},
    )
    assert server_summary.status_code == 200
    assert server_summary.json()["current_target"] == {
        "target_issue": "2026195",
        "target_draw_date": "2026-07-14",
    }

    events = _events(isolated_repo)
    event_names = _event_names_from_rows(events)
    assert event_names[:2] == ["prediction_completed", "plan_saved"]
    # Deep-linking into a tool loads the summary and brings the panel up in the same tick, so
    # workbench_opened and tool_opened are posted together and their arrival order says
    # nothing. Everything the user did afterwards stays strictly ordered.
    assert sorted(event_names[2:4]) == ["tool_opened", "workbench_opened"]
    assert event_names[4:] == [
        "tool_result_generated",
        "plan_edited",
        "review_viewed",
        "plan_carried_forward",
    ]
    assert event_names.count("plan_edited") == 1
    assert event_names.count("plan_saved") == 1
    assert event_names.count("review_viewed") == 1
    # The reduction panel opened once and produced one submitted result: the renders, the plan
    # save and the summary refresh in between recorded nothing.
    assert event_names.count("tool_opened") == 1
    assert event_names.count("tool_result_generated") == 1
    tool_events = [event for event in events if event["event_name"].startswith("tool_")]
    assert [event["properties"] for event in tool_events] == [
        # 缩水选号 sends the statistics window with its request — here the 120 the deep link
        # carried, the same window the saved plan's snapshot records — so the open event says so.
        {"game_key": "3d", "tool_key": "reduction", "window": 120},
        {"game_key": "3d", "tool_key": "reduction", "result_count": reduced_total},
    ]
    _assert_events_safe(events)


def test_stale_home_and_workbench_disable_current_saves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser_page: Page,
):
    repo = _build_isolated_repo(tmp_path / "stale.sqlite", latest_date=date(2026, 7, 5))
    with _served_repo(repo, monkeypatch) as url:
        _install_client_id(browser_page, url, CLIENT_ID)
        _complete_real_3d_prediction(browser_page, url)
        assert browser_page.locator("#savePlanButton").is_disabled()
        assert "过期" in browser_page.locator("#planSaveStatus").inner_text()

        browser_page.goto(f"{url}/analysis.html?game=3d&tool=reduction")
        browser_page.wait_for_function(
            "() => document.querySelector('#threeDManualSave')?.disabled === true",
            timeout=5000,
        )
        assert browser_page.locator("#threeDManualSave").is_disabled()
        assert browser_page.locator("#threeDFilterSave").is_disabled()


def test_save_500_and_network_pending_retry_preserve_prediction_and_are_idempotent(
    live_server_url: str,
    browser_page: Page,
):
    _install_client_id(browser_page, live_server_url, CLIENT_ID)
    _complete_real_3d_prediction(browser_page, live_server_url)
    original_number = browser_page.locator("#fortuneNumber").inner_text()
    calls = []

    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: (
            calls.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=500, content_type="application/json", body='{"detail":"boom"}'),
        ),
    )
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('重试')",
        timeout=5000,
    )
    assert browser_page.locator("#fortuneNumber").inner_text() == original_number
    first_request_id = calls[0]["request_id"]

    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('重试')",
        timeout=5000,
    )
    assert calls[1]["request_id"] == first_request_id

    browser_page.unroute(f"{live_server_url}/api/plans")
    browser_page.route(f"{live_server_url}/api/plans", lambda route: route.abort("failed"))
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('待同步')",
        timeout=5000,
    )
    assert browser_page.locator("#fortuneNumber").inner_text() == original_number


def test_review_missing_draw_waits_once_other_client_404_and_admin_401(
    isolated_repo: LotteryRepository,
    live_server_url: str,
    browser_page: Page,
):
    client = TestClient(app)
    review_requests = []
    created = client.post(
        "/api/plans",
        headers={"X-Lottery-Client-Id": CLIENT_ID},
        json=_plan_payload(request_id="review-pending-1"),
    )
    assert created.status_code == 201
    plan_id = created.json()["plan"]["id"]

    other = client.get(f"/api/plans/{plan_id}", headers={"X-Lottery-Client-Id": OTHER_CLIENT_ID})
    assert other.status_code == 404
    assert client.get("/api/admin/settings").status_code == 401

    _install_client_id(browser_page, live_server_url, CLIENT_ID)
    browser_page.on(
        "request",
        lambda request: review_requests.append(request.url)
        if request.url.endswith(f"/api/plans/{plan_id}/review")
        else None,
    )
    browser_page.goto(f"{live_server_url}/result.html?id={plan_id}")
    browser_page.wait_for_function(
        "() => document.querySelector('#reviewAction').disabled === true",
        timeout=5000,
    )
    browser_page.wait_for_load_state("networkidle")
    assert browser_page.locator("#reviewAction").inner_text() == "开奖后可复盘"
    assert review_requests == []
    assert _plan_by_id(isolated_repo, plan_id)["review"] is None
    assert _plan_by_id(isolated_repo, plan_id)["status"] == "saved"


def test_reduced_motion_key_path_can_predict_save_and_open_detail(
    isolated_repo: LotteryRepository,
    live_server_url: str,
    browser_page: Page,
):
    browser_page.emulate_media(reduced_motion="reduce")
    _install_client_id(browser_page, live_server_url, CLIENT_ID)
    _complete_real_3d_prediction(browser_page, live_server_url)
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => !document.querySelector('#savedPlanLink').hidden",
        timeout=5000,
    )
    plan_id = _href_plan_id(browser_page.locator("#savedPlanLink").get_attribute("href"))
    browser_page.locator("#savedPlanLink").click()
    browser_page.wait_for_url(f"**/result.html?id={plan_id}", timeout=5000)
    browser_page.wait_for_function(
        "() => document.querySelector('#resultTitle').textContent.length > 0",
        timeout=5000,
    )
    assert _plan_by_id(isolated_repo, plan_id)["source_type"] == "fortune"


@contextmanager
def _served_repo(repo: LotteryRepository, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOTTERY_LUCK_AI_ENABLED", "0")
    monkeypatch.setattr(
        "lottery_luck.api.PredictionEngine.predict",
        _mock_prediction,
    )
    app.dependency_overrides[get_repository] = lambda: repo
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            server.should_exit = True
            raise RuntimeError("uvicorn test server did not start")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        app.dependency_overrides.clear()


def _build_isolated_repo(
    db_path: Path,
    *,
    latest_date: date = LATEST_DRAW_DATE,
) -> LotteryRepository:
    with sqlite3.connect(db_path) as connection:
        _create_draws_table(connection)
        _insert_fc3d_draws(connection, count=120, latest_date=latest_date)
        record_crawl_log(
            connection,
            provider="cwl",
            game_key="3d",
            source="task15-fixture",
            page_size=120,
            pages=1,
            wrote_count=120,
            status="success",
            error="",
            started_at=_utc_iso(datetime(2026, 7, 12, 7, 59, tzinfo=timezone.utc)),
            finished_at=_utc_iso(datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc)),
            duration_ms=1000,
        )
        connection.commit()

    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()
    repo.initialize_product_events_schema()
    return repo


def _create_draws_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE draws (
          game_key TEXT,
          game_name TEXT,
          issue TEXT,
          draw_date TEXT,
          week TEXT,
          red_numbers TEXT,
          blue_number TEXT,
          sales TEXT,
          pool_money TEXT,
          content TEXT,
          PRIMARY KEY(game_key, issue)
        )
        """
    )


def _insert_fc3d_draws(
    connection: sqlite3.Connection,
    *,
    count: int,
    latest_date: date,
) -> None:
    latest_sequence = int(LATEST_ISSUE[4:])
    for offset in range(count):
        draw_date = latest_date - timedelta(days=offset)
        issue = f"2026{latest_sequence - offset:03d}"
        digits = _deterministic_digits(offset)
        _insert_draw_row(connection, issue, draw_date.isoformat(), digits)


def _insert_draw(db_path: Path, issue: str, draw_date: str, digits: list[int]) -> None:
    with sqlite3.connect(db_path) as connection:
        _insert_draw_row(connection, issue, draw_date, tuple(digits))
        record_crawl_log(
            connection,
            provider="cwl",
            game_key="3d",
            source="task15-review-fixture",
            page_size=1,
            pages=1,
            wrote_count=1,
            status="success",
            error="",
            started_at=_utc_iso(datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)),
            finished_at=_utc_iso(datetime(2026, 7, 13, 12, 1, tzinfo=timezone.utc)),
            duration_ms=1000,
        )
        connection.commit()


def _insert_draw_row(
    connection: sqlite3.Connection,
    issue: str,
    draw_date: str,
    digits: tuple[int, int, int] | list[int],
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO draws (
            game_key, game_name, issue, draw_date, week, red_numbers,
            blue_number, sales, pool_money, content
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "3d",
            "福彩3D",
            issue,
            draw_date,
            "",
            ",".join(str(digit) for digit in digits),
            "",
            "",
            "",
            "",
        ),
    )


def _deterministic_digits(offset: int) -> tuple[int, int, int]:
    return (
        (offset * 7 + 1) % 10,
        (offset * 3 + 4) % 10,
        (offset * 9 + 2) % 10,
    )


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _install_client_id(page: Page, base_url: str, client_id: str) -> None:
    page.add_init_script(
        f"""
        (() => {{
          localStorage.setItem('lotteryLuck.clientId.v1', {json.dumps(client_id)});
        }})();
        """
    )
    page.goto(f"{base_url}/privacy.html")
    page.evaluate(
        "clientId => localStorage.setItem('lotteryLuck.clientId.v1', clientId)",
        client_id,
    )


def _complete_real_3d_prediction(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    page.wait_for_function("() => Boolean(window.FortuneMotion)")
    page.evaluate("() => { window.FortuneMotion.resolve = async () => {}; }")
    page.locator('button[data-game="3d"]').click()
    page.locator('input[name="name"]').fill("测试用户")
    page.locator('input[name="birth_date"]').fill("1990-01-01")
    page.locator('input[name="birth_place"]').fill("杭州")
    page.locator('input[name="current_city"]').fill("上海")
    page.locator('[data-select-name="birth_hour"] .custom-select-trigger').click()
    page.locator('[data-select-name="birth_hour"] .custom-select-option[data-value="辰"]').click()
    page.locator("#submitButton").click()
    page.wait_for_function(
        "() => !document.querySelector('#predictionActions').hidden",
        timeout=5000,
    )
    page.evaluate(
        """
        () => {
          const stage = document.querySelector("#ritualStage");
          if (!stage) return;
          stage.dataset.motionState = "idle";
          stage.setAttribute("aria-hidden", "true");
          stage.classList.add("is-dismissed");
        }
        """
    )


def _mock_prediction(self: Any, game_key: str, personal: Any, fortune_mode: str = "steady") -> dict[str, Any]:
    assert game_key == "3d"
    _ = self, personal, fortune_mode
    return {
        "game_key": "3d",
        "fortune_mode": "steady",
        "mode_profile": {"key": "steady", "label": "稳财号"},
        "best_draw_date": TARGET_DRAW_DATE,
        "luck_score": 66,
        "numbers": {"main": [1, 2, 3], "special": []},
        "history_basis": {"draw_count": 120, "hot_main": [1, 2, 3], "cold_main": [4, 5]},
        "personal_basis": {
            "ai_enabled": False,
            "ai_explanation": "测试特征",
            "ai_lucky_themes": [],
            "ai_confidence": 0,
        },
        "recent_draws": [],
        "disclaimer": "娱乐推荐，不构成投注建议",
        "ritual_summary": "测试财运合参",
        "fortune_hook": {
            "headline": "3d 测试财签",
            "subline": "测试本命财格",
            "tags": ["本命财格 测试"],
        },
        "interpretation_layers": {
            "short_hook": "测试短钩子",
            "long_reading": "测试长解读",
        },
        "metaphysics_profile": {
            "wealth_pattern": "测试财格",
            "reading": "测试解读",
            "selection_rule": "测试取号逻辑",
            "day_advice": "宜测试。",
        },
        "avoid_numbers": [{"number": 9, "reason": "避冲测试"}],
        "daily_fortune_sign": {
            "headline": "3d 今日财签",
            "direction": "正东",
            "lucky_hour": "巳时",
            "lucky_tails": [3, 8],
            "avoid_tails": [9],
            "tags": ["正东财位", "旺时 巳时", "尾 3、8 · 避 9"],
        },
        "ritual_steps": [
            {"key": "wealth_pattern", "label": "定本命财盘", "summary": "测试步骤"},
            {"key": "fortune_direction", "label": "定今日财局", "summary": "测试财位"},
            {"key": "fortune_eye", "label": "取财眼尾数", "summary": "测试财眼"},
            {"key": "avoid_clash", "label": "避冲煞号", "summary": "测试避冲"},
            {"key": "final_numbers", "label": "落财运号", "summary": "测试成号"},
        ],
        "master_ritual": {
            "opening": "测试起盘开场",
            "verdict": "测试起盘断语。",
            "tail_map": {
                "favorable": [{"tail": 3, "element_label": "火"}],
                "avoid": [{"tail": 9, "element_label": "水"}],
                "legend": "尾数1/2木，3/4火，5/6土，7/8金，9/0水。",
            },
            "steps": [
                {"key": "birth_chart", "label": "定命盘", "value": "测试命盘", "detail": "测试命盘细节"},
                {"key": "wealth_pattern", "label": "排本命财格", "value": "测试财格", "detail": "测试财格细节"},
                {"key": "daily_luck", "label": "定今日财局", "value": "测试财局", "detail": "测试财局细节"},
                {"key": "tail_digits", "label": "取喜用尾数", "value": "尾 3", "detail": "测试尾数细节"},
                {"key": "avoid_clash", "label": "避冲煞号", "value": "避 09", "detail": "测试避冲细节"},
                {"key": "final_numbers", "label": "落财运号", "value": "01 02 03", "detail": "测试落号细节"},
            ],
        },
        "credibility_chain": [],
        "number_reasons": {"main": [], "special": []},
        "fortune_report": {"closed_loop": [], "daily_calendar": []},
    }


def _build_public_freshness_for_retention_today(
    game: dict[str, Any],
    *,
    today: date | str | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_public_freshness(game, today=today or TODAY, logs=logs)


def _fingerprint_repo_sqlite() -> RepoFingerprint:
    path = DB_PATH
    if not path.exists():
        return RepoFingerprint(path=path, mtime_ns=None, digest=None)
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return RepoFingerprint(path=path, mtime_ns=stat.st_mtime_ns, digest=digest)


def _plan_payload(*, request_id: str) -> dict[str, Any]:
    return {
        "game_key": "3d",
        "target_issue": TARGET_ISSUE,
        "target_draw_date": TARGET_DRAW_DATE,
        "source_type": "filter",
        "request_id": request_id,
        "title": "专业筛选方案",
        "entries": [
            {
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "",
            }
        ],
        "condition_snapshot": {
            "mode": "pro",
            "analysis_window": 120,
            "conditions": {"sum_min": 6, "sum_max": 18},
            "metrics": {"sum": 6, "span": 2},
            "latest_data_issue": LATEST_ISSUE,
            "latest_data_date": LATEST_DRAW_DATE.isoformat(),
        },
    }


def _href_plan_id(href: str | None) -> str:
    assert href
    return href.rsplit("id=", 1)[1]


def _plan_by_id(repo: LotteryRepository, plan_id: str) -> dict[str, Any]:
    with sqlite3.connect(repo.db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT client_id FROM lottery_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
    assert row is not None
    plan = repo.get_plan(str(row["client_id"]), plan_id)
    assert plan is not None
    return plan


def _latest_plan_id_by_source(repo: LotteryRepository, source_type: str) -> str:
    with sqlite3.connect(repo.db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id
            FROM lottery_plans
            WHERE client_id = ? AND source_type = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (CLIENT_ID, source_type),
        ).fetchone()
    assert row is not None
    return str(row["id"])


def _events(repo: LotteryRepository) -> list[dict[str, Any]]:
    with sqlite3.connect(repo.db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT client_id, event_name, properties
            FROM product_events
            ORDER BY id ASC
            """
        ).fetchall()
    return [
        {
            "client_id": str(row["client_id"]),
            "event_name": str(row["event_name"]),
            "properties": json.loads(str(row["properties"] or "{}")),
        }
        for row in rows
    ]


def _event_names(repo: LotteryRepository) -> list[str]:
    return _event_names_from_rows(_events(repo))


def _event_names_from_rows(events: list[dict[str, Any]]) -> list[str]:
    return [str(event["event_name"]) for event in events]


def _assert_events_safe(events: list[dict[str, Any]]) -> None:
    serialized = json.dumps(
        [
            {
                "event_name": event["event_name"],
                "properties": event["properties"],
            }
            for event in events
        ],
        ensure_ascii=False,
    )
    for private_value in PRIVATE_VALUES:
        assert private_value not in serialized
    for event in events:
        assert set(event["properties"]) <= {
            "game_key",
            "source_type",
            "mode",
            "window",
            "entry_count",
            "candidate_count",
            "freshness_status",
            "review_status",
            "tool_key",
            "result_count",
        }
        assert event["client_id"] == CLIENT_ID
        assert "client_id" not in event["properties"]
