"""Skill Transfer Map: from the skills a person already has to the occupations next to them.

Start from skills, not job titles. For an origin (the job the person does now, or one they pick)
the candidates are the occupations O*NET lists as related plus the SIMILAR occupations whose O*NET
skill and knowledge profile is closest (cosine similarity of importance vectors). For each:

    coverage    importance-weighted share of the target's O*NET skills and knowledge the person
                has at the level it needs (min(yours / needed, 1)), 0-100. Not a count of shared
                skill names: a skill the target hardly uses counts little.
    evidence    the share of that coverage backed by a finished mission or the CV, rather than a
                self-rating or the assumption that doing a job means having its skills. Sources
                are not equally reliable (EVIDENCE_WEIGHT, used when two sources give one level).
    critical    gaps on skills the target rates important (importance >= CRITICAL_IMPORTANCE of 5)
                that are at least CRITICAL_GAP levels short
    readiness   100, less CRITICAL_PENALTY per critical gap; halved when the target's Job Zone is
                above the person's education; the licence a regulated profession needs is shown
    outlook     Malaysian demand moved by the scenario (outlook.py): MyCOL, DOSM job ads, AI use
    training    hours and weeks of the free courses on the gaps (matching.learning_path); fees of
                hands-on programmes are "no reliable data", never 0

    transfer score = 0.55 x coverage + 0.25 x outlook + 0.20 x readiness       (TRANSFER_WEIGHTS)

Candidates come from O*NET (US) relations and skills; the Malaysian signals re-rank them. Every
weight is our engineering proposal, listed on the Sources page, not a published formula.
"""

import math

import learning
import matching
import outlook

SIMILAR = 25                  # most similar occupations by skill profile, added to O*NET's related list
CRITICAL_IMPORTANCE = 3.5     # O*NET importance (1-5) from which a gap is critical
CRITICAL_GAP = 1.0            # O*NET level points short before a gap is critical
CRITICAL_PENALTY = 20.0
TRANSFER_WEIGHTS = {"coverage": 0.55, "outlook": 0.25, "readiness": 0.20}
EVIDENCE_WEIGHT = {"project": 1.0, "cv": 0.8, "self": 0.6, "job": 0.5}   # how much each source of a level is trusted
SHOWN = 8                     # skills listed per group on a route
_vectors = {"key": None, "value": None}


def vectors(data: dict) -> dict:
    """Each occupation's importance vector over O*NET skills and knowledge, with its length."""
    key = id(data["occ_elements"])
    if _vectors["key"] == key:
        return _vectors["value"]
    value = {}
    for occ_id, rows in data["occ_elements"].items():
        v = {eid: imp for eid, imp, _, _ in rows}
        value[occ_id] = (v, math.sqrt(sum(x * x for x in v.values())) or 1.0)
    _vectors.update(key=key, value=value)
    return value


def similarity(a: str, b: str, data: dict) -> float:
    vs = vectors(data)
    if a not in vs or b not in vs:
        return 0.0
    (va, na), (vb, nb) = vs[a], vs[b]
    return sum(x * vb.get(k, 0.0) for k, x in va.items()) / (na * nb)


def candidates(origin: str, data: dict, similar: int = SIMILAR) -> dict:
    """{occ_id: relation} for the origin: O*NET related first, then the closest skill profiles."""
    out = {r: "related" for r in data["related"].get(origin, []) if r in data["by_id"]}
    scored = sorted(((similarity(origin, o["occ_id"], data), o["occ_id"]) for o in data["occupations"]
                     if o["occ_id"] != origin), reverse=True)
    for _, occ_id in scored[:similar]:
        out.setdefault(occ_id, "similar_skills")
    out.pop(origin, None)
    return out


def skill_groups(profile: dict, occ: dict, data: dict, sources: dict) -> dict:
    """The target's skills and knowledge as "you have", "to strengthen" and "not yet", with coverage."""
    have = profile.get("skills", {})
    groups = {"have": [], "strengthen": [], "missing": []}
    got = total = backed = 0.0
    critical = []
    for eid, imp, need, kind in sorted(data["occ_elements"].get(occ["occ_id"], []), key=lambda r: -r[1]):
        mine = float(have.get(eid, 0.0))
        cover = min(mine / need, 1.0) if need > 0 else 1.0
        got += imp * cover
        total += imp
        source = sources.get(eid) or ("job" if mine > 0 else None)
        backed += imp * cover if source in ("project", "cv") else 0.0
        item = {"skill_id": eid, "skill_name": data["elements"][eid]["name"], "kind": kind, "importance": imp,
                "needed": need, "yours": round(mine, 1), "gap": round(max(0.0, need - mine), 1), "source": source}
        groups["have" if cover >= 1 else "strengthen" if mine > 0 else "missing"].append(item)
        if imp >= CRITICAL_IMPORTANCE and need - mine >= CRITICAL_GAP:
            critical.append(item)
    return {"coverage": round(100 * got / total, 1) if total else None,
            "evidence": round(100 * backed / got, 1) if got else None,
            "groups": {k: v[:SHOWN] for k, v in groups.items()},
            "counts": {k: len(v) for k, v in groups.items()},
            "critical": critical[:SHOWN], "critical_count": len(critical)}


def training(profile: dict, occ: dict, data: dict, weights: dict, hours_per_week: float) -> dict:
    """Free-course hours on the person's gaps for this target, and the hands-on programmes it needs."""
    detail = matching.skill_score(profile, occ, data, weights, detail=True)
    path = matching.learning_path(detail, data, hours_per_week)
    gap_targets = [f"element:{g['skill_id']}" for g in detail["gaps"] if g["level_needed"] - g["your_level"] >= 1]
    programmes = learning.programmes_for(gap_targets + [f"field:{occ['field_id']}"], data)
    return {"hours": path["total_hours"], "weeks": path["weeks"], "steps": len(path["steps"]),
            "courses": [{"title": s["title"], "provider": s["provider"], "url": s["url"], "hours": s["hours"],
                         "verified_date": s["verified_date"]} for s in path["steps"][:4]],
            "course_fees_myr": round(sum(s["cost_myr"] or 0 for s in path["steps"]), 2),
            "programmes": [{"title": p["title"], "provider": p["provider"], "url": p["url"], "notes": p["notes"]}
                           for p in programmes],
            "fees_unknown": bool(programmes), "gaps_without_course": len(path["gaps_without_course"])}


def local_demand(occ: dict, data: dict, adoption: float) -> dict:
    """The Malaysian evidence behind a route: MyCOL, DOSM ads of its MASCO group, wage of the group."""
    d = data["demand"]["occupations"].get(occ["occ_id"], {})
    ads = next((s for s in d.get("signals", []) if s["signal"] == "job_ads"), None)
    o = outlook.role_outlook(occ, data, adoption)
    return {"demand": o["demand"], "outlook": o["outlook"], "status": o["status"], "mycol": occ["mycol"],
            "masco_major": occ.get("masco_major") or None,
            "ads_group": ads["group_name"] if ads else None, "ads_change_pct": ads["change_pct"] if ads else None,
            "group_wage_myr": (d.get("wage") or {}).get("median"), "wage_note": "median of the whole MASCO major group",
            "statuses": {k: outlook.role_outlook(occ, data, v["adoption"])["status"] for k, v in outlook.SCENARIOS.items()}}


def route(profile: dict, occ: dict, data: dict, adoption: float, weights: dict, hours_per_week: float,
          sources: dict, relation: str = "", origin: str | None = None) -> dict:
    """One target occupation from the person's skills: coverage, gaps, qualification, training, demand."""
    groups = skill_groups(profile, occ, data, sources)
    zone, mine = occ.get("job_zone"), profile.get("education_job_zone")
    steps_up = max(0, (zone or 0) - (mine or 0)) if zone and mine else 0
    licence = matching.licence(occ, data)
    readiness = max(0.0, 100 - CRITICAL_PENALTY * groups["critical_count"]) * (0.5 if steps_up else 1.0)
    train = training(profile, occ, data, weights, hours_per_week)
    local = local_demand(occ, data, adoption)
    parts = {"coverage": groups["coverage"] or 0.0, "outlook": local["outlook"], "readiness": readiness}
    total = sum(TRANSFER_WEIGHTS[k] * v for k, v in parts.items())
    return {"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"], "job_zone": zone,
            "relation": relation, "similarity": round(100 * similarity(origin, occ["occ_id"], data), 1) if origin else None,
            "score": round(total, 1), "parts": {k: round(v, 1) for k, v in parts.items()},
            **groups, "qualification": {"job_zone": zone, "your_zone": mine, "steps_up": steps_up, "licence": licence},
            "training": train, "local": local}


def map_for(profile: dict, data: dict, origin: str, adoption: float, hours_per_week: float = 5.0,
            sources: dict | None = None, limit: int = 10, max_weeks: float | None = None) -> dict:
    """Every candidate route from the origin, best transfer score first, with the network to draw."""
    profile = matching.prepare(profile, data)
    weights = outlook.skill_weights(data, adoption)
    sources = sources or {}
    rows = [route(profile, data["by_id"][occ_id], data, adoption, weights, hours_per_week, sources, rel, origin)
            for occ_id, rel in candidates(origin, data).items()]
    for r in rows:
        r["fits_time"] = max_weeks is None or (r["training"]["weeks"] or 0) <= max_weeks
    # best transfer score first; a route longer than the person's time limit is marked, not hidden or
    # pushed down (sorting on it put weak, unrelated routes first whenever the strong ones need tools)
    rows.sort(key=lambda r: (-r["score"], r["title"]))
    shown = rows[:limit]
    # the network: the origin, the routes, and the important skills they share with it
    origin_skills = {eid for eid, imp, _, _ in data["occ_elements"].get(origin, []) if imp >= CRITICAL_IMPORTANCE}
    edges = []
    for r in shown:
        shared = [eid for eid, imp, _, _ in data["occ_elements"].get(r["occ_id"], [])
                  if imp >= CRITICAL_IMPORTANCE and eid in origin_skills]
        edges.append({"to": r["occ_id"], "shared": len(shared),
                      "skills": [data["elements"][e]["name"] for e in shared[:6]]})
    occ = data["by_id"][origin]
    return {"origin": {"occ_id": origin, "title": occ["title"], "field_id": occ["field_id"],
                       "local": local_demand(occ, data, adoption)},
            "routes": shown, "considered": len(rows), "edges": edges, "adoption": adoption,
            "hours_per_week": hours_per_week, "max_weeks": max_weeks, "rules": rules()}


def rules() -> dict:
    return {"weights": TRANSFER_WEIGHTS, "critical_importance": CRITICAL_IMPORTANCE, "critical_gap": CRITICAL_GAP,
            "critical_penalty": CRITICAL_PENALTY, "similar": SIMILAR, "evidence_weight": EVIDENCE_WEIGHT,
            "note": "Candidates from O*NET related occupations and skill-profile similarity; re-ranked with Malaysian "
                    "demand. Weights are our proposal, not a published formula."}
