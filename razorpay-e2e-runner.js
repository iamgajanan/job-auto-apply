/**
 * Razorpay Final E2E Runner
 *
 * Flow:
 *  1. Login, create order, assert order fields
 *  2. Assert invalid webhook returns 400
 *  3. Open Razorpay Checkout via local HTTP server + Playwright (headless)
 *  4. Use UPI success@razorpay (official Razorpay test VPA, auto-captures)
 *  5. POST /verify -> backend verifies with Razorpay API, updates DB
 *  6. Assert status === captured
 *  7. Assert payment in /history shows captured
 *  8. Assert me.user.plan_code === 'starter'
 */
const { chromium } = require("playwright");
const http = require("http");

const BASE = process.env.BASE_URL;
const EMAIL = process.env.EMAIL;
const PASSWORD = process.env.PASSWORD;

if (!BASE || !EMAIL || !PASSWORD) {
  console.error("FATAL: Missing env BASE_URL / EMAIL / PASSWORD");
  process.exit(1);
}

async function api(urlPath, opts = {}) {
  const res = await fetch(BASE + urlPath, opts);
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(`${urlPath}: HTTP ${res.status} - ${text.slice(0, 500)}`);
  return data;
}

/**
 * Search all page frames for a visible element matching any of the selectors.
 * Returns the first match, or null if none found within timeout ms.
 */
async function findVisible(page, selectors, timeoutMs = 20000) {
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

async function screenshot(page, name) {
  try { await page.screenshot({ path: `/tmp/rzp-${name}.png`, fullPage: true }); } catch {}
}

(async () => {
  // ── Step 1: Login ──────────────────────────────────────────────────────────
  console.log("[1] Login...");
  const login = await api("/api/v1/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  });
  const token = login.session.access_token;
  console.log("    Login OK");

  // ── Step 2: Create order ───────────────────────────────────────────────────
  console.log("[2] Create Razorpay order (plan=starter)...");
  const order = await api("/api/v1/payments/orders", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify({ plan_code: "starter" }),
  });
  if (order.plan_code !== "starter")       throw new Error(`plan_code wrong: ${order.plan_code}`);
  if (order.amount_inr_paise !== 29900)    throw new Error(`amount wrong: ${order.amount_inr_paise}`);
  if (order.currency !== "INR")            throw new Error(`currency wrong: ${order.currency}`);
  if (!order.order_id.startsWith("order_")) throw new Error(`order_id bad: ${order.order_id}`);
  if (!order.razorpay_key_id.startsWith("rzp_test_")) throw new Error(`key bad: ${order.razorpay_key_id}`);
  console.log(`    Order OK: ${order.order_id}`);

  // ── Step 3: Invalid webhook → 400 ─────────────────────────────────────────
  console.log("[3] Assert invalid webhook signature → HTTP 400...");
  const whRes = await fetch(`${BASE}/api/v1/payments/webhook`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-razorpay-signature": "badsig-e2e-test",
    },
    body: JSON.stringify({
      id: "e2e-badsig",
      event: "payment.captured",
      payload: { payment: { entity: { id: "pay_bad", order_id: "order_bad" } } },
    }),
  });
  if (whRes.status !== 400) throw new Error(`Expected 400, got ${whRes.status}`);
  console.log("    INVALID WEBHOOK: PASS (HTTP 400)");

  // ── Step 4: Start local HTTP server for checkout page ─────────────────────
  const checkoutHtml = `<!doctype html>
<html><head><meta charset="utf-8"><title>RZP E2E Test</title></head>
<body>
<button id="pay">Pay</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
  var rzp = new Razorpay({
    key: ${JSON.stringify(order.razorpay_key_id)},
    amount: ${order.amount_inr_paise},
    currency: "INR",
    name: "Job Finder Test",
    description: "Automated E2E Test",
    order_id: ${JSON.stringify(order.order_id)},
    prefill: { name: "CI Test User", email: ${JSON.stringify(EMAIL)}, contact: "9999999999" },
    handler: function(r) { window.paymentResult = r; },
    modal: { ondismiss: function() { window.paymentDismissed = true; } }
  });
  document.getElementById("pay").onclick = function() { rzp.open(); };
</script>
</body></html>`;

  const server = http.createServer((req, res) => {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(checkoutHtml);
  });
  await new Promise(resolve => server.listen(4173, "127.0.0.1", resolve));
  console.log("[4] HTTP server started on http://127.0.0.1:4173");

  let browser;
  try {
    // ── Step 5: Browser checkout ─────────────────────────────────────────────
    console.log("[5] Launching headless Chromium...");
    browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();

    page.on("console", msg => {
      if (msg.type() === "error") console.log("    [browser-err]", msg.text().slice(0, 200));
    });

    await page.goto("http://127.0.0.1:4173/");
    await page.waitForLoadState("networkidle");
    console.log("    Page loaded, clicking Pay button...");
    await page.getByRole("button", { name: "Pay" }).click();

    // Wait for Razorpay Checkout modal to appear
    console.log("    Waiting for Razorpay Checkout modal...");
    await page.waitForTimeout(4000);
    await screenshot(page, "01-after-pay-click");

    // Handle optional mobile number field (Razorpay sometimes shows this first)
    const mobileField = await findVisible(page, [
      'input[placeholder="Mobile number"]',
      'input[placeholder*="mobile" i]',
      'input[placeholder*="phone" i]',
    ], 8000);

    if (mobileField) {
      console.log("    Filling mobile number field...");
      await mobileField.fill("9999999999");
      await page.waitForTimeout(500);
      const continueBtn = await findVisible(page, [
        'button:has-text("Continue")',
        'button[class*="continue" i]',
      ], 5000);
      if (continueBtn) {
        await continueBtn.click({ force: true });
        console.log("    Clicked Continue");
        await page.waitForTimeout(2000);
      }
    } else {
      console.log("    No mobile field (checkout skipped it)");
    }

    await screenshot(page, "02-after-mobile");

    // ── Select UPI payment method ────────────────────────────────────────────
    console.log("    Looking for UPI payment option...");
    const upiOption = await findVisible(page, [
      '[data-testid="UPI"]',
      'span:has-text("UPI")',
      'div:has-text("UPI")',
      'li:has-text("UPI")',
      'label:has-text("UPI")',
      '[class*="upi" i]:not(input)',
      'a:has-text("UPI")',
    ], 20000);

    if (!upiOption) {
      await screenshot(page, "03-no-upi-option");
      // Log frame URLs for debugging
      for (const f of page.frames()) {
        console.log("    Frame URL:", f.url().slice(0, 100));
      }
      throw new Error("UPI payment option not found in Razorpay Checkout");
    }
    console.log("    Clicking UPI option...");
    await upiOption.click({ force: true });
    await page.waitForTimeout(2000);
    await screenshot(page, "03-after-upi-click");

    // ── Fill UPI ID ──────────────────────────────────────────────────────────
    console.log("    Looking for UPI ID input...");
    const upiInput = await findVisible(page, [
      'input[placeholder*="Enter UPI ID" i]',
      'input[placeholder*="UPI ID" i]',
      'input[placeholder*="Enter UPI" i]',
      'input[placeholder*="VPA" i]',
      'input[placeholder*="@" i]',
      'input[name*="vpa" i]',
      'input[name*="upi" i]',
      'input[type="email"]',
    ], 20000);

    if (!upiInput) {
      await screenshot(page, "04-no-upi-input");
      throw new Error("UPI ID input field not found");
    }
    console.log("    Filling UPI ID: success@razorpay");
    await upiInput.fill("success@razorpay");
    await page.waitForTimeout(500);
    await screenshot(page, "04-upi-filled");

    // ── Click Pay button ─────────────────────────────────────────────────────
    console.log("    Looking for Pay/Verify and Pay button...");
    const payBtn = await findVisible(page, [
      'button:has-text("Verify and Pay")',
      'button:has-text("Pay Now")',
      'button:has-text("Pay ₹")',
      'button:has-text("Pay")',
    ], 10000);

    if (!payBtn) {
      await screenshot(page, "05-no-pay-btn");
      throw new Error("Pay button not found after UPI input");
    }
    console.log("    Clicking Pay button...");
    await payBtn.click({ force: true });
    await screenshot(page, "05-after-pay-click");

    // ── Wait for payment result ───────────────────────────────────────────────
    console.log("    Waiting for payment completion (up to 60s)...");
    let result = null;
    for (let i = 0; i < 120; i++) {
      result = await page.evaluate(() => window.paymentResult || null);
      if (result && result.razorpay_payment_id) break;
      const dismissed = await page.evaluate(() => window.paymentDismissed || false);
      if (dismissed) throw new Error("Razorpay Checkout modal was dismissed");
      if (i % 10 === 9) await screenshot(page, `06-waiting-${i}`);
      await page.waitForTimeout(500);
    }

    if (!result || !result.razorpay_payment_id || !result.razorpay_order_id || !result.razorpay_signature) {
      await screenshot(page, "06-checkout-timeout");
      throw new Error("Checkout did not return payment result: " + JSON.stringify(result));
    }
    console.log("    CHECKOUT: PASS", result.razorpay_payment_id);

    await browser.close();
    browser = null;
    server.close();

    // ── Step 6: POST /verify (checks with Razorpay API, updates DB) ──────────
    console.log("[6] Verifying payment with backend...");
    const verify = await api("/api/v1/payments/verify", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
      body: JSON.stringify({
        razorpay_order_id: result.razorpay_order_id,
        razorpay_payment_id: result.razorpay_payment_id,
        razorpay_signature: result.razorpay_signature,
      }),
    });
    if (verify.status !== "captured") throw new Error("Verify status wrong: " + verify.status);
    console.log("    SIGNATURE VERIFY: PASS");

    // ── Step 7: Check /history shows captured ────────────────────────────────
    console.log("[7] Checking payment history shows captured...");
    let row = null;
    for (let i = 0; i < 30; i++) {
      const h = await api("/api/v1/payments/history", { headers: { authorization: `Bearer ${token}` } });
      row = h.payments.find(x => x.provider_order_id === order.order_id);
      if (row && row.status === "captured") break;
      await new Promise(r => setTimeout(r, 1000));
    }
    if (!row || row.status !== "captured") {
      throw new Error("Payment history does not show captured: " + JSON.stringify(row));
    }
    if (row.provider_payment_id !== result.razorpay_payment_id) {
      throw new Error(`Payment ID mismatch: history=${row.provider_payment_id} vs result=${result.razorpay_payment_id}`);
    }
    console.log("    PAYMENT CAPTURED IN DB: PASS");

    // ── Step 8: Check plan upgrade ───────────────────────────────────────────
    console.log("[8] Checking account plan upgrade...");
    const me = await api("/api/v1/account/me", { headers: { authorization: `Bearer ${token}` } });
    // /account/me returns { user: { plan_code, ... }, usage: { ... } }
    const planCode = (me.user || me).plan_code;
    if (planCode !== "starter") throw new Error(`Plan not upgraded, got: ${planCode} (full: ${JSON.stringify(me)})`);
    console.log("    PLAN UPGRADE: PASS");

    console.log("\nRAZORPAY FINAL E2E: PASS");

  } finally {
    if (browser) {
      try { await browser.close(); } catch {}
    }
    try { server.close(); } catch {}
  }
})().catch(e => {
  console.error("\nFAILED:", e.stack || String(e));
  process.exit(1);
});
