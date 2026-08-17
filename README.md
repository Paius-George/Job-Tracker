# 🚀 LinkedIn Discord Job Alert Bot

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
- **Multi-Search Profiles**: Monitor multiple roles simultaneously (e.g., Python Backend, AI Engineer, React Frontend) with custom colors and separate webhooks.
- **Smart Duplicate Prevention**: Tracks every notified and discovered job in a local SQLite database to prevent duplicate alerts across restarts.
- **Polite Scraping & Anti-Rate-Limit**: Rotates desktop browser User-Agents, adds random jitter delays, and handles Discord & LinkedIn 429 backoff gracefully.

---

## 📁 Project Structure

```text
Linkedin/
├── config.yaml          # Active configuration (filters, searches, schedule)
├── config.example.yaml  # Reference template configuration
├── .env                 # Environment variables (DISCORD_WEBHOOK_URL)
├── main.py              # CLI entry point (run, scan-once, test-webhook, stats)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker container configuration
├── docker-compose.yml   # Docker Compose deployment
├── src/
│   ├── config.py        # Config parser and validator
│   ├── database.py      # SQLite storage for duplicate prevention
│   ├── discord_notifier.py # Discord embed formatter and webhook client
│   ├── runner.py        # Orchestration and daemon scheduler
│   ├── utils.py         # User-agent rotation & formatting helpers
│   └── scraper/
│       ├── models.py    # JobPost & SearchProfile dataclasses
│       └── linkedin.py  # LinkedIn guest API scraper and filter engine
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

## 🛠️ CLI Commands

| Command | Description |
| :--- | :--- |
| `python main.py run` | Start continuous monitoring daemon (checks every X minutes). |
| `python main.py scan-once` | Run a single scan across all profiles and exit (great for cron/CI). |
| `python main.py test-webhook` | Send a test notification to verify your Discord webhook. |
| `python main.py stats` | View database stats (jobs indexed, alerts sent, recent jobs). |
| `python main.py validate` | Inspect and validate `config.yaml` syntax and active profiles. |
| `python main.py reset-db` | Clear database history to re-scan from scratch. |

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
# Add to crontab (runs every 15 minutes)
*/15 * * * * cd /path/to/Linkedin && .venv/bin/python3 main.py scan-once >> /tmp/job_bot.log 2>&1
```

---

## 🧪 Running Tests

To run the unit test suite:
```bash
python -m unittest discover tests
```
