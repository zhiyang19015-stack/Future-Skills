import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main  # noqa: E402  (adds scripts/ to the path)
import impact  # noqa: E402


def post(path, data):
    res = main.dispatch("POST", path, json.dumps(data).encode())
    return res.status, json.loads(res.body)


class TestImpact(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(impact, "TALLY", Path(self.dir.name) / "sdg_tally.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def test_empty_tally_still_lists_the_three_proposal_targets(self):
        s = impact.summary()
        self.assertEqual(s["students"], 0)
        self.assertEqual([t["target"] for t in s["headline"]], ["4.3", "4.4", "8.5"])
        self.assertTrue(all(t["goal_name"] for t in s["headline"]))

    def test_latest_report_per_person_and_occupation_counts_once(self):
        impact.record("browser-aaaa1111", "29-1141.00", 40, 5, 1)
        impact.record("browser-aaaa1111", "29-1141.00", 40, 12, 3)  # ticked more: replaces, not adds
        impact.record("browser-bbbb2222", "29-1141.00", 40, 0, 0)
        s = impact.summary()
        self.assertEqual((s["students"], s["students_studying"], s["paths"]), (2, 1, 2))
        self.assertEqual((s["hours_planned"], s["hours_done"]), (80.0, 12.0))
        self.assertEqual(s["roles"][0]["students"], 2)

    def test_every_path_counts_towards_the_three_platform_targets(self):
        impact.record("browser-aaaa1111", "29-1141.00", 30, 10)
        impact.record("browser-bbbb2222", "13-2011.00", 50, 0)
        for t in impact.summary()["headline"]:
            self.assertEqual((t["students"], t["hours_done"], t["hours_planned"]), (2, 10.0, 80.0), t["target"])
            self.assertTrue(t["why"])

    def test_path_counts_towards_the_targets_its_learning_page_lists(self):
        listed = {t["target"] for t in main.learning.page("29-1141.00")["sdg"]}
        impact.record("browser-aaaa1111", "29-1141.00", 30, 10)
        counted = {t["target"] for t in impact.summary()["targets"]}
        self.assertEqual(counted, listed)

    def test_bad_reports_are_refused(self):
        for bad in [{"learner": "x", "occ_id": "29-1141.00", "hours_planned": 1, "hours_done": 0},
                    {"learner": "browser-aaaa1111", "occ_id": "NOPE", "hours_planned": 1, "hours_done": 0},
                    {"learner": "browser-aaaa1111", "occ_id": "29-1141.00", "hours_planned": 1, "hours_done": 5},
                    {"learner": "browser-aaaa1111", "occ_id": "29-1141.00", "hours_planned": -1, "hours_done": 0},
                    {"learner": "browser-aaaa1111", "occ_id": "29-1141.00", "hours_planned": "10", "hours_done": 0}]:
            status, _ = post("/api/sdg/record", bad)
            self.assertEqual(status, 400, bad)

    def test_api_records_and_sums_up(self):
        status, s = post("/api/sdg/record", {"learner": "browser-aaaa1111", "occ_id": "29-1141.00",
                                             "hours_planned": 20, "hours_done": 4, "items_done": 2})
        self.assertEqual(status, 200)
        self.assertEqual(s["hours_done"], 4.0)
        got = json.loads(main.dispatch("GET", "/api/sdg/summary").body)
        self.assertEqual(got["students"], 1)
        self.assertIn("method", got)


if __name__ == "__main__":
    unittest.main()
