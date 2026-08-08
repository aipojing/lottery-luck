(() => {
  "use strict";

  const PRODUCT_CLIENT_VERSION = "20260713-product-client-v2";
  const INSTALL_SENTINEL = "__LotteryProductClient_20260713_product_client_v2__";
  const CLIENT_ID_KEY = "lotteryLuck.clientId.v1";
  const PENDING_PLANS_KEY = "lotteryLuck.pendingPlans.v1";
  const PLAN_SYNC_EVENT = "lotteryproduct:plansync";
  const MAX_PENDING_PLANS = 20;
  const SAFE_PLAN_TITLES = {
    fortune: "首页财运号",
    manual: "手动选号",
    filter: "筛选方案",
    random: "随机选号",
    carried: "沿用方案",
  };
  const REQUIRED_API_METHODS = [
    "clientId",
    "request",
    "track",
    "createPlan",
    "listPlans",
    "getPlan",
    "updatePlan",
    "deletePlan",
    "reviewPlan",
    "carryForward",
    "flushPendingPlans",
    "pendingPlans",
    "removePendingPlan",
    "retryPendingPlan",
  ];
  const SOURCE_TYPES = new Set(["fortune", "manual", "filter", "random", "carried"]);
  const GROUP_TYPES = new Set(["豹子", "组三", "组六"]);

  const installedClient = window[INSTALL_SENTINEL];
  if (
    installedClient?.version === PRODUCT_CLIENT_VERSION &&
    isCompatibleApi(installedClient.api)
  ) {
    return;
  }

  let memoryClientId = "";
  let pendingQueue = loadPendingQueue();
  let flushPromise = null;

  function isCompatibleApi(api) {
    return (
    api?.version === PRODUCT_CLIENT_VERSION &&
      Object.isFrozen(api) &&
      REQUIRED_API_METHODS.every((method) => typeof api[method] === "function")
    );
  }

  function cloneJson(value) {
    if (value === undefined) return undefined;
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (error) {
      return undefined;
    }
  }

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function copyText(value, minLength, maxLength) {
    if (typeof value !== "string") return undefined;
    const text = value.trim();
    if (text.length < minLength || text.length > maxLength) return undefined;
    return text;
  }

  function copyIsoDate(value) {
    const text = copyText(value, 10, 10);
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text || "");
    if (!match) return undefined;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (
      date.getUTCFullYear() !== year ||
      date.getUTCMonth() !== month - 1 ||
      date.getUTCDate() !== day
    ) {
      return undefined;
    }
    return text;
  }

  function copyEnum(value, allowed) {
    const text = typeof value === "string" ? value.trim() : "";
    return text && allowed.has(text) ? text : undefined;
  }

  function copyInteger(value, min, max) {
    return Number.isInteger(value) && value >= min && value <= max
      ? value
      : undefined;
  }

  function copyString(value) {
    if (value === undefined || value === null) return undefined;
    return String(value);
  }

  function copyDigitArray(value) {
    if (!Array.isArray(value) || value.length !== 3) return undefined;
    return value.every((item) => Number.isInteger(item) && item >= 0 && item <= 9)
      ? value.slice()
      : undefined;
  }

  function copyIntegerArray(value, min, max) {
    if (!Array.isArray(value)) return undefined;
    const result = [];
    for (const item of value) {
      if (
        Number.isInteger(item) &&
        item >= min &&
        item <= max
      ) {
        if (!result.includes(item)) result.push(item);
      } else {
        return undefined;
      }
    }
    return result.sort((a, b) => a - b);
  }

  function copyTypeArray(value) {
    if (!Array.isArray(value)) return undefined;
    const result = [];
    value.forEach((item) => {
      if (GROUP_TYPES.has(item) && !result.includes(item)) result.push(item);
    });
    return result.length === value.length ? result : undefined;
  }

  function copyPositionMap(value) {
    if (!isPlainObject(value)) return undefined;
    const result = {};
    const positions = Object.keys(value);
    if (!positions.every((position) => ["0", "1", "2"].includes(position))) {
      return undefined;
    }
    positions.forEach((position) => {
      const digits = copyIntegerArray(value[position], 0, 9);
      if (digits === undefined || digits.length !== value[position].length) {
        return;
      }
      result[position] = digits;
    });
    return Object.keys(result).length === positions.length ? result : undefined;
  }

  function copyRatio(value, parts) {
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) return undefined;
    const numbers = text.split(":").map((item) => Number(item));
    if (numbers.length !== parts) return undefined;
    return numbers.every((item) => Number.isInteger(item) && item >= 0 && item <= 3) &&
      numbers.reduce((total, item) => total + item, 0) === 3
      ? text
      : undefined;
  }

  function copyPairArray(value) {
    if (!Array.isArray(value)) return undefined;
    const result = value.map((pair) => {
      return (
        Array.isArray(pair) &&
        pair.length === 2 &&
        pair.every((item) => Number.isInteger(item) && item >= 0 && item <= 9)
      )
        ? [pair[0], pair[1]]
        : undefined;
    });
    return result.every((pair) => pair !== undefined) ? result : undefined;
  }

  function sanitizeEntries(entries) {
    if (!Array.isArray(entries) || entries.length < 1 || entries.length > 50) {
      return undefined;
    }
    const seenPositions = new Set();
    const result = [];
    for (const [index, entry] of entries.entries()) {
      if (!isPlainObject(entry)) return undefined;
      const item = {
        position: entry.position === undefined ? index : entry.position,
        main_numbers: copyDigitArray(entry.main_numbers),
        special_numbers: [],
        note: "",
      };
      if (
        !Number.isInteger(item.position) ||
        item.position < 0 ||
        item.position > 49 ||
        seenPositions.has(item.position) ||
        !item.main_numbers ||
        (entry.special_numbers !== undefined &&
          (!Array.isArray(entry.special_numbers) || entry.special_numbers.length !== 0))
      ) {
        return undefined;
      }
      seenPositions.add(item.position);
      result.push(item);
    }
    return result;
  }

  function sanitizeConditions(conditions) {
    const source = isPlainObject(conditions) ? conditions : {};
    const sanitized = {};
    [
      ["sum_min", 0, 27],
      ["sum_max", 0, 27],
      ["span_min", 0, 9],
      ["span_max", 0, 9],
      ["max_results", 1, 200],
    ].forEach(([key, min, max]) => {
      if (!(key in source)) return;
      const value = copyInteger(source[key], min, max);
      if (value === undefined) sanitized.__invalid = true;
      else sanitized[key] = value;
    });
    [
      ["types", copyTypeArray],
      ["odd_counts", (value) => copyIntegerArray(value, 0, 3)],
      ["big_counts", (value) => copyIntegerArray(value, 0, 3)],
      ["position_include", copyPositionMap],
      ["position_exclude", copyPositionMap],
    ].forEach(([key, copier]) => {
      if (!(key in source)) return;
      const value = copier(source[key]);
      if (value !== undefined) sanitized[key] = value;
      else sanitized.__invalid = true;
    });
    if (sanitized.__invalid) return undefined;
    return sanitized;
  }

  function sanitizeMetrics(metrics) {
    const source = isPlainObject(metrics) ? metrics : {};
    const sanitized = {};
    [
      ["sum", 0, 27],
      ["sum_tail", 0, 9],
      ["span", 0, 9],
      ["repeat_count", 0, 2],
    ].forEach(([key, min, max]) => {
      if (!(key in source)) return;
      const value = copyInteger(source[key], min, max);
      if (value === undefined) sanitized.__invalid = true;
      else sanitized[key] = value;
    });
    [
      ["group_type", (value) => copyEnum(value, GROUP_TYPES)],
      ["odd_even", (value) => copyRatio(value, 2)],
      ["big_small", (value) => copyRatio(value, 2)],
      ["mod3", (value) => copyRatio(value, 3)],
      ["prime_composite", (value) => copyRatio(value, 2)],
      ["consecutive_pairs", copyPairArray],
      ["adjacent_pairs", copyPairArray],
    ].forEach(([key, copier]) => {
      if (!(key in source)) return;
      const value = copier(source[key]);
      if (value !== undefined) sanitized[key] = value;
      else sanitized.__invalid = true;
    });
    if (sanitized.__invalid) return undefined;
    return sanitized;
  }

  function sanitizeSnapshot(snapshot) {
    if (!isPlainObject(snapshot)) return undefined;
    const latestIssue = copyText(snapshot.latest_data_issue, 1, 32);
    const latestDate = copyIsoDate(snapshot.latest_data_date);
    const mode = copyEnum(snapshot.mode, new Set(["simple", "pro"]));
    const conditions = sanitizeConditions(snapshot.conditions);
    const metrics = sanitizeMetrics(snapshot.metrics);
    if (
      !latestIssue ||
      !latestDate ||
      !mode ||
      ![30, 60, 120].includes(snapshot.analysis_window) ||
      !conditions ||
      !metrics
    ) {
      return undefined;
    }
    const sanitized = {
      mode,
      analysis_window: snapshot.analysis_window,
      latest_data_issue: latestIssue,
      latest_data_date: latestDate,
      conditions,
      metrics,
    };
    return sanitized;
  }

  function sanitizeQueueMetadata(source, target) {
    const status = copyEnum(source.status, new Set(["blocked", "retryable"]));
    if (status === "blocked") {
      target.blocked = true;
      target.status = "blocked";
    } else if (status === "retryable") {
      target.blocked = false;
      target.status = "retryable";
    }
    const error = copyString(source.last_error)?.trim();
    if (/^HTTP [45][0-9]{2}$/.test(error || "") || error === "network error") {
      target.last_error = error;
    }
  }

  function sanitizePlanPayload(payload, options = {}) {
    if (!payload || typeof payload !== "object") return null;

    const gameKey = copyEnum(payload.game_key, new Set(["3d"]));
    const targetIssue = copyText(payload.target_issue, 1, 32);
    const targetDrawDate = copyIsoDate(payload.target_draw_date);
    const requestId = copyText(payload.request_id, 1, 96);
    const sourceType = copyEnum(payload.source_type, SOURCE_TYPES);
    const entries = sanitizeEntries(payload.entries);
    const snapshot = sanitizeSnapshot(payload.condition_snapshot);
    if (
      !gameKey ||
      !targetIssue ||
      !targetDrawDate ||
      !sourceType ||
      !requestId ||
      !entries?.length ||
      !snapshot
    ) {
      return null;
    }

    const sanitized = {};
    sanitized.game_key = gameKey;
    sanitized.target_issue = targetIssue;
    sanitized.target_draw_date = targetDrawDate;
    sanitized.source_type = sourceType;
    sanitized.request_id = requestId;
    sanitized.title = SAFE_PLAN_TITLES[sourceType];
    sanitized.entries = entries;
    sanitized.condition_snapshot = snapshot;
    if (options.includeMetadata) sanitizeQueueMetadata(payload, sanitized);
    return cloneJson(sanitized);
  }

  function isReasonableClientId(value) {
    return /^[A-Za-z0-9._:-]{8,128}$/.test(value);
  }

  function existingClientId() {
    try {
      const stored = window.localStorage.getItem(CLIENT_ID_KEY);
      const trimmed = typeof stored === "string" ? stored.trim() : "";
      return isReasonableClientId(trimmed) ? trimmed : "";
    } catch (error) {
      return "";
    }
  }

  function uuidFromRandomValues() {
    const cryptoApi = window.crypto;
    if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
    if (cryptoApi?.getRandomValues) {
      const bytes = new Uint8Array(16);
      cryptoApi.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (byte) =>
        byte.toString(16).padStart(2, "0"),
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join(""),
      ].join("-");
    }
    return `client-${Date.now().toString(36)}-${performance.now().toString(36)}`;
  }

  function clientId() {
    if (memoryClientId) return memoryClientId;
    const stored = existingClientId();
    if (stored) {
      memoryClientId = stored;
      return memoryClientId;
    }

    memoryClientId = uuidFromRandomValues();
    try {
      window.localStorage.setItem(CLIENT_ID_KEY, memoryClientId);
    } catch (error) {
      // Memory id is enough for the current page when storage is blocked.
    }
    return memoryClientId;
  }

  function loadPendingQueue() {
    let raw = "";
    try {
      raw = window.localStorage.getItem(PENDING_PLANS_KEY) || "";
    } catch (error) {
      return [];
    }
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      const seen = new Set();
      const queue = parsed
        .map((item) => sanitizePlanPayload(item, { includeMetadata: true }))
        .filter((item) => {
          const requestId = item?.request_id?.trim();
          if (!requestId || seen.has(requestId)) return false;
          item.request_id = requestId;
          seen.add(requestId);
          return true;
        });
      persistQueue(queue);
      return queue;
    } catch (error) {
      try {
        window.localStorage.setItem(PENDING_PLANS_KEY, "[]");
      } catch (storageError) {
        // Corrupt storage should never block the page.
      }
      return [];
    }
  }

  function persistQueue(queue) {
    try {
      window.localStorage.setItem(PENDING_PLANS_KEY, JSON.stringify(queue));
      return true;
    } catch (error) {
      return false;
    }
  }

  function persistPendingQueue() {
    return persistQueue(pendingQueue);
  }

  function enqueuePendingPlan(payload) {
    const sanitized = sanitizePlanPayload(payload);
    const requestId = sanitized?.request_id?.trim();
    if (!sanitized || !requestId) {
      return { queued: false, persisted: false };
    }
    sanitized.request_id = requestId;
    const exists = pendingQueue.some((item) => item.request_id === requestId);
    if (!exists) {
      pendingQueue.push(sanitized);
      while (pendingQueue.length > MAX_PENDING_PLANS) pendingQueue.shift();
    }
    return { queued: true, persisted: persistPendingQueue() };
  }

  function isJsonBody(body) {
    if (!body || typeof body !== "object") return false;
    return !(
      body instanceof FormData ||
      body instanceof Blob ||
      body instanceof ArrayBuffer ||
      body instanceof URLSearchParams
    );
  }

  function sameOriginPath(path) {
    const url = new URL(path, window.location.origin);
    if (url.origin !== window.location.origin) {
      throw new Error("LotteryProduct only supports same-origin requests");
    }
    return `${url.pathname}${url.search}${url.hash}`;
  }

  async function parseJsonSafely(response) {
    const text = await response.text().catch(() => "");
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch (error) {
      return {};
    }
  }

  function networkError(original) {
    const error = new Error("Network request failed");
    error.network = true;
    error.detail = "network error";
    error.cause = original;
    return error;
  }

  function invalidPlanError() {
    const error = new Error("invalid plan");
    error.status = 422;
    error.detail = "invalid plan";
    error.pending = false;
    error.persistedLocally = false;
    return error;
  }

  function httpError(response, payload) {
    const detail = typeof payload?.detail === "string"
      ? payload.detail
      : "Request failed";
    const error = new Error(detail);
    error.status = response.status;
    error.detail = detail;
    error.payload = payload && typeof payload === "object" ? payload : {};
    return error;
  }

  async function requestWithStatus(path, options = {}) {
    const init = { ...options };
    const headers = new Headers(options.headers || {});
    delete init.headers;

    if (options.body !== undefined && options.body !== null) {
      if (isJsonBody(options.body)) {
        init.body = JSON.stringify(options.body);
        if (!headers.has("Content-Type")) {
          headers.set("Content-Type", "application/json");
        }
      } else {
        init.body = options.body;
      }
    } else {
      delete init.body;
    }
    headers.set("X-Lottery-Client-Id", clientId());
    init.headers = headers;

    let response;
    try {
      response = await window.fetch(sameOriginPath(path), init);
    } catch (error) {
      if (error instanceof TypeError) throw networkError(error);
      throw error;
    }

    if (response.status === 204) return {};
    const payload = await parseJsonSafely(response);
    if (!response.ok) throw httpError(response, payload);
    return {
      payload: payload && typeof payload === "object" ? payload : {},
      status: response.status,
    };
  }

  async function request(path, options = {}) {
    const result = await requestWithStatus(path, options);
    if (result === undefined || result === null) return {};
    if (!("payload" in result)) return {};
    return result.payload && typeof result.payload === "object" ? result.payload : {};
  }

  function planSyncDetail(requestId, status, options = {}) {
    const id = copyText(options.planId, 1, 128);
    const detail = {
      request_id: String(requestId || "").trim(),
      status,
    };
    if (id && status === "saved") detail.plan = { id };
    if (Number.isInteger(options.httpStatus)) detail.http_status = options.httpStatus;
    return detail;
  }

  function dispatchPlanSync(detail) {
    try {
      window.dispatchEvent(new CustomEvent(PLAN_SYNC_EVENT, { detail }));
    } catch (error) {
      // Sync events are advisory; queue state remains the source of truth.
    }
  }

  function savedPlanId(payload) {
    if (isPlainObject(payload?.plan)) return copyText(payload.plan.id, 1, 128) || "";
    return copyText(payload?.id, 1, 128) || "";
  }

  function syncErrorStatus(error) {
    return isBlockedFlushError(error) ? "blocked" : "retryable";
  }

  async function postPlanForFlush(payload) {
    return requestWithStatus("/api/plans", {
      method: "POST",
      body: payload,
    });
  }

  async function track(eventName, properties = {}) {
    try {
      await request("/api/events", {
        method: "POST",
        keepalive: true,
        body: { event_name: eventName, properties },
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  async function createPlan(payload) {
    const canonical = sanitizePlanPayload(payload);
    if (!canonical) throw invalidPlanError();
    try {
      return await request("/api/plans", {
        method: "POST",
        body: canonical,
      });
    } catch (error) {
      if (error.network === true) {
        const queued = enqueuePendingPlan(canonical);
        const pendingError = new Error(
          queued.persisted
            ? "计划已进入待同步队列，网络恢复后会再次保存。"
            : "计划尚未保存，请保持本页打开并稍后重试。",
        );
        pendingError.network = true;
        pendingError.pending = queued.queued === true;
        pendingError.persistedLocally = queued.persisted === true;
        throw pendingError;
      }
      throw error;
    }
  }

  function listPlans() {
    return request("/api/plans");
  }

  function getPlan(id) {
    return request(`/api/plans/${encodeURIComponent(id)}`);
  }

  function updatePlan(id, payload) {
    return request(`/api/plans/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: payload,
    });
  }

  function deletePlan(id) {
    return request(`/api/plans/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  function reviewPlan(id) {
    return request(`/api/plans/${encodeURIComponent(id)}/review`, {
      method: "POST",
    });
  }

  function carryForward(id, requestId) {
    const options = { method: "POST" };
    if (requestId !== undefined && requestId !== null && String(requestId).trim()) {
      options.body = { request_id: String(requestId) };
    }
    return request(`/api/plans/${encodeURIComponent(id)}/carry-forward`, options);
  }

  function pendingPlans() {
    return cloneJson(pendingQueue) || [];
  }

  function normalizedRequestId(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function removePendingPlan(requestId) {
    const target = normalizedRequestId(requestId);
    if (!target) return false;
    const before = pendingQueue.length;
    pendingQueue = pendingQueue.filter((item) => item.request_id !== target);
    if (pendingQueue.length === before) return false;
    persistPendingQueue();
    return true;
  }

  function retryPendingPlan(requestId) {
    const target = normalizedRequestId(requestId);
    if (!target) return false;
    const item = pendingQueue.find((entry) => entry.request_id === target);
    if (!item) return false;
    item.blocked = false;
    item.status = "retryable";
    delete item.last_error;
    persistPendingQueue();
    return true;
  }

  function payloadForFlush(item) {
    const payload = sanitizePlanPayload(item);
    if (payload) delete payload.last_error;
    return payload;
  }

  function flushErrorMessage(error) {
    if (error?.status) return `HTTP ${error.status}`;
    if (error?.network) return "network error";
    return "flush failed";
  }

  function isBlockedFlushError(error) {
    return Number.isInteger(error?.status) && error.status >= 400 && error.status < 500;
  }

  function flushPendingPlans() {
    if (flushPromise) return flushPromise;

    const promise = (async () => {
      let flushed = 0;
      let stopped = false;
      const results = [];
      let index = 0;
      while (index < pendingQueue.length) {
        if (pendingQueue[index]?.blocked === true || pendingQueue[index]?.status === "blocked") {
          index += 1;
          continue;
        }
        const payload = payloadForFlush(pendingQueue[index]);
        if (!payload?.request_id) {
          pendingQueue.splice(index, 1);
          persistPendingQueue();
          continue;
        }
        try {
          const response = await postPlanForFlush(payload);
          const detail = planSyncDetail(payload.request_id, "saved", {
            planId: savedPlanId(response.payload),
            httpStatus: response.status,
          });
          pendingQueue.splice(index, 1);
          flushed += 1;
          persistPendingQueue();
          results.push(detail);
          dispatchPlanSync(detail);
        } catch (error) {
          const blocked = isBlockedFlushError(error);
          const detail = planSyncDetail(payload.request_id, syncErrorStatus(error), {
            httpStatus: Number.isInteger(error?.status) ? error.status : undefined,
          });
          pendingQueue[index] = {
            ...pendingQueue[index],
            blocked,
            status: blocked ? "blocked" : "retryable",
            last_error: flushErrorMessage(error),
          };
          persistPendingQueue();
          results.push(detail);
          dispatchPlanSync(detail);
          if (blocked) {
            index += 1;
          } else {
            stopped = true;
            break;
          }
        }
      }
      return { flushed, remaining: pendingQueue.length, stopped, results };
    })();

    flushPromise = promise;
    promise.finally(() => {
      if (flushPromise === promise) flushPromise = null;
    });
    return promise;
  }

  window.addEventListener("online", () => {
    flushPendingPlans().catch(() => {});
  });

  const api = Object.freeze({
    version: PRODUCT_CLIENT_VERSION,
    clientId,
    request,
    track,
    createPlan,
    listPlans,
    getPlan,
    updatePlan,
    deletePlan,
    reviewPlan,
    carryForward,
    flushPendingPlans,
    pendingPlans,
    removePendingPlan,
    retryPendingPlan,
  });
  const sentinel = Object.freeze({ version: PRODUCT_CLIENT_VERSION, api });
  try {
    Object.defineProperty(window, INSTALL_SENTINEL, {
      value: sentinel,
      configurable: false,
      writable: false,
    });
  } catch (error) {
    window[INSTALL_SENTINEL] = sentinel;
  }
  try {
    Object.defineProperty(window, "LotteryProduct", {
      value: api,
      configurable: false,
      writable: false,
    });
  } catch (error) {
    window.LotteryProduct = api;
  }
})();
