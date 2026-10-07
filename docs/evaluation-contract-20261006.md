# 统一题库评测合同（2026-10-06）

这是题库升级的长期承载文档。题面可以按领域使用不同的输入和输出协议，但运行、判分和汇总使用共同的身份、状态和统计合同：`eval_bank_20260925/evaluation.py`。领域 prompt/scorer 由 `bank_adapters.py` 插件注册表适配；runner 不再按题号直接选 scorer。NX、Toyama 等专用入口仍可保留各自请求编排，但结果交给相同的 verdict 与统计 primitive。

## 统一边界

1. 题库 manifest 负责 bank/item 身份、版本、生命周期和 adapter 选择；题面模块提供公开输入/输出协议、参考答案/隐藏夹具和字段分组。不在题库模块复制 HTTP、并发、重试或汇总逻辑。
2. `BankAdapter` 是可插拔边界：`prompt(item, language)` 和 `score(item, response, language)`。registry 在启动时校验 manifest 引用都已注册；adapter 不能执行网络请求或写报告。
3. 执行器负责计划 job、独立 sample 序号、请求预算、随机盐、原始响应落盘、超时和渠道元数据。每条结果保留 `experiment_id`、`bank_id/version`、`adapter_id`、`scorer_sha256`、题面 hash、语言、sample、状态和原始响应位置等追溯字段。基础设施重试沿用同一 sample，不增加 pass@k 样本数。
4. 评分器返回统一状态 `status`、`reason_code`、`passed`、`points`、`points_total`；普通题型可返回 `score10` 和 `groups`，工程题返回正/负/净账，不虚构 `score10`。`normalize_verdict()` 拒绝矛盾状态、越界分数和不一致量尺。
5. 汇总只消费判定记录，不重跑 scorer。`pass@k` 的样本身份包含实验、渠道/模型、bank/version、prompt hash、scorer hash、题号、语言与 sample；每题以 `1-C(n-c,k)/C(n,k)` 估算，再对有至少 k 个已判独立样本的题等权平均。超时是 fail 并进入总体；error/missing/pending 不算作答对或作答错，样本不足的题不进入 pass@k eligible 分母。
6. 栏目累计分按已判样本的 points/points_total 加总；题内 group 同名字段只在相同 bank/version 内累计。不同栏目始终分开，报告不生成跨栏总分。工程分开呈现 positive、negative、net 和严格满分通过数。

## 编码执行画像

当前标准库题共用本机临时语言 sandbox，不要求容器或额外运行时依赖。`bank_manifest.py` 以 `RUNTIME_PROFILE_SPECS` 声明 profile、以 `ITEM_RUNTIME_PROFILES` 按题号/语言绑定；registry 在启动时验证引用。独立 resolver 按题使用 pip hash-locked wheels、Go `go.mod`/`go.sum` 或 npm lockfile，在内容寻址缓存中准备依赖；安装过程使用隔离 HOME、指定公共包源、禁用 package lifecycle scripts，Python 仅接收带 hash 的二进制 wheel。模型代码执行仍使用本机临时目录和现有禁网环境，不接收包管理器凭据。执行器通过 Python path、Go module cache 或临时 node_modules 接入缓存，不改用户全局环境。缺工具链记 `missing`，lockfile/hash/安装故障记 `error`，都不记模型 fail。结果行记录 `runtime_profile_id` 与 profile hash，使 pass@k 只在相同运行环境下比较。manifest 当前未将 profile 绑定到任何 active 题，因此第三方库题尚未进入 active 分数；跨平台执行依赖各宿主已安装的本机语言工具链，不依赖 Apple Container 或其他容器守护进程。

## 超时合同

- 空响应超时：`status=fail`、`reason_code=timeout`、所有积分为 0。
- 有可解析阶段的超时：运行原题 scorer，保留已返回字段积分，强制 `status=fail`、`passed=false`、`reason_code=timeout_partial`；未返回阶段为 0。
- 请求错误、缺工具链、夹具崩溃不伪装成模型失败，继续用 `error`/`missing`，不进入能力分母。
- `pass@k` 使用判分后的 `pass`/`fail` 样本。超时阶段分不丢失，也不能让超时样本变成通过。

## 生命周期与研究资格

`eval_bank_20260925/bank_manifest.py` 是生命周期清单：

| bank | 状态 | 用途 |
| --- | --- | --- |
| `business-coding` 20261008 | active | CP-09..18，每题一种语言：4 Python、3 Go、3 TypeScript |
| `business-engineering` 20261008 | active | E-01..10，正分、负分、净分各自换算成百分数 |
| `business-reasoning` 20261008 | active | NX-09..18 |

活跃全量入口是 `cursor_workspace/build_scripts/run_eval.py`。它只依赖题目注册表、统一 `evaluation.score_item`、统一统计和报告。quick 跑 CP-09、E-07、NX-09。`rebuild_eval_summary.py` 从不可变的 `results.jsonl` 重建统计和报告，不调用模型；旧结果缺少的版本身份必须继续视为 unknown，重建不反向伪造。

## 题库真实性门禁

题库不以“能把某模型通过率压到目标区间”为保留理由。每道题进入研究或主测前，评审记录以下证据：

1. **业务锚点**：对应真实工作中的决策、状态、约束或沟通任务；能指出使用者和错误代价。
2. **能力映射**：明确主要考察推理、指令遵循、幻觉控制、知识广度中的哪一项，次要能力不超过两项。
3. **迁移价值**：换数据、换领域或换表达后仍考察同一能力；不是只记住字段、顺序、隐藏规则或固定答案。
4. **规则必要性**：删除一条规则会改变真实决策或结果，而不是只改变评分器触发点。
5. **反测试化检查**：无无关日志堆长、无刻意反常规陷阱、无题面之外的隐藏操作、无只能靠猜评分器的字段。
6. **独立复核**：至少一个不写 scorer 的评审者能从题面说明正确性、边界和业务合理性。

未满足这些门禁的题只能标为 `probe`，报告必须单独展示，不能用于模型能力结论或 D 指标校准。NX 的长日志、Toyama 的后置条件机制题和 CP 的反常规规则目前都应按 probe 处理，除非补齐业务锚点与迁移证据。

## 难度目标和出题策略

目标不是把同一计算拉长，而是让规则改变状态转移或最优选择。目标模型为 DeepSeek Flash 级别：主测通过率约 30%–50%，同时保留少量快速验证题。

- 新规则必须改变参考状态机的关键结果；删除规则后标准答案应变化。
- 每题保持 20 分字段账，阶段字段独立给分；最终值错不能抹掉已正确阶段。
- 行数只做微调：规则交互优先，避免无关日志、重复编号、提示捷径和第二种读法。
- 现实参数先做整库单位/数量合理性核验，再一次性改题库；例如交通时刻按秒、门诊/外卖/换乘按分钟、水果按天。
- 八题场景应分散在路口、门诊、外卖、水果、换乘等业务，不把所有题收成同一种回放。
- 每次升级先本地重放参考答案和边界小例，再用 booster 双渠道、每渠道并发 8、独立采样验证；结果以目录 `summary.md` 和原始 `results.jsonl` 为准。

## 版本边界

活动题库升级时同时更新题库版本、评分器测试和本文件的 manifest；执行器只引用统一合同。旧实验保持旧版本可重放，不把不同版本的通过率合并为一个数字。
