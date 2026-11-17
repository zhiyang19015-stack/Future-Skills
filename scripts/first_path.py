"""Check 10, the first-time path: how many clicks and how many required answers a first-time
visitor needs from the home page to a ranked list, and from there to a learning plan.

How it is counted (no browser, no user test):
  * Each path is written below as the steps a visitor takes: "click" (a button or link),
    "input" (an answer they must give: one tap that is also a click) and "see" (what appears
    with no further action). Clicks = click + input steps; required answers = input steps.
  * Every step names the page file and the function that draws it, and a piece of markup that
    must be in that function's source (the button's href or data-act). If a step's markup is
    gone, the path is reported broken, so a redesign cannot keep an old count by accident.
  * The answers are then sent to the real API: a blank profile must get no ranking; the path's
    answers must get a ranking and a learning plan with at least one resource. This is run for
    every one of the fields, so "one tap is enough" is tested, not assumed.
Not measured here: time in minutes, whether a person finds the button without being told,
and anything the browser draws (layout, scrolling). Those need people or a browser.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "static"
sys.path.insert(0, str(ROOT / "src"))

import main  # noqa: E402

# The paths a first-time visitor can take. Keep each needle to what the code really draws.
PATHS = {
    "own": {
        "about": "own answers, through Quick start",
        "steps": [
            {"do": "click", "file": "app.js", "fn": "PAGES.home", "needle": ['href="#/quick"', '"matches" : "quick"'],
             "what": "Home: the button to build a profile (opens Quick start)"},
            {"do": "input", "file": "you.js", "fn": "fieldsCard", "needle": 'data-act="field"',
             "what": "Quick start: tap one field you like"},
            {"do": "see", "file": "quick.js", "fn": "quickResults", "needle": 'quick.r.matches', "what": "ranked occupations",
             "reaches": "ranking"},
            {"do": "see", "file": "quick.js", "fn": "quickResults", "needle": 'quick.r.plan', "what": "a free learning plan",
             "reaches": "plan"},
        ],
    },
    "demo": {
        "about": "a fictional demo person",
        "steps": [
            {"do": "click", "file": "app.js", "fn": "personaCards", "needle": 'data-act="demo"',
             "what": "Home: tap a fictional demo person"},
            {"do": "see", "file": "explore.js", "fn": "PAGES.matches", "needle": "matchCard(", "what": "ranked occupations",
             "reaches": "ranking"},
            {"do": "click", "file": "explore.js", "fn": "matchCard", "needle": 'href="#/pathway/', "what": "Matches: open the plan"},
            {"do": "see", "file": "explore.js", "fn": "PAGES.pathway", "needle": "resourceRow(", "what": "the learning plan",
             "reaches": "plan"},
        ],
    },
}


def source_of(file: str, fn: str) -> str:
    """The source of one top-level function (or PAGES.x = async ...) in a page file."""
    text = (STATIC / file).read_text(encoding="utf-8")
    start = re.search(rf"^(?:async )?(?:function {re.escape(fn)}\(|{re.escape(fn)} = )", text, re.M)
    if not start:
        return ""
    end = re.search(r"^}", text[start.end():], re.M)
    return text[start.start(): start.end() + (end.end() if end else len(text))]


def walk(path: dict) -> dict:
    clicks = inputs = 0
    at, broken = {}, []
    for s in path["steps"]:
        needles = s["needle"] if isinstance(s["needle"], list) else [s["needle"]]
        if not any(n in source_of(s["file"], s["fn"]) for n in needles):
            broken.append(f"{s['file']} {s['fn']}: {' or '.join(needles)}")
        if s["do"] in ("click", "input"):
            clicks += 1
        if s["do"] == "input":
            inputs += 1
        if s.get("reaches"):
            at[s["reaches"]] = {"clicks": clicks, "inputs": inputs}
    return {"about": path["about"], "steps": [f"{s['do']}: {s['what']}" for s in path["steps"]],
            "to_ranking": at.get("ranking"), "to_plan": at.get("plan"), "broken": broken}


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    res = main.dispatch(method, path, json.dumps(body).encode("utf-8") if body is not None else b"")
    return res.status, json.loads(res.body)


def api_check() -> dict:
    """A blank profile gets no ranking; one liked field gets a ranking and a plan, for each field."""
    _, blank = call("POST", "/api/match", {})
    blank_ranked = bool([m for m in blank.get("results", []) if main.listed(m)])
    fields = [f["field_id"] for f in call("GET", "/api/fields")[1]]
    ok = []
    for fid in fields:
        body = {"kind": "student", "education_job_zone": 4, "technologies": [], "fields": {fid: 100}, "scenario": "moderate"}
        status, m = call("POST", "/api/match", {**body, "top": 12})
        moves = [x for x in m.get("results", []) if main.listed(x)] if status == 200 else []
        if not moves:
            continue
        status, plan = call("POST", "/api/learn", {**body, "occ_id": moves[0]["occ_id"]})
        resources = sum(len(s["resources"]) for s in plan.get("stages", []) + plan.get("skills", [])) if status == 200 else 0
        if resources:
            ok.append(fid)
    return {"blank_ranked": blank_ranked, "fields": len(fields), "one_tap_ok": len(ok)}


def run() -> dict:
    paths = {k: walk(p) for k, p in PATHS.items()}
    api = api_check()
    own = paths["own"]
    return {"paths": paths, "api": api,
            "pass": not any(p["broken"] for p in paths.values()) and not api["blank_ranked"]
            and api["one_tap_ok"] == api["fields"] and own["to_plan"] is not None}


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, ensure_ascii=False))
