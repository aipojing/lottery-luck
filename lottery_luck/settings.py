from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SCORE_KEYS = ("personal_space", "ai_fortune", "draw_day_luck", "history_guardrail")

DEFAULT_METAPHYSICS_WEIGHTS: dict[str, dict[str, int]] = {
    "steady": {
        "personal_space": 40,
        "ai_fortune": 25,
        "draw_day_luck": 20,
        "history_guardrail": 15,
    },
    "windfall": {
        "personal_space": 32,
        "ai_fortune": 28,
        "draw_day_luck": 30,
        "history_guardrail": 10,
    },
    "guard": {
        "personal_space": 45,
        "ai_fortune": 18,
        "draw_day_luck": 12,
        "history_guardrail": 25,
    },
}

DEFAULT_AI_COPY_STYLES = [
    {
        "key": "short_hook",
        "label": "短钩子",
        "description": "一句话命中本期财格，用于首页第一眼信服。",
    },
    {
        "key": "long_reading",
        "label": "长解读",
        "description": "解释命格、喜用元素、开奖日气口和号码组合关系。",
    },
    {
        "key": "review_copy",
        "label": "复盘话术",
        "description": "开奖后把命中、财眼和解释贴合度说清楚。",
    },
]

DEFAULT_PREDICTION_QUOTA: dict[str, Any] = {
    "free_daily": 1,
    "new_user_bonus": 3,
    "member_daily": 20,
    "package_units": [6, 18, 66],
    "mode_costs": {
        "steady": 1,
        "windfall": 1,
        "guard": 1,
    },
    "enabled_games": ["ssq", "dlt", "3d", "pl3", "kl8"],
    "allow_demo_after_exhausted": True,
}


def get_settings() -> dict[str, Any]:
    override = _load_json_override()
    return {
        "metaphysics_weights": _metaphysics_weights_from_override(override),
        "ai_copy_styles": _ai_copy_styles_from_override(override),
        "prediction_quota": _prediction_quota_from_override(override),
        "source": str(os.getenv("LOTTERY_LUCK_SETTINGS_PATH") or "default"),
    }


def get_metaphysics_weights() -> dict[str, dict[str, int]]:
    return get_settings()["metaphysics_weights"]


def get_prediction_quota() -> dict[str, Any]:
    return get_settings()["prediction_quota"]


def _load_json_override() -> dict[str, Any]:
    path = os.getenv("LOTTERY_LUCK_SETTINGS_PATH")
    if not path:
        return {}
    settings_path = Path(path)
    if not settings_path.exists():
        return {}
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _metaphysics_weights_from_override(override: dict[str, Any]) -> dict[str, dict[str, int]]:
    configured = override.get("metaphysics_weights")
    if not isinstance(configured, dict):
        return {mode: dict(weights) for mode, weights in DEFAULT_METAPHYSICS_WEIGHTS.items()}

    result = {mode: dict(weights) for mode, weights in DEFAULT_METAPHYSICS_WEIGHTS.items()}
    for mode, defaults in DEFAULT_METAPHYSICS_WEIGHTS.items():
        raw = configured.get(mode)
        if not isinstance(raw, dict):
            continue
        for key in SCORE_KEYS:
            result[mode][key] = _safe_weight(raw.get(key), defaults[key])
    return result


def _ai_copy_styles_from_override(override: dict[str, Any]) -> list[dict[str, str]]:
    raw_styles = override.get("ai_copy_styles")
    if not isinstance(raw_styles, list):
        return [dict(style) for style in DEFAULT_AI_COPY_STYLES]
    styles = []
    for item in raw_styles:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        description = str(item.get("description") or "").strip()
        if key and label:
            styles.append({"key": key, "label": label, "description": description})
    return styles or [dict(style) for style in DEFAULT_AI_COPY_STYLES]


def _safe_weight(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(0, min(100, number))


def _prediction_quota_from_override(override: dict[str, Any]) -> dict[str, Any]:
    raw = override.get("prediction_quota")
    if not isinstance(raw, dict):
        return _default_prediction_quota()

    result = _default_prediction_quota()
    result["free_daily"] = _safe_int(raw.get("free_daily"), result["free_daily"], 0, 9999)
    result["new_user_bonus"] = _safe_int(
        raw.get("new_user_bonus"),
        result["new_user_bonus"],
        0,
        9999,
    )
    result["member_daily"] = _safe_int(raw.get("member_daily"), result["member_daily"], 0, 9999)
    result["allow_demo_after_exhausted"] = _safe_bool(
        raw.get("allow_demo_after_exhausted"),
        result["allow_demo_after_exhausted"],
    )

    package_units = raw.get("package_units")
    if isinstance(package_units, list):
        parsed_units = [
            _safe_int(unit, 0, 1, 99999)
            for unit in package_units
            if _safe_int(unit, 0, 1, 99999) > 0
        ]
        if parsed_units:
            result["package_units"] = parsed_units

    mode_costs = raw.get("mode_costs")
    if isinstance(mode_costs, dict):
        for mode, default in result["mode_costs"].items():
            result["mode_costs"][mode] = _safe_int(mode_costs.get(mode), default, 0, 99)

    enabled_games = raw.get("enabled_games")
    if isinstance(enabled_games, list):
        parsed_games = [str(game).strip().lower() for game in enabled_games if str(game).strip()]
        if parsed_games:
            result["enabled_games"] = parsed_games

    return result


def _default_prediction_quota() -> dict[str, Any]:
    return {
        **DEFAULT_PREDICTION_QUOTA,
        "package_units": list(DEFAULT_PREDICTION_QUOTA["package_units"]),
        "mode_costs": dict(DEFAULT_PREDICTION_QUOTA["mode_costs"]),
        "enabled_games": list(DEFAULT_PREDICTION_QUOTA["enabled_games"]),
    }


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(minimum, min(maximum, number))


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(default)
