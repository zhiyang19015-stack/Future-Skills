/* Step 6, "Futures": the same person under three speeds of AI adoption and across 1,000 drawn
   futures; then one piece of simulated AI news, or any changed number, before and after. */
"use strict";

const NEWS_ROLES = 8;
const NEWS_SKILLS = 8;

function futureColumn(c) {
  return `<section class="card future"><div class="row between"><h2>${t("scn." + c.id)}</h2><span class="chip plain num">${Math.round(c.adoption * 100)}%</span></div>
    <p class="tiny muted">${t("scn." + c.id + ".desc")}</p>
    <div>${c.top.map((m) => `<div class="line"><b>${m.rank}</b><a href="#/occ/${esc(m.occ_id)}" style="color:inherit;text-decoration:none">${esc(m.title)}</a><span class="num strong">${fmt(m.total)}</span>
      <span></span><span class="row" style="gap:6px">${statusChip(m.status)}<span class="tiny muted">${t("fut.outlook", fmt(m.outlook, 0))}</span></span><span></span></div>`).join("")}</div></section>`;
}

const moveCell = (n) => (n > 0 ? `<span class="move up">▲ ${n}</span>` : n < 0 ? `<span class="move down">▼ ${Math.abs(n)}</span>` : `<span class="muted">–</span>`);

function movesTable(f) {
  const rows = f.moves.map((m) => `<tr>
      <td>${occLink(m.occ_id, m.title)}<div class="tiny muted">${t("fut.why", fmt(m.ai_share, 0), fmt(m.ai_share_reference, 0))}${m.builder ? ` · ${t("fut.builder", fmt(m.builder, 0))}` : ""}</div></td>
      ${SCENARIO_IDS.map((id) => `<td class="n">#${m.ranks[id]}</td>`).join("")}
      <td class="n">${moveCell(m.rank_move)}</td><td class="n">${signed(m.total_move)}</td>
      <td class="n">${m.stability ? `${fmt(m.stability.top3, 0)}%` : "–"}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th>${t("fut.col.occ")}</th>${SCENARIO_IDS.map((id) => `<th class="n">${t("scn." + id + ".short")}</th>`).join("")}
    <th class="n">${t("fut.col.move")}</th><th class="n">${t("fut.col.points")}</th><th class="n">${t("fut.col.top3")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function simulationCard(f) {
  const sim = f.simulation;
  if (!sim) return "";
  const best = [...f.moves].filter((m) => m.stability).sort((a, b) => b.stability.top3 - a.stability.top3).slice(0, 6);
  return `<section class="card stack"><h2>${t("fut.sim.h", sim.futures)}</h2>
    <p class="muted small">${t("fut.sim.p", Math.round(sim.adoption.low * 100), Math.round(sim.adoption.mid * 100), Math.round(sim.adoption.high * 100), f.horizon_year)}</p>
    ${best.map((m) => `<div class="meter"><span>${esc(m.title)}</span>${bar(m.stability.top3, "ai")}<span class="v">${fmt(m.stability.top3, 0)}%</span></div>
      <p class="tiny muted">${t("fut.sim.row", fmt(m.stability.top1, 0), fmt(m.stability.score_low), fmt(m.stability.score_high))}</p>`).join("")}
    <p class="src">${t("fut.sim.src", sim.assumptions.demand_sd, Math.round(sim.assumptions.param_spread * 100))}</p></section>`;
}

/* One ranking next to the other, with how far each occupation moved. */
function beforeAfter(w) {
  const was = Object.fromEntries(w.before.map((m) => [m.occ_id, m]));
  const col = (rows, title, isAfter) => `<div><h3>${title}</h3>${rows.slice(0, 8).map((m) => {
    const old = was[m.occ_id];
    const d = isAfter && old ? old.rank - m.rank : 0;
    const pts = isAfter && old ? m.total - old.total : 0;
    return `<div class="future"><div class="line"><b>${m.rank}</b><span>${esc(m.title)}</span><span class="num">${fmt(m.total)}${isAfter ? ` ${old ? moveCell(d) : `<span class="move up">${t("wi.new")}</span>`}${Math.abs(pts) >= 0.05 ? ` <span class="tiny muted">${signed(pts)}</span>` : ""}` : ""}</span></div></div>`;
  }).join("")}</div>`;
  return `<div class="ba">${col(w.before, t("fut.before"), false)}${col(w.after, t("fut.after"), true)}</div>`;
}

function changeLine(c) {
  if (c.kind === "mycol") return t("wi.mycol", esc(c.label), esc(c.before), esc(c.after));
  if (c.kind === "job_ads") return t("wi.ads", esc(c.label), signed(c.after, 0));
  if (c.kind === "arxiv") return t("wi.arxiv", signed(c.after, 0));
  if (c.kind === "handoff") return `${t("wi.handoff", esc(c.label), fmt(c.before, 0), fmt(c.after, 0))}${c.skills && c.skills.length ? ` <span class="muted">(${c.skills.length})</span>` : ""}`;
  return t(c.tasks === 1 ? "wi.share.one" : "wi.share", esc(c.label), fmt(c.before, 0), fmt(c.after, 0), c.tasks);
}

function whatIfResult(w) {
  const top = (list) => (list[0] ? esc(list[0].title) : "–");
  const changedTop = w.before[0] && w.after[0] && w.before[0].occ_id !== w.after[0].occ_id;
  const roles = w.roles.slice(0, NEWS_ROLES).map((r) => `<div class="meter"><span>${occLink(r.occ_id, r.title)}</span>
      <span class="small">${statusChip(r.before.status)} → ${statusChip(r.after.status)}</span><span class="v ${r.move > 0 ? "pass" : r.move < 0 ? "fail" : ""}">${signed(r.move)}</span></div>`).join("");
  const skills = w.skills.slice(0, NEWS_SKILLS).map((s) => `<div class="meter"><span>${esc(s.skill_name)}</span>
      <span class="small">${statusChip(s.before.status)} → ${statusChip(s.after.status)}</span><span class="v">${s.after.handoff === null ? "–" : `${fmt(s.before.handoff, 0)} → ${fmt(s.after.handoff, 0)}%`}</span></div>`).join("");
  const p = w.path;
  const learn = (side) => side.learn_next.map(dotName).join("") || `<span class="small muted">–</span>`;
  let n = 1;
  return `<section class="card stack fade" style="border-color:var(--ai)" id="whatif-result">
    <div class="row between"><h2>${t("wi.h")}</h2><span class="chip warn">${t("wi.copy")}</span></div>
    <p class="headline">${changedTop ? t("wi.top.changed", top(w.before), top(w.after)) : t("wi.top.same", top(w.after))}</p>
    <div class="stack tight"><h3>${n++} · ${t("wi.inputs")}</h3><ul class="small stack tight">${w.changes.map((c) => `<li>${changeLine(c)}</li>`).join("")}</ul></div>
    ${skills ? `<div class="stack tight"><h3>${n++} · ${t("wi.skills", w.skills.length)}</h3>${skills}</div>` : ""}
    <div class="stack tight"><h3>${n++} · ${t("wi.roles", w.roles.length)}</h3>${roles || `<p class="small muted">${t("wi.roles.none")}</p>`}</div>
    <div class="stack tight"><h3>${n++} · ${t("wi.ranking")}</h3>${beforeAfter(w)}</div>
    ${p ? `<div class="stack tight"><h3>${n++} · ${t("wi.path", esc(p.role_name))}</h3>
      <div class="ba"><div><p class="tiny muted">${t("fut.before")}</p><div class="tags">${learn(p.before)}</div></div><div><p class="tiny muted">${t("fut.after")}</p><div class="tags">${learn(p.after)}</div></div></div>
      <p class="small ${p.order_changed ? "" : "muted"}">${t(p.order_changed ? "wi.path.changed" : "wi.path.same")}</p></div>` : ""}
    <p class="src">${t("wi.src", w.trend_data.id)}</p>
  </section>`;
}

/* Change any one number yourself. */
const CUSTOM_KINDS = ["job_ads", "handoff", "ai_share", "mycol", "arxiv"];
function customCard(wi) {
  const c = ui.custom || { kind: "job_ads" };
  let picker = "", field = "", source = "";
  if (c.kind === "mycol") {
    picker = `<label class="field">${t("wi.c.occ")}<input type="search" placeholder="${esc(t("radar.search.ph"))}" value="${esc(c.query || "")}" data-in="customQuery"></label>
      <div class="tags" id="custom-occs">${customOccs(c)}</div>`;
    field = `<label class="field">${t("wi.c.status")}<select data-on="customValue">${["yes", "near", "no"].map((o) => `<option value="${o}"${o === (c.value || "no") ? " selected" : ""}>${o}</option>`).join("")}</select></label>`;
    source = "MyCOL 2024/2025";
  } else {
    const items = wi.inputs.filter((i) => i.kind === c.kind);
    const item = items.find((i) => i.id === c.id) || items[0];
    if (item && items.length > 1) {
      picker = `<label class="field">${t("wi.c.pick")}<select data-on="customId">${items.map((i) => `<option value="${esc(i.id)}"${i.id === item.id ? " selected" : ""}>${esc(i.kind === "job_ads" ? `MASCO ${i.id} · ${i.label}` : i.label)}</option>`).join("")}</select></label>`;
    }
    if (item) {
      const v = c.id === item.id && c.value !== undefined ? c.value : item.value;
      const pct = c.kind === "job_ads" || c.kind === "arxiv";
      field = `<label class="field">${t(pct ? "wi.c.pct" : "wi.c.value", fmt(item.value, 0))}
        <input type="number" min="${item.min}" max="${item.max}" step="1" value="${esc(v)}" data-on="customValue"></label>`;
      source = `${esc(item.source_name)}${item.release_date ? ` · ${dateText(item.release_date)}` : ""}`;
    }
  }
  return `<section class="card"><details class="more"${ui.customOpen ? " open" : ""}><summary>${t("wi.c.h")}</summary>
    <div class="stack">
      <p class="small muted">${t("wi.c.p")}</p>
      <div class="seg" role="group">${CUSTOM_KINDS.map((k) => `<button type="button" data-act="customKind" data-id="${k}" aria-pressed="${c.kind === k}">${t("wi.kind." + k)}</button>`).join("")}</div>
      <div class="grid two">${picker}${field}</div>
      ${source ? `<p class="src">${source}</p>` : ""}
      <div class="row"><button type="button" class="btn small primary" data-act="customRun">${t("wi.c.run")}</button>${ui.customError ? `<span class="small fail">${esc(ui.customError)}</span>` : ""}</div>
    </div></details></section>`;
}
function customOccs(c) {
  const all = ui.occList || [];
  const found = c.query ? occMatches(all, c.query, "", 10) : [];
  return found.map((o) => `<button type="button" class="toggle" data-act="customOcc" data-id="${esc(o.occ_id)}" aria-pressed="${c.id === o.occ_id}">${esc(o.title)} · MyCOL ${esc(o.mycol)}</button>`).join("");
}

PAGES.futures = async () => {
  const [f, wi, occs] = await Promise.all([cached("/api/futures", { ...profileBody(), hours_per_week: state.hours, sdg_goals: state.sdgGoals, show_restricted: Boolean(state.showRestricted), top: 5 }),
    cached("/api/whatif"), cached("/api/occupations")]);
  ui.occList = occs;
  rememberScenarios(f.scenarios);
  const people = state.demo ? await cached("/api/profiles") : [];
  const demo = people.find((p) => p.profile_id === state.demo);
  const tops = f.scenarios.map((c) => c.top[0]).filter(Boolean);
  const verdict = !tops.length ? "" : f.top_changes ? t("fut.verdict.top", esc(tops[0].title), esc(tops[tops.length - 1].title))
    : f.top3_changes ? t("fut.verdict.top3", esc(tops[0].title)) : t("fut.verdict.same", esc(tops[0].title));
  return `<div class="stack loose">
    <header class="stack tight"><p class="eyebrow">${t("step", 6)} · ${t("nav.futures")}</p><h1>${t("fut.h1")}</h1>
      <p class="lead">${t("fut.lead")}${demo ? ` ${t("fut.for", esc(demo.name))}` : ""}</p></header>
    ${!hasProfile() ? `<div class="warn row between"><span>${t("match.empty")}</span><a class="btn small" href="#/you">${t("home.start")}</a></div>` : ""}
    ${verdict ? `<p class="note"><strong>${verdict}</strong> ${t("scn.estimate.long")}</p>` : ""}
    <div class="cols">${f.scenarios.map(futureColumn).join("")}</div>
    <section class="card stack"><h2>${t("fut.moves.h")}</h2><p class="muted small">${t("fut.moves.p")}</p>${movesTable(f)}</section>
    ${simulationCard(f)}

    <section class="stack">
      <div><div class="row"><h2>${t("news.h")}</h2><span class="chip ai">${t("news.simulated")}</span></div><p class="muted small">${t("news.p")}</p></div>
      <div class="grid">${wi.news.map((n) => `<button type="button" class="card news" data-act="news" data-id="${esc(n.id)}" aria-pressed="${ui.news === n.id}">
        ${fieldChip(n.field)}<span class="headline">“${esc(t("news." + n.id + ".title"))}”</span>
        <span class="small muted">${esc(t("news." + n.id + ".sum"))}</span></button>`).join("")}</div>
      ${ui.busy.whatif ? loading(t("wi.running")) : ""}
      ${ui.whatif ? whatIfResult(ui.whatif) : ""}
      ${ui.whatif ? `<div class="row"><button type="button" class="btn small" data-act="newsClear">${t("wi.clear")}</button></div>` : ""}
    </section>
    <section class="stack"><h3>${t("wi.examples")}</h3><div class="tags">${wi.examples.map((e) => `<button type="button" class="toggle" data-act="example" data-id="${esc(e.id)}">${esc(t("ex." + e.id) === "ex." + e.id ? e.name : t("ex." + e.id))}</button>`).join("")}</div></section>
    ${customCard(wi)}
    <div class="row"><a class="btn" href="#/radar">${t("nav.radar")}</a><a class="btn" href="#/sources">${t("nav.sources")}</a></div>
  </div>`;
};

async function runWhatIf(changes) {
  ui.busy.whatif = true; ui.whatif = null; ui.customError = null; redraw();
  try {
    ui.whatif = await request("/api/whatif", matchBody({ trend_changes: changes }));
  } catch (e) {
    ui.customError = e.message;
  }
  ui.busy.whatif = false;
  await route(true);
  const el = $("#whatif-result");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}
Object.assign(ACT, {
  news: async (el) => {
    const wi = await cached("/api/whatif");
    const n = wi.news.find((x) => x.id === el.dataset.id);
    ui.news = n.id;
    runWhatIf(n.changes);
  },
  example: async (el) => {
    const wi = await cached("/api/whatif");
    const e = wi.examples.find((x) => x.id === el.dataset.id);
    ui.news = null;
    runWhatIf(e.changes);
  },
  newsClear: () => { ui.news = null; ui.whatif = null; redraw(); },
  customKind: (el) => { ui.custom = { kind: el.dataset.id }; ui.customOpen = true; redraw(); },
  customOcc: (el) => { ui.custom = { ...(ui.custom || { kind: "mycol" }), id: el.dataset.id }; ui.customOpen = true; redraw(); },
  customRun: async () => {
    const wi = await cached("/api/whatif");
    const c = ui.custom || { kind: "job_ads" };
    ui.news = null; ui.customOpen = true;
    if (c.kind === "mycol") {
      if (!c.id) { ui.customError = t("wi.c.pickocc"); redraw(); return; }
      runWhatIf({ mycol: { [c.id]: c.value || "no" } });
      return;
    }
    const items = wi.inputs.filter((i) => i.kind === c.kind);
    const item = items.find((i) => i.id === c.id) || items[0];
    const value = Number(c.value === undefined || c.id !== item.id ? item.value : c.value);
    if (c.kind === "arxiv") runWhatIf({ arxiv: value });
    else runWhatIf({ [c.kind]: { [item.id]: value } });
  },
});
Object.assign(ON, {
  customId: (el) => { ui.custom = { kind: (ui.custom || { kind: "job_ads" }).kind, id: el.value }; ui.customOpen = true; redraw(); },
  customValue: async (el) => {
    const c = ui.custom || { kind: "job_ads" };
    if (!c.id && c.kind !== "mycol") {  // the first item is shown but not picked yet
      const wi = await cached("/api/whatif");
      c.id = wi.inputs.filter((i) => i.kind === c.kind)[0].id;
    }
    ui.custom = { ...c, value: el.value };
  },
  customQuery: (el) => {
    ui.custom = { ...(ui.custom || { kind: "mycol" }), query: el.value };
    const out = $("#custom-occs");
    if (out) out.innerHTML = customOccs(ui.custom);
  },
});
