from __future__ import annotations

import copy

import pytest

from lottery_luck.three_d_tools import build_trend_payload


def draw(issue: str, draw_date: str, red_numbers: str) -> dict[str, str]:
    return {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": issue,
        "draw_date": draw_date,
        "red_numbers": red_numbers,
    }


def test_trend_payload_is_chronological_and_resets_window_omission():
    draws = [
        draw("2026182", "2026-07-11", "6,6,2"),
        draw("2026181", "2026-07-10", "0,0,6"),
        draw("2026180", "2026-07-09", "1,2,3"),
    ]

    payload = build_trend_payload(draws, 30)

    assert [row["issue"] for row in payload["rows"]] == [
        "2026180",
        "2026181",
        "2026182",
    ]
    assert payload["rows"][0]["number_text"] == "123"
    assert payload["rows"][0]["omissions"]["0"]["1"] == 0
    assert payload["rows"][1]["omissions"]["0"]["1"] == 1
    assert payload["rows"][2]["omissions"]["0"]["6"] == 0
    assert set(payload["rows"][2]["omissions"]["2"]) == {str(i) for i in range(10)}


def test_trend_payload_reports_the_drought_a_drawn_digit_ended():
    """Each row states, per position, how many draws the drawn digit had been missing.

    `omissions[position][digit]` is 0 for the digit that just hit, by construction, so it can
    never describe the streak the hit ended. `hit_omissions` carries that pre-reset streak.
    """
    draws = [
        draw("2026184", "2026-07-13", "5,0,0"),
        draw("2026183", "2026-07-12", "1,0,0"),
        draw("2026182", "2026-07-11", "1,0,0"),
        draw("2026181", "2026-07-10", "1,0,0"),
        draw("2026180", "2026-07-09", "5,0,0"),
    ]

    payload = build_trend_payload(draws, 30)

    # 百位: 5 opens the window, then 1 hits three times, then 5 returns after a 3-draw drought.
    assert [row["hit_omissions"]["0"] for row in payload["rows"]] == [0, 1, 0, 0, 3]
    # 十位/个位: 0 hits every draw, so it never carries a drought.
    assert [row["hit_omissions"]["1"] for row in payload["rows"]] == [0, 0, 0, 0, 0]
    assert set(payload["rows"][4]["hit_omissions"]) == {"0", "1", "2"}
    # The omission matrix stays intact for its own consumers.
    assert payload["rows"][4]["omissions"]["0"]["5"] == 0
    assert payload["rows"][4]["omissions"]["0"]["1"] == 1


def test_trend_payload_handles_empty_draws():
    payload = build_trend_payload([], 30)

    assert payload["window"] == 30
    assert payload["sample_size"] == 0
    assert payload["rows"] == []
    assert payload["latest_issue"] == ""
    assert payload["latest_date"] == ""
    # The definition names the reading the table actually shows: the pre-hit omission streak.
    assert payload["definition"] == (
        "每格是这一位当期开出的数字，下面的遗漏是它在这次开出前，已经连续多少期没有开出。"
    )
    # The reading the table really carries is the pre-hit streak, and the copy must say so
    # without narrating the implementation.
    assert "开出前" in payload["definition"]
    for internal in ("窗口", "序列", "omission", "segment"):
        assert internal not in payload["definition"], internal


@pytest.mark.parametrize("bad_window", [31, 0, "30", True, 30.0])
def test_trend_payload_rejects_invalid_window(bad_window):
    with pytest.raises(ValueError, match="invalid 3d data"):
        build_trend_payload([], bad_window)


def test_trend_payload_preserves_leading_zero_number_text():
    draws = [
        draw("2026181", "2026-07-10", "0,0,6"),
    ]

    payload = build_trend_payload(draws, 30)

    assert payload["rows"][0]["number_text"] == "006"
    assert payload["rows"][0]["numbers"] == [0, 0, 6]


def test_trend_payload_does_not_mutate_input_list():
    draws = [
        draw("2026182", "2026-07-11", "6,6,2"),
        draw("2026181", "2026-07-10", "0,0,6"),
        draw("2026180", "2026-07-09", "1,2,3"),
    ]
    original = copy.deepcopy(draws)

    build_trend_payload(draws, 30)

    assert draws == original
