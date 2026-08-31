# Development Plan: Romanian Junior Cyber Job Tracker

This plan outlines the architecture, technology stack, and step-by-step development phases for building an automated job tracker tailored for junior/internship positions in the cybersecurity and IT support fields in Romania.

## 1. Project Scope & Requirements

### Target Audience & Roles
*   **Levels:** Junior, Entry-Level, Internship, 0-2 years experience.
*   **Keywords/Roles:** QA Tester, IT Support, Helpdesk, Pentester, Red Team, SOC Analyst, Junior Cybersecurity.
*   **Location:** Romania (Remote, Hybrid, or On-site in major cities like Bucharest, Cluj, Timisoara, Iasi).

### Target Data Sources (Job Boards & Company Portals)
*   **LinkedIn** (filtered for Romania)
*   **eJobs.ro**
*   **BestJobs.eu**
*   **Hipo.ro** (excellent for student/internship roles)
*   **StagiiPeBune.ro** (specifically for IT internships in Romania)
*   **Company Portals:** Direct scraping of specific companies' career pages (e.g., Bitdefender, CrowdStrike, Atos, local banks, etc.)

### Key Features
*   Automated daily scraping of the target job boards.
*   Filtering logic to ensure only junior/internship roles are saved.
*   Deduplication (merging jobs posted on multiple platforms by the same company).
*   Notification system (e.g., Telegram bot, Discord webhook) for immediate alerts on new listings.
*   Dashboard/UI to view, filter, and track application status (Applied, Interviewing, Rejected).

---

## 2. Technology Stack Recommendations

*   **Backend & Scraping:** Python
    *   *Libraries:* `BeautifulSoup4` and `Requests` (for static sites), `Playwright` (preferred over Selenium for dynamic sites like LinkedIn), `Scrapy` (for robust, large-scale scraping).
*   **Database:** 
    *   *Starting out:* `SQLite` (simple, file-based, easy to set up).
    *   *Scaling:* `PostgreSQL` (robust, better if deploying to the cloud).
*   **Frontend/Dashboard:** 
    *   *Fast setup:* `Streamlit` (pure Python, excellent for data dashboards).
*   **Scheduling:** `Cron` (Linux) or `APScheduler` (Python-native).
*   **Notifications:** Discord Webhooks (via HTTP POST) to send formatted job offers.

---

## 3. Development Phases

### Phase 1: Setup & Basic Scraping (MVP)
*   [x] Initialize a Python project with virtual environment.
*   [x] Create a basic SQLite database schema (`jobs` table: `id`, `title`, `company`, `location`, `url`, `platform`, `date_posted`, `status`).
*   [x] Build the first scraper for an accessible platform (e.g., eJobs or Hipo).
    *   Extract job title, company, link, and location.
*   [x] Save the scraped data to the database.

### Phase 2: Expanding Sources & Advanced Scraping
*   [ ] Integrate Playwright for JavaScript-heavy sites (LinkedIn). *(not needed: the public guest API returns full search results with all filters applied, without login/ban risk)*
*   [x] Build scrapers for BestJobs and StagiiPeBune. *(verified live: `src/scraper/bestjobs.py`, `src/scraper/stagiipebune.py`; Hipo.ro also implemented but the site is in maintenance until Sep 4, 2026)*
*   [x] Standardize the data output from all scrapers into a single format (e.g., a Pydantic model) before saving to the DB. *(implemented via the `JobPost` dataclass)*
*   [x] Universal ATS scrapers for company career pages (Greenhouse + Lever) driven by `data/ats_companies.json` — `src/scraper/ats.py`.
*   [x] Optional automated Google dorking for custom career sites — `src/scraper/googledork.py` (enable with `"google"` in a profile's `platforms`).

### Phase 3: Data Filtering & Enrichment
*   [x] Implement a keyword filtering engine (`src/tracker.py` → `JuniorRoleFilter`):
    *   **Include list:** "junior", "intern", "internship", "entry level", "entry-level".
    *   **Exclude list:** "senior", "lead", "manager", "5+ years", "principal".
    *   Configurable via `config.yaml` (`junior_filter_enabled`, `junior_filter_strict`, keyword list overrides).
*   [x] Deduplication logic: Check if a job with a very similar title and the same company already exists in the database. *(fuzzy token matching; duplicates are marked `DUPLICATE` and not re-alerted)*

### Phase 4: Notifications & Automation
*   [x] Create a Discord Webhook in your target server/channel and get the webhook URL.
*   [x] Write a script that checks the database for jobs added in the last 24 hours (or since last run) and sends a formatted rich-embed message to the Discord Webhook.
*   [x] Set up a scheduler (daemon mode via `python main.py run`, or a daily cron job with `scan-once`).

### Phase 5: Application Tracking Interface (The "Tracker")
*   [x] **Skipped by decision** — Discord alerts already include all job details and a direct apply link, so a separate dashboard/tracker UI is not needed. The SQLite status vocabulary (NEW/APPLIED/...) is kept for dedup bookkeeping only.

### Phase 6: Deployment
*   [x] Create a `requirements.txt`.
*   [x] Dockerize the application to ensure it runs consistently anywhere.
*   [x] Free 24/7 hosting via GitHub Actions (scheduled scraping + Discord alerts, `data/jobs.db` committed back for deduplication). VPS deployment (Hetzner/DigitalOcean/Raspberry Pi) remains an alternative.

---

## 4. Potential Challenges & Solutions
1.  **Anti-Scraping Defenses:** Sites like LinkedIn aggressively block frequent automated requests. 
    *   *Solution:* Use Playwright with stealth plugins, add random human-like delays, rotate User-Agents. If needed, scrape without logging in, as logged-in accounts get banned quickly.
2.  **Structural Changes on Target Sites:** Job boards change their HTML/CSS frequently, which will break your scrapers.
    *   *Solution:* Keep CSS selectors as generic as possible. Set up error logging so you know exactly which scraper failed and why.
3.  **False Positives:** A senior role description might say "will mentor juniors" and pass the include filter.
    *   *Solution:* Ensure the "Exclude list" is strong. For ultimate accuracy, you could pass the job description to a fast LLM (like Gemini Flash) to ask: "Is this a junior/internship role?" (Though this adds cost/complexity).
