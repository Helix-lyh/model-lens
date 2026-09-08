# 题库参考答案与评分机制（54 条原始题，展开后 78 道）

维护者文档。题面在 `bank/questions.yaml`，本文只放答案，**不要**把答案写回题面。
bank-v2.1 改写了 24 道非编码题，设计说明与参考 JSON 见 `docs/bank-v2-design.md`。
编码题的 Go/TS 参考实现见 `cursor_workspace/build_scripts/verify_lang_sandboxes.py`，
Python 参考实现与结构题期望输出见 `cursor_workspace/build_scripts/verify_bank_answers.py`；
两个脚本都会把参考答案跑进真实沙箱，必须全部满分。

## 评分机制

- 题库共 54 条原始题（12 架构 + 12 知识 + 18 推理 + 12 编码）；题量上限 20–60 按展开前计。
  编码题按 python/go/typescript 展开，展开后共 78 道。
- 每题若干得分点，折合满分 10：`score10 = 10 × n / m`。只按域、按难度聚合展示，不合成总分。
- 快速模式只跑 easy/medium（展开后 14 道实例），每题 1 次 t=0；全量 78 道，每题 1 次 t=0。
  pass0 取该次；单次采样下 majority 为 None。高 token 用量不改变机械评分。
- 四类 grader：
  - `keyword`：每命中一组 `must_include` 得 1 分；命中数 ≥ `min_hits` 且没碰 `must_exclude` 才 pass。
    现行仅 `architecture-easy-01`、`architecture-medium-01`。
  - `alias`：规范化（NFKC、去标点、casefold、去空白）后与 `answers` 精确/包含匹配，1 分。
    现行仅 `reasoning-easy-01/02`、`reasoning-medium-01/02`。
  - `code_tests`：按语言抽围栏代码，进沙箱编译加跑测；只认 stdout 里最后一个 `POINTS n/m`，
    满点才 pass；编译失败、禁运 import、超时、缺 POINTS 都是 0。缺工具链记 missing 不记 0。
  - `structure`：抽 json/text 块写入 `payload.txt`，跑 `tests_file` 逐条计点。
    指令题 `grader.strict_response=true` 时原样传递响应，不得剥围栏或首尾空白。
  题面锁类型和带干扰项的枚举；不用 LLM-as-judge。
- 知识域 t=0 全错触发 `knowledge_alarm`（疑似空响应或完全不对题）。
- 结构题权威期望以 `cursor_workspace/build_scripts/verify_bank_answers.py` 的 `STRUCTURE` 与对应
  `bank/tests/v2_*.py`（或未改写的 `a_*.py` / `r_*.py`）fixture 为准。改题面、fixture 或等价规则必须升版本。
  现行未改写收束：`r_extreme_04.witness` 为 `BIND_SUM`。
- **已作废，禁止用来改现行 fixture：** `c05_nested.py`、`c06_lines.py`、`c07_array.py`、`c08_oneline.py`、
  `c09_lines6.py`、`c10_meta.py`、`c11_logic_grid.py`，以及旧 `a_hard_01..04` / `a_extreme_01` /
  `a_extreme_03` / `k_hard_*` / `k_extreme_*` / `r_hard_01..04` / `r_extreme_01` / `r_extreme_05`
  的 JSON（如 OFFSET_SCAN、711.90、reading_mA、深分页 keyword）。这些 `tests_file` 已换成 `v2_*`。

## 一、架构域（12 题）

现行不是「12 题 keyword」。easy/medium 为 keyword；hard-01..04 为指令遵循 structure（`strict_response`）；其余 hard/extreme 为普通 structure。

### architecture-easy-01 高 QPS 商品详情缓存（keyword，4 组，min_hits=4）
1. 缓存商品详情（缓存、cache）
2. 键按商品 id / sku（键、key、sku）
3. TTL / 过期（ttl、过期、失效）
4. 击穿防护：互斥锁 / singleflight / 预热（击穿、互斥锁、singleflight、预热）

### architecture-medium-01 推荐 API 灰度（keyword，5 组，min_hits=5）
1. 灰度 / 金丝雀 / 切流
2. 明确比例或白名单（5%、10%、1%、白名单）
3. 错误率 / p99 / 延迟
4. 超时 / 5xx / 可用率 / 点击率 / 转化率 / cpu
5. 可执行回滚条件

### architecture-hard-01..04 离线部署审批协议（`v2_architecture_hard_*.py`，指令题）
单行紧凑 JSON，键顺序按分支。权威期望见 `STRUCTURE` / v2 fixture / `docs/bank-v2-design.md`。

```json
{"status":"OK","kept":["c","a"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}
{"status":"OK","kept":["z","x"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":1}
{"status":"OK","kept":["q"],"trace":["DENY","TAKE","DUP","LIMIT"],"remaining":4}
{"status":"IMPOSSIBLE","conflict":["R0","R9"]}
```

旧 keyword（深分页 / 视频上传 / Redis 锁 / 支付回调）以及 OFFSET_SCAN JSON **不是**现行 hard-01..04。

### architecture-hard-05 outbox（`a_hard_05.py`）

```json
{"atomic_write":"ONE_DB_TRANSACTION","publisher_retry":"RETRY_UNSENT","consumer_key":"event_id","ack_order":"COMMIT_THEN_ACK","dead_letter":"AFTER_MAX_RETRIES","replay":"IDEMPOTENT"}
```

### architecture-extreme-01 钱包冲正（`v2_architecture_extreme_01.py`）

```json
{"actions":["APPLY","FUNDS","DUP","APPLY","APPLY","REFUND_LIMIT","APPLY"],"balance":7,"refundable_a":9,"seen":["a","b","c","d","e","f"]}
```

### architecture-extreme-02 发布回滚（`a_extreme_02.py`）

```json
{"read_mode":"OLD_FIRST","rollback_mode":"ROLL_BACK_APP_ONLY","data_action":"BACKFILL_THEN_RETRY","compat_window":10,"lost_records":0}
```

### architecture-extreme-03 fencing/CAS（`v2_architecture_extreme_03.py`）

```json
{"actions":["ACCEPT","STALE","CONFLICT","ACCEPT","ACCEPT"],"token":10,"version":6,"value":50}
```

### architecture-extreme-04 版本向量（`a_extreme_04.py`）

```json
{"relation":"CONCURRENT","resolution":"MANUAL_MERGE","value":"A+B","vector":{"east":5,"west":4},"audit":"RETAIN_BOTH"}
```

### architecture-extreme-05 共享预算（`a_extreme_05.py`）

```json
{"global_limit":240,"burst_capacity":60,"accepted_s1":300,"accepted_s2":60,"rejected_policy":"DROP_NO_REFUND","recovery":"RETRY_IDEMPOTENT"}
```

非现行题号（easy-02..04、medium-02..04、旧 keyword hard）已从 `questions.yaml` 移除，不要按旧答案改 fixture。

## 二、编码域（12 题 ×3 语言，code_tests，POINTS 满点才 pass）

下面给 Python 参考实现；Go/TS 参考实现逻辑一致，全文见 `verify_lang_sandboxes.py`。

### coding-easy-01 pack_runs（5 点）

```python
def pack_runs(xs):
    out = []
    for x in xs:
        if out and out[-1][0] == x:
            out[-1] = (x, out[-1][1] + 1)
        else:
            out.append((x, 1))
    return out
```

### coding-easy-02 validate_user（5 点）

```python
def validate_user(obj):
    errors = []
    name = obj.get("name")
    if not isinstance(name, str) or not name:
        errors.append("name")
    age = obj.get("age")
    if not isinstance(age, int) or isinstance(age, bool) or not (0 <= age <= 120):
        errors.append("age")
    return errors
```

### coding-easy-03 parse_badge（5 点）

```python
import re
from datetime import date

_RE = re.compile(r"^(\d{2})#(\d{2})\.(\d{2})\+(\d)$")


def parse_badge(s):
    m = _RE.fullmatch(s)
    if not m:
        return None
    y, mo, d, n = 2000 + int(m[1]), int(m[2]), int(m[3]), int(m[4])
    try:
        date(y, mo, d)
    except ValueError:
        return None
    return (y, mo, d, n)
```

### coding-easy-04 tag_scores（6 点）
考点：按第一个冒号拆分、冒号后整段必须是 `^-?\\d+$`、同名累加。

```python
import re

_SCORE = re.compile(r"^-?\d+$")


def tag_scores(items):
    out = {}
    for item in items:
        tag, sep, score = item.partition(":")
        if not sep or not tag or not _SCORE.fullmatch(score):
            continue
        out[tag] = out.get(tag, 0) + int(score)
    return out
```

### coding-medium-01 apply_ops 货架状态机（6 点）

```python
def apply_ops(ops):
    bins = {"A": 0, "B": 0, "C": 0}
    nxt = {"A": "B", "B": "C", "C": "A"}
    for raw in ops:
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "+":
            bins[parts[1]] += int(parts[2])
        elif parts[0] == "-":
            n = int(parts[2])
            if bins[parts[1]] >= n:
                bins[parts[1]] -= n
        elif parts[0] == ">":
            bins[parts[2]] += bins[parts[1]]
            bins[parts[1]] = 0
        elif parts[0] == "?" and bins[parts[1]] > 0:
            bins[parts[1]] -= 1
            bins[nxt[parts[1]]] += 1
    return bins
```

### coding-medium-02 cook_text 逐字符统计（5 点）

```python
def cook_text(s):
    vowels, nums, squeezes, i = {}, [], 0, 0
    while i < len(s):
        c = s[i]
        if c.isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            nums.append(int(s[i:j]))
            i = j
            continue
        run = 1
        while i + run < len(s) and s[i + run] == c:
            run += 1
        low = c.lower()
        if low in "aeiou":
            vowels[low] = vowels.get(low, 0) + run
        if c.isalpha() and run > 1:
            squeezes += run - 1
        i += run
    return {"vowels": vowels, "squeezes": squeezes, "nums": nums}
```

### coding-medium-03 orders_for_user_sql（7 点）

```python
def orders_for_user_sql(user_id):
    return (
        "SELECT id, user_id, created_at, amount FROM orders "
        f"WHERE user_id = {user_id} ORDER BY created_at DESC LIMIT 20"
    )
```

### coding-medium-04 render 模板渲染（8 点）
考点：`{{`/`}}` 转义优先、合法占位符 `[A-Za-z0-9_]+`、缺键与非法占位符原样保留。

```python
import re

_NAME = re.compile(r"\{([A-Za-z0-9_]+)\}")


def render(template, vars):
    out, i = [], 0
    while i < len(template):
        if template.startswith("{{", i):
            out.append("{")
            i += 2
            continue
        if template.startswith("}}", i):
            out.append("}")
            i += 2
            continue
        if template[i] == "{":
            m = _NAME.match(template, i)
            if m:
                name = m.group(1)
                out.append(vars[name] if name in vars else m.group(0))
                i = m.end()
                continue
        out.append(template[i])
        i += 1
    return "".join(out)
```

### coding-hard-01 FreezeBag（4 点）

```python
class FreezeBag:
    def __init__(self, capacity):
        self.cap = capacity
        self.vals = {}
        self.order = []
        self.frozen = set()

    def put(self, key, value):
        if key in self.vals:
            self.vals[key] = value
            self.order.remove(key)
            self.order.append(key)
            return
        if len(self.vals) >= self.cap:
            victim = next((k for k in self.order if k not in self.frozen), None)
            if victim is None:
                return
            del self.vals[victim]
            self.order.remove(victim)
        self.vals[key] = value
        self.order.append(key)

    def get(self, key):
        return self.vals.get(key)

    def freeze(self, key):
        if key in self.vals:
            self.frozen.add(key)
```

### coding-hard-02 SafeCounter（1 点）

```python
import threading


class SafeCounter:
    def __init__(self):
        self._lock = threading.Lock()
        self._n = 0

    def increment(self):
        with self._lock:
            self._n += 1

    def value(self):
        with self._lock:
            return self._n
```

### coding-hard-03 SlidingLimiter 滑动窗口限流（6 点）
考点：窗口左开右闭 `(ts-window, ts]`、被拒绝的请求不计入。

```python
class SlidingLimiter:
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self.allowed = []

    def allow(self, ts):
        lo = ts - self.window
        self.allowed = [t for t in self.allowed if t > lo]
        if len(self.allowed) < self.limit:
            self.allowed.append(ts)
            return True
        return False
```

### coding-hard-04 plan_tasks 字典序稳定拓扑排序（6 点）
考点：Kahn + 最小堆保证同层字典序、依赖对去重、环返回失败值。

```python
import heapq


def plan_tasks(tasks, deps):
    pairs = {(a, b) for a, b in deps}
    indeg = {t: 0 for t in tasks}
    after = {t: [] for t in tasks}
    for a, b in pairs:
        indeg[a] += 1
        after[b].append(a)
    ready = [t for t in tasks if indeg[t] == 0]
    heapq.heapify(ready)
    out = []
    while ready:
        t = heapq.heappop(ready)
        out.append(t)
        for nxt in after[t]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(ready, nxt)
    return out if len(out) == len(tasks) else None
```

## 三、知识域（12 题，全部 structure / bank-v2.1 RFC）

权威期望见 `STRUCTURE` 与 `bank/tests/v2_knowledge_*.py`，说明见 `docs/bank-v2-design.md`。
现行 `knowledge-hard-01` **不是** `c05_nested.py`。旧 alias 直觉陷阱、`c05_nested` / `c06_lines` / `c07_array` / `c08_oneline` / `c09_lines6` / `c10_meta` 已作废。

| 题号 | fixture | 参考 JSON |
|---|---|---|
| knowledge-easy-01 | `v2_knowledge_easy_01.py` | `{"address":"2001:db8::1:0:0:1"}` |
| knowledge-medium-01 | `v2_knowledge_medium_01.py` | `{"service":"UNAVAILABLE","alias_allowed":false}` |
| knowledge-hard-01 | `v2_knowledge_hard_01.py` | `{"relations":["NEWER","OLDER","UNDEFINED","EQUAL"],"add_250_10":4}` |
| knowledge-hard-02 | `v2_knowledge_hard_02.py` | `{"ttl":240,"nxdomain_key":["QNAME","QCLASS"],"nodata_key":["QNAME","QTYPE","QCLASS"]}` |
| knowledge-hard-03 | `v2_knowledge_hard_03.py` | `{"type":"TYPE65400","rdata":"\\# 3 00ff10","compress_names":false}` |
| knowledge-hard-04 | `v2_knowledge_hard_04.py` | `{"base64url":"_w==","base32":"74======","pad_bits_zero":true}` |
| knowledge-hard-05 | `v2_knowledge_hard_05.py` | `{"addresses":["2001:db8:0:1:2:3:4:5","2001::2:0:0:3:4","::"]}` |
| knowledge-extreme-01 | `v2_knowledge_extreme_01.py` | `{"after_first":4,"after_second":32771,"third_defined":false,"second_relation":"NEWER"}` |
| knowledge-extreme-02 | `v2_knowledge_extreme_02.py` | `{"x_hit":true,"y_hit":false,"x_remaining":30,"y_a_remaining":40}` |
| knowledge-extreme-03 | `v2_knowledge_extreme_03.py` | `{"first":["b","c"],"next":["a"],"weight_scope":"SAME_PRIORITY","target_alias":"FORBIDDEN"}` |
| knowledge-extreme-04 | `v2_knowledge_extreme_04.py` | `{"encodings":["MY======","MZXQ====","MZXW6==="],"alphabet_last":"7","bits_per_symbol":5}` |
| knowledge-extreme-05 | `v2_knowledge_extreme_05.py` | `{"lengths":[0,4],"hex_digits":[0,8],"empty_valid":true,"type_731":"TYPE731"}` |

## 四、推理域（18 题）

### 单答案推理（alias，match: exact，1 点）

| 题号 | 题意 | 标准答案 |
|---|---|---|
| reasoning-easy-01 | 1,4,9,16,25 下一项 | `36` |
| reasoning-easy-02 | 40 人容斥，两者都会几人 | `6` |
| reasoning-medium-01 | 甲乙丙职业约束，乙的职业 | `教师` |
| reasoning-medium-02 | 至少一红条件下两红概率 | `1/3` |

旧 alias 表（2,6,12,20,30→42、甲乙丙谁说真话、hard-01 说谎者等）对应的题号已改写，不要用来改 fixture。

### 指令遵循（`v2_reasoning_hard_01..04.py`，`strict_response`）

```json
{"status":"OK","kept":["o","m"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":0}
{"status":"OK","kept":["w","u"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}
{"status":"IMPOSSIBLE","conflict":["R0","R9"]}
{"status":"OK","kept":["x","z"],"trace":["TAKE","TAKE","LIMIT","DUP"],"remaining":1}
```

旧 `c11_logic_grid.py` / `r_hard_01..04` JSON **不是**现行 hard-01..04。

### 未改写 structure

**reasoning-hard-05**（`r_hard_05.py`）

```json
{"truth":[true,true,false],"liar_count":1,"consistent":true}
```

**reasoning-hard-06**（`r_hard_06.py`）4 色水杯配对。最坏最少交换 8；7 不够。

```json
{"swaps":8,"seven_enough":false}
```

**reasoning-hard-07**（`r_hard_07.py`）手套。右手任意两色最多 8 只，9 只右必齐三色，再加 1 左保证同色一对。

```json
{"n":10,"left":1,"right":9}
```

**reasoning-hard-08**（`r_hard_08.py`）光滑/粗糙球。12 只粗糙：R+G 最多 7，必有粗糙蓝；R+B 最多 11，必有粗糙绿。

```json
{"n":12,"smooth":0,"rough":12}
```

**reasoning-hard-09**（`r_hard_09.py`）线性探测。H(2022)=1、H(12)=1→2、H(25)=4；删 25 留墓碑。失败 ASL=1.8。

```json
{"h2022":1,"h12":2,"h25":4,"asl_fail":1.8}
```

**reasoning-extreme-01**（`v2_reasoning_extreme_01.py`）依赖/互斥背包。旧 `r_extreme_01.py` 的 `counterfactual_*` JSON 已作废。

```json
{"base_indices":[1,3,4],"base_value":18,"changed_indices":[0,2],"changed_value":19,"delta":1}
```

**reasoning-extreme-02**（`r_extreme_02.py`）

```json
{"trace":[5,10,13,10,13],"final":13,"rolled_back":"ADD_3","replayed":"ADD_3"}
```

**reasoning-extreme-03**（`r_extreme_03.py`）

```json
{"max_confidence":0.8,"decision":"CONFLICT","value":null,"witness":["E1","E2"]}
```

**reasoning-extreme-04**（`r_extreme_04.py`）`witness` 为 `BIND_SUM`。

```json
{"x":2,"y":5,"cost":3,"optimal":true,"witness":"BIND_SUM"}
```

**reasoning-extreme-05**（`v2_reasoning_extreme_05.py`）最短路径计数。旧 `difference` 字段 JSON 已作废。

```json
{"path":["A","B","D"],"cost":5,"count":5,"changed_path":["A","B","E","D"],"changed_cost":5,"changed_count":3}
```
