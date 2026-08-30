# model-lens Agent 说明

个人工具。三栏独立（家族 / 判真 / 降智），禁止 0–100 总分，禁止输出「支持」。密钥只读环境变量。

## 0. 开场先做环境初始化

改编码沙箱、跑 `bank` / `audit`、或跑含 Go/TS 的 pytest 之前，先初始化并核对工具链。不要假设默认 PATH 里有 `go` / `node` / `tsc`（本机 `tsc` 常常不在 PATH，node 在 nvm 下）。

```bash
python cursor_workspace/build_scripts/init_env.py          # 建 .venv、钉死 typescript 5.8.2
python cursor_workspace/build_scripts/init_env.py --check  # 只检查，不安装
```

或：`bash cursor_workspace/build_scripts/init_env.sh`

通过后再用 `.venv/bin/python` / `.venv/bin/pytest`。系统 `python3` 可能是 3.9，不要用它跑测。

| 工具 | 要求 | 没有时 |
|---|---|---|
| Python | 3.11+，项目 `.venv` | 先跑 init |
| `go` | ≥ 1.20 | 编码 `-go` 题记 **missing**，不记 0 分 |
| `node` | 能跑编译产物 | 编码 `-typescript` 题记 **missing** |
| `tsc` | 5.8.2；优先 `.cache/tsc` | init 会装；否则才退回 `npx` |

`src/toolchain.py` 会额外搜 nvm / Homebrew / `/usr/local/go`，不必改用户全局 git/nvm 配置。`Tool.ok` 含版本门槛（Python≥3.11、go≥1.20）；不达标与缺工具一样记 missing，不进 D。

## 编码沙箱（只做 python / go / ts）

同一题面展开为 `*-python` / `*-go` / `*-typescript`。不做 Java / C# / C++，不做 3 轮回修。

计分：

1. 抽不出对应语言围栏 → `missing`（`javascript`/`js` 可当 TS）
2. 本机缺该语言工具链 → `missing`，`passed` / `score10` 为空，**不进 D 分母**
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
