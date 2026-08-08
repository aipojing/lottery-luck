from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any


CREATE_PRODUCT_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS product_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  event_name TEXT NOT NULL,
  properties TEXT NOT NULL DEFAULT '{}',
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_PRODUCT_EVENTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_product_events_client_time
ON product_events (client_id, occurred_at DESC, id DESC)
"""

DROP_OLD_PRODUCT_EVENTS_INDEX_SQL = """
DROP INDEX IF EXISTS idx_product_events_client_occurred_at
"""

DROP_CURRENT_PRODUCT_EVENTS_INDEX_SQL = """
DROP INDEX IF EXISTS idx_product_events_client_time
"""

ALLOWED_EVENT_NAMES = {
    "prediction_completed",
    "plan_saved",
    "workbench_opened",
    "plan_edited",
    "review_viewed",
    "plan_carried_forward",
    "tool_opened",
    "tool_result_generated",
}

ALLOWED_PROPERTY_KEYS = {
    "game_key",
    "source_type",
    "mode",
    "window",
    "entry_count",
    "candidate_count",
    "freshness_status",
    "review_status",
    "tool_key",
    "result_count",
}

STRING_PROPERTY_VALUES = {
    "game_key": {"ssq", "dlt", "3d", "pl3", "kl8", "qlc", "pl5"},
    "source_type": {"fortune", "manual", "filter", "random", "carried"},
    "mode": {"steady", "windfall", "guard", "simple", "pro"},
    "freshness_status": {"fresh", "attention", "stale", "empty"},
    # review_status is the only nullable property; omit it or pass None when absent.
    "review_status": {"draft", "saved", "pending_review", "reviewed", "expired"},
    # The 3D toolbox tools. A closed whitelist: an unknown tool key is rejected, never
    # passed through, so no free text can ride into an event on this property.
    "tool_key": {
        "trend",
        "omission",
        "frequency",
        "heat",
        "number",
        "attributes",
        "reduction",
        "recent",
    },
}
COUNT_PROPERTY_KEYS = {"entry_count", "candidate_count", "result_count"}
INTEGER_PROPERTY_KEYS = {"window", *COUNT_PROPERTY_KEYS}
WINDOW_VALUES = {30, 60, 120}
MIN_COUNT_PROPERTY_VALUE = 0
MAX_COUNT_PROPERTY_VALUE = 10000
MAX_CLIENT_ID_LENGTH = 96
MAX_STRING_PROPERTY_LENGTH = 64
MAX_PROPERTIES_BYTES = 2048
INVALID_EVENT_MESSAGE = "invalid product event"
CURRENT_PRODUCT_EVENTS_INDEX = "idx_product_events_client_time"
OLD_PRODUCT_EVENTS_INDEX = "idx_product_events_client_occurred_at"
CURRENT_PRODUCT_EVENTS_INDEX_DEFINITION = [
    ("client_id", False),
    ("occurred_at", True),
    ("id", True),
]
_SCHEMA_LOCK = threading.Lock()
_TIMESTAMP_LOCK = threading.Lock()
_LAST_OCCURRED_AT: datetime | None = None


def record_event(
    connection: sqlite3.Connection,
    *,
    client_id: str,
    event_name: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_client_id = _normalize_client_id(client_id)
    if not normalized_client_id:
        raise ValueError("client_id is required")
    normalized_event_name = _normalize_event_name(event_name)
    serialized_properties = _serialize_properties({} if properties is None else properties)
    occurred_at = _utc_now_iso()

    cursor = connection.execute(
        """
        INSERT INTO product_events (client_id, event_name, properties, occurred_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            normalized_client_id,
            normalized_event_name,
            serialized_properties,
            occurred_at,
        ),
    )
    connection.commit()
    return _get_event(connection, int(cursor.lastrowid))


def ensure_product_events_table(connection: sqlite3.Connection) -> None:
    if _product_events_schema_is_current(connection):
        return
    with _SCHEMA_LOCK:
        if _product_events_schema_is_current(connection):
            return
        connection.execute(CREATE_PRODUCT_EVENTS_SQL)
        connection.execute(DROP_OLD_PRODUCT_EVENTS_INDEX_SQL)
        connection.execute(DROP_CURRENT_PRODUCT_EVENTS_INDEX_SQL)
        connection.execute(CREATE_PRODUCT_EVENTS_INDEX_SQL)


def _product_events_schema_is_current(connection: sqlite3.Connection) -> bool:
    table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'product_events'
        """
    ).fetchone()
    if table is None:
        return False
    indexes = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND tbl_name = 'product_events'
            """
        ).fetchall()
    }
    if OLD_PRODUCT_EVENTS_INDEX in indexes or CURRENT_PRODUCT_EVENTS_INDEX not in indexes:
        return False
    return _index_definition(connection, CURRENT_PRODUCT_EVENTS_INDEX) == (
        CURRENT_PRODUCT_EVENTS_INDEX_DEFINITION
    )


def _index_definition(connection: sqlite3.Connection, index_name: str) -> list[tuple[str, bool]]:
    rows = connection.execute(f"PRAGMA index_xinfo({index_name})").fetchall()
    key_rows = [row for row in rows if int(row[5])]
    return [
        (str(row[2]), bool(row[3]))
        for row in sorted(key_rows, key=lambda row: int(row[0]))
    ]


def _get_event(connection: sqlite3.Connection, event_id: int) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, client_id, event_name, properties, occurred_at
        FROM product_events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        raise ValueError(INVALID_EVENT_MESSAGE)
    decoded = dict(row)
    decoded["properties"] = _load_properties(decoded["properties"])
    return decoded


def _normalize_client_id(value: str) -> str:
    return str(value or "").strip()[:MAX_CLIENT_ID_LENGTH]


def _normalize_event_name(value: str) -> str:
    event_name = str(value or "").strip()
    if event_name not in ALLOWED_EVENT_NAMES:
        raise ValueError(INVALID_EVENT_MESSAGE)
    return event_name


def _serialize_properties(properties: dict[str, Any]) -> str:
    if not isinstance(properties, dict):
        raise ValueError(INVALID_EVENT_MESSAGE)
    normalized: dict[str, Any] = {}
    for key, value in properties.items():
        if key not in ALLOWED_PROPERTY_KEYS:
            raise ValueError(INVALID_EVENT_MESSAGE)
        normalized[str(key)] = _normalize_property_value(str(key), value)
    try:
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(INVALID_EVENT_MESSAGE) from exc
    if len(serialized.encode("utf-8")) > MAX_PROPERTIES_BYTES:
        raise ValueError(INVALID_EVENT_MESSAGE)
    return serialized


def _normalize_property_value(key: str, value: Any) -> str | int | None:
    if value is None:
        if key == "review_status":
            return None
        raise ValueError(INVALID_EVENT_MESSAGE)
    if isinstance(value, bool):
        raise ValueError(INVALID_EVENT_MESSAGE)
    if isinstance(value, str):
        if len(value) > MAX_STRING_PROPERTY_LENGTH:
            raise ValueError(INVALID_EVENT_MESSAGE)
        allowed_values = STRING_PROPERTY_VALUES.get(key)
        if allowed_values is None or value not in allowed_values:
            raise ValueError(INVALID_EVENT_MESSAGE)
        return value
    if isinstance(value, int):
        if key == "window":
            if value not in WINDOW_VALUES:
                raise ValueError(INVALID_EVENT_MESSAGE)
            return value
        if key in COUNT_PROPERTY_KEYS:
            if value < MIN_COUNT_PROPERTY_VALUE or value > MAX_COUNT_PROPERTY_VALUE:
                raise ValueError(INVALID_EVENT_MESSAGE)
            return value
        raise ValueError(INVALID_EVENT_MESSAGE)
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(INVALID_EVENT_MESSAGE)
        raise ValueError(INVALID_EVENT_MESSAGE)
    raise ValueError(INVALID_EVENT_MESSAGE)


def _load_properties(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _utc_now_iso() -> str:
    global _LAST_OCCURRED_AT
    with _TIMESTAMP_LOCK:
        now = datetime.now(timezone.utc)
        if _LAST_OCCURRED_AT is not None and now <= _LAST_OCCURRED_AT:
            now = _LAST_OCCURRED_AT + timedelta(microseconds=1)
        _LAST_OCCURRED_AT = now
        return now.isoformat(timespec="microseconds")
