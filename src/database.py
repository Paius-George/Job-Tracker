import os
import sqlite3
import datetime
import logging
from typing import Optional, Dict, Any, List
from src.scraper.models import JobPost
from src.tracker import ALL_STATUSES, normalize_text, titles_similar

logger = logging.getLogger("job_bot")


class JobDatabase:
    """Manages SQLite storage for tracking seen and notified jobs to prevent duplicate alerts."""

    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create necessary tables and indices if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    job_id TEXT PRIMARY KEY,
                    search_name TEXT,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    url TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified_at TIMESTAMP,
                    status TEXT DEFAULT 'NOTIFIED'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_name TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    jobs_found INTEGER DEFAULT 0,
                    jobs_new INTEGER DEFAULT 0,
                    jobs_notified INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_jobs_id ON seen_jobs(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_jobs_date ON seen_jobs(discovered_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_jobs_status ON seen_jobs(status)")

            # --- Migrations for the application tracker (Phase 5 of the plan) ---
            cursor.execute("PRAGMA table_info(seen_jobs)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "platform" not in existing_cols:
                cursor.execute("ALTER TABLE seen_jobs ADD COLUMN platform TEXT")
                logger.info("Database migrated: added 'platform' column to seen_jobs.")

            # Normalize legacy status values into the tracker vocabulary
            cursor.execute("UPDATE seen_jobs SET status = 'NEW' WHERE status = 'NOTIFIED'")
            conn.commit()

    def is_job_seen(self, job_id: str) -> bool:
        """Check whether a job has already been recorded in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (str(job_id),))
            return cursor.fetchone() is not None

    def mark_job_seen(self, job: JobPost, search_name: str, notified: bool = True, status: str = "NEW", platform: Optional[str] = None):
        """Record a job as seen and optionally notified."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        notified_at = now if notified else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO seen_jobs 
                (job_id, search_name, title, company, location, url, platform, discovered_at, notified_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(job.id),
                search_name,
                job.title,
                job.company,
                job.location,
                job.job_url,
                platform or job.platform,
                now,
                notified_at,
                status
            ))
            conn.commit()

    def record_scan(self, search_name: str, found: int, new_jobs: int, notified: int, duration: float):
        """Save scan execution telemetry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scan_history (search_name, jobs_found, jobs_new, jobs_notified, duration_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (search_name, found, new_jobs, notified, duration))
            conn.commit()

    def update_status(self, job_id: str, status: str) -> bool:
        """Update the application tracking status of a job (Phase 5).

        Valid statuses: NEW, APPLIED, INTERVIEWING, OFFER, REJECTED, HIDDEN
        (system statuses FILTERED / DUPLICATE / SEND_FAILED are also accepted
        for internal bookkeeping).
        """
        if status not in ALL_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(ALL_STATUSES)}")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE seen_jobs SET status = ? WHERE job_id = ?", (status, str(job_id)))
            conn.commit()
            if cursor.rowcount == 0:
                logger.warning(f"Cannot update status: job '{job_id}' not found in database.")
                return False
            logger.debug(f"Job '{job_id}' status updated to '{status}'.")
            return True

    def get_jobs(
        self,
        statuses: Optional[List[str]] = None,
        platform: Optional[str] = None,
        search_name: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch tracked jobs with optional filters (used by dashboard & CLI).

        Args:
            statuses: Only return jobs whose status is in this list.
                      Defaults to all tracker statuses (system statuses excluded).
            platform: Filter by platform name (e.g. 'eJobs.ro', 'LinkedIn').
            search_name: Filter by search profile name.
            limit: Maximum number of rows returned.
        """
        if statuses is None:
            statuses = ["NEW", "APPLIED", "INTERVIEWING", "OFFER", "REJECTED", "HIDDEN"]

        query = "SELECT * FROM seen_jobs WHERE status IN ({})".format(",".join("?" for _ in statuses))
        params: List[Any] = list(statuses)

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if search_name:
            query += " AND search_name = ?"
            params.append(search_name)

        query += " ORDER BY discovered_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def find_similar_job(self, title: str, company: str, threshold: float = 0.85) -> Optional[Dict[str, Any]]:
        """Cross-platform deduplication (Phase 3): find an already-tracked job
        with a very similar title at the same company.

        Only 'real' tracked jobs count as potential duplicates (system
        statuses like FILTERED / DUPLICATE / HIDDEN are ignored). Returns the
        existing job as a dict, or None when no similar job exists.
        """
        tracked = ["NEW", "APPLIED", "INTERVIEWING", "OFFER", "REJECTED"]
        placeholders = ",".join("?" for _ in tracked)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT job_id, title, company, url, platform, status FROM seen_jobs WHERE status IN ({placeholders})",
                tracked,
            )
            rows = cursor.fetchall()

        company_key = normalize_text(company)
        if not company_key:
            return None

        for row in rows:
            if normalize_text(row["company"]) != company_key:
                continue
            if titles_similar(title, row["title"], threshold=threshold):
                return dict(row)
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Return high-level statistics about stored jobs and scan runs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM seen_jobs")
            total_seen = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM seen_jobs WHERE notified_at IS NOT NULL")
            total_notified = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scan_history")
            total_scans = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(timestamp) FROM scan_history")
            last_scan_row = cursor.fetchone()
            last_scan = last_scan_row[0] if last_scan_row and last_scan_row[0] else "Never"

            # Application tracking status breakdown (Phase 5)
            cursor.execute("SELECT status, COUNT(*) FROM seen_jobs GROUP BY status ORDER BY COUNT(*) DESC")
            status_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

            # Recent 5 notified jobs
            cursor.execute("""
                SELECT job_id, title, company, location, search_name, notified_at, url 
                FROM seen_jobs 
                WHERE notified_at IS NOT NULL 
                ORDER BY discovered_at DESC 
                LIMIT 5
            """)
            recent_jobs = [dict(row) for row in cursor.fetchall()]

            return {
                "total_seen": total_seen,
                "total_notified": total_notified,
                "total_scans": total_scans,
                "last_scan": last_scan,
                "recent_jobs": recent_jobs,
                "status_breakdown": status_breakdown,
            }

    def clear_all(self):
        """Reset database tables (useful for testing or full reset)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM seen_jobs")
            cursor.execute("DELETE FROM scan_history")
            conn.commit()
            logger.info("Database records cleared successfully.")

    def cleanup_old_records(self, days: int = 60):
        """Delete records older than specified number of days to keep database compact."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM seen_jobs 
                WHERE discovered_at < datetime('now', ? || ' days')
            """, (f"-{days}",))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Purged {deleted} records older than {days} days from database.")
