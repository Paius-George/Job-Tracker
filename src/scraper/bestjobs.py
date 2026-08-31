import time
import random
import logging
import re
import urllib.parse
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")


class BestJobsScraper(BaseScraper):
    """Scrapes BestJobs.eu via pre-built search URLs (Bucharest + keyword).

    Search URL format (verified live):
        https://www.bestjobs.eu/locuri-de-munca/{city}/{keyword-slug}
    Job cards contain anchors to detail pages:  href="/loc-de-munca/{slug}-{id}"
    with the title in an <h2> and the company in a small text-ink-medium div.
    """

    platform_name = "BestJobs"
    platform_code = "bestjobs"
    platform_icon = "https://www.bestjobs.eu/favicon.ico"

    BASE_URL = "https://www.bestjobs.eu"

    def __init__(self, request_delay: float = 2.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.bestjobs.eu/",
        }

    def _build_search_url(self, profile: SearchProfile) -> str:
        """Build the search URL (verified live):
        https://www.bestjobs.eu/ro/locuri-de-munca?keyword=qa+tester&location=bucuresti
        """
        # Extract a single clean search term from the OR-separated keyword query
        clean = profile.keywords.replace('"', "").replace("'", "")
        terms = [t.strip().lower() for t in clean.split(" OR ") if t.strip()]
        keyword = terms[0] if terms else "it"

        params = {"keyword": keyword}
        if "bucharest" in profile.location.lower() or "bucuresti" in profile.location.lower():
            params["location"] = "bucuresti"
        return f"{self.BASE_URL}/ro/locuri-de-munca?{urllib.parse.urlencode(params)}"

    def _parse_job_id(self, href: str) -> Optional[str]:
        """Extract the numeric job id from '/loc-de-munca/{slug}-{id}'."""
        tail = href.rstrip("/").split("/")[-1]
        match = re.search(r"-(\d+)$", tail)
        if match:
            return match.group(1)
        return None

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        url = self._build_search_url(profile)
        logger.info(f"Scraping BestJobs for '{profile.name}' (URL: {url})")

        jobs: List[JobPost] = []
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code != 200:
                logger.warning(f"BestJobs returned HTTP {response.status_code}")
                return jobs

            soup = BeautifulSoup(response.text, "html.parser")

            # Every job card contains an overlay anchor to the detail page
            for anchor in soup.find_all("a", href=re.compile(r"^/loc-de-munca/")):
                href = anchor.get("href", "")
                if not href:
                    continue

                card = anchor.find_parent("div")
                if not card:
                    continue

                # Title: prefer the card's <h2>, fallback to aria-label
                h2 = card.find("h2")
                title = clean_text(h2.get_text()) if h2 else clean_text(anchor.get("aria-label", ""))
                if not title:
                    continue

                # Company: the small grey div inside the card
                company_el = card.find("div", class_=re.compile(r"text-ink-medium"))
                company = clean_text(company_el.get_text()) if company_el else "BestJobs Employer"

                # Location: from the search context (cards don't always repeat it)
                location = f"{profile.location}, Romania" if profile.location else "Romania"

                job_id = self._parse_job_id(href) or str(abs(hash(href)))
                detail_url = href if href.startswith("http") else self.BASE_URL + href

                jobs.append(JobPost(
                    id=f"bestjobs-{job_id}",
                    title=title,
                    company=company,
                    location=location,
                    job_url=detail_url,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                ))

        except Exception as e:
            logger.warning(f"Error scraping BestJobs: {e}")

        # Deduplicate within the page
        unique = list({j.id: j for j in jobs}.values())
        logger.info(f"Found {len(unique)} jobs on BestJobs for '{profile.name}'")
        return unique