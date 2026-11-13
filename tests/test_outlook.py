import unittest

from helpers import COOK, DATA, NURSE

import outlook


class TestOutlook(unittest.TestCase):
    def test_adoption_comes_from_the_scenario_or_is_kept_in_range(self):
        self.assertEqual(outlook.adoption_of("fast"), 0.5)
        self.assertEqual(outlook.adoption_of(None, 2.0), outlook.ADOPTION_MAX)
        self.assertEqual(outlook.adoption_of(None, -1), 0.0)

    def test_nothing_moves_without_adoption(self):
        for occ in DATA["occupations"][::40]:
            o = outlook.role_outlook(occ, DATA, 0.0)
            self.assertEqual((o["change"], o["status"]), (0.0, "steady"))
            self.assertEqual(o["outlook"], o["demand"])

    def test_more_ai_share_than_average_costs_outlook_points(self):
        avg = DATA["ai"]["reference"]["role_ai_share"]
        exposed = next(o for o in DATA["occupations"] if DATA["ai"]["roles"][o["occ_id"]]["ai_share"] > avg + 20)
        sheltered = DATA["by_id"][COOK]
        self.assertLess(outlook.role_outlook(exposed, DATA, 0.5)["change"], 0)
        self.assertGreater(outlook.role_outlook(sheltered, DATA, 0.5)["change"], 0)

    def test_faster_adoption_moves_further(self):
        occ = DATA["by_id"][NURSE]
        slow, fast = (abs(outlook.role_outlook(occ, DATA, a)["change"]) for a in (0.1, 0.5))
        self.assertGreater(fast, slow)

    def test_a_skill_handed_over_more_than_typical_counts_for_less(self):
        ref = DATA["ai"]["reference"]
        heavy = outlook.skill_weight({"handoff": ref["skill_handoff"] + 30, "builder": False}, 0.5, ref)
        light = outlook.skill_weight({"handoff": ref["skill_handoff"] - 30, "builder": False}, 0.5, ref)
        self.assertLess(heavy["weight"], 1.0)
        self.assertGreater(light["weight"], 1.0)
        self.assertEqual(outlook.skill_weight(None, 0.5, ref)["weight"], 1.0)

    def test_the_drawn_futures_are_repeatable(self):
        roles = [{"occ_id": f"X{i}", "field": 50.0, "interest": 50.0, "skill_curve": None, "demand": 40.0 + 5 * i,
                  "ai_share": 10.0, "ai_share_low": 5.0, "ai_share_high": 15.0, "builder": 0.0, "tempo": 1.0,
                  "bonus": 0.0, "last": False} for i in range(4)]
        total = lambda f, i, s, o: o  # noqa: E731
        a = outlook.simulate(roles, total, DATA["ai"]["reference"], n=200)
        b = outlook.simulate(roles, total, DATA["ai"]["reference"], n=200)
        self.assertEqual(a, b)
        self.assertAlmostEqual(sum(r["top1"] for r in a["roles"].values()), 100.0, delta=0.5)
        self.assertGreater(a["roles"]["X3"]["top1"], a["roles"]["X0"]["top1"])


if __name__ == "__main__":
    unittest.main()
