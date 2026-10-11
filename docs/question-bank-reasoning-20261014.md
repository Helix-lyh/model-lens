# 推理题 20261014：相互约束与时序依赖（维护者用，不进入题面）

难度来自规则激活/失效、因果链与优先级冲突，而非堆实体或枚举空间。答案字段收敛且由模拟器唯一确定。防泄露靠约束写全，不用算法词表。

| 题 | 档 | 关键条件 20261013→20261014 | 收敛答案字段 | 删除测试 |
|---|---|---|---|---|
| NX-09 门诊多诊室与感染清场 | A | 4→6 | `served, waiting, last_end, infectious_rooms` | 全部通过 |
| NX-10 充电峰谷和预约占用 | A | 4→6 | `assign, rejected, total_cost` | 全部通过 |
| NX-11 冷链批次锁定与取消归还 | B | 5→7 | `locks, loaded, free, rejected` | 全部通过 |
| NX-12 电梯停运下的外卖路线 | C | 3→6 | `route, arrivals, late, total` | 全部通过 |
| NX-13 航班延误与机组时限 | C | 6→6 | `flights, cancelled, duty, last_end` | 全部通过 |
| NX-14 充电站老化优先级排队 | B | 4→7 | `schedule, peak_cost, finish_order` | 全部通过 |
| NX-15 隔离病床与清洁 | B | 5→7 | `beds, waiting, disinfect_until, emergency_wait` | 全部通过 |
| NX-16 按箱采购与热天损耗 | D | 4→7 | `buy, sold, waste, profit` | 全部通过 |
| NX-17 换乘预算和分时封路 | D | 3→6 | `path, arrive, cost, alternatives, reason` | 全部通过 |
| NX-18 冷藏配送和电梯停运 | C | 4→8 | `route, arrivals, late, elevator_walk` | 全部通过 |
