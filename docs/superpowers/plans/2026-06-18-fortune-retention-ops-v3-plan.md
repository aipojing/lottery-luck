# Fortune Retention Ops V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next product loop for lottery fortune recommendation: result detail and sharing, deeper metaphysics credibility, and minimum viable crawler operations.

**Architecture:** Keep number generation local and deterministic inside `PredictionEngine`; add richer report payloads that the frontend can persist in localStorage. Keep user retention client-side for now, while backend operations use SQLite-backed task records and FastAPI admin endpoints. Avoid login/cloud sync in this batch so the product can keep moving without account-system risk.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite, vanilla HTML/CSS/JavaScript, localStorage, Canvas API for share poster generation.

---

### Task 1: Prediction Report Payload

**Files:**
- Modify: `lottery_luck/predictor.py`
- Test: `tests/test_predictor.py`

- [x] **Step 1: Write the failing test**

Add a test asserting every prediction includes `fortune_report` with a closed explanation loop:

```python
def test_prediction_includes_fortune_report_closed_loop():
    payload = PredictionEngine(EmptyRepo(), FakeAiProvider()).predict(
        "ssq", _personal(), today="2026-06-16", fortune_mode="windfall"
    )

    report = payload["fortune_report"]
    assert report["mode_label"] == "偏财号"
    assert report["closed_loop"][0]["label"] == "个人信息"
    assert report["closed_loop"][-1]["label"] == "号码组合"
    assert "喜用" in report["tail_digit_map"]["summary"]
    assert report["fortune_eye"]["number"] == payload["numbers"]["special"][-1]
    assert report["daily_calendar"]
    assert report["daily_calendar"][0]["draw_date"] == payload["best_draw_date"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py::test_prediction_includes_fortune_report_closed_loop -q`

Expected: FAIL because `fortune_report` does not exist.

- [x] **Step 3: Implement minimal report builder**

Add `_fortune_report(...)`, `_tail_digit_map(...)`, `_fortune_eye(...)`, and `_daily_calendar(...)` helpers in `lottery_luck/predictor.py`; attach `fortune_report` to the prediction response. The report must reuse already computed `metaphysics_profile`, `mode_profile`, `main_numbers`, `special_numbers`, and `number_reasons`.

- [x] **Step 4: Run predictor tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add lottery_luck/predictor.py tests/test_predictor.py docs/superpowers/plans/2026-06-18-fortune-retention-ops-v3-plan.md
git commit -m "feat: add fortune report payload"
```

### Task 2: Result Detail And Share Poster Shell

**Files:**
- Create: `web/result.html`
- Create: `web/result.js`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Test: `tests/test_api.py`

- [x] **Step 1: Write the failing tests**

Add API/static asset tests:

```python
def test_result_page_serves_fortune_detail_shell():
    response = client.get("/result.html")

    assert response.status_code == 200
    assert "财运号详情" in response.text
    assert 'id="resultDetail"' in response.text
    assert 'id="posterCanvas"' in response.text
    assert "./result.js" in response.text


def test_result_frontend_asset_is_served():
    response = client.get("/result.js")

    assert response.status_code == 200
    assert "FORTUNE_HISTORY_KEY" in response.text
    assert "renderResultDetail" in response.text
    assert "drawSharePoster" in response.text
```

- [x] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_result_page_serves_fortune_detail_shell tests/test_api.py::test_result_frontend_asset_is_served -q`

Expected: FAIL because `result.html` and `result.js` do not exist.

- [x] **Step 3: Implement result page**

Create `result.html` with a black-gold detail layout, record summary, closed-loop explanation, number reasons, review status, and a share poster canvas. Create `result.js` that reads `?id=...` from localStorage history and renders the detail; if no id is found, it falls back to the latest record.

- [x] **Step 4: Link records from homepage history**

Update `saveFortuneHistory` to persist `fortune_report`, `credibility_chain`, `number_reasons`, `interpretation_layers`, `avoid_numbers`, and `metaphysics_profile`. Update `renderFortuneHistory` to include a “查看详情” link to `result.html?id=<record.id>`.

- [x] **Step 5: Run tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add web/result.html web/result.js web/app.js web/styles.css tests/test_api.py
git commit -m "feat: add fortune result detail page"
```

### Task 3: Profile Book And Daily Fortune Calendar

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Test: `tests/test_api.py`

- [x] **Step 1: Write failing static shell assertions**

Extend `test_root_serves_frontend_shell`:

```python
assert 'id="profileBook"' in response.text
assert 'id="dailyFortuneCalendar"' in response.text
assert "我的财运档案" in response.text
assert "每日财运日历" in response.text
```

Extend `test_frontend_assets_are_served`:

```python
assert "renderProfileBook" in response.text
assert "renderDailyFortuneCalendar" in response.text
```

- [x] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_root_serves_frontend_shell tests/test_api.py::test_frontend_assets_are_served -q`

Expected: FAIL because the new sections/functions do not exist.

- [x] **Step 3: Implement client-side profile and calendar**

Add a compact profile section summarizing most-used game, dominant wealth pattern, latest mode, total saved records, and latest review result. Add a daily fortune calendar derived from the latest record’s `fortune_report.daily_calendar`, with “最佳开奖日” highlighted.

- [x] **Step 4: Run tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add web/index.html web/app.js web/styles.css tests/test_api.py
git commit -m "feat: add fortune profile and daily calendar"
```

### Task 4: Admin Metaphysics Config And AI Style Presets

**Files:**
- Create: `lottery_luck/settings.py`
- Modify: `lottery_luck/api.py`
- Modify: `lottery_luck/predictor.py`
- Modify: `web/admin.html`
- Modify: `web/admin.js`
- Modify: `web/styles.css`
- Test: `tests/test_api.py`
- Test: `tests/test_predictor.py`

- [x] **Step 1: Write failing tests**

Add an API test:

```python
def test_admin_settings_endpoint_returns_metaphysics_config():
    response = client.get("/api/admin/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metaphysics_weights"]["steady"]["personal_space"] == 40
    assert "短钩子" in payload["ai_copy_styles"][0]["label"]
```

Add a predictor test that monkeypatches settings weights and confirms mode weights can be overridden by `settings.get_metaphysics_weights()`.

- [x] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_admin_settings_endpoint_returns_metaphysics_config -q`

Expected: FAIL because `/api/admin/settings` is missing.

- [x] **Step 3: Implement settings module and endpoint**

Create `lottery_luck/settings.py` with default config, JSON file loading from `LOTTERY_LUCK_SETTINGS_PATH`, and safe fallback. Add `GET /api/admin/settings`. Keep persistence out of scope for this batch unless the JSON env path already exists.

- [x] **Step 4: Surface config in admin UI**

Add an admin card showing current mode weights and AI copy style presets. This is read-only V1 so ops can see what algorithm is running.

- [x] **Step 5: Run tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_predictor.py -q`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add lottery_luck/settings.py lottery_luck/api.py lottery_luck/predictor.py web/admin.html web/admin.js web/styles.css tests/test_api.py tests/test_predictor.py
git commit -m "feat: expose metaphysics settings"
```

### Task 5: Crawler Task Queue And Scheduler CLI

**Files:**
- Create: `lottery_luck/tasks.py`
- Create: `lottery_luck/scheduler.py`
- Modify: `lottery_luck/api.py`
- Modify: `lottery_luck/repository.py`
- Modify: `web/admin.html`
- Modify: `web/admin.js`
- Modify: `web/styles.css`
- Test: `tests/test_tasks.py`
- Test: `tests/test_api.py`

- [x] **Step 1: Write failing task tests**

Create `tests/test_tasks.py`:

```python
import sqlite3

from lottery_luck.tasks import (
    create_task,
    ensure_task_table,
    list_tasks,
    mark_task_finished,
)


def test_task_queue_creates_and_completes_crawl_task():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    ensure_task_table(connection)

    task = create_task(connection, kind="crawl", provider="cwl", game_keys=["ssq", "3d"])
    mark_task_finished(connection, task["id"], status="success", result={"wrote_count": 2})

    tasks = list_tasks(connection, limit=5)
    assert tasks[0]["kind"] == "crawl"
    assert tasks[0]["provider"] == "cwl"
    assert tasks[0]["game_keys"] == ["ssq", "3d"]
    assert tasks[0]["status"] == "success"
    assert tasks[0]["result"]["wrote_count"] == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_tasks.py -q`

Expected: FAIL because `lottery_luck.tasks` does not exist.

- [x] **Step 3: Implement task helpers**

Create a SQLite `admin_tasks` table, JSON encode/decode `game_keys`, `payload`, and `result`, and provide create/list/finish helpers.

- [x] **Step 4: Add scheduler CLI**

Create `python -m lottery_luck.scheduler --once --provider cwl --games ssq,3d,kl8` and `--provider sports --games dlt,pl3,pl5`. In `--once`, create a task, run the matching crawler synchronously, store success/failure, and print a JSON summary.

- [x] **Step 5: Add admin endpoints and UI**

Add `GET /api/admin/tasks` and `POST /api/admin/tasks/run`. Add an admin task panel showing latest tasks and a “执行一次定时补采” action.

- [x] **Step 6: Run tests**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_tasks.py tests/test_api.py -q`

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add lottery_luck/tasks.py lottery_luck/scheduler.py lottery_luck/api.py lottery_luck/repository.py web/admin.html web/admin.js web/styles.css tests/test_tasks.py tests/test_api.py
git commit -m "feat: add crawl task queue"
```

### Task 6: Verification And Push

**Files:**
- All touched files

- [x] **Step 1: Run backend tests**

Run: `PYTHONPATH=. .venv/bin/pytest -q`

Expected: all tests pass.

- [x] **Step 2: Run frontend syntax checks**

Run: `node --check web/app.js && node --check web/result.js && node --check web/admin.js && node --check web/analysis.js && node --check web/strategy.js`

Expected: all checks pass.

- [x] **Step 3: Browser verification**

Start the server with `PYTHONPATH=. .venv/bin/uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017`, then verify `/`, `/result.html`, and `/admin.html` render without console errors on desktop and mobile widths.

- [x] **Step 4: Push**

Run: `git push origin main`

Expected: push succeeds.
