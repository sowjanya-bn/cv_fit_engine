from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from cvfitengine.core.load import load_resume_form
from cvfitengine.parsing.jd_parser import parse_job
from cvfitengine.parsing.jd_classifier import classify_jd
from cvfitengine.selection.select import rank_blocks
from cvfitengine.rendering.latex import render_latex
from cvfitengine.parsing.tag_extractor import load_tag_vocab, extract_job_tags, collect_resume_tags
from cvfitengine.core.role_profiles import load_role_profiles
from cvfitengine.core.base_packs import load_base_packs
from cvfitengine.scoring.score import load_scoring_config


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

    st.divider()
    st.header("Baseline fill")
    # These are fallbacks. Role base packs can override them.
    min_exp_default = st.slider("Minimum experience blocks", 1, 8, 3)
    min_proj_default = st.slider("Minimum project blocks", 0, 8, 2)

    profiles = load_role_profiles("configs/role_profiles.yaml")
    profile_keys = sorted([k for k in profiles.keys() if k != "default"])
    role_key = st.selectbox("Role profile", ["default"] + profile_keys, index=0)

    base_packs = load_base_packs("configs/base_packs.yaml")
    pack = base_packs.get(role_key, base_packs.get("default", {}))
    pack_min_exp = int(pack.get("min_experience_blocks", min_exp_default))
    pack_min_proj = int(pack.get("min_project_blocks", min_proj_default))
    required_exp_ids = list(pack.get("required_experience_ids", []))
    required_proj_ids = list(pack.get("required_project_ids", []))

    st.caption("Role base pack")
    st.write({
        "required_experience_ids": required_exp_ids,
        "required_project_ids": required_proj_ids,
        "min_experience_blocks": pack_min_exp,
        "min_project_blocks": pack_min_proj,
    })

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
    jd_profile = classify_jd(jd_text)
    vocab = load_tag_vocab("configs/tag_vocab.yaml")
    job_tags = extract_job_tags(jd_text, vocab)
    resume_tags = collect_resume_tags(resume)
    scoring_cfg = load_scoring_config("configs/scoring.yaml")

    missing_tags = {
        k: sorted(list(set(job_tags[k]) - set(resume_tags[k])))
        for k in job_tags.keys()
    }
    st.session_state["job"] = job.model_dump()
    st.session_state["jd_profile"] = {
        "category": jd_profile.category,
        "seniority_level": jd_profile.seniority_level,
        "scores": jd_profile.scores,
    }

    # Determine anchor emphasis for this role based on JD type.
    anchor_ids: list[str] = []
    anchor_sets = (pack.get("anchor_sets") or {})
    if isinstance(anchor_sets, dict) and anchor_sets:
        if jd_profile.category == "backend_systems":
            anchor_ids = list(anchor_sets.get("eng_first", []))
        else:
            # applied_ai_systems / ml_heavy / mixed -> default to AI-first emphasis
            anchor_ids = list(anchor_sets.get("ai_first", []))
    else:
        # Fallback: treat required blocks as anchors.
        anchor_ids = required_exp_ids

    st.session_state["anchor_ids"] = anchor_ids

    st.session_state["ranked_proj"] = [
        {k: v for k, v in r.items() if k != "block"} | {"block": r["block"]}
        for r in rank_blocks(job.keywords, resume.blocks.projects, job_tags=job_tags, section_weight=proj_w, scoring_cfg=scoring_cfg)
    ]

    # Re-rank experience using anchors + seniority bias.
    st.session_state["ranked_exp"] = [
        {k: v for k, v in r.items() if k != "block"} | {"block": r["block"]}
        for r in rank_blocks(
            job.keywords,
            resume.blocks.experience,
            job_tags=job_tags,
            section_weight=exp_w,
            scoring_cfg=scoring_cfg,
            anchor_ids=anchor_ids,
            anchor_multiplier=float(pack.get("anchor_multiplier", 1.18)),
            seniority_level=jd_profile.seniority_level,
        )
    ]

    st.subheader("JD classification")
    st.json(st.session_state["jd_profile"])
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
jd_profile_state = st.session_state.get("jd_profile")

st.divider()
st.subheader("Ranked blocks")

tab_exp, tab_proj = st.tabs(["Experience", "Projects"])

def block_label_exp(b):
    dates = ""
    if (b.start or "").strip() or (b.end or "").strip():
        dates = f" ({(b.start or '').strip()}–{(b.end or '').strip()})"
    return f"{b.id} | {b.role} @ {b.company}{dates}"

def block_label_proj(b):
    return f"{b.id} | {b.title}"

with tab_exp:
    st.caption("Select which experience blocks to include. You can edit bullets before rendering.")

    # Seed options with required blocks from the base pack.
    exp_by_id = {b.id: b for b in resume.blocks.experience}

    # Prefer a JD-aware order: anchors first (in-order), then remaining required.
    anchor_ids_ui = st.session_state.get("anchor_ids", []) or []
    ordered_required = []
    for i in anchor_ids_ui:
        if i in required_exp_ids and i not in ordered_required:
            ordered_required.append(i)
    for i in required_exp_ids:
        if i not in ordered_required:
            ordered_required.append(i)

    exp_options = [exp_by_id[i] for i in ordered_required if i in exp_by_id]

    # Fill remaining options using ranking.
    for r in ranked_exp[:top_exp_preview]:
        if r["block"].id in {b.id for b in exp_options}:
            continue
        # Always include at least the pack minimum (or user baseline), even if scores are low.
        if r["score"] >= min_score or len(exp_options) < max(pack_min_exp, min_exp_default):
            exp_options.append(r["block"])

    selected_exp = st.multiselect(
        "Experience blocks",
        options=exp_options,
        default=exp_options[: min(max(pack_min_exp, min_exp_default), len(exp_options))],
        format_func=block_label_exp,
    )

    # Chronology enforcement: warn early if dates are missing.
    missing_dates = [b for b in selected_exp if not (b.start or "").strip() or not (b.end or "").strip()]
    if missing_dates:
        st.warning(
            "Missing dates for: "
            + ", ".join([f"{b.role} ({b.id})" for b in missing_dates])
            + ". Add start and end dates to enable export."
        )

    for b in selected_exp:
        with st.expander(f"Edit bullets: {block_label_exp(b)}", expanded=False):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                b.start = st.text_input(f"{b.id} start", value=b.start or "", key=f"{b.id}_start")
            with col2:
                b.end = st.text_input(f"{b.id} end", value=b.end or "", key=f"{b.id}_end")
            with col3:
                b.location = st.text_input(f"{b.id} location", value=b.location or "", key=f"{b.id}_loc")

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

    proj_by_id = {b.id: b for b in resume.blocks.projects}
    proj_options = [proj_by_id[i] for i in required_proj_ids if i in proj_by_id]

    for r in ranked_proj[:top_proj_preview]:
        if r["block"].id in {b.id for b in proj_options}:
            continue
        if r["score"] >= min_score or len(proj_options) < max(pack_min_proj, min_proj_default):
            proj_options.append(r["block"])

    selected_proj = st.multiselect(
        "Project blocks",
        options=proj_options,
        default=proj_options[: min(max(pack_min_proj, min_proj_default), len(proj_options))],
        format_func=block_label_proj,
    )

    for b in selected_proj:
        with st.expander(f"Edit bullets: {block_label_proj(b)}", expanded=False):
            col1, col2 = st.columns([1, 1])
            with col1:
                b.start = st.text_input(f"{b.id} start", value=b.start or "", key=f"{b.id}_start")
            with col2:
                b.end = st.text_input(f"{b.id} end", value=b.end or "", key=f"{b.id}_end")
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
        # Block export if chronology is incomplete.
        missing_dates = [b for b in selected_exp if not (b.start or "").strip() or not (b.end or "").strip()]
        if missing_dates:
            st.error(
                "Cannot export: missing start/end dates for "
                + ", ".join([f"{b.role} ({b.id})" for b in missing_dates])
            )
            st.stop()
        run_dir = ensure_run_dir(runs_dir)

        selection = {
            "job_title": job.title,
            "selected_experience": [b.id for b in selected_exp],
            "selected_projects": [b.id for b in selected_proj],
        }
        (run_dir / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")

        fit_report = {
            "jd_profile": jd_profile_state,
            "job_keywords": job.keywords,
            "ranked_experience": [
                {
                    "id": r["id"],
                    "score": r["score"],
                    "base_score": r["base_score"],
                    "text_score": r.get("text_score", 0.0),
                    "tag_score": r.get("tag_score", 0.0),
                    "tag_overlap": r["tag_overlap"],
                }
                for r in ranked_exp[:20]
            ],
            "ranked_projects": [
                {
                    "id": r["id"],
                    "score": r["score"],
                    "base_score": r["base_score"],
                    "text_score": r.get("text_score", 0.0),
                    "tag_score": r.get("tag_score", 0.0),
                    "tag_overlap": r["tag_overlap"],
                }
                for r in ranked_proj[:20]
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



