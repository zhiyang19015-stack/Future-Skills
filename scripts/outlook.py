"""Scenarios: one explicit speed-of-AI-adoption parameter, applied to the measured signals.

Signals (measured; each has a source and a date on the Sources page):
    demand     Malaysian demand for the occupation, 0-100: MyCOL status and the DOSM job-ad share
               of its MASCO major group (scripts/demand.py)
    ai_share   how much of the occupation's tasks people already hand to AI, 0-100, with a low
               and a high reading (scripts/ai_exposure.py)
    builder    the part of the occupation's Hot technologies that are used to build AI, 0-100
    tempo      how fast AI research is moving: the growth of AI papers on arXiv (demand.py's
               momentum), mapped from 0..100 to 0.5..1.5
    handoff    per skill, 0-100: when AI is used for it, how often it is handed over entirely

The parameter:
    adoption   0 to 1: how far, by HORIZON_YEAR, AI use moves from where the latest data has it
               towards being used wherever it can be. 0 = nothing changes. SCENARIOS names three
               values; the page also takes any value (the slider).

Occupation outlook, 0-100:
    pace    = adoption x tempo                                           (at most 1)
    shift   = BUILDER_SHIFT x (builder - average) - EXPOSURE_SHIFT x gap
    gap     = ai_share - average, or max(0, ai_share - average) when the share is thin
              (index points per 100 points of difference, at pace 1; averages over every occupation)
    outlook = demand + pace x shift
  In words: AI adoption moves demand away from occupations whose tasks are handed to AI more than
  the average occupation, towards those that build AI and those measured to hand over less. A thin
  share (few of the occupation's own tasks seen) earns nothing below the average: the Economic
  Index measures chat-AI use only, so a low share there says nothing about ATMs, robots or
  self-service machines. It says nothing about total hiring, which nobody can measure yet.

Skill weight (the skill fit in matching.py, and "rising / declining" on the Radar):
    drift   = SKILL_BUILDER_SHIFT x builder - SKILL_SHIFT x (handoff - typical AI use) / 100
    weight  = 1 + adoption x drift                (kept within WEIGHT_MIN..WEIGHT_MAX; no data = 1)
  A skill AI takes over more than typical AI use does counts for less as adoption grows: having
  it sets a person apart less. A skill people keep doing themselves counts for more.

Status: a role is "rising" when pace x shift is at least ROLE_BAND points, "declining" when at
most -ROLE_BAND; a skill when its weight leaves 1 +- SKILL_BAND. At adoption 0 everything is
"steady", so rising and declining are always read under a named scenario, never as one verdict.

simulate() draws FUTURES futures (the adoption speed, each occupation's demand and AI share,
and the two shift constants) and counts how often each occupation stays near the top: the range
around a recommendation, in numbers.

Every constant below is our assumption, not data (SOURCES.md, "Choices and limits").
"""

import hashlib
import json
import random

HORIZON_YEAR = 2030
SCENARIOS = {
    "slow": {"name": "Slow AI adoption", "adoption": 0.10,
             "description": "AI tools spread slowly and unevenly. By 2030 about a tenth of the gap between "
                            "today's AI use and using it wherever it can be has closed."},
    "moderate": {"name": "Moderate AI adoption", "adoption": 0.25,
                 "description": "AI use keeps spreading at a steady pace. By 2030 about a quarter of the gap "
                                "has closed."},
    "fast": {"name": "Fast AI adoption", "adoption": 0.50,
             "description": "AI agents become normal at work. By 2030 about half of the gap has closed."},
}
DEFAULT_SCENARIO = "moderate"
ADOPTION_MAX = 0.9

EXPOSURE_SHIFT = 100.0      # points an occupation loses at pace 1 when its AI share is 100 points above average
BUILDER_SHIFT = 60.0        # points it gains when its builder share is 100 points above average
TEMPO_SPAN = 0.5            # tempo runs from 1 - span (AI research shrinking) to 1 + span (growing fast)
SKILL_SHIFT = 2.0           # weight a skill loses at adoption 1 when its handoff is 100 points above typical use
SKILL_BUILDER_SHIFT = 1.0   # weight a skill that builds AI gains at adoption 1
WEIGHT_MIN, WEIGHT_MAX = 0.4, 1.6
ROLE_BAND = 2.0             # outlook points from demand before an occupation is called rising or declining
SKILL_BAND = 0.05           # weight from 1 before a skill is called rising or declining
NEUTRAL = 50.0              # demand of an occupation with no demand data

FUTURES = 1000
ADOPTION_SHAPE = (2.0, 4.0)  # beta shape of adoption across futures x ADOPTION_MAX: mean 0.30, most likely 0.23
DEMAND_SD = 5.0              # points: the demand signals are few and medium-confidence
PARAM_SPREAD = 0.3           # the two shift constants vary +-30% between futures
GRID_STEP = 0.05
GRID = [round(i * GRID_STEP, 2) for i in range(int(ADOPTION_MAX / GRID_STEP) + 1)]


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def adoption_of(scenario: str | None = None, adoption: float | None = None) -> float:
    """The adoption value of a named scenario, or the given value kept within 0..ADOPTION_MAX."""
    if adoption is not None:
        return clamp(float(adoption), 0.0, ADOPTION_MAX)
    return SCENARIOS[scenario or DEFAULT_SCENARIO]["adoption"]


def role_signals(role: dict, data: dict) -> dict:
    """The measured signals of one occupation, each with whether it had data."""
    d = data["demand"]["occupations"].get(role["occ_id"], {})
    ai = data["ai"]["roles"].get(role["occ_id"], {})
    momentum = data["demand"]["momentum"].get("momentum")
    return {
        "demand": d["demand"] if d.get("demand") is not None else NEUTRAL,
        "has_demand": d.get("demand") is not None,
        "momentum": momentum,
        "tempo": round(1 + TEMPO_SPAN * clamp((momentum - 50) / 50, -1.0, 1.0), 3) if momentum is not None else 1.0,
        "ai_share": ai.get("ai_share") if ai.get("ai_share") is not None else data["ai"]["reference"]["role_ai_share"],
        "ai_share_low": ai.get("ai_share_low"), "ai_share_high": ai.get("ai_share_high"),
        "has_ai_share": ai.get("ai_share") is not None,
        "thin": ai.get("thin_evidence", True),
        "builder": ai.get("builder_share", 0.0),
    }


def outlook_value(demand: float, ai_share: float, builder: float, tempo: float, adoption: float, reference: dict,
                  exposure_shift: float = EXPOSURE_SHIFT, builder_shift: float = BUILDER_SHIFT,
                  thin: bool = False) -> dict:
    pace = min(1.0, adoption * tempo)
    # A share above the average always lowers the outlook. A share below it raises the outlook only
    # when it is measured on the occupation's own tasks: a thin share (few of its tasks seen in the
    # Economic Index, which sees chat-AI use only) is no evidence against ATMs, robots or self-service.
    gap = ai_share - reference["role_ai_share"]
    exposure = -pace * exposure_shift * (max(0.0, gap) if thin else gap) / 100
    build = pace * builder_shift * (builder - reference["role_builder_share"]) / 100
    return {"pace": pace, "exposure_points": exposure, "builder_points": build,
            "outlook": clamp(demand + exposure + build)}


def status(change: float, band: float) -> str:
    return "rising" if change >= band else "declining" if change <= -band else "steady"


def role_outlook(role: dict, data: dict, adoption: float) -> dict:
    """One occupation's outlook under an adoption value, with every part that made it."""
    s, ref = role_signals(role, data), data["ai"]["reference"]
    v = outlook_value(s["demand"], s["ai_share"], s["builder"], s["tempo"], adoption, ref, thin=s["thin"])
    change = v["exposure_points"] + v["builder_points"]
    return {**s, "adoption": adoption, "pace": round(v["pace"], 3),
            "exposure_points": round(v["exposure_points"], 1), "builder_points": round(v["builder_points"], 1),
            "change": round(change, 1), "outlook": round(v["outlook"], 1), "status": status(change, ROLE_BAND),
            "ai_share_reference": ref["role_ai_share"], "builder_reference": ref["role_builder_share"]}


def skill_weight(skill: dict | None, adoption: float, reference: dict) -> dict:
    """How much one skill counts under an adoption value: its weight, why, and its status."""
    if not skill or skill.get("handoff") is None:
        return {"weight": 1.0, "drift": 0.0, "status": "steady", "handoff": None, "builder": False,
                "measured": False}
    drift = (SKILL_BUILDER_SHIFT * (1.0 if skill["builder"] else 0.0)
             - SKILL_SHIFT * (skill["handoff"] - reference["skill_handoff"]) / 100)
    weight = clamp(1 + adoption * drift, WEIGHT_MIN, WEIGHT_MAX)
    return {"weight": round(weight, 3), "drift": round(drift, 3), "status": status(weight - 1, SKILL_BAND),
            "handoff": skill["handoff"], "builder": skill["builder"], "measured": True}


def skill_weights(data: dict, adoption: float) -> dict:
    ref = data["ai"]["reference"]
    return {sid: skill_weight(s, adoption, ref) for sid, s in data["ai"]["skills"].items()}


def interpolate(curve: list[float], adoption: float) -> float:
    """A value read off a curve given at GRID points."""
    x = clamp(adoption, 0.0, ADOPTION_MAX) / GRID_STEP
    i = min(int(x), len(curve) - 2)
    return curve[i] + (curve[i + 1] - curve[i]) * (x - i)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def seed_of(roles: list[dict]) -> int:
    """The same inputs always draw the same futures, so a result can be shown again and checked."""
    text = json.dumps([[r["occ_id"], r["field"], r["interest"], r["skill_curve"], r["demand"], r["ai_share"],
                        r["bonus"]] for r in roles], sort_keys=True)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def simulate(roles: list[dict], total, reference: dict, n: int = FUTURES, seed: int | None = None) -> dict:
    """Rank the occupations in n drawn futures.

    roles: one dict per occupation with occ_id, field and interest (0-100 or None), skill_curve
    (the skill fit at each GRID adoption value, or None), demand, ai_share with ai_share_low /
    _high, builder, tempo, bonus (SDG points) and last (True for one ranked after the others).
    total(field, interest, skill, outlook) is matching's own weighted total, so a future is
    scored exactly as the page scores the occupation.
    """
    rng = random.Random(seed_of(roles) if seed is None else seed)
    scores = {r["occ_id"]: [] for r in roles}
    ranks = {r["occ_id"]: [] for r in roles}
    adoptions = []
    for _ in range(n):
        adoption = rng.betavariate(*ADOPTION_SHAPE) * ADOPTION_MAX
        adoptions.append(adoption)
        k_exposure = EXPOSURE_SHIFT * rng.uniform(1 - PARAM_SPREAD, 1 + PARAM_SPREAD)
        k_builder = BUILDER_SHIFT * rng.uniform(1 - PARAM_SPREAD, 1 + PARAM_SPREAD)
        drawn = []
        for r in roles:
            lo, hi = r.get("ai_share_low"), r.get("ai_share_high")
            share = rng.triangular(lo, hi, clamp(r["ai_share"], lo, hi)) if lo is not None and hi is not None and hi > lo \
                else r["ai_share"]
            v = outlook_value(clamp(r["demand"] + rng.gauss(0, DEMAND_SD)), share, r["builder"], r["tempo"],
                              adoption, reference, k_exposure, k_builder, thin=r.get("thin", False))
            skill = interpolate(r["skill_curve"], adoption) if r["skill_curve"] else None
            score = min(100.0, total(r["field"], r["interest"], skill, v["outlook"]) + r["bonus"])
            scores[r["occ_id"]].append(score)
            drawn.append((r["last"], -score, r["occ_id"]))
        for place, (_, _, rid) in enumerate(sorted(drawn), 1):
            ranks[rid].append(place)
    out = {}
    for r in roles:
        rid = r["occ_id"]
        out[rid] = {"top1": round(100 * sum(1 for p in ranks[rid] if p == 1) / n, 1),
                    "top3": round(100 * sum(1 for p in ranks[rid] if p <= 3) / n, 1),
                    "top5": round(100 * sum(1 for p in ranks[rid] if p <= 5) / n, 1),
                    "score_low": round(percentile(scores[rid], 0.1), 1),
                    "score_mid": round(percentile(scores[rid], 0.5), 1),
                    "score_high": round(percentile(scores[rid], 0.9), 1),
                    "rank_best": percentile(ranks[rid], 0.1), "rank_worst": percentile(ranks[rid], 0.9)}
    return {"futures": n, "roles": out,
            "adoption": {"low": round(percentile(adoptions, 0.1), 2), "mid": round(percentile(adoptions, 0.5), 2),
                         "high": round(percentile(adoptions, 0.9), 2)},
            "assumptions": {"adoption_shape": list(ADOPTION_SHAPE), "adoption_max": ADOPTION_MAX,
                            "demand_sd": DEMAND_SD, "param_spread": PARAM_SPREAD}}


def parameters() -> dict:
    """Every constant of the model, for the Sources page and the API."""
    return {"horizon_year": HORIZON_YEAR, "default_scenario": DEFAULT_SCENARIO, "adoption_max": ADOPTION_MAX,
            "exposure_shift": EXPOSURE_SHIFT, "builder_shift": BUILDER_SHIFT, "tempo_span": TEMPO_SPAN,
            "skill_shift": SKILL_SHIFT, "skill_builder_shift": SKILL_BUILDER_SHIFT,
            "weight_min": WEIGHT_MIN, "weight_max": WEIGHT_MAX, "role_band": ROLE_BAND, "skill_band": SKILL_BAND,
            "futures": FUTURES, "demand_sd": DEMAND_SD, "param_spread": PARAM_SPREAD,
            "adoption_shape": list(ADOPTION_SHAPE)}
