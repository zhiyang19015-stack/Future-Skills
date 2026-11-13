/* Future Skills: the Lab. Five tools over the same engine and data (src/main.py /api/lab/*):
     stress     Career Stress Test: change the assumptions, watch the tasks, skills and routes move
     map        Skill Transfer Map: from the skills you have to the occupations next to them
     decide     Career Decision Lab: stay and upskill, an adjacent move, a bigger change, under your limits
     why        Confidence Challenge: why this occupation and not that one, and what would swap them
     missions   Action Missions: short practice tasks with a standard and a product you can show
   Every number keeps its kind: observed AI use, research-estimated exposure, a scenario assumption
   or your own input. None of them is a probability of losing a job. */
"use strict";

const LAB_TABS = ["stress", "map", "decide", "why", "missions"];
const CATS = ["automation", "augmentation", "human", "unclear"];
const labDefaults = () => ({ friction: 0.3, demand: 0, maxWeeks: 52, budget: 500, other: "", query: "", otherQuery: "", missions: {} });
function lab() {
  if (!state.lab || typeof state.lab !== "object") state.lab = labDefaults();
  return Object.assign(state.lab, Object.assign(labDefaults(), state.lab));
}
const labBody = (extra = {}) => matchBody(extra);  // profileBody() already sends the finished missions
const kindChip = (k) => `<span class="chip kind-${esc(k)}" title="${esc(t("lab.kind." + k + ".p"))}">${t("lab.kind." + k)}</span>`;

/* Which occupation a tab is about: the one in the address, else the job you do now, else your top match. */
async function labOcc(arg) {
  if (arg) return arg;
  if (state.demo) {
    const people = await cached("/api/profiles");
    const me = people.find((p) => p.profile_id === state.demo);
    if (me && me.current_occupation) return me.current_occupation;
  } else if (state.kind !== "student" && state.currentOcc) return state.currentOcc;
  if (state.occId) return state.occId;
  const m = await getMatches();
  const first = m.results.find((x) => !x.flags.includes("needs_extra_education") && !x.flags.includes("current_occupation"));
  return (first || m.results[0]).occ_id;
}

function occPicker(tab, current, key = "query", target = "") {
  return `<label class="field"><span class="small strong">${t(key === "query" ? "lab.pick" : "lab.pick.other")}</span>
    <input type="search" value="${esc(lab()[key])}" data-in="labSearch" data-key="${key}" data-tab="${tab}" data-target="${esc(target)}" placeholder="${esc(t("lab.pick.ph"))}" autocomplete="off"></label>
    <div class="tags" id="lab-${key}"></div>`;
}
async function fillPicker(el) {
  const occs = await cached("/api/occupations");
  const box = $(`#lab-${el.dataset.key}`);
  if (!box) return;
  const found = el.value.trim().length >= 2 ? occMatches(occs, el.value, "", 8) : [];
  box.innerHTML = found.map((o) => el.dataset.key === "query"
    ? `<a class="chip plain" href="#/lab/${esc(el.dataset.tab)}/${esc(o.occ_id)}">${esc(o.title)}</a>`
    : `<button type="button" class="chip plain" data-act="labOther" data-id="${esc(o.occ_id)}">${esc(o.title)}</button>`).join("");
}

function mixBar(mix) {
  return `<div class="mix" role="img" aria-label="${esc(CATS.map((c) => `${t("lab.cat." + c)} ${fmt(mix[c], 0)}%`).join(", "))}">${CATS.map((c) =>
    mix[c] > 0 ? `<i class="m-${c}" style="width:${mix[c]}%" title="${esc(t("lab.cat." + c))} ${fmt(mix[c], 0)}%"></i>` : "").join("")}</div>`;
}
const mixLegend = (mix) => `<div class="tags">${CATS.map((c) => `<span class="chip plain"><i class="dot m-${c}"></i>${t("lab.cat." + c)} ${fmt(mix[c], 0)}%</span>`).join("")}</div>`;

function slider(on, label, value, min, max, step, shown) {
  return `<label class="field"><span>${label}: <b class="num">${shown}</b></span>
    <input type="range" min="${min}" max="${max}" step="${step}" value="${value}" data-on="${on}" aria-label="${esc(label)}"></label>`;
}

function routeCard(r, hours) {
  const tr = r.training, loc = r.local;
  return `<article class="card pad-s stack tight">
    <div class="row between"><div><h3>${occLink(r.occ_id, r.title)}</h3>
      <p class="tiny muted">${esc(fieldName(r.field_id))}${r.relation ? ` · ${t("lab.rel." + r.relation)}` : ""}${r.similarity !== null && r.similarity !== undefined ? ` · ${t("lab.similar", fmt(r.similarity, 0))}` : ""}</p></div>
      <div class="tags">${statusChip(loc.status)}${mycolChip(loc.mycol)}</div></div>
    <div class="meter"><span>${t("lab.coverage")}</span>${bar(r.coverage)}<span class="v">${fmt(r.coverage, 0)}%</span></div>
    <p class="tiny muted">${r.evidence !== null && r.evidence !== undefined ? t("lab.backed", fmt(r.evidence, 0)) : ""} ${t("lab.counts", r.counts.have, r.counts.strengthen, r.counts.missing)}</p>
    ${r.critical_count ? `<p class="small">${t("lab.critical", r.critical_count)} ${r.critical.slice(0, 4).map((g) => `<span class="chip warn">${esc(g.skill_name)} +${fmt(g.gap)}</span>`).join(" ")}</p>` : `<p class="small muted">${t("lab.critical.none")}</p>`}
    <p class="small">${t("lab.train", fmt(tr.hours, 0), fmt(tr.weeks, 0), hours)}${tr.fees_unknown ? ` ${t("lab.fees.unknown")}` : ""}${r.fits_time === false ? ` <span class="chip declining">${t("lab.toolong")}</span>` : ""}</p>
    ${r.qualification.steps_up ? `<p class="small">${t("lab.qual", r.qualification.job_zone)}</p>` : ""}
    ${r.qualification.licence ? `<p class="small">${t("lab.licence", esc(r.qualification.licence.body))}</p>` : ""}
    <p class="tiny muted">${t("lab.local", fmt(loc.demand, 0), loc.ads_group ? esc(loc.ads_group) : "–", signed(loc.ads_change_pct))} ${loc.group_wage_myr ? t("lab.wage", Math.round(loc.group_wage_myr).toLocaleString(LOCALE[LANG])) : t("lab.nowage")}</p>
    <p class="tiny muted">${t("lab.score", fmt(r.score, 0), fmt(r.parts.coverage, 0), fmt(r.parts.outlook, 0), fmt(r.parts.readiness, 0))}</p>
  </article>`;
}

function tabsNav(tab, occ) {
  return `<div class="seg" role="tablist">${LAB_TABS.map((id) => `<a role="tab" class="segbtn" href="#/lab/${id}${occ && id !== "decide" ? "/" + esc(occ) : ""}" aria-selected="${tab === id}">${t("lab.tab." + id)}</a>`).join("")}</div>`;
}

/* ---------- Career Stress Test ---------- */

async function stressPage(occId) {
  const L = lab();
  const body = labBody({ occ_id: occId, friction: L.friction, demand_change: L.demand, max_weeks: L.maxWeeks,
    use_profile: hasProfile() });
  const [r, radar] = await Promise.all([cached("/api/lab/stress", body), getRadar()]);
  rememberScenarios(radar.scenarios);
  const s = r.summary, o = r.outlook, x = r.ilo;
  const changes = r.changes.map((c) => `<li>${t("lab.chg." + c.input, c.input === "demand_change" ? signed(c.from, 0) : Math.round(c.from * 100), c.input === "demand_change" ? signed(c.to, 0) : Math.round(c.to * 100))}:
      ${t("lab.chg.effect", signed(c.pressure_change), signed(c.outlook_change), c.tasks_moved)}</li>`).join("");
  const byCat = (c) => r.tasks.filter((k) => k.category === c);
  const taskLine = (k) => `<li><span>${esc(k.task)}</span> <span class="tiny muted">${t("lab.task.line", fmt(k.observed, 0), fmt(k.pressure_low, 0), fmt(k.pressure_high, 0))}${k.automation_pct !== null ? ` · ${t("task.auto", fmt(k.automation_pct, 0))}` : ""}</span></li>`;
  return `
    <section class="card stack"><h2>${t("lab.stress.h", esc(r.occupation.title))}</h2>
      <p class="muted small">${t("lab.stress.p")}</p>
      ${scenarioControl({ adoption: r.params.adoption, horizon: 2030 }, radar.scenarios)}
      <div class="grid two">
        ${slider("labFriction", t("lab.friction"), Math.round(L.friction * 100), 0, 90, 5, `${Math.round(L.friction * 100)}%`)}
        ${slider("labDemand", t("lab.demand", r.occupation.masco_major || "–"), L.demand, -50, 100, 5, `${signed(L.demand, 0)}%`)}
        ${slider("labWeeks", t("lab.weeks"), L.maxWeeks, 4, 156, 4, L.maxWeeks)}
        ${slider("labHours", t("lab.hours"), state.hours, 1, 40, 1, state.hours)}
      </div>
      <p class="tiny muted">${t("lab.effective", Math.round(r.effective_adoption * 100), fmt(r.pace, 2))} ${kindChip("scenario_assumption")}</p>
    </section>

    <section class="grid two">
      <div class="card stack tight"><h3>${t("lab.observed.h")} ${kindChip("observed")}</h3>
        <div class="big">${fmt(o.ai_share, 0)}%</div><p class="small muted">${t("lab.observed.p", fmt(o.ai_share_low, 0), fmt(o.ai_share_high, 0), fmt(o.ai_share_reference, 0))}</p></div>
      <div class="card stack tight"><h3>${t("lab.ilo.h")} ${kindChip("research_estimate")}</h3>
        ${x ? `<div class="big">${fmt(x.mean, 2)} <small>± ${fmt(x.sd, 2)}</small></div>
          <p class="small">${t("lab.grad." + x.gradient)}</p>
          <p class="tiny muted">${t("lab.ilo.map", esc(x.isco), esc(x.isco_title), t("lab.map." + x.mapping))}</p>` : `<p class="small muted">${t("lab.ilo.none")}</p>`}</div>
    </section>
    ${x && x.disagree ? `<div class="warn">${t("lab.disagree." + x.direction, fmt(x.percentile_observed, 0), fmt(x.percentile_potential, 0))}</div>` : x ? `<p class="small muted">${t("lab.agree", fmt(x.percentile_observed, 0), fmt(x.percentile_potential, 0))}</p>` : ""}

    <section class="card stack"><h2>${t("lab.mix.h")}</h2>
      <p class="small muted">${t("lab.mix.p")}</p>
      <p class="small strong">${t("lab.mix.now")}</p>${mixBar(s.mix)}${mixLegend(s.mix)}
      <p class="small strong">${t("lab.mix.base")}</p>${mixBar(r.baseline.mix)}
      <p class="small">${t("lab.pressure", fmt(s.pressure, 0), fmt(s.pressure_low, 0), fmt(s.pressure_high, 0), fmt(r.baseline.pressure, 0))}</p>
      ${changes ? `<div><p class="small strong">${t("lab.chg.h")}</p><ul class="small">${changes}</ul>
        ${r.tasks_moved_count ? `<details class="more"><summary>${t("lab.moved", r.tasks_moved_count)}</summary><ul class="small">${r.tasks_moved.map((m) => `<li>${esc(m.task)} <span class="muted">${t("lab.cat." + m.from)} → ${t("lab.cat." + m.to)}</span></li>`).join("")}</ul></details>` : ""}</div>`
        : `<p class="small muted">${t("lab.chg.none")}</p>`}
    </section>

    <section class="card stack"><h2>${t("lab.scn.h")}</h2>
      <div class="table-wrap"><table><thead><tr><th>${t("scn.label")}</th><th>${t("lab.scn.mix")}</th><th class="n">${t("lab.scn.pressure")}</th><th>${t("lab.scn.outlook")}</th></tr></thead>
      <tbody>${Object.entries(r.scenarios).map(([id, v]) => `<tr><td>${t("scn." + id)}<div class="tiny muted">${t("lab.effective.short", Math.round(v.effective_adoption * 100))}</div></td>
        <td style="min-width:140px">${mixBar(v.mix)}</td><td class="n">${fmt(v.pressure, 0)} <span class="tiny muted">(${fmt(v.pressure_low, 0)}–${fmt(v.pressure_high, 0)})</span></td>
        <td>${statusChip(v.status)} <span class="tiny muted">${fmt(v.outlook, 0)}</span></td></tr>`).join("")}</tbody></table></div>
      <p class="small">${t("lab.outlook", fmt(o.outlook, 0), fmt(r.sensitivity.outlook_low, 0), fmt(r.sensitivity.outlook_high, 0), Math.round(r.sensitivity.spread * 100), fmt(o.demand, 0))}</p>
      <p class="src">${t("lab.scn.src")}</p>
    </section>

    <section class="grid two">
      <div class="card stack tight"><h3>${t("lab.skills.up")}</h3><div class="tags">${r.skills.gaining.map(dotName).join("") || `<span class="small muted">${t("ad.none")}</span>`}</div></div>
      <div class="card stack tight"><h3>${t("lab.skills.down")}</h3><div class="tags">${r.skills.losing.map(dotName).join("") || `<span class="small muted">${t("ad.none")}</span>`}</div></div>
    </section>

    <section class="card stack"><h2>${t("lab.tasks.h")}</h2>
      ${CATS.map((c) => byCat(c).length ? `<details class="more"${c === "automation" ? " open" : ""}><summary><i class="dot m-${c}"></i> ${t("lab.cat." + c)} (${byCat(c).length}) — <span class="muted small">${t("lab.cat." + c + ".p")}</span></summary><ul class="small stack tight">${byCat(c).map(taskLine).join("")}</ul></details>` : "").join("")}
      ${x && x.most_exposed.length ? `<details class="more"><summary>${t("lab.ilo.tasks", esc(x.isco_title))}</summary><ul class="small">${x.most_exposed.map((k) => `<li>${esc(k.task)} <b class="num">${fmt(k.score, 2)}</b></li>`).join("")}</ul>
        <p class="small strong">${t("lab.ilo.least")}</p><ul class="small">${x.least_exposed.map((k) => `<li>${esc(k.task)} <b class="num">${fmt(k.score, 2)}</b></li>`).join("")}</ul>
        <p class="src">${t("lab.ilo.src")}</p></details>` : ""}
    </section>

    <section class="stack"><div><h2>${t("lab.routes.h")}</h2><p class="muted small">${t("lab.routes.p", r.routes_considered)}</p></div>
      <div class="grid two">${r.routes.map((x2) => routeCard(x2, state.hours)).join("")}</div></section>
    <p class="src">${esc(r.rules.formula)}. ${t("lab.stress.src")}</p>`;
}

/* ---------- Skill Transfer Map ---------- */

function network(m) {
  const W = 640, H = 420, cx = W / 2, cy = H / 2, R = 160;
  const n = m.routes.length || 1;
  const nodes = m.routes.map((r, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return { r, x: cx + R * Math.cos(a) * 1.25, y: cy + R * Math.sin(a) };
  });
  const edge = (e) => m.edges.find((x) => x.to === e.r.occ_id) || { shared: 0, skills: [] };
  const short = (s) => (s.length > 26 ? s.slice(0, 25) + "…" : s);
  return `<svg class="net" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t("lab.net.aria"))}">
    ${nodes.map((e) => `<line x1="${cx}" y1="${cy}" x2="${e.x}" y2="${e.y}" class="edge" stroke-width="${1 + edge(e).shared * 0.8}"><title>${esc(edge(e).skills.join(", "))}</title></line>`).join("")}
    <circle cx="${cx}" cy="${cy}" r="34" class="node origin"></circle>
    <text x="${cx}" y="${cy + 4}" text-anchor="middle" class="lbl strong">${esc(short(m.origin.title))}</text>
    ${nodes.map((e) => `<a href="#/occ/${esc(e.r.occ_id)}"><circle cx="${e.x}" cy="${e.y}" r="${10 + e.r.coverage / 10}" class="node ${esc(e.r.local.status)}"><title>${esc(e.r.title)}: ${fmt(e.r.coverage, 0)}%</title></circle>
      <text x="${e.x}" y="${e.y + 28}" text-anchor="middle" class="lbl">${esc(short(e.r.title))}</text>
      <text x="${e.x}" y="${e.y + 4}" text-anchor="middle" class="lbl num">${fmt(e.r.coverage, 0)}</text></a>`).join("")}
  </svg>`;
}

function skillGroups(r) {
  const chip = (g, cls) => `<span class="chip ${cls}" title="${esc(t("lab.lvl", fmt(g.yours, 1), fmt(g.needed, 1)))}${g.source ? " · " + esc(t("lab.src." + g.source)) : ""}">${esc(g.skill_name)}</span>`;
  return `<div class="grid three">
    <div><p class="small strong">${t("lab.have")} (${r.counts.have})</p><div class="tags">${r.groups.have.map((g) => chip(g, "rising")).join("")}</div></div>
    <div><p class="small strong">${t("lab.strengthen")} (${r.counts.strengthen})</p><div class="tags">${r.groups.strengthen.map((g) => chip(g, "warn")).join("")}</div></div>
    <div><p class="small strong">${t("lab.missing")} (${r.counts.missing})</p><div class="tags">${r.groups.missing.map((g) => chip(g, "plain")).join("")}</div></div></div>`;
}

async function mapPage(occId) {
  const L = lab();
  const m = await cached("/api/lab/transfer", labBody({ origin: occId, max_weeks: L.maxWeeks }));
  const w = m.rules.weights;
  return `<section class="card stack"><h2>${t("lab.map.h", esc(m.origin.title))}</h2>
      <p class="muted small">${t("lab.map.p", m.considered)}</p>
      ${slider("labWeeks", t("lab.weeks"), L.maxWeeks, 4, 156, 4, L.maxWeeks)}
      ${network(m)}
      <p class="tiny muted">${t("lab.net.legend")}</p></section>
    <section class="stack">${m.routes.map((r) => `<div class="stack tight">${routeCard(r, m.hours_per_week)}
      <details class="more card pad-s"><summary>${t("lab.skills.of", esc(r.title))}</summary>${skillGroups(r)}</details></div>`).join("")}</section>
    <p class="src">${t("lab.map.src", Math.round(w.coverage * 100), Math.round(w.outlook * 100), Math.round(w.readiness * 100), m.rules.critical_importance, m.rules.critical_gap)}</p>
    <p class="src">${t("lab.evidence.src")}</p>`;
}

/* ---------- Career Decision Lab ---------- */

const checkChip = (c) => {
  const cls = c.ok === false ? "declining" : c.ok === true ? "rising" : "plain";
  const text = c.limit === "time" ? t("lab.chk.time", fmt(c.value, 0), fmt(c.limit_value, 0))
    : c.limit === "budget" ? t("lab.chk.budget", fmt(c.value, 0), fmt(c.limit_value, 0)) + (c.unknown_fees ? ` ${t("lab.fees.unknown")}` : "")
    : c.limit === "qualification" ? t("lab.chk.qual", c.value, c.limit_value)
    : c.limit === "licence" ? t("lab.chk.licence", esc(c.value)) : t("lab.chk.location");
  return `<li><span class="chip ${cls}">${t("lab.chk." + (c.ok === false ? "no" : c.ok === true ? "ok" : "check"))}</span> ${text}</li>`;
};

async function decidePage() {
  const L = lab();
  const d = await cached("/api/lab/decide", labBody({ limits: { max_weeks: L.maxWeeks, budget_myr: L.budget } }));
  const card = (o) => `<article class="card stack tight">
      <p class="eyebrow">${t("lab.path." + o.path)}</p><h3>${occLink(o.occ_id, o.title)}</h3>
      <div class="tags">${statusChip(o.local.status)}${mycolChip(o.local.mycol)}${o.fits ? `<span class="chip rising">${t("lab.fits")}</span>` : `<span class="chip declining">${t("lab.nofit")}</span>`}</div>
      <div class="meter"><span>${t("lab.coverage")}</span>${bar(o.coverage)}<span class="v">${fmt(o.coverage, 0)}%</span></div>
      <p class="small">${t("lab.train", fmt(o.training.hours, 0), fmt(o.training.weeks, 0), d.hours_per_week)} ${t("lab.fees", fmt(o.training.course_fees_myr, 0))}</p>
      <p class="small">${o.critical_count ? `${t("lab.critical", o.critical_count)} ${o.critical.slice(0, 4).map((g) => `<span class="chip warn">${esc(g.skill_name)} +${fmt(g.gap)}</span>`).join(" ")}` : t("lab.critical.none")}</p>
      <p class="small">${t("lab.robust", o.robust_scenarios)} ${Object.entries(o.local.statuses).map(([id, s]) => `<span class="chip ${esc(s)}" title="${esc(t("scn." + id))}"><i class="dot"></i>${t("scn." + id)}</span>`).join(" ")}</p>
      <p class="tiny muted">${t("lab.local", fmt(o.local.demand, 0), o.local.ads_group ? esc(o.local.ads_group) : "–", signed(o.local.ads_change_pct))} ${o.local.group_wage_myr ? t("lab.wage", Math.round(o.local.group_wage_myr).toLocaleString(LOCALE[LANG])) : t("lab.nowage")}</p>
      <ul class="small stack tight checks">${o.checks.map(checkChip).join("")}</ul>
      ${o.fallback ? `<p class="small">${t("lab.fallback", occLink(o.fallback.occ_id, o.fallback.title), fmt(o.fallback.coverage, 0))} ${statusChip(o.fallback.status)}</p>` : ""}
      ${o.path !== "stay" ? `<a class="small" href="#/lab/why/${esc(d.options[0].occ_id)}" data-act="labCompare" data-id="${esc(o.occ_id)}">${t("lab.whynot", esc(d.options[0].title))}</a>` : ""}
    </article>`;
  return `<section class="card stack"><h2>${t("lab.decide.h")}</h2><p class="muted small">${t("lab.decide.p", esc(d.origin.title))}</p>
      <div class="grid two">
        ${slider("labWeeks", t("lab.weeks"), L.maxWeeks, 4, 156, 4, L.maxWeeks)}
        ${slider("labBudget", t("lab.budget"), L.budget, 0, 5000, 100, `RM ${L.budget}`)}
        ${slider("labHours", t("lab.hours"), state.hours, 1, 40, 1, state.hours)}
      </div>
      <p class="tiny muted">${t("lab.location")}</p></section>
    <section class="grid three">${d.options.map(card).join("")}</section>
    <section class="card stack"><h2>${t("lab.caas.h")}</h2><p class="small muted">${t("lab.caas.p")}</p>
      <ul class="stack tight">${d.caas.map((c) => `<li><span class="strong">${t("lab.caas." + c)}</span> ${t("lab.caas." + c + ".q")}</li>`).join("")}</ul>
      <p class="src">${t("lab.caas.src")}</p></section>
    <p class="src">${t("lab.decide.src")}</p>`;
}

/* ---------- Confidence Challenge ---------- */

async function whyPage(occId) {
  const L = lab();
  let other = L.other && L.other !== occId ? L.other : "";
  if (!other) {
    const m = await getMatches();
    const next = m.results.find((x) => x.occ_id !== occId && !x.flags.includes("current_occupation") && !x.flags.includes("needs_extra_education"));
    other = next ? next.occ_id : "";
  }
  const picker = occPicker("why", occId, "otherQuery", occId);
  if (!other) return `<section class="card stack"><h2>${t("lab.why.h")}</h2>${picker}</section>`;
  const c = await cached("/api/lab/challenge", labBody({ occ_id: occId, other_id: other }));
  const a = c.chosen, b = c.other;
  const flip = c.flip;
  const flipLine = (k, v) => `<li>${v === null || v === undefined ? t("lab.flip." + k + ".never") : v === "out_of_range" ? t("lab.flip.out") + " " + t("lab.flip." + k + ".label") : t("lab.flip." + k, k === "adoption" ? Math.round(v * 100) : fmt(v, 1))}</li>`;
  const ev = (x) => `<div class="card pad-s stack tight"><h3>${occLink(x.occ_id, x.title)} ${evidenceChip(x.evidence.grade)}</h3>
      <p class="small">${t("lab.total", fmt(x.total, 1))} · ${statusChip(x.outlook.status)}</p>
      <p class="tiny muted">${t("lab.map." + x.mapping)} · ${x.ilo ? `${t("lab.grad." + x.ilo.gradient)}${x.ilo.disagree ? ` · <b>${t("lab.disagree.short")}</b>` : ""}` : t("lab.ilo.none")}</p>
      <p class="small">${x.missing.length ? t("lab.missing.data") + " " + x.missing.map((k) => `<span class="chip warn">${t("lab.miss." + k)}</span>`).join(" ") : t("lab.missing.none")}</p></div>`;
  return `<section class="card stack"><h2>${t("lab.why.h")}</h2><p class="muted small">${t("lab.why.p")}</p>${picker}</section>
    <section class="card stack"><h2>${t("lab.why.vs", esc(a.title), esc(b.title))}</h2>
      <p>${t(c.gap >= 0 ? "lab.why.gap" : "lab.why.gap.neg", fmt(Math.abs(c.gap), 1), esc(a.title), esc(b.title))}</p>
      <div class="table-wrap"><table><thead><tr><th>${t("lab.part")}</th><th class="n">${esc(a.title)}</th><th class="n">${esc(b.title)}</th><th class="n">${t("lab.points")}</th><th>${t("lab.kind")}</th></tr></thead>
        <tbody>${c.parts.map((p) => `<tr><td>${t("part." + p.part)}</td><td class="n">${fmt(p.chosen, 0)}</td><td class="n">${fmt(p.other, 0)}</td><td class="n">${signed(p.points)}</td><td>${kindChip(p.kind)}</td></tr>`).join("")}</tbody></table></div>
    </section>
    <section class="card stack"><h2>${t("lab.flip.h")}</h2><ul class="small stack tight">${flipLine("adoption", flip.adoption)}${flipLine("skill_points", flip.skill_points)}${flipLine("demand_points", flip.demand_points)}</ul>
      <p class="src">${t("lab.flip.src")}</p></section>
    <section class="grid two">${ev(a)}${ev(b)}</section>
    <section class="card stack tight"><h2>${t("lab.dates.h")}</h2>
      <p class="small">${t("lab.dates", dateText(c.dates.ai_release), esc(c.dates.ai_period), dateText(c.dates.demand_computed), dateText(c.dates.ilo_release))}</p>
      <div class="tags">${["observed", "research_estimate", "scenario_assumption", "user_input"].map(kindChip).join("")}</div>
      <p class="src">${t("lab.kinds.note")}</p></section>`;
}

/* ---------- Action Missions ---------- */

async function missionsPage(occId) {
  const r = await cached("/api/missions", labBody({ occ_id: occId }));
  const L = lab();
  const card = (m) => `<article class="card pad-s stack tight">
      <div class="row between"><h3>${esc(m.title)}</h3><span class="chip plain">${t("path.hours", fmt(m.hours, 0))}</span></div>
      <div class="tags">${m.skills.map((s) => `<span class="chip brand">${esc(s)}</span>`).join("")}<span class="chip plain">${t("lab.mlevel", fmt(m.level, 0))}</span></div>
      <p class="small"><span class="strong">${t("lab.done.when")}</span> ${esc(m.done_when)}</p>
      <p class="small"><span class="strong">${t("lab.keep")}</span> ${esc(m.evidence)}</p>
      ${m.resources.length ? `<p class="small">${t("lab.help")} ${m.resources.map((x) => `<a href="${safeUrl(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>`).join(" · ")}</p>` : ""}
      ${m.done ? `<p class="small">${t("lab.mdone")}${L.missions[m.mission_id] && L.missions[m.mission_id].url ? ` · <a href="${safeUrl(L.missions[m.mission_id].url)}" target="_blank" rel="noopener">${t("lab.mevidence")}</a>` : ""}</p>
        <button type="button" class="btn small" data-act="labUndo" data-id="${esc(m.mission_id)}">${t("lab.undo")}</button>`
        : `<div class="row"><input type="url" class="grow" placeholder="${esc(t("lab.url.ph"))}" id="ev-${esc(m.mission_id)}">
        <button type="button" class="btn small primary" data-act="labDone" data-id="${esc(m.mission_id)}">${t("lab.markdone")}</button></div>`}
    </article>`;
  return `<section class="card stack"><h2>${t("lab.missions.h", esc(r.title))}</h2><p class="muted small">${t("lab.missions.p")}</p>
      ${state.demo ? `<div class="warn">${t("lab.missions.demo")}</div>` : ""}</section>
    <section class="grid two">${r.missions.map(card).join("") || `<p class="small muted">${t("lab.missions.none")}</p>`}</section>
    ${r.done.length ? `<section class="stack"><h2>${t("lab.missions.done")}</h2><div class="grid two">${r.done.map(card).join("")}</div></section>` : ""}
    <p class="src">${t("lab.missions.src")}</p>`;
}

/* ---------- the page ---------- */

PAGES.lab = async (args) => {
  const tab = LAB_TABS.includes(args[0]) ? args[0] : "stress";
  const occId = tab === "decide" ? null : await labOcc(args[1]);
  const inner = tab === "stress" ? await stressPage(occId) : tab === "map" ? await mapPage(occId)
    : tab === "decide" ? await decidePage() : tab === "why" ? await whyPage(occId) : await missionsPage(occId);
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("nav.lab")}</p><h1>${t("lab.h1")}</h1><p class="lead">${t("lab.lead")}</p></header>
    ${tabsNav(tab, occId)}
    ${tab !== "decide" ? `<section class="card pad-s stack tight">${occPicker(tab, occId)}</section>` : ""}
    ${inner}
    <div class="warn small">${t("lab.never")}</div>
  </div>`;
};

/* ---------- controls ---------- */

const labRedraw = () => { save(); redraw(); };
Object.assign(ON, {
  labFriction: (el) => { lab().friction = Number(el.value) / 100; labRedraw(); },
  labDemand: (el) => { lab().demand = Number(el.value); labRedraw(); },
  labWeeks: (el) => { lab().maxWeeks = Number(el.value); labRedraw(); },
  labBudget: (el) => { lab().budget = Number(el.value); labRedraw(); },
  labHours: (el) => { state.hours = Number(el.value); cache.clear(); labRedraw(); },
  labSearch: (el) => { lab()[el.dataset.key] = el.value; save(); fillPicker(el); },
});
Object.assign(ACT, {
  labOther: (el) => { lab().other = el.dataset.id; lab().otherQuery = ""; labRedraw(); },
  labCompare: (el) => { lab().other = el.dataset.id; save(); },
  labDone: (el) => {
    const id = el.dataset.id;
    const box = $(`#ev-${id}`);
    const url = box && /^https?:\/\//i.test(box.value.trim()) ? box.value.trim() : "";
    lab().missions[id] = { done: true, url, date: new Date().toISOString().slice(0, 10) };
    cache.clear();  // a finished mission is new skill evidence: every result is worked out again
    labRedraw();
  },
  labUndo: (el) => { delete lab().missions[el.dataset.id]; cache.clear(); labRedraw(); },
});
