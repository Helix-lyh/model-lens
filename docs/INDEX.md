# model-lens 文档

个人兴趣工具：对 OpenAI 兼容中转（含 New API）及官方站做**家族归属 / 型号判真 / 降智**三栏独立审计。非取证、非生产门禁。不是 TideSight 子项目。

安装、命令与密钥约定见仓库根目录 [README](../README.md)。现行实现合同是 [design](design.md)。题库内容快照版本 **20260908**（`scorer-v2` / `single-v1` 是协议戳，不是题面版本）。

| 文档 | 用途 |
|---|---|
| [design](design.md) | **现行可执行方案**。执行只按本文。 |
| [extending](extending.md) | 加题、加词表、加官方渠道。 |
| [sku-wrapper](sku-wrapper.md) | 附录：wrapper / 同网关 SKU / 错误信封。不进 F/I/D。 |
| [bank-v2-design](bank-v2-design.md) | 题库内容题设计与参考答案（版本 20260908）。 |
| [question-bank-evolution](question-bank-evolution.md) | 题库改写约束与版本边界。 |
| [coding-v2-validation](coding-v2-validation.md) | 编码 fixture 与 POINTS 协议。 |
| [bank-answers](bank-answers.md) | 参考答案索引。答案不进题面。 |
| [review-20260830](review-20260830.md) | **过时**历史评审。不要按其中的旧参数实现（例如 `max_tokens=1`）。 |

2026-08-30 原稿已由 `design.md` 取代，本地路径不收录。
