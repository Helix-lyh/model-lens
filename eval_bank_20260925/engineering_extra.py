"""E-02..E-06 的可执行工程题：案例、独立 oracle、参考实现和评分适配。"""
from __future__ import annotations

import json
import inspect
import tempfile
from pathlib import Path

from src.grade import grade_response
from src.types import Question


CASES = {
"E-02": [
 {"name":"replay","events":[{"op":"CREATE","merchant":"m","order":"o","amount":10},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PAID","event_id":"e1","signature":"ok"},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PAID","event_id":"e1","signature":"ok"},{"op":"GET","merchant":"m","order":"o"}]},
 {"name":"stale","events":[{"op":"CREATE","merchant":"m","order":"o","amount":10},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PAID","event_id":"e1","signature":"ok"},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PENDING","event_id":"e2","signature":"ok"},{"op":"GET","merchant":"m","order":"o"}]},
 {"name":"bad_signature","events":[{"op":"CREATE","merchant":"m","order":"o","amount":10},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PAID","event_id":"e1","signature":"bad"},{"op":"GET","merchant":"m","order":"o"}]},
 {"name":"tenant","events":[{"op":"CREATE","merchant":"a","order":"o","amount":10},{"op":"CREATE","merchant":"b","order":"o","amount":20},{"op":"CALLBACK","merchant":"b","order":"o","amount":20,"state":"PAID","event_id":"e2","signature":"ok"},{"op":"GET","merchant":"a","order":"o"},{"op":"GET","merchant":"b","order":"o"}]},
 {"name":"refund","events":[{"op":"CREATE","merchant":"m","order":"o","amount":10},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"PAID","event_id":"e1","signature":"ok"},{"op":"CALLBACK","merchant":"m","order":"o","amount":10,"state":"REFUNDED","event_id":"e2","signature":"ok"},{"op":"GET","merchant":"m","order":"o"}]},
],
"E-03": [
 {"name":"reserve","events":[{"op":"STOCK","tenant":"a","sku":"s","quantity":5},{"op":"RESERVE","tenant":"a","sku":"s","quantity":3,"reservation_id":"r"},{"op":"GET","tenant":"a","sku":"s"}]},
 {"name":"retry","events":[{"op":"STOCK","tenant":"a","sku":"s","quantity":5},{"op":"RESERVE","tenant":"a","sku":"s","quantity":3,"reservation_id":"r"},{"op":"RESERVE","tenant":"a","sku":"s","quantity":3,"reservation_id":"r"},{"op":"GET","tenant":"a","sku":"s"}]},
 {"name":"release","events":[{"op":"STOCK","tenant":"a","sku":"s","quantity":5},{"op":"RESERVE","tenant":"a","sku":"s","quantity":3,"reservation_id":"r"},{"op":"RELEASE","tenant":"a","sku":"s","reservation_id":"r"},{"op":"GET","tenant":"a","sku":"s"}]},
 {"name":"expire","events":[{"op":"STOCK","tenant":"a","sku":"s","quantity":5},{"op":"RESERVE","tenant":"a","sku":"s","quantity":3,"reservation_id":"r"},{"op":"EXPIRE","tenant":"a","sku":"s","reservation_id":"r"},{"op":"GET","tenant":"a","sku":"s"}]},
 {"name":"tenant","events":[{"op":"STOCK","tenant":"a","sku":"s","quantity":2},{"op":"STOCK","tenant":"b","sku":"s","quantity":4},{"op":"RESERVE","tenant":"a","sku":"s","quantity":2,"reservation_id":"r"},{"op":"GET","tenant":"b","sku":"s"}]},
],
"E-04": [
 {"name":"erase","events":[{"op":"PUT","tenant":"a","doc_id":"d","content":"secret"},{"op":"ERASE","tenant":"a","doc_id":"d","request_id":"x"},{"op":"READ","tenant":"a","doc_id":"d"}]},
 {"name":"retry","events":[{"op":"PUT","tenant":"a","doc_id":"d","content":"x"},{"op":"ERASE","tenant":"a","doc_id":"d","request_id":"x"},{"op":"ERASE","tenant":"a","doc_id":"d","request_id":"x"},{"op":"READ","tenant":"a","doc_id":"d"}]},
 {"name":"ledger","events":[{"op":"PUT","tenant":"a","doc_id":"d","content":"x"},{"op":"CHARGE","tenant":"a","doc_id":"d","amount":7},{"op":"ERASE","tenant":"a","doc_id":"d"},{"op":"AUDIT","tenant":"a","doc_id":"d"}]},
 {"name":"tenant","events":[{"op":"PUT","tenant":"a","doc_id":"d","content":"a-secret"},{"op":"PUT","tenant":"b","doc_id":"d","content":"b-secret"},{"op":"ERASE","tenant":"a","doc_id":"d"},{"op":"READ","tenant":"b","doc_id":"d"}]},
 {"name":"audit","events":[{"op":"PUT","tenant":"a","doc_id":"d","content":"private"},{"op":"ERASE","tenant":"a","doc_id":"d"},{"op":"AUDIT","tenant":"a","doc_id":"d"}]},
],
"E-05": [
 {"name":"dependency","events":[{"op":"SUBMIT","tenant":"a","task_id":"a"},{"op":"SUBMIT","tenant":"a","task_id":"b","depends_on":"a"},{"op":"START","tenant":"a","task_id":"b"},{"op":"COMPLETE","tenant":"a","task_id":"a"},{"op":"START","tenant":"a","task_id":"b"},{"op":"GET","tenant":"a","task_id":"b"}]},
 {"name":"retry","events":[{"op":"SUBMIT","tenant":"a","task_id":"a"},{"op":"START","tenant":"a","task_id":"a"},{"op":"FAIL","tenant":"a","task_id":"a"},{"op":"START","tenant":"a","task_id":"a"},{"op":"FAIL","tenant":"a","task_id":"a"},{"op":"GET","tenant":"a","task_id":"a"}]},
 {"name":"cancel","events":[{"op":"SUBMIT","tenant":"a","task_id":"a"},{"op":"CANCEL","tenant":"a","task_id":"a"},{"op":"COMPLETE","tenant":"a","task_id":"a"},{"op":"GET","tenant":"a","task_id":"a"}]},
 {"name":"duplicate","events":[{"op":"SUBMIT","tenant":"a","task_id":"a"},{"op":"START","tenant":"a","task_id":"a"},{"op":"COMPLETE","tenant":"a","task_id":"a"},{"op":"COMPLETE","tenant":"a","task_id":"a"},{"op":"GET","tenant":"a","task_id":"a"}]},
 {"name":"tenant","events":[{"op":"SUBMIT","tenant":"a","task_id":"a"},{"op":"SUBMIT","tenant":"a","task_id":"b"},{"op":"START","tenant":"a","task_id":"a"},{"op":"START","tenant":"a","task_id":"b"},{"op":"GET","tenant":"a","task_id":"b"}]},
],
"E-06": [
 {"name":"approval","events":[{"op":"PROPOSE","env":"prod","key":"k","version":1,"value":"a"},{"op":"PUBLISH","env":"prod","key":"k","version":1},{"op":"READ","env":"prod","key":"k"}]},
 {"name":"publish","events":[{"op":"PROPOSE","env":"prod","key":"k","version":1,"value":"a"},{"op":"APPROVE","env":"prod","key":"k","version":1,"approved":True},{"op":"PUBLISH","env":"prod","key":"k","version":1},{"op":"READ","env":"prod","key":"k"}]},
 {"name":"rollback","events":[{"op":"PROPOSE","env":"prod","key":"k","version":1,"value":"a"},{"op":"APPROVE","env":"prod","key":"k","version":1,"approved":True},{"op":"PUBLISH","env":"prod","key":"k","version":1},{"op":"PROPOSE","env":"prod","key":"k","version":2,"value":"b"},{"op":"APPROVE","env":"prod","key":"k","version":2,"approved":True},{"op":"PUBLISH","env":"prod","key":"k","version":2},{"op":"ROLLBACK","env":"prod","key":"k","version":1},{"op":"READ","env":"prod","key":"k"}]},
 {"name":"environment","events":[{"op":"PROPOSE","env":"staging","key":"k","version":1,"value":"s"},{"op":"APPROVE","env":"staging","key":"k","version":1,"approved":True},{"op":"PUBLISH","env":"staging","key":"k","version":1},{"op":"READ","env":"prod","key":"k"}]},
 {"name":"retry","events":[{"op":"PROPOSE","env":"prod","key":"k","version":1,"value":"a","request_id":"x"},{"op":"PROPOSE","env":"prod","key":"k","version":1,"value":"a","request_id":"x"},{"op":"READ","env":"prod","key":"k"}]},
],
}


def evaluate(item_id, name, rows):
    rows = rows if isinstance(rows, list) else []
    def r(i): return rows[i] if -len(rows) <= i < len(rows) and isinstance(rows[i], dict) else {}
    violations=[]
    if item_id == "E-02":
        checks = {"replay": r(-1).get("status")=="PAID", "stale": r(-1).get("status")=="PAID", "bad_signature": r(-1).get("status")=="PENDING" and r(1).get("ok") is False, "tenant": r(-2).get("status")=="PENDING" and r(-1).get("status")=="PAID", "refund": r(-1).get("status")=="REFUNDED"}
        labels = {"replay":["idempotent_replay","stable_query"],"stale":["monotonic_state","no_regression"],"bad_signature":["signature_fail_closed","rejection_shape"],"tenant":["tenant_isolation","amount_binding"],"refund":["refund_transition","terminal_state"]}
        if name=="bad_signature" and r(1).get("ok") is True: violations.append("signature_bypass")
    elif item_id == "E-03":
        checks = {"reserve":r(-1).get("available")==2,"retry":r(-1).get("available")==2,"release":r(-1).get("available")==5,"expire":r(-1).get("available")==5,"tenant":r(-1).get("available")==4}
        labels = {"reserve":["reservation_consistency","available_quantity"],"retry":["idempotent_reserve","no_double_debit"],"release":["release_consistency","terminal_release"],"expire":["expiry_release","timeout_recovery"],"tenant":["tenant_isolation","per_tenant_stock"]}
        if name=="tenant" and r(-1).get("available") != 4: violations.append("tenant_stock_bleed")
        if any(isinstance(x, dict) and isinstance(x.get("available"), (int, float)) and x["available"] < 0 for x in rows): violations.append("oversell")
    elif item_id == "E-04":
        text=json.dumps(rows, ensure_ascii=False)
        checks={"erase":r(-1).get("found") is False,"retry":r(-1).get("found") is False,"ledger":r(-1).get("amount")==7,"tenant":r(-1).get("content")=="b-secret","audit":"private" not in text}
        labels={"erase":["erasure_visibility","content_inaccessible"],"retry":["idempotent_erasure","stable_delete"],"ledger":["ledger_retention","amount_reconciliation"],"tenant":["tenant_isolation","cross_tenant_protection"],"audit":["audit_minimization","audit_continuity"]}
        if name in {"erase","audit"} and (r(-1).get("found") is True or "secret" in text or "private" in text): violations.append("content_exposure")
    elif item_id == "E-05":
        checks={"dependency":r(2).get("ok") is False and r(-1).get("state") in {"RUNNING","SUCCEEDED"},"retry":r(-1).get("state") in {"RETRY","FAILED"},"cancel":r(-1).get("state")=="CANCELED","duplicate":r(-1).get("state")=="SUCCEEDED" and r(2).get("run_count",0)==r(3).get("run_count",0),"tenant":r(-1).get("state") in {"QUEUED","RUNNING"}}
        labels={"dependency":["dependency_gate","blocked_before_dependency"],"retry":["retry_bound","failure_state"],"cancel":["cancel_suppression","terminal_cancel"],"duplicate":["idempotent_completion","single_side_effect"],"tenant":["tenant_quota","fair_start"]}
        if name=="dependency" and r(2).get("ok") is True: violations.append("dependency_bypass")
        if name=="cancel" and r(-1).get("state") != "CANCELED": violations.append("late_completion_resurrection")
    else:
        checks={"approval":r(-1).get("value") is None,"publish":r(-1).get("value")=="a","rollback":r(-1).get("value")=="a","environment":r(-1).get("value") is None,"retry":r(-1).get("value") is None}
        labels={"approval":["approval_gate","unapproved_hidden"],"publish":["publish_visibility","approved_value"],"rollback":["rollback_restore","version_selection"],"environment":["environment_isolation","default_hidden"],"retry":["idempotent_proposal","stable_proposal"]}
        if name=="approval" and r(-1).get("value") == "a": violations.append("unapproved_publish")
        if name=="environment" and r(-1).get("value") is not None: violations.append("environment_bleed")
    covered=labels[name] if checks.get(name) else []
    gaps=[] if checks.get(name) else labels[name]
    return {"covered":covered,"gaps":gaps,"violations":violations}


REFS = {
"E-02": '''def solve(events):
    orders={}; seen=set(); out=[]; rank={"PENDING":0,"PAID":1,"REFUNDED":2}
    for e in events:
        k=(e.get("merchant"),e.get("order")); op=e.get("op")
        if op=="CREATE": orders[k]={"status":"PENDING","amount":e.get("amount")}; out.append({"ok":True,"status":"PENDING"})
        elif op=="CALLBACK":
            x=orders.setdefault(k,{"status":"PENDING","amount":e.get("amount")}); ok=e.get("signature")=="ok"
            if ok and e.get("event_id") not in seen and e.get("amount")==x["amount"] and rank.get(e.get("state"),-1)>=rank[x["status"]]: x["status"]=e.get("state"); seen.add(e.get("event_id"))
            out.append({"ok":ok,"status":x["status"]})
        elif op=="GET": out.append({"ok":True,"status":orders.get(k,{"status":"PENDING"})["status"]})
        else: out.append({"ok":False})
    return out''',
"E-03": '''def solve(events):
    stock={}; holds={}; out=[]
    for e in events:
        k=(e.get("tenant"),e.get("sku")); op=e.get("op")
        if op=="STOCK": stock[k]=e.get("quantity",0); out.append({"ok":True,"available":stock[k]})
        elif op=="RESERVE":
            h=holds.get(e.get("reservation_id"));
            if h: out.append({"ok":True,"available":stock[k]})
            elif stock.get(k,0)>=e.get("quantity",0): stock[k]-=e["quantity"]; holds[e["reservation_id"]]=(k,e["quantity"],"HELD"); out.append({"ok":True,"available":stock[k]})
            else: out.append({"ok":False,"available":stock.get(k,0)})
        elif op in {"RELEASE","EXPIRE"}: h=holds.get(e.get("reservation_id")); stock[h[0]]+=h[1] if h and h[2]=="HELD" else 0; holds[e.get("reservation_id")]=(h[0],h[1],"RELEASED") if h else h; out.append({"ok":bool(h),"available":stock.get(k,0)})
        elif op=="CONFIRM": h=holds.get(e.get("reservation_id")); holds[e.get("reservation_id")]=(h[0],h[1],"CONFIRMED") if h else h; out.append({"ok":bool(h),"available":stock.get(k,0)})
        elif op=="GET": out.append({"ok":True,"available":stock.get(k,0)})
        else: out.append({"ok":False})
    return out''',
"E-04": '''def solve(events):
    docs={}; ledger={}; erased=set(); out=[]
    for e in events:
        k=(e.get("tenant"),e.get("doc_id")); op=e.get("op")
        if op=="PUT": docs[k]=e.get("content"); out.append({"ok":True})
        elif op=="READ": out.append({"ok":True,"found":k in docs,"content":docs.get(k)})
        elif op=="ERASE": erased.add(k); docs.pop(k,None); out.append({"ok":True})
        elif op=="CHARGE": ledger[k]=ledger.get(k,0)+e.get("amount",0); out.append({"ok":True})
        elif op=="AUDIT": out.append({"ok":True,"amount":ledger.get(k,0),"erased":k in erased})
        else: out.append({"ok":False})
    return out''',
"E-05": '''def solve(events):
    tasks={}; out=[]
    for e in events:
        k=(e.get("tenant"),e.get("task_id")); t=tasks.setdefault(k,{"state":"QUEUED","run_count":0,"depends_on":e.get("depends_on")}); op=e.get("op")
        if op=="SUBMIT": t["depends_on"]=e.get("depends_on"); out.append({"ok":True,"state":t["state"]})
        elif op=="START": dep=tasks.get((e.get("tenant"),t.get("depends_on"))); ok=not dep or dep["state"]=="SUCCEEDED"; t["state"]="RUNNING" if ok and t["state"] not in {"CANCELED","SUCCEEDED"} else t["state"]; t["run_count"]+=1 if ok and t["state"]=="RUNNING" else 0; out.append({"ok":ok,"state":t["state"],"run_count":t["run_count"]})
        elif op=="FAIL": t["state"]="RETRY" if t["run_count"]<2 else "FAILED"; out.append({"ok":True,"state":t["state"]})
        elif op=="CANCEL": t["state"]="CANCELED"; out.append({"ok":True,"state":t["state"]})
        elif op=="COMPLETE": t["state"]="SUCCEEDED" if t["state"]!="CANCELED" else t["state"]; out.append({"ok":True,"state":t["state"],"run_count":t["run_count"]})
        elif op=="GET": out.append({"ok":True,"state":t["state"],"run_count":t["run_count"]})
        else: out.append({"ok":False})
    return out''',
"E-06": '''def solve(events):
    vals={}; approved=set(); active={}; out=[]
    for e in events:
        k=(e.get("env"),e.get("key"),e.get("version")); op=e.get("op")
        if op=="PROPOSE": vals[k]=e.get("value"); out.append({"ok":True})
        elif op=="APPROVE": approved.add(k) if e.get("approved") else None; out.append({"ok":True})
        elif op=="PUBLISH": ok=k in approved; active[(e.get("env"),e.get("key"))]=e.get("version") if ok else active.get((e.get("env"),e.get("key"))); out.append({"ok":ok})
        elif op=="ROLLBACK": active[(e.get("env"),e.get("key"))]=e.get("version"); out.append({"ok":True})
        elif op=="READ": v=active.get((e.get("env"),e.get("key"))); out.append({"ok":True,"value":vals.get((e.get("env"),e.get("key"),v)) if v is not None else None})
        else: out.append({"ok":False})
    return out''',
}


def extra_fixture(marker, item_id):
    blob=json.dumps(CASES[item_id], ensure_ascii=False, separators=(",", ":"))
    source=inspect.getsource(evaluate)
    return f'''import contextlib,copy,io,json
{source}
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 from solution import solve
reports=[]
for case in json.loads({blob!r}):
 try:
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()): out=solve(copy.deepcopy(case["events"]))
 except BaseException: out=[]
 reports.append({{"name":case["name"],**evaluate({item_id!r},case["name"],out)}})
covered=sorted({{x for r in reports for x in r["covered"]}}); violations=sorted({{x for r in reports for x in r["violations"]}})
print({marker!r}+" POINTS "+str(len(covered))+"/10")
print({marker!r}+" ENGINEERING "+json.dumps({{"covered":covered,"violations":violations,"reports":reports}},ensure_ascii=False))
'''


def score_extra(item_id, text):
    marker="__MODEL_LENS_"+item_id.replace("-","")+"_"
    with tempfile.TemporaryDirectory(prefix="engineering-extra-") as d:
        root=Path(d); p=root/"bank/tests"; p.mkdir(parents=True); (p/"tests.py").write_text(extra_fixture(marker,item_id))
        q=Question(id=item_id,domain="engineering",difficulty="extreme",prompt="",grader={"type":"code_tests","language":"python","tests_file":"bank/tests/tests.py","result_marker":marker},pass_criteria="10 positive obligations and no negative debt",language="python")
        g=grade_response(q,text,repo_root=root)
    line=next((x for x in g.detail.splitlines() if x.startswith("ENGINEERING ")),"")
    try: report=json.loads(line[len("ENGINEERING "):])
    except (ValueError,TypeError): report={"covered":[],"reports":[],"unobserved":["execution_error"]}
    covered=sorted(set(report.get("covered",[]))); violations=sorted(set(report.get("violations",[]))); total=10
    negative=len(violations); risk={"critical":negative,"high":0,"medium":0,"weighted_points":negative*6}
    return {"status":"pass" if len(covered)==total and not violations else "fail","passed":len(covered)==total and not violations,"obligations":{"covered":len(covered),"total":total,"gap":max(0,total-len(covered)),"unobserved":len(report.get("unobserved",[]))},"obligations_covered":covered,"obligations_total":total,"risk_debt":risk,"positive_points":len(covered),"negative_points":negative,"net_points":len(covered)-negative,"prohibitions_triggered":violations,"reports":report.get("reports",[])}
