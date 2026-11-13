import unittest

from helpers import DATA

import matching

GAMBLING_CASHIER = "41-2012.00"
SALES_PERSON = {"fields": {"41": 100, "43": 100}, "technologies": ["microsoft-excel"]}


class TestMalaysianRestrictions(unittest.TestCase):
    def test_gambling_occupations_are_marked(self):
        found = matching.restriction(DATA["by_id"][GAMBLING_CASHIER], DATA)
        self.assertEqual(found["restriction_id"], "gambling")
        self.assertIsNone(matching.restriction(DATA["by_id"]["39-1014.00"], DATA))  # "Except Gambling"

    def test_they_are_left_out_of_matches_by_default(self):
        ranked = matching.rank(SALES_PERSON, DATA)
        listed = [m for m in ranked if not m["_parts"]["last"]]
        restricted = set(DATA["restricted"])
        self.assertFalse(restricted & {m["occ_id"] for m in listed})
        cashier = next(m for m in ranked if m["occ_id"] == GAMBLING_CASHIER)
        self.assertIn("restricted_my", cashier["flags"])

    def test_the_person_can_choose_to_show_them(self):
        ranked = matching.rank({**SALES_PERSON, "show_restricted": True}, DATA)
        cashier = next(m for m in ranked if m["occ_id"] == GAMBLING_CASHIER)
        self.assertNotIn("restricted_my", cashier["flags"])
        self.assertFalse(cashier["_parts"]["last"])

    def test_the_score_itself_does_not_change(self):
        hidden = next(m for m in matching.rank(SALES_PERSON, DATA) if m["occ_id"] == GAMBLING_CASHIER)
        shown = next(m for m in matching.rank({**SALES_PERSON, "show_restricted": True}, DATA)
                     if m["occ_id"] == GAMBLING_CASHIER)
        self.assertEqual(hidden["total"], shown["total"])


if __name__ == "__main__":
    unittest.main()
