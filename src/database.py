import os
import sqlite3
import datetime
import logging
from typing import Optional, Dict, Any, List
from src.scraper.models import JobPost

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
            conn.commit()

    def is_job_seen(self, job_id: str) -> bool:
        """Check whether a job has already been recorded in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (str(job_id),))
            return cursor.fetchone() is not None

    def mark_job_seen(self, job: JobPost, search_name: str, notified: bool = True, status: str = "NOTIFIED"):
        """Record a job as seen and optionally notified."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        notified_at = now if notified else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO seen_jobs 
                (job_id, search_name, title, company, location, url, discovered_at, notified_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(job.id),
                search_name,
                job.title,
                job.company,
                job.location,
                job.job_url,
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
