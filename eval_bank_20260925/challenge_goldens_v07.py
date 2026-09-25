"""Frozen challenge-07 overlays for the new history-coupled behaviors.

The unchanged cases are reused from challenge-06.  One independently authored
case in every scoring group exercises the new operation, so a solver that only
implements the old contract cannot receive a pass by relying on the old 16
cases.
"""

from copy import deepcopy

from .challenge_goldens_v06 import golden_cases as previous_golden_cases


_UPGRADES = {
    "CP-01": [
        ({"initial": {"a": 3}, "events": [{"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]}, {"op": "SNAPSHOT", "id": "s"}, {"op": "PAY", "id": "p", "order": "o"}, {"op": "RESTORE", "id": "x", "snapshot": "s"}]}, {"trace": ["OK", "SNAP", "OK", "RESTORE"], "inventory": [["a", 2]], "orders": [["o", "RESERVED", [["a", 1]]]]}),
        ({"initial": {"a": 2}, "events": [{"op": "SNAPSHOT", "id": "s"}, {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]}, {"op": "RESTORE", "id": "x", "snapshot": "s"}, {"op": "RESERVE", "id": "r2", "order": "p", "lines": [["a", 1]]}]}, {"trace": ["SNAP", "OK", "RESTORE", "OK"], "inventory": [["a", 1]], "orders": [["p", "RESERVED", [["a", 1]]]]}),
        ({"initial": {"a": 2}, "events": [{"op": "SNAPSHOT", "id": "s"}, {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]}, {"op": "RESTORE", "id": "x", "snapshot": "missing"}, {"op": "RESTORE", "id": "y", "snapshot": "s"}]}, {"trace": ["SNAP", "OK", "INVALID", "RESTORE"], "inventory": [["a", 2]], "orders": []}),
        ({"initial": {"a": 2}, "events": [{"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]}, {"op": "SNAPSHOT", "id": "s"}, {"op": "CANCEL", "id": "c", "order": "o"}, {"op": "RESTORE", "id": "x", "snapshot": "s"}, {"op": "CANCEL", "id": "c2", "order": "o"}]}, {"trace": ["OK", "SNAP", "OK", "RESTORE", "OK"], "inventory": [["a", 2]], "orders": [["o", "CANCELED", []]]}),
        ({"initial": {"a": 1}, "events": [{"op": "SNAPSHOT", "id": "s"}, {"op": "RESTORE", "id": "x", "snapshot": "s"}, {"op": "RESTORE", "id": "x", "snapshot": "s"}]}, {"trace": ["SNAP", "RESTORE", "DUP"], "inventory": [["a", 1]], "orders": []}),
    ],
    "CP-03": [
        ({"roles": {"admin": ["base"], "base": []}, "users": {"u": ["admin"]}, "events": [["ADD", "r", {"effect": "allow", "role": "base", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["SETROLE", "admin", []], ["CHECK", "u", "read", "x", 0]]}, ["ALLOW", "DENY"]),
        ({"roles": {"r": ["p"], "p": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "p", "action": "read", "resource": "x"}], ["SETROLE", "r", []], ["CHECK", "u", "read", "x", 0], ["SETROLE", "r", ["p"]], ["CHECK", "u", "read", "x", 0]]}, ["DENY", "ALLOW"]),
        ({"roles": {"a": ["b"], "b": ["a"]}, "users": {"u": ["a"]}, "events": [["ADD", "x", {"effect": "allow", "role": "b", "action": "*", "resource": "*"}], ["CHECK", "u", "read", "x", 0], ["SETROLE", "a", []], ["CHECK", "u", "read", "x", 0]]}, ["ALLOW", "DENY"]),
        ({"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["SETROLE", "r", ["missing"]], ["CHECK", "u", "read", "x", 0], ["SETROLE", "r", []], ["CHECK", "u", "read", "x", 0]]}, ["ALLOW", "ALLOW"]),
        ({"roles": {"a": [], "b": []}, "users": {"u": ["a"]}, "events": [["ADD", "x", {"effect": "allow", "role": "b", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["SETROLE", "a", ["b"]], ["CHECK", "u", "read", "x", 0], ["SETROLE", "a", []], ["CHECK", "u", "read", "x", 0]]}, ["DENY", "ALLOW", "DENY"]),
    ],
    "CP-06": [
        ({"window": 10, "events": [["INGEST", "e", "a", 1, 3], ["AMEND", "m", "e", 11, 7], ["QUERY", "a", 1], ["QUERY", "a", 11]]}, [{"entity": "a", "start": 0, "count": 0, "sum": 0, "ids": []}, {"entity": "a", "start": 10, "count": 1, "sum": 7, "ids": ["e"]}]),
        ({"window": 5, "events": [["INGEST", "e", "a", 1, 3], ["AMEND", "m", "unknown", 2, 8], ["QUERY", "a", 1], ["AMEND", "m", "e", 9, 4], ["QUERY", "a", 9]]}, [{"entity": "a", "start": 0, "count": 1, "sum": 3, "ids": ["e"]}, {"entity": "a", "start": 5, "count": 0, "sum": 0, "ids": []}]),
        ({"window": 4, "events": [["INGEST", "e", "a", 1, 3], ["RETRACT", "r", "e"], ["AMEND", "m", "e", 9, 8], ["QUERY", "a", 1], ["SNAPSHOT"]]}, [{"entity": "a", "start": 0, "count": 0, "sum": 0, "ids": []}, []]),
        ({"window": 10, "events": [["INGEST", "e", "a", 1, 3], ["AMEND", "m", "e", 11, 4], ["AMEND", "m2", "e", 2, 9], ["SNAPSHOT"]]}, [[{"entity": "a", "start": 0, "count": 1, "sum": 9, "ids": ["e"]}]]),
        ({"window": 3, "events": [["INGEST", "e", "a", 0, 1], ["AMEND", "m", "e", -4, 5], ["QUERY", "a", -4], ["AMEND", "m2", "e", 2, 6], ["QUERY", "a", 2]]}, [{"entity": "a", "start": -6, "count": 1, "sum": 5, "ids": ["e"]}, {"entity": "a", "start": 0, "count": 1, "sum": 6, "ids": ["e"]}]),
    ],
    "CP-07": [
        ({"workers": 1, "resources": {}, "blackouts": [[0, 3]], "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 5, "needs": [], "deps": []}], "cancel": []}, {"schedule": [["a", 3, 5, 0, False]], "states": [["a", "DONE"]]}),
        ({"workers": 1, "resources": {}, "blackouts": [[1, 4]], "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 5, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 2, "deadline": 5, "needs": [], "deps": []}], "cancel": []}, {"schedule": [["b", 0, 1, 0, False], ["a", 4, 6, 0, True]], "states": [["a", "DONE"], ["b", "DONE"]]}),
        ({"workers": 1, "resources": {}, "blackouts": [[0, 10]], "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 5, "needs": [], "deps": []}], "cancel": []}, {"schedule": [["a", 10, 12, 0, True]], "states": [["a", "DONE"]]}),
        ({"workers": 1, "resources": {}, "blackouts": [[2, 5]], "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 5, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 2, "priority": 1, "deadline": 8, "needs": [], "deps": []}], "cancel": []}, {"schedule": [["a", 0, 2, 0, False], ["b", 5, 7, 0, False]], "states": [["a", "DONE"], ["b", "DONE"]]}),
        ({"workers": 1, "resources": {}, "blackouts": [[0, 2], [3, 9]], "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 9, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 2, "priority": 1, "deadline": 12, "needs": [], "deps": []}], "cancel": []}, {"schedule": [["a", 2, 3, 0, False], ["b", 9, 11, 0, False]], "states": [["a", "DONE"], ["b", "DONE"]]}),
    ],
    "CP-08": [
        ({"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 2, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "changed", "field": "x"}, "set": {"seen": True}, "add": {}, "remove": []}]}, {"facts": [["seen", True], ["x", 2]], "fired": ["a", "b"], "conflicts": [], "stopped": False}),
        ({"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "eq", "field": "x", "value": 1}, "set": {}, "add": {"tags": "a"}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "changed", "field": "tags"}, "set": {"seen": True}, "add": {}, "remove": []}]}, {"facts": [["seen", True], ["tags", ["a"]], ["x", 1]], "fired": ["a", "b"], "conflicts": [], "stopped": False}),
        ({"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "changed", "field": "x"}, "set": {"bad": True}, "add": {}, "remove": []}]}, {"facts": [["x", 1]], "fired": [], "conflicts": [], "stopped": False}),
        ({"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {}, "add": {}, "remove": ["x"]}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "changed", "field": "x"}, "set": {"removed": True}, "add": {}, "remove": []}]}, {"facts": [["removed", True]], "fired": ["a", "b"], "conflicts": [], "stopped": False}),
        ({"facts": {"tags": []}, "rules": [{"id": "a", "phase": "pre", "priority": 1, "when": {"op": "exists", "field": "tags"}, "set": {}, "add": {"tags": "x"}, "remove": []}, {"id": "b", "phase": "main", "priority": 1, "when": {"all": [{"op": "changed", "field": "tags"}, {"op": "contains", "field": "tags", "value": "x"}]}, "set": {"ok": True}, "add": {}, "remove": []}]}, {"facts": [["ok", True], ["tags", ["x"]]], "fired": ["a", "b"], "conflicts": [], "stopped": False}),
    ],
}


def golden_cases(item_id):
    groups = previous_golden_cases(item_id)
    for index, (data, expected) in enumerate(_UPGRADES.get(item_id, ())):
        groups[index][0] = (deepcopy(data), deepcopy(expected))
    return groups
