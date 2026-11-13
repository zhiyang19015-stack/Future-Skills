"""Career Stress Test: change the assumptions and watch an occupation's tasks, skills and routes move.

It never says a job will disappear. It shows which tasks may change, which skills count more, and
which moves stay open, under assumptions the person sets and that are labelled as assumptions.

Inputs (each one an assumption, never a forecast):
    adoption        how far AI use moves towards everywhere it can be used by 2030 (outlook.py)
    friction        firms' resistance to adopting AI, 0-0.9: the share of that move that does not
                    happen (cost, rules, trust, skills). Effective adoption = adoption x (1 - friction)
    demand_change   % change in the online job ads of the occupation's MASCO major group, run
                    through the real demand pipeline on a copy (scripts/whatif.py)
    hours_per_week  study time, for the training weeks of each route
    max_weeks       how long the person can spend retraining (routes beyond it are marked)

Per O*NET task (an engineering proposal, not a published formula):
    observed        AI share of the task in the Anthropic Economic Index, with its low-high range
    potential       the ILO 2025 task scores of the occupation's ISCO-08 group x 100, spread over its
                    O*NET tasks by rank of observed AI use (task_potentials); SD = the group's SD
    pace            min(1, effective adoption x research tempo)
    pressure        observed + pace x max(0, potential - observed)
                    low uses observed_low and potential - SD; high uses observed_high and potential + SD
  Category:
    unclear         the observed range is POOR_EVIDENCE points wide or more: not enough evidence
    automation      pressure >= AUTOMATE and AI mostly does the task alone (automation share >= 50%)
    augmentation    pressure >= AUGMENT otherwise: AI helps a person do it
    human           below AUGMENT: the task stays with people
  Without an ILO score the scenario cannot move a task's pressure past what is observed; it says so.

The occupation's result is the importance-weighted mix of its tasks, the outlook (outlook.py) under
the same assumptions, the skills that gain or lose weight, a sensitivity check (the outlook's two
shift constants +-30%), whether the two AI sources disagree (scripts/ilo.py), and the 3-5 closest
routes (scripts/transfer.py). "What changed" compares every input with its default, one at a time.
"""

import ilo
import matching
import outlook
import transfer
import whatif

AUTOMATE = 50.0
AUGMENT = 20.0
AUTOMATION_SIDE = 50.0
POOR_EVIDENCE = 60.0
FRICTION_MAX = 0.9
DEMAND_MIN, DEMAND_MAX = -50.0, 100.0
SENSITIVITY = 0.3
ROUTES = 5
CATEGORIES = ("automation", "augmentation", "human", "unclear")
DEFAULTS = {"adoption": outlook.SCENARIOS[outlook.DEFAULT_SCENARIO]["adoption"], "friction": 0.3,
            "demand_change": 0.0, "hours_per_week": 5.0, "max_weeks": None}


class StressError(ValueError):
    pass


def validate(params: dict | None) -> dict:
    p = {**DEFAULTS, **{k: v for k, v in (params or {}).items() if k in DEFAULTS and v is not None}}
    limits = {"adoption": (0.0, outlook.ADOPTION_MAX), "friction": (0.0, FRICTION_MAX),
              "demand_change": (DEMAND_MIN, DEMAND_MAX), "hours_per_week": (1.0, 40.0), "max_weeks": (1.0, 520.0)}
    for k, (lo, hi) in limits.items():
        v = p[k]
        if v is None and k == "max_weeks":
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise StressError(f"'{k}' must be a number from {lo:g} to {hi:g}")
        p[k] = float(v)
    return p


def effective(p: dict) -> float:
    return p["adoption"] * (1 - p["friction"])


def task_potentials(tasks: list[dict], potential: dict | None) -> dict:
    """{task_id: ILO potential 0-100} for the occupation's O*NET tasks.

    The ILO scores the ISCO-08 group's own tasks, not O*NET's, so the two task lists cannot be
    matched one to one. Its scores are spread over the O*NET tasks by rank: the O*NET task with the
    most observed AI use gets the ILO group's highest task score, the least used its lowest (ties
    by importance, the less important first). Quantiles handle lists of different lengths. Without
    the ILO task scores every task gets the occupation's mean."""
    if not potential:
        return {}
    scores = sorted((x["score"] for x in ilo.tables()["tasks"].get(potential["isco"], []) if x["score"] is not None),
                    reverse=True)
    if not scores:
        return {t["task_id"]: 100 * potential["mean"] for t in tasks}
    order = sorted(tasks, key=lambda t: (-(t["ai_share"] if (t["ai_share_high"] - t["ai_share_low"]) < POOR_EVIDENCE
                                           else 0.0), t["importance"] or 0.0, t["task_id"]))
    n, m = len(order), len(scores)
    return {t["task_id"]: 100 * scores[round(i * (m - 1) / (n - 1)) if n > 1 else 0] for i, t in enumerate(order)}


def task_rows(occ: dict, data: dict, pace: float, potential: dict | None) -> list[dict]:
    rows = []
    tasks = data["ai"]["tasks_by_occ"].get(occ["occ_id"], [])
    pots = task_potentials(tasks, potential)
    sd = 100 * potential["sd"] if potential else 0.0
    for t in tasks:
        obs, lo, hi = t["ai_share"], t["ai_share_low"], t["ai_share_high"]
        pot = pots.get(t["task_id"])
        if pot is None:
            mid, low, high = obs, lo, hi
        else:
            mid = obs + pace * max(0.0, pot - obs)
            low = lo + pace * max(0.0, max(0.0, pot - sd) - lo)
            high = hi + pace * max(0.0, min(100.0, pot + sd) - hi)
        unclear = (hi - lo) >= POOR_EVIDENCE
        auto = t["automation_pct"]
        if unclear:
            cat = "unclear"
        elif mid >= AUTOMATE and auto is not None and auto >= AUTOMATION_SIDE:
            cat = "automation"
        elif mid >= AUGMENT:
            cat = "augmentation"
        else:
            cat = "human"
        rows.append({"task_id": t["task_id"], "task": t["task"], "importance": t["importance"] or 0.0,
                     "observed": obs, "observed_low": lo, "observed_high": hi, "automation_pct": auto,
                     "measured": t["usage_pct"] is not None,
                     "potential": round(pot, 1) if pot is not None else None, "pressure": round(mid, 1), "pressure_low": round(low, 1),
                     "pressure_high": round(high, 1), "category": cat})
    return rows


def summary(rows: list[dict]) -> dict:
    weight = sum(r["importance"] for r in rows) or 1.0
    mix = {c: round(100 * sum(r["importance"] for r in rows if r["category"] == c) / weight, 1) for c in CATEGORIES}
    counts = {c: sum(1 for r in rows if r["category"] == c) for c in CATEGORIES}
    mean = lambda k: round(sum(r["importance"] * r[k] for r in rows) / weight, 1) if rows else None  # noqa: E731
    return {"mix": mix, "counts": counts, "pressure": mean("pressure"), "pressure_low": mean("pressure_low"),
            "pressure_high": mean("pressure_high")}


def scenario_data(occ: dict, data: dict, p: dict) -> dict:
    """The data with the person's demand change run through the real pipeline (a copy, this request only)."""
    group = occ.get("masco_major")
    if not p["demand_change"] or not group:
        return data
    return whatif.changed_data(data, whatif.validate({"job_ads": {str(group): p["demand_change"]}}))


def core(occ: dict, data: dict, p: dict, potential: dict | None) -> dict:
    """Tasks, outlook and skills under one set of inputs."""
    d = scenario_data(occ, data, p)
    eff = effective(p)
    o = outlook.role_outlook(occ, d, eff)
    pace = min(1.0, eff * o["tempo"])
    rows = task_rows(occ, d, pace, potential)
    return {"data": d, "effective_adoption": round(eff, 3), "pace": round(pace, 3), "tasks": rows,
            "summary": summary(rows), "outlook": o}


def skills_shift(occ: dict, data: dict, adoption: float, limit: int = 6) -> dict:
    """The occupation's important skills and tools that gain or lose weight under the adoption."""
    weights = outlook.skill_weights(data, adoption)
    items = []
    for eid, imp, _, _ in data["occ_elements"].get(occ["occ_id"], []):
        w = weights.get(eid)
        if w and w["measured"] and imp >= 3.0:
            items.append({"skill_id": eid, "skill_name": data["elements"][eid]["name"], "weight": w["weight"],
                          "status": w["status"], "handoff": w["handoff"]})
    for tid in data["occ_techs"].get(occ["occ_id"], []):
        w = weights.get(tid)
        if w and w["measured"]:
            items.append({"skill_id": tid, "skill_name": data["technologies"][tid]["name"], "weight": w["weight"],
                          "status": w["status"], "handoff": w["handoff"]})
    items.sort(key=lambda x: -x["weight"])
    return {"gaining": [x for x in items if x["status"] == "rising"][:limit],
            "losing": [x for x in items if x["status"] == "declining"][::-1][:limit]}


def sensitivity(occ: dict, data: dict, eff: float) -> dict:
    """The outlook when the two shift constants are SENSITIVITY lower or higher: how much the
    result leans on numbers we chose."""
    s, ref = outlook.role_signals(occ, data), data["ai"]["reference"]
    out = {}
    for name, k in (("low", 1 - SENSITIVITY), ("high", 1 + SENSITIVITY)):
        v = outlook.outlook_value(s["demand"], s["ai_share"], s["builder"], s["tempo"], eff, ref,
                                  outlook.EXPOSURE_SHIFT * k, outlook.BUILDER_SHIFT * k)
        out[name] = round(v["outlook"], 1)
    return {"outlook_low": min(out.values()), "outlook_high": max(out.values()), "spread": SENSITIVITY}


def explain_changes(occ: dict, data: dict, p: dict, base: dict, now: dict, potential: dict | None) -> list[dict]:
    """Each input that differs from its default, applied alone: what it moved."""
    out = []
    for key in ("adoption", "friction", "demand_change"):
        if abs((p[key] or 0) - (DEFAULTS[key] or 0)) < 1e-9:
            continue
        alone = core(occ, data, {**DEFAULTS, key: p[key]}, potential)
        moved = sum(1 for a, b in zip(base["tasks"], alone["tasks"]) if a["category"] != b["category"])
        out.append({"input": key, "from": DEFAULTS[key], "to": p[key],
                    "pressure_change": round(alone["summary"]["pressure"] - base["summary"]["pressure"], 1),
                    "outlook_change": round(alone["outlook"]["outlook"] - base["outlook"]["outlook"], 1),
                    "demand_change": round(alone["outlook"]["demand"] - base["outlook"]["demand"], 1),
                    "tasks_moved": moved})
    moved_all = [{"task": b["task"], "from": a["category"], "to": b["category"]}
                 for a, b in zip(base["tasks"], now["tasks"]) if a["category"] != b["category"]]
    return out, moved_all


def run(occ_id: str, data: dict, params: dict | None = None, profile: dict | None = None,
        sources: dict | None = None) -> dict:
    occ = data["by_id"].get(occ_id)
    if occ is None:
        raise StressError(f"unknown occ_id '{occ_id}'")
    p = validate(params)
    potential = ilo.for_occupation(occ, data)
    now = core(occ, data, p, potential)
    base = core(occ, data, dict(DEFAULTS), potential)
    changes, moved = explain_changes(occ, data, p, base, now, potential)
    scenarios = {}
    for name, s in outlook.SCENARIOS.items():
        r = core(occ, data, {**p, "adoption": s["adoption"]}, potential)
        scenarios[name] = {"adoption": s["adoption"], "effective_adoption": r["effective_adoption"],
                           "mix": r["summary"]["mix"], "pressure": r["summary"]["pressure"],
                           "pressure_low": r["summary"]["pressure_low"], "pressure_high": r["summary"]["pressure_high"],
                           "outlook": r["outlook"]["outlook"], "status": r["outlook"]["status"]}
    person = profile or {"kind": "working", "current_occupation": occ_id,
                         "education_job_zone": occ["job_zone"] or matching.DEFAULT_JOB_ZONE, "technologies": []}
    routes = transfer.map_for(person, now["data"], occ_id, now["effective_adoption"], p["hours_per_week"],
                              sources=sources, limit=ROUTES, max_weeks=p["max_weeks"])
    tasks = sorted(now["tasks"], key=lambda t: (CATEGORIES.index(t["category"]), -t["pressure"], -t["importance"]))
    o = now["outlook"]
    return {"occupation": {"occ_id": occ_id, "title": occ["title"], "field_id": occ["field_id"], "isco": occ["isco"],
                           "isco_basis": occ["isco_basis"], "masco_major": occ["masco_major"]},
            "params": p, "defaults": DEFAULTS, "effective_adoption": now["effective_adoption"], "pace": now["pace"],
            "summary": now["summary"], "baseline": base["summary"], "tasks": tasks,
            "outlook": {k: o[k] for k in ("demand", "outlook", "change", "status", "ai_share", "ai_share_low",
                                          "ai_share_high", "ai_share_reference", "tempo")},
            "baseline_outlook": base["outlook"]["outlook"], "sensitivity": sensitivity(occ, now["data"], now["effective_adoption"]),
            "scenarios": scenarios, "skills": skills_shift(occ, now["data"], now["effective_adoption"]),
            "ilo": potential, "changes": changes, "tasks_moved": moved[:12], "tasks_moved_count": len(moved),
            "routes": routes["routes"], "routes_considered": routes["considered"],
            "evidence_kinds": {"observed": "Anthropic Economic Index (AI use)", "research_estimate": "ILO WP140 (potential)",
                               "scenario_assumption": "adoption, friction, demand change", "user_input": "hours, weeks, your skills"},
            "rules": rules()}


def rules() -> dict:
    return {"automate": AUTOMATE, "augment": AUGMENT, "automation_side": AUTOMATION_SIDE, "poor_evidence": POOR_EVIDENCE,
            "friction_max": FRICTION_MAX, "sensitivity": SENSITIVITY, "defaults": DEFAULTS,
            "formula": "pressure = observed + min(1, adoption x (1 - friction) x tempo) x max(0, ILO potential - observed)",
            "note": "An engineering proposal, not a published formula. Exposure and use are not job loss."}
