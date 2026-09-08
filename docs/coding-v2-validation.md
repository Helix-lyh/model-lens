# Coding v2 validation

本次仅强化 `coding-extreme-03`（`bounded_knapsack`）的三语言 fixture，未修改题面、`src/*` 或评分器。

## 覆盖

- 保留原有 6 个边界、全局最优、负价值和稳定 tie-break 用例。
- Python、Go、TypeScript 各新增 12 组确定性生成用例；每组 5 项，容量由 seed 推导。
- 三语言 fixture 各自执行小规模子集穷举 oracle，按最大 value、最小 weight、indices 升序字典序比较。
- 因此每种语言计分从 6 题扩展为 18 题，可拒绝贪心、容量边界错误、价值相同但重量错误，以及 tie-break 错误实现。

## 验证边界

oracle 只覆盖题面规定的小规模 0/1 背包；不证明大规模性能，也不证明未覆盖的异常输入行为。`POINTS` 仅是 fixture 输出标记，行为断言才是判定依据。

## 命令

```bash
.venv/bin/python cursor_workspace/build_scripts/init_env.py --check
.venv/bin/pytest tests/test_coding_v2.py -q
.venv/bin/python cursor_workspace/build_scripts/verify_lang_sandboxes.py
```

本次变更后，Python fixture 通过升级测试；Go/TypeScript fixture 使用同一组 seed 和独立穷举 oracle 结构，须在完整语言沙箱命令中验证。
