"""
Cover letter generator — calls Anthropic API directly using claude-haiku.
Results are cached per job_id to avoid redundant API calls.
"""
from __future__ import annotations

import os

import httpx


def generate_cover_letter(
    job: dict,
    resume,
    score_result: dict,
    *,
    force_regenerate: bool = False,
) -> str:
    """Generate a 3-paragraph cover letter for the given job and resume.

    Caches result by job_id. Returns cached version unless force_regenerate=True.

    Parameters
    ----------
    job:          dict or JobListing-like (needs id, title, company)
    resume:       ResumeForm instance
    score_result: dict from score_job() — used for matched/missing skills
    """
    from ..scrapers.cache import JobCache

    job_id = _get_id(job)
    cache = JobCache()

    # Return cached unless force regenerate
    if not force_regenerate:
        cached = cache.get_cover_letter(job_id)
        if cached:
            return cached

    letter = _call_anthropic(job, resume, score_result)
    cache.save_cover_letter(job_id, letter)
    return letter


def _get_id(job) -> str:
    if isinstance(job, dict):
        return job.get("id", "")
    return getattr(job, "id", "") or ""


def _call_anthropic(job: dict, resume, score_result: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[Cover letter unavailable: ANTHROPIC_API_KEY not set]"

    title = _field(job, "title")
    company = _field(job, "company")
    candidate_name = resume.profile.person.full_name
    headline = resume.profile.headlines[0].text if resume.profile.headlines else ""

    matched_skills = (score_result.get("matched_skills") or [])[:5]
    missing_skills = (score_result.get("missing_skills") or score_result.get("missing_tools") or [])[:3]
    seniority = score_result.get("seniority_level", "")
    fit_score = score_result.get("fit_score", 0.0)
    fit_pct = int(round(fit_score * 100)) if fit_score else 0

    system_prompt = (
        "You are an expert cover letter writer. Write concise, compelling cover letters "
        "in exactly 3 paragraphs separated by a blank line. Never start with 'I am writing to apply'. "
        "Lead with the candidate's most relevant differentiator. "
        "Frame missing skills as areas of active learning or adjacent expertise. "
        "Return ONLY the cover letter body — no salutation, no sign-off, no markdown, no bullet points. "
        "Each paragraph must be separated by exactly one blank line (\\n\\n). "
        "Do NOT run paragraphs together."
    )

    user_prompt = f"""Write a cover letter for:
Job: {title} at {company}
Candidate: {candidate_name} — {headline}
Fit score: {fit_pct}%
Top matched skills: {', '.join(matched_skills) if matched_skills else 'see profile'}
Skills to develop (frame positively): {', '.join(missing_skills) if missing_skills else 'none identified'}
Seniority signal: {seniority}

Profile summary:
{_profile_summary(resume)}

Rules:
- Exactly 3 paragraphs
- Separate each paragraph with a blank line
- ~80-90 words per paragraph (~250 words total)
- Paragraph 1: open with the strongest differentiator specific to this role
- Paragraph 2: connect specific experience/projects to the job requirements
- Paragraph 3: motivation for this company + forward-looking close
- Specific, not generic."""

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 600,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
        if resp.status_code != 200:
            return f"[Cover letter generation failed: {resp.status_code}]"
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
        return _ensure_paragraph_breaks(text)
    except Exception as e:
        return f"[Cover letter generation error: {e}]"


def _ensure_paragraph_breaks(text: str) -> str:
    """Normalise paragraph breaks — collapse excess blank lines, ensure 3 paragraphs."""
    import re
    # Normalise Windows line endings
    text = text.replace("\r\n", "\n")
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n\n".join(paragraphs)


def _field(job, key: str) -> str:
    if isinstance(job, dict):
        return job.get(key, "")
    return getattr(job, key, "") or ""


def _profile_summary(resume) -> str:
    parts = []
    if resume.profile.summaries:
        parts.append(resume.profile.summaries[0].text)
    # Skills overview
    skill_items = []
    for cat in resume.profile.skills.categories or []:
        skill_items.extend(cat.items[:3])
    if skill_items:
        parts.append("Skills: " + ", ".join(skill_items[:10]))
    # Recent experience
    exp = resume.blocks.experience
    if exp:
        parts.append(f"Most recent: {exp[0].role} at {exp[0].company}")
    return "\n".join(parts)
