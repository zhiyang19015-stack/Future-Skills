/* UI redesign pieces shared by the pages: the evidence stamp, the task breakdown strip, the
   now-to-next roadmap, the learning metro map, rank moves when the scenario changes, and the
   before/after marks of an approved news item. Every number comes from the API answer the page
   already has; nothing here computes a score, it only draws one. */
"use strict";

/* ---------- evidence stamp: grade · source · date, next to a key number; opens the Sources page ---------- */

function evStamp({ grade = null, parts = [] }) {
  const items = parts.filter(([, d]) => d).map(([label, d]) => `<span>${esc(label)} ${dateText(d)}</span>`);
  if (!grade && !items.length) return "";
  return `<a class="fs-stamp" href="#/sources" title="${esc(t("stamp.title"))}">${grade ? `<b class="g g-${esc(grade)}" aria-label="${esc(t("stamp.grade", grade))}">${esc(grade)}</b>` : ""}${items.join('<i aria-hidden="true">·</i>')}</a>`;
}

/* ---------- task breakdown strip ----------
   The Lab's stress-test rule (scripts/stress_test.py) on today's observed AI share, with no scenario
   moving it: a task whose observed range is POOR_EVIDENCE points wide or more has too little
   evidence and is not drawn; one at AUTOMATE % or more that AI mostly does alone (automation share
   >= AUTOMATION_SIDE %) is "AI can do"; AUGMENT % or more is "AI assists"; below that, "people
   lead". Each task counts by its O*NET importance. tests/test_ui_rules.py keeps these equal. */
const TASK_RULE = { AUTOMATE: 50, AUGMENT: 20, AUTOMATION_SIDE: 50, POOR_EVIDENCE: 60 };
const STRIP_KINDS = ["automation", "augmentation", "human"];
function taskKind(x) {
  if ((x.ai_share_high ?? 0) - (x.ai_share_low ?? 0) >= TASK_RULE.POOR_EVIDENCE) return "unclear";
  if (x.ai_share >= TASK_RULE.AUTOMATE && x.automation_pct !== null && x.automation_pct !== undefined
    && x.automation_pct >= TASK_RULE.AUTOMATION_SIDE) return "automation";
  if (x.ai_share >= TASK_RULE.AUGMENT) return "augmentation";
  return "human";
}
function taskMix(tasks) {
  const weight = tasks.reduce((s, x) => s + (x.importance || 0), 0) || tasks.length || 1;
  const w = (x) => (tasks.some((y) => y.importance) ? x.importance || 0 : 1);
  const mix = { automation: 0, augmentation: 0, human: 0, unclear: 0 }, counts = { ...mix };
  for (const x of tasks) { const k = taskKind(x); mix[k] += (100 * w(x)) / weight; counts[k] += 1; }
  return { mix, counts };
}
function taskStrip(tasks, source) {
  if (!tasks || !tasks.length) return "";
  const { mix, counts } = taskMix(tasks);
  const label = STRIP_KINDS.map((k) => `${t("strip." + k)} ${fmt(mix[k], 0)}%`).join(", ");
  return `<section class="card stack fs-strip" aria-label="${esc(t("strip.h"))}">
    <div class="row between"><h2>${t("strip.h")}</h2><span class="chip warn">${t("strip.notloss")}</span></div>
    <p class="small muted">${t("strip.p", tasks.length)}</p>
    <div class="fs-strip-bar" role="img" aria-label="${esc(label)}">${STRIP_KINDS.map((k) => (mix[k] > 0
      ? `<i class="s-${k}" style="width:${mix[k]}%">${mix[k] >= 14 ? `<span>${t("strip." + k)}</span>` : ""}</i>` : "")).join("")}</div>
    <div class="fs-strip-legend">${STRIP_KINDS.map((k) => `<span><i class="sw s-${k}" aria-hidden="true"></i><b>${t("strip." + k)}</b> ${fmt(mix[k], 0)}% · ${t("strip.tasks", counts[k])}<br><span class="tiny muted">${t("strip." + k + ".p")}</span></span>`).join("")}</div>
    ${counts.unclear ? `<p class="small">${t("strip.unclear", counts.unclear, fmt(mix.unclear, 0))}</p>` : ""}
    <p class="src">${t("strip.rule", TASK_RULE.AUTOMATE, TASK_RULE.AUTOMATION_SIDE, TASK_RULE.AUGMENT, TASK_RULE.POOR_EVIDENCE)}</p>
    ${source ? aiSource(source) : ""}
  </section>`;
}

/* ---------- now -> where you could be: shared skills carry over, gaps are the stepping stones ---------- */

function roadmap(m, cur) {
  const d = m.skill_detail || {};
  const have = [...(d.tech_used || []), ...(d.strengths || [])].slice(0, 3);
  const gaps = [...(d.gaps || []), ...(d.tech_missing || [])].slice(0, 3);
  const node = (cls, text, sub = "") => `<li class="fs-node ${cls}"><span class="strong">${esc(text)}</span>${sub ? `<span class="tiny muted">${sub}</span>` : ""}</li>`;
  const col = (title, cls, list, empty) => `<div class="fs-col"><p class="tiny strong muted">${title}</p>
    <ul class="plainlist">${list.length ? list.join("") : `<li class="tiny muted">${empty}</li>`}</ul></div>`;
  const arrow = `<svg class="fs-arrow" viewBox="0 0 40 16" aria-hidden="true"><path d="M2 8h32M28 3l6 5-6 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const gapSub = (g) => (g.your_level !== undefined && g.level_needed !== undefined ? t("road.level", fmt(g.your_level), fmt(g.level_needed)) : t("road.tool"));
  return `<section class="card stack fs-road" aria-label="${esc(t("road.h"))}">
    <div><h2>${t("road.h")}</h2><p class="small muted">${t("road.p")}</p></div>
    <div class="fs-road-row">
      ${col(t("road.now"), "now", [node("now", cur ? nm(cur.title) : t("road.you"), cur ? "" : t("road.you.p"))], "")}
      ${arrow}
      ${col(t("road.have"), "have", have.map((x) => node("have", nm(x.skill_name), t("road.have.p"))), t("road.have.none"))}
      ${arrow}
      ${col(t("road.gap"), "gap", gaps.map((g) => node("gap", nm(g.skill_name), gapSub(g))), t("road.gap.none"))}
      ${arrow}
      ${col(t("road.next"), "next", [node("next", nm(m.title), `#${m.rank} · ${t("match.score", fmt(m.total))}`)], "")}
    </div>
    <p class="tiny muted"><span class="fs-key have"></span> ${t("road.key.have")} &nbsp; <span class="fs-key gap"></span> ${t("road.key.gap")}</p>
  </section>`;
}

/* ---------- learning metro map: stations are the path's skills in the plan's own order ---------- */

function metroMap(L, occId) {
  const done = state.done[occId] || {};
  const seg = (list) => {
    const free = list.filter((r) => !r.cost_myr), paid = list.filter((r) => r.cost_myr);
    const hours = list.reduce((s, r) => s + (r.hours || 0), 0);
    const bits = [free.length ? t("metro.free", free.length) : "", paid.length ? t("metro.paid", paid.length) : "", hours ? t("path.hours", fmt(hours, 0)) : ""].filter(Boolean);
    return bits.length ? bits.join(" · ") : t("path.nocourse");
  };
  const allDone = (list) => list.length > 0 && list.every((r) => done[r.url]);
  const station = (name, list, jump, kind = "") => `<li class="fs-stop${allDone(list) ? " done" : ""}${list.length ? "" : " empty"} ${kind}">
      <button type="button" class="linklike" data-act="jump" data-id="${jump}"><span class="strong">${esc(name)}</span></button>
      <span class="tiny muted">${allDone(list) ? `✓ ${t("metro.done")} · ` : ""}${seg(list)}</span></li>`;
  const stops = [];
  if (L.stages[0].resources.length) stops.push(station(t("metro.basics"), L.stages[0].resources, "path-s1", "start"));
  L.skills.forEach((s, i) => stops.push(station(nm(s.skill_name), s.resources, `path-sk-${i}`)));
  if (L.hands_on.length) stops.push(`<li class="fs-stop end"><button type="button" class="linklike" data-act="jump" data-id="path-s3"><span class="strong">${t("metro.hands")}</span></button><span class="tiny muted">${t("metro.hands.p", L.hands_on.length)}</span></li>`);
  const claim = L.claimable || [];
  // a long line folds its middle: the first METRO_HEAD stops and the last one stay, a button shows the rest
  let line = stops.join("");
  if (stops.length > METRO_MAX) {
    const hidden = stops.slice(METRO_HEAD, -1);
    line = stops.slice(0, METRO_HEAD).join("")
      + `<li class="fs-stop fold"><button type="button" class="linklike" data-act="metroMore" aria-expanded="false"><span class="strong">${t("metro.more", hidden.length)}</span></button></li>`
      + hidden.map((h) => h.replace('<li class="fs-stop', '<li class="fs-stop hid')).join("") + stops[stops.length - 1];
  }
  return `<section class="card stack fs-metro" aria-label="${esc(t("metro.h"))}">
    <div><h2>${t("metro.h")}</h2><p class="small muted">${t("metro.p")}</p></div>
    <ol class="fs-line">${line}</ol>
    ${claim.length ? `<div class="fs-spur"><button type="button" class="linklike" data-act="jump" data-id="path-hrd"><span class="strong">${t("metro.hrd")}</span></button>
      <span class="tiny muted">${t("metro.hrd.p", claim.length, Math.max(...claim.map((r) => r.teaches_gaps || 0)))}</span></div>` : ""}
    <p class="tiny muted"><span class="fs-key line"></span> ${t("metro.key.free")} &nbsp; <span class="fs-key spur"></span> ${t("metro.key.hrd")}</p>
  </section>`;
}
const METRO_MAX = 8, METRO_HEAD = 5;
ACT.metroMore = (el) => { const box = el.closest(".fs-metro"); if (box) box.classList.add("open"); };
ACT.jump = (el) => {
  const to = document.getElementById(el.dataset.id);
  if (!to) return;
  const box = el.closest(".fs-metro");
  if (box) box.classList.add("open");
  to.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  to.setAttribute("tabindex", "-1"); to.focus({ preventScroll: true });
};

/* ---------- rank moves: when the scenario changes on Matches, each card slides to its new place ---------- */

function rememberRanks(label, id) {
  const cards = $$("#app article.match[id^='m-']");
  if (!cards.length) return;
  ui.rankFrom = { label, id, ranks: {}, rects: {} };
  for (const c of cards) {
    const id = c.id.slice(2);
    ui.rankFrom.ranks[id] = Number(c.dataset.rank);
    ui.rankFrom.rects[id] = c.getBoundingClientRect().top;
  }
}
function moveChip(m) {
  const from = ui.rankFrom;
  if (!from) return "";
  // a named scenario: the API's own rank there (m.scenario_ranks); a custom one: the card's last place
  const named = from.id && m.scenario_ranks ? m.scenario_ranks[from.id] : undefined;
  const was = named ?? from.ranks[m.occ_id];
  const why = ui.moveWhy && ui.moveWhy[m.occ_id];
  const chip = was === undefined || was === null ? `<span class="fs-move new">${t("move.new", esc(from.label))}</span>`
    : was === m.rank ? `<span class="fs-move same">${t("move.same", esc(from.label))}</span>`
    : `<span class="fs-move ${was > m.rank ? "up" : "down"}">${t(was > m.rank ? "move.up" : "move.down", Math.abs(was - m.rank), was, esc(from.label))}</span>`;
  return `<div class="stack tight">${chip}${why && was !== m.rank ? `<span class="tiny muted">${robustWhy(why)}</span>` : ""}</div>`;
}
function playRankMoves() {
  const from = ui.rankFrom;
  if (!from || !from.rects) return;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  for (const c of $$("#app article.match[id^='m-']")) {
    const before = from.rects[c.id.slice(2)];
    if (before === undefined || still) continue;
    const dy = before - c.getBoundingClientRect().top;
    if (Math.abs(dy) > 1 && c.animate) c.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 200, easing: "ease-out" });
  }
  from.rects = null;  // play once; the chips stay until the person leaves the page
}

/* ---------- approved news: what it changed in this person's list ---------- */

function newsMarks(m) {
  const b = ui.newsBefore;
  if (!b || !b.after) return { banner: "", mark: () => "" };
  const now = Object.fromEntries(m.ranking.slice(0, 12).map((r) => [r.occ_id, r.rank]));
  const moved = m.ranking.slice(0, 12).filter((r) => b.ranks[r.occ_id] !== r.rank);
  const banner = `<div class="note stack tight fs-newsmark" role="status"><p class="strong">${t("nb.h", esc(b.title))}</p>
    <p class="small">${moved.length ? t("nb.moved", moved.length) : t("nb.same")} ${t("nb.undo")} <a href="#/futures">${t("nb.go")} →</a>
      <button type="button" class="linklike" data-act="newsMarksOff">${t("nb.hide")}</button></p></div>`;
  const mark = (id) => (b.ranks[id] !== undefined && now[id] !== undefined && b.ranks[id] !== now[id]
    ? `<span class="fs-move changed">${t("nb.row", b.ranks[id], now[id])}</span>` : b.ranks[id] === undefined && now[id] !== undefined ? `<span class="fs-move changed">${t("nb.row.new")}</span>` : "");
  return { banner, mark };
}
ACT.newsMarksOff = () => { ui.newsBefore = null; redraw(); };

/* The plans kept just before an approval (futures.js rnDecide): the chosen job and the top 3 moves. */
const planOf = (L) => ({ hours: L.total_hours, skills: Object.fromEntries(L.skills.map((s, i) => [s.skill_id, { i, status: s.ai.status }])) });
async function plansBefore(m) {
  const ids = [...new Set([state.occId, ...(m.results || []).filter(isMove).slice(0, 3).map((r) => r.occ_id)].filter(Boolean))];
  const out = {};
  await Promise.all(ids.map(async (id) => {
    try { out[id] = planOf(await cached("/api/learn", matchBody({ occ_id: id }))); } catch (e) { /* not kept: the page says so */ }
  }));
  return out;
}
const statusWord = (s) => (STRINGS["status.word." + s] ? t("status.word." + s) : esc(s));
function pathNewsMarks(L, occId) {
  const b = ui.newsBefore;
  if (!b || !b.after) return { banner: "", mark: () => "" };
  const off = `<a href="#/futures">${t("nb.go")} →</a> <button type="button" class="linklike" data-act="newsMarksOff">${t("nb.hide")}</button>`;
  const was = (b.plans || {})[occId];
  if (!was) return { banner: `<div class="note small" role="status"><span class="strong">${t("nb.h", esc(b.title))}</span> ${t("nb.path.unkept")} ${off}</div>`, mark: () => "" };
  const now = planOf(L);
  const marks = {};
  L.skills.forEach((s, i) => {
    const w = was.skills[s.skill_id];
    const bits = !w ? [t("nb.path.new")] : [w.i !== i ? t("nb.path.step", w.i + 1, i + 1) : "", w.status !== s.ai.status ? t("nb.path.ai", statusWord(w.status), statusWord(s.ai.status)) : ""].filter(Boolean);
    if (bits.length) marks[s.skill_id] = bits.join(" · ");
  });
  const gone = Object.keys(was.skills).filter((id) => !now.skills[id]).length;
  const n = Object.keys(marks).length;
  const hours = Math.round(now.hours) !== Math.round(was.hours) ? ` ${t("nb.path.hours", fmt(was.hours, 0), fmt(now.hours, 0))}` : "";
  const banner = `<div class="note stack tight fs-newsmark" role="status"><p class="strong">${t("nb.h", esc(b.title))}</p>
    <p class="small">${n || gone ? t("nb.path.moved", n, gone) : t("nb.path.same")}${hours} ${t("nb.undo")} ${off}</p></div>`;
  return { banner, mark: (id) => (marks[id] ? `<span class="fs-move changed">${t("nb.path.row", marks[id])}</span>` : "") };
}

/* ---------- the profile's progress: which optional parts have an answer ---------- */

function profileProgress() {
  const parts = [["fields", Object.keys(state.fields).length > 0, "you-fields"], ["cv", Boolean(state.cv), "you-cv"],
    ["tools", state.techs.length > 0, "you-tools"], ["interests", quizDone(), "you-interests"], ["skills", ratedCount() > 0, "you-skills"]];
  if (state.kind !== "student") parts.unshift(["job", Boolean(state.currentOcc), "you-who"]);
  const n = parts.filter(([, on]) => on).length;
  return `<section class="card pad-s stack tight fs-progress" aria-label="${esc(t("prog.h"))}">
    <div class="row between"><span class="strong">${t("prog.n", n, parts.length)}</span><span class="small muted">${t(n ? "prog.ready" : "prog.one")}</span></div>
    <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${parts.length}" aria-valuenow="${n}" aria-label="${esc(t("prog.h"))}"><i style="width:${Math.round((100 * n) / parts.length)}%"></i></div>
    <div class="tags">${parts.map(([k, on, id]) => `<button type="button" class="toggle fs-part${on ? " on" : ""}" data-act="jump" data-id="${id}">${on ? "✓" : "○"} ${t("prog." + k)}</button>`).join("")}</div>
  </section>`;
}
