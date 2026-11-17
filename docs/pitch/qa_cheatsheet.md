# Q&A 速查表

每题一句英文答案，加上在哪一页展示。三个人都要能答。数字出处：
- JC = `docs/judge_check.md`
- EV = `docs/eval_results.md`
- IV = `docs/impact_verification.md`
- CM = `docs/cost_model.md`

## 必答四题

| 问题 | 一句话答案 | 在哪展示 |
|---|---|---|
| **Why is this the score?** | "It is four parts you can see: for Aiman's own job, field 18.6 + interest 14.5 + skills 22.8 + outlook 29.6 = 85.6; the weights 20/15/30/35 are our assumptions and are listed on the Sources page, and the card says what would raise it." | Matches → "Why this score?"；Sources 页的常数表 |
| **Is the AI share the probability of losing the job?** | "No: it is the share of the job's tasks people already bring to AI (30.2% for Aiman, range 8.1–52.3), and many of those uses help the person rather than replace them, so it is never shown as a chance of being replaced."（JC 第 8 项） | 职业页的任务条（AI 做 / 与 AI 合作 / 仍是人做）；Lab 的 Stress Test |
| **Are the courses real?** | "Yes: every link was opened and dated by us, and our check reopens a random 10 (9 of 10 returned HTTP 200 on the last run; the miss was e-LATiH timing out), so please click any one now." | Pathway → 点任意一门课；Sources 页；`scripts/check_links.py` |
| **Why no test with real people?** | "The competition does not allow real personal data, so we built a reproducible evaluation instead: 40 synthetic people labelled by an independent annotator before the run, 62.5% with an accepted role in the top 5; career clarity with 20+ real testers (KPI 1) is not measured and is our first pilot step." | Impact slide；`docs/eval_results.md`；Workshop check 页（试点工具已做好） |

## 评委指南第 12 节列出的问题

| 问题 | 一句话答案 | 在哪展示 |
|---|---|---|
| Change the trend data now: what should change? | "Change any number on Futures or approve a checked real news item: the AI share, outlook, ranking and path recompute on the spot, and undo restores them (Aiman's AI share 30.2 → 36.8 → 30.2)." | Futures → "Change one number yourself" / 真实新闻 |
| Where does this recommendation come from? | "From our own code over sourced data (O*NET 31.0, Anthropic Economic Index 2026-06-26, MyCOL 2024/2025, DOSM job ads); no language model picks or scores anything." | Sources 页；每张卡上的来源和日期 |
| How do you keep the trend data current, and what does it cost? | "'Update data' refetches the public sources and the Economic Index is reviewed on each release; a 200-person pilot costs about RM 50 a month, RM 0.25 a person." | Sources 页的日期；`docs/cost_model.md` |
| What if AI moves faster or slower than you predict? | "That is the scenario switch: across our 40 test people the top-5 set changes for 62.5% between slow and fast, the first move for 27.5%, and each page names the choices that hold in all three."（EV） | Futures；Matches 上的稳健选择 |
| How do you stop it inventing a job or a course? | "Jobs and courses come only from our data files, each with a source; an LLM reply containing a number not in our facts is thrown away and a template is shown instead." | Sources 页；`scripts/explain.py`；README 的 AI Disclosure |

## 可能被追问的

| 问题 | 一句话答案 | 在哪展示 |
|---|---|---|
| 32.5% first-move agreement is low, isn't it? | "Yes, and we report it: we traced it to a coarse Malaysian demand signal, fixed only what the ISCO-08 crosswalk supports (the 5 most common first moves went from 20 to 15 of 40 people, 29 different first moves), and tuned no weight; the top 5 is the better unit (62.5%), and v1 got 12.5% / 15%." | `docs/eval_results.md` 的 "Every person" 表 |
| Who labelled the test people? | "An independent AI agent that saw only the stories and the occupation list, never our code or output; the labels were committed before the first run and their hash is in the results." | `eval/LABELING.md`；git 历史 `cd6d453` |
| Why doesn't the first place change when you switch scenarios? | "Because it is a robust choice: it ranks first under slow, moderate and fast adoption, and the page labels it so; what changes is the rest of the top 5, with a reason for each move. None of our 5 demo people's first move changes; across 40 test people the top-5 set changes for 62.5%."（JC 第 2 项、EV） | Futures 的三列并排；Matches 上的 robust / depends 标签 |
| Is the Malaysian demand data fine-grained? | "No: it is MyCOL status plus job ads for 9 major groups, 15 distinct values over 910 occupations; the occupation page says to read it as weak evidence, and we checked 36 questionable ISCO links (9 corrected, 27 unverified)." | 职业页 "The signals behind it"；`data/isco_review.csv` |
| Why does the first move change less than in v1? | "v1 re-ranked 25 IT roles by trend weights; we rank 910 occupations where a person's skills and fields usually dominate, so the top-5 set moves (62.5%) more often than the first place (27.5%)." | `docs/v1_vs_v2.md` |
| Phase 1 baseline and target? | "KPI 2 pathway coverage: baseline 14%, target 40%, now 94.8% for IT occupations and 90.8% over all 910; KPI 1 career clarity: target 70% of 20+ testers, not measured yet." | `docs/impact_verification.md` |
| Is it fair? | "The matcher has no input for name, age, gender, ethnicity or religion, and our fairness check shows the same CV gives the same results when they are added; bias in O*NET and usage data is not measured." | `scripts/fairness_check.py`；README 的 Responsible Use |
| PDPA? | "Nothing personal is stored on the server: answers stay in the browser, a CV is read for one request; a real deployment would add a privacy notice, access control for the Team view and log retention." | README 的 Responsible Use |
| Who pays? | "University and TVET career centres first, at about RM 0.25 a person in a pilot; enterprise HR after a pilot, using the Team view." | Team 页；`docs/cost_model.md` |
| Is it Malaysian? | "Demand uses MyCOL 2024/2025 and DOSM job ads, titles are shown in BM and Chinese, 14.4% of plan resources are not in English, and 540 of 910 occupations have an HRD Corp-claimable course."（EV、IV） | Pathway 的 HRD Corp 分支；切换语言 |
| Does AI make the decision? | "No: data sets the score, AI only words the explanation, the person decides, and no result is for hiring, firing or promotion." | 首页 "Data sets the score…" 那一段 |
