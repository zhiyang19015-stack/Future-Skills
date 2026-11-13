"""The learning page for one occupation: what to learn, in order, with checked free links.

Stages:
  1. Foundations     free resources for the occupation's field and for every job seeker
  2. Skills to build its skills, knowledge areas and Hot technologies, biggest gap first, each
                     with free resources (data/learning_resources.csv). With a profile these are
                     the person's own gaps (matching.py); without one, the occupation's own list
                     by importance.
  3. Hands-on        training programmes in Malaysia for the practical skills a course online
                     cannot teach (skills certificates, site safety), when the occupation needs them
  4. Licence         the body a regulated profession must register with in Malaysia

The page adds up the SDG targets the path serves: the occupation's own targets and those of the
skills on it (data/sdg_map.csv), each with its reason.

Every link was opened on its verified_date. A skill with no checked resource says so instead of
pointing at one nobody has looked at.
"""

import matching
import outlook

MAX_SKILLS = 10
MAX_PER_SKILL = 2


def free_for(target: str, data: dict) -> list[dict]:
    return [matching.resource_item(r) for r in data["by_target"].get(target, [])
            if matching.is_free(r) and r["format"] != "programme"]


def programmes_for(targets: list[str], data: dict) -> list[dict]:
    seen = {}
    for t in targets:
        for r in data["by_target"].get(t, []):
            if r["format"] == "programme":
                seen.setdefault(r["url"], matching.resource_item(r))
    return list(seen.values())


GAP_KEYS = ("skill_id", "skill_name", "kind", "your_level", "level_needed", "rated", "ai")
AI_KEYS = ("status", "handoff", "weight", "builder", "measured")


def target_of(row: dict) -> str:
    """The learning-resource target a skill row is filed under."""
    return f"tech:{row['skill_id']}" if row["kind"] == "technology" else f"element:{row['skill_id']}"


def personal_rows(detail: dict) -> tuple[list[dict], list[dict]]:
    """A person's gaps worth a course (MIN_PATH_GAP levels short or more) and the tools they lack."""
    gaps = [{key: gap[key] for key in GAP_KEYS} for gap in detail["gaps"]
            if gap["level_needed"] - gap["your_level"] >= matching.MIN_PATH_GAP]
    tools = [{"skill_id": tool["skill_id"], "skill_name": tool["skill_name"], "kind": "technology", "ai": tool["ai"]}
             for tool in detail["tech_missing"]]
    return gaps, tools


def occupation_rows(occ: dict, data: dict) -> tuple[list[dict], list[dict]]:
    """With no person: the occupation's skills, most important first, and its tools, each with its AI reading."""
    weights = outlook.skill_weights(data, outlook.adoption_of())

    def reading(key: str) -> dict:
        found = weights.get(key, matching.STEADY)
        return {name: found[name] for name in AI_KEYS}
    elements = sorted(data["occ_elements"].get(occ["occ_id"], []), key=lambda e: e[1], reverse=True)
    skills = [{"skill_id": eid, "skill_name": data["elements"][eid]["name"], "kind": kind, "level_needed": need,
               "importance": importance, "ai": reading(eid)} for eid, importance, need, kind in elements]
    tools = [{"skill_id": tid, "skill_name": data["technologies"][tid]["name"], "kind": "technology",
              "ai": reading(tid)} for tid in data["occ_techs"].get(occ["occ_id"], [])]
    return skills, tools


def skill_rows(occ: dict, data: dict, match: dict | None) -> tuple[list[dict], int]:
    """What to build, biggest gap (or importance) first, and how many rows were left off.
    Rows with a checked resource come first so the page opens with links; within each half the
    order is rated skills, then tools, then skills the person did not rate."""
    skills, tools = personal_rows(match["skill_detail"]) if match else occupation_rows(occ, data)
    ordered = [s for s in skills if s.get("rated", True)] + tools + [s for s in skills if not s.get("rated", True)]
    with_links = [row for row in ordered if free_for(target_of(row), data)]
    without = [row for row in ordered if not free_for(target_of(row), data)]
    shown = (with_links + without)[:MAX_SKILLS]
    for row in shown:
        row["resources"] = free_for(target_of(row), data)[:MAX_PER_SKILL]
        row["sdg"] = [{"target": x["target"], "goal_name": x["goal_name"]}
                      for x in matching.element_sdg(row["skill_id"], data)]
    return shown, len(ordered) - len(shown)


def sdg_summary(occ: dict, skills: list[dict], data: dict, total_hours: float) -> list[dict]:
    """SDG targets of the occupation and of the skills on its path, its own first.

    hours: for a target of the occupation itself every hour of the path counts (the whole path
    leads to the job); for one reached only through skills, the hours of the resources that
    teach those skills, each resource once."""
    targets = {}

    def entry(t):
        return targets.setdefault(t["target"], {"target": t["target"], "goal_name": t["goal_name"], "role": None,
                                                "skills": [], "hours": 0.0, "_seen": {}})
    for t in matching.occupation_sdg(occ, data):
        entry(t)["role"] = {"link_strength": t["link_strength"], "rationale": t["rationale"]}
    for s in skills:
        for t in matching.element_sdg(s["skill_id"], data):
            e = entry(t)
            e["skills"].append({"skill_id": s["skill_id"], "skill_name": s["skill_name"],
                                "link_strength": t["link_strength"], "rationale": t["rationale"]})
            for r in s.get("resources", []):
                e["_seen"][r["url"]] = r["hours"] or 0.0
    for e in targets.values():
        e["hours"] = round(total_hours if e["role"] else sum(e.pop("_seen").values()), 1)
        e.pop("_seen", None)

    def order(t):
        return tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in t.split("."))
    return sorted(targets.values(), key=lambda t: (t["role"] is None, -len(t["skills"]), order(t["target"])))


def study_hours(resources: list[dict]) -> tuple[float, int]:
    """Hours of the resources, each link counted once, and how many state no length."""
    unique = {r["url"]: r for r in resources}
    stated = [r["hours"] for r in unique.values() if r["hours"]]
    return round(sum(stated), 1), len(unique) - len(stated)


def page(occ_id: str, data: dict | None = None, match: dict | None = None, hours_per_week: float = 0.0) -> dict | None:
    """The whole learning page of one occupation; with match (matching.detailed), built on that person's gaps.
    hours_per_week 0 means the usual study time (matching.DEFAULT_HOURS_PER_WEEK)."""
    weekly = hours_per_week or matching.DEFAULT_HOURS_PER_WEEK
    if data is None:
        data = matching.load_data()
    occ = data["by_id"].get(occ_id)
    if not occ:
        return None
    field_target = f"field:{occ['field_id']}"
    foundations = list({r["url"]: r for t in (field_target, "all") for r in free_for(t, data)}.values())
    skills, not_shown = skill_rows(occ, data, match)
    hands_on = programmes_for([f"element:{e[0]}" for e in data["occ_elements"].get(occ_id, [])] + [field_target], data)
    total, untimed = study_hours(foundations + [r for s in skills for r in s["resources"]])
    return {
        "role": {"role_id": occ_id, "occ_id": occ_id, "name": occ["title"], "field_id": occ["field_id"],
                 "field_name": occ["field_name"], "job_zone": occ["job_zone"], "mycol": occ["mycol"],
                 "description": occ["description"], "search_title": occ["search_title"]},
        "personal": bool(match),
        "stages": [{"id": "foundations", "resources": foundations}],
        "skills": skills,
        "skills_not_shown": not_shown,
        "hands_on": hands_on,
        "licence": matching.licence(occ, data),
        "sdg": sdg_summary(occ, skills, data, total),
        "total_hours": total,
        "resources_without_hours": untimed,
        "hours_per_week": weekly,
        "weeks": round(total / weekly, 1),
    }
