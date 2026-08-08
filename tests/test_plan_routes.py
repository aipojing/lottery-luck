import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lottery_luck import plans as plan_store
from lottery_luck.api import app, get_repository
from lottery_luck.repository import LotteryRepository


client = TestClient(app)
CLIENT_A = {"X-Lottery-Client-Id": " client-a "}
CLIENT_B = {"X-Lottery-Client-Id": "client-b"}


@pytest.fixture()
def repo(tmp_path: Path):
    db_path = tmp_path / "plan-routes.sqlite"
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
    app.dependency_overrides[get_repository] = lambda: repository
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


def _insert_draw(
    repo: LotteryRepository,
    *,
    issue: str,
    draw_date: str,
    red_numbers: str = "1,2,3",
    game_key: str = "3d",
):
    with sqlite3.connect(repo.db_path) as connection:
        connection.execute(
            """
            INSERT INTO draws (
                game_key, game_name, issue, draw_date, week, red_numbers,
                blue_number, sales, pool_money, content
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_key,
                "FC3D" if game_key == "3d" else "Other",
                issue,
                draw_date,
                "",
                red_numbers,
                "",
                "",
                "",
                "",
            ),
        )


def _delete_draw(repo: LotteryRepository, *, issue: str, game_key: str = "3d"):
    with sqlite3.connect(repo.db_path) as connection:
        connection.execute(
            "DELETE FROM draws WHERE game_key = ? AND issue = ?",
            (game_key, issue),
        )


def _plan_review_count(repo: LotteryRepository, plan_id: str) -> int:
    with sqlite3.connect(repo.db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM plan_reviews WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
    return int(row[0])


def _plan_payload(**overrides):
    payload = {
        "game_key": "3d",
        "target_issue": "2026156",
        "target_draw_date": "2026-06-16",
        "source_type": "manual",
        "request_id": "req-plan-1",
        "title": "steady plan",
        "entries": [
            {
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "first",
            },
            {
                "position": 1,
                "main_numbers": [2, 2, 1],
                "special_numbers": [],
                "note": "",
            },
        ],
        "condition_snapshot": {
            "mode": "pro",
            "analysis_window": 60,
            "conditions": {"group_type": "组三", "sum_min": 4, "position_0": 2},
            "metrics": {"span": 1, "sum": 5},
            "latest_data_issue": "2026155",
            "latest_data_date": "2026-06-15",
        },
    }
    payload.update(overrides)
    return payload


def _create_plan(headers=CLIENT_A, **overrides):
    response = client.post("/api/plans", headers=headers, json=_plan_payload(**overrides))
    assert response.status_code == 201
    return response.json()["plan"]


def test_plan_routes_require_client_header(repo):
    response = client.post("/api/plans", json=_plan_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Lottery-Client-Id is required"


def test_plan_routes_map_domain_value_errors_to_generic_422_without_leak():
    class BrokenRepo:
        def list_plans(self, client_id):
            raise ValueError("invalid plan: /secret/path")

    app.dependency_overrides[get_repository] = lambda: BrokenRepo()
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/plans",
            headers=CLIENT_A,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid plan"
    assert "secret" not in response.text


def test_create_plan_returns_201_and_maps_api_fields_to_domain_payload(repo):
    response = client.post("/api/plans", headers=CLIENT_A, json=_plan_payload())

    assert response.status_code == 201
    plan = response.json()["plan"]
    assert plan["client_id"] == "client-a"
    assert plan["game_key"] == "3d"
    assert plan["target_issue"] == "2026156"
    assert plan["target_draw_date"] == "2026-06-16"
    assert plan["source_type"] == "manual"
    assert plan["request_id"] == "req-plan-1"
    assert plan["entries"][0]["position"] == 0
    assert plan["entries"][0]["main_numbers"] == [1, 2, 3]
    assert plan["entries"][0]["special_numbers"] == []
    assert plan["entries"][0]["note"] == "first"
    snapshot = plan["condition_snapshot"]
    assert snapshot["analysis_window"] == 60
    assert snapshot["conditions_json"] == {
        "group_type": "组三",
        "sum_min": 4,
        "position_0": 2,
    }
    assert snapshot["metrics_json"] == {"span": 1, "sum": 5}
    assert snapshot["latest_data_date"] == "2026-06-15"


def test_create_plan_is_idempotent_for_same_client_and_nonempty_request_id(repo):
    first = _create_plan(request_id="same-request")
    retry = _create_plan(request_id="same-request")
    other_client = _create_plan(headers=CLIENT_B, request_id="same-request")

    assert retry["id"] == first["id"]
    assert other_client["id"] != first["id"]


def test_create_plan_retries_existing_request_before_drawn_target_rejection(repo):
    first = _create_plan(request_id="draw-arrived")
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16")

    retry = client.post(
        "/api/plans",
        headers=CLIENT_A,
        json=_plan_payload(request_id="draw-arrived"),
    )
    other_client = client.post(
        "/api/plans",
        headers=CLIENT_B,
        json=_plan_payload(request_id="draw-arrived"),
    )

    assert retry.status_code == 201
    assert retry.json()["plan"]["id"] == first["id"]
    assert other_client.status_code == 409
    assert other_client.json()["detail"] == "target issue is already drawn"


def test_create_plan_request_id_conflicting_payload_returns_409(repo):
    first = _create_plan(request_id="conflict-request")

    response = client.post(
        "/api/plans",
        headers=CLIENT_A,
        json=_plan_payload(request_id="conflict-request", title="changed title"),
    )
    other_client = _create_plan(
        headers=CLIENT_B,
        request_id="conflict-request",
        title="changed title",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "request id conflicts with an existing plan"
    assert other_client["id"] != first["id"]


def test_create_plan_rejects_target_issue_that_is_already_drawn(repo):
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16")

    response = client.post("/api/plans", headers=CLIENT_A, json=_plan_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "target issue is already drawn"


def test_list_plans_is_scoped_to_current_client(repo):
    mine = _create_plan(headers=CLIENT_A, request_id="mine", title="mine")
    _create_plan(headers=CLIENT_B, request_id="theirs", title="theirs")

    response = client.get("/api/plans", headers=CLIENT_A)

    assert response.status_code == 200
    assert [plan["id"] for plan in response.json()["plans"]] == [mine["id"]]


def test_get_patch_and_delete_cross_client_return_404(repo):
    mine = _create_plan(headers=CLIENT_A)

    get_response = client.get(f"/api/plans/{mine['id']}", headers=CLIENT_B)
    patch_response = client.patch(
        f"/api/plans/{mine['id']}",
        headers=CLIENT_B,
        json={"title": "cross-client"},
    )
    delete_response = client.delete(f"/api/plans/{mine['id']}", headers=CLIENT_B)
    owner_response = client.get(f"/api/plans/{mine['id']}", headers=CLIENT_A)

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert owner_response.status_code == 200
    assert owner_response.json()["plan"]["title"] == "steady plan"


@pytest.mark.parametrize(
    "patch_body",
    [
        {},
        {"target_issue": "2026999"},
        {"unexpected": "field"},
        {"entries": [{"position": "0", "main_numbers": [1, 2, 3]}]},
        {"entries": [{"position": 0, "main_numbers": [1, 2, True]}]},
    ],
)
def test_patch_rejects_extra_immutable_empty_and_non_strict_integer_payloads(
    repo,
    patch_body,
):
    mine = _create_plan(headers=CLIENT_A)

    response = client.patch(
        f"/api/plans/{mine['id']}",
        headers=CLIENT_A,
        json=patch_body,
    )

    assert response.status_code == 422


def test_position_is_persisted_sorted_patched_and_carried_forward(repo):
    plan = _create_plan(
        headers=CLIENT_A,
        request_id="position-source",
        entries=[
            {"position": 49, "main_numbers": [9, 9, 9], "special_numbers": []},
            {"position": 2, "main_numbers": [2, 2, 1], "special_numbers": []},
        ],
    )

    assert [entry["position"] for entry in plan["entries"]] == [2, 49]
    assert [entry["main_numbers"] for entry in plan["entries"]] == [[2, 2, 1], [9, 9, 9]]

    patched = client.patch(
        f"/api/plans/{plan['id']}",
        headers=CLIENT_A,
        json={
            "entries": [
                {"position": 10, "main_numbers": [1, 0, 0], "special_numbers": []},
                {"position": 3, "main_numbers": [3, 3, 3], "special_numbers": []},
            ],
        },
    )
    assert patched.status_code == 200
    patched_plan = patched.json()["plan"]
    assert [entry["position"] for entry in patched_plan["entries"]] == [3, 10]
    assert [entry["main_numbers"] for entry in patched_plan["entries"]] == [
        [3, 3, 3],
        [1, 0, 0],
    ]

    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="3,3,3")
    carried = client.post(
        f"/api/plans/{plan['id']}/carry-forward",
        headers=CLIENT_A,
        json={"request_id": "position-carry"},
    )

    assert carried.status_code == 200
    assert [entry["position"] for entry in carried.json()["plan"]["entries"]] == [3, 10]


def test_duplicate_entry_position_is_rejected_on_create_and_patch(repo):
    create_response = client.post(
        "/api/plans",
        headers=CLIENT_A,
        json=_plan_payload(
            request_id="duplicate-position",
            entries=[
                {"position": 4, "main_numbers": [1, 2, 3], "special_numbers": []},
                {"position": 4, "main_numbers": [3, 2, 1], "special_numbers": []},
            ],
        ),
    )
    plan = _create_plan(headers=CLIENT_A, request_id="patch-position-source")
    patch_response = client.patch(
        f"/api/plans/{plan['id']}",
        headers=CLIENT_A,
        json={
            "entries": [
                {"position": 8, "main_numbers": [1, 2, 3], "special_numbers": []},
                {"position": 8, "main_numbers": [3, 2, 1], "special_numbers": []},
            ],
        },
    )

    assert create_response.status_code == 422
    assert create_response.json()["detail"] == "invalid plan"
    assert patch_response.status_code == 422
    assert patch_response.json()["detail"] == "invalid plan"


def test_create_plan_allows_omitted_entry_positions_and_empty_snapshot_maps(repo):
    payload = _plan_payload(
        request_id="defaults",
        entries=[
            {"main_numbers": [1, 2, 3], "special_numbers": []},
            {"main_numbers": [4, 5, 6], "special_numbers": []},
            {"position": 4, "main_numbers": [7, 8, 9], "special_numbers": []},
        ],
    )
    payload["condition_snapshot"] = {
        "mode": "simple",
        "analysis_window": 30,
        "latest_data_issue": "2026155",
        "latest_data_date": "2026-06-15",
    }

    response = client.post("/api/plans", headers=CLIENT_A, json=payload)

    assert response.status_code == 201
    plan = response.json()["plan"]
    assert [entry["position"] for entry in plan["entries"]] == [0, 1, 4]
    assert plan["condition_snapshot"]["conditions_json"] == {}
    assert plan["condition_snapshot"]["metrics_json"] == {}


def test_omitted_position_fallback_can_conflict_with_explicit_position(repo):
    response = client.post(
        "/api/plans",
        headers=CLIENT_A,
        json=_plan_payload(
            request_id="fallback-conflict",
            entries=[
                {"main_numbers": [1, 2, 3], "special_numbers": []},
                {"position": 0, "main_numbers": [3, 2, 1], "special_numbers": []},
            ],
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid plan"


def test_review_uses_exact_target_issue_not_latest_and_scores_repeated_digits(repo):
    plan = _create_plan(headers=CLIENT_A)
    _insert_draw(repo, issue="2026157", draw_date="2026-06-17", red_numbers="9,9,9")
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="2,2,1")

    response = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)

    assert response.status_code == 200
    reviewed = response.json()["plan"]
    assert reviewed["status"] == "reviewed"
    assert reviewed["review"]["draw_issue"] == "2026156"
    assert reviewed["review"]["draw_numbers"] == [2, 2, 1]
    assert reviewed["review"]["direct_hit"] is True
    assert reviewed["review"]["group_type"] == "组三"
    entries = reviewed["review"]["result_json"]["entries"]
    assert entries[0]["any_position_hits"] == [1, 2]
    assert entries[1]["direct_hit"] is True
    assert entries[1]["any_position_hits"] == [2, 2, 1]


def test_review_missing_draw_returns_409_and_marks_plan_pending_without_fake_review(repo):
    plan = _create_plan(headers=CLIENT_A)

    response = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)
    fetched = client.get(f"/api/plans/{plan['id']}", headers=CLIENT_A).json()["plan"]

    assert response.status_code == 409
    assert response.json()["detail"] == "draw is not available"
    assert fetched["status"] == "pending_review"
    assert fetched["review"] is None


def test_review_missing_draw_clears_existing_review_in_same_request(repo):
    plan = _create_plan(headers=CLIENT_A)
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="1,2,3")
    reviewed = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)
    assert reviewed.status_code == 200
    assert _plan_review_count(repo, plan["id"]) == 1
    _delete_draw(repo, issue="2026156")

    response = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)
    fetched = client.get(f"/api/plans/{plan['id']}", headers=CLIENT_A).json()["plan"]

    assert response.status_code == 409
    assert response.json()["detail"] == "draw is not available"
    assert fetched["status"] == "pending_review"
    assert fetched["review"] is None
    assert _plan_review_count(repo, plan["id"]) == 0


def test_review_missing_draw_review_delete_failure_returns_503_without_leak(
    repo,
    monkeypatch,
):
    plan = _create_plan(headers=CLIENT_A)
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="1,2,3")
    reviewed = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)
    assert reviewed.status_code == 200
    _delete_draw(repo, issue="2026156")

    def fail_after_delete(connection, plan_id):
        connection.execute("DELETE FROM plan_reviews WHERE plan_id = ?", (plan_id,))
        raise sqlite3.OperationalError("sqlite secret path")

    monkeypatch.setattr(
        plan_store,
        "clear_plan_review_in_transaction",
        fail_after_delete,
        raising=False,
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        f"/api/plans/{plan['id']}/review",
        headers=CLIENT_A,
    )
    fetched = client.get(f"/api/plans/{plan['id']}", headers=CLIENT_A).json()["plan"]

    assert response.status_code == 503
    assert response.json()["detail"] == "plan service is unavailable"
    assert "sqlite" not in response.text
    assert "secret" not in response.text
    assert fetched["status"] == "reviewed"
    assert fetched["review"] is not None
    assert _plan_review_count(repo, plan["id"]) == 1


def test_carry_forward_uses_server_latest_draw_copies_snapshot_and_is_idempotent(repo):
    plan = _create_plan(headers=CLIENT_A)
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="2,2,1")
    reviewed = client.post(f"/api/plans/{plan['id']}/review", headers=CLIENT_A)
    assert reviewed.status_code == 200

    forbidden = client.post(
        f"/api/plans/{plan['id']}/carry-forward",
        headers=CLIENT_A,
        json={"target_issue": "2026999"},
    )
    first = client.post(
        f"/api/plans/{plan['id']}/carry-forward",
        headers=CLIENT_A,
        json={"request_id": "carry-once"},
    )
    retry = client.post(
        f"/api/plans/{plan['id']}/carry-forward",
        headers=CLIENT_A,
        json={"request_id": "carry-once"},
    )

    assert forbidden.status_code == 422
    assert first.status_code == 200
    carried = first.json()["plan"]
    assert retry.json()["plan"]["id"] == carried["id"]
    assert carried["id"] != plan["id"]
    assert carried["source_type"] == "carried"
    assert carried["carried_from_plan_id"] == plan["id"]
    assert carried["target_issue"] == "2026157"
    assert carried["target_draw_date"] == "2026-06-17"
    assert carried["entries"][0]["main_numbers"] == plan["entries"][0]["main_numbers"]
    assert carried["condition_snapshot"]["conditions_json"] == plan["condition_snapshot"]["conditions_json"]
    assert carried["review"] is None


def test_carry_forward_cross_year_target_is_derived_from_latest_draw(repo):
    plan = _create_plan(
        headers=CLIENT_A,
        target_issue="2026365",
        target_draw_date="2026-12-31",
        request_id="cross-year-source",
    )
    _insert_draw(repo, issue="2026365", draw_date="2026-12-31", red_numbers="1,2,3")

    response = client.post(f"/api/plans/{plan['id']}/carry-forward", headers=CLIENT_A)

    assert response.status_code == 200
    carried = response.json()["plan"]
    assert carried["target_issue"] == "2027001"
    assert carried["target_draw_date"] == "2027-01-01"


def test_carry_forward_returns_409_when_latest_draw_is_missing(repo):
    plan = _create_plan(headers=CLIENT_A)

    response = client.post(f"/api/plans/{plan['id']}/carry-forward", headers=CLIENT_A)

    assert response.status_code == 409
    assert response.json()["detail"] == "draw is not available"


def test_carry_forward_requires_source_target_draw_even_when_latest_exists(repo):
    plan = _create_plan(
        headers=CLIENT_A,
        request_id="carry-source-missing",
        target_issue="2026156",
        target_draw_date="2026-06-16",
    )
    _insert_draw(repo, issue="2026155", draw_date="2026-06-15", red_numbers="1,2,3")

    response = client.post(
        f"/api/plans/{plan['id']}/carry-forward",
        headers=CLIENT_A,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "draw is not available"
    assert client.get("/api/plans", headers=CLIENT_A).json()["plans"] == [plan]


def test_carry_forward_request_id_conflicting_payload_returns_409(repo):
    first_source = _create_plan(
        headers=CLIENT_A,
        request_id="carry-conflict-source-1",
        title="source one",
    )
    second_source = _create_plan(
        headers=CLIENT_A,
        request_id="carry-conflict-source-2",
        target_issue="2026157",
        target_draw_date="2026-06-17",
        title="source two",
    )
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="1,2,3")
    first = client.post(
        f"/api/plans/{first_source['id']}/carry-forward",
        headers=CLIENT_A,
        json={"request_id": "carry-conflict"},
    )
    _insert_draw(repo, issue="2026157", draw_date="2026-06-17", red_numbers="3,2,1")

    conflict = client.post(
        f"/api/plans/{second_source['id']}/carry-forward",
        headers=CLIENT_A,
        json={"request_id": "carry-conflict"},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "request id conflicts with an existing plan"


def test_carry_forward_checks_client_scope_before_latest_draw_availability(repo):
    plan = _create_plan(headers=CLIENT_A)

    response = client.post(f"/api/plans/{plan['id']}/carry-forward", headers=CLIENT_B)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "bad_date",
    [
        "20260616",
        "2026-W25-2",
        "2026-06-16T00:00:00",
        " 2026-06-16 ",
        "2026-6-16",
    ],
)
@pytest.mark.parametrize("date_field", ["target_draw_date", "latest_data_date"])
def test_plan_dates_require_zero_padded_yyyy_mm_dd_json_strings(repo, bad_date, date_field):
    payload = _plan_payload(request_id=f"bad-date-{date_field}-{bad_date}")
    if date_field == "target_draw_date":
        payload["target_draw_date"] = bad_date
    else:
        payload["condition_snapshot"] = {
            **payload["condition_snapshot"],
            "latest_data_date": bad_date,
        }

    response = client.post("/api/plans", headers=CLIENT_A, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "body", "error_on"),
    [
        ("post", "/api/plans", _plan_payload(request_id="sqlite-create"), "create_plan"),
        ("get", "/api/plans", None, "list_plans"),
        ("get", "/api/plans/plan-test", None, "get_plan"),
        ("patch", "/api/plans/plan-test", {"title": "patched"}, "update_plan"),
        ("delete", "/api/plans/plan-test", None, "delete_plan"),
        ("post", "/api/plans/plan-test/review", None, "pending_update"),
        ("post", "/api/plans/plan-test/carry-forward", {}, "recent_draws"),
    ],
)
def test_plan_routes_map_sqlite_errors_to_generic_503(method, path, body, error_on):
    class SqliteErrorRepo:
        def _raise(self):
            raise sqlite3.OperationalError("sqlite secret path")

        def draw_by_issue(self, game_key, issue):
            return None

        def get_plan_by_request_id(self, client_id, request_id):
            return None

        def create_plan_lifecycle(self, client_id, payload):
            if error_on == "create_plan":
                self._raise()
            return {"id": "plan-test"}

        def create_plan(self, client_id, payload):
            if error_on == "create_plan":
                self._raise()
            return {"id": "plan-test"}

        def list_plans(self, client_id):
            if error_on == "list_plans":
                self._raise()
            return []

        def get_plan(self, client_id, plan_id):
            if error_on == "get_plan":
                self._raise()
            return {
                "id": plan_id,
                "target_issue": "2026156",
                "target_draw_date": "2026-06-16",
            }

        def update_plan(self, client_id, plan_id, updates):
            if error_on in {"update_plan", "pending_update"}:
                self._raise()
            return {"id": plan_id}

        def delete_plan(self, client_id, plan_id):
            if error_on == "delete_plan":
                self._raise()
            return True

        def recent_draws(self, game_key, limit=1):
            if error_on == "recent_draws":
                self._raise()
            return [{"issue": "2026156", "draw_date": "2026-06-16", "red_numbers": "1,2,3"}]

        def review_plan_lifecycle(self, client_id, plan_id):
            if error_on == "pending_update":
                self._raise()
            return {"id": plan_id, "review": {"draw_issue": "2026156"}}

        def review_plan(self, client_id, plan_id, draw):
            return {"id": plan_id, "review": {"draw_issue": draw["issue"]}}

        def carry_forward_plan_lifecycle(self, client_id, plan_id, *, request_id=None):
            if error_on == "recent_draws":
                self._raise()
            return {"id": "carried-plan", "carried_from_plan_id": plan_id}

        def carry_forward_plan(self, client_id, plan_id, latest_draw, *, request_id=None):
            return {"id": "carried-plan", "carried_from_plan_id": plan_id}

    app.dependency_overrides[get_repository] = lambda: SqliteErrorRepo()
    try:
        response = TestClient(app, raise_server_exceptions=False).request(
            method.upper(),
            path,
            headers=CLIENT_A,
            json=body,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "plan service is unavailable"
    assert "sqlite" not in response.text
    assert "secret" not in response.text


def test_draw_by_issue_returns_exact_parameterized_match_or_none(repo):
    _insert_draw(repo, issue="2026156", draw_date="2026-06-16", red_numbers="1,2,3")

    draw = repo.draw_by_issue("3d", "2026156")

    assert draw is not None
    assert draw["issue"] == "2026156"
    assert draw["red_numbers"] == "1,2,3"
    assert repo.draw_by_issue("3d", "2026999") is None
    assert repo.draw_by_issue("3d", "2026156' OR 1=1 --") is None


def test_plan_router_is_registered_before_static_mount(repo):
    route_names = [getattr(route, "name", "") for route in app.routes]
    plan_index = next(
        index
        for index, route in enumerate(app.routes)
        if any(
            getattr(child, "path", "") == "/api/plans"
            for child in getattr(getattr(route, "original_router", None), "routes", [])
        )
    )
    static_index = route_names.index("web")

    response = client.get("/api/plans")

    assert plan_index < static_index
    assert response.status_code == 400
