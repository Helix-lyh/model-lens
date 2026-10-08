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
import os
import secrets
import subprocess
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

from eval_bank_20260925.challenge import salt_prompt, salted_prompt_hash  # noqa: E402
from eval_bank_20260925.report import render_markdown  # noqa: E402
from src.limits import official_max_output  # noqa: E402
from eval_bank_20260925.evaluation import is_timeout_error, normalize_verdict, pass_at_k as _shared_pass_at_k, score_item as _shared_score_item, scoring_provenance, summarize as _shared_summarize, summarize_engineering, timeout_verdict as _shared_timeout_verdict  # noqa: E402
from eval_bank_20260925.bank_manifest import ITEM_CODE_LANG, active_item_ids, bank_for_item, item_provenance  # noqa: E402
from eval_bank_20260925.bank_adapters import render_item_prompt  # noqa: E402
from eval_bank_20260925.bank_registry import ITEMS as PLUGIN_ITEMS  # noqa: E402
from src.client import ChatClient, JsonlRecorder  # noqa: E402
from src.types import Endpoint  # noqa: E402

GROK_AUTH = Path.home() / ".grok" / "auth.json"
GROK_PROXY_HEADERS = {
    "X-XAI-Token-Auth": "xai-grok-cli",
    "x-grok-client-version": "1.0.41",
}
@dataclass(frozen=True)
class EngineeringItem:
    id: str
    level: str
    title: str
    prompt: str
    reference: str | None = None
    kind: str = "engineering"


ALL_BY_ID = {
    plugin.item_id: EngineeringItem(
        plugin.item_id,
        "extreme",
        plugin.title,
        plugin.prompt(),
        kind=plugin.domain,
    )
    for plugin in PLUGIN_ITEMS.items()
}


def _unique(values: list[str]) -> list[str]:
    """稳定去重，避免重复参数扩大请求数和分母。"""
    return list(dict.fromkeys(value for value in values if value))


def _is_coding(item: Any) -> bool:
    return bool(getattr(item, "reference", None)) or getattr(item, "kind", None) == "coding"


def _item_prompt(item: Any, lang: str | None) -> str:
    return render_item_prompt(item, lang)


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


def _is_timeout_error(error: str | None, status_code: int | None = None) -> bool:
    return is_timeout_error(error, status_code)


def _score_item(item: Any, item_id: str, lang: str | None, text: str) -> Any:
    """Score whatever content arrived, including a timed-out partial response."""
    return _shared_score_item(item, text, language=lang)


def _verdict_fields(verdict: Any) -> dict[str, Any]:
    return normalize_verdict(verdict)


def _timeout_verdict(item: Any, item_id: str, lang: str | None, text: str) -> dict[str, Any]:
    """Timeouts are failed attempts; preserve points from parseable partial output."""
    return _verdict_fields(_shared_timeout_verdict(item, text, language=lang))


def _error_row(ch: Channel, item: Any, lang: str | None, reason: str, detail: str, *, sample: int = 0, run_id: str | None = None) -> dict[str, Any]:
    return {
        "channel": ch.name,
        "model": ch.model,
        "item": item.id,
        "lang": lang,
        "sample": sample,
        "run_id": run_id,
        "experiment_id": run_id,
        **item_provenance(item.id),
        **scoring_provenance(item, lang),
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
    def cap(model: str) -> int:
        value = official_max_output(model)
        if value is None:
            raise SystemExit(f"{model} 没有登记官方 max output")
        return value

    out = [
        Channel("deepseek-flash", "deepseek-flash", booster, "BOOSTER_API_KEY", cap("deepseek-flash"), {}),
        Channel("space-bunny-free", "space-bunny-free", booster, "BOOSTER_API_KEY", cap("space-bunny-free"), {}),
        Channel("deepseek-chat", "deepseek-chat", _deepseek_base(), "DEEPSEEK_API_KEY", cap("deepseek-v4"), {}),
        Channel("mimo-v2.6-flash", "mimo-v2.6-flash", booster, "BOOSTER_API_KEY", cap("mimo-v2.6-flash"), {}),
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


def pick_items(phase: str, only: list[str] | None = None, *, bank_profile: str = "active") -> list[Any]:
    if only:
        only = _unique(only)
        missing = [i for i in only if i not in ALL_BY_ID]
        if missing:
            raise SystemExit(f"未知题号 {missing}")
        return [ALL_BY_ID[i] for i in only]
    if bank_profile != "active":
        raise ValueError(f"unknown bank profile: {bank_profile}")
    return [ALL_BY_ID[item_id] for item_id in active_item_ids(list(ALL_BY_ID), phase)]


def jobs_for(items: list[Any], langs: list[str], samples: int = 1) -> list[tuple[Any, str | None]]:
    if samples < 1:
        raise ValueError("samples must be >= 1")
    langs = _unique(langs)
    jobs: list[tuple[Any, str | None]] = []
    for item in items:
        if _is_coding(item):
            assigned = ITEM_CODE_LANG.get(item.id)
            if assigned is not None:
                if assigned in langs:
                    jobs.append((item, assigned))
                continue
            bank = bank_for_item(item.id)
            if bank.languages:
                chosen = [lang for lang in langs if lang in bank.languages]
                if not chosen:
                    raise ValueError(f"{item.id} 需要 {', '.join(bank.languages)} 中的语言")
                for lang in chosen:
                    jobs.append((item, lang))
                continue
            for lang in langs:
                jobs.append((item, lang))
        else:
            jobs.append((item, None))
    return jobs * samples


def run_one(client: ChatClient, ch: Channel, item: Any, lang: str | None, out_dir: Path,
            timeout_s: float, sample: int = 0) -> dict[str, Any]:
    item_id = item.id
    provenance = {
        **item_provenance(item_id),
        **scoring_provenance(item, lang),
        "experiment_id": out_dir.name,
    }
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
        kind=f"eval20261008:{tag}",
        stream=False,
    )
    text = record.content or ""
    stem = out_dir / ch.name / tag
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".txt").write_text(text, encoding="utf-8")
    if record.status_code != 200 or record.error:
        timed_out = _is_timeout_error(record.error, record.status_code)
        if timed_out:
            verdict = _timeout_verdict(item, item_id, lang, text)
            fields = _verdict_fields(verdict)
            return {
                "channel": ch.name, "model": ch.model, "item": item_id, "lang": lang, "sample": sample, "run_id": out_dir.name,
                **provenance, **fields, "request_error": record.error, "response_model": None,
                "usage": record.usage, "latency_ms": record.latency_ms,
                "finish_reason": _finish_reason(record.raw), "truncated": False,
                "salt": salt, "base_prompt_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
                "prompt_sha256": salted_prompt_hash(prompt),
            }
        return {
            "channel": ch.name, "model": ch.model, "item": item_id, "lang": lang, "sample": sample, "run_id": out_dir.name,
            **provenance,
            "status": "error", "reason_code": "timeout" if timed_out else "request_error", "passed": None,
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
        verdict = _timeout_verdict(item, item_id, lang, text)
    elif finish_reason == "length":
        verdict = {"status": "error", "reason_code": "response_truncated", "passed": None, "points": None, "score10": None}
    else:
        verdict = _score_item(item, item_id, lang, text)
    fields = _verdict_fields(verdict)
    return {
        "channel": ch.name, "model": ch.model, "item": item_id, "lang": lang, "sample": sample, "run_id": out_dir.name,
        **provenance, **fields, "response_model": response_model,
        "usage": record.usage, "latency_ms": record.latency_ms,
        "finish_reason": finish_reason, "truncated": finish_reason == "length",
        "salt": salt, "base_prompt_sha256": hashlib.sha256(base_prompt.encode()).hexdigest(),
        "prompt_sha256": salted_prompt_hash(prompt),
    }


def run_channel(ch: Channel, jobs: list[tuple[Any, str | None]], out_dir: Path, concurrency: int,
                *, timeout_s: float = 20 * 60, max_retries: int = 1,
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
            shown = row.get("points")
            if row.get("net_points") is not None:
                shown = f"{row.get('positive_points')}-{row.get('negative_points')}={row.get('net_points')}"
            print(f"  [{ch.name}] {row.get('item')} {row.get('lang') or ''} -> {row.get('status')} {shown}", flush=True)
    return results


def _pass_at_k(rows: list[dict[str, Any]], k: int) -> tuple[float | None, int, int]:
    """按(题目,语言)先算独立采样 pass@k，再对题目等权平均。"""
    return _shared_pass_at_k(rows, k)


def summarize(rows: list[dict[str, Any]], model_names: list[str], pass_k: int = 1) -> dict[str, Any]:
    def bucket(rows_filtered: list[dict[str, Any]]) -> dict[str, Any]:
        return _shared_summarize(rows_filtered, pass_k=pass_k)

    by_model: dict[str, Any] = {}
    for name in model_names:
        mine = [r for r in rows if r["channel"] == name]
        engineering_rows = [r for r in mine if _item_domain(r.get("item")) == "engineering"]
        entry: dict[str, Any] = {}
        if engineering_rows:
            entry["engineering"] = summarize_engineering(engineering_rows, pass_k=pass_k)
        for domain in ("reasoning", "coding", "engineering"):
            if domain == "engineering":
                continue
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
    payload = {"meta": meta, "summary": summary, "bank_version": "20261008"}
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(render_markdown({**meta, "bank_version": "20261008"}, rows), encoding="utf-8")


def publish_reports(out_dir: Path, channels: list[str]) -> None:
    """评测结束就生成页面。单模型页看 deepseek-flash；两个及以上模型再出对比页。"""
    root = Path(__file__).resolve().parents[2]
    scripts = root / "cursor_workspace" / "build_scripts"
    commands = [(
        [sys.executable, str(scripts / "build_eval_ledger_20261006.py")],
        "单模型页",
    )]
    if len(channels) >= 2:
        commands.append((
            [sys.executable, str(scripts / "build_eval_matrix.py"), "--run", str(out_dir)],
            "对比页",
        ))
    for command, label in commands:
        completed = subprocess.run(command, cwd=root, check=False)
        if completed.returncode != 0:
            print(f"{label}未生成，退出码 {completed.returncode}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("quick", "hard"), required=True)
    parser.add_argument("--langs", default="python", help="编程题语言，逗号分隔：python,go,typescript")
    parser.add_argument("--models", default="deepseek-flash,space-bunny-free", help="只跑指定渠道，逗号分隔；默认 booster 工程校准双渠道")
    parser.add_argument(
        "--temp-channel", action="append", default=[],
        help="临时 booster 渠道，格式 name=model_id，可重复；密钥仍只读 BOOSTER_API_KEY",
    )
    parser.add_argument("--items", default="", help="只跑指定题号，逗号分隔；默认按 phase")
    parser.add_argument("--bank-profile", choices=("active",), default="active",
                        help="只跑 20261008 活跃题库")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--samples", type=int, default=1, help="每道题独立采样次数；默认 1")
    parser.add_argument("--pass-at", type=int, default=1, dest="pass_k", help="报告 pass@k；必须不大于 --samples")
    parser.add_argument("--timeout", type=float, default=20 * 60, help="单次请求超时秒，默认 1200（20 分钟）")
    parser.add_argument("--retries", type=int, default=3, help="HTTP 5xx/连接错误重试次数；超时永不重试；默认 3")
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
    booster = _booster_base()
    for spec in args.temp_channel:
        if "=" not in spec:
            parser.error(f"--temp-channel 需要 name=model_id，收到 {spec!r}")
        name, model_id = spec.split("=", 1)
        name, model_id = name.strip(), model_id.strip()
        if not name or not model_id:
            parser.error(f"--temp-channel 需要 name=model_id，收到 {spec!r}")
        cap = official_max_output(model_id) or official_max_output(name)
        if cap is None:
            parser.error(f"{model_id} 没有登记官方 max output，先写入 catalog/output_limits.yaml")
        all_channels[name] = Channel(name, model_id, booster, "BOOSTER_API_KEY", cap, {})
    names = _unique(args.models.split(",") if args.models else list(all_channels))
    unknown = [n for n in names if n not in all_channels]
    if unknown:
        parser.error(f"未知渠道 {unknown}，可选 {list(all_channels)}")
    langs = _unique(args.langs.split(","))

    requested_items = _unique(args.items.split(",")) or None
    items = pick_items(args.phase, requested_items, bank_profile=args.bank_profile)
    if not items:
        parser.error("当前阶段没有可运行题目")
    unknown_langs = set(langs) - {"python", "go", "typescript"}
    if unknown_langs or not langs:
        parser.error(f"--langs 需要 python,go,typescript 中的语言，收到 {langs}")
    try:
        jobs = jobs_for(items, langs, args.samples)
    except ValueError as exc:
        parser.error(str(exc))
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = Path(args.out) / f"eval-20261008-{stamp}-{args.phase}"
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_grok_token()
    meta = {"phase": args.phase, "bank_profile": args.bank_profile, "bank_version": "20261008",
            "langs": langs, "models": names,
            "experiment_id": out_dir.name,
            "banks": {bank_for_item(item.id).id: bank_for_item(item.id).version for item in items},
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
    publish_reports(out_dir, names)
    for name, entry in summary.items():
        for domain in ("coding", "engineering", "reasoning"):
            if domain not in entry:
                continue
            stats = entry[domain]
            if domain == "engineering":
                print(f"  {name:18} {domain} positive={stats['positive_points']} negative={stats['negative_points']} net={stats['net_points']} strict={stats['strict_passed']}/{stats['judged']} missing={stats['missing']} errors={stats['errors']}")
            else:
                print(f"  {name:18} {domain} pass@1={stats['pass_at_1']} pass@{args.pass_k}={stats['pass_at_k']} ({stats['passed']}/{stats['judged']}) mean={stats['mean_percent']}% missing={stats['missing']} errors={stats['errors']}")
    if worker_errors:
        for name, detail in worker_errors.items():
            print(f"worker_error[{name}]: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
