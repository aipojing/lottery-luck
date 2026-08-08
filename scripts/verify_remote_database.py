from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from lottery_luck.config import TURSO_AUTH_TOKEN_ENV, TURSO_DATABASE_URL_ENV
from lottery_luck.database import connect_database

PUBLIC_GAMES = ("ssq", "dlt", "3d", "pl3", "kl8")


def compare_snapshots(source: dict[str, Any], remote: dict[str, Any]) -> None:
    source_games = _games(source)
    remote_games = _games(remote)

    for game in PUBLIC_GAMES:
        source_row = source_games.get(game, {})
        remote_row = remote_games.get(game, {})
        source_count = int(source_row.get("count") or 0)
        remote_count = int(remote_row.get("count") or 0)
        if source_count != remote_count:
            raise ValueError(
                f"{game} count mismatch: source={source_count} remote={remote_count}"
            )

        source_issue = str(source_row.get("latest_issue") or "")
        remote_issue = str(remote_row.get("latest_issue") or "")
        if source_issue != remote_issue:
            raise ValueError(
                f"{game} latest issue mismatch: source={source_issue} remote={remote_issue}"
            )


def read_remote_snapshot() -> dict[str, dict[str, Any]]:
    missing = [
        name
        for name in (TURSO_DATABASE_URL_ENV, TURSO_AUTH_TOKEN_ENV)
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise RuntimeError(
            f"remote verification requires {', '.join(missing)}; refusing local fallback"
        )

    with connect_database() as connection:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a Turso/libSQL database after importing the SQLite source."
    )
    parser.add_argument("--source-snapshot", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        source = json.loads(args.source_snapshot.read_text(encoding="utf-8"))
        remote = read_remote_snapshot()
        compare_snapshots(source, remote)
    except Exception as exc:
        print(f"remote verification failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(remote, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _games(snapshot: dict[str, Any]) -> dict[str, Any]:
    games = snapshot.get("games")
    if isinstance(games, dict):
        return games
    return snapshot


if __name__ == "__main__":
    raise SystemExit(main())
