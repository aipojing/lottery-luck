from __future__ import annotations

from typing import Any

from .rules import GAME_RULES, parse_numbers


def review_prediction(
    game_key: str,
    latest_draws: list[dict[str, Any]],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise ValueError(f"unsupported game_key: {game}")

    predicted_main = _normalize_numbers(prediction.get("main"))
    predicted_special = _normalize_numbers(prediction.get("special"))
    fortune_eye = _normalize_eye(prediction.get("fortune_eye"), predicted_special, predicted_main)

    if not latest_draws:
        return {
            "game_key": game,
            "status": "pending",
            "latest_draw": None,
            "main_hits": [],
            "special_hits": [],
            "hit_count": 0,
            "fortune_eye_hit": False,
            "summary": "等待开奖数据更新后复盘。先把这组号留住，开奖后再看财眼是否应验。",
        }

    latest = latest_draws[0]
    parsed = parse_numbers(
        game,
        str(latest.get("red_numbers") or ""),
        str(latest.get("blue_number") or ""),
    )
    main_hits = [number for number in predicted_main if number in set(parsed["main"])]
    special_hits = [number for number in predicted_special if number in set(parsed["special"])]
    fortune_eye_hit = fortune_eye in set(parsed["main"] + parsed["special"])
    hit_count = len(main_hits) + len(special_hits)

    return {
        "game_key": game,
        "status": "reviewed",
        "latest_draw": {
            "issue": str(latest.get("issue") or ""),
            "draw_date": str(latest.get("draw_date") or ""),
            "main": parsed["main"],
            "special": parsed["special"],
        },
        "main_hits": main_hits,
        "special_hits": special_hits,
        "hit_count": hit_count,
        "fortune_eye_hit": fortune_eye_hit,
        "summary": _summary(hit_count, fortune_eye_hit),
    }


def _normalize_numbers(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _normalize_eye(value: Any, special: list[int], main: list[int]) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        if special:
            return special[-1]
        if main:
            return main[-1]
    return None


def _summary(hit_count: int, fortune_eye_hit: bool) -> str:
    if hit_count <= 0:
        return "本期未命中，说明这组号更多是避冲守势，下次可换偏财号提高变化感。"
    if fortune_eye_hit:
        return f"本期命中 {hit_count} 个，财眼也落点，说明这组号的核心气口有应验。"
    return f"本期命中 {hit_count} 个，财眼未中但主号有贴合，可作为下一期调号参考。"
