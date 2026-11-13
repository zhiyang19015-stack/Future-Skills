"""The parts of step 1: the skills check, the interest questionnaire and the CV reader."""
import base64
import io
import unittest
import zipfile

from helpers import CLERK, DATA, ROOT

import cv_reader
import interest
import skillcheck


class TestSkillCheck(unittest.TestCase):
    def test_it_asks_what_the_chosen_fields_need_most(self):
        health = skillcheck.plan(DATA, ["29"])
        office = skillcheck.plan(DATA, ["43"])
        self.assertEqual(len(health["questions"]), skillcheck.SKILLS_ASKED + skillcheck.KNOWLEDGE_ASKED)
        health_knowledge = [q["element_id"] for q in health["questions"] if q["kind"] == "knowledge"]
        office_knowledge = [q["element_id"] for q in office["questions"] if q["kind"] == "knowledge"]
        self.assertIn("2.C.5.a", health_knowledge)  # medicine and dentistry
        self.assertNotIn("2.C.5.a", office_knowledge)
        self.assertEqual(len(skillcheck.plan(DATA, [], everything=True)["questions"]), 68)

    def test_every_question_offers_not_yet_and_three_levels(self):
        for q in skillcheck.plan(DATA, ["17"])["questions"]:
            self.assertEqual([o["level"] for o in q["options"]][0], 0.0)
            self.assertEqual(len(q["options"]), 4)

    def test_answers_are_checked(self):
        self.assertEqual(skillcheck.levels({"2.A.1.a": 4}, DATA), {"2.A.1.a": 4.0})
        for bad in ({"nope": 2}, {"2.A.1.a": 9}, {"2.A.1.a": True}, ["2.A.1.a"]):
            with self.assertRaises(skillcheck.SkillCheckError):
                skillcheck.levels(bad, DATA)
        with self.assertRaises(skillcheck.SkillCheckError):
            skillcheck.plan(DATA, ["99"])


class TestInterest(unittest.TestCase):
    def test_totals_percent_and_code(self):
        items = interest.item_bank()["items"]
        answers = [5 if i["type"] in "SI" else 1 for i in items]
        r = interest.score(answers)
        self.assertEqual(r["riasec"]["S"], 30)
        self.assertEqual(r["percent"]["R"], 0.0)
        self.assertEqual(r["code"][:2], "IS")  # a tie keeps R, I, A, S, E, C order
        self.assertTrue(r["usable"])

    def test_the_same_answer_everywhere_is_not_used(self):
        r = interest.score([3] * 36)
        self.assertFalse(r["usable"])
        self.assertEqual(r["warnings"][0]["type"], "same_answer")

    def test_bad_answers_are_refused(self):
        for bad in ([3] * 35, [0] + [3] * 35, ["5"] * 36, None):
            with self.assertRaises(interest.AnswerError):
                interest.score(bad)


class TestCVReader(unittest.TestCase):
    text = (ROOT / "src" / "static" / "sample_cv.txt").read_text(encoding="utf-8")

    def test_the_sample_cv(self):
        r = cv_reader.summarise({"text": self.text}, DATA)
        tools = {t["skill_id"] for t in r["technologies"]}
        self.assertTrue({"microsoft-excel", "sap-software", "intuit-quickbooks"} <= tools)
        self.assertEqual(r["education_job_zone"], 3)  # a diploma
        self.assertEqual(r["cv_skills"].get("2.C.1.c"), 3.0)  # accounting, at diploma level
        self.assertIn(CLERK, [o["occ_id"] for o in r["occupations"]])
        self.assertEqual(r["source"], "match")

    def test_a_club_role_outside_the_work_sections_is_not_a_job(self):
        r = cv_reader.summarise({"text": self.text}, DATA)
        self.assertNotIn("11-3031.01", [o["occ_id"] for o in r["occupations"]])  # Treasurer, under ACTIVITIES

    def test_common_words_are_not_tools(self):
        found = cv_reader.find_technologies("I excel at teamwork and keep a project diary in Word.", DATA["technologies"])
        self.assertEqual(found, [])
        found = cv_reader.find_technologies("Built reports in MS Excel and Microsoft Word.", DATA["technologies"])
        self.assertEqual({t["skill_id"] for t in found}, {"microsoft-excel", "microsoft-word"})

    def test_a_docx_is_read(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:body><w:p><w:t>Diploma in Nursing, 2021</w:t></w:p>"
                                            "<w:p><w:t>Staff Nurse at Hospital Contoh, using Microsoft Excel</w:t></w:p>"
                                            "</w:body></w:document>")
        r = cv_reader.summarise({"docx_base64": base64.b64encode(buf.getvalue()).decode()}, DATA)
        self.assertEqual(r["education_job_zone"], 3)
        self.assertIn("29-1141.00", [o["occ_id"] for o in r["occupations"]])

    def test_bad_input_is_refused(self):
        for bad in ({}, {"text": "too short"}, {"docx_base64": "not base64!"}):
            with self.assertRaises(cv_reader.CVReadError):
                cv_reader.summarise(bad, DATA)


if __name__ == "__main__":
    unittest.main()
