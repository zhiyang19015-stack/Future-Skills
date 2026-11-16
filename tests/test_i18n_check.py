"""The language and label check (scripts/i18n_check.py): its rules on small made-up files, and the app's own files."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (sets the import paths)
import i18n_check
import judge_check


class RulesTest(unittest.TestCase):
    def scan(self, files: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                Path(tmp, name).write_text(text, encoding="utf-8")
            with mock.patch.object(i18n_check, "STATIC", Path(tmp)):
                name = next(iter(files))
                return {"hard": i18n_check.hardcoded(name), "unl": i18n_check.unlabelled(name),
                        "rows": i18n_check.tables() if "i18n.js" in files else None}

    def test_english_in_markup_is_found_and_text_through_t_is_not(self):
        code = 'const a = `<p>${t("x.ok")}</p><p>Read this first</p><button title="Close it">${t("x.b")}</button>`;\n'
        hits = self.scan({"page.js": code})["hard"]
        self.assertEqual(sorted(h["text"] for h in hits), ["Close it", "Read this first"])

    def test_names_codes_and_expressions_are_not_english_text(self):
        code = 'const a = `<span>MyCOL</span><b>SDG ${x}</b><i>${esc(row.title)}</i><a>LinkedIn</a>`;\n'
        self.assertEqual(self.scan({"page.js": code})["hard"], [])

    def test_template_inside_an_expression_is_read_once(self):
        code = 'const a = `<div>${ok ? `<p>Nested words</p>` : ""}</div>`;\n'
        self.assertEqual([h["text"] for h in self.scan({"page.js": code})["hard"]], ["Nested words"])

    def test_unlabelled_field(self):
        code = ('const a = `<textarea id="x" placeholder="${t("p")}"></textarea>'
                '<label>${t("n")} <input type="text"></label><input aria-label="${t("q")}">`;\n')
        hits = self.scan({"page.js": code})["unl"]
        self.assertEqual([h["field"] for h in hits], ["textarea"])

    def test_rows_outside_strings_are_not_ui_rows(self):
        i18n = ('const STRINGS = {\n  "a.b": ["One", "Satu", ""],\n};\n'
                'const NAMES = {\n  "No Poverty": ["Tanpa Kemiskinan", "无贫穷"],\n};\n')
        rows = self.scan({"i18n.js": i18n})["rows"]
        self.assertEqual(list(rows), ["a.b"])
        self.assertEqual(rows["a.b"]["zh"], "")

    def test_contrast_ratio(self):
        self.assertEqual(i18n_check.ratio("#000000", "#ffffff"), 21.0)
        self.assertEqual(i18n_check.ratio("#777777", "#ffffff"), 4.48)


class AppTest(unittest.TestCase):
    def test_every_key_the_pages_call_exists(self):
        r = i18n_check.run()
        for name, page in r["pages"].items():
            self.assertEqual(page["missing_keys"], [], name)

    def test_summary_is_what_the_judge_check_reports(self):
        lg = judge_check.languages()
        self.assertEqual(lg["summary"], i18n_check.summary(i18n_check.run()))
        self.assertEqual(lg["pass"], all(v in (0, "0 / 0", "yes") for v in lg["summary"].values()))


if __name__ == "__main__":
    unittest.main()
