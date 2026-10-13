"""Dispatch layer: guardrail enforcement + trajectory logging."""

from typing import Any, Dict, Optional

from ..core.errors import GuardrailError, UnknownToolError
from ..core.result import ToolResult
from ..tools import registry
from .trajectory import TrajectoryLogger


def call_tool(
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    agent_note: Optional[str] = None,
) -> ToolResult:
    arguments = dict(arguments or {})
    try:
        spec = registry.get(name)
    except UnknownToolError as exc:
        return ToolResult.error(str(exc))
    if not spec.execution_enabled:
        result = ToolResult.blocked(
            f"tool {name!r} is registered but execution is disabled "
            f"(risk level {spec.risk_level})"
        )
        _log(session_id, name, arguments, result, agent_note)
        return result
    try:
        result = spec.handler(**arguments)
        if not isinstance(result, ToolResult):
            result = ToolResult.error(
                f"tool {name!r} returned a non-ToolResult value"
            )
    except GuardrailError as exc:
        result = ToolResult.blocked(str(exc))
    except Exception as exc:  # never convert failure to success
        result = ToolResult.error(f"{type(exc).__name__}: {exc}")
    _log(session_id, name, arguments, result, agent_note)
    return result


def _log(session_id, name, arguments, result, agent_note) -> None:
    if session_id is None:
        return
    artifacts = []
    if isinstance(result.data, dict):
        for key in ("paths", "artifacts", "output_files"):
            val = result.data.get(key)
            if isinstance(val, (list, tuple)):
                artifacts.extend(str(v) for v in val)
    TrajectoryLogger(session_id).log_call(
        tool=name,
        arguments=arguments,
        result_status=result.status,
        result_summary=result.summary,
        warnings=result.warnings,
        artifacts=artifacts,
        agent_note=agent_note,
    )
