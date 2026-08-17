import unittest
import os
import tempfile
from src.scraper.models import JobPost, SearchProfile, SearchFilters, BotSettings, AppConfig
from src.scraper.linkedin import LinkedInScraper
from src.database import JobDatabase
from src.discord_notifier import DiscordNotifier


class TestJobBot(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = JobDatabase(self.temp_db_file.name)

    def tearDown(self):
        try:
            os.remove(self.temp_db_file.name)
        except Exception:
            pass

    def test_filter_matching(self):
        scraper = LinkedInScraper()

        filters = SearchFilters(
            title_must_include=["Python", "Backend"],
            title_must_exclude=["Senior", "Lead", "Staff"],
            companies_exclude=["Revature"],
            description_must_exclude=["security clearance required"]
        )

        # Case 1: Matching Junior Python Job
        job1 = JobPost(
            id="101",
            title="Junior Python Developer",
            company="Tech Corp",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/101",
            description="Looking for a junior Python engineer to build APIs."
        )
        matched1, _ = scraper.matches_filters(job1, filters)
        self.assertTrue(matched1)

        # Case 2: Excluded by Senior Title
        job2 = JobPost(
            id="102",
            title="Senior Python Backend Architect",
            company="Tech Corp",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/102"
        )
        matched2, reason2 = scraper.matches_filters(job2, filters)
        self.assertFalse(matched2)
        self.assertIn("Senior", reason2)

        # Case 3: Excluded by Company Blacklist
        job3 = JobPost(
            id="103",
            title="Python Developer",
            company="Revature Global",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/103"
        )
        matched3, reason3 = scraper.matches_filters(job3, filters)
        self.assertFalse(matched3)
        self.assertIn("Revature", reason3)

        # Case 4: Excluded by Description keyword
        job4 = JobPost(
            id="104",
            title="Backend Python Developer",
            company="Defense Contractor",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/104",
            description="Active Top Secret Security Clearance required for this role."
        )
        matched4, reason4 = scraper.matches_filters(job4, filters)
        self.assertFalse(matched4)
        self.assertIn("security clearance", reason4.lower())

    def test_database_duplicate_prevention(self):
        job = JobPost(
            id="99901",
            title="Python Software Engineer",
            company="Awesome Startup",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/99901"
        )

        self.assertFalse(self.db.is_job_seen("99901"))
        self.db.mark_job_seen(job, search_name="Python Search", notified=True)
        self.assertTrue(self.db.is_job_seen("99901"))

        stats = self.db.get_stats()
        self.assertEqual(stats["total_seen"], 1)
        self.assertEqual(stats["total_notified"], 1)

    def test_discord_embed_builder(self):
        notifier = DiscordNotifier()
        profile = SearchProfile(
            name="Python Junior Alerts",
            embed_color="#3776AB"
        )
        job = JobPost(
            id="12345",
            title="Junior Python Engineer",
            company="Stripe",
            location="Remote",
            job_url="https://linkedin.com/jobs/view/12345",
            logo_url="https://example.com/logo.png",
            workplace_type="Remote",
            employment_type="Full-time",
            seniority_level="Entry level",
            salary="$90,000 - $110,000",
            post_text="1 hour ago",
            description="Join our backend infrastructure team building scalable payments APIs."
        )

        embed = notifier.build_embed(job, profile)
        self.assertIn("Junior Python Engineer", embed["title"])
        self.assertEqual(embed["url"], "https://linkedin.com/jobs/view/12345")
        self.assertEqual(embed["color"], 0x3776AB)
        self.assertEqual(embed["author"]["name"], "Stripe")
        self.assertEqual(embed["author"]["icon_url"], "https://example.com/logo.png")

        # Check fields
        field_names = [f["name"] for f in embed["fields"]]
        self.assertIn("📍 Location", field_names)
        self.assertIn("💼 Role Details", field_names)
        self.assertIn("⏰ Posted", field_names)
        self.assertIn("💰 Salary", field_names)
        self.assertIn("🏷️ Matched Filter", field_names)


if __name__ == "__main__":
    unittest.main()
