import json
import math
from itertools import permutations

from eval_bank_20260925.next_reasoning import ITEMS, reference_answer, render_reasoning_prompt, score_reasoning


def test_next_reasoning_has_ten_frozen_executable_fixtures():
    assert [item.item_id for item in ITEMS] == [f"NX-{n:02d}" for n in range(9, 19)]
    for item in ITEMS:
        assert item.prompt
        result = score_reasoning(item.item_id, json.dumps(item.answer, ensure_ascii=False))
        assert result["status"] == "pass"
        assert result["passed"] is True
        assert result["points"] == result["points_total"] == 20
        assert result["score10"] == 10.0


def test_next_reasoning_is_mechanical_and_partial():
    item = ITEMS[0]
    malformed = score_reasoning(item.item_id, "explanation")
    assert malformed["status"] == "fail"
    assert malformed["points"] == 0
    partial = dict(item.answer)
    partial["last_end"] = -1
    result = score_reasoning(item.item_id, json.dumps(partial))
    assert result["status"] == "fail"
    assert result["points"] == 16
    assert result["passed"] is False


def test_nx12_tie_uses_id_order_and_nx16_is_not_copying_demand():
    route = reference_answer("NX-12")
    assert route["route"] == ["A", "B", "C"]
    assert route["total"] == 19
    old = dict(route, route=["B", "A", "C"], arrivals=[["B", 5], ["A", 13], ["C", 19]], late=["A", "C"])
    assert score_reasoning("NX-12", json.dumps(old))["points"] == 4
    stock = reference_answer("NX-16")
    assert stock["buy"] == [8, 0, 4]
    copied = dict(stock, buy=[4, 6, 4], sold=[4, 6, 4], profit=56)
    assert score_reasoning("NX-16", json.dumps(copied))["points"] < 20
    locks = dict(reference_answer("NX-11"), locks=[{"order": "O1", "batch": "A", "qty": 3}, {"order": "O2", "batch": "B", "qty": 3}])
    assert score_reasoning("NX-11", json.dumps(locks))["points"] == 20


def test_next_reasoning_prompt_has_json_contract_and_business_facts():
    prompt = render_reasoning_prompt("NX-17")
    assert "只输出一个 JSON 对象" in prompt
    assert "closed_edge_at_departure" in prompt
    assert "预算 8" in prompt
    assert "若首段在出发时封闭，reason 使用 closed_edge_at_departure。" not in prompt


def _assign_rooms(patients, rooms, emergency_minutes, clean_minutes):
    free_at = {room: 0 for room in rooms}
    disinfect = {}
    remaining = sorted(patients, key=lambda row: (row[1], row[0]))
    waiting, served, infectious = [], [], []
    index = now = 0
    while index < len(remaining) or waiting:
        if not waiting and index < len(remaining):
            now = max(now, remaining[index][1])
        while index < len(remaining) and remaining[index][1] <= now:
            waiting.append(remaining[index])
            index += 1
        open_rooms = [room for room in rooms if free_at[room] <= now]
        ready = sorted((row for row in waiting if row[1] <= now), key=lambda row: (not row[2], row[1], row[0]))
        if open_rooms and ready:
            room = open_rooms[0]
            patient = ready[0]
            waiting.remove(patient)
            end = now + (emergency_minutes if patient[2] else clean_minutes)
            if patient[3]:
                free_at[room] = end + 3
                disinfect[room] = end + 3
                infectious.append(room)
            else:
                free_at[room] = end
            served.append([patient[0], room, now, end])
            continue
        nxt = [row[1] for row in remaining[index:index + 1]]
        nxt += [moment for moment in free_at.values() if moment > now]
        if not nxt:
            break
        now = min(nxt)
    served.sort(key=lambda row: (row[2], row[1]))
    waiting_ids = [row[0] for row in sorted(waiting, key=lambda row: (row[1], row[0]))]
    last_end = max((row[3] for row in served), default=0)
    return served, waiting_ids, last_end, sorted(set(infectious)), disinfect


def test_nx09_idle_room_takes_arrived_emergency():
    served, waiting, last_end, infectious, _disinfect = _assign_rooms(
        [("A", 0, False, False), ("B", 1, True, True), ("C", 1, False, False), ("D", 6, True, False)],
        ("R1", "R2"), 8, 5,
    )
    answer = reference_answer("NX-09")
    assert answer["served"] == served
    assert answer["waiting"] == waiting == []
    assert answer["last_end"] == last_end == 18
    assert answer["infectious_rooms"] == infectious == ["R2"]
    assert [row for row in served if row[0] == "D"] == [["D", "R1", 10, 18]]


def _charge_plan():
    reservations = {"P1": (3, 5), "P2": (0, 2)}
    power = {"P1": 2, "P2": 3}
    vehicles = [("V1", 0, 4, 4), ("V2", 1, 3, 6), ("V3", 2, 3, 4)]
    occupied = {pile: [] for pile in power}

    def rate(minute):
        return 3 if 2 <= minute < 4 else 1

    def blocked(pile, start, end):
        windows = [reservations[pile], *occupied[pile]]
        return any(start < stop and end > begin for begin, stop in windows)

    assign, rejected = [], []
    for name, arrive, energy, deadline in vehicles:
        best = None
        for pile, watts in power.items():
            duration = math.ceil(energy / watts)
            for start in range(arrive, deadline - duration + 1):
                end = start + duration
                if blocked(pile, start, end):
                    continue
                fee = sum(rate(minute) for minute in range(start, end))
                candidate = (fee, end, pile, start)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            rejected.append(name)
            continue
        fee, end, pile, start = best
        occupied[pile].append((start, end))
        assign.append([name, pile, start, end, fee])
    return {"assign": assign, "rejected": rejected, "total_cost": sum(row[4] for row in assign)}


def test_nx10_picks_each_vehicles_cheapest_window():
    answer = reference_answer("NX-10")
    assert answer == _charge_plan()
    assert ["V1", "P2", 2, 4, 6] not in answer["assign"]
    assert answer["total_cost"] == sum(row[4] for row in answer["assign"])


def test_nx14_peak_cost_sums_minutes_inside_the_window():
    answer = reference_answer("NX-14")

    def rate(minute):
        if minute < 3:
            return 2
        if minute < 8:
            return 1
        return 3

    peak = 0
    for _name, _pile, start, end, cost in answer["schedule"]:
        assert sum(rate(minute) for minute in range(start, end)) == cost
        peak += sum(rate(minute) for minute in range(start, end) if minute < 3)
    assert answer["peak_cost"] == peak == 10


def test_nx15_emergency_takes_b1_and_disinfect_matches_that_bed():
    served, waiting, _last_end, _infectious, disinfect = _assign_rooms(
        [("P1", 0, False, True), ("P2", 0, True, False), ("P3", 4, True, True), ("P4", 9, False, False)],
        ("B1", "B2"), 8, 5,
    )
    answer = reference_answer("NX-15")
    assert answer["beds"] == served
    assert answer["waiting"] == waiting == []
    assert served[0][:2] == ["P2", "B1"]
    assert [row[1] for row in served if row[0] == "P1"] == ["B2"]
    by_id = {row[0]: row for row in served}
    assert answer["disinfect_until"][by_id["P1"][1]] == by_id["P1"][3] + 3
    assert answer["disinfect_until"][by_id["P3"][1]] == by_id["P3"][3] + 3
    assert answer["disinfect_until"] == disinfect
    assert answer["emergency_wait"] == (by_id["P2"][2] - 0) + (by_id["P3"][2] - 4)


def _paths_open_at_departure():
    edges = {
        "A": [("B", 4, 3), ("C", 2, 5)],
        "B": [("D", 4, 3)],
        "C": [("B", 1, 2), ("D", 8, 1)],
        "D": [],
    }
    closed = {("A", "C")}
    found = []

    def walk(node, path, minutes, fee):
        if node == "D":
            found.append((path, minutes, fee))
            return
        for nxt, step, price in edges[node]:
            if (node, nxt) in closed or (nxt, node) in closed:
                continue
            if fee + price > 8 or nxt in path:
                continue
            walk(nxt, path + [nxt], minutes + step, fee + price)

    walk("A", ["A"], 0, 0)
    found.sort(key=lambda row: (row[1], row[2], row[0]))
    return found


def test_nx17_open_first_edge_does_not_use_closed_reason_or_wait():
    prompt = render_reasoning_prompt("NX-17")
    assert prompt.count("closed_edge_at_departure") == 1
    feasible = _paths_open_at_departure()
    best, *rest = feasible
    answer = reference_answer("NX-17")
    assert answer["path"] == best[0] == ["A", "B", "D"]
    assert answer["path"][:2] == ["A", "B"]
    assert [answer["arrive"], answer["cost"]] == [best[1], best[2]]
    assert answer["alternatives"] == [[list(path), minutes, fee] for path, minutes, fee in rest]
    assert answer["reason"] == ""
    assert all(row[0][:2] != ["A", "C"] for row in answer["alternatives"])
    assert [[["A", "C", "D"], 15, 6]] != answer["alternatives"]


def _delivery(route):
    meta = {"A": ("L2", 0, 15), "B": ("L1", 0, 8), "C": ("L2", 4, 20)}
    floors = {"L1": 2, "L2": 6}
    clock = walk = 0
    arrivals, late = [], []
    for order_id in route:
        building, ready, deadline = meta[order_id]
        clock = max(clock, ready) + 2
        if building == "L2" and 3 <= clock < 10:
            ascent = floors[building] * 2
            walk += ascent
        else:
            ascent = floors[building]
        clock += ascent
        arrivals.append([order_id, clock])
        if clock > deadline:
            late.append(order_id)
    return clock, arrivals, late, walk


def test_nx18_minimum_completion_does_not_add_downstairs_time():
    ranked = sorted(((_delivery(route)[0], route) for route in permutations(("A", "B", "C"))))
    best_clock, best_route = ranked[0]
    assert best_route == ("A", "B", "C")
    assert _delivery(("B", "A", "C"))[0] > best_clock
    clock, arrivals, late, walk = _delivery(best_route)
    answer = reference_answer("NX-18")
    assert answer["route"] == list(best_route)
    assert answer["arrivals"] == arrivals
    assert answer["late"] == late == ["B"]
    assert answer["elevator_walk"] == walk == 0
    assert arrivals[-1][1] == clock == 20
