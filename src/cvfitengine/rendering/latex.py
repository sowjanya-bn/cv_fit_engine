from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

def render_latex(template_path: str | Path, context: dict) -> str:
    tp = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(tp.parent)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template(tp.name)
    return tpl.render(**context)
