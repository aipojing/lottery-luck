from __future__ import annotations

from collections import Counter
from typing import Any

from .analysis import filter_candidates
from .rules import GAME_RULES, parse_numbers


STRATEGY_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "label": "保守型",
        "description": "控制连号和近期重复，偏向均衡结构。",
        "conditions": {"exclude_recent": 2, "min_hot": 1, "max_consecutive_run": 2},
    },
    "balanced": {
        "label": "均衡型",
        "description": "兼顾热号、和值、奇偶和结构离散度。",
        "conditions": {"exclude_recent": 1, "min_hot": 1, "max_consecutive_run": 3},
    },
    "aggressive": {
        "label": "激进型",
        "description": "放宽近期限制，增加热号权重。",
        "conditions": {"exclude_recent": 0, "min_hot": 2, "max_consecutive_run": 3},
    },
}


def generate_strategy_candidates(
    game_key: str,
    draws: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    normalized = _normalize_strategy_request(game, request)
    filtered = filter_candidates(game, draws, normalized["conditions"])
    return {
        "game_key": game,
        "preset": normalized["preset"],
        "strategy_name": normalized["label"],
        "description": normalized["description"],
        "conditions": filtered["conditions"],
        "basis": filtered["basis"],
        "diagnostics": _strategy_diagnostics(filtered["conditions"], normalized),
        "candidates": filtered["candidates"],
        "baseline": {
            "label": "随机基准",
            "candidates": _baseline_candidates(game, draws, normalized["candidate_count"]),
        },
        "disclaimer": "策略实验室仅供历史数据分析和娱乐参考，不构成投注建议。",
    }


def backtest_strategy_lab(
    game_key: str,
    draws: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    normalized = _normalize_strategy_request(game, request)
    parsed_draws = [_parse_draw(game, draw) for draw in draws]
    test_count = min(normalized["window"], max(0, len(parsed_draws) - 1))
    rows = []

    for index in range(test_count):
        target = parsed_draws[index]
        history_rows = draws[index + 1 :]
        generated = generate_strategy_candidates(
            game,
            history_rows,
            {
                "preset": normalized["preset"],
                "candidate_count": 1,
                "conditions": normalized["custom_conditions"],
            },
        )
        candidate = generated["candidates"][0] if generated["candidates"] else {"main": [], "special": []}
        baseline_candidate = _baseline_candidates(game, history_rows, 1, seed_text=target["issue"])[0]
        main_hits = len(set(candidate["main"]) & set(target["main"]))
        special_hits = len(set(candidate.get("special", [])) & set(target["special"]))
        baseline_main_hits = len(set(baseline_candidate["main"]) & set(target["main"]))
        baseline_special_hits = len(set(baseline_candidate.get("special", [])) & set(target["special"]))
        rows.append(
            {
                "issue": target["issue"],
                "draw_date": target["draw_date"],
                "actual": {"main": target["main"], "special": target["special"]},
                "candidate": {"main": candidate["main"], "special": candidate.get("special", [])},
                "baseline_candidate": baseline_candidate,
                "main_hits": main_hits,
                "special_hits": special_hits,
                "baseline_main_hits": baseline_main_hits,
                "baseline_special_hits": baseline_special_hits,
            }
        )

    average = _average(row["main_hits"] for row in rows)
    baseline_average = _average(row["baseline_main_hits"] for row in rows)
    return {
        "game_key": game,
        "preset": normalized["preset"],
        "strategy_name": normalized["label"],
        "conditions": normalized["conditions"],
        "tested_draws": len(rows),
        "average_main_hits": round(average, 2),
        "max_main_hits": max((row["main_hits"] for row in rows), default=0),
        "baseline_average_main_hits": round(baseline_average, 2),
        "baseline_max_main_hits": max((row["baseline_main_hits"] for row in rows), default=0),
        "hit_distribution": _hit_distribution(rows),
        "rows": rows[:20],
        "disclaimer": "策略回测只说明历史样本表现，不代表未来结果。",
    }


def compare_strategy_presets(
    game_key: str,
    draws: list[dict[str, Any]],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    game = _require_game(game_key)
    request = request or {}
    rows = []
    for preset in STRATEGY_PRESETS:
        result = backtest_strategy_lab(
            game,
            draws,
            {
                "preset": preset,
                "window": request.get("window"),
                "candidate_count": request.get("candidate_count", 1),
                "conditions": request.get("conditions") or {},
            },
        )
        rows.append(
            {
                "preset": result["preset"],
                "strategy_name": result["strategy_name"],
                "tested_draws": result["tested_draws"],
                "average_main_hits": result["average_main_hits"],
                "max_main_hits": result["max_main_hits"],
                "baseline_average_main_hits": result["baseline_average_main_hits"],
                "hit_distribution": result["hit_distribution"],
            }
        )
    rows.sort(key=lambda row: (-row["average_main_hits"], -row["max_main_hits"], row["preset"]))
    return {
        "game_key": game,
        "window": _bounded_int(request.get("window"), 100, 1, 300),
        "strategies": rows,
        "disclaimer": "策略对比只说明历史样本表现，不代表未来结果。",
    }


def _normalize_strategy_request(game_key: str, request: dict[str, Any] | None) -> dict[str, Any]:
    request = request or {}
    preset_key = str(request.get("preset") or "balanced").strip()
    if preset_key not in STRATEGY_PRESETS:
        preset_key = "balanced"
    preset = STRATEGY_PRESETS[preset_key]
    candidate_count = _bounded_int(request.get("candidate_count"), 5, 1, 30)
    custom_conditions = request.get("conditions") if isinstance(request.get("conditions"), dict) else {}
    conditions = {
        **_game_condition_defaults(game_key, preset_key),
        **preset["conditions"],
        **custom_conditions,
        "count": candidate_count,
    }
    return {
        "preset": preset_key,
        "label": preset["label"],
        "description": preset["description"],
        "candidate_count": candidate_count,
        "window": _bounded_int(request.get("window"), 100, 1, 300),
        "conditions": conditions,
        "custom_conditions": custom_conditions,
    }


def _game_condition_defaults(game_key: str, preset_key: str) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    odd = (rule.main_count + 1) // 2
    even = rule.main_count - odd
    minimum = min(rule.main_range)
    maximum = max(rule.main_range)
    middle_sum = rule.main_count * (minimum + maximum)
    bands = {
        "conservative": (0.38, 0.62),
        "balanced": (0.33, 0.68),
        "aggressive": (0.28, 0.74),
    }
    low, high = bands[preset_key]
    return {
        "odd_even": f"{odd}:{even}",
        "sum_min": int(middle_sum * low),
        "sum_max": int(middle_sum * high),
    }


def _strategy_diagnostics(
    conditions: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    active = [
        key
        for key, value in conditions.items()
        if key != "count" and value not in (None, "", [], 0, 99)
    ]
    return {
        "preset_label": normalized["label"],
        "condition_count": len(active),
        "active_conditions": active,
    }


def _baseline_candidates(
    game_key: str,
    draws: list[dict[str, Any]],
    count: int,
    seed_text: str = "",
) -> list[dict[str, Any]]:
    return [
        _baseline_candidate(game_key, f"{seed_text}:{len(draws)}:{index}", index)
        for index in range(count)
    ]


def _baseline_candidate(game_key: str, seed_text: str, offset: int) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    main = _deterministic_numbers(list(rule.main_range), rule.main_count, seed_text, offset, rule.allow_repeat)
    special = (
        _deterministic_numbers(list(rule.special_range or []), rule.special_count, seed_text, offset + 7, False)
        if rule.special_count
        else []
    )
    return {
        "main": main,
        "special": special,
        "score": 0,
        "tags": ["随机基准"],
    }


def _deterministic_numbers(
    pool: list[int],
    pick_count: int,
    seed_text: str,
    offset: int,
    allow_repeat: bool,
) -> list[int]:
    if not pool or pick_count <= 0:
        return []
    seed = sum((index + 1) * ord(char) for index, char in enumerate(seed_text)) + offset * 17
    if allow_repeat:
        return [pool[(seed + index * 3) % len(pool)] for index in range(pick_count)]
    rotated = pool[seed % len(pool) :] + pool[: seed % len(pool)]
    return sorted(rotated[:pick_count])


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


def _hit_distribution(rows: list[dict[str, Any]]) -> list[dict[str, int]]:
    counts = Counter(row["main_hits"] for row in rows)
    return [{"hits": hits, "count": counts[hits]} for hits in sorted(counts)]


def _average(values: Any) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _require_game(game_key: str) -> str:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise ValueError(f"unsupported game_key: {game}")
    return game
