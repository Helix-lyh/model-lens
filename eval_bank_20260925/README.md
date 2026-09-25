# 候选题库 20260925

16 道候选核心题：8 道推理和 8 道历史编程基线；另有 `challenge-05` 的 CP-01..CP-08 复杂业务编程挑战。候选包本身仍支持 Python / Go / TypeScript 三语言旧题，CP 挑战按用户当前目标固定为 Python。完整历史题面见 `../docs/bank-review-20260925.md`，CP 设计见 `../docs/bank-design-20260925.md`。

这是可以在本地评分的候选题包。当前 `src.cli bank/audit` 仍使用原有 `bank/questions.yaml`；本目录没有替换活动题库，也没有改变 F/I/D 三栏或降智阈值。全部难度为设计档位，尚无模型实测校准。

加强版 `20260925-challenge-09` 的单题时间预算按难度固定为：简单 4 分钟、普通 8 分钟、困难 12 分钟、超难 16 分钟。CP 编程题本轮不再把经典算法的输入量放大作为主要难点，而改为小规模的复杂业务契约：幂等键、原子回滚、租约与迟到回执、角色继承、发布依赖、账务冲正、迟到事件、资源容量和规则写冲突。v08 组合快照恢复、过期回执、动态角色、环境过滤、黑窗竞争和跨阶段实际状态变化。v09 在每题题面里增加一条反常规规则：退货不改状态、依赖只认 DONE、通配不跨冒号、具体环境压过星号、冲正成功才释放交易号、封窗不追溯、预算不归还、changed 只看本阶段。每题 5 个得分组各使用 4 个不同输入，避免靠重复样例制造满分。CP-01/02 为困难，CP-03/04/05/06/07/08 为超难；30%–50% 的 pass@1 是待真实模型校准目标，不是本地验证结论。`challenge_live` 默认按题目档位选择预算，并把实际预算写入每题结果；只有显式传入 `--timeout` 时才覆盖该映射。有效答案的 `score10` 还乘以耗时系数：实际耗时不超过该档预算的一半时系数为 1；超过一半后线性下降，达到预算时为 0.5，低于 0.5 不再下降。原始内容分保存在 `score10_content`。每个请求在题面前缀加入独立的随机盐，并记录盐和加盐题面哈希，以避免网关缓存复用。超时、网关错误和缺少结果属于交付稳定性，不计入能力分母。`challenge-01`、`challenge-02`、`challenge-03`、`challenge-05` 的结果保留用于难度校准对照。

## 文件

当前运行版本为 `20260925-challenge-09`；challenge-05 是历史校准基线。v08 官方 `deepseek-flash` 的 CP pass@1 为 0.625，高于 30%–50%。v09 用写进题面的反常规规则加难，本地参考回放不能代替真实端点校准。

| 文件 | 内容 |
|---|---|
| `catalog.py` | 题面、难度、得分组、三语言接口 |
| `questions.json` | 完整机器索引，推理题含答案；不是可直接发模型的文件 |
| `oracles.py` | 推理参考答案复算和独立算法交叉检查 |
| `references.py` / `.go` / `.ts` | 三语言编程参考实现 |
| `cases.py` | 编程同源输入和期望，固定种子，含规模组 |
| `score.py` | 推理部分分、严格解析、有限轮次汇总 |
| `runner.py` | 生成三语言 fixtures，复用仓库语言执行器 |
| `cli.py` | 导出单题给模型，评分已保存的响应 |
| `export.py` | 机械导出评审文档、机器索引 |
| `../tests/test_eval_bank_20260925.py` | 满分、变异实现、三语言和评分边界回归 |

## 本地运行

均在仓库根目录执行。先检查工具链；若失败，按根目录 AGENTS.md 运行初始化，再检查。

```bash
.venv/bin/python cursor_workspace/build_scripts/init_env.py --check
.venv/bin/pytest -q tests/test_eval_bank_20260925.py

# 只打印给模型的题面，不包含答案或隐藏测试。
.venv/bin/python -m eval_bank_20260925.cli prompt R-X-01
.venv/bin/python -m eval_bank_20260925.cli prompt P-X-01 --lang python

# 评分已经保存的响应；路径由调用方提供。
.venv/bin/python -m eval_bank_20260925.cli score R-X-01 response.txt
.venv/bin/python -m eval_bank_20260925.cli score P-H-02 response.txt --lang typescript

# 有限轮次评分，按第一、二、三轮顺序传入；最多三轮，满分即停。
.venv/bin/python -m eval_bank_20260925.cli score P-H-02 r1.txt r2.txt --lang go

# 官方 DeepSeek 端点（与 Booster 结果分开保存）；可按账号配额提高并发
.venv/bin/python -m eval_bank_20260925.challenge_live --kind all \
  --base-url https://api.deepseek.com --api-key-env DEEPSEEK_API_KEY \
  --model deepseek-chat --concurrency 16
```

CLI 不调用模型，不读取 API key，不自动发修复请求；这里实现的是评分流程。用户此次提出的有限轮次扩展仅在此候选包中加入，不修改原有单轮 runner。

## 评分合同

单题 20 内容分点，`score10=points/2`，不产生全库 0–100 总分，不使用模型裁判。20 是权重单位；某些推理数组按元素比例给分，可以出现小数。未取整的点数用于判断和折扣，显示分保留四位小数。

- 推理：最终响应是一个 JSON 对象，也可完整包在一个 `json` 围栏中。键顺序无关；拒绝重复键、NaN、Infinity、非有限数字、额外说明和多个候选答案。整数严格区分布尔和小数。概率允许等价整数分数；反例用语义检查，接受所有合规构造。
- 格式不计内容分。顶层缺键/多键仍可保留已正确字段的分，但 `protocol_ok=false`，不得 pass。嵌套方案的关键字段联动，不能拿错误下标配正确价值冒充正确方案。
- 编程：只取一份指定语言代码；每题五组，每组四个检查，每检查一分。一个检查可以包含多例，全部正确才得该点。用例失败不会阻止其他检查运行；编译失败、禁用 import、运行超时、异常终止或无合法评分标记为 fail、0 分。候选代码不得读测试文件或伪造标记。
- 缺少对应语言围栏或本地工具链：遵守现行仓库合同，记 missing，`points/score10/passed=null`，不伪装成模型 0 分。必须单独报告 `missing_fence` 与 `missing_toolchain` 的数量和覆盖率；不能靠不输出代码提高表面通过率。
- 满内容分且协议合规才 pass。反馈只给 `status`、`reason_code`、失败得分组名，不给隐藏输入、期望输出、差值、测试源码。本地审核者可见完整 round 分数，发模型时只发送 `feedback` 对象。

### 推理题分点细则

通常一个得分组内的标量等额；数组按位置逐项比较。除题面明确允许的等价项外，类型和长度必须匹配。特别规则如下：

| 题 | 细则 |
|---|---|
| R-E-01 | `residue_min` 五个位置分摊 6 分；`impossible` 每个正确成员 1 分，每个错误成员扣抵 1 分，下限 0，上限 10；必须是升序无重复整数。`largest`、`count` 各 2 分，但必须同时给对完整集合，避免重复猜答案拿分。 |
| R-E-02 | 四个概率分别 4/4/6/6 分；等价分数可得分。 |
| R-N-01 | frontier 的 13 个数分摊 8 分；minimum 4 分；完整最优分配列表 4 分；合法反例 4 分，按题意验证。 |
| R-N-02 | count4、count5 各 3 分；parity7 两数各 5 分；count7 的 4 分依赖 parity7 全对。 |
| R-H-01 | lower_bounds 两数各 1.5 分；base 的 makespan 和完整 starts 各 4 分；optimal_count 4 分；changed 的两项各 2.5 分。 |
| R-H-02 | base、changed 各 7 分，其中有效最优方案（indices/value/weight 整体）5.25 分，value_ties 1.75 分；feasible_counts 两数各 2 分；delta 2 分依赖两个完整结果正确。 |
| R-X-01 | fixed 4 分；after_first_left 三数分摊 8 分；first_action_costs 两数各 2 分；adaptive 4 分依赖 first_action_costs 全对。 |
| R-X-02 | histogram 四行各 2 分，一行的 h 和数量整体比较；selected 3 分依赖 histogram 全对；rotation_fixed 5 分；orbits 4 分依赖 selected、rotation_fixed 正确。 |

这些分数衡量可验证的子任务完成度，不能证明模型内部采用了某种推理路径。不因文字解释长或声称“已证明最优”加分。

## 独立采样与有限轮次

批量跑测默认每题一个独立样本，即 `pass@1`。需要估计 `pass@k` 时，使用 `run_eval_20260925.py --samples n --pass-at k`；结果保留 `(channel,item,lang,sample)` 维度，并按同题的 `n` 个已判分样本使用无偏估计 `1 - C(n-c,k)/C(n,k)`，其中 `c` 是通过数。`n<k`、missing 或 error 造成有效样本不足时，该题的 pass@k 为 null，不把缺失当失败。基础设施重试不增加 sample；`solve_within_k` / `repair` 是带反馈修复轮，仍按下面的折扣规则统计，不能与独立采样 pass@k 混用。

第一轮仍为主指标。反馈修复另叫 `solve_within_k` / `repair`，不把它称为独立采样的 pass@k。

设第 r 轮内容得分为 `s_r`（0..10），折扣 `d=[1,0.7,0.45]`：

```text
discounted_score10 = max(d_r * s_r)，r=1..实际轮数
rounds_to_solve = 首次完整 pass 的轮次；未通过则 null
repair_credit10 = 10 * d[rounds_to_solve]；未通过则 null
```

折扣整轮，不跨轮拼接得分点。未全对时仍保留部分分。例如三轮分别 6、8、10，则折扣结果为 max(6,5.6,4.5)=6，首次全对在第 3 轮，`repair_credit10=4.5`。第 3 轮修复成功不会抹掉首轮已经完成的内容；若业务只看完整解决的轮次成本，使用 `repair_credit10`。

响应最多三个，必须同题、同语言、同版本；第一轮成功后不能继续选优。有 missing/error 时汇总为 incomplete，折扣分和完成指标为 null，保留各轮诊断。基础设施重试另记，不能假装一轮模型修复。

下一轮上下文应包含原题、之前所有模型回答和统一反馈；首次全过即停。模型没有执行工具权限；由评测端运行编程验证器并发送摘要，这是此受限修复实验的唯一新增信息通道。

## 验证范围与接入边界

本地验证覆盖 8 道推理参考答案、24 个编程语言实例、8 类错误实现、解析与计分边界。推理计数通过枚举/DP/状态搜索等独立路径交叉核对；解释器使用人工预期用例和三语言回放，尚非形式化验证。

执行器复用 `src.grade`，不是本次新建的操作系统级隔离环境。Python 的禁网/禁子进程通过现有运行期限制，Go/TS 使用现有 import 检查和环境清理。它们不能作为防恶意代码的安全边界，候选题包也没有解决伪造 stdout 或读取同进程 fixture 的攻击面。当前验证运行的是已检查的参考代码；实际批量模型代码执行应放入受控、无密钥、无网络且无宿主文件权限的独立环境，测试结果应由可信外部进程持有。这是进入真实评测前的工程缺口，不代表“输出格式检查即可禁工具”。

本次没有改 `src`、活动题库、AGENTS.md/CLAUDE.md，也没有使用实网模型或产生模型费用。现行 loader 对题号、总数和领域矩阵有硬约束，新 JSON 不能直接覆盖 `bank/questions.yaml`。正式接入需要显式版本选择、报告版本标记以及 D 指标重新校准。
