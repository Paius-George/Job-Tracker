import time
import random
import signal
import logging
from typing import Dict, List, Optional
from rich.console import Console

from src.scraper.models import AppConfig, SearchProfile, JobPost
from src.scraper.base import BaseScraper
from src.scraper.linkedin import LinkedInScraper
from src.scraper.ejobs import EJobsScraper
from src.scraper.jobicy import JobicyScraper
from src.scraper.remoteok import RemoteOKScraper
from src.scraper.arbeitnow import ArbeitnowScraper
from src.scraper import SCRAPER_REGISTRY
from src.database import JobDatabase
from src.discord_notifier import DiscordNotifier
from src.tracker import JuniorRoleFilter

logger = logging.getLogger("job_bot")
console = Console()


class JobBotRunner:
    """Coordinates scraping across multiple platforms, filtering, duplicate tracking, and Discord alerting."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.db = JobDatabase(config.settings.database_path)
        self.notifier = DiscordNotifier(default_webhook_url=config.settings.discord_webhook_url)
        self.is_running = True

        # Initialize all scrapers
        self.scrapers: Dict[str, BaseScraper] = {}
        for code, scraper_cls in SCRAPER_REGISTRY.items():
            try:
                self.scrapers[code] = scraper_cls(request_delay=config.settings.request_delay_seconds)
            except Exception as e:
                logger.warning(f"Could not initialize scraper for '{code}': {e}")

        # Global junior/internship filtering engine (Phase 3)
        self.role_filter = JuniorRoleFilter(
            enabled=config.settings.junior_filter_enabled,
            strict=config.settings.junior_filter_strict,
            include_keywords=config.settings.junior_include_keywords,
            title_exclude_keywords=config.settings.junior_title_exclude_keywords,
            description_exclude_keywords=config.settings.junior_description_exclude_keywords,
        )

    def scan_search_profile(self, profile: SearchProfile) -> dict:
        """Execute scan across all configured platforms for a single search profile."""
        if not profile.enabled:
            logger.info(f"Skipping disabled search: '{profile.name}'")
            return {"found": 0, "new": 0, "notified": 0, "duration": 0.0}

        start_time = time.time()
        logger.info(f"🔍 Starting scan for: [bold cyan]{profile.name}[/bold cyan]", extra={"markup": True})

        # Determine platforms to query
        target_platforms = profile.platforms or list(SCRAPER_REGISTRY.keys())
        scraped_jobs: List[JobPost] = []
        max_pages = profile.max_pages if profile.max_pages is not None else self.config.settings.max_pages_per_search

        for plat_code in target_platforms:
            if not self.is_running:
                break
            scraper = self.scrapers.get(plat_code)
            if not scraper:
                continue

            try:
                platform_jobs = scraper.search_profile_jobs(profile, max_pages=max_pages)
                scraped_jobs.extend(platform_jobs)
            except Exception as e:
                logger.warning(f"Error scraping platform '{plat_code}' for '{profile.name}': {e}")

            time.sleep(1.0)

        total_found = len(scraped_jobs)
        new_jobs = 0
        notified_count = 0

        for job in scraped_jobs:
            if not self.is_running:
                break

            # 2. Check duplicate database
            if self.db.is_job_seen(job.id):
                logger.debug(f"Job {job.id} ('{job.title}' on {job.platform}) already seen. Skipping.")
                continue

            new_jobs += 1
            logger.info(
                f"🆕 [[bold yellow]{job.platform}[/bold yellow]] Discovered: [bold]{job.title}[/bold] @ [green]{job.company}[/green] ({job.location})",
                extra={"markup": True}
            )

            # 3. Apply custom title/location/company filters
            matched, reason = LinkedInScraper.matches_filters(job, profile.filters)
            if not matched:
                logger.info(f"   ⏩ Filtered out: {reason}")
                self.db.mark_job_seen(job, profile.name, notified=False, status="FILTERED")
                continue

            # 4. Fetch rich job details for LinkedIn if enabled
            if self.config.settings.fetch_job_details and job.platform == "LinkedIn" and hasattr(self.scrapers.get("linkedin"), "fetch_job_details"):
                try:
                    time.sleep(random.uniform(1.0, 2.0))
                    job = self.scrapers["linkedin"].fetch_job_details(job)
                    matched_desc, desc_reason = LinkedInScraper.matches_filters(job, profile.filters)
                    if not matched_desc:
                        logger.info(f"   ⏩ Filtered out after details check: {desc_reason}")
                        self.db.mark_job_seen(job, profile.name, notified=False, status="FILTERED_DESC")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to fetch details for job {job.id}: {e}")

            # 4b. Global junior/internship keyword filter (Phase 3 safety net)
            junior_ok, junior_reason = self.role_filter.matches(job)
            if not junior_ok:
                logger.info(f"   🚫 Junior filter: {junior_reason}")
                self.db.mark_job_seen(job, profile.name, notified=False, status="FILTERED")
                continue

            # 4c. Cross-platform deduplication: similar title at same company (Phase 3)
            duplicate = self.db.find_similar_job(job.title, job.company)
            if duplicate:
                logger.info(
                    f"   🔁 Duplicate of '{duplicate['title']}' @ {duplicate['company']} "
                    f"(already tracked on {duplicate['platform']} as {duplicate['status']})"
                )
                self.db.mark_job_seen(job, profile.name, notified=False, status="DUPLICATE")
                continue

            # 5. Send Discord alert
            logger.info(f"   🚀 Sending Discord alert for: [bold green]{job.title}[/bold green] ([cyan]{job.platform}[/cyan])", extra={"markup": True})
            success = self.notifier.send_job_alert(job, profile)
            if success:
                notified_count += 1
                self.db.mark_job_seen(job, profile.name, notified=True, status="NEW")
                logger.info(f"   ✅ Discord alert delivered successfully!")
            else:
                logger.warning(f"   ❌ Failed to send Discord alert for job {job.id}")
                self.db.mark_job_seen(job, profile.name, notified=False, status="SEND_FAILED")

            time.sleep(1.0)

        duration = time.time() - start_time
        self.db.record_scan(profile.name, total_found, new_jobs, notified_count, duration)
        logger.info(
            f"Scan finished for '{profile.name}': {total_found} found, {new_jobs} new, {notified_count} notified in {duration:.1f}s"
        )
        return {"found": total_found, "new": new_jobs, "notified": notified_count, "duration": duration}

    def run_all_searches(self) -> dict:
        """Run all enabled search profiles in sequence."""
        total_found = 0
        total_new = 0
        total_notified = 0
        active_searches = [s for s in self.config.searches if s.enabled]

        if not active_searches:
            logger.warning("No enabled search profiles found in configuration!")
            return {"found": 0, "new": 0, "notified": 0}

        logger.info(f"Starting scan cycle across {len(active_searches)} active search profiles...")

        for idx, profile in enumerate(active_searches):
            if not self.is_running:
                break

            result = self.scan_search_profile(profile)
            total_found += result["found"]
            total_new += result["new"]
            total_notified += result["notified"]

            if idx < len(active_searches) - 1 and self.is_running:
                delay = self.config.settings.request_delay_seconds + random.uniform(2.0, 4.0)
                logger.info(f"Waiting {delay:.1f}s before next search profile...")
                time.sleep(delay)

        return {"found": total_found, "new": total_new, "notified": total_notified}

    def start_daemon(self):
        """Run the bot in a continuous background loop checking periodically."""
        def handle_exit(signum, frame):
            logger.info("\nReceived exit signal. Shutting down gracefully...")
            self.is_running = False

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        interval_min = self.config.settings.check_interval_minutes
        logger.info(f"🚀 Job Alert Bot daemon started! Check interval: {interval_min} minutes.")

        while self.is_running:
            try:
                self.run_all_searches()
            except Exception as e:
                logger.exception(f"Unexpected error during scan cycle: {e}")

            if not self.is_running:
                break

            sleep_seconds = interval_min * 60
            logger.info(f"💤 Sleeping for {interval_min} minutes until next check... (Press Ctrl+C to stop)")

            slept = 0
            while slept < sleep_seconds and self.is_running:
                time.sleep(1)
                slept += 1

        logger.info("Bot stopped.")
