from __future__ import annotations
import re

def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9\+\#\.-]{1,}", text.lower()))

def score_block(job_keywords: list[str], block_text: str) -> dict:
    jk = set(job_keywords)
    bt = _tokenize(block_text)
    overlap = jk & bt
    denom = max(10, len(jk))
    score = len(overlap) / denom
    return {"score": round(score, 4), "overlap": sorted(list(overlap))[:50], "overlap_count": len(overlap)}

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

