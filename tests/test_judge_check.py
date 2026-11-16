"""The judge check script: each check reads the real API and the report is built from its numbers."""

import json
import unittest

import helpers  # noqa: F401  (sets the import paths)
import judge_check


class JudgeCheckTest(unittest.TestCase):
    def test_blank_profile_reports_what_the_api_returns(self):
        found = judge_check.blank_profile()
        self.assertEqual(found["status"], 200)
        self.assertEqual(found["pass"], found["ranked"] == 0)
        self.assertEqual(len(found["top"]), min(3, found["ranked"]))

    def test_radar_counts_match_its_rows(self):
        found = judge_check.radar()
        for name in ("moderate", "fast"):
            rows = found[name]["rows"]
            self.assertLessEqual(len(rows), judge_check.RADAR_TOP)
            self.assertEqual(found[name]["unmeasured"], sum(1 for r in rows if r["thin"] or r["manual"]))

    def test_job_search_titles(self):
        for title in ("PRDV102: Resume Writing", "PRDV103: Interviewing Skills", "Write a CV"):
            self.assertTrue(judge_check.JOB_SEARCH.search(title), title)
        for title in ("CS105: Introduction to Python", "Curriculum Design", "Software Testing"):
            self.assertFalse(judge_check.JOB_SEARCH.search(title), title)

    def test_link_draw_repeats_with_its_seed(self):
        a = judge_check.links(7, offline=True)
        self.assertEqual(a, judge_check.links(7, offline=True))
        self.assertFalse(a["checked"])
        self.assertEqual(len(a["rows"]), judge_check.LINKS)

    def test_no_public_url_is_reported_as_none(self):
        self.assertEqual(judge_check.public_url(None, offline=False)["detail"], "none")

    def test_report_is_built_from_the_saved_numbers(self):
        if not judge_check.BASELINE.exists():
            self.skipTest("no baseline saved")
        base = json.loads(judge_check.BASELINE.read_text(encoding="utf-8"))
        text = judge_check.as_markdown(base, base)
        for k, v in judge_check.headline(base).items():
            self.assertIn(f"| {k} | {v} | {v} |", text)
        for n in range(1, 8):
            self.assertIn(f"## {n}. ", text)


if __name__ == "__main__":
    unittest.main()
