"""Robust and scenario-dependent choices: which occupations hold under every named scenario, which
ones only make the list under some, and why, in numbers our code computed.

Input: one person's list of moves (the listed occupations, best first) under each named scenario,
exactly as matching.rank scores them. Nothing here changes a score or a coefficient; it only reads
the three existing rankings.

Our rules (not data; README and SOURCES.md, "Choices and limits"):
    robust                 in the first ROBUST_TOP under every named scenario. "first" when it is
                           first under all of them.
    scenario-dependent     in the first TOP under at least one scenario and either missing from the
                           first TOP under another, or its rank moves by RANK_SWING places or more.

The "why" of each scenario-dependent choice says which part of the match score moved between the
slowest and the fastest scenario, with the numbers:
    share_low / share_high  the outlook moved because its AI share of tasks is below / above the
                            average occupation's
    builder                 the outlook moved because its tools build AI more / less than average
    skills_up / skills_down the skill fit moved: the skills it needs count more / less as AI spreads
    others                  its own score barely moves (under OWN_MOVE points); the occupations
                            around it move more ("crossed" names the one of those that moves most)
Scenario results are estimates under an assumption about how fast AI spreads, not predictions.
"""

ROBUST_TOP = 3     # robust: in the first 3 under every named scenario
TOP = 5            # compared: the first 5 under each scenario
RANK_SWING = 2     # places; a rank move this large within the first TOP counts as scenario-dependent
OWN_MOVE = 0.3     # match points; a smaller move of its own score does not explain a move in rank

REASONS = ("share_low", "share_high", "builder", "skills_up", "skills_down", "others")


def _points(m: dict, part: str) -> float:
    return m["components"][part]["points"] or 0.0


def reason(slow: dict, fast: dict) -> dict:
    """Why one occupation's place differs between the slowest and the fastest scenario."""
    total_move = round(fast["total"] - slow["total"], 1)
    outlook_pts = _points(fast, "outlook") - _points(slow, "outlook")
    skill_pts = _points(fast, "skill") - _points(slow, "skill")
    o_fast, o_slow = fast["outlook"], slow["outlook"]
    exposure = o_fast["exposure_points"] - o_slow["exposure_points"]
    builder = o_fast["builder_points"] - o_slow["builder_points"]
    if abs(total_move) < OWN_MOVE:
        code = "others"
    elif abs(outlook_pts) >= abs(skill_pts):
        if abs(exposure) >= abs(builder):
            code = "share_low" if exposure > 0 else "share_high"
        else:
            code = "builder"
    else:
        code = "skills_up" if skill_pts > 0 else "skills_down"
    return {"code": code, "total_move": total_move,
            "outlook_move": round(o_fast["outlook"] - o_slow["outlook"], 1),
            "outlook_points": round(outlook_pts, 1), "skill_points": round(skill_pts, 1),
            "skill_move": round((fast["components"]["skill"]["score"] or 0) - (slow["components"]["skill"]["score"] or 0), 1),
            "ai_share": o_fast["ai_share"], "ai_share_reference": o_fast["ai_share_reference"],
            "thin": bool(o_fast.get("thin")),
            "builder": o_fast["builder"], "builder_reference": o_fast["builder_reference"]}


def crossed(occ_id: str, ranks: dict, by_name: dict, slow: str, fast: str) -> dict | None:
    """Of the occupations it swaps places with between slow and fast, the one whose own score moves
    most: the other side of a rank move its own score does not explain."""
    mine = ranks[occ_id]
    up = mine[fast] < mine[slow]
    best = None
    for other, r in ranks.items():
        if other == occ_id or slow not in r or fast not in r:
            continue
        if (r[slow] < mine[slow] and r[fast] > mine[fast]) if up else (r[slow] > mine[slow] and r[fast] < mine[fast]):
            move = by_name[other][fast]["total"] - by_name[other][slow]["total"]
            if best is None or abs(move) > abs(best["total_move"]):
                best = {"occ_id": other, "title": by_name[other][slow]["title"], "total_move": round(move, 1),
                        "ai_share": by_name[other][fast]["outlook"]["ai_share"]}
    return best


def classify(orders: dict) -> dict:
    """orders: {scenario name: [listed match dicts, best first]}, in the order slow -> fast.

    Returns the robust choices, the scenario-dependent ones (each with its why), and the rules."""
    names = [n for n in orders if orders[n]]
    rules = {"robust_top": ROBUST_TOP, "top": TOP, "rank_swing": RANK_SWING, "own_move": OWN_MOVE,
             "estimate": True}
    if len(names) < 2:
        return {"robust": [], "dependent": [], "rules": rules, "scenarios": names}
    slow, fast = names[0], names[-1]
    ranks, by_name = {}, {}
    for n in names:
        for i, m in enumerate(orders[n]):
            ranks.setdefault(m["occ_id"], {})[n] = i + 1
            by_name.setdefault(m["occ_id"], {})[n] = m
    seen = []
    for n in names:
        for m in orders[n][:TOP]:
            if m["occ_id"] not in seen:
                seen.append(m["occ_id"])
    robust, dependent = [], []
    for occ_id in seen:
        r = ranks[occ_id]
        if len(r) < len(names):  # not listed under every scenario: cannot be compared
            continue
        title = by_name[occ_id][slow]["title"]
        totals = {n: by_name[occ_id][n]["total"] for n in names}
        if all(r[n] <= ROBUST_TOP for n in names):
            first = all(r[n] == 1 for n in names)
            # the lead over the next occupation, smallest across scenarios, when it is first in all
            lead = min(orders[n][0]["total"] - orders[n][1]["total"] for n in names if len(orders[n]) > 1) \
                if first and all(len(orders[n]) > 1 for n in names) else None
            robust.append({"occ_id": occ_id, "title": title, "kind": "first" if first else "top3",
                           "ranks": r, "totals": totals, "worst_rank": max(r.values()),
                           "score_move": round(max(totals.values()) - min(totals.values()), 1),
                           "lead": None if lead is None else round(lead, 1)})
            continue
        inside = [n for n in names if r[n] <= TOP]
        swing = max(r.values()) - min(r.values())
        if len(inside) < len(names) or swing >= RANK_SWING:
            dependent.append({"occ_id": occ_id, "title": title, "ranks": r, "totals": totals,
                              "in_top": inside, "kind": "enters" if len(inside) < len(names) else "moves",
                              "rank_swing": swing,
                              "why": {**reason(by_name[occ_id][slow], by_name[occ_id][fast]),
                                      "crossed": crossed(occ_id, ranks, by_name, slow, fast)}})
    robust.sort(key=lambda x: (x["kind"] != "first", x["worst_rank"], x["title"]))
    dependent.sort(key=lambda x: (-x["rank_swing"], x["title"]))
    return {"robust": robust, "dependent": dependent, "rules": rules, "scenarios": names,
            "slow": slow, "fast": fast}
