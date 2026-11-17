"""Reproducible evaluation on 40 held-out synthetic people, against labels written before the run.

Synthetic data, not validated with real people. The rules are in eval/LABELING.md: an independent
annotator labelled each person in eval/personas.json from their story alone (eval/labels.json),
and this script scores the app against those labels and against fixed rules:

    agreement     first move / any of the top 5 in the person's "acceptable" occupations;
                  any of the top 5 in their "not_acceptable" ones (moderate adoption)
    scenarios     whose first move, or the set of occupations in their top 5, differs between
                  slow and fast adoption
    plan          the learning plan for the first move (moderate adoption): courses that should
                  not be there (job-search courses for someone in work, a paid course in the free
                  plan, a course for a skill already at the level needed, the same course twice),
                  the share that is free, the share not in English

The same people go through three versions of the app:

    now           this checkout
    v2_before     commit 5e2a48f, the rewrite before the improvement plan (stages 1 to 5)
    v1            the competition version (pekoremon/future-skills, fdf158d), which knew 25 IT
                  roles only; it gets only what it can read (education, skills, tools), see v1_collect

Every share comes with a 95% Wilson interval. The 5 demo people (data/sample_profiles.json) were
used to tune stages 1 to 5, so they are reported apart as the tuning set.

    python scripts/eval.py                          # score this checkout, print the summary
    python scripts/eval.py --write                  # also write docs/eval_results.md and .json
    python scripts/eval.py --baselines --v1-root ../repo --write
                                                    # also run 5e2a48f (a temporary git worktree)
                                                    # and v1, and keep them in docs/eval_baselines.json
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import eval_personas  # noqa: E402

DOCS = ROOT / "docs"
BASELINES = DOCS / "eval_baselines.json"
V2_BEFORE = "5e2a48f"
SCENARIOS = ("slow", "moderate", "fast")
V1_SCENARIOS = {"slow": "local_demand", "moderate": "baseline", "fast": "fast_ai"}
TOP = 5
JOB_SEARCH = re.compile(r"\b(resume|résumé|cv|interview\w*|job search|cover letter)\b", re.I)
LABEL = "Synthetic data, not validated with real people."


# --- collecting: what each version recommends --------------------------------------------------------

def plan_items(page: dict) -> list[dict]:
    """The free plan of a learning page: Foundations (and v1's role stage) plus each skill's resources.
    Employer-paid and hands-on programmes are listed apart on the page and are not part of the plan."""
    items = []
    for st in page.get("stages", []):
        for r in st.get("resources", []):
            items.append({**r, "stage": st.get("id"), "skill_id": None})
    for s in page.get("skills", []):
        for r in s.get("resources", []) or []:
            items.append({**r, "stage": "skills", "skill_id": s.get("skill_id"), "skill_kind": s.get("kind"),
                          "your_level": s.get("your_level"), "level_needed": s.get("level_needed")})
    return [{k: x.get(k) for k in ("title", "url", "provider", "cost_myr", "language", "stage", "skill_id",
                                    "skill_kind", "your_level", "level_needed")} for x in items]


def v2_collect(persons: list[dict], app_root: Path = ROOT) -> list[dict]:
    """Run each person through the API of the checkout at app_root (in this process)."""
    sys.path.insert(0, str(app_root / "src"))
    import main  # noqa: E402

    def call(path, body):
        res = main.dispatch("POST", path, json.dumps(body).encode("utf-8"))
        return res.status, json.loads(res.body)

    out = []
    for x in persons:
        prof = x["app_profile"]
        rec = {"id": x["id"], "kind": prof.get("kind"), "current": prof.get("current_occupation"),
               "top": {}, "plan": None, "error": None}
        for sc in SCENARIOS:
            status, body = call("/api/match", {**prof, "scenario": sc, "top": 30})
            if status != 200:
                rec["error"] = f"match {sc}: HTTP {status}"
                break
            rec["top"][sc] = [{"occ_id": m["occ_id"], "title": m["title"]}
                              for m in body.get("results", []) if main.listed(m)][:TOP]
        first = (rec["top"].get("moderate") or [None])[0]
        if first and not rec["error"]:
            status, page = call("/api/learn", {**prof, "occ_id": first["occ_id"]})
            rec["plan"] = plan_items(page) if status == 200 else None
            if status != 200:
                rec["error"] = f"learn: HTTP {status}"
        out.append(rec)
    return out


def v1_profile(prof: dict, v1_skills: dict) -> dict:
    """What v1 can read of a profile: education, O*NET skill levels and tools. v1's interest items
    and its IT-area preferences have no counterpart here, so they are left out (its matcher scales the
    other parts up when one is missing)."""
    by_element = {s["onet_element_id"]: sid for sid, s in v1_skills.items() if s.get("onet_element_id")}
    by_name = {s["skill_name"].lower(): sid for sid, s in v1_skills.items() if s.get("skill_type") == "technology"}
    tech_names = {r["tech_id"]: r["name"].lower() for r in eval_personas.read_csv("technologies.csv")}
    skills = {by_element[e]: v for e, v in prof.get("skills", {}).items() if e in by_element}
    techs = [by_name[tech_names[t]] for t in prof.get("technologies", []) if tech_names.get(t) in by_name]
    return {"education_job_zone": prof["education_job_zone"], "skills": skills, "technologies": techs,
            "hours_per_week": prof.get("hours_per_week", 6)}


V1_RUNNER = r'''
import csv, json, sys
from pathlib import Path
root = Path(sys.argv[1]); sys.path.insert(0, str(root / "src")); sys.path.insert(0, str(root / "scripts"))
import main
lang = {r["resource_id"]: r.get("language", "") for r in csv.DictReader(open(root / "data" / "learning_resources.csv", encoding="utf-8"))}
req = json.load(sys.stdin)
def call(path, body):
    res = main.dispatch("POST", path, json.dumps(body).encode("utf-8"))
    return res.status, json.loads(res.body)
if req.get("skills_table"):
    print(json.dumps({r["skill_id"]: r for r in csv.DictReader(open(root / "data" / "skills.csv", encoding="utf-8"))})); sys.exit()
out = []
for x in req["people"]:
    rec = {"id": x["id"], "top": {}, "page": None, "error": None}
    for sc, v1sc in req["scenarios"].items():
        st, body = call("/api/match", {**x["profile"], "scenario": v1sc, "top": 25})
        if st != 200:
            rec["error"] = f"match {sc}: HTTP {st} {body}"; break
        keep = [m for m in body["results"] if not {"needs_extra_education", "not_for_it_graduates"} & set(m["flags"])]
        rec["top"][sc] = [{"role_id": m["role_id"], "occ_id": m.get("onet_soc"), "title": m.get("role_name_en") or m.get("name")} for m in keep]
    first = (rec["top"].get("moderate") or [None])[0]
    if first and not rec["error"]:
        st, page = call("/api/learn", {**x["profile"], "role_id": first["role_id"], "scenario": "baseline"})
        if st == 200:
            for s in page.get("stages", []) + page.get("skills", []):
                for r in s.get("resources", []) or []:
                    r["language"] = lang.get(r.get("id"), "")
            rec["page"] = page
        else:
            rec["error"] = f"learn: HTTP {st}"
    out.append(rec)
print(json.dumps(out))
'''


def v1_collect(persons: list[dict], v1_root: Path) -> list[dict]:
    """Run each person through the competition version, in its own process (its modules share names)."""
    def run(payload):
        done = subprocess.run([sys.executable, "-c", V1_RUNNER, str(v1_root)], input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8", cwd=v1_root, check=True)
        return json.loads(done.stdout.strip().splitlines()[-1])
    v1_skills = run({"skills_table": True})
    roles = {r["role_id"]: r for r in _read(v1_root / "data" / "roles.csv")}
    people = [{"id": x["id"], "profile": v1_profile(x["persona"]["profile"], v1_skills)} for x in persons]
    raw = run({"people": people, "scenarios": V1_SCENARIOS})
    by_id = {x["id"]: x for x in persons}
    out = []
    for r in raw:
        prof = by_id[r["id"]]["app_profile"]
        cur = prof.get("current_occupation")
        top = {}
        for sc, rows in r["top"].items():
            rows = [{"occ_id": roles[m["role_id"]]["onet_soc"], "title": roles[m["role_id"]]["role_name_en"]}
                    for m in rows]
            top[sc] = [m for m in rows if m["occ_id"] != cur][:TOP]
        out.append({"id": r["id"], "kind": prof.get("kind"), "current": cur, "top": top,
                    "plan": plan_items(r["page"]) if r["page"] else None, "error": r["error"]})
    return out


def _read(path: Path) -> list[dict]:
    import csv
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def v2_before_collect(persons: list[dict], commit: str) -> list[dict]:
    """Check out an older commit into a temporary git worktree and run this same script there."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "wt"
        subprocess.run(["git", "worktree", "add", "--detach", str(wt), commit], cwd=ROOT, check=True,
                       capture_output=True)
        try:
            payload = json.dumps([{"id": x["id"], "app_profile": x["app_profile"]} for x in persons])
            done = subprocess.run([sys.executable, str(Path(__file__)), "--collect-at", str(wt)], input=payload,
                                  capture_output=True, text=True, encoding="utf-8", cwd=wt, check=True)
            return json.loads(done.stdout.strip().splitlines()[-1])
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)


# --- scoring -----------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1))


def share(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "ci": [lo, hi]}


def plan_checks(rec: dict) -> dict:
    plan = rec["plan"] or []
    seen, dup = set(), 0
    for r in plan:
        dup += r["url"] in seen
        seen.add(r["url"])
    job = [r["title"] for r in plan if rec["kind"] == "working" and JOB_SEARCH.search(r["title"] or "")]
    paid = [r["title"] for r in plan if (r["cost_myr"] or 0) > 0]
    have = [r["title"] for r in plan if r.get("skill_kind") != "technology" and r.get("your_level") is not None
            and r.get("level_needed") is not None and r["your_level"] >= r["level_needed"]]
    unique = list({r["url"]: r for r in plan}.values())   # shares count each link once, as the page's hours do
    free = sum(1 for r in unique if r["cost_myr"] is not None and float(r["cost_myr"]) == 0)
    non_en = sum(1 for r in unique if (r["language"] or "en").lower() not in ("en", "english"))
    return {"resources": len(unique), "listed": len(plan), "job_search_for_working": job, "paid_in_plan": paid, "already_have": have,
            "duplicates": dup, "should_not": len(job) + len(paid) + len(have) + dup, "free": free, "non_english": non_en}


def score(records: list[dict], labels: dict) -> dict:
    rows = []
    for rec in records:
        lab = labels.get(rec["id"], {})
        ok, bad = set(lab.get("acceptable", [])), set(lab.get("not_acceptable", []))
        mod = rec["top"].get("moderate") or []
        ids = [m["occ_id"] for m in mod]
        slow = [m["occ_id"] for m in rec["top"].get("slow") or []]
        fast = [m["occ_id"] for m in rec["top"].get("fast") or []]
        row = {"id": rec["id"], "error": rec["error"], "first": mod[0]["title"] if mod else None,
               "first_id": ids[0] if ids else None, "top5": [m["title"] for m in mod],
               "first_ok": bool(ids) and ids[0] in ok, "top5_ok": bool(ok & set(ids)),
               "top5_bad": sorted(bad & set(ids)), "labelled": bool(lab),
               "first_changed": bool(slow and fast) and slow[0] != fast[0],
               "top5_set_changed": bool(slow and fast) and set(slow) != set(fast),
               "first_slow_fast": [rec["top"]["slow"][0]["title"] if slow else None,
                                   rec["top"]["fast"][0]["title"] if fast else None]}
        row["plan"] = plan_checks(rec)
        rows.append(row)
    return rows


def summary(rows: list[dict], group_of: dict) -> dict:
    def block(rs):
        n = len(rs)
        res = sum(r["plan"]["resources"] for r in rs)
        return {"people": n,
                "first_ok": share(sum(r["first_ok"] for r in rs), n),
                "top5_ok": share(sum(r["top5_ok"] for r in rs), n),
                "top5_bad": share(sum(bool(r["top5_bad"]) for r in rs), n),
                "first_changed": share(sum(r["first_changed"] for r in rs), n),
                "top5_set_changed": share(sum(r["top5_set_changed"] for r in rs), n),
                "resources": res, "listed": sum(r["plan"]["listed"] for r in rs),
                "should_not": sum(r["plan"]["should_not"] for r in rs),
                "should_not_by_rule": {k: sum(len(r["plan"][k]) if isinstance(r["plan"][k], list) else r["plan"][k]
                                              for r in rs)
                                       for k in ("job_search_for_working", "paid_in_plan", "already_have", "duplicates")},
                "free": share(sum(r["plan"]["free"] for r in rs), res),
                "non_english": share(sum(r["plan"]["non_english"] for r in rs), res),
                "no_plan": sum(1 for r in rs if not r["plan"]["resources"]),
                # added after the first run, to describe what it showed; not a target
                "distinct_first": len({r["first"] for r in rs if r["first"]}),
                "common_first": sorted(((t, sum(1 for r in rs if r["first"] == t)) for t in {r["first"] for r in rs if r["first"]}),
                                       key=lambda x: (-x[1], x[0]))[:5],
                "errors": sum(1 for r in rs if r["error"])}
    out = {"all": block(rows)}
    for g in ("student", "working", "switcher", "jobseeker"):
        out[g] = block([r for r in rows if group_of[r["id"]] == g])
    return out


# --- running -----------------------------------------------------------------------------------------

def labels_file() -> tuple[dict, str]:
    raw = eval_personas.LABELS.read_bytes().replace(b"\r\n", b"\n")
    return json.loads(raw.decode("utf-8"))["labels"], hashlib.sha256(raw).hexdigest()


def held_out() -> list[dict]:
    return [{"id": x["id"], "group": x["group"], "persona": x, "app_profile": eval_personas.app_profile(x)}
            for x in eval_personas.people()]


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def tuning_rows() -> dict:
    """The 5 demo people: no labels, so only the rule checks and scenario changes are scored."""
    sys.path.insert(0, str(ROOT / "src"))
    import main  # noqa: E402
    persons = [{"id": p["profile_id"], "app_profile": {"profile_id": p["profile_id"]}} for p in main.sample_profiles()]
    recs = v2_collect(persons)
    for r, p in zip(recs, main.sample_profiles()):
        r["kind"] = p.get("kind", "student")
    rows = score(recs, {})
    return {"people": len(rows), "first_changed": share(sum(r["first_changed"] for r in rows), len(rows)),
            "top5_set_changed": share(sum(r["top5_set_changed"] for r in rows), len(rows)),
            "should_not": sum(r["plan"]["should_not"] for r in rows),
            "free": share(sum(r["plan"]["free"] for r in rows), sum(r["plan"]["resources"] for r in rows)),
            "non_english": share(sum(r["plan"]["non_english"] for r in rows), sum(r["plan"]["resources"] for r in rows))}


DIAG_TOP = 50


def diagnosis(persons: list[dict], labels: dict) -> dict:
    """Why first moves concentrate, on this checkout: the score parts of each missed first move against the
    best-placed acceptable occupation, and how coarse the demand signal is. Describes, changes nothing."""
    import csv
    sys.path.insert(0, str(ROOT / "src"))
    import main  # noqa: E402
    parts = ("field", "interest", "skill", "outlook")
    leads, ahead, misses = {k: [] for k in parts}, {k: 0 for k in parts}, 0
    for x in persons:
        res = main.dispatch("POST", "/api/match", json.dumps({**x["app_profile"], "scenario": "moderate",
                                                              "top": DIAG_TOP}).encode("utf-8"))
        ranked = [m for m in json.loads(res.body).get("results", []) if main.listed(m)]
        ok = set(labels.get(x["id"], {}).get("acceptable", []))
        if not ranked or ranked[0]["occ_id"] in ok:
            continue
        best = next((m for m in ranked if m["occ_id"] in ok), None)
        if best is None:
            continue
        misses += 1
        for k in parts:
            a = (ranked[0]["components"].get(k) or {}).get("points") or 0.0
            b = (best["components"].get(k) or {}).get("points") or 0.0
            leads[k].append(a - b)
            ahead[k] += a > b
    occ = eval_personas.read_csv("occupations.csv")
    demand = [float(r["demand"]) for r in eval_personas.read_csv("demand.csv")]
    low = [o for o in occ if o["isco"][:1] == "2" and o["job_zone"] and int(o["job_zone"]) <= 3]
    yes = [o for o in occ if o["mycol"] == "yes"]
    return {"misses": misses, "lead": {k: round(sum(v) / len(v), 1) if v else 0.0 for k, v in leads.items()},
            "ahead": ahead, "occupations": len(occ), "demand_values": len(set(demand)), "demand_top": max(demand),
            "demand_top_n": sum(1 for v in demand if v == max(demand)), "mycol_yes": len(yes),
            "mycol_titles": len({o["mycol_occupation"] for o in yes}), "pro_low_zone": len(low),
            "pro_low_zone_examples": [f"{o['title']} → {o['isco']} {o['isco_title']}" for o in low
                                      if o["mycol"] == "yes"][:4]}


def run(with_baselines: bool = False, v1_root: Path | None = None) -> dict:
    labels, digest = labels_file()
    persons = held_out()
    group_of = {x["id"]: x["group"] for x in persons}
    versions = {}
    now_rows = score(v2_collect(persons), labels)
    versions["now"] = {"commit": commit(), "rows": now_rows, "summary": summary(now_rows, group_of)}
    base = json.loads(BASELINES.read_text(encoding="utf-8")) if BASELINES.exists() else {}
    if with_baselines:
        base = {"labels_sha256": digest, "made": date.today().isoformat(),
                "v2_before": {"commit": V2_BEFORE, "records": v2_before_collect(persons, V2_BEFORE)}}
        if v1_root:
            v1c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=v1_root, capture_output=True,
                                 text=True).stdout.strip()
            base["v1"] = {"commit": v1c, "records": v1_collect(persons, v1_root)}
    for name in ("v2_before", "v1"):
        if name in base:
            rows = score(base[name]["records"], labels)
            versions[name] = {"commit": base[name]["commit"], "rows": rows, "summary": summary(rows, group_of)}
    return {"date": date.today().isoformat(), "labels_sha256": digest, "label": LABEL, "versions": versions,
            "tuning_set": tuning_rows(), "diagnosis": diagnosis(persons, labels), "_baselines": base if with_baselines else None}


# --- report ------------------------------------------------------------------------------------------

def pct(s: dict) -> str:
    return "—" if s["pct"] is None else f"{s['pct']}% ({s['k']}/{s['n']}; {s['ci'][0]}–{s['ci'][1]})"


METRICS = [("first_ok", "First move agrees with the labels"), ("top5_ok", "Top 5 has a labelled-acceptable occupation"),
           ("top5_bad", "Top 5 has a labelled mistake (lower is better)"),
           ("first_changed", "First move differs, slow vs fast"), ("top5_set_changed", "Top 5 set differs, slow vs fast"),
           ("free", "Plan resources that are free"), ("non_english", "Plan resources not in English")]
NAMES = {"now": "Now", "v2_before": f"v2 before stages 1-5 ({V2_BEFORE})", "v1": "Competition v1"}
GROUP_NAMES = {"student": "Students", "working": "In work", "switcher": "Switchers", "jobseeker": "Job seekers"}


def as_markdown(r: dict) -> str:
    vs = [v for v in ("v1", "v2_before", "now") if v in r["versions"]]
    L = ["# Evaluation on 40 held-out synthetic people", "",
         f"**{LABEL}** Generated by `python scripts/eval.py --write` on {r['date']} at commit "
         f"`{r['versions']['now']['commit']}`. Every number below is computed by the script; none is typed by hand. "
         "Rules: [eval/LABELING.md](../eval/LABELING.md). People: [eval/personas.json](../eval/personas.json). "
         f"Labels: [eval/labels.json](../eval/labels.json), sha256 `{r['labels_sha256'][:16]}…`, written by an independent "
         "annotator that saw only the stories, before any of these people was run through the app.", "",
         "Each share: value (count/people; 95% Wilson interval). With 40 people an interval is about ±15 points wide, "
         "so small differences between versions are not evidence of anything.", "",
         "## All 40 people, three versions", "",
         "| Metric | " + " | ".join(f"{NAMES[v]} `{r['versions'][v]['commit']}`" for v in vs) + " |",
         "|---|" + "---|" * len(vs)]
    for key, name in METRICS:
        L.append(f"| {name} | " + " | ".join(pct(r["versions"][v]["summary"]["all"][key]) for v in vs) + " |")
    L.append("| Courses that should not be in the plan | "
             + " | ".join(f"{r['versions'][v]['summary']['all']['should_not']} of {r['versions'][v]['summary']['all']['listed']} listed"
                          for v in vs) + " |")
    for k, name in (("job_search_for_working", "  of which job-search courses for people in work"),
                    ("paid_in_plan", "  of which paid courses in the free plan"),
                    ("already_have", "  of which courses for a skill already at the level needed"),
                    ("duplicates", "  of which the same course listed twice (under two skills; its hours count once)")):
        L.append(f"| {name} | " + " | ".join(str(r["versions"][v]["summary"]["all"]["should_not_by_rule"][k]) for v in vs) + " |")
    L.append("| People with no learning plan | " + " | ".join(str(r["versions"][v]["summary"]["all"]["no_plan"]) for v in vs) + " |")
    L.append("| Different first moves among the people (added after the first run; describes it, not a target) | "
             + " | ".join(str(r["versions"][v]["summary"]["all"]["distinct_first"]) for v in vs) + " |")
    L.append("| Most common first moves (people) | " + " | ".join(
        "; ".join(f"{t} ({n})" for t, n in r["versions"][v]["summary"]["all"]["common_first"][:3]) for v in vs) + " |")
    L.append("| Errors | " + " | ".join(str(r["versions"][v]["summary"]["all"]["errors"]) for v in vs) + " |")
    L += ["", "How the versions were run: the same 40 profiles through each version's own API. "
          f"`{V2_BEFORE}` ran from a temporary git worktree. v1 knew 25 IT roles only and could read only education, "
          "skill levels and tools (its interest questions and IT-area preferences have no counterpart in these profiles), "
          "so most of its gap is coverage, not a better algorithm. v1 has no idea of a person's status, so its "
          "\"job-search courses for people in work\" are counted by the same rule.", "",
          "## Now, by group", "", "| Metric | " + " | ".join(GROUP_NAMES.values()) + " |", "|---|---|---|---|---|"]
    s = r["versions"]["now"]["summary"]
    for key, name in METRICS:
        L.append(f"| {name} | " + " | ".join(pct(s[g][key]) for g in GROUP_NAMES) + " |")
    L.append("| Courses that should not be in the plan | " + " | ".join(f"{s[g]['should_not']} of {s[g]['listed']} listed" for g in GROUP_NAMES) + " |")
    t = r["tuning_set"]
    L += ["", "## Tuning set (the 5 demo people, not in the numbers above)", "",
          "They have no labels; the stages 1 to 5 rules were tuned on them, so they are expected to look better.", "",
          f"First move differs slow vs fast: {pct(t['first_changed'])}; top 5 set differs: {pct(t['top5_set_changed'])}; "
          f"courses that should not be there: {t['should_not']}; free: {pct(t['free'])}; not in English: {pct(t['non_english'])}.", "",
          "## Every person, now", "",
          "| Person | Group | First move (moderate) | Agrees | Top 5 agrees | Labelled mistakes in top 5 | First move slow → fast | Plan: resources / should not / free / not English |",
          "|---|---|---|---|---|---|---|---|"]
    group_of = {x["id"]: x["group"] for x in eval_personas.people()}
    for row in r["versions"]["now"]["rows"]:
        p = row["plan"]
        L.append(f"| {row['id']} | {GROUP_NAMES[group_of[row['id']]]} | {row['first'] or '—'} | {'yes' if row['first_ok'] else 'no'} | "
                 f"{'yes' if row['top5_ok'] else 'no'} | {len(row['top5_bad'])} | {row['first_slow_fast'][0]} → {row['first_slow_fast'][1]} | "
                 f"{p['resources']} / {p['should_not']} / {p['free']} / {p['non_english']} |")
    d = r.get("diagnosis")
    if d:
        L += ["", "## Why first moves concentrate (found after the first run; nothing was changed because of it)", "",
              f"For each of the {d['misses']} people whose first move is not in their acceptable list, the first move is "
              f"compared with the best-placed acceptable occupation in their top {DIAG_TOP} (moderate adoption). "
              "Mean points the first move is ahead by, per part of the match score:", "",
              "| Part (weight) | Mean lead | First move ahead in |", "|---|---|---|"]
        L += [f"| {k} ({w}%) | {d['lead'][k]:+g} | {d['ahead'][k]} of {d['misses']} |"
              for k, w in (("field", 20), ("interest", 15), ("skill", 30), ("outlook", 35))]
        L += ["", f"- Malaysian demand, which is most of the outlook, has {d['demand_values']} distinct values over "
              f"{d['occupations']} occupations; {d['demand_top_n']} occupations share the top value {d['demand_top']:g} "
              "(on the MyCOL list, in the MASCO major group whose share of job ads grew most).",
              f"- {d['mycol_yes']} occupations count as on the MyCOL list, through {d['mycol_titles']} MyCOL titles: "
              "an occupation inherits \"yes\" from the ISCO-08 unit group it maps to.",
              f"- {d['pro_low_zone']} occupations map to ISCO major group 2 (professionals) while O*NET's job zone is 3 or "
              "less, for example: " + "; ".join(d["pro_low_zone_examples"]) + ". Such a mapping gives the "
              "professionals' job-ad signal. The raw ESCO crosswalk rows behind them have not been rechecked.",
              "- Any fix (finer demand, MyCOL by exact title, a checked crosswalk) has to be tested on new synthetic "
              "people, not on these 40."]
    L += ["", "## Limits", "",
          "- The people and their labels are synthetic. One annotator (an AI agent) wrote the labels; no second annotator "
          "checked them, so label noise is unmeasured.",
          "- Agreement means \"a counsellor would accept this\", not \"this person would succeed in it\".",
          "- Interest answers are made from each person's three liked types by one fixed rule "
          "(`scripts/eval_personas.py`), not answered by people.",
          "- Phase 1 KPI 1 (career clarity of 20+ real testers) cannot be measured this way: see "
          "[impact_verification.md](impact_verification.md) and the pilot plan in the README.", ""]
    return "\n".join(L)


def main_cli() -> int:
    cli = argparse.ArgumentParser(description="Evaluate the app on 40 held-out synthetic people.")
    cli.add_argument("--write", action="store_true", help="write docs/eval_results.md and docs/eval_results.json")
    cli.add_argument("--baselines", action="store_true", help=f"also run {V2_BEFORE} and v1 and keep their output")
    cli.add_argument("--v1-root", type=Path, help="a checkout of the competition version (for --baselines)")
    cli.add_argument("--collect-at", type=Path, help=argparse.SUPPRESS)  # used by v2_before_collect
    a = cli.parse_args()
    if a.collect_at:
        print(json.dumps(v2_collect(json.load(sys.stdin), a.collect_at.resolve())))
        return 0
    r = run(a.baselines, a.v1_root.resolve() if a.v1_root else None)
    base = r.pop("_baselines")
    for v, x in r["versions"].items():
        s = x["summary"]["all"]
        print(f"{v:10} first {pct(s['first_ok'])} | top5 {pct(s['top5_ok'])} | mistake {pct(s['top5_bad'])} | "
              f"first changes {pct(s['first_changed'])} | should-not {s['should_not']}/{s['listed']} | "
              f"free {pct(s['free'])} | non-EN {pct(s['non_english'])}")
    if a.write:
        if base:
            BASELINES.write_text(json.dumps(base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        (DOCS / "eval_results.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                               newline="\n")
        (DOCS / "eval_results.md").write_text(as_markdown(r), encoding="utf-8", newline="\n")
        print("wrote docs/eval_results.md and docs/eval_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
