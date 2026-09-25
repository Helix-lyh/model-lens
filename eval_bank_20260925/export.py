"""机械导出到 stdout；写入仓库时审查 diff，不改活动 bank/questions.yaml。"""

import argparse
import json

from . import VERSION
from .catalog import ITEMS, model_prompt
from .cases import coding_cases
from .runner import reference_source
from .score import golden

LEVELS = {"easy": "简单", "medium": "普通", "hard": "困难", "extreme": "超难"}


def machine_bank():
    rows = []
    for item in ITEMS:
        row = {
            "id": item.id,
            "difficulty": item.level,
            "title": item.title,
            "kind": "coding" if item.reference else "reasoning",
            "groups": [{"id": g, "points": p} for g, p in item.groups],
            "points_total": 20,
            "difficulty_status": "provisional",
        }
        if item.reference:
            row["prompts"] = {
                lang: model_prompt(item, lang)
                for lang in ("python", "go", "typescript")
            }
            row["reference_function"] = item.reference
            row["test_points"] = 20
        else:
            row["prompt"] = model_prompt(item)
            row["reference_answer"] = golden(item.id)
        rows.append(row)
    return {
        "version": VERSION,
        "status": "candidate",
        "core_items": 16,
        "expanded_instances": 32,
        "protocol": {
            "tools": False,
            "network": False,
            "primary_rounds": 1,
            "optional_repair_rounds": 3,
            "repair_factors": [1.0, 0.7, 0.45],
            "scoring": "deterministic",
            "format_points": 0,
        },
        "items": rows,
    }


def review_document():
    lines = [
        "# 题库评审稿 20260925",
        "",
        "> 本稿由 `eval_bank_20260925.catalog`、独立答案验证器和同源用例机械导出。包含答案，不能整体发给待测模型。",
        "",
        "版本：**20260925**。16 道核心题：8 道推理 + 8 道编程；每档 2+2。编程展开 Python / Go / TypeScript 后，共 32 个实例。难度为待实测校准的设计档位。",
        "",
        "评分与运行方法见 [使用说明](../eval_bank_20260925/README.md)；设计取舍与 Grok 版核对见 [设计说明](bank-design-20260925.md)。",
        "",
        "每题 20 个内容分点，`score10 = points / 2`。格式不奖励；只报告可检查的子结果，不要求模型输出私有思维链。推理字段或数组分量可以部分得分；编程每组 4 个计分检查，每检查 1 点，一个检查可能包含多个案例，必须全部正确。",
        "",
        "## 题目索引",
        "",
        "| ID | 难度 | 类型 | 题名 |",
        "|---|---|---|---|",
    ]
    for item in ITEMS:
        lines.append(
            f"| {item.id} | {LEVELS[item.level]} | {'编程' if item.reference else '推理'} | {item.title} |"
        )
    for item in ITEMS:
        lines += [
            "",
            f"## {item.id} · {LEVELS[item.level]} · {item.title}",
            "",
            "### 题面",
            "",
            item.prompt,
            "",
            "### 计分",
            "",
            "| 得分组 | 分点预算 |",
            "|---|---:|",
        ]
        lines += [f"| `{name}` | {points} |" for name, points in item.groups]
        lines += ["", f"设计意图：{item.rationale}"]
        if not item.reference:
            lines += [
                "",
                "### 参考答案",
                "",
                "```json",
                json.dumps(golden(item.id), ensure_ascii=False, indent=2),
                "```",
                "",
                "复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。",
            ]
        else:
            groups = coding_cases(item.id)
            lines += [
                "",
                "### 三语言接口",
                "",
                "- Python：`def solve(data)`。",
                "- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。",
                "- TypeScript：`export function solve(data: any): any`。",
                "",
                "三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。",
                "",
                "### Python 参考实现",
                "",
                "```python",
                reference_source(item.id).rstrip(),
                "```",
                "",
                "完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。",
                "",
                "### 评分用例目录（审核者可见）",
                "",
                "以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。",
                "",
                "| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |",
                "|---|---:|---:|---|---|",
            ]

            def preview(value):
                text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                return text if len(text) <= 190 else text[:185] + "…"

            for (name, _), group in zip(item.groups, groups):
                for point, batch in enumerate(group, 1):
                    first = batch[0]
                    a = preview(first.data).replace("|", "&#124;").replace("`", "&#96;")
                    b = (
                        preview(first.expected)
                        .replace("|", "&#124;")
                        .replace("`", "&#96;")
                    )
                    lines.append(f"| {name} | {point} | {len(batch)} | `{a}` | `{b}` |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), required=True)
    args = parser.parse_args()
    print(
        (
            json.dumps(machine_bank(), ensure_ascii=False, indent=2)
            if args.format == "json"
            else review_document()
        ),
        end="\n" if args.format == "json" else "",
    )


if __name__ == "__main__":
    main()
