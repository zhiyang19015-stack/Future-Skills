/* Future Skills: the team view, for an HR or career-centre officer. The same engine as the six
   steps, run for every job on a fictional team (scripts/team.py): which jobs AI reaches most, the
   adjacent occupation each can move to, the skills those moves need, hours, and UN targets. */
"use strict";

/* The evidence grade of an occupation's numbers: a letter from three rule-based checks, with the
   reason for each on hover or in the open card. Never a percentage. */
const evidenceChip = (grade) => (grade ? `<span class="chip grade-${esc(grade)}" title="${esc(t("ev." + grade))}">${t("ev.chip", esc(grade))}</span>` : "");
function evidenceLines(e) {
  if (!e) return "";
  const line = (c) => {
    if (c.check === "ai_usage") return t("ev.ai." + c.reason, c.tasks_covered, c.tasks);
    if (c.check === "mapping") return t("ev.map." + c.reason);
    return t("ev.fresh." + c.reason, c.ai_release_days === null ? "–" : c.ai_release_days, c.demand_days === null ? "–" : c.demand_days);
  };
  return `<div class="stack tight"><h3>${t("ev.h")} ${evidenceChip(e.grade)}</h3>
    <p class="small">${t("ev." + e.grade)}</p>
    <ul class="small">${e.checks.map((c) => `<li>${line(c)} <span class="muted">(${c.points}/2)</span></li>`).join("")}</ul>
    <p class="src">${t("ev.note", e.points, e.max_points)}</p></div>`;
}
/* Career routes: the related occupations that stay open from this one under the scenario. */
function routeLines(r) {
  if (!r || !r.related) return "";
  return `<div class="stack tight"><h3>${t("routes.h")}</h3>
    <p class="small">${t("routes.p", r.open, r.related, fmt(r.reach_points, 0))}</p>
    ${r.routes.length ? `<div class="tags">${r.routes.map((x) => `<a class="chip ${esc(x.status)}" href="#/occ/${esc(x.occ_id)}"><i class="dot"></i>${esc(x.title)} · ${fmt(x.total, 0)}</a>`).join("")}</div>` : `<p class="small muted">${t("routes.none")}</p>`}
    <p class="src">${t("routes.src")}</p></div>`;
}

function heatCell(gap) {
  if (gap === null || gap === undefined) return '<td class="n muted">·</td>';
  const level = gap >= 2 ? 3 : gap >= 1 ? 2 : 1;
  return `<td class="n heat h${level}">${fmt(gap)}</td>`;
}

PAGES.team = async () => {
  const v = await cached(`/api/team?${scenarioQuery()}`);
  const moving = v.roles.filter((r) => r.move);
  const b = v.budget;
  const roleRow = (r) => `<tr>
      <td><span class="strong">${occLink(r.occ_id, r.title)}</span><div class="tiny muted">${esc(fieldName(r.field_id))}</div></td>
      <td class="n">${r.headcount}</td>
      <td class="n" title="${esc(t("team.range", fmt(r.ai_share_low, 0), fmt(r.ai_share_high, 0)))}">${fmt(r.ai_share, 0)}%</td>
      <td>${SCENARIO_IDS.map((id) => `<span class="chip ${esc(r.statuses[id])}" title="${esc(t("scn." + id))}"><i class="dot"></i>${t("scn." + id)}</span>`).join(" ")}</td>
      <td>${evidenceChip(r.evidence)}</td></tr>`;
  const moveCard = (r) => `<article class="card pad-s stack tight">
      <div class="row between"><div><p class="tiny muted">${t("team.from", r.headcount, esc(r.title))}</p><h3>${occLink(r.move.occ_id, r.move.title)}</h3></div>
        <div class="tags">${statusChip(r.move.status)}${evidenceChip(r.move.evidence)}</div></div>
      <p class="small">${t("team.move.p", fmt(r.move.total, 0), fmt(r.move.hours, 0), fmt(r.move.weeks, 0), v.team.hours_per_week)}</p>
      ${r.move.gaps.length ? `<div class="tags">${r.move.gaps.slice(0, 5).map((g) => `<span class="chip plain">${esc(g.skill_name)} +${fmt(g.gap)}</span>`).join("")}</div>` : ""}
      ${r.move.courses.length ? `<ul class="small">${r.move.courses.map((c) => `<li><a href="${safeUrl(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a> <span class="muted">· ${esc(c.provider)}${c.hours ? ` · ${t("path.hours", fmt(c.hours, 0))}` : ""} · ${t("path.checked", dateText(c.verified_date))}</span></li>`).join("")}</ul>` : ""}
      ${r.move.sdg.map((s) => `<p class="small">${sdgChip(s.target)} ${esc(s.rationale)}</p>`).join("")}
    </article>`;
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("team.eyebrow")}</p><h1>${t("team.h1")}</h1>
      <p class="lead">${t("team.lead")}</p></header>
    <div class="warn">${t("team.synthetic", esc(v.team.name), v.team.people)}</div>
    ${scenarioControl({ adoption: v.adoption, horizon: v.horizon_year }, v.scenarios)}
    <section class="grid three">
      <div class="card pad-s tile"><span class="small muted">${t("team.t.declining")}</span><div class="big">${v.counts.declining} <small>/ ${v.team.people}</small></div></div>
      <div class="card pad-s tile"><span class="small muted">${t("team.t.hours")}</span><div class="big">${fmt(b.person_hours, 0)}</div><span class="tiny muted">${t("team.t.hours.sub", b.people, fmt(b.longest_weeks, 0))}</span></div>
      <div class="card pad-s tile"><span class="small muted">${t("team.t.cost")}</span><div class="big">RM ${fmt(b.cost_myr, 0)}</div><span class="tiny muted">${t("team.t.cost.sub")}</span></div>
    </section>
    <section class="card stack"><h2>${t("team.roles.h")}</h2><p class="muted small">${t("team.roles.p")}</p>
      <div class="table-wrap"><table><thead><tr><th>${t("team.col.job")}</th><th class="n">${t("team.col.people")}</th><th class="n">${t("team.col.ai")}</th><th>${t("team.col.outlook")}</th><th>${t("ev.h")}</th></tr></thead>
        <tbody>${v.roles.map(roleRow).join("")}</tbody></table></div>
    </section>
    <section class="stack"><div><h2>${t("team.moves.h")}</h2><p class="muted small">${t("team.moves.p")}</p></div>
      ${moving.map(moveCard).join("") || `<p class="small muted">${t("team.moves.none")}</p>`}
      ${v.declining_without_move.length ? `<p class="note">${t("team.nomove", v.declining_without_move.map(esc).join(", "))}</p>` : ""}
    </section>
    ${v.heatmap.skills.length ? `<section class="card stack"><h2>${t("team.heat.h")}</h2><p class="muted small">${t("team.heat.p")}</p>
      <div class="table-wrap"><table class="heatmap"><thead><tr><th>${t("team.col.job")}</th>${v.heatmap.skills.map((s) => `<th class="n">${esc(s.skill_name)}<div class="tiny muted">${t("team.kind." + s.kind)}</div></th>`).join("")}</tr></thead>
        <tbody>${v.heatmap.rows.map((r) => `<tr><td>${esc(r.title)} <span class="muted">× ${r.headcount}</span></td>${r.gaps.map(heatCell).join("")}</tr>`).join("")}</tbody></table></div>
    </section>
    <section class="card stack"><h2>${t("team.groups.h")}</h2><p class="muted small">${t("team.groups.p")}</p>
      ${v.groups.map((g) => `<div class="meter"><span>${esc(g.skill_name)}</span>${bar(100 * g.people / v.team.people)}<span class="v">${t("team.people", g.people)}</span></div>
        <p class="tiny muted">${g.roles.map((r) => `${esc(r.title)} × ${r.headcount}`).join(" · ")}</p>`).join("")}
    </section>` : ""}
    ${v.sdg.length ? `<section class="card stack"><h2>${t("team.sdg.h")}</h2><p class="muted small">${t("team.sdg.p")}</p>
      ${v.sdg.map((s) => `<p class="small">${sdgChip(s.target)} <span class="strong">${t("team.sdg.row", s.people, fmt(s.person_hours, 0))}</span> ${esc(s.rationale)}</p>`).join("")}
    </section>` : ""}
    <p class="src">${t("team.method")} ${esc(b.note)}</p>
    <div class="row"><a class="btn" href="#/pilot">${t("home.pilot.go")}</a><a class="btn" href="#/radar">${t("nav.radar")}</a><a class="btn" href="#/sources">${t("nav.sources")}</a></div>
  </div>`;
};
