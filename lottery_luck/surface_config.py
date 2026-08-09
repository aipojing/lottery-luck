from __future__ import annotations

from copy import deepcopy
from typing import Any

from .rules import FRONTEND_GAME_KEYS

COMMON_STRATEGY_FEATURES = ["preset", "backtest", "compare", "save"]
LOTTO_STRATEGY_FIELDS = [
    "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
    "max_consecutive_run", "ac_min", "ac_max", "prime_composite", "mod3",
    "zone", "tail_exclude", "tail_include", "min_omission",
]
DIGIT_STRATEGY_FIELDS = [
    "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
    "max_consecutive_run", "prime_composite", "mod3", "tail_exclude",
    "tail_include", "min_omission",
]
COMMON_TOOLS = ["quick", "lock", "full", "dantuo", "conditional", "reduce", "organize"]

GAME_SURFACES: dict[str, dict[str, Any]] = {
    "ssq": {
        "label": "双色球",
        "research": {"data": ["hot_cold", "omission", "trend", "shape", "special_zone", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "zone_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
    "dlt": {
        "label": "大乐透",
        "research": {"data": ["hot_cold", "omission", "trend", "shape", "special_zone", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "zone_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
    "3d": {
        "label": "福彩3D",
        "research": {"data": ["position_trend", "position_omission", "frequency", "heat", "number_query", "number_attributes", "digit_shape", "recent"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "digit_shape"], "condition_fields": DIGIT_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "组选包号", "full": "定位复式", "conditional": "条件缩水"},
    },
    "pl3": {
        "label": "排列3",
        "research": {"data": ["position_trend", "position_omission", "frequency", "heat", "number_query", "number_attributes", "digit_shape", "recent"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "digit_shape"], "condition_fields": DIGIT_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "组选包号", "full": "定位复式", "conditional": "条件缩水"},
    },
    "kl8": {
        "label": "快乐8",
        "research": {"data": ["hot_cold", "omission", "range_density", "odd_even", "repeat", "consecutive", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "large_field_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
}


def capabilities_for_game(game_key: str) -> dict[str, Any]:
    key = str(game_key).strip().lower()
    if key not in GAME_SURFACES:
        raise KeyError(key)
    return deepcopy(GAME_SURFACES[key])


def surface_config_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "views": ["data", "strategy"],
        "games": {key: capabilities_for_game(key) for key in FRONTEND_GAME_KEYS},
    }
