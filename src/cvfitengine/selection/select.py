from __future__ import annotations

from ..scoring.score import score_block, block_to_text, load_scoring_config

def rank_blocks(
    job_keywords: list[str],
    blocks: list,
    job_tags: dict | None = None,
    section_weight: float = 1.0,
    scoring_cfg: dict | None = None,
    *,
    anchor_ids: list[str] | None = None,
    anchor_multiplier: float = 1.15,
    seniority_level: str | None = None,
) -> list[dict]:
    ranked = []
    cfg = scoring_cfg or load_scoring_config()
    anchor_set = set(anchor_ids or [])
    for b in blocks:
        r = score_block(job_keywords, block_to_text(b), job_tags=job_tags, block_tags=getattr(b, "tags", None), scoring_cfg=cfg)
        base_score = r["score"]
        weighted_score = base_score

        # Anchor boost: ensure key narrative blocks float to the top.
        if anchor_set and getattr(b, "id", None) in anchor_set:
            weighted_score *= float(anchor_multiplier)

        # Seniority boost: prefer lead-tagged blocks when JD signals seniority.
        # This is intentionally conservative and does not manufacture experience.
        if seniority_level:
            sen = set([str(x).lower() for x in getattr(getattr(b, "tags", None), "seniority", []) or []])
            if seniority_level.lower() in {"senior", "lead", "principal", "staff", "architect"}:
                if "lead" in sen:
                    weighted_score *= 1.10
                if "mid-level" in sen and seniority_level.lower() == "senior":
                    weighted_score *= 1.03

        weighted_score = round(weighted_score * float(section_weight), 4)
        ranked.append({
            "id": b.id,
            "score": weighted_score,
            "base_score": base_score,
            "overlap_count": r.get("overlap_count", 0),
            "text_overlap": r.get("overlap", []),
            "tag_overlap": r.get("tag_overlap", {}),
            "text_score": r.get("text_score", 0.0),
            "tag_score": r.get("tag_score", 0.0),
            "block": b
        })
    ranked.sort(key=lambda x: (x["score"], x["overlap_count"]), reverse=True)
    return ranked
