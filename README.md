# model-lens

独立仓库。用自建 `httpx` 客户端判断匿名网关 / 官方站模型属于哪一个词表家族。家族栏 **必须非流式**；题库默认同此，加 `--stream-metrics` 才走 SSE 测 TTFT / decode TPS。

渠道按 pi / DSH 的拆法：`channel` 选厂商预设，`api` 选线协议（OpenAI Completions / Responses、Anthropic Messages、Gemini、Vertex、Azure、Bedrock Converse）。不绑死 New API。不引入云厂商 SDK。MIT 许可，见 `LICENSE`。加题 / 加词表见 `docs/extending.md`。

**不引入** `openai` / `anthropic` SDK、`transformers`、TideSight。密钥只读环境变量，永不写入 jsonl / 报告 / 日志。

## 怎么跑

默认命令是 `family`：只跑家族栏。无参考源时判真/降智一律 `skipped`，不要跨族标「不支持」。`bank` 只跑题库。`audit` = F + C + I + D（无 `reference` 则 I/D = skipped）。`--quick` 为快速模式：只跑 easy/medium、每题 T=0，且 **D=skipped**。默认全量三档。禁止输出「支持」。

```bash
export TARGET_KEY=...          # 不要写进 yaml / 仓库
python -m src.cli family --target examples/targets.yaml
python -m src.cli family --target examples/targets.yaml --out out
python -m src.cli report --run out/run-xxx
python -m src.cli bank   --target examples/targets.yaml --quick
python -m src.cli bank   --target examples/targets.yaml --timeout 180
python -m src.cli bank   --target examples/targets.yaml --quick --stream-metrics
python -m src.cli audit  --target examples/targets.yaml --quick
python -m src.cli audit  --target examples/targets.yaml
python -m src.cli gallery --run out/run-a --run out/run-b --out out/gallery
python -m src.cli shell  --target examples/targets.yaml --peers glm-5.3-flash
```

`shell` 只跑附录（wrapper 常数、同网关 SKU 卡、错误信封），不改家族 / 判真 / 降智。`--peers` 省略时，若 `claimed_model` 和 target 不同，就拿声称型号当对照。

对照页：`out/gallery/gallery.html`（基层数据同目录 `gallery.json`）。每场 run 也会写 `gallery.json`。

`targets.yaml` 见 `examples/targets.yaml`（中转）、`examples/targets.official.yaml`（官方渠道）、`examples/targets.cloud.yaml`（Bedrock / Vertex）。`reference` 可省略。

```yaml
target:
  channel: zhipu          # 可选。有预设则 base_url 可省
  base_url: https://...   # 中转或覆盖预设
  api: openai-completions # 可选。覆盖线协议
  api_key_env: TARGET_KEY
  model: glm-4.5-flash
```

| channel | 默认协议 | 默认根路径 |
|---|---|---|
| `newapi` / 省略且主机不认识 | openai-completions | 必须自己写 `base_url` |
| `zhipu` / `glm` | openai-completions | `https://open.bigmodel.cn/api/paas/v4` |
| `dashscope` / `qwen` | openai-completions | DashScope compatible-mode |
| `deepseek` / `moonshot` / `doubao` | openai-completions | 各家官方兼容口 |
| `openai` | openai-completions | `https://api.openai.com/v1` |
| `openai-responses` | openai-responses | 同上 `/responses` |
| `anthropic` | anthropic-messages | `https://api.anthropic.com` |
| `google` / `gemini` | google-generative-ai | Generative Language |
| `azure` | azure-openai-completions | 必须写 resource `base_url`；`model` 是 deployment |
| `bedrock` | bedrock-converse | 根路径由 `compat.region` / `AWS_REGION` 拼；Bearer |
| `vertex` | google-vertex | 需要 `compat.project` + access token；`location` 默认 us-central1 |

只认识主机时（如 `open.bigmodel.cn`）会自动套对应渠道。自定义网关：写 `api` + `base_url`，必要时 `compat.auth`（`bearer` / `x-api-key` / `api-key` / `x-goog-api-key`）。新官方站多数情况只需在 `src/channels/presets.py` 加一行。

## Phase 1 诚实上限

| 现象 | 处理 |
|---|---|
| 中转改写 usage | F = `token_untrusted` |
| 模板随内容变 | hits 下降 → 低置信或 ambiguous |
| 官方自己量化 | I 仍可能是 `同族未分型` |
| 同家族 Flash vs Pro | 只许 `同族未分型`，禁止「支持」 |
| 8-bit / 同家族弱档 | D 允许未检出 |
| 语义缓存 | 盐只防字面缓存 |
| catalog 过时 | 新匿名模型可能落到旧代际 |

三栏独立，禁止合成总分。`prompt_tokens` 只信响应里的整数 usage（Completions 的 `prompt_tokens`、Anthropic/Responses 的 `input_tokens`、Gemini 的 `promptTokenCount`、Bedrock 的 `inputTokens`），禁止本地估算。家族栏禁止 streaming。

每条请求额外落盘 `usage`（cached / cache_write / reasoning）和 `metrics`（输入输出字符、缓存命中率、计费输入、端到端 tok/s；`--stream-metrics` 时还有 TTFT / decode tok/s）。`report` 会从 `requests.jsonl` 汇总成「流量 / 缓存 / 速率」附录。默认速率按整段墙钟。中转 streaming 的 usage 常不可信，所以测速开关默认关。

## 依赖

Python 3.11+、编码沙箱还要 `go` ≥ 1.20 和 `node`（`tsc` 5.8.2 由初始化脚本钉到 `.cache/tsc`）。词表侧用 `tiktoken` / `tokenizers`，不引入 `transformers`。

Agent / 本机开场先跑：

```bash
python cursor_workspace/build_scripts/init_env.py
python cursor_workspace/build_scripts/init_env.py --check
```

缺 `go` / `node` 时对应语言题记 missing，不记模型 0 分。约定见 `AGENTS.md`。
