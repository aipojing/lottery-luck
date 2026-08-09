(function exposeUserAiKey(global) {
  const STORAGE_KEY = "lotteryLuck.deepseekApiKey.v1";
  const MAX_LENGTH = 512;

  function targetStorage(storage) {
    return storage || global.localStorage;
  }

  function normalize(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function prepare(value) {
    const apiKey = normalize(value);
    if (!apiKey) throw new Error("API Key 不能为空");
    if (apiKey.length > MAX_LENGTH) throw new Error("API Key 过长");
    return apiKey;
  }

  function read(storage) {
    try {
      return normalize(targetStorage(storage).getItem(STORAGE_KEY));
    } catch (error) {
      return "";
    }
  }

  function save(value, storage) {
    const apiKey = prepare(value);
    targetStorage(storage).setItem(STORAGE_KEY, apiKey);
    return apiKey;
  }

  function clear(storage) {
    targetStorage(storage).removeItem(STORAGE_KEY);
  }

  function withPredictionHeader(headers = {}, storage) {
    const apiKey = read(storage);
    if (!apiKey) return { ...headers };
    return { ...headers, "X-DeepSeek-Api-Key": apiKey };
  }

  global.LotteryAiKey = Object.freeze({
    STORAGE_KEY,
    MAX_LENGTH,
    prepare,
    read,
    save,
    clear,
    withPredictionHeader,
  });
})(globalThis);
