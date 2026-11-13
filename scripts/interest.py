"""Score the interest questionnaire (data/interest_items.json) on Holland's six types (RIASEC).

Each of the 36 statements belongs to one type and is answered 1 (strongly dislike) to 5
(strongly like). A type's total is the sum of its six answers (6-30), also given as 0-100:

    percent = (total - 6) / 24 x 100

code = the three highest types (ties go in R, I, A, S, E, C order). matching.py compares the
six totals with each occupation's O*NET interest scores (Pearson correlation), so only their
pattern matters, not their level.

The result says when it should not be leaned on (warnings, usable):
    same_answer   every statement got the same answer: no pattern to compare
    flat          the six totals lie within FLAT_RANGE points of each other
    all_low       no type reaches LOW_TOTAL: the person liked hardly anything listed
A result with same_answer or flat is not usable for matching; all_low is shown but still used.

Usage: python scripts/interest.py 5 4 3 ...   (36 answers)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "data" / "interest_items.json"
TYPES = ("R", "I", "A", "S", "E", "C")
FLAT_RANGE = 3      # totals within 3 points (of 24) of each other show no clear pattern
LOW_TOTAL = 18      # no type at "like" on average (3 x 6) or above


class AnswerError(ValueError):
    """Answers that cannot be scored; the text says which one is wrong."""


def item_bank() -> dict:
    return json.loads(ITEMS.read_text(encoding="utf-8"))


def score(answers: list) -> dict:
    """Totals, percents, code and warnings for a list of 36 answers (1-5)."""
    bank = item_bank()
    items = bank["items"]
    if type(answers) is not list or len(answers) != len(items):
        raise AnswerError(f"'answers' must be a list of {len(items)} numbers from 1 to 5")
    wrong = [n for n, a in enumerate(answers, 1) if type(a) is not int or a not in range(1, 6)]
    if wrong:
        raise AnswerError(f"answer {wrong[0]} must be a whole number from 1 to 5")
    totals = dict.fromkeys(TYPES, 0)
    for statement, answer in zip(items, answers):
        totals[statement["type"]] += answer
    per_type = len(items) // len(TYPES)
    low, high = per_type, per_type * 5
    percent = {t: round(100 * (v - low) / (high - low), 1) for t, v in totals.items()}
    code = "".join(sorted(TYPES, key=lambda t: (-totals[t], TYPES.index(t)))[:3])
    warnings = []
    if min(answers) == max(answers):
        warnings.append({"type": "same_answer", "text": "You gave every statement the same answer, so your "
                                                        "interests cannot be told apart. Try again and use the "
                                                        "whole scale."})
    elif max(totals.values()) - min(totals.values()) <= FLAT_RANGE:
        warnings.append({"type": "flat", "text": "Your six interest totals are very close, so they do not point "
                                                 "to any kind of work. Interest is left out of your matches."})
    if max(totals.values()) < LOW_TOTAL:
        warnings.append({"type": "all_low", "text": "You liked few of the activities listed. Your result shows "
                                                    "what you dislike least; the field choices on your profile "
                                                    "may say more."})
    usable = not any(w["type"] in ("same_answer", "flat") for w in warnings)
    return {"riasec": totals, "percent": percent, "code": code, "warnings": warnings, "usable": usable,
            "attribution": bank["attribution"]}


def main(argv: list[str]) -> int:
    try:
        result = score([int(a) for a in argv])
    except (ValueError, AnswerError) as e:
        print(e)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
