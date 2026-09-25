"""20260925 challenge-01：新题身份，不覆盖原 16 题或历史分数。"""

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from random import Random

from . import challenge_oracles as oracle
from .score import parse_json, strict_equal


REVISION='20260925-challenge-09'


@dataclass
class Challenge:
    id: str
    title: str
    kind: str
    prompt: str
    expected: dict
    scale: str
    level: str


def _json(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))


@lru_cache(None)
def reasoning_items(seed=92501):
    rng=Random(seed);items=[]
    def add(qid,title,intro,queries,fn,scale,level):
        prompt=intro+'\n四个独立子问题如下：\n'+_json(queries)+'\n只输出一个 JSON 对象，键为 q1、q2、q3、q4，值为各子问题所求结果。每项 5 内容分，独立计分。禁止工具、联网或运行代码；无需输出思维链。'
        expected={key:fn(value) for key,value in queries.items()}
        items.append(Challenge(qid,title,'reasoning',prompt,expected,scale,level))
    queries={}
    for k,n in enumerate((11,12,13,14),1):
        queries[f'q{k}']={'n':n,'mod':5,'residue':(seed+2*k)%5,'ascents':n//2,'forbidden':[[i,i] for i in range(n)]+[[i,i+1] for i in range(n-1)]+[[n-1,1],[n-2,0],[0,n-1]]}
    add('CR-01','禁位排列的端点、逆序同余与上升数',
        '排列包含整数 0..n-1 各一次，位置从 0 编号。forbidden 中 [i,v] 表示第 i 位不能为 v。还要求首项小于末项，逆序对总数模 mod 等于 residue，恰有 ascents 个相邻上升（p[i]<p[i+1]）。重复禁位仍只是同一条约束，逆序对按完整排列计算，不是只在未禁位置上计算。求合法排列数量。',queries,oracle.permutation_counts,'末题 n=14，加入双端点禁位、模 5 逆序约束和上升数联合约束；这是新版本的简单档基线。','easy')
    queries={}
    for k,n in enumerate((20,21,22,23),1):
        rows=[[rng.randrange(2,10),rng.randrange(1,7),rng.randrange(3,19)] for _ in range(n)]
        queries[f'q{k}']={'items':rows,'requires':[[3,1],[7,4],[n-1,2],[n-2,5]],'excludes':[[0,5],[6,9],[2,8],[10,11]],'weight':n*2,'resource':n+7,'parity':(k+seed)%2}
    add('CR-02','双资源依赖选择的最优值与全部计数',
        'items[i]=[重量,资源消耗,价值]。每件最多一次，重量总和<=weight、资源总和<=resource。requires=[a,b] 表示选 a 必选 b；excludes=[a,b] 表示不能同时选。所选下标中能被 3 整除者的数量模 2 必须等于 parity。先价值最大，再重量小、资源消耗小、升序下标数组字典序小；不要把价值并列数误当可行集合数。返回 {value,indices,weight,resource,optimal_count,feasible_count}；optimal_count 只按最大价值计最优集合数，feasible_count 计全部合法集合。无可行解返回 null。',queries,oracle.constrained_selection,'20..23 个物品对应百万级子集，增加依赖、互斥、双资源和奇偶联动；这是新版本的简单档基线。','easy')
    queries={}
    for k,(rows,cols,h) in enumerate(((8,10,18),(8,12,24),(10,12,30),(10,14,36)),1):
        queries[f'q{k}']={'rows':rows,'cols':cols,'holes':[[0,0],[rows-1,cols-1]],'horizontal':h+(seed%2)*2}
    add('CR-03','六行缺角棋盘的精确方向计数',
        'rows 行 cols 列棋盘，坐标从 0 开始，删除 holes 中格子。用 1x2 骨牌完全覆盖剩余格子，允许横竖放，不重叠、不越界。求恰有 horizontal 块横放骨牌的铺法数；不按旋转或镜像去重，缺角也不能当作可旋转等价。',queries,oracle.domino_count,'棋盘扩大到 10x14，并要求精确方向计数；轮廓状态和横放约束同时存在，作为普通档的超难基线。','medium')
    queries={}
    for k,n in enumerate((12,13,14,15),1):
        w=[[None if i==j else rng.randrange(1,12) for j in range(n)] for i in range(n)]
        queries[f'q{k}']={'n':n,'weights':w,'before':[[1,4],[2,5],[3,6],[4,8],[5,9]]}
    add('CR-04','带先后约束的最短 Hamilton 路径',
        '有向图节点 0..n-1，weights[u][v] 是边权，null 表示无边。找从 0 出发、最终到 n-1、每节点恰访问一次的最小权重路径。before=[a,b] 表示 a 必须先访问，约束按传递闭包理解；不可把无边当作大权重。返回 {cost,count,path}：最小总权、达到此最小权的路径数、其中节点序列字典序最小的路径。无解返回 null。',queries,oracle.hamilton,'最多 13 个内部节点、五组先后约束和稠密有向权图；必须联合计数和字典序路径，作为普通档的超难基线。','medium')
    queries={}
    for k,n in enumerate((40,44,48,52),1):
        queries[f'q{k}']={'n':n,'height':5+k%2,'mod':11,'residue':(seed+3*k)%11,'peaks':n//3,'max_run':3}
    add('CR-05','有界平衡串的加权同余计数',
        '长度 n 的二进制串，1 使高度+1，0 使高度-1；从 0 开始，每个前缀高度必须在 [0,height]，最终回到 0。连续相同位最多 max_run 个。相邻子串 10 恰出现 peaks 次。所有值为 1 的位的位置编号之和模 mod 等于 residue，位置从 1 编号。求串数量。',queries,oracle.bounded_words,'原始串空间达到 2^52；高度、连续段、峰数和模 11 加权余数联合约束，属于困难档。','hard')
    queries={}
    for k in range(1,5):
        left=[rng.randrange(2,6) for _ in range(5)];right=[rng.randrange(2,6) for _ in range(5)]
        queries[f'q{k}']={'left':left,'right':right,'pairs':4,'costs':[1+k%2,2 if k>2 else 1],'drawn_left':[0]*5,'drawn_right':[0]*5}
    add('CR-06','双配对目标与非对称代价的自适应博弈',
        '四种颜色的左/右手套库存为 left/right。每步选择一侧后由最坏对手决定颜色，取出后才可见颜色并可改变后续选择；不能把对手当作均匀随机。不能放回；每次选左/右花费 costs[0]/costs[1]。已取数量由 drawn_left/right 给出并属于原库存。成功条件是 sum_i min(已取左_i,已取右_i)>=pairs，同色可形成多双，达到目标后立即停止计费。求最优自适应策略在最坏颜色序列下的最小剩余总代价。保证总库存可以形成目标双数。',queries,oracle.adaptive_pairs,'五色、四双目标和非对称行动代价形成高维 min-max 状态；库存观察后的策略不能用固定配额替代，属于困难档。','hard')
    queries={}
    for k,high in enumerate((220,260,300,340),1):
        queries[f'q{k}']={'low':2,'high':high+(seed%3),'announcements':[['SUM','DONT'],['PRODUCT','OTHER_DONT'],['SUM','DONT'],['PRODUCT','KNOW'],['SUM','KNOW']]}
    add('CR-07','公开知识更新中的嵌套不知道',
        '最初可能世界是所有 low<=a<b<=high 的整数对。SUM 只知道 a+b，PRODUCT 只知道 a*b，两人知道范围与规则。announcements 按序真实公开。每次均只在上一步剩余世界集合内重新计算知识：KNOW=说话者观察值对应恰一个世界；DONT=多于一个；OTHER_DONT=说话者观察值对应的每个世界里，另一人都对应多于一个世界。筛掉不满足当次发言的世界后继续。返回 {counts,worlds}：每次发言后的世界数，以及最终世界列表按 a 再 b 升序。',queries,oracle.public_knowledge,'初始世界超过五万，包含五次公开更新和嵌套知道/不知道量词；看似重复的声明每次都必须基于新世界重算。','extreme')
    queries={}
    for k,n in enumerate((8,9,9,10),1):
        all_edges=list(combinations(range(n),2));rng.shuffle(all_edges);edges=sorted(all_edges[:18 if k<3 else 20])
        queries[f'q{k}']={'n':n,'edges':[list(e) for e in edges],'active':n+2,'degree_parity':[[1,k%2],[n-2,(seed+k)%2],[n-1,(seed+2*k)%2]]}
    add('CR-08','条件化随机图的连通概率',
        '无向图节点 0..n-1，edges 是唯一边列表。均匀选恰好 active 条边保留。再条件化到 degree_parity：其中 [v,p] 要求保留图中 v 的度模 2 为 p。求 {given,connected,probability,component_histogram}：满足条件的边子集数、其中全图连通的数量、连通条件概率的最简 [分子,分母]、节点 0 所在连通分量大小的 [大小,数量] 升序表（只列非零）。',queries,oracle.reliability,'18..20 条边、三项度奇偶条件和连通分量统计共同条件化；边子集不可用独立概率相乘，属于超难档。','extreme')
    return tuple(items)


def grade_reasoning(item,text):
    try:data=parse_json(text)
    except (ValueError,TypeError,RecursionError):return {'status':'fail','reason_code':'format_error','points':0,'score10':0,'passed':False,'groups':[]}
    if not isinstance(data, dict) or set(data) != set(item.expected):
        protocol_ok = False
    else:
        protocol_ok = True
        for key, want in item.expected.items():
            got = data.get(key)
            if isinstance(want, dict):
                protocol_ok = protocol_ok and isinstance(got, dict) and set(got) == set(want)
    groups=[]
    for key,want in item.expected.items():
        got=data.get(key)
        # 每个独立子问题内按明确输出字段均分，数组必须完整正确。
        checks=[strict_equal(got.get(k),v) for k,v in want.items()] if isinstance(want,dict) and isinstance(got,dict) else [strict_equal(got,want)]
        score=5*sum(checks)/len(checks)
        groups.append({'id':key,'points':score,'max':5})
    total=sum(g['points'] for g in groups)
    passed=total==20 and protocol_ok
    return {'status':'pass' if passed else 'fail','reason_code':'ok' if passed else 'content_mismatch','points':total,'score10':total/2,'passed':passed,'groups':groups}


def prompt_hash(item):return hashlib.sha256(item.prompt.encode()).hexdigest()


def salt_prompt(prompt, salt):
    """Prefix a per-request nonce so gateway/prompt caches cannot reuse a prior answer."""
    return f"【本次请求随机盐 {salt}；与题目答案无关】\n\n{prompt}"


def salted_prompt_hash(prompt):
    return hashlib.sha256(prompt.encode()).hexdigest()


# 此导入只用于静态题目生成。
from itertools import combinations
