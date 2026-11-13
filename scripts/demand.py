"""Malaysian demand for every occupation, and the pace of AI research ("Update data").

Two kinds of input, both written to data/demand_inputs.csv by update():

    DOSM Job Market Insights   online job ads by MASCO major group, per quarter, from DOSM's
    (raw/dosm/jmi_data_*.xlsx)  "Data JMI" workbook (the newest file in raw/dosm/). DOSM's series
                               breaks in 2025 Q3 (all ads +109% in one quarter, no reason given),
                               so windows never cross BREAK_QUARTER.
    OpenDOSM wages_occupation  median monthly wage by MASCO major group (context only, not scored)
    arXiv API                  papers whose abstract mentions AI or large language models, and all
                               papers, in the last two 6-month windows (global research pace)
    MyCOL 2024/2025            the official critical-occupations list, already linked to each
                               occupation in data/occupations.csv (scripts/build_onet.py)

build() turns them into, for each occupation:

    signals, each a strength from -1 (falling) to 1 (rising) and a confidence:
        mycol      yes 1, near 0.5 (same ISCO-08 minor group as a listed occupation), no 0;
                   confidence high for yes and no, medium for near
        job_ads    change in the share of all online job ads held by the occupation's MASCO
                   major group, last two quarters against the two before (both after the
                   break): strength = change / SHARE_FULL_PCT, capped at -1 and 1; medium
                   confidence, since a major group stands in for the occupation
    demand   = 50 + 50 x sum(weight x strength) / sum(weight), weight = CONFIDENCE
    momentum = 50 + 50 x (growth of AI papers on arXiv / ARXIV_FULL_PCT), capped at 0 and 100
               (the same for every occupation; outlook.py turns it into the tempo of adoption)

Every threshold here is our own assumption, listed on the Sources page.

Usage:
    python scripts/demand.py              # update the inputs (arXiv takes ~20 s), then rebuild
    python scripts/demand.py --no-arxiv   # keep the previous arXiv counts
    python scripts/demand.py --build      # rebuild data/demand.csv from the inputs only
Standard library only.
"""

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DOSM = ROOT / "raw" / "dosm"
INPUTS = DATA / "demand_inputs.csv"
OUT = DATA / "demand.csv"
FORMULA_VERSION = "v5-all-occupations"

BREAK_QUARTER = (2025, 3)
SHARE_FULL_PCT = 20.0     # a 20% relative change in a group's share of ads is full strength
ARXIV_FULL_PCT = 40.0     # +40% growth of AI papers in six months is full momentum
MYCOL_STRENGTH = {"yes": 1.0, "near": 0.5, "no": 0.0}
MYCOL_CONFIDENCE = {"yes": "high", "near": "medium", "no": "high"}
CONFIDENCE = {"high": 1.0, "medium": 2 / 3, "low": 1 / 3}
NEUTRAL = 50.0

MASCO_MAJOR = {  # MASCO 2020 major group -> label in DOSM's JMI workbook, OpenDOSM wages id, name
    "1": ("Managers", "managers", "Managers"),
    "2": ("Professionals", "professionals", "Professionals"),
    "3": ("Technicians and associate professionals", "technicians", "Technicians and associate professionals"),
    "4": ("Clerical support workers", "clerical", "Clerical support workers"),
    "5": ("Service and sales workers", "service_sales", "Service and sales workers"),
    "6": ("Skilled agricultural, forestry, livestock and fishery workers", "agriculture",
          "Skilled agricultural, forestry, livestock and fishery workers"),
    "7": ("Craft and related trades workers", "craft", "Craft and related trades workers"),
    "8": ("Plant and machine operators and assemblers", "operators", "Plant and machine operators and assemblers"),
    "9": ("Elementary Occupations", "elementary", "Elementary occupations"),
}
JMI_TOTAL = "Jumlah"
JMI_SOURCE = "DOSM Big Data Analytics: Job Market Insights, data file"
JMI_URL = "https://www.dosm.gov.my/portal-main/release-document-log?release_document_id=20742"
# When DOSM released each workbook and when it was downloaded into raw/dosm/; add a line per new file.
JMI_DATES = {"jmi_data_2026q2.xlsx": ("2026-08-18", "2026-10-23")}
WAGES_API = "https://api.data.gov.my/data-catalogue/"
WAGES_PAGE = "https://open.dosm.gov.my/data-catalogue/wages_occupation"
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_AI = ('(abs:"large language model" OR abs:LLM OR abs:"artificial intelligence" OR abs:"machine learning" '
            'OR abs:"deep learning" OR abs:"neural network" OR abs:"generative AI")')
ARXIV_DELAY_S = 3
FIELDS = ["input_id", "kind", "entity", "metric", "value", "period_start", "period_end", "note",
          "source_name", "source_url", "release_date", "fetched_date"]
TODAY = dt.date.today().isoformat()


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {len(rows):>4} rows to {path.relative_to(ROOT)}")


def clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# --- fetching -------------------------------------------------------------------------------------

def http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "future-skills-data-update"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def xlsx_rows(path: Path) -> list[list]:
    """The first worksheet of an .xlsx file as rows of values (numbers as floats)."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{ns}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.iter(f"{ns}row"):
        out = {}
        for c in row.iter(f"{ns}c"):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            index = 0
            for ch in col:
                index = index * 26 + ord(ch) - 64
            v = c.find(f"{ns}v")
            if v is None:
                inline = c.find(f"{ns}is")
                out[index - 1] = "".join(t.text or "" for t in inline.iter(f"{ns}t")) if inline is not None else None
            elif c.get("t") == "s":
                out[index - 1] = shared[int(v.text)]
            elif c.get("t") in ("str", "inlineStr"):
                out[index - 1] = v.text
            else:
                try:
                    out[index - 1] = float(v.text)
                except (TypeError, ValueError):
                    out[index - 1] = v.text
        rows.append([out.get(i) for i in range(max(out) + 1)] if out else [])
    return rows


def jmi_quarters(rows: list[list], title: str) -> dict:
    """{row label: {(year, quarter): ads}} for one table of the workbook (its quarterly block)."""
    start = next(i for i, r in enumerate(rows) if any(isinstance(x, str) and x.startswith(title) for x in r))
    yrow = next(i for i in range(start, start + 6) if any(isinstance(x, float) and 2015 < x < 2040 for x in rows[i]))
    cols, year = {}, None
    head, labels = rows[yrow], rows[yrow + 1]
    for j in range(max(len(head), len(labels))):
        y = head[j] if j < len(head) else None
        q = labels[j] if j < len(labels) else None
        if isinstance(y, float):
            year = int(y)
        if isinstance(q, str) and re.fullmatch(r"Q[1-4]", q.strip()):
            cols[j] = (year, int(q.strip()[1]))
        elif cols and isinstance(q, str):
            break  # the monthly block starts
    table = {}
    for r in rows[yrow + 2:]:
        label = next((x.strip() for x in r[:2] if isinstance(x, str)), None)
        if label is None or label.startswith("Source"):
            break
        table[label] = {yq: r[j] for j, yq in cols.items() if j < len(r) and isinstance(r[j], float)}
    return table


def newest_workbook() -> Path:
    files = sorted(RAW_DOSM.glob("jmi_data_*.xlsx"))
    if not files:
        sys.exit("No DOSM Data JMI workbook in raw/dosm/ (jmi_data_<year>q<quarter>.xlsx)")
    return files[-1]


def job_ad_rows() -> list[dict]:
    path = newest_workbook()
    m = re.search(r"(\d{4})q(\d)", path.name)
    table = jmi_quarters(xlsx_rows(path), "Table 2")
    out = []
    for entity, label in [("all", JMI_TOTAL)] + [(k, v[0]) for k, v in MASCO_MAJOR.items()]:
        for (y, q), value in sorted(table.get(label, {}).items()):
            if (y, q) < BREAK_QUARTER:
                continue
            start = dt.date(y, 3 * q - 2, 1)
            end = (dt.date(y + (q == 4), (3 * q) % 12 + 1, 1) - dt.timedelta(days=1))
            out.append({"kind": "job_ads", "entity": entity, "metric": "online_job_ads", "value": int(value),
                        "period_start": start.isoformat(), "period_end": end.isoformat(),
                        "note": f"{label}; quarters from {BREAK_QUARTER[0]} Q{BREAK_QUARTER[1]} (series break) on",
                        "source_name": f"{JMI_SOURCE} ({m.group(1)} Q{m.group(2)})" if m else JMI_SOURCE,
                        "source_url": JMI_URL, "release_date": JMI_DATES.get(path.name, ("", ""))[0],
                        "fetched_date": JMI_DATES.get(path.name, ("", ""))[1]})
    return out


def wage_rows() -> list[dict]:
    q = urllib.parse.urlencode({"id": "wages_occupation", "limit": 5000})
    data = json.loads(http_get(f"{WAGES_API}?{q}"))
    latest = max(r["date"] for r in data)
    out = []
    for entity, (_, wid, name) in [("all", ("", "overall", "All employees"))] + list(MASCO_MAJOR.items()):
        row = next((r for r in data if r["date"] == latest and r["occupation"] == wid and r["sex"] == "both"), None)
        if row:
            out.append({"kind": "wage", "entity": entity, "metric": "median_monthly_wage_myr",
                        "value": row["wages_median"], "period_start": latest, "period_end": f"{latest[:4]}-12-31",
                        "note": f"{name}; Malaysian citizen employees; excludes bonuses",
                        "source_name": "OpenDOSM wages_occupation (DOSM Salaries & Wages Survey)",
                        "source_url": WAGES_PAGE, "release_date": "", "fetched_date": TODAY})
    return out


def windows() -> tuple[tuple[dt.date, dt.date], tuple[dt.date, dt.date]]:
    """The 6 full months before the last 6 full months, and the last 6."""
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)

    def back(d: dt.date, months: int) -> dt.date:
        m = d.month - months
        return dt.date(d.year + (m - 1) // 12, (m - 1) % 12 + 1, 1)
    last = (back(end, 5), end)
    prev = (back(end, 11), back(end, 5) - dt.timedelta(days=1))
    return prev, last


def arxiv_rows(old: list[dict]) -> list[dict]:
    """AI and all papers on arXiv in two 6-month windows; the settled older window is reused."""
    prev, last = windows()
    kept = {(r["metric"], r["period_start"]): r for r in old if r["kind"] == "arxiv"}
    out, last_call = [], 0.0
    for start, end in (prev, last):
        when = f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
        for metric, query in (("ai_papers", f"{ARXIV_AI} AND {when}"), ("all_papers", f"cat:* AND {when}")):
            if (start, end) == prev and (metric, start.isoformat()) in kept:
                out.append(kept[(metric, start.isoformat())])
                continue
            wait = ARXIV_DELAY_S - (time.monotonic() - last_call)
            if wait > 0:
                time.sleep(wait)
            last_call = time.monotonic()
            url = f"{ARXIV_API}?" + urllib.parse.urlencode({"search_query": query, "max_results": 1})
            found = re.search(r"<opensearch:totalResults[^>]*>(\d+)<", http_get(url))
            if not found:
                raise ValueError("arXiv answer has no totalResults")
            out.append({"kind": "arxiv", "entity": "all", "metric": metric, "value": int(found.group(1)),
                        "period_start": start.isoformat(), "period_end": end.isoformat(),
                        "note": "papers whose abstract mentions AI or large language models" if metric == "ai_papers"
                        else "all papers; global research pace, not Malaysian demand",
                        "source_name": "arXiv API", "source_url": "https://info.arxiv.org/help/api/",
                        "release_date": TODAY, "fetched_date": TODAY})
            print(f"  arXiv {metric:<10} {start:%Y-%m}..{end:%Y-%m}: {out[-1]['value']}")
    return out


def update(arxiv: bool = True) -> list[dict]:
    old = read(INPUTS) if INPUTS.exists() else []
    rows = job_ad_rows()
    try:
        rows += wage_rows()
    except Exception as e:  # noqa: BLE001  keep the last wages when OpenDOSM cannot be reached
        print(f"  OpenDOSM wages not updated ({e!r}); previous rows kept", file=sys.stderr)
        rows += [r for r in old if r["kind"] == "wage"]
    if arxiv:
        rows += arxiv_rows(old)
    else:
        rows += [r for r in old if r["kind"] == "arxiv"]
    for i, r in enumerate(rows, 1):
        r["input_id"] = f"D{i:03d}"
    write(INPUTS, rows, FIELDS)
    return rows


# --- scoring --------------------------------------------------------------------------------------

def load_inputs() -> dict:
    return {"inputs": read(INPUTS), "occupations": read(DATA / "occupations.csv")}


def halves(series: dict) -> tuple[list, list]:
    """The quarters after the break split into the latest two and the two before them."""
    quarters = sorted(series)
    return quarters[-4:-2], quarters[-2:]


def ad_signals(rows: list[dict], changes: dict) -> dict:
    """Per MASCO major group: its share of all ads in each window and the change between them."""
    series = {}
    for r in rows:
        if r["kind"] == "job_ads":
            series.setdefault(r["entity"], {})[r["period_start"]] = float(r["value"])
    total = series.get("all", {})
    if len(total) < 4:
        return {}
    before, after = halves(total)
    edits = changes.get("job_ads") or {}
    out = {}
    for g in MASCO_MAJOR:
        s = series.get(g, {})
        if not all(q in s for q in before + after):
            continue
        factor = 1 + float(edits.get(g, 0)) / 100
        last = sum(s[q] for q in after) * factor
        all_last = sum(total[q] for q in after) - sum(s[q] for q in after) + last
        share_prev = sum(s[q] for q in before) / sum(total[q] for q in before)
        share_last = last / all_last
        change = 100 * (share_last / share_prev - 1) if share_prev else 0.0
        out[g] = {"group": g, "name": MASCO_MAJOR[g][2], "share_before": round(100 * share_prev, 2),
                  "share_after": round(100 * share_last, 2), "change_pct": round(change, 1),
                  "strength": round(clamp(change / SHARE_FULL_PCT), 3), "confidence": "medium",
                  "window_before": f"{before[0]}..{before[-1]}", "window_after": f"{after[0]}..{after[-1]}",
                  "ads_after": round(last), "changed": g in edits}
    return out


def momentum_of(rows: list[dict], changes: dict) -> dict:
    """Growth of AI papers on arXiv, last 6 months against the 6 before, as 0-100 momentum."""
    counts = {}
    for r in rows:
        if r["kind"] == "arxiv":
            counts.setdefault(r["period_start"], {})[r["metric"]] = float(r["value"])
    starts = sorted(counts)
    if len(starts) < 2 or not all("ai_papers" in counts[s] for s in starts[-2:]):
        return {"momentum": None, "growth_pct": None}
    a, b = counts[starts[-2]], counts[starts[-1]]
    ai_before, ai_after = a["ai_papers"], b["ai_papers"] * (1 + float(changes.get("arxiv", 0)) / 100)
    growth = 100 * (ai_after / ai_before - 1)
    every = (100 * (b["all_papers"] / a["all_papers"] - 1)) if a.get("all_papers") and b.get("all_papers") else None
    return {"momentum": round(NEUTRAL + NEUTRAL * clamp(growth / ARXIV_FULL_PCT), 1), "growth_pct": round(growth, 1),
            "ai_papers_before": round(ai_before), "ai_papers_after": round(ai_after),
            "all_papers_growth_pct": None if every is None else round(every, 1),
            "window_after": starts[-1], "changed": "arxiv" in changes}


def wages_of(rows: list[dict]) -> dict:
    return {r["entity"]: {"median": float(r["value"]), "year": r["period_start"][:4]}
            for r in rows if r["kind"] == "wage"}


def build(inputs: dict | None = None, changes: dict | None = None) -> dict:
    """{"occupations": {occ_id: demand row}, "groups": ad signals, "momentum": ..., "wages": ...}.
    changes (scripts/whatif.py): {"job_ads": {group: % change of its latest ads},
    "arxiv": % change of the latest AI papers, "mycol": {occ_id: "yes" | "near" | "no"}}."""
    inputs = inputs or load_inputs()
    changes = changes or {}
    groups = ad_signals(inputs["inputs"], changes)
    momentum = momentum_of(inputs["inputs"], changes)
    wages = wages_of(inputs["inputs"])
    mycol_edits = changes.get("mycol") or {}
    out = {}
    for o in inputs["occupations"]:
        status = mycol_edits.get(o["occ_id"], o["mycol"])
        signals = [{"signal": "mycol", "status": status, "strength": MYCOL_STRENGTH[status],
                    "confidence": MYCOL_CONFIDENCE[status], "occupation": o["mycol_occupation"],
                    "changed": o["occ_id"] in mycol_edits}]
        g = groups.get(o["masco_major"])
        if g:
            signals.append({"signal": "job_ads", "group": g["group"], "group_name": g["name"],
                            "change_pct": g["change_pct"], "strength": g["strength"], "confidence": g["confidence"],
                            "changed": g["changed"]})
        weights = [CONFIDENCE[s["confidence"]] for s in signals]
        demand = NEUTRAL + NEUTRAL * sum(w * s["strength"] for w, s in zip(weights, signals)) / sum(weights)
        out[o["occ_id"]] = {"occ_id": o["occ_id"], "demand": round(demand, 1), "has_demand": True,
                            "mycol": status, "signals": signals, "masco_major": o["masco_major"],
                            "wage": wages.get(o["masco_major"]), "momentum": momentum["momentum"]}
    dates = [r["fetched_date"] for r in inputs["inputs"] if re.fullmatch(r"\d{4}-\d\d-\d\d", r["fetched_date"])]
    return {"occupations": out, "groups": groups, "momentum": momentum, "wages": wages,
            "computed_date": max(dates, default=None), "formula_version": FORMULA_VERSION,
            "changed": bool(changes)}


_cache = {"key": None, "value": None}


def current() -> dict:
    """build() of the files as they are, rebuilt only when one of them changes."""
    key = tuple((DATA / f).stat().st_mtime_ns for f in ("demand_inputs.csv", "occupations.csv"))
    if _cache["key"] != key:
        _cache.update(key=key, value=build())
    return _cache["value"]


def write_table(result: dict) -> None:
    rows = []
    for o in result["occupations"].values():
        ads = next((s for s in o["signals"] if s["signal"] == "job_ads"), None)
        rows.append({"occ_id": o["occ_id"], "demand": o["demand"], "mycol": o["mycol"],
                     "masco_major": o["masco_major"], "ads_share_change_pct": ads["change_pct"] if ads else "",
                     "momentum": "" if o["momentum"] is None else o["momentum"],
                     "formula_version": result["formula_version"], "computed_date": TODAY})
    write(OUT, rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-arxiv", action="store_true", help="keep the previous arXiv counts")
    ap.add_argument("--build", action="store_true", help="only rebuild data/demand.csv from the inputs")
    args = ap.parse_args()
    if not args.build:
        print("[update inputs]")
        update(arxiv=not args.no_arxiv)
    result = build()
    write_table(result)
    m = result["momentum"]
    print(f"AI research momentum {m['momentum']} (AI papers {m.get('ai_papers_before')} -> {m.get('ai_papers_after')}, "
          f"{m['growth_pct']:+}%; all papers {m.get('all_papers_growth_pct')}%)" if m["momentum"] is not None
          else "No arXiv counts")
    for g in result["groups"].values():
        print(f"  MASCO {g['group']} {g['name'][:44]:<44} share of ads {g['share_before']:5.2f}% -> "
              f"{g['share_after']:5.2f}% ({g['change_pct']:+.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
