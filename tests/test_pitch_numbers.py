"""The pitch material quotes the numbers the scripts produce (scripts/pitch_numbers.py), not older ones."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PITCH = ROOT / "docs" / "pitch"
DOCS = ("deck_outline.md", "demo_script.md", "qa_cheatsheet.md")
# The keys the pitch quotes; each value must appear in the pitch documents.
QUOTED = ("eval_first_ok", "eval_top5_ok", "v1_first_ok", "v1_top5_ok", "eval_first_changed", "eval_top5_set_changed",
          "eval_free_k", "eval_non_english", "eval_top5_occupations_take", "eval_distinct_first",
          "demo_first_move_changed", "ilo_confirmed", "ilo_disagree", "kpi2_it", "kpi2_all")


class PitchNumbersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PITCH / "numbers.json"
        if not path.exists():
            raise unittest.SkipTest("run scripts/pitch_numbers.py --write first")
        cls.n = json.loads(path.read_text(encoding="utf-8"))
        cls.text = "\n".join((PITCH / d).read_text(encoding="utf-8") for d in DOCS)

    def test_numbers_file_is_current(self):
        import pitch_numbers
        self.assertEqual(pitch_numbers.numbers(), self.n)

    def test_every_quoted_number_is_the_current_one(self):
        missing = [k for k in QUOTED if str(self.n[k]) not in self.text]
        self.assertEqual(missing, [], {k: self.n[k] for k in missing})

    def test_no_claim_that_the_demo_first_move_changes(self):
        # since stage 7 no demo person's first move changes between slow and fast adoption (judge_check)
        if self.n["demo_first_move_changed"].startswith("0 "):
            self.assertIsNone(re.search(r"first move (?:changes|flips) for (?:Aiman|the demo)", self.text, re.I))


if __name__ == "__main__":
    unittest.main()
