"""The skills check: rate yourself against O*NET's own examples of each level.

For every skill and knowledge area O*NET gives three example tasks, at a low, a middle and a
high level of its 0-7 scale (data/elements.csv, from level_scale_anchors). For writing:

    level 2  "Write down a guest's order at a restaurant"
    level 4  "Write an email to staff outlining new directives"
    level 6  "Write a novel for publication"

The person picks the hardest example they can already do, or "not yet". That is their level,
on the same scale O*NET rates every occupation with, so matching.py can compare them directly.

plan() picks what to ask: the skills and knowledge areas that matter most in the fields the
person chose (mean O*NET importance over the fields' occupations), SKILLS_ASKED skills and
KNOWLEDGE_ASKED knowledge areas, so the check takes a few minutes. The rest can be added.
A self-rating is a self-rating: the page says so, and the CV and current job can raise a level
but never lower one.
"""

import matching

SKILLS_ASKED = 12
KNOWLEDGE_ASKED = 8
NOT_YET = 0.0


class SkillCheckError(ValueError):
    pass


def importance_by_element(data: dict, fields: list[str] | None) -> dict:
    """Mean importance of each element over the occupations of the given fields (all if none)."""
    wanted = set(fields or [])
    sums, counts = {}, {}
    for occ in data["occupations"]:
        if wanted and occ["field_id"] not in wanted:
            continue
        for eid, imp, _, _ in data["occ_elements"].get(occ["occ_id"], []):
            sums[eid] = sums.get(eid, 0.0) + imp
            counts[eid] = counts.get(eid, 0) + 1
    return {e: sums[e] / counts[e] for e in sums}


def question(e: dict) -> dict:
    options = [{"level": NOT_YET, "text": None}]
    for part in ("low", "mid", "high"):
        if e[f"anchor_{part}"]:
            options.append({"level": float(e[f"anchor_{part}_level"]), "text": e[f"anchor_{part}"]})
    return {"element_id": e["element_id"], "name": e["name"], "kind": e["kind"], "group": e["group"],
            "description": e["description"], "options": options}


def plan(data: dict, fields: list[str] | None = None, everything: bool = False) -> dict:
    """The questions to ask, most important first, and the rest by name."""
    for f in fields or []:
        if f not in data["fields"]:
            raise SkillCheckError(f"unknown field '{f}'")
    weight = importance_by_element(data, fields)
    ranked = sorted(data["elements"].values(), key=lambda e: (-weight.get(e["element_id"], 0), e["name"]))
    skills = [e for e in ranked if e["kind"] == "skill"]
    knowledge = [e for e in ranked if e["kind"] == "knowledge"]
    asked = skills + knowledge if everything else skills[:SKILLS_ASKED] + knowledge[:KNOWLEDGE_ASKED]
    ids = {e["element_id"] for e in asked}
    return {"fields": fields or [], "questions": [question(e) for e in asked],
            "more": [{"element_id": e["element_id"], "name": e["name"], "kind": e["kind"]}
                     for e in ranked if e["element_id"] not in ids],
            "scale": "O*NET level 0-7; each example is one of O*NET's level anchors",
            "source": {"name": matching.read_csv("elements.csv")[0]["source_name"],
                       "url": matching.read_csv("elements.csv")[0]["source_url"]}}


def levels(answers, data: dict) -> dict:
    """Check a page's answers {element_id: level} and return them as floats."""
    if not isinstance(answers, dict):
        raise SkillCheckError("'skills' must be an object of element_id -> level 0-7")
    out = {}
    for eid, value in answers.items():
        if eid not in data["elements"]:
            raise SkillCheckError(f"unknown skill or knowledge area '{eid}'")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 7:
            raise SkillCheckError(f"'skills.{eid}' must be a number from 0 to 7")
        out[eid] = float(value)
    return out
