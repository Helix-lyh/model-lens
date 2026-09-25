"""题面与评分组是唯一手写题目定义；导出文档和 JSON 由这里产生。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    level: str
    title: str
    prompt: str
    groups: tuple[tuple[str, int], ...]
    rationale: str
    reference: str | None = None


ITEMS = [
    Item(
        "R-E-01",
        "easy",
        "包装金额与余数证书",
        """有面额为 5、8、11 的三种包装，数量均为非负整数，不限制包装总数。
求 1..50 中不能凑出的金额。输出对象：
residue_min：按余数 0,1,2,3,4 排列，能够凑出且模 5 为该余数的最小非负金额；
impossible：1..50 中不能凑出的全部金额，升序、不重复；largest：最大的不可达金额；count：不可达金额数量。
只输出一个 JSON 对象。""",
        (("residue_min", 6), ("impossible", 10), ("largest_count", 4)),
        "可达金额可反复加 5；最小余数代表给出有限证书。最终集合与统计量必须相互一致。",
    ),
    Item(
        "R-E-02",
        "easy",
        "先验选择后的条件概率",
        """先选袋子：选择 U 的概率为 1/3，选择 V 的概率为 2/3。U 内有 3 红 1 蓝，V 内有 1 红 3 蓝。
在选中袋子中等概率、不放回抽两个球。报告程序当且仅当至少一个球是红色时输出 H；现在观察到 H。
求 likelihood_u=P(H|U)、likelihood_v=P(H|V)、posterior_u=P(U|H)、both_red=P(两球都红|H)。
每个概率使用 [分子,分母] 的整数数组，分母必须为正；等价分数均可。只输出包含这四个字段的 JSON。""",
        (("likelihood_u", 4), ("likelihood_v", 4), ("posterior_u", 6), ("both_red", 6)),
        "区分条件化与直接平均，避免依赖自然语言含糊的观察者选择机制。",
    ),
    Item(
        "R-N-01",
        "medium",
        "预先固定抽取的最坏情况",
        """三种颜色按红、蓝、绿排序。左手套库存 L=[3,5,4]，右手套库存 R=[4,2,6]。
摸之前能选择左或右，不能挑颜色；取出后可看见颜色。但本题必须预先固定总共取 l 只左、r 只右，不能根据看到的颜色改变计划。
目标：无论抽到什么，都至少有一双同色左右手套。0<=l,r<=12。
输出 frontier：长度 13，frontier[l] 是仍存在无配对抽法时可取得的最多右手套数；minimum：最少 l+r；
allocations：所有达到 minimum 且必有配对的 [l,r]，按 l 升序；
counterexample：固定 (l,r)=(5,5) 的一种无配对抽法，含 left、right 两个长度 3 的非负整数数组，各颜色不超过库存。
只输出一个 JSON 对象。""",
        (("frontier", 8), ("minimum", 4), ("allocations", 4), ("counterexample", 4)),
        "最小值必须同时有上界策略和下界反例；接受所有合法反例，不锁定一种写法。",
    ),
    Item(
        "R-N-02",
        "medium",
        "带端点比较与奇偶性的禁位排列",
        """对 1..n 的排列 p，位置从 1 编号。要求 p(i)!=i，且 i<n 时 p(i)!=i+1；另要求 p(1)<p(n)。没有首尾环形禁位。
一个逆序对是 i<j 且 p(i)>p(j)。
输出 count4、count5：n=4、5 的合法排列数；parity7：[n=7 时逆序对数为偶数的合法排列数, 为奇数的合法排列数]；count7：n=7 合法排列总数。
只输出一个 JSON 对象。""",
        (("count4", 3), ("count5", 3), ("parity7", 10), ("count7", 4)),
        "端点和奇偶条件打破直接套错排数的路径；小规模子问题可以独立拿分。",
    ),
    Item(
        "R-H-01",
        "hard",
        "双处理器与互斥资源调度",
        """任务 A..F 的时长依次 [3,2,4,3,2,2]。依赖：A->C、A->D、B->E、C->F、D->F、E->F。
有两台相同处理器；任务不可抢占，每个任务使用一台处理器。开始时间是非负整数，执行区间为 [start,start+duration)，端点相接不重叠。
额外规则：C 和 E 使用同一独占资源，不能重叠。允许处理器主动空闲。
输出 lower_bounds：[只考虑依赖的最长路径时长, 总工作量除以 2 向上取整]；
base：含 makespan（全部任务完成的最早时间）、starts（A..F 的开始时间，最优方案中取字典序最小）；
optimal_count：最优 makespan 下不同开始时间向量的个数，不区分处理器编号；
changed：仅删除 C/E 资源互斥后，按相同规则给出 makespan、starts。
只输出一个 JSON 对象。""",
        (("lower_bounds", 3), ("base", 8), ("optimal_count", 4), ("changed", 5)),
        "工作量和关键路径下界不一定可达；必须处理故意空闲、资源交互与反事实。",
    ),
    Item(
        "R-H-02",
        "hard",
        "约束选物与没有增益的反事实",
        """有八件物品，下标 0..7 的 (重量,价值) 分别为
[(4,8),(5,11),(6,13),(3,7),(2,4),(4,9),(5,12),(1,2)]。每件最多选一次，总重量<=15。
规则：选 2 必须选 4；选 6 必须选 3；0 与 5 不能同选；1 与 6 不能同选。
最大化价值；并列先取总重量较小，再取升序下标数组字典序较小。空集合可行。
输出 base：{indices,value,weight,value_ties}，value_ties 是只按最大价值计的最优集合数，尚未应用后两项平局规则；
changed：仅删除 1/6 互斥后按同样规则的四字段对象；
feasible_counts：[原规则可行集合数,删除互斥后可行集合数]；delta：新最大价值减旧最大价值。
只输出 JSON。""",
        (("base", 7), ("changed", 7), ("feasible_counts", 4), ("delta", 2)),
        "删除约束未必提高最优值，但可能改变最优解及最优解数量。",
    ),
    Item(
        "R-X-01",
        "extreme",
        "可观察颜色的自适应抽取博弈",
        """红、蓝、绿三色的左手套库存 [2,3,4]，右手套库存 [3,2,4]。
每一步选择取一只左或右，从该侧剩余手套中取出，颜色不能由你选择；取出后立刻看见颜色。允许据此调整下一步选择，出现同色左右配对立即成功。
问对最不利的颜色序列，最佳策略需要的最少总抽取数。不是期望值，不能放回。
输出 fixed：若预先固定左右数量时的最少总数；
after_first_left：首步取左且得到红/蓝/绿后，最佳自适应策略仍需要的最坏剩余步数，长度 3，不含首步；
first_action_costs：[强制首步左后的最佳最坏总数,强制首步右后的最佳最坏总数]；adaptive：不限制首步时的最少最坏总数。
只输出 JSON。""",
        (
            ("fixed", 4),
            ("after_first_left", 8),
            ("first_action_costs", 4),
            ("adaptive", 4),
        ),
        "需要区分固定分配、可观察策略和 min-max 量词顺序。穷举状态递推验证最优性。",
    ),
    Item(
        "R-X-02",
        "extreme",
        "缺角棋盘的计数与旋转去重",
        """4 行 7 列棋盘，坐标 (行,列) 从 0 开始。删除 (0,0) 和 (3,6)。
用 1x2 骨牌无重叠地完全铺满其余 26 格；骨牌可横可竖。先按每块骨牌实际覆盖的格子区分铺法。
输出 horizontal_histogram：全部铺法中按横放骨牌数 h 分类的 [h,铺法数]，h 升序，只列非零项；
selected：恰好横放 10 块时的铺法数；rotation_fixed：其中旋转 180 度后完全不变的铺法数；
orbits：恰好横放 10 块时，把相差 180 度旋转的铺法视为同一种后的数量。只按该旋转去重，不按镜像去重。
只输出 JSON。""",
        (
            ("horizontal_histogram", 8),
            ("selected", 3),
            ("rotation_fixed", 5),
            ("orbits", 4),
        ),
        "计数、对称不动点和轨道数分开验证，避免简单除以二。",
    ),
    Item(
        "P-E-01",
        "easy",
        "半开区间归并",
        """输入 {intervals:[[l,r],...]}，整数 -1000000<=l<=r<=1000000，最多 2000 个区间。
将半开区间 [l,r) 的并集转换为按左端点升序的最少区间列表。空区间丢弃；相接如 [1,3)、[3,5) 必须合并。
返回 {intervals:归并后的列表,length:并集总长度}。可修改输入，但多次调用之间不得残留状态。
公开例：[[1,3],[3,5],[2,4],[8,8]] -> {intervals:[[1,5]],length:4}。""",
        (("empty", 4), ("touching", 4), ("overlap", 4), ("ordering", 4), ("mixed", 4)),
        "空区间、端点和嵌套分别计分。",
        "merge_intervals",
    ),
    Item(
        "P-E-02",
        "easy",
        "逐字符转义分隔",
        """输入 {text:字符串}，长度<=10000，仅含 ASCII 可打印字符。
从左到右解析：未转义的 | 分隔字段，保留空字段；反斜杠转义紧跟的任意一个字符，该字符按字面加入当前字段，反斜杠本身不保留。
末尾没有后继字符的反斜杠按字面保留。返回字段字符串数组。不递归处理已经转义出的字符。
公开例：空串 -> [""]；"a||b|" -> ["a","","b",""]；字符序列 a、反斜杠、|、b -> ["a|b"]。""",
        (
            ("empty_fields", 4),
            ("escaped_separator", 4),
            ("escaped_escape", 4),
            ("trailing", 4),
            ("mixed", 4),
        ),
        "用状态转换区分一次转义、成对反斜杠和末尾残留。",
        "escaped_split",
    ),
    Item(
        "P-N-01",
        "medium",
        "去重与原子库存批次",
        """输入 {initial:{sku:非负整数,...},events:[{id:字符串,delta:[[sku,整数增量],...]},...]}。
sku 和 id 为非空 ASCII 字母数字串，最多 100 个 sku、2000 个事件，每事件最多 20 条 delta，所有库存和增量绝对值不超过 1000000。
初始缺失 sku 视为 0。按序处理，id 首次出现立即占用，即使该事件失败；重复 id 返回 DUP，不做其他检查。
同一事件先按 sku 合并全部增量，再检查所有最终库存是否非负；有负数则整个事件不生效，返回 NEGATIVE；否则原子更新，返回 OK。
返回 {stock:[[sku,最终库存],...],trace:[状态,...]}。stock 只列非零库存并按 sku 字典序排序；空增量事件也占号并返回 OK。
公开例：initial={a:2}，事件 x 的 delta=[[a,-3],[a,1]]，再一次 x 的 delta=[[a,5]] -> stock=[]，trace=[OK,DUP]。""",
        (
            ("basic", 4),
            ("atomic", 4),
            ("duplicate", 4),
            ("coalesce", 4),
            ("interactions", 4),
        ),
        "失败占号、重复项合并和批次回滚形成交互边界。",
        "atomic_stock",
    ),
    Item(
        "P-N-02",
        "medium",
        "拓扑顺序与真正的环成员",
        """输入 {nodes:[唯一节点名,...],edges:[[u,v],...]}；边表示 u 必须先于 v，端点保证存在。
0..60 个节点，0..2000 条边。名字为 ASCII 字母数字串，按字符串字典序比较。重复边只算一次；允许自环。
若无环，返回 {order:字典序最小的完整拓扑序,cycle_nodes:[]}。
若有环，返回 {order:null,cycle_nodes:真正处在至少一个有向环中的节点名升序列表}；仅仅被环阻塞的下游节点不能列入。
公开例：nodes=[a,b,c]，edges=[[a,b],[b,a],[b,c]] -> {order:null,cycle_nodes:[a,b]}。""",
        (("dag", 4), ("ties", 4), ("cycles", 4), ("downstream", 4), ("mixed", 4)),
        "区分 Kahn 算法的剩余节点与环成员。",
        "dependency_order",
    ),
    Item(
        "P-H-01",
        "hard",
        "带两层平局规则的区间调度",
        """输入 {jobs:[{id,start,end,value},...]}，id 唯一，为 ASCII 字母数字串；0<=start<end<=1000000；value 为 -1000..1000 的整数，最多 2000 项。
选择互不重叠的半开区间任务，端点相接可共存，空集合可行。先最大化总 value；平局取任务数少者；仍平局，比较按执行时间排列的 id 数组，取字典序最小。
返回 {value:总价值,ids:执行顺序的 id 数组}。
公开例：[{id:a,start:0,end:2,value:4},{id:b,start:2,end:4,value:4},{id:c,start:0,end:4,value:8}] -> {value:8,ids:[c]}。""",
        (("basic", 4), ("boundary", 4), ("count_tie", 4), ("lex_tie", 4), ("scale", 4)),
        "不仅测试能否找到最优值，还测试稳定重建、负价值和两层平局。",
        "weighted_schedule",
    ),
    Item(
        "P-H-02",
        "hard",
        "快照事务与写写冲突",
        """输入 {initial:{key:整数,...},events:[事件,...]}。最多 200 个 key、2000 条事件，值为绝对值<=1000000 的整数。
事件为 [BEGIN,tx]、[GET,tx,key]、[SET,tx,key,value]、[COMMIT,tx]。名字是非空 ASCII 字母数字串；tx 的 BEGIN 只出现一次，后续事件只引用活跃事务；结束时可以仍有活跃事务。
全局版本从 0 开始。BEGIN 记录当前已提交内容和版本；GET 先读自己的写集，否则读 BEGIN 快照，缺失返回 null；不能读其他事务未提交内容。
COMMIT：若自己的任一写入 key 最近提交版本 > 本事务快照版本，整个事务失败并结束；否则原子提交，全局版本加 1，包括空写集提交。失败提交不增加版本。同值写入也算写；读集不参与冲突判断。
返回 {reads:[[tx,key,value_or_null],...],commits:[[tx,成功布尔,成功后的版本或null],...],final:[[key,value],...]}，前两项按发生顺序，final 按 key 升序且只含已提交内容。
公开例：initial={x:1}；[BEGIN,a],[BEGIN,b],[SET,a,x,2],[COMMIT,a],[GET,b,x],[SET,b,x,3],[COMMIT,b] -> reads=[[b,x,1]],commits=[[a,true,1],[b,false,null]],final=[[x,2]]。""",
        (
            ("snapshot", 4),
            ("own_writes", 4),
            ("conflict", 4),
            ("version", 4),
            ("isolation", 4),
        ),
        "将快照读、读己之写、同值提交和全事务冲突分开，避免把串行化规则混入。",
        "snapshot_transactions",
    ),
    Item(
        "P-X-01",
        "extreme",
        "带边计数的动态连通性",
        """输入 {n:顶点数,events:[[op,u,v],...]}，顶点 0..n-1，1<=n<=20000，最多 40000 条事件。
无向图初始无边；op 为 ADD、REMOVE、ASK。ADD 给无向边的引用计数加 1；REMOVE 只减去一个引用，已经为零则无操作。计数大于零时边存在；(u,v) 与 (v,u) 是同一条边；允许自环。
ASK 查询该时刻 u 和 v 是否连通；顶点与自己永远连通。只返回所有 ASK 的布尔数组，按出现顺序。
公开例：n=2；ADD 0 1、ADD 1 0、REMOVE 0 1、ASK 0 1、REMOVE 1 0、ASK 0 1 -> [true,false]。
大规模测试包含长链上的反复断开与恢复。需要避免每次查询都遍历整张图；按给定离线事件列表设计。""",
        (
            ("basic", 4),
            ("multiplicity", 4),
            ("deletions", 4),
            ("rollback", 4),
            ("scale", 4),
        ),
        "离线时间区间、引用计数及可回滚连通结构相互作用；规模组识别逐次全图搜索。",
        "dynamic_connectivity",
    ),
    Item(
        "P-X-02",
        "extreme",
        "错误优先级明确的寄存器解释器",
        """输入 {src:程序字符串,limit:0..10000 的整数}；最多 2000 个源代码行，行长<=200。
三个寄存器 A/B/C 初值 0，所有操作码和寄存器都区分大小写。空行忽略；# 起到行尾为注释。空白分词。
指令：SET X Y、ADD X Y、MUL X Y、MOD X Y、JZ X L、JNZ X L、JMP L、LABEL L、HALT。
X 必须是 A/B/C；Y 可以是寄存器或符合 [+-]?[0-9]+ 的十进制整数，文字整数必须在有符号 32 位范围。标签名符合 [A-Za-z_][A-Za-z0-9_]*，区分大小写，指向 LABEL 后的下一条可执行指令，允许标签在程序末尾。
先静态检查整个源程序，包括不可达代码：未知指令、参数数目错误、非法寄存器/操作数/标签、重复标签、任何不存在的跳转目标均返回 {status:ERR,steps:0}；静态错误优先于任何运行期结果。
运行期 LABEL 不计步，其余指令每执行一条计 1 步，包括 HALT 和出错指令。在准备执行下一条前，若 steps 已等于 limit，则 TIMEOUT；已经到达程序末尾则成功，不再检查步数。
ADD/MUL 运算结果超出 [-2147483648,2147483647] 则 OVERFLOW；MOD 除数 0 则 DIV0；否则余数与除数同号，例如 -7 mod 3=2，7 mod -3=-2。乘法应精确判断溢出，不可依赖浮点舍入。
正常 HALT 或执行到末尾返回 {status:OK,value:A,steps:已执行步数}；运行期错误只返回 {status:DIV0|OVERFLOW|TIMEOUT,steps:已执行步数}。
公开例：src="SET A -7\\nMOD A 3\\nHALT",limit=3 -> {status:OK,value:2,steps:3}。""",
        (
            ("arithmetic", 4),
            ("static", 4),
            ("labels", 4),
            ("runtime", 4),
            ("step_boundary", 4),
        ),
        "预校验与执行阶段不同，考察跨语言整数语义、未走分支错误和精确步数。",
        "register_machine",
    ),
]

BY_ID = {item.id: item for item in ITEMS}


def model_prompt(item, language=None):
    prefix = "你只能依据题面独立作答，不得使用工具、联网或运行代码。无需输出思维链。JSON 顶层及所有嵌套对象都必须且只能包含题面列出的字段，不得添加额外键或第二个候选答案。\n"
    if not item.reference:
        if language is not None:
            raise ValueError("推理题不使用 language")
        return prefix + item.prompt
    signatures = {
        "python": "def solve(data):，输入和输出为 JSON 对应的 Python 数据。",
        "go": "func Solve(input json.RawMessage) json.RawMessage，package solution，自行 import encoding/json。输入是一份 JSON，返回编码后的 JSON。",
        "typescript": "export function solve(data: any): any，输入和输出为 JSON 对应的数据。",
    }
    if language not in signatures:
        raise ValueError("编程题需要 python/go/typescript")
    return (
        prefix
        + item.prompt
        + "\n实现接口："
        + signatures[language]
        + f"\n只输出一个 {language} 代码围栏。只用标准库，不使用文件、网络或子进程；不得读取判分器或打印评分标记。每次调用独立，允许修改本次输入。"
    )
