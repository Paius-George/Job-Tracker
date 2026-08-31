from abc import ABC, abstractmethod
from typing import List, Optional
from src.scraper.models import JobPost, SearchProfile


class BaseScraper(ABC):
    """Abstract base class for all job board scrapers."""

    platform_name: str = "Unknown"
    platform_code: str = "unknown"
    platform_icon: Optional[str] = None

    @abstractmethod
    def search_profile_jobs(self, profile: SearchProfile, max_pages: int = 1) -> List[JobPost]:
        """Search and parse job listings matching the given search profile."""
        pass
