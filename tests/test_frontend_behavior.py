import base64
import json
import re
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from lottery_luck.api import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server_url():
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("uvicorn test server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def browser_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        yield page
        browser.close()


def _prediction_payload(game_key, main, special=None):
    special = special or []
    return {
        "game_key": game_key,
        "fortune_mode": "steady",
        "mode_profile": {"key": "steady", "label": "稳财号"},
        "best_draw_date": "2026-06-18",
        "luck_score": 66,
        "numbers": {"main": main, "special": special},
        "history_basis": {"draw_count": 10, "hot_main": main, "cold_main": [1, 2]},
        "personal_basis": {
            "ai_enabled": False,
            "ai_explanation": "测试特征",
            "ai_lucky_themes": [],
            "ai_confidence": 0,
        },
        "recent_draws": [],
        "disclaimer": "娱乐推荐，不构成投注建议",
        "ritual_summary": "测试财运合参",
        "fortune_hook": {
            "headline": f"{game_key} 测试财签",
            "subline": "测试本命财格",
            "tags": ["本命财格 测试"],
        },
        "interpretation_layers": {
            "short_hook": "测试短钩子",
            "long_reading": "测试长解读",
        },
        "metaphysics_profile": {
            "wealth_pattern": "测试财格",
            "reading": "测试解读",
            "selection_rule": "测试取号逻辑",
            "day_advice": "宜测试。",
        },
        "avoid_numbers": [{"number": 1, "reason": f"{game_key} 避冲测试"}],
        "daily_fortune_sign": {
            "headline": f"{game_key} 今日财签",
            "direction": "正东",
            "lucky_hour": "巳时",
            "lucky_tails": [3, 8],
            "avoid_tails": [1],
            "tags": ["正东财位", "旺时 巳时", "尾 3、8 · 避 1"],
        },
        "ritual_steps": [
            {"key": "wealth_pattern", "label": "定本命财盘", "summary": "测试步骤"},
            {"key": "fortune_direction", "label": "定今日财局", "summary": "测试财位"},
            {"key": "fortune_eye", "label": "取财眼尾数", "summary": "测试财眼"},
            {"key": "avoid_clash", "label": "避冲煞号", "summary": "测试避冲"},
            {"key": "final_numbers", "label": "落财运号", "summary": "测试成号"},
        ],
        "master_ritual": {
            "opening": "测试起盘开场",
            "verdict": "测试起盘断语：测试财格按稳财号落盘。",
            "tail_map": {
                "favorable": [{"tail": 3, "element_label": "火"}],
                "avoid": [{"tail": 1, "element_label": "木"}],
                "legend": "尾数1/2木，3/4火，5/6土，7/8金，9/0水。",
            },
            "steps": [
                {"key": "birth_chart", "label": "定命盘", "value": "测试命盘", "detail": "测试命盘细节"},
                {"key": "wealth_pattern", "label": "排本命财格", "value": "测试财格", "detail": "测试财格细节"},
                {"key": "daily_luck", "label": "定今日财局", "value": "测试财局", "detail": "测试财局细节"},
                {"key": "tail_digits", "label": "取喜用尾数", "value": "尾 3", "detail": "测试尾数细节"},
                {"key": "avoid_clash", "label": "避冲煞号", "value": "避 01", "detail": "测试避冲细节"},
                {"key": "final_numbers", "label": "落财运号", "value": "11 -> 12 -> 财眼01", "detail": "测试落号细节"},
            ],
        },
        "credibility_chain": [],
        "number_reasons": {"main": [], "special": []},
        "fortune_report": {"closed_loop": [], "daily_calendar": []},
    }


def _prediction_payload_3d(
    main=None,
    *,
    can_claim_current=True,
    freshness_status="fresh",
    best_draw_date="2026-07-13",
):
    main = main or [1, 2, 3]
    payload = _prediction_payload("3d", main, [])
    payload["best_draw_date"] = best_draw_date
    payload["target_issue"] = "2026194"
    payload["target_draw_date"] = best_draw_date
    payload["data_freshness"] = {
        "status": freshness_status,
        "latest_issue": "2026193",
        "latest_date": "2026-07-12",
        "staleness_days": 1 if can_claim_current else 7,
        "can_claim_current": can_claim_current,
        "message": (
            "数据已更新至第2026193期"
            if can_claim_current
            else "数据停留在第2026193期，暂不提供本期结论"
        ),
        "last_successful_update": "2026-07-12T08:00:00+00:00",
        "sync_error": "" if can_claim_current else "timeout",
    }
    payload["number_metrics"] = {
        "numbers": main,
        "number_text": ",".join(str(number) for number in main),
        "sum": sum(main),
        "sum_tail": sum(main) % 10,
        "span": max(main) - min(main),
        "group_type": "组六",
        "odd_even": "2:1",
        "odd_count": 2,
        "even_count": 1,
        "big_small": "0:3",
        "big_count": 0,
        "small_count": 3,
        "mod3": "1:1:1",
        "prime_composite": "2:1",
        "repeat_count": 0,
        "consecutive_pairs": [[1, 2], [2, 3]],
        "adjacent_pairs": [[0, 1], [1, 2]],
    }
    return payload


def _workbench_summary_payload(
    *,
    status="fresh",
    can_save=True,
    current_target=None,
    latest_plan=None,
    active_plan_count=0,
    window=30,
):
    current_target = current_target if current_target is not None else {
        "target_issue": "2026183",
        "target_draw_date": "2026-07-12",
    }
    freshness = {
        "status": status,
        "latest_issue": "2026182",
        "latest_date": "2026-07-11",
        "staleness_days": 1 if can_save else 8,
        "can_claim_current": can_save,
        "message": "数据已更新至第2026182期" if can_save else "数据待更新",
        "last_successful_update": "2026-07-12T01:00:00+00:00",
        "sync_error": "" if can_save else "timeout retry exhausted",
    }
    recent_draws = [
        {
            "issue": f"2026{182 - index:03d}",
            "draw_date": f"2026-07-{11 - index:02d}",
            "number_text": text,
            "numbers": [int(char) for char in text],
        }
        for index, text in enumerate(
            ["662", "006", "123", "909", "286", "008", "594", "711", "450", "384"]
        )
    ]
    digits = {
        str(digit): {
            "position": 0,
            "digit": digit,
            "frequency": 9 - digit if digit < 9 else 1,
            "current_omission": digit,
            "average_omission": round(2.5 + digit / 10, 2),
            "max_omission": digit + 4,
            "historical_percentile": digit * 10,
            "frequency_percentile": 90 - digit * 5,
            "omission_hotness": 80 - digit * 3,
            "heat_score": 70 - digit,
            "heat": "hot" if digit < 3 else "neutral",
        }
        for digit in range(10)
    }
    position_stats = {
        "window": window,
        "sample_size": 30,
        "latest_issue": "2026182",
        "latest_date": "2026-07-11",
        "definition": "统计的是最近30期开奖。出次是这个数字在该位置开出过的期数；当前遗漏是它已经连续多少期没有开出。历史统计不代表未来概率。",
        "positions": {
            "0": {"label": "百位", "digits": digits},
            "1": {"label": "十位", "digits": {key: {**value, "position": 1} for key, value in digits.items()}},
            "2": {"label": "个位", "digits": {key: {**value, "position": 2} for key, value in digits.items()}},
        },
    }
    return {
        "window": window,
        "sample_size": 30,
        "latest_draw": recent_draws[0],
        "freshness": freshness,
        "actions": {
            "can_filter_current": can_save,
            "can_save_current": can_save,
            "can_read_history": True,
        },
        "active_plan_count": active_plan_count,
        "latest_plan": latest_plan,
        "current_target": current_target if can_save or current_target is None else current_target,
        "recent_draws": recent_draws,
        "position_stats": position_stats,
        "attribute_distributions": {
            "group_type": [
                {"label": "豹子", "count": 2},
                {"label": "组三", "count": 8},
                {"label": "组六", "count": 20},
            ],
            "sum": [{"value": 6, "count": 2}, {"value": 14, "count": 4}],
            "span": [{"value": 0, "count": 2}, {"value": 6, "count": 5}],
            "odd_even": [{"label": "1:2", "count": 9}, {"label": "2:1", "count": 12}],
        },
        "definition": "这里的数据只是所选期数内真实开奖号码的统计，历史统计不代表未来概率。",
    }


def _open_3d_tool(page, tool_key):
    """Open a toolbox tool the way a user does: click its tile on the home screen."""
    page.locator(f'[data-three-d-tool-key="{tool_key}"]').click()
    page.wait_for_selector(f'[data-three-d-tool-panel="{tool_key}"]:not([hidden])')


def _number_query_payload(number_text="006", window=30, sample_size=None):
    # The position stats can only come from the draws that really existed in the window,
    # so the fixture derives every omission fact from that sample instead of asserting a
    # window the numbers never came from.
    sample = window if sample_size is None else sample_size
    position_digits = {
        "0": {"current_omission": 4, "average_omission": 6.5, "max_omission": 16},
        "1": {"current_omission": 1, "average_omission": 4.5, "max_omission": 12},
        "2": {"current_omission": 0, "average_omission": 3.2, "max_omission": 9},
    }
    position_digits = {
        position: {key: min(value, sample) for key, value in cell.items()}
        for position, cell in position_digits.items()
    }
    return {
        "number_text": number_text,
        "numbers": [int(char) for char in number_text],
        "attributes": {
            "number_text": number_text,
            "sum": 6,
            "sum_tail": 6,
            "span": 6,
            "group_type": "组三",
            "odd_even": "0:3",
            "big_small": "1:2",
            "mod3": "3:0:0",
            "prime_composite": "0:3",
            "repeat_count": 1,
            "consecutive_pairs": [],
            "adjacent_pairs": [],
        },
        "history": {
            "exact": {
                "count": 1,
                "latest": {
                    "issue": "2026181",
                    "draw_date": "2026-07-10",
                    "number_text": number_text,
                    "numbers": [int(char) for char in number_text],
                },
            },
            "group": {
                "count": 2,
                "latest": {
                    "issue": "2026181",
                    "draw_date": "2026-07-10",
                    "number_text": number_text,
                    "numbers": [int(char) for char in number_text],
                },
            },
        },
        "position_stats_window": window,
        "position_stats_sample_size": sample,
        "position_digits": position_digits,
        "freshness": {
            "status": "fresh",
            "latest_issue": "2026182",
            "latest_date": "2026-07-11",
            "can_claim_current": True,
        },
        "actions": {
            "can_filter_current": True,
            "can_save_current": True,
            "can_read_history": True,
        },
    }


def _speed_up_motion(page, *, gated=False):
    page.wait_for_function("() => Boolean(window.FortuneMotion)")
    if gated:
        page.evaluate(
            """
            () => {
              window.__releaseMotionResolve = null;
              window.__motionResolveStarted = false;
              window.FortuneMotion.resolve = async () => {
                window.__motionResolveStarted = true;
                await new Promise((resolve) => {
                  window.__releaseMotionResolve = resolve;
                });
              };
            }
            """
        )
    else:
        page.evaluate(
            """
            () => {
              window.FortuneMotion.resolve = async () => {};
            }
            """
        )


def _route_predict_payload(page, live_server_url, payload, *, status=200):
    page.route(
        f"{live_server_url}/api/predict",
        lambda route: route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        ),
    )


def _dismiss_motion_stage(page):
    page.evaluate(
        """
        () => {
          const stage = document.querySelector("#ritualStage");
          if (!stage) return;
          stage.dataset.motionState = "idle";
          stage.setAttribute("aria-hidden", "true");
          stage.classList.add("is-dismissed");
        }
        """
    )


def _complete_3d_prediction(page, live_server_url, payload=None, *, gated_motion=False):
    _route_predict_payload(page, live_server_url, payload or _prediction_payload_3d())
    page.goto(live_server_url)
    page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(page, gated=gated_motion)
    page.locator('button[data-game="3d"]').click()
    _fill_required_form(page)
    page.locator("#submitButton").click()
    if gated_motion:
        page.wait_for_function("() => window.__motionResolveStarted === true")
        return
    page.wait_for_function(
        "() => !document.querySelector('#predictionActions').hidden",
        timeout=5000,
    )
    _dismiss_motion_stage(page)


def _fill_required_form(page):
    page.evaluate(
        "() => localStorage.setItem('lotteryLuck.deepseekApiKey.v1', 'sk-test-key')"
    )
    page.locator('input[name="name"]').fill("测试用户")
    page.locator('input[name="birth_date"]').fill("1990-01-01")
    page.locator('input[name="birth_place"]').fill("杭州")
    page.locator('input[name="current_city"]').fill("上海")
    page.locator('[data-select-name="birth_hour"] .custom-select-trigger').click()
    page.locator(
        '[data-select-name="birth_hour"] .custom-select-option[data-value="辰"]'
    ).click()


def test_ai_settings_rejects_invalid_key_without_persisting_it(
    live_server_url, browser_page
):
    browser_page.route(
        f"{live_server_url}/api/ai/validate",
        lambda route: route.fulfill(
            status=401,
            content_type="application/json",
            body=json.dumps(
                {
                    "detail": {
                        "code": "AI_KEY_INVALID",
                        "message": "DeepSeek API Key 无效或已失效，请重新配置。",
                    }
                },
                ensure_ascii=False,
            ),
        ),
    )
    browser_page.goto(live_server_url)
    browser_page.locator("#aiSettingsButton").click()
    browser_page.locator("#deepseekApiKey").fill("sk-invalid-key")
    browser_page.locator('#aiSettingsForm button[type="submit"]').click()

    browser_page.wait_for_function(
        "() => document.querySelector('#aiSettingsHint').classList.contains('error')",
        timeout=5000,
    )

    assert browser_page.locator("#aiSettingsDialog").get_attribute("open") is not None
    assert "无效或已失效" in browser_page.locator("#aiSettingsHint").inner_text()
    assert browser_page.evaluate(
        "() => localStorage.getItem('lotteryLuck.deepseekApiKey.v1')"
    ) is None


def test_ai_settings_persists_key_only_after_successful_validation(
    live_server_url, browser_page
):
    browser_page.route(
        f"{live_server_url}/api/ai/validate",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"valid":true}',
        ),
    )
    browser_page.goto(live_server_url)
    browser_page.locator("#aiSettingsButton").click()
    browser_page.locator("#deepseekApiKey").fill("  sk-valid-key  ")
    browser_page.locator('#aiSettingsForm button[type="submit"]').click()

    browser_page.wait_for_function(
        "() => document.querySelector('#aiSettingsLabel').textContent === 'AI 已配置'",
        timeout=5000,
    )

    assert browser_page.evaluate(
        "() => localStorage.getItem('lotteryLuck.deepseekApiKey.v1')"
    ) == "sk-valid-key"


def test_public_frontend_contains_no_membership_or_package_controls():
    html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    admin_js = (PROJECT_ROOT / "web" / "admin.js").read_text(encoding="utf-8")

    for marker in (
        "quotaStatus",
        "unlockPanel",
        "mockMemberButton",
        "mockPackageButton",
        "/api/quota/status",
        "/api/quota/mock-unlock",
        "/api/cloud/fortune-records",
        "云端记录",
        "会员额度",
        "次数包",
        "隐私提示",
        "派生五行向量",
        "短钩子",
        "可信解释链",
    ):
        assert marker not in html + app_js + admin_js


def test_home_only_reveals_result_sections_after_prediction(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)
    browser_page.evaluate("() => localStorage.clear()")
    browser_page.reload()

    assert browser_page.locator("#predictionResults").is_hidden()
    assert browser_page.locator(".profile-calendar-panel").is_hidden()
    assert browser_page.locator("#historyQuickButton").is_hidden()
    assert browser_page.locator(".privacy-disclosure").count() == 0
    assert browser_page.locator("#bestDate").inner_text() == "输入生辰，起一盘属于你的号码"
    initial_text = browser_page.locator("body").inner_text()
    for marker in ("等待生成短钩子", "可信解释链", "派生五行向量", "财位待定"):
        assert marker not in initial_text

    _complete_3d_prediction(browser_page, live_server_url)

    assert browser_page.locator("#predictionResults").is_visible()
    assert browser_page.locator(".profile-calendar-panel").is_visible()
    assert browser_page.locator("#historyQuickButton").is_visible()
    assert browser_page.locator("#historyQuickCount").inner_text() == "1"


def test_history_numbers_open_from_a_sticky_entry_without_scrolling_to_page_bottom(
    live_server_url, browser_page
):
    _complete_3d_prediction(browser_page, live_server_url)
    browser_page.evaluate("() => window.scrollTo(0, 0)")

    quick_button = browser_page.locator("#historyQuickButton")
    assert quick_button.evaluate("element => getComputedStyle(element).position") == "sticky"
    assert browser_page.evaluate("() => window.scrollY") == 0

    quick_button.click()

    assert browser_page.locator("#historyDialog").get_attribute("open") is not None
    assert browser_page.locator("#historyDialog .fortune-history-card").count() == 1
    assert "01 02 03" in browser_page.locator(
        "#historyDialog .history-numbers"
    ).inner_text()
    assert browser_page.evaluate("() => window.scrollY") < 300

    browser_page.locator("#closeHistoryDialogButton").click()
    assert browser_page.locator("#historyDialog").get_attribute("open") is None


def test_clearing_history_closes_drawer_and_hides_quick_entry(
    live_server_url, browser_page
):
    _complete_3d_prediction(browser_page, live_server_url)

    browser_page.locator("#historyQuickButton").click()
    browser_page.locator("#clearHistoryButton").click()

    assert browser_page.locator("#historyDialog").get_attribute("open") is None
    assert browser_page.locator("#historyQuickButton").is_hidden()
    assert browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    ) == []


def test_successful_prediction_saves_recent_profile_for_click_to_fill_only(
    live_server_url, browser_page
):
    _route_predict_payload(
        browser_page,
        live_server_url,
        _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1]),
    )
    browser_page.goto(live_server_url)
    browser_page.evaluate("() => localStorage.clear()")
    browser_page.reload()
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(browser_page)
    _fill_required_form(browser_page)
    browser_page.locator('input[name="name"]').fill("朋友小周")
    browser_page.locator('input[name="birth_date"]').fill("1993-08-13")
    browser_page.locator('input[name="birth_place"]').fill("石家庄")
    browser_page.locator('input[name="current_city"]').fill("北京")
    browser_page.locator('[data-select-name="calendar_type"] .custom-select-trigger').click()
    browser_page.locator(
        '[data-select-name="calendar_type"] .custom-select-option[data-value="lunar"]'
    ).click()
    browser_page.locator('[data-mode="windfall"]').click()
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        """
        () => JSON.parse(
          localStorage.getItem('lotteryLuck.recentProfiles.v1') || '[]'
        ).length === 1
        """,
        timeout=5000,
    )

    browser_page.reload()
    browser_page.wait_for_selector("#recentProfiles:not([hidden])")
    assert browser_page.locator('input[name="name"]').input_value() == ""
    assert browser_page.locator('input[name="birth_date"]').input_value() == ""
    assert browser_page.locator('input[name="birth_place"]').input_value() == ""
    assert browser_page.locator('input[name="current_city"]').input_value() == ""
    assert browser_page.locator('input[name="calendar_type"]').input_value() == "solar"
    assert browser_page.locator('input[name="fortune_mode"]').input_value() == "steady"
    assert browser_page.locator("[data-profile-fill]").count() == 1
    assert "朋友小周" in browser_page.locator("[data-profile-fill]").inner_text()

    browser_page.locator("[data-profile-fill]").click()
    values = browser_page.evaluate(
        """
        () => Object.fromEntries([
          'name', 'birth_date', 'calendar_type', 'birth_hour',
          'birth_place', 'current_city', 'fortune_mode'
        ].map((name) => [name, document.querySelector(`[name="${name}"]`).value]))
        """
    )
    assert values == {
        "name": "朋友小周",
        "birth_date": "1993-08-13",
        "calendar_type": "lunar",
        "birth_hour": "辰",
        "birth_place": "石家庄",
        "current_city": "北京",
        "fortune_mode": "windfall",
    }
    assert browser_page.locator('[data-mode="windfall"]').get_attribute("aria-pressed") == "true"
    assert "已带入“朋友小周”的资料" in browser_page.locator("#generateFeedback").inner_text()

    browser_page.locator("[data-profile-remove]").click()
    assert browser_page.locator("#recentProfiles").is_hidden()
    assert browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.recentProfiles.v1') || '[]')"
    ) == []


def test_failed_prediction_does_not_save_recent_profile(live_server_url, browser_page):
    _route_predict_payload(
        browser_page,
        live_server_url,
        _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1]),
        status=500,
    )
    browser_page.goto(live_server_url)
    browser_page.evaluate("() => localStorage.clear()")
    browser_page.reload()
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(browser_page)
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")

    assert browser_page.evaluate(
        "() => localStorage.getItem('lotteryLuck.recentProfiles.v1')"
    ) is None
    assert browser_page.locator("#recentProfiles").is_hidden()


def test_prediction_requests_never_consume_quota():
    app_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "requestPayload.consume_quota = false" in app_js
    assert "Boolean(userInitiated)" not in app_js


def test_workbench_cta_hidden_until_3d_motion_resolves(live_server_url, browser_page):
    payload = _prediction_payload_3d()
    _complete_3d_prediction(browser_page, live_server_url, payload, gated_motion=True)

    assert browser_page.locator("#predictionActions").is_hidden()
    assert browser_page.locator("#savePlanButton").is_hidden()

    browser_page.evaluate("() => window.__releaseMotionResolve()")
    browser_page.wait_for_function(
        "() => !document.querySelector('#predictionActions').hidden",
        timeout=5000,
    )

    assert browser_page.locator("#savePlanButton").inner_text() == "保存为本期方案"
    assert browser_page.locator("#savePlanButton").is_enabled()
    assert browser_page.locator("#openWorkbenchLink").get_attribute("href") == "./analysis.html?game=3d"
    assert browser_page.locator("#savedPlanLink").is_hidden()
    assert "尚未保存" in browser_page.locator("#planSaveStatus").inner_text()


def _event_dump(events):
    return json.dumps(events, ensure_ascii=False)


def _assert_event_payloads_are_safe(events):
    serialized = _event_dump(events)
    forbidden_values = [
        "测试用户",
        "隐私姓名",
        "1990-01-01",
        "1988-01-01",
        "辰",
        "杭州",
        "上海",
        "首页财运号",
        "筛选方案",
        "plan-save-1",
        "plan-detail-1",
        "request_id",
        "client_id",
        "clientId",
    ]
    forbidden_keys = {
        "name",
        "birth_date",
        "birthDate",
        "birth_hour",
        "birthHour",
        "birth_time",
        "birthTime",
        "birth_place",
        "birth_city",
        "current_city",
        "city",
        "numbers",
        "number",
        "number_text",
        "main_numbers",
        "special_numbers",
        "entries",
        "title",
        "conditions",
        "plan_id",
        "request_id",
        "client_id",
    }
    for value in forbidden_values:
        assert value not in serialized
    for event in events:
        assert set(event.get("properties", {})) <= {
            "game_key",
            "source_type",
            "mode",
            "window",
            "entry_count",
            "candidate_count",
            "freshness_status",
            "review_status",
            "tool_key",
            "result_count",
        }
        assert forbidden_keys.isdisjoint(event)
        assert forbidden_keys.isdisjoint(event.get("properties", {}))


def _wait_for_events(page, events, event_name, count, timeout_ms=5000):
    """Wait until `count` events with this name have really been posted, then return them."""
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        matched = [event for event in events if event.get("event_name") == event_name]
        if len(matched) >= count:
            return matched
        assert time.monotonic() < deadline, (
            f"only {len(matched)} {event_name} events arrived: {_event_dump(events)}"
        )
        page.wait_for_timeout(50)


def _named_events(events, event_name):
    return [event for event in events if event.get("event_name") == event_name]


def _wait_until(page, predicate, message, timeout_ms=5000):
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate():
        assert time.monotonic() < deadline, message
        page.wait_for_timeout(50)


def test_retention_events_prediction_completed_once_after_real_success_only(
    live_server_url,
    browser_page,
):
    events = []
    _route_predict_payload(browser_page, live_server_url, _prediction_payload_3d())
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body='{"accepted":true}'),
        ),
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(browser_page)
    browser_page.locator('button[data-game="3d"]').click()
    _fill_required_form(browser_page)
    browser_page.evaluate(
        """
        () => {
          document.querySelector("#submitButton").click();
          document.querySelector("#submitButton").click();
        }
        """
    )
    browser_page.wait_for_function(
        "() => !document.querySelector('#predictionActions').hidden",
        timeout=5000,
    )
    _dismiss_motion_stage(browser_page)
    browser_page.wait_for_timeout(150)

    completed = [event for event in events if event.get("event_name") == "prediction_completed"]
    assert completed == [
        {
            "event_name": "prediction_completed",
            "properties": {
                "game_key": "3d",
                "source_type": "fortune",
                "mode": "steady",
                "entry_count": 1,
                "freshness_status": "fresh",
            },
        }
    ]
    _assert_event_payloads_are_safe(events)

    completed_count = len(completed)
    browser_page.unroute(f"{live_server_url}/api/predict")
    browser_page.route(f"{live_server_url}/api/predict", lambda route: route.abort("failed"))
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(browser_page)
    browser_page.locator('button[data-game="3d"]').click()
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'error'",
        timeout=5000,
    )
    browser_page.wait_for_timeout(150)
    assert len([event for event in events if event.get("event_name") == "prediction_completed"]) == completed_count






def test_strategy_redirect_home_remains_prediction_and_3d_workbench_has_no_birth_form(
    live_server_url,
    browser_page,
):
    browser_page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(), ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        ),
    )
    browser_page.route(f"{live_server_url}/api/events", lambda route: route.fulfill(status=202, body="{}"))

    browser_page.goto(live_server_url)

    assert browser_page.locator("#predictForm").is_visible()
    assert browser_page.locator('input[name="birth_date"]').is_visible()
    assert browser_page.locator('input[name="birth_place"]').is_visible()
    browser_page.locator('button[data-game="3d"]').click()
    assert browser_page.locator("#analysisEntry").get_attribute("href") == "./analysis.html?game=3d&view=data"
    assert browser_page.locator("#strategyEntry").count() == 0

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_function("() => document.querySelector('#threeDToolbox')?.hidden === false")

    assert browser_page.locator("#threeDToolbox").is_visible()
    assert browser_page.locator("#threeDToolbox #predictForm").count() == 0
    assert browser_page.locator('#threeDToolbox input[name="name"]').count() == 0
    assert browser_page.locator('#threeDToolbox input[name="birth_date"]').count() == 0
    assert browser_page.locator('#threeDToolbox input[name="birth_hour"]').count() == 0
    assert browser_page.locator('#threeDToolbox input[name="birth_place"]').count() == 0
    assert browser_page.locator('#threeDToolbox input[name="current_city"]').count() == 0


def test_research_center_has_data_and_strategy_views_for_all_games(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&view=strategy")
    browser_page.wait_for_selector("#researchViewTabs")
    assert browser_page.locator('[data-research-view="strategy"]').get_attribute("aria-selected") == "true"
    assert browser_page.locator("#researchStrategyView").is_visible()
    assert browser_page.locator("#strategyCompat").count() == 0
    assert browser_page.locator('[data-game="3d"]').get_attribute("aria-pressed") == "true"


def test_research_view_switch_updates_url_without_duplicate_game_tabs(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=dlt&view=data&window=60")
    assert browser_page.locator("#gameTabs").count() == 1
    browser_page.locator('[data-research-view="strategy"]').click()
    browser_page.wait_for_function("() => new URLSearchParams(location.search).get('view') === 'strategy'")
    assert browser_page.locator("#researchDataView").is_hidden()
    assert browser_page.locator("#researchStrategyView").is_visible()


def test_strategy_view_hands_normalized_conditions_to_tools(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector("#useStrategyButton")
    browser_page.locator('[name="sum_min"]').fill("80")
    browser_page.locator("#useStrategyButton").click()
    browser_page.wait_for_url("**/tools.html?game=ssq&tool=conditional&source=strategy")
    handoff = browser_page.evaluate("() => JSON.parse(sessionStorage.getItem('lottery_research_handoff_v1'))")
    assert handoff["version"] == 1
    assert handoff["game_key"] == "ssq"
    assert handoff["conditions"]["sum_min"] == 80


def test_saved_strategies_stay_scoped_by_legacy_game_key_and_invalid_rows_are_preserved(live_server_url, browser_page):
    browser_page.add_init_script("""
      localStorage.setItem("lotteryLuck:strategyLab:ssq", JSON.stringify([
        {name: "旧均衡策略", preset: "balanced", form: {sum_min: 80, sum_max: 130}},
        {name: "旧非法策略", preset: "removed-preset", form: {unknown_rule: 1}}
      ]));
      localStorage.setItem("lotteryLuck:strategyLab:dlt", JSON.stringify([
        {name: "大乐透策略", preset: "balanced", form: {sum_min: 60}}
      ]));
    """)
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector('[data-saved-strategy-state="valid"]')
    assert browser_page.locator("#savedStrategies li").count() == 2
    invalid = browser_page.locator('[data-saved-strategy-state="needs-resave"]')
    assert "需要重新保存" in invalid.inner_text()
    assert invalid.get_by_role("button", name="加载").is_disabled()
    assert browser_page.locator("#savedStrategies").get_by_text("大乐透策略").count() == 0
    saved = browser_page.evaluate("() => JSON.parse(localStorage.getItem('lotteryLuck:strategyLab:ssq'))")
    assert len(saved) == 2


def test_late_strategy_response_is_ignored_after_switching_to_data(live_server_url, browser_page):
    page = browser_page
    calls = []
    page.add_init_script("""
      (() => {
        const originalFetch = window.fetch.bind(window);
        window.fetch = (input, init = {}) => {
          const url = new URL(typeof input === "string" ? input : input.url, location.origin);
          const response = originalFetch(input, init);
          if (url.pathname !== "/api/strategy/ssq/generate") return response;
          return response.then(
            (value) => new Promise((resolve) => setTimeout(() => resolve(value), 800)),
          );
        };
      })();
    """)

    def route_generate(route):
        calls.append(route.request.url)
        route.fulfill(status=200, content_type="application/json", body=json.dumps({
            "game_key": "ssq",
            "preset": "balanced",
            "strategy_name": "迟到策略",
            "description": "竞态测试",
            "conditions": {},
            "basis": {"draw_count": 12, "hot_main": [], "excluded_recent": []},
            "diagnostics": {"preset_label": "均衡型", "condition_count": 0, "active_conditions": []},
            "candidates": [{"main": [1, 2, 3, 4, 5, 6], "special": [7], "tags": ["迟到标记"]}],
            "baseline": {"label": "随机基准", "candidates": []},
            "disclaimer": "历史结果不代表未来概率。",
        }, ensure_ascii=False))

    page.route(f"{live_server_url}/api/strategy/ssq/generate", route_generate)
    page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    page.locator("#generateButton").click()
    page.locator('[data-research-view="data"]').click()
    page.wait_for_timeout(1_200)

    assert calls
    assert page.locator("#researchDataView").is_visible()
    assert page.locator("#researchStrategyView").is_hidden()
    assert "迟到标记" not in page.locator("#candidateResult").inner_text()


def test_data_view_contains_observation_only(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=data")
    browser_page.wait_for_selector("#researchDataView")
    for selector in ["#filterForm", "#backtestForm", "#poolForm", "#poolCopyButton"]:
        assert browser_page.locator(selector).count() == 0
    assert browser_page.locator("#trendPanel").count() == 1
    assert browser_page.locator("#recentPanel").count() == 1


def test_3d_data_catalog_has_no_reduction_tile(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&view=data")
    browser_page.wait_for_selector("[data-three-d-tool-key]")
    assert browser_page.locator('[data-three-d-tool-key="reduction"]').count() == 0
    assert browser_page.locator('[data-three-d-tool-panel="reduction"]').count() == 0


def test_no_execution_controls_in_research_panels(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector("#researchStrategyView")
    body_text = browser_page.locator("#researchStrategyView").inner_text()
    assert "号码篮" not in body_text
    for selector in ["#copyResults", "#addAllResults", "[data-add-result]", "[data-download-results]"]:
        assert browser_page.locator(f"#researchStrategyView {selector}").count() == 0
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=data")
    browser_page.wait_for_selector("#researchDataView")
    for selector in ["#copyResults", "#addAllResults", "[data-add-result]", "[data-download-results]"]:
        assert browser_page.locator(f"#researchDataView {selector}").count() == 0


def test_legacy_strategy_and_reduction_urls_replace_to_new_owner(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/strategy.html?game=dlt")
    browser_page.wait_for_url("**/analysis.html?game=dlt&view=strategy")
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=reduction&window=60")
    browser_page.wait_for_url("**/tools.html?game=3d&tool=conditional&source=legacy")


def test_3d_statistical_deep_links_continue_opening_data_view(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=trend")
    browser_page.wait_for_selector("#threeDToolbox:not([hidden])")
    assert browser_page.locator("#threeDToolWorkspace").is_visible()
    assert "trend" in browser_page.evaluate("() => window.location.search")

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=attributes")
    browser_page.wait_for_selector("#threeDToolbox:not([hidden])")
    assert browser_page.locator("#threeDToolWorkspace").is_visible()

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=omission&window=60")
    browser_page.wait_for_selector("#threeDToolbox:not([hidden])")
    assert (
        browser_page.locator('#threeDToolWindows [data-three-d-window="60"]').get_attribute("aria-pressed")
        == "true"
    )


def test_retention_events_workbench_opened_waits_for_summary_success(
    live_server_url,
    browser_page,
):
    events = []
    browser_page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": "summary unavailable"}),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body='{"accepted":true}'),
        ),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDFreshness')?.textContent.includes('数据加载失败')",
        timeout=5000,
    )
    browser_page.wait_for_timeout(150)

    assert [event for event in events if event.get("event_name") == "workbench_opened"] == []


def test_save_plan_click_posts_once_uses_canonical_draft_and_tracks_without_navigation(
    live_server_url,
    browser_page,
):
    payload = _prediction_payload_3d()
    _complete_3d_prediction(browser_page, live_server_url, payload)
    before_url = browser_page.url
    posts = []
    events = []

    def route_plans(route):
        body = json.loads(route.request.post_data or "{}")
        posts.append(body)
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps(
                {"plan": {"id": "plan-save-1", "request_id": body["request_id"]}, "duplicate_warning": True},
                ensure_ascii=False,
            ),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    browser_page.route(f"{live_server_url}/api/plans", route_plans)
    browser_page.route(f"{live_server_url}/api/events", route_events)

    browser_page.evaluate(
        """
        () => {
          const button = document.querySelector("#savePlanButton");
          button.click();
          button.click();
        }
        """
    )
    browser_page.wait_for_function(
        "() => !document.querySelector('#savedPlanLink').hidden",
        timeout=5000,
    )

    assert len(posts) == 1
    request_id = posts[0]["request_id"]
    assert request_id.startswith("prediction:")
    assert len(request_id) <= 96
    assert posts[0] == {
        "game_key": "3d",
        "target_issue": "2026194",
        "target_draw_date": "2026-07-13",
        "source_type": "fortune",
        "request_id": request_id,
        "title": "首页财运号",
        "entries": [
            {
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "",
            }
        ],
        "condition_snapshot": {
            "mode": "simple",
            "analysis_window": 30,
            "conditions": {},
            "metrics": {
                "sum": 6,
                "sum_tail": 6,
                "span": 2,
                "repeat_count": 0,
                "group_type": "组六",
                "odd_even": "2:1",
                "big_small": "0:3",
                "mod3": "1:1:1",
                "prime_composite": "2:1",
                "consecutive_pairs": [[1, 2], [2, 3]],
                "adjacent_pairs": [[0, 1], [1, 2]],
            },
            "latest_data_issue": "2026193",
            "latest_data_date": "2026-07-12",
        },
    }
    encoded_body = json.dumps(posts[0], ensure_ascii=False)
    for private_value in ["测试用户", "1990-01-01", "杭州", "上海"]:
        assert private_value not in encoded_body
    assert len(events) == 1
    assert events[0] == {
        "event_name": "plan_saved",
        "properties": {
            "game_key": "3d",
            "source_type": "fortune",
            "freshness_status": "fresh",
        },
    }
    assert browser_page.url == before_url
    assert browser_page.locator("#savePlanButton").inner_text() == "已保存"
    assert browser_page.locator("#savePlanButton").is_disabled()
    assert "重复" in browser_page.locator("#planSaveStatus").inner_text()
    assert browser_page.locator("#savedPlanLink").get_attribute("href") == "./result.html?id=plan-save-1"


def test_workbench_cta_stale_prediction_disables_save_but_keeps_workbench_link(
    live_server_url,
    browser_page,
):
    payload = _prediction_payload_3d(can_claim_current=False, freshness_status="stale")
    payload["data_freshness"]["sync_error"] = ""
    _complete_3d_prediction(browser_page, live_server_url, payload)

    assert browser_page.locator("#predictionActions").is_visible()
    assert browser_page.locator("#savePlanButton").is_disabled()
    assert "过期" in browser_page.locator("#planSaveStatus").inner_text()
    assert browser_page.locator("#openWorkbenchLink").get_attribute("href") == "./analysis.html?game=3d"


def test_workbench_cta_non_3d_error_and_game_switch_reset(live_server_url, browser_page):
    ssq_payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    _route_predict_payload(browser_page, live_server_url, ssq_payload)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _speed_up_motion(browser_page)
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '11 12 13 14 15 16 01'",
        timeout=5000,
    )
    _dismiss_motion_stage(browser_page)
    assert browser_page.locator("#predictionActions").is_hidden()

    browser_page.unroute(f"{live_server_url}/api/predict")
    _route_predict_payload(browser_page, live_server_url, _prediction_payload_3d())
    browser_page.locator('button[data-game="3d"]').click()
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => !document.querySelector('#predictionActions').hidden",
        timeout=5000,
    )
    _dismiss_motion_stage(browser_page)
    browser_page.locator('button[data-game="dlt"]').click()
    assert browser_page.locator("#predictionActions").is_hidden()
    assert browser_page.locator("#predictionActions").evaluate(
        "el => getComputedStyle(el).display"
    ) == "none"

    browser_page.unroute(f"{live_server_url}/api/predict")
    browser_page.route(f"{live_server_url}/api/predict", lambda route: route.abort("failed"))
    browser_page.locator('button[data-game="3d"]').click()
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'error'",
        timeout=5000,
    )
    assert browser_page.locator("#predictionActions").is_hidden()


def test_save_plan_network_pending_and_memory_unsaved_messages_keep_result(
    live_server_url,
    browser_page,
):
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    events = []
    browser_page.route(f"{live_server_url}/api/plans", lambda route: route.abort("failed"))
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body='{"accepted":true}'),
        ),
    )

    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('待同步')",
        timeout=5000,
    )
    assert "待同步" in browser_page.locator("#planSaveStatus").inner_text()
    assert "已保存" not in browser_page.locator("#planSaveStatus").inner_text()
    assert browser_page.locator("#fortuneNumber").inner_text() == "01 02 03"

    browser_page.unroute(f"{live_server_url}/api/plans")
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d([2, 3, 4]))
    browser_page.evaluate(
        """
        () => {
          const originalSetItem = Storage.prototype.setItem;
          Storage.prototype.setItem = function (key, value) {
            if (key === "lotteryLuck.pendingPlans.v1") {
              throw new DOMException("Quota exceeded", "QuotaExceededError");
            }
            return originalSetItem.call(this, key, value);
          };
        }
        """
    )
    browser_page.route(f"{live_server_url}/api/plans", lambda route: route.abort("failed"))
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#planSaveStatus').textContent.includes('尚未保存')",
        timeout=5000,
    )

    assert browser_page.locator("#savePlanButton").is_enabled()
    assert browser_page.locator("#savePlanButton").inner_text() in {"保存为本期方案", "重试保存"}
    assert browser_page.locator("#fortuneNumber").inner_text() == "02 03 04"
    assert [event for event in events if event.get("event_name") == "plan_saved"] == []


def test_save_plan_pending_online_sync_marks_current_plan_saved_and_tracks_once(
    live_server_url,
    browser_page,
):
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    posts = []
    events = []

    def route_plans(route):
        body = json.loads(route.request.post_data or "{}")
        posts.append(body)
        if len(posts) == 1:
            route.abort("failed")
            return
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps(
                {"plan": {"id": "synced-plan-1", "request_id": body["request_id"]}},
                ensure_ascii=False,
            ),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    browser_page.route(f"{live_server_url}/api/plans", route_plans)
    browser_page.route(f"{live_server_url}/api/events", route_events)

    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('待同步')",
        timeout=5000,
    )
    pending_id = browser_page.evaluate(
        "() => window.LotteryProduct.pendingPlans()[0].request_id"
    )
    browser_page.evaluate("() => window.dispatchEvent(new Event('online'))")
    browser_page.wait_for_function(
        "() => !document.querySelector('#savedPlanLink').hidden",
        timeout=5000,
    )

    assert [post["request_id"] for post in posts] == [pending_id, pending_id]
    assert browser_page.locator("#savePlanButton").inner_text() == "已保存"
    assert browser_page.locator("#savedPlanLink").get_attribute("href") == "./result.html?id=synced-plan-1"
    assert len(events) == 1
    assert events[0]["event_name"] == "plan_saved"
    assert events[0]["properties"] == {
        "game_key": "3d",
        "source_type": "fortune",
        "freshness_status": "fresh",
    }


@pytest.mark.parametrize(
    ("status", "detail", "expected_text"),
    [
        (422, "invalid plan for 隐私姓名", "工作台"),
        (503, "temporary outage for 隐私姓名", "待同步"),
    ],
)
def test_save_plan_pending_online_sync_blocked_or_retryable_status(
    live_server_url,
    browser_page,
    status,
    detail,
    expected_text,
):
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    calls = 0

    def route_plans(route):
        nonlocal calls
        calls += 1
        if calls == 1:
            route.abort("failed")
            return
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps({"detail": detail}, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/plans", route_plans)
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('待同步')",
        timeout=5000,
    )
    browser_page.evaluate("() => window.dispatchEvent(new Event('online'))")
    browser_page.wait_for_function(
        f"() => document.querySelector('#planSaveStatus').textContent.includes('{expected_text}')",
        timeout=5000,
    )

    assert "隐私姓名" not in browser_page.locator("#planSaveStatus").inner_text()
    assert browser_page.locator("#savedPlanLink").is_hidden()


def test_save_plan_sync_event_for_old_request_is_ignored(
    live_server_url,
    browser_page,
):
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    browser_page.route(f"{live_server_url}/api/plans", lambda route: route.abort("failed"))
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => window.LotteryProduct.pendingPlans().length === 1",
        timeout=5000,
    )
    old_request_id = browser_page.evaluate(
        "() => window.LotteryProduct.pendingPlans()[0].request_id"
    )

    browser_page.unroute(f"{live_server_url}/api/predict")
    _route_predict_payload(browser_page, live_server_url, _prediction_payload_3d([2, 3, 4]))
    browser_page.unroute(f"{live_server_url}/api/plans")
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '02 03 04'",
        timeout=5000,
    )
    _dismiss_motion_stage(browser_page)

    browser_page.evaluate(
        """
        (requestId) => {
          window.dispatchEvent(new CustomEvent("lotteryproduct:plansync", {
            detail: {
              request_id: requestId,
              status: "saved",
              plan: {id: "old-plan"},
              http_status: 201,
            },
          }));
        }
        """,
        old_request_id,
    )
    browser_page.wait_for_timeout(100)

    assert browser_page.locator("#fortuneNumber").inner_text() == "02 03 04"
    assert browser_page.locator("#savePlanButton").inner_text() == "保存为本期方案"
    assert browser_page.locator("#savedPlanLink").is_hidden()


def test_save_plan_request_id_uses_crypto_get_random_values_uuid_fallback(
    live_server_url,
    browser_page,
):
    browser_page.add_init_script(
        """
        (() => {
          let seed = 1;
          Object.defineProperty(window.crypto, "randomUUID", {
            value: undefined,
            configurable: true,
          });
          Object.defineProperty(window.crypto, "getRandomValues", {
            value: (array) => {
              for (let index = 0; index < array.length; index += 1) {
                array[index] = (seed + index * 13) & 255;
              }
              seed += 17;
              return array;
            },
            configurable: true,
          });
        })();
        """
    )
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    posts = []

    def route_plans(route):
        body = json.loads(route.request.post_data or "{}")
        posts.append(body)
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps({"plan": {"id": f"plan-{len(posts)}"}}, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/plans", route_plans)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
    )

    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function("() => !document.querySelector('#savedPlanLink').hidden")
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent === '保存为本期方案'",
        timeout=5000,
    )
    _dismiss_motion_stage(browser_page)
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function("() => document.querySelector('#savedPlanLink').href.includes('plan-2')")

    request_ids = [post["request_id"] for post in posts]
    assert len(request_ids) == 2
    assert request_ids[0] != request_ids[1]
    assert all(
        re.fullmatch(
            r"prediction:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request_id,
        )
        for request_id in request_ids
    )


def test_save_plan_409_and_late_response_do_not_clear_or_race_current_prediction(
    live_server_url,
    browser_page,
):
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=409,
            content_type="application/json",
            body=json.dumps({"detail": "target issue is already drawn"}, ensure_ascii=False),
        ),
    )
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#planSaveStatus').textContent.includes('本期已开奖')",
        timeout=5000,
    )
    assert browser_page.locator("#fortuneNumber").inner_text() == "01 02 03"
    assert browser_page.locator("#openWorkbenchLink").get_attribute("href") == "./analysis.html?game=3d"

    browser_page.unroute(f"{live_server_url}/api/plans")
    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d([3, 4, 5]))
    browser_page.evaluate(
        """
        () => {
          window.__resolveDelayedPlanSave = null;
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, init = {}) => {
            const url = typeof input === "string" ? input : input?.url || "";
            const method = String(init.method || "GET").toUpperCase();
            if (url.includes("/api/plans") && method === "POST") {
              return new Promise((resolve) => {
                window.__resolveDelayedPlanSave = () => resolve(new Response(JSON.stringify({
                  plan: {id: "late-plan", request_id: JSON.parse(init.body).request_id}
                }), {
                  status: 201,
                  headers: {"Content-Type": "application/json"},
                }));
              });
            }
            return originalFetch(input, init);
          };
        }
        """
    )
    browser_page.locator("#savePlanButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#savePlanButton').textContent.includes('保存中')",
        timeout=1000,
    )
    browser_page.locator('button[data-game="dlt"]').click()
    browser_page.evaluate("() => window.__resolveDelayedPlanSave()")
    browser_page.wait_for_timeout(200)

    assert browser_page.locator("#predictionActions").is_hidden()
    assert browser_page.locator("#savedPlanLink").is_hidden()


def test_workbench_cta_mobile_hidden_display_and_keyboard_focus(
    live_server_url,
    browser_page,
):
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    assert browser_page.locator("#predictionActions").evaluate(
        "el => getComputedStyle(el).display"
    ) == "none"

    _complete_3d_prediction(browser_page, live_server_url, _prediction_payload_3d())
    layout = browser_page.evaluate(
        """
        () => {
          const actions = document.querySelector("#predictionActions");
          const save = document.querySelector("#savePlanButton");
          const workbench = document.querySelector("#openWorkbenchLink");
          save.focus();
          const saveFocused = document.activeElement === save;
          workbench.focus();
          const workbenchFocused = document.activeElement === workbench;
          const rects = [actions, save, workbench].map((node) => node.getBoundingClientRect());
          return {
            scrollWidth: document.documentElement.scrollWidth,
            innerWidth: window.innerWidth,
            minButtonHeight: Math.min(save.offsetHeight, workbench.offsetHeight),
            inViewport: rects.every((rect) => rect.left >= 0 && rect.right <= window.innerWidth),
            saveFocused,
            workbenchFocused,
          };
        }
        """
    )

    assert layout["scrollWidth"] <= layout["innerWidth"]
    assert layout["minButtonHeight"] >= 40
    assert layout["inViewport"] is True
    assert layout["saveFocused"] is True
    assert layout["workbenchFocused"] is True


def test_analysis_3d_uses_dedicated_toolbox_route_url_and_game_switch(
    live_server_url, browser_page
):
    summary_calls = []
    analysis_3d_calls = []
    events = []
    latest_plan = {
        "id": "plan-current",
        "game_key": "3d",
        "target_issue": "2026183",
        "target_draw_date": "2026-07-12",
        "source_type": "manual",
        "status": "draft",
        "entries": [{"position": 0, "main_numbers": [4, 5, 6], "special_numbers": [], "note": ""}],
        "condition_snapshot": {
            "mode": "simple",
            "analysis_window": 30,
            "conditions": {},
            "metrics": {"sum": 15},
            "latest_data_issue": "2026182",
            "latest_data_date": "2026-07-11",
        },
    }

    def route_summary(route):
        summary_calls.append(route.request.url)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _workbench_summary_payload(
                    active_plan_count=1,
                    latest_plan=latest_plan,
                    window=int(re.search(r"window=(\d+)", route.request.url).group(1)),
                ),
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/workbench/3d/summary**", route_summary)
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": [latest_plan]}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/analysis/3d**",
        lambda route: (
            analysis_3d_calls.append(route.request.url),
            route.fulfill(status=500, content_type="application/json", body='{"detail":"wrong api"}'),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
        ),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_selector("#threeDToolbox:not([hidden])")
    assert (
        browser_page.locator("#threeDToolbox h1").inner_text() == "福彩3D工具箱"
    )

    assert analysis_3d_calls == []
    assert browser_page.locator("#analysisWorkbench").is_hidden()
    assert browser_page.locator("#threeDToolbox").is_visible()
    assert browser_page.locator("#threeDToolHome").is_visible()
    assert browser_page.locator("#threeDToolWorkspace").is_hidden()
    assert "1个本期方案" in browser_page.locator("#threeDPlanStrip").inner_text()
    browser_page.wait_for_function(
        "() => window.location.search === '?game=3d&view=data&window=30'"
    )

    _open_3d_tool(browser_page, "frequency")
    browser_page.wait_for_function(
        "() => window.location.search === '?game=3d&view=data&window=30&tool=frequency'"
    )
    assert browser_page.locator("#threeDToolHome").is_hidden()
    assert browser_page.locator("#threeDToolTitle").inner_text() == "出次统计"
    assert browser_page.locator('[data-three-d-window="30"]').get_attribute("aria-pressed") == "true"

    opened_events = [event for event in events if event.get("event_name") == "workbench_opened"]
    assert len(opened_events) == 1
    assert opened_events[0]["properties"] == {"game_key": "3d", "window": 30}
    # Opening the tool also records tool_opened; wait for it so the duplicate-click check
    # below cannot mistake a late arrival of this event for an event the duplicate click made.
    _wait_for_events(browser_page, events, "tool_opened", 1)

    summary_count_before_duplicate = len(summary_calls)
    event_count_before_duplicate = len(events)
    browser_page.locator('button[data-game="3d"]').click()
    browser_page.wait_for_timeout(200)
    assert len(summary_calls) == summary_count_before_duplicate
    assert len(events) == event_count_before_duplicate

    summary_count_before_ssq = len(summary_calls)
    browser_page.locator('button[data-game="ssq"]').click()
    browser_page.wait_for_function("() => new URLSearchParams(location.search).get('game') === 'ssq'")
    assert "tool=" not in browser_page.evaluate("() => location.search")
    assert browser_page.locator("#analysisWorkbench").is_visible()
    assert browser_page.locator("#threeDToolbox").is_hidden()
    assert len(summary_calls) == summary_count_before_ssq

    browser_page.locator('button[data-game="3d"]').click()
    browser_page.wait_for_function(
        "() => window.location.search === '?game=3d&view=data&window=30'"
    )
    assert browser_page.locator("#threeDToolbox").is_visible()
    assert browser_page.locator("#threeDToolHome").is_visible()
    browser_page.wait_for_timeout(200)
    assert len(summary_calls) == summary_count_before_ssq + 1
    reopened_events = [event for event in events if event.get("event_name") == "workbench_opened"]
    assert len(reopened_events) == 2


def test_3d_toolbox_ignores_late_plan_responses_and_filters_current_target(
    live_server_url, browser_page
):
    old_plan = {
        "id": "old-plan",
        "game_key": "3d",
        "target_issue": "2026182",
        "target_draw_date": "2026-07-11",
        "source_type": "manual",
        "status": "draft",
        "entries": [{"position": 0, "main_numbers": [1, 1, 1], "special_numbers": [], "note": ""}],
    }
    current_plan = {
        "id": "current-plan",
        "game_key": "3d",
        "target_issue": "2026183",
        "target_draw_date": "2026-07-12",
        "source_type": "filter",
        "status": "saved",
        "entries": [{"position": 0, "main_numbers": [6, 6, 2], "special_numbers": [], "note": ""}],
    }
    init_script = """
        (() => {
          const originalFetch = window.fetch.bind(window);
          const oldPlan = __OLD_PLAN__;
          const currentPlan = __CURRENT_PLAN__;
          window.__planQueueForTest = [
            {delay: 500, body: {plans: [oldPlan]}},
            {delay: 0, body: {plans: [oldPlan, currentPlan]}},
          ];
          window.__planFetchCallsForTest = 0;
          window.fetch = (input, init = {}) => {
            const url = new URL(typeof input === "string" ? input : input.url, location.origin);
            const method = String(init.method || (typeof input === "string" ? "GET" : input.method || "GET")).toUpperCase();
            if (url.pathname === "/api/plans" && method === "GET") {
              window.__planFetchCallsForTest += 1;
              const item = window.__planQueueForTest.shift() || {delay: 0, body: {plans: []}};
              return new Promise((resolve) => {
                setTimeout(() => {
                  resolve(new Response(JSON.stringify(item.body), {
                    status: 200,
                    headers: {"Content-Type": "application/json"},
                  }));
                }, item.delay);
              });
            }
            return originalFetch(input, init);
          };
        })();
        """
    init_script = init_script.replace("__OLD_PLAN__", json.dumps(old_plan, ensure_ascii=False))
    init_script = init_script.replace("__CURRENT_PLAN__", json.dumps(current_plan, ensure_ascii=False))
    browser_page.add_init_script(init_script)
    browser_page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(), ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_function("() => document.querySelector('#threeDToolbox')?.hidden === false")
    browser_page.locator('button[data-game="ssq"]').click()
    browser_page.wait_for_function("() => new URLSearchParams(location.search).get('game') === 'ssq'")
    browser_page.locator('button[data-game="3d"]').click()
    browser_page.wait_for_function("() => document.querySelector('#threeDPlanStrip')?.textContent.includes('current-plan') || document.querySelector('#threeDPlanDetailLink')?.href.includes('current-plan')")
    browser_page.wait_for_timeout(650)

    strip_text = browser_page.locator("#threeDPlanStrip").inner_text()
    assert "1个本期方案" in strip_text
    assert "2026183 / 2026-07-12" in strip_text
    assert "2026182 / 2026-07-11" not in strip_text
    assert browser_page.locator("#threeDPlanDetailLink").get_attribute("href").endswith("id=current-plan")


def test_3d_toolbox_flow_renders_recent_query_and_xss_safe_freshness(
    live_server_url, browser_page
):
    query_requests = []
    summary = _workbench_summary_payload(active_plan_count=0, latest_plan=None)
    summary["freshness"]["message"] = "<img src=x onerror=alert(1)>数据已更新至第2026182期"
    summary["recent_draws"][0]["issue"] = "<script>2026182</script>"

    browser_page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(summary, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        ),
    )

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_requests.append(body)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_function("() => document.querySelector('#threeDToolbox')?.hidden === false")
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDFreshness')?.textContent.includes('数据已更新至第2026182期')"
    )

    assert browser_page.locator("#threeDFreshness img").count() == 0
    assert "<img src=x onerror=alert(1)>" in browser_page.locator("#threeDFreshness").inner_text()

    _open_3d_tool(browser_page, "recent")
    assert browser_page.locator("#threeDRecentDraws script").count() == 0
    assert browser_page.locator("#threeDRecentDraws li").count() == 10
    assert "<script>2026182</script>" in browser_page.locator("#threeDRecentDraws").inner_text()

    browser_page.go_back()
    browser_page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(browser_page, "number")
    browser_page.locator("#threeDNumberQueryInput").fill("006")
    with browser_page.expect_response(f"{live_server_url}/api/3d/number-query"):
        browser_page.locator("#threeDNumberQueryForm button[type='submit']").click()
    browser_page.wait_for_function("() => document.querySelector('#threeDNumberQueryResult')?.textContent.includes('直选')")

    assert query_requests == [{"number": "006", "window": 30}]
    query_text = browser_page.locator("#threeDNumberQueryResult").inner_text()
    assert "直选" in query_text
    assert "组选" in query_text
    assert "1" in query_text
    assert "2" in query_text


def _stub_3d_toolbox_shell(browser_page, live_server_url, summary=None):
    """Route the summary, plan list and event endpoints the toolbox shell needs."""
    payload = summary if summary is not None else _workbench_summary_payload()
    browser_page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body='{"accepted":true}'
        ),
    )


def _open_tool_definition(page):
    """Open the tool definition's 说明 disclosure the way a user does, and read what renders.

    The mandatory line (window, real sample, latest data date, disclaimer) is the summary and
    is asserted visible without a click; only the mechanics of the statistic live behind the
    disclosure. inner_text() is deliberate: it returns what is actually rendered, so this
    still fails if the mechanics never make it onto the screen.
    """
    definition = page.locator("#threeDToolDefinition")
    summary = definition.locator("summary")
    summary.wait_for(state="visible")
    if definition.get_attribute("open") is None:
        summary.click()
    page.wait_for_function(
        "() => document.querySelector('#threeDToolDefinition')?.open === true"
    )
    return definition.inner_text()


def _wait_for_query_result(browser_page, tool, needle):
    browser_page.wait_for_function(
        "([tool, needle]) => document"
        ".querySelector(`[data-three-d-tool-panel=\"${tool}\"] [data-tool-result]`)"
        "?.textContent.includes(needle)",
        arg=[tool, needle],
    )


def test_3d_tool_events_record_open_once_and_result_only_on_active_submit(
    live_server_url, browser_page
):
    """tool_opened fires once per tool; tool_result_generated only on a real submitted result."""
    events = []
    query_requests = []
    query_fails = {"value": False}

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_requests.append(body)
        if query_fails["value"]:
            route.fulfill(status=500, content_type="application/json", body='{"detail":"boom"}')
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_number_query_payload(body["number"], window=body["window"]), ensure_ascii=False),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/events", route_events)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_selector("#threeDToolHome:not([hidden])")

    _open_3d_tool(browser_page, "number")
    opened = _wait_for_events(browser_page, events, "tool_opened", 1)
    assert opened[0]["properties"] == {"game_key": "3d", "tool_key": "number", "window": 30}

    # Re-opening the same tool is not a first open, and no render along the way records again.
    browser_page.go_back()
    browser_page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(browser_page, "number")
    browser_page.wait_for_timeout(300)
    assert len(_named_events(events, "tool_opened")) == 1
    assert _named_events(events, "tool_result_generated") == []

    # A submitted query that really came back records exactly one result event.
    browser_page.locator("#threeDNumberQueryInput").fill("006")
    with browser_page.expect_response(f"{live_server_url}/api/3d/number-query"):
        browser_page.locator("#threeDNumberQueryForm button[type='submit']").click()
    browser_page.wait_for_function("() => document.querySelector('#threeDNumberQueryResult')?.textContent.includes('直选')")
    generated = _wait_for_events(browser_page, events, "tool_result_generated", 1)
    assert generated[0]["properties"] == {
        "game_key": "3d",
        "tool_key": "number",
        "result_count": 1,
    }

    # Re-rendering the payload already on screen records nothing new.
    browser_page.locator("#threeDFreshness").get_by_role("button", name="重试").click()
    browser_page.wait_for_timeout(300)
    assert len(_named_events(events, "tool_result_generated")) == 1
    assert len(_named_events(events, "tool_opened")) == 1

    # A failed submit records nothing at all.
    query_fails["value"] = True
    browser_page.locator("#threeDNumberQueryInput").fill("007")
    with browser_page.expect_response(f"{live_server_url}/api/3d/number-query"):
        browser_page.locator("#threeDNumberQueryForm button[type='submit']").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDNumberQueryFeedback')?.classList.contains('is-error') === true"
    )
    browser_page.wait_for_timeout(300)
    assert len(_named_events(events, "tool_result_generated")) == 1

    _assert_event_payloads_are_safe(events)


def test_3d_tool_open_records_nothing_when_the_tool_data_fails_to_load(
    live_server_url, browser_page
):
    """A failed tool open is not an open.

    The panel reports its error and no tool_opened event is recorded. Only a load that
    really came up may count, so hoisting the tracking call above the `rendered === false`
    guard (and thus counting every failed load as an open) fails here.
    """
    page = browser_page
    events = []
    summary_ok = {"value": False}

    def route_summary(route):
        if not summary_ok["value"]:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "summary unavailable"}),
            )
            return
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    # Registered last, so it wins over the shell's fire-and-forget events route.
    page.route(f"{live_server_url}/api/events", route_events)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=heat&window=60")
    page.wait_for_selector('[data-three-d-tool-panel="heat"]:not([hidden])')
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"heat\"] [data-tool-status]')"
        "?.dataset.state === 'error'"
    )
    page.wait_for_timeout(300)

    status = page.locator('[data-three-d-tool-panel="heat"] [data-tool-status]')
    assert "加载失败" in status.inner_text()
    assert _named_events(events, "tool_opened") == []
    assert _named_events(events, "tool_result_generated") == []

    # The guard is not "never record": once the data really loads, the same tool that failed
    # records its first open exactly once.
    summary_ok["value"] = True
    page.locator('[data-three-d-window="120"]').click()
    opened = _wait_for_events(page, events, "tool_opened", 1)
    assert opened[0]["properties"] == {"game_key": "3d", "tool_key": "heat", "window": 120}
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"heat\"] [data-tool-status]')"
        "?.dataset.state !== 'error'"
    )
    page.wait_for_timeout(300)
    assert len(_named_events(events, "tool_opened")) == 1
    _assert_event_payloads_are_safe(events)


def test_3d_tool_event_payloads_are_safe_and_never_carry_the_queried_number(
    live_server_url, browser_page
):
    events = []
    query_calls = {"count": 0}

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_calls["count"] += 1
        # The second query fails: a failed lookup is not a generated result.
        if query_calls["count"] == 2:
            route.fulfill(status=500, content_type="application/json", body='{"detail":"boom"}')
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/events", route_events)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(browser_page, "number")
    opened = _wait_for_events(browser_page, events, "tool_opened", 1)
    assert opened[0]["properties"] == {"game_key": "3d", "tool_key": "number", "window": 30}

    browser_page.locator("#threeDNumberQueryInput").fill("006")
    with browser_page.expect_response(f"{live_server_url}/api/3d/number-query"):
        browser_page.locator("#threeDNumberQueryForm button[type='submit']").click()
    _wait_for_query_result(browser_page, "number", "直选")
    generated = _wait_for_events(browser_page, events, "tool_result_generated", 1)
    assert generated[0]["properties"] == {
        "game_key": "3d",
        "tool_key": "number",
        "result_count": 1,
    }

    # A failed query keeps the previous result on screen but generates no new result event.
    browser_page.locator("#threeDNumberQueryInput").fill("123")
    with browser_page.expect_response(f"{live_server_url}/api/3d/number-query"):
        browser_page.locator("#threeDNumberQueryForm button[type='submit']").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#threeDNumberQueryFeedback')"
        "?.classList.contains('is-error') === true"
    )
    browser_page.wait_for_timeout(300)
    assert len(_named_events(events, "tool_result_generated")) == 1

    # The queried digits are user input: they never ride along in an analytics event.
    for number in ["006", "123"]:
        assert all(number not in json.dumps(event, ensure_ascii=False) for event in events)
    _assert_event_payloads_are_safe(events)


def test_3d_attributes_tool_shows_server_attributes_for_leading_zero_number(
    live_server_url, browser_page
):
    query_requests = []
    events = []

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_requests.append(body)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    def route_events(route):
        events.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="application/json", body='{"accepted":true}')

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/events", route_events)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=attributes")
    panel = browser_page.locator('[data-three-d-tool-panel="attributes"]')
    panel.wait_for(state="visible")
    panel.get_by_label("属性号码").fill("006")
    panel.get_by_role("button", name="查询属性").click()
    _wait_for_query_result(browser_page, "attributes", "和值")

    result = panel.locator("[data-tool-result]")
    assert query_requests == [{"number": "006", "window": 30}]
    assert "006" in result.inner_text()
    assert "和值 6" in result.inner_text()
    assert "和值尾 6" in result.inner_text()
    assert "跨度 6" in result.inner_text()
    assert "组三" in result.inner_text()
    assert "奇偶 0:3" in result.inner_text()
    assert "大小 1:2" in result.inner_text()
    assert "012路 3:0:0" in result.inner_text()
    assert "质合 0:3" in result.inner_text()
    assert "相邻 无" in result.inner_text()
    assert "连号 无" in result.inner_text()
    # History hits stay available as secondary information on the attributes tool.
    assert "直选" in result.inner_text()
    assert "组选" in result.inner_text()
    # 号码属性 states what it computes, and that it computes it from the input digits. What it
    # computes from and the disclaimer are visible with no click; the mechanics are in 说明.
    visible_definition = browser_page.locator("#threeDToolDefinition").inner_text()
    assert "不依赖历史开奖" in visible_definition
    assert "不代表未来开奖结果" in visible_definition
    definition = _open_tool_definition(browser_page)
    assert "相邻" in definition
    assert "连号" in definition

    # The queried number is user input and never leaves in an analytics event. Events must
    # actually have been delivered, or this assertion would be vacuous.
    assert [event.get("event_name") for event in events].count("workbench_opened") == 1
    assert all("006" not in json.dumps(event, ensure_ascii=False) for event in events)


def test_3d_number_tool_leads_with_history_hits_and_position_omissions_under_stale_data(
    live_server_url, browser_page
):
    query_requests = []

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_requests.append(body)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    _stub_3d_toolbox_shell(
        browser_page,
        live_server_url,
        summary=_workbench_summary_payload(status="stale", can_save=False),
    )
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=number")
    panel = browser_page.locator('[data-three-d-tool-panel="number"]')
    panel.wait_for(state="visible")
    panel.get_by_label("三位号码").fill("006")
    panel.get_by_role("button", name="查询", exact=True).click()
    _wait_for_query_result(browser_page, "number", "直选次数")

    result = panel.locator("[data-tool-result]")
    text = result.inner_text()
    # Stale data must not block a read-only historical lookup.
    assert query_requests == [{"number": "006", "window": 30}]
    assert "006" in text
    assert "直选次数 1" in text
    assert "组选次数 2" in text
    assert "最近命中 2026181" in text
    assert "百位 当前遗漏 4" in text
    assert "十位 当前遗漏 1" in text
    assert "个位 当前遗漏 0" in text
    # The omissions must be labelled with the window and the sample they came from.
    assert "位置遗漏统计近30期，实际取到30期" in text
    assert "近120期" not in text
    # Attributes stay secondary on this tool.
    assert "和值 6" in text
    assert "跨度 6" in text

    # 号码查询 states its statistical definition like every other tool: what it counts and the
    # disclaimer without a click, the mechanics of 直选/组选/位置遗漏 behind 说明.
    visible_definition = browser_page.locator("#threeDToolDefinition").inner_text()
    assert "查你输入的三位号码在过去开出过多少次" in visible_definition
    assert "不代表未来开奖结果" in visible_definition
    definition = _open_tool_definition(browser_page)
    assert "直选" in definition
    assert "组选" in definition


def test_3d_number_tool_states_the_real_sample_when_history_is_shorter_than_the_window(
    live_server_url, browser_page
):
    # The window asks for 30 draws, but only 12 exist, so the stats came from 12.
    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"], sample_size=12),
                ensure_ascii=False,
            ),
        )

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=number")
    panel = browser_page.locator('[data-three-d-tool-panel="number"]')
    panel.wait_for(state="visible")
    panel.get_by_label("三位号码").fill("006")
    panel.get_by_role("button", name="查询", exact=True).click()
    _wait_for_query_result(browser_page, "number", "直选次数")

    text = panel.locator("[data-tool-result]").inner_text()
    assert "位置遗漏统计近30期，实际取到12期" in text
    # The largest omission the sample can hold is the sample itself.
    assert "最大 12" in text

    # The fact layout that replaced the old query grid must survive a phone viewport.
    browser_page.set_viewport_size({"width": 390, "height": 780})
    browser_page.wait_for_timeout(100)
    assert browser_page.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth"
    )
    assert browser_page.evaluate(
        """() => {
          const list = document.querySelector('#threeDNumberQueryResult .three-d-fact-list');
          return getComputedStyle(list).gridTemplateColumns.split(' ').length;
        }"""
    ) == 1
    assert panel.locator("[data-tool-result]").is_visible()


def test_3d_number_tool_keeps_last_result_when_a_refresh_fails_and_retry_recovers(
    live_server_url, browser_page
):
    query_attempts = []

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_attempts.append(body)
        if len(query_attempts) == 2:
            route.abort("failed")
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=number")
    panel = browser_page.locator('[data-three-d-tool-panel="number"]')
    panel.wait_for(state="visible")
    panel.get_by_label("三位号码").fill("006")
    panel.get_by_role("button", name="查询", exact=True).click()
    _wait_for_query_result(browser_page, "number", "直选次数")

    feedback = panel.locator("[data-tool-feedback]")
    result = panel.locator("[data-tool-result]")
    panel.get_by_role("button", name="查询", exact=True).click()
    browser_page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"number\"] "
        "[data-tool-feedback]')?.textContent.includes('刷新失败')"
    )

    # The failed refresh keeps the last successful result on screen.
    assert "直选次数 1" in result.inner_text()
    assert len(query_attempts) == 2

    feedback.get_by_role("button", name="重试").click()
    browser_page.wait_for_function(
        "() => !document.querySelector('[data-three-d-tool-panel=\"number\"] "
        "[data-tool-feedback]')?.textContent.includes('刷新失败')"
    )
    assert len(query_attempts) == 3
    assert "直选次数 1" in result.inner_text()


def test_3d_attributes_tool_drops_stale_result_on_input_change_and_reports_invalid_number(
    live_server_url, browser_page
):
    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        if body.get("number") != "006":
            route.fulfill(
                status=422,
                content_type="application/json",
                body=json.dumps({"detail": "invalid 3d number"}, ensure_ascii=False),
            )
            return
        payload = _number_query_payload("006")
        payload["number_text"] = '<img src=x onerror="window.__queryInjected=1">006'
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        )

    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.route(f"{live_server_url}/api/3d/number-query", route_query)

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=attributes")
    panel = browser_page.locator('[data-three-d-tool-panel="attributes"]')
    panel.wait_for(state="visible")
    panel.get_by_label("属性号码").fill("006")
    panel.get_by_role("button", name="查询属性").click()
    _wait_for_query_result(browser_page, "attributes", "和值")

    result = panel.locator("[data-tool-result]")
    # API text renders as text, never as markup.
    assert result.locator("img").count() == 0
    assert browser_page.evaluate("() => window.__queryInjected") is None
    assert '<img src=x onerror="window.__queryInjected=1">006' in result.inner_text()

    panel.get_by_label("属性号码").fill("00")
    browser_page.wait_for_function(
        "() => !document.querySelector('[data-three-d-tool-panel=\"attributes\"] "
        "[data-tool-result]')?.textContent.includes('和值')"
    )
    assert "和值" not in result.inner_text()

    # The server rejects this number, and its 422 surfaces as the input error.
    panel.get_by_label("属性号码").fill("777")
    panel.get_by_role("button", name="查询属性").click()
    browser_page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"attributes\"] "
        "[data-tool-feedback]')?.textContent.includes('请输入三位数字')"
    )
    assert "和值" not in result.inner_text()


# A rendered 出次统计 on a 390px phone: chrome, the definition line, the window tabs and the
# 3x10 matrix. Well below what the tool really draws (~790px), far above a blank page.
MOBILE_TOOL_VIEW_MIN_CONTENT_HEIGHT = 600


ADMIN_SESSION_KEY = "lottery_luck_admin_session"


def _admin_settings_payload():
    return {
        "metaphysics_weights": {
            "steady": {
                "personal_space": 40,
                "ai_fortune": 20,
                "draw_day_luck": 20,
                "history_guardrail": 20,
            }
        },
        "ai_copy_styles": [{"label": "短钩子", "description": "测试文案"}],
        "prediction_quota": {
            "free_daily": 1,
            "new_user_bonus": 3,
            "member_daily": 20,
            "package_units": [6, 18],
            "enabled_games": ["ssq"],
            "mode_costs": {"steady": 1, "windfall": 2, "guard": 1},
        },
    }


def _admin_health_payload():
    return {
        "today": "2026-07-12",
        "kpis": {
            "healthy_games": 1,
            "attention_games": 0,
            "empty_games": 0,
            "total_draws": 12,
            "latest_crawl_at": "2026-07-12T08:00:00+00:00",
        },
        "games": [],
        "logs": [],
        "commands": {},
        "failure_summary": {"has_failure": False},
    }


def _admin_tasks_payload():
    return {"tasks": []}


def _route_admin_api(page, live_server_url, handler):
    page.route(f"{live_server_url}/api/admin/**", handler)


def _admin_locked(page):
    return page.locator("#dataAdmin").get_attribute("data-locked") == "true"


def _stored_admin_token(page):
    return page.evaluate(f"() => sessionStorage.getItem('{ADMIN_SESSION_KEY}')")


def _wait_for_request_count(page, requests, count, timeout=5):
    deadline = time.time() + timeout
    while len(requests) < count and time.time() < deadline:
        page.wait_for_timeout(50)


PRODUCT_CLIENT_URL = "/product-client.js?v=20260713-product-client-v2"


def _load_product_client_page(page, live_server_url):
    page.goto(f"{live_server_url}/privacy.html")
    page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    page.wait_for_function("() => Boolean(window.LotteryProduct)")


def _pending_plan_payload(request_id="pending-1"):
    return {
        "game_key": "3d",
        "target_issue": "2026156",
        "target_draw_date": "2026-06-16",
        "source_type": "manual",
        "request_id": request_id,
        "title": "offline plan",
        "entries": [
            {
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "first",
            }
        ],
        "condition_snapshot": {
            "mode": "pro",
            "analysis_window": 60,
            "conditions": {"group_type": "组三", "sum_min": 4},
            "metrics": {"span": 2, "sum": 6},
            "latest_data_issue": "2026155",
            "latest_data_date": "2026-06-15",
        },
    }


SAFE_PLAN_TITLES = {
    "fortune": "首页财运号",
    "manual": "手动选号",
    "filter": "筛选方案",
    "random": "随机选号",
    "carried": "沿用方案",
}


def _sanitized_pending_plan_payload(request_id="pending-1"):
    payload = json.loads(json.dumps(_pending_plan_payload(request_id), ensure_ascii=False))
    payload["title"] = SAFE_PLAN_TITLES[payload["source_type"]]
    payload["entries"][0]["note"] = ""
    payload["condition_snapshot"]["conditions"] = {"sum_min": 4}
    payload["condition_snapshot"]["metrics"] = {"span": 2, "sum": 6}
    return payload


def test_3d_toolbox_first_screen_exposes_tools_and_has_no_mobile_overflow(
    live_server_url, browser_page
):
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolbox:not([hidden])")

    assert page.get_by_role("heading", name="福彩3D工具箱").is_visible()
    assert page.get_by_role("button", name="走势图").is_visible()
    assert page.get_by_role("button", name="最近开奖").is_visible()
    assert page.locator("#threeDToolbox").evaluate(
        "node => node.scrollWidth <= document.documentElement.clientWidth"
    )


# Release gate: on a 390x844 phone the toolbox home must show the draw status and at least
# this many tool entries without scrolling.
MOBILE_FIRST_SCREEN_MIN_TOOLS = 6
# No mobile compaction may push a tool entry below the project's touch floor.
MOBILE_TAP_TARGET_FLOOR = 40

MOBILE_FOLD_PLAN = {
    "id": "plan-current",
    "game_key": "3d",
    "target_issue": "2026183",
    "target_draw_date": "2026-07-12",
    "source_type": "manual",
    "status": "draft",
    "entries": [{"position": 0, "main_numbers": [4, 5, 6], "special_numbers": [], "note": ""}],
    "condition_snapshot": {
        "mode": "simple",
        "analysis_window": 30,
        "conditions": {},
        "metrics": {"sum": 15},
        "latest_data_issue": "2026182",
        "latest_data_date": "2026-07-11",
    },
}


def _measure_mobile_first_screen(page):
    measured = page.evaluate(
        """
        () => {
          const fold = window.innerHeight;
          const band = document.querySelector("#threeDFreshness");
          const bandRect = band?.getBoundingClientRect();
          const tiles = Array.from(document.querySelectorAll("[data-three-d-tool-key]"));
          const box = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const rect = node.getBoundingClientRect();
            return {
              top: Math.round(rect.top),
              bottom: Math.round(rect.bottom),
              height: Math.round(rect.height),
            };
          };
          return {
            fold,
            scrollY: window.scrollY,
            statusFullyVisible: Boolean(bandRect && bandRect.top >= 0 && bandRect.bottom <= fold),
            statusBox: box("#threeDFreshness"),
            statusText: (band?.textContent || "").replace(/\\s+/g, " ").trim(),
            toolsAboveFold: tiles
              .filter((tile) => tile.getBoundingClientRect().bottom <= fold)
              .map((tile) => tile.dataset.threeDToolKey),
            minTileHeight: tiles.length
              ? Math.min(...tiles.map((tile) => Math.round(tile.getBoundingClientRect().height)))
              : 0,
            chrome: {
              siteHeader: box(".site-header"),
              gameTabs: box("#gameTabs"),
              toolboxHead: box(".three-d-toolbox-head"),
              planStrip: box("#threeDPlanStrip"),
            },
          };
        }
        """
    )
    # Printed so a failing run reports the real numbers instead of a truncated repr.
    print("mobile_first_screen:", json.dumps(measured, ensure_ascii=False))
    return measured


def test_3d_toolbox_mobile_first_screen_shows_status_and_six_tools_above_the_fold(
    live_server_url, browser_page
):
    """The plan's release gate: 390px, no scrolling, draw status + >= 6 tool entries."""
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})

    def route_summary(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _workbench_summary_payload(active_plan_count=1, latest_plan=MOBILE_FOLD_PLAN),
                ensure_ascii=False,
            ),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolbox:not([hidden])")
    # Measure the settled band, not the "数据加载中。" placeholder.
    page.wait_for_function(
        "() => document.querySelector('#threeDFreshness')?.textContent.includes('2026182')"
    )
    page.wait_for_function(
        "() => document.querySelector('#threeDPlanStrip')?.textContent.includes('本期方案')"
    )

    measured = _measure_mobile_first_screen(page)

    assert measured["scrollY"] == 0, measured
    assert page.locator("[data-three-d-tool-key]").count() == 7, measured
    # The count may never be bought by shrinking tiles below the touch floor.
    assert measured["minTileHeight"] >= MOBILE_TAP_TARGET_FLOOR, measured
    assert measured["statusFullyVisible"], measured
    assert len(measured["toolsAboveFold"]) >= MOBILE_FIRST_SCREEN_MIN_TOOLS, measured


# Release gate for the tool view: once a tool is open, the toolbox-home chrome above it (the
# kicker, the big page title, the home subtitle, the plan strip) is overhead the reader did not
# ask for. The tool's own data must start inside the first screen at both widths. The bars are
# set from what the compacted tool view really achieves (~470px desktop / ~490px mobile) with
# room for font fallbacks; before the compaction the table started at 787px / 734px.
TOOL_DATA_MAX_TOP_DESKTOP = 560
TOOL_DATA_MAX_TOP_MOBILE = 570


def _measure_tool_view(page):
    """Where the open tool's data really starts, and what the chrome above it costs."""
    measured = page.evaluate(
        """
        () => {
          const panel = '[data-three-d-tool-panel="frequency"]';
          const table = document.querySelector(`${panel} table`);
          const row = document.querySelector(`${panel} tbody tr`);
          const shown = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return false;
            const rect = node.getBoundingClientRect();
            return rect.width > 1 && rect.height > 1;
          };
          const docTop = (node) =>
            node ? Math.round(node.getBoundingClientRect().top + window.scrollY) : null;
          const definition = document.querySelector("#threeDToolDefinition");
          return {
            fold: window.innerHeight,
            scrollY: window.scrollY,
            dataTop: docTop(table),
            firstRowBottom: row
              ? Math.round(row.getBoundingClientRect().bottom + window.scrollY)
              : null,
            planStripShown: shown("#threeDPlanStrip"),
            pageTitleShown: shown("#threeDToolboxTitle"),
            toolTitle: (document.querySelector("#threeDToolTitle")?.innerText || "").trim(),
            // innerText, not textContent: only what a reader can actually see counts.
            definitionVisibleText: (definition?.innerText || "").replace(/\\s+/g, " ").trim(),
            noOverflow:
              document.documentElement.scrollWidth <= document.documentElement.clientWidth,
          };
        }
        """
    )
    print("tool_view:", json.dumps(measured, ensure_ascii=False))
    return measured


@pytest.mark.parametrize(
    ("width", "height", "max_top"),
    (
        (1440, 900, TOOL_DATA_MAX_TOP_DESKTOP),
        (390, 844, TOOL_DATA_MAX_TOP_MOBILE),
    ),
)
def test_3d_tool_view_lifts_tool_data_above_the_home_chrome(
    live_server_url, browser_page, width, height, max_top
):
    page = browser_page
    page.set_viewport_size({"width": width, "height": height})
    _stub_3d_toolbox_shell(page, live_server_url)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=frequency&window=30")
    page.wait_for_selector('[data-three-d-tool-panel="frequency"] [data-digit-cell]')
    page.wait_for_function(
        "() => document.querySelector('#threeDToolDefinition')?.innerText.includes('近30期')"
    )

    measured = _measure_tool_view(page)

    assert measured["scrollY"] == 0, measured
    assert measured["noOverflow"], measured
    assert measured["toolTitle"] == "出次统计", measured
    # The data itself, not the chrome, owns the top of the tool view.
    assert measured["dataTop"] is not None, measured
    assert measured["dataTop"] <= max_top, measured
    # The first row of real data is readable without scrolling.
    assert measured["firstRowBottom"] <= measured["fold"], measured
    # The home chrome is home chrome: the plan strip belongs to the toolbox home screen.
    assert measured["planStripShown"] is False, measured
    # The page heading stays in the accessibility tree; the tool's own title carries the view.
    assert measured["pageTitleShown"] is False, measured
    assert page.get_by_role("heading", name="福彩3D工具箱").count() == 1

    # Honesty guarantees are never traded for height: the window, the real sample, the latest
    # data date and the disclaimer stay visible, with no click.
    visible = measured["definitionVisibleText"]
    assert "近30期" in visible, visible
    assert "实际取到30期" in visible, visible
    assert "2026-07-11" in visible, visible
    assert "不代表未来概率" in visible, visible
    # The stale/blocked reason and the data date stay in the issue band, next to 重试.
    band = page.locator("#threeDFreshness")
    assert band.is_visible()
    assert "2026-07-11" in band.inner_text()
    assert band.get_by_role("button", name="重试").is_visible()

    # Leaving the tool restores the home screen the chrome belongs to.
    page.go_back()
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    assert page.locator("#threeDPlanStrip").is_visible()
    assert page.locator("#threeDToolboxTitle").is_visible()


# A tile row that stops short of its grid's right edge leaves bordered dead space: the
# "超长空白" the visual rules forbid. One pixel of slack absorbs sub-pixel rounding only.
TOOL_ROW_EDGE_SLACK = 1


def _measure_tool_group_rows(page):
    """Per tool group, per tile row: does the row reach the right edge of its grid?

    The groups hold 4 / 2 / 1 tools. A fixed 4-column grid therefore leaves empty
    cells, and because the grid paints the cell borders those cells read as bordered dead
    areas. Measuring the row's right edge against the grid's content box catches exactly
    that, at whatever column count the viewport resolves to.
    """
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll(".three-d-tool-grid")).map((grid) => {
          const style = getComputedStyle(grid);
          const gridRect = grid.getBoundingClientRect();
          const contentRight =
            gridRect.right -
            parseFloat(style.paddingRight || "0") -
            parseFloat(style.borderRightWidth || "0");
          const tiles = Array.from(grid.querySelectorAll("[data-three-d-tool-key]"));
          const rows = new Map();
          for (const tile of tiles) {
            const rect = tile.getBoundingClientRect();
            const key = Math.round(rect.top);
            const row = rows.get(key) || { top: key, right: -Infinity, tiles: [] };
            row.right = Math.max(row.right, rect.right);
            row.tiles.push(tile.dataset.threeDToolKey);
            rows.set(key, row);
          }
          return {
            id: grid.id,
            tileCount: tiles.length,
            contentRight: Math.round(contentRight),
            rows: Array.from(rows.values())
              .sort((a, b) => a.top - b.top)
              .map((row) => ({
                top: row.top,
                right: Math.round(row.right),
                gapToEdge: Math.round(contentRight - row.right),
                tiles: row.tiles,
              })),
          };
        })
        """
    )


def test_3d_tool_groups_never_leave_an_empty_grid_cell(live_server_url, browser_page):
    """Guard: every tile row fills its grid, so no group paints an empty bordered cell."""
    page = browser_page
    for viewport in ({"width": 1440, "height": 1000}, {"width": 390, "height": 844}):
        page.set_viewport_size(viewport)
        page.goto(f"{live_server_url}/analysis.html?game=3d")
        page.wait_for_selector("[data-three-d-tool-key]")

        groups = _measure_tool_group_rows(page)
        print(f"tool_group_rows@{viewport['width']}:", json.dumps(groups, ensure_ascii=False))

        assert sum(group["tileCount"] for group in groups) == 7, groups
        for group in groups:
            assert group["tileCount"] > 0, group
            for row in group["rows"]:
                assert row["gapToEdge"] <= TOOL_ROW_EDGE_SLACK, (viewport, group, row)


def _route_3d_toolbox_apis(page, live_server_url, summary_factory):
    page.route(
        f"{live_server_url}/api/workbench/3d/summary**",
        summary_factory,
    )
    page.route(
        f"{live_server_url}/api/plans",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        ),
    )
    page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
    )


def test_3d_tool_deep_link_legacy_mode_and_browser_back(
    live_server_url, browser_page
):
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    page.get_by_role("button", name="走势图").click()
    page.wait_for_url("**view=data&window=30&tool=trend")
    page.go_back()
    assert page.locator("#threeDToolHome").is_visible()
    assert page.locator("#threeDToolWorkspace").is_hidden()

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=omission&window=60")
    page.wait_for_selector('[data-three-d-tool-panel="omission"]:not([hidden])')
    assert page.locator('[data-three-d-window="60"]').get_attribute("aria-pressed") == "true"

    page.goto(f"{live_server_url}/analysis.html?game=3d&mode=pro&window=120")
    page.wait_for_url("**/analysis.html?game=3d&view=data&window=120&tool=frequency")
    assert page.locator('[data-three-d-tool-panel="frequency"]').is_visible()


def test_browser_back_restores_3d_toolbox_after_switching_games(
    live_server_url, browser_page
):
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(
        f"{live_server_url}/api/analysis/ssq**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_analysis_payload("ssq"), ensure_ascii=False),
        ),
    )

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    page.get_by_role("button", name="遗漏统计").click()
    page.wait_for_url("**view=data&window=30&tool=omission")

    page.locator('button[data-game="ssq"]').click()
    page.wait_for_url("**game=ssq&view=data&window=30")
    assert page.locator("#analysisWorkbench").is_visible()
    assert page.locator("#threeDToolbox").is_hidden()

    page.go_back()
    page.wait_for_url("**/analysis.html?game=3d&view=data&window=30")
    assert page.locator("#threeDToolbox").is_visible()
    assert page.locator("#threeDToolHome").is_visible()
    assert page.locator("#analysisWorkbench").is_hidden()


_ICON_CONTRAST_SCRIPT = """
(selector) => {
  const luminance = (rgb) => {
    const channels = rgb.map((value) => {
      const channel = value / 255;
      return channel <= 0.03928
        ? channel / 12.92
        : Math.pow((channel + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  };
  const parse = (color) => {
    const match = color.match(/rgba?\\(([^)]+)\\)/);
    if (!match) return null;
    const parts = match[1].split(",").map((part) => Number(part.trim()));
    if (parts.length > 3 && parts[3] === 0) return null;
    return parts.slice(0, 3);
  };
  return Array.from(document.querySelectorAll(selector)).map((node) => {
    const style = getComputedStyle(node);
    const paint = parse(style.backgroundColor);
    // The icon is painted by the element itself (a mask of the official Lucide file), so its
    // own paint color decides whether a user sees anything. Contrast is measured against the
    // darkest backdrop the black-gold theme can put behind it.
    const contrast = paint
      ? (luminance(paint) + 0.05) / 0.05
      : 1;
    return {
      tag: node.tagName.toLowerCase(),
      maskImage: style.maskImage || style.webkitMaskImage || "none",
      backgroundColor: style.backgroundColor,
      contrastOnBlack: Number(contrast.toFixed(2)),
      width: Math.round(node.getBoundingClientRect().width),
    };
  });
}
"""


_BACKGROUND_LUMINANCE_SCRIPT = """
(dataUrl) => new Promise((resolve) => {
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    // The backdrop is whatever colour the element is mostly painted in: the panel, the
    // gradient, the table row. Text is a minority of the pixels, so the mode is the ground.
    const counts = new Map();
    for (let i = 0; i < pixels.length; i += 4) {
      const key = `${pixels[i] >> 3},${pixels[i + 1] >> 3},${pixels[i + 2] >> 3}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    let mode = "0,0,0";
    let best = -1;
    for (const [key, count] of counts) {
      if (count > best) {
        best = count;
        mode = key;
      }
    }
    resolve(mode.split(",").map((value) => Number(value) * 8));
  };
  image.src = dataUrl;
})
"""


def _relative_luminance(rgb):
    def channel(value):
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(component) for component in rgb[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(page, selector):
    """WCAG contrast of an element's text: computed colour against its painted backdrop."""
    style = page.evaluate(
        """
        (selector) => {
          const node = document.querySelector(selector);
          const computed = getComputedStyle(node);
          return {color: computed.color, fontSize: computed.fontSize, fontWeight: computed.fontWeight};
        }
        """,
        selector,
    )
    shot = page.locator(selector).first.screenshot()
    data_url = "data:image/png;base64," + base64.b64encode(shot).decode()
    background = page.evaluate(_BACKGROUND_LUMINANCE_SCRIPT, data_url)
    inner = style["color"][style["color"].index("(") + 1 : style["color"].index(")")]
    foreground = [float(part) for part in inner.replace("/", ",").split(",")[:3]]
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    size = float(style["fontSize"].removesuffix("px"))
    weight = int(style["fontWeight"])
    is_large = size >= 24 or (size >= 18.66 and weight >= 700)
    return {
        "selector": selector,
        "color": style["color"],
        "font_size": style["fontSize"],
        "ratio": round((lighter + 0.05) / (darker + 0.05), 2),
        "required": 3.0 if is_large else 4.5,
    }


def test_3d_toolbox_secondary_text_meets_wcag_aa_contrast(live_server_url, browser_page):
    """The black-gold theme may not buy its look with unreadable 12px secondary text."""
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(
        f"{live_server_url}/api/3d/trends**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=30), ensure_ascii=False),
        ),
    )

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")

    measured = [
        _contrast_ratio(page, '[data-three-d-tool-key="trend"] strong'),
        _contrast_ratio(page, '[data-three-d-tool-key="trend"] span'),
        _contrast_ratio(page, ".three-d-disclaimer"),
    ]

    _open_3d_tool(page, "trend")
    page.wait_for_selector("#threeDTrendPanel table thead th")
    measured.append(_contrast_ratio(page, "#threeDToolKicker"))
    measured.append(_contrast_ratio(page, "#threeDTrendPanel table thead th"))

    page.go_back()
    _open_3d_tool(page, "number")
    measured.append(_contrast_ratio(page, "#threeDQueryTitle"))
    measured.append(_contrast_ratio(page, "#threeDNumberQueryForm label span"))

    failing = [item for item in measured if item["ratio"] < item["required"]]
    assert failing == [], failing


def test_3d_toolbox_icons_are_painted_in_a_visible_color(live_server_url, browser_page):
    """A Lucide SVG in an <img> paints its currentColor stroke black: invisible on black."""
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(
        f"{live_server_url}/api/3d/trends**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=30), ensure_ascii=False),
        ),
    )

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")

    tiles = page.evaluate(_ICON_CONTRAST_SCRIPT, "[data-three-d-tool-key] .three-d-icon")
    assert len(tiles) == 7, tiles
    for icon in tiles:
        assert icon["width"] > 0, icon
        assert "assets/icons/" in icon["maskImage"], icon
        assert icon["contrastOnBlack"] >= 3, icon

    _open_3d_tool(page, "trend")
    back = page.evaluate(_ICON_CONTRAST_SCRIPT, "#threeDToolBack .three-d-icon")
    assert len(back) == 1, back
    assert "arrow-left.svg" in back[0]["maskImage"], back
    assert back[0]["contrastOnBlack"] >= 3, back


def test_3d_tool_open_moves_focus_into_the_workspace_and_back_restores_the_tile(
    live_server_url, browser_page
):
    """A keyboard user who opens a tool must land in the tool, not back at the page top."""
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(
        f"{live_server_url}/api/3d/trends**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=30), ensure_ascii=False),
        ),
    )

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")

    # Open the tool the way a keyboard user does: focus the tile, press Enter.
    page.locator('[data-three-d-tool-key="trend"]').focus()
    page.keyboard.press("Enter")
    page.wait_for_selector('[data-three-d-tool-panel="trend"]:not([hidden])')

    focus_after_open = page.evaluate(
        """
        () => {
          const active = document.activeElement;
          const workspace = document.querySelector("#threeDToolWorkspace");
          return {
            id: active?.id || "",
            insideWorkspace: Boolean(active && workspace && workspace.contains(active)),
            isWorkspace: active === workspace,
          };
        }
        """
    )
    assert focus_after_open["insideWorkspace"] is True, focus_after_open

    # The first control the user reaches from there is the labelled way back.
    page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement?.id") == "threeDToolBack"
    assert (
        page.locator("#threeDToolBack").get_attribute("aria-label") == "返回工具箱"
    )

    page.keyboard.press("Enter")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    assert page.evaluate(
        "() => document.activeElement?.dataset?.threeDToolKey"
    ) == "trend"


def test_3d_tool_switch_ignores_late_result(live_server_url, browser_page):
    page = browser_page
    windows_requested = []

    # Delay inside the browser: a blocking sleep in a sync route handler would stall
    # the Playwright client itself and never produce a real in-flight request.
    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, init = {}) => {
            const url = new URL(typeof input === "string" ? input : input.url, location.origin);
            const isLateSummary =
              url.pathname === "/api/workbench/3d/summary" &&
              url.searchParams.get("window") === "120";
            if (!isLateSummary) return originalFetch(input, init);
            // The request goes out immediately; only its response lands late.
            return originalFetch(input, init).then(
              (response) => new Promise((resolve) => setTimeout(() => resolve(response), 800)),
            );
          };
        })();
        """
    )

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        windows_requested.append(window)
        payload = _workbench_summary_payload(window=window)
        if window == 120:
            # The superseded request carries a marker that must never reach the DOM.
            payload["position_stats"]["definition"] = "窗口120迟到定义"
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "omission")

    # Switching the window starts a slow summary request for the omission tool.
    page.locator('[data-three-d-window="120"]').click()
    # Leave the tool before that request comes back.
    page.go_back()
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "number")
    page.wait_for_timeout(1500)

    # The superseded request really was sent, and its late payload landed after the switch.
    assert 120 in windows_requested
    assert page.locator('[data-three-d-tool-panel="number"]').is_visible()
    assert page.locator('[data-three-d-tool-panel="omission"]').is_hidden()
    assert page.locator("#threeDToolTitle").inner_text() == "号码查询"
    assert "窗口120迟到定义" not in page.locator("#threeDToolbox").inner_text()
    assert "窗口120迟到定义" not in page.locator("#threeDToolDefinition").inner_html()
    assert (
        page.evaluate("() => window.ThreeDWorkbench.getSummary()?.position_stats?.definition")
        != "窗口120迟到定义"
    )
    assert page.evaluate("() => new URLSearchParams(location.search).get('tool')") == "number"


def test_3d_tool_load_failure_reports_error_in_the_active_panel(
    live_server_url, browser_page
):
    page = browser_page
    calls = []

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        calls.append(window)
        if window == 60:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "summary unavailable"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "heat")
    page.locator('[data-three-d-window="60"]').click()

    status = page.locator('[data-three-d-tool-panel="heat"] [data-tool-status]')
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"heat\"] [data-tool-status]')"
        "?.dataset.state === 'error'"
    )
    assert "加载失败" in status.inner_text()


def test_3d_tool_deep_link_load_failure_reports_error_in_the_active_panel(
    live_server_url, browser_page
):
    """A shared deep link whose first summary fetch fails must say so inside the tool panel."""
    page = browser_page

    def route_summary(route):
        route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": "summary unavailable"}),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=heat&window=60")
    page.wait_for_selector('[data-three-d-tool-panel="heat"]:not([hidden])')

    status = page.locator('[data-three-d-tool-panel="heat"] [data-tool-status]')
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"heat\"] [data-tool-status]')"
        "?.dataset.state === 'error'",
        timeout=5000,
    )
    assert "加载失败" in status.inner_text()


# The disclaimer analysis.html prints in the 最近开奖 panel's status line. A failed load writes
# its error over exactly this node, so recovery has to put this sentence back verbatim. The
# panel states the 不代表未来概率 half itself: with a tool open the toolbox head (which used to
# carry it for this tool) is collapsed, and no tool may rely on another element's disclaimer.
RECENT_TOOL_DISCLAIMER = "数据来自真实历史开奖记录，历史统计不代表未来概率。"


def test_3d_non_stats_tool_restores_its_disclaimer_after_a_failed_load(
    live_server_url, browser_page
):
    """A recovered load must give the panel its disclaimer back, not keep the error text.

    Only the four statistics tools rewrite their own status line once their data is current
    again. 最近开奖 (like 号码查询/号码属性/缩水选号) has no such rewrite, so an error written over
    its mandated disclaimer would otherwise stay on screen above correct data for the rest of
    the session — including after the freshness band's 重试 reloads the data successfully.
    """
    page = browser_page
    calls = []

    def route_summary(route):
        calls.append(route.request.url)
        # Only the deep link's first summary fails; every retry after it succeeds.
        if len(calls) == 1:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "summary unavailable"}),
            )
            return
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=recent")
    page.wait_for_selector('[data-three-d-tool-panel="recent"]:not([hidden])')
    status = page.locator('[data-three-d-tool-panel="recent"] [data-tool-status]')
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"recent\"] [data-tool-status]')"
        "?.dataset.state === 'error'",
        timeout=5000,
    )
    assert "加载失败" in status.inner_text()

    # Recover the way the page itself offers it: the freshness band's 重试.
    page.locator("#threeDFreshness button", has_text="重试").click()
    page.wait_for_function(
        # Only a real draw row carries the <b> with the number; the empty state has none.
        "() => document.querySelectorAll('#threeDRecentDraws li b').length > 0",
        timeout=5000,
    )
    page.wait_for_function(
        "() => !document.querySelector('[data-three-d-tool-panel=\"recent\"] [data-tool-status]')"
        "?.dataset.state",
        timeout=5000,
    )
    assert status.inner_text().strip() == RECENT_TOOL_DISCLAIMER
    assert "加载失败" not in status.inner_text()

    # Re-opening the tool from the home grid must not resurrect the error text either.
    page.go_back()
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "recent")
    page.wait_for_timeout(200)
    assert status.inner_text().strip() == RECENT_TOOL_DISCLAIMER


def test_3d_number_tool_deep_link_round_trips_its_window(live_server_url, browser_page):
    """号码查询 really queries the window the link carried, so the link must keep carrying it."""
    page = browser_page
    query_windows = []

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    def route_query(route):
        body = json.loads(route.request.post_data or "{}")
        query_windows.append(body["window"])
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _number_query_payload(body["number"], window=body["window"]),
                ensure_ascii=False,
            ),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(f"{live_server_url}/api/3d/number-query", route_query)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=number&window=120")
    page.wait_for_selector('[data-three-d-tool-panel="number"]:not([hidden])')
    assert page.evaluate("() => location.search") == "?game=3d&view=data&window=120&tool=number"

    page.locator("#threeDNumberQueryInput").fill("006")
    with page.expect_response(f"{live_server_url}/api/3d/number-query"):
        page.locator("#threeDNumberQueryForm button[type='submit']").click()
    _wait_for_query_result(page, "number", "直选")
    assert query_windows == [120]

    # Reloading the URL the address bar shows must query the same window again, not 30.
    page.reload()
    page.wait_for_selector('[data-three-d-tool-panel="number"]:not([hidden])')
    assert page.evaluate("() => location.search") == "?game=3d&view=data&window=120&tool=number"
    page.locator("#threeDNumberQueryInput").fill("006")
    with page.expect_response(f"{live_server_url}/api/3d/number-query"):
        page.locator("#threeDNumberQueryForm button[type='submit']").click()
    _wait_for_query_result(page, "number", "直选")
    assert query_windows == [120, 120]


# 百位 5 opens the window, disappears for three draws and comes back in the last row: the
# omission the trend cell must show is that drought, never the post-reset 0.
TREND_DRAWS = [
    ("2026178", "2026-07-07", "512"),
    ("2026179", "2026-07-08", "662"),
    ("2026180", "2026-07-09", "006"),
    ("2026181", "2026-07-10", "123"),
    ("2026182", "2026-07-11", "534"),
]
# Per position, the omission each drawn digit of the latest row (534) ended.
TREND_LATEST_HIT_OMISSIONS = [3, 4, 4]


def _trend_payload(window=30):
    """Mirror /api/3d/trends: chronological rows carrying per-position window omissions."""
    omissions = [{str(digit): 0 for digit in range(10)} for _ in range(3)]
    rows = []
    for issue, draw_date, number_text in TREND_DRAWS:
        numbers = [int(char) for char in number_text]
        hit_omissions = {
            str(position): omissions[position][str(hit)] for position, hit in enumerate(numbers)
        }
        for position, hit in enumerate(numbers):
            for digit in range(10):
                key = str(digit)
                omissions[position][key] = 0 if digit == hit else omissions[position][key] + 1
        rows.append(
            {
                "issue": issue,
                "draw_date": draw_date,
                "number_text": number_text,
                "numbers": numbers,
                "hit_omissions": hit_omissions,
                "omissions": {
                    str(position): dict(values) for position, values in enumerate(omissions)
                },
            }
        )
    return {
        "window": window,
        "sample_size": len(rows),
        "latest_issue": TREND_DRAWS[-1][0],
        "latest_date": TREND_DRAWS[-1][1],
        "definition": (
            "每格是这一位当期开出的数字，下面的遗漏是它在这次开出前，已经连续多少期没有开出。"
        ),
        "rows": rows,
        "freshness": {"status": "fresh", "latest_issue": TREND_DRAWS[-1][0], "latest_date": TREND_DRAWS[-1][1]},
        "actions": {"can_save_current": True, "can_filter_current": True, "can_read_history": True},
    }


def _summary_with_window_frequency(window):
    """Frequency values that differ per window, so a stale window shows up in the DOM."""
    payload = _workbench_summary_payload(window=window)
    for position in payload["position_stats"]["positions"].values():
        for key, cell in position["digits"].items():
            cell["frequency"] = window + int(key)
    return payload


def test_3d_trend_tool_renders_semantic_table_with_window_omission(
    live_server_url, browser_page
):
    page = browser_page
    summary_calls = []
    trend_calls = []

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        summary_calls.append(window)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    def route_trends(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        trend_calls.append(window)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(f"{live_server_url}/api/3d/trends**", route_trends)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "trend")

    table = page.locator('[data-three-d-tool-panel="trend"] table.three-d-trend-table')
    page.wait_for_selector('[data-three-d-tool-panel="trend"] table.three-d-trend-table tbody tr')

    # A real semantic table, not a hand-drawn SVG.
    assert table.count() == 1
    assert page.locator('[data-three-d-tool-panel="trend"] svg').count() == 0
    headers = table.locator("thead th").all_inner_texts()
    assert headers == ["期号", "日期", "百位", "十位", "个位"]

    rows = table.locator("tbody tr")
    assert rows.count() == len(TREND_DRAWS)
    assert rows.nth(0).locator("td").nth(0).inner_text() == "2026178"
    assert rows.nth(0).locator("td").nth(1).inner_text() == "2026-07-07"
    # Latest row is 534: every digit carries the omission streak it ended, not the 0 the
    # server wrote into `omissions[position][digit]` when the digit hit.
    latest_cells = rows.nth(len(TREND_DRAWS) - 1).locator("[data-digit-cell]")
    assert latest_cells.count() == 3
    latest_texts = [latest_cells.nth(index).inner_text() for index in range(3)]
    assert [text.split()[0] for text in latest_texts] == ["5", "3", "4"], latest_texts
    assert [f"遗漏 {value}" for value in TREND_LATEST_HIT_OMISSIONS] == [
        f"遗漏 {text.split('遗漏 ')[1]}" for text in latest_texts
    ], latest_texts
    # The very first row of the window opens every streak at 0 — a real 0, not the bug's 0.
    assert "遗漏 0" in rows.nth(0).locator("[data-digit-cell]").nth(0).inner_text()

    definition = page.locator("#threeDToolDefinition").inner_text()
    assert "近30期" in definition
    assert "2026-07-11" in definition
    assert "不代表未来概率" in definition
    assert "推荐" not in page.locator("#threeDToolWorkspace").inner_text()

    # A window switch refetches trends only; the summary is not a trend source.
    page.locator('[data-three-d-window="60"]').click()
    page.wait_for_function("() => new URLSearchParams(location.search).get('window') === '60'")
    page.wait_for_function("() => document.querySelector('#threeDToolDefinition')?.textContent.includes('近60期')")

    assert trend_calls == [30, 60]
    assert summary_calls == [30]


def test_3d_trend_tool_failed_window_refresh_keeps_last_result(
    live_server_url, browser_page
):
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    def route_trends(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        if window == 60:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "trends unavailable"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)
    page.route(f"{live_server_url}/api/3d/trends**", route_trends)

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=trend&window=30")
    page.wait_for_selector('[data-three-d-tool-panel="trend"] table.three-d-trend-table tbody tr')

    page.locator('[data-three-d-window="60"]').click()
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"trend\"] [data-tool-status]')"
        "?.dataset.state === 'error'"
    )

    status = page.locator('[data-three-d-tool-panel="trend"] [data-tool-status]')
    assert "重试" in status.inner_text()
    # The failed refresh must not wipe the table the user was reading.
    assert page.locator('[data-three-d-tool-panel="trend"] tbody tr').count() == len(TREND_DRAWS)

    # The kept rows are the 30-period ones, so every window label must say 30, not the 60
    # the user asked for and never received.
    definition = page.locator("#threeDToolDefinition").inner_text()
    assert "近30期" in definition
    assert "近60期" not in definition
    assert "近60期" not in status.inner_text()


def test_3d_tool_error_survives_summary_retry(
    live_server_url, browser_page
):
    """Renders that are not a tool load may not relabel a stale panel as freshly loaded."""
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    def route_trends(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        if window == 60:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "trends unavailable"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_trend_payload(window=window), ensure_ascii=False),
        )

    def route_plans(route):
        if route.request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "plan": {
                            "id": "plan-3d-error-1",
                            "game_key": "3d",
                            "status": "draft",
                            "source_type": "manual",
                            "title": "手动选号",
                            "target_issue": "2026183",
                            "target_draw_date": "2026-07-12",
                            "entries": [
                                {
                                    "position": 0,
                                    "main_numbers": [1, 2, 3],
                                    "special_numbers": [],
                                    "note": "",
                                }
                            ],
                        }
                    },
                    ensure_ascii=False,
                ),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plans": []}, ensure_ascii=False),
        )

    page.route(f"{live_server_url}/api/workbench/3d/summary**", route_summary)
    page.route(f"{live_server_url}/api/3d/trends**", route_trends)
    page.route(f"{live_server_url}/api/plans", route_plans)
    page.route(
        f"{live_server_url}/api/events",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"accepted":true}'),
    )

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=trend&window=30")
    page.wait_for_selector('[data-three-d-tool-panel="trend"] table.three-d-trend-table tbody tr')

    page.locator('[data-three-d-window="60"]').click()
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"trend\"] [data-tool-status]')"
        "?.dataset.state === 'error'"
    )
    status = page.locator('[data-three-d-tool-panel="trend"] [data-tool-status]')

    # The freshness 重试 button reloads the summary through a non-tool-load path and
    # re-renders everything. That may not erase the trend panel's error while stale rows
    # are on screen; wait for the summary response so the follow-up render has run.
    with page.expect_response(re.compile(r"/api/workbench/3d/summary")):
        page.locator("#threeDFreshness").get_by_role("button", name="重试").click()
    page.wait_for_timeout(800)

    assert status.get_attribute("data-state") == "error"
    assert "加载失败" in status.inner_text()
    assert page.locator('[data-three-d-tool-panel="trend"] tbody tr').count() == len(TREND_DRAWS)

    # Whatever survives on screen still states the window it actually came from.
    definition = page.locator("#threeDToolDefinition").inner_text()
    assert "近30期" in definition
    assert "近60期" not in definition


def test_3d_omission_tool_renders_full_position_digit_matrix(
    live_server_url, browser_page
):
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "omission")
    page.wait_for_selector('[data-three-d-tool-panel="omission"] [data-digit-cell]')

    assert page.locator('[data-three-d-tool-panel="omission"] [data-position]').count() == 3
    assert page.locator('[data-three-d-tool-panel="omission"] [data-digit-cell]').count() == 30
    labels = page.locator('[data-three-d-tool-panel="omission"] [data-position]').all_inner_texts()
    assert "百位" in labels[0] and "十位" in labels[1] and "个位" in labels[2]
    # current_omission of 百位 digit 5 is 5 in the fixture.
    cell = page.locator(
        '[data-three-d-tool-panel="omission"] [data-position="0"] [data-digit-cell][data-digit="5"]'
    )
    assert "现5" in cell.inner_text()

    definition = page.locator("#threeDToolDefinition").inner_text()
    assert "近30期" in definition
    assert "2026-07-11" in definition
    assert "不代表未来概率" in definition
    assert "推荐" not in page.locator("#threeDToolWorkspace").inner_text()


def test_3d_frequency_tool_reads_frequency_for_the_current_window(
    live_server_url, browser_page
):
    page = browser_page
    summary_calls = []

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        summary_calls.append(window)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_summary_with_window_frequency(window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "frequency")
    page.wait_for_selector('[data-three-d-tool-panel="frequency"] [data-digit-cell]')

    assert page.locator('[data-three-d-tool-panel="frequency"] [data-digit-cell]').count() == 30
    first_cell = page.locator(
        '[data-three-d-tool-panel="frequency"] [data-position="0"] [data-digit-cell][data-digit="0"]'
    )
    assert first_cell.inner_text() == "30"

    page.locator('[data-three-d-window="120"]').click()
    page.wait_for_function("() => new URLSearchParams(location.search).get('window') === '120'")
    page.wait_for_function(
        "() => document.querySelector('[data-three-d-tool-panel=\"frequency\"]"
        " [data-position=\"0\"] [data-digit-cell][data-digit=\"0\"]')?.textContent === '120'"
    )

    assert summary_calls == [30, 120]
    assert page.locator("#threeDToolDefinition").inner_text().count("近120期") == 1
    assert "不代表未来概率" in page.locator("#threeDToolDefinition").inner_text()
    assert "推荐" not in page.locator("#threeDToolWorkspace").inner_text()


def test_3d_heat_tool_shows_hot_warm_cold_layers_with_definition(
    live_server_url, browser_page
):
    page = browser_page

    def route_summary(route):
        window = int(re.search(r"window=(\d+)", route.request.url).group(1))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_workbench_summary_payload(window=window), ensure_ascii=False),
        )

    _route_3d_toolbox_apis(page, live_server_url, route_summary)

    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolHome:not([hidden])")
    _open_3d_tool(page, "heat")
    page.wait_for_selector('[data-three-d-tool-panel="heat"] [data-heat-layer]')

    panel = page.locator('[data-three-d-tool-panel="heat"]')
    assert panel.locator("[data-position]").count() == 3
    # Three layers per position: 热 / 温 / 冷.
    assert panel.locator("[data-heat-layer]").count() == 9
    layer_labels = panel.locator('[data-position="0"] [data-heat-layer]').all_inner_texts()
    assert "热" in layer_labels[0]
    assert "温" in layer_labels[1]
    assert "冷" in layer_labels[2]
    # Fixture: digits 0-2 are hot, 3-9 neutral (温), none cold.
    hot_digits = panel.locator('[data-position="0"] [data-heat-layer="热"] [data-digit-cell]')
    assert hot_digits.count() == 3
    assert "遗漏" in hot_digits.nth(0).inner_text()
    assert panel.locator('[data-position="0"] [data-heat-layer="温"] [data-digit-cell]').count() == 7
    assert panel.locator('[data-position="0"] [data-heat-layer="冷"] [data-digit-cell]').count() == 0

    # Window, real sample, latest data date and disclaimer: visible, no click.
    visible_definition = page.locator("#threeDToolDefinition").inner_text()
    assert "近30期" in visible_definition
    assert "2026-07-11" in visible_definition
    assert "不代表未来概率" in visible_definition
    # What 热 / 温 / 冷 actually mean is the mechanics, one click away in 说明.
    definition = _open_tool_definition(page)
    assert "热" in definition and "温" in definition and "冷" in definition
    assert "推荐" not in page.locator("#threeDToolWorkspace").inner_text()
    assert "历史统计不代表未来概率" in panel.locator("[data-tool-status]").inner_text()


def test_3d_toolbox_catalog_and_route_contract(
    live_server_url, browser_page
):
    page = browser_page
    page.goto(f"{live_server_url}/analysis.html?game=ssq")
    page.wait_for_function("Boolean(window.ThreeDToolbox)")
    assert page.evaluate("window.ThreeDToolbox.TOOLS.length") == 7
    assert page.evaluate("window.ThreeDToolbox.normalizeTool('omission')") == "omission"
    assert page.evaluate("window.ThreeDToolbox.normalizeTool('unknown')") == ""
    assert page.evaluate("window.ThreeDToolbox.normalizeWindow('60')") == 60
    assert page.evaluate("window.ThreeDToolbox.normalizeWindow('61')") == 30


def test_product_client_is_available_across_pages_and_reuses_client_header(
    live_server_url, browser_page
):
    probes = []

    def route_probe(route):
        probes.append(
            {
                "path": route.request.url.removeprefix(live_server_url),
                "client": route.request.headers.get("x-lottery-client-id"),
            }
        )
        route.fulfill(status=200, content_type="application/json", body='{"ok":true}')

    browser_page.route(f"{live_server_url}/api/product-client-probe", route_probe)
    ids = []
    for path in ["/", "/analysis.html", "/result.html"]:
        browser_page.goto(f"{live_server_url}{path}")
        browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")
        ids.append(browser_page.evaluate("() => window.LotteryProduct.clientId()"))
        browser_page.evaluate(
            "() => window.LotteryProduct.request('/api/product-client-probe')"
        )

    assert len(set(ids)) == 1
    assert probes == [
        {"path": "/api/product-client-probe", "client": ids[0]},
        {"path": "/api/product-client-probe", "client": ids[0]},
        {"path": "/api/product-client-probe", "client": ids[0]},
    ]


def test_product_client_local_storage_unavailable_keeps_memory_client_id(
    live_server_url, browser_page
):
    browser_page.add_init_script(
        """
        (() => {
          const storage = window.localStorage;
          Object.defineProperty(storage, "getItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "setItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "removeItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
        })();
        """
    )
    _load_product_client_page(browser_page, live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          const first = window.LotteryProduct.clientId();
          const second = window.LotteryProduct.clientId();
          let sentClientId = null;
          window.fetch = (input, init) => {
            sentClientId = new Headers(init.headers).get("X-Lottery-Client-Id");
            return Promise.resolve(new Response("{}", {status: 200}));
          };
          await window.LotteryProduct.request("/api/memory-client");
          return {
            first,
            second,
            sentClientId,
            stable: first === second,
            hasUuidShape: /^[a-z0-9-]{20,80}$/i.test(first),
          };
        }
        """
    )

    assert result["stable"] is True
    assert result["hasUuidShape"] is True
    assert result["sentClientId"] == result["first"]


def test_product_client_request_parses_responses_and_marks_errors(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          localStorage.setItem("lotteryLuck.clientId.v1", "client-request");
          const calls = [];
          window.fetch = (input, init = {}) => {
            const url = new URL(input, window.location.href);
            const headers = Object.fromEntries(new Headers(init.headers).entries());
            calls.push({
              path: url.pathname,
              method: init.method || "GET",
              headers,
              body: init.body || null,
            });
            if (url.pathname === "/api/empty") {
              return Promise.resolve(new Response(null, {status: 204}));
            }
            if (url.pathname === "/api/json") {
              return Promise.resolve(new Response(JSON.stringify({ok: true}), {
                status: 200,
                headers: {"Content-Type": "application/json"},
              }));
            }
            if (url.pathname === "/api/text") {
              return Promise.resolve(new Response("plain text", {
                status: 200,
                headers: {"Content-Type": "text/plain"},
              }));
            }
            return Promise.resolve(new Response(JSON.stringify({
              detail: "invalid plan",
              code: "bad_request",
            }), {
              status: 422,
              headers: {"Content-Type": "application/json"},
            }));
          };

          const empty = await window.LotteryProduct.request("/api/empty");
          const json = await window.LotteryProduct.request("/api/json", {
            method: "POST",
            headers: {
              "X-Custom": "yes",
              "X-Lottery-Client-Id": "caller-should-not-win",
            },
            body: {hello: "world"},
          });
          const text = await window.LotteryProduct.request("/api/text");
          let httpError;
          try {
            await window.LotteryProduct.request("/api/error");
          } catch (error) {
            httpError = {
              message: error.message,
              status: error.status,
              detail: error.detail,
              payload: error.payload,
              network: error.network === true,
            };
          }
          window.fetch = () => Promise.reject(new TypeError("Failed to fetch"));
          let networkError;
          try {
            await window.LotteryProduct.request("/api/network");
          } catch (error) {
            networkError = {
              message: error.message,
              status: error.status || null,
              detail: error.detail || null,
              network: error.network === true,
            };
          }

          return {empty, json, text, httpError, networkError, calls};
        }
        """
    )

    assert result["empty"] == {}
    assert result["json"] == {"ok": True}
    assert result["text"] == {}
    assert result["calls"][0]["headers"]["x-lottery-client-id"] == "client-request"
    assert "content-type" not in result["calls"][0]["headers"]
    assert result["calls"][1]["method"] == "POST"
    assert result["calls"][1]["headers"]["x-custom"] == "yes"
    assert result["calls"][1]["headers"]["x-lottery-client-id"] == "client-request"
    assert result["calls"][1]["headers"]["content-type"] == "application/json"
    assert json.loads(result["calls"][1]["body"]) == {"hello": "world"}
    assert result["httpError"] == {
        "message": "invalid plan",
        "status": 422,
        "detail": "invalid plan",
        "payload": {"detail": "invalid plan", "code": "bad_request"},
        "network": False,
    }
    assert result["networkError"]["network"] is True
    assert result["networkError"]["status"] is None


def test_product_client_track_posts_event_keepalive_and_swallows_failures(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          localStorage.setItem("lotteryLuck.clientId.v1", "client-track");
          const unhandled = [];
          const calls = [];
          window.addEventListener("unhandledrejection", (event) => {
            unhandled.push(String(event.reason && event.reason.message || event.reason));
          });
          navigator.sendBeacon = () => {
            throw new Error("sendBeacon must not be used");
          };
          const properties = {game_key: "3d"};
          window.fetch = (input, init = {}) => {
            calls.push({
              path: new URL(input, window.location.href).pathname,
              method: init.method,
              keepalive: init.keepalive === true,
              headers: Object.fromEntries(new Headers(init.headers).entries()),
              body: JSON.parse(init.body),
            });
            return Promise.resolve(new Response("{}", {status: 200}));
          };
          const ok = await window.LotteryProduct.track("plan_saved", properties);
          window.fetch = () => Promise.reject(new TypeError("offline"));
          const failed = await window.LotteryProduct.track("plan_failed", properties);
          await new Promise((resolve) => setTimeout(resolve, 0));
          return {ok, failed, calls, properties, unhandled};
        }
        """
    )

    assert result["ok"] is True
    assert result["failed"] is False
    assert result["properties"] == {"game_key": "3d"}
    assert result["unhandled"] == []
    assert result["calls"] == [
        {
            "path": "/api/events",
            "method": "POST",
            "keepalive": True,
            "headers": {
                "content-type": "application/json",
                "x-lottery-client-id": "client-track",
            },
            "body": {
                "event_name": "plan_saved",
                "properties": {"game_key": "3d"},
            },
        }
    ]


def test_product_client_plan_methods_use_expected_routes_and_bodies(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)
    payload = _pending_plan_payload("plan-method-create")
    expected_create_payload = _sanitized_pending_plan_payload("plan-method-create")

    result = browser_page.evaluate(
        """
        async (payload) => {
          const calls = [];
          window.fetch = (input, init = {}) => {
            const url = new URL(input, window.location.href);
            calls.push({
              path: url.pathname,
              method: init.method || "GET",
              body: init.body ? JSON.parse(init.body) : null,
            });
            return Promise.resolve(new Response(JSON.stringify({ok: true}), {
              status: init.method === "POST" && url.pathname === "/api/plans" ? 201 : 200,
              headers: {"Content-Type": "application/json"},
            }));
          };
          await window.LotteryProduct.createPlan(payload);
          await window.LotteryProduct.listPlans();
          await window.LotteryProduct.getPlan("plan id/one");
          await window.LotteryProduct.updatePlan("plan id/one", {title: "patched"});
          await window.LotteryProduct.deletePlan("plan id/one");
          await window.LotteryProduct.reviewPlan("plan id/one");
          await window.LotteryProduct.carryForward("plan id/one", "carry-1");
          return calls;
        }
        """,
        payload,
    )

    assert result == [
        {"path": "/api/plans", "method": "POST", "body": expected_create_payload},
        {"path": "/api/plans", "method": "GET", "body": None},
        {"path": "/api/plans/plan%20id%2Fone", "method": "GET", "body": None},
        {
            "path": "/api/plans/plan%20id%2Fone",
            "method": "PATCH",
            "body": {"title": "patched"},
        },
        {"path": "/api/plans/plan%20id%2Fone", "method": "DELETE", "body": None},
        {"path": "/api/plans/plan%20id%2Fone/review", "method": "POST", "body": None},
        {
            "path": "/api/plans/plan%20id%2Fone/carry-forward",
            "method": "POST",
            "body": {"request_id": "carry-1"},
        },
    ]


def test_product_client_create_plan_posts_canonical_payload_before_queueing_retry(
    live_server_url, browser_page
):
    from lottery_luck.plan_routes import PlanCreateRequest

    _load_product_client_page(browser_page, live_server_url)
    payload = _pending_plan_payload("canonical-retry")
    payload["source_type"] = "filter"
    payload["title"] = "用户自由标题 secret@example.com"
    payload["entries"][0]["note"] = "用户自由备注 13800000000"
    payload["condition_snapshot"]["conditions"] = {
        "sum_min": 4,
        "group_type": "组三",
        "email": "secret@example.com",
    }
    expected = _sanitized_pending_plan_payload("canonical-retry")
    expected["source_type"] = "filter"
    expected["title"] = SAFE_PLAN_TITLES["filter"]

    posts = []
    saved_payload = {}

    def route_plan_create(route):
        nonlocal saved_payload
        body = json.loads(route.request.post_data or "{}")
        PlanCreateRequest.model_validate(body)
        posts.append(body)
        if len(posts) == 1:
            saved_payload = json.loads(json.dumps(body, ensure_ascii=False))
            route.abort("failed")
            return
        if body == saved_payload:
            route.fulfill(
                status=201,
                content_type="application/json",
                body=json.dumps(
                    {"plan": {"id": "plan-existing", "request_id": body["request_id"]}},
                    ensure_ascii=False,
                ),
            )
            return
        route.fulfill(
            status=409,
            content_type="application/json",
            body=json.dumps({"detail": "request id conflicts with an existing plan"}),
        )

    browser_page.route(f"{live_server_url}/api/plans", route_plan_create)

    result = browser_page.evaluate(
        """
        async (payload) => {
          localStorage.removeItem("lotteryLuck.pendingPlans.v1");
          const before = JSON.stringify(payload);
          let errorState;
          try {
            await window.LotteryProduct.createPlan(payload);
          } catch (error) {
            errorState = {
              network: error.network === true,
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
            };
          }
          payload.title = "caller mutation after failed response";
          payload.entries[0].note = "caller mutation after failed response";
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            errorState,
            before,
            afterCreateBeforeCallerMutation: JSON.stringify({
              ...payload,
              title: "用户自由标题 secret@example.com",
              entries: [{...payload.entries[0], note: "用户自由备注 13800000000"}],
            }),
            flushResult,
            pending: window.LotteryProduct.pendingPlans(),
          };
        }
        """,
        payload,
    )

    assert result["errorState"] == {
        "network": True,
        "pending": True,
        "persistedLocally": True,
    }
    assert posts == [expected, expected]
    assert result["flushResult"]["flushed"] == 1
    assert result["pending"] == []
    assert json.loads(result["before"])["title"] == "用户自由标题 secret@example.com"


def test_product_client_network_create_queues_sanitized_plan_once(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          localStorage.removeItem("lotteryLuck.pendingPlans.v1");
          const payload = {
            game_key: "3d",
            target_issue: "2026156",
            target_draw_date: "2026-06-16",
            source_type: "manual",
            request_id: "offline-create-1",
            title: "张三的自由标题 13800000000",
            name: "隐私姓名",
            birth_date: "1990-01-01",
            birthYear: "1990",
            birth_hour: "午",
            birthHour: "子",
            birth_place: "杭州",
            birth_city: "苏州",
            place: "宁波",
            city: "北京",
            email: "secret@example.com",
            phone: "13800000000",
            current_city: "上海",
            explanation: "drop top explanation",
            entries: [{
              position: 0,
              main_numbers: [1, 2, 3],
              special_numbers: [],
              note: "我的备注 secret@example.com",
              name: "entry pii",
              extra: "drop entry extra",
            }],
            condition_snapshot: {
              mode: "pro",
              analysis_window: 60,
              conditions: {
                sum_min: 4,
                sum_max: 22,
                span_min: 1,
                span_max: 8,
                types: ["组三", "组六"],
                odd_counts: [1, 3],
                big_counts: [0, 2],
                position_include: {"0": [1, 2], "2": [9]},
                position_exclude: {"1": [0]},
                name: "nested pii",
                birth_date: "1988-01-01",
                birthYear: "1988",
                birth_city: "嘉兴",
                place: "绍兴",
                city: "深圳",
                email: "nested@example.com",
                phone: "13900000000",
                birth_hour: "卯",
                random_free_text: "自由文本",
              },
              metrics: {
                sum: 6,
                sum_tail: 6,
                span: 2,
                group_type: "组三",
                odd_even: "2:1",
                big_small: "1:2",
                mod3: "1:1:1",
                prime_composite: "2:1",
                repeat_count: 1,
                consecutive_pairs: [[1, 2]],
                adjacent_pairs: [[0, 1]],
                current_city: "上海",
                birthHour: "酉",
                phone: "13700000000",
              },
              latest_data_issue: "2026155",
              latest_data_date: "2026-06-15",
              birth_place: "杭州",
              explanation: "drop snapshot explanation",
            },
          };
          window.fetch = () => Promise.reject(new TypeError("Failed to fetch"));
          let firstError;
          try {
            await window.LotteryProduct.createPlan(payload);
          } catch (error) {
            firstError = {
              message: error.message,
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
              network: error.network === true,
            };
          }
          payload.entries[0].main_numbers.push(9);
          payload.title = "mutated after queue";
          payload.entries[0].note = "mutated note";
          const retryPayload = {
            ...payload,
            title: "retry title",
            entries: [{
              ...payload.entries[0],
              main_numbers: [1, 2, 3],
              note: "retry note",
            }],
          };
          let secondError;
          try {
            await window.LotteryProduct.createPlan(retryPayload);
          } catch (error) {
            secondError = {
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
            };
          }
          const pending = window.LotteryProduct.pendingPlans();
          pending[0].entries[0].main_numbers.push(99);
          const afterCopyMutation = window.LotteryProduct.pendingPlans();
          const storedRaw = localStorage.getItem("lotteryLuck.pendingPlans.v1");
          return {
            firstError,
            secondError,
            pending: afterCopyMutation,
            storedRaw,
          };
        }
        """
    )

    assert result["firstError"] == {
        "message": "计划已进入待同步队列，网络恢复后会再次保存。",
        "pending": True,
        "persistedLocally": True,
        "network": True,
    }
    assert result["secondError"] == {"pending": True, "persistedLocally": True}
    assert len(result["pending"]) == 1
    queued = result["pending"][0]
    assert queued["request_id"] == "offline-create-1"
    assert queued["title"] == "手动选号"
    assert queued["entries"][0]["main_numbers"] == [1, 2, 3]
    assert queued["entries"][0]["note"] == ""
    assert queued["condition_snapshot"]["conditions"] == {
        "sum_min": 4,
        "sum_max": 22,
        "span_min": 1,
        "span_max": 8,
        "types": ["组三", "组六"],
        "odd_counts": [1, 3],
        "big_counts": [0, 2],
        "position_include": {"0": [1, 2], "2": [9]},
        "position_exclude": {"1": [0]},
    }
    assert queued["condition_snapshot"]["metrics"] == {
        "sum": 6,
        "sum_tail": 6,
        "span": 2,
        "group_type": "组三",
        "odd_even": "2:1",
        "big_small": "1:2",
        "mod3": "1:1:1",
        "prime_composite": "2:1",
        "repeat_count": 1,
        "consecutive_pairs": [[1, 2]],
        "adjacent_pairs": [[0, 1]],
    }
    forbidden = [
        "隐私姓名",
        "1990-01-01",
        "1988-01-01",
        "13800000000",
        "13900000000",
        "13700000000",
        "secret@example.com",
        "nested@example.com",
        "张三的自由标题",
        "我的备注",
        "自由文本",
        "午",
        "子",
        "卯",
        "酉",
        "杭州",
        "上海",
        "苏州",
        "嘉兴",
        "宁波",
        "北京",
        "深圳",
        "birth_date",
        "birthYear",
        "birth_hour",
        "birthHour",
        "birth_place",
        "birth_city",
        "current_city",
        "explanation",
        "entry pii",
        "drop entry extra",
    ]
    assert all(value not in result["storedRaw"] for value in forbidden)


def test_product_client_resanitizes_restored_queue_and_flushes_clean_payload(
    live_server_url, browser_page
):
    dirty = _pending_plan_payload("  restored-dirty  ")
    dirty["title"] = "王五的方案 secret@example.com"
    dirty["name"] = "王五"
    dirty["email"] = "secret@example.com"
    dirty["phone"] = "13800000000"
    dirty["entries"][0]["note"] = "联系王五 13800000000"
    dirty["entries"][0]["extra"] = "entry extra secret"
    dirty["condition_snapshot"]["conditions"] = {
        "sum_min": 4,
        "group_type": "组三",
        "birthYear": "1988",
        "deep": {"email": "nested@example.com"},
    }
    dirty["condition_snapshot"]["metrics"] = {
        "sum": 6,
        "span": 2,
        "profile": {"phone": "13900000000"},
        "city": "上海",
    }
    duplicate = {**dirty, "title": "duplicate should vanish"}
    expected = _sanitized_pending_plan_payload("restored-dirty")

    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        ([dirty, duplicate]) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([
            dirty,
            duplicate,
          ]));
        }
        """,
        [dirty, duplicate],
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const restoredRaw = localStorage.getItem("lotteryLuck.pendingPlans.v1");
          const pendingBefore = window.LotteryProduct.pendingPlans();
          pendingBefore[0].title = "mutated copy";
          const pendingAfterCopyMutation = window.LotteryProduct.pendingPlans();
          const posts = [];
          window.fetch = (input, init = {}) => {
            posts.push(JSON.parse(init.body));
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            restoredRaw,
            pendingAfterCopyMutation,
            posts,
            flushResult,
            storedAfterFlush: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert result["pendingAfterCopyMutation"] == [expected]
    assert result["posts"] == [expected]
    assert result["flushResult"]["flushed"] == 1
    assert result["storedAfterFlush"] == "[]"
    forbidden = [
        "王五",
        "secret@example.com",
        "13800000000",
        "13900000000",
        "联系王五",
        "entry extra secret",
        "birthYear",
        "nested@example.com",
        "上海",
        "duplicate should vanish",
    ]
    assert all(value not in result["restoredRaw"] for value in forbidden)


def test_product_client_create_plan_http_errors_and_missing_request_id_do_not_queue(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)
    payload = _pending_plan_payload("http-error-plan")

    result = browser_page.evaluate(
        """
        async (payload) => {
          localStorage.removeItem("lotteryLuck.pendingPlans.v1");
          window.fetch = () => Promise.resolve(new Response(JSON.stringify({
            detail: "plan service is unavailable",
          }), {
            status: 503,
            headers: {"Content-Type": "application/json"},
          }));
          let httpError;
          try {
            await window.LotteryProduct.createPlan(payload);
          } catch (error) {
            httpError = {
              status: error.status,
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
            };
          }
          window.fetch = () => Promise.reject(new TypeError("offline"));
          let missingRequestIdError;
          try {
            await window.LotteryProduct.createPlan({...payload, request_id: ""});
          } catch (error) {
            missingRequestIdError = {
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
            };
          }
          return {
            httpError,
            missingRequestIdError,
            pending: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """,
        payload,
    )

    assert result["httpError"] == {
        "status": 503,
        "pending": False,
        "persistedLocally": False,
    }
    assert result["missingRequestIdError"] == {
        "pending": False,
        "persistedLocally": False,
    }
    assert result["pending"] == []
    assert result["storedRaw"] in (None, "[]")


def test_product_client_rejects_invalid_plan_payloads_before_fetch_or_queue(
    live_server_url, browser_page
):
    _load_product_client_page(browser_page, live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          localStorage.removeItem("lotteryLuck.pendingPlans.v1");
          const valid = {
            game_key: "3d",
            target_issue: "2026156",
            target_draw_date: "2026-06-16",
            source_type: "manual",
            request_id: "valid-seed",
            title: "caller title",
            entries: [{
              position: 0,
              main_numbers: [1, 2, 3],
              special_numbers: [],
              note: "caller note",
            }],
            condition_snapshot: {
              mode: "pro",
              analysis_window: 60,
              conditions: {sum_min: 4},
              metrics: {sum: 6, span: 2},
              latest_data_issue: "2026155",
              latest_data_date: "2026-06-15",
            },
          };
          const copy = (value) => JSON.parse(JSON.stringify(value));
          const manyEntries = Array.from({length: 51}, (_, index) => ({
            position: index,
            main_numbers: [1, 2, 3],
            special_numbers: [],
          }));
          const invalids = [
            null,
            {},
            {...copy(valid), game_key: "ssq"},
            {...copy(valid), target_issue: ""},
            {...copy(valid), target_issue: "x".repeat(33)},
            {...copy(valid), target_draw_date: "2026-02-31"},
            {...copy(valid), source_type: "home"},
            {...copy(valid), request_id: ""},
            {...copy(valid), request_id: "x".repeat(97)},
            {...copy(valid), entries: undefined},
            {...copy(valid), entries: []},
            {...copy(valid), entries: manyEntries},
            {...copy(valid), entries: [{main_numbers: [1, 2], special_numbers: []}]},
            {...copy(valid), entries: [{main_numbers: [1, 2, 10], special_numbers: []}]},
            {...copy(valid), entries: [{main_numbers: ["1", 2, 3], special_numbers: []}]},
            {...copy(valid), entries: [{main_numbers: [1, 2, 3], special_numbers: [4]}]},
            {...copy(valid), entries: [
              {position: 0, main_numbers: [1, 2, 3], special_numbers: []},
              {position: 0, main_numbers: [4, 5, 6], special_numbers: []},
            ]},
            {...copy(valid), entries: [{position: 50, main_numbers: [1, 2, 3], special_numbers: []}]},
            {...copy(valid), entries: [{position: 1.5, main_numbers: [1, 2, 3], special_numbers: []}]},
            {...copy(valid), condition_snapshot: undefined},
            {...copy(valid), condition_snapshot: {...copy(valid).condition_snapshot, mode: "expert"}},
            {...copy(valid), condition_snapshot: {...copy(valid).condition_snapshot, analysis_window: 90}},
            {...copy(valid), condition_snapshot: {...copy(valid).condition_snapshot, latest_data_issue: ""}},
            {...copy(valid), condition_snapshot: {...copy(valid).condition_snapshot, latest_data_date: "2026-02-31"}},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              conditions: {sum_min: -1},
            }},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              conditions: {types: ["bad"]},
            }},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              conditions: {position_include: {"3": [1]}},
            }},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              metrics: {sum: Infinity},
            }},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              metrics: {group_type: "bad"},
            }},
            {...copy(valid), condition_snapshot: {
              ...copy(valid).condition_snapshot,
              metrics: {consecutive_pairs: [["x", 1]]},
            }},
          ];
          let fetchCount = 0;
          window.fetch = () => {
            fetchCount += 1;
            return Promise.resolve(new Response("{}", {status: 200}));
          };
          const results = [];
          for (const payload of invalids) {
            try {
              await window.LotteryProduct.createPlan(payload);
              results.push({ok: true});
            } catch (error) {
              results.push({
                ok: false,
                status: error.status || null,
                pending: error.pending === true,
                detail: error.detail || error.message,
              });
            }
          }
          return {
            fetchCount,
            results,
            pending: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert result["fetchCount"] == 0
    assert len(result["results"]) >= 20
    assert all(item == {
        "ok": False,
        "status": 422,
        "pending": False,
        "detail": "invalid plan",
    } for item in result["results"])
    assert result["pending"] == []
    assert result["storedRaw"] in (None, "[]")


def test_product_client_drops_invalid_restored_items_without_posting(
    live_server_url, browser_page
):
    valid = _pending_plan_payload("restore-valid")
    invalid = _pending_plan_payload("restore-invalid")
    invalid["entries"][0]["main_numbers"] = [1, 2]
    expected = _sanitized_pending_plan_payload("restore-valid")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        ([invalid, valid]) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([invalid, valid]));
        }
        """,
        [invalid, valid],
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const restored = window.LotteryProduct.pendingPlans();
          const posts = [];
          window.fetch = (input, init = {}) => {
            posts.push(JSON.parse(init.body));
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            restored,
            posts,
            flushResult,
            pending: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert result["restored"] == [expected]
    assert result["posts"] == [expected]
    assert result["flushResult"]["flushed"] == 1
    assert result["pending"] == []
    assert result["storedRaw"] == "[]"


def test_product_client_pending_queue_uses_memory_when_storage_unavailable(
    live_server_url, browser_page
):
    browser_page.add_init_script(
        """
        (() => {
          const storage = window.localStorage;
          Object.defineProperty(storage, "getItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "setItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "removeItem", {
            value: () => { throw new Error("local storage disabled"); },
            configurable: true,
          });
        })();
        """
    )
    _load_product_client_page(browser_page, live_server_url)
    payload = _pending_plan_payload("memory-only")

    result = browser_page.evaluate(
        """
        async (payload) => {
          window.fetch = () => Promise.reject(new TypeError("offline"));
          let errorState;
          try {
            await window.LotteryProduct.createPlan(payload);
          } catch (error) {
            errorState = {
              message: error.message,
              pending: error.pending === true,
              persistedLocally: error.persistedLocally === true,
              network: error.network === true,
            };
          }
          return {
            errorState,
            pending: window.LotteryProduct.pendingPlans(),
          };
        }
        """,
        payload,
    )

    assert result["errorState"] == {
        "message": "计划尚未保存，请保持本页打开并稍后重试。",
        "pending": True,
        "persistedLocally": False,
        "network": True,
    }
    assert len(result["pending"]) == 1
    assert result["pending"][0]["request_id"] == "memory-only"


def test_product_client_flush_pending_plans_is_fifo_and_single_flight(
    live_server_url, browser_page
):
    payload = _pending_plan_payload("flush-once")
    expected_payload = _sanitized_pending_plan_payload("flush-once")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
        }
        """,
        payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const posts = [];
          let resolveFetch;
          window.fetch = (input, init = {}) => {
            posts.push({
              path: new URL(input, window.location.href).pathname,
              body: JSON.parse(init.body),
            });
            return new Promise((resolve) => {
              resolveFetch = () => resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
                status: 201,
                headers: {"Content-Type": "application/json"},
              }));
            });
          };
          const first = window.LotteryProduct.flushPendingPlans();
          const second = window.LotteryProduct.flushPendingPlans();
          const samePromise = first === second;
          await new Promise((resolve) => setTimeout(resolve, 0));
          const callsBeforeResolve = posts.length;
          resolveFetch();
          const firstResult = await first;
          const secondResult = await second;
          return {
            samePromise,
            callsBeforeResolve,
            posts,
            firstResult,
            secondResult,
            pending: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert result["samePromise"] is True
    assert result["callsBeforeResolve"] == 1
    assert result["posts"] == [{"path": "/api/plans", "body": expected_payload}]
    assert result["firstResult"]["flushed"] == 1
    assert result["secondResult"] == result["firstResult"]
    assert result["pending"] == []
    assert result["storedRaw"] == "[]"


def test_product_client_flush_dispatches_plan_sync_events_and_results_without_pii(
    live_server_url,
    browser_page,
):
    saved = _pending_plan_payload("sync-saved")
    blocked = _pending_plan_payload("sync-blocked")
    retryable = _pending_plan_payload("sync-retryable")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        ([saved, blocked, retryable]) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([
            saved,
            blocked,
            retryable,
          ]));
        }
        """,
        [saved, blocked, retryable],
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const events = [];
          const posts = [];
          window.addEventListener("lotteryproduct:plansync", (event) => {
            events.push(event.detail);
          });
          window.fetch = (input, init = {}) => {
            const body = JSON.parse(init.body);
            posts.push(body.request_id);
            if (body.request_id === "sync-saved") {
              return Promise.resolve(new Response(JSON.stringify({
                plan: {
                  id: "saved-plan-id",
                  title: "隐私姓名 should not leak",
                  request_id: body.request_id,
                },
              }), {
                status: 201,
                headers: {"Content-Type": "application/json"},
              }));
            }
            if (body.request_id === "sync-blocked") {
              return Promise.resolve(new Response(JSON.stringify({
                detail: "invalid plan for 隐私姓名",
              }), {
                status: 422,
                headers: {"Content-Type": "application/json"},
              }));
            }
            return Promise.resolve(new Response(JSON.stringify({
              detail: "server failed for secret@example.com",
            }), {
              status: 503,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            posts,
            events,
            flushResult,
            pending: window.LotteryProduct.pendingPlans(),
            serializedEvents: JSON.stringify(events),
            serializedResults: JSON.stringify(flushResult.results),
          };
        }
        """
    )

    expected_results = [
        {
            "request_id": "sync-saved",
            "status": "saved",
            "plan": {"id": "saved-plan-id"},
            "http_status": 201,
        },
        {
            "request_id": "sync-blocked",
            "status": "blocked",
            "http_status": 422,
        },
        {
            "request_id": "sync-retryable",
            "status": "retryable",
            "http_status": 503,
        },
    ]
    assert result["posts"] == ["sync-saved", "sync-blocked", "sync-retryable"]
    assert result["events"] == expected_results
    assert result["flushResult"]["results"] == expected_results
    assert result["flushResult"]["flushed"] == 1
    assert result["flushResult"]["remaining"] == 2
    assert result["pending"][0]["request_id"] == "sync-blocked"
    assert result["pending"][0]["status"] == "blocked"
    assert result["pending"][1]["request_id"] == "sync-retryable"
    assert result["pending"][1]["status"] == "retryable"
    for forbidden in ["隐私姓名", "secret@example.com", "title", "detail"]:
        assert forbidden not in result["serializedEvents"]
        assert forbidden not in result["serializedResults"]


def test_product_client_online_flush_dispatches_plan_sync_event(
    live_server_url,
    browser_page,
):
    payload = _pending_plan_payload("online-sync")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
        }
        """,
        payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const events = [];
          window.addEventListener("lotteryproduct:plansync", (event) => {
            events.push(event.detail);
          });
          window.fetch = (input, init = {}) => Promise.resolve(new Response(JSON.stringify({
            plan: {id: "online-plan-id", request_id: JSON.parse(init.body).request_id},
          }), {
            status: 201,
            headers: {"Content-Type": "application/json"},
          }));
          window.dispatchEvent(new Event("online"));
          await new Promise((resolve, reject) => {
            const started = performance.now();
            const tick = () => {
              if (events.length) {
                resolve();
                return;
              }
              if (performance.now() - started > 3000) {
                reject(new Error("sync event timed out"));
                return;
              }
              setTimeout(tick, 25);
            };
            tick();
          });
          return {
            events,
            pending: window.LotteryProduct.pendingPlans(),
          };
        }
        """
    )

    assert result["events"] == [
        {
            "request_id": "online-sync",
            "status": "saved",
            "plan": {"id": "online-plan-id"},
            "http_status": 201,
        }
    ]
    assert result["pending"] == []


def test_product_client_flush_deduplicates_restored_request_ids(
    live_server_url, browser_page
):
    payload = _pending_plan_payload("flush-duplicate")
    duplicate = {**payload, "title": "duplicate should not post"}
    expected_payload = _sanitized_pending_plan_payload("flush-duplicate")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        ([payload, duplicate]) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([
            payload,
            duplicate,
          ]));
        }
        """,
        [payload, duplicate],
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const posts = [];
          window.fetch = (input, init = {}) => {
            posts.push(JSON.parse(init.body));
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            flushResult,
            posts,
            pending: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert result["posts"] == [expected_payload]
    assert result["flushResult"]["flushed"] == 1
    assert result["pending"] == []
    assert result["storedRaw"] == "[]"


def test_product_client_flush_blocks_4xx_plan_but_continues_retryable_items(
    live_server_url, browser_page
):
    first = _pending_plan_payload("flush-fail-1")
    second = _pending_plan_payload("flush-fail-2")
    expected_second = _sanitized_pending_plan_payload("flush-fail-2")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        ([first, second]) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([first, second]));
        }
        """,
        [first, second],
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const posts = [];
          window.fetch = (input, init = {}) => {
            const body = JSON.parse(init.body);
            posts.push(body);
            if (body.request_id === "flush-fail-2") {
              return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved-2"}}), {
                status: 201,
                headers: {"Content-Type": "application/json"},
              }));
            }
            return Promise.resolve(new Response(JSON.stringify({
              detail: "invalid plan for 隐私姓名 secret@example.com",
            }), {
              status: 422,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          window.dispatchEvent(new Event("online"));
          return {
            posts,
            flushResult,
            pending: window.LotteryProduct.pendingPlans(),
            removed: window.LotteryProduct.removePendingPlan(" flush-fail-1 "),
            afterRemove: window.LotteryProduct.pendingPlans(),
            storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
          };
        }
        """
    )

    assert [post["request_id"] for post in result["posts"]] == [
        "flush-fail-1",
        "flush-fail-2",
    ]
    assert result["posts"][1] == expected_second
    assert "blocked" not in result["posts"][0]
    assert "last_error" not in result["posts"][0]
    assert result["flushResult"]["flushed"] == 1
    assert result["flushResult"]["remaining"] == 1
    assert result["flushResult"]["stopped"] is False
    assert result["pending"][0]["request_id"] == "flush-fail-1"
    assert result["pending"][0]["blocked"] is True
    assert result["pending"][0]["status"] == "blocked"
    assert result["pending"][0]["last_error"] == "HTTP 422"
    assert result["removed"] is True
    assert result["afterRemove"] == []
    assert "隐私姓名" not in result["storedRaw"]
    assert "secret@example.com" not in result["storedRaw"]


def test_product_client_retry_pending_plan_clears_blocked_status_for_next_flush(
    live_server_url, browser_page
):
    payload = _sanitized_pending_plan_payload("retry-blocked")
    blocked_payload = {
        **payload,
        "blocked": True,
        "status": "blocked",
        "last_error": "HTTP 422",
    }
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
        }
        """,
        blocked_payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    result = browser_page.evaluate(
        """
        async () => {
          const posts = [];
          window.fetch = (input, init = {}) => {
            posts.push(JSON.parse(init.body));
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          const retryResult = window.LotteryProduct.retryPendingPlan(" retry-blocked ");
          const afterRetry = window.LotteryProduct.pendingPlans();
          const flushResult = await window.LotteryProduct.flushPendingPlans();
          return {
            retryResult,
            afterRetry,
            flushResult,
            posts,
            pending: window.LotteryProduct.pendingPlans(),
          };
        }
        """
    )

    assert result["retryResult"] is True
    assert result["afterRetry"][0]["request_id"] == "retry-blocked"
    assert result["afterRetry"][0]["blocked"] is False
    assert result["afterRetry"][0]["status"] == "retryable"
    assert "last_error" not in result["afterRetry"][0]
    assert result["posts"] == [payload]
    assert result["flushResult"]["flushed"] == 1
    assert result["pending"] == []


def test_product_client_flush_retries_5xx_on_next_online(
    live_server_url, browser_page
):
    payload = _pending_plan_payload("flush-retry-5xx")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
        }
        """,
        payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    browser_page.evaluate(
        """
        () => {
          window.__retryPosts = [];
          window.__retryStatuses = [503, 201];
          window.fetch = (input, init = {}) => {
            window.__retryPosts.push(JSON.parse(init.body).request_id);
            const status = window.__retryStatuses.shift();
            return Promise.resolve(new Response(JSON.stringify(
              status >= 500
                ? {detail: "temporary database failure secret@example.com"}
                : {plan: {id: "saved"}}
            ), {
              status,
              headers: {"Content-Type": "application/json"},
            }));
          };
          window.dispatchEvent(new Event("online"));
        }
        """
    )
    browser_page.wait_for_function(
        """
        () => {
          const pending = window.LotteryProduct.pendingPlans();
          return window.__retryPosts.length === 1
            && pending.length === 1
            && pending[0].status === "retryable";
        }
        """
    )

    first_state = browser_page.evaluate(
        """
        () => ({
          posts: window.__retryPosts,
          pending: window.LotteryProduct.pendingPlans(),
          storedRaw: localStorage.getItem("lotteryLuck.pendingPlans.v1"),
        })
        """
    )
    assert first_state["posts"] == ["flush-retry-5xx"]
    assert first_state["pending"][0]["blocked"] is False
    assert first_state["pending"][0]["status"] == "retryable"
    assert first_state["pending"][0]["last_error"] == "HTTP 503"
    assert "temporary database failure" not in first_state["storedRaw"]
    assert "secret@example.com" not in first_state["storedRaw"]

    browser_page.evaluate("() => window.dispatchEvent(new Event('online'))")
    browser_page.wait_for_function(
        "() => window.__retryPosts.length === 2 && window.LotteryProduct.pendingPlans().length === 0"
    )
    assert browser_page.evaluate("() => window.__retryPosts") == [
        "flush-retry-5xx",
        "flush-retry-5xx",
    ]


def test_product_client_online_event_flushes_pending_plans(
    live_server_url, browser_page
):
    payload = _pending_plan_payload("online-flush")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
        }
        """,
        payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    browser_page.evaluate(
        """
        () => {
          window.__onlineFlushCalls = 0;
          window.fetch = (input, init = {}) => {
            window.__onlineFlushCalls += 1;
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          window.dispatchEvent(new Event("online"));
        }
        """
    )
    browser_page.wait_for_function(
        "() => window.__onlineFlushCalls === 1 && window.LotteryProduct.pendingPlans().length === 0"
    )

    assert browser_page.evaluate("() => window.__onlineFlushCalls") == 1


def test_product_client_double_load_uses_install_guard_without_trusting_public_object(
    live_server_url, browser_page
):
    payload = _pending_plan_payload("double-load-online")
    expected_payload = _sanitized_pending_plan_payload("double-load-online")
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        (payload) => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", JSON.stringify([payload]));
          window.LotteryProduct = {
            version: "20260713-product-client-v2",
            fake: true,
            flushPendingPlans: () => {
              throw new Error("attacker object must not be trusted");
            },
          };
        }
        """,
        payload,
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function(
        """
        () => window.LotteryProduct
          && window.LotteryProduct.version === "20260713-product-client-v2"
          && window.LotteryProduct.fake !== true
          && typeof window.LotteryProduct.createPlan === "function"
        """
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")

    result = browser_page.evaluate(
        """
        async () => {
          const posts = [];
          const firstApi = window.LotteryProduct;
          const firstRequest = firstApi.request;
          const firstFlush = firstApi.flushPendingPlans;
          const firstSentinelApi = window.__LotteryProductClient_20260713_product_client_v2__.api;
          const descriptor = Object.getOwnPropertyDescriptor(window, "LotteryProduct");
          let assignmentError = "";
          try {
            window.LotteryProduct.request = () => {
              throw new Error("mutated request");
            };
            window.LotteryProduct = {fake: true};
          } catch (error) {
            assignmentError = error.message;
          }
          window.fetch = (input, init = {}) => {
            posts.push(JSON.parse(init.body));
            return Promise.resolve(new Response(JSON.stringify({plan: {id: "saved"}}), {
              status: 201,
              headers: {"Content-Type": "application/json"},
            }));
          };
          window.dispatchEvent(new Event("online"));
          await window.LotteryProduct.flushPendingPlans();
          return {
            posts,
            pending: window.LotteryProduct.pendingPlans(),
            version: window.LotteryProduct.version,
            frozen: Object.isFrozen(window.LotteryProduct),
            sentinelFrozen: Object.isFrozen(window.__LotteryProductClient_20260713_product_client_v2__.api),
            propertyWritable: descriptor && descriptor.writable === true,
            propertyConfigurable: descriptor && descriptor.configurable === true,
            requestSame: window.LotteryProduct.request === firstRequest,
            flushSame: window.LotteryProduct.flushPendingPlans === firstFlush,
            sentinelSame: firstSentinelApi === window.LotteryProduct,
            fake: window.LotteryProduct.fake === true,
            assignmentError,
          };
        }
        """
    )

    assert result["version"] == "20260713-product-client-v2"
    assert result["posts"] == [expected_payload]
    assert result["pending"] == []
    assert result["frozen"] is True
    assert result["sentinelFrozen"] is True
    assert result["propertyWritable"] is False
    assert result["propertyConfigurable"] is False
    assert result["requestSame"] is True
    assert result["flushSame"] is True
    assert result["sentinelSame"] is True
    assert result["fake"] is False


def test_product_client_ignores_corrupt_pending_storage(
    live_server_url, browser_page
):
    browser_page.goto(f"{live_server_url}/privacy.html")
    browser_page.evaluate(
        """
        () => {
          localStorage.setItem("lotteryLuck.pendingPlans.v1", "{not valid json");
        }
        """
    )
    browser_page.add_script_tag(url=f"{live_server_url}{PRODUCT_CLIENT_URL}")
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")

    assert browser_page.evaluate("() => window.LotteryProduct.pendingPlans()") == []


def test_admin_initial_locked_without_stored_token_makes_no_protected_fetch(
    live_server_url, browser_page
):
    requests = []

    def route_admin(route):
        requests.append(route.request.url)
        route.fulfill(status=500, content_type="application/json", body='{"detail":"unexpected"}')

    _route_admin_api(browser_page, live_server_url, route_admin)

    browser_page.goto(f"{live_server_url}/admin.html")
    browser_page.wait_for_timeout(250)

    assert _admin_locked(browser_page)
    assert browser_page.locator("#adminAuthPanel").is_visible()
    assert browser_page.locator("#adminSettings").is_hidden()
    assert requests == []


def test_admin_wrong_token_validation_stays_locked_and_stops_follow_on_requests(
    live_server_url, browser_page
):
    requests = []

    def route_admin(route):
        requests.append(
            {
                "path": route.request.url.removeprefix(live_server_url),
                "token": route.request.headers.get("x-lottery-admin-token"),
            }
        )
        route.fulfill(
            status=401,
            headers={"WWW-Authenticate": "LotteryAdmin"},
            content_type="application/json",
            body='{"detail":"admin authorization required"}',
        )

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill("wrong-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        f"() => sessionStorage.getItem('{ADMIN_SESSION_KEY}') === null"
    )

    assert _admin_locked(browser_page)
    assert browser_page.locator("#adminTokenInput").input_value() == ""
    assert _stored_admin_token(browser_page) is None
    assert requests == [
        {"path": "/api/admin/settings", "token": "wrong-token"},
    ]


def test_admin_correct_token_validates_then_stores_and_unlocks(
    live_server_url, browser_page
):
    requests = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(
            {
                "path": path,
                "token": route.request.headers.get("x-lottery-admin-token"),
                "stored": browser_page.evaluate(
                    f"() => sessionStorage.getItem('{ADMIN_SESSION_KEY}')"
                ),
            }
        )
        if path == "/api/admin/settings":
            body = json.dumps(_admin_settings_payload(), ensure_ascii=False)
        elif path == "/api/admin/data-health":
            body = json.dumps(_admin_health_payload(), ensure_ascii=False)
        elif path == "/api/admin/tasks":
            body = json.dumps(_admin_tasks_payload(), ensure_ascii=False)
        else:
            body = "{}"
        route.fulfill(status=200, content_type="application/json", body=body)

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill("correct-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )
    deadline = time.time() + 5
    while len(requests) < 3 and time.time() < deadline:
        browser_page.wait_for_timeout(50)

    assert browser_page.locator("#adminTokenInput").input_value() == ""
    assert _stored_admin_token(browser_page) == "correct-token"
    assert browser_page.locator("#adminSettings").is_visible()
    assert requests[0] == {
        "path": "/api/admin/settings",
        "token": "correct-token",
        "stored": None,
    }
    assert {request["path"] for request in requests[1:]} == {
        "/api/admin/data-health",
        "/api/admin/tasks",
    }
    assert all(request["token"] == "correct-token" for request in requests)


def test_admin_existing_session_token_validates_before_unlocking(
    live_server_url, browser_page
):
    requests = []

    browser_page.add_init_script(
        f"sessionStorage.setItem('{ADMIN_SESSION_KEY}', 'stored-token');"
    )

    def route_admin(route):
        requests.append(
            {
                "path": route.request.url.removeprefix(live_server_url),
                "locked": browser_page.locator("#dataAdmin").get_attribute("data-locked"),
                "token": route.request.headers.get("x-lottery-admin-token"),
            }
        )
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_admin_settings_payload(), ensure_ascii=False),
        )

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )

    assert requests[0] == {
        "path": "/api/admin/settings",
        "locked": "true",
        "token": "stored-token",
    }


def test_admin_lock_removes_session_token_and_hides_panels(live_server_url, browser_page):
    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        if path == "/api/admin/settings":
            body = json.dumps(_admin_settings_payload(), ensure_ascii=False)
        elif path == "/api/admin/data-health":
            body = json.dumps(_admin_health_payload(), ensure_ascii=False)
        else:
            body = json.dumps(_admin_tasks_payload(), ensure_ascii=False)
        route.fulfill(status=200, content_type="application/json", body=body)

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")
    browser_page.locator("#adminTokenInput").fill("correct-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )

    browser_page.locator("#adminLockButton").click()

    assert _admin_locked(browser_page)
    assert _stored_admin_token(browser_page) is None
    assert browser_page.locator("#adminAuthPanel").is_visible()
    assert browser_page.locator("#adminSettings").is_hidden()
    assert browser_page.locator("#adminTasks").is_hidden()
    assert browser_page.locator("#adminLayout").is_hidden()


def test_admin_non_401_validation_failure_stays_locked_without_persisting_token(
    live_server_url, browser_page
):
    requests = []

    def route_admin(route):
        requests.append(route.request.url.removeprefix(live_server_url))
        route.fulfill(status=503, content_type="application/json", body='{"detail":"busy"}')

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill("candidate-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_timeout(250)

    assert _admin_locked(browser_page)
    assert _stored_admin_token(browser_page) is None
    assert browser_page.locator("#adminTokenInput").input_value() == ""
    assert requests == ["/api/admin/settings"]


def test_admin_validation_network_failure_stays_locked_without_leaking_token(
    live_server_url, browser_page
):
    submitted_token = "network-secret-token"
    requests = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(path)
        if path == "/api/admin/settings":
            route.abort()
            return
        route.fulfill(status=200, content_type="application/json", body="{}")

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill(submitted_token)
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_timeout(300)

    assert _admin_locked(browser_page)
    assert _stored_admin_token(browser_page) is None
    assert browser_page.locator("#adminSettings").is_hidden()
    assert browser_page.locator("#adminTasks").is_hidden()
    assert browser_page.locator("#adminLayout").is_hidden()
    assert browser_page.locator("#adminTokenInput").input_value() == ""
    assert submitted_token not in browser_page.locator("#apiStatus").inner_text()
    assert submitted_token not in browser_page.locator("#adminAuthMessage").inner_text()
    assert submitted_token not in browser_page.locator("#adminSummary").inner_text()
    assert requests == ["/api/admin/settings"]


def test_admin_late_validation_response_after_lock_does_not_unlock_or_store(
    live_server_url, browser_page
):
    submitted_token = "late-validation-token"
    requests = []
    delayed_settings = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(path)
        if path == "/api/admin/settings":
            delayed_settings.append(route)
            return
        route.fulfill(status=200, content_type="application/json", body="{}")

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill(submitted_token)
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#adminTokenInput').value === ''"
    )
    _wait_for_request_count(browser_page, requests, 1)
    browser_page.evaluate("() => window.lockAdmin()")
    delayed_settings[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(_admin_settings_payload(), ensure_ascii=False),
    )
    browser_page.wait_for_timeout(300)

    assert _admin_locked(browser_page)
    assert _stored_admin_token(browser_page) is None
    assert browser_page.locator("#adminSettings").is_hidden()
    assert submitted_token not in browser_page.locator("body").inner_text()
    assert requests == ["/api/admin/settings"]


def test_admin_late_health_response_after_lock_does_not_repopulate_dom(
    live_server_url, browser_page
):
    stale_marker = "STALE_PROTECTED_HEALTH"
    requests = []
    delayed_health = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(path)
        if path == "/api/admin/settings":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_admin_settings_payload(), ensure_ascii=False),
            )
            return
        if path == "/api/admin/data-health":
            delayed_health.append(route)
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"tasks": [{"provider": stale_marker}], "status": stale_marker}),
        )

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")
    browser_page.locator("#adminTokenInput").fill("correct-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )
    _wait_for_request_count(browser_page, requests, 2)
    browser_page.locator("#adminLockButton").click()
    delayed_health[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                **_admin_health_payload(),
                "logs": [{"game_key": "ssq", "source": stale_marker, "status": stale_marker}],
                "kpis": {**_admin_health_payload()["kpis"], "latest_crawl_at": stale_marker},
            },
            ensure_ascii=False,
        ),
    )
    browser_page.wait_for_timeout(400)

    assert _admin_locked(browser_page)
    assert _stored_admin_token(browser_page) is None
    assert browser_page.locator("#adminSettings").is_hidden()
    assert browser_page.locator("#adminTasks").is_hidden()
    assert browser_page.locator("#adminLayout").is_hidden()
    assert stale_marker not in browser_page.locator("#adminSummary").text_content()
    assert stale_marker not in browser_page.locator("#crawlLogs").text_content()
    assert stale_marker not in browser_page.locator("#adminTaskList").text_content()
    assert requests == ["/api/admin/settings", "/api/admin/data-health"]


def test_admin_late_tasks_response_after_lock_does_not_repopulate_dom(
    live_server_url, browser_page
):
    stale_marker = "STALE_PROTECTED_TASK"
    requests = []
    delayed_tasks = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(path)
        if path == "/api/admin/settings":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_admin_settings_payload(), ensure_ascii=False),
            )
            return
        if path == "/api/admin/data-health":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_admin_health_payload(), ensure_ascii=False),
            )
            return
        if path == "/api/admin/tasks":
            delayed_tasks.append(route)
            return
        route.fulfill(status=200, content_type="application/json", body="{}")

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")
    browser_page.locator("#adminTokenInput").fill("correct-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )
    _wait_for_request_count(browser_page, requests, 3)

    browser_page.locator("#adminLockButton").click()
    delayed_tasks[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "tasks": [
                    {
                        "provider": stale_marker,
                        "game_keys": [stale_marker],
                        "status": stale_marker,
                        "result": {"wrote_count": 0},
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    browser_page.wait_for_timeout(400)

    assert _admin_locked(browser_page)
    assert browser_page.locator("#adminTasks").is_hidden()
    assert stale_marker not in browser_page.locator("#adminTaskList").text_content()
    assert requests == [
        "/api/admin/settings",
        "/api/admin/data-health",
        "/api/admin/tasks",
    ]


def test_admin_duplicate_unlock_submit_sends_one_validation_request(
    live_server_url, browser_page
):
    requests = []
    delayed_settings = []

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(path)
        if path == "/api/admin/settings":
            delayed_settings.append(route)
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(_admin_health_payload()))

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill("dupe-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.locator("#adminUnlockButton").click(force=True)
    browser_page.wait_for_timeout(250)

    assert requests == ["/api/admin/settings"]
    assert browser_page.locator("#adminUnlockButton").is_disabled()
    delayed_settings[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(_admin_settings_payload(), ensure_ascii=False),
    )
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )


def test_admin_storage_disabled_uses_memory_token_until_lock(
    live_server_url, browser_page
):
    requests = []
    browser_page.add_init_script(
        """
        (() => {
          const storage = window.sessionStorage;
          Object.defineProperty(storage, "getItem", {
            value: () => { throw new Error("session disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "setItem", {
            value: () => { throw new Error("session disabled"); },
            configurable: true,
          });
          Object.defineProperty(storage, "removeItem", {
            value: () => { throw new Error("session disabled"); },
            configurable: true,
          });
        })();
        """
    )

    def route_admin(route):
        path = route.request.url.removeprefix(live_server_url)
        requests.append(
            {
                "path": path,
                "token": route.request.headers.get("x-lottery-admin-token"),
            }
        )
        if path == "/api/admin/settings":
            body = json.dumps(_admin_settings_payload(), ensure_ascii=False)
        elif path == "/api/admin/data-health":
            body = json.dumps(_admin_health_payload(), ensure_ascii=False)
        else:
            body = json.dumps(_admin_tasks_payload(), ensure_ascii=False)
        route.fulfill(status=200, content_type="application/json", body=body)

    _route_admin_api(browser_page, live_server_url, route_admin)
    browser_page.goto(f"{live_server_url}/admin.html")

    browser_page.locator("#adminTokenInput").fill("memory-token")
    browser_page.locator("#adminUnlockButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#dataAdmin').dataset.locked === 'false'"
    )
    _wait_for_request_count(browser_page, requests, 3)

    assert all(request["token"] == "memory-token" for request in requests)
    browser_page.locator("#adminLockButton").click()
    browser_page.wait_for_timeout(250)

    assert _admin_locked(browser_page)
    assert browser_page.locator("#adminSettings").is_hidden()


def test_result_detail_falls_back_to_old_avoid_number_reasons(
    live_server_url, browser_page
):
    record = {
        "id": "old-avoid",
        "created_at": "2026-06-18T08:00:00.000Z",
        "game_key": "ssq",
        "game_label": "双色球",
        "mode_label": "稳财号",
        "input_summary": "阳历1990年 · 辰时 · 北京市",
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_numbers": [7],
        "number_text": "01 02 03 04 05 06 07",
        "avoid_numbers": [{"number": 9, "reason": "旧记录避开 09，减少冲气叠加。"}],
        "review": {"status": "pending", "summary": "等待开奖数据更新后复盘。"},
    }
    browser_page.add_init_script(
        "localStorage.setItem('lotteryLuck.fortuneHistory.v1', "
        f"{json.dumps(json.dumps([record], ensure_ascii=False))});"
    )

    browser_page.goto(f"{live_server_url}/result.html?id=old-avoid")

    assert "旧记录避开 09" in browser_page.locator("#resultReasons").inner_text()


def test_result_detail_renders_legacy_string_closed_loop(
    live_server_url, browser_page
):
    record = {
        "id": "legacy-loop",
        "created_at": "2026-06-18T08:00:00.000Z",
        "game_key": "ssq",
        "game_label": "双色球",
        "mode_label": "稳财号",
        "input_summary": "阳历1990年 · 辰时 · 北京市",
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_numbers": [7],
        "number_text": "01 02 03 04 05 06 07",
        "fortune_report": {
            "closed_loop": [
                "个人信息 -> 木火通财格",
                "喜用元素 -> 尾数 3/8",
            ]
        },
        "review": {"status": "pending", "summary": "等待开奖数据更新后复盘。"},
    }
    browser_page.add_init_script(
        "localStorage.setItem('lotteryLuck.fortuneHistory.v1', "
        f"{json.dumps(json.dumps([record], ensure_ascii=False))});"
    )

    browser_page.goto(f"{live_server_url}/result.html?id=legacy-loop")
    loop_text = browser_page.locator("#resultLoop").inner_text()

    assert "个人信息 -> 木火通财格" in loop_text
    assert "喜用元素 -> 尾数 3/8" in loop_text
    assert "合参节点\n--" not in loop_text


def test_result_detail_renders_master_ritual_record(
    live_server_url, browser_page
):
    record = {
        "id": "master-ritual",
        "created_at": "2026-06-18T08:00:00.000Z",
        "game_key": "ssq",
        "game_label": "双色球",
        "mode_label": "稳财号",
        "input_summary": "阳历1990年 · 辰时 · 北京市",
        "main_numbers": [11, 12, 13, 14, 15, 16],
        "special_numbers": [1],
        "number_text": "11 12 13 14 15 16 01",
        "master_ritual": {
            "opening": "测试起盘开场",
            "verdict": "测试起盘断语：此盘先定火旺财浮。",
            "tail_map": {
                "favorable": [{"tail": 3, "element_label": "火"}],
                "avoid": [{"tail": 1, "element_label": "木"}],
                "legend": "尾数1/2木，3/4火，5/6土，7/8金，9/0水。",
            },
            "steps": [
                {"key": "birth_chart", "label": "定命盘", "value": "阳历生日已折算", "detail": "命盘细节"},
                {"key": "wealth_pattern", "label": "排本命财格", "value": "火旺财浮", "detail": "财格细节"},
                {"key": "daily_luck", "label": "定今日财局", "value": "西北财位", "detail": "财局细节"},
                {"key": "tail_digits", "label": "取喜用尾数", "value": "宜 3", "detail": "尾数细节"},
                {"key": "avoid_clash", "label": "避冲煞号", "value": "避 01", "detail": "避冲细节"},
                {"key": "final_numbers", "label": "落财运号", "value": "11 -> 12 -> 财眼01", "detail": "落号细节"},
            ],
        },
        "review": {"status": "pending", "summary": "等待开奖数据更新后复盘。"},
    }
    browser_page.add_init_script(
        "localStorage.setItem('lotteryLuck.fortuneHistory.v1', "
        f"{json.dumps(json.dumps([record], ensure_ascii=False))});"
    )

    browser_page.goto(f"{live_server_url}/result.html?id=master-ritual")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultMasterRitual').textContent.includes('测试起盘断语')",
        timeout=5000,
    )
    master_text = browser_page.locator("#resultMasterRitual").inner_text()

    assert "测试起盘断语" in master_text
    assert "定命盘" in master_text
    assert "落财运号" in master_text
    assert "喜用尾数 3火尾" in master_text
    assert "避开尾数 1木尾" in master_text


def test_result_detail_hides_poster_download_when_no_record(
    live_server_url, browser_page
):
    browser_page.add_init_script(
        "localStorage.removeItem('lotteryLuck.fortuneHistory.v1');"
    )

    browser_page.goto(f"{live_server_url}/result.html")

    assert "暂无财运号详情" in browser_page.locator("#resultTitle").inner_text()
    assert not browser_page.locator("#posterCanvas").is_visible()
    assert not browser_page.locator("#posterDownload").is_visible()
    assert browser_page.locator("#posterDownload").get_attribute("href") is None


def test_analysis_calendar_renders_api_text_without_html_injection(
    live_server_url, browser_page
):
    browser_page.route(
        f"{live_server_url}/api/calendar",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "today": "2026-06-19",
                    "games": [
                        {
                            "game_key": "ssq",
                            "game_name": '<img src=x onerror="window.__calendarInjected=1">恶意彩种',
                            "latest_issue": "2026068",
                            "latest_date": "2026-06-19",
                            "next_draw_date": "2026-06-20",
                            "status": "等待开奖",
                            "reminder_key": "reminder:ssq:2026-06-20",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&window=30")
    browser_page.wait_for_function(
        "() => document.querySelector('#calendarPanel').textContent.includes('恶意彩种')",
        timeout=5000,
    )

    assert browser_page.locator("#calendarPanel img").count() == 0
    assert (
        browser_page.evaluate("() => Boolean(window.__calendarInjected)")
        is False
    )


def _analysis_payload(game_key="ssq"):
    return {
        "game_key": game_key,
        "summary": {
            "draw_count": 30,
            "latest_issue": "2026068",
            "latest_date": "2026-06-19",
        },
        "common": {
            "hot": [{"number": 1, "count": 8}],
            "cold": [{"number": 2, "count": 1}],
            "missing": [{"number": 3, "missing": 5}],
        },
        "trend": {
            "sum": [{"label": "90-99", "count": 3}],
            "odd_even": [{"label": "3:3", "count": 4}],
            "zone": [{"label": "二区", "count": 2}],
        },
        "professional": {
            "ac": [{"label": "8", "count": 2}],
            "mod3": [{"label": "2:2:2", "count": 2}],
            "prime_composite": [{"label": "2:4", "count": 2}],
            "tail": [{"label": "1", "count": 3}],
        },
        "recent_draws": [
            {
                "draw_date": "2026-06-19",
                "issue": "2026068",
                "main": [1, 2, 3, 4, 5, 6],
                "special": [7],
                "tags": ["测试"],
            }
        ],
    }


def _calendar_payload():
    return {
        "today": "2026-06-19",
        "games": [
            {
                "game_key": "ssq",
                "game_name": "双色球",
                "latest_issue": "2026068",
                "latest_date": "2026-06-19",
                "next_draw_date": "2026-06-20",
                "status": "等待开奖",
                "reminder_key": "reminder:ssq:2026-06-20",
            }
        ],
    }


def _pool_payload():
    return {
        "summary": {"pool_size": 1, "duplicate_groups": 0, "extreme_sum_count": 0},
        "entries": [
            {
                "main": [1, 2, 3, 4, 5, 6],
                "special": [7],
                "risk_score": 1,
                "hot_hits": 2,
                "cold_hits": 1,
                "sum": 21,
                "sum_level": "正常",
                "ac_value": 8,
                "prime_composite": "3:3",
                "mod3": "2:2:2",
                "zone": "二区",
                "tail_pattern": "1尾",
                "warnings": [],
            }
        ],
    }


def _filter_payload():
    return {
        "conditions": {},
        "candidates": [
            {
                "main": [1, 2, 3, 4, 5, 6],
                "special": [7],
                "tags": ["测试"],
                "mod3": "2:2:2",
                "tail_pattern": "1尾",
                "max_consecutive_run": 2,
                "omission_hits": [],
            }
        ],
    }


def test_analysis_page_uses_shared_product_client_for_natural_api_requests(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => Boolean(window.LotteryProduct)")
    client_id = browser_page.evaluate("() => window.LotteryProduct.clientId()")

    calls = []

    def route_analysis_api(route):
        request = route.request
        path = request.url.removeprefix(live_server_url)
        calls.append(
            {
                "path": path,
                "method": request.method,
                "client": request.headers.get("x-lottery-client-id"),
                "content_type": request.headers.get("content-type"),
                "body": json.loads(request.post_data or "{}") if request.post_data else None,
            }
        )
        if path == "/api/games":
            body = {"games": [{"game_key": "ssq", "game_name": "双色球", "latest_date": "2026-06-19", "latest_issue": "2026068"}]}
        elif path.startswith("/api/analysis/"):
            body = _analysis_payload("ssq")
        elif path == "/api/calendar":
            body = _calendar_payload()
        elif path == "/api/surfaces/config":
            body = {
                "version": 1,
                "views": ["data", "strategy"],
                "games": {"ssq": {"research": {"strategy": {"condition_fields": ["sum_min", "sum_max"]}}}},
            }
        else:
            body = {}
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body, ensure_ascii=False),
        )

    for pattern in [
        "/api/games",
        "/api/analysis/**",
        "/api/calendar",
        "/api/surfaces/config",
    ]:
        browser_page.route(f"{live_server_url}{pattern}", route_analysis_api)

    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&window=30")
    browser_page.wait_for_function(
        "() => document.querySelector('#calendarPanel').textContent.includes('双色球')"
    )

    expected_paths = {
        "/api/games",
        "/api/analysis/ssq?window=30",
        "/api/calendar",
    }
    seen_paths = {call["path"] for call in calls}
    assert expected_paths.issubset(seen_paths)
    assert all(call["client"] == client_id for call in calls)
    analysis_call = next(call for call in calls if call["path"] == "/api/analysis/ssq?window=30")
    assert analysis_call["method"] == "GET"


def test_analysis_http_error_ui_works_through_shared_product_client(
    live_server_url, browser_page
):
    browser_page.route(
        f"{live_server_url}/api/games",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"games": [{"game_key": "ssq", "game_name": "双色球"}]}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/analysis/**",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps({"detail": "analysis unavailable"}),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/calendar",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_calendar_payload(), ensure_ascii=False),
        ),
    )

    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&window=30")
    browser_page.wait_for_function(
        "() => document.querySelector('#analysisSummary').textContent.includes('分析数据暂不可用')"
    )

    assert browser_page.locator("#analysisSummary").get_attribute("class").find("error") >= 0


def test_stale_prediction_response_does_not_overwrite_switched_game_or_history(
    live_server_url, browser_page
):
    # Delay the first response inside the browser. Sleeping in a synchronous
    # Playwright route handler can block the client and postpone the game switch
    # until after the stale response has already been rendered.
    browser_page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, init = {}) => {
            const url = new URL(typeof input === "string" ? input : input.url, location.origin);
            const body = init.body ? JSON.parse(init.body) : {};
            const isDelayedPrediction = url.pathname === "/api/predict" && body.game_key === "ssq";
            if (!isDelayedPrediction) return originalFetch(input, init);
            return originalFetch(input, init).then(
              (response) => new Promise((resolve) => setTimeout(() => resolve(response), 800)),
            );
          };
        })();
        """
    )

    def route_predict(route):
        body = json.loads(route.request.post_data or "{}")
        game_key = body.get("game_key", "ssq")
        if game_key == "ssq":
            payload = _prediction_payload("ssq", [21, 22, 23, 24, 25, 26], [6])
        else:
            payload = _prediction_payload("dlt", [3, 4, 5, 6, 7], [8, 9])
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")

    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.locator('button[data-game="dlt"]').click()
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=6000,
    )

    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '03 04 05 06 07 08 09'",
        timeout=3000,
    )

    assert browser_page.locator("#fortuneNumber").inner_text() == "03 04 05 06 07 08 09"
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert len(records) == 1
    assert records[0]["game_key"] == "dlt"


def test_game_switch_cancels_active_cinematic_stage(live_server_url, browser_page):
    def route_predict(route):
        time.sleep(1.2)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1]),
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'running'"
    )
    browser_page.locator('button[data-game="dlt"]').click()

    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "cancelled"


def test_default_empty_form_submission_does_not_start_motion_or_request_prediction(
    live_server_url, browser_page
):
    predict_calls = []

    def route_predict(route):
        predict_calls.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])),
        )

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")

    browser_page.locator("#submitButton").click()
    browser_page.wait_for_timeout(250)

    assert predict_calls == []
    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "idle"
    assert browser_page.locator("#submitButton").is_enabled()


def test_manual_prediction_makes_ritual_state_visibly_active(
    live_server_url, browser_page
):
    def route_predict(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1]),
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )

    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()

    browser_page.locator(".fortune-ritual-panel.is-ritual-running").wait_for(
        state="visible",
        timeout=500,
    )
    assert browser_page.locator(".fortune-hook").is_hidden()
    assert "正在起盘" in browser_page.locator("#ritualStatus").inner_text()
    assert browser_page.locator("#ritualProgress").evaluate(
        "el => Number(el.style.getPropertyValue('--ritual-progress'))"
    ) > 0
    assert browser_page.locator(".ritual-step.active").count() == 1

    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )
    assert "起盘完成" in browser_page.locator("#ritualStatus").inner_text()
    assert "测试起盘断语" in browser_page.locator("#masterRitual").inner_text()
    assert "落财运号" in browser_page.locator("#masterRitual").inner_text()
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert records[0]["master_ritual"]["verdict"].startswith("测试起盘断语")


def test_motion_controller_moves_from_running_to_complete(live_server_url, browser_page):
    browser_page.goto(live_server_url)
    browser_page.evaluate(
        """
        () => window.FortuneMotion.start({
          requestId: 9001,
          steps: [
            {label: '定命盘'},
            {label: '排财格'},
            {label: '定财局'},
            {label: '取尾数'},
            {label: '落财号'},
          ],
        })
        """
    )

    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "running"
    assert browser_page.locator("#ritualStage").get_attribute("aria-hidden") == "false"
    assert browser_page.locator("#motionSteps li").count() == 5

    browser_page.evaluate(
        """
        () => window.FortuneMotion.resolve(
          {requestId: 9001},
          {main: [3, 8, 16, 21, 27, 32], special: [9]}
        )
        """
    )
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=5000,
    )

    assert browser_page.locator("#motionNumbers .motion-ball").count() == 7
    assert browser_page.locator("#motionNumbers .motion-ball").evaluate_all(
        "nodes => nodes.map((node) => node.textContent)"
    ) == [
        "03", "08", "16", "21", "27", "32", "09"
    ]
    assert browser_page.locator("#motionNumbers").evaluate(
        """
        (node) => Array.from(node.childNodes)
          .every((child) => child.nodeType !== Node.TEXT_NODE)
        """
    )


def test_scroll_sections_reveal_once(live_server_url, browser_page):
    _complete_3d_prediction(browser_page, live_server_url)
    section = browser_page.locator(".master-ritual-panel")
    assert section.get_attribute("data-motion-reveal") == ""
    section.scroll_into_view_if_needed()
    browser_page.wait_for_function(
        "() => document.querySelector('.master-ritual-panel').classList.contains('is-revealed')"
    )
    assert section.get_attribute("class").count("is-revealed") == 1


def test_reveal_sections_stay_visible_when_motion_script_is_blocked(
    live_server_url, browser_page
):
    browser_page.route("**/motion.js*", lambda route: route.abort())
    _route_predict_payload(browser_page, live_server_url, _prediction_payload_3d())
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    browser_page.locator('button[data-game="3d"]').click()
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => !document.querySelector('#predictionResults').hidden",
        timeout=5000,
    )

    sections = browser_page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-motion-reveal]'))
          .map((node) => ({
            className: node.className,
            opacity: getComputedStyle(node).opacity,
            visibility: getComputedStyle(node).visibility,
          }))
        """
    )

    assert len(sections) == 10
    assert all(section["opacity"] == "1" for section in sections)
    assert all(section["visibility"] == "visible" for section in sections)


def test_home_stays_clean_while_slow_games_api_resolves(
    live_server_url, browser_page
):
    browser_page.set_viewport_size({"width": 1280, "height": 1600})
    browser_page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          window.__gamesFetchStarted = false;
          window.__gamesFetchResolved = false;
          window.fetch = (input, init) => {
            const url = typeof input === "string" ? input : input?.url || "";
            if (!url.includes("/api/games")) return originalFetch(input, init);
            window.__gamesFetchStarted = true;
            return new Promise(() => {});
          };
        })();
        """
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        """
        () => {
          return window.__gamesFetchStarted
            && window.__gamesFetchResolved === false
            && document.querySelector('#predictionResults')?.hidden === true;
        }
        """,
        timeout=1200,
    )


def test_reveal_is_idempotent_for_repeated_initialization(
    live_server_url, browser_page
):
    browser_page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          window.__gamesFetchStarted = false;
          window.fetch = (input, init) => {
            const url = typeof input === "string" ? input : input?.url || "";
            if (!url.includes("/api/games")) return originalFetch(input, init);
            window.__gamesFetchStarted = true;
            return new Promise(() => {});
          };
          window.__revealObserverCount = 0;
          window.__revealObserveCount = 0;
          window.IntersectionObserver = class {
            constructor(callback, options) {
              this.callback = callback;
              this.options = options;
              window.__revealObserverCount += 1;
            }
            observe() {
              window.__revealObserveCount += 1;
            }
            unobserve() {}
          };
        })();
        """
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        "() => window.FortuneMotion && window.__gamesFetchStarted"
    )
    browser_page.evaluate(
        "() => document.querySelector('.master-ritual-panel').classList.add('is-revealed')"
    )
    browser_page.wait_for_function(
        "() => getComputedStyle(document.querySelector('.master-ritual-panel')).opacity === '1'"
    )
    result = browser_page.evaluate(
        """
        () => {
          const section = document.querySelector('.master-ritual-panel');
          window.FortuneMotion.reveal();
          window.FortuneMotion.reveal();
          return {
            observerCount: window.__revealObserverCount,
            observeCount: window.__revealObserveCount,
            className: section.className,
            opacity: getComputedStyle(section).opacity,
          };
        }
        """
    )

    assert result["observerCount"] == 1
    assert result["observeCount"] == 10
    assert result["className"].count("is-revealed") == 1
    assert result["opacity"] == "1"


def test_reduced_motion_skips_long_cinematic_timeline(live_server_url, browser_page):
    browser_page.emulate_media(reduced_motion="reduce")
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    browser_page.route(
        f"{live_server_url}/api/predict",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        ),
    )
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    started_at = time.monotonic()
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=1500,
    )
    assert time.monotonic() - started_at < 1.5
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 7


def test_reduced_motion_scrolls_to_result_without_smooth(
    live_server_url, browser_page
):
    browser_page.emulate_media(reduced_motion="reduce")
    browser_page.add_init_script(
        """
        (() => {
          window.__scrollIntoViewCalls = [];
          Element.prototype.scrollIntoView = function (options) {
            window.__scrollIntoViewCalls.push({
              target: this.id || this.className || this.tagName,
              behavior: options && typeof options === "object" ? options.behavior : options,
            });
          };
        })();
        """
    )
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    browser_page.route(
        f"{live_server_url}/api/predict",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        ),
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        """
        () => window.__scrollIntoViewCalls.some((call) =>
          String(call.target).includes('oracle-board')
        )
        """,
        timeout=5000,
    )

    oracle_calls = [
        call
        for call in browser_page.evaluate("() => window.__scrollIntoViewCalls")
        if "oracle-board" in str(call["target"])
    ]
    assert oracle_calls
    assert oracle_calls[-1]["behavior"] in {"auto", "instant"}


def test_cinematic_stage_fits_twenty_kl8_balls_on_mobile(
    live_server_url,
    browser_page,
):
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.goto(live_server_url)
    browser_page.evaluate(
        """
        () => {
          const stage = document.querySelector("#ritualStage");
          const numbers = document.querySelector("#motionNumbers");
          stage.classList.remove("is-dismissed");
          stage.dataset.motionState = "complete";
          stage.setAttribute("aria-hidden", "false");
          numbers.replaceChildren();
          Array.from({length: 20}, (_, index) => index + 1).forEach((value, index) => {
            const ball = document.createElement("i");
            ball.className = "motion-ball";
            ball.style.setProperty("--motion-index", String(index));
            ball.textContent = String(value).padStart(2, "0");
            numbers.append(ball);
          });
        }
        """
    )

    layout = browser_page.evaluate(
        """
        () => {
          const copy = document.querySelector(".ritual-stage-copy");
          const numbers = document.querySelector("#motionNumbers");
          const balls = Array.from(document.querySelectorAll("#motionNumbers .motion-ball"));
          const copyRect = copy.getBoundingClientRect();
          const numbersRect = numbers.getBoundingClientRect();
          const rows = new Set(
            balls.map((ball) => Math.round(ball.getBoundingClientRect().top))
          );
          return {
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            copyLeft: copyRect.left,
            copyRight: copyRect.right,
            numbersLeft: numbersRect.left,
            numbersRight: numbersRect.right,
            numbersScrollWidth: numbers.scrollWidth,
            numbersClientWidth: numbers.clientWidth,
            rowCount: rows.size,
            ballsInViewport: balls.every((ball) => {
              const rect = ball.getBoundingClientRect();
              return rect.left >= 0
                && rect.right <= window.innerWidth
                && rect.top >= 0
                && rect.bottom <= window.innerHeight;
            }),
          };
        }
        """
    )

    assert layout["copyLeft"] >= 0
    assert layout["copyRight"] <= layout["viewportWidth"]
    assert layout["numbersLeft"] >= 0
    assert layout["numbersRight"] <= layout["viewportWidth"]
    assert layout["numbersScrollWidth"] <= layout["numbersClientWidth"] + 1
    assert layout["rowCount"] > 1
    assert layout["ballsInViewport"] is True


def test_active_cinematic_stage_blocks_click_through_to_page_floaters(
    live_server_url,
    browser_page,
):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )
    browser_page.locator('[data-select-name="calendar_type"] .custom-select-trigger').click()
    browser_page.locator('[data-select-name="calendar_type"] .custom-select-menu').wait_for(
        state="visible",
        timeout=1000,
    )
    browser_page.evaluate(
        """
        () => {
          const stage = document.querySelector("#ritualStage");
          const option = document.querySelector(
            '[data-select-name="calendar_type"] .custom-select-option[data-value="lunar"]'
          );
          window.__stageClickThroughs = 0;
          option.addEventListener("click", () => {
            window.__stageClickThroughs += 1;
          });
          stage.classList.remove("is-dismissed");
          stage.dataset.motionState = "running";
          stage.setAttribute("aria-hidden", "false");
        }
        """
    )
    point = browser_page.evaluate(
        """
        () => {
          const option = document.querySelector(
            '[data-select-name="calendar_type"] .custom-select-option[data-value="lunar"]'
          );
          const rect = option.getBoundingClientRect();
          return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
        }
        """
    )
    before_click = browser_page.evaluate(
        """
        ({x, y}) => {
          const stage = document.querySelector("#ritualStage");
          const menu = document.querySelector('[data-select-name="calendar_type"] .custom-select-menu');
          return {
            stagePointerEvents: getComputedStyle(stage).pointerEvents,
            stageZIndex: Number(getComputedStyle(stage).zIndex),
            menuZIndex: Number(getComputedStyle(menu).zIndex),
          };
        }
        """,
        point,
    )
    browser_page.mouse.click(point["x"], point["y"])
    after_click = browser_page.evaluate(
        """
        () => ({
          clickThroughs: window.__stageClickThroughs,
          selectedCalendarType: document.querySelector('[name="calendar_type"]').value,
        })
        """
    )

    assert before_click["stagePointerEvents"] == "auto"
    assert before_click["stageZIndex"] > before_click["menuZIndex"]
    assert after_click == {"clickThroughs": 0, "selectedCalendarType": "solar"}


def test_reduced_motion_disables_result_refreshed_animation(
    live_server_url,
    browser_page,
):
    browser_page.emulate_media(reduced_motion="reduce")
    browser_page.goto(live_server_url)

    animation_name = browser_page.evaluate(
        """
        () => {
          const target = document.querySelector("#fortuneNumber");
          target.classList.add("result-refreshed");
          return getComputedStyle(target).animationName;
        }
        """
    )

    assert animation_name == "none"


def test_motion_controller_cancel_settles_pending_resolve_quickly(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          window.FortuneMotion.start({requestId: 9101});
          const pending = window.FortuneMotion.resolve(
            {requestId: 9101},
            {main: [3, 8, 16, 21, 27, 32], special: [9]}
          );
          window.FortuneMotion.cancel({requestId: 9101});
          const outcome = await Promise.race([
            pending.then((value) => ({settled: true, value})),
            new Promise((resolve) => window.setTimeout(
              () => resolve({settled: false, value: null}),
              250
            )),
          ]);
          return {
            ...outcome,
            state: document.querySelector("#ritualStage").dataset.motionState,
            ballCount: document.querySelectorAll("#motionNumbers .motion-ball").length,
          };
        }
        """
    )

    assert result == {
        "settled": True,
        "value": False,
        "state": "cancelled",
        "ballCount": 0,
    }


def test_motion_controller_old_resolve_does_not_overwrite_new_request(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          window.FortuneMotion.start({requestId: 9201});
          const oldResolve = window.FortuneMotion.resolve(
            {requestId: 9201},
            {main: [1, 2, 3, 4, 5, 6], special: [7]}
          );
          window.FortuneMotion.start({requestId: 9202});
          const oldOutcome = await Promise.race([
            oldResolve.then((value) => ({settled: true, value})),
            new Promise((resolve) => window.setTimeout(
              () => resolve({settled: false, value: null}),
              250
            )),
          ]);
          return {
            oldOutcome,
            state: document.querySelector("#ritualStage").dataset.motionState,
            title: document.querySelector("#motionTitle").textContent,
            ballTexts: Array.from(document.querySelectorAll("#motionNumbers .motion-ball"))
              .map((node) => node.textContent),
          };
        }
        """
    )

    assert result == {
        "oldOutcome": {"settled": True, "value": False},
        "state": "running",
        "title": "命盘入局",
        "ballTexts": [],
    }


def test_motion_controller_ignores_malformed_request_id(live_server_url, browser_page):
    browser_page.goto(live_server_url)

    result = browser_page.evaluate(
        """
        () => {
          window.FortuneMotion.start({});
          window.FortuneMotion.start({requestId: ''});
          return {
            state: document.querySelector("#ritualStage").dataset.motionState,
            hidden: document.querySelector("#ritualStage").getAttribute("aria-hidden"),
            stepCount: document.querySelectorAll("#motionSteps li").length,
          };
        }
        """
    )

    assert result == {"state": "idle", "hidden": "true", "stepCount": 0}


def test_motion_controller_reduced_motion_fail_interrupts_pending_resolve(
    live_server_url, browser_page
):
    browser_page.emulate_media(reduced_motion="reduce")
    browser_page.goto(live_server_url)

    result = browser_page.evaluate(
        """
        async () => {
          window.FortuneMotion.start({requestId: 9301});
          queueMicrotask(() => window.FortuneMotion.fail({requestId: 9301}, "测试失败"));
          const value = await window.FortuneMotion.resolve(
            {requestId: 9301},
            {main: [3, 8, 16, 21, 27, 32], special: [9]}
          );
          return {
            value,
            state: document.querySelector("#ritualStage").dataset.motionState,
            ballCount: document.querySelectorAll("#motionNumbers .motion-ball").length,
          };
        }
        """
    )

    assert result == {"value": False, "state": "error", "ballCount": 0}


def test_manual_prediction_starts_ritual_before_slow_api_returns(
    live_server_url, browser_page
):
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    browser_page.add_init_script(
        f"""
        (() => {{
          const payload = {json.dumps(payload, ensure_ascii=False)};
          const originalFetch = window.fetch.bind(window);
          window.__slowPredictSawSignal = false;
          window.fetch = (input, init) => {{
            const url = typeof input === "string" ? input : input?.url || "";
            if (!url.includes("/api/predict")) return originalFetch(input, init);
            window.__slowPredictSawSignal = Boolean(init?.signal);
            const response = () => new Response(JSON.stringify(payload), {{
              status: 200,
              headers: {{ "Content-Type": "application/json" }},
            }});
            return new Promise((resolve, reject) => {{
              const timer = window.setTimeout(() => resolve(response()), 800);
              init?.signal?.addEventListener("abort", () => {{
                window.clearTimeout(timer);
                reject(new DOMException("Aborted", "AbortError"));
              }}, {{once: true}});
            }});
          }};
        }})();
        """
    )
    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )

    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()

    browser_page.locator(".fortune-ritual-panel.is-ritual-running").wait_for(
        state="visible",
        timeout=300,
    )
    assert browser_page.locator(".fortune-hook").is_hidden()
    assert "正在起盘" in browser_page.locator("#ritualStatus").inner_text()
    assert browser_page.locator("#ritualProgress").evaluate(
        "el => Number(el.style.getPropertyValue('--ritual-progress'))"
    ) > 0

    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )
    assert browser_page.evaluate("() => window.__slowPredictSawSignal") is True


def test_home_waits_for_manual_submission_before_showing_numbers(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")

    assert browser_page.locator("#fortuneNumber").inner_text() == ""
    assert browser_page.locator("#numberBalls .ball").count() == 0
    assert browser_page.locator("#predictionResults").is_hidden()
    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "idle"
    assert browser_page.locator("#generateFeedback").inner_text() == ""
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert records == []


def test_switching_games_resets_result_surfaces_to_idle(
    live_server_url, browser_page
):
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    payload["recent_draws"] = [
        {
            "issue": "2026070",
            "draw_date": "2026-06-21",
            "red_numbers": "11,12,13,14,15,16",
            "blue_number": "01",
        }
    ]
    payload["credibility_chain"] = [
        {"title": "测试可信链", "text": "测试可信解释", "detail": "测试可信细节"}
    ]
    payload["number_reasons"] = {
        "main": [{"number": 11, "role": "测试主号", "text": "测试号码释义"}],
        "special": [{"number": 1, "role": "测试财眼", "text": "测试财眼释义"}],
    }

    browser_page.route(
        f"{live_server_url}/api/predict",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        ),
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '11 12 13 14 15 16 01'",
        timeout=6000,
    )
    assert "测试可信链" in browser_page.locator("#credibilityChain").inner_text()
    assert "测试号码释义" in browser_page.locator("#numberReasons").inner_text()
    assert "2026070" in browser_page.locator("#recentDraws").inner_text()

    browser_page.locator('button[data-game="dlt"]').click()
    snapshot = browser_page.evaluate(
        """
        () => ({
          fortuneHeadline: document.querySelector('#fortuneHeadline').textContent,
          fortuneSubline: document.querySelector('#fortuneSubline').textContent,
          fortuneTags: Array.from(document.querySelectorAll('#fortuneTags span'))
            .map((node) => node.textContent),
          profileValues: Array.from(document.querySelectorAll('#metaphysicsProfile dd'))
            .map((node) => node.textContent),
          avoidNumbers: document.querySelector('#avoidNumbers').textContent,
          masterRitual: document.querySelector('#masterRitual').textContent,
          credibility: document.querySelector('#credibilityChain').textContent,
          interpretation: document.querySelector('#interpretationLayers').textContent,
          hotNumbers: document.querySelector('#hotNumbers').textContent,
          historyHotText: document.querySelector('#historyHotText').textContent,
          coldNumbers: document.querySelector('#coldNumbers').textContent,
          aiState: document.querySelector('#aiState').textContent,
          personalBasis: document.querySelector('#personalBasis').textContent,
          recentDraws: document.querySelector('#recentDraws').textContent,
          numberReasons: document.querySelector('#numberReasons').textContent,
          disclaimer: document.querySelector('#disclaimer').textContent,
        })
        """
    )

    assert snapshot == {
        "fortuneHeadline": "本次结果已清空",
        "fortuneSubline": "重新填写信息即可生成新的参考。",
        "fortuneTags": ["本命财格", "今日宜忌", "避开号"],
        "profileValues": ["--", "--", "--", "--"],
        "avoidNumbers": "--",
        "masterRitual": "本次暂无取号说明。重新起盘后查看完整思路。",
        "credibility": "本次暂无详细依据。",
        "interpretation": "本次暂无解读。重新起盘后查看完整内容。",
        "hotNumbers": "--",
        "historyHotText": "--",
        "coldNumbers": "--",
        "aiState": "命盘合参",
        "personalBasis": "本次暂无运势说明。",
        "recentDraws": "暂无近期开奖数据。",
        "numberReasons": "本次暂无号码说明。",
        "disclaimer": "仅供娱乐参考，请理性看待结果。",
    }


def test_reclicking_active_game_tab_during_request_keeps_prediction_running(
    live_server_url, browser_page
):
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    browser_page.add_init_script(
        f"""
        (() => {{
          const payload = {json.dumps(payload, ensure_ascii=False)};
          const originalFetch = window.fetch.bind(window);
          window.__predictAbortCount = 0;
          window.__predictCalls = [];
          window.fetch = (input, init) => {{
            const url = typeof input === "string" ? input : input?.url || "";
            if (!url.includes("/api/predict")) return originalFetch(input, init);
            const body = JSON.parse(init?.body || "{{}}");
            window.__predictCalls.push(body.game_key);
            const response = () => new Response(JSON.stringify(payload), {{
              status: 200,
              headers: {{"Content-Type": "application/json"}},
            }});
            return new Promise((resolve, reject) => {{
              const timer = window.setTimeout(() => resolve(response()), 900);
              const abort = () => {{
                window.__predictAbortCount += 1;
                window.clearTimeout(timer);
                reject(new DOMException("Aborted", "AbortError"));
              }};
              if (init?.signal?.aborted) {{
                abort();
                return;
              }}
              init?.signal?.addEventListener("abort", abort, {{once: true}});
            }});
          }};
        }})();
        """
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.locator('button[data-game="ssq"]').click()
    browser_page.wait_for_function(
        """
        () => window.__predictAbortCount > 0
          || document.querySelector('#fortuneNumber').textContent === '11 12 13 14 15 16 01'
        """,
        timeout=6000,
    )

    assert browser_page.evaluate("() => window.__predictAbortCount") == 0
    assert browser_page.evaluate("() => window.__predictCalls") == ["ssq"]
    assert browser_page.locator("#fortuneNumber").inner_text() == "11 12 13 14 15 16 01"
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert len(records) == 1
    assert records[0]["storage_state"] == "local"


def test_cinematic_stage_waits_for_real_prediction_before_dropping_numbers(
    live_server_url, browser_page
):
    payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    browser_page.add_init_script(
        f"""
        (() => {{
          const payload = {json.dumps(payload, ensure_ascii=False)};
          const originalFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {{
            const url = typeof input === "string" ? input : input?.url || "";
            if (!url.includes("/api/predict")) return originalFetch(input, init);
            const response = () => new Response(JSON.stringify(payload), {{
              status: 200,
              headers: {{"Content-Type": "application/json"}},
            }});
            return new Promise((resolve) => setTimeout(() => resolve(response()), 2800));
          }};
        }})();
        """
    )
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()

    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'waiting'",
        timeout=4000,
    )
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 0

    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=6000,
    )
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 7
    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '11 12 13 14 15 16 01'",
        timeout=3000,
    )
    assert browser_page.locator("#fortuneNumber").inner_text() == "11 12 13 14 15 16 01"


def test_manual_prediction_failure_preserves_previous_result_and_history(
    live_server_url, browser_page
):
    def route_predict(route):
        route.abort("failed")

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    before = browser_page.locator("#fortuneNumber").inner_text()
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'error'",
        timeout=5000,
    )

    assert browser_page.locator("#fortuneNumber").inner_text() == before
    assert "起盘失败" in browser_page.locator("#generateFeedback").inner_text()
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert records == []


@pytest.mark.parametrize("malformed_kind", ["missing_numbers", "wrong_main_count"])
def test_malformed_predict_200_preserves_previous_result_and_history(
    live_server_url, browser_page, malformed_kind
):
    valid_payload = _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
    malformed_payload = _prediction_payload("ssq", [21, 22, 23, 24, 25, 26], [2])
    if malformed_kind == "missing_numbers":
        malformed_payload.pop("numbers")
    else:
        malformed_payload["numbers"] = {"main": [21, 22], "special": [2]}
    calls = 0

    def route_predict(route):
        nonlocal calls
        calls += 1
        payload = valid_payload if calls == 1 else malformed_payload
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    _fill_required_form(browser_page)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#fortuneNumber').textContent === '11 12 13 14 15 16 01'",
        timeout=6000,
    )
    before_records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert len(before_records) == 1

    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'error'",
        timeout=5000,
    )

    assert browser_page.locator("#fortuneNumber").inner_text() == "11 12 13 14 15 16 01"
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 0
    assert "起盘失败" in browser_page.locator("#generateFeedback").inner_text()
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert len(records) == 1
    assert records[0]["id"] == before_records[0]["id"]
    assert records[0]["number_text"] == before_records[0]["number_text"]


def test_home_hides_internal_status_copy(live_server_url, browser_page):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function(
        "() => !document.querySelector('#submitButton').disabled",
        timeout=5000,
    )

    visible_text = browser_page.locator("body").inner_text()

    assert "填写资料后点击开始起盘" not in visible_text
    assert browser_page.locator('a[href="./admin.html"]').count() == 0
    for internal_copy in [
        "AI 未启用",
        "AI 已启用",
        "Demo",
        "API",
        "默认示例盘",
        "样本",
        "数据后台",
        "数据更新",
    ]:
        assert internal_copy not in visible_text


def test_home_motion_has_no_mobile_horizontal_overflow(live_server_url, browser_page):
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    assert browser_page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


def _plan_detail_payload(
    *,
    plan_id="plan-detail-1",
    title="专业筛选方案",
    source_type="filter",
    status="saved",
    review=None,
):
    return {
        "id": plan_id,
        "client_id": "client-safe",
        "game_key": "3d",
        "target_issue": "2026194",
        "target_draw_date": "2026-07-13",
        "source_type": source_type,
        "request_id": "request-detail-1",
        "title": title,
        "status": status,
        "carried_from_plan_id": None,
        "created_at": "2026-07-12T08:00:00+08:00",
        "updated_at": "2026-07-12T09:30:00+08:00",
        "entries": [
            {
                "id": 11,
                "plan_id": plan_id,
                "position": 0,
                "main_numbers": [1, 2, 3],
                "special_numbers": [],
                "note": "第一组",
                "created_at": "2026-07-12T08:00:00+08:00",
            },
            {
                "id": 12,
                "plan_id": plan_id,
                "position": 1,
                "main_numbers": [6, 6, 2],
                "special_numbers": [],
                "note": "第二组",
                "created_at": "2026-07-12T08:00:00+08:00",
            },
        ],
        "condition_snapshot": {
            "plan_id": plan_id,
            "mode": "professional",
            "analysis_window": 120,
            "conditions_json": {
                "sum_min": 6,
                "sum_max": 18,
                "span_min": 1,
                "span_max": 8,
                "types": ["组三", "组六"],
                "odd_count": 2,
                "position_include": {"0": [1, 6], "2": [3]},
                "position_exclude": {"1": [9]},
                "unknown_future_key": "future-safe",
            },
            "metrics_json": {
                "latest_issue": "2026193",
                "data_version": "stats-v1",
                "sample_size": 120,
            },
            "latest_data_issue": "2026193",
            "latest_data_date": "2026-07-12",
            "created_at": "2026-07-12T08:00:00+08:00",
        },
        "review": review,
        "duplicate_warning": False,
    }


def _review_payload(plan_id="plan-detail-1"):
    return {
        "plan_id": plan_id,
        "draw_issue": "2026194",
        "draw_numbers": [1, 2, 3],
        "review_status": "reviewed",
        "direct_hit": True,
        "group_type": "组六",
        "matched_positions": [0, 1, 2],
        "matched_conditions": ["sum_min", "sum_max", "types"],
        "missed_conditions": ["position_include.0"],
        "result_json": {
            "draw_issue": "2026194",
            "draw_date": "2026-07-13",
            "draw_numbers": [1, 2, 3],
            "group_type": "组六",
            "entries": [
                {
                    "entry_id": 11,
                    "position": 0,
                    "main_numbers": [1, 2, 3],
                    "direct_hit": True,
                    "matched_positions": [0, 1, 2],
                    "any_position_hits": [1, 2, 3],
                    "matched_conditions": ["sum_min", "sum_max", "types"],
                    "missed_conditions": [],
                },
                {
                    "entry_id": 12,
                    "position": 1,
                    "main_numbers": [6, 6, 2],
                    "direct_hit": False,
                    "matched_positions": [1],
                    "any_position_hits": [2],
                    "matched_conditions": ["position_include.0"],
                    "missed_conditions": ["sum_max"],
                },
            ],
            "matched_conditions": ["sum_min", "sum_max", "types"],
            "missed_conditions": ["position_include.0"],
        },
        "reviewed_at": "2026-07-13T22:00:00+08:00",
    }


def test_plan_detail_loads_server_plan_by_id_and_renders_entries_snapshot_safely(
    live_server_url,
    browser_page,
):
    plan_id = "plan id/unsafe"
    calls = []
    plan = _plan_detail_payload(
        plan_id=plan_id,
        title='<img src=x onerror="window.__xss=1">专业筛选方案',
        source_type="manual",
    )

    browser_page.add_init_script(
        """
        localStorage.setItem("lotteryLuck.fortuneHistory.v1", JSON.stringify([
          {id: "other-local", game_label: "本地第一条", main_numbers: [9,9,9], source_type: "fortune"}
        ]));
        """
    )
    browser_page.route(
        f"{live_server_url}/api/plans/*",
        lambda route: (
            calls.append(route.request.url),
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"plan": plan}, ensure_ascii=False),
            ),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan%20id%2Funsafe")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultTitle').textContent.includes('专业筛选方案')",
        timeout=5000,
    )

    body_text = browser_page.locator("body").inner_text()
    assert calls == [f"{live_server_url}/api/plans/plan%20id%2Funsafe"]
    assert "本地第一条" not in body_text
    assert "第2026194期" in body_text
    assert "2026-07-13" in body_text
    assert "01 02 03" in body_text
    assert "06 06 02" in body_text
    assert "120期" in body_text
    assert "专业模式" in body_text
    assert "和值下限" in body_text
    assert "和值上限" in body_text
    assert "跨度下限" in body_text
    assert "号码类型" in body_text
    assert "奇数个数" in body_text
    assert "百位包含" in body_text
    assert "个位包含" in body_text
    assert "十位排除" in body_text
    assert "扩展信息" in body_text
    assert "future-safe" in body_text
    assert "数据版本" in body_text
    assert "2026193" in body_text
    assert "professional" not in body_text
    for raw_key in [
        "sum_min",
        "sum_max",
        "span_min",
        "span_max",
        "position_include.0",
        "position_include",
        "position_exclude",
        "unknown_future_key",
        "data_version",
    ]:
        assert raw_key not in body_text
    assert "大师起盘" not in body_text
    assert "财眼" not in body_text
    assert browser_page.evaluate("() => window.__xss") is None


def test_plan_detail_404_falls_back_only_to_same_legacy_id(live_server_url, browser_page):
    browser_page.add_init_script(
        """
        localStorage.setItem("lotteryLuck.fortuneHistory.v1", JSON.stringify([
          {id: "other-local", game_key: "3d", game_label: "不该展示", mode_label: "错", main_numbers: [9,9,9]},
          {id: "legacy-same", game_key: "3d", game_label: "旧版同ID", mode_label: "兼容记录", main_numbers: [1,2,3], source_type: "fortune"}
        ]));
        """
    )
    browser_page.route(
        f"{live_server_url}/api/plans/*",
        lambda route: route.fulfill(
            status=404,
            content_type="application/json",
            body=json.dumps({"detail": "not found"}),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=legacy-same")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultTitle').textContent.includes('旧版同ID')",
        timeout=5000,
    )
    assert "不该展示" not in browser_page.locator("body").inner_text()
    assert "大师起盘" in browser_page.locator("body").inner_text()

    browser_page.goto(f"{live_server_url}/result.html?id=missing-id")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultStatus').textContent.includes('不存在')",
        timeout=5000,
    )
    assert "不该展示" not in browser_page.locator("body").inner_text()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "不可访问"),
        (403, "不可访问"),
        (404, "不存在"),
    ],
)
def test_plan_detail_api_errors_do_not_leak_local_records(
    live_server_url,
    browser_page,
    status,
    expected,
):
    browser_page.add_init_script(
        """
        localStorage.setItem("lotteryLuck.fortuneHistory.v1", JSON.stringify([
          {id: "private-local", game_key: "3d", game_label: "隐私本地", main_numbers: [8,8,8]}
        ]));
        """
    )
    browser_page.route(
        f"{live_server_url}/api/plans/*",
        lambda route: route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps({"detail": "blocked"}),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=server-plan")
    browser_page.wait_for_function(
        f"() => document.querySelector('#resultStatus').textContent.includes('{expected}')",
        timeout=5000,
    )
    assert "隐私本地" not in browser_page.locator("body").inner_text()


def test_plan_detail_pending_review_autoreviews_once_and_tracks_view_once_without_pii(
    live_server_url,
    browser_page,
):
    plan = _plan_detail_payload(status="pending_review", review=None)
    calls = {"get": 0, "review": 0}
    events = []

    def route_plan(route):
        if route.request.method == "GET":
            calls["get"] += 1
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"plan": plan}, ensure_ascii=False),
            )
            return
        calls["review"] += 1
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {"plan": {**plan, "status": "reviewed", "review": _review_payload()}},
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1", route_plan)
    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1/review", route_plan)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultReview').textContent.includes('是否直选命中')",
        timeout=5000,
    )
    browser_page.locator("#resultReview").scroll_into_view_if_needed()
    browser_page.wait_for_function("() => window.__task13ReviewTracked === true", timeout=5000)
    browser_page.evaluate("() => window.scrollTo(0, 0)")
    browser_page.locator("#resultReview").scroll_into_view_if_needed()
    browser_page.wait_for_timeout(250)

    body_text = browser_page.locator("body").inner_text()
    assert calls == {"get": 1, "review": 1}
    assert "第2026194期" in body_text
    assert "01 02 03" in body_text
    assert "是否直选命中" in body_text
    assert "是" in body_text
    assert "否" in body_text
    assert "命中位置" in body_text
    assert "百位、十位、个位" in body_text
    assert "任意位置命中号码" in body_text
    assert "01、02、03" in body_text
    assert "命中条件" in body_text
    assert "和值下限、和值上限、号码类型" in body_text
    assert "未命中条件" in body_text
    assert "百位包含" in body_text
    for raw_key in [
        "direct_hit",
        "matched_positions",
        "any_position_hits",
        "matched_conditions",
        "missed_conditions",
        "sum_min",
        "sum_max",
        "position_include.0",
        "professional",
    ]:
        assert raw_key not in body_text
    assert events == [
        {
            "event_name": "review_viewed",
            "properties": {
                "game_key": "3d",
                "source_type": "filter",
                "review_status": "reviewed",
            },
        }
    ]
    assert "01" not in json.dumps(events, ensure_ascii=False)


def test_plan_detail_renders_reviewed_plan_when_review_status_is_hit_type(
    live_server_url,
    browser_page,
):
    review = {**_review_payload(), "review_status": "direct_hit"}
    plan = _plan_detail_payload(status="reviewed", review=review)
    events = []
    browser_page.route(
        f"{live_server_url}/api/plans/plan-detail-1",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": plan}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultStatus').textContent.includes('已复盘')",
        timeout=5000,
    )
    browser_page.locator("#resultReview").scroll_into_view_if_needed()
    browser_page.wait_for_function("() => window.__task13ReviewTracked === true", timeout=5000)
    browser_page.evaluate("() => window.scrollTo(0, 0)")
    browser_page.locator("#resultReview").scroll_into_view_if_needed()
    browser_page.wait_for_function("() => document.scrollingElement.scrollTop > 0", timeout=5000)

    review_text = browser_page.locator("#resultReview").inner_text()
    brand_decoration = browser_page.locator(".brand-lockup").evaluate(
        "node => getComputedStyle(node).textDecorationLine"
    )
    assert brand_decoration == "none"
    assert "开奖结果" in review_text
    assert "是否直选命中" in review_text
    assert "等待开奖数据更新后复盘" not in review_text
    assert events == [
        {
            "event_name": "review_viewed",
            "properties": {
                "game_key": "3d",
                "source_type": "filter",
                "review_status": "reviewed",
            },
        }
    ]
    _assert_event_payloads_are_safe(events)


def test_plan_detail_review_409_waits_without_loop(live_server_url, browser_page):
    plan = _plan_detail_payload(status="pending_review", review=None)
    review_calls = 0
    events = []

    def route_plan(route):
        nonlocal review_calls
        if route.request.method == "POST":
            review_calls += 1
            route.fulfill(
                status=409,
                content_type="application/json",
                body=json.dumps({"detail": "draw is not available"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": plan}, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1", route_plan)
    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1/review", route_plan)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )
    with browser_page.expect_response(
        f"{live_server_url}/api/plans/plan-detail-1/review"
    ) as review_response:
        browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    assert review_response.value.status == 409
    browser_page.wait_for_function(
        "() => document.querySelector('#resultFeedback').textContent.includes('开奖后可复盘')",
        timeout=5000,
    )
    browser_page.wait_for_load_state("networkidle")

    assert review_calls == 1
    assert browser_page.locator("#reviewAction").inner_text() == "开奖后可复盘"
    assert events == []


def test_plan_detail_carry_forward_is_single_flight_and_uses_server_id(
    live_server_url,
    browser_page,
):
    plan = _plan_detail_payload(status="reviewed", review=_review_payload())
    carry_calls = []
    events = []
    browser_page.route(
        f"{live_server_url}/api/plans/plan-detail-1",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": plan}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans/plan-detail-1/carry-forward",
        lambda route: (
            carry_calls.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "plan": {
                            **plan,
                            "id": "server next/id",
                            "target_issue": "2026199",
                            "target_draw_date": "2026-07-18",
                            "source_type": "carried",
                        }
                    },
                    ensure_ascii=False,
                ),
            ),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_selector("#carryForwardAction")
    browser_page.evaluate(
        """
        () => {
          document.querySelector("#carryForwardAction").click();
          document.querySelector("#carryForwardAction").click();
        }
        """
    )
    browser_page.wait_for_url("**/result.html?id=server%20next%2Fid", timeout=5000)

    assert len(carry_calls) == 1
    assert "target_issue" not in carry_calls[0]
    carried_events = [event for event in events if event.get("event_name") == "plan_carried_forward"]
    assert carried_events == [
        {
            "event_name": "plan_carried_forward",
            "properties": {
                "game_key": "3d",
                "source_type": "filter",
                "review_status": "reviewed",
            },
        }
    ]
    _assert_event_payloads_are_safe(events)


def test_plan_detail_carry_forward_navigates_when_event_request_hangs(
    live_server_url,
    browser_page,
):
    plan = _plan_detail_payload(status="reviewed", review=_review_payload())
    events = []
    hanging_event_routes = []
    browser_page.route(
        f"{live_server_url}/api/plans/plan-detail-1",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": plan}, ensure_ascii=False),
        ),
    )
    browser_page.route(
        f"{live_server_url}/api/plans/plan-detail-1/carry-forward",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "plan": {
                        **plan,
                        "id": "server next/hang",
                        "target_issue": "2026199",
                        "target_draw_date": "2026-07-18",
                        "source_type": "carried",
                    }
                },
                ensure_ascii=False,
            ),
        ),
    )

    def route_hanging_event(route):
        events.append(json.loads(route.request.post_data or "{}"))
        hanging_event_routes.append(route)

    browser_page.route(f"{live_server_url}/api/events", route_hanging_event)

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_selector("#carryForwardAction")
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_url("**/result.html?id=server%20next%2Fhang", timeout=1000)

    assert events == [
        {
            "event_name": "plan_carried_forward",
            "properties": {
                "game_key": "3d",
                "source_type": "filter",
                "review_status": "reviewed",
            },
        }
    ]
    _assert_event_payloads_are_safe(events)
    for route in hanging_event_routes:
        try:
            route.abort("failed")
        except Exception:
            pass


def test_plan_detail_carry_forward_reuses_request_id_until_success_and_resets_for_new_source(
    live_server_url,
    browser_page,
):
    plan = _plan_detail_payload(status="reviewed", review=_review_payload())
    next_plan = _plan_detail_payload(
        plan_id="server-next",
        status="reviewed",
        review=_review_payload("server-next"),
        source_type="carried",
    )
    carry_calls = []

    def route_plan(route):
        url = route.request.url
        payload = next_plan if url.endswith("/api/plans/server-next") else plan
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": payload}, ensure_ascii=False),
        )

    def route_first_carry(route):
        carry_calls.append(json.loads(route.request.post_data or "{}"))
        if len(carry_calls) == 1:
            route.abort("failed")
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": next_plan}, ensure_ascii=False),
        )

    def route_next_carry(route):
        carry_calls.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {"plan": {**next_plan, "id": "server-next-again"}},
                ensure_ascii=False,
            ),
        )

    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1", route_plan)
    browser_page.route(f"{live_server_url}/api/plans/server-next", route_plan)
    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1/carry-forward", route_first_carry)
    browser_page.route(f"{live_server_url}/api/plans/server-next/carry-forward", route_next_carry)
    browser_page.route(f"{live_server_url}/api/events", lambda route: route.fulfill(status=202, body="{}"))

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_selector("#carryForwardAction")
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#resultFeedback').textContent.includes('沿用失败')",
        timeout=5000,
    )
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_url("**/result.html?id=server-next", timeout=5000)
    browser_page.wait_for_selector("#carryForwardAction")
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_url("**/result.html?id=server-next-again", timeout=5000)

    assert len(carry_calls) == 3
    assert carry_calls[0]["request_id"]
    assert carry_calls[1]["request_id"] == carry_calls[0]["request_id"]
    assert carry_calls[2]["request_id"] != carry_calls[0]["request_id"]


def test_plan_detail_carry_forward_error_can_retry_and_delete_flows(
    live_server_url,
    browser_page,
):
    plan = _plan_detail_payload(status="reviewed", review=_review_payload())
    carry_calls = 0
    delete_calls = 0
    events = []

    def route_plan(route):
        nonlocal delete_calls
        if route.request.method == "DELETE":
            delete_calls += 1
            route.fulfill(status=204, body="")
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": plan}, ensure_ascii=False),
        )

    def route_carry(route):
        nonlocal carry_calls
        carry_calls += 1
        if carry_calls == 1:
            route.fulfill(status=503, content_type="application/json", body='{"detail":"try later"}')
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": {**plan, "id": "retry-next"}}, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1", route_plan)
    browser_page.route(f"{live_server_url}/api/plans/plan-detail-1/carry-forward", route_carry)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_selector("#carryForwardAction")
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#resultFeedback').textContent.includes('沿用失败')",
        timeout=5000,
    )
    browser_page.wait_for_timeout(150)
    assert [event for event in events if event.get("event_name") == "plan_carried_forward"] == []
    assert browser_page.locator("#carryForwardAction").is_enabled()
    browser_page.locator("#carryForwardAction").click()
    browser_page.wait_for_url("**/result.html?id=retry-next", timeout=5000)
    assert len([event for event in events if event.get("event_name") == "plan_carried_forward"]) == 1

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_selector("#deletePlanAction")
    browser_page.once("dialog", lambda dialog: dialog.accept())
    browser_page.locator("#deletePlanAction").click()
    browser_page.wait_for_url("**/analysis.html?game=3d", timeout=5000)
    assert delete_calls == 1


@pytest.mark.parametrize(
    ("target", "path", "ready_text"),
    [
        ("pending", "/result.html?id=pending-plan", "等待开奖数据更新后复盘。"),
        ("error", "/result.html?id=error-plan", "暂时无法读取方案"),
        ("empty", "/result.html", "暂无财运号详情"),
    ],
)
def test_plan_detail_disconnects_stale_review_observer_across_reinitialization(
    live_server_url,
    browser_page,
    target,
    path,
    ready_text,
):
    reviewed_plan = _plan_detail_payload(
        status="reviewed",
        review={**_review_payload(), "review_status": "direct_hit"},
    )
    pending_plan = _plan_detail_payload(plan_id="pending-plan", status="saved", review=None)
    events = []

    browser_page.add_init_script(
        """
        (() => {
          window.__reviewObserverInstances = [];
          window.IntersectionObserver = class {
            constructor(callback, options) {
              this.callback = callback;
              this.options = options;
              this.disconnected = false;
              window.__reviewObserverInstances.push(this);
            }
            observe(target) {
              this.target = target;
            }
            disconnect() {
              this.disconnected = true;
            }
          };
        })();
        """
    )

    def route_plan(route):
        if route.request.url.endswith("/api/plans/error-plan"):
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "boom"}),
            )
            return
        payload = pending_plan if route.request.url.endswith("/api/plans/pending-plan") else reviewed_plan
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"plan": payload}, ensure_ascii=False),
        )

    browser_page.route(f"{live_server_url}/api/plans/*", route_plan)
    browser_page.route(
        f"{live_server_url}/api/events",
        lambda route: (
            events.append(json.loads(route.request.post_data or "{}")),
            route.fulfill(status=202, content_type="application/json", body="{}"),
        ),
    )

    browser_page.goto(f"{live_server_url}/result.html?id=plan-detail-1")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultReview').textContent.includes('是否直选命中')",
        timeout=5000,
    )
    assert browser_page.evaluate("() => window.__reviewObserverInstances.length") == 1
    assert events == []

    browser_page.evaluate(
        """(path) => {
          history.pushState({}, "", path);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }""",
        path,
    )
    browser_page.wait_for_function(
        "(readyText) => document.body.textContent.includes(readyText)",
        arg=ready_text,
        timeout=5000,
    )

    assert browser_page.evaluate("() => window.__reviewObserverInstances[0].disconnected") is True
    browser_page.evaluate(
        """() => {
          window.__reviewObserverInstances[0].callback([{isIntersecting: true}]);
        }"""
    )
    browser_page.wait_for_load_state("networkidle")
    assert events == []

    browser_page.evaluate(
        """() => {
          history.pushState({}, "", "/result.html?id=plan-detail-1");
          window.dispatchEvent(new PopStateEvent("popstate"));
        }"""
    )
    browser_page.wait_for_function(
        "() => window.__reviewObserverInstances.length === 2",
        timeout=5000,
    )
    browser_page.evaluate(
        """() => {
          const observer = window.__reviewObserverInstances[1];
          observer.callback([{isIntersecting: true}]);
          observer.callback([{isIntersecting: true}]);
        }"""
    )
    browser_page.wait_for_function("() => window.__task13ReviewTracked === true", timeout=5000)
    browser_page.wait_for_load_state("networkidle")

    assert events == [
        {
            "event_name": "review_viewed",
            "properties": {
                "game_key": "3d",
                "source_type": "filter",
                "review_status": "reviewed",
            },
        }
    ]


def test_legacy_fortune_without_id_and_result_page_has_no_mobile_overflow(
    live_server_url,
    browser_page,
):
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.add_init_script(
        """
        localStorage.setItem("lotteryLuck.fortuneHistory.v1", JSON.stringify([
          {
            id: "legacy-first",
            game_key: "3d",
            game_label: "旧版财运",
            mode_label: "稳财号",
            source_type: "fortune",
            main_numbers: [1,2,3],
            fortune_report: {closed_loop: [{label: "玄学", value: "保留"}]},
            master_ritual: {verdict: "旧版大师起盘保留"}
          }
        ]));
        """
    )

    browser_page.goto(f"{live_server_url}/result.html")
    browser_page.wait_for_function(
        "() => document.querySelector('#resultTitle').textContent.includes('旧版财运')",
        timeout=5000,
    )

    assert "大师起盘" in browser_page.locator("body").inner_text()
    assert browser_page.locator("#workbenchAction").get_attribute("href") == "/analysis.html?game=3d"
    assert browser_page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


# The copy on every tool is read by lottery players, not by the engineers who built it. This
# locks the page against the leaks that were on it: API field names (frequency, current_omission,
# historical_percentile), internal jargon (segment, 分位, min-max, 工作台, 未分层, 样本) and raw
# API enum values (manual / draft) rendered straight into the plan strip. The honesty copy is
# asserted too, so a future "cleanup" cannot pass this test by deleting the disclaimers.
INTERNAL_TOOLBOX_COPY = [
    "frequency",
    "omission",
    "percentile",
    "segment",
    "payload",
    "workbench",
    "min-max",
    "ASCII",
    "manual",
    "draft",
    "工作台",
    "未分层",
    "分位",
    "样本",
]
MISLEADING_TOOLBOX_COPY = ["推荐", "必中", "提高中奖率"]


def test_3d_toolbox_shows_no_developer_facing_copy_on_any_tool(live_server_url, browser_page):
    _stub_3d_toolbox_shell(browser_page, live_server_url)
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d")
    browser_page.wait_for_function("() => document.querySelector('#threeDToolbox')?.hidden === false")

    toolbox = browser_page.locator("#threeDToolbox")
    seen_disclaimers = 0
    for tool_key in ["trend", "omission", "frequency", "heat", "number", "attributes", "recent"]:
        _open_3d_tool(browser_page, tool_key)
        visible_text = toolbox.inner_text()
        for internal_copy in INTERNAL_TOOLBOX_COPY:
            assert internal_copy not in visible_text, (tool_key, internal_copy)
        # 概率 may only ever appear inside an explicit negation.
        for match in re.finditer("概率", visible_text):
            lead = visible_text[max(0, match.start() - 8) : match.start()]
            assert "不代表" in lead, (tool_key, lead)
        for misleading_copy in MISLEADING_TOOLBOX_COPY:
            assert misleading_copy not in visible_text, (tool_key, misleading_copy)
        # Every tool keeps a disclaimer a user can actually see.
        assert "不代表未来" in visible_text, tool_key
        seen_disclaimers += 1
        browser_page.go_back()
        browser_page.wait_for_selector("#threeDToolHome:not([hidden])")

    assert seen_disclaimers == 7
def test_number_tools_page_exposes_all_cards_and_top_level_navigation(live_server_url, browser_page):
    page = browser_page
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.wait_for_selector("[data-tool-card]")
    assert page.locator("[data-tool-card]").count() == 7
    assert page.locator("[data-game-key]").count() == 5
    assert page.locator('[data-tool-card="quick"]').get_attribute("aria-current") == "true"
    assert page.locator('a[href="./tools.html?game=ssq&tool=quick"]', has_text="选号工具").count() == 1

    for path in ["/", "/analysis.html?game=ssq", "/strategy.html?game=ssq"]:
        page.goto(f"{live_server_url}{path}")
        assert page.locator('a[href="./tools.html?game=ssq&tool=quick"]', has_text="选号工具").count() == 1


def test_quick_pick_adds_normalized_unique_entries_to_persistent_basket(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.fill('#toolWorkbench input[name="count"]', "2")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    assert page.locator("[data-result-entry]").count() == 2
    page.click("#addAllResults")
    assert page.locator("#basketCount").inner_text() == "2"
    page.reload()
    page.wait_for_selector("#basketCount")
    assert page.locator("#basketCount").inner_text() == "2"


def test_basket_deduplicates_and_csv_has_expected_header(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    result = page.evaluate(
        """
        () => {
          localStorage.clear();
          const entry = {main:[1,2,3], special:[], text:'123'};
          LotteryTools.addEntriesToBasket('3d', [entry, entry], 'quick');
          return {
            size: LotteryTools.readBasket().games['3d'].length,
            csv: LotteryTools.formatCsv('3d', LotteryTools.readBasket().games['3d'])
          };
        }
        """
    )
    assert result["size"] == 1
    assert result["csv"].startswith("game_key,main,special,source")


def test_tools_switch_between_full_and_organize_without_hiding_cards(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=full")
    page.click('[data-number-zone="main"] [data-number="1"]')
    page.click('[data-tool-card="organize"]')
    page.wait_for_selector('textarea[name="batch_a"]')
    assert page.locator("[data-tool-card]").count() == 7
    page.fill(
        'textarea[name="batch_a"]',
        "01 02 03 04 05 06 | 07\n01 02 03 04 05 06 | 07",
    )
    page.select_option('select[name="operation"]', "dedupe")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    assert page.locator("[data-result-entry]").count() == 1


def test_tools_invalid_url_state_falls_back_to_default_keys(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=bad&tool=unknown")
    page.wait_for_selector('#toolWorkbench input[name="count"]')
    assert page.url.endswith("/tools.html?game=ssq&tool=quick")
    assert page.locator('[data-tool-card="quick"]').get_attribute("aria-current") == "true"


def test_tools_ignores_old_response_after_switching_games(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    held_requests = []
    page.route(
        f"{live_server_url}/api/tools/ssq/quick-pick",
        lambda route: held_requests.append(route),
    )
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_timeout(100)
    assert held_requests
    page.click('[data-game-key="dlt"]')
    held_requests[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "entries": [{"main": [1, 2, 3, 4, 5, 6], "special": [7], "text": "old ssq"}],
                "ticket_count": 1,
                "total_cost": 2,
            }
        ),
    )
    page.wait_for_timeout(100)
    assert page.locator("[data-result-entry]").count() == 0
    assert page.locator("#toolResult").inner_text().find("old ssq") == -1
    assert page.evaluate("() => LotteryTools.readBasket().games.dlt.length") == 0


def test_tools_success_result_replaces_initial_empty_copy(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    assert page.locator("#toolResult .tool-empty").count() == 0


def test_basket_quota_fallback_keeps_entries_and_shows_warning(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    result = page.evaluate(
        """
        () => {
          localStorage.clear();
          Storage.prototype.setItem = () => { throw new DOMException('full', 'QuotaExceededError'); };
          LotteryTools.addEntriesToBasket('3d', [{main:[1,2,3], text:'123'}], 'quick');
          return LotteryTools.readBasket().games['3d'].length;
        }
        """
    )
    assert result == 1
    assert page.locator("#basketWarning").is_visible()


def test_copy_rejection_uses_exec_command_fallback(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("#copyResults")
    page.evaluate(
        """
        () => {
          Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: {writeText: () => Promise.reject(new Error('blocked'))}
          });
          document.execCommand = (command) => {
            window.__copyFallbackCommand = command;
            return true;
          };
        }
        """
    )
    page.click("#copyResults")
    page.wait_for_function("() => window.__copyFallbackCommand === 'copy'")
    assert "已复制" in page.locator("#toolStatus").inner_text()


def test_digit_basket_and_csv_keep_repeated_ordered_digits_and_group_type(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    result = page.evaluate(
        """
        () => {
          localStorage.clear();
          LotteryTools.addEntriesToBasket('3d', [
            {main:[1,1,2], special:[], text:'112', play_type:'straight'},
            {main:[1,2,2], special:[], text:'122', play_type:'straight'},
            {main:[1,2], special:[], text:'1 2 · 组三', play_type:'group3'}
          ], 'compose');
          const entries = LotteryTools.readBasket().games['3d'];
          return { entries, csv: LotteryTools.formatCsv('3d', entries) };
        }
        """
    )

    assert [entry["text"] for entry in result["entries"]] == ["112", "122", "1 2 · 组三"]
    assert "112" in result["csv"] and "122" in result["csv"]
    assert "group3" in result["csv"]


def test_tools_show_live_cost_default_count_and_result_operations(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    assert page.locator('#toolWorkbench input[name="count"]').input_value() == "5"
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    assert page.locator("[data-result-entry]").count() == 5
    assert page.locator("[data-copy-result]").count() == 5
    assert page.locator("[data-replace-result]").count() == 5
    page.click("#clearResults")
    assert page.locator("[data-result-entry]").count() == 0

    page.click('[data-tool-card="full"]')
    for number in range(1, 7):
        page.click(f'[data-number-zone="main"] [data-number="{number}"]')
    page.click('[data-number-zone="special"] [data-number="1"]')
    assert "2 元，共 1 注" in page.locator("#costSummary").inner_text()


def test_tools_reduce_can_use_latest_full_result_and_switches_digit_group_label(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=full")
    for number in range(1, 8):
        page.click(f'[data-number-zone="main"] [data-number="{number}"]')
    page.click('[data-number-zone="special"] [data-number="1"]')
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    page.click('[data-tool-card="reduce"]')
    assert page.locator('input[name="reduce_source"][value="current"]').is_checked()

    page.click('[data-game-key="3d"]')
    assert page.locator('[data-tool-card="dantuo"] strong').inner_text() == "组选包号"
    assert "已切换规则" in page.locator("#toolStatus").inner_text()


def test_copy_failure_cleans_temporary_textarea_and_gives_manual_instruction(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("#copyResults")
    page.evaluate(
        """
        () => {
          Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: {writeText: () => Promise.reject(new Error('blocked'))}
          });
          document.execCommand = () => { throw new Error('blocked'); };
        }
        """
    )
    page.click("#copyResults")
    page.wait_for_function("() => document.querySelector('#toolStatus').textContent.includes('请手动复制')")
    assert page.locator('textarea[data-copy-fallback]').count() == 0


def test_tools_basket_cap_copy_all_and_organizer_csv_download(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    size = page.evaluate(
        """
        () => {
          localStorage.clear();
          const entries = Array.from({length: 501}, (_, value) => {
            const text = String(value).padStart(3, '0');
            return {main: [...text].map(Number), special: [], text, play_type: 'straight'};
          });
          LotteryTools.addEntriesToBasket('3d', entries, 'quick');
          return LotteryTools.readBasket().games['3d'].length;
        }
        """
    )
    assert size == 500
    assert "500" in page.locator("#basketWarning").inner_text()
    page.evaluate(
        """
        () => Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: {writeText: (text) => { window.__basketCopy = text; return Promise.resolve(); }}
        })
        """
    )
    page.click("#copyBasket")
    page.wait_for_function("() => window.__basketCopy?.includes('000')")

    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=organize")
    page.fill('textarea[name="batch_a"]', "01 02 03 04 05 06 | 07")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("#downloadResults")
    with page.expect_download() as download_info:
        page.click("#downloadResults")
    assert download_info.value.suggested_filename == "ssq-organized-numbers.csv"


def test_replace_quick_result_does_not_render_after_switching_game(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    held = []

    def hold_replacement(route):
        if '"count":1' in (route.request.post_data or ""):
            held.append(route)
        else:
            route.continue_()

    page.route(f"{live_server_url}/api/tools/ssq/quick-pick", hold_replacement)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-replace-result]")
    page.click('[data-replace-result="0"]')
    page.wait_for_timeout(100)
    assert held
    page.click('[data-game-key="dlt"]')
    held[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "entries": [{"main": [1, 2, 3, 4, 5, 6], "special": [7], "text": "stale replacement"}],
            "ticket_count": 1,
            "total_cost": 2,
        }),
    )
    page.wait_for_timeout(100)
    assert "stale replacement" not in page.locator("#toolResult").inner_text()
    assert page.locator("[data-result-entry]").count() == 0


def test_replace_quick_result_does_not_render_after_clearing_results(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    held = []

    def hold_replacement(route):
        if '"count":1' in (route.request.post_data or ""):
            held.append(route)
        else:
            route.continue_()

    page.route(f"{live_server_url}/api/tools/ssq/quick-pick", hold_replacement)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=quick")
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-replace-result]")
    page.click('[data-replace-result="0"]')
    page.wait_for_timeout(100)
    assert held
    page.click("#clearResults")
    held[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "entries": [{"main": [1, 2, 3, 4, 5, 6], "special": [7], "text": "stale replacement"}],
            "ticket_count": 1,
            "total_cost": 2,
        }),
    )
    page.wait_for_timeout(100)
    assert "stale replacement" not in page.locator("#toolResult").inner_text()
    assert page.locator("[data-result-entry]").count() == 0


def test_truncated_compose_can_reduce_and_shows_distribution_metadata(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(12000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=full")
    for number in range(1, 16):
        page.click(f'[data-number-zone="main"] [data-number="{number}"]')
    page.click('[data-number-zone="special"] [data-number="1"]')
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_function("() => document.querySelector('#toolResult').innerText.includes('5005')")
    page.click('[data-tool-card="reduce"]')
    page.wait_for_selector('input[name="reduce_source"][value="current"]')
    assert "5005" in page.locator("#toolWorkbench").inner_text()
    page.fill('input[name="budget"]', "20")
    assert "10 注" in page.locator("#liveCostSummary").inner_text()
    page.click('#toolWorkbench button[type="submit"]')
    page.wait_for_selector("[data-result-entry]")
    assert page.locator("[data-result-entry]").count() == 10
    result_text = page.locator("#toolResult").inner_text()
    assert "原始组合：5005 注" in result_text
    assert "覆盖分布" in result_text
    assert "不提高中奖概率" in result_text


def test_reduce_empty_source_previews_zero_and_organizer_csv_marks_organize(
    live_server_url, browser_page
):
    page = browser_page
    page.set_default_timeout(8000)
    page.goto(f"{live_server_url}/tools.html?game=ssq&tool=reduce")
    assert "0 元，共 0 注" in page.locator("#liveCostSummary").inner_text()
    csv = page.evaluate(
        """
        () => LotteryTools.formatCsv('ssq', [
          {main:[1,2,3,4,5,6], special:[7], text:'01 02 03 04 05 06 | 07'}
        ], 'organize')
        """
    )
    assert ",organize," in csv


def test_mobile_basket_shows_entry_count_and_actual_saved_cost(live_server_url, browser_page):
    page = browser_page
    page.set_default_timeout(8000)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{live_server_url}/tools.html?game=dlt&tool=quick")
    page.evaluate(
        """
        () => {
          localStorage.clear();
          LotteryTools.addEntriesToBasket(
            'dlt',
            [{main:[1,2,3,4,5], special:[1,2], text:'01 02 03 04 05 | 01 02'}],
            'compose',
            {entry_cost: 3, multiplier: 2}
          );
        }
        """
    )
    assert page.locator("[data-basket-count]").inner_text() == "1"
    assert page.locator("#mobileBasketCost").inner_text() == "6 元"


def test_tools_render_game_specific_capabilities_and_conditional_card(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/tools.html?game=3d&tool=conditional")
    browser_page.wait_for_selector('[data-tool-card="conditional"]')
    assert browser_page.locator('[data-tool-card="conditional"] strong').inner_text() == "条件缩水"
    assert browser_page.locator('[data-tool-card="dantuo"] strong').inner_text() == "组选包号"
    assert browser_page.locator("#conditionalDigitFields").is_visible()


def test_tools_consume_valid_strategy_handoff_once(live_server_url, browser_page):
    browser_page.add_init_script("""
      sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify({
        version: 1, created_at: Date.now(), game_key: "ssq", source: "strategy",
        preset: "balanced", name: "均衡型", window: 120,
        conditions: {odd_even: "3:3", sum_min: 80, sum_max: 130}
      }));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=ssq&tool=conditional&source=strategy")
    browser_page.wait_for_selector("#conditionalSource")
    assert "来源：均衡型" in browser_page.locator("#conditionalSource").inner_text()
    assert browser_page.locator('[name="sum_min"]').input_value() == "80"
    assert browser_page.evaluate("() => sessionStorage.getItem('lottery_research_handoff_v1')") is None


def test_old_number_pool_migrates_idempotently_without_deletion(live_server_url, browser_page):
    browser_page.add_init_script("""
      localStorage.setItem("lotteryLuck:numberPool:3d", JSON.stringify([
        {main: [1, 1, 2], special: []}, {main: [1, 2, 2], special: []}
      ]));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    browser_page.wait_for_function("() => document.querySelector('[data-basket-count]').textContent === '2'")
    browser_page.reload()
    browser_page.wait_for_function("() => document.querySelector('[data-basket-count]').textContent === '2'")
    assert browser_page.evaluate("() => localStorage.getItem('lotteryLuck:numberPool:3d')") is not None


def test_expired_or_cross_game_handoff_is_rejected_with_visible_message(live_server_url, browser_page):
    browser_page.add_init_script("""
      sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify({
        version: 1, created_at: Date.now() - 1800001, game_key: "dlt", source: "strategy", conditions: {}
      }));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=ssq&tool=conditional&source=strategy")
    assert "策略条件未能带入" in browser_page.locator("#toolStatus").inner_text()


@pytest.mark.parametrize(
    "handoff",
    [
        {"preset": "unknown", "window": 120, "conditions": {}},
        {"preset": "balanced", "window": "120", "conditions": {}},
        {"preset": "balanced", "window": 120, "conditions": {"unknown_rule": 1}},
        {"preset": "balanced", "window": 120, "conditions": {"sum_min": "80"}},
    ],
)
def test_tools_rejects_malformed_strategy_handoff_schema(live_server_url, browser_page, handoff):
    browser_page.add_init_script(
        """
        sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify({
          version: 1, created_at: Date.now(), game_key: "ssq", source: "strategy", ...%s
        }));
        """ % json.dumps(handoff),
    )
    browser_page.goto(f"{live_server_url}/tools.html?game=ssq&tool=conditional&source=strategy")
    assert "策略条件未能带入" in browser_page.locator("#toolStatus").inner_text()
    assert browser_page.locator("#conditionalSource").is_hidden()
    assert "条件已预填" not in browser_page.locator("#toolWorkbench").inner_text()


def test_research_data_url_is_canonical_and_invalid_route_notice_survives_game_load(
    live_server_url, browser_page
):
    browser_page.goto(f"{live_server_url}/analysis.html?game=invalid&view=invalid&window=60")
    browser_page.wait_for_selector("#researchDataView:not([hidden])")
    assert browser_page.evaluate("() => window.location.search") == "?game=ssq&view=data&window=60"
    assert "已回到" in browser_page.locator("#apiStatus").inner_text()

    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&view=data&window=60")
    browser_page.wait_for_selector("#threeDToolbox:not([hidden])")
    assert browser_page.evaluate("() => window.location.search") == "?game=3d&view=data&window=60"


def test_research_game_switch_keeps_reset_feedback_until_the_next_user_action(
    live_server_url, browser_page
):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector("#strategyForm")
    browser_page.locator('[data-game="dlt"]').click()
    browser_page.wait_for_function(
        "() => document.querySelector('#strategyStatus').textContent.includes('已按新彩种规则重置')"
    )


def test_research_center_data_view_uses_the_research_center_heading(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=data")
    assert browser_page.locator("#analysisWorkbench h1").inner_text() == "研究中心"


def test_public_navigation_has_research_and_tools_without_strategy_entry(live_server_url, browser_page):
    for path in ["/", "/analysis.html?game=ssq&view=data", "/tools.html?game=ssq", "/privacy.html", "/result.html"]:
        browser_page.goto(f"{live_server_url}{path}")
        nav = browser_page.locator(".header-nav")
        assert nav.get_by_role("link", name="研究中心").count() == 1
        assert nav.get_by_role("link", name="选号工具").count() == 1
        assert nav.get_by_role("link", name="策略实验室").count() == 0
