"""Verified real AI news: AI reads, rules decide, a person approves.

    python scripts/news.py            check every item in data/news.json against its page (needs the internet)

The steps, each written to the log as it happens:
 1 Pick      a person adds a real article from a TRUSTED site to data/news.json: its link, publisher,
             title, the date the page shows, and the page's own words to quote.
 2 Check     check() opens the page and looks for every quote word for word, after the same clean-up
             on both sides (tags removed, entities decoded, curly quotes and dashes made plain, spaces
             collapsed). It also reads the date the page itself gives (article:published_time or
             datePublished). A quote that is not there, a date that differs or a page that does not open
             leaves the item "not verified", and it cannot be approved.
 3 Propose   propose() names the O*NET work activities and AI-usage topics the news is about. An LLM
             (explain.py's settings) may pick them, but only from a list we give it: names not on the
             list are dropped and it is never asked for a number. Without an LLM, or when its reply is
             unusable, a keyword rule picks them. Either way the proposal holds names, no numbers.
 4 Size      size() is the fixed rule that turns names into changes:
               each work activity  AI share of every task under it at least (its average now + ACTIVITY_STEP),
                                   never above whatif.NEWS_FLOOR
               each topic          hands-off share + TOPIC_STEP, never above whatif.HANDOFF_MAX
             The steps are assumptions, set once and the same for every item: one real product release
             moves less than the simulated headlines (which raise activities to NEWS_FLOOR outright).
 5 Approve   a person approves or rejects the sized proposal; undo takes an approval back. Only
             approved items change the data the pages use (apply()), for everyone, until undone.

The log is one JSON line per step in .cache/news_log.jsonl (NEWS_LOG overrides the path). The state of
each item is the log read from the top. On a host whose disk is wiped at a restart, approvals go with it.
"""

import hashlib
import html
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import ai_exposure
import explain
import matching
import whatif

ROOT = Path(__file__).resolve().parent.parent
NEWS_FILE = ROOT / "data" / "news.json"
DEFAULT_LOG = ROOT / ".cache" / "news_log.jsonl"
TRUSTED = {  # sites a person may pick news from: the companies that ship the AI tools, in their own words
    "devblogs.microsoft.com": "Microsoft Developer Blogs",
    "news.microsoft.com": "Microsoft News",
    "github.blog": "GitHub Blog",
    "mistral.ai": "Mistral AI",
    "www.anthropic.com": "Anthropic",
    "openai.com": "OpenAI",
    "blog.google": "Google",
    "developers.googleblog.com": "Google for Developers",
}
ACTIVITY_STEP = 20.0     # points of AI share an approved real item adds to each activity it names
TOPIC_STEP = 10.0        # points of hands-off share it adds to each AI-usage topic it names
MAX_ACTIVITIES = 4
MAX_TOPICS = 2
LLM_CANDIDATES = 60      # activities offered to the LLM, the best keyword matches first
TIMEOUT_S = 20
MAX_PAGE = 3_000_000
AGENT = "Mozilla/5.0 (compatible; future-skills-news-check)"
REVIEWER_CHARS = 40
STOP = set("""a an and are as at be been but by can could do does for from had has have how in into is it its
it's itself just like make makes made more most new no not now of on or our out over per so such than that the
their them then there these they this those through to up us use used using was we were what when where which
while who will with without within you your yours across after all also any been before both each even every
get gets give gives here many much one only other others own same should since some still very way ways well
today excited announce available release brings everyone""".split())

_lock = threading.Lock()
_applied = {"key": None, "value": None}


class NewsError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_path() -> Path:
    return Path(os.environ.get("NEWS_LOG") or DEFAULT_LOG)


def items() -> list[dict]:
    """The items in data/news.json, each with its site's name; NewsError when one breaks the rules."""
    raw = json.loads(NEWS_FILE.read_text(encoding="utf-8"))["items"]
    seen = set()
    for n in raw:
        host = urllib.parse.urlsplit(n["url"]).netloc
        if host not in TRUSTED:
            raise NewsError(f"{n['id']}: {host} is not one of the trusted sites")
        if n["id"] in seen or not n["quotes"] or not re.fullmatch(r"\d{4}-\d\d-\d\d", n["published"]):
            raise NewsError(f"{n['id']}: needs a unique id, at least one quote and a published date")
        seen.add(n["id"])
        n["site"] = TRUSTED[host]
    return raw


def item(news_id: str) -> dict:
    found = next((n for n in items() if n["id"] == news_id), None)
    if found is None:
        raise NewsError(f"'{news_id}' is not an item in data/news.json")
    return found


# --- the log --------------------------------------------------------------------------------------

def write(event: dict) -> dict:
    event = {"at": now(), **event}
    path = log_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_log() -> list[dict]:
    try:
        lines = log_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a half-written line from a crash is skipped, not fatal
    return out


def states(log: list[dict] | None = None) -> dict:
    """{news_id: {"check", "proposal", "decision", "approved"}} from the log read top to bottom."""
    out = {}
    for e in read_log() if log is None else log:
        s = out.setdefault(e.get("id"), {"check": None, "proposal": None, "decision": None, "approved": None})
        step = e.get("step")
        if step == "checked":
            s["check"] = e
        elif step == "proposed":
            s["proposal"] = e
        elif step == "approved":
            s["decision"], s["approved"] = e, e
        elif step == "rejected":
            s["decision"], s["approved"] = e, None
        elif step == "undone":
            s["decision"], s["approved"] = e, None
    return out


# --- 2 check --------------------------------------------------------------------------------------

QUOTE_MARKS = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
                             "“": '"', "”": '"', "„": '"', "″": '"',
                             "–": "-", "—": "-", "−": "-", " ": " ", " ": " "})


def clean(text: str) -> str:
    """The same clean-up for the page and the quote: plain quotes and dashes, single spaces."""
    return re.sub(r"\s+", " ", html.unescape(text).translate(QUOTE_MARKS)).strip()


def page_text(body: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", body)
    return clean(re.sub(r"<[^>]+>", " ", body))


def page_date(body: str) -> str | None:
    """The publish date the page itself states, as YYYY-MM-DD, or None."""
    for pattern in (r'property=["\']article:published_time["\'][^>]*content=["\'](\d{4}-\d\d-\d\d)',
                    r'content=["\'](\d{4}-\d\d-\d\d)[^"\']*["\'][^>]*property=["\']article:published_time',
                    r'"datePublished"\s*:\s*"(\d{4}-\d\d-\d\d)'):
        m = re.search(pattern, body)
        if m:
            return m.group(1)
    return None


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return r.read(MAX_PAGE).decode(r.headers.get_content_charset() or "utf-8", "replace")


def verdict(n: dict, body: str) -> dict:
    """What a page says about one item: each quote found or not, and the page's own date."""
    text = page_text(body)
    quotes = [{"quote": q, "found": clean(q) in text} for q in n["quotes"]]
    found_date = page_date(body)
    date_ok = found_date == n["published"]
    verified = all(q["found"] for q in quotes) and date_ok
    problem = None
    if not all(q["found"] for q in quotes):
        problem = "quote_not_found"
    elif found_date is None:
        problem = "no_date"
    elif not date_ok:
        problem = "date_differs"
    return {"status": "verified" if verified else "not_verified", "problem": problem, "quotes": quotes,
            "page_date": found_date, "page_chars": len(text)}


def check(news_id: str, opener=fetch) -> dict:
    """Open the item's page now and log what it shows."""
    n = item(news_id)
    try:
        result = verdict(n, opener(n["url"]))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as failure:
        result = {"status": "not_verified", "problem": "unreachable", "detail": type(failure).__name__,
                  "quotes": [{"quote": q, "found": None} for q in n["quotes"]], "page_date": None}
    return write({"step": "checked", "id": news_id, "url": n["url"], **result})


# --- 3 propose ------------------------------------------------------------------------------------

def stem(word: str) -> str:
    for end in ("ing", "ed", "es", "s"):
        if word.endswith(end) and len(word) - len(end) >= 3:
            word = word[: -len(end)]
            if end in ("ing", "ed") and len(word) >= 4 and word[-1] == word[-2] and word[-1] not in "aeiouls":
                word = word[:-1]  # running -> run, as in Porter's stemmer
            break
    return word[:6]


def words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOP}


def candidates(n: dict, layer: dict) -> tuple[list[dict], list[dict]]:
    """The work activities with a task in the item's field, and the AI-usage topics with a measured
    hands-off share, each with how many words it shares with the item's title and quotes."""
    occs = matching.static_tables()["by_id"]
    said = words(n["title"] + " " + " ".join(n["quotes"]))
    acts = {}
    for t in layer["tasks"]:
        if occs.get(t["occ_id"], {}).get("field_id") != n["field"]:
            continue
        for a in t["work_activities"]:
            acts[a] = acts.get(a, 0) + 1
    activity_rows = [{"name": a, "tasks_in_field": c, "shared": sorted(words(a) & said)} for a, c in acts.items()]
    activity_rows.sort(key=lambda r: (-len(r["shared"]), -r["tasks_in_field"], r["name"]))
    topic_rows = [{"name": t["topic"], "shared": sorted(words(t["topic"]) & said)}
                  for t in layer["topics"].values() if t["handoff_measured"] is not None]
    topic_rows.sort(key=lambda r: (-len(r["shared"]), r["name"]))
    return activity_rows, topic_rows


def keyword_pick(activity_rows: list[dict], topic_rows: list[dict]) -> tuple[list[str], list[str]]:
    """The keyword rule: the activities and topics sharing the most words with the item, at least one."""
    return ([r["name"] for r in activity_rows if r["shared"]][:MAX_ACTIVITIES],
            [r["name"] for r in topic_rows if r["shared"]][:MAX_TOPICS])


PROPOSE_PROMPT = """You read one piece of AI news and say which work it is about.
Pick up to {acts} work activities and up to {topics} AI-usage topics from the lists in the user message:
only ones the quoted text directly describes AI doing. Copy names exactly. Give no numbers, no reasons.
Reply with JSON only: {{"activities": [...], "topics": [...]}}"""


def llm_pick(n: dict, activity_rows: list[dict], topic_rows: list[dict], caller=None) -> tuple[list[str], list[str]]:
    """The LLM's pick, kept only where every name is on the lists. NewsError when nothing usable comes back."""
    acts = [r["name"] for r in activity_rows[:LLM_CANDIDATES]]
    topics = [r["name"] for r in topic_rows]
    question = json.dumps({"title": n["title"], "publisher": n["publisher"], "quotes": n["quotes"],
                           "work_activities": acts, "topics": topics}, ensure_ascii=False)
    system = PROPOSE_PROMPT.format(acts=MAX_ACTIVITIES, topics=MAX_TOPICS)
    reply = (caller or call_llm)(system, question)
    match = re.search(r"\{.*\}", reply, re.S)
    try:
        parsed = json.loads(match.group(0)) if match else None
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        raise NewsError("the LLM reply was not JSON")
    picked_a = [a for a in dict.fromkeys(parsed.get("activities") or []) if a in acts][:MAX_ACTIVITIES]
    picked_t = [t for t in dict.fromkeys(parsed.get("topics") or []) if t in topics][:MAX_TOPICS]
    if not picked_a and not picked_t:
        raise NewsError("the LLM named nothing on the lists")
    return picked_a, picked_t


def call_llm(system: str, question: str) -> str:
    payload = json.dumps(explain.chat_body([{"role": "system", "content": system},
                                            {"role": "user", "content": question}]))
    req = urllib.request.Request(f"{explain.base_url()}/chat/completions", data=payload.encode("utf-8"), method="POST",
                                 headers={"Accept": "application/json", "Content-Type": "application/json",
                                          "Authorization": f"Bearer {explain.api_key()}"})
    with urllib.request.urlopen(req, timeout=explain.TIMEOUT_S) as answer:
        return str(json.loads(answer.read())["choices"][0]["message"].get("content") or "")


def size(activities: list[str], topics: list[str], layer: dict) -> dict:
    """The fixed rule: names in, changes (the what-if format) and their before and after out."""
    groups = whatif.activity_counts(layer)
    hand = {t["topic"]: t["handoff_measured"] for t in layer["topics"].values() if t["handoff_measured"] is not None}
    changes, rows = {"ai_share": {}, "handoff": {}}, []
    for a in activities:
        tasks = groups.get(a)
        if not tasks:
            continue
        avg = round(sum(x["ai_share"] for x in tasks) / len(tasks), 1)
        floor = min(whatif.NEWS_FLOOR, round(avg + ACTIVITY_STEP, 1))
        raised = sum(1 for x in tasks if x["ai_share"] < floor)
        if floor > avg and raised:
            changes["ai_share"][a] = floor
            rows.append({"kind": "ai_share", "name": a, "before": avg, "after": floor, "tasks": len(tasks),
                         "tasks_raised": raised, "rule": f"average {avg:g} + {ACTIVITY_STEP:g}, at most {whatif.NEWS_FLOOR:g}"})
    for t in topics:
        if t not in hand:
            continue
        after = min(whatif.HANDOFF_MAX, round(hand[t] + TOPIC_STEP, 1))
        if after > hand[t]:
            changes["handoff"][t] = after
            rows.append({"kind": "handoff", "name": t, "before": hand[t], "after": after,
                         "rule": f"{hand[t]:g} + {TOPIC_STEP:g}, at most {whatif.HANDOFF_MAX:g}"})
    return {"changes": changes, "rows": rows}


def proposal_id(news_id: str, changes: dict) -> str:
    return hashlib.sha256(json.dumps([news_id, changes], sort_keys=True).encode()).hexdigest()[:12]


def propose(news_id: str, caller=None) -> dict:
    """Ask for a proposal (LLM, else the keyword rule), size it by the rule and log it."""
    n = item(news_id)
    layer = ai_exposure.current()
    activity_rows, topic_rows = candidates(n, layer)
    method, model, fallback_reason = "keyword", None, None
    if explain.configured() or caller:
        try:
            acts, topics = llm_pick(n, activity_rows, topic_rows, caller)
            method, model = "llm", explain.model_name() if not caller else "test"
        except (NewsError, urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as failure:
            fallback_reason = f"LLM failed: {type(failure).__name__}"
            acts, topics = keyword_pick(activity_rows, topic_rows)
    else:
        fallback_reason = "no LLM configured"
        acts, topics = keyword_pick(activity_rows, topic_rows)
    sized = size(acts, topics, layer)
    shared = {r["name"]: r["shared"] for r in activity_rows + topic_rows}
    return write({"step": "proposed", "id": news_id, "method": method, "model": model, "fallback_reason": fallback_reason,
                  "activities": acts, "topics": topics, "shared_words": {k: shared.get(k, []) for k in acts + topics},
                  "rows": sized["rows"], "changes": sized["changes"],
                  "proposal_id": proposal_id(news_id, sized["changes"]),
                  "data_period": layer["context"]["latest"]})


# --- 5 decide -------------------------------------------------------------------------------------

def reviewer_name(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()[:REVIEWER_CHARS]
    return text or "not given"


def decide(news_id: str, action: str, proposal: str | None = None, reviewer=None) -> dict:
    """approve | reject | undo, with the rules: only a verified item with a current proposal is approved,
    and only an approved item can be undone."""
    item(news_id)
    s = states().get(news_id) or {"check": None, "proposal": None, "approved": None}
    who = reviewer_name(reviewer)
    if action == "undo":
        if not s["approved"]:
            raise NewsError("only an approved item can be undone")
        return write({"step": "undone", "id": news_id, "reviewer": who, "proposal_id": s["approved"]["proposal_id"]})
    if action not in ("approve", "reject"):
        raise NewsError("'action' must be approve, reject or undo")
    if not s["proposal"]:
        raise NewsError("there is no proposal to decide on yet")
    if proposal != s["proposal"]["proposal_id"]:
        raise NewsError("the proposal changed since you saw it; look again before deciding")
    if action == "reject":
        return write({"step": "rejected", "id": news_id, "reviewer": who, "proposal_id": proposal})
    if s["approved"]:
        raise NewsError("this item is already approved")
    if not s["check"] or s["check"]["status"] != "verified":
        raise NewsError("not verified: check the source first; an item whose quotes or date are not on its page cannot be approved")
    if not (s["proposal"]["changes"]["ai_share"] or s["proposal"]["changes"]["handoff"]):
        raise NewsError("the proposal changes nothing")
    return write({"step": "approved", "id": news_id, "reviewer": who, "proposal_id": proposal,
                  "check_at": s["check"]["at"], "changes": s["proposal"]["changes"], "rows": s["proposal"]["rows"]})


# --- applying approved items ----------------------------------------------------------------------

def approved_changes(st: dict | None = None) -> tuple[list[str], dict]:
    """The ids of the approved items and their changes together: for each activity or topic the
    highest value any of them sets."""
    st = states() if st is None else st
    ids, out = [], {"ai_share": {}, "handoff": {}}
    for news_id, s in sorted(st.items(), key=lambda kv: str(kv[0])):
        if not s["approved"]:
            continue
        ids.append(news_id)
        for kind in out:
            for k, v in (s["approved"]["changes"].get(kind) or {}).items():
                out[kind][k] = max(v, out[kind].get(k, v))
    return ids, out


def apply(data: dict) -> dict:
    """The data every page uses: as measured, plus the approved items. Rebuilt only when the log changes."""
    ids, changes = approved_changes()
    if not ids:
        return data
    key = (id(data["ai"]), id(data["demand"]), json.dumps(changes, sort_keys=True))
    with _lock:
        if _applied["key"] == key:
            return _applied["value"]
    value = {**whatif.changed_data(data, {"handoff": changes["handoff"], "ai_share": changes["ai_share"]}),
             "news": {"approved": ids, "changes": changes}}
    with _lock:
        _applied.update(key=key, value=value)
    return value


def view() -> dict:
    """Every item with its latest check, proposal and decision, and the log, newest first."""
    st = states()
    log = read_log()
    out = []
    for n in items():
        s = st.get(n["id"]) or {"check": None, "proposal": None, "decision": None, "approved": None}
        out.append({**n, "check": s["check"], "proposal": s["proposal"], "decision": s["decision"],
                    "approved": bool(s["approved"]),
                    "state": "approved" if s["approved"] else (s["decision"] or {}).get("step") or "pending"})
    return {"items": out, "log": log[-40:][::-1], "log_lines": len(log),
            "rule": {"activity_step": ACTIVITY_STEP, "topic_step": TOPIC_STEP, "activity_max": whatif.NEWS_FLOOR,
                     "topic_max": whatif.HANDOFF_MAX, "max_activities": MAX_ACTIVITIES, "max_topics": MAX_TOPICS},
            "trusted": sorted(set(TRUSTED.values())), "llm": {"configured": explain.configured(),
                                                              "model": explain.model_name() if explain.configured() else None}}


def main() -> int:
    """Check every item now (writes to the log) and print the result."""
    bad = 0
    for n in items():
        r = check(n["id"])
        found = sum(1 for q in r["quotes"] if q["found"])
        print(f"{r['status']:13} {n['id']}: {found}/{len(r['quotes'])} quotes found, page date {r['page_date']} "
              f"(listed {n['published']}){' - ' + r['problem'] if r['problem'] else ''}")
        bad += r["status"] != "verified"
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
