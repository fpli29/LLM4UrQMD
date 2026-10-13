"""Authoritative registry of Agent-facing scientific tools.

Every tool module registers its ToolSpec at import time. Risk classes:

    READ_ONLY            — inspects source/knowledge, never runs UrQMD
    ANALYSIS             — deterministic computation over existing data
    SIMULATION           — launches UrQMD (event-capped)
    PHYSICS_INTERVENTION — changes transport physics (DISABLED in MVP)
    SOURCE_MODIFICATION  — would edit UrQMD source (DISABLED in MVP)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ..core.errors import UnknownToolError

READ_ONLY = "READ_ONLY"
ANALYSIS = "ANALYSIS"
SIMULATION = "SIMULATION"
PHYSICS_INTERVENTION = "PHYSICS_INTERVENTION"
SOURCE_MODIFICATION = "SOURCE_MODIFICATION"

RISK_LEVELS = (
    READ_ONLY,
    ANALYSIS,
    SIMULATION,
    PHYSICS_INTERVENTION,
    SOURCE_MODIFICATION,
)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    risk_level: str
    requires_urqmd: bool = False
    physics_changing: bool = False
    execution_enabled: bool = True
    #: True only for physics-changing tools whose handler enforces the
    #: frozen preregistered whitelist (Phase-1C execution policy).
    whitelist_gated: bool = False
    handler: Optional[Callable] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_level": self.risk_level,
            "requires_urqmd": self.requires_urqmd,
            "physics_changing": self.physics_changing,
            "execution_enabled": self.execution_enabled,
        }


REGISTRY: Dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    if spec.risk_level not in RISK_LEVELS:
        raise ValueError(f"unknown risk level {spec.risk_level!r}")
    if spec.name in REGISTRY:
        raise ValueError(f"duplicate tool registration: {spec.name}")
    if spec.physics_changing and spec.execution_enabled \
            and not spec.whitelist_gated:
        raise ValueError(
            f"{spec.name}: physics-changing tools must be registered with "
            "execution_enabled=False, unless whitelist_gated=True "
            "(handler enforces the frozen preregistered whitelist)"
        )
    REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> ToolSpec:
    try:
        return REGISTRY[name]
    except KeyError:
        raise UnknownToolError(f"no such tool: {name!r}") from None
