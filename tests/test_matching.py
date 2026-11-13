import unittest

from helpers import ACCOUNTANT, CLERK, DATA, NURSE, sample

import matching


def ranked(profile, **kw):
    return matching.rank(profile, DATA, **kw)


class TestFieldFit(unittest.TestCase):
    def test_a_chosen_field_leads(self):
        fit = matching.field_fit(matching.prepare({"fields": {"29": 100, "15": 0}}, DATA), DATA)
        self.assertEqual(fit["best"], "29")
        rows = {f["id"]: f for f in fit["fields"]}
        self.assertEqual(rows["15"]["fit"], 0.0)
        self.assertIsNone(rows["23"]["fit"])  # no answer for it: not scored, never 0
        self.assertEqual(fit["sources_used"], ["choice"])

    def test_the_current_job_is_evidence_for_its_field(self):
        fit = matching.field_fit(matching.prepare({"current_occupation": CLERK}, DATA), DATA)
        row = next(f for f in fit["fields"] if f["id"] == "43")
        self.assertEqual(row["parts"]["experience"]["score"], matching.CURRENT_FIELD)
        self.assertIn("you work as", row["explain"])


class TestScore(unittest.TestCase):
    def test_interest_fit_is_a_correlation(self):
        nurse = DATA["by_id"][NURSE]
        same = {k: nurse["interest_scores"][k] for k in matching.RIASEC}
        opposite = {k: 8 - v for k, v in same.items()}
        self.assertEqual(matching.interest_fit(same, nurse)[0], 100.0)
        self.assertEqual(matching.interest_fit(opposite, nurse)[0], 0.0)
        self.assertIsNone(matching.interest_fit({k: 3 for k in matching.RIASEC}, nurse)[0])

    def test_only_the_skill_parts_a_person_answered_count(self):
        occ = DATA["by_id"][ACCOUNTANT]
        only_tools = matching.prepare({"technologies": ["microsoft-excel"]}, DATA)
        parts = matching.skill_score(only_tools, occ, DATA, None)["parts"]
        self.assertEqual((parts["skill"], parts["knowledge"]), (None, None))
        self.assertIsNotNone(parts["technology"])
        nothing = matching.skill_score(matching.prepare({}, DATA), occ, DATA, None)
        self.assertIsNone(nothing["score"])

    def test_more_skill_never_lowers_the_fit(self):
        occ = DATA["by_id"][ACCOUNTANT]
        low = matching.prepare({"skills": {"2.C.1.c": 2.0, "2.A.1.e": 2.0}}, DATA)
        high = matching.prepare({"skills": {"2.C.1.c": 6.0, "2.A.1.e": 6.0}}, DATA)
        self.assertGreater(matching.skill_score(high, occ, DATA, None)["score"],
                           matching.skill_score(low, occ, DATA, None)["score"])

    def test_education_flags(self):
        diploma = {"education_job_zone": 3}
        self.assertEqual(matching.education_flags({"job_zone": 5}, diploma), ["needs_extra_education"])
        self.assertEqual(matching.education_flags({"job_zone": 1}, diploma), ["below_education"])
        self.assertEqual(matching.education_flags({"job_zone": 3}, diploma), [])

    def test_doing_a_job_counts_as_having_its_skills(self):
        p = matching.prepare({"current_occupation": CLERK, "skills": {"2.A.1.e": 7.0}}, DATA)
        need = {e: lv for e, _, lv, _ in DATA["occ_elements"][CLERK]}
        self.assertEqual(p["skills"]["2.A.1.e"], 7.0)  # a level the person gave is never lowered
        self.assertTrue(all(p["skills"][e] >= lv for e, lv in need.items()))


class TestRanking(unittest.TestCase):
    def test_every_occupation_is_ranked_and_the_flagged_ones_come_last(self):
        rows = ranked({"education_job_zone": 3, "fields": {"29": 100}})
        self.assertEqual(len(rows), len(DATA["occupations"]))
        last = [r["_parts"]["last"] for r in rows]
        self.assertEqual(last, sorted(last))

    def test_a_picked_un_goal_adds_points_and_keeps_the_cost_visible(self):
        base = {r["occ_id"]: r for r in ranked({"fields": {"29": 100}})}
        goal = {r["occ_id"]: r for r in ranked({"fields": {"29": 100}, "sdg_goals": ["3"]})}
        nurse = goal[NURSE]["sdg_choice"]
        self.assertEqual(nurse["bonus"], matching.SDG_BONUS["direct"])
        self.assertEqual(nurse["total_without"], base[NURSE]["total"])

    def test_the_demo_people_get_sensible_first_matches(self):
        first = {}
        for pid in ("P01", "P02", "P03", "P04"):
            out = matching.match_person(sample(pid), DATA, top=3, futures=50)
            first[pid] = out["results"][0]
            self.assertEqual(len(out["results"]), 3)
            self.assertIsNotNone(out["results"][0]["stability"])
        self.assertIn(first["P01"]["field_id"], ("29", "31", "21"))
        self.assertIn(first["P02"]["field_id"], ("13", "43"))
        self.assertEqual(first["P03"]["field_id"], "17")

    def test_the_learning_path_is_free_and_lists_each_link_once(self):
        m = matching.match_person(sample("P02"), DATA, top=1, futures=0)["results"][0]
        steps = m["pathway"]["steps"]
        self.assertTrue(steps)
        self.assertEqual(len({s["url"] for s in steps}), len(steps))
        self.assertTrue(all(not s["cost_myr"] for s in steps))


if __name__ == "__main__":
    unittest.main()
