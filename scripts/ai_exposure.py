"""The AI-exposure layer: how much of each task, occupation, topic and skill people already hand to AI.

Built from the extracts scripts/ai_exposure_extract.py writes (data/aei/, data/onet/):

    Anthropic Economic Index    monthly Claude.ai usage by O*NET task, occupation, work activity
                                and request topic, with the share of conversations that are
                                "automation" (the person hands the task over) or "augmentation"
                                (the person works with the AI). Global and Malaysia.
    Anthropic task penetration  Anthropic's own task-level coverage, built from its August and
                                November 2025 samples (Labor market impacts, 2026-03-05).
    O*NET 31.0                  each occupation's task statements and their importance, O*NET's
                                links from tasks to work activities and from skills to work activities.

Four tables, each row with its source and date:

    Task     ai_share 0-100. Two readings of the same thing, averaged:
               A  ours, from the latest Economic Index month: a task with at least MIN_USAGE_PCT
                  of all conversations counts, weighted as Anthropic weights it - automation in
                  full, augmentation by half:  A = automation% x 1 + augmentation% x 0.5
               B  Anthropic's task penetration x 100
             A task neither reading sees gets 0. The two readings are also kept as the low and
             high end, so every number above them comes with a range.
    Occupation  ai_share = mean of its tasks' ai_share, weighted by O*NET task importance, then
             steadied: an occupation with little usage in the data is pulled towards a prior
             (steady_readings): Anthropic's own observed exposure of that occupation, else the
             well-measured occupations of its field. A what-if's changed tasks are then added in
             full (lift_roles). Also the occupation's own Economic Index rows:
             its share of all usage (global and Malaysia) and its automation share.
             builder_share = the part of its Hot and In Demand technologies that are used to
             build AI (AI_BUILD_TOPICS).
    Topic    the Economic Index request topics our technologies map to (data/skill_topic_map.csv,
             our crosswalk): share of all usage, and handoff = automation share.
    Skill    handoff 0-100, "when AI is used for this, how often is it handed over entirely":
               technology        its topic's automation share
               O*NET skill       automation share of the generalized work activities O*NET links
                                 the skill to, weighted by each activity's share of usage (no
                                 value when those activities are under MIN_ACTIVITY_PCT of usage)
               knowledge area    no link exists in O*NET: no data, counted as neutral
             builder = the technology builds AI.

Nothing here predicts anything: it is what the latest release measured. scripts/outlook.py
applies the scenarios. build(changes=...) runs the same code on a changed copy (what-if).

Usage: python scripts/ai_exposure.py      # rebuild data/ai_*.csv and print a summary
Standard library only.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MIN_USAGE_PCT = 0.01      # a task below this share of all conversations is not counted as covered
MIN_ACTIVITY_PCT = 0.5    # an O*NET skill whose linked work activities have less usage than this gets no value
FULL_EVIDENCE_PCT = 0.25  # an occupation with at least this share of all usage is trusted as measured
THIN_SPREAD = 15.0        # points of range, each side, for an occupation with no usage evidence at all
AUTOMATION_WEIGHT = 1.0   # Anthropic's weighting in its observed-exposure measure
AUGMENTATION_WEIGHT = 0.5
DEFAULT_IMPORTANCE = 3.0  # O*NET's 1-5 scale; used for the few tasks O*NET has not rated
# Topics whose tools are used to build AI systems; a team choice, shown on the Sources page.
AI_BUILD_TOPICS = ("AI app building", "AI agent design", "ML and data science",
                   "AI evaluation and risk", "Prompt engineering")
FORMULA_VERSION = "v2-all-occupations"

AUTO, AUG = "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct"


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_inputs() -> dict:
    """Every file build() reads. A what-if changes a copy of nothing here: it passes `changes`."""
    return {
        "aei": read("aei/aei_extract.csv"),
        "penetration": {r["task_id"]: float(r["penetration"]) for r in read("aei/task_penetration.csv")},
        "job_exposure": {r["occ_code"]: float(r["observed_exposure"]) for r in read("aei/job_exposure.csv")},
        "tasks": read("onet/tasks.csv"),
        "skill_links": read("onet/skill_work_activities.csv"),
        "topic_map": read("skill_topic_map.csv"),
        "roles": read("occupations.csv"),
        "elements": read("elements.csv"),
        "technologies": read("technologies.csv"),
        "role_techs": read("occupation_technologies.csv"),
        "source": json.loads((DATA / "aei" / "source.json").read_text(encoding="utf-8")),
    }


class Usage:
    """Economic Index rows by (geo, category, level, node) -> {(month, metric): value}."""

    def __init__(self, rows: list[dict]):
        self.values = {}
        months = set()
        for r in rows:
            cat = r["category_name"]
            node = "overall" if cat == "overall" else r["node_name"] if cat == "request" else r["node_external_id"]
            key = (r["geo_id"], r["category_name"], r["hierarchy_level"], node)
            self.values.setdefault(key, {})[(r["date_start"][:7], r["metric_id"])] = float(r["value"])
            months.add(r["date_start"][:7])
        self.months = sorted(months)
        self.latest = self.months[-1]
        self.previous = self.months[-2] if len(self.months) > 1 else None

    def get(self, geo: str, category: str, level: str, node: str, metric: str, month: str | None = None):
        return self.values.get((geo, category, level, node), {}).get((month or self.latest, metric))

    def recent(self, geo: str, category: str, level: str, node: str, metric: str):
        """The latest month's value, else the month before (a cell is published only above a threshold)."""
        for month in (self.latest, self.previous):
            if month and (v := self.get(geo, category, level, node, metric, month)) is not None:
                return v
        return None

    def nodes(self, geo: str, category: str, level: str) -> list[str]:
        return sorted(k[3] for k in self.values if k[:3] == (geo, category, level))


def weighted_reading(automation: float | None, augmentation: float | None) -> float | None:
    """Anthropic's weighting of how a task is carried out, 0-100."""
    if automation is None and augmentation is None:
        return None
    return round(AUTOMATION_WEIGHT * (automation or 0.0) + AUGMENTATION_WEIGHT * (augmentation or 0.0), 1)


def split(names: str) -> list[str]:
    return [n for n in names.split(" | ") if n]


def build_tasks(inputs: dict, u: Usage, changes: dict) -> list[dict]:
    floors = changes.get("ai_share") or {}
    soc_auto = {r["occ_id"]: weighted_reading(u.recent("GLOBAL", "soc_occupation", "0", r["occ_id"], AUTO),
                                              u.recent("GLOBAL", "soc_occupation", "0", r["occ_id"], AUG))
                for r in inputs["roles"]}
    everyone = weighted_reading(u.recent("GLOBAL", "overall", "0", "overall", AUTO),
                                u.recent("GLOBAL", "overall", "0", "overall", AUG))
    out = []
    for t in inputs["tasks"]:
        tid = t["task_id"]
        usage = u.recent("GLOBAL", "onet", "0", tid, "pct")
        auto, aug = u.recent("GLOBAL", "onet", "0", tid, AUTO), u.recent("GLOBAL", "onet", "0", tid, AUG)
        covered = usage is not None and usage >= MIN_USAGE_PCT
        ours = 0.0
        if covered:  # a covered task whose collaboration split is not published uses its occupation's
            ours = weighted_reading(auto, aug) or soc_auto.get(t["occ_id"]) or everyone or 0.0
        theirs = inputs["penetration"].get(tid)
        readings = [ours] + ([round(100 * theirs, 1)] if theirs is not None else [])
        share, low, high = sum(readings) / len(readings), min(readings), max(readings)
        measured = {"ai_share": round(share, 1), "ai_share_low": round(low, 1), "ai_share_high": round(high, 1)}
        raised = max((floors[a] for a in split(t["dwa_names"]) if a in floors), default=None)
        if raised is not None and raised > share:
            share, low, high = raised, max(low, raised), max(high, raised)
        out.append({
            "occ_id": t["occ_id"], "task_id": tid, "task": t["task"],
            "task_type": t["task_type"],
            "importance": float(t["importance"]) if t["importance"] else None,
            "work_activities": split(t["dwa_names"]), "activity_groups": split(t["iwa_names"]),
            "general_activities": split(t["gwa_ids"]),
            "emerging": t["emerging"] == "Y",
            "usage_pct": usage, "usage_pct_previous": u.get("GLOBAL", "onet", "0", tid, "pct", u.previous)
            if u.previous else None,
            "usage_pct_my": u.recent("MYS", "onet", "0", tid, "pct"),
            "automation_pct": auto, "augmentation_pct": aug,
            "hours_alone": u.recent("GLOBAL", "onet", "0", tid, "human_only_time_mean"),
            "minutes_with_ai": u.recent("GLOBAL", "onet", "0", tid, "human_with_ai_time_mean"),
            "reading_usage": round(ours, 1), "reading_penetration": readings[1] if len(readings) > 1 else None,
            "ai_share": round(share, 1), "ai_share_low": round(low, 1), "ai_share_high": round(high, 1),
            "measured": measured, "changed": raised is not None and raised > measured["ai_share"],
        })
    return out


def build_roles(inputs: dict, u: Usage, tasks: list[dict], skills: dict) -> dict:
    by_occ = {}
    for t in tasks:
        by_occ.setdefault(t["occ_id"], []).append(t)
    techs = {}
    for r in inputs["role_techs"]:
        techs.setdefault(r["occ_id"], []).append(r["tech_id"])
    out = {}
    for r in inputs["roles"]:
        soc = r["occ_id"]
        mine = by_occ.get(soc, [])
        rated = [t["importance"] for t in mine if t["importance"] is not None]
        fill = sum(rated) / len(rated) if rated else DEFAULT_IMPORTANCE
        weights = [t["importance"] if t["importance"] is not None else fill for t in mine]
        total = sum(weights) or 1.0

        def mean(key, of=lambda t: t, digits=1):
            return round(sum(w * of(t)[key] for w, t in zip(weights, mine)) / total, digits) if mine else None

        def as_measured(t):
            return t["measured"]
        mine_techs = techs.get(soc, [])
        builders = [s for s in mine_techs if skills.get(s, {}).get("builder")]
        ranked = sorted(mine, key=lambda t: (-t["ai_share"], -(t["importance"] or 0)))
        out[soc] = {
            "occ_id": soc, "title": r["title"], "field_id": r["field_id"],
            "tasks": len(mine), "tasks_covered": sum(1 for t in mine if t["ai_share"] > 0),
            # the measured values; a what-if's changed tasks are added by lift_roles() after steadying
            "ai_share": mean("ai_share", as_measured), "ai_share_low": mean("ai_share_low", as_measured),
            "ai_share_high": mean("ai_share_high", as_measured),
            "lift": (mean("ai_share", digits=4) - mean("ai_share", as_measured, 4)) if mine else 0.0,
            "reading_usage": mean("reading_usage"),
            "reading_penetration": round(sum(w * (t["reading_penetration"] or 0.0) for w, t in zip(weights, mine)) / total, 1)
            if mine else None,
            "anthropic_observed_exposure": round(100 * inputs["job_exposure"][soc[:7]], 1)
            if soc[:7] in inputs["job_exposure"] else None,
            "automation_pct": u.recent("GLOBAL", "soc_occupation", "0", soc, AUTO),
            "usage_pct": u.recent("GLOBAL", "soc_occupation", "0", soc, "pct"),
            "usage_pct_previous": u.get("GLOBAL", "soc_occupation", "0", soc, "pct", u.previous) if u.previous else None,
            "usage_pct_my": u.recent("MYS", "soc_occupation", "0", soc, "pct"),
            "builder_share": round(100 * len(builders) / len(mine_techs), 1) if mine_techs else 0.0,
            "builder_skills": builders, "technologies": len(mine_techs),
            "top_ai_tasks": [t["task_id"] for t in ranked[:3] if t["ai_share"] > 0],
            "top_human_tasks": [t["task_id"] for t in sorted(mine, key=lambda t: (t["ai_share"], -(t["importance"] or 0)))[:3]],
        }
    return out


def steady_readings(roles: dict) -> float:
    """Pull the AI share of thinly used occupations towards a prior.

    The Economic Index counts conversations, so an occupation few people bring to Claude shows
    little usage whatever AI could do for it. Reading that as "AI hardly touches this job"
    would call every small occupation safe. So each occupation's share is trusted in
    proportion to its evidence:

        evidence = min(1, the occupation's share of all usage / FULL_EVIDENCE_PCT)
        ai_share = evidence x measured + (1 - evidence) x prior

    prior = Anthropic's observed exposure of the occupation (Labor market impacts), when it is
    above 0: Anthropic's own reading of the same occupation from its larger samples. Anthropic
    gives 0 to an occupation none of whose tasks it observed, which is a missing reading, so
    then the prior is the usage-weighted mean measured share of the occupation's field.
    A thin occupation also keeps a range at least THIN_SPREAD points wide on each side, since
    less evidence means less certainty, not more. Returns the all-occupation prior.
    """
    usage = {k: r["usage_pct"] or 0.0 for k, r in roles.items()}

    def pooled(keys):
        total = sum(usage[k] for k in keys)
        if total:
            return sum(usage[k] * roles[k]["ai_share"] for k in keys) / total
        return sum(roles[k]["ai_share"] for k in keys) / max(1, len(keys))
    overall = pooled(list(roles))
    fields = {}
    for k, r in roles.items():
        fields.setdefault(r["field_id"], []).append(k)
    field_prior = {f: pooled(keys) if sum(usage[k] for k in keys) else overall for f, keys in fields.items()}
    for k, r in roles.items():
        # Anthropic reports 0 for an occupation none of whose tasks it observed: no reading, not a reading of 0
        own = r["anthropic_observed_exposure"] or None
        prior = own if own is not None else field_prior[r["field_id"]]
        e = min(1.0, usage[k] / FULL_EVIDENCE_PCT)
        slack = (1 - e) * THIN_SPREAD
        measured = r["ai_share"]
        share = e * measured + (1 - e) * prior
        r.update(ai_share_measured=measured, evidence=round(e, 2), thin_evidence=e < 0.5,
                 prior=round(prior, 1), prior_basis="anthropic_exposure" if own is not None else "field",
                 ai_share=round(share, 1),
                 ai_share_low=round(max(0.0, min(e * r["ai_share_low"] + (1 - e) * prior, share - slack)), 1),
                 ai_share_high=round(min(100.0, max(e * r["ai_share_high"] + (1 - e) * prior, share + slack)), 1))
    return round(overall, 1)


def lift_roles(roles: dict) -> None:
    """Add what a what-if changed to each role, in full.

    The steadied share is our estimate of today. A what-if is an assumption put on top of it
    ("suppose these tasks were handed to AI"), not a reading to be doubted, so the change in the
    role's task mean is added as it is: a thinly measured role moves as far as a well-measured
    one, and a role the change does not touch stays where it was.
    """
    for r in roles.values():
        lift = r.pop("lift")
        r["changed"] = abs(lift) >= 0.05
        if r["changed"]:
            for key in ("ai_share", "ai_share_low", "ai_share_high"):
                r[key] = round(min(100.0, max(0.0, r[key] + lift)), 1)


def build_topics(inputs: dict, u: Usage, changes: dict) -> dict:
    edits = changes.get("handoff") or {}
    mapped = {}
    for m in inputs["topic_map"]:
        if m["topic"]:
            mapped.setdefault(m["topic"], []).append(m["tech_id"])
    out = {}
    for name in u.nodes("GLOBAL", "request", "1"):
        if name not in mapped and name not in AI_BUILD_TOPICS:
            continue
        auto = u.recent("GLOBAL", "request", "1", name, AUTO)
        handoff = edits.get(name, auto)
        out[name] = {
            "topic": name, "skills": mapped.get(name, []), "builder": name in AI_BUILD_TOPICS,
            "usage_pct": u.recent("GLOBAL", "request", "1", name, "pct"),
            "usage_pct_previous": u.get("GLOBAL", "request", "1", name, "pct", u.previous) if u.previous else None,
            "usage_pct_my": u.recent("MYS", "request", "1", name, "pct"),
            "work_pct": u.recent("GLOBAL", "request", "1", name, "use_case_work_pct"),
            "handoff": handoff, "handoff_measured": auto, "changed": name in edits and edits[name] != auto,
        }
    return out


def build_skills(inputs: dict, u: Usage, topics: dict) -> dict:
    """Hands-off share of every skill, knowledge area and technology, keyed by its id."""
    topic_of = {m["tech_id"]: m for m in inputs["topic_map"]}
    links = {}
    for row in inputs["skill_links"]:
        links.setdefault(row["element_id"], []).append((row["gwa_id"], row["gwa_name"]))
    every = [(e["element_id"], e["name"], e["kind"]) for e in inputs["elements"]] + \
            [(t["tech_id"], t["name"], "technology") for t in inputs["technologies"]]
    out = {}
    for sid, name, kind in every:
        row = {"skill_id": sid, "skill_name": name, "skill_type": kind, "handoff": None,
               "handoff_my": None, "basis": "none", "evidence": [], "usage_pct": None, "builder": False,
               "changed": False, "note": ""}
        if kind == "technology":
            m = topic_of.get(sid)
            topic = topics.get(m["topic"]) if m and m["topic"] else None
            if topic and topic["handoff"] is not None:
                row.update(handoff=topic["handoff"], basis="topic", evidence=[topic["topic"]],
                           usage_pct=topic["usage_pct"], builder=topic["builder"], changed=topic["changed"],
                           note=m["rationale"])
            else:
                row["note"] = (m or {}).get("rationale") or "No matching usage topic; counted as neutral"
        elif sid in links:
            seen = []
            for gid, gname in links[sid]:
                share, auto = u.recent("GLOBAL", "onet", "3", gid, "pct"), u.recent("GLOBAL", "onet", "3", gid, AUTO)
                if share and auto is not None:
                    seen.append((share, auto, gname, u.recent("MYS", "onet", "3", gid, AUTO),
                                 u.recent("MYS", "onet", "3", gid, "pct")))
            total = sum(x[0] for x in seen)
            if seen and total >= MIN_ACTIVITY_PCT:
                local = [(x[4], x[3]) for x in seen if x[3] is not None and x[4]]
                row.update(handoff=round(sum(x[0] * x[1] for x in seen) / total, 1), basis="work_activity",
                           evidence=[x[2] for x in sorted(seen, key=lambda x: -x[0])[:3]],
                           usage_pct=round(total, 2),
                           handoff_my=round(sum(a * b for a, b in local) / sum(a for a, _ in local), 1) if local else None,
                           note=f"O*NET links this skill to {len(links[sid])} work activities")
            else:
                row["note"] = (f"Its work activities are under {MIN_ACTIVITY_PCT}% of usage: too thin to read; "
                               "counted as neutral")
        else:
            row["note"] = "O*NET links no work activity to knowledge areas; counted as neutral"
        out[sid] = row
    return out


def build_context(u: Usage, field_ids: list[str]) -> dict:
    """Malaysia next to the world, per field and overall, and what people use AI for."""
    def pair(category, level, node, metric):
        return {"global": u.recent("GLOBAL", category, level, node, metric),
                "malaysia": u.recent("MYS", category, level, node, metric)}
    index = {m: u.get("MYS", "overall", "0", "overall", "usage_per_capita_index", m) for m in u.months}
    uses = {name: {"usage": pair("request", "2", name, "pct"), "automation": pair("request", "2", name, AUTO)}
            for name in u.nodes("GLOBAL", "request", "2")}
    return {
        "months": u.months, "latest": u.latest,
        "usage_index_my": index,
        "usage_share_my": u.recent("MYS", "overall", "0", "overall", "usage_pct"),
        "automation_all": pair("overall", "0", "overall", AUTO),
        "work_use": pair("overall", "0", "overall", "use_case_work_pct"),
        "coursework_use": pair("overall", "0", "overall", "use_case_coursework_pct"),
        "fields": {f: {"usage": pair("soc_occupation", "1", f, "pct"),
                       "automation": pair("soc_occupation", "1", f, AUTO)} for f in field_ids},
        "uses": dict(sorted(uses.items(), key=lambda kv: -(kv[1]["usage"]["global"] or 0))),
    }


def build(inputs: dict | None = None, changes: dict | None = None) -> dict:
    """All four tables. `changes` (scripts/whatif.py) edits the measured values for one request:
    {"handoff": {topic: new automation share 0-100}, "ai_share": {work activity: at least 0-100}}.
    A work activity is one of O*NET's detailed work activities ("Write computer programming code.")."""
    inputs = inputs or load_inputs()
    changes = changes or {}
    u = Usage(inputs["aei"])
    topics = build_topics(inputs, u, changes)
    skills = build_skills(inputs, u, topics)
    tasks = build_tasks(inputs, u, changes)
    roles = build_roles(inputs, u, tasks, skills)
    prior = steady_readings(roles)
    lift_roles(roles)
    field_ids = sorted({r["field_id"] for r in roles.values()})
    context = build_context(u, field_ids)
    shares = [r["ai_share"] for r in roles.values() if r["ai_share"] is not None]
    builders = [r["builder_share"] for r in roles.values()]
    by_field = {}
    for r in roles.values():
        by_field.setdefault(r["field_id"], []).append(r["ai_share"])
    reference = {
        "role_ai_share": round(sum(shares) / len(shares), 1) if shares else 0.0,   # mean over every occupation
        "role_builder_share": round(sum(builders) / len(builders), 1) if builders else 0.0,
        "skill_handoff": context["automation_all"]["global"] or 50.0,               # all Claude.ai use
        "field_ai_share": {f: round(sum(v) / len(v), 1) for f, v in sorted(by_field.items())},
    }
    reference["well_measured_ai_share"] = prior
    tasks_by_occ = {}
    for t in tasks:
        tasks_by_occ.setdefault(t["occ_id"], []).append(t)
    return {"tasks": tasks, "tasks_by_occ": tasks_by_occ, "roles": roles, "topics": topics, "skills": skills,
            "context": context, "reference": reference, "source": inputs["source"],
            "formula_version": FORMULA_VERSION,
            "changed": bool(changes.get("handoff") or changes.get("ai_share"))}


_cache = {"key": None, "value": None}
_FILES = ("aei/aei_extract.csv", "aei/task_penetration.csv", "aei/job_exposure.csv", "aei/source.json",
          "onet/tasks.csv", "onet/skill_work_activities.csv", "skill_topic_map.csv", "occupations.csv",
          "elements.csv", "technologies.csv", "occupation_technologies.csv")


def current() -> dict:
    """build() of the files as they are, rebuilt only when one of them changes."""
    key = tuple((DATA / f).stat().st_mtime_ns for f in _FILES)
    if _cache["key"] != key:
        _cache.update(key=key, value=build())
    return _cache["value"]


# --- the tables as files: for people to read, for validate_data.py and for the tests ---------------

def tables(layer: dict) -> dict[str, list[dict]]:
    period = layer["context"]["latest"]
    join = lambda xs: " | ".join(str(x) for x in xs)  # noqa: E731
    blank = lambda v: "" if v is None else v  # noqa: E731
    tasks = [{"occ_id": t["occ_id"], "task_id": t["task_id"], "importance": blank(t["importance"]),
              "usage_pct": blank(t["usage_pct"]), "automation_pct": blank(t["automation_pct"]),
              "augmentation_pct": blank(t["augmentation_pct"]), "hours_alone": blank(t["hours_alone"]),
              "minutes_with_ai": blank(t["minutes_with_ai"]), "reading_usage": t["reading_usage"],
              "reading_penetration": blank(t["reading_penetration"]), "ai_share": t["ai_share"],
              "ai_share_low": t["ai_share_low"], "ai_share_high": t["ai_share_high"]}
             for t in layer["tasks"]]
    roles = [{"occ_id": r["occ_id"], "title": r["title"], "field_id": r["field_id"], "tasks": r["tasks"],
              "tasks_covered": r["tasks_covered"], "ai_share": r["ai_share"], "ai_share_low": r["ai_share_low"],
              "ai_share_high": r["ai_share_high"], "ai_share_measured": r["ai_share_measured"],
              "evidence": r["evidence"], "prior": r["prior"], "prior_basis": r["prior_basis"],
              "reading_usage": r["reading_usage"], "reading_penetration": r["reading_penetration"],
              "anthropic_observed_exposure": blank(r["anthropic_observed_exposure"]),
              "automation_pct": blank(r["automation_pct"]), "usage_pct": blank(r["usage_pct"]),
              "usage_pct_my": blank(r["usage_pct_my"]), "builder_share": r["builder_share"],
              "builder_skills": join(r["builder_skills"]), "data_period": period, "formula_version": FORMULA_VERSION}
             for r in layer["roles"].values()]
    topics = [{"topic": t["topic"], "usage_pct": blank(t["usage_pct"]), "usage_pct_previous": blank(t["usage_pct_previous"]),
               "usage_pct_my": blank(t["usage_pct_my"]), "work_pct": blank(t["work_pct"]), "handoff": blank(t["handoff"]),
               "builder": "Y" if t["builder"] else "N", "technologies": join(t["skills"]), "data_period": period}
              for t in layer["topics"].values()]
    skills = [{"skill_id": s["skill_id"], "skill_name": s["skill_name"], "skill_type": s["skill_type"],
               "handoff": blank(s["handoff"]), "handoff_my": blank(s["handoff_my"]), "basis": s["basis"],
               "evidence": join(s["evidence"]), "builder": "Y" if s["builder"] else "N", "note": s["note"],
               "data_period": period}
              for s in layer["skills"].values()]
    return {"ai_tasks.csv": tasks, "ai_occupations.csv": roles, "ai_topics.csv": topics, "ai_skills.csv": skills}


def write_tables(layer: dict) -> None:
    for name, rows in tables(layer).items():
        with (DATA / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {len(rows):>5} rows to data/{name}")


def main() -> int:
    layer = build()
    write_tables(layer)
    c, ref = layer["context"], layer["reference"]
    print(f"Economic Index months {c['months']}; Malaysia usage index {c['usage_index_my']}")
    print(f"Reference: handoff of all use {ref['skill_handoff']}%, mean occupation AI share {ref['role_ai_share']}%, "
          f"mean builder share {ref['role_builder_share']}%; usage-weighted share {ref['well_measured_ai_share']}%")
    print("field mean AI share: " + ", ".join(f"{f} {v}" for f, v in ref["field_ai_share"].items()))
    ranked = sorted(layer["roles"].values(), key=lambda r: -r["ai_share"])
    print("highest and lowest AI share (low-high), measured, evidence, prior:")
    for r in ranked[:8] + ranked[-8:]:
        print(f"  {r['occ_id']} {r['title'][:40]:<40} {r['ai_share']:5.1f} ({r['ai_share_low']:4.1f}-{r['ai_share_high']:4.1f})"
              f"  {r['ai_share_measured']:5.1f}  {r['evidence']:4.2f}  {r['prior']:5.1f} {r['prior_basis']}")
    with_data = [s for s in layer["skills"].values() if s["handoff"] is not None]
    print(f"{len(with_data)} of {len(layer['skills'])} skills and technologies have a handoff value; "
          f"{len(layer['topics'])} topics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
