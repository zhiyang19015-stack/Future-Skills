# Sources and Licences

Every number the app shows comes from one of the sources below, and every row in `data/` names its source and date (`source_name`, `source_url`, `source_date`), or its table's source is recorded in `data/aei/source.json`. Malaysian demand comes from DOSM and MyCOL only; O*NET (US) describes the work itself and never stands in for a Malaysian number. Dates are `YYYY-MM-DD`; for a download, `source_date` is the day it was downloaded.

## Data sources

| Source | Used for | Format, refresh | Licence |
|---|---|---|---|
| [O*NET 31.0 Database](https://www.onetcenter.org/database.html) | The 910 occupations: descriptions, Job Zones, interest profiles (RIASEC), skills and knowledge with importance and level, Hot and In Demand technologies, task statements and their importance, detailed work activities, reported job titles, related occupations, and the level examples of the skills check | CSV per file; re-extracted when O*NET publishes a new database (`scripts/build_onet.py`) | CC BY 4.0 |
| [Anthropic Economic Index](https://huggingface.co/datasets/Anthropic/EconomicIndex), release 2026-06-26 (Claude.ai use in April and May 2026), pinned at revision `4e5f69f` and checked by sha256 | The AI share of every task, the hands-off share of work activities and request topics, occupation and field usage, Malaysia next to the world | 219 MB CSV, cut to our rows by `scripts/ai_exposure_extract.py`; a newer release is only reported, and a person reviews it before it is used | CC-BY |
| [Anthropic, Labor market impacts of AI](https://www.anthropic.com/research/labor-market-impacts) (2026-03-05), `labor_market_impacts/` in the same dataset | The second reading of each task's AI share (task penetration) and, for thinly measured occupations, the prior (observed exposure) | CSV | CC-BY |
| [ESCO–O*NET occupation crosswalk](https://esco.ec.europa.eu/en/use-esco/other-crosswalks) (European Commission with the US DOL, September 2022) and the [ESCO API](https://ec.europa.eu/esco/api/) (ESCO v1.1) | Each O*NET occupation's ISCO-08 unit group, which links it to Malaysia's MASCO 2020, to MyCOL and to DOSM's figures by MASCO major group | CSV (3 MB) and API look-ups, read once by `scripts/build_onet.py` | EU open data |
| [MyCOL 2024/2025](https://www.talentcorp.com.my/images/uploads/publication/205/MyMahir-MyCOL-20242025-Brochure-1773377416.pdf) (TalentCorp, MyMahir) | Malaysian demand: whether an occupation is on Malaysia's critical-occupations list | The 66 occupations typed from the brochure (`raw/mycol/mycol_2024_2025.csv`), linked to ISCO-08 in `data/mycol_map.csv` | Public document |
| [DOSM Job Market Insights, "Data JMI Q2 2026"](https://www.dosm.gov.my/portal-main/release-document-log?release_document_id=20742) | Malaysian demand: online job ads by MASCO major group, per quarter | Excel workbook in `raw/dosm/`; a new one each quarter | DOSM terms of use, with attribution |
| [OpenDOSM `wages_occupation`](https://open.dosm.gov.my/data-catalogue/wages_occupation) | The median monthly wage of each MASCO major group (shown as context, not scored) | API, fetched by "Update data" | OpenDOSM terms, with attribution |
| [arXiv API](https://info.arxiv.org/help/api/) | The pace of AI research: papers whose abstract mentions AI or large language models, last 6 full months against the 6 before | API, fetched by "Update data" (3 s between calls) | arXiv API terms of use |
| [Saylor Academy](https://learn.saylor.org/) | Most free courses on a learning path, with the study hours each course page states | Course pages, each opened by `scripts/check_links.py` | Free courses with free certificates |
| [FAO elearning Academy](https://elearning.fao.org/), [OpenWHO](https://openwho.org/), [MIT OpenCourseWare](https://ocw.mit.edu/), [e-LATiH (HRD Corp)](https://elatih.hrdcorp.gov.my/) | Free courses on food and farming, health, engineering design, and short courses for Malaysians | Web pages, opened and checked | Free |
| [Department of Skills Development (JPK)](https://www.dsd.gov.my/), [CIDB Malaysia](https://www.cidb.gov.my/) | Hands-on training in Malaysia: SKM skills certificates, construction safety induction | Web pages, opened and checked | Public information |
| Laws of Malaysia (`data/my_restrictions.csv`): Common Gaming Houses Act 1953 (Act 289); Syariah Criminal Offences (Federal Territories) Act 1997 (Act 559), section 18, and the states' equivalents | The 7 gambling occupations, which are legal only in licensed premises and an offence for Muslims to take part in: marked, and left out of matches unless the person chooses to show them (the app does not ask anyone's religion) | Attorney General's Chambers, Laws of Malaysia portal | Public information |
| Malaysian professional bodies (`data/regulated.csv`): MMC, BEM, LAM, BQSM, MIA, Malaysian Bar, BOVAEP, Energy Commission, CAAM, JPJ, and the Dental Council, Pharmacy Board, Nursing Board, Allied Health Professions Council and Land Surveyors Board | Which occupations need registration to practise in Malaysia, and with whom | Web pages; the five whose sites could not be reached from our server are shown without a link | Public information |
| [UN Global indicator framework for the SDGs](https://unstats.un.org/sdgs/indicators/indicators-list/) | The SDG goals and targets in `data/sdg_map.csv` | Web page / PDF | UN terms of use |

## Licence notes

- **O*NET**: This product includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. Future Skills has modified all or some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.
- **Anthropic Economic Index**: data released by Anthropic under CC-BY; credited on every page that shows it.
- **Interest questionnaire** (`data/interest_items.json`): 36 statements written for Future Skills on Holland's six interest types, the model behind O*NET's interest profiles. It is not the O*NET Interest Profiler.
- **ESCO**: © European Union, ESCO classification, used under the European Commission's reuse policy.

## Raw files

The large downloads stay out of git; with them in one folder (`--raw`, or the `FS_RAW` variable) the tables can be rebuilt.

| File | Where it comes from | Read by |
|---|---|---|
| `onet_db_31_0_csv/*.csv` (occupation_data, essential_skills, transferable_skills, knowledge, software_skills, career_interest_types, job_zones, task_statements, task_ratings, tasks_to_dwas, gwas_to_iwas_to_dwas, emerging_tasks, essential/transferable skills to work activities, sample_of_reported_titles, related_occupations, level_scale_anchors, content_model_reference) | `https://www.onetcenter.org/dl_files/database/db_31_0_csv/<file>` | `build_onet.py` |
| `esco/esco_onet_crosswalk.csv` | `https://esco.ec.europa.eu/system/files/2023-08/ONET_%28Occupations%29_0_updated.csv` | `build_onet.py` |
| `esco/esco_occupation_isco.json` | ESCO API `resource/occupation` look-ups of every ESCO occupation in the crosswalk (its code and broader ISCO group) | `build_onet.py` |
| `aei/release_2026_06_26/data/aei_claude_ai_2026-06-26.csv`, `aei/labor_market_impacts/*.csv` | The Economic Index dataset at the pinned revision | `ai_exposure_extract.py` |
| `raw/dosm/jmi_data_2026q2.xlsx` (committed) | DOSM "Data JMI Q2 2026" | `demand.py` |
| `raw/mycol/mycol_2024_2025.csv` (committed) | Typed from the MyCOL 2024/2025 brochure | `data/mycol_map.csv` |

## Choices and limits

Every constant below is our choice, not data; the Sources page shows the values in use.

- **AI share of a task** = mean of two readings, Anthropic's task penetration and `automation × 1 + augmentation × 0.5` in the latest month for tasks with at least 0.01% of all use; the two readings are also its range. An occupation's share is the importance-weighted mean of its tasks.
- **Thin evidence.** Usage is counted in conversations, so an occupation few people bring to Claude shows little use whatever AI could do for it. Its share is trusted in proportion to its usage (full at 0.25% of all use) and otherwise leans on a prior: Anthropic's observed exposure for that occupation, or, when Anthropic observed none of its tasks (it reports 0), the usage-weighted mean of its field. A thin occupation keeps at least 15 points of range on each side.
- **Hands-off share** of a skill: the automation share of the work activities O*NET links it to, weighted by their usage; of a tool: the automation share of the request topic it belongs to (`data/skill_topic_map.csv`, our crosswalk, each link with a reason). Knowledge areas have no link in O*NET and count as neutral.
- **Linking to Malaysia.** An O*NET occupation gets the ISCO-08 unit group its closest ESCO matches share (exact matches outvote close ones, close outvote broad); a management occupation keeps to ISCO group 1. MASCO 2020 follows ISCO-08, so the unit group's first digit is the MASCO major group. MyCOL: "yes" when the list names the occupation or its unit group through an exact or close match; "near" through a broad match or when another unit group of the same ISCO minor group is listed. Five MASCO titles with no ISCO-08 group (data, cyber security, animation, games, quality) are linked to the O*NET occupations of that name; two are left unlinked rather than guessed.
- **Malaysian demand** = 50 + 50 × the confidence-weighted mean of: MyCOL (yes 1, near 0.5, no 0; high confidence, near medium) and the change in the major group's share of all online job ads, last two quarters against the two before, divided by 20% and capped at ±1 (medium confidence: a major group stands in for the occupation). DOSM's series breaks in 2025 Q3 (all ads +109% in one quarter), so windows never cross it.
- **Research tempo** = 1 + 0.5 × (momentum − 50) ÷ 50, where momentum = 50 + 50 × (growth of AI papers on arXiv ÷ 40%), capped. All papers grew too, so the AI share of papers can fall while AI papers grow; the Sources page shows both.
- **Outlook** = demand + min(1, adoption × tempo) × (60 × (builder share − average) − 100 × max(0, AI share − average)) ÷ 100. Rising or declining at ±2 points. Only a share above the average counts: the Economic Index measures chat-AI use, so a low share is no evidence that ATMs, robots or self-service machines leave the occupation alone. It says nothing about total hiring.
- **Skill weight** = 1 + adoption × (1 if it builds AI − 2 × (hands-off share − typical AI use) ÷ 100), kept within 0.4–1.6.
- **Match** = 20% field fit + 15% interest + 30% skills + 35% outlook (+ 10 or 6 points for an occupation serving a UN goal the person picked, capped at 100). Field fit = 50% the person's field choices + 25% interest + 25% CV and current job. Skills = 50% skills + 25% knowledge + 25% tools, each only when answered. Interest = the correlation of the person's six totals with the occupation's O*NET profile. An occupation above the person's education is listed after the others, unless it is within the further study the person said they would take on (none, one or two Job Zones): then it stays in the list, marked with the qualification it usually needs. One two or more Job Zones below their education is also listed after the others.
- **Learn next** (the tools a person is missing for an occupation): the tools not declining under the scenario first; within each group those O*NET marks In Demand for the occupation, then by skill weight; office tools nearly every job lists come last.
- **Simulated news** is not data. A headline sets a floor of 95% on the AI share of every task under the O*NET detailed work activities it names and raises the hands-off share of its AI-use topics, on a copy of the data for one request. The result is read first through the person's own job (or, without one, their first match): a task counts as moved when its AI share changes by 5 points or more.
- **Drawn futures**: 1,000 per ranking; each draws the adoption speed (beta 2,4 × 0.9), demand (±5 points), the AI share within its range and the two shift constants (±30%), and ranks the top 30 again.
- **CV reading** is word matching against O*NET's tool names and job titles, a list of Malaysian titles and qualification words; job titles count only under a work-experience heading. It can miss what a CV words differently and says so.
- **SDG links** (`data/sdg_map.csv`) are ours: a field's link holds for its occupations unless a more specific rule (a minor group, an occupation) replaces it; every link has a written reason.

### Evidence grade, routes and the team view

- **Evidence grade** (`scripts/evidence.py`): A from 5 of 6 points, B from 3, otherwise C. The points are our rule: 2 when the AI share is measured on the occupation's own tasks, 1 when it leans on Anthropic's observed exposure, 0 on the field average; 2, 1, 0 for an exact, close, or broad or missing MASCO mapping; 2 when the Economic Index release is at most 270 days old and demand was computed at most 60 days ago, less 1 for each that is older. It is not calibrated against outcomes and must not be read as a probability.
- **Routes kept open**: related occupations come from O*NET 31.0 (US). The 15-point reach is our choice. The count says how many next moves remain in the model, not how many jobs exist in Malaysia.
- **Team view** (`scripts/team.py`): each job is run as a person at the level O*NET gives the job, with no tools and no interests, so a real team member's match will differ. A move is searched only among related occupations and the job's own field. Hours are the course providers' stated lengths, not time to mastery; staff time and wages are not costed. The team in `data/sample_team.json` is fictional.
- **Scenario report** (`scripts/scenario_report.py`): describes what the scenarios change; it sets no quota of rankings that must change.

## The optional language model

Optional and only for wording: an OpenAI-compatible chat model writes the "Why this score?" text from one match's computed facts. A reply with a number not in the facts, its own prediction ("will grow", "akan meningkat", "将会增长"), the wrong language or too many words is thrown away and a template written from the same facts is shown. No personal data is sent.

## When something fails

- **A source is unreachable** during "Update data": the previous rows are kept and the log says which source failed.
- **A newer Economic Index release**: reported on the Sources page, never used until a person reviews and pins it.
- **A course page disappears or asks for a log-in**: `scripts/check_links.py` reports it as broken.
- **Usage data covers software only**: manual work shows little AI use; robots and machines are not measured.
