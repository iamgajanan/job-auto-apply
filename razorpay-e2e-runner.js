/**
 * Razorpay Final E2E Runner  -  by claude
 * ENV: BASE_URL  CI_TEST_USER_EMAIL  CI_TEST_USER_PASSWORD
 * Prereqs: /tmp/node_modules/playwright, HTTP server on 4173 serving /tmp/rzp/
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

async function api(path, opts = {}) {
  const r = await fetch(BASE + path, opts), t = await r.text();
  let d; try { d = JSON.parse(t); } catch { d = { _raw: t }; }
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}\n${t.slice(0, 400)}`);
  return d;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const shot  = async (page, n) => {
  try { await page.screenshot({ path: `/tmp/rzp/${n}.png`, fullPage: true }); } catch {}
};

// Dump all text visible in all frames (for debugging)
async function dumpFrameText(page, label) {
  console.log(`\n--- Frame dump: ${label} ---`);
  for (const f of page.frames()) {
    try {
      const url = f.url().slice(0, 100);
      const txt = await f.evaluate(() => document.body?.innerText || "").catch(() => "");
      if (txt.trim()) console.log(`  [${url}]\n  ${txt.replace(/\n/g, " ").slice(0, 300)}`);
    } catch {}
  }
  console.log("--- end dump ---\n");
}

// Find visible element by CSS in any frame
async function findEl(page, sels, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const f of page.frames()) for (const s of sels) {
      try { const e = f.locator(s).first(); if (await e.count() && await e.isVisible()) return e; } catch {}
    }
    await page.waitForTimeout(400);
  }
  return null;
}

// Find element whose text CONTAINS the given string (case-insensitive)
async function findContainsText(page, substr, ms = 20000) {
  const end = Date.now() + ms;
  const lower = substr.toLowerCase();
  while (Date.now() < end) {
    for (const f of page.frames()) {
      try {
        // Try multiple element types that could be a payment method tab
        for (const tag of ["a", "li", "div", "span", "button", "label", "p"]) {
          const els = await f.locator(tag).all();
          for (const el of els) {
            try {
              if (!await el.isVisible()) continue;
              const txt = (await el.textContent() || "").toLowerCase().trim();
              if (txt === lower || txt.startsWith(lower + " ") || txt.startsWith(lower + "\n")) {
                console.log(`  Found "${await el.textContent()}" via <${tag}>`);
                return el;
              }
            } catch {}
          }
        }
      } catch {}
    }
    await page.waitForTimeout(500);
  }
  return null;
}

// Find button by partial text
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

(async () => {
  fs.mkdirSync("/tmp/rzp", { recursive: true });

  // [1] Login
  console.log("[1] Login...");
  const login = await api("/api/v1/auth/login", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASS }),
  });
  const token = login?.session?.access_token;
  if (!token) throw new Error("No token: " + JSON.stringify(login));
  console.log("    PASS");

  // [2] Create order
  console.log("[2] Create order (starter)...");
  const order = await api("/api/v1/payments/orders", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify({ plan_code: "starter" }),
  });
  if (order.plan_code !== "starter")                    throw new Error("plan_code: " + order.plan_code);
  if (order.amount_inr_paise !== 29900)                 throw new Error("amount: " + order.amount_inr_paise);
  if (order.currency !== "INR")                         throw new Error("currency: " + order.currency);
  if (!String(order.order_id).startsWith("order_"))     throw new Error("order_id: " + order.order_id);
  if (!String(order.razorpay_key_id).startsWith("rzp_test_")) throw new Error("key_id: " + order.razorpay_key_id);
  console.log("    PASS –", order.order_id);

  // [3] Invalid webhook → 400 or 503
  console.log("[3] Invalid webhook...");
  const wh = await fetch(`${BASE}/api/v1/payments/webhook`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-razorpay-signature": "bad-sig-e2e" },
    body: JSON.stringify({ id: "e2e-bad", event: "payment.captured",
      payload: { payment: { entity: { id: "pay_bad", order_id: "order_bad" } } } }),
  });
  if (wh.status !== 400 && wh.status !== 503)
    throw new Error("Webhook expected 400/503, got: " + wh.status);
  console.log("    PASS – HTTP", wh.status);

  // [4] Write checkout HTML
  console.log("[4] Writing checkout HTML...");
  fs.writeFileSync("/tmp/rzp/index.html",
    `<!doctype html><html><head><meta charset="utf-8"></head><body>
<button id="pay">Pay</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
var rzp = new Razorpay({
  key: ${JSON.stringify(order.razorpay_key_id)},
  amount: ${order.amount_inr_paise},
  currency: "INR",
  name: "Job Finder Test",
  description: "Automated E2E",
  order_id: ${JSON.stringify(order.order_id)},
  prefill: { name: "CI Test", email: ${JSON.stringify(EMAIL)}, contact: "9999999999" },
  handler: function(r) { window.paymentResult = r; },
  modal: { ondismiss: function() { window.paymentDismissed = true; } }
});
document.getElementById("pay").onclick = function() { rzp.open(); };
</script>
</body></html>`);
  console.log("    Written");

  // [5] Browser
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
    console.log("    Pay clicked — waiting 5s for Razorpay iframe...");
    await sleep(5000);
    await shot(page, "01-after-pay");
    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 100)).join("\n            "));

    // Mobile field
    const mobile = await findEl(page, [
      'input[placeholder="Mobile number"]',
      'input[placeholder*="mobile" i]',
      'input[type="tel"]',
    ], 30000);
    if (mobile) {
      console.log("    Mobile field found — filling...");
      await mobile.fill("9999999999");
      const cont = await findBtn(page, /continue/i, 5000);
      if (!cont) throw new Error("Continue button not found after mobile");
      await cont.click({ timeout: 3000 });
      console.log("    Clicked Continue");
      await sleep(3000);
      await shot(page, "02-after-continue");
    } else {
      console.log("    No mobile field");
      await shot(page, "02-no-mobile");
    }

    await dumpFrameText(page, "after mobile/continue step");
    console.log("    Frames:", page.frames().map(f => f.url().slice(0, 100)).join("\n            "));

    // UPI tab — try exact text first, then contains text
    console.log("    Looking for UPI tab (exact match first)...");
    let upiTab = null;

    // Try exact text "UPI" in any frame
    for (let i = 0; i < 40 && !upiTab; i++) {
      for (const f of page.frames()) {
        try {
          const e = f.getByText("UPI", { exact: true }).first();
          if (await e.count() && await e.isVisible()) { upiTab = e; break; }
        } catch {}
      }
      if (!upiTab) await page.waitForTimeout(500);
    }

    if (!upiTab) {
      console.log("    Exact 'UPI' not found — trying contains 'upi'...");
      upiTab = await findContainsText(page, "upi", 5000);
    }

    if (!upiTab) {
      await shot(page, "03-no-upi-tab");
      await dumpFrameText(page, "UPI NOT FOUND - all frames");
      throw new Error("UPI tab not found after exhaustive search");
    }

    const tabText = await upiTab.textContent().catch(() => "?");
    console.log(`    Found UPI element: "${tabText}" — clicking...`);
    await upiTab.click({ timeout: 3000 });
    await sleep(2000);
    await shot(page, "03-after-upi-click");
    await dumpFrameText(page, "after UPI tab click");

    // UPI input
    console.log("    Looking for UPI input...");
    const upiInput = await findEl(page, [
      'input[placeholder*="UPI" i]',
      'input[placeholder*="VPA" i]',
      'input[name*="vpa" i]',
      'input[name*="upi" i]',
      'input[type="text"]',
      'input[type="email"]',
    ], 20000);
    if (!upiInput) {
      await shot(page, "04-no-upi-input");
      await dumpFrameText(page, "no UPI input");
      throw new Error("UPI ID input not found");
    }
    console.log("    Filling success@razorpay...");
    await upiInput.fill("success@razorpay");
    await sleep(500);
    await shot(page, "04-upi-filled");

    // Pay button
    const payBtn =
      await findBtn(page, /verify\s*and\s*pay/i, 3000) ||
      await findBtn(page, /pay\s*now/i, 3000) ||
      await findBtn(page, /^pay$/i, 5000) ||
      await findBtn(page, /pay/i, 5000);
    if (!payBtn) {
      await shot(page, "05-no-pay");
      throw new Error("Pay button not found");
    }
    console.log("    Clicking Pay...");
    await payBtn.click({ timeout: 3000 });
    await shot(page, "05-after-pay");

    console.log("    Waiting for payment result (90s)...");
    await page.waitForFunction(() => !!window.paymentResult, null, { timeout: 90000 });
    result = await page.evaluate(() => window.paymentResult);
    if (!result?.razorpay_payment_id || !result?.razorpay_order_id || !result?.razorpay_signature) {
      await shot(page, "06-bad-result");
      throw new Error("Incomplete: " + JSON.stringify(result));
    }
    console.log("    CHECKOUT PASS –", result.razorpay_payment_id);

  } finally {
    await browser.close().catch(() => {});
  }

  // [6] POST /verify
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
  if (verify.status !== "captured") throw new Error("/verify: " + verify.status);
  console.log("    PASS – captured");

  // [7] GET /history
  console.log("[7] GET /payments/history...");
  let row = null;
  for (let i = 0; i < 30; i++) {
    const h = await api("/api/v1/payments/history", { headers: { authorization: `Bearer ${token}` } });
    row = (h.payments || []).find(p => p.provider_order_id === order.order_id);
    if (row && row.status === "captured") break;
    await sleep(1000);
  }
  if (!row || row.status !== "captured") throw new Error("History: " + JSON.stringify(row));
  console.log("    PASS – captured in DB");

  // [8] GET /account/me
  console.log("[8] GET /account/me...");
  const me = await api("/api/v1/account/me", { headers: { authorization: `Bearer ${token}` } });
  if (me?.user?.plan_code !== "starter")
    throw new Error("Plan: " + me?.user?.plan_code + " | " + JSON.stringify(me));
  console.log("    PASS – plan_code: starter");

  console.log("\nRAZORPAY FINAL E2E: PASS");

})().catch(err => { console.error("\nFAILED:", err.stack || String(err)); process.exit(1); });
