"""The clarity check (scripts/pilot.py): sessions, answers, the two readings and who may see them."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import DEVELOPER, NURSE, get, post

import learning
import pilot


def learner(i: int) -> str:
    return f"browser-{i:04d}"


class TestPilot(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(pilot, "STORE", Path(self.dir.name) / "pilot.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)
        status, session = post("/api/pilot/session", {})
        self.assertEqual(status, 200)
        self.code, self.key = session["code"], session["key"]
        page = learning.page(DEVELOPER)
        self.gap = page["skills"][0]["skill_id"]
        self.course = next(r["id"] for s in page["skills"] for r in s["resources"])
        _, options = get("/api/pilot/options")
        self.options = options

    def say(self, i, phase, occ=None, gap=None, course=None, code=None):
        return post("/api/pilot/answer", {"code": code or self.code, "learner": learner(i), "phase": phase,
                                          "occ_id": occ, "gap_id": gap, "resource_id": course})

    def results(self):
        status, s = post("/api/pilot/summary", {"code": self.code, "key": self.key})
        self.assertEqual(status, 200)
        return s

    def test_options_are_the_same_lists_for_everyone_and_all_free(self):
        self.assertEqual(len(self.options["elements"]), 68)
        ids = {r["id"] for r in self.options["resources"]}
        self.assertIn(self.course, ids)
        self.assertFalse([i for i in ids if i.startswith("H")], "a paid HRD Corp course is offered as a first course")

    def test_the_key_is_not_stored_and_only_it_opens_the_results(self):
        self.assertNotIn(self.key, pilot.STORE.read_text(encoding="utf-8"))
        for body in ({"code": self.code, "key": "wrong"}, {"code": self.code}, {"code": "ZZZZZZ", "key": self.key}):
            status, answer = post("/api/pilot/summary", body)
            self.assertEqual(status, 400)
            self.assertNotIn("rows", answer)
        status, _ = get(f"/api/pilot/session/{self.code.lower()}")
        self.assertEqual(status, 200)
        self.assertEqual(get("/api/pilot/session/ZZZZZZ")[0], 400)

    def test_an_answer_is_a_pick_from_a_list_never_text(self):
        self.assertEqual(self.say(1, "before", occ="I want to be a doctor")[0], 400)
        self.assertEqual(self.say(1, "before", gap="Aiman bin Ali")[0], 400)
        self.assertEqual(self.say(1, "during")[0], 400)
        self.assertEqual(self.say(1, "before", code="ZZZZZZ")[0], 400)
        self.assertEqual(post("/api/pilot/answer", {"code": self.code, "learner": "x", "phase": "before"})[0], 400)
        self.assertEqual(self.results()["people"], {"before": 0, "after": 0, "both": 0})

    def test_named_is_counted_as_given_and_consistent_is_checked_against_the_path(self):
        self.say(1, "before")                                           # not sure about anything
        self.say(1, "after", DEVELOPER, self.gap, self.course)          # all three, and they agree
        self.say(2, "before", NURSE)
        off_path = next(e["id"] for e in self.options["elements"]
                        if e["id"] not in pilot.path_of(DEVELOPER)[0])
        status, saved = self.say(2, "after", DEVELOPER, off_path, self.course)
        self.assertEqual(status, 200)
        self.assertTrue(saved["reading"]["clear"])
        self.assertFalse(saved["reading"]["gap_on_path"])
        self.say(3, "before", DEVELOPER, self.gap, self.course)         # never came back
        s = self.results()
        self.assertEqual(s["people"], {"before": 3, "after": 2, "both": 2})
        self.assertEqual(s["named"]["before"], 0)
        self.assertEqual(s["named"]["after"], 2)
        self.assertEqual(s["named"]["after_pct"], 100.0)
        self.assertEqual(s["consistent_after"], {"count": 1, "pct": 50.0})
        self.assertEqual({q["question"]: (q["before"], q["after"]) for q in s["questions"]},
                         {"occupation": (1, 2), "gap": (0, 2), "course": (0, 2)})
        self.assertEqual(len(s["rows"]), 5, "every response is kept")
        self.assertNotIn("browser-", str(s["rows"]), "the export carries a running number, not the browser id")

    def test_a_changed_answer_replaces_the_one_before(self):
        self.say(1, "before", DEVELOPER, self.gap, self.course)
        self.say(1, "before")
        self.say(1, "after")
        s = self.results()
        self.assertEqual(s["people"]["both"], 1)
        self.assertEqual(s["named"]["before"], 0)

    def test_few_people_are_never_a_met_target(self):
        for i in range(pilot.MIN_PEOPLE - 1):
            self.say(i, "before")
            self.say(i, "after", DEVELOPER, self.gap, self.course)
        s = self.results()
        self.assertEqual(s["named"]["after_pct"], 100.0)
        self.assertFalse(s["enough_people"])
        self.assertFalse(s["target_met"])
        self.say(99, "before")
        self.say(99, "after", DEVELOPER, self.gap, self.course)
        s = self.results()
        self.assertTrue(s["enough_people"])
        self.assertTrue(s["target_met"])

    def test_a_session_is_deleted_after_the_retention_period(self):
        self.say(1, "before", DEVELOPER)
        late = pilot._today() + pilot.timedelta(days=pilot.KEEP_DAYS + 1)
        with mock.patch.object(pilot, "_today", return_value=late):
            self.assertEqual(post("/api/pilot/summary", {"code": self.code, "key": self.key})[0], 400)
            post("/api/pilot/session", {})
        self.assertNotIn(self.code, pilot.STORE.read_text(encoding="utf-8"))

    def test_sessions_and_people_are_bounded(self):
        with mock.patch.object(pilot, "MAX_PEOPLE", 2):
            self.assertEqual(self.say(1, "before")[0], 200)
            self.assertEqual(self.say(2, "before")[0], 200)
            self.assertEqual(self.say(3, "before")[0], 400)
            self.assertEqual(self.say(1, "after")[0], 200, "someone already in can still answer")
        with mock.patch.object(pilot, "MAX_SESSIONS", 1):
            self.assertEqual(post("/api/pilot/session", {})[0], 400)


if __name__ == "__main__":
    unittest.main()
