"""The judge check: the live checks a Domain 1 finalist judge runs, run by code on the real API.

Every number in docs/judge_check.md comes from this script; nothing in it is typed by hand. It
calls the same JSON API the web page calls (main.dispatch), so it checks what a judge would see.

    1 Blank profile     nothing filled in: what does /api/match return?
    2 Scenarios         the 5 demo people under slow, moderate and fast adoption: does the first
                        move (the job they do now is not a move) change, how many of the top 5
                        change, the largest change in a match score; and does each person's
                        Matches and Futures page name a robust choice and give a "why" for every
                        scenario-dependent one
    3 Changed data      every simulated headline for every demo person: the ranking, the outlook
                        of the job they do now and the learning path, before and after
    4 Radar             of the first 15 "rising" occupations, how many have an AI share the
                        Economic Index cannot measure (thin evidence, or mostly physical work that
                        chat-AI use does not show) rather than a low measured one
    5 Learning paths    each demo person's path for their first move: job-search courses given to
                        someone in work, the share of resources not in English, skills with no course
    6 Course links      10 learning-resource links drawn at random (seed printed): does each open?
    7 Public URL        is the app reachable at a public address? ("none" when there is none)
    8 Real news         each real news item's page opened: are its quotes and date there? Can an item be
                        approved before that check? Aiman's own job before approval, after it, and after
                        undo (on a log of its own, so the app's own approvals are untouched)
    9 Languages, labels UI text in English, Bahasa Melayu and Chinese: strings missing or falling back to
                        English, English written into the page instead of through i18n, SDG reasons and
                        Sources-page text in English only, form fields with no label, colour pairs below
                        WCAG AA, and whether <html lang> follows the language (scripts/i18n_check.py,
                        read from the page's files; no browser)
   10 First-time path   clicks and required answers from the home page to a ranked list and to a learning
                        plan, counted from the paths in scripts/first_path.py, each step checked against the
                        page's source and the answers sent to the real API; plus the browser checks (390px
                        sideways scroll, console errors) saved in docs/ui_check.json by a browser run

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
import first_path  # noqa: E402
import i18n_check  # noqa: E402
import ilo  # noqa: E402
import main  # noqa: E402
import matching  # noqa: E402
import outlook  # noqa: E402
import news  # noqa: E402
import robust  # noqa: E402

DOCS = ROOT / "docs"
REPORT, RESULT, BASELINE = DOCS / "judge_check.md", DOCS / "judge_check.json", DOCS / "judge_check_baseline.json"
UI_BEFORE = DOCS / "judge_check_ui_before.json"   # the run on main just before the UI redesign
UI_CHECK = DOCS / "ui_check.json"                 # browser measurements (scripts/a11y_audit.js), not made here
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

WHY_NUMBERS = {"share_low": ("ai_share", "ai_share_reference", "outlook_move"),
               "share_high": ("ai_share", "ai_share_reference", "outlook_move"),
               "builder": ("builder", "builder_reference", "outlook_move"),
               "skills_up": ("skill_move",), "skills_down": ("skill_move",), "others": ("total_move",)}


def has_why(item: dict) -> bool:
    """A scenario-dependent choice has a "why" when its reason is a known one and carries its numbers."""
    w = item.get("why") or {}
    return w.get("code") in robust.REASONS and all(w.get(k) is not None for k in WHY_NUMBERS[w["code"]])


def robust_page(body: dict) -> dict:
    r = body.get("robust") or {}
    dep = r.get("dependent") or []
    return {"robust": [x["title"] for x in r.get("robust") or []], "dependent": len(dep),
            "with_why": sum(1 for x in dep if has_why(x)),
            "ok": bool(r.get("robust")) and all(has_why(x) for x in dep) and bool((r.get("rules") or {}).get("estimate"))}


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
        pages = {"matches": robust_page(matched), "futures": robust_page(body)}
        rows.append({"profile_id": p["profile_id"], "name": p["name"], "kind": p.get("kind", "student"),
                     "first": first, "first_changed": first[slow] != first[fast],
                     "first_changed_any": len(set(first.values())) > 1,
                     "top5": {n: [m["title"] for m in cols[n]] for n in names},
                     "top5_new_in_fast": len(new_in_fast), "top5_order_changed": ids[slow] != ids[fast],
                     "top5_changed": bool(new_in_fast) or ids[slow] != ids[fast],
                     "max_score_move": max((abs(m["total_move"]) for m in body["moves"]), default=0.0),
                     "first_score_move": next((m["total_move"] for m in body["moves"]
                                               if cols[slow] and m["occ_id"] == cols[slow][0]["occ_id"]), None),
                     "verdict": verdict.get("kind"), "robust": pages,
                     "robust_ok": all(x["ok"] for x in pages.values())})
    return {"slow": slow, "fast": fast, "people": rows,
            "first_move_changed": sum(r["first_changed"] for r in rows),
            "top5_changed": sum(r["top5_changed"] for r in rows),
            "top5_set_changed": sum(1 for r in rows if r["top5_new_in_fast"]),
            "max_score_move": max((r["max_score_move"] for r in rows), default=0.0),
            "robust_ok": sum(r["robust_ok"] for r in rows),
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
                         "ilo_mean": ilo_row["mean"] if ilo_row else None,
                         "second_source": r.get("second_source", "not checked")})
        out[name] = {"rows": rows, "thin": sum(r["thin"] for r in rows), "manual": sum(r["manual"] for r in rows),
                     "unmeasured": sum(r["thin"] or r["manual"] for r in rows),
                     "listed": len(rows), "title": body.get("rising_title"),
                     "confirmed": sum(1 for r in rows if r["second_source"] == "confirmed")}
    out["second_source"] = ilo.coverage(data)
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


# --- 8 real news ------------------------------------------------------------------------------------

def own_job(body: dict, occ_id: str) -> dict | None:
    for i, m in enumerate(body.get("results") or [], 1):
        if m["occ_id"] == occ_id:
            return {"title": m["title"], "rank": i, "total": m["total"], "ai_share": m["ai"]["ai_share"],
                    "outlook": m["outlook"]["outlook"], "status": m["outlook"]["status"]}
    return None


def real_news(offline: bool) -> dict:
    """The real news flow through the API, on a log of its own."""
    import tempfile
    old = os.environ.get("NEWS_LOG")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["NEWS_LOG"] = str(Path(tmp) / "judge_news_log.jsonl")
        try:
            _, view = call("GET", "/api/news")
            items, refused = [], 0
            for n in view["items"]:
                # before any check: propose, then try to approve; the rules must refuse
                _, p = call("POST", "/api/news/propose", {"id": n["id"]})
                status, _ = call("POST", "/api/news/decide", {"id": n["id"], "action": "approve",
                                                              "proposal_id": p.get("proposal_id")})
                refused += status == 400
                row = {"id": n["id"], "publisher": n["publisher"], "published": n["published"], "url": n["url"],
                       "person": n.get("person"), "method": p.get("method"),
                       "activities": p.get("activities"), "topics": p.get("topics")}
                if offline:
                    row["status"] = "not checked (offline)"
                else:
                    _, c = call("POST", "/api/news/check", {"id": n["id"]})
                    row.update(status=c["status"], problem=c.get("problem"), page_date=c.get("page_date"),
                               quotes_found=sum(1 for q in c["quotes"] if q["found"]), quotes=len(c["quotes"]))
                items.append(row)
            demo = None
            first = next((x for x in items if x["status"] == "verified" and x["person"]), None)
            if first:
                person = next(p for p in people() if p["profile_id"] == first["person"])
                body = {"profile_id": person["profile_id"], "scenario": "moderate", "top": 10}
                job = person.get("current_occupation")
                _, before = call("POST", "/api/match", body)
                _, p = call("POST", "/api/news/propose", {"id": first["id"]})
                status, _ = call("POST", "/api/news/decide", {"id": first["id"], "action": "approve",
                                                              "proposal_id": p["proposal_id"], "reviewer": "judge_check"})
                _, after = call("POST", "/api/match", body)
                call("POST", "/api/news/decide", {"id": first["id"], "action": "undo", "reviewer": "judge_check"})
                _, back = call("POST", "/api/match", body)
                top = lambda r: [m["occ_id"] for m in r["results"][:TOP]]  # noqa: E731
                ten = lambda r: [m["occ_id"] for m in r["results"][:10]]  # noqa: E731
                demo = {"id": first["id"], "name": person["name"], "approved": status == 200,
                        "own_job": {"before": own_job(before, job), "approved": own_job(after, job),
                                    "undone": own_job(back, job)},
                        "top5_changed": top(before) != top(after), "top10_order_changed": ten(before) != ten(after),
                        "undo_restores": ten(before) == ten(back) and before["trend_data"]["id"] == back["trend_data"]["id"],
                        "rows": p["rows"]}
            steps = [e["step"] for e in news.read_log()]
        finally:
            if old is None:
                os.environ.pop("NEWS_LOG", None)
            else:
                os.environ["NEWS_LOG"] = old
    return {"items": items, "verified": sum(1 for x in items if x["status"] == "verified"),
            "checked": not offline, "refused_unchecked": refused, "demo": demo, "log_steps": len(steps),
            "pass": not offline and bool(items) and refused == len(items) and bool(demo and demo["undo_restores"])}


def run(seed: int = DEFAULT_SEED, offline: bool = False, url: str | None = None) -> dict:
    return {"date": date.today().isoformat(), "commit": commit(), "targets": TARGETS,
            "blank": blank_profile(), "scenarios": scenarios(), "news": news_runs(), "radar": radar(),
            "paths": paths(), "links": links(seed, offline), "public": public_url(url, offline),
            "real_news": real_news(offline), "languages": languages(), "first_path": first_time_path()}


def first_time_path() -> dict:
    """Check 10: the path counts from scripts/first_path.py and, when a browser run saved them, the
    browser's own measurements. A browser number this script did not make is labelled as such."""
    r = first_path.run()
    if UI_CHECK.exists():
        r["browser"] = json.loads(UI_CHECK.read_text(encoding="utf-8"))
    return r


def first_path_headline(fp: dict | None) -> dict:
    if not fp:
        return {}
    own, demo, b = fp["paths"]["own"], fp["paths"]["demo"], fp.get("browser")
    cell = lambda x: "path broken" if not x else f"{x['clicks']} / {x['inputs']}"
    out = {
        "10. Own answers: clicks / required answers to a ranked list": cell(own["to_ranking"]),
        "10. Own answers: clicks / required answers to a learning plan": cell(own["to_plan"]),
        "10. Fictional demo person: clicks to a ranked list / to the Pathway page":
            f"{demo['to_ranking']['clicks'] if demo['to_ranking'] else '—'} / {demo['to_plan']['clicks'] if demo['to_plan'] else '—'}",
        f"10. Fields where one tap gives a ranking and a plan (of {fp['api']['fields']})": fp["api"]["one_tap_ok"],
        "10. Path steps whose button is missing from the page source": sum(len(p["broken"]) for p in fp["paths"].values()),
    }
    if b:
        out["10. Pages with sideways scroll at 390px (browser)"] = f"{b['overflow_pages']} of {b['pages']}"
        out["10. Console errors on the pages visited (browser)"] = b["console_errors"]
    else:
        out["10. Pages with sideways scroll at 390px (browser)"] = "not measured"
        out["10. Console errors on the pages visited (browser)"] = "not measured"
    out["10. Minutes for a first-time user"] = "not measured"
    return out


def languages() -> dict:
    """Check 9, from scripts/i18n_check.py: the counts, and the findings each count is made of."""
    r = i18n_check.run()
    return {"summary": i18n_check.summary(r), "rows": r["rows"], "totals": r["totals"],
            "pages": {f: {"pages": p["pages"], "missing_keys": len(p["missing_keys"]),
                          "fallback_ms": p["langs"]["ms"]["fallback"], "fallback_zh": p["langs"]["zh"]["fallback"],
                          "hardcoded": [f"{h['line']}: {h['text'][:60]}" for h in p["hardcoded"]],
                          "unlabelled": [f"{h['line']}: {h['field']}" for h in p["unlabelled"]]}
                      for f, p in r["pages"].items()},
            "side": r["side"], "sources": r["sources"], "indonesian": r["indonesian"], "names": r["names"],
            "contrast_fail": [c for c in r["contrast"] if not c["pass"]], "lang_attr": r["lang_attr"],
            "pass": all(v in (0, "0 / 0", "yes") for v in i18n_check.summary(r).values())}


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
        "2. Pages naming a robust choice and a why for every scenario-dependent one (of 5)":
            s.get("robust_ok", "not checked"),
        f"3. Headline runs whose top 5 changed (of {n['runs']})": n["top5_changed"],
        f"3. Headline runs whose first move changed (of {n['runs']})": n["first_changed"],
        f"3. Own-job outlook moved 1 point or more (of {n['own_job_runs']} runs with a job)": n["own_job_moved"],
        f"3. Learning path changed (of {n['runs']})": n["path_changed"],
        "4. Radar rising top 15, AI share not measurable (moderate)":
            f"{r['radar']['moderate']['unmeasured']} of {r['radar']['moderate']['listed']}",
        "4. Radar rising top 15, AI share not measurable (fast)":
            f"{r['radar']['fast']['unmeasured']} of {r['radar']['fast']['listed']}",
        "4. Occupations whose AI share a second source confirms / disputes / cannot check (of 910)":
            "{confirmed} / {disagree} / {one_source}".format(**r["radar"]["second_source"])
            if r["radar"].get("second_source") else "not checked",
        "4. Radar rising top 15 confirmed by a second source (moderate)":
            f"{r['radar']['moderate']['confirmed']} of {r['radar']['moderate']['listed']}"
            if "confirmed" in r["radar"]["moderate"] else "not checked",
        "5. Job-search courses given to people in work": p["unsuited"],
        "5. Resources not in English (%)": p["non_english_pct"],
        "5. Skills on a path with no free course": p["no_course"],
        "6. Course links returning 200 (of 10)": lk.get("ok_200") if lk["checked"] else "not checked",
        "7. Public URL": r["public"]["detail"] if not r["public"]["url"] else
        f"{r['public']['url']} ({r['public']['detail']})",
        **real_news_headline(r.get("real_news")),
        **(r["languages"]["summary"] if r.get("languages") else {}),
        **first_path_headline(r.get("first_path")),
    }


def real_news_headline(rn: dict | None) -> dict:
    if not rn:
        return {}
    d = rn["demo"]
    job = (d or {}).get("own_job") or {}
    share = " / ".join("—" if not job.get(k) else format(job[k]["ai_share"], "g") for k in ("before", "approved", "undone"))
    return {
        f"8. Real news items whose quotes and date are on their page (of {len(rn['items'])})":
            rn["verified"] if rn["checked"] else "not checked",
        f"8. Approval refused before the page was checked (of {len(rn['items'])})": rn["refused_unchecked"],
        "8. Aiman's own-job AI share (%): before / approved / undone": share if d else "not run",
        "8. Aiman's top 10 order changed after approval": ("yes" if d["top10_order_changed"] else "no") if d else "not run",
        "8. Undo restores the ranking and data version": ("yes" if d["undo_restores"] else "no") if d else "not run",
    }


def robust_cell(x: dict) -> str:
    if "robust" not in x:
        return "not checked"
    f = x["robust"]["futures"]
    both = "both pages" if x["robust_ok"] else "missing on a page"
    return (f"{'; '.join(f['robust']) or 'none'}; {f['dependent']} ({f['with_why']} with why), {both}")


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
    if UI_BEFORE.exists():
        ui = json.loads(UI_BEFORE.read_text(encoding="utf-8"))
        was = headline(ui)
        out += ["", "## UI redesign: before and after", "",
                f"Before = the run on main on {ui['date']} at commit `{ui['commit']}`, just before the UI redesign.", "",
                "| Check | Before redesign | Now |", "|---|---|---|"]
        out += [f"| {k} | {was.get(k, '—')} | {v} |" for k, v in now.items()]
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
            "| Top 5: new occupations under fast | Top 5 order differs | Largest score move in top 5 | Page verdict "
            "| Robust choice; depends on scenario (with why) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for x in s["people"]:
        out += [f"| {x['name']} ({x['kind']}) | {' / '.join(x['first'].values())} | {'yes' if x['first_changed'] else 'no'} "
                f"| {'—' if x['first_score_move'] is None else format(x['first_score_move'], '+g')} "
                f"| {x['top5_new_in_fast']} | {'yes' if x['top5_order_changed'] else 'no'} | {x['max_score_move']:g} "
                f"| {x['verdict']} | {robust_cell(x)} |"]
    out += ["", f"First move differs for {s['first_move_changed']} of 5; another occupation enters the top 5 for "
            f"{s['top5_set_changed']} of 5 (set or order differs for {s['top5_changed']}); the largest move of any "
            f"match score in a top 5 is {s['max_score_move']:g} points."
            + (f" Matches and Futures name a robust choice and give a why for every scenario-dependent one for "
               f"{s['robust_ok']} of 5 (robust = in the top {robust.ROBUST_TOP} under all three; depends = in the "
               f"top {robust.TOP} under only some, or moves {robust.RANK_SWING} places or more)."
               if "robust_ok" in s else ""), ""]
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
                "| # | Occupation | Field | AI share | Outlook change | Thin | ILO exposure | Second source |",
                "|---|---|---|---|---|---|---|---|"]
        out += [f"| {i} | {o['title']} | {o['field_id']}{' (manual)' if o['manual'] else ''} | {o['ai_share']:g}% | "
                f"{o['change']:+g} | {'yes' if o['thin'] else 'no'} | {'—' if o['ilo_mean'] is None else o['ilo_mean']} | "
                f"{o.get('second_source', 'not checked')} |"
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

    rn = r.get("real_news")
    if rn:
        out += [f"## 8. Real news — {mark(rn['pass']) if rn['checked'] else 'not checked'}", "",
                "Each item in `data/news.json` through the API on a log of its own (`scripts/news.py`): first an approval "
                "tried before any check (it must be refused), then the page opened and every quote and the date looked "
                f"for. Refused before the check: {rn['refused_unchecked']} of {len(rn['items'])}.", "",
                "| Item | Publisher, date | Page check | Proposed (method): activities; topics |", "|---|---|---|---|"]
        for x in rn["items"]:
            check = x["status"] if "quotes" not in x else (f"{x['status']}: {x['quotes_found']} of {x['quotes']} quotes, "
                                                          f"page date {x['page_date']}")
            out += [f"| [{x['id']}]({x['url']}) | {x['publisher']}, {x['published']} | {check} | ({x['method']}) "
                    f"{'; '.join(x['activities'] or []) or '—'}; {'; '.join(x['topics'] or []) or '—'} |"]
        d = rn["demo"]
        if d:
            out += ["", f"Approved, then undone, for {d['name']} (moderate adoption), `{d['id']}`:", "",
                    "| Own job | Before | Approved | Undone |", "|---|---|---|---|"]
            for label, key in (("Rank in the list", "rank"), ("Match score", "total"), ("AI share of its tasks (%)", "ai_share"),
                               ("Outlook", "outlook"), ("Status", "status")):
                out += [f"| {label} | " + " | ".join("—" if not d["own_job"][k] else str(d["own_job"][k][key])
                                                     for k in ("before", "approved", "undone")) + " |"]
            out += ["", f"Top 5 changed: {'yes' if d['top5_changed'] else 'no'}; top 10 order changed: "
                    f"{'yes' if d['top10_order_changed'] else 'no'}; undo restores the ranking and the data version: "
                    f"{'yes' if d['undo_restores'] else 'no'}. Rule-sized changes: "
                    + "; ".join(f"{x['name'].rstrip('.')} {x['before']:g} → {x['after']:g}" for x in d["rows"]) + "."]
        out += [""]

    lg = r.get("languages")
    if lg:
        out += [f"## 9. Languages and labels — {mark(lg['pass'])}", "",
                "Read from the page's own files by `scripts/i18n_check.py` (no browser): every `t(\"key\")` call, "
                f"the {lg['rows']} rows of the string tables, the markup in the scripts and `index.html`, the SDG reasons "
                "of `data/sdg_map.csv`, the Sources page's descriptions and the colour tokens of `style.css`. Occupation "
                "descriptions, task statements and course titles stay as their source wrote them and are not counted; "
                "occupation, skill and MASCO group names and course notes are counted against our own translation. A rule on source text: it can miss text built in an unusual way.", "",
                "| Page file (pages) | Missing keys | BM / ZH falling back to English | English written into the page "
                "| Fields with no label |", "|---|---|---|---|---|"]
        for f, x in lg["pages"].items():
            hard = f"{len(x['hardcoded'])}" + (f" ({'; '.join(x['hardcoded'])})" if x["hardcoded"] else "")
            unl = f"{len(x['unlabelled'])}" + (f" ({'; '.join(x['unlabelled'])})" if x["unlabelled"] else "")
            out += [f"| {f} ({x['pages']}) | {x['missing_keys']} | {x['fallback_ms']} / {x['fallback_zh']} | {hard} | {unl} |"]
        sd = lg["side"]
        out += ["", "Other tables, lines with no BM / ZH: " + "; ".join(
            f"{name.replace('_', ' ')} {v['missing_ms']} / {v['missing_zh']} of {v['rows']}" for name, v in sd.items())
            + f". Sources-page descriptions in English only: {lg['sources']['untranslated']} of {lg['sources']['parts']}."
            + ("" if "names" not in lg else " Names from the data with no BM / ZH line: " + "; ".join(
                f"{name.replace('_', ' ')} {v['missing_ms']} / {v['missing_zh']} of {v['rows']}" for name, v in lg["names"].items())
               + " (our own translation, not official).")
            + " Colour pairs below 4.5:1: " + ("none" if not lg["contrast_fail"] else "; ".join(
                f"{c['theme']} --{c['text']} on --{c['on']} {c['ratio']}:1" for c in lg["contrast_fail"])) + ".", ""]
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
