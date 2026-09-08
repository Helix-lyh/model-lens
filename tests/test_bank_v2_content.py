"""Offline v2 reference/negative tests using the real isolated fixture runner."""
import copy
import itertools
import json
from pathlib import Path

import pytest
import yaml

from src.bank import load_questions, RAW_MATRIX
from src.grade import grade_response, run_python_sandbox

ROOT = Path(__file__).resolve().parents[1]
RAW = yaml.safe_load((ROOT / 'bank/questions.yaml').read_text())
NEW = [q for q in RAW if str(q.get('metadata', {}).get('version') or '') == '2026090901']


def encoded(q):
    return json.dumps(q['metadata']['reference_answer'], ensure_ascii=False, separators=(',', ':'))


def run(q, payload):
    return run_python_sandbox('', ROOT / q['grader']['tests_file'], payload=payload)[0]


def test_counts():
    qs = load_questions()
    assert len(RAW) == 54 and len(qs) == 78 and len(NEW) == 25
    assert sum(q['metadata']['construct'] == 'instruction_following' for q in NEW) == 8
    for domain, row in RAW_MATRIX.items():
        for difficulty, count in row.items():
            assert sum(q['domain'] == domain and q['difficulty'] == difficulty for q in RAW) == count


@pytest.mark.parametrize('q', NEW, ids=lambda q: q['id'])
def test_reference_in_real_sandbox_and_grader(q):
    assert run(q, encoded(q)) == 'pass'
    obj = next(x for x in load_questions() if x.id == q['id'])
    assert grade_response(obj, encoded(q), repo_root=ROOT).passed is True


@pytest.mark.parametrize('q', NEW, ids=lambda q: q['id'])
def test_each_field_negative_and_schema(q):
    answer = q['metadata']['reference_answer']
    for key in answer:
        bad = copy.deepcopy(answer)
        bad[key] = None
        assert run(q, json.dumps(bad, ensure_ascii=False, separators=(',', ':'))) == 'fail'
    assert run(q, json.dumps(q['metadata']['negative_example'], ensure_ascii=False)) == 'fail'
    assert run(q, encoded(q)[:-1] + ',"extra":0}') == 'fail'
    key = next(iter(answer))
    assert run(q, encoded(q)[:-1] + ',' + json.dumps(key) + ':null}') == 'fail'


@pytest.mark.parametrize('q', NEW, ids=lambda q: q['id'])
def test_nested_type_and_protocol(q):
    def corrupt(value):
        if isinstance(value, dict):
            return {k: corrupt(v) for k, v in value.items()}
        if isinstance(value, list):
            return [corrupt(v) for v in value]
        if type(value) is bool:
            return int(value)
        if type(value) is int:
            return str(value)
        return None
    assert run(q, json.dumps(corrupt(q['metadata']['reference_answer']))) == 'fail'
    obj = next(x for x in load_questions() if x.id == q['id'])
    if q['grader'].get('strict_response'):
        for payload in (' ' + encoded(q), encoded(q) + '\n', '```json\n' + encoded(q) + '\n```'):
            assert run(q, payload) == 'fail'
            assert grade_response(obj, payload, repo_root=ROOT).passed is False
    else:
        assert grade_response(obj, '```json\n' + encoded(q) + '\n```', repo_root=ROOT).passed is True
        reversed_keys = dict(reversed(list(q['metadata']['reference_answer'].items())))
        assert run(q, json.dumps(reversed_keys, ensure_ascii=False)) == 'pass'


def test_independent_knapsack_oracle():
    items = [(4, 7), (5, 9), (6, 12), (3, 5), (2, 4)]
    def optimum(removed):
        candidates = []
        for flags in itertools.product((False, True), repeat=5):
            chosen = [i for i in range(5) if flags[i]]
            weight = sum(items[i][0] for i in chosen)
            if weight > 10 or (1 in chosen and 4 not in chosen):
                continue
            if not removed and 0 in chosen and 2 in chosen:
                continue
            candidates.append((-sum(items[i][1] for i in chosen), weight, chosen))
        value, _, chosen = min(candidates)
        return chosen, -value
    q = next(q for q in NEW if q['id'] == 'reasoning-extreme-01')
    a = q['metadata']['reference_answer']
    assert optimum(False) == (a['base_indices'], a['base_value'])
    assert optimum(True) == (a['changed_indices'], a['changed_value'])


def test_independent_path_oracle():
    edges = [('A','B',2), ('A','C',1), ('C','B',1), ('B','D',3), ('C','D',4), ('B','E',1), ('E','D',2)]
    def paths(removed):
        found = []
        def visit(path, cost):
            if path[-1] == 'D':
                found.append((cost, path)); return
            for x, y, w in edges:
                if removed and (x,y) == ('B','D'):
                    continue
                if x == path[-1] and y not in path:
                    visit(path+[y], cost+w)
        visit(['A'], 0)
        best = min(cost for cost, _ in found)
        winners = sorted(path for cost, path in found if cost == best)
        return winners[0], best, len(winners)
    a = next(q for q in NEW if q['id'] == 'reasoning-extreme-05')['metadata']['reference_answer']
    assert paths(False) == (a['path'], a['cost'], a['count'])
    assert paths(True) == (a['changed_path'], a['changed_cost'], a['changed_count'])
