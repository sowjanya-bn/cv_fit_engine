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
});

// ── tab routing ────────────────────────────────────────────────
function switchTab(t) {
  const tabs = ["strategy", "live", "discover", "shortlist", "tailor", "output", "settings"];
  tabs.forEach(k => {
    document.getElementById("panel-" + k).classList.toggle("active", k === t);
    document.getElementById("nav-" + k).classList.toggle("active", k === t);
  });
  if (t === "shortlist") renderShortlist();
  if (t === "tailor") populateTailorSelect();
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

async function discoverJobs() {
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

Candidate: Naga Sowjanya Barla. Key credentials: First-author ESWC 2026 paper on RAG+Knowledge Graphs (arXiv:2604.02545), MSc Data Science & AI (Univ. Liverpool 2026), 13 years backend engineering (TCS), Python/Java/RDF/SPARQL/RAG/LLMs. Based in Liverpool UK.

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
    discoveredJobs = data.jobs || [];
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

function renderJobCards() {
  const c = document.getElementById("job-cards");
  c.innerHTML = "";
  const slIds = new Set(shortlist.map(j => j.id));
  discoveredJobs.forEach(job => {
    const s = job.fit_score || 0;
    const bc = s >= 80 ? "badge-green" : s >= 65 ? "badge-amber" : "badge-muted";
    const fc = s >= 80 ? "fill-hi" : s >= 65 ? "fill-mid" : "fill-lo";
    const d = document.createElement("div");
    d.className = "job-card" + (slIds.has(job.id) ? " selected" : "");
    d.innerHTML = `
      <div class="jc-check">✓</div>
      <div style="font-size:14px;font-weight:600;margin-bottom:2px">${job.title}</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px">${job.company} · ${job.location}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <span class="badge ${bc}">${s}% fit</span>
        <span class="badge badge-muted">${job.type || ""}</span>
        ${job.salary ? `<span style="font-size:12px;color:var(--muted)">${job.salary}</span>` : ""}
      </div>
      <div class="score-bar"><div class="score-fill ${fc}" style="width:${s}%"></div></div>
      <div style="font-size:12px;color:var(--muted);margin-top:6px;line-height:1.5">${job.fit_reason || ""}</div>
      ${job.notable ? `<div style="font-size:11px;color:var(--navy);margin-top:6px;padding:4px 8px;background:var(--navy-light);border-radius:4px">${job.notable}</div>` : ""}
      ${job.why_apply ? `<div style="font-size:11px;color:var(--teal);margin-top:4px;padding:4px 8px;background:var(--teal-light);border-radius:4px">Lead with: ${job.why_apply}</div>` : ""}
      <div class="tag-row">${(job.tags || []).slice(0, 6).map(t => `<span class="tag">${t}</span>`).join("")}</div>
    `;
    d.onclick = () => toggleShortlist(job, d);
    c.appendChild(d);
  });
}

// ── shortlist ──────────────────────────────────────────────────
function toggleShortlist(job, el) {
  const idx = shortlist.findIndex(j => j.id === job.id);
  if (idx === -1) { shortlist.push(job); el.classList.add("selected"); }
  else { shortlist.splice(idx, 1); el.classList.remove("selected"); }
  updateSlBadge();
}

function updateSlBadge() {
  const b = document.getElementById("sl-badge");
  if (shortlist.length) { b.textContent = shortlist.length; b.style.display = ""; }
  else b.style.display = "none";
}

function clearShortlist() {
  shortlist = [];
  updateSlBadge();
  renderShortlist();
  renderJobCards();
}

function renderShortlist() {
  const c = document.getElementById("sl-cards");
  const emp = document.getElementById("sl-empty");
  const act = document.getElementById("sl-actions");
  c.innerHTML = "";
  if (!shortlist.length) { emp.style.display = ""; act.style.display = "none"; return; }
  emp.style.display = "none"; act.style.display = "flex";
  shortlist.forEach(job => {
    const s = job.fit_score || 0;
    const bc = s >= 80 ? "badge-green" : s >= 65 ? "badge-amber" : "badge-muted";
    const d = document.createElement("div");
    d.className = "card";
    d.innerHTML = `
      <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:6px">
        <div style="flex:1">
          <div class="card-title">${job.title}</div>
          <div class="card-sub">${job.company} · ${job.location} · ${job.salary || ""}</div>
        </div>
        <span class="badge ${bc}">${s}% fit</span>
        <button class="btn btn-sm btn-primary" onclick="tailorJob('${job.id}')">Tailor →</button>
      </div>
      <div style="font-size:12px;line-height:1.6;color:var(--muted)">${job.jd_summary || ""}</div>
      <div class="tag-row">${(job.tags || []).map(t => `<span class="tag">${t}</span>`).join("")}</div>`;
    c.appendChild(d);
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
      `CANDIDATE:\nNaga Sowjanya Barla — AI Engineer, 13 yrs exp, MSc Data Science & AI (Liverpool 2026), ESWC 2026 first-author paper on RAG+KG, KG-RAG dissertation, Python/Java/RDF/SPARQL/RAG/LLMs, TCS backend engineering at scale.\nSkills: ${Object.values(PROFILE.skills).flat().join(", ")}\nAchievements: ${PROFILE.achievements.map(a => a.title).join("; ")}\n\nJD:\n${jd}`
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
  const jd = document.getElementById("jd-ta").value.trim();
  if (!jd) { showTailorErr("Paste a job description first."); return; }
  const variant = document.getElementById("cv-variant").value;
  const intensity = document.getElementById("tailor-intensity").value;
  const wantCover = document.getElementById("want-cover").value === "yes";
  const tone = document.getElementById("cover-tone").value;
  const emph = document.getElementById("emph-notes").value;
  const role = ROLES.find(r => r.id === variant) || ROLES[0];
  clearTailorErr();

  switchTab("output");
  document.getElementById("out-loading").style.display = "flex";
  document.getElementById("out-msg").textContent = "Rewriting bullets and generating tailored CV...";
  document.getElementById("out-area").style.display = "none";
  document.getElementById("out-empty").style.display = "none";

  const sys = `You are an elite CV writer specialising in AI/ML/Semantic Web roles. You have this candidate's full profile.

CANDIDATE: Naga Sowjanya Barla — AI Engineer, 13 yrs exp, ESWC 2026 first-author paper, MSc Data Science & AI (Liverpool), KG-RAG dissertation, Python/Java/RDF/SPARQL.

CRITICAL RULES:
- The ESWC 2026 paper is her single biggest differentiator. It must appear prominently — in an Achievements section that comes early in the CV, or in the summary.
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

  try {
    const raw = await callClaude(sys,
      `FULL PROFILE:\n${JSON.stringify(PROFILE, null, 2)}\n\nJOB DESCRIPTION:\n${jd}\n\nGenerate cover letter: ${wantCover}`
    );
    const data = parseJSON(raw);
    lastOutput = { data, wantCover, role, jd };
    renderOutput(data, wantCover, role);
    document.getElementById("out-area").style.display = "block";
    document.getElementById("cover-tab-btn").style.display = wantCover ? "" : "none";
  } catch (e) {
    document.getElementById("out-loading").innerHTML = `<span style="color:var(--red)">Generation failed: ${e.message}</span>`;
  } finally {
    document.getElementById("out-loading").style.display = "none";
  }
}

// ── output rendering ───────────────────────────────────────────
function renderOutput(data, wantCover, role) {
  const sc = data.match_score || 0;
  document.getElementById("out-metrics").innerHTML = `
    <div class="metric"><div class="metric-val">${sc}%</div><div class="metric-lbl">estimated match</div></div>
    <div class="metric" style="grid-column:span 2">
      <div style="font-size:12px;color:var(--muted);line-height:1.6;text-align:left;padding-top:4px">${data.key_changes || ""}</div>
    </div>`;

  // CV preview
  let h = `
    <div style="margin-bottom:1.5rem">
      <div style="font-size:22px;font-weight:700;color:var(--navy)">${PROFILE.name}</div>
      <div style="font-size:13px;color:var(--muted);font-style:italic;margin-top:2px">${data.headline || role.label}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:5px">${PROFILE.email} · ${PROFILE.phone} · ${PROFILE.location}</div>
      <div style="font-size:12px;color:var(--muted)">${PROFILE.linkedin} · ${PROFILE.github}</div>
    </div>`;

  // Achievements always first and prominent
  h += `<div class="cv-section">Notable Achievements</div>
    <ul class="cv-bullets">
      ${PROFILE.achievements.map(a => `<li><strong>${a.title}</strong><br><span style="font-size:12px;color:var(--muted)">${a.detail}</span></li>`).join("")}
    </ul>`;

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
  lines.push("ACHIEVEMENTS");
  PROFILE.achievements.forEach(a => { lines.push("★ " + a.title); lines.push("  " + a.detail); });
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

  // Achievements — always first
  tex += `\\section{Achievements}\n\\begin{itemize}\n`;
  PROFILE.achievements.forEach(a => {
    tex += `  \\item \\textbf{${esc(a.title)}} --- {\\small\\color{muted}${esc(a.detail)}}\n`;
  });
  tex += `\\end{itemize}\n\n`;

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
  a.download = "cv_tailored.tex";
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
    a.download = "cv_tailored.pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("PDF error: " + e.message);
  } finally {
    btn.textContent = orig;
    btn.disabled = false;
  }
}
