import unittest
import urllib.error
from unittest import mock

from helpers import ROOT  # noqa: F401  (also puts scripts/ on the path)

import check_links


class Page:
    def __init__(self, body: str, status: int = 200):
        self.body, self.status = body.encode(), status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self.body


class TestCheckLinks(unittest.TestCase):
    def test_every_link_the_page_shows_is_checked(self):
        found = check_links.links()
        self.assertTrue(any(name == "learning_resources.csv" for name, _, _ in found))
        self.assertTrue(any(name == "regulated.csv" for name, _, _ in found))
        self.assertTrue(all(url.startswith("https://") for _, _, url in found))

    def test_an_open_page_is_ok(self):
        with mock.patch("urllib.request.urlopen", return_value=Page("<title>Course</title>")):
            self.assertEqual(check_links.status("https://learn.saylor.org/course/bus101")[0], "ok")

    def test_a_saylor_course_behind_a_log_in_is_broken(self):
        with mock.patch("urllib.request.urlopen", return_value=Page("<title>Log in to the site | Saylor</title>")):
            self.assertEqual(check_links.status("https://learn.saylor.org/course/x"), ("broken", "asks for a log-in"))

    def test_refused_and_missing_pages(self):
        def raise_(code):
            def f(*a, **k):
                raise urllib.error.HTTPError("u", code, "x", {}, None)
            return f
        with mock.patch("urllib.request.urlopen", side_effect=raise_(403)):
            self.assertEqual(check_links.status("https://example.org")[0], "refused")
        with mock.patch("urllib.request.urlopen", side_effect=raise_(404)):
            self.assertEqual(check_links.status("https://example.org")[0], "broken")
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertEqual(check_links.status("https://example.org")[0], "broken")


if __name__ == "__main__":
    unittest.main()
