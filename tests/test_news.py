"""Verified real AI news (scripts/news.py): the page check, the AI's limits, the fixed rule, and that
nothing changes anyone's numbers until a person approves. No test opens the internet: pages are fakes."""

import json
import os
import re
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

from helpers import DATA, ROOT, get, post, sample  # noqa: F401  (puts scripts/ and src/ on the path)

import ai_exposure  # noqa: E402
import main  # noqa: E402
import matching  # noqa: E402
import news  # noqa: E402
import whatif  # noqa: E402

MS = "copilot_testing_dotnet"
QA = "15-1253.00"


def page_for(n: dict, date: str | None = None, drop_quote: bool = False) -> str:
    """A fake article page: the quotes with curly apostrophes, entities and line breaks, as sites send them."""
    quotes = n["quotes"][1:] if drop_quote else n["quotes"]
    body = "".join(f"<p>{q.replace(chr(39), '&rsquo;').replace(' ', chr(10), 1)}</p>" for q in quotes)
    meta = f'<meta property="article:published_time" content="{date}T18:05:00+00:00">' if date else ""
    return f"<html><head>{meta}<script>var x = 1;</script></head><body><h1>{n['title']}</h1>{body}</body></html>"


def opener_for(date=None, drop_quote=False):
    return lambda url: page_for(next(n for n in news.items() if n["url"] == url), date, drop_quote)


class NewsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("NEWS_LOG", main.NEWS_REVIEW_CODE)}
        os.environ["NEWS_LOG"] = str(Path(self.tmp.name) / "log.jsonl")
        os.environ.pop(main.NEWS_REVIEW_CODE, None)

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def verified(self, news_id=MS):
        n = news.item(news_id)
        self.assertEqual(news.check(news_id, opener_for(n["published"]))["status"], "verified")
        return news.propose(news_id)


class TestItems(NewsCase):
    def test_every_item_is_from_a_trusted_site_with_a_date_and_quotes(self):
        found = news.items()
        self.assertGreaterEqual(len(found), 1)
        for n in found:
            self.assertIn(urllib.parse.urlsplit(n["url"]).netloc, news.TRUSTED)
            self.assertRegex(n["published"], r"^\d{4}-\d\d-\d\d$")
            self.assertTrue(n["quotes"] and all(len(q) >= 20 for q in n["quotes"]))
            self.assertIn(n["field"], DATA["fields"])
            self.assertTrue(n["url"].startswith("https://"))

    def test_a_site_off_the_list_is_refused(self):
        raw = json.loads(news.NEWS_FILE.read_text(encoding="utf-8"))
        raw["items"][0]["url"] = "https://example.com/made-up"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "news.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            old, news.NEWS_FILE = news.NEWS_FILE, path
            try:
                with self.assertRaises(news.NewsError):
                    news.items()
            finally:
                news.NEWS_FILE = old


class TestCheck(NewsCase):
    def test_quotes_found_word_for_word_after_the_same_clean_up(self):
        n = news.item(MS)
        r = news.verdict(n, page_for(n, n["published"]))
        self.assertEqual(r["status"], "verified")
        self.assertTrue(all(q["found"] for q in r["quotes"]))
        self.assertEqual(r["page_date"], n["published"])

    def test_a_missing_quote_a_wrong_date_or_no_date_is_not_verified(self):
        n = news.item(MS)
        self.assertEqual(news.verdict(n, page_for(n, n["published"], drop_quote=True))["problem"], "quote_not_found")
        self.assertEqual(news.verdict(n, page_for(n, "2025-01-01"))["problem"], "date_differs")
        self.assertEqual(news.verdict(n, page_for(n, None))["problem"], "no_date")
        for case in (page_for(n, "2025-01-01"), page_for(n, None)):
            self.assertEqual(news.verdict(n, case)["status"], "not_verified")

    def test_a_page_that_does_not_open_is_not_verified_and_logged(self):
        def broken(url):
            raise urllib.error.URLError("offline")
        r = news.check(MS, broken)
        self.assertEqual((r["status"], r["problem"]), ("not_verified", "unreachable"))
        self.assertEqual(news.read_log()[-1]["step"], "checked")

    def test_a_changed_word_is_not_found(self):
        n = news.item(MS)
        changed = page_for(n, n["published"]).replace("unit tests", "integration tests")
        self.assertEqual(news.verdict(n, changed)["status"], "not_verified")


class TestProposal(NewsCase):
    def test_the_keyword_rule_stays_in_the_items_field_and_holds_no_numbers_of_its_own(self):
        p = self.verified()
        self.assertEqual(p["method"], "keyword")
        self.assertTrue(p["activities"])
        layer = ai_exposure.current()
        field_acts = {a for t in layer["tasks"] if DATA["by_id"].get(t["occ_id"], {}).get("field_id") == "15"
                      for a in t["work_activities"]}
        self.assertTrue(set(p["activities"]) <= field_acts)
        self.assertLessEqual(len(p["activities"]), news.MAX_ACTIVITIES)
        self.assertLessEqual(len(p["topics"]), news.MAX_TOPICS)
        for name in p["activities"] + p["topics"]:
            self.assertTrue(p["shared_words"][name], name)

    def test_the_llm_may_only_name_items_on_the_list(self):
        n = news.item(MS)
        acts, topics = news.candidates(n, ai_exposure.current())
        good_act, good_topic = acts[0]["name"], topics[0]["name"]
        reply = json.dumps({"activities": [good_act, "Invent a new job.", good_act], "topics": [good_topic, "Nope"],
                            "ai_share": 99, "handoff": {"x": 98}})
        a, t = news.llm_pick(n, acts, topics, caller=lambda s, q: "Sure! " + reply)
        self.assertEqual((a, t), ([good_act], [good_topic]))

    def test_an_unusable_llm_reply_falls_back_to_the_keyword_rule(self):
        self.verified()
        for bad in ("no json here", json.dumps({"activities": ["Made up."], "topics": []})):
            p = news.propose(MS, caller=lambda s, q, bad=bad: bad)
            self.assertEqual(p["method"], "keyword")
            self.assertIn("LLM failed", p["fallback_reason"])

    def test_numbers_come_from_the_fixed_rule(self):
        layer = ai_exposure.current()
        groups = whatif.activity_counts(layer)
        p = self.verified()
        for r in p["rows"]:
            if r["kind"] == "ai_share":
                avg = round(sum(x["ai_share"] for x in groups[r["name"]]) / len(groups[r["name"]]), 1)
                self.assertEqual(r["after"], min(whatif.NEWS_FLOOR, round(avg + news.ACTIVITY_STEP, 1)))
                self.assertEqual(p["changes"]["ai_share"][r["name"]], r["after"])
            else:
                self.assertEqual(r["after"], min(whatif.HANDOFF_MAX, round(r["before"] + news.TOPIC_STEP, 1)))
        high = max(groups, key=lambda a: sum(x["ai_share"] for x in groups[a]) / len(groups[a]))
        sized = news.size([high], [], layer)
        self.assertTrue(all(v <= whatif.NEWS_FLOOR for v in sized["changes"]["ai_share"].values()))


class TestDecide(NewsCase):
    def test_nothing_is_approved_without_a_verified_check_and_the_current_proposal(self):
        with self.assertRaises(news.NewsError):
            news.decide(MS, "approve", "x")
        n = news.item(MS)
        news.check(MS, opener_for("2025-01-01"))
        p = news.propose(MS)
        with self.assertRaises(news.NewsError):
            news.decide(MS, "approve", p["proposal_id"])  # not verified
        news.check(MS, opener_for(n["published"]))
        with self.assertRaises(news.NewsError):
            news.decide(MS, "approve", "stale")
        with self.assertRaises(news.NewsError):
            news.decide(MS, "undo")
        self.assertEqual(news.approved_changes()[0], [])

    def test_approve_changes_the_data_for_everyone_and_undo_takes_it_back(self):
        base = matching.load_data()
        self.assertIs(news.apply(base), base)
        p = self.verified()
        event = news.decide(MS, "approve", p["proposal_id"], "  A   reviewer  ")
        self.assertEqual(event["reviewer"], "A reviewer")
        live = news.apply(base)
        self.assertEqual(live["news"]["approved"], [MS])
        before = {t["task_id"]: t["ai_share"] for t in base["ai"]["tasks_by_occ"][QA]}
        after = {t["task_id"]: t["ai_share"] for t in live["ai"]["tasks_by_occ"][QA]}
        self.assertTrue(any(after[k] > before[k] for k in before))
        self.assertTrue(all(after[k] >= before[k] for k in before))
        with self.assertRaises(news.NewsError):
            news.decide(MS, "approve", p["proposal_id"])  # already approved
        news.decide(MS, "undo", reviewer="A reviewer")
        self.assertIs(news.apply(base), base)
        self.assertEqual([e["step"] for e in news.read_log()], ["checked", "proposed", "approved", "undone"])

    def test_reject_changes_nothing(self):
        p = self.verified()
        news.decide(MS, "reject", p["proposal_id"])
        self.assertEqual(news.approved_changes()[0], [])
        self.assertEqual(news.states()[MS]["decision"]["step"], "rejected")

    def test_a_what_if_on_top_keeps_the_approved_news(self):
        p = self.verified()
        news.decide(MS, "approve", p["proposal_id"])
        live = news.apply(matching.load_data())
        name = next(iter(p["changes"]["ai_share"]))
        merged = whatif.with_news(live, {"ai_share": {name: 1.0}, "handoff": {}})
        self.assertEqual(merged["ai_share"][name], p["changes"]["ai_share"][name])  # the higher floor holds
        self.assertEqual(whatif.with_news(matching.load_data(), {"ai_share": {name: 1.0}})["ai_share"], {name: 1.0})


class TestApi(NewsCase):
    def test_the_page_flow_through_the_api(self):
        status, view = get("/api/news")
        self.assertEqual(status, 200)
        self.assertEqual({n["state"] for n in view["items"]}, {"pending"})
        self.assertFalse(view["review_code_required"])
        n = news.item(MS)
        news.check(MS, opener_for(n["published"]))
        status, p = post("/api/news/propose", {"id": MS})
        self.assertEqual(status, 200)
        body = {"profile_id": "P05", "scenario": "moderate", "top": 5}
        _, before = post("/api/match", body)
        status, d = post("/api/news/decide", {"id": MS, "action": "approve", "proposal_id": p["proposal_id"]})
        self.assertEqual((status, d["step"]), (200, "approved"))
        _, after = post("/api/match", body)
        self.assertEqual(after["trend_data"]["news_approved"], [MS])
        self.assertNotEqual(before["trend_data"]["id"], after["trend_data"]["id"])
        qa = lambda r: next(m for m in r["results"] if m["occ_id"] == QA)  # noqa: E731
        self.assertGreater(qa(after)["ai"]["ai_share"], qa(before)["ai"]["ai_share"])
        post("/api/news/decide", {"id": MS, "action": "undo"})
        _, back = post("/api/match", body)
        self.assertEqual(back["trend_data"]["id"], before["trend_data"]["id"])

    def test_bad_requests_and_the_reviewer_code(self):
        self.assertEqual(post("/api/news/check", {"id": "made_up"})[0], 400)
        self.assertEqual(post("/api/news/decide", {"id": MS, "action": "delete"})[0], 400)
        os.environ[main.NEWS_REVIEW_CODE] = "letmein-test"
        self.assertTrue(get("/api/news")[1]["review_code_required"])
        self.assertEqual(post("/api/news/decide", {"id": MS, "action": "undo", "code": "wrong"})[0], 403)
        self.assertEqual(post("/api/news/decide", {"id": MS, "action": "undo", "code": "letmein-test"})[0], 400)


class TestJudgeCheck(NewsCase):
    def test_offline_run_refuses_every_unchecked_approval_and_leaves_the_apps_log_alone(self):
        import judge_check
        r = judge_check.real_news(offline=True)
        self.assertEqual(r["refused_unchecked"], len(r["items"]))
        self.assertIsNone(r["demo"])
        self.assertFalse(r["pass"])
        self.assertEqual(news.read_log(), [])  # the run used a log of its own
        rows = judge_check.real_news_headline(r)
        self.assertIn("not checked", rows.values())


class TestPage(unittest.TestCase):
    def test_every_real_news_line_is_in_three_languages_and_simulated_stays_labelled(self):
        text = (ROOT / "src" / "static" / "i18n.js").read_text(encoding="utf-8")
        script = (ROOT / "src" / "static" / "futures.js").read_text(encoding="utf-8")
        keys = {k for k in re.findall(r't\("(rn\.[a-z.]+)"', script) if not k.endswith(".")}  # "rn.step." + step: below
        keys |= {"rn.problem." + p for p in ("quote_not_found", "no_date", "date_differs", "unreachable")}
        keys |= {"rn.step." + s for s in ("checked", "proposed", "approved", "rejected", "undone")}
        for key in keys:
            line = next((ln for ln in text.splitlines() if ln.strip().startswith(f'"{key}":')), None)
            self.assertIsNotNone(line, key)
            self.assertEqual(len(json.loads(line.split(":", 1)[1].strip().rstrip(","))), 3, key)
        self.assertTrue(all(n["simulated"] for n in whatif.news()))
        self.assertIn('t("news.simulated")', script)


if __name__ == "__main__":
    unittest.main()
