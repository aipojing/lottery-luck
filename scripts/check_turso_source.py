from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PUBLIC_GAMES = ("ssq", "dlt", "3d", "pl3", "kl8")


def check_source_database(db_path: Path | str) -> dict[str, Any]:
    path = Path(db_path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        snapshot = _draw_snapshot(connection)
        return {
            "database_path": str(path),
            "file_size_bytes": path.stat().st_size,
            "integrity_check": _pragma_value(connection, "integrity_check"),
            "page_size": _pragma_value(connection, "page_size"),
            "encoding": _pragma_value(connection, "encoding"),
            "auto_vacuum": _pragma_value(connection, "auto_vacuum"),
            "draw_count": _draw_count(connection),
            "games": snapshot,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight the local SQLite source before importing it to Turso."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path, help="Write the JSON snapshot to this path.")
    args = parser.parse_args(argv)

    try:
        result = check_source_database(args.database)
        _write_json(result, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        _validate_preflight(result)
    except Exception as exc:
        print(f"source preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _draw_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM draws").fetchone()
    return int(row[0])


def _draw_snapshot(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT game_key,
               COUNT(*) AS count,
               (SELECT issue
                FROM draws d2
                WHERE d2.game_key = draws.game_key
                ORDER BY draw_date DESC, issue DESC
                LIMIT 1) AS latest_issue
        FROM draws
        WHERE game_key IN (?, ?, ?, ?, ?)
        GROUP BY game_key
        """,
        PUBLIC_GAMES,
    ).fetchall()
    by_key = {str(row["game_key"]): row for row in rows}
    return {
        game: {
            "count": int(by_key[game]["count"]) if game in by_key else 0,
            "latest_issue": str(by_key[game]["latest_issue"] or "")
            if game in by_key
            else "",
        }
        for game in PUBLIC_GAMES
    }


def _pragma_value(connection: sqlite3.Connection, name: str) -> Any:
    row = connection.execute(f"PRAGMA {name}").fetchone()
    return row[0] if row is not None else None


def _validate_preflight(result: dict[str, Any]) -> None:
    checks = {
        "integrity_check": result.get("integrity_check") == "ok",
        "page_size": result.get("page_size") == 4096,
        "encoding": result.get("encoding") == "UTF-8",
        "auto_vacuum": result.get("auto_vacuum") == 0,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise ValueError(f"invalid source settings: {', '.join(failures)}")


def _write_json(result: dict[str, Any], output_path: Path | None) -> None:
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
