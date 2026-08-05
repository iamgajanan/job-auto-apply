# Naukri & LinkedIn Job Scraper

Scrape job listings from **Naukri.com** with advanced filtering — by location, experience level, work mode, and posting date. Returns structured job data ready for analysis, import, or integration.

> **LinkedIn support is coming soon.** Star this actor to get notified when it launches.

---

## What You Get

Each job record includes:

```json
{
  "platform": "naukri",
  "job_id": "...",
  "title": "Senior React Developer",
  "company": "Tech Corp Pvt Ltd",
  "location": "Pune",
  "experience": "3-6 Yrs",
  "salary": "8-14 Lacs PA",
  "work_mode": "Hybrid",
  "job_url": "https://www.naukri.com/job-listings-...",
  "description": "Looking for a React developer with...",
  "posted_within": "2 days ago",
  "status": "NEW"
}
```

---

## Input Parameters

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `job_title` | ✅ | — | Job title or keywords (e.g. `"React Developer"`, `"Data Scientist"`) |
| `location` | ✅ | — | City or region (e.g. `"Pune"`, `"Bangalore"`, `"India"`) |
| `experience` | — | any | Years of experience (e.g. `"3 years"`, `"5 years"`) |
| `work_mode` | — | `"any"` | `"remote"`, `"hybrid"`, `"onsite"`, or `"any"` |
| `posted_within` | — | `"any"` | `"day"`, `"week"`, `"month"`, or `"any"` |
| `maxResults` | — | `100` | How many jobs to return (max 100) |

---

## Example Runs

### React Developer jobs in Pune

```json
{
  "job_title": "React Developer",
  "location": "Pune",
  "experience": "3 years",
  "work_mode": "any",
  "posted_within": "week",
  "maxResults": 50
}
```

### Remote Python jobs across India

```json
{
  "job_title": "Python Engineer",
  "location": "India",
  "work_mode": "remote",
  "posted_within": "month",
  "maxResults": 100
}
```

### Senior Data Scientist in Bangalore

```json
{
  "job_title": "Data Scientist",
  "location": "Bangalore",
  "experience": "5 years",
  "maxResults": 100
}
```

---

## Use Cases

- **Recruitment** — bulk search for candidates across job markets
- **Job alerts** — run on a schedule to track new postings
- **Market research** — analyse job trends, salaries, and hiring patterns
- **Career planning** — monitor demand for your skills and location
- **Data pipelines** — feed job data into your own apps or spreadsheets

---

## Performance

- ~50–70 jobs per run for most searches
- Typical runtime: 30–60 seconds
- Filters applied server-side and client-side for accuracy

---

## Disclaimer

This actor uses web automation to collect publicly available job listings from Naukri.com. Use of scraped data must comply with Naukri's terms of service. The actor author is not responsible for how the data is used.

---

## Coming Soon

- ✅ Naukri scraping (available now)
- 🔜 LinkedIn scraping (in development)
- 🔜 Scheduled runs + email alerts
- 🔜 Export to Google Sheets
