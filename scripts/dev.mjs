#!/usr/bin/env node
/**
 * Cross-platform local dev runner.
 * Reads the root .env, starts the API on API_PORT and Next.js on WEB_PORT.
 * Usage: node scripts/dev.mjs
 */
import { execFileSync, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const envPath = join(root, ".env");

if (existsSync(envPath)) {
  for (const rawLine of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    const value = line
      .slice(index + 1)
      .trim()
      .replace(/^["']|["']$/g, "");
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}

const apiPort = process.env.API_PORT || "8000";
const webPort = process.env.WEB_PORT || "3000";
const apiHost = process.env.API_HOST || "127.0.0.1";
const backend = join(root, "backend");
const frontend = join(root, "frontend");

const python = [
  join(backend, ".venv", "Scripts", "python.exe"),
  join(backend, ".venv", "bin", "python"),
].find(existsSync);

if (!python) {
  console.error(
    "Backend virtualenv not found. Create it first:\n" +
      "  cd backend\n" +
      "  python -m venv .venv\n" +
      "  ./.venv/Scripts/pip install -r requirements.txt   (Windows)\n" +
      "  .venv/bin/pip install -r requirements.txt         (macOS/Linux)",
  );
  process.exit(1);
}

if (!existsSync(join(frontend, "node_modules"))) {
  console.error("Frontend dependencies missing. Run: cd frontend && npm install");
  process.exit(1);
}

console.log(`FireClip API: http://${apiHost}:${apiPort}`);
console.log(`FireClip web: http://localhost:${webPort}`);
console.log("Press Ctrl+C to stop both.\n");

let stopping = false;
const api = spawn(python, ["-m", "app"], {
  cwd: backend,
  env: { ...process.env, API_HOST: apiHost, API_PORT: apiPort },
  stdio: "inherit",
});

const npm = process.platform === "win32" ? process.env.ComSpec || "cmd.exe" : "npm";
const webArgs =
  process.platform === "win32"
    ? ["/d", "/s", "/c", `npm run dev -- -p ${webPort}`]
    : ["run", "dev", "--", "-p", webPort];
const web = spawn(npm, webArgs, {
  cwd: frontend,
  env: { ...process.env, API_BASE_URL: `http://${apiHost}:${apiPort}` },
  stdio: "inherit",
});

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of [api, web]) {
    try {
      if (process.platform === "win32" && child.pid) {
        execFileSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
      } else {
        child.kill("SIGTERM");
      }
    } catch {
      /* already stopped */
    }
  }
  process.exit(code);
}

api.on("exit", (code) => {
  if (!stopping) {
    console.error(`API exited with code ${code ?? 1}`);
    stop(code ?? 1);
  }
});
web.on("exit", (code) => {
  if (!stopping) {
    console.error(`Web exited with code ${code ?? 1}`);
    stop(code ?? 1);
  }
});
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
