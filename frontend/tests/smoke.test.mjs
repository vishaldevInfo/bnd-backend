// End-to-end smoke test: drives headless Chrome through the running app.
//
// Needs the backend and frontend running (see README) plus the admin login (ENV account):
//   SMOKE_EMAIL=demo@example.com SMOKE_PASSWORD=... npm run test:smoke
// Optional: APP_URL (default http://localhost:3010), CHROME_PATH (default google-chrome).
//
// No extra dependencies: Chrome is controlled over the DevTools protocol with
// Node's built-in WebSocket. Assertions never depend on specific member names.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const APP_URL = process.env.APP_URL ?? "http://localhost:3010";
const { SMOKE_EMAIL, SMOKE_PASSWORD } = process.env;

async function appIsUp() {
  try {
    return (await fetch(`${APP_URL}/api/health`)).ok;
  } catch {
    return false;
  }
}

const skipReason = !SMOKE_EMAIL || !SMOKE_PASSWORD
  ? "set SMOKE_EMAIL and SMOKE_PASSWORD to run the smoke test"
  : !(await appIsUp())
    ? `app or database not reachable at ${APP_URL}/api/health`
    : false;

// ---------- Minimal Chrome DevTools client ----------

let chrome, socket, profileDir;
let nextId = 0;
const pending = new Map();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, (message) => (message.error ? reject(new Error(message.error.message)) : resolve(message.result)));
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const { result, exceptionDetails } = await send("Runtime.evaluate", {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description ?? exceptionDetails.text);
  return result.value;
}

/** Polls `expression` until it returns a truthy value. */
async function waitFor(expression, description, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await evaluate(expression).catch(() => null);
    if (value) return value;
    await sleep(250);
  }
  const page = await evaluate("location.pathname + ' | ' + document.body.innerText.replace(/\\s+/g, ' ').slice(0, 300)").catch(() => "?");
  throw new Error(`Timed out waiting for: ${description}\n  page: ${page}`);
}

async function open(path) {
  await send("Page.navigate", { url: `${APP_URL}${path}` });
  await waitFor("document.readyState === 'complete'", `page load ${path}`);
}

const path = () => evaluate("location.pathname + location.search");
// Visible data rows only: charts also render screen-reader tables (class "sr-only").
const ROWS = "document.querySelectorAll('table:not(.sr-only) tbody tr')";
const text = (selector) => `document.querySelector(${JSON.stringify(selector)})?.textContent?.trim() ?? ""`;

async function fillLogin(email, password) {
  // React listens for input events, so set values through the native setter.
  await evaluate(`(() => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    for (const [id, value] of [["email", ${JSON.stringify(email)}], ["password", ${JSON.stringify(password)}]]) {
      const input = document.getElementById(id);
      set.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    document.querySelector("form button[type=submit]").click();
  })()`);
}

before(async () => {
  if (skipReason) return;
  profileDir = mkdtempSync(join(tmpdir(), "bnd-smoke-"));
  const port = 9500 + Math.floor(Math.random() * 400);
  chrome = spawn(process.env.CHROME_PATH ?? "google-chrome", [
    "--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`, "about:blank",
  ], { stdio: "ignore" });

  let target;
  for (let i = 0; i < 75 && !target; i++) {
    await sleep(200);
    try {
      target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page");
    } catch { /* Chrome still starting */ }
  }
  assert.ok(target, "Chrome did not start (set CHROME_PATH?)");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  });
  await new Promise((resolve) => socket.addEventListener("open", resolve));
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
});

after(async () => {
  socket?.close();
  if (chrome) {
    const exited = new Promise((resolve) => chrome.once("exit", resolve));
    chrome.kill();
    await exited; // Chrome must release its profile folder before it is deleted
  }
  if (profileDir) rmSync(profileDir, { recursive: true, force: true, maxRetries: 3 });
});

// ---------- The user journey (tests run in order and share the browser) ----------

test("signed-out visitors are sent to the login page", { skip: skipReason }, async () => {
  await open("/admin/invoices");
  await waitFor("location.pathname === '/admin'", "redirect to /admin");
  assert.equal(await path(), "/admin?next=%2Fadmin%2Finvoices");
});

test("wrong credentials show one generic error", { skip: skipReason }, async () => {
  await waitFor("document.getElementById('email')", "login form");
  await fillLogin(SMOKE_EMAIL, "definitely-not-the-password");
  const message = await waitFor(text("[role=alert]"), "login error message");
  assert.equal(message, "Invalid email or password.");
});

test("signing in returns to the requested page", { skip: skipReason }, async () => {
  await fillLogin(SMOKE_EMAIL, SMOKE_PASSWORD);
  await waitFor("location.pathname === '/admin/invoices'", "redirect back to /admin/invoices");
  await waitFor(`${ROWS}.length > 0`, "invoice rows");
  const summary = await evaluate(text("[aria-live=polite]"));
  assert.match(summary, /^[\d,]+ invoices in total$/);
});

test("an invoice opens with its line items and total", { skip: skipReason }, async () => {
  await evaluate("document.querySelector('tbody tr a').click()");
  await waitFor("/^\\/admin\\/invoices\\/[^/]+\\/[^/]+$/.test(location.pathname)", "invoice detail URL");
  await waitFor("document.body.innerText.includes('Invoice total')", "line items table");
  assert.ok(await evaluate(`${ROWS}.length > 0`), "at least one line item");
});

test("dashboard shows KPIs, both charts and recent invoices", { skip: skipReason }, async () => {
  await open("/admin/dashboard");
  await waitFor("document.querySelectorAll('.recharts-surface').length === 2", "two charts", 45_000);
  const kpis = await evaluate(`["Total Invoices", "Total Amount", "Average Invoice", "Active Facilities"]
    .map((label) => document.body.innerText.includes(label))`);
  assert.deepEqual(kpis, [true, true, true, true]);
  assert.equal(await evaluate(`${ROWS}.length`), 10, "10 recent invoices");
});

test("filters are kept in the URL", { skip: skipReason }, async () => {
  await open("/admin/invoices?sort=amount&order=asc&page_size=50");
  await waitFor(`${ROWS}.length === 50`, "50 rows");
  assert.equal(await evaluate(text("th[aria-sort] button")), "Amount");
});

test("report offers a CSV download with the same filters", { skip: skipReason }, async () => {
  await open("/admin/reports?start=2026-01-01&end=2026-03-31");
  const href = await waitFor("document.querySelector('a[download]')?.getAttribute('href')", "Download CSV link");
  assert.equal(href, "/api/reports/invoices/export?start=2026-01-01&end=2026-03-31");
});

test("signing out returns to login and protects pages again", { skip: skipReason }, async () => {
  await evaluate("document.querySelector('button[aria-label=\"Sign out\"]').click()");
  await waitFor("location.pathname === '/admin'", "admin login page after sign out");
  await open("/admin/dashboard");
  await waitFor("location.pathname === '/admin'", "redirect to /admin after sign out");
});
