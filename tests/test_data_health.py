import sqlite3

from lottery_luck.data_health import (
    build_public_freshness,
    build_data_health_report,
    ensure_crawl_logs_table,
    record_crawl_log,
    recent_crawl_logs,
)


def test_data_health_report_marks_healthy_attention_and_empty_games():
    games = [
        {
            "game_key": "dlt",
            "game_name": "大乐透",
            "provider": "sports",
            "draw_count": 300,
            "earliest_date": "2024-06-17",
            "latest_date": "2026-06-15",
            "latest_issue": "26066",
        },
        {
            "game_key": "ssq",
            "game_name": "双色球",
            "provider": "cwl",
            "draw_count": 2025,
            "earliest_date": "2013-01-01",
            "latest_date": "2026-06-14",
            "latest_issue": "2026067",
        },
        {
            "game_key": "pl3",
            "game_name": "排列3",
            "provider": "sports",
            "draw_count": 0,
            "earliest_date": "",
            "latest_date": "",
            "latest_issue": "",
        },
    ]
    draw_dates = {
        "dlt": ["2026-06-15", "2026-06-13", "2026-06-10", "2026-06-08"],
        "ssq": ["2026-06-14", "2026-06-11", "2026-06-09"],
        "pl3": [],
    }
    logs = [
        {
            "provider": "sports",
            "game_key": "dlt",
            "status": "success",
            "finished_at": "2026-06-17T08:00:00+00:00",
        }
    ]

    report = build_data_health_report(games, draw_dates, logs, today="2026-06-17")

    rows = {row["game_key"]: row for row in report["games"]}
    assert rows["dlt"]["status"] == "healthy"
    assert rows["dlt"]["status_tone"] == "good"
    assert rows["dlt"]["latest_expected_draw_date"] == "2026-06-15"
    assert rows["dlt"]["next_draw_date"] == "2026-06-17"
    assert rows["ssq"]["status"] == "attention"
    assert rows["ssq"]["status_tone"] == "warning"
    assert rows["ssq"]["latest_expected_draw_date"] == "2026-06-16"
    assert "2026-06-16" in rows["ssq"]["recent_missing_dates"]
    assert rows["pl3"]["status"] == "empty"
    assert rows["pl3"]["status_tone"] == "danger"
    assert report["kpis"]["healthy_games"] == 1
    assert report["kpis"]["attention_games"] == 1
    assert report["kpis"]["empty_games"] == 1
    assert report["kpis"]["latest_crawl_at"] == "2026-06-17T08:00:00+00:00"
    assert report["failure_summary"] == {"has_failure": False, "message": "暂无失败日志。"}


def test_data_health_report_surfaces_latest_failure_and_missing_trend():
    games = [
        {
            "game_key": "ssq",
            "game_name": "双色球",
            "provider": "cwl",
            "draw_count": 2025,
            "earliest_date": "2013-01-01",
            "latest_date": "2026-06-11",
            "latest_issue": "2026066",
        }
    ]
    draw_dates = {"ssq": ["2026-06-11"]}
    logs = [
        {
            "provider": "cwl",
            "game_key": "ssq",
            "source": "api",
            "status": "failed",
            "error": "official api timeout",
            "finished_at": "2026-06-17T09:00:00+00:00",
        },
        {
            "provider": "cwl",
            "game_key": "3d",
            "source": "api",
            "status": "success",
            "error": "",
            "finished_at": "2026-06-17T08:00:00+00:00",
        },
    ]

    report = build_data_health_report(games, draw_dates, logs, today="2026-06-17")

    row = report["games"][0]
    assert row["status"] == "attention"
    assert row["missing_trend"] == "widening"
    assert row["status_tone"] == "warning"
    assert report["failure_summary"]["has_failure"] is True
    assert report["failure_summary"]["game_key"] == "ssq"
    assert "official api timeout" in report["failure_summary"]["message"]


def test_crawl_log_helpers_create_write_and_read_logs():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    ensure_crawl_logs_table(connection)

    record_crawl_log(
        connection,
        provider="sports",
        game_key="dlt",
        source="browser",
        page_size=100,
        pages=3,
        wrote_count=300,
        status="success",
        error="",
        started_at="2026-06-17T08:00:00+00:00",
        finished_at="2026-06-17T08:00:03+00:00",
        duration_ms=3000,
    )

    logs = recent_crawl_logs(connection, limit=5)

    assert len(logs) == 1
    assert logs[0]["provider"] == "sports"
    assert logs[0]["game_key"] == "dlt"
    assert logs[0]["source"] == "browser"
    assert logs[0]["wrote_count"] == 300
    assert logs[0]["status"] == "success"


def test_public_freshness_marks_stale_data_as_not_claimable():
    freshness = build_public_freshness(
        {
            "game_key": "3d",
            "latest_issue": "2026182",
            "latest_date": "2026-06-29",
        },
        today="2026-07-12",
    )

    assert freshness == {
        "status": "stale",
        "latest_issue": "2026182",
        "latest_date": "2026-06-29",
        "staleness_days": 13,
        "can_claim_current": False,
        "message": "数据停留在第2026182期，暂不提供本期结论",
        "last_successful_update": "",
        "sync_error": "",
    }
    assert list(freshness) == [
        "status",
        "latest_issue",
        "latest_date",
        "staleness_days",
        "can_claim_current",
        "message",
        "last_successful_update",
        "sync_error",
    ]


def test_public_freshness_marks_empty_data_as_not_claimable():
    freshness = build_public_freshness(
        {"game_key": "ssq", "latest_issue": "", "latest_date": ""},
        today="2026-07-12",
    )

    assert freshness == {
        "status": "empty",
        "latest_issue": "",
        "latest_date": "",
        "staleness_days": None,
        "can_claim_current": False,
        "message": "暂无可用开奖数据",
        "last_successful_update": "",
        "sync_error": "",
    }


def test_public_freshness_allows_fresh_and_attention_data():
    fresh = build_public_freshness(
        {"game_key": "dlt", "latest_issue": "25080", "latest_date": "2026-07-10"},
        today="2026-07-12",
    )
    attention = build_public_freshness(
        {"game_key": "pl3", "latest_issue": "2026189", "latest_date": "2026-07-08"},
        today="2026-07-12",
    )

    assert fresh["status"] == "fresh"
    assert fresh["can_claim_current"] is True
    assert fresh["message"] == "数据已更新至第25080期"
    assert attention["status"] == "attention"
    assert attention["can_claim_current"] is True
    assert attention["message"] == "数据已更新至第2026189期"


def test_public_freshness_uses_successful_update_and_sanitized_newest_failure():
    freshness = build_public_freshness(
        {"game_key": "ssq", "latest_issue": "2026078", "latest_date": "2026-07-11"},
        today="2026-07-12",
        logs=[
            {
                "game_key": "ssq",
                "status": "failed",
                "error": " first line\nsecond line " + ("x" * 200),
                "finished_at": "2026-07-12T04:00:00+00:00",
            },
            {
                "game_key": "ssq",
                "status": "success",
                "error": "",
                "finished_at": "2026-07-12T03:00:00+00:00",
            },
        ],
    )

    assert freshness["last_successful_update"] == "2026-07-12T03:00:00+00:00"
    assert freshness["sync_error"] == "first line second line " + ("x" * 137)
    assert len(freshness["sync_error"]) == 160


def test_public_freshness_ignores_unscoped_and_other_game_logs():
    freshness = build_public_freshness(
        {"game_key": "ssq", "latest_issue": "2026078", "latest_date": "2026-07-11"},
        today="2026-07-12",
        logs=[
            {
                "game_key": "3d",
                "status": "failed",
                "error": "wrong game failure",
                "finished_at": "2026-07-12T06:00:00+00:00",
            },
            {
                "game_key": "ssq",
                "status": "success",
                "error": "",
                "finished_at": "2026-07-12T05:00:00+00:00",
            },
            {
                "game_key": "ssq",
                "status": "success",
                "error": "",
                "finished_at": "2026-07-12T05:30:00+00:00",
            },
            {
                "status": "failed",
                "error": "unscoped failure",
                "finished_at": "2026-07-12T07:00:00+00:00",
            },
            {
                "game_key": "",
                "status": "failed",
                "error": "empty scope failure",
                "finished_at": "2026-07-12T06:30:00+00:00",
            },
        ],
    )

    assert freshness["last_successful_update"] == "2026-07-12T05:30:00+00:00"
    assert freshness["sync_error"] == ""


def test_public_freshness_uses_finished_at_to_find_newest_log_when_unordered():
    freshness = build_public_freshness(
        {"game_key": "ssq", "latest_issue": "2026078", "latest_date": "2026-07-11"},
        today="2026-07-12",
        logs=[
            {
                "game_key": "ssq",
                "status": "success",
                "error": "",
                "finished_at": "2026-07-12T05:00:00+00:00",
            },
            {
                "game_key": "ssq",
                "status": "failed",
                "error": "newest failure",
                "finished_at": "2026-07-12T06:00:00+00:00",
            },
        ],
    )

    assert freshness["last_successful_update"] == "2026-07-12T05:00:00+00:00"
    assert freshness["sync_error"] == "newest failure"


def test_public_freshness_compares_finished_at_chronologically_and_ignores_malformed():
    freshness = build_public_freshness(
        {"game_key": "ssq", "latest_issue": "2026078", "latest_date": "2026-07-11"},
        today="2026-07-12",
        logs=[
            {
                "game_key": "ssq",
                "status": "success",
                "error": "",
                "finished_at": "2026-07-12T05:30:00+08:00",
            },
            {
                "game_key": "ssq",
                "status": "failed",
                "error": "latest absolute failure",
                "finished_at": "2026-07-12T00:00:00+00:00",
            },
            {
                "game_key": "ssq",
                "status": "failed",
                "error": "bad timestamp failure",
                "finished_at": "not a timestamp",
            },
        ],
    )

    assert freshness["last_successful_update"] == "2026-07-12T05:30:00+08:00"
    assert freshness["sync_error"] == "latest absolute failure"
