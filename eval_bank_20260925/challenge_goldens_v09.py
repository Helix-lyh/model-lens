"""Frozen challenge-09 overlays.

v09 adds one specified counter-conventional rule per CP item and puts a case
for it in every scoring group. Expected values are committed literals checked
by the independent oracle.
"""

from copy import deepcopy

from .challenge_goldens_v08 import golden_cases as previous_golden_cases


_NEW = {
    "CP-01": [
        ({'initial': {'a': 1}, 'events': [{'op': 'RESERVE', 'id': 'r', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'PAY', 'id': 'p', 'order': 'o'}, {'op': 'SHIP', 'id': 's', 'order': 'o'}, {'op': 'RETURN', 'id': 'bad', 'order': 'o', 'lines': [['a', 2]]}, {'op': 'RETURN', 'id': 'bad', 'order': 'o', 'lines': [['a', 1]]}]}, {'trace': ['OK', 'OK', 'OK', 'REJECT', 'DUP'], 'inventory': [], 'orders': [['o', 'SHIPPED', [['a', 1]]]]}),
        ({'initial': {'a': 3}, 'events': [{'op': 'RESERVE', 'id': 'r', 'order': 'o', 'lines': [['a', 3]]}, {'op': 'PAY', 'id': 'p', 'order': 'o'}, {'op': 'SHIP', 'id': 's', 'order': 'o'}, {'op': 'RETURN', 'id': 'x', 'order': 'o', 'lines': [['a', 2], ['a', -1]]}, {'op': 'RETURN', 'id': 'y', 'order': 'o', 'lines': [['a', 2], ['a', 1]]}]}, {'trace': ['OK', 'OK', 'OK', 'REJECT', 'OK'], 'inventory': [['a', 3]], 'orders': [['o', 'SHIPPED', []]]}),
        ({'initial': {'a': 1}, 'events': [{'op': 'RESERVE', 'id': 'r', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'PAY', 'id': 'p', 'order': 'o'}, {'op': 'RETURN', 'id': 'early', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'SHIP', 'id': 's', 'order': 'o'}, {'op': 'RETURN', 'id': 'ret', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'CANCEL', 'id': 'c', 'order': 'o'}]}, {'trace': ['OK', 'OK', 'INVALID', 'OK', 'OK', 'INVALID'], 'inventory': [['a', 1]], 'orders': [['o', 'SHIPPED', []]]}),
        ({'initial': {'a': 3, 'b': 3}, 'events': [{'op': 'RESERVE', 'id': 'r', 'order': 'o', 'lines': [['a', 2], ['b', 1]]}, {'op': 'PAY', 'id': 'p', 'order': 'o'}, {'op': 'SHIP', 'id': 's', 'order': 'o'}, {'op': 'RETURN', 'id': 'part', 'order': 'o', 'lines': [['a', 1]]}]}, {'trace': ['OK', 'OK', 'OK', 'OK'], 'inventory': [['a', 2], ['b', 2]], 'orders': [['o', 'SHIPPED', [['a', 1], ['b', 1]]]]}),
        ({'initial': {'a': 1}, 'events': [{'op': 'RESERVE', 'id': 'r', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'PAY', 'id': 'p', 'order': 'o'}, {'op': 'SHIP', 'id': 's', 'order': 'o'}, {'op': 'SNAPSHOT', 'id': 'snap'}, {'op': 'RETURN', 'id': 'ret', 'order': 'o', 'lines': [['a', 1]]}, {'op': 'RESTORE', 'id': 'back', 'snapshot': 'snap'}]}, {'trace': ['OK', 'OK', 'OK', 'SNAP', 'OK', 'RESTORE'], 'inventory': [], 'orders': [['o', 'SHIPPED', [['a', 1]]]]}),
    ],
    "CP-02": [
        ({'lease': 5, 'tasks': [{'id': 'a', 'priority': 1, 'ready': 0, 'max_attempts': 2}, {'id': 'b', 'priority': 9, 'ready': 0, 'max_attempts': 2, 'depends': ['a']}], 'events': [{'op': 'POLL', 'worker': 'w', 'now': 0}, {'op': 'ACK', 'worker': 'w', 'task': 'a', 'token': 'a:1', 'now': 1}, {'op': 'POLL', 'worker': 'w', 'now': 1}]}, {'trace': ['a:1', 'OK', 'b:1'], 'tasks': [['a', 'DONE', 1], ['b', 'RUNNING', 1]]}),
        ({'lease': 1, 'tasks': [{'id': 'a', 'priority': 1, 'ready': 0, 'max_attempts': 1}, {'id': 'b', 'priority': 5, 'ready': 0, 'max_attempts': 2, 'depends': ['a']}], 'events': [{'op': 'POLL', 'worker': 'w', 'now': 0}, {'op': 'TICK', 'now': 1}, {'op': 'POLL', 'worker': 'w', 'now': 1}]}, {'trace': ['a:1', 'OK', None], 'tasks': [['a', 'DEAD', 1], ['b', 'PENDING', 0]]}),
        ({'lease': 3, 'tasks': [{'id': 'a', 'priority': 1, 'ready': 0, 'max_attempts': 2}, {'id': 'b', 'priority': 5, 'ready': 0, 'max_attempts': 1, 'depends': ['a']}], 'events': [{'op': 'POLL', 'worker': 'w', 'now': 0}, {'op': 'POLL', 'worker': 'w', 'now': 3}, {'op': 'ACK', 'worker': 'w', 'task': 'a', 'token': 'a:1', 'now': 3}, {'op': 'POLL', 'worker': 'w2', 'now': 3}]}, {'trace': ['a:1', 'a:2', 'STALE', None], 'tasks': [['a', 'RUNNING', 2], ['b', 'PENDING', 0]]}),
        ({'lease': 5, 'tasks': [{'id': 'a', 'priority': 1, 'ready': 0, 'max_attempts': 1}, {'id': 'b', 'priority': 1, 'ready': 0, 'max_attempts': 2, 'depends': ['a']}], 'events': [{'op': 'POLL', 'worker': 'w', 'now': 0}, {'op': 'FAIL', 'worker': 'w', 'task': 'a', 'token': 'a:1', 'now': 1}, {'op': 'POLL', 'worker': 'w', 'now': 1}]}, {'trace': ['a:1', 'DEAD', None], 'tasks': [['a', 'DEAD', 1], ['b', 'PENDING', 0]]}),
        ({'lease': 4, 'tasks': [{'id': 'a', 'priority': 1, 'ready': 0, 'max_attempts': 2}, {'id': 'b', 'priority': 2, 'ready': 0, 'max_attempts': 2, 'depends': ['a']}], 'events': [{'op': 'CANCEL', 'task': 'a', 'now': 0}, {'op': 'POLL', 'worker': 'w', 'now': 0}, {'op': 'CANCEL', 'task': 'b', 'now': 1}]}, {'trace': ['OK', None, 'OK'], 'tasks': [['a', 'CANCELED', 0], ['b', 'CANCELED', 0]]}),
    ],
    "CP-03": [
        ({'roles': {'child': ['parent'], 'parent': []}, 'users': {'u': ['child']}, 'events': [['ADD', 'p', {'effect': 'allow', 'role': 'parent', 'action': 'read', 'resource': 'doc:*'}], ['CHECK', 'u', 'read', 'doc:1', 0], ['CHECK', 'u', 'read', 'doc:1:2', 0]]}, ['ALLOW', 'DENY']),
        ({'roles': {'r': []}, 'users': {'u': ['r']}, 'events': [['ADD', 'd', {'effect': 'deny', 'role': 'r', 'action': 'read', 'resource': 'doc:*'}], ['ADD', 'a', {'effect': 'allow', 'role': 'r', 'action': 'read', 'resource': '*'}], ['CHECK', 'u', 'read', 'doc:1', 0], ['CHECK', 'u', 'read', 'doc:1:2', 0]]}, ['DENY', 'ALLOW']),
        ({'roles': {'r': []}, 'users': {'u': ['r']}, 'events': [['ADD', 'w', {'effect': 'allow', 'role': 'r', 'action': 'read', 'resource': 'a:b:*'}], ['CHECK', 'u', 'read', 'a:b:c', 0], ['CHECK', 'u', 'read', 'a:b:c:d', 0], ['CHECK', 'u', 'read', 'a:b:', 0]]}, ['ALLOW', 'DENY', 'DENY']),
        ({'roles': {'r': []}, 'users': {'u': ['r']}, 'events': [['ADD', 'w', {'effect': 'allow', 'role': 'r', 'action': 'read', 'resource': 'doc:*', 'start': 0, 'end': 5}], ['CHECK', 'u', 'read', 'doc:1', 4], ['CHECK', 'u', 'read', 'doc:1', 5], ['CHECK', 'u', 'read', 'doc:1:2', 4]]}, ['ALLOW', 'DENY', 'DENY']),
        ({'roles': {'r': ['p'], 'p': []}, 'users': {'u': ['r']}, 'events': [['ADD', 'd', {'effect': 'deny', 'role': 'p', 'action': 'read', 'resource': 'doc:*'}], ['ADD', 'a', {'effect': 'allow', 'role': 'p', 'action': '*', 'resource': '*'}], ['CHECK', 'u', 'read', 'doc:1', 0], ['CHECK', 'u', 'read', 'doc:1:2', 0], ['SETROLE', 'r', []], ['CHECK', 'u', 'read', 'doc:1', 0], ['CHECK', 'u', 'read', 'doc:1:2', 0]]}, ['DENY', 'ALLOW', 'DENY', 'DENY']),
    ],
    "CP-04": [
        ({'environment': 'prod', 'base': {'api': {'port': 80, 'keep': 1}}, 'overlays': {'prod': {'api': {'port': 443}}}, 'dependencies': {}, 'changes': [{'id': 'a', 'service': 'api', 'env': '*', 'set': {'port': 1, 'debug': True}, 'delete': []}, {'id': 'b', 'service': 'api', 'env': 'prod', 'set': {'port': 8443}, 'delete': []}], 'rollback': []}, {'status': 'OK', 'order': ['a', 'b'], 'config': [['api', [['debug', True], ['keep', 1], ['port', 8443]]]], 'conflicts': []}),
        ({'environment': 'prod', 'base': {'api': {'p': 1}, 'web': {'v': 1}}, 'overlays': {}, 'dependencies': {'web': ['api']}, 'changes': [{'id': 's', 'service': 'api', 'env': '*', 'set': {'p': 2, 'extra': 1}, 'delete': []}, {'id': 't', 'service': 'api', 'env': 'prod', 'set': {'p': 3}, 'delete': []}, {'id': 'u', 'service': 'web', 'set': {'v': 2}, 'delete': []}], 'rollback': []}, {'status': 'OK', 'order': ['s', 't', 'u'], 'config': [['api', [['extra', 1], ['p', 3]]], ['web', [['v', 2]]]], 'conflicts': []}),
        ({'environment': 'prod', 'base': {'api': {'x': 0}}, 'overlays': {}, 'dependencies': {}, 'changes': [{'id': 's', 'service': 'api', 'env': 'prod', 'set': {'x': 9}, 'delete': []}, {'id': 'w', 'service': 'api', 'env': '*', 'set': {'x': 4}, 'delete': []}], 'rollback': ['s']}, {'status': 'OK', 'order': ['w'], 'config': [['api', [['x', 4]]]], 'conflicts': []}),
        ({'environment': 'prod', 'base': {'api': {'x': 0}}, 'overlays': {}, 'dependencies': {}, 'changes': [{'id': 'a', 'service': 'api', 'env': 'prod', 'set': {'x': 1}, 'delete': []}, {'id': 'b', 'service': 'api', 'env': 'prod', 'set': {'x': 2}, 'delete': []}, {'id': 'c', 'service': 'api', 'env': '*', 'set': {'x': 3}, 'delete': []}], 'rollback': []}, {'status': 'CONFLICT', 'order': ['a', 'b', 'c'], 'config': [], 'conflicts': [['a', 'b']]}),
        ({'environment': 'staging', 'base': {'api': {'x': 0, 'y': 1}, 'web': {'z': 1}}, 'overlays': {}, 'dependencies': {}, 'changes': [{'id': 'a', 'service': 'api', 'env': '*', 'set': {'x': 5, 'y': 9}, 'delete': []}, {'id': 'b', 'service': 'api', 'env': 'staging', 'set': {'x': 7}, 'delete': []}, {'id': 'c', 'service': 'web', 'env': '*', 'set': {'z': 2}, 'delete': []}], 'rollback': []}, {'status': 'OK', 'order': ['a', 'b', 'c'], 'config': [['api', [['x', 7], ['y', 9]]], ['web', [['z', 2]]]], 'conflicts': []}),
    ],
    "CP-05": [
        ({'accounts': {'a': 10, 'b': 0}, 'treasury': 'fee', 'events': [['BATCH', 'b1', [['t', 'a', 'b', 3, 1]]], ['REVERSE', 'r1', 't'], ['BATCH', 'bad', [['t', 'a', 'b', 3, 1], ['t2', 'a', 'missing', 1, 0]]], ['BATCH', 'b3', [['t', 'a', 'b', 3, 1]]]]}, {'trace': ['OK', 'OK', 'REJECT', 'OK'], 'balances': [['a', 6], ['b', 3], ['fee', 1]], 'transactions': [['t', 'SETTLED']]}),
        ({'accounts': {'a': 10, 'b': 0}, 'treasury': 'fee', 'events': [['BATCH', 'b1', [['t', 'a', 'b', 3, 1]]], ['REVERSE', 'r1', 't'], ['REVERSE', 'r1', 't'], ['BATCH', 'b2', [['t', 'a', 'b', 4, 0]]]]}, {'trace': ['OK', 'OK', 'DUP', 'OK'], 'balances': [['a', 6], ['b', 4]], 'transactions': [['t', 'SETTLED']]}),
        ({'accounts': {'a': 10, 'b': 0}, 'treasury': 'fee', 'events': [['BATCH', 'b1', [['t', 'a', 'b', 3, 1]]], ['REVERSE', 'r1', 't'], ['BATCH', 'b2', [['t', 'a', 'b', 3, 2]]]]}, {'trace': ['OK', 'OK', 'OK'], 'balances': [['a', 5], ['b', 3], ['fee', 2]], 'transactions': [['t', 'SETTLED']]}),
        ({'accounts': {'a': 10, 'b': 0, 'c': 0}, 'treasury': 'fee', 'events': [['BATCH', 'b1', [['t1', 'a', 'b', 3, 1]]], ['BATCH', 'b2', [['t2', 'b', 'c', 3, 0]]], ['REVERSE', 'r1', 't1'], ['BATCH', 'b3', [['t1', 'a', 'b', 1, 0]]]]}, {'trace': ['OK', 'OK', 'INVALID', 'REJECT'], 'balances': [['a', 6], ['c', 3], ['fee', 1]], 'transactions': [['t1', 'SETTLED'], ['t2', 'SETTLED']]}),
        ({'accounts': {'a': 4, 'b': 0}, 'treasury': 'fee', 'events': [['BATCH', 'b1', [['t', 'a', 'b', 3, 1]]], ['REVERSE', 'r1', 't'], ['BATCH', 'b2', [['t', 'a', 'b', 4, 0]]]]}, {'trace': ['OK', 'OK', 'OK'], 'balances': [['b', 4]], 'transactions': [['t', 'SETTLED']]}),
    ],
    "CP-06": [
        ({'window': 10, 'events': [['INGEST', 'e', 'a', 1, 3], ['SEAL', 's', 'a', 1], ['INGEST', 'e', 'a', 1, 9], ['INGEST', 'e2', 'a', 2, 4], ['QUERY', 'a', 1]]}, [{'entity': 'a', 'start': 0, 'count': 1, 'sum': 3, 'ids': ['e']}]),
        ({'window': 10, 'events': [['INGEST', 'e', 'a', -1, 4], ['SEAL', 's', 'a', -3], ['QUERY', 'a', -1], ['INGEST', 'late', 'a', -2, 1], ['QUERY', 'a', -1], ['INGEST', 'next', 'a', 0, 5], ['QUERY', 'a', 0]]}, [{'entity': 'a', 'start': -10, 'count': 1, 'sum': 4, 'ids': ['e']}, {'entity': 'a', 'start': -10, 'count': 1, 'sum': 4, 'ids': ['e']}, {'entity': 'a', 'start': 0, 'count': 1, 'sum': 5, 'ids': ['next']}]),
        ({'window': 10, 'events': [['INGEST', 'e', 'a', 15, 2], ['SEAL', 's', 'a', 15], ['INGEST', 'f', 'a', 12, 9], ['INGEST', 'g', 'b', 12, 1], ['QUERY', 'a', 15], ['QUERY', 'b', 12]]}, [{'entity': 'a', 'start': 10, 'count': 1, 'sum': 2, 'ids': ['e']}, {'entity': 'b', 'start': 10, 'count': 1, 'sum': 1, 'ids': ['g']}]),
        ({'window': 10, 'events': [['INGEST', 'e', 'a', 1, 3], ['SEAL', 's', 'a', 1], ['RETRACT', 'r', 'e'], ['AMEND', 'm', 'e', 25, 8], ['QUERY', 'a', 1], ['QUERY', 'a', 25]]}, [{'entity': 'a', 'start': 0, 'count': 0, 'sum': 0, 'ids': []}, {'entity': 'a', 'start': 20, 'count': 0, 'sum': 0, 'ids': []}]),
        ({'window': 10, 'events': [['INGEST', 'e', 'a', 1, 3], ['INGEST', 'f', 'b', 5, 1], ['SEAL', 'seal', 'a', 1], ['INGEST', 'g', 'a', 2, 9], ['INGEST', 'h', 'b', 21, 4], ['SNAPSHOT']]}, [[{'entity': 'a', 'start': 0, 'count': 1, 'sum': 3, 'ids': ['e']}, {'entity': 'b', 'start': 0, 'count': 1, 'sum': 1, 'ids': ['f']}, {'entity': 'b', 'start': 20, 'count': 1, 'sum': 4, 'ids': ['h']}]]),
    ],
    "CP-07": [
        ({'workers': 1, 'resources': {}, 'budgets': {'p': 2}, 'jobs': [{'id': 'a', 'release': 0, 'duration': 2, 'priority': 1, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'p'}, {'id': 'b', 'release': 0, 'duration': 2, 'priority': 5, 'deadline': 10, 'needs': [], 'deps': ['a'], 'pool': 'p'}], 'cancel': []}, {'schedule': [['a', 0, 2, 0, False]], 'states': [['a', 'DONE'], ['b', 'PENDING']]}),
        ({'workers': 2, 'resources': {'gpu': 1}, 'budgets': {'gpu': 3}, 'jobs': [{'id': 'a', 'release': 0, 'duration': 2, 'priority': 2, 'deadline': 10, 'needs': ['gpu'], 'deps': [], 'pool': 'gpu'}, {'id': 'b', 'release': 0, 'duration': 2, 'priority': 1, 'deadline': 10, 'needs': ['gpu'], 'deps': [], 'pool': 'gpu'}], 'cancel': []}, {'schedule': [['a', 0, 2, 0, False]], 'states': [['a', 'DONE'], ['b', 'PENDING']]}),
        ({'workers': 1, 'resources': {}, 'budgets': {'gpu': 2}, 'jobs': [{'id': 'a', 'release': 0, 'duration': 3, 'priority': 5, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'gpu'}, {'id': 'b', 'release': 0, 'duration': 2, 'priority': 1, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'gpu'}], 'cancel': []}, {'schedule': [['b', 0, 2, 0, False]], 'states': [['a', 'PENDING'], ['b', 'DONE']]}),
        ({'workers': 1, 'resources': {}, 'budgets': {'cpu': 2}, 'jobs': [{'id': 'a', 'release': 0, 'duration': 2, 'priority': 1, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'cpu'}, {'id': 'b', 'release': 0, 'duration': 2, 'priority': 3, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'cpu'}, {'id': 'c', 'release': 0, 'duration': 2, 'priority': 0, 'deadline': 10, 'needs': [], 'deps': [], 'pool': 'cpu'}], 'cancel': [{'id': 'b', 'time': 0}]}, {'schedule': [['a', 0, 2, 0, False]], 'states': [['a', 'DONE'], ['b', 'CANCELED'], ['c', 'PENDING']]}),
        ({'workers': 1, 'resources': {}, 'budgets': {'cpu': 2}, 'jobs': [{'id': 'a', 'release': 0, 'duration': 2, 'priority': 1, 'deadline': 1, 'needs': [], 'deps': [], 'pool': 'cpu'}, {'id': 'b', 'release': 0, 'duration': 2, 'priority': 9, 'deadline': 1, 'needs': [], 'deps': [], 'pool': 'cpu'}], 'cancel': []}, {'schedule': [['b', 0, 2, 0, True]], 'states': [['a', 'PENDING'], ['b', 'DONE']]}),
    ],
    "CP-08": [
        ({'facts': {'x': 1}, 'rules': [{'id': 'a', 'phase': 'main', 'priority': 2, 'when': {'op': 'exists', 'field': 'x'}, 'set': {'x': 3}, 'add': {}, 'remove': []}, {'id': 'b', 'phase': 'main', 'priority': 1, 'when': {'all': [{'op': 'changed', 'field': 'x'}, {'op': 'gte', 'field': 'x', 'value': 3}]}, 'set': {'ok': True}, 'add': {}, 'remove': []}]}, {'facts': [['ok', True], ['x', 3]], 'fired': ['a', 'b'], 'conflicts': [], 'stopped': False}),
        ({'facts': {'x': 1}, 'rules': [{'id': 'p', 'phase': 'pre', 'priority': 1, 'when': {'op': 'exists', 'field': 'x'}, 'set': {'x': 2}, 'add': {}, 'remove': []}, {'id': 'm', 'phase': 'main', 'priority': 1, 'when': {'op': 'changed', 'field': 'x'}, 'set': {'bad': True}, 'add': {}, 'remove': []}]}, {'facts': [['x', 2]], 'fired': ['p'], 'conflicts': [], 'stopped': False}),
        ({'facts': {'x': 1}, 'rules': [{'id': 'a', 'phase': 'main', 'priority': 3, 'when': {'op': 'exists', 'field': 'x'}, 'set': {}, 'add': {}, 'remove': ['x']}, {'id': 'b', 'phase': 'main', 'priority': 2, 'when': {'op': 'changed', 'field': 'x'}, 'set': {'x': 1}, 'add': {}, 'remove': []}, {'id': 'c', 'phase': 'main', 'priority': 1, 'when': {'op': 'changed', 'field': 'x'}, 'set': {'bad': True}, 'add': {}, 'remove': []}]}, {'facts': [['x', 1]], 'fired': ['a', 'b'], 'conflicts': [], 'stopped': False}),
        ({'facts': {'tags': ['a']}, 'rules': [{'id': 'a', 'phase': 'main', 'priority': 3, 'when': {'op': 'exists', 'field': 'tags'}, 'set': {}, 'add': {'tags': 'b'}, 'remove': []}, {'id': 'b', 'phase': 'main', 'priority': 2, 'when': {'op': 'changed', 'field': 'tags'}, 'set': {'tags': ['a']}, 'add': {}, 'remove': []}, {'id': 'c', 'phase': 'main', 'priority': 1, 'when': {'op': 'changed', 'field': 'tags'}, 'set': {'bad': True}, 'add': {}, 'remove': []}]}, {'facts': [['tags', ['a']]], 'fired': ['a', 'b'], 'conflicts': [], 'stopped': False}),
        ({'facts': {'x': 1}, 'rules': [{'id': 'a', 'phase': 'main', 'priority': 2, 'when': {'op': 'exists', 'field': 'x'}, 'set': {}, 'add': {}, 'remove': ['x']}, {'id': 'b', 'phase': 'main', 'priority': 1, 'when': {'op': 'changed', 'field': 'x'}, 'set': {'x': 1}, 'add': {}, 'remove': []}, {'id': 'c', 'phase': 'post', 'priority': 1, 'when': {'op': 'changed', 'field': 'x'}, 'set': {'seen': True}, 'add': {}, 'remove': []}]}, {'facts': [['x', 1]], 'fired': ['a', 'b'], 'conflicts': [], 'stopped': False}),
    ],
}

_EXPECT = {
    "CP-04": {
        (1, 0): {'status': 'OK', 'order': ['a', 'b'], 'config': [['api', [['x', 3]]]], 'conflicts': []},
    },
    "CP-08": {
        (0, 0): {'facts': [['tags', []], ['x', 4]], 'fired': ['p', 'm2'], 'conflicts': [], 'stopped': False},
        (2, 0): {'facts': [['bad', True], ['x', 1], ['z', 1]], 'fired': ['a', 'b'], 'conflicts': [], 'stopped': False},
        (3, 0): {'facts': [], 'fired': ['a'], 'conflicts': [], 'stopped': False},
        (4, 0): {'facts': [['tags', ['x']]], 'fired': ['a'], 'conflicts': [], 'stopped': False},
    },
}


def golden_cases(item_id):
    groups = previous_golden_cases(item_id)
    for (group, index), expected in _EXPECT.get(item_id, {}).items():
        data = groups[group][index][0]
        groups[group][index] = (deepcopy(data), deepcopy(expected))
    for index, (data, expected) in enumerate(_NEW.get(item_id, ())):
        groups[index][3] = (deepcopy(data), deepcopy(expected))
    return groups
