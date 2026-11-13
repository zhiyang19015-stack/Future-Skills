"""SDG contribution, added up over every student who follows a learning path.

Each browser makes up a random id (no name, email or IP is kept). When a person ticks an item
on a learning path, the browser sends that id, the occupation and the path's hours: planned (every
item with hours) and done (the ticked ones). The latest report per id and occupation replaces the
one before, so ticking and unticking never counts twice.

Two views:
  headline  the three targets the platform itself serves (the proposal's): every learning path is
            free technical education (4.3), job skills (4.4) and a route into a job (8.5), so
            every path counts towards all three.
  targets   the SDG targets each path's learning page lists (learning.sdg_summary: the occupation's
            own targets and those of the skills on its path, data/sdg_map.csv).
Both give how many students follow a path towards the target and their planned and done hours.

Stored in .cache/sdg_tally.json, so a restart keeps it.
"""

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import learning
import matching

ROOT = Path(__file__).resolve().parent.parent
TALLY = ROOT / ".cache" / "sdg_tally.json"
HEADLINE = ["4.3", "4.4", "8.5"]
GOAL_NAMES = {"4": "Quality Education", "8": "Decent Work and Economic Growth"}
WHY = {
    "4.3": "Every course on a path is free, so a student can study without paying fees.",
    "4.4": "A path builds the skills a real job asks for.",
    "8.5": "A path leads towards a job that Malaysia is hiring for.",
}
MAX_HOURS = 2000          # one path never needs more; anything above is a bad report
ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
METHOD = ("Each browser sends an anonymous random id, the occupation and the path's planned and done "
          "hours whenever an item is ticked; the latest report per id and occupation counts once. A path counts "
          "towards SDG 4.3, 4.4 and 8.5 (free courses, job skills, a route into a job) and towards the "
          "targets its learning page lists (data/sdg_map.csv: the occupation's targets and those of the skills "
          "on its path). Done hours add up the hours of the ticked courses.")

_lock = threading.Lock()
_targets: dict[str, list[dict]] = {}


class ImpactError(ValueError):
    pass


def role_targets(role_id: str) -> list[dict]:
    """The SDG targets one occupation's learning path counts towards (cached per occupation)."""
    if role_id not in _targets:
        p = learning.page(role_id)
        if p is None:
            raise ImpactError(f"unknown occ_id '{role_id}'")
        _targets[role_id] = [{"target": t["target"], "goal_name": t["goal_name"]} for t in p["sdg"]]
    return _targets[role_id]


def _read() -> dict:
    try:
        return json.loads(TALLY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(tally: dict) -> None:
    TALLY.parent.mkdir(parents=True, exist_ok=True)
    tmp = TALLY.with_suffix(".tmp")
    tmp.write_text(json.dumps(tally, ensure_ascii=False), encoding="utf-8")
    tmp.replace(TALLY)


def _hours(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= MAX_HOURS:
        raise ImpactError(f"'{name}' must be a number from 0 to {MAX_HOURS}")
    return round(float(value), 1)


def record(learner: str, role_id: str, hours_planned, hours_done, items_done=0) -> dict:
    """Keep one student's latest report for one path; returns the new summary."""
    if not isinstance(learner, str) or not ID_RE.match(learner):
        raise ImpactError("'learner' must be the browser's random id")
    if not isinstance(role_id, str) or not role_id:
        raise ImpactError("'occ_id' is required")
    role_targets(role_id)  # unknown roles are refused
    planned, done = _hours(hours_planned, "hours_planned"), _hours(hours_done, "hours_done")
    if done > planned:
        raise ImpactError("'hours_done' cannot be more than 'hours_planned'")
    if isinstance(items_done, bool) or not isinstance(items_done, int) or not 0 <= items_done <= 500:
        raise ImpactError("'items_done' must be a whole number from 0 to 500")
    with _lock:
        tally = _read()
        tally[f"{learner}|{role_id}"] = {"planned": planned, "done": done, "items": items_done,
                                         "date": datetime.now(timezone.utc).date().isoformat()}
        _write(tally)
    return summary()


def summary() -> dict:
    """Students, paths and hours per SDG target, and in total."""
    with _lock:
        tally = _read()
    roles = {o["occ_id"]: o["title"] for o in matching.static_tables()["occupations"]}
    per: dict[str, dict] = {}
    learners, active, total = set(), set(), {"planned": 0.0, "done": 0.0, "paths": 0}
    by_role: dict[str, dict] = {}
    for key, r in tally.items():
        learner, role_id = key.split("|", 1)
        try:
            ts = role_targets(role_id)
        except ImpactError:
            continue
        learners.add(learner)
        total["paths"] += 1
        if r["done"] > 0 or r.get("items", 0) > 0:
            active.add(learner)
        total["planned"] += r["planned"]
        total["done"] += r["done"]
        role = by_role.setdefault(role_id, {"role_id": role_id, "occ_id": role_id, "name": roles.get(role_id, role_id),
                                            "students": 0, "hours_done": 0.0})
        role["students"] += 1
        role["hours_done"] += r["done"]
        for t in ts:
            e = per.setdefault(t["target"], {"target": t["target"], "goal": t["target"].split(".")[0],
                                             "goal_name": t["goal_name"], "students": set(), "paths": 0,
                                             "hours_planned": 0.0, "hours_done": 0.0})
            e["students"].add(learner)
            e["paths"] += 1
            e["hours_planned"] += r["planned"]
            e["hours_done"] += r["done"]
    out = []
    for e in per.values():
        out.append({**e, "students": len(e["students"]), "hours_planned": round(e["hours_planned"], 1),
                    "hours_done": round(e["hours_done"], 1)})
    out.sort(key=lambda t: (-t["students"], -t["hours_done"], t["target"]))
    headline = [{"target": t, "goal": t.split(".")[0], "goal_name": GOAL_NAMES[t.split(".")[0]], "why": WHY[t],
                 "students": len(learners), "students_studying": len(active), "paths": total["paths"],
                 "hours_planned": round(total["planned"], 1), "hours_done": round(total["done"], 1)} for t in HEADLINE]
    return {
        "students": len(learners),
        "students_studying": len(active),
        "paths": total["paths"],
        "hours_planned": round(total["planned"], 1),
        "hours_done": round(total["done"], 1),
        "headline": headline,
        "targets": out,
        "roles": sorted(({**r, "hours_done": round(r["hours_done"], 1)} for r in by_role.values()),
                        key=lambda r: (-r["students"], -r["hours_done"]))[:10],
        "method": METHOD,
        "since": min((r["date"] for r in tally.values()), default=None),
    }
