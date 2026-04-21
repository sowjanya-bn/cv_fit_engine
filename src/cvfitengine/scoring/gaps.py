"""
Skill gap analysis — compares JD requirements against resume coverage.
"""
from __future__ import annotations

from pathlib import Path


def compute_gaps(job: dict, resume) -> dict:
    """Compare JD skills/tools against resume and return gap report.

    Parameters
    ----------
    job:    dict or JobListing-like with description_full field
    resume: ResumeForm instance

    Returns
    -------
    {
        missing_skills:   list[str],
        missing_tools:    list[str],
        partial_matches:  list[str],
        coverage_pct:     float (0-1)
    }
    """
    from ..parsing.tag_extractor import (
        load_tag_vocab,
        extract_job_tags,
        collect_resume_tags,
    )

    # Resolve vocab path relative to package
    vocab_path = Path(__file__).parent.parent.parent.parent / "configs" / "tag_vocab.yaml"
    if not vocab_path.exists():
        vocab_path = Path("configs/tag_vocab.yaml")

    try:
        vocab = load_tag_vocab(vocab_path)
    except Exception:
        return {
            "missing_skills": [],
            "missing_tools": [],
            "partial_matches": [],
            "coverage_pct": 0.0,
        }

    description = _get_description(job)
    if not description:
        return {
            "missing_skills": [],
            "missing_tools": [],
            "partial_matches": [],
            "coverage_pct": 0.0,
        }

    # Extract what the JD requires
    jd_tags = extract_job_tags(description, vocab)
    required_skills = set(jd_tags.get("skills", []))
    required_tools = set(jd_tags.get("tools", []))

    # Collect what the resume has (block tags + profile skills)
    resume_tags = collect_resume_tags(resume)
    resume_skills = set(resume_tags.get("skills", set()))
    resume_tools = set(resume_tags.get("tools", set()))

    # Also extract from profile.skills categories (flat text)
    profile_text = _extract_profile_skills_text(resume)
    if profile_text:
        profile_tags = extract_job_tags(profile_text, vocab)
        resume_skills |= set(profile_tags.get("skills", []))
        resume_tools |= set(profile_tags.get("tools", []))

    # Compute gaps
    missing_skills = sorted(required_skills - resume_skills)
    missing_tools = sorted(required_tools - resume_tools)

    # Partial matches: resume has token sub-components of required tags
    partial: list[str] = []
    all_resume_tokens = _flatten_tokens(resume_skills | resume_tools)
    for tag in (required_skills | required_tools):
        if tag in (resume_skills | resume_tools):
            continue
        parts = set(tag.replace("-", " ").split())
        if parts & all_resume_tokens:
            partial.append(tag)

    # Coverage
    total_required = len(required_skills) + len(required_tools)
    if total_required == 0:
        coverage = 1.0
    else:
        matched = (
            len(required_skills & resume_skills)
            + len(required_tools & resume_tools)
        )
        coverage = round(matched / total_required, 4)

    return {
        "missing_skills": missing_skills,
        "missing_tools": missing_tools,
        "partial_matches": partial,
        "coverage_pct": coverage,
    }


def _get_description(job) -> str:
    if isinstance(job, dict):
        return job.get("description_full") or job.get("summary") or ""
    return getattr(job, "description_full", "") or getattr(job, "summary", "") or ""


def _extract_profile_skills_text(resume) -> str:
    """Flatten all skill category items from profile.skills into one string."""
    try:
        categories = resume.profile.skills.categories or []
        parts = []
        for cat in categories:
            parts.extend(cat.items or [])
        return " ".join(parts)
    except Exception:
        return ""


def _flatten_tokens(tag_set: set[str]) -> set[str]:
    """Return individual word tokens from a set of possibly hyphenated tags."""
    tokens: set[str] = set()
    for tag in tag_set:
        tokens.add(tag)
        tokens.update(tag.replace("-", " ").split())
    return tokens
