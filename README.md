# CVFitEngine

Role-aligned CV assembly engine.

CVFitEngine reads a structured YAML resume form and a job description, scores relevant blocks, selects the best-matching experience and projects, and renders a tailored LaTeX CV along with a fit report.

The pipeline is deterministic and modular. The UI layer will be added later on top of this core engine.

---

# Architecture Overview

The system follows a clean pipeline:

resume_form.yaml
    ↓
Load + Validate (Pydantic models)
    ↓
Parse Job Description (keyword extraction)
    ↓
Score Blocks (keyword + tag overlap)
    ↓
Select Top Blocks
    ↓
Render Template (LaTeX via Jinja2)
    ↓
Output: CV + Selection + Fit Report

The YAML form is the canonical input.
Future UI components will generate this YAML.

---

# Installation

This project uses the modern Python packaging standard via `pyproject.toml`.

## 1. Create a virtual environment

python -m venv .venv
source .venv/bin/activate

On Windows:

.venv\Scripts\activate

## 2. Install in editable mode

pip install -e .

Editable mode allows you to modify the source code without reinstalling the package.

---

# Running the Pipeline

Place a job description in:

data/jobs/raw/jd.txt

Then run:

python -m cvfitengine.cli.main \
  --job data/jobs/raw/jd.txt \
  --user data/forms/users/sowjanya.yaml

The pipeline will create a timestamped run folder under:

data/runs/<timestamp>/

Containing:

- cv.tex — rendered LaTeX CV
- selection.json — selected experience and projects
- fit_report.json — scoring diagnostics and keyword overlaps

---

# Project Structure

cvfitengine/
  src/                      # Core pipeline logic
    cvfitengine/
      cli/                  # CLI entrypoint
      core/                 # Domain models (Pydantic)
      parsing/              # Job description parsing
      scoring/              # Block scoring logic
      selection/            # Block ranking and selection
      rendering/            # Template rendering
      ui/                   # Future UI layer

  data/
    forms/
      template/             # Blank YAML form
      users/                # User-filled YAML forms (gitignored)
    jobs/
      raw/                  # Raw job descriptions
      parsed/               # Structured job data (future)
    runs/                   # Output runs (gitignored)

  templates/
    latex/                  # LaTeX Jinja templates

  configs/                  # App configuration

  pyproject.toml            # Dependency and build configuration

---

# Design Principles

- YAML-first architecture
- Deterministic block selection
- Stable IDs for reusable experience blocks
- Tag-aware scoring (skills, tools, domain)
- Clear separation between pipeline and UI

---

# Roadmap

- Improve tag-based scoring weights
- Add role-specific selection rules
- Add DOCX rendering
- Build Streamlit-based UI on top of the pipeline



# Pre-requisites

brew install tectonic

tectonic --version

