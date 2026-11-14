"""Check the data tables: every row has its source, every id it points to exists, every number is
in range. Run after rebuilding any table, and by the tests.

    python scripts/validate_data.py        exits 1 and prints each problem if any check fails
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCED = ("fields.csv", "occupations.csv", "elements.csv", "technologies.csv", "mycol_map.csv", "sdg_map.csv",
           "skill_topic_map.csv", "learning_resources.csv", "onet/skill_work_activities.csv", "cost_inputs.csv")
RESOURCE_FORMATS = {"course", "catalogue", "programme", "video", "claimable"}
SDG_TARGET = re.compile(r"^(1[0-7]|[1-9])\.([0-9]{1,2}|[a-g])$")


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value, lo: float, hi: float) -> bool:
    try:
        return lo <= float(value) <= hi
    except (TypeError, ValueError):
        return False


def check() -> list[str]:
    problems = []

    def need(ok: bool, text: str) -> None:
        if not ok:
            problems.append(text)

    for name in SOURCED:
        for i, r in enumerate(read(name), 2):
            for col in ("source_name", "source_url", "source_date"):
                need(bool((r.get(col) or "").strip()), f"{name} line {i}: no {col}")
            need(DATE.match(r.get("source_date") or "") is not None, f"{name} line {i}: source_date is not YYYY-MM-DD")

    fields = {r["field_id"] for r in read("fields.csv")}
    occupations = {r["occ_id"]: r for r in read("occupations.csv")}
    elements = {r["element_id"]: r for r in read("elements.csv")}
    techs = {r["tech_id"] for r in read("technologies.csv")}
    need(len(occupations) > 800, f"only {len(occupations)} occupations")
    for o in occupations.values():
        need(o["field_id"] in fields, f"{o['occ_id']}: unknown field {o['field_id']}")
        need(o["job_zone"] == "" or o["job_zone"] in "12345", f"{o['occ_id']}: job_zone {o['job_zone']}")
        need(o["mycol"] in ("yes", "near", "no"), f"{o['occ_id']}: mycol {o['mycol']}")
        need(o["isco"] == "" or re.fullmatch(r"\d{4}", o["isco"]) is not None, f"{o['occ_id']}: isco {o['isco']}")
        need(o["masco_major"] == o["isco"][:1], f"{o['occ_id']}: masco_major does not follow isco")
        for k in "RIASEC":
            need(o[f"score_{k}"] == "" or number(o[f"score_{k}"], 1, 7), f"{o['occ_id']}: score_{k} out of 1-7")
    for e in elements.values():
        need(e["kind"] in ("skill", "knowledge"), f"{e['element_id']}: kind {e['kind']}")
        need(bool(e["anchor_low"] and e["anchor_mid"] and e["anchor_high"]), f"{e['element_id']}: missing level examples")
    for i, r in enumerate(read("occupation_elements.csv"), 2):
        need(r["occ_id"] in occupations, f"occupation_elements line {i}: unknown occupation {r['occ_id']}")
        need(r["element_id"] in elements, f"occupation_elements line {i}: unknown element {r['element_id']}")
        need(number(r["importance"], 1, 5) and number(r["level"], 0, 7), f"occupation_elements line {i}: out of range")
    for i, r in enumerate(read("occupation_technologies.csv"), 2):
        need(r["occ_id"] in occupations and r["tech_id"] in techs, f"occupation_technologies line {i}: unknown id")
    for i, r in enumerate(read("related_occupations.csv"), 2):
        need(r["occ_id"] in occupations and r["related_id"] in occupations, f"related_occupations line {i}: unknown id")
    tasks = read("onet/tasks.csv")
    need(all(t["occ_id"] in occupations for t in tasks), "onet/tasks.csv has unknown occupations")
    need(len({t["occ_id"] for t in tasks}) == len(occupations), "an occupation has no tasks")

    for i, r in enumerate(read("skill_topic_map.csv"), 2):
        need(r["tech_id"] in techs, f"skill_topic_map line {i}: unknown technology {r['tech_id']}")
        need(bool(r["rationale"].strip()), f"skill_topic_map line {i}: no reason")

    for i, r in enumerate(read("sdg_map.csv"), 2):
        need(SDG_TARGET.match(r["sdg_target"]) is not None, f"sdg_map line {i}: target {r['sdg_target']}")
        need(r["sdg_target"].split(".")[0] == r["sdg_goal"], f"sdg_map line {i}: goal and target disagree")
        need(r["link_strength"] in ("direct", "indirect"), f"sdg_map line {i}: link_strength {r['link_strength']}")
        need(bool(r["rationale"].strip()), f"sdg_map line {i}: no reason")
        kind, code = r["entity_type"], r["entity_id"]
        known = {"field": code in fields, "element": code in elements,
                 "occupation": code in occupations, "broad": any(o.startswith(code) for o in occupations),
                 "minor": any(o.startswith(code) for o in occupations)}
        need(known.get(kind, False), f"sdg_map line {i}: unknown {kind} {code}")
    every_field = {r["entity_id"] for r in read("sdg_map.csv") if r["entity_type"] == "field"}
    need(every_field == fields, f"fields without an SDG link: {sorted(fields - every_field)}")

    targets_ok = re.compile(r"^(all|field:\d\d|element:[0-9A-Za-z.]+|tech:[a-z0-9-]+)$")
    seen_urls = set()
    for i, r in enumerate(read("learning_resources.csv"), 2):
        for t in filter(None, r["targets"].split(";")):
            need(targets_ok.match(t) is not None, f"learning_resources line {i}: bad target {t}")
            kind, _, code = t.partition(":")
            need({"all": True, "field": code in fields, "element": code in elements, "tech": code in techs}[kind],
                 f"learning_resources line {i}: unknown {t}")
        need(r["url"].startswith("https://"), f"learning_resources line {i}: url is not https")
        need(r["url"] not in seen_urls, f"learning_resources line {i}: the same url twice")
        seen_urls.add(r["url"])
        need(r["format"] in RESOURCE_FORMATS, f"learning_resources line {i}: format {r['format']}")
        if r["format"] == "claimable":  # paid, the employer claims it from HRD Corp: never counted as free
            need(r["cost_myr"] == "quote" or (number(r["cost_myr"], 1, 100000)),
                 f"learning_resources line {i}: a claimable course needs a fee or 'quote'")
            need("HRD" in r["notes"], f"learning_resources line {i}: say where the page states it is HRD Corp claimable")
        need(DATE.match(r["verified_date"]) is not None, f"learning_resources line {i}: verified_date")
        need(r["duration_hours"] == "" or number(r["duration_hours"], 0.1, 500), f"learning_resources line {i}: hours")

    for i, r in enumerate(read("regulated.csv"), 2):
        prefixes = [p for p in r["onet_prefixes"].split(";") if p]
        need(bool(prefixes) and all(any(o.startswith(p) for o in occupations) for p in prefixes),
             f"regulated line {i}: a prefix matches no occupation")
        need(bool(r["url"]) == bool(r["verified_date"]), f"regulated line {i}: a url needs its verified_date")

    for i, r in enumerate(read("my_restrictions.csv"), 2):
        ids = [o for o in r["occ_ids"].split(";") if o]
        need(bool(ids) and all(o in occupations for o in ids), f"my_restrictions line {i}: unknown occupation")
        need(r["source_url"].startswith("https://") and bool(r["source_name"]), f"my_restrictions line {i}: source")
        need(DATE.match(r["source_date"]) is not None, f"my_restrictions line {i}: source_date")

    for i, r in enumerate(read("mycol_map.csv"), 2):
        need(bool(r["isco"]) or bool(r["onet_codes"]) or r["basis"] == "not linked", f"mycol_map line {i}: no link")
        need(all(c in occupations for c in filter(None, r["onet_codes"].split(";"))), f"mycol_map line {i}: unknown code")

    for r in read("demand.csv"):
        need(r["occ_id"] in occupations and number(r["demand"], 0, 100), f"demand.csv: {r['occ_id']} out of range")
    for r in read("ai_occupations.csv"):
        need(number(r["ai_share_low"], 0, 100) and number(r["ai_share_high"], 0, 100)
             and float(r["ai_share_low"]) <= float(r["ai_share"]) <= float(r["ai_share_high"]),
             f"ai_occupations.csv: {r['occ_id']} share outside its range")

    people = json.loads((DATA / "sample_profiles.json").read_text(encoding="utf-8"))
    for p in people:
        need(all(f in fields for f in p.get("fields", {})), f"{p['profile_id']}: unknown field")
        need(all(e in elements for e in p.get("skills", {})), f"{p['profile_id']}: unknown skill")
        need(all(t in techs for t in p.get("technologies", [])), f"{p['profile_id']}: unknown technology")
        need(p.get("current_occupation") in (None, *occupations), f"{p['profile_id']}: unknown current_occupation")
        need(len(p.get("interest_answers", [])) in (0, 36), f"{p['profile_id']}: interest answers")
    items = json.loads((DATA / "interest_items.json").read_text(encoding="utf-8"))["items"]
    need(len(items) == 36 and all(sum(1 for x in items if x["type"] == k) == 6 for k in "RIASEC"),
         "interest_items.json: needs 6 statements of each of the 6 types")
    return problems


def main() -> int:
    problems = check()
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)" if problems else "All data checks passed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
