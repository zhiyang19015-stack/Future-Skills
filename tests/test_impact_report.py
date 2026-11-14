"""HRD Corp-claimable courses on the learning page, and the impact report against the Phase 1 baseline."""
import json
import unittest

from helpers import ACCOUNTANT, COOK, DATA, DEVELOPER, NURSE, ROOT, post

import impact_report
import learning
import matching


class TestClaimable(unittest.TestCase):
    def test_claimable_courses_are_never_free(self):
        rows = [r for r in DATA["resources"] if r["format"] == "claimable"]
        self.assertGreaterEqual(len(rows), 10)
        for r in rows:
            self.assertFalse(matching.is_free(r), r["resource_id"])
            self.assertIn("HRD", r["notes"])

    def test_they_stay_out_of_the_free_plan_and_its_hours(self):
        page = learning.page(DEVELOPER, DATA)
        free_urls = {r["url"] for s in page["skills"] for r in s["resources"]} | {r["url"] for r in page["stages"][0]["resources"]}
        self.assertTrue(page["claimable"])
        self.assertFalse(free_urls & {r["url"] for r in page["claimable"]})
        self.assertLessEqual(len(page["claimable"]), learning.MAX_CLAIMABLE)

    def test_they_fit_the_occupation(self):
        titles = lambda occ: {r["title"] for r in learning.page(occ, DATA)["claimable"]}
        self.assertIn("Certified Trade Finance Professional (CTFP)", titles(ACCOUNTANT))
        self.assertTrue(any("HACCP" in t for t in titles(COOK)))
        self.assertFalse(any("Project Management" in t for t in titles(NURSE)))
        self.assertFalse(any("Project Management" in t for t in titles(COOK)))

    def test_the_api_returns_them_for_a_person(self):
        status, page = post("/api/learn", {"profile_id": "P05", "occ_id": DEVELOPER})
        self.assertEqual(status, 200)
        self.assertIn("claimable", page)
        for r in page["claimable"]:
            self.assertEqual(r["format"], "claimable")
            self.assertTrue(r["cost_myr"] or r["fee_on_request"])


class TestImpactReport(unittest.TestCase):
    def test_a_demo_journey_names_a_target_gaps_and_a_free_course(self):
        people = json.loads((ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8"))
        run = impact_report.journey(people[0], DATA)
        self.assertTrue(run["target"])
        self.assertGreaterEqual(run["gaps"], 2)
        self.assertTrue(run["free_course"])

    def test_it_coverage_beats_the_phase1_target(self):
        it = impact_report.it_coverage(DATA)
        self.assertGreater(it["occupations"], 20)
        self.assertGreaterEqual(it["mean"], impact_report.PHASE1["coverage_target"])

    def test_the_report_claims_no_people_result(self):
        fake = {"phase1": impact_report.PHASE1, "coverage": {"occupations": 1, "mean": 50.0, "elements": 2, "elements_covered": 1},
                "it": {"occupations": 1, "mean": 50.0, "lowest": 50.0},
                "journey": {"people": 1, "clear": 1, "share": 100.0, "missing": []},
                "cost": {"occupations": 1, "with_hrd": 1, "hrd_courses": 1}, "demo": [], "sdg": {}, "computed": "2026-11-14"}
        text = impact_report.as_markdown(fake)
        self.assertIn("not measured with people", text)
        self.assertIn("This tests the system, not people", text)


if __name__ == "__main__":
    unittest.main()
