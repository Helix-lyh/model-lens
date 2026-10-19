"""分段选择：段序固定，每段选做法和路线。小段上的窗口看进入时刻，前一段走完的时刻会改写后一段。

十五个场景共用同一套计算。只把每段表上的分钟加起来，会漏掉窗口等待和进场时刻。
"""
from __future__ import annotations

import copy
import itertools
import json
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _ids(spec: dict, kind: str) -> list[str]:
    return [c["id"] for c in spec["choices"] if c["kind"] == kind]


def _surge_text(spec: dict):
    def text(p, _w, why=spec["surge_why"]):
        ids = "、".join(p["ids"])
        return f"{ids} 的每个小段作业分钟×{p['factor']}。等窗口、交接和进场等待都不乘。{why}"

    return text


def _wave_text(spec: dict):
    def text(p, _w, why=spec["wave_why"]):
        ids = "、".join(p["ids"])
        return (f"窗口：周期 {p['cycle']} 分钟，每周期前 {p['open']} 分钟可以进入。"
                f"灯标记为 1 的小段，进入时刻若落在窗口外，先等到下一周期再走该小段。"
                f"只有 {ids} 看灯。时刻表做法不看灯。{why}")

    return text


def _seam_text(spec: dict):
    def text(p, _w, why=spec["seam_why"]):
        return f"相邻两段做法不同时，下一段开始前先交接 {p['minutes']} 分钟。做法相同则不交接。{why}"

    return text


def _board_text(spec: dict):
    def text(p, _w, why=spec["board_why"]):
        ids = "、".join(p["ids"])
        return (f"{ids} 先花到场分钟，再等到进场时刻 {_c(p['times'])} 里不早于当前时刻的一班，然后花作业分钟。"
                "时刻表没有更晚的班次，这个方案不可行。等班的时间不计入作业分钟。" + why)

    return text


def _nominal(mode: dict, body) -> int:
    if mode["kind"] == "timed":
        return int(body["access"]) + int(body["ride"])
    return sum(int(seg["min"]) for seg in body)


def greedy_local(world: dict) -> tuple:
    """每段只比表上的分钟，不计翻倍、窗口、交接和进场时刻。"""
    plan = []
    for leg in world["data"]["legs"]:
        best = None
        for mode in world["data"]["modes"]:
            for route in ("DIRECT", "DETOUR"):
                nominal = _nominal(mode, leg[mode["id"]][route])
                key = (nominal, mode["id"], route)
                if best is None or key < best[0]:
                    best = (key, mode["id"], route)
        plan.extend((best[1], best[2]))
    return tuple(plan)


class CascadeFamily:
    def __init__(self, spec: dict):
        self.spec = spec
        self.id = spec["id"]
        self.primary = "time"
        self.shared = "cost"
        self.cf_key = "no_surge"
        self.modules = {m.id: m for m in [
            Module("surge", spec["surge_title"], 10, _surge_text(spec)),
            Module("wave", spec["wave_title"], 20, _wave_text(spec)),
            Module("seam", spec["seam_title"], 30, _seam_text(spec)),
            Module("board", spec["board_title"], 40, _board_text(spec)),
        ]}
        self.metrics = {"time": spec["time_label"], "cost": spec["cost_label"]}
        self._phrases = {"time": spec["time_phrase"], "cost": spec["cost_phrase"]}
        self.counterfactuals = {
            "no_surge": Counterfactual(_drop_surge, lambda _w, s=spec["cf_text"]: s),
        }
        self.readings = {}
        self.greedies = lambda w: [greedy_local(w)]

    def effective(self, world: dict) -> dict:
        return world

    def plans(self, world: dict) -> Iterator[tuple]:
        pairs = [(m["id"], r) for m in world["data"]["modes"] for r in ("DIRECT", "DETOUR")]
        for combo in itertools.product(pairs, repeat=len(world["data"]["legs"])):
            yield tuple(x for pair in combo for x in pair)

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        return _simulate(world, plan, surge=True)

    def local_clock(self, world: dict, plan: tuple) -> int | None:
        """只累加小段作业分钟。翻倍照乘，不计窗口、交接和进场等待。"""
        out = _simulate(world, plan, surge=True, local=True)
        return None if out is None else out.metrics["time"]

    def header(self, world: dict) -> str:
        s = self.spec
        d = world["data"]
        labels = [[m["id"], m["label"]] for m in d["modes"]]
        routes = [[r["id"], r["label"]] for r in d["routes"]]
        costs = [[m["id"], d["cost"][m["id"]]] for m in d["modes"]]
        lines = [
            s["role"],
            f"做法代号每行 `[代号, 名称]`：{_c(labels)}。路线代号每行 `[代号, 名称]`：{_c(routes)}。",
            s["carry"],
            "每一段都要选一种做法，再选一条路线。上一段的完成时刻就是下一段的开始时刻。",
            "换了做法要先交接，再走这一段。标了灯的小段按进入时刻等窗口。时刻表做法先花到场分钟，等到班次，再花作业分钟。",
        ]
        for i, leg in enumerate(d["legs"], 1):
            lines.append(
                f"第{i}段（{leg['name']}）每行 `[做法, 路线, …]`。"
                "前两种做法是 `[做法, 路线, 小段分钟列表, 灯标记列表]`，灯标记 1 表示该小段要等窗口；"
                f"时刻表做法是 `[做法, 路线, 到场分钟, 作业分钟]`。表：{_c(_leg_rows(leg, d['modes']))}。"
            )
        lines.append(f"{s['cost_label']}按每一段所选做法的费用相加。各做法每段费用 `[做法, 费用]`：{_c(costs)}。")
        return "\n".join(lines)

    def objective_text(self, world: dict) -> str:
        layers = [self._phrases[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个做法并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        s = self.spec
        fast = _ids(s, "surge")[0]
        plain = _ids(s, "skip")[0]
        example = "-".join([f"{fast}-DIRECT", f"{plain}-DETOUR", f"{fast}-DIRECT"])
        return [
            {"name": "plan", "type": "plan", "metric": "time", "points": 6,
             "text": f"给出五段各自的做法和路线，全部用短横线连接，例如 {example}。"},
            {"name": "time", "metric": "time", "points": 5},
            {"name": "cost", "metric": "cost", "points": 4},
            {"name": "cf_time", "metric": "time", "points": 5, "cf": "no_surge"},
        ]


def _leg_rows(leg: dict, modes: list[dict]) -> list:
    rows = []
    for mode in modes:
        for route in ("DIRECT", "DETOUR"):
            body = leg[mode["id"]][route]
            if mode["kind"] == "timed":
                rows.append([mode["id"], route, body["access"], body["ride"]])
            else:
                rows.append([
                    mode["id"], route,
                    [int(seg["min"]) for seg in body],
                    [1 if seg.get("lights") else 0 for seg in body],
                ])
    return rows


def _light_wait(clock: int, cycle: int, open_: int) -> int:
    phase = clock % cycle
    return 0 if phase < open_ else cycle - phase


def _simulate(world: dict, plan: tuple, *, surge: bool, local: bool = False) -> Outcome | None:
    modes = {m["id"]: m for m in world["data"]["modes"]}
    legs = world["data"]["legs"]
    if len(plan) != 2 * len(legs):
        return None
    pairs = []
    for i in range(0, len(plan), 2):
        mode, route = plan[i], plan[i + 1]
        if mode not in modes or route not in ("DIRECT", "DETOUR"):
            return None
        if route not in legs[i // 2][mode]:
            return None
        pairs.append((mode, route))
    modules = world["modules"]
    hot = set(modules["surge"]["ids"]) if surge and "surge" in modules else set()
    factor = int(modules["surge"]["factor"]) if hot else 1
    wave = None if local else modules.get("wave")
    seam = None if local else modules.get("seam")
    board = None if local else modules.get("board")
    wave_ids = set(wave["ids"]) if wave else set()
    board_ids = set(board["ids"]) if board else set()
    clock = cost = 0
    prev = None
    fired: set[str] = set()
    for (mode, route), leg in zip(pairs, legs):
        if seam and prev is not None and mode != prev:
            clock += int(seam["minutes"])
            fired.add("seam")
        prev = mode
        body = leg[mode][route]
        if modes[mode]["kind"] == "timed":
            clock += int(body["access"])
            if board and mode in board_ids:
                nxt = next((t for t in board["times"] if t >= clock), None)
                if nxt is None:
                    return None
                if nxt > clock:
                    fired.add("board")
                clock = nxt
            clock += int(body["ride"])
        else:
            for seg in body:
                minutes = int(seg["min"])
                if mode in hot:
                    minutes *= factor
                    fired.add("surge")
                if wave and seg.get("lights") and mode in wave_ids:
                    wait = _light_wait(clock, int(wave["cycle"]), int(wave["open"]))
                    if wait:
                        clock += wait
                        fired.add("wave")
                clock += minutes
        cost += int(world["data"]["cost"][mode])
    return Outcome(tuple(plan), {"time": clock, "cost": cost}, [], frozenset(fired))


def _drop_surge(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("surge", None)
    return x


SPECS = [
    {
        "id": "or",
        "role": "你为一间手术室已经排好先后的五台手术各选一种班组。手术顺序不能改，只能选这一台由谁来做。",
        "carry": "五台按表上的顺序接台。上一台的完成时刻就是下一台的开始时刻。选错班组会让后面的病人空等消毒发放，手术室被占着，后面的台次继续延误。",
        "choices": [
            {"id": "CREW", "label": "连台班", "kind": "surge"},
            {"id": "FLOAT", "label": "机动班", "kind": "norm"},
            {"id": "BLOCK", "label": "封闭班", "kind": "skip"},
            {"id": "VEND", "label": "外包班", "kind": "meet"},
        ],
        "stages": ["骨科", "普外", "腔镜", "耳鼻喉", "急诊加台"],
        "surge_title": "连台铺台",
        "surge_why": "连台班要在本台重复开包铺台，作业变慢。铺台时间算在这一台里，不另计一笔。",
        "wave_title": "消毒发放",
        "wave_why": "连台班和机动班用供应室的无菌包，错过发放窗口就要等下一轮，病人继续躺在手术室。",
        "seam_title": "班组交接",
        "seam_why": "换班组要核对病人、器械和麻醉，这段时间手术不能开始。",
        "board_title": "外包进场",
        "board_why": "外包班按合同时刻进场，人没到不能开台。",
        "cf_text": "若连台班不再重复铺台、作业分钟恢复表上的数字，",
        "time_label": "五台全部做完的时刻（从 0 分钟起算）",
        "cost_label": "班组费用合计",
        "time_phrase": "五台全部做完的时刻最小",
        "cost_phrase": "班组费用合计最小",
        "plan": "给出五台各自的做法代号，按段序用短横线连接，例如 CREW-BLOCK-CREW-BLOCK-CREW。",
    },
    {
        "id": "apron",
        "role": "你为一个近机位上已经排好落地顺序的五班过站各选一种保障做法。航班顺序不能改。",
        "carry": "五班按落地顺序接。上一班的完成时刻就是下一班可以开始保障的时刻。做法选错会让后面的航班错过廊桥窗口，离港继续往后推。",
        "choices": [
            {"id": "QUICK", "label": "快保", "kind": "surge"},
            {"id": "FULL", "label": "全套", "kind": "norm"},
            {"id": "TOW", "label": "拖远", "kind": "skip"},
            {"id": "SLOT", "label": "廊桥窗", "kind": "meet"},
        ],
        "stages": ["早班窄体", "早班宽体", "午班货机", "午班公务", "晚班加班"],
        "surge_title": "快保复检",
        "surge_why": "快保要在本班把简略检查再做一遍，作业分钟变长。",
        "wave_title": "廊桥窗口",
        "wave_why": "快保和全套都要占廊桥。错过开放时段，这班不能上客，得等下一窗。",
        "seam_title": "设备交接",
        "seam_why": "相邻两班换做法，要先把客梯车和电源换套，这段时间不能开始下一班。",
        "board_title": "廊桥预约",
        "board_why": "选廊桥窗的班只能在预约时刻靠桥，车没到不能上客。",
        "cf_text": "若快保不用复检、作业分钟恢复表上的数字，",
        "time_label": "五班全部保障完的时刻（从 0 分钟起算）",
        "cost_label": "地勤费用合计",
        "time_phrase": "五班全部保障完的时刻最小",
        "cost_phrase": "地勤费用合计最小",
        "plan": "给出五班各自的做法代号，按段序用短横线连接，例如 QUICK-TOW-QUICK-TOW-QUICK。",
    },
    {
        "id": "berth",
        "role": "你为一条船已经排好舱序的五个舱各选一种作业做法。舱的顺序不能改。",
        "carry": "五个舱按舱序做。上一舱的完成时刻就是下一舱可以开工的时刻。做法选错会让后面的舱错过潮窗，船在泊位上继续耗着。",
        "choices": [
            {"id": "TWIN", "label": "双吊", "kind": "surge"},
            {"id": "SINGLE", "label": "单吊", "kind": "norm"},
            {"id": "SHIFT", "label": "移箱", "kind": "skip"},
            {"id": "TIDE", "label": "乘潮", "kind": "meet"},
        ],
        "stages": ["一舱", "二舱", "三舱", "四舱", "五舱"],
        "surge_title": "双吊复核",
        "surge_why": "双吊要在本舱把锁具再核一遍，作业分钟变长。",
        "wave_title": "岸电窗口",
        "wave_why": "双吊和单吊依赖岸电档。错过档期就要等下一档，岸桥空转。",
        "seam_title": "吊具交接",
        "seam_why": "相邻两舱换做法要先换吊具，这段时间不能起吊。",
        "board_title": "乘潮时刻",
        "board_why": "乘潮作业只能在给定时刻开工，潮位不到不能动超限箱。",
        "cf_text": "若双吊不用复核、作业分钟恢复表上的数字，",
        "time_label": "五舱全部做完的时刻（从 0 分钟起算）",
        "cost_label": "岸桥费用合计",
        "time_phrase": "五舱全部做完的时刻最小",
        "cost_phrase": "岸桥费用合计最小",
        "plan": "给出五舱各自的做法代号，按段序用短横线连接，例如 TWIN-SHIFT-TWIN-SHIFT-TWIN。",
    },
    {
        "id": "agv",
        "role": "你为已经排好先后的五波拣货各选一种搬运做法。波次顺序不能改。",
        "carry": "五波按顺序跑。上一波的完成时刻就是下一波可以发车的时刻。做法选错会让后面的波次错过巷道窗口，截单继续往后拖。",
        "choices": [
            {"id": "DIRECT", "label": "直送", "kind": "surge"},
            {"id": "AISLE", "label": "巷道", "kind": "norm"},
            {"id": "STAGE", "label": "暂存", "kind": "skip"},
            {"id": "BATCH", "label": "齐套窗", "kind": "meet"},
        ],
        "stages": ["一波", "二波", "三波", "四波", "截单波"],
        "surge_title": "直送复盘",
        "surge_why": "直送要在本波把货再盘一遍，行走分钟变长。",
        "wave_title": "巷道窗口",
        "wave_why": "直送和巷道都要进共享巷道。错过放行窗口就得在巷口等下一轮，后面的订单继续积压。",
        "seam_title": "夹具交接",
        "seam_why": "相邻两波换做法要先换夹具，这段时间车辆不能出发。",
        "board_title": "齐套时刻",
        "board_why": "齐套窗只能在给定时刻发车，货没齐不能走。",
        "cf_text": "若直送不用复盘、作业分钟恢复表上的数字，",
        "time_label": "五波全部送达的时刻（从 0 分钟起算）",
        "cost_label": "搬运费用合计",
        "time_phrase": "五波全部送达的时刻最小",
        "cost_phrase": "搬运费用合计最小",
        "plan": "给出五波各自的做法代号，按段序用短横线连接，例如 DIRECT-STAGE-DIRECT-STAGE-DIRECT。",
    },
    {
        "id": "ticket",
        "role": "你为已经排好时段的五段客服班各选一种处理做法。时段顺序不能改。",
        "carry": "五段按时间接。上一段的完成时刻就是下一段可以开始接单的时刻。做法选错会让后面的时段错过技能窗口，排队继续加长。",
        "choices": [
            {"id": "BOT", "label": "自动", "kind": "surge"},
            {"id": "L1", "label": "一线", "kind": "norm"},
            {"id": "SPEC", "label": "专席", "kind": "skip"},
            {"id": "CALL", "label": "回呼", "kind": "meet"},
        ],
        "stages": ["早班", "午前", "午后", "晚高峰", "夜班"],
        "surge_title": "自动复核",
        "surge_why": "自动处理要在本段把转人工的单再核一遍，作业分钟变长。",
        "wave_title": "技能窗口",
        "wave_why": "自动和一线都要等技能组放行。错过窗口，这批工单不能开工。",
        "seam_title": "技能交接",
        "seam_why": "相邻两段换做法要先交接未结工单，这段时间不能接新单。",
        "board_title": "回呼时刻",
        "board_why": "回呼只能在约定时刻拨出，客户不在线不能算开始。",
        "cf_text": "若自动处理不用复核、作业分钟恢复表上的数字，",
        "time_label": "五段全部处理完的时刻（从 0 分钟起算）",
        "cost_label": "人力费用合计",
        "time_phrase": "五段全部处理完的时刻最小",
        "cost_phrase": "人力费用合计最小",
        "plan": "给出五段各自的做法代号，按段序用短横线连接，例如 BOT-SPEC-BOT-SPEC-BOT。",
    },
    {
        "id": "gpu",
        "role": "你为已经排好阶段顺序的五个训练阶段各选一种占卡做法。阶段顺序不能改。",
        "carry": "五个阶段按顺序跑。上一阶段的完成时刻就是下一阶段可以占卡的时刻。做法选错会让后面的阶段错过独占窗口，训练墙钟继续拉长。",
        "choices": [
            {"id": "GRAB", "label": "抢占", "kind": "surge"},
            {"id": "BATCH", "label": "批处理", "kind": "norm"},
            {"id": "SHARE", "label": "共享", "kind": "skip"},
            {"id": "WIN", "label": "独占窗", "kind": "meet"},
        ],
        "stages": ["预处理", "训练", "校验", "导出", "补训"],
        "surge_title": "抢占回滚",
        "surge_why": "抢占被中断后要在本阶段重放一段，作业分钟变长。",
        "wave_title": "独占窗口",
        "wave_why": "抢占和批处理都要整卡。错过独占窗口就得等到下一窗，卡在队列里空等。",
        "seam_title": "镜像交接",
        "seam_why": "相邻阶段换做法要先换运行镜像，这段时间不能开算。",
        "board_title": "独占预约",
        "board_why": "独占窗只能在预约时刻启动，时刻没到不能占卡。",
        "cf_text": "若抢占不用回滚、作业分钟恢复表上的数字，",
        "time_label": "五阶段全部跑完的时刻（从 0 分钟起算）",
        "cost_label": "算力费用合计",
        "time_phrase": "五阶段全部跑完的时刻最小",
        "cost_phrase": "算力费用合计最小",
        "plan": "给出五阶段各自的做法代号，按段序用短横线连接，例如 GRAB-SHARE-GRAB-SHARE-GRAB。",
    },
    {
        "id": "galley",
        "role": "你为已经定好上菜顺序的五道菜各选一种出餐做法。上菜顺序不能改。",
        "carry": "五道按上菜顺序做。上一道的完成时刻就是下一道可以起火的时刻。做法选错会让后面的菜错过炉位窗口，整桌和外卖一起延误。",
        "choices": [
            {"id": "SEAR", "label": "急火", "kind": "surge"},
            {"id": "STEW", "label": "炖档", "kind": "norm"},
            {"id": "HOLD", "label": "保温", "kind": "skip"},
            {"id": "RIDER", "label": "骑手窗", "kind": "meet"},
        ],
        "stages": ["凉菜", "热炒", "炖品", "主食", "打包"],
        "surge_title": "急火回锅",
        "surge_why": "急火要在本道把锅再热一次，作业分钟变长。",
        "wave_title": "炉位窗口",
        "wave_why": "急火和炖档都要主炉。错过档口就得等下一轮，菜在台面变凉。",
        "seam_title": "灶台交接",
        "seam_why": "相邻两道换做法要先清灶，这段时间不能起下一道。",
        "board_title": "骑手时刻",
        "board_why": "骑手窗只能在骑手到店时刻开始打包，人没到不能交接。",
        "cf_text": "若急火不用回锅、作业分钟恢复表上的数字，",
        "time_label": "五道全部出完的时刻（从 0 分钟起算）",
        "cost_label": "出餐费用合计",
        "time_phrase": "五道全部出完的时刻最小",
        "cost_phrase": "出餐费用合计最小",
        "plan": "给出五道各自的做法代号，按段序用短横线连接，例如 SEAR-HOLD-SEAR-HOLD-SEAR。",
    },
    {
        "id": "fresh",
        "role": "你为已经排好时段的五段生鲜补货各选一种补货做法。时段顺序不能改。",
        "carry": "五段按一天的顺序补。上一段的完成时刻就是下一段可以开始的时刻。做法选错会让后面的时段错过冷库窗口，缺货和损耗一起上去。",
        "choices": [
            {"id": "PUSH", "label": "直补", "kind": "surge"},
            {"id": "FACE", "label": "排面", "kind": "norm"},
            {"id": "BACK", "label": "后仓", "kind": "skip"},
            {"id": "DAWN", "label": "晨配", "kind": "meet"},
        ],
        "stages": ["开门前", "午前", "午后", "晚高峰", "闭店前"],
        "surge_title": "直补复称",
        "surge_why": "直补要在本段把重量再核一遍，作业分钟变长。",
        "wave_title": "冷库窗口",
        "wave_why": "直补和排面都要进冷库。错过开门时段就得等下一轮，货在月台升温。",
        "seam_title": "货架交接",
        "seam_why": "相邻两段换做法要先交接库存数，这段时间不能上架。",
        "board_title": "晨配时刻",
        "board_why": "晨配只能在到货时刻开始，车没到不能补。",
        "cf_text": "若直补不用复称、作业分钟恢复表上的数字，",
        "time_label": "五段全部补完的时刻（从 0 分钟起算）",
        "cost_label": "补货费用合计",
        "time_phrase": "五段全部补完的时刻最小",
        "cost_phrase": "补货费用合计最小",
        "plan": "给出五段各自的做法代号，按段序用短横线连接，例如 PUSH-BACK-PUSH-BACK-PUSH。",
    },
    {
        "id": "canteen",
        "role": "你为已经排好开餐顺序的五个时段各选一种供餐做法。时段顺序不能改。",
        "carry": "五个时段按课表接。上一段的完成时刻就是下一段可以开窗的时刻。做法选错会让后面的时段错过出餐窗口，队伍堵在窗口。",
        "choices": [
            {"id": "EXPRESS", "label": "快窗", "kind": "surge"},
            {"id": "HOT", "label": "热菜", "kind": "norm"},
            {"id": "SET", "label": "套餐", "kind": "skip"},
            {"id": "BELL", "label": "铃次", "kind": "meet"},
        ],
        "stages": ["早自习后", "第一节后", "午休", "第三节后", "晚自习前"],
        "surge_title": "快窗回热",
        "surge_why": "快窗要在本段把预制菜再热一遍，作业分钟变长。",
        "wave_title": "灶台窗口",
        "wave_why": "快窗和热菜都要主灶。错过档口就得等下一轮，学生堵在窗口外。",
        "seam_title": "窗口交接",
        "seam_why": "相邻两段换做法要先换餐具和菜单，这段时间不能开窗。",
        "board_title": "下课铃次",
        "board_why": "铃次只能在给定的下课时刻开窗，铃没响不能放人。",
        "cf_text": "若快窗不用回热、作业分钟恢复表上的数字，",
        "time_label": "五段全部供完的时刻（从 0 分钟起算）",
        "cost_label": "供餐费用合计",
        "time_phrase": "五段全部供完的时刻最小",
        "cost_phrase": "供餐费用合计最小",
        "plan": "给出五段各自的做法代号，按段序用短横线连接，例如 EXPRESS-SET-EXPRESS-SET-EXPRESS。",
    },
    {
        "id": "plug",
        "role": "你为已经按到达顺序排好的五辆车各选一种补能做法。车辆顺序不能改。",
        "carry": "五辆按到达顺序补能。上一辆的完成时刻就是下一辆可以开始的时刻。做法选错会让后面的车错过功率窗口，车位被占着，后面继续排队。",
        "choices": [
            {"id": "BOOST", "label": "快充", "kind": "surge"},
            {"id": "TRICKLE", "label": "慢充", "kind": "norm"},
            {"id": "SWAP", "label": "换电", "kind": "skip"},
            {"id": "BOOK", "label": "预约桩", "kind": "meet"},
        ],
        "stages": ["第一辆", "第二辆", "第三辆", "第四辆", "第五辆"],
        "surge_title": "快充降额",
        "surge_why": "快充在连续使用时要降额，本辆的作业分钟变长。",
        "wave_title": "功率窗口",
        "wave_why": "快充和慢充都受场站功率档限制。错过档期就得等下一档，车停在桩上不出电。",
        "seam_title": "接头交接",
        "seam_why": "相邻两辆换做法要先换接头或换电平台，这段时间下一辆不能开始。",
        "board_title": "预约时刻",
        "board_why": "预约桩只能在预约时刻启动，时刻没到不能插枪。",
        "cf_text": "若快充不降额、作业分钟恢复表上的数字，",
        "time_label": "五辆全部补完的时刻（从 0 分钟起算）",
        "cost_label": "补能费用合计",
        "time_phrase": "五辆全部补完的时刻最小",
        "cost_phrase": "补能费用合计最小",
        "plan": "给出五辆各自的做法代号，按段序用短横线连接，例如 BOOST-SWAP-BOOST-SWAP-BOOST。",
    },
    {
        "id": "relief",
        "role": "你为已经排好发放顺序的五批物资各选一种运送做法。批次顺序不能改。",
        "carry": "五批按需求顺序送。上一批的完成时刻就是下一批可以装车的时刻。做法选错会让后面的批次错过道路窗口，缺口继续放大。",
        "choices": [
            {"id": "TRUCK", "label": "公路", "kind": "surge"},
            {"id": "RELAY", "label": "接力", "kind": "norm"},
            {"id": "DEPOT", "label": "前置仓", "kind": "skip"},
            {"id": "CONVOY", "label": "车队窗", "kind": "meet"},
        ],
        "stages": ["饮水", "药品", "口粮", "帐篷", "燃料"],
        "surge_title": "公路绕行",
        "surge_why": "公路直送要在本批绕开阻断点，作业分钟变长。",
        "wave_title": "道路窗口",
        "wave_why": "公路和接力都要过临时放行点。错过放行就得等下一窗，物资停在半路。",
        "seam_title": "运力交接",
        "seam_why": "相邻两批换做法要先交接车辆和单据，这段时间不能发车。",
        "board_title": "车队时刻",
        "board_why": "车队窗只能在集结时刻发车，人没齐不能走。",
        "cf_text": "若公路不用绕行、作业分钟恢复表上的数字，",
        "time_label": "五批全部送达的时刻（从 0 分钟起算）",
        "cost_label": "运输费用合计",
        "time_phrase": "五批全部送达的时刻最小",
        "cost_phrase": "运输费用合计最小",
        "plan": "给出五批各自的做法代号，按段序用短横线连接，例如 TRUCK-DEPOT-TRUCK-DEPOT-TRUCK。",
    },
    {
        "id": "bed",
        "role": "你为已经排好转科顺序的五个病区各选一种清床做法。病区顺序不能改。",
        "carry": "五个病区按转科顺序清。上一区的完成时刻就是下一区可以开始的时刻。做法选错会让后面的病区错过终末消毒窗口，新病人进不了床。",
        "choices": [
            {"id": "WIP", "label": "即清", "kind": "surge"},
            {"id": "TERM", "label": "终末", "kind": "norm"},
            {"id": "ISO", "label": "隔离组", "kind": "skip"},
            {"id": "CREW", "label": "保洁窗", "kind": "meet"},
        ],
        "stages": ["一病区", "二病区", "三病区", "ICU", "隔离区"],
        "surge_title": "即清复消",
        "surge_why": "即清要在本区把表面再消一遍，作业分钟变长。",
        "wave_title": "消毒窗口",
        "wave_why": "即清和终末都要等消毒机档期。错过档期就得等下一轮，空床不能收治。",
        "seam_title": "班组交接",
        "seam_why": "相邻两区换做法要先交接隔离要求，这段时间不能进下一区。",
        "board_title": "保洁时刻",
        "board_why": "保洁窗只能在排班时刻进场，人没到不能清床。",
        "cf_text": "若即清不用复消、作业分钟恢复表上的数字，",
        "time_label": "五区全部清完的时刻（从 0 分钟起算）",
        "cost_label": "清床费用合计",
        "time_phrase": "五区全部清完的时刻最小",
        "cost_phrase": "清床费用合计最小",
        "plan": "给出五区各自的做法代号，按段序用短横线连接，例如 WIP-ISO-WIP-ISO-WIP。",
    },
    {
        "id": "crowd",
        "role": "你为已经排好时段的五段入场各选一种安检做法。时段顺序不能改。",
        "carry": "五段按入场顺序接。上一段的完成时刻就是下一段可以放行的时刻。做法选错会让后面的时段错过安检窗口，入口密度继续堆高。",
        "choices": [
            {"id": "OPEN", "label": "常开", "kind": "surge"},
            {"id": "SCREEN", "label": "严检", "kind": "norm"},
            {"id": "SPLIT", "label": "分流", "kind": "skip"},
            {"id": "GATE", "label": "放行窗", "kind": "meet"},
        ],
        "stages": ["开场前", "入场初", "高峰", "中场", "散场"],
        "surge_title": "常开复检",
        "surge_why": "常开通道要在本段把可疑人员再检一遍，作业分钟变长。",
        "wave_title": "安检窗口",
        "wave_why": "常开和严检都受安检机档期限制。错过档期就得等下一轮，队伍停在入口。",
        "seam_title": "警力交接",
        "seam_why": "相邻两段换做法要先调整警力和广播，这段时间不能放行。",
        "board_title": "放行时刻",
        "board_why": "放行窗只能在给定时刻开门，时刻没到不能放人。",
        "cf_text": "若常开不用复检、作业分钟恢复表上的数字，",
        "time_label": "五段全部放完的时刻（从 0 分钟起算）",
        "cost_label": "安保费用合计",
        "time_phrase": "五段全部放完的时刻最小",
        "cost_phrase": "安保费用合计最小",
        "plan": "给出五段各自的做法代号，按段序用短横线连接，例如 OPEN-SPLIT-OPEN-SPLIT-OPEN。",
    },
    {
        "id": "maint",
        "role": "你为已经排好工序的五步检修各选一种作业做法。工序顺序不能改。",
        "carry": "五步按工序接。上一步的完成时刻就是下一步可以开始的时刻。做法选错会让后面的工序错过停电窗口，设备不能按计划送电。",
        "choices": [
            {"id": "HOT", "label": "热修", "kind": "surge"},
            {"id": "SWAP", "label": "更换", "kind": "norm"},
            {"id": "BYPASS", "label": "旁路", "kind": "skip"},
            {"id": "OUTAGE", "label": "停电窗", "kind": "meet"},
        ],
        "stages": ["巡检", "紧固", "润滑", "校验", "试车"],
        "surge_title": "热修复测",
        "surge_why": "热修要在本步带电复测，作业分钟变长。",
        "wave_title": "停电窗口",
        "wave_why": "热修和更换都要停电档。错过档期就得等下一窗，设备继续带着故障运行。",
        "seam_title": "工单交接",
        "seam_why": "相邻两步换做法要先交接工作票，这段时间不能开工。",
        "board_title": "停电时刻",
        "board_why": "停电窗只能在批准时刻开始，调度没下令不能动设备。",
        "cf_text": "若热修不用复测、作业分钟恢复表上的数字，",
        "time_label": "五步全部做完的时刻（从 0 分钟起算）",
        "cost_label": "检修费用合计",
        "time_phrase": "五步全部做完的时刻最小",
        "cost_phrase": "检修费用合计最小",
        "plan": "给出五步各自的做法代号，按段序用短横线连接，例如 HOT-BYPASS-HOT-BYPASS-HOT。",
    },
    {
        "id": "drone",
        "role": "你为已经排好起飞顺序的五架配送各选一种飞行做法。起飞顺序不能改。",
        "carry": "五架按顺序飞。上一架的完成时刻就是下一架可以申请空域的时刻。做法选错会让后面的架次错过空域窗口，订单继续延误。",
        "choices": [
            {"id": "DIRECT", "label": "直飞", "kind": "surge"},
            {"id": "CORRIDOR", "label": "走廊", "kind": "norm"},
            {"id": "GROUND", "label": "地面", "kind": "skip"},
            {"id": "SLOT", "label": "时隙", "kind": "meet"},
        ],
        "stages": ["一架", "二架", "三架", "四架", "五架"],
        "surge_title": "直飞复飞",
        "surge_why": "直飞要在本架把避障航段再飞一次，作业分钟变长。",
        "wave_title": "空域窗口",
        "wave_why": "直飞和走廊都要申请空域。错过窗口就得在起降点等下一轮，电量继续耗。",
        "seam_title": "吊舱交接",
        "seam_why": "相邻两架换做法要先换吊舱和航线，这段时间不能起飞。",
        "board_title": "时隙时刻",
        "board_why": "时隙只能在给定时刻起飞，时刻过了就要等下一班时隙。",
        "cf_text": "若直飞不用复飞、作业分钟恢复表上的数字，",
        "time_label": "五架全部送达的时刻（从 0 分钟起算）",
        "cost_label": "飞行费用合计",
        "time_phrase": "五架全部送达的时刻最小",
        "cost_phrase": "飞行费用合计最小",
        "plan": "给出五架各自的做法代号，按段序用短横线连接，例如 DIRECT-GROUND-DIRECT-GROUND-DIRECT。",
    },
]


def _repair(family: CascadeFamily) -> None:
    def normalize(plan: tuple) -> tuple | None:
        # 评分时先有世界。这里只校验代号形状，段位合法性在 simulate 里再对表。
        if not plan or not all(isinstance(p, str) and p.isupper() for p in plan):
            return None
        return tuple(plan)

    family.normalize_plan = normalize  # type: ignore


FAMILIES = {}
SPEC_OF = {}
for _spec in SPECS:
    _fam = CascadeFamily(_spec)
    _repair(_fam)
    FAMILIES[_spec["id"]] = _fam
    SPEC_OF[_spec["id"]] = _spec
