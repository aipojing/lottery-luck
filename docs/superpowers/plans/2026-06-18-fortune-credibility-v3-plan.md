# Fortune Credibility V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V3 homepage fortune experience: ritual generation steps, daily fortune sign, clearer credibility chain, richer avoid-number explanations, and durable local history fields.

**Architecture:** Extend the existing `PredictionEngine` payload instead of adding a new endpoint. The frontend keeps the current single-page shell and renders new V3 data through small dedicated render helpers. History and detail pages remain localStorage-based and backward compatible with old records.

**Tech Stack:** Python 3.14, FastAPI, pytest, vanilla HTML/CSS/JavaScript, localStorage, Playwright screenshot verification.

---

## File Structure

- Modify `lottery_luck/predictor.py`: add deterministic `daily_fortune_sign`, structured `ritual_steps`, expanded `credibility_chain`, and bounded avoid-number reasons.
- Modify `tests/test_predictor.py`: cover new payload fields, stability, fallback behavior, and avoid-number constraints.
- Modify `tests/test_api.py`: cover `/api/predict` response shape and homepage shell containers.
- Modify `web/index.html`: add `dailyFortuneSign` and `ritualSteps` containers near the primary result.
- Modify `web/app.js`: render ritual steps, delay result updates during user-initiated generation, render daily fortune sign, persist V3 history fields.
- Modify `web/result.js`: prefer V3 `credibility_chain`, `daily_fortune_sign`, and `avoid_numbers` when rendering detail and poster text.
- Modify `web/styles.css`: style ritual steps and daily fortune sign across desktop and mobile.

## Task 1: Backend V3 Payload

**Files:**
- Modify: `lottery_luck/predictor.py`
- Test: `tests/test_predictor.py`

- [ ] **Step 1: Write failing tests for V3 payload fields**

Add tests near the existing predictor payload tests:

```python
def test_predict_includes_daily_fortune_sign_and_ritual_steps():
    payload = PredictionEngine(_Repo(), NullAiProvider()).predict(
        "ssq",
        _personal(),
        today="2026-06-18",
        fortune_mode="steady",
    )

    sign = payload["daily_fortune_sign"]
    assert sign["headline"]
    assert sign["direction"] in {"正东", "东南", "正南", "西南", "正西", "西北", "正北", "东北"}
    assert len(sign["tags"]) == 3
    assert len(sign["lucky_tails"]) >= 1
    assert len(sign["avoid_tails"]) >= 1

    steps = payload["ritual_steps"]
    assert [step["key"] for step in steps] == [
        "wealth_pattern",
        "fortune_direction",
        "fortune_eye",
        "avoid_clash",
        "final_numbers",
    ]
    assert all(step["label"] and step["summary"] for step in steps)


def test_predict_v3_avoid_numbers_are_bounded_and_do_not_overlap():
    payload = PredictionEngine(_Repo(), NullAiProvider()).predict(
        "kl8",
        _personal(),
        today="2026-06-18",
    )

    selected = set(payload["numbers"]["main"] + payload["numbers"]["special"])
    avoid_numbers = payload["avoid_numbers"]
    assert 1 <= len(avoid_numbers) <= 6
    assert not selected.intersection(item["number"] for item in avoid_numbers)
    assert all(item["reason"] for item in avoid_numbers)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py::test_predict_includes_daily_fortune_sign_and_ritual_steps tests/test_predictor.py::test_predict_v3_avoid_numbers_are_bounded_and_do_not_overlap -q
```

Expected: fail because `daily_fortune_sign` and V3 `ritual_steps` do not exist yet.

- [ ] **Step 3: Implement deterministic helper functions**

Add helper functions to `lottery_luck/predictor.py` after `_fortune_hook`:

```python
FORTUNE_DIRECTIONS = ("正东", "东南", "正南", "西南", "正西", "西北", "正北", "东北")


def _element_tail_digits(elements: list[str]) -> list[int]:
    tails: list[int] = []
    wanted = set(elements)
    for digit, element in DIGIT_ELEMENT.items():
        if element in wanted and digit not in tails:
            tails.append(digit)
    return tails


def _daily_fortune_sign(
    personal: PersonalInput,
    draw_date: str,
    profile: Mapping[str, Any],
    ai_feature: AiFeature,
) -> dict[str, Any]:
    seed = stable_int("|".join((personal.name, personal.birth_date, personal.current_city, draw_date, "daily-sign")))
    direction = FORTUNE_DIRECTIONS[seed % len(FORTUNE_DIRECTIONS)]
    lucky_tails = _element_tail_digits(profile.get("favorable_elements") or [])[:4]
    avoid_tails = _element_tail_digits(profile.get("avoid_elements") or [])[:4]
    if ai_feature.enabled:
        preferred = [digit for digit in ai_feature.preferred_digits if digit not in lucky_tails]
        lucky_tails = (lucky_tails + preferred)[:4]
    lucky_label = "/".join(str(tail) for tail in lucky_tails[:2]) or "喜用"
    avoid_label = "/".join(str(tail) for tail in avoid_tails[:2]) or "冲位"
    headline = f"今日偏财气在{direction}，宜取 {lucky_label} 尾，避 {avoid_label} 冲。"
    return {
        "headline": headline,
        "direction": direction,
        "lucky_tails": lucky_tails,
        "avoid_tails": avoid_tails,
        "tags": [f"{direction}财位", f"尾 {lucky_label}", f"避 {avoid_label}"],
    }
```

- [ ] **Step 4: Implement ritual steps**

Add helper:

```python
def _ritual_steps(
    profile: Mapping[str, Any],
    sign: Mapping[str, Any],
    main_numbers: list[int],
    special_numbers: list[int],
    avoid_numbers: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    eye = special_numbers[-1] if special_numbers else (main_numbers[-1] if main_numbers else "--")
    avoid_text = " / ".join(f"{item.get('number'):02d}" for item in avoid_numbers[:3] if item.get("number") is not None)
    return [
        {
            "key": "wealth_pattern",
            "label": "校准本命财格",
            "summary": f"归入{profile.get('wealth_pattern') or '本命财格'}，先定个人时空底盘。",
        },
        {
            "key": "fortune_direction",
            "label": "定今日财位",
            "summary": f"今日财位落在{sign.get('direction') or '当前气口'}，先看开奖日气口。",
        },
        {
            "key": "fortune_eye",
            "label": "取财眼尾数",
            "summary": f"以{profile.get('favorable_element_labels') or '喜用数'}收束，财眼落到 {int(eye):02d}。",
        },
        {
            "key": "avoid_clash",
            "label": "避冲煞号",
            "summary": f"避开 {avoid_text or '冲位号'}，不让整组号码偏冲。",
        },
        {
            "key": "final_numbers",
            "label": "成财运号",
            "summary": f"最终落到{_format_number_path(main_numbers, special_numbers)}。",
        },
    ]
```

- [ ] **Step 5: Wire helpers into `PredictionEngine.predict`**

In `predict`, compute after `avoid_numbers`:

```python
daily_fortune_sign = _daily_fortune_sign(personal, best_draw_date, metaphysics_profile, ai_feature)
ritual_steps = _ritual_steps(
    metaphysics_profile,
    daily_fortune_sign,
    main_numbers,
    special_numbers,
    avoid_numbers,
)
```

Then add to the returned payload:

```python
"daily_fortune_sign": daily_fortune_sign,
"ritual_steps": ritual_steps,
```

- [ ] **Step 6: Expand avoid-number limit**

Change `_avoid_numbers` to cap at `6` for `kl8` and `4` for other games:

```python
limit = 6 if game_key == "kl8" else 4
for number, _, _ in ranked[:limit]:
    ...
```

- [ ] **Step 7: Run tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py::test_predict_includes_daily_fortune_sign_and_ritual_steps tests/test_predictor.py::test_predict_v3_avoid_numbers_are_bounded_and_do_not_overlap -q
```

Expected: both pass.

- [ ] **Step 8: Commit backend payload**

```bash
git add lottery_luck/predictor.py tests/test_predictor.py
git commit -m "feat: add fortune credibility v3 payload"
```

## Task 2: Homepage Shell And Rendering

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API shell test**

Extend `test_root_serves_frontend_shell`:

```python
assert 'id="dailyFortuneSign"' in response.text
assert 'id="ritualSteps"' in response.text
assert "今日财运签" in response.text
assert "校准本命财格" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_root_serves_frontend_shell -q
```

Expected: fail because the containers are not in `index.html`.

- [ ] **Step 3: Add homepage containers**

In `web/index.html`, insert after the board disclaimer:

```html
<section class="daily-fortune-sign" id="dailyFortuneSign" aria-label="今日财运签">
  <div>
    <p class="section-kicker">今日财运签</p>
    <strong>等待起局。</strong>
  </div>
  <div class="fortune-sign-tags">
    <span>财位待定</span>
    <span>尾数待定</span>
    <span>避冲待定</span>
  </div>
</section>

<section class="ritual-steps" id="ritualSteps" aria-label="起局步骤">
  <div class="ritual-step">
    <span>1</span>
    <strong>校准本命财格</strong>
    <small>等待生成</small>
  </div>
  <div class="ritual-step">
    <span>2</span>
    <strong>定今日财位</strong>
    <small>等待生成</small>
  </div>
  <div class="ritual-step">
    <span>3</span>
    <strong>取财眼尾数</strong>
    <small>等待生成</small>
  </div>
  <div class="ritual-step">
    <span>4</span>
    <strong>避冲煞号</strong>
    <small>等待生成</small>
  </div>
  <div class="ritual-step">
    <span>5</span>
    <strong>成财运号</strong>
    <small>等待生成</small>
  </div>
</section>
```

- [ ] **Step 4: Add element references and render helpers**

Add to `els` in `web/app.js`:

```js
dailyFortuneSign: document.querySelector("#dailyFortuneSign"),
ritualSteps: document.querySelector("#ritualSteps"),
```

Add render helpers:

```js
function renderDailyFortuneSign(sign) {
  if (!els.dailyFortuneSign) return;
  const data = sign || {};
  const headline = data.headline || "等待起局。";
  const tags = Array.isArray(data.tags) && data.tags.length ? data.tags : ["财位待定", "尾数待定", "避冲待定"];
  els.dailyFortuneSign.replaceChildren();
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "今日财运签";
  const title = document.createElement("strong");
  title.textContent = headline;
  copy.append(kicker, title);
  const tagWrap = document.createElement("div");
  tagWrap.className = "fortune-sign-tags";
  tags.slice(0, 3).forEach((tag) => {
    const chip = document.createElement("span");
    chip.textContent = tag;
    tagWrap.append(chip);
  });
  els.dailyFortuneSign.append(copy, tagWrap);
}

function renderRitualSteps(steps, activeIndex = -1) {
  if (!els.ritualSteps) return;
  const rows = Array.isArray(steps) && steps.length ? steps : [];
  els.ritualSteps.replaceChildren();
  rows.forEach((step, index) => {
    const item = document.createElement("div");
    item.className = "ritual-step";
    if (index < activeIndex) item.classList.add("done");
    if (index === activeIndex) item.classList.add("active");
    const number = document.createElement("span");
    number.textContent = String(index + 1);
    const label = document.createElement("strong");
    label.textContent = step.label || "起局步骤";
    const summary = document.createElement("small");
    summary.textContent = step.summary || "等待生成";
    item.append(number, label, summary);
    els.ritualSteps.append(item);
  });
}
```

- [ ] **Step 5: Wire rendering into `renderPrediction`**

In `renderPrediction(payload)`, call:

```js
renderDailyFortuneSign(payload.daily_fortune_sign);
renderRitualSteps(payload.ritual_steps || DEFAULT_RITUAL_STEPS, Number.MAX_SAFE_INTEGER);
```

- [ ] **Step 6: Add CSS**

Add styles in `web/styles.css` near `.fortune-hook`:

```css
.daily-fortune-sign,
.ritual-steps {
  width: min(1160px, 100%);
  margin: 18px auto 0;
}

.daily-fortune-sign {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid rgba(214, 169, 88, 0.24);
  background: linear-gradient(90deg, rgba(214, 169, 88, 0.16), rgba(8, 6, 3, 0.72));
  padding: 16px 20px;
}

.daily-fortune-sign strong {
  display: block;
  color: var(--gold-pale);
  font-size: 20px;
  font-weight: 500;
}

.fortune-sign-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.fortune-sign-tags span,
.ritual-step span {
  border: 1px solid rgba(214, 169, 88, 0.32);
  color: var(--gold-soft);
  background: rgba(214, 169, 88, 0.08);
}

.fortune-sign-tags span {
  border-radius: 999px;
  padding: 6px 10px;
}

.ritual-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.ritual-step {
  min-width: 0;
  border: 1px solid rgba(214, 169, 88, 0.18);
  background: rgba(5, 4, 2, 0.58);
  padding: 12px;
}

.ritual-step span {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  margin-bottom: 8px;
}

.ritual-step.active {
  border-color: rgba(255, 224, 147, 0.62);
  box-shadow: 0 0 22px rgba(214, 169, 88, 0.18);
}

.ritual-step.done span {
  color: #130c03;
  background: linear-gradient(180deg, #fff0b9, #c98b23);
}
```

Add inside mobile media query:

```css
.daily-fortune-sign {
  display: grid;
}

.fortune-sign-tags {
  justify-content: flex-start;
}

.ritual-steps {
  grid-template-columns: 1fr;
}
```

- [ ] **Step 7: Run tests and JS checks**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_root_serves_frontend_shell -q
node --check web/app.js
```

Expected: pass.

- [ ] **Step 8: Commit homepage shell**

```bash
git add web/index.html web/app.js web/styles.css tests/test_api.py
git commit -m "feat: render fortune ritual experience"
```

## Task 3: User-Initiated Ritual Timing And History

**Files:**
- Modify: `web/app.js`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write static asset assertions**

In `test_frontend_assets_are_served`, add:

```python
assert "runRitualSequence" in response.text
assert "daily_fortune_sign" in response.text
assert "ritual_steps" in response.text
assert "avoid_reasons" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_frontend_assets_are_served -q
```

Expected: fail because the ritual sequence helper and stored fields are missing.

- [ ] **Step 3: Add ritual sequence helper**

Add in `web/app.js` near feedback helpers:

```js
const DEFAULT_RITUAL_STEPS = [
  { key: "wealth_pattern", label: "校准本命财格", summary: "折算个人时空底盘。" },
  { key: "fortune_direction", label: "定今日财位", summary: "校准开奖日气口。" },
  { key: "fortune_eye", label: "取财眼尾数", summary: "锁定喜用尾数。" },
  { key: "avoid_clash", label: "避冲煞号", summary: "排除本期冲位。" },
  { key: "final_numbers", label: "成财运号", summary: "收束为本组号码。" },
];

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function runRitualSequence(steps = DEFAULT_RITUAL_STEPS) {
  const rows = Array.isArray(steps) && steps.length ? steps : DEFAULT_RITUAL_STEPS;
  for (let index = 0; index < rows.length; index += 1) {
    renderRitualSteps(rows, index);
    await wait(280);
  }
  renderRitualSteps(rows, rows.length);
}
```

- [ ] **Step 4: Update `predict` timing**

In `predict`, when `userInitiated`, start the ritual promise before fetch:

```js
const ritualPromise = userInitiated ? runRitualSequence(DEFAULT_RITUAL_STEPS) : Promise.resolve();
```

After payload is fetched and before `renderPrediction(payload)`:

```js
if (userInitiated) await ritualPromise;
renderPrediction(payload);
```

In the catch block, also `await ritualPromise` before rendering demo fallback.

- [ ] **Step 5: Store V3 history fields**

In `saveFortuneHistory`, add fields:

```js
daily_fortune_sign: payload.daily_fortune_sign || null,
ritual_steps: payload.ritual_steps || [],
avoid_reasons: (payload.avoid_numbers || []).map((item) => item.reason).filter(Boolean),
```

Keep existing `avoid_numbers` and `number_reasons`.

- [ ] **Step 6: Run tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_frontend_assets_are_served -q
node --check web/app.js
```

Expected: pass.

- [ ] **Step 7: Commit ritual interaction**

```bash
git add web/app.js tests/test_api.py
git commit -m "feat: add fortune ritual sequence"
```

## Task 4: Detail Page Compatibility

**Files:**
- Modify: `web/result.js`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write static asset assertion**

In `test_result_frontend_asset_is_served`, add:

```python
assert "daily_fortune_sign" in response.text
assert "renderDailyFortuneSign" in response.text
assert "credibility_chain" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_result_frontend_asset_is_served -q
```

Expected: fail because result detail does not render V3 sign yet.

- [ ] **Step 3: Add detail sign rendering**

In `web/result.js`, add an element dynamically at the top of `renderResultDetail` after `els.meta` updates:

```js
function renderDailyFortuneSign(record) {
  const sign = record.daily_fortune_sign || {};
  const headline = sign.headline || record.headline || "这条记录暂无今日财运签。";
  els.meta.textContent = `${els.meta.textContent} · ${headline}`;
}
```

Call in `renderResultDetail(record)`:

```js
renderDailyFortuneSign(record);
```

- [ ] **Step 4: Prefer V3 credibility chain**

Update `renderClosedLoop(report)` to accept `record`:

```js
function renderClosedLoop(record) {
  els.loop.replaceChildren();
  const report = record.fortune_report || {};
  const chain = Array.isArray(record.credibility_chain) && record.credibility_chain.length
    ? record.credibility_chain.map((item) => ({
        label: item.label || item.title,
        value: item.value || item.text,
        detail: item.explanation || item.detail,
      }))
    : Array.isArray(report.closed_loop) ? report.closed_loop : [];
  ...
}
```

Then call `renderClosedLoop(record)`.

- [ ] **Step 5: Update poster copy**

In `drawSharePoster`, use:

```js
const sign = record.daily_fortune_sign || {};
wrapText(ctx, sign.headline || report.summary || record.headline || "娱乐推荐，不构成投注建议。", 90, 575, width - 180, 38);
```

- [ ] **Step 6: Run tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_result_frontend_asset_is_served -q
node --check web/result.js
```

Expected: pass.

- [ ] **Step 7: Commit detail compatibility**

```bash
git add web/result.js tests/test_api.py
git commit -m "feat: show fortune v3 detail data"
```

## Task 5: Full Verification And Service Restart

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run full tests**

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run JS syntax checks**

```bash
node --check web/app.js && node --check web/result.js && node --check web/analysis.js && node --check web/strategy.js && node --check web/admin.js
```

Expected: no output and exit code 0.

- [ ] **Step 3: Restart local server**

Stop the current uvicorn session, then run:

```bash
PYTHONPATH=. .venv/bin/uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
```

Expected: server starts on `http://127.0.0.1:8017`.

- [ ] **Step 4: Verify real API and rendered page**

Run:

```bash
.venv/bin/python - <<'PY'
import json, urllib.request
payload = {
    "game_key": "ssq",
    "name": "张三",
    "birth_date": "1990-01-01",
    "birth_hour": "辰",
    "birth_place": "北京市",
    "current_city": "北京市",
}
request = urllib.request.Request(
    "http://127.0.0.1:8017/api/predict",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as resp:
    data = json.load(resp)
print(data["daily_fortune_sign"]["headline"])
print([step["key"] for step in data["ritual_steps"]])
PY
```

Expected: prints a non-empty fortune sign headline and five ritual step keys.

- [ ] **Step 5: Browser screenshot verification**

Use Playwright to capture desktop and mobile screenshots:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from playwright.sync_api import sync_playwright
out = Path("/tmp/lottery-fortune-v3")
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, size in [("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 900})]:
        page = browser.new_page(viewport=size)
        page.goto("http://127.0.0.1:8017/", wait_until="networkidle")
        assert page.locator("#dailyFortuneSign").count() == 1
        assert page.locator("#ritualSteps").count() == 1
        page.screenshot(path=str(out / f"{name}.png"), full_page=False)
        page.close()
    browser.close()
PY
```

Expected: command exits 0 and screenshots show no overlap between fortune sign, ritual steps, balls, and form.

- [ ] **Step 6: Final commit if needed and push**

If any verification fixes were made:

```bash
git add lottery_luck/predictor.py tests/test_predictor.py tests/test_api.py web/index.html web/app.js web/result.js web/styles.css
git commit -m "fix: polish fortune credibility v3"
```

Push:

```bash
git push origin main
```

Expected: branch `main` pushed successfully.
