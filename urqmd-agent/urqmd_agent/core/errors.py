"""Error hierarchy for the Agent tool layer."""


class UrqmdError(Exception):
    """Base class for all tool-layer errors."""


class GuardrailError(UrqmdError):
    """A deterministic guardrail refused the requested action."""


class ToolError(UrqmdError):
    """A tool could not complete (bad input, missing data, parse failure)."""


class UnknownToolError(UrqmdError):
    """The requested tool name is not in the registry."""
