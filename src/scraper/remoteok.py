import logging
from typing import List, Optional
import requests

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import clean_text

logger = logging.getLogger("job_bot")


class RemoteOKScraper(BaseScraper):
    """Scrapes remote tech & cybersecurity jobs from RemoteOK."""

    platform_name = "RemoteOK"
    platform_code = "remoteok"
    platform_icon = "https://remoteok.com/assets/favicon-96x96.png"

    BASE_URL = "https://remoteok.com/api"

    def __init__(self, request_delay: float = 1.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _determine_tag(self, keywords: str) -> str:
        kw_lower = keywords.lower()
        if "security" in kw_lower or "soc" in kw_lower or "pentest" in kw_lower or "cyber" in kw_lower:
            return "security"
        elif "devops" in kw_lower or "cloud" in kw_lower or "linux" in kw_lower:
            return "devops"
        elif "support" in kw_lower or "helpdesk" in kw_lower:
            return "support"
        elif "python" in kw_lower:
            return "python"
        return "tech"

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        tag = self._determine_tag(profile.keywords)
        url = f"{self.BASE_URL}?tag={tag}"

        logger.info(f"Fetching RemoteOK jobs for '{profile.name}' (tag: {tag})")
        jobs: List[JobPost] = []

        try:
            headers = {"User-Agent": "JobAlertBot/1.0 (Mozilla/5.0 desktop compatible)"}
            response = self.session.get(url, headers=headers, timeout=12)
            if response.status_code != 200:
                logger.warning(f"RemoteOK API returned HTTP {response.status_code}")
                return jobs

            data = response.json()
            raw_jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []

            for item in raw_jobs:
                if not isinstance(item, dict):
                    continue

                raw_id = item.get("id") or str(abs(hash(item.get("url", ""))))
                job_id = f"remoteok-{raw_id}"
                title = clean_text(item.get("position"))
                company = clean_text(item.get("company"))
                loc = clean_text(item.get("location") or "Worldwide Remote")
                job_url = item.get("url", "")
                logo_url = item.get("company_logo")
                pub_date = item.get("date")
                desc = clean_text(item.get("description"))

                job = JobPost(
                    id=job_id,
                    title=title,
                    company=company,
                    location=f"🌐 Remote ({loc})",
                    job_url=job_url,
                    logo_url=logo_url,
                    post_date=pub_date,
                    workplace_type="Remote",
                    description=desc,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                )
                jobs.append(job)

        except Exception as e:
            logger.warning(f"Error fetching RemoteOK jobs: {e}")

        logger.info(f"Found {len(jobs)} jobs on RemoteOK for '{profile.name}'")
        return jobs
