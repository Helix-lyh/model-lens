"""用 .venv/bin/python -m eval_bank_20260925.cli --help 查看入口。"""

import argparse
import json
from pathlib import Path

from .catalog import BY_ID, model_prompt
from .runner import score_coding
from .score import Score, score_reasoning, summarize_repair
from .challenge_coding import coding_items, score_saved
from .engineering import ENGINEERING_SCENARIOS, score_engineering


CP_BY_ID = {item.id: item for item in coding_items()}
ALL_IDS = tuple(BY_ID) + tuple(CP_BY_ID)
ALL_IDS = ALL_IDS + tuple(ENGINEERING_SCENARIOS)


def main():
    parser = argparse.ArgumentParser(
        description="20260925 候选题库：导出题面或评分已保存的模型回答"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prompt = sub.add_parser("prompt", help="只输出发给模型的题面，不带答案或隐藏测试")
    prompt.add_argument("item_id", choices=ALL_IDS)
    prompt.add_argument("--lang", choices=("python", "go", "typescript"))
    score = sub.add_parser("score", help="评 1..3 个已保存响应；不调用模型")
    score.add_argument("item_id", choices=ALL_IDS)
    score.add_argument("responses", nargs="+", type=Path)
    score.add_argument("--lang", choices=("python", "go", "typescript"))
    args = parser.parse_args()
    if args.item_id in ENGINEERING_SCENARIOS:
        if args.command == "prompt":
            print(ENGINEERING_SCENARIOS[args.item_id]["prompt"])
            return
        if len(args.responses) != 1:
            parser.error("工程题每题只能传入 1 个响应文件；它不并入 repair/pass@k")
        print(json.dumps(score_engineering(args.responses[0].read_text(encoding="utf-8"), args.item_id), ensure_ascii=False, indent=2))
        return
    if args.item_id in CP_BY_ID:
        if args.lang not in (None, "python"):
            parser.error("CP 挑战当前只支持 --lang python")
        item = CP_BY_ID[args.item_id]
        if args.command == "prompt":
            print(item.prompt)
            return
        if not 1 <= len(args.responses) <= 3:
            parser.error("每题只能传入 1..3 个响应文件")
        def as_score(raw):
            return Score(item.id, "python", raw["status"], raw["reason_code"],
                         raw.get("points"), 20, raw.get("score10"),
                         raw.get("passed"), [], raw.get("status") == "pass")
        rounds = [as_score(score_saved(item.id, path.read_text(encoding="utf-8"), language="python")) for path in args.responses]
        summary = summarize_repair(rounds)
        print(json.dumps({"rounds": [r.to_dict() for r in rounds], "summary": summary}, ensure_ascii=False, indent=2))
        return
    item = BY_ID[args.item_id]
    if bool(item.reference) != bool(args.lang):
        parser.error("编程题必须指定 --lang；推理题不能指定 --lang")
    if args.command == "prompt":
        print(model_prompt(item, args.lang))
        return
    if not 1 <= len(args.responses) <= 3:
        parser.error("每题只能传入 1..3 个响应文件")
    rounds = []
    for path in args.responses:
        text = path.read_text(encoding="utf-8")
        result = (
            score_coding(item.id, text, args.lang)
            if item.reference
            else score_reasoning(item.id, text)
        )
        rounds.append(result)
    summary = summarize_repair(rounds)
    feedback = []
    for result in rounds:
        feedback.append(
            {
                "status": result.status,
                "reason_code": result.reason_code,
                "failed_groups": [
                    g["name"] for g in result.groups if g["points"] < g["max"]
                ],
            }
        )
    print(
        json.dumps(
            {
                "rounds": [r.to_dict() for r in rounds],
                "summary": summary,
                "feedback": feedback,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
