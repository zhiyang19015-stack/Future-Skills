"""What the scenarios and a piece of simulated news change for one person, and the study setting
that decides which occupations stay in their list."""
import unittest

from helpers import ACCOUNTANT, CLERK, DATA, get, post, sample

import main
import matching
import scenario_report
import whatif

DESIGNER = "27-1024.00"


def moves(profile_id: str, top: int = 5) -> list[dict]:
    """A demo person's first occupations, without the job they do now."""
    status, m = post("/api/match", {"profile_id": profile_id, "top": top})
    assert status == 200, m
    return [r for r in m["results"] if "current_occupation" not in r["flags"]][:top]


class TestStudyLevels(unittest.TestCase):
    def test_within_reach_is_flagged_not_set_aside(self):
        degree_job = DATA["by_id"][ACCOUNTANT]
        self.assertEqual(degree_job["job_zone"], 4)
        flags = lambda zone, study: matching.education_flags(degree_job, {"education_job_zone": zone, "study_levels": study})  # noqa: E731
        self.assertEqual(flags(3, 0), ["needs_extra_education"])
        self.assertEqual(flags(3, 1), ["more_study"])
        self.assertEqual(flags(2, 1), ["needs_extra_education"])
        self.assertEqual(flags(2, 2), ["more_study"])
        self.assertEqual(flags(4, 2), [])
        self.assertEqual(matching.education_flags(degree_job, {"education_job_zone": 3}), ["needs_extra_education"])
        self.assertEqual(matching.study_reach({"study_levels": 9}), matching.MAX_STUDY_LEVELS)

    def test_an_occupation_within_reach_stays_in_the_ranking(self):
        place = lambda rows: next(i for i, m in enumerate(rows) if m["occ_id"] == ACCOUNTANT)  # noqa: E731
        at_her_level = matching.rank({**sample("P02"), "study_levels": 0}, DATA)
        one_level_up = matching.rank(sample("P02"), DATA)  # the demo person would study one level up
        self.assertGreater(place(at_her_level), 100)        # after everything open at a diploma
        self.assertLess(place(one_level_up), 10)
        found = one_level_up[place(one_level_up)]
        self.assertIn("more_study", found["flags"])
        self.assertFalse(found["_parts"]["last"])

    def test_the_api_checks_it(self):
        for bad in (3, -1, 1.5, "1", True):
            self.assertEqual(post("/api/match", {"study_levels": bad})[0], 400, bad)
        status, body = post("/api/match", {"education_job_zone": 3, "study_levels": 1, "fields": {"13": 100}, "top": 5})
        self.assertEqual(status, 200)
        self.assertTrue(any("more_study" in m["flags"] for m in body["results"]))

    def test_the_demo_people_get_the_moves_their_stories_ask_for(self):
        siti = moves("P02")  # "move up to a professional finance role"
        self.assertTrue(all(m["field_id"] == "13" for m in siti), [m["title"] for m in siti])
        self.assertIn(ACCOUNTANT, [m["occ_id"] for m in siti])
        mei = moves("P04")   # "switch into design or marketing"
        self.assertIn(DESIGNER, [m["occ_id"] for m in mei])
        self.assertTrue(all("more_study" in m["flags"] for m in mei), [m["title"] for m in mei])

    def test_the_learning_page_carries_the_flag(self):
        status, page = post("/api/learn", {"profile_id": "P02", "occ_id": ACCOUNTANT})
        self.assertEqual(status, 200)
        self.assertIn("more_study", page["flags"])
        self.assertEqual(get(f"/api/learn/{ACCOUNTANT}")[1]["flags"], [])


class TestLearnNext(unittest.TestCase):
    def test_a_tool_ai_is_taking_over_follows_the_others(self):
        m = matching.match_person(sample("P05"), DATA, top=3, futures=0)["results"][0]
        tools = [t for t in m["skill_detail"]["tech_missing"] if t["category"] not in matching.GENERAL_TOOLS]
        declining = [t["ai"]["status"] == "declining" for t in tools]
        self.assertTrue(tools)
        self.assertEqual(declining, sorted(declining))


class TestScenarioVerdict(unittest.TestCase):
    @staticmethod
    def tops(fast: list[tuple[str, float]]) -> dict:
        rows = lambda pairs: [{"occ_id": o, "title": o, "total": v, "ai_share": 20.0} for o, v in pairs]  # noqa: E731
        slow = [("a", 80.0), ("b", 70.0), ("c", 60.0)]
        return {"slow": rows(slow), "moderate": rows(slow), "fast": rows(fast)}

    def test_three_plain_cases(self):
        ref = {"role_ai_share": 10.0}
        same = main.scenario_verdict(self.tops([("a", 78.5), ("b", 70.0), ("c", 60.0)]), ref)
        self.assertEqual((same["kind"], same["largest_move"]), ("same", 1.5))
        self.assertEqual(main.scenario_verdict(self.tops([("a", 80.0), ("c", 66.0), ("b", 65.0)]), ref)["kind"], "top3")
        top = main.scenario_verdict(self.tops([("b", 75.0), ("a", 74.0), ("c", 60.0)]), ref)
        self.assertEqual((top["kind"], top["slow_first"]["occ_id"], top["fast_first"]["occ_id"]), ("top", "a", "b"))
        self.assertEqual(top["ai_share_reference"], 10.0)
        self.assertIsNone(main.scenario_verdict({"slow": self.tops([])["slow"], "moderate": [], "fast": []}, ref))

    def test_the_matches_page_and_the_futures_page_agree(self):
        for profile_id in ("P02", "P01"):
            verdict = post("/api/match", {"profile_id": profile_id, "top": 3})[1]["verdict"]
            futures = post("/api/futures", {"profile_id": profile_id, "top": 3})[1]
            self.assertEqual(futures["top_changes"], verdict["kind"] == "top", profile_id)
            self.assertEqual(futures["top3_changes"], verdict["kind"] != "same", profile_id)
            self.assertEqual(verdict["slow_first"]["occ_id"], futures["scenarios"][0]["top"][0]["occ_id"])

    def test_the_demo_people_show_both_answers(self):
        """A guard on the demo set, not on the model: the people offered on the home page must keep
        showing a list that changes with the scenario and a list that holds. If a data update breaks
        this, choose other demo people; the model is never tuned to make a ranking flip."""
        people = scenario_report.report(DATA)["people"]
        changed = [p["name"] for p in people if p["top_order_changed"]]
        self.assertGreaterEqual(len(changed), 3, changed)
        self.assertGreaterEqual(len(people) - len(changed), 1)
        for p in people:
            if not p["top_set_changed"]:
                self.assertTrue(p["why_unchanged"], p["name"])  # a list that holds says why


class TestNewsForAPerson(unittest.TestCase):
    def publish(self, news_id: str, person: str) -> dict:
        item = next(n for n in whatif.news() if n["id"] == news_id)
        status, result = post("/api/whatif", {"profile_id": person, "trend_changes": item["changes"]})
        self.assertEqual(status, 200, result)
        return result

    def test_one_headline_leads_and_each_names_a_real_demo_person(self):
        news = whatif.news()
        people = {p["profile_id"] for p in get("/api/profiles")[1]}
        self.assertEqual([n["id"] for n in news if n["lead"]], [whatif.LEAD_NEWS])
        named = [n for n in news if n["person"]]
        self.assertGreaterEqual(len(named), 3)
        self.assertTrue(all(n["person"] in people for n in named))
        self.assertTrue(next(n for n in news if n["lead"])["person"])

    def test_the_lead_story_is_told_through_her_own_job(self):
        you = self.publish(whatif.LEAD_NEWS, "P02")["you"]
        job = you["subject"]
        self.assertEqual((you["subject_kind"], job["occ_id"]), ("current", CLERK))
        self.assertTrue(job["touched"])
        self.assertGreaterEqual(job["tasks_moved"], 3)
        self.assertLessEqual(len(job["moved"]), whatif.TASKS_SHOWN)
        self.assertTrue(all(t["after"] - t["before"] >= whatif.TASK_MOVE for t in job["moved"]))
        importance = [t["importance"] for t in job["moved"]]
        self.assertEqual(importance, sorted(importance, reverse=True))  # the most important task first
        self.assertGreater(job["ai_share"]["after"], job["ai_share"]["before"])
        self.assertLess(job["outlook"]["after"], job["outlook"]["before"])
        self.assertIn("intuit-quickbooks", [t["skill_id"] for t in you["tools"]])
        self.assertTrue(you["reached"])
        self.assertTrue(all(r["tasks_moved"] and r["rank"]["before"] for r in you["reached"]))

    def test_every_named_headline_reaches_its_person(self):
        for item in whatif.news():
            if item["person"]:
                you = self.publish(item["id"], item["person"])["you"]
                self.assertTrue(you["subject"]["tasks_moved"] or you["reached"], item["id"])

    def test_a_student_is_read_through_their_first_match(self):
        result = self.publish("clinical_scribes", "P01")
        you = result["you"]
        self.assertEqual(you["subject_kind"], "top")
        self.assertEqual(you["subject"]["occ_id"], result["before"][0]["occ_id"])
        self.assertEqual(you["first"]["before"]["occ_id"], result["before"][0]["occ_id"])

    def test_news_about_other_work_leaves_the_job_untouched(self):
        job = self.publish("ai_tutors", "P02")["you"]["subject"]  # an accounts assistant, a headline about teaching
        self.assertEqual(job["tasks_moved"], 0)
        self.assertFalse(job["touched"])
        self.assertEqual(job["moved"], [])


if __name__ == "__main__":
    unittest.main()
