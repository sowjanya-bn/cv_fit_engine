# CV Fit Engine — Enhancement Spec
**For Claude Code. Implement phases in order. Each phase is independently testable.**

---

## Codebase overview

Before touching anything, understand these files:

| File | Role |
|---|---|
| `src/app.py` | FastAPI backend. All API routes live here. |
| `src/cvfitengine/scrapers/linkedin.py` | Playwright LinkedIn scraper. `LinkedInScraper` class. |
| `src/cvfitengine/scrapers/indeed.py` | Playwright Indeed scraper. `IndeedScraper` class. |
| `src/cvfitengine/scrapers/base.py` | Abstract base. Handles browser lifecycle, stealth, delays. |
| `src/cvfitengine/scrapers/cache.py` | SQLite job cache at `~/.cvfit/jobs.db`. `JobCache` class. |
| `src/cvfitengine/apply/queue.py` | `ApplyQueue` — SQLite `apply_log` table. |
| `src/cvfitengine/apply/linkedin_apply.py` | LinkedIn Easy Apply automation. Never auto-submits. |
| `src/cvfitengine/apply/cover_letter.py` | Cover letter generation via Claude API. |
| `src/cvfitengine/scoring/score.py` | `score_block()` and `rank_blocks()`. Do not modify. |
| `src/cvfitengine/parsing/jd_parser.py` | `parse_job(text)` → `JobSpec`. Do not modify. |
| `public/app.js` | All frontend logic. ~1500 lines vanilla JS. |
| `public/index.html` | Single-page app shell. |
| `public/profile.js` | Sowjanya's profile data. Do not modify. |

**Do not modify** `score.py`, `jd_parser.py`, `jd_classifier.py`, `tag_extractor.py`, `core/`, `configs/`, or `templates/` unless explicitly told to.

---

## Phase 1 — Date filters for Playwright scrapers

**Goal:** LinkedIn and Indeed scrapers currently ignore recency. Reed and Adzuna already support `days_old`. Make LinkedIn and Indeed match.

### Task 1-1 — Add `days_old` to `ScraperRequest` in `app.py`

In `src/app.py`, find `ScraperRequest`:

```python
class ScraperRequest(BaseModel):
    source: str
    query: str
    location: str = "UK"
    max_results: int = 20
```

Add `days_old`:

```python
class ScraperRequest(BaseModel):
    source: str
    query: str
    location: str = "UK"
    max_results: int = 20
    days_old: int = 7  # 0 = any time
```

Then in `_run_scrape()`, pass `days_old` when constructing scrapers:

```python
if req.source in ("indeed", "both"):
    scraper = IndeedScraper(req.query, req.location, req.max_results, days_old=req.days_old)

if req.source in ("linkedin", "both"):
    scraper = LinkedInScraper(req.query, req.location, req.max_results, days_old=req.days_old)
```

### Task 1-2 — LinkedIn date filter

In `src/cvfitengine/scrapers/linkedin.py`:

Add `days_old: int = 7` to `__init__` and `super().__init__()`. Store as `self.days_old`.

In `_build_url()`, add the `f_TPR` param LinkedIn uses for recency:

```python
# LinkedIn f_TPR values:
# r86400   = past 24 hours
# r604800  = past week
# r2592000 = past month
_TPR_MAP = {
    1: "r86400",
    7: "r604800",
    30: "r2592000",
}

if self.days_old > 0:
    tpr = _TPR_MAP.get(self.days_old)
    if not tpr:
        # Default to week for anything between 1-7, month for anything above
        tpr = "r604800" if self.days_old <= 7 else "r2592000"
    params["f_TPR"] = tpr
```

### Task 1-3 — Indeed date filter

In `src/cvfitengine/scrapers/indeed.py`:

Add `days_old: int = 7` to `__init__` and `super().__init__()`. Store as `self.days_old`.

In `_build_url()`, add the `fromage` param Indeed uses for recency:

```python
params = {
    "q": self.query,
    "l": self.location,
    "start": start,
}
if self.days_old > 0:
    params["fromage"] = self.days_old  # Indeed accepts exact days
```

### Task 1-4 — Frontend passes `days_old`

In `public/app.js`, find `discoverJobsWithScrape()`. Find the `fetch("/api/jobs/scrape", ...)` call. It currently sends:

```js
body: JSON.stringify({ source: scrapeSource, query, location: loc || "UK", max_results: 20 })
```

Change to read the recency filter that already exists in the UI (`jobRecencyFilter`) and pass it:

```js
const daysOld = jobRecencyFilter === "week" ? 7 : jobRecencyFilter === "month" ? 30 : 0;
body: JSON.stringify({ source: scrapeSource, query, location: loc || "UK", max_results: 20, days_old: daysOld })
```

**Test:** Run a LinkedIn scrape with `days_old=1`. All returned jobs should have `posted_date` containing "hour" or "day".

---

## Phase 2 — JD paste → trigger flow

**Goal:** User pastes a raw JD anywhere in the app. Claude extracts role and keywords. Scrape runs. Results are scored. Best matches surface automatically.

### Task 2-1 — New backend endpoint `/api/jd/trigger`

Add to `src/app.py`:

```python
class JDTriggerRequest(BaseModel):
    jd_text: str
    location: str = "UK"
    source: str = "both"   # 'linkedin' | 'indeed' | 'both'
    days_old: int = 7
    max_results: int = 20

class JDTriggerResponse(BaseModel):
    scrape_job_id: str     # poll /api/jobs/scrape/{id}/status as normal
    extracted_title: str
    extracted_keywords: list[str]

@app.post("/api/jd/trigger", response_model=JDTriggerResponse)
async def jd_trigger(req: JDTriggerRequest, background_tasks: BackgroundTasks):
    """Parse a raw JD with Claude, extract role+keywords, kick off a scrape."""
    from cvfitengine.parsing.jd_parser import parse_job

    # Parse JD for keywords
    job_spec = parse_job(req.jd_text)
    query = job_spec.title or "software engineer"
    keywords = job_spec.keywords[:10]

    # Kick off scrape using extracted query
    scrape_req = ScraperRequest(
        source=req.source,
        query=query,
        location=req.location,
        max_results=req.max_results,
        days_old=req.days_old,
    )
    job_id = _make_scrape_id()   # reuse existing helper or use uuid4().hex[:8]
    _scrape_jobs[job_id] = {"status": "queued", "progress": 0, "total": 0, "results": []}
    background_tasks.add_task(_run_scrape, job_id, scrape_req)

    return JDTriggerResponse(
        scrape_job_id=job_id,
        extracted_title=query,
        extracted_keywords=keywords,
    )
```

Note: reuse the existing `_run_scrape` and `_scrape_jobs` dict already in `app.py`. Do not duplicate them.

### Task 2-2 — JD paste panel in frontend

In `public/index.html`, add a new panel inside the `discover` tab section, above the existing scrape controls:

```html
<div id="jd-trigger-panel" style="margin-bottom:1.5rem;padding:1rem;border:1px solid var(--border);border-radius:8px;background:var(--bg-card)">
  <div style="font-weight:600;font-size:13px;margin-bottom:.5rem">Paste a job description to find similar roles</div>
  <textarea id="jd-trigger-ta" rows="5" placeholder="Paste any job description here — Claude will extract the role and find matching jobs for you..." style="width:100%;font-size:12px;padding:.5rem;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);resize:vertical"></textarea>
  <div style="display:flex;gap:.5rem;margin-top:.5rem;align-items:center">
    <button class="btn btn-primary btn-sm" onclick="triggerFromJD()">Find similar jobs</button>
    <span id="jd-trigger-msg" style="font-size:12px;color:var(--muted)"></span>
  </div>
</div>
```

### Task 2-3 — `triggerFromJD()` function in `app.js`

Add to `public/app.js`:

```js
async function triggerFromJD() {
  const jd = document.getElementById("jd-trigger-ta").value.trim();
  const msg = document.getElementById("jd-trigger-msg");
  if (!jd) { msg.textContent = "Paste a JD first."; return; }

  const loc = document.getElementById("loc-pref")?.value || "UK";
  const useLI = document.getElementById("src-linkedin")?.checked;
  const useIndeed = document.getElementById("src-indeed")?.checked;
  const source = useLI && useIndeed ? "both" : useIndeed ? "indeed" : "linkedin";
  const daysOld = jobRecencyFilter === "week" ? 7 : jobRecencyFilter === "month" ? 30 : 0;

  msg.textContent = "Extracting role from JD...";

  try {
    const r = await fetch("/api/jd/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jd, location: loc, source, days_old: daysOld, max_results: 20 })
    });
    if (!r.ok) throw new Error(await r.text());
    const { scrape_job_id, extracted_title, extracted_keywords } = await r.json();

    msg.textContent = `Searching for "${extracted_title}" roles...`;

    // Reuse existing scrape polling logic — poll scrape_job_id status
    // then call renderDiscoveredJobs() when complete
    await _pollScrapeAndRender(scrape_job_id, msg);

  } catch (e) {
    msg.textContent = "Error: " + e.message;
  }
}
```

Extract the polling logic from the existing `discoverJobsWithScrape()` into a shared helper `_pollScrapeAndRender(job_id, msgEl)` that both functions call. Do not duplicate the polling loop.

**Test:** Paste a real JD. Confirm `extracted_title` is reasonable and scrape runs.

---

## Phase 3 — Dynamic apply flow

**Goal:** Replace the static apply button with a guided 3-step flow: generate cover letter → preview and edit → confirm submit.

### Task 3-1 — Cover letter preview with edit

The existing flow calls `/api/apply/generate-cover-letter` and immediately sends. Instead, show the result in an editable textarea before queuing.

In `public/app.js`, find the apply panel logic (around `applyPanelJobId`). After cover letter is generated, instead of immediately calling `/api/apply/queue`, show it in a panel:

```js
// After cover letter fetch:
document.getElementById("cl-preview-ta").value = generatedCoverLetter;
document.getElementById("cl-preview-panel").style.display = "";
document.getElementById("cl-generate-btn").style.display = "none";
document.getElementById("cl-confirm-btn").style.display = "";
```

Add to `public/index.html` inside the apply panel:

```html
<div id="cl-preview-panel" style="display:none;margin-top:1rem">
  <label style="font-size:12px;font-weight:600;color:var(--muted)">Cover letter — edit before sending</label>
  <textarea id="cl-preview-ta" rows="10" style="width:100%;font-size:12px;padding:.5rem;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);resize:vertical;margin-top:.25rem"></textarea>
  <div style="display:flex;gap:.5rem;margin-top:.5rem">
    <button id="cl-confirm-btn" class="btn btn-primary btn-sm" onclick="confirmApplyWithCL()" style="display:none">Confirm & queue application</button>
    <button class="btn btn-ghost btn-sm" onclick="regenerateCoverLetter()">Regenerate</button>
  </div>
</div>
```

### Task 3-2 — `confirmApplyWithCL()` uses edited text

```js
async function confirmApplyWithCL() {
  const editedCL = document.getElementById("cl-preview-ta").value.trim();
  // Pass editedCL as the cover_letter body to /api/apply/queue
  // instead of the originally generated text
}
```

### Task 3-3 — Application status in apply panel

After queuing, show live status in the apply panel. Poll `/api/apply/log` for the job_id and update a status badge every 3 seconds until status is `applied`, `failed`, or `skipped`.

---

## Phase 4 — Local folder tracker

**Goal:** Every application saves a folder of artifacts to disk. The applications tab becomes a proper tracker with pipeline stages and notes.

### Task 4-1 — Folder structure

On every successful queue (when `/api/apply/queue` is called), create:

```
~/.cvfit/applications/{YYYY-MM-DD}_{company}_{job_title_slug}/
  job_description.txt      ← the full JD text
  cover_letter.txt         ← the cover letter used
  cv_tailored.tex          ← LaTeX source if PDF was generated
  cv_tailored.pdf          ← PDF if generated (copy from temp)
  status.json              ← pipeline stage + timestamps + notes
```

`status.json` schema:

```json
{
  "job_id": "abc123",
  "company": "Acme Ltd",
  "job_title": "ML Engineer",
  "source": "linkedin",
  "apply_url": "https://...",
  "stage": "applied",
  "stages_log": [
    {"stage": "applied", "at": "2026-05-01T10:00:00"}
  ],
  "notes": "",
  "follow_up_due": null,
  "fit_score": 0.82,
  "skill_gaps": ["Kubernetes", "Terraform"]
}
```

Valid stages: `queued` → `applied` → `interview` → `offer` → `rejected` → `withdrawn`

### Task 4-2 — New backend routes for tracker

Add to `src/app.py`:

```python
APPLICATIONS_DIR = Path.home() / ".cvfit" / "applications"

@app.get("/api/tracker/list")
async def tracker_list():
    """List all application folders with their status.json."""

@app.patch("/api/tracker/{job_id}/stage")
async def tracker_update_stage(job_id: str, body: dict):
    """Update stage. body: {stage: str}"""

@app.patch("/api/tracker/{job_id}/notes")
async def tracker_update_notes(job_id: str, body: dict):
    """Update notes. body: {notes: str}"""

@app.patch("/api/tracker/{job_id}/follow_up")
async def tracker_follow_up(job_id: str, body: dict):
    """Set follow-up date. body: {follow_up_due: str | null}"""

@app.get("/api/tracker/{job_id}/files")
async def tracker_files(job_id: str):
    """Return list of files in the application folder."""

@app.get("/api/tracker/{job_id}/file/{filename}")
async def tracker_get_file(job_id: str, filename: str):
    """Return contents of a specific file (JD, cover letter, etc)."""
```

Implement `_save_application_folder(job: dict, cover_letter: str, jd_text: str, pdf_path: str | None)` and call it from the existing `/api/apply/queue` handler.

### Task 4-3 — Kanban board in applications tab

Replace the existing flat table in `public/index.html` (inside `#panel-applications`) with a Kanban board:

```html
<div id="kanban-board" style="display:flex;gap:1rem;overflow-x:auto;padding-bottom:1rem">
  <!-- One column per stage, rendered by JS -->
</div>
```

In `public/app.js`, replace `loadApplicationLog()` with `loadTracker()`:

- Fetch `/api/tracker/list`
- Group applications by `stage`
- Render one column per stage: Queued | Applied | Interview | Offer | Rejected | Withdrawn
- Each card shows: company, job title, fit score badge, date, follow-up flag
- Clicking a card opens a detail drawer with: JD text, cover letter, notes textarea (auto-saves on blur), stage dropdown, follow-up date picker, skill gaps list

### Task 4-4 — Tracker stats bar

Above the Kanban board, add a stats bar:

```html
<div id="tracker-stats" style="display:flex;gap:1.5rem;margin-bottom:1rem;font-size:12px;color:var(--muted)">
  <!-- Rendered by JS -->
</div>
```

Show: Total applied | This week | Response rate (interviews / applied) | Avg fit score

---

## File map — what to create and what to extend

### New files
- None required — all changes are extensions to existing files.

### Files to extend
- `src/app.py` — add `days_old` to `ScraperRequest`, add `/api/jd/trigger`, add `/api/tracker/*` routes, extend `/api/apply/queue` to save folder
- `src/cvfitengine/scrapers/linkedin.py` — add `days_old` param + `f_TPR` in `_build_url()`
- `src/cvfitengine/scrapers/indeed.py` — add `days_old` param + `fromage` in `_build_url()`
- `public/app.js` — add `triggerFromJD()`, `_pollScrapeAndRender()`, `confirmApplyWithCL()`, `loadTracker()`, Kanban render logic
- `public/index.html` — add JD trigger panel, cover letter preview panel, Kanban board, stats bar

### Files to leave untouched
- `src/cvfitengine/scoring/score.py`
- `src/cvfitengine/parsing/jd_parser.py`
- `src/cvfitengine/parsing/jd_classifier.py`
- `src/cvfitengine/parsing/tag_extractor.py`
- `src/cvfitengine/core/` (all files)
- `src/cvfitengine/apply/linkedin_apply.py`
- `src/cvfitengine/apply/cover_letter.py`
- `src/cvfitengine/apply/queue.py`
- `configs/` (all files)
- `templates/` (all files)
- `public/profile.js`
- `data/` (all files)

---

## Verify these scenarios before finishing

| Scenario | Expected behaviour |
|---|---|
| Scrape with `days_old=1` | LinkedIn URL contains `f_TPR=r86400`, Indeed URL contains `fromage=1` |
| Scrape with `days_old=0` | No date param added to either URL |
| Paste JD → trigger | `/api/jd/trigger` returns `extracted_title` matching the role in the JD |
| Apply flow | Cover letter appears in editable textarea before queue |
| Edit cover letter | Edited text (not original) is saved to `cover_letter.txt` in folder |
| Application folder | `~/.cvfit/applications/` has a new subfolder after queuing |
| `status.json` | Stage is `queued` on creation, updates to `applied` after confirm |
| Kanban | Applications grouped correctly by stage |
| Stage update | Drag or dropdown change calls PATCH and persists after page reload |
| Notes | Notes save on blur and persist after page reload |
| Stats bar | Response rate is 0% when no interviews, updates when stage changed to `interview` |
