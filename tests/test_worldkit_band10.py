"""新决策形状三题族：手算轨迹，以及猎到的世界贪心恰好 4 分。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, core, render
from eval_bank_20260925.worldkit.families import evac, family_of, quay, repair

ROOT = Path(__file__).resolve().parents[1]
BAND = ROOT / "eval_bank_20260925/worldkit/worlds/band10"


def test_quay_two_ships_split_berths_and_share_one():
    world = {
        "family": "quay",
        "data": {
            "tug": 4,
            "berths": [{"id": "1", "length": 180}, {"id": "2", "length": 110}],
            "ships": [
                {"id": "A", "length": 160, "arrive": 0, "work": 6, "due": 20, "cargo": "粮"},
                {"id": "B", "length": 80, "arrive": 0, "work": 6, "due": 20, "cargo": "箱"},
            ],
        },
        "modules": {"flush": {"minutes": 3}},
        "objective": ["tardiness", "late_n"],
        "questions": quay.FAMILY.questions(),
        "background": [],
    }
    split = quay.FAMILY.simulate(world, ("A1", "B2"))
    assert split is not None
    assert split.metrics == {"tardiness": 0, "late_n": 0}
    shared = quay.FAMILY.simulate(world, ("A1", "B1"))
    assert shared is not None
    assert shared.metrics == {"tardiness": 3, "late_n": 1}
    too_long = quay.FAMILY.simulate(world, ("A2", "B1"))
    assert too_long is None


def test_quay_tide_delays_deep_berth_start():
    world = {
        "family": "quay",
        "data": {
            "tug": 4,
            "berths": [{"id": "1", "length": 180}, {"id": "2", "length": 110}],
            "ships": [
                {"id": "A", "length": 160, "arrive": 0, "work": 6, "due": 20, "cargo": "粮"},
                {"id": "B", "length": 80, "arrive": 0, "work": 6, "due": 20, "cargo": "箱"},
            ],
        },
        "modules": {"tide": {"berth": "1", "lo": 0, "hi": 8}},
        "objective": ["tardiness", "late_n"],
        "questions": quay.FAMILY.questions(),
        "background": [],
    }
    out = quay.FAMILY.simulate(world, ("A1", "B2"))
    assert out is not None
    # A 本可 0 分靠，潮汐推迟到 8；拖轮 12 分空出，B 12 分靠、22 分离泊。
    assert out.metrics == {"tardiness": 2, "late_n": 1}
    assert "tide" in out.fired


def test_evac_queue_on_one_stair():
    world = {
        "family": "evac",
        "data": {
            "stairs": [{"id": "1", "cap": 2}, {"id": "2", "cap": 2}],
            "groups": [
                {"id": "A", "size": 3, "walk": {"1": 0, "2": 5}, "due": 3},
                {"id": "B", "size": 3, "walk": {"1": 0, "2": 5}, "due": 3},
            ],
        },
        "modules": {},
        "objective": ["delay", "late_n"],
        "questions": evac.FAMILY.questions(),
        "background": [],
    }
    out = evac.FAMILY.simulate(world, ("A1", "B1"))
    assert out is not None
    # A 占 3 名额、每分钟 2，进入 2 分钟；B 从 2 做到 4，滞留 1。
    assert out.metrics == {"delay": 1, "late_n": 1}


def test_evac_smoke_blocks_start_not_an_ongoing_entry():
    world = {
        "family": "evac",
        "data": {
            "stairs": [{"id": "1", "cap": 2}, {"id": "2", "cap": 2}],
            "groups": [
                {"id": "A", "size": 2, "walk": {"1": 0, "2": 2}, "due": 10},
            ],
        },
        "modules": {"smoke": {"stair": "2", "lo": 0, "hi": 4}},
        "objective": ["delay", "late_n"],
        "questions": evac.FAMILY.questions(),
        "background": [],
    }
    out = evac.FAMILY.simulate(world, ("A2",))
    assert out is not None
    # 走到 2 分钟，落在烟气窗口内，等到 4 再进入 1 分钟，5 分进完。
    assert out.metrics == {"delay": 0, "late_n": 0}
    assert "smoke" in out.fired


def test_repair_clash_holds_the_second_crew():
    world = {
        "family": "repair",
        "data": {
            "depot": "0",
            "crews": [
                {"id": "1", "skills": ["线"]},
                {"id": "2", "skills": ["线", "变"]},
            ],
            "jobs": [
                {"id": "A", "site": "P", "skill": "线", "work": 4, "due": 10},
                {"id": "B", "site": "P", "skill": "线", "work": 4, "due": 10},
            ],
            "travel": {
                "0": {"0": 0, "P": 3},
                "P": {"0": 3, "P": 0},
            },
        },
        "modules": {"clash": {}},
        "objective": ["late", "late_n"],
        "questions": repair.FAMILY.questions(),
        "background": [],
    }
    held = repair.FAMILY.simulate(world, ("A1", "B2"))
    assert held is not None
    assert held.metrics == {"late": 1, "late_n": 1}
    assert "clash" in held.fired
    free = repair.FAMILY.simulate(
        {**world, "modules": {}},
        ("A1", "B2"),
    )
    assert free is not None
    assert free.metrics == {"late": 0, "late_n": 0}


def test_repair_fatigue_splits_a_job_across_the_threshold():
    world = {
        "family": "repair",
        "data": {
            "depot": "0",
            "crews": [{"id": "1", "skills": ["线"]}],
            "jobs": [
                {"id": "A", "site": "P", "skill": "线", "work": 4, "due": 20},
            ],
            "travel": {"0": {"0": 0, "P": 3}, "P": {"0": 3, "P": 0}},
        },
        "modules": {"fatigue": {"at": 5}},
        "objective": ["late", "late_n"],
        "questions": repair.FAMILY.questions(),
        "background": [],
    }
    out = repair.FAMILY.simulate(world, ("A1",))
    assert out is not None
    # 3 分钟到达，做 2 个单位到第 5 分钟，余下 2 个单位半速要 4 分钟，完工 9。
    assert out.metrics == {"late": 0, "late_n": 0}
    assert out.trace == []
    done = repair._finish(3, 4, 5)
    assert done == (9, True)


TEN = (
    "delivery", "trip", "elevator", "signal", "line",
    "trip2", "elevator2", "elevator3", "elevator4", "charge",
)


def test_band10_has_ten_worlds_reference_full_and_no_leaks():
    manifest = json.loads((BAND / "manifest.json").read_text(encoding="utf-8"))
    names = [it["file"].removesuffix(".json") for it in manifest["items"]]
    assert names == list(TEN)
    assert manifest["sum_points"] == 51
    for it in manifest["items"]:
        path = BAND / it["file"]
        world = json.loads(path.read_text(encoding="utf-8"))
        assert world["family"] == it["family"]
        fam = family_of(world)
        prompt = render.render_prompt(fam, world)
        assert render.leaks(prompt) == []
        if it["family"] == "delivery":
            continue
        sol = core.solve(fam, world, core.Budget(400_000, 60))
        assert sol.status == "ok"
        key = core.answers(fam, world)
        ref = answers.reference_text(world, key, core.Solver(fam), best=sol.best)
        assert answers.score(fam, world, key, ref, best=sol.best)["passed"]
