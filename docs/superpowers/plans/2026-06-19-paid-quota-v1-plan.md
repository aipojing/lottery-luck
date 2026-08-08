# Paid Quota V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a V1 paid quota system where analysis stays free, user-initiated predictions consume configurable quota, free records stay local, and paid records can sync to cloud storage.

**Architecture:** Keep prediction math unchanged. Add focused quota/cloud modules backed by SQLite, expose status/unlock/cloud endpoints in FastAPI, and have the homepage send a stable local `client_id`. V1 uses mock unlocks and local client identity so real login/payment can replace only the edge adapters later.

**Tech Stack:** Python 3.14, FastAPI, SQLite, pytest, vanilla HTML/CSS/JavaScript, Playwright frontend behavior tests.

---

## File Structure

- Create `lottery_luck/quota.py`: quota config application, SQLite tables, status, consume, mock unlock, cloud record persistence.
- Modify `lottery_luck/settings.py`: default `prediction_quota` config and override parsing.
- Modify `lottery_luck/repository.py`: small wrapper methods that open DB connections and call quota/cloud helpers.
- Modify `lottery_luck/api.py`: client-id header handling, quota status/unlock endpoints, gated user-initiated predict, cloud record endpoints.
- Modify `web/index.html`: quota badge and unlock panel shell.
- Modify `web/app.js`: local client id, quota status rendering, quota-aware prediction, mock unlock actions, cloud record sync, storage badges.
- Modify `web/admin.js`: render commercial quota settings in the existing settings card.
- Modify `web/styles.css`: quota badge, unlock panel, storage badge styles.
- Modify tests in `tests/test_api.py`, `tests/test_frontend_behavior.py`; create `tests/test_quota.py`.

---

### Task 1: Settings And Quota Core

**Files:**
- Create: `lottery_luck/quota.py`
- Modify: `lottery_luck/settings.py`
- Modify: `lottery_luck/repository.py`
- Test: `tests/test_quota.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing quota tests**

Add `tests/test_quota.py`:

```python
import sqlite3

from lottery_luck.quota import (
    consume_prediction_quota,
    mock_unlock_quota,
    quota_status,
    save_cloud_record,
    cloud_records,
)
from lottery_luck.settings import get_settings


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


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

    first = consume_prediction_quota(connection, "client-a", "ssq", "steady", today="2026-06-19", config=config)
    second = consume_prediction_quota(connection, "client-a", "ssq", "steady", today="2026-06-19", config=config)
    third = consume_prediction_quota(connection, "client-a", "ssq", "steady", today="2026-06-19", config=config)

    assert first["allowed"] is True
    assert first["source"] == "new_user_bonus"
    assert second["allowed"] is True
    assert second["source"] == "free_daily"
    assert third["allowed"] is False
    assert third["quota"]["remaining_total"] == 0


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

    unlock = mock_unlock_quota(connection, "client-paid", kind="package", units=6, today="2026-06-19", config=config)
    consume = consume_prediction_quota(connection, "client-paid", "ssq", "steady", today="2026-06-19", config=config)
    saved = save_cloud_record(connection, "client-paid", {"id": "r1", "game_key": "ssq", "number_text": "01 02"})

    assert unlock["quota"]["is_paid"] is True
    assert consume["allowed"] is True
    assert consume["source"] == "package"
    assert saved["storage_state"] == "cloud"
    assert cloud_records(connection, "client-paid")[0]["id"] == "r1"
```

- [ ] **Step 2: Run quota tests red**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_quota.py -q`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.quota` or missing `prediction_quota`.

- [ ] **Step 3: Implement settings defaults and quota module**

In `lottery_luck/settings.py`, add `DEFAULT_PREDICTION_QUOTA`, expose it from `get_settings()`, and parse overrides with bounded integers.

Create `lottery_luck/quota.py` with:

```python
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
```

Implement `quota_status()`, `consume_prediction_quota()`, `mock_unlock_quota()`, `save_cloud_record()`, and `cloud_records()` using these tables. Missing/blank `client_id` returns untracked unlimited status.

- [ ] **Step 4: Add repository wrappers**

In `lottery_luck/repository.py`, import quota helpers and add:

```python
def quota_status(self, client_id: str, today: str | None = None) -> dict[str, Any]:
    with self._connect() as connection:
        return quota_status(connection, client_id, today=today)

def consume_prediction_quota(self, client_id: str, game_key: str, mode_key: str, today: str | None = None) -> dict[str, Any]:
    with self._connect() as connection:
        return consume_prediction_quota(connection, client_id, game_key, mode_key, today=today)

def mock_unlock_quota(self, client_id: str, *, kind: str, units: int | None = None, today: str | None = None) -> dict[str, Any]:
    with self._connect() as connection:
        return mock_unlock_quota(connection, client_id, kind=kind, units=units, today=today)

def save_cloud_record(self, client_id: str, record: dict[str, Any]) -> dict[str, Any]:
    with self._connect() as connection:
        return save_cloud_record(connection, client_id, record)

def cloud_records(self, client_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with self._connect() as connection:
        return cloud_records(connection, client_id, limit=limit)
```

- [ ] **Step 5: Run quota tests green**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_quota.py -q`

Expected: PASS.

- [ ] **Step 6: Commit backend quota core**

Run:

```bash
git add lottery_luck/settings.py lottery_luck/quota.py lottery_luck/repository.py tests/test_quota.py
git commit -m "feat: add paid prediction quota core"
```

Expected: commit succeeds.

---

### Task 2: Quota And Cloud APIs

**Files:**
- Modify: `lottery_luck/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests to `tests/test_api.py`:

```python
import sqlite3
from pathlib import Path

from lottery_luck.repository import LotteryRepository


def _quota_db(tmp_path: Path) -> LotteryRepository:
    db_path = tmp_path / "quota.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE draws (game_key TEXT, game_name TEXT, issue TEXT, draw_date TEXT, week TEXT, red_numbers TEXT, blue_number TEXT, sales TEXT, pool_money TEXT, content TEXT, PRIMARY KEY(game_key, issue))"
        )
    return LotteryRepository(db_path)


def test_quota_status_endpoint_returns_configured_remaining(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_SETTINGS_PATH", str(tmp_path / "missing.json"))
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        response = client.get("/api/quota/status", headers={"X-Lottery-Client-Id": "client-api"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["tracked"] is True
    assert payload["remaining_total"] == 4
    assert payload["config"]["free_daily"] == 1


def test_predict_with_client_quota_returns_unlock_payload_when_exhausted(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"prediction_quota": {"free_daily": 0, "new_user_bonus": 0, "member_daily": 0}}),
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
            json={"game_key": "ssq", "name": "张三", "birth_date": "1990-05-17", "consume_quota": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["quota_exhausted"] is True
    assert payload["quota"]["remaining_total"] == 0
    assert "解锁" in payload["unlock"]["title"]
    assert "numbers" not in payload


def test_mock_unlock_and_cloud_record_endpoints(tmp_path, monkeypatch):
    repo = _quota_db(tmp_path)
    app.dependency_overrides[get_repository] = lambda: repo
    headers = {"X-Lottery-Client-Id": "client-cloud"}
    try:
        unlock = client.post("/api/quota/mock-unlock", headers=headers, json={"kind": "package", "units": 6})
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
```

- [ ] **Step 2: Run API tests red**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_quota_status_endpoint_returns_configured_remaining tests/test_api.py::test_predict_with_client_quota_returns_unlock_payload_when_exhausted tests/test_api.py::test_mock_unlock_and_cloud_record_endpoints -q`

Expected: FAIL because quota endpoints do not exist.

- [ ] **Step 3: Implement API endpoints and gated prediction**

In `lottery_luck/api.py`:

- Import `Header` and `Request` if needed.
- Add `consume_quota: bool = False` to `PredictRequest`.
- Add `MockUnlockRequest` and `CloudRecordRequest`.
- Add helper `_client_id()`.
- Add `GET /api/quota/status`, `POST /api/quota/mock-unlock`, `GET/POST /api/cloud/fortune-records`.
- In `/api/predict`, before prediction, if `consume_quota` and client id exists, call `repo.consume_prediction_quota(...)`; when denied return:

```python
{
    "quota_exhausted": True,
    "quota": quota_result["quota"],
    "unlock": {
        "title": "解锁今日财运号",
        "message": "本次额度已用完，可开通会员或购买次数包继续起盘。",
        "benefits": ["继续起盘", "云端保存", "开奖后复盘", "多设备同步"],
    },
    "disclaimer": "仅供娱乐与数据分析参考，不构成投注建议。",
}
```

When allowed, attach `payload["quota"] = quota_result["quota"]`.

- [ ] **Step 4: Run API tests green**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_quota_status_endpoint_returns_configured_remaining tests/test_api.py::test_predict_with_client_quota_returns_unlock_payload_when_exhausted tests/test_api.py::test_mock_unlock_and_cloud_record_endpoints -q`

Expected: PASS.

- [ ] **Step 5: Commit API layer**

Run:

```bash
git add lottery_luck/api.py tests/test_api.py
git commit -m "feat: add quota and cloud record APIs"
```

Expected: commit succeeds.

---

### Task 3: Homepage Paid Quota Experience

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_api.py`
- Modify: `tests/test_frontend_behavior.py`

- [ ] **Step 1: Write failing frontend tests**

Update `test_root_serves_frontend_shell()` to assert:

```python
assert 'id="quotaStatus"' in response.text
assert 'id="unlockPanel"' in response.text
assert "解锁今日财运号" in response.text
```

Update `test_frontend_assets_are_served()` to assert:

```python
assert "CLIENT_ID_KEY" in response.text
assert "loadQuotaStatus" in response.text
assert "quota_exhausted" in response.text
assert "syncCloudRecord" in response.text
```

Add Playwright test:

```python
def test_quota_exhausted_shows_unlock_panel_without_saving_history(live_server_url, browser_page):
    browser_page.route(
        f"{live_server_url}/api/quota/status",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({
            "tracked": True,
            "remaining_total": 0,
            "is_paid": False,
            "config": {"allow_demo_after_exhausted": True},
        }, ensure_ascii=False)),
    )
    browser_page.route(
        f"{live_server_url}/api/predict",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({
            "quota_exhausted": True,
            "quota": {"remaining_total": 0, "is_paid": False},
            "unlock": {"title": "解锁今日财运号", "message": "额度已用完", "benefits": ["继续起盘", "云端保存"]},
            "disclaimer": "仅供娱乐与数据分析参考，不构成投注建议。",
        }, ensure_ascii=False)),
    )

    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled", timeout=5000)
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function("() => !document.querySelector('#unlockPanel').hidden", timeout=5000)

    assert "解锁今日财运号" in browser_page.locator("#unlockPanel").inner_text()
    assert "次数已用完" in browser_page.locator("#quotaStatus").inner_text()
    records = browser_page.evaluate("() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')")
    assert records == []
```

- [ ] **Step 2: Run frontend tests red**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_root_serves_frontend_shell tests/test_api.py::test_frontend_assets_are_served tests/test_frontend_behavior.py::test_quota_exhausted_shows_unlock_panel_without_saving_history -q
```

Expected: FAIL because markup and JS functions are missing.

- [ ] **Step 3: Add quota markup**

In `web/index.html`, inside `#predictForm` before submit button add:

```html
<div class="quota-status" id="quotaStatus" aria-live="polite">
  今日剩余 -- 次
</div>
```

After `#predictForm`, add:

```html
<section class="unlock-panel" id="unlockPanel" aria-label="解锁预测额度" hidden>
  <div>
    <p class="section-kicker">会员权益</p>
    <h2>解锁今日财运号</h2>
    <p id="unlockMessage">次数用完后，可开通会员或购买次数包继续起盘。</p>
    <ul id="unlockBenefits">
      <li>继续起盘</li>
      <li>云端保存</li>
      <li>开奖后复盘</li>
      <li>多设备同步</li>
    </ul>
  </div>
  <div class="unlock-actions">
    <button class="primary-action small" id="mockMemberButton" type="button">模拟开通会员</button>
    <button class="text-action" id="mockPackageButton" type="button">模拟购买次数包</button>
  </div>
</section>
```

- [ ] **Step 4: Implement frontend quota logic**

In `web/app.js`:

- Add `CLIENT_ID_KEY`.
- Add `clientId()`.
- Update `fetchJson()` to send `X-Lottery-Client-Id`.
- Add `loadQuotaStatus()`, `renderQuotaStatus()`, `renderUnlockPanel()`, `hideUnlockPanel()`, `mockUnlock()`, `syncCloudRecord()`.
- Add `consume_quota: userInitiated` to predict payload.
- If predict payload has `quota_exhausted`, show unlock panel, update quota, do not save history.
- Have `saveFortuneHistory()` return the record and set `storage_state` to `"cloud"` when `payload.quota?.is_paid`, otherwise `"local"`.
- Render storage badge in history cards.

- [ ] **Step 5: Add styles**

In `web/styles.css`, add `.quota-status`, `.unlock-panel`, `.unlock-actions`, `.storage-badge`, and compact mobile behavior near existing form/history styles.

- [ ] **Step 6: Run frontend tests green**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_root_serves_frontend_shell tests/test_api.py::test_frontend_assets_are_served tests/test_frontend_behavior.py::test_quota_exhausted_shows_unlock_panel_without_saving_history -q
```

Expected: PASS.

- [ ] **Step 7: Commit homepage quota UX**

Run:

```bash
git add web/index.html web/app.js web/styles.css tests/test_api.py tests/test_frontend_behavior.py
git commit -m "feat: add paid quota homepage experience"
```

Expected: commit succeeds.

---

### Task 4: Admin Commercial Settings And Full Verification

**Files:**
- Modify: `web/admin.js`
- Modify: `tests/test_api.py`
- Verify: all tests

- [ ] **Step 1: Write failing admin tests**

Update `test_admin_settings_endpoint_returns_metaphysics_config()`:

```python
assert payload["prediction_quota"]["free_daily"] == 1
assert payload["prediction_quota"]["member_daily"] == 20
```

Update `test_admin_frontend_asset_is_served()`:

```python
assert "商业化配置" in response.text
assert "prediction_quota" in response.text
assert "renderCommercialSettings" in response.text
```

- [ ] **Step 2: Run admin tests red**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_admin_settings_endpoint_returns_metaphysics_config tests/test_api.py::test_admin_frontend_asset_is_served -q
```

Expected: FAIL until admin asset renders commercial settings.

- [ ] **Step 3: Implement admin settings card**

In `web/admin.js`, add:

```javascript
function renderCommercialSettings(grid, quota) {
  const card = document.createElement("article");
  card.className = "settings-card settings-card-wide";
  const title = document.createElement("strong");
  title.textContent = "商业化配置";
  const list = document.createElement("ul");
  [
    ["免费每日", quota.free_daily],
    ["新客赠送", quota.new_user_bonus],
    ["会员每日", quota.member_daily],
    ["次数包", (quota.package_units || []).join(" / ")],
    ["消耗彩种", (quota.enabled_games || []).map((key) => GAME_LABELS[key] || key).join(" / ")],
  ].forEach(([label, value]) => {
    const item = document.createElement("li");
    item.textContent = `${label}：${value ?? "--"}`;
    list.append(item);
  });
  card.append(title, list);
  grid.append(card);
}
```

Call `renderCommercialSettings(grid, payload.prediction_quota || {})` inside `renderSettings()`.

- [ ] **Step 4: Run admin tests green**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_admin_settings_endpoint_returns_metaphysics_config tests/test_api.py::test_admin_frontend_asset_is_served -q
```

Expected: PASS.

- [ ] **Step 5: Full verification**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q
node --check web/app.js web/admin.js web/result.js web/analysis.js web/strategy.js
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit admin and verification polish**

Run:

```bash
git add web/admin.js tests/test_api.py
git commit -m "feat: show commercial quota settings"
```

Expected: commit succeeds.

- [ ] **Step 7: Push branch**

Run:

```bash
git status --short
git push
```

Expected: only `cwl_history/cwl_history.sqlite` remains unstaged, push succeeds.
