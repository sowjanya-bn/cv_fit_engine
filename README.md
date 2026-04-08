# CV Fit Studio

A local web app for role-aware CV tailoring, job discovery, and cover letter generation — powered by Claude.

Built around Sowjanya's profile but easily adapted (edit `public/profile.js`).

---

## Quick start

### 1. Clone / unzip the project

```bash
cd cv-fit-studio
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your Anthropic API key

**Option A — `.env` file (recommended):**
```bash
cp .env.example .env
# then edit .env and paste your key
```

**Option B — environment variable:**
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here   # Mac/Linux
set ANTHROPIC_API_KEY=sk-ant-your-key-here       # Windows CMD
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"    # PowerShell
```

### 4. Run

```bash
python run.py
```

Open **http://localhost:8000** in your browser.

---

## Project structure

```
cv-fit-studio/
├── run.py              ← start the app
├── requirements.txt
├── .env.example
├── src/
│   └── app.py          ← FastAPI backend (proxies Claude API calls)
└── public/
    ├── index.html      ← single-page UI
    ├── profile.js      ← YOUR resume data (edit this!)
    └── app.js          ← all UI logic
```

---

## Customising for your profile

Edit `public/profile.js` — it's plain JavaScript with your full resume structured as:

- `PROFILE.experience[]` — each role with bullets and tags
- `PROFILE.projects[]` — projects with bullets
- `PROFILE.skills{}` — skill categories
- `PROFILE.achievements[]` — headline achievements
- `PROFILE.education[]` — degrees
- `ROLES[]` — the 5 target tracks with fit scores and strategy text

All other logic in `app.js` reads from `PROFILE` and `ROLES`.

---

## Features

| Tab | What it does |
|-----|-------------|
| **Role Strategy** | Shows 5 target tracks with honest fit scores and employer targets |
| **Job Discovery** | Claude generates 8 realistic, scored job listings per track |
| **Shortlist** | Save jobs you like; quick-tailor from here |
| **Tailor CV** | Role-aware CV generation with genuine bullet rewrites + fit analysis |
| **Output** | CV preview, cover letter, plain text (copy-paste), LaTeX download |
| **Settings** | API key status check |

---

## Why local?

- API key stays server-side — never in the browser
- You own your data — nothing leaves except the Claude API calls
- Works offline for everything except generation
- Easy to extend with your existing `cvfitengine` Python code

---

## Integrating with your existing cvfitengine

The LaTeX output from the Output tab is structurally compatible with your existing `cv.tex.j2` template. You can:

1. Download the `.tex` file from the Output tab
2. Drop it into your `data/runs/` directory
3. Compile with your existing `pdf.py` renderer

Or import `cvfitengine` scoring directly into `src/app.py` to add tag-based re-ranking on top of the LLM output.

---

## Troubleshooting

**"API key not set"** — check `.env` has `ANTHROPIC_API_KEY=sk-ant-...` with no quotes or spaces.

**Slow generation** — normal; Claude is writing a full CV. The `max_tokens=4096` setting gives it room to produce quality output.

**Port already in use** — change the port in `run.py`: `uvicorn.run(..., port=8001)`.
