import json
import sqlite3

import pytest

from lottery_luck.quota import (
    cloud_records,
    consume_prediction_quota,
    mock_unlock_quota,
    save_cloud_record,
    quota_status,
    refund_prediction_quota,
)
from lottery_luck.settings import get_settings


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def _paid_connection(client_id: str = "client-paid"):
    connection = _connection()
    mock_unlock_quota(connection, client_id, kind="package", units=6, today="2026-06-19")
    return connection


def _cloud_record(**overrides):
    record = {
        "id": "r1",
        "created_at": "2026-06-19T10:00:00Z",
        "game_key": "ssq",
        "game_label": "双色球",
        "mode_label": "稳财号",
        "input_summary": "阳历1990年 · 午时 · 上海",
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_numbers": [7],
        "fortune_eye": 7,
        "number_text": "01 02 03 04 05 06 07",
        "best_draw_date": "2026-06-21",
        "luck_score": 88.5,
        "wealth_pattern": "土厚守财",
        "headline": "测试标题",
        "fortune_report": {"closed_loop": [{"label": "命格", "value": "测试"}]},
        "master_ritual": {"steps": [], "element_name": "金", "game_name": "双色球"},
        "credibility_chain": [{"label": "数据", "detail": "测试"}],
        "interpretation_layers": {"short_hook": "测试"},
        "metaphysics_profile": {"wealth_pattern": "土厚守财"},
        "number_reasons": {"main": [{"number": 1, "reason": "测试"}]},
        "avoid_numbers": [8, 9],
        "daily_fortune_sign": {"headline": "测试财签"},
        "ritual_steps": [{"label": "定盘"}],
        "avoid_reasons": [{"number": 8, "reason": "测试"}],
        "storage_state": "local",
        "review": {"status": "pending", "summary": "等待复盘"},
    }
    record.update(overrides)
    return record


def test_settings_include_prediction_quota_defaults():
    quota = get_settings()["prediction_quota"]

    assert quota["free_daily"] == 1
    assert quota["new_user_bonus"] == 3
    assert quota["member_daily"] == 20
    assert quota["mode_costs"]["steady"] == 1
    assert quota["enabled_games"] == ["ssq", "dlt", "3d", "pl3", "kl8"]


def test_quota_status_and_consume_use_bonus_before_free_daily():
    connection = _connection()
    config = {
        "free_daily": 1,
        "new_user_bonus": 1,
        "member_daily": 0,
        "package_units": [6],
        "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
        "enabled_games": ["ssq"],
        "allow_demo_after_exhausted": True,
    }

    first = consume_prediction_quota(
        connection,
        "client-a",
        "ssq",
        "steady",
        today="2026-06-19",
        config=config,
    )
    second = consume_prediction_quota(
        connection,
        "client-a",
        "ssq",
        "steady",
        today="2026-06-19",
        config=config,
    )
    third = consume_prediction_quota(
        connection,
        "client-a",
        "ssq",
        "steady",
        today="2026-06-19",
        config=config,
    )

    assert first["allowed"] is True
    assert first["source"] == "new_user_bonus"
    assert second["allowed"] is True
    assert second["source"] == "free_daily"
    assert third["allowed"] is False
    assert third["quota"]["remaining_total"] == 0


@pytest.mark.parametrize(
    ("source_config", "unlock", "expected_source", "remaining_key", "usage_date"),
    [
        (
            {
                "free_daily": 0,
                "new_user_bonus": 1,
                "member_daily": 0,
                "package_units": [6],
                "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
                "enabled_games": ["ssq"],
                "allow_demo_after_exhausted": True,
            },
            None,
            "new_user_bonus",
            "bonus_remaining",
            "all",
        ),
        (
            {
                "free_daily": 1,
                "new_user_bonus": 0,
                "member_daily": 0,
                "package_units": [6],
                "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
                "enabled_games": ["ssq"],
                "allow_demo_after_exhausted": True,
            },
            None,
            "free_daily",
            "free_daily_remaining",
            "2026-06-19",
        ),
        (
            {
                "free_daily": 0,
                "new_user_bonus": 0,
                "member_daily": 1,
                "package_units": [6],
                "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
                "enabled_games": ["ssq"],
                "allow_demo_after_exhausted": True,
            },
            {"kind": "member"},
            "member_daily",
            "member_daily_remaining",
            "2026-06-19",
        ),
        (
            {
                "free_daily": 0,
                "new_user_bonus": 0,
                "member_daily": 0,
                "package_units": [6],
                "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
                "enabled_games": ["ssq"],
                "allow_demo_after_exhausted": True,
            },
            {"kind": "package", "units": 1},
            "package",
            "package_credits",
            "",
        ),
    ],
)
def test_refund_prediction_quota_restores_consumed_allowance(
    source_config, unlock, expected_source, remaining_key, usage_date
):
    connection = _connection()
    client_id = f"client-refund-{expected_source}"
    if unlock:
        mock_unlock_quota(
            connection,
            client_id,
            today="2026-06-19",
            config=source_config,
            **unlock,
        )

    before = quota_status(
        connection,
        client_id,
        today="2026-06-19",
        config=source_config,
    )
    consumed = consume_prediction_quota(
        connection,
        client_id,
        "ssq",
        "steady",
        today="2026-06-19",
        config=source_config,
    )
    after_consume = quota_status(
        connection,
        client_id,
        today="2026-06-19",
        config=source_config,
    )
    refunded = refund_prediction_quota(
        connection,
        client_id,
        consumed,
        today="2026-06-19",
        config=source_config,
    )

    assert consumed["allowed"] is True
    assert consumed["source"] == expected_source
    assert after_consume[remaining_key] == before[remaining_key] - 1
    assert refunded[remaining_key] == before[remaining_key]
    assert refunded["remaining_total"] == before["remaining_total"]
    if usage_date:
        row = connection.execute(
            """
            SELECT used FROM quota_usage
            WHERE client_id = ? AND usage_date = ? AND source = ?
            """,
            (client_id, usage_date, expected_source),
        ).fetchone()
        assert row is None


def test_refund_prediction_quota_noops_for_untracked_free_game_and_zero_cost():
    connection = _connection()
    config = {
        "free_daily": 1,
        "new_user_bonus": 0,
        "member_daily": 0,
        "package_units": [6],
        "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
        "enabled_games": ["ssq"],
        "allow_demo_after_exhausted": True,
    }

    untracked = consume_prediction_quota(
        connection,
        "",
        "ssq",
        "steady",
        today="2026-06-19",
        config=config,
    )
    free_game = consume_prediction_quota(
        connection,
        "client-free-game",
        "3d",
        "steady",
        today="2026-06-19",
        config=config,
    )
    zero_cost = {
        "allowed": True,
        "source": "free_daily",
        "cost": 0,
        "client_id": "client-zero",
        "usage_date": "2026-06-19",
    }

    assert refund_prediction_quota(
        connection,
        "",
        untracked,
        today="2026-06-19",
        config=config,
    )["tracked"] is False
    assert refund_prediction_quota(
        connection,
        "client-free-game",
        free_game,
        today="2026-06-19",
        config=config,
    )["remaining_total"] == 1
    assert refund_prediction_quota(
        connection,
        "client-zero",
        zero_cost,
        today="2026-06-19",
        config=config,
    )["remaining_total"] == 1

    with pytest.raises(ValueError, match="invalid quota refund"):
        refund_prediction_quota(
            connection,
            "client-zero",
            {"allowed": True, "source": "bad", "cost": 1},
            today="2026-06-19",
            config=config,
        )


def test_mock_unlock_enables_paid_cloud_records():
    connection = _connection()
    config = {
        "free_daily": 0,
        "new_user_bonus": 0,
        "member_daily": 5,
        "package_units": [6, 18],
        "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
        "enabled_games": ["ssq"],
        "allow_demo_after_exhausted": True,
    }

    unlock = mock_unlock_quota(
        connection,
        "client-paid",
        kind="package",
        units=6,
        today="2026-06-19",
        config=config,
    )
    consume = consume_prediction_quota(
        connection,
        "client-paid",
        "ssq",
        "steady",
        today="2026-06-19",
        config=config,
    )
    saved = save_cloud_record(
        connection,
        "client-paid",
        {"id": "r1", "game_key": "ssq", "number_text": "01 02"},
    )

    assert unlock["quota"]["is_paid"] is True
    assert consume["allowed"] is True
    assert consume["source"] == "package"
    assert saved["storage_state"] == "cloud"
    assert cloud_records(connection, "client-paid")[0]["id"] == "r1"


def test_cloud_record_preserves_valid_frontend_contract_and_safe_name_suffixes():
    connection = _paid_connection()

    saved = save_cloud_record(connection, "client-paid", _cloud_record())
    stored = cloud_records(connection, "client-paid")[0]

    assert saved["storage_state"] == "cloud"
    assert stored["id"] == "r1"
    assert stored["master_ritual"]["game_name"] == "双色球"
    assert stored["master_ritual"]["element_name"] == "金"


def test_cloud_record_rejects_unknown_top_level_fields_without_writing_payload():
    connection = _paid_connection()
    save_cloud_record(connection, "client-paid", _cloud_record(id="safe-record"))

    with pytest.raises(ValueError, match="unsupported cloud record field") as exc_info:
        save_cloud_record(
            connection,
            "client-paid",
            _cloud_record(id="bad-record", unexpected="隐私姓名-Sentinel"),
        )
    assert "unexpected" not in str(exc_info.value)

    serialized_records = json.dumps(
        cloud_records(connection, "client-paid"), ensure_ascii=False
    )
    assert "safe-record" in serialized_records
    assert "bad-record" not in serialized_records
    assert "隐私姓名-Sentinel" not in serialized_records


@pytest.mark.parametrize(
    ("sensitive_key", "sentinel"),
    [
        ("fullName", "隐私姓名-Sentinel"),
        ("birthDate", "1988-12-31"),
        ("date_of_birth", "1988-12-31"),
        ("dob", "1988-12-31"),
        ("birthHour", "隐私时辰-Sentinel"),
        ("birthPlace", "隐私出生地"),
        ("birthplace", "隐私出生地"),
        ("currentCity", "隐私城市"),
    ],
)
def test_cloud_record_rejects_nested_sensitive_key_aliases_without_broad_substring_matching(
    sensitive_key, sentinel
):
    connection = _paid_connection()
    save_cloud_record(connection, "client-paid", _cloud_record(id="safe-record"))

    record = _cloud_record(
        id="bad-record",
        master_ritual={
            "game_name": "双色球",
            "element_name": "金",
            "nested": {sensitive_key: sentinel},
        },
    )
    with pytest.raises(ValueError, match="sensitive cloud record field") as exc_info:
        save_cloud_record(connection, "client-paid", record)
    assert sensitive_key not in str(exc_info.value)

    serialized_records = json.dumps(
        cloud_records(connection, "client-paid"), ensure_ascii=False
    )
    assert "safe-record" in serialized_records
    assert "bad-record" not in serialized_records
    assert sentinel not in serialized_records
    assert "game_name" in serialized_records
    assert "element_name" in serialized_records


def test_cloud_record_rejects_oversize_payload_before_db_write():
    connection = _paid_connection()

    with pytest.raises(ValueError, match="cloud record payload is too large"):
        save_cloud_record(
            connection,
            "client-paid",
            _cloud_record(id="oversize", headline="x" * (260 * 1024)),
        )

    assert cloud_records(connection, "client-paid") == []
