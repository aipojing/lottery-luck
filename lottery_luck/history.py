from collections import Counter
from typing import Any

from .rules import GAME_RULES, parse_numbers


def _weighted_increment(index: int) -> float:
    return 1.0 / (1.0 + index / 40.0)


def build_history_profile(game_key: str, draws: list[dict[str, Any]]) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    main_frequency = Counter({n: 0 for n in rule.main_range})
    main_weighted = Counter({n: 0.0 for n in rule.main_range})
    special_frequency = Counter({n: 0 for n in rule.special_range or []})
    position_frequency: dict[int, Counter[int]] = {
        position: Counter({n: 0 for n in rule.main_range})
        for position in range(rule.draw_main_count)
    }
    last_seen = {n: None for n in rule.main_range}

    for index, draw in enumerate(draws):
        parsed = parse_numbers(game_key, draw["red_numbers"], draw.get("blue_number") or "")
        for pos, number in enumerate(parsed["main"]):
            if pos >= rule.draw_main_count:
                break
            if number not in main_frequency:
                continue
            main_frequency[number] += 1
            main_weighted[number] += _weighted_increment(index)
            position_frequency[pos][number] += 1
            if last_seen.get(number) is None:
                last_seen[number] = index
        for number in parsed["special"]:
            special_frequency[number] += 1

    omission = {
        number: (last_seen[number] if last_seen[number] is not None else len(draws))
        for number in rule.main_range
    }
    hot_main = [number for number, _ in main_frequency.most_common(10)]
    cold_main = sorted(rule.main_range, key=lambda n: main_frequency[n])[:10]

    return {
        "draw_count": len(draws),
        "main_frequency": dict(main_frequency),
        "main_weighted": dict(main_weighted),
        "main_omission": omission,
        "special_frequency": dict(special_frequency),
        "position_frequency": {pos: dict(counter) for pos, counter in position_frequency.items()},
        "hot_main": hot_main,
        "cold_main": cold_main,
    }
