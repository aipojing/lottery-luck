const FORTUNE_HISTORY_KEY = "lotteryLuck.fortuneHistory.v1";

const GAME_LABELS = {
  ssq: "双色球",
  "3d": "福彩3D",
  qlc: "七乐彩",
  kl8: "快乐8",
  dlt: "大乐透",
  pl3: "排列3",
  pl5: "排列5",
};

const STATUS_LABELS = {
  draft: "草稿",
  saved: "已保存",
  pending_review: "待复盘",
  reviewed: "已复盘",
  expired: "已过期",
};

const REVIEW_RESULT_STATUSES = new Set([
  "direct_hit",
  "any_position_hit",
  "no_hit",
  "missed",
]);

const SOURCE_LABELS = {
  fortune: "首页财运号",
  manual: "手动选号",
  filter: "工作台筛选",
  random: "随机选号",
  carried: "沿用方案",
};

const POSITION_LABELS = ["百位", "十位", "个位"];

const MODE_LABELS = {
  simple: "本期助手",
  professional: "专业模式",
};

const COMMON_VALUE_LABELS = {
  ...STATUS_LABELS,
  ...SOURCE_LABELS,
  ...MODE_LABELS,
  condition_snapshot: "条件快照",
  entries: "号码组",
  fresh: "已更新",
  stale: "待更新",
  pending: "等待中",
  current: "当前",
  historical: "历史",
  hot: "热",
  warm: "温",
  cold: "冷",
  neutral: "平",
  reviewed: "已复盘",
  saved: "已保存",
  manual: "手动选号",
  filter: "工作台筛选",
  fortune: "首页财运号",
  carried: "沿用方案",
  random: "随机选号",
  direct_hit: "直选命中",
};

const FIELD_LABELS = {
  analysis_window: "窗口期数",
  mode: "工作模式",
  conditions: "筛选条件",
  conditions_json: "筛选条件",
  metrics: "统计摘要",
  metrics_json: "统计摘要",
  data_version: "数据版本",
  version: "数据版本",
  latest_issue: "最新期号",
  latest_date: "最新开奖日",
  latest_data_issue: "最新期号",
  latest_data_date: "最新开奖日",
  sample_size: "样本期数",
  window: "窗口期数",
  sum_min: "和值下限",
  sum_max: "和值上限",
  span_min: "跨度下限",
  span_max: "跨度上限",
  types: "号码类型",
  type: "类型",
  group_type: "号码形态",
  odd_count: "奇数个数",
  even_count: "偶数个数",
  big_count: "大号个数",
  small_count: "小号个数",
  prime_count: "质数个数",
  composite_count: "合数个数",
  repeat_count: "重复个数",
  direct_hit: "是否直选命中",
  matched_positions: "命中位置",
  any_position_hits: "任意位置命中号码",
  matched_conditions: "命中条件",
  missed_conditions: "未命中条件",
  review_status: "复盘状态",
  draw_issue: "开奖期号",
  draw_date: "开奖日期",
  draw_numbers: "开奖号码",
};

const POSITION_FIELD_LABELS = {
  position_include: "包含",
  position_exclude: "排除",
};

const els = {
  status: document.querySelector("#resultStatus"),
  title: document.querySelector("#resultTitle"),
  meta: document.querySelector("#resultMeta"),
  badge: document.querySelector("#resultBadge"),
  summary: document.querySelector("#resultSummary"),
  numbers: document.querySelector("#resultNumbers"),
  snapshot: document.querySelector("#resultSnapshot"),
  fortuneSection: document.querySelector("#fortuneSection"),
  masterRitual: document.querySelector("#resultMasterRitual"),
  loop: document.querySelector("#resultLoop"),
  fortuneEye: document.querySelector("#resultFortuneEye"),
  tailMap: document.querySelector("#resultTailMap"),
  reasons: document.querySelector("#resultReasons"),
  review: document.querySelector("#resultReview"),
  feedback: document.querySelector("#resultFeedback"),
  workbenchAction: document.querySelector("#workbenchAction"),
  reviewAction: document.querySelector("#reviewAction"),
  carryForwardAction: document.querySelector("#carryForwardAction"),
  deletePlanAction: document.querySelector("#deletePlanAction"),
  posterCanvas: document.querySelector("#posterCanvas"),
  posterDownload: document.querySelector("#posterDownload"),
};

const state = {
  generation: 0,
  kind: "empty",
  record: null,
  reviewAttempted: false,
  carryPending: false,
  carryRequest: null,
  deletePending: false,
  reviewTracked: false,
  reviewTracking: null,
  observer: null,
  listenersBound: false,
};

function padNumber(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return String(value || "");
  return String(number).padStart(2, "0");
}

function textValue(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return textValue(value, "--");
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatNumbers(numbers) {
  return (Array.isArray(numbers) ? numbers : []).map(padNumber).join(" ");
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function localizedValue(value) {
  if (typeof value !== "string") return value;
  return COMMON_VALUE_LABELS[value] || value;
}

function positionLabel(index) {
  const numeric = Number(index);
  if (Number.isInteger(numeric) && numeric >= 0) {
    return POSITION_LABELS[numeric] || `第${numeric + 1}位`;
  }
  return "未知位置";
}

function friendlyFieldLabel(key, fallback = "扩展信息") {
  const raw = String(key || "");
  const normalized = raw.replace(/^conditions\./, "").replace(/^metrics\./, "");
  const positionMatch = normalized.match(/^(position_include|position_exclude)\.(\d+)$/);
  if (positionMatch) {
    return `${positionLabel(positionMatch[2])}${POSITION_FIELD_LABELS[positionMatch[1]]}`;
  }
  return FIELD_LABELS[normalized] || fallback;
}

function conditionLabel(key) {
  return friendlyFieldLabel(key, "扩展条件");
}

function formatConditionList(value) {
  const items = safeArray(value);
  if (!items.length) return "无";
  return items.map(conditionLabel).join("、");
}

function formatPositionList(value) {
  const items = safeArray(value);
  if (!items.length) return "无";
  return items.map(positionLabel).join("、");
}

function isReviewComplete(record) {
  const reviewStatus = textValue(record?.review?.review_status || record?.review?.status);
  return record?.status === "reviewed"
    || reviewStatus === "reviewed"
    || REVIEW_RESULT_STATUSES.has(reviewStatus);
}

function displayRows(value, context = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value).flatMap(([key, item]) => {
    if (POSITION_FIELD_LABELS[key] && item && typeof item === "object" && !Array.isArray(item)) {
      return Object.entries(item).map(([position, digits]) => [
        `${positionLabel(position)}${POSITION_FIELD_LABELS[key]}`,
        formatDisplayValue(digits, { asNumbers: true }),
      ]);
    }
    if (item && typeof item === "object" && !Array.isArray(item)) {
      const nested = displayRows(item, key);
      return nested.length ? nested : [[friendlyFieldLabel(key), formatDisplayValue(item)]];
    }
    return [[friendlyFieldLabel(key, context ? "扩展信息" : "扩展信息"), formatDisplayValue(item, { key })]];
  });
}

function formatDisplayValue(value, options = {}) {
  const key = options.key || "";
  if (Array.isArray(value)) {
    if (!value.length) return "无";
    if (key === "matched_conditions" || key === "missed_conditions") {
      return formatConditionList(value);
    }
    return value.map((item) => {
      if (Array.isArray(item)) return item.map((part) => localizedValue(part)).join("-");
      const mapped = localizedValue(item);
      return options.asNumbers ? padNumber(mapped) : String(mapped);
    }).join("、");
  }
  if (value && typeof value === "object") return "扩展信息";
  if (typeof value === "boolean") return value ? "是" : "否";
  return textValue(localizedValue(value), "无");
}

function readFortuneHistory() {
  try {
    const records = JSON.parse(localStorage.getItem(FORTUNE_HISTORY_KEY) || "[]");
    return Array.isArray(records) ? records : [];
  } catch (error) {
    return [];
  }
}

function legacyRecord(id) {
  const records = readFortuneHistory();
  if (id) return records.find((record) => String(record?.id) === id) || null;
  return records[0] || null;
}

function httpStatus(error) {
  return Number(error?.status || error?.http_status || error?.response?.status || 0);
}

async function loadRecord() {
  const id = new URLSearchParams(window.location.search).get("id");
  if (!id) {
    const legacy = legacyRecord("");
    return legacy ? { kind: "legacy", record: legacy } : { kind: "empty", record: null };
  }
  const product = window.LotteryProduct;
  if (!product || typeof product.getPlan !== "function") {
    throw Object.assign(new Error("LotteryProduct is unavailable"), { status: 0 });
  }
  try {
    const payload = await product.getPlan(id);
    return { kind: "plan", record: payload?.plan || payload };
  } catch (error) {
    if (httpStatus(error) === 404) {
      const legacy = legacyRecord(id);
      if (legacy) return { kind: "legacy", record: legacy };
    }
    throw error;
  }
}

function setFeedback(message, role = "status") {
  if (!els.feedback) return;
  els.feedback.textContent = message || "";
  els.feedback.hidden = !message;
  els.feedback.setAttribute("role", role);
}

function clearNode(node) {
  if (node) node.replaceChildren();
}

function disconnectReviewObserver() {
  if (state.observer) state.observer.disconnect();
  state.observer = null;
}

function resetReviewTracking() {
  disconnectReviewObserver();
  state.reviewTracked = false;
  state.reviewTracking = null;
}

function syncCarryRequest(record) {
  const sourceId = textValue(record?.id);
  if (!sourceId || state.carryRequest?.sourceId !== sourceId) {
    state.carryRequest = null;
  }
}

function carryRequestId(record) {
  const sourceId = textValue(record?.id);
  if (!sourceId) return "";
  if (state.carryRequest?.sourceId === sourceId && state.carryRequest.requestId) {
    return state.carryRequest.requestId;
  }
  const requestId = `carry:${sourceId}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
  state.carryRequest = { sourceId, requestId };
  return requestId;
}

function appendText(parent, tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  parent.append(node);
  return node;
}

function appendKeyValue(parent, label, value) {
  const item = document.createElement("div");
  item.className = "detail-kv";
  appendText(item, "span", label);
  appendText(item, "b", textValue(value, "--"));
  parent.append(item);
  return item;
}

function setLoading() {
  resetReviewTracking();
  els.status.textContent = "读取方案";
  els.title.textContent = "方案详情与复盘";
  els.meta.textContent = "正在读取保存的方案。";
  els.badge.textContent = "--";
  clearNode(els.summary);
  clearNode(els.numbers);
  clearNode(els.snapshot);
  clearNode(els.review);
  setFeedback("");
}

function renderError(error) {
  resetReviewTracking();
  syncCarryRequest(null);
  const status = httpStatus(error);
  const inaccessible = status === 401 || status === 403;
  const missing = status === 404;
  els.status.textContent = inaccessible ? "不可访问" : missing ? "不存在" : "读取失败";
  els.title.textContent = inaccessible ? "方案不可访问" : missing ? "方案不存在" : "暂时无法读取方案";
  els.meta.textContent = inaccessible
    ? "请确认当前账号或设备是否有权限查看这条方案。"
    : missing
      ? "没有找到对应方案，也没有同 ID 的旧版本地记录。"
      : "网络或服务暂时不可用，请稍后重试。";
  els.badge.textContent = status ? String(status) : "ERR";
  clearNode(els.summary);
  clearNode(els.numbers);
  clearNode(els.snapshot);
  clearNode(els.review);
  setFeedback(els.meta.textContent, "alert");
  setPlanActions(null, "error");
  setPosterVisible(false);
  if (els.fortuneSection) els.fortuneSection.hidden = true;
}

function renderEmpty() {
  resetReviewTracking();
  syncCarryRequest(null);
  els.status.textContent = "暂无记录";
  els.title.textContent = "暂无财运号详情";
  els.meta.textContent = "请先返回首页生成财运号，或去工作台保存本期方案。";
  els.badge.textContent = "--";
  clearNode(els.summary);
  clearNode(els.numbers);
  clearNode(els.snapshot);
  clearNode(els.review);
  setFeedback("暂无可展示的方案。");
  setPlanActions(null, "empty");
  setPosterVisible(false);
  if (els.fortuneSection) els.fortuneSection.hidden = true;
}

function planTitle(plan) {
  return textValue(plan?.title, `${GAME_LABELS[plan?.game_key] || "方案"}详情`);
}

function renderSummary(record, kind) {
  clearNode(els.summary);
  const game = GAME_LABELS[record?.game_key] || record?.game_label || "--";
  const source = kind === "legacy"
    ? "旧版本地记录"
    : SOURCE_LABELS[record?.source_type] || (record?.source_type ? "其他来源" : "--");
  appendKeyValue(els.summary, "彩种", game);
  appendKeyValue(els.summary, "来源", source);
  appendKeyValue(els.summary, "目标期", record?.target_issue ? `第${record.target_issue}期` : "--");
  appendKeyValue(els.summary, "开奖日期", record?.target_draw_date || record?.best_draw_date || "--");
  appendKeyValue(els.summary, "状态", kind === "legacy" ? "旧版兼容" : STATUS_LABELS[record?.status] || (record?.status ? "其他状态" : "--"));
  appendKeyValue(els.summary, "创建", formatDateTime(record?.created_at));
  appendKeyValue(els.summary, "更新", formatDateTime(record?.updated_at));
}

function entryNumbers(record) {
  if (Array.isArray(record?.entries) && record.entries.length) {
    return record.entries.map((entry, index) => ({
      position: entry.position ?? index,
      main_numbers: safeArray(entry.main_numbers),
      special_numbers: safeArray(entry.special_numbers),
      note: textValue(entry.note),
    }));
  }
  const main = safeArray(record?.main_numbers);
  const special = safeArray(record?.special_numbers);
  if (main.length || special.length) {
    return [{ position: 0, main_numbers: main, special_numbers: special, note: "" }];
  }
  if (record?.number_text) {
    return [{ position: 0, number_text: record.number_text, note: "" }];
  }
  return [];
}

function renderNumbers(record) {
  clearNode(els.numbers);
  const entries = entryNumbers(record);
  if (!entries.length) {
    appendText(els.numbers, "p", "暂无号码组。", "empty-state");
    return;
  }
  entries.forEach((entry, index) => {
    const group = document.createElement("section");
    group.className = "result-entry";
    const head = document.createElement("div");
    head.className = "result-entry-head";
    appendText(head, "strong", `第${Number(entry.position ?? index) + 1}组`);
    appendText(head, "span", entry.note || "保存号码");
    const balls = document.createElement("div");
    balls.className = "result-entry-balls";
    if (entry.number_text) {
      appendText(balls, "span", entry.number_text, "number-text");
    } else {
      safeArray(entry.main_numbers).forEach((number) => appendBall(balls, number, "ball"));
      safeArray(entry.special_numbers).forEach((number) => appendBall(balls, number, "ball special"));
      appendText(balls, "span", formatNumbers([...safeArray(entry.main_numbers), ...safeArray(entry.special_numbers)]), "entry-number-text");
    }
    group.append(head, balls);
    els.numbers.append(group);
  });
}

function appendBall(parent, number, className) {
  const ball = document.createElement("span");
  ball.className = className;
  ball.textContent = padNumber(number);
  parent.append(ball);
}

function renderSnapshot(record) {
  clearNode(els.snapshot);
  const snapshot = record?.condition_snapshot || {};
  if (!snapshot || !Object.keys(snapshot).length) {
    appendText(els.snapshot, "p", "暂无保存时的条件快照。", "empty-state");
    return;
  }
  const grid = document.createElement("div");
  grid.className = "snapshot-grid";
  appendKeyValue(grid, "窗口期数", snapshot.analysis_window ? `${snapshot.analysis_window}期` : "--");
  appendKeyValue(grid, "工作模式", localizedValue(snapshot.mode) || "--");
  appendKeyValue(grid, "数据版本", snapshot.metrics_json?.data_version || snapshot.metrics_json?.version || "--");
  appendKeyValue(grid, "最新期号", snapshot.latest_data_issue || snapshot.metrics_json?.latest_issue || "--");
  appendKeyValue(grid, "最新开奖日", snapshot.latest_data_date || "--");
  els.snapshot.append(grid);
  renderJsonBlock(els.snapshot, "筛选条件", snapshot.conditions_json || snapshot.conditions || {});
  renderJsonBlock(els.snapshot, "统计摘要", snapshot.metrics_json || snapshot.metrics || {});
}

function renderJsonBlock(parent, label, value) {
  const block = document.createElement("section");
  block.className = "snapshot-block";
  appendText(block, "h3", label);
  const rows = displayRows(value, label);
  if (!rows.length) {
    appendText(block, "p", "无", "empty-state");
  } else {
    rows.forEach(([key, item]) => appendKeyValue(block, key, item));
  }
  parent.append(block);
}

function renderReview(record) {
  clearNode(els.review);
  const review = record?.review || null;
  const reviewClass = review?.review_status || review?.status || record?.status || "pending";
  const isReviewed = isReviewComplete(record);
  els.review.className = `result-review ${reviewClass}`;
  if (!isReviewed) {
    appendText(els.review, "p", "等待开奖数据更新后复盘。", "empty-state");
    return;
  }
  const result = review.result_json || {};
  const draw = document.createElement("section");
  draw.className = "review-draw";
  appendText(draw, "h3", "开奖结果");
  appendKeyValue(draw, "期号", result.draw_issue || review.draw_issue || "--");
  appendKeyValue(draw, "开奖日期", result.draw_date || review.draw_date || "--");
  appendKeyValue(draw, "开奖号码", formatNumbers(result.draw_numbers || review.draw_numbers));
  appendKeyValue(draw, "形态", result.group_type || review.group_type || "--");
  els.review.append(draw);

  const entries = safeArray(result.entries);
  if (!entries.length) {
    appendText(els.review, "p", "暂无逐组复盘明细。", "empty-state");
  } else {
    const list = document.createElement("div");
    list.className = "review-entry-list";
    entries.forEach((entry, index) => list.append(reviewEntryNode(entry, index)));
    els.review.append(list);
  }
  const condition = document.createElement("section");
  condition.className = "review-conditions";
  appendText(condition, "h3", "条件复盘");
  appendText(
    condition,
    "p",
    `命中条件：${formatConditionList(result.matched_conditions || review.matched_conditions)} · 未命中条件：${formatConditionList(result.missed_conditions || review.missed_conditions)}`,
    "review-compact-line",
  );
  appendKeyValue(condition, "命中条件", formatConditionList(result.matched_conditions || review.matched_conditions));
  appendKeyValue(condition, "未命中条件", formatConditionList(result.missed_conditions || review.missed_conditions));
  els.review.append(condition);
  setupReviewTracking(record);
}

function reviewEntryNode(entry, index) {
  const node = document.createElement("article");
  node.className = "review-entry";
  appendText(node, "h3", `第${Number(entry.position ?? index) + 1}组 ${formatNumbers(entry.main_numbers)}`);
  appendText(
    node,
    "p",
    `直选：${entry.direct_hit ? "是" : "否"} · 命中位置：${formatPositionList(entry.matched_positions)} · 任意命中：${listText(entry.any_position_hits, true)}`,
    "review-compact-line",
  );
  appendKeyValue(node, "是否直选命中", entry.direct_hit ? "是" : "否");
  appendKeyValue(node, "命中位置", formatPositionList(entry.matched_positions));
  appendKeyValue(node, "任意位置命中号码", listText(entry.any_position_hits, true));
  appendKeyValue(node, "命中条件", formatConditionList(entry.matched_conditions));
  appendKeyValue(node, "未命中条件", formatConditionList(entry.missed_conditions));
  return node;
}

function listText(value, asNumbers = false) {
  const items = safeArray(value);
  if (!items.length) return "无";
  return items.map((item) => asNumbers ? padNumber(item) : String(item)).join("、");
}

function allowedProductSource(value) {
  const source = textValue(value);
  return ["fortune", "manual", "filter", "random", "carried"].includes(source)
    ? source
    : "";
}

function allowedReviewStatus(value) {
  const status = textValue(value);
  return ["draft", "saved", "pending_review", "reviewed", "expired"].includes(status)
    ? status
    : "";
}

function setupReviewTracking(record) {
  if (!isReviewComplete(record)) return;
  const tracking = {
    generation: state.generation,
    recordId: textValue(record?.id),
  };
  if (state.reviewTracked || !els.review || state.kind !== "plan" || !tracking.recordId) return;
  disconnectReviewObserver();
  state.reviewTracking = tracking;
  const track = () => {
    if (state.reviewTracked) return false;
    if (
      state.generation !== tracking.generation
      || state.kind !== "plan"
      || textValue(state.record?.id) !== tracking.recordId
      || state.reviewTracking?.recordId !== tracking.recordId
      || state.reviewTracking?.generation !== tracking.generation
    ) return false;
    state.reviewTracked = true;
    window.__task13ReviewTracked = true;
    const properties = {
      game_key: record?.game_key || "3d",
      review_status: "reviewed",
    };
    const sourceType = allowedProductSource(record?.source_type);
    if (sourceType) properties.source_type = sourceType;
    window.LotteryProduct?.track?.("review_viewed", properties)?.catch?.(() => {});
    return true;
  };
  if (!("IntersectionObserver" in window)) {
    track();
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      const tracked = track();
      if (tracked) {
        observer.disconnect();
        if (state.observer === observer) state.observer = null;
      }
    }
  }, { threshold: 0.2 });
  state.observer = observer;
  state.observer.observe(els.review);
}

function setPlanActions(record, kind) {
  const isPlan = kind === "plan" && record;
  if (els.workbenchAction) {
    els.workbenchAction.href = "/analysis.html?game=3d";
  }
  if (els.reviewAction) {
    els.reviewAction.type = "button";
    els.reviewAction.disabled = true;
    els.reviewAction.textContent = record?.status === "reviewed" ? "已完成复盘" : "开奖后可复盘";
  }
  if (els.carryForwardAction) {
    els.carryForwardAction.type = "button";
    els.carryForwardAction.disabled = !isPlan || state.carryPending;
    els.carryForwardAction.textContent = state.carryPending ? "沿用中" : "沿用到下一期";
  }
  if (els.deletePlanAction) {
    els.deletePlanAction.type = "button";
    els.deletePlanAction.disabled = !isPlan || state.deletePending;
    els.deletePlanAction.textContent = state.deletePending ? "删除中" : "删除方案";
  }
}

function renderRecord(kind, record) {
  resetReviewTracking();
  syncCarryRequest(record);
  state.kind = kind;
  state.record = record;
  if (!record) {
    renderEmpty();
    return;
  }
  const isLegacy = kind === "legacy";
  const status = isLegacy ? "旧版兼容" : STATUS_LABELS[record.status] || record.status || "--";
  els.status.textContent = status;
  els.title.textContent = isLegacy
    ? `${record.game_label || GAME_LABELS[record.game_key] || "旧版财运"} · ${record.mode_label || "兼容记录"}`
    : planTitle(record);
  els.meta.textContent = isLegacy
    ? `${record.input_summary || "旧版本地记录"} · ${formatDateTime(record.created_at)}`
    : `${GAME_LABELS[record.game_key] || record.game_key || "--"} · 第${record.target_issue || "--"}期 · ${record.target_draw_date || "--"}`;
  els.badge.textContent = status;
  renderSummary(record, kind);
  renderNumbers(record);
  renderSnapshot(record);
  renderReview(record);
  renderFortuneCompatibility(record, kind);
  setPlanActions(record, kind);
  setPosterVisible(isLegacy);
  if (isLegacy) drawSharePoster(record);
}

function renderResultDetail(kind, record) {
  renderRecord(kind, record);
}

function renderFortuneCompatibility(record, kind) {
  const show = kind === "legacy" || (record?.source_type === "fortune" && record?.fortune_report);
  if (!els.fortuneSection) return;
  els.fortuneSection.hidden = !show;
  if (!show) return;
  const report = record?.fortune_report || {};
  renderMasterRitual(record);
  renderClosedLoop(record);
  renderFortuneEye(report);
  renderTailMap(report);
  renderReasons(record);
}

async function maybeAutoReview(generation) {
  const record = state.record;
  if (state.kind !== "plan" || !record || state.reviewAttempted) return;
  if (record.status !== "pending_review" || isReviewComplete(record)) return;
  state.reviewAttempted = true;
  try {
    const payload = await window.LotteryProduct.reviewPlan(record.id);
    if (generation !== state.generation) return;
    const reviewed = payload?.plan || payload;
    if (reviewed?.id) renderResultDetail("plan", reviewed);
  } catch (error) {
    if (generation !== state.generation) return;
    if (httpStatus(error) === 409) {
      setFeedback("开奖后可复盘，当前仍在等待开奖数据。");
      setPlanActions(record, "plan");
      return;
    }
    setFeedback("自动复盘失败，可稍后刷新重试。", "alert");
  }
}

async function initialize() {
  bindListeners();
  resetReviewTracking();
  const generation = ++state.generation;
  state.reviewAttempted = false;
  setLoading();
  try {
    const loaded = await loadRecord();
    if (generation !== state.generation) return;
    renderResultDetail(loaded.kind, loaded.record);
    await maybeAutoReview(generation);
  } catch (error) {
    if (generation !== state.generation) return;
    renderError(error);
  }
}

function bindListeners() {
  if (state.listenersBound) return;
  state.listenersBound = true;
  els.carryForwardAction?.addEventListener("click", handleCarryForward);
  els.deletePlanAction?.addEventListener("click", handleDeletePlan);
  window.addEventListener("popstate", initialize);
}

async function handleCarryForward() {
  if (state.carryPending || state.kind !== "plan" || !state.record?.id) return;
  state.carryPending = true;
  setFeedback("正在沿用到下一期。");
  setPlanActions(state.record, "plan");
  try {
    const requestId = carryRequestId(state.record);
    const payload = await window.LotteryProduct.carryForward(state.record.id, requestId);
    const next = payload?.plan || payload;
    const newId = textValue(next?.id);
    if (!newId) throw new Error("missing carried plan id");
    const properties = {
      game_key: next?.game_key || state.record.game_key || "3d",
    };
    const sourceType = allowedProductSource(state.record.source_type);
    if (sourceType) properties.source_type = sourceType;
    const reviewStatus = allowedReviewStatus(state.record.review?.review_status || state.record.status);
    properties.review_status = reviewStatus || null;
    state.carryRequest = null;
    try {
      window.LotteryProduct?.track?.("plan_carried_forward", properties)?.catch?.(() => false);
    } catch (error) {
      // Carry-forward navigation must not depend on best-effort telemetry.
    }
    window.location.assign(`/result.html?id=${encodeURIComponent(newId)}`);
  } catch (error) {
    state.carryPending = false;
    setFeedback("沿用失败，请稍后重试。", "alert");
    setPlanActions(state.record, "plan");
  }
}

async function handleDeletePlan() {
  if (state.deletePending || state.kind !== "plan" || !state.record?.id) return;
  if (!window.confirm("确认删除这条方案？删除后不可恢复。")) return;
  state.deletePending = true;
  setFeedback("正在删除方案。");
  setPlanActions(state.record, "plan");
  try {
    await window.LotteryProduct.deletePlan(state.record.id);
    window.location.assign("/analysis.html?game=3d");
  } catch (error) {
    state.deletePending = false;
    setFeedback("删除失败，请检查网络后重试。", "alert");
    setPlanActions(state.record, "plan");
  }
}

function appendLoopItem(step) {
  const item = document.createElement("li");
  appendText(item, "strong", step.label || "合参节点");
  appendText(item, "span", step.value || "--");
  appendText(item, "small", step.detail || "");
  els.loop.append(item);
}

function tailText(tails) {
  return safeArray(tails).map(textValue).filter(Boolean).join("、");
}

function dailyFortuneSignText(record) {
  const sign = record?.daily_fortune_sign || {};
  const headline = textValue(sign.headline);
  if (headline) return headline;
  const parts = [];
  const direction = textValue(sign.direction);
  const luckyHour = textValue(sign.lucky_hour);
  const luckyTails = tailText(sign.lucky_tails);
  const avoidTails = tailText(sign.avoid_tails);
  if (direction) parts.push(`财位${direction}`);
  if (luckyHour) parts.push(`旺时${luckyHour}`);
  if (luckyTails) parts.push(`宜取 ${luckyTails} 尾`);
  if (avoidTails) parts.push(`避 ${avoidTails} 冲`);
  return parts.length ? `今日${parts.join("，")}。` : "";
}

function renderDailyFortuneSign(record) {
  const sign = record?.daily_fortune_sign || {};
  const summary = dailyFortuneSignText(record);
  const tags = safeArray(sign.tags).map(textValue).filter(Boolean).join(" · ");
  if (!summary && !tags) return false;
  appendLoopItem({
    label: "今日财签",
    value: summary || "今日财签已生成。",
    detail: tags || "用于校准当日旺时、财位和尾数取避。",
  });
  return true;
}

function renderClosedLoop(record) {
  clearNode(els.loop);
  renderDailyFortuneSign(record);
  const report = record?.fortune_report || {};
  const closedLoop = safeArray(report?.closed_loop);
  const ritualSteps = safeArray(record?.ritual_steps);
  const loop = closedLoop.length ? closedLoop : ritualSteps;
  if (!loop.length) {
    const item = document.createElement("li");
    item.textContent = "这条历史记录暂无完整闭环解释。";
    els.loop.append(item);
    return;
  }
  loop.forEach((step) => {
    if (typeof step === "string") {
      appendLoopItem({ label: "合参节点", value: step, detail: "" });
    } else {
      appendLoopItem({
        label: step?.label || step?.title || "合参节点",
        value: step?.value || step?.summary || step?.text || "--",
        detail: step?.detail || step?.explanation || "",
      });
    }
  });
}

function renderMasterRitual(record) {
  if (!els.masterRitual) return;
  clearNode(els.masterRitual);
  const master = record?.master_ritual && typeof record.master_ritual === "object" ? record.master_ritual : {};
  const steps = safeArray(master.steps);
  appendText(els.masterRitual, "strong", master.verdict || "旧记录暂无大师起盘。");
  appendText(els.masterRitual, "p", master.opening || "这条历史记录生成于旧版本，可以继续查看下方闭环解释和逐号释义。");
  if (steps.length) {
    const list = document.createElement("ol");
    list.className = "master-ritual-steps result-master-steps";
    steps.forEach((step) => {
      const item = document.createElement("li");
      appendText(item, "span", step?.label || "起盘节点");
      appendText(item, "b", step?.value || "--");
      appendText(item, "small", step?.detail || "");
      list.append(item);
    });
    els.masterRitual.append(list);
  }
  const tailMap = master.tail_map && typeof master.tail_map === "object" ? master.tail_map : {};
  const favorable = safeArray(tailMap.favorable).map(formatTailEntry).filter(Boolean);
  const avoid = safeArray(tailMap.avoid).map(formatTailEntry).filter(Boolean);
  if (favorable.length || avoid.length) {
    const tailLine = document.createElement("div");
    tailLine.className = "master-tail-map result-master-tail";
    appendText(tailLine, "span", `喜用尾数 ${favorable.join("、") || "--"}`);
    appendText(tailLine, "span", `避开尾数 ${avoid.join("、") || "--"}`);
    els.masterRitual.append(tailLine);
  }
}

function formatTailEntry(entry) {
  if (!entry || typeof entry !== "object") return "";
  const tail = entry.tail === undefined || entry.tail === null ? "" : String(entry.tail);
  const label = entry.element_label ? `${entry.element_label}尾` : "尾";
  return tail ? `${tail}${label}` : "";
}

function renderFortuneEye(report) {
  clearNode(els.fortuneEye);
  const eye = report?.fortune_eye || {};
  const card = document.createElement("div");
  card.className = "fortune-eye-card";
  appendText(card, "b", eye.number === undefined || eye.number === null ? "--" : padNumber(eye.number));
  appendText(card, "span", `${eye.role || "财眼位"} · ${eye.element_label || "--"}数`);
  appendText(card, "p", eye.reading || "财眼用于收束整组号码，让推荐不只是随机排列。");
  els.fortuneEye.append(card);
}

function renderTailMap(report) {
  clearNode(els.tailMap);
  const map = report?.tail_digit_map || {};
  appendText(els.tailMap, "p", map.summary || "暂无尾数映射。");
  safeArray(map.items).forEach((item) => {
    appendText(els.tailMap, "span", `${padNumber(item.number)} · 尾${item.digit} · ${item.element_label || ""}${item.role || ""}`);
  });
}

function renderReasons(record) {
  clearNode(els.reasons);
  const reasonPayload = record?.number_reasons || {};
  const items = [
    ...safeArray(reasonPayload.main),
    ...safeArray(reasonPayload.special),
  ];
  const avoidReasons = avoidReasonTexts(record);
  if (!items.length && !avoidReasons.length) {
    const item = document.createElement("li");
    item.textContent = "这条历史记录暂无逐号释义。";
    els.reasons.append(item);
    return;
  }
  items.forEach((reason) => {
    const item = document.createElement("li");
    appendText(item, "b", padNumber(reason.number));
    const body = document.createElement("div");
    body.className = "reason-body";
    appendText(body, "p", `${reason.position_label || reason.role || "号码"} · ${reason.element_label || "--"}数`, "reason-meta");
    appendText(body, "p", reason.text || safeArray(reason.lines).join(" ") || "财运参考。");
    item.append(body);
    els.reasons.append(item);
  });
  avoidReasons.slice(0, 6).forEach((reason) => {
    const item = document.createElement("li");
    appendText(item, "b", "避");
    const body = document.createElement("div");
    body.className = "reason-body";
    appendText(body, "p", "本期避开 · 避冲原因", "reason-meta");
    appendText(body, "p", reason);
    item.append(body);
    els.reasons.append(item);
  });
}

function avoidReasonTexts(record) {
  const directReasons = safeArray(record?.avoid_reasons).filter(Boolean);
  if (directReasons.length) return directReasons;
  return safeArray(record?.avoid_numbers)
    .map((item) => item?.reason)
    .filter(Boolean);
}

function numberText(record) {
  const entries = entryNumbers(record);
  if (entries.length) {
    const first = entries[0];
    return first.number_text || formatNumbers([...safeArray(first.main_numbers), ...safeArray(first.special_numbers)]);
  }
  return record?.number_text || "--";
}

function drawSharePoster(record) {
  const canvas = els.posterCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.fillStyle = "#050402";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(214,169,88,.42)";
  ctx.lineWidth = 2;
  ctx.strokeRect(42, 42, width - 84, height - 84);
  ctx.fillStyle = "#f6d489";
  ctx.font = "42px serif";
  ctx.fillText("数运合参", 90, 140);
  ctx.fillStyle = "#ffe9af";
  ctx.font = "64px serif";
  wrapText(ctx, numberText(record), 90, 330, width - 180, 78);
  ctx.fillStyle = "#b99a61";
  ctx.font = "24px sans-serif";
  wrapText(ctx, "仅供娱乐与数据分析参考，不构成投注建议。", 90, 575, width - 180, 38);
  if (els.posterDownload) els.posterDownload.href = canvas.toDataURL("image/png");
}

function setPosterVisible(isVisible) {
  if (els.posterCanvas) els.posterCanvas.hidden = !isVisible;
  if (els.posterDownload) {
    els.posterDownload.hidden = !isVisible;
    if (!isVisible) els.posterDownload.removeAttribute("href");
  }
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
  const chars = String(text || "").split("");
  let line = "";
  let lineY = y;
  chars.forEach((char) => {
    const testLine = line + char;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, lineY);
      line = char;
      lineY += lineHeight;
    } else {
      line = testLine;
    }
  });
  if (line) ctx.fillText(line, x, lineY);
}

initialize();
