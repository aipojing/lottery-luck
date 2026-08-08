import json

import httpx
import pytest

from lottery_luck.ai_features import (
    AiFeature,
    DeepSeekFlashProvider,
    NullAiProvider,
    neutral_ai_feature,
    validate_ai_payload,
)
from lottery_luck.personal import PersonalInput
from lottery_luck.predictor import PredictionEngine


def _valid_payload(**overrides):
    payload = {
        "element_bias": {
            "wood": 0.10,
            "fire": 0.15,
            "earth": 0.20,
            "metal": 0.35,
            "water": 0.20,
        },
        "digit_bias": {
            "0": 0.05,
            "1": 0.05,
            "2": 0.08,
            "3": 0.08,
            "4": 0.09,
            "5": 0.10,
            "6": 0.10,
            "7": 0.18,
            "8": 0.17,
            "9": 0.10,
        },
        "lucky_themes": ["金气", "稳健"],
        "explanation": "金元素较强，适合作为娱乐特征参考。",
        "confidence": 0.95,
    }
    payload.update(overrides)
    return payload


class EmptyRepo:
    def all_draws(self, game_key):
        return []

    def recent_draws(self, game_key, limit=100):
        return []

    def list_games(self):
        return []


def test_null_provider_returns_disabled_neutral_feature():
    feature = NullAiProvider().extract({"game": "ssq"})

    assert feature == neutral_ai_feature()
    assert feature.enabled is False
    assert "未启用" in feature.explanation
    assert feature.score_for_digit(7, "metal") == 50.0
    assert feature.score_for_digit(0, "water") == 50.0


def test_validate_payload_caps_confidence_and_scores_metal_above_water():
    feature = validate_ai_payload(_valid_payload())

    assert isinstance(feature, AiFeature)
    assert feature.enabled is True
    assert feature.confidence == pytest.approx(0.85)
    assert feature.element_bias["metal"] > feature.element_bias["water"]
    assert feature.score_for_digit(7, "metal") > feature.score_for_digit(0, "water")


def test_validate_payload_accepts_numeric_strings():
    feature = validate_ai_payload(
        _valid_payload(
            element_bias={
                "wood": "0.10",
                "fire": "0.15",
                "earth": "0.20",
                "metal": "0.35",
                "water": "0.20",
            },
            digit_bias={
                "0": "0.05",
                "1": "0.05",
                "2": "0.08",
                "3": "0.08",
                "4": "0.09",
                "5": "0.10",
                "6": "0.10",
                "7": "0.18",
                "8": "0.17",
                "9": "0.10",
            },
        )
    )

    assert feature.enabled is True
    assert feature.element_bias["metal"] == pytest.approx(0.35)


@pytest.mark.parametrize("field", ["numbers", "number", "prediction_numbers"])
def test_validate_payload_rejects_specific_number_fields(field):
    feature = validate_ai_payload(_valid_payload(**{field: [7, 8, 9]}))

    assert feature.enabled is False
    assert feature.score_for_digit(7, "metal") == 50.0


@pytest.mark.parametrize("phrase", ["必中", "保证", "稳赚"])
def test_validate_payload_rejects_promissory_explanation(phrase):
    feature = validate_ai_payload(
        _valid_payload(explanation=f"娱乐参考，但这个组合{phrase}。")
    )

    assert feature.enabled is False


def test_validate_payload_rejects_blank_explanation():
    feature = validate_ai_payload(_valid_payload(explanation=" \t\n "))

    assert feature.enabled is False


def test_validate_payload_requires_lucky_themes():
    payload = _valid_payload()
    del payload["lucky_themes"]

    feature = validate_ai_payload(payload)

    assert feature.enabled is False


def test_validate_payload_rejects_promissory_lucky_themes():
    feature = validate_ai_payload(_valid_payload(lucky_themes=["金气", "稳赚"]))

    assert feature.enabled is False


@pytest.mark.parametrize("themes", [None, [], [" ", "\t"]])
def test_validate_payload_rejects_empty_lucky_themes(themes):
    feature = validate_ai_payload(_valid_payload(lucky_themes=themes))

    assert feature.enabled is False


@pytest.mark.parametrize("phrase", ["保證", "保証", "guarantee", "guaranteed"])
def test_validate_payload_rejects_normalized_promissory_text(phrase):
    feature = validate_ai_payload(_valid_payload(explanation=f"娱乐参考 {phrase}"))

    assert feature.enabled is False


@pytest.mark.parametrize("explanation", ["建议 04 16 29", "推薦號碼８", "number 8"])
def test_validate_payload_rejects_specific_numbers_in_explanation(explanation):
    feature = validate_ai_payload(_valid_payload(explanation=explanation))

    assert feature.enabled is False


def test_validate_payload_rejects_specific_numbers_in_lucky_themes():
    feature = validate_ai_payload(_valid_payload(lucky_themes=["金气", "推薦號碼８"]))

    assert feature.enabled is False


@pytest.mark.parametrize(
    "payload",
    [
        "not a dict",
        _valid_payload(element_bias={"wood": 1.0}),
        _valid_payload(digit_bias={str(i): 0.2 for i in range(10)}),
        _valid_payload(element_bias={
            "wood": 0.1,
            "fire": 0.1,
            "earth": 0.2,
            "metal": 0.3,
            "water": float("inf"),
        }),
        _valid_payload(digit_bias={
            "0": 0.05,
            "1": 0.05,
            "2": 0.08,
            "3": 0.08,
            "4": 0.09,
            "5": 0.10,
            "6": 0.10,
            "7": 0.18,
            "8": 0.17,
            "9": float("nan"),
        }),
        _valid_payload(confidence=-0.01),
        _valid_payload(confidence=95),
        _valid_payload(extra_field=True),
    ],
)
def test_validate_payload_rejects_missing_unnormalized_non_finite_or_illegal_payloads(
    payload,
):
    feature = validate_ai_payload(payload)

    assert feature.enabled is False


def test_deepseek_provider_without_api_key_falls_back_to_neutral(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    feature = DeepSeekFlashProvider().extract({"game": "ssq"})

    assert feature.enabled is False
    assert "未启用" in feature.explanation


def test_deepseek_provider_uses_flash_model_and_parses_mock_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-flash"
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert "具体号码" in body["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_valid_payload(confidence=0.5))
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = DeepSeekFlashProvider(client=client)

    feature = provider.extract({"game": "ssq", "draw_date": "2026-06-18"})

    assert feature.enabled is True
    assert feature.confidence == pytest.approx(0.5)
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.deepseek.com/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-key"


def test_prediction_engine_deepseek_http_body_contains_only_minimized_personal_context(
    monkeypatch,
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_valid_payload(confidence=0.5))
                        }
                    }
                ]
            },
        )

    personal = PersonalInput(
        name="隐私姓名-Sentinel",
        birth_date="1988-12-31",
        birth_hour="午",
        birth_place="隐私出生地",
        current_city="隐私城市",
    )
    provider = DeepSeekFlashProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    payload = PredictionEngine(EmptyRepo(), provider).predict(
        "ssq", personal, today="2026-06-16", fortune_mode="windfall"
    )

    assert payload["personal_basis"]["ai_enabled"] is True
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    serialized_body = json.dumps(body, ensure_ascii=False, sort_keys=True)
    for raw_value in (
        personal.name,
        personal.birth_date,
        personal.birth_hour,
        personal.birth_place,
        personal.current_city,
    ):
        assert raw_value not in serialized_body

    user_message = next(
        message for message in body["messages"] if message["role"] == "user"
    )
    context = json.loads(user_message["content"])["context"]
    assert set(context) == {
        "game_key",
        "fortune_mode",
        "best_draw_date",
        "personal_features",
    }
    assert set(context["personal_features"]) == {
        "birth_vector",
        "birth_hour_known",
        "calendar_type",
        "location_relation",
    }
    assert context["personal_features"]["birth_hour_known"] is True
    assert context["personal_features"]["calendar_type"] == "solar"
    assert context["personal_features"]["location_relation"] == "different"
    assert set(context["personal_features"]["birth_vector"]) == {
        "wood",
        "fire",
        "earth",
        "metal",
        "water",
    }
    assert "personal" not in context


def test_deepseek_provider_reads_model_from_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-env-model")
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "deepseek-env-model"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_valid_payload(confidence=0.5))
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    feature = DeepSeekFlashProvider(client=client).extract({"game": "ssq"})

    assert feature.enabled is True
    assert len(requests) == 1


class _ReusableTransport(httpx.BaseTransport):
    def __init__(self):
        self.calls = 0
        self.closed = False

    def handle_request(self, request):
        if self.closed:
            raise RuntimeError("transport was closed")
        self.calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(_valid_payload(confidence=0.5))
                        }
                    }
                ]
            },
        )

    def close(self):
        self.closed = True


def test_deepseek_provider_reuses_transport_client_and_exposes_close(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    transport = _ReusableTransport()
    provider = DeepSeekFlashProvider(transport=transport)

    first = provider.extract({"game": "ssq"})
    second = provider.extract({"game": "ssq"})

    assert first.enabled is True
    assert second.enabled is True
    assert transport.calls == 2
    assert transport.closed is False

    provider.close()
    assert transport.closed is True


def test_deepseek_provider_http_error_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )

    feature = DeepSeekFlashProvider(client=client).extract({"game": "ssq"})

    assert feature.enabled is False
    assert "DeepSeek 请求失败" in feature.explanation


def test_deepseek_provider_invalid_json_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "not json"}}]}
            )
        )
    )

    feature = DeepSeekFlashProvider(client=client).extract({"game": "ssq"})

    assert feature.enabled is False
    assert "DeepSeek 响应解析失败" in feature.explanation
