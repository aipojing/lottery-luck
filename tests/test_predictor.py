import json

import pytest

from lottery_luck.ai_features import AiFeature, NullAiProvider, neutral_ai_feature
from lottery_luck.personal import PersonalInput, birth_vector
from lottery_luck.predictor import (
    PredictionEngine,
    _daily_fortune_sign,
    _history_scores,
    _normalize,
)
from lottery_luck.repository import LotteryRepository
from lottery_luck.rules import GAME_RULES, candidate_draw_dates


def _personal(name: str = "张三") -> PersonalInput:
    return PersonalInput(
        name=name,
        birth_date="1990-05-17",
        birth_hour="午",
        birth_place="杭州",
        current_city="上海",
    )


class FakeAiProvider:
    def __init__(self) -> None:
        self.contexts = []

    def extract(self, context):
        self.contexts.append(context)
        return AiFeature(
            enabled=True,
            element_bias={
                "wood": 0.10,
                "fire": 0.10,
                "earth": 0.10,
                "metal": 0.50,
                "water": 0.20,
            },
            digit_bias={
                "0": 0.04,
                "1": 0.04,
                "2": 0.04,
                "3": 0.04,
                "4": 0.04,
                "5": 0.06,
                "6": 0.06,
                "7": 0.34,
                "8": 0.30,
                "9": 0.04,
            },
            lucky_themes=["金气", "稳健"],
            explanation="金元素较强，作为娱乐特征参考。",
            confidence=0.7,
        )


class RaisingAiProvider:
    def extract(self, context):
        raise RuntimeError("provider unavailable")


class InvalidAiProvider:
    def extract(self, context):
        return {"enabled": True}


class CapturingAiProvider(FakeAiProvider):
    pass


class EmptyRepo:
    def all_draws(self, game_key):
        return []

    def recent_draws(self, game_key, limit=100):
        return []

    def list_games(self):
        return []


class ThreeDGlobalTrendRepo:
    def all_draws(self, game_key):
        return (
            [{"red_numbers": "8,1,1", "blue_number": ""} for _ in range(20)]
            + [{"red_numbers": "2,1,1", "blue_number": ""} for _ in range(30)]
        )

    def recent_draws(self, game_key, limit=100):
        return self.all_draws(game_key)[:limit]

    def list_games(self):
        return []


class DigitRepeatTrendRepo:
    def all_draws(self, game_key):
        if game_key == "pl3":
            return [{"red_numbers": "7,7,7", "blue_number": ""} for _ in range(30)]
        if game_key == "pl5":
            return [{"red_numbers": "8,8,8,8,8", "blue_number": ""} for _ in range(30)]
        return []

    def recent_draws(self, game_key, limit=100):
        return self.all_draws(game_key)[:limit]

    def list_games(self):
        return []


def test_ssq_prediction_is_deterministic_and_valid():
    engine = PredictionEngine(LotteryRepository(), ai_provider=None)
    first = engine.predict("ssq", _personal(), today="2026-06-16")
    second = engine.predict("ssq", _personal(), today="2026-06-16")

    assert first == second
    assert first["game_key"] == "ssq"
    assert len(first["numbers"]["main"]) == 6
    assert first["numbers"]["main"] == sorted(first["numbers"]["main"])
    assert len(set(first["numbers"]["main"])) == 6
    assert all(1 <= number <= 33 for number in first["numbers"]["main"])
    assert len(first["numbers"]["special"]) == 1
    assert 1 <= first["numbers"]["special"][0] <= 16
    assert 0 <= first["luck_score"] <= 100
    assert "不构成投注建议" in first["disclaimer"]
    assert len(first["recent_draws"]) <= 5


def test_invalid_game_key_raises_clear_error():
    with pytest.raises(ValueError, match="unsupported game_key: nope"):
        PredictionEngine(EmptyRepo(), ai_provider=None).predict(
            "nope", _personal(), today="2026-06-16"
        )


def test_3d_prediction_is_valid_and_preserves_order_with_repeats_allowed():
    payload = PredictionEngine(LotteryRepository(), ai_provider=None).predict(
        "3d", _personal(), today="2026-06-16"
    )

    assert len(payload["numbers"]["main"]) == 3
    assert all(0 <= number <= 9 for number in payload["numbers"]["main"])
    assert payload["numbers"]["special"] == []


def test_3d_prediction_uses_global_history_trend_with_position_frequency(monkeypatch):
    def neutral_personal_score(data, game_key, number, draw_date, ai_score=50.0):
        return 50.0

    monkeypatch.setattr(
        "lottery_luck.predictor.personal_score_for_number",
        neutral_personal_score,
    )

    payload = PredictionEngine(ThreeDGlobalTrendRepo(), ai_provider=None).predict(
        "3d", _personal(), today="2026-06-16"
    )

    assert payload["numbers"]["main"][0] == 1


def test_3d_missing_position_entry_uses_neutral_position_fallback(monkeypatch):
    def neutral_personal_score(data, game_key, number, draw_date, ai_score=50.0):
        return 50.0

    monkeypatch.setattr(
        "lottery_luck.predictor.personal_score_for_number",
        neutral_personal_score,
    )
    profile = {
        "main_frequency": {1: 3},
        "main_weighted": {1: 3.0},
        "main_omission": {1: 0},
        "position_frequency": {},
    }

    numbers, scores = PredictionEngine(EmptyRepo(), ai_provider=None)._select_3d_numbers(
        "3d", _personal(), "2026-06-16", profile, neutral_ai_feature()
    )

    assert len(numbers) == 3
    assert len(scores) == 3
    assert all(0 <= number <= 9 for number in numbers)


def test_qlc_special_is_not_in_main():
    payload = PredictionEngine(LotteryRepository(), ai_provider=None).predict(
        "qlc", _personal(), today="2026-06-16"
    )

    assert len(payload["numbers"]["main"]) == 7
    assert payload["numbers"]["main"] == sorted(payload["numbers"]["main"])
    assert len(set(payload["numbers"]["main"])) == 7
    assert all(1 <= number <= 30 for number in payload["numbers"]["main"])
    assert len(payload["numbers"]["special"]) == 1
    assert 1 <= payload["numbers"]["special"][0] <= 30
    assert payload["numbers"]["special"][0] not in payload["numbers"]["main"]


def test_kl8_outputs_ten_unique_numbers_in_range():
    payload = PredictionEngine(LotteryRepository(), ai_provider=None).predict(
        "kl8", _personal(), today="2026-06-16"
    )

    assert len(payload["numbers"]["main"]) == 10
    assert payload["numbers"]["main"] == sorted(payload["numbers"]["main"])
    assert len(set(payload["numbers"]["main"])) == 10
    assert all(1 <= number <= 80 for number in payload["numbers"]["main"])
    assert payload["numbers"]["special"] == []


def test_dlt_outputs_five_plus_two_numbers_in_range():
    payload = PredictionEngine(EmptyRepo(), ai_provider=None).predict(
        "dlt", _personal(), today="2026-06-16"
    )

    assert len(payload["numbers"]["main"]) == 5
    assert payload["numbers"]["main"] == sorted(payload["numbers"]["main"])
    assert len(set(payload["numbers"]["main"])) == 5
    assert all(1 <= number <= 35 for number in payload["numbers"]["main"])
    assert len(payload["numbers"]["special"]) == 2
    assert all(1 <= number <= 12 for number in payload["numbers"]["special"])


@pytest.mark.parametrize(
    ("birth_place", "current_city", "expected_relation"),
    [
        ("  杭州  ", "杭州", "same"),
        ("杭州", "上海", "different"),
        ("", "上海", "incomplete"),
    ],
)
def test_ai_provider_context_uses_only_minimized_personal_features(
    birth_place, current_city, expected_relation
):
    provider = CapturingAiProvider()
    personal = PersonalInput(
        name="隐私姓名-Sentinel",
        birth_date="1988-12-31",
        birth_hour="午",
        birth_place=birth_place,
        current_city=current_city,
        calendar_type="solar",
    )

    payload = PredictionEngine(EmptyRepo(), provider).predict(
        "ssq", personal, today="2026-06-16", fortune_mode="windfall"
    )

    assert payload["personal_basis"]["ai_enabled"] is True
    assert len(provider.contexts) == 1
    context = provider.contexts[0]
    serialized_context = json.dumps(context, ensure_ascii=False, sort_keys=True)
    for raw_value in (
        personal.name,
        personal.birth_date,
        personal.birth_hour,
        personal.birth_place,
        personal.current_city,
    ):
        if raw_value:
            assert raw_value not in serialized_context

    assert set(context) == {
        "game_key",
        "fortune_mode",
        "best_draw_date",
        "personal_features",
    }
    assert context["game_key"] == "ssq"
    assert context["fortune_mode"] == "windfall"
    assert context["best_draw_date"] == payload["best_draw_date"]
    assert set(context["personal_features"]) == {
        "birth_vector",
        "birth_hour_known",
        "calendar_type",
        "location_relation",
    }
    assert context["personal_features"]["birth_vector"] == birth_vector(personal)
    assert set(context["personal_features"]["birth_vector"]) == {
        "wood",
        "fire",
        "earth",
        "metal",
        "water",
    }
    assert all(
        isinstance(value, float)
        for value in context["personal_features"]["birth_vector"].values()
    )
    assert context["personal_features"]["birth_hour_known"] is True
    assert context["personal_features"]["calendar_type"] == "solar"
    assert context["personal_features"]["location_relation"] == expected_relation


def test_ai_provider_exception_fallback_does_not_log_or_return_raw_request_data(
    caplog, capsys
):
    class LeakyRaisingAiProvider:
        def __init__(self) -> None:
            self.contexts = []

        def extract(self, context):
            self.contexts.append(context)
            raise RuntimeError("隐私姓名-Sentinel 1988-12-31 午 杭州 上海")

    provider = LeakyRaisingAiProvider()
    personal = PersonalInput(
        name="隐私姓名-Sentinel",
        birth_date="1988-12-31",
        birth_hour="午",
        birth_place="杭州",
        current_city="上海",
    )

    payload = PredictionEngine(EmptyRepo(), provider).predict(
        "ssq", personal, today="2026-06-16"
    )

    assert payload["personal_basis"]["ai_enabled"] is False
    captured = capsys.readouterr()
    log_output = "\n".join(record.getMessage() for record in caplog.records)
    all_observable_output = "\n".join(
        [
            payload["personal_basis"]["ai_explanation"],
            captured.out,
            captured.err,
            log_output,
        ]
    )
    for raw_value in (
        personal.name,
        personal.birth_date,
        personal.birth_hour,
        personal.birth_place,
        personal.current_city,
    ):
        assert raw_value not in all_observable_output
    assert provider.contexts


@pytest.mark.parametrize(("game_key", "expected_digit"), [("pl3", 7), ("pl5", 8)])
def test_sports_digit_games_use_position_selection_and_allow_repeats(
    monkeypatch, game_key, expected_digit
):
    def neutral_personal_score(data, game_key, number, draw_date, ai_score=50.0):
        return 50.0

    monkeypatch.setattr(
        "lottery_luck.predictor.personal_score_for_number",
        neutral_personal_score,
    )

    payload = PredictionEngine(DigitRepeatTrendRepo(), ai_provider=None).predict(
        game_key, _personal(), today="2026-06-16"
    )

    assert payload["numbers"]["main"] == [expected_digit] * GAME_RULES[game_key].main_count
    assert payload["numbers"]["special"] == []


def test_best_draw_date_is_in_candidate_draw_dates():
    today = "2026-06-16"
    payload = PredictionEngine(LotteryRepository(), ai_provider=None).predict(
        "ssq", _personal(), today=today
    )

    candidates = {draw_date.isoformat() for draw_date in candidate_draw_dates("ssq", today, 30)}
    assert payload["best_draw_date"] in candidates


def test_changing_name_changes_result_or_luck_score():
    engine = PredictionEngine(LotteryRepository(), ai_provider=None)
    first = engine.predict("ssq", _personal("张三"), today="2026-06-16")
    second = engine.predict("ssq", _personal("李四"), today="2026-06-16")

    assert (
        first["numbers"] != second["numbers"]
        or first["luck_score"] != second["luck_score"]
    )


def test_custom_ai_provider_is_called_and_basis_reflects_enabled():
    provider = FakeAiProvider()
    payload = PredictionEngine(LotteryRepository(), provider).predict(
        "ssq", _personal(), today="2026-06-16"
    )

    assert len(provider.contexts) == 1
    context = provider.contexts[0]
    assert context["game_key"] == "ssq"
    assert "personal" not in context
    assert context["personal_features"]["birth_hour_known"] is True
    assert context["personal_features"]["calendar_type"] == "solar"
    assert context["best_draw_date"] == payload["best_draw_date"]
    assert payload["personal_basis"]["ai_enabled"] is True
    assert payload["personal_basis"]["ai_explanation"] == "金元素较强，作为娱乐特征参考。"
    assert payload["personal_basis"]["ai_lucky_themes"] == ["金气", "稳健"]
    assert payload["personal_basis"]["ai_confidence"] == 0.7


def test_prediction_payload_is_metaphysics_recommendation():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq", _personal(), today="2026-06-16"
    )

    basis = payload["recommendation_basis"]
    assert basis["mode"] == "玄学主导"
    assert basis["weights"] == {
        "personal_space": 40,
        "ai_fortune": 25,
        "draw_day_luck": 20,
        "history_guardrail": 15,
    }
    assert [item["label"] for item in basis["items"]] == [
        "个人时空",
        "AI 命理",
        "开奖日运势",
        "数据托底",
    ]
    assert "财运" in payload["ritual_summary"]
    assert "娱乐推荐" in payload["disclaimer"]
    assert "不构成投注建议" in payload["disclaimer"]

    reasons = payload["number_reasons"]
    assert {item["number"] for item in reasons["main"]} == set(payload["numbers"]["main"])
    assert {item["number"] for item in reasons["special"]} == set(payload["numbers"]["special"])
    assert all("财" in item["text"] for item in reasons["main"] + reasons["special"])


def test_prediction_payload_includes_personalized_fortune_hook():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq", _personal(), today="2026-06-16"
    )

    hook = payload["fortune_hook"]
    assert hook["headline"]
    assert "本命财格" in hook["subline"]
    assert hook["tags"]
    assert any("今日宜" in tag for tag in hook["tags"])

    profile = payload["metaphysics_profile"]
    assert profile["wealth_pattern"]
    assert profile["dominant_element"] in {"wood", "fire", "earth", "metal", "water"}
    assert profile["wealth_element"] in {"wood", "fire", "earth", "metal", "water"}
    assert profile["favorable_element_labels"]
    assert profile["avoid_element_labels"]
    assert profile["day_advice"].startswith("宜")
    assert "历史数据" in profile["selection_rule"]

    selected = set(payload["numbers"]["main"] + payload["numbers"]["special"])
    avoid_numbers = payload["avoid_numbers"]
    assert 1 <= len(avoid_numbers) <= 5
    assert all(item["number"] not in selected for item in avoid_numbers)
    assert all(item["reason"] for item in avoid_numbers)

    reason = payload["number_reasons"]["main"][0]
    assert reason["position_label"]
    assert reason["element_label"] in {"木", "火", "土", "金", "水"}
    assert reason["selection_role"]
    assert len(reason["lines"]) == 3
    assert reason["lines"][0].startswith("五行角色")
    assert reason["lines"][1].startswith("入选原因")
    assert reason["lines"][2].startswith("组合位置")


def test_predict_includes_daily_fortune_sign_and_ritual_steps():
    payload = PredictionEngine(EmptyRepo(), NullAiProvider()).predict(
        "ssq",
        _personal(),
        today="2026-06-18",
        fortune_mode="steady",
    )

    sign = payload["daily_fortune_sign"]
    assert sign["headline"]
    assert sign["direction"] in {"正东", "东南", "正南", "西南", "正西", "西北", "正北", "东北"}
    assert sign["lucky_hour"]
    assert sign["lucky_hour"] in sign["headline"]
    assert len(sign["tags"]) == 3
    assert any(sign["lucky_hour"] in tag for tag in sign["tags"])
    assert len(sign["lucky_tails"]) >= 1
    assert len(sign["avoid_tails"]) >= 1

    steps = payload["ritual_steps"]
    assert [step["key"] for step in steps] == [
        "wealth_pattern",
        "fortune_direction",
        "fortune_eye",
        "avoid_clash",
        "final_numbers",
    ]
    assert all(step["label"] and step["summary"] for step in steps)


def test_prediction_payload_includes_master_ritual_closed_loop():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq",
        _personal(),
        today="2026-06-18",
        fortune_mode="windfall",
    )

    master_ritual = payload["master_ritual"]
    profile = payload["metaphysics_profile"]
    final_step = master_ritual["steps"][-1]

    assert master_ritual["opening"]
    assert profile["wealth_pattern"] in master_ritual["verdict"]
    assert payload["mode_profile"]["label"] in master_ritual["verdict"]
    assert [step["label"] for step in master_ritual["steps"]] == [
        "定命盘",
        "排本命财格",
        "定今日财局",
        "取喜用尾数",
        "避冲煞号",
        "落财运号",
    ]
    assert all(step["value"] and step["detail"] for step in master_ritual["steps"])
    assert "->" in final_step["value"]
    assert str(payload["numbers"]["special"][-1]).zfill(2) in final_step["value"]

    tail_map = master_ritual["tail_map"]
    assert tail_map["legend"].startswith("尾数1/2木")
    assert tail_map["favorable"]
    assert tail_map["avoid"]
    assert {"tail", "element_label"} <= set(tail_map["favorable"][0])


def test_predict_v3_avoid_numbers_are_bounded_and_do_not_overlap():
    payload = PredictionEngine(EmptyRepo(), NullAiProvider()).predict(
        "kl8",
        _personal(),
        today="2026-06-18",
    )

    selected = set(payload["numbers"]["main"] + payload["numbers"]["special"])
    avoid_numbers = payload["avoid_numbers"]
    assert 1 <= len(avoid_numbers) <= 6
    assert not selected.intersection(item["number"] for item in avoid_numbers)
    assert all(item["reason"] for item in avoid_numbers)


def test_daily_fortune_sign_seed_uses_time_place_city_and_draw_date():
    profile = {"favorable_elements": ["earth"], "avoid_elements": ["wood"]}
    ai_feature = neutral_ai_feature()
    personal = _personal()
    base = _daily_fortune_sign(personal, "2026-06-18", profile, ai_feature)
    variants = [
        PersonalInput(
            name=personal.name,
            birth_date=personal.birth_date,
            birth_hour="子",
            birth_place=personal.birth_place,
            current_city=personal.current_city,
        ),
        PersonalInput(
            name=personal.name,
            birth_date=personal.birth_date,
            birth_hour=personal.birth_hour,
            birth_place="宁波",
            current_city=personal.current_city,
        ),
        PersonalInput(
            name=personal.name,
            birth_date=personal.birth_date,
            birth_hour=personal.birth_hour,
            birth_place=personal.birth_place,
            current_city="北京",
        ),
    ]

    for variant in variants:
        assert _daily_fortune_sign(variant, "2026-06-18", profile, ai_feature) != base
    assert _daily_fortune_sign(personal, "2026-06-19", profile, ai_feature) != base


def test_daily_fortune_sign_uses_ai_digit_bias_as_lucky_tails():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq",
        _personal(),
        today="2026-06-18",
    )

    sign = payload["daily_fortune_sign"]
    assert 7 in sign["lucky_tails"]
    assert 8 in sign["lucky_tails"]


@pytest.mark.parametrize(
    ("fortune_mode", "expected_label"),
    [
        ("steady", "稳财号"),
        ("windfall", "偏财号"),
        ("guard", "守财号"),
    ],
)
def test_prediction_payload_supports_fortune_modes_and_credibility_chain(
    fortune_mode, expected_label
):
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq", _personal(), today="2026-06-16", fortune_mode=fortune_mode
    )

    assert payload["fortune_mode"] == fortune_mode
    assert payload["mode_profile"]["label"] == expected_label
    assert payload["mode_profile"]["weights"]
    assert expected_label in payload["fortune_hook"]["subline"]

    chain = payload["credibility_chain"]
    assert [item["title"] for item in chain] == [
        "个人时空",
        "本命财格",
        "喜用元素",
        "数字尾数",
        "号码组合",
    ]
    assert all(item["text"] for item in chain)
    assert "->" in chain[-1]["detail"]
    assert "本地折算" not in str(payload)
    assert "不在结果中回显" not in str(payload)


def test_metaphysics_weights_can_be_overridden(monkeypatch):
    custom_weights = {
        "steady": {
            "personal_space": 55,
            "ai_fortune": 10,
            "draw_day_luck": 20,
            "history_guardrail": 15,
        },
        "windfall": {
            "personal_space": 30,
            "ai_fortune": 35,
            "draw_day_luck": 25,
            "history_guardrail": 10,
        },
        "guard": {
            "personal_space": 60,
            "ai_fortune": 10,
            "draw_day_luck": 10,
            "history_guardrail": 20,
        },
    }
    monkeypatch.setattr("lottery_luck.predictor.get_metaphysics_weights", lambda: custom_weights)

    payload = PredictionEngine(EmptyRepo(), ai_provider=None).predict(
        "ssq", _personal(), today="2026-06-16", fortune_mode="guard"
    )

    assert payload["mode_profile"]["weights"] == custom_weights["guard"]
    assert payload["recommendation_basis"]["weights"] == custom_weights["guard"]


def test_prediction_includes_fortune_report_closed_loop():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq", _personal(), today="2026-06-16", fortune_mode="windfall"
    )

    report = payload["fortune_report"]

    assert report["mode_label"] == "偏财号"
    assert report["closed_loop"][0]["label"] == "个人时空"
    assert report["closed_loop"][-1]["label"] == "号码组合"
    assert "喜用" in report["tail_digit_map"]["summary"]
    assert report["fortune_eye"]["number"] == payload["numbers"]["special"][-1]
    assert report["daily_calendar"]
    assert report["daily_calendar"][0]["draw_date"] == payload["best_draw_date"]


def test_combined_score_uses_metaphysics_first_weights(monkeypatch):
    def fixed_personal_score(data, game_key, number, draw_date, ai_score=50.0):
        return 80.0

    def fixed_day_luck(seed, number, modulus=100):
        return 70.0

    monkeypatch.setattr(
        "lottery_luck.predictor.personal_score_for_number",
        fixed_personal_score,
    )
    monkeypatch.setattr("lottery_luck.predictor.mod_match", fixed_day_luck)

    ai_feature = AiFeature(
        enabled=True,
        element_bias={
            "wood": 0.20,
            "fire": 0.20,
            "earth": 0.20,
            "metal": 0.20,
            "water": 0.20,
        },
        digit_bias={
            "0": 0.09555555555555556,
            "1": 0.09555555555555556,
            "2": 0.09555555555555556,
            "3": 0.09555555555555556,
            "4": 0.09555555555555556,
            "5": 0.09555555555555556,
            "6": 0.09555555555555556,
            "7": 0.09555555555555556,
            "8": 0.14,
            "9": 0.09555555555555556,
        },
        lucky_themes=[],
        explanation="",
        confidence=1.0,
    )

    score = PredictionEngine(EmptyRepo(), None)._combined_score(
        "ssq", _personal(), "2026-06-18", ai_feature, 8, history_score=20.0
    )

    assert score == 64.0


@pytest.mark.parametrize("provider", [RaisingAiProvider(), InvalidAiProvider()])
def test_ai_provider_failures_fall_back_to_disabled_neutral_feature(provider):
    payload = PredictionEngine(EmptyRepo(), provider).predict(
        "ssq", _personal(), today="2026-06-16"
    )

    assert payload["personal_basis"]["ai_enabled"] is False
    assert payload["personal_basis"]["ai_explanation"] == neutral_ai_feature().explanation
    assert len(payload["numbers"]["main"]) == 6


@pytest.mark.parametrize("game_key", ["ssq", "3d", "qlc", "kl8", "dlt", "pl3", "pl5"])
def test_empty_history_same_score_normalization_does_not_crash_for_all_games(game_key):
    payload = PredictionEngine(EmptyRepo(), ai_provider=None).predict(
        game_key, _personal(), today="2026-06-16"
    )
    rule = GAME_RULES[game_key]

    assert len(payload["numbers"]["main"]) == rule.main_count
    assert len(payload["numbers"]["special"]) == rule.special_count
    assert all(number in rule.main_range for number in payload["numbers"]["main"])
    if not rule.allow_repeat:
        assert payload["numbers"]["main"] == sorted(payload["numbers"]["main"])
        assert len(set(payload["numbers"]["main"])) == rule.main_count
    if game_key == "qlc":
        assert payload["numbers"]["special"][0] not in payload["numbers"]["main"]
    if rule.special_range:
        assert all(number in rule.special_range for number in payload["numbers"]["special"])
    assert 0 <= payload["luck_score"] <= 100
    assert payload["history_basis"]["draw_count"] == 0
    assert payload["personal_basis"]["ai_enabled"] is False
    assert payload["personal_basis"]["ai_explanation"] == neutral_ai_feature().explanation


def test_history_scores_missing_profile_keys_are_neutral():
    scores = _history_scores("ssq", {})

    assert set(scores) == set(GAME_RULES["ssq"].main_range)
    assert all(score == 50.0 for score in scores.values())


def test_normalize_skips_bad_keys_and_accepts_empty_or_non_mapping_values():
    assert _normalize({"bad": 1, 1: 10, 2: 20}) == {1: 0.0, 2: 100.0}
    assert _normalize({}) == {}
    assert _normalize(None) == {}
