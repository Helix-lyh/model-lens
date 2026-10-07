# 题库与运行命名规范

题库身份、版本、生命周期和运行实例是四个不同概念，不能塞进一个字符串。

| 对象 | 格式 | 示例 | 说明 |
| --- | --- | --- | --- |
| `bank_id` | `<业务域>-<能力>` | `business-coding` | 稳定主键；小写 ASCII kebab-case；不带日期、版本、模型名 |
| `bank_version` | `<major>[.<minor>]` | `9`, `3.3` | 题面、隐藏夹具或评分语义变化就升版本 |
| `status` | `active` / `quick` / `deprecated` | `active` | 生命周期，不表示难度、质量或是否进入 F/I/D |
| `item_id` | `<BANK_PREFIX>-<NN>` | `CP-04`, `NX-07` | 题面与历史结果的稳定定位；版本变化不重用旧题号 |
| `run_id` | `<bank_id>-<version>-<UTC timestamp>-<random>` | `business-coding-9-20261006T121500Z-a1b2` | 一次执行实例，不能代替 sample 身份 |
| `sample` | 非负整数 | `0`, `1` | 同一 `run_id` 内的独立模型采样序号 |

旧目录名（如 `eval-20260925-*`、`eval-nx-20261006*`）和旧 manifest ID 保留为兼容输入；新代码、`meta.json` 和报告应使用 canonical `bank_id` 与 `bank_version`，并在 `legacy_id` 中保留旧值（如确有需要）。

## 题库分类

- `business-*`：有明确业务流程、角色、状态或工程责任，才可申请 `active`。
- `reasoning-calibration`：用于机制校准和快速 smoke，不能自动并入业务能力主测。
- `legacy-*`：只用于历史回放，不能成为新实验默认集合。

`active` 只表示已通过真实性门禁并有明确维护者；低通过率、题面复杂度或模型排名变化都不能单独触发状态升级。
