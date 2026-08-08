import { mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";

import { syncLegacy } from "../scripts/sync-legacy.mjs";

async function makeRepo() {
  const root = await mkdtemp(path.join(os.tmpdir(), "legacy-sync-"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  return root;
}

function gitAdd(root: string, ...files: string[]) {
  execFileSync("git", ["add", "--", ...files], { cwd: root });
}

describe("legacy static sync", () => {
  it("copies only tracked web files and removes stale generated files", async () => {
    const root = await makeRepo();
    execFileSync("mkdir", ["-p", "web/assets", "frontend/public"], { cwd: root });
    await writeFile(path.join(root, "web", "index.html"), "<main>canonical</main>");
    await writeFile(path.join(root, "web", "assets", "style.css"), "body{}");
    await writeFile(path.join(root, "web", "draft.html"), "untracked");
    await writeFile(path.join(root, "frontend", "public", "stale.txt"), "old");
    gitAdd(root, "web/index.html", "web/assets/style.css");

    await syncLegacy(root);

    await expect(readFile(path.join(root, "frontend", "public", "index.html"), "utf8")).resolves.toBe(
      "<main>canonical</main>",
    );
    await expect(readFile(path.join(root, "frontend", "public", "assets", "style.css"), "utf8")).resolves.toBe(
      "body{}",
    );
    await expect(readFile(path.join(root, "frontend", "public", "draft.html"), "utf8")).rejects.toThrow();
    await expect(readFile(path.join(root, "frontend", "public", "stale.txt"), "utf8")).rejects.toThrow();
  });

  it("rejects tracked symlinks that resolve outside web", async () => {
    const root = await makeRepo();
    execFileSync("mkdir", ["-p", "web"], { cwd: root });
    await writeFile(path.join(root, "outside.txt"), "secret");
    await symlink(path.join(root, "outside.txt"), path.join(root, "web", "escape.txt"));
    gitAdd(root, "web/escape.txt");

    await expect(syncLegacy(root)).rejects.toThrow(/Unsafe symlink/);
  });
});
