from __future__ import annotations
from ..scoring.score import score_block, block_to_text

def rank_blocks(job_keywords: list[str], blocks: list, job_tags: dict | None = None, section_weight: float = 1.0) -> list[dict]:
    ranked = []
    for b in blocks:
        r = score_block(job_keywords, block_to_text(b))
        base_score = r["score"]
        weighted_score = round(base_score * float(section_weight), 4)
        ranked.append({
            "id": b.id,
            "score": weighted_score,
            "base_score": base_score,
            "overlap_count": r.get("overlap_count", 0),
            "text_overlap": r.get("text_overlap", r.get("overlap", [])),
            "tag_overlap": r.get("tag_overlap", {}),
            "block": b
        })
    ranked.sort(key=lambda x: (x["score"], x["overlap_count"]), reverse=True)
    return ranked
