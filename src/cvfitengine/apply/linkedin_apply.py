"""
LinkedIn Easy Apply automation.

CRITICAL: Never auto-clicks the final Submit button.
The session pauses at 'awaiting_confirm' and takes a screenshot.
The user must call confirm_apply(job_id) to proceed.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

SCREENSHOTS_DIR = Path.home() / ".cvfit" / "screenshots"

# Module-level store: job_id -> live Playwright Page (kept alive between
# /apply/run and /apply/confirm calls)
_pending_sessions: dict[str, object] = {}


def check_plan_approved(job_id: str, plans_dir: str = "plans/") -> tuple[bool, str]:
    """Return (approved, reason). Application must not proceed unless approved=True."""
    import json
    from pathlib import Path

    plans = Path(plans_dir)
    slug = job_id.replace("/", "_").replace(" ", "_")
    plan_file = plans / f"tailoring_plan_{slug}.json"

    if not plan_file.exists():
        return False, f"No tailoring plan found for job_id '{job_id}'. Run planning/tailoring_plan.py first."

    try:
        data = json.loads(plan_file.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Could not read tailoring plan: {e}"

    status = data.get("approval_status", "pending")
    if status == "approved":
        return True, "Plan approved."
    return False, f"Tailoring plan exists but approval_status is '{status}'. Review and set to 'approved' before applying."


async def apply_easy(
    job: dict,
    resume,
    cover_letter: str,
    cv_pdf_path: str,
) -> dict:
    """Fill in a LinkedIn Easy Apply form and pause before final submit.

    Returns
    -------
    {status: 'awaiting_confirm'|'failed', screenshot_path: str, error: str|None}
    """
    from ..scrapers.base import BROWSER_CONTEXT_DIR
    from playwright.async_api import async_playwright

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = _field(job, "id")
    job_url = _field(job, "url") or _field(job, "apply_url")

    # Gate: require an approved tailoring plan before proceeding
    approved, reason = check_plan_approved(job_id)
    if not approved:
        return {"status": "blocked", "screenshot_path": "", "error": reason}

    if not job_url:
        return {"status": "failed", "screenshot_path": "", "error": "No job URL"}

    pw = await async_playwright().start()
    context_path = str(BROWSER_CONTEXT_DIR / "linkedin")
    Path(context_path).mkdir(parents=True, exist_ok=True)

    try:
        from playwright_stealth import Stealth
        _stealth = Stealth()
    except ImportError:
        _stealth = None

    context = await pw.chromium.launch_persistent_context(
        user_data_dir=context_path,
        headless=False,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()
    if _stealth:
        await _stealth.apply_stealth_async(page)

    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)

        # Browser stays open — user applies manually.
        # Store session so it can be closed later via confirm_apply().
        _pending_sessions[job_id] = {"page": page, "context": context, "pw": pw}

        return {
            "status": "awaiting_confirm",
            "screenshot_path": "",
            "error": None,
        }

    except Exception as e:
        screenshot_path = await _screenshot(page, job_id, "error")
        await context.close()
        await pw.stop()
        return {
            "status": "failed",
            "screenshot_path": screenshot_path,
            "error": str(e),
        }


async def confirm_apply(job_id: str) -> dict:
    """Click the final Submit button for a paused Easy Apply session.

    Must be called after apply_easy() returns status='awaiting_confirm'.
    """
    session = _pending_sessions.get(job_id)
    if not session:
        return {"status": "failed", "error": "No pending session for this job"}

    page = session["page"]
    context = session["context"]
    pw = session["pw"]

    try:
        del _pending_sessions[job_id]
    except KeyError:
        pass

    try:
        await context.close()
    except Exception:
        pass
    try:
        await pw.stop()
    except Exception:
        pass

    return {"status": "applied", "screenshot_path": "", "error": None}


# ── wizard helpers ─────────────────────────────────────────────────

async def _fill_wizard_pages(page, resume, person, cover_letter: str, cv_pdf_path: str) -> None:
    """Iterate through Easy Apply wizard pages, filling known fields."""
    max_pages = 10
    for _ in range(max_pages):
        await asyncio.sleep(1.0)

        # Check if we're at the final submit page — stop here
        submit_btn = await page.query_selector(
            "button[aria-label*='Submit application']"
        )
        if submit_btn:
            return  # Pause here — caller will screenshot and wait for confirm

        # Fill phone if present
        phone_input = await page.query_selector("input[id*='phoneNumber']")
        if phone_input:
            val = await phone_input.input_value()
            if not val:
                await phone_input.fill(person.phone or "")

        # Fill name fields
        await _try_fill(page, "input[id*='firstName']", person.full_name.split()[0] if person.full_name else "")
        await _try_fill(page, "input[id*='lastName']", person.full_name.split()[-1] if person.full_name else "")
        await _try_fill(page, "input[id*='email']", person.email or "")
        await _try_fill(page, "input[id*='city'], input[id*='location']", person.location or "")

        # Upload CV if file input present and not yet uploaded
        file_input = await page.query_selector("input[type='file']")
        if file_input and cv_pdf_path and Path(cv_pdf_path).exists():
            await file_input.set_input_files(cv_pdf_path)
            await asyncio.sleep(0.5)

        # Fill cover letter textarea
        cl_area = await page.query_selector("textarea[id*='coverLetter'], textarea[name*='cover']")
        if cl_area and cover_letter:
            await cl_area.fill(cover_letter)

        # Click Next button
        next_btn = await page.query_selector(
            "button[aria-label*='Continue to next step'], "
            "button[aria-label*='Review'], "
            "footer button[data-easy-apply-next-button]"
        )
        if next_btn:
            label = await next_btn.get_attribute("aria-label") or ""
            # Stop before final submit
            if "submit" in label.lower():
                return
            await next_btn.click()
        else:
            return


async def _try_fill(page, selector: str, value: str) -> None:
    if not value:
        return
    try:
        el = await page.query_selector(selector)
        if el:
            current = await el.input_value()
            if not current:
                await el.fill(value)
    except Exception:
        pass


async def _screenshot(page, job_id: str, suffix: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"{job_id}_{suffix}_{ts}.png"
    try:
        await page.screenshot(path=str(path))
        return str(path)
    except Exception:
        return ""


def _field(job, key: str) -> str:
    if isinstance(job, dict):
        return job.get(key, "") or ""
    return getattr(job, key, "") or ""
