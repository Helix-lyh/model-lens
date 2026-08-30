# model-lens 现行方案

个人兴趣。三栏独立结论，综合可用大约 60%–80% 即可。  
本文吸收 [review-20260830](review-20260830.md)，**取代**原稿 `ModelLens.md` 作为实现合同。评审未改的产品共识仍有效。

**先做 Module F。** 只验证「匿名模型是不是某词表家族」时，只跑 `family`，不必先写满题库。

---

## 0. 产品共识（冻结）

1. 三个任务分开计分，禁止合成 0–100 总分。
2. 任务：家族归属、型号判真、降智/能力衰减。
3. 8-bit 量化允许检不出。同家族 Flash vs Pro 只许 `同族未分型`，禁止写「支持」。
4. 能力题库只覆盖系统架构、编码、世界知识。不做冷门 trivia、安全红队、文风、小众语言知识。
5. 词表/协议探针不是「题目」。
6. 默认用户只有 New API 的 `base_url` + `api_key` + `model`。此配置下**只保证家族栏**；判真/降智必须另给参考源，否则 `skipped`。

非目标：INT4 取证、checkpoint hash、多模态指纹、LLMmap 分类器、网关注入扫描、完整 MMD/RUT、Web UI。

---

## 1. 架构

```
targets.yaml
    → 多渠道 httpx client（默认非流式；题库可 --stream-metrics）+ jsonl recorder
         → Module F  词表差分（独立）
         → Module C  四域题库（独立）
              → Module I  判真（跨族靠 F；同族只标未分型）
              → Module D  降智粗筛（仅 I=同族未分型 且参考源不同网关）
    → report.md / report.json    三栏独立
```

数据流单向：请求写入 `out/<run>/requests.jsonl`，分析脚本只读记录。

独立仓库（`~/code/model-lens`）。自建 `httpx` 客户端，不引入 `openai` / `anthropic` SDK，不依赖 TideSight。渠道按 pi / DSH 的拆法：`channel` 选厂商预设，`api` 选线协议；新官方站通常只加预设，不改调用方。字段名用 `tokenizer_family` / `vocab_hits`。

线协议（可扩展）：`openai-completions`（New API / 绝大多数兼容口）、`openai-responses`、`anthropic-messages`、`google-generative-ai`、`google-vertex`、`azure-openai-completions`、`bedrock-converse`。各家 usage 字段归一成整数 `prompt_tokens`；缺整数则 Module F fail-closed。禁止本地估算。不引入 boto3 / 官方云 SDK。

---

## 2. Module F：家族归属

### 2.1 公式（必须按此实现）

对固定 `BASE`（建议 `The quick brown fox.\n`，不要空串）和探针 `x`：

```
delta_api(x) = prompt_tokens(user=BASE+x) - prompt_tokens(user=BASE)
n_hat_k(x)   = encode_k(BASE+x) - encode_k(BASE)    # 每个候选词表本地算
```

比较的是两条差分，不是 `encode_k(x)`。  
`temperature=0`，**非流式**。`max_tokens` 只填 `catalog/output_limits.yaml` 里的**官方 Maximum Output**（如 DeepSeek V4 = 384K）；没有登记则不传。禁止自订 1 / 512 这种小额配额；输出长短靠题面约束，不靠卡 `max_tokens`。Anthropic 口必须带该字段，未登记会直接报错。

禁止：用空 usage 时本地估算填 `prompt_tokens`；家族栏 streaming（中转常伪造 usage）。题库测 TTFT / decode TPS 用 `--stream-metrics`，默认关。

### 2.2 Fail-closed

任一条出现下列情况，整场 F 标 `token_untrusted`，**不输出家族**：

- HTTP 非 2xx 且无法形成成对 BASE / BASE+x
- 响应无整数 `usage.prompt_tokens`
- `delta_api < 1` 或大到不合理（例如 &gt; `|x| + 500`）
- BASE 与 BASE+x 的 `prompt_tokens` 无法配对

部分探针失败：丢掉该探针再算；有效探针 &lt; 8 则 `token_untrusted`。

### 2.3 计分

对每个候选 k：

- `exact_hits(k)` = `delta_api == n_hat_k` 的条数
- `l1(k)` = Σ |delta_api − n_hat_k|

主排序：`l1` 升序；并列再用 `exact_hits`。

- `ambiguous`：前两名 `l1` 差 &lt; 3，或最佳 `l1 ≥ 2 × 探针数`，或最佳 exact_hits &lt; 6
- 否则家族 = 最佳候选
- 分档（在非 ambiguous 时）：
  - 高：exact_hits ≥ 8 且比第二名至少多 3
  - 中：有领先但差距不够「高」
  - 低：其余仍选出了唯一第一名

输出示例：`family=glm5 hits=10/14 l1=2 runner_up=qwen2_5 hits=6/14 l1=11 confidence=high`  
并列或不可信时：`family=ambiguous` 或 `family=token_untrusted`，不要猜。

### 2.4 探针（12–14 条，不是能力题）

保留原稿的表面形式分叉，并补两条特殊 token（tokwhois 已证明比冷门字更分家）：

1. 64 位连续数字（同一数字重复，测分组）
2. π 小数前 80 位
3. 常用汉字短串
4. 日文假名短句
5. 韩文短句
6. 泰文短句
7. 阿拉伯文短句
8. emoji 串（含组合）
9. 超长英文黏词
10. 中英数字混排
11. 一小段 Python（符号密）
12. 特殊空白 / 零宽各一处
13. `[gMASK]`（GLM 向）
14. `<|im_start|>`（ChatML / Qwen 向）

不测小众语言知识。条文放 `probes/family_probes.yaml`，可微调，条数保持 12–14。

### 2.5 协议探测（可选，失败不阻断）

`temperature=1.01`、非法 role / 非法 max_tokens、`logprobs=true`。只写入 jsonl。报告附录可列原始状态码，**不进入家族结论**。

### 2.6 catalog

`catalog/manifest.json`：来源 URL、git commit 或 encoding 名、sha256。宁少勿错。

Phase 1 必收（互不塌缩、均已核实可公开获取）：

| id | 来源 | 备注 |
|---|---|---|
| `cl100k_base` | tiktoken（文件 SHA256 可钉） | |
| `o200k_base` | tiktoken | o 系列不要传 `max_tokens` |
| `glm4` | `zai-org/GLM-4.5` `tokenizer.json` | 与 GLM-4 文本词表同一，不要再拆 4 vs 4.5 |
| `glm5` | `zai-org/GLM-5` / `GLM-5.2` | 5.x 共用；泰文/emoji ZWJ 可分 4→5 |
| `qwen2_5` | `Qwen/Qwen2.5-72B-Instruct` | **代表 Qwen2.5 / Qwen3 / MiMo**，禁止再拆。MiMo-V2-Flash 官方 `tokenizer.json` 14 探针 L1=0 |
| `qwen3_8` | `Qwen/Qwen3.8-Flash-Next`（vocab 248320） | 与上一条必须分开 |
| `deepseek_v3` | `deepseek-ai/DeepSeek-V3` | V4-Pro 文件 SHA 不同，探针 L1=0，不单列 |
| `kimi` | `tiktoken.model` + 官方 pretok 正则 | 不能当普通 `tokenizer.json` 加载 |
| `hunyuan` | `tencent/Hunyuan-A13B-Pretrain` `hy.tiktoken` | 官方 PAT_STR，禁止套 Kimi pretok。7B-Pretrain 同 SHA |

可选：`minimax`（MiniMax-M1 `tokenizer.json`）；`grok2`（`xai-org/grok-2` `tokenizer.tok.json`，只映射 grok-2，**不要**套 grok-4.x）。缺本地文件则跳过。不收：Claude 社区近似、Grok-3/4 无公开词表、Llama-3/4 gated。加题 / 加词表步骤见 [extending](extending.md)。  
特殊 token 探针（`[gMASK]`、`<|im_start|>`）本地按 **escaped** 模式计，因部分端点会转义 user 字面量。

加载：`tiktoken` + `tokenizers`。**禁止** `transformers`。

`catalog/model_family.yaml`：声称型号 → catalog id。未知型号：F 仍可跑，I 走行为步并注明「未登记家族」。

---

## 3. Module C：能力题库（Phase 2）

### 3.1 规模

题库 **20–60** 条原始题（编码按 1 题计，不按语言展开后计数），四域都要有，且每域覆盖 easy / medium / hard。  
编号：`{architecture|coding|knowledge|reasoning}-{easy|medium|hard}-{两位序号}`，例如 `coding-medium-01`。  
编码题加载时按语言展开为 `coding-medium-01-python` / `-go` / `-typescript`。  
`--quick` 快速：只跑 easy/medium，每题 `temperature=0` 一次。  
默认全量：三档都跑，每题 `0` 一次再 `0.7` × 3。  
当前 48 条原始题（12 架构 + 12 知识 + 12 推理 + 12 编码），展开后 72 道；快速 48 道 × 1 次；全量 72 × 4 + F。

### 3.2 出题

每题：`id`、`domain`、`difficulty`、`prompt`、`grader`、`pass_criteria`。全部自写，不用 GSM8K/MMLU/HumanEval 原文。题干可用中文。`id` 必须与 `domain`、`difficulty` 两段一致。

题面盐：与标准答案无关的短前缀（例如 run id）。不声称能防语义缓存。

域方向：架构仍是工程判断；编码仍是可跑单测。知识易档短答 exact；中/难档含长流程指令遵循（非常规嵌套 / 故意「错键」 / 后条覆盖前条），用 `structure` 多条硬规则核对。禁止安全拒答类题干，禁止抄公开基准原文。

### 3.3 评分

不用 LLM-as-judge。编码同一题面分别用 Python / Go / TypeScript 抽代码、编译、跑测。不做 Java / C# / C++，不做 3 轮自动修。

每题若干得分点。沙箱 **stdout** 必须出现 `POINTS n/m`（只认 stdout 里最后一次匹配；stderr / 编译日志不算。keyword/alias 自己写入后传入）。没有 POINTS 记 fail，不得因 exit 0 记 pass。`score10 = 10 × n / m`。满点才算该题 `pass`；部分对仍记折合分。架构题可写 `must_exclude`：套话命中则不得 pass。easy/medium/hard 的 completion_tokens 超过 80K/100K/128K 时，该次折合分与 points 同步减半（pass 不因此翻盘）。分域、分难度各自展示通过率与折合 10。**禁止**再合成 0–100 总分。

| 域 | grader | 进 Module I 向量 | 进 Module D 决策 |
|---|---|---|---|
| 架构 | 关键词组各 1 分；命中 ≥ `min_hits` 且未触 `must_exclude` 才 pass | **否** | **否**（只进分域附录） |
| 编码 | 按语言抽第一个 fenced 块；Python 无网沙箱，Go `go test`（GOPROXY=off），TS `tsc` 后再 `node`；用例各 1 分；编译失败或超时记 0 | **是**（抽不出记 `missing`） | 是 |
| 知识 | 短答 exact 1 分；`structure` 每条硬规则 1 分 | **否**（过易，只当冒烟：全错才报警） | **否** |

编码抽不出代码、本机缺该语言工具链、或工具链低于门槛（Python 3.11 / go 1.20）：该题 `missing`，不中断整场，不进 D 分母。沙箱清空 `TARGET_KEY` / `REF_KEY` 及进程里其它 API 环境变量。编译失败、禁运 import、跑完没有 `POINTS`、或超时记 0 分。猜对不算：知识栏 `match: exact`，带解释的句子不得分。环境初始化见 `AGENTS.md` 与 `cursor_workspace/build_scripts/init_env.py`。

---

## 4. Module I：型号判真（Phase 3）

不新增题。无参考源只出家族：I = `skipped`。声称型号未登记：`skipped`。T/R 同一网关缓存域：`invalid`。`family` 无 reference 时不打印 I，仍可把 skipped 写入报告。

1. F 为 `token_untrusted`：I = `skipped`。无参考源：I = `skipped`（在 token_untrusted 之后立刻短路）。
2. F 家族与声称型号所属家族不一致，且 F 置信度 ≥ 中：`不支持`（跨族换货；必须有参考源）。F 为 `ambiguous`：不走本条。中转目标（规范 channel=`newapi`）默认置信封顶「中」，除非 usage 自洽通过。
3. F 显示同族：I = `同族未分型`（**禁止**写「支持」）。词表分不开 Flash/Pro。
4. 不再用全库对错 Hamming 声称「同一分布」。编码题一致率只进附录，不单独把 I 推成「支持」。

不要输出「92% 是真模型」。

---

## 5. Module D：降智粗筛（Phase 3）

仅当 I 为 `同族未分型`（或用户显式 `--force-degrade`）且有**不同网关**的参考源。换家族报换货，不报降智。`--quick`、F 不可信 / ambiguous、T/R 同网关：D = `skipped`。

指标：

- `pass0`：temperature=0 的**编码题**通过率（`missing` 不进分母；架构/知识不进决策）
- `stab`：有重复采样时，每题 4 次中多数通过的比例（2-2 平局不算通过）
- `score10`：编码题折合 10 的平均（部分对也进；缺测不进）
- 分域通过率三张表只进附录

规则（粗筛，宁可漏检）：

- `pass0(R) - pass0(T) ≥ 0.25` **且** `stab(R) - stab(T) ≥ 0.20`：`疑似衰减`
- 或 `score10(R) - score10(T) ≥ 2.5`：`疑似衰减`（通过率接近但折合分塌了；不要求 stab 同时破线）
- 否则：`未检出衰减` 或 `偏离不足以下结论`

I 与 D 互斥：D 为 `疑似衰减` 时，I 不准写「支持」（本方案 I 也已禁止「支持」）。  
报告固定一句：8-bit 与同家族弱档经常落在「未检出」。题库规模可变，二项做 15pp 等价检验功效不够；本工具不假装做成了分布检验。

---

## 6. 目录、配置、CLI

```
model-lens/
  README.md
  pyproject.toml
  catalog/
    manifest.json
    tokenizers/
    model_family.yaml
  bank/
    questions.yaml
    tests/
  probes/
    family_probes.yaml
  src/
    client.py
    channels/          # 协议适配 + 官方预设
    family.py
    grade.py
    compare.py
    report.py
    cli.py
  examples/
    targets.yaml
  docs/
  out/                 # gitignore
```

`targets.yaml`：

```yaml
claimed_model: glm-5.3-flash
target:
  # 中转：不写 channel，按 OpenAI 兼容编解码
  base_url: https://your-newapi/v1
  api_key_env: TARGET_KEY
  model: glm-5.3-flash
# reference 可省略；省略则 I/D = skipped
# 官方站可只写 channel，base_url 用预设
# reference:
#   channel: zhipu
#   api_key_env: ZHIPU_API_KEY
#   model: glm-4.5-flash
reference:
  base_url: https://official-or-trusted/v1
  api_key_env: REF_KEY
  model: glm-5.3-flash
```

`channel` 例：`zhipu` / `dashscope` / `anthropic` / `openai` / `google` / `azure` / `bedrock` / `vertex` / `newapi`。`api` 可覆盖线协议；`headers` / `compat` / `api_version` 可选。target 与 reference 可以是不同渠道。Bedrock 用 Bearer（`AWS_BEARER_TOKEN_BEDROCK`）+ `compat.region`；Vertex 用 access token + `compat.project` / `compat.location`。云渠道示例见 `examples/targets.cloud.yaml`。

CLI：

```
python -m src.cli family --target examples/targets.yaml
python -m src.cli bank   --target examples/targets.yaml --quick
python -m src.cli bank   --target examples/targets.yaml --quick --stream-metrics
python -m src.cli audit  --target examples/targets.yaml --quick
python -m src.cli audit  --target examples/targets.yaml --force-degrade
python -m src.cli report --run out/run-xxx
```

客户端：按渠道选线协议，默认非流式。记录请求体、归一后的 `usage`（含 cached / cache_write / reasoning）、输入输出字符长度、墙钟延迟、派生的缓存命中率与端到端 tok/s、`channel`/`api`。家族栏超时默认 60s；题库 / audit 默认 180s，可用 `--timeout` 改。最多 2 次；失败记缺测，不中断整场。密钥只走环境变量。家族栏仍只信整数 `prompt_tokens`，禁止本地估算，禁止 streaming。端到端速率含排队+预填。`max_tokens` 用官方上限，见 `catalog/output_limits.yaml`。题库可加 `--stream-metrics` 填 `ttft_ms` / `decode_tps`（SSE；Bedrock Event Stream 会回退到非流式）。中转 streaming 的 usage 常不可信。

---

## 7. 报告

Markdown + 同名 JSON。禁止单一概率。

```
# Audit run-...
- target / claimed / reference
- 家族：glm5 | 10/14 | l1=2 | 第二名 qwen2_5 | 高
  或 ambiguous / token_untrusted
- 判真：不支持（家族冲突）/ 同族未分型 / skipped / invalid
- 降智：未检出 / 疑似衰减 / 偏离不足 / skipped
- 分域通过率（target vs reference）
- 附录：每题对错与 missing、F 每条 delta vs n_hat
```

---

## 8. 实施顺序

### Phase 0

Python 3.11+。依赖：`httpx`、`pyyaml`、`tiktoken`、`tokenizers`。独立 venv。无 GPU。

### Phase 1（先验收再往后）

1. 差分计数（同一拼接的本地 n_hat）
2. ≥5 个互不塌缩的钉死词表（优先 §2.6 的 8 条）
3. 12–14 条探针
4. 用两个已知官方模型（例如 Qwen 与 GLM）自测，互判不错家族；usage 缺失时必须 `token_untrusted`

阶段验收：已知 GLM 与 Qwen 能分开；缺 usage 不猜。

### Phase 2

写满题库与 grader（20–60，三档编号）。编码：同一题面 Python / Go / TypeScript 抽代码 + 编译跑测。用任一能用的模型跑通，修评分误杀。

### Phase 3

I/D 按本文规则。同一模型打两次：I 应为 `同族未分型`（或 skip），D 应为未检出。输出 md/json。

### Phase 4

README 写清：准确率预期、8-bit 与同家族弱档、token 不可信、题库范围、如何加词表和加题、无参考源只出家族。

---

## 9. 验收（给 Agent）

分栏验收，禁止「综合 60–80%」一句话过关：

- F：≥4 个已知远家族，**官方非流式**，top-1 ≥ 70%（`ambiguous` 计未命中）。Qwen2.5/Qwen3 算同一标签。
- I 跨族：声称 GLM、实际 Qwen →「不支持」召回 ≥ 70%，且只认 F 冲突，不靠 Hamming。
- I 同模型：官方 vs 官方误报「不支持」≤ 30%；同族不同 SKU 标 `同族未分型`，不承诺。
- D：人为换明显更弱的同家族小模型可以标衰减，**允许不标**。`--quick` 不出 D。
- 单次完整审计 &lt; 数百次短请求

---

## 10. README 必须写的上限

| 现象 | 处理 |
|---|---|
| 中转改写 usage | F = `token_untrusted` |
| 模板随内容变 | hits 下降 → 低置信或 ambiguous |
| 官方自己量化 | I 仍可能是 `同族未分型` |
| 同家族 Flash vs Pro | 只许 `同族未分型`，禁止「支持」 |
| 8-bit / 同家族弱档 | D 允许未检出 |
| 语义缓存 | 盐只防字面缓存 |
| catalog 过时 | 新匿名模型可能落到旧代际 |

---

## 11. 硬约束

1. 先 F，再题库。  
2. 题库 20–60 条原始题（展开前计数），四域 × 三档英文编号；快速只跑 easy/medium。   
3. 三栏不准加权总分。  
4. 请求落 jsonl，分析可离线重放。  
5. 密钥只走环境变量。  
6. 开源项目协议或安装过重则抄方法，不抄重依赖。  
7. 实现语言：Python。  
8. 无参考源只出家族。  
9. 不引入 `transformers`，不引入 `openai` SDK。不并入 TideSight。  
10. 不把协议探测、本地估算 usage、MiMo 独立家族写进主路径。
