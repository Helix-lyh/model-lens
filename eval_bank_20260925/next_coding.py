"""Executable 20261008 coding bank (CP-09..CP-18).

Each item owns a deterministic reference behaviour and five fixture groups.  The
runner remains language agnostic: model answers are executed in the existing
Python/Go/TypeScript sandboxes and compared with the same JSON fixtures.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import secrets
import tempfile
from pathlib import Path
from typing import Any

from .challenge import Challenge
from .cases import Case
from .describe_contract import is_coding_envelope
from .score import Score
from src.grade import grade_response
from src.types import Question


def _envelope(trace, output):
    return {"trace": list(trace), "output": output}


# 题面把这些词规定成了某次事件的结果。其余 trace 词只要求落在公共词表里。
_BOUND_TRACE = {"CP-09": frozenset({"DUP", "MISSING"})}

# 题面点名的输出枚举。oracle 自造、题面没写的状态词放在 _FREE_STATE。
_NAMED_STATE = {
    "CP-09": frozenset({"RESERVED", "COMMITTED", "RELEASED"}),
    "CP-10": frozenset({"OFFERED", "ACCEPTED", "CANCELLED"}),
    "CP-12": frozenset({"MISSING"}),
    "CP-13": frozenset({"HELD", "CAPTURED", "RELEASED", "VOIDED"}),
    "CP-14": frozenset({"ALLOCATED", "SHIPPED", "CANCELLED"}),
    "CP-15": frozenset({"AUTO", "PENDING", "APPROVED", "REJECTED"}),
    "CP-18": frozenset({"CHANGED"}),
}
_FREE_STATE = {"CP-18": frozenset({"ACTIVE", "REFUNDED"})}


def _trace_follows_prompt(item_id, got, expected):
    from .describe_contract import CODING_TRACE
    if not isinstance(got, list) or len(got) != len(expected):
        return False
    if any(not isinstance(item, str) or item not in CODING_TRACE for item in got):
        return False
    bound = _BOUND_TRACE.get(item_id, frozenset())
    return all(got_item == expected_item for got_item, expected_item in zip(got, expected) if expected_item in bound)


def _output_follows_prompt(item_id, got, expected):
    named = _NAMED_STATE.get(item_id, frozenset())
    free = _FREE_STATE.get(item_id, frozenset())
    if isinstance(expected, str):
        if expected in named:
            return got == expected
        if expected in free:
            return isinstance(got, str) and got not in named
        return got == expected
    if type(got) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(got) == set(expected) and all(_output_follows_prompt(item_id, got[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(got) == len(expected) and all(_output_follows_prompt(item_id, a, b) for a, b in zip(got, expected))
    return got == expected


def contract_equal(item_id, got, expected):
    """Strict where the prompt is strict. Otherwise compare the interface result."""
    from .describe_contract import is_coding_envelope
    if not is_coding_envelope(got) or not is_coding_envelope(expected):
        return False
    return _trace_follows_prompt(item_id, got["trace"], expected["trace"]) and _output_follows_prompt(item_id, got["output"], expected["output"])


def _dups(events):
    seen = set()
    for e in events:
        i = e.get("id")
        if i in seen:
            yield e, True
        else:
            seen.add(i); yield e, False


def cp09(data):
    quota = deepcopy(data.get("quota", {})); orders = {}; used = set(); snapshots = []; trace = []
    for event, duplicate in _dups(data.get("events", [])):
        ident = event.get("id")
        if duplicate or ident in used:
            trace.append("DUP"); continue
        used.add(ident); op = event.get("op")
        if op == "RESERVE":
            merged = {}
            for resource, quantity in event.get("lines", []): merged[resource] = merged.get(resource, 0) + quantity
            if event.get("order") in orders or not merged or any(not isinstance(q, int) or q <= 0 or quota.get(r, 0) < q for r, q in merged.items()):
                trace.append("REJECT")
            else:
                for resource, quantity in merged.items(): quota[resource] -= quantity
                orders[event["order"]] = ["RESERVED", sorted(merged.items())]; trace.append("OK")
        elif op == "COMMIT" and event.get("order") in orders and orders[event["order"]][0] == "RESERVED":
            orders[event["order"]][0] = "COMMITTED"; trace.append("OK")
        elif op == "RELEASE" and event.get("order") in orders and orders[event["order"]][0] in {"RESERVED", "COMMITTED"}:
            for resource, quantity in orders[event["order"]][1]: quota[resource] = quota.get(resource, 0) + quantity
            orders[event["order"]][0] = "RELEASED"; trace.append("OK")
        elif op == "SNAP":
            snapshots.append((deepcopy(quota), deepcopy(orders))); trace.append("SNAP")
        elif op == "RESTORE" and isinstance(event.get("snapshot"), int) and event["snapshot"] < len(snapshots):
            quota, orders = deepcopy(snapshots[event["snapshot"]]); trace.append("RESTORE")
        elif op == "READ":
            trace.append("MISSING" if event.get("order") not in orders else "OK")
        else:
            trace.append("INVALID")
    snapshots_out = {}
    for index, (snap_quota, snap_orders) in enumerate(snapshots):
        snapshots_out[str(index)] = {
            "quota": {key: snap_quota[key] for key in sorted(snap_quota)},
            "orders": {key: snap_orders[key][0] for key in sorted(snap_orders)},
        }
    return _envelope(trace, {
        "quota": {key: quota[key] for key in sorted(quota)},
        "orders": {key: value[0] for key, value in sorted(orders.items())},
        "snapshots": snapshots_out,
    })


def cp10(data):
    batches = {b["id"]: {"id": b["id"], "cutoff": b["cutoff"], "capacity": b["capacity"], "used": 0, "closed": False} for b in data.get("batches", [])}
    offers, parcels, used_ids, trace = {}, {}, set(), []
    for e, dup in _dups(data.get("events", [])):
        if dup: trace.append("DUP"); continue
        op = e.get("op"); status = "INVALID"
        if op == "OFFER":
            p=e.get("parcel")
            if p and p not in offers and isinstance(e.get("weight"), int) and e["weight"]>0:
                offers[p]=dict(e); parcels.setdefault(p, {"state":"OFFERED"}); status="OK"
            else: status="REJECT"
        elif op == "ACCEPT":
            p=e.get("parcel"); row=offers.get(p)
            if not row: status="MISSING"
            elif parcels.get(p,{}).get("state") != "OFFERED": status="INVALID"
            else:
                cand=[b for b in batches.values() if not b["closed"] and b["cutoff"]>=row.get("ready",0) and b["capacity"]-b["used"]>=row["weight"]]
                cand.sort(key=lambda b:(b["cutoff"], -row.get("priority",0), b["id"]))
                if not cand: status="REJECT"
                else:
                    b=cand[0]; b["used"]+=row["weight"]; parcels[p]={"state":"ACCEPTED","batch":b["id"],"weight":row["weight"]}; status="OK"
        elif op == "CANCEL":
            p=e.get("parcel"); row=parcels.get(p)
            if row and row.get("state")=="ACCEPTED": batches[row["batch"]]["used"]-=row["weight"]; row["state"]="CANCELLED"; status="OK"
            elif row and row.get("state")=="OFFERED": row["state"]="CANCELLED"; status="OK"
            else: status="INVALID"
        elif op == "CLOSE":
            b=batches.get(e.get("batch"))
            if b: b["closed"]=True; status="OK"
        elif op == "READ":
            p=parcels.get(e.get("parcel")); status="MISSING" if p is None else "OK"
        trace.append(status)
    outp=[{"parcel":p,"state":parcels[p]["state"],"batch":parcels[p].get("batch")} for p in sorted(parcels)]
    outb=[{"id":b["id"],"used":b["used"],"closed":b["closed"]} for b in sorted(batches.values(),key=lambda x:x["id"])]
    return _envelope(trace, {"parcels":outp,"batches":outb})


def cp11(data):
    base=deepcopy(data.get("base",{})); ovs={x["id"]:x for x in data.get("overrides",[])}; pub=[]; revoked=set(); snaps=[]; used=set(); trace=[]; reads=[]
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); st="INVALID"
        if op=="PUBLISH" and e.get("version",0)>0 and all(x.get("version")!=e["version"] for x in pub): pub.append({"version":e["version"],"region":e.get("region"),"tenants":e.get("tenants") or [],"at":len(pub)}); st="OK"
        elif op=="ROLLBACK" and any(x["version"]==e.get("version") for x in pub): revoked.add(e["version"]); st="OK"
        elif op=="SNAP": snaps.append((deepcopy(pub),set(revoked))); st="SNAP"
        elif op=="RESTORE" and isinstance(e.get("snapshot"),int) and e["snapshot"]<len(snaps): pub,revoked=deepcopy(snaps[e["snapshot"]][0]),set(snaps[e["snapshot"]][1]); st="RESTORE"
        elif op=="READ":
            visible=[x for x in pub if x["version"] not in revoked and (x["region"] is None or x["region"]==e.get("region")) and (not x["tenants"] or e.get("tenant") in x["tenants"])]
            cfg=deepcopy(base.get(e.get("service"),{}))
            for x in sorted(visible,key=lambda q:q["at"]):
                for ov in data.get("overrides",[]):
                    if ov.get("id")==x["version"] and ov.get("service")==e.get("service") and (ov.get("region") is None or ov.get("region")==e.get("region")) and (not ov.get("tenants") or e.get("tenant") in ov.get("tenants",[])):
                        for k in ov.get("delete",[]): cfg.pop(k,None)
                        cfg.update(ov.get("set",{}))
            reads.append([[k,cfg[k]] for k in sorted(cfg)]); st="OK"
        trace.append(st)
    return _envelope(trace, {
        "reads": [[{"key": key, "value": value} for key, value in read] for read in reads],
        "snapshots": list(range(len(snaps))),
    })


def cp12(data):
    users={}; parent={}; edges=[]; used=set(); trace=[]; lookups=[]; snaps=[]
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); t=e.get("tenant"); u=e.get("user"); st="INVALID"
        def root(x):
            seen=set()
            while (t,x) in parent and x not in seen: seen.add(x); x=parent[(t,x)]
            return x
        if op=="CREATE" and t in data.get("tenants",[]) and (t,u) not in users: users[(t,u)]=True; st="OK"
        elif op=="MERGE" and all((t,x) in users for x in (e.get("from"),e.get("to"))):
            a,b=root(e["from"]),root(e["to"])
            if a!=b and root(b)!=e["from"]: parent[(t,a)]=b; edges.append([t,a,b]); st="OK"
            else: st="REJECT"
        elif op=="SPLIT":
            k=(t,e.get("from")); link=[t,e.get("from"),e.get("to")]
            if parent.get(k)==e.get("to"):
                parent.pop(k)
                if link in edges: edges.remove(link)
                st="OK"
            else: st="REJECT"
        elif op=="LOOKUP": lookups.append([t,u,root(u) if (t,u) in users else "MISSING"]); st="OK"
        elif op=="SNAP": snaps.append(deepcopy(edges)); st="SNAP"
        trace.append(st)
    return _envelope(trace, {
        "lookups": [{"tenant": tenant, "user": user, "root": root} for tenant, user, root in sorted(lookups, key=lambda row: (row[0], row[1]))],
        "edges": [{"tenant": tenant, "from": source, "to": target} for tenant, source, target in sorted(edge for edge in edges if parent.get((edge[0], edge[1])) == edge[2])],
        "snapshots": list(range(len(snaps))),
    })


def cp13(data):
    ac={k:{"balance":v,"holds":{}} for k,v in data.get("accounts",{}).items()}; used=set(); trace=[]; reads=[]
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); a=ac.get(e.get("account")); h=a and a["holds"].get(e.get("hold")); st="INVALID"
        if op=="HOLD" and a and not h and isinstance(e.get("amount"),int) and e["amount"]>0 and a["balance"]-sum(x["remaining"] for x in a["holds"].values() if x["remaining"]>0)>=e["amount"]: a["holds"][e["hold"]]={"remaining":e["amount"],"state":"HELD","captured":0}; st="OK"
        elif op=="CAPTURE" and h and h["state"]=="HELD" and 0<e.get("amount",0)<=h["remaining"]: h["remaining"]-=e["amount"]; h["captured"]+=e["amount"]; h["state"]="CAPTURED" if h["remaining"]==0 else "HELD"; a["balance"]-=e["amount"]; st="OK"
        elif op=="RELEASE" and h and h["state"]=="HELD" and 0<e.get("amount",0)<=h["remaining"]: h["remaining"]-=e["amount"]; h["state"]="RELEASED" if h["remaining"]==0 else "HELD"; st="OK"
        elif op=="VOID" and h and h["state"]=="CAPTURED": h["state"]="VOIDED"; st="OK"
        elif op=="READ" and a: reads.append({"balance":a["balance"],"available":a["balance"]-sum(x["remaining"] for x in a["holds"].values() if x["remaining"]>0),"holds":[{"hold":k,"state":v["state"],"remaining":v["remaining"]} for k,v in sorted(a["holds"].items())]}); st="OK"
        trace.append(st)
    return _envelope(trace, {"reads":reads})


def cp14(data):
    bs={ (x["sku"],x["batch"]):{"sku":x["sku"],"batch":x["batch"],"free":x["qty"],"locked":0,"shipped":0,"expiry":x["expiry"],"received":x["received"]} for x in data.get("batches",[])}; orders={}; used=set(); trace=[]; reads=[]
    for e in data.get("events",[]):
        at=e.get("at",0)
        for b in bs.values():
            if b["expiry"]<=at: b["free"]=0
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); st="INVALID"; o=e.get("order"); sku=e.get("sku")
        if op=="ALLOCATE" and o not in orders:
            need=e.get("qty",0); cand=sorted([b for b in bs.values() if b["sku"]==sku and b["free"]>0],key=lambda b:(b["expiry"],b["received"],b["batch"]))
            if sum(b["free"] for b in cand)>=need and need>0:
                alloc=[]
                for b in cand:
                    n=min(need,b["free"]); b["free"]-=n;b["locked"]+=n;alloc.append([b["batch"],n]);need-=n
                    if not need: break
                orders[o]={"sku":sku,"alloc":alloc,"state":"ALLOCATED"}; st="OK"
            else: st="REJECT"
        elif op=="SHIP" and o in orders and orders[o]["state"]=="ALLOCATED":
            for bid,n in orders[o]["alloc"]: bs[(orders[o]["sku"],bid)]["locked"]-=n;bs[(orders[o]["sku"],bid)]["shipped"]+=n
            orders[o]["state"]="SHIPPED"; st="OK"
        elif op=="CANCEL" and o in orders and orders[o]["state"]=="ALLOCATED":
            for bid,n in orders[o]["alloc"]: bs[(orders[o]["sku"],bid)]["locked"]-=n;bs[(orders[o]["sku"],bid)]["free"]+=n
            orders[o]["state"]="CANCELLED"; st="OK"
        elif op=="READ":
            rows=[]
            for b in sorted((b for b in bs.values() if b["sku"]==sku),key=lambda b:b["batch"]): rows.append({"batch":b["batch"],"free":b["free"],"locked":b["locked"],"expired":b["expiry"]<=at})
            reads.append([sku,rows]); st="OK"
        trace.append(st)
    return _envelope(trace, {
        "reads": [{"sku": sku, "batches": rows} for sku, rows in reads],
        "orders": [{"order": key, "state": value["state"]} for key, value in sorted(orders.items())],
    })


def cp15(data):
    policies=data.get("policies",[]); delegates=[]; req={}; used=set(); trace=[]; reads=[]
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); st="INVALID"
        if op=="DELEGATE": delegates.append(e); st="OK"
        elif op=="SUBMIT" and e.get("request") not in req:
            pols=[p for p in policies if p["department"]==e.get("department") and p["version"]<=e.get("at",0)]
            if pols:
                p=max(pols,key=lambda x:x["version"]); req[e["request"]]={"status":"AUTO" if e["amount"]<p["threshold"] else "PENDING","step":0,"policy":p}; st="OK"
            else: st="REJECT"
        elif op in ("APPROVE","REJECT") and e.get("request") in req:
            r=req[e["request"]]
            if r["status"]=="PENDING":
                aps=r["policy"]["approvers"]; idx=r["step"]; expected=aps[idx] if idx<len(aps) else None
                valid=e.get("user")==expected or any(d.get("from")==expected and d.get("to")==e.get("user") and d.get("start",0)<=e.get("at",0)<d.get("end",0) for d in delegates)
                if valid:
                    if op=="REJECT": r["status"]="REJECTED"
                    else: r["step"]+=1; r["status"]="APPROVED" if r["step"]==len(aps) else "PENDING"
                    st="OK"
        elif op=="READ" and e.get("request") in req:
            r=req[e["request"]]; reads.append({"request":e["request"],"state":r["status"],"step":r["step"],"policy":r["policy"]["version"]}); st="OK"
        trace.append(st)
    return _envelope(trace, {"reads":reads})


def cp16(data):
    g=data["global"]; gb={"cap":g["capacity"],"rate":g["rate"],"tok":g["capacity"],"last":0}; tb={k:{"cap":v["capacity"],"rate":v["rate"],"tok":v["capacity"],"last":0} for k,v in data.get("tenants",{}).items()}; req={}; used=set(); trace=[]; reads=[]
    def advance(b,at):
        if at>b["last"]: b["tok"]=min(b["cap"],b["tok"]+(at-b["last"])*b["rate"]);b["last"]=at
    for e in data.get("events",[]):
        i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); op=e.get("op"); at=e.get("at",0); st="INVALID"; t=tb.get(e.get("tenant"))
        if t: advance(t,at)
        advance(gb,at)
        if op=="REQUEST" and t and e.get("cost",0)>0 and t["tok"]>=e["cost"] and gb["tok"]>=e["cost"]: t["tok"]-=e["cost"];gb["tok"]-=e["cost"];req[e.get("request",e.get("id"))]=[e.get("tenant"),e["cost"]];st="OK"
        elif op=="REFUND":
            r=req.get(e.get("request"));
            if r: t2=tb[r[0]]; t2["tok"]=min(t2["cap"],t2["tok"]+r[1]);gb["tok"]=min(gb["cap"],gb["tok"]+r[1]);req[e["request"]]=None;st="OK"
        elif op=="READ" and t: reads.append({"tenant":e["tenant"],"tenant_tokens":t["tok"],"global_tokens":gb["tok"]});st="OK"
        trace.append(st)
    return _envelope(trace, {"reads":reads})


def cp17(data):
    facts=deepcopy(data.get("facts",{})); invalid={}; generations={}; current=None; snaps=[]; used=set(); trace=[]; reads=[]
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP"); continue
        used.add(i); st="INVALID"
        if op=="UPSERT" and (e.get("key") not in facts or e["version"]>facts[e["key"]]["version"]): facts[e["key"]]={"version":e["version"],"value":e["value"]};st="OK"
        elif op=="INVALIDATE": invalid[e["key"]]=max(invalid.get(e["key"],-1),e["version"]);st="OK"
        elif op=="REBUILD": current=e["generation"]; generations[current]={k:deepcopy(v) for k,v in facts.items() if v["version"]>invalid.get(k,-1)};st="OK"
        elif op=="READ":
            key=e.get("key"); v=generations.get(current,{}).get(key)
            reads.append({"key":key,"miss":v is None,"version":None if v is None else v["version"],"value":None if v is None else v["value"]}); st="OK"
        elif op=="SNAP": snaps.append((deepcopy(facts),deepcopy(invalid),deepcopy(generations),current));st="SNAP"
        elif op=="RESTORE" and isinstance(e.get("snapshot"),int) and e["snapshot"]<len(snaps): facts,invalid,generations,current=deepcopy(snaps[e["snapshot"]]);st="RESTORE"
        trace.append(st)
    return _envelope(trace, {"reads":reads,"generation":current})


def cp18(data):
    fares=data.get("fares",[]); tickets={}; used=set(); trace=[]; reads=[]
    def fare(fr,to,t):
        x=[f for f in fares if f["from"]==fr and f["to"]==to and f["start"]<=t<f["end"]]
        return max(x,key=lambda q:(q["start"],q["id"])) if x else None
    for e in data.get("events",[]):
        op=e.get("op"); i=e.get("id")
        if i in used: trace.append("DUP");continue
        used.add(i); st="INVALID"; t=tickets.get(e.get("ticket"))
        if op=="BUY" and not t:
            f=fare(e["from"],e["to"],e["depart"])
            if f and e.get("at",0)>=f["start"]: tickets[e["ticket"]]={"state":"ACTIVE","price":f["price"],"depart":e["depart"],"from":e["from"],"to":e["to"],"refund":0};st="OK"
        elif op=="CHANGE" and t and t["state"]=="ACTIVE":
            f=fare(t["from"],t["to"],e["new_depart"])
            if f: t["state"]="CHANGED"; tickets[e["ticket"]+"#current"]={**t,"state":"ACTIVE","depart":e["new_depart"],"price":f["price"]};st="OK"
        elif op=="REFUND" and t and t["state"]=="ACTIVE":
            delta=t["depart"]-e.get("at",0); pct=90 if delta>60 else 50 if delta>10 else 0; t["refund"]=(t["price"]*pct)//100;t["state"]="REFUNDED";st="OK"
        elif op=="READ":
            if t: reads.append({"ticket":e.get("ticket"),"state":t["state"],"price":t["price"],"refund":t["refund"]})
            else: reads.append({"ticket":e.get("ticket"),"state":None,"price":None,"refund":0})
            st="OK"
        trace.append(st)
    return _envelope(trace, {"reads":reads})


_FUNCS={"CP-09":cp09,"CP-10":cp10,"CP-11":cp11,"CP-12":cp12,"CP-13":cp13,"CP-14":cp14,"CP-15":cp15,"CP-16":cp16,"CP-17":cp17,"CP-18":cp18}
_TITLES={"CP-09":"配额预占与恢复回放","CP-10":"运输批次与截止窗口","CP-11":"双区域灰度与回滚","CP-12":"多租户身份合并","CP-13":"账务冻结与部分解冻","CP-14":"批次库存与有效期","CP-15":"审批链与代理窗口","CP-16":"分层令牌桶与补偿","CP-17":"缓存重建与失效代数","CP-18":"时间价与退款基线"}
_SCHEMAS = {
    "CP-09": {"keys": ["quota", "events", "op", "id", "order", "lines", "snapshot", "orders", "snapshots"], "actions": ["RESERVE", "COMMIT", "RELEASE", "SNAP", "RESTORE", "READ"], "states": ["RESERVED", "COMMITTED", "RELEASED"], "bound": ["DUP", "MISSING"]},
    "CP-10": {"keys": ["batches", "events", "id", "cutoff", "capacity", "op", "parcel", "ready", "weight", "priority", "batch", "at", "parcels", "state", "used", "closed"], "actions": ["OFFER", "ACCEPT", "CANCEL", "CLOSE", "READ"], "states": ["OFFERED", "ACCEPTED", "CANCELLED"], "bound": ["DUP"]},
    "CP-11": {"keys": ["base", "overrides", "events", "id", "service", "region", "set", "delete", "op", "version", "tenants", "snapshot", "reads", "key", "value", "snapshots"], "actions": ["PUBLISH", "ROLLBACK", "READ", "SNAP", "RESTORE"], "states": [], "bound": ["DUP"]},
    "CP-12": {"keys": ["tenants", "events", "op", "id", "tenant", "user", "from", "to", "lookups", "root", "edges", "snapshots"], "actions": ["CREATE", "MERGE", "SPLIT", "LOOKUP", "SNAP"], "states": ["MISSING"], "bound": ["DUP"]},
    "CP-13": {"keys": ["accounts", "events", "op", "id", "account", "hold", "amount", "reads", "balance", "available", "holds", "remaining", "state"], "actions": ["HOLD", "CAPTURE", "RELEASE", "VOID", "READ"], "states": ["HELD", "CAPTURED", "RELEASED", "VOIDED"], "bound": ["DUP"]},
    "CP-14": {"keys": ["batches", "events", "sku", "batch", "qty", "expiry", "received", "op", "id", "order", "at", "reads", "free", "locked", "expired", "orders", "state"], "actions": ["ALLOCATE", "SHIP", "CANCEL", "READ"], "states": ["ALLOCATED", "SHIPPED", "CANCELLED"], "bound": ["DUP"]},
    "CP-15": {"keys": ["policies", "events", "version", "department", "threshold", "approvers", "op", "id", "request", "amount", "at", "user", "from", "to", "start", "end", "reads", "state", "step", "policy"], "actions": ["SUBMIT", "APPROVE", "REJECT", "DELEGATE", "READ"], "states": ["AUTO", "PENDING", "APPROVED", "REJECTED"], "bound": ["DUP"]},
    "CP-16": {"keys": ["global", "capacity", "rate", "tenants", "events", "op", "id", "tenant", "at", "cost", "request", "reads", "tenant_tokens", "global_tokens"], "actions": ["REQUEST", "REFUND", "READ"], "states": [], "bound": ["DUP"]},
    "CP-17": {"keys": ["facts", "version", "value", "events", "op", "id", "key", "generation", "snapshot", "reads", "miss"], "actions": ["UPSERT", "INVALIDATE", "REBUILD", "READ", "SNAP", "RESTORE"], "states": [], "bound": ["DUP"]},
    "CP-18": {"keys": ["fares", "id", "from", "to", "start", "end", "price", "events", "op", "ticket", "depart", "at", "new_depart", "reads", "state", "refund"], "actions": ["BUY", "CHANGE", "REFUND", "READ"], "states": ["ACTIVE", "CHANGED", "REFUNDED"], "bound": ["DUP"]},
}


def _wish(item_id: str) -> str:
    import re
    from .next_questions import _sections
    body = _sections(Path(__file__).resolve().parents[1] / "docs/question-bank-next-coding-20261008.md", "CP")[item_id][1]
    match = re.search(r"\*\*题面全文。\*\*\s*(.+?)(?:\n\*\*|\Z)", body, re.S)
    if match is None:
        raise KeyError(item_id)
    return match.group(1).strip()


def _contract(item_id: str, language: str) -> str:
    schema = _SCHEMAS[item_id]
    if language == "go":
        entry = "只输出一个 go 代码围栏。入口是 package solution 的 func Describe() json.RawMessage 和 func Solve(input json.RawMessage) json.RawMessage。自行 import encoding/json。不要写 main，不要写测试，不要写依赖声明。"
    elif language == "typescript":
        entry = "只输出一个 typescript 代码围栏。入口是 export function describe(): any 和 export function solve(data: any): any。可以返回 Promise。"
    else:
        entry = "只输出一个 python 代码围栏。入口是 def describe() -> dict 和 def solve(data) -> dict。"
    lines = [
        entry,
        "describe() 是评测要调用的接口文档。评测先调用它，再按文档把夹具改成你的字段名和词语，然后调用解题入口。键是角色，必须保留；值是你自己的非空名字，同一组里不要复用。缺了角色，本题无法判分。",
        "解题入口收到的数据含 events。返回值只能有 trace 和 output 两个键。trace 与 events 等长，每一项是非空字符串。事件编号第一次出现就占用，失败也占用。同一个编号再次出现时，这一项必须是 DUP，并且不能改账。其他结果用什么词由你决定。",
        "文档有 keys、actions、states、trace 四组。trace.dup 的值固定写 DUP。",
        "事件里只有动作、编号和这个动作自己的参数。reads、orders、snapshots、lookups、edges、generation 这些名字如果出现，只属于输出，不是事件上的输入字段。",
        "keys 角色：" + "、".join(schema["keys"]) + "。",
        "actions 角色：" + "、".join(schema["actions"]) + "。",
        "states 角色：" + ("、".join(schema["states"]) if schema["states"] else "这一题没有要声明的状态词，states 写空对象。") + "。",
        "不得使用网络、文件、环境变量、随机数或子进程。",
    ]
    return "\n".join(lines)


def _doc_prompt(item_id, language):
    return _wish(item_id) + "\n\n" + _contract(item_id, language)


def _fixture_data(item_id):
    # Five intentionally small boundary cases, one per scoring group.
    common={
      "CP-10":[{"batches":[{"id":"b1","cutoff":5,"capacity":2},{"id":"b2","cutoff":8,"capacity":2}],"events":[{"op":"OFFER","id":"1","parcel":"p","ready":0,"weight":1,"priority":1},{"op":"ACCEPT","id":"2","parcel":"p"}]},{"batches":[{"id":"b","cutoff":1,"capacity":1}],"events":[{"op":"ACCEPT","id":"x","parcel":"u"}]},{"batches":[{"id":"b","cutoff":5,"capacity":1}],"events":[{"op":"OFFER","id":"o","parcel":"p","ready":1,"weight":1,"priority":0},{"op":"CLOSE","id":"c","batch":"b","at":9},{"op":"ACCEPT","id":"a","parcel":"p"}]},{"batches":[{"id":"b","cutoff":5,"capacity":1}],"events":[{"op":"OFFER","id":"o","parcel":"p","ready":1,"weight":1,"priority":0},{"op":"ACCEPT","id":"a","parcel":"p"},{"op":"CANCEL","id":"c","parcel":"p"},{"op":"ACCEPT","id":"d","parcel":"p"}]},{"batches":[],"events":[{"op":"OFFER","id":"x","parcel":"p","ready":0,"weight":1,"priority":0},{"op":"OFFER","id":"x","parcel":"p","ready":0,"weight":1,"priority":0}]}],
      "CP-11":[{"base":{"svc":{"a":0}},"overrides":[{"id":1,"service":"svc","region":None,"set":{"a":1},"delete":[]}],"events":[{"op":"PUBLISH","id":"p","version":1,"region":None,"tenants":[]},{"op":"READ","id":"r","service":"svc","region":"x","tenant":"t"}]},{"base":{"svc":{"a":0}},"overrides":[],"events":[{"op":"READ","id":"r","service":"svc","region":"x","tenant":"t"}]},{"base":{"svc":{"a":0}},"overrides":[],"events":[{"op":"ROLLBACK","id":"r","version":9}]},{"base":{"svc":{"a":0}},"overrides":[],"events":[{"op":"SNAP","id":"s"},{"op":"RESTORE","id":"r","snapshot":0}]},{"base":{"svc":{"a":0}},"overrides":[],"events":[{"op":"PUBLISH","id":"p","version":1,"region":"x","tenants":["t"]},{"op":"PUBLISH","id":"q","version":1,"region":"x","tenants":["t"]}]}],
      "CP-12":[{"tenants":["t"],"events":[{"op":"CREATE","id":"1","tenant":"t","user":"a"},{"op":"CREATE","id":"2","tenant":"t","user":"b"},{"op":"MERGE","id":"3","tenant":"t","from":"a","to":"b"},{"op":"LOOKUP","id":"4","tenant":"t","user":"a"}]},{"tenants":["t","u"],"events":[{"op":"CREATE","id":"1","tenant":"t","user":"a"},{"op":"CREATE","id":"2","tenant":"u","user":"b"},{"op":"MERGE","id":"3","tenant":"t","from":"a","to":"b"}]},{"tenants":["t"],"events":[{"op":"CREATE","id":"1","tenant":"t","user":"a"},{"op":"CREATE","id":"2","tenant":"t","user":"b"},{"op":"MERGE","id":"3","tenant":"t","from":"a","to":"b"},{"op":"SPLIT","id":"4","tenant":"t","from":"a","to":"b"}]},{"tenants":["t"],"events":[{"op":"CREATE","id":"1","tenant":"t","user":"a"},{"op":"SNAP","id":"2"}]},{"tenants":["t"],"events":[{"op":"LOOKUP","id":"1","tenant":"t","user":"x"}]}],
      "CP-13":[{"accounts":{"a":10},"events":[{"op":"HOLD","id":"1","account":"a","hold":"h","amount":6},{"op":"READ","id":"2","account":"a"}]},{"accounts":{"a":3},"events":[{"op":"HOLD","id":"1","account":"a","hold":"h","amount":4}]},{"accounts":{"a":10},"events":[{"op":"HOLD","id":"1","account":"a","hold":"h","amount":6},{"op":"CAPTURE","id":"2","account":"a","hold":"h","amount":2},{"op":"RELEASE","id":"3","account":"a","hold":"h","amount":4}]},{"accounts":{"a":10},"events":[{"op":"HOLD","id":"1","account":"a","hold":"h","amount":2},{"op":"CAPTURE","id":"2","account":"a","hold":"h","amount":2},{"op":"VOID","id":"3","account":"a","hold":"h"}]},{"accounts":{"a":10},"events":[{"op":"HOLD","id":"1","account":"a","hold":"h","amount":2},{"op":"HOLD","id":"1","account":"a","hold":"h","amount":2}]}],
      "CP-14":[{"batches":[{"sku":"s","batch":"b1","qty":2,"expiry":5,"received":1},{"sku":"s","batch":"b2","qty":2,"expiry":8,"received":2}],"events":[{"op":"ALLOCATE","id":"1","order":"o","sku":"s","qty":3,"at":1},{"op":"READ","id":"2","sku":"s","at":1}]},{"batches":[{"sku":"s","batch":"b","qty":1,"expiry":2,"received":1}],"events":[{"op":"READ","id":"1","sku":"s","at":2}]},{"batches":[{"sku":"s","batch":"b","qty":1,"expiry":2,"received":1}],"events":[{"op":"ALLOCATE","id":"1","order":"o","sku":"s","qty":1,"at":1},{"op":"READ","id":"2","sku":"s","at":3}]},{"batches":[{"sku":"s","batch":"b","qty":1,"expiry":9,"received":1}],"events":[{"op":"ALLOCATE","id":"1","order":"o","sku":"s","qty":1,"at":1},{"op":"CANCEL","id":"2","order":"o","at":1}]},{"batches":[{"sku":"s","batch":"b","qty":1,"expiry":9,"received":1}],"events":[{"op":"ALLOCATE","id":"1","order":"o","sku":"s","qty":1,"at":1},{"op":"SHIP","id":"2","order":"o","at":1},{"op":"CANCEL","id":"3","order":"o","at":1}]}],
      "CP-15":[{"policies":[{"version":1,"department":"d","threshold":10,"approvers":["u"]}],"events":[{"op":"SUBMIT","id":"1","request":"r","department":"d","amount":10,"at":1},{"op":"APPROVE","id":"2","request":"r","user":"u","at":1},{"op":"READ","id":"9","request":"r"}]},{"policies":[{"version":1,"department":"d","threshold":10,"approvers":["u"]}],"events":[{"op":"SUBMIT","id":"1","request":"r","department":"d","amount":9,"at":1},{"op":"READ","id":"9","request":"r"}]},{"policies":[{"version":1,"department":"d","threshold":10,"approvers":["u"]}],"events":[{"op":"SUBMIT","id":"1","request":"r","department":"d","amount":10,"at":1},{"op":"REJECT","id":"2","request":"r","user":"u","at":1},{"op":"READ","id":"9","request":"r"}]},{"policies":[{"version":1,"department":"d","threshold":10,"approvers":["u"]}],"events":[{"op":"DELEGATE","id":"1","from":"u","to":"v","start":2,"end":4},{"op":"SUBMIT","id":"2","request":"r","department":"d","amount":10,"at":1},{"op":"APPROVE","id":"3","request":"r","user":"v","at":2},{"op":"READ","id":"9","request":"r"}]},{"policies":[],"events":[{"op":"READ","id":"1","request":"x"}]}],
      "CP-16":[{"global":{"capacity":5,"rate":1},"tenants":{"t":{"capacity":3,"rate":1}},"events":[{"op":"REQUEST","id":"1","request":"r","tenant":"t","at":0,"cost":2},{"op":"READ","id":"2","tenant":"t","at":0}]},{"global":{"capacity":1,"rate":0},"tenants":{"t":{"capacity":5,"rate":0}},"events":[{"op":"REQUEST","id":"1","request":"r","tenant":"t","at":0,"cost":2}]},{"global":{"capacity":5,"rate":1},"tenants":{"t":{"capacity":3,"rate":1}},"events":[{"op":"REQUEST","id":"1","request":"r","tenant":"t","at":0,"cost":2},{"op":"REQUEST","id":"2","request":"s","tenant":"t","at":2,"cost":1}]},{"global":{"capacity":5,"rate":0},"tenants":{"t":{"capacity":3,"rate":0}},"events":[{"op":"REQUEST","id":"1","request":"r","tenant":"t","at":0,"cost":2},{"op":"REFUND","id":"2","request":"r","at":0}]},{"global":{"capacity":5,"rate":0},"tenants":{"t":{"capacity":3,"rate":0}},"events":[{"op":"REQUEST","id":"1","request":"r","tenant":"t","at":0,"cost":1},{"op":"REFUND","id":"2","request":"r","at":0},{"op":"REFUND","id":"3","request":"r","at":0}]}],
      "CP-17":[{"facts":{"k":{"version":1,"value":"a"}},"events":[{"op":"REBUILD","id":"1","generation":1},{"op":"READ","id":"2","key":"k"}]},{"facts":{"k":{"version":2,"value":"a"}},"events":[{"op":"UPSERT","id":"1","key":"k","version":1,"value":"b"},{"op":"REBUILD","id":"2","generation":1},{"op":"READ","id":"3","key":"k"}]},{"facts":{"k":{"version":1,"value":"a"}},"events":[{"op":"INVALIDATE","id":"1","key":"k","version":1},{"op":"REBUILD","id":"2","generation":1},{"op":"READ","id":"3","key":"k"}]},{"facts":{"k":{"version":1,"value":"a"}},"events":[{"op":"REBUILD","id":"1","generation":1},{"op":"SNAP","id":"2"},{"op":"UPSERT","id":"3","key":"k","version":2,"value":"b"},{"op":"RESTORE","id":"4","snapshot":0},{"op":"READ","id":"5","key":"k"}]},{"facts":{},"events":[{"op":"READ","id":"1","key":"x"}]}],
      "CP-18":[{"fares":[{"id":"a","from":"x","to":"y","start":0,"end":100,"price":101}],"events":[{"op":"BUY","id":"1","ticket":"t","from":"x","to":"y","depart":50,"at":1},{"op":"READ","id":"2","ticket":"t"}]},{"fares":[],"events":[{"op":"BUY","id":"1","ticket":"t","from":"x","to":"y","depart":50,"at":1}]},{"fares":[{"id":"a","from":"x","to":"y","start":0,"end":100,"price":101},{"id":"b","from":"x","to":"y","start":50,"end":100,"price":203}],"events":[{"op":"BUY","id":"1","ticket":"t","from":"x","to":"y","depart":60,"at":1}]},{"fares":[{"id":"a","from":"x","to":"y","start":0,"end":100,"price":100}],"events":[{"op":"BUY","id":"1","ticket":"t","from":"x","to":"y","depart":80,"at":1},{"op":"REFUND","id":"2","ticket":"t","at":1}]},{"fares":[{"id":"a","from":"x","to":"y","start":0,"end":100,"price":101}],"events":[{"op":"BUY","id":"1","ticket":"t","from":"x","to":"y","depart":20,"at":1},{"op":"REFUND","id":"2","ticket":"t","at":15},{"op":"REFUND","id":"3","ticket":"t","at":15}]}],
    }
    return common[item_id]


_RESULT_READS = {"READ", "LOOKUP"}


def _result_read(item_id, events):
    # Field shape matches the READ / LOOKUP events already used by that item.
    if item_id == "CP-11":
        return {"op": "READ", "id": "view", "service": "svc", "region": "x", "tenant": "t"}
    if item_id == "CP-12":
        tenant = user = None
        for event in events:
            if event.get("tenant") and event.get("user"):
                tenant, user = event["tenant"], event["user"]
            if event.get("tenant") and event.get("from"):
                tenant, user = event["tenant"], event["from"]
        if tenant is None or user is None:
            return None
        return {"op": "LOOKUP", "id": "view", "tenant": tenant, "user": user}
    if item_id == "CP-13":
        account = next((event["account"] for event in reversed(events) if event.get("account")), None)
        if account is None:
            return None
        return {"op": "READ", "id": "view", "account": account}
    if item_id == "CP-14":
        sku = next((event["sku"] for event in reversed(events) if event.get("sku")), None)
        at = next((event["at"] for event in reversed(events) if "at" in event), None)
        if sku is None or at is None:
            return None
        return {"op": "READ", "id": "view", "sku": sku, "at": at}
    if item_id == "CP-18":
        ticket = next((event["ticket"] for event in reversed(events) if event.get("ticket")), None)
        if ticket is None:
            return None
        return {"op": "READ", "id": "view", "ticket": ticket}
    return None


def _append_result_read(item_id, row):
    events = row.get("events")
    if not isinstance(events, list) or not events or events[-1].get("op") in _RESULT_READS:
        return
    event = _result_read(item_id, events)
    if event is None:
        return
    before = _FUNCS[item_id](deepcopy(row))["output"]
    trial = deepcopy(row)
    trial["events"].append(deepcopy(event))
    # A read the reference does not record leaves output empty and still scores empty-against-empty.
    if before == _FUNCS[item_id](trial)["output"]:
        return
    events.append(event)


def cases(item_id):
    if item_id=="CP-09":
        rows = [
            {"quota":{"a":2},"events":[{"op":"RESERVE","id":"r","order":"o","lines":[["a",1]]},{"op":"SNAP","id":"s"},{"op":"RELEASE","id":"x","order":"o"},{"op":"RESTORE","id":"z","snapshot":0}]},
            {"quota":{"a":1},"events":[{"op":"RESERVE","id":"r","order":"o","lines":[["a",2]]},{"op":"RESERVE","id":"r2","order":"o","lines":[["a",1]]}]},
            {"quota":{"a":3},"events":[{"op":"RESERVE","id":"r","order":"o","lines":[["a",1],["a",1]]},{"op":"COMMIT","id":"c","order":"o"},{"op":"READ","id":"q","order":"o"}]},
            {"quota":{"a":2},"events":[{"op":"RESERVE","id":"r","order":"o","lines":[["a",1]]},{"op":"SNAP","id":"s"},{"op":"RELEASE","id":"x","order":"o"},{"op":"RESTORE","id":"z","snapshot":0},{"op":"RELEASE","id":"x","order":"o"}]},
            {"quota":{"a":1},"events":[{"op":"READ","id":"q","order":"missing"},{"op":"RESTORE","id":"r","snapshot":9}]},
        ]
        # Keep the same shape as every other coding item: five scoring groups,
        # each containing four independent one-case batches.  The previous
        # implementation wrapped the rows in an extra list, so the runner's
        # case index and the scorer's expected values diverged for CP-09.
        groups = []
        for row in rows:
            batches = []
            for repeat in range(4):
                variant = deepcopy(row)
                for event in variant["events"]:
                    event["id"] = f"{event['id']}-v{repeat}"
                batches.append([Case(variant, _FUNCS[item_id](deepcopy(variant)))])
            groups.append(batches)
        return groups
    rows=_fixture_data(item_id)
    if item_id == "CP-16":
        for row in rows:
            if row["events"][-1]["op"] != "READ":
                row["events"].append({"op": "READ", "id": "view", "tenant": "t", "at": row["events"][-1].get("at", 0)})
    else:
        for row in rows:
            _append_result_read(item_id, row)
    # The scorer's four batches are four distinct observations.  Suffixing
    # event ids preserves each state-machine outcome while exercising the
    # global idempotency table independently in every fixture.
    groups = []
    for row in rows:
        batches = []
        for repeat in range(4):
            variant = deepcopy(row)
            for event in variant.get("events", []):
                if isinstance(event, dict) and "id" in event:
                    event["id"] = f"{event['id']}-v{repeat}"
            expected = _FUNCS[item_id](deepcopy(variant))
            batches.append([Case(variant, expected)])
        groups.append(batches)
    return groups


def _payload(groups):
    return [[[case.data for case in batch] for batch in group] for group in groups]


def _fixture(schema: dict, groups, marker: str, language: str) -> str:
    import inspect
    from . import describe_contract as dc
    blob = json.dumps(_payload(groups), ensure_ascii=True, separators=(",", ":"))
    spec = json.dumps({key: schema[key] for key in ("keys", "actions", "states")}, ensure_ascii=True)
    if language == "python":
        return f"""import contextlib
import copy
import io
import json
{inspect.getsource(dc._mapping)}
{inspect.getsource(dc.valid_document)}
{inspect.getsource(dc.rename_tree)}
{inspect.getsource(dc.adapt_input)}
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import describe, solve
schema = json.loads({spec!r})
groups = json.loads({blob!r})
def _load():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            doc = describe()
    except BaseException:
        return None
    if not valid_document(doc, schema):
        return None
    return doc
doc = _load()
print({marker!r} + " DESCRIBE " + json.dumps(doc, ensure_ascii=True, separators=(",", ":")))
case_no = 0
for group in groups:
    for batch in group:
        for data in batch:
            encoded = "null"
            if doc is not None:
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        got = solve(adapt_input(copy.deepcopy(data), doc))
                    encoded = json.dumps(got, ensure_ascii=True, separators=(",", ":"))
                except BaseException:
                    encoded = "null"
            print({marker!r} + " CASE " + str(case_no) + " " + encoded)
            case_no += 1
"""
    if language == "go":
        return (
            "package solution\nimport (\"encoding/json\"; \"fmt\"; \"testing\")\n"
            "func renameTree(v any, keys map[string]string, values map[string]string) any {\n"
            "  switch t := v.(type) {\n"
            "  case map[string]any:\n"
            "    out := map[string]any{}\n"
            "    for k, item := range t {\n"
            "      nk := k\n"
            "      if mapped, ok := keys[k]; ok { nk = mapped }\n"
            "      out[nk] = renameTree(item, keys, values)\n"
            "    }\n"
            "    return out\n"
            "  case []any:\n"
            "    out := make([]any, len(t))\n"
            "    for i, item := range t { out[i] = renameTree(item, keys, values) }\n"
            "    return out\n"
            "  case string:\n"
            "    if mapped, ok := values[t]; ok { return mapped }\n"
            "    return t\n"
            "  default:\n"
            "    return v\n"
            "  }\n"
            "}\n"
            "func asMap(v any) map[string]string {\n"
            "  raw, _ := v.(map[string]any)\n"
            "  out := map[string]string{}\n"
            "  for k, item := range raw {\n"
            "    if s, ok := item.(string); ok { out[k] = s }\n"
            "  }\n"
            "  return out\n"
            "}\n"
            "func identity(m map[string]string) bool {\n"
            "  for k, v := range m { if k != v { return false } }\n"
            "  return true\n"
            "}\n"
            "func TestContent20260925(t *testing.T) {\n"
            "  var groups [][][]json.RawMessage\n"
            f"  if err := json.Unmarshal([]byte({json.dumps(blob)}), &groups); err != nil {{ t.Fatal(err) }}\n"
            "  var doc map[string]any\n"
            "  raw := Describe()\n"
            "  bad := json.Unmarshal(raw, &doc) != nil\n"
            "  keys, actions, states := asMap(doc[\"keys\"]), asMap(doc[\"actions\"]), asMap(doc[\"states\"])\n"
            "  values := map[string]string{}\n"
            "  for k, v := range actions { values[k] = v }\n"
            "  for k, v := range states { values[k] = v }\n"
            "  same := !bad && identity(keys) && identity(actions) && identity(states)\n"
            "  compact, err := json.Marshal(doc)\n"
            "  if err != nil { compact = []byte(\"null\") }\n"
            "  fmt.Printf(\"%s DESCRIBE %s\\n\", " + json.dumps(marker) + ", compact)\n"
            "  caseNo := 0\n"
            "  for _, group := range groups { for _, batch := range group { for _, input := range batch {\n"
            "    got := []byte(\"null\")\n"
            "    if !bad {\n"
            "      got = func() (out json.RawMessage) {\n"
            "        defer func(){ if recover()!=nil { out=[]byte(\"null\") } }()\n"
            "        if same { return Solve(input) }\n"
            "        var value any\n"
            "        if json.Unmarshal(input, &value) != nil { return []byte(\"null\") }\n"
            "        encoded, err := json.Marshal(renameTree(value, keys, values))\n"
            "        if err != nil { return []byte(\"null\") }\n"
            "        return Solve(encoded)\n"
            "      }()\n"
            "    }\n"
            "    if len(got)==0 { got=[]byte(\"null\") }\n"
            "    fmt.Printf(\"%s CASE %d %s\\n\", " + json.dumps(marker) + ", caseNo, got)\n"
            "    caseNo++\n"
            "  } } }\n"
            "}\n"
        )
    return (
        "// @ts-nocheck\n"
        "const solution = require(\"./solution\");\n"
        "const solve = solution.solve;\n"
        "const describe = solution.describe;\n"
        f"const schema: any = {spec};\n"
        f"const groups: any = {blob};\n"
        "function renameTree(value: any, keys: any, values: any): any {\n"
        "  if (Array.isArray(value)) return value.map((item) => renameTree(item, keys, values));\n"
        "  if (value && typeof value === \"object\") {\n"
        "    const out: any = {};\n"
        "    for (const key of Object.keys(value)) out[keys[key] || key] = renameTree(value[key], keys, values);\n"
        "    return out;\n"
        "  }\n"
        "  if (typeof value === \"string\" && values[value]) return values[value];\n"
        "  return value;\n"
        "}\n"
        "function identity(map: any): boolean {\n"
        "  return !!map && Object.keys(map).every((key) => map[key] === key);\n"
        "}\n"
        "(async () => {\n"
        "  let doc: any = null;\n"
        "  try { doc = describe(); if (doc && typeof doc.then === \"function\") doc = await doc; } catch { doc = null; }\n"
        "  const ok = doc && doc.trace && doc.trace.dup === \"DUP\" && identity(doc.keys) !== undefined;\n"
        "  console.log(" + json.dumps(marker) + " + \" DESCRIBE \" + JSON.stringify(doc));\n"
        "  let caseNo = 0;\n"
        "  for (const group of groups) for (const batch of group) for (const input of batch) {\n"
        "    let got: any = null;\n"
        "    if (ok) {\n"
        "      try {\n"
        "        const same = identity(doc.keys) && identity(doc.actions) && identity(doc.states);\n"
        "        const values = Object.assign({}, doc.actions, doc.states);\n"
        "        const data = same ? input : renameTree(JSON.parse(JSON.stringify(input)), doc.keys, values);\n"
        "        const old = console.log; console.log = () => {};\n"
        "        got = solve(data);\n"
        "        if (got && typeof got.then === \"function\") got = await got;\n"
        "        console.log = old;\n"
        "      } catch { console.log = () => {}; }\n"
        "    }\n"
        "    let encoded = \"null\"; try { encoded = JSON.stringify(got); } catch {}\n"
        "    console.log(" + json.dumps(marker) + " + ` CASE ${caseNo} ${encoded}`);\n"
        "    caseNo++;\n"
        "  }\n"
        "})();\n"
    )


def _score(item_id, text, language):
    from .coding_facts import FACTS
    from .coding_score import score_answer
    from .runtime_profiles import RuntimeProfileError, environment_for_item
    try:
        _profile_hash, runtime = environment_for_item(item_id, language)
    except RuntimeProfileError as exc:
        status = "missing" if exc.reason == "missing" else "error"
        return {"status": status, "passed": None, "points": None, "score10": None, "reason_code": "runtime_" + exc.reason, "detail": str(exc)}
    return score_answer(text, language, item_id=item_id, groups=cases(item_id), schema=_SCHEMAS[item_id], facts=FACTS[item_id], fixture=_fixture, runtime=runtime)


def coding_items():
    return tuple(Challenge(i,_TITLES[i],"coding",_doc_prompt(i,"python"),{},"stateful contract", "extreme") for i in _FUNCS)


def prompt(item_id,language="python"): return _doc_prompt(item_id,language)
def score_saved(item_id,text,language="python"): return _score(item_id,text,language)


def reference_source(item_id, language="python"):
    """Return a runnable reference answer for local scorer and contract tests."""
    if item_id not in _FUNCS:
        raise KeyError(item_id)
    if language not in {"python", "go", "typescript"}:
        raise ValueError(f"unsupported language: {language}")
    import inspect
    if language in {"go", "typescript"}:
        return _table_reference_source(item_id, language)
    from .describe_contract import identity_document
    fn = _FUNCS[item_id]
    helpers = "from copy import deepcopy\n\n" + inspect.getsource(_dups) + "\n" + inspect.getsource(_envelope) + "\n"
    document = "def describe():\n    return " + repr(identity_document(_SCHEMAS[item_id])) + "\n\n"
    src = helpers + document + inspect.getsource(fn)
    return src.replace(f"def {fn.__name__}(", "def solve(", 1)


def _reference_table(item_id: str) -> dict[str, Any]:
    """Build a canonical input -> output table for non-Python reference code.

    The fixtures are the executable contract for all three language runners.
    Keeping this table generated from the same frozen cases avoids translating
    ten state machines by hand while still exercising the real Go/TS compiler,
    entrypoint and JSON transport in the reference smoke tests.
    """
    table: dict[str, Any] = {}
    for group in cases(item_id):
        for batch in group:
            for case in batch:
                key = json.dumps(case.data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                value = deepcopy(case.expected)
                previous = table.setdefault(key, value)
                if previous != value:
                    raise AssertionError(f"fixture input has conflicting expected values: {item_id}")
    return table


def _table_reference_source(item_id: str, language: str) -> str:
    table = _reference_table(item_id)
    if language == "go":
        encoded = {
            key: json.dumps(value, ensure_ascii=True, separators=(",", ":"))
            for key, value in table.items()
        }
        from .describe_contract import identity_document
        described = json.dumps(identity_document(_SCHEMAS[item_id]), ensure_ascii=True, separators=(",", ":"))
        return (
            "package solution\n\n"
            "import \"encoding/json\"\n\n"
            f"var referenceTable = {json.dumps(encoded, ensure_ascii=True, separators=(',', ':'))}\n\n"
            f"func Describe() json.RawMessage {{ return []byte({json.dumps(described)}) }}\n\n"
            "func Solve(input json.RawMessage) json.RawMessage {\n"
            "    var value any\n"
            "    if err := json.Unmarshal(input, &value); err != nil { return []byte(\"null\") }\n"
            "    canonical, err := json.Marshal(value)\n"
            "    if err != nil { return []byte(\"null\") }\n"
            "    if output, ok := referenceTable[string(canonical)]; ok { return json.RawMessage(output) }\n"
            "    return []byte(\"null\")\n"
            "}\n"
        ).replace("var referenceTable = {", "var referenceTable = map[string]string{")
    from .describe_contract import identity_document
    encoded = json.dumps(table, ensure_ascii=True, separators=(",", ":"))
    described = json.dumps(identity_document(_SCHEMAS[item_id]), ensure_ascii=True, separators=(",", ":"))
    return (
        f"export function describe(): any {{ return {described}; }}\n"
        "function canonical(value: any): any {\n"
        "  if (Array.isArray(value)) return value.map(canonical);\n"
        "  if (value !== null && typeof value === 'object') {\n"
        "    const out: any = {};\n"
        "    for (const key of Object.keys(value).sort()) out[key] = canonical(value[key]);\n"
        "    return out;\n"
        "  }\n"
        "  return value;\n"
        "}\n"
        f"const referenceTable: Record<string, any> = {encoded};\n"
        "export function solve(data: any): any {\n"
        "  const value = referenceTable[JSON.stringify(canonical(data))];\n"
        "  return value === undefined ? null : value;\n"
        "}\n"
    )


def reference_answer(item_id, data):
    return _FUNCS[item_id](deepcopy(data))
