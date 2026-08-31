import logging
from typing import List, Optional
import requests

from src.scraper.base import BaseScraper
from src.scraper.models import JobPost, SearchProfile
from src.utils import clean_text

logger = logging.getLogger("job_bot")


class JobicyScraper(BaseScraper):
    """Scrapes remote tech & security jobs via Jobicy API."""

    platform_name = "Jobicy"
    platform_code = "jobicy"
    platform_icon = "https://jobicy.com/assets/images/logo.png"

    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, request_delay: float = 1.0):
        self.request_delay = request_delay
        self.session = requests.Session()

    def _determine_tag(self, keywords: str) -> str:
        """Map search keywords to Jobicy supported tags."""
        kw_lower = keywords.lower()
        if "security" in kw_lower or "soc" in kw_lower or "pentest" in kw_lower or "cyber" in kw_lower:
            return "security"
        elif "devops" in kw_lower or "cloud" in kw_lower or "linux" in kw_lower:
            return "devops"
        elif "support" in kw_lower or "helpdesk" in kw_lower:
            return "supporting"
        elif "python" in kw_lower:
            return "python"
        return "engineering"

    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        """Fetch remote jobs matching profile."""
        tag = self._determine_tag(profile.keywords)
        url = f"{self.BASE_URL}?count=50&tag={tag}"

        logger.info(f"Fetching Jobicy remote jobs for '{profile.name}' (tag: {tag})")
        jobs: List[JobPost] = []

        try:
            headers = {"User-Agent": "JobBot/1.0"}
            response = self.session.get(url, headers=headers, timeout=12)
            if response.status_code != 200:
                logger.warning(f"Jobicy API returned HTTP {response.status_code}")
                return jobs

            data = response.json()
            raw_jobs = data.get("jobs", [])

            for item in raw_jobs:
                job_id = f"jobicy-{item.get('id')}"
                title = clean_text(item.get("jobTitle"))
                company = clean_text(item.get("companyName"))
                geo = clean_text(item.get("jobGeo", "Remote / Europe"))
                job_url = item.get("url", "")
                logo_url = item.get("companyLogo")
                pub_date = item.get("pubDate")
                desc = clean_text(item.get("jobExcerpt") or item.get("jobDescription"))
                level = item.get("jobLevel")

                job = JobPost(
                    id=job_id,
                    title=title,
                    company=company,
                    location=f"🌐 Remote ({geo})",
                    job_url=job_url,
                    logo_url=logo_url,
                    post_date=pub_date,
                    workplace_type="Remote",
                    seniority_level=level,
                    description=desc,
                    matched_search_name=profile.name,
                    platform=self.platform_name,
                    platform_icon=self.platform_icon,
                )
                jobs.append(job)

        except Exception as e:
            logger.warning(f"Error fetching Jobicy jobs: {e}")

        logger.info(f"Found {len(jobs)} jobs on Jobicy for '{profile.name}'")
        return jobs
