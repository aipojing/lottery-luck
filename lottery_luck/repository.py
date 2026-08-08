import sqlite3
from pathlib import Path
from typing import Any, Callable

from .database import connect_database
from . import plans as plan_store
from .data_health import (
    recent_crawl_logs as read_recent_crawl_logs,
    recent_crawl_logs_by_game as read_recent_crawl_logs_by_game,
)
from .product_events import ensure_product_events_table, record_event
from .quota import (
    cloud_records,
    consume_prediction_quota,
    mock_unlock_quota,
    quota_status,
    refund_prediction_quota,
    save_cloud_record,
)
from .rules import GAME_RULES
from .tasks import create_task, list_tasks, mark_task_finished, mark_task_started


DRAW_COLUMNS = "game_key, game_name, issue, draw_date, week, red_numbers, blue_number, sales, pool_money, content"


class PlanLifecycleError(Exception):
    pass


class PlanNotFoundError(PlanLifecycleError):
    pass


class PlanDrawUnavailableError(PlanLifecycleError):
    pass


class PlanTargetAlreadyDrawnError(PlanLifecycleError):
    pass


class PlanRequestConflictError(PlanLifecycleError):
    pass


class LotteryRepository:
    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        connection_factory: Callable[[], Any] | None = None,
    ):
        self.db_path = Path(db_path) if db_path is not None else None
        self.connection_factory = connection_factory

    def _connect(self) -> Any:
        if self.connection_factory is not None:
            return self.connection_factory()
        return connect_database(self.db_path)

    def list_games(self) -> list[dict[str, Any]]:
        sql = """
        SELECT game_key,
               MAX(game_name) AS game_name,
               COUNT(*) AS draw_count,
               MIN(draw_date) AS earliest_date,
               MAX(draw_date) AS latest_date,
               (SELECT issue FROM draws d2
                WHERE d2.game_key = draws.game_key
                ORDER BY draw_date DESC, issue DESC LIMIT 1) AS latest_issue
        FROM draws
        GROUP BY game_key
        ORDER BY game_key
        """
        with self._connect() as connection:
            rows_by_key = {
                str(row["game_key"]): dict(row)
                for row in connection.execute(sql)
            }

        games = []
        for key, rule in GAME_RULES.items():
            row = rows_by_key.get(key, {})
            games.append(
                {
                    "game_key": key,
                    "game_name": row.get("game_name") or rule.name,
                    "draw_count": int(row.get("draw_count") or 0),
                    "earliest_date": row.get("earliest_date") or "",
                    "latest_date": row.get("latest_date") or "",
                    "latest_issue": row.get("latest_issue") or "",
                    "provider": rule.provider,
                }
            )
        return games

    def recent_draws(self, game_key: str, limit: int = 100) -> list[dict[str, Any]]:
        sql = f"""
        SELECT {DRAW_COLUMNS}
        FROM draws
        WHERE game_key = ?
        ORDER BY draw_date DESC, issue DESC
        LIMIT ?
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, (game_key, limit))]

    def draw_by_issue(self, game_key: str, issue: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return _draw_by_issue(connection, game_key, issue)

    def all_draws(self, game_key: str) -> list[dict[str, Any]]:
        sql = f"""
        SELECT {DRAW_COLUMNS}
        FROM draws
        WHERE game_key = ?
        ORDER BY draw_date DESC, issue DESC
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, (game_key,))]

    def recent_draw_dates_by_game(self, limit_per_game: int = 400) -> dict[str, list[str]]:
        sql = """
        SELECT game_key, draw_date
        FROM draws
        WHERE draw_date IS NOT NULL AND draw_date != ''
        ORDER BY game_key, draw_date DESC, issue DESC
        """
        result: dict[str, list[str]] = {}
        seen: dict[str, set[str]] = {}
        with self._connect() as connection:
            for row in connection.execute(sql):
                key = str(row["game_key"])
                draw_date = str(row["draw_date"])
                result.setdefault(key, [])
                seen.setdefault(key, set())
                if draw_date in seen[key] or len(result[key]) >= limit_per_game:
                    continue
                result[key].append(draw_date)
                seen[key].add(draw_date)
        return result

    def recent_crawl_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return read_recent_crawl_logs(connection, limit=limit)

    def recent_crawl_logs_by_game(
        self,
        game_keys: list[str],
        limit_per_game: int = 20,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return read_recent_crawl_logs_by_game(
                connection,
                game_keys,
                limit_per_game=limit_per_game,
            )

    def recent_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return list_tasks(connection, limit=limit)

    def create_task(
        self,
        *,
        kind: str,
        provider: str,
        game_keys: list[str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return create_task(
                connection,
                kind=kind,
                provider=provider,
                game_keys=game_keys,
                payload=payload,
            )

    def start_task(self, task_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            return mark_task_started(connection, task_id)

    def finish_task(
        self,
        task_id: int,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return mark_task_finished(
                connection,
                task_id,
                status=status,
                result=result,
                error=error,
            )

    def quota_status(self, client_id: str, today: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            return quota_status(connection, client_id, today=today)

    def consume_prediction_quota(
        self,
        client_id: str,
        game_key: str,
        mode_key: str,
        today: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return consume_prediction_quota(
                connection,
                client_id,
                game_key,
                mode_key,
                today=today,
            )

    def refund_prediction_quota(
        self,
        client_id: str,
        consume_result: dict[str, Any],
        today: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return refund_prediction_quota(
                connection,
                client_id,
                consume_result,
                today=today,
            )

    def mock_unlock_quota(
        self,
        client_id: str,
        *,
        kind: str,
        units: int | None = None,
        today: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return mock_unlock_quota(
                connection,
                client_id,
                kind=kind,
                units=units,
                today=today,
            )

    def save_cloud_record(self, client_id: str, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            return save_cloud_record(connection, client_id, record)

    def cloud_records(self, client_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return cloud_records(connection, client_id, limit=limit)

    def initialize_product_events_schema(self) -> None:
        with self._connect() as connection:
            ensure_product_events_table(connection)

    def initialize_plan_schema(self) -> None:
        with self._connect() as connection:
            plan_store.initialize_plan_schema(connection)

    def create_plan(self, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            return plan_store.create_plan(connection, client_id, payload)

    def create_plan_lifecycle(
        self,
        client_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                normalized = plan_store.normalize_create_payload(payload)
                if normalized["request_id"]:
                    existing = plan_store.get_plan_by_request_id(
                        connection,
                        client_id,
                        normalized["request_id"],
                    )
                    if existing is not None:
                        if not plan_store.create_payload_matches_plan(
                            existing,
                            normalized,
                        ):
                            raise PlanRequestConflictError
                        connection.commit()
                        return existing
                if _draw_by_issue(connection, "3d", normalized["target_issue"]) is not None:
                    raise PlanTargetAlreadyDrawnError
                plan = plan_store.create_plan_from_normalized_in_transaction(
                    connection,
                    client_id,
                    normalized,
                    enforce_request_match=True,
                )
                connection.commit()
                return plan
            except ValueError as exc:
                if str(exc) == plan_store.REQUEST_ID_CONFLICT_MESSAGE:
                    raise PlanRequestConflictError from exc
                raise
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def list_plans(self, client_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return plan_store.list_plans(connection, client_id, limit=limit)

    def active_plan_summary(
        self,
        client_id: str,
        *,
        game_key: str | None = "3d",
        target_issue: str | None = None,
    ) -> dict[str, Any]:
        normalized_client_id = str(client_id or "").strip()[:96]
        normalized_game_key = str(game_key or "").strip().lower()[:32]
        normalized_target_issue = str(target_issue or "").strip()[:32]
        if not normalized_client_id or not normalized_game_key or not normalized_target_issue:
            return {"count": 0, "latest_plan": None}
        active_statuses = ("draft", "saved", "pending_review")
        with self._connect() as connection:
            count_row = connection.execute(
                """
                SELECT COUNT(*) AS active_count
                FROM lottery_plans
                WHERE client_id = ?
                  AND game_key = ?
                  AND target_issue = ?
                  AND status IN (?, ?, ?)
                """,
                (normalized_client_id, normalized_game_key, normalized_target_issue, *active_statuses),
            ).fetchone()
            latest_row = connection.execute(
                """
                SELECT *
                FROM lottery_plans
                WHERE client_id = ?
                  AND game_key = ?
                  AND target_issue = ?
                  AND status IN (?, ?, ?)
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (normalized_client_id, normalized_game_key, normalized_target_issue, *active_statuses),
            ).fetchone()
            latest_plan = (
                plan_store._hydrate_plan(  # type: ignore[attr-defined]
                    connection,
                    dict(latest_row),
                    duplicate_warning=False,
                )
                if latest_row is not None
                else None
            )
            return {
                "count": int(count_row["active_count"] if count_row else 0),
                "latest_plan": latest_plan,
            }

    def get_plan_by_request_id(
        self,
        client_id: str,
        request_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            return plan_store.get_plan_by_request_id(connection, client_id, request_id)

    def get_plan(self, client_id: str, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return plan_store.get_plan(connection, client_id, plan_id)

    def update_plan(
        self,
        client_id: str,
        plan_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            return plan_store.update_plan(connection, client_id, plan_id, updates)

    def delete_plan(self, client_id: str, plan_id: str) -> bool:
        with self._connect() as connection:
            return plan_store.delete_plan(connection, client_id, plan_id)

    def review_plan(
        self,
        client_id: str,
        plan_id: str,
        draw: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            return plan_store.review_plan(connection, client_id, plan_id, draw)

    def review_plan_lifecycle(
        self,
        client_id: str,
        plan_id: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                plan = plan_store.get_plan(connection, client_id, plan_id)
                if plan is None:
                    raise PlanNotFoundError
                draw = _draw_by_issue(connection, "3d", plan["target_issue"])
                if draw is None:
                    plan_store.clear_plan_review_in_transaction(connection, plan["id"])
                    updated = plan_store.update_plan_in_transaction(
                        connection,
                        client_id,
                        plan_id,
                        {"status": "pending_review"},
                    )
                    if updated is None:
                        raise PlanNotFoundError
                    connection.commit()
                    raise PlanDrawUnavailableError
                reviewed = plan_store.review_plan_in_transaction(
                    connection,
                    client_id,
                    plan_id,
                    draw,
                )
                if reviewed is None:
                    raise PlanNotFoundError
                connection.commit()
                return reviewed
            except (PlanDrawUnavailableError, PlanNotFoundError):
                if connection.in_transaction:
                    connection.rollback()
                raise
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def carry_forward_plan(
        self,
        client_id: str,
        plan_id: str,
        latest_draw: dict[str, Any],
        *,
        target_draw_date: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            return plan_store.carry_forward_plan(
                connection,
                client_id,
                plan_id,
                latest_draw,
                target_draw_date=target_draw_date,
                request_id=request_id,
            )

    def carry_forward_plan_lifecycle(
        self,
        client_id: str,
        plan_id: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                source = plan_store.get_plan(connection, client_id, plan_id)
                if source is None:
                    raise PlanNotFoundError
                if _draw_by_issue(connection, "3d", source["target_issue"]) is None:
                    raise PlanDrawUnavailableError
                latest_draw = _latest_draw(connection, "3d")
                if latest_draw is None:
                    raise PlanDrawUnavailableError
                payload = plan_store.build_carry_forward_payload(
                    source,
                    latest_draw,
                    request_id=request_id,
                )
                normalized = plan_store.normalize_create_payload(payload)
                if normalized["request_id"]:
                    existing = plan_store.get_plan_by_request_id(
                        connection,
                        client_id,
                        normalized["request_id"],
                    )
                    if existing is not None:
                        if not plan_store.create_payload_matches_plan(
                            existing,
                            normalized,
                        ):
                            raise PlanRequestConflictError
                        connection.commit()
                        return existing
                if _draw_by_issue(connection, "3d", normalized["target_issue"]) is not None:
                    raise PlanTargetAlreadyDrawnError
                carried = plan_store.create_plan_from_normalized_in_transaction(
                    connection,
                    client_id,
                    normalized,
                    enforce_request_match=True,
                )
                connection.commit()
                return carried
            except ValueError as exc:
                if str(exc) == plan_store.REQUEST_ID_CONFLICT_MESSAGE:
                    raise PlanRequestConflictError from exc
                raise
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def record_product_event(
        self,
        *,
        client_id: str,
        event_name: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as connection:
            return record_event(
                connection,
                client_id=client_id,
                event_name=event_name,
                properties=properties,
            )


def _draw_by_issue(
    connection: sqlite3.Connection,
    game_key: str,
    issue: str,
) -> dict[str, Any] | None:
    sql = f"""
    SELECT {DRAW_COLUMNS}
    FROM draws
    WHERE game_key = ? AND issue = ?
    LIMIT 1
    """
    row = connection.execute(sql, (game_key, issue)).fetchone()
    return None if row is None else dict(row)


def _latest_draw(
    connection: sqlite3.Connection,
    game_key: str,
) -> dict[str, Any] | None:
    sql = f"""
    SELECT {DRAW_COLUMNS}
    FROM draws
    WHERE game_key = ?
    ORDER BY draw_date DESC, issue DESC
    LIMIT 1
    """
    row = connection.execute(sql, (game_key,)).fetchone()
    return None if row is None else dict(row)
