from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from cvfitengine.core.load import load_resume_form
from cvfitengine.parsing.jd_parser import parse_job
from cvfitengine.selection.select import rank_blocks
from cvfitengine.rendering.latex import render_latex
from cvfitengine.parsing.tag_extractor import load_tag_vocab, extract_job_tags, collect_resume_tags
from cvfitengine.core.role_profiles import load_role_profiles


def now_stamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")


def ensure_run_dir(base: str | Path) -> Path:
    run_dir = Path(base) / now_stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_context(resume_form, job, selected_exp, selected_proj):
    headline = resume_form.profile.headlines[0].text if resume_form.profile.headlines else ""
    summary = resume_form.profile.summaries[0].text if resume_form.profile.summaries else ""

    skills = [{"name": c.name, "items": c.items} for c in resume_form.profile.skills.categories]

    return {
        "person": resume_form.profile.person,
        "headline": headline,
        "summary": summary,
        "skills": skills,
        "certifications": resume_form.profile.certifications,
        "interests": resume_form.profile.interests,
        "education": resume_form.blocks.education,
        "experience": selected_exp,
        "projects": selected_proj,
        "job_title": job.title,
        "job_keywords": job.keywords,
    }


st.set_page_config(page_title="CVFitEngine", layout="wide")
st.title("CVFitEngine")
st.caption("Load YAML resume form, paste job description, select blocks, render LaTeX.")

with st.sidebar:
    st.header("Inputs")
    user_yaml_path = st.text_input("User form YAML path", value="data/forms/users/resume_form_sowjanya.yaml")
    template_path = st.text_input("LaTeX template path", value="templates/latex/cv.tex.j2")
    runs_dir = st.text_input("Runs output dir", value="data/runs")

    st.divider()
    st.header("Selection settings")
    top_exp_preview = st.slider("Preview top experience", 1, 12, 8)
    top_proj_preview = st.slider("Preview top projects", 1, 12, 6)

    st.divider()
    st.header("Export")
    min_score = st.slider("Min score threshold", 0.0, 1.0, 0.10, 0.01)

    profiles = load_role_profiles("configs/role_profiles.yaml")
    profile_keys = sorted([k for k in profiles.keys() if k != "default"])
    role_key = st.selectbox("Role profile", ["default"] + profile_keys, index=0)

    weights = profiles.get(role_key, profiles.get("default", {}))
    exp_w = float(weights.get("experience", 1.0))
    proj_w = float(weights.get("projects", 1.0))
    ach_w = float(weights.get("achievements", 1.0))

st.caption(f"Section weights: experience {exp_w}, projects {proj_w}, achievements {ach_w}")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("Job description")
    jd_text = st.text_area("Paste the job description here", height=340, placeholder="Paste JD text...")

    parse_clicked = st.button("Parse and rank", type="primary", use_container_width=True)

with col_right:
    st.subheader("Loaded resume form")
    resume = None
    load_error = None
    try:
        resume = load_resume_form(user_yaml_path)
        st.success(f"Loaded: {resume.profile.person.full_name}")
    except Exception as e:
        load_error = str(e)
        st.error(f"Could not load YAML form: {load_error}")

if parse_clicked:
    if not resume:
        st.stop()
    if not jd_text.strip():
        st.warning("Paste a job description first.")
        st.stop()

    job = parse_job(jd_text)
    vocab = load_tag_vocab("configs/tag_vocab.yaml")
    job_tags = extract_job_tags(jd_text, vocab)
    resume_tags = collect_resume_tags(resume)

    missing_tags = {
        k: sorted(list(set(job_tags[k]) - set(resume_tags[k])))
        for k in job_tags.keys()
    }
    st.session_state["job"] = job.model_dump()
    st.session_state["ranked_exp"] = [
        {k: v for k, v in r.items() if k != "block"} | {"block": r["block"]}
        for r in rank_blocks(job.keywords, resume.blocks.experience, job_tags=job_tags, section_weight=exp_w)
    ]

    st.session_state["ranked_proj"] = [
        {k: v for k, v in r.items() if k != "block"} | {"block": r["block"]}
        for r in rank_blocks(job.keywords, resume.blocks.projects, job_tags=job_tags, section_weight=proj_w)
    ]
    st.subheader("Extracted job tags")
    st.json(job_tags)

    st.subheader("Missing tags (not present anywhere in resume tags)")
    st.json(missing_tags)

if "ranked_exp" not in st.session_state:
    st.info("Paste a job description and click Parse and rank.")
    st.stop()

job = parse_job(jd_text)
ranked_exp = st.session_state["ranked_exp"]
ranked_proj = st.session_state["ranked_proj"]

st.divider()
st.subheader("Ranked blocks")

tab_exp, tab_proj = st.tabs(["Experience", "Projects"])

def block_label_exp(b):
    return f"{b.id} | {b.role} @ {b.company}"

def block_label_proj(b):
    return f"{b.id} | {b.title}"

with tab_exp:
    st.caption("Select which experience blocks to include. You can edit bullets before rendering.")

    exp_options = []
    for r in ranked_exp[:top_exp_preview]:
        if r["score"] < min_score:
            continue
        exp_options.append(r["block"])

    selected_exp = st.multiselect(
        "Experience blocks",
        options=exp_options,
        default=exp_options[: min(3, len(exp_options))],
        format_func=block_label_exp,
    )

    for b in selected_exp:
        with st.expander(f"Edit bullets: {block_label_exp(b)}", expanded=False):
            for i, bullet in enumerate(b.bullets):
                new_text = st.text_area(
                    f"{b.id} bullet {i+1}",
                    value=bullet.text,
                    height=70,
                    key=f"{b.id}_bullet_{i}",
                )
                bullet.text = new_text

with tab_proj:
    st.caption("Select which project blocks to include. You can edit bullets before rendering.")

    proj_options = []
    for r in ranked_proj[:top_proj_preview]:
        if r["score"] < min_score:
            continue
        proj_options.append(r["block"])

    selected_proj = st.multiselect(
        "Project blocks",
        options=proj_options,
        default=proj_options[: min(2, len(proj_options))],
        format_func=block_label_proj,
    )

    for b in selected_proj:
        with st.expander(f"Edit bullets: {block_label_proj(b)}", expanded=False):
            for i, bullet in enumerate(b.bullets):
                new_text = st.text_area(
                    f"{b.id} bullet {i+1}",
                    value=bullet.text,
                    height=70,
                    key=f"{b.id}_bullet_{i}",
                )
                bullet.text = new_text

st.divider()
col_a, col_b = st.columns([1, 1])

with col_a:
    if st.button("Generate run outputs", use_container_width=True):
        run_dir = ensure_run_dir(runs_dir)

        selection = {
            "job_title": job.title,
            "selected_experience": [b.id for b in selected_exp],
            "selected_projects": [b.id for b in selected_proj],
        }
        (run_dir / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")

        fit_report = {
            "job_keywords": job.keywords,
            "ranked_experience": [
                {"id": r["id"], "score": r["score"], "base_score": r["base_score"], "tag_overlap": r["tag_overlap"]} for r in ranked_exp[:20]
            ],
            "ranked_projects": [
                {"id": r["id"], "score": r["score"], "base_score": r["base_score"], "tag_overlap": r["tag_overlap"]} for r in ranked_proj[:20]
            ],
        }
        (run_dir / "fit_report.json").write_text(json.dumps(fit_report, indent=2), encoding="utf-8")

        ctx = build_context(resume, job, selected_exp, selected_proj)
        tex = render_latex(template_path, ctx)
        (run_dir / "cv.tex").write_text(tex, encoding="utf-8")

        st.success(f"Wrote outputs to: {run_dir}")
        st.session_state["last_run_dir"] = str(run_dir)

        from cvfitengine.rendering.pdf import compile_latex_to_pdf

        pdf_path = compile_latex_to_pdf(run_dir / "cv.tex")
        st.success(f"PDF generated: {pdf_path}")

        with open(pdf_path, "rb") as f:
            st.download_button(
                label="Download PDF",
                data=f,
                file_name="cv.pdf",
                mime="application/pdf"
            )

with col_b:
    last_run = st.session_state.get("last_run_dir")
    if last_run:
        st.info(f"Last run: {last_run}")

st.divider()
st.subheader("Preview LaTeX")

ctx_preview = build_context(resume, job, selected_exp, selected_proj)
tex_preview = render_latex(template_path, ctx_preview)
st.code(tex_preview, language="tex")



