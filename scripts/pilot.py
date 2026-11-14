"""The clarity check: Phase 1's KPI 1, measured with people instead of claimed.

KPI 1 asks whether a person can name a target occupation, its biggest missing skill and a first
course. A career-centre officer opens a workshop session and gets a short code and a private key.
Each participant answers the same three questions before using the app and again after it. Every
answer is a pick from a list (an occupation, one of O*NET's skills and knowledge areas, a free
resource) or "not sure yet": no name and no typed text, so nothing personal can be written down.

Two readings, kept apart:
  named       the person picked an answer to all three questions. Counted as given.
  consistent  after the workshop, the three answers also agree with the data: the skill is one
              O*NET lists for that occupation, and the course is a free resource that teaches one
              of its skills or tools, or its field.
Rates are over the people who answered both before and after. Below MIN_PEOPLE such people the
counts are shown but must not be read as a rate (KPI 1 asks for 20 or more testers).

Only the officer's key opens a session's results; every response is kept and can be exported.
A session and its answers are deleted KEEP_DAYS after it was opened.

Stored in .cache/pilot.json: per session a hash of the key, the date, and per random browser id
and phase the three picks and the date.
"""

import hashlib
import hmac
import json
import re
import secrets
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import matching

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / ".cache" / "pilot.json"
PHASES = ("before", "after")
QUESTIONS = ("occupation", "gap", "course")
TARGET_PCT = 70            # KPI 1: 70% can name all three after the workshop ...
MIN_PEOPLE = 20            # ... of 20 or more testers
KEEP_DAYS = 180
MAX_SESSIONS = 200
MAX_PEOPLE = 300           # per session; a workshop is about 40
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I: a code is read out in a room
CODE_RE = re.compile(rf"^[{ALPHABET}]{{6}}$")
ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
METHOD = ("Each participant answers three questions before and after using the app: a target occupation, its "
          "biggest missing skill and a first course, each picked from a list or 'not sure yet'. 'Named' counts "
          "a person who picked all three, as given. 'Consistent' also needs the skill to be one O*NET lists for that "
          "occupation and the course to be a free resource that teaches one of its skills or tools, or its field. Rates are over people who answered both "
          f"times; with fewer than {MIN_PEOPLE} of them the counts are not a rate. No name or typed text is "
          f"collected, and a session is deleted {KEEP_DAYS} days after it was opened.")

_lock = threading.Lock()
_paths: dict[str, tuple[set, set]] = {}


class PilotError(ValueError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _read() -> dict:
    try:
        store = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return store if isinstance(store, dict) else {}


def _write(store: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def _expire(store: dict) -> None:
    oldest = (_today() - timedelta(days=KEEP_DAYS)).isoformat()
    for code in [c for c, s in store.items() if s["created"] < oldest]:
        del store[code]


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _code(value) -> str:
    code = value.strip().upper() if isinstance(value, str) else ""
    if not CODE_RE.match(code):
        raise PilotError("'code' must be the 6-character session code")
    return code


def options() -> dict:
    """What a participant picks from: the skills and knowledge areas and every free resource.
    (Occupations come from /api/occupations.) The lists are the same for everyone, so they never
    hint at the answer for one occupation."""
    data = matching.load_data()
    elements = [{"id": e["element_id"], "name": e["name"], "kind": e["kind"]} for e in data["elements"].values()]
    resources = [{"id": r["resource_id"], "title": r["title"], "provider": r["provider"]}
                 for r in data["resources"] if matching.is_free(r) and r["format"] in ("course", "video")]
    return {"elements": sorted(elements, key=lambda e: (e["kind"], e["name"])),
            "resources": sorted(resources, key=lambda r: r["title"]),
            "target_pct": TARGET_PCT, "min_people": MIN_PEOPLE, "keep_days": KEEP_DAYS, "method": METHOD}


def path_of(occ_id: str) -> tuple[set, set]:
    """The skills and knowledge areas O*NET lists for an occupation, and the free resources that
    teach one of them, one of its tools, its field or every job (what its learning path draws on)."""
    if occ_id not in _paths:
        data = matching.load_data()
        occ = data["by_id"].get(occ_id)
        if occ is None:
            raise PilotError(f"unknown occ_id '{occ_id}'")
        skills = {e[0] for e in data["occ_elements"].get(occ_id, [])}
        targets = [f"element:{s}" for s in skills] + [f"tech:{t}" for t in data["occ_techs"].get(occ_id, [])]
        targets += [f"field:{occ['field_id']}", "all"]
        _paths[occ_id] = (skills, {r["resource_id"] for t in targets for r in data["by_target"].get(t, []) if matching.is_free(r)})
    return _paths[occ_id]


def open_session() -> dict:
    """A new session: its code for the room and the key that opens its results (shown once)."""
    with _lock:
        store = _read()
        _expire(store)
        if len(store) >= MAX_SESSIONS:
            raise PilotError("too many open sessions on this server; an old one must expire first")
        code = next(c for c in iter(lambda: "".join(secrets.choice(ALPHABET) for _ in range(6)), None)
                    if c not in store)
        key = secrets.token_urlsafe(18)
        store[code] = {"key": _hash(key), "created": _today().isoformat(), "answers": {}}
        _write(store)
    return {"code": code, "key": key, "created": store[code]["created"], "keep_days": KEEP_DAYS}


def exists(code) -> dict:
    code = _code(code)
    with _lock:
        store = _read()
        _expire(store)
    if code not in store:
        raise PilotError("no open session has this code")
    return {"code": code, "created": store[code]["created"]}


def _pick(value, known, name: str) -> str | None:
    """One answer: an id from the list, or None for 'not sure yet'."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or value not in known:
        raise PilotError(f"'{name}' must be an id from its list, or empty for 'not sure yet'")
    return value


def _reading(answer: dict) -> dict:
    """What one response says: which questions it names and, when all three, whether they agree."""
    named = {"occupation": bool(answer["occ_id"]), "gap": bool(answer["gap_id"]), "course": bool(answer["resource_id"])}
    out = {"named": named, "clear": all(named.values()), "gap_on_path": None, "course_on_path": None}
    if answer["occ_id"]:
        skills, resources = path_of(answer["occ_id"])
        if answer["gap_id"]:
            out["gap_on_path"] = answer["gap_id"] in skills
        if answer["resource_id"]:
            out["course_on_path"] = answer["resource_id"] in resources
    out["consistent"] = bool(out["clear"] and out["gap_on_path"] and out["course_on_path"])
    return out


def answer(code, learner, phase, occ_id=None, gap_id=None, resource_id=None) -> dict:
    """Keep one participant's answers for one phase; the latest replaces the one before."""
    code = _code(code)
    if not isinstance(learner, str) or not ID_RE.match(learner):
        raise PilotError("'learner' must be the browser's random id")
    if phase not in PHASES:
        raise PilotError("'phase' must be 'before' or 'after'")
    data = matching.load_data()
    row = {"occ_id": _pick(occ_id, data["by_id"], "occ_id"),
           "gap_id": _pick(gap_id, data["elements"], "gap_id"),
           "resource_id": _pick(resource_id, {r["resource_id"] for r in data["resources"] if matching.is_free(r)},
                                "resource_id"),
           "date": _today().isoformat()}
    with _lock:
        store = _read()
        _expire(store)
        if code not in store:
            raise PilotError("no open session has this code")
        answers = store[code]["answers"]
        people = {k.split("|", 1)[0] for k in answers}
        if learner not in people and len(people) >= MAX_PEOPLE:
            raise PilotError("this session is full")
        answers[f"{learner}|{phase}"] = row
        _write(store)
    return {"saved": True, "code": code, "phase": phase, "reading": _reading(row)}


def _share(count: int, of: int) -> float | None:
    return round(100 * count / of, 1) if of else None


def summary(code, key) -> dict:
    """A session's results, for the holder of its key: counts per phase and question, the two
    readings over the people who answered both times, and every response for export."""
    code = _code(code)
    with _lock:
        store = _read()
        _expire(store)
    session = store.get(code)
    if session is None or not isinstance(key, str) or not hmac.compare_digest(session["key"], _hash(key)):
        raise PilotError("no open session has this code and key")
    data = matching.load_data()
    people: dict[str, dict] = {}
    for k, row in session["answers"].items():
        learner, phase = k.split("|", 1)
        people.setdefault(learner, {})[phase] = {**row, **_reading(row)}
    paired = [p for p in people.values() if len(p) == 2]
    n = len(paired)

    def count(phase: str, test) -> int:
        return sum(1 for p in paired if test(p[phase]))

    questions = [{"question": q, **{ph: count(ph, lambda r, q=q: r["named"][q]) for ph in PHASES}} for q in QUESTIONS]
    clear = {ph: count(ph, lambda r: r["clear"]) for ph in PHASES}
    consistent = count("after", lambda r: r["consistent"])
    rows = []
    for i, learner in enumerate(sorted(people, key=lambda l: min(r["date"] for r in people[l].values())), 1):
        for ph in PHASES:
            r = people[learner].get(ph)
            if r:
                occ, gap = data["by_id"].get(r["occ_id"]), data["elements"].get(r["gap_id"])
                rows.append({"participant": i, "phase": ph, "date": r["date"],
                             "occ_id": r["occ_id"] or "", "occupation": occ["title"] if occ else "",
                             "gap_id": r["gap_id"] or "", "gap": gap["name"] if gap else "",
                             "resource_id": r["resource_id"] or "", "named_all_three": r["clear"],
                             "consistent_with_data": r["consistent"]})
    return {
        "code": code, "created": session["created"],
        "expires": (date.fromisoformat(session["created"]) + timedelta(days=KEEP_DAYS)).isoformat(),
        "people": {"before": sum(1 for p in people.values() if "before" in p),
                   "after": sum(1 for p in people.values() if "after" in p), "both": n},
        "questions": questions,
        "named": {**clear, "before_pct": _share(clear["before"], n), "after_pct": _share(clear["after"], n)},
        "consistent_after": {"count": consistent, "pct": _share(consistent, n)},
        "target_pct": TARGET_PCT, "min_people": MIN_PEOPLE,
        "enough_people": n >= MIN_PEOPLE,
        "target_met": n >= MIN_PEOPLE and 100 * clear["after"] >= TARGET_PCT * n,
        "rows": rows, "method": METHOD,
    }
