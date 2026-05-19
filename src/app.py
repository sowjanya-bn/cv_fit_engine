"""
CV Fit Studio — FastAPI backend
Run: python run.py  →  http://localhost:8000
"""

from __future__ import annotations

import os
import base64
import hashlib
import asyncio
import tempfile
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import Optional

import httpx
import yaml
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel

app = FastAPI(title="CV Fit Studio")

PUBLIC = Path(__file__).parent.parent / "public"
app.mount("/static", StaticFiles(directory=str(PUBLIC)), name="static")


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


# ── env helper ─────────────────────────────────────────────────
def env(key: str, required: bool = False) -> str:
    val = os.environ.get(key, "")
    if required and not val:
        raise HTTPException(status_code=500, detail=f"{key} not set in .env")
    return val


# ══════════════════════════════════════════════════════════════
# Claude proxy
# ══════════════════════════════════════════════════════════════
class ClaudeRequest(BaseModel):
    system: str
    user: str
    max_tokens: int = 4096


class ClaudeResponse(BaseModel):
    text: str


@app.post("/api/claude", response_model=ClaudeResponse)
async def call_claude(req: ClaudeRequest):
    api_key = env("ANTHROPIC_API_KEY", required=True)
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": req.max_tokens,
        "system": req.system,
        "messages": [{"role": "user", "content": req.user}],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Anthropic API error: {resp.text}",
        )
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return ClaudeResponse(text=text)


# ══════════════════════════════════════════════════════════════
# Job search — Reed + Adzuna in parallel
# ══════════════════════════════════════════════════════════════
class JobSearchRequest(BaseModel):
    keywords: str
    location: str = "UK"
    results_per_source: int = 10
    days_old: int = 7  # 0 = any time


def _dedup(jobs: list) -> list:
    """Deduplicate jobs by title+company MD5.

    Accepts list[dict] (legacy) or list[dict] from scrapers.
    For scraped jobs, also checks SQLite cache to skip already-stored listings
    and persists new ones.
    """
    if not jobs:
        return jobs

    # Check if these are scraper jobs (have 'description_full' key) → use cache
    first = jobs[0] if jobs else {}
    use_cache = isinstance(first, dict) and "description_full" in first

    seen: set[str] = set()
    out = []

    if use_cache:
        from cvfitengine.scrapers.cache import JobCache
        cache = JobCache()

    for j in jobs:
        key = hashlib.md5(
            f"{j.get('title','').lower().strip()}{j.get('company','').lower().strip()}".encode()
        ).hexdigest()
        if key in seen:
            continue
        seen.add(key)

        if use_cache:
            job_id = j.get("id", key)
            if cache.exists_fresh(job_id):
                # Already cached and fresh — still include it (from cache)
                cached = cache.get(job_id)
                if cached:
                    out.append(cached)
                continue
            # New job — persist to cache then include
            j["id"] = job_id
            cache.save(j)

        out.append(j)
    return out


def _fmt_salary(lo, hi) -> str:
    if lo and hi:
        return f"£{int(lo):,}–£{int(hi):,}"
    if lo:
        return f"£{int(lo):,}+"
    if hi:
        return f"up to £{int(hi):,}"
    return ""


async def _search_reed(keywords: str, location: str, n: int, days_old: int = 7) -> list[dict]:
    key = env("REED_API_KEY")
    if not key:
        return []
    token = base64.b64encode(f"{key}:".encode()).decode()
    params = {
        "keywords": keywords,
        "locationName": location,
        "resultsToTake": min(n, 100),
    }
    if days_old > 0:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%S")
        params["postedByMeOnly"] = "false"
        params["graduateJob"] = "false"
        # Reed uses minimumDate param
        params["minimumDate"] = since
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://www.reed.co.uk/api/1.0/search",
                params=params,
                headers={"Authorization": f"Basic {token}"},
            )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("results", []):
            jobs.append({
                "id": f"reed_{j.get('jobId', '')}",
                "title": j.get("jobTitle", ""),
                "company": j.get("employerName", ""),
                "location": j.get("locationName", ""),
                "salary": _fmt_salary(j.get("minimumSalary"), j.get("maximumSalary")),
                "type": "Full-time",
                "summary": (j.get("jobDescription", "") or "")[:280].strip(),
                "url": j.get("jobUrl", ""),
                "source": "Reed",
                "posted": (j.get("date", "") or "")[:10],
            })
        return jobs
    except Exception:
        return []


async def _search_adzuna(keywords: str, location: str, n: int, days_old: int = 7) -> list[dict]:
    app_id = env("ADZUNA_APP_ID")
    app_key = env("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    where = location if location.lower() not in ("uk", "united kingdom", "anywhere uk") else "london"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(n, 50),
        "what": keywords,
        "where": where,
        "content-type": "application/json",
        "sort_by": "date",
    }
    if days_old > 0:
        params["max_days_old"] = days_old
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.adzuna.com/v1/api/jobs/gb/search/1",
                params=params,
            )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("results", []):
            lo = j.get("salary_min")
            hi = j.get("salary_max")
            jobs.append({
                "id": f"adzuna_{j.get('id', '')}",
                "title": j.get("title", ""),
                "company": j.get("company", {}).get("display_name", ""),
                "location": j.get("location", {}).get("display_name", ""),
                "salary": _fmt_salary(lo, hi),
                "type": "Full-time",
                "summary": (j.get("description", "") or "")[:280].strip(),
                "url": j.get("redirect_url", ""),
                "source": "Adzuna",
                "posted": (j.get("created", "") or "")[:10],
            })
        return jobs
    except Exception:
        return []


@app.post("/api/jobs/search")
async def search_jobs(req: JobSearchRequest):
    reed_task = _search_reed(req.keywords, req.location, req.results_per_source, req.days_old)
    adzuna_task = _search_adzuna(req.keywords, req.location, req.results_per_source, req.days_old)
    reed_results, adzuna_results = await asyncio.gather(reed_task, adzuna_task)
    combined = _dedup(reed_results + adzuna_results)
    return {
        "jobs": combined,
        "counts": {
            "reed": len(reed_results),
            "adzuna": len(adzuna_results),
            "total": len(combined),
        },
    }


# ══════════════════════════════════════════════════════════════
# PDF — compile LaTeX via pdflatex
# ══════════════════════════════════════════════════════════════
class PDFRequest(BaseModel):
    latex: str
    filename: str = "cv_tailored"


@app.post("/api/pdf")
async def generate_pdf(req: PDFRequest):
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "cv.tex"
        tex_path.write_text(req.latex, encoding="utf-8")
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory", tmpdir,
            str(tex_path),
        ]
        result = None
        for _ in range(2):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        pdf_path = Path(tmpdir) / "cv.pdf"
        if not pdf_path.exists():
            log = (result.stdout or "")[-2000:]
            raise HTTPException(
                status_code=500,
                detail=f"pdflatex failed.\n{log}",
            )
        pdf_bytes = pdf_path.read_bytes()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{req.filename}.pdf"'},
    )


# ══════════════════════════════════════════════════════════════
# Scraper endpoints — Phase 1
# ══════════════════════════════════════════════════════════════
class ScraperRequest(BaseModel):
    source: str  # 'linkedin' | 'indeed' | 'both'
    query: str
    location: str = "UK"
    max_results: int = 20
    days_old: int = 7  # 0 = any time


# In-memory job tracker: job_id -> {status, progress, results, error}
_scrape_jobs: dict[str, dict] = {}


async def _run_scrape(job_id: str, req: ScraperRequest) -> None:
    _scrape_jobs[job_id]["status"] = "running"
    try:
        results: list[dict] = []

        if req.source in ("indeed", "both"):
            from cvfitengine.scrapers.indeed import IndeedScraper
            scraper = IndeedScraper(req.query, req.location, req.max_results, days_old=req.days_old)
            indeed_jobs = await scraper.scrape()
            results.extend(indeed_jobs)
            _scrape_jobs[job_id]["progress"] = len(results)

        if req.source in ("linkedin", "both"):
            from cvfitengine.scrapers.linkedin import LinkedInScraper
            scraper = LinkedInScraper(req.query, req.location, req.max_results, days_old=req.days_old)
            li_jobs = await scraper.scrape()
            results.extend(li_jobs)
            _scrape_jobs[job_id]["progress"] = len(results)

        deduped = _dedup(results)
        _scrape_jobs[job_id]["status"] = "complete"
        _scrape_jobs[job_id]["results"] = deduped
        _scrape_jobs[job_id]["total"] = len(deduped)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n[scrape:{job_id}] FAILED\n{tb}")
        _scrape_jobs[job_id]["status"] = "failed"
        _scrape_jobs[job_id]["error"] = str(e)
        _scrape_jobs[job_id]["traceback"] = tb


@app.post("/api/jobs/scrape")
async def scrape_jobs(req: ScraperRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _scrape_jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": req.max_results,
        "results": [],
        "error": None,
    }
    background_tasks.add_task(_run_scrape, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/scrape/{job_id}/status")
async def scrape_status(job_id: str):
    info = _scrape_jobs.get(job_id)
    if not info:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return {
        "job_id": job_id,
        "status": info["status"],
        "progress": info.get("progress", 0),
        "total": info.get("total", 0),
        "result_count": len(info.get("results", [])),
        "error": info.get("error"),
        "traceback": info.get("traceback"),
    }


@app.get("/api/jobs/scrape/{job_id}/results")
async def scrape_results(job_id: str):
    info = _scrape_jobs.get(job_id)
    if not info:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return {"jobs": info.get("results", []), "status": info["status"]}


# ══════════════════════════════════════════════════════════════
# JD trigger — Phase 2
# ══════════════════════════════════════════════════════════════
class JDTriggerRequest(BaseModel):
    jd_text: str
    location: str = "UK"
    source: str = "both"
    days_old: int = 7
    max_results: int = 20


class JDTriggerResponse(BaseModel):
    scrape_job_id: str
    extracted_title: str
    extracted_keywords: list[str]


@app.post("/api/jd/trigger", response_model=JDTriggerResponse)
async def jd_trigger(req: JDTriggerRequest, background_tasks: BackgroundTasks):
    """Parse a raw JD with Claude, extract role+keywords, kick off a scrape."""
    from cvfitengine.parsing.jd_parser import parse_job

    job_spec = parse_job(req.jd_text)
    query = job_spec.title or "software engineer"
    keywords = (job_spec.keywords or [])[:10]

    scrape_req = ScraperRequest(
        source=req.source,
        query=query,
        location=req.location,
        max_results=req.max_results,
        days_old=req.days_old,
    )
    job_id = str(uuid.uuid4())
    _scrape_jobs[job_id] = {"status": "queued", "progress": 0, "total": 0, "results": [], "error": None}
    background_tasks.add_task(_run_scrape, job_id, scrape_req)

    return JDTriggerResponse(
        scrape_job_id=job_id,
        extracted_title=query,
        extracted_keywords=keywords,
    )


# ══════════════════════════════════════════════════════════════
# Batch scoring — Phase 3
# ══════════════════════════════════════════════════════════════
class BatchScoreRequest(BaseModel):
    job_ids: list[str]
    resume_yaml: str  # YAML string of the resume form


class BatchScoreResult(BaseModel):
    job_id: str
    fit_score: float
    matched_skills: list[str]
    matched_tools: list[str]
    missing_skills: list[str]
    missing_tools: list[str]
    coverage_pct: float
    jd_category: str = ""
    seniority_level: str = ""


def _load_resume_from_yaml(resume_yaml: str):
    from cvfitengine.core.types import ResumeForm
    data = yaml.safe_load(resume_yaml)
    return ResumeForm(**data)


def _score_one(job: dict, resume) -> dict:
    from cvfitengine.scoring.score import score_job
    from cvfitengine.scoring.gaps import compute_gaps

    score_result = score_job(job, resume)
    gap_result = compute_gaps(job, resume)
    return {
        "job_id": job.get("id", ""),
        "fit_score": score_result["fit_score"],
        "matched_skills": score_result["matched_skills"],
        "matched_tools": score_result["matched_tools"],
        "missing_skills": gap_result["missing_skills"],
        "missing_tools": gap_result["missing_tools"],
        "coverage_pct": gap_result["coverage_pct"],
        "jd_category": score_result["jd_category"],
        "seniority_level": score_result["seniority_level"],
    }


@app.post("/api/jobs/score")
async def score_jobs_batch(req: BatchScoreRequest):
    from cvfitengine.scrapers.cache import JobCache

    try:
        resume = _load_resume_from_yaml(req.resume_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid resume YAML: {e}")

    cache = JobCache()
    results = []

    async def _score_and_cache(job_id: str):
        job = cache.get(job_id)
        if not job:
            return {"job_id": job_id, "error": "Job not found in cache"}
        result = _score_one(job, resume)
        cache.update_score(
            job_id,
            result["fit_score"],
            result["missing_skills"] + result["missing_tools"],
        )
        return result

    tasks = [_score_and_cache(jid) for jid in req.job_ids]
    results = await asyncio.gather(*tasks)
    return {"results": list(results)}


@app.get("/api/jobs/ranked")
async def ranked_jobs(
    min_score: float = 0.0,
    limit: int = 50,
    source: Optional[str] = None,
):
    from cvfitengine.scrapers.cache import JobCache
    cache = JobCache()
    jobs = cache.list_ranked(min_score=min_score, limit=limit, source=source)
    return {"jobs": jobs, "total": len(jobs)}


# ══════════════════════════════════════════════════════════════
# Apply endpoints — Phase 4
# ══════════════════════════════════════════════════════════════
class CoverLetterRequest(BaseModel):
    job_id: str
    resume_yaml: str
    force_regenerate: bool = False


APPLICATIONS_DIR = Path.home() / ".cvfit" / "applications"


def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def _save_application_folder(job: dict, cover_letter: str, jd_text: str = "", cv_latex: str = "") -> None:
    import json as _json
    from datetime import datetime
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    company = _slugify(job.get("company", "unknown"))
    title = _slugify(job.get("title", "role"))
    folder = APPLICATIONS_DIR / f"{date_str}_{company}_{title}"
    folder.mkdir(parents=True, exist_ok=True)

    if jd_text:
        (folder / "job_description.txt").write_text(jd_text, encoding="utf-8")
    elif job.get("description_full"):
        (folder / "job_description.txt").write_text(job["description_full"], encoding="utf-8")

    if cover_letter:
        (folder / "cover_letter.txt").write_text(cover_letter, encoding="utf-8")

    if cv_latex:
        tex_path = folder / "cv_tailored.tex"
        tex_path.write_text(cv_latex, encoding="utf-8")
        try:
            from cvfitengine.rendering.pdf import compile_latex_to_pdf
            compile_latex_to_pdf(tex_path)
        except Exception:
            pass  # PDF compile is best-effort; .tex is always saved

    status_path = folder / "status.json"
    if not status_path.exists():
        status = {
            "job_id": job.get("id", ""),
            "company": job.get("company", ""),
            "job_title": job.get("title", ""),
            "source": job.get("source", ""),
            "apply_url": job.get("apply_url", job.get("url", "")),
            "stage": "queued",
            "stages_log": [{"stage": "queued", "at": datetime.utcnow().isoformat()}],
            "notes": "",
            "follow_up_due": None,
            "fit_score": job.get("fit_score", 0),
            "skill_gaps": job.get("missing_skills", []),
        }
        status_path.write_text(_json.dumps(status, indent=2), encoding="utf-8")


class QueueApplyRequest(BaseModel):
    job_id: str
    method: str = "easy_apply"
    cover_letter: str = ""
    jd_text: str = ""
    cv_latex: str = ""


class RunApplyRequest(BaseModel):
    cv_pdf_path: str = ""


@app.post("/api/apply/generate-cover-letter")
async def gen_cover_letter(req: CoverLetterRequest):
    from cvfitengine.scrapers.cache import JobCache
    from cvfitengine.apply.cover_letter import generate_cover_letter
    from cvfitengine.scoring.score import score_job

    cache = JobCache()
    job = cache.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in cache")

    try:
        resume = _load_resume_from_yaml(req.resume_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid resume YAML: {e}")

    score_result = _score_one(job, resume)
    letter = generate_cover_letter(
        job, resume, score_result, force_regenerate=req.force_regenerate
    )

    from cvfitengine.scoring.gaps import compute_gaps
    gaps = compute_gaps(job, resume)

    fit_score = score_result.get("fit_score", 0)
    return {
        "cover_letter": letter,
        "fit_score": round(fit_score * 100) if fit_score <= 1 else fit_score,
        "matched_skills": score_result.get("matched_skills", []),
        "matched_tools": score_result.get("matched_tools", []),
        "missing_skills": gaps.get("missing_skills", []),
        "missing_tools": gaps.get("missing_tools", []),
        "top_blocks": score_result.get("top_blocks", []),
        "jd_category": score_result.get("jd_category", ""),
        "seniority_level": score_result.get("seniority_level", ""),
    }


@app.post("/api/apply/queue")
async def queue_apply(req: QueueApplyRequest):
    from cvfitengine.scrapers.cache import JobCache
    from cvfitengine.apply.queue import ApplyQueue, ApplyError

    cache = JobCache()
    job = cache.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in cache")

    q = ApplyQueue()
    try:
        q.enqueue(req.job_id, job.get("title", ""), job.get("company", ""), req.method)
    except ApplyError as e:
        raise HTTPException(status_code=409, detail=str(e))

    cache.update_status(req.job_id, "queued")
    _save_application_folder(job, req.cover_letter, req.jd_text, req.cv_latex)
    return {"queued": True}


# Active apply tasks: job_id -> asyncio.Task
_apply_tasks: dict[str, asyncio.Task] = {}


@app.post("/api/apply/run/{job_id}")
async def run_apply(job_id: str, req: RunApplyRequest, background_tasks: BackgroundTasks):
    from cvfitengine.scrapers.cache import JobCache
    from cvfitengine.apply.queue import ApplyQueue
    from cvfitengine.apply.linkedin_apply import apply_easy

    cache = JobCache()
    job = cache.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in cache")

    q = ApplyQueue()
    entry = q.get(job_id)
    if not entry:
        raise HTTPException(status_code=400, detail="Job not in apply queue — call /api/apply/queue first")

    cached_cl = cache.get_cover_letter(job_id)

    async def _do_apply():
        # Minimal resume shell for apply_easy (just needs person fields)
        class _FakePerson:
            full_name = ""; email = ""; phone = ""; location = ""
        class _FakeResume:
            class profile:
                person = _FakePerson()

        result = await apply_easy(job, _FakeResume(), cached_cl or "", req.cv_pdf_path)
        if result["status"] == "awaiting_confirm":
            q.mark_awaiting_confirm(
                job_id,
                cover_letter=cached_cl or "",
                screenshot_path=result.get("screenshot_path", ""),
            )
        elif result["status"] == "failed":
            q.mark_failed(job_id, result.get("error", "unknown"))
            cache.update_status(job_id, "failed")
        return result

    task = asyncio.create_task(_do_apply())
    _apply_tasks[job_id] = task

    # Give it a moment to start
    await asyncio.sleep(0.1)
    return {"status": "running", "message": "Easy Apply session started"}


@app.post("/api/apply/confirm/{job_id}")
async def confirm_apply_endpoint(job_id: str):
    from cvfitengine.scrapers.cache import JobCache
    from cvfitengine.apply.queue import ApplyQueue
    from cvfitengine.apply.linkedin_apply import confirm_apply

    result = await confirm_apply(job_id)
    cache = JobCache()
    q = ApplyQueue()

    if result["status"] == "applied":
        q.mark_applied(job_id)
        cache.update_status(job_id, "applied")
    else:
        q.mark_failed(job_id, result.get("error", "confirm failed"))
        cache.update_status(job_id, "failed")

    screenshot_url = ""
    sp = result.get("screenshot_path", "")
    if sp:
        screenshot_url = f"/static/screenshots/{Path(sp).name}"

    return {
        "status": result["status"],
        "screenshot_url": screenshot_url,
        "error": result.get("error"),
    }


@app.get("/api/apply/log")
async def apply_log():
    from cvfitengine.apply.queue import ApplyQueue
    q = ApplyQueue()
    return {"log": q.list_all()}


# ══════════════════════════════════════════════════════════════
# Resume YAML
# ══════════════════════════════════════════════════════════════
_RESUME_YAML_PATH = Path(__file__).parent.parent / "data" / "forms" / "users" / "resume_form_sowjanya.yaml"


@app.get("/api/resume-yaml", response_class=Response)
async def get_resume_yaml():
    if not _RESUME_YAML_PATH.exists():
        raise HTTPException(status_code=404, detail="Resume YAML not found")
    return Response(content=_RESUME_YAML_PATH.read_text(), media_type="text/plain")


# Health
# ══════════════════════════════════════════════════════════════
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "api_key_set": bool(env("ANTHROPIC_API_KEY")),
        "anthropic": bool(env("ANTHROPIC_API_KEY")),
        "reed": bool(env("REED_API_KEY")),
        "adzuna": bool(env("ADZUNA_APP_ID")) and bool(env("ADZUNA_APP_KEY")),
    }


# ══════════════════════════════════════════════════════════════
# Sponsor Check
# ══════════════════════════════════════════════════════════════

class SponsorCheckRequest(BaseModel):
    company_name: str

@app.post("/api/sponsor/check")
async def check_sponsor(req: SponsorCheckRequest):
    """
    Check whether a company is on the UK licensed sponsor register.
    Returns: licensed | not_licensed | unknown
    Note: 'licensed' means they have permission to sponsor — not that
    they are actively doing so. Always verify via job ad or recruiter.
    """
    from cvfitengine.sponsor_checker import is_licensed_sponsor, sponsor_status_label
    status = is_licensed_sponsor(req.company_name)
    return {
        "company_name": req.company_name,
        "sponsor_status": status,
        "label": sponsor_status_label(status),
    }

@app.post("/api/sponsor/invalidate-cache")
async def invalidate_sponsor_cache():
    """Force a fresh download of the sponsor register on next check."""
    from cvfitengine.sponsor_checker import invalidate_cache
    invalidate_cache()
    return {"status": "cache invalidated"}


# ══════════════════════════════════════════════════════════════
# Shortlist — categorical persistence
# ══════════════════════════════════════════════════════════════

SHORTLIST_BUCKETS = ["dream-aligned", "status-unlock", "sponsor-safe-bridge", "tactical-only"]
_shortlist_store: dict[str, list] = {b: [] for b in SHORTLIST_BUCKETS}

class ShortlistSaveRequest(BaseModel):
    job: dict
    bucket: str  # one of SHORTLIST_BUCKETS
    sponsor_status: str = "unknown"  # licensed | not_licensed | unknown

@app.post("/api/shortlist/save")
async def shortlist_save(req: ShortlistSaveRequest):
    if req.bucket not in SHORTLIST_BUCKETS:
        return {"error": f"Unknown bucket '{req.bucket}'. Must be one of {SHORTLIST_BUCKETS}"}
    job = {**req.job, "sponsor_status": req.sponsor_status, "bucket": req.bucket}
    bucket = _shortlist_store[req.bucket]
    # Deduplicate by job id
    existing = next((i for i, j in enumerate(bucket) if j.get("id") == job.get("id")), None)
    if existing is not None:
        bucket[existing] = job  # update in place
    else:
        bucket.append(job)
    return {"status": "saved", "bucket": req.bucket, "total": len(bucket)}

@app.delete("/api/shortlist/remove")
async def shortlist_remove(job_id: str, bucket: str):
    if bucket not in SHORTLIST_BUCKETS:
        return {"error": f"Unknown bucket '{bucket}'"}
    before = len(_shortlist_store[bucket])
    _shortlist_store[bucket] = [j for j in _shortlist_store[bucket] if j.get("id") != job_id]
    removed = before - len(_shortlist_store[bucket])
    return {"status": "removed" if removed else "not_found", "bucket": bucket}

@app.get("/api/shortlist")
async def shortlist_get():
    """Return all shortlisted jobs organised by bucket."""
    return {
        "buckets": _shortlist_store,
        "total": sum(len(v) for v in _shortlist_store.values()),
    }


# ══════════════════════════════════════════════════════════════
# Tracker — Phase 4
# ══════════════════════════════════════════════════════════════
import json as _json
from datetime import datetime as _dt


def _load_status(folder: Path) -> dict | None:
    sp = folder / "status.json"
    if not sp.exists():
        return None
    try:
        return _json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_status(folder: Path, status: dict) -> None:
    (folder / "status.json").write_text(_json.dumps(status, indent=2), encoding="utf-8")


def _find_app_folder(job_id: str) -> Path | None:
    if not APPLICATIONS_DIR.exists():
        return None
    for folder in APPLICATIONS_DIR.iterdir():
        if not folder.is_dir():
            continue
        s = _load_status(folder)
        if s and s.get("job_id") == job_id:
            return folder
    return None


@app.get("/api/tracker/list")
async def tracker_list():
    if not APPLICATIONS_DIR.exists():
        return {"applications": []}
    apps = []
    for folder in sorted(APPLICATIONS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        s = _load_status(folder)
        if s:
            apps.append(s)
    return {"applications": apps}


@app.patch("/api/tracker/{job_id}/stage")
async def tracker_update_stage(job_id: str, body: dict):
    folder = _find_app_folder(job_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Application not found")
    s = _load_status(folder)
    stage = body.get("stage", "")
    s["stage"] = stage
    s.setdefault("stages_log", []).append({"stage": stage, "at": _dt.utcnow().isoformat()})
    _save_status(folder, s)
    return {"ok": True}


@app.patch("/api/tracker/{job_id}/notes")
async def tracker_update_notes(job_id: str, body: dict):
    folder = _find_app_folder(job_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Application not found")
    s = _load_status(folder)
    s["notes"] = body.get("notes", "")
    _save_status(folder, s)
    return {"ok": True}


@app.patch("/api/tracker/{job_id}/follow_up")
async def tracker_follow_up(job_id: str, body: dict):
    folder = _find_app_folder(job_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Application not found")
    s = _load_status(folder)
    s["follow_up_due"] = body.get("follow_up_due")
    _save_status(folder, s)
    return {"ok": True}


@app.get("/api/tracker/{job_id}/files")
async def tracker_files(job_id: str):
    folder = _find_app_folder(job_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Application not found")
    files = [f.name for f in folder.iterdir() if f.is_file()]
    return {"files": files}


@app.get("/api/tracker/{job_id}/file/{filename}")
async def tracker_get_file(job_id: str, filename: str):
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    folder = _find_app_folder(job_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Application not found")
    fpath = folder / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=fpath.read_text(encoding="utf-8"), media_type="text/plain")


# ══════════════════════════════════════════════════════════════
# SPA
# ══════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(PUBLIC / "index.html"))
