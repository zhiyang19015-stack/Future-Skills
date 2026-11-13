"""Is there a newer Anthropic Economic Index release than the one the scores use?

The release is pinned (scripts/ai_exposure_extract.py): a new one may change its columns or
its meaning, so it is never taken in unseen. The "Update data" job only asks the dataset's
public file listing for the newest release folder and reports it. A person then reviews the
release, pins it and rebuilds the tables.

The answer is kept in .cache/release_check.json so the Sources page can show when it was last
checked without calling out again.
"""

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

import ai_exposure

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "release_check.json"
LISTING = "https://huggingface.co/api/datasets/Anthropic/EconomicIndex/tree/main"
RELEASE = re.compile(r"^release_(\d{4})_(\d{2})_(\d{2})$")
TIMEOUT_S = 15


def pinned() -> str:
    return ai_exposure.current()["source"]["economic_index"]["release_date"]


def fetch_listing() -> list[dict]:
    req = urllib.request.Request(LISTING, headers={"User-Agent": "future-skills"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())


def latest_release(listing: list[dict]) -> str | None:
    """The newest release date among the dataset's top-level folders, as YYYY-MM-DD."""
    found = [RELEASE.match(str(item.get("path", ""))) for item in listing if isinstance(item, dict)]
    dates = ["-".join(m.groups()) for m in found if m]
    return max(dates, default=None)


def check(fetch=fetch_listing) -> dict:
    """Compare the pinned release with the newest one. Never raises: an unreachable listing is reported."""
    out = {"pinned": pinned(), "latest": None, "new_release": False,
           "checked": date.today().isoformat(), "error": None}
    try:
        out["latest"] = latest_release(fetch())
        out["new_release"] = bool(out["latest"] and out["latest"] > out["pinned"])
    except Exception as e:  # noqa: BLE001  the update job must finish whatever the listing does
        out["error"] = f"could not read the release listing: {e.__class__.__name__}"
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass
    return out


def last_check() -> dict:
    """The result of the last check(), or "never checked" for the pinned release."""
    try:
        saved = json.loads(CACHE.read_text(encoding="utf-8"))
        if saved.get("pinned") == pinned():
            return saved
    except (OSError, ValueError):
        pass
    return {"pinned": pinned(), "latest": None, "new_release": False, "checked": None, "error": None}
