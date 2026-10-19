"""赋值/波次题族的手算轨迹：滞后降容、共用最长绿灯、分资源溢出。"""
from eval_bank_20260925.worldkit import render
from eval_bank_20260925.worldkit.families import cycle, ramp, shift, triage


def test_shift_lag_taxes_whole_shift_and_setup_adds_occupancy():
    world = {
        "family": "shift",
        "data": {
            "n_waves": 2,
            "wave_end": [10, 20],
            "cap": 6,
            "lines": [{"id": "X"}, {"id": "Y"}],
            "jobs": [
                {"id": "A", "seq": 0, "family": "P", "minutes": 4, "due": 12},
                {"id": "B", "seq": 1, "family": "Q", "minutes": 4, "due": 12},
            ],
        },
        "modules": {"lag": {"k": 1, "slow": 10, "alt": 2}, "setup": {"minutes": 2}},
        "objective": ["over", "late_n"],
        "questions": shift.FAMILY.questions(),
        "background": [],
    }
    piled = shift.FAMILY.simulate(world, ("A1X", "B1X"))
    assert piled is not None
    # A 占用 4；B 换族 +2 占用 6；第 1 班占用 10>6，两笔完成 20。逾期 8+8，超额 4，再加两笔各计一次超额 → 8。
    assert piled.metrics == {"over": 24, "late_n": 2}
    split = shift.FAMILY.simulate(world, ("A1X", "B1Y"))
    assert split is not None
    assert split.metrics == {"over": 0, "late_n": 0}
    lagged = shift.FAMILY.simulate(world, ("A1X", "B2X"))
    assert lagged is not None
    # 第 2 班有效容量 6-4=2，B 占用 6>2，完成 30。逾期 18，A 超额 0、B 超额 4。
    assert lagged.metrics == {"over": 22, "late_n": 1}
    assert render.leaks(render.render_prompt(shift.FAMILY, world)) == []


def test_cycle_shared_slot_takes_max_green_not_sum():
    world = {
        "family": "cycle",
        "data": {
            "n_slots": 2,
            "slot_start": [0, 20],
            "greens": {"S": 10, "L": 20},
            "headway": 5,
            "miss": 15,
            "streams": [
                {"id": "A", "name": "南北直行", "n": 4},
                {"id": "B", "name": "东西直行", "n": 4},
            ],
        },
        "modules": {"share": {}, "offset": {"phase": "A", "lo": 0, "hi": 10, "alt_lo": 20, "alt_hi": 30}},
        "objective": ["delay", "wait_n"],
        "questions": cycle.FAMILY.questions(),
        "background": [],
    }
    piled = cycle.FAMILY.simulate(world, ("A1L", "B1L"))
    assert piled is not None
    # 同槽绿灯取 20，容量 4，8 辆多余 4，延误 60。
    assert piled.metrics == {"delay": 60, "wait_n": 4}
    split = cycle.FAMILY.simulate(world, ("A1L", "B2S"))
    assert split is not None
    # B 在 20 秒时段，容量 2，多余 2，延误 30+80。
    assert split.metrics == {"delay": 110, "wait_n": 2}
    assert cycle.FAMILY.simulate(world, ("A2L", "B1L")) is None
    summed = cycle.FAMILY.simulate({**world, "modules": {"offset": world["modules"]["offset"]}}, ("A1L", "B1L"))
    assert summed is not None
    assert summed.metrics["wait_n"] == 0
    assert render.leaks(render.render_prompt(cycle.FAMILY, world)) == []


def test_triage_overflow_stays_on_one_bed_and_mix_adds_occupancy():
    world = {
        "family": "triage",
        "data": {
            "n_slots": 2,
            "slot_end": [10, 20],
            "beds": [{"id": "N"}, {"id": "I"}],
            "patients": [
                {"id": "A", "seq": 0, "grade": "隔离", "care": 4, "limit": 12},
                {"id": "B", "seq": 1, "grade": "普通", "care": 4, "limit": 12},
            ],
        },
        "modules": {"slot": {"cap": 6}, "mix": {"extra": 3, "alt": 8}},
        "objective": ["excess", "late_n"],
        "questions": triage.FAMILY.questions(),
        "background": [],
    }
    piled = triage.FAMILY.simulate(world, ("A1I", "B1I"))
    assert piled is not None
    # B 交叉 +3 占用 7：第 1 时段剩 2，余 5 挤进第 2 时段，完成 20。超出 8。
    assert piled.metrics == {"excess": 8, "late_n": 1}
    split = triage.FAMILY.simulate(world, ("A1I", "B1N"))
    assert split is not None
    assert split.metrics == {"excess": 0, "late_n": 0}
    assert render.leaks(render.render_prompt(triage.FAMILY, world)) == []


def test_ramp_overflow_stays_on_one_tractor_and_zone_adds_occupancy():
    world = {
        "family": "ramp",
        "data": {
            "n_waves": 2,
            "wave_end": [10, 20],
            "tractors": [{"id": "X"}, {"id": "Y"}],
            "flights": [
                {"id": "A", "seq": 0, "dep": 12, "tow": 4, "zone": "东"},
                {"id": "B", "seq": 1, "dep": 12, "tow": 4, "zone": "西"},
            ],
        },
        "modules": {"wave": {"cap": 6}, "zone": {"minutes": 3, "alt": 8}},
        "objective": ["flow", "late_n"],
        "questions": ramp.FAMILY.questions(),
        "background": [],
    }
    piled = ramp.FAMILY.simulate(world, ("A1X", "B1X"))
    assert piled is not None
    # B 换区 +3 占用 7，完成 20。总完成 10+20，误点 1 架。
    assert piled.metrics == {"flow": 30, "late_n": 1}
    split = ramp.FAMILY.simulate(world, ("A1X", "B1Y"))
    assert split is not None
    assert split.metrics == {"flow": 20, "late_n": 0}
    assert render.leaks(render.render_prompt(ramp.FAMILY, world)) == []
