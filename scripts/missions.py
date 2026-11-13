"""Career Action Missions: short practice tasks that turn a course into something you can show.

Each mission in data/missions.csv names the skills and tools it trains (O*NET element and
technology ids), the O*NET level a finished mission shows (level), hours, the standard it must
meet (done_when), the product to keep (evidence) and the checked free resources that help.

For one occupation the missions on the person's biggest gaps come first. A mission the person marks
done (with their own evidence link, kept in their browser) counts as "project" evidence: its level
becomes a floor for its skills, the most trusted source in the Skill Transfer Map. The tools it
uses count as tools the person has. We do not check the work: the evidence is the person's own.

The missions are our design, built on the skill and work-activity structure of O*NET; no source
has shown that these particular tasks work, and the page says so.
"""

import csv
import io
from pathlib import Path

import matching

DATA = Path(__file__).resolve().parents[1] / "data"
MAX_SHOWN = 6
_cache = {"key": None, "value": None}


class MissionError(ValueError):
    pass


def catalogue() -> dict:
    path = DATA / "missions.csv"
    key = path.stat().st_mtime_ns
    if _cache["key"] == key:
        return _cache["value"]
    rows = {}
    for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))):
        targets = [t.strip() for t in r["targets"].split(";") if t.strip()]
        rows[r["mission_id"]] = {**r, "targets": targets, "level": float(r["level"]), "hours": float(r["hours"]),
                                 "resource_ids": [x for x in r["resource_ids"].split(";") if x],
                                 "fields": [x for x in r["fields"].split(";") if x]}
    _cache.update(key=key, value=rows)
    return rows


def validate_done(done, data: dict | None = None) -> list[str]:
    if done is None:
        return []
    known = catalogue()
    if not isinstance(done, list) or any(m not in known for m in done):
        raise MissionError("'missions_done' must be a list of mission ids from /api/missions")
    return list(dict.fromkeys(done))


def evidence(done: list[str], data: dict) -> tuple[dict, list[str]]:
    """The skill levels ({element_id: level}) and tools the finished missions show."""
    levels, tools = {}, []
    for mid in done:
        m = catalogue()[mid]
        for t in m["targets"]:
            kind, _, sid = t.partition(":")
            if kind == "element" and sid in data["elements"]:
                levels[sid] = max(levels.get(sid, 0.0), m["level"])
            elif kind == "tech" and sid in data["technologies"]:
                tools.append(sid)
    return levels, list(dict.fromkeys(tools))


def item(m: dict, data: dict) -> dict:
    by_id = {r["resource_id"]: r for r in data["resources"]}
    names = []
    for t in m["targets"]:
        kind, _, sid = t.partition(":")
        if kind == "element" and sid in data["elements"]:
            names.append(data["elements"][sid]["name"])
        elif kind == "tech" and sid in data["technologies"]:
            names.append(data["technologies"][sid]["name"])
    return {"mission_id": m["mission_id"], "title": m["title"], "skills": names, "targets": m["targets"],
            "level": m["level"], "hours": m["hours"], "done_when": m["done_when"], "evidence": m["evidence"],
            "resources": [matching.resource_item(by_id[r]) for r in m["resource_ids"] if r in by_id]}


def for_occupation(occ_id: str, profile: dict, data: dict, done: list[str] | None = None,
                   limit: int = MAX_SHOWN) -> dict:
    """The missions on the person's gaps for one occupation, the biggest gaps first."""
    occ = data["by_id"].get(occ_id)
    if occ is None:
        raise MissionError(f"unknown occ_id '{occ_id}'")
    profile = matching.prepare(profile, data)
    detail = matching.skill_score(profile, occ, data, None, detail=True)
    gap_points = {f"element:{g['skill_id']}": g["gap_points"] for g in detail["gaps"]}
    for t in detail["tech_missing"]:
        gap_points[f"tech:{t['skill_id']}"] = 1.0
    done = set(done or [])
    scored = []
    for m in catalogue().values():
        hits = [t for t in m["targets"] if t in gap_points]
        weight = sum(gap_points[t] for t in hits)
        if hits or occ["field_id"] in m["fields"]:
            scored.append((-(weight + (0.5 if occ["field_id"] in m["fields"] else 0)), m["mission_id"], m, hits))
    scored.sort(key=lambda x: (x[0], x[1]))
    open_ = [dict(item(m, data), gaps=len(hits), done=m["mission_id"] in done) for _, _, m, hits in scored]
    shown = [m for m in open_ if not m["done"]][:limit]
    finished = [m for m in open_ if m["done"]] + [item(catalogue()[x], data) | {"done": True, "gaps": 0}
                                                  for x in done if x not in {m["mission_id"] for m in open_}]
    return {"occ_id": occ_id, "title": occ["title"], "missions": shown, "done": finished,
            "hours": sum(m["hours"] for m in shown), "note": __doc__.strip().split("\n\n")[-1]}


def all_missions(data: dict) -> list[dict]:
    return [item(m, data) for m in catalogue().values()]
