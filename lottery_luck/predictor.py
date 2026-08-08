from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from math import isfinite
from typing import Any

from .ai_features import AiFeature, NullAiProvider, neutral_ai_feature
from .history import build_history_profile
from .personal import (
    DIGIT_ELEMENT,
    ELEMENTS,
    PersonalInput,
    birth_vector,
    mod_match,
    normalize_vector,
    personal_score_for_number,
    stable_int,
)
from .repository import LotteryRepository
from .rules import GAME_RULES, candidate_draw_dates
from .settings import get_metaphysics_weights


RECOMMENDATION_WEIGHTS = {
    "personal_space": 40,
    "ai_fortune": 25,
    "draw_day_luck": 20,
    "history_guardrail": 15,
}

ELEMENT_LABELS = {
    "wood": "木",
    "fire": "火",
    "earth": "土",
    "metal": "金",
    "water": "水",
}

FORTUNE_DIRECTIONS = ("正东", "东南", "正南", "西南", "正西", "西北", "正北", "东北")
FORTUNE_HOURS = (
    "子时",
    "丑时",
    "寅时",
    "卯时",
    "辰时",
    "巳时",
    "午时",
    "未时",
    "申时",
    "酉时",
    "戌时",
    "亥时",
)

WEALTH_ELEMENT = {
    "wood": "earth",
    "fire": "metal",
    "earth": "water",
    "metal": "wood",
    "water": "fire",
}

SUPPORT_ELEMENT = {
    "wood": "water",
    "fire": "wood",
    "earth": "fire",
    "metal": "earth",
    "water": "metal",
}

CLASH_ELEMENT = {
    "wood": "metal",
    "fire": "water",
    "earth": "wood",
    "metal": "fire",
    "water": "earth",
}

PATTERN_META = {
    "wood": {
        "name": "木旺生财",
        "reading": "机会感强，容易看到新入口，但财气怕散。",
        "hook": "机会开得多，关键在把散财收成一条线",
        "position": "引财位",
    },
    "fire": {
        "name": "火旺财浮",
        "reading": "热度和冲劲足，财气来得快，也容易花得快。",
        "hook": "财气起得快，关键在降火后再收财",
        "position": "聚财位",
    },
    "earth": {
        "name": "土厚守财",
        "reading": "底盘稳，适合稳中取财，但需要给机会留出口。",
        "hook": "底盘不弱，关键在给财气留一个流动口",
        "position": "守财位",
    },
    "metal": {
        "name": "金明取财",
        "reading": "判断利落，适合少而准，不宜把盘面铺得太满。",
        "hook": "判断感够准，关键在少取不杂、以财眼收束",
        "position": "断财位",
    },
    "water": {
        "name": "水旺流财",
        "reading": "灵感和流动性强，财气能动，但需要定数落袋。",
        "hook": "灵感不缺，关键在让流动财气落到定数上",
        "position": "流财位",
    },
}

FORTUNE_MODE_PROFILES = {
    "steady": {
        "label": "稳财号",
        "tone": "稳中取财",
        "description": "优先保持个人时空、开奖日气口和数据托底的均衡，适合稳妥型合参。",
        "weights": {
            "personal_space": 40,
            "ai_fortune": 25,
            "draw_day_luck": 20,
            "history_guardrail": 15,
        },
    },
    "windfall": {
        "label": "偏财号",
        "tone": "顺势取财",
        "description": "更看重开奖日气口和 AI 命理偏好，适合想要更强变化感的合参。",
        "weights": {
            "personal_space": 32,
            "ai_fortune": 28,
            "draw_day_luck": 30,
            "history_guardrail": 10,
        },
    },
    "guard": {
        "label": "守财号",
        "tone": "收口守财",
        "description": "更看重个人时空和历史托底，适合保守、少冲突的合参。",
        "weights": {
            "personal_space": 45,
            "ai_fortune": 18,
            "draw_day_luck": 12,
            "history_guardrail": 25,
        },
    },
}


class PredictionEngine:
    def __init__(self, repo: LotteryRepository, ai_provider: Any) -> None:
        self.repo = repo
        self.ai_provider = ai_provider or NullAiProvider()

    def predict(
        self,
        game_key: str,
        personal: PersonalInput,
        today: str | None = None,
        fortune_mode: str = "steady",
    ) -> dict[str, Any]:
        game = game_key.strip().lower()
        if game not in GAME_RULES:
            raise ValueError(f"unsupported game_key: {game}")
        rule = GAME_RULES[game]
        current_day = today or date.today().isoformat()
        mode_key = _normalize_fortune_mode(fortune_mode)
        mode_profile = _mode_profile(mode_key)

        all_draws = self.repo.all_draws(game)
        recent_draws = self.repo.recent_draws(game, limit=5)
        profile = build_history_profile(game, all_draws)
        best_draw_date = self._best_draw_date(game, personal, current_day, mode_key)
        ai_feature = self._extract_ai_feature(game, personal, best_draw_date, mode_key)
        metaphysics_profile = self._metaphysics_profile(personal, ai_feature, best_draw_date)

        main_scores = self._main_scores(game, personal, best_draw_date, profile, ai_feature, mode_key)
        if rule.allow_repeat:
            main_numbers, selected_scores = self._select_position_numbers(
                game, personal, best_draw_date, profile, ai_feature, mode_key
            )
        else:
            ranked = sorted(
                main_scores.items(),
                key=lambda item: (
                    -item[1],
                    self._tie_breaker(game, personal, f"{best_draw_date}|{mode_key}", item[0]),
                ),
            )
            main_numbers = sorted(number for number, _ in ranked[: rule.main_count])
            selected_scores = [main_scores[number] for number in main_numbers]

        special_numbers = self._select_special_numbers(
            game, personal, best_draw_date, profile, ai_feature, mode_key, main_numbers
        )
        if special_numbers:
            selected_scores.extend(
                self._special_score(game, personal, best_draw_date, profile, ai_feature, number, mode_key)
                for number in special_numbers
            )
        number_reasons = self._number_reasons(
            game,
            personal,
            best_draw_date,
            profile,
            ai_feature,
            metaphysics_profile,
            mode_profile,
            mode_key,
            main_numbers,
            special_numbers,
        )
        fortune_report = _fortune_report(
            game,
            personal,
            best_draw_date,
            metaphysics_profile,
            mode_profile,
            main_numbers,
            special_numbers,
            number_reasons,
        )
        avoid_numbers = self._avoid_numbers(
            game,
            personal,
            best_draw_date,
            metaphysics_profile,
            main_numbers,
            special_numbers,
            mode_key,
        )
        daily_fortune_sign = _daily_fortune_sign(
            personal,
            best_draw_date,
            metaphysics_profile,
            ai_feature,
        )
        ritual_steps = _ritual_steps(
            metaphysics_profile,
            daily_fortune_sign,
            main_numbers,
            special_numbers,
            avoid_numbers,
        )
        master_ritual = _master_ritual(
            personal,
            best_draw_date,
            metaphysics_profile,
            mode_profile,
            daily_fortune_sign,
            main_numbers,
            special_numbers,
            avoid_numbers,
        )

        return {
            "game_key": game,
            "fortune_mode": mode_key,
            "mode_profile": mode_profile,
            "best_draw_date": best_draw_date,
            "luck_score": round(_mean(selected_scores), 2),
            "numbers": {"main": main_numbers, "special": special_numbers},
            "recommendation_basis": _recommendation_basis(mode_key),
            "ritual_summary": _ritual_summary(ai_feature, best_draw_date),
            "fortune_hook": _fortune_hook(metaphysics_profile, mode_profile),
            "interpretation_layers": _interpretation_layers(
                metaphysics_profile,
                mode_profile,
                main_numbers,
                special_numbers,
            ),
            "metaphysics_profile": metaphysics_profile,
            "avoid_numbers": avoid_numbers,
            "daily_fortune_sign": daily_fortune_sign,
            "ritual_steps": ritual_steps,
            "master_ritual": master_ritual,
            "credibility_chain": _credibility_chain(
                metaphysics_profile,
                mode_profile,
                main_numbers,
                special_numbers,
            ),
            "fortune_report": fortune_report,
            "number_reasons": number_reasons,
            "history_basis": {
                "draw_count": profile["draw_count"],
                "hot_main": profile["hot_main"],
                "cold_main": profile["cold_main"],
            },
            "personal_basis": {
                "ai_enabled": ai_feature.enabled,
                "ai_explanation": ai_feature.explanation,
                "ai_lucky_themes": ai_feature.lucky_themes,
                "ai_confidence": ai_feature.confidence,
            },
            "recent_draws": recent_draws,
            "disclaimer": "本结果仅供娱乐推荐和玄学合参，不构成投注建议。",
        }

    def _best_draw_date(
        self, game_key: str, personal: PersonalInput, today: str, fortune_mode: str = "steady"
    ) -> str:
        candidates = candidate_draw_dates(game_key, today, 30)
        if not candidates:
            return today

        rule = GAME_RULES[game_key]

        def date_score(draw_date: date) -> float:
            draw = draw_date.isoformat()
            scores = [
                personal_score_for_number(personal, game_key, number, draw)
                for number in rule.main_range
            ]
            return _mean(sorted(scores, reverse=True)[: rule.main_count])

        best = max(
            candidates,
            key=lambda draw_date: (
                date_score(draw_date),
                -stable_int(
                    "|".join(
                        (
                            game_key,
                            fortune_mode,
                            personal.name,
                            personal.birth_date,
                            personal.calendar_type,
                            personal.birth_hour,
                            personal.birth_place,
                            personal.current_city,
                            draw_date.isoformat(),
                        )
                    )
                ),
            ),
        )
        return best.isoformat()

    def _extract_ai_feature(
        self, game_key: str, personal: PersonalInput, best_draw_date: str, fortune_mode: str = "steady"
    ) -> AiFeature:
        context = {
            "game_key": game_key,
            "fortune_mode": fortune_mode,
            "best_draw_date": best_draw_date,
            "personal_features": {
                "birth_vector": birth_vector(personal),
                "birth_hour_known": personal.birth_hour != "unknown",
                "calendar_type": personal.calendar_type,
                "location_relation": _location_relation(
                    personal.birth_place,
                    personal.current_city,
                ),
            },
        }
        try:
            feature = self.ai_provider.extract(context)
        except Exception:
            return neutral_ai_feature()
        if not isinstance(feature, AiFeature):
            return neutral_ai_feature()
        return feature

    def _main_scores(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        fortune_mode: str = "steady",
    ) -> dict[int, float]:
        history_scores = _history_scores(game_key, profile)
        return {
            number: self._combined_score(
                game_key, personal, draw_date, ai_feature, number, history_scores[number], fortune_mode
            )
            for number in GAME_RULES[game_key].main_range
        }

    def _combined_score(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        ai_feature: AiFeature,
        number: int,
        history_score: float,
        fortune_mode: str = "steady",
    ) -> float:
        digit = number % 10
        ai_score = ai_feature.score_for_digit(digit, DIGIT_ELEMENT[digit])
        personal_score = personal_score_for_number(
            personal,
            game_key,
            number,
            draw_date,
            ai_score=50.0,
        )
        day_luck_score = self._draw_day_score(game_key, personal, draw_date, number, fortune_mode)
        weights = _score_weights(fortune_mode)
        return round(
            personal_score * weights["personal_space"]
            + ai_score * weights["ai_fortune"]
            + day_luck_score * weights["draw_day_luck"]
            + history_score * weights["history_guardrail"],
            4,
        )

    def _select_3d_numbers(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        fortune_mode: str = "steady",
    ) -> tuple[list[int], list[float]]:
        return self._select_position_numbers(game_key, personal, draw_date, profile, ai_feature, fortune_mode)

    def _select_position_numbers(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        fortune_mode: str = "steady",
    ) -> tuple[list[int], list[float]]:
        selected: list[int] = []
        selected_scores: list[float] = []
        position_frequency = profile.get("position_frequency", {})
        global_history_scores = _history_scores(game_key, profile)

        for position in range(GAME_RULES[game_key].main_count):
            position_scores = _normalize(position_frequency.get(position, {}))
            ranked = []
            for number in GAME_RULES[game_key].main_range:
                history_score = (
                    global_history_scores[number] * 0.70
                    + position_scores.get(number, 50.0) * 0.30
                )
                score = self._combined_score(
                    game_key, personal, draw_date, ai_feature, number, history_score, fortune_mode
                )
                ranked.append((number, score))
            number, score = max(
                ranked,
                key=lambda item: (
                    item[1],
                    -self._tie_breaker(game_key, personal, f"{draw_date}|{fortune_mode}|{position}", item[0]),
                ),
            )
            selected.append(number)
            selected_scores.append(score)
        return selected, selected_scores

    def _select_special_numbers(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        fortune_mode: str,
        main_numbers: list[int],
    ) -> list[int]:
        rule = GAME_RULES[game_key]
        if not rule.special_range or rule.special_count <= 0:
            return []

        excluded = set(main_numbers) if game_key == "qlc" else set()
        candidates = [number for number in rule.special_range if number not in excluded]
        ranked = sorted(
            candidates,
            key=lambda number: (
                -self._special_score(game_key, personal, draw_date, profile, ai_feature, number),
                self._tie_breaker(game_key, personal, f"{draw_date}|{fortune_mode}|special", number),
            ),
        )
        return ranked[: rule.special_count]

    def _special_score(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        number: int,
        fortune_mode: str = "steady",
    ) -> float:
        special_scores = _normalize(profile.get("special_frequency", {}))
        history_score = special_scores.get(number, 50.0)
        return self._combined_score(
            game_key, personal, draw_date, ai_feature, number, history_score, fortune_mode
        )

    def _draw_day_score(
        self, game_key: str, personal: PersonalInput, draw_date: str, number: int, fortune_mode: str = "steady"
    ) -> float:
        return mod_match(
            stable_int(
                "|".join(
                    (
                        game_key,
                        fortune_mode,
                        personal.calendar_type,
                        personal.birth_hour,
                        personal.birth_place,
                        personal.current_city,
                        draw_date,
                        "draw-day-luck",
                    )
                )
            ),
            number,
        )

    def _number_reasons(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        profile: Mapping[str, Any],
        ai_feature: AiFeature,
        metaphysics_profile: Mapping[str, Any],
        mode_profile: Mapping[str, Any],
        fortune_mode: str,
        main_numbers: list[int],
        special_numbers: list[int],
    ) -> dict[str, list[dict[str, Any]]]:
        history_scores = _history_scores(game_key, profile)
        special_scores = _normalize(profile.get("special_frequency", {}))
        return {
            "main": [
                self._number_reason(
                    game_key,
                    personal,
                    draw_date,
                    ai_feature,
                    metaphysics_profile,
                    mode_profile,
                    fortune_mode,
                    number,
                    "主号",
                    history_scores.get(number, 50.0),
                )
                for number in main_numbers
            ],
            "special": [
                self._number_reason(
                    game_key,
                    personal,
                    draw_date,
                    ai_feature,
                    metaphysics_profile,
                    mode_profile,
                    fortune_mode,
                    number,
                    "财眼",
                    special_scores.get(number, 50.0),
                )
                for number in special_numbers
            ],
        }

    def _number_reason(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        ai_feature: AiFeature,
        metaphysics_profile: Mapping[str, Any],
        mode_profile: Mapping[str, Any],
        fortune_mode: str,
        number: int,
        role: str,
        history_score: float,
    ) -> dict[str, Any]:
        score = self._combined_score(
            game_key, personal, draw_date, ai_feature, number, history_score, fortune_mode
        )
        digit = number % 10
        element = DIGIT_ELEMENT[digit]
        element_label = ELEMENT_LABELS[element]
        wealth_element = str(metaphysics_profile.get("wealth_element") or "")
        support_element = str(metaphysics_profile.get("support_element") or "")
        favorable_elements = set(metaphysics_profile.get("favorable_elements") or [])
        avoid_elements = set(metaphysics_profile.get("avoid_elements") or [])
        wealth_pattern = str(metaphysics_profile.get("wealth_pattern") or "本命财格")
        mode_label = str(mode_profile.get("label") or "财运号")
        theme = ai_feature.lucky_themes[0] if ai_feature.lucky_themes else "财气流转"
        day_score = self._draw_day_score(game_key, personal, draw_date, number, fortune_mode)
        emphasis = "开奖日气口相合" if day_score >= 55 else "用作平衡气口"
        position_label = _position_label(role, element, wealth_element, support_element, avoid_elements)
        selection_role = _selection_role(element, wealth_element, support_element, favorable_elements, avoid_elements)
        position_copy = _position_copy(position_label)
        lines = [
            f"五行角色：尾数{digit}属{element_label}，在{wealth_pattern}里属于{selection_role}。",
            f"入选原因：按{mode_label}取数，呼应{theme}，{emphasis}，综合财运分{round(score)}。",
            f"组合位置：作为{position_label}，{position_copy}",
        ]
        text = " ".join(lines)
        return {
            "number": number,
            "role": role,
            "element": element,
            "element_label": element_label,
            "score": round(score, 2),
            "position_label": position_label,
            "selection_role": selection_role,
            "lines": lines,
            "text": text,
        }

    def _metaphysics_profile(
        self,
        personal: PersonalInput,
        ai_feature: AiFeature,
        draw_date: str,
    ) -> dict[str, Any]:
        merged = _merged_element_vector(personal, ai_feature)
        dominant = max(ELEMENTS, key=lambda element: (merged[element], -ELEMENTS.index(element)))
        wealth = WEALTH_ELEMENT[dominant]
        support = SUPPORT_ELEMENT[dominant]
        avoid_elements = _unique_elements([CLASH_ELEMENT[dominant], dominant])
        favorable_elements = _unique_elements([wealth, support])
        meta = PATTERN_META[dominant]
        day_mode = _day_mode(personal, draw_date)
        favorable_labels = _element_labels(favorable_elements)
        avoid_labels = _element_labels(avoid_elements)

        if day_mode == "守":
            day_advice = f"宜守财、收口、少改号；忌{avoid_labels}过旺。"
        elif day_mode == "进":
            day_advice = f"宜顺势进财、保留一个财眼；忌{avoid_labels}连用。"
        else:
            day_advice = f"宜先筛后取、用{favorable_labels}落袋；忌临时追热。"

        selection_rule = (
            f"先取{ELEMENT_LABELS[wealth]}数定财眼，再用{ELEMENT_LABELS[support]}数托盘；"
            "历史数据只校正热冷，不主导结果。"
        )
        return {
            "wealth_pattern": str(meta["name"]),
            "dominant_element": dominant,
            "dominant_element_label": ELEMENT_LABELS[dominant],
            "wealth_element": wealth,
            "wealth_element_label": ELEMENT_LABELS[wealth],
            "support_element": support,
            "support_element_label": ELEMENT_LABELS[support],
            "favorable_elements": favorable_elements,
            "favorable_element_labels": favorable_labels,
            "avoid_elements": avoid_elements,
            "avoid_element_labels": avoid_labels,
            "day_mode": day_mode,
            "day_advice": day_advice,
            "selection_rule": selection_rule,
            "reading": str(meta["reading"]),
            "hook_phrase": str(meta["hook"]),
        }

    def _avoid_numbers(
        self,
        game_key: str,
        personal: PersonalInput,
        draw_date: str,
        metaphysics_profile: Mapping[str, Any],
        main_numbers: list[int],
        special_numbers: list[int],
        fortune_mode: str = "steady",
    ) -> list[dict[str, Any]]:
        selected = set(main_numbers + special_numbers)
        avoid_elements = set(metaphysics_profile.get("avoid_elements") or [])
        avoid_labels = str(metaphysics_profile.get("avoid_element_labels") or "冲气")
        candidates = []
        for number in GAME_RULES[game_key].main_range:
            if number in selected:
                continue
            element = DIGIT_ELEMENT[number % 10]
            if element not in avoid_elements:
                continue
            candidates.append(
                (
                    number,
                    self._draw_day_score(game_key, personal, draw_date, number),
                    self._tie_breaker(game_key, personal, f"{draw_date}|{fortune_mode}|avoid", number),
                )
            )

        if not candidates:
            candidates = [
                (
                    number,
                    self._draw_day_score(game_key, personal, draw_date, number),
                    self._tie_breaker(game_key, personal, f"{draw_date}|{fortune_mode}|avoid", number),
                )
                for number in GAME_RULES[game_key].main_range
                if number not in selected
            ]

        ranked = sorted(candidates, key=lambda item: (item[1], item[2]))
        limit = 6 if game_key == "kl8" else 4
        avoid_numbers = []
        for number, _, _ in ranked[:limit]:
            element = DIGIT_ELEMENT[number % 10]
            element_label = ELEMENT_LABELS[element]
            avoid_numbers.append(
                {
                    "number": number,
                    "element": element,
                    "element_label": element_label,
                    "reason": f"尾数{number % 10}属{element_label}，本期与{avoid_labels}过旺相叠，先不入局。",
                }
            )
        return avoid_numbers

    def _tie_breaker(
        self, game_key: str, personal: PersonalInput, draw_date: str, number: int
    ) -> int:
        return stable_int(
            "|".join(
                (
                    game_key,
                    personal.name,
                    personal.birth_date,
                    personal.calendar_type,
                    personal.birth_hour,
                    personal.birth_place,
                    personal.current_city,
                    draw_date,
                    str(number),
                )
            )
        )


def _history_scores(game_key: str, profile: Mapping[str, Any]) -> dict[int, float]:
    rule = GAME_RULES[game_key]
    frequency = _normalize(profile.get("main_frequency", {}))
    weighted = _normalize(profile.get("main_weighted", {}))
    omission = _normalize(profile.get("main_omission", {}))

    return {
        number: round(
            frequency.get(number, 50.0) * 0.4
            + weighted.get(number, 50.0) * 0.4
            + omission.get(number, 50.0) * 0.2,
            4,
        )
        for number in rule.main_range
    }


def _merged_element_vector(personal: PersonalInput, ai_feature: AiFeature) -> dict[str, float]:
    personal_vector = birth_vector(personal)
    if not ai_feature.enabled:
        return personal_vector

    ai_vector = normalize_vector(ai_feature.element_bias)
    confidence = max(0.0, min(0.35, ai_feature.confidence * 0.35))
    return normalize_vector(
        {
            element: personal_vector[element] * (1.0 - confidence)
            + ai_vector[element] * confidence
            for element in ELEMENTS
        }
    )


def _normalize_fortune_mode(fortune_mode: str) -> str:
    mode = str(fortune_mode or "").strip().lower()
    return mode if mode in FORTUNE_MODE_PROFILES else "steady"


def _mode_profile(fortune_mode: str) -> dict[str, Any]:
    mode = _normalize_fortune_mode(fortune_mode)
    profile = FORTUNE_MODE_PROFILES[mode]
    return {
        "key": mode,
        "label": profile["label"],
        "tone": profile["tone"],
        "description": profile["description"],
        "weights": _raw_score_weights(mode),
    }


def _score_weights(fortune_mode: str) -> dict[str, float]:
    weights = _raw_score_weights(fortune_mode)
    total = sum(float(value) for value in weights.values()) or 100.0
    return {key: float(value) / total for key, value in weights.items()}


def _location_relation(birth_place: str, current_city: str) -> str:
    birth = _normalized_location_text(birth_place)
    current = _normalized_location_text(current_city)
    if not birth or not current:
        return "incomplete"
    return "same" if birth == current else "different"


def _normalized_location_text(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _raw_score_weights(fortune_mode: str) -> dict[str, int]:
    mode = _normalize_fortune_mode(fortune_mode)
    defaults = FORTUNE_MODE_PROFILES[mode]["weights"]
    configured = get_metaphysics_weights().get(mode, {})
    return {
        key: int(configured.get(key, defaults[key]))
        for key in defaults
    }


def _fortune_hook(profile: Mapping[str, Any], mode_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    pattern = str(profile.get("wealth_pattern") or "本命财格")
    hook_phrase = str(profile.get("hook_phrase") or "财气需要先聚后取")
    favorable = str(profile.get("favorable_element_labels") or "喜用数")
    avoid = str(profile.get("avoid_element_labels") or "冲气")
    day_mode = str(profile.get("day_mode") or "守")
    day_advice = str(profile.get("day_advice") or "宜守财，忌追热。")
    mode_label = str((mode_profile or {}).get("label") or "稳财号")
    return {
        "headline": f"你这盘不是缺财气，而是{hook_phrase}。",
        "subline": f"本命财格：{pattern}，本期按{mode_label}用{favorable}入局；{day_advice}",
        "tags": [
            f"本命财格 {pattern}",
            f"模式 {mode_label}",
            f"今日宜 {day_mode}财",
            f"避开 {avoid}过旺",
        ],
    }


def _element_tail_digits(elements: list[str]) -> list[int]:
    tails: list[int] = []
    wanted = set(elements)
    for digit, element in DIGIT_ELEMENT.items():
        if element in wanted and digit not in tails:
            tails.append(digit)
    return tails


def _daily_fortune_sign(
    personal: PersonalInput,
    draw_date: str,
    profile: Mapping[str, Any],
    ai_feature: AiFeature,
) -> dict[str, Any]:
    seed = stable_int(
        "|".join(
            (
                personal.name,
                personal.birth_date,
                personal.birth_hour,
                personal.birth_place,
                personal.current_city,
                draw_date,
                "daily-sign",
            )
        )
    )
    direction = FORTUNE_DIRECTIONS[seed % len(FORTUNE_DIRECTIONS)]
    lucky_hour = FORTUNE_HOURS[(seed // len(FORTUNE_DIRECTIONS)) % len(FORTUNE_HOURS)]
    lucky_tails = _element_tail_digits(list(profile.get("favorable_elements") or []))
    avoid_tails = _element_tail_digits(list(profile.get("avoid_elements") or []))

    for tail in _ai_lucky_tail_digits(ai_feature):
        if tail not in lucky_tails:
            lucky_tails.append(tail)

    if not lucky_tails:
        lucky_tails.append(seed % 10)
    if not avoid_tails:
        avoid_tails.append((seed // 10) % 10)

    lucky_label = _tail_digit_label(lucky_tails)
    avoid_label = _tail_digit_label(avoid_tails)
    return {
        "headline": f"今日偏财气在{direction}，旺时{lucky_hour}，宜取 {lucky_label} 尾，避 {avoid_label} 冲。",
        "direction": direction,
        "lucky_hour": lucky_hour,
        "lucky_tails": lucky_tails,
        "avoid_tails": avoid_tails,
        "tags": [
            f"{direction}财位",
            f"旺时 {lucky_hour}",
            f"尾 {lucky_label} · 避 {avoid_label}",
        ],
    }


def _ai_lucky_tail_digits(ai_feature: AiFeature) -> list[int]:
    if not ai_feature.enabled:
        return []

    neutral_bias = 1.0 / 10.0
    ranked: list[tuple[int, float]] = []
    seen: set[int] = set()
    for digit_key, bias_value in ai_feature.digit_bias.items():
        try:
            digit = int(digit_key) % 10
            bias = float(bias_value)
        except (TypeError, ValueError):
            continue
        if digit in seen or not isfinite(bias) or bias <= neutral_bias:
            continue
        ranked.append((digit, bias))
        seen.add(digit)

    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [digit for digit, _ in ranked[:2]]


def _ritual_steps(
    profile: Mapping[str, Any],
    sign: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
    avoid_numbers: list[dict[str, Any]],
) -> list[dict[str, str]]:
    pattern = str(profile.get("wealth_pattern") or "本命财格")
    direction = str(sign.get("direction") or "--")
    eye_number = special_numbers[-1] if special_numbers else (main_numbers[-1] if main_numbers else None)
    if eye_number is None:
        eye_summary = "财眼暂未落号，保持主号顺序。"
    else:
        eye_summary = f"财眼落在 {eye_number:02d}，取尾 {eye_number % 10} 收束财气。"

    avoid_preview = "、".join(f"{item['number']:02d}" for item in avoid_numbers[:3])
    avoid_summary = (
        f"先避开 {avoid_preview}，减少冲气叠加。"
        if avoid_preview
        else "本期无额外避冲号。"
    )
    return [
        {
            "key": "wealth_pattern",
            "label": "定本命财盘",
            "summary": f"本盘先按{pattern}定主线。",
        },
        {
            "key": "fortune_direction",
            "label": "定今日财局",
            "summary": f"今日偏财气落在{direction}。",
        },
        {
            "key": "fortune_eye",
            "label": "取财眼尾数",
            "summary": eye_summary,
        },
        {
            "key": "avoid_clash",
            "label": "避冲煞号",
            "summary": avoid_summary,
        },
        {
            "key": "final_numbers",
            "label": "落财运号",
            "summary": f"最终落到 {_format_number_path(main_numbers, special_numbers)}。",
        },
    ]


def _interpretation_layers(
    profile: Mapping[str, Any],
    mode_profile: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
) -> dict[str, str]:
    pattern = str(profile.get("wealth_pattern") or "本命财格")
    hook_phrase = str(profile.get("hook_phrase") or "财气需要先聚后取")
    favorable = str(profile.get("favorable_element_labels") or "喜用数")
    avoid = str(profile.get("avoid_element_labels") or "冲气")
    day_advice = str(profile.get("day_advice") or "宜守财，忌追热。")
    selection_rule = str(profile.get("selection_rule") or "先定财眼，再定主号。")
    mode_label = str(mode_profile.get("label") or "稳财号")
    number_path = _format_number_path(main_numbers, special_numbers)
    return {
        "short_hook": f"{pattern}不是缺财，而是{hook_phrase}。",
        "long_reading": (
            f"这组按{mode_label}生成：先看本命财格为{pattern}，再取{favorable}补财气，"
            f"同时避开{avoid}过旺。{day_advice}{selection_rule}最终落到{number_path}。"
        ),
    }


def _credibility_chain(
    profile: Mapping[str, Any],
    mode_profile: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
) -> list[dict[str, str]]:
    numbers = main_numbers + special_numbers
    tail_labels = _tail_element_summary(numbers)
    number_detail = _format_number_path(main_numbers, special_numbers)
    return [
        {
            "title": "个人时空",
            "text": "出生日期、时辰和所在城市共同形成本次基础盘。",
            "detail": "用于确定本次取号方向。",
        },
        {
            "title": "本命财格",
            "text": f"本盘归入{profile.get('wealth_pattern') or '本命财格'}，{profile.get('reading') or '以个人时空推导财气。'}",
            "detail": f"主气{profile.get('dominant_element_label') or '--'}，财星{profile.get('wealth_element_label') or '--'}。",
        },
        {
            "title": "喜用元素",
            "text": f"本期优先用{profile.get('favorable_element_labels') or '--'}，避开{profile.get('avoid_element_labels') or '--'}过旺。",
            "detail": str(profile.get("selection_rule") or ""),
        },
        {
            "title": "数字尾数",
            "text": f"推荐号尾数落在{tail_labels}，把五行角色映射到具体号码。",
            "detail": "尾数1/2木，3/4火，5/6土，7/8金，9/0水。",
        },
        {
            "title": "号码组合",
            "text": f"按{mode_profile.get('label') or '稳财号'}生成，{mode_profile.get('description') or '保持玄学合参。'}",
            "detail": number_detail,
        },
    ]


def _master_ritual(
    personal: PersonalInput,
    best_draw_date: str,
    profile: Mapping[str, Any],
    mode_profile: Mapping[str, Any],
    sign: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
    avoid_numbers: list[dict[str, Any]],
) -> dict[str, Any]:
    pattern = str(profile.get("wealth_pattern") or "本命财格")
    reading = str(profile.get("reading") or "根据个人时空推导财气。")
    mode_label = str(mode_profile.get("label") or "稳财号")
    mode_description = str(mode_profile.get("description") or "保持玄学合参。")
    favorable = str(profile.get("favorable_element_labels") or "喜用数")
    avoid = str(profile.get("avoid_element_labels") or "冲气")
    day_mode = str(profile.get("day_mode") or "守")
    day_advice = str(profile.get("day_advice") or "宜守财，忌追热。")
    direction = str(sign.get("direction") or "--")
    lucky_hour = str(sign.get("lucky_hour") or "--")
    number_path = _format_number_path(main_numbers, special_numbers)
    calendar = "阴历" if personal.calendar_type == "lunar" else "阳历"
    hour = f"{personal.birth_hour}时" if personal.birth_hour != "unknown" else "时辰未知"
    favorable_tails = _element_tail_digits(list(profile.get("favorable_elements") or []))
    avoid_tails = _element_tail_digits(list(profile.get("avoid_elements") or []))
    if not favorable_tails:
        favorable_tails = [int(tail) % 10 for tail in sign.get("lucky_tails") or []]
    if not avoid_tails:
        avoid_tails = [int(tail) % 10 for tail in sign.get("avoid_tails") or []]

    avoid_preview = "、".join(f"{item['number']:02d}" for item in avoid_numbers[:4]) or "--"
    avoid_detail = (
        "；".join(str(item.get("reason") or "") for item in avoid_numbers[:2] if item.get("reason"))
        or f"避开{avoid}过旺的尾数，让号码组合不被冲气牵走。"
    )
    tail_legend = "尾数1/2木，3/4火，5/6土，7/8金，9/0水。"
    return {
        "opening": f"先看命盘，再定财局；{pattern}的关键，是把{favorable}落成可见数字。",
        "verdict": (
            f"此盘先定{pattern}，今日{day_mode}财，按{mode_label}起盘；"
            f"宜取{favorable}尾数，避{avoid}过旺。"
        ),
        "tail_map": {
            "favorable": _tail_entries(favorable_tails),
            "avoid": _tail_entries(avoid_tails),
            "legend": tail_legend,
        },
        "steps": [
            {
                "key": "birth_chart",
                "label": "定命盘",
                "value": f"{calendar} · {hour} · 城市方位",
                "detail": "结合出生日期、时辰和所在城市确定本次基础盘。",
            },
            {
                "key": "wealth_pattern",
                "label": "排本命财格",
                "value": pattern,
                "detail": (
                    f"{reading} 主气{profile.get('dominant_element_label') or '--'}，"
                    f"财星{profile.get('wealth_element_label') or '--'}，"
                    f"托财{profile.get('support_element_label') or '--'}。"
                ),
            },
            {
                "key": "daily_luck",
                "label": "定今日财局",
                "value": f"{best_draw_date} · {direction}财位 · {lucky_hour}",
                "detail": f"{day_advice}{sign.get('headline') or ''}",
            },
            {
                "key": "tail_digits",
                "label": "取喜用尾数",
                "value": f"宜 {_tail_digit_label(favorable_tails)} · 避 {_tail_digit_label(avoid_tails)}",
                "detail": f"{profile.get('selection_rule') or '先定财眼，再定主号。'}{tail_legend}",
            },
            {
                "key": "avoid_clash",
                "label": "避冲煞号",
                "value": f"避 {avoid_preview}",
                "detail": avoid_detail,
            },
            {
                "key": "final_numbers",
                "label": "落财运号",
                "value": number_path,
                "detail": f"按{mode_label}收束：{mode_description}",
            },
        ],
    }


def _tail_entries(tails: list[int]) -> list[dict[str, Any]]:
    entries = []
    seen: set[int] = set()
    for raw_tail in tails:
        tail = int(raw_tail) % 10
        if tail in seen:
            continue
        seen.add(tail)
        element = DIGIT_ELEMENT[tail]
        entries.append(
            {
                "tail": tail,
                "element": element,
                "element_label": ELEMENT_LABELS[element],
            }
        )
    return entries


def _fortune_report(
    game_key: str,
    personal: PersonalInput,
    best_draw_date: str,
    profile: Mapping[str, Any],
    mode_profile: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
    number_reasons: Mapping[str, Any],
) -> dict[str, Any]:
    closed_loop = _fortune_closed_loop(personal, profile, mode_profile, main_numbers, special_numbers)
    return {
        "game_key": game_key,
        "mode_key": str(mode_profile.get("key") or "steady"),
        "mode_label": str(mode_profile.get("label") or "稳财号"),
        "wealth_pattern": str(profile.get("wealth_pattern") or "本命财格"),
        "dominant_element": str(profile.get("dominant_element") or ""),
        "dominant_element_label": str(profile.get("dominant_element_label") or ""),
        "wealth_element": str(profile.get("wealth_element") or ""),
        "wealth_element_label": str(profile.get("wealth_element_label") or ""),
        "support_element": str(profile.get("support_element") or ""),
        "support_element_label": str(profile.get("support_element_label") or ""),
        "closed_loop": closed_loop,
        "tail_digit_map": _tail_digit_map(profile, main_numbers + special_numbers),
        "fortune_eye": _fortune_eye(profile, main_numbers, special_numbers, number_reasons),
        "daily_calendar": _daily_calendar(game_key, personal, best_draw_date, profile),
        "summary": (
            f"{profile.get('wealth_pattern') or '本命财格'}按{mode_profile.get('label') or '稳财号'}取数，"
            f"以{profile.get('favorable_element_labels') or '喜用数'}入局，"
            f"最后落到{_format_number_path(main_numbers, special_numbers)}。"
        ),
    }


def _fortune_closed_loop(
    personal: PersonalInput,
    profile: Mapping[str, Any],
    mode_profile: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
) -> list[dict[str, str]]:
    calendar = "阴历" if personal.calendar_type == "lunar" else "阳历"
    hour = f"{personal.birth_hour}时" if personal.birth_hour != "unknown" else "时辰未知"
    return [
        {
            "label": "个人时空",
            "value": f"{calendar} · {hour} · 城市方位",
            "detail": "出生日期、时辰和所在城市共同形成本次基础盘。",
        },
        {
            "label": "命格",
            "value": str(profile.get("wealth_pattern") or "本命财格"),
            "detail": str(profile.get("reading") or "根据个人时空推导财气强弱。"),
        },
        {
            "label": "喜用元素",
            "value": str(profile.get("favorable_element_labels") or "喜用数"),
            "detail": str(profile.get("selection_rule") or "先定财眼，再定主号。"),
        },
        {
            "label": "数字尾数",
            "value": _tail_element_summary(main_numbers + special_numbers),
            "detail": "把喜用元素映射为尾数，再落到当前彩种可选号码。",
        },
        {
            "label": "号码组合",
            "value": _format_number_path(main_numbers, special_numbers),
            "detail": f"按{mode_profile.get('label') or '稳财号'}收束成最终娱乐推荐。",
        },
    ]


def _tail_digit_map(profile: Mapping[str, Any], numbers: list[int]) -> dict[str, Any]:
    favorable_elements = set(profile.get("favorable_elements") or [])
    avoid_elements = set(profile.get("avoid_elements") or [])
    rows = []
    for number in numbers:
        digit = number % 10
        element = DIGIT_ELEMENT[digit]
        if element in favorable_elements:
            role = "喜用"
        elif element in avoid_elements:
            role = "制衡"
        else:
            role = "平衡"
        rows.append(
            {
                "number": number,
                "digit": digit,
                "element": element,
                "element_label": ELEMENT_LABELS[element],
                "role": role,
            }
        )
    favorable = str(profile.get("favorable_element_labels") or "喜用数")
    summary = f"喜用{favorable}优先入局，尾数映射为{_tail_element_summary(numbers)}。"
    return {"summary": summary, "items": rows}


def _fortune_eye(
    profile: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
    number_reasons: Mapping[str, Any],
) -> dict[str, Any]:
    number = special_numbers[-1] if special_numbers else (main_numbers[-1] if main_numbers else None)
    reasons = list(number_reasons.get("special") or []) or list(number_reasons.get("main") or [])
    reason = next((item for item in reasons if item.get("number") == number), reasons[-1] if reasons else {})
    digit = int(number) % 10 if number is not None else 0
    element = DIGIT_ELEMENT[digit]
    return {
        "number": number,
        "digit": digit,
        "element": element,
        "element_label": ELEMENT_LABELS[element],
        "role": reason.get("position_label") or "财眼位",
        "reading": (
            reason.get("text")
            or f"尾数{digit}属{ELEMENT_LABELS[element]}，用于收束{profile.get('wealth_pattern') or '本命财格'}的财气。"
        ),
    }


def _daily_calendar(
    game_key: str,
    personal: PersonalInput,
    best_draw_date: str,
    profile: Mapping[str, Any],
) -> list[dict[str, Any]]:
    start = date.fromisoformat(best_draw_date)
    candidates = candidate_draw_dates(game_key, start.isoformat(), 30)
    ordered = [start]
    for candidate in candidates:
        if candidate not in ordered:
            ordered.append(candidate)
        if len(ordered) >= 6:
            break

    rows = []
    for index, draw_date in enumerate(ordered):
        draw = draw_date.isoformat()
        score = mod_match(
            stable_int(
                "|".join(
                    (
                        game_key,
                        personal.name,
                        personal.birth_date,
                        personal.calendar_type,
                        personal.birth_hour,
                        personal.current_city,
                        draw,
                        "fortune-calendar",
                    )
                )
            ),
            index + 1,
        )
        rows.append(
            {
                "draw_date": draw,
                "label": "最佳开奖日" if index == 0 else f"备选日{index}",
                "day_mode": _day_mode(personal, draw),
                "score": round(100.0 if index == 0 else max(45.0, score), 2),
                "advice": str(profile.get("day_advice") or "宜先筛后取，忌临时追热。"),
            }
        )
    return rows


def _position_label(
    role: str,
    element: str,
    wealth_element: str,
    support_element: str,
    avoid_elements: set[str],
) -> str:
    if role == "财眼":
        return "财眼位"
    if element == wealth_element:
        return "引财位"
    if element == support_element:
        return "生财位"
    if element in avoid_elements:
        return "制衡位"
    return "守财位"


def _selection_role(
    element: str,
    wealth_element: str,
    support_element: str,
    favorable_elements: set[str],
    avoid_elements: set[str],
) -> str:
    label = ELEMENT_LABELS[element]
    if element == wealth_element:
        return f"{label}财星数"
    if element == support_element:
        return f"{label}生扶数"
    if element in favorable_elements:
        return f"{label}喜用数"
    if element in avoid_elements:
        return f"{label}制衡数"
    return f"{label}平衡数"


def _position_copy(position_label: str) -> str:
    copies = {
        "财眼位": "用于收束整组财气，避免号码只散不聚。",
        "引财位": "负责打开进财口，让组合有明确主线。",
        "生财位": "负责给财星续力，让财气不断档。",
        "制衡位": "用于压住过旺之气，让盘面不偏不冲。",
        "守财位": "负责稳住底盘，让整组号码不飘。",
    }
    return copies.get(position_label, "用于平衡整组财气。")


def _day_mode(personal: PersonalInput, draw_date: str) -> str:
    modes = ("守", "进", "收")
    index = stable_int(
        "|".join(
            (
                personal.calendar_type,
                personal.birth_hour,
                draw_date,
                "fortune-day-mode",
            )
        )
    ) % len(modes)
    return modes[index]


def _unique_elements(elements: list[str]) -> list[str]:
    result: list[str] = []
    for element in elements:
        if element in ELEMENTS and element not in result:
            result.append(element)
    return result


def _element_labels(elements: list[str]) -> str:
    return "、".join(ELEMENT_LABELS[element] for element in elements)


def _tail_element_summary(numbers: list[int]) -> str:
    seen: list[str] = []
    for number in numbers:
        digit = number % 10
        label = f"{digit}{ELEMENT_LABELS[DIGIT_ELEMENT[digit]]}"
        if label not in seen:
            seen.append(label)
    return "、".join(seen) or "--"


def _tail_digit_label(tails: list[int]) -> str:
    return "、".join(str(tail) for tail in tails) or "--"


def _format_number_path(main_numbers: list[int], special_numbers: list[int]) -> str:
    main = " -> ".join(f"{number:02d}" for number in main_numbers)
    if not special_numbers:
        return main
    special = " -> ".join(f"{number:02d}" for number in special_numbers)
    return f"{main} -> 财眼{special}"


def _recommendation_basis(fortune_mode: str = "steady") -> dict[str, Any]:
    weights = _raw_score_weights(fortune_mode)
    return {
        "mode": "玄学主导",
        "weights": dict(weights),
        "items": [
            {"key": "personal_space", "label": "个人时空", "weight": weights["personal_space"]},
            {"key": "ai_fortune", "label": "AI 命理", "weight": weights["ai_fortune"]},
            {"key": "draw_day_luck", "label": "开奖日运势", "weight": weights["draw_day_luck"]},
            {"key": "history_guardrail", "label": "数据托底", "weight": weights["history_guardrail"]},
        ],
    }


def _ritual_summary(ai_feature: AiFeature, best_draw_date: str) -> str:
    if ai_feature.enabled:
        themes = "、".join(ai_feature.lucky_themes) or "财气流转"
        return f"{best_draw_date} 财运合参完成：以{themes}为主调，结合个人时空与开奖日气口生成推荐号。"
    return f"{best_draw_date} 财运合参完成：AI 命理未启用，使用个人时空与开奖日气口生成推荐号。"


def _normalize(values: Mapping[int, Any] | Any) -> dict[int, float]:
    if not isinstance(values, Mapping):
        return {}

    numeric: dict[int, float] = {}
    for key, value in values.items():
        try:
            number_key = int(key)
        except (TypeError, ValueError):
            continue
        numeric[number_key] = _finite_float(value)
    if not numeric:
        return {}

    minimum = min(numeric.values())
    maximum = max(numeric.values())
    if maximum == minimum:
        return {key: 50.0 for key in numeric}

    return {
        key: round((value - minimum) / (maximum - minimum) * 100.0, 4)
        for key, value in numeric.items()
    }


def _finite_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(number):
        return 0.0
    return number


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
