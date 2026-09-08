# model-lens 项目协作指南

`AGENTS.md` 与 `CLAUDE.md` 内容相同，修改时必须同步。

个人工具。

- 三栏独立（家族 / 判真 / 降智）
- 禁止 0–100 总分
- 禁止输出「支持」
- 密钥只读环境变量

## 工作方法论

主模型是 Grok 4.6，次模型是 gpt-sol。Grok 负责读现状、改文件、跑验证和收口；需要强推理、方案对照或对抗复核时再交给 gpt-sol。别家模型的接口参数、effort 档位、thinking-block 协议不要写进本仓库规则。

### 第一性原理

- 动手前先回到根本：这个任务到底要解决什么问题？别照搬惯例或“大家都这么做”。
- 把问题拆到最小、能验证的单元，一个个解决。
- 每个决定都说得出“为什么”，而不只是“怎么做”。

### 对抗式审查（交付前必做）

- 写完先切换成最挑剔的审查者，从逻辑漏洞、事实对不对、有没有更简单的做法这几个角度攻击自己。
- 主动列出最可能翻车的 3 到 5 个点，改完再交。
- 不接受“看起来没问题”，得拿出验证过的证据。

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

## 硬约束

- 不引入 `transformers`、`openai` / `anthropic` SDK，不复用 TideSight
- 不本地估算 `prompt_tokens`；Module F 必须非流式
- 不用 LLM-as-judge；不加 0–100 合成分
- 词表文件不进 git；不要把用户 key 写入仓库
- 不要主动 commit / push，除非用户明确要求
- 对用户回复用中文
