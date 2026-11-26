// Startup connectivity report for the internal API.
// Next.js bakes API_BASE_URL into its /api and /health rewrites at build time,
// so a hostname that is wrong (or shadowed by another container) turns every
// API call into a 500 with "Failed to proxy ... ECONNREFUSED". Print what this
// container can actually resolve and reach, once, before the server starts.
import { lookup } from "node:dns/promises";
import { networkInterfaces } from "node:os";

const base = process.env.API_BASE_URL || "http://127.0.0.1:8000";

const note = (message) => console.log(`[web] ${message}`);

const own = Object.values(networkInterfaces())
  .flat()
  .filter((entry) => entry && entry.family === "IPv4" && !entry.internal)
  .map((entry) => entry.address);
note(`web container addresses: ${own.join(", ") || "none"}`);

let target;
try {
  target = new URL(base);
} catch {
  note(`API_BASE_URL is not a valid URL: ${base}`);
  process.exit(0);
}

try {
  const addresses = await lookup(target.hostname, { all: true });
  note(`API ${base} resolves to ${addresses.map((entry) => entry.address).join(", ")}`);
} catch (error) {
  note(`API ${base} does not resolve (${error.code || error.message}).`);
  note("The web and api containers are not on a shared Docker network.");
  process.exit(0);
}

try {
  const response = await fetch(`${target.origin}/health`, {
    signal: AbortSignal.timeout(5000),
  });
  note(`API /health responded ${response.status}.`);
} catch (error) {
  note(`API /health failed (${error.cause?.code || error.name}).`);
  note(
    `If ${base} is not the FireClip api container, another project is answering on that name. ` +
      "The api service also publishes the unique alias fireclip-api.",
  );
}
