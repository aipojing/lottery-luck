import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date as real_date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from lottery_luck import scheduler
from lottery_luck.ai_features import AiAuthenticationError, AiFeature
from lottery_luck.api import app, get_repository
from lottery_luck.repository import LotteryRepository


client = TestClient(app)
ADMIN_TOKEN = "test-admin-token"
ADMIN_HEADERS = {"X-Lottery-Admin-Token": ADMIN_TOKEN}


@pytest.fixture(autouse=True)
def admin_token_env(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", ADMIN_TOKEN)


def _quota_db(tmp_path: Path) -> LotteryRepository:
    db_path = tmp_path / "quota.sqlite"
    with sqlite3.connect(db_path) as connection:
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
              sales TEXT,
              pool_money TEXT,
              content TEXT,
              PRIMARY KEY(game_key, issue)
            )
            """
        )
    repo = LotteryRepository(db_path)
    repo.initialize_product_events_schema()
    return repo


def _raw_quota_db_without_product_events_schema(tmp_path: Path) -> LotteryRepository:
    db_path = tmp_path / "quota-uninitialized.sqlite"
    with sqlite3.connect(db_path) as connection:
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
              sales TEXT,
              pool_money TEXT,
              content TEXT,
              PRIMARY KEY(game_key, issue)
            )
            """
        )
    return LotteryRepository(db_path)


def _asgi_post_events(body: bytes, headers: list[tuple[bytes, bytes]]):
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/events",
        "raw_path": b"/api/events",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    asyncio.run(app(scope, receive, send))
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status, response_body.decode("utf-8")


def test_games_returns_visible_frontend_keys():
    response = client.get("/api/games")

    assert response.status_code == 200
    games = response.json()["games"]
    keys = {game["game_key"] for game in games}
    assert keys == {"ssq", "dlt", "3d", "pl3", "kl8"}
    assert [game["game_key"] for game in games] == [
        "ssq",
        "dlt",
        "3d",
        "pl3",
        "kl8",
    ]
    ssq_rule = next(game["number_rule"] for game in games if game["game_key"] == "ssq")
    assert ssq_rule == {
        "main_count": 6,
        "main_min": 1,
        "main_max": 33,
        "special_count": 1,
        "special_min": 1,
        "special_max": 16,
        "allow_repeat": False,
        "special_distinct_from_main": False,
    }


def test_health_returns_public_data_readiness_by_visible_game():
    class Repo:
        def list_games(self):
            return [
                {
                    "game_key": "ssq",
                    "latest_issue": "2026079",
                    "latest_date": "2026-07-11",
                },
                {
                    "game_key": "dlt",
                    "latest_issue": "25080",
                    "latest_date": "2026-07-08",
                },
                {
                    "game_key": "3d",
                    "latest_issue": "2026182",
                    "latest_date": "2026-06-29",
                },
                {"game_key": "pl3", "latest_issue": "", "latest_date": ""},
                {
                    "game_key": "kl8",
                    "latest_issue": "2026189",
                    "latest_date": "2026-07-12",
                },
                {
                    "game_key": "pl5",
                    "latest_issue": "2026189",
                    "latest_date": "2026-07-12",
                },
            ]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return [
                {
                    "game_key": "3d",
                    "status": "failed",
                    "error": "timeout\nretry exhausted",
                    "finished_at": "2026-07-12T05:00:00+00:00",
                },
                {
                    "game_key": "3d",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T04:00:00+00:00",
                },
                {
                    "game_key": "ssq",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T03:00:00+00:00",
                },
            ]

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.get("/api/health?today=2026-07-12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["service"] == "ok"
    assert set(payload["data"]) == {"ssq", "dlt", "3d", "pl3", "kl8"}
    assert payload["data"]["ssq"]["status"] == "fresh"
    assert payload["data"]["dlt"]["status"] == "attention"
    assert payload["data"]["3d"] == {
        "status": "stale",
        "latest_issue": "2026182",
        "latest_date": "2026-06-29",
        "staleness_days": 13,
        "can_claim_current": False,
        "message": "数据停留在第2026182期，暂不提供本期结论",
        "last_successful_update": "2026-07-12T04:00:00+00:00",
        "sync_error": "timeout retry exhausted",
    }
    assert payload["data"]["pl3"]["status"] == "empty"
    assert payload["data"]["kl8"]["can_claim_current"] is True


def test_health_returns_degraded_when_repository_read_fails_without_leaking_error():
    class Repo:
        def list_games(self):
            raise sqlite3.DatabaseError("database is locked: /secret/path")

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "error",
        "data": {},
        "error": "data repository unavailable",
    }
    assert "secret" not in response.text


def test_health_rejects_malformed_today_query():
    class Repo:
        def list_games(self):
            return []

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return []

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/health?today=not-a-date"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_health_uses_per_game_logs_when_one_game_has_more_than_global_limit():
    class Repo:
        def list_games(self):
            return [
                {"game_key": "ssq", "latest_issue": "2026190", "latest_date": "2026-07-12"},
                {"game_key": "dlt", "latest_issue": "25080", "latest_date": "2026-07-12"},
            ]

        def recent_crawl_logs(self, limit=20):
            return [
                {
                    "game_key": "ssq",
                    "status": "success",
                    "error": "",
                    "finished_at": f"2026-07-12T{i:02d}:00:00+00:00",
                }
                for i in range(20)
            ]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return [
                {
                    "game_key": "dlt",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T23:00:00+00:00",
                },
                {
                    "game_key": "ssq",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T19:00:00+00:00",
                },
            ]

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.get("/api/health?today=2026-07-12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["dlt"]["last_successful_update"] == "2026-07-12T23:00:00+00:00"


def test_health_status_is_ok_when_visible_games_are_claimable():
    class Repo:
        def list_games(self):
            return [
                {"game_key": key, "latest_issue": "2026190", "latest_date": "2026-07-12"}
                for key in ["ssq", "dlt", "3d", "pl3", "kl8"]
            ]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return []

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.get("/api/health?today=2026-07-12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert all(game["status"] == "fresh" for game in payload["data"].values())


def test_root_serves_frontend_shell():
    response = client.get("/")

    assert response.status_code == 200
    assert "玄金私享盘" in response.text
    assert "开始起盘" in response.text
    assert "生成模式" in response.text
    assert 'id="predictionResults" hidden' in response.text
    assert 'id="masterRitual"' in response.text
    assert "取号思路" in response.text
    assert 'id="credibilityChain"' in response.text
    assert 'id="fortuneHistory"' in response.text
    assert "我的历史财运号" in response.text
    assert 'id="profileBook"' in response.text
    assert 'id="dailyFortuneCalendar"' in response.text
    assert "我的记录" in response.text
    assert "近期开奖日" in response.text
    assert 'id="dailyFortuneSign"' in response.text
    assert 'id="ritualSteps"' in response.text
    assert "今日财签" in response.text
    assert "起盘过程" in response.text
    assert 'id="interpretationLayers"' in response.text
    assert 'id="generateFeedback"' in response.text
    assert "本命财格" in response.text
    assert "今日宜忌" in response.text
    assert 'class="header-nav"' in response.text
    assert 'aria-label="页面目录"' in response.text
    assert 'aria-current="page">预测首页' in response.text
    assert "meta-divider" not in response.text
    assert 'href="./analysis.html' in response.text
    assert 'href="./privacy.html"' in response.text
    assert 'rel="icon" href="./assets/black-gold-stone.png"' in response.text
    assert "隐私提示" not in response.text
    assert "第三方 AI" not in response.text
    assert "派生五行向量" not in response.text
    assert "短钩子" not in response.text
    assert "可信解释链" not in response.text
    assert 'href="./admin.html"' not in response.text
    assert 'id="analysisWorkbench"' not in response.text
    assert "<noscript>" in response.text
    assert "启用 JavaScript" in response.text
    assert 'value="张三"' not in response.text
    assert 'value="1990-01-01"' not in response.text
    assert 'name="birth_hour" value="辰"' not in response.text
    assert 'name="birth_place" value=' not in response.text
    assert 'name="current_city" value=' not in response.text
    assert 'name="gender"' not in response.text


def test_analysis_page_serves_analysis_workbench():
    response = client.get("/analysis.html")

    assert response.status_code == 200
    assert "分析中心" in response.text
    assert 'id="analysisWorkbench"' in response.text
    assert 'id="threeDToolbox"' in response.text
    assert 'id="threeDFreshness"' in response.text
    assert 'id="threeDPlanStrip"' in response.text
    assert 'id="threeDIssueBand"' in response.text
    assert 'id="threeDToolHome"' in response.text
    assert 'id="threeDToolWorkspace"' in response.text
    assert 'id="threeDToolPanels"' in response.text
    assert 'data-three-d-tool-panel="reduction"' not in response.text
    assert "./three-d-toolbox.js" in response.text
    assert "./workbench-3d.css" in response.text
    assert "./workbench-3d.js" in response.text
    assert "./analysis.js" in response.text
    assert "./research-strategy.js" in response.text
    assert response.text.index("./styles.css") < response.text.index("./workbench-3d.css")
    assert response.text.index("./workbench-3d.js") < response.text.index("./analysis.js")
    assert response.text.index("./analysis.js") < response.text.index("./research-strategy.js")
    assert 'id="researchViewTabs"' in response.text
    assert 'id="researchDataView"' in response.text
    assert 'id="researchStrategyView"' in response.text
    assert 'data-research-view="data"' in response.text
    assert 'data-research-view="strategy"' in response.text
    assert "策略验证" in response.text
    assert 'id="useStrategyButton"' in response.text
    assert 'id="strategyCompat"' not in response.text
    assert "开奖日历和提醒" in response.text
    assert "彩民常看" in response.text
    assert 'id="commonViewPanel"' in response.text
    assert 'class="header-nav"' in response.text
    assert 'aria-label="页面目录"' in response.text
    assert 'aria-current="page">研究中心' in response.text
    assert "meta-divider" not in response.text
    assert 'href="./admin.html"' not in response.text


def test_strategy_page_serves_redirect_shell():
    response = client.get("/strategy.html")

    assert response.status_code == 200
    assert "策略实验室" in response.text
    assert "./strategy-redirect.js" in response.text
    assert "./strategy.js" not in response.text
    assert 'id="strategyLab"' not in response.text
    assert 'class="header-nav"' in response.text
    assert 'aria-label="页面目录"' in response.text
    assert "meta-divider" not in response.text
    assert 'href="./admin.html"' not in response.text


def test_result_page_serves_fortune_detail_shell():
    response = client.get("/result.html")

    assert response.status_code == 200
    assert "财运号详情" in response.text
    assert 'id="resultDetail"' in response.text
    assert 'id="posterCanvas"' in response.text
    assert 'class="header-nav"' in response.text
    assert 'aria-label="页面目录"' in response.text
    assert 'aria-current="page">财运详情' in response.text
    assert "meta-divider" not in response.text
    assert "./result.js" in response.text
    assert 'href="./privacy.html"' in response.text
    assert "仅限成年人娱乐与数据分析" in response.text
    assert "不销售彩票" in response.text
    assert "不构成投注建议" in response.text


def test_privacy_page_serves_ai_data_boundary():
    response = client.get("/privacy.html")

    assert response.status_code == 200
    text = response.text
    assert "隐私与 AI 数据边界" in text
    assert "姓名" in text
    assert "出生日期" in text
    assert "出生地" in text
    assert "当前城市" in text
    assert "服务器端" in text
    assert "不会把原始姓名、精确出生日期、出生时辰地支、出生地或当前城市直接发送给第三方 AI" in text
    assert "派生的五行向量" in text
    assert "birth_vector 是由出生日期和已知出生时辰粗略派生的五行分布" in text
    assert "不是原始出生日期或原始出生时辰" in text
    assert "是否知道出生时辰" in text
    assert "历法类型" in text
    assert "出生地与当前城市关系" in text
    assert "same / different / incomplete" in text
    assert "只按去除首尾空白、压缩空白和大小写归一后的文本精确相等判断" in text
    assert "不会做行政区划后缀等价" in text
    assert "本地历史" in text
    assert "可在首页清空" in text
    assert "保存方案" in text
    assert "首页财运历史只保存在当前浏览器的 Local Storage" in text
    assert "不会上传为云端财运记录" in text
    assert "可在首页清空" in text
    assert "仅限成年人娱乐与数据分析" in text
    assert "不销售彩票" in text
    assert "不承诺中奖" in text
    assert "不承诺收益" in text
    assert "不构成投注建议" in text
    assert "全部个人处理都在浏览器" not in text
    assert "所有个人处理都在浏览器" not in text
    assert "零存储" not in text


def test_readme_documents_local_fortune_history_boundary():
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )

    assert "浏览器本地历史可能保存精简摘要，可在首页清空" in text
    assert "birth_vector 是由出生日期和已知出生时辰粗略派生的五行分布" in text
    assert "不是原始出生日期或原始出生时辰" in text
    assert "location_relation 只按去除首尾空白、压缩空白和大小写归一后的文本精确相等判断" in text
    assert "不会做行政区划后缀等价" in text
    assert "首页财运历史只写入当前浏览器的 Local Storage" in text
    assert "不会上传为云端财运记录" in text


def test_admin_page_serves_data_backend_shell():
    response = client.get("/admin.html")

    assert response.status_code == 200
    assert "数据后台" in response.text
    assert 'id="dataAdmin"' in response.text
    assert 'id="adminActionPlan"' in response.text
    assert 'id="adminSettings"' in response.text
    assert 'id="adminTasks"' in response.text
    assert 'id="cwlCrawlForm"' not in response.text
    assert 'id="sportsCrawlForm"' not in response.text
    assert "福彩官方补采" not in response.text
    assert "体彩官方补采" not in response.text
    assert 'name="source"' in response.text
    assert 'name="pages"' in response.text
    assert "玄学算法配置" in response.text
    assert "后台任务队列" in response.text
    assert 'class="header-nav"' in response.text
    assert 'aria-label="页面目录"' in response.text
    assert 'aria-current="page">数据后台' in response.text
    assert "meta-divider" not in response.text
    assert "./admin.js?v=" in response.text
    assert "./styles.css?v=" in response.text


def test_frontend_assets_are_served():
    response = client.get("/app.js")

    assert response.status_code == 200
    assert "loadGames" in response.text
    assert "大乐透" in response.text
    assert "排列3" in response.text
    assert "userInitiated" in response.text
    assert "scrollIntoView" in response.text
    assert "fortune_mode" in response.text
    assert "localStorage" in response.text
    assert "renderFortuneHistory" in response.text
    assert "renderProfileBook" in response.text
    assert "renderDailyFortuneCalendar" in response.text
    assert "reviewFortuneHistory" in response.text
    assert "/api/review/" in response.text
    assert "renderMasterRitual" in response.text
    assert "renderDailyFortuneSign" in response.text
    assert "renderRitualSteps" in response.text
    assert "daily_fortune_sign" in response.text
    assert "master_ritual" in response.text
    assert "ritual_steps" in response.text
    assert "avoid_reasons" in response.text
    assert "predictionRequestId" in response.text
    assert "isLatestRequest" in response.text
    assert "FortuneMotion" in response.text
    assert "起盘失败，请稍后重试" in response.text
    assert "CLIENT_ID_KEY" in response.text
    assert 'const VISIBLE_GAME_KEYS = ["ssq", "dlt", "3d", "pl3", "kl8"];' in response.text


def test_home_includes_cinematic_motion_assets_and_stage():
    response = client.get("/")
    motion_js = client.get("/motion.js")
    motion_css = client.get("/motion.css")

    assert response.status_code == 200
    assert './motion.css?v=' in response.text
    assert './motion.js?v=' in response.text
    assert response.text.index("./motion.js?v=") < response.text.index("./app.js?v=")
    assert 'id="ritualStage"' in response.text
    assert 'id="motionStatus"' in response.text
    assert 'id="motionNumbers"' in response.text
    assert motion_js.status_code == 200
    assert "window.FortuneMotion" in motion_js.text
    assert motion_css.status_code == 200
    assert ".ritual-stage" in motion_css.text


def test_product_client_is_loaded_before_page_scripts():
    pages = [
        ("/", "./app.js?v=", True),
        ("/analysis.html", "./analysis.js?v=", False),
        ("/result.html", "./result.js?v=", False),
    ]

    for path, page_script, has_motion in pages:
        response = client.get(path)
        html = response.text

        assert response.status_code == 200
        assert "./product-client.js?v=20260713-product-client-v2" in html
        assert html.index("./product-client.js?v=") < html.index(page_script)
        if path == "/analysis.html":
            assert "./workbench-3d.js?v=" in html
            assert "./workbench-3d.css?v=" in html
            assert html.index("./product-client.js?v=") < html.index("./workbench-3d.js?v=")
            assert html.index("./workbench-3d.js?v=") < html.index("./analysis.js?v=")
        if has_motion:
            assert html.index("./motion.js?v=") < html.index("./product-client.js?v=")
            assert html.index("./motion.js?v=") < html.index("./app.js?v=")


def test_product_client_asset_is_served():
    response = client.get("/product-client.js")

    assert response.status_code == 200
    assert "window.LotteryProduct" in response.text
    assert "lotteryLuck.clientId.v1" in response.text
    assert "lotteryLuck.pendingPlans.v1" in response.text
    assert "Math.random" not in response.text


def test_3d_workbench_assets_are_served_and_do_not_use_inner_html():
    js = client.get("/workbench-3d.js")
    toolbox = client.get("/three-d-toolbox.js")
    css = client.get("/workbench-3d.css")

    assert js.status_code == 200
    assert toolbox.status_code == 200
    assert css.status_code == 200
    assert "window.ThreeDWorkbench" in js.text
    assert "window.ThreeDToolbox" in toolbox.text
    assert "LotteryProduct.request" in js.text
    assert "LotteryProduct.listPlans" in js.text
    assert "LotteryProduct.createPlan" not in js.text
    assert "LotteryProduct.updatePlan" not in js.text
    # Both files of the 3D toolbox render API text into the DOM, so both stay on DOM APIs.
    for source in (js.text, toolbox.text):
        assert ".innerHTML" not in source
        assert "insertAdjacentHTML" not in source
    assert "#threeDToolbox" in css.text
    assert "overflow-x: auto" in css.text


def test_admin_frontend_asset_is_served():
    response = client.get("/admin.js")

    assert response.status_code == 200
    assert "loadHealth" in response.text
    assert "loadSettings" in response.text
    assert "renderSettings" in response.text
    assert "loadTasks" in response.text
    assert "runAdminTask" in response.text
    assert "sessionStorage" in response.text
    assert "localStorage" not in response.text
    assert "X-Lottery-Admin-Token" in response.text
    assert "handleUnauthorized" in response.text
    assert "lockAdmin" in response.text
    assert "renderActionPlan" in response.text
    assert "providerDefaults" in response.text
    assert 'sports: "dlt,pl3"' in response.text
    assert 'sports: "dlt,pl3,pl5"' not in response.text
    assert "setCrawlBusy" not in response.text
    assert "renderCrawlResult" not in response.text
    assert "右侧官方补采表单" not in response.text
    assert "/api/admin/data-health" in response.text
    assert "/api/admin/settings" in response.text
    assert "/api/admin/tasks" in response.text
    assert "/api/admin/crawl/cwl" not in response.text
    assert "/api/admin/crawl/sports" not in response.text


def test_admin_settings_endpoint_returns_metaphysics_config():
    response = client.get("/api/admin/settings", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["metaphysics_weights"]["steady"]["personal_space"] == 40
    assert "短钩子" in payload["ai_copy_styles"][0]["label"]
    assert payload["prediction_quota"]["free_daily"] == 1
    assert payload["prediction_quota"]["member_daily"] == 20


def test_lifespan_initializes_product_event_and_plan_schema_before_serving(monkeypatch):
    calls = []
    monkeypatch.setattr("lottery_luck.api.remote_database_enabled", lambda: True)

    class Repo:
        def initialize_product_events_schema(self):
            calls.append("events")

        def initialize_plan_schema(self):
            calls.append("plans")

        def initialize_write_limits_schema(self):
            calls.append("limits")

        def prune_product_events(self):
            calls.append("prune-events")

        def prune_write_limits(self):
            calls.append("prune-limits")

    monkeypatch.setattr("lottery_luck.api.LotteryRepository", lambda: Repo())
    monkeypatch.setattr(
        "lottery_luck.api.auto_update.config_from_env",
        lambda: SimpleNamespace(enabled=False),
    )

    async def run_lifespan():
        async with app.router.lifespan_context(app):
            calls.append("serving")

    asyncio.run(run_lifespan())

    assert calls == [
        "events",
        "plans",
        "limits",
        "prune-events",
        "prune-limits",
        "serving",
    ]


def test_quota_status_endpoint_returns_configured_remaining(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    monkeypatch.setenv("LOTTERY_LUCK_SETTINGS_PATH", str(tmp_path / "missing.json"))
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.get(
            "/api/quota/status",
            headers={"X-Lottery-Client-Id": "client-api"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["tracked"] is True
    assert payload["remaining_total"] == 4
    assert payload["config"]["free_daily"] == 1


def test_prediction_ignores_requested_quota_when_disabled(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "false")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(monkeypatch, _engine_payload(game_key="ssq"))

    class Repo:
        def __init__(self):
            self.quota_calls = []

        def consume_prediction_quota(self, client_id, game_key, mode_key):
            self.quota_calls.append(("consume", client_id, game_key, mode_key))
            return {"allowed": True, "quota": {"remaining_total": 12}}

        def quota_status(self, client_id):
            self.quota_calls.append(("status", client_id))
            return {"remaining_total": 12}

    repo = Repo()
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-quota-disabled"},
            json={**_predict_request("ssq"), "consume_quota": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "quota" not in payload
    assert repo.quota_calls == []


def test_predict_with_client_quota_returns_unlock_payload_when_exhausted(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "prediction_quota": {
                    "free_daily": 0,
                    "new_user_bonus": 0,
                    "member_daily": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOTTERY_LUCK_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-empty"},
            json={
                "game_key": "ssq",
                "name": "张三",
                "birth_date": "1990-05-17",
                "consume_quota": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["quota_exhausted"] is True
    assert payload["quota"]["remaining_total"] == 0
    assert "解锁" in payload["unlock"]["title"]
    assert "numbers" not in payload


def test_commercial_routes_are_hidden_from_openapi():
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/quota/status" not in paths
    assert "/api/quota/mock-unlock" not in paths
    assert "/api/cloud/fortune-records" not in paths


def test_commercial_routes_are_dormant_when_quota_is_disabled(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "false")
    headers = {"X-Lottery-Client-Id": "client-disabled"}

    responses = (
        client.get("/api/quota/status", headers=headers),
        client.post(
            "/api/quota/mock-unlock",
            headers=headers,
            json={"kind": "package", "units": 6},
        ),
        client.post(
            "/api/cloud/fortune-records",
            headers=headers,
            json={"record": {"id": "disabled", "game_key": "ssq"}},
        ),
        client.get("/api/cloud/fortune-records", headers=headers),
    )

    assert [response.status_code for response in responses] == [404, 404, 404, 404]


def test_mock_unlock_and_cloud_record_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    headers = {"X-Lottery-Client-Id": "client-cloud"}
    try:
        unlock = client.post(
            "/api/quota/mock-unlock",
            headers=headers,
            json={"kind": "package", "units": 6},
        )
        save = client.post(
            "/api/cloud/fortune-records",
            headers=headers,
            json={"record": {"id": "r-cloud", "game_key": "ssq", "number_text": "01 02 03"}},
        )
        records = client.get("/api/cloud/fortune-records", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert unlock.status_code == 200
    assert unlock.json()["quota"]["is_paid"] is True
    assert save.status_code == 200
    assert save.json()["record"]["storage_state"] == "cloud"
    assert records.json()["records"][0]["id"] == "r-cloud"


@pytest.mark.parametrize(
    "record",
    [
        {"id": "bad-unknown", "game_key": "ssq", "number_text": "01", "extra": "nope"},
        {
            "id": "bad-sensitive",
            "game_key": "ssq",
            "number_text": "01",
            "review": {"fullName": "隐私姓名-Sentinel"},
        },
        {"id": "bad-oversize", "game_key": "ssq", "number_text": "x" * (260 * 1024)},
    ],
)
def test_cloud_record_endpoint_rejects_unknown_sensitive_and_oversize_payloads(
    tmp_path, record, monkeypatch
):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    headers = {"X-Lottery-Client-Id": "client-cloud"}
    try:
        unlock = client.post(
            "/api/quota/mock-unlock",
            headers=headers,
            json={"kind": "package", "units": 6},
        )
        response = client.post(
            "/api/cloud/fortune-records",
            headers=headers,
            json={"record": record},
        )
        records = client.get("/api/cloud/fortune-records", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert unlock.status_code == 200
    assert response.status_code == 400
    assert records.json()["records"] == []
    assert "隐私姓名-Sentinel" not in response.text


def test_cloud_record_endpoint_does_not_echo_pii_looking_unknown_field_name(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    headers = {"X-Lottery-Client-Id": "client-cloud"}
    pii_field_name = "birthDate_1988_12_31_隐私姓名"
    try:
        client.post(
            "/api/quota/mock-unlock",
            headers=headers,
            json={"kind": "package", "units": 6},
        )
        response = client.post(
            "/api/cloud/fortune-records",
            headers=headers,
            json={
                "record": {
                    "id": "bad-unknown-pii-key",
                    "game_key": "ssq",
                    "number_text": "01",
                    pii_field_name: "not stored",
                }
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert pii_field_name not in response.text
    assert "birthDate" not in response.text
    assert "1988_12_31" not in response.text
    assert "隐私姓名" not in response.text


def test_product_event_endpoint_accepts_allowed_event_and_persists_without_id(tmp_path):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/events",
            headers={"X-Lottery-Client-Id": " client-api "},
            json={
                "event_name": "prediction_completed",
                "properties": {
                    "game_key": "ssq",
                    "source_type": "fortune",
                    "mode": "steady",
                    "window": 30,
                    "entry_count": 1,
                    "candidate_count": 5,
                    "freshness_status": "fresh",
                    "review_status": None,
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    with sqlite3.connect(repo.db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT client_id, event_name, properties
            FROM product_events
            """
        ).fetchone()
    assert dict(row) == {
        "client_id": "client-api",
        "event_name": "prediction_completed",
        "properties": json.dumps(
            {
                "game_key": "ssq",
                "source_type": "fortune",
                "mode": "steady",
                "window": 30,
                "entry_count": 1,
                "candidate_count": 5,
                "freshness_status": "fresh",
                "review_status": None,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


def test_product_event_endpoint_requires_client_id(tmp_path):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/events",
            json={"event_name": "workbench_opened", "properties": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "X-Lottery-Client-Id is required"}


def test_product_event_endpoint_returns_429_before_writing_when_rate_limited():
    class LimitedRepo:
        def consume_write_limit(self, **kwargs):
            return False

        def record_product_event(self, **kwargs):
            raise AssertionError("rate-limited event must not be written")

    app.dependency_overrides[get_repository] = lambda: LimitedRepo()
    try:
        response = client.post(
            "/api/events",
            headers={"X-Lottery-Client-Id": "client-api"},
            json={"event_name": "workbench_opened", "properties": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json() == {"detail": "write rate limit exceeded"}
    assert response.headers["Retry-After"]


@pytest.mark.parametrize(
    "payload",
    [
        {"event_name": "invalid_隐私姓名", "properties": {}},
        {"event_name": "plan_saved", "properties": {"name": "隐私姓名-Sentinel"}},
        {"event_name": "plan_saved", "properties": {"numbers": "01 02 03"}},
        {"event_name": "plan_saved", "properties": {"game_key": {"nested": "value"}}},
        {"event_name": "plan_saved", "properties": {"entry_count": -1}},
        {"event_name": "plan_saved", "properties": {"entry_count": True}},
        {"event_name": "plan_saved", "properties": {"entry_count": 10001}},
        {"event_name": "plan_saved", "properties": {"window": 1.5}},
        {"event_name": "plan_saved", "properties": {"window": 90}},
        {"event_name": "plan_saved", "properties": {"freshness_status": True}},
        {"event_name": "plan_saved", "properties": {"source_type": "home"}},
    ],
)
def test_product_event_endpoint_returns_generic_422_for_domain_validation(
    tmp_path, payload
):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/events",
            headers={"X-Lottery-Client-Id": "client-api"},
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid product event"}
    assert "隐私姓名" not in response.text
    assert "01 02 03" not in response.text
    with sqlite3.connect(repo.db_path) as connection:
        exists = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'product_events'
            """
        ).fetchone()
        count = (
            connection.execute("SELECT COUNT(*) FROM product_events").fetchone()[0]
            if exists
            else 0
        )
    assert count == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"event_name": "x" * 65 + "隐私姓名", "properties": {}},
        {"event_name": "plan_saved", "properties": ["name", "隐私姓名-Sentinel"]},
        {
            "event_name": "plan_saved",
            "properties": {},
            "birth_date_1988_12_31_隐私姓名": "not allowed",
        },
    ],
)
def test_product_event_endpoint_returns_generic_422_for_request_validation(
    tmp_path, payload
):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/events",
            headers={"X-Lottery-Client-Id": "client-api"},
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid product event"}
    assert "隐私姓名" not in response.text
    assert "隐私姓名-Sentinel" not in response.text
    assert "1988_12_31" not in response.text


def test_product_event_endpoint_rejects_oversized_body_before_json_parse(tmp_path):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    pii_payload = "隐私姓名-Sentinel" + ("x" * 9000)
    try:
        response = client.post(
            "/api/events",
            headers={
                "X-Lottery-Client-Id": "client-api",
                "Content-Type": "application/json",
            },
            content=(
                '{"event_name":"plan_saved","properties":{"game_key":"'
                + pii_payload
                + '"}}'
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json() == {"detail": "product event payload too large"}
    assert "隐私姓名-Sentinel" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        [
            (b"x-lottery-client-id", b"client-api"),
            (b"content-type", b"application/json"),
        ],
        [
            (b"x-lottery-client-id", b"client-api"),
            (b"content-type", b"application/json"),
            (b"content-length", b"not-a-number"),
        ],
        [
            (b"x-lottery-client-id", b"client-api"),
            (b"content-type", b"application/json"),
            (b"content-length", b"12"),
        ],
    ],
)
def test_product_event_asgi_body_cap_uses_actual_body_size_for_untrusted_lengths(
    headers,
):
    body = (
        b'{"event_name":"plan_saved","properties":{"game_key":"'
        + "隐私姓名-Sentinel".encode("utf-8")
        + (b"x" * 9000)
        + b'"}}'
    )

    status, response_text = _asgi_post_events(body, headers)

    assert status == 413
    assert json.loads(response_text) == {"detail": "product event payload too large"}
    assert "隐私姓名-Sentinel" not in response_text


def test_product_event_asgi_body_cap_replays_normal_body_for_fastapi_parsing():
    class RecordingRepo:
        def __init__(self):
            self.calls = []

        def record_product_event(self, **kwargs):
            self.calls.append(kwargs)
            return {}

    repo = RecordingRepo()
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        status, response_text = _asgi_post_events(
            b'{"event_name":"plan_saved","properties":{"game_key":"ssq"}}',
            [
                (b"x-lottery-client-id", b"client-api"),
                (b"content-type", b"application/json"),
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 202
    assert json.loads(response_text) == {"accepted": True}
    assert repo.calls == [
        {
            "client_id": "client-api",
            "event_name": "plan_saved",
            "properties": {"game_key": "ssq"},
        }
    ]


def test_product_event_endpoint_returns_503_for_unavailable_storage_without_echo():
    class UnavailableRepo:
        def record_product_event(self, **kwargs):
            raise sqlite3.OperationalError("database is locked: /secret/path")

    app.dependency_overrides[get_repository] = lambda: UnavailableRepo()
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/events",
            headers={"X-Lottery-Client-Id": "client-api"},
            json={
                "event_name": "plan_saved",
                "properties": {"game_key": "ssq", "source_type": "manual"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "product event unavailable"}
    assert "secret" not in response.text
    assert "locked" not in response.text


def test_product_event_endpoint_returns_503_when_schema_unexpectedly_missing(tmp_path):
    repo = _raw_quota_db_without_product_events_schema(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/events",
            headers={"X-Lottery-Client-Id": "client-api"},
            json={"event_name": "plan_saved", "properties": {"game_key": "ssq"}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "product event unavailable"}
    with sqlite3.connect(repo.db_path) as connection:
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


def test_product_events_has_no_public_get_route():
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/events"
    ]

    assert routes
    assert all("GET" not in getattr(route, "methods", set()) for route in routes)


def test_admin_tasks_endpoint_returns_recent_tasks():
    class AdminRepo:
        def recent_tasks(self, limit=20):
            return [
                {
                    "id": 7,
                    "kind": "crawl",
                    "provider": "cwl",
                    "game_keys": ["ssq"],
                    "status": "success",
                    "result": {"wrote_count": 1},
                    "error": "",
                    "created_at": "2026-06-18T08:00:00+00:00",
                    "started_at": "2026-06-18T08:00:01+00:00",
                    "finished_at": "2026-06-18T08:00:02+00:00",
                }
            ]

    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.get("/api/admin/tasks", headers=ADMIN_HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["tasks"][0]["id"] == 7
    assert response.json()["tasks"][0]["result"]["wrote_count"] == 1


def test_allowed_origins_enable_cors_for_configured_origin():
    script = """
from fastapi.testclient import TestClient
from lottery_luck.api import app

response = TestClient(app).options(
    "/api/health",
    headers={
        "Origin": "https://app.example.com",
        "Access-Control-Request-Method": "GET",
    },
)
assert response.headers.get("access-control-allow-origin") == "https://app.example.com"
"""
    env = {
        **os.environ,
        "PYTHONPATH": os.getcwd(),
        "ALLOWED_ORIGINS": "https://app.example.com, https://admin.example.com",
        "LOTTERY_LUCK_SERVE_STATIC": "false",
        "LOTTERY_LUCK_AUTO_UPDATE_ENABLED": "false",
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_cron_requires_bearer_secret_and_never_runs_without_it(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    calls = []

    def fail_if_called(**kwargs):
        calls.append(kwargs)
        raise AssertionError("cron must not run without the configured bearer secret")

    monkeypatch.setattr("lottery_luck.api.scheduler.run_once", fail_if_called)

    unset = client.get("/api/cron/crawl")

    monkeypatch.setenv("CRON_SECRET", "cron-secret-123456")
    missing = client.get("/api/cron/crawl")
    wrong = client.get(
        "/api/cron/crawl",
        headers={"Authorization": "Bearer wrong-secret"},
    )

    assert unset.status_code == 401
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert calls == []


def test_authorized_cron_runs_cwl_then_mirrored_sports(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "cron-secret-123456")
    calls = []

    def fake_run_once(**kwargs):
        calls.append(kwargs)
        return {
            "task": {
                "id": len(calls),
                "provider": kwargs["provider"],
                "result": {
                    "provider": kwargs["provider"],
                    "source": kwargs.get("source"),
                    "games": kwargs["games"],
                },
            }
        }

    monkeypatch.setattr("lottery_luck.api.scheduler.run_once", fake_run_once)
    monkeypatch.setattr(
        "lottery_luck.api._task_games",
        lambda provider, games: ["ssq", "3d", "kl8"]
        if provider == "cwl"
        else ["dlt", "pl3", "pl5"],
    )

    response = client.get(
        "/api/cron/crawl",
        headers={"Authorization": "Bearer cron-secret-123456"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert [call["provider"] for call in calls] == ["cwl", "sports"]
    assert calls[0]["games"] == ["ssq", "3d", "kl8"]
    assert calls[1]["games"] == ["dlt", "pl3"]
    assert calls[1]["source"] == "mirror"
    assert response.json()["results"][0]["result"]["games"] == ["ssq", "3d", "kl8"]
    assert response.json()["results"][1]["result"]["games"] == ["dlt", "pl3"]
    assert response.json()["results"][1]["result"]["source"] == "mirror"


def test_admin_run_task_endpoint_creates_runs_and_finishes_cwl_task(monkeypatch):
    class AdminRepo:
        def __init__(self):
            self.finished = None

        def create_task(self, *, kind, provider, game_keys, payload):
            return {
                "id": 8,
                "kind": kind,
                "provider": provider,
                "game_keys": game_keys,
                "payload": payload,
                "status": "queued",
                "result": {},
                "error": "",
            }

        def start_task(self, task_id):
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            self.finished = {
                "id": task_id,
                "status": status,
                "result": result or {},
                "error": error,
            }
            return self.finished

        def list_games(self):
            return []

        def recent_draw_dates_by_game(self, limit_per_game=500):
            return {}

        def recent_crawl_logs(self, limit=20):
            return []

    repo = AdminRepo()
    calls = []

    def fake_crawl(games, **kwargs):
        calls.append((games, kwargs))
        return {
            "provider": "cwl",
            "wrote_count": 2,
            "failed_games": [],
            "games": [{"game_key": "ssq", "status": "success", "wrote_count": 2}],
        }

    monkeypatch.setattr("lottery_luck.api.crawl_cwl_games", fake_crawl)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/admin/tasks/run",
            headers=ADMIN_HEADERS,
            json={"provider": "cwl", "games": ["ssq"], "page_size": 50},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["task"]["status"] == "success"
    assert payload["task"]["result"]["wrote_count"] == 2
    assert calls == [(["ssq"], {"page_size": 50})]


def test_admin_run_task_endpoint_records_detailed_crawl_errors(monkeypatch):
    class AdminRepo:
        def create_task(self, *, kind, provider, game_keys, payload):
            return {"id": 9, "kind": kind, "provider": provider, "game_keys": game_keys}

        def start_task(self, task_id):
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            return {
                "id": task_id,
                "status": status,
                "result": result or {},
                "error": error,
            }

        def list_games(self):
            return []

        def recent_draw_dates_by_game(self, limit_per_game=500):
            return {}

        def recent_crawl_logs(self, limit=20):
            return []

    def fake_crawl(games, **kwargs):
        return {
            "provider": "cwl",
            "wrote_count": 0,
            "failed_games": ["ssq"],
            "games": [
                {
                    "game_key": "ssq",
                    "status": "failed",
                    "wrote_count": 0,
                    "error": "Redirect response '302 Moved Temporarily'",
                }
            ],
        }

    monkeypatch.setattr("lottery_luck.api.crawl_cwl_games", fake_crawl)
    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.post(
            "/api/admin/tasks/run",
            headers=ADMIN_HEADERS,
            json={"provider": "cwl", "games": ["ssq"], "page_size": 50},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["status"] == "failed"
    assert "ssq: Redirect response" in task["error"]


def test_result_frontend_asset_is_served():
    response = client.get("/result.js")

    assert response.status_code == 200
    assert "FORTUNE_HISTORY_KEY" in response.text
    assert "renderResultDetail" in response.text
    assert "renderMasterRitual" in response.text
    assert "renderDailyFortuneSign" in response.text
    assert "master_ritual" in response.text
    assert "daily_fortune_sign" in response.text
    assert "ritual_steps" in response.text
    assert "avoid_reasons" in response.text
    assert "drawSharePoster" in response.text


def test_analysis_asset_includes_common_view_and_research_shell():
    response = client.get("/analysis.js")

    assert response.status_code == 200
    assert "renderCommonView" in response.text
    assert "LotteryResearch" in response.text
    assert "researchSubscribers" in response.text


def test_research_strategy_asset_serves_isolated_module():
    response = client.get("/research-strategy.js")

    assert response.status_code == 200
    assert "window.LotteryResearch.subscribe" in response.text
    assert "lotteryLuck:strategyLab:" in response.text
    assert "needs-resave" in response.text
    assert "lottery_research_handoff_v1" in response.text
    assert "tool=conditional&source=strategy" in response.text


def test_frontend_styles_are_served():
    response = client.get("/styles.css")
    motion_response = client.get("/motion.css")

    assert response.status_code == 200
    assert "玄金" not in response.text
    assert motion_response.status_code == 200
    assert '[data-motion-state="running"]' in motion_response.text
    assert '[data-motion-state="waiting"]' in motion_response.text
    assert '[data-motion-state="complete"]' in motion_response.text
    assert "@keyframes motion-ball-land" in motion_response.text
    assert "@media (prefers-reduced-motion: reduce)" in motion_response.text
    assert "transform-origin: left;" in motion_response.text
    assert "transform: scaleX(calc(var(--motion-progress, 8) * 1%));" in motion_response.text
    assert "transition: transform 700ms var(--motion-ease);" in motion_response.text
    assert "transition: width 700ms var(--motion-ease);" not in motion_response.text
    assert "--gold" in response.text


def test_analysis_asset_includes_sports_lottery_tabs():
    analysis_response = client.get("/analysis.js")

    assert analysis_response.status_code == 200
    assert "大乐透" in analysis_response.text
    assert "排列3" in analysis_response.text
    assert 'const VISIBLE_GAME_KEYS = ["ssq", "dlt", "3d", "pl3", "kl8"];' in analysis_response.text


def test_admin_data_health_endpoint_returns_game_rows_and_logs():
    class AdminRepo:
        def list_games(self):
            return [
                {
                    "game_key": "dlt",
                    "game_name": "大乐透",
                    "provider": "sports",
                    "draw_count": 300,
                    "earliest_date": "2024-06-17",
                    "latest_date": "2026-06-15",
                    "latest_issue": "26066",
                }
            ]

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {"dlt": ["2026-06-15", "2026-06-13", "2026-06-10"]}

        def recent_crawl_logs(self, limit=20):
            return [
                {
                    "provider": "sports",
                    "game_key": "dlt",
                    "status": "success",
                    "finished_at": "2026-06-17T08:00:00+00:00",
                }
            ]

    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.get(
            "/api/admin/data-health?today=2026-06-17",
            headers=ADMIN_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["healthy_games"] == 1
    assert payload["games"][0]["game_key"] == "dlt"
    assert payload["logs"][0]["status"] == "success"


def test_admin_data_health_endpoint_hides_non_frontend_games():
    class AdminRepo:
        def list_games(self):
            return [
                {
                    "game_key": "ssq",
                    "game_name": "双色球",
                    "provider": "cwl",
                    "draw_count": 2026,
                    "earliest_date": "2013-01-01",
                    "latest_date": "2026-06-16",
                    "latest_issue": "2026068",
                },
                {
                    "game_key": "qlc",
                    "game_name": "七乐彩",
                    "provider": "cwl",
                    "draw_count": 2025,
                    "earliest_date": "2013-01-02",
                    "latest_date": "2026-06-13",
                    "latest_issue": "2026066",
                },
                {
                    "game_key": "pl5",
                    "game_name": "排列5",
                    "provider": "sports",
                    "draw_count": 300,
                    "earliest_date": "2025-08-07",
                    "latest_date": "2026-06-16",
                    "latest_issue": "26157",
                },
            ]

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {
                "ssq": ["2026-06-16", "2026-06-14", "2026-06-11"],
                "qlc": ["2026-06-13"],
                "pl5": ["2026-06-16"],
            }

        def recent_crawl_logs(self, limit=20):
            return []

    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.get(
            "/api/admin/data-health?today=2026-06-17",
            headers=ADMIN_HEADERS,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [game["game_key"] for game in payload["games"]] == ["ssq"]
    assert payload["kpis"]["total_games"] == 1
    assert payload["kpis"]["total_draws"] == 2026
    assert "qlc" not in payload["commands"]["cwl"]
    assert "pl5" not in payload["commands"]["sports_browser"]


def test_admin_run_task_defaults_to_visible_sports_games(monkeypatch):
    class AdminRepo:
        def create_task(self, *, kind, provider, game_keys, payload):
            return {"id": 10, "kind": kind, "provider": provider, "game_keys": game_keys}

        def start_task(self, task_id):
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            return {"id": task_id, "status": status, "result": result or {}, "error": error}

        def list_games(self):
            return []

        def recent_draw_dates_by_game(self, limit_per_game=500):
            return {}

        def recent_crawl_logs(self, limit=20):
            return []

    calls = []

    def fake_crawl(games, **kwargs):
        calls.append((games, kwargs))
        return {
            "provider": "sports",
            "source": kwargs["source"],
            "wrote_count": 0,
            "failed_games": [],
            "games": [],
        }

    monkeypatch.setattr("lottery_luck.api.crawl_sports_games", fake_crawl)
    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.post(
            "/api/admin/tasks/run",
            headers=ADMIN_HEADERS,
            json={"provider": "sports", "games": [], "source": "auto"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][0] == ["dlt", "pl3"]


def test_admin_sports_crawl_endpoint_runs_crawler_and_returns_refreshed_health(monkeypatch):
    class AdminRepo:
        def __init__(self):
            self.created = None
            self.started = []
            self.finished = None

        def create_task(self, *, kind, provider, game_keys, payload):
            self.created = {
                "id": 11,
                "kind": kind,
                "provider": provider,
                "game_keys": game_keys,
                "payload": payload,
            }
            return self.created

        def start_task(self, task_id):
            self.started.append(task_id)
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            self.finished = {
                "id": task_id,
                "status": status,
                "result": result or {},
                "error": error,
            }
            return self.finished

        def list_games(self):
            return [
                {
                    "game_key": "dlt",
                    "game_name": "大乐透",
                    "provider": "sports",
                    "draw_count": 301,
                    "earliest_date": "2024-06-17",
                    "latest_date": "2026-06-15",
                    "latest_issue": "26066",
                }
            ]

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {"dlt": ["2026-06-15", "2026-06-13", "2026-06-10"]}

        def recent_crawl_logs(self, limit=20):
            return []

    calls = []

    def fake_crawl(games, **kwargs):
        calls.append((games, kwargs))
        return {
            "provider": "sports",
            "source": kwargs["source"],
            "wrote_count": 1,
            "failed_games": [],
            "games": [{"game_key": "dlt", "status": "success", "wrote_count": 1, "error": ""}],
        }

    monkeypatch.setattr("lottery_luck.api.crawl_sports_games", fake_crawl)
    repo = AdminRepo()
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/admin/crawl/sports",
            headers=ADMIN_HEADERS,
            json={"games": ["dlt"], "source": "direct", "page_size": 50, "pages": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["crawl"]["wrote_count"] == 1
    assert payload["health"]["games"][0]["draw_count"] == 301
    assert repo.created["provider"] == "sports"
    assert repo.started == [11]
    assert repo.finished["status"] == "success"
    assert repo.finished["result"] == payload["crawl"]
    assert calls == [
        (
            ["dlt"],
            {
                "source": "direct",
                "page_size": 50,
                "page_no": 1,
                "pages": 2,
                "timeout_ms": 30000,
                "headless": True,
            },
        )
    ]


def test_admin_cwl_crawl_endpoint_runs_crawler_and_returns_refreshed_health(monkeypatch):
    class AdminRepo:
        def __init__(self):
            self.created = None
            self.started = []
            self.finished = None

        def create_task(self, *, kind, provider, game_keys, payload):
            self.created = {
                "id": 12,
                "kind": kind,
                "provider": provider,
                "game_keys": game_keys,
                "payload": payload,
            }
            return self.created

        def start_task(self, task_id):
            self.started.append(task_id)
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            self.finished = {
                "id": task_id,
                "status": status,
                "result": result or {},
                "error": error,
            }
            return self.finished

        def list_games(self):
            return [
                {
                    "game_key": "ssq",
                    "game_name": "双色球",
                    "provider": "cwl",
                    "draw_count": 2026,
                    "earliest_date": "2013-01-01",
                    "latest_date": "2026-06-16",
                    "latest_issue": "2026068",
                }
            ]

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {"ssq": ["2026-06-16", "2026-06-14", "2026-06-11"]}

        def recent_crawl_logs(self, limit=20):
            return []

    calls = []

    def fake_crawl(games, **kwargs):
        calls.append((games, kwargs))
        return {
            "provider": "cwl",
            "source": "api",
            "wrote_count": 2,
            "failed_games": [],
            "games": [{"game_key": "ssq", "status": "success", "wrote_count": 2, "error": ""}],
        }

    monkeypatch.setattr("lottery_luck.api.crawl_cwl_games", fake_crawl)
    repo = AdminRepo()
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.post(
            "/api/admin/crawl/cwl",
            headers=ADMIN_HEADERS,
            json={"games": ["ssq"], "page_size": 50},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["crawl"]["provider"] == "cwl"
    assert payload["crawl"]["wrote_count"] == 2
    assert payload["health"]["games"][0]["game_key"] == "ssq"
    assert repo.created["provider"] == "cwl"
    assert repo.started == [12]
    assert repo.finished["status"] == "success"
    assert repo.finished["result"] == payload["crawl"]
    assert calls == [(["ssq"], {"page_size": 50})]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/admin/crawl/cwl", {"games": ["ssq"], "page_size": 50}),
        ("/api/admin/crawl/sports", {"games": ["dlt"], "source": "direct"}),
    ],
)
def test_admin_crawl_endpoints_return_409_when_crawl_is_in_progress(monkeypatch, path, body):
    class AdminRepo:
        def list_games(self):
            return []

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {}

        def recent_crawl_logs(self, limit=20):
            return []

    def busy(**kwargs):
        raise scheduler.CrawlInProgressError("crawl already in progress")

    monkeypatch.setattr("lottery_luck.api.scheduler.run_once", busy)
    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.post(path, json=body, headers=ADMIN_HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "crawl already in progress" in response.json()["detail"]


@pytest.mark.parametrize(
    ("path", "body", "patch_target", "provider", "failed_game"),
    [
        (
            "/api/admin/crawl/cwl",
            {"games": ["ssq"], "page_size": 50},
            "lottery_luck.api.crawl_cwl_games",
            "cwl",
            "ssq",
        ),
        (
            "/api/admin/crawl/sports",
            {"games": ["dlt"], "source": "direct"},
            "lottery_luck.api.crawl_sports_games",
            "sports",
            "dlt",
        ),
    ],
)
def test_admin_crawl_endpoints_return_failed_payload_when_crawler_raises(
    monkeypatch,
    path,
    body,
    patch_target,
    provider,
    failed_game,
):
    class AdminRepo:
        def create_task(self, *, kind, provider, game_keys, payload):
            return {"id": 14, "kind": kind, "provider": provider, "game_keys": game_keys}

        def start_task(self, task_id):
            return {"id": task_id, "status": "running"}

        def finish_task(self, task_id, *, status, result=None, error=""):
            return {
                "id": task_id,
                "status": status,
                "result": result or {},
                "error": error,
            }

        def list_games(self):
            return []

        def recent_draw_dates_by_game(self, limit_per_game=400):
            return {}

        def recent_crawl_logs(self, limit=20):
            return []

    def broken_crawl(*args, **kwargs):
        raise RuntimeError("legacy crawler exploded")

    monkeypatch.setattr(patch_target, broken_crawl)
    app.dependency_overrides[get_repository] = lambda: AdminRepo()
    try:
        response = client.post(path, json=body, headers=ADMIN_HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["crawl"]["provider"] == provider
    assert payload["crawl"]["status"] == "failed"
    assert payload["crawl"]["failed_games"] == [failed_game]
    assert "legacy crawler exploded" in payload["crawl"]["error"]
    assert payload["health"]["games"] == []


def test_predict_ssq_returns_valid_payload_without_deepseek_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
            "birth_hour": "午",
            "birth_place": "杭州",
            "current_city": "上海",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == "ssq"
    assert len(payload["numbers"]["main"]) == 6
    assert "娱乐推荐" in payload["disclaimer"]
    assert "不构成投注建议" in payload["disclaimer"]
    assert payload["best_draw_date"]
    assert payload["personal_basis"]["ai_enabled"] is False
    assert payload["recommendation_basis"]["mode"] == "玄学主导"
    assert payload["number_reasons"]["main"]
    assert payload["fortune_hook"]["headline"]
    assert payload["interpretation_layers"]["short_hook"]
    assert payload["interpretation_layers"]["long_reading"]
    assert payload["metaphysics_profile"]["wealth_pattern"]
    assert payload["avoid_numbers"]
    assert payload["daily_fortune_sign"]["lucky_hour"]
    assert payload["ritual_steps"]
    assert payload["master_ritual"]["verdict"]
    assert payload["master_ritual"]["steps"][-1]["label"] == "落财运号"
    assert "财运" in payload["ritual_summary"]


def test_predict_without_deepseek_key_explains_missing_configuration(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 200
    assert "请在 AI 设置中配置 DeepSeek API Key" in response.json()["personal_basis"][
        "ai_explanation"
    ]


def test_predict_accepts_calendar_type_and_sends_minimized_features_to_ai_provider(monkeypatch):
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    contexts = []

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            assert api_key == "user-secret"
            assert strict_errors is True

        def extract(self, context):
            contexts.append(context)
            return {
                "invalid": "payload falls back to neutral without network",
            }

        def close(self):
            pass

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
            "calendar_type": "lunar",
        },
        headers={"X-DeepSeek-Api-Key": "user-secret"},
    )

    assert response.status_code == 200
    assert contexts[0]["personal_features"]["calendar_type"] == "lunar"
    assert set(contexts[0]["personal_features"]) == {
        "birth_vector",
        "birth_hour_known",
        "calendar_type",
        "location_relation",
    }
    assert "personal" not in contexts[0]


def test_predict_accepts_fortune_mode(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
            "fortune_mode": "windfall",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fortune_mode"] == "windfall"
    assert payload["mode_profile"]["label"] == "偏财号"
    assert payload["credibility_chain"]


def test_predict_invalid_fortune_mode_returns_422(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
            "fortune_mode": "random",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("game_key", ["ssq", "3d", "qlc", "kl8", "dlt", "pl3", "pl5"])
def test_predict_supported_games_smoke(monkeypatch, game_key):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": game_key,
            "name": "张三",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == game_key
    assert payload["numbers"]["main"]
    assert payload["best_draw_date"]


def test_predict_uses_default_birth_hour_when_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 200
    assert len(response.json()["numbers"]["main"]) == 6


def test_predict_invalid_game_key_returns_422():
    response = client.post(
        "/api/predict",
        json={
            "game_key": "nope",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 422


def test_predict_invalid_birth_date_returns_422():
    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "not-a-date",
        },
    )

    assert response.status_code == 422


def test_predict_missing_required_field_returns_422():
    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 422


def test_predict_blank_name_returns_422():
    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "   ",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 422


def test_user_deepseek_key_header_constructs_provider_and_closes_it(
    monkeypatch,
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "server-key-must-not-be-used")
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    events = []

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            events.append(("constructed", api_key, strict_errors))

        def extract(self, context):
            return {
                "invalid": "payload falls back to neutral without network",
            }

        def close(self):
            events.append("closed")

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
        headers={"X-DeepSeek-Api-Key": "  user-secret  "},
    )

    assert response.status_code == 200
    assert events == [("constructed", "user-secret", True), "closed"]


def test_ai_key_validation_only_succeeds_after_provider_accepts_key(monkeypatch):
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    events = []

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            events.append(("constructed", api_key, strict_errors))

        def extract(self, context):
            events.append(("validated", context))
            return AiFeature(
                enabled=True,
                element_bias={
                    "wood": 0.2,
                    "fire": 0.2,
                    "earth": 0.2,
                    "metal": 0.2,
                    "water": 0.2,
                },
                digit_bias={str(digit): 0.1 for digit in range(10)},
                lucky_themes=["平衡"],
                explanation="仅用于连接验证。",
                confidence=0.1,
            )

        def close(self):
            events.append("closed")

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/ai/validate",
        headers={"X-DeepSeek-Api-Key": "  user-secret  "},
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}
    assert events == [
        ("constructed", "user-secret", True),
        ("validated", {"purpose": "credential_validation"}),
        "closed",
    ]


def test_ai_key_validation_rejects_invalid_credentials_without_echoing_key(monkeypatch):
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    secret = "invalid-user-secret"

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            assert api_key == secret
            assert strict_errors is True

        def extract(self, context):
            raise AiAuthenticationError

        def close(self):
            pass

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/ai/validate",
        headers={"X-DeepSeek-Api-Key": secret},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AI_KEY_INVALID"
    assert secret not in response.text


def test_predict_rejects_invalid_user_ai_key_instead_of_returning_neutral_success(
    monkeypatch,
):
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            assert api_key == "invalid-key"
            assert strict_errors is True

        def extract(self, context):
            raise AiAuthenticationError

        def close(self):
            pass

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
        headers={"X-DeepSeek-Api-Key": "invalid-key"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AI_KEY_INVALID"


def test_server_deepseek_key_is_not_used_without_user_header(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "server-key-must-not-be-used")
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("DeepSeek provider should require a user key header")

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", fail_if_constructed)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
    )

    assert response.status_code == 200
    assert response.json()["personal_basis"]["ai_enabled"] is False


def test_explicit_ai_switch_false_disables_deepseek_provider(
    monkeypatch,
):
    monkeypatch.setenv("LOTTERY_LUCK_AI_ENABLED", "false")

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("DeepSeek provider should not be constructed")

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", fail_if_constructed)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
        headers={"X-DeepSeek-Api-Key": "user-secret"},
    )

    assert response.status_code == 200
    assert response.json()["personal_basis"]["ai_enabled"] is False


def test_explicit_ai_switch_constructs_provider_and_closes_it(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_AI_ENABLED", "true")
    events = []

    class FakeDeepSeekProvider:
        def __init__(self, *, api_key, strict_errors):
            events.append(("constructed", api_key, strict_errors))

        def extract(self, context):
            return {
                "invalid": "payload falls back to neutral without network",
            }

        def close(self):
            events.append("closed")

    monkeypatch.setattr("lottery_luck.api.DeepSeekFlashProvider", FakeDeepSeekProvider)

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
        headers={"X-DeepSeek-Api-Key": "user-secret"},
    )

    assert response.status_code == 200
    assert events == [("constructed", "user-secret", True), "closed"]


def test_oversized_user_deepseek_key_is_rejected_without_echoing_value(monkeypatch):
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    secret = "s" * 513

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-17",
        },
        headers={"X-DeepSeek-Api-Key": secret},
    )

    assert response.status_code == 400
    assert secret not in response.text


def test_dependency_override_can_supply_repository():
    class EmptyRepo:
        def list_games(self):
            return [{"game_key": "ssq"}]

        def all_draws(self, game_key):
            return []

        def recent_draws(self, game_key, limit=100):
            return []

    app.dependency_overrides[get_repository] = lambda: EmptyRepo()
    try:
        response = client.get("/api/games")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["games"][0]["game_key"] == "ssq"
    assert response.json()["games"][0]["number_rule"]["main_count"] == 6


def test_predict_response_does_not_echo_personal_fields(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LOTTERY_LUCK_AI_ENABLED", raising=False)
    personal_values = {
        "name": "隐私测试-Alice",
        "birth_date": "1988-12-31",
        "birth_place": "隐私出生地",
        "current_city": "隐私城市",
    }

    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "birth_hour": " 午 ",
            **personal_values,
        },
    )

    assert response.status_code == 200
    encoded_payload = json.dumps(response.json(), ensure_ascii=False)
    for value in personal_values.values():
        assert value not in encoded_payload


def _predict_request(game_key="3d"):
    return {
        "game_key": game_key,
        "name": "张三",
        "birth_date": "1990-05-17",
        "birth_hour": "午",
        "birth_place": "杭州",
        "current_city": "上海",
    }


def _engine_payload(game_key="3d", *, best_draw_date="2026-07-13", numbers=None):
    return {
        "game_key": game_key,
        "fortune_mode": "steady",
        "mode_profile": {"key": "steady", "label": "稳财号"},
        "best_draw_date": best_draw_date,
        "luck_score": 66,
        "numbers": {"main": numbers or [1, 2, 3], "special": []},
        "history_basis": {"draw_count": 10, "hot_main": [1, 2, 3], "cold_main": [4, 5]},
        "personal_basis": {"ai_enabled": False, "ai_explanation": "测试特征"},
        "recent_draws": [],
        "disclaimer": "娱乐推荐，不构成投注建议",
    }


def _install_predict_engine(monkeypatch, payload):
    class FakePredictionEngine:
        def __init__(self, repo, ai_provider):
            self.repo = repo
            self.ai_provider = ai_provider

        def predict(self, game_key, personal, fortune_mode="steady"):
            assert personal.name == "张三"
            assert fortune_mode == "steady"
            return dict(payload)

    monkeypatch.setattr("lottery_luck.api.PredictionEngine", FakePredictionEngine)


def _quota_settings(tmp_path: Path, monkeypatch, *, enabled_games=None):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    settings_path = tmp_path / "quota-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "prediction_quota": {
                    "free_daily": 0,
                    "new_user_bonus": 1,
                    "member_daily": 0,
                    "package_units": [6],
                    "mode_costs": {"steady": 1, "windfall": 1, "guard": 1},
                    "enabled_games": enabled_games or ["ssq", "3d"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOTTERY_LUCK_SETTINGS_PATH", str(settings_path))


def _quota_remaining(repo, client_id):
    return repo.quota_status(client_id, today="2026-07-13")["remaining_total"]


def test_predict_refunds_quota_when_3d_metadata_enrichment_fails(
    tmp_path,
    monkeypatch,
):
    _quota_settings(tmp_path, monkeypatch, enabled_games=["3d"])
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(monkeypatch, _engine_payload(best_draw_date="2026-07-13"))
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo

    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-refund-3d"},
            json={**_predict_request("3d"), "consume_quota": True},
        )
        remaining = _quota_remaining(repo, "client-refund-3d")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "prediction data unavailable"}
    assert remaining == 1


def test_predict_refunds_quota_when_engine_returns_user_error(
    tmp_path,
    monkeypatch,
):
    _quota_settings(tmp_path, monkeypatch, enabled_games=["ssq"])
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    class FailingEngine:
        def __init__(self, repo, ai_provider):
            pass

        def predict(self, game_key, personal, fortune_mode="steady"):
            raise ValueError("unsupported input")

    monkeypatch.setattr("lottery_luck.api.PredictionEngine", FailingEngine)
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo

    try:
        response = client.post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-refund-engine"},
            json={**_predict_request("ssq"), "consume_quota": True},
        )
        remaining = _quota_remaining(repo, "client-refund-engine")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "unsupported input"}
    assert remaining == 1


def test_predict_success_keeps_consumed_quota(tmp_path, monkeypatch):
    _quota_settings(tmp_path, monkeypatch, enabled_games=["ssq"])
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    payload = _engine_payload(
        game_key="ssq",
        best_draw_date="2026-07-14",
        numbers=[1, 2, 3, 4, 5, 6],
    )
    payload["numbers"] = {"main": [1, 2, 3, 4, 5, 6], "special": [7]}
    _install_predict_engine(monkeypatch, payload)
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo

    try:
        response = client.post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-success-keeps-quota"},
            json={**_predict_request("ssq"), "consume_quota": True},
        )
        remaining = _quota_remaining(repo, "client-success-keeps-quota")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert remaining == 0
    assert response.json()["quota"]["remaining_total"] == 0


def test_predict_refund_failure_preserves_original_error_and_runs_once(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    calls = {"refund": 0}

    class FailingEngine:
        def __init__(self, repo, ai_provider):
            pass

        def predict(self, game_key, personal, fortune_mode="steady"):
            raise ValueError("engine failed")

    class Repo:
        def consume_prediction_quota(self, client_id, game_key, mode_key):
            return {
                "allowed": True,
                "source": "new_user_bonus",
                "cost": 1,
                "client_id": client_id,
                "usage_date": "all",
                "quota": {"remaining_total": 0},
            }

        def refund_prediction_quota(self, client_id, quota_result):
            calls["refund"] += 1
            raise RuntimeError("refund database unavailable")

    monkeypatch.setattr("lottery_luck.api.PredictionEngine", FailingEngine)
    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post(
            "/api/predict",
            headers={"X-Lottery-Client-Id": "client-refund-fails"},
            json={**_predict_request("ssq"), "consume_quota": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "engine failed"}
    assert calls["refund"] == 1


def test_predict_3d_adds_server_target_freshness_and_number_metrics(monkeypatch):
    class FrozenDate(real_date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 13)

    monkeypatch.setattr("lottery_luck.data_health.date", FrozenDate)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    payload = _engine_payload(best_draw_date="2026-07-13", numbers=[1, 2, 3])
    _install_predict_engine(monkeypatch, payload)
    calls = []

    class Repo:
        def list_games(self):
            return [
                {"game_key": "ssq", "latest_issue": "2026070", "latest_date": "2026-07-12"},
                {"game_key": "3d", "latest_issue": "2026193", "latest_date": "2026-07-12"},
            ]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            calls.append((list(game_keys), limit_per_game))
            return [
                {
                    "game_key": "3d",
                    "status": "success",
                    "error": "",
                    "finished_at": "2026-07-12T08:00:00+00:00",
                },
                {
                    "game_key": "ssq",
                    "status": "failed",
                    "error": "must be ignored",
                    "finished_at": "2026-07-12T09:00:00+00:00",
                },
            ]

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post("/api/predict", json=_predict_request("3d"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert calls == [(["3d"], 20)]
    assert result["target_issue"] == "2026194"
    assert result["target_draw_date"] == result["best_draw_date"] == "2026-07-13"
    assert result["data_freshness"] == {
        "status": "fresh",
        "latest_issue": "2026193",
        "latest_date": "2026-07-12",
        "staleness_days": 1,
        "can_claim_current": True,
        "message": "数据已更新至第2026193期",
        "last_successful_update": "2026-07-12T08:00:00+00:00",
        "sync_error": "",
    }
    assert result["number_metrics"]["numbers"] == [1, 2, 3]
    assert result["number_metrics"]["sum"] == 6
    assert result["number_metrics"]["span"] == 2
    assert result["number_metrics"]["group_type"] == "组六"
    assert result["number_metrics"]["odd_even"] == "2:1"
    assert result["number_metrics"]["big_small"] == "0:3"
    assert result["number_metrics"]["mod3"] == "1:1:1"
    assert result["number_metrics"]["prime_composite"] == "2:1"


def test_predict_3d_stale_data_returns_prediction_but_marks_uncurrent(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(
        monkeypatch,
        _engine_payload(best_draw_date="2026-07-13", numbers=[7, 7, 2]),
    )

    class Repo:
        def list_games(self):
            return [{"game_key": "3d", "latest_issue": "2026187", "latest_date": "2026-07-06"}]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return [
                {
                    "game_key": "3d",
                    "status": "failed",
                    "error": "timeout\nsecret path /tmp/hidden",
                    "finished_at": "2026-07-12T08:00:00+00:00",
                }
            ]

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post("/api/predict", json=_predict_request("3d"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert result["numbers"]["main"] == [7, 7, 2]
    assert result["target_issue"] == "2026194"
    assert result["data_freshness"]["status"] == "stale"
    assert result["data_freshness"]["can_claim_current"] is False
    assert result["data_freshness"]["sync_error"] == "timeout secret path /tmp/hidden"


def test_predict_3d_cross_year_target_uses_best_draw_date(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(
        monkeypatch,
        _engine_payload(best_draw_date="2027-01-01", numbers=[0, 9, 9]),
    )

    class Repo:
        def list_games(self):
            return [{"game_key": "3d", "latest_issue": "2026365", "latest_date": "2026-12-31"}]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            assert list(game_keys) == ["3d"]
            return []

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post("/api/predict", json=_predict_request("3d"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert result["target_issue"] == "2027001"
    assert result["target_draw_date"] == "2027-01-01"


def test_predict_3d_missing_latest_metadata_returns_stable_service_error(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(monkeypatch, _engine_payload(best_draw_date="2026-07-13"))

    class Repo:
        def list_games(self):
            return [{"game_key": "3d", "latest_issue": "", "latest_date": ""}]

        def recent_crawl_logs_by_game(self, game_keys, limit_per_game=5):
            return []

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/predict",
            json=_predict_request("3d"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "prediction data unavailable"}


def test_predict_3d_repository_error_does_not_leak_or_become_user_400(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _install_predict_engine(monkeypatch, _engine_payload(best_draw_date="2026-07-13"))

    class Repo:
        def list_games(self):
            raise RuntimeError("database locked at /private/customer.sqlite")

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/predict",
            json=_predict_request("3d"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "prediction data unavailable"}
    assert "private" not in response.text


def test_predict_other_games_do_not_receive_3d_plan_fields(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    payload = _engine_payload(
        game_key="ssq",
        best_draw_date="2026-07-14",
        numbers=[1, 2, 3, 4, 5, 6],
    )
    payload["numbers"] = {"main": [1, 2, 3, 4, 5, 6], "special": [7]}
    _install_predict_engine(monkeypatch, payload)

    class Repo:
        def list_games(self):
            raise AssertionError("3d metadata lookup should not run for non-3d")

        def quota_status(self, client_id):
            return {"tracked": False, "remaining_total": None}

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post("/api/predict", json=_predict_request("ssq"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert result["game_key"] == "ssq"
    assert "target_issue" not in result
    assert "target_draw_date" not in result
    assert "data_freshness" not in result
    assert "number_metrics" not in result


@pytest.mark.parametrize("game_key", ["ssq", "3d", "qlc", "kl8"])
def test_analysis_endpoint_returns_cwl_supported_games(game_key):
    response = client.get(f"/api/analysis/{game_key}?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == game_key
    assert payload["window"] == 30
    assert payload["summary"]["draw_count"] > 0
    assert "hot" in payload
    assert "cold" in payload
    assert "omission" in payload
    assert "shape" in payload
    assert "trend" in payload
    assert "recent_draws" in payload


@pytest.mark.parametrize("game_key", ["dlt", "pl3", "pl5"])
def test_analysis_endpoint_returns_sports_supported_games_without_seed_data(game_key):
    response = client.get(f"/api/analysis/{game_key}?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == game_key
    assert payload["window"] == 30
    assert payload["summary"]["draw_count"] >= 0
    assert "hot" in payload
    assert "trend" in payload


def test_analysis_endpoint_invalid_window_falls_back_to_30():
    response = client.get("/api/analysis/ssq?window=999")

    assert response.status_code == 200
    assert response.json()["window"] == 30


def test_analysis_endpoint_non_numeric_window_falls_back_to_30():
    response = client.get("/api/analysis/ssq?window=bad")

    assert response.status_code == 200
    assert response.json()["window"] == 30


def test_analysis_endpoint_invalid_game_returns_404():
    response = client.get("/api/analysis/nope")

    assert response.status_code == 404


def test_analysis_endpoint_handles_empty_repository():
    class EmptyRepo:
        def recent_draws(self, game_key, limit=100):
            return []

    app.dependency_overrides[get_repository] = lambda: EmptyRepo()
    try:
        response = client.get("/api/analysis/ssq?window=60")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["window"] == 60
    assert payload["summary"] == {"draw_count": 0, "latest_issue": "", "latest_date": ""}
    assert payload["trend"]["rows"] == []


def test_filter_endpoint_returns_candidate_sets():
    response = client.post(
        "/api/filter/ssq",
        json={
            "exclude_recent": 2,
            "min_hot": 1,
            "odd_even": "3:3",
            "sum_min": 80,
            "sum_max": 130,
            "max_consecutive_run": 2,
            "count": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == "ssq"
    assert len(payload["candidates"]) <= 5
    assert "不构成投注建议" in payload["disclaimer"]


def test_filter_endpoint_accepts_professional_conditions():
    response = client.post(
        "/api/filter/ssq",
        json={
            "exclude_recent": 0,
            "min_hot": 0,
            "odd_even": "3:3",
            "sum_min": 60,
            "sum_max": 160,
            "max_consecutive_run": 3,
            "ac_min": 4,
            "ac_max": 12,
            "zone": "2:2:2",
            "tail_exclude": [0, 5],
            "count": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["candidates"]) <= 2
    if payload["candidates"]:
        assert "ac_value" in payload["candidates"][0]
        assert payload["candidates"][0]["zone"] == "2:2:2"


def test_backtest_endpoint_returns_strategy_summary():
    response = client.post(
        "/api/backtest/ssq",
        json={"strategy": "hot_omission_balance", "window": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "hot_omission_balance"
    assert payload["tested_draws"] == 5
    assert "average_main_hits" in payload
    assert "不代表未来结果" in payload["disclaimer"]


def test_backtest_compare_endpoint_returns_ranked_strategies():
    response = client.post(
        "/api/backtest/ssq/compare",
        json={"strategies": ["hot_omission_balance", "cold_rebound", "hot_focus"], "window": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["strategies"]) == 3
    assert payload["strategies"][0]["average_main_hits"] >= payload["strategies"][-1]["average_main_hits"]
    assert "不代表未来结果" in payload["disclaimer"]


def test_strategy_generate_endpoint_returns_candidates_and_baseline():
    response = client.post(
        "/api/strategy/ssq/generate",
        json={"preset": "balanced", "candidate_count": 4},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preset"] == "balanced"
    assert len(payload["candidates"]) <= 4
    assert len(payload["baseline"]["candidates"]) == 4
    assert "diagnostics" in payload


def test_strategy_generate_endpoint_supports_sports_lottery_games():
    response = client.post(
        "/api/strategy/dlt/generate",
        json={"preset": "balanced", "candidate_count": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == "dlt"
    assert len(payload["candidates"]) <= 3
    if payload["candidates"]:
        assert len(payload["candidates"][0]["main"]) == 5
        assert len(payload["candidates"][0]["special"]) == 2


def test_strategy_backtest_endpoint_returns_distribution_and_baseline():
    response = client.post(
        "/api/strategy/ssq/backtest",
        json={"preset": "balanced", "window": 5, "candidate_count": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tested_draws"] == 5
    assert payload["hit_distribution"]
    assert "baseline_average_main_hits" in payload


def test_strategy_compare_endpoint_returns_preset_rows():
    response = client.post(
        "/api/strategy/ssq/compare",
        json={"window": 5, "candidate_count": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["strategies"]) == 3
    assert payload["strategies"][0]["average_main_hits"] >= payload["strategies"][-1]["average_main_hits"]


def test_number_pool_endpoint_analyzes_user_numbers():
    response = client.post(
        "/api/number-pool/ssq/analyze",
        json={
            "numbers": [
                {"main": [1, 2, 3, 4, 5, 6], "special": [7]},
                {"main": [1, 2, 3, 4, 5, 6], "special": [8]},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["pool_size"] == 2
    assert payload["entries"][0]["duplicate_count"] == 1
    assert payload["entries"][0]["fortune_commentary"]["wealth_type"] in {
        "进财",
        "守财",
        "散财",
    }


def test_review_endpoint_compares_prediction_against_latest_draw():
    class ReviewRepo:
        def recent_draws(self, game_key, limit=1):
            assert game_key == "ssq"
            assert limit == 1
            return [
                {
                    "game_key": "ssq",
                    "game_name": "双色球",
                    "issue": "2026068",
                    "draw_date": "2026-06-16",
                    "red_numbers": "01,02,03,04,05,06",
                    "blue_number": "07",
                }
            ]

    app.dependency_overrides[get_repository] = lambda: ReviewRepo()
    try:
        response = client.post(
            "/api/review/ssq",
            json={"main": [1, 2, 9, 10, 11, 12], "special": [7], "fortune_eye": 7},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "reviewed"
    assert payload["latest_draw"]["issue"] == "2026068"
    assert payload["main_hits"] == [1, 2]
    assert payload["special_hits"] == [7]
    assert payload["hit_count"] == 3
    assert payload["fortune_eye_hit"] is True
    assert "财眼" in payload["summary"]


def test_review_endpoint_returns_pending_without_draws():
    class EmptyReviewRepo:
        def recent_draws(self, game_key, limit=1):
            return []

    app.dependency_overrides[get_repository] = lambda: EmptyReviewRepo()
    try:
        response = client.post(
            "/api/review/dlt",
            json={"main": [1, 2, 3, 4, 5], "special": [1, 2], "fortune_eye": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["hit_count"] == 0
    assert "等待开奖" in payload["summary"]


def test_calendar_endpoint_returns_visible_frontend_games():
    response = client.get("/api/calendar?today=2026-06-17")

    assert response.status_code == 200
    payload = response.json()
    assert [game["game_key"] for game in payload["games"]] == [
        "ssq",
        "dlt",
        "3d",
        "pl3",
        "kl8",
    ]
    assert all(game["next_draw_date"] >= "2026-06-17" for game in payload["games"])


def test_result_page_loads_product_client_before_detail_script():
    html = Path("web/result.html").read_text(encoding="utf-8")

    product_index = html.index("product-client.js")
    result_index = html.index("result.js")

    assert product_index < result_index
    assert 'id="resultDetail"' in html
