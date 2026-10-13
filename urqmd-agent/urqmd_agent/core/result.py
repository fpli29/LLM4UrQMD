"""Standard result envelope for every Agent-facing scientific tool."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

STATUS_OK = "ok"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"


@dataclass
class ToolResult:
    """Machine-readable result of one tool call.

    status:
        "ok"      — the tool completed and `data` is trustworthy.
        "blocked" — a guardrail refused the request (e.g. intervention
                    execution disabled); no partial side effects.
        "error"   — the tool failed; `data` may be empty, `warnings`
                    carry the diagnostic. An error is NEVER silently
                    converted to success.
    """

    status: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "data": self.data,
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def ok(cls, summary: str, data=None, **kw) -> "ToolResult":
        return cls(STATUS_OK, summary, data or {}, **kw)

    @classmethod
    def blocked(cls, summary: str, **kw) -> "ToolResult":
        return cls(STATUS_BLOCKED, summary, **kw)

    @classmethod
    def error(cls, summary: str, **kw) -> "ToolResult":
        return cls(STATUS_ERROR, summary, **kw)
