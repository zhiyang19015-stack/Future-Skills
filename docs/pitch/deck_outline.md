# Deck 大纲（决赛）

成品 deck（11 页，Slides artifact，私有，需要从页面的 Share 菜单分享给队友）：https://claude.ai/artifact/2cDkghtzswsc7KJch1D8jL 。它按本大纲做，多了一页 "Live demo" 过渡页，Impact 拆成两页（基线和评测、成本和覆盖）。

规则：一个评分点一页，标题就是带数字的结论。每个数字都写出处文件，评委问"从哪来"时可以当场打开。评测数字一律写上"synthetic data, not validated with real people"。截图都在 `docs/ui-redesign/`，是新 UI。

数字出处缩写：
- **EV** = `docs/eval_results.md`（`scripts/eval.py`，40 个留出合成人物）
- **JC** = `docs/judge_check.md`（`scripts/judge_check.py`，在线跑的）
- **IV** = `docs/impact_verification.md`
- **CM** = `docs/cost_model.md`
- **VS** = `docs/v1_vs_v2.md`

页面上的英文就是要放进 slide 的原文。

---

## 0. 封面：Who I am now → where I could be

- **标题：** Aiman tests software. AI now writes his test scripts. Which of his tasks stay his, and what should he learn first?
- **副标题：** Future Skills: 910 occupations, ranked for you under three AI futures, with a free plan. Live at future-skills-sq6h.onrender.com
- **截图：** `30-home-1440.png`
- **讲法：** 用一个人开场，不用统计数字开场。Aiman 是虚构人物，要说出来。

## 1. Problem-Solution Fit（15%）

- **标题：** All 6 must-haves run live for any of 910 occupations, not 25 IT roles
- **内容：**

  | Must-have | 在哪一页 |
  |---|---|
  | 1. Profile | You |
  | 2. Trend signal with source and date | Radar / Sources |
  | 3. Ranked roles with reasons | Matches |
  | 4. Pathway | Pathway |
  | 5. SDG | SDG |
  | 6. Scenarios | Futures |

  - 覆盖面：v1 有 25 个职位、5 个 IT 方向，现在有 910 个职业、22 个领域（VS §1）。
  - 题目点名的四类人（学生、在职、转行、求职）在评测里各 10 人，全部跑通，0 次报错（EV）。
  - 拿掉测试：把 SDG 标签拿掉，用户会失去"选目标后哪些职业上升、要多花几小时"这一步，它会改排名（SDG 页）。
- **截图：** `03-quick-steps-desktop.jpg`

## 2. Innovation & Creativity（25%）

- **标题：** We measure how much of each job's tasks people already hand to AI: 18,592 O*NET tasks, Malaysia next to the world
- **内容：**
  - AI 份额是从 Anthropic Economic Index 量出来的，不是模型的意见。每个职业都有 A/B/C 证据等级；ILO 作为第二来源：789 个确认、91 个有分歧、30 个查不了（JC 第 4 项）。
  - 真新闻要人批准：2 条真新闻都核对过原文引语和日期；核对之前申请批准，2 次都被拒绝；批准后 Aiman 本职的 AI 份额 30.2% → 36.8%，撤销后回到 30.2%（JC 第 8 项）。
  - 和现有平台不同：MYFutureJobs、JobStreet、LinkedIn 只给职位；Coursera、e-LATiH 只给课程。我们给的是"你的任务里哪些已经交给 AI"，再接上路径。
- **截图：** `07-occupation-task-strip-desktop.jpg`、`10-news-approved-banner-desktop.jpg`

## 3. Technical Execution（25%）

- **标题：** Deployed, and the judges' checks run as code: blank profile ranks 0 (was 10), 9 of 10 sampled course links open, 0 of 1,196 UI strings missing
- **内容：**
  - 公开网址检查通过（JC 第 7 项，HTTP 200）。
  - 空白档案：以前会排 10 个职业、第一名 92 分；现在排 0 个，并告诉用户先填什么（JC 第 1 项）。
  - 抽查 10 个课程链接，9 个返回 200。打不开的是 e-LATiH，结果是 URLError；照实写（JC 第 6 项）。
  - 管线：只用 Python 标准库；"Update data" 会去抓 OpenDOSM、arXiv 等公开来源；每个数字都带来源和日期（Sources 页）。
- **截图：** `05-matches-rank-move-desktop.jpg`

## 4. Impact & Feasibility（20%）—— 用评测数字

- **标题：** Pathway coverage 14% → 94.8% (IT occupations; 90.8% over all 910) against a 40% Phase 1 target; on 40 held-out synthetic people, 62.5% get a counsellor-accepted role in their top 5 (v1: 15%)（出处：IV、EV）
- **内容：**

  | 指标 | Phase 1 基线 | 目标 | 现在 | 出处 |
  |---|---|---|---|---|
  | KPI 2：所需技能里有核查过的免费课的比例 | 14%（26/186） | 40% | IT 职业 94.8%，全部 910 个 90.8% | IV |
  | KPI 1：职业清晰度（20 人以上） | 课前测量 | 70% | **未测量**，试点计划见 README | IV |

  评测结果（40 个合成人物，标注是独立标注者事先写好的）：

  | 指标 | v1 | 现在 | 出处 |
  |---|---|---|---|
  | 第一推荐被标注接受 | 12.5%（5/40） | 35%（14/40，95% 区间 22–51） | EV |
  | 前 5 名里有被接受的职业 | 15% | 62.5%（25/40，47–76） | EV |
  | 学习计划里的免费资源 | — | 100%（688/688） | EV |
  | 学习计划里的非英文资源 | 0% | 14.2% | EV |
  | 给在职人员的求职课 | — | 0（5e2a48f 时是 20） | EV |

  - 成本：200 人的试点每月 RM 49.95，每人 RM 0.25；5 万人时每人 RM 0.0112（CM）。
  - HRD Corp：11 门可报销课程，910 个职业里有 540 个用得上（IV）。
  - PDPA：服务器上不存任何个人资料；公平性检查见 `scripts/fairness_check.py`。
- **页脚（必须有）：** Evaluation: synthetic data, not validated with real people. KPI 1 needs real testers and is not measured.
- **截图：** `09-pathway-metro-hrd-branch-desktop.jpg`

## 5. Design & UX（5%）

- **标题：** 2 clicks and 1 answer from the home page to a ranked list and a plan; 0 of 12 pages scroll sideways at 390px
- **内容：**
  - 首次使用路径（JC 第 10 项）：
    - 用自己的回答：2 次点击、1 个必答问题，就到排名和学习计划。
    - 用虚构示例人物：1 次点击到排名，2 次到 Pathway。
  - 三语，缺失字符串 0 个；颜色对比度低于 AA 标准的 0 对（JC 第 9 项）。
  - 首次使用要几分钟：**未测量**，没有找真人计时。
- **截图：** `20-home-390.jpg`、`22-matches-rank-move-390.jpg`

## 6. Presentation：Honest limits（10%）

- **标题：** What we do not know: KPI 1 is not measured, 5 occupations take 20 of 40 first moves, the first move changes for only 20% between slow and fast
- **内容：**
  - 评测里，第一推荐只集中在少数几个职业上：
    - 40 人只出现 23 个不同的第一推荐。
    - CNC Tool Programmers 5 人，Tax Preparers 5 人，Talent Directors 4 人，Medical Equipment Repairers 3 人，Registered Nurses 3 人：前 5 个职业占了 20 人（EV）。
    - 原因已经查清：26 个没对上的人里，26 个是靠前景分赢的（平均多 6.8 分）；前景分大部分来自马来西亚需求分，而需求分在 910 个职业上只有 15 个不同的值，其中 111 个职业并列最高的 90.6（EV 的 "Why first moves concentrate"）。
    - 我们没有为了提高分数去调参数。要改，就用新的一批人物验证。
  - 情景：
    - 慢和快两种情景下，前 5 名组成变了的人有 70%（28/40，EV）。
    - 第一推荐变了的只有 20%（8/40，EV）。v1 是 45%，因为 v1 只在 25 个 IT 职位里重新排序。
  - 数据限制：
    - AI 使用数据只来自一家公司的产品，只有两个月。
    - 机器人和机器做的工作不在数据里。
  - 我们提供的是估计，不是预测。
- **讲法：** 主动讲弱点。评分表要求 "Honest that predictions are estimates and about data limits"。

## 7. 结尾：Next

- 真人试点：用 Workshop check 做 20 人以上的前后测，算 KPI 1。
- 第一推荐太集中：把需求分做细（MyCOL 只认确切职称，不再按 ISCO 组继承；重新核对 ESCO 对照），并且只用留出集之外的新人物来验证。
- 合作方：大学和 TVET 的就业中心先上，企业 HR 放在试点之后。
