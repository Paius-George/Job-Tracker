import time
import datetime
import logging
from typing import Optional, Dict, Any
import requests

from src.scraper.models import JobPost, SearchProfile
from src.utils import hex_to_discord_color, clean_text

logger = logging.getLogger("job_bot")


class DiscordNotifier:
    """Formats and sends rich Discord embeds via webhooks."""

    def __init__(self, default_webhook_url: Optional[str] = None):
        self.default_webhook_url = default_webhook_url
        self.session = requests.Session()

    def build_embed(self, job: JobPost, profile: SearchProfile) -> Dict[str, Any]:
        """Create a Discord Embed dictionary for a job posting."""
        color = hex_to_discord_color(profile.embed_color, default=0x0A66C2)

        # Build fields list
        fields = []

        # Location field
        loc_str = job.location
        if job.workplace_type:
            icon = "🌐" if "remote" in job.workplace_type.lower() else "🏢"
            loc_str = f"{icon} {job.location} ({job.workplace_type})"
        fields.append({"name": "📍 Location", "value": loc_str, "inline": True})

        # Employment & Seniority
        employment_parts = []
        if job.employment_type:
            employment_parts.append(job.employment_type)
        if job.seniority_level:
            employment_parts.append(job.seniority_level)
        if employment_parts:
            fields.append({"name": "💼 Role Details", "value": " • ".join(employment_parts), "inline": True})

        # Post Date / Freshness
        posted_val = job.post_text or job.post_date or "Recently"
        fields.append({"name": "⏰ Posted", "value": f"*{posted_val}*", "inline": True})

        # Salary if available
        if job.salary:
            fields.append({"name": "💰 Salary", "value": f"**{job.salary}**", "inline": True})

        # Applicants if available
        if job.applicants:
            fields.append({"name": "👥 Applicants", "value": job.applicants, "inline": True})

        # Matched Search Name & Source
        fields.append({"name": "🏢 Source", "value": f"**{job.platform or 'LinkedIn'}**", "inline": True})
        fields.append({"name": "🏷️ Matched Filter", "value": f"`{profile.name}`", "inline": True})

        # Description snippet
        desc_snippet = ""
        if job.description:
            clean_desc = clean_text(job.description)
            if len(clean_desc) > 300:
                desc_snippet = f"> {clean_desc[:297]}...\n\n"
            else:
                desc_snippet = f"> {clean_desc}\n\n"

        embed_description = f"{desc_snippet}🔗 **[Click here to view & apply on {job.platform or 'Web'}]({job.job_url})**"

        # Author section (Company)
        author = {
            "name": job.company,
            "url": job.company_url or job.job_url,
        }
        if job.logo_url and job.logo_url.startswith("http"):
            author["icon_url"] = job.logo_url

        footer_icon = job.platform_icon or "https://cdn-icons-png.flaticon.com/512/3536/3536505.png"
        embed = {
            "title": f"📢 {job.title}",
            "url": job.job_url,
            "description": embed_description,
            "color": color,
            "author": author,
            "fields": fields,
            "footer": {
                "text": f"{job.platform or 'Job Bot'} • {profile.name}",
                "icon_url": footer_icon,
            },
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Thumbnail if company logo exists
        if job.logo_url and job.logo_url.startswith("http"):
            embed["thumbnail"] = {"url": job.logo_url}

        return embed

    def send_job_alert(self, job: JobPost, profile: SearchProfile, webhook_url: Optional[str] = None) -> bool:
        """Send a single job notification embed to Discord."""
        target_webhook = webhook_url or profile.webhook_url or self.default_webhook_url
        if not target_webhook or "YOUR_WEBHOOK" in target_webhook:
            logger.error("No valid Discord Webhook URL configured! Please set it in config.yaml or .env")
            return False

        embed = self.build_embed(job, profile)

        payload: Dict[str, Any] = {
            "username": f"{job.platform or 'Job'} Alert Bot",
            "avatar_url": job.platform_icon or "https://cdn-icons-png.flaticon.com/512/3536/3536505.png",
            "embeds": [embed],
        }

        # Role mention if specified
        if profile.role_id_to_mention:
            payload["content"] = f"<@&{profile.role_id_to_mention}> 🔔 **New Job Alert:** [{job.title}]({job.job_url})"

        return self._post_webhook(target_webhook, payload)

    def send_test_message(self, webhook_url: Optional[str] = None) -> bool:
        """Send a test message to verify the webhook connection."""
        target_webhook = webhook_url or self.default_webhook_url
        if not target_webhook or "YOUR_WEBHOOK" in target_webhook:
            logger.error("Invalid Webhook URL for test message.")
            return False

        payload = {
            "username": "LinkedIn Job Bot",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3536/3536505.png",
            "embeds": [
                {
                    "title": "✅ LinkedIn Job Alert Bot - Connection Successful!",
                    "description": "Your Discord webhook is configured properly. You will receive real-time job alerts matching your custom filters here.",
                    "color": 0x00D26A,
                    "fields": [
                        {"name": "Status", "value": "🟢 Online & Active", "inline": True},
                        {"name": "Timestamp", "value": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
                    ],
                    "footer": {"text": "Job Alert Bot Test Check"},
                }
            ],
        }

        return self._post_webhook(target_webhook, payload)

    def _post_webhook(self, webhook_url: str, payload: dict, max_retries: int = 3) -> bool:
        """Execute HTTP POST to Discord webhook with rate limit backoff."""
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(webhook_url, json=payload, timeout=10)

                if response.status_code in (200, 204):
                    return True
                elif response.status_code == 429:
                    retry_after = 2.0
                    try:
                        data = response.json()
                        retry_after = float(data.get("retry_after", 2.0))
                    except Exception:
                        pass
                    logger.warning(f"Discord rate limit hit (429). Waiting {retry_after}s before retrying...")
                    time.sleep(retry_after + 0.5)
                else:
                    logger.error(f"Discord webhook failed with HTTP {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception sending webhook (attempt {attempt}/{max_retries}): {e}")
                time.sleep(2 * attempt)

        return False
