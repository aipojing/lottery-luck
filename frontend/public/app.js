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
const FORTUNE_HISTORY_KEY = "lotteryLuck.fortuneHistory.v1";
const CLIENT_ID_KEY = "lotteryLuck.clientId.v1";
const MODE_LABELS = {
  steady: "稳财号",
  windfall: "偏财号",
  guard: "守财号",
};
const DEMO_GAME_RULES = {
  ssq: {
    main_count: 6,
    main_min: 1,
    main_max: 33,
    special_count: 1,
    special_min: 1,
    special_max: 16,
    allow_repeat: false,
    special_distinct_from_main: false,
  },
  dlt: {
    main_count: 5,
    main_min: 1,
    main_max: 35,
    special_count: 2,
    special_min: 1,
    special_max: 12,
    allow_repeat: false,
    special_distinct_from_main: false,
  },
  "3d": {
    main_count: 3,
    main_min: 0,
    main_max: 9,
    special_count: 0,
    special_min: null,
    special_max: null,
    allow_repeat: true,
    special_distinct_from_main: false,
  },
  pl3: {
    main_count: 3,
    main_min: 0,
    main_max: 9,
    special_count: 0,
    special_min: null,
    special_max: null,
    allow_repeat: true,
    special_distinct_from_main: false,
  },
  kl8: {
    main_count: 10,
    main_min: 1,
    main_max: 80,
    special_count: 0,
    special_min: null,
    special_max: null,
    allow_repeat: false,
    special_distinct_from_main: false,
  },
  qlc: {
    main_count: 7,
    main_min: 1,
    main_max: 30,
    special_count: 1,
    special_min: 1,
    special_max: 30,
    allow_repeat: false,
    special_distinct_from_main: true,
  },
  pl5: {
    main_count: 5,
    main_min: 0,
    main_max: 9,
    special_count: 0,
    special_min: null,
    special_max: null,
    allow_repeat: true,
    special_distinct_from_main: false,
  },
};
const MAIN_COUNTS = Object.fromEntries(
  Object.entries(DEMO_GAME_RULES).map(([key, rule]) => [key, rule.main_count]),
);
const DEFAULT_DAILY_FORTUNE_SIGN = {
  headline: "今日财签待起，起盘后显示今日财位、旺时和宜避尾数。",
  direction: "",
  lucky_hour: "待定",
  lucky_tails: [],
  avoid_tails: [],
  tags: ["财位待起", "旺时待起", "尾数待起"],
};
const DEFAULT_RITUAL_STEPS = [
  { key: "wealth_pattern", label: "定本命财盘", summary: "折算个人时空底盘。" },
  { key: "fortune_direction", label: "定今日财局", summary: "校准开奖日气口。" },
  { key: "fortune_eye", label: "取财眼尾数", summary: "锁定喜用尾数。" },
  { key: "avoid_clash", label: "避冲煞号", summary: "排除本期冲位。" },
  { key: "final_numbers", label: "落财运号", summary: "收束为本组号码。" },
];

const DEMO_GAMES = [
  {
    game_key: "ssq",
    game_name: "双色球",
    draw_count: 3430,
    latest_date: "2026-06-15",
    latest_issue: "2026067",
  },
  {
    game_key: "3d",
    game_name: "福彩3D",
    draw_count: 6900,
    latest_date: "2026-06-15",
    latest_issue: "2026157",
  },
  {
    game_key: "qlc",
    game_name: "七乐彩",
    draw_count: 2420,
    latest_date: "2026-06-14",
    latest_issue: "2026066",
  },
  {
    game_key: "kl8",
    game_name: "快乐8",
    draw_count: 1600,
    latest_date: "2026-06-15",
    latest_issue: "2026157",
  },
  {
    game_key: "dlt",
    game_name: "大乐透",
    draw_count: 0,
    latest_date: "--",
    latest_issue: "--",
  },
  {
    game_key: "pl3",
    game_name: "排列3",
    draw_count: 0,
    latest_date: "--",
    latest_issue: "--",
  },
  {
    game_key: "pl5",
    game_name: "排列5",
    draw_count: 0,
    latest_date: "--",
    latest_issue: "--",
  },
];

const DEMO_PREDICTIONS = {
  ssq: {
    game_key: "ssq",
    best_draw_date: "2026-06-18",
    luck_score: 89.1,
    numbers: { main: [4, 16, 19, 27, 29, 32], special: [11] },
    history_basis: {
      draw_count: 3430,
      hot_main: [4, 7, 16, 19, 21, 27, 32, 33],
      cold_main: [5, 13, 22, 30],
    },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [
      { issue: "2026067", draw_date: "2026-06-15", red_numbers: "02,07,11,18,24,31", blue_number: "09" },
      { issue: "2026066", draw_date: "2026-06-12", red_numbers: "03,08,14,19,25,30", blue_number: "04" },
    ],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  "3d": {
    game_key: "3d",
    best_draw_date: "2026-06-16",
    luck_score: 68.3,
    numbers: { main: [7, 1, 9], special: [] },
    history_basis: { draw_count: 6900, hot_main: [1, 7, 9, 3, 8], cold_main: [0, 4, 6] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [
      { issue: "2026157", draw_date: "2026-06-15", red_numbers: "6,2,9", blue_number: "" },
      { issue: "2026156", draw_date: "2026-06-14", red_numbers: "1,8,3", blue_number: "" },
    ],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  qlc: {
    game_key: "qlc",
    best_draw_date: "2026-06-17",
    luck_score: 72.18,
    numbers: { main: [2, 6, 11, 17, 21, 25, 30], special: [13] },
    history_basis: { draw_count: 2420, hot_main: [6, 11, 17, 21, 25, 30], cold_main: [1, 13, 27] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [
      { issue: "2026066", draw_date: "2026-06-14", red_numbers: "01,05,12,16,20,24,28", blue_number: "09" },
      { issue: "2026065", draw_date: "2026-06-11", red_numbers: "03,07,13,18,22,26,30", blue_number: "11" },
    ],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  kl8: {
    game_key: "kl8",
    best_draw_date: "2026-06-16",
    luck_score: 74.96,
    numbers: { main: [5, 9, 16, 22, 31, 37, 48, 55, 66, 78], special: [] },
    history_basis: { draw_count: 1600, hot_main: [9, 16, 22, 31, 48, 55, 66, 78], cold_main: [3, 14, 40, 71] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [
      { issue: "2026157", draw_date: "2026-06-15", red_numbers: "01,04,09,12,18,22,31,38,44,50,56,60,66,70,73,75,78,79,80,03", blue_number: "" },
      { issue: "2026156", draw_date: "2026-06-14", red_numbers: "02,07,13,16,21,27,33,39,41,47,52,58,63,68,71,74,76,77,79,80", blue_number: "" },
    ],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  dlt: {
    game_key: "dlt",
    best_draw_date: "2026-06-17",
    luck_score: 76.2,
    numbers: { main: [3, 9, 18, 24, 32], special: [6, 11] },
    history_basis: { draw_count: 0, hot_main: [3, 9, 18, 24, 32], cold_main: [1, 12, 28] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  pl3: {
    game_key: "pl3",
    best_draw_date: "2026-06-16",
    luck_score: 63.7,
    numbers: { main: [7, 7, 7], special: [] },
    history_basis: { draw_count: 0, hot_main: [7, 3, 8], cold_main: [0, 4, 6] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
  pl5: {
    game_key: "pl5",
    best_draw_date: "2026-06-16",
    luck_score: 66.4,
    numbers: { main: [1, 2, 8, 8, 9], special: [] },
    history_basis: { draw_count: 0, hot_main: [1, 2, 8, 9], cold_main: [0, 4, 6] },
    personal_basis: {
      ai_enabled: false,
      ai_explanation: "",
      ai_lucky_themes: [],
      ai_confidence: 0,
    },
    recent_draws: [],
    disclaimer: "仅供娱乐参考，请理性看待结果。",
  },
};

const state = {
  activeGame: "ssq",
  analysisWindow: 30,
  analysisPayload: null,
  currentPrediction: { main: [], special: [] },
  games: DEMO_GAMES,
  gameRules: DEMO_GAME_RULES,
  demoMode: false,
  manualRunCount: 0,
  activeMode: "steady",
  predictionRequestId: 0,
  predictionAbortController: null,
  planDraft: null,
  planSave: {
    generation: 0,
    saving: false,
    savedId: "",
    synced: false,
    pending: false,
    retryable: false,
    blocked: false,
    message: "尚未保存",
    tracked: false,
  },
};

const els = {
  apiStatus: document.querySelector("#apiStatus"),
  gameTabs: document.querySelector("#gameTabs"),
  latestIssue: document.querySelector("#latestIssue"),
  latestDate: document.querySelector("#latestDate"),
  fortuneNumber: document.querySelector("#fortuneNumber"),
  bestDate: document.querySelector("#bestDate"),
  luckScore: document.querySelector("#luckScore"),
  oracleBoard: document.querySelector(".oracle-board"),
  predictionResults: document.querySelector("#predictionResults"),
  numberBalls: document.querySelector("#numberBalls"),
  predictForm: document.querySelector("#predictForm"),
  submitButton: document.querySelector("#submitButton"),
  generateFeedback: document.querySelector("#generateFeedback"),
  fortuneModeOptions: document.querySelector("#fortuneModeOptions"),
  drawCount: document.querySelector("#drawCount"),
  hotNumbers: document.querySelector("#hotNumbers"),
  historyHotText: document.querySelector("#historyHotText"),
  coldNumbers: document.querySelector("#coldNumbers"),
  aiState: document.querySelector("#aiState"),
  personalBasis: document.querySelector("#personalBasis"),
  fortuneHeadline: document.querySelector("#fortuneHeadline"),
  fortuneSubline: document.querySelector("#fortuneSubline"),
  fortuneTags: document.querySelector("#fortuneTags"),
  metaphysicsProfile: document.querySelector("#metaphysicsProfile"),
  avoidNumbers: document.querySelector("#avoidNumbers"),
  masterRitual: document.querySelector("#masterRitual"),
  fortuneRitualPanel: document.querySelector(".fortune-ritual-panel"),
  dailyFortuneSign: document.querySelector("#dailyFortuneSign"),
  ritualStatus: document.querySelector("#ritualStatus"),
  ritualProgress: document.querySelector("#ritualProgress"),
  ritualSteps: document.querySelector("#ritualSteps"),
  credibilityChain: document.querySelector("#credibilityChain"),
  interpretationLayers: document.querySelector("#interpretationLayers"),
  numberReasons: document.querySelector("#numberReasons"),
  profileBook: document.querySelector("#profileBook"),
  dailyFortuneCalendar: document.querySelector("#dailyFortuneCalendar"),
  recentDraws: document.querySelector("#recentDraws"),
  disclaimer: document.querySelector("#disclaimer"),
  fortuneHistory: document.querySelector("#fortuneHistory"),
  profileCalendarPanel: document.querySelector(".profile-calendar-panel"),
  historyPanel: document.querySelector(".history-panel"),
  clearHistoryButton: document.querySelector("#clearHistoryButton"),
  predictionActions: document.querySelector("#predictionActions"),
  savePlanButton: document.querySelector("#savePlanButton"),
  openWorkbenchLink: document.querySelector("#openWorkbenchLink"),
  savedPlanLink: document.querySelector("#savedPlanLink"),
  planSaveStatus: document.querySelector("#planSaveStatus"),
  analysisEntry: document.querySelector("#analysisEntry"),
  strategyEntry: document.querySelector("#strategyEntry"),
  analysisWindowTabs: document.querySelector("#analysisWindowTabs"),
  analysisSummary: document.querySelector("#analysisSummary"),
  analysisHotCold: document.querySelector("#analysisHotCold"),
  analysisTrend: document.querySelector("#analysisTrend"),
  analysisShape: document.querySelector("#analysisShape"),
  analysisRecentDraws: document.querySelector("#analysisRecentDraws"),
  aiSettingsButton: document.querySelector("#aiSettingsButton"),
  aiSettingsLabel: document.querySelector("#aiSettingsLabel"),
  aiSettingsDialog: document.querySelector("#aiSettingsDialog"),
  aiSettingsForm: document.querySelector("#aiSettingsForm"),
  deepseekApiKey: document.querySelector("#deepseekApiKey"),
  showDeepseekApiKey: document.querySelector("#showDeepseekApiKey"),
  aiSettingsHint: document.querySelector("#aiSettingsHint"),
  closeAiSettingsButton: document.querySelector("#closeAiSettingsButton"),
  clearAiSettingsButton: document.querySelector("#clearAiSettingsButton"),
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

function setGenerateFeedback(message, isError = false) {
  if (!els.generateFeedback) return;
  els.generateFeedback.textContent = message;
  els.generateFeedback.classList.toggle("error", isError);
}

function currentTimeLabel() {
  const now = new Date();
  return now.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function currentModeLabel(mode = state.activeMode) {
  return MODE_LABELS[mode] || "稳财号";
}

function clientId() {
  try {
    const existing = localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const generated = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `client-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(CLIENT_ID_KEY, generated);
    return generated;
  } catch (error) {
    return "client-session";
  }
}

function updateAiSettingsState() {
  const configured = Boolean(window.LotteryAiKey?.read());
  if (els.aiSettingsButton) {
    els.aiSettingsButton.classList.toggle("is-configured", configured);
    els.aiSettingsButton.setAttribute(
      "aria-label",
      configured ? "DeepSeek Key 已配置，打开设置" : "打开 DeepSeek AI 设置",
    );
  }
  if (els.aiSettingsLabel) {
    els.aiSettingsLabel.textContent = configured ? "AI 已配置" : "AI 设置";
  }
}

function setAiSettingsHint(message, isError = false) {
  if (!els.aiSettingsHint) return;
  els.aiSettingsHint.textContent = message;
  els.aiSettingsHint.classList.toggle("error", isError);
}

function closeAiSettings() {
  if (!els.aiSettingsDialog) return;
  if (typeof els.aiSettingsDialog.close === "function") {
    els.aiSettingsDialog.close();
  } else {
    els.aiSettingsDialog.removeAttribute("open");
  }
}

function openAiSettings() {
  if (!els.aiSettingsDialog || !els.deepseekApiKey) return;
  els.deepseekApiKey.value = window.LotteryAiKey?.read() || "";
  els.deepseekApiKey.type = "password";
  if (els.showDeepseekApiKey) els.showDeepseekApiKey.checked = false;
  setAiSettingsHint("密钥仅保存在当前浏览器，起盘时使用。");
  if (typeof els.aiSettingsDialog.showModal === "function") {
    els.aiSettingsDialog.showModal();
  } else {
    els.aiSettingsDialog.setAttribute("open", "");
  }
  els.deepseekApiKey.focus();
}

function setupAiSettings() {
  updateAiSettingsState();
  els.aiSettingsButton?.addEventListener("click", openAiSettings);
  els.closeAiSettingsButton?.addEventListener("click", closeAiSettings);
  els.showDeepseekApiKey?.addEventListener("change", () => {
    if (!els.deepseekApiKey) return;
    els.deepseekApiKey.type = els.showDeepseekApiKey.checked ? "text" : "password";
  });
  els.aiSettingsDialog?.addEventListener("click", (event) => {
    if (event.target === els.aiSettingsDialog) closeAiSettings();
  });
  els.aiSettingsForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      window.LotteryAiKey.save(els.deepseekApiKey?.value || "");
      updateAiSettingsState();
      setAiSettingsHint("已保存到当前浏览器。");
      window.setTimeout(closeAiSettings, 320);
    } catch (error) {
      setAiSettingsHint(error?.message || "保存失败，请重试。", true);
    }
  });
  els.clearAiSettingsButton?.addEventListener("click", () => {
    try {
      window.LotteryAiKey?.clear();
      if (els.deepseekApiKey) els.deepseekApiKey.value = "";
      updateAiSettingsState();
      setAiSettingsHint("密钥已从当前浏览器清除。");
    } catch (error) {
      setAiSettingsHint("清除失败，请检查浏览器存储权限。", true);
    }
  });
}

function resetSubmitButtonLabel() {
  const label = els.submitButton?.querySelector("span");
  if (!label) return;
  label.textContent = "开始起盘";
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isStrictIsoDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() + 1 === month
    && parsed.getUTCDate() === day
  );
}

function createPredictionPlanRequestId() {
  const cryptoApi = window.crypto;
  let raw = "";
  if (cryptoApi?.randomUUID) {
    raw = cryptoApi.randomUUID();
  } else if (cryptoApi?.getRandomValues) {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    raw = [
      hex.slice(0, 4).join(""),
      hex.slice(4, 6).join(""),
      hex.slice(6, 8).join(""),
      hex.slice(8, 10).join(""),
      hex.slice(10, 16).join(""),
    ].join("-");
  } else {
    raw = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 18)}`;
  }
  return `prediction:${raw.replace(/[^A-Za-z0-9._:-]/g, "")}`.slice(0, 96);
}

function renderPlanActions() {
  if (!els.predictionActions) return;
  const draft = state.planDraft;
  const visible = Boolean(draft && draft.game_key === "3d");
  els.predictionActions.hidden = !visible;
  if (els.openWorkbenchLink) els.openWorkbenchLink.href = "./analysis.html?game=3d";
  if (!visible) {
    if (els.savedPlanLink) els.savedPlanLink.hidden = true;
    if (els.planSaveStatus) els.planSaveStatus.textContent = "尚未保存";
    if (els.savePlanButton) {
      els.savePlanButton.disabled = false;
      els.savePlanButton.textContent = "保存为本期方案";
    }
    return;
  }

  const save = state.planSave;
  const canClaim = draft.can_claim_current === true;
  let buttonText = save.retryable ? "重试保存" : "保存为本期方案";
  if (save.saving) buttonText = "保存中";
  if (save.pending) buttonText = "待同步";
  if (save.savedId || save.synced) buttonText = "已保存";
  const disabled = (
    save.saving
    || save.pending
    || Boolean(save.savedId || save.synced)
    || save.blocked
    || !canClaim
  );
  if (els.savePlanButton) {
    els.savePlanButton.textContent = buttonText;
    els.savePlanButton.disabled = disabled;
  }
  if (els.savedPlanLink) {
    const id = String(save.savedId || "");
    els.savedPlanLink.hidden = !id;
    if (id) els.savedPlanLink.href = `./result.html?id=${encodeURIComponent(id)}`;
  }
  if (els.planSaveStatus) {
    els.planSaveStatus.textContent = save.message || (
      canClaim ? "尚未保存" : "数据过期/不可保存，可去3D工作台继续筛选。"
    );
  }
}

function resetPlanActions(message = "尚未保存") {
  state.planDraft = null;
  state.planSave = {
    generation: state.planSave.generation + 1,
    saving: false,
    savedId: "",
    synced: false,
    pending: false,
    retryable: false,
    blocked: false,
    message,
    tracked: false,
  };
  renderPlanActions();
}

function build3dPlanDraft(payload, requestContext) {
  if (!payload || payload.game_key !== "3d" || !requestContext?.planRequestId) {
    return null;
  }
  const freshness = payload.data_freshness;
  const canClaim = freshness?.can_claim_current === true;
  return {
    game_key: "3d",
    target_issue: String(payload.target_issue || "").trim(),
    target_draw_date: String(payload.target_draw_date || "").trim(),
    source_type: "fortune",
    request_id: requestContext.planRequestId,
    title: "首页财运号",
    entries: [
      {
        position: 0,
        main_numbers: [...payload.numbers.main],
        special_numbers: [],
        note: "首页财运号",
      },
    ],
    condition_snapshot: {
      mode: "simple",
      analysis_window: 30,
      conditions: {},
      metrics: {...payload.number_metrics},
      latest_data_issue: String(freshness.latest_issue || "").trim(),
      latest_data_date: String(freshness.latest_date || "").trim(),
    },
    can_claim_current: canClaim,
    freshness_status: String(freshness.status || (canClaim ? "fresh" : "stale")).trim(),
  };
}

function activatePlanDraft(payload, requestContext) {
  const draft = build3dPlanDraft(payload, requestContext);
  if (!draft) {
    resetPlanActions();
    return;
  }
  state.planDraft = draft;
  state.planSave = {
    generation: requestContext.requestId,
    saving: false,
    savedId: "",
    synced: false,
    pending: false,
    retryable: false,
    blocked: false,
    message: draft.can_claim_current
      ? "尚未保存"
      : "数据过期/不可保存，可去3D工作台继续筛选。",
    tracked: false,
  };
  renderPlanActions();
}

function isCurrentPlanSave(generation, requestId) {
  return (
    state.planSave.generation === generation
    && state.activeGame === "3d"
    && state.planDraft?.request_id === requestId
  );
}

function trackPlanSavedOnce() {
  if (state.planSave.tracked || !state.planDraft) return;
  state.planSave.tracked = true;
  try {
    window.LotteryProduct?.track?.("plan_saved", {
      game_key: "3d",
      source_type: "fortune",
      freshness_status: state.planDraft.freshness_status || "fresh",
    })?.catch?.(() => {});
  } catch (error) {
    // Tracking must never change the save result.
  }
}

function trackPredictionCompleted(payload, requestContext) {
  if (!payload || requestContext.predictionTracked || state.demoMode) return;
  requestContext.predictionTracked = true;
  const properties = {
    game_key: payload.game_key || requestContext.gameKey,
    source_type: "fortune",
    mode: requestContext.modeKey || "steady",
    entry_count: 1,
  };
  const freshnessStatus = String(payload.data_freshness?.status || "").trim();
  if (["fresh", "attention", "stale", "empty"].includes(freshnessStatus)) {
    properties.freshness_status = freshnessStatus;
  }
  try {
    window.LotteryProduct?.track?.("prediction_completed", properties)?.catch?.(() => {});
  } catch (error) {
    // Tracking must never change the prediction result.
  }
}

function savePlanConflictMessage(error) {
  const detail = String(error?.detail || error?.message || "");
  if (error?.status === 409 && detail.includes("target issue is already drawn")) {
    return {
      blocked: true,
      message: "本期已开奖，可查看复盘或创建下一期。",
    };
  }
  if (error?.status === 409) {
    return {
      blocked: true,
      message: "方案暂不可保存，请去3D工作台刷新本期数据后重试。",
    };
  }
  return null;
}

async function saveCurrentPlan() {
  const draft = state.planDraft;
  if (
    !draft
    || state.planSave.saving
    || state.planSave.savedId
    || state.planSave.pending
    || draft.can_claim_current !== true
  ) {
    return;
  }
  const generation = state.planSave.generation;
  const requestId = draft.request_id;
  state.planSave = {
    ...state.planSave,
    saving: true,
    retryable: false,
    blocked: false,
    message: "正在保存方案...",
  };
  renderPlanActions();
  try {
    const result = await window.LotteryProduct.createPlan(draft);
    if (!isCurrentPlanSave(generation, requestId)) return;
    const plan = isPlainObject(result?.plan) ? result.plan : {};
    const savedId = String(plan.id || result?.id || "").trim();
    const duplicate = Boolean(result?.duplicate_warning || plan.duplicate_warning);
    state.planSave = {
      ...state.planSave,
      saving: false,
      savedId,
      synced: true,
      pending: false,
      retryable: false,
      blocked: false,
      message: duplicate
        ? "已保存；检测到重复或相近方案，可在详情中合并查看。"
        : "已保存，可查看方案详情。",
    };
    renderPlanActions();
    trackPlanSavedOnce();
  } catch (error) {
    if (!isCurrentPlanSave(generation, requestId)) return;
    const conflict = savePlanConflictMessage(error);
    if (error?.network === true && error.pending === true && error.persistedLocally === true) {
      state.planSave = {
        ...state.planSave,
        saving: false,
        pending: true,
        retryable: false,
        blocked: false,
        message: "已进入待同步队列，网络恢复后会继续保存；当前状态为待同步。",
      };
    } else if (error?.network === true) {
      state.planSave = {
        ...state.planSave,
        saving: false,
        pending: false,
        retryable: true,
        blocked: false,
        message: "尚未保存，请稍后重试；当前号码已保留。",
      };
    } else if (conflict) {
      state.planSave = {
        ...state.planSave,
        saving: false,
        pending: false,
        retryable: false,
        blocked: conflict.blocked,
        message: conflict.message,
      };
    } else {
      state.planSave = {
        ...state.planSave,
        saving: false,
        pending: false,
        retryable: true,
        blocked: false,
        message: "尚未保存，请稍后重试；当前号码已保留。",
      };
    }
    renderPlanActions();
  }
}

function currentPlanMatchesSync(detail) {
  return (
    isPlainObject(detail)
    && typeof detail.request_id === "string"
    && state.activeGame === "3d"
    && state.planDraft?.request_id === detail.request_id.trim()
  );
}

function applyPlanSyncEvent(detail) {
  if (!currentPlanMatchesSync(detail)) return;
  const status = String(detail.status || "").trim();
  if (status === "saved") {
    const plan = isPlainObject(detail.plan) ? detail.plan : {};
    const savedId = String(plan.id || "").trim();
    state.planSave = {
      ...state.planSave,
      saving: false,
      savedId,
      synced: true,
      pending: false,
      retryable: false,
      blocked: false,
      message: savedId
        ? "待同步方案已保存，可查看方案详情。"
        : "待同步方案已保存，但暂未返回可查看详情。",
    };
    renderPlanActions();
    trackPlanSavedOnce();
    return;
  }
  if (status === "blocked") {
    state.planSave = {
      ...state.planSave,
      saving: false,
      savedId: "",
      synced: false,
      pending: false,
      retryable: false,
      blocked: true,
      message: "同步被服务端拒绝，请去3D工作台刷新本期数据后重试。",
    };
    renderPlanActions();
    return;
  }
  if (status === "retryable") {
    state.planSave = {
      ...state.planSave,
      saving: false,
      savedId: "",
      synced: false,
      pending: true,
      retryable: false,
      blocked: false,
      message: "待同步未完成，网络或服务恢复后会继续重试。",
    };
    renderPlanActions();
  }
}

function setupPlanSyncListener() {
  const key = "__lotteryLuckPlanSyncListenerInstalled";
  if (window[key]) return;
  window[key] = true;
  window.addEventListener("lotteryproduct:plansync", (event) => {
    applyPlanSyncEvent(event.detail);
  });
}

function normalizeDailyFortuneSign(sign) {
  const data = sign && typeof sign === "object" ? sign : {};
  return {
    ...DEFAULT_DAILY_FORTUNE_SIGN,
    ...data,
    headline: data.headline || DEFAULT_DAILY_FORTUNE_SIGN.headline,
    tags: Array.isArray(data.tags) && data.tags.length
      ? data.tags
      : DEFAULT_DAILY_FORTUNE_SIGN.tags,
    lucky_tails: Array.isArray(data.lucky_tails) ? data.lucky_tails : DEFAULT_DAILY_FORTUNE_SIGN.lucky_tails,
    avoid_tails: Array.isArray(data.avoid_tails) ? data.avoid_tails : DEFAULT_DAILY_FORTUNE_SIGN.avoid_tails,
  };
}

function normalizeRitualSteps(steps) {
  const rows = Array.isArray(steps) && steps.length ? steps : DEFAULT_RITUAL_STEPS;
  return rows.map((step, index) => {
    const fallback = DEFAULT_RITUAL_STEPS[index] || DEFAULT_RITUAL_STEPS[DEFAULT_RITUAL_STEPS.length - 1];
    return {
      key: step?.key || fallback.key,
      label: step?.label || fallback.label,
      summary: step?.summary || fallback.summary,
    };
  });
}

function normalizePredictionPayload(payload) {
  const data = payload && typeof payload === "object" ? payload : {};
  const avoidNumbers = Array.isArray(data.avoid_numbers) ? data.avoid_numbers : [];
  const avoidReasons = Array.isArray(data.avoid_reasons) && data.avoid_reasons.length
    ? data.avoid_reasons
    : avoidNumbers.map((item) => item?.reason).filter(Boolean);
  return {
    ...data,
    daily_fortune_sign: normalizeDailyFortuneSign(data.daily_fortune_sign),
    ritual_steps: normalizeRitualSteps(data.ritual_steps),
    master_ritual: normalizeMasterRitual(data.master_ritual),
    avoid_reasons: avoidReasons,
  };
}

function normalizeNumberRule(rule) {
  if (!rule || typeof rule !== "object") return null;
  const mainCount = Number(rule.main_count);
  const mainMin = Number(rule.main_min);
  const mainMax = Number(rule.main_max);
  const specialCount = Number(rule.special_count || 0);
  const specialMin = rule.special_min === null || rule.special_min === undefined
    ? null
    : Number(rule.special_min);
  const specialMax = rule.special_max === null || rule.special_max === undefined
    ? null
    : Number(rule.special_max);
  if (
    !Number.isInteger(mainCount)
    || !Number.isInteger(mainMin)
    || !Number.isInteger(mainMax)
    || !Number.isInteger(specialCount)
    || mainCount < 0
    || specialCount < 0
    || mainMin > mainMax
  ) {
    return null;
  }
  if (
    specialCount > 0
    && (
      !Number.isInteger(specialMin)
      || !Number.isInteger(specialMax)
      || specialMin > specialMax
    )
  ) {
    return null;
  }
  return {
    main_count: mainCount,
    main_min: mainMin,
    main_max: mainMax,
    special_count: specialCount,
    special_min: specialCount > 0 ? specialMin : null,
    special_max: specialCount > 0 ? specialMax : null,
    allow_repeat: Boolean(rule.allow_repeat),
    special_distinct_from_main: Boolean(rule.special_distinct_from_main),
  };
}

function gameRulesFromGames(games) {
  const rules = {...DEMO_GAME_RULES};
  (Array.isArray(games) ? games : []).forEach((game) => {
    const key = String(game?.game_key || "").trim().toLowerCase();
    const rule = normalizeNumberRule(game?.number_rule);
    if (key && rule) rules[key] = rule;
  });
  return rules;
}

function hasDuplicateNumbers(numbers) {
  return new Set(numbers).size !== numbers.length;
}

function assertNumberList(numbers, rule, poolName) {
  const countKey = `${poolName}_count`;
  const minKey = `${poolName}_min`;
  const maxKey = `${poolName}_max`;
  const expectedCount = rule[countKey];
  if (!Array.isArray(numbers)) {
    throw new Error(`invalid prediction payload: ${poolName} numbers missing`);
  }
  if (numbers.length !== expectedCount) {
    throw new Error(`invalid prediction payload: ${poolName} count mismatch`);
  }
  numbers.forEach((number) => {
    if (
      !Number.isInteger(number)
      || number < rule[minKey]
      || number > rule[maxKey]
    ) {
      throw new Error(`invalid prediction payload: ${poolName} number out of range`);
    }
  });
}

function validate3dServerFields(payload) {
  const targetIssue = String(payload.target_issue || "").trim();
  const targetDrawDate = String(payload.target_draw_date || "").trim();
  const bestDrawDate = String(payload.best_draw_date || "").trim();
  if (!targetIssue || targetIssue.length > 32) {
    throw new Error("invalid prediction payload: target issue missing");
  }
  if (
    !isStrictIsoDate(targetDrawDate)
    || !isStrictIsoDate(bestDrawDate)
    || targetDrawDate !== bestDrawDate
  ) {
    throw new Error("invalid prediction payload: target date mismatch");
  }
  const freshness = payload.data_freshness;
  if (!isPlainObject(freshness)) {
    throw new Error("invalid prediction payload: freshness missing");
  }
  const latestIssue = String(freshness.latest_issue || "").trim();
  const latestDate = String(freshness.latest_date || "").trim();
  if (!latestIssue || latestIssue.length > 32 || !isStrictIsoDate(latestDate)) {
    throw new Error("invalid prediction payload: freshness latest data invalid");
  }
  if (typeof freshness.can_claim_current !== "boolean") {
    throw new Error("invalid prediction payload: freshness claim flag invalid");
  }
  if (!isPlainObject(payload.number_metrics)) {
    throw new Error("invalid prediction payload: number metrics missing");
  }
  payload.target_issue = targetIssue;
  payload.target_draw_date = targetDrawDate;
  payload.data_freshness = {
    ...freshness,
    latest_issue: latestIssue,
    latest_date: latestDate,
  };
}

function validatePredictionPayload(payload, expectedGameKey) {
  if (!payload || typeof payload !== "object") {
    throw new Error("invalid prediction payload: response must be an object");
  }
  const payloadGameKey = String(payload.game_key || "").trim().toLowerCase();
  const gameKey = String(expectedGameKey || payloadGameKey || state.activeGame).trim().toLowerCase();
  if (payloadGameKey && payloadGameKey !== gameKey) {
    throw new Error("invalid prediction payload: game mismatch");
  }
  const rule = state.gameRules[gameKey] || DEMO_GAME_RULES[gameKey];
  if (!rule) {
    throw new Error("invalid prediction payload: unknown game rule");
  }
  const numbers = payload.numbers;
  if (!numbers || typeof numbers !== "object" || Array.isArray(numbers)) {
    throw new Error("invalid prediction payload: numbers missing");
  }
  const main = numbers.main;
  const special = numbers.special;
  assertNumberList(main, rule, "main");
  assertNumberList(special, rule, "special");
  if (!rule.allow_repeat && hasDuplicateNumbers(main)) {
    throw new Error("invalid prediction payload: duplicate main numbers");
  }
  if (hasDuplicateNumbers(special)) {
    throw new Error("invalid prediction payload: duplicate special numbers");
  }
  if (
    rule.special_distinct_from_main
    && special.some((number) => main.includes(number))
  ) {
    throw new Error("invalid prediction payload: duplicate cross-pool numbers");
  }
  if (gameKey === "3d") validate3dServerFields(payload);
  return payload;
}

function normalizeMasterRitual(masterRitual) {
  const data = masterRitual && typeof masterRitual === "object" ? masterRitual : {};
  const tailMap = data.tail_map && typeof data.tail_map === "object" ? data.tail_map : {};
  return {
    opening: data.opening || "重新起盘后查看完整思路。",
    verdict: data.verdict || "本次暂无取号说明。",
    tail_map: {
      favorable: Array.isArray(tailMap.favorable) ? tailMap.favorable : [],
      avoid: Array.isArray(tailMap.avoid) ? tailMap.avoid : [],
      legend: tailMap.legend || "尾数1/2木，3/4火，5/6土，7/8金，9/0水。",
    },
    steps: Array.isArray(data.steps) ? data.steps : [],
  };
}

function renderDailyFortuneSign(sign) {
  if (!els.dailyFortuneSign) return;
  const data = normalizeDailyFortuneSign(sign);
  els.dailyFortuneSign.replaceChildren();

  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "今日财签";
  const headline = document.createElement("strong");
  headline.textContent = data.headline;
  copy.append(kicker, headline);

  const tagWrap = document.createElement("div");
  tagWrap.className = "fortune-sign-tags";
  data.tags.slice(0, 3).forEach((tag) => {
    const chip = document.createElement("span");
    chip.textContent = tag;
    tagWrap.append(chip);
  });
  els.dailyFortuneSign.append(copy, tagWrap);
}

function renderRitualSteps(steps, activeIndex = Number.MAX_SAFE_INTEGER) {
  if (!els.ritualSteps) return;
  const rows = normalizeRitualSteps(steps);
  els.ritualSteps.replaceChildren();
  rows.forEach((step, index) => {
    const item = document.createElement("div");
    item.className = "ritual-step";
    if (index < activeIndex) item.classList.add("done");
    if (index === activeIndex) item.classList.add("active");
    const number = document.createElement("span");
    number.textContent = String(index + 1);
    const label = document.createElement("strong");
    label.textContent = step.label;
    const summary = document.createElement("small");
    summary.textContent = step.summary;
    item.append(number, label, summary);
    els.ritualSteps.append(item);
  });
}

function setRitualState(stateName, label = "", progress = 0) {
  els.fortuneRitualPanel?.classList.toggle("is-ritual-running", stateName === "running");
  els.fortuneRitualPanel?.classList.toggle("is-ritual-complete", stateName === "complete");
  if (els.ritualStatus) {
    els.ritualStatus.textContent = label || "点击后逐步起盘";
  }
  if (els.ritualProgress) {
    const bounded = Math.max(0, Math.min(100, Number(progress) || 0));
    els.ritualProgress.style.setProperty("--ritual-progress", String(bounded));
  }
}

function startRitualPreview(shouldContinue = () => true) {
  if (!shouldContinue()) return;
  if (els.predictionResults) {
    els.predictionResults.hidden = false;
    els.predictionResults.classList.add("is-generating");
  }
  renderDailyFortuneSign(DEFAULT_DAILY_FORTUNE_SIGN);
  setRitualState("running", "正在起盘 · 校准财运盘", 8);
  renderRitualSteps(DEFAULT_RITUAL_STEPS, 0);
}

function flashResultPanels(userInitiated) {
  if (!userInitiated) return;
  [els.oracleBoard, document.querySelector(".fortune-hook")].forEach((panel) => {
    if (!panel) return;
    panel.classList.remove("result-refreshed");
    panel.getBoundingClientRect();
    panel.classList.add("result-refreshed");
  });
}

function preferredScrollBehavior() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ? "auto"
    : "smooth";
}

function scrollToResult(userInitiated) {
  if (!userInitiated || !els.oracleBoard) return;
  els.oracleBoard.scrollIntoView({ behavior: preferredScrollBehavior(), block: "center" });
}

function currentGameMeta() {
  return state.games.find((game) => game.game_key === state.activeGame) || DEMO_GAMES[0];
}

function formatDateTime(isoDate) {
  if (!isoDate || isoDate === "--") return "数据更新：--";
  return `数据更新：${isoDate} 10:30`;
}

function formatOracleDate(isoDate) {
  if (!isoDate) return "--";
  const date = new Date(`${isoDate}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${date.getMonth() + 1}月${date.getDate()}日　${weekdays[date.getDay()]}`;
}

function renderTabs() {
  els.gameTabs.replaceChildren();
  VISIBLE_GAME_KEYS.forEach((key) => {
    const meta = state.games.find((game) => game.game_key === key) || {
      game_key: key,
      game_name: GAME_LABELS[key],
      latest_date: "--",
      latest_issue: "--",
    };
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab-button${key === state.activeGame ? " active" : ""}`;
    button.setAttribute("aria-pressed", String(key === state.activeGame));
    button.dataset.game = key;

    const title = document.createElement("strong");
    title.textContent = GAME_LABELS[key] || meta.game_name;
    const subtitle = document.createElement("span");
    subtitle.textContent = `${meta.latest_issue || "--"} / ${meta.latest_date || "--"}`;
    button.append(title, subtitle);
    els.gameTabs.append(button);
  });
}

function renderGameMeta() {
  const meta = currentGameMeta();
  els.latestIssue.textContent = `最新期号 ${meta.latest_issue || "--"}`;
  els.latestDate.textContent = formatDateTime(meta.latest_date);
  renderAnalysisEntry();
  renderStrategyEntry();
}

function renderAnalysisEntry() {
  if (!els.analysisEntry) return;
  els.analysisEntry.href = `./analysis.html?game=${encodeURIComponent(state.activeGame)}`;
}

function renderStrategyEntry() {
  if (!els.strategyEntry) return;
  els.strategyEntry.href = state.activeGame === "3d"
    ? "./analysis.html?game=3d&mode=pro&window=30"
    : `./strategy.html?game=${encodeURIComponent(state.activeGame)}`;
}

function hasAnalysisWorkbench() {
  return Boolean(
    els.analysisWindowTabs
      && els.analysisSummary
      && els.analysisHotCold
      && els.analysisTrend
      && els.analysisShape
      && els.analysisRecentDraws,
  );
}

function ballClass(gameKey, isSpecial) {
  if (gameKey === "3d") return "ball digit";
  if ((gameKey === "ssq" || gameKey === "dlt") && isSpecial) return "ball special";
  if (gameKey === "qlc" && isSpecial) return "ball qlc-special";
  return "ball";
}

function renderPrediction(payload) {
  payload = normalizePredictionPayload(payload);
  els.oracleBoard?.classList.remove("is-idle");
  if (els.predictionResults) {
    els.predictionResults.hidden = false;
    els.predictionResults.classList.remove("is-generating");
  }
  const main = payload?.numbers?.main || [];
  const special = payload?.numbers?.special || [];
  state.currentPrediction = { main, special };
  const allNumbers = [...main, ...special];
  els.fortuneNumber.textContent = allNumbers.map(padNumber).join(" ") || "--";
  els.bestDate.textContent = formatOracleDate(payload.best_draw_date);
  els.luckScore.textContent =
    payload.luck_score === undefined ? "--" : `${Math.round(Number(payload.luck_score))}`;

  els.numberBalls.replaceChildren();
  main.forEach((number) => appendBall(number, ballClass(payload.game_key, false)));
  special.forEach((number) => appendBall(number, ballClass(payload.game_key, true)));
  if (!main.length && !special.length) {
    const empty = document.createElement("span");
    empty.className = "empty-state";
    empty.textContent = "暂无号码";
    els.numberBalls.append(empty);
  }

  const basis = payload.history_basis || {};
  els.drawCount.textContent = "近期走势";
  renderMiniNumbers(els.hotNumbers, basis.hot_main, special);
  els.historyHotText.textContent = formatNumberList(basis.hot_main);
  els.coldNumbers.textContent = formatNumberList(basis.cold_main);

  els.aiState.textContent = "命盘合参";
  const ritual = payload.ritual_summary || "财运合参完成：使用个人时空与开奖日气口生成推荐号。";
  const profile = payload.metaphysics_profile || {};
  const profileSummary = profile.wealth_pattern
    ? `${profile.wealth_pattern}：${profile.reading || "以个人时空推导本期财气。"} ${profile.selection_rule || ""}`
    : ritual;
  els.personalBasis.textContent = profileSummary;
  renderDailyFortuneSign(payload.daily_fortune_sign);
  renderRitualSteps(payload.ritual_steps);
  renderFortuneHook(payload);
  renderMasterRitual(payload.master_ritual);
  renderCredibilityChain(payload.credibility_chain);
  renderInterpretationLayers(payload.interpretation_layers);
  renderNumberReasons(payload.number_reasons, main, special);

  renderRecentDraws(payload.recent_draws || []);
  els.disclaimer.textContent = payload.disclaimer || "仅供娱乐参考，请理性看待结果。";
  if (state.analysisPayload) renderAnalysis(state.analysisPayload);
}

function formatTailEntry(entry) {
  if (!entry || typeof entry !== "object") return "";
  const tail = entry.tail === undefined ? "" : String(entry.tail);
  const label = entry.element_label ? `${entry.element_label}尾` : "尾";
  return tail ? `${tail}${label}` : "";
}

function renderMasterRitual(masterRitual) {
  if (!els.masterRitual) return;
  const data = normalizeMasterRitual(masterRitual);
  els.masterRitual.replaceChildren();

  const verdict = document.createElement("strong");
  verdict.textContent = data.verdict;
  const opening = document.createElement("p");
  opening.textContent = data.opening;
  els.masterRitual.append(verdict, opening);

  const steps = Array.isArray(data.steps) ? data.steps : [];
  if (steps.length) {
    const list = document.createElement("ol");
    list.className = "master-ritual-steps";
    steps.forEach((step) => {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = step.label || "起盘节点";
      const value = document.createElement("b");
      value.textContent = step.value || "--";
      const detail = document.createElement("small");
      detail.textContent = step.detail || "";
      item.append(label, value, detail);
      list.append(item);
    });
    els.masterRitual.append(list);
  }

  const favorable = data.tail_map.favorable.map(formatTailEntry).filter(Boolean);
  const avoid = data.tail_map.avoid.map(formatTailEntry).filter(Boolean);
  if (favorable.length || avoid.length) {
    const tailLine = document.createElement("div");
    tailLine.className = "master-tail-map";
    const favorableText = document.createElement("span");
    favorableText.textContent = `喜用尾数 ${favorable.join("、") || "--"}`;
    const avoidText = document.createElement("span");
    avoidText.textContent = `避开尾数 ${avoid.join("、") || "--"}`;
    tailLine.append(favorableText, avoidText);
    els.masterRitual.append(tailLine);
  }
}

function renderCredibilityChain(chain) {
  if (!els.credibilityChain) return;
  const items = Array.isArray(chain) ? chain : [];
  els.credibilityChain.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("li");
    empty.textContent = "本次暂无详细依据。";
    els.credibilityChain.append(empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = item.title || "合参节点";
    const text = document.createElement("span");
    text.textContent = item.text || "--";
    const detail = document.createElement("small");
    detail.textContent = item.detail || "";
    row.append(title, text, detail);
    els.credibilityChain.append(row);
  });
}

function renderInterpretationLayers(layers) {
  if (!els.interpretationLayers) return;
  els.interpretationLayers.replaceChildren();
  const shortHook = document.createElement("strong");
  shortHook.textContent = layers?.short_hook || "本次暂无解读。";
  const longReading = document.createElement("p");
  longReading.textContent = layers?.long_reading || "重新起盘后查看完整内容。";
  els.interpretationLayers.append(shortHook, longReading);
}

function renderFortuneHook(payload) {
  if (!els.fortuneHeadline || !els.metaphysicsProfile || !els.avoidNumbers) return;
  const hook = payload?.fortune_hook || {};
  const profile = payload?.metaphysics_profile || {};

  els.fortuneHeadline.textContent = hook.headline || "本次结果已清空";
  els.fortuneSubline.textContent = hook.subline || "重新填写信息即可生成新的参考。";

  els.fortuneTags.replaceChildren();
  const tags = Array.isArray(hook.tags) && hook.tags.length
    ? hook.tags
    : ["本命财格", "今日宜忌", "避开号"];
  tags.slice(0, 4).forEach((tag) => {
    const chip = document.createElement("span");
    chip.textContent = tag;
    els.fortuneTags.append(chip);
  });

  const entries = [
    ["本命财格", profile.wealth_pattern || "--"],
    ["喜用取数", profile.favorable_element_labels ? `${profile.favorable_element_labels}入局` : "--"],
    ["今日宜忌", profile.day_advice || "--"],
    ["取号逻辑", profile.selection_rule || "--"],
  ];
  els.metaphysicsProfile.replaceChildren();
  entries.forEach(([label, value]) => {
    const row = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    row.append(dt, dd);
    els.metaphysicsProfile.append(row);
  });

  els.avoidNumbers.replaceChildren();
  const avoidNumbers = Array.isArray(payload?.avoid_numbers) ? payload.avoid_numbers : [];
  if (!avoidNumbers.length) {
    els.avoidNumbers.textContent = "--";
    return;
  }
  avoidNumbers.slice(0, 4).forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "avoid-chip";
    const number = document.createElement("b");
    number.textContent = padNumber(item.number);
    const reason = document.createElement("small");
    reason.textContent = item.reason || "本期先不入局";
    chip.append(number, reason);
    els.avoidNumbers.append(chip);
  });
}

function renderNumberReasons(reasonPayload, main, special) {
  if (!els.numberReasons) return;
  const mainReasons = Array.isArray(reasonPayload?.main)
    ? reasonPayload.main
    : main.map((number) => ({
        number,
        role: "主号",
        text: "个人时空入局，配合开奖日气口，作为主号财运参考。",
      }));
  const specialReasons = Array.isArray(reasonPayload?.special)
    ? reasonPayload.special
    : special.map((number) => ({
        number,
        role: "财眼",
        text: "用作财眼收束，平衡整组号码的财气。",
      }));
  const items = [...mainReasons, ...specialReasons];
  els.numberReasons.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("li");
    empty.textContent = "本次暂无号码说明。";
    els.numberReasons.append(empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("li");
    const number = document.createElement("b");
    number.textContent = padNumber(item.number);
    const body = document.createElement("div");
    body.className = "reason-body";
    const meta = document.createElement("p");
    meta.className = "reason-meta";
    const title = item.position_label || item.role || "号码";
    const element = item.element_label ? ` · ${item.element_label}数` : "";
    meta.textContent = `${title}${element}`;
    const lines = Array.isArray(item.lines) && item.lines.length
      ? item.lines
      : [item.text || `${item.role || "号码"}财运参考。`];
    const list = document.createElement("ul");
    list.className = "reason-lines";
    lines.forEach((line) => {
      const lineItem = document.createElement("li");
      lineItem.textContent = line;
      list.append(lineItem);
    });
    body.append(meta, list);
    row.append(number, body);
    els.numberReasons.append(row);
  });
}

function appendBall(number, className) {
  const ball = document.createElement("span");
  ball.className = className;
  ball.textContent = padNumber(number);
  els.numberBalls.append(ball);
}

function formatNumberList(values) {
  if (!Array.isArray(values) || !values.length) return "--";
  return values.map(padNumber).join(" / ");
}

function renderMiniNumbers(container, values, specialValues = []) {
  container.replaceChildren();
  const list = Array.isArray(values) ? values.slice(0, 9) : [];
  specialValues.slice(0, 1).forEach((number) => list.splice(2, 0, { value: number, special: true }));
  if (!list.length) {
    container.textContent = "--";
    return;
  }
  list.forEach((item) => {
    const value = typeof item === "object" ? item.value : item;
    const chip = document.createElement("span");
    chip.className = `mini-chip${typeof item === "object" && item.special ? " special" : ""}`;
    chip.textContent = padNumber(value);
    container.append(chip);
  });
}

function renderRecentDraws(draws) {
  els.recentDraws.replaceChildren();
  draws.slice(0, 4).forEach((draw) => {
    const item = document.createElement("li");
    const red = draw.red_numbers || (draw.numbers?.main || []).join(",");
    const blue = draw.blue_number ? ` + ${draw.blue_number}` : "";
    item.textContent = `${draw.draw_date || "--"} 第${draw.issue || "--"}期：${red}${blue}`;
    els.recentDraws.append(item);
  });
  if (!els.recentDraws.children.length) {
    const item = document.createElement("li");
    item.textContent = "暂无近期开奖数据。";
    els.recentDraws.append(item);
  }
}

function renderAnalysisWindowTabs() {
  if (!els.analysisWindowTabs) return;
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
  if (!els.analysisSummary) return;
  els.analysisSummary.classList.toggle("error", isError);
  els.analysisSummary.textContent = message;
}

function demoAnalysisPayload(gameKey) {
  const prediction = DEMO_PREDICTIONS[gameKey] || DEMO_PREDICTIONS.ssq;
  const main = prediction.history_basis?.hot_main || prediction.numbers.main || [];
  const cold = prediction.history_basis?.cold_main || [];
  const recent = (prediction.recent_draws || []).map((draw) => ({
    issue: draw.issue,
    draw_date: draw.draw_date,
    main: String(draw.red_numbers || "")
      .split(",")
      .filter(Boolean)
      .map(Number),
    special: String(draw.blue_number || "")
      .split(",")
      .filter(Boolean)
      .map(Number),
    overlap_with_prediction: 0,
    tags: ["Demo"],
  }));
  return {
    game_key: gameKey,
    window: state.analysisWindow,
    summary: {
      draw_count: Math.min(state.analysisWindow, prediction.history_basis?.draw_count || 0),
      latest_issue: prediction.recent_draws?.[0]?.issue || "--",
      latest_date: prediction.recent_draws?.[0]?.draw_date || "--",
    },
    hot: {
      main: main.slice(0, 10).map((number, index) => ({ number, count: Math.max(1, 10 - index) })),
      special: (prediction.numbers.special || []).map((number) => ({ number, count: 3 })),
    },
    cold: {
      main: cold.slice(0, 10).map((number, index) => ({ number, count: index })),
      special: [],
    },
    omission: {
      main: cold.slice(0, 10).map((number, index) => ({ number, missing: state.analysisWindow - index })),
      special: [],
    },
    position_hot: [],
    position_cold: [],
    position_omission: [],
    shape: {
      odd_even: [{ label: "均衡", count: 8 }],
      big_small: [{ label: "均衡", count: 7 }],
      sum_ranges: [{ label: "80-99", count: 6 }],
      consecutive_counts: [{ label: "1组连号", count: 4 }],
      range_distribution: [],
      digit_types: [],
      span: [],
      repeat_counts: [],
    },
    trend: {
      columns: main.slice(0, gameKey === "kl8" ? 8 : 12).map((number) => padNumber(number)),
      rows: recent.map((draw) => ({
        issue: draw.issue,
        draw_date: draw.draw_date,
        hits: draw.main,
        special_hits: draw.special,
      })),
    },
    recent_draws: recent,
  };
}

function analysisNumberLabel(value) {
  if (typeof value === "string" && value.includes("-")) return value;
  return padNumber(value);
}

function overlapWithPrediction(draw) {
  const main = new Set(draw.main || []);
  const special = new Set(draw.special || []);
  const predictedMain = new Set(state.currentPrediction.main || []);
  const predictedSpecial = new Set(state.currentPrediction.special || []);
  return [...main].filter((number) => predictedMain.has(number)).length
    + [...special].filter((number) => predictedSpecial.has(number)).length;
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

function renderAnalysisHotCold(payload) {
  const card = els.analysisHotCold;
  card.replaceChildren();
  analysisCardTitle(card, "热冷遗漏", `${payload.window}期`);

  if (payload.game_key === "3d" && Array.isArray(payload.position_hot)) {
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
    return;
  }

  const grid = document.createElement("div");
  grid.className = "analysis-rank-grid";
  grid.append(
    rankList("热号", payload.hot?.main, "count"),
    rankList("冷号", payload.cold?.main, "count"),
    rankList("遗漏", payload.omission?.main, "missing"),
  );
  if (payload.hot?.special?.length || payload.omission?.special?.length) {
    grid.append(rankList("特别", payload.hot?.special?.length ? payload.hot.special : payload.omission.special, payload.hot?.special?.length ? "count" : "missing", "special"));
  }
  card.append(grid);
}

function renderAnalysisTrend(payload) {
  const card = els.analysisTrend;
  card.replaceChildren();
  analysisCardTitle(card, "走势视图", payload.game_key === "kl8" ? "区间" : "命中");

  if (payload.game_key === "3d" && payload.trend?.position_columns) {
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
  const columns = (payload.trend?.columns || []).slice(0, payload.game_key === "kl8" ? 8 : 12);
  grid.style.setProperty("--trend-columns", String(Math.max(1, columns.length)));
  columns.forEach((column) => {
    const cell = document.createElement("span");
    cell.className = "trend-head";
    cell.textContent = column;
    grid.append(cell);
  });

  (payload.trend?.rows || []).slice(0, 8).forEach((row) => {
    const hits = new Set((row.hits || []).map(analysisNumberLabel));
    columns.forEach((column) => {
      const cell = document.createElement("span");
      cell.className = hits.has(column) || hits.has(Number(column)) ? "trend-hit" : "trend-cell";
      cell.textContent = hits.has(column) || hits.has(Number(column)) ? "●" : "";
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
  const card = els.analysisShape;
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
  const card = els.analysisRecentDraws;
  card.replaceChildren();
  analysisCardTitle(card, "近期开奖", "重合");
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
    tag.textContent = `合 ${overlapWithPrediction(draw)} 个`;
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
  if (!payload || !els.analysisSummary) return;
  state.analysisPayload = payload;
  const gameName = GAME_LABELS[payload.game_key] || currentGameMeta().game_name || "--";
  const summary = payload.summary || {};
  els.analysisSummary.classList.remove("error");
  els.analysisSummary.textContent = `${gameName} · 样本 ${summary.draw_count ?? 0} 期 · 最新 ${summary.latest_issue || "--"} · ${summary.latest_date || "--"}`;
  renderAnalysisHotCold(payload);
  renderAnalysisTrend(payload);
  renderAnalysisShape(payload);
  renderAnalysisDraws(payload);
}

async function loadAnalysis() {
  renderAnalysisWindowTabs();
  renderAnalysisStatus("分析数据加载中。");
  try {
    const payload = state.demoMode
      ? demoAnalysisPayload(state.activeGame)
      : await fetchJson(`/api/analysis/${state.activeGame}?window=${state.analysisWindow}`);
    renderAnalysis(payload);
  } catch (error) {
    if (state.demoMode) {
      renderAnalysis(demoAnalysisPayload(state.activeGame));
      return;
    }
    renderAnalysisStatus("分析数据暂不可用", true);
  }
}

async function fetchJson(url, options = {}) {
  const headers = {
    "X-Lottery-Client-Id": clientId(),
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadGames() {
  try {
    const data = await fetchJson("/api/games");
    state.games = Array.isArray(data.games) && data.games.length ? data.games : DEMO_GAMES;
    state.gameRules = gameRulesFromGames(state.games);
    state.demoMode = false;
    setStatus("娱乐推荐");
  } catch (error) {
    state.games = DEMO_GAMES;
    state.gameRules = DEMO_GAME_RULES;
    state.demoMode = true;
    setStatus("娱乐参考", true);
  }
  renderTabs();
  renderGameMeta();
}

function renderIdlePrediction() {
  state.currentPrediction = { main: [], special: [] };
  resetPlanActions();
  els.oracleBoard?.classList.add("is-idle");
  if (els.predictionResults) {
    els.predictionResults.hidden = true;
    els.predictionResults.classList.remove("is-generating");
  }
  els.fortuneNumber.textContent = "";
  els.bestDate.textContent = "输入生辰，起一盘属于你的号码";
  els.luckScore.textContent = "";
  els.numberBalls.replaceChildren();
  els.drawCount.textContent = "近期走势";
  renderMiniNumbers(els.hotNumbers, [], []);
  els.historyHotText.textContent = "--";
  els.coldNumbers.textContent = "--";
  els.aiState.textContent = "命盘合参";
  els.personalBasis.textContent = "本次暂无运势说明。";
  renderDailyFortuneSign(DEFAULT_DAILY_FORTUNE_SIGN);
  renderRitualSteps(DEFAULT_RITUAL_STEPS, -1);
  renderFortuneHook({});
  renderMasterRitual(null);
  renderCredibilityChain([]);
  renderInterpretationLayers(null);
  renderNumberReasons(null, [], []);
  renderRecentDraws([]);
  els.disclaimer.textContent = "仅供娱乐参考，请理性看待结果。";
  setRitualState("idle", "填写资料后开始起盘", 0);
  setGenerateFeedback("");
}

function validatePredictForm() {
  if (!els.predictForm.reportValidity()) return false;
  const birthHour = String(
    els.predictForm.querySelector('input[name="birth_hour"]')?.value || "",
  ).trim();
  if (!birthHour) {
    setGenerateFeedback("请选择出生时辰后再开始起盘。", true);
    els.predictForm
      .querySelector('[data-select-name="birth_hour"] .custom-select-trigger')
      ?.focus();
    return false;
  }
  return true;
}

function formPayload() {
  const data = new FormData(els.predictForm);
  return {
    game_key: state.activeGame,
    name: String(data.get("name") || "").trim(),
    birth_date: data.get("birth_date"),
    calendar_type: data.get("calendar_type") || "solar",
    fortune_mode: data.get("fortune_mode") || state.activeMode || "steady",
    birth_hour: String(data.get("birth_hour") || "").trim(),
    birth_place: String(data.get("birth_place") || "").trim(),
    current_city: String(data.get("current_city") || "").trim(),
  };
}

function setupFortuneModes() {
  if (!els.fortuneModeOptions) return;
  const input = els.predictForm.querySelector('input[name="fortune_mode"]');
  els.fortuneModeOptions.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button) return;
    state.activeMode = button.dataset.mode || "steady";
    if (input) input.value = state.activeMode;
    Array.from(els.fortuneModeOptions.querySelectorAll("button[data-mode]")).forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    setGenerateFeedback(`已切换为${currentModeLabel()}，点击开始起盘刷新本次合参。`);
  });
}

function readFortuneHistory() {
  try {
    const records = JSON.parse(localStorage.getItem(FORTUNE_HISTORY_KEY) || "[]");
    return Array.isArray(records) ? records : [];
  } catch (error) {
    return [];
  }
}

function writeFortuneHistory(records) {
  localStorage.setItem(FORTUNE_HISTORY_KEY, JSON.stringify(records.slice(0, 12)));
}

function inputSummary(request) {
  const calendar = request.calendar_type === "lunar" ? "阴历" : "阳历";
  const year = String(request.birth_date || "").slice(0, 4) || "未知年";
  const hour = request.birth_hour && request.birth_hour !== "unknown" ? `${request.birth_hour}时` : "时辰未知";
  const city = request.current_city || request.birth_place || "城市未填";
  return `${calendar}${year}年 · ${hour} · ${city}`;
}

function fortuneSignSummary(sign) {
  if (!sign || typeof sign !== "object") return "今日财签待补全";
  const tailText = Array.isArray(sign.lucky_tails) && sign.lucky_tails.length
    ? `宜尾 ${sign.lucky_tails.slice(0, 3).join(" / ")}`
    : "";
  const parts = [
    sign.lucky_hour ? `旺时 ${sign.lucky_hour}` : "",
    sign.direction ? `${sign.direction}财位` : "",
    tailText,
  ].filter(Boolean);
  if (parts.length) return `今日财签 · ${parts.join(" · ")}`;
  return sign.headline || "今日财签待补全";
}

function saveFortuneHistory(payload, request, context = {}) {
  payload = normalizePredictionPayload(payload);
  if (!payload?.numbers) return;
  const gameKey = context.gameKey || payload.game_key || state.activeGame;
  const modeKey = context.modeKey || payload.fortune_mode || state.activeMode;
  const main = payload.numbers.main || [];
  const special = payload.numbers.special || [];
  const fortuneEye = special.length ? special[special.length - 1] : main[main.length - 1];
  const record = {
    id: `${Date.now()}-${gameKey}-${modeKey}`,
    created_at: new Date().toISOString(),
    game_key: gameKey,
    game_label: GAME_LABELS[gameKey] || gameKey,
    mode_label: payload.mode_profile?.label || currentModeLabel(modeKey),
    input_summary: inputSummary(request),
    main_numbers: main,
    special_numbers: special,
    fortune_eye: fortuneEye,
    number_text: [...main, ...special].map(padNumber).join(" "),
    best_draw_date: payload.best_draw_date || "",
    luck_score: payload.luck_score ?? "",
    wealth_pattern: payload.metaphysics_profile?.wealth_pattern || "",
    headline: payload.fortune_hook?.headline || "",
    fortune_report: payload.fortune_report || null,
    master_ritual: payload.master_ritual || null,
    credibility_chain: payload.credibility_chain || [],
    interpretation_layers: payload.interpretation_layers || null,
    metaphysics_profile: payload.metaphysics_profile || null,
    number_reasons: payload.number_reasons || null,
    avoid_numbers: payload.avoid_numbers || [],
    daily_fortune_sign: payload.daily_fortune_sign || null,
    ritual_steps: payload.ritual_steps || [],
    avoid_reasons: payload.avoid_reasons || [],
    storage_state: "local",
    review: { status: "pending", summary: "等待开奖数据更新后复盘。" },
  };
  writeFortuneHistory([record, ...readFortuneHistory()]);
  renderFortuneHistory();
  reviewFortuneHistory();
  return record;
}

function renderFortuneHistory() {
  if (!els.fortuneHistory) return;
  const records = readFortuneHistory();
  if (els.profileCalendarPanel) els.profileCalendarPanel.hidden = !records.length;
  if (els.historyPanel) els.historyPanel.hidden = !records.length;
  els.fortuneHistory.replaceChildren();
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无生成记录。";
    els.fortuneHistory.append(empty);
    renderProfileBook(records);
    renderDailyFortuneCalendar(records);
    return;
  }
  records.slice(0, 6).forEach((record) => {
    const card = document.createElement("article");
    card.className = "fortune-history-card";
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${record.game_label} · ${record.mode_label}`;
    const time = document.createElement("time");
    time.textContent = new Date(record.created_at).toLocaleString("zh-CN", { hour12: false });
    head.append(title, time);
    const storage = document.createElement("small");
    storage.className = "storage-badge local";
    storage.textContent = "本机记录";
    const numbers = document.createElement("p");
    numbers.className = "history-numbers";
    numbers.textContent = record.number_text;
    const meta = document.createElement("span");
    meta.textContent = `${record.input_summary} · ${record.wealth_pattern || "本命财格"} · 财运指数 ${record.luck_score || "--"}`;
    const headline = document.createElement("small");
    headline.textContent = record.headline || "财运合参记录";
    const signSummary = document.createElement("small");
    signSummary.className = "history-sign";
    signSummary.textContent = fortuneSignSummary(record.daily_fortune_sign);
    const review = document.createElement("p");
    review.className = `history-review ${record.review?.status || "pending"}`;
    review.textContent = reviewText(record);
    const actions = document.createElement("div");
    actions.className = "fortune-history-actions";
    const detailLink = document.createElement("a");
    detailLink.href = `./result.html?id=${encodeURIComponent(record.id)}`;
    detailLink.textContent = "查看详情";
    actions.append(detailLink);
    card.append(head, storage, numbers, meta, headline, signSummary, review, actions);
    els.fortuneHistory.append(card);
  });
  renderProfileBook(records);
  renderDailyFortuneCalendar(records);
}

function renderProfileBook(records = readFortuneHistory()) {
  if (!els.profileBook) return;
  els.profileBook.replaceChildren();
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "生成后自动沉淀个人财运档案。";
    els.profileBook.append(empty);
    return;
  }
  const latest = records[0];
  const mostGame = mostFrequent(records.map((record) => record.game_label || GAME_LABELS[record.game_key] || record.game_key));
  const mostPattern = mostFrequent(
    records.map((record) => record.wealth_pattern || record.fortune_report?.wealth_pattern || "").filter(Boolean),
  );
  const reviewedCount = records.filter((record) => record.review?.status === "reviewed").length;
  const latestReview = latest.review?.status === "reviewed"
    ? `最近复盘命中 ${latest.review.hit_count || 0} 个`
    : "最近记录等待开奖复盘";
  const items = [
    ["累计生成", `${records.length} 次`],
    ["常看彩种", mostGame || "--"],
    ["常见财格", mostPattern || latest.wealth_pattern || "--"],
    ["复盘进度", `${reviewedCount}/${records.length} · ${latestReview}`],
  ];
  items.forEach(([label, value]) => {
    const item = document.createElement("div");
    const dt = document.createElement("span");
    dt.textContent = label;
    const dd = document.createElement("strong");
    dd.textContent = value;
    item.append(dt, dd);
    els.profileBook.append(item);
  });
}

function renderDailyFortuneCalendar(records = readFortuneHistory()) {
  if (!els.dailyFortuneCalendar) return;
  els.dailyFortuneCalendar.replaceChildren();
  const latest = records[0];
  const rows = Array.isArray(latest?.fortune_report?.daily_calendar)
    ? latest.fortune_report.daily_calendar
    : [];
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "生成后展示未来开奖日气口。";
    els.dailyFortuneCalendar.append(empty);
    return;
  }
  rows.slice(0, 5).forEach((row) => {
    const item = document.createElement("div");
    item.className = `daily-fortune-item${row.label === "最佳开奖日" ? " best" : ""}`;
    const day = document.createElement("strong");
    day.textContent = row.draw_date || "--";
    const meta = document.createElement("span");
    meta.textContent = `${row.label || "开奖日"} · ${row.day_mode || "守"}财 · ${Math.round(Number(row.score || 0))}`;
    const advice = document.createElement("small");
    advice.textContent = row.advice || "宜先筛后取，忌临时追热。";
    item.append(day, meta, advice);
    els.dailyFortuneCalendar.append(item);
  });
}

function mostFrequent(values) {
  const counts = new Map();
  values.filter(Boolean).forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "";
}

function numbersForReview(record) {
  const main = Array.isArray(record.main_numbers) ? record.main_numbers.map(Number) : [];
  const special = Array.isArray(record.special_numbers) ? record.special_numbers.map(Number) : [];
  if (main.length) {
    return { main, special, fortune_eye: Number(record.fortune_eye ?? special.at(-1) ?? main.at(-1)) };
  }
  const parsed = String(record.number_text || "")
    .split(/[,\s/+，、]+/)
    .map((part) => Number(part))
    .filter((number) => Number.isInteger(number));
  const count = MAIN_COUNTS[record.game_key] || Math.max(0, parsed.length - 1);
  const parsedMain = parsed.slice(0, count);
  const parsedSpecial = parsed.slice(count);
  return {
    main: parsedMain,
    special: parsedSpecial,
    fortune_eye: Number(record.fortune_eye ?? parsedSpecial.at(-1) ?? parsedMain.at(-1)),
  };
}

function reviewText(record) {
  const review = record.review || {};
  if (review.status === "reviewed") {
    const hits = [
      ...(review.main_hits || []),
      ...(review.special_hits || []),
    ].map(padNumber);
    const eye = review.fortune_eye_hit ? "财眼命中" : "财眼未中";
    return `已复盘 · 命中 ${review.hit_count || 0} 个${hits.length ? `（${hits.join(" ")}）` : ""} · ${eye}。${review.summary || ""}`;
  }
  return review.summary || "待复盘 · 等待开奖数据更新。";
}

async function reviewFortuneHistory() {
  const records = readFortuneHistory();
  if (!records.length || state.demoMode) return;
  let changed = false;
  const reviewed = [];
  for (const record of records) {
    const request = numbersForReview(record);
    if (!record.game_key || !request.main.length) {
      reviewed.push(record);
      continue;
    }
    try {
      const payload = await fetchJson(`/api/review/${record.game_key}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      reviewed.push({
        ...record,
        main_numbers: request.main,
        special_numbers: request.special,
        fortune_eye: request.fortune_eye,
        review: payload,
      });
      changed = true;
    } catch (error) {
      reviewed.push(record);
    }
  }
  if (changed) {
    writeFortuneHistory(reviewed);
    renderFortuneHistory();
  }
}

function setupCustomSelects() {
  const selects = Array.from(document.querySelectorAll(".custom-select"));

  function closeAll(except) {
    selects.forEach((select) => {
      if (select === except) return;
      select.classList.remove("open");
      select.querySelector(".custom-select-trigger")?.setAttribute("aria-expanded", "false");
      const menu = select.querySelector(".custom-select-menu");
      if (menu) menu.hidden = true;
    });
  }

  selects.forEach((select) => {
    const fieldName = select.dataset.selectName;
    const trigger = select.querySelector(".custom-select-trigger");
    const triggerText = trigger?.querySelector("span:first-child");
    const menu = select.querySelector(".custom-select-menu");
    const input = fieldName
      ? els.predictForm.querySelector(`input[name="${fieldName}"]`)
      : null;
    const options = Array.from(select.querySelectorAll(".custom-select-option"));

    trigger?.addEventListener("click", () => {
      const willOpen = !select.classList.contains("open");
      closeAll(select);
      select.classList.toggle("open", willOpen);
      trigger.setAttribute("aria-expanded", String(willOpen));
      if (menu) menu.hidden = !willOpen;
    });

    options.forEach((option) => {
      option.setAttribute("aria-selected", String(option.classList.contains("active")));
      option.addEventListener("click", () => {
        options.forEach((item) => {
          item.classList.remove("active");
          item.setAttribute("aria-selected", "false");
        });
        option.classList.add("active");
        option.setAttribute("aria-selected", "true");
        if (input) input.value = option.dataset.value || "";
        if (triggerText) triggerText.textContent = option.textContent.trim();
        closeAll();
        trigger?.focus();
      });
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".custom-select")) closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAll();
  });
}

async function predict({ userInitiated = false } = {}) {
  const runCount = userInitiated ? (state.manualRunCount += 1) : state.manualRunCount;
  const requestPayload = formPayload();
  requestPayload.consume_quota = false;
  state.predictionAbortController?.abort();
  const abortController = new AbortController();
  state.predictionAbortController = abortController;
  const requestContext = {
    requestId: state.predictionRequestId + 1,
    gameKey: state.activeGame,
    modeKey: requestPayload.fortune_mode || state.activeMode || "steady",
    planRequestId: userInitiated ? createPredictionPlanRequestId() : "",
    hadVisibleResults: Boolean(els.predictionResults && !els.predictionResults.hidden),
  };
  state.predictionRequestId = requestContext.requestId;
  resetPlanActions();
  const isLatestRequest = () => (
    state.predictionRequestId === requestContext.requestId
    && state.activeGame === requestContext.gameKey
  );
  const motion = window.FortuneMotion;
  els.submitButton.disabled = true;
  els.submitButton.querySelector("span").textContent = "起盘中";
  if (userInitiated) {
    setGenerateFeedback(`第 ${runCount} 次${currentModeLabel(requestContext.modeKey)}起盘中，正在校准本命财格与开奖日气口...`);
    els.numberBalls.classList.add("is-generating");
    startRitualPreview(isLatestRequest);
    motion?.start({
      ...requestContext,
      steps: DEFAULT_RITUAL_STEPS,
    });
  }
  try {
    const payload = normalizePredictionPayload(await fetchJson("/api/predict", {
      method: "POST",
      headers: window.LotteryAiKey?.withPredictionHeader({
        "Content-Type": "application/json",
      }) || { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
      signal: abortController.signal,
    }));
    if (!isLatestRequest()) return;
    validatePredictionPayload(payload, requestContext.gameKey);
    if (userInitiated) {
      await motion?.resolve(requestContext, payload.numbers);
      if (!isLatestRequest()) return;
      renderRitualSteps(payload.ritual_steps);
      setRitualState("complete", "起盘完成 · 财运号已落盘", 100);
    }
    if (!isLatestRequest()) return;
    renderPrediction(payload);
    if (userInitiated && payload.game_key === "3d") {
      activatePlanDraft(payload, requestContext);
    }
    if (userInitiated) {
      trackPredictionCompleted(payload, requestContext);
    }
    if (!state.demoMode) setStatus("娱乐推荐");
    if (userInitiated) {
      const record = saveFortuneHistory(payload, requestPayload, requestContext);
      if (!isLatestRequest()) return;
      setGenerateFeedback(`第 ${runCount} 次${payload.mode_profile?.label || currentModeLabel(requestContext.modeKey)}已落盘，已保存到本机 · ${currentTimeLabel()}`);
      flashResultPanels(true);
      scrollToResult(true);
    } else if (!state.manualRunCount) {
      setGenerateFeedback("填写资料后点击开始起盘。");
    }
  } catch (error) {
    if (!isLatestRequest()) return;
    resetPlanActions();
    motion?.fail(requestContext, "起盘失败，请稍后重试");
    setRitualState("idle", "本次未能落盘", 0);
    renderRitualSteps(DEFAULT_RITUAL_STEPS, -1);
    if (els.predictionResults) {
      els.predictionResults.classList.remove("is-generating");
      els.predictionResults.hidden = !requestContext.hadVisibleResults;
    }
    setGenerateFeedback("起盘失败，请稍后重试。已保留当前资料和上次结果。", true);
  } finally {
    if (state.predictionAbortController === abortController) {
      state.predictionAbortController = null;
    }
    if (isLatestRequest()) {
      els.submitButton.disabled = false;
      els.numberBalls.classList.remove("is-generating");
      resetSubmitButtonLabel();
    }
  }
}

els.gameTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-game]");
  if (!button) return;
  const nextGame = button.dataset.game;
  if (!nextGame || nextGame === state.activeGame) return;
  state.predictionAbortController?.abort();
  state.predictionAbortController = null;
  state.predictionRequestId += 1;
  window.FortuneMotion?.cancel();
  state.activeGame = nextGame;
  renderTabs();
  renderGameMeta();
  renderIdlePrediction();
  els.submitButton.disabled = false;
  resetSubmitButtonLabel();
});

if (els.analysisWindowTabs) {
  els.analysisWindowTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-window]");
    if (!button) return;
    state.analysisWindow = Number(button.dataset.window) || 30;
    loadAnalysis();
  });
}

els.predictForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!validatePredictForm()) return;
  predict({ userInitiated: true });
});

setupCustomSelects();
setupFortuneModes();
setupAiSettings();
setupPlanSyncListener();
renderFortuneHistory();
els.clearHistoryButton?.addEventListener("click", () => {
  writeFortuneHistory([]);
  renderFortuneHistory();
});
els.savePlanButton?.addEventListener("click", () => {
  saveCurrentPlan();
});
if (hasAnalysisWorkbench()) renderAnalysisWindowTabs();

window.FortuneMotion?.enter();
window.FortuneMotion?.reveal();

loadGames().then(() => {
  renderIdlePrediction();
  reviewFortuneHistory();
});
