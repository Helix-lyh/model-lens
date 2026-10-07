"""Executable 20261008 reasoning fixtures and mechanical scorers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .score import parse_json, strict_equal


@dataclass(frozen=True)
class ReasoningSpec:
    item_id: str
    title: str
    prompt: str
    answer: dict[str, Any]
    groups: tuple[tuple[str, int], ...]


def _spec(item_id, title, prompt, answer, groups):
    return ReasoningSpec(item_id, title, prompt.strip(), answer, groups)


_SPECS = (
    _spec("NX-09", "门诊双台与感染清场", """
门诊分诊台安排 A、B、C、D 四名患者。房间 R1、R2 初始在 0 分钟空闲，每个房间一次只能接诊一人。普通服务 5 分钟，急诊服务 8 分钟；感染患者结束后该房间清场 3 分钟，清场期间不可接诊。患者事件（时间单位为分钟）：`A arrive=0 normal clean`、`B arrive=1 emergency infectious`、`C arrive=1 normal clean`、`D arrive=6 emergency clean`。每当房间可用时，先选已到达的急诊患者，再选普通患者；同级按到达时间、id 排序；两个房间同时可用时先选 R1。输出 JSON：`served` 为 `[id,room,start,end]` 列表，按 start、room 排序；另有 `waiting`、`last_end`、`infectious_rooms`。""", {"served":[["A","R1",0,5],["B","R2",1,9],["C","R1",5,10],["D","R1",10,18]],"waiting":[],"last_end":18,"infectious_rooms":["R2"]}, (("served",10),("waiting",2),("last_end",4),("infectious_rooms",4))),
    _spec("NX-10", "充电峰谷和预约占用", """
桩 P1 功率 2、P2 功率 3，预约占用 `P1:[3,5)`、`P2:[0,2)`。车辆 `V1 arrive=0 energy=4 deadline=4`、`V2 arrive=1 energy=3 deadline=6`、`V3 arrive=2 energy=3 deadline=4`。充电时长为 `ceil(energy/power)`；预约区间不可充电。每辆车选择能在 deadline 前完成的桩，总费最低者优先，同费按完成时刻、桩号排序；峰时段 `[2,4)` 每分钟 3，其余每分钟 1。输出 `assign`（`[vehicle,pile,start,end,cost]`，按车辆顺序）、`rejected`、`total_cost`。""", {"assign":[["V1","P1",0,2,2],["V2","P2",4,5,1],["V3","P2",2,3,3]],"rejected":[],"total_cost":6}, (("assign",12),("rejected",3),("total_cost",5))),
    _spec("NX-11", "冷链批次与装车窗口", """
批次 `A qty=4 expiry=5`、`B qty=3 expiry=8`，expiry 时刻起不可锁定；装车窗口为半开区间 `[4,7)`，容量 6。订单事件 `O1 t=3 qty=3`、`O2 t=4 qty=3`、`LOAD t=5`、`O3 t=6 qty=2`。请求时从未锁定库存中锁定 `expiry>请求时刻` 的最早批次，不能拆批次。LOAD 按请求时刻和 id 装载已锁定订单，容量不足的订单保持 locked；窗口外的 LOAD 失败。输出 `locks`、`loaded`、`free:{A,B}`、`rejected`。""", {"locks":[["O1","A",3],["O2","B",3]],"loaded":["O1","O2"],"free":{"A":1,"B":0},"rejected":["O3"]}, (("locks",8),("loaded",4),("free",4),("rejected",4))),
    _spec("NX-12", "电梯停运下的外卖路线", """
骑手从 W（0 层）出发，W 与每个楼宇之间、以及相邻两个订单楼宇之间各有一段道路。`rain at0`；雨天每段道路 4 分钟。订单 `A` 在 2 层、deadline 10，`B` 在 1 层、deadline 8，`C` 在 2 层、deadline 18，均 `ready=0`。电梯事件 `down L2 at3`、`up L2 at10`；电梯每层 1 分钟，停运时步行每层 2 分钟。到达楼宇时读取当刻的电梯状态；选择总完成时刻最小的顺序，同刻按 id；deadline 只记录 late，不阻止执行。输出 `route`、`arrivals`（`[id,time]`）、`late`、`total`。""", {"route":["B","A","C"],"arrivals":[["B",5],["A",13],["C",19]],"late":["A","C"],"total":19}, (("route",4),("arrivals",8),("late",4),("total",4))),
    _spec("NX-13", "航班延误与机组时限", """
航段 F1 `09:00-10:30`、F2 `10:50-12:00`、F3 `11:20-13:00`，以当天 0 点起的分钟数计。机组 C1 可从 08:00 开始执勤、上限 360 分钟；C2 从 09:30 开始、上限 300 分钟。转场至少 20 分钟。事件：`delay F1 +40`、`close F2 at 10:45`。航段只能由一组机组执行；按原计划优先保留 C1，若到达、转场或上限不满足则改选 C2，否则取消。输出 `flights`（`[id,crew,start,end]`）、`cancelled`、`duty`、`last_end`。""", {"flights":[["F1","C1",540,670],["F3","C2",680,780]],"cancelled":["F2"],"duty":{"C1":130,"C2":100},"last_end":780}, (("flights",10),("cancelled",3),("duty",5),("last_end",2))),
    _spec("NX-14", "充电站峰值排队", """
桩 S1、S2 功率均为 1。费率 `[0,3)` 为 2、`[3,8)` 为 1、`[8,∞)` 为 3。车辆 `A arrive=0 energy=4 priority=1`、`B arrive=1 energy=2 priority=2`、`C arrive=2 energy=3 priority=1`。每当桩空闲，从已到达车辆中选 priority 最高者，同级按到达时间、id；充电不可抢占。费用按每分钟所属费率累加。输出 `schedule`（`[id,pile,start,end,cost]`，按 start、桩号排序）、`peak_cost`（`[0,3)` 内的费用）、`finish_order`（按结束时刻、id）。""", {"schedule":[["A","S1",0,4,7],["B","S2",1,3,4],["C","S2",3,6,3]],"peak_cost":10,"finish_order":["B","A","C"]}, (("schedule",12),("peak_cost",4),("finish_order",4))),
    _spec("NX-15", "传染病房空台时间", """
床 B1、B2 初始空闲。普通服务 5 分钟，急诊 8 分钟；感染患者离床后清洁 3 分钟，清洁完成床位才可用。患者 `P1 t=0 normal infectious`、`P2 t=0 emergency clean`、`P3 t=4 emergency infectious`、`P4 t=9 normal clean`。每当床位可用，先选已到达的急诊，再选普通；同级按到达时间、id；两床同时可用时先选 B1。输出 `beds`（`[id,bed,start,end]`）、`waiting`、`disinfect_until`、`emergency_wait`（急诊患者从到达到开始的总分钟数）。""", {"beds":[["P2","B1",0,8],["P1","B2",0,5],["P3","B1",8,16],["P4","B2",9,14]],"waiting":[],"disinfect_until":{"B1":19,"B2":8},"emergency_wait":4}, (("beds",12),("waiting",2),("disinfect_until",4),("emergency_wait",2))),
    _spec("NX-16", "水果采购与热天损耗", """
库容 8；普通日需求 4、热天需求 6；售价 10、进价 6。库存按天结算：当天先销售旧货再销售新货；热天当天新进的货在销售后全部报废；普通日未售库存可留到下一天，第二天开店前过期。三天依次为 `normal`、`hot`、`normal`。每天开店前决定进货量，不能超过容量和当天需求；目标最大化三天利润。输出 `buy`、`sold`、`waste`（三个数组长度均为 3）和 `profit`（收入 − 成本）。""", {"buy":[4,6,4],"sold":[4,6,4],"waste":[0,0,0],"profit":56}, (("buy",6),("sold",6),("waste",4),("profit",4))),
    _spec("NX-17", "换乘预算和封路", """
站点 A、B、C、D。边 `A-B(4,3)`、`A-C(2,5)`、`C-B(1,2)`、`B-D(4,3)`、`C-D(8,1)`，括号内为分钟数和费用。预算 8；出发时刻 0。`A-C` 在 t0 封闭、t5 开放。只可使用出发时开放、且累计费用不超过预算的路径；已出发的边不受后续封路影响。目标按最早到达、最低费用、站点字典序依次比较。输出 `path`、`arrive`、`cost`、`alternatives`（`[path,arrive,cost]`，按到达、费用、路径排序）、`reason`；首段在出发时即封闭用 `reason=closed_edge_at_departure`，没有预算内可行路径用 `reason=no_budget_path`。""", {"path":["A","B","D"],"arrive":8,"cost":6,"alternatives":[],"reason":""}, (("path",4),("arrive",3),("cost",3),("alternatives",8),("reason",2))),
    _spec("NX-18", "冷藏配送和电梯停运", """
骑手从 W 出发，W 与每个楼宇之间、以及连续两个订单楼宇之间各有一段道路，每段 2 分钟。楼宇 L1 为 2 层、L2 为 6 层；电梯每层 1 分钟，停运时步行每层 2 分钟。`L2` 在 t3 停运、t10 恢复。订单 `A L2 ready=0 deadline=15`、`B L1 ready=0 deadline=8`、`C L2 ready=4 deadline=20`。未到 ready 不能出发，必要时等待；选择总完成时刻最小的顺序，同刻按 id；到达楼宇时读取当刻的电梯状态；deadline 只产生 late，不阻止执行。输出 `route`、`arrivals`（`[id,time]`）、`late`、`elevator_walk`。""", {"route":["A","B","C"],"arrivals":[["A",8],["B",12],["C",20]],"late":["B"],"elevator_walk":0}, (("route",4),("arrivals",8),("late",4),("elevator_walk",4))),
)

ITEMS = _SPECS
BY_ID = {item.item_id: item for item in ITEMS}


def reasoning_items():
    return ITEMS


def render_reasoning_prompt(item_id: str) -> str:
    prompt = BY_ID[item_id].prompt
    return "你只能依据题面作答，只输出一个 JSON 对象，不要解释或增加字段。\n" + prompt


def score_reasoning(item_id: str, text: str) -> dict[str, Any]:
    item = BY_ID[item_id]
    try:
        data = parse_json(text)
    except (ValueError, TypeError, RecursionError):
        return {"status":"fail","reason_code":"format_error","passed":False,"points":0,"points_total":20,"score10":0.0,"protocol_ok":False,"groups":[]}
    protocol = isinstance(data, dict) and set(data) == set(item.answer)
    points = 0
    groups = []
    for name, maximum in item.groups:
        earned = maximum if strict_equal(data.get(name), item.answer[name]) else 0
        points += earned
        groups.append({"name":name,"points":earned,"max":maximum})
    passed = protocol and points == 20
    return {"status":"pass" if passed else "fail","reason_code":"ok" if passed else ("content_mismatch" if protocol else "schema_mismatch"),"passed":passed,"points":points,"points_total":20,"score10":round(points / 2, 4),"protocol_ok":protocol,"groups":groups}


def reference_answer(item_id: str) -> dict[str, Any]:
    return BY_ID[item_id].answer
