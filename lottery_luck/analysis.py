from __future__ import annotations

from collections import Counter
from datetime import date
from itertools import combinations, product
from typing import Any

from .rules import GAME_RULES, candidate_draw_dates, parse_numbers


ALLOWED_WINDOWS = {30, 60, 120}


def normalize_window(value: int | str | None) -> int:
    try:
        window = int(value) if value is not None else 30
    except (TypeError, ValueError):
        return 30
    return window if window in ALLOWED_WINDOWS else 30


def build_analysis_payload(
    game_key: str,
    draws: list[dict[str, Any]],
    window: int | str | None = 30,
    prediction: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise ValueError(f"unsupported game_key: {game}")

    normalized_window = normalize_window(window)
    window_draws = draws[:normalized_window]
    parsed_draws = [_parse_draw(game, draw) for draw in window_draws]

    hot = {
        "main": _rank_counts(game, parsed_draws, "main", "hot"),
        "special": _rank_counts(game, parsed_draws, "special", "hot"),
    }
    cold = {
        "main": _rank_counts(game, parsed_draws, "main", "cold"),
        "special": _rank_counts(game, parsed_draws, "special", "cold"),
    }

    return {
        "game_key": game,
        "window": normalized_window,
        "summary": _summary(window_draws),
        "hot": hot,
        "cold": cold,
        "recent_weight": {
            "main": _recent_weight(game, parsed_draws, "main"),
            "special": _recent_weight(game, parsed_draws, "special"),
        },
        "omission": {
            "main": _omission(game, parsed_draws, "main"),
            "special": _omission(game, parsed_draws, "special"),
        },
        "position_hot": _position_rank(game, parsed_draws, "hot"),
        "position_cold": _position_rank(game, parsed_draws, "cold"),
        "position_omission": _position_omission(game, parsed_draws),
        "shape": _shape(game, parsed_draws),
        "professional": _professional_metrics(game, parsed_draws),
        "trend": _trend(game, parsed_draws, limit=normalized_window),
        "recent_draws": _recent_draws(parsed_draws, prediction, hot, cold),
    }


def _parse_draw(game_key: str, draw: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_numbers(
        game_key,
        str(draw.get("red_numbers") or ""),
        str(draw.get("blue_number") or ""),
    )
    return {
        "issue": str(draw.get("issue") or ""),
        "draw_date": str(draw.get("draw_date") or ""),
        "main": parsed["main"],
        "special": parsed["special"],
    }


def _summary(draws: list[dict[str, Any]]) -> dict[str, Any]:
    latest = draws[0] if draws else {}
    return {
        "draw_count": len(draws),
        "latest_issue": str(latest.get("issue") or ""),
        "latest_date": str(latest.get("draw_date") or ""),
    }


def _rank_counts(
    game_key: str,
    draws: list[dict[str, Any]],
    field: str,
    order: str,
    limit: int = 10,
) -> list[dict[str, int]]:
    numbers = _number_pool(game_key, field)
    if not numbers:
        return []

    counts = Counter({number: 0 for number in numbers})
    for draw in draws:
        counts.update(number for number in draw[field] if number in counts)

    if order == "cold":
        ranked = sorted(counts.items(), key=lambda item: (item[1], item[0]))
    else:
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"number": number, "count": count} for number, count in ranked[:limit]]


def _recent_weight(
    game_key: str,
    draws: list[dict[str, Any]],
    field: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    numbers = _number_pool(game_key, field)
    if not numbers:
        return []

    scores = {number: 0.0 for number in numbers}
    for index, draw in enumerate(draws):
        weight = 1.0 / (1.0 + index / 8.0)
        for number in draw[field]:
            if number in scores:
                scores[number] += weight
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"number": number, "weight": round(score, 3)}
        for number, score in ranked[:limit]
    ]


def _omission(
    game_key: str,
    draws: list[dict[str, Any]],
    field: str,
    limit: int = 10,
) -> list[dict[str, int]]:
    missing = _full_omission(game_key, draws, field)
    ranked = sorted(missing.items(), key=lambda item: (-item[1], item[0]))
    return [{"number": number, "missing": count} for number, count in ranked[:limit]]


def _full_omission(
    game_key: str,
    draws: list[dict[str, Any]],
    field: str,
) -> dict[int, int]:
    numbers = _number_pool(game_key, field)
    if not numbers:
        return {}

    missing: dict[int, int] = {}
    for number in numbers:
        missing[number] = len(draws)
        for index, draw in enumerate(draws):
            if number in draw[field]:
                missing[number] = index
                break
    return missing


def _position_rank(
    game_key: str,
    draws: list[dict[str, Any]],
    order: str,
    limit: int = 5,
) -> list[list[dict[str, int]]]:
    rule = GAME_RULES[game_key]
    result: list[list[dict[str, int]]] = []
    for position in range(rule.draw_main_count):
        counts = Counter({number: 0 for number in rule.main_range})
        for draw in draws:
            if position < len(draw["main"]):
                number = draw["main"][position]
                if number in counts:
                    counts[number] += 1
        if order == "cold":
            ranked = sorted(counts.items(), key=lambda item: (item[1], item[0]))
        else:
            ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        result.append([{"number": number, "count": count} for number, count in ranked[:limit]])
    return result


def _position_omission(
    game_key: str,
    draws: list[dict[str, Any]],
    limit: int = 5,
) -> list[list[dict[str, int]]]:
    rule = GAME_RULES[game_key]
    result: list[list[dict[str, int]]] = []
    for position in range(rule.draw_main_count):
        missing = {}
        for number in rule.main_range:
            missing[number] = len(draws)
            for index, draw in enumerate(draws):
                if position < len(draw["main"]) and draw["main"][position] == number:
                    missing[number] = index
                    break
        ranked = sorted(missing.items(), key=lambda item: (-item[1], item[0]))
        result.append([{"number": number, "missing": count} for number, count in ranked[:limit]])
    return result


def _shape(game_key: str, draws: list[dict[str, Any]]) -> dict[str, list[dict[str, int]]]:
    base = {
        "odd_even": _counter_to_rows(_count_labels(_ratio(draw["main"], "odd_even") for draw in draws)),
        "big_small": _counter_to_rows(_count_labels(_ratio(draw["main"], "big_small", game_key) for draw in draws)),
        "sum_ranges": _counter_to_rows(_count_labels(_sum_bucket(draw["main"]) for draw in draws)),
        "consecutive_counts": _counter_to_rows(
            _count_labels(_consecutive_label(draw["main"]) for draw in draws)
        ),
        "repeat_counts": _repeat_counts(draws),
    }

    if game_key == "3d":
        base["digit_types"] = _counter_to_rows(
            _count_labels(_digit_type(draw["main"]) for draw in draws),
            preferred_order=["豹子", "组三", "组六"],
        )
        base["span"] = _counter_to_rows(_count_labels(_span_label(draw["main"]) for draw in draws))
    if game_key == "kl8":
        base["range_distribution"] = _range_distribution(draws)
    return base


def _professional_metrics(game_key: str, draws: list[dict[str, Any]]) -> dict[str, list[dict[str, int]]]:
    return {
        "ac_values": _counter_to_rows(_count_labels(f"AC{_ac_value(draw['main'])}" for draw in draws)),
        "prime_composite": _counter_to_rows(
            _count_labels(_prime_composite_ratio(draw["main"]) for draw in draws)
        ),
        "tail_distribution": _tail_distribution(draws),
        "mod3_distribution": _mod3_distribution(draws),
        "zone_distribution": _zone_distribution(game_key, draws),
        "neighbor_counts": _neighbor_counts(draws),
        "omission_layers": _omission_layers(game_key, draws),
    }


def filter_candidates(
    game_key: str,
    draws: list[dict[str, Any]],
    conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    rule = GAME_RULES[game]
    parsed_draws = [_parse_draw(game, draw) for draw in draws]
    normalized = _normalize_conditions(conditions)
    hot_numbers = [row["number"] for row in _rank_counts(game, parsed_draws, "main", "hot", limit=20)]
    excluded = _recent_numbers(parsed_draws, normalized["exclude_recent"])
    ranked_pool = _ranked_candidate_pool(game, parsed_draws, excluded)
    omission_map = _full_omission(game, parsed_draws, "main")

    candidates: list[dict[str, Any]] = []
    for main in _candidate_combinations(game, ranked_pool):
        main_list = list(main)
        if not _passes_conditions(main_list, hot_numbers, normalized, game, omission_map):
            continue
        special = _select_candidate_special(game, parsed_draws, main_list)
        candidates.append(
            {
                "main": main_list,
                "special": special,
                "score": _candidate_score(main_list, hot_numbers),
                "sum": sum(main_list),
                "odd_even": _ratio(main_list, "odd_even"),
                "big_small": _ratio(main_list, "big_small", game),
                "ac_value": _ac_value(main_list),
                "prime_composite": _prime_composite_ratio(main_list),
                "mod3": _mod3_ratio(main_list),
                "zone": _zone_ratio(game, main_list),
                "tail_pattern": _tail_pattern(main_list),
                "omission_hits": _candidate_omission_hits(main_list, omission_map),
                "max_consecutive_run": _max_consecutive_run(main_list),
                "tags": _candidate_tags(game, main_list, hot_numbers),
            }
        )
        if len(candidates) >= normalized["count"]:
            break

    return {
        "game_key": game,
        "conditions": normalized,
        "basis": {
            "draw_count": len(parsed_draws),
            "hot_main": hot_numbers[:10],
            "excluded_recent": sorted(excluded),
        },
        "candidates": candidates,
        "disclaimer": "筛选结果仅供历史数据分析和娱乐参考，不构成投注建议。",
    }


def backtest_strategy(
    game_key: str,
    draws: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    parsed_draws = [_parse_draw(game, draw) for draw in draws]
    request = request or {}
    window = _bounded_int(request.get("window"), default=100, minimum=1, maximum=300)
    strategy = str(request.get("strategy") or "hot_omission_balance")
    test_count = min(window, max(0, len(parsed_draws) - 1))
    rows = []

    for index in range(test_count):
        target = parsed_draws[index]
        history_rows = [
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "red_numbers": ",".join(str(number) for number in draw["main"]),
                "blue_number": ",".join(str(number) for number in draw["special"]),
            }
            for draw in parsed_draws[index + 1 :]
        ]
        conditions = _strategy_conditions(game, strategy)
        filtered = filter_candidates(game, history_rows, {**conditions, "count": 1})
        candidate = filtered["candidates"][0] if filtered["candidates"] else {"main": [], "special": []}
        main_hits = len(set(candidate["main"]) & set(target["main"]))
        special_hits = len(set(candidate.get("special", [])) & set(target["special"]))
        rows.append(
            {
                "issue": target["issue"],
                "draw_date": target["draw_date"],
                "actual": {"main": target["main"], "special": target["special"]},
                "candidate": {"main": candidate["main"], "special": candidate.get("special", [])},
                "main_hits": main_hits,
                "special_hits": special_hits,
            }
        )

    average = sum(row["main_hits"] for row in rows) / len(rows) if rows else 0.0
    return {
        "game_key": game,
        "strategy": strategy,
        "tested_draws": len(rows),
        "average_main_hits": round(average, 2),
        "max_main_hits": max((row["main_hits"] for row in rows), default=0),
        "rows": rows[:20],
        "disclaimer": "回测只说明历史样本表现，不代表未来结果。",
    }


def compare_backtest_strategies(
    game_key: str,
    draws: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    request = request or {}
    raw_strategies = request.get("strategies") or ["hot_omission_balance", "cold_rebound", "hot_focus"]
    if not isinstance(raw_strategies, list):
        raw_strategies = ["hot_omission_balance", "cold_rebound", "hot_focus"]
    strategies = [str(strategy) for strategy in raw_strategies if str(strategy).strip()][:6]
    if not strategies:
        strategies = ["hot_omission_balance", "cold_rebound", "hot_focus"]

    window = _bounded_int(request.get("window"), default=100, minimum=1, maximum=300)
    rows = []
    for strategy in strategies:
        result = backtest_strategy(game, draws, {"strategy": strategy, "window": window})
        rows.append(
            {
                "strategy": result["strategy"],
                "tested_draws": result["tested_draws"],
                "average_main_hits": result["average_main_hits"],
                "max_main_hits": result["max_main_hits"],
                "recent_rows": result["rows"][:5],
            }
        )
    rows.sort(key=lambda row: (-row["average_main_hits"], -row["max_main_hits"], row["strategy"]))
    return {
        "game_key": game,
        "window": window,
        "strategies": rows,
        "disclaimer": "策略对比只说明历史样本表现，不代表未来结果。",
    }


def analyze_number_pool(
    game_key: str,
    draws: list[dict[str, Any]],
    numbers: list[dict[str, Any]],
) -> dict[str, Any]:
    game = _require_game(game_key)
    parsed_draws = [_parse_draw(game, draw) for draw in draws]
    hot = {row["number"] for row in _rank_counts(game, parsed_draws, "main", "hot", limit=10)}
    cold = {row["number"] for row in _rank_counts(game, parsed_draws, "main", "cold", limit=10)}
    seen: Counter[tuple[int, ...]] = Counter()
    normalized_pool = [_normalize_pool_entry(entry) for entry in numbers]
    for entry in normalized_pool:
        seen[tuple(entry["main"])] += 1

    entries = []
    for index, entry in enumerate(normalized_pool):
        main = entry["main"]
        total = sum(main)
        duplicate_count = seen[tuple(main)]
        risk_score = _pool_risk_score(game, main, total, duplicate_count)
        entries.append(
            {
                "index": index,
                "main": main,
                "special": entry["special"],
                "sum": total,
                "sum_level": _sum_level(game, total),
                "odd_even": _ratio(main, "odd_even"),
                "big_small": _ratio(main, "big_small", game),
                "ac_value": _ac_value(main),
                "prime_composite": _prime_composite_ratio(main),
                "mod3": _mod3_ratio(main),
                "zone": _zone_ratio(game, main),
                "tail_pattern": _tail_pattern(main),
                "hot_hits": len(set(main) & hot),
                "cold_hits": len(set(main) & cold),
                "duplicate_count": max(0, duplicate_count - 1),
                "max_consecutive_run": _max_consecutive_run(main),
                "risk_score": risk_score,
                "warnings": _pool_warnings(game, main, total, duplicate_count, risk_score),
                "fortune_commentary": _pool_fortune_commentary(
                    game, main, total, duplicate_count, risk_score
                ),
            }
        )

    return {
        "game_key": game,
        "summary": {
            "pool_size": len(entries),
            "duplicate_groups": sum(1 for count in seen.values() if count > 1),
            "extreme_sum_count": sum(1 for entry in entries if entry["sum_level"] != "正常"),
        },
        "entries": entries,
    }


def build_draw_calendar(
    games: list[dict[str, Any]],
    today: str | None = None,
) -> dict[str, Any]:
    current_day = today or date.today().isoformat()
    rows = []
    for game in games:
        key = str(game.get("game_key") or "").strip().lower()
        if key not in GAME_RULES:
            continue
        dates = candidate_draw_dates(key, current_day, 14)
        next_date = dates[0].isoformat() if dates else current_day
        rows.append(
            {
                "game_key": key,
                "game_name": game.get("game_name") or GAME_RULES[key].name,
                "latest_issue": game.get("latest_issue") or "",
                "latest_date": game.get("latest_date") or "",
                "next_draw_date": next_date,
                "crawler_updated_at": f"{game.get('latest_date') or current_day} 10:30",
                "status": "等待开奖" if next_date >= current_day else "待更新",
                "reminder_key": f"reminder:{key}:{next_date}",
            }
        )
    return {"today": current_day, "games": rows}


def _trend(game_key: str, draws: list[dict[str, Any]], limit: int = 12) -> dict[str, Any]:
    if game_key == "kl8":
        columns = _range_labels()
        rows = [
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "hits": _hit_ranges(draw["main"]),
                "special_hits": [],
            }
            for draw in draws[:limit]
        ]
    elif game_key in {"3d", "pl3"}:
        columns = [_format_number(number) for number in GAME_RULES[game_key].main_range]
        position_columns = ["百位", "十位", "个位"]
        rows = [
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "hits": draw["main"],
                "special_hits": [],
                "position_hits": [
                    {"position": position_columns[index], "number": number}
                    for index, number in enumerate(draw["main"][:3])
                ],
            }
            for draw in draws[:limit]
        ]
        return {"columns": columns, "position_columns": position_columns, "rows": rows}
    else:
        rule = GAME_RULES[game_key]
        columns = [_format_number(number) for number in rule.main_range]
        rows = [
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "hits": draw["main"],
                "special_hits": draw["special"],
            }
            for draw in draws[:limit]
        ]
    return {"columns": columns, "rows": rows}


def _recent_draws(
    draws: list[dict[str, Any]],
    prediction: dict[str, list[int]] | None,
    hot: dict[str, list[dict[str, int]]],
    cold: dict[str, list[dict[str, int]]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    predicted_main = set((prediction or {}).get("main") or [])
    predicted_special = set((prediction or {}).get("special") or [])
    hot_numbers = {item["number"] for item in hot["main"][:5]} | {
        item["number"] for item in hot["special"][:3]
    }
    cold_numbers = {item["number"] for item in cold["main"][:5]} | {
        item["number"] for item in cold["special"][:3]
    }

    result = []
    for draw in draws[:limit]:
        main = set(draw["main"])
        special = set(draw["special"])
        tags = []
        if (main | special) & hot_numbers:
            tags.append("含热号")
        if (main | special) & cold_numbers:
            tags.append("含冷号")
        result.append(
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "main": draw["main"],
                "special": draw["special"],
                "overlap_with_prediction": len(main & predicted_main)
                + len(special & predicted_special),
                "tags": tags,
            }
        )
    return result


def _number_pool(game_key: str, field: str) -> list[int]:
    rule = GAME_RULES[game_key]
    if field == "special":
        return list(rule.special_range or [])
    return list(rule.main_range)


def _count_labels(labels: Any) -> Counter[str]:
    return Counter(label for label in labels if label)


def _counter_to_rows(
    counter: Counter[str],
    preferred_order: list[str] | None = None,
) -> list[dict[str, int]]:
    if preferred_order:
        keys = preferred_order + sorted(set(counter) - set(preferred_order))
        return [{"label": key, "count": counter[key]} for key in keys if counter[key] > 0]
    return [
        {"label": label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _ratio(numbers: list[int], mode: str, game_key: str | None = None) -> str:
    if not numbers:
        return ""
    if mode == "odd_even":
        first = sum(1 for number in numbers if number % 2 == 1)
        second = len(numbers) - first
    else:
        rule = GAME_RULES[game_key or "ssq"]
        midpoint = (min(rule.main_range) + max(rule.main_range)) / 2
        first = sum(1 for number in numbers if number > midpoint)
        second = len(numbers) - first
    return f"{first}:{second}"


def _ac_value(numbers: list[int]) -> int:
    unique = sorted(set(numbers))
    if len(unique) <= 1:
        return 0
    distances = {
        abs(second - first)
        for first, second in combinations(unique, 2)
        if abs(second - first) > 0
    }
    return max(0, len(distances) - (len(unique) - 1))


def _prime_composite_ratio(numbers: list[int]) -> str:
    prime_count = sum(1 for number in numbers if _is_prime(number))
    composite_count = len(numbers) - prime_count
    return f"{prime_count}:{composite_count}"


def _is_prime(number: int) -> bool:
    if number < 2:
        return False
    for divisor in range(2, int(number**0.5) + 1):
        if number % divisor == 0:
            return False
    return True


def _mod3_ratio(numbers: list[int]) -> str:
    counts = [0, 0, 0]
    for number in numbers:
        counts[number % 3] += 1
    return ":".join(str(count) for count in counts)


def _zone_ratio(game_key: str, numbers: list[int]) -> str:
    labels = _zone_labels(game_key)
    counts = [0 for _ in labels]
    for number in numbers:
        index = _zone_index(game_key, number)
        if 0 <= index < len(counts):
            counts[index] += 1
    return ":".join(str(count) for count in counts)


def _tail_pattern(numbers: list[int]) -> str:
    tails = sorted({number % 10 for number in numbers})
    return "/".join(str(tail) for tail in tails)


def _tail_distribution(draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts = Counter({f"尾{tail}": 0 for tail in range(10)})
    for draw in draws:
        counts.update(f"尾{number % 10}" for number in draw["main"])
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _mod3_distribution(draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts = Counter({"0路": 0, "1路": 0, "2路": 0})
    for draw in draws:
        counts.update(f"{number % 3}路" for number in draw["main"])
    return [{"label": label, "count": counts[label]} for label in ["0路", "1路", "2路"]]


def _zone_distribution(game_key: str, draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    labels = _zone_labels(game_key)
    counts = Counter({label: 0 for label in labels})
    for draw in draws:
        counts.update(_zone_label(game_key, number) for number in draw["main"])
    return [{"label": label, "count": counts[label]} for label in labels]


def _zone_labels(game_key: str) -> list[str]:
    if game_key == "kl8":
        return ["一区", "二区", "三区", "四区"]
    return ["一区", "二区", "三区"]


def _zone_index(game_key: str, number: int) -> int:
    if game_key == "kl8":
        return min(3, max(0, (number - 1) // 20))
    if game_key == "3d":
        if number <= 3:
            return 0
        if number <= 6:
            return 1
        return 2
    rule = GAME_RULES[game_key]
    minimum = min(rule.main_range)
    maximum = max(rule.main_range)
    span = maximum - minimum + 1
    zone_size = max(1, (span + 2) // 3)
    return min(2, max(0, (number - minimum) // zone_size))


def _zone_label(game_key: str, number: int) -> str:
    labels = _zone_labels(game_key)
    return labels[_zone_index(game_key, number)]


def _neighbor_counts(draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts: Counter[str] = Counter()
    for index in range(len(draws) - 1):
        current = set(draws[index]["main"])
        previous = set(draws[index + 1]["main"])
        neighbor_count = sum(1 for number in current if number - 1 in previous or number + 1 in previous)
        counts[f"{neighbor_count}邻号"] += 1
    rows = _counter_to_rows(counts)
    return rows if rows else [{"label": "0邻号", "count": 0}]


def _omission_layers(game_key: str, draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    if not draws:
        return [
            {"label": "高遗漏", "count": 0},
            {"label": "中遗漏", "count": 0},
            {"label": "低遗漏", "count": 0},
        ]

    missing = _full_omission(game_key, draws, "main")
    high_threshold = max(2, int(len(draws) * 0.66))
    medium_threshold = max(1, int(len(draws) * 0.33))
    layers = Counter({"高遗漏": 0, "中遗漏": 0, "低遗漏": 0})
    for value in missing.values():
        if value >= high_threshold:
            layers["高遗漏"] += 1
        elif value >= medium_threshold:
            layers["中遗漏"] += 1
        else:
            layers["低遗漏"] += 1
    return [{"label": label, "count": layers[label]} for label in ["高遗漏", "中遗漏", "低遗漏"]]


def _sum_bucket(numbers: list[int]) -> str:
    if not numbers:
        return ""
    total = sum(numbers)
    start = total // 20 * 20
    end = start + 19
    return f"{start:02d}-{end:02d}"


def _consecutive_label(numbers: list[int]) -> str:
    count = _consecutive_count(numbers)
    if count == 0:
        return "无连号"
    return f"{count}组连号"


def _consecutive_count(numbers: list[int]) -> int:
    unique = sorted(set(numbers))
    return sum(1 for index in range(len(unique) - 1) if unique[index + 1] == unique[index] + 1)


def _digit_type(numbers: list[int]) -> str:
    unique_count = len(set(numbers))
    if unique_count == 1:
        return "豹子"
    if unique_count == 2:
        return "组三"
    return "组六"


def _span_label(numbers: list[int]) -> str:
    if not numbers:
        return ""
    return f"跨度{max(numbers) - min(numbers)}"


def _range_distribution(draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts = Counter({label: 0 for label in _range_labels()})
    for draw in draws:
        counts.update(_range_label(number) for number in draw["main"])
    return [{"label": label, "count": counts[label]} for label in _range_labels()]


def _repeat_counts(draws: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts: Counter[str] = Counter()
    for index in range(len(draws) - 1):
        current = set(draws[index]["main"])
        previous = set(draws[index + 1]["main"])
        counts[f"{len(current & previous)}个重号"] += 1
    return _counter_to_rows(counts)


def _hit_ranges(numbers: list[int]) -> list[str]:
    labels = []
    seen = set()
    for number in sorted(numbers):
        label = _range_label(number)
        if label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def _range_label(number: int) -> str:
    start = ((number - 1) // 10) * 10 + 1
    end = start + 9
    return f"{start:02d}-{end:02d}"


def _range_labels() -> list[str]:
    return [f"{start:02d}-{start + 9:02d}" for start in range(1, 80, 10)]


def _format_number(number: int) -> str:
    return f"{number:02d}"


def _require_game(game_key: str) -> str:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise ValueError(f"unsupported game_key: {game}")
    return game


def _normalize_conditions(conditions: dict[str, Any] | None) -> dict[str, Any]:
    raw = conditions or {}
    return {
        "exclude_recent": _bounded_int(raw.get("exclude_recent"), 0, 0, 30),
        "min_hot": _bounded_int(raw.get("min_hot"), 0, 0, 10),
        "odd_even": str(raw.get("odd_even") or "").strip(),
        "sum_min": _optional_int(raw.get("sum_min")),
        "sum_max": _optional_int(raw.get("sum_max")),
        "max_consecutive_run": _bounded_int(raw.get("max_consecutive_run"), 99, 1, 99),
        "ac_min": _optional_int(raw.get("ac_min")),
        "ac_max": _optional_int(raw.get("ac_max")),
        "prime_composite": str(raw.get("prime_composite") or "").strip(),
        "mod3": str(raw.get("mod3") or "").strip(),
        "zone": str(raw.get("zone") or "").strip(),
        "tail_exclude": _int_list(raw.get("tail_exclude"), minimum=0, maximum=9),
        "tail_include": _int_list(raw.get("tail_include"), minimum=0, maximum=9),
        "min_omission": _optional_int(raw.get("min_omission")),
        "count": _bounded_int(raw.get("count"), 10, 1, 30),
    }


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(value: Any, minimum: int | None = None, maximum: int | None = None) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values: list[Any] = [
            part
            for part in value.replace(",", " ").replace("/", " ").replace("，", " ").replace("、", " ").split()
        ]
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]

    result = []
    for item in raw_values:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if minimum is not None and number < minimum:
            continue
        if maximum is not None and number > maximum:
            continue
        if number not in result:
            result.append(number)
    return result


def _recent_numbers(draws: list[dict[str, Any]], recent: int) -> set[int]:
    result: set[int] = set()
    for draw in draws[:recent]:
        result.update(draw["main"])
    return result


def _ranked_candidate_pool(
    game_key: str,
    draws: list[dict[str, Any]],
    excluded: set[int],
) -> list[int]:
    rule = GAME_RULES[game_key]
    weighted = _recent_weight(game_key, draws, "main", limit=len(rule.main_range))
    ordered = [row["number"] for row in weighted if row["number"] not in excluded]
    ordered.extend(number for number in rule.main_range if number not in excluded and number not in ordered)
    if len(ordered) < rule.main_count:
        ordered = list(rule.main_range)
    return ordered


def _candidate_combinations(game_key: str, pool: list[int]) -> list[tuple[int, ...]]:
    rule = GAME_RULES[game_key]
    if rule.allow_repeat:
        digits = pool[:10] if pool else list(rule.main_range)
        return [tuple(values) for values in product(digits, repeat=rule.main_count)]
    if game_key == "kl8":
        result = []
        source = pool or list(rule.main_range)
        for offset in range(min(len(source), 80)):
            wrapped = source[offset:] + source[:offset]
            candidate = tuple(sorted(wrapped[: rule.main_count]))
            if candidate not in result:
                result.append(candidate)
        return result
    pool_size = min(len(pool), 18)
    return list(combinations(sorted(pool[:pool_size]), rule.main_count))


def _passes_conditions(
    main: list[int],
    hot_numbers: list[int],
    conditions: dict[str, Any],
    game_key: str,
    omission_map: dict[int, int],
) -> bool:
    if conditions["min_hot"] and len(set(main) & set(hot_numbers[:10])) < conditions["min_hot"]:
        return False
    if conditions["odd_even"] and _ratio(main, "odd_even") != conditions["odd_even"]:
        return False
    if conditions["sum_min"] is not None and sum(main) < conditions["sum_min"]:
        return False
    if conditions["sum_max"] is not None and sum(main) > conditions["sum_max"]:
        return False
    if _max_consecutive_run(main) > conditions["max_consecutive_run"]:
        return False
    if conditions["ac_min"] is not None and _ac_value(main) < conditions["ac_min"]:
        return False
    if conditions["ac_max"] is not None and _ac_value(main) > conditions["ac_max"]:
        return False
    if conditions["prime_composite"] and _prime_composite_ratio(main) != conditions["prime_composite"]:
        return False
    if conditions["mod3"] and _mod3_ratio(main) != conditions["mod3"]:
        return False
    if conditions["zone"] and _zone_ratio(game_key, main) != conditions["zone"]:
        return False
    tails = {number % 10 for number in main}
    if conditions["tail_exclude"] and tails & set(conditions["tail_exclude"]):
        return False
    if conditions["tail_include"] and not set(conditions["tail_include"]).issubset(tails):
        return False
    if conditions["min_omission"] is not None and not any(
        omission_map.get(number, 0) >= conditions["min_omission"] for number in main
    ):
        return False
    return True


def _select_candidate_special(
    game_key: str,
    draws: list[dict[str, Any]],
    main: list[int],
) -> list[int]:
    rule = GAME_RULES[game_key]
    if not rule.special_range or rule.special_count <= 0:
        return []
    ranked = _recent_weight(game_key, draws, "special", limit=len(rule.special_range))
    excluded = set(main) if game_key == "qlc" else set()
    selected = []
    for row in ranked:
        if row["number"] not in excluded and row["number"] not in selected:
            selected.append(row["number"])
        if len(selected) >= rule.special_count:
            return selected
    for number in rule.special_range:
        if number not in excluded and number not in selected:
            selected.append(number)
        if len(selected) >= rule.special_count:
            break
    return selected


def _candidate_score(main: list[int], hot_numbers: list[int]) -> float:
    hot_rank = {number: index for index, number in enumerate(hot_numbers)}
    score = 0.0
    for number in main:
        score += max(0, 20 - hot_rank.get(number, 20))
    score += 10 if _max_consecutive_run(main) <= 2 else 0
    return round(score, 2)


def _candidate_omission_hits(
    main: list[int],
    omission_map: dict[int, int],
) -> list[dict[str, int]]:
    rows = [
        {"number": number, "missing": omission_map.get(number, 0)}
        for number in main
        if omission_map.get(number, 0) > 0
    ]
    return sorted(rows, key=lambda row: (-row["missing"], row["number"]))[:4]


def _candidate_tags(game_key: str, main: list[int], hot_numbers: list[int]) -> list[str]:
    tags = []
    hot_count = len(set(main) & set(hot_numbers[:10]))
    if hot_count:
        tags.append(f"含{hot_count}个热号")
    tags.append(f"奇偶{_ratio(main, 'odd_even')}")
    tags.append(f"和值{sum(main)}")
    tags.append(f"AC{_ac_value(main)}")
    tags.append(f"质合{_prime_composite_ratio(main)}")
    tags.append(f"区间{_zone_ratio(game_key, main)}")
    return tags


def _max_consecutive_run(numbers: list[int]) -> int:
    unique = sorted(set(numbers))
    if not unique:
        return 0
    longest = current = 1
    for index in range(1, len(unique)):
        if unique[index] == unique[index - 1] + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _strategy_conditions(game_key: str, strategy: str) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    odd = rule.main_count // 2
    even = rule.main_count - odd
    if strategy == "hot_omission_balance":
        return {
            "exclude_recent": 1,
            "min_hot": 1,
            "odd_even": f"{odd}:{even}",
            "max_consecutive_run": 2,
        }
    if strategy == "cold_rebound":
        return {"exclude_recent": 2, "min_hot": 0, "max_consecutive_run": 2}
    return {"exclude_recent": 0, "min_hot": 1, "max_consecutive_run": 3}


def _normalize_pool_entry(entry: dict[str, Any]) -> dict[str, list[int]]:
    main = entry.get("main") or []
    special = entry.get("special") or []
    return {
        "main": sorted({int(number) for number in main}),
        "special": sorted({int(number) for number in special}),
    }


def _sum_level(game_key: str, total: int) -> str:
    rule = GAME_RULES[game_key]
    low = rule.main_count * (min(rule.main_range) + max(rule.main_range)) * 0.36
    high = rule.main_count * (min(rule.main_range) + max(rule.main_range)) * 0.64
    if total < low:
        return "偏低"
    if total > high:
        return "偏高"
    return "正常"


def _pool_risk_score(game_key: str, main: list[int], total: int, duplicate_count: int) -> int:
    score = 0
    if duplicate_count > 1:
        score += 25
    if _sum_level(game_key, total) != "正常":
        score += 20
    if _max_consecutive_run(main) >= 3:
        score += 18
    ac = _ac_value(main)
    if ac <= max(1, len(set(main)) // 3):
        score += 16
    tails = [number % 10 for number in main]
    if len(set(tails)) <= max(2, len(main) // 2):
        score += 12
    return min(100, score)


def _pool_warnings(
    game_key: str,
    main: list[int],
    total: int,
    duplicate_count: int,
    risk_score: int,
) -> list[str]:
    warnings = []
    if duplicate_count > 1:
        warnings.append("号码重复")
    if _sum_level(game_key, total) != "正常":
        warnings.append(f"和值{_sum_level(game_key, total)}")
    if _max_consecutive_run(main) >= 3:
        warnings.append("连号偏多")
    if _ac_value(main) <= max(1, len(set(main)) // 3):
        warnings.append("AC偏低")
    if risk_score >= 60:
        warnings.append("风险偏高")
    return warnings


def _pool_fortune_commentary(
    game_key: str,
    main: list[int],
    total: int,
    duplicate_count: int,
    risk_score: int,
) -> dict[str, str]:
    sum_level = _sum_level(game_key, total)
    tails = {number % 10 for number in main}
    metal_tails = {7, 8}
    wood_tails = {1, 2}
    water_tails = {9, 0}

    if risk_score >= 55 or sum_level != "正常":
        wealth_type = "散财"
    elif duplicate_count > 1 or len(tails & metal_tails) >= 2:
        wealth_type = "守财"
    else:
        wealth_type = "进财"

    if len(tails & (metal_tails | wood_tails)) >= max(1, len(main) // 3):
        compatibility = "相合"
    elif len(tails & water_tails) >= max(2, len(main) // 2):
        compatibility = "略冲"
    else:
        compatibility = "中性"

    comments = {
        "进财": "这组号尾数有生发感，适合做进财尝试。",
        "守财": "这组号收口较稳，更像守财盘，适合保留观察。",
        "散财": "这组号和值或结构偏散，建议缩小投入感，只作参考。",
    }
    return {
        "wealth_type": wealth_type,
        "compatibility": compatibility,
        "comment": f"{comments[wealth_type]} 与当前号码结构{compatibility}。",
    }
