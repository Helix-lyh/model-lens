# Audit run-20261016T150433Z

- target: cat-jam-free @ <gateway>
- claimed: cat-jam-free
- reference: （无）

- 家族：qwen2_5 | 9/10 | l1=5 | 第二名 qwen3_8 | 高
- 判真：skipped（观测 qwen2_5）。无参考源
- 降智：skipped

## 流量 / 缓存 / 速率

- 请求：15/15 成功
- 输入 token：合计 1080 / 单次最大 133
- 输出 token：合计 7378 / 单次最大 2545
- 缓存命中 token：合计 320 / 单次最大 128
- 计费输入（prompt−cached）：合计 31 / 单次最大 23
- 输入/输出字符：合计 821 / 单次最大 149 / 合计 6444 / 单次最大 1437
- 墙钟延迟 ms：均值 1892.9 / 最大 7170
- 端到端输出 tok/s：均值 218.9183 / 最大 367.1673
- TTFT ms：（无）
- decode tok/s（TTFT→结束）：（无）
- 缓存命中率（有 usage 的请求均值）：0.913087
- 速率口径：e2e_wall_clock（e2e 含排队+预填；decode 要 --stream-metrics）

## 附录

### F 每条 delta vs 各候选 n_hat

| probe | delta_api | cl100k_base | o200k_base | glm4 | glm5 | qwen2_5 | qwen3_8 | deepseek_v3 | kimi | minimax | hunyuan | grok2 | dropped |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| digit64 | 64 | 22 | 22 | 43 | 43 | 64 | 64 | 22 | 22 | 22 | 64 | 64 |  |
| pi80 |  | 29 | 29 | 51 | 51 | 82 | 82 | 29 | 29 | 29 | 82 | 82 | cache_inconsistent |
| han | 13 | 19 | 14 | 12 | 12 | 13 | 11 | 12 | 10 | 12 | 12 | 13 |  |
| kana |  | 17 | 15 | 16 | 16 | 15 | 13 | 15 | 15 | 11 | 16 | 14 | cache_inconsistent |
| hangul | 11 | 15 | 10 | 12 | 12 | 11 | 8 | 13 | 14 | 9 | 14 | 13 |  |
| thai | 17 | 32 | 14 | 32 | 28 | 17 | 9 | 14 | 26 | 31 | 32 | 30 |  |
| arabic | 12 | 20 | 7 | 12 | 12 | 12 | 8 | 11 | 14 | 8 | 20 | 20 |  |
| emoji |  | 28 | 17 | 25 | 12 | 14 | 26 | 17 | 21 | 18 | 18 | 19 | cache_inconsistent |
| glue |  | 36 | 33 | 36 | 36 | 36 | 34 | 35 | 34 | 33 | 36 | 33 | cache_inconsistent |
| mixed | 17 | 16 | 14 | 13 | 13 | 17 | 17 | 13 | 13 | 13 | 17 | 18 |  |
| python | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 |  |
| special_ws | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 |  |
| gmask | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 5 | 3 | 3 | 3 | 3 |  |
| im_start | 1 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 5 | 6 | 5 |  |
