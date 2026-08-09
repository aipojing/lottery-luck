from itertools import combinations, islice
from random import Random
from time import perf_counter

import pytest

from lottery_luck.number_tools import (
    ToolError,
    compose_dantuo,
    compose_digit_group,
    compose_full,
    organize_batches,
    quick_pick,
    reduce_by_budget,
    tool_config_payload,
)


def test_config_exposes_only_public_games_and_prices():
    payload = tool_config_payload()

    assert list(payload["games"]) == ["ssq", "dlt", "3d", "pl3", "kl8"]
    assert payload["games"]["ssq"]["unit_cost"] == 2
    assert payload["games"]["dlt"]["add_on_cost"] == 1
    assert payload["games"]["kl8"]["play_types"] == list(range(1, 11))


@pytest.mark.parametrize("game_key", ["ssq", "dlt", "3d", "pl3", "kl8"])
def test_quick_pick_is_valid_and_repeatable_with_injected_rng(game_key):
    options = {"play_type": 5} if game_key == "kl8" else {}

    first = quick_pick(game_key, 3, options, {}, {}, rng=Random(17))
    second = quick_pick(game_key, 3, options, {}, {}, rng=Random(17))

    assert first == second
    assert first["ticket_count"] == 3
    assert first["total_cost"] == 6
    assert len(first["entries"]) == 3
    if game_key not in {"3d", "pl3"}:
        assert all(entry["main"] == sorted(entry["main"]) for entry in first["entries"])
    else:
        assert all(len(entry["text"]) == 3 for entry in first["entries"])


def test_quick_pick_honors_locked_and_excluded_numbers():
    payload = quick_pick(
        "ssq",
        4,
        {},
        {"main": [1, 2], "special": [7]},
        {"main": [3, 4], "special": [8]},
        rng=Random(9),
    )

    assert all({1, 2}.issubset(entry["main"]) for entry in payload["entries"])
    assert all(not {3, 4}.intersection(entry["main"]) for entry in payload["entries"])
    assert all(entry["special"] == [7] for entry in payload["entries"])


def test_digit_quick_pick_honors_per_position_lock_and_exclude():
    payload = quick_pick(
        "3d",
        3,
        {},
        {"positions": [[1], [], [3]]},
        {"positions": [[], [7], []]},
        rng=Random(4),
    )

    assert all(entry["main"][0] == 1 for entry in payload["entries"])
    assert all(entry["main"][2] == 3 for entry in payload["entries"])
    assert all(entry["main"][1] != 7 for entry in payload["entries"])


def test_quick_pick_rejects_lock_exclude_conflict():
    with pytest.raises(ToolError, match="locked and excluded") as exc:
        quick_pick("ssq", 1, {}, {"main": [3]}, {"main": [3]}, rng=Random(1))

    assert exc.value.code == "locked_conflict"


@pytest.mark.parametrize("count", [0, 21, True])
def test_quick_pick_rejects_invalid_count(count):
    with pytest.raises(ToolError) as exc:
        quick_pick("ssq", count, {}, {}, {}, rng=Random(1))

    assert exc.value.code == "invalid_count"


def test_ssq_full_composition_expands_main_and_special_cartesian_product():
    payload = compose_full(
        "ssq",
        {"main": [1, 2, 3, 4, 5, 6, 7], "special": [8, 9]},
        {"multiplier": 1},
    )

    assert payload["ticket_count"] == 14
    assert payload["total_cost"] == 28
    assert len(payload["entries"]) == 14


def test_dlt_full_composition_calculates_add_on_cost():
    payload = compose_full(
        "dlt",
        {"main": [1, 2, 3, 4, 5, 6], "special": [1, 2, 3]},
        {"multiplier": 2, "add_on": True},
    )

    assert payload["ticket_count"] == 18
    assert payload["entry_cost"] == 3
    assert payload["total_cost"] == 108


def test_ssq_dantuo_keeps_dan_in_every_entry():
    payload = compose_dantuo(
        "ssq",
        {"main": [1, 2], "special": []},
        {"main": [3, 4, 5, 6, 7], "special": [8]},
        {},
    )

    assert payload["ticket_count"] == 5
    assert all({1, 2}.issubset(entry["main"]) for entry in payload["entries"])


def test_dlt_double_zone_dantuo_expands_both_zones():
    payload = compose_dantuo(
        "dlt",
        {"main": [1, 2], "special": [1]},
        {"main": [3, 4, 5, 6], "special": [2, 3]},
        {},
    )

    assert payload["ticket_count"] == 8
    assert all({1, 2}.issubset(entry["main"]) for entry in payload["entries"])
    assert all(1 in entry["special"] for entry in payload["entries"])


def test_kl8_dantuo_uses_selected_play_type():
    payload = compose_dantuo(
        "kl8",
        {"main": [1, 2]},
        {"main": [3, 4, 5, 6]},
        {"play_type": 4},
    )

    assert payload["ticket_count"] == 6
    assert all(len(entry["main"]) == 4 for entry in payload["entries"])


def test_digit_position_full_is_cartesian_product():
    payload = compose_full("3d", {"positions": [[1, 2], [3], [4, 5]]}, {})

    assert payload["ticket_count"] == 4
    assert [entry["text"] for entry in payload["entries"]] == ["134", "135", "234", "235"]


def test_digit_group_pack_counts_group3_and_group6():
    group3 = compose_digit_group("pl3", [1, 2, 3], "group3")
    group6 = compose_digit_group("pl3", [1, 2, 3, 4], "group6")

    assert group3["ticket_count"] == 3
    assert all(entry["play_type"] == "group3" for entry in group3["entries"])
    assert group6["ticket_count"] == 4
    assert all(entry["play_type"] == "group6" for entry in group6["entries"])


def test_full_composition_returns_count_but_not_entries_above_limit():
    payload = compose_full("kl8", {"main": list(range(1, 21))}, {"play_type": 10})

    assert payload["ticket_count"] == 184_756
    assert payload["entries"] == []
    assert payload["truncated"] is True
    assert "combination_limit" in payload["warnings"]
    assert "spend_limit" in payload["warnings"]


def test_composition_rejects_invalid_dan_tuo_overlap():
    with pytest.raises(ToolError) as exc:
        compose_dantuo(
            "ssq",
            {"main": [1]},
            {"main": [1, 2, 3, 4, 5, 6], "special": [7]},
            {},
        )

    assert exc.value.code == "locked_conflict"


def test_budget_reduction_is_deterministic_and_within_budget():
    source = compose_full(
        "ssq",
        {"main": [1, 2, 3, 4, 5, 6, 7, 8], "special": [9]},
        {},
    )["entries"]

    first = reduce_by_budget("ssq", source, 10, {})
    second = reduce_by_budget("ssq", list(reversed(source)), 10, {})

    assert first["entries"] == second["entries"]
    assert first["original_ticket_count"] == 28
    assert first["ticket_count"] == 5
    assert first["total_cost"] == 10
    assert set(first["coverage"]) == {f"{number:02d}" for number in range(1, 9)}
    assert "不代表中奖保证" in first["disclaimer"]


def test_budget_reduction_deduplicates_source_entries():
    entry = {"main": [1, 2, 3, 4, 5, 6], "special": [7]}

    payload = reduce_by_budget("ssq", [entry, entry], 10, {})

    assert payload["original_ticket_count"] == 1
    assert payload["ticket_count"] == 1


def test_budget_smaller_than_one_ticket_is_rejected():
    with pytest.raises(ToolError) as exc:
        reduce_by_budget(
            "ssq",
            [{"main": [1, 2, 3, 4, 5, 6], "special": [7]}],
            1,
            {},
        )

    assert exc.value.code == "budget_too_small"


def test_organizer_normalizes_deduplicates_and_intersects():
    payload = organize_batches(
        "ssq",
        "01 02 03 04 05 06 | 07\n1,2,3,4,5,6|7\n08 09 10 11 12 13 | 14",
        "01 02 03 04 05 06 | 07",
        "intersection",
        {},
    )

    assert payload["valid_a"] == 2
    assert payload["duplicates_a"] == 1
    assert [entry["text"] for entry in payload["entries"]] == [
        "01 02 03 04 05 06 | 07"
    ]


def test_digit_organizer_accepts_compact_and_spaced_forms():
    payload = organize_batches("3d", "123\n1 2 3\n908", "", "dedupe", {})

    assert payload["valid_a"] == 2
    assert payload["duplicates_a"] == 1
    assert [entry["text"] for entry in payload["entries"]] == ["123", "908"]


def test_organizer_keeps_valid_lines_and_reports_invalid_lines():
    payload = organize_batches(
        "dlt",
        "01 02 03 04 05 | 01 02\n01 02 | 03\nnot numbers",
        "",
        "dedupe",
        {},
    )

    assert payload["valid_a"] == 1
    assert [row["line"] for row in payload["invalid_a"]] == [2, 3]
    assert all(row["code"] == "invalid_number_line" for row in payload["invalid_a"])


def test_organizer_supports_union_and_difference():
    batch_a = "123\n456"
    batch_b = "456\n789"

    union = organize_batches("pl3", batch_a, batch_b, "union", {})
    difference = organize_batches("pl3", batch_a, batch_b, "difference", {})

    assert [entry["text"] for entry in union["entries"]] == ["123", "456", "789"]
    assert [entry["text"] for entry in difference["entries"]] == ["123"]


def test_budget_tools_enforce_the_total_cost_limit_boundary():
    entry = {"main": [1, 2, 3, 4, 5, 6], "special": [7]}
    assert reduce_by_budget("ssq", [entry], 20_000, {})["total_cost"] == 2
    with pytest.raises(ToolError) as exc:
        reduce_by_budget("ssq", [entry], 20_002, {})
    assert exc.value.code == "spend_limit"

    rows = [
        " ".join(f"{number:02d}" for number in main) + " | 07"
        for main in islice(combinations(range(1, 34), 6), 10_001)
    ]
    assert organize_batches("ssq", "\n".join(rows[:10_000]), "", "dedupe", {})[
        "total_cost"
    ] == 20_000
    with pytest.raises(ToolError) as exc:
        organize_batches("ssq", "\n".join(rows), "", "dedupe", {})
    assert exc.value.code == "spend_limit"


@pytest.mark.parametrize("play_type", [1, 5])
def test_kl8_budget_tools_use_the_requested_play_type(play_type):
    main = list(range(1, play_type + 1))
    entry = {"main": main, "special": []}
    text = " ".join(f"{number:02d}" for number in main)

    reduced = reduce_by_budget("kl8", [entry], 2, {"play_type": play_type})
    organized = organize_batches("kl8", text, "", "dedupe", {"play_type": play_type})

    assert reduced["entries"][0]["main"] == main
    assert organized["entries"][0]["main"] == main


def test_dlt_budget_tools_include_add_on_in_costs():
    entry = {"main": [1, 2, 3, 4, 5], "special": [1, 2]}
    reduced = reduce_by_budget("dlt", [entry], 3, {"add_on": True})
    organized = organize_batches(
        "dlt", "01 02 03 04 05 | 01 02", "", "dedupe", {"add_on": True}
    )

    assert reduced["entry_cost"] == 3
    assert reduced["total_cost"] == 3
    assert organized["entry_cost"] == 3
    assert organized["total_cost"] == 3


def test_digit_reduction_keeps_straight_order_repeats_and_group_semantics():
    group_entries = compose_digit_group("3d", [1, 2, 3], "group3")["entries"]
    source = [
        {"main": [1, 1, 2], "special": [], "play_type": "straight"},
        {"main": [1, 2, 2], "special": [], "play_type": "straight"},
        *group_entries[:1],
    ]

    payload = reduce_by_budget("3d", source, 6, {})

    assert payload["ticket_count"] == 3
    assert {entry["text"] for entry in payload["entries"]} >= {"112", "122"}
    assert any(entry["play_type"] == "group3" for entry in payload["entries"])
    assert any(entry["main"] == [1, 1, 2] for entry in payload["entries"])


def test_dlt_dantuo_allows_a_full_zone_without_dan():
    payload = compose_dantuo(
        "dlt",
        {"main": [], "special": [1]},
        {"main": [2, 3, 4, 5, 6, 7], "special": [2, 3]},
        {},
    )

    assert payload["ticket_count"] == 12
    assert all(entry["special"] == [1, 2] or entry["special"] == [1, 3] for entry in payload["entries"])


def test_dantuo_rejects_tuo_when_dan_already_fills_a_zone():
    with pytest.raises(ToolError) as exc:
        compose_dantuo(
            "dlt",
            {"main": [1], "special": [1, 2]},
            {"main": [2, 3, 4, 5], "special": [3]},
            {},
        )

    assert exc.value.code == "selection_too_large"


def test_dlt_reduction_scores_and_reports_both_number_zones():
    payload = reduce_by_budget(
        "dlt",
        [
            {"main": [1, 2, 3, 4, 5], "special": [1, 2]},
            {"main": [6, 7, 8, 9, 10], "special": [3, 4]},
        ],
        4,
        {},
    )

    assert payload["ticket_count"] == 2
    assert payload["coverage_by_zone"]["main"] == {
        "01": 1,
        "02": 1,
        "03": 1,
        "04": 1,
        "05": 1,
        "06": 1,
        "07": 1,
        "08": 1,
        "09": 1,
        "10": 1,
    }
    assert payload["coverage_by_zone"]["special"] == {"01": 1, "02": 1, "03": 1, "04": 1}


def test_truncated_full_composition_exposes_compact_source_for_budget_reduction():
    composed = compose_full(
        "ssq",
        {"main": list(range(1, 16)), "special": [1]},
        {},
    )

    reduced = reduce_by_budget(
        "ssq",
        [],
        20,
        {},
        source=composed["reduction_source"],
    )

    assert composed["ticket_count"] == 5_005
    assert composed["entries"] == []
    assert composed["truncated"] is True
    assert composed["reduction_source"] == {
        "kind": "full",
        "selection": {"main": list(range(1, 16)), "special": [1]},
        "options": {"multiplier": 1},
    }
    assert reduced["original_ticket_count"] == 5_005
    assert reduced["ticket_count"] == 10
    assert reduced["total_cost"] == 20
    assert len(reduced["entries"]) == 10


def test_budget_reduction_uses_bounded_selection_for_nearly_full_compact_source():
    composed = compose_full(
        "ssq",
        {"main": list(range(1, 16)), "special": [1]},
        {},
    )

    started_at = perf_counter()
    reduced = reduce_by_budget(
        "ssq",
        [],
        20_000,
        {},
        source=composed["reduction_source"],
    )
    elapsed = perf_counter() - started_at

    assert elapsed < 5
    assert reduced["original_ticket_count"] == 5_005
    assert reduced["ticket_count"] == 5_000
    assert reduced["total_cost"] == 10_000
    assert len(reduced["entries"]) == 5_000
    assert set(reduced["coverage_by_zone"]["main"]) == {
        f"{number:02d}" for number in range(1, 16)
    }
    assert reduced["coverage_by_zone"]["special"] == {"01": 5_000}


def test_budget_reduction_keeps_greedy_small_budget_selection_and_coverage():
    source = compose_full(
        "ssq",
        {"main": list(range(1, 9)), "special": [9]},
        {},
    )["entries"]

    reduced = reduce_by_budget("ssq", source, 10, {})

    assert [entry["text"] for entry in reduced["entries"]] == [
        "01 02 05 06 07 08 | 09",
        "02 03 04 06 07 08 | 09",
        "02 03 05 06 07 08 | 09",
        "02 04 05 06 07 08 | 09",
        "03 04 05 06 07 08 | 09",
    ]
    assert reduced["coverage_by_zone"] == {
        "main": {
            "01": 1,
            "02": 4,
            "03": 3,
            "04": 3,
            "05": 4,
            "06": 5,
            "07": 5,
            "08": 5,
        },
        "special": {"09": 5},
    }


def test_dlt_dantuo_requires_at_least_one_dan_across_both_zones():
    with pytest.raises(ToolError) as exc:
        compose_dantuo(
            "dlt",
            {"main": [], "special": []},
            {"main": [1, 2, 3, 4, 5], "special": [1, 2]},
            {},
        )

    assert exc.value.code == "selection_too_small"


def test_digit_group_rejects_spend_over_limit_in_pure_domain_call():
    with pytest.raises(ToolError) as exc:
        compose_digit_group("3d", list(range(10)), "group6", {"multiplier": 99})

    assert exc.value.code == "spend_limit"
