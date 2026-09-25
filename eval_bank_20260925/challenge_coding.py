"""20260925 编程题：复杂业务契约，小规模固定行为集。"""

from copy import deepcopy
from functools import lru_cache
import inspect
from pathlib import Path
import secrets
import tempfile

from .challenge import Challenge
from . import challenge_refs as ref
from .cases import Case
from .runner import (
    _score_case_results,
    go_result_fixture,
    python_result_fixture,
    ts_result_fixture,
)
from src.grade import grade_response
from src.types import Question


SPECS = [
    ("CP-01", "订单事件处理与库存补偿", "order_processor", """\
入口契约：评测把你的代码写入 solution.py，并执行 from solution import solve；必须提供 def solve(data)，接收一个字典并返回 JSON 兼容字典。事件统一为对象，字段如下：RESERVE {op,id,order,lines:[[sku,qty],...]}; PAY/SHIP/CANCEL {op,id,order}; SNAPSHOT {op,id}; RESTORE {op,id,snapshot}。id 是全局幂等键，第一次失败也占用；重复事件 trace 为 "DUP"。RESERVE 先合并同 SKU，再整体校验；数量必须为正整数，失败 trace 为 "REJECT" 且库存不变；成功及合法 PAY/SHIP/CANCEL trace 为 "OK"。不存在订单、重复订单或非法迁移 trace 为 "INVALID"。状态流转 RESERVED→PAID→SHIPPED；CANCEL 只允许 RESERVED/PAID，释放全部预留并清空行。SNAPSHOT 在当前业务状态保存不可变快照并 trace 为 "SNAP"；RESTORE 只按已保存 snapshot 恢复库存和订单并 trace 为 "RESTORE"，未知快照为 "INVALID"。恢复不会回退已占用的事件 id，也不会删除快照。RETURN {op,id,order,lines} 只允许 SHIPPED，否则 INVALID。先按 RESERVE 合并同 SKU，每段数量必须为正整数，合并后不能为空，且每个 SKU 不得超过订单当前行数量，否则 REJECT，订单和库存都不变。成功 trace 为 OK：数量加回库存，订单行扣减并删除扣到 0 的 SKU，状态保持 SHIPPED，因此不能再 PAY、SHIP 或 CANCEL。返回 trace、非零库存 inventory（按 SKU 排序）、orders（按订单号排序；订单行按 SKU 排序，CANCELED 行为空）。
公开例：{"initial":{"a":2},"events":[{"op":"RESERVE","id":"r","order":"o","lines":[["a",1]]},{"op":"PAY","id":"p","order":"o"}]} → {"trace":["OK","OK"],"inventory":[["a",1]],"orders":[["o","PAID",[["a",1]]]]}。禁止工具、网络、文件和子进程。""", ("idempotency", "atomic_reserve", "state_machine", "compensation", "history_restore")),
    ("CP-02", "带租约与迟到回执的任务队列", "task_queue", """\
入口契约同本题库：必须提供 def solve(data)。输入 tasks=[{id,priority,ready,max_attempts}]、正整数 lease、events 数组；每个事件都是对象：POLL {op,worker,now}、ACK/FAIL {op,worker,task,token,now}、CANCEL {op,task,now}、TICK {op,now}。处理任一事件前，所有 until<=now 的 RUNNING 任务先过期：attempts 已达到 max_attempts 变 DEAD，否则回 PENDING；过期释放 worker，迟到或 worker/token 不匹配的 ACK/FAIL trace 为 "STALE"。tasks 可含 depends（id 数组，缺省为空）。POLL 只选 ready<=now、且每个 depends 都已经是 DONE 的 PENDING；前置是 PENDING、RUNNING、CANCELED、DEAD 或未知 id 都不算完成。循环依赖时相关任务都不能被领取，后继也不会因此变成 CANCELED 或 DEAD。候选人按 priority 降序、ready 升序、id 字典序；领取时 attempts+1，token=id+":"+attempts，until=now+lease；同一 worker 已持有任务或无任务 trace 为 null。ACK trace "OK" 并变 DONE；合法 FAIL 在仍有次数时 trace "RETRY" 并回 PENDING，否则 trace "DEAD"；CANCEL 可取消 PENDING/RUNNING，trace "OK"（释放 worker），其余 "INVALID"；TICK trace "OK"。返回按事件顺序的 trace 和按 id 排序的 tasks=[id,state,attempts]。所有事件均需显式 now；now 只影响本事件及此前已到期租约。
公开例：{"lease":3,"tasks":[{"id":"a","priority":1,"ready":0,"max_attempts":2}],"events":[{"op":"POLL","worker":"w","now":0}]} → {"trace":["a:1"],"tasks":[["a","RUNNING",1]]}。""", ("priority", "lease", "stale_ack", "retry_dead", "cancel_workers")),
    ("CP-03", "角色继承与动态权限判定", "permission_engine", """\
入口契约同本题库：必须提供 def solve(data)。roles 是 role→父角色数组，users 是 user→角色数组；events 统一为数组编码：["ADD",rule_id,rule]、["REMOVE",rule_id]、["SETROLE",role,parents]、["CHECK",user,action,resource,time]。SETROLE 立即替换该角色的父角色数组，只影响后续 CHECK；循环继承合法，CHECK 每次都重新计算闭包。rule 必须含 effect(allow/deny)、role、action（精确字符串或 "*"）、resource（"*"、精确字符串，或以 "*" 结尾的单段通配）、可选 start/end；缺 start 视为负无穷，缺 end 视为正无穷，时间区间为 [start,end)。模式 "*" 匹配任意资源；其他以 "*" 结尾的模式去掉末尾星号得到前缀，只匹配「前缀 + 恰好一段且该段不含冒号」：doc:* 匹配 doc:1，不匹配 doc:1:2，也不匹配 doc:。CHECK 沿继承闭包去重；deny 只否决实际适用的规则，不适用的宽规则不能否决。没有 deny 时，allow 按 resource 精确优先于单段通配、再优先于 "*"，然后 action 精确优先于 "*"；同一优先级有 allow 即 ALLOW，否则 DENY。ADD 同 id 替换，REMOVE 未知 id 无操作。只返回 CHECK 的 ALLOW/DENY 数组。
公开例：{"roles":{"admin":["viewer"],"viewer":[]},"users":{"u":["admin"]},"events":[["ADD","r",{"effect":"allow","role":"viewer","action":"read","resource":"doc:*"}],["CHECK","u","read","doc:1",0],["CHECK","u","write","doc:1",0]]} → ["ALLOW","DENY"]。""", ("inheritance", "deny_precedence", "wildcard_specificity", "time_window", "dynamic_rules")),
    ("CP-04", "多环境配置发布计划", "release_plan", """\
入口契约同本题库：必须提供 def solve(data)，返回 {status,order,config,conflicts}。environment 缺省为 "prod"；base 与 overlays[environment] 先合并。changes 是对象数组 {id,service,env,set,delete,after}：env 缺省表示当前环境，"*" 表示所有环境；set 是 key→value，delete 是 key 数组，after 缺省为空；rollback 中 id 和其他环境的 change 忽略。dependencies[s] 列出服务 s 必须先完成的服务，约束到该服务的全部已选 changes；层内按 change id 字典序。依赖环返回 {status:"CYCLE",order:[],config:[],conflicts:[]}。conflicts 为排序后的 [id,id] 对，不能取最后值；相同写入不冲突。env 为具体环境的写入比 "*" 更具体，而且与 order 无关。某个服务的某个 key 只要存在具体环境写入，所有 "*" 写入都忽略该 key，双方不算冲突；"*" 写的其他 key 仍生效。回滚掉的 change 不参与这比较。只有同一档（都是具体环境，或在没有具体写入时都是 "*"）里、没有传递先后、且写入不同（set 的值不同，或一方 set 一方 delete），才 CONFLICT。无冲突时按 order 依次 delete 后 set。成功 status="OK"，config 按 service、key 排序；conflicts 为空。
公开例：{"environment":"prod","base":{"api":{"port":80}},"overlays":{"prod":{"api":{"port":443}}},"dependencies":{},"changes":[{"id":"x","service":"api","set":{"debug":true},"delete":[]}],"rollback":[]} → {"status":"OK","order":["x"],"config":[["api",[["debug",true],["port",443]]]],"conflicts":[]}。""", ("overlay", "dependency_order", "rollback_filter", "conflict_detection", "atomic_result")),
    ("CP-05", "批量结算与可逆冲正", "ledger", """\
入口契约同本题库：必须提供 def solve(data)。accounts 是账户→整数余额，treasury 缺省为 "_fees"；events 统一为数组编码：["BATCH",batch_id,rows] 或 ["REVERSE",operation_id,tx_id]。row 固定为 [tx_id,from,to,amount,fee]；amount>0、fee>=0、账户存在且 from!=to。BATCH/REVERSE 各自幂等，第一次失败也占用 id；重复 trace="DUP"。BATCH 先在临时余额中原子校验，成功 trace="OK" 且交易 SETTLED，失败 trace="REJECT" 且不写入；REVERSE 只能冲正 SETTLED 一次，成功 "OK"、未知/已冲正/余额不足 "INVALID"，原路退回 amount+fee 并扣回 to/treasury。成功记为 REVERSED 的 tx_id 立即释放，之后的 BATCH 可以再次使用并重新成为 SETTLED，也能再次冲正。冲正失败或 REJECT 的批次都不释放 tx_id；仍为 SETTLED 的 tx_id 再出现会使该 BATCH REJECT。REVERSE 的 operation id 不释放。返回 trace、非零 balances（名称排序）和 transactions=[tx_id,state]（id 排序）。
公开例：{"accounts":{"a":10,"b":0},"treasury":"fee","events":[["BATCH","b1",[["t","a","b",3,1]]]]} → {"trace":["OK"],"balances":[["a",6],["b",3],["fee",1]],"transactions":[["t","SETTLED"]]}。""", ("batch_atomicity", "duplicate_ids", "fee_accounting", "reversal", "balance_contract")),
    ("CP-06", "乱序事件窗口与撤回聚合", "event_aggregate", """\
入口契约同本题库：必须提供 def solve(data)。window 为正数；events 统一为数组编码：["INGEST",event_id,entity,timestamp,value]、["RETRACT",operation_id,event_id]、["AMEND",operation_id,event_id,timestamp,value]、["SEAL",operation_id,entity,timestamp]、["QUERY",entity,timestamp]、["SNAPSHOT"]。首次 INGEST 固定 event_id 内容，重复不覆盖。RETRACT 的 operation_id 首次出现即占用（即使 event_id 未知），已知事件撤回后永久无效；重复 operation_id 无效果。AMEND 的 operation_id 也首次占用；只有已知且当前有效的事件可以修订 timestamp/value，entity 不变，修订立即影响后续 QUERY/SNAPSHOT；未知、已撤回或重复 operation_id 都无效果。SEAL 与 RETRACT、AMEND 共用 operation_id，首次出现即占用，重复无效果。它用与 QUERY 相同的向下取整封住该 entity 的一个窗口，不封住该时间之后的其他窗口，也不追溯：封窗前已经写入且当前有效的事件继续有效；封窗之后新 INGEST 进该窗口只占用 event_id 并保持无效。无效事件不能 AMEND。AMEND 在事件当前窗口或目标窗口已被封装时不修改数据。其他 entity 不受影响。窗口为 [floor(timestamp/window)*window,start+window)，允许负时间和乱序到达；QUERY 只看当前有效且 entity 相同、落在该窗口的事件，返回 {entity,start,count,sum,ids}；SNAPSHOT 返回所有非空窗口同形对象数组，按 entity、start 排序。只返回 QUERY/SNAPSHOT 的结果数组。
公开例：{"window":10,"events":[["INGEST","e","a",1,3],["QUERY","a",1]]} → [{"entity":"a","start":0,"count":1,"sum":3,"ids":["e"]}]。""", ("dedup", "half_open_window", "late_events", "retraction", "snapshot_order")),
    ("CP-07", "资源约束下的稳定调度", "resource_schedule", """\
入口契约同本题库：必须提供 def solve(data)。workers 为正整数，resources 为资源→容量；jobs 为 {id,release,duration,priority,deadline,needs,deps}，cancel 为 {id,time} 数组；可选 blackouts 为全局维护半开区间 [start,end)。可选 budgets 是池到可消耗时长的映射，job 可含 pool。没有 pool 不消耗预算。成功启动时立刻扣减 duration，完成、取消和未能启动都不归还；pool 不在 budgets 中时剩余视为 0。duration 大于剩余就跳过该任务并继续尝试下一个，不能让它挡住后面仍能运行的任务。RUNNING 任务不受后来黑窗影响；新任务只有在整个 [t,t+duration) 不与任何 blackouts 重叠时才能在 t 启动，若当前时刻被阻塞则跳到下一个黑窗边界或其他事件时刻。worker 在输出中使用从 0 开始的整数槽位。时间从 0 开始按整数推进：先完成 end==t，再取消该时刻仍 PENDING 的任务（RUNNING 不受影响），再给空闲 worker 分配；可运行须 release<=t 且所有 deps 已 DONE，按 priority 降序、deadline 升序、id 升序尝试，资源冲突时继续尝试后续任务。不可抢占，资源按容量计数。无可运行任务时跳到下一个 release 或完成时刻；若剩余 PENDING 因依赖缺失/循环、容量永远不足、预算永远不够或永远落在维护黑窗内而无法运行，立即终止，保留 PENDING，不等待无限时间。schedule=[id,start,end,worker,late]，late 为 end>deadline；states 按 id 为 [id,DONE/CANCELED/PENDING]。
公开例：{"workers":1,"resources":{},"jobs":[{"id":"a","release":0,"duration":2,"priority":1,"deadline":3,"needs":[],"deps":[]}],"cancel":[]} → {"schedule":[["a",0,2,0,false]],"states":[["a","DONE"]]}。""", ("dependency_release", "resource_capacity", "stable_priority", "cancel_boundary", "deadline_output")),
    ("CP-08", "分阶段规则引擎与写冲突", "rule_engine", """\
入口契约同本题库：必须提供 def solve(data)。facts 为 key→值，rules 为对象数组 {id,phase,priority,when,set,add,remove,stop}；phase 缺省 "main"，priority 缺省 0，when 缺省视为 false（需显式条件才命中）。阶段 pre、main、post，阶段内 priority 降序、id 升序。when 递归支持 all/any/not，叶子 op 为 exists/eq/neq/in/contains/gte/lte/changed。changed 只和本阶段开始时的事实比较：存在性或值不同才为真。它不是粘滞标记，改回阶段开始状态后即为假，上一阶段的变化也不会留到下一阶段。同值 set、重复 add、删除不存在字段均不算改变，初始 facts 不算 changed。同一阶段里尚未改回时，后面的规则看得到 changed。例如 pre 把 x 从 1 改成 2 之后，main 的 changed x 为假。同一 main 内先删除 x 时 changed x 为真；把 x 设回阶段开始的值之后，后面的 changed x 为假。删除没有发生 set，所以这次设回不算写冲突。谓词读取当前 facts 与已发生的变化。命中规则记录 fired，按 set、add、remove 执行。相同阶段同 key 已由更高或更早同优先级规则 set 时，后续不同值不覆盖且 conflicts 记 [先id,后id,key]；相同值无冲突；不同阶段不冲突。add 列表追加去重，remove 删除字段；stop 命中后停止后续所有规则。只单次按排序规则执行，不隐式重跑。返回 facts=[key,value]（key 排序）、fired、conflicts、stopped。
公开例：{"facts":{"n":1},"rules":[{"id":"r","phase":"main","priority":1,"when":{"op":"eq","field":"n","value":1},"set":{"ok":true},"add":{},"remove":[]}]} → {"facts":[["n",1],["ok",true]],"fired":["r"],"conflicts":[],"stopped":false}。""", ("nested_predicates", "phase_priority", "write_conflict", "list_actions", "stop_boundary")),
]


def coding_items(seed=92501):
    levels = {"CP-01": "hard", "CP-02": "hard", "CP-03": "extreme", "CP-04": "extreme", "CP-05": "extreme", "CP-06": "extreme", "CP-07": "extreme", "CP-08": "extreme"}
    return tuple(Challenge(qid, title, "coding", prompt + "\n每次调用独立，禁止工具、网络、文件和子进程；只输出一个 python 代码围栏。得分分为五个等权组：" + ",".join(groups) + "，每组 4 分。", {}, "复杂业务状态与规则交互；输入保持小规模，区分度来自契约组合。", levels[qid]) for qid, title, _, prompt, groups in SPECS)


def reference_source(item_id):
    spec = next(s for s in SPECS if s[0] == item_id)
    source = inspect.getsource(getattr(ref, spec[2]))
    return source.replace("def " + spec[2] + "(", "def solve(", 1)


@lru_cache(None)
def cases(item_id, seed=92501):
    """Return frozen CP goldens; expected values never come from challenge_refs."""
    if seed != 92501:
        raise ValueError("CP goldens are fixed to seed 92501")
    from .challenge_goldens_v09 import golden_cases
    return [
        [[Case(deepcopy(data), deepcopy(expected))] for data, expected in group]
        for group in golden_cases(item_id)
    ]


def score_saved(item_id, text, seed=92501, language="python"):
    factory, filename = {"python": (python_result_fixture, "test.py"), "go": (go_result_fixture, "test_test.go"), "typescript": (ts_result_fixture, "test.ts")}[language]
    marker = "__MODEL_LENS_FIXTURE_" + secrets.token_hex(12) + "__"
    with tempfile.TemporaryDirectory(prefix="challenge-grade-") as temporary:
        root = Path(temporary); path = root / "bank" / "tests" / filename; path.parent.mkdir(parents=True)
        path.write_text(factory(cases(item_id, seed), marker), encoding="utf-8")
        q = Question(id=item_id, domain="coding", difficulty="extreme", prompt="", grader={"type": "code_tests", "language": language, "tests_file": str(path.relative_to(root)), "result_marker": marker}, pass_criteria="20/20", language=language)
        score = grade_response(q, text, repo_root=root)
    group_names = next((spec[4] for spec in SPECS if spec[0] == item_id), None)
    if group_names is None:
        raise KeyError(item_id)
    definitions = tuple((name, 4) for name in group_names)
    case_score = _score_case_results(
        item_id, cases(item_id, seed), score.detail, language, group_defs=definitions
    )
    if case_score is not None:
        return case_score.to_dict()
    if score.status == "missing":
        reason_code = "missing_toolchain" if "toolchain" in score.detail else "missing_fence"
    elif score.status == "pass":
        reason_code = "ok"
    elif "timeout" in score.detail:
        reason_code = "timeout"
    elif "compile" in score.detail:
        reason_code = "compile_error"
    elif "forbidden import" in score.detail:
        reason_code = "forbidden_import"
    elif score.detail.startswith("FIXTURE_RESULT"):
        reason_code = "tests_failed"
    else:
        reason_code = "execution_error"
    return {
        "status": score.status,
        "passed": score.passed,
        "points": score.points,
        "score10": score.score10,
        "reason_code": reason_code,
        "detail": score.detail,
    }
