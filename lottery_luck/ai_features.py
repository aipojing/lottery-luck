from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import httpx

from lottery_luck.personal import DIGIT_ELEMENT, ELEMENTS

_DIGITS = tuple(str(digit) for digit in range(10))
_ALLOWED_FIELDS = {
    "element_bias",
    "digit_bias",
    "lucky_themes",
    "explanation",
    "confidence",
}
_FORBIDDEN_NUMBER_FIELDS = {
    "number",
    "numbers",
    "prediction_number",
    "prediction_numbers",
    "predicted_number",
    "predicted_numbers",
    "recommended_numbers",
    "winning_numbers",
}
_PROMISSORY_PHRASES = ("必中", "保证", "保證", "保証", "稳赚", "穩賺")
_PROMISSORY_WORDS = ("guarantee", "guaranteed")
_PREDICTION_WORDS = (
    "号码",
    "號碼",
    "number",
    "数字",
    "digit",
    "推荐",
    "建议",
    "推薦",
)
_NORMALIZATION_TOLERANCE = 1e-6


class AiProviderError(RuntimeError):
    """Base error for user-visible AI provider failures."""


class AiAuthenticationError(AiProviderError):
    """The provider rejected the supplied credential."""


class AiServiceUnavailableError(AiProviderError):
    """The provider could not complete the request."""


class AiProviderResponseError(AiProviderError):
    """The provider returned a response that cannot be used safely."""


@dataclass(frozen=True)
class AiFeature:
    enabled: bool
    element_bias: dict[str, float]
    digit_bias: dict[str, float]
    lucky_themes: list[str]
    explanation: str
    confidence: float

    def score_for_digit(self, digit: int, element: str) -> float:
        if not self.enabled:
            return 50.0

        digit_key = str(int(digit) % 10)
        digit_element = element if element in ELEMENTS else DIGIT_ELEMENT[int(digit) % 10]
        if _is_neutral_distribution(self.element_bias, 1.0 / len(ELEMENTS)) and (
            _is_neutral_distribution(self.digit_bias, 1.0 / len(_DIGITS))
        ):
            return 50.0

        digit_score = self.digit_bias.get(digit_key, 0.0) * len(_DIGITS) * 50.0
        element_score = (
            self.element_bias.get(digit_element, 0.0) * len(ELEMENTS) * 50.0
        )
        blended = (digit_score + element_score) / 2.0
        adjusted = 50.0 + (blended - 50.0) * self.confidence
        return round(max(0.0, min(100.0, adjusted)), 4)


def neutral_ai_feature(explanation: str | None = None) -> AiFeature:
    return AiFeature(
        enabled=False,
        element_bias={element: 1.0 / len(ELEMENTS) for element in ELEMENTS},
        digit_bias={digit: 1.0 / len(_DIGITS) for digit in _DIGITS},
        lucky_themes=[],
        explanation=explanation or "AI 特征未启用，使用中性特征。",
        confidence=0.0,
    )


class NullAiProvider:
    def __init__(self, explanation: str | None = None) -> None:
        self.explanation = explanation

    def extract(self, context: Mapping[str, Any] | None = None) -> AiFeature:
        return neutral_ai_feature(self.explanation)


def validate_ai_payload(payload: Any) -> AiFeature:
    if not isinstance(payload, dict):
        return neutral_ai_feature()

    payload_fields = set(payload)
    if payload_fields & _FORBIDDEN_NUMBER_FIELDS:
        return neutral_ai_feature()
    if payload_fields - _ALLOWED_FIELDS:
        return neutral_ai_feature()

    required_fields = {
        "element_bias",
        "digit_bias",
        "lucky_themes",
        "explanation",
        "confidence",
    }
    if not required_fields.issubset(payload):
        return neutral_ai_feature()

    explanation = payload["explanation"]
    if not isinstance(explanation, str):
        return neutral_ai_feature()

    cleaned_explanation = explanation.strip()
    if not cleaned_explanation or _contains_forbidden_text(cleaned_explanation):
        return neutral_ai_feature()

    element_bias = _validated_distribution(payload["element_bias"], ELEMENTS)
    digit_bias = _validated_distribution(payload["digit_bias"], _DIGITS)
    if element_bias is None or digit_bias is None:
        return neutral_ai_feature()

    confidence = _validated_confidence(payload["confidence"])
    if confidence is None:
        return neutral_ai_feature()

    lucky_themes = _validated_themes(payload["lucky_themes"])
    if lucky_themes is None:
        return neutral_ai_feature()
    if any(_contains_forbidden_text(theme) for theme in lucky_themes):
        return neutral_ai_feature()

    return AiFeature(
        enabled=True,
        element_bias=element_bias,
        digit_bias=digit_bias,
        lucky_themes=lucky_themes,
        explanation=cleaned_explanation,
        confidence=min(confidence, 0.85),
    )


class DeepSeekFlashProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 10.0,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        strict_errors: bool = False,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY")
        self.model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._transport = transport
        self._owns_client = client is None
        self.strict_errors = strict_errors

    def extract(self, context: Mapping[str, Any] | None = None) -> AiFeature:
        if not self.api_key:
            return neutral_ai_feature()

        try:
            response = self._get_client().post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": _system_prompt(),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"context": context or {}}, ensure_ascii=False
                            ),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 400,
                    "thinking": {"type": "disabled"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            feature = validate_ai_payload(json.loads(content))
            if not feature.enabled:
                if self.strict_errors:
                    raise AiProviderResponseError("DeepSeek returned an invalid response")
                return neutral_ai_feature("DeepSeek 返回格式未通过校验，使用中性特征。")
            return feature
        except httpx.HTTPStatusError as exc:
            if self.strict_errors:
                if exc.response.status_code in {401, 403}:
                    raise AiAuthenticationError("DeepSeek rejected the API key") from exc
                raise AiServiceUnavailableError("DeepSeek request failed") from exc
            return neutral_ai_feature("DeepSeek 请求失败，使用中性特征。")
        except httpx.HTTPError as exc:
            if self.strict_errors:
                raise AiServiceUnavailableError("DeepSeek request failed") from exc
            return neutral_ai_feature("DeepSeek 请求失败，使用中性特征。")
        except AiProviderError:
            raise
        except Exception as exc:
            if self.strict_errors:
                raise AiProviderResponseError("DeepSeek response could not be parsed") from exc
            return neutral_ai_feature("DeepSeek 响应解析失败，使用中性特征。")

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, transport=self._transport)
        return self._client


def _system_prompt() -> str:
    return (
        "你是彩票娱乐网页的 AI 特征提取层，只能输出 JSON。"
        "不得输出具体号码、日期、中奖承诺或任何预测结论。"
        "不得使用必中、保证、稳赚等承诺语。"
        "只输出 element_bias、digit_bias、lucky_themes、explanation、confidence。"
        "element_bias 必须包含 wood/fire/earth/metal/water 且总和为 1。"
        "digit_bias 必须包含字符串键 0 到 9 且总和为 1。"
        "confidence 取 0 到 0.85，explanation 说明娱乐特征依据。"
    )


def _validated_distribution(
    values: Any, required_keys: tuple[str, ...]
) -> dict[str, float] | None:
    if not isinstance(values, dict) or set(values) != set(required_keys):
        return None

    normalized: dict[str, float] = {}
    for key in required_keys:
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            return None
        try:
            number = float(value)
        except ValueError:
            return None
        if not isfinite(number) or number < 0.0:
            return None
        normalized[key] = number

    if abs(sum(normalized.values()) - 1.0) > _NORMALIZATION_TOLERANCE:
        return None
    return normalized


def _validated_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None

    confidence = float(value)
    if not isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        return None
    return confidence


def _validated_themes(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None

    themes: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        cleaned = item.strip()
        if cleaned:
            themes.append(cleaned)
    if not themes:
        return None
    return themes[:8]


def _is_neutral_distribution(values: Mapping[str, float], expected: float) -> bool:
    return all(abs(value - expected) <= _NORMALIZATION_TOLERANCE for value in values.values())


def _contains_forbidden_text(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    if any(phrase in normalized for phrase in _PROMISSORY_PHRASES):
        return True
    if any(word in normalized for word in _PROMISSORY_WORDS):
        return True

    for sentence in re.split(r"[。！？.!?;\n]+", normalized):
        if any(word in sentence for word in _PREDICTION_WORDS) and re.search(
            r"\d", sentence
        ):
            return True
    return False
