import os
import yaml
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from src.scraper.models import AppConfig, BotSettings, SearchProfile, SearchFilters

logger = logging.getLogger("job_bot")


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load and parse application configuration from YAML and environment variables."""
    # Load .env file if present
    load_dotenv(override=False)

    if not os.path.exists(config_path):
        if os.path.exists("config.example.yaml"):
            logger.warning(f"'{config_path}' not found. Falling back to 'config.example.yaml'.")
            config_path = "config.example.yaml"
        else:
            raise FileNotFoundError(f"Configuration file '{config_path}' not found.")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    raw_settings = raw_data.get("settings", {})
    raw_searches = raw_data.get("searches", [])

    # Environment variable override for Discord Webhook URL
    env_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    webhook_url = env_webhook or raw_settings.get("discord_webhook_url", "")

    settings = BotSettings(
        discord_webhook_url=webhook_url,
        check_interval_minutes=int(raw_settings.get("check_interval_minutes", 15)),
        request_delay_seconds=float(raw_settings.get("request_delay_seconds", 3.0)),
        max_pages_per_search=int(raw_settings.get("max_pages_per_search", 1)),
        fetch_job_details=bool(raw_settings.get("fetch_job_details", True)),
        database_path=raw_settings.get("database_path", "data/jobs.db"),
        log_level=raw_settings.get("log_level", "INFO"),
        # Phase 3: global junior/internship filtering engine
        junior_filter_enabled=bool(raw_settings.get("junior_filter_enabled", True)),
        junior_filter_strict=bool(raw_settings.get("junior_filter_strict", False)),
        junior_include_keywords=raw_settings.get("junior_include_keywords"),
        junior_title_exclude_keywords=raw_settings.get("junior_title_exclude_keywords"),
        junior_description_exclude_keywords=raw_settings.get("junior_description_exclude_keywords"),
    )

    searches = []
    for idx, s in enumerate(raw_searches):
        filters_dict = s.get("filters", {})
        filters = SearchFilters(
            title_must_include=filters_dict.get("title_must_include", []) or [],
            title_must_exclude=filters_dict.get("title_must_exclude", []) or [],
            description_must_include=filters_dict.get("description_must_include", []) or [],
            description_must_exclude=filters_dict.get("description_must_exclude", []) or [],
            companies_include=filters_dict.get("companies_include", []) or [],
            companies_exclude=filters_dict.get("companies_exclude", []) or [],
            location_must_include=filters_dict.get("location_must_include", []) or [],
            location_must_exclude=filters_dict.get("location_must_exclude", []) or [],
            max_age_hours=filters_dict.get("max_age_hours"),
            min_salary=filters_dict.get("min_salary"),
        )

        profile = SearchProfile(
            name=s.get("name", f"Search #{idx + 1}"),
            enabled=bool(s.get("enabled", True)),
            webhook_url=s.get("webhook_url") or None,
            role_id_to_mention=s.get("role_id_to_mention") or None,
            embed_color=s.get("embed_color", "#0A66C2"),
            keywords=s.get("keywords", ""),
            location=s.get("location", "Remote"),
            date_posted=s.get("date_posted", "past_24h"),
            sort_by=s.get("sort_by", "recent"),
            workplace_types=s.get("workplace_types", []) or [],
            experience_levels=s.get("experience_levels", []) or [],
            job_types=s.get("job_types", []) or [],
            filters=filters,
            max_pages=s.get("max_pages"),
            platforms=s.get("platforms", ["linkedin", "ejobs", "bestjobs", "hipo", "stagiipebune", "ats", "jobicy", "remoteok", "arbeitnow"])
            or ["linkedin", "ejobs", "bestjobs", "hipo", "stagiipebune", "ats", "jobicy", "remoteok", "arbeitnow"],
        )
        searches.append(profile)

    return AppConfig(settings=settings, searches=searches)
