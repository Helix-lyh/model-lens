# 评审交接 · 报告页与文案（2026-10-07）

给外部评审者。范围是三项：**单模型完整报告页**、**多模型横向对比页**、**本轮全部人读文案改动**（按闻风 skill 的判定规则）。

## 0. 请重点核什么

1. **事实有没有被表达改动带偏。** 本轮改了题面文字、文档参考答案、计分说明。要核的是「改完之后，文档描述的场景、数字、规则，与可执行代码是否一致」。
2. **两个页面是否真的同源同口径。** 它们共用同一份样式和同一套格式化函数，但渲染路径是两套。要核的是「同一个概念在两个页面上的口径有没有分叉」。
3. **未判（missing / error）的处理是否站得住。** 对比页里两个渠道各有一道题未判，处理方式见 §4。

## 1. 被评对象

| 文件 | git 状态 | 本轮做了什么 |
|---|---|---|
| `docs/eval-ledger-20261008.html` | 未跟踪（重新生成） | 单模型台账页，页面文案与计分展示已改 |
| `cursor_workspace/build_scripts/build_eval_ledger_20261006.py` | 未跟踪 | 台账页生成器；文案、布局、重构 |
| `cursor_workspace/build_scripts/build_eval_matrix.py` | **新增** | 横向对比页生成器 |
| `cursor_workspace/build_scripts/ledger_common.py` | **新增** | 两个页面共用的常量、取数、格式化 |
| `web/ledger.css` | **新增** | 抽出并追加的共享样式 |
| `docs/question-bank-next-reasoning-20261008.md` | 未跟踪 | 全文重写（事实同步 + 语域） |
| `docs/question-bank-next-engineering-20261008.md` | 未跟踪 | E-01..E-10 相关段落同步 |
| `eval_bank_20260925/next_reasoning.py` | 未跟踪 | 10 条题面文本与文档同步 |
| `eval_bank_20260925/report.py` | 未跟踪 | 报告文案 + 新增枚举对照 |
| `tests/test_next_reasoning.py` | 未跟踪 | 1 处断言随题面留白更新 |
| `AGENTS.md` / `CLAUDE.md` | 已跟踪（修改） | 语域 + 规则来源改为单一 |
| `src/cli.py` / `src/config.py` / `src/report.py` | 已跟踪（修改） | 各 1–3 处文案 |

仓库工作树在本轮之前就有大量未提交改动（旧题库下线、runner 改造等），**不属于本轮**。核对时请以本表为准，不要用 `git diff` 的全量。

## 2. 事实同步（以可执行代码为准）

用户裁决：「以代码为准，文档同步更新。」

### 2.1 推理档文档 6 题参考答案原来与代码不符

`docs/question-bank-next-reasoning-20261008.md` 与 `eval_bank_20260925/next_reasoning.py` 冲突，代码侧有测试兜底（`tests/test_next_reasoning.py` 明确断言文档那版是错的）。已按代码修正：

| 题 | 文档原答案（错） | 已改为（代码实际） |
|---|---|---|
| NX-09 | `["D","R2",12,20]`、`last_end 20` | `["D","R1",10,18]`、`last_end 18` |
| NX-10 | V1→P2，`total_cost 10` | V1→P1，`total_cost 6` |
| NX-14 | `peak_cost 8` | `peak_cost 10` |
| NX-15 | `["P1","B1",0,5]`、`["P2","B2",0,8]` | `["P2","B1",0,8]`、`["P1","B2",0,5]` |
| NX-17 | `alternatives [[["A","C","D"],15,6]]`、`reason "closed_edge_at_departure"` | `alternatives []`、`reason ""` |
| NX-18 | `route ["B","A","C"]`、`elevator_walk 12` | `route ["A","B","C"]`、`elevator_walk 0` |

### 2.2 推理档计分说明原来与评分器不符

文档原写「每题 20 分，四个输出字段各含 5 个机械观察点」。实际评分器是**按字段分组计权**，且**整组相等才得分**：

```
NX-09 served:10 waiting:2 last_end:4 infectious_rooms:4
NX-10 assign:12 rejected:3 total_cost:5
… （10 题各自权重不同，已逐题写入文档）
```

### 2.3 工程档 E-01..E-06 的题面原来描述的是另一套接口

文档写 `REGISTER/LOGIN/REQUEST/LOGOUT`、`CALLBACK/QUERY`、`RESERVE/CONFIRM/RELEASE`、`PUT/ERASE/GET/AUDIT`、`SUBMIT/POLL/REPORT/CANCEL`、`PROPOSE/APPROVE/PUBLISH/ROLLBACK/READ`；实际发出的题面是另一套（含 `now`/`generation`/`request_id`/`session_ref`、`CREATE/CALLBACK/GET`、`STOCK/RESERVE/GET`、`PUT/ERASE/READ`、`SUBMIT/UPDATE/GET`、`PROPOSE/PUBLISH/READ`）。已把 E-01..E-06 的**题面全文、20 点清单、参考行为**同步到实际实现。

### 2.4 三条不能碰的边界

- **E-07..E-10 的「题面全文」是代码解析的原文**（`engineering.py:_published_wish` 直接从文档抽这一节发给模型）。这四段**一个字没动**，只改了上面的「业务锚点」标签行。有测试可验（见 §3）。
- `coding` 档文档的「题面全文」同理，是 `next_coding.py:_wish` 的抓取源，本轮未动。
- 推理档文档的「题面全文」不被代码解析，但本轮把它与 `next_reasoning.py` 的题面**同步成了同一份文字**，改一处即两边都改。

## 3. 可复现证据

```bash
# 全量测试
.venv/bin/pytest -q
# 本轮最后一次结果：399 passed in 35.43s

# 两个页面构建幂等（连续构建两次，输出逐字节相同）
.venv/bin/python cursor_workspace/build_scripts/build_eval_ledger_20261006.py
.venv/bin/python cursor_workspace/build_scripts/build_eval_matrix.py \
  --run out/eval-20261008-20261007T151030-quick --out /tmp/m1.html

# 台账页不再输出内部记账字段
grep -c "主能力为" docs/eval-ledger-20261008.html   # 期望 0

# 仓库禁用词
grep -c "支持" docs/eval-ledger-20261008.html        # 期望 0

# E-07..E-10 题面与文档仍逐字一致
# （脚本见本轮会话；等价写法：抽出文档「题面全文。」段与 ITEMS.get(id).prompt() 比较）
```

已执行并确认：台账页构建幂等 ✅、对比页构建幂等 ✅、`主能力为` 命中 0 ✅、`支持` 命中 0 ✅、E-07..E-10 题面逐字一致 ✅。

**抽共享样式/公共模块时做过逐字节回归**：抽取 CSS 到 `web/ledger.css`、抽取 `ledger_common.py` 之后，两次重新生成的台账 HTML 与抽取前**逐字节相同**。该快照在 `/tmp`，后续 CSS 又追加了对比页规则，所以现在**无法原样重放**，只能核最终产物。

## 4. 多模型对比页的口径

### 4.1 可比性闸门（生成期硬校验，不通过拒绝生成）

`check_comparable()` 要求全部成立：

- 渠道数 ≥ 2
- `meta.models` 与 `results.jsonl` 里出现的渠道集合一致
- **每一道题**在各渠道上的 `scorer_sha256` 相同
- **每一道题**在各渠道上的 `bank_version` 相同
- 每个渠道的题集相同（不做缺题静默补位）
- `results` 的题集与 `meta.items` 一致

### 4.2 未判（missing / error）的处理

`status ∈ {missing, error, pending_review}` 或 `points is None` 一律视为**未判**：

- 逐题单元显示 `—` 加原因码，不显示 0 分
- 栏级合计只累计已判题目，分母同步缩小
- 单元与合计都写出「n / m 题已判」，分母不同时读者能直接看到

实测场次 `out/eval-20261008-20261007T151030-quick` 里：mimo 的 E-07 记 `missing_fence`（抽不出代码围栏）、longcat 的 CP-09 记 `execution_error`（执行报错）。这正是需要评审者判断的第 3 点。

## 5. 文案改动清单

判定规则来自闻风 skill：只在「读者需要猜主语/动作/对象/条件/结果」「名称与职责不符」「黑话遮住具体动作」「套话拖慢阅读」「有同样准确且明显更自然的说法」时立案；不按词长句长判错。

### 5.1 规则文件

| 位置 | 改前 | 改后 |
|---|---|---|
| `AGENTS.md:3` | `AGENTS.md 与 CLAUDE.md 内容相同，修改时必须同步。` | `本文件是仓库协作规则的唯一来源。CLAUDE.md 只保留一条指向本文件的说明…` |
| `AGENTS.md:15` | `跑验证和收口` / `别家模型的接口参数` | `跑验证和最终定稿` / `其他厂商模型的接口参数` |
| `AGENTS.md:19` | `动手前先回到根本：这个任务到底要解决什么问题？别照搬惯例…` | `动手前先明确任务要解决的核心问题，不照搬惯例…` |
| `AGENTS.md:25-27` | `事实对不对` / `最可能翻车` / `得拿出` | `事实准确性` / `最可能出错` / `必须拿出` |
| `AGENTS.md:66` | 约 250 字一整段（三方库题、标准库题、画像声明、依赖解析、答案约束、错误分类、判分口径混在一起） | 拆成 7 条；**事实一条未增删** |
| `CLAUDE.md` | 与 `AGENTS.md` 全文重复 | 4 行指向文件，要求开工前完整读取 `AGENTS.md` |

> **需要评审者特别注意**：`CLAUDE.md` 由「内容相同的副本」改成「指路」。如果宿主只自动加载 `CLAUDE.md` 而不读 `AGENTS.md`，规则会隔一跳。这是用户明确要求的形态，但请评估这个风险。

### 5.2 代码里的对外文案

| 位置 | 改前 | 改后 |
|---|---|---|
| `src/cli.py:390` | `…默认 180；家族栏同一客户端` | `…默认 180；audit 的家族栏复用同一客户端` |
| `src/config.py:33` | `base_url 可省略当 channel 带默认根路径` | `channel 自带默认根路径时，base_url 可省略` |
| `src/report.py:205` | `对照词表只当本地计数器。不能证明是同一条权重。` | `对照用词表仅作本地计数，不能证明两者是同一份权重。` |
| `src/report.py:316` | `主统计按 raw cluster 等权（一题一票，不因三语展开加权）；三语言 missing 不进分母、不记 0 分` | `主统计以原始题（raw cluster）为单位等权（一题一票，不因三语展开而加权）；记 missing 的语言不进分母，也不记 0 分` |
| `src/report.py:331` | `编码抽不出代码或本机缺工具链记 missing，不中断整场，不进 D 分母` | `编码题抽不出代码、或本机缺工具链时记 missing：不中断本场，也不进 D 分母` |
| `eval_bank_20260925/report.py` | `分数是该分母上的百分数。` | `各栏分数以本栏满分为分母。` |
| `eval_bank_20260925/report.py` | 逐题表「原因」列直接输出 `content_mismatch` 等机器枚举，无对照 | 新增两行枚举对照（状态列 + 原因列） |

### 5.3 报告页展示文案

| 位置 | 改前 | 改后 |
|---|---|---|
| hero 描述 | `这是私有题库…每栏十题，模型作答，由程序按结果打分。` + 一段口径说明 | 一行 `用私有题库测模型的编码、工程和推理。`；口径说明移到页脚 |
| 栏副标题 | `每题 20 分` / `每题 20 分` / `得分点 − 扣分点` | `10 题 · 每题 20 分 · 百分制` / 同左 / `10 题 · 每题 20 条关系 · 净分制` |
| 模型参数 | `思考强度 高` / `温度 0` / `整段返回` | `推理强度 high` / `采样温度 0` / `传输 非流式` |
| 计分数字（栏级 / 分区头 / 题级三层） | `50.0` + `100 / 200 分`；题级 `20` + `4 / 20 分` | 三层统一为 `50.0 / 100` + `原始分 100 / 200 分`；题级 `20 / 100` + `原始分 4 / 20 分` |
| 题目简介 | 取文档「业务锚点…主能力为推理」整行 | 去掉栏目名与「主能力」标签，只留业务描述 |

## 6. 未覆盖 / 已知限制

1. **T 组题面表述未做完。** `engineering.py` 里 E-01..E-06 的题面仍是原措辞（`现在只取事件里的 now`、`老用户/新用户`、句中断行的硬换行）。原因是这六题的历史实测数字（`T115945`、`T112527`）挂在原措辞上，改字会让那些引用失去对应物。**需要用户裁决后再动。**
2. **题面的中英状态词未消歧。** 推理栏 NX-15 同一段里 `clean`（患者属性）与「清洁」（房间动作）同词根，NX-09 是 `clean` 与「清场」。方案已提出，未执行。
3. **D 组剩余文档未改**：`README.md` 标题（`## 怎么跑` 与其余名词标题不一致）、`evaluation-contract-20261006.md`、`engineering-handoff-20261006.md`、`question-bank-evolution.md`、`question-bank-quality-gate-20261006.md`。
4. **对比页只在 quick 场次上验证过**（每栏 1 题）。hard 全量（3 渠道 × 30 题）正在后台跑，尚未出页面。
5. **移动端未实测。** 对比页在窄屏靠 `.mscroll` 横向滚动，sticky 表头在该断点被关闭，未做视觉确认。
6. **对比页未接入 CLI。** 目前是独立构建脚本，没有 `src/cli.py` 入口。
7. `--models` 渠道里 `deepseek-flash` 是 booster 上唯一可用的 DeepSeek Flash：`deepseek-v4-flash`、`deepseek-v4.1-flash` 等一律返回 503 `model_not_found`。如果评审者认为「DeepSeek V4.1 Flash」应指别的模型，这个前提需要重核。

## 7. 题面改动的口径断代

本轮把推理栏 10 条题面的文字改成了与文档同一份（留白、句式、补主语；未改数值、规则、字段名、排序）。因此：

- **同一场 run 内三渠道可比**（同一份题面）。
- **新一批的 deepseek-flash 分数不等于** `eval-ledger-20261008.html` 里那份（那份用的是修订前文字）。页脚已加口径说明：`题库 20261008 · 2026-10-07 作答，分数对应当时的题面`。
- 待评审者判断：这个处理方式（页脚标注 + 不重跑旧批次）是否足够，还是应当升 `bank_version`。

## 8. 建议的评审动作

1. 打开 `docs/eval-ledger-20261008.html` 与 `/tmp/matrix-quick.html`，核三层计分数字是否自洽（大数字 × 分母 = 原始分）。
2. 跑 `§3` 的四条命令，核幂等、禁用词、E-07..E-10 一致性。
3. 抽 2–3 道题，把「文档题面 / 代码题面 / 评分器分组 / 参考答案」四样并排对一遍。
4. 对 §6 的 7 条逐条判断：哪些是必须补的、哪些可以接受。
5. 对 §4.1 的闸门判据判断是否充分——尤其是「同题不同渠道必须同 `scorer_sha256`」是否会误伤合法场景。
