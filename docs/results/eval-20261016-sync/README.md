# 三模型同步评测记录（2026-10-16）

题库版本 **20261018**（`business-coding` / `business-engineering` / `business-reasoning`），计分版本 **20261018.s1**；阶段 hard，语言 python/go/typescript，流式，每渠道并发 8，超时 1200 s，重试 3，每请求独立随机盐。三个模型同经一个 OpenAI 兼容网关（地址已去敏为 `<gateway>`），不记密钥。

## 参数

| 渠道 | max_tokens（= catalog `output_limits.yaml` 官方最大输出） | 词表家族（vocab 探针） |
|---|---:|---|
| beam-free | 131072（用户口述 1048576 为 context；按 1048576 发送被上游 `context_length_exceeded`，见 solo 失败批次未收录） | qwen2_5，12/13，l1=5，第二名 hunyuan，**高** |
| cat-jam-free | 131000 | qwen2_5，9/10，l1=5，第二名 qwen3_8，**高** |
| deepseek-flash | 384000 | deepseek_v3，14/14，l1=0，第二名 o200k_base，**高** |

词表结论：beam-free、cat-jam-free 的 tokenizer 指纹落在 qwen2_5 桶（该桶含 Qwen2.5 / Qwen3 / MiMo，不能再细分）；deepseek-flash 落在 deepseek_v3 桶，与其声称一致。映射已写入 `catalog/model_family.yaml`。

## 时间（Asia/Shanghai）

- 同步跑：三模型 hard 同时起跑 2026-10-16 23:03:29；nx3（推理 ×3 采样）beam/cat-jam 23:18:49、deepseek 23:19:29。首轮 nx3 与 hard 时间重叠已中止，不收录。
- 历史单独跑（同题库 20261018）：deepseek-flash 2026-10-12 16:12；cat-jam-free 2026-10-14 01:34；beam-free 2026-10-16 22:33（hard）/ 22:35（nx3）。

## 对照表（固定分母：截断/超时/错误记 0 分）

hard（各题 1 次采样，每栏 10 题，满分 200）：

| 渠道 | 批次 | 编码 | 工程（净分） | 推理 | 编码通过 | 推理通过 |
|---|---|---:|---:|---:|---:|---:|
| beam-free | 同步 10-16 | 54.0% | 29.0% | 74.0% | 3 | 7 |
| beam-free | 单独 10-16 | 60.0% | 36.5% | 64.0% | 4 | 6 |
| cat-jam-free | 同步 10-16 | 52.0% | 38.0% | 70.0% | 3 | 7 |
| cat-jam-free | 单独 10-14 | 42.0% | 31.5% | 57.0% | 2 | 5 |
| deepseek-flash | 同步 10-16 | 46.0% | 32.5% | 80.0% | 3 | 8 |
| deepseek-flash | 单独 10-12 | 36.0% | 36.5% | 84.0% | 0 | 8 |

nx3（推理 10 题 × 3 采样，满分 600）：

| 渠道 | 批次 | 得分 | pass@1 | pass@3 | 超时 |
|---|---|---:|---:|---:|---:|
| beam-free | 同步 | 72.7% | 0.667 | 0.8 | 0 |
| beam-free | 单独 | 71.7% | 0.667 | 0.7 | 0 |
| cat-jam-free | 同步 | 75.7% | 0.700 | 0.8 | 0 |
| cat-jam-free | 单独 | 71.3% | 0.667 | 0.9 | 1 |
| deepseek-flash | 同步 | 82.7% | 0.800 | 0.8 | 0 |
| deepseek-flash | 单独 | 83.0% | 0.767 | 0.8 | 0 |

全部批次截断 0。

## 波动

- 单次 hard 波动大：同模型两次之间编码 ±6~10 个百分点、推理 ±4~13、工程 ±4~8。单栏 10 题、单采样下一题之差就是 10%（编码/推理）——hard 单次结果不足以排序 beam 与 cat-jam。
- nx3 稳定得多：同模型两批差 ≤4.4 个百分点；deepseek-flash 两批 82.7 / 83.0。
- 推理排序（nx3）：deepseek-flash（≈83%）明显领先；beam-free 与 cat-jam-free（71~76%）差距在噪声内。
- 区分题：NX-16 deepseek 6/6 满分，beam 0/6，cat-jam 1/6；NX-09 三家都很低（36 次中 3 次满分）；NX-14 三家都只拿部分分（≤8/20）；NX-18 cat-jam/beam 单次偶失分，nx3 基本满分。
- 工程栏三家严格通过均为 0，净分 29~38%，差异小于单次波动。

## 数据

`data/` 下按 `sync/<渠道>/{hard,nx3}`、`solo/<渠道>-<日期>/{hard,nx3}` 存 `summary.md`、`summary.json`、`results.jsonl`；`data/vocab/*.report.md` 为词表报告。results 已精简：去掉原始回答、盐、请求错误正文与 detail/report 大字段，仅保留题号、状态、得分、分组、usage、延迟、哈希等；网关地址替换为 `<gateway>`。原始目录在 box `/workspace/scratch/model-lens-sync-2026-10-16/` 等处，不入库。
