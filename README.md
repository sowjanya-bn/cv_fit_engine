# CV Fit Engine

A local web app for role-aware CV tailoring, job discovery, cover letter generation, and job application automation — powered by Claude.

Built around Sowjanya's profile but easily adapted (edit `data/profile.yaml`).

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set your Anthropic API key

**Option A — `.env` file (recommended):**
```bash
cp .env.example .env
# edit .env and paste your key
```

**Option B — environment variable:**
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here   # Mac/Linux
```

### 3. Run

```bash
python run.py
```

Open **http://localhost:8000** in your browser.

---

## Project structure

```
cv_fit_engine/
├── run.py                      ← start the app
├── requirements.txt
├── .env.example
├── data/
│   ├── profile.yaml            ← YOUR resume data (edit this!)
│   ├── jobs_cache.json         ← scraped job cache
│   └── runs/                   ← generated CV/cover letter output
├── src/
│   └── app.py                  ← FastAPI backend
└── src/cvfitengine/
    ├── apply/
    │   ├── cover_letter.py     ← cover letter generation
    │   ├── linkedin_apply.py   ← LinkedIn Easy Apply automation
    │   └── queue.py            ← application queue
    ├── scoring/
    │   ├── score.py            ← CV-to-JD fit scoring
    │   └── gaps.py             ← skill gap analysis
    ├── scrapers/
    │   ├── cache.py            ← job cache
    │   └── ...                 ← job board scrapers (LinkedIn, etc.)
    └── sponsor_checker.py      ← visa sponsor eligibility checker
```

---

## Features

| Tab | What it does |
|-----|-------------|
| **Role Strategy** | Shows target tracks with honest fit scores and employer targets |
| **Job Discovery** | Scrapes and scores real job listings; filter by recency |
| **Shortlist** | Save jobs across buckets (priority / tactical-only); quick-tailor from here |
| **Tailor CV** | Role-aware CV generation with bullet rewrites + fit analysis |
| **Cover Letter** | Generates tailored cover letters per job with gap analysis |
| **Apply** | LinkedIn Easy Apply automation queue |
| **Output** | CV preview, cover letter, plain text (copy-paste), LaTeX download |

---

## Customising for your profile

Edit `data/profile.yaml` — structured as:

- `experience[]` — each role with bullets and tags
- `projects[]` — projects with bullets
- `skills{}` — skill categories
- `education[]` — degrees
- `target_roles[]` — target tracks with strategy text

---

## Troubleshooting

**"API key not set"** — check `.env` has `ANTHROPIC_API_KEY=sk-ant-...` with no quotes or spaces.

**Slow generation** — normal; Claude is writing a full CV + cover letter.

**Port already in use** — change the port in `run.py`: `uvicorn.run(..., port=8001)`.

**LinkedIn apply not working** — run `playwright install chromium` and ensure you have a valid LinkedIn session saved.
