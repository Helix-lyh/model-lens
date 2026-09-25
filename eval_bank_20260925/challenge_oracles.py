"""加强版有限问题的精确求解；只由评测端离线运行。"""

from collections import Counter
from functools import lru_cache
from fractions import Fraction


def permutation_counts(data):
    n, mod = data['n'], data['mod']
    forbidden = {tuple(p) for p in data['forbidden']}
    @lru_cache(None)
    def dp(mask, first, last, residue, ascents):
        i=mask.bit_count()
        if i==n:
            return int(first<last and residue==data['residue'] and ascents==data['ascents'])
        if ascents>data['ascents'] or ascents+n-i<data['ascents']:
            return 0
        result=0
        for v in range(n):
            if mask>>v&1 or (i,v) in forbidden:
                continue
            inversions=(mask>>(v+1)).bit_count()
            result+=dp(mask|1<<v,v if i==0 else first,v,(residue+inversions)%mod,ascents+int(i>0 and last<v))
        return result
    return dp(0,-1,-1,0,0)


def constrained_selection(data):
    items=data['items'];n=len(items)
    best=None;count=feasible=0
    for mask in range(1<<n):
        if any(mask>>a&1 and not mask>>b&1 for a,b in data['requires']):continue
        if any(mask>>a&1 and mask>>b&1 for a,b in data['excludes']):continue
        picked=[i for i in range(n) if mask>>i&1]
        w=sum(items[i][0] for i in picked);r=sum(items[i][1] for i in picked)
        if w>data['weight'] or r>data['resource']:continue
        if sum(i%3==0 for i in picked)%2 != data['parity']:continue
        feasible+=1;value=sum(items[i][2] for i in picked)
        key=(-value,w,r,picked)
        if best is None or value>-best[0]:count=1
        elif value==-best[0]:count+=1
        if best is None or key<best:best=key
    return {'value':-best[0], 'indices':best[3], 'weight':best[1], 'resource':best[2], 'optimal_count':count,'feasible_count':feasible} if best else None


def domino_count(data):
    rows,cols=data['rows'],data['cols'];holes={tuple(p) for p in data['holes']}
    blocked=[sum(1<<r for r in range(rows) if (r,c) in holes) for c in range(cols)]
    dp={(0,0):1}
    for col in range(cols):
        nxt=Counter()
        for (incoming,h),count in dp.items():
            if incoming&blocked[col]:continue
            def fill(mask,out,added):
                if mask==(1<<rows)-1:
                    nxt[out,h+added]+=count;return
                r=next(i for i in range(rows) if not mask>>i&1)
                if r+1<rows and not mask>>(r+1)&1:fill(mask|1<<r|1<<(r+1),out,added)
                if col+1<cols and not blocked[col+1]>>r&1:fill(mask|1<<r,out|1<<r,added+1)
            fill(incoming|blocked[col],0,0)
        dp=nxt
    return sum(count for (mask,h),count in dp.items() if mask==0 and (data.get('horizontal') is None or h==data['horizontal']))


def hamilton(data):
    n=data['n'];weights=data['weights'];requirements=[0]*n
    for a,b in data['before']:requirements[b]|=1<<a
    @lru_cache(None)
    def dp(mask,last):
        if mask==(1<<n)-1:return (0,1,()) if last==n-1 else None
        best=None
        for v in range(n):
            if mask>>v&1 or requirements[v]&mask!=requirements[v] or weights[last][v] is None:continue
            if v==n-1 and mask.bit_count()!=n-1:continue
            tail=dp(mask|1<<v,v)
            if tail is None:continue
            cost=weights[last][v]+tail[0];path=(v,)+tail[2]
            if best is None or cost<best[0]:best=(cost,tail[1],path)
            elif cost==best[0]:best=(cost,best[1]+tail[1],min(path,best[2]))
        return best
    best=dp(1,0)
    return None if best is None else {'cost':best[0],'count':best[1],'path':[0,*best[2]]}


def bounded_words(data):
    n=data['n'];height=data['height'];mod=data['mod'];target=data['residue']
    @lru_cache(None)
    def dp(i,balance,last,run,residue,peaks):
        if i==n:return int(balance==0 and residue==target and peaks==data['peaks'])
        if balance>n-i or peaks>data['peaks']:return 0
        total=0
        for bit in (0,1):
            b=balance+(1 if bit else -1);r=run+1 if bit==last else 1
            if not 0<=b<=height or r>data['max_run']:continue
            total+=dp(i+1,b,bit,r,(residue+(i+1)*bit)%mod,peaks+int(last==1 and bit==0))
        return total
    return dp(0,0,-1,0,0,0)


def adaptive_pairs(data):
    left,right=tuple(data['left']),tuple(data['right']);target=data['pairs']
    @lru_cache(None)
    def dp(a,b):
        if sum(min(x,y) for x,y in zip(a,b))>=target:return 0
        choices=[]
        for side,cap,drawn,cost in ((0,left,a,data['costs'][0]),(1,right,b,data['costs'][1])):
            worst=[]
            for i in range(len(cap)):
                if drawn[i]>=cap[i]:continue
                nxt=list(drawn);nxt[i]+=1
                worst.append(dp(tuple(nxt),b) if side==0 else dp(a,tuple(nxt)))
            if worst:choices.append(cost+max(worst))
        return min(choices) if choices else 10**6
    a=tuple(data.get('drawn_left',[0]*len(left)));b=tuple(data.get('drawn_right',[0]*len(left)))
    return dp(a,b)


def public_knowledge(data):
    worlds=[(a,b) for a in range(data['low'],data['high']+1) for b in range(a+1,data['high']+1)]
    history=[]
    for op in data['announcements']:
        owner,claim=op
        observed=lambda p:p[0]+p[1] if owner=='SUM' else p[0]*p[1]
        buckets=Counter(map(observed,worlds))
        if claim=='KNOW':worlds=[w for w in worlds if buckets[observed(w)]==1]
        elif claim=='DONT':worlds=[w for w in worlds if buckets[observed(w)]>1]
        else:
            other=lambda p:p[0]*p[1] if owner=='SUM' else p[0]+p[1]
            counts=Counter(map(other,worlds))
            bad={observed(w) for w in worlds if counts[other(w)]==1}
            worlds=[w for w in worlds if observed(w) not in bad]
        history.append(len(worlds))
    return {'counts':history,'worlds':[list(w) for w in worlds]}


def reliability(data):
    n=data['n'];edges=data['edges'];m=len(edges);given=connected=0;hist=Counter()
    for mask in range(1<<m):
        if mask.bit_count()!=data['active']:continue
        degree=[0]*n;adj=[[] for _ in range(n)]
        for i,(u,v) in enumerate(edges):
            if mask>>i&1:degree[u]+=1;degree[v]+=1;adj[u].append(v);adj[v].append(u)
        if any(degree[v]%2!=p for v,p in data['degree_parity']):continue
        given+=1;seen={0};todo=[0]
        while todo:
            for v in adj[todo.pop()]:
                if v not in seen:seen.add(v);todo.append(v)
        connected+=len(seen)==n;hist[len(seen)]+=1
    return {'given':given,'connected':connected,'probability':[Fraction(connected,given).numerator,Fraction(connected,given).denominator] if given else None,'component_histogram':[[k,hist[k]] for k in sorted(hist)]}
