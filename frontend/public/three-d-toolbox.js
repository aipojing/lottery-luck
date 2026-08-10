(() => {
  "use strict";

  const WINDOWS = Object.freeze([30, 60, 120]);
  const WINDOW_SET = new Set(WINDOWS);
  const DEFAULT_WINDOW = 30;
  const TOOLS = Object.freeze([
    { key: "trend", group: "stats", icon: "trending-up", title: "走势图", description: "按期查看百十个位变化" },
    { key: "omission", group: "stats", icon: "binary", title: "遗漏统计", description: "查看各位置当前遗漏" },
    { key: "frequency", group: "stats", icon: "chart-no-axes-column-increasing", title: "出次统计", description: "比较各数字出现次数" },
    { key: "heat", group: "stats", icon: "flame", title: "冷热码", description: "看哪些数字冷、哪些热" },
    { key: "number", group: "query", icon: "search", title: "号码查询", description: "查直选、组选和历史命中" },
    { key: "attributes", group: "query", icon: "list-filter", title: "号码属性", description: "查和值、跨度、奇偶等" },
    { key: "recent", group: "records", icon: "history", title: "最近开奖", description: "查看最近10期真实开奖" },
  ]);
  const TOOL_KEYS = new Set(TOOLS.map((tool) => tool.key));
  // Every tool that sends a statistics window with its own request: the four statistics tools
  // and 号码查询/号码属性 (their position stats are computed over that window). Their URL
  // carries the window, so a shared or reloaded link queries the same window it was made with.
  // 最近开奖 shows the fixed latest draws and asks for no window, so its URL carries none.
  const WINDOW_TOOLS = new Set([
    "trend",
    "omission",
    "frequency",
    "heat",
    "number",
    "attributes",
  ]);
  // The statistics tools are the only ones that offer a window switcher in the workspace; the
  // other window-reading tools take the window their link carried.
  const WINDOW_TAB_TOOLS = new Set(["trend", "omission", "frequency", "heat"]);
  const GROUP_TARGETS = Object.freeze({
    stats: "#threeDStatsTools",
    query: "#threeDQueryTools",
    records: "#threeDRecordTools",
  });
  // The CSS custom property that carries each tool's Lucide file into the icon mask.
  const ICON_URL_PROPERTY = "--three-d-icon-url";
  // Set on the toolbox root while a tool is open. The toolbox-home chrome — the kicker, the
  // page title, the home subtitle and the plan strip — is home content: with a tool open it
  // only pushes the tool's data down the page, so CSS collapses it under this scope. The page
  // heading itself is never removed, only made visually hidden (see workbench-3d.css).
  const TOOL_OPEN_CLASS = "is-tool-open";
  const GAME_KEY = "3d";
  const TODAY_PATTERN = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

  const TOOL_ERROR_MESSAGE = "加载失败，请重试。";

  const state = {
    tool: "",
    window: DEFAULT_WINDOW,
    generation: 0,
    abortController: null,
  };

  // The tools whose panel has already been opened successfully. A tool records `tool_opened`
  // at most once per page: a window change, a popstate, a re-render or a second visit to the
  // same tool all reach loadActiveTool again, and none of them is a first open.
  const openedTools = new Set();

  function normalizeTool(value) {
    const key = String(value || "").trim().toLowerCase();
    return TOOL_KEYS.has(key) ? key : "";
  }

  function normalizeWindow(value) {
    const parsed = Number(value);
    return WINDOW_SET.has(parsed) ? parsed : DEFAULT_WINDOW;
  }

  function readRoute() {
    const params = new URLSearchParams(window.location.search);
    const legacyMode = params.get("mode");
    return {
      tool: normalizeTool(params.get("tool") || (legacyMode === "pro" ? "frequency" : "")),
      window: normalizeWindow(params.get("window")),
    };
  }

  function routeUrl(tool, windowSize) {
    const params = new URLSearchParams();
    params.set("game", GAME_KEY);
    params.set("view", "data");
    params.set("window", String(normalizeWindow(windowSize)));
    if (tool) params.set("tool", tool);
    const today = new URLSearchParams(window.location.search).get("today");
    if (TODAY_PATTERN.test(today || "")) params.set("today", today);
    return `./analysis.html?${params.toString()}`;
  }

  function toolByKey(key) {
    return TOOLS.find((tool) => tool.key === key) || null;
  }

  function renderCatalog() {
    for (const selector of new Set(Object.values(GROUP_TARGETS))) {
      document.querySelector(selector)?.replaceChildren();
    }
    for (const tool of TOOLS) {
      const target = document.querySelector(GROUP_TARGETS[tool.group]);
      if (!target) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "three-d-tool-tile";
      button.dataset.threeDToolKey = tool.key;
      button.setAttribute("aria-label", tool.title);

      // The official Lucide file draws with `stroke="currentColor"`. Inside an <img> that
      // resolves to black, i.e. invisible on the black-gold surface, so the file is used as
      // a mask and the gold paint comes from CSS. The asset itself stays untouched.
      const icon = document.createElement("span");
      icon.className = "three-d-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.style.setProperty(ICON_URL_PROPERTY, `url("./assets/icons/${tool.icon}.svg")`);

      const title = document.createElement("strong");
      title.textContent = tool.title;
      const description = document.createElement("span");
      description.textContent = tool.description;
      button.append(icon, title, description);
      target.append(button);
    }
  }

  function renderWindowTabs() {
    const tabs = document.querySelector("#threeDToolWindows");
    if (!tabs) return;
    const usesWindow = WINDOW_TAB_TOOLS.has(state.tool);
    tabs.hidden = !usesWindow;
    tabs.replaceChildren();
    if (!usesWindow) return;
    for (const windowSize of WINDOWS) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.threeDWindow = String(windowSize);
      button.setAttribute("aria-pressed", String(state.window === windowSize));
      button.textContent = `近${windowSize}期`;
      tabs.append(button);
    }
  }

  function renderRoute() {
    const home = document.querySelector("#threeDToolHome");
    const workspace = document.querySelector("#threeDToolWorkspace");
    if (!home || !workspace) return;
    const hasTool = Boolean(state.tool);
    home.hidden = hasTool;
    workspace.hidden = !hasTool;
    document.querySelector("#threeDToolbox")?.classList.toggle(TOOL_OPEN_CLASS, hasTool);
    const selected = toolByKey(state.tool);
    const title = document.querySelector("#threeDToolTitle");
    const kicker = document.querySelector("#threeDToolKicker");
    if (title) title.textContent = selected?.title || "";
    if (kicker) kicker.textContent = selected?.description || "";
    document.querySelectorAll("[data-three-d-tool-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.threeDToolPanel !== state.tool;
    });
    renderWindowTabs();
  }

  function writeUrl(historyMode) {
    const method = historyMode === "push" ? "pushState" : "replaceState";
    window.history[method]({}, "", routeUrl(state.tool, state.window));
  }

  function toolStatusNode(tool) {
    if (!tool) return null;
    const panel = document.querySelector(`[data-three-d-tool-panel="${tool}"]`);
    return panel?.querySelector("[data-tool-status]") || null;
  }

  // The status line is where the panel prints its disclaimer, so an error message overwrites
  // it. Keep the sentence that was there so clearing the error can put it back: only the
  // statistics tools rewrite their own status line on a successful load, and the other four
  // would otherwise show the error above correct data for the rest of the session.
  function renderToolError(tool, message) {
    if (tool !== state.tool) return;
    const status = toolStatusNode(tool);
    if (!status) return;
    if (status.dataset.defaultText === undefined) {
      status.dataset.defaultText = status.textContent;
    }
    status.textContent = message;
    status.dataset.state = "error";
  }

  function clearToolError(tool) {
    const status = toolStatusNode(tool);
    if (!status) return;
    if (status.dataset.state === "error" && status.dataset.defaultText !== undefined) {
      status.textContent = status.dataset.defaultText;
    }
    delete status.dataset.state;
  }

  // Every load captures its generation. A superseded load is aborted and may not
  // write to the DOM, so a late response can never overwrite the current tool.
  function supersedeActiveLoad() {
    state.generation += 1;
    state.abortController?.abort();
    state.abortController = null;
  }

  // The event carries only aggregate-safe values: the game, the tool key (a closed whitelist
  // the server also enforces) and, where the tool really reads one, the statistics window.
  // No number, no free text, nothing about the person using it.
  function trackToolOpened(tool) {
    if (!TOOL_KEYS.has(tool) || openedTools.has(tool)) return;
    openedTools.add(tool);
    const properties = { game_key: GAME_KEY, tool_key: tool };
    if (WINDOW_TOOLS.has(tool)) properties.window = normalizeWindow(state.window);
    window.LotteryProduct?.track?.("tool_opened", properties)?.catch?.(() => {});
  }

  // Resolves to whether the tool's data really loaded, so the caller (the initial
  // activation) can decide whether the workbench counts as opened.
  async function loadActiveTool(options = {}) {
    if (!state.tool || !window.ThreeDWorkbench?.renderTool) return false;
    const tool = state.tool;
    const generation = state.generation;
    const controller = new AbortController();
    state.abortController = controller;
    clearToolError(tool);
    try {
      const rendered = await window.ThreeDWorkbench.renderTool(tool, {
        window: state.window,
        signal: controller.signal,
        flush: options.flush === true,
      });
      if (generation !== state.generation) return false;
      if (rendered === false) {
        renderToolError(tool, TOOL_ERROR_MESSAGE);
        return false;
      }
      // The only path where a tool panel really came up with its data. A superseded, aborted
      // or failed load has returned above, so none of them can be counted as an open.
      trackToolOpened(tool);
      return true;
    } catch (error) {
      if (error?.name !== "AbortError" && generation === state.generation) {
        renderToolError(tool, TOOL_ERROR_MESSAGE);
      }
      return false;
    } finally {
      if (generation === state.generation) state.abortController = null;
    }
  }

  // Opening a tool hides the tile the user just activated, so the browser would drop focus
  // back to the document. Move it into the workspace instead: a keyboard or screen-reader
  // user lands on the tool they asked for, one Tab away from the labelled way back.
  function moveFocusIntoWorkspace() {
    const workspace = document.querySelector("#threeDToolWorkspace");
    if (!workspace || workspace.hidden) return;
    workspace.focus({ preventScroll: true });
  }

  // Leaving a tool hides the workspace; return focus to the tile that opened it so the
  // keyboard user resumes where they were instead of at the top of the page.
  function moveFocusToTile(tool) {
    if (!tool) return;
    const tile = document.querySelector(`[data-three-d-tool-key="${tool}"]`);
    if (!tile || tile.offsetParent === null) return;
    tile.focus({ preventScroll: true });
  }

  function openTool(tool, options = {}) {
    supersedeActiveLoad();
    state.tool = normalizeTool(tool);
    renderRoute();
    writeUrl(options.historyMode === "replace" ? "replace" : "push");
    if (options.focus !== false) moveFocusIntoWorkspace();
    loadActiveTool();
  }

  function setWindow(value) {
    const normalized = normalizeWindow(value);
    if (normalized === state.window) return;
    supersedeActiveLoad();
    state.window = normalized;
    renderWindowTabs();
    writeUrl("replace");
    // renderTool receives the new window and decides whether a refetch is needed;
    // pushing it into the workbench first would hide the change from that check.
    loadActiveTool();
  }

  // Only tools that read a statistics window carry `window` in the URL, so an absent
  // param means "keep the window the user already chose", not "reset to default".
  function routeFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const route = readRoute();
    return {
      tool: route.tool,
      window: params.has("window") ? route.window : state.window,
    };
  }

  function applyRoute(route) {
    state.tool = normalizeTool(route.tool);
    state.window = normalizeWindow(route.window);
    renderRoute();
  }

  function initializeRoute(options = {}) {
    applyRoute(options.reset === true ? { tool: "", window: DEFAULT_WINDOW } : routeFromUrl());
    if (options.preserveHistory === true) {
      return {
        ...currentRoute(),
        load: state.tool ? loadActiveTool({ flush: true }) : null,
      };
    }
    if (!state.tool) {
      writeUrl("replace");
      return { ...currentRoute(), load: null };
    }
    // A deep link lands directly in a tool. Seed a toolbox-home entry underneath it
    // so 返回 goes back to the toolbox instead of leaving the page.
    window.history.replaceState({}, "", routeUrl("", state.window));
    window.history.pushState({}, "", routeUrl(state.tool, state.window));
    // The first load must take the same generation/abort-aware path as every later one,
    // so a failing deep link reports the error inside the active tool panel. The caller
    // awaits this promise instead of starting a second load of its own.
    return { ...currentRoute(), load: loadActiveTool({ flush: true }) };
  }

  function currentRoute() {
    return { tool: state.tool, window: state.window };
  }

  function handlePopState() {
    supersedeActiveLoad();
    const previousTool = state.tool;
    applyRoute(routeFromUrl());
    if (state.tool) {
      moveFocusIntoWorkspace();
    } else {
      moveFocusToTile(previousTool);
    }
    return loadActiveTool();
  }

  function bindListeners() {
    document.querySelector("#threeDToolHome")?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-three-d-tool-key]");
      if (!button) return;
      openTool(button.dataset.threeDToolKey);
    });
    document.querySelector("#threeDToolWindows")?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-three-d-window]");
      if (!button) return;
      setWindow(button.dataset.threeDWindow);
    });
    document.querySelector("#threeDToolBack")?.addEventListener("click", () => {
      if (state.tool) window.history.back();
    });
  }

  renderCatalog();
  bindListeners();

  window.ThreeDToolbox = Object.freeze({
    TOOLS,
    normalizeTool,
    normalizeWindow,
    readRoute,
    routeUrl,
    openTool,
    initializeRoute,
    currentRoute,
    handlePopState,
    // The toolbox owns the error it writes into a tool's status line, so it also owns taking
    // it back. The workbench calls this when a reload from the freshness band succeeds, the
    // one recovery path that never goes through a tool load.
    clearToolError,
  });
})();
