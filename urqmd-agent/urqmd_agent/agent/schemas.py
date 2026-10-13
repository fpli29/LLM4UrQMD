"""Argument validation for tool calls (deterministic, no guessing).

Each entry maps a field name to (type_tuple, required, description).
validate_args raises ToolError on unknown fields, missing required fields,
or type mismatches.
"""

from typing import Any, Dict

from ..core.errors import ToolError

_TYPE_NAMES = {int: "int", float: "float", str: "str", bool: "bool",
               list: "list", dict: "dict"}


def validate_args(schema: Dict[str, tuple], args: Dict[str, Any]) -> Dict[str, Any]:
    unknown = set(args) - set(schema)
    if unknown:
        raise ToolError(f"unknown argument(s): {sorted(unknown)}")
    out = {}
    for field, (types, required, _desc) in schema.items():
        if field not in args:
            if required:
                raise ToolError(f"missing required argument {field!r}")
            continue
        value = args[field]
        if not isinstance(value, types) or (
            isinstance(value, bool) and bool not in types
        ):
            want = "/".join(_TYPE_NAMES.get(t, t.__name__) for t in types)
            raise ToolError(
                f"argument {field!r} must be {want}, got {type(value).__name__}"
            )
        out[field] = value
    return out
