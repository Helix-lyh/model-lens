"""model-lens CLI：family 只跑 F；bank / audit 跑题库。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from src.bank import DEFAULT_CONCURRENCY, load_questions, run_bank
from src.client import ChatClient, JsonlRecorder
from src.config import load_targets
from src.compare import decide_degrade, decide_identity
from src.catalog import lookup_claimed_family
from src.family import format_family_line
from src.types import BankResult, DegradeResult, Endpoint, FamilyResult, IdentityResult, Targets


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _new_run_dir(out_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


FAMILY_TIMEOUT_S = 60.0
BANK_TIMEOUT_S = 180.0


def _add_concurrency(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"同时进行的请求数，默认 {DEFAULT_CONCURRENCY}；家族 BASE 仍先串行",
    )


def _client(endpoint, run_dir: Path, *, timeout_s: float) -> ChatClient:
    return ChatClient(endpoint, JsonlRecorder(run_dir / "requests.jsonl"), timeout_s=timeout_s)


def _run_family(client: ChatClient, *, concurrency: int = DEFAULT_CONCURRENCY) -> FamilyResult:
    from src.catalog import load_catalog
    from src.family import run_family
    from src.probes import load_family_probes

    root = _project_root()
    catalog = load_catalog(root)
    base, probes = load_family_probes(root)
    return run_family(client, catalog, base, probes, concurrency=concurrency)


def _run_bank(
    client: ChatClient,
    *,
    salt: str,
    quick: bool,
    prefix: str,
    stream_metrics: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> BankResult:
    return run_bank(
        client,
        load_questions(_project_root()),
        salt=salt,
        quick=quick,
        repo=_project_root(),
        kind_prefix=prefix,
        stream_metrics=stream_metrics,
        concurrency=concurrency,
    )


def _write_report(
    run_dir: Path,
    targets: Targets,
    family: FamilyResult | None,
    bank: BankResult | None = None,
    bank_ref: BankResult | None = None,
    identity: IdentityResult | None = None,
    degrade: DegradeResult | None = None,
    wrapper=None,
    sku=None,
    envelopes=None,
) -> None:
    from src.report import write_run_report

    write_run_report(
        run_dir,
        targets=targets,
        family=family,
        bank=bank,
        bank_ref=bank_ref,
        identity=identity,
        degrade=degrade,
        wrapper=wrapper,
        sku=sku,
        envelopes=envelopes,
    )


def resolve_shell_peers(targets: Targets, peers_arg: str | None) -> list[str]:
    """对照 id：--peers 优先；否则用 claimed_model（和 target 不同才收）。"""
    target_id = targets.target.model
    if peers_arg:
        return [p.strip() for p in peers_arg.split(",") if p.strip() and p.strip() != target_id]
    claimed = (targets.claimed_model or "").strip()
    if claimed and claimed != target_id:
        return [claimed]
    return []


def _peer_client(endpoint: Endpoint, model: str, run_dir: Path, *, timeout_s: float) -> ChatClient:
    from dataclasses import replace

    return _client(replace(endpoint, model=model), run_dir, timeout_s=timeout_s)


def _run_shell_layers(
    client: ChatClient,
    targets: Targets,
    run_dir: Path,
    *,
    peers: list[str],
    timeout_s: float,
):
    from src.catalog import load_catalog
    from src.envelopes import format_envelopes_line, run_envelopes
    from src.sku import format_sku_line, run_catalog_ab
    from src.wrapper import format_wrapper_line, run_wrapper

    catalog = load_catalog(_project_root())
    wrapper = run_wrapper(client, catalog)
    print(format_wrapper_line(wrapper))

    clients = {targets.target.model: client}
    for peer_id in peers:
        clients[peer_id] = _peer_client(
            targets.target, peer_id, run_dir, timeout_s=timeout_s
        )
    sku = run_catalog_ab(clients, target_id=targets.target.model)
    print(format_sku_line(sku))

    envelopes = run_envelopes(client)
    print(format_envelopes_line(envelopes))
    return wrapper, sku, envelopes


def _cmd_family(args: argparse.Namespace) -> int:
    targets = load_targets(args.target)
    run_dir = _new_run_dir(Path(args.out))
    client = _client(targets.target, run_dir, timeout_s=args.timeout)
    result = _run_family(client, concurrency=args.concurrency)
    identity = decide_identity(
        result, targets, claimed_family=lookup_claimed_family(targets.claimed_model)
    )
    _write_report(run_dir, targets, result, identity=identity)
    print(format_family_line(result))
    if targets.reference is not None:
        print(f"I={identity.status}")
    print(run_dir)
    return 0


def _cmd_bank(args: argparse.Namespace) -> int:
    targets = load_targets(args.target)
    run_dir = _new_run_dir(Path(args.out))
    client = _client(targets.target, run_dir, timeout_s=args.timeout)
    bank = _run_bank(
        client,
        salt=run_dir.name,
        quick=args.quick,
        prefix="bank",
        stream_metrics=args.stream_metrics,
        concurrency=args.concurrency,
    )
    _write_report(run_dir, targets, family=None, bank=bank)
    _print_bank(bank)
    print(run_dir)
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    targets = load_targets(args.target)
    run_dir = _new_run_dir(Path(args.out))
    client = _client(targets.target, run_dir, timeout_s=args.timeout)
    family = _run_family(client, concurrency=args.concurrency)
    print(format_family_line(family))
    bank = _run_bank(
        client,
        salt=run_dir.name,
        quick=args.quick,
        prefix="bank",
        stream_metrics=args.stream_metrics,
        concurrency=args.concurrency,
    )
    _print_bank(bank)
    bank_ref = None
    if targets.reference is not None:
        ref_client = _client(targets.reference, run_dir, timeout_s=args.timeout)
        bank_ref = _run_bank(
            ref_client,
            salt=run_dir.name,
            quick=args.quick,
            prefix="bank_ref",
            stream_metrics=args.stream_metrics,
            concurrency=args.concurrency,
        )
        _print_bank(bank_ref, label="reference")
    identity = decide_identity(
        family,
        targets,
        claimed_family=lookup_claimed_family(targets.claimed_model),
        bank=bank,
        bank_ref=bank_ref,
    )
    degrade = decide_degrade(
        identity,
        family,
        targets,
        bank,
        bank_ref,
        quick=args.quick,
        force=args.force_degrade,
    )
    print(f"I={identity.status}")
    print(f"D={degrade.status}")
    _write_report(
        run_dir,
        targets,
        family,
        bank=bank,
        bank_ref=bank_ref,
        identity=identity,
        degrade=degrade,
    )
    print(run_dir)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from src.report import render_run

    render_run(Path(args.run))
    return 0


def _cmd_gallery(args: argparse.Namespace) -> int:
    from src.gallery import write_gallery

    html = write_gallery([Path(p) for p in args.runs], Path(args.out))
    print(html)
    return 0


def _cmd_shell(args: argparse.Namespace) -> int:
    targets = load_targets(args.target)
    run_dir = _new_run_dir(Path(args.out))
    client = _client(targets.target, run_dir, timeout_s=args.timeout)
    wrapper, sku, envelopes = _run_shell_layers(
        client,
        targets,
        run_dir,
        peers=resolve_shell_peers(targets, args.peers),
        timeout_s=args.timeout,
    )
    _write_report(
        run_dir,
        targets,
        family=None,
        wrapper=wrapper,
        sku=sku,
        envelopes=envelopes,
    )
    print(run_dir)
    return 0


def _print_bank(bank: BankResult, *, label: str = "target") -> None:
    parts = [
        f"bank[{label}]",
        "快速" if bank.quick else "全量",
        f"n={bank.n_questions or len(bank.questions)}",
    ]
    for domain, row in bank.domain_pass0.items():
        pts = (bank.domain_points or {}).get(domain) or {}
        chunk = f"{domain}={row['passed']}/{row['judged']}"
        if pts.get("score10") is not None:
            chunk += f" 折合{pts['score10']}"
        parts.append(chunk)
    if bank.knowledge_alarm:
        parts.append(f"alarm={bank.knowledge_alarm}")
    print(" ".join(parts))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-lens",
        description="词表家族 / 题库 / 判真 / 降智粗筛；shell 只跑附录（壳 / SKU / 信封）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_family = sub.add_parser("family", help="只跑 Module F")
    p_family.add_argument("--target", required=True)
    p_family.add_argument("--out", default="out")
    p_family.add_argument(
        "--timeout",
        type=float,
        default=FAMILY_TIMEOUT_S,
        help=f"单次请求超时秒，默认 {FAMILY_TIMEOUT_S:.0f}",
    )
    _add_concurrency(p_family)
    p_family.set_defaults(func=_cmd_family)

    p_bank = sub.add_parser("bank", help="只跑 Module C 题库")
    p_bank.add_argument("--target", required=True)
    p_bank.add_argument("--out", default="out")
    p_bank.add_argument(
        "--quick",
        action="store_true",
        help="快速：只跑 easy/medium，每题 temperature=0 一次",
    )
    p_bank.add_argument(
        "--stream-metrics",
        action="store_true",
        help="题库走 SSE 测 TTFT / decode TPS；家族栏仍非流式。中转 streaming 的 usage 常不可信",
    )
    p_bank.add_argument(
        "--timeout",
        type=float,
        default=BANK_TIMEOUT_S,
        help=f"单次请求超时秒，默认 {BANK_TIMEOUT_S:.0f}（推理模型题库）",
    )
    _add_concurrency(p_bank)
    p_bank.set_defaults(func=_cmd_bank)

    p_report = sub.add_parser("report", help="对已有 run 重出 md/json")
    p_report.add_argument("--run", required=True)
    p_report.set_defaults(func=_cmd_report)

    p_gallery = sub.add_parser("gallery", help="多场 run 合成 HTML 对照页")
    p_gallery.add_argument("--run", dest="runs", action="append", required=True)
    p_gallery.add_argument("--out", default="out/gallery")
    p_gallery.set_defaults(func=_cmd_gallery)

    p_audit = sub.add_parser("audit", help="F + C + I/D")
    p_audit.add_argument("--target", required=True)
    p_audit.add_argument("--out", default="out")
    p_audit.add_argument(
        "--quick",
        action="store_true",
        help="快速：只跑 easy/medium 且 T=0；D=skipped",
    )
    p_audit.add_argument(
        "--force-degrade",
        action="store_true",
        help="即使 I 不是同族未分型也算 D（仍要求不同网关参考源）",
    )
    p_audit.add_argument(
        "--stream-metrics",
        action="store_true",
        help="仅题库走 SSE 测 TTFT / decode TPS；Module F 永不流式",
    )
    p_audit.add_argument(
        "--timeout",
        type=float,
        default=BANK_TIMEOUT_S,
        help=f"单次请求超时秒，默认 {BANK_TIMEOUT_S:.0f}；家族栏同一客户端",
    )
    _add_concurrency(p_audit)
    p_audit.set_defaults(func=_cmd_audit)

    p_shell = sub.add_parser("shell", help="附录：wrapper / 同网关 SKU / 错误信封；不进 F/I/D")
    p_shell.add_argument("--target", required=True)
    p_shell.add_argument("--out", default="out")
    p_shell.add_argument(
        "--peers",
        default=None,
        help="同网关对照 id，逗号分隔；省略则用 claimed_model（与 target 不同时）",
    )
    p_shell.add_argument(
        "--timeout",
        type=float,
        default=FAMILY_TIMEOUT_S,
        help=f"单次请求超时秒，默认 {FAMILY_TIMEOUT_S:.0f}",
    )
    p_shell.set_defaults(func=_cmd_shell)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
