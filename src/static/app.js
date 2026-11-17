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
/* A whole number of ringgit (or any count) grouped the Malaysian way: 12,000. */
const whole = (n) => (n === null || n === undefined || n === "" || Number.isNaN(Number(n)) ? "–" : Math.round(Number(n)).toLocaleString(LOCALE[LANG]));
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
  if (!res.ok) throw Object.assign(new Error(answer.error || `HTTP ${res.status}`), { status: res.status });
  return answer;
}
/* An error in the page's language. The server's own reason is in English and kept after it, in
   brackets, because it names exactly what to fix; an error made in this page is already translated. */
function errText(e) {
  if (!e) return "";
  if (e.offline) return t("err.offline");
  if (!e.status) return e.message;
  const what = e.status === 404 ? t("err.notfound") : e.status === 400 ? t("err.input") : e.status === 409 ? t("err.busy")
    : t("err.server");
  if (e.status === 404 || e.message === `HTTP ${e.status}`) return what;  // nothing more to say than the status
  return LANG === "en" && e.status === 400 ? `${what} ${e.message}` : `${what} (${e.message})`;
}
function cached(path, body) {
  const key = path + (body === undefined ? "" : "\n" + JSON.stringify(body));
  if (!cache.has(key)) cache.set(key, request(path, body).catch((e) => { cache.delete(key); throw e; }));
  return cache.get(key);
}
const getRadar = () => cached(`/api/radar?${scenarioQuery()}`);
const getMatches = (top = 12) => cached("/api/match", matchBody({ top }));
/* A profile with no answers gets no ranking (the API's needs_input): this says why and where to start. */
const blankCard = () => `<div class="warn row between" role="status"><span>${t("match.blank")}</span><a class="btn small" href="#/you">${t("home.start")}</a></div>`;
const blankPage = (step, nav) => `<div class="stack loose"><header class="stack tight"><p class="eyebrow">${t("step", step)} · ${t("nav." + nav)}</p>
    <h1>${t("match.blank.h1")}</h1></header>${blankCard()}</div>`;

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
const dotName = (x) => `<span class="chip ${esc(x.status)}" title="${esc(handoffTitle(x))}"><i class="dot"></i>${esc(nm(x.skill_name))}</span>`;
const bar = (value, cls = "", extra = "") => `<div class="bar ${cls}" role="img" aria-label="${fmt(value, 0)}"><i style="width:${clamp(value || 0, 0, 100)}%"></i>${extra}</div>`;
const loading = (text) => `<div class="loading"><span class="spinner" aria-hidden="true"></span><span>${esc(text || t("loading"))}</span></div>`;
const initials = (name) => esc(String(name || "?").trim()[0] || "?");
const occLink = (id, title) => `<a href="#/occ/${esc(id)}"${nmTranslated(title) ? ` title="${esc(title)}" ` : ""}>${esc(nm(title))}</a>`;
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

/* Robust and scenario-dependent choices (/api/match and /api/futures, "robust"): which occupations
   hold under all three named scenarios, which ones only make the list under some, and why. Every
   number comes from the API; this only puts it into words. Shared by Matches and Futures. */
function robustWhy(w) {
  const k = w.code;
  let s;
  if (k === "share_low" || k === "share_high") s = t("rb.why." + k, fmt(w.ai_share, 0), fmt(w.ai_share_reference, 0), signed(w.outlook_move), signed(w.total_move));
  else if (k === "builder") s = t("rb.why.builder", fmt(w.builder, 0), fmt(w.builder_reference, 0), signed(w.outlook_move), signed(w.total_move));
  else if (k === "skills_up" || k === "skills_down") s = t("rb.why." + k, signed(w.skill_move), signed(w.total_move));
  else s = w.crossed ? t("rb.why.others", signed(w.total_move), esc(nm(w.crossed.title)), signed(w.crossed.total_move), fmt(w.crossed.ai_share, 0))
    : t("rb.why.others.none", signed(w.total_move));
  return w.thin && (k === "share_low" || k === "share_high") ? `${s}${LANG === "zh" ? "" : " "}${t("rb.thin")}` : s;
}
function robustCard(r) {
  if (!r || !r.scenarios || r.scenarios.length < 2) return "";
  const q = r.rules;
  const names = (ids) => ids.map((id) => t("scn." + id + ".short").toLowerCase()).join(t("rb.or"));
  const robust = r.robust.map((x) => `<li><span class="strong">${occLink(x.occ_id, x.title)}</span>
      <div class="small muted">${x.kind === "first" ? (x.lead === null ? t("rb.first.nolead") : t("rb.first", fmt(x.lead))) : t("rb.top3", q.robust_top, x.ranks[r.slow], x.ranks.moderate ?? "–", x.ranks[r.fast], fmt(x.score_move))}</div></li>`).join("");
  const dep = r.dependent.map((x) => `<li><span class="strong">${occLink(x.occ_id, x.title)}</span>
      <div class="small">${x.kind === "enters" ? t("rb.when.enters", q.top, names(x.in_top), x.ranks[r.slow], x.ranks[r.fast]) : t("rb.when.moves", q.top, x.ranks[r.slow], x.ranks[r.fast])}</div>
      <div class="small muted">${robustWhy(x.why)}</div></li>`).join("");
  return `<section class="card stack robust" id="robust"><div class="row between"><h2>${t("rb.h")}</h2><span class="chip warn">${t("scn.estimate")}</span></div>
    <p class="small muted">${t("rb.p", q.robust_top, q.top, q.rank_swing)}</p>
    <div class="grid two"><div class="stack tight"><h3>${t("rb.robust.h")}</h3>${robust ? `<ul class="plainlist stack tight">${robust}</ul>` : `<p class="small">${t("rb.robust.none", q.robust_top)}</p>`}</div>
      <div class="stack tight"><h3>${t("rb.dep.h")}</h3>${dep ? `<ul class="plainlist stack tight">${dep}</ul>` : `<p class="small muted">${t("rb.dep.none", q.top)}</p>`}</div></div>
    <p class="src">${t("scn.estimate.long")}</p></section>`;
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
  return list.filter((o) => (!field || o.field_id === field) && words.every((w) => o.title.toLowerCase().includes(w) || nm(o.title).toLowerCase().includes(w))).slice(0, limit);
}

/* ---------- navigation ---------- */

const STEPS = [["you", "nav.you"], ["radar", "nav.radar"], ["matches", "nav.matches"], ["pathway", "nav.pathway"],
  ["sdg", "nav.sdg"], ["futures", "nav.futures"]];
const TOOLS = [["lab", "nav.lab"], ["team", "nav.team"], ["sources", "nav.sources"]];
/* the page each route belongs to in the navigation: an occupation sits under the Radar, the quick
   start under You, the workshop check under Team */
const NAV_OF = { occ: "radar", quick: "you", check: "team", pilot: "team" };
const icon = (id, cls = "ico") => `<svg class="${cls}" aria-hidden="true" focusable="false"><use href="#i-${id}"/></svg>`;
const here = (id, at) => (at === id ? ' aria-current="page"' : "");
/* The app shell: the sidebar (the six steps, then the tools), the top bar (where you are, the
   scenario every page uses, the data date), the right rail on wide screens, and the phone's
   bottom bar. All of it is drawn again on every route, from state and the cached API answers. */
function drawChrome(current) {
  const at = NAV_OF[current] || current;
  document.body.dataset.page = at;  // the stylesheet gives the home page the full width (no rail)
  const stepNo = STEPS.findIndex(([id]) => id === at);
  const done = { you: hasProfile() };
  $("#steps").innerHTML = `<a class="nav" href="#/"${here("home", at)}>${icon("home")}<span>${t("nav.home")}</span></a>
    <p class="nav-h">${t("nav.group.path")}</p>
    ${STEPS.map(([id, key], i) => `<a class="nav" href="#/${id}"${here(id, at)}><b class="n${done[id] ? " done" : ""}">${done[id] ? icon("check", "ico tick") : i + 1}</b><span>${t(key)}</span></a>`).join("")}
    <p class="nav-h">${t("nav.group.tools")}</p>
    ${TOOLS.map(([id, key]) => `<a class="nav" href="#/${id}"${here(id, at)}>${icon(id)}<span>${t(key)}</span></a>`).join("")}`;
  $("#side-foot").innerHTML = `<p class="tiny muted">${t("foot.privacy")}${LANG === "zh" ? "。" : "."}</p><a class="tiny" href="#/" data-act="reset">${t("foot.reset")}</a>`;
  $("#crumb").innerHTML = at === "home" ? `<span class="strong">${t("nav.home")}</span>`
    : stepNo >= 0 ? `<span class="muted">${t("step", stepNo + 1)}</span><span class="muted" aria-hidden="true">/</span><span class="strong">${t(STEPS[stepNo][1])}</span>`
    : `<span class="strong">${t("nav." + at) === "nav." + at ? "" : t("nav." + at)}</span>`;
  const scn = SCENARIO_IDS.map((id) => `<button type="button" data-act="scenario" data-id="${id}" aria-pressed="${state.scenario === id}"><i class="sd sd-${id}" aria-hidden="true"></i>${t("scn." + id + ".short")}</button>`).join("");
  $("#top-scn").innerHTML = `<div class="seg mini" role="group" aria-label="${esc(t("scn.label"))}">${scn}</div>`;
  const d = ui.dataDates;
  $("#top-stamp").innerHTML = d ? `<a class="live" href="#/sources" title="${esc(t("stamp.title"))}"><i class="pulse" aria-hidden="true"></i>${t("shell.data", monthText(d.month), dateText(d.release))}</a>` : "";
  const pct = Math.round((state.adoption || 0) * 100);
  $("#rail").innerHTML = `<section class="rail-block"><p class="rail-h">${t("scn.label")}</p>
      <p class="strong"><i class="sd sd-${esc(state.scenario)}" aria-hidden="true"></i> ${state.scenario === "custom" ? `${pct}%` : t("scn." + state.scenario)}</p>
      <p class="small muted">${t(state.scenario === "custom" ? "scn.custom.desc" : `scn.${state.scenario}.desc`, pct)}</p>
      <div class="adopt" role="img" aria-label="${esc(t("shell.adopt", pct))}"><i style="width:${clamp(pct, 0, 100)}%"></i></div>
      <p class="tiny muted">${t("shell.adopt", pct)}</p></section>
    ${state.demo ? `<section class="rail-block"><p class="rail-h">${t("shell.demo.h")}</p><p class="small"><span class="chip warn">${t("home.fictional")}</span></p><a class="small" href="#/you">${t("shell.demo.own")} →</a></section>` : ""}
    <section class="rail-block"><p class="rail-h">${t("shell.read.h")}</p>
      <ul class="rail-list small"><li>${t("shell.read.1")}</li><li>${t("shell.read.2")}</li><li>${t("shell.read.3")}</li></ul></section>
    <section class="rail-block rail-note small">${t("foot.human")}</section>
    ${d ? `<a class="rail-block rail-src small" href="#/sources"><span class="rail-h">${t("nav.sources")}</span><span>${t("shell.data", monthText(d.month), dateText(d.release))}</span></a>` : ""}`;
  const tabs = [["home", "/", "nav.home"], ["you", "/you", "nav.you"], ["radar", "/radar", "nav.radar"], ["matches", "/matches", "nav.matches"]];
  const inMore = !tabs.some(([id]) => id === at);
  $("#bnav").innerHTML = tabs.map(([id, href, key]) => `<a href="#${href}"${here(id, at)}>${icon(id)}<span>${t(key)}</span></a>`).join("")
    + `<button type="button" data-act="moreNav" aria-expanded="false" aria-controls="more"${inMore ? ' aria-current="page"' : ""}>${icon("more")}<span>${t("nav.more")}</span></button>`;
  $("#more").innerHTML = `<div class="more-in"><p class="nav-h">${t("nav.more")}</p>${[["pathway", "nav.pathway"], ["sdg", "nav.sdg"], ["futures", "nav.futures"], ...TOOLS].map(([id, key]) =>
    `<a class="nav" href="#/${id}"${here(id, at)}>${icon(id)}<span>${t(key)}</span></a>`).join("")}</div>`;
  $("#more").hidden = true;
  $("#foot").innerHTML = `<p>${t("foot.estimates")}</p><p>${t("foot.human")}</p>
    <p>${t("foot.privacy")} · <a href="#/sources">${t("nav.sources")}</a> · <a href="#/" data-act="reset">${t("foot.reset")}</a></p>`;
  const dark = isDark();
  const btn = $("#theme");
  btn.innerHTML = icon(dark ? "sun" : "moon");
  btn.setAttribute("aria-label", t(dark ? "theme.light" : "theme.dark"));
  btn.title = btn.getAttribute("aria-label");
  $("#lang").value = LANG;
  // the page shell in index.html: its text and labels name their key
  $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $$("[data-i18n-aria]").forEach((el) => { if (el.id !== "theme") el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
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
  if (!keepScroll) { app.innerHTML = loading(); ui.rankFrom = null; }
  try {
    const html = await page(args.map(decodeURIComponent));
    if (seq !== routeSeq) return;  // the person moved on while this page was loading
    app.innerHTML = `<div class="fade">${html}</div>`;
    if (keepScroll) window.scrollTo(0, y); else { window.scrollTo(0, 0); app.focus({ preventScroll: true }); }
    playRankMoves();  // ui.js: cards slide to their new place after a scenario change
  } catch (e) {
    if (seq !== routeSeq) return;
    const offline = Boolean(e && e.offline);
    app.innerHTML = `<div class="err stack tight" role="alert"><p>${offline || (e && e.status) ? esc(errText(e)) : `${t("err.generic")} ${esc(e && e.message)}`}</p>
      <div class="row"><button class="btn small" type="button" data-act="retry">${t("err.retry")}</button><a href="#/">${t("err.home")}</a></div></div>`;
  }
}
const redraw = () => route(true);

/* ---------- actions: one listener each; elements say what they do with data-act / data-on / data-in ---------- */

const ACT = {
  retry: () => route(),
  scenario: (el) => setScenario(el.dataset.id),
  /* the phone's "More" sheet: the steps and tools that do not fit in the bottom bar */
  moreNav: (el) => {
    const box = $("#more");
    box.hidden = !box.hidden;
    el.setAttribute("aria-expanded", String(!box.hidden));
    if (!box.hidden) { const first = box.querySelector("a"); if (first) first.focus(); }
  },
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
    rememberRanks(scenarioLabel(), state.scenario === "custom" ? null : state.scenario);
    state.adoption = v;
    state.scenario = SCENARIO_IDS.find((id) => Math.abs((SCENARIO_VALUES[id] ?? -1) - v) < 0.001) || "custom";
    afterScenario();
  },
};
const SCENARIO_VALUES = { slow: 0.1, moderate: 0.25, fast: 0.5 };  // refreshed from the API
/* The scenario in words, for "was #3 under slow AI adoption". */
const scenarioLabel = () => (state.scenario === "custom" ? `${Math.round(state.adoption * 100)}%` : t("scn." + state.scenario));
function setScenario(id) {
  if (id !== state.scenario) rememberRanks(scenarioLabel(), state.scenario === "custom" ? null : state.scenario);
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
  return `<div class="grid people">${people.map((p) => `
    <button type="button" class="card persona" data-act="demo" data-id="${esc(p.profile_id)}">
      <div class="row"><span class="avatar" aria-hidden="true">${initials(p.name)}</span>
        <div><div class="strong">${esc(p.name)}</div><span class="chip brand">${t("kind." + (p.kind || "student"))}</span> <span class="chip plain">${t("home.fictional")}</span></div></div>
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
    `<div class="card tile"><div class="big">${big}</div><p class="small muted">${text}</p></div>`).join("")}</div>
    <div class="row">${evStamp({ parts: [[t("stamp.ai"), (src && (src.ai_usage || src.economic_index || src).release_date)]] })}</div>${aiSource(src)}`;
}

/* The hero's picture: every field as one bar, its height the share of its tasks people already hand
   to AI (/api/radar, moderate). The person's own field, when they chose one, is drawn in the brand
   colour; otherwise the highest. Real numbers only: a bar is never drawn without one. */
function exposureSkyline(fields) {
  const list = [...fields].filter((f) => f.ai_share !== null && f.ai_share !== undefined).sort((a, b) => b.ai_share - a.ai_share);
  if (!list.length) return "";
  const mine = Object.keys(state.fields || {}).filter((id) => state.fields[id] > 0);  // you.js: 100 = chosen, 0 = ruled out
  const pick = list.find((f) => mine.includes(f.field_id)) || list[0];
  const top = Math.max(10, Math.ceil(list[0].ai_share / 10) * 10);
  const W = 560, H = 250, L = 34, R = 8, T = 30, B = 210;
  const bw = (W - L - R) / list.length;
  const y = (v) => B - ((B - T) * v) / top;
  const lvl = (v) => Math.min(5, Math.floor((v / top) * 6));
  const ticks = [0, top / 2, top].map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="gl"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" class="tk">${fmt(v, 0)}%</text>`).join("");
  const bars = list.map((f, i) => {
    const x = L + i * bw + 2, h = Math.max(2, B - y(f.ai_share));
    return `<rect x="${fmt(x, 1)}" y="${fmt(B - h, 1)}" width="${fmt(bw - 4, 1)}" height="${fmt(h, 1)}" rx="3" class="${f === pick ? "pick" : "h" + lvl(f.ai_share)}"><title>${esc(fieldName(f.field_id))}: ${fmt(f.ai_share)}%</title></rect>`;
  }).join("");
  const i = list.indexOf(pick), px = L + i * bw + bw / 2, anchor = i > list.length / 2 ? "end" : "start";
  const label = `<line x1="${fmt(px, 1)}" x2="${fmt(px, 1)}" y1="${fmt(y(pick.ai_share) - 4, 1)}" y2="${T - 8}" class="lead-l"/>
    <text x="${fmt(px + (anchor === "start" ? -4 : 4), 1)}" y="${T - 14}" text-anchor="${anchor}" class="call">${esc(fieldName(pick.field_id))} · ${fmt(pick.ai_share)}%</text>`;
  const low = list[list.length - 1];
  const aria = t("home.viz.aria", list.length, fieldName(list[0].field_id), fmt(list[0].ai_share), fieldName(low.field_id), fmt(low.ai_share));
  return `<svg class="skyline" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(aria)}">${ticks}${bars}${label}
    <text x="${L}" y="${B + 18}" class="tk">${t("home.viz.hi")}</text><text x="${W - R}" y="${B + 18}" text-anchor="end" class="tk">${t("home.viz.lo")}</text></svg>
    <ol class="viz-top">${list.slice(0, 3).map((f) => `<li><span>${esc(fieldName(f.field_id))}</span><b class="num">${fmt(f.ai_share)}%</b></li>`).join("")}</ol>`;
}

/* How the occupations split under the scenario: rising, steady, declining, with words, not colour alone. */
const SPLIT = ["rising", "steady", "declining"];
function statusSplit(c) {
  const n = (c.rising || 0) + (c.steady || 0) + (c.declining || 0) || 1;
  return `<div class="split" role="img" aria-label="${esc(SPLIT.map((s) => `${t("status." + s)} ${c[s]}`).join(", "))}">${SPLIT.map((s) =>
    `<i class="sp-${s}" style="width:${(100 * c[s]) / n}%"></i>`).join("")}</div>
    <ul class="split-key">${SPLIT.map((s) => `<li><i class="sw sp-${s}" aria-hidden="true"></i>${t("status." + s)} <b class="num">${c[s]}</b></li>`).join("")}</ul>`;
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
  const c = radar.context, src = radar.sources, months = c.months || [], index = c.usage_index_my || {};
  const aiDate = src && (src.ai_usage || src.economic_index || src).release_date;
  return `<div class="stack loose home">
    <section class="hero fs-hero">
      <div class="hero-copy stack">
        <p class="eyebrow">${t("home.eyebrow")}</p>
        <h1>${t("home.h1")}</h1>
        <p class="lead">${t("home.lead", counts, radar.fields.length)}</p>
        <div class="row">
          ${started ? `<a class="btn primary big" href="#/matches">${t("home.continue")} ${icon("arrow")}</a>` : `<a class="btn primary big" href="#/quick">${icon("quick")}${t("home.cta.profile")}</a>`}
          <a class="btn big" href="#/radar">${icon("radar")}${t("home.cta.radar")}</a>
        </div>
        ${started ? "" : `<p class="small muted">${t("home.cta.note")} <a href="#/you">${t("home.cta.full")}</a></p>`}
        <div class="tags"><span class="chip plain">${icon("check", "ico xs")}${t("home.free")}</span><span class="chip plain">${icon("check", "ico xs")}${t("home.nologin")}</span><span class="chip plain">${icon("check", "ico xs")}${t("home.private")}</span><span class="chip plain">English · Bahasa Melayu · 中文</span></div>
      </div>
      <figure class="hero-viz">
        <figcaption class="row between"><span class="strong">${t("home.viz.h")}</span><span class="chip brand">${t("scn.moderate")}</span></figcaption>
        <p class="tiny muted">${t("home.viz.p")}</p>
        ${exposureSkyline(radar.fields)}
        <div class="row">${evStamp({ parts: [[t("stamp.ai"), aiDate]] })}</div>
      </figure>
    </section>

    <section class="stack" aria-labelledby="facts-h">
      <div class="sec-h"><h2 id="facts-h">${t("home.facts.h")}</h2><a class="small" href="#/radar">${t("home.cta.radar")} →</a></div>
      <div class="kpis">
        <div class="card kpi"><p class="k-l">${t("home.kpi.occ")}</p><p class="k-v num">${whole(counts)}</p><p class="small muted">${t("home.kpi.occ.p", radar.fields.length)}</p></div>
        <div class="card kpi wide"><p class="k-l">${t("home.kpi.split", radar.horizon_year)}</p><p class="k-v num">${radar.counts.declining}<small> / ${whole(counts)}</small></p>${statusSplit(radar.counts)}</div>
        <div class="card kpi"><p class="k-l">${t("home.kpi.work")}</p><p class="k-v num">${fmt(c.work_use.malaysia, 0)}%</p><p class="small muted">${t("fact.work", fmt(c.work_use.global, 0))}</p></div>
        <div class="card kpi"><p class="k-l">${t("home.kpi.handoff")}</p><p class="k-v num">${fmt(c.automation_all.malaysia, 0)}%</p><p class="small muted">${t("fact.handoff", fmt(c.automation_all.global, 0))}</p></div>
      </div>
      ${months.length ? `<p class="small muted">${fmt(index[months[months.length - 1]], 2)}× · ${t("fact.index", fmt(index[months[0]], 2), monthText(months[0]), monthText(months[months.length - 1]))}</p>` : ""}
      ${aiSource(src)}
    </section>

    <section class="stack" aria-label="${esc(t("home.flow.h"))}">
      <h2 class="visually-hidden">${t("home.flow.h")}</h2>
      <ol class="fs-flow">${[1, 2, 3].map((i) => `<li><span class="n">${i}</span><span class="strong">${t("home.flow." + i)}</span><span class="small muted">${t(`home.flow.${i}.p`)}</span></li>`).join("")}</ol>
    </section>

    <section class="stack">
      <div class="sec-h"><div><h2>${t("home.persona.h")}</h2><p class="muted small">${t("home.persona.p")}</p></div><span class="chip warn">${t("home.fictional")}</span></div>
      ${personaCards(people)}
    </section>

    <div class="grid two">
      ${news ? `<section class="card stack news-card">
        <div class="row"><span class="chip ai">${t("news.simulated")}</span>${fieldChip(news.field)}</div>
        <p class="headline big">“${esc(t("news." + news.id + ".title"))}”</p>
        <p class="muted small">${t("home.news.p")}</p>
        <div class="row"><button type="button" class="btn primary small" data-act="newsFor" data-id="${esc(news.id)}" data-person="${own ? "" : esc(news.person || "")}">${newsGo}</button>
          <a class="btn ghost small" href="#/futures">${t("home.news.more")}</a><a class="btn ghost small" href="#/futures">${t("home.news.real")} →</a></div>
      </section>` : ""}
      <section class="card stack">
        <div class="row">${icon("team", "ico lg")}<h2>${t("home.team.h")}</h2></div><p class="muted small">${t("home.team.p")}</p>
        <div class="row"><a class="btn small" href="#/team">${t("home.team.go")} →</a><a class="btn small" href="#/pilot">${t("home.pilot.go")} →</a></div>
      </section>
    </div>

    <section class="stack">
      <h2>${t("home.how.h")}</h2>
      <div class="journey">${STEPS.map(([id, key], i) => `
        <a href="#/${id}"><span class="n">${i + 1}</span>${icon(id)}<span class="strong">${t(key)}</span><span class="small muted">${t("how." + id)}</span></a>`).join("")}</div>
    </section>

    <section class="stack">
      <h2>${t("home.rules.h")}</h2>
      <div class="grid three">${[1, 2, 3].map((i) => `
        <div class="card flat pad-s stack tight"><span class="strong">${t(`home.rules.${i}.h`)}</span><span class="small muted">${t(`home.rules.${i}.p`)}</span></div>`).join("")}</div>
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

/* The source table's own words (ours, not the sources') in the chosen language. The text comes from
   /api/sources in English; a row or a phrase with no line in i18n.js is shown as the API wrote it. */
function sourceText(r, part, autoDays) {
  const raw = r[part] || "";
  const has = (k) => STRINGS[k] !== undefined;
  if (part === "name") return has(`srcrow.${r.id}.name`) ? t(`srcrow.${r.id}.name`) : raw;
  if (part === "used_for") {
    if (r.id === "onet") return t("srcrow.onet.used", r.rows);
    if (r.id === "my_restrictions") return `${t("srcrow.my_restrictions.used")} ${raw.split(": ").slice(1).join(": ")}`;
    return has(`srcrow.${r.id}.used`) ? t(`srcrow.${r.id}.used`) : raw;
  }
  if (part === "refresh") {
    if (/^Fetched again/.test(raw)) return autoDays > 0 ? t("srcrow.fetch.every", fmt(autoDays, 0)) : t("srcrow.fetch.pressed");
    if (raw === "Checked by hand.") return t("srcrow.hand");
    return has(`srcrow.${r.id}.refresh`) ? t(`srcrow.${r.id}.refresh`) : raw;
  }
  // covers: a count, a date range, or a phrase
  let m;
  if ((m = raw.match(/^(\d+) (resources|targets|professions|missions|occupations)$/))) return t("srcrow.n." + m[2], m[1]);
  if ((m = raw.match(/^(\d+) ISCO-08 occupations$/))) return t("srcrow.n.isco", m[1]);
  if ((m = raw.match(/^(\S+) edition, (\d+) occupations$/))) return t("srcrow.mycol.covers", m[1], m[2]);
  if ((m = raw.match(/^(\d{4}-\d{2}(?:-\d{2})?) to (\d{4}-\d{2}(?:-\d{2})?)$/))) {
    const d = (x) => (x.length === 7 ? monthText(x) : dateText(x));
    return t("srcrow.to", d(m[1]), d(m[2]));
  }
  return has(`srcrow.${r.id}.covers`) ? t(`srcrow.${r.id}.covers`) : raw;
}

PAGES.sources = async () => {
  const s = await request("/api/sources");  // never cached: this page shows how fresh the data is now
  const p = s.parameters, x = s.exposure, w = s.weights, fw = s.field_weights, d = s.demand;
  const rows = s.sources.map((r) => `<tr>
      <td><span class="strong">${r.url ? `<a href="${safeUrl(r.url)}" target="_blank" rel="noopener">${esc(sourceText(r, "name"))}</a>` : esc(sourceText(r, "name"))}</span>
        <div class="small muted">${esc(sourceText(r, "used_for"))}</div>${r.licence ? `<div class="tiny muted">${esc(r.licence)}</div>` : ""}</td>
      <td class="n">${r.released ? dateText(r.released) : esc(sourceText(r, "covers") || "–")}</td>
      <td class="n">${dateText(r.fetched)}</td>
      <td class="small muted">${esc(sourceText(r, "refresh", s.update.auto_update_days))}</td>
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
        ${s.assumptions ? `<p><span class="strong">${t("srcs.f.other")}</span><br><span class="small">${t("srcs.f.other.p", fmt(s.assumptions.current_job_field, 0), fmt(s.assumptions.cv_title_field, 0), fmt(s.assumptions.whatif_handoff_max, 0), fmt(50 + s.assumptions.explain_neutral_band, 1), fmt(50 - s.assumptions.explain_neutral_band, 1))}</span></p>` : ""}
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
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#more").hidden) { $("#more").hidden = true; const b = $("#bnav [data-act='moreNav']"); if (b) { b.setAttribute("aria-expanded", "false"); b.focus(); } }
  });
  try {
    FIELDS = Object.fromEntries((await cached("/api/fields")).map((f) => [f.field_id, f]));
  } catch (e) { /* route() shows the error */ }
  route();
  // the data date in the top bar: the AI-use month and release the numbers come from (the home page's own answer, cached)
  cached("/api/radar?scenario=moderate").then((r) => {
    const ai = r.sources && (r.sources.ai_usage || r.sources.economic_index);
    ui.dataDates = { month: r.context && r.context.latest, release: ai && ai.release_date };
    drawChrome(location.hash.replace(/^#\/?/, "").split("/")[0] || "home");
  }).catch(() => { /* no date: the top bar leaves it out */ });
}
