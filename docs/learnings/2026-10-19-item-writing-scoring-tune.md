# 出题、解题、打分与调参（20261019.s2）

适用范围：model-lens 活跃三栏（CP / E / NX），机械判分、不用 LLM-as-judge。跨项目「许愿式编程」通则仍以工程栏既有交接为准。

## 出题

- 题面写业务规则和 I/O 合同，不写评分点、分组名、满分。工程是许愿式：公开接口与默认值，隐藏关系留在 scorer。
- 要改难度就改**会动金标的约束**（截止时刻、禁止拆批、过期不能发货、进货间隔、清场时长），不要靠无关日志、反常规陷阱或猜评分器。
- 编码 `describe()` 是合同，业务 facts 是另一层。布局等价（字典 vs 列表、平行 `root`）应能比上；再加一条写进题面的约束去改唯一答案。
- 推理键集合不要为了压分而加键。先动实例，用 uniqueness / deletion / degree 门禁；金标必须跟着求解器重算并冻结 JSON。

## 解题（评分器）

- 不要把未见过的合法布局打成 0。先认合同内等价形状，再硬化业务。
- 不要为了贴某一张模型卷放宽金标。CP-10 上一轮 0 分是布局误杀，认字典后必须再用 `at` vs cutoff 改 g1。
- 参考实现必须仍满分。改 oracle / 夹具后先跑 `test_next_coding` / 推理 `--check`。

## 打分

- 三栏百分制，分母是该栏自己的满分。禁止跨栏合成。超时进分母记 0；请求失败（503）是 `request_error`，不是考砸。
- `--resume` 重跑 `request_error` / `worker_error` / `runner_error`，跳过已判的 `timeout`。stall 放弃的题若写成 `timeout`，续跑不会重打。
- 推理 `scorer_sha256` 必须钉**现行**冻结文件。曾误钉 `reasoning_20261020.json`，改金标时哈希不变，对比页会把不同冻结并排。
- 对比页闸门只看哈希和题集齐，不看已判。整渠道 503 会以 0 分进固定分母，看起来像 0 分卷。报告里要写「未判」。

## 调参（满分 / 零分）

- 目标按题：满分卷落到约 8–12/20，零分卷升到约 4–8/20。改实例后**新采样会重算**，旧卷的预期分只是下界。
- 只改时间/费用/反事实、计数键不动时，模型若按新金标做对，仍是 20。20261019 实测：deepseek 推理 172/200，多道 NX 仍满分。
- 合同过严造成的 0（布局）和真不会做的 0 要分开。认布局可能把 0 直接抬到 20（CP-12）。
- 原推理 sidecar 用 `NX08-*` 和独立 `bank_version=20261008`，不进 `ACTIVE_ITEMS`，不要在 import 时改全局 registry。

## 冻结身份

- 一个 `bank_version` 对应一份题面+金标。本次用户要求日历名 1019：现行集合是 `20261019` / 计分 `20261019.s2`，覆盖同名旧 s1 快照；旧金标只从 git 历史回放。
- `reasoning_20261023.json` 保持 20261023.s1（NX-16 profit 659）。调参后的推理金标只在 `reasoning_20261019.json`（NX-16 profit 603）。
- 工程本轮未调参，版本说明必须写明。

## 运行器

- woa 中转上同一时刻不要把多模型并发叠满。`--serial-channels` 按渠道串行，`--concurrency` 仍是每渠道请求数。
- 流式总超时不能只靠另一线程 `resp.close()`。看门狗要关底层 stream；渠道结束时 `client.close()`，`ThreadPoolExecutor.shutdown(wait=False, cancel_futures=True)`；放弃的 `run_one` 不得再写 `.txt`。
- 新网关型号先登 `catalog/output_limits.yaml` 再进 `channels()`。免费档 flash 与同网关 mimo/longcat 一样先登记 131072。

## 依据

- 编码合同与夹具：`eval_bank_20260925/coding_facts.py`、`next_coding.py`，`tests/test_next_coding.py`
- 推理冻结：`reasoning_20261019.json`，生成 `cursor_workspace/build_scripts/gen_reasoning_20261019.py --check`
- 实测：`out/eval-20261019-20261019T181715-hard`、`out/eval-20261019-20261019T204255-hard`；对比页 `docs/eval-matrix-20261019.html`
- mimo NX-18 流式挂死：请求无 TCP、无 NX-18.txt，进程 0% CPU，直到杀进程 `--resume`
- longcat：woa `HTTP 503 No available channel for model longcat-2.5-preview-free`
