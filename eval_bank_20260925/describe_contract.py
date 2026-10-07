"""Shared describe() contract for coding items.

The prompt names roles. The solution names its own fields. Scoring renames
the fixture into those fields, then compares the business result.
"""

from __future__ import annotations

CODING_TRACE = frozenset({"OK", "REJECT", "DUP", "INVALID", "MISSING", "SNAP", "RESTORE"})


def is_coding_envelope(value):
    return (
        isinstance(value, dict)
        and set(value) == {"trace", "output"}
        and isinstance(value["trace"], list)
        and all(isinstance(item, str) and item in CODING_TRACE for item in value["trace"])
        and isinstance(value["output"], dict)
    )


def _tree_equal(got, expected):
    if type(got) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(got) == set(expected) and all(_tree_equal(got[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(got) == len(expected) and all(_tree_equal(left, right) for left, right in zip(got, expected))
    return got == expected


def coding_envelope_equal(got, expected):
    if not is_coding_envelope(got) or not is_coding_envelope(expected):
        return False
    return got["trace"] == expected["trace"] and _tree_equal(got["output"], expected["output"])



def identity_document(schema: dict) -> dict:
    def ident(roles):
        return {role: role for role in roles}

    return {
        "keys": ident(schema["keys"]),
        "actions": ident(schema["actions"]),
        "states": ident(schema["states"]),
        "trace": {"dup": "DUP"},
    }


def _mapping(section, roles) -> bool:
    if not isinstance(section, dict) or set(section) != set(roles):
        return False
    values = [section[role] for role in roles]
    if not all(isinstance(value, str) and value for value in values):
        return False
    return len(set(values)) == len(values)


def valid_document(doc, schema) -> bool:
    if not isinstance(doc, dict):
        return False
    if not _mapping(doc.get("keys"), schema["keys"]):
        return False
    if not _mapping(doc.get("actions"), schema["actions"]):
        return False
    if not _mapping(doc.get("states"), schema["states"]):
        return False
    trace = doc.get("trace")
    return isinstance(trace, dict) and trace.get("dup") == "DUP"


def rename_tree(value, key_map, value_map):
    if isinstance(value, dict):
        return {key_map.get(key, key): rename_tree(item, key_map, value_map) for key, item in value.items()}
    if isinstance(value, list):
        return [rename_tree(item, key_map, value_map) for item in value]
    if isinstance(value, str) and value in value_map:
        return value_map[value]
    return value


def adapt_input(data, doc):
    values = {}
    values.update(doc["actions"])
    values.update(doc["states"])
    return rename_tree(data, doc["keys"], values)


def project_output(value, doc):
    keys = {name: role for role, name in doc["keys"].items()}
    states = {name: role for role, name in doc["states"].items()}
    return rename_tree(value, keys, states)


def business_equal(got, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(got, dict) and all(key in got and business_equal(got[key], item) for key, item in expected.items())
    if isinstance(expected, list):
        return isinstance(got, list) and len(got) == len(expected) and all(business_equal(left, right) for left, right in zip(got, expected))
    return got == expected


def trace_ok(got, expected, bound) -> bool:
    if not isinstance(got, list) or len(got) != len(expected):
        return False
    if not all(isinstance(item, str) and item for item in got):
        return False
    for got_item, expected_item in zip(got, expected):
        if expected_item in bound and got_item != expected_item:
            return False
        if expected_item not in bound and got_item == "DUP" and expected_item != "DUP":
            return False
    return True
