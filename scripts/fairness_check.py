"""Check that recommendations do not depend on who the person is.

The same fictional CV (src/static/sample_cv.txt) is sent eight times, each time as a different
person: the name, gender, age, religion, ethnicity and home state change; the qualifications,
tools and work history do not. Each CV goes through the real app path:

    POST /api/cv/summary -> tools, education level, subjects, job titles, field evidence
    POST /api/match      -> field fit and every occupation's score (same interest answers each time)

A fair result is the same for all eight: the same tools found, the same field fits, the same
occupations in the same order with the same scores. The personal details are also sent in the
match request itself (gender, age, ethnicity, religion, state), to show the API ignores them.
The script prints the largest difference seen and exits 1 if there is any.

    python scripts/fairness_check.py        (tests/test_fairness.py runs it)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import main  # noqa: E402

SAMPLE = (ROOT / "src" / "static" / "sample_cv.txt").read_text(encoding="utf-8")
FIRST_LINE = SAMPLE.splitlines()[0]
PEOPLE = [  # fictional people only; each changes who the person is, never what they can do
    {"name": "SITI HAJAR BINTI ROSLAN", "gender": "Female", "age": 26, "ethnicity": "Malay", "religion": "Islam", "state": "Perak"},
    {"name": "MUHAMMAD HAFIZ BIN ISMAIL", "gender": "Male", "age": 27, "ethnicity": "Malay", "religion": "Islam", "state": "Terengganu"},
    {"name": "TAN MEI LING", "gender": "Female", "age": 25, "ethnicity": "Chinese", "religion": "Buddhism", "state": "Penang"},
    {"name": "LIM WEI JIE", "gender": "Male", "age": 29, "ethnicity": "Chinese", "religion": "Christianity", "state": "Johor"},
    {"name": "PRIYA A/P RAJENDRAN", "gender": "Female", "age": 24, "ethnicity": "Indian", "religion": "Hinduism", "state": "Selangor"},
    {"name": "ARJUN A/L MURUGAN", "gender": "Male", "age": 31, "ethnicity": "Indian", "religion": "Hinduism", "state": "Kedah"},
    {"name": "JANET ANAK JUGAH", "gender": "Female", "age": 38, "ethnicity": "Iban", "religion": "Christianity", "state": "Sarawak"},
    {"name": "MOHD FAIZAL BIN JUMAT", "gender": "Male", "age": 44, "ethnicity": "Kadazan-Dusun", "religion": "Islam", "state": "Sabah"},
]
INTEREST = next(p for p in json.loads((ROOT / "data" / "sample_profiles.json").read_text(encoding="utf-8"))
                if p["profile_id"] == "P02")["interest_answers"]
DETAILS = ("gender", "age", "ethnicity", "religion", "state")


def cv_for(person: dict) -> str:
    header = (f"{person['name']} (fictional sample CV)\n{person['gender']}, age {person['age']}, "
              f"{person['ethnicity']}, {person['religion']}, {person['state']}")
    return SAMPLE.replace(FIRST_LINE, header, 1)


def post(path: str, body: dict) -> dict:
    res = main.dispatch("POST", path, json.dumps(body).encode("utf-8"))
    out = json.loads(res.body)
    if res.status != 200:
        raise RuntimeError(f"{path}: {res.status} {out}")
    return out


def run_one(person: dict, with_details: bool = False) -> dict:
    cv = post("/api/cv/summary", {"text": cv_for(person)})
    body = {"kind": "working", "interest_answers": INTEREST, "cv_fields": cv["cv_fields"], "cv_why": cv["cv_why"],
            "cv_skills": cv["cv_skills"], "technologies": [t["skill_id"] for t in cv["technologies"]],
            "education_job_zone": cv["education_job_zone"] or 4, "top": 30}
    if with_details:
        body.update({k: person[k] for k in DETAILS})
    res = post("/api/match", body)
    return {"technologies": sorted(t["skill_id"] for t in cv["technologies"]), "cv_fields": cv["cv_fields"],
            "fields": {f["id"]: f["fit"] for f in res["fields"]},
            "occupations": [(m["occ_id"], m["total"]) for m in res["results"]],
            "titles": {m["occ_id"]: m["title"] for m in res["results"]}}


def largest_gap(results: list[dict]) -> dict:
    base = results[0]
    gap = {"technologies": 0, "cv_field": 0.0, "field_fit": 0.0, "order": 0, "score": 0.0}
    for r in results[1:]:
        gap["technologies"] += r["technologies"] != base["technologies"]
        for key, part in (("cv_field", "cv_fields"), ("field_fit", "fields")):
            for f in set(base[part]) | set(r[part]):
                x, y = base[part].get(f), r[part].get(f)
                gap[key] = max(gap[key], 100.0 if (x is None) != (y is None) else abs((x or 0) - (y or 0)))
        gap["order"] += [o for o, _ in r["occupations"]] != [o for o, _ in base["occupations"]]
        scores = dict(r["occupations"])
        gap["score"] = max([gap["score"]] + [abs(s - scores.get(o, -100)) for o, s in base["occupations"]])
    return gap


def check() -> dict:
    results = [run_one(p) for p in PEOPLE] + [run_one(p, with_details=True) for p in PEOPLE]
    gap = largest_gap(results)
    return {"people": len(PEOPLE), "occupations": len(results[0]["occupations"]), "gap": gap,
            "fair": not any(gap.values()), "results": results[:len(PEOPLE)]}


def main_cli() -> int:
    out = check()
    print(f"Fairness check: {out['people']} fictional people, the same CV, different name, gender, age, "
          f"ethnicity, religion and state.")
    for p, r in zip(PEOPLE, out["results"]):
        top = ", ".join(f"{r['titles'][o]} {s}" for o, s in r["occupations"][:3])
        print(f"  {p['ethnicity']:<14} {p['gender']:<6} age {p['age']:<3} {p['religion']:<12} -> {top}")
    g = out["gap"]
    print(f"Largest difference over {out['occupations']} occupations, with and without the details in the request: "
          f"tools differ for {g['technologies']}; CV field evidence {g['cv_field']}; field fit {g['field_fit']}; "
          f"order differs for {g['order']}; score {g['score']}")
    print("PASS: recommendations do not depend on personal details." if out["fair"]
          else "FAIL: some recommendations changed with personal details.")
    return 0 if out["fair"] else 1


if __name__ == "__main__":
    sys.exit(main_cli())
