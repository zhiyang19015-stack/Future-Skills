# Labelling rules for the evaluation set

Synthetic data, not validated with real people. These rules were written on 2026-11-17, before the labels, and the labels were written before any person in `eval/personas.json` was run through the app.

## Who labels, and what they see

- The labels in `eval/labels.json` were written by an independent annotator: a separate Claude agent that never saw the app's code, its scoring rules or any of its output.
- It saw only `eval/annotator_view.md` (each person's story and profile in words), `eval/occupation_list.csv` (the 910 occupations with field, education level and the O*NET description) and this file.
- Its labels are committed before `scripts/eval.py` is first run on these people. `docs/eval_results.json` stores the sha256 of `eval/labels.json` so a later change to the labels shows.

## Tuning set and held-out set

- **Tuning set:** the 5 demo people in `data/sample_profiles.json` (P01 to P05). The scoring rules were tuned on them in stages 1 to 5. They are reported apart and are not in the headline numbers.
- **Held-out set:** the 40 people in `eval/personas.json` (E01 to E40), with 10 each of students, people in work, switchers and job seekers. No rule, weight or data file of the app is changed because of their results. If a result is bad, it is reported as it is.

## What the profile means

- **Education level:** the O*NET job zone the person has reached. 1 = little or no schooling needed; 2 = SPM or some training; 3 = diploma, skills certificate or vocational training; 4 = bachelor's degree; 5 = postgraduate.
- **Will study:** how many levels above that the person says they would study for (0, 1 or 2).
- **Interests:** the three Holland (RIASEC) types they like most, in order, and the one they like least. R = hands-on, I = investigating, A = creative, S = helping people, E = persuading and leading, C = organising and records.
- **Fields:** the O*NET major groups they want to work in, with a weight from 0 to 100.
- **Group:** student, in work, switcher or job seeker. A job seeker is a fresh graduate (sent to the app as a student) or someone who lost or is leaving a job (sent as a switcher).

## The two labels for each person

1. **acceptable** (3 to 20 occupation ids): occupations a careful Malaysian career counsellor would accept as a sensible *next move* for this person. Each must:
   - be reachable with the person's education plus the levels they would study for (job zone at most level + will study);
   - fit what the story says they want, or clearly use the skills, tools and interests they have;
   - not be the job they already do.
2. **not_acceptable** (0 to 15 occupation ids): occupations that would be a clear mistake in this person's top 5. List only mistakes a recommender could plausibly make: occupations in or near the person's fields that
   - need much more education than they will study for (job zone above level + will study + 1), or
   - go against something the story says they do not want, or
   - need a licence or registration the person cannot get with their plans.

An occupation is in at most one of the two lists. Anything in neither list is "not judged": it counts neither for nor against the app.

## How the labels are scored (scripts/eval.py)

- **First move agrees:** the first occupation in the person's list that is not their own job is in *acceptable*.
- **Top 5 agrees:** at least one of the first 5 such occupations is in *acceptable*.
- **Top 5 has a mistake:** at least one of the first 5 is in *not_acceptable*.

All three use the moderate adoption scenario. Each share comes with a 95% Wilson interval: with 40 people a share is only known to within about ±15 points.

## Rules that need no label

These are checked by rule on every learning plan, the same for every person:

- **Courses that should not be there:** a job-search course (CV, résumé, interview, cover letter, job search) for someone in work; a paid course counted in the free plan; a course for a skill the person already rates at or above what the occupation needs; the same course twice.
- **Free share:** the share of the plan's resources that cost RM 0.
- **Not in English:** the share of the plan's resources whose language is not English.
- **Scenario changes:** the share of people whose first move, or the set of occupations in their top 5, differs between slow and fast adoption.
