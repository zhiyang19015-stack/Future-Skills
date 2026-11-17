"""The stage 6 evaluation: personas, labels and the scoring rules (scripts/eval.py)."""

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import eval as ev  # noqa: E402
import eval_personas  # noqa: E402


def occ_ids() -> dict:
    with open(ROOT / "data" / "occupations.csv", encoding="utf-8", newline="") as f:
        return {r["occ_id"]: int(r["job_zone"]) for r in csv.DictReader(f)}


class PersonasTest(unittest.TestCase):
    def test_forty_people_ten_per_group(self):
        people = eval_personas.people()
        self.assertEqual(len(people), 40)
        for g in ("student", "working", "switcher", "jobseeker"):
            self.assertEqual(sum(p["group"] == g for p in people), 10, g)

    def test_held_out_set_is_apart_from_the_demo_people(self):
        demo = json.loads((ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8"))
        self.assertFalse({p["profile_id"] for p in demo} & {p["id"] for p in eval_personas.people()})

    def test_interest_rule(self):
        answers = eval_personas.interest_answers({"top": ["S", "I", "R"], "low": "E"})
        self.assertEqual(len(answers), 36)
        # the items cycle R I A S E C
        self.assertEqual(answers[:6], [4, 4, 2, 5, 1, 2])

    def test_profiles_use_known_ids(self):
        occ = occ_ids()
        for p in eval_personas.people():
            prof = eval_personas.app_profile(p)
            if prof.get("current_occupation"):
                self.assertIn(prof["current_occupation"], occ)
            self.assertIn(prof["kind"], ("student", "working", "switcher"))


class LabelsTest(unittest.TestCase):
    def setUp(self):
        if not eval_personas.LABELS.exists():
            self.skipTest("no labels yet")
        self.labels, self.digest = ev.labels_file()

    def test_every_person_is_labelled_by_the_rules(self):
        occ = occ_ids()
        for p in eval_personas.people():
            lab = self.labels[p["id"]]
            ok, bad = lab["acceptable"], lab["not_acceptable"]
            self.assertTrue(3 <= len(ok) <= 20, p["id"])
            self.assertLessEqual(len(bad), 15, p["id"])
            self.assertFalse(set(ok) & set(bad), p["id"])
            reach = p["profile"]["education_job_zone"] + p["profile"].get("study_levels", 0)
            for o in ok + bad:
                self.assertIn(o, occ, p["id"])
            for o in ok:
                self.assertLessEqual(occ[o], reach, f"{p['id']} {o}")
                self.assertNotEqual(o, p["profile"].get("current_occupation"), p["id"])

    def test_results_name_these_labels(self):
        res = ROOT / "docs" / "eval_results.json"
        if res.exists():
            self.assertEqual(json.loads(res.read_text(encoding="utf-8"))["labels_sha256"], self.digest)


class ScoringTest(unittest.TestCase):
    def test_wilson(self):
        self.assertEqual(ev.wilson(0, 0), (0.0, 0.0))
        lo, hi = ev.wilson(20, 40)
        self.assertTrue(34 < lo < 36 and 64 < hi < 66)

    def test_plan_checks(self):
        plan = [{"title": "PRDV102: Resume Writing", "url": "a", "cost_myr": 0, "language": "en", "skill_id": None},
                {"title": "Excel basics", "url": "b", "cost_myr": 0, "language": "ms", "skill_id": "x",
                 "skill_kind": "skill", "your_level": 4, "level_needed": 3},
                {"title": "Excel basics", "url": "b", "cost_myr": 0, "language": "ms", "skill_id": "y",
                 "skill_kind": "skill", "your_level": 1, "level_needed": 3},
                {"title": "Paid course", "url": "c", "cost_myr": 500, "language": "zh", "skill_id": None}]
        c = ev.plan_checks({"kind": "working", "plan": plan})
        self.assertEqual(c["job_search_for_working"], ["PRDV102: Resume Writing"])
        self.assertEqual(c["paid_in_plan"], ["Paid course"])
        self.assertEqual(c["already_have"], ["Excel basics"])
        self.assertEqual(c["duplicates"], 1)
        self.assertEqual((c["resources"], c["listed"], c["free"], c["non_english"]), (3, 4, 2, 2))
        self.assertEqual(ev.plan_checks({"kind": "student", "plan": plan[:1]})["should_not"], 0)

    def test_score_uses_the_moderate_first_move_and_slow_vs_fast(self):
        top = lambda *ids: [{"occ_id": i, "title": i} for i in ids]  # noqa: E731
        rec = {"id": "E01", "kind": "student", "error": None, "plan": [],
               "top": {"slow": top("a", "b"), "moderate": top("b", "c", "z"), "fast": top("c", "b")}}
        row = ev.score([rec], {"E01": {"acceptable": ["c"], "not_acceptable": ["z"]}})[0]
        self.assertFalse(row["first_ok"])
        self.assertTrue(row["top5_ok"])
        self.assertEqual(row["top5_bad"], ["z"])
        self.assertTrue(row["first_changed"])
        self.assertTrue(row["top5_set_changed"])


class ComparisonTest(unittest.TestCase):
    def test_v1_vs_v2_reads_the_evaluation(self):
        import v1_vs_v2
        if not (ROOT / "docs" / "eval_results.json").exists() or not v1_vs_v2.KEEP.exists():
            self.skipTest("no results yet")
        r = v1_vs_v2.build(None)
        text = v1_vs_v2.as_markdown(r)
        now = r["eval"]["versions"]["now"]["summary"]["all"]["first_ok"]
        self.assertIn(f"{now['pct']}% ({now['k']}/{now['n']})", text)
        self.assertEqual(r["catalogue"]["now"]["occupations"], 910)


if __name__ == "__main__":
    unittest.main()
