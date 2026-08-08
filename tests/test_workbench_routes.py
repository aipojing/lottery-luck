import importlib
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lottery_luck import workbench_3d
from lottery_luck.api import app, get_repository
from lottery_luck.repository import LotteryRepository


client = TestClient(app, raise_server_exceptions=False)


FRESH_DRAWS = [
    {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": "2026182",
        "draw_date": "2026-07-11",
        "week": "",
        "red_numbers": "6,6,2",
        "blue_number": "",
        "sales": "",
        "pool_money": "",
        "content": "",
    },
    {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": "2026181",
        "draw_date": "2026-07-10",
        "week": "",
        "red_numbers": "0,0,6",
        "blue_number": "",
        "sales": "",
        "pool_money": "",
        "content": "",
    },
    {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": "2026180",
        "draw_date": "2026-07-09",
        "week": "",
        "red_numbers": "1,2,3",
        "blue_number": "",
        "sales": "",
        "pool_money": "",
        "content": "",
    },
]


class FakeWorkbenchRepo:
    def __init__(
        self,
        *,
        status: str = "fresh",
        draws: list[dict[str, Any]] | None = None,
        logs: list[dict[str, Any]] | None = None,
        active_summary: dict[str, Any] | None = None,
        include_3d_metadata: bool = True,
    ):
        self.status = status
        self.draws = list(FRESH_DRAWS if draws is None else draws)
        self.logs = list(logs if logs is not None else _default_logs())
        self.active_summary = active_summary or {"count": 0, "latest_plan": None}
        self.include_3d_metadata = include_3d_metadata
        self.log_requests: list[tuple[list[str], int]] = []
        self.plan_clients: list[tuple[str, str | None, str | None]] = []
        self.draw_requests: list[tuple[str, int]] = []

    def list_games(self):
        latest_by_status = {
            "fresh": ("2026182", "2026-07-11", len(self.draws)),
            "attention": ("2026182", "2026-07-08", len(self.draws)),
            "stale": ("2026175", "2026-07-01", len(self.draws)),
            "empty": ("", "", 0),
        }
        issue, latest_date, draw_count = latest_by_status[self.status]
        games = [
            {
                "game_key": "ssq",
                "game_name": "双色球",
                "draw_count": 1,
                "earliest_date": "2026-07-12",
                "latest_date": "2026-07-12",
                "latest_issue": "2026080",
                "provider": "cwl",
            },
        ]
        if self.include_3d_metadata:
            games.insert(
                0,
                {
                    "game_key": "3d",
                    "game_name": "福彩3D",
                    "draw_count": draw_count,
                    "earliest_date": self.draws[-1]["draw_date"] if self.draws else "",
                    "latest_date": latest_date,
                    "latest_issue": issue,
                    "provider": "cwl",
                },
            )
        return games

    def recent_crawl_logs_by_game(self, game_keys, limit_per_game=20):
        self.log_requests.append((list(game_keys), limit_per_game))
        requested = {str(key).strip().lower() for key in game_keys}
        return [
            log
            for log in self.logs
            if str(log.get("game_key") or "").strip().lower() in requested
        ][:limit_per_game]

    def recent_crawl_logs(self, limit=20):  # pragma: no cover - guards wrong API use
        raise AssertionError("workbench routes must request logs by game")

    def recent_draws(self, game_key: str, limit: int = 100):
        assert game_key == "3d"
        self.draw_requests.append((game_key, limit))
        return self.draws[:limit]

    def active_plan_summary(
        self,
        client_id: str,
        *,
        game_key: str | None = None,
        target_issue: str | None = None,
    ):
        self.plan_clients.append((client_id, game_key, target_issue))
        return self.active_summary


class ExplodingRepo:
    def list_games(self):
        raise sqlite3.OperationalError("database is locked: /secret/path")


class InvalidDrawRepo(FakeWorkbenchRepo):
    def recent_draws(self, game_key: str, limit: int = 100):
        assert game_key == "3d"
        return [
            {
                "game_key": "3d",
                "game_name": "福彩3D",
                "issue": "2026182",
                "draw_date": "2026-07-11",
                "red_numbers": "not persisted 3d digits",
            }
        ]


class UnexpectedRepo(FakeWorkbenchRepo):
    def __init__(self, exc: Exception):
        super().__init__()
        self.exc = exc

    def list_games(self):
        raise self.exc


class CrossYearWorkbenchRepo(FakeWorkbenchRepo):
    def list_games(self):
        return [
            {
                "game_key": "3d",
                "game_name": "福彩3D",
                "draw_count": len(self.draws),
                "earliest_date": "2026-12-29",
                "latest_date": "2026-12-31",
                "latest_issue": "2026365",
                "provider": "cwl",
            }
        ]


def _default_logs() -> list[dict[str, Any]]:
    return [
        {
            "provider": "cwl",
            "game_key": "3d",
            "source": "api",
            "page_size": 100,
            "pages": 1,
            "wrote_count": 3,
            "status": "success",
            "error": "",
            "started_at": "2026-07-12T01:00:00+00:00",
            "finished_at": "2026-07-12T01:00:01+00:00",
            "duration_ms": 1000,
        }
    ]


def _override_repo(repo: Any) -> Any:
    app.dependency_overrides[get_repository] = lambda: repo
    return repo


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_fresh_summary_returns_stats_public_freshness_actions_and_client_plan_scope():
    latest_plan = {
        "id": "plan-latest",
        "client_id": "client-a",
        "status": "saved",
        "updated_at": "2026-07-12T08:00:00+00:00",
        "entries": [{"position": 0, "main_numbers": [6, 6, 2]}],
    }
    repo = _override_repo(
        FakeWorkbenchRepo(
            active_summary={"count": 2, "latest_plan": latest_plan},
        )
    )

    response = client.get(
        "/api/workbench/3d/summary?window=30&today=2026-07-12",
        headers={"X-Lottery-Client-Id": " client-a "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["window"] == 30
    assert payload["sample_size"] == 3
    assert payload["latest_draw"]["number_text"] == "662"
    assert payload["position_stats"]["positions"]["0"]["digits"]["6"]["frequency"] == 1
    assert payload["freshness"] == {
        "status": "fresh",
        "latest_issue": "2026182",
        "latest_date": "2026-07-11",
        "staleness_days": 1,
        "can_claim_current": True,
        "message": "数据已更新至第2026182期",
        "last_successful_update": "2026-07-12T01:00:01+00:00",
        "sync_error": "",
    }
    assert payload["actions"]["can_filter_current"] is True
    assert payload["actions"]["can_save_current"] is True
    assert payload["actions"]["can_read_history"] is True
    assert payload["current_target"] == {
        "target_issue": "2026183",
        "target_draw_date": "2026-07-12",
    }
    assert payload["recent_draws"] == [
        {
            "issue": "2026182",
            "draw_date": "2026-07-11",
            "number_text": "662",
            "numbers": [6, 6, 2],
        },
        {
            "issue": "2026181",
            "draw_date": "2026-07-10",
            "number_text": "006",
            "numbers": [0, 0, 6],
        },
        {
            "issue": "2026180",
            "draw_date": "2026-07-09",
            "number_text": "123",
            "numbers": [1, 2, 3],
        },
    ]
    assert payload["active_plan_count"] == 2
    assert payload["latest_plan"] == latest_plan
    assert repo.plan_clients == [("client-a", "3d", "2026183")]
    assert repo.log_requests == [(["3d"], 20)]


def test_stale_summary_is_read_only_but_keeps_history_and_plan_data():
    repo = _override_repo(
        FakeWorkbenchRepo(
            status="stale",
            active_summary={"count": 1, "latest_plan": {"id": "plan-readonly"}},
        )
    )

    response = client.get(
        "/api/workbench/3d/summary?today=2026-07-12",
        headers={"X-Lottery-Client-Id": "client-a"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["freshness"]["status"] == "stale"
    assert payload["sample_size"] == 3
    assert payload["active_plan_count"] == 1
    assert payload["latest_plan"] == {"id": "plan-readonly"}
    assert payload["current_target"] == {
        "target_issue": "2026176",
        "target_draw_date": "2026-07-02",
    }
    assert payload["actions"]["can_filter_current"] is False
    assert payload["actions"]["can_save_current"] is False
    assert payload["actions"]["can_read_history"] is True


def test_empty_summary_returns_complete_zero_matrix_and_read_only_actions():
    _override_repo(FakeWorkbenchRepo(status="empty", draws=[]))

    response = client.get("/api/workbench/3d/summary?today=2026-07-12")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_size"] == 0
    assert payload["latest_draw"] is None
    assert payload["current_target"] is None
    assert payload["recent_draws"] == []
    assert payload["freshness"]["status"] == "empty"
    assert payload["actions"] == {
        "can_filter_current": False,
        "can_save_current": False,
        "can_read_history": False,
    }
    assert set(payload["position_stats"]["positions"]) == {"0", "1", "2"}
    for position in ("0", "1", "2"):
        digits = payload["position_stats"]["positions"][position]["digits"]
        assert set(digits) == {str(digit) for digit in range(10)}
        assert all(cell["frequency"] == 0 for cell in digits.values())


def test_summary_without_current_target_does_not_query_or_claim_current_plans():
    repo = _override_repo(
        FakeWorkbenchRepo(
            status="empty",
            draws=[],
            active_summary={"count": 3, "latest_plan": {"id": "old-active"}},
        )
    )

    response = client.get(
        "/api/workbench/3d/summary?today=2026-07-12",
        headers={"X-Lottery-Client-Id": "client-a"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_target"] is None
    assert payload["active_plan_count"] == 0
    assert payload["latest_plan"] is None
    assert repo.plan_clients == []


@pytest.mark.parametrize(
    ("draws", "expected_sample_size", "can_read_history"),
    [
        (FRESH_DRAWS, 3, True),
        ([], 0, False),
    ],
)
def test_summary_degrades_when_3d_metadata_is_missing(
    draws,
    expected_sample_size,
    can_read_history,
):
    _override_repo(FakeWorkbenchRepo(draws=draws, include_3d_metadata=False))

    response = client.get("/api/workbench/3d/summary?today=2026-07-12")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_size"] == expected_sample_size
    assert payload["freshness"]["status"] == "empty"
    assert payload["freshness"]["latest_issue"] == ""
    assert payload["freshness"]["latest_date"] == ""
    assert payload["freshness"]["can_claim_current"] is False
    assert payload["current_target"] is None
    assert payload["actions"] == {
        "can_filter_current": False,
        "can_save_current": False,
        "can_read_history": can_read_history,
    }


def test_summary_limits_recent_draws_to_10_and_resolves_cross_year_target():
    draws = [
        {
            "game_key": "3d",
            "game_name": "福彩3D",
            "issue": f"2026{365 - index:03d}",
            "draw_date": f"2026-12-{31 - index:02d}",
            "week": "",
            "red_numbers": f"{index % 10},{(index + 1) % 10},{(index + 2) % 10}",
            "blue_number": "",
            "sales": "",
            "pool_money": "",
            "content": "",
        }
        for index in range(12)
    ]
    _override_repo(CrossYearWorkbenchRepo(draws=draws))

    response = client.get("/api/workbench/3d/summary?window=120&today=2027-01-01")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_target"] == {
        "target_issue": "2027001",
        "target_draw_date": "2027-01-01",
    }
    assert len(payload["recent_draws"]) == 10
    assert payload["recent_draws"][0] == {
        "issue": "2026365",
        "draw_date": "2026-12-31",
        "number_text": "012",
        "numbers": [0, 1, 2],
    }


@pytest.mark.parametrize(
    "path",
    [
        "/api/workbench/3d/summary?window=90&today=2026-07-12",
        "/api/workbench/3d/summary?window=30.0&today=2026-07-12",
        "/api/workbench/3d/summary?today=",
        "/api/workbench/3d/summary?today=2026-7-12",
        "/api/workbench/3d/summary?today=2026-W29",
        "/api/workbench/3d/summary?today=2026-07-12T00:00:00",
        "/api/workbench/3d/summary?today=%202026-07-12%20",
        "/api/workbench/3d/summary?today=2026-02-30",
    ],
)
def test_summary_rejects_invalid_window_and_today(path):
    _override_repo(FakeWorkbenchRepo())

    response = client.get(path)

    assert response.status_code == 422


def test_number_query_accepts_string_and_digit_list_with_identical_results():
    _override_repo(FakeWorkbenchRepo())

    text_response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "662", "window": 120},
    )
    list_response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": [6, 6, 2], "window": 120},
    )

    assert text_response.status_code == 200
    assert list_response.status_code == 200
    assert text_response.json() == list_response.json()
    payload = text_response.json()
    assert payload["number_text"] == "662"
    assert payload["history"]["exact"]["count"] == 1
    assert payload["freshness"]["status"] == "fresh"
    assert payload["actions"]["can_filter_current"] is True


@pytest.mark.parametrize("window", [30, 60, 120])
def test_number_query_reports_the_window_and_sample_its_position_stats_came_from(window):
    repo = FakeWorkbenchRepo()
    _override_repo(repo)

    response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "662", "window": window},
    )

    assert response.status_code == 200
    payload = response.json()
    # The route only ever fetched `window` draws, so the payload may claim no other window.
    assert repo.draw_requests[-1] == ("3d", window)
    assert payload["position_stats_window"] == window
    # And the sample it reports is the number of draws the stats were really computed from.
    assert payload["position_stats_sample_size"] == len(FRESH_DRAWS)
    assert payload["position_digits"]["0"]["frequency"] <= payload["position_stats_sample_size"]
    assert payload["position_digits"]["0"]["max_omission"] <= payload["position_stats_sample_size"]


def test_number_query_preserves_leading_zeroes():
    _override_repo(FakeWorkbenchRepo())

    response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "006", "window": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["number_text"] == "006"
    assert payload["numbers"] == [0, 0, 6]
    assert payload["history"]["exact"]["count"] == 1


@pytest.mark.parametrize(
    "body",
    [
        {"number": "66", "window": 120},
        {"number": "６６２", "window": 120},
        {"number": [6, True, 2], "window": 120},
        {"number": [6, "6", 2], "window": 120},
        {"number": [6, 6, 10], "window": 120},
        {"number": "662", "window": 120, "extra": "nope"},
        {"number": "662", "window": 90},
    ],
)
def test_number_query_rejects_invalid_number_window_and_extra_fields(body):
    _override_repo(FakeWorkbenchRepo())

    response = client.post("/api/3d/number-query?today=2026-07-12", json=body)

    assert response.status_code == 422


def test_stale_number_query_returns_history_but_disables_current_actions():
    _override_repo(FakeWorkbenchRepo(status="stale"))

    response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "662", "window": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["history"]["exact"]["count"] == 1
    assert payload["freshness"]["status"] == "stale"
    assert payload["actions"]["can_filter_current"] is False
    assert payload["actions"]["can_save_current"] is False
    assert payload["actions"]["can_read_history"] is True


def test_empty_number_query_returns_empty_history_and_no_history_action():
    _override_repo(FakeWorkbenchRepo(status="empty", draws=[]))

    response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "662", "window": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["history"]["exact"] == {"count": 0, "latest": None}
    assert payload["history"]["group"] == {"count": 0, "latest": None}
    assert payload["freshness"]["status"] == "empty"
    assert payload["actions"] == {
        "can_filter_current": False,
        "can_save_current": False,
        "can_read_history": False,
    }


@pytest.mark.parametrize(
    ("draws", "exact_count", "can_read_history"),
    [
        (FRESH_DRAWS, 1, True),
        ([], 0, False),
    ],
)
def test_number_query_degrades_when_3d_metadata_is_missing(
    draws,
    exact_count,
    can_read_history,
):
    _override_repo(FakeWorkbenchRepo(draws=draws, include_3d_metadata=False))

    response = client.post(
        "/api/3d/number-query?today=2026-07-12",
        json={"number": "662", "window": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["history"]["exact"]["count"] == exact_count
    assert payload["freshness"]["status"] == "empty"
    assert payload["freshness"]["can_claim_current"] is False
    assert payload["actions"] == {
        "can_filter_current": False,
        "can_save_current": False,
        "can_read_history": can_read_history,
    }


@pytest.mark.parametrize("status", ["fresh", "attention"])
def test_filter_returns_candidates_when_public_freshness_allows_current_actions(status):
    _override_repo(FakeWorkbenchRepo(status=status))

    response = client.post(
        "/api/3d/filter?today=2026-07-12",
        json={"filters": {"max_results": 5}, "window": 30},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1000
    assert len(payload["candidates"]) == 5
    assert payload["candidates"][0]["number_text"] == "000"
    assert payload["filters"]["max_results"] == 5
    assert payload["freshness"]["status"] == status
    assert payload["actions"]["can_filter_current"] is True
    assert payload["actions"]["can_save_current"] is True


def test_filter_allows_empty_filters_with_default_limit():
    _override_repo(FakeWorkbenchRepo())

    response = client.post(
        "/api/3d/filter?today=2026-07-12",
        json={"filters": {}, "window": 30},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1000
    assert len(payload["candidates"]) == 100


@pytest.mark.parametrize("draws", [FRESH_DRAWS, []])
def test_filter_rejects_when_3d_metadata_is_missing_before_filtering(monkeypatch, draws):
    calls = []

    def spy_filter_candidates(filters):
        calls.append(filters)
        raise AssertionError("filter_candidates must not be called")

    workbench_routes = importlib.import_module("lottery_luck.workbench_routes")
    monkeypatch.setattr(workbench_routes, "filter_candidates", spy_filter_candidates)
    _override_repo(FakeWorkbenchRepo(draws=draws, include_3d_metadata=False))

    response = client.post(
        "/api/3d/filter?today=2026-07-12",
        json={"filters": {"max_results": 5}, "window": 30},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "current data is not available"
    assert calls == []


@pytest.mark.parametrize("status", ["stale", "empty"])
def test_filter_rejects_stale_and_empty_data_before_filtering(monkeypatch, status):
    calls = []

    def spy_filter_candidates(filters):
        calls.append(filters)
        raise AssertionError("filter_candidates must not be called")

    monkeypatch.setattr(workbench_3d, "filter_candidates", spy_filter_candidates)
    try:
        workbench_routes = importlib.import_module("lottery_luck.workbench_routes")
    except ModuleNotFoundError:
        workbench_routes = None
    if workbench_routes is not None:
        monkeypatch.setattr(
            workbench_routes,
            "filter_candidates",
            spy_filter_candidates,
            raising=False,
        )
    _override_repo(FakeWorkbenchRepo(status=status, draws=[] if status == "empty" else None))

    response = client.post(
        "/api/3d/filter?today=2026-07-12",
        json={"filters": {"max_results": 0}, "window": 30},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "current data is not available"
    assert calls == []


def test_filter_maps_invalid_filter_to_generic_422_without_leaking_detail():
    _override_repo(FakeWorkbenchRepo())

    response = client.post(
        "/api/3d/filter?today=2026-07-12",
        json={"filters": {"unknown": "/secret/path"}, "window": 30},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid 3d filter"
    assert "secret" not in response.text


def test_freshness_uses_only_3d_logs_and_sanitizes_sync_errors():
    repo = _override_repo(
        FakeWorkbenchRepo(
            logs=[
                {
                    "game_key": "ssq",
                    "status": "failed",
                    "error": "other game failure",
                    "finished_at": "2026-07-12T07:00:00+00:00",
                },
                {
                    "game_key": "3d",
                    "status": "failed",
                    "error": "timeout\nretry exhausted",
                    "finished_at": "2026-07-12T06:00:00+00:00",
                },
                {
                    "game_key": "3d",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T05:00:00+00:00",
                },
            ],
        )
    )

    response = client.get("/api/workbench/3d/summary?today=2026-07-12")

    assert response.status_code == 200
    freshness = response.json()["freshness"]
    assert freshness["sync_error"] == "timeout retry exhausted"
    assert freshness["last_successful_update"] == "2026-07-12T05:00:00+00:00"
    assert "other game" not in response.text
    assert repo.log_requests == [(["3d"], 20)]


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/workbench/3d/summary?today=2026-07-12", None),
        ("post", "/api/3d/number-query?today=2026-07-12", {"number": "662"}),
        ("post", "/api/3d/filter?today=2026-07-12", {"filters": {}, "window": 30}),
    ],
)
def test_workbench_routes_map_repository_errors_to_503_without_leaking_details(
    method,
    path,
    json_body,
):
    _override_repo(ExplodingRepo())

    if json_body is None:
        response = getattr(client, method)(path)
    else:
        response = getattr(client, method)(path, json=json_body)

    assert response.status_code == 503
    assert response.json()["detail"] == "workbench service is unavailable"
    assert "secret" not in response.text


def test_summary_client_header_is_isolated_and_blank_header_does_not_query_plans():
    repo = _override_repo(
        FakeWorkbenchRepo(
            active_summary={"count": 7, "latest_plan": {"id": "plan-client-b"}},
        )
    )

    other_response = client.get(
        "/api/workbench/3d/summary?today=2026-07-12",
        headers={"X-Lottery-Client-Id": " client-b "},
    )
    blank_response = client.get(
        "/api/workbench/3d/summary?today=2026-07-12",
        headers={"X-Lottery-Client-Id": "   "},
    )

    assert other_response.status_code == 200
    assert other_response.json()["active_plan_count"] == 7
    assert other_response.json()["latest_plan"] == {"id": "plan-client-b"}
    assert blank_response.status_code == 200
    assert blank_response.json()["active_plan_count"] == 0
    assert blank_response.json()["latest_plan"] is None
    assert repo.plan_clients == [("client-b", "3d", "2026183")]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/3d/number-query?today=2026-07-12",
            {"number": "662", "window": 120, "today": "2026-07-11"},
        ),
        (
            "/api/3d/filter?today=2026-07-12",
            {"filters": {}, "window": 30, "today": "2026-07-11"},
        ),
    ],
)
def test_today_cannot_be_forged_in_post_bodies(path, body):
    _override_repo(FakeWorkbenchRepo(status="stale"))

    response = client.post(path, json=body)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "get",
            "/api/workbench/3d/summary?today=2026-07-12&today=2026-07-11",
            None,
        ),
        (
            "get",
            "/api/workbench/3d/summary?today=2026-07-12&today=2026-07-12",
            None,
        ),
        (
            "post",
            "/api/3d/number-query?today=2026-07-12&today=2026-07-11",
            {"number": "662", "window": 120},
        ),
        (
            "post",
            "/api/3d/number-query?today=2026-07-12&today=2026-07-12",
            {"number": "662", "window": 120},
        ),
        (
            "post",
            "/api/3d/filter?today=2026-07-12&today=2026-07-11",
            {"filters": {}, "window": 30},
        ),
        (
            "post",
            "/api/3d/filter?today=2026-07-12&today=2026-07-12",
            {"filters": {}, "window": 30},
        ),
    ],
)
def test_workbench_routes_reject_duplicate_today_query_values(method, path, body):
    _override_repo(FakeWorkbenchRepo())

    if body is None:
        response = getattr(client, method)(path)
    else:
        response = getattr(client, method)(path, json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid today"


def test_openapi_documents_today_query_for_all_workbench_routes():
    app.openapi_schema = None

    schema = app.openapi()

    for path, method in [
        ("/api/workbench/3d/summary", "get"),
        ("/api/3d/number-query", "post"),
        ("/api/3d/filter", "post"),
    ]:
        parameters = schema["paths"][path][method]["parameters"]
        today = next(parameter for parameter in parameters if parameter["name"] == "today")
        assert today["in"] == "query"
        assert today["required"] is False
        assert _schema_contains_pattern(today["schema"], r"^\d{4}-\d{2}-\d{2}$")


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/workbench/3d/summary?today=2026-07-12", None),
        ("post", "/api/3d/number-query?today=2026-07-12", {"number": "662"}),
    ],
)
def test_invalid_persisted_draws_return_503_and_log_data_invalid(
    caplog,
    method,
    path,
    json_body,
):
    _override_repo(InvalidDrawRepo())

    with caplog.at_level(logging.WARNING, logger="lottery_luck.workbench_routes"):
        if json_body is None:
            response = getattr(client, method)(path)
        else:
            response = getattr(client, method)(path, json=json_body)

    assert response.status_code == 503
    assert response.json()["detail"] == "workbench service is unavailable"
    assert "data invalid" in caplog.text


@pytest.mark.parametrize(
    "exc",
    [
        KeyError("missing internal key"),
        TypeError("bad internal type"),
        RuntimeError("unexpected branch"),
    ],
)
def test_unexpected_workbench_errors_return_500_and_are_logged(caplog, exc):
    _override_repo(UnexpectedRepo(exc))

    with caplog.at_level(logging.ERROR, logger="lottery_luck.workbench_routes"):
        response = client.get("/api/workbench/3d/summary?today=2026-07-12")

    assert response.status_code == 500
    assert "unexpected error" in caplog.text


def test_active_plan_summary_repository_counts_only_current_3d_target_and_hydrates_latest(tmp_path: Path):
    repo = _plan_repo(tmp_path)
    saved = repo.create_plan("client-a", _plan_payload(request_id="saved", title="saved"))
    draft = repo.create_plan("client-a", _plan_payload(request_id="draft", title="draft"))
    repo.update_plan("client-a", draft["id"], {"status": "draft"})
    repo.create_plan("client-a", _plan_payload(request_id="old-active", title="old", target_issue="2026199"))
    repo.create_plan("client-a", _plan_payload(request_id="reviewed", title="reviewed"))
    reviewed = repo.list_plans("client-a", limit=10)[0]
    repo.update_plan("client-a", reviewed["id"], {"status": "expired"})
    repo.create_plan("client-b", _plan_payload(request_id="other", title="other"))

    summary = repo.active_plan_summary("client-a", game_key="3d", target_issue="2026200")

    assert summary["count"] == 2
    assert summary["latest_plan"]["id"] == draft["id"]
    assert summary["latest_plan"]["entries"] == draft["entries"]
    assert summary["latest_plan"]["condition_snapshot"] == draft["condition_snapshot"]
    assert summary["latest_plan"]["client_id"] == "client-a"
    assert saved["id"] != draft["id"]


def test_active_plan_summary_repository_returns_empty_without_target_issue(tmp_path: Path):
    repo = _plan_repo(tmp_path)
    repo.create_plan("client-a", _plan_payload(request_id="active", title="active"))

    summary = repo.active_plan_summary("client-a", game_key="3d", target_issue=None)

    assert summary == {"count": 0, "latest_plan": None}


def test_workbench_router_is_registered_before_static_mount():
    static_index = next(
        index for index, route in enumerate(app.routes) if getattr(route, "name", "") == "web"
    )
    paths_by_top_level_index: dict[str, int] = {}
    for index, route in enumerate(app.routes):
        route_path = getattr(route, "path", "")
        if route_path:
            paths_by_top_level_index[route_path] = index
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            for child in original_router.routes:
                paths_by_top_level_index[getattr(child, "path", "")] = index
    workbench_indices = [
        paths_by_top_level_index["/api/workbench/3d/summary"],
        paths_by_top_level_index["/api/3d/number-query"],
        paths_by_top_level_index["/api/3d/filter"],
    ]

    assert max(workbench_indices) < static_index


def test_existing_3d_analysis_route_still_returns_payload():
    response = client.get("/api/analysis/3d?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == "3d"
    assert payload["window"] == 30


def test_trends_route_keeps_history_readable_when_current_data_is_stale():
    _override_repo(FakeWorkbenchRepo(status="stale"))

    response = client.get("/api/3d/trends?window=30&today=2026-07-13")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"]
    assert payload["freshness"]["status"] == "stale"
    assert payload["actions"]["can_read_history"] is True
    assert payload["actions"]["can_save_current"] is False


@pytest.mark.parametrize("window", ["0", "29", "31", "abc", "30.0"])
def test_trends_route_rejects_invalid_window(window):
    _override_repo(FakeWorkbenchRepo())

    response = client.get(f"/api/3d/trends?window={window}&today=2026-07-13")

    assert response.status_code == 422


def test_trends_route_returns_empty_rows_when_no_history():
    _override_repo(FakeWorkbenchRepo(status="empty", draws=[]))

    response = client.get("/api/3d/trends?window=30&today=2026-07-13")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == []
    assert payload["sample_size"] == 0
    assert payload["freshness"]["status"] == "empty"
    assert payload["actions"]["can_read_history"] is False
    assert payload["actions"]["can_save_current"] is False


def test_trends_route_maps_repository_errors_to_503_without_leaking_details():
    _override_repo(ExplodingRepo())

    response = client.get("/api/3d/trends?window=30&today=2026-07-13")

    assert response.status_code == 503
    assert response.json()["detail"] == "workbench service is unavailable"
    assert "secret" not in response.text


def test_openapi_documents_trends_window_query_as_30_60_120_only():
    app.openapi_schema = None

    schema = app.openapi()

    parameters = schema["paths"]["/api/3d/trends"]["get"]["parameters"]
    window = next(parameter for parameter in parameters if parameter["name"] == "window")
    assert window["in"] == "query"
    assert _schema_contains_pattern(window["schema"], r"^(30|60|120)$")


def _plan_repo(tmp_path: Path) -> LotteryRepository:
    db_path = tmp_path / "plans.sqlite"
    with sqlite3.connect(db_path) as connection:
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
    repository = LotteryRepository(db_path)
    repository.initialize_plan_schema()
    return repository


def _schema_contains_pattern(schema: dict[str, Any], pattern: str) -> bool:
    if schema.get("pattern") == pattern:
        return True
    return any(
        _schema_contains_pattern(item, pattern)
        for item in schema.get("anyOf", []) + schema.get("oneOf", [])
        if isinstance(item, dict)
    )


def _plan_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "game_key": "3d",
        "target_issue": "2026200",
        "target_draw_date": "2026-07-29",
        "source_type": "manual",
        "request_id": "repo-plan",
        "title": "repo plan",
        "entries": [
            {
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "first",
            }
        ],
        "condition_snapshot": {
            "mode": "pro",
            "analysis_window": 60,
            "conditions_json": {"sum_min": 6},
            "metrics_json": {"sum": 6},
            "latest_data_issue": "2026182",
            "latest_data_date": "2026-07-11",
        },
    }
    payload.update(overrides)
    return payload
