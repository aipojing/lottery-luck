import sqlite3

import pytest

from lottery_luck import database


class FakeLibsqlCursor:
    def __init__(self, rows=(), description=(), *, lastrowid=None, rowcount=-1):
        self._rows = list(rows)
        self.description = description
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows


class FakeLibsqlConnection:
    def __init__(self):
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.executed = []
        self._in_transaction = False

    @property
    def row_factory(self):
        raise NotImplementedError("libSQL row_factory is not implemented")

    @row_factory.setter
    def row_factory(self, value):
        raise NotImplementedError("libSQL row_factory is not implemented")

    @property
    def in_transaction(self):
        return self._in_transaction

    def execute(self, sql, parameters=()):
        self.executed.append((sql, parameters))
        if sql == "SELECT one":
            return FakeLibsqlCursor(
                rows=[("game-a", 3), ("game-b", 5)],
                description=(("game_key",), ("draw_count",)),
            )
        if sql == "SELECT empty":
            return FakeLibsqlCursor(description=(("value",),))
        if sql == "INSERT row":
            self._in_transaction = True
            return FakeLibsqlCursor(lastrowid=42, rowcount=1)
        return FakeLibsqlCursor()

    def cursor(self):
        return self

    def commit(self):
        self.committed = True
        self._in_transaction = False

    def rollback(self):
        self.rolled_back = True
        self._in_transaction = False

    def close(self):
        self.closed = True


def test_connect_database_uses_explicit_sqlite_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://ignored.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "ignored-token")

    connection = database.connect_database(tmp_path / "local.sqlite")
    try:
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_implicit_local_database_uses_runtime_copy_without_mutating_seed(
    tmp_path, monkeypatch
):
    seed_path = tmp_path / "seed.sqlite"
    runtime_path = tmp_path / ".runtime" / "lottery.sqlite"
    with sqlite3.connect(seed_path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('seed')")

    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(database, "DB_PATH", seed_path)
    monkeypatch.setattr(database, "LOCAL_RUNTIME_DB_PATH", runtime_path)

    with database.connect_database() as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "seed"
        connection.execute("INSERT INTO marker VALUES ('runtime')")

    with sqlite3.connect(seed_path) as connection:
        assert connection.execute("SELECT value FROM marker").fetchall() == [("seed",)]
    with sqlite3.connect(runtime_path) as connection:
        assert connection.execute("SELECT value FROM marker").fetchall() == [
            ("seed",),
            ("runtime",),
        ]


def test_connect_database_uses_libsql_for_implicit_production_connection(monkeypatch):
    calls = []

    class FakeLibsql:
        @staticmethod
        def connect(*, database, auth_token):
            calls.append((database, auth_token))
            return FakeLibsqlConnection()

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(database, "_load_libsql", lambda: FakeLibsql)

    connection = database.connect_database()

    assert calls[0] == ("libsql://lottery.turso.io", "secret-token")
    assert connection.row_factory is sqlite3.Row


def test_remote_connection_adapts_tuple_rows_to_sqlite_row_api(monkeypatch):
    raw_connection = FakeLibsqlConnection()

    class FakeLibsql:
        @staticmethod
        def connect(*, database, auth_token):
            return raw_connection

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(database, "_load_libsql", lambda: FakeLibsql)

    with database.connect_database() as connection:
        cursor = connection.execute("SELECT one")
        first = cursor.fetchone()
        assert first["game_key"] == "game-a"
        assert first[1] == 3
        assert dict(first) == {"game_key": "game-a", "draw_count": 3}

        assert [row["draw_count"] for row in cursor] == [5]
        assert connection.execute("SELECT one").fetchall()[0]["game_key"] == "game-a"
        assert connection.execute("SELECT empty").fetchone() is None

        write_cursor = connection.execute("INSERT row")
        assert write_cursor.lastrowid == 42
        assert write_cursor.rowcount == 1
        assert connection.in_transaction is True

    assert raw_connection.committed is True
    assert raw_connection.closed is True


def test_remote_cursor_iteration_supports_fetch_only_libsql_cursor():
    class FetchOnlyCursor:
        description = (("game_key",), ("draw_count",))

        def __init__(self):
            self.rows = [("game-a", 3), ("game-b", 5)]

        def fetchone(self):
            if not self.rows:
                return None
            return self.rows.pop(0)

    cursor = database.RemoteCursor(FetchOnlyCursor())

    assert [(row["game_key"], row["draw_count"]) for row in cursor] == [
        ("game-a", 3),
        ("game-b", 5),
    ]


def test_remote_connection_context_manager_rolls_back_and_closes(monkeypatch):
    raw_connection = FakeLibsqlConnection()

    class FakeLibsql:
        @staticmethod
        def connect(*, database, auth_token):
            return raw_connection

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(database, "_load_libsql", lambda: FakeLibsql)

    connection = database.connect_database()
    with pytest.raises(ValueError, match="boom"):
        with connection:
            connection.execute("INSERT row")
            raise ValueError("boom")

    assert raw_connection.rolled_back is True
    assert raw_connection.closed is True


def test_remote_database_requires_token(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TURSO_AUTH_TOKEN"):
        database.connect_database()
