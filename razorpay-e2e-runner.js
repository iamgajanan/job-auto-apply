/**
 * Razorpay Final E2E Runner
 * Mirrors the approach proven by razorpay-checkout-diagnostic.yml
 */
"use strict";

const { chromium } = require("/tmp/node_modules/playwright");
const fs = require("fs");

const BASE     = (process.env.BASE_URL || "").replace(/\/$/, "");
const EMAIL    = process.env.CI_TEST_USER_EMAIL    || "";
const PASSWORD = process.env.CI_TEST_USER_PASSWORD || "";

if (!BASE || !EMAIL || !PASSWORD) {
  console.error("FATAL: BASE_URL, CI_TEST_USER_EMAIL, CI_TEST_USER_PASSWORD must be set");
  process.exit(1);
}

async function api(path, opts = {}) {
  const res  = await fetch(BASE + path, opts);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { _raw: text }; }
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}\n${text.slice(0, 500)}`);
  return data;
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function shot(page, name) {
  try { await page.screenshot({ path: `/tmp/rzp/${name}.png`, fullPage: true }); } catch {}
}

// Search all frames for any selector, return first visible element or null
async function findEl(page, selectors, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      for (const sel of selectors) {
        try {
          const el = frame.locator(sel).first();
          if ((await el.count()) > 0 && (await el.isVisible())) return el;
        } catch {}
      }
    }
    await page.waitForTimeout(400);
  }
  return null;
}

// Search all frames using getByText exact match
async function findByText(page, text, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      try {
        const el = frame.getByText(text, { exact: true }).first();
        if ((await el.count()) > 0 && (await el.isVisible())) return el;
      } catch {}
    }
    await page.waitForTimeout(400);
  }
  return null;
}

// Search all frames using getByRole button with name regex
async function findButton(page, nameRegex, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      try {
        const el = frame.getByRole("button", { name: nameRegex }).last();
        if ((await el.count()) > 0 && (await el.isVisible())) return el;
      } catch {}
    }
    await page.waitForTimeout(400);
  }
  return null;
}

(async () => {
  fs.mkdirSync("/tmp/rzp", { recursive: true });

  // ── 1. Login ──────────────────────────────────────────────────────────────
  console.log("[1] Login...");
  const login = await api("/api/v1/auth/login", {
    method : "POST",
    headers: { "content-type": "application/json" },
    body   : JSON.stringify({ email: EMAIL, password: PASSWORD }),
  });
  const token = login.session.access_token;
  if (!token) throw new Error("No access token: " + JSON.stringify(login));
  console.log("    PASS");

  // ── 2. Create Razorpay order ──────────────────────────────────────────────
  console.log("[2] Create order (plan=starter)...");
  const order = await api("/api/v1/payments/orders", {
    method : "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body   : JSON.stringify({ plan_code: "starter" }),
  });
  if (order.plan_code        !== "starter")          throw new Error("plan_code wrong: "  + order.plan_code);
  if (order.amount_inr_paise !== 29900)              throw new Error("amount wrong: "     + order.amount_inr_paise);
  if (order.currency         !== "INR")              throw new Error("currency wrong: "   + order.currency);
  if (!order.order_id.startsWith("order_"))          throw new Error("order_id bad: "     + order.order_id);
  if (!order.razorpay_key_id.startsWith("rzp_test_")) throw new Error("key_id bad: "     + order.razorpay_key_id);
  console.log("    PASS –", order.order_id);

  // ── 3. Invalid webhook must return 400 ───────────────────────────────────
  console.log("[3] Invalid webhook signature → expect HTTP 400...");
  const wh = await fetch(`${BASE}/api/v1/payments/webhook`, {
    method : "POST",
    headers: { "content-type": "application/json", "x-razorpay-signature": "badsig-e2e-test" },
    body   : JSON.stringify({
      id: "e2e-invalid", event: "payment.captured",
      payload: { payment: { entity: { id: "pay_bad", order_id: "order_bad" } } },
    }),
  });
  if (wh.status !== 400) throw new Error("Expected 400, got " + wh.status);
  console.log("    PASS – HTTP 400");

  // ── 4. Write checkout page (HTTP server already running on 4173) ──────────
  console.log("[4] Writing checkout HTML for http://127.0.0.1:4173/index.html...");
  fs.writeFileSync("/tmp/rzp/index.html", [
    "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>",
    "<button id=\"pay\">Pay</button>",
    "<script src=\"https://checkout.razorpay.com/v1/checkout.js\"></script>",
    "<script>",
    "var rzp=new Razorpay({",
    `  key:${JSON.stringify(order.razorpay_key_id)},`,
    `  amount:${order.amount_inr_paise},`,
    "  currency:\"INR\",",
    "  name:\"Job Finder Test\",",
    "  description:\"Automated E2E Test\",",
    `  order_id:${JSON.stringify(order.order_id)},`,
    `  prefill:{name:"CI Test",email:${JSON.stringify(EMAIL)},contact:"9999999999"},`,
    "  handler:function(r){window.paymentResult=r;},",
    "  modal:{ondismiss:function(){window.paymentDismissed=true;}}",
    "});",
    "document.getElementById(\"pay\").onclick=function(){rzp.open();};",
    "</script></body></html>",
  ].join("\n"));
  console.log("    Written");

  // ── 5. Playwright browser ─────────────────────────────────────────────────
  console.log("[5] Launching Chromium (headless)...");
  const browser = await chromium.launch({
    headless: true,
    args    : ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("console", m => { if (m.type() === "error") console.log("  [browser-err]", m.text().slice(0, 200)); });

  let result;
  try {
    await page.goto("http://127.0.0.1:4173/index.html");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Pay" }).click();
    console.log("    Pay clicked — waiting for Razorpay iframe...");
    await sleep(4000);
    await shot(page, "01-after-pay");
    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 80)).join("\n           "));

    // ── Mobile number (Razorpay first screen) ─────────────────────────────
    const mobile = await findEl(page, [
      'input[placeholder="Mobile number"]',
      'input[placeholder*="mobile" i]',
      'input[type="tel"]',
    ], 30000);

    if (mobile) {
      console.log("    Filling mobile: 9999999999");
      await mobile.fill("9999999999");
      const cont = await findButton(page, /continue/i, 5000);
      if (!cont) throw new Error("Continue button not found after mobile field");
      await cont.click({ timeout: 3000 });
      console.log("    Clicked Continue");
      await sleep(1500);
      await shot(page, "02-after-continue");
    } else {
      console.log("    No mobile field — checkout skipped contact screen");
      await shot(page, "02-no-mobile");
    }

    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 80)).join("\n           "));

    // ── UPI tab — use exact text match (same as diagnostic) ───────────────
    console.log("    Looking for UPI tab (exact text)...");
    const upiTab = await findByText(page, "UPI", 20000);
    if (!upiTab) {
      await shot(page, "03-no-upi-tab");
      console.log("    All frame URLs:", page.frames().map(f => f.url()).join("\n    "));
      throw new Error("UPI tab not found");
    }
    console.log("    Clicking UPI tab...");
    await upiTab.click({ timeout: 3000 });
    await sleep(1500);
    await shot(page, "03-after-upi-click");

    // ── UPI ID input ──────────────────────────────────────────────────────
    console.log("    Looking for UPI ID input...");
    const upiInput = await findEl(page, [
      'input[placeholder*="UPI" i]',
      'input[placeholder*="VPA" i]',
      'input[name*="vpa" i]',
      'input[name*="upi" i]',
    ], 20000);
    if (!upiInput) {
      await shot(page, "04-no-upi-input");
      throw new Error("UPI ID input not found");
    }
    console.log("    Filling success@razorpay...");
    await upiInput.fill("success@razorpay");
    await shot(page, "04-upi-filled");

    // ── Pay / Verify and Pay button ───────────────────────────────────────
    console.log("    Looking for Pay button...");
    const payBtn =
      await findButton(page, /verify\s*and\s*pay/i, 2000) ||
      await findButton(page, /pay\s*now/i, 2000) ||
      await findButton(page, /^pay$/i, 5000) ||
      await findButton(page, /pay/i, 3000);

    if (!payBtn) {
      await shot(page, "05-no-pay-btn");
      throw new Error("Pay button not found");
    }
    console.log("    Clicking Pay...");
    await payBtn.click({ timeout: 3000 });
    await shot(page, "05-after-pay");

    // ── Wait for payment result ───────────────────────────────────────────
    console.log("    Waiting for window.paymentResult (up to 60s)...");
    await page.waitForFunction(() => !!window.paymentResult, null, { timeout: 60000 });
    result = await page.evaluate(() => window.paymentResult);

    if (!result?.razorpay_payment_id || !result?.razorpay_order_id || !result?.razorpay_signature) {
      await shot(page, "06-bad-result");
      throw new Error("Incomplete payment result: " + JSON.stringify(result));
    }
    console.log("    CHECKOUT PASS –", result.razorpay_payment_id);

  } finally {
    await browser.close().catch(() => {});
  }

  // ── 6. POST /verify — verifies signature + fetches from Razorpay API ─────
  console.log("[6] POST /payments/verify...");
  const verify = await api("/api/v1/payments/verify", {
    method : "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body   : JSON.stringify({
      razorpay_order_id  : result.razorpay_order_id,
      razorpay_payment_id: result.razorpay_payment_id,
      razorpay_signature : result.razorpay_signature,
    }),
  });
  if (verify.status !== "captured") throw new Error("/verify status wrong: " + verify.status);
  console.log("    PASS – captured");

  // ── 7. GET /history — payment must show captured ──────────────────────────
  console.log("[7] GET /payments/history → assert captured...");
  let histRow = null;
  for (let i = 0; i < 30; i++) {
    const hist = await api("/api/v1/payments/history", { headers: { authorization: `Bearer ${token}` } });
    histRow = (hist.payments || []).find(p => p.provider_order_id === order.order_id);
    if (histRow && histRow.status === "captured") break;
    await sleep(1000);
  }
  if (!histRow)                          throw new Error("Order not in history");
  if (histRow.status !== "captured")     throw new Error("History status: " + histRow.status);
  if (histRow.provider_payment_id !== result.razorpay_payment_id)
    throw new Error("payment_id mismatch in history");
  console.log("    PASS – payment captured in DB");

  // ── 8. GET /account/me — plan must be starter ─────────────────────────────
  // Response shape: { user: { plan_code, ... }, usage: { ... } }
  console.log("[8] GET /account/me → assert plan_code=starter...");
  const me = await api("/api/v1/account/me", { headers: { authorization: `Bearer ${token}` } });
  const planCode = me.user ? me.user.plan_code : me.plan_code;
  if (planCode !== "starter")
    throw new Error("Plan not upgraded. Got: " + planCode + "\n" + JSON.stringify(me));
  console.log("    PASS – plan_code: starter");

  console.log("\nRAZORPAY FINAL E2E: PASS");

})().catch(err => {
  console.error("\nFAILED:", err.stack || String(err));
  process.exit(1);
});
