"""Recommendation Confidence Challenge: "why this one and not that one?", answered with the numbers.

For two occupations and one person it shows:

    parts        each part of the match score (field fit, interest, skills, outlook) for both, and
                 how many points of the gap between them each part explains
    flip         what would have to change for the order to swap, one assumption at a time:
                 the adoption speed (searched over 0-90%), the other's skill fit, its Malaysian
                 demand. "Never in range" when no value would do it
    evidence     for each: evidence grade, how it reaches MASCO, data dates, the data that is
                 missing, and whether the two AI sources disagree (scripts/ilo.py)
    kinds        every number labelled as one of four kinds, never merged into one "probability
                 of being replaced": observed AI use, research-estimated AI exposure, scenario
                 assumption, your own input
"""

import evidence
import ilo
import matching
import outlook

KINDS = {"field": "user_input", "interest": "user_input", "skill": "user_input", "outlook": "scenario_assumption",
         "ai_share": "observed", "ilo_exposure": "research_estimate", "demand": "observed", "adoption": "scenario_assumption"}


class ChallengeError(ValueError):
    pass


def card(profile: dict, data: dict, occ_id: str, adoption: float, fit: dict) -> dict:
    m = matching.detailed(profile, data, occ_id, adoption, fit)
    occ = data["by_id"][occ_id]
    o = m["outlook"]
    potential = ilo.for_occupation(occ, data)
    missing = []
    if o.get("thin"):
        missing.append("ai_thin")
    if not o["has_demand"]:
        missing.append("demand")
    if not potential:
        missing.append("ilo")
    if not (m.get("demand_detail") or {}).get("wage"):
        missing.append("wage")
    if m["components"]["interest"]["score"] is None:
        missing.append("interest")
    if m["components"]["skill"]["score"] is None:
        missing.append("skills")
    return {"occ_id": occ_id, "title": m["title"], "field_id": m["field_id"], "total": m["total"],
            "components": m["components"], "outlook": {k: o[k] for k in ("demand", "outlook", "change", "status",
                                                                          "ai_share", "ai_share_low", "ai_share_high")},
            "flags": m["flags"], "evidence": m["evidence"], "mapping": occ["isco_basis"] or "none",
            "ilo": {k: potential[k] for k in ("mean", "sd", "gradient", "disagree", "direction", "percentile_gap")}
            if potential else None,
            "missing": missing, "gaps": [{"skill_name": g["skill_name"], "gap": round(g["level_needed"] - g["your_level"], 1)}
                                         for g in m["skill_detail"]["gaps"][:3]]}


def total_at(profile: dict, data: dict, occ: dict, adoption: float, fits: dict) -> float:
    return matching.score(profile, occ, data, adoption, outlook.skill_weights(data, adoption), fits)["total"]


def run(profile: dict, data: dict, adoption: float, chosen: str, other: str) -> dict:
    for x in (chosen, other):
        if x not in data["by_id"]:
            raise ChallengeError(f"unknown occ_id '{x}'")
    if chosen == other:
        raise ChallengeError("pick two different occupations")
    profile = matching.prepare(profile, data)
    fit = matching.field_fit(profile, data)
    fits = {f["id"]: f for f in fit["fields"] if f["fit"] is not None}
    a, b = card(profile, data, chosen, adoption, fit), card(profile, data, other, adoption, fit)
    gap = round(a["total"] - b["total"], 1)
    parts = []
    for k in matching.WEIGHTS:
        pa, pb = a["components"][k]["points"], b["components"][k]["points"]
        parts.append({"part": k, "kind": KINDS[k], "chosen": a["components"][k]["score"], "other": b["components"][k]["score"],
                      "points": None if pa is None or pb is None else round(pa - pb, 1)})
    parts.sort(key=lambda p: -abs(p["points"] or 0))
    # what would swap the order, one assumption at a time
    flip = {"adoption": None, "skill_points": None, "demand_points": None}
    sign = 1 if gap >= 0 else -1
    for x in outlook.GRID:
        d = total_at(profile, data, data["by_id"][chosen], x, fits) - total_at(profile, data, data["by_id"][other], x, fits)
        if d * sign < 0:
            flip["adoption"] = x
            break
    w = matching.WEIGHTS
    share = lambda k: w[k] / sum(w[p] for p in w if b["components"][p]["score"] is not None)  # noqa: E731
    if b["components"]["skill"]["score"] is not None and gap > 0:
        need = gap / share("skill")
        flip["skill_points"] = round(need, 1) if b["components"]["skill"]["score"] + need <= 100 else "out_of_range"
    if gap > 0:
        need = gap / share("outlook")
        flip["demand_points"] = round(need, 1) if b["outlook"]["outlook"] + need <= 100 else "out_of_range"
    src = data["ai"]["source"]["economic_index"]
    return {"chosen": a, "other": b, "gap": gap, "parts": parts, "flip": flip, "adoption": adoption,
            "dates": {"ai_release": src["release_date"], "ai_period": data["ai"]["context"]["latest"],
                      "demand_computed": data["demand"]["computed_date"],
                      "ilo_release": (ilo.tables()["source"] or {}).get("source_date")},
            "kinds": KINDS, "grade_rules": evidence.rules(),
            "note": "Every number keeps its kind: observed AI use, research-estimated exposure, scenario assumption "
                    "or your input. They are never merged into one probability of being replaced."}
