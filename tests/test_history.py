import pytest

from lottery_luck.history import _weighted_increment, build_history_profile
from lottery_luck.rules import GAME_RULES
from lottery_luck.repository import LotteryRepository


def test_history_profile_contains_frequency_and_omission():
    repo = LotteryRepository()
    profile = build_history_profile("ssq", repo.all_draws("ssq"))
    assert profile["main_frequency"][4] > 0
    assert 1 <= profile["hot_main"][0] <= 33
    assert 1 <= profile["cold_main"][0] <= 33
    assert profile["main_omission"][4] >= 0


def test_history_profile_supports_3d_positions():
    repo = LotteryRepository()
    profile = build_history_profile("3d", repo.all_draws("3d"))
    assert set(profile["position_frequency"].keys()) == {0, 1, 2}
    assert set(profile["position_frequency"][0].keys()) == set(GAME_RULES["3d"].main_range)


def test_history_profile_manual_ssq_sample_asserts_frequency_weight_omission_and_special():
    draws = [
        {"red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"red_numbers": "01,02,03,04,05,07", "blue_number": "08"},
    ]

    profile = build_history_profile("ssq", draws)

    assert profile["draw_count"] == 2
    assert profile["main_frequency"][1] == 2
    assert profile["main_frequency"][6] == 1
    assert profile["main_frequency"][7] == 1
    assert profile["main_omission"][1] == 0
    assert profile["main_omission"][8] == 2
    assert profile["main_weighted"][1] == pytest.approx(
        _weighted_increment(0) + _weighted_increment(1)
    )
    assert profile["special_frequency"][7] == 1
    assert profile["special_frequency"][8] == 1
    assert profile["position_frequency"][0][1] == 2
    assert profile["position_frequency"][1][7] == 0


def test_history_profile_manual_3d_repeat_numbers_and_position_counts():
    draws = [
        {"red_numbers": "1,2,2", "blue_number": ""},
        {"red_numbers": "1,1,3", "blue_number": ""},
    ]
    profile = build_history_profile("3d", draws)

    assert profile["main_frequency"][1] == 3
    assert profile["position_frequency"][0][1] == 2
    assert profile["position_frequency"][1][2] == 1
    assert profile["position_frequency"][1][1] == 1
    assert profile["position_frequency"][2][3] == 1


def test_history_profile_returns_stable_position_schema_for_empty_draws():
    for game_key in ("ssq", "3d", "kl8"):
        rule = GAME_RULES[game_key]
        profile = build_history_profile(game_key, [])

        assert set(profile["position_frequency"].keys()) == set(range(rule.draw_main_count))
        for pos in range(rule.draw_main_count):
            assert set(profile["position_frequency"][pos].keys()) == set(rule.main_range)
            assert all(v == 0 for v in profile["position_frequency"][pos].values())


def test_history_profile_for_kl8_limited_to_draw_main_positions():
    draws = [
        {
            "red_numbers": "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21",
            "blue_number": "",
        }
    ]
    profile = build_history_profile("kl8", draws)

    assert set(profile["position_frequency"].keys()) == set(range(20))
    assert profile["position_frequency"][19][20] == 1
    assert 20 not in profile["position_frequency"]
