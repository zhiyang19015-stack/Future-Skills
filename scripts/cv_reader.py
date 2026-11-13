"""Read a CV (or a job ad) with plain word matching: no LLM, the same answer every time.

From the text it finds:
    technologies    names from data/technologies.csv (O*NET Hot and In Demand technologies),
                    with their usual short forms: "MS Excel", "AutoCAD", "SQL"
    qualifications  lines that name a qualification, and the highest one as a Job Zone:
                    SPM or a skills certificate 2, STPM / foundation / diploma 3, a bachelor's
                    degree 4, a master's or doctorate 5 (Malaysian and international names)
    knowledge       the subject of each qualification line ("Diploma in Accounting") as an O*NET
                    knowledge area, at a level that follows the qualification (KNOWLEDGE_LEVEL)
    job titles      O*NET titles, titles people in each occupation reported, and common
                    Malaysian job titles (MALAYSIAN_TITLES): evidence for the job's field

The text is used for the one request and never stored. A CV that words things differently is
missed rather than guessed, and the page says how the CV was read.
"""

import base64
import binascii
import html
import io
import re
import zipfile

MAX_CHARS = 60_000
TITLE_EVIDENCE = 70.0  # experience evidence for a field whose job title the CV names
EDUCATION = [  # (Job Zone, pattern), highest first
    (5, r"\b(ph\.?\s?d|doctor of philosophy|doktor falsafah|master'?s?|m\.?\s?sc|mba|m\.?\s?eng|m\.?\s?ed|sarjana(?! muda))\b"),
    (4, r"\b(bachelor'?s?|b\.?\s?sc|b\.?\s?a\b|b\.?\s?eng|b\.?\s?ed|b\.?\s?com|bba|ijazah sarjana muda|ijazah|degree|honours|\(hons\))"),
    (3, r"\b(diploma|dkm|diploma kemahiran|advanced diploma|stpm|a-?levels?|matriculation|matrikulasi|foundation|asasi|"
        r"skm (tahap|level) 3)\b"),
    (2, r"\b(spm|o-?levels?|igcse|skm|sijil kemahiran|certificate|sijil)\b"),
]
KNOWLEDGE_LEVEL = {5: 5.0, 4: 4.0, 3: 3.0, 2: 2.0}
KNOWLEDGE_WORDS = {  # O*NET knowledge area -> subject words in a qualification line
    "2.C.1.a": r"business administration|management|pengurusan",
    "2.C.1.b": r"office management|secretarial|kesetiausahaan",
    "2.C.1.c": r"accounting|accountancy|finance|economics|perakaunan|kewangan|ekonomi|banking",
    "2.C.1.d": r"marketing|sales|pemasaran",
    "2.C.1.e": r"hospitality|customer service|tourism|pelancongan|hotel",
    "2.C.1.f": r"human resource|sumber manusia",
    "2.C.2.a": r"manufacturing|production|pembuatan",
    "2.C.2.b": r"agricultur|food science|food technology|culinary|kulinari|pertanian|aquaculture|plantation",
    "2.C.3.a": r"computer|information technology|\bict\b|software|data science|cyber|komputer|teknologi maklumat",
    "2.C.3.b": r"engineering|kejuruteraan",
    "2.C.3.c": r"design|architecture|seni bina|reka bentuk",
    "2.C.3.d": r"construction|civil engineering|building|quantity surveying|pembinaan",
    "2.C.3.e": r"mechanical|mekanikal|automotive|mechatronic",
    "2.C.4.a": r"mathematic|statistic|actuarial|matematik|statistik",
    "2.C.4.b": r"physics|fizik",
    "2.C.4.c": r"chemistry|chemical|kimia",
    "2.C.4.d": r"biology|biotechnology|biomedical|microbiology|biologi|bioteknologi",
    "2.C.4.e": r"psychology|psikologi",
    "2.C.4.f": r"sociology|anthropology|social science|sosiologi",
    "2.C.4.g": r"geography|geomatic|\bgis\b|geografi",
    "2.C.5.a": r"medicine|medical|dentistry|nursing|pharmacy|perubatan|kejururawatan|farmasi|mbbs",
    "2.C.5.b": r"counsel|therapy|physiotherapy|occupational therapy|kaunseling|fisioterapi",
    "2.C.6": r"education|teaching|tesl|pendidikan|perguruan",
    "2.C.7.a": r"english|tesl|bahasa inggeris",
    "2.C.7.b": r"mandarin|chinese|arabic|japanese|korean|french|german|bahasa cina|bahasa arab",
    "2.C.7.c": r"fine art|music|art and design|seni halus|muzik|animation|multimedia",
    "2.C.7.d": r"history|archaeolog|sejarah",
    "2.C.7.e": r"philosophy|islamic studies|theology|usuluddin|syariah|pengajian islam",
    "2.C.8.a": r"security|criminology|fire|keselamatan|kriminologi",
    "2.C.8.b": r"\blaw\b|\bllb\b|legal|undang-undang|public administration|political science",
    "2.C.9.a": r"telecommunication|telekomunikasi|network",
    "2.C.9.b": r"mass communication|journalism|media|broadcasting|komunikasi",
    "2.C.10": r"logistic|transport|supply chain|aviation|maritime|logistik|pengangkutan",
}
# Common Malaysian job titles that O*NET words differently -> the closest O*NET occupation
MALAYSIAN_TITLES = {
    "accounts executive": "13-2011.00", "account executive (finance)": "13-2011.00",
    "accounts assistant": "43-3031.00", "account assistant": "43-3031.00", "account clerk": "43-3031.00",
    "admin executive": "43-6014.00", "administrative executive": "43-6014.00", "admin assistant": "43-6014.00",
    "admin clerk": "43-9061.00", "kerani": "43-9061.00", "general clerk": "43-9061.00",
    "staff nurse": "29-1141.00", "jururawat": "29-1141.00", "medical officer": "29-1215.00",
    "pegawai perubatan": "29-1215.00", "medical assistant": "31-9092.00", "pembantu perubatan": "31-9092.00",
    "software engineer": "15-1252.00", "web developer": "15-1254.00", "data analyst": "15-2051.01",
    "it executive": "15-1232.00", "it support": "15-1232.00", "system engineer": "15-1244.00",
    "sales executive": "41-4012.00", "sales assistant": "41-2031.00", "promoter": "41-2031.00",
    "juruwang": "41-2011.00", "cashier": "41-2011.00", "kitchen helper": "35-2021.00",
    "waiter": "35-3031.00", "waitress": "35-3031.00", "barista": "35-3023.01",
    "lorry driver": "53-3032.00", "pemandu lori": "53-3032.00", "despatch rider": "43-5021.00",
    "dispatch rider": "43-5021.00", "production operator": "51-2092.00", "operator pengeluaran": "51-2092.00",
    "qc inspector": "51-9061.00", "quality inspector": "51-9061.00", "customer service executive": "43-4051.00",
    "customer service officer": "43-4051.00", "hr executive": "13-1071.00", "human resource executive": "13-1071.00",
    "marketing executive": "13-1161.00", "pengawal keselamatan": "33-9032.00", "security guard": "33-9032.00",
    "cleaner": "37-2011.00", "tukang cuci": "37-2011.00",
    "guru tadika": "25-2012.00", "kindergarten teacher": "25-2012.00", "primary school teacher": "25-2021.00",
    "secondary school teacher": "25-2031.00", "chef de partie": "35-1011.00", "kitchen chef": "35-1011.00",
    "site supervisor": "47-1011.00", "quantity surveyor": "13-1051.00", "draughtsman": "17-3011.00",
    "juruteknik": "49-9071.00", "maintenance technician": "49-9071.00", "pharmacy assistant": "29-2052.00",
}
GENERIC = {"manager", "director", "assistant", "operator", "technician", "specialist", "consultant", "engineer",
           "analyst", "designer", "officer", "executive", "supervisor", "coordinator", "teacher", "driver",
           "worker", "helper", "clerk", "instructor", "inspector", "administrator", "associate", "agent", "advisor",
           "adviser", "representative", "trainer", "planner", "developer", "programmer", "scientist", "artist",
           "writer", "editor", "producer", "leader", "lead", "owner", "partner", "president", "founder", "intern",
           "student", "volunteer", "head", "chief", "member", "staff", "secretary", "receptionist", "tutor"}
# vendor words a tool is often named without ("MS Excel", "Excel")
VENDORS = ("microsoft ", "ms ", "google ", "adobe ", "autodesk ", "oracle ", "ibm ", "sap ", "apple ", "intuit ",
           "dassault systemes ", "esri ", "the mathworks ", "mathworks ", "atlassian ", "amazon ", "cisco ")
COMMON_WORDS = {"word", "access", "project", "teams", "outlook", "edge", "office", "publisher", "sheets", "docs", "meet",
                "drive", "slides", "forms", "safari", "windows", "excel", "go", "chef", "puppet", "shell", "visio",
                "word processing software", "spreadsheet software", "email", "zoom", "slack", "asana", "canva", "git",
                "analytics", "google", "cloud", "workspace", "database", "data", "reporting", "payroll", "business software",
                "software applications", "creative cloud"}
SHORT_FORMS = {"c": r"\bC (?:programming|language)\b|\bANSI C\b", "r": r"\bR (?:programming|language|Studio)\b|\bRStudio\b",
               "microsoft-excel": r"\b(?:MS |Microsoft )?Excel\b", "microsoft-word": r"\b(?:MS|Microsoft) Word\b",
               "microsoft-powerpoint": r"\b(?:MS |Microsoft )?PowerPoint\b", "microsoft-outlook": r"\b(?:MS |Microsoft )Outlook\b",
               "microsoft-access": r"\b(?:MS|Microsoft) Access\b", "microsoft-project": r"\b(?:MS|Microsoft) Project\b",
               "microsoft-teams": r"\b(?:MS |Microsoft )Teams\b", "google-sheets": r"\bGoogle Sheets\b",
               "google-docs": r"\bGoogle Docs\b", "zoom": r"\bZoom\b", "slack": r"\bSlack\b", "canva": r"\bCanva\b"}


class CVReadError(ValueError):
    """A CV that cannot be read; the text says why and goes back to the person."""


def docx_text(raw: bytes) -> str:
    """The text of a Word file: paragraph ends, line breaks and tabs become new lines."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError) as e:
        raise CVReadError("That .docx file could not be read") from e
    xml = re.sub(r"</w:p>|<w:br/>|<w:tab/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def read_text(body: dict) -> str:
    """The text of a request: {"text": ...} or {"docx_base64": ...}."""
    if isinstance(body.get("text"), str):
        text = body["text"]
    elif isinstance(body.get("docx_base64"), str):
        try:
            text = docx_text(base64.b64decode(body["docx_base64"], validate=True))
        except binascii.Error as e:
            raise CVReadError("'docx_base64' is not valid base64") from e
    else:
        raise CVReadError("send the CV as 'text' or 'docx_base64'")
    text = text[:MAX_CHARS]
    if len(text.strip()) < 40:
        raise CVReadError("The CV text is too short to read (at least 40 characters)")
    return text


def tool_patterns(technologies: dict) -> list[tuple[str, re.Pattern]]:
    out = []
    for tid, t in technologies.items():
        if tid in SHORT_FORMS:
            out.append((tid, re.compile(SHORT_FORMS[tid])))
            continue
        name = t["name"]
        forms = {name.lower()}
        if name.lower().endswith(" software"):
            forms.add(name.lower()[:-9])
        for v in VENDORS:
            for f in list(forms):
                if f.startswith(v):
                    forms.add(f[len(v):])
        acronym = re.search(r"\s([A-Z][A-Z0-9+#]{2,})$", name)  # "Structured query language SQL" -> "SQL"
        if acronym and len(name.split()) >= 3:
            forms.add(acronym.group(1).lower())
        forms = {f.strip() for f in forms if len(f.strip()) >= 3 and f.strip() not in COMMON_WORDS}
        if forms:
            alt = "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
            out.append((tid, re.compile(rf"(?<![\w+#])(?:{alt})(?![\w+#])", re.IGNORECASE)))
    return out


_patterns = {"key": None, "value": None}


def find_technologies(text: str, technologies: dict) -> list[dict]:
    """Technologies the text names, each with the words that matched, in the order they appear."""
    key = id(technologies)
    if _patterns["key"] != key:
        _patterns.update(key=key, value=tool_patterns(technologies))
    found = []
    for tid, pattern in _patterns["value"]:
        m = pattern.search(text)
        if m:
            found.append((m.start(), {"skill_id": tid, "skill_name": technologies[tid]["name"], "matched": m.group(0)}))
    return [f for _, f in sorted(found, key=lambda x: x[0])]


def qualifications(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        clean = line.strip(" -•*\t")
        if not clean or len(clean) > 200:
            continue
        for zone, pattern in EDUCATION:
            if re.search(pattern, clean, re.IGNORECASE):
                out.append({"title": clean, "job_zone": zone})
                break
    return out


def knowledge(quals: list[dict], elements: dict) -> list[dict]:
    """O*NET knowledge areas named in qualification lines, at the level the qualification gives."""
    best = {}
    for q in quals:
        for eid, words in KNOWLEDGE_WORDS.items():
            m = re.search(words, q["title"], re.IGNORECASE)
            if m and eid in elements:
                level = KNOWLEDGE_LEVEL[q["job_zone"]]
                if level > best.get(eid, {}).get("level", -1):
                    best[eid] = {"element_id": eid, "name": elements[eid]["name"], "level": level,
                                 "matched": m.group(0), "from": q["title"]}
    return list(best.values())


def singular(title: str) -> str:
    words = title.split()
    last = words[-1]
    if last.endswith("ies"):
        last = last[:-3] + "y"
    elif last.endswith("s") and not last.endswith("ss"):
        last = last[:-1]
    return " ".join(words[:-1] + [last])


def title_index(data: dict) -> dict:
    """lowercase title -> occ_id: O*NET titles (and the parts of an "A and B" title that are titles of
    their own), the titles people in each occupation reported, and common Malaysian titles. One-word
    titles come only from reported titles, so a CV heading such as "EDUCATION" is never a job."""
    index = {}

    def add(title, occ_id, single_ok=True):
        t = re.sub(r"\s*\(.*?\)", "", title).strip().lower()
        words = t.split()
        if not words or all(w in GENERIC for w in words):
            return
        if len(words) == 1 and (not single_ok or len(t) < 7):
            return
        index.setdefault(t, occ_id)
    for occ in data["occupations"]:
        base = occ["title"].split(" Except")[0].split(",")[0].strip()
        add(singular(base), occ["occ_id"], single_ok=False)
        for part in base.split(" and "):
            add(singular(part.strip()), occ["occ_id"], single_ok=False)
        for r in data["titles"].get(occ["occ_id"], []):
            add(r["title"], occ["occ_id"])
    for t, occ_id in MALAYSIAN_TITLES.items():
        if occ_id in data["by_id"]:
            index[t] = occ_id
    return index


_titles = {"key": None, "value": None}


WORK_HEADINGS = re.compile(r"experience|employment|work history|career|pengalaman|pekerjaan|工作", re.IGNORECASE)


def work_sections(text: str) -> str:
    """The parts of a CV under a work-experience heading; the whole text when it has none.
    A heading is a short line in capitals or ending with a colon ("EXPERIENCE", "Pengalaman Kerja:"),
    so a title under ACTIVITIES (a club's treasurer) is not read as a job."""
    lines = text.splitlines()
    heads = [i for i, line in enumerate(lines) if 0 < len(line.strip()) <= 40
             and (line.strip().isupper() or line.strip().endswith(":"))]
    if not any(WORK_HEADINGS.search(lines[i]) for i in heads):
        return text
    parts = []
    for n, i in enumerate(heads):
        if WORK_HEADINGS.search(lines[i]):
            end = heads[n + 1] if n + 1 < len(heads) else len(lines)
            parts.extend(lines[i + 1:end])
    return "\n".join(parts)


def find_titles(text: str, data: dict) -> list[dict]:
    """Occupations whose titles the text names, in order (for a CV, only its work sections)."""
    key = id(data["occupations"])
    if _titles["key"] != key:
        index = title_index(data)
        alt = "|".join(re.escape(t) for t in sorted(index, key=len, reverse=True))
        _titles.update(key=key, value=(index, re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)))
    index, pattern = _titles["value"]
    seen = {}
    for m in pattern.finditer(text):
        occ_id = index[m.group(0).lower()]
        seen.setdefault(occ_id, m.group(0))
    return [{"occ_id": o, "title": data["by_id"][o]["title"], "field_id": data["by_id"][o]["field_id"], "matched": w}
            for o, w in list(seen.items())[:6]]


def summarise(body: dict, data: dict) -> dict:
    text = read_text(body)
    techs = find_technologies(text, data["technologies"])
    quals = qualifications(text)
    zone = max((q["job_zone"] for q in quals), default=None)
    known = knowledge(quals, data["elements"])
    jobs = find_titles(work_sections(text), data)
    fields, why = {}, {}
    for j in jobs:
        if j["field_id"] not in fields:
            fields[j["field_id"]] = TITLE_EVIDENCE
            why[j["field_id"]] = f"your CV names {j['matched']} ({j['title']})"
    parts = [f"{len(techs)} tool{'s' if len(techs) != 1 else ''}"]
    if zone:
        parts.append(f"a qualification at Job Zone {zone}")
    if known:
        parts.append(f"{len(known)} subject area{'s' if len(known) != 1 else ''}")
    if jobs:
        parts.append(f"{len(jobs)} job title{'s' if len(jobs) != 1 else ''}")
    return {"summary": "Found " + ", ".join(parts) + ".", "source": "match", "technologies": techs,
            "qualifications": quals[:6], "education_job_zone": zone, "knowledge": known,
            "cv_skills": {k["element_id"]: k["level"] for k in known}, "occupations": jobs,
            "cv_fields": fields, "cv_why": why,
            "method": "Word match against O*NET technology names and job titles and a list of qualification "
                      "words; no LLM. The CV was used for this request only and not stored."}
