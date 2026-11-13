import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import releases  # noqa: E402

LISTING = [{"type": "directory", "path": "labor_market_impacts"}, {"type": "directory", "path": "release_2025_09_15"},
           {"type": "directory", "path": "release_2026_06_26"}, {"type": "file", "path": "README.md"}, "junk"]


class TestReleases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patch = mock.patch.object(releases, "CACHE", Path(self.tmp.name) / "release_check.json")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_newest_release_folder_wins(self):
        self.assertEqual(releases.latest_release(LISTING), "2026-06-26")
        self.assertIsNone(releases.latest_release([{"path": "README.md"}]))

    def test_the_pinned_release_is_current(self):
        out = releases.check(lambda: LISTING)
        self.assertEqual((out["pinned"], out["latest"], out["new_release"], out["error"]),
                         ("2026-06-26", "2026-06-26", False, None))
        self.assertEqual(releases.last_check(), out)  # kept for the Sources page

    def test_a_newer_release_is_reported_not_used(self):
        out = releases.check(lambda: LISTING + [{"path": "release_2026_09_30"}])
        self.assertEqual((out["latest"], out["new_release"]), ("2026-09-30", True))
        self.assertEqual(releases.pinned(), "2026-06-26")

    def test_an_unreachable_listing_is_reported_and_never_raises(self):
        def offline():
            raise OSError("no network")
        out = releases.check(offline)
        self.assertEqual((out["latest"], out["new_release"]), (None, False))
        self.assertIn("OSError", out["error"])

    def test_never_checked(self):
        self.assertEqual(releases.last_check(), {"pinned": "2026-06-26", "latest": None, "new_release": False,
                                                "checked": None, "error": None})
        releases.CACHE.write_text(json.dumps({"pinned": "2025-01-01", "latest": "2026-06-26"}), encoding="utf-8")
        self.assertIsNone(releases.last_check()["checked"])  # a check of another pin does not count


if __name__ == "__main__":
    unittest.main()
