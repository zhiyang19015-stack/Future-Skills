"""The Lab: ILO data, stress test, skill transfer map, decision lab, confidence challenge, missions, registry."""

import csv
import unittest

from helpers import CLERK, DATA, DEVELOPER, NURSE, ROOT, get, post

import challenge
import decision_lab
import ilo
import matching
import missions
import stress_test
import transfer


class TestILO(unittest.TestCase):
    def test_tables(self):
        t = ilo.tables()
        self.assertEqual(len(t["occupations"]), 427)
        self.assertEqual(sum(len(v) for v in t["tasks"].values()), 3265)
        for o in t["occupations"].values():
            self.assertTrue(0 <= o["mean_2025"] <= 1 and o["sd_2025"] >= 0)
            self.assertIn(o["gradient"], ilo.GRADIENT_ORDER)

    def test_most_occupations_reach_an_ilo_score(self):
        mapped = sum(1 for o in DATA["occupations"] if o["isco"] in ilo.tables()["occupations"])
        self.assertGreaterEqual(mapped, 850)

    def test_for_occupation_keeps_both_measures_apart(self):
        x = ilo.for_occupation(DATA["by_id"][CLERK], DATA)
        self.assertEqual(x["gradient"], "g4")
        self.assertIn("percentile_observed", x)
        self.assertIn("percentile_potential", x)
        self.assertEqual(x["disagree"], abs(x["percentile_gap"]) >= ilo.DIVERGENCE)


class TestStressTest(unittest.TestCase):
    def test_parameters_change_the_underlying_result(self):
        slow = stress_test.run(CLERK, DATA, {"adoption": 0.1})
        fast = stress_test.run(CLERK, DATA, {"adoption": 0.5})
        self.assertGreater(fast["summary"]["pressure"], slow["summary"]["pressure"])
        friction = stress_test.run(CLERK, DATA, {"adoption": 0.5, "friction": 0.9})
        self.assertLess(friction["summary"]["pressure"], fast["summary"]["pressure"])

    def test_changes_are_explained_one_at_a_time(self):
        r = stress_test.run(CLERK, DATA, {"adoption": 0.5, "demand_change": -30})
        inputs = {c["input"] for c in r["changes"]}
        self.assertEqual(inputs, {"adoption", "demand_change"})
        demand = next(c for c in r["changes"] if c["input"] == "demand_change")
        self.assertLess(demand["demand_change"], 0)        # job ads down -> demand down, through the real pipeline
        self.assertEqual(demand["pressure_change"], 0.0)   # demand does not touch the tasks
        self.assertEqual(stress_test.run(CLERK, DATA)["changes"], [])

    def test_ranges_categories_and_routes(self):
        r = stress_test.run(NURSE, DATA)
        self.assertAlmostEqual(sum(r["summary"]["mix"].values()), 100, delta=0.5)
        for t in r["tasks"]:
            self.assertLessEqual(t["pressure_low"], t["pressure"] + 1e-6)
            self.assertIn(t["category"], stress_test.CATEGORIES)
        self.assertTrue(1 <= len(r["routes"]) <= stress_test.ROUTES)
        self.assertEqual(set(r["scenarios"]), {"slow", "moderate", "fast"})
        self.assertLessEqual(r["sensitivity"]["outlook_low"], r["sensitivity"]["outlook_high"])

    def test_no_ilo_score_means_no_scenario_move(self):
        occ = next(o for o in DATA["occupations"] if o["isco"] not in ilo.tables()["occupations"]
                   and DATA["ai"]["tasks_by_occ"].get(o["occ_id"]))
        r = stress_test.run(occ["occ_id"], DATA, {"adoption": 0.9, "friction": 0})
        self.assertIsNone(r["ilo"])
        self.assertTrue(all(t["pressure"] == t["observed"] for t in r["tasks"]))

    def test_bad_input(self):
        with self.assertRaises(stress_test.StressError):
            stress_test.run(CLERK, DATA, {"friction": 2})
        with self.assertRaises(stress_test.StressError):
            stress_test.run("00-0000.00", DATA)

    def test_review_set_covers_the_groups(self):
        text = (ROOT / "data" / "review_occupations.csv").read_text(encoding="utf-8")
        rows = list(csv.DictReader(text.splitlines()))
        self.assertGreaterEqual(len(rows), 20)
        self.assertEqual({r["group"] for r in rows},
                         {"clerical", "professional", "service", "manufacturing", "health", "trades"})
        self.assertTrue(all(r["occ_id"] in DATA["by_id"] for r in rows))


class TestTransfer(unittest.TestCase):
    def test_routes_from_skills(self):
        person = {"kind": "working", "current_occupation": CLERK, "education_job_zone": 3, "technologies": []}
        m = transfer.map_for(person, DATA, CLERK, 0.25, 5)
        self.assertTrue(m["routes"])
        self.assertNotIn(CLERK, {r["occ_id"] for r in m["routes"]})
        scores = [r["score"] for r in m["routes"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        r = m["routes"][0]
        self.assertEqual(sum(r["counts"].values()), len(DATA["occ_elements"][r["occ_id"]]))
        self.assertTrue(0 <= r["coverage"] <= 100)
        w = transfer.TRANSFER_WEIGHTS
        self.assertAlmostEqual(r["score"], sum(w[k] * r["parts"][k] for k in w), delta=0.2)

    def test_evidence_sources_are_not_equal(self):
        person = {"kind": "student", "education_job_zone": 4, "technologies": [], "skills": {"2.A.1.c": 6.0}}
        occ = DATA["by_id"][DEVELOPER]
        self_rated = transfer.skill_groups(matching.prepare(person, DATA), occ, DATA, {"2.A.1.c": "self"})
        from_cv = transfer.skill_groups(matching.prepare(person, DATA), occ, DATA, {"2.A.1.c": "cv"})
        self.assertEqual(self_rated["coverage"], from_cv["coverage"])
        self.assertEqual(self_rated["evidence"], 0.0)
        self.assertGreater(from_cv["evidence"], 0.0)


class TestDecisionAndChallenge(unittest.TestCase):
    def setUp(self):
        self.aiman = matching.with_interest(next(p for p in __import__("json").loads(
            (ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8")) if p["profile_id"] == "P01"))

    def test_three_paths_and_limits(self):
        d = decision_lab.run(self.aiman, DATA, 0.25, 5, {"max_weeks": 4, "budget_myr": 0})
        self.assertEqual([o["path"] for o in d["options"]], ["stay", "adjacent", "change"])
        self.assertEqual(len({o["occ_id"] for o in d["options"]}), 3)
        self.assertNotEqual(d["options"][2]["field_id"], d["origin"]["field_id"])
        for o in d["options"]:
            time = next(c for c in o["checks"] if c["limit"] == "time")
            self.assertEqual(time["ok"], (o["training"]["weeks"] or 0) <= 4)
            self.assertIn("location", {c["limit"] for c in o["checks"]})
        relaxed = decision_lab.run(self.aiman, DATA, 0.25, 40, {"max_weeks": 520})
        self.assertLess(relaxed["options"][0]["training"]["weeks"], d["options"][0]["training"]["weeks"])

    def test_missing_wage_is_never_zero(self):
        d = decision_lab.run(self.aiman, DATA, 0.25, 5)
        for o in d["options"]:
            self.assertTrue(o["local"]["group_wage_myr"] is None or o["local"]["group_wage_myr"] > 0)

    def test_challenge_explains_the_gap(self):
        c = challenge.run(self.aiman, DATA, 0.25, "15-1253.00", DEVELOPER)
        self.assertAlmostEqual(sum(p["points"] or 0 for p in c["parts"]), c["gap"], delta=0.6)
        self.assertEqual(set(c["kinds"].values()) - {"user_input", "scenario_assumption", "observed",
                                                       "research_estimate"}, set())
        with self.assertRaises(challenge.ChallengeError):
            challenge.run(self.aiman, DATA, 0.25, DEVELOPER, DEVELOPER)


class TestMissions(unittest.TestCase):
    def test_catalogue_ids_exist(self):
        res = {r["resource_id"] for r in DATA["resources"]}
        for m in missions.catalogue().values():
            for t in m["targets"]:
                kind, _, sid = t.partition(":")
                self.assertIn(sid, DATA["elements"] if kind == "element" else DATA["technologies"], t)
            self.assertTrue(set(m["resource_ids"]) <= res, m["mission_id"])
            self.assertTrue(m["done_when"] and m["evidence"] and m["hours"] > 0)

    def test_finished_mission_counts_as_evidence(self):
        before = post("/api/match", {"education_job_zone": 4, "fields": {"13": 100}, "include": ["13-2011.00"]})[1]
        after = post("/api/match", {"education_job_zone": 4, "fields": {"13": 100}, "include": ["13-2011.00"],
                                    "missions_done": ["M01", "M08"]})[1]
        skill = lambda r: next(m for m in r["results"] if m["occ_id"] == "13-2011.00")["components"]["skill"]["score"]  # noqa: E731
        self.assertIsNone(skill(before))
        self.assertGreater(skill(after), 0)
        self.assertEqual(post("/api/missions", {"occ_id": CLERK, "missions_done": ["nope"]})[0], 400)


class TestLabAPI(unittest.TestCase):
    def test_endpoints(self):
        status, r = post("/api/lab/stress", {"occ_id": CLERK, "scenario": "fast", "friction": 0.2, "demand_change": 10})
        self.assertEqual(status, 200)
        self.assertEqual(r["params"]["adoption"], 0.5)
        self.assertEqual(post("/api/lab/stress", {"occ_id": CLERK, "friction": "x"})[0], 400)
        self.assertEqual(post("/api/lab/transfer", {"origin": NURSE})[0], 200)
        self.assertEqual(post("/api/lab/transfer", {})[0], 400)
        self.assertEqual(post("/api/lab/decide", {"profile_id": "P01", "limits": {"max_weeks": 26}})[0], 200)
        self.assertEqual(post("/api/lab/decide", {"profile_id": "P01", "limits": {"max_weeks": -1}})[0], 400)
        self.assertEqual(post("/api/lab/challenge", {"profile_id": "P01", "occ_id": DEVELOPER, "other_id": NURSE})[0], 200)
        status, m = post("/api/missions", {"occ_id": CLERK})
        self.assertEqual(status, 200)
        self.assertTrue(m["missions"])
        self.assertEqual(get("/api/missions")[0], 200)

    def test_registry_and_sources(self):
        status, r = get("/api/metrics")
        self.assertEqual(status, 200)
        fields = {"metric_id", "unit", "geography", "taxonomy", "source_name", "source_url", "publication_date",
                  "observation_period", "method", "confidence", "limitations", "transformation", "kind"}
        for m in r["metrics"]:
            self.assertTrue(fields <= set(m), m["metric_id"])
            self.assertIn(m["kind"], r["kinds"])
            self.assertNotEqual(m["publication_date"], "live")
        self.assertIn("ilo_wp140", {s["id"] for s in get("/api/sources")[1]["sources"]})
        self.assertIsNotNone(get(f"/api/occupations/{CLERK}")[1]["ilo"])


if __name__ == "__main__":
    unittest.main()
