"""Language and accessibility check of the web page's own files: no server, no browser, no network.

It reads src/static/*.js, index.html and style.css as text (and /api/sources through main.dispatch,
in-process) and counts, for English, Bahasa Melayu and
Chinese:

    keys      t("key") calls whose key is in no string table (the page shows the bare key)
    fallback  table rows with no Bahasa Melayu or Chinese text (t() falls back to English)
    same      rows whose Bahasa Melayu or Chinese text is the English text, other than names kept on
              purpose (KEEP_AS_IS)
    hardcoded English words written straight into the page's HTML or into an attribute a screen
              reader reads (title, aria-label, placeholder, alt), not through t()
    labels    <input>, <select> and <textarea> elements with no label, aria-label or aria-labelledby
    contrast  pairs of text and background colours in style.css below WCAG AA (4.5:1), light and dark
    tables    UN goal names, goal texts, the 36 interest statements and the SDG reasons of
              data/sdg_map.csv with no Bahasa Melayu or Chinese line; Sources-page descriptions
    names     occupation titles, skill and knowledge names, MASCO groups and course notes from the data
              with no line in names-i18n.js (our own translation, shown through nm())
    indonesian Bahasa Melayu rows with a word on the INDONESIAN list (a rule of thumb)

Counts are per page file, named by the pages it draws (PAGE_FILES). The scan is a rule on the source
text, so it can miss text built in an unusual way and it can count text that only looks English (a
brand name). What it counts is listed by line in the report, so every count can be checked.

    python scripts/i18n_check.py           # print the counts and every finding
    python scripts/i18n_check.py --json    # the same as JSON
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "static"
TABLES = ("i18n.js", "lab-i18n.js", "pilot-i18n.js", "ui-i18n.js")
LANGS = ("en", "ms", "zh")

# Which pages each script draws (its PAGES.* entries), so a count can be read per page.
PAGE_FILES = {
    "index.html": "header, skip link",
    "app.js": "home, sources, header and footer, errors",
    "ui.js": "redesign pieces: task strip, roadmap, learning line, evidence stamps, rank moves, profile progress",
    "you.js": "1 You",
    "explore.js": "2 Radar, occupation, 3 Matches, 4 Pathway, 5 SDG",
    "futures.js": "6 Futures, news",
    "quick.js": "quick start",
    "team.js": "team",
    "lab.js": "lab",
    "pilot.js": "workshop check",
}

# Rows whose Bahasa Melayu or Chinese text is rightly the same as the English: names of products,
# sources and programmes that have no official translation, and symbols. Key -> languages.
KEEP_AS_IS: dict[str, tuple[str, ...]] = {
    "fmt.video": ("ms",),             # "video" is the Bahasa Melayu word (Kamus Dewan)
    "nav.radar": ("ms",),             # "radar" is the Bahasa Melayu word
    "why.t.demand.neutral": ("ms",),  # "neutral" is the Bahasa Melayu word
    "lab.ilo.map": ("ms",),           # only a code and blanks: "ISCO-08 {0} {1}; {2}"
}
# Text in index.html that is meant to be read in all three languages at once.
TRILINGUAL = {"Language / Bahasa / 语言"}
# Malaysian phrases that contain a word from the list below and are right as they are.
MALAYSIAN_OK = ("perhubungan perusahaan",)  # industrial relations: Jabatan Perhubungan Perusahaan Malaysia
# Words that are Indonesian and not Bahasa Malaysia (the Malaysian word in brackets). A rule of thumb for
# "BM, not Indonesian": a hit is a word to check, not proof of an error.
INDONESIAN = ("bisa (boleh)", "karena (kerana)", "rekomendasi (cadangan)", "kualitas (kualiti)",
              "aktivitas (aktiviti)", "fasilitas (kemudahan)", "jadwal (jadual)", "kalender (kalendar)",
              "nomor (nombor)", "otomatis (automatik)", "perusahaan (syarikat)", "karyawan (pekerja)",
              "pelatihan (latihan)", "keterampilan (kemahiran)", "lowongan (kekosongan)", "unduh (muat turun)",
              "unggah (muat naik)", "berhasil (berjaya)", "silakan (sila)", "kamu (anda)", "biaya (kos)",
              "kantor (pejabat)", "menit (minit)", "sertifikat (sijil)", "standar (piawai)",
              "efektif (berkesan)", "mobil (kereta)", "rumah sakit (hospital)", "kartu (kad)",
              "saat ini (sekarang)", "mengunjungi (melawat)")

SDG_MAP = ROOT / "data" / "sdg_map.csv"
ROW = re.compile(r'^\s*"([^"]+)":\s*(\[.*\]),?\s*$')
T_CALL = re.compile(r"""\bt\(\s*(["'])([^"'`]+?)\1\s*[,)]""")
TEXT_ATTR = re.compile(r"""\b(title|aria-label|placeholder|alt)=(["'])([^"'$]*?)\2""")
WORD = re.compile(r"[A-Za-z]{3,}")
# Words that are names or codes, the same in every language of the app.
NAMES = {"Future", "Skills", "MyCOL", "MYFutureJobs", "JobStreet", "LinkedIn", "SDG", "HRD", "Corp", "O*NET",
         "ONET", "ILO", "DOSM", "PDPA", "Claude", "Anthropic", "Economic", "Index", "Bahasa", "Melayu", "English",
         "PDF", "docx", "txt", "CSV", "JSON", "API", "URL", "HTTP", "MASCO", "SOC", "TVET", "UN", "ISCO", "RIASEC",
         "NET"}


def tables() -> dict[str, dict]:
    """Every row of the string tables: key -> {"file", "line", "en", "ms", "zh"}."""
    rows = {}
    for name in TABLES:
        if not (STATIC / name).exists():
            continue
        inside = False  # only the rows of STRINGS (i18n.js) or Object.assign(STRINGS, ...) (the others)
        for n, line in enumerate((STATIC / name).read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"(const STRINGS = \{|Object\.assign\(STRINGS, \{)", line):
                inside = True
                continue
            if inside and re.match(r"\}\)?;", line):
                inside = False
            m = inside and ROW.match(line)
            if not m:
                continue
            vals = json.loads(m.group(2))
            if not (isinstance(vals, list) and vals and all(isinstance(v, str) for v in vals)):
                continue
            rows[m.group(1)] = {"file": name, "line": n, **{lang: (vals[i] if i < len(vals) else "")
                                                             for i, lang in enumerate(LANGS)}}
    return rows


def _strip_expressions(src: str) -> str:
    """A template's text with every ${...} replaced by a blank, braces counted so nesting is kept out."""
    out, i, depth = [], 0, 0
    while i < len(src):
        if depth == 0 and src.startswith("${", i):
            depth, i = 1, i + 2
            out.append(" ")
            continue
        if depth:
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
            i += 1
            continue
        out.append(src[i])
        i += 1
    return "".join(out)


def templates(code: str) -> list[tuple[int, str]]:
    """The static text of every `...` template in a script, with the line it starts on. A template
    inside a ${...} is found on its own."""
    found, i, n = [], 0, len(code)
    stack = []  # open templates: (start index, start line)
    line = 1
    in_str = None
    while i < n:
        c = code[i]
        if c == "\n":
            line += 1
        if in_str:  # inside '...' or "..." outside any template text
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if not stack and code.startswith("//", i):
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        if not stack and code.startswith("/*", i):
            j = code.find("*/", i)
            line += code[i:j].count("\n")
            i = n if j < 0 else j + 2
            continue
        if not stack and c in "\"'":
            in_str = c
            i += 1
            continue
        if c == "`":
            if stack and stack[-1][2] == 0:  # closing the innermost template
                start, sline, _ = stack.pop()
                found.append((sline, code[start:i]))
            else:
                stack.append([i + 1, line, 0])
            i += 1
            continue
        if stack:
            top = stack[-1]
            if c == "\\":
                i += 2
                continue
            if top[2] == 0 and code.startswith("${", i):
                top[2] = 1
                i += 2
                continue
            if top[2] > 0:
                if c in "\"'":  # a string inside an expression
                    q, j = c, i + 1
                    while j < n and code[j] != q:
                        j += 2 if code[j] == "\\" else 1
                    i = j + 1
                    continue
                if c == "{":
                    top[2] += 1
                elif c == "}":
                    top[2] -= 1
        i += 1
    return found


def _english(text: str) -> list[str]:
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    return [w for w in WORD.findall(text) if w not in NAMES]


def hardcoded(name: str) -> list[dict]:
    """English written into the page's markup instead of through t()."""
    code = (STATIC / name).read_text(encoding="utf-8")
    hits = []
    pieces = [(1, code)] if name.endswith(".html") else templates(code)
    for start, raw in pieces:
        text = raw if name.endswith(".html") else _strip_expressions(raw)
        if name.endswith(".html"):
            text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<head>.*?</head>", lambda m: "\n" * m.group(0).count("\n"),
                          text, flags=re.S)
            # the shell's text and labels that app.js replaces from a key (data-i18n, data-i18n-aria)
            text = re.sub(r"(<[^>]*\bdata-i18n=[^>]*>)[^<]*", r"\1", text)
            text = re.sub(r"""\baria-label=(["'])[^"']*\1(?=[^>]*\bdata-i18n-aria=)""", "", text)
            for keep in TRILINGUAL:
                text = text.replace(keep, " ")
        for m in TEXT_ATTR.finditer(text):
            words = _english(m.group(3))
            if words:
                hits.append({"file": name, "line": start + text[:m.start()].count("\n"), "where": m.group(1),
                             "text": m.group(3).strip()})
        if "<" not in text and ">" not in text:
            continue  # not markup: a class name, a URL, a key
        for m in re.finditer(r">([^<>]+)<", text):
            words = _english(m.group(1))
            if words:
                hits.append({"file": name, "line": start + text[:m.start()].count("\n"), "where": "text",
                             "text": " ".join(m.group(1).split())})
    return _unique(hits)


def _unique(hits: list[dict]) -> list[dict]:
    """A template inside another is read twice (once on its own); count each finding once."""
    seen, out = set(), []
    for h in hits:
        k = (h["file"], h["line"], h.get("where", h.get("field")), h["text"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


def unlabelled(name: str) -> list[dict]:
    """Form fields with no label: no aria-label/aria-labelledby, no id named by a <label for>, and not
    inside a <label> in the same template."""
    code = (STATIC / name).read_text(encoding="utf-8")
    pieces = [(1, code)] if name.endswith(".html") else templates(code)
    fors = set(re.findall(r"""<label[^>]*\bfor=["']([^"'$]+)["']""", code))
    hits = []
    for start, raw in pieces:
        for m in re.finditer(r"<(input|select|textarea)\b([^>]*)>", raw):
            attrs = m.group(2)
            if re.search(r"""type=["']hidden["']""", attrs) or re.search(r"aria-label(ledby)?=", attrs):
                continue
            fid = re.search(r"""\bid=["']([^"'$]+)["']""", attrs)
            if fid and fid.group(1) in fors:
                continue
            before = raw[:m.start()]
            if before.rfind("<label") > before.rfind("</label>"):
                continue  # wrapped in a label
            hits.append({"file": name, "line": start + before.count("\n"), "field": m.group(1),
                         "text": " ".join(m.group(0).split())[:120]})
    return _unique(hits)


def indonesian() -> list[dict]:
    """Bahasa Melayu rows that use a word from INDONESIAN."""
    words = [w.split(" (")[0] for w in INDONESIAN]
    pat = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
    ms = {k: r["ms"] for k, r in tables().items()}
    for name in ("sdg-i18n.js", "names-i18n.js"):
        ms.update({f"{name}: {en[:50]}": pair[0] for en, pair in _pairs(name).items()})
    ok = re.compile("|".join(re.escape(x) for x in MALAYSIAN_OK), re.I)
    return [{"key": k, "word": m.group(1)} for k, text in ms.items() for m in [pat.search(ok.sub(" ", text))] if m]


def _pairs(name: str) -> dict:
    """English -> [ms, zh] rows of a static table file (sdg-i18n.js, names-i18n.js); empty when absent."""
    path = STATIC / name
    if not path.exists():
        return {}
    rows = {}
    for m in re.finditer(r'^\s*("(?:[^"\\]|\\.)*"):\s*(\[.*\]),\s*$', path.read_text(encoding="utf-8"), re.M):
        rows[json.loads(m.group(1))] = json.loads(m.group(2))
    return rows


def data_names() -> dict:
    """Names the data keeps in English that the page shows through nm() (names-i18n.js): occupation titles,
    O*NET skill and knowledge names, MASCO major groups and course notes, with how many have no BM / ZH line."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import demand  # noqa: E402
    have = _pairs("names-i18n.js")
    sets = {}
    with (ROOT / "data" / "occupations.csv").open(encoding="utf-8") as f:
        sets["occupations"] = sorted({r["title"] for r in csv.DictReader(f)})
    with (ROOT / "data" / "elements.csv").open(encoding="utf-8") as f:
        sets["skills_knowledge"] = sorted({r["name"] for r in csv.DictReader(f)})
    sets["masco_groups"] = sorted({v[0] for v in demand.MASCO_MAJOR.values()})
    with (ROOT / "data" / "learning_resources.csv").open(encoding="utf-8") as f:
        sets["course_notes"] = sorted({r["notes"] for r in csv.DictReader(f) if r["notes"].strip()})
    return {k: {"rows": len(v), "missing_ms": sum(1 for e in v if not (e in have and have[e][0].strip())),
                "missing_zh": sum(1 for e in v if not (e in have and len(have[e]) > 1 and have[e][1].strip()))}
            for k, v in sets.items()}


def side_tables() -> dict:
    """The other tables the page reads: UN goal names [ms, zh], goal and target texts [en, ms, zh], the 36
    interest statements, and the SDG reasons of data/sdg_map.csv, each with how many lines it lacks."""
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    names = re.search(r"const NAMES = \{(.*?)\n\};", i18n, re.S).group(1)
    texts = re.search(r"const SDG_TEXT = \{(.*?)\n\};", i18n, re.S).group(1)
    name_rows = [json.loads(m) for m in re.findall(r":\s*(\[.*\]),", names)]
    text_rows = [json.loads(m) for m in re.findall(r":\s*(\[.*\]),", texts)]
    quiz = (STATIC / "quiz-i18n.js").read_text(encoding="utf-8")
    quiz_n = {}
    for lang in ("ms", "zh"):
        block = re.search(lang + r": \[(.*?)\n  \]", quiz, re.S)
        quiz_n[lang] = len(re.findall(r'^\s+"', block.group(1), re.M)) if block else 0
    reasons = []
    with SDG_MAP.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["rationale"] not in reasons:
                reasons.append(r["rationale"])
    why_file = STATIC / "sdg-i18n.js"
    why = {}
    if why_file.exists():
        for m in re.finditer(r'^\s*("(?:[^"\\]|\\.)*"):\s*(\[.*\]),\s*$', why_file.read_text(encoding="utf-8"), re.M):
            why[json.loads(m.group(1))] = json.loads(m.group(2))
    return {
        "goal_names": {"rows": len(name_rows), "missing_ms": sum(1 for r in name_rows if not r[0].strip()),
                       "missing_zh": sum(1 for r in name_rows if len(r) < 2 or not r[1].strip())},
        "goal_texts": {"rows": len(text_rows), "missing_ms": sum(1 for r in text_rows if len(r) < 2 or not r[1].strip()),
                       "missing_zh": sum(1 for r in text_rows if len(r) < 3 or not r[2].strip())},
        "interest_items": {"rows": 36, "missing_ms": 36 - quiz_n["ms"], "missing_zh": 36 - quiz_n["zh"]},
        "sdg_reasons": {"rows": len(reasons),
                        "missing_ms": sum(1 for e in reasons if not (e in why and why[e][0].strip())),
                        "missing_zh": sum(1 for e in reasons if not (e in why and len(why[e]) > 1 and why[e][1].strip()))},
    }


def source_rows() -> dict:
    """The Sources page's own words from /api/sources (what each source is used for, how it is refreshed):
    how many have a Bahasa Melayu and Chinese line in i18n.js. Names of sources are not counted."""
    sys.path.insert(0, str(ROOT / "src"))
    import main  # noqa: E402
    rows = json.loads(main.dispatch("GET", "/api/sources").body)["sources"]
    keys = tables()
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    if "function sourceText" not in app:
        return {"parts": 2 * len(rows), "untranslated": 2 * len(rows)}
    have = 0
    for r in rows:
        have += r["id"] in ("onet", "my_restrictions") or f"srcrow.{r['id']}.used" in keys
        have += (r["refresh"].startswith("Fetched again") or r["refresh"] == "Checked by hand."
                 or f"srcrow.{r['id']}.refresh" in keys)
    return {"parts": 2 * len(rows), "untranslated": 2 * len(rows) - have}


# --- contrast -----------------------------------------------------------------------------------

TEXT_ON = {  # text colour token -> backgrounds it is drawn on in style.css
    "ink": ("bg", "surface", "surface-2"),
    "muted": ("bg", "surface", "surface-2"),
    "brand": ("bg", "surface", "surface-2", "brand-soft"),
    "brand-strong": ("brand-soft", "surface"),
    "on-brand": ("brand",),
    "ai": ("surface", "ai-soft"),
    "rise": ("surface", "rise-soft"),
    "fall": ("surface", "fall-soft"),
    "steady": ("surface", "steady-soft"),
    "warn": ("surface", "warn-soft"),
}
AA = 4.5


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block))


def palettes() -> dict[str, dict[str, str]]:
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    light = _tokens(re.search(r":root\s*\{(.*?)\}", css, re.S).group(1))
    dark = _tokens(re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S).group(1))
    return {"light": light, "dark": {**light, **dark}}


def _lum(hex6: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex6[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(fg: str, bg: str) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return round((a + 0.05) / (b + 0.05), 2)


def contrast() -> list[dict]:
    rows = []
    for theme, pal in palettes().items():
        for fg, bgs in TEXT_ON.items():
            for bg in bgs:
                if fg in pal and bg in pal:
                    r = ratio(pal[fg], pal[bg])
                    rows.append({"theme": theme, "text": fg, "on": bg, "ratio": r, "pass": r >= AA})
    return rows


# --- the whole check ----------------------------------------------------------------------------

def run() -> dict:
    rows = tables()
    files = list(PAGE_FILES)
    used: dict[str, set] = {f: set() for f in files}
    for f in files:
        if f.endswith(".js"):
            used[f] = {m.group(2) for m in T_CALL.finditer((STATIC / f).read_text(encoding="utf-8"))}
    pages = {}
    for f in files:
        keys = used[f]
        missing = sorted(k for k in keys if k not in rows and k + ".one" not in rows)
        per = {}
        for lang in LANGS:
            fb = sorted(k for k in keys if k in rows and not rows[k][lang].strip())
            same = sorted(k for k in keys if k in rows and lang != "en" and rows[k][lang].strip()
                          and rows[k][lang] == rows[k]["en"] and _english(rows[k]["en"])
                          and lang not in KEEP_AS_IS.get(k, ()))
            per[lang] = {"missing_key": len(missing), "fallback": len(fb), "same_as_en": len(same),
                         "fallback_keys": fb, "same_keys": same}
        hard = hardcoded(f)
        pages[f] = {"pages": PAGE_FILES[f], "keys_used": len(keys), "missing_keys": missing, "langs": per,
                    "hardcoded": hard, "unlabelled": unlabelled(f)}
    # rows no page file names by a literal key may still be used through a built key ("scn." + id)
    all_rows = {lang: {"fallback": sorted(k for k, r in rows.items() if not r[lang].strip()),
                       "same_as_en": sorted(k for k, r in rows.items() if lang != "en" and r[lang] == r["en"]
                                            and _english(r["en"]) and lang not in KEEP_AS_IS.get(k, ()))}
                for lang in LANGS}
    con = contrast()
    totals = {lang: {"missing_key": sum(len(p["missing_keys"]) for p in pages.values()),
                     "fallback": len(all_rows[lang]["fallback"]),
                     "same_as_en": len(all_rows[lang]["same_as_en"]),
                     "hardcoded": sum(len(p["hardcoded"]) for p in pages.values())}
              for lang in LANGS}
    totals["en"]["hardcoded"] = 0  # English text is right for English
    return {"rows": len(rows), "pages": pages, "all_rows": all_rows, "totals": totals,
            "unlabelled": sum(len(p["unlabelled"]) for p in pages.values()),
            "contrast": con, "contrast_fail": sum(1 for c in con if not c["pass"]),
            "lang_attr": _lang_attr(), "indonesian": indonesian(), "side": side_tables(), "sources": source_rows(),
            "names": data_names()}


def _lang_attr() -> bool:
    """Does the page set <html lang> from the chosen language?"""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    return bool(re.search(r"document\.documentElement\.lang\s*=", app))


def summary(r: dict) -> dict:
    """The numbers the judge check's before/after table compares."""
    t = r["totals"]
    return {
        "9. UI strings missing or falling back to English, BM / ZH (of {} rows)".format(r["rows"]):
            f"{t['ms']['missing_key'] + t['ms']['fallback']} / {t['zh']['missing_key'] + t['zh']['fallback']}",
        "9. Rows whose BM / ZH text is the English text": f"{t['ms']['same_as_en']} / {t['zh']['same_as_en']}",
        "9. English text written into the page, not through i18n": t["ms"]["hardcoded"],
        "9. SDG reasons shown in English only, BM / ZH (of {})".format(r["side"]["sdg_reasons"]["rows"]):
            f"{r['side']['sdg_reasons']['missing_ms']} / {r['side']['sdg_reasons']['missing_zh']}",
        "9. Sources-page descriptions shown in English only (of {})".format(r["sources"]["parts"]):
            r["sources"]["untranslated"],
        "9. Names from the data shown in English only, BM / ZH (occupations, skills, MASCO groups, course notes; of {})"
        .format(sum(v["rows"] for v in r["names"].values())):
            "{} / {}".format(sum(v["missing_ms"] for v in r["names"].values()),
                             sum(v["missing_zh"] for v in r["names"].values())),
        "9. BM lines using an Indonesian word (rule of thumb)": len(r["indonesian"]),
        "9. Form fields with no label": r["unlabelled"],
        "9. Colour pairs below WCAG AA 4.5:1 (light + dark, of {})".format(len(r["contrast"])): r["contrast_fail"],
        "9. <html lang> follows the chosen language": "yes" if r["lang_attr"] else "no",
    }


def as_text(r: dict) -> str:
    out = [f"String rows: {r['rows']}", "", "| Page file (pages) | Keys used | Missing keys | BM fallback / same | "
           "ZH fallback / same | Hard-coded English | Unlabelled fields |", "|---|---|---|---|---|---|---|"]
    for f, p in r["pages"].items():
        ms, zh = p["langs"]["ms"], p["langs"]["zh"]
        out.append(f"| {f} ({p['pages']}) | {p['keys_used']} | {len(p['missing_keys'])} | {ms['fallback']} / "
                   f"{ms['same_as_en']} | {zh['fallback']} / {zh['same_as_en']} | {len(p['hardcoded'])} | "
                   f"{len(p['unlabelled'])} |")
    out += ["", "Totals (all rows, including those used through built keys): " + json.dumps(r["totals"]), ""]
    for f, p in r["pages"].items():
        for k in p["missing_keys"]:
            out.append(f"- missing key {f}: {k}")
        for h in p["hardcoded"]:
            out.append(f"- hard-coded {h['file']}:{h['line']} [{h['where']}] {h['text'][:100]}")
        for h in p["unlabelled"]:
            out.append(f"- no label {h['file']}:{h['line']} {h['text']}")
    for lang in ("ms", "zh"):
        for k in r["all_rows"][lang]["fallback"]:
            out.append(f"- {lang} fallback: {k}")
        for k in r["all_rows"][lang]["same_as_en"]:
            out.append(f"- {lang} same as English: {k}")
    for h in r["indonesian"]:
        out.append(f"- Indonesian word in ms {h['key']}: {h['word']}")
    out.append("- other tables: " + json.dumps(r["side"]))
    out.append("- names from the data: " + json.dumps(r["names"]))
    for c in r["contrast"]:
        if not c["pass"]:
            out.append(f"- contrast {c['theme']}: --{c['text']} on --{c['on']} = {c['ratio']}:1")
    out += ["", "Summary:"] + [f"- {k}: {v}" for k, v in summary(r).items()]
    return "\n".join(out)


def main_cli() -> int:
    cli = argparse.ArgumentParser(description="Count untranslated and hard-coded UI text, unlabelled fields and low contrast.")
    cli.add_argument("--json", action="store_true")
    opts = cli.parse_args()
    r = run()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(r, ensure_ascii=False, indent=1) if opts.json else as_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
