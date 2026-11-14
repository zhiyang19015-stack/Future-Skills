"""Impact against the Phase 1 proposal, worked out by code so anyone can run it again.

The Phase 1 proposal (preliminary round, October 2026) set two KPIs for SDG target 4.4:

    KPI 1  career clarity      at least 70% of 20 or more student testers can name a target role,
                               its top missing skills and a next course after one session
    KPI 2  pathway coverage    the share of needed skills with at least one manually checked free
                               course: baseline 14.0% (26 of 186 skills of 25 IT roles), target 40%

This script reports, from the files in this repository:

    coverage    KPI 2 now, at the proposal's IT scope and over every occupation
    journey     what KPI 1 needs from the product, checked on synthetic people: for how many of them
                the app names a target occupation, at least two skill gaps and a checked free course.
                It is a test run of the system, not a measure of people: KPI 1 itself needs real
                testers and has no value in this repository (see docs/feasibility.md)
    cost        how much of each path is free, and how many occupations also list an HRD
                Corp-claimable course an employer can pay for
    sdg         the free study hours the demo people's paths put towards each SDG target

    python scripts/impact_report.py            # print the report
    python scripts/impact_report.py --write    # also save it as docs/impact_verification.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import kpi
import learning
import matching

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = {"coverage_baseline": 14.0, "coverage_baseline_n": "26 of 186 skills", "coverage_target": 40.0,
          "clarity_target": 70.0, "clarity_testers": 20}
SAMPLE_EVERY = 10          # one synthetic working adult for every 10th occupation, in occ_id order
NOT_A_MOVE = {"needs_extra_education", "below_education", "current_occupation", "restricted_my"}
IT_FIELD = "15"


def it_coverage(data: dict) -> dict:
    """KPI 2 at the proposal's scope: occupations in the Computer and Mathematical field."""
    has = {eid: bool(matching.resources_for(f"element:{eid}", data)) for eid in data["elements"]}
    shares = []
    for occ in data["occupations"]:
        if occ["field_id"] != IT_FIELD:
            continue
        rows = data["occ_elements"].get(occ["occ_id"], [])
        total = sum(imp for _, imp, _, _ in rows)
        if total:
            shares.append(100 * sum(imp for eid, imp, _, _ in rows if has[eid]) / total)
    return {"occupations": len(shares), "mean": round(sum(shares) / len(shares), 1), "lowest": round(min(shares), 1)}


def synthetic_people(data: dict) -> list[dict]:
    """The five demo people, then a working adult in every SAMPLE_EVERY-th occupation: their job,
    its field and its usual education, nothing else (the app adds the job's own skill levels)."""
    people = json.loads((ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8"))
    for occ in sorted(data["occupations"], key=lambda o: o["occ_id"])[::SAMPLE_EVERY]:
        people.append({"profile_id": f"S-{occ['occ_id']}", "kind": "working", "current_occupation": occ["occ_id"],
                       "education_job_zone": int(occ["job_zone"] or 3), "fields": {occ["field_id"]: 100}})
    return people


def journey(person: dict, data: dict) -> dict:
    """Target occupation, named gaps and a checked free course for one person, as the app gives them."""
    found = matching.match_person(person, data, futures=0, top=10)
    move = next((m for m in found["results"] if not NOT_A_MOVE & set(m["flags"])), None)
    if move is None:
        return {"id": person["profile_id"], "target": None, "gaps": 0, "free_course": False, "claimable": 0,
                "hours": 0.0, "sdg": {}}
    page = learning.page(move["occ_id"], data, move)
    gaps = [s for s in page["skills"] if s.get("level_needed", 0) > s.get("your_level", 0) or s["kind"] == "technology"]
    return {"id": person["profile_id"], "target": move["title"], "gaps": len(gaps),
            "free_course": any(s["resources"] for s in page["skills"]) or bool(page["stages"][0]["resources"]),
            "claimable": len(page["claimable"]), "hours": page["total_hours"],
            "sdg": {t["target"]: t["hours"] for t in page["sdg"]}}


def report(data: dict | None = None) -> dict:
    data = data or matching.load_data()
    cov = kpi.coverage(data)
    runs = [journey(p, data) for p in synthetic_people(data)]
    clear = [r for r in runs if r["target"] and r["gaps"] >= 2 and r["free_course"]]
    with_hrd = sum(1 for o in data["occupations"] if learning.page(o["occ_id"], data)["claimable"])
    demo = [r for r in runs if not r["id"].startswith("S-")]
    sdg = {}
    for r in demo:
        for target, hours in r["sdg"].items():
            sdg[target] = round(sdg.get(target, 0.0) + hours, 1)
    return {"phase1": PHASE1, "coverage": cov, "it": it_coverage(data),
            "journey": {"people": len(runs), "clear": len(clear), "share": round(100 * len(clear) / len(runs), 1),
                        "missing": [r["id"] for r in runs if r not in clear]},
            "cost": {"occupations": len(data["occupations"]), "with_hrd": with_hrd,
                     "hrd_courses": sum(1 for r in data["resources"] if r["format"] == "claimable")},
            "demo": demo, "sdg": dict(sorted(sdg.items(), key=lambda kv: -kv[1])),
            "computed": date.today().isoformat()}


def as_markdown(r: dict) -> str:
    p, c, it, j, k = r["phase1"], r["coverage"], r["it"], r["journey"], r["cost"]
    element_share = round(100 * c["elements_covered"] / c["elements"], 1)
    met = "met" if it["mean"] >= p["coverage_target"] else "not met"
    out = [
        "# Impact against the Phase 1 baseline", "",
        f"Generated by `python scripts/impact_report.py --write` on {r['computed']}. Every value is worked out from the "
        "files in this repository; run the command to check it.", "",
        "## The Phase 1 KPIs and where they stand", "",
        "| KPI (Phase 1 proposal, SDG 4.4) | Phase 1 baseline | Phase 2 target | Now | Status |",
        "|---|---|---|---|---|",
        f"| 2. Pathway coverage: share of needed skills with a checked free course | {p['coverage_baseline']:g}% "
        f"({p['coverage_baseline_n']}, 25 IT roles) | {p['coverage_target']:g}% | IT occupations: {it['mean']:g}% "
        f"(mean of {it['occupations']}, lowest {it['lowest']:g}%); all {c['occupations']} occupations: {c['mean']:g}%; "
        f"{c['elements_covered']} of {c['elements']} O*NET skills and knowledge areas ({element_share:g}%) | {met} |",
        f"| 1. Career clarity: testers who can name a target role, its top missing skills and a next course | "
        f"asked before the session | {p['clarity_target']:g}% of {p['clarity_testers']}+ testers | not measured with "
        "people in this version | open: needs the pilot in [feasibility.md](feasibility.md) |", "",
        "The unit of KPI 2 changed with the rewrite: Phase 1 counted 186 skills of our own list for 25 IT roles; this "
        "version uses O*NET's skills and knowledge areas, weighted by how important each is to the occupation. Both "
        "count a skill only when a free resource for it has a link we opened and dated.", "",
        "An earlier version reported a career-clarity result from 20 testers. Its response sheet does not support "
        "that number, so it is withdrawn and not used here.", "",
        "## What KPI 1 needs from the product, checked on synthetic people", "",
        f"For a person to name a target role, its missing skills and a next course, the app must give all three. "
        f"Run on {j['people']} synthetic people (the 5 demo people and a working adult in every {SAMPLE_EVERY}th "
        f"occupation, with only their job, field and usual education), the app gave a target occupation, at least "
        f"two skill gaps and a checked free course for **{j['clear']} of {j['people']} ({j['share']:g}%)**. "
        "This tests the system, not people: it is the ceiling KPI 1 can reach, not a result for KPI 1.", "",
    ]
    if j["missing"]:
        out += [f"Not complete for: {', '.join(j['missing'])}.", ""]
    out += [
        "## Learning cost", "",
        "Every step of a learning plan is free: paid courses are never in the plan, its hours or its count. "
        f"{k['hrd_courses']} HRD Corp-claimable courses, each with the provider page that says so, are listed apart "
        f"for working adults whose employer can claim them: {k['with_hrd']} of {k['occupations']} occupations "
        f"({round(100 * k['with_hrd'] / k['occupations'], 1):g}%) have at least one that teaches their own skills.", "",
        "| Demo person | Target occupation | Gaps on the path (up to 10 shown) | Free hours | HRD Corp options |", "|---|---|---|---|---|",
    ]
    out += [f"| {d['id']} | {d['target']} | {d['gaps']} | {d['hours']:g} | {d['claimable']} |" for d in r["demo"]]
    out += ["", "## SDG targets the demo paths serve", "",
            "Free study hours on the five demo people's first paths, added up per target (`scripts/learning.py`: "
            "every hour counts towards the occupation's own targets; a skill's targets get the hours of the "
            "resources that teach it). Planned hours, not hours studied: studied hours come from the anonymous "
            "tally on the SDG page once people use it.", "",
            "| SDG target | Planned free hours |", "|---|---|"]
    out += [f"| {t} | {h:g} |" for t, h in r["sdg"].items() if h]
    out += ["", "## How to check", "",
            "```bash", "python scripts/impact_report.py   # this report", "python scripts/kpi.py             # the KPI baseline",
            "python scripts/check_links.py     # opens every course link again", "python -m pytest -q tests/test_impact_report.py",
            "```"]
    return "\n".join(out)


def main() -> int:
    cli = argparse.ArgumentParser(description="Impact against the Phase 1 baseline, from the data in this repository.")
    cli.add_argument("--write", action="store_true", help="save the report as docs/impact_verification.md")
    opts = cli.parse_args()
    text = as_markdown(report())
    if opts.write:
        (ROOT / "docs" / "impact_verification.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
