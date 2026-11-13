import unittest

from helpers import CLERK, DATA, NURSE

import demand


class TestDemand(unittest.TestCase):
    inputs = demand.load_inputs()

    def test_the_dosm_workbook_is_read_after_the_series_break(self):
        rows = demand.job_ad_rows()
        self.assertTrue(rows)
        self.assertTrue(all(r["period_start"] >= "2025-07-01" for r in rows))
        self.assertEqual({r["entity"] for r in rows}, {"all", *demand.MASCO_MAJOR})

    def test_group_signals_compare_shares_of_all_ads(self):
        groups = demand.ad_signals(self.inputs["inputs"], {})
        self.assertEqual(set(groups), set(demand.MASCO_MAJOR))
        self.assertAlmostEqual(sum(g["share_after"] for g in groups.values()), 100.0, delta=1.0)
        for g in groups.values():
            self.assertTrue(-1 <= g["strength"] <= 1)

    def test_mycol_and_ads_set_each_occupations_demand(self):
        out = demand.build(self.inputs)
        nurse = out["occupations"][NURSE]
        self.assertEqual(nurse["mycol"], "yes")
        self.assertEqual([s["signal"] for s in nurse["signals"]], ["mycol", "job_ads"])
        self.assertTrue(all(0 <= o["demand"] <= 100 for o in out["occupations"].values()))
        self.assertGreater(nurse["demand"], out["occupations"][CLERK]["demand"])

    def test_a_what_if_changes_a_copy_only(self):
        before = demand.build(self.inputs)
        after = demand.build(self.inputs, {"mycol": {NURSE: "no"}, "job_ads": {"2": -50}, "arxiv": 50})
        self.assertLess(after["occupations"][NURSE]["demand"], before["occupations"][NURSE]["demand"])
        self.assertGreater(after["momentum"]["momentum"], before["momentum"]["momentum"])
        self.assertEqual(demand.current()["occupations"][NURSE]["mycol"], "yes")

    def test_momentum_follows_the_growth_of_ai_papers(self):
        m = demand.momentum_of(self.inputs["inputs"], {})
        expected = 50 + 50 * max(-1, min(1, m["growth_pct"] / demand.ARXIV_FULL_PCT))
        self.assertAlmostEqual(m["momentum"], expected, delta=0.1)

    def test_wages_are_context_for_every_major_group(self):
        self.assertTrue(set(demand.MASCO_MAJOR) <= set(DATA["demand"]["wages"]))


if __name__ == "__main__":
    unittest.main()
