from __future__ import annotations

import re
from pathlib import Path

import yaml


def load_scoring_config(path: str | Path = "configs/scoring.yaml") -> dict:
    """Load scoring weights from YAML."""
    p = Path(path)
    if not p.exists():
        return {"weights": {}}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {"weights": {}}

def _tokenize(text: str) -> set[str]:
    # Tokenizer for keyword overlap. Keep common tech symbols.
    tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9\+\#\.-]{1,}", text.lower()))
    # Split dotted identifiers too (e.g. "schema.org" -> "schema", "org")
    extra = set()
    for t in tokens:
        if "." in t:
            extra.update([p for p in t.split(".") if p])
    return tokens | extra


def _norm_tag_list(vals) -> set[str]:
    if not vals:
        return set()
    return {str(x).strip().lower() for x in vals if str(x).strip()}


def _tag_overlap(job_tags: dict | None, block_tags) -> dict:
    """Compute overlap lists by tag category."""
    if not job_tags or not block_tags:
        return {"skills": [], "tools": [], "domain": [], "seniority": []}

    out = {}
    for k in ["skills", "tools", "domain", "seniority"]:
        jt = _norm_tag_list(job_tags.get(k, []))
        bt = _norm_tag_list(getattr(block_tags, k, []) if hasattr(block_tags, k) else block_tags.get(k, []))
        out[k] = sorted(list(jt & bt))
    return out

def score_block(
    job_keywords: list[str],
    block_text: str,
    *,
    job_tags: dict | None = None,
    block_tags=None,
    scoring_cfg: dict | None = None,
) -> dict:
    """Score a block against the job.

    The score is a blend of:
      - keyword token overlap
      - tag overlap (skills/tools/domain/seniority), when job_tags and block_tags exist
    """
    jk = set([str(x).lower() for x in (job_keywords or [])])
    bt = _tokenize(block_text)
    text_overlap = jk & bt
    denom = max(10, len(jk))
    text_score = len(text_overlap) / denom

    tag_overlap = _tag_overlap(job_tags, block_tags)

    cfg = scoring_cfg or {"weights": {}}
    w = cfg.get("weights", {}) or {}
    w_skill = float(w.get("skill_overlap", 0.0))
    w_tool = float(w.get("tool_overlap", 0.0))
    w_domain = float(w.get("domain_match", 0.0))
    w_sen = float(w.get("seniority_match", 0.0))

    def frac(cat: str) -> float:
        jt = _norm_tag_list((job_tags or {}).get(cat, []))
        if not jt:
            return 0.0
        return len(tag_overlap.get(cat, [])) / max(1, len(jt))

    tag_score = (
        w_skill * frac("skills")
        + w_tool * frac("tools")
        + w_domain * frac("domain")
        + w_sen * frac("seniority")
    )

    tag_weight_sum = max(0.0, (w_skill + w_tool + w_domain + w_sen))
    if tag_weight_sum > 0:
        blended = 0.6 * text_score + 0.4 * min(1.0, tag_score)
    else:
        blended = text_score

    return {
        "score": round(blended, 4),
        "text_score": round(text_score, 4),
        "tag_score": round(tag_score, 4),
        "overlap": sorted(list(text_overlap))[:50],
        "overlap_count": len(text_overlap),
        "tag_overlap": tag_overlap,
    }

def score_job(job, resume, scoring_cfg: dict | None = None) -> dict:
    """Aggregate fit score for a full job against a ResumeForm.

    Parameters
    ----------
    job:         dict or JobListing-like with description_full field
    resume:      ResumeForm instance
    scoring_cfg: optional override; loads configs/scoring.yaml if None

    Returns
    -------
    {
        fit_score:       float 0-1,
        matched_skills:  list[str],
        matched_tools:   list[str],
        top_blocks:      list[str]  (block IDs),
        jd_category:     str,
        seniority_level: str,
    }
    """
    from pathlib import Path
    from ..parsing.jd_parser import parse_job
    from ..parsing.jd_classifier import classify_jd
    from ..parsing.tag_extractor import load_tag_vocab, extract_job_tags, collect_resume_tags
    from ..selection.select import rank_blocks

    description = (
        job.get("description_full") if isinstance(job, dict)
        else getattr(job, "description_full", "")
    ) or ""

    if not description:
        return {
            "fit_score": 0.0,
            "matched_skills": [],
            "matched_tools": [],
            "top_blocks": [],
            "jd_category": "unknown",
            "seniority_level": "unknown",
        }

    job_spec = parse_job(description)
    jd_profile = classify_jd(description)

    cfg = scoring_cfg or load_scoring_config()

    # Load tag vocab for job tag extraction
    vocab_path = Path(__file__).parent.parent.parent.parent / "configs" / "tag_vocab.yaml"
    if not vocab_path.exists():
        vocab_path = Path("configs/tag_vocab.yaml")
    job_tags: dict | None = None
    try:
        vocab = load_tag_vocab(vocab_path)
        job_tags = extract_job_tags(description, vocab)
    except Exception:
        job_tags = None

    # Score experience blocks (weight 0.6)
    exp_blocks = list(resume.blocks.experience or [])
    exp_ranked = rank_blocks(
        job_spec.keywords,
        exp_blocks,
        job_tags=job_tags,
        section_weight=0.6,
        scoring_cfg=cfg,
        seniority_level=jd_profile.seniority_level,
    ) if exp_blocks else []

    # Score project blocks (weight 0.3)
    proj_blocks = list(resume.blocks.projects or [])
    proj_ranked = rank_blocks(
        job_spec.keywords,
        proj_blocks,
        job_tags=job_tags,
        section_weight=0.3,
        scoring_cfg=cfg,
    ) if proj_blocks else []

    # Score education blocks (weight 0.1)
    edu_blocks = list(resume.blocks.education or [])
    edu_ranked = rank_blocks(
        job_spec.keywords,
        edu_blocks,
        job_tags=job_tags,
        section_weight=0.1,
        scoring_cfg=cfg,
    ) if edu_blocks else []

    # Weighted aggregate
    def _top_score(ranked: list[dict]) -> float:
        return ranked[0]["score"] if ranked else 0.0

    fit_score = round(
        _top_score(exp_ranked) * 0.6
        + _top_score(proj_ranked) * 0.3
        + _top_score(edu_ranked) * 0.1,
        4,
    )
    fit_score = min(1.0, fit_score)

    # Collect matched skills / tools from tag overlaps
    matched_skills: set[str] = set()
    matched_tools: set[str] = set()
    for r in (exp_ranked[:3] + proj_ranked[:3]):
        to = r.get("tag_overlap") or {}
        matched_skills.update(to.get("skills", []))
        matched_tools.update(to.get("tools", []))

    top_blocks = (
        [r["id"] for r in exp_ranked[:2]]
        + [r["id"] for r in proj_ranked[:1]]
    )

    return {
        "fit_score": fit_score,
        "matched_skills": sorted(matched_skills),
        "matched_tools": sorted(matched_tools),
        "top_blocks": top_blocks,
        "jd_category": jd_profile.category,
        "seniority_level": jd_profile.seniority_level,
    }


def block_to_text(block) -> str:
    parts = []

    # core text fields
    for k in ["role", "company", "title", "institution", "degree", "summary", "context"]:
        v = getattr(block, k, None)
        if v:
            parts.append(str(v))

    # bullets
    for b in getattr(block, "bullets", []) or []:
        txt = getattr(b, "text", None)
        if txt:
            parts.append(txt)

    # block-level tags (skills/tools/domain/seniority)
    tags = getattr(block, "tags", None)
    if tags:
        for attr in ["skills", "tools", "domain", "seniority"]:
            vals = getattr(tags, attr, None)
            if vals:
                parts.extend([str(x) for x in vals])

    return " ".join(parts)

