from datetime import datetime, timedelta, timezone
import sqlite3

from lottery_luck.write_limits import consume_write_limit, ensure_write_limits_table


def test_fixed_window_write_limit_is_scoped_and_resets_next_window():
    connection = sqlite3.connect(":memory:")
    ensure_write_limits_table(connection)
    now = datetime(2026, 8, 9, 10, 15, tzinfo=timezone.utc)

    assert consume_write_limit(
        connection,
        scope="events-client",
        bucket_key="client-a",
        limit=2,
        window_seconds=3600,
        now=now,
    ) is True
    assert consume_write_limit(
        connection,
        scope="events-client",
        bucket_key="client-a",
        limit=2,
        window_seconds=3600,
        now=now + timedelta(minutes=1),
    ) is True
    assert consume_write_limit(
        connection,
        scope="events-client",
        bucket_key="client-a",
        limit=2,
        window_seconds=3600,
        now=now + timedelta(minutes=2),
    ) is False
    assert consume_write_limit(
        connection,
        scope="events-client",
        bucket_key="client-b",
        limit=2,
        window_seconds=3600,
        now=now + timedelta(minutes=2),
    ) is True
    assert consume_write_limit(
        connection,
        scope="events-client",
        bucket_key="client-a",
        limit=2,
        window_seconds=3600,
        now=now + timedelta(hours=1),
    ) is True


def test_write_limit_lazily_initializes_schema_for_isolated_repositories():
    connection = sqlite3.connect(":memory:")

    assert consume_write_limit(
        connection,
        scope="plans-client",
        bucket_key="client-a",
        limit=1,
        window_seconds=86400,
    ) is True
    assert connection.execute(
        "SELECT count FROM api_write_limits"
    ).fetchone()[0] == 1
