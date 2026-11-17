"""The source audit (scripts/source_audit.py): every data file has a source, and every unsourced number has been
looked at by a person."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import source_audit  # noqa: E402


class SourceAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = source_audit.run()

    def test_every_data_file_has_a_source(self):
        bad = [x["file"] for x in self.r["data"] if x["status"] == "no source found" or x["empty_rows"]]
        self.assertEqual(bad, [])

    def test_every_constant_off_the_sources_page_was_looked_at(self):
        # a new constant whose value is not on the Sources page must be put on it, or classified in CONST_KIND
        self.assertEqual([x["name"] for x in self.r["constants"] if x["kind"] == "not checked"], [])

    def test_every_uncited_statistic_was_looked_at(self):
        self.assertEqual([f"{x['file']}:{x['line']}" for x in self.r["prose"] if x["status"] != "fine"], [])
        self.assertEqual([f"{x['file']}:{x['line']}" for x in self.r["ui"] if x["status"] != "fine"], [])


if __name__ == "__main__":
    unittest.main()
