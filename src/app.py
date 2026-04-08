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
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel

app = FastAPI(title="CV Fit Studio")

PUBLIC = Path(__file__).parent.parent / "public"
app.mount("/static", StaticFiles(directory=str(PUBLIC)), name="static")


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


def _dedup(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for j in jobs:
        key = hashlib.md5(
            f"{j.get('title','').lower().strip()}{j.get('company','').lower().strip()}".encode()
        ).hexdigest()
        if key not in seen:
            seen.add(key)
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
# Health
# ══════════════════════════════════════════════════════════════
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "anthropic": bool(env("ANTHROPIC_API_KEY")),
        "reed": bool(env("REED_API_KEY")),
        "adzuna": bool(env("ADZUNA_APP_ID")) and bool(env("ADZUNA_APP_KEY")),
    }


# ══════════════════════════════════════════════════════════════
# SPA
# ══════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(PUBLIC / "index.html"))
