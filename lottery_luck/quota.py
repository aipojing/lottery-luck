from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from .settings import get_prediction_quota


CREATE_QUOTA_ACCOUNTS_SQL = """
CREATE TABLE IF NOT EXISTS quota_accounts (
  client_id TEXT PRIMARY KEY,
  first_seen_date TEXT NOT NULL,
  package_credits INTEGER NOT NULL DEFAULT 0,
  paid_user INTEGER NOT NULL DEFAULT 0,
  member_until TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_QUOTA_USAGE_SQL = """
CREATE TABLE IF NOT EXISTS quota_usage (
  client_id TEXT NOT NULL,
  usage_date TEXT NOT NULL,
  source TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (client_id, usage_date, source)
)
"""

CREATE_CLOUD_RECORDS_SQL = """
CREATE TABLE IF NOT EXISTS cloud_fortune_records (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

CLOUD_RECORD_MAX_BYTES = 256 * 1024
REFUNDABLE_QUOTA_SOURCES = {"new_user_bonus", "free_daily", "member_daily", "package"}
NOOP_QUOTA_SOURCES = {"untracked", "free_game"}

CLOUD_RECORD_ALLOWED_FIELDS = {
    "id",
    "created_at",
    "game_key",
    "game_label",
    "mode_label",
    "input_summary",
    "main_numbers",
    "special_numbers",
    "fortune_eye",
    "number_text",
    "best_draw_date",
    "luck_score",
    "wealth_pattern",
    "headline",
    "fortune_report",
    "master_ritual",
    "credibility_chain",
    "interpretation_layers",
    "metaphysics_profile",
    "number_reasons",
    "avoid_numbers",
    "daily_fortune_sign",
    "ritual_steps",
    "avoid_reasons",
    "storage_state",
    "review",
}

SENSITIVE_RECORD_KEY_ALIASES = {
    "name",
    "fullname",
    "birthdate",
    "dateofbirth",
    "dob",
    "birthhour",
    "birthplace",
    "currentcity",
}


def quota_status(
    connection: sqlite3.Connection,
    client_id: str,
    *,
    today: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client_id = _normalize_client_id(client_id)
    quota_config = _quota_config(config)
    today = _today(today)
    if not client_id:
        return _untracked_status(quota_config)

    _ensure_schema(connection)
    account = _ensure_account(connection, client_id, today)
    status = _status_from_account(connection, client_id, account, today, quota_config)
    connection.commit()
    return status


def consume_prediction_quota(
    connection: sqlite3.Connection,
    client_id: str,
    game_key: str,
    mode_key: str,
    *,
    today: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client_id = _normalize_client_id(client_id)
    quota_config = _quota_config(config)
    today = _today(today)
    cost = _quota_cost(quota_config, game_key, mode_key)
    if not client_id or cost <= 0:
        return {
            "allowed": True,
            "source": "untracked" if not client_id else "free_game",
            "cost": cost,
            "client_id": client_id,
            "usage_date": today,
            "quota": quota_status(connection, client_id, today=today, config=quota_config),
        }

    _ensure_schema(connection)
    account = _ensure_account(connection, client_id, today)
    status = _status_from_account(connection, client_id, account, today, quota_config)
    source = _first_available_source(status, cost)
    if not source:
        connection.commit()
        return {
            "allowed": False,
            "source": "",
            "cost": cost,
            "client_id": client_id,
            "usage_date": today,
            "quota": status,
        }

    if source == "package":
        usage_date = today
        connection.execute(
            """
            UPDATE quota_accounts
            SET package_credits = package_credits - ?,
                paid_user = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
            """,
            (cost, client_id),
        )
    else:
        usage_date = "all" if source == "new_user_bonus" else today
        _add_usage(connection, client_id, usage_date, source, cost)

    refreshed = quota_status(connection, client_id, today=today, config=quota_config)
    return {
        "allowed": True,
        "source": source,
        "cost": cost,
        "client_id": client_id,
        "usage_date": usage_date,
        "quota": refreshed,
    }


def refund_prediction_quota(
    connection: sqlite3.Connection,
    client_id: str,
    consume_result: dict[str, Any],
    *,
    today: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(consume_result, dict):
        raise ValueError("invalid quota refund")

    client_id = _normalize_client_id(client_id)
    quota_config = _quota_config(config)
    today = _today(today)
    source = str(consume_result.get("source") or "").strip().lower()
    if source not in REFUNDABLE_QUOTA_SOURCES | NOOP_QUOTA_SOURCES:
        raise ValueError("invalid quota refund")
    try:
        cost = int(consume_result.get("cost") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid quota refund") from exc
    if cost < 0:
        raise ValueError("invalid quota refund")

    result_client_id = _normalize_client_id(consume_result.get("client_id") or client_id)
    if client_id and result_client_id and client_id != result_client_id:
        raise ValueError("invalid quota refund")
    client_id = client_id or result_client_id

    if not client_id or source in NOOP_QUOTA_SOURCES or cost <= 0:
        return quota_status(connection, client_id, today=today, config=quota_config)

    _ensure_schema(connection)
    _ensure_account(connection, client_id, today)
    if source == "package":
        connection.execute(
            """
            UPDATE quota_accounts
            SET package_credits = package_credits + ?,
                paid_user = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
            """,
            (cost, client_id),
        )
    else:
        usage_date = str(consume_result.get("usage_date") or "").strip()
        if not usage_date:
            usage_date = "all" if source == "new_user_bonus" else today
        if source == "new_user_bonus" and usage_date != "all":
            raise ValueError("invalid quota refund")
        if source != "new_user_bonus" and usage_date == "all":
            raise ValueError("invalid quota refund")
        connection.execute(
            """
            UPDATE quota_usage
            SET used = CASE WHEN used <= ? THEN 0 ELSE used - ? END
            WHERE client_id = ? AND usage_date = ? AND source = ?
            """,
            (cost, cost, client_id, usage_date, source),
        )
        connection.execute(
            """
            DELETE FROM quota_usage
            WHERE client_id = ? AND usage_date = ? AND source = ? AND used <= 0
            """,
            (client_id, usage_date, source),
        )

    refunded = quota_status(connection, client_id, today=today, config=quota_config)
    connection.commit()
    return refunded


def mock_unlock_quota(
    connection: sqlite3.Connection,
    client_id: str,
    *,
    kind: str,
    units: int | None = None,
    today: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client_id = _normalize_client_id(client_id)
    quota_config = _quota_config(config)
    today = _today(today)
    if not client_id:
        raise ValueError("client_id is required")

    _ensure_schema(connection)
    _ensure_account(connection, client_id, today)
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind == "member":
        member_until = (date.fromisoformat(today) + timedelta(days=365)).isoformat()
        connection.execute(
            """
            UPDATE quota_accounts
            SET paid_user = 1,
                member_until = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
            """,
            (member_until, client_id),
        )
        unlocked_units = quota_config["member_daily"]
    elif normalized_kind == "package":
        package_units = quota_config.get("package_units") or [6]
        unlocked_units = _safe_positive_int(units, int(package_units[0]))
        connection.execute(
            """
            UPDATE quota_accounts
            SET paid_user = 1,
                package_credits = package_credits + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
            """,
            (unlocked_units, client_id),
        )
    else:
        raise ValueError("unsupported unlock kind")

    connection.commit()
    return {
        "client_id": client_id,
        "kind": normalized_kind,
        "units": unlocked_units,
        "quota": quota_status(connection, client_id, today=today, config=quota_config),
    }


def save_cloud_record(
    connection: sqlite3.Connection,
    client_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    client_id = _normalize_client_id(client_id)
    if not client_id:
        raise ValueError("client_id is required")

    _ensure_schema(connection)
    account = _ensure_account(connection, client_id, _today(None))
    if not _is_paid(account, _today(None)):
        raise PermissionError("cloud records require a paid account")

    payload = _sanitize_record(record)
    record_id = str(payload.get("id") or "").strip() or f"{client_id}-record"
    payload["id"] = record_id
    payload["storage_state"] = "cloud"
    serialized_payload = _serialized_cloud_record_payload(payload)
    connection.execute(
        """
        INSERT INTO cloud_fortune_records (id, client_id, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          client_id = excluded.client_id,
          payload = excluded.payload,
          created_at = CURRENT_TIMESTAMP
        """,
        (record_id, client_id, serialized_payload),
    )
    connection.commit()
    return payload


def cloud_records(
    connection: sqlite3.Connection,
    client_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    client_id = _normalize_client_id(client_id)
    if not client_id:
        return []
    _ensure_schema(connection)
    rows = connection.execute(
        """
        SELECT payload
        FROM cloud_fortune_records
        WHERE client_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (client_id, max(1, min(200, int(limit or 50)))),
    )
    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            result.append(payload)
    return result


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_QUOTA_ACCOUNTS_SQL)
    connection.execute(CREATE_QUOTA_USAGE_SQL)
    connection.execute(CREATE_CLOUD_RECORDS_SQL)


def _normalize_client_id(client_id: str) -> str:
    return str(client_id or "").strip()[:96]


def _today(today: str | None) -> str:
    return str(today or date.today().isoformat())[:10]


def _quota_config(config: dict[str, Any] | None) -> dict[str, Any]:
    base = get_prediction_quota() if config is None else config
    return {
        "free_daily": _safe_positive_int(base.get("free_daily"), 0),
        "new_user_bonus": _safe_positive_int(base.get("new_user_bonus"), 0),
        "member_daily": _safe_positive_int(base.get("member_daily"), 0),
        "package_units": [
            _safe_positive_int(unit, 0)
            for unit in (base.get("package_units") or [6])
            if _safe_positive_int(unit, 0) > 0
        ] or [6],
        "mode_costs": {
            "steady": _safe_positive_int((base.get("mode_costs") or {}).get("steady"), 1),
            "windfall": _safe_positive_int((base.get("mode_costs") or {}).get("windfall"), 1),
            "guard": _safe_positive_int((base.get("mode_costs") or {}).get("guard"), 1),
        },
        "enabled_games": [
            str(game).strip().lower()
            for game in (base.get("enabled_games") or [])
            if str(game).strip()
        ],
        "allow_demo_after_exhausted": bool(base.get("allow_demo_after_exhausted", True)),
    }


def _ensure_account(
    connection: sqlite3.Connection,
    client_id: str,
    today: str,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM quota_accounts WHERE client_id = ?",
        (client_id,),
    ).fetchone()
    if row is None:
        connection.execute(
            """
            INSERT INTO quota_accounts (client_id, first_seen_date)
            VALUES (?, ?)
            """,
            (client_id, today),
        )
        row = connection.execute(
            "SELECT * FROM quota_accounts WHERE client_id = ?",
            (client_id,),
        ).fetchone()
    return dict(row)


def _status_from_account(
    connection: sqlite3.Connection,
    client_id: str,
    account: dict[str, Any],
    today: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    bonus_used = _usage(connection, client_id, "all", "new_user_bonus")
    free_used = _usage(connection, client_id, today, "free_daily")
    member_used = _usage(connection, client_id, today, "member_daily")
    is_member = _is_member(account, today)
    bonus_remaining = max(0, int(config["new_user_bonus"]) - bonus_used)
    free_remaining = max(0, int(config["free_daily"]) - free_used)
    member_remaining = max(0, int(config["member_daily"]) - member_used) if is_member else 0
    package_credits = max(0, int(account.get("package_credits") or 0))
    paid_user = bool(account.get("paid_user")) or is_member
    remaining_total = bonus_remaining + free_remaining + member_remaining + package_credits
    return {
        "tracked": True,
        "client_id": client_id,
        "is_paid": paid_user,
        "is_member": is_member,
        "member_until": account.get("member_until") or "",
        "remaining_total": remaining_total,
        "bonus_remaining": bonus_remaining,
        "free_daily_remaining": free_remaining,
        "member_daily_remaining": member_remaining,
        "package_credits": package_credits,
        "used_today": free_used + member_used,
        "config": config,
    }


def _untracked_status(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "tracked": False,
        "client_id": "",
        "is_paid": False,
        "is_member": False,
        "member_until": "",
        "remaining_total": None,
        "bonus_remaining": 0,
        "free_daily_remaining": 0,
        "member_daily_remaining": 0,
        "package_credits": 0,
        "used_today": 0,
        "config": config,
    }


def _quota_cost(config: dict[str, Any], game_key: str, mode_key: str) -> int:
    enabled_games = set(config.get("enabled_games") or [])
    if enabled_games and str(game_key).strip().lower() not in enabled_games:
        return 0
    return _safe_positive_int((config.get("mode_costs") or {}).get(mode_key), 1)


def _first_available_source(status: dict[str, Any], cost: int) -> str:
    for key, source in [
        ("bonus_remaining", "new_user_bonus"),
        ("free_daily_remaining", "free_daily"),
        ("member_daily_remaining", "member_daily"),
        ("package_credits", "package"),
    ]:
        if int(status.get(key) or 0) >= cost:
            return source
    return ""


def _add_usage(
    connection: sqlite3.Connection,
    client_id: str,
    usage_date: str,
    source: str,
    amount: int,
) -> None:
    connection.execute(
        """
        INSERT INTO quota_usage (client_id, usage_date, source, used)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(client_id, usage_date, source) DO UPDATE SET
          used = used + excluded.used
        """,
        (client_id, usage_date, source, amount),
    )


def _usage(connection: sqlite3.Connection, client_id: str, usage_date: str, source: str) -> int:
    row = connection.execute(
        """
        SELECT used
        FROM quota_usage
        WHERE client_id = ? AND usage_date = ? AND source = ?
        """,
        (client_id, usage_date, source),
    ).fetchone()
    return int(row["used"]) if row else 0


def _is_member(account: dict[str, Any], today: str) -> bool:
    member_until = str(account.get("member_until") or "").strip()
    return bool(member_until and member_until >= today)


def _is_paid(account: dict[str, Any], today: str) -> bool:
    return bool(account.get("paid_user")) or _is_member(account, today)


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("cloud record must be an object")
    _reject_sensitive_record_keys(record)
    unknown_fields = sorted(
        str(key) for key in record if str(key) not in CLOUD_RECORD_ALLOWED_FIELDS
    )
    if unknown_fields:
        raise ValueError("unsupported cloud record field")
    return {str(key): value for key, value in record.items()}


def _reject_sensitive_record_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if _normalized_record_key(key) in SENSITIVE_RECORD_KEY_ALIASES:
                raise ValueError("sensitive cloud record field is not allowed")
            _reject_sensitive_record_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_record_keys(item)


def _normalized_record_key(key: Any) -> str:
    return "".join(char for char in str(key or "").casefold() if char.isalnum())


def _serialized_cloud_record_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > CLOUD_RECORD_MAX_BYTES:
        raise ValueError("cloud record payload is too large")
    return serialized


def _safe_positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(0, number)
