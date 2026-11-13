import json
import os
import unittest
from unittest import mock

from helpers import DATA, NURSE, sample

import explain
import matching


def a_match():
    return matching.match_person(sample("P01"), DATA, top=1, futures=50, include=[NURSE])["results"][-1]


class FakeReply:
    def __init__(self, text):
        self.data = json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.data


class TestExplain(unittest.TestCase):
    m = a_match()

    def test_without_a_key_the_template_is_used(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = explain.explain(self.m)
        self.assertEqual(out["source"], "fallback")
        self.assertIn(self.m["title"], out["text"])
        self.assertEqual(out["text_lang"], "en")
        self.assertEqual(explain.unknown_numbers(out["text"], out["facts"]), [])

    def test_the_facts_hold_the_card_numbers(self):
        f = explain.build_facts(self.m)
        self.assertEqual(f["match_score"], self.m["total"])
        self.assertEqual(f["field_fit"], self.m["components"]["field"]["points"])
        self.assertEqual(sum(v for v in f["max_points"].values() if v), 100.0)

    def test_predictions_are_caught_in_three_languages(self):
        self.assertTrue(explain.predictions("Demand will keep growing in the coming years."))
        self.assertTrue(explain.predictions("Permintaan akan meningkat.", "ms"))
        self.assertTrue(explain.predictions("需求将会增长。", "zh"))
        self.assertFalse(explain.predictions("Under the moderate scenario the estimate is steady."))

    def test_language_check(self):
        self.assertTrue(explain.in_language("Anda sesuai dengan pekerjaan ini kerana minat yang anda ada untuk orang.", "ms"))
        self.assertFalse(explain.in_language("You fit this job because of your interest in people.", "ms"))
        self.assertTrue(explain.in_language("这个职业很适合你，因为你喜欢帮助别人，而且你的技能契合度很高。", "zh"))

    def test_an_llm_reply_is_used_only_when_it_passes_the_checks(self):
        env = {"LLM_API_KEY": "test-key"}
        good = f"{self.m['title']} suits you: your interest fit is strong. Under the scenario the estimate is " \
               f"{self.m['outlook']['status']}, an estimate, not a prediction."
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("urllib.request.urlopen", return_value=FakeReply(good)):
            explain._replies.clear()
            self.assertEqual(explain.explain(self.m, short=True)["source"], "llm")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("urllib.request.urlopen", return_value=FakeReply("You will earn RM 98765 a month.")):
            explain._replies.clear()
            out = explain.explain(self.m, short=True)
        self.assertEqual(out["source"], "fallback")
        self.assertIn("98765", out["reason"])

    def test_an_unknown_language_is_refused(self):
        with self.assertRaises(ValueError):
            explain.explain(self.m, lang="fr")


if __name__ == "__main__":
    unittest.main()
