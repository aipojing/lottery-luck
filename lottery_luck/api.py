from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager, suppress
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import plans, workbench_3d
from .ai_features import DeepSeekFlashProvider, NullAiProvider
from .admin_auth import (
    ADMIN_TOKEN_HEADER,
    AUTH_DETAIL,
    AUTH_SCHEME,
    admin_token_is_valid,
    require_admin,
)
from .analysis import (
    analyze_number_pool,
    backtest_strategy,
    build_analysis_payload,
    build_draw_calendar,
    compare_backtest_strategies,
    filter_candidates,
    normalize_window,
)
from . import auto_update, scheduler
from .crawler import crawl_cwl_games
from .config import PROJECT_ROOT, env_flag, quota_enabled
from .data_health import build_data_health_report, build_public_freshness
from .personal import PersonalInput
from .plan_routes import get_repository, router as plan_router
from .predictor import PredictionEngine
from .repository import LotteryRepository
from .review import review_prediction
from .rules import FRONTEND_GAME_KEYS, GAME_RULES
from .settings import get_settings
from .sports_crawler import crawl_sports_games
from .strategy import (
    backtest_strategy_lab,
    compare_strategy_presets,
    generate_strategy_candidates,
)
from .workbench_routes import router as workbench_router


AUTO_UPDATE_SHUTDOWN_TIMEOUT_SECONDS = 2.0
PRODUCT_EVENT_MAX_CONTENT_LENGTH = 8192
PREDICTION_DATA_UNAVAILABLE = "prediction data unavailable"
USER_DEEPSEEK_API_KEY_HEADER = "X-DeepSeek-Api-Key"
USER_DEEPSEEK_API_KEY_MAX_LENGTH = 512
PRODUCTION_CRON_CWL_GAMES = ["ssq", "3d", "kl8"]
PRODUCTION_CRON_SPORTS_GAMES = ["dlt", "pl3"]
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        repo = LotteryRepository()
        repo.initialize_product_events_schema()
        repo.initialize_plan_schema()
    except Exception:
        LOGGER.exception("startup schema initialization failed")
        raise

    config = auto_update.config_from_env()
    stop_event: asyncio.Event | None = None
    task: asyncio.Task[None] | None = None
    if config.enabled:
        stop_event = asyncio.Event()
        task = asyncio.create_task(auto_update.update_loop(config, stop_event))
    try:
        yield
    finally:
        if stop_event is not None and task is not None:
            stop_event.set()
            try:
                await asyncio.wait_for(task, timeout=AUTO_UPDATE_SHUTDOWN_TIMEOUT_SECONDS)
            except TimeoutError:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


app = FastAPI(title="数运合参", lifespan=lifespan)

_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def limit_product_event_payload_size(request: Request, call_next):
    if request.url.path == "/api/events" and request.method == "POST":
        chunks: list[bytes] = []
        total_size = 0
        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > PRODUCT_EVENT_MAX_CONTENT_LENGTH:
                return JSONResponse(
                    {"detail": "product event payload too large"},
                    status_code=413,
                )
            chunks.append(chunk)
        body = b"".join(chunks)
        replayed = False

        async def replay_body():
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        request._body = body
        request._receive = replay_body
    return await call_next(request)


@app.middleware("http")
async def require_admin_for_api_prefix(request: Request, call_next):
    if request.url.path.startswith("/api/admin/") and not admin_token_is_valid(
        request.headers.get(ADMIN_TOKEN_HEADER)
    ):
        return JSONResponse(
            {"detail": AUTH_DETAIL},
            status_code=401,
            headers={"WWW-Authenticate": AUTH_SCHEME},
        )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def product_events_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    if request.url.path == "/api/events":
        return JSONResponse({"detail": "invalid product event"}, status_code=422)
    return await request_validation_exception_handler(request, exc)


class PredictRequest(BaseModel):
    game_key: Literal["ssq", "3d", "qlc", "kl8", "dlt", "pl3", "pl5"]
    name: str = Field(min_length=1)
    birth_date: date
    calendar_type: Literal["solar", "lunar"] = "solar"
    fortune_mode: Literal["steady", "windfall", "guard"] = "steady"
    birth_hour: str = "unknown"
    birth_place: str = ""
    current_city: str = ""
    consume_quota: bool = False

    @field_validator("name", "birth_hour", "birth_place", "current_city", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("name")
    @classmethod
    def require_non_blank_name(cls, value: str) -> str:
        if not value:
            raise ValueError("name must not be blank")
        return value


class FilterRequest(BaseModel):
    exclude_recent: int = 0
    min_hot: int = 0
    odd_even: str = ""
    sum_min: int | None = None
    sum_max: int | None = None
    max_consecutive_run: int = 99
    ac_min: int | None = None
    ac_max: int | None = None
    prime_composite: str = ""
    mod3: str = ""
    zone: str = ""
    tail_exclude: list[int] = Field(default_factory=list)
    tail_include: list[int] = Field(default_factory=list)
    min_omission: int | None = None
    count: int = 10


class BacktestRequest(BaseModel):
    strategy: str = "hot_omission_balance"
    window: int = 100


class BacktestCompareRequest(BaseModel):
    strategies: list[str] = Field(
        default_factory=lambda: ["hot_omission_balance", "cold_rebound", "hot_focus"]
    )
    window: int = 100


class StrategyRequest(BaseModel):
    preset: str = "balanced"
    candidate_count: int = 5
    window: int = 100
    conditions: dict[str, Any] = Field(default_factory=dict)


class StrategyCompareRequest(BaseModel):
    window: int = 100
    candidate_count: int = 1
    conditions: dict[str, Any] = Field(default_factory=dict)


class PoolNumber(BaseModel):
    main: list[int]
    special: list[int] = []


class NumberPoolRequest(BaseModel):
    numbers: list[PoolNumber]


class SportsCrawlRequest(BaseModel):
    games: list[Literal["dlt", "pl3", "pl5"]] = Field(
        default_factory=lambda: ["dlt", "pl3", "pl5"]
    )
    source: Literal["auto", "direct", "browser", "mirror"] = "auto"
    page_size: int = Field(default=30, ge=1, le=500)
    page_no: int = Field(default=1, ge=1)
    pages: int = Field(default=1, ge=1, le=20)
    timeout_ms: int = Field(default=30000, ge=5000, le=180000)
    browser_headed: bool = False


class CwlCrawlRequest(BaseModel):
    games: list[Literal["ssq", "3d", "qlc", "kl8"]] = Field(
        default_factory=lambda: ["ssq", "3d", "kl8"]
    )
    page_size: int = Field(default=100, ge=1, le=500)


class AdminTaskRunRequest(BaseModel):
    provider: Literal["cwl", "sports"] = "cwl"
    games: list[str] = Field(default_factory=lambda: ["ssq", "3d", "kl8"])
    source: Literal["auto", "direct", "browser", "mirror"] = "auto"
    page_size: int = Field(default=100, ge=1, le=500)
    pages: int = Field(default=1, ge=1, le=20)
    timeout_ms: int = Field(default=30000, ge=5000, le=180000)
    browser_headed: bool = False


class ReviewRequest(BaseModel):
    main: list[int] = Field(default_factory=list)
    special: list[int] = Field(default_factory=list)
    fortune_eye: int | None = None


class MockUnlockRequest(BaseModel):
    kind: Literal["member", "package"] = "package"
    units: int | None = Field(default=None, ge=1, le=99999)


class CloudRecordRequest(BaseModel):
    record: dict[str, Any]


class ProductEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(min_length=1, max_length=64)
    properties: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/health")
def health(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    today: date | None = None,
) -> dict[str, Any]:
    try:
        games_by_key = {
            str(game.get("game_key") or "").strip().lower(): game
            for game in repo.list_games()
        }
        visible_keys = [key for key in FRONTEND_GAME_KEYS if key in games_by_key]
        crawl_logs = repo.recent_crawl_logs_by_game(visible_keys, limit_per_game=20)
    except Exception:
        LOGGER.exception("health check database query failed")
        return {
            "status": "degraded",
            "service": "error",
            "data": {},
            "error": "data repository unavailable",
        }

    logs_by_game: dict[str, list[dict[str, Any]]] = {}
    for log in crawl_logs:
        key = str(log.get("game_key") or "").strip().lower()
        logs_by_game.setdefault(key, []).append(log)

    data = {
        key: build_public_freshness(
            games_by_key[key],
            today=today,
            logs=logs_by_game.get(key, []),
        )
        for key in FRONTEND_GAME_KEYS
        if key in games_by_key
    }
    degraded = any(
        freshness["status"] in {"stale", "empty"} for freshness in data.values()
    )
    return {
        "status": "degraded" if degraded else "ok",
        "service": "ok",
        "data": data,
    }


def get_ai_provider(
    x_deepseek_api_key: Annotated[
        str | None,
        Header(alias=USER_DEEPSEEK_API_KEY_HEADER),
    ] = None,
) -> NullAiProvider | DeepSeekFlashProvider:
    if not env_flag("LOTTERY_LUCK_AI_ENABLED", True):
        return NullAiProvider("DeepSeek 已被配置开关关闭，使用中性特征。")
    api_key = (x_deepseek_api_key or "").strip()
    if len(api_key) > USER_DEEPSEEK_API_KEY_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="invalid DeepSeek API key")
    if api_key:
        return DeepSeekFlashProvider(api_key=api_key)
    return NullAiProvider("请在 AI 设置中配置 DeepSeek API Key，当前使用中性特征。")


def _frontend_number_rule(game_key: str) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    special_range = rule.special_range
    return {
        "main_count": rule.main_count,
        "main_min": rule.main_range.start,
        "main_max": rule.main_range.stop - 1,
        "special_count": rule.special_count,
        "special_min": special_range.start if special_range else None,
        "special_max": special_range.stop - 1 if special_range else None,
        "allow_repeat": rule.allow_repeat,
        "special_distinct_from_main": bool(
            special_range == rule.main_range
            and rule.special_count
            and not rule.allow_repeat
        ),
    }


def _frontend_game_payload(game: dict[str, Any], game_key: str) -> dict[str, Any]:
    return {
        **game,
        "number_rule": _frontend_number_rule(game_key),
    }


@app.get("/api/games")
def list_games(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, list[dict[str, Any]]]:
    games_by_key = {game["game_key"]: game for game in repo.list_games()}
    return {
        "games": [
            _frontend_game_payload(games_by_key[key], key)
            for key in FRONTEND_GAME_KEYS
            if key in games_by_key
        ]
    }


def _admin_health_payload(
    repo: LotteryRepository,
    today: str | None = None,
) -> dict[str, Any]:
    visible_games = [
        game
        for game in repo.list_games()
        if str(game.get("game_key") or "").strip().lower() in FRONTEND_GAME_KEYS
    ]
    return build_data_health_report(
        visible_games,
        repo.recent_draw_dates_by_game(limit_per_game=500),
        repo.recent_crawl_logs(limit=20),
        today=today,
    )


@app.get("/api/admin/data-health", dependencies=[Depends(require_admin)])
def admin_data_health(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    today: str | None = None,
) -> dict[str, Any]:
    return _admin_health_payload(repo, today=today)


@app.get("/api/admin/settings", dependencies=[Depends(require_admin)])
def admin_settings() -> dict[str, Any]:
    return get_settings()


def _client_id(value: str | None) -> str:
    return str(value or "").strip()[:96]


def require_commercial_routes() -> None:
    if not quota_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


def _unlock_payload(quota: dict[str, Any]) -> dict[str, Any]:
    return {
        "quota_exhausted": True,
        "quota": quota,
        "unlock": {
            "title": "解锁今日财运号",
            "message": "本次额度已用完，可开通会员或购买次数包继续起盘。",
            "benefits": ["继续起盘", "云端保存", "开奖后复盘", "多设备同步"],
        },
        "disclaimer": "仅供娱乐与数据分析参考，不构成投注建议。",
    }


def _prediction_data_unavailable(exc: Exception) -> HTTPException:
    LOGGER.exception("3d prediction metadata unavailable")
    return HTTPException(status_code=503, detail=PREDICTION_DATA_UNAVAILABLE)


def _augment_3d_prediction_payload(
    payload: dict[str, Any],
    repo: LotteryRepository,
) -> dict[str, Any]:
    try:
        games_by_key = {
            str(game.get("game_key") or "").strip().lower(): game
            for game in repo.list_games()
        }
        game = games_by_key.get("3d")
        logs = repo.recent_crawl_logs_by_game(["3d"], limit_per_game=20)
    except Exception as exc:
        raise _prediction_data_unavailable(exc) from exc

    if not game:
        raise HTTPException(status_code=503, detail=PREDICTION_DATA_UNAVAILABLE)

    try:
        target = plans.resolve_3d_target(
            str(game.get("latest_issue") or ""),
            str(game.get("latest_date") or ""),
            str(payload.get("best_draw_date") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=PREDICTION_DATA_UNAVAILABLE) from exc

    payload["target_issue"] = target["target_issue"]
    payload["target_draw_date"] = target["target_draw_date"]
    payload["data_freshness"] = build_public_freshness(game, logs=logs)
    payload["number_metrics"] = workbench_3d.number_attributes(
        payload["numbers"]["main"],
    )
    return payload


@app.get(
    "/api/quota/status",
    include_in_schema=False,
    dependencies=[Depends(require_commercial_routes)],
)
def quota_status(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
    today: str | None = None,
) -> dict[str, Any]:
    return repo.quota_status(_client_id(x_lottery_client_id), today=today)


@app.post(
    "/api/quota/mock-unlock",
    include_in_schema=False,
    dependencies=[Depends(require_commercial_routes)],
)
def quota_mock_unlock(
    request: MockUnlockRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Lottery-Client-Id is required")
    try:
        return repo.mock_unlock_quota(client_id, kind=request.kind, units=request.units)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/cloud/fortune-records",
    include_in_schema=False,
    dependencies=[Depends(require_commercial_routes)],
)
def cloud_record_save(
    request: CloudRecordRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Lottery-Client-Id is required")
    try:
        return {"record": repo.save_cloud_record(client_id, request.record)}
    except PermissionError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/api/cloud/fortune-records",
    include_in_schema=False,
    dependencies=[Depends(require_commercial_routes)],
)
def cloud_record_list(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    return {"records": repo.cloud_records(_client_id(x_lottery_client_id))}


@app.post("/api/events", status_code=202)
def product_event_create(
    request: ProductEventRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, bool]:
    client_id = _client_id(x_lottery_client_id)
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Lottery-Client-Id is required")
    try:
        repo.record_product_event(
            client_id=client_id,
            event_name=request.event_name,
            properties=request.properties,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid product event") from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="product event unavailable") from exc
    return {"accepted": True}


@app.get("/api/admin/tasks", dependencies=[Depends(require_admin)])
def admin_tasks(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    return {"tasks": repo.recent_tasks(limit=20)}


@app.post("/api/admin/tasks/run", dependencies=[Depends(require_admin)])
def admin_run_task(
    request: AdminTaskRunRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    games = _task_games(request.provider, request.games)
    try:
        result = scheduler.run_once(
            provider=request.provider,
            games=games,
            source=request.source,
            page_size=request.page_size,
            pages=request.pages,
            timeout_ms=request.timeout_ms,
            browser_headed=request.browser_headed,
            repo=repo,
            cwl_runner=crawl_cwl_games,
            sports_runner=crawl_sports_games,
        )
    except scheduler.CrawlInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finished_task = result["task"]
    return {"task": finished_task, "health": _admin_health_payload(repo)}


@app.post("/api/admin/crawl/sports", dependencies=[Depends(require_admin)])
def admin_crawl_sports(
    request: SportsCrawlRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    try:
        result = scheduler.run_once(
            provider="sports",
            games=request.games,
            source=request.source,
            page_size=request.page_size,
            page_no=request.page_no,
            pages=request.pages,
            timeout_ms=request.timeout_ms,
            browser_headed=request.browser_headed,
            repo=repo,
            sports_runner=crawl_sports_games,
        )
    except scheduler.CrawlInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"crawl": result["task"]["result"], "health": _admin_health_payload(repo)}


@app.post("/api/admin/crawl/cwl", dependencies=[Depends(require_admin)])
def admin_crawl_cwl(
    request: CwlCrawlRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    try:
        result = scheduler.run_once(
            provider="cwl",
            games=request.games,
            page_size=request.page_size,
            repo=repo,
            cwl_runner=crawl_cwl_games,
        )
    except scheduler.CrawlInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"crawl": result["task"]["result"], "health": _admin_health_payload(repo)}


@app.get("/api/cron/crawl")
def cron_crawl(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, Any]:
    cron_secret = os.getenv("CRON_SECRET", "")
    if not cron_secret or authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="cron authorization required")

    try:
        cwl_result = scheduler.run_once(
            provider="cwl",
            games=PRODUCTION_CRON_CWL_GAMES,
            page_size=100,
            cwl_runner=crawl_cwl_games,
        )
        sports_result = scheduler.run_once(
            provider="sports",
            games=PRODUCTION_CRON_SPORTS_GAMES,
            source="mirror",
            page_size=100,
            page_no=1,
            pages=1,
            timeout_ms=30000,
            browser_headed=False,
            sports_runner=crawl_sports_games,
        )
    except scheduler.CrawlInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"ok": True, "results": [cwl_result["task"], sports_result["task"]]}


@app.post("/api/predict")
def predict(
    request: PredictRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    ai_provider: Annotated[
        NullAiProvider | DeepSeekFlashProvider,
        Depends(get_ai_provider),
    ],
    x_lottery_client_id: Annotated[
        str | None,
        Header(alias="X-Lottery-Client-Id"),
    ] = None,
) -> dict[str, Any]:
    client_id = _client_id(x_lottery_client_id)
    use_quota = quota_enabled()
    quota_result = None
    quota_refunded = False

    def refund_consumed_quota() -> None:
        nonlocal quota_refunded
        if quota_refunded or not quota_result or not quota_result.get("allowed"):
            return
        quota_refunded = True
        try:
            repo.refund_prediction_quota(client_id, quota_result)
        except Exception:
            LOGGER.exception("prediction quota refund failed")

    if use_quota and request.consume_quota and client_id:
        quota_result = repo.consume_prediction_quota(
            client_id,
            request.game_key,
            request.fortune_mode,
        )
        if not quota_result.get("allowed"):
            return _unlock_payload(quota_result["quota"])

    personal = PersonalInput(
        name=request.name,
        birth_date=request.birth_date.isoformat(),
        calendar_type=request.calendar_type,
        birth_hour=request.birth_hour,
        birth_place=request.birth_place,
        current_city=request.current_city,
    )
    engine = PredictionEngine(repo, ai_provider)

    try:
        payload = engine.predict(request.game_key, personal, fortune_mode=request.fortune_mode)
        if request.game_key == "3d":
            payload = _augment_3d_prediction_payload(payload, repo)
        if use_quota and quota_result:
            payload["quota"] = quota_result["quota"]
        elif use_quota and client_id:
            payload["quota"] = repo.quota_status(client_id)
        return payload
    except ValueError as exc:
        refund_consumed_quota()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        refund_consumed_quota()
        raise
    except Exception:
        refund_consumed_quota()
        raise
    finally:
        close = getattr(ai_provider, "close", None)
        if callable(close):
            close()


@app.post("/api/review/{game_key}")
def review(
    game_key: str,
    request: ReviewRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return review_prediction(game, repo.recent_draws(game, limit=1), request.model_dump())


@app.get("/api/analysis/{game_key}")
def analysis(
    game_key: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    window: str | None = "30",
) -> dict[str, Any]:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise HTTPException(status_code=404, detail=f"unsupported game_key: {game}")
    normalized_window = normalize_window(window)
    return build_analysis_payload(
        game,
        repo.recent_draws(game, limit=normalized_window),
        normalized_window,
    )


def _require_supported_game(game_key: str) -> str:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise HTTPException(status_code=404, detail=f"unsupported game_key: {game}")
    return game


def _task_games(provider: str, games: list[str]) -> list[str]:
    allowed = {"cwl": {"ssq", "3d", "qlc", "kl8"}, "sports": {"dlt", "pl3", "pl5"}}[provider]
    selected = [str(game).strip().lower() for game in games if str(game).strip().lower() in allowed]
    if selected:
        return selected
    return ["ssq", "3d", "kl8"] if provider == "cwl" else ["dlt", "pl3"]


@app.post("/api/filter/{game_key}")
def filter_numbers(
    game_key: str,
    request: FilterRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return filter_candidates(game, repo.recent_draws(game, limit=120), request.model_dump())


@app.post("/api/backtest/{game_key}")
def backtest(
    game_key: str,
    request: BacktestRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return backtest_strategy(game, repo.recent_draws(game, limit=max(request.window + 160, 220)), request.model_dump())


@app.post("/api/backtest/{game_key}/compare")
def backtest_compare(
    game_key: str,
    request: BacktestCompareRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return compare_backtest_strategies(
        game,
        repo.recent_draws(game, limit=max(request.window + 160, 220)),
        request.model_dump(),
    )


@app.post("/api/strategy/{game_key}/generate")
def strategy_generate(
    game_key: str,
    request: StrategyRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return generate_strategy_candidates(
        game,
        repo.recent_draws(game, limit=120),
        request.model_dump(),
    )


@app.post("/api/strategy/{game_key}/backtest")
def strategy_backtest(
    game_key: str,
    request: StrategyRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return backtest_strategy_lab(
        game,
        repo.recent_draws(game, limit=max(request.window + 160, 220)),
        request.model_dump(),
    )


@app.post("/api/strategy/{game_key}/compare")
def strategy_compare(
    game_key: str,
    request: StrategyCompareRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return compare_strategy_presets(
        game,
        repo.recent_draws(game, limit=max(request.window + 160, 220)),
        request.model_dump(),
    )


@app.post("/api/number-pool/{game_key}/analyze")
def number_pool(
    game_key: str,
    request: NumberPoolRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    game = _require_supported_game(game_key)
    return analyze_number_pool(
        game,
        repo.recent_draws(game, limit=120),
        [number.model_dump() for number in request.numbers],
    )


@app.get("/api/calendar")
def calendar(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    today: str | None = None,
) -> dict[str, Any]:
    games_by_key = {game["game_key"]: game for game in repo.list_games()}
    return build_draw_calendar(
        [games_by_key[key] for key in FRONTEND_GAME_KEYS if key in games_by_key],
        today=today,
    )


app.include_router(plan_router)
app.include_router(workbench_router)
if env_flag("LOTTERY_LUCK_SERVE_STATIC", True):
    app.mount("/", StaticFiles(directory=PROJECT_ROOT / "web", html=True), name="web")
