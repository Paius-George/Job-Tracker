import logging
from typing import List, Optional
import requests
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import clean_text

logger = logging.getLogger("job_bot")


class ArbeitnowScraper(BaseScraper):
    """Scrapes European tech & remote jobs via Arbeitnow API."""

    platform_name = "Arbeitnow"
    platform_code = "arbeitnow"
    platform_icon = "https://www.arbeitnow.com/favicon-32x32.png"

    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, request_delay: float = 1.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        logger.info(f"Fetching Arbeitnow EU jobs for '{profile.name}'")
        jobs: List[JobPost] = []

        try:
            headers = {"User-Agent": "JobBot/1.0"}
            response = self.session.get(self.BASE_URL, headers=headers, timeout=12)
            if response.status_code != 200:
                logger.warning(f"Arbeitnow API returned HTTP {response.status_code}")
                return jobs

            data = response.json()
            raw_jobs = data.get("data", [])

            for item in raw_jobs:
                slug = item.get("slug") or str(abs(hash(item.get("url", ""))))
                job_id = f"arbeitnow-{slug}"
                title = clean_text(item.get("title"))
                company = clean_text(item.get("company_name"))
                loc = clean_text(item.get("location") or "Europe / Remote")
                job_url = item.get("url", "")
                is_remote = item.get("remote", False)
                pub_date = str(item.get("created_at", ""))
                
                # Strip HTML from description
                raw_desc = item.get("description", "")
                desc = BeautifulSoup(raw_desc, "html.parser").get_text("\n", strip=True) if raw_desc else ""

                job = JobPost(
                    id=job_id,
                    title=title,
                    company=company,
                    location=f"{'🌐 Remote' if is_remote else '📍'} {loc}",
                    job_url=job_url,
                    post_date=pub_date,
                    workplace_type="Remote" if is_remote else "On-site",
                    description=desc,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                )
                jobs.append(job)

        except Exception as e:
            logger.warning(f"Error fetching Arbeitnow jobs: {e}")

        logger.info(f"Found {len(jobs)} jobs on Arbeitnow for '{profile.name}'")
        return jobs
