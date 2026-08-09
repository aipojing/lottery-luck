from __future__ import annotations

import re
import sqlite3
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .repository import (
    LotteryRepository,
    PlanDrawUnavailableError,
    PlanNotFoundError,
    PlanRequestConflictError,
    PlanTargetAlreadyDrawnError,
)
from .write_limits import WriteRateLimitExceeded, enforce_request_write_limits


Digit = Annotated[StrictInt, Field(ge=0, le=9)]
Position = Annotated[StrictInt, Field(ge=0, le=49)]
IssueText = Annotated[str, Field(min_length=1, max_length=32)]
RequestId = Annotated[str, Field(max_length=96)]
PLAN_SERVICE_UNAVAILABLE = "plan service is unavailable"
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

router = APIRouter(prefix="/api")


def get_repository() -> LotteryRepository:
    return LotteryRepository()


def _client_id(value: str | None) -> str:
    client_id = str(value or "").strip()[:96]
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Lottery-Client-Id is required")
    return client_id


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="plan not found")


def _parse_iso_date(value: Any) -> Any:
    if isinstance(value, str):
        if not ISO_DATE_RE.fullmatch(value):
            raise ValueError("date must be YYYY-MM-DD")
        return date.fromisoformat(value)
    return value


class PlanEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    position: Position | None = None
    main_numbers: list[Digit] = Field(min_length=3, max_length=3)
    special_numbers: list[StrictInt] = Field(default_factory=list, max_length=0)
    note: str = Field(default="", max_length=120)

    @field_validator("note", mode="before")
    @classmethod
    def strip_note(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    def to_domain_payload(self) -> dict[str, Any]:
        payload = {
            "main_numbers": list(self.main_numbers),
            "special_numbers": [],
            "note": self.note,
        }
        if self.position is not None:
            payload["position"] = self.position
        return payload


class PlanConditionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["simple", "pro"]
    analysis_window: Literal[30, 60, 120]
    conditions: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    latest_data_issue: IssueText
    latest_data_date: date

    @field_validator("latest_data_issue", mode="before")
    @classmethod
    def strip_issue(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("latest_data_date", mode="before")
    @classmethod
    def parse_latest_data_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)

    def to_domain_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "analysis_window": self.analysis_window,
            "conditions_json": self.conditions,
            "metrics_json": self.metrics,
            "latest_data_issue": self.latest_data_issue,
            "latest_data_date": self.latest_data_date.isoformat(),
        }


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    game_key: Literal["3d"]
    target_issue: IssueText
    target_draw_date: date
    source_type: Literal["fortune", "manual", "filter", "random", "carried"]
    request_id: RequestId = ""
    title: str = Field(min_length=1, max_length=80)
    entries: list[PlanEntryInput] = Field(min_length=1, max_length=50)
    condition_snapshot: PlanConditionInput

    @field_validator("target_issue", "request_id", "title", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("target_draw_date", mode="before")
    @classmethod
    def parse_target_draw_date(cls, value: Any) -> Any:
        return _parse_iso_date(value)

    def to_domain_payload(self) -> dict[str, Any]:
        return {
            "game_key": "3d",
            "target_issue": self.target_issue,
            "target_draw_date": self.target_draw_date.isoformat(),
            "source_type": self.source_type,
            "request_id": self.request_id,
            "title": self.title,
            "entries": [entry.to_domain_payload() for entry in self.entries],
            "condition_snapshot": self.condition_snapshot.to_domain_payload(),
        }


class PlanPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = Field(default=None, min_length=1, max_length=80)
    status: Literal["draft", "saved", "pending_review", "expired"] | None = None
    entries: list[PlanEntryInput] | None = Field(default=None, min_length=1, max_length=50)
    condition_snapshot: PlanConditionInput | None = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "PlanPatchRequest":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self

    def to_domain_updates(self) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        if "title" in self.model_fields_set:
            updates["title"] = self.title
        if "status" in self.model_fields_set:
            updates["status"] = self.status
        if "entries" in self.model_fields_set:
            updates["entries"] = [
                entry.to_domain_payload() for entry in (self.entries or [])
            ]
        if "condition_snapshot" in self.model_fields_set:
            updates["condition_snapshot"] = (
                self.condition_snapshot.to_domain_payload()
                if self.condition_snapshot is not None
                else None
            )
        return updates


class CarryForwardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: RequestId = ""

    @field_validator("request_id", mode="before")
    @classmethod
    def strip_request_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


def _handle_plan_value_error(exc: ValueError) -> None:
    message = str(exc)
    if message == "request id conflicts with an existing plan":
        raise HTTPException(
            status_code=409,
            detail="request id conflicts with an existing plan",
        ) from exc
    if message == "invalid target":
        raise HTTPException(status_code=409, detail="invalid target") from exc
    if message == "invalid review":
        raise HTTPException(status_code=409, detail="invalid review") from exc
    raise HTTPException(status_code=422, detail="invalid plan") from exc


def _handle_lifecycle_error(exc: Exception) -> None:
    if isinstance(exc, PlanNotFoundError):
        raise _not_found() from exc
    if isinstance(exc, PlanDrawUnavailableError):
        raise HTTPException(status_code=409, detail="draw is not available") from exc
    if isinstance(exc, PlanTargetAlreadyDrawnError):
        raise HTTPException(
            status_code=409,
            detail="target issue is already drawn",
        ) from exc
    if isinstance(exc, PlanRequestConflictError):
        raise HTTPException(
            status_code=409,
            detail="request id conflicts with an existing plan",
        ) from exc
    raise exc


def _handle_sqlite_error(exc: sqlite3.Error) -> None:
    raise HTTPException(status_code=503, detail=PLAN_SERVICE_UNAVAILABLE) from exc


@router.post("/plans", status_code=201)
def create_plan(
    request: PlanCreateRequest,
    http_request: Request,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        enforce_request_write_limits(
            repo,
            http_request,
            client_id=client_id,
            category="plans",
        )
        plan = repo.create_plan_lifecycle(client_id, request.to_domain_payload())
    except WriteRateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="write rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (
        PlanDrawUnavailableError,
        PlanNotFoundError,
        PlanRequestConflictError,
        PlanTargetAlreadyDrawnError,
    ) as exc:
        _handle_lifecycle_error(exc)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    return {"plan": plan}


@router.get("/plans")
def list_plans(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        plans = repo.list_plans(client_id)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    return {"plans": plans}


@router.get("/plans/{plan_id}")
def get_plan(
    plan_id: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        plan = repo.get_plan(client_id, plan_id)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    if plan is None:
        raise _not_found()
    return {"plan": plan}


@router.patch("/plans/{plan_id}")
def patch_plan(
    plan_id: str,
    request: PlanPatchRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        plan = repo.update_plan(client_id, plan_id, request.to_domain_updates())
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    if plan is None:
        raise _not_found()
    return {"plan": plan}


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> Response:
    client_id = _client_id(x_lottery_client_id)
    try:
        deleted = repo.delete_plan(client_id, plan_id)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    if not deleted:
        raise _not_found()
    return Response(status_code=204)


@router.post("/plans/{plan_id}/review")
def review_plan(
    plan_id: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        reviewed = repo.review_plan_lifecycle(client_id, plan_id)
    except (
        PlanDrawUnavailableError,
        PlanNotFoundError,
        PlanRequestConflictError,
        PlanTargetAlreadyDrawnError,
    ) as exc:
        _handle_lifecycle_error(exc)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    return {"plan": reviewed}


@router.post("/plans/{plan_id}/carry-forward")
def carry_forward_plan(
    plan_id: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    request: CarryForwardRequest | None = None,
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    try:
        carried = repo.carry_forward_plan_lifecycle(
            client_id,
            plan_id,
            request_id=(request.request_id if request is not None else ""),
        )
    except (
        PlanDrawUnavailableError,
        PlanNotFoundError,
        PlanRequestConflictError,
        PlanTargetAlreadyDrawnError,
    ) as exc:
        _handle_lifecycle_error(exc)
    except ValueError as exc:
        _handle_plan_value_error(exc)
    except sqlite3.Error as exc:
        _handle_sqlite_error(exc)
    return {"plan": carried}
