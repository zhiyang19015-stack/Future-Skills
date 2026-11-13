"""Rank every occupation for one person under a future scenario, and explain every score.

Two steps, so the person first sees which fields of work fit them, then the occupations:

1. Field fit, for each of the 22 fields (SOC major groups, data/fields.csv):

    field_fit = 0.50 x choice + 0.25 x interest + 0.25 x experience       (each part 0-100)

   - choice: the fields the person marked on their profile, 100 "interested", 0 "not for me".
   - interest: the mean interest fit (below) of the field's occupations, from the questionnaire.
   - experience: the field of the job the person does now (CURRENT_FIELD), and the job titles
     the CV names (scripts/cv_reader.py).
   A part the person gave no answer for is left out and the other weights are scaled up.

2. Occupation score, for every occupation in data/occupations.csv:

    total = 0.20 x field fit + 0.15 x interest + 0.30 x skill + 0.35 x outlook   (+ SDG points)

   - interest: Pearson correlation of the person's six RIASEC totals with the occupation's
     O*NET interest scores, mapped from -1..1 to 0..100.
   - skill: up to three parts, each only when the person answered for it:
         skills, knowledge = sum(importance x weight x coverage) / sum(importance x weight)
         coverage = min(person's level / O*NET level, 1), over the occupation's O*NET skills or
         knowledge areas; an element the person did not rate counts as level 0
         technologies = sum(weight of its Hot technologies the person uses) / sum(weight)
         skill = 0.5 x skills + 0.25 x knowledge + 0.25 x technologies
     weight is 1 today and moves with the scenario (outlook.skill_weights): a skill AI takes
     over more than typical counts for less, one people keep doing counts for more.
   - outlook: Malaysian demand moved by the scenario's AI adoption (outlook.py).
   - UN goals the person picks (sdg_goals) add SDG_BONUS points to an occupation that serves one,
     capped at 100; each occupation keeps its total without them, so the cost of the choice shows.

   Education: an occupation whose Job Zone is above the person's level is flagged
   needs_extra_education, one at least TOO_LOW zones below it below_education. Both are ranked
   after the others, never hidden.

Every weight here is our design choice, not data (SOURCES.md, "Choices and limits").

Profile (data/sample_profiles.json holds fictional people only; every part is optional):
    {"kind": "student" | "working" | "switcher", "education_job_zone": 4,
     "current_occupation": "43-3031.00",         # the job a working person does now
     "fields": {"29": 100, "15": 0},             # field choices
     "interest": {...},                          # scripts/interest.py score()
     "skills": {"2.A.1.a": 4.0, ...},            # O*NET level 0-7 per skill or knowledge area
     "technologies": ["microsoft-excel", ...],   # tech_ids from data/technologies.csv
     "cv_fields": {"13": 80}, "cv_why": {"13": "..."},
     "hours_per_week": 5, "sdg_goals": ["3"]}

Usage:
    python scripts/matching.py                         # first sample profile, top 8
    python scripts/matching.py --profile P02 --top 10 --scenario fast
"""

import argparse
import csv
import io
import json
import statistics
import sys
from pathlib import Path

import ai_exposure
import demand
import evidence
import outlook

DATA = Path(__file__).resolve().parents[1] / "data"

FIELD_WEIGHTS = {"choice": 0.50, "interest": 0.25, "experience": 0.25}
FIELD_SOURCE_LABEL = {"choice": "your field choices", "interest": "interests", "experience": "CV and work"}
WEIGHTS = {"field": 0.20, "interest": 0.15, "skill": 0.30, "outlook": 0.35}
SKILL_SPLIT = {"skill": 0.5, "knowledge": 0.25, "technology": 0.25}
SDG_BONUS = {"direct": 10.0, "indirect": 6.0}
DEFAULT_JOB_ZONE = 4         # a bachelor's degree, the usual level of a graduating student
TOO_LOW = 2                  # Job Zones below the person's level before "below_education"
CURRENT_FIELD = 80.0         # experience evidence for the field of the job a person does now
CLEAR_LEAD = 10.0            # field-fit points the best field needs over the next to be called clear
STABILITY_POOL = 30          # occupations taken into the drawn futures (the top of the ranking)
DEFAULT_HOURS_PER_WEEK = 5        # study hours a week when the person gives none
MIN_PATH_GAP = 0.5           # gaps smaller than this (O*NET level points) get no learning step
MAX_PATH_STEPS = 14
DETAIL_ITEMS = 12            # gaps, strengths and tools listed on an occupation's card
ROUTE_REACH = 15.0           # match points below this occupation's at which a related one still counts as a route
ROUTES_SHOWN = 3
RIASEC = ("R", "I", "A", "S", "E", "C")
STEADY = {"weight": 1.0, "status": "steady", "handoff": None, "builder": False, "measured": False}
SCENARIOS = outlook.SCENARIOS
DEFAULT_SCENARIO = outlook.DEFAULT_SCENARIO
# Office tools nearly every job lists; in "learn next" they follow the tools of the job itself
GENERAL_TOOLS = {"Office suite software", "Spreadsheet software", "Presentation software", "Word processing software",
                 "Electronic mail software", "Document management software", "Project management software",
                 "Calendar and scheduling software", "Internet browser software", "Operating system software"}


def read_csv(file_name: str) -> list[dict]:
    """The rows of a CSV in data/ as dicts; a byte-order mark at the start is skipped."""
    text = (DATA / file_name).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --- the data --------------------------------------------------------------------------------------

_TABLES = ("fields.csv", "occupations.csv", "elements.csv", "occupation_elements.csv", "technologies.csv",
           "occupation_technologies.csv", "occupation_titles.csv", "related_occupations.csv",
           "learning_resources.csv", "sdg_map.csv", "regulated.csv", "my_restrictions.csv")
# Flags that keep an occupation out of the listed ranking (it is scored, but placed after the rest).
UNLISTED_FLAGS = {"needs_extra_education", "below_education", "restricted_my"}
_cache = {"key": None, "value": None}


def search_title(occ_id: str, title: str, reported: list[dict]) -> str:
    """Words to search Malaysian job sites with: the shortest common reported title, else the
    O*NET title without its plural, "and" lists and "Except ..." parts."""
    common = [r["title"].split(" (")[0].strip() for r in reported if r["common"] == "Y"]
    if common:
        return min(common, key=len)
    words = title.split(",")[0].split(" and ")[0].split(" Except")[0].strip()
    return words[:-1] if words.endswith("s") and not words.endswith("ss") else words


def static_tables() -> dict:
    """Every table that only changes when the files do, keyed for fast lookup."""
    key = tuple((DATA / f).stat().st_mtime_ns for f in _TABLES)
    if _cache["key"] == key:
        return _cache["value"]
    fields = {r["field_id"]: r for r in read_csv("fields.csv")}
    titles = {}
    for r in read_csv("occupation_titles.csv"):
        titles.setdefault(r["occ_id"], []).append(r)
    occupations = []
    for r in read_csv("occupations.csv"):
        scores = {k: number(r[f"score_{k}"]) for k in RIASEC}
        occupations.append({**r, "job_zone": int(r["job_zone"]) if r["job_zone"] else None,
                            "interest_scores": scores if all(v is not None for v in scores.values()) else None,
                            "field_name": fields[r["field_id"]]["name_en"],
                            "search_title": search_title(r["occ_id"], r["title"], titles.get(r["occ_id"], []))})
    elements = {r["element_id"]: r for r in read_csv("elements.csv")}
    occ_elements = {}
    for r in read_csv("occupation_elements.csv"):
        occ_elements.setdefault(r["occ_id"], []).append(
            (r["element_id"], float(r["importance"]), float(r["level"]), elements[r["element_id"]]["kind"]))
    technologies = {r["tech_id"]: r for r in read_csv("technologies.csv")}
    occ_techs, in_demand = {}, {}
    for r in read_csv("occupation_technologies.csv"):
        if r["hot"] == "Y" or r["in_demand"] == "Y":
            occ_techs.setdefault(r["occ_id"], []).append(r["tech_id"])
            if r["in_demand"] == "Y":  # O*NET's own mark: employers ask for it in this occupation's job ads
                in_demand.setdefault(r["occ_id"], set()).add(r["tech_id"])
    related = {}
    for r in read_csv("related_occupations.csv"):
        related.setdefault(r["occ_id"], []).append(r["related_id"])
    resources = read_csv("learning_resources.csv")
    by_target = {}
    for r in resources:
        for target in filter(None, r["targets"].split(";")):
            by_target.setdefault(target.strip(), []).append(r)
    sdg_rules = {}
    for r in read_csv("sdg_map.csv"):
        sdg_rules.setdefault((r["entity_type"], r["entity_id"]), []).append(r)
    regulated = read_csv("regulated.csv")
    restricted = {o.strip(): r for r in read_csv("my_restrictions.csv") for o in r["occ_ids"].split(";") if o.strip()}
    value = {"restricted": restricted,"fields": fields, "occupations": occupations, "by_id": {o["occ_id"]: o for o in occupations},
             "elements": elements, "occ_elements": occ_elements, "technologies": technologies,
             "occ_techs": occ_techs, "in_demand": in_demand, "titles": titles, "related": related,
             "resources": resources, "by_target": by_target, "sdg_rules": sdg_rules, "regulated": regulated}
    _cache.update(key=key, value=value)
    return value


def load_data() -> dict:
    """The tables plus the two measured layers: AI use (ai_exposure) and Malaysian demand."""
    return {**static_tables(), "ai": ai_exposure.current(), "demand": demand.current()}


# --- SDG targets, licences --------------------------------------------------------------------------

SPECIFICITY = ("occupation", "broad", "minor", "field")


def occupation_sdg(occ: dict, data: dict) -> list[dict]:
    """The SDG targets an occupation serves: its own rules first, then its group's, one per target."""
    keys = {"occupation": occ["occ_id"], "broad": occ["occ_id"][:7], "minor": occ["occ_id"][:4],
            "field": occ["field_id"]}
    seen = {}
    for kind in SPECIFICITY:
        for r in data["sdg_rules"].get((kind, keys[kind]), []):
            if r["sdg_target"] not in seen:
                seen[r["sdg_target"]] = {"target": r["sdg_target"], "goal_name": r["sdg_goal_name"],
                                         "link_strength": r["link_strength"], "rationale": r["rationale"],
                                         "level": kind}
    return sorted(seen.values(), key=lambda s: (s["link_strength"] != "direct", SPECIFICITY.index(s["level"])))


def element_sdg(eid: str, data: dict) -> list[dict]:
    return [{"target": r["sdg_target"], "goal_name": r["sdg_goal_name"], "link_strength": r["link_strength"],
             "rationale": r["rationale"]} for r in data["sdg_rules"].get(("element", eid), [])]


def licence(occ: dict, data: dict) -> dict | None:
    """The Malaysian body an occupation must register with, when it is a regulated profession."""
    for r in data["regulated"]:
        if any(occ["occ_id"].startswith(p.strip()) for p in r["onet_prefixes"].split(";") if p.strip()):
            return {k: r[k] for k in ("profession", "body", "requirement", "url", "verified_date")}
    return None


def restriction(occ: dict, data: dict) -> dict | None:
    """A Malaysian legal limit on an occupation (data/my_restrictions.csv), when there is one."""
    r = data.get("restricted", {}).get(occ["occ_id"])
    return {k: r[k] for k in ("restriction_id", "topic", "note", "source_name", "source_url", "source_date")} if r else None


def sdg_goal(target: str) -> str:
    return str(target).split(".")[0]


def sdg_choice(goals, targets: list[dict], total: float) -> dict:
    """The points for an occupation that serves one of the person's picked goals (strongest link)."""
    picked = {str(g) for g in goals or []}
    hits = [s for s in targets if sdg_goal(s["target"]) in picked]
    bonus = max((SDG_BONUS.get(s["link_strength"], 0.0) for s in hits), default=0.0)
    return {"goals": sorted({sdg_goal(s["target"]) for s in hits}, key=int), "bonus": bonus,
            "targets": [{"target": s["target"], "link_strength": s["link_strength"], "rationale": s["rationale"]}
                        for s in hits],
            "total_without": round(total, 1), "total": round(min(100.0, total + bonus), 1)}


def sdg_goal_options(data: dict) -> list[dict]:
    """The UN goals at least one occupation serves, with how many: what a person can pick from."""
    goals = {}
    for occ in data["occupations"]:
        for s in occupation_sdg(occ, data):
            g = goals.setdefault(sdg_goal(s["target"]), {"goal": sdg_goal(s["target"]), "goal_name": s["goal_name"],
                                                         "occupations": 0})
            g["occupations"] += 1
    return sorted(goals.values(), key=lambda g: int(g["goal"]))


# --- the parts of a score ---------------------------------------------------------------------------

def weighted(scores: dict, weights: dict) -> tuple[float | None, dict]:
    """The weighted mean of the scores that have a value (a missing score's weight is shared out over
    the others), and the points each score adds to it."""
    known = {k: v for k, v in scores.items() if v is not None}
    scale = sum(weights[k] for k in known)
    if not scale:
        return None, dict.fromkeys(scores)
    adds = {k: round(weights[k] * known[k] / scale, 1) if k in known else None for k in scores}
    return round(sum(weights[k] * v for k, v in known.items()) / scale, 1), adds


def combine(field, interest, skill, outlook_score) -> float:
    """The total before SDG points, unrounded: what outlook.simulate scores a future with."""
    parts = (("field", field), ("interest", interest), ("skill", skill), ("outlook", outlook_score))
    total = sum(WEIGHTS[k] for k, v in parts if v is not None)
    return sum(WEIGHTS[k] * v for k, v in parts if v is not None) / total if total else 0.0


def interest_fit(riasec: dict | None, occ: dict) -> tuple[float | None, str]:
    """How alike the person's six interest totals and the occupation's O*NET profile are: their
    correlation, from -1 (opposite) to 1 (the same pattern), as 0-100."""
    if not riasec:
        return None, "No interest answers"
    profile = occ.get("interest_scores")
    if not profile:
        return None, "No O*NET interest scores for this occupation"
    mine = [float(riasec[k]) for k in RIASEC]
    theirs = [float(profile[k]) for k in RIASEC]
    if min(mine) == max(mine) or min(theirs) == max(theirs):
        return None, "One of the two interest profiles is flat, so there is no pattern to compare"
    r = statistics.correlation(mine, theirs)
    code = "".join(sorted(RIASEC, key=lambda k: (-riasec[k], RIASEC.index(k)))[:3])
    common = "".join(k for k in code if k in occ["riasec"])
    note = f"Your interest code {code} vs its O*NET code {occ['riasec']}; " + \
        (f"shared: {common}" if common else "no shared letters")
    return round(50 * (r + 1), 1), note


def usable_interest(profile: dict) -> dict | None:
    i = profile.get("interest")
    return i["riasec"] if i and i.get("usable") else None


def answered_kinds(profile: dict, data: dict) -> set:
    """Which skill parts the person gave answers for: skill, knowledge, technology."""
    kinds = {data["elements"][e]["kind"] for e in profile.get("skills", {}) if e in data["elements"]}
    if profile.get("technologies"):
        kinds.add("technology")
    return kinds


def skill_score(profile: dict, occ: dict, data: dict, weights: dict | None, detail: bool = False) -> dict:
    """Skill fit for one occupation; with detail, every gap and strength tagged by where it is heading."""
    have = profile.get("skills", {})
    techs = set(profile.get("technologies") or [])
    kinds = profile.get("_kinds") or answered_kinds(profile, data)
    w_of = lambda sid: (weights or {}).get(sid, STEADY)  # noqa: E731
    got = {"skill": 0.0, "knowledge": 0.0, "technology": 0.0}
    total = {"skill": 0.0, "knowledge": 0.0, "technology": 0.0}
    gaps, strengths, used, missing = [], [], [], []
    for eid, imp, need, kind in data["occ_elements"].get(occ["occ_id"], []):
        w = w_of(eid)["weight"]
        mine = float(have.get(eid, 0.0))
        cover = min(mine / need, 1.0) if need > 0 else 1.0
        got[kind] += imp * w * cover
        total[kind] += imp * w
        if detail:
            item = {"skill_id": eid, "skill_name": data["elements"][eid]["name"], "kind": kind, "importance": imp,
                    "level_needed": need, "your_level": mine, "rated": eid in have,
                    "ai": {k: w_of(eid)[k] for k in ("status", "handoff", "weight", "builder", "measured")}}
            if cover < 1:
                gaps.append({**item, "gap_points": round(imp * w * (1 - cover), 2)})
            else:
                strengths.append(item)
    for tid in data["occ_techs"].get(occ["occ_id"], []):
        w = w_of(tid)["weight"]
        total["technology"] += w
        got["technology"] += w if tid in techs else 0.0
        if detail:
            t = data["technologies"].get(tid, {"name": tid, "category": ""})
            entry = {"skill_id": tid, "skill_name": t["name"], "kind": "technology", "category": t["category"],
                     "ai": {k: w_of(tid)[k] for k in ("status", "handoff", "weight", "builder", "measured")}}
            (used if tid in techs else missing).append(entry)
    parts = {k: (100 * got[k] / total[k] if total[k] and k in kinds else None) for k in SKILL_SPLIT}
    score, _ = weighted(parts, SKILL_SPLIT)
    out = {"score": score, "parts": {k: None if v is None else round(v, 1) for k, v in parts.items()}}
    if detail:
        gaps.sort(key=lambda g: (not g["rated"], -g["gap_points"]))
        strengths.sort(key=lambda s: -s["importance"] * s["ai"]["weight"])
        # learn first the tools employers ask for in this occupation, then those that count most under
        # the scenario; office tools nearly every job lists come last
        asked = data["in_demand"].get(occ["occ_id"], set())
        missing.sort(key=lambda t: (t["category"] in GENERAL_TOOLS, t["skill_id"] not in asked, -t["ai"]["weight"],
                                    t["skill_name"]))
        out.update(gaps=gaps, strengths=strengths, tech_used=used, tech_missing=missing)
    return out


# --- field fit --------------------------------------------------------------------------------------

def experience(profile: dict, data: dict) -> tuple[dict, dict]:
    """Experience evidence per field: the job titles the CV names and the job the person does now;
    the stronger one counts, they are never added up. Tools are not used here: most tools are
    listed in many fields (a spreadsheet says little about where someone works), and they already
    count in each occupation's skill fit."""
    scores, why = dict(profile.get("cv_fields") or {}), dict(profile.get("cv_why") or {})
    current = data["by_id"].get(profile.get("current_occupation") or "")
    if current and scores.get(current["field_id"], -1) < CURRENT_FIELD:
        scores[current["field_id"]] = CURRENT_FIELD
        why[current["field_id"]] = f"you work as {current['title']}"
    return scores, why


def top_key(scores: dict | None) -> str | None:
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return None if len(ranked) > 1 and ranked[0][1] == ranked[1][1] else ranked[0][0]


def field_fit(profile: dict, data: dict) -> dict:
    """Score every field from the person's choices, interests and experience, with insights."""
    riasec = usable_interest(profile)
    interest = {}
    if riasec:
        per = {}
        for occ in data["occupations"]:
            v, _ = interest_of(profile, occ)
            if v is not None:
                per.setdefault(occ["field_id"], []).append(v)
        interest = {f: round(sum(v) / len(v), 1) for f, v in per.items()}
    exp, exp_why = experience(profile, data)
    sources = {"choice": {f: float(v) for f, v in (profile.get("fields") or {}).items()} or None,
               "interest": interest or None, "experience": exp or None}
    counts = {}
    for occ in data["occupations"]:
        counts[occ["field_id"]] = counts.get(occ["field_id"], 0) + 1
    rows = []
    for fid, f in data["fields"].items():
        parts = {k: None if s is None or s.get(fid) is None else float(s[fid]) for k, s in sources.items()}
        fit, points = weighted(parts, FIELD_WEIGHTS)
        given = []
        for kind, value in parts.items():
            if value is None:
                continue
            reason = f" ({exp_why[fid]})" if kind == "experience" and fid in exp_why else ""
            given.append(f"{FIELD_SOURCE_LABEL[kind]} {value:g}{reason}")
        rows.append({"id": fid, "name": f["name_en"], "fit": fit, "occupations": counts.get(fid, 0),
                     "parts": {k: {"score": parts[k], "weight": FIELD_WEIGHTS[k], "points": points[k]}
                               for k in FIELD_WEIGHTS},
                     "explain": ", ".join(given) if given else "No answers for this field yet"})
    rows.sort(key=lambda r: (-(r["fit"] if r["fit"] is not None else -1), r["id"]))
    used = [k for k in FIELD_WEIGHTS if sources[k]]
    return {"fields": rows, "sources_used": used, "best": rows[0]["id"] if rows and rows[0]["fit"] is not None else None,
            "insights": field_insights(rows, sources, used, profile, data)}


def field_insights(rows: list[dict], sources: dict, used: list[str], profile: dict, data: dict) -> list[dict]:
    """What the field fits say in words: the best field and its lead, where two kinds of answer
    disagree, when only one kind was given, and the questionnaire's own warnings."""
    name = {f: d["name_en"] for f, d in data["fields"].items()}
    out = []
    scored = [r for r in rows if r["fit"] is not None]
    if scored:
        first = scored[0]
        second = scored[1] if len(scored) > 1 else None
        gap = first["fit"] - (second["fit"] if second else 0)
        text = f"{first['name']} fits you best (field fit {first['fit']:g})"
        if second and gap < CLEAR_LEAD:
            text += f", only {gap:.1f} points ahead of {second['name']}: look at both."
        else:
            text += f", a clear lead of {gap:.1f} points."
        out.append({"type": "best_field", "field": first["id"], "second": second["id"] if second else None,
                    "fit": first["fit"], "gap": round(gap, 1), "close": bool(second and gap < CLEAR_LEAD),
                    "text": text})
    leaders = {k: top_key(sources[k]) for k in used}
    for i, a in enumerate(used):
        for b in used[i + 1:]:
            if leaders[a] and leaders[b] and leaders[a] != leaders[b]:
                out.append({"type": "mismatch", "sources": [a, b], "fields": [leaders[a], leaders[b]],
                            "text": f"Your {FIELD_SOURCE_LABEL[a]} point to {name[leaders[a]]}, your "
                                    f"{FIELD_SOURCE_LABEL[b]} to {name[leaders[b]]}."})
    if len(used) == 1:
        out.append({"type": "one_source", "sources": used,
                    "text": f"Only your {FIELD_SOURCE_LABEL[used[0]]} were used. Add more on the You page for a "
                            "more reliable result."})
    out += [{"type": w["type"], "sources": ["interest"], "text": w["text"]}
            for w in (profile.get("interest") or {}).get("warnings", [])]
    return out


# --- one occupation ---------------------------------------------------------------------------------

def occupation_ai(occ_id: str, data: dict) -> dict | None:
    """What the AI-usage data says about one occupation's tasks, for its card."""
    r = data["ai"]["roles"].get(occ_id)
    if not r:
        return None
    tasks = {t["task_id"]: t for t in data["ai"]["tasks_by_occ"].get(occ_id, [])}

    def brief(tid):
        t = tasks[tid]
        return {k: t[k] for k in ("task_id", "task", "ai_share", "ai_share_low", "ai_share_high",
                                  "automation_pct", "hours_alone", "minutes_with_ai", "importance")}
    return {k: r[k] for k in ("ai_share", "ai_share_low", "ai_share_high", "automation_pct", "usage_pct",
                              "usage_pct_my", "tasks", "tasks_covered", "builder_share", "thin_evidence",
                              "prior_basis", "anthropic_observed_exposure")} | {
        "ai_tasks": [brief(t) for t in r["top_ai_tasks"] if t in tasks],
        "human_tasks": [brief(t) for t in r["top_human_tasks"] if t in tasks]}


def education_flags(occ: dict, profile: dict) -> list[str]:
    zone, mine = occ.get("job_zone"), profile.get("education_job_zone")
    if zone is None or mine is None:
        return []
    if zone > mine:
        return ["needs_extra_education"]
    if zone <= mine - TOO_LOW:
        return ["below_education"]
    return []


def score(profile: dict, occ: dict, data: dict, adoption: float, weights: dict, fits: dict,
          detail: bool = False) -> dict:
    """One occupation's score for the person: its parts, total, flags; with detail, everything shown."""
    skill = skill_score(profile, occ, data, weights, detail)
    future = outlook.role_outlook(occ, data, adoption)
    i_fit, i_why = interest_of(profile, occ)
    field = fits.get(occ["field_id"])
    parts = {"field": field["fit"] if field else None, "interest": i_fit, "skill": skill["score"],
             "outlook": future["outlook"]}
    total, part_points = weighted(parts, WEIGHTS)
    targets = occupation_sdg(occ, data)
    choice = sdg_choice(profile.get("sdg_goals"), targets, total or 0.0)
    flags = education_flags(occ, profile) + [name for name, applies in (
        ("field_not_scored", parts["field"] is None), ("interest_not_scored", i_fit is None),
        ("current_occupation", profile.get("current_occupation") == occ["occ_id"]),
        ("restricted_my", not profile.get("show_restricted") and restriction(occ, data) is not None)) if applies]
    m = {"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"], "field_name": occ["field_name"],
         "job_zone": occ["job_zone"], "mycol": occ["mycol"], "riasec": occ["riasec"], "search_title": occ["search_title"],
         "total": choice["total"],
         "components": {k: {"score": parts[k], "weight": WEIGHTS[k], "points": part_points[k]} for k in WEIGHTS},
         "skill_parts": skill["parts"], "outlook": future, "flags": flags, "sdg_choice": choice,
         "_parts": {"field": parts["field"], "interest": i_fit, "bonus": choice["bonus"],
                    "last": bool(UNLISTED_FLAGS & set(flags))}}
    if detail:
        found = licence(occ, data)
        if found:
            m["flags"].append("licence_needed")
        o = future
        m.update({
            "explain": {"field": f"{field['name']} field fit: {field['explain']}" if field
                        else "Field fit not scored: no field choice, interest or experience answers",
                        "interest": i_why,
                        "outlook": (f"Malaysian demand {o['demand']:g}; AI share of its tasks {o['ai_share']:g} "
                                    f"(average {o['ai_share_reference']:g}); adoption {adoption:g} x tempo "
                                    f"{o['tempo']:g}: {o['change']:+g} points"),
                        "skill": ", ".join(f"{k} {v:g}" for k, v in skill["parts"].items() if v is not None)
                        or "No skill answers yet"},
            # the page shows the first few of each; the counts say how many there are
            "skill_detail": {**{k: skill[k][:DETAIL_ITEMS] for k in ("gaps", "strengths", "tech_used", "tech_missing")},
                             "counts": {k: len(skill[k]) for k in ("gaps", "strengths", "tech_used", "tech_missing")}},
            "pathway": learning_path(skill, data, profile.get("hours_per_week", DEFAULT_HOURS_PER_WEEK)),
            "ai": occupation_ai(occ["occ_id"], data), "sdg": targets, "licence": found,
            "restriction": restriction(occ, data),
            "demand_detail": data["demand"]["occupations"].get(occ["occ_id"]),
            "evidence": evidence.occupation_grade(occ, data),
        })
    return m


def routes(occ_id: str, position: dict, data: dict) -> dict:
    """Career option value: the related occupations (O*NET) that stay open from this one.

    A route is open when the person is not flagged on education for it, it is not declining under
    the scenario, and its match is no more than ROUTE_REACH points below this occupation's. The
    count is a graph measure of how many next moves remain, not a promise of jobs."""
    here = position.get(occ_id)
    if here is None:
        return {"related": 0, "open": 0, "routes": [], "reach_points": ROUTE_REACH}
    mine = set(data["occ_techs"].get(occ_id, []))
    found = []
    for rid in data["related"].get(occ_id, []):
        other = position.get(rid)
        if other is None:
            continue
        shared = mine & set(data["occ_techs"].get(rid, []))
        found.append({"occ_id": rid, "title": other["title"], "field_id": other["field_id"], "rank": other.get("rank"),
                      "total": other["total"], "status": other["outlook"]["status"], "shared_tools": len(shared),
                      "open": (not other["_parts"]["last"] and other["outlook"]["status"] != "declining"
                               and other["total"] >= here["total"] - ROUTE_REACH)})
    open_routes = sorted((r for r in found if r["open"]), key=lambda r: (-r["total"], r["title"]))
    return {"related": len(found), "open": len(open_routes), "routes": open_routes[:ROUTES_SHOWN],
            "reach_points": ROUTE_REACH}


# --- learning path ----------------------------------------------------------------------------------

def is_free(r: dict) -> bool:
    return not r.get("cost_myr") or number(r["cost_myr"]) == 0


def resource_item(r: dict) -> dict:
    return {"id": r["resource_id"], "title": r["title"], "provider": r["provider"], "format": r["format"] or "course",
            "url": r["url"], "hours": number(r["duration_hours"]), "cost_myr": number(r["cost_myr"]),
            "level": r["level"], "language": r["language"], "verified_date": r["verified_date"], "notes": r["notes"]}


def resources_for(target: str, data: dict) -> list[dict]:
    return [r for r in data["by_target"].get(target, []) if is_free(r)]


def learning_path(skill: dict, data: dict, hours_per_week: float = DEFAULT_HOURS_PER_WEEK) -> dict:
    """Free resources on the gaps, in order: gaps the person rated (biggest first), missing
    technologies (the ones that count most under the scenario first), then elements the person
    did not rate. A resource that covers several gaps is listed once; gaps with no checked
    resource are returned apart so the page says so instead of inventing one."""
    rated = [g for g in skill["gaps"] if g["rated"] and g["level_needed"] - g["your_level"] >= MIN_PATH_GAP]
    unrated = [g for g in skill["gaps"] if not g["rated"] and g["level_needed"] >= MIN_PATH_GAP]
    order = [(g["skill_id"], g["skill_name"], g["ai"], "element") for g in rated] + \
            [(t["skill_id"], t["skill_name"], t["ai"], "tech") for t in skill["tech_missing"]] + \
            [(g["skill_id"], g["skill_name"], g["ai"], "element") for g in unrated]
    steps, seen, without = [], {}, []
    for sid, name, ai, kind in order:
        found = resources_for(f"{kind}:{sid}", data)
        if not found:
            if kind == "element":
                without.append({"skill_id": sid, "skill_name": name, "ai": ai})
            continue
        for r in found:
            if r["url"] in seen:
                seen[r["url"]]["skills"].append(name)
                continue
            if len(steps) >= MAX_PATH_STEPS:
                break
            step = {**resource_item(r), "skills": [name], "skill_ids": [sid], "ai": ai}
            seen[r["url"]] = step
            steps.append(step)
    hours = round(sum(s["hours"] for s in steps if s["hours"]), 1)
    return {"steps": steps, "total_hours": hours, "hours_per_week": hours_per_week,
            "weeks": round(hours / hours_per_week, 1) if hours_per_week else None,
            "steps_without_hours": sum(1 for s in steps if not s["hours"]), "gaps_without_course": without[:8]}


# --- the whole ranking --------------------------------------------------------------------------------

def with_current_occupation(profile: dict, data: dict) -> dict:
    """A working person's profile: doing a job counts as having its O*NET skills and knowledge at
    the level the job needs. Tools are never assumed. A level the person gave is never lowered."""
    occ = data["by_id"].get(profile.get("current_occupation") or "")
    if occ is None:
        return profile
    skills = dict(profile.get("skills", {}))
    for eid, _, need, _ in data["occ_elements"].get(occ["occ_id"], []):
        skills[eid] = max(float(skills.get(eid, 0.0)), need)
    return {**profile, "skills": skills}


def with_interest(profile: dict) -> dict:
    """The profile with its questionnaire scored, when it has answers but no result yet."""
    answers = profile.get("interest_answers")
    if answers is None or "interest" in profile:
        return profile
    import interest  # only the demo people and the command line need it here
    return {**profile, "interest": interest.score(answers)}


def prepare(profile: dict, data: dict) -> dict:
    """The profile with its current job's skills added and what every request reuses worked out
    once: which skill parts it answered and its interest fit with every occupation."""
    if "_kinds" in profile:
        return profile
    profile = with_current_occupation(with_interest(profile), data)
    riasec = usable_interest(profile)
    fits = {o["occ_id"]: interest_fit(riasec, o) for o in data["occupations"]}
    return {**profile, "_kinds": answered_kinds(profile, data), "_interest_fit": fits}


def interest_of(profile: dict, occ: dict) -> tuple[float | None, str]:
    found = (profile.get("_interest_fit") or {}).get(occ["occ_id"])
    return found if found is not None else interest_fit(usable_interest(profile), occ)


def order_key(m: dict) -> tuple:
    return (m["_parts"]["last"], -m["total"], m["title"])


def rank(profile: dict, data: dict | None = None, scenario: str | None = None, adoption: float | None = None,
         fit: dict | None = None) -> list[dict]:
    """Score every occupation (without detail) for the profile under a scenario or adoption value."""
    if data is None:
        data = load_data()
    adoption = outlook.adoption_of(scenario, adoption)
    profile = prepare(profile, data)
    fit = fit or field_fit(profile, data)
    fits = {f["id"]: f for f in fit["fields"] if f["fit"] is not None}
    weights = outlook.skill_weights(data, adoption)
    return sorted((score(profile, occ, data, adoption, weights, fits) for occ in data["occupations"]), key=order_key)


def stability(profile: dict, data: dict, ranked: list[dict], futures: int = outlook.FUTURES) -> dict:
    """How the top of the ranking holds up across drawn futures (outlook.simulate)."""
    profile = prepare(profile, data)
    grids = [outlook.skill_weights(data, a) for a in outlook.GRID]
    drawn = []
    for m in ranked[:STABILITY_POOL]:
        occ = data["by_id"][m["occ_id"]]
        curve = [skill_score(profile, occ, data, w)["score"] for w in grids]
        o = m["outlook"]
        drawn.append({"occ_id": m["occ_id"], "field": m["_parts"]["field"], "interest": m["_parts"]["interest"],
                      "skill_curve": None if curve[0] is None else [round(v, 3) for v in curve],
                      "demand": o["demand"], "ai_share": o["ai_share"], "ai_share_low": o["ai_share_low"],
                      "ai_share_high": o["ai_share_high"], "builder": o["builder"], "tempo": o["tempo"], "thin": o["thin"],
                      "bonus": m["_parts"]["bonus"], "last": m["_parts"]["last"]})
    return outlook.simulate(drawn, combine, data["ai"]["reference"], n=futures)


def detailed(profile: dict, data: dict, occ_id: str, adoption: float, fit: dict) -> dict | None:
    """The full card of one occupation for the person."""
    occ = data["by_id"].get(occ_id)
    if occ is None:
        return None
    profile = prepare(profile, data)
    fits = {f["id"]: f for f in fit["fields"] if f["fit"] is not None}
    m = score(profile, occ, data, adoption, outlook.skill_weights(data, adoption), fits, detail=True)
    m.pop("_parts")
    return m


def match_person(profile: dict, data: dict | None = None, scenario: str | None = None, adoption: float | None = None,
                 top: int = 10, futures: int = outlook.FUTURES, include: list[str] | None = None) -> dict:
    """The whole result: field fit with insights, then the top occupations in full, each with how
    often it stays near the top across the drawn futures. include: occupations to add in full."""
    if data is None:
        data = load_data()
    adoption = outlook.adoption_of(scenario, adoption)
    prepared = prepare(profile, data)
    fit = field_fit(prepared, data)
    ranked = rank(prepared, data, adoption=adoption, fit=fit)
    sim = stability(prepared, data, ranked, futures) if futures else None
    place = 0
    for m in ranked:  # the job the person does now is shown on its own, not numbered among the moves
        if "current_occupation" in m["flags"]:
            m["rank"] = None
        else:
            place += 1
            m["rank"] = place
    wanted = [m["occ_id"] for m in ranked[:top]] + [x for x in (include or []) if x in data["by_id"]]
    position = {m["occ_id"]: m for m in ranked}
    results = []
    for occ_id in dict.fromkeys(wanted):
        m = detailed(prepared, data, occ_id, adoption, fit)
        m["rank"] = position[occ_id]["rank"]
        m["stability"] = (sim["roles"].get(occ_id) if sim else None)
        m["routes"] = routes(occ_id, position, data)
        results.append(m)
    by_field = {}
    for m in ranked:
        if not m["_parts"]["last"]:
            by_field.setdefault(m["field_id"], []).append(m["occ_id"])
    for f in fit["fields"]:
        f["top"] = by_field.get(f["id"], [])[:3]
    light = [{"occ_id": m["occ_id"], "title": m["title"], "field_id": m["field_id"], "rank": m["rank"],
              "total": m["total"], "status": m["outlook"]["status"], "flags": m["flags"]} for m in ranked]
    return {**fit, "results": results, "ranking": light, "adoption": adoption,
            "simulation": {k: v for k, v in sim.items() if k != "roles"} if sim else None}


def main() -> int:
    """Print one demo person's fields and top occupations, for a quick look from the command line."""
    cli = argparse.ArgumentParser(description="Rank every occupation for one of the demo people.")
    cli.add_argument("--profile", default="P01", help="a profile_id from data/sample_profiles.json")
    cli.add_argument("--top", type=int, default=8)
    cli.add_argument("--scenario", choices=list(SCENARIOS), default=DEFAULT_SCENARIO)
    opts = cli.parse_args()
    people = {p["profile_id"]: p for p in json.loads((DATA / "sample_profiles.json").read_text(encoding="utf-8"))}
    if opts.profile not in people:
        print(f"There is no demo person {opts.profile}; try one of {', '.join(people)}.")
        return 1
    person = people[opts.profile]
    result = match_person(person, scenario=opts.scenario, top=opts.top)
    print(f"{person['name']}: fields")
    for row in result["fields"][:6]:
        fit = "-" if row["fit"] is None else f"{row['fit']:g}"
        print(f"  {fit:>5}  {row['name']}  ({row['explain']})")
    for note in result["insights"]:
        print(f"  - {note['text']}")
    print(f"\n{person['name']}: top {opts.top} under {SCENARIOS[opts.scenario]['name']} (estimates, not predictions)")
    for m in result["results"]:
        parts = "  ".join(f"{k} {v['score']}" for k, v in m["components"].items())
        flags = f"  [{', '.join(m['flags'])}]" if m["flags"] else ""
        print(f"  {m['rank'] or 'now':>3}. {m['total']:5.1f}  {m['title']} ({m['field_name']}){flags}")
        print(f"         {parts}  outlook {m['outlook']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
