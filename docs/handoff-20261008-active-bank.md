# model-lens 20261008 active 题库交接

更新时间：2026-10-06

## 目标

当前目标是完成 20261008 版 30 道 active 题库并跑 DeepSeek Flash 实测：

- 编码 CP-09..CP-18，共 10 题；每题 Python、Go、TypeScript 三个入口。
- 工程 E-01..E-10，共 10 题；工程栏单独统计正分、禁项、净分。
- 推理 NX-09..NX-18，共 10 题；严格 JSON 协议和机械分组判分。
- 不恢复 CP-01..CP-08、NX-01..NX-08 等旧题到 active；用户明确允许放弃旧题兼容。
- 三栏分开报告，不合成跨栏总分；通过仍要求满点。

## 当前已落地

active manifest 已切到 30 题：

- `eval_bank_20260925/bank_manifest.py`
- `PROGRAMMING_ACTIVE = CP-09..CP-18`
- `ENGINEERING_ACTIVE = E-01..E-10`
- `REASONING_ACTIVE = NX-09..NX-18`
- `QUICK_ACTIVE = CP-09, E-07, NX-09`

插件注册入口：

- `eval_bank_20260925/bank_registry.py`
- `eval_bank_20260925/plugins.py`
- `eval_bank_20260925/bank_adapters.py`
- `cursor_workspace/build_scripts/run_eval.py`

新版实现：

- 编码：`eval_bank_20260925/next_coding.py`
- 工程：`eval_bank_20260925/engineering_next.py`
- 推理：`eval_bank_20260925/next_reasoning.py`
- 重放：`cursor_workspace/build_scripts/replay_eval_20261008.py`

活跃编码题使用标准库，不绑定第三方 runtime profile。评测核心不依赖容器。

## 已验证证据

环境检查：

```bash
.venv/bin/python cursor_workspace/build_scripts/init_env.py --check
```

当前已验证 Python 3.11、Go 1.26、Node 24、TypeScript 5.8.2 可用。

新版专项测试：

```bash
.venv/bin/pytest -q \
  tests/test_next_coding.py \
  tests/test_next_reasoning.py \
  tests/test_bank_20261008.py \
  tests/test_bank_plugin_contract.py \
  tests/test_runtime_profiles.py \
  tests/test_evaluation_contract.py
```

最近一次结果：`38 passed`。其中编码 reference 覆盖 CP-09..CP-18 × Python/Go/TypeScript，CP-09 quota reference 已达到三语言 `20/20`。

工程 reference 已单独验证：E-07..E-10 均 `20 正分 / 0 负分 / net 20`。

原始 DeepSeek Flash 响应已完整保存：

```text
out/eval-20261008-full/eval-20261008-20261006T213617-hard/deepseek-flash/requests.jsonl
```

该文件有 50 条记录，覆盖 30 题，其中编码展开为 30 个语言任务。

## 已定位的根因

此前编码 0% 不能作为模型难度结论，已经确认有多个评测链问题：

1. CP-09 题面是 quota 预占与恢复，但旧 scorer/reference 仍调用 timezone archive。
2. CP-09 oracle 的 `tuple` 与 JSON 返回的 `list` 被严格比较，三语言全部判错。
3. `run_eval_20260925.py` 先构造旧 `ALL_BY_ID`，插件只在题号不存在时加入，导致 CP-09..CP-18 仍可能使用旧题对象。
4. 部分新版题目的题面返回字段和 oracle 比较字段曾不一致；接手后必须继续逐题审计，不能只看 reference 通过。
5. 工程 E-07..E-10 曾出现 fixture 使用 `op`、题面/模型理解 `type` 的键名错位，已统一并验证 reference。

当前 runner 已加入 active registry 覆盖逻辑：active 题号会覆盖旧 `ALL_BY_ID` 对象。需要继续验证它不会破坏分栏和 prompt 选择。

## 重放方式

不要再次请求模型。使用已保存的 `requests.jsonl`：

```bash
.venv/bin/python cursor_workspace/build_scripts/replay_eval_20261008.py \
  out/eval-20261008-full/eval-20261008-20261006T213617-hard \
  --out out/eval-20261008-replay-next
```

重放脚本会从 `deepseek-flash/requests.jsonl` 读取 `content`，用当前 registry scorer 判分并写出 `results.jsonl`、`summary.json`、`summary.md`。

注意：之前生成的 `out/eval-20261008-replay-fixed` 是旧 scorer 版本的重放结果，不能直接作为最终报告；修复 CP-09 和 active runner 覆盖后必须生成新目录。

## 接手后的第一组检查

```bash
.venv/bin/python - <<'PY'
import cursor_workspace.build_scripts.run_eval_20260925 as runner
from eval_bank_20260925.bank_manifest import ACTIVE_ITEMS
from eval_bank_20260925.bank_registry import ITEMS

print('active_count', len(ACTIVE_ITEMS))
print('registry_count', len(ITEMS.items()))
print('missing', [x for x in ACTIVE_ITEMS if x not in ITEMS])
for item_id in ('CP-09', 'CP-18', 'E-07', 'E-10', 'NX-09', 'NX-18'):
    item = runner.ALL_BY_ID[item_id]
    print(item_id, type(item).__name__, runner._item_domain(item_id), len(runner._item_prompt(item, None)))
PY
```

然后运行：

```bash
.venv/bin/pytest -q tests/test_next_coding.py tests/test_next_reasoning.py \
  tests/test_bank_20261008.py tests/test_bank_plugin_contract.py \
  tests/test_runtime_profiles.py tests/test_evaluation_contract.py
```

## 当前未完成事项

1. 用修复后的 active runner 和 scorer 重放 50 条原始答卷，并确认编码分数不再被旧题对象污染。
2. 对 CP-09..CP-18 逐题核对：题面全文、fixture 输入、oracle 输出、三语言 reference 是否完全同契约；尤其检查题面没有遗漏被严格比较的字段。
3. 清理或迁移仍硬编码旧题号的测试和文档。旧题可以保留为 deprecated 历史资料，但不得进入 active runner。
4. 全量 pytest 当前仍可能有旧题兼容测试失败；不能为了旧测试恢复旧题 active。应更新测试到 20261008，或明确将旧回放测试隔离。
5. 新重放报告确认三栏分数。目标是编码、工程净分、推理分别大约 30%–50%；如果编码仍异常低，先查契约和执行链，不能直接归因模型能力。
6. 通过最终审查后，再决定是否需要真实 booster 重跑。优先使用已有原始答卷重放，避免不必要的模型调用。

## 禁止事项

- 不要把 CP-01..CP-08 或 NX-01..NX-08 加回 active。
- 不要把 `pending_review` 当作 active 题的合法判分状态。
- 不要通过放宽 scorer、忽略字段或修改目标区间来掩盖题面/oracle 错位。
- 不要把三栏合成一个总分。
- 不要删除原始 `requests.jsonl`。
- 不要提交、推送或重置工作树。
