import json
import logging
import os
import datetime
from typing import List, Optional
import requests

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import clean_text

logger = logging.getLogger("job_bot")

# Locations that count as "Bucharest or remote from Bucharest"
BUCHAREST_HINTS = ("bucharest", "bucuresti", "bucurești", "romania", "românia", "remote")


def _slug_to_company(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


class CompanyATSScraper(BaseScraper):
    """Universal scraper for company career pages hosted on standard ATS platforms.

    Instead of one scraper per company, this handles dozens of companies with
    just two API formats (both verified live):
      * Greenhouse: https://boards-api.greenhouse.io/v1/boards/{board}/jobs
      * Lever:      https://api.lever.co/v0/postings/{company}?mode=json

    The list of target companies lives in `data/ats_companies.json`:
        {
            "greenhouse": ["bitpanda", "fingerprint"],
            "lever": []
        }
    """

    platform_name = "Company ATS"
    platform_code = "ats"
    platform_icon = "https://cdn-icons-png.flaticon.com/512/2913/2913091.png"

    GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
    LEVER_API = "https://api.lever.co/v0/postings/{}?mode=json"

    def __init__(self, request_delay: float = 2.0, ats_file: Optional[str] = None):
        self.request_delay = request_delay
        self.session = requests.Session()
        self.ats_file = ats_file or os.path.join("data", "ats_companies.json")
        self.greenhouse_boards: List[str] = []
        self.lever_companies: List[str] = []
        self._load_company_list()

    def _load_company_list(self):
        """Load the target companies JSON; tolerate a missing/corrupt file."""
        if not os.path.exists(self.ats_file):
            logger.warning(f"ATS company list '{self.ats_file}' not found — ATS scraping skipped.")
            return
        try:
            with open(self.ats_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            self.greenhouse_boards = [str(b).strip() for b in data.get("greenhouse", []) if str(b).strip()]
            self.lever_companies = [str(c).strip() for c in data.get("lever", []) if str(c).strip()]
            logger.info(
                f"ATS scraper loaded {len(self.greenhouse_boards)} Greenhouse boards "
                f"and {len(self.lever_companies)} Lever companies."
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read ATS company list '{self.ats_file}': {e}")

    @staticmethod
    def _is_relevant_location(location: str) -> bool:
        """Keep Bucharest-based roles and remote roles (doneable from Bucharest)."""
        lowered = (location or "").lower()
        return any(hint in lowered for hint in BUCHAREST_HINTS)

    def _fetch_greenhouse(self, board: str) -> List[JobPost]:
        jobs: List[JobPost] = []
        try:
            resp = self.session.get(self.GREENHOUSE_API.format(board), timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Greenhouse board '{board}' returned HTTP {resp.status_code}")
                return jobs
            data = resp.json()
            for item in data.get("jobs", []):
                location = clean_text(item.get("location", {}).get("name", ""))
                if not self._is_relevant_location(location):
                    continue

                title = clean_text(item.get("title", ""))
                url = item.get("absolute_url") or ""
                if not title or not url:
                    continue

                published = item.get("first_published") or item.get("updated_at")
                post_date = published if isinstance(published, str) else None

                jobs.append(JobPost(
                    id=f"gh-{item.get('id', abs(hash(url)))}",
                    title=title,
                    company=_slug_to_company(board),
                    location=location,
                    job_url=url,
                    post_date=post_date,
                    matched_search_name=None,
                    platform="Greenhouse",
                    platform_icon=self.platform_icon,
                ))
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Error fetching Greenhouse board '{board}': {e}")
        return jobs

    def _fetch_lever(self, company: str) -> List[JobPost]:
        jobs: List[JobPost] = []
        try:
            resp = self.session.get(self.LEVER_API.format(company), timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Lever company '{company}' returned HTTP {resp.status_code}")
                return jobs
            data = resp.json()
            if not isinstance(data, list):
                return jobs
            for item in data:
                location = clean_text(item.get("categories", {}).get("location", ""))
                if not self._is_relevant_location(location):
                    continue

                title = clean_text(item.get("text", ""))
                url = item.get("hostedUrl") or ""
                if not title or not url:
                    continue

                created_ms = item.get("createdAt")
                post_date = None
                if created_ms:
                    try:
                        post_date = datetime.datetime.fromtimestamp(
                            int(created_ms) / 1000, tz=datetime.timezone.utc
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, OSError):
                        pass

                jobs.append(JobPost(
                    id=f"lever-{item.get('id', abs(hash(url)))}",
                    title=title,
                    company=_slug_to_company(company),
                    location=location or "Remote",
                    job_url=url,
                    post_date=post_date,
                    matched_search_name=None,
                    platform="Lever",
                    platform_icon=self.platform_icon,
                ))
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Error fetching Lever company '{company}': {e}")
        return jobs

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        """Fetch postings from all configured ATS boards, keeping only
        Bucharest/remote roles (junior filtering happens downstream)."""
        if not (self.greenhouse_boards or self.lever_companies):
            return []

        logger.info(
            f"Scraping company ATS boards for '{profile.name}' "
            f"({len(self.greenhouse_boards)} Greenhouse, {len(self.lever_companies)} Lever)"
        )

        jobs: List[JobPost] = []
        for board in self.greenhouse_boards:
            jobs.extend(self._fetch_greenhouse(board))
        for company in self.lever_companies:
            jobs.extend(self._fetch_lever(company))

        logger.info(f"Found {len(jobs)} relevant ATS jobs for '{profile.name}'")
        return jobs
