from __future__ import annotations

from pathlib import Path

import yaml

from core.overlay_types import TailoredOverlay


def load_overlay(path: str | Path) -> TailoredOverlay:
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    try:
        return TailoredOverlay.model_validate(data)  # Pydantic v2
    except AttributeError:
        return TailoredOverlay.parse_obj(data)  # Pydantic v1


def save_overlay(overlay: TailoredOverlay, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = overlay.model_dump(exclude_none=False)  # Pydantic v2
    except AttributeError:
        data = overlay.dict(exclude_none=False)  # Pydantic v1

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)