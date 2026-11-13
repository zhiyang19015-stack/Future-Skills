"""The pathway page and the what-if pipeline."""
import unittest

from helpers import ACCOUNTANT, CLERK, DATA, NURSE, sample

import learning
import matching
import whatif


class TestLearning(unittest.TestCase):
    def test_an_occupations_own_page(self):
        page = learning.page(NURSE, DATA)
        self.assertFalse(page["personal"])
        self.assertTrue(page["stages"][0]["resources"])  # foundations for the field and for everyone
        self.assertEqual(page["licence"]["body"].split(" (")[0], "Nursing Board Malaysia")
        self.assertTrue(any(s["role"] for s in page["sdg"]))  # the occupation's own SDG target comes first
        self.assertTrue(page["sdg"][0]["role"])

    def test_a_personal_page_follows_the_persons_gaps(self):
        m = matching.match_person(sample("P02"), DATA, top=1, futures=0, include=[ACCOUNTANT])["results"][-1]
        page = learning.page(ACCOUNTANT, DATA, m, 5)
        self.assertTrue(page["personal"])
        gap_ids = {g["skill_id"] for g in m["skill_detail"]["gaps"]} | {t["skill_id"] for t in m["skill_detail"]["tech_missing"]}
        self.assertTrue({s["skill_id"] for s in page["skills"]} <= gap_ids)
        self.assertEqual(page["weeks"], round(page["total_hours"] / 5, 1))

    def test_hands_on_skills_point_to_training_in_malaysia(self):
        page = learning.page("47-2111.00", DATA)  # electricians
        self.assertTrue(any("Skills Development" in r["provider"] for r in page["hands_on"]))

    def test_an_unknown_occupation_has_no_page(self):
        self.assertIsNone(learning.page("00-0000.00", DATA))


class TestWhatIf(unittest.TestCase):
    def test_validation(self):
        ok = whatif.validate({"job_ads": {"5": -20}, "mycol": {NURSE: "no"}, "arxiv": 10})
        self.assertEqual((ok["job_ads"], ok["mycol"], ok["arxiv"]), ({"5": -20.0}, {NURSE: "no"}, 10.0))
        self.assertFalse(whatif.changed(whatif.validate({"mycol": {NURSE: "yes"}})))  # what it already is
        for bad in ({"job_ads": {"0": 10}}, {"job_ads": {"5": 500}}, {"mycol": {NURSE: "maybe"}},
                    {"mycol": {"00-0000.00": "no"}}, {"handoff": {"Not a topic": 50}},
                    {"ai_share": {"Not an activity.": 50}}, {"other": 1}, [1]):
            with self.assertRaises(whatif.WhatIfError):
                whatif.validate(bad)

    def test_every_simulated_news_item_changes_something(self):
        news = whatif.news()
        self.assertGreaterEqual(len(news), 6)
        self.assertGreater(len({n["field"] for n in news}), 4)  # across many fields, not only IT
        for n in news:
            self.assertTrue(n["simulated"])
            self.assertTrue(whatif.changed(whatif.validate(n["changes"])), n["id"])

    def test_news_moves_the_occupations_it_is_about(self):
        n = next(x for x in whatif.news() if x["id"] == "auto_bookkeeping")
        after = whatif.changed_data(DATA, whatif.validate(n["changes"]))
        moved = {r["occ_id"]: r for r in whatif.role_changes(DATA, after, 0.25, limit=100)}
        self.assertIn(CLERK, moved)
        self.assertLess(moved[CLERK]["move"], 0)
        self.assertEqual(DATA["ai"]["roles"][CLERK]["ai_share"], matching.load_data()["ai"]["roles"][CLERK]["ai_share"])

    def test_a_mycol_change_reaches_demand(self):
        after = whatif.changed_data(DATA, whatif.validate({"mycol": {NURSE: "no"}}))
        self.assertEqual(after["by_id"][NURSE]["mycol"], "no")
        self.assertLess(after["demand"]["occupations"][NURSE]["demand"], DATA["demand"]["occupations"][NURSE]["demand"])
        described = whatif.describe(whatif.validate({"mycol": {NURSE: "no"}}))
        self.assertEqual((described[0]["before"], described[0]["after"]), ("yes", "no"))


if __name__ == "__main__":
    unittest.main()
