(() => {
  "use strict";

  const WINDOWS = [30, 60, 120];
  const GROUP_TYPES = ["豹子", "组三", "组六"];
  const POSITIONS = [
    ["0", "百位"],
    ["1", "十位"],
    ["2", "个位"],
  ];
  const SOURCE_TITLES = {
    manual: "手动选号",
    random: "随机选号",
    filter: "筛选方案",
  };
  // The plan strip used to print the API's own `source_type` / `status` values, so a user read
  // "manual · draft". These map them to the words the rest of the page uses; an unrecognized
  // value is left out of the line rather than shown raw.
  const PLAN_STATUS_TITLES = {
    draft: "草稿",
    saved: "已保存",
    pending_review: "待确认",
  };
  const FILTER_SOURCE = "filter";

  // 缩水选号 starts from the whole three-digit space (000 to 999) and reduces it with the
  // conditions the user sets. The reduced count is always the server's own `total`, never the
  // length of the list on screen: the list is capped, the total is not.
  const NUMBER_SPACE_TOTAL = 1000;
  const CANDIDATE_DISPLAY_LIMIT = 20;
  const GAME_KEY = "3d";
  // Marks the shared page shell as hosting the 3D toolbox; workbench-3d.css keys its mobile
  // compaction of .site-header / .game-tabs off this class and nothing else.
  const TOOLBOX_BODY_CLASS = "three-d-toolbox-active";
  const REDUCTION_TOOL = "reduction";
  // A reduction can never survive more of the number space than the space holds.
  const MAX_RESULT_COUNT = NUMBER_SPACE_TOTAL;
  // 号码查询 and 号码属性 answer with exactly one number's result. The count says that a
  // result came back; the digits it describes are user input and never leave the browser.
  const SINGLE_QUERY_RESULT_COUNT = 1;
  const MAX_FILTER_RESULTS = 200;
  // Mirrors the default text in analysis.html, so a cleared block restores the same idle line.
  const MANUAL_IDLE_MESSAGE = "等待输入。";
  const REDUCTION_IDLE_MESSAGE = "等待生成。";
  const REDUCTION_LOADING_MESSAGE = "生成中。";
  const REDUCTION_EMPTY_MESSAGE = "没有符合条件的候选号。";
  const REDUCTION_FAILED_MESSAGE = "生成候选暂不可用，请稍后重试。";
  const REDUCTION_REFRESH_FAILED_MESSAGE = "生成失败，已保留上次候选和已选号码。";
  const NO_FEEDBACK = Object.freeze({ message: "", isError: false, retry: false });
  const ACTIVE_PLAN_STATUSES = new Set(["draft", "saved", "pending_review"]);

  const TOOL_KEYS = new Set([
    "trend",
    "omission",
    "frequency",
    "heat",
    "number",
    "attributes",
    "reduction",
    "recent",
  ]);
  // The four statistics tools are the only ones with a window switcher (see WINDOW_TAB_TOOLS in
  // three-d-toolbox.js). Three of them read the summary; `trend` reads /api/3d/trends. No other
  // tool refetches on a window change, because no other tool can express one: 号码查询/号码属性 and
  // 缩水选号 take the window their link carried and send it with the request the user submits.
  const SUMMARY_WINDOW_TOOLS = new Set(["omission", "frequency", "heat"]);
  const TREND_TOOL = "trend";
  const STATS_TOOLS = new Set([TREND_TOOL, ...SUMMARY_WINDOW_TOOLS]);

  const TREND_COLUMNS = ["期号", "日期", "百位", "十位", "个位"];
  // Server heat labels collapse into the three layers the tool shows.
  const HEAT_LAYERS = [
    { label: "热", labels: new Set(["hot"]) },
    { label: "温", labels: new Set(["warm", "neutral"]) },
    { label: "冷", labels: new Set(["cool", "cold"]) },
  ];
  // Digits whose server label matches no known layer. They stay visible under a neutral, honest
  // name rather than vanish from the position; the bucket is rendered only when it has members.
  const UNKNOWN_HEAT_LAYER = { label: "其他", labels: new Set() };
  const HEAT_LAYER_DEFINITION =
    "热是这段时间开得多、而且最近还在开的数字；冷是开得少、又很久没开的数字；温在两者之间。";
  const STATS_DISCLAIMER = "历史统计不代表未来概率，也不代表未来开奖结果。";
  // The disclaimer every stats tool states on its own visible line, next to the window, the
  // real sample and the latest data date it was built from.
  const STATS_STATUS_DISCLAIMER = "历史统计不代表未来概率。";
  const TREND_EMPTY_MESSAGE = "暂无走势数据。";

  // 号码查询 and 号码属性 share /api/3d/number-query, a read-only historical lookup that
  // stays usable under stale data. They differ only in what the result leads with.
  const NUMBER_PATTERN = /^[0-9]{3}$/;
  const TODAY_PATTERN = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
  const INVALID_NUMBER_STATUS = 422;
  const NO_PAIR_TEXT = "无";
  const QUERY_IDLE_MESSAGE = "等待查询。";
  const QUERY_LOADING_MESSAGE = "查询中。";
  const QUERY_INVALID_MESSAGE = "请输入三位数字。";
  const QUERY_FAILED_MESSAGE = "号码查询暂不可用，请稍后重试。";
  const QUERY_REFRESH_FAILED_MESSAGE = "刷新失败，已保留上次成功结果。";
  // The server owns every attribute shown online; the frontend only labels what it returns.
  const ATTRIBUTE_FIELDS = [
    ["和值", (attrs) => text(attrs.sum)],
    ["和值尾", (attrs) => text(attrs.sum_tail)],
    ["跨度", (attrs) => text(attrs.span)],
    ["组态", (attrs) => text(attrs.group_type)],
    ["奇偶", (attrs) => text(attrs.odd_even)],
    ["大小", (attrs) => text(attrs.big_small)],
    ["012路", (attrs) => text(attrs.mod3)],
    ["质合", (attrs) => text(attrs.prime_composite)],
    ["相邻", (attrs) => adjacentPairText(attrs.adjacent_pairs)],
    ["连号", (attrs) => consecutivePairText(attrs.consecutive_pairs)],
  ];
  // Every tool states what it computes, in two parts. `summary` is what the reader must see
  // before touching anything — what the tool counts and the disclaimer — and it renders
  // visibly, with no click. `body` is the mechanics behind the 说明 disclosure: useful, but
  // not a wall of text between the reader and the data.
  // These two tools are not window-driven statistics, so their text is fixed; the window and
  // sample of a given result stay payload-sourced and are stated on the result (queryMetaLine).
  const QUERY_TOOL_DEFINITIONS = {
    number: {
      summary: `查你输入的三位号码在过去开出过多少次；统计了多少期，以查询结果上标注的为准。${STATS_DISCLAIMER}`,
      body:
        "直选是三位数字和顺序都一样，组选是三个数字相同、不看顺序。" +
        "位置遗漏是这个数字在这一位上已经连续多少期没有开出。",
    },
    attributes: {
      summary:
        "号码属性只按你输入的三位数字算出来，不依赖历史开奖，不代表未来概率，也不代表未来开奖结果。",
      body:
        "和值是三个数字相加，跨度是最大数字减最小数字，" +
        "组态看三个数字重复了几个（豹子、组三、组六），奇偶、大小、012路、质合是三个数字各自的个数比；" +
        "相邻看百位与十位、十位与个位上的数字是否只差1，连号看号码里有没有连着的数字。",
    },
  };
  const QUERY_TOOLS = {
    number: {
      form: "#threeDNumberQueryForm",
      input: "#threeDNumberQueryInput",
      feedback: "#threeDNumberQueryFeedback",
      result: "#threeDNumberQueryResult",
      render: (result, payload) => renderNumberFacts(result, payload),
    },
    attributes: {
      form: "#threeDAttributesForm",
      input: "#threeDAttributesInput",
      feedback: "#threeDAttributesFeedback",
      result: "#threeDAttributesResult",
      render: (result, payload) => renderAttributeFacts(result, payload),
    },
  };

  const state = {
    active: false,
    tool: "",
    window: 30,
    summary: null,
    trend: null,
    trendWindow: 0,
    trendGeneration: 0,
    plans: [],
    // The candidates on screen, and the conditions they really came from. `appliedConditions`
    // is written only by a successful reduction, so nothing else can claim them as its own.
    filterResult: null,
    appliedConditions: null,
    selectedCandidates: new Map(),
    filterFeedback: NO_FEEDBACK,
    filterLoading: false,
    filterGeneration: 0,
    filterController: null,
    loading: false,
    lastSuccess: null,
    error: "",
    currentPlan: null,
    pending: [],
    saveBusy: false,
    generation: 0,
    plansGeneration: 0,
    // One entry per query tool: the payload it currently displays, its load generation and
    // the in-flight request it can supersede.
    queries: {
      number: { payload: null, generation: 0, controller: null },
      attributes: { payload: null, generation: 0, controller: null },
    },
    abortController: null,
    listenersBound: false,
    trackedOpen: false,
    saveRequests: new Map(),
  };

  const els = {};

  function $(selector) {
    return document.querySelector(selector);
  }

  function cacheElements() {
    els.root = $("#threeDToolbox");
    els.oldWorkbench = $("#analysisWorkbench");
    els.freshness = $("#threeDFreshness");
    els.planStrip = $("#threeDPlanStrip");
    els.targetLabel = $("#threeDTargetLabel");
    els.manualForm = $("#threeDManualForm");
    els.manualNumber = $("#threeDManualNumber");
    els.manualSave = $("#threeDManualSave");
    els.randomSave = $("#threeDRandomSave");
    els.manualStatus = $("#threeDManualStatus");
    els.filterForm = $("#threeDFilterForm");
    els.filterResult = $("#threeDFilterResult");
    els.filterSummary = $("#threeDFilterSummary");
    els.filterSave = $("#threeDFilterSave");
    els.filterStatus = $("#threeDFilterStatus");
    els.filterFeedback = $("#threeDFilterFeedback");
    els.selectedCount = $("#threeDSelectedCount");
    els.recentDraws = $("#threeDRecentDraws");
    els.frequencyMatrix = $("#threeDFrequencyMatrix");
    els.omissionMatrix = $("#threeDOmissionMatrix");
    els.heatRanking = $("#threeDHeatRanking");
    els.trendPanel = $("#threeDTrendPanel");
    els.toolDefinition = $("#threeDToolDefinition");
    els.toolDefinitionMeta = $("#threeDToolDefinitionMeta");
    els.toolDefinitionBody = $("#threeDToolDefinitionBody");
    els.positionInputs = {
      include: POSITIONS.map(([position]) => $(`#threeDPositionInclude${position}`)),
      exclude: POSITIONS.map(([position]) => $(`#threeDPositionExclude${position}`)),
    };
  }

  function clientReady() {
    return Boolean(
      window.LotteryProduct?.request &&
        window.LotteryProduct?.listPlans &&
        window.LotteryProduct?.createPlan &&
        window.LotteryProduct?.updatePlan,
    );
  }

  function currentTarget() {
    return state.summary?.current_target || null;
  }

  function freshness() {
    return state.summary?.freshness || null;
  }

  function actions() {
    return state.summary?.actions || {};
  }

  function canSaveCurrent() {
    return Boolean(actions().can_save_current && currentTarget());
  }

  function canFilterCurrent() {
    return Boolean(actions().can_filter_current && currentTarget());
  }

  function isCurrentTargetPlan(plan) {
    const target = currentTarget();
    if (!target || !plan) return false;
    return (
      plan.game_key === "3d" &&
      plan.target_issue === target.target_issue &&
      plan.target_draw_date === target.target_draw_date &&
      ACTIVE_PLAN_STATUSES.has(plan.status)
    );
  }

  function currentTargetPlans(plans) {
    return (Array.isArray(plans) ? plans : []).filter(isCurrentTargetPlan);
  }

  function latestSummaryPlan() {
    return isCurrentTargetPlan(state.summary?.latest_plan) ? state.summary.latest_plan : null;
  }

  function uuid(label) {
    if (window.crypto?.randomUUID) return `${label}:${window.crypto.randomUUID()}`;
    if (window.crypto?.getRandomValues) {
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
      return `${label}:${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex
        .slice(6, 8)
        .join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
    }
    return `${label}:${Date.now().toString(36)}:${performance.now().toString(36)}`;
  }

  function normalizeWindow(value) {
    const number = Number(value);
    return WINDOWS.includes(number) ? number : 30;
  }

  function setHidden(node, hidden) {
    if (!node) return;
    node.hidden = hidden;
    node.setAttribute("aria-hidden", String(hidden));
  }

  // The toolbox needs the shared shell (site header + game tabs) compacted on a phone so the
  // draw status and the tools reach the first screen. The shell is shared with the prediction
  // home, the ssq analysis view and the strategy page, so the compaction is scoped to this
  // class and only exists while the 3D toolbox is the visible page content.
  function setShellScope(active) {
    document.body?.classList.toggle(TOOLBOX_BODY_CLASS, active);
  }

  // A plan carries the conditions it was really derived from, and only a reduction derives a
  // plan from conditions. A manual or random pick has none, so it must never inherit the
  // conditions a filter run happened to leave behind in the session.
  function snapshotConditions(source) {
    return source === FILTER_SOURCE ? state.appliedConditions || {} : {};
  }

  // The plan API stores a legacy snapshot mode. "pro" means the saved plan used
  // position level conditions; everything else is "simple".
  function snapshotMode(source) {
    const conditions = snapshotConditions(source);
    const hasPositionConditions =
      Object.keys(conditions.position_include || {}).length > 0 ||
      Object.keys(conditions.position_exclude || {}).length > 0;
    return hasPositionConditions ? "pro" : "simple";
  }

  function showToolPanels(tool) {
    document.querySelectorAll("[data-three-d-tool-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.threeDToolPanel !== tool;
    });
  }

  function text(value, fallback = "--") {
    const normalized = value === undefined || value === null ? "" : String(value).trim();
    return normalized || fallback;
  }

  function digitsFromText(value) {
    const raw = String(value || "").trim();
    if (raw.length !== 3 || !/^[0-9]{3}$/.test(raw)) return null;
    return raw.split("").map((digit) => Number(digit));
  }

  function digitText(numbers) {
    return Array.isArray(numbers) ? numbers.join("") : "";
  }

  function parseDigitList(value) {
    const textValue = String(value || "").trim();
    if (!textValue) return [];
    const digits = [];
    for (const part of textValue.split(/[,\s，、]+/)) {
      if (!/^[0-9]$/.test(part)) return null;
      const digit = Number(part);
      if (!digits.includes(digit)) digits.push(digit);
    }
    return digits.sort((a, b) => a - b);
  }

  function numberAttributes(numbers) {
    const uniqueCount = new Set(numbers).size;
    const sum = numbers.reduce((total, digit) => total + digit, 0);
    const sortedUnique = Array.from(new Set(numbers)).sort((a, b) => a - b);
    return {
      sum,
      sum_tail: sum % 10,
      span: Math.max(...numbers) - Math.min(...numbers),
      group_type: uniqueCount === 1 ? "豹子" : uniqueCount === 2 ? "组三" : "组六",
      repeat_count: 3 - uniqueCount,
      consecutive_pairs: sortedUnique
        .slice(0, -1)
        .map((digit, index) => [digit, sortedUnique[index + 1]])
        .filter((pair) => pair[1] - pair[0] === 1),
      adjacent_pairs: [0, 1]
        .filter((index) => Math.abs(numbers[index] - numbers[index + 1]) === 1)
        .map((index) => [index, index + 1]),
    };
  }

  function createText(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value;
    return node;
  }

  function createButton(label, className, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function createLink(label, href) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    return link;
  }

  function detailHref(id) {
    return `./result.html?id=${encodeURIComponent(String(id || ""))}`;
  }

  function requestPath(path) {
    const url = new URL(path, window.location.origin);
    const today = new URLSearchParams(window.location.search).get("today");
    if (TODAY_PATTERN.test(today || "")) url.searchParams.set("today", today);
    return `${url.pathname}${url.search}`;
  }

  function clearStatusClass(node) {
    if (!node) return;
    node.classList.remove("is-error");
  }

  function setToolStatus(node, message, isError = false) {
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("is-error", isError);
  }

  function renderFreshness() {
    if (!els.freshness) return;
    els.freshness.replaceChildren();
    els.freshness.classList.toggle("is-error", Boolean(state.error));
    const currentFreshness = freshness();
    const line = document.createElement("div");
    line.className = "three-d-status-line";
    const strong = createText("strong", "", state.error ? "数据暂不可用" : text(currentFreshness?.message, "数据加载中"));
    const latest = createText(
      "span",
      "",
      `最新 ${text(currentFreshness?.latest_issue)} / ${text(currentFreshness?.latest_date)}`,
    );
    const target = currentTarget();
    const targetText = target
      ? `本期 ${target.target_issue} / ${target.target_draw_date}`
      : "本期目标：--";
    line.append(strong, latest, createText("span", "", targetText));
    if (!canSaveCurrent()) {
      line.append(createText("span", "", "数据待更新"));
    }
    els.freshness.append(line);

    // The server's sync error is an operator diagnostic ("timeout retry exhausted"), not
    // something a player can act on. Its existence is worth stating; its text is not.
    if (currentFreshness?.sync_error) {
      els.freshness.append(
        createText("p", "three-d-tool-status is-error", "开奖数据同步异常，最新数据可能有延迟。"),
      );
    }
    if (state.error) {
      els.freshness.append(createText("p", "three-d-tool-status is-error", state.error));
    }

    const actionsWrap = document.createElement("div");
    actionsWrap.className = "three-d-status-actions";
    actionsWrap.append(
      createButton("重试", "mini-action subtle", () => loadAll({ force: true })),
      createLink("历史方案", "./result.html?game=3d"),
    );
    els.freshness.append(actionsWrap);
    if (els.targetLabel) els.targetLabel.textContent = targetText;
  }

  function renderPlanStrip() {
    if (!els.planStrip) return;
    els.planStrip.replaceChildren();
    const activeCount = state.plans.length || Number(state.summary?.active_plan_count || 0);
    const latestPlan = state.currentPlan || latestSummaryPlan() || state.plans[0] || null;
    const line = document.createElement("div");
    line.className = "three-d-plan-line";
    line.append(createText("strong", "", activeCount ? `${activeCount}个本期方案` : "暂无本期方案"));
    if (latestPlan?.id) {
      const planLabels = [
        SOURCE_TITLES[latestPlan.source_type],
        PLAN_STATUS_TITLES[latestPlan.status],
      ].filter(Boolean);
      if (planLabels.length) line.append(createText("span", "", planLabels.join(" · ")));
      line.append(createText("span", "", `${text(latestPlan.target_issue)} / ${text(latestPlan.target_draw_date)}`));
    } else {
      line.append(createText("span", "", "从首页起盘或直接新建方案"));
    }
    els.planStrip.append(line);

    const actionsWrap = document.createElement("div");
    actionsWrap.className = "three-d-plan-actions";
    if (latestPlan?.id) {
      const edit = createButton("继续编辑", "mini-action subtle", () => {
        if (els.manualNumber && latestPlan.entries?.[0]?.main_numbers) {
          els.manualNumber.value = digitText(latestPlan.entries[0].main_numbers);
          els.manualNumber.focus();
        }
      });
      const detail = createLink("查看详情", detailHref(latestPlan.id));
      detail.id = "threeDPlanDetailLink";
      actionsWrap.append(edit, detail);
    }
    actionsWrap.append(createLink("历史方案", "./result.html?game=3d"));
    els.planStrip.append(actionsWrap);

    state.pending = window.LotteryProduct?.pendingPlans?.() || [];
    if (state.pending.length) {
      const pendingWrap = document.createElement("div");
      pendingWrap.className = "three-d-pending-list";
      pendingWrap.append(createText("strong", "", "待同步"));
      state.pending.slice(0, 4).forEach((item) => {
        const label = item.status === "blocked" || item.blocked === true ? "受阻" : "待同步";
        const source = SOURCE_TITLES[item.source_type] || "";
        pendingWrap.append(createText("span", "", `${label} ${source} ${text(item.target_issue, "")}`.trim()));
      });
      els.planStrip.append(pendingWrap);
    }
  }

  // A disabled save with the reason two sections away is a reason nobody connects to the
  // dead button. The manual save states its own block, next to the button it blocks.
  function manualBlockedMessage() {
    const currentFreshness = freshness() || {};
    return `数据待更新（最新数据 ${text(currentFreshness.latest_issue)} / ${text(
      currentFreshness.latest_date,
    )}），暂不能保存本期方案。`;
  }

  function renderManualStatus() {
    if (!els.manualStatus) return;
    if (!canSaveCurrent()) {
      setToolStatus(els.manualStatus, manualBlockedMessage(), true);
      els.manualStatus.dataset.blocked = "true";
      return;
    }
    // Only a status this function wrote may be cleared by it: a save result must survive.
    if (els.manualStatus.dataset.blocked === "true") {
      delete els.manualStatus.dataset.blocked;
      setToolStatus(els.manualStatus, MANUAL_IDLE_MESSAGE, false);
    }
  }

  function setActionAvailability() {
    const saveDisabled = !canSaveCurrent() || state.saveBusy;
    const filterDisabled = !canFilterCurrent();
    if (els.manualSave) els.manualSave.disabled = saveDisabled;
    if (els.randomSave) els.randomSave.disabled = saveDisabled;
    if (els.filterSave) els.filterSave.disabled = saveDisabled || state.selectedCandidates.size === 0;
    if (els.filterForm) {
      const submit = els.filterForm.querySelector("button[type='submit']");
      if (submit) submit.disabled = filterDisabled;
    }
  }

  function renderRecentDraws() {
    if (!els.recentDraws) return;
    els.recentDraws.replaceChildren();
    const draws = Array.isArray(state.summary?.recent_draws) ? state.summary.recent_draws.slice(0, 10) : [];
    draws.forEach((draw) => {
      const item = document.createElement("li");
      item.append(
        createText("span", "", `${text(draw.draw_date)} ${text(draw.issue)}`),
        createText("b", "", text(draw.number_text, digitText(draw.numbers))),
        createText("span", "", Array.isArray(draw.numbers) ? draw.numbers.join(" ") : "--"),
      );
      els.recentDraws.append(item);
    });
    if (!draws.length) {
      const item = document.createElement("li");
      item.append(createText("span", "", "暂无开奖数据"));
      els.recentDraws.append(item);
    }
  }

  // The summary describes the conditions the candidates on screen came from, not whatever is
  // currently typed into the form: a failed run leaves the previous candidates, and they were
  // not reduced by conditions that were never applied.
  function renderFilterSummary() {
    if (!els.filterSummary) return;
    const conditions = state.appliedConditions || {};
    const parts = [];
    if (Number.isInteger(conditions.sum_min) || Number.isInteger(conditions.sum_max)) {
      parts.push(`和值 ${conditions.sum_min ?? 0}-${conditions.sum_max ?? 27}`);
    }
    if (Number.isInteger(conditions.span_min) || Number.isInteger(conditions.span_max)) {
      parts.push(`跨度 ${conditions.span_min ?? 0}-${conditions.span_max ?? 9}`);
    }
    if (Array.isArray(conditions.types) && conditions.types.length) {
      parts.push(conditions.types.join(" / "));
    }
    if (Array.isArray(conditions.odd_counts) && conditions.odd_counts.length) {
      parts.push(`奇数个数 ${conditions.odd_counts.join(" / ")}`);
    }
    const positionCount =
      Object.keys(conditions.position_include || {}).length +
      Object.keys(conditions.position_exclude || {}).length;
    if (positionCount) parts.push(`位置约束 ${positionCount} 项`);
    els.filterSummary.textContent = parts.length ? parts.join(" · ") : "等待条件。";
  }

  function renderSelectedCount() {
    if (els.selectedCount) els.selectedCount.textContent = `已选 ${state.selectedCandidates.size} 组`;
    if (els.filterSave) els.filterSave.disabled = !canSaveCurrent() || state.selectedCandidates.size === 0 || state.saveBusy;
  }

  // Generating candidates claims the current issue, so it is blocked while the data is stale.
  // The block states the data date it is blocking on; the conditions stay editable.
  function reductionBlockedMessage() {
    const currentFreshness = freshness() || {};
    return `数据待更新（最新数据 ${text(currentFreshness.latest_issue)} / ${text(
      currentFreshness.latest_date,
    )}），暂不能生成本期候选。`;
  }

  // The panel shows, in this order of truth: the candidates that really came back, the block
  // that stops a stale claim, or the idle prompt. Rendering is driven entirely by state, so a
  // render triggered by anything else (a plan save, a summary refresh) cannot erase an error.
  function renderFilterPanel() {
    renderFilterResultArea();
    renderFilterFeedback();
    renderSelectedCount();
  }

  function renderFilterResultArea() {
    if (!els.filterResult) return;
    if (state.filterResult) {
      renderCandidates(state.filterResult);
      return;
    }
    if (!canFilterCurrent()) {
      setToolStatus(els.filterResult, reductionBlockedMessage(), true);
      return;
    }
    setToolStatus(els.filterResult, state.filterLoading ? REDUCTION_LOADING_MESSAGE : REDUCTION_IDLE_MESSAGE);
  }

  function renderFilterFeedback() {
    const node = els.filterFeedback;
    if (!node) return;
    // With candidates on screen the block cannot go into the result area without discarding
    // them, so it is stated here instead.
    const feedback =
      state.filterResult && !canFilterCurrent()
        ? { message: reductionBlockedMessage(), isError: true, retry: false }
        : state.filterFeedback;
    node.replaceChildren();
    node.classList.toggle("is-error", feedback.isError === true);
    setHidden(node, !feedback.message);
    if (!feedback.message) return;
    node.append(createText("span", "", feedback.message));
    if (feedback.retry === true) {
      // 重试 re-runs the conditions that failed, not whatever the form holds by the time it is
      // clicked: an edit made after the failure is a new run the user must submit themselves.
      node.append(
        createButton("重试", "mini-action subtle", () =>
          runFilter(feedback.retryConditions, { submitted: true }),
        ),
      );
    }
  }

  function candidateNumberText(candidate) {
    return text(candidate?.number_text, digitText(candidate?.numbers));
  }

  // A new candidate list is a new set: a number that is no longer a candidate is no longer
  // selected, so it can never be saved into a plan it does not belong to. It is matched
  // against every survivor the server sent, not just the page shown, so a reorder that pushes
  // a still-valid pick past the display cap does not silently unselect it.
  function retainedSelection(candidates) {
    const byNumber = new Map(
      candidates.map((candidate) => [candidateNumberText(candidate), candidate]),
    );
    const retained = new Map();
    state.selectedCandidates.forEach((_, numberText) => {
      const candidate = byNumber.get(numberText);
      if (candidate) retained.set(numberText, candidate);
    });
    return retained;
  }

  function allCandidates(payload) {
    return Array.isArray(payload?.candidates) ? payload.candidates : [];
  }

  function displayedCandidates(payload) {
    return allCandidates(payload).slice(0, CANDIDATE_DISPLAY_LIMIT);
  }

  // The scale is the honest headline of a reduction: the whole space it started from, and the
  // server's own total of what survived. The list below it is capped, so it says so.
  function renderReductionScale(total, shownCount) {
    const scale = document.createElement("p");
    scale.className = "three-d-reduction-scale";
    scale.append(
      createText("span", "", `原始范围 ${NUMBER_SPACE_TOTAL} 组`),
      createText("span", "", `筛后候选 ${Number.isFinite(total) ? total : "--"} 组`),
      createText("span", "", `显示前 ${shownCount} 组`),
    );
    return scale;
  }

  function renderCandidates(payload) {
    if (!els.filterResult) return;
    els.filterResult.replaceChildren();
    clearStatusClass(els.filterResult);
    const candidates = displayedCandidates(payload);
    els.filterResult.append(renderReductionScale(Number(payload?.total), candidates.length));
    if (!candidates.length) {
      els.filterResult.append(createText("p", "", REDUCTION_EMPTY_MESSAGE));
      return;
    }
    const list = document.createElement("ol");
    list.className = "three-d-candidate-list";
    candidates.forEach((candidate) => {
      const numberText = candidateNumberText(candidate);
      const item = document.createElement("li");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.candidateNumber = numberText;
      checkbox.checked = state.selectedCandidates.has(numberText);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selectedCandidates.set(numberText, candidate);
        else state.selectedCandidates.delete(numberText);
        renderSelectedCount();
      });
      const number = createText("b", "", numberText);
      const attrs = candidate.attributes || {};
      const meta = createText(
        "span",
        "",
        [
          `和值${text(attrs.sum)}`,
          `跨度${text(attrs.span)}`,
          text(attrs.group_type, ""),
          attrs.odd_even ? `奇偶${attrs.odd_even}` : "",
          attrs.mod3 ? `012 ${attrs.mod3}` : "",
        ]
          .filter(Boolean)
          .join(" / "),
      );
      item.append(checkbox, number, meta);
      list.append(item);
    });
    els.filterResult.append(list);
  }

  function positionLabel(index) {
    return POSITIONS[Number(index)]?.[1] || "--";
  }

  // The server sends adjacent pairs as position indexes and consecutive pairs as digits.
  function adjacentPairText(pairs) {
    return pairText(pairs, (pair) => `${positionLabel(pair[0])}-${positionLabel(pair[1])}`);
  }

  function consecutivePairText(pairs) {
    return pairText(pairs, (pair) => `${text(pair[0])}-${text(pair[1])}`);
  }

  function pairText(pairs, format) {
    const labels = (Array.isArray(pairs) ? pairs : [])
      .filter((pair) => Array.isArray(pair) && pair.length === 2)
      .map(format);
    return labels.length ? labels.join(" / ") : NO_PAIR_TEXT;
  }

  function hitCountText(label, entry) {
    return `${label} ${text(entry?.count, "0")}`;
  }

  function latestHitText(entry) {
    const latest = entry?.latest;
    if (!latest) return "最近命中 --";
    return `最近命中 ${text(latest.issue)} / ${text(latest.draw_date)} / ${text(latest.number_text)}`;
  }

  function attributeSummaryText(attrs) {
    return ATTRIBUTE_FIELDS.slice(0, 4)
      .map(([label, format]) => `${label} ${format(attrs || {})}`)
      .join(" · ");
  }

  // Every fact comes from the rendered payload, never from the input or from `state`: a
  // result must never be labelled with data it did not come from. The window is what was
  // asked of history; the sample is how many draws that window really held, and the
  // omissions above were computed from exactly that sample.
  // `lead` names the figures the tool above the line really shows, so the window and the sample
  // are never attached to a reading the user cannot see (号码属性 lists no positional omissions).
  function queryMetaLine(payload, lead) {
    const payloadFreshness = payload?.freshness || {};
    return [
      `${lead}近${text(payload?.position_stats_window)}期，实际取到${text(
        payload?.position_stats_sample_size,
      )}期`,
      `最新数据 ${text(payloadFreshness.latest_issue)} / ${text(payloadFreshness.latest_date)}`,
      STATS_STATUS_DISCLAIMER,
    ].join(" · ");
  }

  // A fact is one text node so it reads as one line, and so API text can never become markup.
  function factList(facts) {
    const list = document.createElement("ul");
    list.className = "three-d-fact-list";
    facts.forEach((fact) => list.append(createText("li", "", fact)));
    return list;
  }

  function omissionFacts(payload) {
    const positionDigits = payload?.position_digits || {};
    return POSITIONS.filter(([position]) => positionDigits[position]).map(([position, label]) => {
      const cell = positionDigits[position];
      return `${label} 当前遗漏 ${text(cell.current_omission)} / 平均 ${text(cell.average_omission)} / 最大 ${text(cell.max_omission)}`;
    });
  }

  // 号码查询 leads with the historical hits and the positional omissions.
  function renderNumberFacts(result, payload) {
    const history = payload?.history || {};
    result.append(
      createText("p", "three-d-fact-lead", `号码 ${text(payload?.number_text)}`),
      factList([
        hitCountText("直选次数", history.exact),
        latestHitText(history.exact),
        hitCountText("组选次数", history.group),
        latestHitText(history.group),
      ]),
    );
    const omissions = omissionFacts(payload);
    if (omissions.length) result.append(factList(omissions));
    result.append(
      createText("p", "three-d-fact-note", `号码属性：${attributeSummaryText(payload?.attributes)}`),
      createText("p", "three-d-fact-meta", queryMetaLine(payload, "位置遗漏统计")),
    );
  }

  // 号码属性 leads with the server's attributes; the same historical hits stay secondary.
  function renderAttributeFacts(result, payload) {
    const attrs = payload?.attributes || {};
    const history = payload?.history || {};
    result.append(
      createText("p", "three-d-fact-lead", `号码 ${text(payload?.number_text)}`),
      factList(ATTRIBUTE_FIELDS.map(([label, format]) => `${label} ${format(attrs)}`)),
      createText(
        "p",
        "three-d-fact-note",
        `历史命中：${hitCountText("直选次数", history.exact)} · ${hitCountText("组选次数", history.group)} · ${latestHitText(history.exact)}`,
      ),
      createText("p", "three-d-fact-meta", queryMetaLine(payload, "历史命中统计")),
    );
  }

  function queryNodes(tool) {
    const config = QUERY_TOOLS[tool];
    if (!config) return null;
    return {
      config,
      input: $(config.input),
      feedback: $(config.feedback),
      result: $(config.result),
    };
  }

  function renderQueryResult(tool, payload) {
    const nodes = queryNodes(tool);
    if (!nodes?.result) return;
    nodes.result.replaceChildren();
    clearStatusClass(nodes.result);
    nodes.config.render(nodes.result, payload);
  }

  function renderQueryFeedback(tool, message, options = {}) {
    const nodes = queryNodes(tool);
    if (!nodes?.feedback) return;
    nodes.feedback.replaceChildren();
    nodes.feedback.classList.toggle("is-error", options.isError === true);
    nodes.feedback.hidden = !message;
    if (!message) return;
    nodes.feedback.append(createText("span", "", message));
    if (options.retry === true) {
      nodes.feedback.append(createButton("重试", "mini-action subtle", () => runQuery(tool)));
    }
  }

  // Any input change invalidates the displayed result: it belongs to another number, so it
  // must not stay on screen, be reused, or survive as saveable state.
  function discardQueryResult(tool) {
    const queryState = state.queries[tool];
    const nodes = queryNodes(tool);
    if (!queryState || !nodes) return;
    queryState.generation += 1;
    queryState.controller?.abort();
    queryState.controller = null;
    queryState.payload = null;
    if (nodes.result) {
      nodes.result.replaceChildren();
      clearStatusClass(nodes.result);
      nodes.result.textContent = QUERY_IDLE_MESSAGE;
    }
    renderQueryFeedback(tool, "");
  }

  function handleQueryInput(tool) {
    const queryState = state.queries[tool];
    const nodes = queryNodes(tool);
    if (!queryState || !nodes?.input) return;
    const numberText = String(nodes.input.value || "").trim();
    if (queryState.payload && text(queryState.payload.number_text, "") === numberText) return;
    discardQueryResult(tool);
  }

  function renderPositionStats() {
    const stats = state.summary?.position_stats;
    renderFrequencyMatrix(stats);
    renderOmissionMatrix(stats);
    renderHeatLayers(stats);
  }

  // The stats source a tool describes: trend reads /api/3d/trends, the matrices read
  // the summary's position stats.
  function statsSource(tool) {
    if (tool === TREND_TOOL) return state.trend;
    return state.summary?.position_stats || null;
  }

  // The window a payload was built from, never the window the user last asked for: a failed
  // refresh keeps the previous payload, and labelling those rows with the requested window
  // would tell the user the data came from a window it never came from.
  function statsMetaLine(source) {
    return [
      `近${text(source?.window)}期，实际取到${text(source?.sample_size)}期`,
      `最新数据 ${text(source?.latest_issue)} / ${text(source?.latest_date)}`,
    ].join(" · ");
  }

  // The rendered payload is current only when it really came back for the window on screen.
  function statsSourceIsCurrent(source) {
    return Boolean(source) && Number(source.window) === state.window;
  }

  // The summary renders visibly; the body is one click away behind 说明. An empty summary
  // means the tool has nothing it can state truthfully yet, so the whole block stays hidden.
  function setToolDefinition(summary, body) {
    if (!els.toolDefinition || !els.toolDefinitionMeta || !els.toolDefinitionBody) return;
    els.toolDefinitionMeta.textContent = summary;
    els.toolDefinitionBody.textContent = body;
    els.toolDefinition.hidden = !summary;
    if (!summary) els.toolDefinition.open = false;
  }

  function renderToolDefinition() {
    if (!els.toolDefinition) return;
    // The query tools state a fixed definition: it makes no claim about a window, so it is
    // true before any result exists.
    const queryDefinition = QUERY_TOOL_DEFINITIONS[state.tool];
    if (queryDefinition) {
      setToolDefinition(queryDefinition.summary, queryDefinition.body);
      return;
    }
    const source = STATS_TOOLS.has(state.tool) ? statsSource(state.tool) : null;
    // Nothing loaded yet means there is no window, sample or date to state truthfully.
    if (!source) {
      setToolDefinition("", "");
      return;
    }
    // The window, the real sample, the latest data date and the disclaimer are the line the
    // reader may not have to click for; the mechanics of the statistic are.
    const meta = `${statsMetaLine(source)} · ${STATS_STATUS_DISCLAIMER}`;
    const body = [text(source?.definition, "")];
    if (state.tool === "heat") body.push(HEAT_LAYER_DEFINITION);
    setToolDefinition(meta, body.filter(Boolean).join(" "));
  }

  // A stats tool restates its window, its latest data date and the disclaimer once its data
  // is current again, which also clears an error a failed refresh wrote into the status. It
  // must not do that while the panel still shows the previous window's data: a render that is
  // not a successful load of the current window (a plan save, a summary retry) would then
  // erase the error and present stale rows as fresh.
  function renderStatsStatus() {
    if (!STATS_TOOLS.has(state.tool)) return;
    const source = statsSource(state.tool);
    if (!statsSourceIsCurrent(source)) return;
    const status = document
      .querySelector(`[data-three-d-tool-panel="${state.tool}"]`)
      ?.querySelector("[data-tool-status]");
    if (!status) return;
    status.textContent = `${statsMetaLine(source)} · ${STATS_STATUS_DISCLAIMER}`;
    status.classList.remove("is-error");
    delete status.dataset.state;
  }

  function appendCell(row, value, className = "") {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text(value);
    row.append(cell);
  }

  function appendDigitCell(row, digit, omission) {
    const cell = document.createElement("td");
    cell.className = "three-d-trend-digit";
    cell.dataset.digitCell = "";
    cell.dataset.digit = String(digit);
    const ball = document.createElement("strong");
    ball.textContent = String(digit);
    const meta = document.createElement("span");
    // A missing omission is unknown, not zero.
    meta.textContent = `遗漏 ${text(omission)}`;
    cell.append(ball, meta);
    row.append(cell);
  }

  function renderTrend() {
    // The panel is hidden for every other tool, so rebuilding its rows there is dead work.
    if (!els.trendPanel || state.tool !== TREND_TOOL) return;
    const rows = Array.isArray(state.trend?.rows) ? state.trend.rows : [];
    if (!rows.length) {
      els.trendPanel.replaceChildren(createText("p", "three-d-tool-status", TREND_EMPTY_MESSAGE));
      return;
    }
    const table = document.createElement("table");
    table.className = "three-d-table three-d-trend-table";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    TREND_COLUMNS.forEach((column) => headRow.append(createText("th", "", column)));
    head.append(headRow);
    const body = document.createElement("tbody");
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      appendCell(tr, row.issue);
      appendCell(tr, row.draw_date);
      const numbers = Array.isArray(row.numbers) ? row.numbers.slice(0, 3) : [];
      numbers.forEach((digit, position) => {
        // `omissions[position][digit]` is the server's post-draw value: it is 0 for the digit
        // that just hit, on every row. `hit_omissions[position]` is the streak that digit
        // ended — the number a 走势图 reader is looking for.
        appendDigitCell(tr, digit, row.hit_omissions?.[String(position)]);
      });
      body.append(tr);
    });
    table.append(head, body);
    els.trendPanel.replaceChildren(table);
  }

  function renderFrequencyMatrix(stats) {
    renderMatrix(els.frequencyMatrix, stats, "frequency", (cell) => String(cell.frequency ?? 0));
  }

  function renderOmissionMatrix(stats) {
    renderMatrix(els.omissionMatrix, stats, "current_omission", (cell) => {
      const strong = document.createElement("strong");
      strong.textContent = `现${cell.current_omission ?? 0}`;
      const span = document.createElement("span");
      // `historical_percentile` is the share of this digit's past omission streaks that were no
      // longer than the current one, so it reads as "longer than X% of past waits".
      span.textContent = `均${cell.average_omission ?? 0} / 最大${cell.max_omission ?? 0} / 长于历史${cell.historical_percentile ?? 0}%`;
      return [strong, span];
    });
  }

  function renderMatrix(container, stats, valueKey, formatter) {
    if (!container) return;
    container.replaceChildren();
    const table = document.createElement("table");
    table.className = "three-d-table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    headRow.append(createText("th", "", "位置"));
    for (let digit = 0; digit <= 9; digit += 1) headRow.append(createText("th", "", String(digit)));
    thead.append(headRow);
    const tbody = document.createElement("tbody");
    POSITIONS.forEach(([position, label]) => {
      const row = document.createElement("tr");
      row.dataset.position = position;
      row.append(createText("th", "", label));
      for (let digit = 0; digit <= 9; digit += 1) {
        const cellData = stats?.positions?.[position]?.digits?.[String(digit)] || {};
        const cell = document.createElement("td");
        cell.dataset.digitCell = "";
        cell.dataset.digit = String(digit);
        const value = formatter(cellData, valueKey);
        if (Array.isArray(value)) cell.append(...value);
        else cell.textContent = value;
        row.append(cell);
      }
      tbody.append(row);
    });
    table.append(thead, tbody);
    container.append(table);
  }

  // A label the server adds later must stay visible under 其他 rather than disappear from
  // the position, which would silently show fewer than 10 digits.
  function heatLayerOf(cell) {
    const label = String(cell?.heat || "").trim();
    return HEAT_LAYERS.find((layer) => layer.labels.has(label)) || UNKNOWN_HEAT_LAYER;
  }

  function heatDigitChip(cell) {
    const chip = document.createElement("span");
    chip.className = "three-d-heat-chip";
    chip.dataset.digitCell = "";
    chip.dataset.digit = String(cell.digit ?? "");
    chip.textContent = `${text(cell.digit)} · 遗漏${text(cell.current_omission)}`;
    return chip;
  }

  function renderHeatLayers(stats) {
    if (!els.heatRanking) return;
    const list = document.createElement("ol");
    list.className = "three-d-heat-list";
    POSITIONS.forEach(([position, label]) => {
      const item = document.createElement("li");
      item.dataset.position = position;
      item.append(createText("strong", "", label));
      const digits = Object.values(stats?.positions?.[position]?.digits || {});
      [...HEAT_LAYERS, UNKNOWN_HEAT_LAYER].forEach((layer) => {
        const members = digits
          .filter((cell) => heatLayerOf(cell) === layer)
          .sort((first, second) => Number(first.digit ?? 0) - Number(second.digit ?? 0));
        // 其他 only exists to surface labels the tool does not know; with nothing to
        // surface it stays out of the layout.
        if (layer === UNKNOWN_HEAT_LAYER && !members.length) return;
        const group = document.createElement("div");
        group.className = "three-d-heat-group";
        group.dataset.heatLayer = layer.label;
        group.append(createText("b", "", layer.label));
        if (!members.length) group.append(createText("i", "three-d-heat-empty", "本窗口无"));
        else members.forEach((cell) => group.append(heatDigitChip(cell)));
        item.append(group);
      });
      list.append(item);
    });
    els.heatRanking.replaceChildren(list);
  }

  function renderAll() {
    renderFreshness();
    renderPlanStrip();
    renderRecentDraws();
    renderFilterSummary();
    renderFilterPanel();
    renderPositionStats();
    renderTrend();
    renderToolDefinition();
    renderStatsStatus();
    renderManualStatus();
    setActionAvailability();
  }

  function filtersFromForm() {
    const filters = {};
    const numberField = (id, fallback) => {
      const value = Number($(id)?.value);
      return Number.isInteger(value) ? value : fallback;
    };
    filters.sum_min = numberField("#threeDSumMin", 0);
    filters.sum_max = numberField("#threeDSumMax", 27);
    filters.span_min = numberField("#threeDSpanMin", 0);
    filters.span_max = numberField("#threeDSpanMax", 9);
    const types = Array.from(document.querySelectorAll('#threeDTypeGroup input[name="types"]:checked')).map(
      (input) => input.value,
    );
    const oddCounts = Array.from(document.querySelectorAll('#threeDOddGroup input[name="odd_counts"]:checked')).map(
      (input) => Number(input.value),
    );
    if (types.length) filters.types = GROUP_TYPES.filter((type) => types.includes(type));
    if (oddCounts.length) filters.odd_counts = oddCounts.filter((count) => Number.isInteger(count));
    const include = positionMapFromInputs("include");
    const exclude = positionMapFromInputs("exclude");
    if (Object.keys(include).length) filters.position_include = include;
    if (Object.keys(exclude).length) filters.position_exclude = exclude;
    filters.max_results = MAX_FILTER_RESULTS;
    return filters;
  }

  function positionMapFromInputs(kind) {
    const result = {};
    els.positionInputs[kind].forEach((input, index) => {
      const digits = parseDigitList(input?.value || "");
      if (digits && digits.length) result[String(index)] = digits;
    });
    return result;
  }

  // The reduction claims the current issue, so stale data blocks the request before it goes
  // out; the conditions stay editable either way. A failed run keeps the candidates and the
  // selection the user is working with and offers a retry of those very conditions, and a
  // superseded run may never write state or DOM, however late its response lands.
  // `conditions` re-runs an earlier attempt; without it the form is the source of truth.
  // `options.submitted` marks the runs the user really asked for (the form, and the retry of
  // a failed run). A background refresh re-runs the applied conditions on its own, so it must
  // not be counted as a result the user generated.
  async function runFilter(conditions, options = {}) {
    if (!window.LotteryProduct?.request) {
      state.filterFeedback = { message: REDUCTION_FAILED_MESSAGE, isError: true, retry: true };
      renderFilterPanel();
      return;
    }
    if (!canFilterCurrent()) {
      state.filterFeedback = NO_FEEDBACK;
      renderFilterPanel();
      return;
    }
    const filters = conditions || filtersFromForm();
    const generation = ++state.filterGeneration;
    state.filterController?.abort();
    const controller = new AbortController();
    state.filterController = controller;
    state.filterLoading = true;
    state.filterFeedback = state.filterResult
      ? { message: REDUCTION_LOADING_MESSAGE, isError: false, retry: false }
      : NO_FEEDBACK;
    renderFilterPanel();
    try {
      const payload = await window.LotteryProduct.request(requestPath("/api/3d/filter"), {
        method: "POST",
        body: { filters, window: state.window },
        signal: controller.signal,
      });
      if (controller.signal.aborted || generation !== state.filterGeneration || !state.active) return;
      applyFilterResult(payload, filters);
      state.filterFeedback = NO_FEEDBACK;
      if (options.submitted === true) {
        trackToolResult(REDUCTION_TOOL, reductionResultCount(payload));
      }
    } catch (error) {
      if (error?.name === "AbortError" || controller.signal.aborted) return;
      if (generation !== state.filterGeneration || !state.active) return;
      state.filterFeedback = filterErrorFeedback(error, filters);
    } finally {
      if (generation === state.filterGeneration) {
        state.filterLoading = false;
        state.filterController = null;
        if (state.active) renderFilterPanel();
      }
    }
  }

  function filterErrorFeedback(error, conditions) {
    if (error?.status === 409) {
      return { message: reductionBlockedMessage(), isError: true, retry: false };
    }
    const message = state.filterResult ? REDUCTION_REFRESH_FAILED_MESSAGE : REDUCTION_FAILED_MESSAGE;
    return { message, isError: true, retry: true, retryConditions: conditions };
  }

  // The conditions that produced these candidates become the ones a saved plan may claim.
  // Changed conditions therefore make a different plan, and `requestIdForCreate` already keys
  // the retained request id on the payload those conditions produce: the next save mints a new
  // id on its own, so nothing has to be evicted here.
  function applyFilterResult(payload, filters) {
    state.filterResult = payload;
    state.appliedConditions = filters;
    state.selectedCandidates = retainedSelection(allCandidates(payload));
    renderFilterSummary();
  }

  // The lookup is read-only history, so it never checks freshness: stale data still answers.
  // A failed refresh keeps the last successful result on screen and offers a retry, and a
  // superseded request may never write the DOM.
  async function runQuery(tool) {
    const queryState = state.queries[tool];
    const nodes = queryNodes(tool);
    if (!queryState || !nodes?.input) return;
    // Without the client there is nothing to query: say so rather than leave a dead button.
    if (!window.LotteryProduct?.request) {
      renderQueryFeedback(tool, QUERY_FAILED_MESSAGE, { isError: true, retry: true });
      return;
    }
    const numberText = String(nodes.input.value || "").trim();
    if (!NUMBER_PATTERN.test(numberText)) {
      renderQueryFeedback(tool, QUERY_INVALID_MESSAGE, { isError: true });
      return;
    }
    const generation = ++queryState.generation;
    queryState.controller?.abort();
    const controller = new AbortController();
    queryState.controller = controller;
    renderQueryFeedback(tool, QUERY_LOADING_MESSAGE);
    try {
      const payload = await window.LotteryProduct.request(requestPath("/api/3d/number-query"), {
        method: "POST",
        body: { number: numberText, window: state.window },
        signal: controller.signal,
      });
      if (controller.signal.aborted || generation !== queryState.generation || !state.active) return;
      queryState.payload = payload;
      renderQueryResult(tool, payload);
      renderQueryFeedback(tool, "");
      // runQuery only ever runs from a submit or from the retry of a failed submit, and only a
      // response that survived the checks above gets here. Re-rendering the payload already on
      // screen (a failed refresh below) goes through renderQueryResult, which records nothing.
      trackToolResult(tool, SINGLE_QUERY_RESULT_COUNT);
    } catch (error) {
      if (error?.name === "AbortError" || controller.signal.aborted) return;
      if (generation !== queryState.generation || !state.active) return;
      if (error?.status === INVALID_NUMBER_STATUS) {
        renderQueryFeedback(tool, QUERY_INVALID_MESSAGE, { isError: true });
        return;
      }
      if (queryState.payload) {
        renderQueryResult(tool, queryState.payload);
        renderQueryFeedback(tool, QUERY_REFRESH_FAILED_MESSAGE, { isError: true, retry: true });
        return;
      }
      renderQueryFeedback(tool, QUERY_FAILED_MESSAGE, { isError: true, retry: true });
    } finally {
      if (queryState.controller === controller) queryState.controller = null;
    }
  }

  function conditionSnapshot(source, metrics = {}) {
    const currentFreshness = freshness() || {};
    return {
      mode: snapshotMode(source),
      analysis_window: state.window,
      conditions: snapshotConditions(source),
      metrics,
      latest_data_issue: text(currentFreshness.latest_issue, ""),
      latest_data_date: text(currentFreshness.latest_date, ""),
    };
  }

  function entriesFromNumbers(rows) {
    return rows.map((numbers, index) => ({
      position: index,
      main_numbers: numbers.slice(0, 3),
      special_numbers: [],
      note: "",
    }));
  }

  function editablePlanFor(source) {
    const target = currentTarget();
    if (!target) return null;
    return (state.plans || []).find((plan) => {
      return (
        plan &&
        plan.id &&
        plan.source_type === source &&
        plan.target_issue === target.target_issue &&
        plan.target_draw_date === target.target_draw_date &&
        ["draft", "saved"].includes(plan.status)
      );
    }) || null;
  }

  function stableJson(value) {
    if (Array.isArray(value)) return `[${value.map((item) => stableJson(item)).join(",")}]`;
    if (value && typeof value === "object") {
      return `{${Object.keys(value)
        .sort()
        .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
        .join(",")}}`;
    }
    return JSON.stringify(value);
  }

  function requestIdForCreate(source, payload) {
    const signature = stableJson(payload);
    const existing = state.saveRequests.get(source);
    if (existing?.signature === signature && existing.requestId) return existing.requestId;
    const requestId = uuid(source);
    state.saveRequests.set(source, { signature, requestId });
    return requestId;
  }

  function clearSaveRequest(source, requestId) {
    const existing = state.saveRequests.get(source);
    if (existing?.requestId === requestId) state.saveRequests.delete(source);
  }

  async function savePlan(source, rows, metrics, candidateCount, statusNode) {
    if (!canSaveCurrent()) {
      setToolStatus(statusNode, "数据待更新，暂不能保存本期方案。", true);
      return;
    }
    if (state.saveBusy) return;
    const target = currentTarget();
    const entries = entriesFromNumbers(rows);
    const snapshot = conditionSnapshot(source, metrics);
    state.saveBusy = true;
    setActionAvailability();
    setToolStatus(statusNode, "保存中。");
    const editable = editablePlanFor(source);
    try {
      let response;
      if (editable) {
        response = await window.LotteryProduct.updatePlan(editable.id, {
          title: SOURCE_TITLES[source],
          status: "draft",
          entries,
          condition_snapshot: snapshot,
        });
      } else {
        const createPayload = {
          game_key: "3d",
          target_issue: target.target_issue,
          target_draw_date: target.target_draw_date,
          source_type: source,
          title: SOURCE_TITLES[source],
          entries,
          condition_snapshot: snapshot,
        };
        const requestId = requestIdForCreate(source, createPayload);
        response = await window.LotteryProduct.createPlan({
          ...createPayload,
          request_id: requestId,
        });
        clearSaveRequest(source, requestId);
      }
      const plan = response?.plan || response || {};
      state.currentPlan = plan.id ? plan : { id: editable?.id };
      setToolStatus(statusNode, "已保存。");
      await refreshPlansAndSummary();
      state.saveBusy = false;
      setActionAvailability();
      exposeDetailLink(plan.id || editable?.id);
      trackPlanEdited(source, entries.length, candidateCount);
    } catch (error) {
      if (error?.pending) {
        setToolStatus(statusNode, error.message || "待同步，网络恢复后会再次保存。");
      } else if (error?.status === 409) {
        setToolStatus(statusNode, "本期状态已变化，请刷新后重试。", true);
      } else if (error?.network) {
        setToolStatus(statusNode, "网络受阻，请稍后重试。", true);
      } else {
        setToolStatus(statusNode, "保存暂不可用，请稍后重试。", true);
      }
      renderPlanStrip();
    } finally {
      state.saveBusy = false;
      setActionAvailability();
    }
  }

  function exposeDetailLink(id) {
    if (!id || !els.planStrip) return;
    let link = $("#threeDPlanDetailLink");
    if (!link) {
      link = createLink("查看详情", detailHref(id));
      link.id = "threeDPlanDetailLink";
      link.hidden = true;
      els.planStrip.append(link);
    }
    link.href = detailHref(id);
    link.hidden = false;
  }

  // Recorded only where a request the user actively submitted really came back valid. Every
  // other path returns before this call: an aborted or superseded response, a failed request,
  // a background refresh, and every render path (renderAll and friends never call it), so a
  // re-render or a result that is merely still on screen can never record a second event.
  // The payload stays aggregate-safe: the game, the tool key, and how many results came back.
  function trackToolResult(toolKey, resultCount) {
    if (!TOOL_KEYS.has(toolKey)) return;
    const count = Number(resultCount);
    if (!Number.isFinite(count)) return;
    window.LotteryProduct?.track?.("tool_result_generated", {
      game_key: GAME_KEY,
      tool_key: toolKey,
      result_count: Math.min(Math.max(Math.trunc(count), 0), MAX_RESULT_COUNT),
    })?.catch?.(() => {});
  }

  // The server's own total of what survived the reduction, never the capped list on screen.
  function reductionResultCount(payload) {
    const total = Number(payload?.total);
    return Number.isFinite(total) ? total : allCandidates(payload).length;
  }

  function trackPlanEdited(source, entryCount, candidateCount) {
    const properties = {
      game_key: "3d",
      source_type: source,
      mode: snapshotMode(source),
      window: state.window,
      entry_count: entryCount,
      candidate_count: candidateCount,
    };
    const freshnessStatus = String(freshness()?.status || "").trim();
    if (["fresh", "attention", "stale", "empty"].includes(freshnessStatus)) {
      properties.freshness_status = freshnessStatus;
    }
    window.LotteryProduct?.track?.("plan_edited", properties)?.catch?.(() => {});
  }

  async function saveManual(source = "manual") {
    const numbers = digitsFromText(els.manualNumber?.value);
    if (!numbers) {
      setToolStatus(els.manualStatus, "请输入三位数字。", true);
      return;
    }
    await savePlan(source, [numbers], minimalMetrics(numbers), 1, els.manualStatus);
  }

  function minimalMetrics(numbers) {
    const attrs = numberAttributes(numbers);
    return {
      sum: attrs.sum,
      sum_tail: attrs.sum_tail,
      span: attrs.span,
      group_type: attrs.group_type,
      repeat_count: attrs.repeat_count,
    };
  }

  function randomDigits() {
    const bytes = new Uint8Array(3);
    if (window.crypto?.getRandomValues) {
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes, (byte) => byte % 10);
    }
    const seed = Date.now() + Math.floor(performance.now());
    return [seed % 10, Math.floor(seed / 10) % 10, Math.floor(seed / 100) % 10];
  }

  async function saveRandom() {
    const numbers = randomDigits();
    if (els.manualNumber) els.manualNumber.value = digitText(numbers);
    await savePlan("random", [numbers], minimalMetrics(numbers), 1, els.manualStatus);
  }

  async function saveFilter() {
    const candidates = Array.from(state.selectedCandidates.values());
    if (!candidates.length) {
      setToolStatus(els.filterStatus, "请先选择候选号码。", true);
      return;
    }
    await savePlan(
      FILTER_SOURCE,
      candidates.map((candidate) => candidate.numbers || digitsFromText(candidate.number_text)).filter(Boolean),
      compactObject(candidateMetrics(candidates[0])),
      candidates.length,
      els.filterStatus,
    );
  }

  // The metrics describe the first selected candidate, exactly as the server reported it.
  function candidateMetrics(candidate) {
    const attrs = candidate?.attributes || {};
    return {
      sum: attrs.sum,
      sum_tail: attrs.sum_tail,
      span: attrs.span,
      repeat_count: attrs.repeat_count,
      group_type: attrs.group_type,
      odd_even: attrs.odd_even,
      big_small: attrs.big_small,
      mod3: attrs.mod3,
      prime_composite: attrs.prime_composite,
      consecutive_pairs: attrs.consecutive_pairs,
      adjacent_pairs: attrs.adjacent_pairs,
    };
  }

  function compactObject(value) {
    const result = {};
    Object.entries(value || {}).forEach(([key, item]) => {
      if (item !== undefined && item !== null && item !== "") result[key] = item;
    });
    return result;
  }

  async function refreshPlansAndSummary() {
    await loadSummary({ silent: true });
    await loadPlans();
    renderAll();
  }

  async function loadPlans() {
    const generation = ++state.plansGeneration;
    let payload;
    try {
      payload = await window.LotteryProduct.listPlans();
    } catch (error) {
      if (generation === state.plansGeneration && state.active) {
        state.plans = [];
        if (!isCurrentTargetPlan(state.currentPlan)) state.currentPlan = latestSummaryPlan();
      }
      return;
    }
    if (generation !== state.plansGeneration || !state.active) return;
    state.plans = currentTargetPlans(payload?.plans);
    if (state.currentPlan?.id) {
      const hydrated = state.plans.find((plan) => plan.id === state.currentPlan.id);
      if (hydrated) state.currentPlan = hydrated;
      else if (!isCurrentTargetPlan(state.currentPlan)) state.currentPlan = null;
    } else {
      state.currentPlan = latestSummaryPlan() || state.plans[0] || null;
    }
  }

  async function loadSummary(options = {}) {
    if (state.abortController) state.abortController.abort();
    const generation = ++state.generation;
    const controller = new AbortController();
    state.abortController = controller;
    // The toolbox aborts a superseded tool load through its own signal; forward it
    // so the in-flight fetch stops and never writes state or DOM.
    const external = options.signal;
    const abortFromExternal = () => controller.abort();
    if (external) {
      if (external.aborted) controller.abort();
      else external.addEventListener("abort", abortFromExternal, { once: true });
    }
    state.loading = true;
    state.error = "";
    if (!options.silent) renderFreshness();
    try {
      const payload = await window.LotteryProduct.request(requestPath(`/api/workbench/3d/summary?window=${state.window}`), {
        signal: controller.signal,
      });
      // A response can still land after the load was superseded; it must not become state.
      if (controller.signal.aborted || external?.aborted) return false;
      if (generation !== state.generation || !state.active) return;
      state.summary = payload;
      state.lastSuccess = payload;
      state.error = "";
      return true;
    } catch (error) {
      if (error?.name === "AbortError") return false;
      if (generation !== state.generation || !state.active) return;
      state.error = state.lastSuccess ? "刷新失败，已保留上次成功数据。" : "数据加载失败，请稍后重试。";
      if (state.lastSuccess) state.summary = state.lastSuccess;
      else state.summary = null;
      return false;
    } finally {
      external?.removeEventListener("abort", abortFromExternal);
      if (generation === state.generation) {
        state.loading = false;
        state.abortController = null;
      }
    }
  }

  // The trend tool is history only: it reads /api/3d/trends and stays usable under stale
  // data. A refetch never clears the last successful rows, so a failed refresh keeps the
  // table the user was reading while the panel reports the error and offers retry.
  async function loadTrend(options = {}) {
    if (!window.LotteryProduct?.request) return false;
    const windowSize = state.window;
    if (state.trend && state.trendWindow === windowSize) return true;
    const generation = ++state.trendGeneration;
    try {
      const payload = await window.LotteryProduct.request(requestPath(`/api/3d/trends?window=${windowSize}`), {
        signal: options.signal,
      });
      // A superseded load may not write state or DOM, however late its response lands.
      if (options.signal?.aborted || generation !== state.trendGeneration || !state.active) return false;
      state.trend = payload;
      state.trendWindow = windowSize;
      return true;
    } catch (error) {
      if (error?.name === "AbortError" || options.signal?.aborted) return false;
      if (generation !== state.trendGeneration || !state.active) return false;
      return false;
    }
  }

  async function loadAll(options = {}) {
    if (!clientReady()) {
      state.error = "工具箱暂时无法使用，请刷新页面重试。";
      renderAll();
      return false;
    }
    if (!options.skipFlush) {
      try {
        await window.LotteryProduct.flushPendingPlans();
      } catch (error) {
        // Pending plans remain visible in the strip.
      }
    }
    const summaryLoaded = await loadSummary(options);
    if (options.signal?.aborted) return false;
    await loadPlans();
    if (options.signal?.aborted) return false;
    if (!state.summary && state.lastSuccess) state.summary = state.lastSuccess;
    renderAll();
    // The freshness band's 重试 lands here without going through a tool load, so nothing else
    // would take back an error the toolbox wrote over this panel's disclaimer. The statistics
    // tools restore their own status line in renderStatsStatus, and only when their data is
    // really current again — clearing theirs here would present stale rows as fresh.
    if (summaryLoaded === true && state.tool && !STATS_TOOLS.has(state.tool)) {
      window.ThreeDToolbox?.clearToolError?.(state.tool);
    }
    if (state.filterResult && canFilterCurrent()) runFilter();
    return summaryLoaded === true;
  }

  function bindListeners() {
    if (state.listenersBound) return;
    state.listenersBound = true;
    els.manualForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      saveManual("manual");
    });
    els.randomSave?.addEventListener("click", () => {
      saveRandom();
    });
    els.filterForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      runFilter(undefined, { submitted: true });
    });
    els.filterSave?.addEventListener("click", () => {
      saveFilter();
    });
    Object.entries(QUERY_TOOLS).forEach(([tool, config]) => {
      $(config.form)?.addEventListener("submit", (event) => {
        event.preventDefault();
        runQuery(tool);
      });
      $(config.input)?.addEventListener("input", () => handleQueryInput(tool));
    });
    window.addEventListener("lotteryproduct:plansync", () => {
      if (!state.active) return;
      state.pending = window.LotteryProduct?.pendingPlans?.() || [];
      loadPlans().finally(renderPlanStrip);
    });
  }

  function trackOpen() {
    if (state.trackedOpen || !window.LotteryProduct?.track) return;
    state.trackedOpen = true;
    window.LotteryProduct.track("workbench_opened", {
      game_key: "3d",
      window: state.window,
    })?.catch?.(() => {});
  }

  // The toolbox owns tool routing and the URL. renderTool only shows the panel
  // the route asks for and makes sure the summary it needs has been loaded.
  async function renderTool(tool, options = {}) {
    if (!TOOL_KEYS.has(tool)) return false;
    const nextWindow = normalizeWindow(options.window);
    const windowChanged = nextWindow !== state.window;
    const toolChanged = tool !== state.tool;
    state.window = nextWindow;
    state.tool = tool;
    showToolPanels(tool);
    // The 说明 disclosure belongs to the tool that was open: a new tool starts it closed, so
    // nobody lands on another tool's mechanics. A window switch keeps it as the reader left it.
    if (toolChanged && els.toolDefinition) els.toolDefinition.open = false;
    let loaded = true;
    // No summary yet means this is the first load of the page (a deep link): every tool
    // needs it for freshness and plans, not just the window-driven ones. Afterwards only a
    // window change on a summary-driven statistics tool refetches it.
    if (!state.summary || (SUMMARY_WINDOW_TOOLS.has(tool) && windowChanged)) {
      loaded = await loadAll({ skipFlush: options.flush !== true, signal: options.signal });
    }
    // A superseded load must leave the DOM to whichever tool is current now.
    if (options.signal?.aborted) return true;
    if (tool === TREND_TOOL) {
      const trendLoaded = await loadTrend({ signal: options.signal });
      if (options.signal?.aborted) return true;
      if (!trendLoaded) loaded = false;
    }
    renderAll();
    return loaded !== false;
  }

  // Returns the deep-link load the toolbox already started (null when the route has no
  // tool), so activation never fires a second, error-blind load of the same summary.
  function applyRoute(options = {}) {
    const route = window.ThreeDToolbox?.initializeRoute?.({
      reset: options.reset === true,
      preserveHistory: options.restoreRoute === true,
    });
    state.tool = route?.tool || "";
    state.window = normalizeWindow(route?.window);
    return route?.load || null;
  }

  async function activate(options = {}) {
    cacheElements();
    if (!els.root) return;
    if (state.active) {
      setHidden(els.root, false);
      setHidden(els.oldWorkbench, true);
      setShellScope(true);
      bindListeners();
      renderAll();
      return;
    }
    state.active = true;
    state.trackedOpen = false;
    setHidden(els.root, false);
    setHidden(els.oldWorkbench, true);
    setShellScope(true);
    bindListeners();
    const deepLinkLoad = applyRoute(options);
    renderAll();
    const opened = deepLinkLoad ? await deepLinkLoad : await loadAll();
    if (opened) trackOpen();
  }

  function deactivate() {
    state.active = false;
    state.generation += 1;
    state.plansGeneration += 1;
    state.trendGeneration += 1;
    Object.values(state.queries).forEach((queryState) => {
      queryState.generation += 1;
      queryState.controller?.abort();
      queryState.controller = null;
    });
    state.filterGeneration += 1;
    state.filterController?.abort();
    state.filterController = null;
    if (state.abortController) state.abortController.abort();
    state.abortController = null;
    cacheElements();
    setHidden(els.root, true);
    setShellScope(false);
    if (els.oldWorkbench) {
      els.oldWorkbench.hidden = false;
      els.oldWorkbench.setAttribute("aria-hidden", "false");
    }
  }

  // The toolbox owns the route: it hands the window to renderTool and re-runs a load itself,
  // so the workbench exposes no separate window setter or reload entry point.
  window.ThreeDWorkbench = Object.freeze({
    activate,
    deactivate,
    renderTool,
    getSummary: () => state.summary,
  });
})();
