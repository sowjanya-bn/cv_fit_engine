/**
 * app.js — CV Fit Studio client logic
 * Calls /api/claude (local FastAPI proxy) instead of Anthropic directly.
 * API key never touches the browser.
 */

// ── state ──────────────────────────────────────────────────────
let activeTrack = ROLES[0];
let shortlist = [];
let discoveredJobs = [];
let activeJob = null;
let lastOutput = null;

// ── init ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderRoleCards();
  renderTrackPills();
  renderLiveTrackPills();
  checkHealth();
  loadShortlistFromServer();
  // Pre-load resume YAML so scoring works without visiting Tailor tab
  fetch("/api/resume-yaml").then(r => r.ok ? r.text() : null).then(t => {
    if (t) window._resumeYamlCache = t;
  }).catch(() => {});
});

// ── tab routing ────────────────────────────────────────────────
function switchTab(t) {
  const tabs = ["strategy", "live", "discover", "shortlist", "tailor", "output", "applications", "settings"];
  tabs.forEach(k => {
    document.getElementById("panel-" + k).classList.toggle("active", k === t);
    document.getElementById("nav-" + k).classList.toggle("active", k === t);
  });
  if (t === "shortlist") renderShortlist();
  if (t === "tailor") populateTailorSelect();
  if (t === "applications") loadTracker();
  if (t === "output" && !lastOutput) {
    document.getElementById("out-empty").style.display = "";
    document.getElementById("out-area").style.display = "none";
  }
}

// ── health / settings ──────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    const d = await r.json();
    const el = document.getElementById("key-indicator");
    const box = document.getElementById("key-status-box");
    if (d.api_key_set) {
      el.textContent = "✓ API key set";
      el.style.color = "#6ee7b7";
      if (box) { box.className = "alert alert-ok"; box.textContent = "API key found in environment. You're good to go."; box.style.display = ""; }
    } else {
      el.textContent = "✗ No API key";
      el.style.color = "#fca5a5";
      if (box) { box.className = "alert alert-err"; box.textContent = "ANTHROPIC_API_KEY not set. Set it as an environment variable and restart the server."; box.style.display = ""; }
    }
  } catch (e) {
    const el = document.getElementById("key-indicator");
    if (el) el.textContent = "Server not running?";
  }
}

// ── Claude proxy call ──────────────────────────────────────────
async function callClaude(system, user, maxTokens = 4096) {
  const r = await fetch("/api/claude", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ system, user, max_tokens: maxTokens })
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || "API error");
  }
  const d = await r.json();
  return d.text;
}

function parseJSON(raw) {
  let s = raw.replace(/```json|```/g, "").trim();
  const a = s.indexOf("{"), b = s.lastIndexOf("}");
  if (a !== -1 && b !== -1) s = s.slice(a, b + 1);
  return JSON.parse(s);
}

// ── role strategy ──────────────────────────────────────────────
function renderRoleCards() {
  const c = document.getElementById("role-cards");
  c.innerHTML = "";
  ROLES.forEach(r => {
    const fc = r.fit >= 80 ? "fill-hi" : r.fit >= 65 ? "fill-mid" : "fill-lo";
    const d = document.createElement("div");
    d.className = "role-card" + (r.id === activeTrack.id ? " selected" : "");
    d.innerHTML = `
      <div class="rc-title">${r.label}</div>
      <span class="badge ${r.fitClass}" style="margin-bottom:6px">${r.fitLabel}</span>
      <div class="score-bar"><div class="score-fill ${fc}" style="width:${r.fit}%"></div></div>
      <div style="font-size:11px;color:var(--hint);margin-top:5px">${r.fit}% profile match</div>`;
    d.onclick = () => selectRole(r, d);
    c.appendChild(d);
  });
  showRoleDetail(activeTrack);
}

function selectRole(r, el) {
  activeTrack = r;
  document.querySelectorAll(".role-card").forEach(c => c.classList.remove("selected"));
  el.classList.add("selected");
  showRoleDetail(r);
  renderTrackPills();
}

function showRoleDetail(r) {
  document.getElementById("role-detail").style.display = "block";
  document.getElementById("role-detail-content").innerHTML = `
    <div style="font-size:15px;font-weight:600;color:var(--navy);margin-bottom:.6rem">${r.label}</div>
    <div class="insight ok" style="margin-bottom:.75rem">${r.pitch}</div>
    <div class="grid2">
      <div>
        <label class="lbl" style="margin-bottom:4px">Key skills to highlight</label>
        <div class="tag-row">${r.keySkills.map(s => `<span class="tag match">${s}</span>`).join("")}</div>
      </div>
      <div>
        <label class="lbl" style="margin-bottom:4px">Target employers</label>
        <div style="font-size:12px;color:var(--muted);line-height:1.6">${r.companies}</div>
      </div>
    </div>
    <div style="margin-top:.75rem">
      <label class="lbl" style="margin-bottom:6px">Search under these job titles (${(r.searchTitles||[]).length} variants)</label>
      <div class="tag-row">${(r.searchTitles || []).map(t => `<span class="tag" style="font-size:11px">${t}</span>`).join("")}</div>
      <div style="font-size:11px;color:var(--hint);margin-top:6px">Use these exact titles on LinkedIn, Indeed, jobs.ac.uk, and company career pages.</div>
    </div>`;
}

// ── discover ───────────────────────────────────────────────────
function renderTrackPills() {
  const c = document.getElementById("track-pills");
  if (!c) return;
  c.innerHTML = ROLES.map(r =>
    `<span class="pill${r.id === activeTrack.id ? " active" : ""}" onclick="setTrack('${r.id}',this)">${r.label.split("/")[0].trim()}</span>`
  ).join("");
  fillAdditionalContext();
}

function setTrack(id, el) {
  activeTrack = ROLES.find(r => r.id === id);
  document.querySelectorAll("#track-pills .pill").forEach(p => p.classList.remove("active"));
  el.classList.add("active");
  fillAdditionalContext();
}

function fillAdditionalContext() {
  const el = document.getElementById("extra-ctx");
  if (el && activeTrack.additionalContext) {
    el.value = activeTrack.additionalContext;
  }
}

async function discoverJobs(mergeMode = false) {
  const loc = document.getElementById("loc-pref").value;
  const co = document.getElementById("co-type").value;
  const extra = document.getElementById("extra-ctx").value;
  const loadEl = document.getElementById("disc-loading");
  const errEl = document.getElementById("disc-error");

  loadEl.style.display = "flex";
  document.getElementById("disc-msg").textContent = `Finding ${activeTrack.label} roles...`;
  errEl.style.display = "none";
  document.getElementById("disc-results").style.display = "none";

  const titles = (activeTrack.searchTitles || [activeTrack.label]).join(", ");
  const sys = `You are a specialist tech recruiter for AI/ML/semantic web roles in the UK. Generate 8 realistic job listings matching the candidate profile. Return ONLY valid JSON — no markdown, no preamble.

Candidate: Naga Sowjanya Barla. Key credentials: MSc Data Science & AI (Univ. Liverpool 2026), 13 years backend engineering (TCS), Python/Java/RDF/SPARQL/RAG/LLMs. Based in Liverpool UK.

IMPORTANT: Use realistic job titles from this list for this track — these are the actual titles companies post: ${titles}. Vary them across the 8 results rather than repeating one title.

Return JSON:
{ "jobs": [ {
  "id": "j1",
  "title": "",
  "company": "",
  "location": "",
  "type": "Full-time|Contract|Hybrid|Remote",
  "salary": "£XXk-£XXk",
  "fit_score": 0-100,
  "fit_reason": "2 sentence explanation specific to Sowjanya's actual credentials",
  "jd_summary": "3-4 sentence realistic JD",
  "key_requirements": [],
  "tags": [],
  "notable": "one concrete thing that makes this role especially interesting for her",
  "why_apply": "1 sentence on what angle of her profile to lead with for this specific role"
} ] }

Make companies realistic and varied — mix startups, scale-ups, enterprises, research orgs. UK-focused. fit_score must be honest not flattering.`;

  try {
    const raw = await callClaude(sys,
      `Role track: ${activeTrack.label}\nKey skills: ${activeTrack.keySkills.join(", ")}\nLocation: ${loc}\nCompany type: ${co}\nCandidate context: ${extra}`
    );
    const data = parseJSON(raw);
    const claudeJobs = data.jobs || [];
    if (mergeMode) {
      // Merge: add Claude-generated jobs not already in discoveredJobs
      const existingIds = new Set(discoveredJobs.map(j => j.id));
      discoveredJobs = discoveredJobs.concat(claudeJobs.filter(j => !existingIds.has(j.id)));
    } else {
      discoveredJobs = claudeJobs;
    }
    renderJobCards();
    document.getElementById("disc-results").style.display = "block";
    document.getElementById("disc-title").textContent = `${discoveredJobs.length} ${activeTrack.label} roles found`;
  } catch (e) {
    errEl.textContent = "Search failed: " + e.message;
    errEl.style.display = "block";
  } finally {
    loadEl.style.display = "none";
  }
}

let jobSortMode = "score"; // 'score' | 'date' | 'salary'
let jobRecencyFilter = "all"; // 'all' | 'week'

// Parse LinkedIn relative date strings → days ago (Infinity = unknown)
function _relativeTodays(str) {
  if (!str) return Infinity;
  const s = str.toLowerCase().trim();
  if (/just now|today|hour|minute/.test(s)) return 0;
  const days = s.match(/(\d+)\s*day/);
  if (days) return parseInt(days[1]);
  const weeks = s.match(/(\d+)\s*week/);
  if (weeks) return parseInt(weeks[1]) * 7;
  const months = s.match(/(\d+)\s*month/);
  if (months) return parseInt(months[1]) * 30;
  // ISO date string e.g. "2025-04-15"
  const iso = s.match(/(\d{4}-\d{2}-\d{2})/);
  if (iso) return Math.floor((Date.now() - new Date(iso[1])) / 86400000);
  return Infinity;
}

function renderJobCards() {
  const c = document.getElementById("job-cards");
  c.innerHTML = "";
  const slIds = new Set(shortlist.map(j => j.id));

  let jobs = [...discoveredJobs];

  // Recency filter
  if (jobRecencyFilter === "week") {
    jobs = jobs.filter(j => _relativeTodays(j.posted_date || j.posted) <= 7);
  }

  if (jobSortMode === "score") {
    jobs.sort((a, b) => (b.fit_score || 0) - (a.fit_score || 0));
  } else if (jobSortMode === "date") {
    jobs.sort((a, b) => _relativeTodays(a.posted_date || a.posted) - _relativeTodays(b.posted_date || b.posted));
  } else if (jobSortMode === "salary") {
    jobs.sort((a, b) => _parseSalary(b) - _parseSalary(a));
  }

  // Controls row
  const ctrl = document.createElement("div");
  ctrl.style = "display:flex;gap:8px;align-items:center;margin-bottom:.75rem;flex-wrap:wrap";
  ctrl.innerHTML = `
    <span style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em">Sort:</span>
    ${["score","date","salary"].map(m =>
      `<button class="btn btn-sm${jobSortMode===m?" btn-primary":""}" onclick="setJobSort('${m}')">${m==="score"?"Fit score":m==="date"?"Newest":"Salary"}</button>`
    ).join("")}
    <span style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-left:4px">Filter:</span>
    <button class="btn btn-sm${jobRecencyFilter==="all"?" btn-primary":""}" onclick="setJobRecency('all')">All</button>
    <button class="btn btn-sm${jobRecencyFilter==="week"?" btn-primary":""}" onclick="setJobRecency('week')">≤ 1 week</button>
    <span style="font-size:11px;color:var(--hint);margin-left:auto">${jobs.length} shown</span>
  `;
  c.appendChild(ctrl);

  if (!jobs.length) {
    const empty = document.createElement("div");
    empty.style = "color:var(--muted);font-size:13px;padding:1.5rem 0;text-align:center";
    empty.textContent = jobRecencyFilter === "week"
      ? "No jobs posted within the last week. Try removing the filter."
      : "No jobs found.";
    c.appendChild(empty);
    return;
  }

  jobs.forEach(job => {
    // Normalize score — backend returns 0-1, Claude returns 0-100
    const rawScore = job.fit_score || 0;
    const s = rawScore <= 1 ? Math.round(rawScore * 100) : rawScore;
    const bc = s >= 70 ? "badge-green" : s >= 50 ? "badge-amber" : "badge-muted";
    const fc = s >= 70 ? "fill-hi" : s >= 50 ? "fill-mid" : "fill-lo";

    const matchedSkills = (job.matched_skills || []).slice(0, 5);
    const missingSkills = (job.missing_skills || []).slice(0, 3);
    const salary = job.salary_raw || job.salary || "";
    const postedDate = job.posted_date || job.posted || "";
    const scoreBadge = s > 0
      ? `<span class="badge ${bc}">${s}% fit</span>`
      : `<span class="badge badge-muted" style="opacity:.6">unscored</span>`;
    const dateBadge = postedDate
      ? `<span style="font-size:11px;color:var(--hint)">📅 ${postedDate}</span>`
      : `<span style="font-size:11px;color:var(--hint);opacity:.5">date unknown</span>`;

    const d = document.createElement("div");
    d.className = "job-card" + (slIds.has(job.id) ? " selected" : "");
    d.innerHTML = `
      <div class="jc-check">✓</div>
      <div style="font-size:14px;font-weight:600;margin-bottom:2px">${job.title}</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px">${job.company} · ${job.location || ""}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        ${scoreBadge}
        ${dateBadge}
        ${salary ? `<span style="font-size:12px;color:var(--teal);font-weight:500">${salary}</span>` : ""}
        <span class="badge badge-muted">${job.type || job.employment_type || ""}</span>
      </div>
      <div class="score-bar"><div class="score-fill ${fc}" style="width:${s}%"></div></div>
      ${job.fit_reason ? `<div style="font-size:12px;color:var(--muted);margin-top:6px;line-height:1.5">${job.fit_reason}</div>` : ""}
      ${job.notable ? `<div style="font-size:11px;color:var(--navy);margin-top:6px;padding:4px 8px;background:var(--navy-light);border-radius:4px">${job.notable}</div>` : ""}
      ${job.why_apply ? `<div style="font-size:11px;color:var(--teal);margin-top:4px;padding:4px 8px;background:var(--teal-light);border-radius:4px">Lead with: ${job.why_apply}</div>` : ""}
      ${matchedSkills.length ? `<div class="tag-row">${matchedSkills.map(t=>`<span class="tag match">${t}</span>`).join("")}</div>` : ""}
      ${missingSkills.length ? `<div class="tag-row">${missingSkills.map(t=>`<span class="tag gap">${t}</span>`).join("")}</div>` : ""}
      ${(job.tags||[]).length ? `<div class="tag-row">${(job.tags||[]).slice(0,6).map(t=>`<span class="tag">${t}</span>`).join("")}</div>` : ""}
      <div style="display:flex;gap:6px;margin-top:8px">
        <button class="btn btn-sm" onclick="event.stopPropagation();openApplyPanel('${job.id}')">Apply →</button>
      </div>
    `;
    d.onclick = () => toggleShortlist(job, d);
    c.appendChild(d);
  });
}

function setJobSort(mode) {
  jobSortMode = mode;
  renderJobCards();
}

function setJobRecency(filter) {
  jobRecencyFilter = filter;
  renderJobCards();
}

function _parseSalary(job) {
  const s = job.salary_raw || job.salary || "";
  const m = s.match(/[\d,]+/);
  return m ? parseInt(m[0].replace(/,/g,"")) : 0;
}

// ── shortlist (categorical) ────────────────────────────────────

const BUCKETS = [
  { key: "dream-aligned",        label: "Dream-Aligned",        color: "#22c55e" },
  { key: "status-unlock",        label: "Status-Unlock (KTP)",  color: "#a78bfa" },
  { key: "sponsor-safe-bridge",  label: "Sponsor-Safe Bridge",  color: "#60a5fa" },
  { key: "tactical-only",        label: "Tactical-Only",        color: "#f59e0b" },
];

const SPONSOR_LABELS = {
  "licensed":     { text: "✓ Licensed sponsor", color: "#22c55e" },
  "not_licensed": { text: "✗ Not on register",  color: "#ef4444" },
  "unknown":      { text: "? Sponsor unknown",  color: "#f59e0b" },
};

// In-memory mirror of server state (bucket → job[])
let categorisedShortlist = { "dream-aligned": [], "status-unlock": [], "sponsor-safe-bridge": [], "tactical-only": [] };

async function toggleShortlist(job, el) {
  const allJobs = Object.values(categorisedShortlist).flat();
  const existing = allJobs.find(j => j.id === job.id);

  if (existing) {
    // Remove
    const bucket = existing.bucket || "dream-aligned";
    await fetch(`/api/shortlist/remove?job_id=${encodeURIComponent(job.id)}&bucket=${encodeURIComponent(bucket)}`, { method: "DELETE" });
    categorisedShortlist[bucket] = categorisedShortlist[bucket].filter(j => j.id !== job.id);
    el.classList.remove("selected");
  } else {
    // Show bucket picker before saving
    const bucket = await pickBucket(job);
    if (!bucket) return; // user cancelled
    const sponsor_status = await checkSponsor(job.company);
    await fetch("/api/shortlist/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job, bucket, sponsor_status }),
    });
    categorisedShortlist[bucket].push({ ...job, bucket, sponsor_status });
    el.classList.add("selected");
  }
  updateSlBadge();
  renderShortlist();
}

async function checkSponsor(companyName) {
  if (!companyName) return "unknown";
  try {
    const r = await fetch("/api/sponsor/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_name: companyName }),
    });
    const d = await r.json();
    return d.sponsor_status || "unknown";
  } catch { return "unknown"; }
}

function pickBucket(job) {
  return new Promise(resolve => {
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center";
    const box = document.createElement("div");
    box.style.cssText = "background:var(--surface);border-radius:12px;padding:24px;max-width:400px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.4)";
    box.innerHTML = `
      <div style="font-weight:600;font-size:15px;margin-bottom:4px">Save to shortlist</div>
      <div style="color:var(--muted);font-size:13px;margin-bottom:16px">${job.title} @ ${job.company}</div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:10px">Which bucket does this role belong to?</div>
      ${BUCKETS.map(b => `
        <button data-bucket="${b.key}" style="display:block;width:100%;text-align:left;padding:10px 14px;margin-bottom:8px;border-radius:8px;border:1px solid var(--border);background:var(--surface);cursor:pointer;font-size:13px">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${b.color};margin-right:8px"></span>
          ${b.label}
        </button>`).join("")}
      <button id="sl-cancel" style="width:100%;padding:8px;margin-top:4px;border-radius:8px;border:1px solid var(--border);background:transparent;cursor:pointer;color:var(--muted);font-size:13px">Cancel</button>`;
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    box.querySelectorAll("[data-bucket]").forEach(btn => {
      btn.addEventListener("click", () => { document.body.removeChild(overlay); resolve(btn.dataset.bucket); });
    });
    document.getElementById("sl-cancel").addEventListener("click", () => { document.body.removeChild(overlay); resolve(null); });
  });
}

function updateSlBadge() {
  const total = Object.values(categorisedShortlist).reduce((n, arr) => n + arr.length, 0);
  const b = document.getElementById("sl-badge");
  if (total) { b.textContent = total; b.style.display = ""; }
  else b.style.display = "none";
  // Keep flat shortlist in sync for tailor tab compatibility
  shortlist = Object.values(categorisedShortlist).flat();
}

async function clearShortlist() {
  categorisedShortlist = { "dream-aligned": [], "status-unlock": [], "sponsor-safe-bridge": [], "tactical-only": [] };
  shortlist = [];
  updateSlBadge();
  renderShortlist();
  renderJobCards();
}

async function loadShortlistFromServer() {
  try {
    const r = await fetch("/api/shortlist");
    const d = await r.json();
    if (d.buckets) {
      categorisedShortlist = d.buckets;
      shortlist = Object.values(categorisedShortlist).flat();
      updateSlBadge();
    }
  } catch { /* server not ready yet, use empty state */ }
}

function renderShortlist() {
  const c = document.getElementById("sl-cards");
  const emp = document.getElementById("sl-empty");
  const act = document.getElementById("sl-actions");
  c.innerHTML = "";
  const total = Object.values(categorisedShortlist).reduce((n, arr) => n + arr.length, 0);
  if (!total) { emp.style.display = ""; act.style.display = "none"; return; }
  emp.style.display = "none"; act.style.display = "flex";

  BUCKETS.forEach(bucket => {
    const jobs = categorisedShortlist[bucket.key] || [];
    if (!jobs.length) return;

    // Bucket header
    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;gap:8px;margin:16px 0 8px";
    header.innerHTML = `
      <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${bucket.color}"></span>
      <span style="font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)">${bucket.label}</span>
      <span style="font-size:12px;color:var(--muted)">(${jobs.length})</span>`;
    c.appendChild(header);

    jobs.forEach(job => {
      const s = job.fit_score || 0;
      const bc = s >= 80 ? "badge-green" : s >= 65 ? "badge-amber" : "badge-muted";
      const sp = job.sponsor_status || "unknown";
      const spInfo = SPONSOR_LABELS[sp] || SPONSOR_LABELS["unknown"];
      const d = document.createElement("div");
      d.className = "card";
      d.innerHTML = `
        <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:6px">
          <div style="flex:1">
            <div class="card-title">${job.title}</div>
            <div class="card-sub">${job.company} · ${job.location} · ${job.salary || ""}</div>
            <div style="font-size:11px;margin-top:3px;color:${spInfo.color}">${spInfo.text}</div>
          </div>
          <span class="badge ${bc}">${s}% fit</span>
          <button class="btn btn-sm btn-primary" onclick="tailorJob('${job.id}')">Tailor →</button>
        </div>
        <div style="font-size:12px;line-height:1.6;color:var(--muted)">${job.jd_summary || ""}</div>
        <div class="tag-row">${(job.tags || []).map(t => `<span class="tag">${t}</span>`).join("")}</div>`;
      c.appendChild(d);
    });
  });
}

function tailorJob(id) {
  activeJob = shortlist.find(j => j.id === id);
  switchTab("tailor");
  populateTailorSelect();
  document.getElementById("tailor-sel").value = id;
  onTailorSelect();
  // Also show apply link if coming from live search (has url)
  const applyLink = document.getElementById("tailor-apply-link");
  if (applyLink && activeJob && activeJob.url) {
    applyLink.href = activeJob.url;
    applyLink.style.display = "";
  }
}

// ── tailor ─────────────────────────────────────────────────────
function populateTailorSelect() {
  const s = document.getElementById("tailor-sel");
  const cur = s.value;
  s.innerHTML = '<option value="">— pick from shortlist or paste a custom JD below —</option>';
  shortlist.forEach(j => {
    const o = document.createElement("option");
    o.value = j.id;
    o.textContent = `${j.title} @ ${j.company}`;
    s.appendChild(o);
  });
  if (cur) s.value = cur;
}

function onTailorSelect() {
  const id = document.getElementById("tailor-sel").value;
  const applyLink = document.getElementById("tailor-apply-link");
  const roleLabel = document.getElementById("tailor-role-label");
  if (!id) {
    document.getElementById("jd-ta").value = "";
    if (applyLink) applyLink.style.display = "none";
    if (roleLabel) roleLabel.textContent = "Generate a role-specific CV and cover letter with genuine bullet rewrites.";
    return;
  }
  activeJob = shortlist.find(j => j.id === id);
  if (applyLink && activeJob.url) {
    applyLink.href = activeJob.url;
    applyLink.style.display = "";
  } else if (applyLink) {
    applyLink.style.display = "none";
  }
  if (roleLabel) {
    roleLabel.textContent = `${activeJob.title} · ${activeJob.company}`;
  }
  document.getElementById("jd-ta").value =
    `${activeJob.title} at ${activeJob.company}\n${activeJob.location} · ${activeJob.type || ""} · ${activeJob.salary || ""}\n\n${activeJob.jd_summary || ""}\n\nKey requirements:\n${(activeJob.key_requirements || []).map(r => "• " + r).join("\n")}`;
  const tags = activeJob.tags || [];
  const guess = tags.some(t => ["rdf","sparql","kg","ontology","semantic"].includes(t.toLowerCase())) ? "kg"
    : tags.some(t => ["rag","llm","nlp"].includes(t.toLowerCase())) ? "ai"
    : tags.some(t => ["java","spring","kafka"].includes(t.toLowerCase())) ? "java" : "ai";
  document.getElementById("cv-variant").value = guess;
}

async function runFitAnalysis() {
  const jd = document.getElementById("jd-ta").value.trim();
  if (!jd) { showTailorErr("Paste a job description first."); return; }
  clearTailorErr();
  document.getElementById("tailor-loading").style.display = "flex";
  document.getElementById("tailor-msg").textContent = "Analysing fit...";
  document.getElementById("fit-section").style.display = "none";

  const sys = `You are an expert CV analyst. Analyse fit between candidate and JD. Return ONLY valid JSON:
{ "overall":0-100,"exp_score":0-100,"skills_score":0-100,"matched":[],"missing":[],"strong_points":[],"gaps":[],"cv_strategy":"2 sentence tailoring strategy specific to this candidate and JD" }`;

  try {
    const raw = await callClaude(sys,
      `CANDIDATE:\nNaga Sowjanya Barla — AI Engineer, 13 yrs exp, MSc Data Science & AI (Liverpool 2026), KG-RAG dissertation, Python/Java/RDF/SPARQL/RAG/LLMs, TCS backend engineering at scale.\nSkills: ${Object.values(PROFILE.skills).flat().join(", ")}\n\nJD:\n${jd}`
    );
    const fit = parseJSON(raw);
    document.getElementById("fit-metrics").innerHTML = `
      <div class="metric"><div class="metric-val">${fit.overall || 0}%</div><div class="metric-lbl">overall fit</div></div>
      <div class="metric"><div class="metric-val">${fit.exp_score || 0}%</div><div class="metric-lbl">experience match</div></div>
      <div class="metric"><div class="metric-val">${fit.skills_score || 0}%</div><div class="metric-lbl">skills match</div></div>`;
    let html = "";
    if ((fit.matched || []).length)
      html += `<div class="field"><label class="lbl" style="margin-bottom:4px">Matched keywords</label><div class="tag-row">${fit.matched.map(k => `<span class="tag match">${k}</span>`).join("")}</div></div>`;
    if ((fit.missing || []).length)
      html += `<div class="field"><label class="lbl" style="margin-bottom:4px">Keywords to inject</label><div class="tag-row">${fit.missing.map(k => `<span class="tag gap">${k}</span>`).join("")}</div></div>`;
    if (fit.cv_strategy)
      html += `<div class="insight">Strategy: ${fit.cv_strategy}</div>`;
    document.getElementById("fit-detail").innerHTML = html;
    document.getElementById("fit-section").style.display = "block";
  } catch (e) {
    showTailorErr("Analysis failed: " + e.message);
  } finally {
    document.getElementById("tailor-loading").style.display = "none";
  }
}

async function generateCV() {
  console.log("Generating CV with current JD and settings...");
  const jd = document.getElementById("jd-ta").value.trim();
  if (!jd) { showTailorErr("Paste a job description first."); return; }
  const variant = document.getElementById("cv-variant").value;
  const intensity = document.getElementById("tailor-intensity").value;
  const coverMode = document.getElementById("want-cover").value; // "yes" | "no" | "cover-only"
  const wantCover = coverMode !== "no";
  const coverOnly = coverMode === "cover-only";
  const tone = document.getElementById("cover-tone").value;
  const emph = document.getElementById("emph-notes").value;
  const role = ROLES.find(r => r.id === variant) || ROLES[0];
  clearTailorErr();

  switchTab("output");
  document.getElementById("out-loading").style.display = "flex";
  document.getElementById("out-msg").textContent = coverOnly ? "Drafting cover letter..." : "Rewriting bullets and generating tailored CV...";
  document.getElementById("out-area").style.display = "none";
  document.getElementById("out-empty").style.display = "none";

  try {
    let data;

    if (coverOnly) {
      const sys = `You are an expert cover letter writer for AI/ML/Semantic Web roles.
Tone: ${tone}. Exactly 3 paragraphs. No opening "I am writing to apply". Lead with the research story.
Return ONLY valid JSON — no markdown fences:
{ "cover_letter": "full cover letter text", "match_score": 0-100, "key_changes": "1 sentence on why this letter fits the role" }`;
      const raw = await callClaude(sys,
        `FULL PROFILE:\n${JSON.stringify(PROFILE, null, 2)}\n\nJOB DESCRIPTION:\n${jd}`
      );
      data = parseJSON(raw);
    } else {
      const sys = `You are an elite CV writer specialising in AI/ML/Semantic Web roles. You have this candidate's full profile.

CANDIDATE: Naga Sowjanya Barla — AI Engineer, 13 yrs exp, MSc Data Science & AI (Liverpool), KG-RAG dissertation, Python/Java/RDF/SPARQL.

CRITICAL RULES:
- Bullets must be genuinely rewritten — not just keyword-injected. Use strong action verbs. Quantify anything quantifiable. Cut bullets that add no signal.
- CV variant: ${role.label}. Tailor section ordering and bullet emphasis for this track.
- Intensity: ${intensity}. ${intensity === "sharp" ? "Substantially rewrite bullets; restructure if it helps." : intensity === "moderate" ? "Strengthen and sharpen; keep structure mostly intact." : "Light touch only — minimal changes."}
- Candidate emphasis notes: ${emph}
- Cover letter tone: ${tone}. Exactly 3 paragraphs. No opening "I am writing to apply". Lead with the research story.
- Track-specific ordering: ${variant === "kg" || variant === "research" ? "Lead with ESWC paper and KG-RAG work. TCS shows scale but is secondary." : variant === "java" ? "Lead with TCS backend depth. AI/research work is a differentiator, secondary." : "Lead with RAG/LLM credentials and publication. TCS shows production scale."}

Return ONLY valid JSON — no markdown fences:
{
  "headline": "role-specific headline, max 8 words",
  "summary": "tailored 3-sentence summary — mention ESWC paper, be specific to the role",
  "experience": [ { "id":"", "role":"", "co":"", "dates":"", "bullets":[] } ],
  "projects": [ { "id":"", "title":"", "bullets":[] } ],
  "cover_letter": "full cover letter text, or empty string if not requested",
  "match_score": 0-100,
  "key_changes": "2 sentence summary of what was changed and why"
}`;
      const raw = await callClaude(sys,
        `FULL PROFILE:\n${JSON.stringify(PROFILE, null, 2)}\n\nJOB DESCRIPTION:\n${jd}\n\nGenerate cover letter: ${wantCover}`
      );
      data = parseJSON(raw);
    }

    lastOutput = { data, wantCover, coverOnly, role, jd };
    renderOutput(data, wantCover, coverOnly, role);
    document.getElementById("out-area").style.display = "block";
    document.getElementById("cover-tab-btn").style.display = wantCover ? "" : "none";
    if (coverOnly) switchOut("cover");
  } catch (e) {
    document.getElementById("out-loading").innerHTML = `<span style="color:var(--red)">Generation failed: ${e.message}</span>`;
  } finally {
    document.getElementById("out-loading").style.display = "none";
  }
}

// ── output rendering ───────────────────────────────────────────
function renderOutput(data, wantCover, coverOnly, role) {
  const sc = data.match_score || 0;
  document.getElementById("out-metrics").innerHTML = `
    <div class="metric"><div class="metric-val">${sc}%</div><div class="metric-lbl">estimated match</div></div>
    <div class="metric" style="grid-column:span 2">
      <div style="font-size:12px;color:var(--muted);line-height:1.6;text-align:left;padding-top:4px">${data.key_changes || ""}</div>
    </div>`;

  // In cover-only mode hide CV/plain/LaTeX tabs; show them otherwise
  ["cv", "plain", "latex"].forEach(id => {
    const btn = document.querySelector(`.out-tab[onclick="switchOut('${id}')"]`);
    if (btn) btn.style.display = coverOnly ? "none" : "";
  });

  // CV preview
  let h = `
    <div style="margin-bottom:1.5rem">
      <div style="font-size:22px;font-weight:700;color:var(--navy)">${PROFILE.name}</div>
      <div style="font-size:13px;color:var(--muted);font-style:italic;margin-top:2px">${data.headline || role.label}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:5px">${PROFILE.email} · ${PROFILE.phone} · ${PROFILE.location}</div>
      <div style="font-size:12px;color:var(--muted)">${PROFILE.linkedin} · ${PROFILE.github}</div>
    </div>`;

  if (data.summary) {
    h += `<div class="cv-section">Professional Summary</div>
      <p style="font-size:13px;line-height:1.7">${data.summary}</p>`;
  }

  if ((data.projects || []).length) {
    h += `<div class="cv-section">Key Projects</div>`;
    data.projects.forEach(p => {
      h += `<div style="margin-bottom:1rem">
        <div class="cv-role">${p.title}</div>
        <ul class="cv-bullets">${(p.bullets || []).map(b => `<li>${b}</li>`).join("")}</ul>
      </div>`;
    });
  }

  if ((data.experience || []).length) {
    h += `<div class="cv-section">Experience</div>`;
    data.experience.forEach(e => {
      h += `<div style="margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px">
          <span class="cv-role">${e.role}</span>
          <span style="font-size:12px;color:var(--muted)">${e.dates || ""}</span>
        </div>
        <div class="cv-meta">${e.co}</div>
        <ul class="cv-bullets">${(e.bullets || []).map(b => `<li>${b}</li>`).join("")}</ul>
      </div>`;
    });
  }

  h += `<div class="cv-section">Education</div>`;
  PROFILE.education.forEach(e => {
    h += `<div style="margin-bottom:6px;font-size:13px">
      <strong>${e.degree}</strong> — ${e.inst} <span style="color:var(--muted)">${e.year || ""}</span>
      ${e.note ? `<div style="font-size:12px;color:var(--muted)">${e.note}</div>` : ""}
    </div>`;
  });

  h += `<div class="cv-section">Skills</div>`;
  Object.entries(PROFILE.skills).forEach(([cat, items]) => {
    h += `<div style="font-size:13px;margin-bottom:4px"><strong>${cat}:</strong> ${items.join(", ")}</div>`;
  });

  document.getElementById("out-cv").innerHTML = h;

  // Cover letter
  const cl = data.cover_letter || "";
  document.getElementById("out-cover").innerHTML = wantCover && cl
    ? cl.split(/\n\n+/).map(p => `<p style="margin-bottom:1rem;font-size:13px;line-height:1.8">${p.replace(/\n/g, "<br>")}</p>`).join("")
    : '<p style="color:var(--muted)">No cover letter generated.</p>';

  // Plain text
  const lines = [
    PROFILE.name,
    data.headline || role.label,
    `${PROFILE.email} | ${PROFILE.phone} | ${PROFILE.location}`,
    PROFILE.linkedin,
    ""
  ];
  lines.push("");
  if (data.summary) { lines.push("SUMMARY"); lines.push(data.summary); lines.push(""); }
  (data.projects || []).forEach(p => {
    lines.push("PROJECTS");
    lines.push(p.title);
    (p.bullets || []).forEach(b => lines.push("• " + b));
    lines.push("");
  });
  (data.experience || []).forEach(e => {
    lines.push(`${e.role} | ${e.co} | ${e.dates || ""}`);
    (e.bullets || []).forEach(b => lines.push("• " + b));
    lines.push("");
  });
  lines.push("EDUCATION");
  PROFILE.education.forEach(e => lines.push(`${e.degree} — ${e.inst} ${e.year || ""}`));
  lines.push("");
  lines.push("SKILLS");
  Object.entries(PROFILE.skills).forEach(([c, i]) => lines.push(`${c}: ${i.join(", ")}`));
  if (wantCover && cl) { lines.push("", "--- COVER LETTER ---", "", cl); }
  document.getElementById("out-plain").textContent = lines.join("\n");

  // LaTeX
  document.getElementById("out-latex").textContent = buildLatex(data, wantCover, role);
}

function buildLatex(data, wantCover, role) {
  const esc = s => (s || "")
    .replace(/&/g, "\\&").replace(/%/g, "\\%").replace(/#/g, "\\#")
    .replace(/_/g, "\\_").replace(/\$/g, "\\$").replace(/~/g, "\\textasciitilde{}");

  let tex = `% Generated by CV Fit Studio — ${role.label}\n`;
  tex += `\\documentclass[a4paper,10pt]{article}\n`;
  tex += `\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}\n\\usepackage{lmodern}\n`;
  tex += `\\usepackage{geometry}\n\\usepackage{enumitem}\n\\usepackage[hidelinks]{hyperref}\n`;
  tex += `\\usepackage{xcolor}\n\\usepackage{titlesec}\n`;
  tex += `\\geometry{top=0.6in,bottom=0.6in,left=0.7in,right=0.7in}\n`;
  tex += `\\definecolor{navy}{HTML}{1A3C5E}\n\\definecolor{muted}{HTML}{555555}\n\\definecolor{body}{HTML}{222222}\n`;
  tex += `\\titleformat{\\section}{\\normalfont\\small\\bfseries\\color{navy}}{}{0em}{\\MakeUppercase}[\\vspace{2pt}{\\color{navy}\\titlerule[1.2pt]}]\n`;
  tex += `\\titlespacing*{\\section}{0pt}{10pt}{6pt}\n`;
  tex += `\\setlist[itemize]{leftmargin=1.4em,itemsep=1.5pt,topsep=3pt,parsep=0pt,label={\\color{navy}\\normalsize$\\bullet$}}\n`;
  tex += `\\pagestyle{empty}\n\\setlength{\\parindent}{0pt}\n\\begin{document}\n\n`;

  // Header
  tex += `\\begin{center}\n`;
  tex += `  {\\fontsize{24}{28}\\selectfont\\bfseries\\color{navy}${esc(PROFILE.name)}}\\par\\vspace{4pt}\n`;
  tex += `  {\\small\\color{muted}\\textit{${esc(data.headline || role.label)}}}\\par\\vspace{3pt}\n`;
  tex += `  {\\footnotesize\\color{muted}${esc(PROFILE.location)} $\\cdot$ ${esc(PROFILE.phone)} $\\cdot$ ${esc(PROFILE.email)}}\\par\\vspace{2pt}\n`;
  tex += `  {\\footnotesize\\color{muted}\\href{${PROFILE.linkedin}}{LinkedIn} $\\cdot$ \\href{${PROFILE.github}}{GitHub}}\n`;
  tex += `\\end{center}\n\\vspace{4pt}{\\color{navy}\\hrule height 0.8pt}\\vspace{6pt}\n\n`;

  // Summary
  if (data.summary) {
    tex += `\\section{Profile}\n{\\small\\color{body}${esc(data.summary)}}\n\n`;
  }

  // Projects
  if ((data.projects || []).length) {
    tex += `\\section{Projects}\n`;
    data.projects.forEach(p => {
      tex += `\\noindent\\textbf{\\color{navy}${esc(p.title)}}\\par\\vspace{2pt}\n\\begin{itemize}\n`;
      (p.bullets || []).forEach(b => { tex += `  \\item ${esc(b)}\n`; });
      tex += `\\end{itemize}\\vspace{6pt}\n`;
    });
    tex += "\n";
  }

  // Experience
  if ((data.experience || []).length) {
    tex += `\\section{Experience}\n`;
    data.experience.forEach(e => {
      tex += `\\noindent\\textbf{\\color{navy}${esc(e.role)}}\\hfill{\\small\\color{muted}\\textit{${esc(e.dates || "")}}}\\par\n`;
      tex += `\\noindent{\\small\\color{muted}\\textit{${esc(e.co)}}}\\par\\vspace{3pt}\n`;
      tex += `\\begin{itemize}\n`;
      (e.bullets || []).forEach(b => { tex += `  \\item ${esc(b)}\n`; });
      tex += `\\end{itemize}\\vspace{4pt}\n`;
    });
    tex += "\n";
  }

  // Education
  tex += `\\section{Education}\n`;
  PROFILE.education.forEach(e => {
    tex += `\\noindent\\textbf{\\color{navy}${esc(e.degree)}}\\hfill{\\small\\color{muted}\\textit{${esc(e.year || "")}}}\\par\n`;
    tex += `\\noindent{\\small\\color{muted}\\textit{${esc(e.inst)}}}`;
    if (e.note) tex += `\\par\\noindent{\\small ${esc(e.note)}}`;
    tex += `\\vspace{5pt}\n\n`;
  });

  // Skills
  tex += `\\section{Skills}\n{\\small\n`;
  Object.entries(PROFILE.skills).forEach(([cat, items]) => {
    tex += `\\textbf{\\color{navy}${esc(cat)}:} ${esc(items.join(", "))}\\par\\vspace{2pt}\n`;
  });
  tex += `}\n\n`;

  // Certifications
  tex += `\\section{Certifications}\n\\begin{itemize}\n`;
  PROFILE.certifications.forEach(c => { tex += `  \\item ${esc(c)}\n`; });
  tex += `\\end{itemize}\n\n\\end{document}\n`;

  return tex;
}

// ── output tab switching ───────────────────────────────────────
function switchOut(t) {
  ["cv", "cover", "plain", "latex"].forEach(k => {
    document.getElementById("out-" + k).style.display = k === t ? "" : "none";
  });
  document.querySelectorAll(".out-tab").forEach((el, i) =>
    el.classList.toggle("active", ["cv", "cover", "plain", "latex"][i] === t)
  );
}

function copyText(id) {
  const el = document.getElementById(id);
  const text = el.textContent || el.innerText;
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(() => {
    prompt("Copy this:", text);
  });
}

function downloadLatex() {
  const text = document.getElementById("out-latex").textContent;
  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = _autoName("cv") + ".tex";
  a.click();
}

// ── error helpers ──────────────────────────────────────────────
function showTailorErr(msg) {
  const el = document.getElementById("tailor-err");
  el.textContent = msg;
  el.style.display = "block";
}
function clearTailorErr() {
  document.getElementById("tailor-err").style.display = "none";
}


// ── live search ────────────────────────────────────────────────
let liveActiveTrack = ROLES[0];

function renderLiveTrackPills() {
  const c = document.getElementById("live-track-pills");
  if (!c) return;
  c.innerHTML = ROLES.map(r =>
    `<span class="pill${r.id === liveActiveTrack.id ? " active" : ""}" onclick="setLiveTrack('${r.id}',this)">${r.label.split("/")[0].trim()}</span>`
  ).join("");
  // auto-fill keywords from first search title
  fillLiveKeywords();
}

function setLiveTrack(id, el) {
  liveActiveTrack = ROLES.find(r => r.id === id);
  document.querySelectorAll("#live-track-pills .pill").forEach(p => p.classList.remove("active"));
  el.classList.add("active");
  fillLiveKeywords();
}

function fillLiveKeywords() {
  const el = document.getElementById("live-keywords");
  if (el && liveActiveTrack.searchTitles && liveActiveTrack.searchTitles.length) {
    el.value = liveActiveTrack.searchTitles[0];
  }
}

async function runLiveSearch() {
  const keywords = document.getElementById("live-keywords").value.trim();
  const location = document.getElementById("live-location").value.trim() || "UK";
  const days = parseInt(document.getElementById("live-recency").value || "7");
  const n = parseInt(document.getElementById("live-results-n").value || "10");
  if (!keywords) return;

  const recencyLabel = days === 0 ? "any time" : `last ${days} days`;
  document.getElementById("live-loading").style.display = "flex";
  document.getElementById("live-msg").textContent = `Searching Reed + Adzuna for "${keywords}" (${recencyLabel})...`;
  document.getElementById("live-error").style.display = "none";
  document.getElementById("live-counts").style.display = "none";
  document.getElementById("live-results").style.display = "none";

  try {
    const r = await fetch("/api/jobs/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords, location, results_per_source: n, days_old: days })
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    const counts = data.counts || {};
    const countEl = document.getElementById("live-counts");
    countEl.textContent = `${counts.total || 0} roles found — ${counts.reed || 0} from Reed, ${counts.adzuna || 0} from Adzuna`;
    countEl.style.display = "";
    renderLiveJobCards(data.jobs || []);
    document.getElementById("live-results").style.display = "block";
    document.getElementById("live-title").textContent = `${(data.jobs || []).length} live roles`;
  } catch (e) {
    document.getElementById("live-error").textContent = "Search failed: " + e.message;
    document.getElementById("live-error").style.display = "block";
  } finally {
    document.getElementById("live-loading").style.display = "none";
  }
}

function renderLiveJobCards(jobs) {
  const c = document.getElementById("live-job-cards");
  c.innerHTML = "";
  const slIds = new Set(shortlist.map(j => j.id));
  if (!jobs.length) {
    c.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:1rem 0">No results found. Try different keywords or location.</div>';
    return;
  }
  jobs.forEach(job => {
    const d = document.createElement("div");
    d.className = "job-card" + (slIds.has(job.id) ? " selected" : "");
    const src = job.source === "Reed"
      ? `<span class="badge badge-navy" style="font-size:10px">Reed</span>`
      : `<span class="badge badge-amber" style="font-size:10px">Adzuna</span>`;
    d.innerHTML = `
      <div class="jc-check">✓</div>
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:6px;margin-bottom:2px">
        <a href="${job.url}" target="_blank" rel="noopener"
           style="font-size:14px;font-weight:600;flex:1;color:var(--navy);text-decoration:none;line-height:1.3"
           onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
          ${job.title} ↗
        </a>
        ${src}
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px">${job.company} · ${job.location}</div>
      ${job.salary ? `<div style="font-size:12px;color:var(--teal);font-weight:500;margin-bottom:4px">${job.salary}</div>` : ""}
      <div style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:6px">${job.summary}</div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:6px">
        ${job.posted ? `<span style="font-size:11px;color:var(--hint)">Posted: ${job.posted}</span>` : "<span></span>"}
        <button class="btn btn-sm" onclick="toggleLiveShortlist(event,'${job.id}')" style="font-size:11px;padding:4px 10px">
          ${slIds.has(job.id) ? "✓ Shortlisted" : "+ Shortlist"}
        </button>
      </div>`;
    // Store job data on element for shortlisting
    d.dataset.job = JSON.stringify(job);
    c.appendChild(d);
  });
}

function toggleLiveShortlist(event, jobId) {
  event.stopPropagation();
  const card = event.target.closest(".job-card");
  const job = JSON.parse(card.dataset.job || "{}");
  const idx = shortlist.findIndex(j => j.id === jobId);
  if (idx === -1) {
    shortlist.push(job);
    card.classList.add("selected");
    event.target.textContent = "✓ Shortlisted";
  } else {
    shortlist.splice(idx, 1);
    card.classList.remove("selected");
    event.target.textContent = "+ Shortlist";
  }
  updateSlBadge();
}

// ── Applications log — Phase 5-T3 ─────────────────────────────
async function loadApplicationLog() {
  const loading = document.getElementById("app-log-loading");
  const empty = document.getElementById("app-log-empty");
  const table = document.getElementById("app-log-table");
  const tbody = document.getElementById("app-log-tbody");

  loading.style.display = "flex";
  empty.style.display = "none";
  table.style.display = "none";

  try {
    const r = await fetch("/api/apply/log");
    const d = await r.json();
    const log = d.log || [];

    if (!log.length) {
      empty.style.display = "";
      return;
    }

    tbody.innerHTML = "";
    log.forEach(entry => {
      const statusCls = entry.status === "applied" ? "badge-green"
        : entry.status === "failed" ? "badge-red"
        : entry.status === "awaiting_confirm" ? "badge-amber"
        : "badge-muted";
      const date = (entry.applied_at || entry.queued_at || "").slice(0, 10);
      const tr = document.createElement("tr");
      tr.style = "border-bottom:1px solid var(--border)";
      tr.innerHTML = `
        <td style="padding:10px">${entry.company || ""}</td>
        <td style="padding:10px">${entry.job_title || ""}</td>
        <td style="padding:10px;color:var(--muted)">${date}</td>
        <td style="padding:10px;color:var(--muted)">${entry.method || ""}</td>
        <td style="padding:10px"><span class="badge ${statusCls}">${entry.status || ""}</span></td>
        <td style="padding:10px">
          ${entry.cover_letter_used
            ? `<button class="btn btn-sm btn-ghost" onclick="toggleCoverLetterRow(this)" data-cl="${encodeURIComponent(entry.cover_letter_used)}">View</button>`
            : '<span style="color:var(--hint);font-size:12px">—</span>'}
        </td>
      `;
      tbody.appendChild(tr);
    });
    table.style.display = "";
  } catch (e) {
    empty.textContent = "Failed to load log: " + e.message;
    empty.style.display = "";
  } finally {
    loading.style.display = "none";
  }
}

function toggleCoverLetterRow(btn) {
  const cl = decodeURIComponent(btn.dataset.cl || "");
  const tr = btn.closest("tr");
  let next = tr.nextElementSibling;
  if (next && next.dataset.clRow) {
    next.remove();
    btn.textContent = "View";
    return;
  }
  const row = document.createElement("tr");
  row.dataset.clRow = "1";
  row.innerHTML = `<td colspan="6" style="padding:10px 14px;background:var(--bg)">
    <div style="font-size:12px;line-height:1.7;white-space:pre-wrap;max-height:200px;overflow-y:auto">${cl}</div>
  </td>`;
  tr.after(row);
  btn.textContent = "Hide";
}

// ── Apply panel — Phase 5-T2 ───────────────────────────────────
let applyPanelJobId = null;
let _applyCVLatex = "";

function openApplyPanel(jobId) {
  const job = discoveredJobs.find(j => j.id === jobId) || { id: jobId, title: "", company: "" };
  applyPanelJobId = jobId;

  document.getElementById("apply-panel-title").textContent = `Apply — ${job.title}`;
  document.getElementById("apply-panel-meta").innerHTML = `
    <div style="font-size:14px;font-weight:600">${job.title}</div>
    <div style="font-size:12px;color:var(--muted);margin-top:2px">${job.company} · ${job.location || ""}</div>
    ${job.url ? `<a href="${job.url}" target="_blank" rel="noopener" style="font-size:11px;color:var(--teal)">View posting ↗</a>` : ""}
  `;

  // Reset panel state
  document.getElementById("apply-cover-text").value = "";
  document.getElementById("apply-tailor-loading").style.display = "";
  document.getElementById("apply-tailor-summary").style.display = "none";
  document.getElementById("apply-tailor-body").style.display = "none";
  document.getElementById("apply-progress").style.display = "none";
  document.getElementById("apply-screenshot-area").style.display = "none";
  document.getElementById("apply-result").style.display = "none";
  document.getElementById("cl-preview-panel").style.display = "none";
  document.getElementById("cl-confirm-btn").style.display = "none";
  document.getElementById("apply-status-badge").style.display = "none";

  // Slide in
  document.getElementById("apply-panel").style.right = "0";
  document.getElementById("apply-overlay").style.display = "";

  // Auto-trigger tailoring
  generateApplyCoverLetter();
}

function closeApplyPanel() {
  document.getElementById("apply-panel").style.right = "-480px";
  document.getElementById("apply-overlay").style.display = "none";
}

async function generateApplyCoverLetter(forceRegenerate = false) {
  if (!applyPanelJobId) return;
  const resumeYaml = window._resumeYamlCache || "";

  document.getElementById("apply-tailor-loading").style.display = "";
  document.getElementById("apply-tailor-summary").style.display = "none";
  document.getElementById("apply-tailor-body").style.display = "none";

  if (!resumeYaml) {
    document.getElementById("apply-tailor-loading").style.display = "none";
    document.getElementById("apply-tailor-body").style.display = "";
    document.getElementById("apply-cover-text").placeholder =
      "Resume YAML not loaded — reload the page and try again.";
    return;
  }

  try {
    const r = await fetch("/api/apply/generate-cover-letter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: applyPanelJobId,
        resume_yaml: resumeYaml,
        force_regenerate: forceRegenerate,
      })
    });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();

    // Render tailoring summary
    const s = d.fit_score || 0;
    const bc = s >= 70 ? "badge-green" : s >= 50 ? "badge-amber" : "badge-muted";
    const matched = (d.matched_skills || []).concat(d.matched_tools || []).slice(0, 6);
    const missing = (d.missing_skills || []).concat(d.missing_tools || []).slice(0, 4);
    const topBlock = (d.top_blocks || [])[0];

    document.getElementById("apply-fit-row").innerHTML = s > 0
      ? `<span class="badge ${bc}" style="font-size:12px">${s}% fit</span>`
        + (d.jd_category ? ` <span class="badge badge-muted" style="font-size:11px">${d.jd_category}</span>` : "")
        + (d.seniority_level ? ` <span class="badge badge-muted" style="font-size:11px">${d.seniority_level}</span>` : "")
      : "";

    document.getElementById("apply-matched-row").innerHTML = matched.length
      ? `<div style="font-size:11px;font-weight:600;color:var(--teal);margin-bottom:3px">Matched</div>
         <div class="tag-row">${matched.map(t => `<span class="tag match">${t}</span>`).join("")}</div>`
      : "";

    document.getElementById("apply-missing-row").innerHTML = missing.length
      ? `<div style="font-size:11px;font-weight:600;color:var(--amber);margin-bottom:3px">Address in letter</div>
         <div class="tag-row">${missing.map(t => `<span class="tag gap">${t}</span>`).join("")}</div>`
      : "";

    document.getElementById("apply-lead-row").innerHTML = topBlock
      ? `<div style="font-size:11px;padding:6px 8px;background:var(--navy-light);border-radius:4px;color:var(--navy)">
           Lead with: <strong>${topBlock}</strong>
         </div>`
      : "";

    document.getElementById("apply-cover-text").value = d.cover_letter || "";
    document.getElementById("apply-tailor-summary").style.display = "";
    document.getElementById("apply-tailor-body").style.display = "";
    // Populate cover letter preview panel
    document.getElementById("cl-preview-ta").value = d.cover_letter || "";
    document.getElementById("cl-preview-panel").style.display = "";
    document.getElementById("cl-confirm-btn").style.display = "";
  } catch (e) {
    document.getElementById("apply-tailor-body").style.display = "";
    document.getElementById("apply-cover-text").value = "";
    document.getElementById("apply-cover-text").placeholder = "Tailoring failed: " + e.message;
  } finally {
    document.getElementById("apply-tailor-loading").style.display = "none";
  }
}

async function generateApplyCV() {
  if (!applyPanelJobId) return;
  const job = discoveredJobs.find(j => j.id === applyPanelJobId);
  if (!job) return;

  const jd = [
    `${job.title} at ${job.company}`,
    job.location ? `${job.location}` : "",
    job.description_full || job.summary || job.jd_summary || "",
  ].filter(Boolean).join("\n\n");

  const btn = document.getElementById("apply-cv-btn");
  btn.disabled = true;
  document.getElementById("apply-cv-loading").style.display = "flex";
  document.getElementById("apply-cv-area").style.display = "none";

  const role = ROLES.find(r => activeTrack && r.id === activeTrack.id) || ROLES[0];
  const sys = `You are an elite CV writer for AI/ML/Semantic Web roles.
CANDIDATE: Naga Sowjanya Barla — AI Engineer, 13 yrs exp, MSc Data Science & AI (Liverpool 2026), Python/Java/RDF/SPARQL/RAG/LLMs, TCS backend engineering.
RULES: ESWC paper must appear prominently. Rewrite bullets — do NOT just inject keywords. Quantify where possible.
Return ONLY valid JSON (no markdown): {"headline":"","summary":"","experience":[{"id":"","role":"","co":"","dates":"","bullets":[]}],"projects":[{"id":"","title":"","bullets":[]}],"key_changes":""}`;

  try {
    const raw = await callClaude(sys,
      `FULL PROFILE:\n${JSON.stringify(PROFILE, null, 2)}\n\nJOB DESCRIPTION:\n${jd}`
    );
    const data = parseJSON(raw);

    // Build plain text
    const lines = [
      PROFILE.name,
      data.headline || role.label,
      `${PROFILE.email} | ${PROFILE.phone} | ${PROFILE.location}`,
      PROFILE.linkedin, "",
    ];
    lines.push("");
    if (data.summary) { lines.push("SUMMARY"); lines.push(data.summary); lines.push(""); }
    (data.projects || []).forEach(p => {
      lines.push("PROJECTS"); lines.push(p.title);
      (p.bullets || []).forEach(b => lines.push("• " + b)); lines.push("");
    });
    (data.experience || []).forEach(e => {
      lines.push(`${e.role} | ${e.co} | ${e.dates || ""}`);
      (e.bullets || []).forEach(b => lines.push("• " + b)); lines.push("");
    });
    lines.push("EDUCATION");
    PROFILE.education.forEach(e => lines.push(`${e.degree} — ${e.inst} ${e.year || ""}`));
    lines.push("", "SKILLS");
    Object.entries(PROFILE.skills).forEach(([c, i]) => lines.push(`${c}: ${i.join(", ")}`));
    if (data.key_changes) { lines.push("", "--- TAILORING NOTES ---", data.key_changes); }

    document.getElementById("apply-cv-plain").textContent = lines.join("\n");
    _applyCVLatex = buildLatex(data, false, role);

    document.getElementById("apply-cv-area").style.display = "";
    btn.textContent = "↻ Re-generate";
  } catch (e) {
    document.getElementById("apply-cv-area").style.display = "";
    document.getElementById("apply-cv-plain").textContent = "Generation failed: " + e.message;
  } finally {
    document.getElementById("apply-cv-loading").style.display = "none";
    btn.disabled = false;
  }
}

const _dlCount = {};
function _autoName(variant) {
  _dlCount[variant] = (_dlCount[variant] || 0) + 1;
  const base = PROFILE.name.toLowerCase().replace(/\s+/g, "");
  return `${base}_${variant}_${_dlCount[variant]}`;
}

function copyApplyText(elId) {
  const text = document.getElementById(elId).value || document.getElementById(elId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(() => {
    prompt("Copy this:", text);
  });
}

function downloadApplyText(elId, filename) {
  const text = document.getElementById(elId).value || document.getElementById(elId).textContent;
  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function downloadApplyCVLatex() {
  if (!_applyCVLatex) { alert("Generate the tailored CV first."); return; }
  const blob = new Blob([_applyCVLatex], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = _autoName("cv") + ".tex";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadApplyCVPDF() {
  if (!_applyCVLatex) { alert("Generate the tailored CV first."); return; }
  await _downloadPDF(_applyCVLatex, _autoName("cv"), "apply-cv-pdf-btn");
}

function _buildCoverLetterLatex(text, job) {
  const esc = s => (s || "")
    .replace(/&/g, "\\&").replace(/%/g, "\\%").replace(/#/g, "\\#")
    .replace(/_/g, "\\_").replace(/\$/g, "\\$").replace(/~/g, "\\textasciitilde{}");

  const today = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const paragraphs = text.split(/\n\n+/).filter(p => p.trim());

  let tex = `\\documentclass[a4paper,11pt]{article}\n`;
  tex += `\\usepackage[top=1.2in,bottom=1.2in,left=1.25in,right=1.25in]{geometry}\n`;
  tex += `\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}\n\\usepackage{lmodern}\n`;
  tex += `\\usepackage[hidelinks]{hyperref}\n\\usepackage{xcolor}\n`;
  tex += `\\definecolor{navy}{HTML}{1A3C5E}\n`;
  tex += `\\pagestyle{empty}\n\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{0.9em}\n`;
  tex += `\\begin{document}\n\n`;

  // Header
  tex += `{\\large\\bfseries\\color{navy}${esc(PROFILE.name)}}\\hfill{\\small\\color{gray}${esc(today)}}\\par\n`;
  tex += `{\\small ${esc(PROFILE.email)} $\\cdot$ ${esc(PROFILE.phone)} $\\cdot$ ${esc(PROFILE.location)}}\\par\n`;
  tex += `{\\small \\href{${PROFILE.linkedin}}{LinkedIn}}\\par\n`;
  tex += `\\vspace{1em}\n`;

  // Addressee
  if (job && job.company) {
    tex += `{\\small Hiring Team}\\par\n`;
    tex += `{\\small\\bfseries ${esc(job.company)}}\\par\n`;
    if (job.title) tex += `{\\small Re: ${esc(job.title)}}\\par\n`;
    tex += `\\vspace{1em}\n`;
  }

  // Body
  paragraphs.forEach(p => {
    tex += `${esc(p.replace(/\n/g, " "))}\\par\n\n`;
  });

  // Sign-off
  tex += `\\vspace{1.5em}\n`;
  tex += `Yours sincerely,\\par\\vspace{2em}\n`;
  tex += `{\\bfseries\\color{navy}${esc(PROFILE.name)}}\\par\n`;

  tex += `\\end{document}\n`;
  return tex;
}

function downloadApplyCoverLetterLatex() {
  const text = document.getElementById("apply-cover-text").value.trim();
  if (!text) { alert("Cover letter is empty."); return; }
  const job = discoveredJobs.find(j => j.id === applyPanelJobId);
  const latex = _buildCoverLetterLatex(text, job);
  const blob = new Blob([latex], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = _autoName("coverletter") + ".tex";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadApplyCoverLetterPDF() {
  const text = document.getElementById("apply-cover-text").value.trim();
  if (!text) { alert("Cover letter is empty."); return; }
  const job = discoveredJobs.find(j => j.id === applyPanelJobId);
  const latex = _buildCoverLetterLatex(text, job);
  await _downloadPDF(latex, _autoName("coverletter"), "apply-cl-pdf-btn");
}

async function _downloadPDF(latex, filename, btnId) {
  const btn = btnId ? document.getElementById(btnId) : null;
  const orig = btn ? btn.textContent : "";
  if (btn) { btn.textContent = "Compiling..."; btn.disabled = true; }
  try {
    const r = await fetch("/api/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latex, filename })
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || "PDF generation failed");
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename + ".pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("PDF error: " + e.message);
  } finally {
    if (btn) { btn.textContent = orig; btn.disabled = false; }
  }
}

async function submitApply() {
  if (!applyPanelJobId) return;
  const method = document.getElementById("apply-method").value;
  const coverLetter = document.getElementById("apply-cover-text").value;

  if (method === "manual") {
    const job = discoveredJobs.find(j => j.id === applyPanelJobId);
    const url = job?.url || job?.apply_url || "";
    if (url) window.open(url, "_blank", "noopener");
    _showApplyResult("success", "Link opened — apply manually in the new tab.");
    return;
  }

  // Queue then run Easy Apply
  document.getElementById("apply-action-area").style.display = "none";
  document.getElementById("apply-progress").style.display = "";
  document.getElementById("apply-progress-msg").textContent = "Queuing application...";

  const _cvLatex = document.getElementById("out-latex")?.textContent || "";

  try {
    // Queue
    const qr = await fetch("/api/apply/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: applyPanelJobId, method, cover_letter: coverLetter, cv_latex: _cvLatex })
    });
    if (!qr.ok) {
      const err = await qr.json().catch(() => ({ detail: qr.statusText }));
      throw new Error(err.detail || "Queue failed");
    }

    document.getElementById("apply-progress-msg").textContent = "Starting Easy Apply session...";

    // Run
    const rr = await fetch(`/api/apply/run/${applyPanelJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv_pdf_path: "" })
    });
    if (!rr.ok) throw new Error(await rr.text());

    document.getElementById("apply-progress-msg").textContent = "Easy Apply running — waiting for confirmation step...";

    // Poll for awaiting_confirm
    await _pollForConfirm(applyPanelJobId);
  } catch (e) {
    document.getElementById("apply-progress").style.display = "none";
    document.getElementById("apply-action-area").style.display = "";
    _showApplyResult("error", "Apply failed: " + e.message);
  }
}

async function _pollForConfirm(jobId) {
  // Poll apply log every 3s for up to 3 min
  for (let i = 0; i < 60; i++) {
    await new Promise(res => setTimeout(res, 3000));
    try {
      const r = await fetch("/api/apply/log");
      const d = await r.json();
      const entry = (d.log || []).find(e => e.job_id === jobId);
      if (entry && entry.status === "awaiting_confirm") {
        _showScreenshotConfirm(entry);
        return;
      }
      if (entry && entry.status === "applied") {
        document.getElementById("apply-progress").style.display = "none";
        _showApplyResult("success", "Application submitted!");
        return;
      }
      if (entry && entry.status === "failed") {
        document.getElementById("apply-progress").style.display = "none";
        _showApplyResult("error", "Apply failed: " + (entry.error_message || "unknown error"));
        return;
      }
    } catch (e) { /* ignore poll errors */ }
  }
  document.getElementById("apply-progress").style.display = "none";
  _showApplyResult("error", "Timed out waiting for Easy Apply to reach confirmation step.");
}

function _showScreenshotConfirm(entry) {
  document.getElementById("apply-progress").style.display = "none";
  const area = document.getElementById("apply-screenshot-area");
  const img = document.getElementById("apply-screenshot-img");
  if (entry.screenshot_path) {
    // Screenshot is served from filesystem — use static path if available
    img.src = `/static/screenshots/${entry.screenshot_path.split("/").pop()}`;
    img.style.display = "";
  } else {
    img.style.display = "none";
  }
  area.style.display = "";
}

async function confirmApply() {
  if (!applyPanelJobId) return;
  document.getElementById("apply-screenshot-area").style.display = "none";
  document.getElementById("apply-progress").style.display = "";
  document.getElementById("apply-progress-msg").textContent = "Submitting application...";
  try {
    const r = await fetch(`/api/apply/confirm/${applyPanelJobId}`, { method: "POST" });
    const d = await r.json();
    document.getElementById("apply-progress").style.display = "none";
    if (d.status === "applied") {
      _showApplyResult("success", "Application submitted successfully!");
    } else {
      _showApplyResult("error", "Confirm failed: " + (d.error || "unknown"));
    }
  } catch (e) {
    document.getElementById("apply-progress").style.display = "none";
    _showApplyResult("error", "Confirm error: " + e.message);
  }
}

async function skipApply() {
  document.getElementById("apply-screenshot-area").style.display = "none";
  _showApplyResult("info", "Application skipped.");
}

function _showApplyResult(type, msg) {
  const el = document.getElementById("apply-result");
  const cls = type === "success" ? "alert-ok" : type === "error" ? "alert-err" : "alert-info";
  el.className = "alert " + cls;
  el.textContent = msg;
  el.style.display = "";
  document.getElementById("apply-action-area").style.display = "";
}

// ── Scrape trigger — Phase 5-T4 ────────────────────────────────
async function _pollScrapeAndRender(job_id, msgEl) {
  const barEl = document.getElementById("scrape-progress-bar");
  let scraped = [];
  for (let i = 0; i < 120; i++) {
    await new Promise(res => setTimeout(res, 3000));
    const st = await fetch(`/api/jobs/scrape/${job_id}/status`);
    const s = await st.json();
    const pct = s.total ? Math.round((s.progress / s.total) * 100) : 0;
    if (barEl) barEl.style.width = pct + "%";
    if (msgEl) msgEl.textContent = `Scraping... ${s.progress}/${s.total} jobs found`;

    if (s.status === "complete") {
      const res = await fetch(`/api/jobs/scrape/${job_id}/results`);
      const rd = await res.json();
      scraped = rd.jobs || [];
      break;
    }
    if (s.status === "failed") {
      const detail = s.traceback ? `${s.error}\n\n${s.traceback}` : (s.error || "Scrape failed");
      throw new Error(detail);
    }
  }

  if (msgEl) msgEl.textContent = `${scraped.length} jobs found. Scoring...`;
  discoveredJobs = scraped;

  if (scraped.length && window._resumeYamlCache) {
    try {
      const ids = scraped.map(j => j.id);
      const scr = await fetch("/api/jobs/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: ids, resume_yaml: window._resumeYamlCache })
      });
      if (scr.ok) {
        const sd = await scr.json();
        const scoreMap = {};
        (sd.results || []).forEach(r => { scoreMap[r.job_id] = r; });
        discoveredJobs = discoveredJobs.map(j => ({
          ...j,
          fit_score: scoreMap[j.id]?.fit_score ?? j.fit_score,
          matched_skills: scoreMap[j.id]?.matched_skills ?? j.matched_skills ?? [],
          missing_skills: scoreMap[j.id]?.missing_skills ?? j.missing_skills ?? [],
        }));
      }
    } catch (e) {
      console.error("[scoring] fetch failed:", e.message);
    }
  }

  renderJobCards();
  document.getElementById("disc-results").style.display = "block";
  document.getElementById("disc-title").textContent = `${discoveredJobs.length} jobs found (scraped)`;
}

async function discoverJobsWithScrape() {
  console.log("discoverJobsWithScrape");
  const useLI = document.getElementById("src-linkedin")?.checked;
  const useIndeed = document.getElementById("src-indeed")?.checked;

  if (!useLI && !useIndeed) {
    return discoverJobs();
  }

  const loc = document.getElementById("loc-pref").value;
  const scrapeSource = useLI && useIndeed ? "both" : useLI ? "linkedin" : "indeed";
  const query = (activeTrack.searchTitles || [activeTrack.label])[0];
  const daysOld = jobRecencyFilter === "week" ? 7 : jobRecencyFilter === "month" ? 30 : 0;
  const maxResults = parseInt(document.getElementById("scrape-max-results")?.value || "20", 10);

  const progressEl = document.getElementById("scrape-progress");
  const msgEl = document.getElementById("scrape-progress-msg");
  const loadEl = document.getElementById("disc-loading");
  const errEl = document.getElementById("disc-error");

  progressEl.style.display = "";
  loadEl.style.display = "flex";
  document.getElementById("disc-msg").textContent = `Scraping ${scrapeSource}...`;
  errEl.style.display = "none";
  document.getElementById("disc-results").style.display = "none";

  try {
    const sr = await fetch("/api/jobs/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: scrapeSource, query, location: loc || "UK", max_results: maxResults, days_old: daysOld })
    });
    if (!sr.ok) throw new Error(await sr.text());
    const { job_id } = await sr.json();
    await _pollScrapeAndRender(job_id, msgEl);
    progressEl.style.display = "none";
  } catch (e) {
    progressEl.style.display = "none";
    errEl.textContent = "Scrape failed: " + e.message;
    errEl.style.display = "block";
  } finally {
    loadEl.style.display = "none";
  }
}

async function triggerFromJD() {
  const jd = document.getElementById("jd-trigger-ta").value.trim();
  const msg = document.getElementById("jd-trigger-msg");
  if (!jd) { msg.textContent = "Paste a JD first."; return; }

  const loc = document.getElementById("loc-pref")?.value || "UK";
  const useLI = document.getElementById("src-linkedin")?.checked;
  const useIndeed = document.getElementById("src-indeed")?.checked;
  const source = useLI && useIndeed ? "both" : useIndeed ? "indeed" : "linkedin";
  const daysOld = jobRecencyFilter === "week" ? 7 : jobRecencyFilter === "month" ? 30 : 0;
  const maxResults = parseInt(document.getElementById("scrape-max-results")?.value || "20", 10);

  msg.textContent = "Extracting role from JD...";

  try {
    const r = await fetch("/api/jd/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jd, location: loc, source, days_old: daysOld, max_results: maxResults })
    });
    if (!r.ok) throw new Error(await r.text());
    const { scrape_job_id, extracted_title } = await r.json();

    msg.textContent = `Searching for "${extracted_title}" roles...`;
    document.getElementById("scrape-progress").style.display = "";
    document.getElementById("disc-loading").style.display = "flex";
    document.getElementById("disc-error").style.display = "none";
    document.getElementById("disc-results").style.display = "none";

    await _pollScrapeAndRender(scrape_job_id, document.getElementById("scrape-progress-msg"));
    document.getElementById("scrape-progress").style.display = "none";
    document.getElementById("disc-loading").style.display = "none";
    msg.textContent = `Done — ${discoveredJobs.length} jobs found for "${extracted_title}"`;
  } catch (e) {
    document.getElementById("scrape-progress").style.display = "none";
    document.getElementById("disc-loading").style.display = "none";
    msg.textContent = "Error: " + e.message;
  }
}


// ── Cover letter confirm + apply status polling ────────────────
async function confirmApplyWithCL() {
  const editedCL = document.getElementById("cl-preview-ta").value.trim();
  if (!applyPanelJobId) return;
  const method = document.getElementById("apply-method").value;

  document.getElementById("cl-confirm-btn").disabled = true;
  document.getElementById("apply-status-badge").style.display = "";
  document.getElementById("apply-status-badge").textContent = "Queuing application...";

  const _cvLatex2 = document.getElementById("out-latex")?.textContent || "";

  try {
    if (method === "manual") {
      const job = discoveredJobs.find(j => j.id === applyPanelJobId);
      const url = job?.url || job?.apply_url || "";
      if (url) window.open(url, "_blank", "noopener");
      document.getElementById("apply-status-badge").textContent = "Link opened — apply manually.";
      // Save folder with edited cover letter and tailored CV
      await fetch("/api/apply/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: applyPanelJobId, method, cover_letter: editedCL, cv_latex: _cvLatex2 })
      });
      return;
    }

    const qr = await fetch("/api/apply/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: applyPanelJobId, method, cover_letter: editedCL, cv_latex: _cvLatex2 })
    });
    if (!qr.ok) {
      const err = await qr.json().catch(() => ({ detail: qr.statusText }));
      throw new Error(err.detail || "Queue failed");
    }
    document.getElementById("apply-status-badge").textContent = "Queued. Starting Easy Apply...";

    const rr = await fetch(`/api/apply/run/${applyPanelJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv_pdf_path: "" })
    });
    if (!rr.ok) throw new Error(await rr.text());

    _pollApplyStatus(applyPanelJobId);
  } catch (e) {
    document.getElementById("apply-status-badge").textContent = "Error: " + e.message;
    document.getElementById("cl-confirm-btn").disabled = false;
  }
}

async function _pollApplyStatus(jobId) {
  const badge = document.getElementById("apply-status-badge");
  for (let i = 0; i < 60; i++) {
    await new Promise(res => setTimeout(res, 3000));
    try {
      const r = await fetch("/api/apply/log");
      const d = await r.json();
      const entry = (d.log || []).find(e => e.job_id === jobId);
      if (!entry) continue;
      const { status } = entry;
      badge.textContent = `Status: ${status}`;
      if (status === "applied") { badge.textContent = "✓ Application submitted!"; return; }
      if (status === "failed") { badge.textContent = "✗ Apply failed: " + (entry.error_message || "unknown"); return; }
      if (status === "awaiting_confirm") {
        badge.textContent = "⏳ Awaiting your confirmation (see screenshot below)";
        _showScreenshotConfirm(entry);
        return;
      }
    } catch (e) { /* ignore */ }
  }
  badge.textContent = "Timed out waiting for apply to complete.";
}

// ── PDF download ───────────────────────────────────────────────
async function downloadPDF() {
  const latex = document.getElementById("out-latex").textContent;
  if (!latex || latex.length < 100) {
    alert("Generate a CV first, then switch to the LaTeX tab before downloading PDF.");
    return;
  }
  const btn = document.getElementById("pdf-btn");
  const orig = btn.textContent;
  btn.textContent = "Compiling...";
  btn.disabled = true;
  try {
    const r = await fetch("/api/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latex, filename: "cv_tailored" })
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || "PDF generation failed");
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = _autoName("cv") + ".pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("PDF error: " + e.message);
  } finally {
    btn.textContent = orig;
    btn.disabled = false;
  }
}

// ── Tracker / Kanban ───────────────────────────────────────────
const KANBAN_STAGES = ["queued", "applied", "interview", "offer", "rejected", "withdrawn"];
const STAGE_LABELS = { queued: "Queued", applied: "Applied", interview: "Interview", offer: "Offer", rejected: "Rejected", withdrawn: "Withdrawn" };
let _trackerData = [];
let _drawerJobId = null;

async function loadTracker() {
  const loading = document.getElementById("tracker-loading");
  const empty = document.getElementById("tracker-empty");
  const board = document.getElementById("kanban-board");
  const stats = document.getElementById("tracker-stats");

  loading.style.display = "flex";
  empty.style.display = "none";
  board.innerHTML = "";

  try {
    const r = await fetch("/api/tracker/list");
    const d = await r.json();
    _trackerData = d.applications || [];

    if (!_trackerData.length) {
      empty.style.display = "";
      stats.innerHTML = "";
      return;
    }

    // Stats bar
    const total = _trackerData.length;
    const now = new Date();
    const weekAgo = new Date(now - 7 * 86400000);
    const thisWeek = _trackerData.filter(a => new Date((a.stages_log?.[0]?.at || "")) >= weekAgo).length;
    const interviews = _trackerData.filter(a => a.stage === "interview" || a.stage === "offer").length;
    const applied = _trackerData.filter(a => a.stage !== "queued").length;
    const responseRate = applied > 0 ? Math.round((interviews / applied) * 100) : 0;
    const avgFit = _trackerData.length
      ? Math.round(_trackerData.reduce((s, a) => s + (a.fit_score || 0) * 100, 0) / _trackerData.length)
      : 0;

    stats.innerHTML = `
      <span>Total: <strong>${total}</strong></span>
      <span>This week: <strong>${thisWeek}</strong></span>
      <span>Response rate: <strong>${responseRate}%</strong></span>
      <span>Avg fit: <strong>${avgFit}%</strong></span>
    `;

    // Build Kanban columns
    const byStage = {};
    KANBAN_STAGES.forEach(s => { byStage[s] = []; });
    _trackerData.forEach(a => {
      const stage = KANBAN_STAGES.includes(a.stage) ? a.stage : "queued";
      byStage[stage].push(a);
    });

    KANBAN_STAGES.forEach(stage => {
      const col = document.createElement("div");
      col.style = "min-width:160px;flex:1;background:var(--bg);border-radius:8px;padding:.75rem";
      const cards = byStage[stage];
      col.innerHTML = `<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.75rem">${STAGE_LABELS[stage]} <span style="font-weight:400">(${cards.length})</span></div>`;
      cards.forEach(app => {
        const score = app.fit_score ? Math.round(app.fit_score * 100) : 0;
        const scoreClass = score >= 70 ? "badge-green" : score >= 50 ? "badge-amber" : "badge-muted";
        const fuFlag = app.follow_up_due ? ` <span title="Follow-up: ${app.follow_up_due}" style="color:var(--amber)">⏰</span>` : "";
        const dateStr = (app.stages_log?.[0]?.at || "").slice(0, 10);
        const card = document.createElement("div");
        card.className = "card";
        card.style = "margin-bottom:.5rem;cursor:pointer;padding:.75rem";
        card.innerHTML = `
          <div style="font-size:12px;font-weight:600;margin-bottom:2px">${app.company || "—"}${fuFlag}</div>
          <div style="font-size:11px;color:var(--muted);margin-bottom:4px">${app.job_title || ""}</div>
          <div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap">
            ${score > 0 ? `<span class="badge ${scoreClass}" style="font-size:10px">${score}%</span>` : ""}
            <span style="font-size:10px;color:var(--hint)">${dateStr}</span>
          </div>`;
        card.onclick = () => openTrackerDrawer(app.job_id);
        col.appendChild(card);
      });
      board.appendChild(col);
    });

  } catch (e) {
    empty.textContent = "Failed to load tracker: " + e.message;
    empty.style.display = "";
  } finally {
    loading.style.display = "none";
  }
}

function filterTracker() {
  const q = (document.getElementById("tracker-search")?.value || "").toLowerCase().trim();
  document.querySelectorAll("#kanban-board .card").forEach(card => {
    const company = card.querySelector("div:first-child")?.textContent.toLowerCase() || "";
    const role = card.querySelector("div:nth-child(2)")?.textContent.toLowerCase() || "";
    card.style.display = (!q || company.includes(q) || role.includes(q)) ? "" : "none";
  });
}

async function openTrackerDrawer(jobId) {
  const app = _trackerData.find(a => a.job_id === jobId);
  if (!app) return;
  _drawerJobId = jobId;

  document.getElementById("drawer-title").textContent = `${app.company} — ${app.job_title}`;

  // Fetch files list
  let files = [];
  try {
    const fr = await fetch(`/api/tracker/${jobId}/files`);
    if (fr.ok) files = (await fr.json()).files || [];
  } catch (e) {}

  const content = document.getElementById("drawer-content");
  const stageOptions = KANBAN_STAGES.map(s => `<option value="${s}"${s === app.stage ? " selected" : ""}>${STAGE_LABELS[s]}</option>`).join("");

  content.innerHTML = `
    <div class="field">
      <label class="lbl">Stage</label>
      <select id="drawer-stage" onchange="_trackerUpdateStage('${jobId}', this.value)">${stageOptions}</select>
    </div>
    <div class="field">
      <label class="lbl">Follow-up date</label>
      <input type="date" id="drawer-followup" value="${app.follow_up_due || ""}" onchange="_trackerFollowUp('${jobId}', this.value)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:var(--radius)" />
    </div>
    <div class="field">
      <label class="lbl">Notes</label>
      <textarea id="drawer-notes" rows="4" style="width:100%;padding:8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius)"
        onblur="_trackerUpdateNotes('${jobId}', this.value)">${app.notes || ""}</textarea>
    </div>
    ${app.skill_gaps?.length ? `
    <div class="field">
      <label class="lbl">Skill gaps</label>
      <div class="tag-row">${app.skill_gaps.map(g => `<span class="tag gap">${g}</span>`).join("")}</div>
    </div>` : ""}
    ${files.length ? `
    <div class="field">
      <label class="lbl">Files</label>
      <div style="display:flex;flex-wrap:wrap;gap:.5rem">
        ${files.filter(f => f !== "status.json").map(f => `
          <button class="btn btn-sm btn-ghost" onclick="_viewTrackerFile('${jobId}','${f}')">${f}</button>`).join("")}
      </div>
    </div>` : ""}
    <div id="drawer-file-view" style="display:none;margin-top:1rem">
      <div style="font-size:11px;font-weight:600;color:var(--muted);margin-bottom:.25rem" id="drawer-file-name"></div>
      <pre style="font-size:11px;line-height:1.6;white-space:pre-wrap;background:var(--bg);padding:10px;border-radius:var(--radius);border:1px solid var(--border);max-height:300px;overflow-y:auto" id="drawer-file-content"></pre>
    </div>
  `;

  document.getElementById("tracker-drawer").style.display = "";
  document.getElementById("tracker-overlay").style.display = "";
}

function closeTrackerDrawer() {
  document.getElementById("tracker-drawer").style.display = "none";
  document.getElementById("tracker-overlay").style.display = "none";
  _drawerJobId = null;
}

async function _trackerUpdateStage(jobId, stage) {
  await fetch(`/api/tracker/${jobId}/stage`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage })
  });
  const app = _trackerData.find(a => a.job_id === jobId);
  if (app) { app.stage = stage; }
  loadTracker();
}

async function _trackerUpdateNotes(jobId, notes) {
  await fetch(`/api/tracker/${jobId}/notes`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes })
  });
}

async function _trackerFollowUp(jobId, date) {
  await fetch(`/api/tracker/${jobId}/follow_up`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ follow_up_due: date || null })
  });
}

async function _viewTrackerFile(jobId, filename) {
  const area = document.getElementById("drawer-file-view");
  const nameEl = document.getElementById("drawer-file-name");
  const contentEl = document.getElementById("drawer-file-content");
  nameEl.textContent = filename;
  contentEl.textContent = "Loading...";
  area.style.display = "";
  try {
    const r = await fetch(`/api/tracker/${jobId}/file/${filename}`);
    contentEl.textContent = r.ok ? await r.text() : "Failed to load file.";
  } catch (e) {
    contentEl.textContent = "Error: " + e.message;
  }
}
