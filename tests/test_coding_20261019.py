"""20261019 编码题：describe() 不合格只扣分不清零；合同只列本题输出角色；CP-17 generation 是 REBUILD 输入。"""
import re

from eval_bank_20260925 import next_coding as nc
from eval_bank_20260925.coding_score import DESCRIBE_PENALTY


def _fence(src, lang="python"):
    return f"```{lang}\n{src}\n```"


def test_describe_invalid_deducts_instead_of_zero():
    src = nc.reference_source("CP-09", "python")
    full = nc.score_saved("CP-09", _fence(src))
    assert full["points"] == 20
    broken = re.sub(r"def describe\(\):\n    return .*\n", "def describe():\n    return {}\n", src, count=1)
    assert broken != src
    r = nc.score_saved("CP-09", _fence(broken))
    assert r["reason_code"] == "describe_invalid" and r["points"] == 20 - DESCRIBE_PENALTY and not r["passed"]


def test_contract_lists_only_own_output_roles():
    others = {"lookups", "edges", "generation", "snapshots", "orders"}
    for item in nc._SCHEMAS:
        text = nc.prompt(item, nc.ITEM_CODE_LANG[item] if hasattr(nc, "ITEM_CODE_LANG") else "python")
        line = next(l for l in text.splitlines() if "只出现在输出里" in l)
        listed = set(line.split("参数。", 1)[1].split(" 只出现在输出里", 1)[0].split("、"))
        assert listed == set(nc.OUTPUT_ONLY_ROLES[item]), item
        assert "不能改账" not in text and "package solution" not in text and "只属于输出" not in text
    cp17 = nc.prompt("CP-17", "typescript")
    assert "REBUILD 事件带 generation" in cp17 and "generation" not in nc.OUTPUT_ONLY_ROLES["CP-17"]
    assert "由调用方给出的代号" in cp17


def test_go_package_name_not_required():
    src = nc.reference_source("CP-13", "go")
    assert src.lstrip().startswith("package solution")
    other = src.replace("package solution", "package main", 1)
    assert nc.score_saved("CP-13", _fence(other, "go"), "go")["points"] == 20
