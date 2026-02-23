from __future__ import annotations
from pathlib import Path
import yaml
from .types import ResumeForm

def load_resume_form(path: str | Path) -> ResumeForm:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return ResumeForm.model_validate(data)
