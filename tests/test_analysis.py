from lottery_luck.analysis import (
    analyze_number_pool,
    backtest_strategy,
    build_analysis_payload,
    build_draw_calendar,
    compare_backtest_strategies,
    filter_candidates,
    normalize_window,
)


def test_normalize_window_accepts_only_supported_windows():
    assert normalize_window(None) == 30
    assert normalize_window("60") == 60
    assert normalize_window(120) == 120
    assert normalize_window("999") == 30
    assert normalize_window("bad") == 30


def test_analysis_payload_calculates_hot_cold_and_omission_for_ssq_sample():
    draws = [
        {
            "issue": "003",
            "draw_date": "2026-06-10",
            "red_numbers": "01,02,03,04,05,06",
            "blue_number": "07",
        },
        {
            "issue": "002",
            "draw_date": "2026-06-08",
            "red_numbers": "01,02,03,07,08,09",
            "blue_number": "08",
        },
        {
            "issue": "001",
            "draw_date": "2026-06-06",
            "red_numbers": "10,11,12,13,14,15",
            "blue_number": "07",
        },
    ]

    payload = build_analysis_payload("ssq", draws, 30)

    assert payload["summary"] == {
        "draw_count": 3,
        "latest_issue": "003",
        "latest_date": "2026-06-10",
    }
    assert payload["hot"]["main"][:3] == [
        {"number": 1, "count": 2},
        {"number": 2, "count": 2},
        {"number": 3, "count": 2},
    ]
    assert payload["hot"]["special"][0] == {"number": 7, "count": 2}
    assert payload["cold"]["main"][0] == {"number": 16, "count": 0}
    assert payload["omission"]["main"][0] == {"number": 16, "missing": 3}
    assert payload["omission"]["special"][0] == {"number": 1, "missing": 3}
    assert payload["recent_weight"]["main"][0]["number"] == 1
    assert payload["shape"]["repeat_counts"]


def test_analysis_payload_calculates_3d_position_and_shape():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "1,2,3", "blue_number": ""},
        {"issue": "002", "draw_date": "2026-06-09", "red_numbers": "1,1,2", "blue_number": ""},
        {"issue": "001", "draw_date": "2026-06-08", "red_numbers": "7,7,7", "blue_number": ""},
    ]

    payload = build_analysis_payload("3d", draws, 30)

    assert payload["position_hot"][0][0] == {"number": 1, "count": 2}
    assert payload["position_hot"][1][0] == {"number": 1, "count": 1}
    assert {"label": "组六", "count": 1} in payload["shape"]["digit_types"]
    assert {"label": "组三", "count": 1} in payload["shape"]["digit_types"]
    assert {"label": "豹子", "count": 1} in payload["shape"]["digit_types"]
    assert payload["position_cold"][0][0] == {"number": 0, "count": 0}
    assert payload["position_omission"][0][0] == {"number": 0, "missing": 3}
    assert {"label": "跨度2", "count": 1} in payload["shape"]["span"]
    assert payload["trend"]["position_columns"] == ["百位", "十位", "个位"]
    assert payload["trend"]["rows"][0]["position_hits"] == [
        {"position": "百位", "number": 1},
        {"position": "十位", "number": 2},
        {"position": "个位", "number": 3},
    ]


def test_analysis_payload_calculates_pl3_position_trend():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "1,2,3", "blue_number": ""},
        {"issue": "002", "draw_date": "2026-06-09", "red_numbers": "1,1,2", "blue_number": ""},
        {"issue": "001", "draw_date": "2026-06-08", "red_numbers": "7,7,7", "blue_number": ""},
    ]

    payload = build_analysis_payload("pl3", draws, 30)

    assert payload["position_hot"][0][0] == {"number": 1, "count": 2}
    assert payload["trend"]["position_columns"] == ["百位", "十位", "个位"]
    assert payload["trend"]["rows"][0]["position_hits"] == [
        {"position": "百位", "number": 1},
        {"position": "十位", "number": 2},
        {"position": "个位", "number": 3},
    ]


def test_analysis_payload_groups_kl8_ranges_and_recent_overlap():
    draws = [
        {
            "issue": "002",
            "draw_date": "2026-06-10",
            "red_numbers": "01,02,11,12,21,22,31,32,41,42,51,52,61,62,71,72,73,74,75,76",
            "blue_number": "",
        },
        {
            "issue": "001",
            "draw_date": "2026-06-09",
            "red_numbers": "01,02,13,14,23,24,33,34,43,44,53,54,63,64,77,78,79,80,05,06",
            "blue_number": "",
        },
    ]

    payload = build_analysis_payload(
        "kl8",
        draws,
        30,
        prediction={"main": [1, 2, 3], "special": []},
    )

    assert payload["shape"]["range_distribution"][0] == {"label": "01-10", "count": 6}
    assert {"label": "2个重号", "count": 1} in payload["shape"]["repeat_counts"]
    assert payload["recent_draws"][0]["overlap_with_prediction"] == 2
    assert payload["trend"]["columns"][0] == "01-10"
    assert payload["trend"]["rows"][0]["hits"][0] == "01-10"


def test_analysis_payload_includes_professional_metrics_for_ssq_sample():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,10,20,30", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,04,07,11,22,33", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "02,05,08,12,23,32", "blue_number": "07"},
    ]

    payload = build_analysis_payload("ssq", draws, 30)
    professional = payload["professional"]

    assert professional["ac_values"][0]["label"].startswith("AC")
    assert professional["prime_composite"][0]["label"]
    assert professional["tail_distribution"][0]["label"].startswith("尾")
    assert {row["label"] for row in professional["mod3_distribution"]} >= {"0路", "1路", "2路"}
    assert {row["label"] for row in professional["zone_distribution"]} >= {"一区", "二区", "三区"}
    assert professional["neighbor_counts"][0]["label"].endswith("邻号")
    assert {row["label"] for row in professional["omission_layers"]} >= {"高遗漏", "中遗漏", "低遗漏"}


def test_analysis_payload_returns_stable_empty_structure():
    payload = build_analysis_payload("qlc", [], 60)

    assert payload["window"] == 60
    assert payload["summary"] == {"draw_count": 0, "latest_issue": "", "latest_date": ""}
    assert payload["hot"]["main"]
    assert payload["trend"]["rows"] == []
    assert payload["recent_draws"] == []


def test_filter_candidates_applies_recent_hot_ratio_sum_and_consecutive_rules():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = filter_candidates(
        "ssq",
        draws,
        {
            "exclude_recent": 1,
            "min_hot": 1,
            "odd_even": "3:3",
            "sum_min": 80,
            "sum_max": 130,
            "max_consecutive_run": 2,
            "count": 5,
        },
    )

    assert payload["conditions"]["odd_even"] == "3:3"
    assert payload["candidates"]
    for candidate in payload["candidates"]:
        main = candidate["main"]
        assert not ({1, 2, 3, 4, 5, 6} & set(main))
        assert sum(1 for number in main if number % 2 == 1) == 3
        assert 80 <= sum(main) <= 130
        assert candidate["max_consecutive_run"] <= 2


def test_filter_candidates_applies_professional_conditions():
    draws = [
        {"issue": "004", "draw_date": "2026-06-12", "red_numbers": "01,04,07,12,22,33", "blue_number": "07"},
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,10,20,30", "blue_number": "08"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "02,05,08,11,23,32", "blue_number": "09"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "06,09,14,17,26,29", "blue_number": "10"},
    ]

    payload = filter_candidates(
        "ssq",
        draws,
        {
            "exclude_recent": 0,
            "min_hot": 1,
            "odd_even": "3:3",
            "sum_min": 60,
            "sum_max": 160,
            "max_consecutive_run": 3,
            "ac_min": 4,
            "ac_max": 12,
            "prime_composite": "2:4",
            "zone": "2:2:2",
            "tail_exclude": [0, 5],
            "count": 3,
        },
    )

    assert payload["candidates"]
    for candidate in payload["candidates"]:
        assert 4 <= candidate["ac_value"] <= 12
        assert candidate["prime_composite"] == "2:4"
        assert candidate["zone"] == "2:2:2"
        assert all(number % 10 not in {0, 5} for number in candidate["main"])
        assert "tail_pattern" in candidate


def test_backtest_strategy_returns_historical_hit_summary():
    draws = [
        {"issue": "004", "draw_date": "2026-06-12", "red_numbers": "16,17,18,19,20,21", "blue_number": "01"},
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = backtest_strategy(
        "ssq",
        draws,
        {"strategy": "hot_omission_balance", "window": 2},
    )

    assert payload["tested_draws"] == 2
    assert payload["average_main_hits"] >= 0
    assert payload["rows"][0]["issue"] == "004"
    assert "candidate" in payload["rows"][0]


def test_compare_backtest_strategies_sorts_by_average_hits():
    draws = [
        {"issue": "006", "draw_date": "2026-06-16", "red_numbers": "01,02,03,04,05,06", "blue_number": "01"},
        {"issue": "005", "draw_date": "2026-06-14", "red_numbers": "01,04,07,10,22,33", "blue_number": "02"},
        {"issue": "004", "draw_date": "2026-06-12", "red_numbers": "16,17,18,19,20,21", "blue_number": "03"},
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = compare_backtest_strategies(
        "ssq",
        draws,
        {"strategies": ["hot_omission_balance", "cold_rebound", "hot_focus"], "window": 3},
    )

    assert [row["strategy"] for row in payload["strategies"]]
    assert len(payload["strategies"]) == 3
    assert payload["strategies"][0]["average_main_hits"] >= payload["strategies"][-1]["average_main_hits"]
    assert "不代表未来结果" in payload["disclaimer"]


def test_analyze_number_pool_flags_duplicates_hot_cold_and_sum_level():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = analyze_number_pool(
        "ssq",
        draws,
        [
            {"main": [1, 2, 3, 4, 5, 6], "special": [7]},
            {"main": [1, 2, 3, 4, 5, 6], "special": [8]},
            {"main": [28, 29, 30, 31, 32, 33], "special": [16]},
        ],
    )

    assert payload["entries"][0]["duplicate_count"] == 1
    assert payload["entries"][0]["hot_hits"] >= 3
    assert payload["entries"][2]["sum_level"] == "偏高"
    assert payload["summary"]["pool_size"] == 3


def test_analyze_number_pool_adds_professional_diagnostics_and_risk_score():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = analyze_number_pool(
        "ssq",
        draws,
        [{"main": [1, 2, 3, 4, 5, 6], "special": [7]}],
    )
    entry = payload["entries"][0]

    assert "ac_value" in entry
    assert entry["prime_composite"]
    assert entry["mod3"]
    assert entry["zone"]
    assert entry["tail_pattern"]
    assert 0 <= entry["risk_score"] <= 100
    assert entry["fortune_commentary"]["wealth_type"] in {"进财", "守财", "散财"}
    assert entry["fortune_commentary"]["compatibility"] in {"相合", "略冲", "中性"}
    assert entry["fortune_commentary"]["comment"]


def test_build_draw_calendar_returns_latest_and_next_draw_dates():
    games = [
        {"game_key": "ssq", "game_name": "双色球", "latest_date": "2026-06-14", "latest_issue": "2026067"},
        {"game_key": "3d", "game_name": "福彩3D", "latest_date": "2026-06-15", "latest_issue": "2026155"},
    ]

    payload = build_draw_calendar(games, today="2026-06-17")

    assert payload["today"] == "2026-06-17"
    assert payload["games"][0]["game_key"] == "ssq"
    assert payload["games"][0]["next_draw_date"] >= "2026-06-17"
    assert payload["games"][1]["next_draw_date"] == "2026-06-17"
