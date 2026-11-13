/* Steps 2 to 5: the Radar (what AI is doing to work in each field), one occupation in detail,
   the person's matches, the learning pathway and the SDG contribution. */
"use strict";

const STATUSES = ["rising", "steady", "declining"];
const SHOWN_MATCHES = 6;
const SHOWN_SKILLS = 30;
const SEARCH_RESULTS = 30;

/* ---------- 2 Radar ---------- */

function occRow(x) {
  return `<div class="item">
    <a class="title" href="#/occ/${esc(x.occ_id)}">${esc(x.title)}</a>
    <div class="val">${fmt(x.outlook, 0)}<small>${signed(x.change)}</small></div>
    <div class="meta">${fieldChip(x.field_id)}<span>${t("radar.demand", fmt(x.demand, 0))}</span><span>${t("radar.share", fmt(x.ai_share, 0), "")}</span>${mycolChip(x.mycol)}
      ${x.thin_evidence ? `<span class="chip warn" title="${esc(t("radar.thin.title"))}">${t("radar.thin")}</span>` : ""}</div>
  </div>`;
}

function fieldTable(r) {
  const ref = r.reference.role_ai_share;
  return `<div class="table-wrap"><table><thead><tr><th>${t("radar.col.field")}</th><th class="n">${t("radar.col.occ")}</th>
    <th>${t("radar.col.share")}</th><th class="n">${t("radar.col.outlook")}</th><th class="n">${t("radar.col.moves")}</th><th class="n">${t("radar.col.use")}</th></tr></thead><tbody>
    ${r.fields.map((f) => `<tr>
      <td><button type="button" class="linklike" data-act="radarField" data-id="${esc(f.field_id)}">${esc(fieldName(f.field_id))}</button></td>
      <td class="n">${f.occupations}</td>
      <td style="min-width:140px">${bar(f.ai_share, "ai", `<span class="mark" style="left:${clamp(ref, 0, 100)}%" title="${esc(t("radar.avg", fmt(ref, 0)))}"></span>`)}<span class="tiny muted">${fmt(f.ai_share, 0)}%</span></td>
      <td class="n">${fmt(f.outlook, 0)}</td>
      <td class="n small"><span class="pass">▲${f.statuses.rising}</span> <span class="fail">▼${f.statuses.declining}</span></td>
      <td class="n small">${f.usage && f.usage.global !== null ? `${fmt(f.usage.global, 1)}%` : "–"}${f.usage && f.usage.malaysia !== null ? ` <span class="muted">(MY ${fmt(f.usage.malaysia, 1)}%)</span>` : ""}</td></tr>`).join("")}
    </tbody></table></div>`;
}

function topicItem(x, ref) {
  return `<div class="item">
    <span class="strong">${esc(x.topic)}</span>
    <div class="val">${fmt(x.handoff, 0)}%<small>${t("radar.handoff")}</small></div>
    <div class="meta" style="display:block">${bar(x.handoff, x.status, `<span class="mark" style="left:${clamp(ref, 0, 100)}%" title="${esc(t("radar.ref", fmt(ref, 0)))}"></span>`)}</div>
    <div class="meta">${statusChip(x.status)}${x.builder ? `<span class="chip ai">${t("radar.builder")}</span>` : ""}${x.changed ? `<span class="chip warn">${t("whatif.changed")}</span>` : ""}
      <span>${t("radar.usage", fmt(x.usage_pct, 2), x.usage_pct_my === null ? "–" : fmt(x.usage_pct_my, 2))}</span></div>
    ${x.skills.length ? `<div class="meta"><span>${x.skills.slice(0, 9).map(esc).join(" · ")}${x.skills.length > 9 ? " …" : ""}</span></div>` : ""}
  </div>`;
}

function skillItem(x) {
  const kind = { technology: "skill.kind.tech", skill: "skill.kind.general", knowledge: "skill.kind.knowledge" }[x.skill_type];
  return `<div class="item">
    <span class="strong">${esc(x.skill_name)}</span>
    <div class="val">${x.handoff === null ? "–" : `${fmt(x.handoff, 0)}%`}<small>${t("radar.handoff")}</small></div>
    <div class="meta">${statusChip(x.status)}<span class="chip plain">${t(kind)}</span>${x.builder ? `<span class="chip ai">${t("radar.builder")}</span>` : ""}
      ${x.occupations ? `<span>${t("radar.occs", x.occupations)}</span>` : ""}${x.sdg.slice(0, 2).map((s) => sdgChip(s)).join("")}</div>
    <div class="meta"><span>${x.evidence.length ? esc(x.evidence.join(" · ")) : esc(x.note)}</span></div>
  </div>`;
}

const radarRows = (r) => r.occupations.map((row) => Object.fromEntries(r.occupation_columns.map((k, i) => [k, row[i]])));
function searchResults(r) {
  const found = occMatches(radarRows(r), ui.radarQuery, ui.radarField, SEARCH_RESULTS)
    .filter((x) => ui.radarFilter === "all" || x.status === ui.radarFilter);
  return found.length ? found.map(occRow).join("") : `<p class="small muted">${t("radar.none")}</p>`;
}

PAGES.radar = async () => {
  const r = await getRadar();
  rememberScenarios(r.scenarios);
  const ref = r.reference.skill_handoff;
  const tab = ui.radarTab;
  const filter = ui.radarFilter;
  const keep = (x) => filter === "all" || x.status === filter;
  const skills = r.skills.filter((x) => x.skill_type !== "technology").filter(keep);
  const tools = r.skills.filter((x) => x.skill_type === "technology").filter(keep);
  const list = tab === "skills" ? skills : tab === "tools" ? tools : r.topics.filter(keep);
  const shown = ui.showAllSkills ? list : list.slice(0, SHOWN_SKILLS);
  const src = r.sources;
  const tabs = [["fields", t("radar.tab.fields", r.fields.length)], ["skills", t("radar.tab.skills", r.skills.filter((x) => x.skill_type !== "technology").length)],
    ["tools", t("radar.tab.tools", r.skills.filter((x) => x.skill_type === "technology").length)], ["topics", t("radar.tab.topics", r.topics.length)]];
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 2)} · ${t("nav.radar")}</p><h1>${t("radar.h1")}</h1><p class="lead">${t("radar.lead", r.occupations.length)}</p></header>
    ${scenarioControl({ adoption: r.scenario.adoption, horizon: r.horizon_year }, r.scenarios)}
    ${r.what_if ? `<p class="warn">${t("whatif.active")}</p>` : ""}

    <section class="stack"><h2>${t("radar.my.h")}</h2>${factTiles(r.context, src)}</section>

    <section class="stack">
      <div><h2>${t("radar.occ.h")}</h2><p class="muted small">${t("radar.occ.p", r.horizon_year, r.counts.rising, r.counts.steady, r.counts.declining)}</p></div>
      <div class="grid two">
        <section class="card"><div class="col-head">${statusChip("rising")}<span class="small muted">${t("radar.top", r.rising.length)}</span></div><div class="list">${r.rising.map(occRow).join("")}</div></section>
        <section class="card"><div class="col-head">${statusChip("declining")}<span class="small muted">${t("radar.top", r.declining.length)}</span></div><div class="list">${r.declining.map(occRow).join("")}</div></section>
      </div>
      <section class="card stack">
        <h3>${t("radar.search.h", r.occupations.length)}</h3>
        <div class="grid two">
          <input type="search" placeholder="${esc(t("radar.search.ph"))}" value="${esc(ui.radarQuery)}" data-in="radarQuery" aria-label="${esc(t("radar.search.ph"))}">
          <select data-on="radarFieldPick" aria-label="${esc(t("radar.col.field"))}"><option value="">${t("radar.allfields")}</option>${Object.keys(FIELDS).map((id) => `<option value="${id}"${ui.radarField === id ? " selected" : ""}>${esc(fieldName(id))}</option>`).join("")}</select>
        </div>
        <div class="list" id="radar-results">${ui.radarQuery || ui.radarField ? searchResults(r) : `<p class="small muted">${t("radar.search.hint")}</p>`}</div>
      </section>
      <p class="src">${t("src.demand", dateText(src.demand_computed_date))} ${t("src.share", esc(src.ai_usage.source_name), dateText(src.ai_usage.release_date), esc(src.task_coverage.source_name))}</p>
    </section>

    <section class="stack">
      <div><h2>${t("radar.skills.h")}</h2><p class="muted small">${t("radar.skills.p", fmt(ref, 0))}</p></div>
      <div class="row between">
        <div class="seg" role="group" aria-label="${t("radar.skills.h")}">${tabs.map(([id, label]) => `<button type="button" data-act="radarTab" data-id="${id}" aria-pressed="${tab === id}">${label}</button>`).join("")}</div>
        ${tab === "fields" ? "" : `<div class="tags">${["all", ...STATUSES].map((s) => `<button type="button" class="toggle" data-act="radarFilter" data-id="${s}" aria-pressed="${filter === s}">${s === "all" ? t("all") : t("status." + s)}</button>`).join("")}</div>`}
      </div>
      <section class="card">${tab === "fields" ? fieldTable(r) : `<div class="list">${(tab === "topics" ? shown.map((x) => topicItem(x, ref)) : shown.map(skillItem)).join("") || `<p class="small muted">${t("radar.none")}</p>`}</div>
        ${list.length > shown.length ? `<div class="row" style="margin-top:12px"><button type="button" class="btn small" data-act="radarMore">${t("show.all", list.length)}</button></div>` : ""}`}
      </section>
      ${aiSource(src)}
    </section>

    <section class="card stack">
      <h2>${t("radar.read.h")}</h2>
      <ul class="stack tight small"><li>${t("radar.read.1")}</li><li>${t("radar.read.2")}</li><li>${t("radar.read.3")}</li><li>${t("radar.read.4")}</li><li>${t("radar.read.5")}</li></ul>
      <div class="row"><a class="btn primary" href="#/futures">${t("radar.change")} →</a><a class="btn" href="#/matches">${t("you.go")} →</a><a class="btn ghost" href="#/sources">${t("nav.sources")}</a></div>
    </section>
  </div>`;
};
Object.assign(ACT, {
  radarTab: (el) => { ui.radarTab = el.dataset.id; ui.showAllSkills = false; redraw(); },
  radarFilter: (el) => { ui.radarFilter = el.dataset.id; redraw(); },
  radarMore: () => { ui.showAllSkills = true; redraw(); },
  radarField: (el) => { ui.radarField = el.dataset.id; redraw(); },
});
Object.assign(ON, {
  radarQuery: async (el) => {
    ui.radarQuery = el.value;
    const out = $("#radar-results");
    if (out) out.innerHTML = ui.radarQuery || ui.radarField ? searchResults(await getRadar()) : `<p class="small muted">${t("radar.search.hint")}</p>`;
  },
  radarFieldPick: (el) => { ui.radarField = el.value; redraw(); },
});

/* ---------- one occupation ---------- */

function taskRow(x) {
  const time = x.hours_alone && x.minutes_with_ai ? t("task.time", fmt(x.hours_alone, 1), fmt(x.minutes_with_ai, 0)) : "";
  return `<div class="task"><span>${esc(x.task)}</span><span class="v">${fmt(x.ai_share, 0)}%</span>
    ${bar(x.ai_share, "ai")}
    <span class="tiny muted" style="grid-column:1/-1">${x.ai_share > 0 ? `${t("task.range", fmt(x.ai_share_low, 0), fmt(x.ai_share_high, 0))}${x.automation_pct !== null && x.automation_pct !== undefined ? ` · ${t("task.auto", fmt(x.automation_pct, 0))}` : ""}${time ? ` · ${time}` : ""}` : t("task.none")}</span></div>`;
}

function licenceCard(l) {
  if (!l) return "";
  return `<section class="card stack tight" style="border-color:var(--warn)"><h2>${t("lic.h")}</h2>
    <p>${t("lic.p", `<strong>${l.url ? `<a href="${safeUrl(l.url)}" target="_blank" rel="noopener">${esc(l.body)}</a>` : esc(l.body)}</strong>`)}</p>
    <p class="small muted">${esc(l.requirement)}</p>
    ${l.verified_date ? `<p class="src">${t("lic.checked", dateText(l.verified_date))}</p>` : `<p class="src">${t("lic.unchecked")}</p>`}</section>`;
}

function demandSignals(d) {
  if (!d) return "";
  return d.signals.map((s) => s.signal === "mycol"
    ? `<li>${t("sig.mycol." + s.status, esc(s.occupation || ""))}</li>`
    : `<li>${t("sig.ads", esc(s.group_name), signed(s.change_pct))}</li>`).join("")
    + (d.wage ? `<li>${t("sig.wage", Math.round(d.wage.median).toLocaleString(LOCALE[LANG]), d.wage.year)}</li>` : "");
}

PAGES.occ = async (args) => {
  const r = await cached(`/api/occupations/${encodeURIComponent(args[0] || "")}?${scenarioQuery()}`);
  const occ = r.occupation, o = r.outlook, ai = r.ai || {};
  const seen = r.tasks.filter((x) => x.ai_share > 0);
  const mine = [...r.tasks].filter((x) => x.ai_share === 0).sort((a, b) => (b.importance || 0) - (a.importance || 0));
  const lowest = mine.length >= 3 ? mine : [...r.tasks].sort((a, b) => a.ai_share - b.ai_share);
  const scen = Object.entries(r.outlooks).map(([id, x]) => `<div class="card pad-s tile"><span class="small muted">${t("scn." + id)}</span>
      <div class="big">${fmt(x.outlook, 0)} <small>${signed(x.change)}</small></div>${statusChip(x.status)}</div>`).join("");
  const band = ai.ai_share_low !== undefined ? `<span class="band" style="left:${ai.ai_share_low}%;width:${Math.max(1, ai.ai_share_high - ai.ai_share_low)}%"></span>` : "";
  const skills = r.skills.filter((s) => s.kind === "skill"), knowledge = r.skills.filter((s) => s.kind === "knowledge");
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow"><a href="#/radar">${t("nav.radar")}</a> · ${esc(fieldName(occ.field_id))}</p>
      <h1>${esc(occ.title)}</h1>
      <p class="lead">${esc(occ.description)}</p>
      ${r.titles.length ? `<p class="small muted">${t("occ.titles")} ${r.titles.slice(0, 6).map(esc).join(" · ")}</p>` : ""}
      <div class="tags">${occ.mycol === "yes" ? `<span class="chip brand">${t("mycol.yes")}</span>` : occ.mycol === "near" ? `<span class="chip plain">${t("mycol.near")}</span>` : `<span class="chip plain">${t("mycol.no")}</span>`}
        ${occ.job_zone ? `<span class="chip plain">${t("zone." + occ.job_zone)}</span>` : ""}<span class="chip plain">O*NET ${esc(occ.occ_id)}</span>
        ${occ.isco ? `<span class="chip plain" title="${esc(occ.isco_title || "")}">ISCO/MASCO ${esc(occ.isco)}</span>` : ""}${occ.riasec ? `<span class="chip plain" title="${esc(t("occ.riasec"))}">RIASEC ${esc(occ.riasec)}</span>` : ""}</div>
      ${jobLinks(occ.search_title)}
    </header>
    ${licenceCard(r.licence)}

    <section class="stack"><h2>${t("occ.outlook.h", 2030)}</h2><div class="grid three">${scen}</div>
      <p class="src">${t("scn.estimate.long")}</p></section>

    <section class="card stack"><h2>${t("occ.signals.h")}</h2>
      <div class="meter"><span>${t("sig.demand")}</span>${bar(o.demand)}<span class="v">${fmt(o.demand, 0)}</span></div>
      <ul class="small stack tight">${demandSignals(r.demand)}</ul>
      <div class="meter"><span>${t("sig.share")}</span>${bar(o.ai_share, "ai tall", band + `<span class="mark" style="left:${o.ai_share_reference}%" title="${esc(t("radar.avg", fmt(o.ai_share_reference, 0)))}"></span>`)}<span class="v">${fmt(o.ai_share, 0)}%</span></div>
      <p class="small muted">${t("sig.share.p", fmt(o.ai_share, 0), fmt(o.ai_share_low, 0), fmt(o.ai_share_high, 0), fmt(o.ai_share_reference, 0), ai.tasks_covered, ai.tasks)}${ai.thin_evidence ? ` ${t(ai.prior_basis === "anthropic_exposure" ? "radar.thin.exposure" : "radar.thin.title")}` : ""}</p>
      <div class="tags"><span class="chip plain">${t("sig.tempo", fmt(o.tempo, 2))}</span>${o.builder ? `<span class="chip plain">${t("sig.builder", fmt(o.builder, 0))}</span>` : ""}
        ${ai.automation_pct !== null && ai.automation_pct !== undefined ? `<span class="chip plain">${t("sig.auto", fmt(ai.automation_pct, 0))}</span>` : ""}
        ${ai.usage_pct_my !== null && ai.usage_pct_my !== undefined ? `<span class="chip plain">${t("sig.usage", fmt(ai.usage_pct_my, 2), fmt(ai.usage_pct, 2))}</span>` : ""}</div>
      ${aiSource(r.source)}
    </section>

    <section class="grid two">
      <div class="card stack"><h2>${t("occ.ai.h")}</h2><div>${seen.slice(0, 5).map(taskRow).join("") || `<p class="small muted">${t("occ.ai.none")}</p>`}</div></div>
      <div class="card stack"><h2>${t("occ.human.h")}</h2><div>${lowest.slice(0, 5).map(taskRow).join("")}</div></div>
    </section>
    <section class="card"><details class="more"><summary>${t("occ.tasks.all", r.tasks.length)}</summary><div>${r.tasks.map(taskRow).join("")}</div></details></section>

    <section class="card stack"><h2>${t("occ.skills.h")}</h2>
      ${r.technologies.length ? `<div><p class="small strong">${t("occ.tools")}</p><div class="tags">${r.technologies.slice(0, 24).map(dotName).join("")}</div></div>` : ""}
      <div><p class="small strong">${t("occ.rated")}</p><div class="tags">${skills.slice(0, 12).map(dotName).join("")}</div></div>
      <div><p class="small strong">${t("occ.knowledge")}</p><div class="tags">${knowledge.slice(0, 10).map(dotName).join("")}</div></div>
      <p class="src">${t("occ.skills.src")}</p>
    </section>

    ${r.evidence ? `<section class="card stack">${evidenceLines(r.evidence)}</section>` : ""}
    <section class="card stack"><h2>${t("occ.sdg.h")}</h2>${r.sdg.map((s) =>
      `<div class="stack tight"><div class="row">${sdgChip(s.target)}<span class="strong small">${esc(sdgText(s.target))}</span></div><p class="small muted">${esc(s.rationale)}</p></div>`).join("") || `<p class="small muted">–</p>`}</section>

    ${r.related.length ? `<section class="card stack"><h2>${t("occ.related")}</h2><div class="tags">${r.related.map((x) => `<a class="chip plain" href="#/occ/${esc(x.occ_id)}">${esc(x.title)}</a>`).join("")}</div></section>` : ""}

    <div class="row"><a class="btn primary" href="#/pathway/${esc(occ.occ_id)}">${t("occ.path")} →</a><a class="btn" href="#/matches">${t("you.go")}</a></div>
  </div>`;
};

/* ---------- 3 Matches ---------- */

function partBars(m) {
  const c = m.components;
  const used = Object.values(c).reduce((s, x) => s + (x.score === null ? 0 : x.weight), 0) || 1;
  return `<div class="parts">${["field", "interest", "skill", "outlook"].map((k) => {
    const x = c[k];
    return `<div class="part"><div class="row between"><span>${t("part." + k)}</span><span class="pv">${x.score === null ? t("part.none") : `${fmt(x.points)} / ${fmt(100 * x.weight / used)}`}</span></div>${bar(x.score, k === "outlook" ? m.outlook.status : "")}</div>`;
  }).join("")}</div>`;
}

function scenarioRanks(m) {
  if (!m.scenario_ranks) return "";
  const r = m.scenario_ranks;
  const same = new Set(Object.values(r)).size === 1;
  return `<span class="chip plain" title="${esc(t("match.ranks.title"))}">${same ? t("match.ranks.same", Object.values(r)[0]) : SCENARIO_IDS.map((id) => `${t("scn." + id + ".short")} #${r[id]}`).join(" · ")}</span>`;
}

/* "Why this score?": fetched while its panel is open, and again whenever the person, the scenario,
   the goals or the language change (the request body is the key). */
const whySig = (id) => JSON.stringify(matchBody({ occ_id: id, lang: LANG }));
const whyLoading = new Set();
function currentWhy(id) {
  const sig = whySig(id), why = ui.why[id];
  if (why && why.sig === sig) return why;
  if (!whyLoading.has(sig)) {
    whyLoading.add(sig);
    setTimeout(async () => {
      let result;
      try { result = await cached("/api/explain", JSON.parse(sig)); } catch (e) { result = { text: e.message, source: "error", text_lang: LANG }; }
      whyLoading.delete(sig);
      ui.why[id] = { ...result, sig };
      if (location.hash.startsWith("#/matches") && ui.open[id]) redraw();
    }, 0);
  }
  return null;
}
const num = (v) => String(Number(v));
/* The template in Malay or Chinese, written from the facts the server used for its English one. */
function whyTemplate(f) {
  const pts = (k) => (f[k] === null ? t("why.t.unscored") : t("why.t.points", num(f[k]), num(f.max_points[k])));
  const o = f.outlook;
  const scen = state.scenario === "custom" ? t("why.t.custom", Math.round(state.adoption * 100)) : t("scn." + state.scenario);
  const parts = [t("why.t.main", f.occupation, num(f.match_score), pts("field_fit"), pts("skill_fit"), pts("outlook_points"), scen,
    t("status." + o.status).toLowerCase(), t("why.t.demand." + (o.malaysian_demand === "no data" ? "none" : o.malaysian_demand)),
    num(o.ai_share_of_tasks), num(o.average_ai_share))];
  if (f.learning_path && f.learning_path.length) {
    const c = f.learning_path[0];
    parts.push(t("why.t.course", c.course, c.provider, c.hours ? t("why.t.hours", num(c.hours)) : "", c.covers.join(", ")));
  } else if (f.biggest_gaps && f.biggest_gaps.length) {
    const g = f.biggest_gaps[0];
    parts.push(t("why.t.gap", g.skill, num(g.your_level), num(g.level_needed)));
  }
  if (f.licence) parts.push(t("why.t.licence", f.licence));
  if (f.sdg.length) parts.push(t("why.t.sdg", f.sdg[0].target, sdgText(f.sdg[0].target)));
  if (f.sdg_goals_picked && f.sdg_goals_picked.length) parts.push(t("why.t.goals", f.sdg_goals_picked.join(", "), num(f.sdg_bonus)));
  return parts.join(LANG === "zh" ? "" : " ");
}
const whyText = (why) => esc(why.text_lang === LANG || !why.facts ? why.text : whyTemplate(why.facts));

function detailHtml(m, sim) {
  const d = m.skill_detail, o = m.outlook, s = m.stability, ai = m.ai || {};
  const why = currentWhy(m.occ_id);
  const tips = why && why.to_raise;
  const gaps = d.gaps.filter((g) => g.rated !== false).slice(0, 6);
  const unrated = d.counts.gaps - d.gaps.filter((g) => g.rated !== false).length;
  return `<div class="full stack" style="border-top:1px solid var(--line);padding-top:16px">
    <div class="stack tight"><h3>${t("match.why.h")}</h3>
      ${why ? `<p>${whyText(why)}</p><p class="src">${t(why.source === "llm" ? "match.why.llm" : "match.why.template", esc(why.model || ""))}</p>` : loading()}
      ${tips && tips.gain !== null ? `<p class="note">${t("match.raise", `<strong>${tips.learn.map(esc).join(", ")}</strong>`, signed(tips.gain), fmt(tips.new_score))}</p>` : ""}
      ${tips && tips.interest_points ? `<p class="note">${t("match.raise.interest", fmt(tips.interest_points, 0))} <a href="#/you/interests">${t("int.start")}</a></p>` : ""}
    </div>
    <div class="stack tight"><h3>${t("match.outlook.h")}</h3>
      <p class="small">${t("match.outlook.p", fmt(o.demand, 0), fmt(o.ai_share, 0), fmt(o.ai_share_reference, 0), signed(o.change), fmt(o.outlook, 0))}</p>
      ${s ? `<p class="small">${t("match.stability.p", sim.futures, fmt(s.top3, 0), fmt(s.top1, 0), fmt(s.score_low), fmt(s.score_high))}</p>` : ""}
    </div>
    <div class="grid two">
      <div class="stack tight"><h3>${t("match.have.h")}</h3><div class="tags">${[...d.tech_used, ...d.strengths.slice(0, 6)].map(dotName).join("") || `<span class="small muted">${t("match.have.none")}</span>`}</div></div>
      <div class="stack tight"><h3>${t("match.gap.h")}</h3>
        <div class="tags">${d.tech_missing.slice(0, 8).map(dotName).join("")}</div>
        ${gaps.map((g) => `<div class="meter"><span>${esc(g.skill_name)}</span>${bar(100 * g.your_level / g.level_needed, g.ai.status)}<span class="v">${fmt(g.your_level)} → ${fmt(g.level_needed)}</span></div>`).join("")}
        ${unrated > 0 ? `<p class="src">${t("match.gap.unrated", unrated)} <a href="#/you/skills">${t("sk.start")}</a></p>` : ""}
      </div>
    </div>
    ${ai.ai_tasks && ai.ai_tasks.length ? `<div class="grid two">
      <div class="stack tight"><h3>${t("occ.ai.h")}</h3><div>${ai.ai_tasks.map(taskRow).join("")}</div></div>
      <div class="stack tight"><h3>${t("occ.human.h")}</h3><div>${ai.human_tasks.map(taskRow).join("")}</div></div></div>` : ""}
    <div class="grid two">${routeLines(m.routes)}${evidenceLines(m.evidence)}</div>
    ${m.licence ? `<p class="small">${t("lic.short", esc(m.licence.body))}</p>` : ""}
    ${m.sdg.length ? `<div class="stack tight"><h3>${t("occ.sdg.h")}</h3>${m.sdg.slice(0, 2).map((x) => `<p class="small">${sdgChip(x.target)} ${esc(x.rationale)}</p>`).join("")}</div>` : ""}
    <div class="row between"><a class="btn small" href="#/occ/${esc(m.occ_id)}">${t("match.occ")}</a>${jobLinks(m.search_title)}</div>
  </div>`;
}

const FLAGS_SHOWN = ["needs_extra_education", "below_education", "current_occupation", "licence_needed"];
function matchCard(m, sim) {
  const open = Boolean(ui.open[m.occ_id]);
  const s = m.stability;
  const flags = m.flags.filter((f) => FLAGS_SHOWN.includes(f));
  const goals = m.sdg_choice && m.sdg_choice.bonus ? `<span class="chip rising">${t("match.sdg.bonus", m.sdg_choice.goals.join(", "), fmt(m.sdg_choice.bonus, 0))}</span>` : "";
  return `<article class="card match" id="m-${esc(m.occ_id)}">
    <span class="rank" aria-label="${t("match.rank", m.rank)}">${m.rank}</span>
    <div class="body stack tight">
      <div><h2><a href="#/occ/${esc(m.occ_id)}" style="color:inherit;text-decoration:none">${esc(m.title)}</a></h2><span class="small muted">${esc(fieldName(m.field_id))}</span></div>
      <div class="tags">${statusChip(m.outlook.status)}${mycolChip(m.mycol)}${s ? `<span class="chip ai" title="${esc(t("match.stability.title", sim.futures))}">${t("match.stability", fmt(s.top3, 0))}</span>` : ""}${scenarioRanks(m)}${evidenceChip(m.evidence && m.evidence.grade)}${goals}
        ${flags.map((f) => `<span class="chip ${f === "current_occupation" ? "brand" : "warn"}">${t("flag." + f)}</span>`).join("")}</div>
    </div>
    <div class="ring" style="--v:${m.total}" role="img" aria-label="${t("match.score", fmt(m.total))}"><span>${fmt(m.total)}<small>/ 100</small></span></div>
    <div class="full stack tight">${partBars(m)}
      ${m.skill_detail.tech_missing.length ? `<div class="row" style="gap:6px"><span class="small strong">${t("match.learn")}</span>${m.skill_detail.tech_missing.slice(0, 3).map(dotName).join("")}</div>` : ""}
      <div class="row"><button type="button" class="btn small" data-act="why" data-id="${esc(m.occ_id)}" aria-expanded="${open}">${t(open ? "match.less" : "match.why")}</button>
        <a class="btn small primary" href="#/pathway/${esc(m.occ_id)}" data-act="pick" data-id="${esc(m.occ_id)}">${t("match.path")} →</a></div>
    </div>
    ${open ? detailHtml(m, sim) : ""}
  </article>`;
}

/* When "Update data" has brought new numbers since the last visit, say what moved. */
function replanNote(m) {
  const sig = JSON.stringify([profileBody(), state.sdgGoals, state.scenario === "custom" ? state.adoption : state.scenario]);
  const now = { id: m.trend_data.id, date: m.trend_data.computed_date, sig, top: m.ranking.slice(0, 12).map((r) => [r.occ_id, r.title, r.rank]) };
  const prev = state.seen;
  if (!m.trend_data.what_if) { state.seen = now; save(); }
  if (!prev || prev.sig !== sig || prev.id === now.id || m.trend_data.what_if) return "";
  const before = Object.fromEntries(prev.top.map(([id, , rank]) => [id, rank]));
  const moved = now.top.filter(([id, , rank]) => before[id] && before[id] !== rank).slice(0, 4);
  return `<div class="note stack tight"><p class="strong">${t("replan.h", dateText(prev.date), dateText(now.date))}</p>
    ${moved.length ? `<ul class="small">${moved.map(([id, name, rank]) => `<li>${t("replan.moved", esc(name), before[id], rank)}</li>`).join("")}</ul>` : `<p class="small">${t("replan.same")}</p>`}</div>`;
}

function goalPicker(m) {
  return `<section class="card stack">
    <div class="row between"><h2>${t("goals.h")}</h2>${state.sdgGoals.length ? `<button type="button" class="btn small ghost" data-act="goalClear">${t("goals.clear")}</button>` : ""}</div>
    <p class="muted small">${t("goals.p", m.sdg_bonus.direct, m.sdg_bonus.indirect)}</p>
    <div class="tags">${m.sdg_goals.map((g) => `<button type="button" class="toggle" data-act="goal" data-id="${esc(g.goal)}" aria-pressed="${state.sdgGoals.includes(g.goal)}" title="${esc(sdgText(g.goal))}">SDG ${esc(g.goal)} · ${esc(nameOf(g.goal_name))} · ${t("goals.occs", g.occupations)}</button>`).join("")}</div>
  </section>`;
}

function adCard() {
  const r = ui.ad;
  const list = (rows) => rows.map((x) => `<div class="row" style="gap:6px">${dotName(x)}${x.course ? `<a class="small" href="${safeUrl(x.course.url)}" target="_blank" rel="noopener">${esc(x.course.title)}</a>` : ""}</div>`).join("");
  return `<section class="card stack">
    <div><h2>${t("ad.h")}</h2><p class="muted small">${t("ad.p")}</p></div>
    <textarea id="ad-text" placeholder="${esc(t("ad.ph"))}">${esc(ui.adText)}</textarea>
    <div class="row"><button type="button" class="btn small primary" data-act="adRun">${t("ad.go")}</button>${ui.adError ? `<span class="small fail">${esc(ui.adError)}</span>` : ""}</div>
    ${r ? `<div class="grid two">
        <div class="stack tight"><h3>${t("ad.have", r.have.length)}</h3>${list(r.have) || `<p class="small muted">${t("ad.none")}</p>`}</div>
        <div class="stack tight"><h3>${t("ad.miss", r.missing.length)}</h3>${list(r.missing) || `<p class="small muted">${t("ad.none")}</p>`}</div></div>
      ${r.titles.length ? `<p class="small">${t("ad.titles")} ${r.titles.map((x) => occLink(x.occ_id, x.title)).join(" · ")}</p>` : ""}
      ${r.roles.length ? `<p class="small">${t("ad.close")} ${r.roles.map((x) => `${occLink(x.occ_id, x.title)} (${x.of_ad}%)`).join(" · ")}</p>` : ""}
      <p class="src">${t("ad.method")}</p>` : ""}
  </section>`;
}

/* What made a field's fit, in the page's language: the parts that had an answer. */
function fieldExplain(f) {
  const parts = ["choice", "interest", "experience"].filter((k) => f.parts[k].score !== null)
    .map((k) => `${t("part." + k)} ${fmt(f.parts[k].score, 0)}`);
  return esc(parts.join(" · ")) + (LANG === "en" && f.parts.experience.score !== null && f.explain.includes("(")
    ? ` <span>(${esc(f.explain.slice(f.explain.indexOf("(") + 1, f.explain.lastIndexOf(")")))})</span>` : "");
}

PAGES.matches = async () => {
  const m = await getMatches(ui.showMore ? 30 : 12);
  rememberScenarios(m.scenarios);
  const people = state.demo ? await cached("/api/profiles") : [];
  const demo = people.find((p) => p.profile_id === state.demo);
  const listed = m.results.filter((x) => !x.flags.includes("needs_extra_education") && !x.flags.includes("below_education") && !x.flags.includes("current_occupation"));
  const shown = ui.showMore ? listed : listed.slice(0, SHOWN_MATCHES);
  const beyond = m.ranking.filter((x) => x.flags.includes("needs_extra_education")).slice(0, 8);
  const below = m.ranking.filter((x) => x.flags.includes("below_education")).length;
  const cur = m.current;
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 3)} · ${t("nav.matches")}</p>
      <h1>${demo ? t("match.h1.demo", esc(demo.name)) : t("match.h1")}</h1>
      <p class="lead">${demo ? esc(t("persona." + demo.profile_id) === "persona." + demo.profile_id ? demo.story : t("persona." + demo.profile_id)) : t("match.lead", m.total_occupations)}</p></header>
    ${!hasProfile() ? `<div class="warn row between"><span>${t("match.empty")}</span><a class="btn small" href="#/you">${t("home.start")}</a></div>` : ""}
    ${replanNote(m)}
    ${scenarioControl({ adoption: m.adoption, horizon: m.horizon_year }, m.scenarios)}
    ${cur ? `<section class="card stack" style="border-color:var(--brand)"><div class="row between"><div><p class="eyebrow">${t("match.now")}</p><h2>${esc(cur.title)}</h2></div>${statusChip(cur.outlook.status)}</div>
      <p>${t("match.now.p", fmt(cur.outlook.ai_share, 0), fmt(cur.outlook.ai_share_reference, 0), signed(cur.outlook.change), `#${cur.rank}`)}</p>
      <div class="row"><a class="btn small" href="#/occ/${esc(cur.occ_id)}">${t("match.now.tasks")}</a></div></section>` : ""}
    <section class="card stack"><h2>${t("match.fields.h")}</h2>
      <div class="stack tight">${m.fields.filter((f) => f.fit !== null).slice(0, 6).map((f) => `<div class="meter"><span>${esc(fieldName(f.id))}</span>${bar(f.fit)}<span class="v">${fmt(f.fit, 0)}</span></div><p class="tiny muted">${fieldExplain(f)}</p>`).join("") || `<p class="small muted">${t("match.fields.none")}</p>`}</div>
      ${m.insights.length ? `<ul class="small">${m.insights.map((i) => `<li>${esc(i.text)}</li>`).join("")}</ul>` : ""}
      <p class="src">${t("match.fields.src")}</p></section>
    ${goalPicker(m)}
    <section class="stack"><div class="row between"><h2>${t(cur ? "match.moves.h" : "match.top.h")}</h2><span class="small muted">${t("match.sim", m.simulation ? m.simulation.futures : 0)}</span></div>
      ${shown.map((x) => matchCard(x, m.simulation || { futures: 0 })).join("")}
      ${!ui.showMore && listed.length > shown.length ? `<div><button type="button" class="btn" data-act="showMore">${t("match.more")}</button></div>` : ""}
      ${beyond.length ? `<p class="small muted">${t("match.beyond", beyond.map((x) => occLink(x.occ_id, x.title)).join(", "))}</p>` : ""}
      ${below ? `<p class="small muted">${t("match.below", below)}</p>` : ""}
    </section>
    ${adCard()}
    <div class="row"><a class="btn primary" href="#/futures">${t("match.futures")} →</a><a class="btn" href="#/you">${t("match.edit")}</a></div>
    <p class="src">${t("src.match", m.trend_data.id, dateText(m.trend_data.computed_date), dateText(m.trend_data.ai_usage_release))}</p>
  </div>`;
};
Object.assign(ACT, {
  showMore: () => { ui.showMore = true; redraw(); },
  pick: (el) => { state.occId = el.dataset.id; save(); },
  goal: (el) => {
    const g = el.dataset.id;
    state.sdgGoals = state.sdgGoals.includes(g) ? state.sdgGoals.filter((x) => x !== g) : [...state.sdgGoals, g];
    ui.why = {}; save(); redraw();
  },
  goalClear: () => { state.sdgGoals = []; ui.why = {}; save(); redraw(); },
  why: (el) => { const id = el.dataset.id; ui.open[id] = !ui.open[id]; redraw(); },
  adRun: async () => {
    ui.adText = $("#ad-text").value;
    ui.adError = null;
    try { ui.ad = await request("/api/jobad", { text: ui.adText, technologies: state.demo ? [] : state.techs, ...scenarioBody() }); } catch (e) { ui.ad = null; ui.adError = e.message; }
    redraw();
  },
});

/* ---------- 4 Pathway ---------- */

async function chosenOccupation(arg) {
  if (arg) { state.occId = arg; save(); return arg; }
  if (state.occId) return state.occId;
  const m = await getMatches();
  const first = m.results.find((x) => !x.flags.includes("needs_extra_education") && !x.flags.includes("below_education")) || m.results[0];
  return first.occ_id;
}
const pathResources = (L) => {
  const seen = new Map();
  for (const r of [...L.stages.flatMap((s) => s.resources), ...L.skills.flatMap((s) => s.resources)]) if (!seen.has(r.url)) seen.set(r.url, r);
  return [...seen.values()];
};
function progressOf(L) {
  const done = state.done[L.role.occ_id] || {};
  const all = pathResources(L);
  const ticked = all.filter((r) => done[r.url]);
  const hours = (list) => list.reduce((s, r) => s + (r.hours || 0), 0);
  return { all, ticked, planned: hours(all), finished: hours(ticked), share: all.length ? ticked.length / all.length : 0 };
}
function resourceRow(r, occId) {
  const done = Boolean((state.done[occId] || {})[r.url]);
  const meta = [esc(r.provider), r.hours ? t("path.hours", fmt(r.hours, 0)) : t("path.nohours"), t("fmt." + (r.format || "course")),
    r.cost_myr ? `RM ${fmt(r.cost_myr, 0)}` : t("path.free"), t("path.checked", dateText(r.verified_date))];
  return `<label class="step${done ? " done" : ""}"><input type="checkbox" data-on="done" data-url="${esc(r.url)}"${done ? " checked" : ""} aria-label="${esc(t("path.tick", r.title))}">
    <span><a class="t" href="${safeUrl(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a><span class="src" style="display:block">${meta.join(" · ")}</span>${r.notes ? `<span class="tiny muted">${esc(r.notes)}</span>` : ""}</span></label>`;
}

PAGES.pathway = async (args) => {
  const occId = await chosenOccupation(args[0]);
  ui.pathOcc = occId;  // the occupation this page shows: a ticked box belongs to it
  const [L, m] = await Promise.all([cached("/api/learn", matchBody({ occ_id: occId })), getMatches()]);
  const p = progressOf(L);
  const options = m.results.filter((x) => !x.flags.includes("needs_extra_education") && !x.flags.includes("below_education")).slice(0, 12);
  if (!options.some((x) => x.occ_id === occId)) options.push({ occ_id: occId, title: L.role.name, rank: null });
  const badges = [["start", p.ticked.length >= 1], ["half", p.share >= 0.5], ["done", p.all.length > 0 && p.share >= 1]];
  let n = 0;
  const stage = (title, body, note = "") => (body ? `<section class="card stack"><div class="row"><span class="rank" style="width:30px;height:30px;border-radius:50%;background:var(--brand-soft);color:var(--brand-strong);display:grid;place-items:center;font-weight:750">${++n}</span><h2>${title}</h2></div>${note ? `<p class="small muted">${note}</p>` : ""}${body}</section>` : "");
  const skills = L.skills.map((s) => `<div class="stack tight" style="padding:10px 0;border-top:1px solid var(--line)">
      <div class="row">${dotName({ ...s.ai, skill_name: s.skill_name })}${s.your_level !== undefined && s.kind !== "technology" ? `<span class="small muted">${t("path.level", fmt(s.your_level), fmt(s.level_needed))}</span>` : ""}${(s.sdg || []).slice(0, 2).map((x) => sdgChip(x.target)).join("")}</div>
      ${s.resources.length ? s.resources.map((r) => resourceRow(r, occId)).join("") : `<p class="small muted">${t("path.nocourse")}</p>`}</div>`).join("");
  const handsOn = L.hands_on.map((r) => `<p class="small"><a href="${safeUrl(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a> · ${esc(r.provider)}<br><span class="muted">${esc(r.notes)}</span></p>`).join("");
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 4)} · ${t("nav.pathway")}</p><h1>${t("path.h1", esc(L.role.name))}</h1>
      <p class="lead">${t(L.personal && hasProfile() ? "path.lead.personal" : "path.lead.role")}</p></header>
    <section class="card pad-s row between">
      <label class="field" style="flex:1 1 260px">${t("path.role")}<select data-on="pathOcc">${options.map((x) => `<option value="${esc(x.occ_id)}"${x.occ_id === occId ? " selected" : ""}>${x.rank ? `#${x.rank} ` : ""}${esc(x.title)}</option>`).join("")}</select></label>
      <label class="field">${t("you.hours")}<select data-on="pathHours" class="inline">${[3, 5, 8, 10, 15, 20].map((h) => `<option value="${h}"${state.hours === h ? " selected" : ""}>${t("you.hours.n", h)}</option>`).join("")}</select></label>
    </section>
    <section class="grid three">
      <div class="card tile"><div class="big">${fmt(L.total_hours, 0)} <small>${t("path.h")}</small></div><p class="small muted">${t(L.resources_without_hours ? "path.total" : "path.total.all", L.resources_without_hours)}</p></div>
      <div class="card tile"><div class="big">${fmt(L.weeks, 0)} <small>${t("path.w")}</small></div><p class="small muted">${t("path.weeks", L.hours_per_week)}</p></div>
      <div class="card tile"><div class="big">${p.all.filter((r) => !r.cost_myr).length} <small>/ ${p.all.length}</small></div><p class="small muted">${t("path.freecount")}</p></div>
    </section>
    <section class="card stack"><div class="row between"><h2>${t("path.progress.h")}</h2><span class="small muted num">${t("path.progress", p.ticked.length, p.all.length, fmt(p.finished, 0), fmt(p.planned, 0))}</span></div>
      <div class="progress"><i style="width:${Math.round(p.share * 100)}%"></i></div>
      <div class="tags">${badges.map(([id, on]) => `<span class="badge${on ? " on" : ""}">${on ? "★" : "☆"} ${t("badge." + id)}</span>`).join("")}</div>
      <div class="row"><button type="button" class="btn small" data-act="ics" data-id="${esc(occId)}">${t("path.ics")}</button><span class="src">${t("path.ics.note")}</span></div>
    </section>
    ${licenceCard(L.licence)}
    ${stage(t("path.s1", esc(fieldName(L.role.field_id))), L.stages[0].resources.map((r) => resourceRow(r, occId)).join(""))}
    ${stage(t("path.s2"), skills, t("path.s2.p") + (L.skills_not_shown ? ` ${t("path.s2.more", L.skills_not_shown)}` : ""))}
    ${stage(t("path.s3"), handsOn, t("path.s3.p"))}
    <div class="row"><a class="btn primary" href="#/sdg">${t("path.sdg")} →</a><a class="btn" href="#/matches">${t("nav.matches")}</a>${jobLinks(L.role.search_title)}</div>
    <p class="src">${t("path.src")}</p>
  </div>`;
};
function learnerId() {
  if (!state.learner) {
    const bytes = crypto.getRandomValues(new Uint8Array(12));
    state.learner = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  return state.learner;
}
Object.assign(ON, {
  pathOcc: (el) => { location.hash = `#/pathway/${el.value}`; },
  pathHours: (el) => { state.hours = Number(el.value); save(); redraw(); },
  done: async (el) => {
    const occId = ui.pathOcc || state.occId;
    const done = state.done[occId] || (state.done[occId] = {});
    if (el.checked) done[el.dataset.url] = true; else delete done[el.dataset.url];
    save();
    const L = await cached("/api/learn", matchBody({ occ_id: occId }));
    const p = progressOf(L);
    // the anonymous tally behind the SDG page: a random id, the occupation and hours; nothing about the person
    request("/api/sdg/record", { learner: learnerId(), occ_id: occId, hours_planned: Math.round(p.planned * 10) / 10,
      hours_done: Math.round(p.finished * 10) / 10, items_done: p.ticked.length }).then(() => { save(); cache.delete("/api/sdg/summary"); }).catch(() => {});
    redraw();
  },
});
ACT.ics = async (el) => {
  const occId = el.dataset.id;
  const L = await cached("/api/learn", matchBody({ occ_id: occId }));
  const todo = pathResources(L).filter((r) => !(state.done[occId] || {})[r.url]);
  const start = new Date(); start.setHours(0, 0, 0, 0); start.setDate(start.getDate() + ((8 - start.getDay()) % 7 || 7));  // next Monday
  const ymd = (d) => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  const clean = (s) => String(s).replace(/([,;\\])/g, "\\$1").replace(/\r?\n/g, " ");
  let used = 0;
  const events = todo.map((r, i) => {
    const day = new Date(start); day.setDate(day.getDate() + 7 * Math.floor(used / state.hours));
    used += r.hours || 1;
    const end = new Date(day); end.setDate(end.getDate() + 1);
    return ["BEGIN:VEVENT", `UID:fs-${occId}-${i}@future-skills`, `DTSTAMP:${ymd(new Date())}T000000Z`, `DTSTART;VALUE=DATE:${ymd(day)}`, `DTEND;VALUE=DATE:${ymd(end)}`,
      `SUMMARY:${clean(`${t("path.ics.study")}: ${r.title}`)}`, `DESCRIPTION:${clean(`${r.provider} · ${r.url}`)}`, `URL:${r.url}`, "END:VEVENT"].join("\r\n");
  });
  const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Future Skills//Pathway//EN", ...events, "END:VCALENDAR"].join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
  a.download = `future-skills-${occId}.ics`;
  a.click();
  URL.revokeObjectURL(a.href);
};

/* ---------- 5 SDG ---------- */

PAGES.sdg = async () => {
  const occId = await chosenOccupation();
  const [L, m, all] = await Promise.all([cached("/api/learn", matchBody({ occ_id: occId })), getMatches(), cached("/api/sdg/summary")]);
  const targets = L.sdg.map((x) => `<div class="stack tight" style="padding:12px 0;border-top:1px solid var(--line)">
      <div class="row between"><div class="row">${sdgChip(x.target)}<span class="strong">${esc(sdgText(x.target))}</span></div><span class="num strong">${t("path.hours", fmt(x.hours, 0))}</span></div>
      ${x.role ? `<p class="small"><span class="chip ${x.role.link_strength === "direct" ? "rising" : "plain"}">${t("sdg.link." + x.role.link_strength)}</span> ${esc(x.role.rationale)}</p>` : ""}
      ${x.skills.length ? `<p class="small muted">${t("sdg.through", x.skills.length)} ${x.skills.slice(0, 6).map((k) => `<span title="${esc(k.rationale)}">${esc(k.skill_name)}</span>`).join(" · ")}${x.skills.length > 6 ? " …" : ""}</p>` : ""}</div>`).join("");
  const listed = m.results.filter((x) => !x.flags.includes("needs_extra_education") && !x.flags.includes("below_education"));
  const without = [...listed].sort((a, b) => b.sdg_choice.total_without - a.sdg_choice.total_without).map((x) => x.occ_id);
  const lifted = listed.filter((x) => x.sdg_choice.bonus).map((x) => ({ ...x, was: without.indexOf(x.occ_id) + 1, now: listed.indexOf(x) + 1 }));
  const first = listed[0];
  const tradeoff = lifted.filter((x) => x.was !== x.now).slice(0, 4).map((x) => `<li>${t("sdg.moved", occLink(x.occ_id, x.title), x.was, x.now, x.sdg_choice.goals.join(", "), fmt(x.sdg_choice.bonus, 0))}
      ${first && x.occ_id !== first.occ_id ? t("sdg.cost", fmt(x.pathway.total_hours, 0), fmt(first.pathway.total_hours, 0), esc(first.title)) : ""}</li>`).join("");
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 5)} · ${t("nav.sdg")}</p><h1>${t("sdg.h1")}</h1><p class="lead">${t("sdg.lead")}</p></header>
    <section class="card stack"><div class="row between"><h2>${t("sdg.path.h", esc(L.role.name))}</h2><a class="btn small" href="#/pathway/${esc(occId)}">${t("nav.pathway")}</a></div>
      <p class="muted small">${t("sdg.path.p", fmt(L.total_hours, 0), L.sdg.length)}</p><div>${targets}</div>
      <p class="src">${t("sdg.src")}</p></section>
    ${goalPicker(m)}
    <section class="card stack"><h2>${t("sdg.effect.h")}</h2>
      ${!state.sdgGoals.length ? `<p class="muted">${t("sdg.effect.none")}</p>` : lifted.length ? `<p>${t("sdg.effect.p", lifted.length)}</p>${tradeoff ? `<ul class="stack tight small">${tradeoff}</ul>` : `<p class="small muted">${t("sdg.effect.same")}</p>`}` : `<p class="muted">${t("sdg.effect.zero")}</p>`}
    </section>
    <section class="card stack"><h2>${t("sdg.lose.h")}</h2><ul class="stack tight small"><li>${t("sdg.lose.1")}</li><li>${t("sdg.lose.2")}</li><li>${t("sdg.lose.3")}</li></ul></section>
    <section class="stack"><div><h2>${t("sdg.all.h")}</h2><p class="muted small">${t("sdg.all.p")}</p></div>
      <div class="grid three">
        <div class="card tile"><div class="big">${all.students}</div><p class="small muted">${t("sdg.all.people", all.students_studying)}</p></div>
        <div class="card tile"><div class="big">${all.paths}</div><p class="small muted">${t("sdg.all.paths")}</p></div>
        <div class="card tile"><div class="big">${fmt(all.hours_done, 0)} <small>/ ${fmt(all.hours_planned, 0)} ${t("path.h")}</small></div><p class="small muted">${t("sdg.all.hours")}</p></div>
      </div>
      ${all.targets.length ? `<section class="card"><div class="table-wrap"><table><thead><tr><th>${t("sdg.col.target")}</th><th class="n">${t("sdg.col.people")}</th><th class="n">${t("sdg.col.planned")}</th><th class="n">${t("sdg.col.done")}</th></tr></thead>
        <tbody>${all.targets.map((x) => `<tr><td>${sdgChip(x.target)} <span class="small">${esc(sdgText(x.target))}</span></td><td class="n">${x.students}</td><td class="n">${fmt(x.hours_planned, 0)}</td><td class="n">${fmt(x.hours_done, 0)}</td></tr>`).join("")}</tbody></table></div></section>` : `<p class="small muted">${t("sdg.all.empty")}</p>`}
      <p class="src">${t("sdg.all.method")}</p>
    </section>
    <div class="row"><a class="btn primary" href="#/futures">${t("match.futures")} →</a></div>
  </div>`;
};
