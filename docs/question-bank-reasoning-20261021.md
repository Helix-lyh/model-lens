# 推理题库 20261021：并列择支加难

计分版本：`20261021.s1`（`bank_manifest.SCORING_VERSION`）。

## 用户原则（必须执行）
- 增加条件之间的互相影响；每条硬约束/关键条件与 **≥3** 条其他条件互相作用，影响最终推理结果。
- 删掉任一条承重约束必须改变**主问题**最优方案（主判分数值），不只改反事实/单字段旁支。
- 题面开放、答案收束为单值 `ANSWER: a,b[,c]`；难度来自约束交互非歧义。

## 本轮机制
### NX-10（推广 NX-14）
事件驱动接车；有效 priority 并列时枚举所有并列分配（含多空闲桩），先最大化接受车辆数，再最小化费用总和。保留预约/间隔/同时上限/最低电量/准入/峰禁/互斥突发。搜索空间约 200+ 条完整调度（非纯模拟）。

### NX-16
12 天、shelf≥3、滚动批量窗口；名义搜索空间大幅上升；最优相对「次日需求进货」启发式利润差显著；报废量承重。

### NX-13 / NX-15
重冻实例，使 CONDITIONS 联合度数均 ≥3。

### NX-14 / NX-12 / NX-18
保留 20261020 网状设计（NX-14 并列择支已达目标带）。

## 度数摘要
| 题 | 度数 | 说明 |
|---|---|---|
| NX-09/10/11/12/13/14/15/16/18 | min≥3 | 通过 |
| NX-17 | 站点禁止窗=2、高峰减速=2 | 未达标（与 20261020 同类） |

## 生成
`.venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261021.py [--check]`

## 题目与答案键
| 题 | 判分数值 | 答案 |
|---|---|---|
| NX-09 | last_end、waiting_n | 41, 5 |
| NX-10 | total_cost、rejected_n、cf_cost | 61, 1, 65 |
| NX-11 | free_sum、loaded_n、cf_free_sum | 11, 2, 9 |
| NX-12 | late_n、total、cf_total | 1, 76, 66 |
| NX-13 | cancelled_n、last_end、cf_cancelled_n | 8, 695, 7 |
| NX-14 | total_cost、peak_cost | 26, 16 |
| NX-15 | emergency_wait、waiting_n、cf_emergency_wait | 55, 5, 8 |
| NX-16 | profit、waste_sum | 651, 4 |
| NX-17 | arrive、cost、cf_arrive | 20, 3, 11 |
| NX-18 | late_n、total、cf_total | 2, 66, 58 |
