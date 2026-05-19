"""
Sponsor licence checker — checks whether an employer is on the UK Government's
Register of Licensed Sponsors (Worker and Temporary Worker routes).

The register is a CSV published daily at:
https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers

Usage:
    checker = SponsorChecker()
    status = checker.check("Tata Consultancy Services")
    # returns "licensed" or "not_licensed"
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REGISTER_URL = (
    "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
)
# Direct CSV — updated daily by UKVI. We re-fetch if the cached file is older than 1 day.
_CSV_URL_TEMPLATE = (
    "https://assets.publishing.service.gov.uk/media/"
    "{media_id}/2026-05-08_-_Worker_and_Temporary_Worker.csv"
)
LATEST_CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "69fdb9468cc72d2f863ea630/2026-05-08_-_Worker_and_Temporary_Worker.csv"
)

CACHE_PATH = Path.home() / ".cvfit" / "sponsor_register.csv"
CACHE_META_PATH = Path.home() / ".cvfit" / "sponsor_register_date.txt"


class SponsorChecker:
    """Binary sponsor licence checker against the UKVI register.

    Results: "licensed" | "not_licensed"

    The register is cached locally and refreshed at most once per day.
    Matching is case-insensitive exact match on the Organisation Name column.
    For fuzzy matching, install rapidfuzz and pass fuzzy=True.
    """

    def __init__(
        self,
        cache_path: Path = CACHE_PATH,
        fuzzy: bool = False,
        fuzzy_threshold: int = 88,
    ) -> None:
        self.cache_path = cache_path
        self.fuzzy = fuzzy
        self.fuzzy_threshold = fuzzy_threshold
        self._names: Optional[set[str]] = None

    def check(self, company_name: str) -> str:
        """Return 'licensed' or 'not_licensed' for the given company name."""
        names = self._load_names()
        normalised = company_name.strip().lower()

        if self.fuzzy:
            return self._fuzzy_check(normalised, names)

        return "licensed" if normalised in names else "not_licensed"

    def _fuzzy_check(self, normalised: str, names: set[str]) -> str:
        try:
            from rapidfuzz import process, fuzz  # type: ignore
        except ImportError:
            logger.warning(
                "rapidfuzz not installed — falling back to exact match. "
                "Run: pip install rapidfuzz"
            )
            return "licensed" if normalised in names else "not_licensed"

        match = process.extractOne(
            normalised,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.fuzzy_threshold,
        )
        return "licensed" if match else "not_licensed"

    def _load_names(self) -> set[str]:
        if self._names is not None:
            return self._names

        if self._cache_is_fresh():
            self._names = self._read_cache()
        else:
            self._names = self._fetch_and_cache()

        return self._names

    def _cache_is_fresh(self) -> bool:
        if not self.cache_path.exists():
            return False
        meta = Path(str(self.cache_path).replace(".csv", "_date.txt"))
        if not meta.exists():
            return False
        try:
            cached_date = datetime.fromisoformat(meta.read_text().strip()).date()
            return cached_date >= date.today()
        except (ValueError, OSError):
            return False

    def _read_cache(self) -> set[str]:
        names: set[str] = set()
        try:
            with self.cache_path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("Organisation Name") or "").strip().lower()
                    if name:
                        names.add(name)
        except OSError as e:
            logger.error("Failed to read sponsor register cache: %s", e)
        return names

    def _fetch_and_cache(self) -> set[str]:
        """Download today's register CSV and cache it locally."""
        import urllib.request

        logger.info("Fetching sponsor register from GOV.UK...")
        names: set[str] = set()

        try:
            with urllib.request.urlopen(LATEST_CSV_URL, timeout=30) as response:
                raw = response.read().decode("utf-8-sig")

            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(raw, encoding="utf-8")

            meta = Path(str(self.cache_path).replace(".csv", "_date.txt"))
            meta.write_text(datetime.utcnow().isoformat())

            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                name = (row.get("Organisation Name") or "").strip().lower()
                if name:
                    names.add(name)

            logger.info("Sponsor register loaded: %d organisations", len(names))

        except Exception as e:
            logger.error("Failed to fetch sponsor register: %s", e)
            # Fall back to stale cache if available
            if self.cache_path.exists():
                logger.warning("Using stale sponsor register cache.")
                names = self._read_cache()

        return names

    def refresh(self) -> int:
        """Force a fresh download of the register. Returns count of organisations."""
        self._names = None
        if self.cache_path.exists():
            self.cache_path.unlink()
        names = self._fetch_and_cache()
        self._names = names
        return len(names)
