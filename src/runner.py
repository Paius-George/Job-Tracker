import time
import random
import signal
import logging
from typing import Optional
from rich.console import Console

from src.scraper.models import AppConfig, SearchProfile
from src.scraper.linkedin import LinkedInScraper
from src.database import JobDatabase
from src.discord_notifier import DiscordNotifier

logger = logging.getLogger("job_bot")
console = Console()


class JobBotRunner:
    """Coordinates scraping, filtering, duplicate tracking, and Discord alerting."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.db = JobDatabase(config.settings.database_path)
        self.scraper = LinkedInScraper(request_delay=config.settings.request_delay_seconds)
        self.notifier = DiscordNotifier(default_webhook_url=config.settings.discord_webhook_url)
        self.is_running = True

    def scan_search_profile(self, profile: SearchProfile) -> dict:
        """Execute scan for a single search profile."""
        if not profile.enabled:
            logger.info(f"Skipping disabled search: '{profile.name}'")
            return {"found": 0, "new": 0, "notified": 0, "duration": 0.0}

        start_time = time.time()
        logger.info(f"🔍 Starting scan for: [bold cyan]{profile.name}[/bold cyan]", extra={"markup": True})

        # 1. Scrape search results
        max_pages = profile.max_pages if profile.max_pages is not None else self.config.settings.max_pages_per_search
        scraped_jobs = self.scraper.search_profile_jobs(profile, max_pages=max_pages)
        total_found = len(scraped_jobs)

        new_jobs = 0
        notified_count = 0

        for job in scraped_jobs:
            # 2. Check duplicate database
            if self.db.is_job_seen(job.id):
                logger.debug(f"Job {job.id} ('{job.title}') already seen. Skipping.")
                continue

            new_jobs += 1
            logger.info(f"🆕 Discovered new job: [bold]{job.title}[/bold] @ [green]{job.company}[/green] ({job.location})", extra={"markup": True})

            # 3. Apply custom title/company filters before details fetch
            matched, reason = self.scraper.matches_filters(job, profile.filters)
            if not matched:
                logger.info(f"   ⏩ Filtered out: {reason}")
                self.db.mark_job_seen(job, profile.name, notified=False, status="FILTERED")
                continue

            # 4. Fetch rich job details (description, criteria) if enabled
            if self.config.settings.fetch_job_details:
                try:
                    time.sleep(random.uniform(1.0, 2.0))
                    job = self.scraper.fetch_job_details(job)
                    # Re-verify filters with description now available
                    matched_desc, desc_reason = self.scraper.matches_filters(job, profile.filters)
                    if not matched_desc:
                        logger.info(f"   ⏩ Filtered out after details check: {desc_reason}")
                        self.db.mark_job_seen(job, profile.name, notified=False, status="FILTERED_DESC")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to fetch job details for {job.id}: {e}")

            # 5. Send Discord alert
            logger.info(f"   🚀 Sending Discord alert for: [bold green]{job.title}[/bold green]", extra={"markup": True})
            success = self.notifier.send_job_alert(job, profile)
            if success:
                notified_count += 1
                self.db.mark_job_seen(job, profile.name, notified=True, status="NOTIFIED")
                logger.info(f"   ✅ Discord alert delivered successfully!")
            else:
                logger.warning(f"   ❌ Failed to send Discord alert for job {job.id}")
                self.db.mark_job_seen(job, profile.name, notified=False, status="SEND_FAILED")

            # Small delay between notifications
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

            # Delay between searches
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
            
            # Sleep in short increments to respond quickly to Ctrl+C
            slept = 0
            while slept < sleep_seconds and self.is_running:
                time.sleep(1)
                slept += 1

        logger.info("Bot stopped.")
