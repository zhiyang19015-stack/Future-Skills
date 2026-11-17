"""Check the ISCO-08 unit group of occupations whose O*NET level clashes with ISCO's skill level, and write the result
as a table a person can review (data/isco_review.csv). With --apply, write the reviewed codes into
data/occupations.csv, link MyCOL again and rebuild Malaysian demand.

Why: an O*NET occupation reaches Malaysia (MyCOL, DOSM job ads by MASCO major group) through the ISCO-08 unit
group its ESCO matches vote for (scripts/build_onet.py). ISCO-08 puts every occupation of major group 2
(professionals) at skill level 4, a first degree or more (ILO, ISCO-08 Vol. 1, Table 2). An O*NET occupation
with Job Zone 3 or less needs less than a degree, so a major-group-2 code for it is suspect. 36 such
occupations got the professionals' job-ad signal and, for some, a MyCOL "yes".

The rule, the same for every flagged occupation (no hand-picked answers):
    1. Take the occupation's ESCO matches in the ESCO-O*NET crosswalk, closest kind of match first
       (exact, then close, then narrow; never broad), and each ESCO occupation's own ISCO-08 code
       (the first four digits of its ESCO code, from the ESCO API).
    2. Keep the codes whose major group's skill level fits the Job Zone (ISCO-08 Table 2: major group
       3 = skill level 3, 4 to 8 = 2, 9 = 1; Job Zone 3 = level 3, 2 = level 2, 1 = level 1).
    3. The closest kind of match with such a code decides; within it, the code most of its ESCO
       occupations share, ties to the lower code.  -> "corrected", with the ESCO occupations as evidence.
    4. No such code among its ESCO matches -> "unverified": the code stays, its mapping counts as
       unverified (no mapping points in the evidence grade) and a MyCOL link through it counts as "near".

    python scripts/isco_review.py                      # write data/isco_review.csv (needs raw/esco/)
    python scripts/isco_review.py --fetch              # also look up ESCO codes not in the cache (ESCO API)
    python scripts/isco_review.py --apply              # also apply it to occupations.csv, MyCOL and demand
"""

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = ROOT / "raw" / "esco"
CROSSWALK = RAW / "esco_onet_crosswalk.csv"
CACHE = RAW / "esco_lookup_targets.json"
GROUP_CACHE = RAW / "isco_group_titles.json"
OUT = DATA / "isco_review.csv"
API = "https://ec.europa.eu/esco/api/resource/"
# Broad matches are left out: a broad match names a wider ESCO occupation, which says nothing about which group
# the narrower O*NET occupation belongs to.
TIERS = ("exactMatch", "closeMatch", "narrowMatch")
# ISCO-08 skill level of each major group (ILO, ISCO-08 Vol. 1, Table 2); group 1 spans 3-4 and 0 has none.
SKILL_LEVEL = {"2": 4, "3": 3, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 1}
ZONE_LEVEL = {1: 1, 2: 2, 3: 3, 4: 4, 5: 4}
ISCO_SOURCE = ("ILO, ISCO-08 Structure, group definitions and correspondence tables (Vol. 1, Table 2: skill levels)",
               "https://www.ilo.org/public/english/bureau/stat/isco/isco08/")
ESCO_SOURCE = ("ESCO-O*NET crosswalk (EC and US DOL, Sep 2022) and the ESCO API (ESCO v1.1 codes)",
               "https://esco.ec.europa.eu/en/use-esco/other-crosswalks")


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def flagged(occ: list[dict]) -> list[dict]:
    return [o for o in occ if o["isco"][:1] == "2" and o["job_zone"] and int(o["job_zone"]) <= 3]


def crosswalk(ids: set) -> dict:
    rows = list(csv.reader(CROSSWALK.open(encoding="utf-8-sig", newline="")))
    head = next(i for i, r in enumerate(rows) if r and r[0] == "O*NET Id")
    out = {}
    for r in rows[head + 1:]:
        if r and r[0] in ids:
            link = dict(zip(rows[head], r))
            out.setdefault(r[0], []).append((link["Type of Match"], link["ESCO or ISCO Title"], link["ESCO or ISCO URI"]))
    return out


def get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "future-skills-isco-review"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:  # noqa: BLE001  (network: try again, then give up on this one)
            time.sleep(2 * (attempt + 1))
    return {}


def lookups(uris: set, fetch: bool) -> dict:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    missing = [u for u in sorted(uris) if u not in cache or not cache[u].get("code")]
    if fetch:
        for u in missing:
            d = get(API + "occupation?" + urllib.parse.urlencode({"uri": u, "language": "en"}))
            cache[u] = {"code": d.get("code"), "title": d.get("title")}
            time.sleep(0.2)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def code_of(uri: str, cache: dict) -> str | None:
    if "/isco/" in uri:
        return uri.rsplit("/C", 1)[-1][:4]
    c = (cache.get(uri) or {}).get("code")
    return c[:4] if c and len(c) >= 4 and c[:4].isdigit() else None


def group_titles(codes: set, occ: list[dict], fetch: bool) -> dict:
    titles = {o["isco"]: o["isco_title"] for o in occ if o["isco"] and o["isco_title"]}
    cache = json.loads(GROUP_CACHE.read_text(encoding="utf-8")) if GROUP_CACHE.exists() else {}
    titles.update(cache)
    if fetch:
        for c in sorted(codes - set(titles)):
            d = get(API + "concept?" + urllib.parse.urlencode({"uri": f"http://data.europa.eu/esco/isco/C{c}",
                                                                 "language": "en"}))
            if d.get("title"):
                cache[c] = titles[c] = d["title"][:1].upper() + d["title"][1:]
            time.sleep(0.2)
        GROUP_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return titles


def review(fetch: bool = False) -> list[dict]:
    occ = read(DATA / "occupations.csv")
    # Once applied, occupations.csv holds the reviewed codes: take each reviewed occupation's first code from the
    # table, so running again gives the same table.
    done = {r["occ_id"]: r for r in read(OUT)} if OUT.exists() else {}
    for o in occ:
        if o["occ_id"] in done:
            r = done[o["occ_id"]]
            o["isco"], o["isco_title"], o["isco_basis"] = r["isco_before"], r["isco_title_before"], r["basis_before"]
    targets = flagged(occ)
    links = crosswalk({o["occ_id"] for o in targets})
    cache = lookups({u for ls in links.values() for _, _, u in ls if "/occupation/" in u}, fetch)
    rows, new_codes = [], set()
    for o in targets:
        level = ZONE_LEVEL[int(o["job_zone"])]
        found, evidence = None, []
        for tier in TIERS:
            fits = [(title, code_of(uri, cache)) for kind, title, uri in links.get(o["occ_id"], []) if kind == tier]
            fits = [(t, c) for t, c in fits if c and SKILL_LEVEL.get(c[0], 0) and SKILL_LEVEL[c[0]] <= level]
            if fits:
                votes = Counter(c for _, c in fits)
                found = sorted(votes, key=lambda c: (-votes[c], c))[0]
                evidence = [f"{t} ({c}, {tier})" for t, c in fits if c == found]
                break
        all_links = "; ".join(f"{t} ({code_of(u, cache) or '?'}, {k})" for k, t, u in links.get(o["occ_id"], []))
        if found:
            new_codes.add(found)
        rows.append({"occ_id": o["occ_id"], "title": o["title"], "job_zone": o["job_zone"],
                     "isco_before": o["isco"], "isco_title_before": o["isco_title"], "basis_before": o["isco_basis"],
                     "verdict": "corrected" if found else "unverified", "isco_after": found or o["isco"],
                     "isco_title_after": "", "evidence": "; ".join(evidence) if found else
                     "no exact, close or narrow ESCO match of this occupation has an ISCO-08 code at its skill level",
                     "esco_matches": all_links, "checked_date": date.today().isoformat(),
                     "source_name": f"{ESCO_SOURCE[0]}; {ISCO_SOURCE[0]}", "source_url": ESCO_SOURCE[1],
                     "source_date": date.today().isoformat()})
    titles = group_titles(new_codes, occ, fetch)
    for r in rows:
        r["isco_title_after"] = titles.get(r["isco_after"], "") if r["verdict"] == "corrected" else r["isco_title_before"]
    return rows


def write(rows: list[dict]) -> None:
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def apply(rows: list[dict]) -> dict:
    """Write the reviewed codes into occupations.csv, link MyCOL again (build_onet.mycol_links) and rebuild demand."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_onet
    import demand
    path = DATA / "occupations.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols, occ = reader.fieldnames, list(reader)
    by = {r["occ_id"]: r for r in rows}
    for o in occ:
        r = by.get(o["occ_id"])
        if r:
            o["isco"], o["isco_title"], o["isco_basis"] = r["isco_after"], r["isco_title_after"], r["verdict"]
            o["masco_major"] = o["isco"][:1]
    isco = {o["occ_id"]: (o["isco"], o["isco_title"], o["isco_basis"]) for o in occ if o["isco"]}
    before = Counter(o["mycol"] for o in occ)
    links = build_onet.mycol_links({o["occ_id"]: o for o in occ}, isco)
    for o in occ:
        o["mycol"], o["mycol_occupation"] = links[o["occ_id"]]
    after = Counter(o["mycol"] for o in occ)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(occ)
    write_mycol_links(occ)
    demand.write_table(demand.build())
    return {"mycol_before": dict(before), "mycol_after": dict(after)}


def write_mycol_links(occ: list[dict]) -> None:
    """data/mycol_links.csv: every occupation counted on or near MyCOL, how, and the ESCO match behind it."""
    mycol = read(DATA / "mycol_map.csv")
    listed = {c.strip() for r in mycol for c in r["onet_codes"].split(";") if c.strip()}
    on_list = {r["isco"] for r in mycol if r["isco"]}
    linked = [o for o in occ if o["mycol"] in ("yes", "near")]
    esco = crosswalk({o["occ_id"] for o in linked})
    rows = []
    for o in linked:
        if o["occ_id"] in listed:
            how = "named by occupation code in data/mycol_map.csv"
        elif o["isco"] in on_list:
            how = {"broad": "unit group on the list, reached through broad ESCO matches only",
                   "unverified": "unit group on the list, but the code is unverified (data/isco_review.csv)",
                   "corrected": "unit group on the list, code corrected in data/isco_review.csv"}.get(
                o["isco_basis"], "unit group on the list, reached through exact or close ESCO matches")
        else:
            how = "another unit group of the same ISCO-08 minor group is on the list"
        best = [f"{t} ({k})" for k, t, _ in esco.get(o["occ_id"], []) if k in ("exactMatch", "closeMatch")]
        rows.append({"occ_id": o["occ_id"], "title": o["title"], "mycol": o["mycol"],
                     "mycol_occupation": o["mycol_occupation"], "isco": o["isco"], "isco_title": o["isco_title"],
                     "isco_basis": o["isco_basis"], "how": how, "esco_exact_or_close": "; ".join(best[:4]),
                     "source_name": "MyCOL 2024/2025 (data/mycol_map.csv); " + ESCO_SOURCE[0],
                     "source_url": ESCO_SOURCE[1], "source_date": date.today().isoformat()})
    with open(DATA / "mycol_links.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = review(a.fetch)
    write(rows)
    print(Counter(r["verdict"] for r in rows), "written", OUT.relative_to(ROOT))
    if a.apply:
        print(apply(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
