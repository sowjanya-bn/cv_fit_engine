from __future__ import annotations
from pathlib import Path
import subprocess

def compile_latex_to_pdf(tex_path: str | Path) -> Path:
    tex_path = Path(tex_path)
    pdf_path = tex_path.with_suffix(".pdf")

    subprocess.run(
        ["tectonic", str(tex_path), "--outdir", str(tex_path.parent)],
        check=True,
    )

    return pdf_path
