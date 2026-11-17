"""The evaluation people (eval/personas.json): turn each into an app profile, and write what the annotator sees.

The annotator never sees the app's code or output (eval/LABELING.md). It gets two files made here
from the personas and the data alone, without running the app:

    eval/annotator_view.md     each person's story and profile in words
    eval/occupation_list.csv   the 910 occupations: id, title, field, education level, description

Interest answers: a person is written with the three Holland types they like most and the one they
like least. The 36 questionnaire answers are made from that by one fixed rule, the same for everyone:
an item of the 1st type is answered 5, of the 2nd 4, of the 3rd 4, of the least-liked type 1, any
other 2.

    python scripts/eval_personas.py     # write the two annotator files
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
DATA = ROOT / "data"
PERSONAS = EVAL / "personas.json"
LABELS = EVAL / "labels.json"
TYPE_WORDS = {"R": "hands-on (Realistic)", "I": "investigating (Investigative)", "A": "creative (Artistic)",
              "S": "helping people (Social)", "E": "persuading and leading (Enterprising)",
              "C": "organising and records (Conventional)"}
ZONE_WORDS = {1: "little or no schooling", 2: "SPM or some training", 3: "diploma, skills certificate or vocational",
              4: "bachelor's degree", 5: "postgraduate"}
GROUP_WORDS = {"student": "student", "working": "in work", "switcher": "switcher", "jobseeker": "job seeker"}
TOP_ANSWER = (5, 4, 4)
LOW_ANSWER = 1
OTHER_ANSWER = 2


def read_csv(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def people() -> list[dict]:
    return json.loads(PERSONAS.read_text(encoding="utf-8"))["people"]


def interest_answers(types: dict) -> list[int]:
    items = json.loads((DATA / "interest_items.json").read_text(encoding="utf-8"))
    items = items["items"] if isinstance(items, dict) else items
    value = {t: a for t, a in zip(types["top"], TOP_ANSWER)}
    out = []
    for it in items:
        t = it["type"]
        out.append(value.get(t, LOW_ANSWER if t == types.get("low") else OTHER_ANSWER))
    return out


def app_profile(person: dict) -> dict:
    """The body the app's API takes for this person (src/main.py: "A profile ... has any of")."""
    p = dict(person["profile"])
    p["interest_answers"] = interest_answers(p.pop("interest_types"))
    return p


def annotator_view() -> str:
    fields = {r["field_id"]: r["name_en"] for r in read_csv("fields.csv")}
    occ = {r["occ_id"]: r["title"] for r in read_csv("occupations.csv")}
    tech = {r["tech_id"]: r["name"] for r in read_csv("technologies.csv")}
    el = {r["element_id"]: r["name"] for r in read_csv("elements.csv")}
    lines = ["# The 40 evaluation people, as the annotator sees them", "",
             "Fictional people. Synthetic data, not validated with real people. Label them by the rules in "
             "`eval/LABELING.md`, choosing occupation ids from `eval/occupation_list.csv`.", ""]
    for x in people():
        p = x["profile"]
        it = p["interest_types"]
        lines += [f"## {x['id']} {x['name']} ({GROUP_WORDS[x['group']]})", "", x["story"], "",
                  f"- Education level: {p['education_job_zone']} ({ZONE_WORDS[p['education_job_zone']]}); "
                  f"will study {p.get('study_levels', 0)} level(s) more",
                  f"- Job now: {occ[p['current_occupation']] + ' (' + p['current_occupation'] + ')' if p.get('current_occupation') else 'none'}",
                  "- Fields wanted: " + "; ".join(f"{fields[f]} ({f}) {w}" for f, w in p["fields"].items()),
                  "- Interests, most liked first: " + ", ".join(TYPE_WORDS[t] for t in it["top"])
                  + f"; least liked: {TYPE_WORDS[it['low']]}",
                  "- Tools used: " + (", ".join(tech[t] for t in p["technologies"]) or "none named"),
                  "- Skills they rate themselves on (0-7): " + (", ".join(f"{el[e]} {v}" for e, v in p["skills"].items()) or "none"),
                  f"- Study time: {p['hours_per_week']} hours a week", ""]
    return "\n".join(lines)


def write_annotator_files() -> None:
    (EVAL / "annotator_view.md").write_text(annotator_view(), encoding="utf-8")
    fields = {r["field_id"]: r["name_en"] for r in read_csv("fields.csv")}
    with open(EVAL / "occupation_list.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["occ_id", "title", "field_id", "field", "job_zone", "description"])
        for r in read_csv("occupations.csv"):
            w.writerow([r["occ_id"], r["title"], r["field_id"], fields.get(r["field_id"], ""), r["job_zone"],
                        r["description"]])


if __name__ == "__main__":
    write_annotator_files()
    print("wrote eval/annotator_view.md and eval/occupation_list.csv")
