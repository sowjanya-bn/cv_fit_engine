from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CustomEdits(BaseModel):
    summary_override: Optional[str] = None
    headline_override: Optional[str] = None
    bullet_overrides: Dict[str, str] = Field(default_factory=dict)


class TailoredOverlay(BaseModel):
    job_id: str
    target_region: str = "uk"
    target_role_family: Optional[str] = None

    selected_summary: Optional[str] = None
    selected_headline: Optional[str] = None

    selected_projects: List[str] = Field(default_factory=list)
    selected_experience: List[str] = Field(default_factory=list)

    skills_order: List[str] = Field(default_factory=list)

    custom_edits: CustomEdits = Field(default_factory=CustomEdits)