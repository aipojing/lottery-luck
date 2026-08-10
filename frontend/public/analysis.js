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

const ANALYSIS_WINDOWS = [30, 60, 120];

const DEMO_GAMES = [
  { game_key: "ssq", game_name: "双色球", latest_date: "2026-06-15", latest_issue: "2026067" },
  { game_key: "3d", game_name: "福彩3D", latest_date: "2026-06-15", latest_issue: "2026157" },
  { game_key: "qlc", game_name: "七乐彩", latest_date: "2026-06-14", latest_issue: "2026066" },
  { game_key: "kl8", game_name: "快乐8", latest_date: "2026-06-15", latest_issue: "2026157" },
  { game_key: "dlt", game_name: "大乐透", latest_date: "--", latest_issue: "--" },
  { game_key: "pl3", game_name: "排列3", latest_date: "--", latest_issue: "--" },
  { game_key: "pl5", game_name: "排列5", latest_date: "--", latest_issue: "--" },
];

const RESEARCH_VIEWS = ["data", "strategy"];

// The seven 3D observation tools whose deep links stay valid inside the research data view.
const RETAINED_3D_DATA_TOOLS = ["trend", "omission", "frequency", "heat", "number", "attributes", "recent"];

const state = {
  activeGame: "ssq",
  activeView: "data",
  analysisWindow: 30,
  games: DEMO_GAMES,
  capabilities: null,
  demoMode: false,
  routeNotice: "",
};

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  latestDate: document.querySelector("#latestDate"),
  gameTabs: document.querySelector("#gameTabs"),
  researchViewTabs: document.querySelector("#researchViewTabs"),
  researchDataView: document.querySelector("#researchDataView"),
  researchStrategyView: document.querySelector("#researchStrategyView"),
  analysisWorkbench: document.querySelector("#analysisWorkbench"),
  analysisWindowTabs: document.querySelector("#analysisWindowTabs"),
  analysisSummary: document.querySelector("#analysisSummary"),
  commonViewPanel: document.querySelector("#commonViewPanel"),
  numberPanel: document.querySelector("#numberPanel"),
  trendPanel: document.querySelector("#trendPanel"),
  recentPanel: document.querySelector("#recentPanel"),
  calendarPanel: document.querySelector("#calendarPanel"),
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

function currentGameMeta() {
  return state.games.find((game) => game.game_key === state.activeGame) || DEMO_GAMES[0];
}

function formatDateTime(isoDate) {
  if (!isoDate || isoDate === "--") return "数据更新：--";
  return `数据更新：${isoDate} 10:30`;
}

function syncUrl() {
  // The 3D toolbox owns the address bar while it is the active data surface; its own
  // writeUrl keeps the retained tool/window params canonical.
  if (state.activeGame === "3d" && state.activeView === "data") return;
  const params = new URLSearchParams(window.location.search);
  params.set("game", state.activeGame);
  params.set("window", String(state.analysisWindow));
  params.set("view", state.activeView);
  const tool = params.get("tool");
  const keepTool =
    state.activeGame === "3d" &&
    state.activeView === "data" &&
    RETAINED_3D_DATA_TOOLS.includes(tool);
  if (!keepTool) {
    params.delete("tool");
    params.delete("mode");
    params.delete("source");
  }
  window.history.replaceState({}, "", `./analysis.html?${params.toString()}`);
}

function normalizeView(value, announceInvalid = false) {
  if (value === null || RESEARCH_VIEWS.includes(value)) return value || "data";
  if (announceInvalid) state.routeNotice = "研究视图无效，已回到数据观察。";
  return "data";
}

function initFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const game = params.get("game");
  const view = params.get("view");
  const windowSize = Number(params.get("window"));
  if (game && VISIBLE_GAME_KEYS.includes(game)) {
    state.activeGame = game;
  } else if (game) {
    state.routeNotice = "彩种无效，已回到双色球。";
  }
  state.activeView = normalizeView(view, view !== null);
  if (ANALYSIS_WINDOWS.includes(windowSize)) {
    state.analysisWindow = windowSize;
  }
}

function routeStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const game = params.get("game");
  const view = params.get("view");
  const windowSize = Number(params.get("window"));
  return {
    game: VISIBLE_GAME_KEYS.includes(game) ? game : "ssq",
    view: normalizeView(view),
    window: ANALYSIS_WINDOWS.includes(windowSize) ? windowSize : 30,
  };
}

const researchSubscribers = new Set();

function notifyResearchSubscribers() {
  const snapshot = { game: state.activeGame, view: state.activeView, window: state.analysisWindow };
  researchSubscribers.forEach((callback) => {
    try {
      callback(snapshot);
    } catch (error) {
      // A subscriber failure must never break the research shell itself.
    }
  });
}

window.LotteryResearch = Object.freeze({
  getState: () => ({ game: state.activeGame, view: state.activeView, window: state.analysisWindow }),
  setView: (view) => activateResearchState({ view }),
  setGame: (game) => activateResearchState({ game }),
  subscribe(callback) {
    researchSubscribers.add(callback);
    return () => researchSubscribers.delete(callback);
  },
});

function applyResearchView() {
  const strategyActive = state.activeView === "strategy";
  if (els.researchDataView) els.researchDataView.hidden = strategyActive;
  if (els.researchStrategyView) els.researchStrategyView.hidden = !strategyActive;
  document.querySelectorAll("#researchViewTabs [data-research-view]").forEach((button) => {
    const selected = button.dataset.researchView === state.activeView;
    button.setAttribute("aria-selected", String(selected));
    button.classList.toggle("active", selected);
  });
}

function activateResearchState(changes = {}) {
  let changed = false;
  if (changes.game !== undefined) {
    const game = String(changes.game);
    if (VISIBLE_GAME_KEYS.includes(game) && game !== state.activeGame) {
      state.activeGame = game;
      changed = true;
    }
  }
  if (changes.view !== undefined) {
    const view = normalizeView(changes.view);
    if (view !== state.activeView) {
      state.activeView = view;
      changed = true;
    }
  }
  if (changes.window !== undefined && ANALYSIS_WINDOWS.includes(changes.window)) {
    if (changes.window !== state.analysisWindow) {
      state.analysisWindow = changes.window;
      changed = true;
    }
  }
  if (!changed) return;
  syncUrl();
  applyResearchView();
  notifyResearchSubscribers();
  if (state.activeView === "data") {
    loadActiveGame({ reset3d: changes.game === "3d" });
  } else if (changes.game !== undefined && window.ThreeDWorkbench?.deactivate) {
    window.ThreeDWorkbench.deactivate();
  }
}

function renderTabs() {
  els.gameTabs.replaceChildren();
  VISIBLE_GAME_KEYS.forEach((key) => {
    const meta = state.games.find((game) => game.game_key === key) || {
      latest_date: "--",
      latest_issue: "--",
    };
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab-button${key === state.activeGame ? " active" : ""}`;
    button.setAttribute("aria-pressed", String(key === state.activeGame));
    button.dataset.game = key;

    const title = document.createElement("strong");
    title.textContent = GAME_LABELS[key];
    const subtitle = document.createElement("span");
    subtitle.textContent = `${meta.latest_issue || "--"} / ${meta.latest_date || "--"}`;
    button.append(title, subtitle);
    els.gameTabs.append(button);
  });
}

function renderGameMeta() {
  els.latestDate.textContent = formatDateTime(currentGameMeta().latest_date);
}

function isThreeDWorkbenchGame() {
  return state.activeGame === "3d";
}

function renderAnalysisWindowTabs() {
  els.analysisWindowTabs.replaceChildren();
  ANALYSIS_WINDOWS.forEach((windowSize) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `analysis-window-button${state.analysisWindow === windowSize ? " active" : ""}`;
    button.dataset.window = String(windowSize);
    button.setAttribute("aria-pressed", String(state.analysisWindow === windowSize));
    button.textContent = `近${windowSize}期`;
    els.analysisWindowTabs.append(button);
  });
}

function renderAnalysisStatus(message, isError = false) {
  els.analysisSummary.classList.toggle("error", isError);
  els.analysisSummary.textContent = message;
}

function analysisNumberLabel(value) {
  if (typeof value === "string" && value.includes("-")) return value;
  return padNumber(value);
}

function analysisCardTitle(container, title, meta = "") {
  const head = document.createElement("div");
  head.className = "analysis-card-head";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const badge = document.createElement("span");
  badge.textContent = meta;
  head.append(heading, badge);
  container.append(head);
}

function compactShape(shape) {
  const parts = [];
  [
    ["连号", shape.consecutive_counts],
    ["重号", shape.repeat_counts],
    ["奇偶", shape.odd_even],
    ["大小", shape.big_small],
    ["区间", shape.range_distribution],
    ["和值", shape.sum_ranges],
  ].forEach(([label, values]) => {
    if (Array.isArray(values) && values.length) {
      parts.push(`${label} ${values.slice(0, 3).map((item) => `${item.label}:${item.count}`).join(" / ")}`);
    }
  });
  return parts.join("　");
}

function rankList(title, rows, valueKey, variant = "") {
  const group = document.createElement("div");
  group.className = "analysis-rank-group";
  const heading = document.createElement("p");
  heading.textContent = title;
  const list = document.createElement("ol");
  list.className = "analysis-rank";

  (rows || []).slice(0, 8).forEach((row) => {
    const item = document.createElement("li");
    const number = document.createElement("span");
    number.className = `analysis-mini-ball${variant ? ` ${variant}` : ""}`;
    number.textContent = analysisNumberLabel(row.number);
    const metric = document.createElement("b");
    metric.textContent = String(row[valueKey] ?? 0);
    item.append(number, metric);
    list.append(item);
  });

  if (!list.children.length) {
    const item = document.createElement("li");
    item.className = "analysis-empty";
    item.textContent = "--";
    list.append(item);
  }
  group.append(heading, list);
  return group;
}

function shapeTop(rows) {
  return Array.isArray(rows) && rows.length ? `${rows[0].label} ${rows[0].count}` : "--";
}

function renderCommonView(payload) {
  if (!els.commonViewPanel) return;
  els.commonViewPanel.replaceChildren();
  analysisCardTitle(els.commonViewPanel, "彩民常看", "先看重点");
  const shape = payload.shape || {};
  const grid = document.createElement("div");
  grid.className = "common-view-grid";
  grid.append(
    rankList("热号", payload.hot?.main, "count"),
    rankList("冷号", payload.cold?.main, "count"),
    rankList("遗漏", payload.omission?.main, "missing"),
  );
  const shapeList = document.createElement("dl");
  shapeList.className = "common-shape-list";
  [
    ["奇偶", shapeTop(shape.odd_even)],
    ["和值", shapeTop(shape.sum_ranges)],
    ["重号", shapeTop(shape.repeat_counts)],
    ["连号", shapeTop(shape.consecutive_counts)],
    ["大小", shapeTop(shape.big_small)],
  ].forEach(([label, value]) => {
    const wrap = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    wrap.append(dt, dd);
    shapeList.append(wrap);
  });
  els.commonViewPanel.append(grid, shapeList);
}

function professionalBlock(title, rows) {
  const group = document.createElement("div");
  group.className = "professional-metric";
  const heading = document.createElement("p");
  heading.textContent = title;
  const values = document.createElement("div");
  values.className = "professional-values";
  (rows || []).slice(0, 4).forEach((row) => {
    const chip = document.createElement("span");
    chip.textContent = `${row.label} ${row.count}`;
    values.append(chip);
  });
  if (!values.children.length) {
    const chip = document.createElement("span");
    chip.textContent = "--";
    values.append(chip);
  }
  group.append(heading, values);
  return group;
}

function renderProfessionalMetrics(container, professional) {
  if (!professional) return;
  const block = document.createElement("div");
  block.className = "professional-grid";
  block.append(
    professionalBlock("AC 离散", professional.ac_values),
    professionalBlock("质合结构", professional.prime_composite),
    professionalBlock("尾数热区", professional.tail_distribution),
    professionalBlock("012 路", professional.mod3_distribution),
    professionalBlock("区间分布", professional.zone_distribution),
    professionalBlock("邻号", professional.neighbor_counts),
    professionalBlock("遗漏层", professional.omission_layers),
  );
  container.append(block);
}

function renderAnalysisHotCold(payload) {
  const card = els.numberPanel;
  card.replaceChildren();
  analysisCardTitle(card, "号码分析面板", `${payload.window}期`);

  if (payload.trend?.position_columns && Array.isArray(payload.position_hot)) {
    const positions = ["百位", "十位", "个位"];
    const wrap = document.createElement("div");
    wrap.className = "position-analysis";
    positions.forEach((position, index) => {
      const panel = document.createElement("div");
      panel.className = "position-panel";
      const title = document.createElement("p");
      title.textContent = position;
      panel.append(
        title,
        rankList("热", payload.position_hot[index], "count"),
        rankList("冷", payload.position_cold?.[index], "count"),
        rankList("漏", payload.position_omission?.[index], "missing"),
      );
      wrap.append(panel);
    });
    card.append(wrap);
    renderProfessionalMetrics(card, payload.professional);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "analysis-rank-grid";
  grid.append(
    rankList("热号", payload.hot?.main, "count"),
    rankList("冷号", payload.cold?.main, "count"),
    rankList("遗漏", payload.omission?.main, "missing"),
    rankList("近期权重", payload.recent_weight?.main, "weight"),
  );
  if (payload.hot?.special?.length || payload.omission?.special?.length) {
    const specialRows = payload.hot?.special?.length ? payload.hot.special : payload.omission.special;
    grid.append(rankList("特别", specialRows, payload.hot?.special?.length ? "count" : "missing", "special"));
  }
  const shape = compactShape(payload.shape || {});
  if (shape) {
    const shapeBlock = document.createElement("div");
    shapeBlock.className = "metric-strip";
    shapeBlock.textContent = shape;
    card.append(shapeBlock);
  }
  card.append(grid);
  renderProfessionalMetrics(card, payload.professional);
}

function renderAnalysisTrend(payload) {
  const card = els.trendPanel;
  card.replaceChildren();
  analysisCardTitle(card, "走势图", payload.game_key === "kl8" ? "热区分布" : "命中点");

  if (payload.trend?.position_columns) {
    const list = document.createElement("div");
    list.className = "position-trend";
    (payload.trend.rows || []).slice(0, 10).forEach((row) => {
      const item = document.createElement("div");
      item.className = "position-trend-row";
      const issue = document.createElement("span");
      issue.textContent = row.issue || "--";
      item.append(issue);
      (row.position_hits || []).forEach((hit) => {
        const chip = document.createElement("b");
        chip.textContent = `${hit.position}${padNumber(hit.number)}`;
        item.append(chip);
      });
      list.append(item);
    });
    card.append(list);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "analysis-trend-grid";
  const columns = (payload.trend?.columns || []).slice(0, payload.game_key === "kl8" ? 8 : 40);
  grid.style.setProperty("--trend-columns", String(Math.max(1, columns.length)));
  columns.forEach((column) => {
    const cell = document.createElement("span");
    cell.className = "trend-head";
    cell.textContent = column;
    grid.append(cell);
  });

  (payload.trend?.rows || []).forEach((row) => {
    const hits = new Set((row.hits || []).map(analysisNumberLabel));
    columns.forEach((column) => {
      const cell = document.createElement("span");
      cell.className = hits.has(column) ? "trend-hit" : "trend-cell";
      cell.textContent = hits.has(column) ? "●" : "";
      cell.title = `${row.issue || "--"} ${row.draw_date || "--"}`;
      grid.append(cell);
    });
  });

  if (!payload.trend?.rows?.length) {
    const empty = document.createElement("p");
    empty.className = "analysis-empty";
    empty.textContent = "暂无走势数据";
    card.append(empty);
    return;
  }
  card.append(grid);
}

function renderAnalysisShape(payload) {
  const card = document.createElement("div");
  card.replaceChildren();
  analysisCardTitle(card, "形态分布", "结构");
  const shape = payload.shape || {};
  const rows = [
    ["奇偶", shape.odd_even],
    ["大小", shape.big_small],
    ["和值", shape.sum_ranges],
    ["连号", shape.consecutive_counts],
    ["类型", shape.digit_types],
    ["跨度", shape.span],
    ["区间", shape.range_distribution],
    ["重号", shape.repeat_counts],
  ];
  const list = document.createElement("div");
  list.className = "analysis-shape-list";
  rows.forEach(([label, values]) => {
    if (!Array.isArray(values) || !values.length) return;
    const item = document.createElement("div");
    const name = document.createElement("span");
    name.textContent = label;
    const metrics = document.createElement("p");
    metrics.textContent = values
      .slice(0, 5)
      .map((value) => `${value.label} ${value.count}`)
      .join(" / ");
    item.append(name, metrics);
    list.append(item);
  });
  if (!list.children.length) {
    list.textContent = "暂无形态数据";
    list.classList.add("analysis-empty");
  }
  card.append(list);
}

function renderAnalysisDraws(payload) {
  const card = els.recentPanel;
  card.replaceChildren();
  analysisCardTitle(card, "近期开奖", "标记");
  const list = document.createElement("ol");
  list.className = "analysis-draw-list";
  (payload.recent_draws || []).slice(0, 6).forEach((draw) => {
    const item = document.createElement("li");
    const issue = document.createElement("span");
    issue.textContent = `${draw.draw_date || "--"} ${draw.issue || "--"}`;
    const numbers = document.createElement("b");
    const main = (draw.main || []).map(padNumber).join(" ");
    const special = (draw.special || []).length ? ` + ${(draw.special || []).map(padNumber).join(" ")}` : "";
    numbers.textContent = `${main}${special}`;
    const tag = document.createElement("em");
    tag.textContent = (draw.tags || []).slice(0, 1).join("") || "样本";
    item.append(issue, numbers, tag);
    list.append(item);
  });
  if (!list.children.length) {
    const item = document.createElement("li");
    item.className = "analysis-empty";
    item.textContent = "暂无开奖数据";
    list.append(item);
  }
  card.append(list);
}

function renderAnalysis(payload) {
  const gameName = GAME_LABELS[payload.game_key] || currentGameMeta().game_name || "--";
  const summary = payload.summary || {};
  els.analysisSummary.classList.remove("error");
  els.analysisSummary.textContent = `${gameName} · 样本 ${summary.draw_count ?? 0} 期 · 最新 ${summary.latest_issue || "--"} · ${summary.latest_date || "--"}`;
  renderCommonView(payload);
  renderAnalysisHotCold(payload);
  renderAnalysisTrend(payload);
  renderAnalysisDraws(payload);
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

function renderCalendar(payload) {
  els.calendarPanel.replaceChildren();
  const list = document.createElement("ol");
  list.className = "calendar-list";
  (payload.games || []).forEach((game) => {
    const item = document.createElement("li");
    const name = document.createElement("b");
    name.textContent = game.game_name || "--";
    const nextDate = document.createElement("span");
    nextDate.textContent = `下期开奖 ${game.next_draw_date || "--"}`;
    const latest = document.createElement("span");
    latest.textContent = `最新 ${game.latest_issue || "--"} / ${game.latest_date || "--"}`;
    const status = document.createElement("em");
    status.textContent = game.status || "--";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mini-action";
    const enabled = localStorage.getItem(game.reminder_key) === "1";
    button.textContent = enabled ? "已提醒" : "提醒";
    button.addEventListener("click", () => {
      const next = localStorage.getItem(game.reminder_key) === "1" ? "0" : "1";
      if (next === "1") localStorage.setItem(game.reminder_key, "1");
      else localStorage.removeItem(game.reminder_key);
      button.textContent = next === "1" ? "已提醒" : "提醒";
    });
    item.append(name, nextDate, latest, status);
    item.append(button);
    list.append(item);
  });
  els.calendarPanel.append(list);
}

async function loadCalendar() {
  try {
    renderCalendar(await fetchJson("/api/calendar"));
  } catch (error) {
    els.calendarPanel.textContent = "开奖日历暂不可用。";
  }
}

async function loadGames() {
  try {
    const data = await fetchJson("/api/games");
    state.games = Array.isArray(data.games) && data.games.length ? data.games : DEMO_GAMES;
    state.demoMode = false;
    setStatus(state.routeNotice || "研究中心", Boolean(state.routeNotice));
  } catch (error) {
    state.games = DEMO_GAMES;
    state.demoMode = true;
    setStatus(state.routeNotice || "Demo 预览", true);
  }
  state.routeNotice = "";
  renderTabs();
  renderGameMeta();
}

async function loadAnalysis() {
  if (isThreeDWorkbenchGame()) return;
  renderAnalysisWindowTabs();
  renderAnalysisStatus("分析数据加载中。");
  try {
    const payload = await fetchJson(`/api/analysis/${state.activeGame}?window=${state.analysisWindow}`);
    renderAnalysis(payload);
    syncUrl();
  } catch (error) {
    renderAnalysisStatus("分析数据暂不可用", true);
  }
}

async function loadActiveGame(options = {}) {
  renderTabs();
  renderGameMeta();
  if (isThreeDWorkbenchGame()) {
    if (window.ThreeDWorkbench?.activate) {
      await window.ThreeDWorkbench.activate({
        reset: options.reset3d === true,
        restoreRoute: options.restore3d === true,
      });
    }
    return;
  }
  if (window.ThreeDWorkbench?.deactivate) {
    window.ThreeDWorkbench.deactivate();
  }
  if (els.analysisWorkbench) {
    els.analysisWorkbench.hidden = false;
    els.analysisWorkbench.setAttribute("aria-hidden", "false");
  }
  await loadAnalysis();
  await loadCalendar();
}

els.gameTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-game]");
  if (!button) return;
  activateResearchState({ game: button.dataset.game });
});

els.researchViewTabs?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-research-view]");
  if (!button) return;
  activateResearchState({ view: button.dataset.researchView });
});

window.addEventListener("popstate", () => {
  const route = routeStateFromUrl();
  const gameChanged = route.game !== state.activeGame;
  const windowChanged = route.window !== state.analysisWindow;
  state.activeGame = route.game;
  state.activeView = route.view;
  state.analysisWindow = route.window;
  applyResearchView();
  notifyResearchSubscribers();
  if (state.activeView === "strategy") return;

  if (gameChanged) {
    loadActiveGame({ restore3d: route.game === "3d" });
    return;
  }
  if (route.game === "3d") {
    window.ThreeDToolbox?.handlePopState?.();
    return;
  }
  if (windowChanged) loadActiveGame();
});

els.analysisWindowTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-window]");
  if (!button) return;
  state.analysisWindow = Number(button.dataset.window) || 30;
  loadAnalysis();
});

// Old 3D selection deep links (reduction/filter) now belong to the number tools. Replace
// the navigation before any data request or toolbox routing runs, so nothing observes the
// legacy route. Legal observation tool params keep flowing through the data view.
function redirectLegacySelectionRoute() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("game") !== "3d") return false;
  const tool = params.get("tool");
  if (tool !== "reduction" && tool !== "filter") return false;
  window.location.replace("./tools.html?game=3d&tool=conditional&source=legacy");
  return true;
}

if (!redirectLegacySelectionRoute()) {
  initFromUrl();
  renderAnalysisWindowTabs();
  applyResearchView();
  loadGames().then(async () => {
    if (state.activeView === "data") {
      await loadActiveGame();
    }
    notifyResearchSubscribers();
  });
}
