"""The evidence grade, career routes, the team view and the scenario regression report."""
import unittest
from datetime import date, timedelta

from helpers import DATA, DEVELOPER, get, post, sample

import evidence
import matching
import scenario_report
import team

QA = "15-1253.00"


class TestEvidenceGrade(unittest.TestCase):
    def test_every_occupation_gets_a_grade_with_three_reasons(self):
        for occ in DATA["occupations"]:
            g = evidence.occupation_grade(occ, DATA)
            self.assertIn(g["grade"], "ABC")
            self.assertEqual([c["check"] for c in g["checks"]], ["ai_usage", "mapping", "freshness"])
            self.assertEqual(g["points"], sum(c["points"] for c in g["checks"]))
            self.assertTrue(all(0 <= c["points"] <= 2 for c in g["checks"]))

    def test_the_grade_follows_the_evidence(self):
        grades = {o["occ_id"]: evidence.occupation_grade(o, DATA) for o in DATA["occupations"]}
        thin = [o for o in DATA["occupations"] if DATA["ai"]["roles"][o["occ_id"]]["thin_evidence"]
                and DATA["ai"]["roles"][o["occ_id"]]["prior_basis"] == "field" and o["isco_basis"] in ("broad", "none")]
        self.assertTrue(thin)
        self.assertTrue(all(grades[o["occ_id"]]["grade"] == "C" for o in thin))  # at most 2 points, from freshness
        self.assertEqual(len({g["grade"] for g in grades.values()}), 3)  # the grade tells occupations apart

    def test_old_data_lowers_the_grade(self):
        occ = DATA["by_id"][QA]
        newest = max(date.fromisoformat(DATA["ai"]["source"]["economic_index"]["release_date"]),
                     date.fromisoformat(DATA["demand"]["computed_date"]))
        now = evidence.occupation_grade(occ, DATA, today=newest)
        later = evidence.occupation_grade(occ, DATA, today=newest + timedelta(days=evidence.FRESH_AI_DAYS + 400))
        self.assertEqual(later["checks"][2]["points"], 0)
        self.assertEqual(later["checks"][2]["reason"], "stale")
        self.assertLess(later["points"], now["points"])

    def test_it_is_on_the_occupation_page_and_the_sources_page(self):
        _, occ = get(f"/api/occupations/{QA}")
        self.assertIn(occ["evidence"]["grade"], "ABC")
        _, src = get("/api/sources")
        self.assertEqual(src["evidence"]["fresh_ai_days"], evidence.FRESH_AI_DAYS)


class TestRoutes(unittest.TestCase):
    def test_routes_are_related_open_and_within_reach(self):
        result = matching.match_person(sample("P05"), DATA, top=3, futures=0, include=[QA])
        for m in result["results"]:
            r = m["routes"]
            self.assertLessEqual(r["open"], r["related"])
            self.assertLessEqual(len(r["routes"]), matching.ROUTES_SHOWN)
            for route in r["routes"]:
                self.assertIn(route["occ_id"], DATA["related"][m["occ_id"]])
                self.assertNotEqual(route["status"], "declining")
                self.assertGreaterEqual(route["total"], m["total"] - matching.ROUTE_REACH)

    def test_the_working_persona_sees_their_own_job(self):
        status, m = post("/api/match", {"profile_id": "P05", "top": 3})
        self.assertEqual(status, 200)
        self.assertEqual(m["current"]["occ_id"], QA)
        self.assertTrue(all("evidence" in r and "routes" in r for r in m["results"]))


class TestTeamView(unittest.TestCase):
    def test_the_fictional_team(self):
        status, v = get("/api/team?scenario=fast")
        self.assertEqual(status, 200)
        self.assertTrue(v["team"]["synthetic"])
        self.assertEqual(v["team"]["people"], sum(r["headcount"] for r in v["roles"]))
        self.assertEqual(sum(v["counts"].values()), v["team"]["people"])
        for r in v["roles"]:
            self.assertEqual(set(r["statuses"]), {"slow", "moderate", "fast"})
            if r["status"] != "declining":
                self.assertIsNone(r["move"])
            if r["move"]:  # a move is adjacent, not declining, and its courses carry a checked date
                self.assertIn(r["move"]["occ_id"], team.adjacent(DATA["by_id"][r["occ_id"]], DATA))
                self.assertNotEqual(r["move"]["status"], "declining")
                self.assertTrue(all(c["url"].startswith("http") and c["verified_date"] for c in r["move"]["courses"]))
        moving = [r for r in v["roles"] if r["move"]]
        self.assertEqual(v["budget"]["people"], sum(r["headcount"] for r in moving))
        self.assertAlmostEqual(v["budget"]["person_hours"], sum(r["headcount"] * r["move"]["hours"] for r in moving), 1)
        self.assertTrue(all(len(row["gaps"]) == len(v["heatmap"]["skills"]) for row in v["heatmap"]["rows"]))
        declining = [r["title"] for r in v["roles"] if r["status"] == "declining" and not r["move"]]
        self.assertEqual(v["declining_without_move"], declining)

    def test_your_own_team_and_bad_teams(self):
        status, v = post("/api/team", {"members": [{"occ_id": DEVELOPER, "headcount": 2}, {"occ_id": DEVELOPER}],
                                       "scenario": "slow"})
        self.assertEqual(status, 200)
        self.assertEqual((len(v["roles"]), v["team"]["people"]), (1, 3))
        self.assertFalse(v["team"]["synthetic"])
        for body in ({}, {"members": []}, {"members": [{"occ_id": "nope"}]},
                     {"members": [{"occ_id": DEVELOPER, "headcount": 0}]},
                     {"members": [{"occ_id": DEVELOPER}], "hours_per_week": 99}):
            self.assertEqual(post("/api/team", body)[0], 400, body)

    def test_a_member_is_a_job_and_nothing_personal(self):
        profile = team.member_profile(DATA["by_id"][DEVELOPER], 5)
        self.assertEqual(set(profile), {"profile_id", "kind", "current_occupation", "education_job_zone",
                                        "technologies", "fields", "hours_per_week"})


class TestScenarioReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = scenario_report.report(DATA)

    def test_it_covers_every_demo_person(self):
        self.assertEqual({p["profile_id"] for p in self.report["people"]}, {"P01", "P02", "P03", "P04", "P05"})

    def test_scenarios_move_the_numbers_they_are_meant_to(self):
        """Faster adoption lowers the outlook of an occupation handed to AI more than average and
        raises one handed over less; an occupation at the average does not move."""
        ref = DATA["ai"]["reference"]["role_ai_share"]
        seen = 0
        for person in self.report["people"]:
            for m in person["moves"]:
                occ = DATA["by_id"][m["occ_id"]]
                builder = DATA["ai"]["roles"][m["occ_id"]]["builder_share"]
                if builder:  # building AI pulls the other way; the sign is not fixed
                    continue
                seen += 1
                if m["ai_share"] > ref:
                    self.assertLessEqual(m["outlook_move"], 0, occ["title"])
                else:
                    self.assertGreaterEqual(m["outlook_move"], 0, occ["title"])
        self.assertGreater(seen, 5)

    def test_an_unchanged_top_is_explained_not_forced(self):
        for person in self.report["people"]:
            if person["top_set_changed"]:
                self.assertIsNone(person["why_unchanged"])
            else:  # a stable ranking is a valid result and comes with its reason
                self.assertTrue(person["why_unchanged"])
        self.assertIn("No ranking is required to change", scenario_report.as_markdown(self.report))


if __name__ == "__main__":
    unittest.main()
