from typing import Any

from .number_tools import ToolError, result_from_candidates
from .strategy import generate_strategy_candidates
from .workbench_3d import filter_candidates as filter_digit_candidates


def conditional_pick(
    game_key: str,
    draws: list[dict[str, Any]],
    source: str,
    preset: str,
    conditions: dict[str, Any],
    count: int,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    if source == "digit_filter":
        if game_key not in {"3d", "pl3"}:
            raise ToolError("invalid_conditional_source", "该彩种不支持数字条件缩水")
        try:
            filtered = filter_digit_candidates({**conditions, "max_results": count})
        except ValueError as exc:
            raise ToolError("invalid_conditions", "数字条件不符合规则") from exc
        candidates = [{"main": row["numbers"], "special": [], "play_type": "straight"} for row in filtered["candidates"]]
        return result_from_candidates(
            game_key, "conditional", candidates, options,
            metadata={"source": source, "total_candidates": filtered["total"], "conditions": filtered["filters"]},
        )
    if source != "strategy":
        raise ToolError("invalid_conditional_source", "不支持的条件选号来源")
    if not draws:
        raise ToolError("history_unavailable", "暂无历史数据，不能应用研究策略")
    if count > 30:
        raise ToolError("invalid_count", "策略条件选号最多生成30组")
    generated = generate_strategy_candidates(
        game_key, draws,
        {"preset": preset, "candidate_count": count, "conditions": conditions},
    )
    return result_from_candidates(
        game_key, "conditional", generated["candidates"], options,
        metadata={"source": source, "preset": generated["preset"], "strategy_name": generated["strategy_name"], "conditions": generated["conditions"]},
    )
