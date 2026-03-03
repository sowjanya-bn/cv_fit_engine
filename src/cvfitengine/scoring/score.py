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

