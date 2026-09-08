# 壳 / SKU 卡字段

报告附录用。不进家族 / 判真 / 降智。不合成总分，不写「支持」。主合同见 [design](design.md) 文末附录。

```bash
python -m src.cli shell --target examples/targets.yaml --peers glm-5.3-flash
```

请求：非流式；`max_tokens` 不传或走官方上限，禁止 `1`。禁止本地估算 `prompt_tokens`。禁止 `transformers` / `openai` SDK。

本地对照禁止 `encode(x)` 对 `delta(BASE+x)`。F 的 `n_hat` 仍是 `encode(BASE+x) − encode(BASE)`。

## wrapper

```
wrapper = prompt_tokens(text) − encode_len(text)
```

同一对照词表、几档长度：差恒定（允许 ±1）才认模板。否则 drift / untrusted。词表 id 只标注用了哪把尺子，不是家族结论。

## SKU 卡（同网关 A/B）

| 字段 | 算法 | 备注 |
|---|---|---|
| `hi_prompt_tokens` | `T("hi")` | 壳厚度 |
| `emoji_delta` | `T(base+emoji) − T(base)` | API 侧差分 |
| `special_image_delta` | `T(hi + "<|begin_of_image|>") − T(hi)` | 只发字面量，不发图 |
| `reasoning_effort` | extra `reasoning_effort=none` | 记 HTTP / 错误码 |

不做图、不做视频。对不上只写「SKU 卡不一致」，不改 I。

## envelopes

畸形参数 → 错误文案分类：serde / 智谱数字码 / 双信封。输出服务栈标签。缺响应或网关改写 → 只落盘。认服务，不认权重。
