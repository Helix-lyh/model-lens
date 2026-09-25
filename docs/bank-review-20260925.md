# 题库评审稿 20260925

> 本稿由 `eval_bank_20260925.catalog`、独立答案验证器和同源用例机械导出。包含答案，不能整体发给待测模型。

版本：**20260925**。16 道核心题：8 道推理 + 8 道编程；每档 2+2。编程展开 Python / Go / TypeScript 后，共 32 个实例。难度为待实测校准的设计档位。

评分与运行方法见 [使用说明](../eval_bank_20260925/README.md)；设计取舍与 Grok 版核对见 [设计说明](bank-design-20260925.md)。

每题 20 个内容分点，`score10 = points / 2`。格式不奖励；只报告可检查的子结果，不要求模型输出私有思维链。推理字段或数组分量可以部分得分；编程每组 4 个计分检查，每检查 1 点，一个检查可能包含多个案例，必须全部正确。

## 题目索引

| ID | 难度 | 类型 | 题名 |
|---|---|---|---|
| R-E-01 | 简单 | 推理 | 包装金额与余数证书 |
| R-E-02 | 简单 | 推理 | 先验选择后的条件概率 |
| R-N-01 | 普通 | 推理 | 预先固定抽取的最坏情况 |
| R-N-02 | 普通 | 推理 | 带端点比较与奇偶性的禁位排列 |
| R-H-01 | 困难 | 推理 | 双处理器与互斥资源调度 |
| R-H-02 | 困难 | 推理 | 约束选物与没有增益的反事实 |
| R-X-01 | 超难 | 推理 | 可观察颜色的自适应抽取博弈 |
| R-X-02 | 超难 | 推理 | 缺角棋盘的计数与旋转去重 |
| P-E-01 | 简单 | 编程 | 半开区间归并 |
| P-E-02 | 简单 | 编程 | 逐字符转义分隔 |
| P-N-01 | 普通 | 编程 | 去重与原子库存批次 |
| P-N-02 | 普通 | 编程 | 拓扑顺序与真正的环成员 |
| P-H-01 | 困难 | 编程 | 带两层平局规则的区间调度 |
| P-H-02 | 困难 | 编程 | 快照事务与写写冲突 |
| P-X-01 | 超难 | 编程 | 带边计数的动态连通性 |
| P-X-02 | 超难 | 编程 | 错误优先级明确的寄存器解释器 |

## R-E-01 · 简单 · 包装金额与余数证书

### 题面

有面额为 5、8、11 的三种包装，数量均为非负整数，不限制包装总数。
求 1..50 中不能凑出的金额。输出对象：
residue_min：按余数 0,1,2,3,4 排列，能够凑出且模 5 为该余数的最小非负金额；
impossible：1..50 中不能凑出的全部金额，升序、不重复；largest：最大的不可达金额；count：不可达金额数量。
只输出一个 JSON 对象。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `residue_min` | 6 |
| `impossible` | 10 |
| `largest_count` | 4 |

设计意图：可达金额可反复加 5；最小余数代表给出有限证书。最终集合与统计量必须相互一致。

### 参考答案

```json
{
  "residue_min": [
    0,
    11,
    22,
    8,
    19
  ],
  "impossible": [
    1,
    2,
    3,
    4,
    6,
    7,
    9,
    12,
    14,
    17
  ],
  "largest": 17,
  "count": 10
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-E-02 · 简单 · 先验选择后的条件概率

### 题面

先选袋子：选择 U 的概率为 1/3，选择 V 的概率为 2/3。U 内有 3 红 1 蓝，V 内有 1 红 3 蓝。
在选中袋子中等概率、不放回抽两个球。报告程序当且仅当至少一个球是红色时输出 H；现在观察到 H。
求 likelihood_u=P(H|U)、likelihood_v=P(H|V)、posterior_u=P(U|H)、both_red=P(两球都红|H)。
每个概率使用 [分子,分母] 的整数数组，分母必须为正；等价分数均可。只输出包含这四个字段的 JSON。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `likelihood_u` | 4 |
| `likelihood_v` | 4 |
| `posterior_u` | 6 |
| `both_red` | 6 |

设计意图：区分条件化与直接平均，避免依赖自然语言含糊的观察者选择机制。

### 参考答案

```json
{
  "likelihood_u": [
    1,
    1
  ],
  "likelihood_v": [
    1,
    2
  ],
  "posterior_u": [
    1,
    2
  ],
  "both_red": [
    1,
    4
  ]
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-N-01 · 普通 · 预先固定抽取的最坏情况

### 题面

三种颜色按红、蓝、绿排序。左手套库存 L=[3,5,4]，右手套库存 R=[4,2,6]。
摸之前能选择左或右，不能挑颜色；取出后可看见颜色。但本题必须预先固定总共取 l 只左、r 只右，不能根据看到的颜色改变计划。
目标：无论抽到什么，都至少有一双同色左右手套。0<=l,r<=12。
输出 frontier：长度 13，frontier[l] 是仍存在无配对抽法时可取得的最多右手套数；minimum：最少 l+r；
allocations：所有达到 minimum 且必有配对的 [l,r]，按 l 升序；
counterexample：固定 (l,r)=(5,5) 的一种无配对抽法，含 left、right 两个长度 3 的非负整数数组，各颜色不超过库存。
只输出一个 JSON 对象。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `frontier` | 8 |
| `minimum` | 4 |
| `allocations` | 4 |
| `counterexample` | 4 |

设计意图：最小值必须同时有上界策略和下界反例；接受所有合法反例，不锁定一种写法。

### 参考答案

```json
{
  "frontier": [
    12,
    10,
    10,
    10,
    10,
    10,
    6,
    6,
    6,
    4,
    0,
    0,
    0
  ],
  "minimum": 11,
  "allocations": [
    [
      10,
      1
    ]
  ],
  "counterexample": {
    "left": [
      0,
      5,
      0
    ],
    "right": [
      4,
      0,
      1
    ]
  }
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-N-02 · 普通 · 带端点比较与奇偶性的禁位排列

### 题面

对 1..n 的排列 p，位置从 1 编号。要求 p(i)!=i，且 i<n 时 p(i)!=i+1；另要求 p(1)<p(n)。没有首尾环形禁位。
一个逆序对是 i<j 且 p(i)>p(j)。
输出 count4、count5：n=4、5 的合法排列数；parity7：[n=7 时逆序对数为偶数的合法排列数, 为奇数的合法排列数]；count7：n=7 合法排列总数。
只输出一个 JSON 对象。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `count4` | 3 |
| `count5` | 3 |
| `parity7` | 10 |
| `count7` | 4 |

设计意图：端点和奇偶条件打破直接套错排数的路径；小规模子问题可以独立拿分。

### 参考答案

```json
{
  "count4": 0,
  "count5": 3,
  "parity7": [
    93,
    91
  ],
  "count7": 184
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-H-01 · 困难 · 双处理器与互斥资源调度

### 题面

任务 A..F 的时长依次 [3,2,4,3,2,2]。依赖：A->C、A->D、B->E、C->F、D->F、E->F。
有两台相同处理器；任务不可抢占，每个任务使用一台处理器。开始时间是非负整数，执行区间为 [start,start+duration)，端点相接不重叠。
额外规则：C 和 E 使用同一独占资源，不能重叠。允许处理器主动空闲。
输出 lower_bounds：[只考虑依赖的最长路径时长, 总工作量除以 2 向上取整]；
base：含 makespan（全部任务完成的最早时间）、starts（A..F 的开始时间，最优方案中取字典序最小）；
optimal_count：最优 makespan 下不同开始时间向量的个数，不区分处理器编号；
changed：仅删除 C/E 资源互斥后，按相同规则给出 makespan、starts。
只输出一个 JSON 对象。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `lower_bounds` | 3 |
| `base` | 8 |
| `optimal_count` | 4 |
| `changed` | 5 |

设计意图：工作量和关键路径下界不一定可达；必须处理故意空闲、资源交互与反事实。

### 参考答案

```json
{
  "lower_bounds": [
    9,
    8
  ],
  "base": {
    "makespan": 10,
    "starts": [
      0,
      0,
      4,
      3,
      2,
      8
    ]
  },
  "optimal_count": 5,
  "changed": {
    "makespan": 9,
    "starts": [
      0,
      0,
      3,
      4,
      2,
      7
    ]
  }
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-H-02 · 困难 · 约束选物与没有增益的反事实

### 题面

有八件物品，下标 0..7 的 (重量,价值) 分别为
[(4,8),(5,11),(6,13),(3,7),(2,4),(4,9),(5,12),(1,2)]。每件最多选一次，总重量<=15。
规则：选 2 必须选 4；选 6 必须选 3；0 与 5 不能同选；1 与 6 不能同选。
最大化价值；并列先取总重量较小，再取升序下标数组字典序较小。空集合可行。
输出 base：{indices,value,weight,value_ties}，value_ties 是只按最大价值计的最优集合数，尚未应用后两项平局规则；
changed：仅删除 1/6 互斥后按同样规则的四字段对象；
feasible_counts：[原规则可行集合数,删除互斥后可行集合数]；delta：新最大价值减旧最大价值。
只输出 JSON。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `base` | 7 |
| `changed` | 7 |
| `feasible_counts` | 4 |
| `delta` | 2 |

设计意图：删除约束未必提高最优值，但可能改变最优解及最优解数量。

### 参考答案

```json
{
  "base": {
    "indices": [
      3,
      4,
      5,
      6,
      7
    ],
    "value": 34,
    "weight": 15,
    "value_ties": 1
  },
  "changed": {
    "indices": [
      1,
      3,
      4,
      6
    ],
    "value": 34,
    "weight": 15,
    "value_ties": 2
  },
  "feasible_counts": [
    72,
    75
  ],
  "delta": 0
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-X-01 · 超难 · 可观察颜色的自适应抽取博弈

### 题面

红、蓝、绿三色的左手套库存 [2,3,4]，右手套库存 [3,2,4]。
每一步选择取一只左或右，从该侧剩余手套中取出，颜色不能由你选择；取出后立刻看见颜色。允许据此调整下一步选择，出现同色左右配对立即成功。
问对最不利的颜色序列，最佳策略需要的最少总抽取数。不是期望值，不能放回。
输出 fixed：若预先固定左右数量时的最少总数；
after_first_left：首步取左且得到红/蓝/绿后，最佳自适应策略仍需要的最坏剩余步数，长度 3，不含首步；
first_action_costs：[强制首步左后的最佳最坏总数,强制首步右后的最佳最坏总数]；adaptive：不限制首步时的最少最坏总数。
只输出 JSON。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `fixed` | 4 |
| `after_first_left` | 8 |
| `first_action_costs` | 4 |
| `adaptive` | 4 |

设计意图：需要区分固定分配、可观察策略和 min-max 量词顺序。穷举状态递推验证最优性。

### 参考答案

```json
{
  "fixed": 9,
  "after_first_left": [
    6,
    7,
    6
  ],
  "first_action_costs": [
    8,
    8
  ],
  "adaptive": 8
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## R-X-02 · 超难 · 缺角棋盘的计数与旋转去重

### 题面

4 行 7 列棋盘，坐标 (行,列) 从 0 开始。删除 (0,0) 和 (3,6)。
用 1x2 骨牌无重叠地完全铺满其余 26 格；骨牌可横可竖。先按每块骨牌实际覆盖的格子区分铺法。
输出 horizontal_histogram：全部铺法中按横放骨牌数 h 分类的 [h,铺法数]，h 升序，只列非零项；
selected：恰好横放 10 块时的铺法数；rotation_fixed：其中旋转 180 度后完全不变的铺法数；
orbits：恰好横放 10 块时，把相差 180 度旋转的铺法视为同一种后的数量。只按该旋转去重，不按镜像去重。
只输出 JSON。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `horizontal_histogram` | 8 |
| `selected` | 3 |
| `rotation_fixed` | 5 |
| `orbits` | 4 |

设计意图：计数、对称不动点和轨道数分开验证，避免简单除以二。

### 参考答案

```json
{
  "horizontal_histogram": [
    [
      6,
      21
    ],
    [
      8,
      48
    ],
    [
      10,
      30
    ],
    [
      12,
      4
    ]
  ],
  "selected": 30,
  "rotation_fixed": 2,
  "orbits": 16
}
```

复核入口：`eval_bank_20260925/oracles.py`；具体部分计分及关联字段约束：`score.py::reasoning_groups`。

## P-E-01 · 简单 · 半开区间归并

### 题面

输入 {intervals:[[l,r],...]}，整数 -1000000<=l<=r<=1000000，最多 2000 个区间。
将半开区间 [l,r) 的并集转换为按左端点升序的最少区间列表。空区间丢弃；相接如 [1,3)、[3,5) 必须合并。
返回 {intervals:归并后的列表,length:并集总长度}。可修改输入，但多次调用之间不得残留状态。
公开例：[[1,3],[3,5],[2,4],[8,8]] -> {intervals:[[1,5]],length:4}。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `empty` | 4 |
| `touching` | 4 |
| `overlap` | 4 |
| `ordering` | 4 |
| `mixed` | 4 |

设计意图：空区间、端点和嵌套分别计分。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    result = []
    for left, right in sorted(data["intervals"]):
        if left == right:
            continue
        if result and left <= result[-1][1]:
            result[-1][1] = max(result[-1][1], right)
        else:
            result.append([left, right])
    return {"intervals": result, "length": sum(b - a for a, b in result)}
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| empty | 1 | 1 | `{"intervals":[]}` | `{"intervals":[],"length":0}` |
| empty | 2 | 1 | `{"intervals":[[1,1]]}` | `{"intervals":[],"length":0}` |
| empty | 3 | 1 | `{"intervals":[[0,0],[2,2]]}` | `{"intervals":[],"length":0}` |
| empty | 4 | 1 | `{"intervals":[[3,3],[-1,-1],[0,0]]}` | `{"intervals":[],"length":0}` |
| touching | 1 | 1 | `{"intervals":[[1,2],[2,3]]}` | `{"intervals":[[1,3]],"length":2}` |
| touching | 2 | 1 | `{"intervals":[[3,5],[0,3]]}` | `{"intervals":[[0,5]],"length":5}` |
| touching | 3 | 1 | `{"intervals":[[-3,0],[0,2],[2,4]]}` | `{"intervals":[[-3,4]],"length":7}` |
| touching | 4 | 1 | `{"intervals":[[1,2],[3,4]]}` | `{"intervals":[[1,2],[3,4]],"length":2}` |
| overlap | 1 | 1 | `{"intervals":[[1,5],[2,3]]}` | `{"intervals":[[1,5]],"length":4}` |
| overlap | 2 | 1 | `{"intervals":[[1,4],[3,7]]}` | `{"intervals":[[1,7]],"length":6}` |
| overlap | 3 | 1 | `{"intervals":[[0,10],[2,8],[3,5]]}` | `{"intervals":[[0,10]],"length":10}` |
| overlap | 4 | 1 | `{"intervals":[[1,2],[1,2],[1,2]]}` | `{"intervals":[[1,2]],"length":1}` |
| ordering | 1 | 1 | `{"intervals":[[8,9],[1,2],[4,5]]}` | `{"intervals":[[1,2],[4,5],[8,9]],"length":3}` |
| ordering | 2 | 1 | `{"intervals":[[3,4],[2,3],[1,2]]}` | `{"intervals":[[1,4]],"length":3}` |
| ordering | 3 | 1 | `{"intervals":[[-5,-2],[-4,-1]]}` | `{"intervals":[[-5,-1]],"length":4}` |
| ordering | 4 | 1 | `{"intervals":[[100,200],[-200,-100],[0,1]]}` | `{"intervals":[[-200,-100],[0,1],[100,200]],"length":201}` |
| mixed | 1 | 1 | `{"intervals":[[1,24],[12,23],[7,38],[19,27],[16,35],[5,22],[13,28],[-20,29],[-20,30],[-5,39],[18,27],[9,38],[-20,23],[-8,36],[-4,38],[6,30],[-8,27],[-6,33],[11,34],[-19,22],[-15,29],[9,…` | `{"intervals":[[-20,39]],"length":59}` |
| mixed | 2 | 1 | `{"intervals":[[18,36],[-13,38],[-10,21],[-13,31],[-1,26],[8,29],[12,22],[-2,22],[8,27],[10,27],[11,32],[0,34],[15,25],[13,26],[-2,31],[-17,24],[3,39],[7,21],[-13,27],[5,27],[-7,36],[-12…` | `{"intervals":[[-17,39]],"length":56}` |
| mixed | 3 | 1 | `{"intervals":[[-10,26],[-6,27],[6,39],[-19,27],[-5,25],[-15,35],[-15,23],[1,21],[18,33],[3,31],[-3,24],[9,35],[-9,23],[-14,30],[5,22],[17,23],[6,32],[2,37],[-15,38],[7,35],[-20,28],[-2,…` | `{"intervals":[[-20,39]],"length":59}` |
| mixed | 4 | 1 | `{"intervals":[[-12,23],[11,39],[5,22],[-8,33],[11,38],[-16,35],[-15,30],[-12,32],[10,23],[0,32],[13,33],[-18,35],[-2,27],[-18,28],[0,21],[0,37],[-10,24],[11,30],[10,37],[-14,30],[-16,39…` | `{"intervals":[[-18,39]],"length":57}` |

## P-E-02 · 简单 · 逐字符转义分隔

### 题面

输入 {text:字符串}，长度<=10000，仅含 ASCII 可打印字符。
从左到右解析：未转义的 | 分隔字段，保留空字段；反斜杠转义紧跟的任意一个字符，该字符按字面加入当前字段，反斜杠本身不保留。
末尾没有后继字符的反斜杠按字面保留。返回字段字符串数组。不递归处理已经转义出的字符。
公开例：空串 -> [""]；"a||b|" -> ["a","","b",""]；字符序列 a、反斜杠、|、b -> ["a|b"]。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `empty_fields` | 4 |
| `escaped_separator` | 4 |
| `escaped_escape` | 4 |
| `trailing` | 4 |
| `mixed` | 4 |

设计意图：用状态转换区分一次转义、成对反斜杠和末尾残留。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    fields, current = [], []
    text = data["text"]
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            current.append(text[i + 1])
            i += 2
        elif text[i] == "|":
            fields.append("".join(current))
            current = []
            i += 1
        else:
            current.append(text[i])
            i += 1
    return fields + ["".join(current)]
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| empty_fields | 1 | 1 | `{"text":""}` | `[""]` |
| empty_fields | 2 | 1 | `{"text":"&#124;"}` | `["",""]` |
| empty_fields | 3 | 1 | `{"text":"&#124;&#124;"}` | `["","",""]` |
| empty_fields | 4 | 1 | `{"text":"a&#124;&#124;b&#124;"}` | `["a","","b",""]` |
| escaped_separator | 1 | 1 | `{"text":"a\\&#124;b"}` | `["a&#124;b"]` |
| escaped_separator | 2 | 1 | `{"text":"\\&#124;"}` | `["&#124;"]` |
| escaped_separator | 3 | 1 | `{"text":"a\\&#124;b&#124;c"}` | `["a&#124;b","c"]` |
| escaped_separator | 4 | 1 | `{"text":"\\&#124;&#124;\\&#124;"}` | `["&#124;","&#124;"]` |
| escaped_escape | 1 | 1 | `{"text":"\\\\"}` | `["\\"]` |
| escaped_escape | 2 | 1 | `{"text":"\\\\&#124;x"}` | `["\\","x"]` |
| escaped_escape | 3 | 1 | `{"text":"\\\\\\&#124;"}` | `["\\&#124;"]` |
| escaped_escape | 4 | 1 | `{"text":"a\\\\b&#124;c"}` | `["a\\b","c"]` |
| trailing | 1 | 1 | `{"text":"\\"}` | `["\\"]` |
| trailing | 2 | 1 | `{"text":"a\\"}` | `["a\\"]` |
| trailing | 3 | 1 | `{"text":"a&#124;\\"}` | `["a","\\"]` |
| trailing | 4 | 1 | `{"text":"\\\\\\"}` | `["\\\\"]` |
| mixed | 1 | 1 | `{"text":"&#124;b a\\ ?? b \\\\a &#124;a&#124;a&#124;b  ??b\\ aab &#124; \\&#124;bbb?\\\\\\aaa&#124;\\b&#124;b?\\\\&#124;b\\?\\ &#124;\\  aa   a baa?&#124;&#124;b?\\?&#124; a&#124;a\\b\\b?\\\\?&#124;\\ b? b&#124;?&#124;ab&#124; ??\\a?ab\\??bb b\\   a\\?ba&#124;&#124;aa\\b? &#124;a?bb?b?b\\ …` | `["","b a ?? b \\a ","a","a","b  ??b aab "," &#124;bbb?\\aaa","b","b?\\","b? ","  aa   a baa?","","b??"," a","abb?\\?"," b? b","?","ab"," ??a?ab??bb b   a?ba","","aab? ","a?bb?b?b abbba?aa","…` |
| mixed | 2 | 1 | `{"text":"&#124;\\?\\&#124;\\a  bb?a\\ \\ab\\?\\? a\\?a?&#124;b?\\?\\a&#124;\\ \\a\\&#124;ba&#124;&#124;?a&#124; bb\\&#124;\\ ?a&#124;a \\ b  ?bb?&#124; ab\\ \\a&#124;&#124;&#124;?a b&#124;\\&#124;a ba&#124;baaa\\?&#124; &#124;aba\\\\ \\ bbaa &#124;b\\aa&#124; ?&#124;aba&#124;a?\\aa ?b &#124;ab\\a\\ \\aa&#124;…` | `["","?&#124;a  bb?a ab?? a?a?","b??a"," a&#124;ba","","?a"," bb&#124; ?a","a  b  ?bb?"," ab a","","","?a b","&#124;a ba","baaa?"," ","aba\\  bbaa ","baa"," ?","aba","a?aa ?b ","aba aa","aa? aa?a b\\ ? ",""…` |
| mixed | 3 | 1 | `{"text":"?b&#124; a&#124;aa\\\\bb&#124;a&#124;? ab&#124;?  \\&#124;ba\\ba&#124; ?bb&#124;\\ aa?? &#124;baa&#124;?\\b&#124;b?\\\\&#124;? &#124; bb?b\\b&#124; ?  &#124;aa b ba&#124;\\aab\\\\&#124;b\\abb &#124;a&#124;aa\\b&#124;ba&#124;?&#124;a?a ?&#124;\\\\ab\\bbb&#124;bb?ba? ?\\ \\a&#124;aba &#124;b&#124;&#124;&#124;\\\\\\aaa? ?&#124;…` | `["?b"," a","aa\\bb","a","? ab","?  &#124;baba"," ?bb"," aa?? ","baa","?b","b?\\","? "," bb?bb"," ?  ","aa b ba","aab\\","babb ","a","aab","ba","?","a?a ?","\\abbbb","bb?ba? ? a","aba ","b","…` |
| mixed | 4 | 1 | `{"text":"bba&#124;b &#124;\\&#124;aaa?&#124;\\ \\ \\&#124; a&#124; \\b b a\\&#124;?&#124;a&#124; ? \\\\ \\ b&#124;\\ \\b\\ b??\\?\\\\bbba aba?\\?b\\&#124;\\?\\b \\ &#124;a&#124;?ba\\ bbb?a?? ?ab&#124;?? &#124;a?\\&#124;?ba&#124; &#124;\\baa\\a&#124;\\a b a? ?b ab\\a \\?&#124; babb&#124;ab&#124;…` | `["bba","b ","&#124;aaa?","  &#124; a"," b b a&#124;?","a"," ? \\  b"," b b???\\bbba aba??b&#124;?b  ","a","?ba bbb?a?? ?ab","?? ","a?&#124;?ba"," ","baaa","a b a? ?b aba ?"," babb","ab"," ?"," ","?","?"," \\a",…` |

## P-N-01 · 普通 · 去重与原子库存批次

### 题面

输入 {initial:{sku:非负整数,...},events:[{id:字符串,delta:[[sku,整数增量],...]},...]}。
sku 和 id 为非空 ASCII 字母数字串，最多 100 个 sku、2000 个事件，每事件最多 20 条 delta，所有库存和增量绝对值不超过 1000000。
初始缺失 sku 视为 0。按序处理，id 首次出现立即占用，即使该事件失败；重复 id 返回 DUP，不做其他检查。
同一事件先按 sku 合并全部增量，再检查所有最终库存是否非负；有负数则整个事件不生效，返回 NEGATIVE；否则原子更新，返回 OK。
返回 {stock:[[sku,最终库存],...],trace:[状态,...]}。stock 只列非零库存并按 sku 字典序排序；空增量事件也占号并返回 OK。
公开例：initial={a:2}，事件 x 的 delta=[[a,-3],[a,1]]，再一次 x 的 delta=[[a,5]] -> stock=[]，trace=[OK,DUP]。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `basic` | 4 |
| `atomic` | 4 |
| `duplicate` | 4 |
| `coalesce` | 4 |
| `interactions` | 4 |

设计意图：失败占号、重复项合并和批次回滚形成交互边界。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    stock = dict(data["initial"])
    seen, trace = set(), []
    for event in data["events"]:
        eid = event["id"]
        if eid in seen:
            trace.append("DUP")
            continue
        seen.add(eid)
        delta = {}
        for key, value in event["delta"]:
            delta[key] = delta.get(key, 0) + value
        if any(stock.get(key, 0) + value < 0 for key, value in delta.items()):
            trace.append("NEGATIVE")
            continue
        for key, value in delta.items():
            stock[key] = stock.get(key, 0) + value
        trace.append("OK")
    return {
        "stock": [[k, stock[k]] for k in sorted(stock) if stock[k] != 0],
        "trace": trace,
    }
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| basic | 1 | 1 | `{"initial":{},"events":[]}` | `{"stock":[],"trace":[]}` |
| basic | 2 | 1 | `{"initial":{"a":2},"events":[{"id":"x","delta":[["a",3]]}]}` | `{"stock":[["a",5]],"trace":["OK"]}` |
| basic | 3 | 1 | `{"initial":{},"events":[{"id":"x","delta":[["constructor",2],["toString",1]]}]}` | `{"stock":[["constructor",2],["toString",1]],"trace":["OK"]}` |
| basic | 4 | 1 | `{"initial":{"a":0},"events":[{"id":"x","delta":[]}]}` | `{"stock":[],"trace":["OK"]}` |
| atomic | 1 | 1 | `{"initial":{"a":1,"b":2},"events":[{"id":"x","delta":[["a",2],["b",-3]]}]}` | `{"stock":[["a",1],["b",2]],"trace":["NEGATIVE"]}` |
| atomic | 2 | 1 | `{"initial":{},"events":[{"id":"x","delta":[["a",-1]]}]}` | `{"stock":[],"trace":["NEGATIVE"]}` |
| atomic | 3 | 1 | `{"initial":{"a":1},"events":[{"id":"x","delta":[["a",-1]]}]}` | `{"stock":[],"trace":["OK"]}` |
| atomic | 4 | 1 | `{"initial":{"a":1},"events":[{"id":"x","delta":[["a",-2]]},{"id":"y","delta":[["a",-1]]}]}` | `{"stock":[],"trace":["NEGATIVE","OK"]}` |
| duplicate | 1 | 1 | `{"initial":{},"events":[{"id":"x","delta":[["a",-1]]},{"id":"x","delta":[["a",5]]}]}` | `{"stock":[],"trace":["NEGATIVE","DUP"]}` |
| duplicate | 2 | 1 | `{"initial":{},"events":[{"id":"x","delta":[]},{"id":"x","delta":[["a",2]]}]}` | `{"stock":[],"trace":["OK","DUP"]}` |
| duplicate | 3 | 1 | `{"initial":{},"events":[{"id":"x","delta":[["a",2]]},{"id":"x","delta":[["a",2]]}]}` | `{"stock":[["a",2]],"trace":["OK","DUP"]}` |
| duplicate | 4 | 1 | `{"initial":{"a":3},"events":[{"id":"x","delta":[["a",-5]]},{"id":"y","delta":[["a",4]]},{"id":"x","delta":[["a",-1]]}]}` | `{"stock":[["a",7]],"trace":["NEGATIVE","OK","DUP"]}` |
| coalesce | 1 | 1 | `{"initial":{"a":2},"events":[{"id":"x","delta":[["a",-3],["a",1]]}]}` | `{"stock":[],"trace":["OK"]}` |
| coalesce | 2 | 1 | `{"initial":{},"events":[{"id":"x","delta":[["a",-2],["a",2]]}]}` | `{"stock":[],"trace":["OK"]}` |
| coalesce | 3 | 1 | `{"initial":{"a":2},"events":[{"id":"x","delta":[["a",2],["a",-5]]}]}` | `{"stock":[["a",2]],"trace":["NEGATIVE"]}` |
| coalesce | 4 | 1 | `{"initial":{"a":1,"b":1},"events":[{"id":"x","delta":[["a",-2],["b",2],["a",1]]}]}` | `{"stock":[["b",3]],"trace":["OK"]}` |
| interactions | 1 | 1 | `{"initial":{"a":3,"b":2},"events":[{"id":"5","delta":[["a",3],["c",-3],["b",1],["c",3]]},{"id":"9","delta":[["a",1],["b",0],["a",1],["b",-3]]},{"id":"4","delta":[["a",-1],["a",1],["c",2…` | `{"stock":[["a",12],["b",5],["c",3]],"trace":["OK","OK","OK","OK","DUP","DUP","OK","OK","NEGATIVE","OK","OK","DUP","OK","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP",…` |
| interactions | 2 | 1 | `{"initial":{"a":3,"b":2},"events":[{"id":"1","delta":[["b",1],["b",-3],["a",3],["b",3]]},{"id":"0","delta":[["a",2],["c",-3],["a",2],["a",0]]},{"id":"8","delta":[["a",0],["b",1],["c",1]…` | `{"stock":[["b",6],["c",1]],"trace":["OK","NEGATIVE","OK","OK","OK","DUP","DUP","OK","NEGATIVE","DUP","DUP","NEGATIVE","OK","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","DUP","D…` |
| interactions | 3 | 1 | `{"initial":{"a":3,"b":2},"events":[{"id":"9","delta":[["a",-2],["a",3],["c",-3],["c",2]]},{"id":"8","delta":[["c",-3],["a",-1],["c",2],["c",3]]},{"id":"4","delta":[["a",2],["b",-1],["c"…` | `{"stock":[["a",3],["b",3],["c",13]],"trace":["NEGATIVE","OK","OK","DUP","OK","NEGATIVE","DUP","DUP","OK","DUP","OK","DUP","DUP","OK","DUP","DUP","DUP","OK","DUP","DUP","DUP","DUP","OK",…` |
| interactions | 4 | 1 | `{"initial":{"a":3,"b":2},"events":[{"id":"5","delta":[["c",-3],["a",-3],["c",-2],["c",-2]]},{"id":"4","delta":[["c",-2],["c",0],["c",2],["b",-2]]},{"id":"7","delta":[["b",3],["c",2],["b…` | `{"stock":[["a",1],["b",5],["c",4]],"trace":["NEGATIVE","OK","OK","NEGATIVE","OK","OK","DUP","DUP","DUP","DUP","DUP","OK","DUP","DUP","DUP","DUP","DUP","OK","DUP","OK","DUP","DUP","DUP",…` |

## P-N-02 · 普通 · 拓扑顺序与真正的环成员

### 题面

输入 {nodes:[唯一节点名,...],edges:[[u,v],...]}；边表示 u 必须先于 v，端点保证存在。
0..60 个节点，0..2000 条边。名字为 ASCII 字母数字串，按字符串字典序比较。重复边只算一次；允许自环。
若无环，返回 {order:字典序最小的完整拓扑序,cycle_nodes:[]}。
若有环，返回 {order:null,cycle_nodes:真正处在至少一个有向环中的节点名升序列表}；仅仅被环阻塞的下游节点不能列入。
公开例：nodes=[a,b,c]，edges=[[a,b],[b,a],[b,c]] -> {order:null,cycle_nodes:[a,b]}。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `dag` | 4 |
| `ties` | 4 |
| `cycles` | 4 |
| `downstream` | 4 |
| `mixed` | 4 |

设计意图：区分 Kahn 算法的剩余节点与环成员。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    import heapq

    nodes = sorted(data["nodes"])
    graph = {v: set() for v in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for u, v in data["edges"]:
        if v not in graph[u]:
            graph[u].add(v)
            indegree[v] += 1
    ready = [v for v in nodes if indegree[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in graph[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(ready, v)
    if len(order) == len(nodes):
        return {"order": order, "cycle_nodes": []}
    # 上限 60 个节点，逐源可达性足够；避免将环的下游误报成环成员。
    cycle = []
    for start in nodes:
        todo, seen = list(graph[start]), set()
        while todo:
            u = todo.pop()
            if u in seen:
                continue
            seen.add(u)
            todo.extend(graph[u] - seen)
        if start in seen:
            cycle.append(start)
    return {"order": None, "cycle_nodes": cycle}
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| dag | 1 | 1 | `{"nodes":[],"edges":[]}` | `{"order":[],"cycle_nodes":[]}` |
| dag | 2 | 1 | `{"nodes":["a"],"edges":[]}` | `{"order":["a"],"cycle_nodes":[]}` |
| dag | 3 | 1 | `{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]}` | `{"order":["a","b","c"],"cycle_nodes":[]}` |
| dag | 4 | 1 | `{"nodes":["a","b","c","d"],"edges":[["a","b"],["a","c"],["b","d"],["c","d"]]}` | `{"order":["a","b","c","d"],"cycle_nodes":[]}` |
| ties | 1 | 1 | `{"nodes":["c","b","a"],"edges":[]}` | `{"order":["a","b","c"],"cycle_nodes":[]}` |
| ties | 2 | 1 | `{"nodes":["a","b","c","d"],"edges":[["a","c"],["b","d"]]}` | `{"order":["a","b","c","d"],"cycle_nodes":[]}` |
| ties | 3 | 1 | `{"nodes":["a","b","c"],"edges":[["a","c"],["a","c"]]}` | `{"order":["a","b","c"],"cycle_nodes":[]}` |
| ties | 4 | 1 | `{"nodes":["a","b","c","d","e","f"],"edges":[["c","f"],["b","e"],["a","d"]]}` | `{"order":["a","b","c","d","e","f"],"cycle_nodes":[]}` |
| cycles | 1 | 1 | `{"nodes":["a"],"edges":[["a","a"]]}` | `{"order":null,"cycle_nodes":["a"]}` |
| cycles | 2 | 1 | `{"nodes":["a","b"],"edges":[["a","b"],["b","a"]]}` | `{"order":null,"cycle_nodes":["a","b"]}` |
| cycles | 3 | 1 | `{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"],["c","a"]]}` | `{"order":null,"cycle_nodes":["a","b","c"]}` |
| cycles | 4 | 1 | `{"nodes":["a","b","c","d"],"edges":[["a","b"],["b","a"],["c","d"],["d","c"]]}` | `{"order":null,"cycle_nodes":["a","b","c","d"]}` |
| downstream | 1 | 1 | `{"nodes":["a","b","c"],"edges":[["a","b"],["b","a"],["b","c"]]}` | `{"order":null,"cycle_nodes":["a","b"]}` |
| downstream | 2 | 1 | `{"nodes":["a","b","c","d"],"edges":[["a","a"],["a","b"],["b","c"],["c","d"]]}` | `{"order":null,"cycle_nodes":["a"]}` |
| downstream | 3 | 1 | `{"nodes":["a","b","c","d"],"edges":[["a","b"],["b","c"],["c","b"],["c","d"]]}` | `{"order":null,"cycle_nodes":["b","c"]}` |
| downstream | 4 | 1 | `{"nodes":["a","b","c","d","e"],"edges":[["a","b"],["b","a"],["b","c"],["c","d"],["d","e"]]}` | `{"order":null,"cycle_nodes":["a","b"]}` |
| mixed | 1 | 1 | `{"nodes":["a","b","c","d","e","f"],"edges":[["a","b"],["b","f"],["d","a"],["f","a"]]}` | `{"order":null,"cycle_nodes":["a","b","f"]}` |
| mixed | 2 | 1 | `{"nodes":["a","b","c","d","e","f"],"edges":[["b","d"],["b","e"],["c","d"],["c","e"]]}` | `{"order":["a","b","c","d","e","f"],"cycle_nodes":[]}` |
| mixed | 3 | 1 | `{"nodes":["a","b","c","d","e","f"],"edges":[["a","b"],["c","e"],["d","a"],["f","a"],["f","c"],["f","e"]]}` | `{"order":["d","f","a","b","c","e"],"cycle_nodes":[]}` |
| mixed | 4 | 1 | `{"nodes":["a","b","c","d","e","f"],"edges":[["a","c"],["a","e"],["a","f"],["b","d"],["c","c"],["d","b"],["f","f"]]}` | `{"order":null,"cycle_nodes":["b","c","d","f"]}` |

## P-H-01 · 困难 · 带两层平局规则的区间调度

### 题面

输入 {jobs:[{id,start,end,value},...]}，id 唯一，为 ASCII 字母数字串；0<=start<end<=1000000；value 为 -1000..1000 的整数，最多 2000 项。
选择互不重叠的半开区间任务，端点相接可共存，空集合可行。先最大化总 value；平局取任务数少者；仍平局，比较按执行时间排列的 id 数组，取字典序最小。
返回 {value:总价值,ids:执行顺序的 id 数组}。
公开例：[{id:a,start:0,end:2,value:4},{id:b,start:2,end:4,value:4},{id:c,start:0,end:4,value:8}] -> {value:8,ids:[c]}。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `basic` | 4 |
| `boundary` | 4 |
| `count_tie` | 4 |
| `lex_tie` | 4 |
| `scale` | 4 |

设计意图：不仅测试能否找到最优值，还测试稳定重建、负价值和两层平局。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    from bisect import bisect_right

    jobs = sorted(data["jobs"], key=lambda x: (x["end"], x["start"], x["id"]))
    ends = [j["end"] for j in jobs]
    best = [(0, [])]
    for i, job in enumerate(jobs):
        index = bisect_right(ends, job["start"], 0, i)
        value, ids = best[index]
        take = (value + job["value"], ids + [job["id"]])
        skip = best[-1]
        best.append(min((take, skip), key=lambda x: (-x[0], len(x[1]), x[1])))
    return {"value": best[-1][0], "ids": best[-1][1]}
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| basic | 1 | 1 | `{"jobs":[]}` | `{"value":0,"ids":[]}` |
| basic | 2 | 1 | `{"jobs":[{"id":"a","start":0,"end":1,"value":3}]}` | `{"value":3,"ids":["a"]}` |
| basic | 3 | 1 | `{"jobs":[{"id":"a","start":0,"end":1,"value":-1}]}` | `{"value":0,"ids":[]}` |
| basic | 4 | 1 | `{"jobs":[{"id":"a","start":0,"end":1,"value":0}]}` | `{"value":0,"ids":[]}` |
| boundary | 1 | 1 | `{"jobs":[{"id":"a","start":0,"end":2,"value":2},{"id":"b","start":2,"end":4,"value":3}]}` | `{"value":5,"ids":["a","b"]}` |
| boundary | 2 | 1 | `{"jobs":[{"id":"a","start":0,"end":3,"value":3},{"id":"b","start":2,"end":4,"value":5}]}` | `{"value":5,"ids":["b"]}` |
| boundary | 3 | 1 | `{"jobs":[{"id":"a","start":0,"end":6,"value":5},{"id":"b","start":1,"end":2,"value":4},{"id":"c","start":3,"end":5,"value":4}]}` | `{"value":8,"ids":["b","c"]}` |
| boundary | 4 | 1 | `{"jobs":[{"id":"a","start":0,"end":2,"value":-1},{"id":"b","start":2,"end":3,"value":4}]}` | `{"value":4,"ids":["b"]}` |
| count_tie | 1 | 1 | `{"jobs":[{"id":"a","start":0,"end":2,"value":4},{"id":"b","start":2,"end":4,"value":4},{"id":"c","start":0,"end":4,"value":8}]}` | `{"value":8,"ids":["c"]}` |
| count_tie | 2 | 1 | `{"jobs":[{"id":"a","start":0,"end":1,"value":0},{"id":"b","start":1,"end":2,"value":2}]}` | `{"value":2,"ids":["b"]}` |
| count_tie | 3 | 1 | `{"jobs":[{"id":"a","start":0,"end":2,"value":4},{"id":"b","start":0,"end":1,"value":2},{"id":"c","start":1,"end":2,"value":2}]}` | `{"value":4,"ids":["a"]}` |
| count_tie | 4 | 1 | `{"jobs":[{"id":"a","start":0,"end":1,"value":1},{"id":"b","start":1,"end":2,"value":1},{"id":"z","start":0,"end":2,"value":2},{"id":"c","start":2,"end":3,"value":1}]}` | `{"value":3,"ids":["z","c"]}` |
| lex_tie | 1 | 1 | `{"jobs":[{"id":"b","start":0,"end":2,"value":3},{"id":"a","start":0,"end":2,"value":3}]}` | `{"value":3,"ids":["a"]}` |
| lex_tie | 2 | 1 | `{"jobs":[{"id":"z","start":0,"end":1,"value":2},{"id":"a","start":1,"end":2,"value":2},{"id":"b","start":0,"end":1,"value":2},{"id":"c","start":1,"end":2,"value":2}]}` | `{"value":4,"ids":["b","a"]}` |
| lex_tie | 3 | 1 | `{"jobs":[{"id":"a","start":2,"end":4,"value":2},{"id":"b","start":0,"end":2,"value":2},{"id":"c","start":0,"end":4,"value":3}]}` | `{"value":4,"ids":["b","a"]}` |
| lex_tie | 4 | 1 | `{"jobs":[{"id":"a","start":0,"end":3,"value":3},{"id":"aa","start":0,"end":3,"value":3},{"id":"b","start":3,"end":4,"value":1}]}` | `{"value":4,"ids":["a","b"]}` |
| scale | 1 | 21 | `{"jobs":[{"id":"j00","start":5,"end":7,"value":9},{"id":"j01","start":8,"end":9,"value":3},{"id":"j02","start":9,"end":14,"value":0},{"id":"j03","start":9,"end":13,"value":3},{"id":"j04…` | `{"value":16,"ids":["j00","j01","j07"]}` |
| scale | 2 | 21 | `{"jobs":[{"id":"j00","start":0,"end":3,"value":3},{"id":"j01","start":8,"end":12,"value":6},{"id":"j02","start":7,"end":10,"value":6},{"id":"j03","start":0,"end":3,"value":6},{"id":"j04…` | `{"value":21,"ids":["j03","j04","j01"]}` |
| scale | 3 | 21 | `{"jobs":[{"id":"j00","start":9,"end":14,"value":9},{"id":"j01","start":4,"end":5,"value":-1},{"id":"j02","start":10,"end":14,"value":7},{"id":"j03","start":8,"end":11,"value":4},{"id":"…` | `{"value":15,"ids":["j09","j07","j00"]}` |
| scale | 4 | 21 | `{"jobs":[{"id":"j00","start":2,"end":6,"value":3},{"id":"j01","start":0,"end":3,"value":-3},{"id":"j02","start":6,"end":8,"value":-1},{"id":"j03","start":2,"end":7,"value":3},{"id":"j04…` | `{"value":4,"ids":["j00","j06"]}` |

## P-H-02 · 困难 · 快照事务与写写冲突

### 题面

输入 {initial:{key:整数,...},events:[事件,...]}。最多 200 个 key、2000 条事件，值为绝对值<=1000000 的整数。
事件为 [BEGIN,tx]、[GET,tx,key]、[SET,tx,key,value]、[COMMIT,tx]。名字是非空 ASCII 字母数字串；tx 的 BEGIN 只出现一次，后续事件只引用活跃事务；结束时可以仍有活跃事务。
全局版本从 0 开始。BEGIN 记录当前已提交内容和版本；GET 先读自己的写集，否则读 BEGIN 快照，缺失返回 null；不能读其他事务未提交内容。
COMMIT：若自己的任一写入 key 最近提交版本 > 本事务快照版本，整个事务失败并结束；否则原子提交，全局版本加 1，包括空写集提交。失败提交不增加版本。同值写入也算写；读集不参与冲突判断。
返回 {reads:[[tx,key,value_or_null],...],commits:[[tx,成功布尔,成功后的版本或null],...],final:[[key,value],...]}，前两项按发生顺序，final 按 key 升序且只含已提交内容。
公开例：initial={x:1}；[BEGIN,a],[BEGIN,b],[SET,a,x,2],[COMMIT,a],[GET,b,x],[SET,b,x,3],[COMMIT,b] -> reads=[[b,x,1]],commits=[[a,true,1],[b,false,null]],final=[[x,2]]。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `snapshot` | 4 |
| `own_writes` | 4 |
| `conflict` | 4 |
| `version` | 4 |
| `isolation` | 4 |

设计意图：将快照读、读己之写、同值提交和全事务冲突分开，避免把串行化规则混入。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    current = dict(data["initial"])
    last_write = dict.fromkeys(current, 0)
    version = 0
    active, reads, commits = {}, [], []
    for event in data["events"]:
        op, tx = event[:2]
        if op == "BEGIN":
            active[tx] = (version, dict(current), {})
        elif op == "GET":
            _, snapshot, writes = active[tx]
            key = event[2]
            reads.append([tx, key, writes.get(key, snapshot.get(key))])
        elif op == "SET":
            active[tx][2][event[2]] = event[3]
        else:
            snap_version, _, writes = active.pop(tx)
            conflict = any(last_write.get(k, 0) > snap_version for k in writes)
            if conflict:
                commits.append([tx, False, None])
            else:
                version += 1
                current.update(writes)
                for key in writes:
                    last_write[key] = version
                commits.append([tx, True, version])
    return {
        "reads": reads,
        "commits": commits,
        "final": [[k, current[k]] for k in sorted(current)],
    }
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| snapshot | 1 | 1 | `{"initial":{},"events":[["BEGIN","a"],["GET","a","x"]]}` | `{"reads":[["a","x",null]],"commits":[],"final":[]}` |
| snapshot | 2 | 1 | `{"initial":{"x":1},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",2],["COMMIT","a"],["GET","b","x"]]}` | `{"reads":[["b","x",1]],"commits":[["a",true,1]],"final":[["x",2]]}` |
| snapshot | 3 | 1 | `{"initial":{"x":1},"events":[["BEGIN","a"],["SET","a","x",2],["BEGIN","b"],["GET","b","x"]]}` | `{"reads":[["b","x",1]],"commits":[],"final":[["x",1]]}` |
| snapshot | 4 | 1 | `{"initial":{"x":0},"events":[["BEGIN","a"],["COMMIT","a"],["BEGIN","b"],["GET","b","x"]]}` | `{"reads":[["b","x",0]],"commits":[["a",true,1]],"final":[["x",0]]}` |
| own_writes | 1 | 1 | `{"initial":{},"events":[["BEGIN","a"],["SET","a","x",2],["GET","a","x"]]}` | `{"reads":[["a","x",2]],"commits":[],"final":[]}` |
| own_writes | 2 | 1 | `{"initial":{},"events":[["BEGIN","a"],["SET","a","x",2],["SET","a","x",3],["GET","a","x"],["COMMIT","a"]]}` | `{"reads":[["a","x",3]],"commits":[["a",true,1]],"final":[["x",3]]}` |
| own_writes | 3 | 1 | `{"initial":{},"events":[["BEGIN","a"],["SET","a","x",0],["GET","a","x"],["COMMIT","a"]]}` | `{"reads":[["a","x",0]],"commits":[["a",true,1]],"final":[["x",0]]}` |
| own_writes | 4 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",2],["SET","b","x",3],["GET","a","x"],["GET","b","x"]]}` | `{"reads":[["a","x",2],["b","x",3]],"commits":[],"final":[]}` |
| conflict | 1 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["COMMIT","a"],["SET","b","x",2],["COMMIT","b"]]}` | `{"reads":[],"commits":[["a",true,1],["b",false,null]],"final":[["x",1]]}` |
| conflict | 2 | 1 | `{"initial":{"x":1},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["COMMIT","a"],["SET","b","x",1],["COMMIT","b"]]}` | `{"reads":[],"commits":[["a",true,1],["b",false,null]],"final":[["x",1]]}` |
| conflict | 3 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["COMMIT","a"],["SET","b","y",2],["SET","b","x",3],["COMMIT","b"]]}` | `{"reads":[],"commits":[["a",true,1],["b",false,null]],"final":[["x",1]]}` |
| conflict | 4 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["SET","b","y",2],["COMMIT","a"],["COMMIT","b"]]}` | `{"reads":[],"commits":[["a",true,1],["b",true,2]],"final":[["x",1],["y",2]]}` |
| version | 1 | 1 | `{"initial":{},"events":[["BEGIN","a"],["COMMIT","a"]]}` | `{"reads":[],"commits":[["a",true,1]],"final":[]}` |
| version | 2 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["COMMIT","b"],["COMMIT","a"]]}` | `{"reads":[],"commits":[["b",true,1],["a",true,2]],"final":[]}` |
| version | 3 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["COMMIT","a"],["SET","b","x",2],["COMMIT","b"],["BEGIN","c"],["COMMIT","c"]]}` | `{"reads":[],"commits":[["a",true,1],["b",false,null],["c",true,2]],"final":[["x",1]]}` |
| version | 4 | 1 | `{"initial":{},"events":[["BEGIN","a"],["SET","a","x",1],["COMMIT","a"],["BEGIN","b"],["SET","b","x",2],["COMMIT","b"]]}` | `{"reads":[],"commits":[["a",true,1],["b",true,2]],"final":[["x",2]]}` |
| isolation | 1 | 1 | `{"initial":{"x":1,"y":1},"events":[["BEGIN","a"],["BEGIN","b"],["GET","a","y"],["GET","b","x"],["SET","a","x",0],["SET","b","y",0],["COMMIT","a"],["COMMIT","b"]]}` | `{"reads":[["a","y",1],["b","x",1]],"commits":[["a",true,1],["b",true,2]],"final":[["x",0],["y",0]]}` |
| isolation | 2 | 1 | `{"initial":{"x":1},"events":[["BEGIN","a"],["SET","a","x",9]]}` | `{"reads":[],"commits":[],"final":[["x",1]]}` |
| isolation | 3 | 1 | `{"initial":{"x":1},"events":[["BEGIN","a"],["BEGIN","b"],["GET","b","x"],["SET","a","x",3],["COMMIT","a"],["COMMIT","b"]]}` | `{"reads":[["b","x",1]],"commits":[["a",true,1],["b",true,2]],"final":[["x",3]]}` |
| isolation | 4 | 1 | `{"initial":{},"events":[["BEGIN","a"],["BEGIN","b"],["SET","a","x",1],["COMMIT","a"],["GET","b","x"],["BEGIN","c"],["GET","c","x"]]}` | `{"reads":[["b","x",null],["c","x",1]],"commits":[["a",true,1]],"final":[["x",1]]}` |

## P-X-01 · 超难 · 带边计数的动态连通性

### 题面

输入 {n:顶点数,events:[[op,u,v],...]}，顶点 0..n-1，1<=n<=20000，最多 40000 条事件。
无向图初始无边；op 为 ADD、REMOVE、ASK。ADD 给无向边的引用计数加 1；REMOVE 只减去一个引用，已经为零则无操作。计数大于零时边存在；(u,v) 与 (v,u) 是同一条边；允许自环。
ASK 查询该时刻 u 和 v 是否连通；顶点与自己永远连通。只返回所有 ASK 的布尔数组，按出现顺序。
公开例：n=2；ADD 0 1、ADD 1 0、REMOVE 0 1、ASK 0 1、REMOVE 1 0、ASK 0 1 -> [true,false]。
大规模测试包含长链上的反复断开与恢复。需要避免每次查询都遍历整张图；按给定离线事件列表设计。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `basic` | 4 |
| `multiplicity` | 4 |
| `deletions` | 4 |
| `rollback` | 4 |
| `scale` | 4 |

设计意图：离线时间区间、引用计数及可回滚连通结构相互作用；规模组识别逐次全图搜索。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    n, events = data["n"], data["events"]
    count, start, intervals = {}, {}, []
    for t, (op, u, v) in enumerate(events):
        edge = tuple(sorted((u, v)))
        if op == "ADD":
            if count.get(edge, 0) == 0:
                start[edge] = t
            count[edge] = count.get(edge, 0) + 1
        elif op == "REMOVE" and count.get(edge, 0):
            count[edge] -= 1
            if count[edge] == 0:
                intervals.append((start.pop(edge), t, edge))
    total = len(events)
    for edge, begin in start.items():
        intervals.append((begin, total, edge))
    if not total:
        return []
    tree = [[] for _ in range(4 * total)]

    def put(node, left, right, begin, end, edge):
        if begin >= right or end <= left:
            return
        if begin <= left and right <= end:
            tree[node].append(edge)
            return
        mid = (left + right) // 2
        put(node * 2, left, mid, begin, end, edge)
        put(node * 2 + 1, mid, right, begin, end, edge)

    for begin, end, edge in intervals:
        put(1, 0, total, begin, end, edge)
    parent, size, history, answer = list(range(n)), [1] * n, [], []

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def visit(node, left, right):
        checkpoint = len(history)
        for u, v in tree[node]:
            a, b = find(u), find(v)
            if a == b:
                continue
            if size[a] < size[b]:
                a, b = b, a
            history.append((b, a, size[a]))
            parent[b] = a
            size[a] += size[b]
        if right - left == 1:
            op, u, v = events[left]
            if op == "ASK":
                answer.append(find(u) == find(v))
        else:
            mid = (left + right) // 2
            visit(node * 2, left, mid)
            visit(node * 2 + 1, mid, right)
        while len(history) > checkpoint:
            b, a, old_size = history.pop()
            parent[b], size[a] = b, old_size

    visit(1, 0, total)
    return answer
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| basic | 1 | 1 | `{"n":5,"events":[]}` | `[]` |
| basic | 2 | 1 | `{"n":5,"events":[["ASK",0,0]]}` | `[true]` |
| basic | 3 | 1 | `{"n":5,"events":[["ASK",0,1]]}` | `[false]` |
| basic | 4 | 1 | `{"n":5,"events":[["ADD",0,1],["ADD",1,2],["ASK",0,2]]}` | `[true]` |
| multiplicity | 1 | 1 | `{"n":5,"events":[["ADD",0,1],["ADD",1,0],["REMOVE",0,1],["ASK",0,1]]}` | `[true]` |
| multiplicity | 2 | 1 | `{"n":5,"events":[["ADD",0,1],["REMOVE",1,0],["ASK",0,1]]}` | `[false]` |
| multiplicity | 3 | 1 | `{"n":5,"events":[["ADD",0,0],["REMOVE",0,0],["ASK",0,0]]}` | `[true]` |
| multiplicity | 4 | 1 | `{"n":5,"events":[["REMOVE",0,1],["ADD",0,1],["ASK",0,1]]}` | `[true]` |
| deletions | 1 | 1 | `{"n":5,"events":[["ADD",0,1],["REMOVE",0,1],["ASK",0,1]]}` | `[false]` |
| deletions | 2 | 1 | `{"n":5,"events":[["ADD",0,1],["ADD",1,2],["ADD",0,2],["REMOVE",0,2],["ASK",0,2]]}` | `[true]` |
| deletions | 3 | 1 | `{"n":5,"events":[["ADD",0,1],["ADD",1,2],["REMOVE",1,2],["ASK",0,2]]}` | `[false]` |
| deletions | 4 | 1 | `{"n":5,"events":[["ADD",0,1],["ADD",0,1],["REMOVE",0,1],["REMOVE",0,1],["ASK",0,1]]}` | `[false]` |
| rollback | 1 | 1 | `{"n":5,"events":[["REMOVE",1,4],["ADD",3,4],["ASK",4,1],["ASK",3,3],["ADD",4,2],["ADD",2,0],["REMOVE",1,4],["ASK",1,3],["ASK",0,0],["ADD",4,2],["ASK",3,2],["ADD",1,1],["ASK",3,3],["REMO…` | `[false,true,false,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true]` |
| rollback | 2 | 1 | `{"n":5,"events":[["ASK",2,4],["ADD",1,3],["ASK",3,0],["REMOVE",2,2],["ASK",0,4],["ADD",2,3],["REMOVE",0,4],["ADD",0,2],["ADD",0,0],["ADD",3,2],["ASK",2,0],["ADD",0,3],["REMOVE",4,3],["A…` | `[false,false,false,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true]` |
| rollback | 3 | 1 | `{"n":5,"events":[["ASK",3,0],["REMOVE",0,1],["ADD",4,2],["ADD",2,2],["REMOVE",3,3],["REMOVE",0,0],["ADD",4,2],["REMOVE",1,4],["ASK",1,2],["REMOVE",0,0],["ADD",0,1],["REMOVE",1,1],["REMO…` | `[false,false,false,false,true,false,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true,true]` |
| rollback | 4 | 1 | `{"n":5,"events":[["ADD",2,3],["ASK",4,3],["ADD",3,0],["ADD",1,1],["ASK",2,4],["REMOVE",2,0],["ADD",0,3],["ADD",1,4],["REMOVE",2,3],["ASK",0,0],["ASK",0,0],["ASK",1,1],["ADD",1,3],["REMO…` | `[false,false,true,true,true,true,false,true,true,true,false,true,true,true,true,true,true,false,false,true,false,true,false,true,false,true,true,true]` |
| scale | 1 | 1 | `{"n":20000,"events":[["ADD",0,1],["ADD",1,2],["ADD",2,3],["ADD",3,4],["ADD",4,5],["ADD",5,6],["ADD",6,7],["ADD",7,8],["ADD",8,9],["ADD",9,10],["ADD",10,11],["ADD",11,12],["ADD",12,13],[…` | `[false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,tr…` |
| scale | 2 | 1 | `{"n":20000,"events":[["ADD",0,1],["ADD",1,2],["ADD",2,3],["ADD",3,4],["ADD",4,5],["ADD",5,6],["ADD",6,7],["ADD",7,8],["ADD",8,9],["ADD",9,10],["ADD",10,11],["ADD",11,12],["ADD",12,13],[…` | `[false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,tr…` |
| scale | 3 | 1 | `{"n":20000,"events":[["ADD",0,1],["ADD",1,2],["ADD",2,3],["ADD",3,4],["ADD",4,5],["ADD",5,6],["ADD",6,7],["ADD",7,8],["ADD",8,9],["ADD",9,10],["ADD",10,11],["ADD",11,12],["ADD",12,13],[…` | `[false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,tr…` |
| scale | 4 | 1 | `{"n":20000,"events":[["ADD",0,1],["ADD",1,2],["ADD",2,3],["ADD",3,4],["ADD",4,5],["ADD",5,6],["ADD",6,7],["ADD",7,8],["ADD",8,9],["ADD",9,10],["ADD",10,11],["ADD",11,12],["ADD",12,13],[…` | `[false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,true,false,tr…` |

## P-X-02 · 超难 · 错误优先级明确的寄存器解释器

### 题面

输入 {src:程序字符串,limit:0..10000 的整数}；最多 2000 个源代码行，行长<=200。
三个寄存器 A/B/C 初值 0，所有操作码和寄存器都区分大小写。空行忽略；# 起到行尾为注释。空白分词。
指令：SET X Y、ADD X Y、MUL X Y、MOD X Y、JZ X L、JNZ X L、JMP L、LABEL L、HALT。
X 必须是 A/B/C；Y 可以是寄存器或符合 [+-]?[0-9]+ 的十进制整数，文字整数必须在有符号 32 位范围。标签名符合 [A-Za-z_][A-Za-z0-9_]*，区分大小写，指向 LABEL 后的下一条可执行指令，允许标签在程序末尾。
先静态检查整个源程序，包括不可达代码：未知指令、参数数目错误、非法寄存器/操作数/标签、重复标签、任何不存在的跳转目标均返回 {status:ERR,steps:0}；静态错误优先于任何运行期结果。
运行期 LABEL 不计步，其余指令每执行一条计 1 步，包括 HALT 和出错指令。在准备执行下一条前，若 steps 已等于 limit，则 TIMEOUT；已经到达程序末尾则成功，不再检查步数。
ADD/MUL 运算结果超出 [-2147483648,2147483647] 则 OVERFLOW；MOD 除数 0 则 DIV0；否则余数与除数同号，例如 -7 mod 3=2，7 mod -3=-2。乘法应精确判断溢出，不可依赖浮点舍入。
正常 HALT 或执行到末尾返回 {status:OK,value:A,steps:已执行步数}；运行期错误只返回 {status:DIV0|OVERFLOW|TIMEOUT,steps:已执行步数}。
公开例：src="SET A -7\nMOD A 3\nHALT",limit=3 -> {status:OK,value:2,steps:3}。

### 计分

| 得分组 | 分点预算 |
|---|---:|
| `arithmetic` | 4 |
| `static` | 4 |
| `labels` | 4 |
| `runtime` | 4 |
| `step_boundary` | 4 |

设计意图：预校验与执行阶段不同，考察跨语言整数语义、未走分支错误和精确步数。

### 三语言接口

- Python：`def solve(data)`。
- Go：`func Solve(input json.RawMessage) json.RawMessage`，包名 `solution`，返回编码后的 JSON。
- TypeScript：`export function solve(data: any): any`。

三语言共享同一份 JSON 输入和期望输出；Go 空数组必须编码为 `[]`，不能用 `null` 代替。TS/JS 先经 TypeScript 5.8.2 编译再执行。

### Python 参考实现

```python
def solve(data):
    import re

    integer = re.compile(r"[+-]?[0-9]+\Z")
    identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
    low, high = -(2**31), 2**31 - 1
    labels, program = {}, []
    arity = {
        "SET": 3,
        "ADD": 3,
        "MUL": 3,
        "MOD": 3,
        "JZ": 3,
        "JNZ": 3,
        "JMP": 2,
        "HALT": 1,
    }

    def operand(token):
        return token in {"A", "B", "C"} or bool(
            integer.fullmatch(token) and low <= int(token) <= high
        )

    for line in data["src"].splitlines():
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        op = parts[0]
        if op == "LABEL":
            if (
                len(parts) != 2
                or not identifier.fullmatch(parts[1])
                or parts[1] in labels
            ):
                return {"status": "ERR", "steps": 0}
            labels[parts[1]] = len(program)
            continue
        if op not in arity or len(parts) != arity[op]:
            return {"status": "ERR", "steps": 0}
        if op in {"SET", "ADD", "MUL", "MOD"} and (
            parts[1] not in {"A", "B", "C"} or not operand(parts[2])
        ):
            return {"status": "ERR", "steps": 0}
        if op in {"JZ", "JNZ"} and parts[1] not in {"A", "B", "C"}:
            return {"status": "ERR", "steps": 0}
        program.append(parts)
    for parts in program:
        if parts[0] in {"JMP", "JZ", "JNZ"} and parts[-1] not in labels:
            return {"status": "ERR", "steps": 0}
    regs = dict.fromkeys("ABC", 0)
    pc = steps = 0
    while pc < len(program):
        if steps == data["limit"]:
            return {"status": "TIMEOUT", "steps": steps}
        parts = program[pc]
        op = parts[0]
        steps += 1
        if op == "HALT":
            break
        if op in {"JMP", "JZ", "JNZ"}:
            jump = (
                op == "JMP"
                or (op == "JZ" and regs[parts[1]] == 0)
                or (op == "JNZ" and regs[parts[1]] != 0)
            )
            pc = labels[parts[-1]] if jump else pc + 1
            continue
        x, token = parts[1:]
        value = regs[token] if token in regs else int(token)
        if op == "SET":
            result = value
        elif op == "ADD":
            result = regs[x] + value
        elif op == "MUL":
            result = regs[x] * value
        else:
            if value == 0:
                return {"status": "DIV0", "steps": steps}
            result = regs[x] % value
        if not low <= result <= high:
            return {"status": "OVERFLOW", "steps": steps}
        regs[x] = result
        pc += 1
    return {"status": "OK", "value": regs["A"], "steps": steps}
```

完整 Go / TypeScript 参考解分别在 `eval_bank_20260925/references.go`、`references.ts`，由 `runner.reference_source(id, language)` 加上对应题目的统一入口。

### 评分用例目录（审核者可见）

以下是全部计分检查。大规模或随机批次只预览首例及摘要；完整输入和期望由固定版本 `cases.py::coding_cases` 生成。不要把这里的测试值作为修复反馈。

| 组 | 检查 | 案例数 | 输入预览 | 期望预览 |
|---|---:|---:|---|---|
| arithmetic | 1 | 2 | `{"src":"SET A 3\nSET B 4\nADD A B\nHALT","limit":10}` | `{"status":"OK","value":7,"steps":4}` |
| arithmetic | 2 | 1 | `{"src":"SET A -7\nMOD A 3","limit":10}` | `{"status":"OK","value":2,"steps":2}` |
| arithmetic | 3 | 1 | `{"src":"SET A 7\nMOD A -3","limit":10}` | `{"status":"OK","value":-2,"steps":2}` |
| arithmetic | 4 | 1 | `{"src":"SET A -7\nMOD A -3","limit":10}` | `{"status":"OK","value":-1,"steps":2}` |
| static | 1 | 2 | `{"src":"HALT\nSET D 1","limit":10}` | `{"status":"ERR","steps":0}` |
| static | 2 | 2 | `{"src":"JZ A missing\nHALT","limit":10}` | `{"status":"ERR","steps":0}` |
| static | 3 | 2 | `{"src":"SET A 1\nJZ A missing","limit":10}` | `{"status":"ERR","steps":0}` |
| static | 4 | 2 | `{"src":"HALT\nLABEL x\nLABEL x","limit":10}` | `{"status":"ERR","steps":0}` |
| labels | 1 | 2 | `{"src":"JMP end\nSET A 9\nLABEL end","limit":1}` | `{"status":"OK","value":0,"steps":1}` |
| labels | 2 | 1 | `{"src":"SET A 3\nLABEL l\nADD A -1\nJNZ A l","limit":7}` | `{"status":"OK","value":0,"steps":7}` |
| labels | 3 | 1 | `{"src":"LABEL X\nJMP x","limit":10}` | `{"status":"ERR","steps":0}` |
| labels | 4 | 1 | `{"src":"# comment\nLABEL start\nLABEL next\nHALT","limit":1}` | `{"status":"OK","value":0,"steps":1}` |
| runtime | 1 | 2 | `{"src":"SET A 2147483647\nADD A 1","limit":10}` | `{"status":"OVERFLOW","steps":2}` |
| runtime | 2 | 2 | `{"src":"SET A -2147483648\nMUL A -1","limit":10}` | `{"status":"OVERFLOW","steps":2}` |
| runtime | 3 | 2 | `{"src":"MOD A 0","limit":10}` | `{"status":"DIV0","steps":1}` |
| runtime | 4 | 1 | `{"src":"MOD A 0\nBOGUS","limit":0}` | `{"status":"ERR","steps":0}` |
| step_boundary | 1 | 2 | `{"src":"","limit":0}` | `{"status":"OK","value":0,"steps":0}` |
| step_boundary | 2 | 2 | `{"src":"HALT","limit":0}` | `{"status":"TIMEOUT","steps":0}` |
| step_boundary | 3 | 2 | `{"src":"SET A 1\nHALT","limit":1}` | `{"status":"TIMEOUT","steps":1}` |
| step_boundary | 4 | 2 | `{"src":"SET A 1\nHALT","limit":2}` | `{"status":"OK","value":1,"steps":2}` |
