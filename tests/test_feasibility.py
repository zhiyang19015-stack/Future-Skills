"""The feasibility pack: KPIs computed from the data, the cost model, and documents with nothing left unfilled."""
import re
import unittest

from helpers import DATA, ROOT

import cost_model
import kpi

PLACEHOLDER = re.compile(r"\bTODO\b|\bTBD\b|RESEARCH NEEDED|\[[Cc]heck\]|TO FILL|_{3,}|[Ll]orem ipsum")  # as typed in drafts
LINK = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")


class TestKpi(unittest.TestCase):
    def test_coverage_is_a_share_of_what_occupations_ask_for(self):
        c = kpi.coverage(DATA)
        self.assertEqual(c["occupations"], len(DATA["occupations"]))
        self.assertTrue(0 < c["lowest"] <= c["mean"] <= 100)
        self.assertLessEqual(c["elements_covered"], c["elements"])
        nothing = {**DATA, "by_target": {}}
        self.assertEqual(kpi.coverage(nothing)["mean"], 0.0)
        self.assertEqual(kpi.coverage(nothing)["under_floor"], c["occupations"])

    def test_grades_and_sources_add_up(self):
        g = kpi.grades(DATA)
        self.assertEqual(g["A"] + g["B"] + g["C"], g["total"])
        s = kpi.sourced()
        self.assertEqual(s["faults"], 0)
        self.assertGreater(s["rows"], 1000)

    def test_the_report_names_every_kpi(self):
        text = kpi.as_markdown(kpi.report(DATA))
        for name in ("Path coverage", "Evidence grade", "Scenario check", "Rows without a source", "Oldest link check"):
            self.assertIn(name, text)


class TestCostModel(unittest.TestCase):
    measured = {"requests": 24, "cpu_seconds": 4.0, "transfer_kb": 200, "memory_mb": 190}
    tokens = {"in": 1000, "out": 400, "out_cap": 1500}

    def test_every_input_has_a_source_and_a_kind(self):
        for row in cost_model.inputs().values():
            self.assertIn(row["kind"], ("published_price", "assumption"), row["input_id"])
            self.assertTrue(row["source_name"] and row["source_url"].startswith("https://") and row["source_date"])

    def test_the_busiest_moment_sets_the_servers(self):
        x = cost_model.inputs()
        small, large = (cost_model.monthly(n, self.measured, self.tokens, x) for n in (200, 50000))
        carries = 10 * 60 * 0.7 / (4.0 * 3)  # journey minutes x 60 x busy share / core seconds
        self.assertEqual(small["server_carries"], round(carries, 1))
        self.assertEqual(small["peak_people"], 40)   # one workshop, however few users
        self.assertEqual(small["servers"], 2)
        self.assertEqual(large["peak_people"], 500)  # 1% of the month's users
        self.assertEqual(large["servers"], 15)
        self.assertAlmostEqual(small["hosting_myr"], 2 * 6.00 * 4.09, places=2)
        self.assertLess(large["per_user_myr"], small["per_user_myr"])

    def test_the_ai_text_is_priced_per_token(self):
        row = cost_model.monthly(5000, self.measured, self.tokens, cost_model.inputs())
        expected = 5000 * 3 * (1000 * 0.15 + 400 * 0.60) / 1e6 * 4.09
        self.assertAlmostEqual(row["llm_myr"], expected, places=2)
        self.assertAlmostEqual(row["total_myr"], row["hosting_myr"] + row["llm_myr"], places=2)

    def test_the_journey_runs_and_is_measured(self):
        m = cost_model.measure(repeats=1)
        self.assertEqual(m["requests"], len(cost_model.journey()))
        self.assertGreater(m["cpu_seconds"], 0)
        self.assertGreater(m["transfer_kb"], 50)
        tokens = cost_model.llm_tokens(4)
        self.assertGreater(tokens["in"], tokens["out"])


class TestDocuments(unittest.TestCase):
    documents = [ROOT / "README.md", ROOT / "SOURCES.md", *sorted((ROOT / "docs").glob("*.md"))]

    def test_nothing_is_left_unfilled(self):
        for path in self.documents:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(PLACEHOLDER.search(line), f"{path.name} line {number}: {line[:80]}")

    def test_links_between_documents_lead_somewhere(self):
        for path in self.documents:
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                if not target.startswith(("http://", "https://", "mailto:")):
                    self.assertTrue((path.parent / target).exists(), f"{path.name}: {target}")

    def test_the_pack_is_generated_and_linked(self):
        for name in ("feasibility.md", "cost_model.md", "kpi_report.md"):
            self.assertTrue((ROOT / "docs" / name).exists(), name)
            self.assertIn(f"docs/{name}", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertNotIn("20 testers:", (ROOT / "docs" / "feasibility.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
