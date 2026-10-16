# 推理题库 20261020：网状交互加难

计分版本：`20261020.s1`（`bank_manifest.SCORING_VERSION`）。

## 用户原则（必须执行）
- 增加条件之间的互相影响；每条硬约束/关键条件与 **≥3** 条其他条件互相作用，影响最终推理结果。
- 删掉任一条承重约束必须改变**主问题**最优方案（主判分数值），不只改反事实/单字段旁支。
- 题面开放、答案收束为单值 `ANSWER: a,b[,c]`；难度来自约束与时序交互。

## 交互与度数定义
约束 A 与 B **联合交互**，当且仅当主值向量满足：
`key(del A)≠key(base)` ∧ `key(del B)≠key(base)` ∧ `key(del A∘B)≠key(del A)` ∧ `key(del A∘B)≠key(del B)`。
度数 = 交互邻居数。生成时写入每题 `degree` / `deletion` / `search_space`。

反事实分支与「只改 cf_*」的互斥条件降为背景，不列入 `CONDITIONS`。

## 审计五题重做要点

| 题 | 档 | 设计要点 | 主答案 | 度数摘要 | 搜索空间 |
|---|---|---|---|---|---|
| NX-12 | C | 洪涝后移；目标改为先少迟到再最早完成；登记/拥堵/回站/取消/互斥网状耦合 | late_n=1, total=76, cf=66 | 七条均 ≥5 | 候选/可行见 frozen |
| NX-14 | C | 有效优先级并列时分支择优（非纯模拟）；老化/峰禁/停用/超时/准入耦合 | total_cost=26, peak=16 | 八条均 ≥3 | tie-branching |
| NX-16 | D | shelf=3 + lead=1 + 滚动批量窗口，跨天库存 DP，不可逐日贪心 | profit=256, waste=1 | 九条均 ≥6 | 名义 (cap/box)^可进货天 |
| NX-17 | D | 扩网；换乘/禁留/减速/互斥承重；次优更近 | arrive=20, cost=3, cf=11 | 四条承重；联合度数 2–3（未满 3 的两条见下） | 可行路径数见 frozen |
| NX-18 | C | 洪涝后移；ready/冷链/迟到目标/拥堵/登记耦合 | late_n=2, total=66, cf=58 | 七条均 ≥4 | 4 活跃单枚举 |

### NX-17 未满度数说明
`站点禁止窗`、`高峰减速` 联合度数为 2（承重共现 4，联合邻居不足 3）。已在文档标注为未达标项；其余审计题均 ≥3。

## 其余题
NX-09/10/11/13/15：删除测试升格为主值；弱互斥/弱条件降背景。度数未全部 ≥3（见 frozen `degree.ok`）。

## 生成
`.venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261020.py [--check]`

## 题目与答案键
| 题 | 判分数值 | 答案 |
|---|---|---|
| NX-09 | last_end(12)、waiting_n(8) | last_end=41, waiting_n=5 |
| NX-10 | total_cost(8)、rejected_n(6)、cf_cost(6) | 36, 4, 34 |
| NX-11 | free_sum(8)、loaded_n(6)、cf_free_sum(6) | 11, 2, 9 |
| NX-12 | late_n(8)、total(6)、cf_total(6) | 1, 76, 66 |
| NX-13 | cancelled_n(8)、last_end(6)、cf_cancelled_n(6) | 7, 965, 6 |
| NX-14 | total_cost(12)、peak_cost(8) | 26, 16 |
| NX-15 | emergency_wait(8)、waiting_n(6)、cf_emergency_wait(6) | 56, 4, 10 |
| NX-16 | profit(12)、waste_sum(8) | 256, 1 |
| NX-17 | arrive(8)、cost(6)、cf_arrive(6) | 20, 3, 11 |
| NX-18 | late_n(8)、total(6)、cf_total(6) | 2, 66, 58 |
