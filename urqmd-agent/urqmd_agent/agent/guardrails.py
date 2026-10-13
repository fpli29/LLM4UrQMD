"""Deterministic guardrails enforced on every tool call.

Guardrails raise GuardrailError before the tool body runs; the tool runner
converts that into a ToolResult with status "blocked". Nothing here consults
the LLM or its prose.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from ..core import config, paths
from ..core.errors import GuardrailError


def check_event_count(nev: int, authorized_cap: Optional[int] = None) -> None:
    cap = authorized_cap if authorized_cap is not None else config.DEFAULT_EVENT_CAP
    if nev < 1:
        raise GuardrailError("event count must be >= 1")
    if nev > cap:
        raise GuardrailError(
            f"event count {nev} exceeds the agent-mode cap of {cap}; "
            "higher statistics require explicit user/evaluation authorization"
        )


def check_output_dir(run_dir: Path) -> Path:
    run_dir = Path(run_dir).resolve()
    for allowed in paths.ALLOWED_OUTPUT_DIRS:
        allowed = allowed.resolve()
        if run_dir == allowed or allowed in run_dir.parents:
            # Fortran ftnNN buffers are character*77 (input.f:23): the path
            # handed to UrQMD must stay short relative to the repo root.
            try:
                checked = str(run_dir.relative_to(paths.REPO_ROOT))
            except ValueError:
                # Whitelisted directory outside URQMD_HOME: the absolute
                # path itself is handed to UrQMD, so check its full length.
                checked = str(run_dir)
            if len(checked) > 60:
                raise GuardrailError(
                    f"run directory path too long for UrQMD ftn buffers: "
                    f"{checked}")
            try:
                return run_dir.relative_to(paths.REPO_ROOT)
            except ValueError:
                return run_dir
    raise GuardrailError(
        f"run directory {run_dir} is outside the allowed output directories: "
        + ", ".join(str(d) for d in paths.ALLOWED_OUTPUT_DIRS)
    )


def check_ctoption(index: int, value: int, described: bool) -> None:
    """CTOptions may only be set after a describe/validation step."""
    if not described:
        raise GuardrailError(
            f"CTOption({index})={value} requested without a prior "
            "describe_option/validate_intervention result; run "
            "urqmd.describe_option first and pass described=True"
        )


def check_no_source_modification() -> None:
    raise GuardrailError(
        "source modification through the Agent layer is disabled"
    )


def check_no_intervention_execution() -> None:
    raise GuardrailError(
        "physics-intervention execution is disabled in the MVP "
        "(urqmd.run_intervention is interface-only)"
    )
