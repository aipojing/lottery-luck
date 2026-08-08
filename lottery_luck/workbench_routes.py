from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date
from typing import Annotated, Any, Literal, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from .data_health import build_public_freshness
from .plans import resolve_3d_target
from .plan_routes import get_repository
from .repository import LotteryRepository
from .three_d_tools import build_trend_payload
from .workbench_3d import (
    build_workbench_summary,
    filter_candidates,
    query_number,
    recent_draw_summaries,
)


WORKBENCH_SERVICE_UNAVAILABLE = "workbench service is unavailable"
CURRENT_DATA_UNAVAILABLE = "current data is not available"
TODAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
WINDOW_PATTERN = r"^(30|60|120)$"
TODAY_RE = re.compile(TODAY_PATTERN)
LOGGER = logging.getLogger(__name__)

Digit = Annotated[StrictInt, Field(ge=0, le=9)]
NumberDigits = Annotated[list[Digit], Field(min_length=3, max_length=3)]
WindowQuery = Annotated[str, Query(pattern=WINDOW_PATTERN)]
WindowValue = Literal[30, 60, 120]

router = APIRouter(prefix="/api")


def _today_from_request(
    request: Request,
    today: Annotated[str | None, Query(pattern=TODAY_PATTERN)] = None,
) -> date:
    _ = today
    values = request.query_params.getlist("today")
    if not values:
        return date.today()
    if len(values) != 1:
        raise HTTPException(status_code=422, detail="invalid today")
    value = values[0]
    if TODAY_RE.fullmatch(value) is None:
        raise HTTPException(status_code=422, detail="invalid today")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid today") from exc


CurrentDay = Annotated[date, Depends(_today_from_request)]


class NumberQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    number: str | NumberDigits
    window: WindowValue = 120

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: Any) -> Any:
        if isinstance(value, str):
            if len(value) != 3 or not value.isascii() or not value.isdecimal():
                raise ValueError("invalid 3d number")
            return value
        if isinstance(value, list) and len(value) == 3:
            return value
        raise ValueError("invalid 3d number")

    def number_text(self) -> str:
        if isinstance(self.number, str):
            return self.number
        return "".join(str(digit) for digit in self.number)


class CandidateFilterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    filters: dict[str, Any]
    window: WindowValue = 30

    @field_validator("filters")
    @classmethod
    def require_filter_dict(cls, value: Any) -> dict[str, Any]:
        if type(value) is not dict:
            raise ValueError("filters must be an object")
        return value


@router.get("/workbench/3d/summary")
def workbench_summary(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    current_day: CurrentDay,
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
    window: WindowQuery = "30",
) -> dict[str, Any]:
    normalized_window = int(window)
    try:
        freshness = _public_3d_freshness(repo, current_day)
        draws = repo.recent_draws("3d", limit=normalized_window)
        payload = build_workbench_summary(draws, normalized_window)
        current_target = _current_target(freshness)
        client_id = _optional_client_id(x_lottery_client_id)
        if client_id and current_target is not None:
            plan_summary = repo.active_plan_summary(
                client_id,
                game_key="3d",
                target_issue=current_target["target_issue"],
            )
        else:
            plan_summary = {"count": 0, "latest_plan": None}
    except HTTPException:
        raise
    except Exception as exc:
        _handle_workbench_exception(exc)

    payload["freshness"] = freshness
    payload["actions"] = _actions(freshness, draws)
    payload["current_target"] = current_target
    payload["recent_draws"] = recent_draw_summaries(draws, limit=10)
    payload["active_plan_count"] = int(plan_summary.get("count") or 0)
    payload["latest_plan"] = plan_summary.get("latest_plan")
    return payload


@router.post("/3d/number-query")
def number_query(
    request: NumberQueryRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    current_day: CurrentDay,
) -> dict[str, Any]:
    try:
        freshness = _public_3d_freshness(repo, current_day)
        draws = repo.recent_draws("3d", limit=request.window)
        # The stats must describe the window that was actually fetched, never a wider one.
        payload = query_number(request.number_text(), draws, request.window)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_workbench_exception(exc)

    payload["freshness"] = freshness
    payload["actions"] = _actions(freshness, draws)
    return payload


@router.post("/3d/filter")
def filter_3d_candidates(
    request: CandidateFilterRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    current_day: CurrentDay,
) -> dict[str, Any]:
    try:
        freshness = _public_3d_freshness(repo, current_day)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_workbench_exception(exc)

    if not freshness["can_claim_current"]:
        raise HTTPException(status_code=409, detail=CURRENT_DATA_UNAVAILABLE)

    try:
        draws = repo.recent_draws("3d", limit=request.window)
    except Exception as exc:
        _handle_workbench_exception(exc)

    try:
        payload = filter_candidates(request.filters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid 3d filter") from exc
    except Exception as exc:
        _handle_unexpected_exception(exc)

    payload["freshness"] = freshness
    payload["actions"] = _actions(freshness, draws)
    return payload


@router.get("/3d/trends")
def three_d_trends(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    current_day: CurrentDay,
    window: WindowQuery = "30",
) -> dict[str, Any]:
    normalized_window = int(window)
    try:
        freshness = _public_3d_freshness(repo, current_day)
        draws = repo.recent_draws("3d", limit=normalized_window)
        payload = build_trend_payload(draws, normalized_window)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_workbench_exception(exc)

    payload["freshness"] = freshness
    payload["actions"] = _actions(freshness, draws)
    return payload


def _public_3d_freshness(
    repo: LotteryRepository,
    current_day: date,
) -> dict[str, Any]:
    games_by_key = {
        str(game.get("game_key") or "").strip().lower(): game
        for game in repo.list_games()
    }
    game = games_by_key.get("3d") or _empty_3d_game()
    logs = repo.recent_crawl_logs_by_game(["3d"], limit_per_game=20)
    return build_public_freshness(game, today=current_day, logs=logs)


def _empty_3d_game() -> dict[str, Any]:
    return {
        "game_key": "3d",
        "game_name": "福彩3D",
        "draw_count": 0,
        "earliest_date": "",
        "latest_date": "",
        "latest_issue": "",
        "provider": "cwl",
    }


def _actions(freshness: dict[str, Any], draws: list[dict[str, Any]]) -> dict[str, bool]:
    can_claim_current = bool(freshness.get("can_claim_current"))
    return {
        "can_filter_current": can_claim_current,
        "can_save_current": can_claim_current,
        "can_read_history": bool(draws),
    }


def _current_target(freshness: dict[str, Any]) -> dict[str, str] | None:
    latest_issue = str(freshness.get("latest_issue") or "").strip()
    latest_date = str(freshness.get("latest_date") or "").strip()
    if not latest_issue or not latest_date:
        return None
    try:
        return resolve_3d_target(latest_issue, latest_date)
    except ValueError:
        return None


def _optional_client_id(value: str | None) -> str:
    return str(value or "").strip()[:96]


def _handle_workbench_exception(exc: Exception) -> NoReturn:
    if isinstance(exc, (sqlite3.Error, OSError)):
        LOGGER.exception("workbench service infrastructure unavailable")
        _raise_unavailable(exc)
    if isinstance(exc, ValueError):
        LOGGER.warning("workbench persisted data invalid", exc_info=True)
        _raise_unavailable(exc)
    _handle_unexpected_exception(exc)


def _handle_unexpected_exception(exc: Exception) -> NoReturn:
    LOGGER.exception("workbench unexpected error")
    raise exc


def _raise_unavailable(exc: Exception) -> NoReturn:
    raise HTTPException(status_code=503, detail=WORKBENCH_SERVICE_UNAVAILABLE) from exc
