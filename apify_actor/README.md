# LinkedIn & Naukri Job Scraper

A powerful actor that scrapes job listings from **LinkedIn** and **Naukri** with advanced filtering options. Returns structured job data including title, company, location, salary, experience requirements, and more.

## Features

✅ **Dual Platform Support** — Scrape from LinkedIn or Naukri in a single run  
✅ **Advanced Filtering** — Filter by location, experience, work mode (remote/hybrid/on-site)  
✅ **Easy Apply Detection** — LinkedIn only: identify jobs with one-click apply  
✅ **Structured Output** — Get jobs in clean JSON format, ready for import or analysis  
✅ **Rate Limited** — Respectful scraping that doesn't overload the platforms  
✅ **Error Handling** — Gracefully handles rate limits and connectivity issues  

## Use Cases

- **Recruitment**: Bulk search for candidates across job markets
- **Market Research**: Track job trends, salary movements, hiring patterns
- **Career Planning**: Monitor job availability in your field and location
- **Job Alerts**: Build automated job search workflows
- **Data Analysis**: Analyze job market data for insights
- **Integration**: Feed job data into your own applications

## Input Parameters

All parameters are JSON. Required fields marked with **\***:

| Field | Type | Default | Example | Description |
|-------|------|---------|---------|-------------|
| **platform*** | string | - | `"linkedin"` | Which platform to scrape: `"linkedin"` or `"naukri"` |
| **job_title*** | string | - | `"React Developer"` | Job title or keywords to search for |
| **location*** | string | - | `"San Francisco"` | City or region to search in |
| experience | string | "" | `"3 years"` | Required experience level (e.g., "2 years", "5+ years") |
| work_mode | string | `"any"` | `"remote"` | Type of work: `"remote"`, `"hybrid"`, `"on-site"`, or `"any"` |
| easy_apply | boolean | `false` | `true` | **LinkedIn only**: Return only jobs with easy apply option |
| posted_within | string | `"any"` | `"week"` | Job posting recency: `"day"`, `"week"`, `"month"`, or `"any"` (LinkedIn only) |
| maxResults | integer | `100` | `50` | Maximum number of results to return (1-100) |

## Output Format

Each job record contains:

```json
{
  "platform": "linkedin",
  "job_id": "3742068459",
  "title": "Senior React Developer",
  "company": "Tech Corp",
  "location": "San Francisco, CA",
  "salary": "$120,000 - $160,000",
  "experience": "5+ years",
  "easy_apply": true,
  "work_mode": "Remote",
  "job_url": "https://linkedin.com/jobs/view/3742068459",
  "apply_url": "https://linkedin.com/jobs-guest/apply/...",
  "description": "We're looking for an experienced React developer...",
  "company_logo": "https://logo.clearbit.com/techcorp.com",
  "posted_at": "2024-08-03T10:30:00Z",
  "posted_within": "1 week ago",
  "status": "NEW"
}
```

## Example Runs

### Example 1: Find Remote React Jobs on LinkedIn

**Input:**
```json
{
  "platform": "linkedin",
  "job_title": "React Developer",
  "location": "Remote",
  "work_mode": "remote",
  "maxResults": 50
}
```

**Output:** 50 remote React developer jobs from LinkedIn worldwide

---

### Example 2: Naukri Jobs in Pune

**Input:**
```json
{
  "platform": "naukri",
  "job_title": "Python Engineer",
  "location": "Pune",
  "experience": "3 years",
  "maxResults": 100
}
```

**Output:** Up to 100 Python engineer jobs in Pune with 3+ years requirement

---

### Example 3: Easy Apply Only (LinkedIn)

**Input:**
```json
{
  "platform": "linkedin",
  "job_title": "Data Scientist",
  "location": "New York",
  "easy_apply": true,
  "posted_within": "week"
}
```

**Output:** Data Science jobs posted in the last week with one-click apply option

---

## Pricing & Credits

Each run consumes Apify credits based on:
- **Typical job search**: 50 jobs ≈ $0.50 - $1.00 in credits
- **Large job search**: 100 jobs ≈ $1.00 - $2.00 in credits
- **Exact pricing**: Depends on platform load and your Apify plan

## Rate Limits & Best Practices

- **Max results per run**: 100 jobs (for speed and stability)
- **Recommended**: Run multiple searches with different parameters rather than one massive search
- **Rate limiting**: Built-in delays respect platform limits (no IP bans)
- **Sessions**: LinkedIn/Naukri sessions must be pre-configured (see Setup below)

## Setup Requirements

### LinkedIn
1. Log in to LinkedIn at least once via browser to create a session
2. The actor uses your saved session for authenticated requests
3. Session persists across runs (valid for weeks typically)
4. If rate limited, Apify handles retries automatically

### Naukri
1. Log in to Naukri at least once via browser to create a session
2. Same session persistence as LinkedIn
3. Less strict rate limiting than LinkedIn

## Common Issues

### "Access Denied" or "Auth Wall"

**Cause:** Your LinkedIn/Naukri session has expired or isn't set up  
**Fix:** Run the actor's setup script to re-authenticate, or contact support

### 0 Results Returned

**Possible causes:**
- No jobs match your filters (try broader location or skill)
- Typo in job_title or location
- Platform temporarily blocking due to rate limit (temporary, retries automatically)

**Fix:** Try a different job_title or location to confirm the actor works

### Timeout Error

**Cause:** Network timeout while scraping (rare)  
**Fix:** Apify automatically retries. If persistent, reduce maxResults and try again.

## Data Freshness

- Jobs updated **daily** as platforms update their listings
- Typical latency: Real-time to a few hours (depends on platform crawl speed)
- Deduplication: Automatic across runs (same job_id = same record)

## API Rate Limits

- **LinkedIn**: ~10 searches per minute per IP (actor handles transparently)
- **Naukri**: ~20 searches per minute per IP
- **Apify queues**: Standard Apify queue limits apply

## Support & Updates

- **Bug reports**: Report issues via Apify marketplace
- **Feature requests**: Let us know what you'd like to see
- **Updates**: Platform markup changes handled automatically (we update selectors as needed)

## Disclaimer

This actor respects the robots.txt and terms of service of LinkedIn and Naukri. However:

- LinkedIn and Naukri prohibit scraping in their official terms of service
- This actor uses web automation and may be blocked if detected
- Use of scraped data must comply with each platform's terms
- Neither the author nor Apify is responsible for account suspensions
- Recommended for research, recruitment, and data analysis purposes

## Legal

This actor is provided "as-is" for educational and research purposes. Users are responsible for compliance with platform terms of service. By using this actor, you agree to use it lawfully and responsibly.

## Get Started

1. **Click "Try it now"** to run with default example parameters
2. **Customize inputs** in the input editor
3. **Run** and view results in the dataset
4. **Export** results to JSON, CSV, or integrate via API

---

**Need help?** Check the Apify documentation or reach out via the marketplace chat.

**Happy job hunting! 🚀**
