"""Intervention tools: catalog listing, validation, planning, and
whitelist-gated execution. Executable only with explicit human
authorization tokens: the preregistered Phase-1C conditions
(cto15_1 / cto59_0 / tim12 / tim8, token 'phase1c-preregistered') and the
Phase-1D confirmatory MB-only condition (mb_only, token
'phase1d-confirmatory', locally patched executable). All other
SOURCE_MODIFICATION remains blocked.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..agent.guardrails import GuardrailError, check_output_dir
from ..core.errors import ToolError
from ..core.result import ToolResult
from ._common import load_catalog
from .registry import PHYSICS_INTERVENTION, READ_ONLY, ToolSpec, register


def _catalog_entries() -> dict:
    return load_catalog()["interventions"]


def _find_key(intervention: str) -> Optional[str]:
    entries = _catalog_entries()
    text = intervention.strip()
    if text in entries:
        return text
    m = re.match(r"^(?:ctoption|cto)\s*\(?\s*(\d+)\s*\)?$", text,
                 re.IGNORECASE)
    if m and f"CTOption({m.group(1)})" in entries:
        return f"CTOption({m.group(1)})"
    lowered = text.lower()
    for key in entries:
        if key.lower() == lowered:
            return key
    return None


def _public_entry(key: str, entry: dict) -> dict:
    out = dict(entry)
    out["name"] = key
    # execution is disabled for ALL interventions in the MVP, including
    # existing runtime options; the catalog listing is informational only
    out["execution_enabled"] = False
    return out


def list_interventions() -> ToolResult:
    """List the source-verified intervention catalog (listing only)."""
    entries = _catalog_entries()
    data = {"interventions": [_public_entry(k, v) for k, v in entries.items()],
            "note": "execution of every intervention is disabled in the MVP; "
                    "this is a catalog listing only"}
    summary = (f"{len(entries)} catalogued intervention(s): "
               + ", ".join(f"{k} [{v['type']}, {v['role']}]"
                           for k, v in entries.items()))
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.list_interventions"})


def validate_intervention(intervention: str,
                          target_mediator: Optional[str] = None,
                          hypothesis: Optional[str] = None) -> ToolResult:
    """Validate a proposed intervention against the source-verified
    catalog. Execution is NEVER allowed in the MVP."""
    key = _find_key(intervention)
    if key is None:
        return ToolResult.error(
            f"{intervention!r} is not a source-verified control in the "
            "knowledge catalog. A phrase like 'turn off MB interactions' is "
            "not executable: run urqmd.source_search / urqmd.describe_option "
            "and select a catalogued control (see urqmd.list_interventions)",
            data={"requested": intervention,
                  "catalog_keys": sorted(_catalog_entries())},
            provenance={"tool": "urqmd.validate_intervention"})
    entry = _public_entry(key, _catalog_entries()[key])
    warnings = [f"collateral effect: {c}"
                for c in entry.get("collateral_effects", [])]
    warnings.append("execution is disabled in the MVP; validation is "
                    "informational only")
    targets = None
    if target_mediator is not None:
        med = target_mediator.lower()
        if "mb" in med or "resonance formation" in med:
            targets = bool(entry.get("affects_mb_resonance_formation"))
            if not targets:
                warnings.append(
                    f"{key} does not target MB resonance formation per the "
                    "catalog")
        else:
            warnings.append(
                f"mediator {target_mediator!r} is not a recognized catalog "
                "keyword; targeting cannot be assessed — inspect "
                "affected_channels/removes fields directly")
    data = {
        "intervention": key, "requested": intervention,
        "hypothesis": hypothesis, "target_mediator": target_mediator,
        "targets_mediator": targets,
        "execution_allowed": False,
        **entry,
    }
    summary = (f"{key} [{entry['type']}, {entry['role']}]: "
               f"{entry.get('description', '')} — execution_allowed=False "
               "(MVP)")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "urqmd.validate_intervention"})


def plan_intervention(hypothesis: str, mediator: str,
                      desired_perturbation: Optional[str] = None
                      ) -> ToolResult:
    """Propose source-verified candidate controls for a hypothesis. It is a
    VALID result that no clean existing intervention exists."""
    entries = _catalog_entries()
    candidates = [_public_entry(k, v) for k, v in entries.items()]
    med = mediator.lower()
    result = "CANDIDATES LISTED"
    notes = []
    if "mb" in med and "resonance" in med:
        exact = [c for c in candidates
                 if c["name"] == "MB_ONLY_PATCH"]
        partial = [c for c in candidates
                   if c.get("affects_mb_resonance_formation")
                   and c["name"] != "MB_ONLY_PATCH"]
        notes.append(
            "MB-only s-channel resonance removal: the exact control "
            "MB_ONLY_PATCH is DESIGNED_NOT_IMPLEMENTED (source patch, never "
            "implemented); the existing runtime control CTOption(15) also "
            "removes MM resonance formation (PARTIAL, collateral)")
        if exact and exact[0]["status"] == "DESIGNED_NOT_IMPLEMENTED":
            result = "NO CLEAN EXISTING INTERVENTION"
        candidates = partial + exact + [
            c for c in candidates
            if c not in partial and c not in exact]
    data = {
        "hypothesis": hypothesis, "mediator": mediator,
        "desired_perturbation": desired_perturbation,
        "result": result,
        "candidates": candidates,
        "execution_enabled": False,
        "notes": notes,
    }
    summary = (f"{result}: {len(candidates)} candidate control(s) for "
               f"mediator {mediator!r}; execution disabled in the MVP")
    return ToolResult.ok(summary, data, warnings=notes,
                         provenance={"tool": "urqmd.plan_intervention"})


def run_intervention(intervention: str = "", run_dir: str = "",
                     authorization: str = "", nev: int = 1100,
                     ecm: float = 7.7) -> ToolResult:
    """Execute a preregistered intervention condition.

    Phase-2C execution policy: PHYSICS_INTERVENTION is enabled ONLY for
    the frozen whitelist (cto15_1 / cto59_0 / tim12 / tim8) with the frozen
    seed set, frozen event count (1100) and frozen energy (7.7 GeV), and
    only with the explicit human authorization token. Any deviation remains
    blocked. 'baseline' is not an intervention and is not executable
    through this tool.

    Phase-1D/2D extension: the confirmatory MB-only condition 'mb_only'
    (MB_ONLY_PATCH, CTOption(100)=1 on the locally patched executable) is
    executable ONLY with authorization='phase1d-confirmatory', with the
    same frozen seeds/event count/energy. All other SOURCE_MODIFICATION
    remains blocked.
    """
    from ..production import intervention_campaign as ic
    from ..production import mbonly_campaign as mc

    if intervention == "baseline":
        raise GuardrailError(
            "'baseline' is not an intervention; use urqmd.run")
    if intervention in ("mb_only", "MB_ONLY_PATCH_CONFIRMATORY"):
        if authorization != "phase1d-confirmatory":
            raise GuardrailError(
                "missing/invalid human authorization token; the mb_only "
                "confirmatory intervention requires "
                "authorization='phase1d-confirmatory'")
        mc.validate_mbonly(nev=nev, ecm=ecm)
        if not run_dir:
            raise GuardrailError("run_dir is required")
        rel = check_output_dir(run_dir)
        summary = mc.run_mbonly(Path(rel))
        return ToolResult.ok(
            f"intervention mb_only ({summary['kind']}) completed: "
            f"{summary['n_events']} events, closure-validated",
            data=summary,
            provenance={"tool": "urqmd.run_intervention",
                        "whitelist": "phase1d",
                        "spec": "MB_ONLY_PATCH confirmatory "
                                "(physics_gate/phase1d/phase1d_protocol.md)"})
    if authorization != "phase1c-preregistered":
        raise GuardrailError(
            "missing/invalid human authorization token; intervention "
            "execution requires authorization='phase1c-preregistered'")
    spec = ic.validate_preregistered_intervention(intervention, nev=nev,
                                                  ecm=ecm)
    if not run_dir:
        raise GuardrailError("run_dir is required")
    rel = check_output_dir(run_dir)
    summary = ic.run_condition(intervention, Path(rel))
    return ToolResult.ok(
        f"intervention {intervention} ({spec.kind}) completed: "
        f"{summary['n_events']} events, closure-validated",
        data=summary,
        provenance={"tool": "urqmd.run_intervention",
                    "whitelist": "phase1c", "spec": spec.description})


register(ToolSpec(
    name="urqmd.list_interventions",
    description=(
        "List the source-verified intervention catalog: type (CHANNEL "
        "REMOVAL / EVOLUTION-TIME TRUNCATION / FINAL-DECAY MODIFICATION), "
        "role, collateral effects and execution status. Listing only — "
        "execution of every intervention is disabled."),
    input_schema={"type": "object", "properties": {}, "required": []},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=list_interventions,
))

register(ToolSpec(
    name="urqmd.validate_intervention",
    description=(
        "Validate a proposed intervention against the source-verified "
        "catalog: reports what it actually does, collateral effects, "
        "runtime vs source-modification, and whether it targets the given "
        "mediator (keyword-based, catalog fields only). Free-form phrases "
        "like 'turn off MB interactions' are rejected with an error. "
        "execution_allowed is ALWAYS false in the MVP."),
    input_schema={"type": "object", "properties": {
        "intervention": {"type": "string",
                         "description": "catalog key, e.g. 'CTOption(15)', "
                                        "'cto 59', 'tim', 'MB_ONLY_PATCH'"},
        "target_mediator": {"type": "string"},
        "hypothesis": {"type": "string"}},
        "required": ["intervention"]},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=validate_intervention,
))

register(ToolSpec(
    name="urqmd.plan_intervention",
    description=(
        "Given a hypothesis and mediator, return candidate source-verified "
        "controls from the catalog. Returning "
        "'NO CLEAN EXISTING INTERVENTION' is a valid outcome. Planning "
        "only; nothing is executed."),
    input_schema={"type": "object", "properties": {
        "hypothesis": {"type": "string"},
        "mediator": {"type": "string"},
        "desired_perturbation": {"type": "string"}},
        "required": ["hypothesis", "mediator"]},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=plan_intervention,
))

register(ToolSpec(
    name="urqmd.run_intervention",
    description=(
        "Execute a preregistered intervention condition. Gated by frozen "
        "whitelists, frozen seed set, frozen 1100 events, frozen 7.7 GeV, "
        "and human authorization tokens: Phase-1C conditions (cto15_1 / "
        "cto59_0 / tim12 / tim8) require 'phase1c-preregistered'; the "
        "Phase-1D confirmatory MB-only condition (mb_only, locally patched "
        "executable) requires 'phase1d-confirmatory'. Any other source "
        "modification remains blocked."),
    input_schema={"type": "object", "properties": {
        "intervention": {"type": "string",
                         "description": "whitelist key: cto15_1 | cto59_0 | "
                                        "tim12 | tim8 (phase1c) | mb_only "
                                        "(phase1d)"},
        "run_dir": {"type": "string",
                    "description": "inside an allowed output directory"},
        "authorization": {"type": "string",
                          "description": "human token "
                                         "'phase1c-preregistered' or "
                                         "'phase1d-confirmatory' (mb_only)"},
        "nev": {"type": "integer", "description": "must equal 1100"},
        "ecm": {"type": "number", "description": "must equal 7.7"}},
        "required": ["intervention", "run_dir", "authorization"]},
    output_schema={"type": "object"},
    risk_level=PHYSICS_INTERVENTION,
    requires_urqmd=True,
    physics_changing=True,
    execution_enabled=True,
    whitelist_gated=True,
    handler=run_intervention,
))
