/* Quick start (#/quick): the whole journey on one page for a first-time visitor. Three answers
   (who you are, your job or the fields you like, your education), then on the same page your top
   occupations with the reasons, a free plan for the first one, its UN targets, and the top three
   under slow and fast AI adoption. It reuses the "You" controls (you.js) and the same API calls
   as the full steps, so nothing here can disagree with them; every block links to its full step. */
"use strict";

const QUICK_TOP = 5;
const QUICK_STEPS = 3;  // free resources shown from the plan; the Pathway step has the rest

PAGES.quick = async () => {
  const occs = await cached("/api/occupations");
  const ready = !state.demo && (Object.keys(state.fields).length > 0 || (state.kind !== "student" && state.currentOcc));
  const answers = `<section class="card stack">
      <h2>${t("quick.q.zone")}</h2>
      <select data-on="zone" aria-label="${esc(t("quick.q.zone"))}">${ZONES.map((z) => `<option value="${z}"${state.zone === z ? " selected" : ""}>${t("zone." + z)}</option>`).join("")}</select>
    </section>`;
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("quick.eyebrow")}</p><h1>${t("quick.h1")}</h1><p class="lead">${t("quick.lead")}</p></header>
    ${state.demo ? `<div class="note row between"><span>${t("quick.demo")}</span><button type="button" class="btn small" data-act="own">${t("you.demo.own")}</button></div>` : ""}
    ${whoCard(occs)}
    ${state.kind === "student" || !state.currentOcc ? fieldsCard() : ""}
    ${answers}
    ${ready ? await quickResults() : `<p class="note">${t("quick.wait")}</p>`}
  </div>`;
};

async function quickResults() {
  const m = await getMatches();
  const moves = m.results.filter(isMove);
  if (!moves.length) return `<p class="note">${t("quick.none")}</p>`;
  const first = moves[0];
  const [L, F] = await Promise.all([cached("/api/learn", matchBody({ occ_id: first.occ_id })),
    cached("/api/futures", matchBody({}))]);
  const gaps = (x) => (x.skill_detail && x.skill_detail.gaps || []).slice(0, 2).map((g) => esc(g.skill_name)).join(", ");
  const parts = (x) => ["field", "interest", "skill", "outlook"].filter((k) => x.components && x.components[k] && x.components[k].score !== null)
    .map((k) => `${t("part." + k)} ${fmt(x.components[k].score, 0)}`).join(" · ");
  const list = moves.slice(0, QUICK_TOP).map((x, i) => `<div class="stack tight" style="padding:10px 0;border-top:1px solid var(--line)">
      <div class="row between"><span class="strong">${i + 1}. ${occLink(x.occ_id, x.title)}</span><span class="row" style="gap:6px">${statusChip(x.outlook.status)}<b class="num">${fmt(x.total, 0)}</b></span></div>
      <span class="small muted">${parts(x)}</span>
      ${gaps(x) ? `<span class="small">${t("quick.gaps", gaps(x))}</span>` : ""}</div>`).join("");
  const gapFirst = [...new Map([...L.skills.flatMap((x) => x.resources), ...L.stages.flatMap((x) => x.resources)].map((r) => [r.url, r])).values()];
  const plan = gapFirst.slice(0, QUICK_STEPS).map((r) => resourceRow(r, first.occ_id)).join("");
  const sdg = (L.sdg || []).slice(0, 4).map((x) => sdgChip(x.target)).join("");
  const top3 = (id) => {
    const s = (F.scenarios || []).find((x) => x.id === id);
    return s ? `<div class="card pad-s stack tight"><span class="strong">${t("scn." + id)}</span><ol class="small">${s.top.slice(0, 3).map((x) => `<li>${esc(x.title)}</li>`).join("")}</ol></div>` : "";
  };
  return `<section class="card stack"><div class="row between"><h2>${t("quick.r.matches")}</h2><a class="small" href="#/matches">${t("quick.more")} →</a></div>
      <p class="small muted">${t("quick.r.matches.p")}</p>${list}</section>
    <section class="card stack"><div class="row between"><h2>${t("quick.r.plan", esc(first.title))}</h2><a class="small" href="#/pathway/${esc(first.occ_id)}">${t("quick.more")} →</a></div>
      <p class="small muted">${t("quick.r.plan.p", fmt(L.total_hours, 0), fmt(L.weeks, 0), L.hours_per_week)}</p>${plan || `<p class="small muted">${t("path.nocourse")}</p>`}
      ${(L.claimable || []).length ? `<p class="small">${t("quick.r.hrd", L.claimable.length)}</p>` : ""}</section>
    <section class="card stack"><div class="row between"><h2>${t("quick.r.sdg")}</h2><a class="small" href="#/sdg">${t("quick.more")} →</a></div>
      <div class="tags">${sdg}</div></section>
    <section class="card stack"><div class="row between"><h2>${t("quick.r.futures")}</h2><a class="small" href="#/futures">${t("quick.more")} →</a></div>
      <p class="small muted">${t("scn.estimate.long")}</p><div class="grid">${top3("slow")}${top3("fast")}</div></section>`;
}
