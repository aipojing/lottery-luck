(() => {
  "use strict";

  const GAME_KEYS = ["ssq", "dlt", "3d", "pl3", "kl8"];
  const TOOL_KEYS = ["quick", "lock", "full", "dantuo", "conditional", "reduce", "organize"];
  const BASKET_KEY = "lottery_tool_basket_v1";
  const HANDOFF_KEY = "lottery_research_handoff_v1";
  const HANDOFF_MAX_AGE_MS = 30 * 60 * 1000;
  const POOL_MIGRATION_KEY = "lottery_tool_pool_migration_v1";
  const STRATEGY_NUMBER_FIELDS = [
    "exclude_recent", "min_hot", "sum_min", "sum_max", "max_consecutive_run",
    "ac_min", "ac_max", "min_omission",
  ];
  const STRATEGY_TEXT_FIELDS = ["odd_even", "prime_composite", "mod3", "zone", "tail_exclude", "tail_include"];
  const STRATEGY_FIELD_LABELS = {
    exclude_recent: "排除近 N 期",
    min_hot: "至少热号",
    odd_even: "奇偶比",
    sum_min: "和值下限",
    sum_max: "和值上限",
    max_consecutive_run: "最大连号长度",
    ac_min: "AC 值下限",
    ac_max: "AC 值上限",
    prime_composite: "质合比",
    mod3: "012 路比",
    zone: "区间比",
    tail_exclude: "排除尾数",
    tail_include: "包含尾数",
    min_omission: "最小遗漏",
  };
  const EMPTY_BASKET = () => ({
    version: 1,
    games: { ssq: [], dlt: [], "3d": [], pl3: [], kl8: [] },
  });
  let config = null;
  let surfaces = null;
  let memoryBasket = null;
  let requestToken = 0;
  let lastComputed = null;
  let activeHandoff = null;
  let handoffRejected = false;
  let publicGameKeys = [...GAME_KEYS];

  function numberList(values) {
    return Array.isArray(values)
      ? [...new Set(values.filter(Number.isInteger))].sort((left, right) => left - right)
      : [];
  }

  function normalizeEntry(entry, gameKey = "") {
    if (!entry || typeof entry !== "object") return null;
    const normalizedGameKey = GAME_KEYS.includes(entry.game_key) ? entry.game_key : gameKey;
    const isDigitGame = normalizedGameKey === "3d" || normalizedGameKey === "pl3";
    const playType = typeof entry.play_type === "string" ? entry.play_type : "straight";
    const rawMain = Array.isArray(entry.main) && entry.main.every(Number.isInteger) ? [...entry.main] : [];
    const normalized = {
      game_key: normalizedGameKey,
      // 数字彩直选的百十个位和重复次数都是号码本身，不能按乐透号码排序去重。
      main: isDigitGame ? rawMain : numberList(entry.main),
      special: numberList(entry.special),
      positions: Array.isArray(entry.positions) ? entry.positions.map(numberList) : [],
      play_type: playType,
      multiplier: Number.isInteger(entry.multiplier) && entry.multiplier > 0 ? entry.multiplier : 1,
      entry_cost: Number.isFinite(entry.entry_cost) && entry.entry_cost > 0 ? entry.entry_cost : 0,
      source: typeof entry.source === "string" ? entry.source : "quick",
      added_at: typeof entry.added_at === "string" ? entry.added_at : new Date().toISOString(),
      text: typeof entry.text === "string" ? entry.text : "",
    };
    return normalized.game_key && (normalized.main.length || normalized.positions.length) ? normalized : null;
  }

  function entryIdentity(entry) {
    return [entry.game_key, entry.play_type || "straight", entry.main.join(" "), entry.special.join(" "), entry.positions.map((item) => item.join(" ")).join("|")].join("/");
  }

  function sanitizeBasket(value) {
    const basket = EMPTY_BASKET();
    if (!value || typeof value !== "object" || !value.games || typeof value.games !== "object") return basket;
    GAME_KEYS.forEach((gameKey) => {
      const seen = new Set();
      basket.games[gameKey] = (Array.isArray(value.games[gameKey]) ? value.games[gameKey] : [])
        .map((entry) => normalizeEntry(entry, gameKey))
        .filter((entry) => {
          if (!entry || seen.has(entryIdentity(entry))) return false;
          seen.add(entryIdentity(entry));
          return true;
        })
        .slice(0, 500);
    });
    return basket;
  }

  function readBasket() {
    if (memoryBasket) return memoryBasket;
    try {
      return sanitizeBasket(JSON.parse(localStorage.getItem(BASKET_KEY) || "null"));
    } catch (_) {
      return EMPTY_BASKET();
    }
  }

  function showBasketWarning(message) {
    const warning = document.querySelector("#basketWarning");
    if (warning) {
      warning.hidden = !message;
      warning.textContent = message || "";
    }
  }

  function writeBasket(value, warning = "") {
    const basket = sanitizeBasket(value);
    try {
      localStorage.setItem(BASKET_KEY, JSON.stringify(basket));
      memoryBasket = null;
      showBasketWarning(warning);
    } catch (error) {
      memoryBasket = basket;
      showBasketWarning("浏览器存储空间不足，号码篮仅在本次打开期间保存。");
    }
    renderBasket(basket);
    return basket;
  }

  function addEntriesToBasket(gameKey, entries, source, costMeta = {}) {
    if (!GAME_KEYS.includes(gameKey)) return readBasket();
    const basket = readBasket();
    const existing = basket.games[gameKey];
    const seen = new Set(existing.map(entryIdentity));
    let limitReached = false;
    (Array.isArray(entries) ? entries : []).forEach((entry) => {
      const normalized = normalizeEntry({ ...costMeta, ...entry, game_key: gameKey, source }, gameKey);
      if (normalized && !seen.has(entryIdentity(normalized)) && existing.length < 500) {
        seen.add(entryIdentity(normalized));
        existing.push(normalized);
      } else if (normalized && !seen.has(entryIdentity(normalized))) {
        limitReached = true;
      }
    });
    return writeBasket(
      basket,
      limitReached ? "当前彩种号码篮最多保存 500 组；超出的号码未加入，请先导出或清理。" : "",
    );
  }

  function removeBasketEntry(gameKey, index) {
    const basket = readBasket();
    if (GAME_KEYS.includes(gameKey)) basket.games[gameKey].splice(index, 1);
    return writeBasket(basket);
  }

  function clearBasket(gameKey) {
    const basket = readBasket();
    if (GAME_KEYS.includes(gameKey)) basket.games[gameKey] = [];
    return writeBasket(basket);
  }

  function presetLabel(preset) {
    return { balanced: "均衡型", conservative: "保守型", aggressive: "激进型" }[preset] || preset;
  }

  function isDigitGame(gameKey) {
    return gameKey === "3d" || gameKey === "pl3";
  }

  function peekResearchHandoff(gameKey) {
    const raw = sessionStorage.getItem(HANDOFF_KEY);
    if (!raw) return { value: null, error: "策略条件未能带入，请重新选择。" };
    try {
      const value = JSON.parse(raw);
      const age = Date.now() - value.created_at;
      const fresh = Number.isFinite(value.created_at) && age >= 0 && age <= HANDOFF_MAX_AGE_MS;
      if (value.version !== 1 || value.game_key !== gameKey || value.source !== "strategy" || !fresh) {
        return { value: null, error: "策略条件未能带入，请重新选择。" };
      }
      return { value, error: "" };
    } catch (_) {
      return { value: null, error: "策略条件未能带入，请重新选择。" };
    }
  }

  function maybeConsumeHandoff() {
    const params = new URLSearchParams(window.location.search);
    const state = urlState();
    if (state.tool !== "conditional") return;
    const hadHandoff = sessionStorage.getItem(HANDOFF_KEY) !== null || params.get("source") === "strategy";
    const peeked = peekResearchHandoff(state.game);
    if (peeked.value) {
      // A valid handoff must still be readable once the navigation that carried it settles,
      // so it is consumed only after the load event. Invalid or stale handoffs are removed
      // at once and reported before the page finishes loading.
      window.addEventListener(
        "load",
        () => {
          setTimeout(() => {
            sessionStorage.removeItem(HANDOFF_KEY);
            activeHandoff = peeked.value;
            const current = urlState();
            if (current.tool === "conditional" && config) activate(current.game, current.tool);
          }, 200);
        },
        { once: true },
      );
    } else if (hadHandoff) {
      sessionStorage.removeItem(HANDOFF_KEY);
      handoffRejected = true;
      setStatus(peeked.error, true);
    }
  }

  function migrateLegacyPools() {
    if (localStorage.getItem(POOL_MIGRATION_KEY) === "1") return;
    const next = sanitizeBasket(readBasket());
    for (const gameKey of publicGameKeys) {
      let rows;
      try {
        rows = JSON.parse(localStorage.getItem(`lotteryLuck:numberPool:${gameKey}`) || "[]");
      } catch (_) {
        setStatus(`${gameKey} 的旧号码池无法读取，原数据已保留。`, true);
        continue;
      }
      if (!Array.isArray(rows)) continue;
      const seen = new Set(next.games[gameKey].map(entryIdentity));
      rows.forEach((row) => {
        const entry = normalizeEntry(
          { ...row, game_key: gameKey, source: "legacy_pool", play_type: typeof row?.play_type === "string" ? row.play_type : "straight" },
          gameKey,
        );
        if (!entry || seen.has(entryIdentity(entry)) || next.games[gameKey].length >= 500) return;
        seen.add(entryIdentity(entry));
        next.games[gameKey].push(entry);
      });
    }
    try {
      localStorage.setItem(BASKET_KEY, JSON.stringify(next));
      localStorage.setItem(POOL_MIGRATION_KEY, "1");
      memoryBasket = null;
      renderBasket(next);
    } catch (_) {
      memoryBasket = next;
      showBasketWarning("旧号码池暂时无法写入浏览器存储，原数据已保留。");
    }
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }

  function formatCsv(gameKey, entries, defaultSource = "quick") {
    const rows = ["game_key,main,special,source,play_type"];
    (Array.isArray(entries) ? entries : []).forEach((entry) => {
      const normalized = normalizeEntry(
        { ...entry, source: typeof entry?.source === "string" ? entry.source : defaultSource },
        gameKey,
      );
      if (!normalized) return;
      const mainValue = (normalized.game_key === "3d" || normalized.game_key === "pl3") && normalized.play_type === "straight"
        ? normalized.main.join("")
        : normalized.main.join(" ");
      rows.push([
        normalized.game_key,
        mainValue,
        normalized.special.join(" "),
        normalized.source,
        normalized.play_type || "straight",
      ].map(csvCell).join(","));
    });
    return rows.join("\n");
  }

  function urlState() {
    const params = new URLSearchParams(window.location.search);
    const game = GAME_KEYS.includes(params.get("game")) ? params.get("game") : "ssq";
    const tool = TOOL_KEYS.includes(params.get("tool")) ? params.get("tool") : "quick";
    const next = new URLSearchParams();
    next.set("game", game);
    next.set("tool", tool);
    if (tool === "conditional" && params.get("source")) next.set("source", params.get("source"));
    if (params.toString() !== next.toString()) {
      history.replaceState(null, "", `./tools.html?${next.toString()}`);
    }
    return { game, tool };
  }

  function setState(game, tool, { announceSwitch = false, focusWorkbench = false } = {}) {
    history.replaceState(null, "", `./tools.html?game=${game}&tool=${tool}`);
    activate(game, tool);
    if (announceSwitch) setStatus("已切换规则；未加入号码篮的当前结果已清空。");
    if (focusWorkbench) {
      const workbench = document.querySelector("#toolWorkbench");
      const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      workbench?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
      workbench?.focus({ preventScroll: true });
    }
  }

  function rangeButtons(zone, minimum, maximum, extra = "") {
    return `<div class="number-zone" data-number-zone="${zone}">${Array.from({ length: maximum - minimum + 1 }, (_, index) => {
      const number = minimum + index;
      const label = String(number).padStart(2, "0");
      return `<button type="button" data-number="${number}" aria-pressed="false" aria-label="${label}，当前：未选择" ${extra}>${label}</button>`;
    }).join("")}</div>`;
  }

  function optionsMarkup(game) {
    const controls = ["<label>倍数 <input name=\"multiplier\" type=\"number\" min=\"1\" max=\"99\" value=\"1\"></label>"];
    if (game.add_on_cost) controls.push("<label class=\"check-control\"><input name=\"add_on\" type=\"checkbox\"> 追加投注</label>");
    if (game.play_types) controls.push(`<label>玩法 <select name="play_type">${game.play_types.map((value) => `<option value="${value}" ${value === game.main.count ? "selected" : ""}>选${value}</option>`).join("")}</select></label>`);
    return `<div class="tool-options">${controls.join("")}</div>`;
  }

  function selectionMarkup(game, mode) {
    if (game.positions) {
      return Array.from({ length: game.positions }, (_, index) => `<fieldset><legend>第 ${index + 1} 位</legend>${rangeButtons(`position-${index}`, game.digits.min, game.digits.max)}</fieldset>`).join("");
    }
    const mainExtra = mode === "dantuo" ? "data-dantuo-number" : "";
    const specialExtra = mode === "dantuo" ? "data-dantuo-number" : "";
    return `<fieldset><legend>前区号码</legend>${rangeButtons("main", game.main.min, game.main.max, mainExtra)}</fieldset>${game.special ? `<fieldset><legend>后区号码</legend>${rangeButtons("special", game.special.min, game.special.max, specialExtra)}</fieldset>` : ""}`;
  }

  function digitConditionalMarkup(game) {
    const checkGroup = (name, legend, values) => `<fieldset class="conditional-checks"><legend>${legend}</legend>${values
      .map((value) => `<label><input type="checkbox" name="${name}" value="${value}" checked> ${value}</label>`)
      .join("")}</fieldset>`;
    const positionInputs = (prefix, legend) => `<fieldset><legend>${legend}</legend><div class="conditional-grid">${["百位", "十位", "个位"]
      .map((label, index) => `<label>${label}<input name="${prefix}_${index}" inputmode="numeric" autocomplete="off" placeholder="如 1 8"></label>`)
      .join("")}</div></fieldset>`;
    return `<div class="conditional-fields" id="conditionalDigitFields">
      <div class="conditional-grid">
        <label>生成注数 <input name="count" type="number" min="1" max="200" value="8"></label>
        <label>和值下限 <input name="sum_min" type="number" min="0" max="27" value="0"></label>
        <label>和值上限 <input name="sum_max" type="number" min="0" max="27" value="27"></label>
        <label>跨度下限 <input name="span_min" type="number" min="0" max="9" value="0"></label>
        <label>跨度上限 <input name="span_max" type="number" min="0" max="9" value="9"></label>
      </div>
      ${checkGroup("types", "组态", ["豹子", "组三", "组六"])}
      ${checkGroup("odd_counts", "奇数个数", [0, 1, 2, 3])}
      ${checkGroup("big_counts", "大数个数", [0, 1, 2, 3])}
      ${positionInputs("position_include", "位置包含")}
      ${positionInputs("position_exclude", "位置排除")}
    </div>${optionsMarkup(game)}`;
  }

  function strategyConditionalMarkup(game, handoff) {
    const escapeAttribute = (value) => String(value).replaceAll("&", "&amp;").replaceAll("\"", "&quot;").replaceAll("<", "&lt;");
    const fields = surfaces?.games?.[game.key]?.research?.strategy?.condition_fields
      || [...STRATEGY_NUMBER_FIELDS, ...STRATEGY_TEXT_FIELDS];
    const conditions = handoff?.conditions && typeof handoff.conditions === "object" ? handoff.conditions : {};
    const fieldMarkup = fields.map((name) => {
      const label = STRATEGY_FIELD_LABELS[name] || name;
      const value = conditions[name];
      const filled = value === 0 ? "0" : (value ?? "");
      const type = STRATEGY_NUMBER_FIELDS.includes(name) ? " type=\"number\"" : "";
      return `<label>${label}<input name="${name}"${type} value="${escapeAttribute(filled)}"></label>`;
    }).join("");
    const presets = ["balanced", "conservative", "aggressive"];
    const selectedPreset = presets.includes(handoff?.preset) ? handoff.preset : "balanced";
    const windowValue = Number.isFinite(Number(handoff?.window)) && Number(handoff.window) > 0 ? Number(handoff.window) : 120;
    return `<div class="conditional-fields" id="conditionalStrategyFields">
      <div class="conditional-grid">
        <label>策略预设 <select name="preset">${presets.map((preset) => `<option value="${preset}" ${preset === selectedPreset ? "selected" : ""}>${presetLabel(preset)}</option>`).join("")}</select></label>
        <label>生成组数 <input name="count" type="number" min="1" max="30" value="8"></label>
        <label>统计窗口 <input name="window" type="number" min="1" max="300" value="${windowValue}"></label>
      </div>
      <div class="conditional-grid">${fieldMarkup}</div>
    </div>${optionsMarkup(game)}`;
  }

  function formMarkup(gameKey, tool) {
    const game = config.games[gameKey];
    const action = tool === "lock" ? "quick-pick" : tool === "quick" ? "quick-pick" : tool === "full" || tool === "dantuo" ? "compose" : tool;
    let body = "";
    if (tool === "conditional") {
      const handoff = activeHandoff && activeHandoff.game_key === gameKey ? activeHandoff : null;
      body = isDigitGame(gameKey) && handoff?.source !== "strategy"
        ? digitConditionalMarkup(game)
        : strategyConditionalMarkup(game, handoff);
    } else if (tool === "quick") {
      body = "<label>生成注数 <input name=\"count\" type=\"number\" min=\"1\" max=\"20\" value=\"5\"></label>" + optionsMarkup(game);
    } else if (tool === "lock") {
      body = `<p class="tool-help">点击号码依次切换：关注、排除、未选择。</p>${selectionMarkup(game, "lock")}${optionsMarkup(game)}`;
    } else if (tool === "full") {
      body = `${selectionMarkup(game, "full")}${optionsMarkup(game)}`;
    } else if (tool === "dantuo") {
      if (game.positions) {
        body = `<label>组选方式 <select name="group_mode"><option value="group3">组三</option><option value="group6" selected>组六</option></select></label><fieldset><legend>包号数字</legend>${rangeButtons("digits", game.digits.min, game.digits.max)}</fieldset>${optionsMarkup(game)}`;
      } else {
        body = `<p class="tool-help">点击号码依次切换：胆码、拖码、未选择。</p>${selectionMarkup(game, "dantuo")}${optionsMarkup(game)}`;
      }
    } else if (tool === "reduce") {
      const hasCurrent = lastComputed?.gameKey === gameKey && (lastComputed.source || lastComputed.entries?.length);
      const currentCount = lastComputed?.ticketCount || lastComputed?.entries?.length || 0;
      body = `<label>预算（元）<input name="budget" type="number" min="2" max="20000" value="20"></label>${hasCurrent ? `<label class="basket-check"><input type="radio" name="reduce_source" value="current" checked> 使用刚计算出的${lastComputed.label || "完整组合"}（${currentCount} 注）</label>` : ""}<label class="basket-check"><input type="radio" name="reduce_source" value="basket" ${hasCurrent ? "" : "checked"}> 使用号码篮</label><div class="reduce-entries">${basketCheckboxes(gameKey)}</div>${optionsMarkup(game)}`;
    } else {
      body = `<label>批次 A<textarea name="batch_a" rows="5" placeholder="每行一注号码"></textarea></label><label>批次 B<textarea name="batch_b" rows="5" placeholder="每行一注号码"></textarea></label><label>整理方式 <select name="operation"><option value="dedupe">批次 A 去重</option><option value="union">合并</option><option value="intersection">交集</option><option value="difference">A 减 B</option></select></label>${optionsMarkup(game)}`;
    }
    return `<form class="tool-form${tool === "conditional" ? " conditional-form" : ""}" data-action="${action}" data-tool="${tool}" novalidate>${body}<button class="tool-submit" type="submit">执行${document.querySelector(`[data-tool-card="${tool}"] strong`)?.textContent || "工具"}</button></form>`;
  }

  function basketCheckboxes(gameKey) {
    const entries = readBasket().games[gameKey];
    if (!entries.length) return "<p class=\"tool-empty\">当前彩种的号码篮为空，请先从结果中加入号码。</p>";
    return entries.map((entry, index) => `<label class="basket-check"><input type="checkbox" name="basket_entry" value="${index}" checked> ${entry.text || entry.main.join(" ")}</label>`).join("");
  }

  function applySurfaceLabels(game) {
    const gameSurface = surfaces?.games?.[game];
    if (!gameSurface) return;
    const visibleTools = Array.isArray(gameSurface.tools) && gameSurface.tools.length ? gameSurface.tools : TOOL_KEYS;
    document.querySelectorAll("[data-tool-card]").forEach((button) => {
      button.hidden = !visibleTools.includes(button.dataset.toolCard);
    });
    Object.entries(gameSurface.tool_labels || {}).forEach(([toolKey, label]) => {
      const title = document.querySelector(`[data-tool-card="${toolKey}"] strong`);
      if (title && label) title.textContent = label;
    });
  }

  function renderConditionalSource(tool) {
    const source = document.querySelector("#conditionalSource");
    if (!source) return;
    if (tool === "conditional" && activeHandoff) {
      source.textContent = `来源：${activeHandoff.name || presetLabel(activeHandoff.preset)} · 条件已预填，确认后再生成。`;
      source.hidden = false;
    } else {
      source.textContent = "";
      source.hidden = true;
    }
  }

  function activate(game, tool) {
    requestToken += 1;
    resetResult();
    document.querySelectorAll("[data-game-key]").forEach((button) => button.setAttribute("aria-current", String(button.dataset.gameKey === game)));
    document.querySelectorAll("[data-tool-card]").forEach((button) => button.setAttribute("aria-current", String(button.dataset.toolCard === tool)));
    updateDantuoLabel(game);
    applySurfaceLabels(game);
    const card = document.querySelector(`[data-tool-card="${tool}"] strong`);
    document.querySelector("#workbenchTitle").textContent = card?.textContent || "选号工具";
    renderConditionalSource(tool);
    const form = document.querySelector("#toolForm");
    form.hidden = false;
    form.innerHTML = config?.games?.[game] ? formMarkup(game, tool) : "<p class=\"tool-empty\">工具配置不可用，暂不能提交。</p>";
    updateLiveCost(form.querySelector("form"), game, tool);
  }

  function updateDantuoLabel(game) {
    const title = document.querySelector('[data-tool-card="dantuo"] strong');
    const description = document.querySelector('[data-tool-card="dantuo"] span');
    const isDigitGame = game === "3d" || game === "pl3";
    if (title) title.textContent = isDigitGame ? "组选包号" : "胆拖组号";
    if (description) description.textContent = isDigitGame ? "选择数字组成组三或组六包号。" : "以胆码和拖码组织方案。";
  }

  function resetResult() {
    const panel = document.querySelector("#toolResult");
    if (!panel) return;
    panel.querySelector(".tool-result-body")?.remove();
    if (!panel.querySelector("#resultEmpty")) {
      const empty = document.createElement("div");
      empty.className = "tool-empty";
      empty.id = "resultEmpty";
      empty.textContent = "生成的号码与计算结果会显示在这里。";
      panel.querySelector("#costSummary").before(empty);
    }
    panel.querySelector("#resultTitle").textContent = "等待生成";
    panel.querySelector("#costSummary").textContent = "预计金额：--";
    panel.__entries = [];
    delete panel.dataset.resultGame;
    delete panel.dataset.resultTool;
  }

  function renderGames() {
    const tabs = document.querySelector("#toolGameTabs");
    if (!tabs || !config?.games) return;
    tabs.innerHTML = GAME_KEYS.filter((key) => config.games[key]).map((key) => `<button type="button" data-game-key="${key}">${config.games[key].name}</button>`).join("");
  }

  function basketEstimatedCost(gameKey, entries) {
    const fallbackCost = config?.games?.[gameKey]?.unit_cost || 2;
    return (entries || []).reduce(
      (total, entry) => total + (entry.entry_cost || fallbackCost) * (entry.multiplier || 1),
      0,
    );
  }

  function renderBasket(basket = readBasket()) {
    const { game } = urlState();
    const entries = basket.games[game];
    const empty = document.querySelector("[data-basket-empty]");
    const list = document.querySelector("#basketEntries");
    const count = document.querySelectorAll("[data-basket-count], #basketCount");
    count.forEach((node) => { node.textContent = String(entries.length); });
    const mobileCost = document.querySelector("#mobileBasketCost");
    if (mobileCost) mobileCost.textContent = `${basketEstimatedCost(game, entries)} 元`;
    if (empty) empty.hidden = entries.length > 0;
    if (list) list.innerHTML = entries.map((entry, index) => `<li><span>${entry.text || entry.main.join(" ")}</span><button type="button" data-remove-basket="${index}">移除</button></li>`).join("");
  }

  function selectedNumbers(form, zone, state) {
    return [...form.querySelectorAll(`[data-number-zone="${zone}"] [data-number]`)]
      .filter((button) => (state ? button.dataset.choice === state : button.getAttribute("aria-pressed") === "true"))
      .map((button) => Number(button.dataset.number));
  }

  function formOptions(form) {
    const options = { multiplier: Number(form.elements.multiplier?.value || 1) };
    if (form.elements.add_on) options.add_on = form.elements.add_on.checked;
    if (form.elements.play_type) options.play_type = Number(form.elements.play_type.value);
    return options;
  }

  function chooseCount(total, picked) {
    if (!Number.isInteger(total) || !Number.isInteger(picked) || total < picked || picked < 0) return null;
    let result = 1;
    for (let index = 1; index <= picked; index += 1) result = (result * (total - picked + index)) / index;
    return result;
  }

  function zoneDantuoCount(form, zone, picked, requiresDan = false) {
    const dan = selectedNumbers(form, zone, "dan").length;
    const tuo = selectedNumbers(form, zone, "tuo").length;
    if (requiresDan && !dan) return null;
    if (dan > picked || (dan === picked && tuo)) return null;
    if (dan === picked) return 1;
    return chooseCount(tuo, picked - dan);
  }

  function reductionSourceCount(form, gameKey) {
    if (form.elements.reduce_source?.value === "current") {
      return lastComputed?.gameKey === gameKey ? Number(lastComputed.ticketCount || lastComputed.entries?.length || 0) : 0;
    }
    return form.querySelectorAll('input[name="basket_entry"]:checked').length;
  }

  function previewTicketCount(form, game, tool) {
    if (!form || !game) return null;
    if (tool === "quick") return Number(form.elements.count?.value || 0);
    if (tool === "conditional") {
      const count = Number(form.elements.count?.value || 0);
      return Number.isInteger(count) && count > 0 ? count : null;
    }
    if (tool === "lock") return 1;
    if (tool === "reduce") {
      const budget = Number(form.elements.budget?.value || 0);
      const options = formOptions(form);
      const entryCost = game.unit_cost + (options.add_on ? game.add_on_cost || 0 : 0);
      const allowedByBudget = Math.floor(budget / Math.max(1, entryCost * options.multiplier));
      return Math.max(0, Math.min(allowedByBudget, reductionSourceCount(form, game.key), 5000));
    }
    if (tool === "organize") return null;
    if (tool === "full") {
      if (game.positions) {
        const lengths = Array.from({ length: game.positions }, (_, index) => selectedNumbers(form, `position-${index}`).length);
        return lengths.every(Boolean) ? lengths.reduce((total, value) => total * value, 1) : null;
      }
      const mainPicked = game.play_types ? Number(form.elements.play_type.value) : game.main.count;
      const main = chooseCount(selectedNumbers(form, "main").length, mainPicked);
      const special = game.special ? chooseCount(selectedNumbers(form, "special").length, game.special.count) : 1;
      return main === null || special === null ? null : main * special;
    }
    if (tool === "dantuo") {
      if (game.positions) return chooseCount(selectedNumbers(form, "digits").length, form.elements.group_mode.value === "group3" ? 2 : 3);
      const mainPicked = game.play_types ? Number(form.elements.play_type.value) : game.main.count;
      const main = zoneDantuoCount(form, "main", mainPicked, game.key !== "dlt");
      const special = game.special ? zoneDantuoCount(form, "special", game.special.count) : 1;
      return main === null || special === null ? null : main * special;
    }
    return null;
  }

  function updateLiveCost(form, gameKey, tool) {
    const summary = document.querySelector("#liveCostSummary");
    const costSummary = document.querySelector("#costSummary");
    const game = config?.games?.[gameKey];
    if (!summary || !game) return;
    const ticketCount = previewTicketCount(form, game, tool);
    if (!Number.isFinite(ticketCount) || ticketCount < 0) {
      summary.textContent = "实时预估：请选择足够的号码后计算注数与金额。";
      return;
    }
    const options = formOptions(form);
    const entryCost = game.unit_cost + (options.add_on ? game.add_on_cost || 0 : 0);
    const totalCost = ticketCount * entryCost * options.multiplier;
    const warning = totalCost > 20000 ? "；超过 20,000 元上限，不能生成。" : "";
    const text = `实时预估：${totalCost} 元，共 ${ticketCount} 注${warning}`;
    summary.textContent = text;
    if (costSummary) costSummary.textContent = text.replace("实时预估：", "预计金额：");
  }

  function setNumberChoice(button, choice) {
    const labels = { "": "未选择", selected: "已选择", locked: "锁定", excluded: "排除", dan: "胆码", tuo: "拖码" };
    button.dataset.choice = choice;
    button.setAttribute("aria-pressed", String(choice === "selected" || choice === "locked" || choice === "dan" || choice === "tuo"));
    button.setAttribute("aria-label", `${button.textContent.trim()}，当前：${labels[choice] || "未选择"}`);
  }

  function serializeForm(form, gameKey, tool) {
    const game = config.games[gameKey];
    const options = formOptions(form);
    if (tool === "quick") return { count: Number(form.elements.count.value), options, locked: {}, excluded: {} };
    if (tool === "lock") {
      const zones = game.positions ? Array.from({ length: game.positions }, (_, index) => `position-${index}`) : ["main", "special"];
      const locked = {};
      const excluded = {};
      zones.forEach((zone) => {
        const key = zone.startsWith("position-") ? "positions" : zone;
        const lockedValues = selectedNumbers(form, zone, "locked");
        const excludedValues = selectedNumbers(form, zone, "excluded");
        if (zone.startsWith("position-")) {
          (locked.positions ||= []).push(lockedValues);
          (excluded.positions ||= []).push(excludedValues);
        } else {
          locked[key] = lockedValues;
          excluded[key] = excludedValues;
        }
      });
      return { count: 1, options, locked, excluded };
    }
    if (tool === "full") {
      return game.positions
        ? { mode: "full", selection: { positions: Array.from({ length: game.positions }, (_, index) => selectedNumbers(form, `position-${index}`)) }, options }
        : { mode: "full", selection: { main: selectedNumbers(form, "main"), special: selectedNumbers(form, "special") }, options };
    }
    if (tool === "dantuo") {
      if (game.positions) return { mode: form.elements.group_mode.value, digits: selectedNumbers(form, "digits"), options };
      const collect = (state) => ({ main: selectedNumbers(form, "main", state), special: selectedNumbers(form, "special", state) });
      return { mode: "dantuo", dan: collect("dan"), tuo: collect("tuo"), options };
    }
    if (tool === "reduce") {
      const entries = readBasket().games[gameKey];
      const useCurrent = form.elements.reduce_source?.value === "current";
      return {
        entries: useCurrent ? lastComputed?.entries || [] : [...form.querySelectorAll('input[name="basket_entry"]:checked')].map((input) => entries[Number(input.value)]),
        source: useCurrent ? lastComputed?.source || null : null,
        budget: Number(form.elements.budget.value),
        options,
      };
    }
    return { batch_a: form.elements.batch_a.value, batch_b: form.elements.batch_b.value, operation: form.elements.operation.value, options };
  }

  function inputDigits(value) {
    return [...new Set(String(value || "").match(/\d/g) || [])].map(Number);
  }

  function conditionalConditions(form, gameKey, source) {
    if (source === "digit_filter") {
      const positions = (prefix) => Object.fromEntries(
        [0, 1, 2]
          .map((index) => [String(index), inputDigits(form.elements[`${prefix}_${index}`]?.value)])
          .filter(([, digits]) => digits.length),
      );
      return {
        sum_min: Number(form.elements.sum_min.value),
        sum_max: Number(form.elements.sum_max.value),
        span_min: Number(form.elements.span_min.value),
        span_max: Number(form.elements.span_max.value),
        types: [...form.querySelectorAll('[name="types"]:checked')].map((input) => input.value),
        odd_counts: [...form.querySelectorAll('[name="odd_counts"]:checked')].map((input) => Number(input.value)),
        big_counts: [...form.querySelectorAll('[name="big_counts"]:checked')].map((input) => Number(input.value)),
        position_include: positions("position_include"),
        position_exclude: positions("position_exclude"),
      };
    }
    const conditions = {};
    STRATEGY_NUMBER_FIELDS.forEach((name) => {
      if (form.elements[name] && form.elements[name].value !== "") conditions[name] = Number(form.elements[name].value);
    });
    STRATEGY_TEXT_FIELDS.forEach((name) => {
      if (form.elements[name] && form.elements[name].value.trim()) conditions[name] = form.elements[name].value.trim();
    });
    return conditions;
  }

  function endpointAndBody(form, gameKey, tool) {
    if (tool === "conditional") {
      const handoff = activeHandoff && activeHandoff.game_key === gameKey ? activeHandoff : null;
      const source = handoff?.source === "strategy" ? "strategy" : (isDigitGame(gameKey) ? "digit_filter" : "strategy");
      return {
        endpoint: `/api/tools/${gameKey}/conditional`,
        body: {
          source,
          preset: form.elements.preset?.value || "balanced",
          count: Number(form.elements.count?.value || 8),
          window: Number(form.elements.window?.value || 120),
          conditions: conditionalConditions(form, gameKey, source),
          options: formOptions(form),
        },
      };
    }
    return { endpoint: `/api/tools/${gameKey}/${form.dataset.action}`, body: serializeForm(form, gameKey, tool) };
  }

  function setStatus(message, error = false) {
    const status = document.querySelector("#toolStatus");
    status.textContent = message;
    status.classList.toggle("is-error", error);
  }

  function reductionMetadataMarkup(payload) {
    const original = Number(payload.original_ticket_count || 0);
    const ratio = Number(payload.reduction_ratio || 0);
    const zones = payload.coverage_by_zone && typeof payload.coverage_by_zone === "object" ? payload.coverage_by_zone : {};
    const zoneNames = { main: "主区", special: "特别区", position_1: "第 1 位", position_2: "第 2 位", position_3: "第 3 位", group3: "组三", group6: "组六" };
    const coverage = Object.entries(zones).map(([zone, values]) => {
      const text = Object.entries(values || {}).map(([number, count]) => `${number}×${count}`).join("、") || "无";
      return `<li><strong>${zoneNames[zone] || zone}</strong>：${text}</li>`;
    }).join("");
    return `<section class="reduction-meta"><p>原始组合：${original} 注；缩减比例：${(ratio * 100).toFixed(1)}%。</p><h3>覆盖分布</h3><ul>${coverage || "<li>暂无覆盖数据。</li>"}</ul><p class="tool-warning">仅作组合管理，不提高中奖概率。${payload.disclaimer || ""}</p></section>`;
  }

  function renderResult(payload, gameKey, tool) {
    const panel = document.querySelector("#toolResult");
    const title = panel.querySelector("#resultTitle");
    const entries = Array.isArray(payload.entries) ? payload.entries : [];
    const trimmed = payload.ticket_count > 0 && !entries.length;
    title.textContent = trimmed ? "计算完成，结果过多未展开" : entries.length ? "号码结果" : "没有可显示的号码";
    const existing = panel.querySelector(".tool-result-body");
    if (existing) existing.remove();
    panel.querySelector("#resultEmpty")?.remove();
    const body = document.createElement("div");
    body.className = "tool-result-body";
    if (trimmed) body.innerHTML = `<p class="tool-warning">共 ${payload.ticket_count} 注，数量较多，未展开全部号码。${(payload.warnings || []).join(" ")}</p>`;
    else if (entries.length) {
      const organizationDownload = tool === "organize" ? '<button id="downloadResults" type="button">下载当前 CSV</button>' : "";
      body.innerHTML = `<div class="result-actions"><button id="addAllResults" type="button">全部加入号码篮</button><button id="copyResults" type="button">复制全部</button>${organizationDownload}<button id="clearResults" type="button">清空当前结果</button></div><ol class="result-list">${entries.map((entry, index) => {
        const replace = tool === "quick" ? `<button type="button" data-replace-result="${index}">换一组</button>` : "";
        return `<li data-result-entry><span>${entry.text || entry.main.join(" ")}</span><span class="result-entry-actions"><button type="button" data-copy-result="${index}">复制</button><button type="button" data-add-result="${index}">加入</button>${replace}</span></li>`;
      }).join("")}</ol>`;
    }
    else body.innerHTML = "<p class=\"tool-empty\">本次操作没有返回号码，请调整条件后重试。</p>";
    if (tool === "reduce") body.insertAdjacentHTML("beforeend", reductionMetadataMarkup(payload));
    panel.querySelector("#costSummary").before(body);
    panel.querySelector("#costSummary").textContent = `预计金额：${payload.total_cost ?? 0} 元，共 ${payload.ticket_count ?? 0} 注`;
    panel.dataset.resultGame = gameKey;
    panel.dataset.resultTool = tool;
    panel.__entries = entries;
    panel.__payload = payload;
    panel.__basketMeta = { entry_cost: payload.entry_cost, multiplier: payload.multiplier };
    if (["full", "dantuo", "group3", "group6"].includes(tool) && (entries.length || payload.reduction_source)) {
      lastComputed = {
        gameKey,
        entries: entries.map((entry) => ({ ...entry })),
        source: payload.reduction_source || null,
        ticketCount: payload.ticket_count,
        label: tool === "full" ? "复式结果" : "组号结果",
      };
    }
  }

  async function copyText(text) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(text);
      setStatus("已复制到剪贴板。");
      return true;
    } catch (_) {
      let textarea = null;
      try {
        textarea = document.createElement("textarea");
        textarea.dataset.copyFallback = "true";
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.append(textarea);
        textarea.select();
        if (!document.execCommand("copy")) throw new Error("execCommand rejected");
        setStatus("已复制到剪贴板。");
        return true;
      } catch (_) {
        setStatus("自动复制失败，请手动复制结果文本。", true);
        return false;
      } finally {
        textarea?.remove();
      }
    }
  }

  function downloadEntriesCsv(gameKey, entries, filename = `${gameKey}-number-basket.csv`, defaultSource = "quick") {
    const blob = new Blob([formatCsv(gameKey, entries, defaultSource)], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function downloadCsv(gameKey) {
    downloadEntriesCsv(gameKey, readBasket().games[gameKey]);
  }

  async function submitTool(form) {
    const { game, tool } = urlState();
    const request = { game, tool, token: ++requestToken };
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    setStatus("正在处理本次号码请求。");
    try {
      const { endpoint, body } = endpointAndBody(form, game, tool);
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail?.message || "请求未能完成，请检查条件后重试。");
      const current = urlState();
      if (request.token !== requestToken || current.game !== request.game || current.tool !== request.tool) return;
      renderResult(payload, request.game, request.tool);
      setStatus("结果已更新，可加入号码篮。");
    } catch (error) {
      if (request.token === requestToken) setStatus(error.message || "请求未能完成，请稍后重试。", true);
    } finally {
      if (request.token === requestToken) submit.disabled = false;
    }
  }

  async function replaceQuickResult(index) {
    const { game, tool } = urlState();
    const form = document.querySelector("#toolWorkbench form");
    const panel = document.querySelector("#toolResult");
    if (!form || tool !== "quick" || panel.dataset.resultTool !== "quick") return;
    const request = { game, tool, token: ++requestToken };
    const replaceButton = panel.querySelector(`[data-replace-result="${index}"]`);
    if (replaceButton) replaceButton.disabled = true;
    try {
      const payload = { ...serializeForm(form, game, tool), count: 1 };
      const response = await fetch(`/api/tools/${game}/quick-pick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const replacement = await response.json();
      if (!response.ok || !replacement.entries?.[0]) throw new Error(replacement.detail?.message || "换一组失败，请重试。 ");
      const current = urlState();
      if (request.token !== requestToken || current.game !== request.game || current.tool !== request.tool) return;
      const entries = [...(panel.__entries || [])];
      entries[index] = replacement.entries[0];
      renderResult({ ...panel.__payload, entries, ticket_count: entries.length }, game, "quick");
      setStatus("已换一组号码。 ");
    } catch (error) {
      if (request.token === requestToken) {
        setStatus(error.message || "换一组失败，请重试。", true);
        if (replaceButton) replaceButton.disabled = false;
      }
    }
  }

  async function loadSurfaces() {
    try {
      const response = await fetch("/api/surfaces/config");
      if (!response.ok) return null;
      const payload = await response.json();
      return payload && typeof payload === "object" && payload.games ? payload : null;
    } catch (_) {
      return null;
    }
  }

  async function initialize() {
    const { game, tool } = urlState();
    const loading = document.querySelector("#toolLoading");
    const error = document.querySelector("#toolError");
    try {
      const [response, surfacePayload] = await Promise.all([fetch("/api/tools/config"), loadSurfaces()]);
      if (!response.ok) throw new Error("config unavailable");
      config = await response.json();
      surfaces = surfacePayload;
      if (surfaces?.games) publicGameKeys = Object.keys(surfaces.games);
      renderGames();
      maybeConsumeHandoff();
      activate(game, tool);
      if (!handoffRejected) setStatus("工具配置已就绪。");
    } catch (_) {
      error.hidden = false;
      maybeConsumeHandoff();
      if (!handoffRejected) setStatus("工具配置加载失败。", true);
      activate(game, tool);
    } finally {
      loading.hidden = true;
      migrateLegacyPools();
      renderBasket();
    }
  }

  window.LotteryTools = { normalizeEntry, readBasket, writeBasket, addEntriesToBasket, removeBasketEntry, clearBasket, formatCsv };
  document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", (event) => {
      const gameButton = event.target.closest("[data-game-key]");
      const toolButton = event.target.closest("[data-tool-card]");
      const state = urlState();
      if (gameButton) {
        setState(gameButton.dataset.gameKey, state.tool, { announceSwitch: gameButton.dataset.gameKey !== state.game });
        return;
      }
      if (toolButton) {
        setState(state.game, toolButton.dataset.toolCard, { focusWorkbench: true });
        return;
      }
      const number = event.target.closest("[data-number]");
      if (number) {
        if (number.hasAttribute("data-dantuo-number")) {
          const choices = ["", "dan", "tuo"];
          setNumberChoice(number, choices[(choices.indexOf(number.dataset.choice || "") + 1) % choices.length]);
        } else if (state.tool === "lock") {
          const choices = ["", "locked", "excluded"];
          setNumberChoice(number, choices[(choices.indexOf(number.dataset.choice || "") + 1) % choices.length]);
        } else setNumberChoice(number, number.dataset.choice === "selected" ? "" : "selected");
        updateLiveCost(document.querySelector("#toolWorkbench form"), state.game, state.tool);
        return;
      }
      const resultPanel = document.querySelector("#toolResult");
      const resultGame = resultPanel.dataset.resultGame;
      const add = event.target.closest("[data-add-result]");
      const addAll = event.target.closest("#addAllResults");
      if ((add || addAll) && resultGame !== state.game) {
        setStatus("当前彩种已切换，请重新生成号码后再加入号码篮。", true);
        return;
      }
      if (add) addEntriesToBasket(resultGame, [resultPanel.__entries[Number(add.dataset.addResult)]], resultPanel.dataset.resultTool, resultPanel.__basketMeta);
      if (addAll) addEntriesToBasket(resultGame, resultPanel.__entries, resultPanel.dataset.resultTool, resultPanel.__basketMeta);
      if (event.target.closest("#copyResults")) copyText((document.querySelector("#toolResult").__entries || []).map((entry) => entry.text || entry.main.join(" ")).join("\n"));
      const copyEntry = event.target.closest("[data-copy-result]");
      if (copyEntry) copyText(resultPanel.__entries[Number(copyEntry.dataset.copyResult)]?.text || "");
      const replace = event.target.closest("[data-replace-result]");
      if (replace) replaceQuickResult(Number(replace.dataset.replaceResult));
      if (event.target.closest("#clearResults")) {
        requestToken += 1;
        lastComputed = null;
        resetResult();
        updateLiveCost(document.querySelector("#toolWorkbench form"), state.game, state.tool);
        setStatus("已清空当前结果。");
      }
      const remove = event.target.closest("[data-remove-basket]");
      if (remove) removeBasketEntry(state.game, Number(remove.dataset.removeBasket));
      if (event.target.closest("#clearBasket")) clearBasket(state.game);
      if (event.target.closest("#copyBasket")) copyText(readBasket().games[state.game].map((entry) => entry.text || entry.main.join(" ")).join("\n"));
      if (event.target.closest("#downloadBasket")) downloadCsv(state.game);
      if (event.target.closest("#downloadResults")) downloadEntriesCsv(state.game, resultPanel.__entries || [], `${state.game}-organized-numbers.csv`, "organize");
    });
    document.addEventListener("input", (event) => {
      const form = event.target.closest("#toolWorkbench form");
      if (!form) return;
      const state = urlState();
      updateLiveCost(form, state.game, state.tool);
    });
    document.addEventListener("change", (event) => {
      const form = event.target.closest("#toolWorkbench form");
      if (!form) return;
      const state = urlState();
      updateLiveCost(form, state.game, state.tool);
    });
    document.addEventListener("submit", (event) => {
      const form = event.target.closest("#toolWorkbench form");
      if (!form) return;
      event.preventDefault();
      submitTool(form);
    });
    maybeConsumeHandoff();
    initialize();
  });
})();
