"""Source/knowledge inspection tools (read-only, never run UrQMD).

All physics semantics come from the human-reviewed knowledge snapshot
(urqmd_agent/knowledge/urqmd_v4.json) or from the source-verified Python
mapping modules. Unknown options/particles/processes are errors, never
guesses.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..core import paths
from ..core.errors import ToolError
from ..core.result import ToolResult
from ..history.taxonomy import PROCESS_INFO, _SPLIT_BY_NOUT, classify
from ..particles import resonance_families as rf
from ._common import load_catalog
from .registry import READ_ONLY, ToolSpec, register

_SOURCE_GLOBS = ("*.f", "*.f90", "*.mk")

#: source-verified PDG <-> (ityp, iso3) ground-state table
#: (urqmd_agent/particles/properties.py, from ityp2pdg.f)
_PDG_TO_ITYP_ISO3 = {
    2212: (1, 1), 2112: (1, -1), -2212: (-1, -1), -2112: (-1, 1),
    211: (101, 2), 111: (101, 0), -211: (101, -2),
    321: (106, 1), 311: (106, -1), -321: (-106, -1), -311: (-106, 1),
    3122: (41, 0), -3122: (-41, 0),
}
_VERIFIED_CHARGES = {
    (1, 1): 1, (1, -1): 0, (-1, -1): -1, (-1, 1): 0,
    (101, 2): 1, (101, 0): 0, (101, -2): -1,
    (106, 1): 1, (106, -1): 0, (-106, -1): -1, (-106, 1): 0,
    (41, 0): 0, (-41, 0): 0,
}


def source_search(term: str, file_filter: Optional[str] = None,
                  max_hits: int = 20) -> ToolResult:
    """Deterministic case-insensitive regex search over UrQMD source files."""
    try:
        pattern = re.compile(term, re.IGNORECASE)
    except re.error as exc:
        raise ToolError(f"invalid regex {term!r}: {exc}") from exc
    hits = []
    files_scanned = 0
    for glob in _SOURCE_GLOBS:
        for path in sorted(paths.REPO_ROOT.rglob(glob)):
            if ".git" in path.parts or not path.is_file():
                continue
            if file_filter and not path.match(file_filter):
                # file_filter is a basename glob such as "make22.f"
                if not Path(path.name).match(file_filter):
                    continue
            files_scanned += 1
            try:
                with path.open("r", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if pattern.search(line):
                            hits.append({
                                "file": str(path.relative_to(paths.REPO_ROOT)),
                                "line": lineno,
                                "snippet": line.rstrip("\n")[:200],
                            })
                            if len(hits) >= max_hits:
                                break
                if len(hits) >= max_hits:
                    break
            except OSError as exc:
                raise ToolError(f"cannot read {path}: {exc}") from exc
            if len(hits) >= max_hits:
                break
        if len(hits) >= max_hits:
            break
    warnings = []
    if len(hits) >= max_hits:
        warnings.append(f"hit cap reached ({max_hits}); refine the search")
    summary = (f"{len(hits)} hit(s) for {term!r} over {files_scanned} "
               f"source file(s)"
               + (f" matching {file_filter!r}" if file_filter else ""))
    return ToolResult.ok(summary, {"term": term, "hits": hits,
                                   "files_scanned": files_scanned,
                                   "truncated": len(hits) >= max_hits},
                         warnings=warnings,
                         provenance={"tool": "urqmd.source_search"})


def _normalize_option_key(option: str) -> str:
    """Map free-form option spellings onto catalog keys."""
    text = option.strip()
    m = re.match(r"^(?:ctoption|cto)\s*\(?\s*(\d+)\s*\)?$", text,
                 re.IGNORECASE)
    if m:
        return f"CTOption({m.group(1)})"
    if re.match(r"^\d+$", text):
        return f"CTOption({text})"
    if re.match(r"^f(13|14|15|16|19|20)$", text, re.IGNORECASE):
        return "f13_f14_f15_f16_f19_f20_keywords"
    return text


def describe_option(option: str) -> ToolResult:
    """Describe one runtime option from the VERIFIED catalog only."""
    catalog = load_catalog()
    key = _normalize_option_key(option)
    entry = catalog["options"].get(key)
    if entry is None:
        return ToolResult.error(
            f"option {option!r} (normalized: {key!r}) is not in the verified "
            "catalog; run urqmd.source_search first and never guess option "
            "semantics",
            data={"option": option, "catalog_keys": sorted(catalog["options"])},
            provenance={"tool": "urqmd.describe_option"})
    data = {"option": key, "requested": option}
    data.update(entry)
    # surface the flat fields the agent needs for planning
    data.setdefault("default", entry.get("default"))
    data.setdefault("affected_channels", entry.get("affected_channels", []))
    data.setdefault("collateral_effects", entry.get("collateral_effects", []))
    data.setdefault("runtime_settable", entry.get("runtime_settable"))
    data.setdefault("physics_changing", entry.get("physics_changing"))
    data.setdefault("intervention_role", entry.get("intervention_role"))
    summary = f"{key}: {entry.get('description', '')}"
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.describe_option",
                                     "catalog": str(paths.KNOWLEDGE_SNAPSHOT)})


def describe_particle(ityp: Optional[int] = None, iso3: Optional[int] = None,
                      pdg: Optional[int] = None) -> ToolResult:
    """Describe a particle from the source-verified (ityp, iso3) mapping."""
    if pdg is not None:
        if pdg not in _PDG_TO_ITYP_ISO3:
            return ToolResult.error(
                f"pdg {pdg} is not in the source-verified ground-state "
                "table; unknown particles are never guessed",
                provenance={"tool": "urqmd.describe_particle"})
        ityp, iso3 = _PDG_TO_ITYP_ISO3[pdg]
    if ityp is None:
        return ToolResult.error("describe_particle needs ityp or pdg",
                                provenance={"tool": "urqmd.describe_particle"})
    if ityp == 0:
        return ToolResult.error("ityp 0 is not a particle",
                                provenance={"tool": "urqmd.describe_particle"})
    try:
        is_bar, is_mes = rf.is_baryon(ityp), rf.is_meson(ityp)
        if not (is_bar or is_mes or rf.is_pythia(ityp)):
            raise ValueError
        family = rf.family_of(ityp, iso3 or 0)
        multiplet = rf.multiplet_of(ityp)
        strit = rf.strit(ityp)
        resonance = rf.is_resonance(ityp)
    except ValueError:
        return ToolResult.error(
            f"ityp {ityp} is outside the source-verified UrQMD 4.0 tables "
            "(baryons 1-70, mesons 100-139, PYTHIA |ityp|>1000); never "
            "guessing particle identity",
            provenance={"tool": "urqmd.describe_particle"})

    catalog = load_catalog()
    canonical = None
    for name, p in catalog["particles"].items():
        if p["ityp"] == ityp and p["iso3"] == (iso3 if iso3 is not None
                                               else p["iso3"]):
            canonical = name
            break
    pdg_id = None
    if iso3 is not None:
        for k, v in _PDG_TO_ITYP_ISO3.items():
            if v == (ityp, iso3):
                pdg_id = k
                break
    charge = _VERIFIED_CHARGES.get((ityp, iso3)) if iso3 is not None else None
    warnings = []
    if iso3 is None:
        warnings.append("iso3 not given: multiplet-level description only; "
                        "charge/PDG member not resolved")
    if iso3 is not None and charge is None:
        warnings.append("charge not in the verified ground-state table; "
                        "left null rather than guessed")
    data = {
        "ityp": ityp, "iso3": iso3, "pdg": pdg_id,
        "canonical_species": canonical,
        "multiplet": multiplet,
        "family": family,
        "charge": charge,
        "strit": strit,
        "physical_strangeness": -strit,
        "baryon": is_bar, "meson": is_mes,
        "resonance": resonance,
        "convention": catalog["particle_notes"]["strangeness_convention"],
    }
    kind = "baryon" if is_bar else ("meson" if is_mes else "PYTHIA")
    summary = (f"ityp={ityp} iso3={iso3}: {canonical or multiplet} "
               f"({kind}, family {family}, strit={strit} -> physical "
               f"S={-strit}, {'resonance' if resonance else 'stable'})")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "urqmd.describe_particle"})


def describe_process(process_id: int, nout: Optional[int] = None
                     ) -> ToolResult:
    """Describe a file15 process id (iline) from the verified taxonomy."""
    catalog = load_catalog()
    entry = catalog["processes"].get(str(process_id))
    known = process_id in PROCESS_INFO or process_id in _SPLIT_BY_NOUT
    if entry is None or not known:
        return ToolResult.error(
            f"process id {process_id} is not in the verified taxonomy; "
            "run urqmd.source_search to locate its source semantics first",
            data={"process_id": process_id},
            provenance={"tool": "urqmd.describe_process"})
    if process_id in _SPLIT_BY_NOUT and nout is None:
        cls = "MB_or_STRING"
        is_elastic = False
        warnings = ["process 27 splits by outgoing multiplicity: nout==1 -> "
                    "MB (anndec resonance fallback), nout>1 -> STRING; "
                    "pass nout for the resolved class"]
    else:
        cls, is_elastic = classify(process_id, nout if nout is not None else 1)
        warnings = []
    data = {
        "process_id": process_id, "nout": nout,
        "class": cls, "coarse_class": cls, "is_elastic": is_elastic,
        "description": entry.get("description", ""),
        "source_refs": entry.get("source_refs", []),
        "caveats": entry.get("caveats", []),
    }
    summary = (f"process {process_id}"
               + (f" nout={nout}" if nout is not None else "")
               + f": class {cls} — {entry.get('description', '')}")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "urqmd.describe_process"})


register(ToolSpec(
    name="urqmd.source_search",
    description=(
        "Deterministic case-insensitive regex search over the UrQMD Fortran "
        "source (*.f/*.f90/*.mk). Use this to verify semantics in the source "
        "before trusting any claim. Read-only; never modifies or runs code."),
    input_schema={"type": "object", "properties": {
        "term": {"type": "string", "description": "regex to search for"},
        "file_filter": {"type": "string",
                        "description": "optional basename glob, e.g. 'make22.f'"},
        "max_hits": {"type": "integer", "default": 20}},
        "required": ["term"]},
    output_schema={"type": "object", "description": "ToolResult with "
                   "data.hits = [{file, line, snippet}]"},
    risk_level=READ_ONLY,
    handler=source_search,
))

register(ToolSpec(
    name="urqmd.describe_option",
    description=(
        "Describe one UrQMD runtime option (e.g. '15', 'CTOption(15)', "
        "'cto 15', 'tim', 'f15') from the human-reviewed, source-verified "
        "knowledge catalog. Returns default, source references, affected "
        "channels, collateral effects, runtime-settability and whether the "
        "option changes physics. NEVER guesses: unknown options return an "
        "error telling you to run urqmd.source_search first."),
    input_schema={"type": "object", "properties": {
        "option": {"type": "string",
                   "description": "e.g. '15', 'CTOption(15)', 'cto 59', 'tim', 'f15'"}},
        "required": ["option"]},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=describe_option,
))

register(ToolSpec(
    name="urqmd.describe_particle",
    description=(
        "Describe a particle from the source-verified UrQMD (ityp, iso3) "
        "mapping: multiplet, resonance family, strit and physical "
        "strangeness (S = -strit), baryon/meson, resonance status "
        "(widit>0), and charge/PDG where source-verified. Unknown "
        "(ityp, iso3) or PDG ids are errors, never guesses."),
    input_schema={"type": "object", "properties": {
        "ityp": {"type": "integer"},
        "iso3": {"type": "integer"},
        "pdg": {"type": "integer"}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=describe_particle,
))

register(ToolSpec(
    name="urqmd.describe_process",
    description=(
        "Describe a file15 process id (iline): coarse class from the "
        "source-verified taxonomy (DECAY/STRING/BB/MB/MM/STRX/ELASTIC/"
        "ANNIHILATION), source locations and caveats. Process 27 needs "
        "nout to resolve (nout==1 -> MB, nout>1 -> STRING). Unknown ids "
        "are errors."),
    input_schema={"type": "object", "properties": {
        "process_id": {"type": "integer"},
        "nout": {"type": "integer",
                 "description": "outgoing multiplicity; resolves process 27"}},
        "required": ["process_id"]},
    output_schema={"type": "object"},
    risk_level=READ_ONLY,
    handler=describe_process,
))
