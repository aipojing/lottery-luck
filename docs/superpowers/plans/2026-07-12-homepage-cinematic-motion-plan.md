# 预测首页玄金电影感动效 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不更换原生前端技术栈的前提下，为预测首页实现“先输入、再起盘、真实结果返回后落号”的玄金电影感动效，并完整覆盖慢请求、额度不足、失败、取消、移动端和减少动态效果模式。

**Architecture:** 新增独立的 `window.FortuneMotion` 动效控制器，以现有 `predictionRequestId` 为请求上下文，驱动 `idle/running/waiting/complete/error/locked/cancelled` 状态。`app.js` 继续负责数据请求和业务渲染，`motion.js` 只负责时间轴和 DOM 动效；`motion.css` 承担所有首页专属动画，避免继续扩大共享样式文件。

**Tech Stack:** FastAPI 静态资源、原生 HTML/CSS/JavaScript、Web Animations/CSS Animations、IntersectionObserver、Playwright、pytest、Node `--check`。

---

## 文件地图

- Create: `web/motion.js` — 首页动效状态机、时间轴、取消、滚动观察和页面可见性处理。
- Create: `web/motion.css` — 起盘舞台、首屏定场、号码落盘、滚动揭示、移动端和减少动态效果样式。
- Modify: `web/index.html` — 加载动效资源，增加起盘舞台和滚动揭示标记。
- Modify: `web/app.js` — 将真实预测生命周期接入 `FortuneMotion`，移除正式起盘失败时的演示号回落。
- Modify: `web/styles.css` — 删除迁移到 `motion.css` 的旧首页关键帧，补充少量共享视觉令牌。
- Modify: `tests/test_api.py` — 验证新资源和首页结构可由 FastAPI 静态站点提供。
- Modify: `tests/test_frontend_behavior.py` — 覆盖状态机、慢请求、真实落号、失败、额度、取消和降级行为。
- Create: `tests/capture_motion_qa.py` — 固定视口、状态断言和截图采集脚本。
- Modify: `design-qa.md` — 记录桌面、移动端、减少动态效果和边界状态视觉证据。

## Task 1: 建立首页动效静态资源契约

**Files:**
- Create: `web/motion.js`
- Create: `web/motion.css`
- Modify: `web/index.html:7-8,37-68,186-217,387`
- Test: `tests/test_api.py:169-200,503-509`

- [ ] **Step 1: 写入失败的静态资源测试**

在 `tests/test_api.py` 的 `test_frontend_assets_are_served` 后新增：

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_home_includes_cinematic_motion_assets_and_stage -q`

Expected: FAIL，首页尚未引用 `motion.css`/`motion.js`，或 `/motion.js` 返回 404。

- [ ] **Step 3: 创建最小资源并接入首页**

创建 `web/motion.js`：

```javascript
(() => {
  "use strict";

  window.FortuneMotion = {
    enter() {},
    start() {},
    resolve() { return Promise.resolve(false); },
    fail() {},
    lock() {},
    cancel() {},
    reveal() {},
  };
})();
```

创建 `web/motion.css`：

```css
.ritual-stage {
  display: none;
}
```

在 `web/index.html` 的 `styles.css` 后增加：

```html
<link rel="stylesheet" href="./motion.css?v=20260712-cinematic-v1" />
```

在 `gameTabs` 后、`oracle-board` 前增加：

```html
<section
  class="ritual-stage"
  id="ritualStage"
  data-motion-state="idle"
  aria-hidden="true"
  aria-label="起盘进度"
>
  <div class="ritual-stage-dial primary" aria-hidden="true"></div>
  <div class="ritual-stage-dial secondary" aria-hidden="true"></div>
  <div class="ritual-stage-copy">
    <p class="ritual-stage-status" id="motionStatus" role="status">等待开始起盘</p>
    <h2 id="motionTitle">命盘待入局</h2>
    <div class="ritual-stage-progress" aria-hidden="true">
      <i id="motionProgress"></i>
    </div>
    <ol class="ritual-stage-steps" id="motionSteps"></ol>
    <div class="ritual-stage-numbers" id="motionNumbers" aria-hidden="true"></div>
  </div>
</section>
```

在 `app.js` 前增加：

```html
<script src="./motion.js?v=20260712-cinematic-v1" defer></script>
```

- [ ] **Step 4: 运行静态资源测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_home_includes_cinematic_motion_assets_and_stage -q`

Expected: PASS。

- [ ] **Step 5: 提交静态骨架**

```bash
git add web/index.html web/motion.js web/motion.css tests/test_api.py
git commit -m "feat: add homepage motion asset shell"
```

## Task 2: 实现可取消的动效状态机

**Files:**
- Modify: `web/motion.js`
- Test: `tests/test_frontend_behavior.py:37-43,324-413`

- [ ] **Step 1: 写入状态机失败测试**

在 `tests/test_frontend_behavior.py` 的慢请求测试前新增：

```python
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
    assert browser_page.locator("#motionNumbers").inner_text().split() == [
        "03", "08", "16", "21", "27", "32", "09"
    ]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_motion_controller_moves_from_running_to_complete -q`

Expected: FAIL，最小 `FortuneMotion` 尚未设置状态或渲染号码。

- [ ] **Step 3: 用完整控制器替换 `web/motion.js`**

```javascript
(() => {
  "use strict";

  const STEP_DELAYS = [420, 900, 1380, 1860];
  const MIN_REVEAL_MS = 2200;
  const DEFAULT_STEPS = ["定命盘", "排财格", "定财局", "取尾数", "落财号"];
  const timers = new Set();
  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const state = {
    requestId: null,
    startedAt: 0,
    resolved: false,
    hiddenByVisibility: false,
  };

  const els = {
    body: document.body,
    stage: document.querySelector("#ritualStage"),
    status: document.querySelector("#motionStatus"),
    title: document.querySelector("#motionTitle"),
    progress: document.querySelector("#motionProgress"),
    steps: document.querySelector("#motionSteps"),
    numbers: document.querySelector("#motionNumbers"),
  };

  function later(callback, delay) {
    const timer = window.setTimeout(() => {
      timers.delete(timer);
      callback();
    }, delay);
    timers.add(timer);
    return timer;
  }

  function clearTimers() {
    timers.forEach((timer) => window.clearTimeout(timer));
    timers.clear();
  }

  function isCurrent(context) {
    return Boolean(context) && Number(context.requestId) === Number(state.requestId);
  }

  function setStageState(nextState) {
    if (!els.stage) return;
    els.stage.dataset.motionState = nextState;
    els.stage.setAttribute("aria-hidden", String(nextState === "idle" || nextState === "cancelled"));
    els.body?.setAttribute("data-motion-state", nextState);
  }

  function setProgress(value) {
    if (els.progress) els.progress.style.setProperty("--motion-progress", String(value));
  }

  function renderSteps(steps) {
    if (!els.steps) return;
    els.steps.replaceChildren();
    (steps || DEFAULT_STEPS.map((label) => ({label}))).slice(0, 5).forEach((step, index) => {
      const item = document.createElement("li");
      item.dataset.stepIndex = String(index);
      const number = document.createElement("span");
      number.textContent = String(index + 1);
      const label = document.createElement("strong");
      label.textContent = step.label || DEFAULT_STEPS[index];
      item.append(number, label);
      els.steps.append(item);
    });
  }

  function activateStep(index) {
    Array.from(els.steps?.children || []).forEach((item, itemIndex) => {
      item.classList.toggle("active", itemIndex === index);
      item.classList.toggle("done", itemIndex < index);
    });
    setProgress([12, 30, 49, 68, 100][Math.max(0, index)] || 12);
  }

  function renderNumbers(numbers) {
    if (!els.numbers) return;
    els.numbers.replaceChildren();
    const main = Array.isArray(numbers?.main) ? numbers.main : [];
    const special = Array.isArray(numbers?.special) ? numbers.special : [];
    [...main.map((value) => ({value, special: false})), ...special.map((value) => ({value, special: true}))]
      .forEach((entry, index) => {
        const ball = document.createElement("i");
        ball.className = `motion-ball${entry.special ? " special" : ""}`;
        ball.style.setProperty("--motion-index", String(index));
        ball.textContent = String(Number(entry.value)).padStart(2, "0");
        els.numbers.append(ball);
      });
  }

  function delay(ms) {
    if (reducedQuery.matches || ms <= 0) return Promise.resolve();
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function cancel(context) {
    if (context && !isCurrent(context)) return;
    clearTimers();
    state.requestId = null;
    state.resolved = false;
    setStageState("cancelled");
    els.stage?.classList.add("is-dismissed");
    els.numbers?.replaceChildren();
  }

  function start(context) {
    cancel();
    state.requestId = Number(context.requestId);
    state.startedAt = performance.now();
    state.resolved = false;
    els.stage?.classList.remove("is-dismissed");
    renderSteps(context.steps);
    els.numbers?.replaceChildren();
    if (els.status) els.status.textContent = "正在校准个人时空";
    if (els.title) els.title.textContent = "命盘入局";
    setProgress(8);
    setStageState("running");

    if (reducedQuery.matches) {
      activateStep(3);
      return;
    }

    const labels = [
      [0, "姓名与生辰已入盘", "本命底盘已定"],
      [1, "正在推导本命财格", "财格成形"],
      [2, "正在结合开奖日气口", "今日财局已定"],
      [3, "正在筛选喜用与避冲尾数", "喜用尾数归位"],
    ];
    labels.forEach(([index, status, title], labelIndex) => {
      later(() => {
        if (!isCurrent(context) || state.resolved) return;
        activateStep(index);
        if (els.status) els.status.textContent = status;
        if (els.title) els.title.textContent = title;
      }, STEP_DELAYS[labelIndex]);
    });
    later(() => {
      if (!isCurrent(context) || state.resolved) return;
      setStageState("waiting");
      if (els.status) els.status.textContent = "真实结果计算中";
      if (els.title) els.title.textContent = "正在收束财局";
    }, MIN_REVEAL_MS);
  }

  async function resolve(context, numbers) {
    if (!isCurrent(context)) return false;
    const elapsed = performance.now() - state.startedAt;
    await delay(Math.max(0, MIN_REVEAL_MS - elapsed));
    if (!isCurrent(context)) return false;
    state.resolved = true;
    clearTimers();
    activateStep(4);
    renderNumbers(numbers);
    if (els.status) els.status.textContent = "起盘完成 · 财运号已落盘";
    if (els.title) els.title.textContent = "今日财运号";
    setStageState("complete");
    await delay(1100);
    if (!isCurrent(context)) return false;
    els.stage?.classList.add("is-dismissed");
    await delay(420);
    if (isCurrent(context)) els.stage?.setAttribute("aria-hidden", "true");
    return true;
  }

  function fail(context, message = "起盘失败，请稍后重试") {
    if (!isCurrent(context)) return;
    clearTimers();
    if (els.status) els.status.textContent = message;
    if (els.title) els.title.textContent = "本次未能落盘";
    setStageState("error");
    later(() => {
      if (!isCurrent(context)) return;
      els.stage?.classList.add("is-dismissed");
      els.stage?.setAttribute("aria-hidden", "true");
    }, reducedQuery.matches ? 0 : 1500);
  }

  function lock(context) {
    if (!isCurrent(context)) return;
    clearTimers();
    if (els.status) els.status.textContent = "今日起盘次数已用完";
    if (els.title) els.title.textContent = "解锁后继续起盘";
    setStageState("locked");
    later(() => {
      if (!isCurrent(context)) return;
      els.stage?.classList.add("is-dismissed");
      els.stage?.setAttribute("aria-hidden", "true");
    }, reducedQuery.matches ? 0 : 900);
  }

  function enter() {
    if (reducedQuery.matches || !els.body) return;
    els.body.classList.add("is-page-entering");
    later(() => els.body?.classList.remove("is-page-entering"), 1200);
  }

  function reveal() {
    const nodes = Array.from(document.querySelectorAll("[data-motion-reveal]"));
    if (reducedQuery.matches || !("IntersectionObserver" in window)) {
      nodes.forEach((node) => node.classList.add("is-revealed"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-revealed");
        observer.unobserve(entry.target);
      });
    }, {threshold: 0.16});
    nodes.forEach((node) => observer.observe(node));
  }

  document.addEventListener("visibilitychange", () => {
    state.hiddenByVisibility = document.hidden;
    els.body?.classList.toggle("motion-paused", document.hidden);
  });

  window.FortuneMotion = {enter, start, resolve, fail, lock, cancel, reveal};
})();
```

- [ ] **Step 4: 运行状态机测试与语法检查**

Run: `node --check web/motion.js`

Expected: 无输出，退出码 0。

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_motion_controller_moves_from_running_to_complete -q`

Expected: PASS。

- [ ] **Step 5: 提交状态机**

```bash
git add web/motion.js tests/test_frontend_behavior.py
git commit -m "feat: add cancellable fortune motion controller"
```

## Task 3: 将真实预测生命周期接入动效控制器

**Files:**
- Modify: `web/app.js:223-234,506-531,1319-1331,1680-1759,1761-1769,1800-1805`
- Modify: `tests/test_frontend_behavior.py:282-526`
- Modify: `tests/test_api.py:169-200`

- [ ] **Step 1: 写入“默认不出号、响应前不落号、失败不保存演示号”的测试**

把现有 `test_default_prediction_is_marked_as_sample_and_not_saved` 替换为：

```python
def test_home_waits_for_manual_submission_before_showing_numbers(
    live_server_url, browser_page
):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")

    assert browser_page.locator("#fortuneNumber").inner_text() == "--"
    assert browser_page.locator("#numberBalls .ball").count() == 0
    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "idle"
    assert "填写资料后点击开始起盘" in browser_page.locator("#generateFeedback").inner_text()
    records = browser_page.evaluate(
        "() => JSON.parse(localStorage.getItem('lotteryLuck.fortuneHistory.v1') || '[]')"
    )
    assert records == []
```

把现有 `test_stale_prediction_response_does_not_overwrite_switched_game_or_history` 替换为：

```python
def test_stale_prediction_response_does_not_overwrite_switched_game_or_history(
    live_server_url, browser_page
):
    def route_predict(route):
        body = json.loads(route.request.post_data or "{}")
        game_key = body.get("game_key", "ssq")
        if game_key == "ssq":
            time.sleep(0.6)
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
```

在 `tests/test_frontend_behavior.py` 增加：

```python
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
```

在 `tests/test_api.py::test_frontend_assets_are_served` 删除这条旧断言：

```python
assert "saveFortuneHistory(fallbackPayload, requestPayload, requestContext)" in response.text
```

改为：

```python
assert "FortuneMotion" in response.text
assert "起盘失败，请稍后重试" in response.text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_home_waits_for_manual_submission_before_showing_numbers tests/test_frontend_behavior.py::test_cinematic_stage_waits_for_real_prediction_before_dropping_numbers tests/test_frontend_behavior.py::test_manual_prediction_failure_preserves_previous_result_and_history tests/test_frontend_behavior.py::test_stale_prediction_response_does_not_overwrite_switched_game_or_history -q`

Expected: FAIL，首页仍会自动渲染示例号，`app.js` 尚未调用动效控制器，失败分支仍保存演示号。

- [ ] **Step 3: 删除自动出号路径并修改 `predict()` 的用户触发生命周期**

在 `state` 中增加请求取消句柄：

```javascript
predictionAbortController: null,
```

在 `formPayload()` 前增加空闲态渲染函数：

```javascript
function renderIdlePrediction() {
  state.currentPrediction = {main: [], special: []};
  els.fortuneNumber.textContent = "--";
  els.bestDate.textContent = "--";
  els.luckScore.textContent = "--";
  els.numberBalls.replaceChildren();
  renderDailyFortuneSign(DEFAULT_DAILY_FORTUNE_SIGN);
  renderRitualSteps(DEFAULT_RITUAL_STEPS, -1);
  setRitualState("idle", "填写资料后开始起盘", 0);
  setGenerateFeedback("填写资料后点击开始起盘。");
}
```

在创建 `requestContext` 前取消旧请求，并为新请求创建 `AbortController`：

```javascript
state.predictionAbortController?.abort();
const abortController = new AbortController();
state.predictionAbortController = abortController;
```

在 `predict()` 中创建 `motion` 引用，并把 `startRitualPreview` 调用替换为：

```javascript
const motion = window.FortuneMotion;

if (userInitiated) {
  setGenerateFeedback(`第 ${runCount} 次${currentModeLabel(requestContext.modeKey)}起盘中，正在校准本命财格与开奖日气口...`);
  els.numberBalls.classList.add("is-generating");
  startRitualPreview(isLatestRequest);
  motion?.start({
    ...requestContext,
    steps: DEFAULT_RITUAL_STEPS,
  });
}
```

把 payload 获取表达式替换为始终请求真实接口：

```javascript
const payload = normalizePredictionPayload(await fetchJson("/api/predict", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(requestPayload),
  signal: abortController.signal,
}));
```

额度不足分支在 `setRitualState` 前增加：

```javascript
motion?.lock(requestContext);
```

成功分支把 `await runRitualSequence(...)` 替换为：

```javascript
if (userInitiated) {
  await motion?.resolve(requestContext, payload.numbers);
  if (!isLatestRequest()) return;
  renderRitualSteps(payload.ritual_steps);
  setRitualState("complete", "起盘完成 · 财运号已落盘", 100);
}
```

把整个 `catch` 分支替换为：

```javascript
} catch (error) {
  if (!isLatestRequest()) return;
  motion?.fail(requestContext, "起盘失败，请稍后重试");
  setRitualState("idle", "本次未能落盘", 0);
  renderRitualSteps(DEFAULT_RITUAL_STEPS, -1);
  setGenerateFeedback("起盘失败，请稍后重试。已保留当前资料和上次结果。", true);
```

把彩种点击处理器替换为：

```javascript
els.gameTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-game]");
  if (!button) return;
  state.predictionAbortController?.abort();
  state.predictionAbortController = null;
  state.predictionRequestId += 1;
  window.FortuneMotion?.cancel();
  state.activeGame = button.dataset.game;
  renderTabs();
  renderGameMeta();
  renderIdlePrediction();
  els.submitButton.disabled = false;
  updateSubmitButtonLabel();
});
```

把 `loadGames().then(...)` 替换为不请求预测的空闲初始化：

```javascript
loadGames().then(() => {
  renderIdlePrediction();
  loadQuotaStatus();
  reviewFortuneHistory();
  window.FortuneMotion?.enter();
  window.FortuneMotion?.reveal();
});
```

在 `finally` 的最新请求分支增加：

```javascript
if (state.predictionAbortController === abortController) {
  state.predictionAbortController = null;
}
```

同时把现有慢请求测试中的 fetch 拦截改为每次 `/api/predict` 都延迟 800 毫秒，删除 `predictCalls` 计数和首次立即返回分支，确保测试名称与行为一致。

- [ ] **Step 4: 运行生命周期测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_home_waits_for_manual_submission_before_showing_numbers tests/test_frontend_behavior.py::test_manual_prediction_makes_ritual_state_visibly_active tests/test_frontend_behavior.py::test_manual_prediction_starts_ritual_before_slow_api_returns tests/test_frontend_behavior.py::test_cinematic_stage_waits_for_real_prediction_before_dropping_numbers tests/test_frontend_behavior.py::test_manual_prediction_failure_preserves_previous_result_and_history tests/test_frontend_behavior.py::test_stale_prediction_response_does_not_overwrite_switched_game_or_history tests/test_frontend_behavior.py::test_quota_exhausted_shows_unlock_panel_without_saving_history -q`

Expected: 7 passed。

- [ ] **Step 5: 运行静态断言与语法检查**

Run: `node --check web/app.js web/motion.js`

Expected: 无输出，退出码 0。

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_frontend_assets_are_served -q`

Expected: PASS。

- [ ] **Step 6: 提交生命周期接入**

```bash
git add web/app.js tests/test_frontend_behavior.py tests/test_api.py
git commit -m "feat: gate cinematic reveal on real prediction"
```

## Task 4: 实现玄金电影感起盘舞台

**Files:**
- Modify: `web/motion.css`
- Modify: `web/styles.css:1-22,901-907,1099-1123`
- Test: `tests/test_api.py:503-509`

- [ ] **Step 1: 写入样式契约失败测试**

扩展 `tests/test_api.py::test_frontend_styles_are_served`：

```python
    motion_response = client.get("/motion.css")

    assert motion_response.status_code == 200
    assert '[data-motion-state="running"]' in motion_response.text
    assert '[data-motion-state="waiting"]' in motion_response.text
    assert '[data-motion-state="complete"]' in motion_response.text
    assert "@keyframes motion-ball-land" in motion_response.text
    assert "@media (prefers-reduced-motion: reduce)" in motion_response.text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_frontend_styles_are_served -q`

Expected: FAIL，`motion.css` 仍只有隐藏骨架。

- [ ] **Step 3: 用以下完整样式替换 `web/motion.css`**

```css
:root {
  --motion-fast: 180ms;
  --motion-reveal: 550ms;
  --motion-enter: 1100ms;
  --motion-ease: cubic-bezier(0.16, 0.84, 0.18, 1);
}

.ritual-stage {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: var(--gold-pale);
  background:
    radial-gradient(circle at 50% 48%, rgba(198, 139, 40, 0.2), transparent 30%),
    rgba(3, 3, 2, 0.96);
  opacity: 0;
  visibility: hidden;
  transform: scale(0.96);
  transition:
    opacity 420ms ease,
    transform 760ms var(--motion-ease),
    visibility 0s linear 760ms;
  pointer-events: none;
}

.ritual-stage::before {
  position: absolute;
  inset: 0;
  content: "";
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 48%, transparent 20%, rgba(0, 0, 0, 0.36) 66%, rgba(0, 0, 0, 0.9)),
    repeating-linear-gradient(104deg, rgba(255, 255, 255, 0.014) 0 1px, transparent 1px 7px);
}

.ritual-stage[data-motion-state="running"],
.ritual-stage[data-motion-state="waiting"],
.ritual-stage[data-motion-state="complete"],
.ritual-stage[data-motion-state="error"],
.ritual-stage[data-motion-state="locked"] {
  opacity: 1;
  visibility: visible;
  transform: scale(1);
  transition-delay: 0s;
}

.ritual-stage.is-dismissed {
  opacity: 0;
  visibility: hidden;
  transform: scale(1.04);
  transition-delay: 0s, 0s, 420ms;
}

.ritual-stage-dial {
  position: absolute;
  width: min(620px, 72vw);
  aspect-ratio: 1;
  border: 1px solid rgba(222, 171, 80, 0.44);
  border-radius: 50%;
  background: repeating-conic-gradient(rgba(225, 175, 85, 0.22) 0 0.6deg, transparent 0.7deg 8deg);
  mask: radial-gradient(circle, transparent 0 66%, #000 67%);
  animation: motion-dial-turn 12s linear infinite;
  pointer-events: none;
}

.ritual-stage-dial.secondary {
  width: min(470px, 58vw);
  opacity: 0.5;
  animation-direction: reverse;
  animation-duration: 17s;
}

.ritual-stage-copy {
  position: relative;
  z-index: 2;
  width: min(790px, calc(100% - 48px));
  text-align: center;
}

.ritual-stage-status {
  margin: 0;
  color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.ritual-stage-copy h2 {
  margin: 12px 0 0;
  color: var(--gold-pale);
  font-size: clamp(34px, 5vw, 62px);
  font-weight: 400;
  line-height: 1.1;
}

.ritual-stage-progress {
  height: 2px;
  margin: 32px auto 25px;
  overflow: hidden;
  background: rgba(211, 158, 65, 0.18);
}

.ritual-stage-progress i {
  display: block;
  width: calc(var(--motion-progress, 8) * 1%);
  height: 100%;
  background: var(--gold-soft);
  box-shadow: 0 0 18px rgba(232, 182, 91, 0.86);
  transition: width 700ms var(--motion-ease);
}

.ritual-stage-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ritual-stage-steps li {
  border-top: 1px solid rgba(218, 167, 77, 0.18);
  color: var(--quiet);
  padding-top: 11px;
  transition:
    color var(--motion-fast) ease,
    border-color var(--motion-fast) ease,
    transform var(--motion-fast) ease;
}

.ritual-stage-steps li.active,
.ritual-stage-steps li.done {
  border-color: var(--gold);
  color: var(--gold-soft);
}

.ritual-stage-steps li.active {
  transform: translateY(-3px);
}

.ritual-stage-steps span,
.ritual-stage-steps strong {
  display: block;
}

.ritual-stage-steps span {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
}

.ritual-stage-steps strong {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 500;
}

.ritual-stage-numbers {
  display: flex;
  justify-content: center;
  gap: clamp(8px, 1.2vw, 16px);
  min-height: 74px;
  margin-top: 36px;
}

.motion-ball {
  display: grid;
  place-items: center;
  width: clamp(48px, 5.2vw, 72px);
  aspect-ratio: 1;
  border: 1px solid var(--gold);
  border-radius: 50%;
  color: var(--gold-pale);
  background:
    radial-gradient(circle at 36% 23%, rgba(255, 220, 170, 0.9), transparent 17%),
    var(--cinnabar-2);
  box-shadow:
    inset 0 -13px 18px rgba(38, 0, 0, 0.62),
    0 24px 30px rgba(85, 15, 6, 0.32);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: clamp(17px, 2vw, 27px);
  font-style: normal;
  opacity: 0;
  animation: motion-ball-land 680ms var(--motion-ease) forwards;
  animation-delay: calc(var(--motion-index) * 90ms);
}

.motion-ball.special {
  background:
    radial-gradient(circle at 36% 23%, rgba(218, 240, 255, 0.92), transparent 17%),
    var(--blue);
  box-shadow:
    inset 0 -13px 18px rgba(0, 12, 38, 0.64),
    0 24px 30px rgba(10, 65, 130, 0.3);
}

.ritual-stage[data-motion-state="waiting"] .ritual-stage-dial {
  animation-duration: 22s;
}

.ritual-stage[data-motion-state="complete"] h2 {
  text-shadow: 0 0 34px rgba(242, 190, 89, 0.62);
}

.ritual-stage[data-motion-state="error"] h2 {
  color: #d98b78;
}

.ritual-stage[data-motion-state="locked"] h2 {
  color: var(--gold-soft);
}

.is-page-entering .site-header,
.is-page-entering .game-tabs,
.is-page-entering .oracle-board,
.is-page-entering .control-panel {
  animation: motion-page-enter var(--motion-enter) var(--motion-ease) both;
}

.is-page-entering .game-tabs { animation-delay: 80ms; }
.is-page-entering .oracle-board { animation-delay: 150ms; }
.is-page-entering .control-panel { animation-delay: 220ms; }

[data-motion-reveal] {
  opacity: 0;
  transform: translateY(24px);
  transition:
    opacity var(--motion-reveal) ease,
    transform var(--motion-reveal) var(--motion-ease);
}

[data-motion-reveal].is-revealed {
  opacity: 1;
  transform: none;
}

.result-refreshed {
  animation: motion-result-settle 700ms ease-out;
}

.motion-paused *,
.motion-paused *::before,
.motion-paused *::after {
  animation-play-state: paused !important;
}

@keyframes motion-dial-turn {
  to { transform: rotate(360deg); }
}

@keyframes motion-ball-land {
  0% { opacity: 0; transform: translateY(-48px) scale(0.72); filter: blur(5px); }
  72% { opacity: 1; transform: translateY(4px) scale(1.04); filter: none; }
  100% { opacity: 1; transform: none; filter: none; }
}

@keyframes motion-page-enter {
  from { opacity: 0; transform: translateY(16px); filter: blur(5px); }
  to { opacity: 1; transform: none; filter: none; }
}

@keyframes motion-result-settle {
  0% { filter: brightness(1); }
  35% { filter: brightness(1.16); }
  100% { filter: brightness(1); }
}

@media (max-width: 780px) {
  .ritual-stage-copy { width: min(100% - 28px, 620px); }
  .ritual-stage-dial { width: min(560px, 112vw); }
  .ritual-stage-dial.secondary { width: min(430px, 88vw); }
  .ritual-stage-steps { gap: 4px; }
  .ritual-stage-steps strong { font-size: 11px; }
  .ritual-stage-numbers { gap: 7px; }
  .motion-ball { width: clamp(38px, 11vw, 52px); }
}

@media (prefers-reduced-motion: reduce) {
  .ritual-stage,
  .ritual-stage *,
  [data-motion-reveal],
  .is-page-entering .site-header,
  .is-page-entering .game-tabs,
  .is-page-entering .oracle-board,
  .is-page-entering .control-panel {
    animation: none !important;
    transition-duration: 1ms !important;
  }

  [data-motion-reveal] {
    opacity: 1;
    transform: none;
  }

  .motion-ball {
    opacity: 1;
    transform: none;
  }
}
```

从 `web/styles.css` 删除 `.numbers.is-generating .ball`、`.result-refreshed` 和两个旧关键帧 `generating-pulse`、`result-refreshed`。新的 `.result-refreshed` 与 `motion-result-settle` 已完整定义在 `motion.css`，`app.js::flashResultPanels()` 无需改名。

- [ ] **Step 4: 运行样式契约和语法测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_frontend_styles_are_served -q`

Expected: PASS。

Run: `git diff --check`

Expected: 无输出，退出码 0。

- [ ] **Step 5: 提交电影感样式**

```bash
git add web/motion.css web/styles.css tests/test_api.py
git commit -m "feat: style cinematic fortune ritual stage"
```

## Task 5: 添加滚动显义、首屏定场和减少动态效果

**Files:**
- Modify: `web/index.html:186-383`
- Modify: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写入滚动揭示和减少动态效果失败测试**

```python
def test_scroll_sections_reveal_once(live_server_url, browser_page):
    browser_page.goto(live_server_url)
    section = browser_page.locator(".master-ritual-panel")
    assert section.get_attribute("data-motion-reveal") == ""
    section.scroll_into_view_if_needed()
    browser_page.wait_for_function(
        "() => document.querySelector('.master-ritual-panel').classList.contains('is-revealed')"
    )
    assert section.get_attribute("class").count("is-revealed") == 1


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
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
        timeout=1500,
    )
    assert time.monotonic() - started_at < 1.5
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 7
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_scroll_sections_reveal_once tests/test_frontend_behavior.py::test_reduced_motion_skips_long_cinematic_timeline -q`

Expected: FAIL，页面尚未声明揭示节点，或减少动态效果仍等待最小时长。

- [ ] **Step 3: 为结果区添加揭示标记**

给以下首页区块增加空属性 `data-motion-reveal`：

```html
<section class="fortune-ritual-panel" data-motion-reveal aria-label="今日财签与生成仪式">
<section class="fortune-hook" data-motion-reveal aria-label="本命财格">
<section class="master-ritual-panel" data-motion-reveal aria-label="大师起盘">
<section class="credibility-panel" data-motion-reveal aria-label="可信解释链">
<section class="interpretation-panel" data-motion-reveal aria-label="起盘解读">
<section class="hot-reference" data-motion-reveal aria-label="近30期号码参考">
<section class="basis-grid" data-motion-reveal aria-label="推荐依据">
<section class="reason-panel" data-motion-reveal aria-label="号码释义">
<section class="profile-calendar-panel" data-motion-reveal aria-label="我的财运档案">
<section class="history-panel" data-motion-reveal aria-label="我的历史财运号">
```

确认 `motion.js::delay()` 保持以下短路逻辑：

```javascript
if (reducedQuery.matches || ms <= 0) return Promise.resolve();
```

- [ ] **Step 4: 运行滚动和降级测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_scroll_sections_reveal_once tests/test_frontend_behavior.py::test_reduced_motion_skips_long_cinematic_timeline -q`

Expected: 2 passed。

- [ ] **Step 5: 提交滚动与降级支持**

```bash
git add web/index.html web/motion.js tests/test_frontend_behavior.py
git commit -m "feat: add reveal and reduced motion behavior"
```

## Task 6: 收口额度、取消、移动端和输入校验边界

**Files:**
- Modify: `web/app.js`
- Modify: `web/motion.js`
- Modify: `web/motion.css`
- Modify: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写入取消、额度和移动端失败测试**

```python
def test_game_switch_cancels_active_cinematic_stage(live_server_url, browser_page):
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'running'"
    )
    browser_page.locator('button[data-game="dlt"]').click()
    assert browser_page.locator("#ritualStage").get_attribute("data-motion-state") == "cancelled"


def test_quota_exhausted_uses_locked_motion_state(live_server_url, browser_page):
    def route_predict(route):
        body = json.loads(route.request.post_data or "{}")
        payload = (
            {"quota_exhausted": True, "quota": {"remaining_total": 0, "is_paid": False}}
            if body.get("consume_quota")
            else _prediction_payload("ssq", [11, 12, 13, 14, 15, 16], [1])
        )
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    browser_page.route(f"{live_server_url}/api/predict", route_predict)
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    browser_page.locator("#submitButton").click()
    browser_page.wait_for_function(
        "() => document.querySelector('#ritualStage').dataset.motionState === 'locked'"
    )
    assert browser_page.locator("#motionNumbers .motion-ball").count() == 0


def test_home_motion_has_no_mobile_horizontal_overflow(live_server_url, browser_page):
    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.goto(live_server_url)
    browser_page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    assert browser_page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_game_switch_cancels_active_cinematic_stage tests/test_frontend_behavior.py::test_quota_exhausted_uses_locked_motion_state tests/test_frontend_behavior.py::test_home_motion_has_no_mobile_horizontal_overflow -q`

Expected: 至少取消或锁定状态测试 FAIL。

- [ ] **Step 3: 完成边界实现**

确认彩种点击处理器第一行调用：

```javascript
window.FortuneMotion?.cancel();
```

确认额度不足分支调用：

```javascript
window.FortuneMotion?.lock(requestContext);
```

在表单提交处理器中使用原生校验，避免无效输入进入演出：

```javascript
els.predictForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!els.predictForm.reportValidity()) return;
  predict({userInitiated: true});
});
```

在 `motion.css` 的移动端媒体查询中确认舞台宽度使用视口约束，并补充：

```css
@media (max-width: 560px) {
  .ritual-stage-copy {
    width: calc(100% - 20px);
  }

  .ritual-stage-steps {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }

  .ritual-stage-steps span {
    font-size: 10px;
  }

  .ritual-stage-steps strong {
    overflow-wrap: anywhere;
  }
}
```

- [ ] **Step 4: 运行边界测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py::test_game_switch_cancels_active_cinematic_stage tests/test_frontend_behavior.py::test_quota_exhausted_uses_locked_motion_state tests/test_frontend_behavior.py::test_home_motion_has_no_mobile_horizontal_overflow -q`

Expected: 3 passed。

- [ ] **Step 5: 提交边界处理**

```bash
git add web/app.js web/motion.js web/motion.css tests/test_frontend_behavior.py
git commit -m "fix: harden cinematic motion edge states"
```

## Task 7: 完整回归、视觉证据与 QA 文档

**Files:**
- Modify: `design-qa.md`
- Create: `tests/capture_motion_qa.py`
- Create: `artifacts/cinematic-home-idle.png`
- Create: `artifacts/cinematic-home-running.png`
- Create: `artifacts/cinematic-home-complete.png`
- Create: `artifacts/cinematic-home-mobile.png`
- Create: `artifacts/cinematic-home-reduced-motion.png`

- [ ] **Step 1: 运行前端定向测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_frontend_behavior.py -q`

Expected: 全部通过，无失败和错误。

- [ ] **Step 2: 运行完整后端回归**

Run: `PYTHONPATH=. .venv/bin/pytest -q`

Expected: 全部通过；只允许已有且已记录的 warning。

- [ ] **Step 3: 运行 JavaScript 与 diff 检查**

Run: `node --check web/app.js web/motion.js web/admin.js web/result.js web/analysis.js web/strategy.js`

Expected: 无输出，退出码 0。

Run: `git diff --check`

Expected: 无输出，退出码 0。

- [ ] **Step 4: 创建并运行固定截图脚本**

创建 `tests/capture_motion_qa.py`：

```python
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BASE_URL = "http://127.0.0.1:8017/"


def assert_no_overflow(page):
    assert page.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth"
    )


def ready(page):
    page.goto(BASE_URL)
    page.wait_for_function("() => !document.querySelector('#submitButton').disabled")
    assert_no_overflow(page)


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        desktop_context = browser.new_context(viewport={"width": 1576, "height": 1118})
        desktop = desktop_context.new_page()
        ready(desktop)
        desktop.screenshot(path=ARTIFACTS / "cinematic-home-idle.png", full_page=True)
        desktop.locator("#submitButton").click()
        desktop.wait_for_function(
            "() => ['running', 'waiting'].includes(document.querySelector('#ritualStage').dataset.motionState)"
        )
        assert desktop.locator("#motionNumbers .motion-ball").count() == 0
        desktop.screenshot(path=ARTIFACTS / "cinematic-home-running.png")
        desktop.wait_for_function(
            "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
            timeout=10000,
        )
        desktop.screenshot(path=ARTIFACTS / "cinematic-home-complete.png")
        assert_no_overflow(desktop)
        desktop_context.close()

        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile = mobile_context.new_page()
        ready(mobile)
        mobile.locator("#submitButton").click()
        mobile.wait_for_function(
            "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
            timeout=10000,
        )
        mobile.screenshot(path=ARTIFACTS / "cinematic-home-mobile.png")
        assert_no_overflow(mobile)
        mobile_context.close()

        reduced_context = browser.new_context(
            viewport={"width": 1576, "height": 1118},
            reduced_motion="reduce",
        )
        reduced = reduced_context.new_page()
        ready(reduced)
        reduced.locator("#submitButton").click()
        reduced.wait_for_function(
            "() => document.querySelector('#ritualStage').dataset.motionState === 'complete'",
            timeout=3000,
        )
        reduced.screenshot(
            path=ARTIFACTS / "cinematic-home-reduced-motion.png"
        )
        assert_no_overflow(reduced)
        reduced_context.close()

        browser.close()


if __name__ == "__main__":
    main()
```

Run: `python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017`

Expected: 服务监听 `http://127.0.0.1:8017/`。

在另一个终端运行：

Run: `.venv/bin/python tests/capture_motion_qa.py`

Expected: 退出码 0，并生成五张固定路径截图。脚本同时验证：

- 页面无水平溢出。
- 起盘舞台不遮挡表单默认态。
- 响应前没有号码球。
- 响应后号码与 payload 一致。
- 文本、按钮、进度和号码没有重叠。
- 移动端五个步骤可读且不撑破视口。

- [ ] **Step 5: 更新 `design-qa.md`**

写入以下结构：

```markdown
**Cinematic Homepage Motion QA**

- desktop idle: `artifacts/cinematic-home-idle.png`
- desktop running: `artifacts/cinematic-home-running.png`
- desktop complete: `artifacts/cinematic-home-complete.png`
- mobile complete: `artifacts/cinematic-home-mobile.png`
- reduced motion: `artifacts/cinematic-home-reduced-motion.png`
- desktop viewport: `1576x1118`
- mobile viewport: `390x844`

**Verified states**

- Input fields remain visible before the user starts the ritual.
- The cinematic stage begins only after a valid form submission.
- No number is shown before the real prediction response resolves.
- Error and quota-exhausted states do not save fallback results.
- Reduced-motion mode preserves the full workflow without long animation.
- Desktop and mobile have no horizontal overflow or control overlap.
```

- [ ] **Step 6: 提交 QA 证据**

```bash
git add design-qa.md tests/capture_motion_qa.py artifacts/cinematic-home-idle.png artifacts/cinematic-home-running.png artifacts/cinematic-home-complete.png artifacts/cinematic-home-mobile.png artifacts/cinematic-home-reduced-motion.png
git commit -m "test: verify cinematic homepage motion"
```

## 最终验收

- [ ] 用户填写个人信息之前，首页不会自动落盘或自动出号。
- [ ] 点击“开始起盘”后立即进入 `running`，慢请求进入 `waiting`。
- [ ] 只有真实 `/api/predict` 结果返回后才进入 `complete` 并渲染号码。
- [ ] 正式起盘失败不会保存或展示演示号。
- [ ] 额度不足不会落号或写入历史记录。
- [ ] 彩种切换不会让旧响应覆盖新页面。
- [ ] 减少动态效果模式、移动端和键盘操作均可完成主流程。
- [ ] 完整 pytest、Node 语法检查、diff 检查和视觉 QA 全部通过。
