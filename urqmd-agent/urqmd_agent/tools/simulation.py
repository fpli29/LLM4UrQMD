"""Simulation tools: input-deck rendering and capped event production.

Decks are rendered from the validated production template
(urqmd_agent/production/campaign.py::INPUT_TEMPLATE); running goes through
production/provenance_campaign.run_one_event, which performs per-event
parse/validation/closure and raises on any failure. Nothing here
reimplements parsing.
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..agent.guardrails import (check_ctoption, check_event_count,
                                check_output_dir)
from ..core import paths
from ..core.errors import GuardrailError, ToolError
from ..core.result import ToolResult
from ..production.campaign import INPUT_TEMPLATE
from ..production.provenance_campaign import (PROVENANCE_COLUMNS,
                                              SUMMARY_COLUMNS,
                                              ProvenanceValidationError,
                                              run_one_event)
from ._common import load_catalog
from .registry import READ_ONLY, SIMULATION, ToolSpec, register

_F15_SUPPRESS_LINE = (
    "f15               # suppress unit 15 history output in production runs\n")

#: CTOption indices already pinned by the validated template
_TEMPLATE_CTOS = {5: 1, 56: 1}


def _render_deck(ecm: float, nev: int, seed: int, history: bool,
                 tim: Optional[list], ctoptions: Optional[Dict[int, int]]
                 ) -> str:
    text = INPUT_TEMPLATE.format(ecm=ecm, nev=nev, rsd=seed)
    if history:
        if _F15_SUPPRESS_LINE not in text:
            raise ToolError("input template no longer contains the f15 "
                            "suppression line; template changed upstream")
        text = text.replace(_F15_SUPPRESS_LINE, "")
    if tim is not None:
        if len(tim) != 2:
            raise ToolError("tim must be a 2-element list [t_main, t_out]")
        text = text.replace("tim 200 200\n",
                            f"tim {tim[0]} {tim[1]}\n", 1)
        if f"tim {tim[0]} {tim[1]}\n" not in text:
            raise ToolError("could not substitute the tim line in the "
                            "template")
    if ctoptions:
        extra = "".join(f"cto {idx} {val}\n"
                        for idx, val in sorted(ctoptions.items()))
        if "\nxxx\n" not in text:
            raise ToolError("input template terminator 'xxx' not found")
        text = text.replace("\nxxx\n", "\n" + extra + "xxx\n", 1)
    return text


def make_input(ecm: float, nev: int, seed: int, history: bool = True,
               tim: Optional[list] = None, ctoptions: Optional[dict] = None,
               described_ctoptions: Optional[list] = None,
               out_path: Optional[str] = None) -> ToolResult:
    """Render a validated UrQMD input deck. NEVER executes anything."""
    ctos: Dict[int, int] = {}
    if ctoptions:
        catalog = load_catalog()
        described = set(described_ctoptions or [])
        for raw_idx, raw_val in ctoptions.items():
            idx, val = int(raw_idx), int(raw_val)
            key = f"CTOption({idx})"
            if key not in catalog["options"] or \
                    catalog["options"][key].get("kind") != "CTOption":
                raise GuardrailError(
                    f"CTOption({idx}) is not in the verified knowledge "
                    "catalog; refusing to write an undocumented option "
                    "(run urqmd.describe_option / urqmd.source_search first)")
            check_ctoption(idx, val, described=idx in described)
            if idx in _TEMPLATE_CTOS:
                if _TEMPLATE_CTOS[idx] == val:
                    continue        # idempotent with the template
                raise GuardrailError(
                    f"CTOption({idx}) conflicts with the validated template "
                    f"value {_TEMPLATE_CTOS[idx]}; overriding template-pinned "
                    "options is not allowed")
            ctos[idx] = val
    text = _render_deck(ecm, nev, seed, history, tim, ctos)
    data = {
        "ecm": ecm, "nev": nev, "seed": seed, "history": history,
        "tim": tim, "ctoptions_applied": ctos,
        "deck_text": text,
    }
    warnings = []
    if tim is not None:
        warnings.append(
            "tim is a BROAD evolution-time truncation acting identically on "
            "all channels (see urqmd.describe_option 'tim')")
    if out_path is not None:
        rel = check_output_dir(Path(out_path))
        dest = paths.REPO_ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        data["deck_path"] = str(rel)
        data.pop("deck_text")
        summary = f"deck written to {rel} (ecm={ecm}, nev={nev}, seed={seed})"
    else:
        summary = (f"deck rendered in memory (ecm={ecm}, nev={nev}, "
                   f"seed={seed}, history={history}); nothing executed")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "urqmd.make_input",
                                     "template": "production.campaign."
                                                 "INPUT_TEMPLATE"})


def run(ecm: float, nev: int, seed: int, run_dir: str,
        keep_raw: bool = False,
        authorized_cap: Optional[int] = None) -> ToolResult:
    """Run `nev` capped single events with f13+f15 and per-event closure."""
    check_event_count(nev, authorized_cap)
    rel_dir = check_output_dir(Path(run_dir))
    # UrQMD reads ftnNN paths into character*77 buffers (input.f:23): the
    # runner must receive the SHORT repo-relative path (the subprocess runs
    # with cwd=REPO_ROOT), never the absolute one. run_one_event resolves
    # those relative paths against the process cwd, so anchor the process
    # at REPO_ROOT first — the caller's cwd may differ when URQMD_HOME
    # points outside this checkout.
    os.chdir(paths.REPO_ROOT)
    workdir = Path(rel_dir)
    (paths.REPO_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)

    run_id = f"ecm{ecm}_rsd{seed}_nev{nev}"
    seeds = [seed + i for i in range(nev)]
    summaries: List[dict] = []
    n_records = 0
    audit_files: List[str] = []
    t0 = time.time()
    try:
        for i in range(nev):
            summary, records, _gen, audit, _wall = run_one_event(
                ecm, seeds[i], workdir, keep_raw=keep_raw,
                event_ordinal=i + 1)
            summaries.append(summary)
            n_records += len(records)
            if audit:
                audit_files.extend(str(p) for p in audit)
    except ProvenanceValidationError as exc:
        return ToolResult.error(
            f"per-event validation failed (run {run_id}, event "
            f"{len(summaries) + 1}): {exc}",
            data={"run_id": run_id, "events_completed": len(summaries)},
            provenance={"tool": "urqmd.run"})
    except RuntimeError as exc:
        tail = ""
        logs = sorted(workdir.glob("*.log"),
                      key=lambda p: p.stat().st_mtime)
        if logs:
            tail = "\n".join(logs[-1].read_text(
                errors="replace").splitlines()[-30:])
        return ToolResult.error(
            f"UrQMD run failed (run {run_id}, event "
            f"{len(summaries) + 1}): {exc}",
            data={"run_id": run_id, "events_completed": len(summaries),
                  "log_tail": tail},
            provenance={"tool": "urqmd.run"})
    wall = time.time() - t0

    summary_csv = workdir / f"summary_{run_id}.csv"
    with summary_csv.open("w", newline="") as sf:
        writer = csv.DictWriter(sf, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        writer.writerows(summaries)

    closure_ok = True   # run_one_event raises on any closure failure
    record = {
        "run_id": run_id,
        "tool": "urqmd.run",
        "ecm": ecm, "nev": nev, "seeds": seeds,
        "run_dir": str(rel_dir),
        "wall_seconds": wall,
        "events_completed": len(summaries),
        "n_provenance_records": n_records,
        "closure_validation": "passed" if closure_ok else "FAILED",
        "keep_raw": keep_raw,
        "output_files": [str(summary_csv)] + audit_files,
    }
    record_path = workdir / "run_record.json"
    record_path.write_text(json.dumps(record, indent=1))

    summary = (f"run {run_id}: {len(summaries)}/{nev} events completed, "
               f"per-event closure validation passed, {wall:.1f}s wall; "
               f"summary CSV + run_record.json in {rel_dir}")
    return ToolResult.ok(summary, record,
                         provenance={"tool": "urqmd.run",
                                     "runner": "production.provenance_"
                                               "campaign.run_one_event"})


def run_status(run_id: Optional[str] = None) -> ToolResult:
    """Report run records found under the allowed output directories."""
    records = []
    for allowed in paths.ALLOWED_OUTPUT_DIRS:
        root = paths.REPO_ROOT / allowed if not allowed.is_absolute() \
            else allowed
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("run_record.json")):
            try:
                rec = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise ToolError(f"unreadable run record {p}: {exc}") from exc
            if run_id is not None and rec.get("run_id") != run_id:
                continue
            rec["record_path"] = str(p.relative_to(paths.REPO_ROOT))
            records.append(rec)
    if run_id is not None and not records:
        return ToolResult.error(
            f"no run record with run_id {run_id!r} under the allowed "
            "output directories",
            provenance={"tool": "urqmd.run_status"})
    summary = (f"{len(records)} run record(s)"
               + (f" for run_id {run_id!r}" if run_id else ""))
    return ToolResult.ok(summary, {"runs": records},
                         provenance={"tool": "urqmd.run_status"})


register(ToolSpec(
    name="urqmd.make_input",
    description=(
        "Render a validated UrQMD 4.0 input deck from the production "
        "template (Au+Au, ecm, nev, rsd; history=True keeps file15 output). "
        "GUARDRAIL: every requested CTOption must be listed in "
        "described_ctoptions AND exist in the verified knowledge catalog, "
        "otherwise the call is blocked. Options pinned by the template "
        "(CTOption 5 and 56) cannot be overridden. This tool NEVER executes "
        "UrQMD; it only renders (and optionally writes) a deck."),
    input_schema={"type": "object", "properties": {
        "ecm": {"type": "number", "description": "sqrt(s_NN) [GeV]"},
        "nev": {"type": "integer"},
        "seed": {"type": "integer"},
        "history": {"type": "boolean", "default": True,
                    "description": "True = produce file15 history"},
        "tim": {"type": "array", "items": {"type": "number"},
                "description": "optional [t_main, t_out] replacement"},
        "ctoptions": {"type": "object",
                      "description": "{index: value}; each index must be "
                                     "described and catalog-verified"},
        "described_ctoptions": {"type": "array", "items": {"type": "integer"},
                                "description": "indices the caller has "
                                               "described via urqmd.describe_option"},
        "out_path": {"type": "string",
                     "description": "optional write location; must be inside "
                                    "an allowed output directory"}},
        "required": ["ecm", "nev", "seed"]},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    requires_urqmd=True,
    handler=make_input,
))

register(ToolSpec(
    name="urqmd.run",
    description=(
        "Run up to the event cap (default 100, raisable only via an explicit "
        "authorized_cap) of single-event UrQMD runs with f13+f15 output, "
        "per-event strict parsing and exact Lambda/K0 closure validation, "
        "into an allowed run directory. Writes summary CSV and "
        "run_record.json. A nonzero UrQMD exit or a validation failure is "
        "reported as status=error with the log tail. Does NOT accept "
        "physics-changing options; use make_input to inspect deck changes."),
    input_schema={"type": "object", "properties": {
        "ecm": {"type": "number"},
        "nev": {"type": "integer"},
        "seed": {"type": "integer"},
        "run_dir": {"type": "string",
                    "description": "output dir inside an allowed output "
                                   "directory (e.g. under physics_gate/agent_runs)"},
        "keep_raw": {"type": "boolean", "default": False},
        "authorized_cap": {"type": "integer",
                           "description": "explicit user-authorized event cap"}},
        "required": ["ecm", "nev", "seed", "run_dir"]},
    output_schema={"type": "object"},
    risk_level=SIMULATION,
    requires_urqmd=True,
    handler=run,
))

register(ToolSpec(
    name="urqmd.run_status",
    description=(
        "List run records (run_record.json) under the allowed output "
        "directories, or the one matching run_id: status, event counts, "
        "closure validation state, output files. Read-only."),
    input_schema={"type": "object", "properties": {
        "run_id": {"type": "string"}}, "required": []},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    requires_urqmd=False,
    handler=run_status,
))
