import time
import random
import logging
import datetime
import urllib.parse
from typing import List, Optional, Tuple
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile, SearchFilters
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")

WORKPLACE_TYPE_MAP = {
    "on_site": "1",
    "on-site": "1",
    "onsite": "1",
    "remote": "2",
    "hybrid": "3",
}

EXPERIENCE_LEVEL_MAP = {
    "internship": "1",
    "entry_level": "2",
    "entry-level": "2",
    "entry": "2",
    "associate": "3",
    "mid_senior": "4",
    "mid-senior": "4",
    "mid_senior_level": "4",
    "mid": "4",
    "director": "5",
    "executive": "6",
}

JOB_TYPE_MAP = {
    "full_time": "F",
    "full-time": "F",
    "fulltime": "F",
    "part_time": "P",
    "part-time": "P",
    "parttime": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
    "volunteer": "V",
}

DATE_POSTED_MAP = {
    "past_30min": "r1800",
    "30min": "r1800",
    "past_hour": "r3600",
    "1h": "r3600",
    "hour": "r3600",
    "past_24h": "r86400",
    "24h": "r86400",
    "past_week": "r604800",
    "week": "r604800",
    "past_month": "r2592000",
    "month": "r2592000",
}


def _parse_age_hours(post_date: Optional[str], post_text: Optional[str]) -> Optional[float]:
    """Estimate the posting age in hours from the available timestamp data.

    Prefers the exact ISO timestamp from the <time datetime="..."> attribute
    and falls back to parsing relative text like '15 minutes ago'.
    Returns None when the age cannot be determined.
    """
    if post_date:
        try:
            posted = datetime.datetime.fromisoformat(str(post_date).strip().replace("Z", "+00:00"))
            if posted.tzinfo is None:
                # LinkedIn guest cards expose UTC timestamps without tz info
                posted = posted.replace(tzinfo=datetime.timezone.utc)
            age = datetime.datetime.now(datetime.timezone.utc) - posted
            return max(age.total_seconds() / 3600.0, 0.0)
        except ValueError:
            pass

    if post_text:
        text = post_text.lower().strip()
        import re
        if re.search(r"\d+\s*minute", text):
            match = re.search(r"(\d+)\s*minute", text)
            if match:
                return int(match.group(1)) / 60.0
        if re.search(r"\d+\s*hour", text):
            match = re.search(r"(\d+)\s*hour", text)
            if match:
                return float(int(match.group(1)))
        # Any larger unit immediately exceeds a 30 minute window
        for unit in ("day", "week", "month", "year"):
            if unit in text:
                return 10000.0
    return None


class LinkedInScraper(BaseScraper):
    """Scrapes LinkedIn public guest job postings without requiring credentials."""

    platform_name = "LinkedIn"
    platform_code = "linkedin"
    platform_icon = "https://cdn-icons-png.flaticon.com/512/3536/3536505.png"

    BASE_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"

    def __init__(self, request_delay: float = 3.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.linkedin.com/jobs",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _build_search_url(self, profile: SearchProfile, start: int = 0) -> str:
        """Construct the search URL with query parameters based on SearchProfile."""
        params = {
            "keywords": profile.keywords,
            "location": profile.location,
            "start": start,
        }

        # Date posted filter
        if profile.date_posted and profile.date_posted in DATE_POSTED_MAP:
            params["f_TPR"] = DATE_POSTED_MAP[profile.date_posted]

        # Sort order
        if profile.sort_by in ("recent", "DD", "date"):
            params["sortBy"] = "DD"

        # Workplace types (e.g. Remote = 2)
        if profile.workplace_types:
            wt_codes = [WORKPLACE_TYPE_MAP[wt.lower()] for wt in profile.workplace_types if wt.lower() in WORKPLACE_TYPE_MAP]
            if wt_codes:
                params["f_WT"] = ",".join(wt_codes)

        # Experience levels
        if profile.experience_levels:
            exp_codes = [EXPERIENCE_LEVEL_MAP[el.lower()] for el in profile.experience_levels if el.lower() in EXPERIENCE_LEVEL_MAP]
            if exp_codes:
                params["f_E"] = ",".join(exp_codes)

        # Job types (Full-time, Contract, etc.)
        if profile.job_types:
            jt_codes = [JOB_TYPE_MAP[jt.lower()] for jt in profile.job_types if jt.lower() in JOB_TYPE_MAP]
            if jt_codes:
                params["f_JT"] = ",".join(jt_codes)

        return f"{self.BASE_SEARCH_URL}?{urllib.parse.urlencode(params)}"

    def _fetch_html(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch HTML content with automatic retries and exponential backoff."""
        for attempt in range(1, max_retries + 1):
            try:
                headers = self._get_headers()
                response = self.session.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:
                    wait_time = attempt * 5 + random.uniform(2, 5)
                    logger.warning(f"Rate limited by LinkedIn (429). Retrying in {wait_time:.1f}s... (attempt {attempt}/{max_retries})")
                    time.sleep(wait_time)
                elif response.status_code == 404:
                    logger.debug(f"Page not found (404): {url}")
                    return None
                else:
                    logger.warning(f"HTTP {response.status_code} fetching {url}")
                    time.sleep(2 * attempt)
            except Exception as e:
                logger.warning(f"Request error for {url}: {e} (attempt {attempt}/{max_retries})")
                time.sleep(2 * attempt)

        return None

    def parse_job_cards(self, html: str, matched_search_name: str = "") -> List[JobPost]:
        """Extract job listings from LinkedIn search HTML response."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="job-search-card")
        jobs: List[JobPost] = []

        for card in cards:
            # Job ID
            urn = card.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if urn and ":" in urn else None

            # Title
            title_el = card.find("h3", class_="base-search-card__title")
            title = clean_text(title_el.get_text()) if title_el else ""

            # Company name & company URL
            company_el = card.find("h4", class_="base-search-card__subtitle")
            company = clean_text(company_el.get_text()) if company_el else "Unknown Company"
            company_link = None
            if company_el and company_el.find("a"):
                raw_company_link = company_el.find("a").get("href", "")
                company_link = raw_company_link.split("?")[0] if raw_company_link else None

            # Location
            location_el = card.find("span", class_="job-search-card__location")
            location = clean_text(location_el.get_text()) if location_el else "Unknown Location"

            # Post date and text (e.g. "2 hours ago")
            time_el = card.find("time")
            post_date = time_el.get("datetime") if time_el else None
            post_text = clean_text(time_el.get_text()) if time_el else None

            # Job link & fallback ID extraction from URL
            link_el = card.find("a", class_="base-card__full-link")
            raw_link = link_el.get("href", "") if link_el else ""
            clean_link = raw_link.split("?")[0] if raw_link else ""

            if not job_id and clean_link:
                # Extract numeric job ID from URL (e.g. ...-4414037159)
                parts = clean_link.rstrip("/").split("-")
                if parts and parts[-1].isdigit():
                    job_id = parts[-1]

            if not clean_link and job_id:
                clean_link = f"https://www.linkedin.com/jobs/view/{job_id}"

            if not job_id or not title:
                continue

            # Logo URL
            img_el = card.find("img")
            logo_url = None
            if img_el:
                logo_url = img_el.get("data-delayed-url") or img_el.get("src")
                if logo_url and "data:image" in logo_url:
                    logo_url = None

            # Salary info if shown on card
            salary_el = card.find("span", class_="job-search-card__salary-info")
            salary = clean_text(salary_el.get_text()) if salary_el else None

            # Workplace type hint from location or card
            workplace_type = None
            if "remote" in location.lower():
                workplace_type = "Remote"
            elif "hybrid" in location.lower():
                workplace_type = "Hybrid"

            job = JobPost(
                id=job_id,
                title=title,
                company=company,
                location=location,
                job_url=clean_link,
                company_url=company_link,
                logo_url=logo_url,
                post_date=post_date,
                post_text=post_text,
                workplace_type=workplace_type,
                salary=salary,
                matched_search_name=matched_search_name,
                platform=self.platform_name,
                platform_icon=self.platform_icon,
            )
            jobs.append(job)

        return jobs

    def fetch_job_details(self, job: JobPost) -> JobPost:
        """Fetch rich details (full description, seniority, criteria, applicants) for a job."""
        detail_url = self.BASE_DETAIL_URL.format(job.id)
        html = self._fetch_html(detail_url)
        if not html:
            return job

        soup = BeautifulSoup(html, "html.parser")

        # Criteria list (Seniority level, Employment type, Job function, Industries)
        criteria = {}
        for item in soup.find_all("li", class_="description__job-criteria-item"):
            header = item.find("h3", class_="description__job-criteria-subheader")
            value = item.find("span", class_="description__job-criteria-text")
            if header and value:
                criteria[clean_text(header.get_text())] = clean_text(value.get_text())

        job.criteria = criteria
        job.seniority_level = criteria.get("Seniority level")
        job.employment_type = criteria.get("Employment type")

        # Description text
        desc_el = soup.find("div", class_="show-more-less-html__markup")
        if desc_el:
            job.description = desc_el.get_text("\n", strip=True)

        # Applicant count
        app_el = soup.find("span", class_="num-applicants__caption")
        if app_el:
            job.applicants = clean_text(app_el.get_text())

        # If logo was missing, try fetching it from details top card
        if not job.logo_url:
            top_logo = soup.find("img", class_="artdeco-entity-image")
            if top_logo:
                job.logo_url = top_logo.get("data-delayed-url") or top_logo.get("src")

        return job

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        """Scrape all job cards matching a search profile across multiple pages."""
        all_jobs: List[JobPost] = []
        seen_ids = set()

        pages_to_fetch = profile.max_pages if profile.max_pages is not None else max_pages

        for page in range(pages_to_fetch):
            start = page * 25
            url = self._build_search_url(profile, start=start)
            logger.info(f"Scraping '{profile.name}' (page {page + 1}/{pages_to_fetch})")
            logger.debug(f"Search URL: {url}")

            html = self._fetch_html(url)
            if not html:
                logger.warning(f"No response received for search '{profile.name}' page {page + 1}")
                break

            jobs = self.parse_job_cards(html, matched_search_name=profile.name)
            if not jobs:
                logger.info(f"No more jobs found for '{profile.name}' at page {page + 1}")
                break

            new_in_page = 0
            for job in jobs:
                if job.id not in seen_ids:
                    seen_ids.add(job.id)
                    all_jobs.append(job)
                    new_in_page += 1

            logger.info(f"Found {len(jobs)} jobs ({new_in_page} unique on this page)")

            # Polite delay between pages
            if page < pages_to_fetch - 1:
                jitter = random.uniform(1.0, 2.5)
                time.sleep(self.request_delay + jitter)

        return all_jobs

    @staticmethod
    def matches_filters(job: JobPost, filters: SearchFilters) -> Tuple[bool, str]:
        """
        Check if a job matches custom include/exclude filters.
        Returns (is_matched, reason_if_rejected).
        """
        title_lower = job.title.lower()
        company_lower = job.company.lower()
        desc_lower = (job.description or "").lower()

        # 1. Company blacklist check
        for company in filters.companies_exclude:
            if company.lower() in company_lower:
                return False, f"Company '{job.company}' is in blacklist ({company})"

        # 2. Company whitelist check (if specified)
        if filters.companies_include:
            matched_company = any(c.lower() in company_lower for c in filters.companies_include)
            if not matched_company:
                return False, f"Company '{job.company}' not in whitelist"

        # 3. Title exclusion check
        for excluded_word in filters.title_must_exclude:
            if excluded_word.lower() in title_lower:
                return False, f"Title contains excluded keyword: '{excluded_word}'"

        # 4. Title inclusion check
        if filters.title_must_include:
            matched_title = any(inc.lower() in title_lower for inc in filters.title_must_include)
            if not matched_title:
                return False, f"Title does not match any required keywords: {filters.title_must_include}"

        # 5. Location exclusion check
        location_lower = (job.location or "").lower()
        if filters.location_must_exclude:
            for exc_loc in filters.location_must_exclude:
                if exc_loc.lower() in location_lower:
                    return False, f"Location '{job.location}' contains excluded location: '{exc_loc}'"

        # 6. Location inclusion check (strict city matching)
        if filters.location_must_include:
            matched_loc = any(inc_loc.lower() in location_lower for inc_loc in filters.location_must_include)
            if not matched_loc:
                return False, f"Location '{job.location}' does not match required locations: {filters.location_must_include}"

        # 7. Post age freshness check (e.g. last 30 minutes)
        if filters.max_age_hours is not None:
            age_hours = _parse_age_hours(job.post_date, job.post_text)
            if age_hours is not None and age_hours > filters.max_age_hours:
                return False, f"Job was posted {age_hours:.1f}h ago (max allowed: {filters.max_age_hours}h)"

        # 8. Description exclusion check
        if job.description and filters.description_must_exclude:
            for exc in filters.description_must_exclude:
                if exc.lower() in desc_lower:
                    return False, f"Description contains excluded term: '{exc}'"

        # 9. Description inclusion check
        if job.description and filters.description_must_include:
            matched_desc = any(inc.lower() in desc_lower for inc in filters.description_must_include)
            if not matched_desc:
                return False, f"Description does not contain required terms: {filters.description_must_include}"

        return True, "Passed all filters"
