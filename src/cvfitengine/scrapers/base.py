"""
Base scraper class for Playwright-based job scrapers.
Manages browser lifecycle, persistent context, rate limiting, and stealth.
"""
from __future__ import annotations

import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncGenerator

BROWSER_CONTEXT_DIR = Path.home() / ".cvfit" / "browser_context"
RATE_LIMIT = 3  # max concurrent pages


class BaseScraper(ABC):
    """Abstract base for all job scrapers.

    Subclasses implement _scrape_page() to yield raw job dicts.
    This base handles browser setup, stealth, rate limiting, and delays.
    """

    def __init__(
        self,
        query: str,
        location: str,
        max_results: int = 20,
        headless: bool = True,
    ) -> None:
        self.query = query
        self.location = location
        self.max_results = max_results
        self.headless = headless
        self._semaphore = asyncio.Semaphore(RATE_LIMIT)
        self._browser = None
        self._context = None

    # ── browser lifecycle ──────────────────────────────────────
    async def _launch(self) -> None:
        from playwright.async_api import async_playwright

        BROWSER_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()

        context_path = str(BROWSER_CONTEXT_DIR / self._context_subdir())
        Path(context_path).mkdir(parents=True, exist_ok=True)

        try:
            from playwright_stealth import Stealth
            self._stealth = Stealth()
        except ImportError:
            self._stealth = None

        self._browser = await self._pw.chromium.launch_persistent_context(
            user_data_dir=context_path,
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self._context = self._browser

    async def _close(self) -> None:
        if self._context:
            await self._context.close()
        if hasattr(self, "_pw"):
            await self._pw.stop()

    async def _new_page(self):
        page = await self._context.new_page()
        if self._stealth:
            await self._stealth.apply_stealth_async(page)
        return page

    # ── delays ─────────────────────────────────────────────────
    async def _human_delay(self, lo: float = 1.0, hi: float = 3.0) -> None:
        await asyncio.sleep(random.uniform(lo, hi))

    # ── entry point ────────────────────────────────────────────
    async def scrape(self) -> list[dict]:
        await self._launch()
        results = []
        try:
            async for job in self._scrape_pages():
                results.append(job)
                if len(results) >= self.max_results:
                    break
        finally:
            await self._close()
        return results[:self.max_results]

    # ── helpers ────────────────────────────────────────────────
    @staticmethod
    def _make_id(title: str, company: str) -> str:
        return hashlib.md5(
            f"{title.lower().strip()}{company.lower().strip()}".encode()
        ).hexdigest()

    # ── abstract interface ─────────────────────────────────────
    @abstractmethod
    def _context_subdir(self) -> str:
        """Return subdirectory name under browser_context/ for this scraper."""

    @abstractmethod
    async def _scrape_pages(self) -> AsyncGenerator[dict, None]:
        """Yield normalised job dicts up to max_results."""
