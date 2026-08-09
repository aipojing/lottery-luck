from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any


EVENT_CLIENT_LIMIT = 120
EVENT_NETWORK_LIMIT = 300
EVENT_WINDOW_SECONDS = 3600
PLAN_CLIENT_LIMIT = 20
PLAN_NETWORK_LIMIT = 80
PLAN_WINDOW_SECONDS = 86400

CREATE_WRITE_LIMITS_SQL = """
CREATE TABLE IF NOT EXISTS api_write_limits (
  scope TEXT NOT NULL,
  bucket_key TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  count INTEGER NOT NULL CHECK (count >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (scope, bucket_key, window_start)
)
"""

CREATE_WRITE_LIMITS_TIME_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_api_write_limits_window
ON api_write_limits (window_start)
"""

_SCHEMA_LOCK = threading.Lock()


class WriteRateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__("write rate limit exceeded")
        self.retry_after = retry_after


def ensure_write_limits_table(connection: Any) -> None:
    with _SCHEMA_LOCK:
        connection.execute(CREATE_WRITE_LIMITS_SQL)
        connection.execute(CREATE_WRITE_LIMITS_TIME_INDEX_SQL)
        connection.commit()


def consume_write_limit(
    connection: Any,
    *,
    scope: str,
    bucket_key: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> bool:
    normalized_scope = str(scope or "").strip()[:64]
    normalized_key = str(bucket_key or "").strip()[:128]
    if not normalized_scope or not normalized_key:
        raise ValueError("write limit scope and bucket are required")
    if limit <= 0 or window_seconds <= 0:
        raise ValueError("write limit values must be positive")

    current = _utc_datetime(now)
    current_epoch = int(current.timestamp())
    window_start = current_epoch - (current_epoch % window_seconds)
    updated_at = current.isoformat(timespec="seconds")

    try:
        return _consume_existing_table(
            connection,
            scope=normalized_scope,
            bucket_key=normalized_key,
            limit=limit,
            window_start=window_start,
            window_seconds=window_seconds,
            updated_at=updated_at,
        )
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        if getattr(connection, "in_transaction", False):
            connection.rollback()
        ensure_write_limits_table(connection)
        return _consume_existing_table(
            connection,
            scope=normalized_scope,
            bucket_key=normalized_key,
            limit=limit,
            window_start=window_start,
            window_seconds=window_seconds,
            updated_at=updated_at,
        )


def prune_write_limits(
    connection: Any,
    *,
    before: datetime | None = None,
) -> int:
    cutoff = _utc_datetime(before or (datetime.now(timezone.utc) - timedelta(days=2)))
    cursor = connection.execute(
        "DELETE FROM api_write_limits WHERE window_start < ?",
        (int(cutoff.timestamp()),),
    )
    connection.commit()
    return max(0, int(cursor.rowcount))


def enforce_request_write_limits(
    repo: Any,
    request: Any,
    *,
    client_id: str,
    category: str,
) -> None:
    consume = getattr(repo, "consume_write_limit", None)
    if not callable(consume):
        return

    if category == "events":
        client_limit = EVENT_CLIENT_LIMIT
        network_limit = EVENT_NETWORK_LIMIT
        window_seconds = EVENT_WINDOW_SECONDS
    elif category == "plans":
        client_limit = PLAN_CLIENT_LIMIT
        network_limit = PLAN_NETWORK_LIMIT
        window_seconds = PLAN_WINDOW_SECONDS
    else:
        raise ValueError("unsupported write limit category")

    network_key = _network_bucket_key(request)
    buckets = (
        (f"{category}-client", client_id, client_limit),
        (f"{category}-network", network_key, network_limit),
    )
    for scope, bucket_key, limit in buckets:
        if not consume(
            scope=scope,
            bucket_key=bucket_key,
            limit=limit,
            window_seconds=window_seconds,
        ):
            raise WriteRateLimitExceeded(window_seconds)


def _consume_existing_table(
    connection: Any,
    *,
    scope: str,
    bucket_key: str,
    limit: int,
    window_start: int,
    window_seconds: int,
    updated_at: str,
) -> bool:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            """
            SELECT count
            FROM api_write_limits
            WHERE scope = ? AND bucket_key = ? AND window_start = ?
            """,
            (scope, bucket_key, window_start),
        ).fetchone()
        count = int(row[0]) if row is not None else 0
        connection.execute(
            """
            DELETE FROM api_write_limits
            WHERE scope = ? AND bucket_key = ? AND window_start < ?
            """,
            (scope, bucket_key, window_start - (window_seconds * 2)),
        )
        if count >= limit:
            connection.commit()
            return False
        connection.execute(
            """
            INSERT INTO api_write_limits (
                scope, bucket_key, window_start, count, updated_at
            )
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(scope, bucket_key, window_start)
            DO UPDATE SET count = count + 1, updated_at = excluded.updated_at
            """,
            (scope, bucket_key, window_start, updated_at),
        )
        connection.commit()
        return True
    except Exception:
        if getattr(connection, "in_transaction", False):
            connection.rollback()
        raise


def _network_bucket_key(request: Any) -> str:
    headers = getattr(request, "headers", {})
    forwarded = str(headers.get("x-forwarded-for", "") or "").split(",", 1)[0].strip()
    client = getattr(request, "client", None)
    source = forwarded or str(getattr(client, "host", "") or "unknown")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _utc_datetime(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
