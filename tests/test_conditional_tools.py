import pytest

from lottery_luck.conditional_tools import conditional_pick
from lottery_luck.number_tools import ToolError


@pytest.fixture
def sample_ssq_draws():
    rows = [
        ("012", "2026-07-12", "01,04,07,12,22,33", "07"),
        ("011", "2026-07-11", "02,05,08,13,23,32", "08"),
        ("010", "2026-07-10", "03,06,09,14,24,31", "09"),
        ("009", "2026-07-09", "01,10,15,20,25,30", "10"),
        ("008", "2026-07-08", "02,11,16,21,26,29", "11"),
        ("007", "2026-07-07", "03,12,17,22,27,28", "12"),
        ("006", "2026-07-06", "04,13,18,23,28,33", "13"),
        ("005", "2026-07-05", "05,14,19,24,29,32", "14"),
        ("004", "2026-07-04", "06,15,20,25,30,31", "15"),
        ("003", "2026-07-03", "07,16,21,26,27,33", "16"),
        ("002", "2026-07-02", "08,17,22,23,28,32", "01"),
        ("001", "2026-07-01", "09,18,19,24,29,31", "02"),
    ]
    return [
        {"issue": issue, "draw_date": date, "red_numbers": main, "blue_number": special}
        for issue, date, main, special in rows
    ]


def test_digit_filter_keeps_ordered_repeated_digits():
    result = conditional_pick(
        "3d", [], "digit_filter", "balanced",
        {"types": ["组三"], "position_include": {"0": [1]}, "max_results": 10},
        10, {},
    )
    assert result["tool"] == "conditional"
    assert all(entry["main"][0] == 1 for entry in result["entries"])
    assert any(len(set(entry["main"])) == 2 for entry in result["entries"])


def test_strategy_filter_requires_history_and_returns_tool_entries(sample_ssq_draws):
    result = conditional_pick("ssq", sample_ssq_draws, "strategy", "balanced", {}, 5, {})
    assert result["ticket_count"] == 5
    assert result["source_meta"]["source"] == "strategy"
    assert all(len(entry["main"]) == 6 and len(entry["special"]) == 1 for entry in result["entries"])


def test_digit_filter_rejects_lotto_game():
    with pytest.raises(ToolError) as exc:
        conditional_pick("ssq", [], "digit_filter", "balanced", {}, 5, {})
    assert exc.value.code == "invalid_conditional_source"


def test_digit_filter_maps_invalid_nested_conditions_to_tool_error():
    with pytest.raises(ToolError) as exc:
        conditional_pick("3d", [], "digit_filter", "balanced", {"types": ["group3"]}, 5, {})
    assert exc.value.code == "invalid_conditions"


def test_strategy_filter_rejects_more_than_thirty_candidates(sample_ssq_draws):
    with pytest.raises(ToolError) as exc:
        conditional_pick("ssq", sample_ssq_draws, "strategy", "balanced", {}, 31, {})
    assert exc.value.code == "invalid_count"
