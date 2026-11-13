/* Step 1, "You": who the person is today. Everything is optional; each part makes the result
   more accurate. The profile page, the 36-statement interest questionnaire and the skills check. */
"use strict";

const TOP_TOOLS = 30;  // the tools most occupations list are shown first; the rest are found by search
const CV_MAX_BYTES = 2_000_000;
const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/";
const ZONES = [1, 2, 3, 4, 5];

const leaveDemo = () => { state.demo = null; };
const changed = () => { leaveDemo(); save(); cache.clear(); redraw(); };

PAGES.you = async (args) => {
  if (args[0] === "interests") return interestsPage();
  if (args[0] === "skills") return skillsPage();
  return profilePage();
};

/* ---------- the profile ---------- */

async function profilePage() {
  const [techs, occs, people] = await Promise.all([cached("/api/technologies"), cached("/api/occupations"), cached("/api/profiles")]);
  const demo = state.demo && people.find((p) => p.profile_id === state.demo);
  const quiz = quizDone() ? await cached("/api/questionnaire/score", { answers: state.answers }) : null;
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 1)} · ${t("nav.you")}</p><h1>${t("you.h1")}</h1><p class="lead">${t("you.lead")}</p></header>
    ${demo ? `<div class="note row between"><span>${t("you.demo", `<strong>${esc(demo.name)}</strong>`)}</span><button type="button" class="btn small" data-act="own">${t("you.demo.own")}</button></div>` : ""}
    <section class="stack"><p class="small muted">${t("you.or.demo")}</p>
      <div class="tags">${people.map((p) => `<button type="button" class="toggle" data-act="demo" data-id="${esc(p.profile_id)}" aria-pressed="${state.demo === p.profile_id}">${esc(p.name)} · ${t("kind." + (p.kind || "student"))}</button>`).join("")}</div></section>
    ${whoCard(occs)}
    ${fieldsCard()}
    ${cvCard()}
    ${toolsCard(techs)}
    ${interestCard(quiz)}
    ${skillsCard()}
    <section class="card stack">
      <h2>${t("you.more.h")}</h2>
      <div class="grid three">
        <label class="field">${t("you.zone")}<select data-on="zone">${ZONES.map((z) => `<option value="${z}"${state.zone === z ? " selected" : ""}>${t("zone." + z)}</option>`).join("")}</select></label>
        <label class="field">${t("you.study")}<select data-on="study">${[0, 1, 2].map((n) => `<option value="${n}"${(state.study || 0) === n ? " selected" : ""}>${t("study." + n)}</option>`).join("")}</select></label>
        <label class="field">${t("you.hours")}<select data-on="hours">${[3, 5, 8, 10, 15, 20].map((h) => `<option value="${h}"${state.hours === h ? " selected" : ""}>${t("you.hours.n", h)}</option>`).join("")}</select></label>
      </div>
      <p class="small muted">${t("you.zone.note")}</p>
    </section>
    <div class="row"><a class="btn primary" href="#/matches">${t("you.go")} →</a><a class="btn" href="#/radar">${t("you.radar")}</a>
      <span class="small muted">${t("you.saved")}</span></div>
  </div>`;
}

function whoCard(occs) {
  const kinds = ["student", "working", "switcher"];
  const current = occs.find((o) => o.occ_id === state.currentOcc);
  const picker = state.kind === "student" ? "" : `<div class="stack tight">
      <label class="field">${t("you.occ")}<input type="search" placeholder="${esc(t("you.occ.ph"))}" value="${esc(ui.occQuery)}" data-in="occQuery" aria-label="${esc(t("you.occ"))}"></label>
      ${current ? `<p class="small"><span class="chip brand">${esc(current.title)}</span> <button type="button" class="btn small ghost" data-act="occClear">${t("you.occ.clear")}</button></p>` : ""}
      <div class="tags" id="occ-list">${occChoices(occs)}</div>
      <p class="small muted">${t("you.occ.note")}</p></div>`;
  return `<section class="card stack">
    <h2>${t("you.who.h")}</h2>
    <div class="seg" role="group" aria-label="${t("you.who.h")}">${kinds.map((k) =>
      `<button type="button" data-act="kind" data-id="${k}" aria-pressed="${!state.demo && state.kind === k}">${t("kind." + k)}</button>`).join("")}</div>
    <p class="small muted">${t("you.who." + state.kind)}</p>
    ${picker}
  </section>`;
}
const occChoices = (occs) => {
  if (!ui.occQuery.trim()) return "";
  const found = occMatches(occs, ui.occQuery, "", 12);
  return found.length ? found.map((o) => `<button type="button" class="toggle" data-act="occPick" data-id="${esc(o.occ_id)}" aria-pressed="${state.currentOcc === o.occ_id}">${esc(o.title)}</button>`).join("")
    : `<span class="small muted">${t("you.occ.none")}</span>`;
};

/* Fields: tap once for "interested", twice for "not for me", a third time to clear. */
function fieldsCard() {
  const ids = Object.keys(FIELDS);
  return `<section class="card stack">
    <div class="row between"><h2>${t("fields.h")}</h2><span class="chip plain">${t("optional")}</span></div>
    <p class="muted small">${t("fields.p")}</p>
    <div class="tags">${ids.map((id) => {
      const v = state.fields[id];
      const mark = v === 100 ? "★ " : v === 0 ? "✕ " : "";
      return `<button type="button" class="toggle${v === 0 ? " no" : ""}" data-act="field" data-id="${id}" aria-pressed="${v === 100}" title="${esc(fieldAbout(id))}">${mark}${esc(fieldName(id))}</button>`;
    }).join("")}</div>
    <p class="tiny muted">${t("fields.legend")}</p>
  </section>`;
}

function cvCard() {
  const r = ui.cvResult;
  const result = r ? `<div class="card flat stack tight">
      <p>${esc(r.summary)}</p>
      <p class="src">${t("cv.by.match")}</p>
      ${r.technologies.length ? `<div><p class="small strong">${t("cv.found", r.technologies.length)}</p><div class="tags">${r.technologies.map((x) => `<span class="chip brand" title="${esc(t("cv.matched", x.matched))}">${esc(x.skill_name)}</span>`).join("")}</div></div>` : `<p class="small muted">${t("cv.none")}</p>`}
      ${r.qualifications.length ? `<p class="small"><span class="strong">${t("cv.quals")}</span> ${r.qualifications.map((q) => esc(q.title)).join(" · ")}</p>` : ""}
      ${r.knowledge.length ? `<p class="small"><span class="strong">${t("cv.subjects")}</span> ${r.knowledge.map((k) => `${esc(k.name)} (${t("level.n", fmt(k.level, 0))})`).join(" · ")}</p>` : ""}
      ${r.occupations.length ? `<p class="small"><span class="strong">${t("cv.titles")}</span> ${r.occupations.map((o) => `${esc(o.matched)} → ${occLink(o.occ_id, o.title)}`).join(" · ")}</p>` : ""}
    </div>` : state.cv ? `<p class="note">${t("cv.kept")}</p>` : "";
  return `<section class="card stack">
    <div class="row between"><h2>${t("cv.h")}</h2><span class="chip plain">${t("optional")}</span></div>
    <p class="muted small">${t("cv.p")}</p>
    <div class="row">
      <label class="btn"><input type="file" class="visually-hidden" accept=".pdf,.docx,.txt" data-on="cvFile">${t("cv.upload")}</label>
      <button type="button" class="btn ghost" data-act="cvSample">${t("cv.sample")}</button>
      <button type="button" class="btn ghost" data-act="cvPaste" aria-expanded="${Boolean(ui.cvPaste)}">${t("cv.paste")}</button>
      ${state.cv ? `<button type="button" class="btn ghost" data-act="cvClear">${t("cv.clear")}</button>` : ""}
    </div>
    ${ui.cvPaste ? `<div class="stack tight"><textarea id="cv-text" placeholder="${esc(t("cv.paste.ph"))}"></textarea><div><button type="button" class="btn small primary" data-act="cvRead">${t("cv.read")}</button></div></div>` : ""}
    ${ui.busy.cv ? loading(t("cv.reading")) : ""}
    ${ui.cvError ? `<p class="err">${esc(ui.cvError)}</p>` : ""}
    ${result}
    <p class="src">${t("cv.privacy")}</p>
  </section>`;
}

const sortedTools = (techs) => [...techs].sort((a, b) => b.occupations - a.occupations || a.name.localeCompare(b.name));
function toolsCard(techs) {
  const picked = new Set(state.techs);
  return `<section class="card stack">
    <div class="row between"><h2>${t("tools.h")}</h2><span class="chip brand">${t("tools.count", picked.size)}</span></div>
    <p class="muted small">${t("tools.p")}</p>
    <input type="search" placeholder="${esc(t("tools.search", techs.length))}" value="${esc(ui.techQuery)}" data-in="techQuery" aria-label="${esc(t("tools.search", techs.length))}">
    <div class="tags" id="tool-list">${toolChips(techs, picked)}</div>
    <p class="src">${t("tools.src")}</p>
  </section>`;
}
function toolChips(techs, picked) {
  const q = ui.techQuery.trim().toLowerCase();
  const sorted = sortedTools(techs);
  const shown = q ? sorted.filter((x) => x.name.toLowerCase().includes(q)).slice(0, 60)
    : sorted.filter((x, i) => i < TOP_TOOLS || picked.has(x.tech_id));
  return shown.length ? shown.map((x) => `<button type="button" class="toggle" data-act="tech" data-id="${esc(x.tech_id)}" aria-pressed="${picked.has(x.tech_id)}" title="${esc(x.category)}">${esc(x.name)}</button>`).join("")
    : `<span class="small muted">${t("tools.none")}</span>`;
}

function interestCard(quiz) {
  if (quiz) {
    return `<section class="card stack">
      <div class="row between"><h2>${t("int.h")}</h2><span class="chip rising">${t("int.done")}</span></div>
      <p>${t("int.result", `<strong>${esc(quiz.code)}</strong>`, quiz.code.split("").map((k) => t("riasec.short." + k)).join(", "))}</p>
      <div class="row"><a class="btn small" href="#/you/interests">${t("int.see")}</a><button type="button" class="btn small ghost" data-act="quizClear">${t("int.clear")}</button></div>
    </section>`;
  }
  const started = Array.isArray(state.answers) && state.answers.some((a) => a !== null);
  return `<section class="card stack">
    <div class="row between"><h2>${t("int.h")}</h2><span class="chip plain">${t("optional")}</span></div>
    <p class="muted small">${t("int.p")}</p>
    <div class="row"><a class="btn small" href="#/you/interests">${t(started ? "int.continue" : "int.start")}</a></div>
  </section>`;
}

function skillsCard() {
  const n = ratedCount();
  return `<section class="card stack">
    <div class="row between"><h2>${t("sk.h")}</h2><span class="chip ${n ? "rising" : "plain"}">${n ? t("sk.count", n) : t("optional")}</span></div>
    <p class="muted small">${t("sk.p")}</p>
    <div class="row"><a class="btn small" href="#/you/skills">${t(n ? "sk.edit" : "sk.start")}</a>
      ${n ? `<button type="button" class="btn small ghost" data-act="skillsClear">${t("sk.clear")}</button>` : ""}</div>
  </section>`;
}

Object.assign(ACT, {
  own: () => { leaveDemo(); save(); redraw(); },
  kind: (el) => { state.kind = el.dataset.id; if (state.kind === "student") state.currentOcc = ""; changed(); },
  occPick: (el) => { state.currentOcc = el.dataset.id; ui.occQuery = ""; changed(); },
  occClear: () => { state.currentOcc = ""; changed(); },
  field: (el) => {
    const id = el.dataset.id, v = state.fields[id];
    if (v === undefined) state.fields[id] = 100; else if (v === 100) state.fields[id] = 0; else delete state.fields[id];
    changed();
  },
  tech: (el) => {
    const id = el.dataset.id;
    state.techs = state.techs.includes(id) ? state.techs.filter((x) => x !== id) : [...state.techs, id];
    changed();
  },
  cvPaste: () => { ui.cvPaste = !ui.cvPaste; redraw(); },
  cvRead: () => { const text = $("#cv-text").value; if (text.trim()) readCV({ text }); },
  cvSample: async () => readCV({ text: await fetch("/static/sample_cv.txt").then((r) => r.text()) }),
  cvClear: () => { state.cv = null; ui.cvResult = null; changed(); },
  quizClear: () => { state.answers = null; ui.quizAt = null; changed(); },
  skillsClear: () => { if (confirm(t("sk.clear.confirm"))) { state.skills = {}; changed(); } },
});
Object.assign(ON, {
  zone: (el) => { state.zone = Number(el.value); changed(); },
  study: (el) => { state.study = Number(el.value); changed(); },
  hours: (el) => { state.hours = Number(el.value); save(); cache.clear(); },
  occQuery: async (el) => {  // filter in place, so the search box keeps its focus
    ui.occQuery = el.value;
    const list = $("#occ-list");
    if (list) list.innerHTML = occChoices(await cached("/api/occupations"));
  },
  techQuery: async (el) => {
    ui.techQuery = el.value;
    const list = $("#tool-list");
    if (list) list.innerHTML = toolChips(await cached("/api/technologies"), new Set(state.techs));
  },
  cvFile: async (el) => {
    const file = el.files && el.files[0];
    if (!file) return;
    try { readCV(await cvRequestBody(file)); } catch (e) { ui.cvError = e.message; redraw(); }
  },
});

/* PDF and text files are read here in the browser; a .docx goes to the server as base64. */
function loadPdfJs() {
  if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = PDFJS + "pdf.min.js";
    s.onload = () => { window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS + "pdf.worker.min.js"; resolve(window.pdfjsLib); };
    s.onerror = () => reject(new Error(t("cv.err.pdf")));
    document.head.appendChild(s);
  });
}
async function pdfText(file) {
  const pdfjs = await loadPdfJs();
  const doc = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
  const pages = [];
  for (let i = 1; i <= Math.min(doc.numPages, 10); i++) {
    const content = await (await doc.getPage(i)).getTextContent();
    pages.push(content.items.map((it) => it.str + (it.hasEOL ? "\n" : " ")).join(""));
  }
  return pages.join("\n");
}
async function cvRequestBody(file) {
  const name = file.name.toLowerCase();
  if (file.size > CV_MAX_BYTES) throw new Error(t("cv.err.size"));
  if (name.endsWith(".pdf")) return { text: await pdfText(file) };
  if (name.endsWith(".txt")) return { text: await file.text() };
  if (name.endsWith(".docx")) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return { docx_base64: btoa(bin) };
  }
  throw new Error(t("cv.err.type"));
}
/* The CV text is used for one request and never kept: only the tools, education level, subject
   levels and field evidence it gave stay in this browser. */
async function readCV(body) {
  ui.busy.cv = true; ui.cvError = null; redraw();
  try {
    const r = await request("/api/cv/summary", body);
    ui.cvResult = r;
    state.cv = { fields: r.cv_fields, why: r.cv_why, skills: r.cv_skills };
    state.techs = [...new Set([...state.techs, ...r.technologies.map((x) => x.skill_id)])];
    if (r.education_job_zone) state.zone = r.education_job_zone;
    ui.cvPaste = false;
    leaveDemo(); save(); cache.clear();
  } catch (e) {
    ui.cvError = e.message;
  }
  ui.busy.cv = false; redraw();
}

/* ---------- the interest questionnaire: 36 statements, about 6 minutes ---------- */

const TYPE_KEYS = ["R", "I", "A", "S", "E", "C"];
async function interestsPage() {
  const q = await cached("/api/questionnaire");
  const head = `<p class="eyebrow">${t("step", 1)} · ${t("int.h")}</p>`;
  if (quizDone() && ui.quizAt === null) {
    const r = await cached("/api/questionnaire/score", { answers: state.answers });
    return `<div class="quiz stack">${head}<h1>${t("int.res.h", esc(r.code))}</h1>
      ${r.warnings.map((w) => `<p class="warn">${esc(w.text)}</p>`).join("")}
      <section class="card stack"><h2>${t("int.res.types")}</h2>${TYPE_KEYS.map((k) =>
        `<div class="meter"><span><strong>${k}</strong> · ${t("riasec." + k)}</span>${bar(r.percent[k], r.code.includes(k) ? "" : "steady")}<span class="v">${fmt(r.percent[k], 0)}</span></div>`).join("")}
        <p class="small muted">${t("int.res.note")}</p></section>
      <div class="row"><a class="btn primary" href="#/matches">${t("you.go")} →</a><a class="btn" href="#/you">${t("back.profile")}</a>
        <button type="button" class="btn ghost" data-act="quizStart">${t("int.again")}</button></div>
      <p class="src">${esc(q.attribution)}</p></div>`;
  }
  if (!Array.isArray(state.answers) || (ui.quizAt === null && !state.answers.some((a) => a !== null))) {
    return `<div class="quiz stack">${head}<h1>${t("int.intro.h")}</h1><p class="lead">${t("int.intro.p")}</p>
      <div class="tags"><span class="chip plain">${t("int.intro.n", q.items.length)}</span><span class="chip plain">${t("int.intro.time")}</span></div>
      <div class="row"><button type="button" class="btn primary" data-act="quizStart">${t("int.start")}</button><a class="btn" href="#/you">${t("back.profile")}</a></div>
      <p class="src">${esc(q.attribution)}</p></div>`;
  }
  const first = state.answers.indexOf(null);
  const at = clamp(ui.quizAt ?? (first === -1 ? 0 : first), 0, q.items.length - 1);
  ui.quizAt = at;
  const text = LANG === "en" ? q.items[at].text : (QUIZ_I18N[LANG] || [])[at] || q.items[at].text;
  return `<div class="quiz stack">${head}
    <div class="row between small muted"><span>${t("int.item", at + 1, q.items.length)}</span><a href="#/you">${t("int.pause")}</a></div>
    <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${q.items.length}" aria-valuenow="${at}"><i style="width:${Math.round((at / q.items.length) * 100)}%"></i></div>
    <p class="muted">${t("int.stem")}</p>
    <div class="card"><p style="font-size:1.2rem;font-weight:650" id="quiz-item">${esc(text)}</p></div>
    <div class="options scale" role="group" aria-labelledby="quiz-item">${[1, 2, 3, 4, 5].map((v) =>
      `<button type="button" data-act="quizAnswer" data-v="${v}" aria-pressed="${state.answers[at] === v}">${t("scale." + v)}</button>`).join("")}</div>
    <div class="row">${at > 0 ? `<button type="button" class="btn small ghost" data-act="quizBack">← ${t("back")}</button>` : ""}</div>
  </div>`;
}
Object.assign(ACT, {
  quizStart: () => { state.answers = Array(QUIZ_LENGTH).fill(null); ui.quizAt = 0; leaveDemo(); save(); redraw(); },
  quizBack: () => { ui.quizAt = Math.max(0, (ui.quizAt || 0) - 1); redraw(); },
  quizAnswer: (el) => {
    state.answers[ui.quizAt] = Number(el.dataset.v);
    const next = state.answers.indexOf(null);
    ui.quizAt = next === -1 ? null : (ui.quizAt + 1 < QUIZ_LENGTH && state.answers[ui.quizAt + 1] === null ? ui.quizAt + 1 : next);
    leaveDemo(); save(); cache.clear(); redraw();
    window.scrollTo(0, 0);
  },
});

/* ---------- the skills check: pick the hardest O*NET example you can already do ---------- */

const likedFields = () => Object.entries(state.fields).filter(([, v]) => v === 100).map(([k]) => k);
async function skillsPage() {
  const fields = likedFields().join(",");
  const plan = await cached(`/api/skillcheck?fields=${encodeURIComponent(fields)}${ui.skillsAll ? "&all=1" : ""}`);
  const head = `<p class="eyebrow">${t("step", 1)} · ${t("sk.h")}</p>`;
  const done = plan.questions.filter((q) => q.element_id in state.skills).length;
  const card = (q) => {
    const mine = state.skills[q.element_id];
    return `<section class="card stack tight" id="sk-${esc(q.element_id)}">
      <div class="row between"><h2 style="font-size:1.05rem">${esc(q.name)}</h2><span class="chip plain">${t(q.kind === "skill" ? "skill.kind.general" : "skill.kind.knowledge")}</span></div>
      <p class="tiny muted">${esc(q.description)}</p>
      <div class="options">${q.options.map((o) => `<button type="button" data-act="skillLevel" data-id="${esc(q.element_id)}" data-v="${o.level}" aria-pressed="${mine === o.level}">
        ${o.text ? `<span class="tiny muted">${t("level.n", fmt(o.level, 0))}</span> ${esc(o.text)}` : t("sk.notyet")}</button>`).join("")}</div>
    </section>`;
  };
  return `<div class="stack">${head}<h1>${t("sk.h1")}</h1><p class="lead">${t("sk.lead")}</p>
    <p class="note small">${fields ? t("sk.for", likedFields().map((f) => esc(fieldName(f))).join(", ")) : t("sk.forall")}</p>
    <div class="row between"><span class="small strong">${t("sk.progress", done, plan.questions.length)}</span><a class="btn small" href="#/you">${t("back.profile")}</a></div>
    ${plan.questions.map(card).join("")}
    ${!ui.skillsAll && plan.more.length ? `<div class="row"><button type="button" class="btn" data-act="skillsAll">${t("sk.more", plan.more.length)}</button></div>` : ""}
    <div class="row"><a class="btn primary" href="#/matches">${t("you.go")} →</a></div>
    <p class="src">${t("sk.src")}</p></div>`;
}
Object.assign(ACT, {
  skillLevel: (el) => {
    const id = el.dataset.id, v = Number(el.dataset.v);
    state.skills[id] = v;
    leaveDemo(); save(); cache.clear();
    $$(`[data-act="skillLevel"][data-id="${CSS.escape(id)}"]`).forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.v) === v)));
  },
  skillsAll: () => { ui.skillsAll = true; redraw(); },
});
