import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import fairness_check  # noqa: E402


class TestFairness(unittest.TestCase):
    def test_personal_details_change_nothing(self):
        out = fairness_check.check()
        self.assertEqual(out["people"], 8)
        self.assertEqual(out["occupations"], 30)
        self.assertEqual(out["gap"], {"technologies": 0, "cv_field": 0.0, "field_fit": 0.0, "order": 0, "score": 0.0})
        self.assertTrue(out["fair"])

    def test_check_sees_a_real_difference(self):
        # A person with more tools must come out different, or the check proves nothing.
        same = fairness_check.run_one(fairness_check.PEOPLE[0])
        sample = fairness_check.SAMPLE
        try:
            fairness_check.SAMPLE = sample.replace("Google Sheets", "Google Sheets, Python, Tableau, Microsoft Power BI")
            other = fairness_check.run_one(fairness_check.PEOPLE[0])
        finally:
            fairness_check.SAMPLE = sample
        gap = fairness_check.largest_gap([same, other])
        self.assertGreater(gap["technologies"], 0)
        self.assertGreater(gap["score"], 0)


if __name__ == "__main__":
    unittest.main()
