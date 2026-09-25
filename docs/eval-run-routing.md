# 20260925 题库跑测路由与口径

记录题库 20260925 实测的渠道接线、密钥环境变量和跑测口径。**只记环境变量名，不记密钥值。**
核对时间：2026-09-25。渠道可用性会变，改动后回来更新本表。

## 渠道

| 渠道 | 当前实际路由 | 密钥环境变量 | model id | 单次输出上限 |
|---|---|---|---|---|
| deepseek-flash | `$BOOSTER_BASE_URL` + `/v1` | `BOOSTER_API_KEY` | `deepseek-flash` | 384000 |
| deepseek-chat（官方校准） | `$DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）+ `/v1` | `DEEPSEEK_API_KEY` | `deepseek-chat` | 384000 |
| mimo-v2.6-flash | `$BOOSTER_BASE_URL` + `/v1` | `BOOSTER_API_KEY` | `mimo-v2.6-flash` | 131072 |
| grok-4.6 | `$AI_LIUYUNHAI_SPACE_BASE_URL` | `AI_LIUYUNHAI_SPACE_API_KEY`（supergrok 分组） | `grok-4.6` | 65536 |
| grok-4.7 | `$AI_LIUYUNHAI_SPACE_BASE_URL` | `AI_LIUYUNHAI_SPACE_API_KEY`（supergrok 分组） | `grok-4.7` | 65536 |

- `BOOSTER_BASE_URL` 只有 origin（如 `http://ai.booster.woa.com`），API 根路径是 `/v1`，runner 会自己补。
- `deepseek-chat` 走官方端点 `api.deepseek.com`，密钥只读 `DEEPSEEK_API_KEY`；`DEEPSEEK_BASE_URL` 只用于改 origin（自建代理时用）。官方回包的 `model` 字段是 `deepseek-flash`，逐题行按原样记在 `response_model`，不做映射。
- `AI_LIUYUNHAI_SPACE_BASE_URL` / `AI_LIUYUNHAI_SPACE_API_KEY` 是自有 New API 网关。**分组取自 token，不取请求**：请求侧 `?group=`、body `group`、`New-Api-Group` 等头都改不了分组。
- grok 需用 `supergrok` 分组的 token，该组含 `grok-4.6` / `grok-4.7`；`grok-4.5` 当前不在任何可用分组。换 token 后只需把 `AI_LIUYUNHAI_SPACE_API_KEY` 指向它。
- 网关回包里 grok 的 `model` 字段是 `grok-4.6-build` / `grok-4.7-build`，与直接打 xAI 模型不完全等价，报告里保留原始回包。
- 备用路由：本机 Grok CLI 的 OIDC 代理 `https://cli-chat-proxy.grok.com/v1`，需 `X-XAI-Token-Auth: xai-grok-cli`、`x-grok-client-version: 1.0.41` 和 `x-grok-model-override: <model>` 头（不带版本头会 426）。runner 用 `--grok-cli-proxy` 切换。

## 口径

- 默认单轮 **pass@1**：每题只发一次，不做修复轮；第一轮内容分满 20 且协议合规才算 pass。需要独立采样时用 `--samples n --pass-at k`，每个 `(channel,item,lang,sample)` 都保留一行；`pass@k = 1 - C(n-c,k)/C(n,k)`，只对同题已判分的独立样本计算，样本不足返回 null。
- `temperature=0` 下独立采样量的是**重跑稳定性**，不是答案多样性：v08 金标准 + deepseek-chat 两采样，24 题里 20 题两次都过、1 题一次过一次不过（R-X-01）、3 题两次都不过（CP-02/CP-04/CP-05）；编程题两次响应文本几乎都不同，部分推理题逐字节相同。要测多样性得先放开 `temperature` 并同步改本口径。
- n=2 的单轮 CP 结论不要当稳定能力值：CP-06 题面与金标准两轮都没变，v07 轮次两次都只有 5/20，v08 轮次两次都 20/20。同题跨轮翻转说明单轮 n=2 的方差足以盖过一档难度差。
- 基础设施重试不新增 sample；`solve_within_k` / `repair` 是带反馈修复轮，不能并入 pass@k。
- `temperature=0`，`reasoning_effort=high`（四渠道统一）。
- 编程题当前只跑一种语言（Python）以控费；`model_prompt(item, lang)` 里 `lang` 只对编程题生效。
- CP-01..CP-08 属于 `challenge_coding` 的校准题，入口固定为 Python `solve(data)`；`run_eval --items CP-01` 与 `challenge_live --kind coding --items CP-01` 都会执行 `score_saved`，不再标成待审。
- 每渠道并发 2，四渠道并行。`--samples` 会增加模型请求数，`--pass-at` 必须满足 `1 <= k <= samples`。
- 校准实测（2026-09-25，v08，官方 `deepseek-chat` 路由，回包 `model=deepseek-flash`，`--samples 2 --pass-at 2`）：CP 8 题 pass@1=0.625、pass@2=0.625；目录题 16 题 pass@1=0.969、pass@2=1.0；全 24 题 pass@1=0.854、pass@2=0.875。回包模型已经是 `deepseek-flash`，不把 booster 密钥当成另一条能力总体。0.625 高于 30%–50%，v09 改为加写进题面的反常规规则；v09 尚未有同口径实测。
- 两阶段：先 `--phase quick`（easy+medium），再 `--phase hard`（hard+extreme）。
- missing（抽不出代码围栏 / 本机缺工具链）不进分母，单独报数。
- 每条请求在题面前加入独立随机盐；结果行记录 `salt`、基础题面哈希和加盐题面哈希。HTTP 单次超时或墙钟耗时超过 `--timeout` 记 `error/timeout`，截断回包（`finish_reason=length`）记 `error/response_truncated`，两者都不进能力分母。
- `run_eval` 按题完成立即追加并 `fsync` `results.jsonl`；单题/渠道异常会保留带 `item`、`lang` 的错误行。渠道初始化或 worker 异常会在汇总后以退出码 1 暴露。

## 跑法

当前 CP 题库版本为 `20260925-challenge-09`（`challenge.py` 的 `REVISION`，金标准走 `challenge_goldens_v09`）。`pass@k` 只计同题已判分样本中的严格布尔 `passed is True`；`n < k` 返回 null，missing/error/timeout 单独报告，`temperature=0` 的重复样本只表示稳定性。

```bash
cd ~/Code/model-lens
# 四渠道：deepseek/mimo 走 BOOSTER_*，grok-4.6/4.7 走 AI_LIUYUNHAI_SPACE_*（需 supergrok 分组 token）
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --langs python --concurrency 2
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase hard  --langs python --concurrency 2

# 只重跑 grok 两档
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --models grok-4.6,grok-4.7

# DeepSeek 官方 key 的 pass@1 / pass@2（独立采样 2 次，一次跑出两个口径）
export DEEPSEEK_API_KEY=...   # 只从环境变量读，不落盘
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --models deepseek-chat --samples 2 --pass-at 2 --concurrency 4
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase hard  --models deepseek-chat --samples 2 --pass-at 2 --concurrency 4
.venv/bin/python cursor_workspace/build_scripts/merge_eval_20260925.py out/eval-...-quick out/eval-...-hard --pass-at 2 --out out/eval-merged-ds-official

# 备用：grok 改走本机 Grok CLI OIDC 代理
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --models grok-4.6,grok-4.7 --grok-cli-proxy

# CP 校准（只跑 Python；题号可重复但会稳定去重）
.venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --items CP-01,CP-01 --models deepseek-flash
.venv/bin/python -m eval_bank_20260925.challenge_live --kind coding --items CP-01 --base-url "$BOOSTER_BASE_URL"

# 合并重跑：有效 pass/fail 不会被后一次 error/missing 覆盖；--out 可落盘合并物
.venv/bin/python cursor_workspace/build_scripts/merge_eval_20260925.py out/eval-...-quick out/eval-...-retry --out out/eval-merged
```

结果落在 `out/eval-20260925-<stamp>-<phase>/`：`summary.md` / `summary.json`（分渠道、分难度、分域 pass@1/pass@k）、`results.jsonl`（逐题，增量落盘，含 `sample`）、`<channel>/<item>[_<lang>][-s<sample>].txt`（原始响应）、`<channel>/requests.jsonl`（含 usage 的落盘记录）。CP 校准结果沿用同一逐题 schema，`pending_review` 只保留给未接评分器的外部结果，不代表 CP。

`--grok-cli-proxy` 显式切回 CLI 代理；不带该开关且给了 `--grok-base` 时走网关。
