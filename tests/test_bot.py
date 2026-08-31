import unittest
import datetime
import os
import tempfile
from src.scraper.models import JobPost, SearchProfile, SearchFilters, BotSettings, AppConfig
from src.scraper.linkedin import LinkedInScraper
from src.database import JobDatabase
from src.discord_notifier import DiscordNotifier
from src.tracker import (
    JuniorRoleFilter,
    titles_similar,
    normalize_text,
    TRACKER_STATUSES,
    ALL_STATUSES,
)


class TestJobBot(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_dir = tempfile.mkdtemp()
        self.db = JobDatabase(self.temp_db_file.name)

    def tearDown(self):
        try:
            os.remove(self.temp_db_file.name)
        except Exception:
            pass
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
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

    # ------------------------------------------------------------------
    # Phase 3: Junior role filtering engine
    # ------------------------------------------------------------------
    def _make_job(self, job_id, title, company="Tech Corp", description=None):
        return JobPost(
            id=job_id,
            title=title,
            company=company,
            location="Bucharest, Romania",
            job_url=f"https://example.com/jobs/{job_id}",
            description=description,
        )

    def test_junior_filter_excludes_senior_titles(self):
        f = JuniorRoleFilter()
        ok, reason = f.matches(self._make_job("1", "Senior Pentester"))
        self.assertFalse(ok)
        self.assertIn("senior", reason.lower())

    def test_junior_filter_allows_juniorless_titles_in_lenient_mode(self):
        f = JuniorRoleFilter()
        ok, reason = f.matches(self._make_job("2", "SOC Analyst L1"))
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_junior_filter_strict_mode_requires_include_keyword(self):
        f = JuniorRoleFilter(strict=True)
        ok, reason = f.matches(self._make_job("3", "SOC Analyst L1"))
        self.assertFalse(ok)

        ok2, _ = f.matches(self._make_job("4", "Junior Pentester"))
        self.assertTrue(ok2)

    def test_junior_filter_catches_false_positives_in_description(self):
        f = JuniorRoleFilter()
        job = self._make_job("5", "Cybersecurity Specialist", description="Candidates need 5+ years of experience.")
        ok, reason = f.matches(job)
        self.assertFalse(ok)
        self.assertIn("5+ years", reason)

    def test_junior_filter_disabled_accepts_everything(self):
        f = JuniorRoleFilter(enabled=False)
        ok, _ = f.matches(self._make_job("6", "Principal Engineer"))
        self.assertTrue(ok)

    # ------------------------------------------------------------------
    # Phase 3: Cross-platform deduplication helpers
    # ------------------------------------------------------------------
    def test_titles_similar(self):
        self.assertTrue(titles_similar("Junior Python Developer", "junior python developer"))
        self.assertTrue(titles_similar("SOC Analyst L1", "SOC Analyst (Level 1)"))
        self.assertFalse(titles_similar("SOC Analyst", "DevOps Engineer"))

    def test_normalize_text(self):
        self.assertEqual(normalize_text("IT-Support Specialist!"), "it support specialist")
        self.assertEqual(normalize_text(None), "")

    def test_find_similar_job_dedup(self):
        original = self._make_job("dup-1", "Junior Pentester", company="Bitdefender")
        self.db.mark_job_seen(original, search_name="Cyber", notified=True)

        # Same company, slightly different title on another platform
        twin = self._make_job("dup-2", "Junior Penetration Tester", company="BitDefender ")
        found = self.db.find_similar_job(twin.title, twin.company)
        self.assertIsNotNone(found)
        self.assertEqual(found["job_id"], "dup-1")

        # Different company -> no duplicate
        other = self._make_job("dup-3", "Junior Pentester", company="CrowdStrike")
        self.assertIsNone(self.db.find_similar_job(other.title, other.company))

    # ------------------------------------------------------------------
    # Phase 5: Application tracking (status management)
    # ------------------------------------------------------------------
    def test_update_status_and_get_jobs(self):
        job = self._make_job("track-1", "Helpdesk Technician")
        self.db.mark_job_seen(job, search_name="IT Support", notified=True)

        self.assertTrue(self.db.update_status("track-1", "APPLIED"))
        jobs = self.db.get_jobs(statuses=["APPLIED"])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "track-1")
        self.assertEqual(jobs[0]["status"], "APPLIED")

        # Default get_jobs() excludes system statuses
        self.db.mark_job_seen(self._make_job("track-2", "SOC Analyst"), search_name="SOC", notified=False, status="DUPLICATE")
        all_tracked = self.db.get_jobs()
        self.assertNotIn("DUPLICATE", {j["status"] for j in all_tracked})

        # Invalid status raises
        with self.assertRaises(ValueError):
            self.db.update_status("track-1", "NOT_A_STATUS")

    def test_status_migration_from_legacy_notified(self):
        """Legacy rows stored with status 'NOTIFIED' should surface as 'NEW'."""
        job = self._make_job("legacy-1", "IT Technician")
        # Simulate a legacy row by writing directly with the old default
        import sqlite3
        with sqlite3.connect(self.temp_db_file.name) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO seen_jobs (job_id, search_name, title, company, location, url, status) "
                "VALUES ('legacy-1', 's', 'IT Technician', 'Acme', 'Bucharest', 'http://x', 'NOTIFIED')"
            )
        # Touch the DB again to trigger the migration in _init_db
        db2 = JobDatabase(self.temp_db_file.name)
        tracked = db2.get_jobs(statuses=["NEW"])
        self.assertIn("legacy-1", {j["job_id"] for j in tracked})

    def test_status_constants(self):
        for s in TRACKER_STATUSES:
            self.assertIn(s, ALL_STATUSES)

    # ------------------------------------------------------------------
    # 30-minute freshness window (user requirement)
    # ------------------------------------------------------------------
    def test_age_filter_last_30_minutes(self):
        from src.scraper.linkedin import _parse_age_hours

        # "minutes ago" handled precisely
        self.assertLessEqual(_parse_age_hours(None, "12 minutes ago"), 0.5)
        self.assertGreater(_parse_age_hours(None, "45 minutes ago"), 0.5)
        # "hours ago" always exceeds the 30 minute window
        self.assertGreater(_parse_age_hours(None, "1 hour ago"), 0.5)
        # larger units -> huge value
        self.assertGreater(_parse_age_hours(None, "2 days ago"), 9999)
        # unknown -> None (age cannot be determined)
        self.assertIsNone(_parse_age_hours(None, None))

        # Exact ISO timestamp (LinkedIn <time datetime="...">, UTC)
        recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertLessEqual(_parse_age_hours(recent, None), 0.5)
        self.assertGreater(_parse_age_hours(old, None), 0.5)

    def test_matches_filters_enforces_30_minute_window(self):
        scraper = LinkedInScraper()
        filters = SearchFilters(max_age_hours=0.5)

        fresh = JobPost(id="t1", title="Helpdesk Technician", company="Acme",
                        location="Bucharest, Romania", job_url="http://x", post_text="12 minutes ago")
        stale = JobPost(id="t2", title="Helpdesk Technician", company="Acme",
                        location="Bucharest, Romania", job_url="http://x", post_text="59 minutes ago")
        old = JobPost(id="t3", title="Helpdesk Technician", company="Acme",
                      location="Bucharest, Romania", job_url="http://x", post_text="2 days ago")

        ok_fresh, _ = scraper.matches_filters(fresh, filters)
        ok_stale, reason_stale = scraper.matches_filters(stale, filters)
        ok_old, _ = scraper.matches_filters(old, filters)

        self.assertTrue(ok_fresh)
        self.assertFalse(ok_stale)
        self.assertIn("0.5", reason_stale)
        self.assertFalse(ok_old)

    def test_date_posted_map_has_30min(self):
        from src.scraper.linkedin import DATE_POSTED_MAP
        self.assertEqual(DATE_POSTED_MAP["past_30min"], "r1800")

    # ------------------------------------------------------------------
    # strategy.md §2: source-specific scrapers
    # ------------------------------------------------------------------
    def _mock_response(self, status_code=200, text="", json_data=None):
        from unittest import mock
        resp = mock.Mock(status_code=status_code)
        resp.text = text
        if json_data is not None:
            resp.json = mock.Mock(return_value=json_data)
        resp.raise_for_status = mock.Mock()
        return resp

    def test_bestjobs_scraper_parses_cards(self):
        from unittest import mock
        from src.scraper.bestjobs import BestJobsScraper

        html = """
        <html><body>
          <div class="card">
            <a href="/loc-de-munca/acme-junior-qa-tester-12345" class="absolute inset-0 z-1" aria-label="Junior QA Tester">
              <span class="hidden">Junior QA Tester</span>
            </a>
            <div class="grow p-3">
              <h2 class="line-clamp-2 text-base font-bold leading-6">Junior QA Tester</h2>
              <div class="mt-2 line-clamp-1 w-full text-sm text-ink-medium">Acme Corp Romania</div>
            </div>
          </div>
          <div class="card">
            <a href="/loc-de-munca/beta-manual-tester-999" class="absolute inset-0 z-1" aria-label="Manual Tester">
              <span class="hidden">Manual Tester</span>
            </a>
            <div class="grow p-3">
              <h2 class="line-clamp-2 text-base font-bold leading-6">Manual Tester</h2>
              <div class="mt-2 line-clamp-1 w-full text-sm text-ink-medium">Beta SRL</div>
            </div>
          </div>
        </body></html>
        """
        scraper = BestJobsScraper()
        profile = SearchProfile(name="QA", keywords='"QA Tester" OR "QA Engineer"', location="Bucharest, Romania")

        with mock.patch.object(scraper.session, "get", return_value=self._mock_response(text=html)):
            jobs = scraper.search_profile_jobs(profile)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].title, "Junior QA Tester")
        self.assertEqual(jobs[0].company, "Acme Corp Romania")
        self.assertEqual(jobs[0].id, "bestjobs-12345")
        self.assertTrue(jobs[0].job_url.startswith("https://www.bestjobs.eu/loc-de-munca/"))

        url = scraper._build_search_url(profile)
        self.assertIn("bestjobs.eu/ro/locuri-de-munca?keyword=qa+tester", url)
        self.assertIn("location=bucuresti", url)

    def test_stagiipebune_scraper_parses_jobs(self):
        from unittest import mock
        from src.scraper.stagiipebune import StagiiPeBuneScraper

        html = """
        <html><body>
          <a href="/students/jobs/">Stagii</a>
          <a href="/jobs/veridion/data-assets-intern-09346">Data Assets Intern</a>
          <a href="/jobs/aquasoft/artificial-intelligence-internship-11819">Artificial Intelligence Internship</a>
          <a href="/companies/">Companies</a>
        </body></html>
        """
        scraper = StagiiPeBuneScraper()
        profile = SearchProfile(name="QA", keywords="QA Tester", location="Bucharest, Romania")

        with mock.patch.object(scraper.session, "get", return_value=self._mock_response(text=html)):
            jobs = scraper.search_profile_jobs(profile)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].title, "Data Assets Intern")
        self.assertEqual(jobs[0].company, "Veridion")
        self.assertEqual(jobs[0].id, "spb-09346")
        self.assertEqual(jobs[0].platform, "StagiiPeBune")

    def test_hipo_scraper_graceful_when_down(self):
        from unittest import mock
        from src.scraper.hipo import HipoScraper

        scraper = HipoScraper()
        profile = SearchProfile(name="IT Support", keywords="Helpdesk", location="Bucharest, Romania")

        # Hipo.ro returns a maintenance page with HTTP 200 but no job links
        with mock.patch.object(scraper.session, "get", return_value=self._mock_response(text="<html><body>maintenance</body></html>")):
            jobs = scraper.search_profile_jobs(profile)
        self.assertEqual(jobs, [])

    def test_ats_scraper_greenhouse_and_lever(self):
        from unittest import mock
        from src.scraper.ats import CompanyATSScraper

        ats_file = os.path.join(self.temp_dir, "ats.json")
        with open(ats_file, "w") as f:
            f.write('{"greenhouse": ["bitpanda"], "lever": ["metabase"]}')

        scraper = CompanyATSScraper(ats_file=ats_file)
        self.assertEqual(scraper.greenhouse_boards, ["bitpanda"])
        self.assertEqual(scraper.lever_companies, ["metabase"])

        greenhouse_payload = {
            "jobs": [
                {"id": 111, "title": "Graduate Frontend Engineer",
                 "absolute_url": "https://job-boards.eu.greenhouse.io/bitpanda/jobs/111",
                 "location": {"name": "București, Bucharest, Romania"},
                 "first_published": "2026-08-31T10:00:00+02:00"},
                {"id": 222, "title": "Director of Sales",
                 "absolute_url": "https://job-boards.eu.greenhouse.io/bitpanda/jobs/222",
                 "location": {"name": "Berlin, Germany"}},
            ]
        }
        lever_payload = [
            {"id": "abc-1", "text": "Junior QA Engineer",
             "hostedUrl": "https://jobs.lever.co/metabase/abc-1",
             "categories": {"location": "Bucharest, Romania"},
             "createdAt": 1756634400000},
            {"id": "abc-2", "text": "Senior Backend Engineer",
             "hostedUrl": "https://jobs.lever.co/metabase/abc-2",
             "categories": {"location": "London, UK"}},
        ]

        profile = SearchProfile(name="QA", keywords="QA", location="Bucharest, Romania")

        def fake_get(url, **kwargs):
            if "greenhouse" in url:
                return self._mock_response(json_data=greenhouse_payload)
            return self._mock_response(json_data=lever_payload)

        with mock.patch.object(scraper.session, "get", side_effect=fake_get):
            jobs = scraper.search_profile_jobs(profile)

        # Berlin + London jobs are dropped (not Bucharest/remote)
        self.assertEqual(len(jobs), 2)
        self.assertEqual({j.platform for j in jobs}, {"Greenhouse", "Lever"})
        titles = {j.title for j in jobs}
        self.assertIn("Graduate Frontend Engineer", titles)
        self.assertIn("Junior QA Engineer", titles)
        lever_job = [j for j in jobs if j.platform == "Lever"][0]
        self.assertTrue(lever_job.post_date.startswith("20"))  # epoch ms converted

    def test_ats_scraper_missing_company_file(self):
        from src.scraper.ats import CompanyATSScraper
        scraper = CompanyATSScraper(ats_file=os.path.join(self.temp_dir, "missing.json"))
        profile = SearchProfile(name="QA", keywords="QA", location="Bucharest, Romania")
        self.assertEqual(scraper.search_profile_jobs(profile), [])

    def test_registry_contains_strategy_sources(self):
        from src.scraper import SCRAPER_REGISTRY
        for code in ("linkedin", "ejobs", "bestjobs", "hipo", "stagiipebune", "ats", "google"):
            self.assertIn(code, SCRAPER_REGISTRY)

    def test_romanian_experience_guardrails(self):
        from src.tracker import DEFAULT_DESCRIPTION_EXCLUDE_KEYWORDS
        for kw in ("5+ ani", "minim 5 ani", "peste 5 ani", "5 ani de experienta"):
            self.assertIn(kw, DEFAULT_DESCRIPTION_EXCLUDE_KEYWORDS)


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
