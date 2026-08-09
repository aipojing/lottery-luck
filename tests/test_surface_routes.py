from fastapi.testclient import TestClient

from lottery_luck.api import app
from lottery_luck.surface_config import capabilities_for_game

client = TestClient(app)


def test_surface_config_has_ordered_public_games_and_two_research_views():
    response = client.get("/api/surfaces/config")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert list(body["games"]) == ["ssq", "dlt", "3d", "pl3", "kl8"]
    assert body["views"] == ["data", "strategy"]


def test_digit_games_expose_position_research_and_group_tool_label():
    game = capabilities_for_game("3d")
    assert "position_omission" in game["research"]["data"]
    assert "digit_shape" in game["research"]["strategy"]["features"]
    assert game["research"]["strategy"]["condition_fields"] == [
        "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
        "max_consecutive_run", "prime_composite", "mod3", "tail_exclude",
        "tail_include", "min_omission",
    ]
    assert game["tool_labels"]["dantuo"] == "组选包号"


def test_lotto_and_kl8_capabilities_are_game_specific():
    dlt = capabilities_for_game("dlt")
    kl8 = capabilities_for_game("kl8")
    assert "special_zone" in dlt["research"]["data"]
    assert "large_field_rules" in kl8["research"]["strategy"]["features"]
    assert "position_omission" not in kl8["research"]["data"]
