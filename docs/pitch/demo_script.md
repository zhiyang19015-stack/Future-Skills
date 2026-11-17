# Demo 剧本（按秒计时）

主办方还没确认 pitch 和 Q&A 的时长（决赛指南第 127 行）。下面按 **demo 5 分钟** 写：4 分钟是我们的旅程，最后 60 秒留给评委"改数据"。时间短的话，按文末的删减顺序砍。

- 演示人物：Aiman（虚构、在职、软件 QA 测试员）。
- 页面语言：先切到 English。
- 网址：**https://future-skills-sq6h.onrender.com**
- 数字出处：`docs/judge_check.md`（JC）、`docs/eval_results.md`（EV）。

## 开场前 10 分钟：唤醒服务（必须做）

Render 免费版闲置 15 分钟就会休眠，第一次请求要等 50 秒以上。

1. 上台前 10 分钟，用两台设备打开 `https://future-skills-sq6h.onrender.com/api/health`。要看到 `200`，或者 JSON 里有 `ok`。
2. 打开首页，点 English，点一次 Aiman 的 "See results"，确认排名出来了。
3. 上台前 2 分钟再刷新一次首页。15 分钟内没人访问，它会再睡着。
4. 同时打开本地备用（见下），停在首页。

## 离线备用（网络或 Render 出问题时）

- **本地服务：** 演示电脑上已经 clone 好仓库，运行：

  ```bash
  py -3 src/main.py
  ```

  然后打开 http://localhost:8080。数据都在仓库里，不需要上网。课程链接核对和 "Update data" 要上网，离线时就跳过。
- **截图：** `docs/ui-redesign/` 里的新 UI 截图，按 01 → 35 的顺序放进备用 slide。
- **录屏：** 还没录。建议冲刺前用 Render 按本剧本录一次，存在演示电脑上。
- **切换口令：** 主讲人说"we'll switch to the local copy"，操作员 5 秒内切到 localhost。不要在台上排查网络。

## 旅程（0:00–4:00）

| 时间 | 屏幕 / 操作 | 说什么（英文） |
|---|---|---|
| 0:00–0:15 | 首页 | "Aiman is a fictional software QA tester in Cyberjaya. His team now uses AI to write test scripts. He asks: what stays mine, and what do I learn first?" |
| 0:15–0:35 | 点 Aiman → **You** 页：职业、领域、工具、兴趣 | "His profile: the job he does now, his field, the six tools he uses, 36 interest answers. Every one of these feeds the ranking. A blank profile ranks nothing." |
| 0:35–1:05 | **Radar** → 打开他本职的职业页，看任务条 | "This is measured, not guessed: 30.2% of his job's tasks are already handed to AI, range 8.1 to 52.3, from the Anthropic Economic Index, release 26 June 2026. Source and date are on screen." |
| 1:05–1:40 | **Matches**：第一张卡 → "Why this score?" | "85.6 = field 18.6 + interest 14.5 + skills 22.8 + outlook 29.6. What would raise it is listed under it. His own job is marked declining under moderate adoption." |
| 1:40–2:10 | **Pathway**：学习线，然后 HRD Corp 分支 | "Free courses on his own gaps, biggest gap first, with hours and weeks at 6 hours a week. Every link was opened and dated. HRD Corp-claimable courses are listed apart: they are paid by the employer." |
| 2:10–2:30 | **SDG**：选一个目标，看哪些职业上升 | "Every occupation and skill is tied to an SDG target with a written reason. Choosing a goal moves occupations up. It is a real choice, not a badge." |
| 2:30–3:10 | **Futures**：慢 / 中 / 快并排；稳健选择和依赖情景的选择 | "Slow, moderate, fast. These are estimates, labelled as such. Digital Forensics Analysts stays in his top 3 in all three. The choices that depend on the scenario each say why." |
| 3:10–3:40 | **Futures**：发布模拟新闻 "AI coding agents now ship whole features" | "Simulated news, clearly marked. His own job's outlook goes 84.7 to 81.1, and his learning path changes. Nothing is saved." |
| 3:40–4:00 | Impact slide（或 EV 表） | "We tested on 40 synthetic people. Their labels were written by an independent annotator before we ran them. 62.5% got a counsellor-accepted role in their top 5; the competition version got 15%. Synthetic, not real people, and we say so." |

## 留给评委的"改数据"检查（4:00–5:00）

主讲人说："Please change the data yourselves." 然后把鼠标交给评委，或者按评委说的操作。备好三种做法，按评委的要求选：

1. **改一个数字（最直接）：** Futures → "Change one number yourself"，把一个 MASCO 组的招聘广告数，或者一个工作活动的 AI 份额改掉。
   - 预期：排名和本职前景重新计算，前后对比显示在最上面。
2. **真新闻，需要人批准：** Futures → 真实新闻 → `copilot_testing_dotnet`。
   - 先点批准，不先核对：会被拒绝（JC 第 8 项：2/2 被拒）。
   - 点核对，页面显示 2/2 句引语都找到了，日期是 2026-02-11。
   - 输入审核码再批准：Aiman 本职的 AI 份额 30.2% → 36.8%。
   - 点撤销：回到 30.2%，数据版本也恢复。
   - 审核码 `NEWS_REVIEW_CODE` 只在 Render 的环境变量里，不在仓库里。由队员输入，不在屏幕上念出来。
3. **查课程是不是真的：** 评委在 Pathway 随便点一门课，在新标签页打开。
   - 说明：抽查 10 个链接，9 个返回 200。e-LATiH 有时连不上，照实说（JC 第 6 项）。

如果评委问"为什么第一推荐没变"：

> "Often it holds: on our 40 test people the first move changes for 20% between slow and fast, while the top-5 set changes for 70%. A list that holds is an answer too, and the page says why."

## 时间不够时的删减顺序

1. 先删 SDG（2:10–2:30），在 Q&A 里用 SDG 页回答。
2. 再删 Radar 职业页（0:35–1:05），改在 Matches 卡片上指出 AI 份额。
3. 不能删：Matches 的 "Why this score?"、Futures 的情景对比、评委改数据。
