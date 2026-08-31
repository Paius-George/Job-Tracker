import logging
import re
from typing import List
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")


class GoogleDorkScraper(BaseScraper):
    """Catches junior roles on custom company career pages via Google dorking.

    Runs queries like:
        site:*.ro/careers OR site:*.ro/jobs "Bucuresti" "junior" ("qa tester" OR "helpdesk")

    Uses the `googlesearch-python` package (optional dependency). If the
    package is missing or Google blocks the request, the scraper degrades
    gracefully and simply returns no jobs. Enable by adding "google" to a
    profile's `platforms` list in config.yaml.
    """

    platform_name = "Google"
    platform_code = "google"
    platform_icon = "https://www.google.com/favicon.ico"

    MAX_RESULTS = 10

    def __init__(self, request_delay: float = 3.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _build_dork(self, profile: SearchProfile) -> str:
        clean = profile.keywords.replace('"', "").strip()
        roles = clean if clean else '"qa tester" OR "helpdesk" OR "it support"'
        return (
            f'(site:*.ro/careers OR site:*.ro/jobs OR site:*.ro/cariera) '
            f'"Bucuresti" ("junior" OR "internship" OR "entry level") ({roles})'
        )

    def _google_search(self, query: str) -> List[str]:
        """Run the Google query; returns result URLs or [] on any failure."""
        try:
            from googlesearch import search
        except ImportError:
            logger.info("googlesearch-python not installed — Google dorking skipped (pip install googlesearch-python).")
            return []

        try:
            return list(search(query, num_results=self.MAX_RESULTS))
        except Exception as e:
            logger.warning(f"Google search failed: {e}")
            return []

    def _page_details(self, url: str) -> tuple:
        """Fetch a result page and extract its title (and og:title fallback)."""
        try:
            resp = self.session.get(
                url, timeout=12,
                headers={"User-Agent": get_random_user_agent(), "Accept-Language": "ro-RO,en;q=0.8"},
            )
            if resp.status_code != 200:
                return None, None
            soup = BeautifulSoup(resp.text, "html.parser")
            title = clean_text(soup.title.get_text()) if soup.title else ""
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                title = clean_text(og["content"]) or title
            return title or None, soup
        except requests.RequestException:
            return None, None

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        dork = self._build_dork(profile)
        logger.info(f"Running Google dork for '{profile.name}': {dork}")

        results = self._google_search(dork)
        if not results:
            return []

        jobs: List[JobPost] = []
        seen = set()
        for url in results:
            if not url or url in seen:
                continue
            seen.add(url)

            domain = urlparse(url).netloc.replace("www.", "")
            title, _soup = self._page_details(url)
            if not title:
                continue
            # Clean common title suffixes (" - Careers", " | ACME Corp")
            title = re.split(r"\s+[|\-–]\s+", title)[0].strip()
            if len(title) < 4:
                continue

            jobs.append(JobPost(
                id=f"google-{abs(hash(url))}",
                title=title[:120],
                company=domain,
                location="Bucharest, Romania",
                job_url=url,
                matched_search_name=profile.name,
                platform=self.platform_name,
                platform_icon=self.platform_icon,
            ))

        logger.info(f"Found {len(jobs)} Google dork results for '{profile.name}'")
        return jobs