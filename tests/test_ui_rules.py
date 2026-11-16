"""The UI redesign draws numbers it does not compute; these tests keep its rules tied to the code that
does: the task strip uses the Lab's stress-test thresholds, and check 10 counts the real first-time path."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import first_path  # noqa: E402
import stress_test  # noqa: E402

UI = (ROOT / "src" / "static" / "ui.js").read_text(encoding="utf-8")


class TaskStripRule(unittest.TestCase):
    def test_thresholds_equal_the_stress_test(self):
        found = re.search(r"const TASK_RULE = \{([^}]*)\}", UI)
        self.assertIsNotNone(found)
        rule = {k: float(v) for k, v in re.findall(r"(\w+): (\d+(?:\.\d+)?)", found.group(1))}
        self.assertEqual(rule, {"AUTOMATE": stress_test.AUTOMATE, "AUGMENT": stress_test.AUGMENT,
                                "AUTOMATION_SIDE": stress_test.AUTOMATION_SIDE, "POOR_EVIDENCE": stress_test.POOR_EVIDENCE})


class FirstPath(unittest.TestCase):
    def test_paths_are_whole_and_counted(self):
        r = first_path.run()
        for p in r["paths"].values():
            self.assertEqual(p["broken"], [], p["about"])
        own = r["paths"]["own"]
        self.assertEqual(own["to_ranking"], {"clicks": 2, "inputs": 1})
        self.assertEqual(own["to_plan"], {"clicks": 2, "inputs": 1})
        self.assertFalse(r["api"]["blank_ranked"])
        self.assertEqual(r["api"]["one_tap_ok"], r["api"]["fields"])

    def test_a_missing_button_breaks_the_path(self):
        path = {"about": "x", "steps": [{"do": "click", "file": "app.js", "fn": "PAGES.home", "needle": "no-such-button", "what": "x"}]}
        self.assertEqual(len(first_path.walk(path)["broken"]), 1)


if __name__ == "__main__":
    unittest.main()
