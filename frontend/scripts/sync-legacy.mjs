import { execFile } from "node:child_process";
import { copyFile, lstat, mkdir, realpath, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

function isInside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === "" || (relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function assertSafeWebPath(filePath) {
  if (!filePath.startsWith("web/")) {
    throw new Error(`Refusing to sync non-web path: ${filePath}`);
  }

  const relativePath = filePath.slice("web/".length);
  if (!relativePath || relativePath.split("/").includes("..") || path.isAbsolute(relativePath)) {
    throw new Error(`Refusing to sync unsafe web path: ${filePath}`);
  }

  return relativePath;
}

async function trackedWebFiles(repoRoot) {
  const { stdout } = await execFileAsync("git", ["-C", repoRoot, "ls-files", "-z", "--", "web"]);
  return stdout.split("\0").filter(Boolean);
}

async function assertSafeSource(sourcePath, webRoot, trackedPath) {
  const sourceStat = await lstat(sourcePath);
  if (!sourceStat.isSymbolicLink()) {
    return;
  }

  const resolvedPath = await realpath(sourcePath);
  if (!isInside(webRoot, resolvedPath)) {
    throw new Error(`Unsafe symlink leaves web/: ${trackedPath}`);
  }
}

export async function syncLegacy(repoRoot = path.resolve(fileURLToPath(new URL("../../", import.meta.url)))) {
  const webRoot = path.join(repoRoot, "web");
  const publicRoot = path.join(repoRoot, "frontend", "public");
  const trackedFiles = await trackedWebFiles(repoRoot);
  const copyJobs = [];

  for (const trackedPath of trackedFiles) {
    const relativePath = assertSafeWebPath(trackedPath);
    const sourcePath = path.join(repoRoot, trackedPath);
    await assertSafeSource(sourcePath, webRoot, trackedPath);
    copyJobs.push({
      sourcePath,
      destinationPath: path.join(publicRoot, relativePath),
    });
  }

  await rm(publicRoot, { force: true, recursive: true });
  await mkdir(publicRoot, { recursive: true });

  for (const { sourcePath, destinationPath } of copyJobs) {
    await mkdir(path.dirname(destinationPath), { recursive: true });
    await copyFile(sourcePath, destinationPath);
  }

  return copyJobs.map(({ destinationPath }) => path.relative(publicRoot, destinationPath).split(path.sep).join("/"));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const copiedFiles = await syncLegacy();
  console.log(`Synced ${copiedFiles.length} tracked web files to frontend/public.`);
}
