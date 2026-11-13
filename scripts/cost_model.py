"""What it costs to run the app for a month, worked out again each time it is run.

Three kinds of number, kept apart:
    measured   by this script on the machine it runs on: the server's memory, and the processor
               time and download size of one full journey through the six steps and the team view
    published  prices read from the providers' own pages (data/cost_inputs.csv, with link and date)
    assumed    ours, in the same file and marked as assumptions: how much slower a rented core is,
               how many people are online at the busiest moment, how often the AI text is opened

Hosting: the server answers one request at a time per process, so the busiest moment sets the cost.
    core seconds per journey = measured seconds x cpu_slowdown
    people one server carries at once = journey_minutes x 60 x busy_share / core seconds per journey
    people at the busiest moment = the larger of class_size and peak_share x users in the month
    servers = people at the busiest moment / people one server carries, rounded up
The AI text is optional (the app writes the same facts from a template without it):
    tokens in = (the instructions + one match's facts) / chars_per_token; tokens out = the reply limit
Nothing here prices people's time; upkeep hours are listed, not costed.

    python scripts/cost_model.py            # print the table
    python scripts/cost_model.py --write    # also save it as docs/cost_model.md
"""

import argparse
import csv
import gzip
import json
import math
import platform
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import explain  # noqa: E402
import main as server  # noqa: E402
import matching  # noqa: E402
import whatif  # noqa: E402

USERS = (200, 5000, 50000)      # people using it in a month: a pilot, one university, many institutions
PERSON = {"profile_id": "P02"}  # the journey is timed for a demo person
OCCUPATION = "13-2082.00"
STATIC = ("style.css", "i18n.js", "quiz-i18n.js", "app.js", "you.js", "explore.js", "futures.js", "team.js")


def inputs() -> dict:
    with (ROOT / "data" / "cost_inputs.csv").open(encoding="utf-8-sig", newline="") as f:
        return {r["input_id"]: {**r, "value": float(r["value"])} for r in csv.DictReader(f)}


def peak_memory_mb() -> float | None:
    """The most memory this process has held, or None where the system cannot say."""
    try:
        import resource
        scale = 1024 * 1024 if sys.platform == "darwin" else 1024
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale
    except ImportError:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("peak", "now", "a", "b", "c", "d", "e", "f")]
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return counters.peak / 1048576
    except (ImportError, AttributeError, OSError):
        pass
    return None


def journey() -> list[tuple[str, str, dict | None]]:
    """Every request of one visit: the page, then each step once, a piece of news and the team view."""
    news = next(n for n in whatif.news() if n["lead"])
    return ([("GET", "/", None)] + [("GET", f"/static/{name}", None) for name in STATIC] + [
        ("GET", "/api/fields", None), ("GET", "/api/profiles", None), ("GET", "/api/radar?scenario=moderate", None),
        ("GET", "/api/whatif", None), ("GET", "/api/occupations", None), ("GET", "/api/technologies", None),
        ("POST", "/api/match", {**PERSON, "top": 12}), ("POST", "/api/explain", {**PERSON, "occ_id": OCCUPATION}),
        ("GET", f"/api/occupations/{OCCUPATION}?scenario=moderate", None),
        ("POST", "/api/learn", {**PERSON, "occ_id": OCCUPATION}), ("GET", "/api/sdg/summary", None),
        ("POST", "/api/futures", {**PERSON, "top": 5}),
        ("POST", "/api/whatif", {**PERSON, "trend_changes": news["changes"]}),
        ("GET", "/api/team?scenario=moderate", None), ("GET", "/api/sources", None)])


def measure(repeats: int = 3) -> dict:
    """Processor seconds and bytes sent for one journey (the fastest of a few runs), and peak memory."""
    matching.load_data()
    steps = journey()
    best, sent = None, 0
    for _ in range(repeats):
        used, sent = 0.0, 0
        for method, path, body in steps:
            start = time.process_time()
            res = server.dispatch(method, path, json.dumps(body).encode("utf-8") if body is not None else b"")
            used += time.process_time() - start
            if res.status != 200:
                raise RuntimeError(f"{method} {path} answered {res.status}")
            sent += len(gzip.compress(res.body, compresslevel=6)) if len(res.body) > 1024 else len(res.body)
        best = used if best is None else min(best, used)
    return {"requests": len(steps), "cpu_seconds": round(best, 2), "transfer_kb": round(sent / 1024),
            "memory_mb": None if peak_memory_mb() is None else round(peak_memory_mb()),
            "machine": platform.processor() or platform.machine(), "python": platform.python_version()}


def llm_tokens(chars_per_token: float) -> dict:
    """Tokens of one "Why this score?" request: the instructions and one match's facts in, the reply limit out."""
    data = matching.load_data()
    profile = matching.prepare(server.build_profile(dict(PERSON), data), data)
    match = matching.detailed(profile, data, OCCUPATION, 0.25, matching.field_fit(profile, data))
    sent = len(explain.prompt_for(False)) + len(json.dumps(explain.build_facts(match), ensure_ascii=False))
    return {"in": math.ceil(sent / chars_per_token), "out": math.ceil(explain.REPLY_LIMIT["en"][0] / chars_per_token),
            "out_cap": explain.MAX_TOKENS}


def monthly(users: int, measured: dict, tokens: dict, x: dict) -> dict:
    """The month's cost for a number of users, from measured values, published prices and assumptions."""
    v = {k: r["value"] for k, r in x.items()}
    core_seconds = measured["cpu_seconds"] * v["cpu_slowdown"]
    carries = v["journey_minutes"] * 60 * v["busy_share"] / core_seconds
    peak = max(v["class_size"], v["peak_share"] * users)
    servers = max(1, math.ceil(peak / carries))
    hosting = servers * v["server_price_usd"] * v["usd_myr"]
    sessions = users * v["sessions_per_user"]
    texts = sessions * v["explanations_per_session"]
    llm = texts * (tokens["in"] * v["llm_input_usd"] + tokens["out"] * v["llm_output_usd"]) / 1e6 * v["usd_myr"]
    return {"users": users, "peak_people": round(peak), "server_carries": round(carries, 1), "servers": servers,
            "hosting_myr": round(hosting, 2), "llm_myr": round(llm, 2), "total_myr": round(hosting + llm, 2),
            "per_user_myr": round((hosting + llm) / users, 4), "transfer_gb": round(sessions * measured["transfer_kb"] / 1048576, 2),
            "transfer_included_gb": servers * v["server_transfer_gb"]}


def report() -> dict:
    x = inputs()
    measured = measure()
    tokens = llm_tokens(x["chars_per_token"]["value"])
    return {"measured": measured, "tokens": tokens, "inputs": x, "computed": date.today().isoformat(),
            "rows": [monthly(n, measured, tokens, x) for n in USERS]}


def as_markdown(r: dict) -> str:
    m, t, x = r["measured"], r["tokens"], r["inputs"]
    memory = "not readable on this system" if m["memory_mb"] is None else f"{m['memory_mb']} MB"
    out = ["# What it costs to run", "",
           f"Generated by `python scripts/cost_model.py --write` on {r['computed']}. Run it again to check every figure. "
           "Measured values come from the machine the script ran on, prices from the providers' own pages, and the rest "
           "are our assumptions, marked as such. People's time is not priced.", "",
           "## Measured", "",
           f"- One full journey (the page, the six steps, one piece of simulated news, the team view): {m['requests']} requests, "
           f"**{m['cpu_seconds']:g} processor seconds** and **{m['transfer_kb']} KB** sent (gzip).",
           f"- Server memory at its peak: **{memory}**, against {x['server_memory_mb']['value']:g} MB on the server priced below.",
           f"- Timed on: {m['machine']}, Python {m['python']}. A rented core is assumed "
           f"{x['cpu_slowdown']['value']:g} times slower (assumption).",
           f"- One \"Why this score?\" request to the optional language model: about {t['in']} tokens in and {t['out']} out "
           f"(the reply is cut off at {t['out_cap']}).", "",
           "## A month", "",
           "| People in the month | Online at the busiest moment | Servers | Hosting (RM) | AI text, optional (RM) | Total (RM) | Per person (RM) |",
           "|---|---|---|---|---|---|---|"]
    out += [f"| {row['users']:,} | {row['peak_people']} | {row['servers']} | {row['hosting_myr']:.2f} | {row['llm_myr']:.2f} "
            f"| {row['total_myr']:.2f} | {row['per_user_myr']:.4f} |" for row in r["rows"]]
    first = r["rows"][0]
    out += ["", f"One server carries about {first['server_carries']:g} people working through the steps at the same moment, so a "
            f"workshop of {x['class_size']['value']:g} sets the floor at {first['servers']} servers however few people use it in "
            f"the month. The largest case sends {r['rows'][-1]['transfer_gb']:g} GB in the month, inside the "
            f"{r['rows'][-1]['transfer_included_gb']:g} GB included.", "",
            f"Not in the table: a domain name (optional), and upkeep of about {x['upkeep_hours']['value']:g} hours a quarter "
            "(the DOSM workbook, reviewing a new Economic Index release, checking links). The weekly data update runs by "
            "itself against free public sources. Without a language-model key the app costs the hosting line only.", "",
            "## Prices and assumptions", "", "| Input | Value | Kind | Source | Date |", "|---|---|---|---|---|"]
    out += [f"| {row['label']} | {row['value']:g} {row['unit']} | {row['kind'].replace('_', ' ')} | "
            + (row["source_name"] if row["kind"] == "assumption" else f"[{row['source_name']}]({row['source_url']})")
            + f" | {row['source_date']} |" for row in x.values()]
    return "\n".join(out)


def cli() -> int:
    args = argparse.ArgumentParser(description="The monthly cost of running the app, from measured values and listed prices.")
    args.add_argument("--write", action="store_true", help="save the table as docs/cost_model.md")
    opts = args.parse_args()
    text = as_markdown(report())
    if opts.write:
        (ROOT / "docs" / "cost_model.md").write_text(text + "\n", encoding="utf-8", newline="\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
