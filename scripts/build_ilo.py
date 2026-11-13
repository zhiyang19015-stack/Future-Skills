"""ILO Working Paper 140 (2025) -> data/ilo_exposure.csv and data/ilo_tasks.csv.

The refined global index of GenAI exposure (Gmyrek et al. 2025) scores each of the 3,265 tasks of
the 427 ISCO-08 four-digit occupations from 0 (current GenAI cannot do the task) to 1 (it could do
all of it), and puts each occupation in an exposure gradient from its mean and standard deviation.
It measures technical potential, not job loss and not use: the Anthropic Economic Index measures
use. The app shows the two side by side and never averages them.

Every O*NET occupation already has an ISCO-08 unit group (data/occupations.csv, from the ESCO
crosswalk), so the ILO score reaches an O*NET occupation through that code. Several O*NET
occupations share one ISCO group and so share its score; the mapping basis stays visible.

Source: https://github.com/pgmyrek/2025_GenAI_scores_ISCO08 (CC BY 4.0, © ILO). We keep the
occupation means, SDs, gradients and the task scores, and drop the models' written justifications.
This is an adaptation: it has not been prepared, reviewed or endorsed by the ILO.

Usage:
    python scripts/build_ilo.py --raw D:/future-skills-raw     # the folder holding ilo/scores2025.xlsx
"""

import argparse
import csv
import sys
import zipfile
from pathlib import Path

import demand  # its stdlib .xlsx reader

DATA = Path(__file__).resolve().parents[1] / "data"
SOURCE_NAME = "ILO Working Paper 140 (Gmyrek et al. 2025): GenAI exposure scores by ISCO-08 task and occupation"
SOURCE_URL = "https://github.com/pgmyrek/2025_GenAI_scores_ISCO08"
PAPER_URL = "https://doi.org/10.54394/HETP0387"
RELEASED = "2025-05-20"
WORKBOOK = "Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx"
GRADIENTS = {"Exposed: Gradient 4": "g4", "Exposed: Gradient 3": "g3", "Exposed: Gradient 2": "g2",
             "Exposed: Gradient 1": "g1", "Minimal Exposure": "minimal", "Not Exposed": "not_exposed"}
HIGH_TASK = 0.75   # the ILO's own "High" band of a task score


def number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(workbook: Path, fetched: str) -> tuple[list[dict], list[dict]]:
    rows = demand.xlsx_rows(workbook)
    head = rows[0]
    col = {name: head.index(name) for name in ("ISCO_08", "Title", "taskID", "Task_ISCO", "score_2023", "score_2025",
                                               "source", "mean_score_2023", "mean_score_2025", "SD_2023", "SD_2025",
                                               "potential25", "potential23")}
    occupations, tasks = {}, []
    for r in rows[1:]:
        if not r or r[col["ISCO_08"]] is None:
            continue
        get = lambda k: r[col[k]] if col[k] < len(r) else None  # noqa: E731
        isco = str(get("ISCO_08")).split(".")[0].zfill(4)
        score = number(get("score_2025"))
        tasks.append({"isco": isco, "task_no": int(number(get("taskID")) or 0), "task": str(get("Task_ISCO")).strip(),
                      "score_2025": round(score, 3) if score is not None else "",
                      "score_2023": round(number(get("score_2023")), 3) if number(get("score_2023")) is not None else "",
                      "basis": get("source") or ""})
        o = occupations.setdefault(isco, {
            "isco": isco, "title": str(get("Title")).strip(), "tasks": 0, "high_tasks": 0,
            "mean_2025": round(number(get("mean_score_2025")), 3), "sd_2025": round(number(get("SD_2025")), 3),
            "gradient": GRADIENTS.get(get("potential25"), "not_exposed"), "gradient_label": get("potential25"),
            "mean_2023": round(number(get("mean_score_2023")), 3) if number(get("mean_score_2023")) is not None else "",
            "category_2023": get("potential23") or "",
            "source_name": SOURCE_NAME, "source_url": SOURCE_URL, "source_date": RELEASED, "fetched_date": fetched})
        o["tasks"] += 1
        o["high_tasks"] += 1 if score is not None and score >= HIGH_TASK else 0
    return sorted(occupations.values(), key=lambda o: o["isco"]), tasks


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--raw", required=True, help="folder with ilo/<workbook> (or ilo/scores2025.xlsx)")
    cli.add_argument("--fetched", default="2026-11-13", help="the date the workbook was downloaded")
    opts = cli.parse_args()
    folder = Path(opts.raw) / "ilo"
    workbook = next((p for p in (folder / WORKBOOK, folder / "scores2025.xlsx") if zipfile.is_zipfile(p)), None)
    if workbook is None:
        print(f"Put {WORKBOOK} from {SOURCE_URL} in {folder}")
        return 1
    occupations, tasks = build(workbook, opts.fetched)
    write(DATA / "ilo_exposure.csv", occupations)
    write(DATA / "ilo_tasks.csv", tasks)
    print(f"{len(occupations)} ISCO-08 occupations, {len(tasks)} tasks -> data/ilo_exposure.csv, data/ilo_tasks.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
