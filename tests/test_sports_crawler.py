import json
import sqlite3

import httpx
import pytest

from lottery_luck import sports_crawler
from lottery_luck.crawler import upsert_draw


VALID_SPORTS_ROW = {
    "lotteryDrawNum": "25158",
    "lotteryGameName": "排列3",
    "lotteryDrawTime": "2026-06-16",
    "lotteryDrawResult": "1 2 3",
}


def _create_sports_crawl_database(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (
                game_key TEXT,
                game_name TEXT,
                issue TEXT,
                draw_date TEXT,
                red_numbers TEXT,
                blue_number TEXT,
                raw_json TEXT,
                fetched_at TEXT,
                PRIMARY KEY (game_key, issue)
            )
            """
        )


def test_normalize_sports_row_splits_dlt_front_and_back_area_numbers():
    draw = sports_crawler.normalize_sports_row(
        "dlt",
        {
            "lotteryDrawNum": "25067",
            "lotteryGameName": "超级大乐透",
            "lotteryDrawTime": "2026-06-16",
            "lotteryDrawResult": "01 02 03 04 05 06 07",
            "prizeLevelList": [{"prizeLevel": "一等奖", "stakeCount": "2"}],
            "totalSaleAmount": "300000000",
            "poolBalanceAfterdraw": "900000000",
        },
    )

    assert draw["game_key"] == "dlt"
    assert draw["game_name"] == "超级大乐透"
    assert draw["issue"] == "25067"
    assert draw["draw_date"] == "2026-06-16"
    assert draw["red_numbers"] == "01,02,03,04,05"
    assert draw["blue_number"] == "06,07"
    assert draw["sales"] == "300000000"
    assert draw["pool_money"] == "900000000"
    assert json.loads(draw["prizegrades_json"]) == [{"prizeLevel": "一等奖", "stakeCount": "2"}]
    assert json.loads(draw["raw_json"])["lotteryDrawNum"] == "25067"
    assert draw["fetched_at"]


def test_normalize_sports_row_keeps_pl_digits_as_main_numbers():
    pl3 = sports_crawler.normalize_sports_row(
        "pl3",
        {
            "lotteryDrawNum": "25158",
            "lotteryDrawTime": "2026-06-16",
            "lotteryDrawResult": "7 7 7",
        },
    )
    pl5 = sports_crawler.normalize_sports_row(
        "pl5",
        {
            "lotteryDrawNum": "25158",
            "lotteryDrawTime": "2026-06-16",
            "lotteryDrawResult": "1,2,3,4,5",
        },
    )

    assert pl3["game_name"] == "排列3"
    assert pl3["red_numbers"] == "7,7,7"
    assert pl3["blue_number"] == ""
    assert pl5["game_name"] == "排列5"
    assert pl5["red_numbers"] == "1,2,3,4,5"
    assert pl5["blue_number"] == ""


def test_fetch_game_rows_uses_official_game_number_mapping_and_payload_shape():
    seen_requests = []

    def handler(request):
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "errorCode": 0,
                "value": {
                    "list": [{"lotteryDrawNum": "25067"}],
                    "pageNo": 1,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    rows = sports_crawler.fetch_game_rows("dlt", page_size=20, page_no=2, client=client)

    assert rows == [{"lotteryDrawNum": "25067"}]
    request = seen_requests[0]
    assert request.url.params["gameNo"] == "85"
    assert request.url.params["provinceId"] == "0"
    assert request.url.params["pageSize"] == "20"
    assert request.url.params["pageNo"] == "2"
    assert request.url.params["isVerify"] == "1"
    assert "User-Agent" in request.headers


def test_official_history_page_url_uses_lottery_gov_page_keys():
    assert (
        sports_crawler.official_history_page_url("dlt")
        == "https://www.lottery.gov.cn/kj/kjlb.html?dlt"
    )
    assert (
        sports_crawler.official_history_page_url("pl3")
        == "https://www.lottery.gov.cn/kj/kjlb.html?pls"
    )
    assert (
        sports_crawler.official_history_page_url("pl5")
        == "https://www.lottery.gov.cn/kj/kjlb.html?plw"
    )


def test_fetch_game_rows_browser_uses_official_page_runner():
    seen = {}

    def fake_runner(page_url, api_url, params, timeout_ms, headless):
        seen["page_url"] = page_url
        seen["api_url"] = api_url
        seen["params"] = params
        seen["timeout_ms"] = timeout_ms
        seen["headless"] = headless
        return {"errorCode": 0, "value": {"list": [{"lotteryDrawNum": "25158"}]}}

    rows = sports_crawler.fetch_game_rows_browser(
        "pl3",
        page_size=50,
        page_no=4,
        timeout_ms=12345,
        headless=False,
        runner=fake_runner,
    )

    assert rows == [{"lotteryDrawNum": "25158"}]
    assert seen == {
        "page_url": "https://www.lottery.gov.cn/kj/kjlb.html?pls",
        "api_url": "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry",
        "params": {
            "gameNo": "35",
            "provinceId": "0",
            "pageSize": "50",
            "pageNo": "4",
            "isVerify": "1",
        },
        "timeout_ms": 12345,
        "headless": False,
    }


def test_auto_fetch_falls_back_to_official_browser_when_direct_api_is_blocked(monkeypatch):
    request = httpx.Request(
        "GET",
        "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry",
    )
    response = httpx.Response(403, request=request, text="WAF")

    def fake_direct(*args, **kwargs):
        raise httpx.HTTPStatusError("blocked", request=request, response=response)

    def fake_browser(*args, **kwargs):
        return [{"lotteryDrawNum": "25067"}]

    monkeypatch.setattr(sports_crawler, "fetch_game_rows", fake_direct)
    monkeypatch.setattr(sports_crawler, "fetch_game_rows_browser", fake_browser)

    assert sports_crawler.fetch_game_rows_auto("dlt") == [{"lotteryDrawNum": "25067"}]


def test_auto_fetch_does_not_hide_non_waf_direct_errors(monkeypatch):
    request = httpx.Request(
        "GET",
        "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry",
    )
    response = httpx.Response(500, request=request, text="server error")

    def fake_direct(*args, **kwargs):
        raise httpx.HTTPStatusError("server error", request=request, response=response)

    monkeypatch.setattr(sports_crawler, "fetch_game_rows", fake_direct)

    with pytest.raises(httpx.HTTPStatusError):
        sports_crawler.fetch_game_rows_auto("dlt")


def test_normalized_sports_draw_can_be_upserted_into_draws_table():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            game_name TEXT,
            issue TEXT,
            draw_date TEXT,
            red_numbers TEXT,
            blue_number TEXT,
            prizegrades_json TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    draw = sports_crawler.normalize_sports_row(
        "dlt",
        {
            "lotteryDrawNum": "25067",
            "lotteryDrawTime": "2026-06-16",
            "lotteryDrawResult": "01 02 03 04 05 06 07",
        },
    )

    upsert_draw(connection, draw)

    row = connection.execute(
        "SELECT game_key, game_name, red_numbers, blue_number FROM draws"
    ).fetchone()
    assert row == ("dlt", "大乐透", "01,02,03,04,05", "06,07")


def test_main_fetches_multiple_pages_per_game(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            game_name TEXT,
            issue TEXT,
            draw_date TEXT,
            red_numbers TEXT,
            blue_number TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    connection.close()
    seen = []

    def fake_fetch(game_key, page_size=30, page_no=1, client=None, base_url=None):
        seen.append((game_key, page_size, page_no))
        return [
            {
                "lotteryDrawNum": f"{game_key}-{page_no}",
                "lotteryDrawTime": "2026-06-16",
                "lotteryDrawResult": "01 02 03 04 05 06 07",
            }
        ]

    monkeypatch.setattr(sports_crawler, "fetch_game_rows", fake_fetch)

    exit_code = sports_crawler.main(
        [
            "--games",
            "dlt,pl3",
            "--source",
            "direct",
            "--page-size",
            "50",
            "--pages",
            "3",
            "--db-path",
            str(db_path),
        ]
    )

    assert exit_code == 0
    assert seen == [
        ("dlt", 50, 1),
        ("dlt", 50, 2),
        ("dlt", 50, 3),
        ("pl3", 50, 1),
        ("pl3", 50, 2),
        ("pl3", 50, 3),
    ]
    assert "wrote 6 sports draws" in capsys.readouterr().out
    with sqlite3.connect(db_path) as check:
        assert check.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 6


def test_crawl_sports_games_records_logs_for_success_and_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            game_name TEXT,
            issue TEXT,
            draw_date TEXT,
            red_numbers TEXT,
            blue_number TEXT,
            raw_json TEXT,
            fetched_at TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    connection.close()

    def fake_fetch(game_key, page_size=30, page_no=1, client=None, base_url=None):
        if game_key == "pl3":
            raise RuntimeError("official page unavailable")
        return [
            {
                "lotteryDrawNum": f"{game_key}-{page_no}",
                "lotteryDrawTime": "2026-06-16",
                "lotteryDrawResult": "01 02 03 04 05 06 07",
            }
        ]

    monkeypatch.setattr(sports_crawler, "fetch_game_rows", fake_fetch)

    result = sports_crawler.crawl_sports_games(
        ["dlt", "pl3"],
        source="direct",
        page_size=30,
        pages=2,
        db_path=db_path,
    )

    assert result["wrote_count"] == 2
    assert result["failed_games"] == ["pl3"]
    assert result["games"][0]["status"] == "success"
    assert result["games"][1]["status"] == "failed"
    with sqlite3.connect(db_path) as check:
        log_rows = check.execute(
            "SELECT game_key, status, wrote_count, error FROM crawl_logs ORDER BY id"
        ).fetchall()
    assert log_rows[0] == ("dlt", "success", 2, "")
    assert log_rows[1][0:3] == ("pl3", "failed", 0)
    assert "official page unavailable" in log_rows[1][3]


def test_crawl_sports_games_uses_injected_connection_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "sports-crawl.sqlite"
    _create_sports_crawl_database(db_path)
    original_connect = sqlite3.connect

    monkeypatch.setattr(
        sports_crawler,
        "fetch_game_rows",
        lambda *args, **kwargs: [VALID_SPORTS_ROW],
    )
    monkeypatch.setattr(
        sports_crawler.sqlite3,
        "connect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("module-level sqlite3.connect should not be required")
        ),
    )

    result = sports_crawler.crawl_sports_games(
        ["pl3"],
        source="direct",
        connection_factory=lambda: original_connect(db_path),
    )

    assert result["wrote_count"] == 1
    with original_connect(db_path) as check:
        row = check.execute("SELECT game_key, issue, red_numbers FROM draws").fetchone()
    assert row == ("pl3", "25158", "1,2,3")
