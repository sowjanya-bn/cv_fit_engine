"""
sponsor_checker.py

Checks whether a company name appears in the UK Home Office register of
licensed sponsors (Worker and Temporary Worker route).

The register is a CSV published daily at GOV.UK. This module:
  - Downloads the latest CSV on first use and caches it locally at
    ~/.cvfit/sponsor_register.csv
  - Exposes a simple is_licensed_sponsor(name) -> str function that
    returns one of three values: "licensed" | "not_licensed" | "unknown"
  - Uses fuzzy matching (rapidfuzz) to handle name variations between
    job listings and the official register

Note: Licensed = employer has legal permission to sponsor.
It does NOT mean they are actively sponsoring or hiring on this route.
That must be verified separately (job ad, recruiter confirmation).
"""

import csv
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── constants ──────────────────────────────────────────────────────────────
REGISTER_URL = (
    "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
)
CACHE_DIR = Path.home() / ".cvfit"
CACHE_FILE = CACHE_DIR / "sponsor_register.csv"
CACHE_MAX_AGE_HOURS = 24  # refresh if older than this

# Column name in the GOV.UK CSV (as of 2026)
REGISTER_NAME_COLUMN = "Organisation Name"

# Fuzzy match threshold — 0-100. 88 catches common abbreviations and
# punctuation differences without too many false positives.
FUZZY_THRESHOLD = 88

# Fallback: return "unknown" if rapidfuzz is not installed rather than crashing
try:
    from rapidfuzz import fuzz, process as rfprocess
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False
    logger.warning(
        "rapidfuzz not installed — sponsor checker will use exact matching only. "
        "Run: pip install rapidfuzz"
    )


# ── cache management ───────────────────────────────────────────────────────

def _cache_is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(CACHE_FILE.stat().st_mtime)
    return age < timedelta(hours=CACHE_MAX_AGE_HOURS)


def _fetch_register_url() -> str | None:
    """Scrape the GOV.UK publication page to find today's CSV download URL."""
    try:
        r = httpx.get(REGISTER_URL, timeout=15, follow_redirects=True)
        r.raise_for_status()
        # The CSV link pattern on the GOV.UK page
        match = re.search(
            r'https://assets\.publishing\.service\.gov\.uk[^\s"\']+\.csv',
            r.text
        )
        if match:
            return match.group(0)
    except Exception as e:
        logger.warning(f"Could not fetch register page: {e}")
    return None


def _download_register() -> bool:
    """Download latest register CSV to cache. Returns True on success."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    csv_url = _fetch_register_url()
    if not csv_url:
        logger.warning("Could not determine register CSV URL.")
        return False
    try:
        logger.info(f"Downloading sponsor register from {csv_url}")
        with httpx.stream("GET", csv_url, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with open(CACHE_FILE, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Sponsor register cached at {CACHE_FILE}")
        return True
    except Exception as e:
        logger.warning(f"Failed to download sponsor register: {e}")
        return False


# ── name loading ───────────────────────────────────────────────────────────

_sponsor_names: list[str] | None = None  # in-memory cache after first load


def _load_sponsor_names() -> list[str]:
    global _sponsor_names
    if _sponsor_names is not None:
        return _sponsor_names

    if not _cache_is_fresh():
        success = _download_register()
        if not success and not CACHE_FILE.exists():
            logger.warning("No sponsor register available — returning 'unknown' for all checks.")
            _sponsor_names = []
            return _sponsor_names

    names = []
    try:
        with open(CACHE_FILE, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get(REGISTER_NAME_COLUMN, "").strip()
                if name:
                    names.append(name)
    except Exception as e:
        logger.warning(f"Could not read sponsor register CSV: {e}")

    _sponsor_names = names
    logger.info(f"Loaded {len(_sponsor_names)} licensed sponsors from register.")
    return _sponsor_names


def invalidate_cache():
    """Force a fresh download on next check. Call if register seems stale."""
    global _sponsor_names
    _sponsor_names = None
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


# ── public API ─────────────────────────────────────────────────────────────

def is_licensed_sponsor(company_name: str) -> str:
    """
    Check whether company_name appears in the UK licensed sponsor register.

    Returns:
        "licensed"     — confident match found in register
        "not_licensed" — register loaded, no match found
        "unknown"      — register unavailable or company_name is empty
    """
    if not company_name or not company_name.strip():
        return "unknown"

    names = _load_sponsor_names()

    if not names:
        return "unknown"

    query = company_name.strip()

    # 1. Exact match first (fast path)
    if query in names:
        return "licensed"

    # 2. Case-insensitive exact match
    query_lower = query.lower()
    for name in names:
        if name.lower() == query_lower:
            return "licensed"

    # 3. Fuzzy match if rapidfuzz is available
    if _FUZZY_AVAILABLE:
        result = rfprocess.extractOne(
            query,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=FUZZY_THRESHOLD,
        )
        if result:
            matched_name, score, _ = result
            logger.debug(f"Fuzzy match: '{query}' → '{matched_name}' (score {score})")
            return "licensed"

    return "not_licensed"


def sponsor_status_label(status: str) -> str:
    """Human-readable label for display in UI."""
    return {
        "licensed": "✓ Licensed sponsor",
        "not_licensed": "✗ Not on register",
        "unknown": "? Sponsor unknown",
    }.get(status, "? Sponsor unknown")
