from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import isfinite
from re import sub
from typing import Mapping

from lunardate import LunarDate

ELEMENTS = ("wood", "fire", "earth", "metal", "water")
DIGIT_ELEMENT = {
    1: "wood",
    2: "wood",
    3: "fire",
    4: "fire",
    5: "earth",
    6: "earth",
    7: "metal",
    8: "metal",
    9: "water",
    0: "water",
}

HOUR_BRANCH = {
    "子": 0,
    "丑": 1,
    "寅": 2,
    "卯": 3,
    "辰": 4,
    "巳": 5,
    "午": 6,
    "未": 7,
    "申": 8,
    "酉": 9,
    "戌": 10,
    "亥": 11,
    "unknown": 0,
}

CALENDAR_TYPES = ("solar", "lunar")


@dataclass(frozen=True)
class PersonalInput:
    name: str
    birth_date: str
    birth_hour: str
    birth_place: str
    current_city: str
    calendar_type: str = "solar"

    def __post_init__(self) -> None:
        birth_hour = self.birth_hour.strip()
        if birth_hour not in HOUR_BRANCH:
            birth_hour = "unknown"
        calendar_type = self.calendar_type.strip().lower()
        if calendar_type not in CALENDAR_TYPES:
            calendar_type = "solar"
        birth_date = _normalize_birth_date(self.birth_date, calendar_type)

        object.__setattr__(self, "name", _clean_text(self.name))
        object.__setattr__(self, "birth_date", birth_date)
        object.__setattr__(self, "birth_hour", birth_hour)
        object.__setattr__(self, "birth_place", _clean_text(self.birth_place))
        object.__setattr__(self, "current_city", _clean_text(self.current_city))
        object.__setattr__(self, "calendar_type", calendar_type)


def _normalize_birth_date(value: str, calendar_type: str) -> str:
    born = date.fromisoformat(value)
    if calendar_type == "lunar":
        return LunarDate(born.year, born.month, born.day).toSolarDate().isoformat()
    return born.isoformat()


def _clean_text(value: str) -> str:
    return sub(r"\s+", " ", value.strip())


def stable_int(value: str) -> int:
    return int(sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def normalize_vector(values: Mapping[str, float]) -> dict[str, float]:
    base = {element: float(values.get(element, 0.0)) for element in ELEMENTS}
    total = sum(base.values())
    if total <= 0:
        return {element: 1.0 / len(ELEMENTS) for element in ELEMENTS}
    return {element: base[element] / total for element in ELEMENTS}


def birth_vector(data: PersonalInput) -> dict[str, float]:
    born = date.fromisoformat(data.birth_date)
    values = {element: 0.0 for element in ELEMENTS}

    values[_element_for_index(born.year)] += 0.25
    values[_element_for_index(born.month)] += 0.30
    values[_element_for_index(born.toordinal() % 60)] += 0.30
    if data.birth_hour == "unknown":
        for element in ELEMENTS:
            values[element] += 0.15 / len(ELEMENTS)
    else:
        hour_index = HOUR_BRANCH[data.birth_hour]
        values[_element_for_index(hour_index)] += 0.15

    return normalize_vector(values)


def mod_match(seed: str | int, number: int, modulus: int = 100) -> float:
    """Score circular modular proximity, so values near either edge still match."""
    if modulus <= 0:
        raise ValueError("modulus must be positive")

    seed_int = stable_int(seed) if isinstance(seed, str) else int(seed)
    target = seed_int % modulus
    value = number % modulus
    distance = min(abs(target - value), modulus - abs(target - value))
    return max(0.0, 100.0 * (1.0 - distance / (modulus / 2)))


def personal_score_for_number(
    data: PersonalInput,
    game_key: str,
    number: int,
    draw_date: str,
    ai_score: float = 50.0,
) -> float:
    draw = date.fromisoformat(draw_date).isoformat()
    game = game_key.strip().lower()

    vector = birth_vector(data)
    digit_element = DIGIT_ELEMENT[number % 10]
    birth_time_score = vector[digit_element] * 100.0

    personal_seed = stable_int(
        "|".join(
            (
                game,
                data.name,
                data.birth_date,
                data.calendar_type,
                data.birth_hour,
                data.birth_place,
                data.current_city,
            )
        )
    )

    name_score = (
        mod_match(personal_seed ^ stable_int(data.name), number) * 0.45
        + mod_match(_name_numerology(data.name), number) * 0.35
        + mod_match(sum(ord(ch) for ch in data.name), number) * 0.20
    )
    space_score = mod_match(
        stable_int(f"{game}|{data.birth_place}|{data.current_city}"), number
    )
    date_score = mod_match(stable_int(f"{personal_seed}|{draw}"), number)
    bounded_ai_score = _bounded_ai_score(ai_score)

    score = (
        birth_time_score * 0.30
        + name_score * 0.15
        + space_score * 0.20
        + date_score * 0.20
        + bounded_ai_score * 0.15
    )
    return round(max(0.0, min(100.0, score)), 4)


def _element_for_index(index: int) -> str:
    return ELEMENTS[index % len(ELEMENTS)]


def _name_numerology(name: str) -> int:
    return (sum((index + 1) * ord(char) for index, char in enumerate(name)) % 81) + 1


def _bounded_ai_score(ai_score: float) -> float:
    score = float(ai_score)
    if not isfinite(score):
        return 50.0
    return max(0.0, min(100.0, score))
