"""Find everything in the repository that has no source we can point to, and write it down.

Rule 7 of the team's working rules: every number must stand up to a check; what is not measured says
"not measured"; an assumption says it is one. This script lists what fails that, in four parts:

    1 data files    every file in data/: a source on each row (source_name / source_url columns, or
                    a url per item in a JSON list), or a source named for the whole file in
                    SOURCES.md or data/README.md. Rows with an empty source are listed.
    2 constants     every module-level number in the code the server runs (src/main.py and the
                    scripts it imports). One counts as shown when its value appears on the app's
                    Sources page (GET /api/sources); the others are listed with file and line, so
                    a person can say whether each is a display limit or a model assumption.
    3 prose         sentences in the hand-written documents (README, SOURCES, docs/feasibility,
                    docs/pitch) that state a statistic (a %, RM, or a number of 1,000 or more)
                    with no link, no "(Source, year)" and no generated file or script named on
                    the same line.
    4 UI            numbers written into the page scripts' text (src/static/*.js strings with %)

It finds candidates; it does not decide. The results page says which are fine and why only where a
person has checked them (CHECKED below), and everything else stays "not checked".

    python scripts/source_audit.py           # print the summary
    python scripts/source_audit.py --write   # also write docs/source_audit.md and docs/source_audit.json
"""

import argparse
import ast
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

PROSE = ["README.md", "SOURCES.md", "docs/feasibility.md", "docs/pitch/deck_outline.md",
         "docs/pitch/demo_script.md", "docs/pitch/qa_cheatsheet.md", "data/README.md"]
STAT = re.compile(r"(\d[\d.,]*\s?%|\bRM\s?\d|\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b(?!-\d))")
YEAR = re.compile(r"^(19|20)\d\d$")
CITED = re.compile(r"\]\(|https?://|\((?:[A-Z][^()]{1,60}?,\s*)?(?:19|20)\d\d[a-z]?\)|`[^`]+\.(?:py|md|csv|json)`|"
                   r"\b[a-z_]+\.(?:py|md|csv|json)\b|\b(?:EV|JC|IV|CM|VS)\b|judge_check|eval_results|"
                   r"impact_verification|cost_model|kpi_report|\bestimate\b|assumption|not measured|未测量|估计|假设")

OWN_KINDS = {"derived", "scenario_assumption", "user_input"}   # labelled ours, so they name no outside source

# Rows checked by hand: (file, a cell of the row) -> why it is fine.
ROW_OK = {("metric_registry.csv", "training_hours"): "each resource's hours come from its own page, linked per row "
          "in learning_resources.csv (source_url)"}

# Constants checked by hand. "limit": a size, timeout or display limit, or a value stated elsewhere with its
# source; no source needed here. "assumption": our own model or wording assumption that is NOT on the Sources
# page yet (it should be added there).
CONST_KIND = {
    "MAX_BODY": ("limit", "largest request body"), "MAX_AD_CHARS": ("limit", "longest job ad read"),
    "UPDATE_TIMEOUT_S": ("limit", "update job timeout"), "AUTO_CHECK_S": ("limit", "how often the update is checked"),
    "RADAR_TOOLS": ("limit", "tools listed on the Radar"), "MAX_CHARS": ("limit", "longest CV read"),
    "MAX_TOKENS": ("limit", "LLM reply cut-off"), "CACHE_SIZE": ("limit", "LLM reply cache"),
    "REPLY_LIMIT": ("limit", "longest LLM reply kept"), "MAX_HOURS": ("limit", "sanity cap on reported hours"),
    "STABILITY_POOL": ("limit", "how many top occupations the drawn futures re-rank (SOURCES.md: the top 30)"),
    "MAX_PATH_STEPS": ("limit", "path steps shown"), "DETAIL_ITEMS": ("limit", "detail rows shown"),
    "MAX_PAGE": ("limit", "largest news page read"), "MAX_SESSIONS": ("limit", "workshop sessions kept"),
    "MAX_PEOPLE": ("limit", "people per workshop session"), "SKILLS_ASKED": ("limit", "skills asked in the skills check"),
    "SHOWN_ACTIVITIES": ("limit", "work activities offered on the page"),
    "EXAMPLES": ("limit", "what-if examples, each labelled as a what-if"),
    "NEWS": ("limit", "the simulated headlines, labelled simulated on screen"),
    "TARGET_PCT": ("limit", "the Phase 1 KPI 1 target (70%), from the Phase 1 proposal"),
    "KEEP_DAYS": ("limit", "retention of workshop answers (README: 180 days)"),
    "NEWS_FLOOR": ("limit", "simulated-news floor of 95%, stated in SOURCES.md (Simulated news)"),
    "CURRENT_FIELD": ("assumption", "the job a person does now counts as 80 of 100 experience evidence for its field"),
    "TITLE_EVIDENCE": ("assumption", "a job title named in a CV counts as 70 of 100 experience evidence for its field"),
    "HANDOFF_MAX": ("assumption", "a topic's hands-off share is capped at 98% in a what-if"),
    "NEUTRAL_BAND": ("assumption", "explanation wording: a part within 12.5 points of the middle is called neutral"),
}

# Prose lines checked by hand: (file, text the line contains, why it is fine). "" matches every line of the file.
PROSE_OK = [
    ("README.md", "Hays Asia Salary Guide 2025", "quoted from the SDC 2026 Domain 1 problem statement (line 34); the line says so"),
    ("README.md", "18,592 O*NET tasks", "counts from data/onet/tasks.csv and the AI-share rule's threshold (Sources page)"),
    ("README.md", "Slow 10%, moderate 25%, fast 50%", "the scenario assumption, on the Sources page"),
    ("README.md", "20% field fit + 15% interest", "the match weights, our assumption, on the Sources page"),
    ("README.md", "1,000 drawn futures", "the number of drawn futures, on the Sources page"),
    ("README.md", "30% larger constants and a 46% outlook weight", "experiments described in docs/scenario_report.md"),
    ("README.md", "Design & UX is 5%", "the rubric weight, from the finalist guide"),
    ("SOURCES.md", "", "SOURCES.md states the model's own formulas and constants; they are assumptions, on the Sources page"),
    ("docs/feasibility.md", "RM", "figures from docs/cost_model.md (scripts/cost_model.py), named in that section"),
    ("docs/feasibility.md", "90.8%", "values from docs/kpi_report.md (scripts/kpi.py), named in the table's heading"),
    ("docs/feasibility.md", "90.4%", "values from docs/kpi_report.md"),
    ("docs/feasibility.md", "2,241", "the data validator's count, in docs/kpi_report.md"),
    ("docs/feasibility.md", "40% tick", "a pilot target we set, not a result (the table lists targets)"),
    ("docs/pitch/deck_outline.md", "（15%）", "rubric weight"), ("docs/pitch/deck_outline.md", "（25%）", "rubric weight"),
    ("docs/pitch/deck_outline.md", "（20%）", "rubric weight"), ("docs/pitch/deck_outline.md", "（10%）", "rubric weight"),
    ("docs/pitch/deck_outline.md", "（5%）", "rubric weight"), ("docs/pitch/deck_outline.md", "1440", "a screenshot file name"),
    ("docs/pitch/deck_outline.md", "18,592 O*NET tasks", "count of data/onet/tasks.csv"),
    ("docs/pitch/deck_outline.md", "1,194 UI strings", "judge_check check 9 (JC)"),
]
UI_OK = [("i18n.js", "rise 15%", "a what-if example's own input, labelled as a what-if"),
         ("i18n.js", "naik 15%", "same, BM"), ("i18n.js", "上升 15%", "same, ZH"),
         ("i18n.js", "fall 20%", "a what-if example's own input"), ("i18n.js", "turun 20%", "same, BM"),
         ("i18n.js", "下降 20%", "same, ZH"), ("i18n.js", "50%", "the field-fit formula, our assumption, on the Sources page"),
         ("lab-i18n.js", "30%", "the Stress Test's default slider value, labelled as a default"),
         ("lab-i18n.js", "90%", "the adoption slider's range (Sources page: adoption_max)"),
         ("names-i18n.js", "100%", "quotes the course provider's page (HRD Corp claimable), linked in learning_resources.csv")]

# Items a person checked by hand (2026-11-17), with the reason they are fine. Keyed by a short id the
# report prints; anything not here is reported as "not checked".
CHECKED = {
    "data:sample_profiles.json": "fictional demo people, labelled fictional on every page (no source needed)",
    "data:sample_team.json": "fictional demo team, labelled fictional (no source needed)",
    "data:missions.csv": "practice tasks we wrote; each names the O*NET element it trains (our own content, labelled so)",
    "data:review_occupations.csv": "our own list of occupations queued for a manual review (not data shown as fact)",
}


# --- 1 data files -------------------------------------------------------------------------------------

def mentioned(name: str) -> list[str]:
    """Where this file's source is recorded for the whole file: a line of SOURCES.md that names it with a link,
    a row of data/README.md that names it (or its folder) with the script that builds it from a source listed
    in SOURCES.md, or the folder's own source.json."""
    out = []
    folder = name.split("/")[0] + "/" if "/" in name else None
    for doc in ("SOURCES.md", "data/README.md"):
        p = ROOT / doc
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            named = f"`{name}`" in line or f"data/{name}" in line or (folder and f"`{folder}`" in line)
            if named and ("http" in line or "](" in line):
                out.append(doc)
                break
            if named and doc == "data/README.md" and re.search(r"`[a-z_/]+\.py`", line):
                out.append("data/README.md (built by " + re.search(r"`([a-z_/]+\.py)`", line).group(1) + ")")
                break
    if folder and (DATA / folder / "source.json").exists():
        out.append(f"data/{folder}source.json")
    return out


def data_files() -> list[dict]:
    rows = []
    for path in sorted(DATA.rglob("*")):
        if path.suffix not in (".csv", ".json") or not path.is_file():
            continue
        name = path.relative_to(DATA).as_posix()
        entry = {"file": name, "rows": 0, "row_level": False, "empty_rows": [], "file_level": mentioned(name)}
        if path.suffix == ".csv":
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                cols = reader.fieldnames or []
                src_cols = [c for c in ("source_name", "source_url") if c in cols] or \
                           [c for c in cols if c in ("source_id", "source", "url")]
                entry["row_level"] = bool(src_cols)
                for i, r in enumerate(reader, 2):
                    entry["rows"] += 1
                    if (r.get("kind") or "") in OWN_KINDS:      # metric_registry: our own rule or the user's input
                        continue
                    if any(name == f and t in r.values() for f, t in ROW_OK):
                        continue
                    if src_cols and not all((r.get(c) or "").strip() for c in src_cols):
                        entry["empty_rows"].append(i)
        else:
            doc = json.loads(path.read_text(encoding="utf-8"))
            items = doc if isinstance(doc, list) else next((v for v in doc.values() if isinstance(v, list)), [])
            entry["rows"] = len(items)
            keyed = [x for x in items if isinstance(x, dict)]
            has = [x for x in keyed if any(k in x for k in ("url", "source_url", "source"))]
            entry["row_level"] = bool(keyed) and len(has) == len(keyed)
            if isinstance(doc, dict) and any(k in doc for k in ("source", "source_url", "source_name")):
                entry["row_level"] = True
        key = f"data:{name}"
        if key in CHECKED:
            entry["status"], entry["why"] = "fine", CHECKED[key]
        elif entry["row_level"] and not entry["empty_rows"]:
            entry["status"] = "sourced per row"
        elif entry["row_level"]:
            entry["status"] = f"{len(entry['empty_rows'])} rows without a source"
        elif entry["file_level"]:
            entry["status"] = "sourced for the whole file in " + ", ".join(entry["file_level"])
        else:
            entry["status"] = "no source found"
        rows.append(entry)
    return rows


# --- 2 constants --------------------------------------------------------------------------------------

def server_modules() -> list[Path]:
    tree = ast.parse((ROOT / "src" / "main.py").read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    mods = [ROOT / "src" / "main.py"] + sorted(p for p in (ROOT / "scripts").glob("*.py") if p.stem in names)
    return mods


def flat_values(x, out: set) -> set:
    if isinstance(x, dict):
        for v in x.values():
            flat_values(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            flat_values(v, out)
    elif isinstance(x, bool):
        pass
    elif isinstance(x, (int, float)):
        out.add(round(float(x), 6))
    elif isinstance(x, str):
        for m in re.findall(r"-?\d+(?:\.\d+)?", x):
            out.add(round(float(m), 6))
    return out


def shown_on_sources_page() -> set:
    import main
    res = main.dispatch("GET", "/api/sources", b"")
    return flat_values(json.loads(res.body), set())


def constants() -> list[dict]:
    shown = shown_on_sources_page()
    out = []
    for path in server_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if not name.isupper():
                continue
            nums = [n.value for n in ast.walk(node.value) if isinstance(n, ast.Constant)
                    and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
            if not nums:
                continue
            values = {round(float(v), 6) for v in nums}
            missing = sorted(v for v in values if v not in shown and v not in (0.0, 1.0))
            kind, why = CONST_KIND.get(name, ("not checked", ""))
            out.append({"file": path.relative_to(ROOT).as_posix(), "line": node.lineno, "name": name,
                        "values": sorted(values)[:8], "shown": not missing, "not_shown": missing[:8],
                        "kind": kind if missing else "shown", "why": why})
    return out


# --- 3 prose ------------------------------------------------------------------------------------------

def prose() -> list[dict]:
    out = []
    for doc in PROSE:
        p = ROOT / doc
        if not p.exists():
            continue
        in_code = False
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or not line.strip():
                continue
            stats = [m for m in STAT.findall(line) if not YEAR.match(m.strip())]
            if stats and not CITED.search(line):
                ok = next((why for f, t, why in PROSE_OK if f == doc and t in line), None)
                out.append({"file": doc, "line": i, "numbers": stats[:6], "text": line.strip()[:220],
                            "status": "fine" if ok else "not checked", "why": ok or ""})
    return out


# --- 4 UI ---------------------------------------------------------------------------------------------

UI_NUM = re.compile(r"[\"'`][^\"'`\n]*\d+(?:\.\d+)?\s?%[^\"'`\n]*[\"'`]")


def ui_strings() -> list[dict]:
    out = []
    for p in sorted((ROOT / "src" / "static").glob("*.js")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in UI_NUM.findall(line):
                if "${" in m or "width" in line or "style" in line.lower():
                    continue
                ok = next((why for f, t, why in UI_OK if p.name == f and t in m), None)
                out.append({"file": p.relative_to(ROOT).as_posix(), "line": i, "text": m[:160],
                            "status": "fine" if ok else "not checked", "why": ok or ""})
    return out


# --- report -------------------------------------------------------------------------------------------

def run() -> dict:
    d = data_files()
    c = constants()
    pr = prose()
    ui = ui_strings()
    return {"date": date.today().isoformat(), "data": d, "constants": c, "prose": pr, "ui": ui,
            "summary": {"data_files": len(d), "data_no_source": sum(x["status"] == "no source found" for x in d),
                        "data_rows_empty": sum(len(x["empty_rows"]) for x in d),
                        "constants": len(c), "constants_not_shown": sum(not x["shown"] for x in c),
                        "constants_assumption_not_shown": sum(x["kind"] == "assumption" for x in c),
                        "constants_not_checked": sum(x["kind"] == "not checked" for x in c),
                        "prose_uncited": len(pr), "prose_not_checked": sum(x["status"] != "fine" for x in pr),
                        "ui_numbers": len(ui), "ui_not_checked": sum(x["status"] != "fine" for x in ui)}}


def as_markdown(r: dict) -> str:
    s = r["summary"]
    L = ["# Source audit", "",
         f"Generated by `python scripts/source_audit.py --write` on {r['date']}. It lists candidates: things with no "
         "source the script can find. A person decides which matter; until then each is \"not checked\".", "",
         "| Part | Checked | Without a source found |", "|---|---|---|",
         f"| 1. Data files in `data/` | {s['data_files']} files | {s['data_no_source']} files; {s['data_rows_empty']} rows with an empty source |",
         f"| 2. Constants in the code the server runs | {s['constants']} | {s['constants_not_shown']} whose value is not on the "
         f"Sources page; by hand: {s['constants_assumption_not_shown']} model assumptions to add there, the rest limits; "
         f"not checked: {s['constants_not_checked']} |",
         f"| 3. Statistics in hand-written documents | {len(PROSE)} documents | {s['prose_uncited']} lines with no source on "
         f"the line; not checked: {s['prose_not_checked']} |",
         f"| 4. Numbers with % written into the page scripts | src/static/*.js | {s['ui_numbers']} strings; not checked: "
         f"{s['ui_not_checked']} |", "",
         "## 1. Data files", "", "| File | Rows | Status |", "|---|---|---|"]
    for x in r["data"]:
        status = x["status"] + (f" — {x['why']}" if x.get("why") else "")
        if x["empty_rows"]:
            status += f" (lines {', '.join(map(str, x['empty_rows'][:10]))}{'…' if len(x['empty_rows']) > 10 else ''})"
        L.append(f"| `{x['file']}` | {x['rows']} | {status} |")
    L += ["", "## 2. Constants whose value is not on the Sources page", "",
          "A value counts as shown when the same number appears anywhere in `GET /api/sources`. 0 and 1 are ignored. "
          "Display limits (how many rows a page shows) need no source; model assumptions should be on the Sources page.", "",
          "| Constant | Where | Value(s) not shown | Kind (checked by hand) | What it is |", "|---|---|---|---|---|"]
    order = {"assumption": 0, "not checked": 1, "limit": 2}
    L += [f"| `{x['name']}` | `{x['file']}:{x['line']}` | {', '.join(f'{v:g}' for v in x['not_shown'])} | {x['kind']} | {x['why']} |"
          for x in sorted((x for x in r["constants"] if not x["shown"]), key=lambda x: order.get(x["kind"], 3))]
    L += ["", "## 3. Statistics with no source on the same line", "",
          "A line counts as cited when it has a link, a `(Source, year)`, a file or script name, one of the pitch "
          "documents' source codes (EV, JC, IV, CM, VS), or says it is an estimate, an assumption or not measured. "
          "A source given in the previous line or a table header is not seen, so some of these are fine.", "",
          "| Where | Numbers | Status | Why | Line |", "|---|---|---|---|---|"]
    L += [f"| `{x['file']}:{x['line']}` | {', '.join(x['numbers'])} | {x['status']} | {x['why']} | {x['text'].replace('|', '/')} |"
          for x in sorted(r["prose"], key=lambda x: x["status"] == "fine")]
    L += ["", "## 4. Numbers with % written into the page scripts", "",
          "These are fixed in the page's code, not read from the API. Each should be a rule we state (a threshold, a "
          "label) or come from a source.", "", "| Where | Text | Status | Why |", "|---|---|---|---|"]
    L += [f"| `{x['file']}:{x['line']}` | {x['text'].replace('|', '/')} | {x['status']} | {x['why']} |" for x in r["ui"]]
    return "\n".join(L) + "\n"


def main_cli() -> int:
    cli = argparse.ArgumentParser(description="List what has no source we can point to.")
    cli.add_argument("--write", action="store_true")
    a = cli.parse_args()
    r = run()
    if a.write:
        (DOCS / "source_audit.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                                newline="\n")
        (DOCS / "source_audit.md").write_text(as_markdown(r), encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(r["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
