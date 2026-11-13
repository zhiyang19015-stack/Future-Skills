"""The metric registry: every number the app shows, traceable to its source, date, method and limits.

data/metric_registry.csv has one row per metric with the fields the research plan asks for:
metric_id, value + unit, geography, taxonomy, source name and URL, publication date and observation
period (kept apart), method, confidence and limitations, and the transformation from the source to
the number on screen, with its version. "live" dates are filled in here from the data actually
loaded, so the registry never shows a date the data does not have.

Each metric also has a kind, one of four that are never merged into one number:
    observed             measured use or counts (Anthropic Economic Index, DOSM, MyCOL, OpenDOSM, arXiv)
    research_estimate    a study's estimate of potential (ILO WP140)
    scenario_assumption  a value the person picks (adoption speed, friction)
    user_input           what the person says about themselves
plus derived: our own formulas over the others.
"""

import csv
import io
from pathlib import Path

import ilo

DATA = Path(__file__).resolve().parents[1] / "data"
KINDS = ("observed", "research_estimate", "scenario_assumption", "user_input", "derived")


def rows() -> list[dict]:
    return list(csv.DictReader(io.StringIO((DATA / "metric_registry.csv").read_text(encoding="utf-8-sig"))))


def live(data: dict, inputs: list[dict]) -> dict:
    """{source_id: (publication date, observation period)} from the loaded data."""
    ei = data["ai"]["source"]["economic_index"]
    months = data["ai"]["context"].get("months") or []
    out = {"economic_index": (ei.get("release_date", ""), f"{months[0]} to {months[-1]}" if months else ""),
           "derived": (data["demand"].get("computed_date", ""), "")}
    by_kind = {}
    for r in inputs:
        by_kind.setdefault(r["kind"], []).append(r)
    for kind in ("job_ads", "wage", "arxiv"):
        mine = by_kind.get(kind, [])
        if mine:
            out[kind] = (max(r["release_date"] for r in mine),
                         f"{min(r['period_start'] for r in mine)} to {max(r['period_end'] for r in mine)}")
    src = ilo.tables()["source"]
    if src:
        out["ilo_wp140"] = (src["source_date"], "2025")
    return out


def registry(data: dict, inputs: list[dict]) -> list[dict]:
    dates = live(data, inputs)
    out = []
    for r in rows():
        pub, period = dates.get(r["source_id"], ("", ""))
        if r["source_id"] == "derived" and r["kind"] != "derived":
            pub = ""
        out.append({**r, "publication_date": pub if r["publication_date"] == "live" else r["publication_date"],
                    "observation_period": period if r["observation_period"] == "live" else r["observation_period"]})
    return out
