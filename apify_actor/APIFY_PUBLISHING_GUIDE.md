# Publishing Guide: LinkedIn & Naukri Job Scraper to Apify

This guide walks you through publishing your actor to the Apify marketplace and starting to earn revenue.

---

## Prerequisites

1. **Apify Account**
   - Sign up at https://apify.com (free account required)
   - Verify email
   - Set up payment method (Stripe)

2. **Local Testing** ✅
   - Actor code complete (you have this)
   - Tested locally or in Apify Studio
   - Input/output validated

3. **Files Prepared** ✅
   - `actor.json` — metadata
   - `INPUT_SCHEMA.json` — parameters
   - `Dockerfile` — container definition
   - `README.md` — marketplace documentation
   - `main.py` — entry point
   - `EXAMPLE_INPUT.json` + `EXAMPLE_OUTPUT.json` — for marketplace preview

---

## Step 1: Prepare Your Repository

All files must be in the correct structure:

```
backend/apify_actor/
├── actor.json
├── INPUT_SCHEMA.json
├── Dockerfile
├── README.md
├── main.py
├── EXAMPLE_INPUT.json
├── EXAMPLE_OUTPUT.json
└── .gitignore (optional)
```

**Create .gitignore** to exclude unnecessary files:

```gitignore
__pycache__/
*.pyc
.env
.venv/
venv/
*.log
```

---

## Step 2: Push to GitHub (Required by Apify)

Apify requires your actor code to be in a public GitHub repository. They pull from there to build and publish.

1. **Create GitHub repo** (public)
   - Name it something like: `job-scraper-apify-actor`
   - Add description: "LinkedIn & Naukri job scraper actor for Apify"

2. **Push code**
   ```bash
   cd backend/apify_actor
   git init
   git add .
   git commit -m "Initial actor commit"
   git remote add origin https://github.com/YOUR_USERNAME/job-scraper-apify-actor
   git push -u origin main
   ```

3. **Make sure these files are in root**:
   - `actor.json`
   - `Dockerfile`
   - `README.md`
   - `INPUT_SCHEMA.json`
   - Everything else

---

## Step 3: Test in Apify Studio

Before publishing to marketplace, test your actor in Apify's free sandbox:

1. **Open Apify Console**
   - Go to https://console.apify.com
   - Click "Create new" → "Start from GitHub"

2. **Link your GitHub repo**
   - Paste your repo URL
   - Apify clones it and builds the Docker image

3. **Test the build**
   - Click "Build" → watch the Docker build progress
   - Should complete in 2-5 minutes
   - If errors: fix in actor code, push to GitHub, rebuild

4. **Test a run**
   - Click "Run" → fill in sample input from `EXAMPLE_INPUT.json`
   - Actor should scrape jobs and push to default dataset
   - Check output matches `EXAMPLE_OUTPUT.json`

5. **Fix any issues**
   - Check logs for errors
   - Update code in GitHub
   - Rebuild + retest
   - Repeat until working

---

## Step 4: Optimize Before Publishing

### Performance
- **Timeout**: Actor should complete in 2-5 minutes for 100 jobs
- **Memory**: ~500MB-1GB typical
- **Reduce resources if possible** (faster = cheaper = more sales)

### Quality
- **Error messages**: Clear and helpful
- **Documentation**: Complete and example-rich
- **Input validation**: Reject bad inputs early with good messages
- **Logging**: Use `app_logger` to show progress

### Compliance
- Check `README.md` has legal disclaimer about platform ToS
- Mention it respects rate limits
- Clarify data is for research/recruitment

---

## Step 5: Configure Pricing

### Apify Marketplace Model

Apify actors charge users **per run**. Users buy credits, your actor consumes credits, you get ~60-70% of revenue.

**Example pricing structure:**

| Scenario | Estimated Credit Cost | Your Revenue |
|----------|----------------------|--------------|
| Small (20 jobs) | $0.50 | $0.30 |
| Medium (50 jobs) | $1.00 | $0.60 |
| Large (100 jobs) | $2.00 | $1.20 |

**How to set pricing:**

Apify uses a **consumption model** (not fixed price). You set:

1. **Base computation cost** — included automatically
2. **Memory usage** — optimize to reduce this
3. **Run duration** — faster = cheaper

**Recommended approach:**
- No extra charges beyond Apify's default
- Just build an efficient actor
- Apify calculates cost based on compute usage
- Your revenue is fixed percentage (60-70%)

**To maximize revenue:**
- Make actor fast (runs complete in <3 min)
- Use minimal memory (500MB is good)
- Efficient scraping (don't re-scrape same data)

---

## Step 6: Publish to Marketplace

Once tested and optimized:

1. **Open Apify Console**
   - Select your actor
   - Click "..." menu → "Publish to Marketplace"

2. **Fill out marketplace listing**
   - **Title**: "LinkedIn & Naukri Job Scraper" (required)
   - **Description**: Use your `README.md` (auto-filled)
   - **Category**: Select "Data scraping" + "Jobs" (if available)
   - **Tags**: `scraping, jobs, linkedin, naukri, careers, recruitment, web-scraping`
   - **Actor image**: Upload a logo/screenshot (optional but recommended)
   - **Source code link**: GitHub URL (pre-filled)

3. **Review & Publish**
   - Apify reviews your actor (usually 1-2 days)
   - Check compliance: legal disclaimer, input validation, docs
   - If approved: goes live on marketplace
   - If rejected: they'll email specific reasons

4. **Monitor approval**
   - Email from Apify when approved
   - Actor becomes searchable on marketplace
   - Shows up in "Data Scraping" category
   - Customers can now purchase and run it

---

## Step 7: Post-Launch Optimization

### First Week
- Monitor error logs (fix any issues ASAP)
- Respond to customer issues quickly
- Track usage metrics (runs, errors, revenue)

### Ongoing
- Update actor when LinkedIn/Naukri changes markup
- Add features based on customer requests (new filters, etc.)
- Improve documentation based on support tickets
- Fix bugs within 24 hours

### Marketing
- Link to your actor from your personal portfolio/blog
- Share on relevant communities (Reddit: r/jobs, r/learnprogramming, etc.)
- Consider writing a blog post: "I built a job scraper, here's how"
- Reply helpfully to reviews/ratings

---

## Pricing Strategy Recommendations

### Conservative (Most Likely to Succeed)
- **Rely on Apify's default pricing** (don't add extra markup)
- **Volume play**: Attract many users with fair pricing
- **Estimated revenue**: $200-1000/month at 10-50 concurrent users
- **Time to profitability**: 2-3 months

### Premium
- **Optimize heavily for speed** (reduces Apify costs)
- **Price at top tier** (users pay more, you get most of it)
- **Target recruitment agencies** (willing to pay more)
- **Estimated revenue**: $500-3000/month at 20-100 premium users
- **Time to profitability**: 1-2 months

### Hybrid
- **Free tier**: Limited searches (10/month) → attracts users
- **Paid tiers**: $4.99/month (100 searches), $14.99/month (500 searches)
- **Enterprise**: Custom (contact us)
- **Note**: Free tier means YOU absorb some cost, so consider carefully
- **Estimated revenue**: $1000+/month once established

**Recommendation for you**: Start with **conservative approach**. Let Apify's default pricing handle it. Once you have 50+ users, you'll see demand patterns and can optimize.

---

## Revenue Breakdown Example

**Scenario**: 30 users, each runs actor 5x/month = 150 runs/month

| Cost Factor | Amount |
|------------|--------|
| Total Apify credits consumed | $60 |
| Your revenue (70% cut) | **$42** |
| Your revenue per month | **$42** |
| Annual revenue (running cost) | **~$500/year** (before growth) |

Once you optimize and scale to 300 users (1500 runs/month):
- Total Apify credits: $600/month
- Your revenue: $420+/month
- **Annual revenue: $5000+**

---

## Troubleshooting Publishing Issues

### "Docker build failed"
- Check `Dockerfile` syntax
- Verify all copied files exist
- Ensure base image is correct (`apify/actor-python:3.11`)
- Check `requirements.txt` has valid packages

### "Actor rejected by Apify review"
- Ensure `README.md` has legal disclaimer
- Input validation must reject bad inputs early
- No hardcoded API keys or credentials
- Logging must be reasonable (not too noisy)

### "High error rate in production"
- Check LinkedIn/Naukri sessions are fresh
- Verify network connectivity
- Test with different job titles/locations
- Add retry logic for transient failures
- Check rate limiting isn't too aggressive

---

## Support Channels

If stuck:

1. **Apify Docs**: https://docs.apify.com/actors
2. **Apify Community**: https://discord.gg/jyEM2PRqaS (Discord)
3. **GitHub Issues**: Users report problems (respond quickly!)
4. **Email Support**: Apify provides for marketplace actors

---

## Next Steps After Launch

1. **Week 1-2**: Monitor performance, fix critical issues
2. **Month 1**: Gather customer feedback, identify improvement areas
3. **Month 2+**: Add features (more filters, export formats, etc.)
4. **Quarter 2**: Consider LinkedIn easy-apply with auto-application (if legal path exists)

---

## Earnings Timeline Projection

| Month | Estimated Runs | Estimated Revenue | Notes |
|-------|----------------|------------------|-------|
| Month 1 | 50-100 | $30-60 | Launch, early adopters |
| Month 2 | 200-300 | $120-180 | Word-of-mouth growth |
| Month 3 | 500-1000 | $300-600 | Marketplace visibility increases |
| Month 6 | 2000-5000 | $1200-3000 | Organic traffic, reputation |
| Month 12 | 5000-20000 | $3000-12000 | Established, possibly featured |

These are estimates. Actual numbers depend on actor quality, marketing, and niche demand.

---

**Good luck launching! 🚀 Your actor is high-quality and should do well on Apify.**
