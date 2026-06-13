# CV Fit Engine — Enhancement Spec

**Companion to CLAUDE_CODE_SPEC.md. These are post-review changes agreed across a three-way session (human, Claude, GPT). Implement after the base spec phases are complete. Phases 5 and 6 build directly on the AlignmentMap produced by Phase 4.**

---

## Enhancement 1 — BlockedRewrite as a first-class model

**Problem:** The original spec had `RewrittenBullet.evidence_state` typed as `Literal["stated", "inferred"]` but the post-generation validation set it to `"unsupported"` on failure — a type violation that would surface silently at runtime.

**Fix already applied to CLAUDE_CODE_SPEC.md.** Documented here for traceability.

`BlockedRewrite` is now a separate dataclass:

```python
@dataclass
class BlockedRewrite:
    original: str
    reason: Literal["missing_evidence", "unsupported_claim"]
    detail: str  # names the specific unsupported element
```

`rewrite_bullets()` returns `tuple[list[RewrittenBullet], list[BlockedRewrite]]`. `RewrittenBullet.evidence_state` is always `"stated"` or `"inferred"` — the type contract is clean and enforced. Nothing is silently dropped: every bullet either rewrites successfully or produces a `BlockedRewrite` with an explanation.

`AlignmentMap` carries both lists:

```python
rewritten_bullets: list[RewrittenBullet]
blocked_rewrites: list[BlockedRewrite]
```

Frontend renders blocked rewrites as a gap list separate from the before/after bullet section.

---

## Enhancement 2 — Remediation layer evidence gating

**Problem:** The `actions_to_80` field in `FitScore` was generating highly specific suggested bullets with invented metrics (team sizes, percentages, API counts) that had no basis in the CV. This made the remediation module a hallucination layer — the exact thing the honesty guardrail exists to prevent.

**Fix already applied to CLAUDE_CODE_SPEC.md.** Documented here for traceability.

`actions_to_80: list[str]` replaced with two typed fields:

```python
safe_edits: list[str]      # reframings of evidence already in the CV
evidence_needed: list[str] # gaps the candidate must address with real experience
```

**Constraint on `safe_edits`:** every word must be traceable to `cv_text`. No invented numbers, team sizes, percentages, tool names, or outcomes. If the suggestion cannot be written without inventing a detail, it is not a safe edit — it goes to `evidence_needed`.

**Constraint on `evidence_needed`:** framed as a candidate question or honest gap disclosure, never as a ready-to-paste bullet. The product distinguishes between a presentation problem (safe edit) and an experience problem (evidence needed). It does not paper over the difference.

Scorer prompt must enforce both constraints explicitly. Verification: no number appearing in `safe_edits` should be absent from the original `cv_text`.

---

## Enhancement 3 (Phase 5) — Fit-to-tailor handoff

**Goal:** When the candidate reviews the alignment map and decides to apply, the Fit Analysis tab offers a "Tailor CV for this role" action. This pre-populates the existing Tailor CV tab with the alignment map as structured input, so the CV generation is grounded in the evidence states already computed — not starting from scratch.

### Task 5-1 — "Tailor for this role" action in Fit Analysis tab

In `public/app.js`, after the full `AlignmentMap` renders, show a decision prompt below the hiring manager verdict:

```
[Tailor CV for this role →]   [Not a good fit — back to search]
```

The "Tailor CV" button does not navigate away immediately. It first shows an interstitial checklist if `score.evidence_needed` is non-empty:

```
Before we tailor your CV, confirm or provide the following:

□ [evidence_needed item 1]   [text input for candidate answer]
□ [evidence_needed item 2]   [text input for candidate answer]

[Continue with what I have]   [I've answered the above — tailor now]
```

"Continue with what I have" proceeds with `evidence_needed` items unanswered — those gaps will be omitted from the tailored CV rather than fabricated. "Tailor now" collects the answers and passes them as `confirmed_evidence: dict[str, str]` to the tailor endpoint.

### Task 5-2 — New backend endpoint `POST /api/align/tailor`

```python
class TailorRequest(BaseModel):
    cv_text: str
    jd_text: str
    alignment_map: AlignmentMap
    confirmed_evidence: dict[str, str] = {}  # candidate answers to evidence_needed items

class TailorResponse(BaseModel):
    tailored_cv: str        # full CV text with rewritten bullets applied
    change_log: list[str]   # one line per change: "Replaced X with Y (stated)"
    omitted_gaps: list[str] # evidence_needed items the candidate did not confirm — omitted, not fabricated

@app.post("/api/align/tailor", response_model=TailorResponse)
async def align_tailor(req: TailorRequest):
    """
    Generate a tailored CV from the alignment map.
    Rules:
      - Apply all RewrittenBullet entries (stated and inferred) from alignment_map
      - Apply safe_edits as reframings
      - If confirmed_evidence is provided, incorporate those answers as stated evidence
      - Never apply a BlockedRewrite — those gaps are listed in omitted_gaps
      - Never fabricate. If a gap has no confirmed evidence, omit it from the CV
        and add it to omitted_gaps — do not invent a bullet to fill it
      - Return a full CV text and a change_log so the candidate can audit every edit
    """
```

### Task 5-3 — Change log and omission transparency in Output tab

In `public/app.js`, when the tailored CV is generated from an alignment map (as opposed to a free-form tailor), the Output tab shows two additional sections before the CV preview:

**Changes made** — the `change_log` as a numbered list. Each entry shows what was changed, the original text, and the evidence state that permitted the change.

**Gaps omitted** — the `omitted_gaps` list. Framed honestly: "The following requirements had no confirmed evidence and were not added to your CV. Address these before applying or accept them as gaps." This is not a failure state — it is the product being honest about what it cannot do.

The candidate can download the tailored CV with or without a gap summary appended.

### Task 5-4 — Wire safe_edits into tailor generation

The tailor prompt must apply `safe_edits` as surface reframings — swapping in JD language where the underlying claim is identical. These are lower-risk than bullet rewrites and should be applied automatically, logged in `change_log` with `(safe edit)` annotation.

---

## File map additions for Enhancement 3

### New files

| File | Purpose |
|---|---|
| `src/cvfitengine/alignment/tailor.py` | Phase 5 — fit-to-tailor CV generation |

### Files to extend

| File | Changes |
|---|---|
| `src/app.py` | Add `POST /api/align/tailor` |
| `public/app.js` | Add evidence_needed interstitial, "Tailor CV" handoff button, change log and omission sections in Output tab |
| `public/index.html` | Add evidence_needed interstitial panel, change log and omissions panel in Output tab |

### Files to leave untouched

Everything in the base spec untouched list remains untouched.

---

## Verification scenarios for Enhancement 3

| Scenario | Expected behaviour |
|---|---|
| All evidence stated | Tailored CV applies all rewrites; `omitted_gaps` empty; `change_log` lists every edit |
| Gap with no confirmed evidence | Gap omitted from CV; added to `omitted_gaps`; no fabricated bullet |
| Candidate confirms evidence_needed item | Answer incorporated as stated evidence; bullet written; logged in `change_log` with `(confirmed)` |
| Candidate clicks "Continue with what I have" | `confirmed_evidence` empty; all `evidence_needed` items appear in `omitted_gaps` |
| Safe edit applied | JD language substituted where underlying claim is identical; logged as `(safe edit)` |
| BlockedRewrite in alignment map | Never appears in tailored CV; appears in `omitted_gaps` with original `BlockedRewrite.detail` |
| Download with gap summary | CV text plus honest gap list appended; candidate can audit every omission |

---

## Summary of all changes from base spec

| Change | Where | Status |
|---|---|---|
| `BlockedRewrite` as first-class model | `models.py`, `rewriter.py`, `AlignmentMap` | Applied to CLAUDE_CODE_SPEC.md |
| `rewrite_bullets()` returns tuple | `rewriter.py` | Applied to CLAUDE_CODE_SPEC.md |
| `actions_to_80` replaced with `safe_edits` + `evidence_needed` | `models.py`, `scorer.py` | Applied to CLAUDE_CODE_SPEC.md |
| Scorer prompt constraint on safe_edits | `scorer.py` docstring | Applied to CLAUDE_CODE_SPEC.md |
| Phase 5 fit-to-tailor handoff | `tailor.py`, `app.py`, frontend | This document |
