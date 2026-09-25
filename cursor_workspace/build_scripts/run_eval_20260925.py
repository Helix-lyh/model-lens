#!/usr/bin/env python3
"""按渠道批量跑 20260925 候选题库；默认单样本 pass@1，可选独立采样 pass@k。

渠道密钥只读环境变量；grok 走本机 Grok CLI 的 OIDC 会话（GROK_CLI_TOKEN，
缺省时从 ~/.grok/auth.json 取，只在本进程内 setenv，不落盘、不打印）。

用法：
  .venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick
  .venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase hard
  .venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --models deepseek-flash,mimo-v2.6-flash
  # DeepSeek 官方 key：一次跑出 pass@1 与 pass@2
  .venv/bin/python cursor_workspace/build_scripts/run_eval_20260925.py --phase quick --models deepseek-chat --samples 2 --pass-at 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.catalog import BY_ID, model_prompt  # noqa: E402
from eval_bank_20260925.challenge import salt_prompt, salted_prompt_hash  # noqa: E402
from eval_bank_20260925.challenge_coding import coding_items, score_saved  # noqa: E402
from eval_bank_20260925.runner import score_coding  # noqa: E402
from eval_bank_20260925.engineering import ENGINEERING_SCENARIOS, aggregate_engineering, score_engineering  # noqa: E402
from eval_bank_20260925.score import score_reasoning  # noqa: E402
from src.client import ChatClient, JsonlRecorder  # noqa: E402
from src.types import Endpoint  # noqa: E402

GROK_AUTH = Path.home() / ".grok" / "auth.json"
GROK_PROXY_HEADERS = {
    "X-XAI-Token-Auth": "xai-grok-cli",
    "x-grok-client-version": "1.0.41",
}
QUICK_LEVELS = {"easy", "medium"}
HARD_LEVELS = {"hard", "extreme"}
CP_BY_ID = {item.id: item for item in coding_items()}


@dataclass(frozen=True)
class EngineeringItem:
    id: str
    level: str
    title: str
    prompt: str
    reference: str | None = None
    kind: str = "engineering"


ENGINEERING_BY_ID = {
    item_id: EngineeringItem(item_id, "engineering", spec["title"], spec["prompt"])
    for item_id, spec in ENGINEERING_SCENARIOS.items()
}
ALL_BY_ID = {**BY_ID, **CP_BY_ID, **ENGINEERING_BY_ID}


def _unique(values: list[str]) -> list[str]:
    """稳定去重，避免重复参数扩大请求数和分母。"""
    return list(dict.fromkeys(value for value in values if value))


def _is_coding(item: Any) -> bool:
    return bool(getattr(item, "reference", None)) or getattr(item, "kind", None) == "coding"


def _item_prompt(item: Any, lang: str | None) -> str:
    if item.id in CP_BY_ID:
        return item.prompt
    if item.id in ENGINEERING_BY_ID:
        return item.prompt
    return model_prompt(item, lang)


def _item_level(item_id: str) -> str | None:
    item = ALL_BY_ID.get(item_id)
    return getattr(item, "level", None)


def _item_domain(item_id: str) -> str | None:
    item = ALL_BY_ID.get(item_id)
    if item is None:
        return None
    if getattr(item, "kind", None) == "engineering":
        return "engineering"
    return "coding" if _is_coding(item) else "reasoning"


def _finish_reason(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    direct = raw.get("finish_reason")
    if isinstance(direct, str):
        return direct
    choices = raw.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        value = choices[0].get("finish_reason")
        return value if isinstance(value, str) else None
    return None


def _error_row(ch: Channel, item: Any, lang: str | None, reason: str, detail: str, *, sample: int = 0, run_id: str | None = None) -> dict[str, Any]:
    return {
        "channel": ch.name,
        "model": ch.model,
        "item": item.id,
        "lang": lang,
        "sample": sample,
        "run_id": run_id,
        "status": "error",
        "reason_code": reason,
        "passed": None,
        "points": None,
        "score10": None,
        "detail": detail,
        "response_model": None,
        "usage": None,
        "latency_ms": None,
        "finish_reason": None,
        "truncated": False,
    }


@dataclass(frozen=True)
class Channel:
    name: str
    model: str
    base_url: str
    api_key_env: str
    max_tokens: int
    extra_headers: dict[str, str]


def _booster_base() -> str:
    base = os.environ.get("BOOSTER_BASE_URL", "http://ai.booster.woa.com").rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def _deepseek_base() -> str:
    """DeepSeek 官方校准端点；只读 origin 环境变量，密钥走 DEEPSEEK_API_KEY。"""
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def channels(*, grok_base: str, grok_key_env: str, grok_cli_proxy: bool) -> dict[str, Channel]:
    booster = _booster_base()
    if grok_cli_proxy:
        base = "https://cli-chat-proxy.grok.com/v1"
        headers = {**GROK_PROXY_HEADERS}
        key_env = "GROK_CLI_TOKEN"
    else:
        base = grok_base.rstrip("/")
        headers = {}
        key_env = grok_key_env
    out = [
        Channel("deepseek-flash", "deepseek-flash", booster, "BOOSTER_API_KEY", 384000, {}),
        Channel("deepseek-chat", "deepseek-chat", _deepseek_base(), "DEEPSEEK_API_KEY", 384000, {}),
        Channel("mimo-v2.6-flash", "mimo-v2.6-flash", booster, "BOOSTER_API_KEY", 131072, {}),
        Channel("grok-4.6", "grok-4.6", base, key_env, 65536,
                {**headers, "x-grok-model-override": "grok-4.6"} if grok_cli_proxy else dict(headers)),
        Channel("grok-4.7", "grok-4.7", base, key_env, 65536,
                {**headers, "x-grok-model-override": "grok-4.7"} if grok_cli_proxy else dict(headers)),
    ]
    return {c.name: c for c in out}


def seed_grok_token() -> None:
    if os.environ.get("GROK_CLI_TOKEN", "").strip():
        return
    if not GROK_AUTH.is_file():
        return
    data = json.loads(GROK_AUTH.read_text(encoding="utf-8"))
    for key, value in data.items():
        if "x.ai" in key and isinstance(value, dict) and value.get("key"):
            os.environ["GROK_CLI_TOKEN"] = value["key"]
            return


def endpoint(ch: Channel) -> Endpoint:
    return Endpoint(
        base_url=ch.base_url,
        api_key_env=ch.api_key_env,
        model=ch.model,
        api="openai-completions",
        extra_headers=dict(ch.extra_headers),
    )


def pick_items(phase: str, only: list[str] | None = None) -> list[Any]:
    if only:
        only = _unique(only)
        missing = [i for i in only if i not in ALL_BY_ID]
        if missing:
            raise SystemExit(f"未知题号 {missing}")
        return [ALL_BY_ID[i] for i in only]
    levels = QUICK_LEVELS if phase == "quick" else HARD_LEVELS
    items = [it for it in ALL_BY_ID.values() if it.level in levels]
    items.sort(key=lambda it: it.id)
    return items


def jobs_for(items: list[Any], langs: list[str], samples: int = 1) -> list[tuple[Any, str | None]]:
    if samples < 1:
        raise ValueError("samples must be >= 1")
    langs = _unique(langs)
    jobs: list[tuple[Any, str | None]] = []
    for item in items:
        if _is_coding(item):
            # CP 校准题目前只公开 Python 入口；catalog 的 P-* 题仍按请求语言展开。
            if item.id in CP_BY_ID:
                if "python" in langs:
                    jobs.append((item, "python"))
                continue
            for lang in langs:
                jobs.append((item, lang))
        else:
            jobs.append((item, None))
    return jobs * samples


def run_one(client: ChatClient, ch: Channel, item: Any, lang: str | None, out_dir: Path,
            timeout_s: float, sample: int = 0) -> dict[str, Any]:
    item_id = item.id
    base_prompt = _item_prompt(item, lang)
    salt = secrets.token_urlsafe(18)
    prompt = salt_prompt(base_prompt, salt)
    tag = f"{item_id}-{lang}" if lang else item_id
    if sample:
        tag += f"-s{sample}"
    record = client.complete(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=ch.max_tokens,
        extra={"reasoning_effort": "high"},
        kind=f"eval20260925:{tag}",
        stream=False,
    )
    text = record.content or ""
    stem = out_dir / ch.name / tag
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".txt").write_text(text, encoding="utf-8")
    if record.status_code != 200 or record.error:
        return {
            "channel": ch.name, "model": ch.model, "item": item_id, "lang": lang, "sample": sample, "run_id": out_dir.name,
            "status": "error", "reason_code": "request_error", "passed": None,
            "points": None, "score10": None, "detail": record.error,
            "response_model": None, "usage": record.usage, "latency_ms": record.latency_ms,
            "finish_reason": _finish_reason(record.raw), "truncated": False,
            "salt": salt, "base_prompt_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
            "prompt_sha256": salted_prompt_hash(prompt),
        }
    response_model = None
    if isinstance(record.raw, dict):
        response_model = record.raw.get("model")
    finish_reason = _finish_reason(record.raw)
    elapsed_timeout = record.latency_ms is not None and record.latency_ms > timeout_s * 1000
    if elapsed_timeout:
        verdict = {"status": "error", "reason_code": "timeout", "passed": None, "points": None, "score10": None}
    elif finish_reason == "length":
        verdict = {"status": "error", "reason_code": "response_truncated", "passed": None, "points": None, "score10": None}
    elif item.id in CP_BY_ID:
        verdict = score_saved(item_id, text, language=lang or "python")
    elif getattr(item, "kind", None) == "engineering":
        verdict = score_engineering(text, item_id)
    elif getattr(item, "reference", None):
        verdict = score_coding(item_id, text, lang)
    else:
        verdict = score_reasoning(item_id, text)
    if isinstance(verdict, dict):
        status = verdict.get("status")
        reason_code = verdict.get("reason_code")
        passed = verdict.get("passed")
        points = verdict.get("points")
        score10 = verdict.get("score10")
        detail = verdict.get("detail")
        obligations = verdict.get("obligations")
        risk_debt = verdict.get("risk_debt")
    else:
        status = verdict.status
        reason_code = verdict.reason_code
        passed = verdict.passed
        points = verdict.points
        score10 = verdict.score10
        detail = None
        obligations = None
        risk_debt = None
    return {
        "channel": ch.name, "model": ch.model, "item": item_id, "lang": lang, "sample": sample, "run_id": out_dir.name,
        "status": status, "reason_code": reason_code,
        "passed": passed, "points": points, "score10": score10,
        "detail": detail, "response_model": response_model,
        "obligations": obligations, "risk_debt": risk_debt,
        "usage": record.usage, "latency_ms": record.latency_ms,
        "finish_reason": finish_reason, "truncated": finish_reason == "length",
        "salt": salt, "base_prompt_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
        "prompt_sha256": salted_prompt_hash(prompt),
    }


def run_channel(ch: Channel, jobs: list[tuple[Any, str | None]], out_dir: Path, concurrency: int,
                *, timeout_s: float = 900.0, max_retries: int = 1,
                on_row: Any = None) -> list[dict[str, Any]]:
    seed_grok_token()
    recorder = JsonlRecorder(out_dir / ch.name / "requests.jsonl")
    client = ChatClient(endpoint(ch), recorder, timeout_s=timeout_s, max_retries=max_retries)
    results: list[dict[str, Any]] = []
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        sample_seen: dict[tuple[str, str | None], int] = defaultdict(int)
        for item, lang in jobs:
            key = (item.id, lang)
            sample = sample_seen[key]
            sample_seen[key] += 1
            future = pool.submit(run_one, client, ch, item, lang, out_dir, timeout_s, sample)
            futures[future] = (item, lang, sample)
        for fut in as_completed(futures):
            item, lang, sample = futures[fut]
            try:
                row = fut.result()
            except Exception as exc:  # noqa: BLE001
                row = _error_row(ch, item, lang, "runner_error", repr(exc), sample=sample, run_id=out_dir.name)
            with lock:
                results.append(row)
            if on_row is not None:
                on_row(row)
            print(f"  [{ch.name}] {row.get('item')} {row.get('lang') or ''} -> {row.get('status')} "
                  f"{row.get('points')}/{20 if row.get('points') is not None else '-'}", flush=True)
    return results


def _pass_at_k(rows: list[dict[str, Any]], k: int) -> tuple[float | None, int, int]:
    """按(题目,语言)先算独立采样 pass@k，再对题目等权平均。"""
    if k < 1:
        raise ValueError("pass_at_k requires k >= 1")
    grouped: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("item"):
            grouped[(row["item"], row.get("lang"))].append(row)
    estimates: list[float] = []
    eligible = 0
    for samples in grouped.values():
        judged = [r for r in samples if r.get("status") in {"pass", "fail"}]
        n = len(judged)
        if n < k:
            continue
        c = sum(r.get("passed") is True for r in judged)
        if c == 0:
            estimate = 0.0
        elif c == n or n - c < k:
            estimate = 1.0
        else:
            estimate = 1.0 - math.comb(n - c, k) / math.comb(n, k)
        estimates.append(estimate)
        eligible += 1
    return (round(sum(estimates) / len(estimates), 4) if estimates else None, eligible, len(grouped))


def summarize(rows: list[dict[str, Any]], model_names: list[str], pass_k: int = 1) -> dict[str, Any]:
    def bucket(rows_filtered: list[dict[str, Any]]) -> dict[str, Any]:
        judged = [r for r in rows_filtered if r["status"] in {"pass", "fail"}]
        passed = [r for r in judged if r.get("passed") is True]
        missing = [r for r in rows_filtered if r["status"] == "missing"]
        errors = [r for r in rows_filtered if r["status"] == "error"]
        pending = [r for r in rows_filtered if r["status"] == "pending_review"]
        numeric = [r for r in judged if r.get("score10") is not None]
        mean = None
        if numeric:
            mean = round(sum(float(r["score10"]) for r in numeric) / len(numeric), 4)
        pass1, _, _ = _pass_at_k(rows_filtered, 1)
        passk, eligible, item_count = _pass_at_k(rows_filtered, pass_k)
        result = {
            "judged": len(judged), "passed": len(passed),
            "pass_at_1": pass1,
            "pass_at_k": passk,
            "pass_at_k_eligible": eligible,
            "pass_at_k_items": item_count,
            "pass_k": pass_k,
            "mean_score10": mean, "missing": len(missing), "errors": len(errors),
            "pending_review": len(pending),
        }
        engineering_rows = [r for r in judged if isinstance(r.get("obligations"), dict)]
        if engineering_rows:
            covered = sum(r["obligations"].get("covered", 0) for r in engineering_rows)
            total = sum(r["obligations"].get("total", 0) for r in engineering_rows)
            risk = {key: sum((r.get("risk_debt") or {}).get(key, 0) for r in engineering_rows)
                    for key in ("critical", "high", "medium")}
            result["engineering_obligations"] = {"covered": covered, "total": total,
                                                   "coverage": round(covered / total, 4) if total else None}
            result["engineering_risk_debt"] = {**risk, "weighted_points": risk["critical"] * 6 + risk["high"] * 3 + risk["medium"]}
            result["engineering_strict_pass"] = sum(r.get("passed") is True for r in engineering_rows)
            result["engineering_total"] = aggregate_engineering([
                {"positive_points": r.get("obligations", {}).get("covered", 0),
                 "negative_points": sum((r.get("risk_debt") or {}).get(k, 0) for k in ("critical", "high", "medium")),
                 "obligations": r.get("obligations"), "passed": r.get("passed")}
                for r in engineering_rows
            ])
        return result

    by_model: dict[str, Any] = {}
    for name in model_names:
        mine = [r for r in rows if r["channel"] == name]
        entry: dict[str, Any] = {"overall": bucket(mine)}
        for level in ("easy", "medium", "hard", "extreme"):
            sub = [r for r in mine if _item_level(r.get("item")) == level]
            if sub:
                entry[level] = bucket(sub)
        for domain in ("reasoning", "coding", "engineering"):
            sub = [r for r in mine if _item_domain(r.get("item")) == domain]
            if sub:
                entry[domain] = bucket(sub)
        by_model[name] = entry
    return by_model


def write_summary(out_dir: Path, summary: dict[str, Any], rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    (out_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    payload = {"meta": meta, "summary": summary}
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# eval 20260925 · phase={meta['phase']} · langs={','.join(meta['langs'])} · effort=high",
        "",
        f"并发：每渠道 {meta['concurrency']}；独立采样 {meta.get('samples', 1)} 次，报告 pass@{meta.get('pass_k', 1)}；不做修复。",
        "",
        "| channel | judged | pass@1 | pass@k | pass | mean score10 | missing | errors | pending |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, entry in summary.items():
        o = entry["overall"]
        lines.append(
            f"| {name} | {o['judged']} | {o['pass_at_1']} | {o['pass_at_k']} | {o['passed']} | {o['mean_score10']} | {o['missing']} | {o['errors']} | {o['pending_review']} |"
        )
    lines += ["", "## 分难度 / 分域", "", "| channel | 分组 | judged | pass@1 | pass | mean |", "| --- | --- | --- | --- | --- | --- |"]
    for name, entry in summary.items():
        for key in ("easy", "medium", "hard", "extreme", "reasoning", "coding", "engineering"):
            if key in entry:
                b = entry[key]
                lines.append(f"| {name} | {key} | {b['judged']} | {b['pass_at_1']} | {b['passed']} | {b['mean_score10']} |")
    lines += ["", "## 逐题", "", "| channel | item | lang | status | points | reason | resp model |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda x: (x.get("channel") or "", x.get("item") or "", x.get("lang") or "")):
        lines.append(
            f"| {r['channel']} | {r.get('item')} | {r.get('lang') or '-'} | {r['status']} | "
            f"{r.get('points')} | {r.get('reason_code')} | {r.get('response_model') or '-'} |"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("quick", "hard"), required=True)
    parser.add_argument("--langs", default="python", help="编程题语言，逗号分隔：python,go,typescript")
    parser.add_argument("--models", default="", help="只跑指定渠道，逗号分隔；默认全部")
    parser.add_argument("--items", default="", help="只跑指定题号，逗号分隔；默认按 phase")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--samples", type=int, default=1, help="每道题独立采样次数；默认 1")
    parser.add_argument("--pass-at", type=int, default=1, dest="pass_k", help="报告 pass@k；必须不大于 --samples")
    parser.add_argument("--timeout", type=float, default=900.0, help="单次请求超时秒，默认 900")
    parser.add_argument("--retries", type=int, default=1, help="超时/网络错误重试次数，默认 1")
    parser.add_argument("--out", default="out")
    parser.add_argument("--grok-base", default=os.environ.get("AI_LIUYUNHAI_SPACE_BASE_URL", "https://ai.liuyunhai.space"))
    parser.add_argument("--grok-key-env", default="AI_LIUYUNHAI_SPACE_API_KEY")
    parser.add_argument("--grok-cli-proxy", action="store_true",
                        help="grok 改走本机 Grok CLI OIDC 代理（默认走 --grok-base）")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency 必须 >= 1")
    if args.timeout <= 0:
        parser.error("--timeout 必须 > 0")
    if args.retries < 0:
        parser.error("--retries 必须 >= 0")
    if args.samples < 1:
        parser.error("--samples 必须 >= 1")
    if args.pass_k < 1 or args.pass_k > args.samples:
        parser.error("--pass-at 必须满足 1 <= k <= --samples")

    all_channels = channels(
        grok_base=args.grok_base, grok_key_env=args.grok_key_env,
        grok_cli_proxy=args.grok_cli_proxy,
    )
    names = _unique(args.models.split(",") if args.models else list(all_channels))
    unknown = [n for n in names if n not in all_channels]
    if unknown:
        parser.error(f"未知渠道 {unknown}，可选 {list(all_channels)}")
    langs = _unique(args.langs.split(","))

    items = pick_items(args.phase, _unique(args.items.split(",")) or None)
    jobs = jobs_for(items, langs, args.samples)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = Path(args.out) / f"eval-20260925-{stamp}-{args.phase}"
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_grok_token()
    meta = {"phase": args.phase, "langs": langs, "models": names,
            "concurrency": args.concurrency, "timeout_s": args.timeout, "retries": args.retries,
            "samples": args.samples, "pass_k": args.pass_k,
            "items": [it.id for it in items],
            "salt_mode": "per_request_random_urlsafe_18",
            "jobs_per_channel": len(jobs), "started_at": stamp,
            "routes": {n: {"base_url": all_channels[n].base_url,
                           "model": all_channels[n].model,
                           "api_key_env": all_channels[n].api_key_env} for n in names}}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"out={out_dir} channels={names} items={len(items)} jobs/channel={len(jobs)} concurrency={args.concurrency}", flush=True)

    seed_grok_token()
    rows: list[dict[str, Any]] = []
    threads = []
    results: dict[str, list[dict[str, Any]]] = {}
    worker_errors: dict[str, str] = {}
    lock = threading.Lock()
    persist_lock = threading.Lock()

    def append_row(row: dict[str, Any]) -> None:
        """题目完成即落盘，进程被中断时保留已完成结果。"""
        with persist_lock:
            with (out_dir / "results.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())

    def worker(name: str) -> None:
        ch = all_channels[name]
        try:
            res = run_channel(ch, jobs, out_dir, args.concurrency,
                              timeout_s=args.timeout, max_retries=args.retries,
                              on_row=append_row)
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
            with lock:
                worker_errors[name] = detail
            seen: dict[tuple[str, str | None], int] = defaultdict(int)
            res = []
            for item, lang in jobs:
                key = (item.id, lang)
                sample = seen[key]
                seen[key] += 1
                res.append(_error_row(ch, item, lang, "worker_error", detail, sample=sample, run_id=out_dir.name))
            for row in res:
                append_row(row)
        with lock:
            results[name] = res

    for name in names:
        t = threading.Thread(target=worker, args=(name,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    for name in names:
        rows.extend(results.get(name, []))

    summary = summarize(rows, names, args.pass_k)
    write_summary(out_dir, summary, rows, meta)
    print(f"\n完成：{out_dir}/summary.md")
    for name, entry in summary.items():
        o = entry["overall"]
        print(f"  {name:18} pass@1={o['pass_at_1']} pass@{args.pass_k}={o['pass_at_k']} ({o['passed']}/{o['judged']}) mean={o['mean_score10']} missing={o['missing']} errors={o['errors']} pending={o['pending_review']}")
    if worker_errors:
        for name, detail in worker_errors.items():
            print(f"worker_error[{name}]: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
