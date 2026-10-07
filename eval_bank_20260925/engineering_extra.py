"""E-02..E-06 隐藏场景。题面不规定 code 的取值，只比较不同情况的 code 是否分开。"""
from __future__ import annotations

import inspect
import json
import tempfile
from pathlib import Path

from src.grade import grade_response
from src.types import Question

LEDGER = 20


def _e(op, **fields):
    return {"op": op, **fields}


def _pay(amount=10, state="PAID", eid="e", sig="ok", merchant="m", order="o"):
    return _e("CALLBACK", merchant=merchant, order=order, amount=amount, state=state, event_id=eid, signature=sig)


def _get(merchant="m", order="o"):
    return _e("GET", merchant=merchant, order=order)


def _create(amount=10, merchant="m", order="o"):
    return _e("CREATE", merchant=merchant, order=order, amount=amount)


def _fails(times):
    events = [_e("SUBMIT", tenant="a", task_id="t")]
    for index in range(times):
        events.append(_e("UPDATE", action="start", tenant="a", task_id="t", attempt=f"a{index}"))
        events.append(_e("UPDATE", action="fail", tenant="a", task_id="t", attempt=f"a{index}"))
    return events


CASES = {
    "E-02": {
        "unpaid": [_create(), _get()],
        "paid": [_create(), _pay(eid="p"), _get()],
        "badsig": [_create(), _pay(sig="bad", eid="b"), _get()],
        "badsig2": [_create(order="p"), _pay(sig="bad", eid="z", order="p"), _get(order="p")],
        "badamt": [_create(), _pay(amount=9, eid="a"), _get()],
        "replay": [_create(), _pay(eid="r"), _pay(eid="r"), _get()],
        "refund": [_create(), _pay(eid="p"), _pay(state="REFUNDED", eid="f"), _get()],
        "late": [_create(), _pay(eid="p"), _pay(state="REFUNDED", eid="f"), _pay(eid="z"), _get()],
        "partial": [_create(), _pay(eid="p"), _pay(amount=4, state="REFUNDED", eid="f"), _get()],
        "other": [_create(merchant="a"), _create(merchant="b", amount=20), _pay(amount=20, merchant="b", eid="b"), _get(merchant="a"), _get(merchant="b")],
        "missing": [_get()],
        "refund_first": [_create(), _pay(state="REFUNDED", eid="f"), _pay(eid="p"), _get()],
        "overpay": [_create(), _pay(amount=12, eid="o")],
        "surcharge_refund": [_e("CREATE", merchant="m", order="sr", amount=10, fee_rule="surcharge"), _pay(amount=11, order="sr", eid="p"), _pay(amount=11, state="REFUNDED", order="sr", eid="f"), _get(order="sr")],
        "surcharge_wrong_refund": [_e("CREATE", merchant="m", order="sw", amount=10, fee_rule="surcharge"), _pay(amount=11, order="sw", eid="p"), _pay(amount=10, state="REFUNDED", order="sw", eid="f"), _get(order="sw")],
        "legacy_signed": [_create(order="ls"), _e("CALLBACK", merchant="m", order="ls", amount=10, state="PAID", event_id="n2", signature="ok", notice_version=1), _get(order="ls")],
        "cross": [_create(merchant="a", order="o1"), _create(merchant="b", order="o1"), _pay(merchant="a", order="o1", eid="same"), _pay(merchant="b", order="o1", eid="same"), _get(merchant="b", order="o1")],
        "surcharge": [_e("CREATE", merchant="m", order="s", amount=10, fee_rule="surcharge"), _pay(amount=11, order="s", eid="s1"), _get(order="s")],
        "surcharge_short": [_e("CREATE", merchant="m", order="s", amount=10, fee_rule="surcharge"), _pay(amount=10, order="s", eid="s1"), _get(order="s")],
        "legacy_notice": [_create(order="n"), _e("CALLBACK", merchant="m", order="n", amount=10, state="PAID", event_id="n1", notice_version=1), _get(order="n")],
        "legacy_retry": [_create(order="lr"), _e("CALLBACK", merchant="m", order="lr", amount=10, state="PAID", event_id="r1", signature="ok", notice_version=1), _e("CALLBACK", merchant="m", order="lr", amount=10, state="PAID", event_id="r1", signature="ok", notice_version=2), _get(order="lr")],
        "surcharge_legacy": [_e("CREATE", merchant="m", order="sl", amount=10, fee_rule="surcharge"), _e("CALLBACK", merchant="m", order="sl", amount=11, state="PAID", event_id="sl1", signature="ok", notice_version=1)],
    },
    "E-03": {
        "stocked": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("GET", tenant="a", sku="s")],
        "reserved": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "retry": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "too_many": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=9, reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "expire_held": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("EXPIRE", tenant="a", sku="s", reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "expire_sold": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("CONFIRM", tenant="a", sku="s", reservation_id="r"), _e("EXPIRE", tenant="a", sku="s", reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "release_held": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("RELEASE", tenant="a", sku="s", reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "release_sold": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("CONFIRM", tenant="a", sku="s", reservation_id="r"), _e("RELEASE", tenant="a", sku="s", reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "other_tenant": [_e("STOCK", tenant="a", sku="s", quantity=2), _e("STOCK", tenant="b", sku="s", quantity=4), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("GET", tenant="b", sku="s")],
        "two_holds": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r1"), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r2"), _e("GET", tenant="a", sku="s")],
        "negative_qty": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=-3, reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "zero_then": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=0, reservation_id="r"), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "other_sku": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("STOCK", tenant="a", sku="t", quantity=1), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("GET", tenant="a", sku="t")],
        "double_expire": [_e("STOCK", tenant="a", sku="s", quantity=5), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r"), _e("EXPIRE", tenant="a", sku="s", reservation_id="r"), _e("EXPIRE", tenant="a", sku="s", reservation_id="r"), _e("GET", tenant="a", sku="s")],
        "confirm_missing": [_e("CONFIRM", tenant="a", sku="s", reservation_id="nope")],
        "holdback_new": [_e("STOCK", tenant="a", sku="s", quantity=4, pool="holdback", batch="new"), _e("GET", tenant="a", sku="s", buyer="new", now=0)],
        "holdback_back": [_e("STOCK", tenant="a", sku="s", quantity=4, pool="holdback", batch="new"), _e("GET", tenant="a", sku="s", buyer="returning", now=0)],
        "expired": [_e("STOCK", tenant="a", sku="s", quantity=5, pool="open", batch="old", expire_at=10), _e("GET", tenant="a", sku="s", buyer="new", now=11)],
        "fresh": [_e("STOCK", tenant="a", sku="s", quantity=4, pool="open", batch="new", expire_at=10), _e("GET", tenant="a", sku="s", buyer="new", now=11)],
        "reject_hold": [_e("STOCK", tenant="a", sku="s", quantity=4, pool="holdback", batch="new"), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r", buyer="new", now=0)],
        "take_hold": [_e("STOCK", tenant="a", sku="s", quantity=4, pool="holdback", batch="new"), _e("RESERVE", tenant="a", sku="s", quantity=2, reservation_id="r", buyer="returning", now=0), _e("GET", tenant="a", sku="s", buyer="returning", now=0), _e("GET", tenant="a", sku="s", buyer="new", now=0)],
        "expired_reserve": [_e("STOCK", tenant="a", sku="s", quantity=5, pool="open", batch="old", expire_at=10), _e("RESERVE", tenant="a", sku="s", quantity=1, reservation_id="r", buyer="new", now=11)],
    },
    "E-04": {
        "visible": [_e("PUT", tenant="a", doc_id="d", content="note"), _e("READ", tenant="a", doc_id="d")],
        "missing": [_e("READ", tenant="a", doc_id="missing")],
        "erased": [_e("PUT", tenant="a", doc_id="d", content="secret"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d")],
        "ledger": [_e("PUT", tenant="a", doc_id="d", content="bill", amount=7), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "no_charge": [_e("PUT", tenant="a", doc_id="d", content="x"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "repeat": [_e("PUT", tenant="a", doc_id="d", content="x"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d")],
        "other_tenant": [_e("PUT", tenant="a", doc_id="d", content="a-secret"), _e("PUT", tenant="b", doc_id="d", content="b-secret"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="b", doc_id="d")],
        "sum": [_e("PUT", tenant="a", doc_id="d", content="x", amount=4), _e("PUT", tenant="a", doc_id="d", content="x", amount=1), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "clean": [_e("PUT", tenant="a", doc_id="d", content="private", amount=3), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "charge_after": [_e("PUT", tenant="a", doc_id="d", content="x", amount=6), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("READ", tenant="a", doc_id="d", role="user"), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "other_doc": [_e("PUT", tenant="a", doc_id="d1", content="x"), _e("PUT", tenant="a", doc_id="d2", content="y"), _e("ERASE", tenant="a", doc_id="d1", request_id="same"), _e("ERASE", tenant="a", doc_id="d2", request_id="same"), _e("READ", tenant="a", doc_id="d2")],
        "tombstone": [_e("PUT", tenant="a", doc_id="d", content="x"), _e("ERASE", tenant="a", doc_id="d", request_id="e1"), _e("PUT", tenant="a", doc_id="d", content="y"), _e("READ", tenant="a", doc_id="d")],
        "negative_fee": [_e("PUT", tenant="a", doc_id="d", content="x", amount=7), _e("PUT", tenant="a", doc_id="d", content="x", amount=-3), _e("READ", tenant="a", doc_id="d", role="auditor")],
        "other_request": [_e("PUT", tenant="b", doc_id="d", content="x"), _e("ERASE", tenant="a", doc_id="z", request_id="same"), _e("ERASE", tenant="b", doc_id="d", request_id="same"), _e("READ", tenant="b", doc_id="d")],
        "two_reads": [_e("PUT", tenant="a", doc_id="d", content="x"), _e("READ", tenant="a", doc_id="d"), _e("READ", tenant="a", doc_id="d")],
    },
    "E-05": {
        "queued": [_e("SUBMIT", tenant="a", task_id="t"), _e("GET", tenant="a", task_id="t")],
        "running": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("GET", tenant="a", task_id="t")],
        "succeeded": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="a1"), _e("GET", tenant="a", task_id="t")],
        "twice": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="a1"), _e("GET", tenant="a", task_id="t")],
        "cancel": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="cancel", tenant="a", task_id="t"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="a1"), _e("GET", tenant="a", task_id="t")],
        "dependency": [_e("SUBMIT", tenant="a", task_id="a"), _e("SUBMIT", tenant="a", task_id="b", depends_on="a"), _e("UPDATE", action="start", tenant="a", task_id="b", attempt="b1"), _e("GET", tenant="a", task_id="b")],
        "stale": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="zz"), _e("GET", tenant="a", task_id="t")],
        "retry_ok": _fails(1) + [_e("UPDATE", action="start", tenant="a", task_id="t", attempt="b"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="b"), _e("GET", tenant="a", task_id="t")],
        "retry_stop": _fails(6) + [_e("UPDATE", action="start", tenant="a", task_id="t", attempt="late"), _e("GET", tenant="a", task_id="t")],
        "other_tenant": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("SUBMIT", tenant="z", task_id="t"), _e("UPDATE", action="start", tenant="z", task_id="t", attempt="z1"), _e("GET", tenant="z", task_id="t")],
        "fail_late": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="fail", tenant="a", task_id="t", attempt="a1"), _e("GET", tenant="a", task_id="t")],
        "unknown": [_e("GET", tenant="a", task_id="missing")],
        "dep_ready": [_e("SUBMIT", tenant="a", task_id="a"), _e("UPDATE", action="start", tenant="a", task_id="a", attempt="a1"), _e("UPDATE", action="complete", tenant="a", task_id="a", attempt="a1"), _e("SUBMIT", tenant="a", task_id="b", depends_on="a"), _e("UPDATE", action="start", tenant="a", task_id="b", attempt="b1"), _e("GET", tenant="a", task_id="b")],
        "start_busy": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a2")],
        "fail_same": [_e("SUBMIT", tenant="a", task_id="t"), _e("UPDATE", action="start", tenant="a", task_id="t", attempt="a1"), _e("UPDATE", action="fail", tenant="a", task_id="t", attempt="a1"), _e("SUBMIT", tenant="a", task_id="u"), _e("UPDATE", action="start", tenant="a", task_id="u", attempt="u1"), _e("UPDATE", action="fail", tenant="a", task_id="u", attempt="u1")],
    },
    "E-06": {
        "empty": [_e("READ", env="prod", key="k")],
        "unapproved": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x"), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "published": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "rollback": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("PROPOSE", env="prod", key="k", version=2, value="b", request_id="y", approved=True), _e("PUBLISH", env="prod", key="k", version=2), _e("PUBLISH", env="prod", key="k", rollback_to=1), _e("READ", env="prod", key="k")],
        "environment": [_e("PROPOSE", env="staging", key="k", version=1, value="s", request_id="s1", approved=True), _e("PUBLISH", env="staging", key="k", version=1), _e("READ", env="prod", key="k")],
        "same_request": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PROPOSE", env="prod", key="k", version=1, value="b", request_id="x"), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "rollback_missing": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("PUBLISH", env="prod", key="k", rollback_to=9), _e("READ", env="prod", key="k")],
        "approve_flag": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=False), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "other_key": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="other")],
        "unpublished": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("READ", env="prod", key="k")],
        "reject_then_yes": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=False), _e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="y", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "string_false": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved="false"), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "forward": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("PROPOSE", env="prod", key="k", version=2, value="b", request_id="y", approved=True), _e("PUBLISH", env="prod", key="k", version=2), _e("PUBLISH", env="prod", key="k", rollback_to=1), _e("PUBLISH", env="prod", key="k", version=2), _e("READ", env="prod", key="k")],
        "request_env": [_e("PROPOSE", env="staging", key="k", version=1, value="s", request_id="x"), _e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k")],
        "two_reads": [_e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True), _e("PUBLISH", env="prod", key="k", version=1), _e("READ", env="prod", key="k"), _e("READ", env="prod", key="k")],
        "hold_ship": [
            _e("PROPOSE", env="prod", key="k", version=1, value="a", request_id="x", approved=True),
            _e("PUBLISH", env="prod", key="k", version=1),
            _e("PROPOSE", env="prod", key="k", version=2, value="b", request_id="y", approved=False),
            _e("PUBLISH", env="prod", key="k", version=2),
            _e("PROPOSE", env="prod", key="k", version=2, value="b", request_id="z", approved=True),
            _e("PUBLISH", env="prod", key="k", version=2),
            _e("PUBLISH", env="prod", key="k", rollback_to=1),
            _e("PUBLISH", env="prod", key="k", version=2),
            _e("READ", env="prod", key="k"),
        ],
    },
}

# (name, left spec, right spec, same, mode). spec 是 [case, index, field] 或 ["lit", value]。
PAIRS = {
    "E-02": [
        ["pay_vs_unpaid", ["paid", 2, "code"], ["unpaid", 1, "code"], False, "eq"],
        ["refund_vs_paid", ["refund", 3, "code"], ["paid", 2, "code"], False, "eq"],
        ["surcharge_vs_flat", ["surcharge", 2, "code"], ["paid", 2, "code"], False, "eq"],
        ["badsig_vs_paid", ["badsig", 2, "code"], ["paid", 2, "code"], False, "eq"],
        ["badsig_cb", ["badsig", 1, "code"], ["paid", 1, "code"], False, "eq"],
        ["badsig_stable", ["badsig", 1, "code"], ["badsig2", 1, "code"], True, "eq"],
        ["legacy_cb_vs_pay", ["legacy_notice", 1, "code"], ["paid", 1, "code"], False, "eq"],
        ["legacy_signed_cb", ["legacy_signed", 1, "code"], ["badsig", 1, "code"], False, "eq"],
        ["surcharge_cb", ["surcharge", 1, "code"], ["badamt", 1, "code"], False, "eq"],
        ["surcharge_short_cb", ["surcharge_short", 1, "code"], ["paid", 1, "code"], False, "eq"],
        ["legacy_retry", ["legacy_retry", 2, "code"], ["paid", 1, "code"], True, "eq"],
        ["ver_before_fee", ["surcharge_legacy", 1, "code"], ["badamt", 1, "code"], False, "eq"],
        ["cross_cb", ["cross", 3, "code"], ["replay", 2, "code"], False, "eq"],
        ["replay_cb", ["replay", 2, "code"], ["replay", 1, "code"], False, "eq"],
        ["partial_cb", ["partial", 2, "code"], ["refund", 2, "code"], False, "eq"],
        ["amt_cb_vs_badsig", ["badamt", 1, "code"], ["badsig", 1, "code"], False, "eq"],
        ["missing_vs_unpaid", ["missing", 0, "code"], ["unpaid", 1, "code"], False, "eq"],
        ["refund_cb", ["refund", 2, "code"], ["paid", 1, "code"], False, "eq"],
        ["late_cb", ["late", 3, "code"], ["paid", 1, "code"], False, "eq"],
        ["refund_first_cb", ["refund_first", 1, "code"], ["refund", 2, "code"], False, "eq"],
    ],
    "E-03": [
        ["stock_5", ["stocked", 1, "available"], ["lit", 5], True, "eq"],
        ["reserved_3", ["reserved", 2, "available"], ["lit", 3], True, "eq"],
        ["retry_3", ["retry", 3, "available"], ["lit", 3], True, "eq"],
        ["retry_code", ["retry", 2, "code"], ["retry", 1, "code"], False, "eq"],
        ["too_many_5", ["too_many", 2, "available"], ["lit", 5], True, "eq"],
        ["too_many_code", ["too_many", 1, "code"], ["reserved", 1, "code"], False, "eq"],
        ["other_tenant_4", ["other_tenant", 3, "available"], ["lit", 4], True, "eq"],
        ["negative_5", ["negative_qty", 2, "available"], ["lit", 5], True, "eq"],
        ["zero_then_3", ["zero_then", 3, "available"], ["lit", 3], True, "eq"],
        ["other_sku_1", ["other_sku", 3, "available"], ["lit", 1], True, "eq"],
        ["two_holds_1", ["two_holds", 3, "available"], ["lit", 1], True, "eq"],
        ["holdback_hidden", ["holdback_new", 1, "available"], ["lit", 0], True, "eq"],
        ["holdback_seen", ["holdback_back", 1, "available"], ["lit", 4], True, "eq"],
        ["expired_old", ["expired", 1, "available"], ["lit", 0], True, "eq"],
        ["fresh_batch", ["fresh", 1, "available"], ["lit", 4], True, "eq"],
        ["new_cannot_hold", ["reject_hold", 1, "code"], ["reserved", 1, "code"], False, "eq"],
        ["returning_takes", ["take_hold", 2, "available"], ["lit", 2], True, "eq"],
        ["expired_vs_oversell", ["expired_reserve", 1, "code"], ["too_many", 1, "code"], False, "eq"],
        ["hold_left_for_new", ["take_hold", 3, "available"], ["lit", 0], True, "eq"],
        ["stock_vs_reserve_code", ["stocked", 1, "code"], ["reserved", 1, "code"], False, "eq"],
    ],
    "E-04": [
        ["seen_vs_missing", ["visible", 1, "code"], ["missing", 0, "code"], False, "eq"],
        ["erased_vs_missing", ["erased", 2, "code"], ["missing", 0, "code"], False, "eq"],
        ["ledger_7", ["ledger", 2, "amount"], ["lit", 7], True, "eq"],
        ["ledger_code", ["ledger", 2, "code"], ["no_charge", 2, "code"], False, "eq"],
        ["no_amount", ["no_charge", 2, "has_amount"], ["lit", "no"], True, "eq"],
        ["repeat_code", ["repeat", 2, "code"], ["repeat", 1, "code"], False, "eq"],
        ["repeat_gone", ["repeat", 3, "code"], ["erased", 2, "code"], True, "eq"],
        ["other_visible", ["other_tenant", 3, "code"], ["visible", 1, "code"], True, "eq"],
        ["sum_5", ["sum", 3, "amount"], ["lit", 5], True, "eq"],
        ["clean", ["clean", 1, "blob"], ["lit", "private"], False, "contains"],
        ["charge_after_6", ["charge_after", 3, "amount"], ["lit", 6], True, "eq"],
        ["other_doc_gone", ["other_doc", 4, "code"], ["erased", 2, "code"], True, "eq"],
        ["tombstone", ["tombstone", 3, "code"], ["erased", 2, "code"], True, "eq"],
        ["negative_ignored", ["negative_fee", 2, "amount"], ["lit", 7], True, "eq"],
        ["reads_stable", ["two_reads", 2, "code"], ["two_reads", 1, "code"], True, "eq"],
        ["other_request_gone", ["other_request", 3, "code"], ["erased", 2, "code"], True, "eq"],
        ["tombstone_put", ["tombstone", 2, "code"], ["visible", 0, "code"], False, "eq"],
        ["charge_after_gone", ["charge_after", 2, "code"], ["erased", 2, "code"], True, "eq"],
        ["ledger_has_amount", ["ledger", 2, "has_amount"], ["lit", "yes"], True, "eq"],
        ["erased_cb", ["erased", 1, "code"], ["visible", 0, "code"], False, "eq"],
    ],
    "E-05": [
        ["queue_vs_run", ["queued", 1, "code"], ["running", 2, "code"], False, "eq"],
        ["run_vs_done", ["running", 2, "code"], ["succeeded", 3, "code"], False, "eq"],
        ["twice_get", ["twice", 4, "code"], ["succeeded", 3, "code"], True, "eq"],
        ["twice_cb", ["twice", 3, "code"], ["twice", 2, "code"], False, "eq"],
        ["cancel_get", ["cancel", 4, "code"], ["succeeded", 3, "code"], False, "eq"],
        ["dep_block", ["dependency", 2, "code"], ["running", 1, "code"], False, "eq"],
        ["stale_cb", ["stale", 2, "code"], ["succeeded", 2, "code"], False, "eq"],
        ["stale_still", ["stale", 3, "code"], ["running", 2, "code"], True, "eq"],
        ["retry_ok", ["retry_ok", -1, "code"], ["succeeded", 3, "code"], True, "eq"],
        ["retry_stop", ["retry_stop", -2, "code"], ["running", 1, "code"], False, "eq"],
        ["retry_not_done", ["retry_stop", -1, "code"], ["succeeded", 3, "code"], False, "eq"],
        ["other_runs", ["other_tenant", 4, "code"], ["running", 2, "code"], True, "eq"],
        ["fail_late", ["fail_late", 4, "code"], ["succeeded", 3, "code"], True, "eq"],
        ["unknown", ["unknown", 0, "code"], ["queued", 1, "code"], False, "eq"],
        ["dep_ready", ["dep_ready", 5, "code"], ["running", 2, "code"], True, "eq"],
        ["busy_code", ["start_busy", 2, "code"], ["running", 1, "code"], False, "eq"],
        ["fail_stable", ["fail_same", 2, "code"], ["fail_same", 5, "code"], True, "eq"],
        ["retry_start", ["retry_ok", 3, "code"], ["running", 1, "code"], True, "eq"],
        ["submit_vs_get", ["queued", 0, "code"], ["queued", 1, "code"], False, "eq"],
        ["cancel_cb", ["cancel", 2, "code"], ["succeeded", 2, "code"], False, "eq"],
    ],
    "E-06": [
        ["empty_vs_live", ["empty", 0, "code"], ["published", 2, "code"], False, "eq"],
        ["unapproved_cb", ["unapproved", 1, "code"], ["published", 1, "code"], False, "eq"],
        ["unapproved_read", ["unapproved", 2, "code"], ["empty", 0, "code"], True, "eq"],
        ["value_a", ["published", 2, "value"], ["lit", "a"], True, "eq"],
        ["rollback_a", ["rollback", 5, "value"], ["lit", "a"], True, "eq"],
        ["env_empty", ["environment", 2, "code"], ["empty", 0, "code"], True, "eq"],
        ["same_request_a", ["same_request", 3, "value"], ["lit", "a"], True, "eq"],
        ["rollback_keeps", ["rollback_missing", 3, "value"], ["lit", "a"], True, "eq"],
        ["rollback_codes", ["rollback_missing", 2, "code"], ["rollback", 4, "code"], False, "eq"],
        ["hold_ship", ["hold_ship", 8, "value"], ["lit", "b"], True, "eq"],
        ["other_key", ["other_key", 2, "code"], ["empty", 0, "code"], True, "eq"],
        ["unpublished", ["unpublished", 1, "code"], ["empty", 0, "code"], True, "eq"],
        ["reject_then_yes", ["reject_then_yes", 3, "code"], ["empty", 0, "code"], False, "eq"],
        ["string_false", ["string_false", 2, "code"], ["empty", 0, "code"], True, "eq"],
        ["forward_b", ["forward", 6, "value"], ["lit", "b"], True, "eq"],
        ["request_cross", ["request_env", 3, "code"], ["empty", 0, "code"], False, "eq"],
        ["approved_vs_flag", ["published", 0, "code"], ["approve_flag", 0, "code"], False, "eq"],
        ["published_has_value", ["published", 2, "has_value"], ["lit", "yes"], True, "eq"],
        ["empty_no_value", ["empty", 0, "has_value"], ["lit", "no"], True, "eq"],
        ["omitted_vs_yes", ["unapproved", 0, "code"], ["published", 0, "code"], False, "eq"],
    ],
}


def _cell(runs, spec):
    if spec[0] == "lit":
        return spec[1]
    name, index, field = spec
    rows = runs.get(name)
    if not isinstance(rows, list):
        return None
    if field == "blob":
        if index < 0:
            index += len(rows)
        if index < 0 or index >= len(rows):
            return None
        return json.dumps(rows[index], ensure_ascii=False, default=str)
    if index < 0:
        index += len(rows)
    if index < 0 or index >= len(rows) or not isinstance(rows[index], dict):
        return None
    row = rows[index]
    if field in {"has_amount", "has_value"}:
        key = "amount" if field == "has_amount" else "value"
        return "yes" if key in row else "no"
    return row.get(field)


def judge_item(item_id, runs):
    def observed(spec):
        """工程题的 code 关系同时约束 reason；缺任一观测都保持空缺语义。"""
        value = _cell(runs, spec)
        if spec[0] == "lit" or spec[2] != "code":
            return value
        reason = _cell(runs, [spec[0], spec[1], "reason"])
        if value is None or reason is None:
            return None
        return value, reason

    def relation(got, want, same, mode):
        if got is None or want is None:
            return None
        if isinstance(got, tuple) and isinstance(want, tuple):
            if mode != "eq":
                raise ValueError("code_reason_contains_unsupported")
            # A negative relation applies to the combined observable pair:
            # changing either code or reason is enough to make the outcome distinct.
            return (got == want) if same else (got != want)
        if mode == "contains":
            return (str(want) in str(got)) if same else (str(want) not in str(got))
        return (got == want) if same else (got != want)

    covered, gaps, violations = [], [], []
    for name, left, right, same, mode in PAIRS[item_id]:
        got, want = observed(left), observed(right)
        if got is None or want is None:
            gaps.append(name)
            continue
        ok = relation(got, want, same, mode)
        if ok:
            covered.append(name)
        else:
            violations.append("deduct_" + name)
    return {"covered": covered, "gaps": gaps, "violations": violations}


def _pack(code, **extra):
    row = {"code": code, "reason": code}
    row.update(extra)
    return row


REFS = {
"E-02": '''def solve(events):
    orders, seen, out = {}, {}, []
    def pack(code):
        return {"code": code, "reason": code}
    for e in events:
        op, key = e.get("op"), (e.get("merchant"), e.get("order"))
        if op == "CREATE":
            if key in orders:
                out.append(pack("exists"))
            else:
                orders[key] = {"state": "pending", "amount": e.get("amount"), "fee": e.get("fee_rule") or "flat"}
                out.append(pack("created"))
        elif op == "CALLBACK":
            order, eid = orders.get(key), e.get("event_id")
            bag = seen.setdefault(key, set())
            due = None if order is None else (order["amount"] if order["fee"] != "surcharge" else order["amount"] + order["amount"] // 10)
            if order is None:
                out.append(pack("missing"))
            elif e.get("notice_version") == 1:
                out.append(pack("legacy_notice"))
            elif e.get("signature") != "ok":
                out.append(pack("bad_signature"))
            elif eid in bag:
                out.append(pack("duplicate"))
            elif e.get("amount") != due:
                bag.add(eid)
                out.append(pack("bad_amount"))
            elif e.get("state") == "PAID" and order["state"] == "pending":
                bag.add(eid)
                order["state"] = "paid"
                out.append(pack("accepted"))
            elif e.get("state") == "REFUNDED" and order["state"] == "paid":
                bag.add(eid)
                order["state"] = "refunded"
                out.append(pack("refunded"))
            else:
                bag.add(eid)
                out.append(pack("ignored"))
        elif op == "GET":
            order = orders.get(key)
            label = "missing" if order is None else ("paid_" + order["fee"] if order["state"] == "paid" else order["state"])
            out.append(pack(label))
        else:
            out.append(pack("ignored"))
    return out''',
"E-03": '''def solve(events):
    lots, holds, out = [], {}, []
    def pack(code, **extra):
        row = {"code": code, "reason": code}
        row.update(extra)
        return row
    def visible(lot, buyer, now):
        if lot["batch"] == "old" and lot["expire_at"] is not None and now > lot["expire_at"]:
            return False
        if lot["pool"] == "holdback" and buyer != "returning":
            return False
        return True
    def avail(tenant, sku, buyer, now):
        return sum(lot["qty"] for lot in lots if lot["tenant"] == tenant and lot["sku"] == sku and visible(lot, buyer, now))
    for e in events:
        op, rid = e.get("op"), e.get("reservation_id")
        tenant, sku = e.get("tenant"), e.get("sku")
        buyer, now = e.get("buyer", "new"), e.get("now", 0)
        qty = e.get("quantity", 0)
        if op == "STOCK":
            if isinstance(qty, int) and qty > 0:
                lots.append({"tenant": tenant, "sku": sku, "pool": e.get("pool", "open"), "batch": e.get("batch", "new"), "qty": qty, "expire_at": e.get("expire_at")})
            out.append(pack("stocked"))
        elif op == "RESERVE":
            if not isinstance(qty, int) or qty <= 0:
                out.append(pack("rejected"))
            elif rid in holds:
                out.append(pack("duplicate"))
            elif avail(tenant, sku, buyer, now) < qty:
                blocked = [lot for lot in lots if lot["tenant"] == tenant and lot["sku"] == sku and lot["qty"] >= qty]
                expired = any(lot["batch"] == "old" and lot["expire_at"] is not None and now > lot["expire_at"] for lot in blocked)
                out.append(pack("expired" if expired else "rejected"))
            else:
                left = qty
                for lot in lots:
                    if left <= 0:
                        break
                    if lot["tenant"] == tenant and lot["sku"] == sku and visible(lot, buyer, now) and lot["qty"] > 0:
                        take = min(lot["qty"], left)
                        lot["qty"] -= take
                        left -= take
                holds[rid] = True
                out.append(pack("reserved"))
        elif op == "GET":
            out.append(pack("available", available=avail(tenant, sku, buyer, now)))
        else:
            out.append(pack("ignored"))
    return out''',
"E-04": '''def solve(events):
    docs, tomb, ledger, seen, out = {}, set(), {}, set(), []
    def pack(code, **extra):
        row = {"code": code, "reason": code}
        row.update(extra)
        return row
    for e in events:
        op, key = e.get("op"), (e.get("tenant"), e.get("doc_id"))
        if op == "PUT":
            if key in tomb:
                out.append(pack("rejected"))
            else:
                docs[key] = e.get("content")
                amount = e.get("amount", 0)
                if isinstance(amount, int) and amount > 0:
                    ledger[key] = ledger.get(key, 0) + amount
                out.append(pack("written"))
        elif op == "ERASE":
            mark = (key, e.get("request_id"))
            if mark in seen:
                out.append(pack("duplicate"))
            else:
                seen.add(mark)
                docs.pop(key, None)
                tomb.add(key)
                out.append(pack("erased"))
        elif op == "CHARGE":
            amount = e.get("amount", 0)
            if isinstance(amount, int) and amount > 0:
                ledger[key] = ledger.get(key, 0) + amount
                out.append(pack("charged"))
            else:
                out.append(pack("rejected"))
        elif op == "READ":
            if e.get("role") == "auditor":
                if key in ledger:
                    out.append(pack("ledger", amount=ledger[key]))
                else:
                    out.append(pack("no_ledger"))
            elif key in docs:
                out.append(pack("visible"))
            elif key in tomb:
                out.append(pack("gone"))
            else:
                out.append(pack("absent"))
        elif op == "AUDIT":
            if key in ledger:
                out.append(pack("ledger", amount=ledger[key]))
            else:
                out.append(pack("no_ledger"))
        else:
            out.append(pack("ignored"))
    return out''',
"E-05": '''def solve(events):
    tasks, out = {}, []
    def pack(code):
        return {"code": code, "reason": code}
    for e in events:
        op, key = e.get("op"), (e.get("tenant"), e.get("task_id"))
        if op == "UPDATE":
            op = {"start": "START", "complete": "COMPLETE", "fail": "FAIL", "cancel": "CANCEL"}.get(e.get("action"), "")
        if op == "SUBMIT" and key not in tasks:
            tasks[key] = {"state": "queued", "fails": 0, "dep": e.get("depends_on"), "attempt": None}
            out.append(pack("submitted"))
            continue
        task = tasks.get(key)
        if op == "GET":
            out.append(pack("not_found" if task is None else task["state"]))
            continue
        if task is None:
            out.append(pack("not_found"))
            continue
        if op == "START":
            attempt = e.get("attempt")
            dep = tasks.get((e.get("tenant"), task["dep"])) if task.get("dep") else None
            if task["state"] == "running":
                out.append(pack("busy"))
            elif task["state"] in {"canceled", "succeeded"} or task["fails"] >= 4:
                out.append(pack("rejected"))
            elif dep is not None and dep["state"] != "succeeded":
                out.append(pack("blocked"))
            elif attempt and attempt != task.get("attempt"):
                task["state"], task["attempt"] = "running", attempt
                out.append(pack("started"))
            else:
                out.append(pack("rejected"))
        elif op == "COMPLETE":
            if task["state"] == "running" and e.get("attempt") == task.get("attempt"):
                task["state"] = "succeeded"
                out.append(pack("completed"))
            else:
                out.append(pack("stale"))
        elif op == "FAIL":
            if task["state"] == "running" and e.get("attempt") == task.get("attempt"):
                task["fails"] += 1
                task["state"] = "failed"
                out.append(pack("failed"))
            else:
                out.append(pack("stale"))
        elif op == "CANCEL" and task["state"] in {"queued", "running"}:
            task["state"] = "canceled"
            out.append(pack("canceled"))
        else:
            out.append(pack("ignored"))
    return out''',
"E-06": '''def solve(events):
    proposed, seen, approved, published, current, out = {}, set(), {}, {}, {}, []
    def pack(code, **extra):
        row = {"code": code, "reason": code}
        row.update(extra)
        return row
    for e in events:
        op = e.get("op")
        env, key, version = e.get("env"), e.get("key"), e.get("version")
        ident = (env, key, version)
        if op == "PROPOSE":
            rid = e.get("request_id")
            scope = (env, key, rid)
            if rid is not None and scope in seen:
                out.append(pack("duplicate"))
                continue
            if rid is not None:
                seen.add(scope)
            if ident not in proposed and ident not in approved:
                proposed[ident] = e.get("value")
            if e.get("approved") is True and ident in proposed:
                approved[ident] = proposed[ident]
                out.append(pack("approved"))
            elif "approved" in e and e.get("approved") is not True:
                out.append(pack("rejected"))
            else:
                out.append(pack("proposed"))
        elif op == "APPROVE":
            if e.get("approved") is True and ident in proposed and ident not in approved:
                approved[ident] = proposed[ident]
                out.append(pack("approved"))
            elif e.get("approved") is True and ident in approved:
                out.append(pack("approved"))
            else:
                out.append(pack("rejected"))
        elif op == "PUBLISH" and e.get("rollback_to") is not None:
            target = e.get("rollback_to")
            if target in published.get((env, key), []):
                current[(env, key)] = target
                out.append(pack("rolled_back"))
            else:
                out.append(pack("rejected"))
        elif op == "PUBLISH":
            if ident in approved:
                current[(env, key)] = version
                published.setdefault((env, key), [])
                if version not in published[(env, key)]:
                    published[(env, key)].append(version)
                out.append(pack("published"))
            else:
                out.append(pack("rejected"))
        elif op == "ROLLBACK":
            if version in published.get((env, key), []):
                current[(env, key)] = version
                out.append(pack("rolled_back"))
            else:
                out.append(pack("rejected"))
        elif op == "READ":
            live = current.get((env, key))
            if live is None:
                out.append(pack("empty"))
            else:
                out.append(pack("live", value=approved[(env, key, live)]))
        else:
            out.append(pack("ignored"))
    return out''',
}


def extra_fixture(marker, item_id):
    source = inspect.getsource(_cell) + "\n" + inspect.getsource(judge_item)
    cases = json.dumps({item_id: CASES[item_id]}, ensure_ascii=False, separators=(",", ":"))
    pairs = json.dumps({item_id: PAIRS[item_id]}, ensure_ascii=False, separators=(",", ":"))
    return f'''import contextlib, copy, io, json
CASES = json.loads({cases!r})
PAIRS = json.loads({pairs!r})
{source}
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
runs = {{}}
for name, events in CASES[{item_id!r}].items():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            runs[name] = solve(copy.deepcopy(events))
    except BaseException:
        runs[name] = None
verdict = judge_item({item_id!r}, runs)
print({marker!r} + " POINTS " + str(len(verdict["covered"])) + "/20")
print({marker!r} + " ENGINEERING " + json.dumps(verdict, ensure_ascii=False))
'''


def score_extra(item_id, text):
    marker = "__MODEL_LENS_" + item_id.replace("-", "") + "_"
    with tempfile.TemporaryDirectory(prefix="engineering-extra-") as directory:
        root = Path(directory)
        tests = root / "bank" / "tests"
        tests.mkdir(parents=True)
        (tests / "tests.py").write_text(extra_fixture(marker, item_id), encoding="utf-8")
        question = Question(
            id=item_id, domain="engineering", difficulty="extreme", prompt="",
            grader={"type": "code_tests", "language": "python", "tests_file": "bank/tests/tests.py", "result_marker": marker},
            pass_criteria="20 positive obligations and no negative debt", language="python",
        )
        grade = grade_response(question, text, repo_root=root)
    from .evaluation import unjudged_execution
    unavailable = unjudged_execution(grade)
    if unavailable is not None:
        return unavailable
    line = next((item for item in grade.detail.splitlines() if item.startswith("ENGINEERING ")), "")
    try:
        report = json.loads(line[len("ENGINEERING "):])
    except (ValueError, TypeError):
        report = {"covered": [], "violations": [], "unobserved": ["execution_error"]}
    covered = sorted(set(report.get("covered", [])))
    violations = sorted(set(report.get("violations", [])))
    positive, negative = len(covered), len(violations)
    return {
        "status": "pass" if positive == LEDGER and negative == 0 else "fail",
        "passed": positive == LEDGER and negative == 0,
        "obligations": {"covered": positive, "total": LEDGER, "gap": LEDGER - positive, "unobserved": len(report.get("unobserved", []))},
        "obligations_covered": covered,
        "obligations_total": LEDGER,
        "prohibitions_total": LEDGER,
        "risk_debt": {"critical": 0, "high": 0, "medium": negative, "weighted_points": negative},
        "points": positive - negative,
        "reason_code": "ok" if positive == LEDGER and negative == 0 else "content_mismatch",
        "positive_points": positive,
        "negative_points": negative,
        "net_points": positive - negative,
        "prohibitions_triggered": violations,
        "reports": report.get("reports", []),
    }
