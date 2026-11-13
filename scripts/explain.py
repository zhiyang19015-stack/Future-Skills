"""Why this score? A plain-language explanation of one occupation match, optionally by an LLM.

Our data decides; the LLM only words it. The model sees the facts matching.py computed for this
person and occupation, nothing else, and its reply is thrown away when it
    - contains a number that is not in the facts,
    - predicts the future in its own words ("will grow", "akan meningkat", "将会增长"),
    - is not in the language asked for, or is too long.
Then, and whenever no LLM is set up, a text written from the same facts by a template is used.

Any OpenAI-compatible chat completions API works, called with the standard library:
    LLM_API_KEY    the key (FIREWORKS_API_KEY is read when this is not set)
    LLM_BASE_URL   the API's base URL, default DEFAULT_BASE_URL
    LLM_MODEL      the model id, default DEFAULT_MODEL
set as environment variables, in a local .env, or as Codespaces secrets.
"""

import hashlib
import json
from collections import OrderedDict
import os
import re
import urllib.error
import urllib.parse
import urllib.request

FIREWORKS = "https://api.fireworks.ai/inference/v1"
DEFAULT_BASE_URL = FIREWORKS
DEFAULT_MODEL = "accounts/fireworks/models/" + "gpt-oss-120b"
TIMEOUT_S = 25
MAX_TOKENS = 1500
CACHE_SIZE = 256
LANGS = ("en", "ms", "zh")
REPLY_LIMIT = {"en": (1400, 450), "ms": (1700, 550), "zh": (700, 220)}  # (full, short) characters
LANGUAGE_NAME = {"en": "plain English", "ms": "plain Bahasa Melayu (Malaysian Malay)",
                 "zh": "plain Simplified Chinese (简体中文)"}
LANGUAGE_RULE = {
    "en": "",
    "ms": "\n- Write the whole reply in Bahasa Melayu. You may translate occupation and field names; keep course "
          "titles, provider names and tool names as they are in the facts. Never write that something \"akan "
          "meningkat\", \"akan berkembang\", \"dijangka\" or \"terus meningkat\".",
    "zh": "\n- Write the whole reply in Simplified Chinese. You may translate occupation and field names; keep course "
          "titles, provider names and tool names as they are in the facts. Never write \"将会增长\", \"预计\", "
          "\"有望\", \"持续增长\" or \"未来几年\".",
}

RULES = """Rules:
- field_fit, interest_fit, skill_fit and outlook_points are the points each part adds to match_score, as the
  person's card shows them; max_points is the most each part can add. Say them as points ("14.2 of 20 points"),
  never as a score out of 100. null means the part is not scored.
- Use only the facts. Add no salaries, job counts, percentages, course names, employers or anything else that is
  not in the JSON. Every number you write must appear exactly as in the facts; if unsure, leave it out.
- Describe the outlook only with the word in outlook.status and name the scenario ("under the Moderate AI adoption
  scenario the estimate is steady"). It is an estimate under that scenario's assumption, never a fact about the
  future: say so. Make no predictions of your own; never say jobs or demand will grow, are expected to or are likely to.
- If a part is low, say so kindly. No headings, lists or markdown: plain sentences only."""
FULL_TASK = """Write 4 to 5 sentences in {language}, speaking to the person as "you":
1. Why the occupation fits or does not, from the field fit, interest and skill parts.
2. What the outlook means under the named scenario: the Malaysian demand, how much of the occupation's tasks
   people already hand to AI compared with the average occupation, and whether the estimate is rising, steady
   or declining.
3. The first concrete step: the first course in the learning path if there is one, else the biggest skill gap.
4. What the occupation's SDG target means in everyday terms."""
SHORT_TASK = """Write 2 short sentences (under 50 words in all) in {language}, speaking to the person as "you":
why this occupation suits them, from the field fit, interest fit, skill fit and the outlook under the named
scenario, strongest part first. Do not mention skill gaps, courses or learning steps."""
INTRO = """You explain career matches to students and working people in Malaysia, across every kind of work.
You get the facts for one person and one occupation as JSON inside <facts> tags, computed by a scoring program
from public data (O*NET, DOSM, MyCOL, the Anthropic Economic Index, the UN SDG targets).

"""

NUMBER = re.compile(r"\d+(?:\.\d+)?")
PREDICTIONS = {
    "en": re.compile(
        r"\b(?:will|won't|is going to|are going to|likely to|unlikely to|expected to|set to|bound to|poised to)\s+"
        r"(?:\w+\s+){0,2}?(?:grow|rise|increase|expand|boom|stay|remain|keep|continue|decline|fall|shrink|drop|be in)\b"
        r"|\b(?:will|likely to|expected to|set to)\s+(?:\w+\s+){0,2}?become\s+(?:even\s+)?(?:more|less|increasingly)\s+"
        r"(?:important|valuable|needed|in demand|sought|common|scarce|relevant)"
        r"|\bas AI(?: tools)? (?:evolves?|advances?|improves?|spreads?|grows?)\b"
        r"|\bkeep(?:s)? (?:growing|rising|increasing)\b|\bin the (?:coming|next) (?:years|decade)\b|\bfuture[- ]proof",
        re.IGNORECASE),
    "ms": re.compile(
        r"\bakan\s+(?:\w+\s+){0,2}?(?:berkembang|meningkat|bertambah|tumbuh|menurun|berkurang|merosot|kekal"
        r"|menjadi\s+(?:lebih|semakin|kurang))\b|\bdijangka\b|\bdiramalkan\b"
        r"|\bterus\s+(?:berkembang|meningkat|bertambah|tumbuh)\b|\b(?:tahun|dekad)(?:-tahun)?\s+(?:akan\s+datang|mendatang)\b"
        r"|\bkalis\s+masa\s+depan\b", re.IGNORECASE),
    "zh": re.compile(r"将(?:会)?(?:持续|继续|不断|进一步)?(?:增长|上升|增加|扩大|下降|减少|萎缩|保持|变得)"
                     r"|预计|预期|有望|势必|必将|未来(?:几|数|十)年|今后(?:几|数)年|(?:持续|不断|继续)(?:增长|上升|扩大)"),
}
CJK = re.compile(r"[一-鿿]")
MALAY = re.compile(r"\b(?:yang|dan|anda|untuk|ini|dengan|ialah|adalah|daripada|kepada)\b", re.IGNORECASE)
ENGLISH = re.compile(r"\b(?:the|and|you|your|this|with|for|is|of)\b", re.IGNORECASE)
NEUTRAL_BAND = 12.5
POINT_KEYS = {"field": "field_fit", "interest": "interest_fit", "skill": "skill_fit", "outlook": "outlook_points"}



class ReplyStore:
    """The last few replies the language model wrote, so asking the same thing again costs nothing.
    The one used longest ago goes first when it is full."""

    def __init__(self, size: int):
        self.size = size
        self.items: OrderedDict[str, dict] = OrderedDict()

    def get(self, key: str) -> dict | None:
        if key not in self.items:
            return None
        self.items.move_to_end(key)
        return {**self.items[key], "cached": True}

    def put(self, key: str, reply: dict) -> None:
        self.items[key] = reply
        self.items.move_to_end(key)
        while len(self.items) > self.size:
            self.items.popitem(last=False)

    def clear(self) -> None:
        self.items.clear()


_replies = ReplyStore(CACHE_SIZE)


def prompt_for(short: bool, lang: str = "en") -> str:
    task = (SHORT_TASK if short else FULL_TASK).format(language=LANGUAGE_NAME[lang])
    return INTRO + task + "\n\n" + RULES + LANGUAGE_RULE[lang]


def env(name: str) -> str:
    """The value of an environment variable; a secret saved as " llm_api_key " still counts."""
    wanted = name.upper()
    for key in sorted(os.environ, key=lambda k: k != name):  # the exact name first
        if key.strip().upper() == wanted and os.environ[key].strip():
            return os.environ[key].strip()
    return ""


def api_key() -> str:
    return env("LLM_API_KEY") or env("FIREWORKS_API_KEY")


def configured() -> bool:
    return bool(api_key())


def base_url() -> str:
    return (env("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def model_name() -> str:
    return env("LLM_MODEL") or env("FIREWORKS_MODEL") or DEFAULT_MODEL


def provider() -> str:
    """A readable name for the API host, for the Sources page."""
    if base_url() == FIREWORKS:
        return "Fireworks AI"
    return urllib.parse.urlsplit(base_url()).netloc or base_url()


def llm_variables_set() -> list[str]:
    """The names, never the values, of the LLM settings in the environment, for the start-up log.
    Each name is quoted so that a stray space in a secret's name can be seen."""
    names = [name for name in os.environ if name.strip().upper().startswith("LLM_") or "FIREWORKS" in name.upper()]
    return [f"'{name}'" for name in sorted(names)]


REASONING = re.compile(r"^(?:.*/)?(?:o\d|gpt-(?:[5-9]|\d{2}))", re.IGNORECASE)


def chat_body(messages: list[dict]) -> dict:
    model = model_name()
    if REASONING.match(model):  # OpenAI reasoning models take other parameters
        return {"model": model, "max_completion_tokens": MAX_TOKENS, "reasoning_effort": "low", "messages": messages}
    return {"model": model, "max_tokens": MAX_TOKENS, "temperature": 0.3, "messages": messages}


def direction(score: float | None) -> str:
    if score is None:
        return "no data"
    return "positive" if score >= 50 + NEUTRAL_BAND else "negative" if score <= 50 - NEUTRAL_BAND else "neutral"


def max_points(components: dict) -> dict:
    """The most points each scored part can add (its weight, scaled up for skipped parts)."""
    used = sum(c["weight"] for c in components.values() if c["score"] is not None)
    return {POINT_KEYS[k]: None if c["score"] is None or not used else round(100 * c["weight"] / used, 1)
            for k, c in components.items()}


def build_facts(m: dict, scenario: dict | None = None) -> dict:
    """The only information the LLM may use: one match, trimmed to what matters."""
    c, d, p, o = m["components"], m["skill_detail"], m["pathway"], m["outlook"]
    return {
        "occupation": m["title"], "field": m["field_name"], "match_score": m["total"],
        **{POINT_KEYS[k]: c[k]["points"] for k in POINT_KEYS}, "max_points": max_points(c),
        "scenario": (scenario or {}).get("name") or f"adoption {o['adoption']:g}",
        "outlook": {"status": o["status"], "malaysian_demand": direction(o["demand"] if o["has_demand"] else None),
                    "ai_share_of_tasks": o["ai_share"], "average_ai_share": o["ai_share_reference"],
                    "points_moved_by_scenario": o["change"]},
        "top3_share_of_futures": (m.get("stability") or {}).get("top3"),
        "field_note": m["explain"]["field"], "interest_note": m["explain"]["interest"],
        "biggest_gaps": [{"skill": g["skill_name"], "your_level": g["your_level"], "level_needed": g["level_needed"],
                          "heading": g["ai"]["status"]} for g in d["gaps"][:3]],
        "technologies_to_learn": [{"tool": t["skill_name"], "heading": t["ai"]["status"]} for t in d["tech_missing"][:4]],
        "learning_path": [{"course": s["title"], "provider": s["provider"], "hours": s["hours"], "covers": s["skills"]}
                          for s in p["steps"][:3]],
        "learning_path_total_hours": p["total_hours"], "learning_path_weeks": p["weeks"],
        "hours_per_week": p["hours_per_week"], "flags": m["flags"],
        "licence": (m.get("licence") or {}).get("body"),
        "sdg": [{"target": s["target"], "goal": s["goal_name"], "why": s["rationale"]} for s in m["sdg"][:2]],
        "sdg_goals_picked": (m.get("sdg_choice") or {}).get("goals", []),
        "sdg_bonus": (m.get("sdg_choice") or {}).get("bonus", 0.0),
    }


def short_facts(facts: dict) -> dict:
    return {k: v for k, v in facts.items() if k not in ("biggest_gaps", "technologies_to_learn", "learning_path",
                                                       "learning_path_total_hours", "learning_path_weeks",
                                                       "hours_per_week")}


def raise_tips(before: dict, after: dict | None, learn: list[str]) -> dict:
    """What would raise the score: the same match with the next tools learned, and interest when unscored."""
    tips = {"learn": learn, "new_score": None, "gain": None, "interest_points": None}
    if after is not None and learn:
        tips.update(new_score=after["total"], gain=round(after["total"] - before["total"], 1))
    if before["components"]["interest"]["score"] is None:
        tips["interest_points"] = round(100 * before["components"]["interest"]["weight"], 1)
    return tips


def normalise(n: str) -> str:
    return str(float(n)).rstrip("0").rstrip(".") if "." in n else str(int(n))


def unknown_numbers(text: str, facts: dict) -> list[str]:
    """Numbers in a reply that are not in the facts (0-10, 100 and 2030 are always allowed)."""
    allowed = {normalise(n) for n in NUMBER.findall(json.dumps(facts))} | {str(i) for i in range(11)} | {"100", "2030"}
    return [n for n in NUMBER.findall(text) if normalise(n) not in allowed]


def predictions(text: str, lang: str = "en") -> list[str]:
    patterns = [PREDICTIONS["en"]] + ([PREDICTIONS[lang]] if lang != "en" else [])
    return [m.group(0) for p in patterns for m in p.finditer(text)]


def in_language(text: str, lang: str) -> bool:
    if lang == "zh":
        return len(CJK.findall(text)) >= max(10, len(text) // 4)
    if lang == "ms":
        ms = len(MALAY.findall(text))
        return ms >= 3 and ms > len(ENGLISH.findall(text))
    return True


def points(facts: dict, key: str) -> str:
    return "not scored" if facts[key] is None else f"{facts[key]:g} of {facts['max_points'][key]:g} points"


def outlook_words(facts: dict) -> str:
    o = facts["outlook"]
    return (f"under the {facts['scenario']} scenario its outlook is {o['status']} (Malaysian demand "
            f"{o['malaysian_demand']}; people already hand {o['ai_share_of_tasks']:g}% of its tasks to AI, against "
            f"{o['average_ai_share']:g}% for the average occupation; an estimate under that scenario, not a prediction)")


def first_step(facts: dict) -> str | None:
    """The sentence about where to start: the first free course, else the biggest gap."""
    for course in facts["learning_path"][:1]:
        length = f" ({course['hours']:g} hours)" if course["hours"] else ""
        return (f"A good first step is the free course \"{course['course']}\" from {course['provider']}{length}, "
                f"which covers {', '.join(course['covers'])}.")
    for gap in facts["biggest_gaps"][:1]:
        return (f"Your biggest gap is {gap['skill']} (you {gap['your_level']:g}, needed {gap['level_needed']:g} "
                "on O*NET's 0-7 scale).")
    return None


def fallback_text(facts: dict) -> str:
    """The explanation written from the facts by a template, used whenever a model is not."""
    sentences = [f"{facts['occupation']} scores {facts['match_score']} out of 100 for you: "
                 f"field fit {points(facts, 'field_fit')}, skill fit {points(facts, 'skill_fit')} and outlook "
                 f"{points(facts, 'outlook_points')}; {outlook_words(facts)}.", first_step(facts)]
    if facts.get("licence"):
        sentences.append(f"To practise in Malaysia you register with the {facts['licence']}.")
    sentences += [f"It serves SDG target {target['target']}: {target['why']}" for target in facts["sdg"][:1]]
    if facts.get("sdg_goals_picked"):
        sentences.append(f"It serves SDG {', '.join(facts['sdg_goals_picked'])}, which you picked, so it gets "
                         f"{facts['sdg_bonus']:g} extra points.")
    return " ".join(x for x in sentences if x)


def one_line_fallback(facts: dict) -> str:
    """One sentence on why the occupation suits the person: the part closest to its maximum leads."""
    labels = (("field_fit", "field fit"), ("interest_fit", "interest fit"), ("skill_fit", "skill fit"))
    shares = [(facts[key] / facts["max_points"][key], key, label) for key, label in labels
              if facts[key] is not None and facts["max_points"][key]]
    if shares:
        _, key, label = max(shares)
        strongest = f"your strongest part is {label} ({points(facts, key)})"
    else:
        strongest = "none of your parts is scored yet"
    return (f"{facts['occupation']} scores {facts['match_score']} out of 100 for you: {strongest}, and "
            f"{outlook_words(facts)}.")


def call_llm(facts: dict, prompt: str) -> str:
    """One chat completion: the rules as the system message, the facts as the user message."""
    question = f"<facts>\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n</facts>\nExplain this match to me."
    payload = json.dumps(chat_body([{"role": "system", "content": prompt}, {"role": "user", "content": question}]))
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "Authorization": f"Bearer {api_key()}"}
    request = urllib.request.Request(f"{base_url()}/chat/completions", data=payload.encode("utf-8"),
                                     headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        first = json.loads(answer.read())["choices"][0]
    if first.get("finish_reason") == "length":
        raise ValueError("the reply was cut off at the token limit")
    return str(first["message"].get("content") or "").strip()


def problem_with(text: str, facts: dict, lang: str, short: bool) -> str | None:
    """Why a reply cannot be shown, or None when it passes every check."""
    if not text:
        return "the reply was empty"
    foreign = unknown_numbers(text, facts)
    if foreign:
        return "the reply had numbers that are not in the facts: " + ", ".join(foreign[:5])
    guesses = predictions(text, lang)
    if guesses:
        return f"the reply made its own prediction: {guesses[0]!r}"
    if not in_language(text, lang):
        return f"the reply was not written in {LANGUAGE_NAME[lang]}"
    if len(text) > REPLY_LIMIT[lang][1 if short else 0]:
        return "the reply was too long"
    return None


def explain(match: dict, short: bool = False, scenario: dict | None = None, lang: str = "en") -> dict:
    """{"text", "source": "llm" | "fallback", "model", "reason", "lang", "text_lang", "facts"} for one match.
    The template text is English (text_lang "en"); the page writes it in Malay or Chinese from facts."""
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {list(LANGS)}")
    full = build_facts(match, scenario)
    facts = short_facts(full) if short else full
    key = hashlib.sha256(json.dumps([facts, short, lang], sort_keys=True).encode()).hexdigest()
    seen = _replies.get(key)
    if seen:
        return seen
    template = one_line_fallback(facts) if short else fallback_text(facts)
    out = {"text": template, "source": "fallback", "model": None, "reason": None, "lang": lang, "text_lang": "en",
           "facts": facts}
    if not configured():
        return {**out, "reason": "no language model is set up (LLM_API_KEY)"}
    try:
        text = call_llm(facts, prompt_for(short, lang))
    except urllib.error.HTTPError as failure:
        return {**out, "reason": f"the language model's API answered HTTP {failure.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as failure:
        return {**out, "reason": f"the language model's API could not be reached ({type(failure).__name__})"}
    except (KeyError, IndexError, TypeError, ValueError) as failure:
        return {**out, "reason": f"the language model's answer could not be read: {failure}"}
    reason = problem_with(text, facts, lang, short)
    if reason:
        return {**out, "reason": reason}
    out = {**out, "text": text, "source": "llm", "model": model_name(), "provider": provider(), "text_lang": lang}
    _replies.put(key, out)
    return out
