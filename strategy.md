# Job Tracker Implementation Strategy

This document outlines the concrete technical ideas and strategies required to build the job tracker, adhering strictly to the constraints provided.

## 1. Strict Search Constraints
To ensure you only receive relevant roles and are the first to apply, the system must enforce these filters:
*   **Location:** **Bucharest only** (or Remote roles that can be done from Bucharest).
*   **Roles:** QA Tester, IT Support, Helpdesk, Pentester, Red Team.
*   **Experience Level:** Junior, Entry-Level, Internship.

---

## 2. Source-Specific Implementation Strategies

### A. Major Job Boards
The most reliable way to scrape these is to pre-build the exact search URLs with all filters applied (Location = Bucharest, Level = Junior/Intern), and then parse the results.

*   **eJobs.ro**
    *   *Strategy:* eJobs uses clean URL parameters. We can construct URLs like `ejobs.ro/locuri-de-munca/bucuresti/it/junior`.
    *   *Parsing:* Use `BeautifulSoup` to find the job cards, extract the title, company, and link.
*   **BestJobs.eu**
    *   *Strategy:* Similar to eJobs, we will utilize their advanced search URL parameters to lock in Bucharest and Entry-Level.
    *   *Parsing:* Standard HTML parsing with `BeautifulSoup`.
*   **LinkedIn (Romania)**
    *   *Strategy:* LinkedIn is highly aggressive against scrapers. We will use `Playwright` to load the page as a real browser.
    *   *Query:* Search specifically for exact phrases: `"qa tester" OR "helpdesk" OR "pentester" OR "it support" OR "red team"`. Filter location strictly to `Bucharest, Romania` and Experience Level to `Internship` and `Entry level`.
*   **Hipo.ro & StagiiPeBune.ro**
    *   *Strategy:* These are highly focused on juniors. We will scrape the Bucharest IT categories. StagiiPeBune often has highly structured tabular data that is very easy to extract.

### B. Company Websites (Direct Scraping)
Instead of building custom scrapers for 50 different company websites, we will use scalable approaches:

*   **Idea 1: Universal ATS Scrapers**
    *   Most companies use standard platforms for their career pages (Greenhouse, Lever, Workday).
    *   We will maintain a JSON list of target Bucharest companies and their ATS links.
    *   We build just 2 or 3 scraper functions (e.g., `parse_greenhouse(url)`, `parse_lever(url)`) that can handle dozens of companies automatically.
*   **Idea 2: Automated Google Dorking**
    *   To catch roles on custom company sites, we will run automated Google queries every few hours.
    *   *Example Query:* `site:*.ro/careers OR site:*.ro/jobs "Bucuresti" AND "junior" AND ("qa tester" OR "helpdesk" OR "pentester")`
    *   *Tooling:* Use a Python library like `googlesearch-python` or SerpAPI to fetch the results and check if they are new.

---

## 3. High-Speed Notification Pipeline (The "Apply First" Edge)
*   **Frequency:** The scraper cron job should run every **30 to 60 minutes**.
*   **Deduplication:** We will use a local `SQLite` database. Before sending an alert, the script checks if the `job_url` or a combination of `company_name + job_title` already exists in the database.
*   **Discord Webhooks:** If a job is new, the script immediately sends an HTTP POST request to a Discord Webhook. The payload will be a rich embed containing:
    *   Job Title
    *   Company Name
    *   Platform (e.g., LinkedIn, eJobs)
    *   Direct Link to Apply

---

## 4. Post-Processing & AI Filtering (Optional but Recommended)
*   **Keyword Guardrails:** Even with filters, some senior roles slip through. The script will download the job description and run a simple Regex check.
    *   If it finds words like `senior`, `5+ ani experienta`, or `lead`, it silently drops the job and does not notify you.
    *   This ensures your Discord feed is 100% relevant junior roles in Bucharest.
