# Feature Spec: Job Application Tracker
**Project:** cv-fit-studio (github.com/sowjanya-bn/cv_fit_engine)  
**Status:** Draft — ready to build  
**Scope:** New tab in the existing Studio UI, backed by Google Sheets  

---

## 1. Problem

You are generating tailored CVs and LaTeX files per role. There is currently no record of:
- Which jobs you applied to and when
- Which CV/TeX variant was used
- Where each application is in the pipeline
- What the JD said (so you can prep for interview without re-finding the posting)
- Patterns across rejections, silences, and advances

This feature closes that gap with zero new infrastructure — Google Sheets as the database, existing FastAPI backend as the proxy, new tab in the Studio UI.

---

## 2. Why Google Sheets (not SQLite)

| Factor | SQLite (local) | Google Sheets |
|---|---|---|
| Access on phone | No | Yes |
| Works across machines | No | Yes |
| Survives laptop wipe | No | Yes |
| Needs a running server | No | No (read anywhere) |
| Query / filter / sort | Python only | Native UI |
| Visualisation | Build it | Pivot tables, charts free |
| Shareable | Manual export | Link |
| Implementation complexity | Low | Low (one OAuth setup) |

The one-time cost is the Google OAuth setup. After that it's invisible.

---

## 3. Data Model

### Sheet: `Applications`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Auto-generated on entry |
| `date_applied` | ISO date | Auto-filled to today |
| `company` | string | Free text |
| `job_title` | string | Free text |
| `job_url` | string | Pasted link |
| `location` | string | e.g. Manchester, Remote |
| `contract_type` | enum | Permanent / Contract / FTC |
| `inside_ir35` | bool | Contract only |
| `day_rate_or_salary` | string | Free text (£540/day, £65k) |
| `source` | string | LinkedIn / Recruiter / Direct / Other |
| `recruiter_name` | string | Optional |
| `recruiter_contact` | string | Optional |
| `cv_variant` | string | Filename of .tex used, e.g. `CV_NagaSowjanya_JavaContract.tex` |
| `status` | enum | See Status Lifecycle below |
| `stage_detail` | string | Free text e.g. "1st stage booked 14 Jun" |
| `next_action` | string | Free text e.g. "Await feedback by Friday" |
| `next_action_date` | date | For sorting / chasing |
| `jd_text` | long string | Full JD pasted in |
| `notes` | long string | Interview prep, gut feel, questions asked |
| `outcome` | enum | Pending / Offer / Rejected / Withdrawn / Ghost |
| `offer_amount` | string | If offer received |
| `visa_sponsorship_needed` | bool | Flag for tracking |
| `last_updated` | ISO datetime | Auto-set on any edit |

### Status Lifecycle

```
Applied → CV Sent → 1st Interview → 2nd Interview → Final Round → Offer
                                                                 → Rejected
                         → Rejected (at any stage)
                         → Ghost (no response after N days)
         → Withdrawn (you pulled out)
```

### Sheet: `Archive`
Identical schema. Rows move here when `outcome` is set to Rejected / Withdrawn / Ghost. Keeps the main sheet clean.

---

## 4. UI — New Tab: "Applications"

Add a third tab to the existing Studio nav alongside "CV Builder" and "Job Search":

```
[ CV Builder ]  [ Job Search ]  [ Applications ]
```

### 4.1 Views

**Pipeline View (default)**  
Kanban-style columns — one per status. Each card shows: company, role, date applied, next action date. Click card → opens Detail Panel.

**Table View (toggle)**  
Flat list, sortable by date / company / status. Good for bulk review. Matches what's in the Sheet exactly.

**Stats Bar** (top of both views)  
```
Active: 12   |   Interviews: 3   |   Offers: 1   |   Response rate: 41%   |   Avg. to response: 8 days
```

### 4.2 Add Application Form

Triggered by "+ New Application" button. Two-panel layout:

**Left panel — Quick Entry**
```
Job URL          [                              ] [Fetch title?]
Company          [                    ]
Job Title        [                    ]
Location         [                    ]
Type             [ Permanent ▼ ]   IR35 [ ▼ ]
Salary / Rate    [                    ]
Source           [ LinkedIn ▼ ]
Recruiter        [                    ]
CV Used          [ dropdown of known .tex filenames ▼ ]
Status           [ Applied ▼ ]
Next action      [                    ]  by [date picker]
```

**Right panel — JD & Notes**
```
┌─ Job Description ──────────────────────────────┐
│  Paste the full JD here                        │
│                                                │
│                                                │
└────────────────────────────────────────────────┘

┌─ Notes / Interview Prep ───────────────────────┐
│  Free text. Populated later as you progress.   │
│                                                │
└────────────────────────────────────────────────┘
```

**Save** → writes row to Google Sheet, updates kanban card.

### 4.3 Detail Panel (slide-in)

Clicking any card opens a full detail view:
- All fields editable inline
- Status update dropdown with date stamp
- JD displayed in readable format (not raw paste)
- Notes section with running log (append, not replace)
- **"Prep with Claude" button** → sends JD + CV variant + current status to the main CV Builder tab, pre-prompting: *"I have a [stage] interview for this role. Help me prepare."*
- **"Update Status" button** → dropdown + optional note, writes back to Sheet instantly

### 4.4 Stale Applications Alert

Any application where `next_action_date` is in the past or `status` has not changed in 7+ days gets a subtle amber indicator on its kanban card. Not a notification — just a visual flag.

---

## 5. Backend — FastAPI Changes

### New file: `src/sheets.py`

Handles all Google Sheets I/O. Exposes functions used by the new route file.

```python
# src/sheets.py — interface
def get_all_applications() -> list[dict]
def add_application(data: dict) -> str          # returns new row id
def update_application(id: str, data: dict) -> bool
def archive_application(id: str) -> bool        # moves to Archive sheet
def get_stats() -> dict                         # response rate, avg days, counts
```

Uses `gspread` + `google-auth` libraries. Credentials stored in `credentials.json` (gitignored). Sheet ID stored in `.env` as `GOOGLE_SHEET_ID`.

### New file: `src/routes/tracker.py`

```
GET  /api/applications          → get_all_applications()
POST /api/applications          → add_application(body)
PUT  /api/applications/{id}     → update_application(id, body)
POST /api/applications/{id}/archive  → archive_application(id)
GET  /api/applications/stats    → get_stats()
```

Mounted in `app.py` alongside existing routes.

---

## 6. Google Sheets Setup (one-time)

Document this in `README_TRACKER.md` so it's reproducible:

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create project → enable **Google Sheets API** + **Google Drive API**
3. Create **Service Account** → download `credentials.json` → place in project root (already in `.gitignore`)
4. Create a new Google Sheet manually → copy the Sheet ID from the URL
5. Share the sheet with the service account email (Editor access)
6. Add to `.env`:
   ```
   GOOGLE_SHEET_ID=your_sheet_id_here
   ```
7. Run `python scripts/setup_sheet.py` → creates the `Applications` and `Archive` sheets with correct headers and a frozen header row

### `scripts/setup_sheet.py`
One-time script that:
- Connects to the sheet
- Creates `Applications` tab with all column headers
- Creates `Archive` tab with same headers
- Freezes row 1
- Applies basic column widths
- Adds data validation dropdowns for `status`, `contract_type`, `outcome` columns
- Writes a test row then deletes it (validates the connection works)

---

## 7. CV Variant Dropdown

The form needs to know which `.tex` files exist. Two options:

**Option A (simple):** Hardcode a list in `profile.js` alongside existing profile data:
```js
const CV_VARIANTS = [
  "CV_NagaSowjanya_AIDeveloper_v2.tex",
  "CV_NagaSowjanya_JavaContract.tex",
  "CV_NagaSowjanya_Sky.tex",
  // add as you go
];
```

**Option B (dynamic):** Backend scans a `cv_variants/` folder for `.tex` files and returns the list via `GET /api/cv-variants`. You drop new `.tex` files in that folder and the dropdown auto-populates.

**Recommendation:** Start with Option A (30 mins), migrate to B later when the variant list grows.

---

## 8. "Prep with Claude" Integration

When the user clicks **"Prep with Claude"** on a detail panel:

1. Pulls `jd_text`, `cv_variant` name, `status`, `stage_detail` from the current record
2. Switches to the CV Builder tab
3. Pre-fills the JD field with `jd_text`
4. Sets a context banner: *"Interview prep mode — [Company] [Role] — [Status]"*
5. Sends to Claude with a system prompt variant that shifts from CV generation to interview coaching:

```
You are helping prepare for a job interview.
Role: {job_title} at {company}
Current stage: {status} — {stage_detail}
CV used: {cv_variant}

The full job description follows. Help the candidate prepare:
- Likely technical questions based on the JD
- How their CV maps to the role's key requirements
- Questions they should ask the interviewer
- Any gaps they should be ready to address
```

This reuses the existing Claude proxy (`/api/claude`) with no new API spend — it's the same call, different prompt.

---

## 9. Build Plan

### Phase 1 — Data layer (half day)
- [ ] Add `gspread`, `google-auth` to `requirements.txt`
- [ ] Write `src/sheets.py` with all five functions
- [ ] Write `src/routes/tracker.py` with all five endpoints
- [ ] Write `scripts/setup_sheet.py`
- [ ] Add `GOOGLE_SHEET_ID` to `.env.example`
- [ ] Test all endpoints via curl / Postman

### Phase 2 — Table View UI (half day)
- [ ] Add "Applications" tab to nav in `index.html`
- [ ] Build flat table view — loads from `GET /api/applications`
- [ ] Add New Application form (left + right panel layout)
- [ ] Wire Save → `POST /api/applications`
- [ ] Wire inline status edit → `PUT /api/applications/{id}`
- [ ] Stats bar above table

### Phase 3 — Pipeline View (half day)
- [ ] Kanban column layout (CSS grid, one column per status)
- [ ] Cards with company / role / date / next-action date
- [ ] Amber stale indicator logic
- [ ] Toggle between Table and Pipeline views

### Phase 4 — Detail Panel + Prep Integration (half day)
- [ ] Slide-in detail panel
- [ ] All fields editable inline
- [ ] Notes append (not replace)
- [ ] "Prep with Claude" button wired to CV Builder tab
- [ ] Archive on terminal outcome

**Total estimate: 2 focused days**

---

## 10. What This Gives You

By the end of Phase 4:

- Every application has a permanent record with the exact JD and CV used
- You can prep for interviews in one click from the tracker
- You can see your pipeline at a glance — no mental overhead tracking stages
- The Sheet itself is a live artefact you can open on your phone between calls
- Over time: response rate data, time-to-feedback patterns, which CV variants are converting

This also quietly becomes another credibility bullet for the cv-fit-engine repo — a full-stack job intelligence system with Google Sheets integration, interview prep mode and pipeline analytics. GPT was right that the engine itself is evidence of the role identity. This makes it more so.
