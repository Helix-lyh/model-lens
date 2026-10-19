"""推出顺序、港口波次、誓言清算的手算轨迹。"""
from eval_bank_20260925.worldkit import answers, core, render
from eval_bank_20260925.worldkit.families import oath, push, yard


def test_push_share_doubles_overlap():
    world = {
        "family": "push",
        "data": {"flights": [
            {"id": "A", "dep": 20, "tow": 2, "zone": "东", "wide": False},
            {"id": "B", "dep": 20, "tow": 2, "zone": "西", "wide": False},
        ]},
        "modules": {"share": {}},
        "objective": ["flow", "late_n"],
        "questions": push.FAMILY.questions(),
        "background": [],
    }
    out = push.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics == {"flow": 8, "late_n": 0}
    bare = push.FAMILY.simulate({**world, "modules": {}}, ("A", "B"))
    assert bare is not None
    assert bare.metrics == {"flow": 4, "late_n": 0}


def test_push_zone_gap_on_same_tractor():
    world = {
        "family": "push",
        "data": {"flights": [
            {"id": "A", "dep": 30, "tow": 2, "zone": "东"},
            {"id": "B", "dep": 30, "tow": 2, "zone": "西"},
            {"id": "C", "dep": 30, "tow": 2, "zone": "北"},
        ]},
        "modules": {"zone": {"minutes": 4, "alt": 10}},
        "objective": ["flow", "late_n"],
        "questions": push.FAMILY.questions(),
        "background": [],
    }
    # A 甲车 0–2 东；B 乙车 0–2 西；C 甲车换区空等 4，从 6 做到 8。
    out = push.FAMILY.simulate(world, ("A", "B", "C"))
    assert out is not None
    assert out.metrics["flow"] == 2 + 2 + 8


def test_yard_overflow_and_threshold():
    world = {
        "family": "yard",
        "data": {
            "n_waves": 2,
            "wave_end": [10, 20],
            "yards": [{"id": "X"}, {"id": "Y"}],
            "ships": [
                {"id": "A", "seq": 0, "boxes": 4, "tide": 15},
                {"id": "B", "seq": 1, "boxes": 4, "tide": 15},
            ],
        },
        "modules": {"wave": {"cap": 5}, "yard": {"thresh": 4, "slow": 10, "alt": 8}},
        "objective": ["over", "late_n"],
        "questions": yard.FAMILY.questions(),
        "background": [],
    }
    split = yard.FAMILY.simulate(world, ("A1X", "B1Y"))
    assert split is not None
    # A 走第 1 波完成 10；B 第 1 波只剩 1，余 3 挤到第 2 波完成 20。过潮 5，1 艘。
    assert split.metrics == {"over": 5, "late_n": 1}
    piled = yard.FAMILY.simulate(world, ("A1X", "B1X"))
    assert piled is not None
    # B 进场时 X 已有 4，整船 +10，完成 30，过潮 15。
    assert piled.metrics["over"] == 15


def test_oath_hand_trace_and_earth_misses():
    world = {
        "family": "oath",
        "data": {
            "parties": ["A", "B", "C"],
            "opening": {"A": 8, "B": 1, "C": 1},
            "mid_at": 6,
            "oaths": [
                {"id": "V1", "src": "A", "dst": "B", "units": 4},
                {"id": "V2", "src": "A", "dst": "B", "units": 3},
                {"id": "V3", "src": "B", "dst": "C", "units": 4},
                {"id": "V4", "src": "C", "dst": "B", "units": 2},
            ],
            "log": [
                {"op": "reg", "oath": "V1"},
                {"op": "reg", "oath": "V2"},
                {"op": "tick"},
                {"op": "run", "oath": "V1"},
                {"op": "reg", "oath": "V3"},
                {"op": "run", "oath": "V2"},
                {"op": "tick"},
                {"op": "tick"},
                {"op": "run", "oath": "V3"},
                {"op": "reg", "oath": "V4"},
                {"op": "tick"},
                {"op": "run", "oath": "V4"},
            ],
        },
        "modules": {
            "delay": {"k": 2},
            "cost": {"fee": 1},
            "cap": {"n": 6},
            "fine": {"m": 2},
            "habit": {},
        },
        "objective": ["live_b"],
        "questions": oath.FAMILY.questions(),
        "background": ["habit"],
    }
    gold = oath._replay(world, earth=False)
    earth = oath._replay(world, earth=True)
    assert gold == {"live_b_mid": 5, "live_b": 2, "penalty": 2}
    assert earth["live_b_mid"] != gold["live_b_mid"]
    assert earth["live_b"] != gold["live_b"]
    assert earth["penalty"] != gold["penalty"]
    sol = core.solve(oath.FAMILY, world)
    assert sol.status == "ok"
    key = core.answers(oath.FAMILY, world)
    ref = answers.reference_text(world, key, core.Solver(oath.FAMILY), best=sol.best)
    scored = answers.score(oath.FAMILY, world, key, ref, best=sol.best)
    assert scored["passed"]
    earth_text = answers.replay_text(
        world, ("LOG",),
        {"live_b_mid": earth["live_b_mid"], "live_b": earth["live_b"], "penalty": earth["penalty"]},
        {"live_b": earth["live_b"]},
    )
    earth_score = answers.score(oath.FAMILY, world, key, earth_text, best=sol.best)
    assert earth_score["points"] == 0
    assert render.leaks(render.render_prompt(oath.FAMILY, world)) == []
    cf = oath.FAMILY.counterfactuals["delay_plus"].transform(world)
    cfm = oath._replay(cf, earth=False)
    assert cfm["live_b"] != gold["live_b"]
