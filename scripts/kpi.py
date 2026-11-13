"""KPIs worked out by code from the data in this repository, so anyone can run them again.

Each has a definition, the value now (the baseline for a pilot), a target and how it is measured:

    coverage    of everything an occupation's O*NET profile asks for (skills and knowledge, weighted
                by importance), the share with at least one checked free resource; the mean over all
                occupations, and how many occupations fall under COVERAGE_FLOOR
    evidence    occupations by evidence grade A, B, C (scripts/evidence.py)
    scenarios   demo people whose first three occupations change between slow and fast adoption,
                and whether every list that holds says why (scripts/scenario_report.py)
    sourced     rows in the sourced tables, and rows the validator faults (scripts/validate_data.py)
    links       learning resources, and the oldest date one was last opened and checked

KPIs that need real users (people who can name a next step, hours studied per UN target) are
defined in docs/feasibility.md; they have no value until a pilot runs, and none is claimed here.

    python scripts/kpi.py            # print the report
    python scripts/kpi.py --write    # also save it as docs/kpi_report.md
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import evidence
import matching
import scenario_report
import validate_data

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_FLOOR = 50.0      # percent: an occupation under this has too little to study from
TARGETS = {"coverage": 90.0, "under_floor": 0, "grade_a_or_b": 70.0, "faults": 0, "links_days": 90}


def coverage(data: dict) -> dict:
    """Importance-weighted share of each occupation's skills and knowledge with a free resource."""
    has = {eid: bool(matching.resources_for(f"element:{eid}", data)) for eid in data["elements"]}
    shares = []
    for occ in data["occupations"]:
        rows = data["occ_elements"].get(occ["occ_id"], [])
        total = sum(imp for _, imp, _, _ in rows)
        if total:
            shares.append(100 * sum(imp for eid, imp, _, _ in rows if has[eid]) / total)
    return {"occupations": len(shares), "mean": round(sum(shares) / len(shares), 1), "lowest": round(min(shares), 1),
            "under_floor": sum(1 for s in shares if s < COVERAGE_FLOOR), "floor": COVERAGE_FLOOR,
            "elements": len(has), "elements_covered": sum(has.values())}


def grades(data: dict) -> dict:
    counts = {"A": 0, "B": 0, "C": 0}
    for occ in data["occupations"]:
        counts[evidence.occupation_grade(occ, data)["grade"]] += 1
    total = sum(counts.values())
    return {**counts, "total": total, "a_or_b": round(100 * (counts["A"] + counts["B"]) / total, 1)}


def scenarios(data: dict) -> dict:
    people = scenario_report.report(data)["people"]
    return {"people": len(people), "order_changed": sum(1 for p in people if p["top_order_changed"]),
            "set_changed": sum(1 for p in people if p["top_set_changed"]),
            "holds_explained": all(p["why_unchanged"] for p in people if not p["top_set_changed"])}


def sourced() -> dict:
    return {"tables": len(validate_data.SOURCED), "rows": sum(len(validate_data.read(t)) for t in validate_data.SOURCED),
            "faults": len(validate_data.check())}


def links(data: dict, today: date | None = None) -> dict:
    checked = sorted(r["verified_date"] for r in data["resources"] if r["verified_date"])
    oldest = date.fromisoformat(checked[0])
    return {"resources": len(data["resources"]), "checked": len(checked), "oldest_check": checked[0],
            "oldest_days": ((today or date.today()) - oldest).days}


def report(data: dict | None = None) -> dict:
    data = data or matching.load_data()
    return {"coverage": coverage(data), "evidence": grades(data), "scenarios": scenarios(data), "sourced": sourced(),
            "links": links(data), "targets": TARGETS, "computed": date.today().isoformat()}


def as_markdown(r: dict) -> str:
    c, e, s, d, k, t = r["coverage"], r["evidence"], r["scenarios"], r["sourced"], r["links"], r["targets"]
    rows = [
        ("Path coverage", f"{c['mean']:g}% (mean of {c['occupations']} occupations; lowest {c['lowest']:g}%)", f"{t['coverage']:g}%",
         "Of each occupation's O*NET skills and knowledge, weighted by importance, the share with a checked free resource"),
        ("Occupations with too little to study", f"{c['under_floor']} under {c['floor']:g}%", str(t["under_floor"]),
         "Same measure, counted per occupation"),
        ("Evidence grade A or B", f"{e['a_or_b']:g}% (A {e['A']}, B {e['B']}, C {e['C']})", f"{t['grade_a_or_b']:g}%",
         "Rule-based grade of each occupation: own-task AI data, exact mapping to Malaysia, fresh data"),
        ("Scenario check", f"top 3 changes for {s['order_changed']} of {s['people']} demo people; "
         f"every list that holds says why: {'yes' if s['holds_explained'] else 'no'}", "every list that holds says why",
         "Slow against fast adoption; no ranking is required to change"),
        ("Rows without a source", f"{d['faults']} faults in {d['rows']} rows of {d['tables']} tables", str(t["faults"]),
         "The data validator: source name, link and date on every row"),
        ("Oldest link check", f"{k['oldest_days']} days ({k['oldest_check']}; {k['checked']} of {k['resources']} resources checked)",
         f"under {t['links_days']} days", "The date each learning resource was last opened"),
    ]
    out = ["# KPIs computed from the repository", "",
           f"Generated by `python scripts/kpi.py --write` on {r['computed']}. Every value is worked out from the files in "
           "this repository; run the command to check it. The values are the baseline a pilot would start from. "
           "KPIs that need real users are defined in [feasibility.md](feasibility.md) and have no value yet.", "",
           "| KPI | Value now | Level to keep | How it is measured |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c_} | {d_} |" for a, b, c_, d_ in rows]
    out += ["", f"{c['elements_covered']} of {c['elements']} O*NET skills and knowledge areas have at least one checked free "
            "resource. Tools are left out of the coverage figure: most have no free course we have checked, and the "
            "learning page says so instead of pointing at one nobody has opened."]
    return "\n".join(out)


def main() -> int:
    cli = argparse.ArgumentParser(description="KPIs computed from the data in this repository.")
    cli.add_argument("--write", action="store_true", help="save the report as docs/kpi_report.md")
    opts = cli.parse_args()
    text = as_markdown(report())
    if opts.write:
        (ROOT / "docs" / "kpi_report.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
