# model-lens 项目协作指南

本文件是仓库协作规则的唯一来源。`CLAUDE.md` 只保留一条指向本文件的说明，不重复本文件内容。

个人工具。

- 三栏独立（家族 / 判真 / 降智）；研究题库的编码、工程、推理也分栏
- 阶段分、题目分、题库分用百分制，分母是该栏自己的满分
- 禁止把不同能力栏合成一个总分
- 禁止输出「支持」
- 密钥只读环境变量

## 工作方法论

主模型是 Grok 4.6，次模型是 gpt-sol。Grok 负责读现状、改文件、跑验证和最终定稿；需要强推理、方案对照或对抗复核时再交给 gpt-sol。其他厂商模型的接口参数、effort 档位、thinking-block 协议不要写进本仓库规则。

### 第一性原理

- 动手前先明确任务要解决的核心问题，不照搬惯例或“大家都这么做”。
- 把问题拆到最小、能验证的单元，一个个解决。
- 每个决定都说得出“为什么”，而不只是“怎么做”。

### 对抗式审查（交付前必做）

- 写完先切换成最挑剔的审查者，从逻辑漏洞、事实准确性、是否有更简单的做法三个角度攻击自己。
- 主动列出最可能出错的 3 到 5 个点，改完再交。
- 不接受“看起来没问题”，必须拿出验证过的证据。

## 开场先做环境初始化

改编码沙箱、跑 `bank` / `audit`、或跑含 Go/TS 的 pytest 之前，先初始化并核对工具链。不要假设默认 PATH 里有 `go` / `node` / `tsc`（本机 `tsc` 常常不在 PATH，node 在 nvm 下）。

```bash
python cursor_workspace/build_scripts/init_env.py          # 建 .venv、钉死 typescript 5.8.2
python cursor_workspace/build_scripts/init_env.py --check  # 只检查，不安装
```

或：`bash cursor_workspace/build_scripts/init_env.sh`

通过后再用 `.venv/bin/python` / `.venv/bin/pytest`。系统 `python3` 可能是 3.9，不要用它跑测。

| 工具 | 要求 |
|---|---|
| Python | 3.11+，项目 `.venv`；没有先跑 init |
| `go` | ≥ 1.20 |
| `node` | 能跑编译产物 |
| `tsc` | 5.8.2；优先 `.cache/tsc`；init 会装，否则才退回 `npx` |

`src/toolchain.py` 会额外搜 nvm / Homebrew / `/usr/local/go`，不必改用户全局 git/nvm 配置。`Tool.ok` 含版本门槛（Python≥3.11、go≥1.20）。

## 编码沙箱（只做 python / go / ts）

同一题面展开为 `*-python` / `*-go` / `*-typescript`。不做 Java / C# / C++，不做 3 轮回修。

计分：

1. 抽不出对应语言围栏 → `missing`（`javascript`/`js` 可当 TS）
2. 本机缺该语言工具链，或 `Tool.ok` 不达标 → `missing`，`passed` / `score10` 为空，**不进 D 分母**（不记 0 分）
3. 模型代码带禁运 import（Go `net`/`os/exec`；TS `fs`/`net`/`child_process`）→ `fail` 0 分
4. 编译失败或超时 → `fail` 0 分
5. 跑完必须有 `POINTS n/m`；没有则 `fail`，不要当 pass
6. 满点才 pass；部分对仍记 `score10`

Go：`package solution`，`GOPROXY=off`，`go test -v`。TS：先 `tsc` 再 `node`。Python：现有无网沙箱。

- **三方库题**：可用指定版本的热门或非热门三方库 API 考察 API 熟悉度与抗幻觉，但版本须有官方文档 / 发布说明 / 源码标签证据，且不能越过目标模型知识时点。
- **标准库题**：走现有本机临时沙箱，不要求容器或新增运行时依赖。
- **画像声明**：`bank_manifest.py` 的 `RUNTIME_PROFILE_SPECS` 声明 profile，`ITEM_RUNTIME_PROFILES` 按题和语言绑定；profile 固定语言 / 工具链身份及精确依赖锁文件 SHA-256。
- **依赖解析**：resolver 按题使用 Python pip、Go modules 或 npm，安装物按 profile hash 缓存；安装阶段使用隔离 HOME、指定包源且禁用安装脚本，模型代码执行时禁网。当前 resolver 支持 Python hash 锁定 wheel、Go `go.mod`/`go.sum`、npm lockfile；没有题目绑定 profile 时不触发安装，active 题库目前仍为标准库题。
- **答案约束**：模型答案不得提供依赖声明或安装命令。
- **错误分类**：缺工具链记 `missing`，锁文件 / 安装基础设施错误记 `error`，两者都不记模型 fail。
- **判分口径**：以细粒度接口行为测试为准，不检查指定实现符号。

## 题库与评测架构

- 题库、运行器、打分器、汇总器分别负责题面/参考资料、请求执行、机械判分、统计展示；不要在题库模块里复制 HTTP 或汇总逻辑。
- 统一结果字段和采样统计由 `eval_bank_20260925/evaluation.py` 承载；领域评分保留自己的纯 scorer，报告适配器不得重写分母。
- 题目立足真实业务场景，考察推理、指令遵循、幻觉控制、知识广度等可迁移能力。低通过率不是保留理由。
- 新题必须通过 `docs/question-bank-quality-gate-20261006.md`；缺业务锚点或迁移证据的题只作 probe，不进入能力主测或 D 校准。
- 不通过无关日志堆长、隐藏题外操作、反常规陷阱或猜评分器来制造难度。

## 硬约束

- 不引入 `transformers`、`openai` / `anthropic` SDK，不复用 TideSight
- 不本地估算 `prompt_tokens`；Module F 必须非流式
- 不用 LLM-as-judge；报告用各栏百分制，不加跨栏合成分
- 词表文件不进 git；不要把用户 key 写入仓库
- 不要主动 commit / push，除非用户明确要求
- 对用户回复用中文
