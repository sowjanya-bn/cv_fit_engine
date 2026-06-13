# CV Fit Engine — Claude Code Spec

**For Claude Code. Read this entire document before touching any file. Implement phases in order. Each phase must be independently testable before moving to the next.**

---

## What this is

A truth-preserving CV fit engine. Not a resume prettifier. The product takes a CV and a job description, maps the employer's requirements to the candidate's existing evidence, rewrites bullets in the employer's language without inventing anything, scores the fit, and delivers a hiring-manager verdict.

The honesty guardrail is a structural constraint, not a prompt instruction. Every module that generates or rewrites content must classify its output into one of four evidence states before producing it:

| State | Meaning |
|---|---|
| `stated` | Candidate explicitly claims this in their CV |
| `inferred` | Reasonable inference from stated experience — flag to user |
| `missing` | No evidence found — surface as gap, do not rewrite around it |
| `unsupported` | The rewrite would overclaim — block it |

If a rewrite would require upgrading `missing` or `unsupported` evidence to `stated`, refuse the rewrite and flag the gap instead.

---

## Shared data model

All four modules read from and write to this shared object. Define it once in `src/cvfitengine/core/models.py` and import it everywhere.

```python
@dataclass
class Requirement:
    rank: int
    text: str
    importance: Literal["critical", "high", "medium"]
    evidence_state: Literal["stated", "inferred", "missing", "unsupported"]
    cv_evidence: str | None  # direct quote or None

@dataclass
class RewrittenBullet:
    original: str
    rewritten: str
    evidence_state: Literal["stated", "inferred"]  # never missing/unsupported
    flag: str | None  # warning note if inferred

@dataclass
class FitScore:
    keyword_match: int       # 0-100
    skills_match: int
    outcome_alignment: int
    role_fit: int
    seniority_fit: int
    recruiter_readability: int
    overall: int
    missing_high_priority: list[str]
    actions_to_80: list[str]

@dataclass
class HiringManagerVerdict:
    would_interview: bool
    reason: str
    biggest_doubt: str
    fix: str

@dataclass
class AlignmentMap:
    requirements: list[Requirement]
    clarifying_questions: list[str]   # max 3
    rewritten_bullets: list[RewrittenBullet]
    score: FitScore
    verdict: HiringManagerVerdict
```

---

## Codebase orientation

Before touching anything, read these files:

| File | Role |
|---|---|
| `src/app.py` | FastAPI backend. All API routes. |
| `src/cvfitengine/scoring/score.py` | `score_block()` and `rank_blocks()`. **Do not modify.** |
| `src/cvfitengine/parsing/jd_parser.py` | `parse_job(text)` → `JobSpec`. **Do not modify.** |
| `src/cvfitengine/scrapers/linkedin.py` | Playwright LinkedIn scraper. |
| `src/cvfitengine/scrapers/indeed.py` | Playwright Indeed scraper. |
| `src/cvfitengine/scrapers/base.py` | Abstract base. Browser lifecycle, stealth, delays. |
| `src/cvfitengine/apply/cover_letter.py` | Cover letter generation via Claude API. |
| `src/cvfitengine/apply/queue.py` | `ApplyQueue` — SQLite `apply_log` table. |
| `public/app.js` | All frontend logic (~1500 lines vanilla JS). |
| `public/index.html` | Single-page app shell. |
| `public/profile.js` | Sowjanya's profile data. **Do not modify.** |

**Do not modify:** `score.py`, `jd_parser.py`, `jd_classifier.py`, `tag_extractor.py`, `core/` (except adding `models.py`), `configs/`, `templates/`, `public/profile.js`.

---

## Phase 1 — Extraction module

**Goal:** Given a CV and a job description, extract the employer's language and map every requirement to the candidate's closest existing evidence. Surface gaps without judgment.

### Task 1-1 — Create `src/cvfitengine/alignment/extractor.py`

```python
def extract_requirements(cv_text: str, jd_text: str) -> list[Requirement]:
    """
    Call Claude API. Return requirements ranked by importance.
    For each requirement:
      - rank by position and frequency in JD (earlier + repeated = higher)
      - find closest evidence in CV
      - classify evidence_state honestly
      - never upgrade missing to stated
    Max 8 requirements. Return at least 3.
    """
```

The Claude prompt must instruct the model to return only JSON matching the `Requirement` schema. Strip markdown fences before parsing. If a field is ambiguous, classify conservatively (downgrade, never upgrade).

### Task 1-2 — New backend endpoint `POST /api/align/extract`

```python
class ExtractRequest(BaseModel):
    cv_text: str
    jd_text: str

class ExtractResponse(BaseModel):
    requirements: list[Requirement]

@app.post("/api/align/extract", response_model=ExtractResponse)
async def align_extract(req: ExtractRequest):
    requirements = extract_requirements(req.cv_text, req.jd_text)
    return ExtractResponse(requirements=requirements)
```

**Test:** POST a real CV + JD. Confirm `evidence_state` for a skill the CV clearly lacks is `"missing"`, not `"inferred"`.

---

## Phase 2 — Rewrite module

**Goal:** Rewrite CV bullets using the employer's language. Ask up to 3 clarifying questions only when evidence is genuinely ambiguous. Show before/after. Never rewrite a `missing` or `unsupported` bullet.

### Task 2-1 — Create `src/cvfitengine/alignment/rewriter.py`

```python
def generate_clarifying_questions(
    requirements: list[Requirement],
    cv_text: str
) -> list[str]:
    """
    Return at most 3 questions.
    Only ask about requirements where evidence_state == 'inferred'
    and a specific answer would change the rewrite materially.
    Never ask about 'missing' — that is a gap, not a clarification.
    """

def rewrite_bullets(
    cv_text: str,
    requirements: list[Requirement],
    clarifications: dict[str, str] | None = None
) -> list[RewrittenBullet]:
    """
    Rewrite bullets from cv_text that map to requirements with
    evidence_state in ('stated', 'inferred').
    Rules enforced in prompt AND validated post-generation:
      - max 20 words per bullet
      - must use employer's language from requirements
      - must not invent metrics not present in cv_text or clarifications
      - evidence_state of output bullet must be 'stated' or 'inferred' only
      - if rewrite would require fabrication, return original with flag
    """
```

Post-generation validation: after the model returns rewrites, check each against the original CV text. If the rewritten bullet contains a metric or claim with no basis in `cv_text` or `clarifications`, set `evidence_state = "unsupported"` and revert to original.

### Task 2-2 — New backend endpoint `POST /api/align/rewrite`

```python
class RewriteRequest(BaseModel):
    cv_text: str
    requirements: list[Requirement]
    clarifications: dict[str, str] = {}

class RewriteResponse(BaseModel):
    clarifying_questions: list[str]
    rewritten_bullets: list[RewrittenBullet]

@app.post("/api/align/rewrite", response_model=RewriteResponse)
async def align_rewrite(req: RewriteRequest):
    questions = generate_clarifying_questions(req.requirements, req.cv_text)
    bullets = rewrite_bullets(req.cv_text, req.requirements, req.clarifications)
    return RewriteResponse(clarifying_questions=questions, rewritten_bullets=bullets)
```

**Test:** Pass a requirement with `evidence_state = "missing"`. Confirm no rewritten bullet is returned for it — only a gap flag.

---

## Phase 3 — Scoring module

**Goal:** Score the CV against the JD across six dimensions. Produce a concrete list of actions to reach 80%. Do not inflate scores.

### Task 3-1 — Create `src/cvfitengine/alignment/scorer.py`

```python
def score_alignment(
    cv_text: str,
    jd_text: str,
    requirements: list[Requirement],
    rewritten_bullets: list[RewrittenBullet]
) -> FitScore:
    """
    Score six dimensions:
      keyword_match     — JD keywords present in CV (string matching, no LLM needed)
      skills_match      — technical skills coverage
      outcome_alignment — metrics and results language
      role_fit          — seniority, scope, sector match
      seniority_fit     — years and level signals
      recruiter_readability — ATS-friendliness, bullet clarity

    overall = weighted average (keyword_match 0.20, skills_match 0.25,
              outcome_alignment 0.20, role_fit 0.20, seniority_fit 0.10,
              recruiter_readability 0.05)

    missing_high_priority — requirements ranked 'critical' or 'high'
                            with evidence_state 'missing'

    actions_to_80 — concrete, specific steps. Not generic advice.
                    e.g. "Add 'stakeholder management' to your Senior PM
                    role bullet — it appears 4 times in the JD and is absent
                    from your CV"
    """
```

`keyword_match` must be computed locally (no API call) — tokenise both texts, compute overlap ratio. Use the existing `score_block()` from `score.py` as a reference for how scoring is already done in this codebase.

### Task 3-2 — New backend endpoint `POST /api/align/score`

```python
class ScoreRequest(BaseModel):
    cv_text: str
    jd_text: str
    requirements: list[Requirement]
    rewritten_bullets: list[RewrittenBullet]

@app.post("/api/align/score", response_model=FitScore)
async def align_score(req: ScoreRequest):
    return score_alignment(
        req.cv_text, req.jd_text,
        req.requirements, req.rewritten_bullets
    )
```

**Test:** Score a CV against a JD where the candidate's seniority is clearly mismatched. Confirm `seniority_fit` is below 50 and `actions_to_80` contains a specific seniority-related action, not a generic one.

---

## Phase 4 — Recruiter review module + full pipeline endpoint

**Goal:** Simulate a hiring manager's 10-second scan. Deliver a binary interview decision, the single biggest doubt, and a specific fix. Then wire all four modules into one endpoint.

### Task 4-1 — Create `src/cvfitengine/alignment/reviewer.py`

```python
def generate_verdict(
    cv_text: str,
    jd_text: str,
    score: FitScore,
    requirements: list[Requirement]
) -> HiringManagerVerdict:
    """
    Simulate a hiring manager reading the CV for 10 seconds.
    The prompt must instruct the model to:
      - make a binary yes/no interview decision
      - give the single biggest doubt (not a list)
      - give one specific fix (not generic advice)
      - base the verdict on the score and requirement gaps, not assumptions
    """
```

### Task 4-2 — Full pipeline endpoint `POST /api/align/full`

Wire all four modules sequentially. This is the primary endpoint the frontend will call.

```python
class FullAlignRequest(BaseModel):
    cv_text: str
    jd_text: str
    clarifications: dict[str, str] = {}

class FullAlignResponse(BaseModel):
    alignment_map: AlignmentMap

@app.post("/api/align/full", response_model=FullAlignResponse)
async def align_full(req: FullAlignRequest):
    # Module 1: extract
    requirements = extract_requirements(req.cv_text, req.jd_text)

    # Module 2: rewrite
    questions = generate_clarifying_questions(requirements, req.cv_text)
    bullets = rewrite_bullets(req.cv_text, requirements, req.clarifications)

    # Module 3: score
    score = score_alignment(req.cv_text, req.jd_text, requirements, bullets)

    # Module 4: review
    verdict = generate_verdict(req.cv_text, req.jd_text, score, requirements)

    return FullAlignResponse(
        alignment_map=AlignmentMap(
            requirements=requirements,
            clarifying_questions=questions,
            rewritten_bullets=bullets,
            score=score,
            verdict=verdict,
        )
    )
```

### Task 4-3 — Frontend integration

In `public/app.js`, add a new tab panel "Fit Analysis" that:

1. Shows a textarea for CV input and a textarea for JD input (or reuses pasted JD from the existing trigger panel — share the state, don't duplicate the UI)
2. On submit, calls `POST /api/align/full`
3. If `clarifying_questions` is non-empty, shows them as an interstitial form before rendering results — collect answers and resubmit with `clarifications` populated
4. Renders the full `AlignmentMap`:
   - Requirements table: rank | requirement | importance | evidence state badge | CV evidence
   - Before/after bullets (only for `stated` and `inferred` — gaps shown separately)
   - Six-dimension score breakdown with overall percentage
   - Missing high-priority terms as tags
   - Actions to 80% as a numbered list
   - Hiring manager verdict with interview decision, biggest doubt, fix

Evidence state badges: `stated` = green, `inferred` = amber with tooltip "based on inference — verify before interview", `missing` = red, `unsupported` = red with strikethrough.

In `public/index.html`, add the Fit Analysis tab to the nav alongside Role Strategy, Job Discovery, Shortlist, Tailor CV, Output.

**Test:** Run the full pipeline. Confirm the clarifying questions interstitial appears when questions are returned, and the re-submitted call includes `clarifications` in the request body.

---

## File map

### New files to create

| File | Purpose |
|---|---|
| `src/cvfitengine/core/models.py` | Shared data model — `Requirement`, `RewrittenBullet`, `FitScore`, `HiringManagerVerdict`, `AlignmentMap` |
| `src/cvfitengine/alignment/__init__.py` | Module init |
| `src/cvfitengine/alignment/extractor.py` | Phase 1 — extraction and mapping |
| `src/cvfitengine/alignment/rewriter.py` | Phase 2 — clarifying questions and bullet rewriter |
| `src/cvfitengine/alignment/scorer.py` | Phase 3 — six-dimension scoring |
| `src/cvfitengine/alignment/reviewer.py` | Phase 4 — hiring manager verdict |

### Files to extend

| File | Changes |
|---|---|
| `src/app.py` | Add four new endpoints: `/api/align/extract`, `/api/align/rewrite`, `/api/align/score`, `/api/align/full` |
| `public/app.js` | Add `Fit Analysis` tab logic, `renderAlignmentMap()`, clarifications interstitial |
| `public/index.html` | Add Fit Analysis tab to nav and panel |

### Files to leave untouched

- `src/cvfitengine/scoring/score.py`
- `src/cvfitengine/parsing/jd_parser.py`
- `src/cvfitengine/parsing/jd_classifier.py`
- `src/cvfitengine/parsing/tag_extractor.py`
- `src/cvfitengine/scrapers/` (all files)
- `src/cvfitengine/apply/` (all files)
- `configs/` (all files)
- `templates/` (all files)
- `public/profile.js`
- `data/` (all files)

---

## Verification scenarios

| Scenario | Expected behaviour |
|---|---|
| Skill clearly absent from CV | `evidence_state = "missing"`, no rewritten bullet produced |
| Metric in rewrite not in CV | `evidence_state = "unsupported"`, original bullet returned with flag |
| Inferred experience | `evidence_state = "inferred"`, rewrite produced, amber badge in UI |
| Clarifying questions returned | Interstitial form shown before results render |
| Clarifications submitted | Re-call includes `clarifications` dict, bullets improve |
| Seniority mismatch | `seniority_fit` < 50, `actions_to_80` contains seniority-specific action |
| All requirements met | `overall` score ≥ 75, `missing_high_priority` empty |
| Full pipeline | `POST /api/align/full` returns all four modules in one response |
| Frontend render | All four result sections render; badges colour-coded by evidence state |
| No hallucination | Rewritten bullets contain no metric absent from original CV text |
