# 加题 / 加词表

个人工具。改完跑 `pytest`。词表文件不进 git（见 `.gitignore` 的 `catalog/tokenizers/*`）。

## 加题（Module C）

题库 **20–60** 条原始题（编码按 1 题计，**不**按语言展开后计数）。编号 `{architecture|coding|knowledge|reasoning}-{easy|medium|hard}-{序号}`，例如 `coding-medium-01`。编码题加载后变成 `coding-medium-01-python` / `-go` / `-typescript`。`src/bank.py` 校验展开前总数、四域都有三档、id 与 domain/difficulty 一致。快速模式只跑 easy/medium。加到 60 条以内即可；超过先淘汰。不做 Java/C#/C++，不做 3 轮回修。

1. 在 `bank/questions.yaml` 加一条（或替换）：

```yaml
- id: knowledge-medium-04
  domain: knowledge          # architecture | coding | knowledge | reasoning
  difficulty: medium         # easy | medium | hard，必须与 id 第二段一致
  prompt: |
    题面。不要写标准答案。末行锁死输出（只输出一个整数）。
  pass_criteria: 一句话说明怎样算过
  grader:
    type: alias
    match: exact
    answers: ["0"]
```

2. 编码题 `grader.type: code_tests`，同一题面写 python / go / typescript 三套测文件：

```yaml
  grader:
    type: code_tests
    languages:
      python:
        tests_file: bank/tests/b09_foo.py
        signature: foo(xs: list[int]) -> int
      go:
        tests_file: bank/tests/go/foo_test.go
        signature: func Foo(xs []int) int
      typescript:
        tests_file: bank/tests/ts/foo.ts
        signature: "export function foo(xs: number[]): number"
```

yaml 里的 `prompt` 只写题意，不要写「只输出 Python」。加载器会按语言补围栏约束和 `signature`。测文件 stdout 必须出现 `POINTS n/m`（只认 stdout 里最后一次匹配；stderr / 编译日志里的 POINTS 不算）。没有 POINTS 记 fail，不得因 exit 0 记 pass。满点才 pass；部分对仍记 `score10`。不要用「全有或全无」的裸 `assert` 当唯一出口。Go 测文件 `package solution`；TS 从 `./solution` import。编译失败、禁运 import、或超时记 0 分。

3. grader 约定：

| type | 做什么 |
|---|---|
| `keyword` | 每组 `must_include` 1 分；命中 ≥ `min_hits` 才 pass。可选 `must_exclude`，命中则不得过 |
| `alias` | 规范化后命中 `answers` 得 1 分。`match: contains`（默认）或 `exact`。知识题用 `exact` |
| `code_tests` | 必须带 `languages`；按语言抽代码；Python 沙箱 / Go `go test` / TS `tsc`+`node`，按 `POINTS n/m` 计分 |
| `structure` | 抽 json/text 块写入 payload，跑 `tests_file` 逐条计点 |

每题折合满分 10：`score10 = 10 × n / m`。报告写分域、分难度平均折合，**不要**再合成总分。

4. 题面加盐由运行器自动加（`【审计标记 …】`），不要自己写进 yaml。
5. 检查：`python -c "from src.bank import load_questions; load_questions()"` 以及 `pytest tests/test_bank.py tests/test_grade.py`。

## 加词表（Module F catalog）

必收条见 `docs/design.md` §2.6。`minimax` / `grok2` 是可选：缺文件就跳过，不让整场 F 失败。DeepSeek V4、MiMo 与已有表探针 L1=0，只加 `model_family.yaml` 映射，不新增 catalog id。

1. 在 `catalog/manifest.json` 的 `vocabs` 加一条：

```json
{
  "id": "minimax",
  "backend": "tokenizers",
  "source_url": "https://huggingface.co/.../resolve/main/tokenizer.json",
  "source_ref": "仓库路径 + 文件名",
  "sha256": null,
  "local_path": "catalog/tokenizers/minimax.json",
  "status": "optional",
  "optional": true,
  "notes": "来源与是否和现有条目塌缩"
}
```

`backend`：`tokenizers`（HF `tokenizer.json`）、`tiktoken`（内置名）、`tiktoken.model`（Kimi BPE + `KIMI_PAT`）、`tiktoken.hunyuan`（`hy.tiktoken` + 官方 PAT）、`tiktoken.tok.json`（Grok-2 `regular_tokens` + V1 pretok）。**不要**引入 `transformers`。混元不能复用 Kimi pretok。Grok-4.x 无公开词表，不要把 `grok2` 映射过去。

2. 下载并回写 sha256：

```bash
python cursor_workspace/build_scripts/fetch_catalog.py
```

`optional: true` 的条目下载失败不让脚本以非零退出。成功后把 `sha256` 钉死。

3. 在 `catalog/model_family.yaml` 写声称型号 → catalog id。匹配是精确命中，否则最长前缀（大小写不敏感）。更长的前缀优先（`qwen3.8` 压过 `qwen3`）。

4. 加载：`src/catalog.py` 缺本地文件会 warning 并跳过该条。家族计分只用实际加载到的词表。

5. 自检：对 BASE + 现有探针算 `n_hat`，新词表与每个已有词表的 L1 不要塌成 0。至少用 `digit64` / `thai` / `emoji` 看一眼。`pytest tests/test_catalog.py`。

Llama-3/4 官方 gated，本仓库不承诺收录。

## 官方 max output

`catalog/output_limits.yaml`：型号 → 厂商文档里的 Maximum Output。DeepSeek V4 是 384000。没有登记的型号，OpenAI 兼容口不传 `max_tokens`；Anthropic 口会报错（该字段必填）。不要在题库或家族探针里写 512 / 1 这种自订配额。输出长短靠题面，不靠卡 `max_tokens`。

## 加官方渠道

多数情况只改 `src/channels/presets.py`：一个 `ChannelPreset`（`api` + `auth` + `base_url`）。线协议已经有：

- `openai-completions` / `openai-responses` / `azure-openai-completions`
- `anthropic-messages`
- `google-generative-ai` / `google-vertex`
- `bedrock-converse`（HTTP Bearer，不是 boto3；流式是 Event Stream，`--stream-metrics` 会回退到非流式）

新协议才需要新 adapter，并在 `src/channels/resolve.py` 的 `ADAPTERS` 登记。
