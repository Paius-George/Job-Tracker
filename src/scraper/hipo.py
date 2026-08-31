import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import get_random_user_agent, clean_text

logger = logging.getLogger("job_bot")


class HipoScraper(BaseScraper):
    """Scrapes Hipo.ro (strong focus on junior/student-friendly roles).

    Strategy: scrape the pre-filtered Bucharest IT category page.
    Hipo job detail pages live under '/oferta-de-angajare/...'.
    Note: Hipo.ro occasionally goes down for maintenance — the scraper
    degrades gracefully (logs a warning, returns no jobs).
    """

    platform_name = "Hipo.ro"
    platform_code = "hipo"
    platform_icon = "https://www.hipo.ro/favicon.ico"

    BASE_URL = "https://www.hipo.ro"

    def __init__(self, request_delay: float = 2.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.hipo.ro/",
        }

    def _build_search_url(self, profile: SearchProfile) -> str:
        """Bucharest IT category (Hipo has no free-text junior filter in URLs)."""
        return f"{self.BASE_URL}/locuri-de-munca/Bucuresti/IT"

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        url = self._build_search_url(profile)
        logger.info(f"Scraping Hipo.ro for '{profile.name}' (URL: {url})")

        jobs: List[JobPost] = []
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code != 200:
                logger.warning(f"Hipo.ro returned HTTP {response.status_code}")
                return jobs

            soup = BeautifulSoup(response.text, "html.parser")

            seen = set()
            for anchor in soup.find_all("a", href=re.compile(r"/oferta-de-angajare/")):
                href = anchor.get("href", "")
                title = clean_text(anchor.get_text())
                if not href or not title or href in seen:
                    continue
                seen.add(href)

                # Try to locate the company inside the job card
                company = "Hipo.ro Employer"
                card = anchor.find_parent(["div", "li", "article"])
                if card:
                    h3 = card.find("h3") or card.find(["strong", "b"])
                    if h3 and h3 is not anchor:
                        candidate = clean_text(h3.get_text())
                        if candidate and candidate.lower() != title.lower():
                            company = candidate

                detail_url = href if href.startswith("http") else self.BASE_URL + href
                job_id = str(abs(hash(href)))

                jobs.append(JobPost(
                    id=f"hipo-{job_id}",
                    title=title,
                    company=company,
                    location="Bucharest, Romania",
                    job_url=detail_url,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                ))

        except Exception as e:
            logger.warning(f"Error scraping Hipo.ro: {e}")

        logger.info(f"Found {len(jobs)} jobs on Hipo.ro for '{profile.name}'")
        return jobs