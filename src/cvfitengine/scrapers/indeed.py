"""
Indeed scraper — no login required.
Constructs search URL, paginates, extracts full job descriptions.

Usage:
    python -m cvfitengine.scrapers.indeed --query 'python developer' --location 'London' --max 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import urllib.parse
from typing import AsyncGenerator

from .base import BaseScraper


class IndeedScraper(BaseScraper):
    """Scraper for indeed.co.uk job listings."""

    BASE_URL = "https://uk.indeed.com/jobs"

    def __init__(
        self,
        query: str,
        location: str,
        max_results: int = 20,
    ) -> None:
        super().__init__(query=query, location=location, max_results=max_results, headless=True)

    def _context_subdir(self) -> str:
        return "indeed"

    def _build_url(self, start: int = 0) -> str:
        params = urllib.parse.urlencode({
            "q": self.query,
            "l": self.location,
            "start": start,
        })
        return f"{self.BASE_URL}?{params}"

    async def _scrape_pages(self) -> AsyncGenerator[dict, None]:
        page = await self._new_page()
        collected = 0
        start = 0
        per_page = 15  # Indeed shows ~15 results per page

        try:
            while collected < self.max_results:
                url = self._build_url(start)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(1.5, 3.0)

                # Accept cookies if prompted
                try:
                    await page.click('[id="onetrust-accept-btn-handler"]', timeout=3000)
                    await self._human_delay(0.5, 1.0)
                except Exception:
                    pass

                # Wait for job cards
                try:
                    await page.wait_for_selector('[data-testid="jobsearch-ResultsList"]', timeout=15000)
                except Exception:
                    break

                job_cards = await page.query_selector_all('[data-testid="slider_item"]')
                if not job_cards:
                    # Try alternate selector
                    job_cards = await page.query_selector_all(".job_seen_beacon")

                if not job_cards:
                    break

                for card in job_cards:
                    if collected >= self.max_results:
                        break

                    job = await self._extract_card(page, card)
                    if job:
                        yield job
                        collected += 1
                    await self._human_delay(0.3, 0.8)

                # Check for next page
                next_btn = await page.query_selector('[data-testid="pagination-page-next"]')
                if not next_btn:
                    break
                start += per_page
                await self._human_delay(1.0, 2.5)

        finally:
            await page.close()

    async def _extract_card(self, list_page, card) -> dict | None:
        """Click into a job card and extract full details."""
        try:
            # Extract basic info from card
            title_el = await card.query_selector('[data-testid="jobTitle"]')
            if not title_el:
                title_el = await card.query_selector(".jobTitle")
            title = (await title_el.inner_text()).strip() if title_el else ""

            company_el = await card.query_selector('[data-testid="company-name"]')
            if not company_el:
                company_el = await card.query_selector(".companyName")
            company = (await company_el.inner_text()).strip() if company_el else ""

            location_el = await card.query_selector('[data-testid="text-location"]')
            if not location_el:
                location_el = await card.query_selector(".companyLocation")
            location = (await location_el.inner_text()).strip() if location_el else ""

            salary_el = await card.query_selector('[data-testid="attribute_snippet_testid"]')
            salary = (await salary_el.inner_text()).strip() if salary_el else ""

            posted_el = await card.query_selector('[data-testid="myJobsStateDate"]')
            if not posted_el:
                posted_el = await card.query_selector(".date")
            posted = (await posted_el.inner_text()).strip() if posted_el else ""

            # Get job URL from title link
            link_el = await card.query_selector('[data-testid="jobTitle"] a, .jobTitle a')
            job_url = ""
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        job_url = "https://uk.indeed.com" + href
                    else:
                        job_url = href

            if not title or not company:
                return None

            # Click the card to load full description in side panel
            await card.click()
            await self._human_delay(0.8, 1.5)

            # Wait for description panel
            description = ""
            try:
                await list_page.wait_for_selector(
                    '[data-testid="jobsearch-JobInfoHeader-title"],'
                    '[id="jobDescriptionText"]',
                    timeout=8000,
                )
                desc_el = await list_page.query_selector('[id="jobDescriptionText"]')
                if not desc_el:
                    desc_el = await list_page.query_selector(".jobsearch-jobDescriptionText")
                if desc_el:
                    description = (await desc_el.inner_text()).strip()
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
                "apply_url": job_url,
                "source": "indeed",
                "easy_apply": False,
                "posted_date": posted,
                "posted": posted,
            }
        except Exception:
            return None


# ── CLI entry point ────────────────────────────────────────────────
async def _main(query: str, location: str, max_results: int) -> None:
    scraper = IndeedScraper(query=query, location=location, max_results=max_results)
    jobs = await scraper.scrape()
    print(json.dumps(jobs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indeed job scraper")
    parser.add_argument("--query", required=True)
    parser.add_argument("--location", default="UK")
    parser.add_argument("--max", type=int, default=5, dest="max_results")
    args = parser.parse_args()
    asyncio.run(_main(args.query, args.location, args.max_results))
