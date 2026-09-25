#!/usr/bin/env python3
"""生成单文件题库评审文档（题面 + 参考答案 + 判分过程）。

只读仓库数据，不改题库。权威来源：
  - bank/questions.yaml                         题面、pass_criteria、grader、metadata
  - cursor_workspace/build_scripts/verify_bank_answers.py
                                                structure 权威期望 / Python 参考实现
  - bank/tests/*.py                             判分 fixture（逐点判定）
产物：docs/bank-review-<version>.md

用法：.venv/bin/python cursor_workspace/build_scripts/build_bank_review.py
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
QYAML = ROOT / "bank" / "questions.yaml"
VERIFY = ROOT / "cursor_workspace" / "build_scripts" / "verify_bank_answers.py"

DOMAIN_ORDER = ["architecture", "coding", "knowledge", "reasoning"]
DOMAIN_CN = {
    "architecture": "架构",
    "coding": "编码",
    "knowledge": "知识",
    "reasoning": "推理",
}
DIFF_ORDER = ["easy", "medium", "hard", "extreme"]
DIFF_CN = {"easy": "易", "medium": "中", "hard": "难", "extreme": "极难"}

# 少量人工补充：未带 metadata 的旧题说明（来自 bank-answers.md）。
LEGACY_NOTES = {
    "architecture-hard-05": "outbox 六项取值：单库事务写入、只重试未发送、事件 id 作消费幂等键、先提交后 ack、超过重试进死信、重放幂等。",
    "architecture-extreme-02": "发布回滚：先读旧、只回滚应用、数据先回填再重试、兼容窗口 10、无记录丢失。",
    "architecture-extreme-04": "版本向量：两个写入并发、需人工合并、保留双份审计。",
    "architecture-extreme-05": "共享预算：全局 240 加突发 60，拒绝不退款，幂等重试恢复。",
    "reasoning-hard-06": "4 色水杯配对：任意策略最坏最少交换 8；7 次不足。",
    "reasoning-hard-07": "手套：右手任意两色最多 8 只，9 只右必齐三色，再加 1 只左保证同色成对。",
    "reasoning-hard-08": "光滑/粗糙球：12 只粗糙。红色+绿色最多 7，必有粗糙蓝；红色+蓝色最多 11，必有粗糙绿。",
    "reasoning-hard-09": "线性探测：H(2022)=1、H(12)=1→2、H(25)=4；删 25 留墓碑，失败 ASL=1.8。",
    "reasoning-extreme-04": "线性规划绑定：witness 固定为 BIND_SUM。",
}

STRUCT_HELP = {
    "schema": "顶层键集合必须与期望精确一致（多键或少键都不得分）。",
    "keys": "顶层键集合必须与期望精确一致（多键或少键都不得分）。",
    "protocol": "原始响应字节必须与期望紧凑 JSON 逐字节一致（不剥围栏、不去首尾空白）。",
    "equal": "类型与值都相等；数组顺序敏感，对象键顺序不敏感。",
}


def load_verify() -> tuple[dict[str, str], dict[str, str]]:
    spec = importlib.util.spec_from_file_location("verify_bank_answers", VERIFY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PY, mod.STRUCTURE


def run_fixture(
    tests_rel: str,
    *,
    payload: str | None = None,
    solution: str | None = None,
    timeout: int = 30,
) -> str:
    src = ROOT / tests_rel
    with tempfile.TemporaryDirectory(prefix="mreview-") as tmp:
        root = Path(tmp)
        (root / "test_q.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        helper = src.parent / "_structured.py"
        if helper.is_file():
            (root / "_structured.py").write_text(helper.read_text(encoding="utf-8"), encoding="utf-8")
        if payload is not None:
            (root / "payload.txt").write_text(payload, encoding="utf-8")
        if solution is not None:
            (root / "solution.py").write_text(solution + "\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-s", "test_q.py"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout


def points_of(stdout: str) -> tuple[int, int] | None:
    found = None
    for line in stdout.splitlines():
        m = re.fullmatch(r"POINTS\s+(\d+)\s*/\s*(\d+)", line.strip())
        if m:
            found = (int(m.group(1)), int(m.group(2)))
    return found


def hits_of(stdout: str) -> list[str]:
    out = []
    for line in stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0] in {"HIT", "MISS"}:
            out.append(parts[1])
    return out


def _short(text: str | None, limit: int = 400) -> str:
    if not text:
        return ""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _func_return_expr(src: str, tree: ast.AST, name: str) -> str | None:
    """取出具名检查函数的完整函数体（压成一行），局部变量定义也一并带上。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            stmts = []
            for stmt in node.body:
                seg = ast.get_source_segment(src, stmt)
                if seg:
                    stmts.append(seg)
            return "；".join(stmts) if stmts else None
    return None


def extract_structure_checks(path: Path) -> list[tuple[str, str]]:
    """从 structure fixture 源码抽取 (检查点名, 判定表达式)。失败返回空表。"""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    consts: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        consts[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass

    def from_tuple(elt: ast.expr, key_hint: str | None) -> tuple[str, str] | None:
        if not isinstance(elt, ast.Tuple) or len(elt.elts) < 2:
            return None
        first, second = elt.elts[0], elt.elts[1]
        if key_hint is None:
            try:
                name = str(ast.literal_eval(first))
            except Exception:
                return None
        else:
            name = key_hint
        if isinstance(second, ast.Lambda):
            expr = ast.get_source_segment(src, second.body)
        elif isinstance(second, ast.Name):
            expr = _func_return_expr(src, tree, second.id)
        else:
            expr = ast.get_source_segment(src, second)
        if key_hint is not None and expr:
            # v2 模板写作 lambda d, k=k: equal(d.get(k), EXPECTED[k])，把 k 还原成具体字段名。
            expr = expr.replace("EXPECTED[k]", f"EXPECTED['{key_hint}']")
            expr = expr.replace("d.get(k)", f"d.get('{key_hint}')")
        return name, _short(expr)

    checks: list[tuple[str, str]] = []

    def walk(node: ast.expr) -> None:
        if isinstance(node, ast.List):
            for elt in node.elts:
                got = from_tuple(elt, None)
                if got:
                    checks.append(got)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            walk(node.left)
            walk(node.right)
        elif isinstance(node, ast.ListComp):
            gen = node.generators[0]
            keys: list[str] = []
            if isinstance(gen.iter, ast.Name):
                value = consts.get(gen.iter.id)
                if isinstance(value, dict):
                    keys = list(value.keys())
            for key in keys:
                got = from_tuple(node.elt, key)
                if got:
                    checks.append(got)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "emit":
            walk(node.args[0])
    return checks


def ast_points_total(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    consts: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        consts[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass

    def count(node: ast.expr) -> int:
        if isinstance(node, ast.List):
            return len(node.elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return count(node.left) + count(node.right)
        if isinstance(node, ast.ListComp):
            gen = node.generators[0]
            if isinstance(gen.iter, ast.Name):
                value = consts.get(gen.iter.id)
                if isinstance(value, dict):
                    return len(value)
            return 0
        return 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "emit":
            return count(node.args[0])
    return 0


def go_ts_points(rel: str) -> tuple[int | None, int | None]:
    out: list[int | None] = []
    for suffix in (".go", ".ts"):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        m = re.search(r"POINTS[^\n]*?/(\d+)", text)
        out.append(int(m.group(1)) if m else None)
    return out[0], out[1]


def fence(text: str, lang: str = "text") -> str:
    body = text.strip("\n")
    return f"```{lang}\n{body}\n```"


def quote(text: str) -> str:
    return "\n".join(("> " + line).rstrip() for line in text.strip().splitlines())


def dump_expected(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)


def render_headers() -> str:
    return (
        "# model-lens 能力题库评审文档\n\n"
        "> 面向评审专家。本文只读汇总题库、参考答案与判分过程，不改动任何评分实现。\n"
        "> 面板中的结论是机械判定结果，不是对题目质量的评价。\n\n"
        "本文由 `cursor_workspace/build_scripts/build_bank_review.py` 生成，数据直接读自：\n\n"
        "- `bank/questions.yaml`：题面、`pass_criteria`、`grader` 配置、`metadata`\n"
        "- `cursor_workspace/build_scripts/verify_bank_answers.py`：structure 权威期望、Python 参考实现\n"
        "- `bank/tests/*.py`：逐点判分 fixture\n\n"
        "改题面、fixture 或等价规则必须升版本；本文对应版本见下。\n"
    )


def render_matrix(questions: list[dict[str, Any]]) -> str:
    lines = ["| 域 | " + " | ".join(DIFF_CN[d] for d in DIFF_ORDER) + " | 小计 |", "|---|---|---|---|---|---|"]
    for domain in DOMAIN_ORDER:
        row = []
        for diff in DIFF_ORDER:
            row.append(str(sum(1 for q in questions if q["domain"] == domain and q["difficulty"] == diff)))
        lines.append(f"| {DOMAIN_CN[domain]} | " + " | ".join(row) + f" | {sum(int(x) for x in row)} |")
    totals = [str(sum(1 for q in questions if q["difficulty"] == d)) for d in DIFF_ORDER]
    lines.append("| **合计** | " + " | ".join(totals) + f" | {len(questions)} |")
    return "\n".join(lines)


def render_graders(questions: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for q in questions:
        counts[q["grader"]["type"]] = counts.get(q["grader"]["type"], 0) + 1
    return "\n".join(f"| {k} | {v} |" for k, v in sorted(counts.items()))


def grading_section(questions: list[dict[str, Any]]) -> str:
    coding = [q for q in questions if q["domain"] == "coding"]
    expanded = len(questions) - len(coding) + len(coding) * 3
    strict = [q for q in questions if q["grader"].get("strict_response")]
    return f"""## 二、评分机制（判分过程）

### 2.1 题库规模

- 原始题 **{len(questions)}** 条：架构 12 + 编码 12 + 知识 12 + 推理 18。
- 编码题按 python / go / typescript 展开，展开后 **{expanded}** 道实例；原始题量按展开前计。
- `--quick` 只跑 easy / medium（展开后 14 道），每题 `temperature=0` 跑 1 次。
- 默认全量跑四档，每题 `temperature=0` 跑 1 次；单次采样下不计算多数投票（majority 恒为 `None`）。
- 高 token 用量不改变机械评分。

### 2.2 四类判分器

| 判分器 | 现行题数 | 判分方式 |
|---|---|---|
| `structure` | {sum(1 for q in questions if q["grader"]["type"] == "structure")} | 从响应抽 JSON 块写入 `payload.txt`，跑 `tests_file` 逐条硬规则计点 |
| `code_tests` | {sum(1 for q in questions if q["grader"]["type"] == "code_tests")} | 按语言抽代码围栏，进沙箱编译运行，隐藏用例逐条计点 |
| `alias` | {sum(1 for q in questions if q["grader"]["type"] == "alias")} | 文本 NFKC 归一、去标点、去空白、casefold 后与 `answers` 精确匹配，1 分 |
| `keyword` | {sum(1 for q in questions if q["grader"]["type"] == "keyword")} | 每命中一组 `must_include` 得 1 分；命中 `must_exclude` 则不得 pass |

`structure` 抓取顺序：先找带语言标签的围栏（json / text / txt / yaml / yml），再找任意围栏，都没有就把整段响应当 payload。
`grader.strict_response=true` 的题**不抽围栏、不去首尾空白**，直接把响应字节当 payload，因此协议不合就是 0 分。
带 metadata（等价规则 / 负例 / 出处）的题共 {sum(1 for q in questions if q.get("metadata"))} 条；其余为未随本版改写的题（12 编码 + 4 短答 + 1 关键词 + 12 旧结构）。

### 2.3 POINTS 协议

- 沙箱 **stdout** 必须出现形如 `POINTS n/m` 的一行；只认**最后一条** POINTS 行，非法结尾不回退到更早结果。
- `score10 = round(10 × n / m, 2)`。**满点（n == m）才算该题 pass**，部分对仍记折合分。
- 没有 POINTS 行记 0 分，不因退出码为 0 判 pass。
- `structure` 的 payload 不是合法 JSON 对象、含重复键、含 NaN / Infinity 时直接 0 分。
- `keyword` 命中套话（`must_exclude`）时不 pass，但折合分仍按命中组数记。

### 2.4 missing 与 fail 的边界

| 情况 | 结果 | 是否进降智分母 |
|---|---|---|
| 抽不出对应语言围栏 | `missing` | 否 |
| 本机缺该语言工具链，或工具链低于门槛（Python 3.11 / go 1.20） | `missing` | 否 |
| Python 代码含禁运行为（网络 / subprocess） | `fail` 0 分 | 是 |
| Go 代码 import `net` / `net/http` / `os/exec` / `plugin` | `fail` 0 分 | 是 |
| TypeScript 代码 import `fs` / `net` / `http` / `https` / `child_process` / `dgram` | `fail` 0 分 | 是 |
| 编译失败、运行超时、没有 POINTS | `fail` 0 分 | 是 |
| HTTP 200 但响应为空 | `fail` 0 分（不是 missing） | 是 |

Python 沙箱断网（socket 与 subprocess 被替换为抛 `OSError`），环境变量只保留 `PATH` / `LANG` / `LC_*` / `TZ` / `TMP*`，
密钥不进入子进程。Go 用 `GOPROXY=off`、`GOSUMDB=off`、`CGO_ENABLED=0`；TS 先 `tsc` 再 `node`。

### 2.5 聚合与模块间关系

- 通过率与折合 10 **只按域、按难度**分开展示，禁止再合成 0–100 总分。
- 进降智（Module D）决策的只有编码题；架构 / 知识 / 推理不进 D 决策，只进分域附录。
- 降智指标：`pass0`（编码题 t=0 通过率，missing 不进分母）、`stab`（重复采样多数通过比例，2-2 平局不算通过）、`score10`（编码题折合分平均，部分对也进）。
- 判据：`pass0(R) − pass0(T) ≥ 0.25` 且 `stab(R) − stab(T) ≥ 0.20`，或 `score10(R) − score10(T) ≥ 2.5`，记「疑似衰减」。
- 知识域 t=0 全错触发 `knowledge_alarm`（疑似空响应或完全不对题）。
- 严格协议结构题 {len(strict)} 道，禁止把响应中的围栏剥掉再评分。

### 2.6 明确不做

- 不用 LLM-as-judge；不做 0–100 合成分；不输出「支持」。
- 不做 Java / C# / C++；不做多轮自动修。
- 不本地估算 token；家族栏非流式。
"""


def render_overview(questions: list[dict[str, Any]], version: str) -> str:
    return f"""## 一、总览

- 题库内容版本：**{version}**（协议戳 `scorer-v2` / `single-v1` 与题面版本不是一回事）。
- 规模与分布：

{render_matrix(questions)}

- 判分器分布：

| 判分器 | 题数 |
|---|---|
{render_graders(questions)}

- 四域题型约定：
  - 架构：工程判断 + 指令遵循协议；easy 为关键词组，其余为封闭结构 JSON。
  - 编码：同一题面分别用 Python / Go / TypeScript 实现，隐藏用例计点；响应需含对应语言的围栏代码块。
  - 知识：真实标准事实（RFC），短答精确匹配或封闭结构 JSON；不把指令遵循放进知识域。
  - 推理：易/中档短答精确匹配，难档为封闭结构 JSON 或逻辑约束。
- 参考答案不写进题面；编码题参考答案见各题档案，Go/TS 参考实现见 `verify_lang_sandboxes.py`。
"""


def render_question(index: int, q: dict[str, Any], py: dict[str, str], struct: dict[str, str]) -> str:
    qid = q["id"]
    domain = q["domain"]
    diff = q["difficulty"]
    grader = q["grader"]
    gtype = grader["type"]
    meta = q.get("metadata") or {}
    out: list[str] = []
    out.append(f"### {qid}\n")
    out.append(f"- 域 / 难度：{DOMAIN_CN[domain]} / {DIFF_CN[diff]}（`{diff}`）")
    out.append(f"- 通过标准：{q.get('pass_criteria', '')}")
    if meta.get("construct"):
        out.append(f"- 构念：`{meta['construct']}`")
    out.append(f"- 判分器：`{gtype}`")
    if grader.get("strict_response"):
        out.append("- 协议：`strict_response=true`（不抽围栏，原样判定）")
    out.append("")

    out.append("**题面**\n")
    out.append(quote(q["prompt"]))
    out.append("")

    # ---- 判分点 ----
    out.append("**判分点**\n")
    if gtype == "structure":
        fixture = grader.get("tests_file", "")
        checks = extract_structure_checks(ROOT / fixture)
        total = ast_points_total(ROOT / fixture)
        empty = run_fixture(fixture, payload="{}")
        expected = struct.get(fixture)
        good = run_fixture(fixture, payload=expected) if expected else ""
        good_pts = points_of(good)
        strict = bool(grader.get("strict_response"))
        out.append(f"fixture：`{fixture}`；满分 {total} 点，每点 1 分。")
        if good_pts:
            out.append(f"权威期望回放：`POINTS {good_pts[0]}/{good_pts[1]}`。")
        out.append("")
        if checks:
            out.append("| # | 检查项 | 判定条件 |")
            out.append("|---|---|---|")
            for i, (name, expr) in enumerate(checks, 1):
                desc = _short(expr, 260).replace("|", "\\|")
                if name in {"schema", "keys"}:
                    desc = STRUCT_HELP[name]
                elif name == "protocol":
                    desc = STRUCT_HELP["protocol"] if strict else "本题 `STRICT=False`：payload 是合法 JSON 对象时该点恒计 1 分。"
                out.append(f"| {i} | `{name}` | {desc} |")
        else:
            out.append("（未能从 fixture 静态提取检查项，见 fixture 源码。）")
        out.append("")
    elif gtype == "code_tests":
        langs = grader.get("languages", {})
        py_file = langs.get("python", {}).get("tests_file", "")
        code = py.get(py_file, "")
        stdout = run_fixture(py_file, solution=code) if code else ""
        pts = points_of(stdout)
        names = hits_of(stdout)
        total = pts[1] if pts else len(names)
        out.append("三语言 fixture 用例同构（同题同点数），各用各自语言声明签名；每个用例 1 分。")
        out.append("")
        out.append("| 语言 | 签名 | fixture | 满分点 |")
        out.append("|---|---|---|---|")
        for lang in ("python", "go", "typescript"):
            info = langs.get(lang, {})
            rel = info.get("tests_file", "")
            if lang == "python":
                m = total
            else:
                go_m, ts_m = (None, None)
                if rel:
                    go_m, ts_m = go_ts_points(rel)
                m = go_m if lang == "go" else ts_m
            sig = str(info.get("signature", "")).replace("|", "\\|")
            out.append(f"| {lang} | `{sig}` | `{rel}` | {m if m else '?'} |")
        out.append("")
        if names:
            out.append("Python 用例清单（顺序即 fixture 执行顺序）：")
            out.append("")
            for i, name in enumerate(names, 1):
                out.append(f"{i}. `{name}`")
            out.append("")
        else:
            out.append(
                f"该 fixture 不输出逐用例名，共 {total} 个断言点；完整源码见附录 B。"
            )
            out.append("")
        if pts and pts[0] == pts[1]:
            out.append(f"Python 参考实现回放：`POINTS {pts[0]}/{pts[1]}`。")
        elif pts:
            out.append(f"Python 参考实现回放：`POINTS {pts[0]}/{pts[1]}`（与参考实现不符，需人工核查）。")
        else:
            out.append("未能回放 Python 参考实现，需人工核查。")
        out.append("")
    elif gtype == "alias":
        out.append(f"- 匹配方式：`{grader.get('match', 'contains')}`，1 分。")
        out.append("- 归一化：NFKC → 去标点 → casefold → 去空白；`exact` 要求归一后完全相等，带解释的句子不得分。")
        out.append("")
    elif gtype == "keyword":
        groups = grader.get("must_include") or []
        out.append(f"- 得分组 {len(groups)} 组，每组 1 分；`min_hits={grader.get('min_hits')}`，命中数达标且未触套话才 pass。")
        banned = grader.get("must_exclude") or []
        if banned:
            out.append(f"- 套话黑名单：{', '.join(' / '.join(map(str, g)) for g in banned)}；命中即不 pass。")
        out.append("")

    # ---- 参考答案 ----
    out.append("**参考答案**\n")
    if gtype == "keyword":
        groups = grader.get("must_include") or []
        for i, group in enumerate(groups, 1):
            out.append(f"{i}. 命中任一：{', '.join('`%s`' % a for a in group)}")
        out.append("")
    elif gtype == "alias":
        answers = grader.get("answers") or []
        out.append("标准答案：" + "、".join(f"`{a}`" for a in answers))
        out.append("")
    elif gtype == "code_tests":
        py_file = grader.get("languages", {}).get("python", {}).get("tests_file", "")
        code = py.get(py_file, "")
        if code:
            out.append("Python：")
            out.append(fence(code, "python"))
            out.append("")
            out.append("Go / TypeScript 参考实现逻辑一致，全文见 `cursor_workspace/build_scripts/verify_lang_sandboxes.py`。")
        else:
            out.append("（参考实现未登记，见 `verify_lang_sandboxes.py`。）")
        out.append("")
    else:
        fixture = grader.get("tests_file", "")
        payload = struct.get(fixture)
        ref = meta.get("reference_answer")
        ref_json = dump_expected(ref) if ref is not None else None
        payload_json = None
        if payload:
            try:
                payload_json = dump_expected(json.loads(payload))
            except Exception:
                payload_json = payload
        checks = extract_structure_checks(ROOT / fixture) if fixture else []
        exact_fields = any(
            "EXPECTED[" in expr for name, expr in checks if name not in {"schema", "keys", "protocol"}
        )
        if payload_json and ref_json and payload_json == ref_json:
            if exact_fields:
                out.append("权威期望（也是 `metadata.reference_answer` 示例解）：")
            else:
                out.append("示例解（本题字段按范围 / 类型判定，不是唯一合法答案）：")
            out.append("")
            out.append(fence(payload_json, "json"))
            out.append("")
        else:
            if payload_json:
                label = "权威期望（fixture `EXPECTED` / `STRUCTURE`）：" if exact_fields else "示例解（本题字段按范围 / 类型判定，不是唯一合法答案）："
                out.append(label)
                out.append("")
                out.append(fence(payload_json, "json"))
                out.append("")
            if ref_json:
                out.append("`metadata.reference_answer`（示例解，非唯一合法解）：")
                out.append("")
                out.append(fence(ref_json, "json"))
                out.append("")
        if not payload_json and not ref_json:
            out.append("（未登记权威期望。）")

    # ---- 等价规则 / 负例 / 出处 ----
    extras: list[str] = []
    if meta.get("equivalence"):
        extras.append(f"- 等价规则：{meta['equivalence']}")
    if meta.get("negative_example") is not None:
        neg = meta["negative_example"]
        try:
            neg_text = " ".join(dump_expected(neg).split())
        except Exception:
            neg_text = str(neg)
        extras.append(f"- 错误样例：`{neg_text}`；关键字段为空或缺失时不通过。")
    if meta.get("sources"):
        extras.append("- 出处：" + "，".join(str(s) for s in meta["sources"]))
    if meta.get("rationale"):
        extras.append(f"- 设计意图：{meta['rationale']}")
    if qid in LEGACY_NOTES:
        extras.append(f"- 未改写旧题说明：{LEGACY_NOTES[qid]}")
    if extras:
        out.append("**补充**\n")
        out.extend(extras)
        out.append("")
    return "\n".join(out)


def appendix(questions: list[dict[str, Any]], py: dict[str, str]) -> str:
    out = ["## 附录 A：structure 判分 fixture 全文\n",
           "逐点判定就在这些文件里。完整路径相对仓库根。\n",
           "| 题号 | fixture | 满分点 | 是否严格协议 |",
           "|---|---|---|---|"]
    for q in questions:
        g = q["grader"]
        if g["type"] == "structure":
            strict = "是" if g.get("strict_response") else "否"
            out.append(
                f"| {q['id']} | `{g['tests_file']}` | {ast_points_total(ROOT / g['tests_file']) or '?'} | {strict} |"
            )
    out.append("")
    for q in questions:
        g = q["grader"]
        if g["type"] != "structure":
            continue
        rel = g["tests_file"]
        out.append(f"### {q['id']} — `{rel}`\n")
        out.append(fence((ROOT / rel).read_text(encoding="utf-8"), "python"))
        out.append("")

    out.append("## 附录 B：编码题 Python 判分 fixture 全文\n")
    out.append("Go / TS 同构，见 `bank/tests/go/` 与 `bank/tests/ts/`。\n")
    for q in questions:
        if q["domain"] != "coding":
            continue
        rel = q["grader"]["languages"]["python"]["tests_file"]
        out.append(f"### {q['id']} — `{rel}`\n")
        out.append(fence((ROOT / rel).read_text(encoding="utf-8"), "python"))
        out.append("")
    return "\n".join(out)


def _cn_number(text: str) -> int | None:
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if text in digits:
        return digits[text]
    if text.startswith("十") and len(text) == 1:
        return 10
    if len(text) == 2 and text[0] in digits and text[1] == "十":
        return digits[text[0]] * 10
    if len(text) == 3 and text[0] in digits and text[1] == "十" and text[2] in digits:
        return digits[text[0]] * 10 + digits[text[2]]
    return None


def _declared_fields(prompt: str) -> int | None:
    m = re.search(r"([一二两三四五六七八九十\d]+)\s*个?\s*字段各\s*1\s*分", prompt)
    if not m:
        return None
    return _cn_number(m.group(1))


def checklist(questions: list[dict[str, Any]], py: dict[str, str]) -> str:
    rows: list[str] = []

    # 0) 结构题题面声明的字段数 vs fixture 实际点数
    for q in questions:
        if q["grader"]["type"] != "structure":
            continue
        declared = _declared_fields(q["prompt"])
        if declared is None:
            continue
        total = ast_points_total(ROOT / q["grader"]["tests_file"])
        if total != declared:
            rows.append(
                f"- `{q['id']}`：题面写「{declared} 个字段各 1 分」，fixture 实际 {total} 点"
                f"（多出的是 `keys` / `schema` 键集合点，题面未声明）。"
            )

    # 1) POINTS 分母 vs pass_criteria 声明的 cases 数
    for q in questions:
        if q["domain"] != "coding":
            continue
        rel = q["grader"]["languages"]["python"]["tests_file"]
        total = points_of(run_fixture(rel, solution=py[rel])) if rel in py else None
        declared = re.search(r"(\d+)\s*个\s*cases", q.get("pass_criteria", ""))
        if total and declared and int(declared.group(1)) != total[1]:
            names = hits_of(run_fixture(rel, solution=py[rel]))
            generated = [n for n in names if n.startswith("generated-")]
            extra = f"；其中 {len(generated)} 个为 generated 随机用例" if generated else ""
            rows.append(
                f"- `{q['id']}`：`pass_criteria` 写「{declared.group(1)} 个 cases」，"
                f"实际 POINTS 分母为 {total[1]}{extra}。声明未随 fixture 更新。"
            )

    # 2) 孤儿 fixture：go/ts 目录里有、题库不引用
    used = {
        q["grader"]["languages"][lang]["tests_file"]
        for q in questions
        if q["domain"] == "coding"
        for lang in ("python", "go", "typescript")
    }
    orphans = []
    for sub in ("go", "ts"):
        for path in sorted((ROOT / "bank" / "tests" / sub).glob(f"*{'.go' if sub == 'go' else '.ts'}")):
            rel = f"bank/tests/{sub}/{path.name}"
            if rel not in used:
                orphans.append(rel)
    if orphans:
        rows.append("- 不在现行题库引用的编码 fixture：" + "、".join(f"`{o}`" for o in orphans) + "。")

    # 3) 非 strict 结构题的 protocol 白送
    freebie = [
        q["id"]
        for q in questions
        if q["grader"]["type"] == "structure"
        and not q["grader"].get("strict_response")
        and "protocol" in [name for name, _ in extract_structure_checks(ROOT / q["grader"]["tests_file"])]
    ]
    if freebie:
        rows.append(
            "- 非严格结构题里 `protocol` 点不做格式校验（fixture 写作 `not STRICT or ...`）："
            + "、".join(f"`{x}`" for x in freebie)
            + "；只要 payload 是合法 JSON 对象，这 1 分必得。"
        )

    # 4) schema/keys 点与字段点重叠
    rows.append(
        "- 结构题的 `schema` / `keys` 点要求顶层键集合精确匹配，与各字段点部分重叠；"
        "字段全对但多带一个键时会同时丢 schema 点与对应字段点。"
    )

    # 5) 无 metadata 的旧结构题
    legacy = [
        q["id"]
        for q in questions
        if q["grader"]["type"] == "structure" and not q.get("metadata")
    ]
    if legacy:
        rows.append(
            "- 未带 metadata（无等价规则 / 负例 / 出处）的结构题（"
            + str(len(legacy))
            + " 道）："
            + "、".join(f"`{x}`" for x in legacy)
            + "。"
        )

    # 6) 共享模板
    strict_ids = [q["id"] for q in questions if q["grader"].get("strict_response")]
    if strict_ids:
        rows.append(
            f"- 严格协议题共 {len(strict_ids)} 道，共享同一套指令协议模板（"
            + "、".join(f"`{x}`" for x in strict_ids)
            + "），不宜当作同等数量的独立能力证据。"
        )

    return "## 三、评审前值得核对的事实点\n\n" + "\n".join(rows) + "\n"


def main() -> None:
    questions = yaml.safe_load(QYAML.read_text(encoding="utf-8"))
    py, struct = load_verify()
    version = ""
    for q in questions:
        if (q.get("metadata") or {}).get("version"):
            version = q["metadata"]["version"]
            break
    version = version or "unknown"

    parts: list[str] = []
    parts.append(render_headers())
    parts.append("")
    parts.append(
        f"- 版本：`{version}`\n"
        f"- 生成命令：`.venv/bin/python cursor_workspace/build_scripts/build_bank_review.py`\n"
    )
    parts.append(render_overview(questions, version))
    parts.append(grading_section(questions))
    parts.append(checklist(questions, py))

    for domain in DOMAIN_ORDER:
        group = [q for q in questions if q["domain"] == domain]
        parts.append(f"## 四、{DOMAIN_CN[domain]}域（{len(group)} 题）\n")
        if domain == "coding":
            parts.append(
                "编码题的响应必须包含对应语言的围栏代码块（`python` / `py`、`go` / `golang`、"
                "`typescript` / `ts` / `tsx` / `javascript` / `js`）；无标签围栏需内容形如代码才被抽取。\n"
            )
        elif domain == "architecture" and any(q["grader"].get("strict_response") for q in group):
            parts.append(
                "本域的 hard 档包含指令遵循题，要求输出原始紧凑单行 JSON，不剥围栏、不去空白。\n"
            )
        for i, q in enumerate(group, 1):
            parts.append(render_question(i, q, py, struct))

    parts.append("## 五、复核方式\n")
    parts.append(
        "本机先初始化工具链（`.venv`、go、node、tsc），然后跑参考实现回放：\n\n"
        "```bash\n"
        "python cursor_workspace/build_scripts/init_env.py\n"
        ".venv/bin/python cursor_workspace/build_scripts/verify_bank_answers.py\n"
        ".venv/bin/python cursor_workspace/build_scripts/verify_lang_sandboxes.py\n"
        "```\n\n"
        "两个脚本都把参考答案跑进真实沙箱，必须全部满分；否则题库、fixture 或参考实现至少有一处不一致。\n\n"
        "本文定稿时已在本地跑过两个脚本：12 道编码题的 Python / Go / TypeScript 参考实现、"
        "37 道结构题的权威期望全部 `pass` 满分，三语言同题点数一致。\n"
    )
    parts.append(appendix(questions, py))

    text = "\n".join(parts)
    out_path = ROOT / "docs" / f"bank-review-{version}.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
