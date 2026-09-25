# model-lens 文档

个人兴趣工具：对 OpenAI 兼容中转（含 New API）及官方站做**家族归属 / 型号判真 / 降智**三栏独立审计。非取证、非生产门禁。不是 TideSight 子项目。

安装、命令与密钥约定见仓库根目录 [README](../README.md)。现行实现合同是 [design](design.md)。题库内容快照版本 **2026090901**（`scorer-v2` / `single-v1` 是协议戳，不是题面版本）。

| 文档 | 用途 |
|---|---|
| [design](design.md) | **现行可执行方案**。执行只按本文。 |
| [extending](extending.md) | 加题、加词表、加官方渠道。 |
| [sku-wrapper](sku-wrapper.md) | 附录：wrapper / 同网关 SKU / 错误信封。不进 F/I/D。 |
| [bank-v2-design](bank-v2-design.md) | 题库内容题设计与参考答案（版本 2026090901）。 |
| [question-bank-evolution](question-bank-evolution.md) | 题库改写约束与版本边界。 |
| [coding-v2-validation](coding-v2-validation.md) | 编码 fixture 与 POINTS 协议。 |
| [bank-answers](bank-answers.md) | 参考答案索引。答案不进题面。 |
| [bank-review-2026090901](bank-review-2026090901.md) | **评审材料**：54 题题面 + 参考答案 + 判分点 + fixture 全文，单文件。由 `cursor_workspace/build_scripts/build_bank_review.py` 生成。 |
| [bank-review-20260925](bank-review-20260925.md) | **新候选题库 20260925**：四档 16 道核心题、参考答案、内容分点和三语言用例目录；尚未切换活动题库。 |
| [bank-design-20260925](bank-design-20260925.md) | 新版设计、Grok 包核对、有限轮次评分和实测校准边界；运行入口见 [候选包说明](../eval_bank_20260925/README.md)。 |
| [eval-run-routing](eval-run-routing.md) | **20260925 跑测路由与口径**：渠道接线、密钥环境变量名、grok CLI 代理头、独立采样 pass@k 约定；不记密钥值。 |
| [review-20260830](review-20260830.md) | **过时**历史评审。不要按其中的旧参数实现（例如 `max_tokens=1`）。 |

2026-08-30 原稿已由 `design.md` 取代，本地路径不收录。
