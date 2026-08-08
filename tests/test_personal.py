import pytest
from math import isfinite

from lottery_luck.personal import (
    ELEMENTS,
    PersonalInput,
    birth_vector,
    personal_score_for_number,
)


def _sample_input(**overrides):
    values = {
        "name": " 张   三 ",
        "birth_date": "1990-05-12",
        "birth_hour": "子",
        "birth_place": " 杭州 ",
        "current_city": "上 海",
    }
    values.update(overrides)
    return PersonalInput(**values)


def test_personal_score_is_stable_for_same_input():
    data = _sample_input()

    first = personal_score_for_number(data, "ssq", 8, "2026-06-18")
    second = personal_score_for_number(data, "ssq", 8, "2026-06-18")

    assert first == second
    assert 0 <= first <= 100
    assert len(str(first).split(".")[-1]) <= 4


def test_personal_score_changes_when_name_changes():
    one = _sample_input(name="张三")
    two = _sample_input(name="李四")

    assert personal_score_for_number(one, "ssq", 8, "2026-06-18") != (
        personal_score_for_number(two, "ssq", 8, "2026-06-18")
    )


def test_personal_score_changes_when_city_changes():
    one = _sample_input(current_city="上海")
    two = _sample_input(current_city="北京")

    assert personal_score_for_number(one, "ssq", 8, "2026-06-18") != (
        personal_score_for_number(two, "ssq", 8, "2026-06-18")
    )


def test_personal_score_changes_when_calendar_type_changes():
    solar = _sample_input(calendar_type="solar")
    lunar = _sample_input(calendar_type="lunar")

    assert solar.calendar_type == "solar"
    assert lunar.calendar_type == "lunar"
    assert personal_score_for_number(solar, "ssq", 8, "2026-06-18") != (
        personal_score_for_number(lunar, "ssq", 8, "2026-06-18")
    )


def test_lunar_birth_date_is_converted_to_solar_date_for_calculation():
    lunar = _sample_input(birth_date="1990-01-01", calendar_type="lunar")
    solar = _sample_input(birth_date="1990-01-27", calendar_type="solar")

    assert lunar.calendar_type == "lunar"
    assert lunar.birth_date == "1990-01-27"
    assert birth_vector(lunar) == birth_vector(solar)


def test_calendar_type_defaults_to_solar_for_unknown_values():
    data = _sample_input(calendar_type="wrong")

    assert data.calendar_type == "solar"


def test_personal_score_changes_when_draw_date_changes():
    data = _sample_input()

    assert personal_score_for_number(data, "ssq", 8, "2026-06-18") != (
        personal_score_for_number(data, "ssq", 8, "2026-06-21")
    )


def test_unknown_birth_hour_is_supported():
    data = _sample_input(birth_hour="凌晨")

    score = personal_score_for_number(data, "ssq", 8, "2026-06-18")

    assert 0 <= score <= 100


def test_unknown_birth_hour_vector_is_not_equivalent_to_zi_hour():
    zi_vector = birth_vector(_sample_input(birth_hour="子"))
    unknown_vector = birth_vector(_sample_input(birth_hour="凌晨"))

    assert unknown_vector != zi_vector
    assert sum(unknown_vector.values()) == pytest.approx(1.0)


def test_birth_vector_is_normalized_and_contains_all_elements():
    vector = birth_vector(_sample_input())

    assert tuple(vector) == ELEMENTS
    assert sum(vector.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in vector.values())


def test_invalid_birth_date_raises_value_error():
    with pytest.raises(ValueError):
        _sample_input(birth_date="1990-02-31")


@pytest.mark.parametrize("ai_score", [-1, 101, float("inf"), float("nan")])
def test_ai_score_out_of_bounds_or_non_finite_still_returns_finite_score(ai_score):
    score = personal_score_for_number(
        _sample_input(), "ssq", 8, "2026-06-18", ai_score=ai_score
    )

    assert isfinite(score)
    assert 0 <= score <= 100


def test_non_finite_ai_score_uses_neutral_score():
    neutral = personal_score_for_number(
        _sample_input(), "ssq", 8, "2026-06-18", ai_score=50
    )

    assert personal_score_for_number(
        _sample_input(), "ssq", 8, "2026-06-18", ai_score=float("inf")
    ) == neutral
    assert personal_score_for_number(
        _sample_input(), "ssq", 8, "2026-06-18", ai_score=float("nan")
    ) == neutral
