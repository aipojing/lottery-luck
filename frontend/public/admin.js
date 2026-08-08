const GAME_LABELS = {
  ssq: "双色球",
  "3d": "福彩3D",
  qlc: "七乐彩",
  kl8: "快乐8",
  dlt: "大乐透",
  pl3: "排列3",
  pl5: "排列5",
};

const els = {
  dataAdmin: document.querySelector("#dataAdmin"),
  apiStatus: document.querySelector("#apiStatus"),
  adminAuthPanel: document.querySelector("#adminAuthPanel"),
  adminAuthForm: document.querySelector("#adminAuthForm"),
  adminTokenInput: document.querySelector("#adminTokenInput"),
  adminAuthMessage: document.querySelector("#adminAuthMessage"),
  adminUnlockButton: document.querySelector("#adminUnlockButton"),
  adminLockButton: document.querySelector("#adminLockButton"),
  adminSummary: document.querySelector("#adminSummary"),
  adminKpis: document.querySelector("#adminKpis"),
  adminActionPlan: document.querySelector("#adminActionPlan"),
  adminSettings: document.querySelector("#adminSettings"),
  adminTasks: document.querySelector("#adminTasks"),
  adminTaskForm: document.querySelector("#adminTaskForm"),
  adminTaskRunButton: document.querySelector("#adminTaskRunButton"),
  adminTaskResult: document.querySelector("#adminTaskResult"),
  adminTaskList: document.querySelector("#adminTaskList"),
  healthTable: document.querySelector("#healthTable"),
  crawlLogs: document.querySelector("#crawlLogs"),
  refreshButton: document.querySelector("#refreshButton"),
  adminLayout: document.querySelector("#adminLayout"),
};

const providerDefaults = {
  cwl: "ssq,3d,kl8",
  sports: "dlt,pl3",
};

const ADMIN_TOKEN_STORAGE_KEY = "lottery_luck_admin_session";
let memoryAdminToken = "";
let adminSessionEpoch = 0;
let unlockValidationInFlight = false;
const pendingAdminControllers = new Set();

function setStatus(message, isError = false) {
  els.apiStatus.textContent = message;
  els.apiStatus.classList.toggle("error", isError);
}

function storedAdminToken() {
  try {
    return (sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || memoryAdminToken || "").trim();
  } catch (error) {
    return memoryAdminToken.trim();
  }
}

function saveAdminToken(value) {
  const token = value.trim();
  memoryAdminToken = token;
  try {
    sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  } catch (error) {
    setAuthMessage("当前浏览器会话存储不可用。", true);
  }
}

function removeAdminToken() {
  memoryAdminToken = "";
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  } catch (error) {
    // Ignore storage failures; locked UI state is still enforced in memory.
  }
}

function hasAdminToken() {
  return Boolean(storedAdminToken());
}

function abortPendingAdminRequests() {
  pendingAdminControllers.forEach((controller) => controller.abort());
  pendingAdminControllers.clear();
}

function invalidateAdminSession() {
  adminSessionEpoch += 1;
  abortPendingAdminRequests();
}

function isCurrentEpoch(epoch) {
  return epoch === adminSessionEpoch;
}

function isCurrentToken(epoch, token) {
  return isCurrentEpoch(epoch) && storedAdminToken() === token.trim();
}

function setUnlockBusy(isBusy) {
  unlockValidationInFlight = isBusy;
  if (els.adminUnlockButton) {
    els.adminUnlockButton.disabled = isBusy;
  }
}

function setAuthMessage(message, isError = false) {
  if (!els.adminAuthMessage) return;
  els.adminAuthMessage.textContent = message;
  els.adminAuthMessage.classList.toggle("error", isError);
}

function businessPanels() {
  return [
    els.adminKpis,
    els.adminActionPlan,
    els.adminSettings,
    els.adminTasks,
    els.adminLayout,
  ].filter(Boolean);
}

function resetActionPlan(message) {
  if (!els.adminActionPlan) return;
  const oldList = els.adminActionPlan.querySelector(".admin-action-list");
  if (oldList) oldList.textContent = message;
}

function resetSettings(message) {
  const grid = els.adminSettings?.querySelector(".settings-grid");
  if (grid) grid.textContent = message;
}

function clearBusinessPanels() {
  if (els.adminSummary) els.adminSummary.textContent = "后台已锁定。";
  els.adminKpis?.replaceChildren();
  resetActionPlan("等待授权。");
  resetSettings("等待授权。");
  if (els.adminTaskResult) els.adminTaskResult.textContent = "等待授权。";
  if (els.adminTaskList) els.adminTaskList.textContent = "等待授权。";
  els.healthTable?.replaceChildren();
  if (els.crawlLogs) els.crawlLogs.textContent = "";
}

function setLockedState(isLocked, message = "") {
  if (els.dataAdmin) els.dataAdmin.dataset.locked = String(isLocked);
  if (els.adminAuthPanel) els.adminAuthPanel.hidden = !isLocked;
  if (els.adminLockButton) els.adminLockButton.hidden = isLocked;
  if (els.refreshButton) els.refreshButton.disabled = isLocked;
  if (els.adminTaskRunButton) els.adminTaskRunButton.disabled = isLocked;
  if (els.adminUnlockButton && !unlockValidationInFlight) {
    els.adminUnlockButton.disabled = !isLocked;
  }
  businessPanels().forEach((panel) => {
    panel.hidden = isLocked;
  });
  if (message) setAuthMessage(message, isLocked);
}

function handleUnauthorized() {
  invalidateAdminSession();
  setUnlockBusy(false);
  removeAdminToken();
  if (els.adminTokenInput) els.adminTokenInput.value = "";
  clearBusinessPanels();
  setLockedState(true, "授权失效，请重新输入后台口令。");
  setStatus("后台已锁定", true);
}

async function fetchJson(url, options = {}) {
  const { headers: optionHeaders = {}, tokenOverride = null, ...fetchOptions } = options;
  const headers = {
    "Content-Type": "application/json",
    ...optionHeaders,
  };
  const adminToken =
    typeof tokenOverride === "string" ? tokenOverride.trim() : storedAdminToken();
  if (adminToken) {
    headers["X-Lottery-Admin-Token"] = adminToken;
  }
  const isProtectedRequest = url.startsWith("/api/admin/");
  const controller = isProtectedRequest ? new AbortController() : null;
  if (controller) {
    pendingAdminControllers.add(controller);
    fetchOptions.signal = controller.signal;
  }
  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    });
    if (response.status === 401) {
      handleUnauthorized();
      const error = new Error("admin authorization required");
      error.status = 401;
      throw error;
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  } finally {
    if (controller) {
      pendingAdminControllers.delete(controller);
    }
  }
}

function renderKpis(kpis) {
  const items = [
    ["健康彩种", kpis.healthy_games],
    ["需关注", kpis.attention_games],
    ["空数据", kpis.empty_games],
    ["总样本", kpis.total_draws],
  ];
  els.adminKpis.replaceChildren();
  items.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "admin-kpi";
    const labelEl = document.createElement("span");
    labelEl.textContent = label;
    const valueEl = document.createElement("strong");
    valueEl.textContent = value ?? "--";
    item.append(labelEl, valueEl);
    els.adminKpis.append(item);
  });
}

function gameNames(games) {
  return games.map((game) => GAME_LABELS[game.game_key] || game.game_name || game.game_key).join(" / ");
}

function appendActionCard(container, title, badge, message, command = "") {
  const card = document.createElement("article");
  card.className = "admin-action-card";
  const head = document.createElement("div");
  head.className = "admin-action-card-head";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const tag = document.createElement("span");
  tag.textContent = badge;
  head.append(heading, tag);
  const copy = document.createElement("p");
  copy.textContent = message;
  card.append(head, copy);
  if (command) {
    const commandEl = document.createElement("code");
    commandEl.textContent = command;
    card.append(commandEl);
  }
  container.append(card);
}

function renderActionPlan(payload) {
  if (!els.adminActionPlan) return;
  const container = document.createElement("div");
  container.className = "admin-action-list";
  const games = Array.isArray(payload.games) ? payload.games : [];
  const attentionGames = games.filter((game) => game.status !== "healthy");
  const cwlGames = attentionGames.filter((game) => game.provider === "cwl");
  const sportsGames = attentionGames.filter((game) => game.provider === "sports");
  const commands = payload.commands || {};
  const failure = payload.failure_summary || {};

  if (failure.has_failure) {
    appendActionCard(
      container,
      "最近失败原因",
      "置顶",
      failure.message || "最近一次补采失败，请优先处理。",
    );
  }

  if (!attentionGames.length) {
    appendActionCard(
      container,
      "当前数据健康",
      "无需补采",
      "所有彩种都已覆盖到最近应期开奖日，可以继续观察下一期开奖。",
    );
  }
  if (cwlGames.length) {
    appendActionCard(
      container,
      "福彩链路需关注",
      `${cwlGames.length} 个彩种`,
      `${gameNames(cwlGames)} 存在近期缺口，可在上方任务队列选择福彩官方并执行补采。`,
      commands.cwl || "",
    );
  }
  if (sportsGames.length) {
    appendActionCard(
      container,
      "体彩链路需关注",
      `${sportsGames.length} 个彩种`,
      `${gameNames(sportsGames)} 存在近期缺口，可在上方任务队列选择体彩官方并执行补采。`,
      commands.sports_browser || "",
    );
  }

  const oldList = els.adminActionPlan.querySelector(".admin-action-list");
  if (oldList) oldList.replaceWith(container);
}

function statusLabel(status) {
  return { healthy: "正常", attention: "关注", empty: "空数据" }[status] || status;
}

function renderHealthTable(games) {
  const table = document.createElement("table");
  table.className = "admin-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["彩种", "来源", "样本", "覆盖范围", "最新", "下期开奖", "缺口", "状态"].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    headRow.append(cell);
  });
  head.append(headRow);
  table.append(head);
  const body = document.createElement("tbody");
  games.forEach((game) => {
    const row = document.createElement("tr");
    row.className = `health-row ${game.status_tone || game.status || ""}`;
    row.title = game.advice || "";

    const gameCell = document.createElement("td");
    const gameName = document.createElement("b");
    gameName.textContent = GAME_LABELS[game.game_key] || game.game_name;
    const gameKey = document.createElement("span");
    gameKey.textContent = game.game_key;
    gameCell.append(gameName, gameKey);

    const providerCell = document.createElement("td");
    providerCell.textContent = game.provider;

    const countCell = document.createElement("td");
    countCell.textContent = game.draw_count;

    const rangeCell = document.createElement("td");
    rangeCell.textContent = `${game.earliest_date || "--"} / ${game.latest_date || "--"}`;

    const latestCell = document.createElement("td");
    latestCell.textContent = game.latest_issue || "--";
    const latestDate = document.createElement("span");
    latestDate.textContent = game.latest_date || "--";
    latestCell.append(latestDate);

    const nextCell = document.createElement("td");
    nextCell.textContent = game.next_draw_date || "--";

    const missingCell = document.createElement("td");
    missingCell.textContent = `${game.missing_recent_count} / ${game.staleness_days ?? "--"}天 / ${game.missing_trend || "stable"}`;

    const statusCell = document.createElement("td");
    const pill = document.createElement("em");
    pill.className = `status-pill ${game.status} ${game.status_tone || ""}`;
    pill.textContent = statusLabel(game.status);
    statusCell.append(pill);

    row.append(gameCell, providerCell, countCell, rangeCell, latestCell, nextCell, missingCell, statusCell);
    body.append(row);
  });
  table.append(body);
  els.healthTable.replaceChildren(table);
}

function renderLogs(logs) {
  if (!logs.length) {
    els.crawlLogs.textContent = "暂无抓取日志。";
    return;
  }
  const list = document.createElement("ul");
  list.className = "admin-log-list";
  logs.forEach((log) => {
    const item = document.createElement("li");
    const game = document.createElement("b");
    game.textContent = GAME_LABELS[log.game_key] || log.game_key;
    const summary = document.createElement("span");
    summary.textContent = `${log.source} · ${log.status} · 写入 ${log.wrote_count ?? 0}`;
    const time = document.createElement("time");
    time.textContent = log.finished_at || "--";
    item.append(game, summary, time);
    if (log.error) {
      const error = document.createElement("em");
      error.textContent = log.error;
      item.append(error);
    }
    list.append(item);
  });
  els.crawlLogs.replaceChildren(list);
}

function renderHealth(payload) {
  const kpis = payload.kpis || {};
  renderKpis(kpis);
  renderActionPlan(payload);
  renderHealthTable(payload.games || []);
  renderLogs(payload.logs || []);
  els.adminSummary.textContent = `今日 ${payload.today} · 健康 ${kpis.healthy_games ?? 0} · 关注 ${kpis.attention_games ?? 0} · 最近抓取 ${kpis.latest_crawl_at || "--"}`;
}

function renderSettings(payload) {
  if (!els.adminSettings) return;
  const grid = document.createElement("div");
  grid.className = "settings-grid";
  const weights = payload.metaphysics_weights || {};
  Object.entries(weights).forEach(([mode, values]) => {
    const card = document.createElement("article");
    card.className = "settings-card";
    const title = document.createElement("strong");
    title.textContent = {
      steady: "稳财号",
      windfall: "偏财号",
      guard: "守财号",
    }[mode] || mode;
    const list = document.createElement("ul");
    [
      ["个人时空", values.personal_space],
      ["AI 命理", values.ai_fortune],
      ["开奖日", values.draw_day_luck],
      ["数据托底", values.history_guardrail],
    ].forEach(([label, value]) => {
      const item = document.createElement("li");
      item.textContent = `${label} ${value ?? 0}%`;
      list.append(item);
    });
    card.append(title, list);
    grid.append(card);
  });

  const styleCard = document.createElement("article");
  styleCard.className = "settings-card settings-card-wide";
  const styleTitle = document.createElement("strong");
  styleTitle.textContent = "AI 文案风格";
  const styleList = document.createElement("ul");
  (payload.ai_copy_styles || []).forEach((style) => {
    const item = document.createElement("li");
    item.textContent = `${style.label}：${style.description || "--"}`;
    styleList.append(item);
  });
  styleCard.append(styleTitle, styleList);
  grid.append(styleCard);

  const oldGrid = els.adminSettings.querySelector(".settings-grid");
  if (oldGrid) oldGrid.replaceWith(grid);
}

async function loadSettings(epoch = adminSessionEpoch) {
  if (!els.adminSettings) return;
  const token = storedAdminToken();
  if (!token) {
    setLockedState(true, "请输入后台口令。");
    return;
  }
  try {
    const settings = await fetchJson("/api/admin/settings");
    if (!isCurrentToken(epoch, token)) return;
    renderSettings(settings);
  } catch (error) {
    if (error.status === 401 || !isCurrentEpoch(epoch) || error.name === "AbortError") return;
    const grid = els.adminSettings.querySelector(".settings-grid");
    if (grid) grid.textContent = "配置读取失败。";
  }
}

function renderTasks(payload) {
  if (!els.adminTaskList) return;
  const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
  if (!tasks.length) {
    els.adminTaskList.textContent = "暂无后台任务。";
    return;
  }
  const list = document.createElement("ul");
  list.className = "admin-task-items";
  tasks.slice(0, 8).forEach((task) => {
    const item = document.createElement("li");
    const title = document.createElement("b");
    title.textContent = `${task.provider || "--"} · ${(task.game_keys || []).join("/") || "--"}`;
    const status = document.createElement("span");
    status.textContent = `${task.status || "--"} · 写入 ${task.result?.wrote_count ?? 0}`;
    const time = document.createElement("time");
    time.textContent = task.finished_at || task.created_at || "--";
    item.append(title, status, time);
    if (task.error) {
      const error = document.createElement("em");
      error.textContent = task.error;
      item.append(error);
    }
    list.append(item);
  });
  els.adminTaskList.replaceChildren(list);
}

async function loadTasks(epoch = adminSessionEpoch) {
  if (!els.adminTaskList) return;
  const token = storedAdminToken();
  if (!token) {
    setLockedState(true, "请输入后台口令。");
    return;
  }
  try {
    const tasks = await fetchJson("/api/admin/tasks");
    if (!isCurrentToken(epoch, token)) return;
    renderTasks(tasks);
  } catch (error) {
    if (error.status === 401 || !isCurrentEpoch(epoch) || error.name === "AbortError") return;
    els.adminTaskList.textContent = "任务队列暂不可用。";
  }
}

function taskPayload() {
  const data = new FormData(els.adminTaskForm);
  const provider = data.get("provider") || "cwl";
  const games = String(data.get("games") || "")
    .split(/[,\s，、/]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  return {
    provider,
    games,
    source: data.get("source") || "auto",
    page_size: Number(data.get("page_size")) || 100,
    pages: Number(data.get("pages")) || 1,
  };
}

function setupTaskProviderDefaults() {
  if (!els.adminTaskForm) return;
  const providerSelect = els.adminTaskForm.querySelector('select[name="provider"]');
  const gamesInput = els.adminTaskForm.querySelector('input[name="games"]');
  providerSelect?.addEventListener("change", () => {
    const provider = providerSelect.value || "cwl";
    if (gamesInput) gamesInput.value = providerDefaults[provider] || providerDefaults.cwl;
  });
}

async function runAdminTask() {
  if (!els.adminTaskForm) return;
  const epoch = adminSessionEpoch;
  const token = storedAdminToken();
  if (!token) {
    setLockedState(true, "请输入后台口令。");
    return;
  }
  const payload = taskPayload();
  els.adminTaskRunButton.disabled = true;
  els.adminTaskResult.textContent = "任务执行中，请稍候。";
  try {
    const result = await fetchJson("/api/admin/tasks/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!isCurrentToken(epoch, token)) return;
    const task = result.task || {};
    els.adminTaskResult.textContent = `任务完成：${task.status || "--"}，写入 ${task.result?.wrote_count ?? 0} 条。`;
    renderHealth(result.health || {});
    await loadTasks(epoch);
  } catch (error) {
    if (error.status === 401 || !isCurrentEpoch(epoch) || error.name === "AbortError") return;
    els.adminTaskResult.textContent = "任务执行失败。";
  } finally {
    if (isCurrentEpoch(epoch)) {
      els.adminTaskRunButton.disabled = !hasAdminToken();
    }
  }
}

async function loadHealth(epoch = adminSessionEpoch) {
  const token = storedAdminToken();
  if (!token) {
    clearBusinessPanels();
    setLockedState(true, "请输入后台口令。");
    setStatus("后台已锁定", true);
    return;
  }
  setStatus("读取数据中");
  try {
    const health = await fetchJson("/api/admin/data-health");
    if (!isCurrentToken(epoch, token)) return;
    renderHealth(health);
    setStatus("数据已更新");
  } catch (error) {
    if (error.status === 401 || !isCurrentEpoch(epoch) || error.name === "AbortError") return;
    setStatus("数据后台暂不可用", true);
    els.adminSummary.textContent = "无法读取数据健康报告。";
  }
}

async function loadAdminData(epoch = adminSessionEpoch) {
  const token = storedAdminToken();
  if (!token) {
    clearBusinessPanels();
    setLockedState(true, "请输入后台口令。");
    setStatus("后台已锁定", true);
    return;
  }
  await loadHealth(epoch);
  if (!isCurrentToken(epoch, token)) return;
  await loadTasks(epoch);
}

async function validateAdminToken(token) {
  return fetchJson("/api/admin/settings", { tokenOverride: token });
}

async function unlockWithSettings(token, settingsPayload, { persistToken, epoch }) {
  if (!isCurrentEpoch(epoch)) return;
  if (persistToken) {
    saveAdminToken(token);
  }
  if (!isCurrentToken(epoch, token)) return;
  setLockedState(false);
  renderSettings(settingsPayload);
  setStatus("授权已通过");
  await loadAdminData(epoch);
}

async function unlockAdmin(event) {
  event.preventDefault();
  if (unlockValidationInFlight) return;
  const epoch = adminSessionEpoch;
  const submitted = (els.adminTokenInput?.value || "").trim();
  if (!submitted) {
    setAuthMessage("请输入后台口令。", true);
    return;
  }
  if (els.adminTokenInput) els.adminTokenInput.value = "";
  setUnlockBusy(true);
  setAuthMessage("正在验证后台口令。");
  setStatus("验证后台授权");
  try {
    const settingsPayload = await validateAdminToken(submitted);
    await unlockWithSettings(submitted, settingsPayload, { persistToken: true, epoch });
  } catch (error) {
    if (error.status === 401) return;
    if (!isCurrentEpoch(epoch) || error.name === "AbortError") return;
    clearBusinessPanels();
    setLockedState(true, "后台暂时无法验证，请稍后重试。");
    setStatus("后台验证失败", true);
  } finally {
    if (isCurrentEpoch(epoch) && _adminLockedForUnlock()) {
      setUnlockBusy(false);
    }
  }
}

function _adminLockedForUnlock() {
  return !els.dataAdmin || els.dataAdmin.dataset.locked === "true";
}

function lockAdmin() {
  invalidateAdminSession();
  setUnlockBusy(false);
  removeAdminToken();
  if (els.adminTokenInput) els.adminTokenInput.value = "";
  clearBusinessPanels();
  setLockedState(true, "需要授权后查看后台数据。");
  setStatus("后台已锁定", true);
}

async function validateStoredAdminSession() {
  const token = storedAdminToken();
  if (!token) {
    lockAdmin();
    return;
  }
  const epoch = adminSessionEpoch;
  clearBusinessPanels();
  setLockedState(true, "正在验证后台授权。");
  setStatus("验证后台授权");
  try {
    const settingsPayload = await validateAdminToken(token);
    await unlockWithSettings(token, settingsPayload, { persistToken: false, epoch });
  } catch (error) {
    if (error.status === 401) return;
    if (!isCurrentEpoch(epoch) || error.name === "AbortError") return;
    clearBusinessPanels();
    setLockedState(true, "后台暂时无法验证，请稍后重试。");
    setStatus("后台验证失败", true);
  }
}

els.refreshButton.addEventListener("click", () => {
  loadAdminData();
});
els.adminAuthForm?.addEventListener("submit", unlockAdmin);
els.adminLockButton?.addEventListener("click", lockAdmin);
els.adminTaskForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  runAdminTask();
});

setupTaskProviderDefaults();
if (hasAdminToken()) {
  validateStoredAdminSession();
} else {
  lockAdmin();
}
