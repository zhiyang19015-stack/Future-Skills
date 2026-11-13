"""Build the occupation tables of every O*NET occupation, with its link to Malaysia.

Reads the raw downloads (kept out of git, see SOURCES.md) and writes the tables the app reads:

    O*NET 31.0 database (CC BY 4.0)      occupations, their skills and knowledge (importance and
                                         level), technologies, interest profile (RIASEC), Job
                                         Zone, task statements, reported job titles, related
                                         occupations, and the level anchors behind the skills check
    ESCO-O*NET crosswalk (EC / US DOL)   each O*NET occupation's ESCO occupations, and through the
    + ESCO API                           ESCO classification their ISCO-08 unit group. MASCO 2020,
                                         Malaysia's classification, follows ISCO-08, so the ISCO
                                         code links an occupation to MyCOL and to DOSM's figures
                                         by MASCO major group.
    data/mycol_map.csv                   the MyCOL 2024/2025 occupations with their ISCO-08 code
                                         (or O*NET codes where MASCO has a title ISCO does not)

Written (each row keeps its source):
    data/occupations.csv                 one row per occupation with skill data
    data/elements.csv                    the 35 skills and 33 knowledge areas, with O*NET's
                                         examples of a low, middle and high level
    data/occupation_elements.csv         importance and level of each skill / knowledge area
                                         an occupation rates at least MIN_IMPORTANCE
    data/technologies.csv                every Hot or In Demand technology
    data/occupation_technologies.csv     which occupations list it
    data/occupation_titles.csv           job titles people in the occupation reported
    data/related_occupations.csv         O*NET's closest related occupations
    data/onet/tasks.csv                  every task statement with its importance and work activities
    data/onet/skill_work_activities.csv  O*NET's links from skills to generalized work activities

Usage: python scripts/build_onet.py [--raw DIR]      (default: $FS_RAW, else raw/)
Standard library only.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ONET_DIR = "onet_db_31_0_csv"
ONET_NAME = "O*NET 31.0 Database"
ONET_URL = "https://www.onetcenter.org/database.html"
ESCO_NAME = "ESCO-O*NET occupation crosswalk (European Commission and US DOL, Sep 2022) with ESCO v1.1 ISCO groups"
ESCO_URL = "https://esco.ec.europa.eu/en/use-esco/other-crosswalks"
CROSSWALK = "esco/esco_onet_crosswalk.csv"
ESCO_ISCO = "esco/esco_occupation_isco.json"

MIN_IMPORTANCE = 2.0        # O*NET's 1-5 importance; below "somewhat important" a skill is left out
RELATED_PER_OCCUPATION = 10
MATCH_WEIGHT = {"exactMatch": 3, "exactISCO": 3, "closeMatch": 2, "narrowMatch": 1, "broadMatch": 1}
RIASEC = {"1.B.1.a": "R", "1.B.1.b": "I", "1.B.1.c": "A", "1.B.1.d": "S", "1.B.1.e": "E", "1.B.1.f": "C"}
HIGH_POINTS = ("1.B.1.g", "1.B.1.h", "1.B.1.i")   # first, second and third interest high-point, 1-6 = R..C
ELEMENT_FILES = (("essential_skills.csv", "skill", "Essential"), ("transferable_skills.csv", "skill", "Transferable"),
                 ("knowledge.csv", "knowledge", "Knowledge"))
SKILL_GROUPS = {"2.A.1": "Basic", "2.A.2": "Learning and thinking", "2.B.1": "Working with people",
                "2.B.2": "Problem solving", "2.B.3": "Technical", "2.B.4": "Systems", "2.B.5": "Managing resources"}
KNOWLEDGE_GROUPS = {"2.C.1": "Business", "2.C.2": "Manufacturing and production", "2.C.3": "Engineering and technology",
                    "2.C.4": "Mathematics and science", "2.C.5": "Health services", "2.C.6": "Education and training",
                    "2.C.7": "Arts and humanities", "2.C.8": "Law and public safety", "2.C.9": "Communications",
                    "2.C.10": "Transportation"}


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name: str, rows: list[dict]) -> None:
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {len(rows):>6} rows to data/{name}")


def slug(text: str) -> str:
    """A stable id from a name: "C++" -> "c-plus-plus", "C#" -> "c-sharp", "Microsoft Excel" -> "microsoft-excel"."""
    text = text.lower().replace("++", " plus plus").replace("#", " sharp")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def ratings(rows: list[dict], keep: set) -> dict:
    """(occupation, element) -> {"IM": importance, "LV": level}, suppressed values left out."""
    out = defaultdict(dict)
    for r in rows:
        if r["O*NET-SOC Code"] not in keep or r["Recommend Suppress"] == "Y":
            continue
        if r["Scale ID"] == "LV" and r.get("Not Relevant") == "Y":
            continue
        out[(r["O*NET-SOC Code"], r["Element ID"])][r["Scale ID"]] = float(r["Data Value"])
    return out


def group_of(element_id: str) -> str:
    groups = SKILL_GROUPS if element_id.startswith("2.A") or element_id.startswith("2.B") else KNOWLEDGE_GROUPS
    for prefix in sorted(groups, key=len, reverse=True):
        if element_id == prefix or element_id.startswith(prefix + "."):
            return groups[prefix]
    return ""


def isco_codes(raw: Path) -> dict:
    """O*NET code -> (ISCO-08 unit group, its title, how it was found), by vote over ESCO matches.

    Only the closest kind of match an occupation has takes part (exact, else close, else
    narrow, else broad: MATCH_WEIGHT), so a few exact matches are not outvoted by many loose
    ones. Within it every ESCO occupation votes for its ISCO unit group; ties go to the lower
    code, so the result does not depend on file order. A management occupation (SOC 11) keeps to
    ISCO major group 1 (managers) whenever any of its matches is in it."""
    rows = list(csv.reader((raw / CROSSWALK).open(encoding="utf-8-sig", newline="")))
    head = next(i for i, r in enumerate(rows) if r and r[0] == "O*NET Id")
    links = [dict(zip(rows[head], r)) for r in rows[head + 1:] if r and r[0]]
    path = raw / ESCO_ISCO
    if not path.exists():
        print(f"  {path} is missing: only the crosswalk's direct ISCO links are used", file=sys.stderr)
    esco = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    votes, titles = defaultdict(dict), {}
    for link in links:
        uri, kind = link["ESCO or ISCO URI"], link["Type of Match"]
        if "/isco/" in uri:
            code, title = uri.rsplit("/C", 1)[-1], link["ESCO or ISCO Title"]
        else:
            found = esco.get(uri) or {}
            if not found.get("isco"):
                continue
            code = found["isco"][0].split("&")[0]
            title = (found.get("isco_title") or [""])[0]
        if len(code) != 4:
            continue
        soc, weight = link["O*NET Id"], MATCH_WEIGHT.get(kind, 1)
        votes[soc].setdefault(weight, Counter())[code] += 1
        if title or code not in titles:
            titles[code] = title
    out = {}
    for soc, tiers in votes.items():
        if soc.startswith("11-"):  # a manager stays a manager: keep ISCO major group 1 where it is offered
            managers = {w: Counter({c: n for c, n in t.items() if c.startswith("1")}) for w, t in tiers.items()}
            managers = {w: t for w, t in managers.items() if t}
            tiers = managers or tiers
        weight = max(tiers)
        counter = tiers[weight]
        code = sorted(counter, key=lambda c: (-counter[c], c))[0]
        out[soc] = (code, titles[code], {3: "exact", 2: "close"}.get(weight, "broad"))
    return out, titles


def mycol_links(occupations: dict, isco: dict) -> dict:
    """O*NET code -> (MyCOL status yes / near / no, the MyCOL occupation it is linked to).

    yes   the MyCOL list names the occupation itself (mycol_map.csv onet_codes), or its ISCO-08
          unit group, found through an exact or close ESCO match
    near  its ISCO-08 unit group is on the list but only through broad ESCO matches, or another
          unit group of the same ISCO-08 minor group is on the list
    no    neither"""
    rows = read(DATA / "mycol_map.csv")
    by_isco = {r["isco"]: r["occupation"] for r in rows if r["isco"]}
    by_onet = {}
    for r in rows:
        for code in filter(None, r["onet_codes"].split(";")):
            by_onet[code.strip()] = r["occupation"]
    minors = {}
    for code, name in by_isco.items():
        minors.setdefault(code[:3], name)
    out = {}
    for soc in occupations:
        code, _, basis = isco.get(soc, ("", "", "none"))
        if soc in by_onet:
            out[soc] = ("yes", by_onet[soc])
        elif code in by_isco:
            out[soc] = ("near" if basis == "broad" else "yes", by_isco[code])
        elif code and code[:3] in minors:
            out[soc] = ("near", minors[code[:3]])
        else:
            out[soc] = ("no", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", default=os.getenv("FS_RAW", str(ROOT / "raw")))
    raw = Path(ap.parse_args().raw)
    db = raw / ONET_DIR
    today = date.today().isoformat()
    onet_src = {"source_name": ONET_NAME, "source_url": ONET_URL, "source_date": today}

    titles = {r["O*NET-SOC Code"]: r for r in read(db / "occupation_data.csv")}
    fields = {r["field_id"]: r for r in read(DATA / "fields.csv")}

    print("[skills and knowledge]")
    element_rows, element_names = {}, {}
    for name, kind, _ in ELEMENT_FILES:
        rows = read(db / name)
        for r in rows:
            element_names.setdefault(r["Element ID"], (r["Element Name"], kind))
        element_rows[name] = rows
    with_skills = {r["O*NET-SOC Code"] for r in element_rows["essential_skills.csv"]}
    tasks_raw = read(db / "task_statements.csv")
    with_tasks = {r["O*NET-SOC Code"] for r in tasks_raw}
    keep = {soc for soc in titles if soc in with_skills and soc in with_tasks and soc[:2] in fields}
    rated = {}
    for name, _, _ in ELEMENT_FILES:
        rated.update(ratings(element_rows[name], keep))
    occ_elements = []
    for (soc, eid), v in sorted(rated.items()):
        if v.get("IM", 0) >= MIN_IMPORTANCE and "LV" in v:
            occ_elements.append({"occ_id": soc, "element_id": eid, "importance": f"{v['IM']:.2f}",
                                 "level": f"{v['LV']:.2f}"})

    described = {r["Element ID"]: r["Description"] for r in read(db / "content_model_reference.csv")}
    anchors = defaultdict(dict)
    for r in read(db / "level_scale_anchors.csv"):
        if r["Scale ID"] == "LV":
            anchors[r["Element ID"]][int(float(r["Anchor Value"]))] = r["Anchor Description"]
    elements = []
    for eid, (name, kind) in element_names.items():
        a = anchors.get(eid, {})
        low, mid, high = (sorted(a)[i] if len(a) > i else None for i in range(3))
        elements.append({"element_id": eid, "name": name, "kind": kind, "group": group_of(eid),
                         "description": described.get(eid, ""),
                         "anchor_low_level": low or "", "anchor_low": a.get(low, ""),
                         "anchor_mid_level": mid or "", "anchor_mid": a.get(mid, ""),
                         "anchor_high_level": high or "", "anchor_high": a.get(high, ""), **onet_src})
    elements.sort(key=lambda e: [int(x) if x.isdigit() else x for x in re.split(r"[.]", e["element_id"])])

    print("[interests, Job Zone, ISCO and MyCOL]")
    scores, high = defaultdict(dict), defaultdict(dict)
    for r in read(db / "career_interest_types.csv"):
        if r["Element ID"] in RIASEC and r["Scale ID"] == "OI":
            scores[r["O*NET-SOC Code"]][RIASEC[r["Element ID"]]] = float(r["Data Value"])
        elif r["Element ID"] in HIGH_POINTS and r["Scale ID"] == "IH":
            high[r["O*NET-SOC Code"]][HIGH_POINTS.index(r["Element ID"])] = int(float(r["Data Value"]))
    zones = {r["O*NET-SOC Code"]: r["Job Zone"] for r in read(db / "job_zones.csv")}
    isco, isco_titles = isco_codes(raw)
    mycol = mycol_links(keep, isco)

    occupations = []
    for soc in sorted(keep):
        s = scores.get(soc, {})
        points = [high[soc].get(i, 0) for i in range(3)]
        code = "".join("RIASEC"[p - 1] for p in points if 1 <= p <= 6)
        if not code and s:
            code = "".join(sorted(s, key=lambda k: -s[k])[:3])
        isco_code, isco_title, basis = isco.get(soc, ("", "", "none"))
        status, linked = mycol[soc]
        occupations.append({
            "occ_id": soc, "title": titles[soc]["Title"], "description": titles[soc]["Description"],
            "field_id": soc[:2], "minor_group": soc[:4], "job_zone": zones.get(soc, ""),
            "riasec": code, **{f"score_{k}": f"{s[k]:.2f}" if k in s else "" for k in "RIASEC"},
            "isco": isco_code, "isco_title": isco_title, "isco_basis": basis,
            "masco_major": isco_code[:1], "mycol": status, "mycol_occupation": linked,
            **onet_src, "isco_source_name": ESCO_NAME, "isco_source_url": ESCO_URL})
    missing_zone = [o["occ_id"] for o in occupations if not o["job_zone"]]
    if missing_zone:
        print(f"  {len(missing_zone)} occupations have no Job Zone: {', '.join(missing_zone[:5])}")

    print("[technologies]")
    techs, occ_techs = {}, []
    for r in read(db / "software_skills.csv"):
        soc = r["O*NET-SOC Code"]
        if soc not in keep or (r["Hot Technology"] != "Y" and r["In Demand"] != "Y"):
            continue
        tid = slug(r["Workplace Example"])
        t = techs.setdefault(tid, {"tech_id": tid, "name": r["Workplace Example"], "category": r["Element Name"],
                                   "occupations": 0, "hot": 0, "in_demand": 0, **onet_src})
        t["occupations"] += 1
        t["hot"] += r["Hot Technology"] == "Y"
        t["in_demand"] += r["In Demand"] == "Y"
        occ_techs.append({"occ_id": soc, "tech_id": tid, "hot": r["Hot Technology"], "in_demand": r["In Demand"]})
    occ_techs.sort(key=lambda r: (r["occ_id"], r["tech_id"]))

    print("[titles, related occupations, tasks]")
    reported = [{"occ_id": r["O*NET-SOC Code"], "title": r["Reported Job Title"],
                 "common": r["Shown in My Next Move"]}
                for r in read(db / "sample_of_reported_titles.csv") if r["O*NET-SOC Code"] in keep]
    related = []
    for r in read(db / "related_occupations.csv"):
        soc, other = r["O*NET-SOC Code"], r["Related O*NET-SOC Code"]
        if soc in keep and other in keep and int(r["Index"]) <= RELATED_PER_OCCUPATION:
            related.append({"occ_id": soc, "related_id": other, "tier": r["Relatedness Tier"], "rank": r["Index"]})

    task_rating = {}
    for r in read(db / "task_ratings.csv"):
        if r["O*NET-SOC Code"] in keep and r["Scale ID"] in ("IM", "RT") and r["Recommend Suppress"] != "Y":
            task_rating[(r["Task ID"], r["Scale ID"])] = r["Data Value"]
    ref = {r["DWA Element ID"]: r for r in read(db / "gwas_to_iwas_to_dwas.csv")}
    dwas = defaultdict(list)
    for r in read(db / "tasks_to_dwas.csv"):
        if r["O*NET-SOC Code"] in keep:
            dwas[r["Task ID"]].append(r["DWA Element ID"])
    emerging = {(r["O*NET-SOC Code"], r["Task"].strip().lower()) for r in read(db / "emerging_tasks.csv")
                if r["Category"] == "New"}
    tasks = []
    for t in tasks_raw:
        soc = t["O*NET-SOC Code"]
        if soc not in keep:
            continue
        mine = [ref[d] for d in dwas.get(t["Task ID"], []) if d in ref]

        def joined(key, mine=mine):
            return " | ".join(dict.fromkeys(m[key] for m in mine))
        tasks.append({"occ_id": soc, "task_id": t["Task ID"], "task": t["Task"],
                      "task_type": t["Task Type"] or "Unrated",
                      "importance": task_rating.get((t["Task ID"], "IM"), ""),
                      "relevance": task_rating.get((t["Task ID"], "RT"), ""),
                      "dwa_names": joined("DWA Element Name"), "iwa_names": joined("IWA Element Name"),
                      "gwa_ids": joined("GWA Element ID"),
                      "emerging": "Y" if (soc, t["Task"].strip().lower()) in emerging else "N"})
    tasks.sort(key=lambda r: (r["occ_id"], r["task_type"] != "Core", -float(r["importance"] or 0), int(r["task_id"])))

    links = []
    for name, kind in (("essential_skills_to_work_activities.csv", "Essential Skills"),
                       ("transferable_skills_to_work_activities.csv", "Transferable Skills")):
        for r in read(db / name):
            links.append({"element_id": r[f"{kind} Element ID"], "element_name": r[f"{kind} Element Name"],
                          "gwa_id": r["Work Activities Element ID"], "gwa_name": r["Work Activities Element Name"],
                          **onet_src})

    write("occupations.csv", occupations)
    write("elements.csv", elements)
    write("occupation_elements.csv", occ_elements)
    write("technologies.csv", sorted(techs.values(), key=lambda t: (-t["occupations"], t["name"])))
    write("occupation_technologies.csv", occ_techs)
    write("occupation_titles.csv", reported)
    write("related_occupations.csv", related)
    write("onet/tasks.csv", tasks)
    write("onet/skill_work_activities.csv", links)

    by_field = Counter(o["field_id"] for o in occupations)
    status = Counter(o["mycol"] for o in occupations)
    basis = Counter(o["isco_basis"] for o in occupations)
    print(f"{len(occupations)} occupations in {len(by_field)} fields; ISCO by {dict(basis)}; MyCOL {dict(status)}")
    print(f"{len(isco_titles)} ISCO unit groups seen in the crosswalk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
