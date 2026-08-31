import time
import random
import logging
import urllib.parse
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")


class EJobsScraper(BaseScraper):
    """Scrapes eJobs.ro (Romania's top job board)."""

    platform_name = "eJobs.ro"
    platform_code = "ejobs"
    platform_icon = "https://static.ejobs.ro/img/logos/ejobs-share.png"

    BASE_URL = "https://www.ejobs.ro"

    def __init__(self, request_delay: float = 2.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.ejobs.ro/",
        }

    def _extract_search_term(self, keywords: str) -> str:
        """Extract a single clean keyword query for eJobs URL format."""
        # e.g. 'Cybersecurity OR "Security Analyst"' -> 'cybersecurity'
        clean = keywords.replace('"', '').replace("'", "")
        terms = [t.strip() for t in clean.split(" OR ") if t.strip()]
        return terms[0] if terms else "it"

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        """Search eJobs for listings matching the profile."""
        search_term = self._extract_search_term(profile.keywords)
        # Location in eJobs URL: bucuresti if requested
        loc_slug = "bucuresti" if "bucharest" in profile.location.lower() or "bucuresti" in profile.location.lower() else ""

        if loc_slug:
            url = f"{self.BASE_URL}/locuri-de-munca/{loc_slug}/{urllib.parse.quote(search_term)}/"
        else:
            url = f"{self.BASE_URL}/locuri-de-munca/{urllib.parse.quote(search_term)}/"

        logger.info(f"Scraping eJobs.ro for '{profile.name}' (query: {search_term})")
        logger.debug(f"eJobs URL: {url}")

        jobs: List[JobPost] = []
        try:
            headers = self._get_headers()
            response = self.session.get(url, headers=headers, timeout=12)
            if response.status_code != 200:
                logger.warning(f"eJobs returned HTTP {response.status_code}")
                return jobs

            soup = BeautifulSoup(response.text, "html.parser")
            for h2 in soup.find_all("h2"):
                title = clean_text(h2.get_text())
                parent = h2.find_parent("div") or h2.find_parent("li")
                if not parent:
                    continue

                link_el = h2.find("a") or parent.find("a")
                if not link_el:
                    continue

                href = link_el.get("href", "")
                if not href or "/locuri-de-munca/" not in href or "salarii" in href:
                    continue

                if not href.startswith("http"):
                    href = self.BASE_URL + href

                h3 = parent.find("h3")
                company = clean_text(h3.get_text()) if h3 else "eJobs Employer"

                # Extract numeric job ID from URL
                parts = href.rstrip("/").split("/")
                raw_id = parts[-1] if parts and parts[-1].isdigit() else str(abs(hash(href)))
                job_id = f"ejobs-{raw_id}"

                # Location badge
                loc = "Bucharest, Romania" if loc_slug else "Romania"

                # Salary info if available
                salary_el = parent.find(lambda el: el.name in ("span", "div") and "lei" in el.get_text().lower() or "€" in el.get_text().lower())
                salary = clean_text(salary_el.get_text()) if salary_el else None

                job = JobPost(
                    id=job_id,
                    title=title,
                    company=company,
                    location=loc,
                    job_url=href,
                    salary=salary,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                )
                jobs.append(job)

        except Exception as e:
            logger.warning(f"Error scraping eJobs: {e}")

        logger.info(f"Found {len(jobs)} jobs on eJobs.ro for '{profile.name}'")
        return jobs
