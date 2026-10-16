# 题库 20261019：核实报告全修

计分版本：`20261019.s1`（`bank_manifest.SCORING_VERSION`，参与 `--resume` 校验）。依据：`/workspace/scratch/grok47-verify-20261017/report.md` 及第二轮复核。

## 推理
- NX-14：老化截止后加成不再增加、已得加成保留；公式写入题面；独立逐分钟模拟器校验，total_cost 71→74。
- NX-16：天数从第 1 天起编号，周末为第 6、7 天，供应商第 3、6 天停供；“当天购入次日上午起可售”改为无歧义表述；删去“唯一”与 `lead=` 参数名。
- NX-12/18：删“唯一”提示；唯一性检查改为在判分数值上进行（并列路线判分值相同即可，无需额外 tie-break）。
- NX-12 删除冗余的“不得提前回站”，求解器枚举提前回站：cf_total 69→67（主值不变）。保留 NX-18 所需的禁止项与承重互斥规则。
- NX-17 删除禁止停留（允许等待，暴力搜索校验，答案不变）。
- 删 3 条无作用干扰条件：NX-13 起飞延误 F02、NX-15 非感染轻清、NX-17 边数上限。

## 工程（v3.4）
- E-01 连续错误上限 10 次、锁定至多 60；E-02 signature=ok 视为已验签，附加费 = 金额 + floor(金额/10)；E-03 新批次永不过期、预留库存只给回头客；E-05 失败上限由作答者在 2..6 内选择，protocol 可选（缺省 2）；E-06 仅 JSON true 视为批准；E-07 `negative` 关系要求与 `short` 不同的代码，参考实现返回 invalid（修矛盾）。
- 题面不再含题号、“工程题”、solution.py；E-07..E-10 统一要求只输出一个 python 代码围栏。

## 编码
- describe() 无效改为回退恒等文档并扣 4 分，不再整题 0 分。
- 每个 CP 只列自己的输出字段；CP-17 REBUILD 事件带 generation；无状态时 states 写无键对象；Go 不再要求 package solution（判分时改写）。

## 题面措辞（泄露表）
- 盐前缀改为 `【请求编号 …；与题目无关】`；删推理前缀“只依据题面推理作答”；“不能改账”→“不能改变已有状态”；CP-11“同一层里后写入的覆盖先写入的”。

## Runner / 汇总
- pass@k 的 n 为全部样本（与固定分母一致）；有截断/未判时分组合计按同一分母计 0（工程记“没测到”）。
- 矩阵页支持多样本（均值、逐样本分、k/n 通过）。
- grok max_tokens 走 catalog：docs.x.ai 仅列 500k 上下文、“No text output limit”，无官方最大输出值，保留 65536 并在 UNLISTED_MAX_OUTPUT 显式登记。

## 题目与答案键
| 题 | 标题 | 判分数值（分） | 答案 |
|---|---|---|---|
| NX-09 | 门诊多诊室与感染清场 | last_end(12)、waiting_n(8) | {'last_end': 41, 'waiting_n': 5} |
| NX-10 | 充电峰谷和预约占用 | total_cost(8)、rejected_n(6)、cf_cost(6) | {'total_cost': 36, 'rejected_n': 4, 'cf_cost': 34} |
| NX-11 | 冷链批次锁定与取消归还 | free_sum(8)、loaded_n(6)、cf_free_sum(6) | {'free_sum': 11, 'loaded_n': 2, 'cf_free_sum': 9} |
| NX-12 | 电梯停运下的外卖路线 | total(8)、late_n(6)、cf_total(6) | {'total': 72, 'late_n': 1, 'cf_total': 67} |
| NX-13 | 航班延误与机组时限 | cancelled_n(8)、last_end(6)、cf_cancelled_n(6) | {'cancelled_n': 7, 'last_end': 965, 'cf_cancelled_n': 6} |
| NX-14 | 充电站老化优先级排队 | total_cost(12)、peak_cost(8) | {'total_cost': 74, 'peak_cost': 30} |
| NX-15 | 隔离病床与清洁 | emergency_wait(8)、waiting_n(6)、cf_emergency_wait(6) | {'emergency_wait': 56, 'waiting_n': 4, 'cf_emergency_wait': 10} |
| NX-16 | 按箱采购与热天损耗 | profit(12)、waste_sum(8) | {'profit': 204, 'waste_sum': 2} |
| NX-17 | 换乘预算和分时封路 | arrive(8)、cost(6)、cf_arrive(6) | {'arrive': 16, 'cost': 4, 'cf_arrive': 8} |
| NX-18 | 冷藏配送和电梯停运 | late_n(8)、total(6)、cf_total(6) | {'late_n': 1, 'total': 58, 'cf_total': 67} |

生成/校验：`.venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261019.py [--check]`。
