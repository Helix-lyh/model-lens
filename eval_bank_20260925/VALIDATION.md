# 20260925 本地验证记录

对应候选版本 `20260925`；CP 业务挑战使用 `20260925-challenge-09`。challenge-05 仅作为历史校准基线。本记录不是模型能力测评结果。

## challenge-09 本地回归

- 每题新增一条写进题面的反常规规则，五个得分组各有一条对应用例；CP-04 有 1 条、CP-08 有 4 条旧用例的期望值随新语义更新。
- `.venv/bin/pytest -q tests/test_challenge_contracts.py`：`22 passed`。8 道参考实现回放仍为 20/20，独立 oracle 与冻结金标准一致。
- `.venv/bin/pytest -q tests/test_challenge_20260925.py tests/test_eval_hardening.py`：`17 passed`。
- 未调用真实模型。v08 的 CP pass@1=0.625 不能外推到 v09。

## CP-06 业务挑战复核

- 8 道 CP 参考实现逐题回放均为 `POINTS 20/20`。
- 每题 5 组、每组 4 个固定行为用例，合计 160 个检查批次；故意返回空结果的实现为 0/20。
- challenge-08 专项回归覆盖 contracts、orchestration、hardening 与 bank 测试；历史 `50 passed` 不作为本版数字。
- CLI 已支持 `prompt/score CP-01..CP-08 --lang python`；旧 16 题路径保持不变。

## 工具链

项目 `.venv/bin/python cursor_workspace/build_scripts/init_env.py --check` 通过：

- Python 3.11.13，使用仓库 `.venv`。
- Go 1.26.1。
- Node v24.18.0。
- TypeScript 5.8.2，使用仓库 `.cache/tsc`。

## 运行结果

1. 新题包、原评分器、工具链、活动题库和编码用例相关回归：

   `.venv/bin/pytest -q tests/test_eval_bank_20260925.py tests/test_grade.py tests/test_toolchain.py tests/test_bank.py tests/test_bank_v2_content.py tests/test_coding_v2.py`

   结果：`173 passed in 39.08s`。

2. 完成 TypeScript 特殊键修复、非有限数字检查和代码格式化后，重跑全部新题包测试：

   `.venv/bin/pytest -q tests/test_eval_bank_20260925.py`

   结果：`39 passed in 19.16s`。其中包含 8 个 Python 参考解、16 个 Go/TS 参考解、8 类定向错误实现，以及额外的 Go/TS 入口烟测。

3. 8 道推理题所有字段替换为 11 种不合规类型或空值，共 352 次评分：没有异常，分数均在 0..20 内。

4. CLI 对实际临时响应文件回放 R-X-01 完整答案：首轮 pass，score10=10，rounds_to_solve=1。

5. `questions.json` 解析结果与 `export.machine_bank()` 完全一致；评审 Markdown 与 `export.review_document()` 完全一致。

6. `ruff check eval_bank_20260925 tests/test_eval_bank_20260925.py --select F`、`git diff --check` 通过。

## 交付内容校验值

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `docs/bank-review-20260925.md` | 63682 | `a6ae6642be9b4c56e687d8d096abde529f1d0172c05cde5e781fe75a813625e0` |
| `eval_bank_20260925/questions.json` | 48515 | `7adb9631e7e8e804ff240c2ccc1bc44b51332a96bf79daa930941dc47acd64ed` |

## 未验证范围

- 未调用真实模型，因此没有 challenge-09 的模型通过率。v08 的 CP pass@1=0.625 只说明旧契约偏易；30%–50% 仍是 v09 的待实测目标。
- 未切换活动 `bank/audit`，未重新校准旧 D 阈值。
- 未实现 API 请求编排、多轮会话存储和厂商层工具禁用验证；CLI 只导出题面和评分现有回答。
- 复用的 `src.grade` 不是恶意代码隔离边界；不能将本地参考解通过视为运行任意模型代码的安全验收。
- 本次没有 commit 或 push。原有 `.idea/`、旧评审文档、旧生成脚本和 docs/INDEX.md 中已有条目保留。
