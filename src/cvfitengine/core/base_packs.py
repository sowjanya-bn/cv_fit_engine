from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_base_packs(path: str | Path = "configs/base_packs.yaml") -> dict[str, dict[str, Any]]:
    """Load role base packs.

    A base pack is a deterministic set of block IDs that should always be included
    for a given target role, plus minimum-fill defaults.
    """
    p = Path(path)
    if not p.exists():
        return {"default": {"required_experience_ids": [], "required_project_ids": [], "min_experience_blocks": 2, "min_project_blocks": 1}}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    # Ensure a default pack exists.
    data.setdefault(
        "default",
        {"required_experience_ids": [], "required_project_ids": [], "min_experience_blocks": 2, "min_project_blocks": 1},
    )
    return data
