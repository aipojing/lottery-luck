import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from lottery_luck import plans as plan_store
from lottery_luck.plans import (
    carry_forward_plan,
    create_plan,
    delete_plan,
    get_plan,
    initialize_plan_schema,
    list_plans,
    resolve_3d_target,
    review_plan,
    update_plan,
)
from lottery_luck.repository import LotteryRepository


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _initialized_connection():
    connection = _connection()
    initialize_plan_schema(connection)
    return connection


def _plan_payload(**overrides):
    payload = {
        "game_key": "3d",
        "target_issue": "2026156",
        "target_draw_date": "2026-06-16",
        "source_type": "manual",
        "request_id": "req-1",
        "title": "稳胆复式",
        "entries": [
            {"main_numbers": [1, 2, 3], "special_numbers": [], "note": "首选"},
            {"main_numbers": [1, 1, 2], "special_numbers": [], "note": ""},
        ],
        "condition_snapshot": {
            "mode": "simple",
            "analysis_window": 30,
            "conditions_json": {
                "group_type": "组六",
                "sum_min": 5,
                "sum_max": 8,
            },
            "metrics_json": {"span": 2},
            "latest_data_issue": "2026155",
            "latest_data_date": "2026-06-15",
        },
    }
    payload.update(overrides)
    return payload


def _index_names(connection, table):
    rows = connection.execute(f"PRAGMA index_list({table})").fetchall()
    return {row["name"] for row in rows}


def _index_columns(connection, index_name):
    rows = connection.execute(f"PRAGMA index_xinfo({index_name})").fetchall()
    return [
        (row["name"], "DESC" if row["desc"] else "ASC")
        for row in rows
        if row["key"]
    ]


def _table_sql(connection, table):
    return connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()["sql"]


def _schema_snapshot(connection):
    return [
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
    ]


def _plan_rows_snapshot(connection):
    tables = [
        "lottery_plans",
        "lottery_plan_entries",
        "plan_condition_snapshots",
        "plan_reviews",
    ]
    snapshot = {}
    for table in tables:
        rows = connection.execute(
            f"SELECT * FROM {table} ORDER BY rowid"
        ).fetchall()
        snapshot[table] = [tuple(row) for row in rows]
    return snapshot


def _object_names(connection):
    return {
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'trigger')
            """
        )
    }


def _create_legacy_plan_db(
    db_path,
    *,
    main_numbers="[1,2,3]",
    conditions_json='{"group_type":"组六"}',
    metrics_json='{"span":2}',
):
    now = "2026-06-15T00:00:00+00:00"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            f"""
            PRAGMA foreign_keys = ON;
            CREATE TABLE lottery_plans (
              id TEXT PRIMARY KEY,
              client_id TEXT NOT NULL,
              game_key TEXT NOT NULL,
              target_issue TEXT NOT NULL,
              target_draw_date TEXT NOT NULL,
              source_type TEXT,
              request_id TEXT DEFAULT '',
              title TEXT NOT NULL,
              status TEXT DEFAULT 'saved',
              carried_from_plan_id TEXT REFERENCES lottery_plans(id) ON DELETE SET NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE lottery_plan_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              plan_id TEXT NOT NULL REFERENCES lottery_plans(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              main_numbers TEXT NOT NULL,
              special_numbers TEXT NOT NULL DEFAULT '[]',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              UNIQUE(plan_id, position)
            );
            CREATE TABLE plan_condition_snapshots (
              plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
              mode TEXT NOT NULL,
              window INTEGER NOT NULL,
              conditions_json TEXT NOT NULL DEFAULT '{{}}',
              metrics_json TEXT NOT NULL DEFAULT '{{}}',
              latest_data_issue TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );
            CREATE TABLE plan_reviews (
              plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
              draw_issue TEXT NOT NULL,
              draw_numbers TEXT NOT NULL,
              review_status TEXT NOT NULL,
              direct_hit INTEGER NOT NULL,
              group_type TEXT NOT NULL,
              matched_positions TEXT NOT NULL DEFAULT '[]',
              matched_conditions TEXT NOT NULL DEFAULT '[]',
              missed_conditions TEXT NOT NULL DEFAULT '[]',
              result_json TEXT NOT NULL DEFAULT '{{}}',
              reviewed_at TEXT NOT NULL
            );
            CREATE INDEX idx_lottery_plans_client_updated_id
            ON lottery_plans (client_id, updated_at, id);
            INSERT INTO lottery_plans (
                id, client_id, game_key, target_issue, target_draw_date,
                source_type, request_id, title, status, carried_from_plan_id,
                created_at, updated_at
            )
            VALUES (
                'legacy-plan', 'client-a', '3d', '2026156', '2026-06-16',
                'manual', 'legacy-request', '旧方案', 'saved', NULL,
                '{now}', '{now}'
            );
            INSERT INTO lottery_plan_entries (
                plan_id, position, main_numbers, special_numbers, note, created_at
            )
            VALUES ('legacy-plan', 0, '{main_numbers}', '[]', '旧数据', '{now}');
            INSERT INTO plan_condition_snapshots (
                plan_id, mode, window, conditions_json, metrics_json,
                latest_data_issue, created_at
            )
            VALUES (
                'legacy-plan', 'simple', 60, '{conditions_json}',
                '{metrics_json}', '2026155', '{now}'
            );
            """
        )


def test_schema_initializer_creates_required_tables_indexes_and_foreign_keys():
    connection = _initialized_connection()

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "lottery_plans",
        "lottery_plan_entries",
        "plan_condition_snapshots",
        "plan_reviews",
    } <= tables

    plan_columns = {
        row["name"]: row
        for row in connection.execute("PRAGMA table_info(lottery_plans)")
    }
    assert plan_columns["id"]["pk"] == 1
    assert plan_columns["client_id"]["notnull"] == 1
    assert plan_columns["game_key"]["notnull"] == 1
    assert plan_columns["source_type"]["notnull"] == 1
    assert plan_columns["status"]["notnull"] == 1
    assert plan_columns["request_id"]["dflt_value"] == "''"
    assert "saved" in str(plan_columns["status"]["dflt_value"])

    plan_sql = _table_sql(connection, "lottery_plans")
    entry_sql = _table_sql(connection, "lottery_plan_entries")
    snapshot_sql = _table_sql(connection, "plan_condition_snapshots")
    review_sql = _table_sql(connection, "plan_reviews")
    assert "game_key TEXT NOT NULL CHECK (game_key = '3d')" in plan_sql
    assert (
        "source_type TEXT NOT NULL CHECK (source_type IN "
        "('fortune', 'manual', 'filter', 'random', 'carried'))"
        in plan_sql
    )
    assert "status TEXT NOT NULL DEFAULT 'saved'" in plan_sql
    assert "CHECK (status IN ('draft', 'saved', 'pending_review', 'reviewed', 'expired'))" in plan_sql
    assert "special_numbers TEXT NOT NULL DEFAULT '[]'" in entry_sql
    assert "CHECK (special_numbers = '[]')" in entry_sql
    assert "mode TEXT NOT NULL CHECK (mode IN ('simple', 'pro'))" in snapshot_sql
    assert "analysis_window INTEGER NOT NULL CHECK (analysis_window IN (30, 60, 120))" in snapshot_sql
    assert "direct_hit INTEGER NOT NULL CHECK (direct_hit IN (0, 1))" in review_sql

    assert "ux_lottery_plans_client_request_id" in _index_names(
        connection,
        "lottery_plans",
    )
    assert _index_columns(connection, "idx_lottery_plans_client_updated_id") == [
        ("client_id", "ASC"),
        ("updated_at", "DESC"),
        ("id", "DESC"),
    ]
    partial_sql = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND name = 'ux_lottery_plans_client_request_id'
        """
    ).fetchone()["sql"]
    assert "WHERE request_id != ''" in partial_sql

    entry_fks = connection.execute("PRAGMA foreign_key_list(lottery_plan_entries)").fetchall()
    snapshot_fks = connection.execute(
        "PRAGMA foreign_key_list(plan_condition_snapshots)"
    ).fetchall()
    review_fks = connection.execute("PRAGMA foreign_key_list(plan_reviews)").fetchall()
    assert entry_fks[0]["table"] == "lottery_plans"
    assert entry_fks[0]["on_delete"] == "CASCADE"
    assert snapshot_fks[0]["on_delete"] == "CASCADE"
    assert review_fks[0]["on_delete"] == "CASCADE"


def test_repository_connections_enable_foreign_keys_and_initialize_plan_schema(tmp_path):
    db_path = tmp_path / "plans.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
    repo = LotteryRepository(db_path)

    repo.initialize_plan_schema()

    with repo._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        created = create_plan(connection, "client-a", _plan_payload())
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO lottery_plan_entries (
                    plan_id, position, main_numbers, special_numbers, note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "missing-plan",
                    0,
                    "[1,2,3]",
                    "[]",
                    "",
                    created["created_at"],
                ),
            )


def test_schema_initializer_migrates_wrong_plan_index_definition(tmp_path):
    db_path = tmp_path / "plans.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        initialize_plan_schema(connection)
        connection.execute("DROP INDEX idx_lottery_plans_client_updated_id")
        connection.execute(
            """
            CREATE INDEX idx_lottery_plans_client_updated_id
            ON lottery_plans (client_id, updated_at, id)
            """
        )

    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        assert _index_columns(connection, "idx_lottery_plans_client_updated_id") == [
            ("client_id", "ASC"),
            ("updated_at", "DESC"),
            ("id", "DESC"),
        ]


def test_schema_initializer_migrates_legacy_plan_tables_with_window_column(tmp_path):
    db_path = tmp_path / "legacy-plans.sqlite"
    now = "2026-06-15T00:00:00+00:00"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE lottery_plans (
              id TEXT PRIMARY KEY,
              client_id TEXT NOT NULL,
              game_key TEXT NOT NULL,
              target_issue TEXT NOT NULL,
              target_draw_date TEXT NOT NULL,
              source_type TEXT,
              request_id TEXT DEFAULT '',
              title TEXT NOT NULL,
              status TEXT DEFAULT 'saved',
              carried_from_plan_id TEXT REFERENCES lottery_plans(id) ON DELETE SET NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE lottery_plan_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              plan_id TEXT NOT NULL REFERENCES lottery_plans(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              main_numbers TEXT NOT NULL,
              special_numbers TEXT NOT NULL DEFAULT '[]',
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              UNIQUE(plan_id, position)
            );
            CREATE TABLE plan_condition_snapshots (
              plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
              mode TEXT NOT NULL,
              window INTEGER NOT NULL,
              conditions_json TEXT NOT NULL DEFAULT '{}',
              metrics_json TEXT NOT NULL DEFAULT '{}',
              latest_data_issue TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );
            CREATE TABLE plan_reviews (
              plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
              draw_issue TEXT NOT NULL,
              draw_numbers TEXT NOT NULL,
              review_status TEXT NOT NULL,
              direct_hit INTEGER NOT NULL,
              group_type TEXT NOT NULL,
              matched_positions TEXT NOT NULL DEFAULT '[]',
              matched_conditions TEXT NOT NULL DEFAULT '[]',
              missed_conditions TEXT NOT NULL DEFAULT '[]',
              result_json TEXT NOT NULL DEFAULT '{}',
              reviewed_at TEXT NOT NULL
            );
            CREATE INDEX idx_lottery_plans_client_updated_id
            ON lottery_plans (client_id, updated_at, id);
            INSERT INTO lottery_plans (
                id, client_id, game_key, target_issue, target_draw_date,
                source_type, request_id, title, status, carried_from_plan_id,
                created_at, updated_at
            )
            VALUES (
                'legacy-plan', 'client-a', '3d', '2026156', '2026-06-16',
                'manual', 'legacy-request', '旧方案', 'saved', NULL,
                '2026-06-15T00:00:00+00:00', '2026-06-15T00:00:00+00:00'
            );
            INSERT INTO lottery_plan_entries (
                plan_id, position, main_numbers, special_numbers, note, created_at
            )
            VALUES ('legacy-plan', 0, '[1,2,3]', '[9]', '旧数据', '2026-06-15T00:00:00+00:00');
            INSERT INTO plan_condition_snapshots (
                plan_id, mode, window, conditions_json, metrics_json,
                latest_data_issue, created_at
            )
            VALUES (
                'legacy-plan', 'simple', 60, '{"group_type":"组六"}',
                '{"span":2}', '2026155', '2026-06-15T00:00:00+00:00'
            );
            """
        )

    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        plan_columns = {
            row["name"]: row
            for row in connection.execute("PRAGMA table_info(lottery_plans)")
        }
        snapshot_columns = {
            row["name"]: row
            for row in connection.execute("PRAGMA table_info(plan_condition_snapshots)")
        }
        assert plan_columns["source_type"]["notnull"] == 1
        assert "analysis_window" in snapshot_columns
        assert "window" not in snapshot_columns
        assert snapshot_columns["latest_data_date"]["notnull"] == 1
        assert _index_columns(connection, "idx_lottery_plans_client_updated_id") == [
            ("client_id", "ASC"),
            ("updated_at", "DESC"),
            ("id", "DESC"),
        ]

        fetched = get_plan(connection, "client-a", "legacy-plan")
        assert fetched["source_type"] == "manual"
        assert fetched["entries"][0]["main_numbers"] == [1, 2, 3]
        assert fetched["entries"][0]["special_numbers"] == []
        assert fetched["condition_snapshot"]["analysis_window"] == 60
        assert fetched["condition_snapshot"]["latest_data_date"] == ""
        assert (
            connection.execute(
                """
                SELECT special_numbers
                FROM lottery_plan_entries
                WHERE plan_id = 'legacy-plan'
                """
            ).fetchone()["special_numbers"]
            == "[]"
        )

        updated = update_plan(connection, "client-a", "legacy-plan", {"title": "迁移后可更新"})
        assert updated["title"] == "迁移后可更新"
        created = create_plan(
            connection,
            "client-a",
            _plan_payload(request_id="after-migration", title="迁移后新增"),
        )
        reviewed = review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
        )
        assert reviewed["review"]["direct_hit"] is True


def test_schema_initializer_migrates_entries_table_missing_special_numbers_check(tmp_path):
    db_path = tmp_path / "legacy-entry-check.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        initialize_plan_schema(connection)
        created = create_plan(connection, "client-a", _plan_payload())
        connection.execute("ALTER TABLE lottery_plan_entries RENAME TO old_entries")
        connection.execute(
            """
            CREATE TABLE lottery_plan_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              plan_id TEXT NOT NULL REFERENCES lottery_plans(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              main_numbers TEXT NOT NULL,
              special_numbers TEXT NOT NULL DEFAULT '[]',
              note TEXT NOT NULL DEFAULT '' CHECK (length(note) <= 120),
              created_at TEXT NOT NULL,
              UNIQUE(plan_id, position)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO lottery_plan_entries (
                id, plan_id, position, main_numbers, special_numbers, note, created_at
            )
            SELECT id, plan_id, position, main_numbers, '[9]', note, created_at
            FROM old_entries
            """
        )
        connection.execute("DROP TABLE old_entries")

    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        assert "CHECK (special_numbers = '[]')" in _table_sql(
            connection,
            "lottery_plan_entries",
        )
        fetched = get_plan(connection, "client-a", created["id"])
        assert fetched["entries"][0]["special_numbers"] == []

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO lottery_plan_entries (
                    plan_id, position, main_numbers, special_numbers, note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    created["id"],
                    99,
                    "[1,2,3]",
                    "[9]",
                    "",
                    created["created_at"],
                ),
            )


@pytest.mark.parametrize(
    "legacy_overrides",
    [
        {"main_numbers": "[1,2]"},
        {"main_numbers": "[1,2,true]"},
        {"conditions_json": "[]"},
        {"metrics_json": "{bad"},
    ],
)
def test_schema_initializer_rolls_back_invalid_legacy_json_without_residue(
    tmp_path,
    legacy_overrides,
):
    db_path = tmp_path / "legacy-invalid.sqlite"
    _create_legacy_plan_db(db_path, **legacy_overrides)
    before_bytes = db_path.read_bytes()
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        before_schema = _schema_snapshot(connection)
        before_rows = _plan_rows_snapshot(connection)

    repo = LotteryRepository(db_path)
    for _attempt in range(2):
        with pytest.raises(ValueError, match="invalid plan"):
            repo.initialize_plan_schema()
        assert db_path.read_bytes() == before_bytes
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            assert _schema_snapshot(connection) == before_schema
            assert _plan_rows_snapshot(connection) == before_rows
            assert not any(
                name.startswith("__old_") or name.startswith("__new_")
                for name in _object_names(connection)
            )
            assert (
                connection.execute(
                    "SELECT main_numbers FROM lottery_plan_entries WHERE plan_id = 'legacy-plan'"
                ).fetchone()["main_numbers"]
                == legacy_overrides.get("main_numbers", "[1,2,3]")
            )


def test_database_rejects_nonempty_special_numbers_raw_insert():
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO lottery_plan_entries (
                plan_id, position, main_numbers, special_numbers, note, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                created["id"],
                99,
                "[1,2,3]",
                "[9]",
                "",
                created["created_at"],
            ),
        )


@pytest.mark.parametrize(
    ("column", "stored_value"),
    [
        ("main_numbers", "[]"),
        ("main_numbers", "[1,2]"),
        ("main_numbers", "[1,2,true]"),
        ("main_numbers", "{bad"),
    ],
)
def test_hydrate_rejects_corrupt_stored_entry_numbers_generically(column, stored_value):
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())
    connection.execute(
        f"UPDATE lottery_plan_entries SET {column} = ? WHERE plan_id = ? AND position = 0",
        (stored_value, created["id"]),
    )

    with pytest.raises(ValueError, match="invalid plan"):
        get_plan(connection, "client-a", created["id"])
    with pytest.raises(ValueError, match="invalid plan"):
        review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
        )


@pytest.mark.parametrize(
    ("column", "stored_value"),
    [
        ("conditions_json", "[]"),
        ("conditions_json", "{bad"),
        ("metrics_json", "[]"),
        ("metrics_json", "{bad"),
    ],
)
def test_hydrate_rejects_corrupt_stored_snapshot_json_generically(column, stored_value):
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())
    connection.execute(
        f"UPDATE plan_condition_snapshots SET {column} = ? WHERE plan_id = ?",
        (stored_value, created["id"]),
    )

    with pytest.raises(ValueError, match="invalid plan"):
        get_plan(connection, "client-a", created["id"])
    with pytest.raises(ValueError, match="invalid plan"):
        review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
        )


def test_create_get_list_update_and_delete_plan_with_decoded_children():
    connection = _initialized_connection()

    created = create_plan(connection, " client-a ", _plan_payload())
    fetched = get_plan(connection, "client-a", created["id"])

    assert created["id"]
    assert created["client_id"] == "client-a"
    assert created["status"] == "saved"
    assert created["duplicate_warning"] is False
    assert created["entries"][0]["position"] == 0
    assert created["entries"][0]["main_numbers"] == [1, 2, 3]
    assert created["entries"][0]["special_numbers"] == []
    assert fetched == created
    assert datetime.fromisoformat(created["created_at"]).tzinfo == timezone.utc

    updated = update_plan(
        connection,
        "client-a",
        created["id"],
        {
            "title": "更新方案",
            "status": "pending_review",
            "entries": [
                {"main_numbers": [9, 9, 9], "note": "豹子"},
            ],
            "condition_snapshot": {
                "mode": "pro",
                "analysis_window": 60,
                "conditions_json": {"group_type": "豹子"},
                "metrics_json": {"sum": 27},
                "latest_data_issue": "2026156",
                "latest_data_date": "2026-06-16",
            },
        },
    )

    assert updated["title"] == "更新方案"
    assert updated["status"] == "pending_review"
    assert updated["game_key"] == "3d"
    assert updated["target_issue"] == "2026156"
    assert updated["source_type"] == "manual"
    assert updated["carried_from_plan_id"] is None
    assert updated["entries"] == [
        {
            "id": updated["entries"][0]["id"],
            "plan_id": created["id"],
            "position": 0,
            "main_numbers": [9, 9, 9],
            "special_numbers": [],
            "note": "豹子",
            "created_at": updated["entries"][0]["created_at"],
        }
    ]
    assert updated["condition_snapshot"]["mode"] == "pro"
    assert updated["condition_snapshot"]["metrics_json"] == {"sum": 27}
    assert updated["updated_at"] > created["updated_at"]
    assert list_plans(connection, "client-a", limit=10) == [updated]

    assert delete_plan(connection, "client-a", created["id"]) is True
    assert get_plan(connection, "client-a", created["id"]) is None


def test_all_reads_and_writes_are_scoped_by_client_without_existence_leak():
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())

    assert get_plan(connection, "client-b", created["id"]) is None
    assert list_plans(connection, "client-b") == []
    assert update_plan(connection, "client-b", created["id"], {"title": "偷看"}) is None
    assert update_plan(connection, "client-b", created["id"], {"title": "x" * 81}) is None
    assert delete_plan(connection, "client-b", created["id"]) is False
    assert (
        review_plan(
            connection,
            "client-b",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
        )
        is None
    )
    assert get_plan(connection, "client-a", created["id"])["title"] == "稳胆复式"


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "target_issue",
        "source_type",
        "request_id",
        "carried_from_plan_id",
        "game_key",
    ],
)
def test_update_plan_rejects_non_allowed_keys_generically_without_existence_leak(forbidden_key):
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())

    for client_id, plan_id in [
        ("client-a", created["id"]),
        ("client-b", created["id"]),
        ("client-a", "missing-plan"),
    ]:
        with pytest.raises(ValueError, match="invalid plan") as exc_info:
            update_plan(connection, client_id, plan_id, {forbidden_key: "secret-value"})
        assert "secret-value" not in str(exc_info.value)
        assert created["id"] not in str(exc_info.value)

    assert get_plan(connection, "client-a", created["id"])["title"] == "稳胆复式"


@pytest.mark.parametrize(
    "payload",
    [
        _plan_payload(game_key="ssq"),
        _plan_payload(title="x" * 81),
        _plan_payload(source_type="outside"),
        _plan_payload(entries=[]),
        _plan_payload(entries=[{"main_numbers": [1, 2]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, 10]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, "3"]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, 3.0]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, True]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, 3], "special_numbers": [4]}]),
        _plan_payload(entries=[{"main_numbers": [1, 2, 3], "note": "隐私" * 121}]),
        _plan_payload(condition_snapshot={"mode": "deep", "analysis_window": 30}),
        _plan_payload(condition_snapshot={"mode": "simple", "analysis_window": 90}),
        _plan_payload(condition_snapshot={"mode": "simple", "analysis_window": 30, "conditions_json": {"x": {"y": {"z": {"a": {"b": {"c": {"d": {"e": 1}}}}}}}}}),
    ],
)
def test_create_rejects_invalid_payloads_with_generic_message_without_echo(payload):
    connection = _initialized_connection()

    with pytest.raises(ValueError, match="invalid plan") as exc_info:
        create_plan(connection, "client-a", payload)

    message = str(exc_info.value)
    assert "隐私" not in message
    assert "outside" not in message
    assert list_plans(connection, "client-a") == []


def test_nonempty_request_id_is_idempotent_per_client_but_empty_request_id_is_not():
    connection = _initialized_connection()
    first = create_plan(connection, "client-a", _plan_payload(request_id="req-same"))
    retry = create_plan(connection, "client-a", _plan_payload(request_id="req-same"))
    other_client = create_plan(connection, "client-b", _plan_payload(request_id="req-same"))
    blank_one = create_plan(connection, "client-a", _plan_payload(request_id=""))
    blank_two = create_plan(connection, "client-a", _plan_payload(request_id=""))

    assert retry == first
    assert other_client["id"] != first["id"]
    assert blank_one["id"] != blank_two["id"]
    assert len(list_plans(connection, "client-a", limit=100)) == 3
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM lottery_plan_entries WHERE plan_id = ?",
            (first["id"],),
        ).fetchone()[0]
        == 2
    )


def test_carried_from_plan_id_is_client_scoped_and_errors_are_generic():
    connection = _initialized_connection()
    source = create_plan(connection, "client-a", _plan_payload(request_id="source"))
    create_plan(connection, "client-b", _plan_payload(request_id="other-source"))

    carried = create_plan(
        connection,
        "client-a",
        _plan_payload(
            request_id="carried-ok",
            title="同 client carry",
            source_type="carried",
            carried_from_plan_id=source["id"],
        ),
    )
    assert carried["carried_from_plan_id"] == source["id"]

    for carried_from_plan_id in ["missing-plan", source["id"]]:
        with pytest.raises(ValueError, match="invalid plan") as exc_info:
            create_plan(
                connection,
                "client-b",
                _plan_payload(
                    request_id=f"bad-{carried_from_plan_id}",
                    title="跨 client carry",
                    source_type="carried",
                    carried_from_plan_id=carried_from_plan_id,
                ),
            )
        assert carried_from_plan_id not in str(exc_info.value)

    assert connection.execute("SELECT COUNT(*) FROM lottery_plans").fetchone()[0] == 3


def test_database_rejects_cross_client_carried_from_plan_id():
    connection = _initialized_connection()
    now = "2026-06-15T00:00:00+00:00"
    source = create_plan(connection, "client-a", _plan_payload(request_id="source"))

    with pytest.raises(sqlite3.IntegrityError):
        with connection:
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
                    "raw-cross-client",
                    "client-b",
                    "3d",
                    "2026157",
                    "2026-06-17",
                    "carried",
                    "raw-cross-client",
                    "raw",
                    "saved",
                    source["id"],
                    now,
                    now,
                ),
            )


def test_duplicate_entries_warn_but_are_allowed_when_not_idempotent():
    connection = _initialized_connection()
    first = create_plan(connection, "client-a", _plan_payload(request_id=""))
    duplicate = create_plan(connection, "client-a", _plan_payload(request_id="", title="副本"))

    assert duplicate["id"] != first["id"]
    assert duplicate["duplicate_warning"] is True
    assert len(list_plans(connection, "client-a", limit=100)) == 2


def test_duplicate_warning_uses_same_client_source_and_exact_entries_across_targets():
    connection = _initialized_connection()
    first = create_plan(connection, "client-a", _plan_payload(request_id="", source_type="manual"))
    different_target = create_plan(
        connection,
        "client-a",
        _plan_payload(
            request_id="",
            title="不同目标期",
            target_issue="2026157",
            target_draw_date="2026-06-17",
            source_type="manual",
        ),
    )
    different_source = create_plan(
        connection,
        "client-a",
        _plan_payload(
            request_id="",
            title="不同来源",
            target_issue="2026158",
            target_draw_date="2026-06-18",
            source_type="random",
        ),
    )
    other_client = create_plan(
        connection,
        "client-b",
        _plan_payload(
            request_id="",
            title="不同 client",
            target_issue="2026159",
            target_draw_date="2026-06-19",
            source_type="manual",
        ),
    )

    assert first["duplicate_warning"] is False
    assert different_target["duplicate_warning"] is True
    assert different_source["duplicate_warning"] is False
    assert other_client["duplicate_warning"] is False


def test_delete_cascades_entries_snapshot_and_review():
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())
    review_plan(
        connection,
        "client-a",
        created["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
    )

    delete_plan(connection, "client-a", created["id"])

    assert connection.execute("SELECT COUNT(*) FROM lottery_plan_entries").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM plan_condition_snapshots").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM plan_reviews").fetchone()[0] == 0


def test_create_and_update_roll_back_atomically_on_child_validation_failure():
    connection = _initialized_connection()
    with pytest.raises(ValueError, match="invalid plan"):
        create_plan(
            connection,
            "client-a",
            _plan_payload(
                entries=[
                    {"main_numbers": [1, 2, 3]},
                    {"main_numbers": [9, 9, 99]},
                ]
            ),
        )
    assert connection.execute("SELECT COUNT(*) FROM lottery_plans").fetchone()[0] == 0

    created = create_plan(connection, "client-a", _plan_payload())
    with pytest.raises(ValueError, match="invalid plan"):
        update_plan(
            connection,
            "client-a",
            created["id"],
            {"title": "坏更新", "entries": [{"main_numbers": [1, 2, 99]}]},
        )
    assert get_plan(connection, "client-a", created["id"])["title"] == "稳胆复式"
    assert len(get_plan(connection, "client-a", created["id"])["entries"]) == 2


def test_review_plan_scores_exact_partial_repeats_and_snapshot_conditions():
    connection = _initialized_connection()
    created = create_plan(
        connection,
        "client-a",
        _plan_payload(
            entries=[
                {"main_numbers": [1, 2, 3]},
                {"main_numbers": [2, 2, 1]},
                {"main_numbers": [9, 9, 9]},
            ],
            condition_snapshot={
                "mode": "pro",
                "analysis_window": 120,
                "conditions_json": {
                    "group_type": "组三",
                    "sum_min": 4,
                    "sum_max": 6,
                    "position_0": 2,
                },
                "metrics_json": {"span": 1, "sum": 5},
                "latest_data_issue": "2026155",
                "latest_data_date": "2026-06-15",
            },
        ),
    )

    reviewed = review_plan(
        connection,
        "client-a",
        created["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [2, 2, 1]},
    )

    assert reviewed["status"] == "reviewed"
    assert reviewed["review"]["draw_numbers"] == [2, 2, 1]
    assert reviewed["review"]["direct_hit"] is True
    assert reviewed["review"]["group_type"] == "组三"
    assert reviewed["review"]["matched_positions"] == [0, 1, 2]
    assert reviewed["review"]["matched_conditions"] == [
        "conditions.group_type",
        "conditions.sum_min",
        "conditions.sum_max",
        "conditions.position_0",
        "metrics.span",
        "metrics.sum",
    ]
    assert reviewed["review"]["missed_conditions"] == []
    entries = reviewed["review"]["result_json"]["entries"]
    assert entries[0]["direct_hit"] is False
    assert entries[0]["matched_positions"] == [1]
    assert entries[0]["any_position_hits"] == [1, 2]
    assert entries[1]["direct_hit"] is True
    assert entries[1]["matched_positions"] == [0, 1, 2]
    assert entries[1]["any_position_hits"] == [2, 2, 1]
    assert entries[2]["any_position_hits"] == []


def test_review_plan_rejects_mismatch_missing_and_conflicting_second_draw_generically():
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())

    with pytest.raises(ValueError, match="invalid review") as mismatch:
        review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026999", "draw_date": "2026-06-16", "main": [1, 2, 3]},
        )
    assert "2026999" not in str(mismatch.value)

    with pytest.raises(ValueError, match="invalid review"):
        review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16"},
        )

    reviewed = review_plan(
        connection,
        "client-a",
        created["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
    )
    retry = review_plan(
        connection,
        "client-a",
        created["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "draw_numbers": [1, 2, 3]},
    )
    assert retry == reviewed

    with pytest.raises(ValueError, match="invalid review"):
        review_plan(
            connection,
            "client-a",
            created["id"],
            {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 4]},
        )


@pytest.mark.parametrize(
    "draw",
    [
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, "3"]},
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3.0]},
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, True]},
        {"issue": "2026156", "draw_date": "2026-06-16", "draw_numbers": [1, 2, "3"]},
        {"issue": "2026156", "draw_date": "2026-06-16", "red_numbers": "1,2,3.0"},
    ],
)
def test_review_plan_rejects_non_int_draw_number_items(draw):
    connection = _initialized_connection()
    created = create_plan(connection, "client-a", _plan_payload())

    with pytest.raises(ValueError, match="invalid review"):
        review_plan(connection, "client-a", created["id"], draw)


def test_review_plan_accepts_repository_shaped_red_numbers_for_review_and_carry():
    connection = _initialized_connection()
    old = create_plan(connection, "client-a", _plan_payload())
    repository_draw = {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": "2026156",
        "draw_date": "2026-06-16",
        "week": "二",
        "red_numbers": "1,2,3",
        "blue_number": "",
        "sales": "",
        "pool_money": "",
        "content": "",
    }

    reviewed = review_plan(connection, "client-a", old["id"], repository_draw)
    carried = carry_forward_plan(connection, "client-a", old["id"], repository_draw)

    assert reviewed["review"]["draw_numbers"] == [1, 2, 3]
    assert carried["target_issue"] == "2026157"
    assert carried["carried_from_plan_id"] == old["id"]


def test_repository_red_numbers_draw_can_review_and_carry_plan(tmp_path):
    db_path = tmp_path / "repo-draw.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (
              game_key TEXT,
              game_name TEXT,
              issue TEXT,
              draw_date TEXT,
              week TEXT,
              red_numbers TEXT,
              blue_number TEXT,
              sales TEXT,
              pool_money TEXT,
              content TEXT,
              PRIMARY KEY(game_key, issue)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO draws (
                game_key, game_name, issue, draw_date, week, red_numbers,
                blue_number, sales, pool_money, content
            )
            VALUES ('3d', '福彩3D', '2026156', '2026-06-16', '二', '1,2,3', '', '', '', '')
            """
        )
    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()
    plan = repo.create_plan("client-a", _plan_payload())
    draw = repo.recent_draws("3d", limit=1)[0]

    reviewed = repo.review_plan("client-a", plan["id"], draw)
    carried = repo.carry_forward_plan("client-a", plan["id"], draw)

    assert reviewed["review"]["draw_numbers"] == [1, 2, 3]
    assert carried["target_issue"] == "2026157"


def test_concurrent_same_review_is_idempotent_without_sqlite_errors(tmp_path, monkeypatch):
    db_path = tmp_path / "review-race.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()
    created = repo.create_plan("client-a", _plan_payload())
    draw = {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]}

    worker_count = 30
    barrier = threading.Barrier(worker_count)
    seen_threads: set[int] = set()
    seen_lock = threading.Lock()
    original_get_review = plan_store._get_review

    def gated_get_review(connection, plan_id):
        review = original_get_review(connection, plan_id)
        if review is None:
            thread_id = threading.get_ident()
            should_wait = False
            with seen_lock:
                if thread_id not in seen_threads:
                    seen_threads.add(thread_id)
                    should_wait = True
            if should_wait:
                barrier.wait(timeout=10)
        return review

    monkeypatch.setattr(plan_store, "_get_review", gated_get_review)

    def review_once(_index):
        return repo.review_plan("client-a", created["id"], draw)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(review_once, range(worker_count)))

    assert len({result["review"]["reviewed_at"] for result in results}) == 1
    assert all(result["review"]["draw_numbers"] == [1, 2, 3] for result in results)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM plan_reviews").fetchone()[0] == 1


def test_carry_forward_clones_entries_snapshot_and_keeps_old_plan_immutable():
    connection = _initialized_connection()
    old = create_plan(connection, "client-a", _plan_payload())
    reviewed_old = review_plan(
        connection,
        "client-a",
        old["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
    )

    carried = carry_forward_plan(
        connection,
        "client-a",
        old["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
    )
    retry = carry_forward_plan(
        connection,
        "client-a",
        old["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "draw_numbers": [1, 2, 3]},
    )

    assert carried == retry
    assert carried["id"] != old["id"]
    assert carried["source_type"] == "carried"
    assert carried["carried_from_plan_id"] == old["id"]
    assert carried["target_issue"] == "2026157"
    assert carried["target_draw_date"] == "2026-06-17"
    assert carried["entries"][0]["main_numbers"] == old["entries"][0]["main_numbers"]
    assert carried["condition_snapshot"]["conditions_json"] == old["condition_snapshot"]["conditions_json"]
    assert carried["review"] is None
    assert get_plan(connection, "client-a", old["id"]) == reviewed_old


def test_resolve_3d_target_increments_future_offsets_cross_year_and_rejects_past():
    assert resolve_3d_target("2026155", "2026-06-15") == {
        "target_issue": "2026156",
        "target_draw_date": "2026-06-16",
    }
    assert resolve_3d_target("2026155", "2026-06-15", "2026-06-18") == {
        "target_issue": "2026158",
        "target_draw_date": "2026-06-18",
    }
    assert resolve_3d_target("2026365", "2026-12-31") == {
        "target_issue": "2027001",
        "target_draw_date": "2027-01-01",
    }
    assert resolve_3d_target("2026365", "2026-12-31", "2027-01-02") == {
        "target_issue": "2027002",
        "target_draw_date": "2027-01-02",
    }
    with pytest.raises(ValueError, match="invalid target"):
        resolve_3d_target("2026155", "2026-06-15", "2026-06-15")


def test_list_orders_newest_first_and_clamps_limits():
    connection = _initialized_connection()
    first = create_plan(connection, "client-a", _plan_payload(request_id="", title="first"))
    second = create_plan(connection, "client-a", _plan_payload(request_id="", title="second"))
    third = create_plan(connection, "client-a", _plan_payload(request_id="", title="third"))

    assert [plan["id"] for plan in list_plans(connection, "client-a", limit=2)] == [
        third["id"],
        second["id"],
    ]
    assert [plan["id"] for plan in list_plans(connection, "client-a", limit=0)] == [
        third["id"]
    ]
    assert len(list_plans(connection, "client-a", limit=500)) == 3
    assert first["updated_at"] < second["updated_at"] < third["updated_at"]


def test_crud_hot_paths_do_not_run_schema_ddl():
    connection = _initialized_connection()
    statements = []
    connection.set_trace_callback(statements.append)

    created = create_plan(connection, "client-a", _plan_payload())
    list_plans(connection, "client-a")
    get_plan(connection, "client-a", created["id"])
    update_plan(connection, "client-a", created["id"], {"title": "新标题"})
    review_plan(
        connection,
        "client-a",
        created["id"],
        {"issue": "2026156", "draw_date": "2026-06-16", "main": [1, 2, 3]},
    )
    delete_plan(connection, "client-a", created["id"])

    schema_statements = [
        statement
        for statement in statements
        if "CREATE " in statement.upper() or "DROP " in statement.upper()
    ]
    assert schema_statements == []


def test_create_plan_does_not_initialize_missing_schema_on_hot_path():
    connection = _connection()

    with pytest.raises(sqlite3.OperationalError):
        create_plan(connection, "client-a", _plan_payload())

    assert (
        connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'lottery_plans'
            """
        ).fetchone()
        is None
    )


def test_repository_concurrent_idempotent_create_returns_one_plan(tmp_path):
    db_path = tmp_path / "plans.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()

    def save_once(_index):
        return repo.create_plan("client-a", _plan_payload(request_id="double-click"))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(save_once, range(30)))

    assert len({result["id"] for result in results}) == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM lottery_plans").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM lottery_plan_entries").fetchone()[0] == 2
