from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any


CREATE_LOTTERY_PLANS_SQL = """
CREATE TABLE IF NOT EXISTS lottery_plans (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  game_key TEXT NOT NULL CHECK (game_key = '3d'),
  target_issue TEXT NOT NULL,
  target_draw_date TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN ('fortune', 'manual', 'filter', 'random', 'carried')),
  request_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'saved'
    CHECK (status IN ('draft', 'saved', 'pending_review', 'reviewed', 'expired')),
  carried_from_plan_id TEXT REFERENCES lottery_plans(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""

CREATE_LOTTERY_PLAN_ENTRIES_SQL = """
CREATE TABLE IF NOT EXISTS lottery_plan_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL REFERENCES lottery_plans(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  main_numbers TEXT NOT NULL,
  special_numbers TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 120),
  created_at TEXT NOT NULL,
  CONSTRAINT ck_lottery_plan_entries_special_numbers_empty
    CHECK (special_numbers = '[]'),
  UNIQUE(plan_id, position)
)
"""

CREATE_PLAN_CONDITION_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS plan_condition_snapshots (
  plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK (mode IN ('simple', 'pro')),
  analysis_window INTEGER NOT NULL CHECK (analysis_window IN (30, 60, 120)),
  conditions_json TEXT NOT NULL DEFAULT '{}',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  latest_data_issue TEXT NOT NULL DEFAULT '',
  latest_data_date TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
)
"""

CREATE_PLAN_REVIEWS_SQL = """
CREATE TABLE IF NOT EXISTS plan_reviews (
  plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
  draw_issue TEXT NOT NULL,
  draw_numbers TEXT NOT NULL,
  review_status TEXT NOT NULL,
  direct_hit INTEGER NOT NULL CHECK (direct_hit IN (0, 1)),
  group_type TEXT NOT NULL,
  matched_positions TEXT NOT NULL DEFAULT '[]',
  matched_conditions TEXT NOT NULL DEFAULT '[]',
  missed_conditions TEXT NOT NULL DEFAULT '[]',
  result_json TEXT NOT NULL DEFAULT '{}',
  reviewed_at TEXT NOT NULL
)
"""

CREATE_REQUEST_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_lottery_plans_client_request_id
ON lottery_plans (client_id, request_id)
WHERE request_id != ''
"""

CREATE_LIST_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_lottery_plans_client_updated_id
ON lottery_plans (client_id, updated_at DESC, id DESC)
"""

CREATE_CARRIED_SCOPE_INSERT_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_lottery_plans_carried_same_client_insert
BEFORE INSERT ON lottery_plans
FOR EACH ROW
WHEN NEW.carried_from_plan_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM lottery_plans
    WHERE id = NEW.carried_from_plan_id
      AND client_id = NEW.client_id
  )
BEGIN
  SELECT RAISE(ABORT, 'invalid plan');
END
"""

CREATE_CARRIED_SCOPE_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_lottery_plans_carried_same_client_update
BEFORE UPDATE OF client_id, carried_from_plan_id ON lottery_plans
FOR EACH ROW
WHEN NEW.carried_from_plan_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM lottery_plans
    WHERE id = NEW.carried_from_plan_id
      AND client_id = NEW.client_id
  )
BEGIN
  SELECT RAISE(ABORT, 'invalid plan');
END
"""

DROP_REQUEST_INDEX_SQL = "DROP INDEX IF EXISTS ux_lottery_plans_client_request_id"
DROP_LIST_INDEX_SQL = "DROP INDEX IF EXISTS idx_lottery_plans_client_updated_id"
DROP_CARRIED_SCOPE_INSERT_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS trg_lottery_plans_carried_same_client_insert"
)
DROP_CARRIED_SCOPE_UPDATE_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS trg_lottery_plans_carried_same_client_update"
)

ALLOWED_SOURCE_TYPES = {"fortune", "manual", "filter", "random", "carried"}
ALLOWED_STATUSES = {"draft", "saved", "pending_review", "reviewed", "expired"}
UPDATE_STATUSES = {"draft", "saved", "pending_review", "expired"}
ALLOWED_UPDATE_KEYS = {"title", "status", "entries", "condition_snapshot"}
ALLOWED_MODES = {"simple", "pro"}
ALLOWED_WINDOWS = {30, 60, 120}
PLAN_TABLES = (
    "lottery_plans",
    "lottery_plan_entries",
    "plan_condition_snapshots",
    "plan_reviews",
)
PLAN_TABLES_CHILD_FIRST = (
    "plan_reviews",
    "plan_condition_snapshots",
    "lottery_plan_entries",
    "lottery_plans",
)
MAX_CLIENT_ID_LENGTH = 96
MAX_TITLE_LENGTH = 80
MAX_NOTE_LENGTH = 120
MAX_ENTRY_COUNT = 50
MAX_JSON_BYTES = 32 * 1024
MAX_JSON_DEPTH = 8
INVALID_PLAN_MESSAGE = "invalid plan"
INVALID_REVIEW_MESSAGE = "invalid review"
INVALID_TARGET_MESSAGE = "invalid target"
REQUEST_ID_CONFLICT_MESSAGE = "request id conflicts with an existing plan"
_SCHEMA_LOCK = threading.Lock()
_TIMESTAMP_LOCK = threading.Lock()
_LAST_TIMESTAMP: datetime | None = None


def initialize_plan_schema(connection: sqlite3.Connection) -> None:
    if _plan_schema_is_current(connection):
        return
    with _SCHEMA_LOCK:
        if _plan_schema_is_current(connection):
            return
        _migrate_plan_schema(connection)


def create_plan(
    connection: sqlite3.Connection,
    client_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalized_client_id = _normalize_client_id(client_id, required=True)
    normalized = _normalize_create_payload(payload)

    with connection:
        return _create_plan_normalized(
            connection,
            normalized_client_id,
            normalized,
            enforce_request_match=False,
        )


def normalize_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _normalize_create_payload(payload)


def create_plan_in_transaction(
    connection: sqlite3.Connection,
    client_id: str,
    payload: dict[str, Any],
    *,
    enforce_request_match: bool = False,
) -> dict[str, Any]:
    normalized_client_id = _normalize_client_id(client_id, required=True)
    normalized = _normalize_create_payload(payload)
    return _create_plan_normalized(
        connection,
        normalized_client_id,
        normalized,
        enforce_request_match=enforce_request_match,
    )


def create_plan_from_normalized_in_transaction(
    connection: sqlite3.Connection,
    client_id: str,
    normalized: dict[str, Any],
    *,
    enforce_request_match: bool = False,
) -> dict[str, Any]:
    normalized_client_id = _normalize_client_id(client_id, required=True)
    return _create_plan_normalized(
        connection,
        normalized_client_id,
        normalized,
        enforce_request_match=enforce_request_match,
    )


def _create_plan_normalized(
    connection: sqlite3.Connection,
    normalized_client_id: str,
    normalized: dict[str, Any],
    *,
    enforce_request_match: bool,
) -> dict[str, Any]:
    if normalized["request_id"]:
        existing = _get_plan_by_request_id(
            connection,
            normalized_client_id,
            normalized["request_id"],
        )
        if existing is not None:
            if enforce_request_match and not create_payload_matches_plan(
                existing,
                normalized,
            ):
                raise ValueError(REQUEST_ID_CONFLICT_MESSAGE)
            return existing

    _validate_carried_from_plan(
        connection,
        normalized_client_id,
        normalized["carried_from_plan_id"],
    )
    duplicate_warning = _has_duplicate_entries(
        connection,
        client_id=normalized_client_id,
        target_issue=normalized["target_issue"],
        target_draw_date=normalized["target_draw_date"],
        source_type=normalized["source_type"],
        entries=normalized["entries"],
    )

    plan_id = _new_plan_id()
    now = _utc_now_iso()
    try:
        connection.execute(
            """
            INSERT INTO lottery_plans (
                id, client_id, game_key, target_issue, target_draw_date,
                source_type, request_id, title, status, carried_from_plan_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                normalized_client_id,
                "3d",
                normalized["target_issue"],
                normalized["target_draw_date"],
                normalized["source_type"],
                normalized["request_id"],
                normalized["title"],
                "saved",
                normalized["carried_from_plan_id"],
                now,
                now,
            ),
        )
        _replace_entries(connection, plan_id, normalized["entries"], now)
        _replace_snapshot(
            connection,
            plan_id,
            normalized.get("condition_snapshot"),
            now,
        )
    except sqlite3.IntegrityError:
        if normalized["request_id"]:
            existing = _get_plan_by_request_id(
                connection,
                normalized_client_id,
                normalized["request_id"],
            )
            if existing is not None:
                if enforce_request_match and not create_payload_matches_plan(
                    existing,
                    normalized,
                ):
                    raise ValueError(REQUEST_ID_CONFLICT_MESSAGE) from None
                return existing
        raise ValueError(INVALID_PLAN_MESSAGE) from None

    created = get_plan(connection, normalized_client_id, plan_id)
    if created is None:
        raise ValueError(INVALID_PLAN_MESSAGE)
    created["duplicate_warning"] = duplicate_warning
    return created


def list_plans(
    connection: sqlite3.Connection,
    client_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    normalized_client_id = _normalize_client_id(client_id)
    if not normalized_client_id:
        return []
    safe_limit = max(1, min(100, _safe_int(limit, 50)))
    rows = connection.execute(
        """
        SELECT *
        FROM lottery_plans
        WHERE client_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (normalized_client_id, safe_limit),
    ).fetchall()
    return [
        _hydrate_plan(connection, dict(row), duplicate_warning=False)
        for row in rows
    ]


def get_plan_by_request_id(
    connection: sqlite3.Connection,
    client_id: str,
    request_id: str,
) -> dict[str, Any] | None:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_request_id = _normalize_text(request_id)
    if not normalized_client_id or not normalized_request_id:
        return None
    return _get_plan_by_request_id(
        connection,
        normalized_client_id,
        normalized_request_id,
    )


def create_payload_matches_plan(
    plan: dict[str, Any],
    normalized: dict[str, Any],
) -> bool:
    if not isinstance(plan, dict) or not isinstance(normalized, dict):
        return False
    scalar_keys = (
        "game_key",
        "target_issue",
        "target_draw_date",
        "source_type",
        "request_id",
        "title",
        "carried_from_plan_id",
    )
    expected_scalars = {
        **{key: normalized.get(key) for key in scalar_keys},
        "game_key": "3d",
    }
    actual_scalars = {key: plan.get(key) for key in scalar_keys}
    if actual_scalars != expected_scalars:
        return False
    return (
        _entries_match_payload(plan.get("entries"), normalized.get("entries"))
        and _snapshot_matches_payload(
            plan.get("condition_snapshot"),
            normalized.get("condition_snapshot"),
        )
    )


def _entries_match_payload(
    entries: Any,
    normalized_entries: Any,
) -> bool:
    if not isinstance(entries, list) or not isinstance(normalized_entries, list):
        return False
    def signature(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "position": item.get("position"),
                    "main_numbers": list(item.get("main_numbers") or []),
                    "special_numbers": list(item.get("special_numbers") or []),
                    "note": item.get("note") or "",
                }
                for item in value
            ],
            key=lambda item: item["position"],
        )

    return signature(entries) == signature(normalized_entries)


def _snapshot_matches_payload(
    snapshot: Any,
    normalized_snapshot: Any,
) -> bool:
    if snapshot is None or normalized_snapshot is None:
        return snapshot is None and normalized_snapshot is None
    if not isinstance(snapshot, dict) or not isinstance(normalized_snapshot, dict):
        return False
    keys = (
        "mode",
        "analysis_window",
        "conditions_json",
        "metrics_json",
        "latest_data_issue",
        "latest_data_date",
    )
    return {key: snapshot.get(key) for key in keys} == {
        key: normalized_snapshot.get(key) for key in keys
    }


def get_plan(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
) -> dict[str, Any] | None:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_plan_id = _normalize_text(plan_id)
    if not normalized_client_id or not normalized_plan_id:
        return None
    row = connection.execute(
        """
        SELECT *
        FROM lottery_plans
        WHERE id = ? AND client_id = ?
        """,
        (normalized_plan_id, normalized_client_id),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_plan(connection, dict(row), duplicate_warning=False)


def update_plan(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    with connection:
        return update_plan_in_transaction(connection, client_id, plan_id, updates)


def update_plan_in_transaction(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(updates, dict):
        raise ValueError(INVALID_PLAN_MESSAGE)
    if set(updates) - ALLOWED_UPDATE_KEYS:
        raise ValueError(INVALID_PLAN_MESSAGE)
    normalized_client_id = _normalize_client_id(client_id)
    normalized_plan_id = _normalize_text(plan_id)
    if not normalized_client_id or not normalized_plan_id:
        return None

    existing = _get_plan_row(connection, normalized_client_id, normalized_plan_id)
    if existing is None:
        return None

    title = None
    status = None
    entries = None
    snapshot = None
    if "title" in updates:
        title = _normalize_title(updates.get("title"))
    if "status" in updates:
        status = _normalize_update_status(updates.get("status"))
    if "entries" in updates:
        entries = _normalize_entries(updates.get("entries"))
    if "condition_snapshot" in updates:
        snapshot = _normalize_snapshot(updates.get("condition_snapshot"))

    now = _utc_now_iso()
    fields = []
    values: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    fields.append("updated_at = ?")
    values.append(now)
    values.extend([normalized_plan_id, normalized_client_id])
    connection.execute(
        f"""
        UPDATE lottery_plans
        SET {", ".join(fields)}
        WHERE id = ? AND client_id = ?
        """,
        values,
    )
    if entries is not None:
        connection.execute(
            "DELETE FROM lottery_plan_entries WHERE plan_id = ?",
            (normalized_plan_id,),
        )
        _replace_entries(connection, normalized_plan_id, entries, now)
    if "condition_snapshot" in updates:
        connection.execute(
            "DELETE FROM plan_condition_snapshots WHERE plan_id = ?",
            (normalized_plan_id,),
        )
        _replace_snapshot(connection, normalized_plan_id, snapshot, now)
    return get_plan(connection, normalized_client_id, normalized_plan_id)


def delete_plan(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
) -> bool:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_plan_id = _normalize_text(plan_id)
    if not normalized_client_id or not normalized_plan_id:
        return False
    with connection:
        cursor = connection.execute(
            """
            DELETE FROM lottery_plans
            WHERE id = ? AND client_id = ?
            """,
            (normalized_plan_id, normalized_client_id),
        )
    return int(cursor.rowcount or 0) > 0


def review_plan(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
    draw: dict[str, Any],
) -> dict[str, Any] | None:
    with connection:
        return review_plan_in_transaction(connection, client_id, plan_id, draw)


def clear_plan_review_in_transaction(
    connection: sqlite3.Connection,
    plan_id: str,
) -> None:
    normalized_plan_id = _normalize_text(plan_id)
    if not normalized_plan_id:
        return
    connection.execute(
        "DELETE FROM plan_reviews WHERE plan_id = ?",
        (normalized_plan_id,),
    )


def review_plan_in_transaction(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
    draw: dict[str, Any],
) -> dict[str, Any] | None:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_plan_id = _normalize_text(plan_id)
    if not normalized_client_id or not normalized_plan_id:
        return None
    if not isinstance(draw, dict):
        raise ValueError(INVALID_REVIEW_MESSAGE)

    plan_row = _get_plan_row(connection, normalized_client_id, normalized_plan_id)
    if plan_row is None:
        return None
    plan = _hydrate_plan(connection, dict(plan_row), duplicate_warning=False)
    actual = _normalize_draw(draw)
    if actual["issue"] != plan["target_issue"]:
        raise ValueError(INVALID_REVIEW_MESSAGE)

    existing_review = _get_review(connection, normalized_plan_id)
    if existing_review is not None:
        if _review_matches(existing_review, actual):
            return get_plan(connection, normalized_client_id, normalized_plan_id)
        raise ValueError(INVALID_REVIEW_MESSAGE)

    result = _build_review_result(plan, actual)
    now = _utc_now_iso()
    try:
        connection.execute(
            """
            INSERT INTO plan_reviews (
                plan_id, draw_issue, draw_numbers, review_status, direct_hit,
                group_type, matched_positions, matched_conditions,
                missed_conditions, result_json, reviewed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_plan_id,
                actual["issue"],
                _dump_json(actual["numbers"]),
                "direct_hit" if result["direct_hit"] else "missed",
                1 if result["direct_hit"] else 0,
                result["group_type"],
                _dump_json(result["matched_positions"]),
                _dump_json(result["matched_conditions"]),
                _dump_json(result["missed_conditions"]),
                _dump_json(result),
                now,
            ),
        )
    except (sqlite3.IntegrityError, sqlite3.OperationalError):
        existing_review = _get_review(connection, normalized_plan_id)
        if existing_review is not None and _review_matches(existing_review, actual):
            return get_plan(connection, normalized_client_id, normalized_plan_id)
        raise ValueError(INVALID_REVIEW_MESSAGE) from None
    connection.execute(
        """
        UPDATE lottery_plans
        SET status = 'reviewed', updated_at = ?
        WHERE id = ? AND client_id = ?
        """,
        (now, normalized_plan_id, normalized_client_id),
    )
    return get_plan(connection, normalized_client_id, normalized_plan_id)


def carry_forward_plan(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
    latest_draw: dict[str, Any],
    *,
    target_draw_date: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    old_plan = get_plan(connection, client_id, plan_id)
    if old_plan is None:
        return None
    payload = build_carry_forward_payload(
        old_plan,
        latest_draw,
        target_draw_date=target_draw_date,
        request_id=request_id,
    )
    return create_plan(connection, client_id, payload)


def build_carry_forward_payload(
    old_plan: dict[str, Any],
    latest_draw: dict[str, Any],
    *,
    target_draw_date: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    draw = _normalize_draw(latest_draw)
    target = resolve_3d_target(
        draw["issue"],
        draw["draw_date"],
        target_draw_date=target_draw_date,
    )
    carry_request_id = (
        _normalize_text(request_id)
        or f"carry:{old_plan['id']}:{draw['issue']}:{draw['draw_date']}:{target['target_issue']}"
    )
    return {
        "game_key": "3d",
        "target_issue": target["target_issue"],
        "target_draw_date": target["target_draw_date"],
        "source_type": "carried",
        "request_id": carry_request_id,
        "title": old_plan["title"],
        "carried_from_plan_id": old_plan["id"],
        "entries": [
            {
                "position": entry["position"],
                "main_numbers": entry["main_numbers"],
                "special_numbers": [],
                "note": entry.get("note") or "",
            }
            for entry in old_plan["entries"]
        ],
        "condition_snapshot": old_plan.get("condition_snapshot"),
    }


def resolve_3d_target(
    latest_issue: str,
    latest_draw_date: str,
    target_draw_date: str | None = None,
) -> dict[str, str]:
    try:
        issue_text = _normalize_text(latest_issue)
        if len(issue_text) < 7:
            raise ValueError
        issue_year = int(issue_text[:4])
        issue_sequence = int(issue_text[4:])
        latest_date = date.fromisoformat(_normalize_text(latest_draw_date))
        target_date = (
            date.fromisoformat(_normalize_text(target_draw_date))
            if target_draw_date is not None
            else latest_date + timedelta(days=1)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(INVALID_TARGET_MESSAGE) from exc

    if target_date <= latest_date:
        raise ValueError(INVALID_TARGET_MESSAGE)

    if target_date.year == issue_year:
        sequence = issue_sequence + (target_date - latest_date).days
    else:
        sequence = (target_date - date(target_date.year, 1, 1)).days + 1
    if sequence <= 0 or sequence > 999:
        raise ValueError(INVALID_TARGET_MESSAGE)
    return {
        "target_issue": f"{target_date.year}{sequence:03d}",
        "target_draw_date": target_date.isoformat(),
    }


def _plan_schema_is_current(connection: sqlite3.Connection) -> bool:
    tables = _sqlite_objects(connection, "table")
    required_tables = {
        "lottery_plans",
        "lottery_plan_entries",
        "plan_condition_snapshots",
        "plan_reviews",
    }
    if not required_tables <= tables:
        return False

    plan_columns = _table_columns(connection, "lottery_plans")
    entry_columns = _table_columns(connection, "lottery_plan_entries")
    snapshot_columns = _table_columns(connection, "plan_condition_snapshots")
    review_columns = _table_columns(connection, "plan_reviews")
    for column in (
        "id",
        "client_id",
        "game_key",
        "target_issue",
        "target_draw_date",
        "source_type",
        "request_id",
        "title",
        "status",
        "carried_from_plan_id",
        "created_at",
        "updated_at",
    ):
        if column not in plan_columns:
            return False
    for column in (
        "plan_id",
        "position",
        "main_numbers",
        "special_numbers",
        "note",
        "created_at",
    ):
        if column not in entry_columns:
            return False
    for column in (
        "plan_id",
        "mode",
        "analysis_window",
        "conditions_json",
        "metrics_json",
        "latest_data_issue",
        "latest_data_date",
        "created_at",
    ):
        if column not in snapshot_columns:
            return False
    if "window" in snapshot_columns:
        return False
    if "direct_hit" not in review_columns:
        return False
    for column in ("client_id", "game_key", "source_type", "request_id", "title", "status"):
        if int(_row_value(plan_columns[column], "notnull", 3)) != 1:
            return False
    if int(_row_value(entry_columns["special_numbers"], "notnull", 3)) != 1:
        return False
    for column in ("mode", "analysis_window", "latest_data_date"):
        if int(_row_value(snapshot_columns[column], "notnull", 3)) != 1:
            return False
    if int(_row_value(review_columns["direct_hit"], "notnull", 3)) != 1:
        return False

    plan_sql = _table_sql(connection, "lottery_plans")
    entry_sql = _table_sql(connection, "lottery_plan_entries")
    snapshot_sql = _table_sql(connection, "plan_condition_snapshots")
    review_sql = _table_sql(connection, "plan_reviews")
    if "source_type TEXT NOT NULL CHECK" not in plan_sql:
        return False
    if "source_type IN ('fortune', 'manual', 'filter', 'random', 'carried')" not in plan_sql:
        return False
    if "game_key TEXT NOT NULL CHECK (game_key = '3d')" not in plan_sql:
        return False
    if "status IN ('draft', 'saved', 'pending_review', 'reviewed', 'expired')" not in plan_sql:
        return False
    if "CHECK (special_numbers = '[]')" not in entry_sql:
        return False
    if "mode TEXT NOT NULL CHECK (mode IN ('simple', 'pro'))" not in snapshot_sql:
        return False
    if "analysis_window INTEGER NOT NULL CHECK (analysis_window IN (30, 60, 120))" not in snapshot_sql:
        return False
    if "direct_hit INTEGER NOT NULL CHECK (direct_hit IN (0, 1))" not in review_sql:
        return False

    if not _child_fk_is_current(connection, "lottery_plan_entries"):
        return False
    if not _child_fk_is_current(connection, "plan_condition_snapshots"):
        return False
    if not _child_fk_is_current(connection, "plan_reviews"):
        return False

    indexes = _sqlite_objects(connection, "index", table="lottery_plans")
    if {
        "ux_lottery_plans_client_request_id",
        "idx_lottery_plans_client_updated_id",
    } - indexes:
        return False
    request_sql = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND name = 'ux_lottery_plans_client_request_id'
        """
    ).fetchone()
    if request_sql is None or "WHERE request_id != ''" not in str(request_sql[0]):
        return False
    if _index_definition(connection, "idx_lottery_plans_client_updated_id") != [
        ("client_id", False),
        ("updated_at", True),
        ("id", True),
    ]:
        return False

    triggers = _sqlite_objects(connection, "trigger", table="lottery_plans")
    return {
        "trg_lottery_plans_carried_same_client_insert",
        "trg_lottery_plans_carried_same_client_update",
    } <= triggers


def _migrate_plan_schema(connection: sqlite3.Connection) -> None:
    foreign_keys_enabled = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing_tables = _sqlite_objects(connection, "table")
            new_tables = _prefixed_plan_tables("__new_")
            old_tables = _prefixed_plan_tables("__old_")
            for temp_table in new_tables.values():
                connection.execute(f"DROP TABLE IF EXISTS {_quote_identifier(temp_table)}")

            _create_plan_schema(connection, new_tables)
            now = _sql_literal(_utc_now_iso())
            if "lottery_plans" in existing_tables:
                _copy_legacy_lottery_plans(
                    connection,
                    "lottery_plans",
                    now,
                    target_table=new_tables["lottery_plans"],
                )
            if "lottery_plan_entries" in existing_tables:
                _copy_legacy_plan_entries(
                    connection,
                    "lottery_plan_entries",
                    now,
                    target_table=new_tables["lottery_plan_entries"],
                )
            if "plan_condition_snapshots" in existing_tables:
                _copy_legacy_plan_condition_snapshots(
                    connection,
                    "plan_condition_snapshots",
                    now,
                    target_table=new_tables["plan_condition_snapshots"],
                )
            if "plan_reviews" in existing_tables:
                _copy_legacy_plan_reviews(
                    connection,
                    "plan_reviews",
                    now,
                    target_table=new_tables["plan_reviews"],
                )

            connection.execute(
                f"""
                UPDATE {_quote_identifier(new_tables["lottery_plans"])}
                SET request_id = ''
                WHERE request_id != ''
                  AND rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM {_quote_identifier(new_tables["lottery_plans"])}
                    WHERE request_id != ''
                    GROUP BY client_id, request_id
                  )
                """
            )

            _validate_plan_schema_data(connection, new_tables)
            _drop_plan_indexes_and_triggers(connection)
            for table in PLAN_TABLES_CHILD_FIRST:
                if table in existing_tables:
                    connection.execute(
                        f"ALTER TABLE {_quote_identifier(table)} "
                        f"RENAME TO {_quote_identifier(old_tables[table])}"
                    )
            for table in PLAN_TABLES:
                connection.execute(
                    f"ALTER TABLE {_quote_identifier(new_tables[table])} "
                    f"RENAME TO {_quote_identifier(table)}"
                )
            _create_current_plan_indexes_and_triggers(connection)
            fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise ValueError(INVALID_PLAN_MESSAGE)
            for table in PLAN_TABLES_CHILD_FIRST:
                if table in existing_tables:
                    connection.execute(f"DROP TABLE {_quote_identifier(old_tables[table])}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.execute(f"PRAGMA foreign_keys = {1 if foreign_keys_enabled else 0}")


def _create_current_plan_schema(connection: sqlite3.Connection) -> None:
    _create_plan_schema(connection, _prefixed_plan_tables(""))


def _prefixed_plan_tables(prefix: str) -> dict[str, str]:
    return {table: f"{prefix}{table}" for table in PLAN_TABLES}


def _create_plan_schema(
    connection: sqlite3.Connection,
    tables: dict[str, str],
) -> None:
    plans = _quote_identifier(tables["lottery_plans"])
    entries = _quote_identifier(tables["lottery_plan_entries"])
    snapshots = _quote_identifier(tables["plan_condition_snapshots"])
    reviews = _quote_identifier(tables["plan_reviews"])
    connection.execute(
        f"""
        CREATE TABLE {plans} (
          id TEXT PRIMARY KEY,
          client_id TEXT NOT NULL,
          game_key TEXT NOT NULL CHECK (game_key = '3d'),
          target_issue TEXT NOT NULL,
          target_draw_date TEXT NOT NULL,
          source_type TEXT NOT NULL CHECK (source_type IN ('fortune', 'manual', 'filter', 'random', 'carried')),
          request_id TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'saved'
            CHECK (status IN ('draft', 'saved', 'pending_review', 'reviewed', 'expired')),
          carried_from_plan_id TEXT REFERENCES {plans}(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE {entries} (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          plan_id TEXT NOT NULL REFERENCES {plans}(id) ON DELETE CASCADE,
          position INTEGER NOT NULL,
          main_numbers TEXT NOT NULL,
          special_numbers TEXT NOT NULL DEFAULT '[]',
          note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 120),
          created_at TEXT NOT NULL,
          CONSTRAINT ck_lottery_plan_entries_special_numbers_empty
            CHECK (special_numbers = '[]'),
          UNIQUE(plan_id, position)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE {snapshots} (
          plan_id TEXT PRIMARY KEY REFERENCES {plans}(id) ON DELETE CASCADE,
          mode TEXT NOT NULL CHECK (mode IN ('simple', 'pro')),
          analysis_window INTEGER NOT NULL CHECK (analysis_window IN (30, 60, 120)),
          conditions_json TEXT NOT NULL DEFAULT '{{}}',
          metrics_json TEXT NOT NULL DEFAULT '{{}}',
          latest_data_issue TEXT NOT NULL DEFAULT '',
          latest_data_date TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE {reviews} (
          plan_id TEXT PRIMARY KEY REFERENCES {plans}(id) ON DELETE CASCADE,
          draw_issue TEXT NOT NULL,
          draw_numbers TEXT NOT NULL,
          review_status TEXT NOT NULL,
          direct_hit INTEGER NOT NULL CHECK (direct_hit IN (0, 1)),
          group_type TEXT NOT NULL,
          matched_positions TEXT NOT NULL DEFAULT '[]',
          matched_conditions TEXT NOT NULL DEFAULT '[]',
          missed_conditions TEXT NOT NULL DEFAULT '[]',
          result_json TEXT NOT NULL DEFAULT '{{}}',
          reviewed_at TEXT NOT NULL
        )
        """
    )


def _create_current_plan_indexes_and_triggers(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_REQUEST_INDEX_SQL)
    connection.execute(CREATE_LIST_INDEX_SQL)
    connection.execute(CREATE_CARRIED_SCOPE_INSERT_TRIGGER_SQL)
    connection.execute(CREATE_CARRIED_SCOPE_UPDATE_TRIGGER_SQL)


def _drop_plan_indexes_and_triggers(connection: sqlite3.Connection) -> None:
    connection.execute(DROP_CARRIED_SCOPE_INSERT_TRIGGER_SQL)
    connection.execute(DROP_CARRIED_SCOPE_UPDATE_TRIGGER_SQL)
    connection.execute(DROP_REQUEST_INDEX_SQL)
    connection.execute(DROP_LIST_INDEX_SQL)


def _copy_legacy_lottery_plans(
    connection: sqlite3.Connection,
    legacy_table: str,
    now: str,
    *,
    target_table: str,
) -> None:
    columns = _table_columns(connection, legacy_table)
    legacy = _quote_identifier(legacy_table)
    target = _quote_identifier(target_table)
    old = "old_plan"
    carried_from = "NULL"
    if "carried_from_plan_id" in columns:
        carried_from = f"""
            CASE
              WHEN {old}.{_quote_identifier("carried_from_plan_id")} IS NOT NULL
                AND EXISTS (
                  SELECT 1
                  FROM {legacy} AS parent_plan
                  WHERE parent_plan.{_quote_identifier("id")} = {old}.{_quote_identifier("carried_from_plan_id")}
                    AND parent_plan.{_quote_identifier("client_id")} = {old}.{_quote_identifier("client_id")}
                )
              THEN {old}.{_quote_identifier("carried_from_plan_id")}
              ELSE NULL
            END
        """
    source_type = _allowed_text_expr(
        columns,
        "source_type",
        ALLOWED_SOURCE_TYPES,
        "'manual'",
        alias=old,
    )
    status = _allowed_text_expr(
        columns,
        "status",
        ALLOWED_STATUSES,
        "'saved'",
        alias=old,
    )
    connection.execute(
        f"""
        INSERT INTO {target} (
            id, client_id, game_key, target_issue, target_draw_date,
            source_type, request_id, title, status, carried_from_plan_id,
            created_at, updated_at
        )
        SELECT
            {_coalesce_text_expr(columns, "id", "''", alias=old)},
            {_coalesce_text_expr(columns, "client_id", "''", alias=old)},
            {_allowed_text_expr(columns, "game_key", {"3d"}, "'3d'", alias=old)},
            {_coalesce_text_expr(columns, "target_issue", "''", alias=old)},
            {_coalesce_text_expr(columns, "target_draw_date", "''", alias=old)},
            {source_type},
            {_coalesce_text_expr(columns, "request_id", "''", alias=old)},
            {_coalesce_text_expr(columns, "title", "'未命名方案'", alias=old)},
            {status},
            {carried_from},
            {_coalesce_text_expr(columns, "created_at", now, alias=old)},
            {_coalesce_text_expr(columns, "updated_at", now, alias=old)}
        FROM {legacy} AS {old}
        """
    )


def _copy_legacy_plan_entries(
    connection: sqlite3.Connection,
    legacy_table: str,
    now: str,
    *,
    target_table: str,
) -> None:
    columns = _table_columns(connection, legacy_table)
    legacy = _quote_identifier(legacy_table)
    target = _quote_identifier(target_table)
    old = "old_entry"
    connection.execute(
        f"""
        INSERT INTO {target} (
            id, plan_id, position, main_numbers, special_numbers, note, created_at
        )
        SELECT
            {_coalesce_raw_expr(columns, "id", "NULL", alias=old)},
            {_coalesce_text_expr(columns, "plan_id", "''", alias=old)},
            {_coalesce_raw_expr(columns, "position", "0", alias=old)},
            {_coalesce_text_expr(columns, "main_numbers", "'[0,0,0]'", alias=old)},
            '[]',
            substr({_coalesce_text_expr(columns, "note", "''", alias=old)}, 1, {MAX_NOTE_LENGTH}),
            {_coalesce_text_expr(columns, "created_at", now, alias=old)}
        FROM {legacy} AS {old}
        """
    )


def _copy_legacy_plan_condition_snapshots(
    connection: sqlite3.Connection,
    legacy_table: str,
    now: str,
    *,
    target_table: str,
) -> None:
    columns = _table_columns(connection, legacy_table)
    legacy = _quote_identifier(legacy_table)
    target = _quote_identifier(target_table)
    old = "old_snapshot"
    window_source = "30"
    if "analysis_window" in columns:
        window_source = f"{old}.{_quote_identifier('analysis_window')}"
    elif "window" in columns:
        window_source = f"{old}.{_quote_identifier('window')}"
    analysis_window = (
        f"CASE WHEN {window_source} IN (30, 60, 120) "
        f"THEN {window_source} ELSE 30 END"
    )
    connection.execute(
        f"""
        INSERT INTO {target} (
            plan_id, mode, analysis_window, conditions_json, metrics_json,
            latest_data_issue, latest_data_date, created_at
        )
        SELECT
            {_coalesce_text_expr(columns, "plan_id", "''", alias=old)},
            {_allowed_text_expr(columns, "mode", ALLOWED_MODES, "'simple'", alias=old)},
            {analysis_window},
            {_coalesce_text_expr(columns, "conditions_json", "'{}'", alias=old)},
            {_coalesce_text_expr(columns, "metrics_json", "'{}'", alias=old)},
            {_coalesce_text_expr(columns, "latest_data_issue", "''", alias=old)},
            {_coalesce_text_expr(columns, "latest_data_date", "''", alias=old)},
            {_coalesce_text_expr(columns, "created_at", now, alias=old)}
        FROM {legacy} AS {old}
        """
    )


def _copy_legacy_plan_reviews(
    connection: sqlite3.Connection,
    legacy_table: str,
    now: str,
    *,
    target_table: str,
) -> None:
    columns = _table_columns(connection, legacy_table)
    legacy = _quote_identifier(legacy_table)
    target = _quote_identifier(target_table)
    old = "old_review"
    direct_hit = "0"
    if "direct_hit" in columns:
        direct_hit = (
            f"CASE WHEN {old}.{_quote_identifier('direct_hit')} IN (0, 1) "
            f"THEN {old}.{_quote_identifier('direct_hit')} ELSE 0 END"
        )
    connection.execute(
        f"""
        INSERT INTO {target} (
            plan_id, draw_issue, draw_numbers, review_status, direct_hit,
            group_type, matched_positions, matched_conditions,
            missed_conditions, result_json, reviewed_at
        )
        SELECT
            {_coalesce_text_expr(columns, "plan_id", "''", alias=old)},
            {_coalesce_text_expr(columns, "draw_issue", "''", alias=old)},
            {_coalesce_text_expr(columns, "draw_numbers", "'[]'", alias=old)},
            {_coalesce_text_expr(columns, "review_status", "''", alias=old)},
            {direct_hit},
            {_coalesce_text_expr(columns, "group_type", "''", alias=old)},
            {_coalesce_text_expr(columns, "matched_positions", "'[]'", alias=old)},
            {_coalesce_text_expr(columns, "matched_conditions", "'[]'", alias=old)},
            {_coalesce_text_expr(columns, "missed_conditions", "'[]'", alias=old)},
            {_coalesce_text_expr(columns, "result_json", "'{}'", alias=old)},
            {_coalesce_text_expr(columns, "reviewed_at", now, alias=old)}
        FROM {legacy} AS {old}
        """
    )


def _validate_plan_schema_data(
    connection: sqlite3.Connection,
    tables: dict[str, str],
) -> None:
    plans = _quote_identifier(tables["lottery_plans"])
    entries = _quote_identifier(tables["lottery_plan_entries"])
    snapshots = _quote_identifier(tables["plan_condition_snapshots"])
    reviews = _quote_identifier(tables["plan_reviews"])
    plan_ids = {
        str(row["id"])
        for row in connection.execute(f"SELECT id FROM {plans}").fetchall()
    }

    entry_keys: set[tuple[str, int]] = set()
    for row in connection.execute(
        f"""
        SELECT plan_id, position, main_numbers, special_numbers
        FROM {entries}
        ORDER BY plan_id, position
        """
    ).fetchall():
        plan_id = str(row["plan_id"])
        if plan_id not in plan_ids:
            raise ValueError(INVALID_PLAN_MESSAGE)
        key = (plan_id, int(row["position"]))
        if key in entry_keys:
            raise ValueError(INVALID_PLAN_MESSAGE)
        entry_keys.add(key)
        _decode_main_numbers_json(row["main_numbers"])
        _decode_empty_special_numbers(row["special_numbers"])

    for row in connection.execute(
        f"""
        SELECT plan_id, conditions_json, metrics_json
        FROM {snapshots}
        ORDER BY plan_id
        """
    ).fetchall():
        if str(row["plan_id"]) not in plan_ids:
            raise ValueError(INVALID_PLAN_MESSAGE)
        _decode_json_object(row["conditions_json"], INVALID_PLAN_MESSAGE)
        _decode_json_object(row["metrics_json"], INVALID_PLAN_MESSAGE)

    for row in connection.execute(
        f"""
        SELECT plan_id, draw_numbers
        FROM {reviews}
        ORDER BY plan_id
        """
    ).fetchall():
        if str(row["plan_id"]) not in plan_ids:
            raise ValueError(INVALID_PLAN_MESSAGE)
        _decode_number_triplet_json(row["draw_numbers"], INVALID_PLAN_MESSAGE)


def _sqlite_objects(
    connection: sqlite3.Connection,
    object_type: str,
    *,
    table: str | None = None,
) -> set[str]:
    if table is None:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ?
            """,
            (object_type,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ? AND tbl_name = ?
            """,
            (object_type, table),
        ).fetchall()
    return {str(row[0]) for row in rows}


def _table_columns(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {
        str(_row_value(row, "name", 1)): row
        for row in connection.execute(
            f"PRAGMA table_info({_quote_identifier(table)})"
        ).fetchall()
    }


def _table_sql(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return "" if row is None else str(row[0])


def _child_fk_is_current(connection: sqlite3.Connection, table: str) -> bool:
    rows = connection.execute(
        f"PRAGMA foreign_key_list({_quote_identifier(table)})"
    ).fetchall()
    return any(
        str(_row_value(row, "table", 2)) == "lottery_plans"
        and str(_row_value(row, "on_delete", 6)) == "CASCADE"
        for row in rows
    )


def _allowed_text_expr(
    columns: dict[str, sqlite3.Row],
    column: str,
    allowed: set[str],
    default: str,
    *,
    alias: str,
) -> str:
    if column not in columns:
        return default
    values = ", ".join(_sql_literal(value) for value in sorted(allowed))
    source = f"{alias}.{_quote_identifier(column)}"
    return f"CASE WHEN {source} IN ({values}) THEN {source} ELSE {default} END"


def _coalesce_text_expr(
    columns: dict[str, sqlite3.Row],
    column: str,
    default: str,
    *,
    alias: str,
) -> str:
    if column not in columns:
        return default
    return f"COALESCE({alias}.{_quote_identifier(column)}, {default})"


def _coalesce_raw_expr(
    columns: dict[str, sqlite3.Row],
    column: str,
    default: str,
    *,
    alias: str,
) -> str:
    if column not in columns:
        return default
    return f"COALESCE({alias}.{_quote_identifier(column)}, {default})"


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _row_value(row: sqlite3.Row, key: str, index: int) -> Any:
    try:
        return row[key]
    except (IndexError, TypeError):
        return row[index]


def _index_definition(connection: sqlite3.Connection, index_name: str) -> list[tuple[str, bool]]:
    rows = connection.execute(f"PRAGMA index_xinfo({index_name})").fetchall()
    key_rows = [row for row in rows if int(row[5])]
    return [
        (str(row[2]), bool(row[3]))
        for row in sorted(key_rows, key=lambda row: int(row[0]))
    ]


def _normalize_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(INVALID_PLAN_MESSAGE)
    game_key = _normalize_text(payload.get("game_key")).lower()
    if game_key != "3d":
        raise ValueError(INVALID_PLAN_MESSAGE)
    source_type = _normalize_text(payload.get("source_type"))
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError(INVALID_PLAN_MESSAGE)
    target_issue = _normalize_required_text(payload.get("target_issue"))
    target_draw_date = _normalize_required_text(payload.get("target_draw_date"))
    _validate_iso_date(target_draw_date)
    carried_from_plan_id = _normalize_text(payload.get("carried_from_plan_id")) or None
    return {
        "game_key": "3d",
        "target_issue": target_issue,
        "target_draw_date": target_draw_date,
        "source_type": source_type,
        "request_id": _normalize_text(payload.get("request_id")),
        "title": _normalize_title(payload.get("title")),
        "entries": _normalize_entries(payload.get("entries")),
        "condition_snapshot": _normalize_snapshot(payload.get("condition_snapshot")),
        "carried_from_plan_id": carried_from_plan_id,
    }


def _normalize_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not (1 <= len(value) <= MAX_ENTRY_COUNT):
        raise ValueError(INVALID_PLAN_MESSAGE)
    entries = []
    seen_positions: set[int] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(INVALID_PLAN_MESSAGE)
        position = _normalize_entry_position(item, index)
        if position in seen_positions:
            raise ValueError(INVALID_PLAN_MESSAGE)
        seen_positions.add(position)
        main_numbers = _normalize_main_numbers(item.get("main_numbers"))
        special_numbers = item.get("special_numbers", [])
        if special_numbers not in (None, []):
            raise ValueError(INVALID_PLAN_MESSAGE)
        note = _normalize_text(item.get("note"))
        if len(note) > MAX_NOTE_LENGTH:
            raise ValueError(INVALID_PLAN_MESSAGE)
        entries.append(
            {
                "position": position,
                "main_numbers": main_numbers,
                "special_numbers": [],
                "note": note,
            }
        )
    return entries


def _normalize_entry_position(item: dict[str, Any], fallback: int) -> int:
    raw_position = item.get("position", fallback)
    if type(raw_position) is not int:
        raise ValueError(INVALID_PLAN_MESSAGE)
    if raw_position < 0 or raw_position > 49:
        raise ValueError(INVALID_PLAN_MESSAGE)
    return raw_position


def _normalize_main_numbers(value: Any) -> list[int]:
    return _normalize_number_triplet(value, INVALID_PLAN_MESSAGE)


def _normalize_number_triplet(value: Any, error_message: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(error_message)
    numbers = []
    for item in value:
        if type(item) is not int:
            raise ValueError(error_message)
        if item < 0 or item > 9:
            raise ValueError(error_message)
        numbers.append(item)
    return numbers


def _decode_main_numbers_json(value: Any) -> list[int]:
    return _decode_number_triplet_json(value, INVALID_PLAN_MESSAGE)


def _decode_number_triplet_json(value: Any, error_message: str) -> list[int]:
    loaded = _load_json_strict(value, error_message)
    return _normalize_number_triplet(loaded, error_message)


def _decode_empty_special_numbers(value: Any) -> list[int]:
    if str(value) != "[]":
        raise ValueError(INVALID_PLAN_MESSAGE)
    return []


def _decode_json_object(value: Any, error_message: str) -> dict[str, Any]:
    loaded = _load_json_strict(value, error_message)
    if not isinstance(loaded, dict):
        raise ValueError(error_message)
    return loaded


def _load_json_strict(value: Any, error_message: str) -> Any:
    if value in (None, ""):
        raise ValueError(error_message)
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(error_message) from exc


def _normalize_snapshot(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ValueError(INVALID_PLAN_MESSAGE)
    mode = _normalize_text(value.get("mode"))
    if mode not in ALLOWED_MODES:
        raise ValueError(INVALID_PLAN_MESSAGE)
    window = _safe_int(value.get("analysis_window"), -1)
    if window not in ALLOWED_WINDOWS:
        raise ValueError(INVALID_PLAN_MESSAGE)
    conditions = _normalize_json_object(value.get("conditions_json", {}))
    metrics = _normalize_json_object(value.get("metrics_json", {}))
    latest_data_issue = _normalize_text(value.get("latest_data_issue"))
    latest_data_date = _normalize_text(value.get("latest_data_date"))
    if latest_data_date:
        _validate_iso_date(latest_data_date)
    return {
        "mode": mode,
        "analysis_window": window,
        "conditions_json": conditions,
        "metrics_json": metrics,
        "latest_data_issue": latest_data_issue,
        "latest_data_date": latest_data_date,
    }


def _normalize_json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(INVALID_PLAN_MESSAGE)
    _validate_json_safe(value)
    return value


def _validate_json_safe(value: Any) -> None:
    if _json_depth(value) > MAX_JSON_DEPTH:
        raise ValueError(INVALID_PLAN_MESSAGE)
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(INVALID_PLAN_MESSAGE) from exc
    if len(serialized.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError(INVALID_PLAN_MESSAGE)


def _json_depth(value: Any) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_json_depth(nested) for nested in value.values())
    if isinstance(value, list):
        if not value:
            return 1
        return 1 + max(_json_depth(nested) for nested in value)
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(INVALID_PLAN_MESSAGE)
    return 1


def _normalize_title(value: Any) -> str:
    title = _normalize_text(value)
    if not title or len(title) > MAX_TITLE_LENGTH:
        raise ValueError(INVALID_PLAN_MESSAGE)
    return title


def _normalize_update_status(value: Any) -> str:
    status = _normalize_text(value)
    if status not in UPDATE_STATUSES:
        raise ValueError(INVALID_PLAN_MESSAGE)
    return status


def _normalize_client_id(value: Any, *, required: bool = False) -> str:
    client_id = _normalize_text(value)[:MAX_CLIENT_ID_LENGTH]
    if required and not client_id:
        raise ValueError("client_id is required")
    return client_id


def _normalize_required_text(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        raise ValueError(INVALID_PLAN_MESSAGE)
    return text


def _normalize_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _validate_iso_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(INVALID_PLAN_MESSAGE) from exc


def _safe_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _new_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex}"


def _replace_entries(
    connection: sqlite3.Connection,
    plan_id: str,
    entries: list[dict[str, Any]],
    now: str,
) -> None:
    for entry in entries:
        connection.execute(
            """
            INSERT INTO lottery_plan_entries (
                plan_id, position, main_numbers, special_numbers, note, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                entry["position"],
                _dump_json(entry["main_numbers"]),
                "[]",
                entry["note"],
                now,
            ),
        )


def _replace_snapshot(
    connection: sqlite3.Connection,
    plan_id: str,
    snapshot: dict[str, Any] | None,
    now: str,
) -> None:
    if snapshot is None:
        return
    connection.execute(
        """
        INSERT INTO plan_condition_snapshots (
            plan_id, mode, analysis_window, conditions_json, metrics_json,
            latest_data_issue, latest_data_date, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            snapshot["mode"],
            snapshot["analysis_window"],
            _dump_json(snapshot["conditions_json"]),
            _dump_json(snapshot["metrics_json"]),
            snapshot["latest_data_issue"],
            snapshot["latest_data_date"],
            now,
        ),
    )


def _get_plan_row(
    connection: sqlite3.Connection,
    client_id: str,
    plan_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM lottery_plans
        WHERE id = ? AND client_id = ?
        """,
        (plan_id, client_id),
    ).fetchone()


def _get_plan_by_request_id(
    connection: sqlite3.Connection,
    client_id: str,
    request_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM lottery_plans
        WHERE client_id = ? AND request_id = ?
        """,
        (client_id, request_id),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_plan(connection, dict(row), duplicate_warning=False)


def _validate_carried_from_plan(
    connection: sqlite3.Connection,
    client_id: str,
    carried_from_plan_id: str | None,
) -> None:
    if carried_from_plan_id is None:
        return
    row = connection.execute(
        """
        SELECT 1
        FROM lottery_plans
        WHERE id = ? AND client_id = ?
        """,
        (carried_from_plan_id, client_id),
    ).fetchone()
    if row is None:
        raise ValueError(INVALID_PLAN_MESSAGE)


def _has_duplicate_entries(
    connection: sqlite3.Connection,
    *,
    client_id: str,
    target_issue: str,
    target_draw_date: str,
    source_type: str,
    entries: list[dict[str, Any]],
) -> bool:
    rows = connection.execute(
        """
        SELECT *
        FROM lottery_plans
        WHERE client_id = ?
          AND source_type = ?
        """,
        (client_id, source_type),
    ).fetchall()
    expected = _entry_signature(entries)
    for row in rows:
        plan = _hydrate_plan(connection, dict(row), duplicate_warning=False)
        if _entry_signature(plan["entries"]) == expected:
            return True
    return False


def _entry_signature(entries: list[dict[str, Any]]) -> list[list[int]]:
    return [list(entry["main_numbers"]) for entry in entries]


def _hydrate_plan(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    *,
    duplicate_warning: bool,
) -> dict[str, Any]:
    plan_id = str(row["id"])
    return {
        "id": plan_id,
        "client_id": str(row["client_id"]),
        "game_key": str(row["game_key"]),
        "target_issue": str(row["target_issue"]),
        "target_draw_date": str(row["target_draw_date"]),
        "source_type": str(row.get("source_type") or ""),
        "request_id": str(row.get("request_id") or ""),
        "title": str(row["title"]),
        "status": str(row["status"]),
        "carried_from_plan_id": row.get("carried_from_plan_id"),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "entries": _plan_entries(connection, plan_id),
        "condition_snapshot": _plan_snapshot(connection, plan_id),
        "review": _get_review(connection, plan_id),
        "duplicate_warning": duplicate_warning,
    }


def _plan_entries(connection: sqlite3.Connection, plan_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, plan_id, position, main_numbers, special_numbers, note, created_at
        FROM lottery_plan_entries
        WHERE plan_id = ?
        ORDER BY position ASC, id ASC
        """,
        (plan_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "plan_id": str(row["plan_id"]),
            "position": int(row["position"]),
            "main_numbers": _decode_main_numbers_json(row["main_numbers"]),
            "special_numbers": _decode_empty_special_numbers(row["special_numbers"]),
            "note": str(row["note"] or ""),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def _plan_snapshot(
    connection: sqlite3.Connection,
    plan_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM plan_condition_snapshots
        WHERE plan_id = ?
        """,
        (plan_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "plan_id": str(row["plan_id"]),
        "mode": str(row["mode"]),
        "analysis_window": int(row["analysis_window"]),
        "conditions_json": _decode_json_object(row["conditions_json"], INVALID_PLAN_MESSAGE),
        "metrics_json": _decode_json_object(row["metrics_json"], INVALID_PLAN_MESSAGE),
        "latest_data_issue": str(row["latest_data_issue"] or ""),
        "latest_data_date": str(row["latest_data_date"] or ""),
        "created_at": str(row["created_at"]),
    }


def _get_review(connection: sqlite3.Connection, plan_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM plan_reviews
        WHERE plan_id = ?
        """,
        (plan_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "plan_id": str(row["plan_id"]),
        "draw_issue": str(row["draw_issue"]),
        "draw_numbers": _decode_number_triplet_json(row["draw_numbers"], INVALID_REVIEW_MESSAGE),
        "review_status": str(row["review_status"]),
        "direct_hit": bool(row["direct_hit"]),
        "group_type": str(row["group_type"]),
        "matched_positions": _load_json(row["matched_positions"], []),
        "matched_conditions": _load_json(row["matched_conditions"], []),
        "missed_conditions": _load_json(row["missed_conditions"], []),
        "result_json": _load_json(row["result_json"], {}),
        "reviewed_at": str(row["reviewed_at"]),
    }


def _review_matches(review: dict[str, Any], actual: dict[str, Any]) -> bool:
    return (
        review["draw_issue"] == actual["issue"]
        and review["draw_numbers"] == actual["numbers"]
    )


def _normalize_draw(draw: dict[str, Any]) -> dict[str, Any]:
    issue = _normalize_text(draw.get("issue"))
    draw_date = _normalize_text(draw.get("draw_date"))
    if not issue or not draw_date:
        raise ValueError(INVALID_REVIEW_MESSAGE)
    try:
        date.fromisoformat(draw_date)
    except ValueError as exc:
        raise ValueError(INVALID_REVIEW_MESSAGE) from exc
    numbers = _draw_numbers(draw)
    if len(numbers) != 3:
        raise ValueError(INVALID_REVIEW_MESSAGE)
    return {"issue": issue, "draw_date": draw_date, "numbers": numbers}


def _draw_numbers(draw: dict[str, Any]) -> list[int]:
    if isinstance(draw.get("main"), list):
        return _normalize_number_triplet(draw["main"], INVALID_REVIEW_MESSAGE)
    elif isinstance(draw.get("draw_numbers"), list):
        return _normalize_number_triplet(draw["draw_numbers"], INVALID_REVIEW_MESSAGE)
    else:
        red_numbers = _normalize_text(draw.get("red_numbers"))
        if not red_numbers:
            raise ValueError(INVALID_REVIEW_MESSAGE)
        return _parse_red_numbers_text(red_numbers)


def _parse_red_numbers_text(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError(INVALID_REVIEW_MESSAGE)
    numbers = []
    for part in parts:
        if not part.isdecimal():
            raise ValueError(INVALID_REVIEW_MESSAGE)
        number = int(part)
        if number < 0 or number > 9:
            raise ValueError(INVALID_REVIEW_MESSAGE)
        numbers.append(number)
    return numbers


def _build_review_result(plan: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    actual_numbers = actual["numbers"]
    group_type = _group_type(actual_numbers)
    entry_results = []
    direct_hit = False
    all_matched_positions: set[int] = set()
    for entry in plan["entries"]:
        main_numbers = entry["main_numbers"]
        matched_positions = [
            index
            for index, number in enumerate(main_numbers)
            if actual_numbers[index] == number
        ]
        entry_direct = main_numbers == actual_numbers
        direct_hit = direct_hit or entry_direct
        all_matched_positions.update(matched_positions)
        entry_results.append(
            {
                "entry_id": entry["id"],
                "position": entry["position"],
                "main_numbers": main_numbers,
                "direct_hit": entry_direct,
                "matched_positions": matched_positions,
                "any_position_hits": _counter_hits(main_numbers, actual_numbers),
            }
        )
    actual_metrics = {
        "group_type": group_type,
        "sum": sum(actual_numbers),
        "span": max(actual_numbers) - min(actual_numbers),
        "numbers": actual_numbers,
        "positions": {str(index): number for index, number in enumerate(actual_numbers)},
    }
    matched_conditions, missed_conditions = _compare_snapshot_conditions(
        plan.get("condition_snapshot"),
        actual_metrics,
    )
    return {
        "draw_issue": actual["issue"],
        "draw_date": actual["draw_date"],
        "draw_numbers": actual_numbers,
        "group_type": group_type,
        "direct_hit": direct_hit,
        "matched_positions": sorted(all_matched_positions),
        "matched_conditions": matched_conditions,
        "missed_conditions": missed_conditions,
        "actual": actual_metrics,
        "entries": entry_results,
    }


def _counter_hits(predicted: list[int], actual: list[int]) -> list[int]:
    remaining = Counter(actual)
    hits = []
    for number in predicted:
        if remaining[number] > 0:
            hits.append(number)
            remaining[number] -= 1
    return hits


def _group_type(numbers: list[int]) -> str:
    unique_count = len(set(numbers))
    if unique_count == 1:
        return "豹子"
    if unique_count == 2:
        return "组三"
    return "组六"


def _compare_snapshot_conditions(
    snapshot: dict[str, Any] | None,
    actual: dict[str, Any],
) -> tuple[list[str], list[str]]:
    if not snapshot:
        return [], []
    matched: list[str] = []
    missed: list[str] = []
    for key, value in (snapshot.get("conditions_json") or {}).items():
        label = f"conditions.{key}"
        (matched if _condition_matches(key, value, actual) else missed).append(label)
    for key, value in (snapshot.get("metrics_json") or {}).items():
        label = f"metrics.{key}"
        (matched if _condition_matches(key, value, actual) else missed).append(label)
    return matched, missed


def _condition_matches(key: str, value: Any, actual: dict[str, Any]) -> bool:
    key = str(key)
    if key in {"group_type", "digit_type", "shape"}:
        return _matches_value(actual["group_type"], value)
    if key == "sum":
        return _matches_number(actual["sum"], value)
    if key == "sum_min":
        return actual["sum"] >= _safe_int(value, 999)
    if key == "sum_max":
        return actual["sum"] <= _safe_int(value, -1)
    if key == "span":
        return _matches_number(actual["span"], value)
    if key == "span_min":
        return actual["span"] >= _safe_int(value, 999)
    if key == "span_max":
        return actual["span"] <= _safe_int(value, -1)
    if key in {"contains", "required_digits", "include_digits"}:
        return not (Counter(_coerce_int_list(value)) - Counter(actual["numbers"]))
    if key in {"exclude_digits", "avoid_digits"}:
        return not (set(_coerce_int_list(value)) & set(actual["numbers"]))
    if key.startswith("position_"):
        position = _safe_int(key.removeprefix("position_"), -1)
        return _position_matches(actual, position, value)
    if key == "positions" and isinstance(value, dict):
        return all(
            _position_matches(actual, _safe_int(position, -1), expected)
            for position, expected in value.items()
        )
    return False


def _matches_value(actual: str, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in {str(item) for item in expected}
    return actual == str(expected)


def _matches_number(actual: int, expected: Any) -> bool:
    if isinstance(expected, dict):
        minimum = expected.get("min", expected.get("gte", expected.get("from")))
        maximum = expected.get("max", expected.get("lte", expected.get("to")))
        if minimum is not None and actual < _safe_int(minimum, 999):
            return False
        if maximum is not None and actual > _safe_int(maximum, -1):
            return False
        return True
    if isinstance(expected, list):
        return actual in {_safe_int(item, -999) for item in expected}
    return actual == _safe_int(expected, -999)


def _position_matches(actual: dict[str, Any], position: int, expected: Any) -> bool:
    if position < 0 or position >= len(actual["numbers"]):
        return False
    actual_number = actual["numbers"][position]
    if isinstance(expected, list):
        return actual_number in {_safe_int(item, -999) for item in expected}
    return actual_number == _safe_int(expected, -999)


def _coerce_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        return [_safe_int(item, -999) for item in value]
    return [_safe_int(value, -999)]


def _dump_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _load_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        loaded = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return fallback
    return loaded


def _utc_now_iso() -> str:
    global _LAST_TIMESTAMP
    with _TIMESTAMP_LOCK:
        now = datetime.now(timezone.utc)
        if _LAST_TIMESTAMP is not None and now <= _LAST_TIMESTAMP:
            now = _LAST_TIMESTAMP + timedelta(microseconds=1)
        _LAST_TIMESTAMP = now
        return now.isoformat(timespec="microseconds")
