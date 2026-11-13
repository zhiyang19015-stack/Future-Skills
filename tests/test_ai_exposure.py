import unittest

from helpers import DATA, DEVELOPER, NURSE

import ai_exposure


class TestAIExposure(unittest.TestCase):
    layer = DATA["ai"]

    def test_weighted_reading_follows_anthropic(self):
        self.assertEqual(ai_exposure.weighted_reading(60.0, 40.0), 80.0)
        self.assertEqual(ai_exposure.weighted_reading(None, 50.0), 25.0)
        self.assertIsNone(ai_exposure.weighted_reading(None, None))

    def test_every_share_sits_inside_its_range(self):
        for occ_id, r in self.layer["roles"].items():
            self.assertLessEqual(r["ai_share_low"], r["ai_share"], occ_id)
            self.assertLessEqual(r["ai_share"], r["ai_share_high"], occ_id)
            self.assertTrue(0 <= r["ai_share_low"] and r["ai_share_high"] <= 100, occ_id)

    def test_a_well_measured_occupation_keeps_its_own_reading(self):
        dev = self.layer["roles"][DEVELOPER]
        self.assertEqual(dev["evidence"], 1.0)
        self.assertEqual(dev["ai_share"], dev["ai_share_measured"])

    def test_a_thin_occupation_leans_on_its_prior_and_keeps_a_wide_range(self):
        nurse = self.layer["roles"][NURSE]
        self.assertLess(nurse["evidence"], 0.5)
        self.assertTrue(nurse["thin_evidence"])
        slack = (1 - nurse["evidence"]) * ai_exposure.THIN_SPREAD  # at least this much on each side, within 0-100
        self.assertGreaterEqual(nurse["ai_share_high"] - nurse["ai_share"], slack - 0.1)
        self.assertGreaterEqual(nurse["ai_share"] - nurse["ai_share_low"], min(slack, nurse["ai_share"]) - 0.1)

    def test_an_unobserved_occupation_takes_its_fields_prior_not_zero(self):
        unobserved = [r for r in self.layer["roles"].values() if r["anthropic_observed_exposure"] == 0.0]
        self.assertTrue(unobserved)
        for r in unobserved:
            self.assertEqual(r["prior_basis"], "field", r["occ_id"])

    def test_computer_work_is_more_exposed_than_building_work(self):
        ref = self.layer["reference"]["field_ai_share"]
        self.assertGreater(ref["15"], ref["47"])
        self.assertGreater(ref["43"], ref["35"])

    def test_a_what_if_lifts_only_the_tasks_under_its_work_activity(self):
        activity = "Record patient medical histories."
        changed = ai_exposure.build(changes={"ai_share": {activity: 95.0}})
        for t in changed["tasks"]:
            if activity in t["work_activities"]:
                self.assertGreaterEqual(t["ai_share"], 95.0)
        self.assertGreater(changed["roles"][NURSE]["ai_share"], self.layer["roles"][NURSE]["ai_share"])
        self.assertEqual(changed["roles"][DEVELOPER]["ai_share"], self.layer["roles"][DEVELOPER]["ai_share"])
        self.assertTrue(changed["changed"])

    def test_tools_take_the_hands_off_share_of_their_topic(self):
        excel = self.layer["skills"]["microsoft-excel"]
        topic = self.layer["topics"]["Data analysis"]
        self.assertEqual((excel["basis"], excel["handoff"]), ("topic", topic["handoff"]))
        self.assertEqual(self.layer["skills"]["2.C.5.a"]["basis"], "none")  # knowledge areas have no link

    def test_tables_have_a_row_per_occupation(self):
        tables = ai_exposure.tables(self.layer)
        self.assertEqual(len(tables["ai_occupations.csv"]), len(DATA["occupations"]))
        self.assertEqual(len(tables["ai_tasks.csv"]), len(self.layer["tasks"]))


if __name__ == "__main__":
    unittest.main()
