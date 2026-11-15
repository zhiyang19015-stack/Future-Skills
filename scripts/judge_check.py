"""The judge check: the live checks a Domain 1 finalist judge runs, run by code on the real API.

Every number in docs/judge_check.md comes from this script; nothing in it is typed by hand. It
calls the same JSON API the web page calls (main.dispatch), so it checks what a judge would see.

    1 Blank profile     nothing filled in: what does /api/match return?
    2 Scenarios         the 5 demo people under slow, moderate and fast adoption: does the first
                        move (the job they do now is not a move) change, how many of the top 5
                        change, the largest change in a match score
    3 Changed data      every simulated headline for every demo person: the ranking, the outlook
                        of the job they do now and the learning path, before and after
    4 Radar             of the first 15 "rising" occupations, how many have an AI share the
                        Economic Index cannot measure (thin evidence, or mostly physical work that
                        chat-AI use does not show) rather than a low measured one
    5 Learning paths    each demo person's path for their first move: job-search courses given to
                        someone in work, the share of resources not in English, skills with no course
    6 Course links      10 learning-resource links drawn at random (seed printed): does each open?
    7 Public URL        is the app reachable at a public address? ("none" when there is none)

    python scripts/judge_check.py                    # print the report
    python scripts/judge_check.py --write            # save docs/judge_check.md and .json
    python scripts/judge_check.py --write --baseline # also freeze this run as the "before" baseline
    python scripts/judge_check.py --offline          # skip checks 6 and 7 (no internet)
    python scripts/judge_check.py --url https://...  # check 7 against this address (or FS_PUBLIC_URL)

The pass marks are the targets set for the improvement plan; a mark is a test of the product, not
a quota the model is tuned to meet.
"""

import argparse
import csv
import json
import os
import random
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import check_links  # noqa: E402
import ilo  # noqa: E402
import main  # noqa: E402
import matching  # noqa: E402
import outlook  # noqa: E402

DOCS = ROOT / "docs"
REPORT, RESULT, BASELINE = DOCS / "judge_check.md", DOCS / "judge_check.json", DOCS / "judge_check_baseline.json"
TOP = 5                      # how far down a person's list the scenarios are compared
RADAR_TOP = 15               # how many of the Radar's rising occupations are read
LINKS = 10                   # course links drawn
DEFAULT_SEED = 2026
JOB_SEARCH = re.compile(r"\b(resume|résumé|cv|interview\w*|job search|cover letter)\b", re.I)
# SOC major groups whose work is mostly physical: an AI share the Economic Index (chat use) cannot see
MANUAL_FIELDS = {"35", "37", "39", "45", "47", "49", "51", "53"}
OWN_JOB_MOVE = 1.0           # outlook points; a change elsewhere shifts every average a little
TARGETS = {"first_move_changed": 3, "top5_changed": 4, "radar_unmeasured_max": 0, "non_english_min": 10.0}


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    res = main.dispatch(method, path, json.dumps(body).encode("utf-8") if body is not None else b"")
    return res.status, json.loads(res.body)


def people() -> list[dict]:
    return main.sample_profiles()


# --- 1 blank profile --------------------------------------------------------------------------------

def blank_profile() -> dict:
    status, body = call("POST", "/api/match", {})
    results = [m for m in body.get("results", []) if main.listed(m)] if status == 200 else []
    return {"status": status, "ranked": len(results), "listed": body.get("listed", 0) if status == 200 else 0,
            "top": [{"title": m["title"], "total": m["total"]} for m in results[:3]],
            "message": body.get("error") or body.get("needs_input"),
            "pass": not results}


# --- 2 scenarios ------------------------------------------------------------------------------------

def scenarios() -> dict:
    names = list(outlook.SCENARIOS)
    slow, fast = names[0], names[-1]
    rows = []
    for p in people():
        _, body = call("POST", "/api/futures", {"profile_id": p["profile_id"], "top": TOP})
        cols = {c["id"]: c["top"] for c in body["scenarios"]}
        first = {n: (cols[n][0]["title"] if cols[n] else None) for n in names}
        ids = {n: [m["occ_id"] for m in cols[n]] for n in names}
        new_in_fast = [o for o in ids[fast] if o not in ids[slow]]
        _, matched = call("POST", "/api/match", {"profile_id": p["profile_id"]})
        verdict = matched.get("verdict") or {}
        rows.append({"profile_id": p["profile_id"], "name": p["name"], "kind": p.get("kind", "student"),
                     "first": first, "first_changed": first[slow] != first[fast],
                     "first_changed_any": len(set(first.values())) > 1,
                     "top5": {n: [m["title"] for m in cols[n]] for n in names},
                     "top5_new_in_fast": len(new_in_fast), "top5_order_changed": ids[slow] != ids[fast],
                     "top5_changed": bool(new_in_fast) or ids[slow] != ids[fast],
                     "max_score_move": max((abs(m["total_move"]) for m in body["moves"]), default=0.0),
                     "first_score_move": next((m["total_move"] for m in body["moves"]
                                               if cols[slow] and m["occ_id"] == cols[slow][0]["occ_id"]), None),
                     "verdict": verdict.get("kind")})
    return {"slow": slow, "fast": fast, "people": rows,
            "first_move_changed": sum(r["first_changed"] for r in rows),
            "top5_changed": sum(r["top5_changed"] for r in rows),
            "top5_set_changed": sum(1 for r in rows if r["top5_new_in_fast"]),
            "max_score_move": max((r["max_score_move"] for r in rows), default=0.0),
            # the top 5 counts as changed when another occupation enters it, not when two swap places
            "pass": sum(r["first_changed"] for r in rows) >= TARGETS["first_move_changed"]
            and sum(1 for r in rows if r["top5_new_in_fast"]) >= TARGETS["top5_changed"]}


# --- 3 changed data ---------------------------------------------------------------------------------

def news_runs() -> dict:
    _, inputs = call("GET", "/api/whatif")
    rows = []
    for n in inputs["news"]:
        for p in people():
            status, body = call("POST", "/api/whatif", {"profile_id": p["profile_id"], "trend_changes": n["changes"]})
            if status != 200:
                rows.append({"news": n["id"], "title": n["title"], "profile_id": p["profile_id"], "error": body})
                continue
            before = [m["occ_id"] for m in body["before"][:TOP]]
            after = [m["occ_id"] for m in body["after"][:TOP]]
            you = body.get("you") or {}
            subject = you.get("subject") if you.get("subject_kind") == "current" else None
            rows.append({"news": n["id"], "title": n["title"], "named": n.get("person") == p["profile_id"],
                         "profile_id": p["profile_id"], "name": p["name"],
                         "first": {"before": body["before"][0]["title"] if body["before"] else None,
                                   "after": body["after"][0]["title"] if body["after"] else None},
                         "first_changed": before[:1] != after[:1],
                         "top5_changed": before != after,
                         "top5_new": len([o for o in after if o not in before]),
                         "own_job": None if subject is None else
                         {"title": subject["title"], "before": subject["outlook"]["before"],
                          "after": subject["outlook"]["after"], "move": subject["outlook_move"]},
                         "path_changed": bool((body.get("path") or {}).get("order_changed"))})
    ok = [r for r in rows if "error" not in r]
    with_job = [r for r in ok if r["own_job"]]
    return {"news": len(inputs["news"]), "runs": len(rows), "errors": len(rows) - len(ok), "rows": rows,
            "top5_changed": sum(r["top5_changed"] for r in ok), "first_changed": sum(r["first_changed"] for r in ok),
            "own_job_runs": len(with_job), "own_job_moved": sum(1 for r in with_job if abs(r["own_job"]["move"]) >= OWN_JOB_MOVE),
            "path_changed": sum(r["path_changed"] for r in ok),
            "news_moving_named_person": sum(1 for r in ok if r["named"] and (r["top5_changed"] or r["path_changed"]
                                                                            or (r["own_job"] and abs(r["own_job"]["move"]) >= OWN_JOB_MOVE))),
            "news_with_person": sum(1 for r in ok if r["named"])}


# --- 4 radar ----------------------------------------------------------------------------------------

def radar() -> dict:
    data = matching.load_data()
    out = {}
    for name in ("moderate", "fast"):
        _, body = call("GET", f"/api/radar?scenario={name}")
        rows = []
        for r in body["rising"][:RADAR_TOP]:
            occ = data["by_id"][r["occ_id"]]
            ilo_row = ilo.for_occupation(occ, data)
            rows.append({"title": r["title"], "field_id": r["field_id"], "ai_share": r["ai_share"],
                         "change": r["change"], "thin": bool(r["thin_evidence"]),
                         "manual": r["field_id"] in MANUAL_FIELDS,
                         "ilo_mean": ilo_row["mean"] if ilo_row else None})
        out[name] = {"rows": rows, "thin": sum(r["thin"] for r in rows), "manual": sum(r["manual"] for r in rows),
                     "unmeasured": sum(r["thin"] or r["manual"] for r in rows),
                     "listed": len(rows), "title": body.get("rising_title")}
    # a renamed list that says why can pass too; the page sends its own title when it has one
    out["pass"] = all(out[n]["unmeasured"] <= TARGETS["radar_unmeasured_max"] or out[n]["title"]
                      for n in ("moderate", "fast"))
    return out


# --- 5 learning paths -------------------------------------------------------------------------------

def resources_of(page: dict) -> list[dict]:
    found = [r for s in page["stages"] for r in s["resources"]]
    found += [r for s in page["skills"] for r in s.get("resources", [])]
    found += page.get("hands_on", []) + page.get("claimable", [])
    return list({r["url"]: r for r in found}.values())


def paths() -> dict:
    rows = []
    for p in people():
        _, matched = call("POST", "/api/match", {"profile_id": p["profile_id"]})
        first = next((m for m in matched["results"] if main.listed(m)), None)
        if first is None:
            continue
        _, page = call("POST", "/api/learn", {"profile_id": p["profile_id"], "occ_id": first["occ_id"]})
        res = resources_of(page)
        job_search = [r["title"] for r in res if JOB_SEARCH.search(r["title"])]
        kind = p.get("kind", "student")
        non_en = [r for r in res if (r.get("language") or "en").lower() != "en"]
        no_course = [s["skill_name"] for s in page["skills"] if not s.get("resources")]
        providers = {}
        for r in res:
            providers[r["provider"]] = providers.get(r["provider"], 0) + 1
        top_provider = max(providers.items(), key=lambda x: x[1]) if providers else ("", 0)
        rows.append({"profile_id": p["profile_id"], "name": p["name"], "kind": kind, "occupation": first["title"],
                     "resources": len(res), "job_search": job_search,
                     "job_search_unsuited": job_search if kind == "working" else [],
                     "non_english": len(non_en), "non_english_pct": round(100 * len(non_en) / len(res), 1) if res else 0.0,
                     "skills": len(page["skills"]), "no_course": no_course,
                     "top_provider": {"name": top_provider[0], "count": top_provider[1]},
                     "hours": page["total_hours"], "weeks": page["weeks"], "hours_per_week": page["hours_per_week"]})
    total = sum(r["resources"] for r in rows)
    non_en = sum(r["non_english"] for r in rows)
    return {"people": rows, "unsuited": sum(len(r["job_search_unsuited"]) for r in rows),
            "no_course": sum(len(r["no_course"]) for r in rows), "resources": total,
            "non_english_pct": round(100 * non_en / total, 1) if total else 0.0,
            "pass": not any(r["job_search_unsuited"] for r in rows)
            and (round(100 * non_en / total, 1) if total else 0) >= TARGETS["non_english_min"]
            and not next((r["no_course"] for r in rows if r["profile_id"] == "P05"), [])}


# --- 6 course links ---------------------------------------------------------------------------------

def links(seed: int, offline: bool) -> dict:
    with (ROOT / "data" / "learning_resources.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["url"]]
    picked = random.Random(seed).sample(rows, min(LINKS, len(rows)))
    if offline:
        return {"seed": seed, "checked": False, "rows": [{"id": r["resource_id"], "url": r["url"]} for r in picked]}
    out = []
    for r in picked:
        verdict, detail = check_links.status(r["url"])
        out.append({"id": r["resource_id"], "title": r["title"], "url": r["url"], "verdict": verdict, "detail": detail})
    ok = sum(1 for r in out if r["verdict"] == "ok" and r["detail"] == "200")
    return {"seed": seed, "checked": True, "rows": out, "ok_200": ok, "of": len(out), "pass": ok == len(out)}


# --- 7 public URL -----------------------------------------------------------------------------------

def public_url(url: str | None, offline: bool) -> dict:
    if not url:
        return {"url": None, "reachable": None, "detail": "none", "pass": False}
    if offline:
        return {"url": url, "reachable": None, "detail": "not checked (offline)", "pass": False}
    target = url.rstrip("/") + "/api/health"
    try:
        req = urllib.request.Request(target, headers={"User-Agent": check_links.AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            return {"url": url, "reachable": r.status == 200, "detail": f"HTTP {r.status} from /api/health",
                    "pass": r.status == 200}
    except (urllib.error.URLError, TimeoutError, OSError) as failure:
        return {"url": url, "reachable": False, "detail": type(failure).__name__, "pass": False}


# --- the report -------------------------------------------------------------------------------------

def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run(seed: int = DEFAULT_SEED, offline: bool = False, url: str | None = None) -> dict:
    return {"date": date.today().isoformat(), "commit": commit(), "targets": TARGETS,
            "blank": blank_profile(), "scenarios": scenarios(), "news": news_runs(), "radar": radar(),
            "paths": paths(), "links": links(seed, offline), "public": public_url(url, offline)}


def headline(r: dict) -> dict:
    """The few numbers the before/after table compares."""
    s, n, p, lk = r["scenarios"], r["news"], r["paths"], r["links"]
    return {
        "1. Blank profile: occupations ranked": r["blank"]["ranked"],
        "1. Blank profile: first score": r["blank"]["top"][0]["total"] if r["blank"]["top"] else None,
        f"2. First move differs, {s['slow']} vs {s['fast']} (of 5)": s["first_move_changed"],
        f"2. Top 5 has a different occupation, {s['slow']} vs {s['fast']} (of 5)": s["top5_set_changed"],
        "2. Top 5 differs in order only or more (of 5)": s["top5_changed"],
        "2. Largest move of a first move's score (points)": max((abs(x["first_score_move"] or 0) for x in s["people"]),
                                                               default=0.0),
        "2. Largest match-score move (points)": s["max_score_move"],
        f"3. Headline runs whose top 5 changed (of {n['runs']})": n["top5_changed"],
        f"3. Headline runs whose first move changed (of {n['runs']})": n["first_changed"],
        f"3. Own-job outlook moved 1 point or more (of {n['own_job_runs']} runs with a job)": n["own_job_moved"],
        f"3. Learning path changed (of {n['runs']})": n["path_changed"],
        "4. Radar rising top 15, AI share not measurable (moderate)":
            f"{r['radar']['moderate']['unmeasured']} of {r['radar']['moderate']['listed']}",
        "4. Radar rising top 15, AI share not measurable (fast)":
            f"{r['radar']['fast']['unmeasured']} of {r['radar']['fast']['listed']}",
        "5. Job-search courses given to people in work": p["unsuited"],
        "5. Resources not in English (%)": p["non_english_pct"],
        "5. Skills on a path with no free course": p["no_course"],
        "6. Course links returning 200 (of 10)": lk.get("ok_200") if lk["checked"] else "not checked",
        "7. Public URL": r["public"]["detail"] if not r["public"]["url"] else
        f"{r['public']['url']} ({r['public']['detail']})",
    }


def mark(ok) -> str:
    return "pass" if ok else "fail"


def as_markdown(r: dict, base: dict | None) -> str:
    s, n, rd, p, lk, pub = r["scenarios"], r["news"], r["radar"], r["paths"], r["links"], r["public"]
    out = ["# Judge check", "",
           f"Generated by `python scripts/judge_check.py --write` on {r['date']} at commit `{r['commit']}`. "
           "Every number below is computed by the script from the app's own API; none is typed by hand. "
           "Run it again to check. Scenario results are estimates under stated assumptions, not predictions.", ""]
    now = headline(r)
    if base:
        was = headline(base)
        out += ["## Before and after", "",
                f"Before = the baseline run on {base['date']} at commit `{base['commit']}`.", "",
                "| Check | Before | Now |", "|---|---|---|"]
        out += [f"| {k} | {was.get(k, '—')} | {v} |" for k, v in now.items()]
    else:
        out += ["## Summary", "", "| Check | Now |", "|---|---|"] + [f"| {k} | {v} |" for k, v in now.items()]
    out += ["", "Targets for the improvement plan: first move differs for at least "
            f"{TARGETS['first_move_changed']} of 5 people and another occupation enters the top 5 for at least "
            f"{TARGETS['top5_changed']}; no occupation with an AI share the data cannot measure in the Radar's rising "
            "top 15 (or the list renamed and explained); no "
            f"job-search course for people in work, at least {TARGETS['non_english_min']:g}% of resources not in "
            "English, no skill without a free course on Aiman's path; every sampled link opens; a public URL.", ""]

    b = r["blank"]
    out += [f"## 1. Blank profile — {mark(b['pass'])}", "",
            f"`POST /api/match` with an empty body returns HTTP {b['status']} and ranks {b['ranked']} occupations "
            f"({b['listed']} listed in all)."]
    if b["top"]:
        out += ["First three: " + "; ".join(f"{m['title']} ({m['total']:g})" for m in b["top"]) + "."]
    if b["message"]:
        out += [f"Message: {b['message']}"]
    out += [""]

    out += [f"## 2. Scenarios — {mark(s['pass'])}", "",
            f"First move = the first occupation in the person's list that is not the job they do now. "
            f"Compared: {s['slow']} against {s['fast']} adoption.", "",
            "| Person | First move: slow / moderate / fast | First move differs | First move's score move "
            "| Top 5: new occupations under fast | Top 5 order differs | Largest score move in top 5 | Page verdict |",
            "|---|---|---|---|---|---|---|---|"]
    for x in s["people"]:
        out += [f"| {x['name']} ({x['kind']}) | {' / '.join(x['first'].values())} | {'yes' if x['first_changed'] else 'no'} "
                f"| {'—' if x['first_score_move'] is None else format(x['first_score_move'], '+g')} "
                f"| {x['top5_new_in_fast']} | {'yes' if x['top5_order_changed'] else 'no'} | {x['max_score_move']:g} "
                f"| {x['verdict']} |"]
    out += ["", f"First move differs for {s['first_move_changed']} of 5; another occupation enters the top 5 for "
            f"{s['top5_set_changed']} of 5 (set or order differs for {s['top5_changed']}); the largest move of any "
            f"match score in a top 5 is {s['max_score_move']:g} points.", ""]
    for x in s["people"]:
        out += [f"- **{x['name']}** top 5, {s['slow']}: " + "; ".join(x["top5"][s["slow"]]),
                f"  {s['fast']}: " + "; ".join(x["top5"][s["fast"]])]
    out += [""]

    out += ["## 3. Changed data (simulated headlines)", "",
            f"Each of the {n['news']} simulated headlines run for each of the 5 people through `POST /api/whatif` "
            f"(moderate adoption): {n['runs']} runs, {n['errors']} errors. Top 5 changed in {n['top5_changed']}, "
            f"first move in {n['first_changed']}, the outlook of the job the person does now moved 1 point or more in "
            f"{n['own_job_moved']} of {n['own_job_runs']} runs with a job, the learning path changed in "
            f"{n['path_changed']}. Headlines written for a named person moved something for that person in "
            f"{n['news_moving_named_person']} of {n['news_with_person']}.", "",
            "| Headline | Person | First move before → after | Top 5: new | Own job outlook | Path changed |",
            "|---|---|---|---|---|---|"]
    for x in n["rows"]:
        if "error" in x:
            out += [f"| {x['title']} | {x['profile_id']} | error: {x['error']} | | | |"]
            continue
        job = "—" if not x["own_job"] else f"{x['own_job']['before']:g} → {x['own_job']['after']:g}"
        first = x["first"]["before"] if not x["first_changed"] else f"{x['first']['before']} → {x['first']['after']}"
        star = " (named)" if x["named"] else ""
        out += [f"| {x['title']} | {x['name']}{star} | {first} | {x['top5_new']} | {job} | "
                f"{'yes' if x['path_changed'] else 'no'} |"]
    out += [""]

    out += [f"## 4. Radar: rising occupations — {mark(rd['pass'])}", "",
            "Not measurable = thin or manual (our rule for this check). Thin = the Economic Index sees too little "
            "of the occupation's own tasks, so its AI share leans on a prior (`thin_evidence`). Manual = a SOC field "
            "of mostly physical work (food, cleaning, personal care, farming, construction, repair, production, "
            "transport): the Economic Index counts chat-AI use only, so machines and robots in that work are not in "
            "it, and a low share there is not evidence that the work is safe from automation.", ""]
    for name in ("moderate", "fast"):
        x = rd[name]
        out += [f"**{name}**: {x['unmeasured']} of {x['listed']} not measurable ({x['thin']} thin, {x['manual']} "
                f"manual)." + (f" The page titles the list \"{x['title']}\"." if x["title"] else ""), "",
                "| # | Occupation | Field | AI share | Outlook change | Thin | ILO exposure |", "|---|---|---|---|---|---|---|"]
        out += [f"| {i} | {o['title']} | {o['field_id']}{' (manual)' if o['manual'] else ''} | {o['ai_share']:g}% | "
                f"{o['change']:+g} | {'yes' if o['thin'] else 'no'} | {'—' if o['ilo_mean'] is None else o['ilo_mean']} |"
                for i, o in enumerate(x["rows"], 1)]
        out += [""]

    out += [f"## 5. Learning paths — {mark(p['pass'])}", "",
            "Each person's path for their first move (moderate adoption), from `POST /api/learn`. Job-search "
            "courses = a title naming a resume, CV, interview, job search or cover letter; unsuited when the person "
            "is in work.", "",
            "| Person | Path for | Resources | Job-search courses | Not in English | Skills with no free course | "
            "Most from one provider | Hours (weeks at h/week) |", "|---|---|---|---|---|---|---|---|"]
    for x in p["people"]:
        js = "; ".join(x["job_search"]) or "none"
        if x["job_search_unsuited"]:
            js += " (unsuited: in work)"
        out += [f"| {x['name']} ({x['kind']}) | {x['occupation']} | {x['resources']} | {js} | "
                f"{x['non_english']} ({x['non_english_pct']:g}%) | {len(x['no_course'])} of {x['skills']}"
                f"{': ' + '; '.join(x['no_course']) if x['no_course'] else ''} | {x['top_provider']['name']} "
                f"({x['top_provider']['count']}) | {x['hours']:g} ({x['weeks']:g} at {x['hours_per_week']:g}) |"]
    out += ["", f"All paths: {p['resources']} resources, {p['non_english_pct']:g}% not in English, "
            f"{p['unsuited']} job-search courses given to people in work, {p['no_course']} skills with no free course.", ""]

    out += [f"## 6. Course links — {mark(lk.get('pass')) if lk['checked'] else 'not checked'}", "",
            f"{len(lk['rows'])} links drawn from `data/learning_resources.csv` with seed {lk['seed']} "
            "(`--seed` to repeat or change the draw)."]
    if lk["checked"]:
        out += [f"{lk['ok_200']} of {lk['of']} returned HTTP 200.", "", "| Resource | Link | Result |", "|---|---|---|"]
        out += [f"| {x['id']} {x['title']} | {x['url']} | {x['verdict']} ({x['detail']}) |" for x in lk["rows"]]
    else:
        out += ["Not checked: run without `--offline`."]
    out += [""]

    out += [f"## 7. Public URL — {mark(pub['pass'])}", "",
            "None: the app has no public address yet." if not pub["url"] else f"{pub['url']}: {pub['detail']}.", ""]
    return "\n".join(out)


def main_cli() -> int:
    cli = argparse.ArgumentParser(description="Run the finalist judges' live checks on the real API.")
    cli.add_argument("--write", action="store_true", help="save docs/judge_check.md and docs/judge_check.json")
    cli.add_argument("--baseline", action="store_true", help="with --write: also save this run as the baseline")
    cli.add_argument("--offline", action="store_true", help="skip the link and public-URL checks")
    cli.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed of the course-link draw")
    cli.add_argument("--url", default=os.environ.get("FS_PUBLIC_URL"), help="the public address to check")
    opts = cli.parse_args()
    result = run(opts.seed, opts.offline, opts.url)
    if opts.write and opts.baseline:
        BASELINE.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    text = as_markdown(result, base)
    if opts.write:
        RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(text + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
