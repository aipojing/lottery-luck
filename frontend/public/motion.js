(() => {
  "use strict";

  const STEP_DELAYS = [420, 900, 1380, 1860];
  const MIN_REVEAL_MS = 2200;
  const DEFAULT_STEPS = ["定命盘", "排财格", "定财局", "取尾数", "落财号"];
  const timers = new Set();
  const delays = new Set();
  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const state = {
    requestId: null,
    startedAt: 0,
    resolved: false,
    hiddenByVisibility: false,
    token: 0,
  };
  let revealObserver = null;
  const revealTracked = new Set();

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

  function cancelDelays() {
    delays.forEach((waiter) => {
      window.clearTimeout(waiter.timer);
      waiter.resolve(false);
    });
    delays.clear();
  }

  function clearMotionWork() {
    clearTimers();
    cancelDelays();
    state.token += 1;
  }

  function isCurrent(context) {
    return Boolean(context) && Number(context.requestId) === Number(state.requestId);
  }

  function isActive(context, token) {
    return isCurrent(context) && token === state.token;
  }

  function getRequestId(context) {
    if (context?.requestId === null || context?.requestId === undefined || context?.requestId === "") {
      return null;
    }
    const requestId = Number(context?.requestId);
    return Number.isFinite(requestId) ? requestId : null;
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

  function delay(ms, token) {
    if (token !== state.token) return Promise.resolve(false);
    if (reducedQuery.matches || ms <= 0) return Promise.resolve(true);
    return new Promise((resolve) => {
      const waiter = {
        timer: null,
        resolve,
        token,
      };
      waiter.timer = window.setTimeout(() => {
        delays.delete(waiter);
        resolve(token === state.token);
      }, ms);
      delays.add(waiter);
    });
  }

  function cancel(context) {
    if (context && !isCurrent(context)) return;
    clearMotionWork();
    state.requestId = null;
    state.resolved = false;
    setStageState("cancelled");
    els.stage?.classList.add("is-dismissed");
    els.numbers?.replaceChildren();
  }

  function start(context) {
    const requestId = getRequestId(context);
    if (requestId === null) return false;
    cancel();
    state.requestId = requestId;
    state.startedAt = performance.now();
    state.resolved = false;
    els.stage?.classList.remove("is-dismissed");
    renderSteps(context?.steps);
    els.numbers?.replaceChildren();
    if (els.status) els.status.textContent = "正在校准个人时空";
    if (els.title) els.title.textContent = "命盘入局";
    setProgress(8);
    setStageState("running");

    if (reducedQuery.matches) {
      activateStep(3);
      return true;
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
    return true;
  }

  async function resolve(context, numbers) {
    if (!isCurrent(context)) return false;
    const token = state.token;
    const elapsed = performance.now() - state.startedAt;
    if (!(await delay(Math.max(0, MIN_REVEAL_MS - elapsed), token))) return false;
    if (!isActive(context, token)) return false;
    state.resolved = true;
    clearTimers();
    if (!isActive(context, token)) return false;
    activateStep(4);
    renderNumbers(numbers);
    if (els.status) els.status.textContent = "起盘完成 · 财运号已落盘";
    if (els.title) els.title.textContent = "今日财运号";
    setStageState("complete");
    if (!(await delay(1100, token))) return false;
    if (!isActive(context, token)) return false;
    els.stage?.classList.add("is-dismissed");
    if (!(await delay(420, token))) return false;
    if (!isActive(context, token)) return false;
    els.stage?.setAttribute("aria-hidden", "true");
    return true;
  }

  function fail(context, message = "起盘失败，请稍后重试") {
    if (!isCurrent(context)) return;
    clearMotionWork();
    if (els.status) els.status.textContent = message;
    if (els.title) els.title.textContent = "本次未能落盘";
    setStageState("error");
    later(() => {
      if (!isCurrent(context)) return;
      els.stage?.classList.add("is-dismissed");
      els.stage?.setAttribute("aria-hidden", "true");
    }, reducedQuery.matches ? 0 : 1500);
  }

  function enter() {
    if (reducedQuery.matches || !els.body) return;
    els.body.classList.add("is-page-entering");
    later(() => els.body?.classList.remove("is-page-entering"), 1200);
  }

  function reveal() {
    const nodes = Array.from(document.querySelectorAll("[data-motion-reveal]"));
    if (reducedQuery.matches || !("IntersectionObserver" in window)) {
      revealTracked.clear();
      nodes.forEach((node) => {
        node.classList.remove("will-reveal");
        node.classList.add("is-revealed");
      });
      return;
    }
    if (!revealObserver) {
      revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-revealed");
          revealObserver?.unobserve(entry.target);
          revealTracked.delete(entry.target);
        });
      }, {threshold: 0.16});
    }
    nodes.forEach((node) => {
      if (node.classList.contains("is-revealed") || revealTracked.has(node)) return;
      node.classList.add("will-reveal");
      revealTracked.add(node);
      revealObserver.observe(node);
    });
  }

  document.addEventListener("visibilitychange", () => {
    state.hiddenByVisibility = document.hidden;
    els.body?.classList.toggle("motion-paused", document.hidden);
  });

  window.FortuneMotion = {
    enter,
    start,
    resolve,
    fail,
    cancel,
    reveal,
  };
})();
