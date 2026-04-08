from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.overlay_types import TailoredOverlay


def _pick_by_id(items: List[dict], item_id: Optional[str], id_key: str = "id") -> Optional[dict]:
    if not item_id:
        return None
    for item in items:
        if item.get(id_key) == item_id:
            return item
    return None


def _filter_by_ids(items: List[dict], selected_ids: List[str], id_key: str = "id") -> List[dict]:
    if not selected_ids:
        return items
    selected = set(selected_ids)
    return [item for item in items if item.get(id_key) in selected]


def _reorder_skill_groups(skill_groups: List[dict], skills_order: List[str], id_key: str = "id") -> List[dict]:
    if not skills_order:
        return skill_groups

    rank = {key: i for i, key in enumerate(skills_order)}

    def sort_key(group: dict):
        group_id = group.get(id_key)
        return (rank.get(group_id, len(rank)),)

    return sorted(skill_groups, key=sort_key)


def _apply_bullet_overrides(experience_items: List[dict], bullet_overrides: Dict[str, str]) -> List[dict]:
    """
    Expected key format:
    exp_tcs_backend.bullet_2
    """
    if not bullet_overrides:
        return experience_items

    updated = deepcopy(experience_items)

    for exp in updated:
        exp_id = exp.get("id")
        bullets = exp.get("bullets", [])

        for key, new_text in bullet_overrides.items():
            prefix = f"{exp_id}.bullet_"
            if key.startswith(prefix):
                try:
                    idx = int(key.replace(prefix, "")) - 1
                except ValueError:
                    continue

                if 0 <= idx < len(bullets):
                    bullets[idx] = new_text

        exp["bullets"] = bullets

    return updated


def build_render_context(master_profile: Dict[str, Any], overlay: TailoredOverlay) -> Dict[str, Any]:
    """
    Build a render-ready context from the stable master profile and a small tailored overlay.

    Assumes the master_profile is a dict-like structure with keys such as:
      - summaries: List[dict]
      - headlines: List[dict]
      - experience: List[dict]
      - projects: List[dict]
      - skill_groups: List[dict]

    Adjust field names later if your existing YAML uses different keys.
    """
    profile = deepcopy(master_profile)

    summaries = profile.get("summaries", [])
    headlines = profile.get("headlines", [])
    experience = profile.get("experience", [])
    projects = profile.get("projects", [])
    skill_groups = profile.get("skill_groups", [])

    selected_summary = _pick_by_id(summaries, overlay.selected_summary) or (summaries[0] if summaries else None)
    selected_headline = _pick_by_id(headlines, overlay.selected_headline) or (headlines[0] if headlines else None)

    selected_experience = _filter_by_ids(experience, overlay.selected_experience)
    selected_projects = _filter_by_ids(projects, overlay.selected_projects)
    ordered_skill_groups = _reorder_skill_groups(skill_groups, overlay.skills_order)

    selected_experience = _apply_bullet_overrides(
        selected_experience,
        overlay.custom_edits.bullet_overrides,
    )

    summary_text = overlay.custom_edits.summary_override or (
        selected_summary.get("text") if selected_summary else None
    )
    headline_text = overlay.custom_edits.headline_override or (
        selected_headline.get("text") if selected_headline else None
    )

    context = {
        "target_region": overlay.target_region,
        "target_role_family": overlay.target_role_family,
        "job_id": overlay.job_id,

        "person": profile.get("person", {}),
        "contact": profile.get("contact", {}),
        "education": profile.get("education", []),
        "certifications": profile.get("certifications", []),
        "publications": profile.get("publications", []),
        "awards": profile.get("awards", []),

        "summary": summary_text,
        "headline": headline_text,
        "experience": selected_experience,
        "projects": selected_projects,
        "skill_groups": ordered_skill_groups,

        # keep these for debugging / future UI
        "selected_summary_id": overlay.selected_summary,
        "selected_headline_id": overlay.selected_headline,
    }

    return context