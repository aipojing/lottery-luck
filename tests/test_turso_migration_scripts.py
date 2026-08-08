from __future__ import annotations

import sqlite3

import pytest

from scripts.check_turso_source import check_source_database
from scripts.verify_remote_database import compare_snapshots, read_remote_snapshot


def create_sample_database(tmp_path):
    db_path = tmp_path / "sample.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA page_size = 4096")
        connection.execute(
            """
            CREATE TABLE draws (
                game_key TEXT NOT NULL,
                issue TEXT NOT NULL,
                draw_date TEXT NOT NULL,
                PRIMARY KEY (game_key, issue)
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO draws (game_key, issue, draw_date)
            VALUES (?, ?, ?)
            """,
            [
                ("3d", "2026199", "2026-07-18"),
                ("3d", "2026200", "2026-07-19"),
            ],
        )

    return db_path


def test_source_check_reports_required_pragmas_and_draw_count(tmp_path):
    db_path = create_sample_database(tmp_path)

    result = check_source_database(db_path)

    assert result["page_size"] == 4096
    assert result["encoding"] == "UTF-8"
    assert result["draw_count"] == 2


def test_compare_snapshots_rejects_latest_issue_mismatch():
    with pytest.raises(ValueError, match="latest issue mismatch"):
        compare_snapshots(
            {"3d": {"count": 10, "latest_issue": "2026200"}},
            {"3d": {"count": 10, "latest_issue": "2026199"}},
        )


def test_remote_snapshot_requires_explicit_turso_configuration(monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TURSO_DATABASE_URL"):
        read_remote_snapshot()
