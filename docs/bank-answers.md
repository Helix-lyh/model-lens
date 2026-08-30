# 题库参考答案与评分机制（48 条原始题，展开后 72 道）

维护者文档。题面在 `bank/questions.yaml`，本文只放答案，**不要**把答案写回题面。
编码题的 Go/TS 参考实现见 `cursor_workspace/build_scripts/verify_lang_sandboxes.py`，
Python 参考实现与结构题期望输出见 `cursor_workspace/build_scripts/verify_bank_answers.py`；
两个脚本都会把参考答案跑进真实沙箱，必须全部满分。

## 评分机制

- 题库共 48 条原始题（12 架构 + 12 知识 + 12 推理 + 12 编码）；题量上限 20–60 按展开前计。
  编码题按 python/go/typescript 展开，展开后共 72 道。
- 每题若干得分点，折合满分 10：`score10 = 10 × n / m`。只按域、按难度聚合展示，不合成总分。
- 快速模式只跑 easy/medium（展开后 48 道），每题 1 次 t=0；全量 72 道，每题 4 次采样（t=0、0.7×3），
  pass0 取 t=0 那次，majority 需至少 3 次可判且 ≥3 次通过。
- 完成 token 超过难度上限（easy 8 万 / medium 10 万 / hard 12.8 万）记 think penalty，score10 减半。
- 四类 grader：
  - `keyword`：每命中一组 `must_include` 得 1 分；命中数 ≥ `min_hits` 且没碰 `must_exclude` 才 pass。
  - `alias`：规范化（NFKC、去标点、casefold、去空白）后与 `answers` 精确/包含匹配，1 分。
  - `code_tests`：按语言抽围栏代码，进沙箱编译加跑测；只认 stdout 里最后一个 `POINTS n/m`，
    满点才 pass；编译失败、禁运 import、超时、缺 POINTS 都是 0。缺工具链记 missing 不记 0。
  - `structure`：抽 json/text 块写入 `payload.txt`，跑 `tests_file` 逐条计点。
- 知识域 t=0 全错触发 `knowledge_alarm`（疑似空响应或完全不对题）。

## 一、架构域（12 题，keyword，min_hits=4，每组 1 分）

参考答案是「应命中的要点」，每行对应一个计分组。

### architecture-easy-01 高 QPS 商品详情缓存（5 组）
1. 缓存商品详情快照/热点数据（缓存、cache）
2. 键按商品 id / sku 设计，如 `item:{sku}`（键、sku）
3. 穿透用空值缓存或布隆过滤器；击穿用互斥锁 / singleflight（击穿、穿透、布隆、互斥锁）
4. TTL 加随机抖动，避免同时失效（过期、ttl）
5. 热点预热，提前加载（热点、预热）

### architecture-easy-02 Session vs JWT（5 组）
1. Session 适合传统 Web、需要即时注销的场景（session、会话）
2. JWT 适合跨服务/移动端无状态鉴权（jwt、token）
3. 注销：Session 删服务端记录即可；JWT 需黑名单或短有效期+refresh（注销、吊销）
4. Session 有服务端存储；JWT 无状态、服务端不存（无状态、存储）
5. JWT 体积大、随请求携带；密钥轮换要支持多 key 验签（体积、密钥、轮换）

### architecture-easy-03 下单后发短信/积分（4 组）
1. 引入消息队列异步解耦，下单接口只写消息（队列、异步、解耦）
2. 至少一次投递靠重试 + 持久化（至少一次、重试）
3. 重复消费靠幂等/去重（业务唯一键）（幂等、去重）
4. 消费者处理完再 ack，失败重投（消费者、ack、确认）

### architecture-medium-01 单体不要急着拆微服务（5 组）
1. 团队小、请求量低、边界不清时不该拆（不该拆、过早拆）
2. 拆了徒增团队沟通与认知负担（团队、沟通、认知负担）
3. 跨服务事务和数据一致性变难（事务、一致性、分布式事务）
4. 运维、部署、可观测复杂度飙升（运维、部署、复杂度）
5. 先在单体里按领域划模块、理清边界（边界、领域、模块）

### architecture-medium-02 网关限流/超时/重试（4 组）
1. 限流防流量超载打垮后端（限流、配额）
2. 超时防慢依赖拖死调用方线程（超时、timeout）
3. 重试补偿偶发失败（重试、retry）
4. 重试会放大故障成重试风暴/雪崩，须配退避、预算和幂等（雪崩、重试风暴、放大）

### architecture-medium-03 日志/指标/追踪分工（4 组）
1. 日志：单次请求的详细现场，能看到那笔订单扣库存的分支与报错（日志、log）
2. 指标：聚合趋势与报警，如「扣库存失败率突增」（指标、metric、监控）
3. 追踪：一次请求跨服务的 span 链，定位断在哪一跳（追踪、trace、span）
4. 三者用请求 id / 调用链串起来互相跳转（请求、链路、调用链）

### architecture-hard-01 OFFSET 200000 深分页（4 组）
1. 深分页要扫过并丢弃前 20 万行，代价随页数线性涨（深分页、offset）
2. 建 (created_at, id) 复合索引（索引、index）
3. 用游标/seek 分页：`WHERE (created_at, id) < (?, ?) ORDER BY ... LIMIT n`（游标、seek、created_at）
4. OFFSET 扫描慢且伤缓冲池（扫描、慢、代价）

### architecture-hard-02 2GB 视频上传（5 组）
1. 直传对象存储（OSS/S3/COS）（对象存储）
2. 浏览器拿预签名 URL 直传（直传、预签名）
3. 经应用服务器中转会吃双份带宽、占连接（带宽、中转）
4. 预签名 URL 限定桶/键/大小并短时过期，即鉴权（鉴权、过期）
5. 上传完成回调后异步病毒扫描，过检才可见（扫描、病毒、回调）

### architecture-easy-04 读写分离后读到旧昵称（5 组）
1. 一主多从，读打到从库（主从、从库、复制）
2. 复制是异步的，存在延迟（延迟、lag、异步）
3. 缓解一：写后短窗口内强制读主（读主、强制走主、强一致）
4. 缓解二：会话粘性，同一用户写后读走同一路径（会话、粘性、写后读）
5. 缓解三：客户端本地回显/缓存新值，或按 GTID 位点等待从库追上（缓存、gtid、位点）

### architecture-medium-04 推荐服务灰度发布（5 组）
1. 金丝雀：先放小比例实例/用户（灰度、金丝雀、canary）
2. 切流按权重逐步放大（1%→5%→25%→100%），可先白名单（流量、权重、比例）
3. 观察错误率、p99 延迟、业务指标，与基线对比（指标、错误率、p99）
4. 指标越阈值自动回滚到旧版本（回滚、rollback）
5. 新旧版本共存期间接口与 schema 必须兼容，必要时双写（兼容、双写、schema）

### architecture-hard-03 Redis 互斥锁（5 组）
1. `SET key val NX PX ttl` 原子拿锁实现互斥（setnx、互斥）
2. 必须带过期时间，防实例宕机死锁（过期、ttl）
3. 任务没跑完锁要到期：看门狗定期续期（续期、看门狗）
4. value 放唯一标识，释放用 Lua 先校验再删，防误删别人的锁（唯一、标识、lua、校验）
5. 锁过期后旧持有者还在跑：下游用 fencing token / epoch 兜底（fencing、fence、epoch）

### architecture-hard-04 支付回调防重与补单（5 组）
1. 回调按第三方流水号做幂等：唯一索引/去重表，重复直接返回成功（幂等、去重、唯一索引）
2. 订单状态机只允许合法迁移，已到终态（已支付）的回调不再入账（状态机、终态、已支付）
3. 漏单靠定时对账 + 主动查询第三方订单状态补单（对账、补单、主动查询）
4. 入账与改状态在一个事务里，保证原子（事务、原子、一致）
5. 乱序用版本号/第三方时间戳判断，旧通知不覆盖新状态（版本号、时间戳、序号）

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

## 三、知识域（12 题）

### 直觉陷阱（alias，match: exact，1 点）

| 题号 | 题意 | 标准答案 |
|---|---|---|
| knowledge-easy-01 | 热锅里放 7 颗冰糖，两分钟后完整颗数 | `0` |
| knowledge-easy-02 | 纸箱触地后人才下楼，箱子在哪 | `地面`（也收 `一楼`/`一层`/`1楼`） |
| knowledge-easy-03 | 已确认死亡的金鱼活着的概率（百分数） | `0` |
| knowledge-easy-04 | 一公斤棉花 vs 一公斤铁哪个重 | `一样重` |
| knowledge-medium-01 | 正轨 4 具遗体、侧轨 1 名活人，扳不扳 | `不扳` |
| knowledge-medium-04 | 先涨 10% 再降 10%，与原价比 | `更低`（0.99 倍） |

### 结构遵循（structure，逐条计点）

**knowledge-medium-02**（`c06_lines.py`，7 点）期望 text 块：

```text
<<HEAD>>
drahcro
7
dra*cro
<<TAIL>>
```

**knowledge-medium-03**（`c08_oneline.py`，7 点）期望单行 JSON（原文必须出现 `-0`，空格 ≤3）：

```json
{"z":{"z":{"z":"ok"}},"a":[],"z2":-0}
```

**knowledge-hard-01**（`c05_nested.py`，8 点）期望 JSON（第 4 层键是 `0k`）：

```json
{"root":{"ok":{"ok":{"ok":{"0k":{"ok":{"tip":42,"_":[0,null,false]}}}}}}}
```

**knowledge-hard-02**（`c07_array.py`，8 点）期望 JSON 数组（下标 3 是 null，末位 mark 大写）：

```json
[{"i":0,"sq":0,"mark":"n"},{"i":1,"sq":1,"mark":"n"},{"i":2,"sq":4,"mark":"n"},null,{"i":4,"sq":16,"mark":"n"},{"i":5,"sq":25,"mark":"N"}]
```

**knowledge-hard-03**（`c09_lines6.py`，8 点）期望 text 块（signal 去元音 `sgnl`）：

```text
[[v2]]
sgnl
sgnl-sgnl
9
lngs
[[end]]
```

**knowledge-hard-04**（`c10_meta.py`，8 点）期望 JSON（`v` 原文必须写 `1e2`）：

```json
{"data":["0",0,false,null],"meta":{"v":1e2,"k k":{}}}
```

## 四、推理域（12 题）

### 单答案推理（alias，match: exact，1 点）

| 题号 | 题意 | 标准答案 | 解析 |
|---|---|---|---|
| reasoning-easy-01 | 数列 2,6,12,20,30 下一项 | `42` | 通项 n(n+1)，6×7=42 |
| reasoning-easy-02 | 甲乙丙谁说真话 | `乙` | 设甲真则丙也真，矛盾；甲谎→乙真→丙谎，自洽且唯一 |
| reasoning-easy-03 | 周三之后 100 天 | `星期五`（也收 `周五`） | 100 mod 7 = 2，周三 + 2 = 周五 |
| reasoning-easy-04 | 50 人容斥 | `15` | 至少会一样 50−10=40；30+25−40=15 |
| reasoning-medium-01 | 8 球找重球最少称几次 | `2` | 3+3 上秤：平则剩 2 个再称 1 次；不平则重的 3 个里 1+1 再称 1 次 |
| reasoning-medium-02 | 小钱的职业 | `医生` | 小孙排除工程师和医生→教师；小赵不是医生→医生只能是小钱 |
| reasoning-medium-03 | 草地湿能否断定下雨 | `不能` | 肯定后件谬误：洒水车等也能让草地湿 |
| reasoning-medium-04 | 三场会议最少几间会议室 | `3` | 10:15–10:30 三场同时进行，峰值重叠数 3 |
| reasoning-hard-01 | A 说「我和 B 都是说谎者」，B 是什么 | `诚实者` | A 若诚实则自己是说谎者，矛盾→A 说谎→「都是说谎者」为假→B 诚实 |
| reasoning-hard-02 | 100 盏灯按倍数轮流按开关 | `10` | 第 i 盏被按 d(i) 次，奇数次仅完全平方数：1,4,…,100 共 10 个 |
| reasoning-hard-04 | 数字谜三位数 | `844` | 设个位 u：百位 2u，十位 2u−u=u，和 4u=16→u=4→844 |

### 结构化推理（structure，逐条计点）

**reasoning-hard-03**（`c11_logic_grid.py`，8 点）逻辑网格。
推导：C 在 1 层且喝茶的在 2 层→C 不喝茶；B 喝咖啡→C 喝可乐→A 喝茶→A 在 2 层→B 在 3 层。
期望 JSON：

```json
{"A": {"floor": 2, "drink": "茶"}, "B": {"floor": 3, "drink": "咖啡"}, "C": {"floor": 1, "drink": "可乐"}}
```
