# Scraper package
from src.scraper.models import JobPost, SearchProfile, SearchFilters, AppConfig, BotSettings
from src.scraper.base import BaseScraper
from src.scraper.linkedin import LinkedInScraper
from src.scraper.ejobs import EJobsScraper
from src.scraper.bestjobs import BestJobsScraper
from src.scraper.hipo import HipoScraper
from src.scraper.stagiipebune import StagiiPeBuneScraper
from src.scraper.ats import CompanyATSScraper
from src.scraper.googledork import GoogleDorkScraper
from src.scraper.jobicy import JobicyScraper
from src.scraper.remoteok import RemoteOKScraper
from src.scraper.arbeitnow import ArbeitnowScraper

SCRAPER_REGISTRY = {
    "linkedin": LinkedInScraper,
    "ejobs": EJobsScraper,
    "bestjobs": BestJobsScraper,
    "hipo": HipoScraper,
    "stagiipebune": StagiiPeBuneScraper,
    "ats": CompanyATSScraper,
    "google": GoogleDorkScraper,
    "jobicy": JobicyScraper,
    "remoteok": RemoteOKScraper,
    "arbeitnow": ArbeitnowScraper,
}

__all__ = [
    "JobPost",
    "SearchProfile",
    "SearchFilters",
    "AppConfig",
    "BotSettings",
    "BaseScraper",
    "LinkedInScraper",
    "EJobsScraper",
    "BestJobsScraper",
    "HipoScraper",
    "StagiiPeBuneScraper",
    "CompanyATSScraper",
    "GoogleDorkScraper",
    "JobicyScraper",
    "RemoteOKScraper",
    "ArbeitnowScraper",
    "SCRAPER_REGISTRY",
]
