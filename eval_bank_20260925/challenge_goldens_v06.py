"""Frozen challenge-06 coding cases.

The cases are authored as small, cross-state workflows and their expected
values are frozen from the independent oracle module.  Runtime scoring never
executes a reference implementation to manufacture expected values.
"""

from copy import deepcopy

from .challenge_coding_oracles import ORACLES


def _cases():
    return {
        "CP-01": [
            [
                {"initial": {"a": 4, "b": 2}, "events": [
                    {"op": "RESERVE", "id": "r1", "order": "o1", "lines": [["a", 1], ["a", 1]]},
                    {"op": "PAY", "id": "p1", "order": "o1"},
                    {"op": "CANCEL", "id": "c1", "order": "o1"},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 3], ["b", 1]]},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]},
                    {"op": "RESERVE", "id": "r", "order": "o2", "lines": [["a", 1]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 2]]},
                ]},
                {"initial": {"a": 3}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]},
                    {"op": "SHIP", "id": "s", "order": "o"},
                    {"op": "PAY", "id": "p", "order": "o"},
                    {"op": "SHIP", "id": "s2", "order": "o"},
                ]},
                {"initial": {"a": 1}, "events": [
                    {"op": "RESERVE", "id": "bad", "order": "o", "lines": [["a", 2], ["b", 1]]},
                    {"op": "RESERVE", "id": "bad", "order": "o2", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "o2"},
                ]},
            ],
            [
                {"initial": {"a": 5}, "events": [
                    {"op": "RESERVE", "id": "r1", "order": "a", "lines": [["a", 2]]},
                    {"op": "RESERVE", "id": "r2", "order": "b", "lines": [["a", 2]]},
                    {"op": "CANCEL", "id": "c1", "order": "a"},
                    {"op": "RESERVE", "id": "r3", "order": "c", "lines": [["a", 2]]},
                ]},
                {"initial": {"x": 1}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["x", 1]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "o", "lines": [["x", 1]]},
                ]},
                {"initial": {"a": 3}, "events": [
                    {"op": "RESERVE", "id": "r1", "order": "z", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "r2", "order": "y", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "z"},
                    {"op": "CANCEL", "id": "c", "order": "z"},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1], ["a", -1]]},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "o2"},
                ]},
            ],
            [
                {"initial": {"a": 3}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "o"},
                    {"op": "SHIP", "id": "s", "order": "o"},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "PAY", "id": "p2", "order": "o"},
                ]},
                {"initial": {"a": 4}, "events": [
                    {"op": "RESERVE", "id": "r1", "order": "o1", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 1]]},
                    {"op": "CANCEL", "id": "c1", "order": "o1"},
                    {"op": "PAY", "id": "p2", "order": "o2"},
                ]},
                {"initial": {"a": 2, "b": 2}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1], ["b", 2]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "p", "lines": [["a", 2], ["b", 1]]},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "o"},
                    {"op": "PAY", "id": "p2", "order": "o"},
                    {"op": "SHIP", "id": "s", "order": "o"},
                ]},
            ],
            [
                {"initial": {"a": 3}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 3]]},
                    {"op": "PAY", "id": "p", "order": "o2"},
                ]},
                {"initial": {"a": 3}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 2]]},
                    {"op": "CANCEL", "id": "c2", "order": "o2"},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "r1", "order": "b", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "r2", "order": "a", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "p", "order": "a"},
                    {"op": "SHIP", "id": "s", "order": "a"},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "r2", "order": "o", "lines": [["a", 1]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r3", "order": "o", "lines": [["a", 1]]},
                ]},
            ],
            [
                {"initial": {"a": 5, "b": 3}, "events": [
                    {"op": "RESERVE", "id": "1", "order": "o1", "lines": [["a", 2], ["b", 1]]},
                    {"op": "PAY", "id": "2", "order": "o1"},
                    {"op": "RESERVE", "id": "3", "order": "o2", "lines": [["a", 2]]},
                    {"op": "CANCEL", "id": "4", "order": "o1"},
                    {"op": "SHIP", "id": "5", "order": "o2"},
                ]},
                {"initial": {"a": 2}, "events": [
                    {"op": "RESERVE", "id": "1", "order": "o", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "2", "order": "o"},
                    {"op": "CANCEL", "id": "3", "order": "o"},
                    {"op": "RESERVE", "id": "4", "order": "p", "lines": [["a", 2]]},
                ]},
                {"initial": {"a": 4}, "events": [
                    {"op": "RESERVE", "id": "1", "order": "o", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "2", "order": "p", "lines": [["a", 1]]},
                    {"op": "PAY", "id": "3", "order": "p"},
                    {"op": "SHIP", "id": "4", "order": "p"},
                    {"op": "CANCEL", "id": "5", "order": "o"},
                ]},
                {"initial": {"a": 1}, "events": [
                    {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
                    {"op": "RESERVE", "id": "r", "order": "o2", "lines": [["a", 1]]},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "CANCEL", "id": "c", "order": "o"},
                    {"op": "RESERVE", "id": "r2", "order": "o2", "lines": [["a", 1]]},
                ]},
            ],
        ],
        "CP-03": [
            [
                {"roles": {"root": ["a"], "a": ["b"], "b": ["root"]}, "users": {"u": ["root"]}, "events": [["ADD", "wide", {"effect": "allow", "role": "b", "action": "*", "resource": "doc:*"}], ["ADD", "deny", {"effect": "deny", "role": "a", "action": "read", "resource": "doc:1"}], ["CHECK", "u", "read", "doc:1", 0], ["REMOVE", "deny"], ["CHECK", "u", "read", "doc:1", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "*", "resource": "doc:*"}], ["ADD", "y", {"effect": "allow", "role": "r", "action": "read", "resource": "doc:1"}], ["CHECK", "u", "read", "doc:1", 0], ["CHECK", "u", "write", "doc:1", 0], ["CHECK", "u", "read", "doc:2", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "read", "resource": "x", "start": 2, "end": 4}], ["CHECK", "u", "read", "x", 1], ["CHECK", "u", "read", "x", 2], ["CHECK", "u", "read", "x", 4], ["ADD", "x", {"effect": "deny", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 3]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "*", "resource": "*"}], ["ADD", "y", {"effect": "deny", "role": "r", "action": "write", "resource": "*"}], ["CHECK", "u", "write", "z", 0], ["CHECK", "u", "read", "z", 0]]},
            ],
            [
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "read", "resource": "prefix*"}], ["CHECK", "u", "read", "prefix", 0], ["CHECK", "u", "read", "prefix/a", 0], ["REMOVE", "x"], ["CHECK", "u", "read", "prefix/a", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "x", {"effect": "allow", "role": "r", "action": "*", "resource": "*"}], ["REMOVE", "missing"], ["CHECK", "u", "read", "x", 0], ["ADD", "x", {"effect": "deny", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x", "start": 0}], ["CHECK", "u", "read", "x", -1], ["CHECK", "u", "read", "x", 0], ["CHECK", "u", "read", "x", 999]]},
                {"roles": {"r": ["unknown"]}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "unknown", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["CHECK", "u", "write", "x", 0]]},
            ],
            [
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["ADD", "b", {"effect": "deny", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["REMOVE", "a"], ["CHECK", "u", "read", "x", 0], ["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0]]},
                {"roles": {"parent": ["child"], "child": []}, "users": {"u": ["parent"]}, "events": [["ADD", "a", {"effect": "deny", "role": "child", "action": "read", "resource": "x"}], ["ADD", "b", {"effect": "allow", "role": "parent", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["CHECK", "u", "write", "x", 0]]},
                {"roles": {"a": ["b"], "b": ["c"], "c": ["a"]}, "users": {"u": ["a"]}, "events": [["ADD", "x", {"effect": "allow", "role": "c", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["REMOVE", "x"], ["CHECK", "u", "read", "x", 0]]},
            ],
            [
                {"roles": {"r1": [], "r2": []}, "users": {"u": ["r1", "r2"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r1", "action": "read", "resource": "x"}], ["ADD", "d", {"effect": "deny", "role": "r2", "action": "write", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["CHECK", "u", "write", "x", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "*"}], ["CHECK", "u", "read", "*", 0], ["CHECK", "u", "read", "other", 0], ["CHECK", "u", "write", "other", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["ADD", "b", {"effect": "deny", "role": "r", "action": "read", "resource": "y"}], ["CHECK", "u", "read", "x", 0], ["CHECK", "u", "read", "y", 0]]},
                {"roles": {"r": []}, "users": {"u": ["missing"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["ADD", "b", {"effect": "allow", "role": "missing", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0]]},
            ],
            [
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x", "end": 3}], ["CHECK", "u", "read", "x", 2], ["CHECK", "u", "read", "x", 3], ["ADD", "b", {"effect": "allow", "role": "r", "action": "read", "resource": "x", "start": 3}], ["CHECK", "u", "read", "x", 3]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "*", "resource": "doc:*"}], ["ADD", "b", {"effect": "deny", "role": "r", "action": "*", "resource": "doc:private*"}], ["CHECK", "u", "read", "doc:private/1", 0], ["CHECK", "u", "read", "doc/public", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["REMOVE", "a"], ["REMOVE", "a"], ["CHECK", "u", "read", "x", 0], ["ADD", "a", {"effect": "deny", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0]]},
                {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["ADD", "a", {"effect": "deny", "role": "r", "action": "read", "resource": "x"}], ["CHECK", "u", "read", "x", 0], ["REMOVE", "a"], ["CHECK", "u", "read", "x", 0]]},
            ],
        ],
        "CP-06": [
            [
                {"window": 10, "events": [["RETRACT", "r0", "e"], ["INGEST", "e", "a", -11, 2], ["INGEST", "e2", "a", -1, 3], ["QUERY", "a", -1], ["RETRACT", "r1", "e"], ["SNAPSHOT"]]},
                {"window": 5, "events": [["INGEST", "e1", "a", 12, 1], ["INGEST", "e2", "a", 10, 2], ["INGEST", "e3", "b", 9, 4], ["SNAPSHOT"], ["RETRACT", "r", "e2"], ["QUERY", "a", 12]]},
                {"window": 3, "events": [["INGEST", "e1", "a", 2, 1], ["INGEST", "e2", "a", 3, 2], ["INGEST", "e3", "a", 5, 4], ["QUERY", "a", 5], ["RETRACT", "r", "e3"], ["QUERY", "a", 5]]},
                {"window": 7, "events": [["INGEST", "e1", "a", 0, 1], ["INGEST", "e2", "b", -1, 2], ["RETRACT", "r", "e2"], ["INGEST", "e3", "b", -7, 4], ["SNAPSHOT"]]},
            ],
            [
                {"window": 10, "events": [["INGEST", "e1", "a", 1, 1], ["RETRACT", "r", "unknown"], ["RETRACT", "r", "e1"], ["INGEST", "e2", "a", 11, 3], ["QUERY", "a", 11], ["SNAPSHOT"]]},
                {"window": 4, "events": [["INGEST", "a", "x", -4, 1], ["INGEST", "b", "x", -1, 2], ["QUERY", "x", -1], ["SNAPSHOT"]]},
                {"window": 6, "events": [["INGEST", "e1", "a", 6, 1], ["INGEST", "e2", "a", 12, 2], ["RETRACT", "x", "e1"], ["SNAPSHOT"], ["RETRACT", "x2", "e2"], ["SNAPSHOT"]]},
                {"window": 10, "events": [["SNAPSHOT"], ["INGEST", "e", "a", 1, 3], ["SNAPSHOT"], ["QUERY", "a", 1]]},
            ],
            [
                {"window": 2, "events": [["INGEST", "e1", "a", 0, 1], ["INGEST", "e2", "a", 1, 2], ["INGEST", "e3", "a", 2, 4], ["QUERY", "a", 1], ["QUERY", "a", 2]]},
                {"window": 5, "events": [["INGEST", "e1", "b", 5, 1], ["INGEST", "e2", "a", 4, 2], ["INGEST", "e3", "b", 9, 3], ["SNAPSHOT"]]},
                {"window": 10, "events": [["INGEST", "e1", "a", 1, -2], ["INGEST", "e2", "a", 2, 0], ["QUERY", "a", 0], ["RETRACT", "r", "e1"], ["QUERY", "a", 0]]},
                {"window": 3, "events": [["INGEST", "e1", "a", 8, 1], ["INGEST", "e2", "a", 4, 2], ["INGEST", "e3", "a", 0, 3], ["SNAPSHOT"], ["RETRACT", "r", "e2"], ["SNAPSHOT"]]},
            ],
            [
                {"window": 10, "events": [["INGEST", "b", "b", 3, 2], ["INGEST", "a", "a", 1, 1], ["INGEST", "c", "a", 12, 5], ["SNAPSHOT"], ["QUERY", "a", 12]]},
                {"window": 7, "events": [["INGEST", "e1", "a", -7, 1], ["INGEST", "e2", "a", -1, 2], ["QUERY", "a", -1], ["RETRACT", "r", "e1"], ["SNAPSHOT"]]},
                {"window": 5, "events": [["INGEST", "e1", "a", 4, 1], ["INGEST", "e2", "a", 5, 2], ["INGEST", "e3", "a", 9, 3], ["RETRACT", "r", "e2"], ["SNAPSHOT"]]},
                {"window": 10, "events": [["INGEST", "e1", "a", 1, 1], ["INGEST", "e2", "b", 1, 2], ["QUERY", "a", 1], ["QUERY", "b", 1], ["RETRACT", "r", "e1"], ["SNAPSHOT"]]},
            ],
            [
                {"window": 3, "events": [["INGEST", "e1", "a", 2, 1], ["INGEST", "e2", "a", 5, 2], ["QUERY", "a", 4], ["QUERY", "a", 5], ["RETRACT", "r", "e2"], ["QUERY", "a", 5]]},
                {"window": 6, "events": [["INGEST", "e1", "a", 6, 1], ["INGEST", "e2", "a", 12, 2], ["RETRACT", "x", "e1"], ["SNAPSHOT"], ["INGEST", "e3", "a", 0, 4], ["SNAPSHOT"]]},
                {"window": 10, "events": [["INGEST", "e1", "a", 1, 1], ["RETRACT", "r", "e1"], ["RETRACT", "r2", "e1"], ["INGEST", "e2", "a", 2, 2], ["QUERY", "a", 0], ["SNAPSHOT"]]},
                {"window": 4, "events": [["INGEST", "e1", "a", -1, 1], ["INGEST", "e2", "a", 0, 2], ["QUERY", "a", -1], ["SNAPSHOT"], ["RETRACT", "r", "e1"], ["SNAPSHOT"]]},
            ],
        ],
        "CP-07": [
            [
                {"workers": 2, "resources": {"gpu": 1}, "jobs": [{"id": "a", "release": 0, "duration": 3, "priority": 1, "deadline": 2, "needs": ["gpu"], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 2, "deadline": 1, "needs": ["gpu"], "deps": []}, {"id": "c", "release": 0, "duration": 1, "priority": 3, "deadline": 4, "needs": [], "deps": ["b"]}], "cancel": []},
                {"workers": 1, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 4, "needs": ["db"], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 2, "deadline": 3, "needs": ["db"], "deps": ["a"]}], "cancel": [{"id": "b", "time": 2}]},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 1, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 2, "deadline": 2, "needs": [], "deps": ["a"]}], "cancel": [{"id": "b", "time": 1}]},
                {"workers": 2, "resources": {"x": 1, "y": 1}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 5, "needs": ["x"], "deps": []}, {"id": "b", "release": 0, "duration": 2, "priority": 2, "deadline": 5, "needs": ["y"], "deps": []}, {"id": "c", "release": 0, "duration": 1, "priority": 1, "deadline": 5, "needs": ["x", "y"], "deps": []}], "cancel": []},
            ],
            [
                {"workers": 1, "resources": {"x": 0}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 1, "needs": ["x"], "deps": []}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": ["missing"]}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": ["b"]}, {"id": "b", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": ["a"]}], "cancel": []},
                {"workers": 1, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 3, "duration": 1, "priority": 1, "deadline": 5, "needs": ["db"], "deps": []}], "cancel": [{"id": "a", "time": 3}]},
            ],
            [
                {"workers": 2, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 2, "deadline": 4, "needs": ["db"], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 3, "deadline": 3, "needs": [], "deps": []}, {"id": "c", "release": 0, "duration": 1, "priority": 1, "deadline": 4, "needs": ["db"], "deps": ["b"]}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "b", "release": 0, "duration": 1, "priority": 1, "deadline": 3, "needs": [], "deps": []}, {"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 3, "needs": [], "deps": []}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 0, "needs": [], "deps": []}, {"id": "b", "release": 1, "duration": 1, "priority": 1, "deadline": 3, "needs": [], "deps": []}], "cancel": []},
                {"workers": 2, "resources": {"gpu": 2}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 3, "needs": ["gpu"], "deps": []}, {"id": "b", "release": 0, "duration": 2, "priority": 1, "deadline": 3, "needs": ["gpu"], "deps": []}], "cancel": []},
            ],
            [
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": []}, {"id": "b", "release": 2, "duration": 1, "priority": 2, "deadline": 4, "needs": [], "deps": ["a"]}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 2, "priority": 1, "deadline": 3, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 2, "deadline": 4, "needs": [], "deps": ["a"]}], "cancel": []},
                {"workers": 2, "resources": {"a": 1, "b": 1}, "jobs": [{"id": "x", "release": 0, "duration": 2, "priority": 1, "deadline": 4, "needs": ["a", "b"], "deps": []}, {"id": "y", "release": 0, "duration": 1, "priority": 2, "deadline": 2, "needs": ["a"], "deps": []}], "cancel": []},
                {"workers": 2, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": ["db"], "deps": []}, {"id": "b", "release": 1, "duration": 1, "priority": 1, "deadline": 3, "needs": ["db"], "deps": []}], "cancel": []},
            ],
            [
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 1, "deadline": 3, "needs": [], "deps": ["a"]}, {"id": "c", "release": 0, "duration": 1, "priority": 1, "deadline": 4, "needs": [], "deps": ["b"]}], "cancel": []},
                {"workers": 1, "resources": {}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": []}, {"id": "b", "release": 0, "duration": 1, "priority": 1, "deadline": 3, "needs": [], "deps": ["a"]}], "cancel": [{"id": "a", "time": 0}]},
                {"workers": 1, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 0, "duration": 3, "priority": 1, "deadline": 1, "needs": ["db"], "deps": []}], "cancel": [{"id": "a", "time": 1}]},
                {"workers": 1, "resources": {"db": 1}, "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": ["db", "missing"], "deps": []}], "cancel": []},
            ],
        ],
        "CP-08": [
            [
                {"facts": {"x": 1, "tags": ["a"]}, "rules": [{"id": "a", "phase": "pre", "priority": 2, "when": {"op": "eq", "field": "x", "value": 1}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 1, "when": {"all": [{"op": "eq", "field": "x", "value": 2}, {"op": "contains", "field": "tags", "value": "a"}]}, "set": {"ok": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 2, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"x": 3}, "add": {}, "remove": []}, {"id": "c", "phase": "post", "priority": 1, "when": {"op": "eq", "field": "x", "value": 2}, "set": {"z": 1}, "add": {}, "remove": []}]},
                {"facts": {"tags": ["a"]}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "tags"}, "set": {}, "add": {"tags": "a"}, "remove": []}, {"id": "b", "phase": "main", "priority": 0, "when": {"op": "contains", "field": "tags", "value": "a"}, "set": {}, "add": {"tags": "b"}, "remove": []}, {"id": "c", "phase": "post", "priority": 0, "when": {"not": {"op": "exists", "field": "bad"}}, "set": {"done": True}, "add": {}, "remove": []}]},
                {"facts": {"a": 1, "b": 2}, "rules": [{"id": "r", "phase": "main", "priority": 2, "when": {"op": "exists", "field": "a"}, "set": {}, "add": {}, "remove": ["b"]}, {"id": "s", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "b"}, "set": {"still": True}, "add": {}, "remove": []}]},
            ],
            [
                {"facts": {"n": 5}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"any": [{"op": "eq", "field": "n", "value": 4}, {"op": "gte", "field": "n", "value": 5}]}, "set": {"hit": True}, "add": {}, "remove": []}, {"id": "stop", "phase": "post", "priority": 1, "when": {"op": "eq", "field": "n", "value": 5}, "set": {"done": True}, "add": {}, "remove": [], "stop": True}, {"id": "never", "phase": "post", "priority": 0, "when": {"op": "exists", "field": "n"}, "set": {"bad": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "eq", "field": "x", "value": 1}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "eq", "field": "x", "value": 2}, "set": {"ok": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 2, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "c", "phase": "main", "priority": 0, "when": {"op": "neq", "field": "x", "value": 4}, "set": {"ok": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "eq", "field": "x", "value": 1}, "set": {"bad": True}, "add": {}, "remove": []}]},
            ],
            [
                {"facts": {"n": 5}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "neq", "field": "n", "value": 4}, "set": {"neq": True}, "add": {}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "in", "field": "n", "value": [4, 5]}, "set": {"in": True}, "add": {}, "remove": []}]},
                {"facts": {"n": 5}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "lte", "field": "n", "value": 5}, "set": {"lte": True}, "add": {}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"op": "gte", "field": "n", "value": 5}, "set": {"gte": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"any": [{"op": "eq", "field": "x", "value": 2}, {"op": "eq", "field": "x", "value": 1}]}, "set": {"matched": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"all": [{"op": "eq", "field": "x", "value": 1}, {"op": "neq", "field": "x", "value": 2}]}, "set": {"matched": True}, "add": {}, "remove": []}]},
            ],
            [
                {"facts": {"tags": ["a", "b"]}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "contains", "field": "tags", "value": "a"}, "set": {}, "add": {"tags": "c"}, "remove": []}, {"id": "b", "phase": "post", "priority": 1, "when": {"not": {"op": "contains", "field": "tags", "value": "z"}}, "set": {}, "add": {}, "remove": ["tags"], "stop": True}]},
                {"facts": {"tags": ["a"]}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "tags"}, "set": {}, "add": {"tags": "a"}, "remove": []}, {"id": "b", "phase": "main", "priority": 0, "when": {"op": "exists", "field": "tags"}, "set": {"after": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "stop", "phase": "main", "priority": 2, "when": {"op": "exists", "field": "x"}, "set": {"seen": True}, "add": {}, "remove": [], "stop": True}, {"id": "never", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"bad": True}, "add": {}, "remove": []}]},
                {"facts": {"a": 1, "b": 2}, "rules": [{"id": "r", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "a"}, "set": {}, "add": {}, "remove": ["b"]}, {"id": "s", "phase": "main", "priority": 0, "when": {"op": "exists", "field": "b"}, "set": {"still": True}, "add": {}, "remove": []}]},
            ],
            [
                {"facts": {"n": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "n"}, "set": {"n": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 0, "when": {"op": "eq", "field": "n", "value": 2}, "set": {"done": True}, "add": {}, "remove": []}]},
                {"facts": {"x": 1}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"x": 2}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 1, "when": {"op": "exists", "field": "x"}, "set": {"x": 3}, "add": {}, "remove": []}]},
                {"facts": {}, "rules": [{"id": "a", "phase": "main", "priority": 1, "set": {"bad": True}, "add": {}, "remove": []}, {"id": "b", "phase": "main", "priority": 0, "when": {"op": "not", "field": "x", "op": "exists"}, "set": {"ok": True}, "add": {}, "remove": []}]},
                {"facts": {"x": [1, 2]}, "rules": [{"id": "a", "phase": "main", "priority": 1, "when": {"op": "contains", "field": "x", "value": 2}, "set": {"ok": True}, "add": {}, "remove": []}]},
            ],
        ],
    }


_PAYLOAD = """c-rM%+j84D68#rGrs#?QO3B1;E?c$9Zr1TSnc13h>4Bu^m>ZeYQdCUYrGH-n-~}K7qQQ%msePEpBEbgwboc3Qkkq_bmp5lKWS!sLy;y5Eb*=LkEBF~i=`KI^Vufq#+)9vTTbnQn$gw-iwQRJqi_ev9#oK($?egpL_K#&gFizG%k{^kYb+ii!TOxsuySeyNF~+aPTwYvXE<Y=VCAhg5hb+d^ECyT0{A?J7Y3Oc<lDVdHJHPB4ACI;bWZS?`gEcu5MnwNOISATT6A+1P?wG8YEp~Zj*>@{4E+*?M7C;U*mq=u!iR%Zs2<yu~^1;GCt0U1=X^E!pxJzdaw6+1ev8s%swn>*su&F6JjnF_H3Obg7ef9gz<Y@0o(7t~BbR!?KRm1})1goXA;Bx>z+(wZIzR}?I>H3e0&!4Wqn0fBHjT#_6YsDoJpx&xNRpxQX5HcQ_+vVSvm)|OHDly8D$yGJs(JqH_`v#Z?;#6L|V<O&{fVnXCKUWgPo+60zQ$94ldy{Dfc2E!}_90IF5=7uLtrutVz!!j*L)h|c+pIoNtMT0B*IgGLw1NH%!T-4zf8qv=2Z=)>=Bv*zgnQ<ovh+FwdaD`6ec2S7Cm^z}n~P5ZdQy_*fa<1KBSnpJu|A=L;(d#iQ;pz~l9aBgH|yj+MWA<A?cfR&))pwCl@|V5Y#nf^-{r#N1iJ?=JbPE``T}h$3wlWZ<N;DpKK)jj-~nBeF`^@JLPsnEXk!clH3@g2j5j9IY2DA6ARjp+^pkvKJ11(~C+fc|@mMV%_ex663W)A_6_Qa>^7`f^SL=wbKJwjRTOY1G<Q1*c1leeciqq8D9Yg6os1_UdOpR?4=#BvDwO7KGJy^f5>hvXtIjHbjsFIwFKNhrNfUpRI!Rfu@s^1)d7QLvaH|y&I2jcH@6Z37y-&);Hu=6qmQt)+K3DBY`wh~`&c=1-^=rU`K(PAjTH*4u8ruIqiBlIkGjPLuP32rtZ&CQ1DPm&Vyf#kNEqqyyMXI)&8RPq$A11s0t_0uqpa&6w^2ZQ_jeBGp$*lgmb{6G@y;(bD9wbrqJPR1nhCSbJ=SuYc|4x)n~ED7jFdnJzzXo^F%IG2gL{J6X%8tv&|Dx(-UBd2ed|NKHtK;`K!STX6l!ZL*PS2Rc5<;UaHqUZC^a{}@zH`{(kP4kjVtHy}tytA&B*Cfm@K7ao5Z*oxw#Muyh6CU4ga23K(OPB^-{`6B4ra{Mf?sDA3Iw79khO><&1JQ1Lnt-Z;B8b-X7Ayxz#=~J-yVOlmlE4(2WyJ=G{1jH7n%8E_3}YgLSS%~p-5hSgb?x#i{TS1cVNP5+SO*+$I^ie<JgdF)xwmIFqFi2Qo4F*X*ft67!|V;j+H9y=MRxwJ+a$=$0$eak(7uBIR9ZcTyImN4x749An?Cvm;s(IWHFYRCx6L|~I71o?<)=P;_%I6hK$w0A3j63s6hB4XW>gT0)Wns<KDO?rk73s42-f?x9DZ^~7rDWOvBC&bj*rq90nuq+{~_G0;l9!h!`4mmm5mcyY+<xBD#YfPu!C**iV-RdjWdy%+P+p}efG^XeTh&0@>Ly)drGE3Lc?cT%kh%%NVJTY-{kV7u}1qJ{JM!4RMWjtr`R}s2$BvEs`IZ^x}7XJ9l*3JKXv%^3$-ICVGUvGvR)pTwyLswP@Ck!J9noSXt=9m9tBUXxOT?x&l`=oc}Xy2i^)?<l5gH^lklgT25+FdOvU)O-MdL|w|j3B`a{d9lhmH$mZGPr*MAw>n+_bfrN)TjvM?*Q<=-i{<!_hYZZGIFiOGzpN>}#j`ftmx-{@DHJ(!6Y&DAGxd4`ePzkXld{#hPkx>j;gCHL#~#m(1`U%pvnT~A@O&MkJ1W}+&2bsq0YMUDt9r(t@a8}+souE~<g)T@dQ&(JLYd;dt7(e8igO67UA!iZ^yFx#MQA(2aKK;$rf`@r^QYu!b3n1}|32=fRnM1X2Fu|iE$3N3ZzQIdk>aaTLsg^S|4dG6a<bdhXEbOd9og4U5Cn;%~=WI5ax5^x=>HHgF3Q8*t~dXOz5<P>_oJK9F>S6+wV_{?PZcr*yH(yLnjc=o>OkQ^NERjvlHd2MntC(Bn<d6~MLYlotZ+FDl|W^Fu>B@f&-g&{NzTbYrS3ABJ2^&ICGo3!(WpLylxEpxLHsA@k~3e+4BSXsSlm(Iia#9RiI`NeQ%f2SgL+>EZQ_9g|ZXSfbPDLU^=<4iCruDOHUz*lG}tgV^S3#S*x@Db4E^LHzN_ez}Cfg}<6b#PXgsm!QIBDj@AP~*Fhi?Lz8Xr*FZCUzAhiEEAod9+9Jqa2F4vQlxB4!aoQu(QfvZ7E=06EH;y0<Y5SGkLv=StZU{cc#n~!XQWrF!q5nY)I$jg)?~3@SBMf(D-p+<*L+898))OdWMF)lrpPP-_<3mJ>5zbGXf~hWB)bFUsou9s>6Pjt`?oljytJcr;gjNDDh=A$wFTzdQuiy^_>qKHF-&jR1GiIHN3L&KwV>-(??Y=oA<o$YYf3y%oR{96bw?N5jbfqrffP~O=oM={3{x;woeE(glE}?E@Iqe^lifwS^BQ$g(mGA?sh8<Oh}iHdv*C^XBXXdGwF5hYYg)H@U}%#0?c2dap{$D=cWxX?!kDdBVM_KxMNoVx4d{Z&7OibYF$XwLenBrc-u^o6}!sF4*r`Dpuej5N2Z%B{FQy79AboWxBk7jTkpG(A8Z&;{3rI<I}hu?U6WS^XxXq1wgr!@_le7HUN|;;xq!?Z1p%A;`*u$z-zH(4(1js#>tPePyMU06&C5k{xu}rqb;`wRx${actM1yOeNMC>)e)qw>N_#?)(BYyF`e}kCqL-z65MzxV&^{u>pi(!!`|Ya<&i$K@7>KVD1MOzkq)swLb)KXf9y2b2P<Z_w0=#)y83dxw91zit1o`_MSNwYGUQ7QVH!RL%yDG4oy%>2Wwu>=VADFa30zBW-KJ#RX@-2XXa&?|1;!l}<{F5r_g28jA_cMtjw}>aY=kNtQFAOI-l~OCj@!b(BQvl=YNQI@cmOlaqMN~dajkY!GU{~mj1D*$GftCV$PpxP5Y9V(U_8hvM<~HH_SCRE+@2DAW<bwvD|xfLzRGJ1L*L{AuzqA;qZC}D(<$Q(Qe!NRni!nIqjg}t)Vec*caBCxg-lbYGbq8e6&85cBvOae0vJ*Yn7M;9R)wc2T(syL7J1W9E<CRL;*ENna8kM}02Lti#5x)Ts1b&<Q53evHVYb#A+6kA1474uO-#B*$Doqa$d&eY7##X;tJ?C!(1(I*LehAA&zz6bR^V|1+?X+^^3GR=afI&d^<dPL3>hDc)iX4Pb)*!^gDBZx_rRq>jB@;;<)0aSzC{6S#shok2P__`xa^;VI>n-aRnurG{lwJijMeRowSoCc71xACZL9y99shdf9IJV)d%3>dtKs&fV@@z5Y|lEnEyXFhlmGdJNtEo~uqp4!{3hO$xp)1P&Xl^}YlqC(M9H4My^#-h*K6iqm1^4ux@7W$7*;DQKE^-G6$NRriAD?FhajS}hQX#x-1OI>g8$}!{d70`fc*qib4HJw@zD(<s|8_e%J_$MPK?b>>u#9uc1}-kbC)A1D#ai_j?#SUT|Jck?9!3k;udU@54_)m6j!pI0%G!uRX?n%F=CP_-bJRT&okYJ340HQdlWd{Zpkr9fP#Zo#xt;23%#BO%fekg_c*4?*n<r{Ci8hujCUzuvgabAAg+kJjayoYzOgP?x_q7Txp)G(VOG0*u1jxPE-ob&E>6?mHwD;QiiiXZ-tF7qmy>!H$mX*ilgeYw(Eieit#wSuyTJ@mobpRy|DO|4eR!DD86<&D1A3S@R9yw`2=@dU?ghc94C3nJZ)YCtyEG&;+%Q0ed}~fH>~1sG5*eyOC12qhv4{715vW|vhcIpDpXeaupGd|zb3Xr6Bfit$FDQnP=RYO3$Tc;mLm?cf2>PXM8R=pdl66GE&mb|6OA>P`uZa44g&2&)D%F>$c(_goM+yP&H*`s(XI(UTnFO@Iq)Zx;5|#DN|9gRhhZi`o%nGt-Br?vZCN)TBCx{@BS%I<BMOmtt1tTp%_k`(;IE<E^n_e{r#`)^B^HL3pY47GasT;sdt`!mj`6POj8wLFcYkUiA(m;>IMl2IXvA}o8#Etp{jz7JyG{A=cB2CZU>8Rz=P0419wyM+bDk!+Y#BIyP@MMhiba7&&Ap0*!ic}<m`3g|UnYC`msV{c4<o<LmIkY<l2RoC_PcQ2P8cnihMb8F3b9a=hEAU@%bEN;4h~?g=<cIMUR4bhp-W*fe(%r|YD7Mj$0_*Z!5JaGU6j0JNJ5eBg!OA*g6Hv|6BxKNd4&MbrueS>{`%CQtjhqQ1c{>tK!XMI|&Ccx`+<PM>I$1l9{zCUF2HZU8i|x3u)>Jr(hk`bn3`3p+3hsS(<W1*sp@QhvE|Ugqr%@dMb?oZ+KW_&G69"""

import base64
import json
import zlib


def golden_cases(item_id):
    payload = json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)))
    try:
        groups = payload[item_id]
    except KeyError:
        from .challenge_goldens import golden_cases as old_cases
        return old_cases(item_id)
    if len(groups) != 5 or any(len(group) != 4 for group in groups):
        raise AssertionError(f"invalid frozen golden shape for {item_id}")
    return [[(entry["data"], entry["expected"]) for entry in group] for group in groups]
