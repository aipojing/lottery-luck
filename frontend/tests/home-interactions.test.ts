import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("home form interactions", () => {
  it("keeps oversized oracle decorations out of pointer hit testing", async () => {
    const css = await readFile(path.join(process.cwd(), "..", "web", "styles.css"), "utf8");

      expect(css).toMatch(
        /\.oracle-board::before,\s*\.oracle-board::after\s*\{[\s\S]*?pointer-events:\s*none;/,
      );
  });
});
