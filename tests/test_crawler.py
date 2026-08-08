import json
import sqlite3

import httpx
import pytest

from lottery_luck import crawler


VALID_CWL_ROW = {
    "code": "2026160",
    "name": "福彩3D",
    "date": "2026-06-16",
    "red": "1,2,3",
}


def _create_crawl_database(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (
                game_key TEXT,
                issue TEXT,
                red_numbers TEXT,
                raw_json TEXT,
                fetched_at TEXT,
                PRIMARY KEY (game_key, issue)
            )
            """
        )


def test_normalize_api_row_maps_official_fields_and_strips_weekday():
    draw = crawler.normalize_api_row(
        "ssq",
        {
            "code": "2026070",
            "name": "双色球",
            "date": "2026-06-16(二)",
            "week": "二",
            "red": "01,02,03,04,05,06",
            "blue": "07",
            "sales": "400000000",
            "poolmoney": "1200000000",
            "content": "开奖公告",
        },
    )

    assert draw["game_key"] == "ssq"
    assert draw["issue"] == "2026070"
    assert draw["game_name"] == "双色球"
    assert draw["draw_date"] == "2026-06-16"
    assert draw["week"] == "二"
    assert draw["red_numbers"] == "01,02,03,04,05,06"
    assert draw["blue_number"] == "07"
    assert draw["sales"] == "400000000"
    assert draw["pool_money"] == "1200000000"
    assert draw["content"] == "开奖公告"
    assert json.loads(draw["raw_json"])["code"] == "2026070"
    assert draw["fetched_at"]


def test_normalize_api_row_accepts_alternate_field_names():
    draw = crawler.normalize_api_row(
        "3d",
        {
            "issue": "2026160",
            "game_name": "福彩3D",
            "draw_date": "2026-06-16",
            "red_numbers": "1,2,3",
            "blue_number": "",
            "pool_money": "0",
        },
    )

    assert draw["issue"] == "2026160"
    assert draw["game_name"] == "福彩3D"
    assert draw["draw_date"] == "2026-06-16"
    assert draw["red_numbers"] == "1,2,3"
    assert draw["blue_number"] == ""
    assert draw["pool_money"] == "0"


def test_normalize_api_row_strips_full_width_weekday_with_spaces():
    draw = crawler.normalize_api_row(
        "ssq",
        {
            "code": "2026070",
            "date": " 2026-06-16 （二） ",
        },
    )

    assert draw["draw_date"] == "2026-06-16"
    assert draw["week"] == "二"


def test_normalize_api_row_maps_wide_table_fields_and_serializes_prizegrades():
    draw = crawler.normalize_api_row(
        "ssq",
        {
            "code": "2026070",
            "detailsLink": "https://example.test/details",
            "videoLink": "https://example.test/video",
            "blue2": "08",
            "prizegrades": [{"type": "一等奖", "typenum": "1"}],
            "specialRuleInfo": "特别规则",
            "prizeSpecialInfo": "特别奖项",
            "compLimitInfo": "兼容限制",
            "fyj_count": "10",
            "fyj_money": "200",
        },
    )

    assert draw["details_url"] == "https://example.test/details"
    assert draw["video_url"] == "https://example.test/video"
    assert draw["blue2"] == "08"
    assert json.loads(draw["prizegrades_json"]) == [{"type": "一等奖", "typenum": "1"}]
    assert draw["special_rule_info"] == "特别规则"
    assert draw["prize_special_info"] == "特别奖项"
    assert draw["comp_limit_info"] == "兼容限制"
    assert draw["fyj_count"] == "10"
    assert draw["fyj_money"] == "200"
    assert json.loads(draw["raw_json"])["detailsLink"] == "https://example.test/details"


def test_upsert_draw_is_idempotent_in_minimal_draws_table():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )

    crawler.upsert_draw(connection, {"game_key": "ssq", "issue": "1", "red_numbers": "01"})
    crawler.upsert_draw(connection, {"game_key": "ssq", "issue": "1", "red_numbers": "02"})

    rows = connection.execute("SELECT * FROM draws").fetchall()
    assert len(rows) == 1
    assert rows[0][2] == "02"


def test_upsert_draw_rejects_blank_issue():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )

    with pytest.raises(ValueError, match="issue"):
        crawler.upsert_draw(connection, {"game_key": "ssq", "issue": "  ", "red_numbers": "01"})


def test_upsert_draw_updates_raw_json_and_fetched_at_when_columns_exist():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )

    crawler.upsert_draw(
        connection,
        {
            "game_key": "ssq",
            "issue": "1",
            "red_numbers": "01",
            "raw_json": "{}",
            "fetched_at": "2026-06-16T00:00:00Z",
        },
    )
    crawler.upsert_draw(
        connection,
        {
            "game_key": "ssq",
            "issue": "1",
            "red_numbers": "02",
            "raw_json": '{"updated": true}',
            "fetched_at": "2026-06-16T01:00:00Z",
        },
    )

    row = connection.execute(
        "SELECT red_numbers, raw_json, fetched_at FROM draws WHERE game_key = ? AND issue = ?",
        ("ssq", "1"),
    ).fetchone()
    assert row == ("02", '{"updated": true}', "2026-06-16T01:00:00Z")


def test_normalize_and_upsert_insert_key_fields_into_wide_draws_table():
    connection = sqlite3.connect(":memory:")
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
            blue2 TEXT,
            sales TEXT,
            pool_money TEXT,
            content TEXT,
            details_url TEXT,
            video_url TEXT,
            special_rule_info TEXT,
            prize_special_info TEXT,
            comp_limit_info TEXT,
            prizegrades_json TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    draw = crawler.normalize_api_row(
        "ssq",
        {
            "code": "2026070",
            "name": "双色球",
            "date": "2026-06-16（二）",
            "red": "01,02,03,04,05,06",
            "blue": "07",
            "blue2": "08",
            "detailsUrl": "https://example.test/details",
            "videoUrl": "https://example.test/video",
            "prizeGrades": [{"type": "一等奖"}],
            "special_rule_info": "特别规则",
            "prize_special_info": "特别奖项",
            "comp_limit_info": "兼容限制",
        },
    )

    crawler.upsert_draw(connection, draw)

    row = connection.execute(
        """
        SELECT draw_date, week, blue2, details_url, video_url, prizegrades_json,
               special_rule_info, prize_special_info, comp_limit_info
        FROM draws
        WHERE game_key = ? AND issue = ?
        """,
        ("ssq", "2026070"),
    ).fetchone()
    assert row == (
        "2026-06-16",
        "二",
        "08",
        "https://example.test/details",
        "https://example.test/video",
        '[{"type": "一等奖"}]',
        "特别规则",
        "特别奖项",
        "兼容限制",
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"result": [{"code": "1"}]}, [{"code": "1"}]),
        ({"result": {"list": [{"code": "2"}]}}, [{"code": "2"}]),
        ({"data": [{"code": "3"}]}, [{"code": "3"}]),
    ],
)
def test_fetch_game_rows_reads_common_payload_shapes_and_sends_query(payload, expected):
    seen_requests = []

    def handler(request):
        seen_requests.append(request)
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    rows = crawler.fetch_game_rows("ssq", page_size=25, page_no=3, client=client)

    assert rows == expected
    request = seen_requests[0]
    assert request.url.params["pageNo"] == "3"
    assert request.url.params["pageSize"] == "25"
    assert request.url.params["name"] == "ssq"
    assert "User-Agent" in request.headers


def test_fetch_game_rows_follows_official_redirect_before_json():
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                302,
                headers={"Location": str(request.url.copy_with(path="/redirected"))},
            )
        return httpx.Response(200, json={"result": [{"code": "2026068"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    rows = crawler.fetch_game_rows("ssq", client=client)

    assert rows == [{"code": "2026068"}]
    assert len(requests) == 2


def test_fetch_game_rows_raises_for_http_errors():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )

    with pytest.raises(httpx.HTTPStatusError):
        crawler.fetch_game_rows("ssq", client=client)


def test_fetch_game_rows_raises_for_unknown_result_shape():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"result": {"unexpected": []}})
        )
    )

    with pytest.raises(ValueError):
        crawler.fetch_game_rows("ssq", client=client)


def test_crawl_cwl_games_uses_injected_connection_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "crawl.sqlite"
    _create_crawl_database(db_path)
    original_connect = sqlite3.connect

    monkeypatch.setattr(
        crawler,
        "fetch_game_rows",
        lambda *args, **kwargs: [VALID_CWL_ROW],
    )
    monkeypatch.setattr(
        crawler.sqlite3,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("module-level sqlite3.connect should not be required")
        ),
    )

    result = crawler.crawl_cwl_games(
        ["3d"],
        connection_factory=lambda: original_connect(db_path),
    )

    assert result["wrote_count"] == 1
    with original_connect(db_path) as check:
        row = check.execute("SELECT game_key, issue, red_numbers FROM draws").fetchone()
    assert row == ("3d", "2026160", "1,2,3")


def test_main_runs_against_temp_db_with_mocked_fetch_and_reports_count(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    connection.close()

    monkeypatch.setattr(
        crawler,
        "fetch_game_rows",
        lambda game_key, page_size=100, page_no=1, client=None: [
            {"code": f"{game_key}-1", "red": "01"}
        ],
    )

    exit_code = crawler.main(
        ["--games", "ssq,3d", "--since-latest", "--db-path", str(db_path)]
    )

    assert exit_code == 0
    assert "wrote 2 draws" in capsys.readouterr().out
    with sqlite3.connect(db_path) as check:
        assert check.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 2


def test_main_continues_after_one_game_fetch_failure_and_returns_nonzero(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    connection.close()

    def fake_fetch(game_key, page_size=100, page_no=1, client=None):
        if game_key == "ssq":
            raise RuntimeError("network unavailable")
        return [{"code": f"{game_key}-1", "red": "01"}]

    monkeypatch.setattr(crawler, "fetch_game_rows", fake_fetch)

    exit_code = crawler.main(["--games", "ssq,3d", "--db-path", str(db_path)])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "failed games: ssq" in output.err
    assert "wrote 1 draws" in output.out
    with sqlite3.connect(db_path) as check:
        assert check.execute("SELECT game_key FROM draws").fetchone()[0] == "3d"


def test_main_rolls_back_failed_game_rows_and_continues_after_upsert_failure(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            red_numbers TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    connection.close()

    def fake_fetch(game_key, page_size=100, page_no=1, client=None):
        if game_key == "ssq":
            return [
                {"code": "ssq-valid", "red": "01"},
                {"code": " ", "red": "02"},
            ]
        return [{"code": f"{game_key}-valid", "red": "03"}]

    monkeypatch.setattr(crawler, "fetch_game_rows", fake_fetch)

    exit_code = crawler.main(["--games", "ssq,3d", "--db-path", str(db_path)])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "failed games: ssq" in output.err
    assert "wrote 1 draws" in output.out
    with sqlite3.connect(db_path) as check:
        rows = check.execute("SELECT game_key, issue FROM draws").fetchall()
    assert rows == [("3d", "3d-valid")]
