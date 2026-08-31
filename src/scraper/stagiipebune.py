import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")


class StagiiPeBuneScraper(BaseScraper):
    """Scrapes StagiiPeBune.ro — Romania's dedicated IT internship board.

    Structure (verified live):
        Listing:  https://stagiipebune.ro/students/jobs/
        Job links: /jobs/{company-slug}/{title-slug}-{numeric-id}
    All internships here are student/junior level by definition.
    """

    platform_name = "StagiiPeBune"
    platform_code = "stagiipebune"
    platform_icon = "https://stagiipebune.ro/favicon.ico"

    BASE_URL = "https://stagiipebune.ro"

    def __init__(self, request_delay: float = 2.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://stagiipebune.ro/",
        }

    @staticmethod
    def _company_from_slug(href: str) -> str:
        """'/jobs/veridion/data-assets-intern-09346' -> 'Veridion'."""
        match = re.search(r"/jobs/([^/]+)/", href)
        if not match:
            return "StagiiPeBune Company"
        slug = match.group(1).replace("-", " ").strip()
        return slug.title()

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        url = f"{self.BASE_URL}/students/jobs/"
        logger.info(f"Scraping StagiiPeBune for '{profile.name}' (URL: {url})")

        jobs: List[JobPost] = []
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code != 200:
                logger.warning(f"StagiiPeBune returned HTTP {response.status_code}")
                return jobs

            soup = BeautifulSoup(response.text, "html.parser")

            seen = set()
            for anchor in soup.find_all("a", href=re.compile(r"^/jobs/[^/]+/.+")):
                href = anchor.get("href", "")
                title = clean_text(anchor.get_text())
                if not href or not title or href in seen:
                    continue
                # Skip navigation stubs (e.g. 'Stagii 25' counters)
                if len(title) < 4 or title.isdigit():
                    continue
                seen.add(href)

                detail_url = href if href.startswith("http") else self.BASE_URL + href
                job_id = href.rstrip("/").split("-")[-1] or str(abs(hash(href)))

                jobs.append(JobPost(
                    id=f"spb-{job_id}",
                    title=title,
                    company=self._company_from_slug(href),
                    location="Bucharest, Romania",  # StagiiPeBune is Romania-wide, IT roles are mostly Bucharest/remote
                    job_url=detail_url,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                ))

        except Exception as e:
            logger.warning(f"Error scraping StagiiPeBune: {e}")

        logger.info(f"Found {len(jobs)} jobs on StagiiPeBune for '{profile.name}'")
        return jobs