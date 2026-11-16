"""Stage 2, credibility: no ranking for a blank profile, Foundations by status, the courses not in
English, and the ILO research estimate as a second check on every occupation's AI share."""
import csv
import re
import unittest

from helpers import DATA, DEVELOPER, ROOT, post

import evidence
import ilo
import learning
import main
import matching
import outlook

STATIC = ROOT / "src" / "static"
JOB_SEARCH = {"R060", "R061"}  # PRDV102 Resume Writing, PRDV103 Interviewing Skills


def first_move(profile_id: str) -> str:
    _, m = post("/api/match", {"profile_id": profile_id})
    return next(x["occ_id"] for x in m["results"] if main.listed(x))


class TestBlankProfile(unittest.TestCase):
    def test_an_empty_body_ranks_nothing_and_asks_for_the_profile(self):
        status, m = post("/api/match", {})
        self.assertEqual(status, 200)
        self.assertEqual(m["results"], [])
        self.assertEqual(m["ranking"], [])
        self.assertEqual(m["needs_input"]["code"], "blank_profile")
        self.assertIn("profile", m["needs_input"]["message"])

    def test_defaults_alone_are_still_blank(self):
        for body in ({"education_job_zone": 4}, {"kind": "working"}, {"technologies": []}, {"fields": {}},
                     {"scenario": "fast", "hours_per_week": 10}):
            status, m = post("/api/match", body)
            self.assertEqual((status, m["results"]), (200, []), body)

    def test_one_answer_is_enough_to_rank(self):
        for body in ({"fields": {"15": 100}}, {"technologies": ["python"]}, {"skills": {"2.A.1.a": 4}},
                     {"kind": "working", "current_occupation": DEVELOPER}, {"profile_id": "P05"}):
            status, m = post("/api/match", body)
            self.assertEqual(status, 200, body)
            self.assertTrue(m["results"], body)
            self.assertNotIn("needs_input", m)

    def test_futures_also_ranks_nothing_for_a_blank_profile(self):
        status, f = post("/api/futures", {})
        self.assertEqual(status, 200)
        self.assertEqual(f["needs_input"]["code"], "blank_profile")
        self.assertTrue(all(c["top"] == [] for c in f["scenarios"]))
        self.assertEqual(f["moves"], [])

    def test_the_message_is_in_all_three_languages(self):
        text = (STATIC / "i18n.js").read_text(encoding="utf-8")
        for key in ("match.blank", "match.blank.h1"):
            row = re.search(r'"%s": \[(.*)\],' % re.escape(key), text)
            self.assertIsNotNone(row, key)
            self.assertEqual(len(re.findall(r'"((?:[^"\\]|\\.)*)"', row.group(1))), 3, key)
        self.assertNotIn('"match.empty"', text)  # the old note said the ranking used the outlook only
        for page in ("explore.js", "futures.js"):
            self.assertIn("needs_input", (STATIC / page).read_text(encoding="utf-8"), page)


class TestFoundationsByStatus(unittest.TestCase):
    def ids(self, page):
        return {r["id"] for r in page["stages"][0]["resources"]}

    def test_people_in_work_get_no_job_search_courses(self):
        for pid in ("P05", "P02"):  # Aiman, Siti Hajar: both in work
            _, page = post("/api/learn", {"profile_id": pid, "occ_id": first_move(pid)})
            self.assertEqual(page["stages"][0]["kind"], "working")
            self.assertFalse(self.ids(page) & JOB_SEARCH, pid)
            self.assertEqual(len(page["stages"][0]["left_out"]), 2)

    def test_students_and_switchers_keep_them(self):
        for kind in ("student", "switcher", None):
            page = learning.page(DEVELOPER, DATA, kind=kind)
            self.assertTrue(JOB_SEARCH <= self.ids(page), kind)
            self.assertEqual(page["stages"][0]["left_out"], [])

    def test_the_status_decides_and_nothing_else_moves(self):
        working = learning.page(DEVELOPER, DATA, kind="working")
        student = learning.page(DEVELOPER, DATA, kind="student")
        self.assertEqual(self.ids(student) - self.ids(working), JOB_SEARCH)
        self.assertEqual(working["skills"], student["skills"])

    def test_the_job_search_courses_are_filed_for_job_seekers(self):
        with (ROOT / "data" / "learning_resources.csv").open(encoding="utf-8", newline="") as f:
            rows = {r["resource_id"]: r for r in csv.DictReader(f)}
        self.assertTrue(all(rows[r]["targets"] == "jobseeker" for r in JOB_SEARCH))


class TestCoursesNotInEnglish(unittest.TestCase):
    def rows(self):
        with (ROOT / "data" / "learning_resources.csv").open(encoding="utf-8", newline="") as f:
            return [r for r in csv.DictReader(f) if r["language"] != "en"]

    def test_each_has_a_provider_free_hours_a_source_and_a_checked_date(self):
        rows = self.rows()
        self.assertEqual({r["resource_id"] for r in rows}, {"R070", "R071", "R072"})
        for r in rows:
            self.assertEqual(r["language"], "zh")
            self.assertEqual(r["provider"], "Microsoft Learn")
            self.assertTrue(r["url"].startswith("https://learn.microsoft.com/zh-cn/training/"), r["url"])
            self.assertGreater(float(r["duration_hours"]), 0)
            self.assertEqual(r["cost_myr"], "0")
            self.assertTrue(r["source_url"].startswith("https://learn.microsoft.com/api/catalog/"))
            self.assertTrue(r["verified_date"])

    def test_they_reach_the_demo_paths_and_say_their_language(self):
        _, page = post("/api/learn", {"profile_id": "P05", "occ_id": first_move("P05")})  # Aiman
        langs = {r["id"]: r["language"] for s in page["stages"] for r in s["resources"]}
        langs.update({r["id"]: r["language"] for s in page["skills"] for r in s["resources"]})
        self.assertEqual({k for k, v in langs.items() if v != "en"}, {"R070", "R071", "R072"})
        self.assertIn('"path.lang.zh"', (STATIC / "i18n.js").read_text(encoding="utf-8"))


class TestSecondSource(unittest.TestCase):
    def test_every_occupation_gets_one_verdict(self):
        c = ilo.coverage(DATA)
        self.assertEqual(c["confirmed"] + c["disagree"] + c["one_source"], len(DATA["occupations"]))
        self.assertGreater(c["confirmed"], 0)
        self.assertGreater(c["disagree"], 0)

    def test_the_verdict_is_the_labs_divergence_rule(self):
        for occ in DATA["occupations"][:200]:
            a = ilo.agreement(occ, DATA)
            if a["verdict"] == "one_source":
                self.assertIsNone(a["gap"])
                continue
            self.assertEqual(a["verdict"] == "disagree", abs(a["gap"]) >= ilo.DIVERGENCE)
            full = ilo.for_occupation(occ, DATA)
            self.assertEqual(full["disagree"], a["verdict"] == "disagree")

    def test_the_check_changes_no_number_of_the_outlook(self):
        for occ in DATA["occupations"][:100]:
            o = outlook.role_outlook(occ, DATA, 0.25)
            self.assertIn(o["second_source"]["verdict"], ilo.VERDICTS)
            s = outlook.role_signals(occ, DATA)
            v = outlook.outlook_value(s["demand"], s["ai_share"], s["builder"], s["tempo"], 0.25,
                                      DATA["ai"]["reference"], thin=s["thin"])
            self.assertEqual(o["outlook"], round(v["outlook"], 1))

    def test_sources_that_disagree_cap_the_grade_at_b(self):
        capped = 0
        for occ in DATA["occupations"]:
            g = evidence.occupation_grade(occ, DATA)
            verdict = g["checks"][3]["reason"]
            if verdict == "disagree":
                self.assertIn(g["grade"], "BC")
            if g["capped"]:
                capped += 1
                self.assertEqual((verdict, g["grade"]), ("disagree", "B"))
                self.assertGreaterEqual(g["points"], 5)
        self.assertGreater(capped, 0)

    def test_the_radar_flags_each_row(self):
        payload = main.radar_payload(matching.load_data(), "moderate", outlook.adoption_of("moderate"))
        self.assertTrue(all(x["second_source"] in ilo.VERDICTS for x in payload["rising"] + payload["declining"]))


if __name__ == "__main__":
    unittest.main()
