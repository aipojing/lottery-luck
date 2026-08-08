const GAME_LABELS = {
  ssq: "双色球",
  "3d": "福彩3D",
  qlc: "七乐彩",
  kl8: "快乐8",
  dlt: "大乐透",
  pl3: "排列3",
  pl5: "排列5",
};

const VISIBLE_GAME_KEYS = ["ssq", "dlt", "3d", "pl3", "kl8"];

const DEMO_GAMES = [
  { game_key: "ssq", game_name: "双色球", latest_date: "2026-06-15", latest_issue: "2026067" },
  { game_key: "3d", game_name: "福彩3D", latest_date: "2026-06-15", latest_issue: "2026157" },
  { game_key: "qlc", game_name: "七乐彩", latest_date: "2026-06-14", latest_issue: "2026066" },
  { game_key: "kl8", game_name: "快乐8", latest_date: "2026-06-15", latest_issue: "2026157" },
  { game_key: "dlt", game_name: "大乐透", latest_date: "--", latest_issue: "--" },
  { game_key: "pl3", game_name: "排列3", latest_date: "--", latest_issue: "--" },
  { game_key: "pl5", game_name: "排列5", latest_date: "--", latest_issue: "--" },
];

const PRESET_DESCRIPTIONS = {
  balanced: "均衡型：兼顾热号、和值、奇偶和结构离散度。",
  conservative: "保守型：控制连号和近期重复，偏向稳态结构。",
  aggressive: "激进型：放宽近期限制，增加热号权重。",
};

const state = {
  activeGame: "ssq",
  activePreset: "balanced",
  games: DEMO_GAMES,
};

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  latestDate: document.querySelector("#latestDate"),
  gameTabs: document.querySelector("#gameTabs"),
  strategySummary: document.querySelector("#strategySummary"),
  strategyCompat: document.querySelector("#strategyCompat"),
  strategyCompatPrimary: document.querySelector("#strategyCompatPrimary"),
  strategyCompatSecondary: document.querySelector("#strategyCompatSecondary"),
  strategyLayout: document.querySelector("#strategyLayout"),
  strategyForm: document.querySelector("#strategyForm"),
  presetDescription: document.querySelector("#presetDescription"),
  generateButton: document.querySelector("#generateButton"),
  backtestButton: document.querySelector("#backtestButton"),
  compareButton: document.querySelector("#compareButton"),
  saveStrategyButton: document.querySelector("#saveStrategyButton"),
  candidateResult: document.querySelector("#candidateResult"),
  backtestResult: document.querySelector("#backtestResult"),
  savedStrategies: document.querySelector("#savedStrategies"),
};

function padNumber(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return String(number).padStart(2, "0");
}

function setStatus(message, isError = false) {
  els.apiStatus.textContent = message;
  els.apiStatus.classList.toggle("error", isError);
}

function initFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const game = params.get("game");
  if (game && VISIBLE_GAME_KEYS.includes(game)) {
    state.activeGame = game;
  }
}

function currentGameMeta() {
  return state.games.find((game) => game.game_key === state.activeGame) || DEMO_GAMES[0];
}

function formatDateTime(isoDate) {
  if (!isoDate || isoDate === "--") return "数据更新：--";
  return `数据更新：${isoDate} 10:30`;
}

function renderGameMeta() {
  const meta = currentGameMeta();
  els.latestDate.textContent = formatDateTime(meta.latest_date);
  if (state.activeGame === "3d") {
    els.strategySummary.textContent = "福彩3D · 旧入口保留兼容 · 专业筛选请进入3D工作台";
  } else {
    els.strategySummary.textContent = `${GAME_LABELS[state.activeGame]} · 策略 ${presetLabel(state.activePreset)} · 最新 ${meta.latest_issue || "--"} · ${meta.latest_date || "--"}`;
  }
  renderCompatibilityState();
}

function renderTabs() {
  els.gameTabs.replaceChildren();
  VISIBLE_GAME_KEYS.forEach((key) => {
    const meta = state.games.find((game) => game.game_key === key) || {};
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab-button${key === state.activeGame ? " active" : ""}`;
    button.dataset.game = key;
    button.setAttribute("aria-pressed", String(key === state.activeGame));
    const title = document.createElement("strong");
    title.textContent = GAME_LABELS[key];
    const subtitle = document.createElement("span");
    subtitle.textContent = `${meta.latest_issue || "--"} / ${meta.latest_date || "--"}`;
    button.append(title, subtitle);
    els.gameTabs.append(button);
  });
}

function renderPresetButtons() {
  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.classList.toggle("active", button.dataset.preset === state.activePreset);
    button.setAttribute("aria-pressed", String(button.dataset.preset === state.activePreset));
  });
  els.presetDescription.textContent = PRESET_DESCRIPTIONS[state.activePreset] || "";
}

function renderCompatibilityState() {
  const isThreeD = state.activeGame === "3d";
  if (els.strategyCompat) els.strategyCompat.hidden = !isThreeD;
  if (els.strategyLayout) els.strategyLayout.hidden = isThreeD;
  document.querySelector(".strategy-actions")?.toggleAttribute("hidden", isThreeD);
  if (els.strategyCompatPrimary) {
    els.strategyCompatPrimary.href = "./analysis.html?game=3d&mode=pro&window=30";
  }
  if (els.strategyCompatSecondary) {
    els.strategyCompatSecondary.href = "./analysis.html?game=3d&mode=simple&window=30";
  }
}

function isCompatibilityOnlyGame() {
  return state.activeGame === "3d";
}

function presetLabel(preset) {
  return { balanced: "均衡型", conservative: "保守型", aggressive: "激进型" }[preset] || preset;
}

function storageKey() {
  return `lotteryLuck:strategyLab:${state.activeGame}`;
}

function readSavedStrategies() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey()) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (error) {
    return [];
  }
}

function writeSavedStrategies(rows) {
  localStorage.setItem(storageKey(), JSON.stringify(rows.slice(0, 20)));
}

function parseNumberInput(value) {
  return String(value ?? "")
    .split(/[,\s/，、]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => Number(part))
    .filter((number) => Number.isInteger(number));
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

function requestBody() {
  const raw = formJson(els.strategyForm);
  const conditions = {};
  [
    "exclude_recent",
    "min_hot",
    "odd_even",
    "sum_min",
    "sum_max",
    "max_consecutive_run",
    "ac_min",
    "ac_max",
    "prime_composite",
    "mod3",
    "zone",
    "min_omission",
  ].forEach((key) => {
    if (raw[key] !== null && raw[key] !== "") conditions[key] = raw[key];
  });
  const tailExclude = parseNumberInput(raw.tail_exclude);
  const tailInclude = parseNumberInput(raw.tail_include);
  if (tailExclude.length) conditions.tail_exclude = tailExclude;
  if (tailInclude.length) conditions.tail_include = tailInclude;

  return {
    preset: state.activePreset,
    candidate_count: Number(raw.candidate_count) || 8,
    window: Number(raw.window) || 100,
    conditions,
  };
}

function syncUrl() {
  const params = new URLSearchParams();
  params.set("game", state.activeGame);
  window.history.replaceState({}, "", `./strategy.html?${params.toString()}`);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
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

async function loadGames() {
  try {
    const data = await fetchJson("/api/games");
    state.games = Array.isArray(data.games) && data.games.length ? data.games : DEMO_GAMES;
    setStatus("策略实验室");
  } catch (error) {
    state.games = DEMO_GAMES;
    setStatus("Demo 预览", true);
  }
  renderTabs();
  renderGameMeta();
}

function renderCandidateList(container, payload) {
  container.replaceChildren();
  appendMetricSummary(container, [
    [payload.candidates.length, "策略候选"],
    [payload.baseline.candidates.length, "随机基准"],
    [payload.diagnostics.condition_count, "有效条件"],
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
  container.append(list, baselineBlock(payload.baseline.candidates || []));
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

function renderSavedStrategies() {
  const rows = readSavedStrategies();
  els.savedStrategies.replaceChildren();
  if (!rows.length) {
    els.savedStrategies.textContent = "暂无保存策略。";
    return;
  }
  const list = document.createElement("ol");
  list.className = "candidate-list saved-list";
  rows.forEach((row, index) => {
    const item = document.createElement("li");
    const title = document.createElement("b");
    title.textContent = row.name;
    const actions = document.createElement("span");
    actions.className = "saved-actions";
    const load = document.createElement("button");
    load.type = "button";
    load.className = "mini-action subtle";
    load.textContent = "加载";
    load.addEventListener("click", () => loadSavedStrategy(row));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "mini-action subtle";
    remove.textContent = "删除";
    remove.addEventListener("click", () => {
      const next = readSavedStrategies().filter((_, savedIndex) => savedIndex !== index);
      writeSavedStrategies(next);
      renderSavedStrategies();
    });
    actions.append(load, remove);
    item.append(title, actions);
    list.append(item);
  });
  els.savedStrategies.append(list);
}

function loadSavedStrategy(row) {
  state.activePreset = row.preset || "balanced";
  renderPresetButtons();
  Object.entries(row.form || {}).forEach(([key, value]) => {
    const input = els.strategyForm.querySelector(`[name="${key}"]`);
    if (input) input.value = value ?? "";
  });
  renderGameMeta();
}

function saveCurrentStrategy() {
  if (isCompatibilityOnlyGame()) return;
  const raw = formJson(els.strategyForm);
  const rows = readSavedStrategies();
  const name = `${presetLabel(state.activePreset)} ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
  rows.unshift({ name, preset: state.activePreset, form: raw });
  writeSavedStrategies(rows);
  renderSavedStrategies();
}

async function generateCandidates() {
  if (isCompatibilityOnlyGame()) return;
  els.candidateResult.textContent = "生成中。";
  try {
    const payload = await fetchJson(`/api/strategy/${state.activeGame}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    });
    renderCandidateList(els.candidateResult, payload);
  } catch (error) {
    els.candidateResult.textContent = "策略生成暂不可用。";
  }
}

async function runBacktest() {
  if (isCompatibilityOnlyGame()) return;
  els.backtestResult.textContent = "回测中。";
  try {
    const payload = await fetchJson(`/api/strategy/${state.activeGame}/backtest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody()),
    });
    renderBacktest(els.backtestResult, payload);
  } catch (error) {
    els.backtestResult.textContent = "策略回测暂不可用。";
  }
}

async function comparePresets() {
  if (isCompatibilityOnlyGame()) return;
  els.backtestResult.textContent = "对比中。";
  try {
    const body = requestBody();
    const payload = await fetchJson(`/api/strategy/${state.activeGame}/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        window: body.window,
        candidate_count: 1,
        conditions: body.conditions,
      }),
    });
    renderCompare(els.backtestResult, payload);
  } catch (error) {
    els.backtestResult.textContent = "预设对比暂不可用。";
  }
}

els.gameTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-game]");
  if (!button) return;
  state.activeGame = button.dataset.game;
  renderTabs();
  renderGameMeta();
  renderSavedStrategies();
  syncUrl();
  if (!isCompatibilityOnlyGame()) generateCandidates();
});

document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activePreset = button.dataset.preset;
    renderPresetButtons();
    renderGameMeta();
  });
});

els.generateButton.addEventListener("click", generateCandidates);
els.backtestButton.addEventListener("click", runBacktest);
els.compareButton.addEventListener("click", comparePresets);
els.saveStrategyButton.addEventListener("click", saveCurrentStrategy);

initFromUrl();
renderPresetButtons();
renderSavedStrategies();
loadGames().then(() => {
  if (!isCompatibilityOnlyGame()) generateCandidates();
});
