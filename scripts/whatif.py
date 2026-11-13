"""Change the data and see what changes ("what if?").

"If this number were different, what would happen to my results?" is answered by running the
real pipeline on a changed copy of the inputs:

    data/demand_inputs.csv + occupations   -> demand.build       (Malaysian demand, research tempo)
    data/aei/ + data/onet/                 -> ai_exposure.build  (AI share, hands-off share)
                                           -> outlook -> matching

What can be changed:
    job_ads   the latest online job ads of a MASCO major group, as a % change (-90 to +200)
    arxiv     the latest 6-month count of AI papers on arXiv, as a % change (-90 to +200)
    mycol     an occupation's MyCOL status: yes / near / no
    handoff   the hands-off share of an AI-usage topic, 0-100 (the tools mapped to it)
    ai_share  "at least this much": the AI share of every task under one of O*NET's detailed
              work activities ("Record patient medical histories."), 0-100
The copy lives for one request: the data files, the "Update data" job and other people never
see it.

    changes = {"job_ads": {"5": -20}, "arxiv": 15, "mycol": {"29-1141.00": "no"},
               "handoff": {"<topic>": 70}, "ai_share": {"<work activity>": 95}}

NEWS holds ready-made changes written as headlines ("AI scribes now write clinical notes"):
simulated events, labelled as such on the page, to watch one piece of news move the skills,
the occupations, a person's ranking and their learning path, before and after. A headline may
name the fictional demo person whose work it is about ("person"), so the home page can play it
for them in one tap.

person_change() reads a change from one person's side: the job they do now (or, without one,
their first match), which of its tasks moved to AI, the tools they use that lose or gain value,
and the occupations in their own list that moved most. The page leads with that and keeps the
changed numbers underneath as the evidence.
"""

import ai_exposure
import demand
import matching
import outlook

MYCOL = ("yes", "near", "no")
KEYS = ("job_ads", "arxiv", "mycol", "handoff", "ai_share")
PCT_MIN, PCT_MAX = -90.0, 200.0
HANDOFF_MAX = 98.0       # a topic is never fully hands-off: someone still asks and checks
NEWS_FLOOR = 95.0
SHOWN_ACTIVITIES = 80    # work activities offered on the page (any of O*NET's can be sent)
LEAD_NEWS = "auto_bookkeeping"   # the headline the home page offers first
TASK_MOVE = 5.0          # points of AI share a task must move by to count as changed
TASKS_SHOWN = 5          # changed tasks of the person's job listed on the page
WATCHED = 10             # how far down the person's list an occupation is followed
MOVES_SHOWN = 3          # fallers and risers named in a person's list
RANK_MOVE = 2            # places an occupation must move in the person's list to be named

EXAMPLES = [
    ("service_ads_down", "Service and sales job ads fall 20%", {"job_ads": {"5": -20}}),
    ("professional_ads_up", "Ads for professionals rise 15%", {"job_ads": {"2": 15}}),
    ("ai_research_flat", "AI research stops growing", {"arxiv": -12}),
    ("nurses_off_mycol", "MyCOL drops Registered Nurses", {"mycol": {"29-1141.00": "no"}}),
    ("electricians_on_mycol", "MyCOL adds Electricians", {"mycol": {"47-2111.00": "yes"}}),
]
NEWS = [
    {"id": "coding_agents", "person": "P05", "field": "15", "title": "AI coding agents now ship whole features",
     "summary": "Agents plan, write, test and merge a feature from one request.",
     "handoff": {"Code design": 25, "Web front-end": 20, "Backend architecture": 20, "Test writing and running": 20,
                 "Git workflow": 20},
     "ai_share": ["Write computer programming code.", "Modify software programs to improve performance.",
                  "Design software applications.", "Develop software or computer applications.",
                  "Develop testing routines or procedures.", "Resolve computer software problems."]},
    {"id": "clinical_scribes", "person": "P01", "field": "29", "title": "AI scribes now write clinical notes",
     "summary": "The assistant listens to the consultation and drafts the notes and the referral letter.",
     "handoff": {"Medical Questions": 15},
     "ai_share": ["Record patient medical histories.", "Maintain medical records.",
                  "Prepare reports summarizing patient diagnostic or care activities.",
                  "Gather medical information from patient histories."]},
    {"id": "service_agents", "field": "43", "title": "AI agents answer most customer chats and calls",
     "summary": "Customers get answers, refunds and bookings from an AI agent; people take the hard cases.",
     "handoff": {"Customer support and service": 25, "Booking and scheduling": 20, "Account and billing": 20},
     "ai_share": ["Respond to customer inquiries.", "Correspond with customers to answer questions or resolve complaints.",
                  "Schedule appointments.", "Respond to customer problems or complaints."]},
    {"id": "auto_bookkeeping", "person": "P02", "field": "13", "title": "AI closes the monthly books",
     "summary": "Invoices, bank feeds and receipts are matched and reconciled without anyone typing them in.",
     "handoff": {"Accounting and bookkeeping": 25, "Financial modeling": 15},
     "ai_share": ["Reconcile records of sales or other financial transactions.", "Maintain financial or account records.",
                  "Verify accuracy of financial or transactional data.", "Prepare financial documents, reports, or budgets."]},
    {"id": "legal_drafting", "field": "23", "title": "AI drafts contracts and finds the case law",
     "summary": "A first draft and the relevant cases arrive in minutes; lawyers review and argue.",
     "handoff": {"Litigation": 20, "Regulatory rules": 20, "Business compliance": 15},
     "ai_share": ["Prepare legal documents.", "Research relevant legal materials to aid decision making.",
                  "Prepare documentation for contracts, transactions, or regulatory compliance."]},
    {"id": "ai_tutors", "field": "25", "title": "AI tutors mark homework and plan lessons",
     "summary": "Teachers get marked work and a draft lesson plan for every class each morning.",
     "handoff": {"Instructional design": 25, "Homework": 20},
     "ai_share": ["Evaluate student work.", "Document lesson plans.", "Develop instructional materials."]},
    {"id": "data_agents", "field": "15", "title": "AI analysts go from a question to a finished dashboard",
     "summary": "Ask in plain words; the agent queries, cleans, charts and explains the data.",
     "handoff": {"Data analysis": 25, "Dashboards and charts": 30, "Data storage": 20},
     "ai_share": ["Analyze data to identify trends or relationships among variables.", "Prepare data for analysis.",
                  "Prepare analytical reports.", "Analyze business or financial data."]},
    {"id": "design_generators", "person": "P04", "field": "27", "title": "Design tools generate whole campaigns from a brief",
     "summary": "A short brief becomes posters, social posts and a short video in seconds.",
     "handoff": {"Photo and video editing": 25, "Promotional writing": 20, "3D modeling and printing": 20},
     "ai_share": ["Create marketing materials.", "Write advertising or promotional material.",
                  "Create computer-generated graphics or animation.", "Design layouts for print publications.",
                  "Design layout of art or product exhibits, displays, or promotional materials.",
                  "Design websites or web applications."]},
]


class WhatIfError(ValueError):
    pass


def activity_counts(layer: dict) -> dict:
    groups = {}
    for task in layer["tasks"]:
        for g in task["work_activities"]:
            groups.setdefault(g, []).append(task)
    return groups


def editable() -> list[dict]:
    """The inputs a what-if may change, each with its value now, its limits and its source."""
    d = demand.current()
    out = []
    for g in d["groups"].values():
        out.append({"id": g["group"], "kind": "job_ads", "label": g["name"], "value": 0.0, "min": PCT_MIN,
                    "max": PCT_MAX, "share_before": g["share_before"], "share_after": g["share_after"],
                    "change_pct": g["change_pct"], "window": g["window_after"],
                    "source_name": demand.JMI_SOURCE, "source_url": demand.JMI_URL})
    m = d["momentum"]
    if m.get("momentum") is not None:
        out.append({"id": "arxiv", "kind": "arxiv", "label": "AI papers on arXiv (last 6 months)", "value": 0.0,
                    "min": PCT_MIN, "max": PCT_MAX, "growth_pct": m["growth_pct"], "papers": m["ai_papers_after"],
                    "source_name": "arXiv API", "source_url": "https://info.arxiv.org/help/api/"})
    layer = ai_exposure.current()
    src = layer["source"]["economic_index"]
    names = {s["skill_id"]: s["skill_name"] for s in layer["skills"].values()}
    for topic in sorted(layer["topics"].values(), key=lambda x: -(x["usage_pct"] or 0)):
        if topic["handoff_measured"] is not None:
            out.append({"id": topic["topic"], "kind": "handoff", "label": topic["topic"],
                        "value": topic["handoff_measured"], "min": 0.0, "max": HANDOFF_MAX,
                        "usage_pct": topic["usage_pct"], "skills": [names.get(s, s) for s in topic["skills"]][:12],
                        "period": layer["context"]["latest"], "source_name": src["source_name"],
                        "source_url": src["source_url"], "release_date": src["release_date"]})
    groups = activity_counts(layer)
    for g, tasks in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:SHOWN_ACTIVITIES]:
        out.append(activity_item(g, tasks, layer))
    return out


def activity_item(name: str, tasks: list[dict], layer: dict) -> dict:
    src = layer["source"]["economic_index"]
    return {"id": name, "kind": "ai_share", "label": name.rstrip("."), "min": 0.0, "max": 100.0,
            "value": round(sum(x["ai_share"] for x in tasks) / len(tasks), 1), "tasks": len(tasks),
            "roles": len({x["occ_id"] for x in tasks}), "period": layer["context"]["latest"],
            "source_name": src["source_name"], "source_url": src["source_url"], "release_date": src["release_date"]}


def examples() -> list[dict]:
    occs = matching.static_tables()["by_id"]
    out = []
    for eid, name, changes in EXAMPLES:
        if all(o in occs for o in (changes.get("mycol") or {})):
            out.append({"id": eid, "name": name, "changes": changes})
    return out


def news() -> list[dict]:
    """The simulated headlines as changes, worked out from the data as it is now."""
    layer = ai_exposure.current()
    groups = activity_counts(layer)
    topics = {t["topic"]: t for t in layer["topics"].values() if t["handoff_measured"] is not None}
    out = []
    for n in NEWS:
        handoff = {t: min(HANDOFF_MAX, round(topics[t]["handoff_measured"] + add, 1))
                   for t, add in n["handoff"].items() if t in topics}
        share = {a: NEWS_FLOOR for a in n["ai_share"]
                 if a in groups and sum(x["ai_share"] for x in groups[a]) / len(groups[a]) < NEWS_FLOOR}
        if handoff or share:
            out.append({"id": n["id"], "field": n["field"], "title": n["title"], "summary": n["summary"],
                        "person": n.get("person"), "lead": n["id"] == LEAD_NEWS,
                        "simulated": True, "changes": {"handoff": handoff, "ai_share": share}})
    return out


def number(v, name: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise WhatIfError(f"'{name}' must be a number from {lo:g} to {hi:g}")
    return float(v)


def validate(changes) -> dict:
    """Check a changes object and drop entries equal to the data now. WhatIfError if bad."""
    out = {"job_ads": {}, "arxiv": 0.0, "mycol": {}, "handoff": {}, "ai_share": {}}
    if changes is None:
        return out
    if not isinstance(changes, dict) or set(changes) - set(KEYS):
        raise WhatIfError(f"'trend_changes' must be an object with any of {list(KEYS)}")
    d = demand.current()
    for g, v in (changes.get("job_ads") or {}).items():
        if g not in d["groups"]:
            raise WhatIfError(f"'{g}' is not a MASCO major group with job-ad data")
        if number(v, f"job_ads.{g}", PCT_MIN, PCT_MAX):
            out["job_ads"][g] = float(v)
    if changes.get("arxiv") not in (None, 0):
        out["arxiv"] = number(changes["arxiv"], "arxiv", PCT_MIN, PCT_MAX)
    occs = matching.static_tables()["by_id"]
    for occ_id, v in (changes.get("mycol") or {}).items():
        if occ_id not in occs:
            raise WhatIfError(f"'{occ_id}' is not an occupation")
        if v not in MYCOL:
            raise WhatIfError(f"MyCOL status of '{occ_id}' must be one of {list(MYCOL)}")
        if v != occs[occ_id]["mycol"]:
            out["mycol"][occ_id] = v
    layer = ai_exposure.current()
    topics = {t["topic"]: t["handoff_measured"] for t in layer["topics"].values() if t["handoff_measured"] is not None}
    for name, v in (changes.get("handoff") or {}).items():
        if name not in topics:
            raise WhatIfError(f"'{name}' is not an AI-usage topic that can be changed")
        if number(v, name, 0, HANDOFF_MAX) != topics[name]:
            out["handoff"][name] = float(v)
    groups = activity_counts(layer)
    for name, v in (changes.get("ai_share") or {}).items():
        if name not in groups:
            raise WhatIfError(f"'{name}' is not one of O*NET's work activities")
        out["ai_share"][name] = number(v, name, 0, 100)
    return out


def changed(changes: dict | None) -> bool:
    return bool(changes and any(changes.get(k) for k in KEYS))


def changed_data(data: dict, changes: dict) -> dict:
    """A copy of a matching.load_data() result built from the changed inputs."""
    d = data["demand"]
    if changes.get("job_ads") or changes.get("arxiv") or changes.get("mycol"):
        d = demand.build(changes={k: changes[k] for k in ("job_ads", "arxiv", "mycol") if changes.get(k)})
    ai = data["ai"]
    if changes.get("handoff") or changes.get("ai_share"):
        ai = ai_exposure.build(changes={"handoff": changes.get("handoff"), "ai_share": changes.get("ai_share")})
    by_id = data["by_id"]
    if changes.get("mycol"):
        occupations = [{**o, "mycol": changes["mycol"].get(o["occ_id"], o["mycol"])} for o in data["occupations"]]
        by_id = {o["occ_id"]: o for o in occupations}
    else:
        occupations = data["occupations"]
    return {**data, "demand": d, "ai": ai, "occupations": occupations, "by_id": by_id}


def describe(changes: dict) -> list[dict]:
    """Each changed input, before and after, for the page."""
    d, layer = demand.current(), ai_exposure.current()
    occs = matching.static_tables()["by_id"]
    out = []
    for g, v in changes.get("job_ads", {}).items():
        out.append({"id": g, "kind": "job_ads", "label": d["groups"][g]["name"], "before": 0.0, "after": v,
                    "unit": "%", "source_name": demand.JMI_SOURCE})
    if changes.get("arxiv"):
        out.append({"id": "arxiv", "kind": "arxiv", "label": "AI papers on arXiv", "before": 0.0,
                    "after": changes["arxiv"], "unit": "%", "source_name": "arXiv API"})
    for occ_id, v in changes.get("mycol", {}).items():
        out.append({"id": occ_id, "kind": "mycol", "label": occs[occ_id]["title"], "before": occs[occ_id]["mycol"],
                    "after": v, "source_name": "MyCOL 2024/2025"})
    topics = {t["topic"]: t for t in layer["topics"].values()}
    for name, v in changes.get("handoff", {}).items():
        out.append({"id": name, "kind": "handoff", "label": name, "before": topics[name]["handoff_measured"], "after": v,
                    "skills": topics[name]["skills"][:8], "source_name": layer["source"]["economic_index"]["source_name"]})
    groups = activity_counts(layer)
    for name, v in changes.get("ai_share", {}).items():
        item = activity_item(name, groups[name], layer)
        out.append({"id": name, "kind": "ai_share", "label": item["label"], "before": item["value"], "after": v,
                    "tasks": item["tasks"], "source_name": item["source_name"]})
    return out


def role_changes(before: dict, after: dict, adoption: float, limit: int = 25) -> list[dict]:
    """Occupations whose outlook, or a signal behind it, differs between two data dicts, biggest move first."""
    keys = ("outlook", "status", "demand", "tempo", "ai_share", "builder")
    out = []
    for occ in before["occupations"]:
        b = outlook.role_outlook(occ, before, adoption)
        a = outlook.role_outlook(after["by_id"][occ["occ_id"]], after, adoption)
        if any(b[k] != a[k] for k in keys):
            out.append({"occ_id": occ["occ_id"], "title": occ["title"], "field_id": occ["field_id"],
                        "before": {k: b[k] for k in keys}, "after": {k: a[k] for k in keys},
                        "move": round(a["outlook"] - b["outlook"], 1)})
    return sorted(out, key=lambda r: -abs(r["move"]))[:limit]


def skill_changes(before: dict, after: dict, adoption: float, limit: int = 25) -> list[dict]:
    """Skills and tools whose weight or status differs between two data dicts, biggest move first."""
    b, a = outlook.skill_weights(before, adoption), outlook.skill_weights(after, adoption)
    out = []
    for sid, x in a.items():
        y = b.get(sid, matching.STEADY)
        if (x["weight"], x["status"], x["handoff"]) != (y["weight"], y["status"], y["handoff"]):
            out.append({"skill_id": sid, "skill_name": after["ai"]["skills"][sid]["skill_name"],
                        "before": {k: y[k] for k in ("weight", "status", "handoff")},
                        "after": {k: x[k] for k in ("weight", "status", "handoff")},
                        "move": round(x["weight"] - y["weight"], 3)})
    return sorted(out, key=lambda s: -abs(s["move"]))[:limit]


def path_changes(before: dict | None, after: dict | None) -> dict | None:
    """How one occupation's free learning path differs between two matches: what it leads with."""
    if not before or not after:
        return None

    def steps(m):
        return [{"title": s["title"], "provider": s["provider"], "url": s["url"], "hours": s["hours"],
                 "skills": s["skills"], "status": s["ai"]["status"]} for s in m["pathway"]["steps"]]

    def learn(m):
        return [{"skill_id": t["skill_id"], "skill_name": t["skill_name"], "status": t["ai"]["status"]}
                for t in m["skill_detail"]["tech_missing"][:5]]
    sb, sa = steps(before), steps(after)
    return {"occ_id": before["occ_id"], "role_id": before["occ_id"], "role_name": before["title"],
            "before": {"steps": sb[:6], "learn_next": learn(before), "total_hours": before["pathway"]["total_hours"]},
            "after": {"steps": sa[:6], "learn_next": learn(after), "total_hours": after["pathway"]["total_hours"]},
            "order_changed": [s["url"] for s in sb] != [s["url"] for s in sa]
            or [t["skill_id"] for t in learn(before)] != [t["skill_id"] for t in learn(after)]}


def occupation_change(occ_id: str | None, before: dict, after: dict, adoption: float) -> dict | None:
    """One occupation before and after a change: the AI share of its tasks, its outlook, and the
    tasks whose AI share moved, the most important first."""
    occ = before["by_id"].get(occ_id or "")
    if occ is None:
        return None
    b = outlook.role_outlook(occ, before, adoption)
    a = outlook.role_outlook(after["by_id"][occ_id], after, adoption)
    was = {t["task_id"]: t for t in before["ai"]["tasks_by_occ"].get(occ_id, [])}
    moved = []
    for t in after["ai"]["tasks_by_occ"].get(occ_id, []):
        old = was.get(t["task_id"])
        if old is not None and abs(t["ai_share"] - old["ai_share"]) >= TASK_MOVE:
            moved.append({"task_id": t["task_id"], "task": t["task"], "importance": t["importance"],
                          "before": old["ai_share"], "after": t["ai_share"]})
    moved.sort(key=lambda t: (-(t["importance"] or 0), t["task"]))
    outlook_move = round(a["outlook"] - b["outlook"], 1)
    return {"occ_id": occ_id, "title": occ["title"], "field_id": occ["field_id"],
            "ai_share": {"before": b["ai_share"], "after": a["ai_share"]},
            "outlook": {"before": b["outlook"], "after": a["outlook"]},
            "status": {"before": b["status"], "after": a["status"]},
            "ai_share_move": round(a["ai_share"] - b["ai_share"], 1), "outlook_move": outlook_move,
            "ai_share_reference": a["ai_share_reference"],
            "tasks": len(was), "tasks_moved": len(moved), "moved": moved[:TASKS_SHOWN],
            # a change elsewhere shifts the average a little, so a small drift is not "touched"
            "touched": bool(moved) or abs(outlook_move) >= outlook.ROLE_BAND / 2}


def person_change(profile: dict, before: dict, after: dict, adoption: float,
                  before_rows: list[dict], after_rows: list[dict]) -> dict:
    """A change read from one person's side, for the top of the result.

    subject   the job they do now or, without one, their first occupation before the change:
              its AI share, outlook and the tasks that moved (occupation_change)
    tools     the tools the person uses whose hands-off share or status changed
    first     their first occupation before and after
    reached   occupations in the first WATCHED of either list with tasks the change moved, the
              biggest rise in AI share first: where the change lands in the person's own options
    fallers, risers   occupations in the same lists that moved RANK_MOVE places or more, the
              biggest move first
    before_rows and after_rows are the person's listed occupations in rank order under one scenario.
    """
    current = profile.get("current_occupation")
    subject_id = current or (before_rows[0]["occ_id"] if before_rows else None)
    place_b = {m["occ_id"]: (i + 1, m) for i, m in enumerate(before_rows)}
    place_a = {m["occ_id"]: (i + 1, m) for i, m in enumerate(after_rows)}
    moves = []
    for occ_id in dict.fromkeys([m["occ_id"] for m in before_rows[:WATCHED] + after_rows[:WATCHED]]):
        if occ_id not in place_b or occ_id not in place_a:
            continue
        (rank_b, b), (rank_a, a) = place_b[occ_id], place_a[occ_id]
        moves.append({"occ_id": occ_id, "title": b["title"], "field_id": b["field_id"],
                      "rank": {"before": rank_b, "after": rank_a}, "rank_move": rank_b - rank_a,
                      "total": {"before": b["total"], "after": a["total"]},
                      "total_move": round(a["total"] - b["total"], 1),
                      "status": {"before": b["outlook"]["status"], "after": a["outlook"]["status"]}})
    fallers = sorted((m for m in moves if m["rank_move"] <= -RANK_MOVE), key=lambda m: (m["rank_move"], m["total_move"]))
    risers = sorted((m for m in moves if m["rank_move"] >= RANK_MOVE), key=lambda m: (-m["rank_move"], -m["total_move"]))
    reached = []
    for m in moves:
        c = occupation_change(m["occ_id"], before, after, adoption)
        if c and c["tasks_moved"]:
            reached.append({**m, "ai_share": c["ai_share"], "ai_share_move": c["ai_share_move"],
                            "tasks": c["tasks"], "tasks_moved": c["tasks_moved"]})
    reached.sort(key=lambda m: (-m["ai_share_move"], m["rank"]["before"]))
    w_before, w_after = outlook.skill_weights(before, adoption), outlook.skill_weights(after, adoption)
    tools = []
    for tid in profile.get("technologies") or []:
        x, y = w_before.get(tid, matching.STEADY), w_after.get(tid, matching.STEADY)
        if (x["status"], x["handoff"]) != (y["status"], y["handoff"]):
            tools.append({"skill_id": tid, "skill_name": after["technologies"][tid]["name"],
                          "status": {"before": x["status"], "after": y["status"]},
                          "handoff": {"before": x["handoff"], "after": y["handoff"]},
                          "weight_move": round(y["weight"] - x["weight"], 3)})
    tools.sort(key=lambda t: (t["weight_move"], t["skill_name"]))

    def brief(m):
        return None if m is None else {"occ_id": m["occ_id"], "title": m["title"], "total": m["total"]}
    first_b = before_rows[0] if before_rows else None
    first_a = after_rows[0] if after_rows else None
    return {"subject_kind": "current" if current else "top",
            "subject": occupation_change(subject_id, before, after, adoption),
            "tools": tools,
            "first": {"before": brief(first_b), "after": brief(first_a),
                      "changed": bool(first_b and first_a and first_b["occ_id"] != first_a["occ_id"])},
            "reached": reached[:MOVES_SHOWN], "fallers": fallers[:MOVES_SHOWN], "risers": risers[:MOVES_SHOWN]}
