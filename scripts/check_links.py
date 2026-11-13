"""Open every link a person can click and report the ones that no longer work.

    python scripts/check_links.py          needs the internet; exits 1 when a link is broken

Checked: the learning resources (data/learning_resources.csv) and the professional bodies
(data/regulated.csv). A site that refuses scripts (HTTP 401, 403, 429) is listed as "refused"
to open by hand, not as broken. A Saylor Academy page that sends people to its log-in page is
broken for our purpose: the course is no longer open to everyone.
"""

import csv
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCES = (("learning_resources.csv", "resource_id", "url"), ("regulated.csv", "profession", "url"))
REFUSED = {401, 403, 429}
TIMEOUT_S = 30
AGENT = "Mozilla/5.0 (compatible; future-skills-link-check)"


def links() -> list[tuple[str, str, str]]:
    out = []
    for name, key, col in SOURCES:
        with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
            out += [(name, r[key], r[col]) for r in csv.DictReader(f) if r[col]]
    return out


def status(url: str) -> tuple[str, str]:
    """("ok" | "refused" | "broken", detail) for one link."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read(200_000).decode("utf-8", "replace")
            if "learn.saylor.org" in url and "<title>Log in to the site" in body:
                return "broken", "asks for a log-in"
            return "ok", str(r.status)
    except urllib.error.HTTPError as refused:
        return ("refused" if refused.code in REFUSED else "broken"), f"HTTP {refused.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as failure:
        return "broken", type(failure).__name__


def main() -> int:
    found = links()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda x: status(x[2]), found))
    broken = [(f, r) for f, r in zip(found, results) if r[0] == "broken"]
    refused = [(f, r) for f, r in zip(found, results) if r[0] == "refused"]
    for (name, key, url), (_, detail) in broken:
        print(f"BROKEN   {name} {key}: {url} ({detail})")
    for (name, key, url), (_, detail) in refused:
        print(f"REFUSED  {name} {key}: {url} ({detail}; open it by hand)")
    print(f"{len(found)} links: {len(found) - len(broken) - len(refused)} ok, {len(refused)} refused, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
