"""Career Decision Lab: three realistic options side by side, with their costs and risks in the open.

    A  stay and upskill    the job the person does now (or the occupation they start from), with the
                           gaps and tools it still asks for
    B  adjacent move       the best route from the Skill Transfer Map: O*NET-related or a close skill
                           profile (scripts/transfer.py)
    C  bigger change       the best-matching occupation for the person in another field
                           (scripts/matching.py), seen through the same transfer measures

For each: skill coverage and critical gaps, training hours and weeks at the person's study time,
known course fees (free courses: RM 0) and fees we have no reliable number for, the qualification
step and licence, Malaysian demand evidence (MyCOL, DOSM job ads of its MASCO group, the group's
median wage as context), how it fares under slow, moderate and fast adoption, and a fallback route.

Limits the person sets (hours a week, the most weeks they can spend, a budget in RM) are checked
for each option; changing them recomputes everything. The lab does not pick for the person: it
says which limits an option breaks and lets them compare. Missing data stays missing: a wage we do
not have is "no reliable data", never a low wage, and an unknown fee is never RM 0.

There is no state-level demand in our sources, so a location limit cannot be checked; the page
says so instead of guessing.
"""

import matching
import outlook
import transfer

PATHS = ("stay", "adjacent", "change")
CAAS = ("concern", "control", "curiosity", "confidence")   # Savickas & Porfeli (2012): reflection prompts, never scored


class LabError(ValueError):
    pass


def validate(limits: dict | None) -> dict:
    limits = limits or {}
    out = {"max_weeks": limits.get("max_weeks"), "budget_myr": limits.get("budget_myr")}
    for k, hi in (("max_weeks", 520), ("budget_myr", 1_000_000)):
        v = out[k]
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= hi:
            raise LabError(f"'{k}' must be a number from 0 to {hi}")
        out[k] = float(v)
    return out


def checks(r: dict, limits: dict) -> list[dict]:
    """Which of the person's limits an option breaks, or cannot be checked against."""
    out = []
    weeks, t = r["training"]["weeks"], r["training"]
    if limits["max_weeks"] is not None:
        out.append({"limit": "time", "ok": (weeks or 0) <= limits["max_weeks"], "value": weeks,
                    "limit_value": limits["max_weeks"]})
    if limits["budget_myr"] is not None:
        out.append({"limit": "budget", "ok": t["course_fees_myr"] <= limits["budget_myr"], "value": t["course_fees_myr"],
                    "limit_value": limits["budget_myr"], "unknown_fees": t["fees_unknown"]})
    q = r["qualification"]
    if q["steps_up"]:
        out.append({"limit": "qualification", "ok": False, "value": q["job_zone"], "limit_value": q["your_zone"]})
    if q["licence"]:
        out.append({"limit": "licence", "ok": None, "value": q["licence"]["body"]})
    out.append({"limit": "location", "ok": None, "value": None})
    return out


def robustness(r: dict) -> int:
    return sum(1 for s in r["local"]["statuses"].values() if s != "declining")


def fallback(occ_id: str, profile: dict, data: dict, adoption: float, hours: float, sources: dict,
             exclude: set) -> dict | None:
    """The best route from this option that is not declining: where to go if it does not work out."""
    found = [r for r in transfer.map_for(profile, data, occ_id, adoption, hours, sources, limit=6)["routes"]
             if r["occ_id"] not in exclude]
    # one that is not declining if there is one; otherwise the closest, said to be declining too
    best = next((r for r in found if r["local"]["status"] != "declining"), found[0] if found else None)
    if best is None:
        return None
    return {"occ_id": best["occ_id"], "title": best["title"], "coverage": best["coverage"],
            "status": best["local"]["status"]}


def run(profile: dict, data: dict, adoption: float, hours_per_week: float, limits: dict | None = None,
        sources: dict | None = None, origin: str | None = None) -> dict:
    limits = validate(limits)
    sources = sources or {}
    prepared = matching.prepare(profile, data)
    ranked = [m for m in matching.rank(prepared, data, adoption=adoption)
              if not m["_parts"]["last"] and "current_occupation" not in m["flags"]]
    start = origin or prepared.get("current_occupation") or (ranked[0]["occ_id"] if ranked else None)
    if start not in data["by_id"]:
        raise LabError("pick an occupation to start from ('origin') or set the job you do now")
    weights = outlook.skill_weights(data, adoption)
    start_occ = data["by_id"][start]
    picks = {"stay": (start, "origin")}
    routes = transfer.map_for(prepared, data, start, adoption, hours_per_week, sources, limit=12,
                              max_weeks=limits["max_weeks"])["routes"]
    # the best route that needs no higher qualification and is not far below the person's education
    zone = prepared.get("education_job_zone") or matching.DEFAULT_JOB_ZONE
    adjacent = next((r for r in routes if not r["qualification"]["steps_up"]
                     and (r["job_zone"] or zone) > zone - matching.TOO_LOW), routes[0] if routes else None)
    if adjacent:
        picks["adjacent"] = (adjacent["occ_id"], adjacent["relation"])
    near = {start} | {r["occ_id"] for r in routes}
    change = next((m for m in ranked if m["field_id"] != start_occ["field_id"] and m["occ_id"] not in near), None)
    if change:
        picks["change"] = (change["occ_id"], "best_match_other_field")
    options = []
    used = {occ for occ, _ in picks.values()}
    for path in PATHS:
        if path not in picks:
            continue
        occ_id, relation = picks[path]
        r = transfer.route(prepared, data["by_id"][occ_id], data, adoption, weights, hours_per_week, sources,
                           relation, origin=start if path != "stay" else None)
        match = next((m for m in ranked if m["occ_id"] == occ_id), None)
        r.update(path=path, match_total=match["total"] if match else None, robust_scenarios=robustness(r),
                 checks=checks(r, limits), fallback=fallback(occ_id, prepared, data, adoption, hours_per_week, sources, used))
        r["fits"] = all(c["ok"] is not False for c in r["checks"])
        options.append(r)
    return {"origin": {"occ_id": start, "title": start_occ["title"], "field_id": start_occ["field_id"],
                       "is_current_job": start == prepared.get("current_occupation")},
            "options": options, "limits": limits, "hours_per_week": hours_per_week, "adoption": adoption,
            "caas": list(CAAS), "rules": {**transfer.rules(), "paths": list(PATHS),
                                          "note": "The lab compares; it does not choose. Missing wages and fees stay missing."}}
