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
| [eval-run-routing](eval-run-routing.md) | **跑测路由与口径**：渠道接线、密钥环境变量名、grok CLI 代理头、独立采样 pass@k 约定；不记密钥值。 |
| [evaluation-contract-20261006](evaluation-contract-20261006.md) | **统一题库评测合同**：题库生命周期、执行器/评分器/汇总边界、超时和活动题库策略。 |
| [evaluation-naming](evaluation-naming.md) | **题库与运行命名规范**：稳定 bank_id、独立版本、生命周期与 sample 身份。 |
| [question-bank-quality-gate-20261006](question-bank-quality-gate-20261006.md) | **题库真实性门禁**：业务锚点、能力映射、迁移价值和反测试化检查。 |
| [question-bank-methodology-20261008](question-bank-methodology-20261008.md) | **活跃题库出题方法论（版本 20261008）**：难度梯度、编码/工程/推理的难度提升边界和校准口径。 |
| [question-bank-next-design-20261008](question-bank-next-design-20261008.md) | **20261008 活跃题库总稿**：题量、旧题处置、新题分册索引和自检。 |
| [question-bank-next-coding-20261008](question-bank-next-coding-20261008.md) | **20261008 活跃编码题册**：10 道三语言同契约题的完整题面、判分点和参考行为。 |
| [question-bank-next-engineering-20261008](question-bank-next-engineering-20261008.md) | **20261008 活跃工程题册**：v3.3 留用题和 4 道新增许愿式生产需求。 |
| [question-bank-next-reasoning-20261008](question-bank-next-reasoning-20261008.md) | **20261008 活跃推理题册**：10 道跨业务时间线、状态和约束题。 |
| [engineering-handoff-20261006](engineering-handoff-20261006.md) | **工程题交接**：优化方向、实测和现行策略。代码版本 v3.3。 |
| [review-20260830](review-20260830.md) | **过时**历史评审。不要按其中的旧参数实现（例如 `max_tokens=1`）。 |

2026-08-30 原稿已由 `design.md` 取代，本地路径不收录。
