from __future__ import annotations

import copy
import importlib

import pytest


def workbench():
    try:
        return importlib.import_module("lottery_luck.workbench_3d")
    except ModuleNotFoundError as exc:
        pytest.fail(f"workbench_3d module missing: {exc}")


def draw(
    numbers: list[int] | None = None,
    *,
    issue: str = "001",
    draw_date: str = "2026-01-01",
    red_numbers: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {"issue": issue, "draw_date": draw_date}
    if numbers is not None:
        row["main"] = numbers
    if red_numbers is not None:
        row["red_numbers"] = red_numbers
    return row


def cell(stats: dict[str, object], position: int, digit: int) -> dict[str, object]:
    positions = stats["positions"]
    return positions[str(position)]["digits"][str(digit)]


def labels(rows: list[dict[str, object]]) -> dict[object, int]:
    return {row["label"]: row["count"] for row in rows}


def values(rows: list[dict[str, object]]) -> dict[object, int]:
    return {row["value"]: row["count"] for row in rows}


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        (
            [6, 6, 2],
            {
                "number_text": "662",
                "sum": 14,
                "sum_tail": 4,
                "span": 4,
                "group_type": "组三",
                "odd_even": "0:3",
                "big_small": "2:1",
                "mod3": "2:0:1",
                "prime_composite": "1:2",
                "repeat_count": 1,
                "consecutive_pairs": [],
                "adjacent_pairs": [],
            },
        ),
        (
            [7, 7, 7],
            {
                "number_text": "777",
                "sum": 21,
                "sum_tail": 1,
                "span": 0,
                "group_type": "豹子",
                "odd_even": "3:0",
                "big_small": "3:0",
                "mod3": "0:3:0",
                "prime_composite": "3:0",
                "repeat_count": 2,
                "consecutive_pairs": [],
                "adjacent_pairs": [],
            },
        ),
        (
            [1, 2, 3],
            {
                "number_text": "123",
                "sum": 6,
                "sum_tail": 6,
                "span": 2,
                "group_type": "组六",
                "odd_even": "2:1",
                "big_small": "0:3",
                "mod3": "1:1:1",
                "prime_composite": "2:1",
                "repeat_count": 0,
                "consecutive_pairs": [[1, 2], [2, 3]],
                "adjacent_pairs": [[0, 1], [1, 2]],
            },
        ),
    ],
)
def test_number_attributes_returns_complete_shape_fields(numbers, expected):
    attrs = workbench().number_attributes(numbers)

    for key, value in expected.items():
        assert attrs[key] == value
    assert attrs["numbers"] == numbers
    assert attrs["unique_count"] == 3 - attrs["repeat_count"]
    assert set(attrs) >= {
        "odd_count",
        "even_count",
        "big_count",
        "small_count",
        "prime_count",
        "composite_count",
    }


@pytest.mark.parametrize(
    "numbers",
    [
        [1, 2],
        [1, 2, 10],
        [1, 2, "3"],
        [1, 2, 3.0],
        [True, 1, 2],
        "123",
    ],
)
def test_number_attributes_rejects_non_strict_digit_lists(numbers):
    with pytest.raises(ValueError, match="invalid 3d data"):
        workbench().number_attributes(numbers)


def test_parsing_rejects_invalid_draws_window_and_number_text():
    wb = workbench()

    for bad_draws in (
        [draw([1, 2, "3"])],
        [draw([1, 2, 3.0])],
        [draw([1, 2, True])],
        [draw([1, 2])],
        [draw(red_numbers="1,2")],
        [draw(red_numbers="1,2,10")],
        [draw(red_numbers="1,2,x")],
        [draw(red_numbers="1, 2,3")],
        [draw(red_numbers="1,\t2,3")],
        [draw(red_numbers="1,,3")],
        [draw(red_numbers="11,2,3")],
        [draw(red_numbers="１,2,3")],
        [draw(red_numbers=" 1,2,3")],
        [draw(red_numbers="1,2,3 ")],
        [{"issue": "001", "draw_date": "2026-01-01"}],
    ):
        with pytest.raises(ValueError, match="invalid 3d data"):
            wb.build_position_stats(bad_draws, 30)

    for bad_window in (31, 0, "30", True, 30.0):
        with pytest.raises(ValueError, match="invalid 3d data"):
            wb.build_position_stats([], bad_window)

    for bad_text in (" 006", "006\n", "１２３", "06", "006x", 6, None):
        with pytest.raises(ValueError, match="invalid 3d data"):
            wb.query_number(bad_text, [], 30)


def test_draw_parsing_requires_main_and_red_numbers_to_match_when_both_exist():
    wb = workbench()

    consistent = wb.build_position_stats(
        [draw([1, 2, 3], red_numbers="1,2,3")],
        30,
    )
    assert consistent["sample_size"] == 1
    assert cell(consistent, 0, 1)["frequency"] == 1
    assert cell(consistent, 1, 2)["frequency"] == 1
    assert cell(consistent, 2, 3)["frequency"] == 1

    for bad_draw in (
        draw([1, 2, 4], red_numbers="1,2,3"),
        draw([1, 2, "3"], red_numbers="1,2,3"),
        draw([1, 2, 3], red_numbers="1,2,x"),
    ):
        with pytest.raises(ValueError, match="invalid 3d data"):
            wb.build_position_stats([bad_draw], 30)


def test_position_stats_are_position_independent_and_include_boundary_omissions():
    wb = workbench()
    draws = [
        draw([6, 1, 0], issue="004", draw_date="2026-01-04"),
        draw([5, 6, 0], issue="003", draw_date="2026-01-03"),
        draw(issue="002", draw_date="2026-01-02", red_numbers="6,6,2"),
        draw([0, 6, 6], issue="001", draw_date="2026-01-01"),
    ]

    stats = wb.build_position_stats(draws, 30)

    assert stats["window"] == 30
    assert stats["sample_size"] == 4
    assert stats["latest_issue"] == "004"
    assert stats["latest_date"] == "2026-01-04"
    assert stats["freshness"]["status"] == "available"
    # The definition is copy a player reads: it states the window it covers, explains every
    # reading the tool shows in the words the tool labels them with, and keeps the disclaimer.
    # It must never ship API field names or internal jargon to an end user.
    assert "最近30期" in stats["definition"]
    assert "出次" in stats["definition"]
    assert "当前遗漏" in stats["definition"]
    assert "平均遗漏" in stats["definition"]
    assert "最大遗漏" in stats["definition"]
    assert "不代表未来概率" in stats["definition"]
    for internal in ("frequency", "omission", "percentile", "segment", "heat", "分位"):
        assert internal not in stats["definition"], internal

    assert cell(stats, 0, 6)["frequency"] == 2
    assert cell(stats, 0, 6)["current_omission"] == 0
    assert cell(stats, 0, 6)["average_omission"] == 0.67
    assert cell(stats, 0, 6)["max_omission"] == 1
    assert cell(stats, 0, 6)["historical_percentile"] == 0.0
    assert cell(stats, 0, 6)["frequency_percentile"] == 100.0

    assert cell(stats, 1, 6)["frequency"] == 3
    assert cell(stats, 1, 6)["current_omission"] == 1
    assert cell(stats, 2, 6)["frequency"] == 1
    assert cell(stats, 2, 6)["current_omission"] == 3

    assert cell(stats, 0, 9)["frequency"] == 0
    assert cell(stats, 0, 9)["current_omission"] == 4
    assert cell(stats, 0, 9)["average_omission"] == 4.0
    assert cell(stats, 0, 9)["max_omission"] == 4
    assert cell(stats, 0, 9)["historical_percentile"] == 0.0
    assert cell(stats, 0, 9)["frequency_percentile"] == 0.0

    for position in range(3):
        for digit in range(10):
            assert 0 <= cell(stats, position, digit)["historical_percentile"] <= 100
            assert 0 <= cell(stats, position, digit)["frequency_percentile"] <= 100


def test_historical_percentile_uses_digit_own_omission_segments():
    wb = workbench()
    stats = wb.build_position_stats(
        [
            draw([0, 0, 0], issue="009"),
            draw([1, 0, 0], issue="008"),
            draw([6, 0, 0], issue="007"),
            draw([2, 0, 0], issue="006"),
            draw([6, 0, 0], issue="005"),
            draw([3, 0, 0], issue="004"),
            draw([4, 0, 0], issue="003"),
            draw([6, 0, 0], issue="002"),
            draw([5, 0, 0], issue="001"),
        ],
        30,
    )

    digit_six = cell(stats, 0, 6)
    assert digit_six["frequency"] == 3
    assert digit_six["current_omission"] == 2
    assert digit_six["average_omission"] == 1.5
    assert digit_six["max_omission"] == 2
    assert digit_six["historical_percentile"] == 100.0
    assert digit_six["frequency_percentile"] == 100.0


def test_position_stats_percentile_window_slice_and_empty_matrix():
    wb = workbench()
    rows = [
        draw([index % 9, 0, 0], issue=f"{index:03d}", draw_date="2026-01-01")
        for index in range(30)
    ]
    rows.append(draw([9, 9, 9], issue="oldest", draw_date="2025-12-01"))

    latest_30 = wb.build_position_stats(rows, 30)
    latest_60 = wb.build_position_stats(rows, 60)

    assert latest_30["sample_size"] == 30
    assert cell(latest_30, 0, 9)["frequency"] == 0
    assert cell(latest_30, 0, 9)["current_omission"] == 30
    assert latest_60["sample_size"] == 31
    assert cell(latest_60, 0, 9)["frequency"] == 1

    boundary = wb.build_position_stats(
        [
            draw([6, 0, 0]),
            draw([5, 0, 0]),
            draw([6, 0, 0]),
            draw([0, 0, 0]),
        ],
        30,
    )
    assert cell(boundary, 0, 6)["historical_percentile"] == 0.0
    assert cell(boundary, 0, 6)["frequency_percentile"] == 100.0
    assert cell(boundary, 0, 5)["historical_percentile"] == 0.0
    assert cell(boundary, 0, 5)["frequency_percentile"] == 50.0
    assert cell(boundary, 0, 9)["historical_percentile"] == 0.0
    assert cell(boundary, 0, 9)["frequency_percentile"] == 0.0

    empty = wb.build_position_stats([], 30)
    assert empty["sample_size"] == 0
    assert empty["freshness"]["status"] == "empty"
    assert empty["latest_issue"] == ""
    assert empty["latest_date"] == ""
    for position in range(3):
        for digit in range(10):
            assert cell(empty, position, digit) == {
                "position": position,
                "digit": digit,
                "frequency": 0,
                "current_omission": 0,
                "average_omission": 0.0,
                "max_omission": 0,
                "historical_percentile": 0.0,
                "frequency_percentile": 0.0,
                "omission_hotness": 0.0,
                "heat_score": 0.0,
                "heat": "cold",
            }


def test_heat_uses_both_frequency_and_current_omission():
    wb = workbench()
    stats = wb.build_position_stats(
        [
            draw([1, 4, 0]),
            draw([2, 5, 0]),
            draw([1, 5, 0]),
            draw([2, 5, 0]),
            draw([3, 6, 0]),
            draw([3, 6, 0]),
        ],
        30,
    )

    same_frequency_latest = cell(stats, 0, 1)
    same_frequency_older = cell(stats, 0, 2)
    assert same_frequency_latest["frequency"] == same_frequency_older["frequency"] == 2
    assert same_frequency_latest["current_omission"] < same_frequency_older["current_omission"]
    assert same_frequency_latest["historical_percentile"] != same_frequency_older["historical_percentile"]
    assert same_frequency_latest["frequency_percentile"] == same_frequency_older["frequency_percentile"]
    assert same_frequency_latest["heat_score"] > same_frequency_older["heat_score"]

    same_omission_more_frequent = cell(stats, 0, 1)
    same_omission_less_frequent = cell(stats, 1, 4)
    assert same_omission_more_frequent["current_omission"] == same_omission_less_frequent["current_omission"] == 0
    assert same_omission_more_frequent["frequency"] > same_omission_less_frequent["frequency"]
    assert same_omission_more_frequent["frequency_percentile"] > same_omission_less_frequent["frequency_percentile"]
    assert same_omission_more_frequent["heat_score"] > same_omission_less_frequent["heat_score"]


def test_query_number_reports_exact_and_counter_group_history_for_repeats():
    wb = workbench()
    draws = [
        draw([0, 0, 6], issue="004", draw_date="2026-01-04"),
        draw(issue="003", draw_date="2026-01-03", red_numbers="0,6,0"),
        draw([6, 0, 0], issue="002", draw_date="2026-01-02"),
        draw([0, 6, 6], issue="001", draw_date="2026-01-01"),
    ]

    result = wb.query_number("006", draws, 120)

    assert result["number_text"] == "006"
    assert result["numbers"] == [0, 0, 6]
    assert result["attributes"]["group_type"] == "组三"
    assert result["history"]["exact"]["count"] == 1
    assert result["history"]["exact"]["latest"]["issue"] == "004"
    assert result["history"]["exact"]["latest"]["index"] == 0
    assert result["history"]["group"]["count"] == 3
    assert result["history"]["group"]["latest"]["issue"] == "004"
    assert result["position_digits"]["0"]["digit"] == 0
    assert result["position_digits"]["0"]["frequency"] == 3
    assert result["position_digits"]["2"]["digit"] == 6
    assert result["freshness"]["status"] == "available"

    empty = wb.query_number("006", [], 120)
    assert empty["history"]["exact"] == {"count": 0, "latest": None}
    assert empty["history"]["group"] == {"count": 0, "latest": None}
    assert empty["freshness"]["status"] == "empty"
    assert empty["position_digits"]["2"]["current_omission"] == 0


def test_query_number_reports_the_window_and_sample_its_position_stats_came_from():
    wb = workbench()
    draws = [
        draw([0, 0, 6], issue=f"{index:03d}", draw_date="2026-01-04")
        for index in range(4)
    ]

    # The caller states the window; the payload may never claim a window the stats
    # were not computed over.
    result = wb.query_number("006", draws, 30)
    assert result["position_stats_window"] == 30
    assert result["position_stats_sample_size"] == 4

    wider = wb.query_number("006", draws, 120)
    assert wider["position_stats_window"] == 120
    assert wider["position_stats_sample_size"] == 4

    # The sample can never exceed the draws actually supplied, and the omission facts
    # are bounded by that sample.
    assert result["position_digits"]["0"]["frequency"] <= result["position_stats_sample_size"]
    assert result["position_digits"]["0"]["max_omission"] <= result["position_stats_sample_size"]

    empty = wb.query_number("006", [], 30)
    assert empty["position_stats_window"] == 30
    assert empty["position_stats_sample_size"] == 0

    with pytest.raises(ValueError):
        wb.query_number("006", draws, 90)


def test_filter_candidates_applies_every_condition_and_preserves_order():
    wb = workbench()
    filters = {
        "sum_min": 1,
        "sum_max": 1,
        "span_min": 1,
        "span_max": 1,
        "types": ["组三"],
        "odd_counts": [1],
        "big_counts": [0],
        "position_include": {"2": [1]},
        "position_exclude": {"0": [1]},
        "max_results": 10,
    }
    original = copy.deepcopy(filters)

    result = wb.filter_candidates(filters)

    assert filters == original
    assert result["total"] == 1
    assert [candidate["number_text"] for candidate in result["candidates"]] == ["001"]
    assert result["candidates"][0]["numbers"] == [0, 0, 1]
    assert result["candidates"][0]["attributes"]["number_text"] == "001"


def test_filter_candidates_counts_total_before_limit_and_keeps_leading_zeroes():
    wb = workbench()
    limited = wb.filter_candidates({"max_results": 5})

    assert limited["total"] == 1000
    assert [candidate["number_text"] for candidate in limited["candidates"]] == [
        "000",
        "001",
        "002",
        "003",
        "004",
    ]
    assert limited["candidates"][0]["numbers"] == [0, 0, 0]
    assert limited["candidates"][0]["attributes"]["group_type"] == "豹子"

    maxed = wb.filter_candidates({"max_results": 200})
    assert maxed["total"] == 1000
    assert len(maxed["candidates"]) == 200
    assert maxed["candidates"][-1]["number_text"] == "199"


def test_filter_candidates_conflicts_return_empty_and_invalid_filters_raise():
    wb = workbench()

    assert wb.filter_candidates({"sum_min": 10, "sum_max": 9}) == {
        "filters": {
            "sum_min": 10,
            "sum_max": 9,
            "span_min": 0,
            "span_max": 9,
            "types": ["豹子", "组三", "组六"],
            "odd_counts": [0, 1, 2, 3],
            "big_counts": [0, 1, 2, 3],
            "position_include": {},
            "position_exclude": {},
            "max_results": 100,
        },
        "total": 0,
        "candidates": [],
    }
    assert wb.filter_candidates(
        {"position_include": {"0": [1]}, "position_exclude": {"0": [1]}}
    )["candidates"] == []

    invalid_filters = [
        None,
        [],
        "max_results=1",
        True,
        {"unknown": 1},
        {"sum_min": -1},
        {"sum_max": 28},
        {"span_min": -1},
        {"span_max": 10},
        {"types": ["组三", "bad"]},
        {"types": "组三"},
        {"odd_counts": [4]},
        {"big_counts": [True]},
        {"position_include": {0: [1]}},
        {"position_include": {"3": [1]}},
        {"position_include": {"0": [10]}},
        {"position_exclude": {"0": [False]}},
        {"position_exclude": []},
        {"max_results": 0},
        {"max_results": 201},
        {"max_results": True},
    ]
    for filters in invalid_filters:
        with pytest.raises(ValueError, match="invalid 3d data"):
            wb.filter_candidates(filters)


def test_workbench_summary_combines_stats_distributions_and_does_not_mutate_draws():
    wb = workbench()
    draws = [
        draw([1, 2, 3], issue="003", draw_date="2026-01-03"),
        draw([1, 1, 2], issue="002", draw_date="2026-01-02"),
        draw([7, 7, 7], issue="001", draw_date="2026-01-01"),
    ]
    original = copy.deepcopy(draws)

    summary = wb.build_workbench_summary(draws, 30)

    assert draws == original
    assert summary["window"] == 30
    assert summary["sample_size"] == 3
    assert summary["latest_draw"] == {
        "issue": "003",
        "draw_date": "2026-01-03",
        "numbers": [1, 2, 3],
        "number_text": "123",
        "attributes": wb.number_attributes([1, 2, 3]),
    }
    assert summary["freshness"] == summary["position_stats"]["freshness"]
    assert summary["freshness"] is not summary["position_stats"]["freshness"]
    summary["freshness"]["status"] = "mutated"
    assert summary["position_stats"]["freshness"]["status"] == "available"
    assert summary["position_stats"]["sample_size"] == 3
    assert labels(summary["attribute_distributions"]["group_type"]) == {
        "豹子": 1,
        "组三": 1,
        "组六": 1,
    }
    assert values(summary["attribute_distributions"]["sum"])[6] == 1
    assert values(summary["attribute_distributions"]["span"])[0] == 1
    assert "不代表未来概率" in summary["definition"]
    assert "工作台" not in summary["definition"]
