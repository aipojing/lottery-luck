from __future__ import annotations

from collections import Counter
import re
from typing import Any


ALLOWED_WINDOWS = {30, 60, 120}
POSITIONS = {0: "百位", 1: "十位", 2: "个位"}
GROUP_TYPES = ["豹子", "组三", "组六"]
PRIME_DIGITS = {2, 3, 5, 7}
INVALID_3D_DATA = "invalid 3d data"
RED_NUMBERS_PATTERN = re.compile(r"^[0-9],[0-9],[0-9]$")


def number_attributes(numbers: list[int]) -> dict[str, Any]:
    digits = _require_digit_list(numbers)
    unique_count = len(set(digits))
    total = sum(digits)
    odd_count = sum(1 for digit in digits if digit % 2 == 1)
    big_count = sum(1 for digit in digits if digit >= 5)
    mod_counts = [0, 0, 0]
    for digit in digits:
        mod_counts[digit % 3] += 1
    prime_count = sum(1 for digit in digits if digit in PRIME_DIGITS)
    sorted_unique = sorted(set(digits))

    return {
        "numbers": list(digits),
        "number_text": _format_number_text(digits),
        "sum": total,
        "sum_tail": total % 10,
        "span": max(digits) - min(digits),
        "group_type": _group_type(unique_count),
        "odd_even": f"{odd_count}:{3 - odd_count}",
        "odd_count": odd_count,
        "even_count": 3 - odd_count,
        "big_small": f"{big_count}:{3 - big_count}",
        "big_count": big_count,
        "small_count": 3 - big_count,
        "mod3": ":".join(str(count) for count in mod_counts),
        "mod3_counts": {"0": mod_counts[0], "1": mod_counts[1], "2": mod_counts[2]},
        "prime_composite": f"{prime_count}:{3 - prime_count}",
        "prime_count": prime_count,
        "composite_count": 3 - prime_count,
        "unique_count": unique_count,
        "repeat_count": 3 - unique_count,
        "consecutive_pairs": [
            [first, second]
            for first, second in zip(sorted_unique, sorted_unique[1:])
            if second - first == 1
        ],
        "adjacent_pairs": [
            [index, index + 1]
            for index in range(2)
            if abs(digits[index] - digits[index + 1]) == 1
        ],
    }


def query_number(
    number_text: str,
    draws: list[dict[str, Any]],
    window: int,
) -> dict[str, Any]:
    """Look a number up in `draws`, which the caller already limited to `window` draws.

    The position stats are computed over that same window, and the payload reports both
    the window and the sample size they really came from: a caller that fetched fewer
    draws than the window (short history) must never be told otherwise.
    """
    numbers = _parse_number_text(number_text)
    parsed_draws = _parse_draws(draws)
    target_counter = Counter(numbers)

    exact_matches: list[tuple[int, dict[str, Any]]] = []
    group_matches: list[tuple[int, dict[str, Any]]] = []
    for index, parsed in enumerate(parsed_draws):
        draw_numbers = parsed["numbers"]
        if draw_numbers == numbers:
            exact_matches.append((index, parsed))
        if Counter(draw_numbers) == target_counter:
            group_matches.append((index, parsed))

    position_stats = build_position_stats(draws, window)
    position_digits = {
        str(position): position_stats["positions"][str(position)]["digits"][str(digit)]
        for position, digit in enumerate(numbers)
    }

    return {
        "number_text": number_text,
        "numbers": numbers,
        "attributes": number_attributes(numbers),
        "history": {
            "exact": {
                "count": len(exact_matches),
                "latest": _latest_match(exact_matches),
            },
            "group": {
                "count": len(group_matches),
                "latest": _latest_match(group_matches),
            },
        },
        "position_stats_window": position_stats["window"],
        "position_stats_sample_size": position_stats["sample_size"],
        "position_digits": position_digits,
        "freshness": position_stats["freshness"],
    }


def build_position_stats(draws: list[dict[str, Any]], window: int) -> dict[str, Any]:
    normalized_window = _require_window(window)
    parsed_draws = _parse_draws(_require_draws(draws)[:normalized_window])
    sample_size = len(parsed_draws)
    latest = parsed_draws[0] if parsed_draws else None

    positions: dict[str, Any] = {}
    for position, label in POSITIONS.items():
        frequencies = {
            digit: sum(1 for draw in parsed_draws if draw["numbers"][position] == digit)
            for digit in range(10)
        }
        minimum_frequency = min(frequencies.values(), default=0)
        maximum_frequency = max(frequencies.values(), default=0)
        digits: dict[str, Any] = {}
        for digit in range(10):
            hit_indexes = [
                index
                for index, draw in enumerate(parsed_draws)
                if draw["numbers"][position] == digit
            ]
            digits[str(digit)] = _position_digit_cell(
                position=position,
                digit=digit,
                sample_size=sample_size,
                frequency=frequencies[digit],
                hit_indexes=hit_indexes,
                minimum_frequency=minimum_frequency,
                maximum_frequency=maximum_frequency,
            )
        positions[str(position)] = {"label": label, "digits": digits}

    latest_issue = latest["issue"] if latest else ""
    latest_date = latest["draw_date"] if latest else ""
    freshness = {
        "status": "available" if latest else "empty",
        "sample_size": sample_size,
        "latest_issue": latest_issue,
        "latest_date": latest_date,
    }

    return {
        "window": normalized_window,
        "sample_size": sample_size,
        "latest_issue": latest_issue,
        "latest_date": latest_date,
        "freshness": freshness,
        # User-facing copy: plain sentences a lottery player can read. The window, the sample
        # and the disclaimer stay in it — only the engineer-speak is gone.
        "definition": (
            f"统计的是最近{normalized_window}期开奖。出次是这个数字在该位置开出过的期数；"
            "当前遗漏是它已经连续多少期没有开出，平均遗漏和最大遗漏是这段时间里两次开出之间的"
            "平均间隔和最大间隔。冷热只是按上面这些历史数据分档，历史统计不代表未来概率。"
        ),
        "positions": positions,
    }


def build_workbench_summary(
    draws: list[dict[str, Any]],
    window: int,
) -> dict[str, Any]:
    normalized_window = _require_window(window)
    parsed_draws = _parse_draws(_require_draws(draws)[:normalized_window])
    attributes = [number_attributes(draw["numbers"]) for draw in parsed_draws]
    position_stats = build_position_stats(draws, normalized_window)
    latest = parsed_draws[0] if parsed_draws else None

    return {
        "window": normalized_window,
        "sample_size": len(parsed_draws),
        "latest_draw": _summary_latest_draw(latest) if latest else None,
        "freshness": dict(position_stats["freshness"]),
        "position_stats": position_stats,
        "attribute_distributions": _attribute_distributions(attributes),
        "definition": "这里的数据只是所选期数内真实开奖号码的统计，历史统计不代表未来概率。",
    }


def recent_draw_summaries(
    draws: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    if type(limit) is not int or limit < 0:
        raise ValueError(INVALID_3D_DATA)
    parsed_draws = _parse_draws(_require_draws(draws)[:limit])
    return [
        {
            "issue": draw["issue"],
            "draw_date": draw["draw_date"],
            "number_text": draw["number_text"],
            "numbers": list(draw["numbers"]),
        }
        for draw in parsed_draws
    ]


def filter_candidates(filters: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_filters(filters)
    if normalized["sum_min"] > normalized["sum_max"] or normalized["span_min"] > normalized["span_max"]:
        return {"filters": normalized, "total": 0, "candidates": []}

    total = 0
    candidates: list[dict[str, Any]] = []
    for first in range(10):
        for second in range(10):
            for third in range(10):
                numbers = [first, second, third]
                attrs = number_attributes(numbers)
                if not _candidate_matches(numbers, attrs, normalized):
                    continue
                total += 1
                if len(candidates) < normalized["max_results"]:
                    candidates.append(
                        {
                            "number_text": attrs["number_text"],
                            "numbers": numbers,
                            "attributes": attrs,
                        }
                    )

    return {"filters": normalized, "total": total, "candidates": candidates}


def _require_digit_list(numbers: Any) -> list[int]:
    if not isinstance(numbers, list) or len(numbers) != 3:
        raise ValueError(INVALID_3D_DATA)
    if any(type(number) is not int or number < 0 or number > 9 for number in numbers):
        raise ValueError(INVALID_3D_DATA)
    return list(numbers)


def _parse_number_text(number_text: Any) -> list[int]:
    if not isinstance(number_text, str):
        raise ValueError(INVALID_3D_DATA)
    if len(number_text) != 3 or not number_text.isascii() or not number_text.isdecimal():
        raise ValueError(INVALID_3D_DATA)
    return [int(character) for character in number_text]


def _parse_draws(draws: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_parse_draw(draw) for draw in _require_draws(draws)]


def _require_draws(draws: Any) -> list[dict[str, Any]]:
    if not isinstance(draws, list):
        raise ValueError(INVALID_3D_DATA)
    return draws


def _parse_draw(draw: Any) -> dict[str, Any]:
    if not isinstance(draw, dict):
        raise ValueError(INVALID_3D_DATA)
    has_main = "main" in draw
    has_red_numbers = "red_numbers" in draw
    if not has_main and not has_red_numbers:
        raise ValueError(INVALID_3D_DATA)

    main_numbers = _require_digit_list(draw["main"]) if has_main else None
    red_numbers = _parse_red_numbers(draw["red_numbers"]) if has_red_numbers else None
    if main_numbers is not None and red_numbers is not None:
        if main_numbers != red_numbers:
            raise ValueError(INVALID_3D_DATA)
        numbers = main_numbers
    else:
        numbers = main_numbers or red_numbers
    return {
        "issue": str(draw.get("issue") or ""),
        "draw_date": str(draw.get("draw_date") or ""),
        "numbers": numbers,
        "number_text": _format_number_text(numbers),
    }


def _parse_red_numbers(value: Any) -> list[int]:
    if not isinstance(value, str) or not RED_NUMBERS_PATTERN.fullmatch(value):
        raise ValueError(INVALID_3D_DATA)
    return [int(value[0]), int(value[2]), int(value[4])]


def _require_window(window: Any) -> int:
    if type(window) is not int or window not in ALLOWED_WINDOWS:
        raise ValueError(INVALID_3D_DATA)
    return window


def _position_digit_cell(
    *,
    position: int,
    digit: int,
    sample_size: int,
    frequency: int,
    hit_indexes: list[int],
    minimum_frequency: int,
    maximum_frequency: int,
) -> dict[str, Any]:
    if sample_size == 0:
        return {
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

    segments = _omission_segments(sample_size, set(hit_indexes))
    current_omission = segments[-1]
    average_omission = round(sum(segments) / len(segments), 2)
    max_omission = max(segments)
    history_segments = segments[:-1]
    if history_segments:
        historical_percentile = round(
            100
            * sum(1 for segment in history_segments if segment <= current_omission)
            / len(history_segments),
            2,
        )
    else:
        historical_percentile = 0.0
    if maximum_frequency == minimum_frequency:
        frequency_percentile = 0.0
    else:
        frequency_percentile = round(
            (frequency - minimum_frequency) / (maximum_frequency - minimum_frequency) * 100,
            2,
        )
    omission_hotness = round((1 - current_omission / sample_size) * 100, 2)
    heat_score = round(frequency_percentile * 0.65 + omission_hotness * 0.35, 2)

    return {
        "position": position,
        "digit": digit,
        "frequency": frequency,
        "current_omission": current_omission,
        "average_omission": average_omission,
        "max_omission": max_omission,
        "historical_percentile": historical_percentile,
        "frequency_percentile": frequency_percentile,
        "omission_hotness": omission_hotness,
        "heat_score": heat_score,
        "heat": _heat_label(heat_score),
    }


def _omission_segments(sample_size: int, hit_indexes: set[int]) -> list[int]:
    if not hit_indexes:
        return [sample_size]
    segments: list[int] = []
    previous_hit = -1
    chronological_hit_indexes = sorted(sample_size - 1 - index for index in hit_indexes)
    for index in chronological_hit_indexes:
        segments.append(index - previous_hit - 1)
        previous_hit = index
    segments.append(sample_size - previous_hit - 1)
    return segments


def _heat_label(score: float) -> str:
    if score >= 75:
        return "hot"
    if score >= 55:
        return "warm"
    if score >= 35:
        return "neutral"
    if score >= 20:
        return "cool"
    return "cold"


def _latest_match(matches: list[tuple[int, dict[str, Any]]]) -> dict[str, Any] | None:
    if not matches:
        return None
    index, parsed = matches[0]
    return {
        "index": index,
        "issue": parsed["issue"],
        "draw_date": parsed["draw_date"],
        "numbers": list(parsed["numbers"]),
        "number_text": parsed["number_text"],
    }


def _summary_latest_draw(parsed: dict[str, Any]) -> dict[str, Any]:
    numbers = list(parsed["numbers"])
    return {
        "issue": parsed["issue"],
        "draw_date": parsed["draw_date"],
        "numbers": numbers,
        "number_text": parsed["number_text"],
        "attributes": number_attributes(numbers),
    }


def _attribute_distributions(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "group_type": _label_rows(
            (attrs["group_type"] for attrs in attributes),
            preferred_order=GROUP_TYPES,
        ),
        "sum": _value_rows(attrs["sum"] for attrs in attributes),
        "sum_tail": _value_rows(attrs["sum_tail"] for attrs in attributes),
        "span": _value_rows(attrs["span"] for attrs in attributes),
        "odd_even": _label_rows(attrs["odd_even"] for attrs in attributes),
        "big_small": _label_rows(attrs["big_small"] for attrs in attributes),
        "mod3": _label_rows(attrs["mod3"] for attrs in attributes),
        "prime_composite": _label_rows(attrs["prime_composite"] for attrs in attributes),
        "repeat_count": _value_rows(attrs["repeat_count"] for attrs in attributes),
        "consecutive_pair_count": _value_rows(
            len(attrs["consecutive_pairs"]) for attrs in attributes
        ),
        "adjacent_pair_count": _value_rows(len(attrs["adjacent_pairs"]) for attrs in attributes),
    }


def _label_rows(
    labels: Any,
    preferred_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    counter = Counter(labels)
    if preferred_order:
        ordered = preferred_order + sorted(set(counter) - set(preferred_order))
    else:
        ordered = sorted(counter)
    return [{"label": label, "count": counter[label]} for label in ordered if counter[label] > 0]


def _value_rows(values: Any) -> list[dict[str, Any]]:
    counter = Counter(values)
    return [{"value": value, "count": counter[value]} for value in sorted(counter)]


def _normalize_filters(filters: Any) -> dict[str, Any]:
    if type(filters) is not dict:
        raise ValueError(INVALID_3D_DATA)
    raw = filters
    allowed_keys = {
        "sum_min",
        "sum_max",
        "span_min",
        "span_max",
        "types",
        "odd_counts",
        "big_counts",
        "position_include",
        "position_exclude",
        "max_results",
    }
    if set(raw) - allowed_keys:
        raise ValueError(INVALID_3D_DATA)

    return {
        "sum_min": _filter_int(raw.get("sum_min", 0), 0, 27),
        "sum_max": _filter_int(raw.get("sum_max", 27), 0, 27),
        "span_min": _filter_int(raw.get("span_min", 0), 0, 9),
        "span_max": _filter_int(raw.get("span_max", 9), 0, 9),
        "types": _filter_types(raw.get("types", GROUP_TYPES)),
        "odd_counts": _filter_counts(raw.get("odd_counts", [0, 1, 2, 3])),
        "big_counts": _filter_counts(raw.get("big_counts", [0, 1, 2, 3])),
        "position_include": _filter_positions(raw.get("position_include", {})),
        "position_exclude": _filter_positions(raw.get("position_exclude", {})),
        "max_results": _filter_int(raw.get("max_results", 100), 1, 200),
    }


def _filter_int(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise ValueError(INVALID_3D_DATA)
    return value


def _filter_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(INVALID_3D_DATA)
    result: list[str] = []
    for item in value:
        if item not in GROUP_TYPES:
            raise ValueError(INVALID_3D_DATA)
        if item not in result:
            result.append(item)
    return result


def _filter_counts(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(INVALID_3D_DATA)
    result: list[int] = []
    for item in value:
        if type(item) is not int or item < 0 or item > 3:
            raise ValueError(INVALID_3D_DATA)
        if item not in result:
            result.append(item)
    return sorted(result)


def _filter_positions(value: Any) -> dict[str, list[int]]:
    if not isinstance(value, dict):
        raise ValueError(INVALID_3D_DATA)
    result: dict[str, list[int]] = {}
    for position, digits in value.items():
        if position not in {"0", "1", "2"} or not isinstance(digits, list):
            raise ValueError(INVALID_3D_DATA)
        normalized_digits: list[int] = []
        for digit in digits:
            if type(digit) is not int or digit < 0 or digit > 9:
                raise ValueError(INVALID_3D_DATA)
            if digit not in normalized_digits:
                normalized_digits.append(digit)
        result[position] = sorted(normalized_digits)
    return result


def _candidate_matches(
    numbers: list[int],
    attrs: dict[str, Any],
    filters: dict[str, Any],
) -> bool:
    if attrs["sum"] < filters["sum_min"] or attrs["sum"] > filters["sum_max"]:
        return False
    if attrs["span"] < filters["span_min"] or attrs["span"] > filters["span_max"]:
        return False
    if attrs["group_type"] not in filters["types"]:
        return False
    if attrs["odd_count"] not in filters["odd_counts"]:
        return False
    if attrs["big_count"] not in filters["big_counts"]:
        return False
    for position, allowed_digits in filters["position_include"].items():
        if numbers[int(position)] not in allowed_digits:
            return False
    for position, excluded_digits in filters["position_exclude"].items():
        if numbers[int(position)] in excluded_digits:
            return False
    return True


def _group_type(unique_count: int) -> str:
    if unique_count == 1:
        return "豹子"
    if unique_count == 2:
        return "组三"
    return "组六"


def _format_number_text(numbers: list[int]) -> str:
    return "".join(str(number) for number in numbers)


__all__ = [
    "number_attributes",
    "query_number",
    "build_position_stats",
    "build_workbench_summary",
    "recent_draw_summaries",
    "filter_candidates",
]
