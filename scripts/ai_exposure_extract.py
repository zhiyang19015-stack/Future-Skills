"""Cut the Anthropic Economic Index down to the rows our occupations use.

Run by a maintainer when a new release is reviewed and pinned (not on every "Update data"),
after scripts/build_onet.py has written the occupations and their O*NET tasks:

    Anthropic Economic Index (CC-BY)   how people use Claude, by O*NET task, occupation and
                                       request topic, per calendar month, global and per country.
                                       One 219 MB CSV per release, pinned below by revision and
                                       sha256 so every run reads the same bytes.

Raw files are read from --raw (default raw/, or the FS_RAW environment variable) and downloaded
there when missing. They stay out of git. What is written, and committed:

    data/aei/aei_extract.csv              the Economic Index rows for our tasks, occupations, work
                                          activities and request topics; GLOBAL and Malaysia
    data/aei/task_penetration.csv         Anthropic's task-level coverage, our tasks only
    data/aei/job_exposure.csv             Anthropic's observed exposure, our occupations only
    data/aei/source.json                  what was read: release, revision, sha256, dates, licence

Then run scripts/ai_exposure.py to build the tables the app reads.

Usage: python scripts/ai_exposure_extract.py [--raw DIR]
Standard library only.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

AEI_REPO = "Anthropic/EconomicIndex"
AEI_REVISION = "4e5f69fab13a9c3f7d0dcc31a6f893a9818738f6"  # dataset `main` on 2026-09-30
AEI_RELEASE = "2026-06-26"
AEI_FILE = "release_2026_06_26/data/aei_claude_ai_2026-06-26.csv"
AEI_SHA256 = "f974b358bce0e5a8417510c61da4342234cd0de9d9d0b62acf4c6dbcf8ec7b68"
AEI_SMALL = ["labor_market_impacts/task_penetration.csv", "labor_market_impacts/job_exposure.csv"]
AEI_URL = f"https://huggingface.co/datasets/{AEI_REPO}/resolve/{AEI_REVISION}/"
AEI_PAGE = f"https://huggingface.co/datasets/{AEI_REPO}/tree/{AEI_REVISION}/"
AEI_NAME = f"Anthropic Economic Index, release {AEI_RELEASE} (Claude.ai usage)"
AEI_LICENCE = "CC-BY (data)"
IMPACTS_NAME = "Anthropic, Labor market impacts of AI (observed exposure), 2026-03-05"
IMPACTS_PAGE = "https://www.anthropic.com/research/labor-market-impacts"

ONET_NAME = "O*NET 31.0 Database"
ONET_PAGE = "https://www.onetcenter.org/database.html"
ONET_FILES = ["occupation_data.csv", "essential_skills.csv", "transferable_skills.csv", "knowledge.csv",
              "software_skills.csv", "career_interest_types.csv", "job_zones.csv", "task_statements.csv",
              "task_ratings.csv", "tasks_to_dwas.csv", "gwas_to_iwas_to_dwas.csv", "emerging_tasks.csv",
              "essential_skills_to_work_activities.csv", "transferable_skills_to_work_activities.csv",
              "sample_of_reported_titles.csv", "related_occupations.csv", "level_scale_anchors.csv",
              "content_model_reference.csv"]

GEOS = {"GLOBAL", "MYS"}
METRICS = {
    "pct", "usage_pct", "usage_per_capita_index",
    "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct",
    "human_only_time_mean", "human_with_ai_time_mean",
    "use_case_work_pct", "use_case_coursework_pct",
}
TASK_METRICS = {"pct", "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct",
                "human_only_time_mean", "human_with_ai_time_mean"}
AEI_COLUMNS = ["date_start", "date_end", "geo_id", "geo_level", "category_name", "hierarchy_level",
               "metric_id", "value", "node_name", "node_external_id"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, path: Path) -> None:
    """Download url to path unless it is already there."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "future-skills"})
    part = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)
    part.replace(path)


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {len(rows):>6} rows to {path.relative_to(ROOT)}")


def aei_rows(path: Path, task_ids: set, socs: set) -> list[dict]:
    """The rows of the release our tables use; every other row is skipped while reading."""
    keep = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != AEI_COLUMNS:
            sys.exit(f"Unexpected columns in {path.name}: {reader.fieldnames}")
        for r in reader:
            if r["geo_id"] not in GEOS or r["metric_id"] not in METRICS:
                continue
            cat, level, node = r["category_name"], r["hierarchy_level"], r["node_external_id"]
            if cat == "onet" and level == "0" and r["metric_id"] not in TASK_METRICS:
                continue
            if (cat == "overall"
                    or (cat == "onet" and (level == "3" or (level == "0" and node in task_ids)))
                    or (cat == "soc_occupation" and (level == "1" or node in socs))
                    or (cat == "request" and level in ("1", "2"))):
                keep.append(r)
    keep.sort(key=lambda r: (r["geo_id"], r["category_name"], r["hierarchy_level"], r["node_name"],
                             r["date_start"], r["metric_id"]))
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", default=os.getenv("FS_RAW", str(ROOT / "raw")),
                    help="folder that holds (or will hold) the raw downloads")
    raw = Path(ap.parse_args().raw)
    today = date.today().isoformat()
    tasks = read(DATA / "onet" / "tasks.csv")
    occupations = read(DATA / "occupations.csv")

    print("[Anthropic Economic Index]")
    big = raw / "aei" / AEI_FILE
    fetch(AEI_URL + AEI_FILE, big)
    digest = sha256(big)
    if digest != AEI_SHA256:
        sys.exit(f"{big.name}: sha256 {digest} is not the pinned {AEI_SHA256}; a new release must be "
                 "reviewed before it is used")
    task_ids = {t["task_id"] for t in tasks}
    socs = {r["occ_id"] for r in occupations}
    rows = aei_rows(big, task_ids, socs)
    write(DATA / "aei" / "aei_extract.csv", rows, AEI_COLUMNS)

    files = {AEI_FILE: digest}
    for name in AEI_SMALL:
        fetch(AEI_URL + name, raw / "aei" / name)
        files[name] = sha256(raw / "aei" / name)
    by_text = {}
    for t in tasks:
        by_text.setdefault(t["task"].strip().lower(), set()).add(t["task_id"])
    pen = []
    for r in read(raw / "aei" / "labor_market_impacts" / "task_penetration.csv"):
        for tid in sorted(by_text.get(r["task"].strip().lower(), ()), key=int):
            pen.append({"task_id": tid, "task": r["task"], "penetration": r["penetration"]})
    pen.sort(key=lambda r: int(r["task_id"]))
    write(DATA / "aei" / "task_penetration.csv", pen)
    six = {s[:7] for s in socs}
    write(DATA / "aei" / "job_exposure.csv",
          [r for r in read(raw / "aei" / "labor_market_impacts" / "job_exposure.csv") if r["occ_code"] in six])

    periods = sorted({(r["date_start"], r["date_end"]) for r in rows})
    (DATA / "aei" / "source.json").write_text(json.dumps({
        "economic_index": {"source_name": AEI_NAME, "source_url": AEI_PAGE + AEI_FILE.rsplit("/", 2)[0],
                           "repo": AEI_REPO, "revision": AEI_REVISION, "release_date": AEI_RELEASE,
                           "licence": AEI_LICENCE, "files": files, "fetched_date": today,
                           "periods": [{"start": a, "end": b} for a, b in periods]},
        "labor_market_impacts": {"source_name": IMPACTS_NAME, "source_url": IMPACTS_PAGE,
                                 "release_date": "2026-03-05", "licence": AEI_LICENCE, "fetched_date": today,
                                 "note": "Built by Anthropic from the August and November 2025 usage samples."},
        "onet": {"source_name": ONET_NAME, "source_url": ONET_PAGE, "licence": "CC BY 4.0",
                 "fetched_date": today, "files": ONET_FILES, "occupations": len(occupations), "tasks": len(tasks)},
    }, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote data/aei/source.json ({len(periods)} periods)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
