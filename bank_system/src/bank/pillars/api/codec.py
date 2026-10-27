"""Lossless JSON codec for the pillar engine state.

The engine objects are plain dataclasses with enum/datetime/list fields. This
module round-trips them into JSON-safe structures and back, using tagged
markers so type information survives serialization:

    ``{"__enum__": <clsname>, "value": <value>}``        enum member
    ``{"__dt__": <iso-8601 string>}``                     tz-aware datetime
    ``{"__set__": [...]}``                                set
    ``{"__dc__": <clsname>, ...fields...}``               dataclass instance

Decoding resolves markers against caller-supplied registries because the
engine dataclasses are not importable all from one module.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any


def encode(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return {"__enum__": type(obj).__name__, "value": obj.value}
    if isinstance(obj, datetime):
        return {"__dt__": obj.isoformat()}
    if isinstance(obj, (set, frozenset)):
        return {"__set__": [encode(x) for x in obj]}
    if isinstance(obj, list):
        return [encode(x) for x in obj]
    if isinstance(obj, tuple):
        return {"__tuple__": [encode(x) for x in obj]}
    if isinstance(obj, dict):
        return {k: encode(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj):
        return {
            "__dc__": type(obj).__name__,
            **{f.name: encode(getattr(obj, f.name)) for f in dataclasses.fields(obj)},
        }
    return obj


def to_wire(obj: Any) -> Any:
    """Flatten engine objects into plain JSON for HTTP responses.

    ``encode``/``decode`` are the *persistence* codec (tagged markers so a
    snapshot round-trips losslessly). This is the *public wire* codec:
    enums -> their value, datetime -> ISO-8601 string, dataclass -> flat
    dict of fields, set/tuple -> list. No markers ever reach an API client.
    """
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return [to_wire(x) for x in obj]
    if isinstance(obj, list):
        return [to_wire(x) for x in obj]
    if isinstance(obj, tuple):
        return [to_wire(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_wire(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj):
        return {f.name: to_wire(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    return obj


def decode(
    node: Any,
    classes: dict[str, type],
    enums: dict[str, type[Enum]],
) -> Any:
    if isinstance(node, dict):
        if "__dt__" in node:
            return datetime.fromisoformat(node["__dt__"])
        if "__enum__" in node:
            return enums[node["__enum__"]](node["value"])
        if "__set__" in node:
            return {decode(x, classes, enums) for x in node["__set__"]}
        if "__tuple__" in node:
            return tuple(decode(x, classes, enums) for x in node["__tuple__"])
        if "__dc__" in node:
            cls = classes[node["__dc__"]]
            kwargs = {k: decode(v, classes, enums) for k, v in node.items() if k != "__dc__"}
            return cls(**kwargs)
        return {k: decode(v, classes, enums) for k, v in node.items()}
    if isinstance(node, list):
        return [decode(x, classes, enums) for x in node]
    return node