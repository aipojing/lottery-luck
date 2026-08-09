from __future__ import annotations

from copy import deepcopy
from itertools import combinations, product
from math import comb, prod
from secrets import SystemRandom
from typing import Any, Protocol


PUBLIC_TOOL_GAMES = ("ssq", "dlt", "3d", "pl3", "kl8")
MAX_GENERATED_TICKETS = 5_000
MAX_TOTAL_COST = 20_000
# Compact reduction sources may be expanded transiently on the server, never in
# the browser or local storage.  This is intentionally below unbounded input.
MAX_REDUCTION_SOURCE_TICKETS = 50_000
# The exact greedy scorer is useful for small selections, but rescoring every
# remaining ticket for thousands of selections is needlessly quadratic.
MAX_EXACT_REDUCTION_STEPS = 128

GAME_TOOL_CONFIG: dict[str, dict[str, Any]] = {
    "ssq": {
        "name": "双色球",
        "main": (1, 33, 6),
        "special": (1, 16, 1),
        "unit_cost": 2,
    },
    "dlt": {
        "name": "大乐透",
        "main": (1, 35, 5),
        "special": (1, 12, 2),
        "unit_cost": 2,
        "add_on_cost": 1,
    },
    "3d": {
        "name": "福彩3D",
        "positions": 3,
        "digits": (0, 9),
        "unit_cost": 2,
    },
    "pl3": {
        "name": "排列3",
        "positions": 3,
        "digits": (0, 9),
        "unit_cost": 2,
    },
    "kl8": {
        "name": "快乐8",
        "main": (1, 80, 10),
        "play_types": tuple(range(1, 11)),
        "unit_cost": 2,
    },
}


class RandomSource(Protocol):
    def sample(self, population: Any, k: int) -> list[Any]: ...

    def choice(self, seq: Any) -> Any: ...


class ToolError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def tool_config_payload() -> dict[str, Any]:
    games: dict[str, Any] = {}
    for game_key in PUBLIC_TOOL_GAMES:
        source = GAME_TOOL_CONFIG[game_key]
        game: dict[str, Any] = {
            "key": game_key,
            "name": source["name"],
            "unit_cost": source["unit_cost"],
        }
        if "main" in source:
            minimum, maximum, count = source["main"]
            game["main"] = {"min": minimum, "max": maximum, "count": count}
        if "special" in source:
            minimum, maximum, count = source["special"]
            game["special"] = {"min": minimum, "max": maximum, "count": count}
        if "positions" in source:
            minimum, maximum = source["digits"]
            game["positions"] = source["positions"]
            game["digits"] = {"min": minimum, "max": maximum}
        if "play_types" in source:
            game["play_types"] = list(source["play_types"])
        if "add_on_cost" in source:
            game["add_on_cost"] = source["add_on_cost"]
        games[game_key] = game
    return {
        "games": games,
        "limits": {
            "max_generated_tickets": MAX_GENERATED_TICKETS,
            "max_total_cost": MAX_TOTAL_COST,
            "max_basket_entries": 500,
        },
        "tools": ["quick", "lock", "full", "dantuo", "reduce", "organize"],
        "disclaimer": "仅供娱乐和号码组织参考，不构成投注建议。",
    }


def normalize_options(game_key: str, options: dict[str, Any] | None) -> dict[str, Any]:
    config = _require_game(game_key)
    raw = options or {}
    if type(raw) is not dict:
        raise ToolError("invalid_options", "options must be an object")

    multiplier = raw.get("multiplier", 1)
    if type(multiplier) is not int or multiplier < 1 or multiplier > 99:
        raise ToolError("invalid_multiplier", "multiplier must be between 1 and 99")

    normalized: dict[str, Any] = {"multiplier": multiplier}
    if game_key == "dlt":
        add_on = raw.get("add_on", False)
        if type(add_on) is not bool:
            raise ToolError("invalid_options", "add_on must be a boolean")
        normalized["add_on"] = add_on
    if game_key == "kl8":
        play_type = raw.get("play_type", config["main"][2])
        if type(play_type) is not int or play_type not in config["play_types"]:
            raise ToolError("invalid_play_type", "快乐8玩法必须为选一至选十")
        normalized["play_type"] = play_type
    return normalized


def quick_pick(
    game_key: str,
    count: int,
    options: dict[str, Any] | None,
    locked: dict[str, Any] | None,
    excluded: dict[str, Any] | None,
    *,
    rng: RandomSource | None = None,
) -> dict[str, Any]:
    config = _require_game(game_key)
    if type(count) is not int or count < 1 or count > 20:
        raise ToolError("invalid_count", "count must be between 1 and 20")
    normalized_options = normalize_options(game_key, options)
    random_source = rng or SystemRandom()

    if "positions" in config:
        entries = _quick_digit_entries(
            game_key,
            count,
            config,
            locked or {},
            excluded or {},
            random_source,
        )
    else:
        entries = _quick_lotto_entries(
            game_key,
            count,
            config,
            normalized_options,
            locked or {},
            excluded or {},
            random_source,
        )
    return _result_payload(game_key, "quick", entries, normalized_options)


def compose_full(
    game_key: str,
    selection: dict[str, Any],
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    config = _require_game(game_key)
    if type(selection) is not dict:
        raise ToolError("invalid_selection", "selection must be an object")
    normalized_options = normalize_options(game_key, options)

    if "positions" in config:
        positions = _normalize_composition_positions(selection.get("positions"), config)
        ticket_count = prod(len(position) for position in positions)
        if _should_expand(game_key, ticket_count, normalized_options):
            entries = [
                _normalize_entry(game_key, list(digits), [])
                for digits in product(*positions)
            ]
        else:
            entries = []
        return _composition_payload(
            game_key,
            "full",
            ticket_count,
            entries,
            normalized_options,
            reduction_source={
                "kind": "full",
                "selection": {"positions": positions},
                "options": normalized_options,
            },
        )

    main_min, main_max, default_main_count = config["main"]
    main_count = normalized_options.get("play_type", default_main_count)
    selected_main = _normalize_number_list(selection.get("main", []), main_min, main_max)
    if len(selected_main) < main_count:
        raise ToolError("selection_too_small", "select more main numbers")
    main_ticket_count = comb(len(selected_main), main_count)

    selected_special: list[int] = []
    special_count = config.get("special", (0, -1, 0))[2]
    special_ticket_count = 1
    if special_count:
        special_min, special_max, _ = config["special"]
        selected_special = _normalize_number_list(
            selection.get("special", []), special_min, special_max
        )
        if len(selected_special) < special_count:
            raise ToolError("selection_too_small", "select more special numbers")
        special_ticket_count = comb(len(selected_special), special_count)

    ticket_count = main_ticket_count * special_ticket_count
    entries: list[dict[str, Any]] = []
    if _should_expand(game_key, ticket_count, normalized_options):
        main_entries = combinations(selected_main, main_count)
        special_entries: Any = (
            list(combinations(selected_special, special_count))
            if special_count
            else [tuple()]
        )
        entries = [
            _normalize_entry(game_key, list(main), list(special))
            for main in main_entries
            for special in special_entries
        ]
    return _composition_payload(
        game_key,
        "full",
        ticket_count,
        entries,
        normalized_options,
        reduction_source={
            "kind": "full",
            "selection": {"main": selected_main, "special": selected_special},
            "options": normalized_options,
        },
    )


def compose_dantuo(
    game_key: str,
    dan: dict[str, Any],
    tuo: dict[str, Any],
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    config = _require_game(game_key)
    if "positions" in config:
        raise ToolError("invalid_play_type", "数字彩请使用组选包号或定位复式")
    if type(dan) is not dict or type(tuo) is not dict:
        raise ToolError("invalid_selection", "dan and tuo must be objects")
    normalized_options = normalize_options(game_key, options)

    main_min, main_max, default_main_count = config["main"]
    main_count = normalized_options.get("play_type", default_main_count)
    dan_main = _normalize_number_list(dan.get("main", []), main_min, main_max)
    tuo_main = _normalize_number_list(tuo.get("main", []), main_min, main_max)
    _require_disjoint(dan_main, tuo_main, "main")
    main_ticket_count = _dantuo_count(
        dan_main,
        tuo_main,
        main_count,
        label="main",
        # 大乐透允许只在后区设胆码；前区此时按普通复式展开。
        require_dan=game_key != "dlt",
    )

    special_count = config.get("special", (0, -1, 0))[2]
    special_ticket_count = 1
    dan_special: list[int] = []
    tuo_special: list[int] = []
    if special_count:
        special_min, special_max, _ = config["special"]
        dan_special = _normalize_number_list(
            dan.get("special", []), special_min, special_max
        )
        tuo_special = _normalize_number_list(
            tuo.get("special", []), special_min, special_max
        )
        _require_disjoint(dan_special, tuo_special, "special")
        special_ticket_count = _dantuo_count(
            dan_special,
            tuo_special,
            special_count,
            label="special",
            require_dan=False,
        )

    if game_key == "dlt" and not dan_main and not dan_special:
        raise ToolError("selection_too_small", "大乐透胆拖至少选择一个胆码")

    ticket_count = main_ticket_count * special_ticket_count
    entries: list[dict[str, Any]] = []
    if _should_expand(game_key, ticket_count, normalized_options):
        main_combinations = _dantuo_combinations(dan_main, tuo_main, main_count)
        special_combinations = (
            _dantuo_combinations(dan_special, tuo_special, special_count)
            if special_count
            else [tuple()]
        )
        entries = [
            _normalize_entry(game_key, list(main), list(special))
            for main in main_combinations
            for special in special_combinations
        ]
    return _composition_payload(
        game_key,
        "dantuo",
        ticket_count,
        entries,
        normalized_options,
        reduction_source={
            "kind": "dantuo",
            "dan": {"main": dan_main, "special": dan_special},
            "tuo": {"main": tuo_main, "special": tuo_special},
            "options": normalized_options,
        },
    )


def compose_digit_group(
    game_key: str,
    digits: list[int],
    group_type: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _require_game(game_key)
    if game_key not in {"3d", "pl3"}:
        raise ToolError("invalid_play_type", "组选包号仅支持福彩3D和排列3")
    if group_type not in {"group3", "group6"}:
        raise ToolError("invalid_play_type", "group_type must be group3 or group6")
    minimum, maximum = config["digits"]
    selected = _normalize_number_list(digits, minimum, maximum)
    pick_count = 2 if group_type == "group3" else 3
    if len(selected) < pick_count:
        raise ToolError("selection_too_small", f"{group_type} requires more digits")
    normalized_options = normalize_options(game_key, options)
    ticket_count = comb(len(selected), pick_count)
    if ticket_count_and_cost(game_key, ticket_count, normalized_options)["total_cost"] > MAX_TOTAL_COST:
        raise ToolError("spend_limit", "total cost exceeds the limit")
    raw_entries = list(combinations(selected, pick_count))
    entries: list[dict[str, Any]] = []
    for numbers in raw_entries:
        entry = _normalize_entry(
            game_key,
            list(numbers),
            [],
            play_type=group_type,
        )
        label = "组三" if group_type == "group3" else "组六"
        entry["text"] = f"{' '.join(str(number) for number in numbers)} · {label}"
        entries.append(entry)
    return _composition_payload(
        game_key,
        group_type,
        ticket_count,
        entries,
        normalized_options,
    )


def ticket_count_and_cost(
    game_key: str,
    ticket_count: int,
    options: dict[str, Any] | None,
) -> dict[str, int]:
    config = _require_game(game_key)
    if type(ticket_count) is not int or ticket_count < 0:
        raise ToolError("invalid_count", "ticket_count must be a non-negative integer")
    normalized_options = normalize_options(game_key, options)
    entry_cost = config["unit_cost"] + (
        config.get("add_on_cost", 0) if normalized_options.get("add_on") else 0
    )
    multiplier = normalized_options["multiplier"]
    return {
        "unit_cost": config["unit_cost"],
        "entry_cost": entry_cost,
        "multiplier": multiplier,
        "total_cost": ticket_count * entry_cost * multiplier,
    }


def reduce_by_budget(
    game_key: str,
    entries: list[dict[str, Any]],
    budget: int,
    options: dict[str, Any] | None,
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select a deterministic, coverage-oriented subset within a ticket budget."""
    _require_game(game_key)
    if type(entries) is not list:
        raise ToolError("invalid_entries", "entries must be a list")
    if type(budget) is not int or budget < 0:
        raise ToolError("invalid_budget", "budget must be a non-negative integer")

    normalized_options = normalize_options(game_key, options)
    cost = ticket_count_and_cost(game_key, 1, normalized_options)
    if budget < cost["total_cost"]:
        raise ToolError("budget_too_small", "budget is smaller than one ticket")
    if budget > MAX_TOTAL_COST:
        raise ToolError("spend_limit", "budget exceeds the total cost limit")

    canonical = (
        _expand_compact_reduction_source(game_key, source)
        if source is not None
        else _canonicalize_entries(game_key, entries, normalized_options)
    )
    max_entries = min(budget // cost["total_cost"], MAX_GENERATED_TICKETS)
    selected = _select_reduction_entries(game_key, canonical, max_entries)
    frequencies: dict[tuple[str, int], int] = {}
    for choice in selected:
        for number in _coverage_tokens(game_key, choice):
            frequencies[number] = frequencies.get(number, 0) + 1

    selected.sort(key=_entry_identity)
    coverage_by_zone: dict[str, dict[str, int]] = {}
    for (zone, number), count in sorted(frequencies.items()):
        coverage_by_zone.setdefault(zone, {})[f"{number:02d}"] = count
    # Keep the original flat main-zone field for existing clients while exposing
    # every zone explicitly.  The greedy scoring above always uses all zones.
    coverage = coverage_by_zone.get("main", next(iter(coverage_by_zone.values()), {}))
    payload = _result_payload(game_key, "reduce", selected, normalized_options)
    payload.update(
        {
            "original_ticket_count": len(canonical),
            "selected_ticket_count": len(selected),
            "reduction_ratio": (len(canonical) - len(selected)) / len(canonical)
            if canonical
            else 0,
            "budget": budget,
            "coverage": coverage,
            "coverage_by_zone": coverage_by_zone,
            "disclaimer": "仅按预算和组合分布缩减，不代表中奖保证；未选组合仍可能包含开奖号码。",
        }
    )
    return payload


def _select_reduction_entries(
    game_key: str,
    canonical: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    """Choose a deterministic subset without quadratic work near the limit."""
    if target_count <= 0 or not canonical:
        return []
    if target_count >= len(canonical):
        return list(canonical)

    omitted_count = len(canonical) - target_count
    if target_count <= MAX_EXACT_REDUCTION_STEPS:
        return _greedy_reduction_selection(game_key, canonical, target_count)
    if omitted_count <= MAX_EXACT_REDUCTION_STEPS:
        return _greedy_reduction_complement(game_key, canonical, omitted_count)
    return _stratified_reduction_selection(game_key, canonical, target_count)


def _greedy_reduction_selection(
    game_key: str,
    canonical: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    """Keep the original coverage scorer where its bounded work is useful."""
    selected: list[dict[str, Any]] = []
    selected_numbers: set[tuple[str, int]] = set()
    frequencies: dict[tuple[str, int], int] = {}
    remaining = list(canonical)

    while remaining and len(selected) < target_count:
        def score(entry: dict[str, Any]) -> tuple[int, int, int, str]:
            numbers = _coverage_tokens(game_key, entry)
            overlap = len(numbers.intersection(selected_numbers))
            max_frequency = max(
                (frequencies.get(number, 0) for number in numbers), default=0
            )
            return (
                len(numbers - selected_numbers),
                -overlap,
                -max_frequency,
                _entry_identity(entry),
            )

        choice = max(remaining, key=score)
        remaining.remove(choice)
        selected.append(choice)
        selected_numbers.update(_coverage_tokens(game_key, choice))
        for number in _coverage_tokens(game_key, choice):
            frequencies[number] = frequencies.get(number, 0) + 1

    return selected


def _greedy_reduction_complement(
    game_key: str,
    canonical: list[dict[str, Any]],
    omitted_count: int,
) -> list[dict[str, Any]]:
    """Remove only the few tickets omitted by an almost-full reduction."""
    remaining = list(canonical)
    frequencies: dict[tuple[str, int], int] = {}
    for entry in remaining:
        for number in _coverage_tokens(game_key, entry):
            frequencies[number] = frequencies.get(number, 0) + 1

    for _ in range(omitted_count):
        def score(entry: dict[str, Any]) -> tuple[int, int, str]:
            numbers = _coverage_tokens(game_key, entry)
            return (
                min(frequencies[number] for number in numbers),
                sum(frequencies[number] for number in numbers),
                _entry_identity(entry),
            )

        choice = max(remaining, key=score)
        remaining.remove(choice)
        for number in _coverage_tokens(game_key, choice):
            frequencies[number] -= 1

    return remaining


def _stratified_reduction_selection(
    game_key: str,
    canonical: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    """Use a linear, coverage-seeded sample for large middle-size budgets."""
    anchors: list[dict[str, Any]] = []
    anchor_ids: set[str] = set()
    covered: set[tuple[str, int]] = set()
    for entry in canonical:
        numbers = _coverage_tokens(game_key, entry)
        if numbers - covered:
            anchors.append(entry)
            anchor_ids.add(_entry_identity(entry))
            covered.update(numbers)
            if len(anchors) == target_count:
                return anchors

    available = [
        entry for entry in canonical if _entry_identity(entry) not in anchor_ids
    ]
    remaining_slots = target_count - len(anchors)
    if remaining_slots <= 0:
        return anchors
    sampled = [
        available[(index * len(available)) // remaining_slots]
        for index in range(remaining_slots)
    ]
    return anchors + sampled


def organize_batches(
    game_key: str,
    batch_a: str,
    batch_b: str,
    operation: str,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Parse two text batches and apply a set operation to their tickets."""
    _require_game(game_key)
    if type(batch_a) is not str or type(batch_b) is not str:
        raise ToolError("invalid_batch", "batches must be strings")
    if operation not in {"dedupe", "union", "intersection", "difference"}:
        raise ToolError("invalid_operation", "unsupported batch operation")
    normalized_options = normalize_options(game_key, options)
    entries_a, invalid_a, duplicates_a = _parse_batch(
        game_key, batch_a, normalized_options
    )
    entries_b, invalid_b, duplicates_b = _parse_batch(
        game_key, batch_b, normalized_options
    )
    index_a = {entry["text"]: entry for entry in entries_a}
    index_b = {entry["text"]: entry for entry in entries_b}

    if operation == "dedupe":
        selected = index_a
    elif operation == "union":
        selected = {**index_a, **index_b}
    elif operation == "intersection":
        selected = {text: entry for text, entry in index_a.items() if text in index_b}
    else:
        selected = {text: entry for text, entry in index_a.items() if text not in index_b}

    entries_out = [selected[text] for text in sorted(selected)]
    payload = _result_payload(game_key, "organize", entries_out, normalized_options)
    if payload["total_cost"] > MAX_TOTAL_COST:
        raise ToolError("spend_limit", "total cost exceeds the limit")
    payload.update(
        {
            "operation": operation,
            "valid_a": len(entries_a),
            "valid_b": len(entries_b),
            "duplicates_a": duplicates_a,
            "duplicates_b": duplicates_b,
            "invalid_a": invalid_a,
            "invalid_b": invalid_b,
        }
    )
    return payload


def _require_game(game_key: str) -> dict[str, Any]:
    if game_key not in PUBLIC_TOOL_GAMES:
        raise ToolError("invalid_game", "unsupported lottery game")
    return GAME_TOOL_CONFIG[game_key]


def _canonicalize_entries(
    game_key: str,
    entries: list[dict[str, Any]],
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if type(entry) is not dict:
            raise ToolError("invalid_entry", "each entry must be an object")
        try:
            play_type = entry.get("play_type", "straight")
            if game_key in {"3d", "pl3"} and play_type in {"group3", "group6"}:
                normalized = _normalize_digit_group_entry(game_key, entry.get("main"), play_type)
            elif game_key in {"3d", "pl3"} and play_type != "straight":
                raise ToolError("invalid_play_type", "unsupported digit play type")
            else:
                normalized = _normalize_ticket_entry(
                    game_key,
                    entry.get("main"),
                    entry.get("special", []),
                    options,
                    play_type=play_type,
                )
        except ToolError as exc:
            raise ToolError("invalid_entry", exc.message) from exc
        canonical[_entry_identity(normalized)] = normalized
    return [canonical[key] for key in sorted(canonical)]


def _parse_batch(
    game_key: str,
    batch: str,
    options: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    canonical: dict[str, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    duplicates = 0
    for line_number, line in enumerate(batch.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = _parse_ticket_line(game_key, line, options)
        except ToolError:
            invalid.append({"line": line_number, "text": line, "code": "invalid_number_line"})
            continue
        if entry["text"] in canonical:
            duplicates += 1
        else:
            canonical[entry["text"]] = entry
    return [canonical[text] for text in sorted(canonical)], invalid, duplicates


def _parse_ticket_line(
    game_key: str,
    line: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    if game_key in {"3d", "pl3"}:
        compact = "".join(line.replace(",", " ").split())
        if len(compact) != 3 or not compact.isdigit():
            raise ToolError("invalid_number_line", "invalid digit ticket")
        return _normalize_ticket_entry(game_key, [int(digit) for digit in compact], [], options)

    if line.count("|") > 1:
        raise ToolError("invalid_number_line", "a ticket can have one separator")
    segments = line.split("|")
    main = _parse_number_segment(segments[0])
    special = _parse_number_segment(segments[1]) if len(segments) == 2 else []
    return _normalize_ticket_entry(game_key, main, special, options)


def _parse_number_segment(segment: str) -> list[int]:
    tokens = segment.replace(",", " ").split()
    if not tokens or any(not token.isdigit() for token in tokens):
        raise ToolError("invalid_number_line", "invalid number ticket")
    return [int(token) for token in tokens]


def _normalize_ticket_entry(
    game_key: str,
    main: Any,
    special: Any,
    options: dict[str, Any] | None = None,
    *,
    play_type: str = "straight",
) -> dict[str, Any]:
    config = _require_game(game_key)
    if "positions" in config:
        if not isinstance(main, list) or len(main) != config["positions"]:
            raise ToolError("invalid_number_line", "a digit ticket needs three positions")
        minimum, maximum = config["digits"]
        if any(type(number) is not int or number < minimum or number > maximum for number in main):
            raise ToolError("invalid_number_line", "a digit ticket contains an invalid digit")
        return _normalize_entry(game_key, list(main), [], play_type=play_type)

    main_min, main_max, default_main_count = config["main"]
    main_count = (options or {}).get("play_type", default_main_count)
    normalized_main = _normalize_number_list(main, main_min, main_max)
    if len(normalized_main) != main_count:
        raise ToolError("invalid_number_line", "incorrect main number count")
    special_count = config.get("special", (0, -1, 0))[2]
    normalized_special: list[int] = []
    if special_count:
        special_min, special_max, _ = config["special"]
        normalized_special = _normalize_number_list(special, special_min, special_max)
        if len(normalized_special) != special_count:
            raise ToolError("invalid_number_line", "incorrect special number count")
    elif special not in (None, []):
        raise ToolError("invalid_number_line", "this game has no special numbers")
    return _normalize_entry(game_key, normalized_main, normalized_special)


def _quick_lotto_entries(
    game_key: str,
    count: int,
    config: dict[str, Any],
    options: dict[str, Any],
    locked: dict[str, Any],
    excluded: dict[str, Any],
    rng: RandomSource,
) -> list[dict[str, Any]]:
    if type(locked) is not dict or type(excluded) is not dict:
        raise ToolError("invalid_selection", "locked and excluded must be objects")
    main_min, main_max, default_main_count = config["main"]
    main_count = options.get("play_type", default_main_count)
    locked_main = _normalize_number_list(locked.get("main", []), main_min, main_max)
    excluded_main = _normalize_number_list(excluded.get("main", []), main_min, main_max)
    _require_disjoint(locked_main, excluded_main, "main")
    if len(locked_main) > main_count:
        raise ToolError("selection_too_large", "locked main numbers exceed the play count")
    main_available = [
        number
        for number in range(main_min, main_max + 1)
        if number not in locked_main and number not in excluded_main
    ]
    main_needed = main_count - len(locked_main)
    if len(main_available) < main_needed:
        raise ToolError("selection_too_small", "not enough main numbers remain after exclusions")

    special_count = config.get("special", (0, -1, 0))[2]
    locked_special: list[int] = []
    special_available: list[int] = []
    if special_count:
        special_min, special_max, _ = config["special"]
        locked_special = _normalize_number_list(
            locked.get("special", []), special_min, special_max
        )
        excluded_special = _normalize_number_list(
            excluded.get("special", []), special_min, special_max
        )
        _require_disjoint(locked_special, excluded_special, "special")
        if len(locked_special) > special_count:
            raise ToolError("selection_too_large", "locked special numbers exceed the play count")
        special_available = [
            number
            for number in range(special_min, special_max + 1)
            if number not in locked_special and number not in excluded_special
        ]
        if len(special_available) < special_count - len(locked_special):
            raise ToolError("selection_too_small", "not enough special numbers remain after exclusions")

    entries: list[dict[str, Any]] = []
    for _ in range(count):
        main = sorted(locked_main + rng.sample(main_available, main_needed))
        special_needed = special_count - len(locked_special)
        special = sorted(
            locked_special + rng.sample(special_available, special_needed)
            if special_count
            else []
        )
        entries.append(_normalize_entry(game_key, main, special))
    return entries


def _quick_digit_entries(
    game_key: str,
    count: int,
    config: dict[str, Any],
    locked: dict[str, Any],
    excluded: dict[str, Any],
    rng: RandomSource,
) -> list[dict[str, Any]]:
    minimum, maximum = config["digits"]
    locked_positions = _normalize_positions(locked.get("positions", []), minimum, maximum)
    excluded_positions = _normalize_positions(excluded.get("positions", []), minimum, maximum)
    entries: list[dict[str, Any]] = []

    pools: list[list[int]] = []
    for position, locked_digits in enumerate(locked_positions):
        excluded_digits = excluded_positions[position]
        _require_disjoint(locked_digits, excluded_digits, f"position {position + 1}")
        if len(locked_digits) > 1:
            raise ToolError("selection_too_large", "each position can lock at most one digit")
        if locked_digits:
            pools.append(list(locked_digits))
            continue
        pool = [digit for digit in range(minimum, maximum + 1) if digit not in excluded_digits]
        if not pool:
            raise ToolError("selection_too_small", "a digit position has no available numbers")
        pools.append(pool)

    for _ in range(count):
        main = [rng.choice(pool) for pool in pools]
        entries.append(_normalize_entry(game_key, main, []))
    return entries


def _normalize_composition_positions(
    value: Any,
    config: dict[str, Any],
) -> list[list[int]]:
    minimum, maximum = config["digits"]
    if not isinstance(value, list) or len(value) != config["positions"]:
        raise ToolError("invalid_selection", "positions must contain three number lists")
    positions = [_normalize_number_list(numbers, minimum, maximum) for numbers in value]
    if any(not numbers for numbers in positions):
        raise ToolError("selection_too_small", "each position requires at least one digit")
    return positions


def _dantuo_combinations(
    dan: list[int],
    tuo: list[int],
    pick_count: int,
) -> list[tuple[int, ...]]:
    needed = pick_count - len(dan)
    if needed == 0:
        return [tuple(sorted(dan))]
    return [tuple(sorted(dan + list(rest))) for rest in combinations(tuo, needed)]


def _dantuo_count(
    dan: list[int],
    tuo: list[int],
    pick_count: int,
    *,
    label: str,
    require_dan: bool,
) -> int:
    if require_dan and not dan:
        raise ToolError("selection_too_small", f"{label} requires at least one dan number")
    if len(dan) > pick_count:
        raise ToolError("selection_too_large", f"too many {label} dan numbers")
    if len(dan) == pick_count:
        if tuo:
            raise ToolError("selection_too_large", f"{label} dan numbers already fill the play count")
        if require_dan:
            raise ToolError("selection_too_large", f"too many {label} dan numbers")
        return 1
    needed = pick_count - len(dan)
    if len(tuo) < needed:
        raise ToolError("selection_too_small", f"not enough {label} tuo numbers")
    if needed == 0:
        return 1
    return comb(len(tuo), needed)


def _should_expand(
    game_key: str,
    ticket_count: int,
    options: dict[str, Any],
) -> bool:
    cost = ticket_count_and_cost(game_key, ticket_count, options)
    return ticket_count <= MAX_GENERATED_TICKETS and cost["total_cost"] <= MAX_TOTAL_COST


def _composition_payload(
    game_key: str,
    tool: str,
    ticket_count: int,
    entries: list[dict[str, Any]],
    options: dict[str, Any],
    *,
    reduction_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cost = ticket_count_and_cost(game_key, ticket_count, options)
    warnings: list[str] = []
    if ticket_count > MAX_GENERATED_TICKETS:
        warnings.append("combination_limit")
    if cost["total_cost"] > MAX_TOTAL_COST:
        warnings.append("spend_limit")
    payload = {
        "game_key": game_key,
        "tool": tool,
        "ticket_count": ticket_count,
        **cost,
        "entries": deepcopy(entries),
        "truncated": bool(warnings),
        "warnings": warnings,
    }
    if reduction_source is not None:
        payload["reduction_source"] = deepcopy(reduction_source)
    return payload


def _expand_compact_reduction_source(
    game_key: str,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Expand a server-validated composition descriptor only for reduction."""
    if type(source) is not dict:
        raise ToolError("invalid_source", "reduction source must be an object")
    kind = source.get("kind")
    source_options = normalize_options(game_key, source.get("options"))
    if kind == "full":
        composed = compose_full(game_key, source.get("selection"), source_options)
    elif kind == "dantuo":
        composed = compose_dantuo(
            game_key,
            source.get("dan"),
            source.get("tuo"),
            source_options,
        )
    else:
        raise ToolError("invalid_source", "unsupported reduction source")
    if composed["ticket_count"] > MAX_REDUCTION_SOURCE_TICKETS:
        raise ToolError("combination_limit", "reduction source contains too many combinations")
    if "spend_limit" in composed["warnings"]:
        raise ToolError("spend_limit", "source total cost exceeds the limit")
    if composed["entries"]:
        return _canonicalize_entries(game_key, composed["entries"], source_options)
    normalized_source = composed["reduction_source"]
    if kind == "full":
        entries = _force_expand_full_source(
            game_key,
            normalized_source["selection"],
            source_options,
        )
    else:
        entries = _force_expand_dantuo_source(
            game_key,
            normalized_source["dan"],
            normalized_source["tuo"],
            source_options,
        )
    return _canonicalize_entries(game_key, entries, source_options)


def _force_expand_full_source(
    game_key: str,
    selection: dict[str, Any],
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    config = _require_game(game_key)
    if "positions" in config:
        positions = _normalize_composition_positions(selection.get("positions"), config)
        return [_normalize_entry(game_key, list(digits), []) for digits in product(*positions)]
    main_min, main_max, default_main_count = config["main"]
    main_count = options.get("play_type", default_main_count)
    selected_main = _normalize_number_list(selection.get("main", []), main_min, main_max)
    special_count = config.get("special", (0, -1, 0))[2]
    selected_special: list[int] = []
    if special_count:
        special_min, special_max, _ = config["special"]
        selected_special = _normalize_number_list(selection.get("special", []), special_min, special_max)
    special_entries: Any = (
        list(combinations(selected_special, special_count)) if special_count else [tuple()]
    )
    return [
        _normalize_entry(game_key, list(main), list(special))
        for main in combinations(selected_main, main_count)
        for special in special_entries
    ]


def _force_expand_dantuo_source(
    game_key: str,
    dan: dict[str, Any],
    tuo: dict[str, Any],
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    config = _require_game(game_key)
    main_min, main_max, default_main_count = config["main"]
    main_count = options.get("play_type", default_main_count)
    dan_main = _normalize_number_list(dan.get("main", []), main_min, main_max)
    tuo_main = _normalize_number_list(tuo.get("main", []), main_min, main_max)
    special_count = config.get("special", (0, -1, 0))[2]
    dan_special: list[int] = []
    tuo_special: list[int] = []
    if special_count:
        special_min, special_max, _ = config["special"]
        dan_special = _normalize_number_list(dan.get("special", []), special_min, special_max)
        tuo_special = _normalize_number_list(tuo.get("special", []), special_min, special_max)
    special_entries: Any = (
        _dantuo_combinations(dan_special, tuo_special, special_count)
        if special_count
        else [tuple()]
    )
    return [
        _normalize_entry(game_key, list(main), list(special))
        for main in _dantuo_combinations(dan_main, tuo_main, main_count)
        for special in special_entries
    ]


def _normalize_positions(value: Any, minimum: int, maximum: int) -> list[list[int]]:
    if value in (None, []):
        return [[], [], []]
    if not isinstance(value, list) or len(value) != 3:
        raise ToolError("invalid_selection", "positions must contain three number lists")
    return [_normalize_number_list(numbers, minimum, maximum) for numbers in value]


def _normalize_number_list(value: Any, minimum: int, maximum: int) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ToolError("invalid_selection", "number selection must be a list")
    result: list[int] = []
    for number in value:
        if type(number) is not int or number < minimum or number > maximum:
            raise ToolError(
                "invalid_number",
                f"number must be between {minimum} and {maximum}",
            )
        if number not in result:
            result.append(number)
    return sorted(result)


def _require_disjoint(locked: list[int], excluded: list[int], label: str) -> None:
    if set(locked).intersection(excluded):
        raise ToolError("locked_conflict", f"{label} number cannot be locked and excluded")


def _normalize_entry(
    game_key: str,
    main: list[int],
    special: list[int],
    **extra: Any,
) -> dict[str, Any]:
    if game_key in {"3d", "pl3"}:
        play_type = extra.pop("play_type", "straight")
        text = "".join(str(number) for number in main)
        return {
            "main": list(main),
            "special": list(special),
            "text": text,
            "play_type": play_type,
            **extra,
        }
    else:
        main_text = " ".join(f"{number:02d}" for number in main)
        special_text = " ".join(f"{number:02d}" for number in special)
        text = f"{main_text} | {special_text}" if special else main_text
    return {"main": list(main), "special": list(special), "text": text, **extra}


def _normalize_digit_group_entry(
    game_key: str,
    main: Any,
    play_type: str,
) -> dict[str, Any]:
    config = _require_game(game_key)
    if not isinstance(main, list):
        raise ToolError("invalid_number_line", "组选包号数字必须为列表")
    needed = 2 if play_type == "group3" else 3
    minimum, maximum = config["digits"]
    if len(main) != needed or len(set(main)) != needed or any(
        type(number) is not int or number < minimum or number > maximum for number in main
    ):
        raise ToolError("invalid_number_line", "组选包号数字不符合规则")
    entry = _normalize_entry(game_key, sorted(main), [], play_type=play_type)
    label = "组三" if play_type == "group3" else "组六"
    entry["text"] = f"{' '.join(str(number) for number in entry['main'])} · {label}"
    return entry


def _entry_identity(entry: dict[str, Any]) -> str:
    """Use semantic identity, not a display-only text value, for dedupe/order."""
    return "|".join(
        [
            str(entry.get("play_type", "straight")),
            ",".join(str(number) for number in entry.get("main", [])),
            ",".join(str(number) for number in entry.get("special", [])),
        ]
    )


def _coverage_tokens(game_key: str, entry: dict[str, Any]) -> set[tuple[str, int]]:
    """Tag each zone so identical numeric values in separate zones stay distinct."""
    if game_key in {"3d", "pl3"}:
        if entry.get("play_type") in {"group3", "group6"}:
            return {(str(entry["play_type"]), number) for number in entry["main"]}
        return {(f"position_{index + 1}", number) for index, number in enumerate(entry["main"])}
    tokens = {("main", number) for number in entry["main"]}
    tokens.update(("special", number) for number in entry.get("special", []))
    return tokens


def _result_payload(
    game_key: str,
    tool: str,
    entries: list[dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    config = _require_game(game_key)
    multiplier = options.get("multiplier", 1)
    entry_cost = config["unit_cost"] + (
        config.get("add_on_cost", 0) if options.get("add_on") else 0
    )
    ticket_count = len(entries)
    return {
        "game_key": game_key,
        "tool": tool,
        "ticket_count": ticket_count,
        "unit_cost": config["unit_cost"],
        "entry_cost": entry_cost,
        "multiplier": multiplier,
        "total_cost": ticket_count * entry_cost * multiplier,
        "entries": deepcopy(entries),
        "truncated": False,
        "warnings": [],
    }


def result_from_candidates(
    game_key: str,
    tool: str,
    candidates: list[dict[str, Any]],
    options: dict[str, Any] | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_options = normalize_options(game_key, options)
    entries = [
        _normalize_entry(
            game_key,
            list(candidate.get("main") or candidate.get("numbers") or []),
            list(candidate.get("special") or []),
            play_type=str(candidate.get("play_type") or "straight"),
        )
        for candidate in candidates
    ]
    payload = _result_payload(game_key, tool, entries, normalized_options)
    if payload["total_cost"] > MAX_TOTAL_COST:
        payload["warnings"].append("spend_limit")
    payload["source_meta"] = deepcopy(metadata or {})
    return payload
