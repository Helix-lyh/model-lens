# model-lens 项目协作指南

本文件是仓库协作规则的唯一来源，开工前必须完整读取并遵守。`CLAUDE.md` 只有一行 `@AGENTS.md` 导入本文件，不另写规则。

model-lens 用自建 `httpx` 客户端判断匿名网关 / 官方站模型属于哪个词表家族，并可选地对照参考源做型号判真与能力降智粗筛。个人工具，非取证、非生产门禁。

```yaml
oh_my_team:
  source: /Users/helix/Code/oh-my-team
  entry: ENTRY.md
  exclude: [design-handoff, ui-implementation, frontend-quality, vercel-react-best-practices, agent-browser, e2e-testing, mobile-delivery]
  capabilities: [git, shell, api]

project_knowledge:
  decisions: docs/decisions/
  memory: docs/memory/
  learnings: docs/learnings/
```

## oh-my-team

- 任务开始先读 `/Users/helix/Code/oh-my-team/ENTRY.md`，按意图选择流程、技能和知识，只打开选中的文件；`exclude` 里的技能不读。
- 同名或同用途时以 oh-my-team 为准，全局技能只用于它没有覆盖的场景。
- 读的是本机 checkout 的当前内容。路径不可读或路由指向的文件不存在时停止并报告，不改用全局副本、旧缓存或其他项目的上下文。
- 只使用 `capabilities` 声明的能力；生产部署另需明确授权。
- 用户消息以 `omt:` 开头时，按 `ENTRY.md` 的「`omt:` 快捷触发」组合技能：先输出一行计划，再按阶段执行。
- 调研结束、找到根因、交付完成或方案含通用部分时，按 oh-my-team 的 `codify` 技能向用户提议沉淀：零散内容整理成系统化文档，项目专属的写进本仓 `project_knowledge`，跨项目成立的写回 oh-my-team；用户确认大纲后才写。

## 项目结构与关键模块

- `src/`：CLI（`src/cli.py`，子命令 `family` / `bank` / `audit` / `report` / `gallery` / `shell`）、渠道预设与线协议（`src/channels/`）、词表家族匹配、判分与报告。
- `eval_bank_20260925/`：题库与评测框架。统一结果字段和采样统计在 `evaluation.py`；题库清单与运行时画像声明在 `bank_manifest.py`、`runtime_profiles.py`。
- `bank/`、`catalog/`、`probes/`、`runtime_profiles/`：题库数据、词表 manifest 与家族配置、家族探针、依赖锁定画像。
- `examples/`：目标配置示例；`web/`：对照页静态资源；`out/` 是跑次产物，不进 git。
- `cursor_workspace/build_scripts/`：本机辅助脚本（环境初始化、词表下载、实网探测、题库核对），不是产品 CLI。
- `tests/`：pytest 套件；`docs/`：设计、评测契约与交接记录，入口 `docs/INDEX.md`，加题 / 加词表见 `docs/extending.md`。

## 常用命令

环境初始化见下节。运行与测试：

```bash
.venv/bin/python -m src.cli family --target examples/targets.yaml
.venv/bin/python -m src.cli bank   --target examples/targets.yaml --quick
.venv/bin/python -m src.cli audit  --target examples/targets.yaml --quick
.venv/bin/pytest
python3 cursor_workspace/build_scripts/fetch_catalog.py   # 下载词表（不进 git）
```

## 项目特有约定与禁区

- 三栏独立（家族 / 判真 / 降智）；研究题库的编码、工程、推理也分栏
- 阶段分、题目分、题库分用百分制，分母是该栏自己的满分
- 禁止把不同能力栏合成一个总分
- 禁止输出「支持」
- 密钥只读环境变量

### 工作方法论

第一性原理、根因修复等通用原则见 oh-my-team 的 `knowledge/shared/team-principles.md`。

个人的模型选择与分工写在本地 `AGENTS.local.md`（已 gitignore），不写进本仓库规则。其他厂商模型的接口参数、effort 档位、thinking-block 协议同样不写入。

#### 对抗式审查（交付前必做）

- 写完先切换成最挑剔的审查者，从逻辑漏洞、事实准确性、是否有更简单的做法三个角度攻击自己。
- 主动列出最可能出错的 3 到 5 个点，改完再交。
- 不接受“看起来没问题”，必须拿出验证过的证据。

### 开场先做环境初始化

改编码沙箱、跑 `bank` / `audit`、或跑含 Go/TS 的 pytest 之前，先初始化并核对工具链。不要假设默认 PATH 里有 `go` / `node` / `tsc`（本机 `tsc` 常常不在 PATH，node 在 nvm 下）。

```bash
python3 cursor_workspace/build_scripts/init_env.py          # 建 .venv、钉死 typescript 5.8.2
python3 cursor_workspace/build_scripts/init_env.py --check  # 只检查，不安装
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

### 编码沙箱（只做 python / go / ts）

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

### 题库与评测架构

- 题库、运行器、打分器、汇总器分别负责题面/参考资料、请求执行、机械判分、统计展示；不要在题库模块里复制 HTTP 或汇总逻辑。
- 统一结果字段和采样统计由 `eval_bank_20260925/evaluation.py` 承载；领域评分保留自己的纯 scorer，报告适配器不得重写分母。
- 题目立足真实业务场景，考察推理、指令遵循、幻觉控制、知识广度等可迁移能力。低通过率不是保留理由。
- 新题必须通过 `docs/question-bank-quality-gate-20261006.md`；缺业务锚点或迁移证据的题只作 probe，不进入能力主测或 D 校准。
- 不通过无关日志堆长、隐藏题外操作、反常规陷阱或猜评分器来制造难度。

### 硬约束

- 不引入 `transformers`、`openai` / `anthropic` SDK，不复用 TideSight
- 不本地估算 `prompt_tokens`；Module F 必须非流式
- 不用 LLM-as-judge；报告用各栏百分制，不加跨栏合成分
- 词表文件不进 git；不要把用户 key 写入仓库
- 不要主动 commit / push，除非用户明确要求
- 对用户回复用中文
