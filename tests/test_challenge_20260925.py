from itertools import permutations, product, combinations
from collections import Counter
import json

from eval_bank_20260925 import challenge_oracles as o
from eval_bank_20260925.challenge import reasoning_items, grade_reasoning, salt_prompt, salted_prompt_hash
from eval_bank_20260925.challenge_coding import cases as challenge_cases
from eval_bank_20260925.challenge_live import TIMEOUT_BY_LEVEL, apply_time_score, time_score_factor


def test_permutations_against_full_enumeration():
    for n in range(3,8):
        for residue in range(3):
            data={'n':n,'mod':3,'residue':residue,'ascents':n//2,'forbidden':[[i,i] for i in range(n)]+[[i,i+1] for i in range(n-1)]}
            expected=0
            for p in permutations(range(n)):
                if p[0]>=p[-1] or any(p[i]==v for i,v in data['forbidden']):continue
                if sum(p[i]<p[i+1] for i in range(n-1))!=n//2:continue
                expected+=sum(p[i]>p[j] for i in range(n) for j in range(i+1,n))%3==residue
            assert o.permutation_counts(data)==expected


def test_words_against_full_enumeration():
    for n in (6,8,10,12):
        data={'n':n,'height':3,'mod':5,'residue':2,'peaks':n//3,'max_run':3}
        expected=0
        for bits in product((0,1),repeat=n):
            if any(bits[i:i+4] in ((0,0,0,0),(1,1,1,1)) for i in range(n-3)):continue
            prefix=[sum(1 if x else -1 for x in bits[:k]) for k in range(1,n+1)]
            if prefix[-1]!=0 or min(prefix)<0 or max(prefix)>3:continue
            if sum(a==1 and b==0 for a,b in zip(bits,bits[1:]))!=n//3:continue
            expected+=sum(i+1 for i,b in enumerate(bits) if b)%5==2
        assert o.bounded_words(data)==expected


def test_domino_profiles_against_cover_enumeration():
    for rows,cols in ((2,5),(4,5),(4,7)):
        holes={(0,0),(rows-1,cols-1)};counts=Counter()
        def visit(left,h):
            if not left:counts[h]+=1;return
            a=min(left)
            for b in ((a[0]+1,a[1]),(a[0],a[1]+1)):
                if b in left:visit(left-{a,b},h+int(a[0]==b[0]))
        visit(set(product(range(rows),range(cols)))-holes,0)
        for h in range(rows*cols//2+1):
            assert o.domino_count({'rows':rows,'cols':cols,'holes':list(holes),'horizontal':h})==counts[h]


def test_hamilton_against_permutations():
    n=7;weights=[[None if a==b else (a*17+b*13)%11+1 for b in range(n)] for a in range(n)]
    data={'n':n,'weights':weights,'before':[[1,3],[2,5]]};candidates=[]
    for middle in permutations(range(1,n-1)):
        p=[0,*middle,n-1]
        if any(p.index(a)>p.index(b) for a,b in data['before']):continue
        candidates.append((sum(weights[a][b] for a,b in zip(p,p[1:])),p))
    cost,path=min(candidates)
    assert o.hamilton(data)=={'cost':cost,'path':path,'count':sum(c==cost for c,p in candidates)}


def test_selection_against_recursive_subsets():
    data={'items':[[3,2,4],[1,2,3],[4,1,7],[2,3,5],[1,1,2]],'requires':[[2,1]],'excludes':[[0,3]],'weight':7,'resource':6,'parity':1}
    all_sets=[c for r in range(6) for c in combinations(range(5),r)]
    good=[c for c in all_sets if sum(i%3==0 for i in c)%2==1 and not (2 in c and 1 not in c) and not (0 in c and 3 in c) and sum(data['items'][i][0] for i in c)<=7 and sum(data['items'][i][1] for i in c)<=6]
    ordered=sorted(good,key=lambda c:(-sum(data['items'][i][2] for i in c),sum(data['items'][i][0] for i in c),sum(data['items'][i][1] for i in c),c))
    result=o.constrained_selection(data)
    assert result['indices']==list(ordered[0]) and result['feasible_count']==len(good)


def test_adaptive_manual_and_public_knowledge_snapshots():
    assert o.adaptive_pairs({'left':[2],'right':[2],'pairs':2,'costs':[1,2]})==6
    assert o.adaptive_pairs({'left':[1,1],'right':[1,1],'pairs':1,'costs':[1,1]})==3
    # 逐观察值分组的独立实现，避免闭包引用错误、更新前后集合混淆。
    data={'low':2,'high':65,'announcements':[['SUM','OTHER_DONT'],['PRODUCT','KNOW'],['SUM','KNOW']]}
    worlds=set(combinations(range(2,66),2));counts=[]
    for speaker,claim in data['announcements']:
        groups={}
        other={}
        for a,b in worlds:
            own=a+b if speaker=='SUM' else a*b
            obs=a*b if speaker=='SUM' else a+b
            groups.setdefault(own,set()).add((a,b));other.setdefault(obs,set()).add((a,b))
        kept=set()
        for group in groups.values():
            if claim=='KNOW':ok=len(group)==1
            else:ok=all(len(other[a*b if speaker=='SUM' else a+b])>1 for a,b in group)
            if ok:kept|=group
        worlds=kept;counts.append(len(worlds))
    assert o.public_knowledge(data)=={'counts':counts,'worlds':[list(w) for w in sorted(worlds)]}


def test_reliability_by_transitive_closure():
    edges=[[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]
    data={'n':4,'edges':edges,'active':3,'degree_parity':[[1,1]]}
    given=connected=0;hist=Counter()
    for selected in combinations(edges,3):
        if sum(1 in e for e in selected)%2!=1:continue
        given+=1;reach=[[i==j for j in range(4)] for i in range(4)]
        for a,b in selected:reach[a][b]=reach[b][a]=True
        for k in range(4):
            for i in range(4):
                for j in range(4):reach[i][j]|=reach[i][k] and reach[k][j]
        size=sum(reach[0]);hist[size]+=1;connected+=size==4
    result=o.reliability(data)
    assert (result['given'],result['connected'],result['component_histogram'])==(given,connected,[[k,hist[k]] for k in sorted(hist)])


def test_challenge_reference_roundtrip_and_no_answer_leak():
    for item in reasoning_items():
        assert grade_reasoning(item,json.dumps(item.expected))['points']==20
        assert grade_reasoning(item,'{}')['points']==0
        assert json.dumps(item.expected,separators=(',',':')) not in item.prompt


def test_challenge_levels_and_time_budgets():
    assert TIMEOUT_BY_LEVEL == {'easy': 240.0, 'medium': 480.0, 'hard': 720.0, 'extreme': 960.0}
    assert [item.level for item in reasoning_items()] == ['easy', 'easy', 'medium', 'medium', 'hard', 'hard', 'extreme', 'extreme']


def test_time_score_half_budget_is_full_score_baseline():
    assert time_score_factor(0, 240) == 1.0
    assert time_score_factor(120_000, 240) == 1.0
    assert time_score_factor(180_000, 240) == 0.75
    assert time_score_factor(240_000, 240) == 0.5
    assert time_score_factor(300_000, 240) == 0.5


def test_time_score_keeps_content_score_and_random_salt_changes_prompt():
    grade = {'score10': 8.0}
    apply_time_score(grade, 180_000, 240)
    assert grade['score10_content'] == 8.0
    assert grade['time_score_factor'] == 0.75
    assert grade['score10'] == 6.0
    first = salt_prompt('题面', 'a')
    second = salt_prompt('题面', 'b')
    assert first != second
    assert salted_prompt_hash(first) != salted_prompt_hash(second)


def test_complex_coding_has_five_distinct_behavior_groups():
    """避免用同一批样例复制出 20 分，保持复杂需求的行为覆盖。"""
    for item_id in (f"CP-{i:02d}" for i in range(1, 9)):
        groups = challenge_cases(item_id)
        assert [len(group) for group in groups] == [4] * 5
        signatures = [
            json.dumps(batch[0].data, sort_keys=True, ensure_ascii=False)
            for group in groups
            for batch in group
        ]
        assert len(set(signatures)) == 20
