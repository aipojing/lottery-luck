from fastapi.testclient import TestClient
import pytest

from lottery_luck.api import app


client = TestClient(app)


def test_tool_config_route():
    response = client.get("/api/tools/config")
    assert response.status_code == 200
    assert list(response.json()["games"]) == ["ssq", "dlt", "3d", "pl3", "kl8"]


def test_quick_pick_route_returns_normalized_entries():
    response = client.post(
        "/api/tools/ssq/quick-pick",
        json={"count": 2, "options": {}, "locked": {"main": [1]}, "excluded": {"main": [2]}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_count"] == 2
    assert all(1 in entry["main"] and 2 not in entry["main"] for entry in body["entries"])


def test_compose_route_maps_domain_errors_to_stable_422_detail():
    response = client.post(
        "/api/tools/ssq/compose",
        json={"mode": "full", "selection": {"main": [1, 2], "special": [3]}, "options": {}},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "selection_too_small"


def test_compose_route_rejects_estimated_spend_over_limit():
    response = client.post(
        "/api/tools/kl8/compose",
        json={
            "mode": "full",
            "selection": {"main": list(range(1, 21))},
            "options": {"play_type": 10},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "spend_limit",
        "message": "estimated spend exceeds 20000 yuan",
    }


def test_unknown_game_has_stable_error():
    response = client.post("/api/tools/qlc/quick-pick", json={"count": 1})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "invalid_game"


@pytest.mark.parametrize(
    "payload",
    [
        {"count": "2"},
        {"count": 2, "unexpected": True},
    ],
)
def test_quick_pick_rejects_non_strict_or_extra_request_fields(payload):
    response = client.post("/api/tools/ssq/quick-pick", json=payload)

    assert response.status_code == 422


def test_reduce_route_returns_budgeted_entries():
    response = client.post(
        "/api/tools/ssq/reduce",
        json={
            "entries": [
                {"main": [1, 2, 3, 4, 5, 6], "special": [7]},
                {"main": [8, 9, 10, 11, 12, 13], "special": [14]},
            ],
            "budget": 2,
        },
    )

    assert response.status_code == 200
    assert response.json()["ticket_count"] == 1
    assert response.json()["total_cost"] == 2


def test_reduce_route_rejects_budget_over_schema_limit():
    response = client.post(
        "/api/tools/ssq/reduce",
        json={
            "entries": [{"main": [1, 2, 3, 4, 5, 6], "special": [7]}],
            "budget": 20_001,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_request",
        "message": "工具请求参数无效。",
    }


def test_organize_route_intersects_batches():
    response = client.post(
        "/api/tools/ssq/organize",
        json={
            "batch_a": "01 02 03 04 05 06 | 07\n08 09 10 11 12 13 | 14",
            "batch_b": "01 02 03 04 05 06 | 07",
            "operation": "intersection",
        },
    )

    assert response.status_code == 200
    assert [entry["text"] for entry in response.json()["entries"]] == [
        "01 02 03 04 05 06 | 07"
    ]


def test_organize_route_enforces_batch_text_limit():
    response = client.post(
        "/api/tools/ssq/organize",
        json={"batch_a": "1" * 100_001},
    )

    assert response.status_code == 422


def test_dlt_compose_route_applies_add_on_cost():
    response = client.post(
        "/api/tools/dlt/compose",
        json={
            "mode": "full",
            "selection": {"main": [1, 2, 3, 4, 5], "special": [1, 2]},
            "options": {"add_on": True},
        },
    )

    assert response.status_code == 200
    assert response.json()["entry_cost"] == 3


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/tools/ssq/quick-pick", {"count": "2"}),
        ("/api/tools/ssq/quick-pick", {"count": 1, "unexpected": True}),
        ("/api/tools/ssq/reduce", {"budget": 20_001, "entries": []}),
    ],
)
def test_tool_request_validation_uses_stable_detail_shape(path, payload):
    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_request",
        "message": "工具请求参数无效。",
    }


def test_dlt_dantuo_route_allows_full_front_zone_and_rejects_full_dan_with_tuo():
    accepted = client.post(
        "/api/tools/dlt/compose",
        json={
            "mode": "dantuo",
            "dan": {"main": [], "special": [1]},
            "tuo": {"main": [2, 3, 4, 5, 6, 7], "special": [2, 3]},
        },
    )
    rejected = client.post(
        "/api/tools/dlt/compose",
        json={
            "mode": "dantuo",
            "dan": {"main": [1], "special": [1, 2]},
            "tuo": {"main": [2, 3, 4, 5], "special": [3]},
        },
    )

    assert accepted.status_code == 200
    assert accepted.json()["ticket_count"] == 12
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "selection_too_large"


def test_reduce_route_keeps_digit_play_type_and_ordered_repeats():
    response = client.post(
        "/api/tools/3d/reduce",
        json={
            "entries": [
                {"main": [1, 1, 2], "special": [], "play_type": "straight"},
                {"main": [1, 2], "special": [], "play_type": "group3"},
            ],
            "budget": 4,
        },
    )

    assert response.status_code == 200
    assert {
        (entry["text"], entry["play_type"], tuple(entry["main"]))
        for entry in response.json()["entries"]
    } == {
        ("112", "straight", (1, 1, 2)),
        ("1 2 · 组三", "group3", (1, 2)),
    }


def test_truncated_compose_route_can_reduce_from_compact_source():
    composed = client.post(
        "/api/tools/ssq/compose",
        json={
            "mode": "full",
            "selection": {"main": list(range(1, 16)), "special": [1]},
        },
    )
    assert composed.status_code == 200
    body = composed.json()
    assert body["ticket_count"] == 5_005
    assert body["entries"] == []

    reduced = client.post(
        "/api/tools/ssq/reduce",
        json={"budget": 20, "source": body["reduction_source"]},
    )
    assert reduced.status_code == 200
    assert reduced.json()["original_ticket_count"] == 5_005
    assert reduced.json()["ticket_count"] == 10
    assert reduced.json()["total_cost"] == 20


def test_dlt_dantuo_route_requires_a_dan_in_at_least_one_zone():
    response = client.post(
        "/api/tools/dlt/compose",
        json={
            "mode": "dantuo",
            "dan": {"main": [], "special": []},
            "tuo": {"main": [1, 2, 3, 4, 5], "special": [1, 2]},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "selection_too_small"
