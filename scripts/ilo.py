"""The ILO 2025 GenAI exposure index next to the Anthropic Economic Index, for one occupation.

Two different measurements, kept apart:

    observed use        Anthropic Economic Index: how much of an occupation's tasks people
                        already hand to Claude (scripts/ai_exposure.py). What AI is used for now.
    research estimate   ILO Working Paper 140: how much of an ISCO-08 occupation's tasks current
                        GenAI could technically do, 0-1 per task, with the occupation's mean, SD
                        and exposure gradient (data/ilo_exposure.csv, scripts/build_ilo.py).

They measure different things, so they are never averaged. Where they disagree strongly the page
says so: the occupation's percentile among all occupations on each measure is compared, and a gap
of DIVERGENCE points or more is a "sources disagree" note with both numbers.

An O*NET occupation reaches the ILO score through its ISCO-08 unit group (ESCO crosswalk); the
mapping basis (exact, close, broad) goes with every score.
"""

import bisect
import csv
import io
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DIVERGENCE = 40.0           # percentile points between the two measures before "sources disagree"
GRADIENT_ORDER = ("not_exposed", "minimal", "g1", "g2", "g3", "g4")
_cache = {"key": None, "value": None}
_ranks = {"key": None, "value": None}


def read(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO((DATA / name).read_text(encoding="utf-8-sig"))))


def tables() -> dict:
    """The ILO occupations by ISCO-08 code and their tasks, read once per file change."""
    files = [DATA / "ilo_exposure.csv", DATA / "ilo_tasks.csv"]
    if not all(f.exists() for f in files):
        return {"occupations": {}, "tasks": {}, "source": None}
    key = tuple(f.stat().st_mtime_ns for f in files)
    if _cache["key"] == key:
        return _cache["value"]
    occupations = {}
    for r in read("ilo_exposure.csv"):
        occupations[r["isco"]] = {**r, "tasks": int(r["tasks"]), "high_tasks": int(r["high_tasks"]),
                                  "mean_2025": float(r["mean_2025"]), "sd_2025": float(r["sd_2025"]),
                                  "mean_2023": float(r["mean_2023"]) if r["mean_2023"] else None}
    tasks = {}
    for r in read("ilo_tasks.csv"):
        tasks.setdefault(r["isco"], []).append({"task_no": int(r["task_no"]), "task": r["task"],
                                                "score": float(r["score_2025"]) if r["score_2025"] else None,
                                                "score_2023": float(r["score_2023"]) if r["score_2023"] else None,
                                                "basis": r["basis"]})
    first = next(iter(occupations.values()), {})
    source = {k: first.get(k) for k in ("source_name", "source_url", "source_date", "fetched_date")} if first else None
    value = {"occupations": occupations, "tasks": tasks, "source": source}
    _cache.update(key=key, value=value)
    return value


def percentiles(values: dict) -> dict:
    """Each key's percentile (0-100) among the values: the share of values strictly below it, plus half the ties."""
    ordered = sorted(values.values())
    n = len(ordered)
    out = {}
    for k, v in values.items():
        below = bisect.bisect_left(ordered, v)
        ties = bisect.bisect_right(ordered, v) - below
        out[k] = round(100 * (below + 0.5 * ties) / n, 1) if n else None
    return out


def ranks(data: dict) -> dict:
    """The percentile of every occupation on observed AI use and on ILO potential (mapped ones only)."""
    key = (id(data["ai"]), _cache["key"])
    if _ranks["key"] == key:
        return _ranks["value"]
    t = tables()["occupations"]
    observed, potential = {}, {}
    for occ in data["occupations"]:
        found = t.get(occ.get("isco") or "")
        role = data["ai"]["roles"].get(occ["occ_id"])
        if found and role and role.get("ai_share") is not None:
            observed[occ["occ_id"]] = role["ai_share"]
            potential[occ["occ_id"]] = found["mean_2025"]
    value = {"observed": percentiles(observed), "potential": percentiles(potential)}
    _ranks.update(key=key, value=value)
    return value


def for_occupation(occ: dict, data: dict, task_examples: int = 3) -> dict | None:
    """The ILO score of the occupation's ISCO-08 group with its mapping basis, its most and least
    exposed tasks, and how it compares with the observed AI use."""
    t = tables()
    found = t["occupations"].get(occ.get("isco") or "")
    if not found:
        return None
    tasks = sorted((x for x in t["tasks"].get(found["isco"], []) if x["score"] is not None), key=lambda x: -x["score"])
    r = ranks(data)
    pct_obs, pct_pot = r["observed"].get(occ["occ_id"]), r["potential"].get(occ["occ_id"])
    gap = None if pct_obs is None or pct_pot is None else round(pct_pot - pct_obs, 1)
    return {"isco": found["isco"], "isco_title": found["title"], "mapping": occ.get("isco_basis") or "none",
            "mean": found["mean_2025"], "sd": found["sd_2025"], "gradient": found["gradient"],
            "gradient_label": found["gradient_label"], "tasks": found["tasks"], "high_tasks": found["high_tasks"],
            "mean_2023": found["mean_2023"], "category_2023": found["category_2023"],
            "most_exposed": tasks[:task_examples], "least_exposed": tasks[-task_examples:][::-1] if tasks else [],
            "percentile_potential": pct_pot, "percentile_observed": pct_obs, "percentile_gap": gap,
            "disagree": gap is not None and abs(gap) >= DIVERGENCE,
            "direction": None if gap is None or abs(gap) < DIVERGENCE else
            ("potential_above_use" if gap > 0 else "use_above_potential"),
            "source": t["source"]}


def rules() -> dict:
    return {"divergence_points": DIVERGENCE, "gradients": list(GRADIENT_ORDER), "source": tables()["source"],
            "note": "ILO scores are technical potential (0-1); Anthropic shares are observed use (0-100). "
                    "They are shown side by side and never averaged."}
