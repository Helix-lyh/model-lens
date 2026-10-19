# 题库 20261019

冻结集合：推理 10 + 工程 10 + 编程 10。计分 `20261019.s2`。默认评测只跑这一版。

本文件是 **20261019.s2** 现行冻结，取代 git 里旧的 20261019.s1 快照（NX-09 `last_end=41`、NX-16 `profit=204`、NX-12/18 无 `walk`）。旧金标只从历史提交回放，不要用本文件去重算 20261019.s1 跑次。`reasoning_20261023.json` 仍是 20261023.s1 快照，本轮调参后的推理金标只写在 `reasoning_20261019.json`。

工程栏沿用既有 v3.4 题面与关系，**本冻结未调工程题**。本轮只动推理实例/键（相对 20261023）和编程合同/夹具。

三栏独立，各栏百分制，不做跨栏合成分。编程每题一种语言。跑次：

```bash
.venv/bin/python cursor_workspace/build_scripts/run_eval.py --phase hard --models deepseek-flash --concurrency 8 --samples 1
```

身份：`eval_bank_20260925.bank_manifest`（`ACTIVE_VERSION=20261019`）。推理实例冻结在 `eval_bank_20260925/reasoning_20261019.json`，由 `cursor_workspace/build_scripts/gen_reasoning_20261019.py --check` 核对。

本冻结并入 20261020–23 推理迭代，以及 2026-10-19 对满分/零分题的合同与实例调参。worldkit 探针不在本集合。原 20261008 推理副本仍可由 `run_eval_selected_groups.py` 以 `NX08-*` 加跑，不进 `ACTIVE_ITEMS`；sidecar 的 `bank_version` 是 `20261008`。

## 编程 CP-09..CP-18

判分：`describe()` 合同 + 业务 facts，5 组 × 4 点，满分 20。题面：`docs/question-bank-next-coding-20261008.md`。

| 题 | 语言 | 标题 |
|---|---|---|
| CP-09 | Python | 配额预占与恢复回放 |
| CP-10 | Python | 运输批次与截止窗口 |
| CP-11 | Python | 双区域灰度与回滚 |
| CP-12 | Python | 多租户身份合并 |
| CP-13 | Go | 账务冻结与部分解冻 |
| CP-14 | Go | 批次库存与有效期 |
| CP-15 | Go | 审批链与代理窗口 |
| CP-16 | TypeScript | 分层令牌桶与补偿 |
| CP-17 | TypeScript | 缓存重建与失效代数 |
| CP-18 | TypeScript | 时间价与退款基线 |

本版编码合同：CP-10 认字典布局，ACCEPT 用事件时刻对截止；CP-12 认平行 `root`；CP-13 扣款/解冻必须带正整数金额；CP-14 一笔分配不得拆批，过期锁定不能发货；CP-17 SNAP 用整数 `snapshot`。

## 工程 E-01..E-10

许愿式工程行为。正分、负分、净分各自换算成百分数。实现版本 `v3.4`。题面：`docs/question-bank-next-engineering-20261008.md`。

| 题 | 标题 |
|---|---|
| E-01 | 注册与登录 |
| E-02 | 支付通知 |
| E-03 | 库存预占 |
| E-04 | 文档归档 |
| E-05 | 异步任务 |
| E-06 | 配置发布 |
| E-07 | 冷链出库和温度窗口 |
| E-08 | 退款争议和证据窗口 |
| E-09 | 设备租约与维护切换 |
| E-10 | 账单草稿和税率版本 |

## 推理 NX-09..NX-18

开放题面，最后一行 `ANSWER:` 按问题顺序给整数。实例与金标冻结如下。

| 题 | 标题 | 判分数值（分） | 答案 |
|---|---|---|---|
| NX-09 | 门诊多诊室与感染清场 | last_end(12)、waiting_n(8) | last_end=45, waiting_n=5 |
| NX-10 | 充电并列优先级与预约占用 | total_cost(8)、rejected_n(6)、cf_cost(6) | total_cost=61, rejected_n=1, cf_cost=65 |
| NX-11 | 冷链批次锁定与取消归还 | free_sum(8)、loaded_n(6)、cf_free_sum(6) | free_sum=13, loaded_n=3, cf_free_sum=11 |
| NX-12 | 电梯停运下的外卖路线 | total(6)、late_n(4)、walk(4)、cf_total(6) | total=73, late_n=1, walk=0, cf_total=61 |
| NX-13 | 航班延误与机组时限 | cancelled_n(8)、last_end(6)、cf_cancelled_n(6) | cancelled_n=4, last_end=1022, cf_cancelled_n=3 |
| NX-14 | 充电站老化优先级排队 | total_cost(12)、peak_cost(8) | total_cost=26, peak_cost=16 |
| NX-15 | 隔离病床与清洁 | emergency_wait(8)、waiting_n(6)、cf_emergency_wait(6) | emergency_wait=42, waiting_n=5, cf_emergency_wait=1 |
| NX-16 | 按箱采购与热天损耗 | profit(12)、waste_sum(8) | profit=603, waste_sum=1 |
| NX-17 | 换乘预算和分时封路 | arrive(8)、cost(6)、cf_arrive(6) | arrive=29, cost=4, cf_arrive=33 |
| NX-18 | 冷藏配送和电梯停运 | late_n(6)、total(4)、walk(4)、cf_total(6) | late_n=2, total=62, walk=14, cf_total=61 |

生成/校验：`.venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261019.py [--check]`。
