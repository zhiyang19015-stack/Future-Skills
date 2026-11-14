/* The clarity check (scripts/pilot.py): Phase 1's KPI 1 measured in a workshop.
     #/check[/CODE]  a participant answers three questions before using the app and again after it
     #/pilot         the workshop leader opens a session and reads its counts
   Every answer is a pick from a list or "not sure yet"; no name and no typed text is sent. The
   leader's keys live under their own storage key, so "Clear my answers" never loses a session. */
"use strict";

const PILOT_KEYS = "future-skills-pilot-keys";
const pilotKeys = () => { try { return JSON.parse(localStorage.getItem(PILOT_KEYS) || "{}") || {}; } catch (e) { return {}; } };
const savePilotKeys = (keys) => { try { localStorage.setItem(PILOT_KEYS, JSON.stringify(keys)); } catch (e) { /* storage off */ } };
const pilotUi = { codeError: false, again: false, draft: null, occText: "", opened: null, results: {}, restoreError: false };

function pilotState() {
  if (!state.pilot || typeof state.pilot !== "object") state.pilot = { code: "", before: null, after: null };
  return state.pilot;
}
const emptyAnswer = () => ({ occ_id: "", gap_id: "", resource_id: "" });
const checkLink = (code) => `${location.origin}${location.pathname}#/check/${code}`;

/* ---------- the participant ---------- */

function pilotForm(phase, occs, options) {
  const d = pilotUi.draft || (pilotUi.draft = emptyAnswer());
  const picked = occs.find((o) => o.occ_id === d.occ_id);
  const group = (kind) => `<optgroup label="${esc(t("chk.kind." + kind))}">${options.elements.filter((e) => e.kind === kind).map((e) =>
    `<option value="${esc(e.id)}"${d.gap_id === e.id ? " selected" : ""}>${esc(e.name)}</option>`).join("")}</optgroup>`;
  return `<section class="card stack">
    <h2>${t(phase === "before" ? "chk.before.h" : "chk.after.h")}</h2>
    <label class="field">${t("chk.q1")}
      <input type="search" list="chk-occs" value="${esc(picked ? picked.title : pilotUi.occText)}" placeholder="${esc(t("chk.q1.ph"))}" data-in="pilotOcc" autocomplete="off"></label>
    <datalist id="chk-occs">${occs.map((o) => `<option value="${esc(o.title)}"></option>`).join("")}</datalist>
    <p class="small muted" id="chk-picked">${picked ? t("chk.q1.picked", esc(picked.title)) : t("chk.q1.none")}</p>
    <label class="field">${t("chk.q2")}
      <select data-on="pilotGap"><option value="">${t("chk.unsure")}</option>${group("skill")}${group("knowledge")}</select></label>
    <label class="field">${t("chk.q3")}
      <select data-on="pilotCourse"><option value="">${t("chk.unsure")}</option>${options.resources.map((r) =>
        `<option value="${esc(r.id)}"${d.resource_id === r.id ? " selected" : ""}>${esc(r.title)} · ${esc(r.provider)}</option>`).join("")}</select></label>
    <div class="row"><button type="button" class="btn primary" data-act="pilotSend" data-phase="${phase}">${t("chk.send")}</button></div>
  </section>`;
}

function pilotCompare(p, occs, options) {
  const name = {
    occupation: (a) => (occs.find((o) => o.occ_id === a.occ_id) || {}).title,
    gap: (a) => (options.elements.find((e) => e.id === a.gap_id) || {}).name,
    course: (a) => (options.resources.find((r) => r.id === a.resource_id) || {}).title,
  };
  const cell = (a, q) => (name[q](a) ? esc(name[q](a)) : `<span class="muted">${t("chk.unsure")}</span>`);
  const r = p.after.reading || {};
  const notes = [r.gap_on_path === true && "chk.gap.on", r.gap_on_path === false && "chk.gap.off",
    r.course_on_path === true && "chk.course.on", r.course_on_path === false && "chk.course.off"].filter(Boolean);
  return `<section class="card stack"><h2>${t("chk.done.h")}</h2><p class="muted small">${t("chk.done.p")}</p>
    <div class="table-wrap"><table><thead><tr><th>${t("chk.col.q")}</th><th>${t("chk.col.before")}</th><th>${t("chk.col.after")}</th></tr></thead>
      <tbody>${["occupation", "gap", "course"].map((q) => `<tr><td class="strong">${t("chk.row." + q)}</td><td>${cell(p.before, q)}</td><td>${cell(p.after, q)}</td></tr>`).join("")}</tbody></table></div>
    ${notes.length ? `<ul class="small stack tight">${notes.map((k) => `<li>${t(k)}</li>`).join("")}</ul>` : ""}
    <div class="row">${p.after.occ_id ? `<a class="btn primary" href="#/pathway/${esc(p.after.occ_id)}">${t("chk.open.path")} →</a>` : `<a class="btn primary" href="#/quick">${t("home.quick")}</a>`}
      <button type="button" class="btn" data-act="pilotRedo">${t("chk.redo")}</button></div>
  </section>`;
}

PAGES.check = async (args) => {
  const p = pilotState();
  const wanted = String(args[0] || "").trim().toUpperCase();
  if (wanted && wanted !== p.code) {  // the link from the room: join that session, with fresh answers
    try {
      await request(`/api/pilot/session/${encodeURIComponent(wanted)}`);
      Object.assign(p, { code: wanted, before: null, after: null });
      Object.assign(pilotUi, { codeError: false, again: false, draft: null, occText: "" });
      save();
    } catch (e) { if (e.offline) throw e; pilotUi.codeError = true; }
  }
  const [occs, options] = await Promise.all([cached("/api/occupations"), cached("/api/pilot/options")]);
  const head = `<header class="stack tight"><p class="eyebrow">${t("chk.eyebrow")}${p.code ? ` · ${t("chk.session", esc(p.code))}` : ""}</p>
    <h1>${t("chk.h1")}</h1><p class="lead">${t("chk.lead")}</p></header>`;
  let body;
  if (!p.code) {
    body = `<section class="card stack"><h2>${t("chk.code.h")}</h2><p class="muted small">${t("chk.code.p")}</p>
      ${pilotUi.codeError ? `<p class="err small" role="alert">${t("chk.code.bad")}</p>` : ""}
      <div class="row"><input type="text" class="inline" id="chk-code" maxlength="6" size="8" autocomplete="off" autocapitalize="characters" aria-label="${esc(t("chk.code.h"))}" style="text-transform:uppercase;letter-spacing:.2em;font-weight:700">
        <button type="button" class="btn primary" data-act="pilotJoin">${t("chk.code.go")}</button></div>
      <p class="small"><a href="#/pilot">${t("chk.code.leader")} →</a></p></section>`;
  } else if (!p.before) {
    body = pilotForm("before", occs, options);
  } else if (!p.after) {
    body = `<section class="card stack"><h2>${t("chk.saved.h")}</h2><p>${t("chk.saved.p")}</p>
        <div class="row"><a class="btn primary" href="#/quick">${t("home.quick")} →</a><a class="btn" href="#/you">${t("nav.you")}</a>
          ${pilotUi.again ? "" : `<button type="button" class="btn" data-act="pilotAgain">${t("chk.again")}</button>`}</div></section>
      ${pilotUi.again ? pilotForm("after", occs, options) : ""}`;
  } else {
    body = pilotCompare(p, occs, options);
  }
  return `<div class="stack loose">${head}${body}
    <p class="src">${t("chk.privacy", options.keep_days)}${p.code ? ` · <a href="#/check" data-act="pilotLeave">${t("chk.leave")}</a>` : ""}</p></div>`;
};

/* ---------- the workshop leader ---------- */

function pilotCsv(rows) {
  const cols = ["participant", "phase", "date", "occ_id", "occupation", "gap_id", "gap", "resource_id", "named_all_three", "consistent_with_data"];
  const cell = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\r\n");
}

function pilotResults(code) {
  const s = pilotUi.results[code];
  if (!s) return "";
  if (s.error) return `<p class="err small" role="alert">${t("plt.bad")}</p>`;
  const n = s.people.both;
  const verdict = !s.enough_people ? `<p class="warn">${t("plt.few", s.target_pct, s.min_people)}</p>`
    : `<p class="${s.target_met ? "note" : "warn"}">${t(s.target_met ? "plt.met" : "plt.notmet", fmt(s.named.after_pct, 0), s.target_pct, s.min_people)}</p>`;
  const tile = (key, v) => `<div class="card pad-s tile"><span class="small muted">${t(key)}</span><div class="big">${v}</div></div>`;
  const share = (count) => (n ? `${count} <span class="muted">/ ${n}</span>` : "–");
  return `<p class="tiny muted">${t("plt.opened", dateText(s.created), dateText(s.expires))}</p>
    <div class="grid three">${tile("plt.t.before", s.people.before)}${tile("plt.t.after", s.people.after)}${tile("plt.t.both", n)}</div>
    <div class="stack tight"><h3>${t("plt.named.h")}</h3>
      <p>${t("plt.named.p", n, s.named.before, s.named.after)}</p>
      ${n ? `<div class="meter"><span>${t("chk.col.before")}</span>${bar(s.named.before_pct)}<span class="v">${s.named.before}</span></div>
        <div class="meter"><span>${t("chk.col.after")}</span>${bar(s.named.after_pct)}<span class="v">${s.named.after}</span></div>
        <p class="small">${t("plt.consistent", s.consistent_after.count, fmt(s.consistent_after.pct, 0))}</p>` : ""}
      ${verdict}</div>
    <div class="stack tight"><h3>${t("plt.q.h")}</h3><p class="muted small">${t("plt.q.p")}</p>
      <div class="table-wrap"><table><thead><tr><th>${t("chk.col.q")}</th><th class="n">${t("chk.col.before")}</th><th class="n">${t("chk.col.after")}</th></tr></thead>
        <tbody>${s.questions.map((q) => `<tr><td>${t("chk.row." + q.question)}</td><td class="n">${share(q.before)}</td><td class="n">${share(q.after)}</td></tr>`).join("")}</tbody></table></div></div>
    <p class="src">${esc(s.method)}</p>`;
}

function pilotSession(code, key) {
  const fresh = pilotUi.opened === code;
  return `<section class="card stack">
    <div class="row between"><div><p class="tiny muted">${t("plt.code")}</p><div class="big" style="font-size:2rem;font-weight:750;letter-spacing:.18em">${esc(code)}</div></div>
      <div class="row"><button type="button" class="btn small primary" data-act="pilotRefresh" data-id="${esc(code)}">${t("plt.refresh")}</button>
        ${pilotUi.results[code] && !pilotUi.results[code].error ? `<button type="button" class="btn small" data-act="pilotCsv" data-id="${esc(code)}">${t("plt.csv")}</button>` : ""}</div></div>
    <p class="small">${t("plt.link")}: <a href="${esc(checkLink(code))}"><code>${esc(checkLink(code))}</code></a></p>
    <details class="more"${fresh ? " open" : ""}><summary>${t("plt.key")}</summary>
      <p class="small"><code>${esc(key)}</code></p><p class="small muted">${t("plt.key.p")}</p>
      <button type="button" class="btn small" data-act="pilotForget" data-id="${esc(code)}">${t("plt.forget")}</button></details>
    ${pilotResults(code)}
  </section>`;
}

async function pilotLoad(code) {
  try {
    pilotUi.results[code] = await request("/api/pilot/summary", { code, key: pilotKeys()[code] });
  } catch (e) {
    if (e.offline) throw e;
    pilotUi.results[code] = { error: true };
  }
}

PAGES.pilot = async () => {
  const options = await cached("/api/pilot/options");
  const keys = pilotKeys();
  const codes = Object.keys(keys).reverse();
  await Promise.all(codes.filter((c) => !pilotUi.results[c]).map(pilotLoad));
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("plt.eyebrow")}</p><h1>${t("plt.h1")}</h1><p class="lead">${t("plt.lead")}</p></header>
    <section class="card stack"><h2>${t("plt.how.h")}</h2>
      <ol class="small stack tight"><li>${t("plt.how.1")}</li><li>${t("plt.how.2")}</li><li>${t("plt.how.3")}</li></ol>
      <div class="row"><button type="button" class="btn primary" data-act="pilotOpen">${t("plt.open")}</button></div>
      <p class="src">${t("plt.open.p", options.keep_days)}</p></section>
    ${codes.map((c) => pilotSession(c, keys[c])).join("") || `<p class="note">${t("plt.none")}</p>`}
    <details class="more card pad-s"><summary>${t("plt.restore.h")}</summary>
      <div class="stack tight" style="margin-top:10px">${pilotUi.restoreError ? `<p class="err small" role="alert">${t("plt.bad")}</p>` : ""}
        <div class="row"><input type="text" class="inline" id="plt-code" maxlength="6" size="8" autocomplete="off" placeholder="${esc(t("plt.code"))}" aria-label="${esc(t("plt.code"))}" style="text-transform:uppercase">
          <input type="text" class="grow" id="plt-key" autocomplete="off" placeholder="${esc(t("plt.key"))}" aria-label="${esc(t("plt.key"))}">
          <button type="button" class="btn" data-act="pilotRestore">${t("plt.restore.go")}</button></div></div></details>
    <div class="row"><a class="btn" href="#/team">${t("nav.team")}</a><a class="btn" href="#/sources">${t("nav.sources")}</a></div>
  </div>`;
};

/* ---------- actions ---------- */

Object.assign(ACT, {
  pilotJoin: () => {
    const code = ($("#chk-code").value || "").trim().toUpperCase();
    if (!code) return;
    pilotUi.codeError = false;
    if (location.hash === `#/check/${code}`) route(); else location.hash = `#/check/${code}`;
  },
  pilotLeave: (el, e) => {
    e.preventDefault();
    state.pilot = { code: "", before: null, after: null };
    Object.assign(pilotUi, { codeError: false, again: false, draft: null, occText: "" });
    save();
    if (location.hash === "#/check") route(); else location.hash = "#/check";
  },
  pilotAgain: () => { pilotUi.again = true; pilotUi.draft = null; pilotUi.occText = ""; redraw(); },
  pilotRedo: () => {
    const p = pilotState();
    pilotUi.draft = { occ_id: p.after.occ_id, gap_id: p.after.gap_id, resource_id: p.after.resource_id };
    p.after = null;
    pilotUi.again = true;
    save();
    redraw();
  },
  pilotSend: async (el) => {
    const p = pilotState();
    const phase = el.dataset.phase;
    const d = pilotUi.draft || emptyAnswer();
    el.disabled = true;
    try {
      const saved = await request("/api/pilot/answer", { code: p.code, learner: learnerId(), phase, ...d });
      p[phase] = { ...d, reading: saved.reading };
      Object.assign(pilotUi, { draft: null, occText: "", again: false });
      save();
      route();
    } catch (e) {
      el.disabled = false;
      alert(e.message);
    }
  },
  pilotOpen: async (el) => {
    el.disabled = true;
    try {
      const s = await request("/api/pilot/session", {});
      savePilotKeys({ ...pilotKeys(), [s.code]: s.key });
      pilotUi.opened = s.code;
    } catch (e) { alert(e.message); }
    redraw();
  },
  pilotRefresh: async (el) => { el.disabled = true; await pilotLoad(el.dataset.id).catch(() => null); redraw(); },
  pilotForget: (el) => {
    if (!confirm(t("plt.forget.confirm"))) return;
    const keys = pilotKeys();
    delete keys[el.dataset.id];
    delete pilotUi.results[el.dataset.id];
    savePilotKeys(keys);
    redraw();
  },
  pilotRestore: async () => {
    const code = ($("#plt-code").value || "").trim().toUpperCase(), key = ($("#plt-key").value || "").trim();
    if (!code || !key) return;
    try {
      pilotUi.results[code] = await request("/api/pilot/summary", { code, key });
      savePilotKeys({ ...pilotKeys(), [code]: key });
      pilotUi.restoreError = false;
    } catch (e) { pilotUi.restoreError = true; }
    redraw();
  },
  pilotCsv: (el) => {
    const s = pilotUi.results[el.dataset.id];
    if (!s || !s.rows) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + pilotCsv(s.rows)], { type: "text/csv;charset=utf-8" }));
    a.download = `clarity-check-${s.code}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  },
});
Object.assign(ON, {
  pilotGap: (el) => { (pilotUi.draft || (pilotUi.draft = emptyAnswer())).gap_id = el.value; },
  pilotCourse: (el) => { (pilotUi.draft || (pilotUi.draft = emptyAnswer())).resource_id = el.value; },
  pilotOcc: async (el) => {  // a title from the list is a pick; anything else is "not sure yet"
    const occs = await cached("/api/occupations");
    const text = el.value.trim().toLowerCase();
    const found = occs.find((o) => o.title.toLowerCase() === text);
    const d = pilotUi.draft || (pilotUi.draft = emptyAnswer());
    d.occ_id = found ? found.occ_id : "";
    pilotUi.occText = el.value;
    const note = $("#chk-picked");
    if (note) note.innerHTML = found ? t("chk.q1.picked", esc(found.title)) : t("chk.q1.none");
  },
});
