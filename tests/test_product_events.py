import json
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from lottery_luck import product_events
from lottery_luck.product_events import (
    ensure_product_events_table,
    prune_product_events,
    record_event,
)
from lottery_luck.repository import LotteryRepository


ALLOWED_EVENT_NAMES = [
    "prediction_completed",
    "plan_saved",
    "workbench_opened",
    "plan_edited",
    "review_viewed",
    "plan_carried_forward",
    "tool_opened",
    "tool_result_generated",
]

TOOL_KEYS = [
    "trend",
    "omission",
    "frequency",
    "heat",
    "number",
    "attributes",
    "reduction",
    "recent",
]


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def _initialized_connection():
    connection = _connection()
    ensure_product_events_table(connection)
    return connection


@pytest.fixture
def connection():
    return _initialized_connection()


def _all_rows(connection):
    rows = connection.execute(
        """
        SELECT client_id, event_name, properties, occurred_at
        FROM product_events
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _index_names(connection):
    indexes = connection.execute("PRAGMA index_list(product_events)").fetchall()
    return {row["name"] for row in indexes}


def _index_columns(connection, index_name):
    rows = connection.execute(f"PRAGMA index_info({index_name})").fetchall()
    return [row["name"] for row in rows]


def _index_key_directions(connection, index_name):
    rows = connection.execute(f"PRAGMA index_xinfo({index_name})").fetchall()
    return [
        (row["name"], "DESC" if row["desc"] else "ASC")
        for row in rows
        if row["key"]
    ]


def _assert_current_product_event_index(connection):
    assert _index_names(connection) == {"idx_product_events_client_time"}
    assert _index_columns(connection, "idx_product_events_client_time") == [
        "client_id",
        "occurred_at",
        "id",
    ]
    assert _index_key_directions(connection, "idx_product_events_client_time") == [
        ("client_id", "ASC"),
        ("occurred_at", "DESC"),
        ("id", "DESC"),
    ]


def test_record_event_persists_allowed_event_with_decoded_properties_and_schema():
    connection = _initialized_connection()

    event = record_event(
        connection,
        client_id="  client-a  ",
        event_name="prediction_completed",
        properties={
            "game_key": "ssq",
            "source_type": "fortune",
            "entry_count": 2,
            "candidate_count": 5,
            "review_status": None,
            "freshness_status": "fresh",
        },
    )

    assert event["id"] == 1
    assert event["client_id"] == "client-a"
    assert event["event_name"] == "prediction_completed"
    assert event["properties"] == {
        "game_key": "ssq",
        "source_type": "fortune",
        "entry_count": 2,
        "candidate_count": 5,
        "review_status": None,
        "freshness_status": "fresh",
    }
    occurred_at = datetime.fromisoformat(event["occurred_at"])
    assert occurred_at.tzinfo == timezone.utc
    assert occurred_at.microsecond > 0

    _assert_current_product_event_index(connection)


def test_record_event_does_not_initialize_missing_schema_on_hot_write_path():
    connection = _connection()

    with pytest.raises(sqlite3.OperationalError):
        record_event(
            connection,
            client_id="client-a",
            event_name="workbench_opened",
            properties={},
        )

    assert (
        connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'product_events'
            """
        ).fetchone()
        is None
    )


def test_repository_schema_initialization_migrates_old_product_event_index_name(tmp_path):
    db_path = tmp_path / "events.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (game_key TEXT)
            """
        )
        connection.execute(
            """
            CREATE TABLE product_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_id TEXT NOT NULL,
              event_name TEXT NOT NULL,
              properties TEXT NOT NULL DEFAULT '{}',
              occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX idx_product_events_client_occurred_at
            ON product_events (client_id, occurred_at DESC)
            """
        )
    repo = LotteryRepository(db_path)

    repo.initialize_product_events_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _assert_current_product_event_index(connection)


def test_schema_initialization_rebuilds_two_column_current_index(tmp_path):
    db_path = tmp_path / "events.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
        connection.execute(
            """
            CREATE TABLE product_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_id TEXT NOT NULL,
              event_name TEXT NOT NULL,
              properties TEXT NOT NULL DEFAULT '{}',
              occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX idx_product_events_client_time
            ON product_events (client_id, occurred_at DESC)
            """
        )
    repo = LotteryRepository(db_path)

    repo.initialize_product_events_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _assert_current_product_event_index(connection)


def test_schema_initialization_rebuilds_wrong_direction_current_index(tmp_path):
    db_path = tmp_path / "events.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
        connection.execute(
            """
            CREATE TABLE product_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_id TEXT NOT NULL,
              event_name TEXT NOT NULL,
              properties TEXT NOT NULL DEFAULT '{}',
              occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX idx_product_events_client_time
            ON product_events (client_id, occurred_at, id)
            """
        )
    repo = LotteryRepository(db_path)

    repo.initialize_product_events_schema()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _assert_current_product_event_index(connection)


@pytest.mark.parametrize("event_name", ALLOWED_EVENT_NAMES)
def test_record_event_accepts_all_allowed_event_names(event_name):
    connection = _initialized_connection()

    event = record_event(
        connection,
        client_id="client-a",
        event_name=event_name,
        properties={"game_key": "3d"},
    )

    assert event["event_name"] == event_name


def test_record_event_normalizes_client_id_and_requires_non_blank():
    connection = _initialized_connection()
    long_client_id = "  " + ("x" * 120)

    event = record_event(
        connection,
        client_id=long_client_id,
        event_name="workbench_opened",
        properties={},
    )

    assert event["client_id"] == "x" * 96
    with pytest.raises(ValueError, match="client_id is required"):
        record_event(
            connection,
            client_id="   ",
            event_name="workbench_opened",
            properties={},
        )


def test_record_event_rejects_invalid_event_name_without_echo():
    connection = _initialized_connection()

    with pytest.raises(ValueError, match="invalid product event") as exc_info:
        record_event(
            connection,
            client_id="client-a",
            event_name="name=隐私姓名-Sentinel",
            properties={},
        )

    message = str(exc_info.value)
    assert "name=隐私姓名-Sentinel" not in message
    assert "隐私姓名" not in message
    assert _all_rows(connection) == []


@pytest.mark.parametrize(
    "properties",
    [
        {"name": "隐私姓名-Sentinel"},
        {"birth_date": "1988-12-31"},
        {"birth_place": "隐私出生地"},
        {"current_city": "隐私城市"},
        {"numbers": "01 02 03"},
        {"plan_id": "plan-123"},
        {"title": "我的方案"},
        {"game_key": {"nested": "value"}},
        {"mode": ["steady"]},
        {"game_key": "ssq", "unexpected_隐私姓名": "value"},
        {"game_key": "fc3d"},
        {"source_type": "home"},
        {"mode": "advanced"},
        {"window": 90},
        {"freshness_status": "unknown"},
        {"review_status": "hit"},
        {"window": True},
        {"entry_count": True},
        {"candidate_count": True},
        {"entry_count": 10001},
        {"candidate_count": 10001},
        {"game_key": None},
        {"freshness_status": None},
    ],
)
def test_record_event_rejects_unsupported_pii_and_nested_properties_without_echo(
    properties,
):
    connection = _initialized_connection()

    with pytest.raises(ValueError, match="invalid product event") as exc_info:
        record_event(
            connection,
            client_id="client-a",
            event_name="plan_saved",
            properties=properties,
        )

    serialized_input = json.dumps(properties, ensure_ascii=False)
    message = str(exc_info.value)
    for leaked in [
        "隐私姓名-Sentinel",
        "1988-12-31",
        "隐私出生地",
        "隐私城市",
        "01 02 03",
        "plan-123",
        "我的方案",
        "unexpected_隐私姓名",
    ]:
        assert leaked not in message
    assert serialized_input not in json.dumps(_all_rows(connection), ensure_ascii=False)


@pytest.mark.parametrize(
    "properties",
    [
        {"game_key": "x" * 65},
        {"window": -1},
        {"entry_count": -1},
        {"candidate_count": -1},
        {"window": 1.5},
        {"entry_count": math.inf},
        {"review_status": object()},
        {"game_key": "x" * 2050},
        [],
    ],
)
def test_record_event_enforces_size_type_and_count_limits(properties):
    connection = _initialized_connection()

    with pytest.raises(ValueError, match="invalid product event"):
        record_event(
            connection,
            client_id="client-a",
            event_name="plan_edited",
            properties=properties,
        )

    assert _all_rows(connection) == []


def test_record_event_accepts_exact_property_schema_boundaries():
    connection = _initialized_connection()

    event = record_event(
        connection,
        client_id="client-a",
        event_name="plan_saved",
        properties={
            "game_key": "pl5",
            "source_type": "carried",
            "mode": "pro",
            "window": 120,
            "entry_count": 0,
            "candidate_count": 10000,
            "freshness_status": "empty",
            "review_status": None,
        },
    )

    assert event["properties"] == {
        "game_key": "pl5",
        "source_type": "carried",
        "mode": "pro",
        "window": 120,
        "entry_count": 0,
        "candidate_count": 10000,
        "freshness_status": "empty",
        "review_status": None,
    }


def test_record_event_records_distinct_utc_microsecond_timestamps_in_insert_order():
    connection = _initialized_connection()

    first = record_event(
        connection,
        client_id="client-a",
        event_name="workbench_opened",
        properties={},
    )
    second = record_event(
        connection,
        client_id="client-a",
        event_name="workbench_opened",
        properties={},
    )

    first_at = datetime.fromisoformat(first["occurred_at"])
    second_at = datetime.fromisoformat(second["occurred_at"])
    assert first_at.tzinfo == timezone.utc
    assert second_at.tzinfo == timezone.utc
    assert first_at <= second_at
    assert first["occurred_at"] != second["occurred_at"]


def test_record_event_skips_schema_ddl_after_schema_is_current():
    connection = _initialized_connection()
    statements = []
    connection.set_trace_callback(statements.append)

    record_event(
        connection,
        client_id="client-a",
        event_name="workbench_opened",
        properties={},
    )

    schema_statements = [
        statement
        for statement in statements
        if "CREATE " in statement.upper() or "DROP " in statement.upper()
    ]
    assert schema_statements == []


def test_record_event_scopes_stored_rows_by_normalized_client_and_allows_repeats():
    connection = _initialized_connection()

    first = record_event(
        connection,
        client_id=" client-a ",
        event_name="review_viewed",
        properties={"review_status": "reviewed"},
    )
    second = record_event(
        connection,
        client_id="client-a",
        event_name="review_viewed",
        properties={"review_status": "expired"},
    )
    third = record_event(
        connection,
        client_id="client-b",
        event_name="review_viewed",
        properties={"review_status": "reviewed"},
    )

    assert [first["id"], second["id"], third["id"]] == [1, 2, 3]
    rows = _all_rows(connection)
    assert [row["client_id"] for row in rows] == ["client-a", "client-a", "client-b"]
    assert [json.loads(row["properties"])["review_status"] for row in rows] == [
        "reviewed",
        "expired",
        "reviewed",
    ]


def test_product_event_retention_removes_expired_rows_and_caps_total_count():
    connection = _initialized_connection()
    rows = [
        ("client-a", "workbench_opened", "{}", "2026-01-01T00:00:00+00:00"),
        ("client-a", "workbench_opened", "{}", "2026-08-07T00:00:00+00:00"),
        ("client-b", "workbench_opened", "{}", "2026-08-08T00:00:00+00:00"),
        ("client-c", "workbench_opened", "{}", "2026-08-09T00:00:00+00:00"),
    ]
    connection.executemany(
        """
        INSERT INTO product_events (client_id, event_name, properties, occurred_at)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()

    deleted = prune_product_events(
        connection,
        retention_days=90,
        max_rows=2,
        now=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )

    remaining = connection.execute(
        "SELECT client_id FROM product_events ORDER BY occurred_at, id"
    ).fetchall()
    assert deleted == 2
    assert [row[0] for row in remaining] == ["client-b", "client-c"]


def test_repository_concurrent_product_event_writes_persist_all_rows(tmp_path):
    db_path = tmp_path / "events.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
    repo = LotteryRepository(db_path)
    repo.initialize_product_events_schema()

    def write_event(index):
        return repo.record_product_event(
            client_id=f"client-{index % 3}",
            event_name="plan_saved",
            properties={
                "game_key": "ssq",
                "source_type": "manual",
                "entry_count": index,
            },
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(write_event, range(30)))

    assert len({result["id"] for result in results}) == 30
    with sqlite3.connect(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM product_events").fetchone()[0]
    assert count == 30


def test_repository_record_product_event_delegates_and_does_not_store_personal_payload(
    tmp_path,
):
    db_path = tmp_path / "events.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE draws (game_key TEXT)")
    repo = LotteryRepository(db_path)
    repo.initialize_product_events_schema()

    event = repo.record_product_event(
        client_id=" client-repo ",
        event_name="plan_carried_forward",
        properties={"game_key": "ssq", "mode": "steady", "window": 30},
    )

    assert event["client_id"] == "client-repo"
    assert event["properties"] == {"game_key": "ssq", "mode": "steady", "window": 30}
    with sqlite3.connect(db_path) as connection:
        raw_payloads = [
            row[0] for row in connection.execute("SELECT properties FROM product_events")
        ]
    serialized = json.dumps(raw_payloads, ensure_ascii=False)
    assert "张三" not in serialized
    assert "1990-01-01" not in serialized
    assert "01 02 03" not in serialized


@pytest.mark.parametrize(
    ("event_name", "properties"),
    [
        ("tool_opened", {"game_key": "3d", "tool_key": "trend", "window": 30}),
        (
            "tool_result_generated",
            {"game_key": "3d", "tool_key": "reduction", "result_count": 12},
        ),
    ],
)
def test_tool_events_accept_only_safe_aggregate_properties(connection, event_name, properties):
    event = record_event(
        connection,
        client_id="client-a",
        event_name=event_name,
        properties=properties,
    )
    assert event["properties"] == properties


@pytest.mark.parametrize("tool_key", TOOL_KEYS)
def test_tool_event_accepts_every_whitelisted_tool_key(connection, tool_key):
    event = record_event(
        connection,
        client_id="client-a",
        event_name="tool_opened",
        properties={"game_key": "3d", "tool_key": tool_key},
    )

    assert event["properties"] == {"game_key": "3d", "tool_key": tool_key}


@pytest.mark.parametrize(
    "properties",
    [
        # Number details, 生辰 and free text stay out of the toolbox events, whatever the
        # frontend tries to attach to them.
        {"game_key": "3d", "tool_key": "number", "number_text": "006"},
        {"game_key": "3d", "tool_key": "number", "birth_date": "1988-12-31"},
        {"game_key": "3d", "tool_key": "number", "birth_time": "辰时"},
        {"game_key": "3d", "tool_key": "attributes", "number_text": "006"},
        # The tool key is a closed whitelist, not a free-form label.
        {"game_key": "3d", "tool_key": "birth_date"},
        {"game_key": "3d", "tool_key": "隐私姓名-Sentinel"},
        {"game_key": "3d", "tool_key": "workbench"},
        {"game_key": "3d", "tool_key": ""},
        {"game_key": "3d", "tool_key": None},
        {"game_key": "3d", "tool_key": 1},
        # Counts stay bounded aggregates.
        {"game_key": "3d", "tool_key": "reduction", "result_count": -1},
        {"game_key": "3d", "tool_key": "reduction", "result_count": 10001},
        {"game_key": "3d", "tool_key": "reduction", "result_count": True},
        {"game_key": "3d", "tool_key": "reduction", "result_count": "12"},
    ],
)
@pytest.mark.parametrize("event_name", ["tool_opened", "tool_result_generated"])
def test_tool_event_rejects_personal_number_and_unknown_tool_key_without_echo(
    connection, event_name, properties
):
    # A contract that rejected everything (an empty whitelist) could not make this test pass:
    # the safe event below must still be recorded before the unsafe one is rejected.
    safe = record_event(
        connection,
        client_id="client-a",
        event_name=event_name,
        properties={"game_key": "3d", "tool_key": "number"},
    )
    assert safe["properties"] == {"game_key": "3d", "tool_key": "number"}

    with pytest.raises(ValueError, match="invalid product event") as exc_info:
        record_event(
            connection,
            client_id="client-a",
            event_name=event_name,
            properties=properties,
        )

    message = str(exc_info.value)
    for leaked in ["006", "1988-12-31", "辰时", "隐私姓名-Sentinel"]:
        assert leaked not in message
    # The server-generated timestamp is scanned out: its microseconds are digits nobody
    # supplied and they can coincidentally spell "006", which made this leak scan flaky.
    # Everything a caller can influence (client id, event name, properties) is still scanned.
    stored = json.dumps(
        [
            {key: value for key, value in row.items() if key != "occurred_at"}
            for row in _all_rows(connection)
        ],
        ensure_ascii=False,
    )
    assert json.dumps(properties, ensure_ascii=False) not in stored
    for leaked in ["006", "1988-12-31", "辰时", "隐私姓名-Sentinel"]:
        assert leaked not in stored


def test_tool_event_keeps_payload_size_cap_and_client_id_truncation(connection):
    event = record_event(
        connection,
        client_id="  " + ("x" * 120),
        event_name="tool_result_generated",
        properties={"game_key": "3d", "tool_key": "reduction", "result_count": 10000},
    )

    assert event["client_id"] == "x" * 96
    assert len(json.dumps(event["properties"], separators=(",", ":")).encode("utf-8")) <= 2048
    with pytest.raises(ValueError, match="invalid product event"):
        record_event(
            connection,
            client_id="client-a",
            event_name="tool_opened",
            properties={"game_key": "3d", "tool_key": "x" * 2050},
        )


def _largest_legal_properties():
    """Every allowed property key at its largest legal value: the biggest payload the
    whitelist can produce. It must still fit under the byte cap."""
    return {
        "game_key": "3d",
        "source_type": "carried",
        "mode": "windfall",
        "window": 120,
        "entry_count": product_events.MAX_COUNT_PROPERTY_VALUE,
        "candidate_count": product_events.MAX_COUNT_PROPERTY_VALUE,
        "freshness_status": "attention",
        "review_status": "pending_review",
        "tool_key": "attributes",
        "result_count": product_events.MAX_COUNT_PROPERTY_VALUE,
    }


def test_payload_byte_cap_rejects_a_payload_over_the_limit_and_accepts_one_at_it(
    connection, monkeypatch
):
    """The byte cap is a real gate, not decoration.

    Every allowed key and value is individually bounded, so no legal payload can reach 2048
    bytes through the public API. The cap is exercised here by moving it onto a legal payload:
    one byte under the payload's size it must reject, exactly at its size it must accept.
    Deleting the cap check makes the rejection half of this test fail.
    """
    properties = {"game_key": "3d", "tool_key": "reduction", "result_count": 10000}
    payload_bytes = len(
        json.dumps(properties, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )

    monkeypatch.setattr(product_events, "MAX_PROPERTIES_BYTES", payload_bytes - 1)
    with pytest.raises(ValueError, match="invalid product event"):
        record_event(
            connection,
            client_id="client-a",
            event_name="tool_result_generated",
            properties=properties,
        )
    assert _all_rows(connection) == []

    monkeypatch.setattr(product_events, "MAX_PROPERTIES_BYTES", payload_bytes)
    event = record_event(
        connection,
        client_id="client-a",
        event_name="tool_result_generated",
        properties=properties,
    )
    assert event["properties"] == properties
    assert len(_all_rows(connection)) == 1


def test_payload_byte_cap_still_admits_the_largest_legal_property_payload(connection):
    """The shipped cap must be wide enough for every allowed key at its largest legal value:
    shrinking MAX_PROPERTIES_BYTES to a value that drops real events fails here."""
    properties = _largest_legal_properties()
    assert set(properties) == product_events.ALLOWED_PROPERTY_KEYS

    event = record_event(
        connection,
        client_id="client-a",
        event_name="tool_result_generated",
        properties=properties,
    )

    assert event["properties"] == properties
    stored = _all_rows(connection)[0]["properties"]
    assert 0 < len(stored.encode("utf-8")) <= product_events.MAX_PROPERTIES_BYTES


@pytest.mark.parametrize(
    "count_key", sorted({"entry_count", "candidate_count", "result_count"})
)
def test_count_properties_are_bounded_by_the_named_count_limits(connection, count_key):
    """The count bounds are named constants, and both edges are enforced."""
    for value in [product_events.MIN_COUNT_PROPERTY_VALUE, product_events.MAX_COUNT_PROPERTY_VALUE]:
        event = record_event(
            connection,
            client_id="client-a",
            event_name="tool_result_generated",
            properties={"game_key": "3d", "tool_key": "reduction", count_key: value},
        )
        assert event["properties"][count_key] == value

    for value in [
        product_events.MIN_COUNT_PROPERTY_VALUE - 1,
        product_events.MAX_COUNT_PROPERTY_VALUE + 1,
    ]:
        with pytest.raises(ValueError, match="invalid product event"):
            record_event(
                connection,
                client_id="client-a",
                event_name="tool_result_generated",
                properties={"game_key": "3d", "tool_key": "reduction", count_key: value},
            )
