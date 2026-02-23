from __future__ import annotations

from pathlib import Path
import yaml


def load_role_profiles(path: str | Path = "configs/role_profiles.yaml") -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}