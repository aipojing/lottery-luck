from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


CREATE_ADMIN_TASKS_SQL = """
CREATE TABLE IF NOT EXISTS admin_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    provider TEXT NOT NULL,
    game_keys TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT ''
)
"""


def ensure_task_table(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_ADMIN_TASKS_SQL)


def create_task(
    connection: sqlite3.Connection,
    *,
    kind: str,
    provider: str,
    game_keys: list[str],
    payload: dict[str, Any] | None = None,
    status: str = "queued",
) -> dict[str, Any]:
    ensure_task_table(connection)
    now = _utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO admin_tasks (
            kind, provider, game_keys, payload, status, result, error, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kind,
            provider,
            _dump_json(game_keys),
            _dump_json(payload or {}),
            status,
            "{}",
            "",
            now,
        ),
    )
    connection.commit()
    task_id = int(cursor.lastrowid)
    return get_task(connection, task_id)


def mark_task_started(connection: sqlite3.Connection, task_id: int) -> dict[str, Any]:
    ensure_task_table(connection)
    connection.execute(
        """
        UPDATE admin_tasks
        SET status = ?, started_at = ?
        WHERE id = ?
        """,
        ("running", _utc_now_iso(), int(task_id)),
    )
    connection.commit()
    return get_task(connection, task_id)


def mark_task_finished(
    connection: sqlite3.Connection,
    task_id: int,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    ensure_task_table(connection)
    connection.execute(
        """
        UPDATE admin_tasks
        SET status = ?, result = ?, error = ?, finished_at = ?
        WHERE id = ?
        """,
        (status, _dump_json(result or {}), error, _utc_now_iso(), int(task_id)),
    )
    connection.commit()
    return get_task(connection, task_id)


def get_task(connection: sqlite3.Connection, task_id: int) -> dict[str, Any]:
    ensure_task_table(connection)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, kind, provider, game_keys, payload, status, result, error,
               created_at, started_at, finished_at
        FROM admin_tasks
        WHERE id = ?
        """,
        (int(task_id),),
    ).fetchone()
    if row is None:
        raise ValueError(f"task not found: {task_id}")
    return _decode_row(dict(row))


def list_tasks(connection: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    ensure_task_table(connection)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, kind, provider, game_keys, payload, status, result, error,
               created_at, started_at, finished_at
        FROM admin_tasks
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [_decode_row(dict(row)) for row in rows]


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "game_keys": _load_json(row.get("game_keys"), []),
        "payload": _load_json(row.get("payload"), {}),
        "result": _load_json(row.get("result"), {}),
    }


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: Any, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
