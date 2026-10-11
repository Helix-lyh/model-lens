# 推理题 20261013：分档、门禁记录与删除测试（维护者用，不进入题面）

生成器 `eval_bank_20260925/reasoning_gen.py`，冻结 `reasoning_20261013.json`，CI `tests/test_next_reasoning_20261013.py`（独立模拟器复查答案与删除测试）。计分分组与满分未改。

| 题 | 档 | 规则条数 20261012→20261013 | 关键条件数 | 题面字数 旧→新 | 删除测试 |
|---|---|---|---|---|---|
| NX-09 门诊多诊室与感染清场 | A | 4→5 | 4 | 991→1270 | 全部通过 |
| NX-10 充电峰谷和预约占用 | A | 4→5 | 4 | 869→1209 | 全部通过 |
| NX-11 冷链批次锁定与取消归还 | B | 3→3 | 5 | 1200→1482 | 全部通过 |
| NX-12 电梯停运下的外卖路线 | C | 4→4 | 3 | 826→1238 | 全部通过 |
| NX-13 航班延误与机组时限 | C | 3→3 | 6 | 1424→1714 | 全部通过 |
| NX-14 充电站老化优先级排队 | B | 4→5 | 4 | 787→1206 | 全部通过 |
| NX-15 隔离病床与清洁 | B | 4→5 | 5 | 978→1307 | 全部通过 |
| NX-16 按箱采购与热天损耗 | D | 4→5 | 4 | 615→945 | 全部通过 |
| NX-17 换乘预算和分时封路 | D | 4→5 | 3 | 906→1436 | 全部通过 |
| NX-18 冷藏配送和电梯停运 | C | 4→4 | 4 | 816→1317 | 全部通过 |

## NX-09 门诊多诊室与感染清场（A 档，seed 21161018）

- 业务锚点：门诊分诊台按到达与急诊级别把患者派到诊室，感染患者后诊室需清场，门诊有关门时刻。
- 失败代价：错误排程：急诊被普通患者挡住、关门前应接诊者被漏掉。
- 主能力：推理
- 迁移任务：换成客服坐席/维修工位派单，规则不变时同一推导成立。
- 删除测试（删除该条件后变化的字段）：
  - 诊室感染限制：infectious_rooms, last_end, served, waiting
  - 清场：last_end, served, waiting
  - 关门时刻：last_end, served, waiting
  - 急诊优先：last_end, served, waiting

## NX-10 充电峰谷和预约占用（A 档，seed 21261013）

- 业务锚点：充电运营按到达顺序为预约车辆确定桩位和时段，电价分时、桩有维护预约。
- 失败代价：错误付款与错误拒单：车主多付电费或被错误拒绝。
- 主能力：推理
- 迁移任务：换成会议室/机位按顺序订最低价时段。
- 删除测试（删除该条件后变化的字段）：
  - 桩最低电量：assign, total_cost
  - 预约占用：assign, total_cost
  - 分时电价：assign, total_cost
  - deadline：assign, rejected, total_cost

## NX-11 冷链批次锁定与取消归还（B 档，seed 21361087）

- 业务锚点：冷链仓按订单锁定批次、按窗口装车，订单可取消、批次会过期。
- 失败代价：错误库存：锁错批次导致过期发货或可售量错误。
- 主能力：推理
- 迁移任务：换成医院血袋/疫苗批次的锁定与出库。
- 删除测试（删除该条件后变化的字段）：
  - 取消归还：free, loaded, locks, rejected（必须含 locks）
  - 批次过期：free, locks, rejected
  - 装车窗口：loaded
  - 装车容量：loaded, locks, rejected
  - 批次在锁上限：free, locks, rejected

## NX-12 电梯停运下的外卖路线（C 档，seed 21461445）

- 业务锚点：外卖骑手在多栋楼宇间安排配送顺序，电梯按时段停运。
- 失败代价：错误排程：骑手按错顺序导致整体送达更晚、迟到判定错误。
- 主能力：推理
- 迁移任务：换成快递员多楼宇派件或巡检员巡楼顺序。
- 删除测试（删除该条件后变化的字段）：
  - 电梯停运：arrivals, route, total（必须含 route）
  - 下楼耗时：arrivals, late, route, total
  - 首次登记：arrivals, late, route, total

## NX-13 航班延误与机组时限（C 档，seed 21562255）

- 业务锚点：航司运控在延误、关闭事件后为航段重新确定执行机组。
- 失败代价：错误排程与合规：机组位置不符、转场不足或超执勤上限仍被派飞。
- 主能力：推理
- 迁移任务：换成长途司机/列车乘务按班次和工时上限换班。
- 删除测试（删除该条件后变化的字段）：
  - 落地延误：cancelled, duty, flights, last_end
  - 起飞延误：cancelled, duty, flights
  - 航段关闭：cancelled, duty, flights, last_end
  - 转场时间：cancelled, duty, flights, last_end
  - 执勤上限：cancelled, duty, flights, last_end
  - 航段数上限：cancelled, duty, flights, last_end

## NX-14 充电站老化优先级排队（B 档，seed 21661019）

- 业务锚点：充电站按优先级排队，等待过久的车辆逐步提升优先级（防饥饿）。
- 失败代价：错误排程与付款：车辆开始/结束时刻错，费用与峰时费用统计错误。
- 主能力：推理
- 迁移任务：换成打印/算力队列的老化优先级调度。
- 删除测试（删除该条件后变化的字段）：
  - 等待老化：finish_order, schedule（必须含 schedule）
  - 初始priority：finish_order, peak_cost, schedule（必须含 schedule）
  - 桩功率差异：finish_order, peak_cost, schedule
  - 桩准入：finish_order, peak_cost, schedule

## NX-15 隔离病床与清洁（B 档，seed 21761014）

- 业务锚点：病房收治：感染患者只能入隔离床，离床后需清洁，到点停止收治。
- 失败代价：感染控制与排程：感染患者被安排到普通床或清洁未完成即入住。
- 主能力：推理
- 迁移任务：换成实验室洁净间与普通间的样本排程。
- 删除测试（删除该条件后变化的字段）：
  - 急诊专床：beds
  - 隔离床限制：beds, disinfect_until, emergency_wait, waiting
  - 感染清洁：beds, disinfect_until, waiting
  - 停止收治：beds, disinfect_until, waiting
  - 急诊优先：beds, disinfect_until, emergency_wait, waiting

## NX-16 按箱采购与热天损耗（D 档，seed 21861016）

- 业务锚点：水果店按箱进货，货物两天内售完，热天不能进货且当天清库。
- 失败代价：错误采购：利润下降、报废增加。
- 主能力：推理
- 迁移任务：换成面包房/鲜花店的整箱采购计划。
- 删除测试（删除该条件后变化的字段）：
  - 按箱进货：buy, profit, waste（必须含 buy）
  - 热天禁进：buy, profit, sold, waste（必须含 buy）
  - 两天保质：buy, profit, sold, waste（必须含 buy）
  - 运费：buy, profit（必须含 buy）

## NX-17 换乘预算和分时封路（D 档，seed 21961277）

- 业务锚点：通勤者在有向线路网中按预算换乘，部分线路分时封闭。
- 失败代价：错误路线：选到封闭线路或超预算路线。
- 主能力：推理
- 迁移任务：换成物流干线在限行时段与运费预算下的路由。
- 删除测试（删除该条件后变化的字段）：
  - 分时封闭：alternatives, arrive, cost, path（必须含 path）
  - 预算：alternatives, arrive, cost, path（必须含 path）
  - 换乘耗时：alternatives, arrive

## NX-18 冷藏配送和电梯停运（C 档，seed 22061182）

- 业务锚点：冷藏骑手配送：订单有出餐时刻和截止时刻，楼宇电梯分时停运。
- 失败代价：错误排程：迟到单数增加、冷藏品超时。
- 主能力：推理
- 迁移任务：换成药品配送按备药时刻与截止时刻排线。
- 删除测试（删除该条件后变化的字段）：
  - ready：arrivals, late, route（必须含 route）
  - 电梯停运：arrivals, elevator_walk, route（必须含 route）
  - 先少迟到：arrivals, elevator_walk, late, route（必须含 route）
  - 首次登记：arrivals, elevator_walk, late, route

