from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH, TURSO_AUTH_TOKEN_ENV, TURSO_DATABASE_URL_ENV


def _load_libsql():
    import libsql

    return libsql


def remote_database_enabled() -> bool:
    return bool(os.environ.get(TURSO_DATABASE_URL_ENV, "").strip())


class RemoteRow:
    def __init__(self, columns: tuple[str, ...], values: tuple[Any, ...]):
        self._columns = columns
        self._values = values
        self._index = {column: index for index, column in enumerate(columns)}
        self._case_index = {
            column.lower(): index for index, column in reversed(list(enumerate(columns)))
        }

    def __getitem__(self, key: int | str | slice) -> Any:
        if isinstance(key, str):
            try:
                return self._values[self._index[key]]
            except KeyError:
                try:
                    return self._values[self._case_index[key.lower()]]
                except KeyError as exc:
                    raise IndexError(f"No item with that key: {key}") from exc
        return self._values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self) -> list[str]:
        return list(self._columns)


class RemoteCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    @property
    def description(self) -> Any:
        return getattr(self._cursor, "description", None)

    @property
    def lastrowid(self) -> Any:
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self) -> int:
        return int(getattr(self._cursor, "rowcount", -1) or 0)

    def execute(self, sql: str, parameters: Any = ()) -> "RemoteCursor":
        result = self._cursor.execute(sql, parameters)
        if result is not None:
            self._cursor = result
        return self

    def executemany(self, sql: str, parameters: Any) -> "RemoteCursor":
        result = self._cursor.executemany(sql, parameters)
        if result is not None:
            self._cursor = result
        return self

    def fetchone(self) -> RemoteRow | None:
        return self._adapt_row(self._cursor.fetchone())

    def fetchall(self) -> list[RemoteRow]:
        return [self._adapt_row(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size: int | None = None) -> list[RemoteRow]:
        if size is None:
            rows = self._cursor.fetchmany()
        else:
            rows = self._cursor.fetchmany(size)
        return [self._adapt_row(row) for row in rows]

    def close(self) -> None:
        close = getattr(self._cursor, "close", None)
        if close is not None:
            close()

    def __iter__(self) -> Iterator[RemoteRow]:
        for row in self._cursor:
            yield self._adapt_row(row)

    def __enter__(self) -> "RemoteCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    def _adapt_row(self, row: Any) -> RemoteRow | None:
        if row is None:
            return None
        if isinstance(row, RemoteRow):
            return row
        return RemoteRow(self._columns(), tuple(row))

    def _columns(self) -> tuple[str, ...]:
        description = self.description or ()
        columns: list[str] = []
        for item in description:
            if isinstance(item, str):
                columns.append(item)
            elif isinstance(item, (tuple, list)) and item:
                columns.append(str(item[0]))
            elif hasattr(item, "name"):
                columns.append(str(item.name))
            else:
                columns.append(str(item))
        return tuple(columns)


class RemoteConnection:
    def __init__(self, connection: Any):
        self._connection = connection
        self.row_factory = sqlite3.Row

    @property
    def in_transaction(self) -> bool:
        return bool(getattr(self._connection, "in_transaction", False))

    def execute(self, sql: str, parameters: Any = ()) -> RemoteCursor:
        return RemoteCursor(self._connection.execute(sql, parameters))

    def executemany(self, sql: str, parameters: Any) -> RemoteCursor:
        return RemoteCursor(self._connection.executemany(sql, parameters))

    def cursor(self) -> RemoteCursor:
        return RemoteCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "RemoteConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def connect_database(db_path: Path | str | None = None) -> Any:
    if db_path is not None or not remote_database_enabled():
        target = Path(db_path) if db_path is not None else DB_PATH
        if db_path is None and not target.exists():
            raise FileNotFoundError(target)
        connection = sqlite3.connect(target, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    url = os.environ[TURSO_DATABASE_URL_ENV].strip()
    token = os.environ.get(TURSO_AUTH_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(
            f"{TURSO_AUTH_TOKEN_ENV} is required when {TURSO_DATABASE_URL_ENV} is set"
        )
    connection = RemoteConnection(_load_libsql().connect(database=url, auth_token=token))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
