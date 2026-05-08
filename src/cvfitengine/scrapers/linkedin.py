"""
LinkedIn scraper — requires login.

First run: opens browser visible (headless=False), waits for user login,
then saves context cookies. Subsequent runs use saved context.

Always runs headless=False — LinkedIn aggressively fingerprints headless mode.

Usage:
    python -m cvfitengine.scrapers.linkedin --query 'python developer' --location 'London' --max 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import urllib.parse
from typing import AsyncGenerator

from .base import BaseScraper, BROWSER_CONTEXT_DIR


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job listings. Always headless=False."""

    BASE_URL = "https://www.linkedin.com/jobs/search/"
    LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(
        self,
        query: str,
        location: str,
        max_results: int = 20,
        easy_apply_only: bool = False,
        days_old: int = 7,
    ) -> None:
        # LinkedIn must always run visible (headless=False)
        super().__init__(query=query, location=location, max_results=max_results, headless=False, days_old=days_old)
        self.easy_apply_only = easy_apply_only

    def _context_subdir(self) -> str:
        return "linkedin"

    # Common location aliases → LinkedIn location name + geoId
    _LOCATION_MAP = {
        "uk": ("United Kingdom", "101165590"),
        "united kingdom": ("United Kingdom", "101165590"),
        "london": ("London, England, United Kingdom", "90009496"),
        "manchester": ("Manchester, England, United Kingdom", "103480482"),
        "liverpool": ("Liverpool, England, United Kingdom", "104621653"),
        "edinburgh": ("Edinburgh, Scotland, United Kingdom", "101474850"),
        "glasgow": ("Glasgow, Scotland, United Kingdom", "101396661"),
        "birmingham": ("Birmingham, England, United Kingdom", "102417530"),
        "bristol": ("Bristol, England, United Kingdom", "101620083"),
        "remote": ("United Kingdom", "101165590"),
    }

    def _resolve_location(self) -> tuple[str, str | None]:
        key = self.location.strip().lower()
        if key in self._LOCATION_MAP:
            return self._LOCATION_MAP[key]
        # Try prefix match (e.g. "Liverpool or Manchester" → liverpool)
        for alias, val in self._LOCATION_MAP.items():
            if key.startswith(alias) or alias in key:
                return val
        return (self.location, None)

    _TPR_MAP = {
        1: "r86400",
        7: "r604800",
        30: "r2592000",
    }

    def _build_url(self, start: int = 0) -> str:
        location_name, geo_id = self._resolve_location()
        params = {
            "keywords": self.query,
            "location": location_name,
            "start": start,
        }
        if geo_id:
            params["geoId"] = geo_id
        if self.easy_apply_only:
            params["f_LF"] = "f_AL"
        if self.days_old > 0:
            tpr = self._TPR_MAP.get(self.days_old)
            if not tpr:
                tpr = "r604800" if self.days_old <= 7 else "r2592000"
            params["f_TPR"] = tpr
        return self.BASE_URL + "?" + urllib.parse.urlencode(params)

    async def _ensure_logged_in(self, page) -> bool:
        """Check if logged in; if not, open login page and wait for user to log in.

        Detects login completion automatically by polling the URL — no terminal
        interaction required.
        """
        await page.goto("https://www.linkedin.com/feed/", timeout=30000)
        await self._human_delay(1.0, 2.0)

        if "login" not in page.url and "signup" not in page.url and "authwall" not in page.url:
            return True

        print("[LinkedIn] Not logged in — opening login page in the Chromium window.")
        print("[LinkedIn] Please log in manually. The scraper will continue automatically once detected.")
        await page.goto(self.LOGIN_URL, timeout=30000)

        # Poll until we reach the feed (max 3 min)
        for _ in range(180):
            await asyncio.sleep(1)
            url = page.url
            if "/feed" in url or "/jobs" in url or "/mynetwork" in url:
                print("[LinkedIn] Login detected — continuing scrape.")
                return True

        raise RuntimeError(
            "LinkedIn login timed out after 3 minutes. "
            "Please log in within the Chromium window that opened."
        )


    async def _random_mouse_move(self, page) -> None:
        """Add random mouse movement to appear human."""
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 1180)
            y = random.randint(100, 700)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def _scrape_pages(self) -> AsyncGenerator[dict, None]:
        page = await self._new_page()
        collected = 0
        start = 0
        per_page = 25

        try:
            await self._ensure_logged_in(page)

            while collected < self.max_results:
                url = self._build_url(start)
                print(f"[LinkedIn] Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(2.0, 4.0)
                await self._random_mouse_move(page)

                # Wait for job list
                try:
                    await page.wait_for_selector(
                        ".jobs-search__results-list, .scaffold-layout__list",
                        timeout=15000,
                    )
                except Exception:
                    break

                job_cards = await page.query_selector_all(
                    ".jobs-search__results-list > li, "
                    ".scaffold-layout__list-item"
                )

                if not job_cards:
                    # Give LinkedIn extra time to render — it can be slow
                    await self._human_delay(2.0, 3.0)
                    job_cards = await page.query_selector_all(
                        ".jobs-search__results-list > li, "
                        ".scaffold-layout__list-item"
                    )
                if not job_cards:
                    print(f"[LinkedIn] No job cards found at URL: {page.url}")
                    # Screenshot for debugging
                    from pathlib import Path
                    ss = Path.home() / ".cvfit" / "screenshots" / "li_debug.png"
                    ss.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(ss), full_page=True)
                    print(f"[LinkedIn] Screenshot saved to {ss}")
                    break

                print(f"[LinkedIn] Found {len(job_cards)} cards on page start={start}")

                for card in job_cards:
                    if collected >= self.max_results:
                        break

                    job = await self._extract_card(page, card)
                    if job:
                        yield job
                        collected += 1
                    await self._human_delay(0.5, 1.5)
                    await self._random_mouse_move(page)

                # Next page
                start += per_page
                await self._human_delay(2.0, 4.0)

        finally:
            await page.close()

    async def _extract_card(self, list_page, card) -> dict | None:
        """Click card, load detail page, extract full JD."""
        try:
            # Click to load details
            link_el = await card.query_selector(
                "a.job-card-list__title--link, "
                "a.job-card-container__link, "
                "a.base-card__full-link"
            )
            if not link_el:
                return None

            title = (await link_el.inner_text()).strip().split("\n")[0].strip()
            job_url = await link_el.get_attribute("href") or ""
            if job_url and not job_url.startswith("http"):
                job_url = "https://www.linkedin.com" + job_url

            company_el = await card.query_selector(
                ".job-card-container__primary-description, "
                ".base-search-card__subtitle"
            )
            company = (await company_el.inner_text()).strip() if company_el else ""

            location_el = await card.query_selector(
                ".job-card-container__metadata-item, "
                ".job-search-card__location"
            )
            location = (await location_el.inner_text()).strip() if location_el else ""

            # Check for easy apply badge
            easy_apply = False
            ea_el = await card.query_selector(".job-card-container__apply-method")
            if ea_el:
                ea_text = (await ea_el.inner_text()).lower()
                easy_apply = "easy apply" in ea_text

            if not title:
                return None

            # Navigate to job detail for full description
            description = ""
            posted = ""
            salary = ""
            apply_url = job_url

            try:
                await link_el.click()
                await self._human_delay(1.5, 3.0)

                # Wait for the detail pane — LinkedIn uses several class names
                try:
                    await list_page.wait_for_selector(
                        ".jobs-description, .jobs-description__content, "
                        ".job-details-jobs-unified-top-card__job-title, "
                        ".jobs-unified-top-card__job-title",
                        timeout=10000,
                    )
                except Exception:
                    pass

                # Try clicking "See more" if present to expand full description
                see_more = await list_page.query_selector(
                    "button.jobs-description__footer-button, "
                    "button[aria-label*='more'], "
                    ".jobs-description__see-more-button"
                )
                if see_more:
                    try:
                        await see_more.click()
                        await self._human_delay(0.5, 1.0)
                    except Exception:
                        pass

                # Description — try each selector in priority order
                for sel in [
                    ".jobs-description__content .show-more-less-html__markup",
                    ".show-more-less-html__markup",
                    ".jobs-description-content__text",
                    ".jobs-description__container",
                    ".jobs-description",
                    "[class*='description__text']",
                    "[class*='jobs-description']",
                ]:
                    desc_el = await list_page.query_selector(sel)
                    if desc_el:
                        description = (await desc_el.inner_text()).strip()
                        if description:
                            break

                # Posted date — try both old and new card layouts
                for sel in [
                    ".jobs-unified-top-card__posted-date",
                    ".job-details-jobs-unified-top-card__primary-description-without-tagline span",
                    "[class*='posted-date']",
                    ".tvm__text--neutral",
                    "span[aria-label*='ago']",
                ]:
                    posted_el = await list_page.query_selector(sel)
                    if posted_el:
                        t = (await posted_el.inner_text()).strip()
                        if any(w in t.lower() for w in ["ago", "day", "week", "hour", "month"]):
                            posted = t
                            break

                # Salary
                for sel in [
                    ".jobs-unified-top-card__job-insight span",
                    "[class*='salary']",
                    "[class*='compensation']",
                ]:
                    salary_el = await list_page.query_selector(sel)
                    if salary_el:
                        salary_text = (await salary_el.inner_text()).strip()
                        if any(c in salary_text for c in ["£", "$", "€", "k", "K"]):
                            salary = salary_text
                            break

                # Easy Apply
                ea_btn = await list_page.query_selector(
                    ".jobs-apply-button--top-card, "
                    "button[aria-label*='Easy Apply']"
                )
                if ea_btn:
                    easy_apply = True

            except Exception:
                pass

            return {
                "id": self._make_id(title, company),
                "title": title,
                "company": company,
                "location": location,
                "salary_raw": salary,
                "salary": salary,
                "employment_type": "Full-time",
                "type": "Full-time",
                "description_full": description,
                "summary": description[:280],
                "url": job_url,
                "apply_url": apply_url,
                "source": "linkedin",
                "easy_apply": easy_apply,
                "posted_date": posted,
                "posted": posted,
            }
        except Exception:
            return None


# ── CLI entry point ─────────────────────────────────────────────────
async def _main(query: str, location: str, max_results: int, easy_apply_only: bool) -> None:
    scraper = LinkedInScraper(
        query=query,
        location=location,
        max_results=max_results,
        easy_apply_only=easy_apply_only,
    )
    jobs = await scraper.scrape()
    print(json.dumps(jobs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn job scraper")
    parser.add_argument("--query", required=True)
    parser.add_argument("--location", default="UK")
    parser.add_argument("--max", type=int, default=5, dest="max_results")
    parser.add_argument("--easy-apply-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.query, args.location, args.max_results, args.easy_apply_only))
