from lottery_luck.rules import GAME_RULES, RESERVED_GAME_RULES, candidate_draw_dates, parse_numbers


def test_parse_numbers_for_all_games():
    assert parse_numbers("ssq", "04,19,27,29,30,32", "13") == {
        "main": [4, 19, 27, 29, 30, 32],
        "special": [13],
    }
    assert parse_numbers("3d", "4,0,9", "") == {"main": [4, 0, 9], "special": []}
    assert parse_numbers("qlc", "10,11,12,13,14,15,17", "06") == {
        "main": [10, 11, 12, 13, 14, 15, 17],
        "special": [6],
    }
    assert len(
        parse_numbers(
            "kl8",
            "07,10,11,12,17,18,24,27,30,31,32,34,42,49,54,59,64,65,71,72",
            "",
        )["main"]
    ) == 20
    assert parse_numbers("dlt", "01,02,03,04,05", "06,07") == {
        "main": [1, 2, 3, 4, 5],
        "special": [6, 7],
    }
    assert parse_numbers("pl3", "7,7,7", "") == {"main": [7, 7, 7], "special": []}
    assert parse_numbers("pl5", "1,2,3,4,5", "") == {
        "main": [1, 2, 3, 4, 5],
        "special": [],
    }


def test_game_rules_include_ranges_and_pick_counts():
    assert GAME_RULES["ssq"].main_range == range(1, 34)
    assert GAME_RULES["ssq"].main_count == 6
    assert GAME_RULES["3d"].allow_repeat is True
    assert GAME_RULES["kl8"].main_count == 10


def test_sports_lottery_rules_are_active():
    assert set(GAME_RULES) == {"ssq", "3d", "qlc", "kl8", "dlt", "pl3", "pl5"}
    assert RESERVED_GAME_RULES == {}
    assert GAME_RULES["dlt"].provider == "sports"
    assert GAME_RULES["dlt"].main_range == range(1, 36)
    assert GAME_RULES["dlt"].main_count == 5
    assert GAME_RULES["dlt"].special_range == range(1, 13)
    assert GAME_RULES["dlt"].special_count == 2
    assert GAME_RULES["pl3"].provider == "sports"
    assert GAME_RULES["pl3"].allow_repeat is True
    assert GAME_RULES["pl5"].provider == "sports"
    assert GAME_RULES["pl5"].allow_repeat is True
    assert GAME_RULES["pl5"].main_count == 5


def test_candidate_draw_dates_follow_game_schedule():
    dates = candidate_draw_dates("ssq", "2026-06-15", 7)
    assert [d.weekday() for d in dates] == [1, 3, 6]
    qlc_dates = candidate_draw_dates("qlc", "2026-06-15", 7)
    assert [d.weekday() for d in qlc_dates] == [0, 2, 4]
    dlt_dates = candidate_draw_dates("dlt", "2026-06-15", 7)
    assert [d.weekday() for d in dlt_dates] == [0, 2, 5]
