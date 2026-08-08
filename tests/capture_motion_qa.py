import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BASE_URL = "http://127.0.0.1:8017/"
EXPECTED_NUMBERS = ["03", "08", "16", "21", "27", "32", "09"]

NUMBER_RULES = {
    "ssq": {
        "main_count": 6,
        "main_min": 1,
        "main_max": 33,
        "special_count": 1,
        "special_min": 1,
        "special_max": 16,
        "allow_repeat": False,
        "special_distinct_from_main": False,
    },
    "dlt": {
        "main_count": 5,
        "main_min": 1,
        "main_max": 35,
        "special_count": 2,
        "special_min": 1,
        "special_max": 12,
        "allow_repeat": False,
        "special_distinct_from_main": False,
    },
    "3d": {
        "main_count": 3,
        "main_min": 0,
        "main_max": 9,
        "special_count": 0,
        "special_min": None,
        "special_max": None,
        "allow_repeat": True,
        "special_distinct_from_main": False,
    },
    "pl3": {
        "main_count": 3,
        "main_min": 0,
        "main_max": 9,
        "special_count": 0,
        "special_min": None,
        "special_max": None,
        "allow_repeat": True,
        "special_distinct_from_main": False,
    },
    "kl8": {
        "main_count": 10,
        "main_min": 1,
        "main_max": 80,
        "special_count": 0,
        "special_min": None,
        "special_max": None,
        "allow_repeat": False,
        "special_distinct_from_main": False,
    },
}

GAMES_PAYLOAD = {
    "games": [
        {
            "game_key": "ssq",
            "game_name": "双色球",
            "draw_count": 3430,
            "latest_date": "2026-07-10",
            "latest_issue": "2026070",
            "number_rule": NUMBER_RULES["ssq"],
        },
        {
            "game_key": "dlt",
            "game_name": "大乐透",
            "draw_count": 1800,
            "latest_date": "2026-07-09",
            "latest_issue": "2026071",
            "number_rule": NUMBER_RULES["dlt"],
        },
        {
            "game_key": "3d",
            "game_name": "福彩3D",
            "draw_count": 6900,
            "latest_date": "2026-07-10",
            "latest_issue": "2026180",
            "number_rule": NUMBER_RULES["3d"],
        },
        {
            "game_key": "pl3",
            "game_name": "排列3",
            "draw_count": 5400,
            "latest_date": "2026-07-10",
            "latest_issue": "2026180",
            "number_rule": NUMBER_RULES["pl3"],
        },
        {
            "game_key": "kl8",
            "game_name": "快乐8",
            "draw_count": 1600,
            "latest_date": "2026-07-10",
            "latest_issue": "2026180",
            "number_rule": NUMBER_RULES["kl8"],
        },
    ]
}

QUOTA_PAYLOAD = {
    "tracked": True,
    "remaining_total": 5,
    "is_paid": False,
    "is_member": False,
    "config": {"allow_demo_after_exhausted": True},
}

PREDICTION_PAYLOAD = {
    "game_key": "ssq",
    "best_draw_date": "2026-07-16",
    "luck_score": 88.4,
    "numbers": {"main": [3, 8, 16, 21, 27, 32], "special": [9]},
    "history_basis": {
        "draw_count": 3430,
        "hot_main": [3, 8, 16, 21, 27, 32],
        "cold_main": [1, 5, 13, 22],
    },
    "quota": {
        "tracked": True,
        "remaining_total": 4,
        "is_paid": False,
        "is_member": False,
    },
    "daily_fortune_sign": {
        "headline": "QA fixed fortune sign for the cinematic workflow.",
        "direction": "East",
        "lucky_hour": "Chen",
        "lucky_tails": ["3", "8", "9"],
        "avoid_tails": ["4"],
        "tags": ["Fixed payload", "No DB state", "QA capture"],
    },
    "ritual_steps": [
        {
            "key": "wealth_pattern",
            "label": "定本命财盘",
            "summary": "QA locks the personal base.",
        },
        {
            "key": "fortune_direction",
            "label": "定今日财局",
            "summary": "QA fixes the draw-day context.",
        },
        {
            "key": "fortune_eye",
            "label": "取财眼尾数",
            "summary": "QA selects the final tail.",
        },
        {
            "key": "avoid_clash",
            "label": "避冲煞号",
            "summary": "QA keeps excluded numbers out.",
        },
        {
            "key": "final_numbers",
            "label": "落财运号",
            "summary": "QA returns the fixed payload.",
        },
    ],
    "metaphysics_profile": {
        "wealth_pattern": "QA wealth pattern",
        "reading": "Fixed reading for repeatable screenshots.",
        "selection_rule": "Use deterministic QA numbers.",
        "day_advice": "Keep the capture stable.",
        "favorable_element_labels": "Gold / Water",
    },
    "fortune_hook": {
        "headline": "QA cinematic fortune payload",
        "subline": "Fixed response used only by the screenshot harness.",
        "tags": ["Repeatable", "Controlled", "Visual QA"],
    },
    "master_ritual": {
        "opening": "QA opening for the deterministic cinematic capture.",
        "verdict": "QA verdict: fixed numbers are ready.",
        "tail_map": {
            "favorable": [{"tail": 3, "element_label": "Gold"}],
            "avoid": [{"tail": 4, "element_label": "Fire"}],
            "legend": "QA fixed tail map.",
        },
        "steps": [
            {
                "label": "Base",
                "value": "Locked",
                "detail": "The browser harness controls the API response.",
            },
            {
                "label": "Numbers",
                "value": "03 08 16 21 27 32 09",
                "detail": "Matches EXPECTED_NUMBERS.",
            },
        ],
    },
    "credibility_chain": [
        {
            "title": "Payload",
            "text": "Deterministic response",
            "detail": "Independent from local SQLite quota state.",
        }
    ],
    "interpretation_layers": {
        "short_hook": "Fixed QA hook.",
        "long_reading": "The evidence screenshots use this stable browser payload.",
    },
    "recent_draws": [
        {
            "issue": "2026070",
            "draw_date": "2026-07-10",
            "red_numbers": "01,04,09,14,20,31",
            "blue_number": "06",
        }
    ],
    "disclaimer": "For deterministic QA evidence only.",
}


def json_script_payload(value):
    return json.dumps(value, ensure_ascii=False)


def assert_no_overflow(page):
    overflow = page.evaluate(
        """
        () => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
        })
        """
    )
    assert overflow["scrollWidth"] <= overflow["innerWidth"] + 1, overflow


def assert_no_visible_overlap(page, selectors):
    overlaps = page.evaluate(
        """
        (selectors) => {
          const rects = [];
          for (const selector of selectors) {
            document.querySelectorAll(selector).forEach((node, index) => {
              const style = getComputedStyle(node);
              const rect = node.getBoundingClientRect();
              if (
                style.display === "none" ||
                style.visibility === "hidden" ||
                Number(style.opacity) === 0 ||
                rect.width <= 0 ||
                rect.height <= 0
              ) {
                return;
              }
              rects.push({
                label: `${selector}[${index}]`,
                left: rect.left,
                right: rect.right,
                top: rect.top,
                bottom: rect.bottom,
              });
            });
          }

          const hits = [];
          for (let i = 0; i < rects.length; i += 1) {
            for (let j = i + 1; j < rects.length; j += 1) {
              const a = rects[i];
              const b = rects[j];
              const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (x > 1 && y > 1) {
                hits.push([a.label, b.label, Math.round(x), Math.round(y)]);
              }
            }
          }
          return hits;
        }
        """,
        selectors,
    )
    assert overlaps == [], overlaps


def assert_form_default_state(page):
    state = page.evaluate(
        """
        () => {
          const stage = document.querySelector("#ritualStage");
          const style = getComputedStyle(stage);
          const panelStyle = getComputedStyle(document.querySelector("#predictForm"));
          const selectors = [
            'input[name="name"]',
            'input[name="birth_date"]',
            'input[name="birth_place"]',
            'input[name="current_city"]',
            '#submitButton',
          ];
          return {
            motionState: stage.dataset.motionState,
            ariaHidden: stage.getAttribute("aria-hidden"),
            visibility: style.visibility,
            opacity: style.opacity,
            panelOpacity: panelStyle.opacity,
            values: {
              name: document.querySelector('input[name="name"]').value,
              birth_date: document.querySelector('input[name="birth_date"]').value,
              birth_place: document.querySelector('input[name="birth_place"]').value,
              current_city: document.querySelector('input[name="current_city"]').value,
              birth_hour: document.querySelector('input[name="birth_hour"]').value,
            },
            required: {
              name: document.querySelector('input[name="name"]').required,
              birth_date: document.querySelector('input[name="birth_date"]').required,
              birth_place: document.querySelector('input[name="birth_place"]').required,
              current_city: document.querySelector('input[name="current_city"]').required,
            },
            controls: selectors.map((selector) => {
              const node = document.querySelector(selector);
              const rect = node.getBoundingClientRect();
              return {
                selector,
                visible: rect.width > 0 && rect.height > 0,
                inViewport:
                  rect.bottom > 0 &&
                  rect.right > 0 &&
                  rect.top < window.innerHeight &&
                  rect.left < window.innerWidth,
              };
            }),
          };
        }
        """
    )
    assert state["motionState"] == "idle", state
    assert state["ariaHidden"] == "true", state
    assert state["visibility"] == "hidden", state
    assert float(state["opacity"]) == 0, state
    assert float(state["panelOpacity"]) == 1, state
    assert state["values"] == {
        "name": "",
        "birth_date": "",
        "birth_place": "",
        "current_city": "",
        "birth_hour": "",
    }, state
    assert all(state["required"].values()), state
    assert all(item["visible"] and item["inViewport"] for item in state["controls"]), state
    assert_no_visible_overlap(
        page,
        [
            "#predictForm > label",
            "#predictForm > fieldset",
            "#quotaStatus",
            "#submitButton",
            "#generateFeedback",
        ],
    )


def fill_required_form(page):
    page.locator('input[name="name"]').fill("视觉QA用户")
    page.locator('input[name="birth_date"]').fill("1990-01-01")
    page.locator('input[name="birth_place"]').fill("杭州")
    page.locator('input[name="current_city"]').fill("上海")
    page.locator('[data-select-name="birth_hour"] .custom-select-trigger').click()
    page.locator(
        '[data-select-name="birth_hour"] .custom-select-option[data-value="辰"]'
    ).click()
    state = page.evaluate(
        """
        () => ({
          name: document.querySelector('input[name="name"]').value,
          birth_date: document.querySelector('input[name="birth_date"]').value,
          birth_place: document.querySelector('input[name="birth_place"]').value,
          current_city: document.querySelector('input[name="current_city"]').value,
          birth_hour: document.querySelector('input[name="birth_hour"]').value,
          birthHourExpanded: document
            .querySelector('[data-select-name="birth_hour"] .custom-select-trigger')
            .getAttribute("aria-expanded"),
        })
        """
    )
    assert state == {
        "name": "视觉QA用户",
        "birth_date": "1990-01-01",
        "birth_place": "杭州",
        "current_city": "上海",
        "birth_hour": "辰",
        "birthHourExpanded": "false",
    }, state


def assert_stage_layout(page):
    assert_no_visible_overlap(
        page,
        [
            "#motionStatus",
            "#motionTitle",
            ".ritual-stage-progress",
            "#motionSteps",
            "#motionNumbers",
        ],
    )


def assert_mobile_steps(page):
    result = page.evaluate(
        """
        () => Array.from(document.querySelectorAll("#motionSteps li")).map((node) => {
          const rect = node.getBoundingClientRect();
          const label = node.textContent.trim();
          return {
            label,
            left: rect.left,
            right: rect.right,
            width: rect.width,
            height: rect.height,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
          };
        })
        """
    )
    assert len(result) == 5, result
    for item in result:
        assert item["label"], result
        assert item["width"] > 0 and item["height"] > 0, result
        assert item["left"] >= -1 and item["right"] <= 391, result
        assert item["scrollWidth"] <= item["clientWidth"] + 1, result


def assert_motion_numbers(page):
    actual = page.locator("#motionNumbers .motion-ball").evaluate_all(
        "nodes => nodes.map((node) => node.textContent)"
    )
    assert actual == EXPECTED_NUMBERS, actual


def assert_final_numbers(page):
    expected = " ".join(EXPECTED_NUMBERS)
    page.wait_for_function(
        """
        (expected) => document.querySelector("#fortuneNumber").textContent === expected
        """,
        arg=expected,
        timeout=6000,
    )
    actual = page.locator("#numberBalls .ball").evaluate_all(
        "nodes => nodes.map((node) => node.textContent)"
    )
    assert actual == EXPECTED_NUMBERS, actual
    records = page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert len(records) == 1, records
    assert records[0]["number_text"] == expected, records


def install_api_controls(page):
    page.add_init_script(
        f"""
        (() => {{
          const gamesPayload = {json_script_payload(GAMES_PAYLOAD)};
          const quotaPayload = {json_script_payload(QUOTA_PAYLOAD)};
          const predictionPayload = {json_script_payload(PREDICTION_PAYLOAD)};
          const originalFetch = window.fetch.bind(window);

          window.__qaControlsReady = true;
          window.__qaPredictRequestBodies = [];
          window.__qaPredictResolvedCount = 0;
          window.__qaPredictResolvers = [];
          window.__qaReleasePrediction = () => {{
            const resolvers = window.__qaPredictResolvers.splice(0);
            resolvers.forEach((resolve) => resolve());
          }};

          localStorage.removeItem("lotteryLuck.fortuneHistory.v1");
          localStorage.setItem("lotteryLuck.clientId.v1", "motion-qa-client");

          const response = (payload) => new Response(JSON.stringify(payload), {{
            status: 200,
            headers: {{"Content-Type": "application/json"}},
          }});

          window.fetch = (input, init = {{}}) => {{
            const url = typeof input === "string" ? input : input?.url || "";
            if (url.includes("/api/games")) return Promise.resolve(response(gamesPayload));
            if (url.includes("/api/quota/status")) return Promise.resolve(response(quotaPayload));
            if (url.includes("/api/predict")) {{
              try {{
                window.__qaPredictRequestBodies.push(JSON.parse(init.body || "{{}}"));
              }} catch (error) {{
                window.__qaPredictRequestBodies.push({{}});
              }}
              return new Promise((resolve) => {{
                window.__qaPredictResolvers.push(() => {{
                  window.__qaPredictResolvedCount += 1;
                  resolve(response(predictionPayload));
                }});
              }});
            }}
            if (url.includes("/api/review/")) {{
              return Promise.resolve(response({{
                status: "pending",
                summary: "QA review is stubbed for deterministic screenshots.",
              }}));
            }}
            if (url.includes("/api/cloud/fortune-records")) {{
              const body = JSON.parse(init.body || "{{}}");
              return Promise.resolve(response({{record: body.record}}));
            }}
            return originalFetch(input, init);
          }};
        }})();
        """
    )


def new_controlled_page(context):
    page = context.new_page()
    install_api_controls(page)
    return page


def ready(page):
    page.goto(BASE_URL)
    page.wait_for_function("() => window.__qaControlsReady === true")
    page.wait_for_function(
        """
        () => document.querySelectorAll("#gameTabs button").length === 5
          && document.querySelector("#quotaStatus").textContent.includes("今日剩余 5 次")
          && !document.querySelector("#submitButton").disabled
        """,
        timeout=5000,
    )
    page.wait_for_function(
        """
        () => !document.body.classList.contains("is-page-entering")
          && Number(getComputedStyle(document.querySelector(".site-header")).opacity) === 1
          && Number(getComputedStyle(document.querySelector(".game-tabs")).opacity) === 1
          && Number(getComputedStyle(document.querySelector(".oracle-board")).opacity) === 1
          && Number(getComputedStyle(document.querySelector("#predictForm")).opacity) === 1
        """,
        timeout=5000,
    )
    assert_no_overflow(page)


def release_prediction(page):
    page.wait_for_function("() => window.__qaPredictResolvers.length > 0")
    page.evaluate("() => window.__qaReleasePrediction()")


def wait_for_complete_stage(page):
    page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=10000,
    )
    page.wait_for_function(
        "() => document.querySelectorAll('#motionNumbers .motion-ball').length === 7",
        timeout=1000,
    )
    page.wait_for_timeout(1050)
    assert_motion_numbers(page)
    assert_stage_layout(page)
    assert_no_overflow(page)


def capture_desktop(browser):
    context = browser.new_context(viewport={"width": 1576, "height": 1118})
    page = new_controlled_page(context)
    ready(page)
    assert_form_default_state(page)
    page.screenshot(path=ARTIFACTS / "cinematic-home-idle.png")

    fill_required_form(page)
    page.locator("#submitButton").click()
    page.wait_for_function(
        """
        () => ['running', 'waiting'].includes(
          document.querySelector('#ritualStage').dataset.motionState
        )
        """
    )
    page.wait_for_timeout(650)
    assert page.evaluate("() => window.__qaPredictResolvedCount") == 0
    assert page.locator("#motionNumbers .motion-ball").count() == 0
    assert page.locator("#numberBalls .ball").count() == 0
    assert_stage_layout(page)
    page.screenshot(path=ARTIFACTS / "cinematic-home-running.png")

    release_prediction(page)
    wait_for_complete_stage(page)
    page.screenshot(path=ARTIFACTS / "cinematic-home-complete.png")
    assert_final_numbers(page)
    assert_no_overflow(page)
    context.close()


def capture_mobile(browser):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = new_controlled_page(context)
    ready(page)
    fill_required_form(page)
    page.locator("#submitButton").click()
    release_prediction(page)
    wait_for_complete_stage(page)
    assert_mobile_steps(page)
    page.screenshot(path=ARTIFACTS / "cinematic-home-mobile.png")
    assert_final_numbers(page)
    assert_no_overflow(page)
    context.close()


def capture_reduced_motion(browser):
    context = browser.new_context(
        viewport={"width": 1576, "height": 1118},
        reduced_motion="reduce",
    )
    page = new_controlled_page(context)
    ready(page)
    fill_required_form(page)
    page.locator("#submitButton").click()
    release_prediction(page)
    assert_final_numbers(page)
    page.screenshot(path=ARTIFACTS / "cinematic-home-reduced-motion.png")
    assert_no_overflow(page)
    context.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        capture_desktop(browser)
        capture_mobile(browser)
        capture_reduced_motion(browser)
        browser.close()


if __name__ == "__main__":
    main()
