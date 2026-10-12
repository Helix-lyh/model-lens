# 推理题库 20261017：开放题面与数值答案

计分版本：`20261017.s1`（`bank_manifest.SCORING_VERSION`，写入每行结果与 meta，参与 `--resume` 校验）。

## 改动
- 删除 `active_shock` 字段及其计分；题面不暴露、不要求复述内部突发 id。
- 互斥突发：开始时刻较早者生效；**同时刻按事件语义优先**（洪涝 > 楼宇封闭、病假 > 禁飞、停用 > 清洁升级、封闭 > 枢纽故障、RECALL > 容量减半、全站停电 > 单桩故障），不依赖 id 字典序。
- 反事实改为单一数值小问：“若改为另一条突发生效（本应生效的那条视为不存在，另一条照常发生），X 是多少？”
- 题面不规定字段/数据结构；每题只问 2 个主数值（含突发的题另问 1 个反事实数值）。主值合计 14、反事实 6；无突发题 12/8。各数值独立给分，没有上游字段连带扣分。
- 答案格式唯一约定：最后一个 `ANSWER:` 行按问题顺序写整数。解析宽容：任意代码块、Markdown 粗体/反引号、全角冒号、前后说明、`问1=` 标签、多次 ANSWER 取最后一次；数值个数不符或小数记 format_error。
- 参考求解器重新生成答案；删除测试作用在判分数值上（删任一关键条件，至少一个判分数值变化）；新增唯一性检查：最优类题主值与反事实值均由严格唯一最优确定（NX-10/12/16/17/18）。
- 只影响已删明细字段的 3 条条件降为背景：NX-13 起飞延误、NX-15 非感染轻清、NX-17 边数上限（仍在题面，不计关键条件）。

## 题目与答案键
| 题 | 标题 | 判分数值（分） | 答案 |
|---|---|---|---|
| NX-09 | 门诊多诊室与感染清场 | last_end(12)、waiting_n(8) | {'last_end': 41, 'waiting_n': 5} |
| NX-10 | 充电峰谷和预约占用 | total_cost(8)、rejected_n(6)、cf_cost(6) | {'total_cost': 36, 'rejected_n': 4, 'cf_cost': 34} |
| NX-11 | 冷链批次锁定与取消归还 | free_sum(8)、loaded_n(6)、cf_free_sum(6) | {'free_sum': 11, 'loaded_n': 2, 'cf_free_sum': 9} |
| NX-12 | 电梯停运下的外卖路线 | total(8)、late_n(6)、cf_total(6) | {'total': 72, 'late_n': 1, 'cf_total': 69} |
| NX-13 | 航班延误与机组时限 | cancelled_n(8)、last_end(6)、cf_cancelled_n(6) | {'cancelled_n': 7, 'last_end': 965, 'cf_cancelled_n': 6} |
| NX-14 | 充电站老化优先级排队 | total_cost(12)、peak_cost(8) | {'total_cost': 71, 'peak_cost': 30} |
| NX-15 | 隔离病床与清洁 | emergency_wait(8)、waiting_n(6)、cf_emergency_wait(6) | {'emergency_wait': 56, 'waiting_n': 4, 'cf_emergency_wait': 10} |
| NX-16 | 按箱采购与热天损耗 | profit(12)、waste_sum(8) | {'profit': 204, 'waste_sum': 2} |
| NX-17 | 换乘预算和分时封路 | arrive(8)、cost(6)、cf_arrive(6) | {'arrive': 16, 'cost': 4, 'cf_arrive': 8} |
| NX-18 | 冷藏配送和电梯停运 | late_n(8)、total(6)、cf_total(6) | {'late_n': 2, 'total': 60, 'cf_total': 69} |

生成/校验：`.venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261017.py [--check]`。
