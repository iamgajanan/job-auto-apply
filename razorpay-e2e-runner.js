/**
 * Razorpay Final E2E Runner  -  by claude
 *
 * Prerequisites (set by workflow before running this):
 *   - /tmp/node_modules/playwright  (cd /tmp && npm install playwright && npx playwright install chromium)
 *   - HTTP server on http://127.0.0.1:4173 serving /tmp/rzp/
 *
 * ENV: BASE_URL  CI_TEST_USER_EMAIL  CI_TEST_USER_PASSWORD
 */
"use strict";

const { chromium } = require("/tmp/node_modules/playwright");
const fs = require("fs");

const BASE  = (process.env.BASE_URL || "").replace(/\/$/, "");
const EMAIL = process.env.CI_TEST_USER_EMAIL    || "";
const PASS  = process.env.CI_TEST_USER_PASSWORD || "";

if (!BASE || !EMAIL || !PASS) {
  console.error("FATAL: BASE_URL, CI_TEST_USER_EMAIL, CI_TEST_USER_PASSWORD required");
  process.exit(1);
}

// ─── helpers ────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const r = await fetch(BASE + path, opts);
  const t = await r.text();
  let d; try { d = JSON.parse(t); } catch { d = { _raw: t }; }
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}\n${t.slice(0, 400)}`);
  return d;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const shot  = async (page, n) => {
  try { await page.screenshot({ path: `/tmp/rzp/${n}.png`, fullPage: true }); } catch {}
};

// search every frame for visible element matching any CSS selector
async function findEl(page, sels, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const f of page.frames())
      for (const s of sels) {
        try { const e = f.locator(s).first(); if (await e.count() && await e.isVisible()) return e; } catch {}
      }
    await page.waitForTimeout(400);
  }
  return null;
}

// search every frame for element with EXACT text
async function findText(page, txt, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const f of page.frames()) {
      try { const e = f.getByText(txt, { exact: true }).first(); if (await e.count() && await e.isVisible()) return e; } catch {}
    }
    await page.waitForTimeout(400);
  }
  return null;
}

// search every frame for button matching regex name
async function findBtn(page, re, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const f of page.frames()) {
      try { const e = f.getByRole("button", { name: re }).last(); if (await e.count() && await e.isVisible()) return e; } catch {}
    }
    await page.waitForTimeout(400);
  }
  return null;
}

// ─── main ────────────────────────────────────────────────────────────────────
(async () => {
  fs.mkdirSync("/tmp/rzp", { recursive: true });

  // [1] Login
  console.log("[1] Login...");
  const login = await api("/api/v1/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASS }),
  });
  const token = login?.session?.access_token;
  if (!token) throw new Error("No token in login response: " + JSON.stringify(login));
  console.log("    PASS");

  // [2] Create Razorpay order
  console.log("[2] Create order (plan=starter)...");
  const order = await api("/api/v1/payments/orders", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify({ plan_code: "starter" }),
  });
  if (order.plan_code          !== "starter")       throw new Error("plan_code wrong: "  + order.plan_code);
  if (order.amount_inr_paise   !== 29900)           throw new Error("amount wrong: "     + order.amount_inr_paise);
  if (order.currency           !== "INR")           throw new Error("currency wrong: "   + order.currency);
  if (!String(order.order_id).startsWith("order_")) throw new Error("order_id bad: "     + order.order_id);
  if (!String(order.razorpay_key_id).startsWith("rzp_test_")) throw new Error("key_id bad: " + order.razorpay_key_id);
  console.log("    PASS –", order.order_id);

  // [3] Invalid webhook → must return 400 (when secret configured) or 503 (when not)
  console.log("[3] Invalid webhook signature → expect 400 or 503...");
  const wh = await fetch(`${BASE}/api/v1/payments/webhook`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-razorpay-signature": "bad-sig-e2e-runner" },
    body: JSON.stringify({ id: "e2e-runner-bad", event: "payment.captured",
      payload: { payment: { entity: { id: "pay_bad", order_id: "order_bad" } } } }),
  });
  if (wh.status !== 400 && wh.status !== 503)
    throw new Error("Expected 400 or 503 for invalid webhook, got: " + wh.status);
  console.log("    PASS – HTTP", wh.status);

  // [4] Write checkout HTML (HTTP server already running on 4173 serving /tmp/rzp)
  console.log("[4] Writing checkout page...");
  fs.writeFileSync("/tmp/rzp/index.html",
    `<!doctype html><html><head><meta charset="utf-8"></head><body>
<button id="pay">Pay</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
var rzp = new Razorpay({
  key:         ${JSON.stringify(order.razorpay_key_id)},
  amount:      ${order.amount_inr_paise},
  currency:    "INR",
  name:        "Job Finder Test",
  description: "Automated E2E",
  order_id:    ${JSON.stringify(order.order_id)},
  prefill:     { name: "CI Test", email: ${JSON.stringify(EMAIL)}, contact: "9999999999" },
  handler:     function(r) { window.paymentResult = r; },
  modal:       { ondismiss: function() { window.paymentDismissed = true; } }
});
document.getElementById("pay").onclick = function() { rzp.open(); };
</script>
</body></html>`);
  console.log("    Written");

  // [5] Playwright browser checkout
  console.log("[5] Launching Chromium...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("console", m => { if (m.type() === "error") console.log("  [browser-err]", m.text().slice(0, 150)); });

  let result;
  try {
    await page.goto("http://127.0.0.1:4173/index.html");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Pay" }).click();
    console.log("    Pay clicked — waiting 4s for Razorpay iframe...");
    await sleep(4000);
    await shot(page, "01-after-pay");
    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 80)).join("\n            "));

    // Mobile field (Razorpay shows this first in test mode)
    const mobile = await findEl(page, [
      'input[placeholder="Mobile number"]',
      'input[placeholder*="mobile" i]',
      'input[type="tel"]',
    ], 30000);

    if (mobile) {
      console.log("    Mobile field found — filling 9999999999...");
      await mobile.fill("9999999999");
      const cont = await findBtn(page, /continue/i, 5000);
      if (!cont) throw new Error("Continue button not found after mobile field");
      await cont.click({ timeout: 3000 });
      console.log("    Clicked Continue");
      await sleep(2000);
      await shot(page, "02-after-continue");
    } else {
      console.log("    No mobile field — Razorpay skipped contact screen");
      await shot(page, "02-no-mobile");
    }
    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 80)).join("\n            "));

    // UPI tab — exact text match
    console.log("    Looking for UPI tab...");
    const upiTab = await findText(page, "UPI", 20000);
    if (!upiTab) {
      await shot(page, "03-no-upi-tab");
      throw new Error("UPI tab not found after 20s");
    }
    console.log("    UPI tab found — clicking...");
    await upiTab.click({ timeout: 3000 });
    await sleep(1500);
    await shot(page, "03-after-upi-click");

    // UPI ID input
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
    await sleep(300);
    await shot(page, "04-upi-filled");

    // Pay button
    const payBtn =
      await findBtn(page, /verify\s*and\s*pay/i, 3000) ||
      await findBtn(page, /pay\s*now/i, 3000)          ||
      await findBtn(page, /^pay$/i, 5000)              ||
      await findBtn(page, /pay/i, 5000);
    if (!payBtn) {
      await shot(page, "05-no-pay-btn");
      throw new Error("Pay button not found");
    }
    console.log("    Clicking Pay...");
    await payBtn.click({ timeout: 3000 });
    await shot(page, "05-after-pay");

    // Wait for payment result
    console.log("    Waiting up to 60s for window.paymentResult...");
    await page.waitForFunction(() => !!window.paymentResult, null, { timeout: 60000 });
    result = await page.evaluate(() => window.paymentResult);

    if (!result?.razorpay_payment_id || !result?.razorpay_order_id || !result?.razorpay_signature) {
      await shot(page, "06-bad-result");
      throw new Error("Incomplete checkout result: " + JSON.stringify(result));
    }
    console.log("    CHECKOUT PASS –", result.razorpay_payment_id);

  } finally {
    await browser.close().catch(() => {});
  }

  // [6] POST /verify — verifies signature + fetches from Razorpay API → marks captured in DB
  console.log("[6] POST /payments/verify...");
  const verify = await api("/api/v1/payments/verify", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify({
      razorpay_order_id:   result.razorpay_order_id,
      razorpay_payment_id: result.razorpay_payment_id,
      razorpay_signature:  result.razorpay_signature,
    }),
  });
  if (verify.status !== "captured") throw new Error("/verify returned: " + verify.status);
  console.log("    PASS – status: captured");

  // [7] GET /history → assert payment row shows captured
  console.log("[7] GET /payments/history → assert captured...");
  let row = null;
  for (let i = 0; i < 30; i++) {
    const h = await api("/api/v1/payments/history", { headers: { authorization: `Bearer ${token}` } });
    row = (h.payments || []).find(p => p.provider_order_id === order.order_id);
    if (row && row.status === "captured") break;
    await sleep(1000);
  }
  if (!row)                        throw new Error("Order not found in history");
  if (row.status !== "captured")   throw new Error("History status: " + row.status);
  console.log("    PASS – captured in DB");

  // [8] GET /account/me → user.plan_code must be starter
  // Response shape: { user: { id, email, plan_code, ... }, usage: { plan_code, ... } }
  console.log("[8] GET /account/me → assert plan_code=starter...");
  const me = await api("/api/v1/account/me", { headers: { authorization: `Bearer ${token}` } });
  const planCode = me?.user?.plan_code;
  if (planCode !== "starter")
    throw new Error("Plan not upgraded. user.plan_code=" + planCode + "\nFull: " + JSON.stringify(me));
  console.log("    PASS – plan_code: starter");

  console.log("\nRAZORPAY FINAL E2E: PASS");

})().catch(err => { console.error("\nFAILED:", err.stack || String(err)); process.exit(1); });
