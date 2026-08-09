import { readFile } from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

async function loadAiKeyModule() {
  const source = await readFile(path.join(process.cwd(), "..", "web", "ai-key.js"), "utf8");
  const values = new Map<string, string>();
  const storage = {
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      values.set(key, value);
    },
    removeItem(key: string) {
      values.delete(key);
    },
  };
  const context = vm.createContext({ localStorage: storage });
  vm.runInContext(source, context);
  return { api: context.LotteryAiKey, storage, values };
}

describe("user DeepSeek API key", () => {
  it("stores a trimmed key locally and adds it only to prediction headers", async () => {
    const { api, storage } = await loadAiKeyModule();

    expect(api.save("  sk-user-key  ", storage)).toBe("sk-user-key");
    expect(api.read(storage)).toBe("sk-user-key");
    expect(api.withPredictionHeader({ "Content-Type": "application/json" }, storage)).toEqual({
      "Content-Type": "application/json",
      "X-DeepSeek-Api-Key": "sk-user-key",
    });
  });

  it("omits the header when no key exists and can clear a saved key", async () => {
    const { api, storage } = await loadAiKeyModule();

    expect(api.withPredictionHeader({ Accept: "application/json" }, storage)).toEqual({
      Accept: "application/json",
    });
    api.save("sk-user-key", storage);
    api.clear(storage);
    expect(api.read(storage)).toBe("");
  });

  it("rejects blank and oversized values", async () => {
    const { api, storage } = await loadAiKeyModule();

    expect(() => api.save("   ", storage)).toThrow(/不能为空/);
    expect(() => api.save("s".repeat(513), storage)).toThrow(/过长/);
  });

  it("can validate a key without storing it", async () => {
    const { api, storage } = await loadAiKeyModule();

    expect(api.prepare("  sk-candidate  ")).toBe("sk-candidate");
    expect(api.read(storage)).toBe("");
  });

  it("fails closed without JavaScript and limits header use to prediction", async () => {
    const html = await readFile(path.join(process.cwd(), "..", "web", "index.html"), "utf8");
    const appSource = await readFile(path.join(process.cwd(), "..", "web", "app.js"), "utf8");

    expect(html).toMatch(/<form[^>]+id="aiSettingsForm"[^>]+method="dialog"/);
    expect(html).not.toContain('name="deepseek_api_key"');
    expect(appSource).toContain('fetchJson("/api/ai/validate"');
    expect(appSource.match(/withPredictionHeader/g)).toHaveLength(1);
    expect(appSource.indexOf('fetchJson("/api/predict"')).toBeLessThan(
      appSource.indexOf("withPredictionHeader"),
    );
    expect(appSource.indexOf('fetchJson("/api/ai/validate"')).toBeLessThan(
      appSource.indexOf("LotteryAiKey.save"),
    );
  });

  it("opens AI settings before validating or starting a prediction when no key exists", async () => {
    const appSource = await readFile(path.join(process.cwd(), "..", "web", "app.js"), "utf8");
    const submitHandler = appSource.slice(
      appSource.indexOf('els.predictForm.addEventListener("submit"'),
      appSource.indexOf("setupCustomSelects();"),
    );

    expect(submitHandler).toContain("if (!requireAiConfiguration()) return;");
    expect(submitHandler.indexOf("requireAiConfiguration")).toBeLessThan(
      submitHandler.indexOf("validatePredictForm"),
    );
    expect(appSource).toMatch(
      /els\.submitButton\?\.addEventListener\("click",[\s\S]*?requireAiConfiguration\(\)[\s\S]*?event\.preventDefault\(\)/,
    );
    expect(appSource).toMatch(
      /function requireAiConfiguration\(\)[\s\S]*?LotteryAiKey\?\.read\(\)[\s\S]*?openAiSettings\(/,
    );
  });
});
