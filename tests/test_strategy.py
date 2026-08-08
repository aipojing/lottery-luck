from lottery_luck.strategy import (
    STRATEGY_PRESETS,
    backtest_strategy_lab,
    compare_strategy_presets,
    generate_strategy_candidates,
)


def _ssq_draws():
    return [
        {"issue": "008", "draw_date": "2026-06-20", "red_numbers": "01,04,09,16,27,32", "blue_number": "06"},
        {"issue": "007", "draw_date": "2026-06-18", "red_numbers": "03,08,12,19,24,31", "blue_number": "11"},
        {"issue": "006", "draw_date": "2026-06-16", "red_numbers": "02,06,14,17,22,33", "blue_number": "01"},
        {"issue": "005", "draw_date": "2026-06-14", "red_numbers": "01,07,11,18,25,29", "blue_number": "13"},
        {"issue": "004", "draw_date": "2026-06-12", "red_numbers": "05,09,15,21,28,30", "blue_number": "02"},
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "02,04,10,20,26,32", "blue_number": "08"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "06,13,17,23,27,31", "blue_number": "09"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "03,05,08,14,22,33", "blue_number": "16"},
    ]


def test_strategy_presets_are_available_for_strategy_lab():
    assert set(STRATEGY_PRESETS) == {"conservative", "balanced", "aggressive"}
    assert STRATEGY_PRESETS["balanced"]["label"] == "均衡型"
    assert STRATEGY_PRESETS["conservative"]["conditions"]["max_consecutive_run"] == 2


def test_generate_strategy_candidates_returns_candidates_diagnostics_and_baseline():
    payload = generate_strategy_candidates(
        "ssq",
        _ssq_draws(),
        {"preset": "balanced", "candidate_count": 5},
    )

    assert payload["game_key"] == "ssq"
    assert payload["preset"] == "balanced"
    assert payload["strategy_name"] == "均衡型"
    assert payload["conditions"]["count"] == 5
    assert payload["candidates"]
    assert len(payload["baseline"]["candidates"]) == 5
    assert payload["diagnostics"]["condition_count"] >= 4
    assert "不构成投注建议" in payload["disclaimer"]


def test_generate_strategy_candidates_applies_custom_condition_overrides():
    payload = generate_strategy_candidates(
        "ssq",
        _ssq_draws(),
        {
            "preset": "balanced",
            "candidate_count": 3,
            "conditions": {"tail_exclude": [0], "ac_min": 4},
        },
    )

    assert payload["conditions"]["tail_exclude"] == [0]
    assert payload["conditions"]["ac_min"] == 4
    assert payload["candidates"]
    for candidate in payload["candidates"]:
        assert candidate["ac_value"] >= 4
        assert all(number % 10 != 0 for number in candidate["main"])


def test_backtest_strategy_lab_returns_distribution_and_random_baseline():
    payload = backtest_strategy_lab(
        "ssq",
        _ssq_draws(),
        {"preset": "balanced", "window": 3, "candidate_count": 1},
    )

    assert payload["tested_draws"] == 3
    assert payload["average_main_hits"] >= 0
    assert payload["baseline_average_main_hits"] >= 0
    assert payload["hit_distribution"]
    assert sum(row["count"] for row in payload["hit_distribution"]) == 3
    assert payload["rows"][0]["baseline_candidate"]["main"]
    assert "不代表未来结果" in payload["disclaimer"]


def test_compare_strategy_presets_sorts_by_average_hits():
    payload = compare_strategy_presets(
        "ssq",
        _ssq_draws(),
        {"window": 3, "candidate_count": 1},
    )

    assert len(payload["strategies"]) == 3
    assert payload["strategies"][0]["average_main_hits"] >= payload["strategies"][-1]["average_main_hits"]
    assert {row["preset"] for row in payload["strategies"]} == {"conservative", "balanced", "aggressive"}
