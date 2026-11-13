"""The team view for an HR or career-centre officer: one synthetic team through the same engine.

Nothing here is a second model. Every member group is a working person's profile (the job they do
now, at the level O*NET says it needs) run through matching.match_person under the chosen
scenario, exactly as on the Matches page. The view adds up what the individual results say:

    roles      each job on the team: headcount, AI share of its tasks, outlook under every named
               scenario, evidence grade (scripts/evidence.py)
    moves      for a job that is declining under the scenario, the best-matching adjacent occupation
               (one O*NET lists as related, or one in the same field) that is not declining and
               needs no higher qualification, with the free path to it. When no adjacent occupation
               qualifies the view says so and points at the tasks that stay with people, rather
               than sending a developer to an unrelated trade
    heatmap    the skills those moves ask for most (rows: jobs, columns: skills, cell: O*NET level
               points still to build)
    groups     people to train together: everyone whose move needs the same skill
    budget     study hours and course fees of every move, per person and for the team; weeks at
               the team's weekly study time
    sdg        the UN targets the moves serve, with person-hours

The team in data/sample_team.json is fictional. The view supports training plans only; it ranks
no person and is not for hiring, firing or promotion decisions.
"""

import json
from pathlib import Path

import evidence
import matching
import outlook

DATA = Path(__file__).resolve().parents[1] / "data"
HEAT_SKILLS = 8


class TeamError(ValueError):
    """A team the view cannot use; its text goes back to the caller."""


def sample_team() -> dict:
    return json.loads((DATA / "sample_team.json").read_text(encoding="utf-8"))


def validate(team: dict, data: dict) -> dict:
    members = team.get("members") if isinstance(team, dict) else None
    if not isinstance(members, list) or not 1 <= len(members) <= 30:
        raise TeamError("'members' must be a list of 1 to 30 {occ_id, headcount} rows")
    seen = {}
    for row in members:
        occ_id, count = (row.get("occ_id"), row.get("headcount", 1)) if isinstance(row, dict) else (None, None)
        if occ_id not in data["by_id"]:
            raise TeamError(f"unknown occ_id '{occ_id}'")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 500:
            raise TeamError("'headcount' must be a whole number from 1 to 500")
        seen[occ_id] = seen.get(occ_id, 0) + count
    hours = team.get("hours_per_week", matching.DEFAULT_HOURS_PER_WEEK)
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 1 <= hours <= 40:
        raise TeamError("'hours_per_week' must be a number from 1 to 40")
    return {"name": str(team.get("name", "Team"))[:80], "note": str(team.get("note", ""))[:300],
            "synthetic": bool(team.get("synthetic", False)), "hours_per_week": hours,
            "members": [{"occ_id": k, "headcount": v} for k, v in seen.items()]}


def member_profile(occ: dict, hours: float) -> dict:
    """A person doing this job: its field, its Job Zone as their level, its O*NET skills (added by
    matching.with_current_occupation). No name, age, gender or anything else about them."""
    return {"profile_id": f"team:{occ['occ_id']}", "kind": "working", "current_occupation": occ["occ_id"],
            "education_job_zone": occ["job_zone"] or matching.DEFAULT_JOB_ZONE, "technologies": [],
            "fields": {occ["field_id"]: 100.0}, "hours_per_week": hours}


def adjacent(occ: dict, data: dict) -> list[str]:
    """Occupations a person in this job can plausibly move to: O*NET's related list and its own field."""
    same_field = [o["occ_id"] for o in data["occupations"] if o["field_id"] == occ["field_id"]]
    return [x for x in dict.fromkeys(data["related"].get(occ["occ_id"], []) + same_field) if x != occ["occ_id"]]


def move_for(occ: dict, data: dict, adoption: float, hours: float) -> dict | None:
    """The best-matching adjacent occupation that is not declining and asks for no higher qualification."""
    profile = matching.prepare(member_profile(occ, hours), data)
    near = set(adjacent(occ, data))
    fit = matching.field_fit(profile, data)
    open_ids = [m["occ_id"] for m in matching.rank(profile, data, adoption=adoption, fit=fit)
                if m["occ_id"] in near and not m["_parts"]["last"] and m["outlook"]["status"] != "declining"]
    for occ_id in open_ids[:1]:
        m = matching.detailed(profile, data, occ_id, adoption, fit)
        blocked = {"needs_extra_education", "below_education", "current_occupation"} & set(m["flags"])
        if blocked or m["outlook"]["status"] == "declining":
            continue
        gaps = [{"skill_id": g["skill_id"], "skill_name": g["skill_name"], "kind": g["kind"],
                 "gap": round(g["level_needed"] - g["your_level"], 2)}
                for g in m["skill_detail"]["gaps"] if g["level_needed"] - g["your_level"] >= matching.MIN_PATH_GAP]
        path = m["pathway"]
        return {"occ_id": m["occ_id"], "title": m["title"], "field_id": m["field_id"], "total": m["total"],
                "status": m["outlook"]["status"], "gaps": gaps,
                "tools": [t["skill_name"] for t in m["skill_detail"]["tech_missing"][:5]],
                "hours": path["total_hours"], "weeks": path["weeks"],
                "cost_myr": round(sum(s["cost_myr"] or 0 for s in path["steps"]), 2),
                "courses": [{"title": s["title"], "provider": s["provider"], "url": s["url"], "hours": s["hours"],
                             "verified_date": s["verified_date"]} for s in path["steps"][:4]],
                "sdg": [{"target": s["target"], "goal_name": s["goal_name"], "rationale": s["rationale"]}
                        for s in m["sdg"][:2]],
                "evidence": m["evidence"]["grade"]}
    return None


def view(team: dict | None = None, data: dict | None = None, scenario: str | None = None,
         adoption: float | None = None) -> dict:
    data = data or matching.load_data()
    team = validate(team if team is not None else sample_team(), data)
    adoption = outlook.adoption_of(scenario, adoption)
    hours = team["hours_per_week"]
    roles, heat, groups, sdg = [], {}, {}, {}
    for member in sorted(team["members"], key=lambda r: -r["headcount"]):
        occ, count = data["by_id"][member["occ_id"]], member["headcount"]
        now = outlook.role_outlook(occ, data, adoption)
        row = {"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"], "headcount": count,
               "ai_share": now["ai_share"], "ai_share_low": now["ai_share_low"], "ai_share_high": now["ai_share_high"],
               "ai_share_reference": now["ai_share_reference"], "demand": now["demand"], "outlook": now["outlook"],
               "change": now["change"], "status": now["status"],
               "statuses": {k: outlook.role_outlook(occ, data, v["adoption"])["status"]
                            for k, v in outlook.SCENARIOS.items()},
               "evidence": evidence.occupation_grade(occ, data)["grade"], "move": None}
        if now["status"] == "declining":
            row["move"] = move_for(occ, data, adoption, hours)
        if row["move"]:
            for g in row["move"]["gaps"]:
                cell = heat.setdefault(g["skill_id"], {"skill_id": g["skill_id"], "skill_name": g["skill_name"],
                                                       "kind": g["kind"], "people": 0, "weight": 0.0, "by_role": {}})
                cell["people"] += count
                cell["weight"] += count * g["gap"]
                cell["by_role"][occ["occ_id"]] = g["gap"]
                groups.setdefault(g["skill_id"], []).append({"occ_id": occ["occ_id"], "title": occ["title"],
                                                             "headcount": count})
            for s in row["move"]["sdg"]:
                entry = sdg.setdefault(s["target"], {**s, "people": 0, "person_hours": 0.0})
                entry["people"] += count
                entry["person_hours"] = round(entry["person_hours"] + count * row["move"]["hours"], 1)
        roles.append(row)
    columns = sorted(heat.values(), key=lambda c: (-c["weight"], c["skill_name"]))[:HEAT_SKILLS]
    moving = [r for r in roles if r["move"]]
    people = sum(r["headcount"] for r in roles)
    return {
        "team": {k: team[k] for k in ("name", "note", "synthetic", "hours_per_week")} | {"people": people},
        "adoption": adoption, "horizon_year": outlook.HORIZON_YEAR,
        "roles": roles,
        "counts": {s: sum(r["headcount"] for r in roles if r["status"] == s) for s in ("rising", "steady", "declining")},
        "heatmap": {"skills": [{"skill_id": c["skill_id"], "skill_name": c["skill_name"], "kind": c["kind"],
                                "people": c["people"]} for c in columns],
                    "rows": [{"occ_id": r["occ_id"], "title": r["title"], "headcount": r["headcount"],
                              "gaps": [c["by_role"].get(r["occ_id"]) for c in columns]} for r in moving]},
        "groups": [{"skill_id": c["skill_id"], "skill_name": c["skill_name"], "kind": c["kind"],
                    "people": c["people"], "roles": groups[c["skill_id"]]} for c in columns if c["people"]],
        "budget": {"people": sum(r["headcount"] for r in moving),
                   "person_hours": round(sum(r["headcount"] * r["move"]["hours"] for r in moving), 1),
                   "cost_myr": round(sum(r["headcount"] * r["move"]["cost_myr"] for r in moving), 2),
                   "longest_weeks": max((r["move"]["weeks"] or 0 for r in moving), default=0),
                   "note": "Hours are the lengths the course providers state, not time to mastery. Fees are the "
                           "courses' own; staff time is not costed."},
        "sdg": sorted(sdg.values(), key=lambda s: -s["person_hours"]),
        "declining_without_move": [r["title"] for r in roles if r["status"] == "declining" and not r["move"]],
        "method": "Each job is run as a working person's profile through the same matching as the Matches page. "
                  "Estimates under one scenario, not predictions; for training plans, never for decisions about a person.",
    }
