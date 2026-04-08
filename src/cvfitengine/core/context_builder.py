from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from cvfitengine.core.overlay_io import load_overlay
from cvfitengine.core.render_context import build_render_context


def build_context_with_optional_overlay(
    master_profile: Dict[str, Any],
    overlay_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    If overlay_path is provided, build context from master profile + overlay.
    Otherwise return the master profile unchanged or in legacy-compatible form.
    """
    if not overlay_path:
        return master_profile

    overlay = load_overlay(Path(overlay_path))
    return build_render_context(master_profile, overlay)