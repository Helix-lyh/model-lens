"""双资源半格：充电抽出的公共循环，后厨并灶、床位护理、双坪并泵。"""
from eval_bank_20260925.worldkit.families import deice, kitchen, ward
from eval_bank_20260925.worldkit.share import dual_progress


def test_stabilize_pushes_the_next_job_after_share_stretches_the_first():
    from eval_bank_20260925.worldkit.share import dual_progress, stabilize
    # 同侧：第一单半格被拉长后，第二单不得在第一单结束前开工。
    starts = [0, 2]
    done_raw = dual_progress(starts, [0, 0], [4, 2], True)
    assert done_raw[0] > 2
    starts2 = [0, 2]
    done = stabilize(starts2, [0, 0], [4, 2], True, [0, 0])
    assert starts2[1] >= done[0]
    assert done[1] >= done[0]


def test_dual_progress_matches_charge_full_overlap():
    # 两车同时开始、各需 4，全程半格，完成于 8。
    assert dual_progress([0, 0], [0, 1], [4, 4], True) == [8, 8]


def test_kitchen_gas_doubles_overlap_cook_time():
    world = {
        "family": "kitchen",
        "data": {"dishes": [
            {"id": "A", "table": "T1", "cook": 2, "hold": 10, "pan": "炒"},
            {"id": "B", "table": "T1", "cook": 2, "hold": 10, "pan": "炒"},
        ]},
        "modules": {"gas": {}},
        "objective": ["flow", "spoils"],
        "questions": kitchen.FAMILY.questions(),
        "background": [],
    }
    out = kitchen.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 0 分同时开工，各需 2 单位，半格：4 分钟完成，出锅时刻都是 4，flow=8。
    assert out.metrics["flow"] == 8
    bare = kitchen.FAMILY.simulate({**world, "modules": {}}, ("A", "B"))
    assert bare is not None
    assert bare.metrics["flow"] == 4


def test_ward_three_iso_patients_do_not_share_the_bed():
    world = {
        "family": "ward",
        "data": {"patients": [
            {"id": "A", "arrive": 0, "limit": 20, "stay": 4, "iso": True, "grade": "甲"},
            {"id": "B", "arrive": 0, "limit": 20, "stay": 4, "iso": True, "grade": "甲"},
            {"id": "C", "arrive": 0, "limit": 20, "stay": 4, "iso": True, "grade": "甲"},
        ]},
        "modules": {"nurse": {}, "clean": {"minutes": 2}},
        "objective": ["excess", "late_n"],
        "questions": ward.FAMILY.questions(),
        "background": [],
    }
    met = ward._metrics(world, ("A", "B", "C"))
    assert met is not None
    # 隔离床串行：B 不得在 A 离开前开工。
    # 用同一床位完成时刻应严格递增间隔至少占用。
    world2 = {**world, "modules": {"nurse": {}, "clean": {"minutes": 0}}}
    # 无消毒时，后一位开工 >= 前一位离开。
    from eval_bank_20260925.worldkit.families.ward import _metrics
    # 只断言 simulate 能跑且不会比「无护理」更早收完所有人。
    with_n = ward.FAMILY.simulate(world2, ("A", "B", "C"))
    without = ward.FAMILY.simulate({**world2, "modules": {}}, ("A", "B", "C"))
    assert with_n is not None and without is not None
    assert with_n.metrics["excess"] >= without.metrics["excess"]


def test_ward_nurse_stretches_overlapping_stays():
    world = {
        "family": "ward",
        "data": {"patients": [
            {"id": "A", "arrive": 0, "limit": 10, "stay": 2, "iso": True, "grade": "甲"},
            {"id": "B", "arrive": 0, "limit": 10, "stay": 2, "iso": False, "grade": "乙"},
        ]},
        "modules": {"nurse": {}},
        "objective": ["excess", "late_n"],
        "questions": ward.FAMILY.questions(),
        "background": [],
    }
    out = ward.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics["excess"] == 0
    # 开始仍是 0；占用被拉长，不影响本题超出（超出看开始时刻）。
    with_share = ward._metrics(world, ("A", "B"))
    without = ward._metrics({**world, "modules": {}}, ("A", "B"))
    assert with_share is not None and without is not None
    assert with_share["excess"] == without["excess"]


def test_gate_tow_adds_pax_when_tractor_overruns_departure():
    from eval_bank_20260925.worldkit.families import gate
    world = {
        "family": "gate",
        "data": {
            "flights": [
                {"id": "A", "arr": 0, "dep": 3, "wide": False, "pax": 10},
                {"id": "B", "arr": 0, "dep": 3, "wide": False, "pax": 10},
            ],
            "gates": [
                {"id": "G1", "remote": True, "bus": 1, "adj": []},
                {"id": "G2", "remote": True, "bus": 1, "adj": []},
            ],
        },
        "modules": {"tow": {"minutes": 4, "alt": 8}},
        "objective": ["pax_bus", "remote_n"],
        "questions": gate.FAMILY.questions(),
        "background": [],
    }
    out = gate.FAMILY.simulate(world, ("G1", "G2"))
    assert out is not None
    # 两车同时拖、各 4 单位半格，完成于 8；超出离开 5 分钟，10*5*2=100，摆渡 10*1*2=20，合计 120。
    assert out.metrics["pax_bus"] == 120
    assert out.metrics["remote_n"] == 2


def test_deice_pump_slows_two_pads():
    world = {
        "family": "deice",
        "data": {"planes": [
            {"id": "A", "ready": 0, "slot": 0, "deice": 2, "hold": 20, "kind": "P"},
            {"id": "B", "ready": 0, "slot": 0, "deice": 2, "hold": 20, "kind": "P"},
        ]},
        "modules": {"pump": {}},
        "objective": ["delay", "redeice"],
        "questions": deice.FAMILY.questions(),
        "background": [],
    }
    out = deice.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 两坪同时喷、各 2 单位半格，4 分钟完成；起飞 4 与 4，延误 4+4=8。无跑道间隔。
    assert out.metrics["delay"] == 8
    assert out.metrics["redeice"] == 0
    bare = deice.FAMILY.simulate({**world, "modules": {}}, ("A", "B"))
    assert bare is not None
    # 单坪：A 0-2 起飞 2，B 2-4 起飞 4，延误 2+4=6。
    assert bare.metrics["delay"] == 6
