# 🚀 LinkedIn Discord Job Alert Bot

[_Versiunea în limba română →_](README.ro.md)

<img width="1024" height="572" alt="image" src="https://github.com/user-attachments/assets/ac0a7cdb-dd01-4074-8c41-17460eacd5f0" />


An automated bot that continuously searches LinkedIn for newly posted jobs matching your custom filters and sends real-time, rich embed alerts directly to your Discord webhook.

---

## ✨ Features

- **No Credentials / Login Required**: Uses LinkedIn's public guest search API—no risk to your personal LinkedIn account.
- **Granular Custom Filters**:
  - 🔍 **Keywords & Field**: Search by any title, tech stack, or industry.
  - 📍 **Location & Workplace**: Remote, Hybrid, or On-site worldwide.
  - 🎯 **Experience Levels**: Internship, Entry level, Associate, Mid-Senior, etc.
  - 💼 **Job Types**: Full-time, Contract, Part-time, Internship.
  - 🚫 **Negative Filters (Title & Description Exclusion)**: Automatically filter out unwanted seniority (e.g., exclude *"Senior"*, *"Lead"*, *"Staff"*, *"Principal"*), security clearance requirements, or specific visa constraints.
  - 🏢 **Company Blacklist & Whitelist**: Block staffing agencies or focus on specific companies.
- **Rich Discord Embed Alerts**:
  - Job Title with clickable direct application link.
  - Company name & company logo thumbnail.
  - Location & Workplace type badge (🌐 Remote / 🏢 On-site / 🔀 Hybrid).
  - Seniority, Employment type & Salary (if disclosed).
  - Matched filter tag & relative posting time (*"15 minutes ago"*).
  - Optional Discord Role ID mentions for push notifications.
- **6+ Job Sources (strategy.md)**: LinkedIn (guest API), eJobs.ro, BestJobs.eu, Hipo.ro, StagiiPeBune.ro, plus **universal company ATS scraping** (Greenhouse & Lever APIs) driven by a simple JSON company list — and optional **Google dorking** for custom career pages.
- **Bucharest-only Junior Roles**: Location locked to Bucharest (or Remote), experience level locked to Internship/Entry level, and role keywords covering QA Tester, IT Support, Helpdesk, Pentester & Red Team.
- **30-Minute Freshness Window**: LinkedIn is queried with the `r1800` (past 30 minutes) filter and every result is re-checked against its exact posting timestamp, so you only see jobs posted in the last 30 minutes.
- **Rich Discord Embeds with Apply Link**: Job title (clickable), company, location & workplace badge, seniority, employment type, salary (if disclosed), description snippet and a direct **[apply here]** link.
- **Junior/Internship Safety Filter**: Drops roles with seniority words in the title (*Senior*, *Lead*, *Manager*, *Principal*...) or experience demands like *"5+ years"* / *"5+ ani"* in the description — catching false positives such as senior roles that merely "mentor juniors".
- **Cross-Platform Deduplication**: Merges jobs posted on multiple platforms by the same company with a very similar title (fuzzy matching), so you never get the same role twice.
- **Smart Duplicate Prevention**: Tracks every alerted job in a local SQLite database to prevent duplicate alerts across restarts.
- **Polite Scraping & Anti-Rate-Limit**: Rotates desktop browser User-Agents, adds random jitter delays, and handles Discord & LinkedIn 429 backoff gracefully.

---

## 📁 Project Structure

```text
Linkedin/
├── config.yaml          # Active configuration (filters, searches, schedule)
├── config.example.yaml  # Reference template configuration
├── .env                 # Environment variables (DISCORD_WEBHOOK_URL)
├── main.py              # CLI entry point (run, scan-once, test-webhook, stats, jobs)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker container configuration
├── docker-compose.yml   # Docker Compose deployment
├── config.yaml          # Active configuration (search profiles, platforms, filters)
├── data/
│   ├── jobs.db          # SQLite database (seen jobs / dedup)
│   └── ats_companies.json # Target companies for Greenhouse/Lever ATS scraping
├── src/
│   ├── config.py        # Config parser and validator
│   ├── database.py      # SQLite storage, dedup & duplicate prevention
│   ├── tracker.py       # Junior role filter engine & status model
│   ├── discord_notifier.py # Discord embed formatter and webhook client
│   ├── runner.py        # Orchestration and daemon scheduler
│   ├── utils.py         # User-agent rotation & formatting helpers
│   └── scraper/
│       ├── models.py    # JobPost & SearchProfile dataclasses
│       ├── base.py      # BaseScraper interface + registry pattern
│       ├── linkedin.py  # LinkedIn guest API scraper and filter engine
│       ├── ejobs.py     # eJobs.ro scraper
│       ├── bestjobs.py  # BestJobs.eu scraper
│       ├── hipo.py      # Hipo.ro scraper
│       ├── stagiipebune.py # StagiiPeBune.ro internships scraper
│       ├── ats.py       # Universal Greenhouse/Lever ATS scraper
│       └── googledork.py # Optional Google dorking for custom career pages
└── tests/
    └── test_bot.py      # Unit test suite
```

---

## ⚡ Quick Start Guide

### 1. Clone & Setup Python Environment

```bash
# Navigate to project directory
cd Linkedin

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Discord Webhook

1. In Discord, go to **Server Settings** -> **Integrations** -> **Webhooks** -> **New Webhook**.
2. Copy the **Webhook URL**.
3. Create your `.env` file:
```bash
cp .env.example .env
```
4. Open `.env` and paste your webhook URL:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdef...
```

### 3. Test Your Discord Webhook

Verify that Discord receives notifications:
```bash
python main.py test-webhook
```

---

## ⚙️ Customizing Filters (`config.yaml`)

Edit [config.yaml](file:///Users/paius/Desktop/proiecte/Linkedin/config.yaml) to customize your searches and filters:

```yaml
settings:
  check_interval_minutes: 15     # Check every 15 minutes
  request_delay_seconds: 3.0     # Delay between requests
  max_pages_per_search: 1        # 25 jobs per page
  fetch_job_details: true        # Fetch full description & criteria

searches:
  - name: "🐍 Python Developer (Junior / Mid)"
    enabled: true
    embed_color: "#3776AB"       # Hex color for embed sidebar
    keywords: "Python Developer"
    location: "Remote"
    date_posted: "past_24h"      # past_24h, past_week, past_month, any
    sort_by: "recent"            # recent (newest first) or relevant
    
    # Workplace Types: remote, hybrid, on_site
    workplace_types:
      - "remote"
    
    # Experience Levels: internship, entry_level, associate, mid_senior, director, executive
    experience_levels:
      - "internship"
      - "entry_level"
      - "associate"
      - "mid_senior"
      
    # Job Types: full_time, part_time, contract, temporary, internship
    job_types:
      - "full_time"
      - "contract"

    # Custom Keyword Filters
    filters:
      # Job title MUST match at least one keyword (case-insensitive)
      title_must_include:
        - "Python"
        - "Backend"
        - "FastAPI"
        - "Django"
        
      # Job title MUST NOT contain any of these keywords
      title_must_exclude:
        - "Senior"
        - "Lead"
        - "Staff"
        - "Principal"
        - "Director"
        - "Architect"
        
      # Description exclusions (e.g. security clearances or visa blocks)
      description_must_exclude:
        - "security clearance required"
        - "US citizenship required"
        
      # Company blacklist
      companies_exclude:
        - "Revature"
```

---

## 🌐 Job Sources & How to Extend Them

All scrapers follow `strategy.md` and are registered in `src/scraper/__init__.py`. Enable/disable them per search profile via the `platforms` list in `config.yaml`.

| Platform code | Site | Notes |
| :--- | :--- | :--- |
| `linkedin` | LinkedIn | Public guest API, no login needed; `past_30min` freshness filter |
| `ejobs` | eJobs.ro | Pre-built Bucharest search URLs |
| `bestjobs` | BestJobs.eu | Keyword + Bucharest search parameters |
| `hipo` | Hipo.ro | Bucharest IT category (site occasionally down — degrades gracefully) |
| `stagiipebune` | StagiiPeBune.ro | Dedicated IT internship board (100% junior) |
| `ats` | Company career pages | Universal Greenhouse + Lever API scraping |
| `google` | Custom career pages | Optional Google dorking (see below) |

**Company ATS scraping** — instead of one scraper per company, add boards to
[data/ats_companies.json](data/ats_companies.json) and the two universal
parsers cover dozens of companies automatically:

```json
{
    "greenhouse": ["bitpanda", "fingerprint"],
    "lever": ["some-lever-company"]
}
```

> Find the board name in a company's job URL: `...greenhouse.io/**bitpanda**/jobs/...`
> or `jobs.lever.co/**company-name**/...`. Only Bucharest/remote roles are kept.

**Google dorking** (catches custom-built career sites) — add `"google"` to a
profile's `platforms` list. Requires `googlesearch-python` (already in
`requirements.txt`). Google aggressively rate-limits scrapers, so expect
flaky results here; every failure is handled gracefully.

---

## 🛠️ CLI Commands

| Command | Description |
| :--- | :--- |
| `python main.py run` | Start continuous monitoring daemon (checks every 30 minutes). |
| `python main.py scan-once` | Run a single scan across all profiles and exit (great for cron/CI). |
| `python main.py test-webhook` | Send a test notification to verify your Discord webhook. |
| `python main.py stats` | View database stats (jobs indexed, alerts sent, recent jobs). |
| `python main.py jobs` | List discovered jobs with status (`--status NEW`, `--platform`, `--limit`). |
| `python main.py validate` | Inspect and validate `config.yaml` syntax and active profiles. |
| `python main.py reset-db` | Clear database history to re-scan from scratch. |

---

## ☁️ Free 24/7 Hosting on GitHub Actions

You don't need your own computer running for the bot to work — GitHub runs it for free:

[.github/workflows/job_monitor.yml](.github/workflows/job_monitor.yml) runs
`python main.py scan-once` every 30 minutes and commits the updated
`data/jobs.db` back to the repo (this is what prevents duplicate alerts
between runs).

**Setup:**

1. Push this repository to GitHub.
2. Go to **Settings → Secrets and variables → Actions** and add
   `DISCORD_WEBHOOK_URL` with your webhook.
3. Trigger a first run manually from the **Actions** tab (*Run workflow*),
   then it keeps running on schedule. *(Note: scheduled workflows can be
   delayed a few minutes and are paused after 60 days of repo inactivity.)*

> ⚠️ Never commit your webhook URL or tokens to the repository — keep them
> in GitHub Action secrets.

---

## 🐳 Running with Docker

You can run the bot 24/7 inside a lightweight Docker container:

```bash
# Build and run in background
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

---

## ⏰ Running via Cron / Scheduled Job

If you prefer to run single scans on a schedule rather than keeping a daemon process alive:

```bash
# Add to crontab (runs every 30 minutes)
*/30 * * * * cd /path/to/Linkedin && .venv/bin/python3 main.py scan-once >> /tmp/job_bot.log 2>&1
```

---

## 🧪 Running Tests

To run the unit test suite:
```bash
python -m unittest discover tests
```
