# data/

Every table the app reads. Generated tables are rebuilt by the scripts named below and checked by `python scripts/validate_data.py`; never edit them by hand. Hand-written tables keep a reason for every row.

| File | Rows | What it holds | Made by |
|---|---|---|---|
| `fields.csv` | 22 | The fields of work (SOC 2018 major groups), named and described in English, Bahasa Melayu and Chinese | by hand |
| `occupations.csv` | 910 | Every O*NET 31.0 occupation with skill data: title, description, field, Job Zone, RIASEC scores and code, ISCO-08 unit group and how it was found, MASCO major group, MyCOL status | `scripts/build_onet.py` |
| `elements.csv` | 68 | The 35 skills and 33 knowledge areas, with O*NET's examples of a low, middle and high level | `build_onet.py` |
| `occupation_elements.csv` | ~40,000 | Importance (1–5) and level (0–7) of each skill and knowledge area an occupation rates at least "somewhat important" | `build_onet.py` |
| `technologies.csv`, `occupation_technologies.csv` | 331 / ~11,700 | The Hot and In Demand technologies, and which occupations list them | `build_onet.py` |
| `occupation_titles.csv`, `related_occupations.csv` | | Job titles people in each occupation reported; O*NET's ten closest related occupations | `build_onet.py` |
| `onet/tasks.csv`, `onet/skill_work_activities.csv` | 18,592 / 232 | Every task statement with its importance and work activities; O*NET's links from skills to work activities | `build_onet.py` |
| `aei/` | | The Anthropic Economic Index rows our tasks, occupations and topics use, Anthropic's task penetration and observed exposure, and `source.json` (release, revision, sha256, dates) | `scripts/ai_exposure_extract.py` |
| `ai_occupations.csv`, `ai_tasks.csv`, `ai_skills.csv`, `ai_topics.csv` | | The AI layer written out for reading and checking (the app computes it from `aei/` and `onet/`) | `scripts/ai_exposure.py` |
| `skill_topic_map.csv` | 331 | Our crosswalk from each technology to an AI-use topic, with a reason | `scripts/build_topic_map.py` |
| `mycol_map.csv` | 66 | The MyCOL 2024/2025 occupations with their ISCO-08 unit group (or O*NET occupations) and how they were linked | by hand |
| `demand_inputs.csv` | | DOSM online job ads by MASCO major group, OpenDOSM median wages, arXiv paper counts | `scripts/demand.py` ("Update data") |
| `demand.csv` | 910 | Each occupation's Malaysian demand and its parts | `demand.py` |
| `sdg_map.csv` | ~200 | Our links from fields, occupation groups, occupations and skills to UN SDG targets, each with a reason | `scripts/build_sdg_map.py` |
| `learning_resources.csv` | 69 | Free courses and training programmes, what they teach (`element:`, `tech:`, `field:`, `all`), hours as the provider states them, the date each link was checked | by hand, checked by `scripts/check_links.py` |
| `regulated.csv` | 16 | Professions that need registration in Malaysia, the body, what it requires, and the O*NET codes it covers | by hand |
| `interest_items.json` | 36 | The interest statements, six for each RIASEC type | by hand |
| `sample_profiles.json` | 4 | Fictional people for the demo | by hand |
