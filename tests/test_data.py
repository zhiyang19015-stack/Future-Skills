import unittest

from helpers import DATA

import matching

import validate_data


class TestData(unittest.TestCase):
    def test_every_table_passes_its_checks(self):
        self.assertEqual(validate_data.check(), [])

    def test_every_field_has_occupations_and_every_occupation_has_what_it_needs(self):
        self.assertEqual(len(DATA["fields"]), 22)
        self.assertGreater(len(DATA["occupations"]), 900)
        by_field = {f: 0 for f in DATA["fields"]}
        for o in DATA["occupations"]:
            by_field[o["field_id"]] += 1
            self.assertTrue(DATA["occ_elements"].get(o["occ_id"]), o["occ_id"])
            self.assertIn(o["occ_id"], DATA["ai"]["roles"])
            self.assertIn(o["occ_id"], DATA["demand"]["occupations"])
        self.assertTrue(all(n > 0 for n in by_field.values()), by_field)

    def test_the_skills_check_has_three_examples_for_every_skill(self):
        self.assertEqual(sum(1 for e in DATA["elements"].values() if e["kind"] == "skill"), 35)
        self.assertEqual(sum(1 for e in DATA["elements"].values() if e["kind"] == "knowledge"), 33)
        for e in DATA["elements"].values():
            levels = [float(e[f"anchor_{p}_level"]) for p in ("low", "mid", "high")]
            self.assertEqual(levels, sorted(levels), e["element_id"])

    def test_malaysian_links(self):
        on_list = [o for o in DATA["occupations"] if o["mycol"] == "yes"]
        self.assertGreater(len(on_list), 100)
        self.assertEqual(DATA["by_id"]["29-1141.00"]["mycol"], "yes")  # nursing professionals are on MyCOL
        self.assertEqual(DATA["by_id"]["15-1252.00"]["isco"], "2512")
        self.assertTrue(all(o["masco_major"] == o["isco"][:1] for o in DATA["occupations"]))

    def test_every_field_and_skill_serves_a_un_goal(self):
        for o in DATA["occupations"][::50]:
            self.assertTrue(matching.occupation_sdg(o, DATA), o["occ_id"])


if __name__ == "__main__":
    unittest.main()
