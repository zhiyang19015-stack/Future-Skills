"""How much to trust one occupation's numbers: a rule-based evidence grade, not a probability.

A single confidence percentage would claim a precision we do not have. Instead three plain checks,
each worth 0, 1 or 2 points, say what the occupation's outlook rests on:

    ai_usage   2  enough of its own tasks are measured in the Anthropic Economic Index
               1  few of its tasks are measured; it leans on Anthropic's observed exposure for it
               0  it leans on the average of its field
    mapping    2  the O*NET occupation reaches a MASCO/ISCO-08 code exactly (ESCO crosswalk)
               1  through a close match
               0  only through a broad group, or not at all, so its Malaysian signals are its group's
    freshness  2  the AI-usage release is at most FRESH_AI_DAYS old and Malaysian demand was
                  computed at most FRESH_DEMAND_DAYS ago
               1  one of the two is older
               0  both are older

Grade A (5-6 points): the outlook rests on the occupation's own, recent data.
Grade B (3-4): usable, read the range.  Grade C (0-2): exploratory; treat the outlook as a hint.

A fourth check earns no points: the second source (scripts/ilo.py, agreement). When the ILO
research estimate and the observed AI use disagree, the grade is at most B, whatever the points:
an outlook two published sources do not agree on does not rest on "its own data" alone.

The thresholds are our assumptions and are listed on the Sources page. The grade is never
calibrated against outcomes, so it is never shown as a percentage.
"""

from datetime import date

import ilo

FRESH_AI_DAYS = 270          # an Economic Index release older than about nine months is stale
FRESH_DEMAND_DAYS = 60       # "Update data" runs weekly; two months without it is stale
GRADES = ((5, "A"), (3, "B"), (0, "C"))
MAPPING_POINTS = {"exact": 2, "close": 1, "broad": 0, "none": 0}
DISAGREE_CAP = "B"           # the best grade when the two AI sources disagree


def days_since(iso: str | None, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(str(iso)[:10])).days
    except (TypeError, ValueError):
        return None


def grade_of(points: int) -> str:
    return next(g for floor, g in GRADES if points >= floor)


def occupation_grade(occ: dict, data: dict, today: date | None = None) -> dict:
    """The evidence grade of one occupation with the reason for each of its three checks."""
    today = today or date.today()
    role = data["ai"]["roles"].get(occ["occ_id"], {})
    if role and not role.get("thin_evidence", True):
        ai_points, ai_reason = 2, "own_tasks"
    elif role.get("prior_basis") == "anthropic_exposure":
        ai_points, ai_reason = 1, "observed_exposure"
    else:
        ai_points, ai_reason = 0, "field_average"
    basis = occ.get("isco_basis") or "none"
    map_points = MAPPING_POINTS.get(basis, 0)
    ai_age = days_since(data["ai"]["source"]["economic_index"].get("release_date"), today)
    demand_age = days_since(data["demand"].get("computed_date"), today)
    stale = sum(1 for age, limit in ((ai_age, FRESH_AI_DAYS), (demand_age, FRESH_DEMAND_DAYS))
                if age is None or age > limit)
    fresh_points = 2 - stale
    points = ai_points + map_points + fresh_points
    second = ilo.agreement(occ, data)
    grade = grade_of(points)
    capped = second["verdict"] == "disagree" and grade < DISAGREE_CAP  # "A" < "B": A is the better grade
    tasks, covered = role.get("tasks") or 0, role.get("tasks_covered") or 0
    return {
        "grade": DISAGREE_CAP if capped else grade, "points": points, "max_points": 6, "capped": capped,
        "checks": [
            {"check": "ai_usage", "points": ai_points, "reason": ai_reason,
             "tasks": tasks, "tasks_covered": covered},
            {"check": "mapping", "points": map_points, "reason": basis},
            {"check": "freshness", "points": fresh_points, "reason": "fresh" if stale == 0 else "stale",
             "ai_release_days": ai_age, "demand_days": demand_age},
            {"check": "second_source", "points": None, "reason": second["verdict"],
             "percentile_observed": second["percentile_observed"],
             "percentile_potential": second["percentile_potential"], "gap": second["gap"]},
        ],
        "range": [role.get("ai_share_low"), role.get("ai_share_high")],
    }


def rules() -> dict:
    """The grade's thresholds, for the Sources page."""
    return {"fresh_ai_days": FRESH_AI_DAYS, "fresh_demand_days": FRESH_DEMAND_DAYS,
            "grades": {g: floor for floor, g in GRADES}, "mapping_points": MAPPING_POINTS,
            "disagree_cap": DISAGREE_CAP, "divergence_points": ilo.DIVERGENCE,
            "note": "A rule-based grade from three checks (0-2 points each); not a calibrated probability. "
                    "When the ILO research estimate and the observed AI use disagree, the grade is at most B."}
