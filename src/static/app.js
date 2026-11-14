/* Future Skills web app: the core. Hash-routed pages over the JSON API in src/main.py.
   The six steps of the journey are the whole navigation:
     1 You  2 Radar  3 Matches  4 Pathway  5 SDG  6 Futures      (+ Sources)
   you.js, explore.js and futures.js hold the pages; this file holds what they share. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const app = $("#app");

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
const fmt = (n, d = 1) => (n === null || n === undefined || n === "" || Number.isNaN(Number(n)) ? "–" : Number(n).toFixed(d));
const signed = (n, d = 1) => (n === null || n === undefined ? "–" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(d)}`);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/* ---------- the person: kept in this browser only; nothing personal is saved on the server ---------- */

const STORE_KEY = "future-skills-v3";
const SCENARIO_IDS = ["slow", "moderate", "fast"];
const blank = () => ({
  kind: "student", currentOcc: "", zone: 4, study: 0, hours: 5, fields: {}, answers: null, cv: null, skills: {}, techs: [],
  demo: null, sdgGoals: [], showRestricted: false, scenario: "moderate", adoption: 0.25, occId: null, done: {}, seen: null, learner: null,
});
function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
    return Object.assign(blank(), saved && typeof saved === "object" ? saved : {});
  } catch (e) { return blank(); }
}
let state = loadState();
function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* storage off: keep it in memory */ }
}
const ui = { open: {}, why: {}, techQuery: "", occQuery: "", radarTab: "fields", radarFilter: "all", radarField: "",
  radarQuery: "", showMore: false, news: null, whatif: null, custom: null, cvResult: null, cvError: null, ad: null,
  adText: "", busy: {}, quizAt: null, skillsAll: false };

const QUIZ_LENGTH = 36;
const quizDone = () => Array.isArray(state.answers) && state.answers.length === QUIZ_LENGTH && state.answers.every((a) => a !== null);
const ratedCount = () => Object.keys(state.skills || {}).length;
const hasProfile = () => Boolean(state.demo || state.techs.length || quizDone() || ratedCount() || state.cv
  || Object.keys(state.fields).length || ((state.kind !== "student") && state.currentOcc));

/* The person as the API wants them. A demo person is sent by id; their answers are in the data. */
function profileBody() {
  if (state.demo) return { profile_id: state.demo };
  const b = { kind: state.kind, education_job_zone: state.zone, technologies: state.techs };
  if (state.study) b.study_levels = state.study;  // how many levels above their own they would study for
  if (state.kind !== "student" && state.currentOcc) b.current_occupation = state.currentOcc;
  if (Object.keys(state.fields).length) b.fields = state.fields;
  if (quizDone()) b.interest_answers = state.answers;
  if (ratedCount()) b.skills = state.skills;
  if (state.cv) {
    if (Object.keys(state.cv.fields || {}).length) { b.cv_fields = state.cv.fields; b.cv_why = state.cv.why || {}; }
    if (Object.keys(state.cv.skills || {}).length) b.cv_skills = state.cv.skills;
  }
  const missions = state.lab && state.lab.missions ? Object.keys(state.lab.missions).filter((k) => state.lab.missions[k].done) : [];
  if (missions.length) b.missions_done = missions;  // finished practice missions (lab.js) count as skill evidence
  return b;
}
const scenarioBody = () => (state.scenario === "custom" ? { adoption: state.adoption } : { scenario: state.scenario });
const scenarioQuery = () => (state.scenario === "custom" ? `adoption=${state.adoption}` : `scenario=${state.scenario}`);
const matchBody = (extra = {}) => ({ ...profileBody(), ...scenarioBody(), hours_per_week: state.hours, sdg_goals: state.sdgGoals, show_restricted: Boolean(state.showRestricted), ...extra });

/* ---------- the API: answers are kept for the visit, so moving between steps costs no data ---------- */

const cache = new Map();
async function request(path, body) {
  let res;
  try {
    res = await fetch(path, body === undefined ? undefined
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch (e) {  // fetch() rejects only when the server cannot be reached
    throw Object.assign(new Error(t("err.offline")), { offline: true });
  }
  let answer = {};
  try { answer = await res.json(); } catch (e) { /* not JSON: the status says what happened */ }
  if (!res.ok) throw new Error(answer.error || `HTTP ${res.status}`);
  return answer;
}
function cached(path, body) {
  const key = path + (body === undefined ? "" : "\n" + JSON.stringify(body));
  if (!cache.has(key)) cache.set(key, request(path, body).catch((e) => { cache.delete(key); throw e; }));
  return cache.get(key);
}
const getRadar = () => cached(`/api/radar?${scenarioQuery()}`);
const getMatches = (top = 12) => cached("/api/match", matchBody({ top }));

/* ---------- fields: the 22 kinds of work, named in the page's language ---------- */

let FIELDS = {};  // field_id -> row of /api/fields, filled in by boot()
const fieldName = (id) => {
  const f = FIELDS[id];
  return f ? f["name_" + LANG] || f.name_en : id || "";
};
const fieldAbout = (id) => { const f = FIELDS[id]; return f ? f["about_" + LANG] || f.about_en : ""; };
const fieldChip = (id) => (id ? `<span class="chip plain">${esc(fieldName(id))}</span>` : "");

/* ---------- small pieces every page uses ---------- */

const SDG_COLOR = { 1: "#E5243B", 2: "#DDA63A", 3: "#4C9F38", 4: "#C5192D", 5: "#FF3A21", 6: "#26BDE2", 7: "#FCC30B", 8: "#A21942",
  9: "#FD6925", 10: "#DD1367", 11: "#FD9D24", 12: "#BF8B2E", 13: "#3F7E44", 14: "#0A97D9", 15: "#56C02B", 16: "#00689D", 17: "#19486A" };
const goalOf = (target) => String(target).split(".")[0];
const sdgChip = (target, title = "") => `<span class="chip sdg" style="--sdg:${SDG_COLOR[goalOf(target)] || "#19486a"}" title="${esc(title || sdgText(target))}"><i class="dot"></i>SDG ${esc(target)}</span>`;
const statusChip = (s) => `<span class="chip ${esc(s)}" title="${esc(t("status.title"))}"><i class="dot"></i>${t("status." + s)}</span>`;
const handoffTitle = (x) => (x.handoff === null || x.handoff === undefined ? t("skill.nodata") : t("skill.handoff.title", fmt(x.handoff, 0)));
const dotName = (x) => `<span class="chip ${esc(x.status)}" title="${esc(handoffTitle(x))}"><i class="dot"></i>${esc(x.skill_name)}</span>`;
const bar = (value, cls = "", extra = "") => `<div class="bar ${cls}" role="img" aria-label="${fmt(value, 0)}"><i style="width:${clamp(value || 0, 0, 100)}%"></i>${extra}</div>`;
const loading = (text) => `<div class="loading"><span class="spinner" aria-hidden="true"></span><span>${esc(text || t("loading"))}</span></div>`;
const initials = (name) => esc(String(name || "?").trim()[0] || "?");
const occLink = (id, title) => `<a href="#/occ/${esc(id)}">${esc(title)}</a>`;
const mycolChip = (m) => (m === "yes" ? `<span class="chip brand" title="${esc(t("mycol.yes"))}">MyCOL</span>`
  : m === "near" ? `<span class="chip plain" title="${esc(t("mycol.near"))}">MyCOL ~</span>` : "");
const dateText = (iso) => {
  if (!iso) return "–";
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? esc(iso) : d.toLocaleDateString(LOCALE[LANG], { day: "numeric", month: "short", year: "numeric" });
};
const monthText = (ym) => {
  const d = new Date(`${ym}-01T00:00:00`);
  return Number.isNaN(d.getTime()) ? esc(ym) : d.toLocaleDateString(LOCALE[LANG], { month: "short", year: "numeric" });
};

/* The source and date under every number that comes from data. */
function aiSource(src) {
  if (!src) return "";
  const s = src.ai_usage || src.economic_index || src;
  return `<p class="src">${t("src.ai", `<a href="${safeUrl(s.source_url)}" target="_blank" rel="noopener">${esc(s.source_name)}</a>`, dateText(s.release_date), dateText(s.fetched_date))}</p>`;
}

/* One control for the scenario, shared by Radar, Matches and Futures: the same person and data,
   a different assumption about how fast AI spreads. */
function scenarioControl(info, scenarios) {
  const pct = Math.round((info.adoption || 0) * 100);
  return `<section class="card pad-s stack tight" aria-label="${t("scn.label")}">
    <div class="row between">
      <div class="row" style="gap:8px"><span class="small strong">${t("scn.label")}</span>
        <div class="seg" role="group" aria-label="${t("scn.label")}">${scenarios.map((s) =>
          `<button type="button" data-act="scenario" data-id="${s.id}" aria-pressed="${state.scenario === s.id}">${t("scn." + s.id)}</button>`).join("")}</div>
      </div>
      <span class="chip warn">${t("scn.estimate")}</span>
    </div>
    <label class="field"><span>${t("scn.slider", `<b class="num" style="color:var(--ink)">${pct}%</b>`, info.horizon || 2030)}</span>
      <input type="range" min="0" max="90" step="5" value="${pct}" data-on="adoption" aria-label="${t("scn.slider.aria")}"></label>
    <p class="small muted">${t(state.scenario === "custom" ? "scn.custom.desc" : `scn.${state.scenario}.desc`, pct)}</p>
  </section>`;
}

/* Job-search links: the government job portal and the two biggest job sites in Malaysia, searched
   with the occupation's common title (each opens a search without signing in). */
function jobLinks(searchTitle) {
  const q = String(searchTitle || "").trim();
  if (!q) return "";
  const sites = [
    ["MYFutureJobs", `https://candidates.myfuturejobs.gov.my/search-jobs?what=${encodeURIComponent(q)}`],
    ["JobStreet", `https://my.jobstreet.com/${encodeURIComponent(q.replace(/\s+/g, "-"))}-jobs`],
    ["LinkedIn", `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(q)}&location=Malaysia`],
  ];
  return `<div class="row small joblinks"><span class="muted">${t("jobs.find", esc(q))}</span>${sites.map(([name, url]) =>
    `<a href="${safeUrl(url)}" target="_blank" rel="noopener">${name}</a>`).join("")}</div>`;
}

/* A searchable list of occupations: the box filters in place, so it keeps its focus. */
function occMatches(list, query, field = "", limit = 30) {
  const q = String(query || "").trim().toLowerCase();
  const words = q.split(/\s+/).filter(Boolean);
  return list.filter((o) => (!field || o.field_id === field) && words.every((w) => o.title.toLowerCase().includes(w))).slice(0, limit);
}

/* ---------- navigation ---------- */

const STEPS = [["you", "nav.you"], ["radar", "nav.radar"], ["matches", "nav.matches"], ["pathway", "nav.pathway"],
  ["sdg", "nav.sdg"], ["futures", "nav.futures"]];
function drawChrome(current) {
  const at = current === "occ" ? "radar" : current;
  $("#steps").innerHTML = STEPS.map(([id, key], i) =>
    `<a href="#/${id}"${at === id ? ' aria-current="page"' : ""}><b>${i + 1}</b><span>${t(key)}</span></a>`).join("")
    + `<a href="#/lab"${at === "lab" ? ' aria-current="page"' : ""}><b>⚗</b><span>${t("nav.lab")}</span></a>`
    + `<a href="#/team"${at === "team" ? ' aria-current="page"' : ""}><b>+</b><span>${t("nav.team")}</span></a>`
    + `<a href="#/sources"${at === "sources" ? ' aria-current="page"' : ""}><b>i</b><span>${t("nav.sources")}</span></a>`;
  $("#foot").innerHTML = `<p>${t("foot.estimates")}</p><p>${t("foot.human")}</p>
    <p>${t("foot.privacy")} · <a href="#/sources">${t("nav.sources")}</a> · <a href="#/" data-act="reset">${t("foot.reset")}</a></p>`;
  const dark = isDark();
  const btn = $("#theme");
  btn.textContent = dark ? "☀" : "☾";
  btn.setAttribute("aria-label", t(dark ? "theme.light" : "theme.dark"));
  btn.title = btn.getAttribute("aria-label");
  $("#lang").value = LANG;
  document.documentElement.lang = LANG === "zh" ? "zh-Hans" : LANG;
}
function isDark() {
  const set = document.documentElement.dataset.theme;
  return set ? set === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
}

const PAGES = {};  // name -> async (args) => html; the page files add theirs
let routeSeq = 0;
async function route(keepScroll = false) {
  const seq = ++routeSeq;
  const [name, ...args] = location.hash.replace(/^#\/?/, "").split("/");
  const page = PAGES[name || "home"] || PAGES.home;
  const y = window.scrollY;
  drawChrome(name || "home");
  if (!keepScroll) app.innerHTML = loading();
  try {
    const html = await page(args.map(decodeURIComponent));
    if (seq !== routeSeq) return;  // the person moved on while this page was loading
    app.innerHTML = `<div class="fade">${html}</div>`;
    if (keepScroll) window.scrollTo(0, y); else { window.scrollTo(0, 0); app.focus({ preventScroll: true }); }
  } catch (e) {
    if (seq !== routeSeq) return;
    const offline = Boolean(e && e.offline);
    app.innerHTML = `<div class="err stack tight" role="alert"><p>${offline ? t("err.offline") : `${t("err.generic")} ${esc(e.message)}`}</p>
      <div class="row"><button class="btn small" type="button" data-act="retry">${t("err.retry")}</button><a href="#/">${t("err.home")}</a></div></div>`;
  }
}
const redraw = () => route(true);

/* ---------- actions: one listener each; elements say what they do with data-act / data-on / data-in ---------- */

const ACT = {
  retry: () => route(),
  scenario: (el) => setScenario(el.dataset.id),
  reset: (el, e) => {
    e.preventDefault();
    if (!confirm(t("foot.reset.confirm"))) return;
    try { localStorage.removeItem(STORE_KEY); } catch (err) { /* storage off */ }
    state = blank();
    Object.assign(ui, { open: {}, why: {}, news: null, whatif: null, cvResult: null, ad: null, adText: "" });
    cache.clear();
    location.hash = "#/";
    route();
  },
  demo: (el) => {
    state = Object.assign(blank(), { demo: el.dataset.id, scenario: state.scenario, adoption: state.adoption, learner: state.learner });
    Object.assign(ui, { open: {}, why: {}, news: null, whatif: null, ad: null });
    save();
    location.hash = "#/matches";
  },
  /* One tap from the home page: publish a simulated headline and land on what it changes. It plays
     for the visitor's own profile when they have one, otherwise for the demo person it is about. */
  newsFor: async (el) => {
    const wi = await cached("/api/whatif");
    const n = wi.news.find((x) => x.id === el.dataset.id);
    if (!n) return;
    if (el.dataset.person) {
      state = Object.assign(blank(), { demo: el.dataset.person, scenario: state.scenario, adoption: state.adoption, learner: state.learner });
    }
    Object.assign(ui, { open: {}, why: {}, news: n.id, whatif: null, ad: null });
    save();
    location.hash = "#/futures";
    runWhatIf(n.changes);
  },
};
const ON = {
  adoption: (el) => {
    const v = Number(el.value) / 100;
    state.adoption = v;
    state.scenario = SCENARIO_IDS.find((id) => Math.abs((SCENARIO_VALUES[id] ?? -1) - v) < 0.001) || "custom";
    afterScenario();
  },
};
const SCENARIO_VALUES = { slow: 0.1, moderate: 0.25, fast: 0.5 };  // refreshed from the API
function setScenario(id) {
  state.scenario = id;
  state.adoption = SCENARIO_VALUES[id] ?? state.adoption;
  afterScenario();
}
function afterScenario() {
  ui.whatif = null;
  ui.why = {};
  save();
  redraw();
}
function rememberScenarios(list) {
  for (const s of list || []) SCENARIO_VALUES[s.id] = s.adoption;
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (el && ACT[el.dataset.act]) ACT[el.dataset.act](el, e);
});
document.addEventListener("change", (e) => {
  const el = e.target.closest("[data-on]");
  if (el && ON[el.dataset.on]) ON[el.dataset.on](el, e);
});
document.addEventListener("input", (e) => {
  const el = e.target.closest("[data-in]");
  if (el && ON[el.dataset.in]) ON[el.dataset.in](el, e);
});

/* ---------- home ---------- */

function personaCards(people) {
  return `<div class="grid">${people.map((p) => `
    <button type="button" class="card persona" data-act="demo" data-id="${esc(p.profile_id)}">
      <div class="row"><span class="avatar" aria-hidden="true">${initials(p.name)}</span>
        <div><div class="strong">${esc(p.name)}</div><span class="chip brand">${t("kind." + (p.kind || "student"))}</span></div></div>
      <p class="small muted">${t("persona." + p.profile_id) === "persona." + p.profile_id ? esc(p.story) : t("persona." + p.profile_id)}</p>
      <span class="small strong" style="color:var(--brand)">${t("home.persona.go")} →</span>
    </button>`).join("")}</div>`;
}

function factTiles(c, src) {
  const months = c.months || [];
  const index = c.usage_index_my || {};
  const first = index[months[0]], last = index[months[months.length - 1]];
  const tiles = [
    [fmt(last, 2) + "×", t("fact.index", fmt(first, 2), monthText(months[0]), monthText(months[months.length - 1]))],
    [fmt(c.work_use.malaysia, 0) + "%", t("fact.work", fmt(c.work_use.global, 0))],
    [fmt(c.automation_all.malaysia, 0) + "%", t("fact.handoff", fmt(c.automation_all.global, 0))],
  ];
  return `<div class="grid three">${tiles.map(([big, text]) =>
    `<div class="card tile"><div class="big">${big}</div><p class="small muted">${text}</p></div>`).join("")}</div>${aiSource(src)}`;
}

PAGES.home = async () => {
  const [radar, people, wi] = await Promise.all([cached("/api/radar?scenario=moderate"), cached("/api/profiles"), cached("/api/whatif")]);
  rememberScenarios(radar.scenarios);
  const started = hasProfile();
  const news = wi.news.find((n) => n.lead) || wi.news[0];
  const own = started && !state.demo;  // a visitor with their own answers sees the news play for them
  const about = news && people.find((p) => p.profile_id === news.person);
  const newsGo = own ? t("home.news.go.you") : about ? t("home.news.go.person", esc(about.name)) : t("home.news.go");
  const counts = radar.fields.reduce((n, f) => n + f.occupations, 0);
  return `<div class="stack loose">
    <section class="hero stack">
      <p class="eyebrow">${t("home.eyebrow")}</p>
      <h1>${t("home.h1")}</h1>
      <p class="lead">${t("home.lead", counts, radar.fields.length)}</p>
      <div class="row">
        <a class="btn primary" href="#/${started ? "matches" : "quick"}">${t(started ? "home.continue" : "home.quick")}</a>
        ${started ? "" : `<a class="btn" href="#/you">${t("home.start")}</a>`}
        <a class="btn" href="#/radar">${t("home.radar")}</a>
      </div>
      <div class="tags"><span class="chip plain">${t("home.free")}</span><span class="chip plain">${t("home.nologin")}</span><span class="chip plain">${t("home.private")}</span><span class="chip plain">English · Bahasa Melayu · 中文</span></div>
    </section>

    <section class="stack">
      <div><h2>${t("home.persona.h")}</h2><p class="muted small">${t("home.persona.p")}</p></div>
      ${personaCards(people)}
    </section>

    ${news ? `<section class="card stack" style="border-color:var(--ai)">
      <div class="row"><span class="chip ai">${t("news.simulated")}</span>${fieldChip(news.field)}</div>
      <p class="headline big">“${esc(t("news." + news.id + ".title"))}”</p>
      <p class="muted">${t("home.news.p")}</p>
      <div class="row"><button type="button" class="btn primary" data-act="newsFor" data-id="${esc(news.id)}" data-person="${own ? "" : esc(news.person || "")}">${newsGo}</button>
        <a class="btn ghost" href="#/futures">${t("home.news.more")}</a></div>
    </section>` : ""}

    <section class="card stack">
      <div><h2>${t("home.team.h")}</h2><p class="muted small">${t("home.team.p")}</p></div>
      <div class="row"><a class="btn small" href="#/team">${t("home.team.go")} →</a></div>
    </section>

    <section class="stack">
      <h2>${t("home.facts.h")}</h2>
      ${factTiles(radar.context, radar.sources)}
    </section>

    <section class="stack">
      <h2>${t("home.rules.h")}</h2>
      <div class="grid three">${[1, 2, 3].map((i) => `
        <div class="card pad-s stack tight"><span class="strong">${t(`home.rules.${i}.h`)}</span><span class="small muted">${t(`home.rules.${i}.p`)}</span></div>`).join("")}</div>
    </section>

    <section class="stack">
      <h2>${t("home.how.h")}</h2>
      <div class="grid three journey">${STEPS.map(([id, key], i) => `
        <a class="card pad-s" href="#/${id}"><span class="n">${i + 1}</span><span class="strong">${t(key)}</span><span class="small muted">${t("how." + id)}</span></a>`).join("")}</div>
    </section>
  </div>`;
};

/* ---------- sources: where every number comes from, its date, and the model's constants ---------- */

function updatePanel(u) {
  const ei = u.economic_index || {};
  const running = u.status === "running";
  const label = { idle: "upd.idle", running: "upd.running", done: "upd.done", failed: "upd.failed" }[u.status] || "upd.idle";
  return `<section class="card stack">
    <div class="row between"><h2>${t("upd.h")}</h2>
      <button type="button" class="btn small primary" data-act="update"${running ? " disabled" : ""}>${t(running ? "upd.running" : "upd.go")}</button></div>
    <p class="muted small">${t(u.auto_update_days > 0 ? "upd.p" : "upd.p.off", fmt(u.auto_update_days, 0))}</p>
    <div class="tags">
      <span class="chip ${u.status === "failed" ? "declining" : "brand"}">${t(label)}</span>
      <span class="chip plain">${t("upd.last", dateText(u.last_fetched))}</span>
      ${u.next_auto_update ? `<span class="chip plain">${t("upd.next", dateText(u.next_auto_update))}</span>` : ""}
      <span class="chip ${ei.new_release ? "warn" : "plain"}">${ei.new_release ? t("upd.ei.new", dateText(ei.latest)) : t("upd.ei.pinned", dateText(ei.pinned), ei.checked ? dateText(ei.checked) : t("upd.never"))}</span>
    </div>
    ${u.log ? `<details class="more"><summary>${t("upd.log")}</summary><pre class="code small">${esc(u.log)}</pre></details>` : ""}
  </section>`;
}

PAGES.sources = async () => {
  const s = await request("/api/sources");  // never cached: this page shows how fresh the data is now
  const p = s.parameters, x = s.exposure, w = s.weights, fw = s.field_weights, d = s.demand;
  const rows = s.sources.map((r) => `<tr>
      <td><span class="strong">${r.url ? `<a href="${safeUrl(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>` : esc(r.name)}</span>
        <div class="small muted">${esc(r.used_for)}</div>${r.licence ? `<div class="tiny muted">${esc(r.licence)}</div>` : ""}</td>
      <td class="n">${r.released ? dateText(r.released) : esc(r.covers || "–")}</td>
      <td class="n">${dateText(r.fetched)}</td>
      <td class="small muted">${esc(r.refresh)}</td>
      <td class="n">${r.rows}</td></tr>`).join("");
  const pct = (v) => `${Math.round(v * 100)}%`;
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("nav.sources")}</p><h1>${t("srcs.h1")}</h1><p class="lead">${t("srcs.lead")}</p></header>
    ${updatePanel(s.update)}
    <section class="card stack"><h2>${t("srcs.table.h")}</h2>
      <div class="table-wrap"><table><thead><tr><th>${t("srcs.col.source")}</th><th class="n">${t("srcs.col.released")}</th><th class="n">${t("srcs.col.fetched")}</th><th>${t("srcs.col.refresh")}</th><th class="n">${t("srcs.col.rows")}</th></tr></thead><tbody>${rows}</tbody></table></div>
    </section>
    <section class="card stack"><h2>${t("srcs.model.h")}</h2>
      <p class="muted small">${t("srcs.model.p")}</p>
      <div class="stack tight">
        <p><span class="strong">${t("srcs.f.field")}</span><br><code>${t("part.choice")} ${pct(fw.choice)} + ${t("part.interest")} ${pct(fw.interest)} + ${t("part.experience")} ${pct(fw.experience)}</code></p>
        <p><span class="strong">${t("srcs.f.match")}</span><br><code>${t("part.field")} ${pct(w.field)} + ${t("part.interest")} ${pct(w.interest)} + ${t("part.skill")} ${pct(w.skill)} + ${t("part.outlook")} ${pct(w.outlook)}</code> <span class="small muted">(+ SDG ${s.sdg_bonus.direct} / ${s.sdg_bonus.indirect})</span></p>
        <p><span class="strong">${t("srcs.f.demand")}</span><br><code>${t("srcs.f.demand.code", d.share_full_pct)}</code></p>
        <p><span class="strong">${t("srcs.f.outlook")}</span><br><code>${t("srcs.f.outlook.code", p.builder_shift, p.exposure_shift)}</code></p>
        <p><span class="strong">${t("srcs.f.skill")}</span><br><code>${t("srcs.f.skill.code", p.skill_builder_shift, p.skill_shift, fmt(s.reference.skill_handoff, 1))}</code></p>
        <p><span class="strong">${t("srcs.f.share")}</span><br><code>${t("srcs.f.share.code", x.automation_weight, x.augmentation_weight, x.min_usage_pct)}</code></p>
        ${s.evidence ? `<p><span class="strong">${t("srcs.f.evidence")}</span><br><span class="small">${t("srcs.ev.p", s.evidence.fresh_ai_days, s.evidence.fresh_demand_days, fmt(s.routes.reach_points, 0))}</span></p>` : ""}
        <p><span class="strong">${t("srcs.f.sim")}</span><br><span class="small">${t("srcs.f.sim.p", p.futures, p.demand_sd, Math.round(p.param_spread * 100))}</span></p>
      </div>
      <div class="tags">${s.scenarios.map((sc) => `<span class="chip plain">${t("scn." + sc.id)}: ${Math.round(sc.adoption * 100)}%</span>`).join("")}
        <span class="chip plain">${t("srcs.horizon", p.horizon_year)}</span>
        ${d.momentum && d.momentum.momentum !== null ? `<span class="chip plain">${t("srcs.momentum", fmt(d.momentum.momentum, 0), signed(d.momentum.growth_pct))}</span>` : ""}</div>
    </section>
    <section class="grid two">
      <div class="card stack"><h2>${t("srcs.guard.h")}</h2><ul class="stack tight small">
        <li>${t("srcs.guard.1")}</li><li>${t("srcs.guard.2", esc(s.llm.configured ? `${s.llm.model} (${s.llm.provider})` : t("srcs.llm.off")))}</li>
        <li>${t("srcs.guard.3")}</li><li>${t("srcs.guard.4")}</li></ul></div>
      <div class="card stack"><h2>${t("srcs.limits.h")}</h2><ul class="stack tight small">
        <li>${t("srcs.limits.1")}</li><li>${t("srcs.limits.2")}</li><li>${t("srcs.limits.3")}</li><li>${t("srcs.limits.4")}</li><li>${t("srcs.limits.5")}</li></ul></div>
    </section>
  </div>`;
};

ACT.update = async (el) => {
  el.disabled = true;
  try { await request("/api/update", {}); } catch (e) { /* already running: just watch it */ }
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const u = await request("/api/update").catch(() => null);
    if (u && u.status !== "running") break;
    if (!location.hash.startsWith("#/sources")) return;
  }
  cache.clear();  // new data: every kept answer is stale
  if (location.hash.startsWith("#/sources")) redraw();
};

/* ---------- start ---------- */

async function boot() {
  $("#lang").addEventListener("change", (e) => { setLang(e.target.value); route(true); });
  $("#theme").addEventListener("click", () => {
    const theme = isDark() ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("future-skills-theme", theme); } catch (e) { /* storage off */ }
    drawChrome(location.hash.replace(/^#\/?/, "").split("/")[0] || "home");
  });
  window.addEventListener("hashchange", () => route());
  try {
    FIELDS = Object.fromEntries((await cached("/api/fields")).map((f) => [f.field_id, f]));
  } catch (e) { /* route() shows the error */ }
  route();
}
