# Feasibility: who it reaches first, what it costs, how we would know it works

This page is the evidence behind the claim that Future Skills can be run for real. It keeps three things apart: what is **measured** or computed from this repository, what is a **published price**, and what is our **plan or assumption**. Nothing here is a result from real users: no pilot has run yet.

The figures come from two generated reports, so they can be checked by running the scripts again:

- [cost_model.md](cost_model.md), from `python scripts/cost_model.py --write`
- [kpi_report.md](kpi_report.md), from `python scripts/kpi.py --write`

## Who we reach first, and how

| | First | Later |
|---|---|---|
| Who uses it | Final-year students and recent graduates at one university or TVET career centre | Working adults through an employer's HR or L&D team |
| Who we talk to | The career-centre officer, who already advises these students | The HR or training manager |
| Why this order | No system to connect to: a link and one workshop are enough. The officer gets the Team view for a class | A company needs an agreement and, before real staff data, the privacy steps listed below |
| Channel | A one-hour workshop in a computer lab or on phones, then the link stays open | A session with one team, using job titles and headcounts only |

## What it costs to run

From [cost_model.md](cost_model.md), on the prices and assumptions listed there:

| People in a month | Servers | Total a month | Per person |
|---|---|---|---|
| 200 (a pilot) | 2 | about RM 50 | about RM 0.25 |
| 5,000 (one university) | 2 | about RM 71 | about RM 0.014 |
| 50,000 (many institutions) | 14 | about RM 560 | about RM 0.011 |

- The cost is set by the busiest moment, not by the number of people in the month: one workshop of 40 already needs two small servers.
- The language model is optional. Without a key the app writes the same explanation from a template, and only the hosting cost remains.
- The data sources are free and public. The weekly update runs by itself; about 6 hours of hands-on upkeep a quarter are assumed and not priced.
- The slowdown of a rented server against the laptop the app was timed on is an assumption. Timing the script on the real server replaces it.

## A pilot we could run

This is a plan, not something that has happened.

- **Size:** one career centre, 200 students in 5 workshops of 40, over 8 weeks.
- **What a student does:** the six steps once in the workshop (about 10 minutes), then follows the learning path on their own.
- **What the officer does:** opens a workshop check (the app's `#/pilot` page) and puts its code on the screen; opens the Team view for the class at the start and the end.
- **Consent and privacy:** the app stores no names, CVs or answers on the server; a student's answers stay in their browser. The only thing counted is the anonymous path tally (a random id, an occupation and hours). The clarity question below is asked inside the app by the workshop check: three picks from lists (an occupation, a skill, a free course) or "not sure yet", before and after, sent with a random browser id and the session code. No name and no typed text; only the officer's key opens the counts, and a session is deleted after 180 days.
- **Cost:** about RM 50 a month of hosting for two months.
- **We stop or change course if** fewer than half of the students finish the six steps in the workshop, or the officer finds the Team view does not help plan a session.

## How we would know it works

The Phase 1 KPIs against their baseline, worked out by code, are in [impact_verification.md](impact_verification.md): pathway coverage is past its 40% target; career clarity still needs the pilot below.

Computed now from the repository ([kpi_report.md](kpi_report.md)); these are the baseline and must not fall:

| KPI | Now | Level to keep |
|---|---|---|
| Path coverage: an occupation's skills and knowledge with a checked free resource | 90.8% on average, lowest 70.2% | 90% |
| Occupations with evidence grade A or B | 90.4% | 70% |
| Rows without a source, link and date | 0 of 2,241 | 0 |
| Every ranking that does not change with the scenario says why | yes | yes |

To be measured in the pilot; none has a value yet:

| KPI | Baseline | Target | How it is measured |
|---|---|---|---|
| Finishes the six steps in one sitting | not measured | 80% of students | Counted by the officer in the workshop |
| Can name a target occupation, its biggest skill gap and a first course | asked before the workshop | 70% after it | The workshop check in the app (`scripts/pilot.py`): the same three questions before and after, answers counted as given, every response kept and exportable. A second reading says how many answers also agree with the data. Fewer than 20 people who answered both times is shown as counts, never as a rate |
| Starts the learning path | 0 | 40% tick at least one resource within 8 weeks | The anonymous path tally on the SDG page |
| Hours of free study towards SDG 4.3, 4.4 and 8.5 | 0 | reported as counted, no target set | The same tally: planned and done hours per target |

An earlier version of this project reported a result from 20 testers. The response sheet does not support that number, so it is not used here or anywhere in this repository.

## Keeping the data fresh

| Source | How it is refreshed | Hands-on work |
|---|---|---|
| DOSM job ads, OpenDOSM wages, arXiv | Fetched again every 7 days and on "Update data" | A new DOSM workbook each quarter |
| Anthropic Economic Index | Every update checks for a newer release and only reports it | A person reviews a new release before it is used |
| MyCOL | Typed in when a new edition is published | Once a year or less |
| Course links | `python scripts/check_links.py` opens every link | Replace a link that stops working |

## Before real use

- A hosted version needs a privacy notice, HTTPS, access control for the Team view and a retention period for server logs (PDPA 2010). The prototype has none because it stores no personal data. The workshop check already has both of its own: results open only with the officer's key, and a session is deleted after 180 days.
- The app is for exploring careers and planning training. It must not be used to hire, dismiss or promote anyone.
- Every outlook is an estimate under a scenario the person picks. Two months of AI-usage data cannot be back-tested, so nothing is presented as a validated forecast.

## Who pays: not decided

The running cost above is the floor any price has to cover. Three ways to cover it, none chosen yet:

| Option | Who pays | What it has to cover | Open question |
|---|---|---|---|
| Free for everyone, hosted by one institution | A university or agency, as part of its career service | About RM 71 a month at 5,000 students | Who keeps the data current after the first year |
| Free for people, a yearly fee per institution for the Team view | Career centres, later HR teams | Hosting, plus the upkeep time someone has to be paid for | The fee; it needs at least one centre's answer |
| Sponsored by a public programme | A skills or employment agency | The same | Whether the agency wants its own hosting |

Decisions still to make, and by whom: the option above and any fee (the project owner, after talking to one career centre); who maintains the data once the first team moves on; whether a hosted version uses a language model at all.
