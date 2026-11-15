"""Robust and scenario-dependent choices: the rule on made-up rankings, then on the real API for
every demo person (Matches and Futures), and the judge check's reading of it."""
import re
import unittest
from pathlib import Path

from helpers import post

import judge_check
import main
import outlook
import robust

NAMES = list(outlook.SCENARIOS)


def occ(occ_id: str, total: float, outlook_pts: float = 0.0, skill_pts: float = 0.0, exposure: float = 0.0,
        builder: float = 0.0, ai_share: float = 10.0, out: float = 50.0) -> dict:
    """One listed match, with only the parts the rule reads."""
    return {"occ_id": occ_id, "title": occ_id.upper(), "total": total,
            "components": {"outlook": {"points": outlook_pts, "score": out}, "skill": {"points": skill_pts, "score": 50.0}},
            "outlook": {"exposure_points": exposure, "builder_points": builder, "outlook": out, "ai_share": ai_share,
                        "ai_share_reference": 10.0, "builder": 0.0, "builder_reference": 0.0, "thin": False}}


def orders(*lists) -> dict:
    return dict(zip(NAMES, lists))


class TestRule(unittest.TestCase):
    def test_first_under_all_is_robust_with_its_lead(self):
        rows = [occ("a", 80), occ("b", 78), occ("c", 70), occ("d", 60), occ("e", 50), occ("f", 40)]
        r = robust.classify(orders(rows, rows, rows))
        self.assertEqual([x["occ_id"] for x in r["robust"]], ["a", "b", "c"])
        self.assertEqual(r["robust"][0]["kind"], "first")
        self.assertEqual(r["robust"][0]["lead"], 2.0)
        self.assertEqual(r["robust"][1]["kind"], "top3")
        self.assertEqual(r["dependent"], [])
        self.assertTrue(r["rules"]["estimate"])

    def test_an_occupation_entering_the_top_5_only_when_fast_is_scenario_dependent(self):
        base = [occ(x, 90 - i) for i, x in enumerate("abcdef")]
        # f: low AI share, its outlook rises with adoption and it overtakes e
        slow_f = occ("f", 84, outlook_pts=10.0, exposure=1.0, ai_share=3.0, out=60)
        fast_f = occ("f", 86.5, outlook_pts=12.5, exposure=8.0, ai_share=3.0, out=67)
        slow = base[:5] + [slow_f]
        fast = base[:4] + [fast_f, base[4]]
        r = robust.classify(orders(slow, slow, fast))
        dep = {x["occ_id"]: x for x in r["dependent"]}
        self.assertIn("f", dep)
        self.assertEqual(dep["f"]["kind"], "enters")
        self.assertEqual(dep["f"]["in_top"], ["fast"])
        why = dep["f"]["why"]
        self.assertEqual(why["code"], "share_low")
        self.assertEqual(why["outlook_move"], 7.0)
        self.assertEqual(why["total_move"], 2.5)
        self.assertEqual(dep["e"]["why"]["code"], "others")      # e itself does not move: f does
        self.assertEqual(dep["e"]["why"]["crossed"]["occ_id"], "f")

    def test_a_skill_led_move_says_so(self):
        w = robust.reason(occ("x", 70, skill_pts=10.0), occ("x", 66, skill_pts=6.0, outlook_pts=0.5))
        self.assertEqual(w["code"], "skills_down")
        w = robust.reason(occ("x", 70, outlook_pts=5.0, exposure=0.0), occ("x", 72, outlook_pts=7.0, exposure=-1.0, builder=4.0))
        self.assertEqual(w["code"], "builder")
        w = robust.reason(occ("x", 70, outlook_pts=5.0), occ("x", 65, outlook_pts=0.0, exposure=-9.0, ai_share=40.0))
        self.assertEqual(w["code"], "share_high")

    def test_nothing_robust_when_no_occupation_holds_the_top_3(self):
        a = [occ(x, 90 - i) for i, x in enumerate("abcdefgh")]
        b = [occ(x, 90 - i) for i, x in enumerate("defabcgh")]
        r = robust.classify(orders(a, a, b))
        self.assertEqual(r["robust"], [])
        self.assertTrue(r["dependent"])

    def test_one_scenario_is_not_compared(self):
        r = robust.classify({"slow": [occ("a", 1)]})
        self.assertEqual((r["robust"], r["dependent"]), ([], []))


class TestApi(unittest.TestCase):
    def test_every_demo_person_gets_robust_choices_and_a_why_on_both_pages(self):
        for p in main.sample_profiles():
            pid = p["profile_id"]
            _, fut = post("/api/futures", {"profile_id": pid, "top": robust.TOP})
            _, mat = post("/api/match", {"profile_id": pid})
            self.assertEqual(fut["robust"], mat["robust"], pid)   # the same three rankings on both pages
            cols = {c["id"]: [m["occ_id"] for m in c["top"]] for c in fut["scenarios"]}
            r = fut["robust"]
            self.assertTrue(r["robust"], pid)
            for x in r["robust"]:
                for name in NAMES:
                    self.assertIn(x["occ_id"], cols[name][:robust.ROBUST_TOP], (pid, x["title"], name))
            for x in r["dependent"]:
                self.assertTrue(judge_check.has_why(x), (pid, x))
                inside = [n for n in NAMES if x["occ_id"] in cols[n]]
                self.assertEqual(inside, x["in_top"], (pid, x["title"]))
                self.assertTrue(len(inside) < len(NAMES) or x["rank_swing"] >= robust.RANK_SWING)

    def test_the_why_matches_the_numbers_of_the_moves_table(self):
        _, fut = post("/api/futures", {"profile_id": "P05", "top": robust.TOP})
        moves = {m["occ_id"]: m for m in fut["moves"]}
        for x in fut["robust"]["dependent"]:
            if x["occ_id"] in moves:
                self.assertEqual(x["why"]["total_move"], moves[x["occ_id"]]["total_move"])
                self.assertEqual(x["why"]["outlook_move"], moves[x["occ_id"]]["outlook_move"])


class TestStrings(unittest.TestCase):
    def test_every_reason_has_text_in_three_languages(self):
        text = (Path(main.ROOT) / "src" / "static" / "i18n.js").read_text(encoding="utf-8")
        keys = ["rb.h", "rb.p", "rb.first", "rb.top3", "rb.robust.none", "rb.dep.none", "rb.when.enters",
                "rb.when.moves", "rb.thin", "rb.why.others.none"] + [f"rb.why.{c}" for c in robust.REASONS]
        for key in keys:
            row = re.search(r'^  "' + re.escape(key) + r'": \[(.*)\],$', text, re.M)
            self.assertIsNotNone(row, key)
            self.assertEqual(len(re.findall(r'"(?:[^"\\]|\\.)*"', row.group(1))), 3, key)


if __name__ == "__main__":
    unittest.main()
