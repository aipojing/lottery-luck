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

  it("fails closed without JavaScript and limits header use to prediction", async () => {
    const html = await readFile(path.join(process.cwd(), "..", "web", "index.html"), "utf8");
    const appSource = await readFile(path.join(process.cwd(), "..", "web", "app.js"), "utf8");

    expect(html).toMatch(/<form[^>]+id="aiSettingsForm"[^>]+method="dialog"/);
    expect(html).not.toContain('name="deepseek_api_key"');
    expect(appSource.match(/withPredictionHeader/g)).toHaveLength(1);
    expect(appSource.indexOf('fetchJson("/api/predict"')).toBeLessThan(
      appSource.indexOf("withPredictionHeader"),
    );
  });
});
