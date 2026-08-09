(() => {
  "use strict";

  const PRESETS = ["balanced", "conservative", "aggressive"];
  const PRESET_LABELS = {
    balanced: "均衡型",
    conservative: "保守型",
    aggressive: "激进型",
  };
  const PRESET_DESCRIPTIONS = {
    balanced: "均衡型：兼顾热号、和值、奇偶和结构离散度。",
    conservative: "保守型：控制连号和近期重复，偏向稳态结构。",
    aggressive: "激进型：放宽近期限制，增加热号权重。",
  };
  // Safe fallbacks mirror the server capability matrix and are only used while (or if)
  // /api/surfaces/config is unavailable; the server payload stays the source of truth.
  const FALLBACK_CONDITION_FIELDS = {
    lotto: [
      "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
      "max_consecutive_run", "ac_min", "ac_max", "prime_composite", "mod3",
      "zone", "tail_exclude", "tail_include", "min_omission",
    ],
    digit: [
      "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
      "max_consecutive_run", "prime_composite", "mod3", "tail_exclude",
      "tail_include", "min_omission",
    ],
  };
  const NUMBER_CONDITION_FIELDS = new Set([
    "exclude_recent", "min_hot", "sum_min", "sum_max", "max_consecutive_run",
    "ac_min", "ac_max", "min_omission",
  ]);
  const TAIL_CONDITION_FIELDS = new Set(["tail_exclude", "tail_include"]);
  const NON_CONDITION_FORM_KEYS = ["candidate_count", "window"];
  const HANDOFF_KEY = "lottery_research_handoff_v1";
  const IDLE_STATUS = "历史统计不代表未来概率。";
  const MAX_SAVED_STRATEGIES = 20;

  const els = {
    strategySummary: document.querySelector("#strategySummary"),
    presetDescription: document.querySelector("#presetDescription"),
    strategyForm: document.querySelector("#strategyForm"),
    generateButton: document.querySelector("#generateButton"),
    useStrategyButton: document.querySelector("#useStrategyButton"),
    backtestButton: document.querySelector("#backtestButton"),
    compareButton: document.querySelector("#compareButton"),
    saveStrategyButton: document.querySelector("#saveStrategyButton"),
    candidateResult: document.querySelector("#candidateResult"),
    backtestResult: document.querySelector("#backtestResult"),
    savedStrategies: document.querySelector("#savedStrategies"),
    strategyStatus: document.querySelector("#strategyStatus"),
  };

  const state = {
    game: "ssq",
    preset: "balanced",
    requestToken: 0,
    capabilities: null,
    games: [],
  };

  function padNumber(value) {
    const number = Number(value);
    if (Number.isNaN(number)) return String(value);
    return String(number).padStart(2, "0");
  }

  function presetLabel(preset) {
    return PRESET_LABELS[preset] || preset;
  }

  function isDigitGame(gameKey) {
    return gameKey === "3d" || gameKey === "pl3";
  }

  async function fetchJson(url, options) {
    if (window.LotteryProduct?.request) {
      return window.LotteryProduct.request(url, options);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }
    return response.json();
  }

  function conditionFieldsFor(gameKey) {
    const fields = state.capabilities?.games?.[gameKey]?.research?.strategy?.condition_fields;
    if (Array.isArray(fields) && fields.length) return fields;
    return isDigitGame(gameKey) ? FALLBACK_CONDITION_FIELDS.digit : FALLBACK_CONDITION_FIELDS.lotto;
  }

  function setStrategyStatus(message) {
    if (!els.strategyStatus) return;
    els.strategyStatus.classList.remove("error");
    els.strategyStatus.textContent = message;
  }

  function showRetryStatus(message, retryCallback) {
    if (!els.strategyStatus) return;
    els.strategyStatus.classList.add("error");
    els.strategyStatus.replaceChildren();
    const text = document.createElement("span");
    text.textContent = message;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "mini-action subtle";
    retry.textContent = "重试";
    retry.addEventListener("click", retryCallback);
    els.strategyStatus.append(text, " ", retry);
  }

  function currentGameMeta() {
    return state.games.find((game) => game.game_key === state.game) || null;
  }

  function hasHistory() {
    const meta = currentGameMeta();
    return !meta || Number(meta.draw_count || 0) > 0;
  }

  function updateHistoryAvailability() {
    const available = hasHistory();
    if (els.backtestButton) els.backtestButton.disabled = !available;
    if (els.compareButton) els.compareButton.disabled = !available;
    if (!available) setStrategyStatus("暂无历史数据，不能回测");
  }

  function renderGameSummary() {
    if (!els.strategySummary) return;
    const meta = currentGameMeta();
    const gameName = meta?.game_name || state.game;
    const latest = meta && meta.latest_date && meta.latest_date !== "--"
      ? ` · 最新 ${meta.latest_issue || "--"} · ${meta.latest_date}`
      : "";
    els.strategySummary.textContent = `${gameName} · 策略 ${presetLabel(state.preset)}${latest} · ${IDLE_STATUS}`;
  }

  function renderPresetButtons() {
    document.querySelectorAll("#researchStrategyView [data-preset]").forEach((button) => {
      button.classList.toggle("active", button.dataset.preset === state.preset);
      button.setAttribute("aria-pressed", String(button.dataset.preset === state.preset));
    });
    if (els.presetDescription) {
      els.presetDescription.textContent = PRESET_DESCRIPTIONS[state.preset] || "选择预设或自定义条件";
    }
  }

  function renderCapabilityFields(gameKey) {
    if (!els.strategyForm) return;
    const fields = new Set(conditionFieldsFor(gameKey));
    els.strategyForm.querySelectorAll("[data-strategy-field]").forEach((label) => {
      label.hidden = !fields.has(label.dataset.strategyField);
    });
  }

  function resetConditionInputs() {
    if (!els.strategyForm) return;
    els.strategyForm.querySelectorAll("[data-strategy-field] input").forEach((input) => {
      input.value = "";
    });
  }

  function formJson(form) {
    const data = new FormData(form);
    const result = {};
    for (const [key, value] of data.entries()) {
      const text = String(value).trim();
      result[key] = text === "" ? null : Number.isNaN(Number(text)) ? text : Number(text);
    }
    return result;
  }

  // Saved rows and requests only carry the fields the current game supports, so a later
  // capability check can never see a key this game never offered.
  function currentFormJson() {
    const raw = formJson(els.strategyForm);
    const allowed = new Set([...conditionFieldsFor(state.game), ...NON_CONDITION_FORM_KEYS]);
    const result = {};
    Object.entries(raw).forEach(([key, value]) => {
      if (allowed.has(key)) result[key] = value;
    });
    return result;
  }

  function parseNumberInput(value) {
    return String(value ?? "")
      .split(/[,\s/，、]+/)
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => Number(part))
      .filter((number) => Number.isInteger(number));
  }

  function normalizedConditions(gameKey) {
    const raw = currentFormJson();
    const conditions = {};
    conditionFieldsFor(gameKey).forEach((key) => {
      const value = raw[key];
      if (value === null || value === undefined || value === "") return;
      if (NUMBER_CONDITION_FIELDS.has(key)) {
        const number = Number(value);
        if (Number.isFinite(number)) conditions[key] = number;
      } else if (TAIL_CONDITION_FIELDS.has(key)) {
        const tails = parseNumberInput(value);
        if (tails.length) conditions[key] = tails;
      } else {
        conditions[key] = String(value);
      }
    });
    return conditions;
  }

  function requestBody() {
    const raw = currentFormJson();
    return {
      preset: state.preset,
      candidate_count: Number(raw.candidate_count) || 8,
      window: Number(raw.window) || 100,
      conditions: normalizedConditions(state.game),
    };
  }

  function postBody() {
    return {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    };
  }

  // Every response is only allowed to touch the DOM while its token, game and view all
  // still match; a superseded request can never write late content into the shell.
  function responseStillCurrent(token, game) {
    return token === state.requestToken && game === state.game && window.LotteryResearch.getState().view === "strategy";
  }

  function appendMetricSummary(container, rows) {
    const summary = document.createElement("div");
    summary.className = "result-summary strategy-summary-grid";
    rows.forEach(([value, label]) => {
      const number = document.createElement("b");
      number.textContent = String(value);
      const text = document.createElement("span");
      text.textContent = label;
      summary.append(number, text);
    });
    container.append(summary);
  }

  function baselineBlock(rows) {
    const block = document.createElement("div");
    block.className = "metric-strip";
    const text = rows
      .slice(0, 5)
      .map((candidate) => {
        const special = candidate.special?.length ? ` + ${candidate.special.map(padNumber).join(" ")}` : "";
        return `${candidate.main.map(padNumber).join(" ")}${special}`;
      })
      .join("　");
    block.textContent = `随机基准：${text || "--"}`;
    return block;
  }

  // Candidate rows are explanatory only: no copy, basket or CSV controls.
  function renderCandidateList(container, payload) {
    container.replaceChildren();
    appendMetricSummary(container, [
      [payload.candidates.length, "策略候选"],
      [payload.baseline?.candidates?.length ?? 0, "随机基准"],
      [payload.diagnostics?.condition_count ?? 0, "有效条件"],
    ]);
    const list = document.createElement("ol");
    list.className = "candidate-list";
    (payload.candidates || []).slice(0, 10).forEach((candidate) => {
      const item = document.createElement("li");
      const nums = document.createElement("b");
      const special = candidate.special?.length ? ` + ${candidate.special.map(padNumber).join(" ")}` : "";
      nums.textContent = `${candidate.main.map(padNumber).join(" ")}${special}`;
      const meta = document.createElement("span");
      meta.textContent = [
        ...(candidate.tags || []),
        `012 ${candidate.mod3 || "--"}`,
        `尾 ${candidate.tail_pattern || "--"}`,
      ].join(" / ");
      item.append(nums, meta);
      list.append(item);
    });
    if (!list.children.length) {
      const empty = document.createElement("li");
      empty.className = "analysis-empty";
      empty.textContent = "没有符合条件的候选号。";
      list.append(empty);
    }
    container.append(list, baselineBlock(payload.baseline?.candidates || []));
  }

  function renderBacktest(container, payload) {
    container.replaceChildren();
    appendMetricSummary(container, [
      [payload.tested_draws, "期回测"],
      [payload.average_main_hits, "策略均值"],
      [payload.baseline_average_main_hits, "随机均值"],
    ]);
    const distribution = document.createElement("div");
    distribution.className = "strategy-distribution";
    (payload.hit_distribution || []).forEach((row) => {
      const chip = document.createElement("span");
      chip.textContent = `${row.hits}命中 ${row.count}期`;
      distribution.append(chip);
    });
    const list = document.createElement("ol");
    list.className = "candidate-list";
    (payload.rows || []).slice(0, 8).forEach((row) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = `${row.issue} 命中 ${row.main_hits}`;
      const meta = document.createElement("span");
      meta.textContent = `策略 ${row.candidate.main.map(padNumber).join(" ")} / 随机 ${row.baseline_candidate.main.map(padNumber).join(" ")}`;
      item.append(title, meta);
      list.append(item);
    });
    container.append(distribution, list);
  }

  function renderCompare(container, payload) {
    container.replaceChildren();
    const list = document.createElement("ol");
    list.className = "candidate-list strategy-list";
    (payload.strategies || []).forEach((row, index) => {
      const item = document.createElement("li");
      const title = document.createElement("b");
      title.textContent = `${index + 1}. ${row.strategy_name}`;
      const meta = document.createElement("span");
      meta.textContent = `${row.tested_draws}期 / 策略均值 ${row.average_main_hits} / 随机均值 ${row.baseline_average_main_hits} / 最高 ${row.max_main_hits}`;
      item.append(title, meta);
      list.append(item);
    });
    container.append(list);
  }

  function storageKey(gameKey) {
    return `lotteryLuck:strategyLab:${gameKey}`;
  }

  function readSavedStrategies(gameKey) {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey(gameKey)) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (error) {
      return [];
    }
  }

  function writeSavedStrategies(gameKey, rows) {
    localStorage.setItem(storageKey(gameKey), JSON.stringify(rows.slice(0, MAX_SAVED_STRATEGIES)));
  }

  // The game is inferred from the storage key; a row is valid only when its preset and
  // every stored form key still exist in the current game's capability schema.
  function validateSavedRow(row, gameKey) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return false;
    if (!PRESETS.includes(row.preset)) return false;
    const form = row.form;
    if (!form || typeof form !== "object" || Array.isArray(form)) return false;
    const allowed = new Set([...conditionFieldsFor(gameKey), ...NON_CONDITION_FORM_KEYS]);
    return Object.keys(form).every((key) => allowed.has(key));
  }

  function renderSavedStrategies(gameKey) {
    if (!els.savedStrategies) return;
    const rows = readSavedStrategies(gameKey);
    els.savedStrategies.replaceChildren();
    if (!rows.length) {
      els.savedStrategies.textContent = "暂无保存策略。";
      return;
    }
    const list = document.createElement("ol");
    list.className = "candidate-list saved-list";
    rows.forEach((row, index) => {
      const valid = validateSavedRow(row, gameKey);
      const item = document.createElement("li");
      item.dataset.savedStrategyState = valid ? "valid" : "needs-resave";
      const title = document.createElement("b");
      title.textContent = row?.name || "未命名策略";
      const actions = document.createElement("span");
      actions.className = "saved-actions";
      const load = document.createElement("button");
      load.type = "button";
      load.className = "mini-action subtle";
      load.textContent = "加载";
      load.disabled = !valid;
      if (valid) load.addEventListener("click", () => loadSavedStrategy(row));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "mini-action subtle";
      remove.textContent = "删除";
      remove.addEventListener("click", () => {
        const next = readSavedStrategies(gameKey).filter((_, savedIndex) => savedIndex !== index);
        writeSavedStrategies(gameKey, next);
        renderSavedStrategies(gameKey);
      });
      actions.append(load, remove);
      item.append(title, actions);
      if (!valid) {
        const notice = document.createElement("span");
        notice.className = "saved-resave-notice";
        notice.textContent = "需要重新保存";
        item.append(notice);
      }
      list.append(item);
    });
    els.savedStrategies.append(list);
  }

  function loadSavedStrategy(row) {
    state.preset = PRESETS.includes(row.preset) ? row.preset : "balanced";
    renderPresetButtons();
    resetConditionInputs();
    Object.entries(row.form || {}).forEach(([key, value]) => {
      const input = els.strategyForm.querySelector(`[name="${key}"]`);
      if (input) input.value = value ?? "";
    });
    renderGameSummary();
    setStrategyStatus("已加载保存的策略，可继续调整。");
  }

  function saveCurrentStrategy() {
    const rows = readSavedStrategies(state.game);
    const name = `${presetLabel(state.preset)} ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
    rows.unshift({ name, preset: state.preset, form: currentFormJson() });
    writeSavedStrategies(state.game, rows);
    renderSavedStrategies(state.game);
    setStrategyStatus("策略已保存到本机浏览器。");
  }

  async function generateCandidates() {
    const token = ++state.requestToken;
    const game = state.game;
    setStrategyStatus("正在生成策略候选…");
    try {
      const payload = await fetchJson(`/api/strategy/${game}/generate`, postBody());
      if (!responseStillCurrent(token, game)) return;
      renderCandidateList(els.candidateResult, payload);
      setStrategyStatus(IDLE_STATUS);
    } catch (error) {
      if (token !== state.requestToken || game !== state.game) return;
      showRetryStatus("策略生成暂不可用。", () => generateCandidates());
    }
  }

  async function runBacktest() {
    if (!hasHistory()) return;
    const token = ++state.requestToken;
    const game = state.game;
    setStrategyStatus("正在回测策略…");
    try {
      const payload = await fetchJson(`/api/strategy/${game}/backtest`, postBody());
      if (!responseStillCurrent(token, game)) return;
      renderBacktest(els.backtestResult, payload);
      setStrategyStatus(IDLE_STATUS);
    } catch (error) {
      if (token !== state.requestToken || game !== state.game) return;
      showRetryStatus("策略回测暂不可用。", () => runBacktest());
    }
  }

  async function comparePresets() {
    if (!hasHistory()) return;
    const token = ++state.requestToken;
    const game = state.game;
    setStrategyStatus("正在对比预设…");
    try {
      const body = requestBody();
      const payload = await fetchJson(`/api/strategy/${game}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          window: body.window,
          candidate_count: 1,
          conditions: body.conditions,
        }),
      });
      if (!responseStillCurrent(token, game)) return;
      renderCompare(els.backtestResult, payload);
      setStrategyStatus(IDLE_STATUS);
    } catch (error) {
      if (token !== state.requestToken || game !== state.game) return;
      showRetryStatus("预设对比暂不可用。", () => comparePresets());
    }
  }

  // One-way handoff: write the normalized strategy context once, then hand execution over
  // to the number tools. Never generate, save or copy numbers here.
  function useCurrentStrategy() {
    const research = window.LotteryResearch.getState();
    const handoff = {
      version: 1,
      created_at: Date.now(),
      game_key: research.game,
      source: "strategy",
      preset: state.preset,
      name: presetLabel(state.preset),
      window: Number(els.strategyForm?.elements?.window?.value || 120),
      conditions: normalizedConditions(research.game),
    };
    sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(handoff));
    window.location.assign(`./tools.html?game=${encodeURIComponent(research.game)}&tool=conditional&source=strategy`);
  }

  async function loadCapabilities() {
    try {
      const payload = await fetchJson("/api/surfaces/config");
      if (payload && typeof payload === "object" && payload.games) state.capabilities = payload;
    } catch (error) {
      state.capabilities = null;
    }
    renderCapabilityFields(state.game);
    renderSavedStrategies(state.game);
  }

  async function loadGamesMeta() {
    try {
      const data = await fetchJson("/api/games");
      state.games = Array.isArray(data.games) ? data.games : [];
    } catch (error) {
      state.games = [];
    }
    updateHistoryAvailability();
    renderGameSummary();
  }

  const unsubscribe = window.LotteryResearch.subscribe((next) => {
    const gameChanged = next.game !== state.game;
    state.game = next.game;
    state.requestToken += 1;
    if (gameChanged) {
      resetConditionInputs();
      setStrategyStatus("已按新彩种规则重置。");
    }
    renderCapabilityFields(next.game);
    renderSavedStrategies(next.game);
    updateHistoryAvailability();
    renderGameSummary();
    if (next.view === "strategy") generateCandidates();
  });

  els.generateButton?.addEventListener("click", generateCandidates);
  els.backtestButton?.addEventListener("click", runBacktest);
  els.compareButton?.addEventListener("click", comparePresets);
  els.saveStrategyButton?.addEventListener("click", saveCurrentStrategy);
  els.useStrategyButton?.addEventListener("click", useCurrentStrategy);
  document.querySelectorAll("#researchStrategyView [data-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      state.preset = button.dataset.preset;
      renderPresetButtons();
      renderGameSummary();
    });
  });

  const initial = window.LotteryResearch.getState();
  state.game = initial.game;
  renderPresetButtons();
  renderCapabilityFields(initial.game);
  renderSavedStrategies(initial.game);
  updateHistoryAvailability();
  renderGameSummary();
  loadCapabilities();
  loadGamesMeta();
  if (initial.view === "strategy") generateCandidates();

  window.addEventListener("pagehide", unsubscribe, { once: true });
})();
