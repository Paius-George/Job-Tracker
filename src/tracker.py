"""
Role filtering & application tracking engine (Phases 3 & 5 of job_tracker_plan.md).

Provides:
    * ``JuniorRoleFilter``  - global include/exclude keyword engine that keeps
      only junior / internship / entry-level roles and drops false positives
      (e.g. senior roles that merely "mentor juniors").
    * ``normalize_text`` / ``titles_similar`` - fuzzy-matching helpers used for
      cross-platform deduplication of similar jobs (same company, similar title).
    * Tracker status constants shared by the database, runner and dashboard.
"""

import re
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from src.scraper.models import JobPost

# --- Application tracking statuses (Phase 5: the "Tracker") -----------------
TRACKER_STATUSES = ["NEW", "APPLIED", "INTERVIEWING", "OFFER", "REJECTED", "HIDDEN"]

# Internal / system statuses (not selectable in the UI)
SYSTEM_STATUSES = ["FILTERED", "FILTERED_DESC", "DUPLICATE", "SEND_FAILED"]

ALL_STATUSES = TRACKER_STATUSES + SYSTEM_STATUSES

# --- Keyword lists (Phase 3: data filtering & enrichment) --------------------
# Roles that MUST appear in the title/description in strict mode.
DEFAULT_INCLUDE_KEYWORDS = [
    "junior", "intern", "internship", "entry level", "entry-level", "entry",
    "graduate", "trainee", "stagiu", "practica", "practică",
]

# Seniority keywords that disqualify a job if found in the title.
DEFAULT_TITLE_EXCLUDE_KEYWORDS = [
    "senior", "lead", "manager", "principal", "staff", "director",
    "head of", "architect", "vp", "vice president", "head",
]

# Experience requirements that disqualify a job if found in the description.
# English + Romanian variants (strategy.md §4 keyword guardrails).
DEFAULT_DESCRIPTION_EXCLUDE_KEYWORDS = [
    "5+ years", "5-7 years", "5 - 7 years", "6+ years", "7+ years",
    "8+ years", "10+ years", "at least 5 years", "minimum 5 years",
    "minimum of 5 years", "minim 5 ani", "peste 5 ani", "5+ ani",
    "5 ani experienta", "5 ani de experienta", "cel putin 5 ani",
]


def normalize_text(text: Optional[str]) -> str:
    """Lowercase, strip accents-invariant punctuation and collapse whitespace.

    Used to compare titles/companies across platforms (e.g. 'Python Developer'
    vs 'python  developer' vs 'Python-Developer')."""
    if not text:
        return ""
    lowered = text.lower().strip()
    # Replace any run of non-alphanumeric characters with a single space
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def _token_matches(token: str, candidates: set) -> bool:
    """Check whether a title token fuzzy-matches any candidate token."""
    for other in candidates:
        if token == other:
            return True
        if len(token) >= 3 and token in other:
            return True
        if SequenceMatcher(None, token, other).ratio() >= 0.7:
            return True
    return False


def titles_similar(title_a: str, title_b: str, threshold: float = 0.85) -> bool:
    """Return True when two job titles are near-duplicates.

    Combines three signals so variants like 'SOC Analyst L1' vs
    'SOC Analyst (Level 1)' or 'Junior Pentester' vs 'Junior Penetration
    Tester' are caught, while unrelated titles are rejected:
        1. character similarity of the normalized titles,
        2. character similarity with all spaces stripped (catches 'L1/Level 1'),
        3. fuzzy token coverage of the shorter title (catches compound words).
    """
    if not title_a or not title_b:
        return False

    norm_a = normalize_text(title_a)
    norm_b = normalize_text(title_b)
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b:
        return True

    # 1. Direct character similarity
    if SequenceMatcher(None, norm_a, norm_b).ratio() >= threshold:
        return True

    # 2. Space-stripped similarity (handles 'L 1' vs 'L1', punctuation variants)
    stripped_ratio = SequenceMatcher(
        None, norm_a.replace(" ", ""), norm_b.replace(" ", "")
    ).ratio()
    if stripped_ratio >= threshold:
        return True

    # 3. Token-level fuzzy coverage of the shorter title
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    short, long = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    matched = sum(1 for token in short if _token_matches(token, long))
    coverage = matched / len(short)
    return coverage >= 0.75


class JuniorRoleFilter:
    """Global keyword filtering engine for junior/internship roles (Phase 3).

    Behaviour:
        * Title excludes are ALWAYS applied (seniority words in the title are
          a hard disqualifier).
        * Description excludes are ALWAYS applied (catches false positives
          like a SOC Analyst L1 role demanding "5+ years experience").
        * Include keywords are only enforced in ``strict`` mode. In lenient
          mode (default) a job lacking "junior/intern" in the title is still
          accepted if the per-profile search filters matched it, because
          profiles target specific roles (e.g. "SOC Analyst L1").
    """

    def __init__(
        self,
        enabled: bool = True,
        strict: bool = False,
        include_keywords: Optional[List[str]] = None,
        title_exclude_keywords: Optional[List[str]] = None,
        description_exclude_keywords: Optional[List[str]] = None,
    ):
        self.enabled = enabled
        self.strict = strict
        self.include_keywords = include_keywords or list(DEFAULT_INCLUDE_KEYWORDS)
        self.title_exclude_keywords = title_exclude_keywords or list(DEFAULT_TITLE_EXCLUDE_KEYWORDS)
        self.description_exclude_keywords = description_exclude_keywords or list(DEFAULT_DESCRIPTION_EXCLUDE_KEYWORDS)

    @staticmethod
    def _contains_any(haystack: str, keywords: List[str]) -> Optional[str]:
        """Return the first keyword found in haystack (case-insensitive), else None."""
        lowered = haystack.lower()
        for keyword in keywords:
            if keyword.lower() in lowered:
                return keyword
        return None

    def matches(self, job: JobPost) -> Tuple[bool, str]:
        """Evaluate a job against the engine.

        Returns:
            (True, "") when the job passes, otherwise (False, reason).
        """
        if not self.enabled:
            return True, ""

        title = job.title or ""
        description = job.description or ""

        # 1. Hard excludes on the title
        hit = self._contains_any(title, self.title_exclude_keywords)
        if hit:
            return False, f"title excluded by keyword '{hit}'"

        # 2. Hard excludes on the description (experience requirements etc.)
        if description:
            hit = self._contains_any(description, self.description_exclude_keywords)
            if hit:
                return False, f"description excluded by keyword '{hit}'"

        # 3. Include keywords (strict mode only)
        if self.strict:
            include_hit = self._contains_any(title, self.include_keywords)
            if not include_hit and description:
                include_hit = self._contains_any(description, self.include_keywords)
            if not include_hit:
                return False, "no junior/internship include keyword found (strict mode)"

        return True, ""