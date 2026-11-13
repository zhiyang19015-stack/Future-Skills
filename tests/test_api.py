import unittest

from helpers import ACCOUNTANT, CLERK, DATA, NURSE, get, post

import main

BASIC = {"education_job_zone": 4, "fields": {"13": 100}, "technologies": ["microsoft-excel"],
         "skills": {"2.A.1.e": 4, "2.C.1.c": 4}}


class TestReading(unittest.TestCase):
    def test_pages_and_lists(self):
        for path in ("/", "/static/app.js", "/api", "/api/health", "/api/fields", "/api/occupations",
                     "/api/technologies", "/api/elements", "/api/profiles", "/api/questionnaire", "/api/scenarios",
                     "/api/skillcheck?fields=29", "/api/explain/status", "/api/update"):
            status = main.dispatch("GET", path).status
            self.assertEqual(status, 200, path)

    def test_fields_and_occupations(self):
        _, fields = get("/api/fields")
        self.assertEqual(len(fields), 22)
        self.assertTrue(all(f["name_ms"] and f["name_zh"] for f in fields))
        _, health = get("/api/occupations?field=29")
        self.assertTrue(health and all(o["field_id"] == "29" for o in health))

    def test_radar(self):
        status, r = get("/api/radar?scenario=fast")
        self.assertEqual(status, 200)
        self.assertEqual(len(r["fields"]), 22)
        self.assertEqual(len(r["occupations"]), sum(f["occupations"] for f in r["fields"]))
        self.assertTrue(all(x["change"] >= y["change"] for x, y in zip(r["rising"], r["rising"][1:])))

    def test_one_occupation(self):
        status, r = get(f"/api/occupations/{NURSE}?scenario=slow")
        self.assertEqual(status, 200)
        self.assertEqual(set(r["outlooks"]), {"slow", "moderate", "fast"})
        self.assertEqual(r["licence"]["profession"], "Nurses and midwives")
        self.assertTrue(r["tasks"] and r["skills"] and r["sdg"])
        self.assertEqual(get("/api/occupations/00-0000.00")[0], 404)

    def test_bad_requests_are_400(self):
        for path, body in (("/api/match", {"fields": {"99": 100}}), ("/api/match", {"skills": {"2.A.1.a": 8}}),
                           ("/api/match", {"technologies": ["no-such-tool"]}), ("/api/match", {"scenario": "soon"}),
                           ("/api/match", {"adoption": 2}), ("/api/match", {"education_job_zone": 9}),
                           ("/api/match", {"current_occupation": "nope"}), ("/api/match", {"profile_id": "P99"}),
                           ("/api/match", {"top": 0}), ("/api/explain", {}), ("/api/explain", {"occ_id": NURSE, "lang": "fr"}),
                           ("/api/learn", {"occ_id": "nope"}), ("/api/jobad", {"text": "short"}),
                           ("/api/cv/summary", {"text": "x"}), ("/api/questionnaire/score", {"answers": [1]}),
                           ("/api/whatif", {}), ("/api/whatif", {"trend_changes": {"job_ads": {"5": 999}}})):
            status, out = post(path, body)
            self.assertEqual(status, 400, (path, body, out))
            self.assertIn("error", out)
        self.assertEqual(main.dispatch("POST", "/api/match", b"not json").status, 400)
        self.assertEqual(main.dispatch("DELETE", "/api/match").status, 405)


class TestThePersonsSteps(unittest.TestCase):
    def test_match(self):
        status, m = post("/api/match", {**BASIC, "top": 5})
        self.assertEqual(status, 200)
        self.assertEqual(len(m["results"]), 5)
        self.assertEqual(m["total_occupations"], len(DATA["occupations"]))
        first = m["results"][0]
        self.assertEqual(set(first["components"]), {"field", "interest", "skill", "outlook"})
        self.assertEqual(set(first["scenario_ranks"]), {"slow", "moderate", "fast"})
        self.assertIsNotNone(first["stability"])

    def test_a_working_person_sees_their_own_job(self):
        _, m = post("/api/match", {**BASIC, "kind": "working", "current_occupation": CLERK, "top": 3})
        self.assertEqual(m["current"]["occ_id"], CLERK)
        self.assertIn("current_occupation", m["current"]["flags"])

    def test_explain_learn_futures(self):
        status, e = post("/api/explain", {**BASIC, "occ_id": ACCOUNTANT, "lang": "zh"})
        self.assertEqual(status, 200)
        self.assertEqual(e["lang"], "zh")
        self.assertIn("to_raise", e)
        status, page = post("/api/learn", {**BASIC, "occ_id": ACCOUNTANT})
        self.assertEqual((status, page["role"]["occ_id"]), (200, ACCOUNTANT))
        status, f = post("/api/futures", {**BASIC, "top": 3})
        self.assertEqual(status, 200)
        self.assertEqual([c["id"] for c in f["scenarios"]], ["slow", "moderate", "fast"])

    def test_cv_and_job_ad(self):
        status, cv = post("/api/cv/summary", {"text": "Diploma in Accounting, 2020\n\nEXPERIENCE\nAccounts Assistant "
                                                      "at Contoh Sdn Bhd, using MS Excel and SAP."})
        self.assertEqual(status, 200)
        self.assertEqual(cv["education_job_zone"], 3)
        status, ad = post("/api/jobad", {"text": "Accounts executive wanted. Must know Microsoft Excel, SAP and "
                                                 "QuickBooks. Good English.", "technologies": ["microsoft-excel"]})
        self.assertEqual(status, 200)
        self.assertEqual([t["skill_id"] for t in ad["have"]], ["microsoft-excel"])
        self.assertIn("sap-software", [t["skill_id"] for t in ad["missing"]])

    def test_a_what_if_returns_before_and_after(self):
        status, w = post("/api/whatif", {**BASIC, "trend_changes": {"job_ads": {"2": -40}}})
        self.assertEqual(status, 200)
        self.assertTrue(w["roles"])
        self.assertTrue(w["before"] and w["after"])
        self.assertTrue(w["trend_data"]["what_if"])

    def test_sources(self):
        status, s = get("/api/sources")
        self.assertEqual(status, 200)
        names = " ".join(r["name"] for r in s["sources"])
        for expected in ("Anthropic Economic Index", "O*NET", "ESCO", "MyCOL", "DOSM", "arXiv"):
            self.assertIn(expected, names)


if __name__ == "__main__":
    unittest.main()
