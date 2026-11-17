/* English, Bahasa Melayu and Chinese for the UI redesign (ui.js and the redrawn home, profile and
   quick-start headers): added to STRINGS from i18n.js. */
"use strict";

Object.assign(STRINGS, {
  /* evidence stamp */
  "stamp.title": ["Evidence grade, source and data date. Opens the Sources page.", "Gred bukti, sumber dan tarikh data. Membuka halaman Sumber.", "证据等级、来源和数据日期。点开到“数据来源”页。"],
  "stamp.grade": ["Evidence grade {0} (not an accuracy or a probability)", "Gred bukti {0} (bukan ketepatan atau kebarangkalian)", "证据等级 {0}（不是准确率，也不是概率）"],
  "stamp.ai": ["AI use", "Penggunaan AI", "AI 使用"],
  "stamp.demand": ["Job ads", "Iklan kerja", "招聘广告"],

  /* task breakdown strip */
  "strip.h": ["What AI does in this job's tasks today", "Apa yang AI lakukan dalam tugas kerja ini hari ini", "这份工作的任务里，AI 现在做了什么"],
  "strip.notloss": ["Task exposure is not job loss", "Pendedahan tugas bukan kehilangan kerja", "任务暴露 ≠ 失业"],
  "strip.p": ["The job's {0} O*NET tasks, each counted by how important it is, grouped by the AI use observed on it.", "{0} tugas O*NET kerja ini, setiap satu dikira mengikut kepentingannya, dikumpulkan mengikut penggunaan AI yang dicerap.", "这份工作的 {0} 项 O*NET 任务，按重要性加权，按观察到的 AI 使用归类。"],
  "strip.automation": ["AI can do", "AI boleh lakukan", "AI 可做"],
  "strip.augmentation": ["AI assists", "AI membantu", "AI 辅助"],
  "strip.human": ["People lead", "Manusia memimpin", "人主导"],
  "strip.automation.p": ["high AI use, and AI mostly does it alone", "penggunaan AI tinggi, dan AI kebanyakannya melakukannya sendiri", "AI 使用高，且多半由 AI 独立完成"],
  "strip.augmentation.p": ["AI is used, with a person doing the task", "AI digunakan, dengan orang melakukan tugas itu", "用到了 AI，但由人来完成任务"],
  "strip.human.p": ["little or no AI use observed", "sedikit atau tiada penggunaan AI dicerap", "几乎没有观察到 AI 使用"],
  "strip.tasks": ["{0} tasks", "{0} tugas", "{0} 项任务"],
  "strip.unclear": ["{0} tasks ({1}% of the work) have too little evidence to sort and are not drawn.", "{0} tugas ({1}% daripada kerja) tidak cukup bukti untuk diisih dan tidak dilukis.", "另有 {0} 项任务（占工作的 {1}%）证据太少，无法归类，没有画出。"],
  "strip.rule": ["Rule (the Lab's stress test, with today's data): AI share {0}% or more and automation share {1}% or more = AI can do; {2}% or more = AI assists; a range {3} points wide or more = not enough evidence. A share of tasks, not a chance of losing the job.", "Peraturan (ujian tekanan Makmal, dengan data hari ini): bahagian AI {0}% atau lebih dan bahagian automasi {1}% atau lebih = AI boleh lakukan; {2}% atau lebih = AI membantu; julat {3} mata atau lebih = bukti tidak mencukupi. Ini bahagian tugas, bukan peluang kehilangan kerja.", "规则（与“实验室”压力测试相同，用今天的数据）：AI 占比 ≥{0}% 且自动化占比 ≥{1}% = AI 可做；≥{2}% = AI 辅助；区间宽度 ≥{3} 个百分点 = 证据不足。这是任务占比，不是失业概率。"],

  /* roadmap */
  "road.h": ["From now to where you could be", "Dari sekarang ke tempat anda boleh pergi", "从现在到你可以去的地方"],
  "road.p": ["Skills you already have carry over; the gaps are the stepping stones. From your answers and the occupation's O*NET skills.", "Kemahiran yang anda ada dibawa bersama; jurang ialah batu loncatan. Daripada jawapan anda dan kemahiran O*NET pekerjaan itu.", "你已有的技能可以带过去，缺口就是踏脚石。依据你的回答和该职业的 O*NET 技能。"],
  "road.now": ["Now", "Sekarang", "现在"],
  "road.you": ["You today", "Anda hari ini", "今天的你"],
  "road.you.p": ["from your answers", "daripada jawapan anda", "来自你的回答"],
  "road.have": ["You already have", "Anda sudah ada", "你已经有的"],
  "road.have.p": ["carries over", "dibawa bersama", "可以带过去"],
  "road.have.none": ["Nothing rated yet: the skills check shows what carries over.", "Belum ada yang dinilai: semakan kemahiran menunjukkan apa yang dibawa bersama.", "还没有评分：做一下技能自测，就能看到哪些可以带过去。"],
  "road.gap": ["Stepping stones", "Batu loncatan", "踏脚石"],
  "road.gap.none": ["No gap found in the skills you rated.", "Tiada jurang ditemui dalam kemahiran yang anda nilai.", "你评分过的技能里没有发现缺口。"],
  "road.next": ["Where you could be", "Tempat anda boleh pergi", "你可以去的地方"],
  "road.level": ["level {0} → {1}", "tahap {0} → {1}", "水平 {0} → {1}"],
  "road.tool": ["tool to learn", "alat untuk dipelajari", "要学的工具"],
  "road.key.have": ["solid: you have it", "padu: anda sudah ada", "实线：你已经有"],
  "road.key.gap": ["dashed: to learn", "putus-putus: perlu dipelajari", "虚线：需要学"],

  /* metro map */
  "metro.h": ["Your learning line", "Laluan pembelajaran anda", "你的学习路线图"],
  "metro.p": ["Each stop is a skill, in the plan's own order (biggest gap first, as below). Tap a stop to go to its courses.", "Setiap hentian ialah kemahiran, mengikut susunan pelan (jurang terbesar dahulu, seperti di bawah). Ketik hentian untuk pergi ke kursusnya.", "每一站是一项技能，顺序与计划相同（缺口最大的在前，和下面一致）。点一站跳到它的课程。"],
  "metro.free": ["{0} free", "{0} percuma", "{0} 个免费"],
  "metro.paid": ["{0} paid", "{0} berbayar", "{0} 个付费"],
  "metro.done": ["done", "selesai", "已完成"],
  "metro.basics": ["Basics of the field", "Asas bidang", "领域基础"],
  "metro.hands": ["Hands-on training", "Latihan amali", "动手实践"],
  "metro.hands.p": ["{0} programmes in Malaysia", "{0} program di Malaysia", "马来西亚的 {0} 个培训项目"],
  "metro.hrd": ["Branch line: HRD Corp claimable", "Laluan cabang: boleh dituntut HRD Corp", "支线：HRD Corp 可报销课程"],
  "metro.hrd.p": ["{0} paid courses an employer can claim; the best one covers {1} of your gaps. Not in the free hours.", "{0} kursus berbayar yang boleh dituntut majikan; yang terbaik meliputi {1} jurang anda. Tidak termasuk dalam jam percuma.", "{0} 门雇主可报销的付费课程；最多的一门覆盖你 {1} 个缺口。不计入免费学时。"],
  "metro.key.free": ["solid line: free courses", "garisan padu: kursus percuma", "实线：免费课程"],
  "metro.more": ["… {0} more stops (show all)", "… {0} hentian lagi (tunjuk semua)", "… 还有 {0} 站（全部显示）"],
  "metro.key.hrd": ["dashed branch: paid, employer can claim", "cabang putus-putus: berbayar, majikan boleh tuntut", "虚线支线：付费，雇主可报销"],

  /* rank moves */
  "move.new": ["new in this list (not ranked under {0})", "baharu dalam senarai ini (tiada kedudukan di bawah {0})", "新进入（{0} 下没有名次）"],
  "move.same": ["same place as under {0}", "tempat sama seperti di bawah {0}", "与 {0} 下名次相同"],
  "move.up": ["↑ {0} (was #{1} under {2})", "↑ {0} (dahulu #{1} di bawah {2})", "↑ {0}（{2} 下是第 {1}）"],
  "move.down": ["↓ {0} (was #{1} under {2})", "↓ {0} (dahulu #{1} di bawah {2})", "↓ {0}（{2} 下是第 {1}）"],

  /* approved news, before and after */
  "nb.h": ["After the approved news “{0}”", "Selepas berita yang diluluskan “{0}”", "批准新闻“{0}”之后"],
  "nb.moved": ["{0} of your top 12 moved; those on this page are marked.", "{0} daripada 12 teratas anda bergerak; yang ada di halaman ini ditanda.", "你前 12 名中有 {0} 个名次变了，本页显示的已标出。"],
  "nb.same": ["Your top 12 kept its order.", "12 teratas anda kekal susunannya.", "你的前 12 名顺序没变。"],
  "nb.undo": ["A reviewer can undo it on the Futures page.", "Penyemak boleh membatalkannya di halaman Masa Depan.", "审核人可以在“未来情景”页撤销。"],
  "nb.go": ["Futures", "Masa Depan", "未来情景"],
  "nb.hide": ["Hide these marks", "Sembunyikan tanda ini", "隐藏这些标记"],
  "nb.row": ["news: #{0} → #{1}", "berita: #{0} → #{1}", "新闻：第 {0} → 第 {1}"],
  "nb.row.new": ["news: new in top 12", "berita: baharu dalam 12 teratas", "新闻：新进前 12"],
  "nb.path.moved": ["In this plan, {0} skills changed (marked below) and {1} left the plan.", "Dalam pelan ini, {0} kemahiran berubah (ditanda di bawah) dan {1} keluar daripada pelan.", "这份计划里有 {0} 项技能变了（下面已标出），{1} 项移出了计划。"],
  "nb.path.same": ["This plan's skills kept their order and AI marks.", "Kemahiran pelan ini kekal susunan dan tanda AI-nya.", "这份计划的技能顺序和 AI 标记都没变。"],
  "nb.path.hours": ["Total hours {0} → {1}.", "Jumlah jam {0} → {1}.", "总学时 {0} → {1}。"],
  "nb.path.unkept": ["This plan was not kept before the approval (only your chosen job and top 3 moves are), so its changes cannot be shown.", "Pelan ini tidak disimpan sebelum kelulusan (hanya pekerjaan pilihan anda dan 3 teratas), jadi perubahannya tidak dapat ditunjukkan.", "批准前没有保存这份计划（只保存了你选的职业和前 3 个），所以无法显示它的变化。"],
  "nb.path.new": ["new in plan", "baharu dalam pelan", "新进计划"],
  "nb.path.step": ["step {0} → {1}", "langkah {0} → {1}", "第 {0} 步 → 第 {1} 步"],
  "nb.path.ai": ["AI: {0} → {1}", "AI: {0} → {1}", "AI：{0} → {1}"],
  "nb.path.row": ["news: {0}", "berita: {0}", "新闻：{0}"],

  /* profile progress */
  "prog.h": ["Your answers so far", "Jawapan anda setakat ini", "你目前的回答"],
  "prog.n": ["{0} of {1} parts answered", "{0} daripada {1} bahagian dijawab", "已回答 {0} / {1} 部分"],
  "prog.one": ["All optional. Answer any one part to get a ranking.", "Semuanya pilihan. Jawab mana-mana satu bahagian untuk mendapat senarai.", "全部可选。回答任意一部分就能得到排名。"],
  "prog.ready": ["Enough for a ranking. Each extra part makes it closer to you.", "Cukup untuk senarai. Setiap bahagian tambahan menjadikannya lebih tepat.", "已经可以排名。多答一部分，结果就更贴近你。"],
  "prog.job": ["Your job", "Kerja anda", "你的工作"],
  "prog.fields": ["Fields", "Bidang", "领域"],
  "prog.cv": ["CV", "CV", "简历"],
  "prog.tools": ["Tools", "Alat", "工具"],
  "prog.interests": ["Interests", "Minat", "兴趣"],
  "prog.skills": ["Skills", "Kemahiran", "技能"],

  /* quick start progress */
  "qs.h": ["Quick start progress", "Kemajuan mula pantas", "快速开始进度"],
  "qs.1": ["Who you are", "Siapa anda", "你是谁"],
  "qs.2": ["One field you like, or your job", "Satu bidang yang anda suka, atau kerja anda", "选一个喜欢的领域，或你的工作"],
  "qs.3": ["Your ranking and plan", "Senarai dan pelan anda", "你的排名和计划"],
  "qs.now": ["now", "sekarang", "当前"],

  /* home */
  "home.cta.profile": ["Build my career profile", "Bina profil kerjaya saya", "建立我的职业档案"],
  "home.cta.radar": ["Explore the AI Radar", "Terokai Radar AI", "探索 AI 雷达"],
  "home.cta.full": ["or answer every question", "atau jawab semua soalan", "或回答全部问题"],
  "home.cta.note": ["Three quick answers, then your ranked occupations and a free plan on the same page.", "Tiga jawapan pantas, kemudian senarai pekerjaan anda dan pelan percuma di halaman yang sama.", "回答三个问题，同一页就会出现你的职业排名和免费学习计划。"],
  "home.flow.h": ["How it works", "Cara ia berfungsi", "怎么用"],
  "home.flow.1": ["Understand your exposure", "Fahami pendedahan anda", "了解你的 AI 暴露度"],
  "home.flow.1.p": ["Which tasks of a job AI already does or helps with, from observed use.", "Tugas kerja yang sudah dilakukan atau dibantu AI, daripada penggunaan yang dicerap.", "根据实际观察到的使用，看一份工作里哪些任务 AI 已经在做或在辅助。"],
  "home.flow.2": ["Compare future scenarios", "Bandingkan senario masa depan", "比较未来情景"],
  "home.flow.2.p": ["Slow, moderate or fast AI adoption: see which choices hold.", "Penggunaan AI perlahan, sederhana atau pantas: lihat pilihan yang kekal.", "AI 普及慢、中、快：看哪些选择站得住。"],
  "home.flow.3": ["Build your next-step pathway", "Bina laluan langkah seterusnya", "规划下一步学习路线"],
  "home.flow.3.p": ["Free courses for your gaps, biggest gap first, with HRD Corp options shown apart.", "Kursus percuma untuk jurang anda, jurang terbesar dahulu, dengan pilihan HRD Corp ditunjukkan berasingan.", "针对你的缺口推荐免费课程，缺口最大的在前；HRD Corp 课程单独列出。"],
  "home.fictional": ["Fictional demo profile", "Profil demo rekaan", "虚构演示人物"],
});
