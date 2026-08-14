const { chromium } = require("playwright");
const fs = require("fs");
const cp = require("child_process");
const base = process.env.BASE_URL, email = process.env.EMAIL, password = process.env.PASSWORD;
async function api(path,opt={}) { const r=await fetch(base+path,opt), t=await r.text(); let d; try{d=JSON.parse(t)}catch{d={raw:t}} if(!r.ok) throw new Error(`${path}: HTTP ${r.status} ${t}`); return d; }
(async()=>{
 const login=await api("/api/v1/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email,password})});
 const token=login.session.access_token;
 const order=await api("/api/v1/payments/orders",{method:"POST",headers:{"content-type":"application/json",authorization:`Bearer ${token}`},body:JSON.stringify({plan_code:"starter"})});
 fs.writeFileSync("/tmp/rzp-index.html",`<!doctype html><button id="pay">Pay</button><script src="https://checkout.razorpay.com/v1/checkout.js"></script><script>const o={key:${JSON.stringify(order.razorpay_key_id)},amount:${order.amount_inr_paise},currency:"INR",name:"Job Finder Test",order_id:${JSON.stringify(order.order_id)},prefill:{name:"CI Test User",email:${JSON.stringify(email)},contact:"+919999999999"},handler:r=>window.paymentResult=r};const z=new Razorpay(o);document.getElementById("pay").onclick=()=>z.open();</script>`);
 cp.execFileSync("openssl",["req","-x509","-newkey","rsa:2048","-nodes","-keyout","/tmp/rzp-key.pem","-out","/tmp/rzp-cert.pem","-days","1","-subj","/CN=localhost"],{stdio:"ignore"});
 const py=cp.spawn("python3",["-c",`import http.server,ssl,os;os.chdir('/tmp');s=http.server.HTTPServer(('127.0.0.1',4173),http.server.SimpleHTTPRequestHandler);s.socket=ssl.wrap_socket(s.socket,certfile='/tmp/rzp-cert.pem',keyfile='/tmp/rzp-key.pem',server_side=True);s.serve_forever()`],{stdio:"ignore"});
 const b=await chromium.launch({headless:true}); const p=await b.newPage({ignoreHTTPSErrors:true,viewport:{width:1280,height:900}});
 await p.goto("https://127.0.0.1:4173/rzp-index.html?x="+Date.now()); await p.getByRole("button",{name:"Pay"}).click();
 let cards=null; for(let i=0;i<90&&!cards;i++){ for(const f of p.frames()){try{const x=f.locator('[data-testid="Cards"]').first();if(await x.count()&&await x.isVisible()){cards=x;break}}catch{}} if(!cards) await p.waitForTimeout(500); }
 if(!cards) throw new Error("Cards option not found"); await cards.click({force:true});
 const card=p.locator('input[autocomplete="cc-number"]').first(); await card.waitFor({state:"visible",timeout:30000}); await card.fill("410028000001007"); await p.locator('input[autocomplete="cc-exp"]').fill("12/30"); await p.locator('input[autocomplete="cc-csc"]').fill("123"); await p.getByRole("button",{name:/pay/i}).last().click({force:true});
 for(let i=0;i<120;i++){ for(const f of p.frames()){try{const otp=f.locator('input[placeholder*="OTP" i],input[name*="otp" i]').first();if(await otp.count()&&await otp.isVisible()){await otp.fill("1234");const s=f.getByRole("button",{name:/submit|verify|pay/i}).last();if(await s.count()&&await s.isVisible())await s.click({force:true})}}catch{}} if(await p.evaluate(()=>!!window.paymentResult)) break; await p.waitForTimeout(500); }
 const result=await p.evaluate(()=>window.paymentResult); if(!result?.razorpay_payment_id||!result?.razorpay_order_id||!result?.razorpay_signature) throw new Error("Checkout result missing: "+JSON.stringify(result)); console.log("CHECKOUT: PASS");
 let row=null; for(let i=0;i<60;i++){const h=await api("/api/v1/payments/history",{headers:{authorization:`Bearer ${token}`}});row=h.payments.find(x=>x.provider_order_id===order.order_id);if(row?.status==="captured")break;await new Promise(r=>setTimeout(r,1000));} if(!row||row.status!=="captured"||row.provider_payment_id!==result.razorpay_payment_id) throw new Error("Webhook did not capture payment"); console.log("WEBHOOK CAPTURED: PASS");
 const v=await api("/api/v1/payments/verify",{method:"POST",headers:{"content-type":"application/json",authorization:`Bearer ${token}`},body:JSON.stringify({razorpay_order_id:result.razorpay_order_id,razorpay_payment_id:result.razorpay_payment_id,razorpay_signature:result.razorpay_signature})}); if(v.status!=="captured") throw new Error("Verification failed"); console.log("SIGNATURE VERIFY: PASS");
 const me=await api("/api/v1/account/me",{headers:{authorization:`Bearer ${token}`}}); if(me.plan_code!=="starter") throw new Error("Plan upgrade missing"); console.log("PLAN UPGRADE: PASS"); await b.close(); py.kill(); console.log("RAZORPAY FINAL E2E: PASS");
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
