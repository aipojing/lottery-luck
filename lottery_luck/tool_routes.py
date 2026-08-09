from __future__ import annotations

from typing import Annotated, Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .conditional_tools import conditional_pick
from .number_tools import (
    PUBLIC_TOOL_GAMES,
    ToolError,
    compose_dantuo,
    compose_digit_group,
    compose_full,
    organize_batches,
    quick_pick,
    reduce_by_budget,
    tool_config_payload,
)
from .plan_routes import get_repository
from .repository import LotteryRepository


router = APIRouter(prefix="/api/tools")


class ToolOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    multiplier: StrictInt = Field(default=1, ge=1, le=99)
    add_on: StrictBool | None = None
    play_type: StrictInt | None = None

    def to_domain_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class QuickPickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    count: StrictInt = Field(default=1, ge=1, le=20)
    options: ToolOptions = Field(default_factory=ToolOptions)
    locked: dict[str, Any] = Field(default_factory=dict)
    excluded: dict[str, Any] = Field(default_factory=dict)


class ComposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["full", "dantuo", "group3", "group6"]
    selection: dict[str, Any] = Field(default_factory=dict)
    dan: dict[str, Any] = Field(default_factory=dict)
    tuo: dict[str, Any] = Field(default_factory=dict)
    digits: list[StrictInt] = Field(default_factory=list)
    options: ToolOptions = Field(default_factory=ToolOptions)


class ReduceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entries: list[dict[str, Any]] = Field(default_factory=list)
    source: dict[str, Any] | None = None
    budget: StrictInt = Field(ge=2, le=20_000)
    options: ToolOptions = Field(default_factory=ToolOptions)


class OrganizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    batch_a: str = Field(default="", max_length=100_000)
    batch_b: str = Field(default="", max_length=100_000)
    operation: Literal["dedupe", "union", "intersection", "difference"] = "dedupe"
    options: ToolOptions = Field(default_factory=ToolOptions)


class ConditionalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["strategy", "digit_filter"] = "strategy"
    preset: Literal["balanced", "conservative", "aggressive"] = "balanced"
    count: StrictInt = Field(default=8, ge=1, le=200)
    window: StrictInt = Field(default=120, ge=1, le=300)
    conditions: dict[str, Any] = Field(default_factory=dict)
    options: ToolOptions = Field(default_factory=ToolOptions)


def _ensure_game(game_key: str) -> None:
    if game_key not in PUBLIC_TOOL_GAMES:
        raise HTTPException(
            status_code=404,
            detail={"code": "invalid_game", "message": "unsupported lottery game"},
        )


def _run_tool(callback: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        payload = callback()
    except ToolError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    if "spend_limit" in payload.get("warnings", []):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "spend_limit",
                "message": "estimated spend exceeds 20000 yuan",
            },
        )
    return payload


@router.get("/config")
def tool_config() -> dict[str, Any]:
    return tool_config_payload()


@router.post("/{game_key}/quick-pick")
def tool_quick_pick(game_key: str, request: QuickPickRequest) -> dict[str, Any]:
    _ensure_game(game_key)
    return _run_tool(
        lambda: quick_pick(
            game_key,
            request.count,
            request.options.to_domain_payload(),
            request.locked,
            request.excluded,
        )
    )


@router.post("/{game_key}/compose")
def tool_compose(game_key: str, request: ComposeRequest) -> dict[str, Any]:
    _ensure_game(game_key)
    options = request.options.to_domain_payload()
    if request.mode == "full":
        return _run_tool(lambda: compose_full(game_key, request.selection, options))
    if request.mode == "dantuo":
        return _run_tool(lambda: compose_dantuo(game_key, request.dan, request.tuo, options))
    return _run_tool(
        lambda: compose_digit_group(game_key, request.digits, request.mode, options)
    )


@router.post("/{game_key}/reduce")
def tool_reduce(game_key: str, request: ReduceRequest) -> dict[str, Any]:
    _ensure_game(game_key)
    return _run_tool(
        lambda: reduce_by_budget(
            game_key,
            request.entries,
            request.budget,
            request.options.to_domain_payload(),
            source=request.source,
        )
    )


@router.post("/{game_key}/organize")
def tool_organize(game_key: str, request: OrganizeRequest) -> dict[str, Any]:
    _ensure_game(game_key)
    return _run_tool(
        lambda: organize_batches(
            game_key,
            request.batch_a,
            request.batch_b,
            request.operation,
            request.options.to_domain_payload(),
        )
    )


@router.post("/{game_key}/conditional")
def tool_conditional(
    game_key: str,
    request: ConditionalRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    _ensure_game(game_key)
    draws = [] if request.source == "digit_filter" else repo.recent_draws(game_key, limit=request.window)
    return _run_tool(lambda: conditional_pick(
        game_key, draws, request.source, request.preset,
        request.conditions, request.count, request.options.to_domain_payload(),
    ))
