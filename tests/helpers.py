"""Shared set-up for the tests: the import paths and a few calls every test file needs."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import main  # noqa: E402,F401  (also puts scripts/ on the path)
import matching  # noqa: E402

DATA = matching.load_data()
NURSE = "29-1141.00"
ACCOUNTANT = "13-2011.00"
CLERK = "43-3031.00"
COOK = "35-2014.00"
DEVELOPER = "15-1252.00"


def post(path: str, body: dict) -> tuple[int, dict]:
    res = main.dispatch("POST", path, json.dumps(body).encode("utf-8"))
    return res.status, json.loads(res.body)


def get(path: str) -> tuple[int, dict | list]:
    res = main.dispatch("GET", path)
    return res.status, json.loads(res.body)


def sample(profile_id: str) -> dict:
    people = json.loads((ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8"))
    return next(p for p in people if p["profile_id"] == profile_id)
