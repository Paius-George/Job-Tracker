from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class JobPost:
    """Represents a scraped job listing."""
    id: str
    title: str
    company: str
    location: str
    job_url: str
    company_url: Optional[str] = None
    logo_url: Optional[str] = None
    post_date: Optional[str] = None       # e.g. "2026-08-17"
    post_text: Optional[str] = None       # e.g. "2 hours ago"
    workplace_type: Optional[str] = None  # e.g. "Remote", "On-site", "Hybrid"
    employment_type: Optional[str] = None # e.g. "Full-time", "Contract"
    seniority_level: Optional[str] = None # e.g. "Entry level", "Mid-Senior"
    salary: Optional[str] = None          # e.g. "$100,000 - $130,000"
    description: Optional[str] = None     # Full text or snippet
    applicants: Optional[str] = None      # e.g. "12 applicants"
    criteria: Dict[str, str] = field(default_factory=dict)
    matched_search_name: Optional[str] = None

@dataclass
class SearchFilters:
    """Post-scraping custom filter criteria."""
    title_must_include: List[str] = field(default_factory=list)
    title_must_exclude: List[str] = field(default_factory=list)
    description_must_include: List[str] = field(default_factory=list)
    description_must_exclude: List[str] = field(default_factory=list)
    companies_include: List[str] = field(default_factory=list)
    companies_exclude: List[str] = field(default_factory=list)
    location_must_include: List[str] = field(default_factory=list)
    location_must_exclude: List[str] = field(default_factory=list)
    min_salary: Optional[float] = None

@dataclass
class SearchProfile:
    """Configuration for a specific search query."""
    name: str
    enabled: bool = True
    webhook_url: Optional[str] = None
    role_id_to_mention: Optional[str] = None
    embed_color: Optional[str] = None
    keywords: str = ""
    location: str = "Remote"
    date_posted: str = "past_24h" # past_24h, past_week, past_month, any
    sort_by: str = "recent"       # recent (DD), relevant
    workplace_types: List[str] = field(default_factory=list) # remote, hybrid, on_site
    experience_levels: List[str] = field(default_factory=list) # internship, entry_level, associate, mid_senior, director, executive
    job_types: List[str] = field(default_factory=list) # full_time, part_time, contract, temporary, internship
    filters: SearchFilters = field(default_factory=SearchFilters)
    max_pages: Optional[int] = None

@dataclass
class BotSettings:
    """Global bot settings."""
    discord_webhook_url: Optional[str] = None
    check_interval_minutes: int = 15
    request_delay_seconds: float = 3.0
    max_pages_per_search: int = 1
    fetch_job_details: bool = True
    database_path: str = "data/jobs.db"
    log_level: str = "INFO"

@dataclass
class AppConfig:
    """Top-level application configuration."""
    settings: BotSettings
    searches: List[SearchProfile] = field(default_factory=list)
