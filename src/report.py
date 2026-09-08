"""报告：家族 / 题库 / I / D 分栏。禁止总分、禁止密钥、禁止「支持」。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from src.bank import DOMAINS
from src.cluster import cluster_id_from_row, raw_matrix_from_bank
from src.types import BankResult, DegradeResult, FamilyResult, IdentityResult
from src.usage import summarize_jsonl

_SECRET_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "access_token",
        "auth_token",
    }
)

_CONF_ZH = {"high": "高", "medium": "中", "low": "低"}


def write_run_report(
    run_dir: Path,
    *,
    targets: Any,
    family: FamilyResult | None,
    extra: dict | None = None,
    bank: BankResult | None = None,
    bank_ref: BankResult | None = None,
    identity: IdentityResult | None = None,
    degrade: DegradeResult | None = None,
    wrapper: Any = None,
    sku: Any = None,
    envelopes: Any = None,
) -> None:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = _run_payload(targets, family, extra, bank, bank_ref, identity, degrade)
    if wrapper is not None:
        payload["wrapper"] = asdict(wrapper) if is_dataclass(wrapper) else wrapper
    if sku is not None:
        payload["sku"] = asdict(sku) if is_dataclass(sku) else sku
    if envelopes is not None:
        payload["envelopes"] = asdict(envelopes) if is_dataclass(envelopes) else envelopes
    traffic = summarize_jsonl(run_dir / "requests.jsonl")
    if traffic:
        payload["traffic"] = traffic
    (run_dir / "family.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if bank is not None:
        (run_dir / "bank.json").write_text(
            json.dumps(asdict(bank), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    _write_human_reports(run_dir, payload)


def render_run(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    family_path = run_dir / "family.json"
    payload = json.loads(family_path.read_text(encoding="utf-8"))
    traffic = summarize_jsonl(run_dir / "requests.jsonl")
    if traffic:
        payload["traffic"] = traffic
    _write_human_reports(run_dir, payload)


def _write_gallery(run_dir: Path) -> None:
    from src.gallery import write_run_gallery

    write_run_gallery(run_dir)


def _write_human_reports(run_dir: Path, payload: dict[str, Any]) -> None:
    title = f"Audit {run_dir.name}"
    report = _report_struct(title, payload)
    (run_dir / "report.md").write_text(_render_md(title, payload), encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if payload.get("bank"):
        _write_gallery(run_dir)


def _run_payload(
    targets: Any,
    family: FamilyResult | None,
    extra: dict | None,
    bank: BankResult | None,
    bank_ref: BankResult | None,
    identity: IdentityResult | None = None,
    degrade: DegradeResult | None = None,
) -> dict[str, Any]:
    return {
        "target": _endpoint_public(_get(targets, "target")),
        "claimed": _get(targets, "claimed_model"),
        "reference": _endpoint_public(_get(targets, "reference")),
        "family": asdict(family) if family is not None else None,
        "bank": asdict(bank) if bank is not None else None,
        "bank_ref": asdict(bank_ref) if bank_ref is not None else None,
        "identity": asdict(identity) if identity is not None else None,
        "degrade": asdict(degrade) if degrade is not None else None,
        "extra": _strip_secrets(extra) if extra else None,
    }


def _report_struct(title: str, payload: dict[str, Any]) -> dict[str, Any]:
    fam = payload.get("family") or {}
    bank = payload.get("bank")
    return {
        "title": title,
        "target": payload.get("target"),
        "claimed": payload.get("claimed"),
        "reference": payload.get("reference"),
        "provenance": _bank_provenance(bank),
        "columns": {
            "family": _family_column(fam),
            "identity": payload.get("identity")
            or {"status": "skipped", "note": "本 run 未跑 I"},
            "degrade": payload.get("degrade") or {"status": "skipped"},
        },
        "traffic": payload.get("traffic"),
        "bank": bank,
        "appendix": {
            "family_probes": fam.get("probes") or [],
            "family_scores": fam.get("scores") or [],
            "wrapper": payload.get("wrapper"),
            "sku": payload.get("sku"),
            "envelopes": payload.get("envelopes"),
            "bank_ref": payload.get("bank_ref"),
            "coding_agree": (payload.get("identity") or {}).get("coding_agree")
            if isinstance(payload.get("identity"), dict)
            else None,
        },
    }


def _family_column(fam: dict[str, Any]) -> dict[str, Any]:
    status = fam.get("status")
    n = fam.get("n_probes") or 0
    hits = fam.get("hits")
    return {
        "status": status,
        "family": fam.get("family"),
        "hits": f"{hits}/{n}" if n else hits,
        "l1": fam.get("l1"),
        "runner_up": fam.get("runner_up"),
        "runner_up_hits": fam.get("runner_up_hits"),
        "runner_up_l1": fam.get("runner_up_l1"),
        "confidence": fam.get("confidence"),
        "untrusted_reason": fam.get("untrusted_reason"),
    }


def _render_md(title: str, payload: dict[str, Any]) -> str:
    fam = payload.get("family") or {}
    target = payload.get("target") or {}
    reference = payload.get("reference")
    identity = payload.get("identity")
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- target: {_fmt_endpoint(target)}",
            f"- claimed: {payload.get('claimed') or '（无）'}",
            f"- reference: {_fmt_endpoint(reference) if reference else '（无）'}",
            "",
            f"- 家族：{_fmt_family_bar(fam) if fam else '（本 run 未跑 F）'}",
            f"- 判真：{_fmt_identity(identity)}",
            f"- 降智：{_fmt_degrade(payload.get('degrade'))}",
            "",
            *_render_bank_bars(payload.get("bank"), payload.get("bank_ref")),
            *_render_traffic(payload.get("traffic")),
            "## 附录",
            "",
            *_render_probe_table(fam),
            *_render_shell_appendix(payload),
            *_render_bank_table(payload.get("bank"), "target"),
            *_render_bank_table(payload.get("bank_ref"), "reference"),
            *_render_coding_agree(identity.get("coding_agree") if isinstance(identity, dict) else None),
        ]
    )


def _render_shell_appendix(payload: dict[str, Any]) -> list[str]:
    wrapper = payload.get("wrapper")
    sku = payload.get("sku")
    envelopes = payload.get("envelopes")
    if not any(isinstance(x, dict) for x in (wrapper, sku, envelopes)):
        return []
    lines = [
        "### 壳 / 适配器（不进 F/I/D）",
        "",
        "- 对照词表只当本地计数器。不能证明是同一条权重。",
        "",
    ]
    if isinstance(wrapper, dict):
        lines.append(f"- wrapper：{_fmt_wrapper(wrapper)}")
    if isinstance(sku, dict):
        lines.append(f"- sku：{_fmt_sku(sku)}")
        for peer in sku.get("peers") or []:
            if not isinstance(peer, dict):
                continue
            offset = peer.get("wrapper_offset")
            signed = f"{offset:+d}" if type(offset) is int else "—"
            lines.append(
                f"  - vs {peer.get('peer_id')}: offset={signed} "
                f"effort={peer.get('effort_none_kind') or '—'}；{peer.get('note') or ''}"
            )
    if isinstance(envelopes, dict):
        lines.append(f"- envelopes：{_fmt_envelopes(envelopes)}")
        for probe in envelopes.get("probes") or []:
            if not isinstance(probe, dict):
                continue
            lines.append(
                f"  - {probe.get('name')}: http={_cell(probe.get('http'))} "
                f"kind={probe.get('kind') or '—'}"
            )
    lines.append("")
    return lines


def _fmt_wrapper(wrapper: dict[str, Any]) -> str:
    status = wrapper.get("status") or "—"
    cid = wrapper.get("catalog_id")
    value = wrapper.get("value")
    spread = wrapper.get("spread")
    parts = [str(status)]
    if cid:
        parts.append(str(cid))
    if type(value) is int:
        parts.append(f"{value:+d}")
    if spread is not None:
        parts.append(f"spread={spread}")
    if wrapper.get("untrusted_reason"):
        parts.append(f"（{wrapper['untrusted_reason']}）")
    return " ".join(parts)


def _fmt_sku(sku: dict[str, Any]) -> str:
    status = sku.get("status") or "—"
    target = sku.get("target") if isinstance(sku.get("target"), dict) else {}
    hi = target.get("hi_prompt_tokens")
    note = sku.get("note") or ""
    parts = [str(status)]
    if hi is not None:
        parts.append(f"hi={hi}")
    if note:
        parts.append(note)
    return " ".join(parts)


def _fmt_envelopes(envelopes: dict[str, Any]) -> str:
    status = envelopes.get("status") or "—"
    family = envelopes.get("family")
    note = envelopes.get("note") or ""
    parts = [str(family or status)]
    if note:
        parts.append(note)
    return " ".join(parts)


def _render_probe_table(fam: dict[str, Any]) -> list[str]:
    probes = fam.get("probes") or []
    if not probes:
        return []
    catalog_ids = _catalog_ids(probes)
    header = ["probe", "delta_api", *catalog_ids, "dropped"]
    lines = [
        "### F 每条 delta vs 各候选 n_hat",
        "",
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for pd in probes:
        n_hat = pd.get("n_hat") or {}
        cells = [
            str(pd.get("probe_id") or ""),
            _cell(pd.get("delta_api")),
            *(_cell(n_hat.get(cid)) for cid in catalog_ids),
            _cell(pd.get("drop_reason") if pd.get("dropped") else ""),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _bank_provenance(bank: Any) -> dict[str, Any] | None:
    if not isinstance(bank, dict):
        return None
    return {
        "schema_version": bank.get("schema_version"),
        "bank_version": bank.get("bank_version"),
        "scorer_version": bank.get("scorer_version"),
        "sampling_protocol": bank.get("sampling_protocol"),
    }


def _render_bank_bars(bank: Any, bank_ref: Any) -> list[str]:
    if not isinstance(bank, dict):
        return []
    lines = [
        f"- 版本：{_fmt_bank_versions(bank)}",
        f"- 模式：{_fmt_bank_mode(bank)}，原始题 {bank.get('raw_question_count') or _raw_count(bank)} 道，展开题 {bank.get('expanded_question_count') or bank.get('n_questions') or len(bank.get('questions') or [])} 道",
        f"- 编码题：raw cluster {bank.get('coding_cluster_count') or '—'}，语言变体 {bank.get('coding_variant_count') or '—'}；主统计按 raw cluster 等权（一题一票，不因三语展开加权）；三语言 missing 不进分母、不记 0 分",
        f"- 编码题可用语言口径：{_fmt_coding_stats(bank.get('coding_available'))}；三语齐全口径：{_fmt_coding_stats(bank.get('coding_strict'))}",
        f"- raw 难度矩阵：{_fmt_raw_matrix(bank)}",
        f"- 分域通过率（temperature=0，missing 不进分母）：{_fmt_domain_rates(bank)}",
        f"- 分域折合10（每题得分点/总分×10，再按域平均；不合成总分）：{_fmt_domain_score10(bank)}",
        f"- 分难度折合10：{_fmt_difficulty_score10(bank)}",
    ]
    if isinstance(bank_ref, dict):
        lines.append(f"- 参考源版本：{_fmt_bank_versions(bank_ref)}")
        lines.append(f"- 参考源分域通过率：{_fmt_domain_rates(bank_ref)}")
        lines.append(f"- 参考源分域折合10：{_fmt_domain_score10(bank_ref)}")
        lines.append(f"- 参考源分难度折合10：{_fmt_difficulty_score10(bank_ref)}")
    alarm = bank.get("knowledge_alarm")
    if alarm:
        lines.append(f"- 知识冒烟：{alarm}")
    lines.append("- 编码抽不出代码或本机缺工具链记 missing，不中断整场，不进 D 分母")
    lines.append("")
    return lines


def _fmt_bank_versions(bank: dict[str, Any]) -> str:
    protocol = bank.get("sampling_protocol") or "—"
    note = "single-v1=每题 1 次；旧 4 次采样是另一口径，不可混比"
    return (
        f"bank_version={bank.get('bank_version') or '—'}；"
        f"scorer_version={bank.get('scorer_version') or '—'}；"
        f"sampling_protocol={protocol}（{note}）"
    )


def _fmt_bank_mode(bank: dict[str, Any]) -> str:
    scope = "快速（easy/medium，T=0）" if bank.get("quick") else "全量（四档）"
    protocol = bank.get("sampling_protocol")
    if protocol == "single-v1":
        return f"{scope}，每题 1 次（sampling_protocol=single-v1）"
    if protocol:
        return f"{scope}，sampling_protocol={protocol}"
    return f"{scope}，采样协议未标注"


def _raw_count(bank: dict[str, Any]) -> int:
    seen: set[str] = set()
    for row in bank.get("questions") or []:
        if not isinstance(row, dict):
            continue
        raw = cluster_id_from_row(row)
        if raw:
            seen.add(raw)
    return len(seen)


def _fmt_raw_matrix(bank: dict[str, Any]) -> str:
    matrix = bank.get("raw_matrix") or raw_matrix_from_bank(bank)
    parts = []
    for domain in DOMAINS:
        row = matrix.get(domain) or {}
        values = "/".join(str(row.get(diff, 0)) for diff in ("easy", "medium", "hard", "extreme"))
        parts.append(f"{domain} {values}")
    return "；".join(parts)


def _fmt_coding_stats(stats: Any) -> str:
    if not isinstance(stats, dict):
        return "—"
    rate = stats.get("rate")
    missing = stats.get("missing")
    text = f"{stats.get('passed', 0)}/{stats.get('judged', 0)}"
    if rate is not None:
        text += f" ({rate})"
    if missing is not None:
        text += f" missing={missing}"
    return text


def _fmt_domain_rates(bank: dict[str, Any]) -> str:
    rates = bank.get("domain_pass0") or {}
    parts = []
    for domain in DOMAINS:
        row = rates.get(domain) or {}
        parts.append(
            f"{domain} {row.get('passed', 0)}/{row.get('judged', 0)} missing={row.get('missing', 0)}"
        )
    return "；".join(parts)


def _fmt_difficulty_score10(bank: dict[str, Any]) -> str:
    rows = bank.get("difficulty_points") or {}
    parts = []
    for key in ("easy", "medium", "hard", "extreme"):
        row = rows.get(key) or {}
        score = row.get("score10")
        label = key
        if score is None:
            parts.append(f"{label} —")
        else:
            parts.append(f"{label} {score}（{row.get('passed', 0)}/{row.get('judged', 0)}）")
    return "；".join(parts)


def _fmt_domain_score10(bank: dict[str, Any]) -> str:
    rows = bank.get("domain_points") or {}
    parts = []
    for domain in DOMAINS:
        row = rows.get(domain) or {}
        score = row.get("score10")
        earned = row.get("earned")
        total = row.get("total")
        if score is None:
            parts.append(f"{domain} —")
        else:
            parts.append(f"{domain} {score}（{earned}/{total}）")
    return "；".join(parts)


def _render_bank_table(bank: Any, label: str) -> list[str]:
    if not isinstance(bank, dict):
        return []
    lines = [
        f"### C 每题对错（{label}）",
        "",
        "| id | domain | 难度 | construct | pass0 | missing | score10 | points | majority | samples | question_hash | fixture_hash |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for q in bank.get("questions") or []:
        if not isinstance(q, dict):
            continue
        samples = q.get("samples") or []
        flags = ",".join(str(s.get("status")) for s in samples)
        first = samples[0] if samples else {}
        pts = first.get("points")
        total = first.get("points_total")
        point_cell = f"{pts}/{total}" if pts is not None and total is not None else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    str(q.get("question_id") or ""),
                    str(q.get("domain") or ""),
                    _cell(q.get("difficulty")),
                    _cell(q.get("construct")),
                    _cell(q.get("pass0")),
                    _missing_cell(q),
                    _cell(q.get("score10")),
                    point_cell,
                    _cell(q.get("majority")),
                    flags,
                    _cell(q.get("question_hash")),
                    _cell(q.get("fixture_hash")),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _missing_cell(q: dict[str, Any]) -> str:
    samples = q.get("samples") or []
    n = sum(1 for s in samples if isinstance(s, dict) and s.get("status") == "missing")
    if n:
        return str(n)
    if q.get("pass0") is None:
        return "1"
    return "0"


def _render_coding_agree(block: Any) -> list[str]:
    if not isinstance(block, dict):
        return []
    return [
        "### 编码题一致率（附录，不驱动 I）",
        "",
        f"- compared={block.get('compared')} agree={block.get('agree')} rate={block.get('rate')}",
        f"- {block.get('note') or ''}",
        "",
    ]


def _render_traffic(traffic: Any) -> list[str]:
    if not isinstance(traffic, dict):
        return []
    lines = [
        "## 流量 / 缓存 / 速率",
        "",
        f"- 请求：{traffic.get('ok')}/{traffic.get('requests')} 成功",
        f"- 输入 token：{_fmt_sum_max(traffic.get('prompt_tokens'))}",
        f"- 输出 token：{_fmt_sum_max(traffic.get('completion_tokens'))}",
        f"- 缓存命中 token：{_fmt_sum_max(traffic.get('cached_tokens'))}",
        f"- 计费输入（prompt−cached）：{_fmt_sum_max(traffic.get('billed_prompt_tokens'))}",
        f"- 输入/输出字符：{_fmt_sum_max(traffic.get('input_chars'))} / {_fmt_sum_max(traffic.get('output_chars'))}",
        f"- 墙钟延迟 ms：{_fmt_avg_max(traffic.get('latency_ms'))}",
        f"- 端到端输出 tok/s：{_fmt_avg_max(traffic.get('e2e_output_tps'))}",
        f"- TTFT ms：{_fmt_avg_max(traffic.get('ttft_ms'))}",
        f"- decode tok/s（TTFT→结束）：{_fmt_avg_max(traffic.get('decode_tps'))}",
        f"- 缓存命中率（有 usage 的请求均值）：{traffic.get('cache_hit_ratio') if traffic.get('cache_hit_ratio') is not None else '（未返回 cached）'}",
        f"- 速率口径：{traffic.get('rate_basis') or 'e2e_wall_clock'}（e2e 含排队+预填；decode 要 --stream-metrics）",
        "",
    ]
    return lines


def _fmt_sum_max(block: Any) -> str:
    if not isinstance(block, dict):
        return "（无）"
    return f"合计 {block.get('sum')} / 单次最大 {block.get('max')}"


def _fmt_avg_max(block: Any) -> str:
    if not isinstance(block, dict):
        return "（无）"
    return f"均值 {block.get('avg')} / 最大 {block.get('max')}"


def _fmt_identity(identity: Any) -> str:
    if not isinstance(identity, dict):
        return "skipped"
    status = identity.get("status") or "skipped"
    note = identity.get("note")
    extra = []
    if identity.get("claimed_family"):
        extra.append(f"声称 {identity['claimed_family']}")
    if identity.get("observed_family"):
        extra.append(f"观测 {identity['observed_family']}")
    body = status if not extra else f"{status}（{'；'.join(extra)}）"
    if note:
        return f"{body}。{note}"
    return body


def _fmt_degrade(degrade: Any) -> str:
    if not isinstance(degrade, dict):
        return "skipped"
    status = degrade.get("status") or "skipped"
    note = degrade.get("note") or ""
    return f"{status}。{note}" if note else str(status)


def _fmt_family_bar(fam: dict[str, Any]) -> str:
    status = fam.get("status")
    name = fam.get("family") or status
    if status == "token_untrusted":
        reason = fam.get("untrusted_reason")
        return f"token_untrusted" + (f"（{reason}）" if reason else "")
    if status == "ambiguous":
        return "ambiguous"
    n = fam.get("n_probes") or 0
    hits = fam.get("hits")
    l1 = fam.get("l1")
    runner = fam.get("runner_up")
    conf = _CONF_ZH.get(fam.get("confidence") or "", fam.get("confidence") or "")
    parts = [str(name), f"{hits}/{n}", f"l1={l1}"]
    if runner:
        parts.append(f"第二名 {runner}")
    if conf:
        parts.append(str(conf))
    return " | ".join(parts)


def _fmt_endpoint(ep: Any) -> str:
    if not ep:
        return "（无）"
    model = ep.get("model") if isinstance(ep, dict) else getattr(ep, "model", None)
    url = ep.get("base_url") if isinstance(ep, dict) else getattr(ep, "base_url", None)
    if model and url:
        return f"{model} @ {url}"
    return str(model or url or "（无）")


def _catalog_ids(probes: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for pd in probes:
        for kid in (pd.get("n_hat") or {}):
            if kid not in seen:
                seen.add(kid)
                ids.append(kid)
    return ids


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _endpoint_public(ep: Any) -> dict[str, Any] | None:
    if ep is None:
        return None
    if is_dataclass(ep) and not isinstance(ep, type):
        raw = asdict(ep)
    elif isinstance(ep, dict):
        raw = dict(ep)
    else:
        raw = {
            "base_url": getattr(ep, "base_url", None),
            "model": getattr(ep, "model", None),
            "api_key_env": getattr(ep, "api_key_env", None),
        }
    return {
        "base_url": raw.get("base_url"),
        "model": raw.get("model"),
        "api_key_env": raw.get("api_key_env"),
        "channel": raw.get("channel"),
        "api": raw.get("api"),
    }


def _strip_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if _is_secret_key(str(key)):
                continue
            out[key] = _strip_secrets(value)
        return out
    if isinstance(data, list):
        return [_strip_secrets(v) for v in data]
    return data


def _is_secret_key(name: str) -> bool:
    n = name.lower()
    if n in _SECRET_NAMES:
        return True
    if n.endswith("_key") and n != "api_key_env":
        return True
    return False
