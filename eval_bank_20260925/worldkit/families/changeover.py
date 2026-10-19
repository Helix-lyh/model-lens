"""单资源换型：顺序决定切换分钟。十五个场景共用同一套计算，题面按业务写切换从哪来、错了多等谁。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _setup(world: dict, prev: str, nxt: str) -> int:
    fix = world["modules"].get("fixture")
    if fix and [prev, nxt] == fix["pair"]:
        return 0
    return world["data"]["setup"][prev][nxt]


def greedy_due(world: dict) -> tuple:
    jobs = world["data"]["jobs"]
    return tuple(j["id"] for j in sorted(jobs, key=lambda j: (j["due"], j["id"])))


class ChangeoverFamily:
    def __init__(self, spec: dict):
        self.spec = spec
        self.id = spec["id"]
        self.primary = "tardiness"
        self.shared = "changes"
        self.cf_key = "no_fixture"
        text = spec["fixture_text"]
        self.modules = {m.id: m for m in [
            Module("fixture", spec["fixture_title"], 10, lambda p, _w, text=text: text(p)),
            Module("peak", "后段加长", 20, _t_peak),
        ]}
        kind = spec["kind"]
        self.metrics = {
            "tardiness": f"总逾期分钟（各{spec['unit']}完工时刻超出时限的部分之和，未超出记 0）",
            "changes": f"切换次数（相邻两个{spec['unit']}的{kind}不同才计 1 次，与切换分钟无关）",
        }
        self._phrases = {
            "tardiness": "总逾期分钟最小",
            "changes": "切换次数最小",
        }
        self.counterfactuals = {
            "no_fixture": Counterfactual(_drop_fixture, lambda _w, s=spec["cf_text"]: s),
        }
        self.readings = {}
        self.greedies = lambda w: [greedy_due(w)]

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 1 and "A" <= p <= "H" for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [j["id"] for j in world["data"]["jobs"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        jobs = {j["id"]: j for j in world["data"]["jobs"]}
        if len(plan) != len(jobs) or set(plan) != set(jobs):
            return None
        clock = 0
        prev = "IDLE"
        changes = tardiness = 0
        fired: set[str] = set()
        fix = world["modules"].get("fixture")
        for pid in plan:
            job = jobs[pid]
            su = _setup(world, prev, job["family"])
            if fix and [prev, job["family"]] == fix["pair"] and su == 0:
                fired.add("fixture")
            peak = world["modules"].get("peak")
            if peak and clock >= peak["at"] and su:
                su *= 2
                fired.add("peak")
            if prev != "IDLE" and job["family"] != prev:
                changes += 1
            clock += su + job["minutes"]
            if clock > job["due"]:
                tardiness += clock - job["due"]
            prev = job["family"]
        return Outcome(tuple(plan), {"tardiness": tardiness, "changes": changes}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        s = self.spec
        d = world["data"]
        jobs = [[j["id"], j["family"], j["minutes"], j["due"]] for j in d["jobs"]]
        setup = [[a, b, d["setup"][a][b]] for a in d["setup"] for b in d["setup"][a]]
        return "\n".join([
            s["role"],
            s["legend"],
            f"{s['table']}：{_c(jobs)}。",
            f"切换表每行 `[前一{s['kind']}, 后一{s['kind']}, 分钟]`：{_c(setup)}。开工前先花掉这次切换分钟，再做本{s['unit']}的作业分钟。",
            f"切换次数只计相邻两个{s['unit']}的{s['kind']}是否不同，与切换分钟无关。从 IDLE 进入第一个{s['unit']}的准备分钟计入完工时刻，但不计次。",
            "完工时刻晚于时限的部分记入总逾期；不晚于时限则该次逾期为 0。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [self._phrases[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        s = self.spec
        return [
            {"name": "plan", "type": "plan", "metric": "tardiness", "points": 6, "text": s["plan"]},
            {"name": "tardiness", "metric": "tardiness", "points": 5},
            {"name": "changes", "metric": "changes", "points": 4},
            {"name": "cf_tardiness", "metric": "tardiness", "points": 5, "cf": "no_fixture"},
        ]


def _t_peak(p, _w):
    return (f"后段加长：切换开始时刻达到 {p['at']} 分钟及以后，这次切换分钟乘 2。"
            "作业分钟不乘。夹具把切换分钟改成 0 的，乘 2 之后仍是 0。"
            "从 IDLE 进入第一个的准备分钟同样适用。后段人手减半，切换变慢，作业时长不变。")


def _drop_fixture(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("fixture", None)
    return x


def _ready(p) -> str:
    a, b = p["pair"]
    return f"{a} 紧接着换成 {b}"


SPECS = [
    {
        "id": "or",
        "kind": "专科",
        "unit": "手术",
        "role": "你排一间手术室今天的连台顺序。同一时刻只做一台，做完并完成器械切换才能接下台。0 分钟手术室空闲，上一台专科记为 IDLE。",
        "legend": "专科代号：W 骨科，X 普外，Y 腔镜，Z 耳鼻喉。连台若没按灭菌托盘的顺序接，就要重铺器械，后面的病人继续等。",
        "table": "手术表每行 `[编号, 专科, 手术分钟, 时限]`",
        "fixture_title": "连台托盘",
        "fixture_text": lambda p: f"连台托盘已按顺序备好：{_ready(p)} 时，这次切换分钟改为 0。其他相邻专科仍按切换表。托盘备错就要重灭，不能当成 0。",
        "cf_text": "若连台托盘未备好、切换分钟恢复原表，",
        "plan": "给出最优手术顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (3, 6),
    },
    {
        "id": "apron",
        "kind": "机型",
        "unit": "航班",
        "role": "你排一个近机位上的过站顺序。同一时刻只接一班，做完并完成接驳设备切换才能接下班。0 分钟机位空闲，上一班机型记为 IDLE。",
        "legend": "机型代号：W 窄体，X 宽体，Y 货机，Z 公务。设备不在机位旁就要回库去取，这班的离港继续往后推。",
        "table": "航班表每行 `[编号, 机型, 过站分钟, 时限]`",
        "fixture_title": "接驳设备预置",
        "fixture_text": lambda p: f"下一步接驳设备已放在机位旁：{_ready(p)} 时，这次切换分钟改为 0。其他相邻机型仍按切换表。",
        "cf_text": "若接驳设备没有预置、切换分钟恢复原表，",
        "plan": "给出最优过站顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "berth",
        "kind": "箱型",
        "unit": "作业",
        "role": "你排一座岸桥的作业顺序。同一时刻只做一票，做完并完成吊具切换才能接下票。0 分钟岸桥空闲，上一票箱型记为 IDLE。",
        "legend": "箱型代号：W 干箱，X 冷藏，Y 危险品，Z 超限。吊具没换成下一票要的规格，这票不能起吊，船期继续耗着。",
        "table": "作业表每行 `[编号, 箱型, 作业分钟, 时限]`",
        "fixture_title": "吊具预换",
        "fixture_text": lambda p: f"吊具已预换成下一票：{_ready(p)} 时，这次切换分钟改为 0。其他相邻箱型仍按切换表。",
        "cf_text": "若吊具没有预换、切换分钟恢复原表，",
        "plan": "给出最优作业顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "agv",
        "kind": "载具",
        "unit": "波次",
        "role": "你排一台 AGV 的拣货波次。同一时刻只跑一波，跑完并完成夹具切换才能接下波。0 分钟车辆空闲，上一波载具记为 IDLE。",
        "legend": "载具代号：W 托盘，X 料箱，Y 原箱，Z 退货。夹具不对就不能取货，这一波的截单继续往后拖。",
        "table": "波次表每行 `[编号, 载具, 行走分钟, 时限]`",
        "fixture_title": "夹具预装",
        "fixture_text": lambda p: f"夹具已预装成下一波：{_ready(p)} 时，这次切换分钟改为 0。其他相邻载具仍按切换表。",
        "cf_text": "若夹具没有预装、切换分钟恢复原表，",
        "plan": "给出最优波次顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "ticket",
        "kind": "队列",
        "unit": "工单",
        "role": "你把工单排给一个坐席连续处理。同一时刻只处理一张，处理完并完成技能切换才能接下张。0 分钟坐席空闲，上一张队列记为 IDLE。",
        "legend": "队列代号：W 账单，X 故障，Y 投诉，Z 外呼。技能没切过去就按错流程处理，这张工单的时限继续走。",
        "table": "工单表每行 `[编号, 队列, 处理分钟, 时限]`",
        "fixture_title": "知识已打开",
        "fixture_text": lambda p: f"下一队列的知识页已打开：{_ready(p)} 时，这次切换分钟改为 0。其他相邻队列仍按切换表。",
        "cf_text": "若知识页没有打开、切换分钟恢复原表，",
        "plan": "给出最优工单顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (2, 4),
    },
    {
        "id": "gpu",
        "kind": "镜像",
        "unit": "任务",
        "role": "你把任务排到一张 GPU 上。同一时刻只跑一个任务，跑完并完成镜像加载才能接下个。0 分钟 GPU 空闲，上一个镜像记为 IDLE。",
        "legend": "镜像代号：W 训练，X 推理，Y 微调，Z 评测。镜像没加载就不能开跑，这个任务的交付时限继续耗着。",
        "table": "任务表每行 `[编号, 镜像, 运行分钟, 时限]`",
        "fixture_title": "权重已预热",
        "fixture_text": lambda p: f"下一镜像的权重已在卡上：{_ready(p)} 时，这次切换分钟改为 0。其他相邻镜像仍按切换表。",
        "cf_text": "若权重没有预热、切换分钟恢复原表，",
        "plan": "给出最优任务顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "galley",
        "kind": "工位",
        "unit": "菜品",
        "role": "你排一个厨师在唯一工位上的制作顺序。同一时刻只做一道，做完并完成工位切换才能接下道。0 分钟工位空闲，上一道工位记为 IDLE。",
        "legend": "工位代号：W 炒，X 蒸，Y 烤，Z 冷菜。锅灶没复位，下一道不能下锅，这桌的出餐时限继续走。同工位连做也要清锅。",
        "table": "菜品表每行 `[编号, 工位, 制作分钟, 时限]`",
        "fixture_title": "工位已预热",
        "fixture_text": lambda p: f"工位已按下一道预热：{_ready(p)} 时，这次切换分钟改为 0。其他相邻工位仍按切换表。",
        "cf_text": "若工位没有预热、切换分钟恢复原表，",
        "plan": "给出最优制作顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (3, 5),
    },
    {
        "id": "fresh",
        "kind": "品类",
        "unit": "批次",
        "role": "你排一张生鲜加工台的批次顺序。同一时刻只加工一批，加工完并完成清洁切换才能接下批。0 分钟加工台空闲，上一批品类记为 IDLE。",
        "legend": "品类代号：W 肉类，X 水产，Y 熟食，Z 果蔬。清洁不到位不能切下一批，这批的上架时限继续走。同品类连切也要冲洗台面。",
        "table": "批次表每行 `[编号, 品类, 加工分钟, 时限]`",
        "fixture_title": "清洁已做好",
        "fixture_text": lambda p: f"下一批的清洁已提前做好：{_ready(p)} 时，这次切换分钟改为 0。其他相邻品类仍按切换表。",
        "cf_text": "若清洁没有提前做好、切换分钟恢复原表，",
        "plan": "给出最优加工顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (4, 6),
    },
    {
        "id": "canteen",
        "kind": "品类",
        "unit": "批次",
        "role": "你排一个食堂窗口的出餐批次。同一时刻只做一批，做完并完成炉具切换才能接下批。0 分钟窗口空闲，上一批品类记为 IDLE。",
        "legend": "品类代号：W 饭，X 面，Y 粉，Z 小吃。炉具没换过，下一批不能下锅，这一批的供餐时限继续走。",
        "table": "批次表每行 `[编号, 品类, 烹制分钟, 时限]`",
        "fixture_title": "炉具已预热",
        "fixture_text": lambda p: f"炉具已按下一批预热：{_ready(p)} 时，这次切换分钟改为 0。其他相邻品类仍按切换表。",
        "cf_text": "若炉具没有预热、切换分钟恢复原表，",
        "plan": "给出最优出餐顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (2, 4),
    },
    {
        "id": "plug",
        "kind": "接口",
        "unit": "车辆",
        "role": "你排一个充电车位的插枪顺序。同一时刻只充一辆，充满并完成接口切换才能接下辆。0 分钟车位空闲，上一辆接口记为 IDLE。",
        "legend": "接口代号：W 乘用，X 货车，Y 欧标，Z 换电接口。枪线没换成这辆能用的接口，就不能开始充电，这辆的出发时限继续走。",
        "table": "车辆表每行 `[编号, 接口, 充电分钟, 时限]`",
        "fixture_title": "枪线已换好",
        "fixture_text": lambda p: f"枪线已换成下一辆的接口：{_ready(p)} 时，这次切换分钟改为 0。其他相邻接口仍按切换表。",
        "cf_text": "若枪线没有提前换好、切换分钟恢复原表，",
        "plan": "给出最优插枪顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "relief",
        "kind": "货类",
        "unit": "批次",
        "role": "你排一辆货车的装车顺序。同一时刻只装一批，装完并完成隔舱切换才能接下批。0 分钟车厢空闲，上一批货类记为 IDLE。",
        "legend": "货类代号：W 食品，X 药品，Y 帐篷，Z 燃油。隔舱没隔开不能混装，这一批的送达时限继续走。",
        "table": "批次表每行 `[编号, 货类, 装车分钟, 时限]`",
        "fixture_title": "隔舱已摆好",
        "fixture_text": lambda p: f"隔舱已按下一批摆好：{_ready(p)} 时，这次切换分钟改为 0。其他相邻货类仍按切换表。",
        "cf_text": "若隔舱没有提前摆好、切换分钟恢复原表，",
        "plan": "给出最优装车顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "bed",
        "kind": "级别",
        "unit": "房间",
        "role": "你排一个保洁组的房间顺序。同一时刻只清一间，清完并完成防护切换才能接下间。0 分钟保洁组空闲，上一间级别记为 IDLE。",
        "legend": "级别代号：W 普通，X 接触，Y 飞沫，Z 空气。防护没换成下一间要求的级别，不能进房间，这间的周转时限继续走。同级别连清也要更换一次性用品。",
        "table": "房间表每行 `[编号, 级别, 清洁分钟, 时限]`",
        "fixture_title": "防护已备好",
        "fixture_text": lambda p: f"下一间的防护已在门口备好：{_ready(p)} 时，这次切换分钟改为 0。其他相邻级别仍按切换表。",
        "cf_text": "若防护没有提前备好、切换分钟恢复原表，",
        "plan": "给出最优清洁顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (3, 5),
    },
    {
        "id": "crowd",
        "kind": "模式",
        "unit": "批次",
        "role": "你排一个安检口的批次顺序。同一时刻只检一批，检完并完成模式切换才能接下批。0 分钟安检口空闲，上一批模式记为 IDLE。",
        "legend": "模式代号：W 随身，X 开包，Y 车检，Z 宠物。设备没换成下一批的模式，这一批不能开始，入场时限继续走。",
        "table": "批次表每行 `[编号, 模式, 检查分钟, 时限]`",
        "fixture_title": "模式已切好",
        "fixture_text": lambda p: f"安检模式已按下一批切好：{_ready(p)} 时，这次切换分钟改为 0。其他相邻模式仍按切换表。",
        "cf_text": "若模式没有提前切好、切换分钟恢复原表，",
        "plan": "给出最优安检顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (2, 4),
    },
    {
        "id": "maint",
        "kind": "设备",
        "unit": "工单",
        "role": "你排一个维修工的工单顺序。同一时刻只修一张，修完并完成工具切换才能接下张。0 分钟维修工空闲，上一张设备记为 IDLE。",
        "legend": "设备代号：W 电梯，X 水泵，Y 配电，Z 空调。工具箱没换成下一张要的套装，不能开工，这张的修复时限继续走。",
        "table": "工单表每行 `[编号, 设备, 维修分钟, 时限]`",
        "fixture_title": "工具已备好",
        "fixture_text": lambda p: f"下一张的工具已备在现场：{_ready(p)} 时，这次切换分钟改为 0。其他相邻设备仍按切换表。",
        "cf_text": "若工具没有提前备好、切换分钟恢复原表，",
        "plan": "给出最优维修顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
    {
        "id": "drone",
        "kind": "吊舱",
        "unit": "架次",
        "role": "你排一架无人机的架次顺序。同一时刻只飞一架次，落地并完成吊舱切换才能接下一次。0 分钟无人机空闲，上一架次吊舱记为 IDLE。",
        "legend": "吊舱代号：W 测绘，X 投送，Y 喊话，Z 热成像。吊舱没换成下一架次要的型号，不能起飞，这一架次的窗口时限继续走。",
        "table": "架次表每行 `[编号, 吊舱, 飞行分钟, 时限]`",
        "fixture_title": "吊舱已挂好",
        "fixture_text": lambda p: f"下一架次的吊舱已挂上：{_ready(p)} 时，这次切换分钟改为 0。其他相邻吊舱仍按切换表。",
        "cf_text": "若吊舱没有提前挂好、切换分钟恢复原表，",
        "plan": "给出最优架次顺序，编号用短横线连接，例如 A-B-C-D-E-F。",
        "same": (0, 0),
    },
]


FAMILIES = {spec["id"]: ChangeoverFamily(spec) for spec in SPECS}
SPEC_OF = {spec["id"]: spec for spec in SPECS}
