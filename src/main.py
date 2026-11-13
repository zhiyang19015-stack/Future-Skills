"""Future Skills: the web server and its JSON API. Run it with:  python src/main.py

Python standard library only, so it runs on any Python 3.10+ with nothing to install.

The six steps of the app and the endpoints behind them:

    1 You       GET  /api/fields, /api/occupations, /api/technologies, /api/profiles
                GET  /api/questionnaire, POST /api/questionnaire/score     the 36 interest statements
                GET  /api/skillcheck?fields=29,31[&all=1]                 the skills check questions
                POST /api/cv/summary   {"text"} or {"docx_base64"}        tools, education, subjects, job titles
    2 Radar     GET  /api/radar?scenario=                                every field and occupation's outlook
                GET  /api/occupations/<occ_id>?scenario=                 one occupation in full
    3 Matches   POST /api/match            profile -> field fit and the ranked occupations with every part
                POST /api/explain          same body + occ_id -> why this score, and what would raise it
                POST /api/jobad            a job ad's text -> the tools it asks for, which you have
    4 Pathway   POST /api/learn            same body + occ_id -> free resources on the person's gaps
                GET  /api/learn/<occ_id>   the occupation's own list
    5 SDG       GET  /api/sdg/summary, POST /api/sdg/record             the anonymous total
    6 Futures   POST /api/futures          the three scenarios side by side
                GET  /api/whatif, POST /api/whatif                      simulated news and changed numbers
    Team        GET  /api/team?scenario=   the fictional team through the same engine: jobs, moves,
                POST /api/team             skill-gap heatmap, training groups, hours, SDG (or your own team)
    Sources     GET  /api/sources          every source, its dates and licence; the model's constants
                POST /api/update           start "Update data"; GET for its status

A profile (the body of /api/match, /api/explain, /api/learn, /api/futures, /api/whatif) has any of:
    kind, education_job_zone (1-5), study_levels (0-2: levels above it the person would study for),
    current_occupation, fields {field_id: 0-100},
    interest_answers [36 x 1-5], skills {element_id: 0-7}, cv_skills {element_id: 0-7},
    technologies [tech_id], cv_fields {field_id: 0-100}, cv_why {field_id: text},
    hours_per_week (1-40), sdg_goals ["3", ...], scenario (slow | moderate | fast) or adoption (0-0.9),
    trend_changes (a what-if, scripts/whatif.py)
or "profile_id" for one of the fictional demo people.

PORT sets the port (default 8080). The update job also runs by itself once the fetched data is
AUTO_UPDATE_DAYS old (default 7; 0 turns it off), checked every hour.
"""

import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
MODULES = ROOT / "scripts"        # the data and model code this server runs
STATIC = HERE / "static"
sys.path.insert(0, os.fspath(MODULES))

import ai_exposure  # noqa: E402
import cv_reader  # noqa: E402
import demand  # noqa: E402
import evidence  # noqa: E402
import explain  # noqa: E402
import impact  # noqa: E402
import interest  # noqa: E402
import learning  # noqa: E402
import matching  # noqa: E402
import outlook  # noqa: E402
import releases  # noqa: E402
import skillcheck  # noqa: E402
import team  # noqa: E402
import whatif  # noqa: E402

MAX_BODY = 4_000_000          # room for a base64 .docx CV
MAX_AD_CHARS = 20_000
UPDATE_TIMEOUT_S = 600
AUTO_UPDATE_DAYS = float(os.getenv("AUTO_UPDATE_DAYS", "7"))
AUTO_CHECK_S = 3600
RADAR_LIST = 15               # rising and declining occupations listed on the Radar
RADAR_TOOLS = 120             # the most-listed tools on the Radar's skills tab
KINDS = ("student", "working", "switcher")
MYCOL_URL = ("https://www.talentcorp.com.my/images/uploads/publication/205/"
             "MyMahir-MyCOL-20242025-Brochure-1773377416.pdf")

_update_running = threading.Lock()
_update = {"status": "idle", "started": None, "finished": None, "trigger": None, "returncode": None, "log": ""}


def load_env_file(path: Path = ROOT / ".env") -> None:
    """KEY=value lines from a local .env; values already in the environment (Codespaces secrets) win."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#") and value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# --- a small router: path patterns with <name> segments ------------------------------------------

class Refused(Exception):
    """A request the API refuses; its text goes back to the caller with HTTP 400."""


class Request:
    """One request as a handler sees it: method, path, query arguments and the raw body."""

    def __init__(self, method: str, url: str, raw: bytes = b""):
        parts = urlsplit(url)
        self.method, self.path, self.body = method, parts.path, raw
        self.args = dict(parse_qsl(parts.query))

    def json(self) -> dict:
        try:
            parsed = json.loads(self.body) if self.body else None
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        raise Refused("send a JSON object")


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str


def reply(payload=None, status: int = 200, **fields) -> Response:
    text = json.dumps(fields if payload is None else payload, ensure_ascii=False)
    return Response(status, text.encode("utf-8"), "application/json; charset=utf-8")


ROUTES: list[tuple[str, tuple[str, ...], str, Callable]] = []


def route(method: str, pattern: str):
    """Register a handler for METHOD pattern; a <name> segment takes any one segment, passed on by name."""
    def register(handler):
        ROUTES.append((method, tuple(pattern.strip("/").split("/")), pattern, handler))
        return handler
    return register


def path_values(pattern: tuple[str, ...], path: str) -> dict | None:
    """The <name> values when the path fits the pattern, else None."""
    parts = path.strip("/").split("/")
    if len(parts) != len(pattern):
        return None
    values = {}
    for want, got in zip(pattern, parts):
        if want.startswith("<") and want.endswith(">"):
            if not got:
                return None
            values[want[1:-1]] = unquote(got)
        elif want != got:
            return None
    return values


STATIC_TYPES = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".txt": "text/plain",
                ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}


def static_file(relative: str) -> Response:
    """A file from src/static/, and never one outside it."""
    target = (STATIC / relative).resolve()
    if STATIC not in target.parents or not target.is_file():
        return reply(error="not found", status=404)
    kind = STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
    if kind.startswith("text/") or kind in ("application/javascript", "application/json", "image/svg+xml"):
        kind = f"{kind}; charset=utf-8"
    return Response(200, target.read_bytes(), kind)


def dispatch(method: str, url: str, raw: bytes = b"") -> Response:
    """Answer one request; the HTTP server and the tests both call this."""
    request = Request(method, url, raw)
    if request.path.startswith("/static/") and method == "GET":
        return static_file(request.path[len("/static/"):])
    other_method = False
    for verb, pattern, _, handler in ROUTES:
        values = path_values(pattern, request.path)
        if values is None:
            continue
        if verb != method:
            other_method = True
            continue
        try:
            return handler(request, **values)
        except Refused as problem:
            return reply(error=str(problem), status=400)
    if other_method:
        return reply(error="method not allowed", status=405)
    return reply(error="not found", status=404)


read_csv = matching.read_csv  # one reader for everything in data/


# --- the person -------------------------------------------------------------------------------------

def sample_profiles() -> list[dict]:
    return json.loads((DATA / "sample_profiles.json").read_text(encoding="utf-8"))


def scores_0_100(given, name: str, keys: set) -> dict:
    if not isinstance(given, dict) or not set(given) <= keys:
        raise Refused(f"'{name}' must map field ids to numbers 0-100")
    for v in given.values():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100:
            raise Refused(f"'{name}' must map field ids to numbers 0-100")
    return {k: float(v) for k, v in given.items()}


def build_profile(body: dict, data: dict) -> dict:
    """A request body as a matching profile, every id and number checked."""
    if "profile_id" in body:
        found = next((p for p in sample_profiles() if p["profile_id"] == body["profile_id"]), None)
        if found is None:
            raise Refused(f"unknown profile_id '{body['profile_id']}'")
        return matching.with_interest(dict(found))
    fields = set(data["fields"])
    profile = {"profile_id": "request", "kind": body.get("kind", "student")}
    if profile["kind"] not in KINDS:
        raise Refused(f"'kind' must be one of {list(KINDS)}")
    zone = body.get("education_job_zone", matching.DEFAULT_JOB_ZONE)
    if isinstance(zone, bool) or zone not in range(1, 6):
        raise Refused("'education_job_zone' must be a whole number from 1 to 5")
    profile["education_job_zone"] = zone
    study = body.get("study_levels", 0)
    if isinstance(study, bool) or study not in range(matching.MAX_STUDY_LEVELS + 1):
        raise Refused(f"'study_levels' must be a whole number from 0 to {matching.MAX_STUDY_LEVELS}")
    profile["study_levels"] = study
    current = body.get("current_occupation")
    if current is not None:
        if current not in data["by_id"]:
            raise Refused(f"unknown current_occupation '{current}'")
        profile["current_occupation"] = current
    for key in ("fields", "cv_fields"):
        if body.get(key) is not None:
            profile[key] = scores_0_100(body[key], key, fields)
    if isinstance(body.get("cv_why"), dict):
        profile["cv_why"] = {k: str(v)[:200] for k, v in body["cv_why"].items() if k in fields}
    if body.get("interest_answers") is not None:
        try:
            profile["interest"] = interest.score(body["interest_answers"])
        except interest.AnswerError as error:
            raise Refused(str(error)) from None
    given = {}
    for key in ("skills", "cv_skills"):
        try:
            given[key] = skillcheck.levels(body.get(key) or {}, data)
        except skillcheck.SkillCheckError as error:
            raise Refused(str(error).replace("'skills", f"'{key}")) from None
    # the CV and the skills check describe the same person: the higher level counts
    profile["skills"] = {e: max(given["skills"].get(e, 0.0), given["cv_skills"].get(e, 0.0))
                         for e in given["skills"].keys() | given["cv_skills"].keys()}
    techs = body.get("technologies", [])
    if not isinstance(techs, list) or any(t not in data["technologies"] for t in techs):
        raise Refused("'technologies' must be a list of tech_ids from /api/technologies")
    profile["technologies"] = list(dict.fromkeys(techs))
    return profile


def scenario_of(args: dict) -> tuple[str | None, float]:
    """The scenario id (None for a slider value) and the adoption value of a request."""
    if args.get("adoption") is not None:
        try:
            value = float(args["adoption"])
        except (TypeError, ValueError):
            raise Refused("'adoption' must be a number") from None
        if isinstance(args["adoption"], bool) or not 0 <= value <= outlook.ADOPTION_MAX:
            raise Refused(f"'adoption' must be a number from 0 to {outlook.ADOPTION_MAX}")
        return None, value
    scenario = args.get("scenario", outlook.DEFAULT_SCENARIO)
    if scenario not in outlook.SCENARIOS:
        raise Refused(f"'scenario' must be one of {list(outlook.SCENARIOS)}")
    return scenario, outlook.adoption_of(scenario)


def scenario_info(scenario: str | None, adoption: float) -> dict:
    if scenario:
        return {"id": scenario, **outlook.SCENARIOS[scenario]}
    return {"id": "custom", "name": "Your own setting", "adoption": adoption,
            "description": f"By {outlook.HORIZON_YEAR}, {adoption:.0%} of the gap between today's AI use and using it "
                           "wherever it can be has closed."}


def scenario_list() -> list[dict]:
    return [{"id": k, **v} for k, v in outlook.SCENARIOS.items()]


def what_if(body: dict, required: bool = False) -> dict | None:
    try:
        changes = whatif.validate(body.get("trend_changes"))
    except whatif.WhatIfError as error:
        raise Refused(str(error)) from None
    if required and not whatif.changed(changes):
        raise Refused("'trend_changes' must change at least one input")
    return changes if whatif.changed(changes) else None


def request_context(body: dict, required_changes: bool = False) -> tuple[dict, dict, str | None, float, dict | None]:
    """The data (changed when the body sends a what-if), profile, scenario and adoption of a request."""
    data = matching.load_data()
    changes = what_if(body, required_changes)
    if changes and not required_changes:
        data = whatif.changed_data(data, changes)
    profile = build_profile(body, data)
    hours = body.get("hours_per_week", profile.get("hours_per_week", matching.DEFAULT_HOURS_PER_WEEK))
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 1 <= hours <= 40:
        raise Refused("'hours_per_week' must be a number from 1 to 40")
    goals = body.get("sdg_goals", profile.get("sdg_goals", []))
    if not isinstance(goals, list) or not all(str(g) in {str(i) for i in range(1, 18)} for g in goals):
        raise Refused("'sdg_goals' must be a list of UN goal numbers 1-17")
    profile = matching.prepare({**profile, "hours_per_week": hours, "sdg_goals": [str(g) for g in goals],
                                "show_restricted": body.get("show_restricted") is True}, data)
    scenario, adoption = scenario_of(body)
    return data, profile, scenario, adoption, changes


def data_version(data: dict, changes: dict | None = None) -> dict:
    """Which data a result used, so the page can tell when "Update data" changed it."""
    h = hashlib.sha256()
    for name in ("demand_inputs.csv", "aei/source.json", "occupations.csv"):
        path = DATA / name
        if path.exists():
            h.update(path.read_bytes())
    if changes:
        h.update(json.dumps(changes, sort_keys=True).encode("utf-8"))
    src = data["ai"]["source"]["economic_index"]
    return {"id": h.hexdigest()[:12], "computed_date": data["demand"]["computed_date"], "what_if": bool(changes),
            "ai_usage_period": data["ai"]["context"]["latest"], "ai_usage_release": src["release_date"]}


# --- step 1: you ------------------------------------------------------------------------------------

@route("GET", "/")
def web_app(req):
    return static_file("index.html")


@route("GET", "/api")
def api_index(req):
    return reply(name="Future Skills API", endpoints=sorted({p for _, _, p, _ in ROUTES if p.startswith("/api")}))


@route("GET", "/api/health")
def health(req):
    return reply({"status": "ok"})


@route("GET", "/api/fields")
def fields(req):
    data = matching.static_tables()
    counts = {}
    for o in data["occupations"]:
        counts[o["field_id"]] = counts.get(o["field_id"], 0) + 1
    return reply([{k: f[k] for k in ("field_id", "name_en", "name_ms", "name_zh", "about_en", "about_ms", "about_zh")}
                  | {"occupations": counts.get(f["field_id"], 0)} for f in data["fields"].values()])


@route("GET", "/api/occupations")
def occupations(req):
    """Every occupation in a compact form (for search on the page); ?field= narrows it."""
    data = matching.static_tables()
    field = req.args.get("field")
    keep = ("occ_id", "title", "field_id", "job_zone", "mycol", "riasec", "search_title")
    return reply([{k: o[k] for k in keep} for o in data["occupations"] if not field or o["field_id"] == field])


@route("GET", "/api/technologies")
def technologies(req):
    data = matching.static_tables()
    return reply([{"tech_id": t["tech_id"], "name": t["name"], "category": t["category"],
                   "occupations": int(t["occupations"])} for t in data["technologies"].values()])


@route("GET", "/api/elements")
def elements(req):
    return reply(list(matching.static_tables()["elements"].values()))


@route("GET", "/api/profiles")
def profiles(req):
    keep = ("profile_id", "name", "kind", "story", "current_occupation", "education_job_zone")
    return reply([{k: p.get(k) for k in keep} for p in sample_profiles()])


@route("GET", "/api/questionnaire")
def questionnaire(req):
    return reply(interest.item_bank())


@route("POST", "/api/questionnaire/score")
def questionnaire_score(req):
    try:
        return reply(interest.score(req.json().get("answers")))
    except interest.AnswerError as error:
        raise Refused(str(error)) from None


@route("GET", "/api/skillcheck")
def skill_check(req):
    fields_ = [f for f in (req.args.get("fields") or "").split(",") if f]
    try:
        return reply(skillcheck.plan(matching.static_tables(), fields_, everything=req.args.get("all") == "1"))
    except skillcheck.SkillCheckError as error:
        raise Refused(str(error)) from None


@route("POST", "/api/cv/summary")
def cv_summary(req):
    """Read a CV for this request only; it is never stored."""
    try:
        return reply(cv_reader.summarise(req.json(), matching.static_tables()))
    except cv_reader.CVReadError as error:
        raise Refused(str(error)) from None


# --- step 2: radar ----------------------------------------------------------------------------------

def occupation_outlooks(occ: dict, data: dict) -> dict:
    return {k: outlook.role_outlook(occ, data, v["adoption"]) for k, v in outlook.SCENARIOS.items()}


def radar_payload(data: dict, scenario: str | None, adoption: float) -> dict:
    layer, ref = data["ai"], data["ai"]["reference"]
    rows, by_field = [], {}
    for occ in data["occupations"]:
        o = outlook.role_outlook(occ, data, adoption)
        ai = layer["roles"].get(occ["occ_id"], {})
        rows.append({"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"], "mycol": occ["mycol"],
                     "job_zone": occ["job_zone"], "demand": o["demand"], "ai_share": o["ai_share"],
                     "ai_share_low": o["ai_share_low"], "ai_share_high": o["ai_share_high"], "outlook": o["outlook"],
                     "change": o["change"], "status": o["status"], "thin_evidence": ai.get("thin_evidence", False)})
        by_field.setdefault(occ["field_id"], []).append(rows[-1])
    fields = []
    for fid, f in data["fields"].items():
        mine = by_field.get(fid, [])
        use = layer["context"]["fields"].get(fid, {})
        fields.append({"field_id": fid, "name": f["name_en"], "occupations": len(mine),
                       "ai_share": round(sum(r["ai_share"] for r in mine) / len(mine), 1) if mine else None,
                       "outlook": round(sum(r["outlook"] for r in mine) / len(mine), 1) if mine else None,
                       "demand": round(sum(r["demand"] for r in mine) / len(mine), 1) if mine else None,
                       "statuses": {s: sum(1 for r in mine if r["status"] == s) for s in ("rising", "steady", "declining")},
                       "usage": use.get("usage"), "automation": use.get("automation")})
    fields.sort(key=lambda f: -(f["ai_share"] or 0))
    weights = outlook.skill_weights(data, adoption)
    named = {k: outlook.skill_weights(data, v["adoption"]) for k, v in outlook.SCENARIOS.items()}
    tool_use = {t: int(data["technologies"][t]["occupations"]) for t in data["technologies"]}
    top_tools = set(sorted(tool_use, key=lambda t: -tool_use[t])[:RADAR_TOOLS])
    skills = []
    for sid, s in layer["skills"].items():
        if s["skill_type"] == "technology" and sid not in top_tools:
            continue
        w = weights.get(sid, matching.STEADY)
        skills.append({"skill_id": sid, "skill_name": s["skill_name"], "skill_type": s["skill_type"],
                       "handoff": s["handoff"], "handoff_my": s["handoff_my"], "basis": s["basis"],
                       "evidence": s["evidence"], "builder": s["builder"], "note": s["note"], "weight": w["weight"],
                       "status": w["status"], "statuses": {k: named[k].get(sid, matching.STEADY)["status"] for k in named},
                       "occupations": tool_use.get(sid), "changed": s["changed"],
                       "sdg": [x["target"] for x in matching.element_sdg(sid, data)]})
    topics = [{**{k: t[k] for k in ("topic", "usage_pct", "usage_pct_previous", "usage_pct_my", "work_pct", "handoff",
                                    "handoff_measured", "builder", "changed")},
               "skills": [data["technologies"][s]["name"] for s in t["skills"] if s in data["technologies"]][:12],
               "status": outlook.skill_weight({"handoff": t["handoff"], "builder": t["builder"]}, adoption, ref)["status"]
               if t["handoff"] is not None else "steady"} for t in layer["topics"].values()]
    # the biggest moves first; among equal moves, the higher (or lower) outlook
    # only occupations the model moves up: measured to hand less to AI than average, or building AI
    rising = sorted((r for r in rows if r["status"] == "rising"),
                    key=lambda r: (-r["change"], -r["outlook"]))[:RADAR_LIST]
    declining = sorted(rows, key=lambda r: (r["change"], r["outlook"]))[:RADAR_LIST]
    return {"scenario": scenario_info(scenario, adoption), "scenarios": scenario_list(),
            "horizon_year": outlook.HORIZON_YEAR, "context": layer["context"], "reference": ref,
            "fields": fields, "rising": rising, "declining": declining,
            "occupations": [[r["occ_id"], r["title"], r["field_id"], r["outlook"], r["change"], r["status"],
                             r["ai_share"], r["demand"], r["mycol"]] for r in rows],
            "occupation_columns": ["occ_id", "title", "field_id", "outlook", "change", "status", "ai_share", "demand",
                                   "mycol"],
            "counts": {s: sum(1 for r in rows if r["status"] == s) for s in ("rising", "steady", "declining")},
            "skills": sorted(skills, key=lambda s: (-s["weight"], s["skill_name"])),
            "topics": sorted(topics, key=lambda t: -(t["handoff"] or 0)),
            "demand": {"groups": list(data["demand"]["groups"].values()), "momentum": data["demand"]["momentum"],
                       "wages": data["demand"]["wages"]},
            "sources": {"ai_usage": layer["source"]["economic_index"], "task_coverage": layer["source"]["labor_market_impacts"],
                        "tasks": layer["source"]["onet"], "demand_computed_date": data["demand"]["computed_date"]},
            "what_if": layer["changed"] or data["demand"]["changed"]}


@route("GET", "/api/radar")
def radar(req):
    scenario, adoption = scenario_of(req.args)
    return reply(radar_payload(matching.load_data(), scenario, adoption))


@route("GET", "/api/occupations/<occ_id>")
def occupation_detail(req, occ_id: str):
    data = matching.load_data()
    occ = data["by_id"].get(occ_id)
    if occ is None:
        return reply(error="not found", status=404)
    _, adoption = scenario_of(req.args)
    weights = outlook.skill_weights(data, adoption)
    skills, techs = [], []
    for eid, imp, level, kind in sorted(data["occ_elements"].get(occ_id, []), key=lambda x: -x[1]):
        w = weights.get(eid, matching.STEADY)
        skills.append({"skill_id": eid, "skill_name": data["elements"][eid]["name"], "kind": kind, "importance": imp,
                       "level": level, "status": w["status"], "handoff": w["handoff"]})
    for tid in data["occ_techs"].get(occ_id, []):
        w = weights.get(tid, matching.STEADY)
        techs.append({"skill_id": tid, "skill_name": data["technologies"][tid]["name"], "status": w["status"],
                      "handoff": w["handoff"]})
    tasks = sorted(data["ai"]["tasks_by_occ"].get(occ_id, []), key=lambda t: (-t["ai_share"], -(t["importance"] or 0)))
    keep = ("task_id", "task", "task_type", "importance", "ai_share", "ai_share_low", "ai_share_high", "automation_pct",
            "hours_alone", "minutes_with_ai", "usage_pct", "emerging")
    related = [{"occ_id": r, "title": data["by_id"][r]["title"], "field_id": data["by_id"][r]["field_id"]}
               for r in data["related"].get(occ_id, [])[:8]]
    d = data["demand"]["occupations"].get(occ_id)
    return reply(occupation={k: occ[k] for k in ("occ_id", "title", "description", "field_id", "field_name", "job_zone",
                                                 "riasec", "isco", "isco_title", "isco_basis", "masco_major", "mycol",
                                                 "mycol_occupation", "search_title")},
                 titles=[t["title"] for t in data["titles"].get(occ_id, [])][:10],
                 outlook=outlook.role_outlook(occ, data, adoption), outlooks=occupation_outlooks(occ, data),
                 ai=matching.occupation_ai(occ_id, data), demand=d, tasks=[{k: t[k] for k in keep} for t in tasks],
                 skills=skills, technologies=techs, sdg=matching.occupation_sdg(occ, data),
                 licence=matching.licence(occ, data), restriction=matching.restriction(occ, data), related=related, source=data["ai"]["source"],
                 evidence=evidence.occupation_grade(occ, data))


# --- step 3: matches --------------------------------------------------------------------------------

def listed(m: dict) -> bool:
    """An occupation in the person's list of moves: open at their education level, not restricted in
    Malaysia (unless asked for) and not the job they do now."""
    return not (matching.UNLISTED_FLAGS | {"current_occupation"}) & set(m["flags"])


VERDICT_TOP = 3               # how far down the list the scenarios are compared for the one-line verdict


def scenario_ranks(profile: dict, data: dict, wanted: set) -> tuple[dict, dict, dict]:
    """Rank and total of the wanted occupations under every named scenario, among the listed ones,
    and the first VERDICT_TOP of each scenario's list."""
    ranks, totals, tops = {}, {}, {}
    for name in outlook.SCENARIOS:
        order = [m for m in matching.rank(profile, data, scenario=name) if listed(m)]
        tops[name] = [{"occ_id": m["occ_id"], "title": m["title"], "total": m["total"],
                       "ai_share": m["outlook"]["ai_share"]} for m in order[:VERDICT_TOP]]
        for i, m in enumerate(order):
            if m["occ_id"] in wanted:
                ranks.setdefault(m["occ_id"], {})[name] = i + 1
                totals.setdefault(m["occ_id"], {})[name] = m["total"]
    return ranks, totals, tops


def scenario_verdict(tops: dict, reference: dict) -> dict | None:
    """What the named scenarios do to the top of one person's list, as one of three plain cases:
    "top" the first occupation differs, "top3" the first holds but the first three do not, "same"
    the first three hold. A list that holds is an answer too, so the verdict also says how far the
    scores moved; nothing here is tuned to make a list change."""
    names = [n for n in outlook.SCENARIOS if tops.get(n)]
    if len(names) < 2:
        return None
    slow, fast = names[0], names[-1]
    firsts = {tops[n][0]["occ_id"] for n in names}
    orders = {tuple(m["occ_id"] for m in tops[n]) for n in names}
    fast_totals = {m["occ_id"]: m["total"] for m in tops[fast]}
    moved = [abs(fast_totals[m["occ_id"]] - m["total"]) for m in tops[slow] if m["occ_id"] in fast_totals]
    return {"kind": "top" if len(firsts) > 1 else "top3" if len(orders) > 1 else "same",
            "slow": slow, "fast": fast, "slow_first": tops[slow][0], "fast_first": tops[fast][0],
            "largest_move": round(max(moved, default=0.0), 1), "ai_share_reference": reference["role_ai_share"],
            "top": VERDICT_TOP}


@route("POST", "/api/match")
def match(req):
    body = req.json()
    top = body.get("top", 10)
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 50:
        raise Refused("'top' must be a whole number from 1 to 50")
    data, profile, scenario, adoption, changes = request_context(body)
    include = [o for o in body.get("include", []) if isinstance(o, str)][:5] if isinstance(body.get("include"), list) else []
    if profile.get("current_occupation"):
        include.append(profile["current_occupation"])
    result = matching.match_person(profile, data, scenario=scenario, adoption=adoption, top=top, include=include)
    ranks, totals, tops = scenario_ranks(profile, data, {m["occ_id"] for m in result["results"]})
    for m in result["results"]:
        m["scenario_ranks"], m["scenario_totals"] = ranks.get(m["occ_id"]), totals.get(m["occ_id"])
    current = next((m for m in result["results"] if "current_occupation" in m["flags"]), None)
    if current:  # the job they do now is not one of their moves: say how many moves score higher instead
        current["moves_above"] = sum(1 for m in result["ranking"] if listed(m) and m["total"] > current["total"])
    listed_count = sum(1 for m in result["ranking"] if listed(m))
    return reply(**{k: v for k, v in result.items() if k != "ranking"}, ranking=result["ranking"][:100],
                 listed=listed_count, total_occupations=len(result["ranking"]),
                 restricted_hidden=sum(1 for m in result["ranking"] if "restricted_my" in m["flags"]),
                 restricted_shown=bool(profile.get("show_restricted")),
                 weights=matching.WEIGHTS, field_weights=matching.FIELD_WEIGHTS, skill_split=matching.SKILL_SPLIT,
                 horizon_year=outlook.HORIZON_YEAR, scenario=scenario_info(scenario, adoption),
                 scenarios=scenario_list(), trend_data=data_version(data, changes), sdg_bonus=matching.SDG_BONUS,
                 sdg_goals=matching.sdg_goal_options(data), current=current, reference=data["ai"]["reference"],
                 verdict=scenario_verdict(tops, data["ai"]["reference"]))


def one_match(body: dict, with_stability: bool = False):
    data, profile, scenario, adoption, changes = request_context(body)
    occ_id = body.get("occ_id") or body.get("role_id")
    if not occ_id:
        raise Refused("'occ_id' is required")
    if occ_id not in data["by_id"]:
        raise Refused(f"unknown occ_id '{occ_id}'")
    if with_stability:
        found = matching.match_person(profile, data, scenario=scenario, adoption=adoption, top=1,
                                      include=[occ_id])["results"]
        found = next(m for m in found if m["occ_id"] == occ_id)
    else:
        prepared = matching.prepare(profile, data)
        found = matching.detailed(prepared, data, occ_id, adoption, matching.field_fit(prepared, data))
    return data, profile, found, scenario, adoption


@route("POST", "/api/explain")
def explain_match(req):
    """Why one occupation scores what it does, in words; the match is recomputed here, so the
    model only ever sees numbers our code produced."""
    body = req.json()
    lang = body.get("lang", "en")
    if lang not in explain.LANGS:
        raise Refused(f"'lang' must be one of {list(explain.LANGS)}")
    data, profile, found, scenario, adoption = one_match(body, with_stability=True)
    learn = found["skill_detail"]["tech_missing"][:2]
    after = None
    if learn:
        fresh = {k: v for k, v in profile.items() if not k.startswith("_")}  # worked out again with the new tools
        more = matching.prepare({**fresh, "technologies": fresh["technologies"] + [t["skill_id"] for t in learn]}, data)
        after = matching.detailed(more, data, found["occ_id"], adoption, matching.field_fit(more, data))
    return reply(occ_id=found["occ_id"], **explain.explain(found, short=bool(body.get("short")),
                                                           scenario=scenario_info(scenario, adoption), lang=lang),
                 to_raise=explain.raise_tips(found, after, [t["skill_name"] for t in learn]))


@route("POST", "/api/jobad")
def job_ad(req):
    """A job ad's tools (word match, no LLM), which the person has, and the closest occupations.
    The ad is used for this request only and never stored."""
    body = req.json()
    text = body.get("text")
    if not isinstance(text, str) or len(text.strip()) < 40:
        raise Refused("'text' must be the job ad's text (at least 40 characters)")
    data = matching.load_data()
    mine = body.get("technologies", [])
    if not isinstance(mine, list) or any(t not in data["technologies"] for t in mine):
        raise Refused("'technologies' must be a list of tech_ids")
    _, adoption = scenario_of(body)
    weights = outlook.skill_weights(data, adoption)
    asked = [t["skill_id"] for t in cv_reader.find_technologies(text[:MAX_AD_CHARS], data["technologies"])]
    titles = cv_reader.find_titles(text[:MAX_AD_CHARS], data)

    def tagged(tid):
        w = weights.get(tid, matching.STEADY)
        free = matching.resources_for(f"tech:{tid}", data)
        return {"skill_id": tid, "skill_name": data["technologies"][tid]["name"], "status": w["status"],
                "handoff": w["handoff"],
                "course": {"title": free[0]["title"], "provider": free[0]["provider"], "url": free[0]["url"]} if free else None}
    close = []
    for occ in data["occupations"]:
        shared = set(data["occ_techs"].get(occ["occ_id"], [])) & set(asked)
        if shared:
            close.append({"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"],
                          "shared": len(shared), "of_ad": round(100 * len(shared) / len(asked)),
                          "status": outlook.role_outlook(occ, data, adoption)["status"]})
    close.sort(key=lambda r: (-r["shared"], r["title"]))
    return reply(found=len(asked), have=[tagged(t) for t in asked if t in mine],
                 missing=[tagged(t) for t in asked if t not in mine], roles=close[:3], titles=titles[:3],
                 method="Word match against the O*NET technology names in data/technologies.csv; no LLM. A tool the "
                        "ad words differently may be missed.")


# --- step 4: pathway and step 5: SDG ----------------------------------------------------------------

@route("POST", "/api/learn")
def learn_for_person(req):
    data, profile, found, _, _ = one_match(req.json())
    return reply(learning.page(found["occ_id"], data, found, profile["hours_per_week"]))


@route("GET", "/api/learn/<occ_id>")
def learn_occupation(req, occ_id: str):
    page = learning.page(occ_id)
    return reply(page) if page else reply(error="not found", status=404)


@route("GET", "/api/sdg/summary")
def sdg_summary(req):
    return reply(impact.summary())


@route("POST", "/api/sdg/record")
def sdg_record(req):
    body = req.json()
    try:
        return reply(impact.record(body.get("learner"), body.get("occ_id") or body.get("role_id"),
                                   body.get("hours_planned"), body.get("hours_done"), body.get("items_done", 0)))
    except impact.ImpactError as error:
        raise Refused(str(error)) from None


# --- step 6: futures --------------------------------------------------------------------------------

def brief(m: dict, rank: int) -> dict:
    return {"occ_id": m["occ_id"], "role_id": m["occ_id"], "title": m["title"], "role_name": m["title"],
            "field_id": m["field_id"], "rank": rank, "total": m["total"], "outlook": m["outlook"]["outlook"],
            "status": m["outlook"]["status"], "skill": m["components"]["skill"]["score"], "flags": m["flags"]}


@route("POST", "/api/futures")
def futures(req):
    """The person's ranking under each named scenario, side by side, and what moves between them."""
    body = req.json()
    top = body.get("top", 5)
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 25:
        raise Refused("'top' must be a whole number from 1 to 25")
    data, profile, _, _, changes = request_context(body)
    result = matching.match_person(profile, data, scenario=outlook.DEFAULT_SCENARIO, top=top)
    stability = {m["occ_id"]: m["stability"] for m in result["results"]}
    columns, ranks, totals, detail = [], {}, {}, {}
    for name, s in outlook.SCENARIOS.items():
        ranked = [m for m in matching.rank(profile, data, scenario=name) if listed(m)]
        for i, m in enumerate(ranked):
            ranks.setdefault(m["occ_id"], {})[name] = i + 1
            totals.setdefault(m["occ_id"], {})[name] = m["total"]
            detail.setdefault(m["occ_id"], {})[name] = m
        columns.append({"id": name, **s, "top": [brief(m, i + 1) for i, m in enumerate(ranked[:top])]})
    first, last = next(iter(outlook.SCENARIOS)), list(outlook.SCENARIOS)[-1]
    moves = []
    for occ_id in {m["occ_id"] for c in columns for m in c["top"]}:
        a, b = detail[occ_id][first], detail[occ_id][last]
        moves.append({"occ_id": occ_id, "role_id": occ_id, "title": a["title"], "role_name": a["title"],
                      "field_id": a["field_id"], "ranks": ranks[occ_id], "totals": totals[occ_id],
                      "stability": stability.get(occ_id), "rank_move": ranks[occ_id][first] - ranks[occ_id][last],
                      "total_move": round(b["total"] - a["total"], 1),
                      "outlook_move": round(b["outlook"]["outlook"] - a["outlook"]["outlook"], 1),
                      "skill_move": round((b["components"]["skill"]["score"] or 0) - (a["components"]["skill"]["score"] or 0), 1),
                      "ai_share": b["outlook"]["ai_share"], "ai_share_reference": b["outlook"]["ai_share_reference"],
                      "builder": b["outlook"]["builder"], "status": b["outlook"]["status"]})
    moves.sort(key=lambda m: (-abs(m["total_move"]), m["title"]))
    tops = [c["top"][0]["occ_id"] for c in columns if c["top"]]
    return reply(scenarios=columns, moves=moves, horizon_year=outlook.HORIZON_YEAR, top_changes=len(set(tops)) > 1,
                 top3_changes=len({tuple(m["occ_id"] for m in c["top"][:3]) for c in columns}) > 1,
                 simulation=result["simulation"], trend_data=data_version(data, changes),
                 parameters=outlook.parameters())


@route("GET", "/api/whatif")
def what_if_inputs(req):
    return reply(inputs=whatif.editable(), examples=whatif.examples(), news=whatif.news(),
                 outlook_weight=matching.WEIGHTS["outlook"])


@route("POST", "/api/whatif")
def what_if_run(req):
    """The same pipeline on a changed copy of the data, for this request only: before and after."""
    body = req.json()
    data, profile, scenario, adoption, changes = request_context(body, required_changes=True)
    after = whatif.changed_data(data, changes)

    def ranked(d):
        return [m for m in matching.rank(profile, d, adoption=adoption) if listed(m)]
    before_rows, after_rows = ranked(data), ranked(after)
    pick = body.get("occ_id") or body.get("role_id") or (before_rows[0]["occ_id"] if before_rows else None)
    path = None
    if pick in data["by_id"]:
        prepared_b, prepared_a = matching.prepare(profile, data), matching.prepare(profile, after)
        path = whatif.path_changes(
            matching.detailed(prepared_b, data, pick, adoption, matching.field_fit(prepared_b, data)),
            matching.detailed(prepared_a, after, pick, adoption, matching.field_fit(prepared_a, after)))
    return reply(changes=whatif.describe(changes), signals=[], roles=whatif.role_changes(data, after, adoption),
                 skills=whatif.skill_changes(data, after, adoption), scenario=scenario_info(scenario, adoption),
                 before=[brief(m, i + 1) for i, m in enumerate(before_rows[:12])],
                 after=[brief(m, i + 1) for i, m in enumerate(after_rows[:12])],
                 path=path, outlook_weight=matching.WEIGHTS["outlook"], trend_data=data_version(after, changes),
                 you=whatif.person_change(profile, data, after, adoption, before_rows, after_rows))


# --- the team view: the same engine for an HR or career-centre officer ------------------------------

@route("GET", "/api/team")
def team_sample(req):
    scenario, adoption = scenario_of(req.args)
    return reply(**team.view(None, matching.load_data(), adoption=adoption), scenario=scenario_info(scenario, adoption),
                 scenarios=scenario_list())


@route("POST", "/api/team")
def team_own(req):
    """A team as {members: [{occ_id, headcount}], hours_per_week}: job titles and counts only, never
    names or anything about a person. Used for this request and not stored."""
    body = req.json()
    scenario, adoption = scenario_of(body)
    try:
        result = team.view(body, matching.load_data(), adoption=adoption)
    except team.TeamError as error:
        raise Refused(str(error)) from None
    return reply(**result, scenario=scenario_info(scenario, adoption), scenarios=scenario_list())


# --- sources and "Update data" -------------------------------------------------------------------------

def run_update(with_arxiv: bool) -> None:
    """The "Update data" job: demand.py in its own process, then a look for a newer AI-usage release."""
    command = [sys.executable, os.fspath(MODULES / "demand.py")]
    if not with_arxiv:
        command.append("--no-arxiv")
    returncode, output = -1, ""
    try:
        finished = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=UPDATE_TIMEOUT_S)
        returncode, output = finished.returncode, finished.stdout + finished.stderr
        release = releases.check()  # reported only: a person reviews and pins a new release
        output += (f"Economic Index: pinned {release['pinned']}, newest {release['latest'] or 'not checked'}"
                   + (" (a new release to review)" if release["new_release"] else "") + "\n")
    except subprocess.TimeoutExpired:
        output += f"stopped after {UPDATE_TIMEOUT_S} s\n"
    except Exception as problem:  # noqa: BLE001  whatever happens, the lock is released below
        output += f"the update could not run: {problem!r}\n"
    finally:
        _update.update(status="done" if returncode == 0 else "failed", returncode=returncode, log=output[-4000:],
                       finished=datetime.now(timezone.utc).isoformat())
        _update_running.release()


def start_update(arxiv: bool, trigger: str) -> bool:
    if not _update_running.acquire(blocking=False):
        return False
    _update.update(status="running", trigger=trigger, returncode=None, log="", finished=None,
                   started=datetime.now(timezone.utc).isoformat())
    threading.Thread(target=run_update, args=(arxiv,), daemon=True).start()
    return True


def last_fetch() -> date | None:
    days = [r["fetched_date"] for r in read_csv("demand_inputs.csv")
            if r["kind"] in ("arxiv", "wage") and re.fullmatch(r"\d{4}-\d\d-\d\d", r["fetched_date"])]
    return date.fromisoformat(max(days)) if days else None


def next_auto_update() -> date | None:
    last = last_fetch()
    return last + timedelta(days=AUTO_UPDATE_DAYS) if AUTO_UPDATE_DAYS > 0 and last else None


def auto_update_loop() -> None:
    while True:
        due = next_auto_update()
        if due and date.today() >= due and start_update(True, "schedule"):
            print(f"Automatic data update started (data from {last_fetch()})", flush=True)
        time.sleep(AUTO_CHECK_S)


@route("POST", "/api/update")
def update_start(req):
    try:
        sent = json.loads(req.body) if req.body else {}
    except ValueError:
        sent = {}
    arxiv = sent.get("arxiv", True) is not False if isinstance(sent, dict) else True
    if not start_update(arxiv, "button"):
        return reply({"error": "an update is already running", **_update}, status=409)
    return reply(dict(_update), status=202)


def update_status() -> dict:
    due = next_auto_update()
    return {**_update, "auto_update_days": AUTO_UPDATE_DAYS, "last_fetched": str(last_fetch() or "") or None,
            "next_auto_update": due.isoformat() if due else None, "economic_index": releases.last_check()}


@route("GET", "/api/update")
def update_state(req):
    return reply(update_status())


def source_rows(data: dict) -> list[dict]:
    layer = data["ai"]
    ei, lmi, onet = (layer["source"][k] for k in ("economic_index", "labor_market_impacts", "onet"))
    months = layer["context"]["months"]
    inputs = read_csv("demand_inputs.csv")
    by_kind = {}
    for r in inputs:
        by_kind.setdefault(r["kind"], []).append(r)
    every = (f"Fetched again every {AUTO_UPDATE_DAYS:g} days and whenever Update data is pressed."
             if AUTO_UPDATE_DAYS > 0 else "Fetched again whenever Update data is pressed.")
    resources = read_csv("learning_resources.csv")
    sdg = read_csv("sdg_map.csv")
    regulated = read_csv("regulated.csv")
    rows = [
        {"id": "economic_index", "name": ei["source_name"], "url": ei["source_url"], "licence": ei["licence"],
         "used_for": "AI share of every task and occupation; hands-off share of each skill and tool; Malaysia next "
                     "to the world", "covers": f"{months[0]} to {months[-1]}", "released": ei["release_date"],
         "fetched": ei["fetched_date"], "refresh": "Pinned release; every update checks for a newer one, which a "
                                                   "person reviews before it is used.", "rows": len(layer["tasks"])},
        {"id": "task_coverage", "name": lmi["source_name"], "url": lmi["source_url"], "licence": lmi["licence"],
         "used_for": "The second reading of each task's AI share, and the prior for thinly measured occupations",
         "covers": "August and November 2025", "released": lmi["release_date"], "fetched": lmi["fetched_date"],
         "refresh": "Read again when Anthropic publishes a new version.",
         "rows": sum(1 for t in layer["tasks"] if t["reading_penetration"] is not None)},
        {"id": "onet", "name": onet["source_name"], "url": onet["source_url"], "licence": onet["licence"],
         "used_for": f"The {len(data['occupations'])} occupations: tasks, skills, knowledge, tools, interest profiles, "
                     "Job Zones, job titles and the skills check's level examples",
         "covers": "O*NET 31.0", "released": "", "fetched": onet["fetched_date"],
         "refresh": "Re-extracted when O*NET publishes a new database.", "rows": len(data["occupations"])},
        {"id": "esco", "name": data["occupations"][0]["isco_source_name"], "url": data["occupations"][0]["isco_source_url"],
         "licence": "EU open data (ESCO)", "used_for": "Each occupation's ISCO-08 unit group, which links it to "
         "Malaysia's MASCO 2020, to MyCOL and to DOSM's figures by major group", "covers": "ESCO v1.1",
         "released": "2022-09", "fetched": onet["fetched_date"], "refresh": "Read again when ESCO publishes a new crosswalk.",
         "rows": sum(1 for o in data["occupations"] if o["isco"])},
        {"id": "mycol", "name": "TalentCorp MyMahir MyCOL 2024/2025", "url": MYCOL_URL,
         "licence": "", "used_for": "Malaysian demand: the official critical-occupations list",
         "covers": "2024/2025 edition, 66 occupations", "released": "2026-03-13", "fetched": "2026-10-23",
         "refresh": "Typed from the brochure when a new edition is published.",
         "rows": sum(1 for o in data["occupations"] if o["mycol"] == "yes")},
    ]
    for kind, name, used in (("job_ads", "DOSM Job Market Insights (online job ads by MASCO major group)",
                              "Malaysian demand: each major group's share of online job ads"),
                             ("wage", "OpenDOSM wages_occupation", "Median wage of each MASCO major group (context)"),
                             ("arxiv", "arXiv API", "The pace of AI research (the tempo of adoption)")):
        mine = by_kind.get(kind, [])
        if mine:
            rows.append({"id": kind, "name": name, "url": mine[0]["source_url"], "licence": "",
                         "used_for": used, "covers": f"{min(r['period_start'] for r in mine)} to "
                                                     f"{max(r['period_end'] for r in mine)}",
                         "released": max(r["release_date"] for r in mine), "fetched": max(r["fetched_date"] for r in mine),
                         "refresh": every if kind != "job_ads" else "A new DOSM workbook each quarter, put in raw/dosm/.",
                         "rows": len(mine)})
    rows.append({"id": "courses", "name": "Free course pages (Saylor Academy and others), each opened and checked",
                 "url": "", "licence": "", "used_for": "Every step of a learning path",
                 "covers": f"{len(resources)} resources", "released": "",
                 "fetched": max(r["verified_date"] for r in resources),
                 "refresh": "scripts/check_links.py opens every link again.", "rows": len(resources)})
    rows.append({"id": "sdg", "name": sdg[0]["source_name"], "url": sdg[0]["source_url"], "licence": "",
                 "used_for": "The SDG targets of every occupation and skill, each with a written reason",
                 "covers": f"{len({r['sdg_target'] for r in sdg})} targets", "released": "",
                 "fetched": max(r["source_date"] for r in sdg), "refresh": "Reviewed when the occupations change.",
                 "rows": len(sdg)})
    rows.append({"id": "regulated", "name": "Malaysian professional bodies (registration to practise)", "url": "",
                 "licence": "", "used_for": "Which occupations need registration in Malaysia, and with whom",
                 "covers": f"{len(regulated)} professions", "released": "",
                 "fetched": max((r["verified_date"] for r in regulated if r["verified_date"]), default=""),
                 "refresh": "Checked by hand.", "rows": len(regulated)})
    limits = read_csv("my_restrictions.csv")
    rows.append({"id": "my_restrictions", "name": "Laws of Malaysia (legal limits on some occupations)",
                 "url": limits[0]["source_url"] if limits else "", "licence": "",
                 "used_for": "Occupations left out of matches unless the person chooses to show them: "
                             + "; ".join(f"{r['topic']} ({r['source_name']})" for r in limits),
                 "covers": f"{sum(len([o for o in r['occ_ids'].split(';') if o]) for r in limits)} occupations",
                 "released": "", "fetched": max((r["source_date"] for r in limits), default=""),
                 "refresh": "Checked by hand.", "rows": len(limits)})
    return rows


@route("GET", "/api/sources")
def sources(req):
    data = matching.load_data()
    return reply(sources=source_rows(data), update=update_status(), parameters=outlook.parameters(),
                 weights=matching.WEIGHTS, field_weights=matching.FIELD_WEIGHTS, skill_split=matching.SKILL_SPLIT,
                 sdg_bonus=matching.SDG_BONUS, scenarios=scenario_list(),
                 ai_build_topics=list(ai_exposure.AI_BUILD_TOPICS),
                 exposure={"min_usage_pct": ai_exposure.MIN_USAGE_PCT, "automation_weight": ai_exposure.AUTOMATION_WEIGHT,
                           "augmentation_weight": ai_exposure.AUGMENTATION_WEIGHT,
                           "full_evidence_pct": ai_exposure.FULL_EVIDENCE_PCT, "thin_spread": ai_exposure.THIN_SPREAD,
                           "min_activity_pct": ai_exposure.MIN_ACTIVITY_PCT},
                 demand={"share_full_pct": demand.SHARE_FULL_PCT, "arxiv_full_pct": demand.ARXIV_FULL_PCT,
                         "mycol_strength": demand.MYCOL_STRENGTH, "break_quarter": list(demand.BREAK_QUARTER),
                         "momentum": data["demand"]["momentum"]},
                 llm={"configured": explain.configured(), "model": explain.model_name(), "provider": explain.provider(),
                      "used_for": "Putting a score into words. It never sets a score, and a reply with a number that is "
                                  "not in our data is thrown away."},
                 reference=data["ai"]["reference"], evidence=evidence.rules(),
                 routes={"reach_points": matching.ROUTE_REACH})


@route("GET", "/api/scenarios")
def scenarios(req):
    return reply(scenarios=scenario_list(), default=outlook.DEFAULT_SCENARIO, horizon_year=outlook.HORIZON_YEAR,
                 parameters=outlook.parameters())


@route("GET", "/api/explain/status")
def explain_status(req):
    return reply(configured=explain.configured(), model=explain.model_name(), provider=explain.provider())


# --- the HTTP server ------------------------------------------------------------------------------------

def low_data(res: Response, method: str, headers) -> tuple[int, bytes, dict]:
    """Status, body and headers that cost little on mobile data: an ETag for every GET (an unchanged
    answer is a 304 with no body) and gzip for text over 1 KB. Cache-Control stays no-cache, so a page
    load always checks for new data."""
    out = {"Content-Type": res.content_type, "Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
    status, body = res.status, res.body
    if method == "GET" and status == 200:
        tag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
        out["ETag"] = tag
        if tag in (headers.get("If-None-Match") or ""):
            return 304, b"", out
    textual = res.content_type.startswith(("text/", "application/json", "application/javascript", "image/svg"))
    if textual and len(body) > 1024 and "gzip" in (headers.get("Accept-Encoding") or ""):
        body = gzip.compress(body, compresslevel=6)
        out["Content-Encoding"] = "gzip"
    return status, body, out


class Handler(BaseHTTPRequestHandler):
    server_version = "FutureSkills/3.0"

    def respond(self, method: str) -> None:
        length = self.headers.get("Content-Length") or "0"
        if not length.isdigit():
            self.close_connection = True  # where the body ends is unknown, so read no further
            res = reply(error="bad Content-Length", status=400)
        elif int(length) > MAX_BODY:
            res = reply(error="request too large", status=413)
        else:
            body = self.rfile.read(int(length)) if int(length) else b""
            try:
                res = dispatch(method, self.path, body)
            except Exception as problem:  # noqa: BLE001  one failing request never stops the server
                self.log_error("%s %s failed: %r", method, self.path, problem)
                res = reply(error="internal server error", status=500)
        status, payload, headers = low_data(res, method, self.headers)
        self.send_response(status)
        for name, value in {**headers, "Content-Length": str(len(payload))}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.respond("GET")

    def do_POST(self):
        self.respond("POST")


def main() -> None:
    global AUTO_UPDATE_DAYS
    load_env_file()  # here, not on import, so the tests never pick up a real API key
    AUTO_UPDATE_DAYS = float(os.getenv("AUTO_UPDATE_DAYS", "7"))  # a value in .env counts too
    port = int(os.environ.get("PORT") or 8080)
    server = ThreadingHTTPServer(("", port), Handler)
    print(f"Future Skills is up: http://localhost:{port}", flush=True)
    print(f"Explanations: LLM {'configured' if explain.configured() else 'not configured'}"
          f" (variables seen: {explain.llm_variables_set() or 'none'})", flush=True)
    matching.load_data()  # build the tables once before the first visitor
    if AUTO_UPDATE_DAYS > 0:
        threading.Thread(target=auto_update_loop, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
