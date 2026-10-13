"""Phase B4-A (azimuth-blind within-event label-permutation nulls for
the D-A cross-dipole) read-only tools.

These tools expose the persisted Phase B4-A deliverables
(physics_gate/phaseB4A/analysis/*.csv and *.json). They never run
UrQMD, never open raw shards, never permute anything, and never
execute user-supplied code. Every number they report is copied from
the frozen analysis CSVs/JSON at call time, so the tools and the CSV
deliverables agree by construction.

Null-semantics discipline (frozen): N0/N1/N2 are azimuth-blind
within-event label permutations on frozen B3-B events. The physical
event — momenta, multiplicities, population sizes and the set totals —
is preserved exactly; only the microscopic D/A labels are permuted.
N1 additionally preserves pT-y composition (N2 adds formation class);
stratification restricts label mobility, which is reported via the
frozen mobility table and never relaxed. All quantities are
attribution-level tabulations, not mechanism statements.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b4a`` registers the ten ``b4a.*`` tools
in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b4a list
    python3 -m urqmd_agent.tools.azimuthal_b4a call \\
        b4a.real_null_contrast '{"cell": "minbias"}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis drivers (support flags, rule text, definitions) are
passed through verbatim as data.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.errors import ToolError
from ..core.result import ToolResult
from .registry import ANALYSIS, ToolSpec, register

REPO_ROOT = Path(__file__).resolve().parents[2]
B4A_DIR = REPO_ROOT / "physics_gate" / "phaseB4A"
B3B_DIR = REPO_ROOT / "physics_gate" / "phaseB3B"
DEFAULT_ANALYSIS_DIR = B4A_DIR / "analysis"
B3B_ANALYSIS_DIR = B3B_DIR / "analysis"

CELLS = ("minbias", "pooled_b3", "bin0", "bin1", "bin2")
NULLS = ("N0", "N1", "N2")
ARMS = ("REAL", "N0", "N1", "N2")
CLS3 = ("DD", "DA", "AA")
WIDTHS = ("60.0", "90.0", "120.0", "180.0")

_cache: Dict[str, Any] = {}


def _read_csv(path: Path, hint: str) -> List[Dict[str, str]]:
    if not path.is_file():
        raise ToolError(f"{path} not found; {hint}")
    key = f"csv:{path}:{path.stat().st_mtime_ns}"
    if key not in _cache:
        _cache.clear()
        with path.open(newline="") as fh:
            _cache[key] = list(csv.DictReader(fh))
    return _cache[key]


def _read_json(path: Path, hint: str) -> Dict[str, Any]:
    if not path.is_file():
        raise ToolError(f"{path} not found; {hint}")
    key = f"json:{path}:{path.stat().st_mtime_ns}"
    if key not in _cache:
        _cache.clear()
        _cache[key] = json.loads(path.read_text())
    return _cache[key]


_HINT = ("the frozen Phase B4-A deliverables are missing; the null "
         "driver outputs under physics_gate/phaseB4A/analysis/ must "
         "exist first")


def _csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_csv(d / fname, _HINT)


def _json(analysis_dir: Optional[str], fname: str) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_json(d / fname, _HINT)


def _b3b_csv(fname: str) -> List[Dict[str, str]]:
    return _read_csv(B3B_ANALYSIS_DIR / fname,
                     "the frozen Phase B3-B anchor deliverables under "
                     "physics_gate/phaseB3B/analysis/ must exist first")


def _f(x: str):
    if x is None or x == "":
        return None
    return float(x)


def _i(x: str):
    if x is None or x == "":
        return None
    return int(x)


def _check_cell(cell: Optional[str], tool: str) -> None:
    if cell is not None and cell not in CELLS:
        raise ToolError(f"cell must be one of {CELLS}",
                        provenance={"tool": tool})


def _check_null(null: Optional[str], tool: str) -> None:
    if null is not None and null not in NULLS:
        raise ToolError(f"null must be one of {NULLS}",
                        provenance={"tool": tool})


def _check_arm(arm: Optional[str], tool: str) -> None:
    if arm is not None and arm not in ARMS:
        raise ToolError(f"arm must be one of {ARMS}",
                        provenance={"tool": tool})


def _meta(analysis_dir: Optional[str]) -> Dict[str, Any]:
    return _json(analysis_dir, "phaseB4A_null_metadata.json")


def _pair_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "width_deg": _f(r["width_deg"]),
        "class": r["class"],
        "n_events": _i(r["n_events"]),
        "n_contributing_events": _i(r["n_contributing_events"]),
        "n_pairs": _i(r["n_pairs"]),
        "support": r["support"],
        "F": _f(r["F"]), "F_sd": _f(r["F_sd"]),
        "Delta_c": _f(r["Delta_c"]), "Delta_c_sd": _f(r["Delta_c_sd"]),
        "Delta_c_ci": [_f(r["Delta_c_ci_lo"]), _f(r["Delta_c_ci_hi"])],
        "contribution": _f(r["contribution"]),
        "contribution_sd": _f(r["contribution_sd"]),
        "contribution_ci": [_f(r["contribution_ci_lo"]),
                            _f(r["contribution_ci_hi"])],
        "C1_c": _f(r["C1_c"]), "C1_c_sd": _f(r["C1_c_sd"]),
        "C1_c_ci": [_f(r["C1_c_ci_lo"]), _f(r["C1_c_ci_hi"])],
        "C1_contribution": _f(r["C1_contribution"]),
        "C1_contribution_sd": _f(r["C1_contribution_sd"]),
        "C1_contribution_ci": [_f(r["C1_contribution_ci_lo"]),
                               _f(r["C1_contribution_ci_hi"])],
        "C2_c": _f(r["C2_c"]), "C3_c": _f(r["C3_c"]),
        "C2_contribution": _f(r["C2_contribution"]),
        "C3_contribution": _f(r["C3_contribution"])}


def _contrast_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "null": r["null"], "quantity": r["quantity"],
        "point": _f(r["point"]), "sd": _f(r["sd"]),
        "ci": [_f(r["ci_lo"]), _f(r["ci_hi"])],
        "ci_excludes_zero": not (_f(r["ci_lo"]) < 0 < _f(r["ci_hi"])),
        "real_point": _f(r["real_point"]), "real_sd": _f(r["real_sd"]),
        "null_point": _f(r["null_point"]), "null_sd": _f(r["null_sd"])}


def _mobility_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "sample": r["sample"], "cell": r["cell"], "null": r["null"],
        "n_events": _i(r["n_events"]),
        "n_particles": _i(r["n_particles"]),
        "frac_particles_exchangeable": _f(r["frac_particles_exchangeable"]),
        "frac_particles_frozen": _f(r["frac_particles_frozen"]),
        "mean_effective_swaps_per_event":
            _f(r["mean_effective_swaps_per_event"]),
        "frac_events_fully_frozen": _f(r["frac_events_fully_frozen"]),
        "mean_strata_per_event": _f(r["mean_strata_per_event"])}


def _additive_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "arm": r["arm"], "quantity": r["quantity"],
        "contribution_DD": _f(r["contribution_DD"]),
        "contribution_DA": _f(r["contribution_DA"]),
        "contribution_AA": _f(r["contribution_AA"]),
        "total": _f(r["total"]),
        "closure_residual": _f(r["closure_residual"]),
        "DA_sole_negative_carrier": r["DA_sole_negative_carrier"] == "True"}


def _mobility_caveat(analysis_dir: Optional[str]) -> Dict[str, Any]:
    rows = [_mobility_row(r)
            for r in _csv(analysis_dir, "phaseB4A_permutation_mobility.csv")
            if r["sample"] == "proton" and r["cell"] == "minbias"]
    mb = {r["null"]: r for r in rows}
    meta = _meta(analysis_dir)
    return {
        "mobility_rule": meta["mobility_rule"],
        "minbias_proton": mb,
        "note": ("stratification restricts label mobility: the N1 "
                 "exchangeable-particle fraction is well below N0 in "
                 "every cell; the frozen rule reports mobility and "
                 "never relaxes it, so the REAL-vs-N1 separation is a "
                 "conservative comparison against a partially "
                 "composition-preserving null with restricted "
                 "permutation support")}


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def null_status(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen B4-A null status: the hypotheses-lock reference and
    its sha256, the N0/N1/N2 null definitions with seeds and R, the
    estimator and shared-index bootstrap protocol, the support rule,
    the totals-invariance check across arms (from the frozen additive
    table), the analytic N0 null check verdict, and the N1 mobility
    caveat."""
    meta = _meta(analysis_dir)
    chk = _json(analysis_dir, "phaseB4A_analytic_null_check.json")
    add = [_additive_row(r)
           for r in _csv(analysis_dir, "phaseB4A_additive_contributions.csv")]
    tot: Dict[Any, list] = {}
    for r in add:
        tot.setdefault((r["cell"], r["quantity"]), []).append(r["total"])
    spread = max(max(v) - min(v) for v in tot.values())
    closure = max(abs(r["closure_residual"]) for r in add)
    data = {
        "phase": meta["phase"], "steps": meta["steps"],
        "hypotheses": meta["hypotheses"],
        "domain": meta["domain"],
        "nulls": meta["nulls"], "R": meta["R"],
        "seed_rule": meta["seed_rule"],
        "estimator": meta["estimator"],
        "bootstrap": meta["bootstrap"],
        "widths_deg": meta["widths_deg"],
        "support_rule": meta["support_rule"],
        "cells": meta["cells"],
        "totals_invariance": {
            "max_abs_total_spread_across_arms": spread,
            "max_abs_closure_residual": closure,
            "pass": spread < 1e-12 and closure < 1e-12,
            "note": ("set totals are identical across REAL and all "
                     "null arms by construction (labels-only "
                     "permutation)")},
        "analytic_null_check": {
            "null": chk["null"], "n_events": chk["n_events"],
            "overall": chk["overall"], "rule": chk["rule"],
            "z_threshold":
                meta["analytic_null_check"]["z_threshold"]},
        "mobility_caveat": _mobility_caveat(analysis_dir),
        "language_discipline_note": (
            "the frozen discipline text lives in null_metadata.json "
            "and hypotheses.md (azimuth-blind label permutations on "
            "frozen events; no dynamical intervention; attribution is "
            "not causation; possible-sources only; no unique ancestry "
            "for D2; class A never labeled as newly created; further "
            "mechanism-language prohibitions verbatim there)")}
    summary = (f"nulls N0/N1/N2 R={meta['R']}; analytic check "
               f"{chk['overall']}; totals spread {spread:.1e}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b4a.null_status", "inputs": {}})


def permutation_mobility(cell: Optional[str] = None,
                         null: Optional[str] = None,
                         analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """The frozen permutation-mobility table per sample, cell and null:
    exchangeable/frozen particle fractions, mean effective swaps per
    event, fully-frozen event fraction and mean strata per event.
    cell and null are optional filters; omitting both returns the full
    table (protons N0/N1/N2, all-B=+1 N0/N1)."""
    tool = "b4a.permutation_mobility"
    _check_cell(cell, tool)
    _check_null(null, tool)
    rows = [_mobility_row(r)
            for r in _csv(analysis_dir, "phaseB4A_permutation_mobility.csv")
            if (cell is None or r["cell"] == cell)
            and (null is None or r["null"] == null)]
    data = {"rows": rows,
            "mobility_rule": _meta(analysis_dir)["mobility_rule"],
            "note": ("mobility is a property of the frozen "
                     "stratification; it is reported, never relaxed")}
    summary = f"{len(rows)} mobility row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "null": null}})


def real_pair_structure(cell: Optional[str] = None,
                        width_deg: Optional[float] = None,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen REAL-arm accepted-proton pair structure per cell,
    kernel width and pair class (DD/DA/AA): pair counts and frozen
    support flags, pair-fraction F, class-level Delta_c and C1_c, and
    the additive contributions to the set Delta(w) and C1 with
    bootstrap SDs and 95% CIs. cell and width_deg (60/90/120/180) are
    optional filters."""
    tool = "b4a.real_pair_structure"
    _check_cell(cell, tool)
    if width_deg is not None and f"{float(width_deg)}" not in WIDTHS:
        raise ToolError(f"width_deg must be one of {WIDTHS}",
                        provenance={"tool": tool})
    rows = [_pair_row(r)
            for r in _csv(analysis_dir, "phaseB4A_real_pair_structure.csv")
            if (cell is None or r["cell"] == cell)
            and (width_deg is None
                 or r["width_deg"] == f"{float(width_deg)}")]
    meta = _meta(analysis_dir)
    data = {"rows": rows, "estimator": meta["estimator"],
            "support_rule": meta["support_rule"],
            "note": ("REAL arm reproduces the frozen B3-B "
                     "DD/DA/AA decomposition on the same events and "
                     "estimator")}
    summary = f"{len(rows)} REAL pair-structure row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "width_deg": width_deg}})


def null_pair_structure(null: Optional[str] = None,
                        cell: Optional[str] = None,
                        width_deg: Optional[float] = None,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen null-arm (N0/N1/N2) accepted-proton pair structure
    per cell, kernel width and pair class, with the same columns as the
    REAL arm; null-arm values are per-event permutation means first,
    physical-event bootstrap second (frozen rule). null, cell and
    width_deg are optional filters; omitting null returns all three
    null arms."""
    tool = "b4a.null_pair_structure"
    _check_cell(cell, tool)
    _check_null(null, tool)
    if width_deg is not None and f"{float(width_deg)}" not in WIDTHS:
        raise ToolError(f"width_deg must be one of {WIDTHS}",
                        provenance={"tool": tool})
    use = NULLS if null is None else (null,)
    rows = []
    for n in use:
        for r in _csv(analysis_dir, f"phaseB4A_{n}_pair_structure.csv"):
            if (cell is not None and r["cell"] != cell) or \
                    (width_deg is not None
                     and r["width_deg"] != f"{float(width_deg)}"):
                continue
            rows.append({"null": n, **_pair_row(r)})
    meta = _meta(analysis_dir)
    data = {"rows": rows, "estimator": meta["estimator"],
            "nulls": meta["nulls"],
            "support_rule": meta["support_rule"],
            "mobility_caveat": _mobility_caveat(analysis_dir)["note"]}
    summary = f"{len(rows)} null pair-structure row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"null": null, "cell": cell,
                               "width_deg": width_deg}})


def real_null_contrast(cell: Optional[str] = None,
                       null: Optional[str] = None,
                       analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen REAL-minus-null contrast table per cell and null:
    the primary delta_C1_label = C1_DA_REAL - C1_DA_null (negative =
    REAL more negative) and the secondary delta_Delta120_label, each
    with shared-index bootstrap SD and 95% CI, a CI-excludes-zero
    flag, and both arm values. cell and null are optional filters.
    The N1 mobility caveat is always attached."""
    tool = "b4a.real_null_contrast"
    _check_cell(cell, tool)
    _check_null(null, tool)
    rows = [_contrast_row(r)
            for r in _csv(analysis_dir, "phaseB4A_real_null_contrasts.csv")
            if (cell is None or r["cell"] == cell)
            and (null is None or r["null"] == null)]
    meta = _meta(analysis_dir)
    data = {"rows": rows,
            "contrasts": meta["contrasts"],
            "bootstrap": meta["bootstrap"],
            "bin2_note": ("all bin2 contrast CIs include zero in the "
                          "frozen table (marked per row by "
                          "ci_excludes_zero)") ,
            "mobility_caveat": _mobility_caveat(analysis_dir)}
    summary = f"{len(rows)} real-null contrast row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "null": null}})


def unitQ_opposition(cell: Optional[str] = None,
                     arm: Optional[str] = None,
                     analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen unit-vector D-A opposition table per cell and arm
    (REAL/N0/N1/N2): the per-event cosTheta_DA distribution summary
    (events on support, mean with bootstrap 95% CI, median, p10/p25/
    p75/p90, and the fraction of events with negative cosTheta_DA).
    cell and arm are optional filters."""
    tool = "b4a.unitQ_opposition"
    _check_cell(cell, tool)
    _check_arm(arm, tool)
    rows = [{
        "cell": r["cell"], "arm": r["arm"],
        "n_events_on_support": _i(r["n_events_on_support"]),
        "mean": _f(r["mean"]), "mean_sd": _f(r["mean_sd"]),
        "mean_ci": [_f(r["mean_ci_lo"]), _f(r["mean_ci_hi"])],
        "median": _f(r["median"]),
        "p10": _f(r["p10"]), "p25": _f(r["p25"]),
        "p75": _f(r["p75"]), "p90": _f(r["p90"]),
        "frac_negative": _f(r["frac_negative"])}
        for r in _csv(analysis_dir, "phaseB4A_unitQ_opposition.csv")
        if (cell is None or r["cell"] == cell)
        and (arm is None or r["arm"] == arm)]
    meta = _meta(analysis_dir)
    data = {"rows": rows,
            "unitQ_identities": meta["unitQ_identities"],
            "opposition_rule": meta["opposition"]}
    summary = f"{len(rows)} unit-Q opposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "arm": arm}})


def ptQ_opposition(cell: Optional[str] = None,
                   arm: Optional[str] = None,
                   analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen pT-weighted Q-vector D-A opposition table per cell,
    arm and quantity (cosThetaQ = cos Theta_Q,DA; negQdot = -Q_D.Q_A):
    the same distribution summary columns as the unit-Q table plus the
    sum. DIAGNOSTIC ONLY — never a replacement for the unweighted
    C1/Delta endpoints. cell and arm are optional filters."""
    tool = "b4a.ptQ_opposition"
    _check_cell(cell, tool)
    _check_arm(arm, tool)
    rows = [{
        "cell": r["cell"], "arm": r["arm"], "quantity": r["quantity"],
        "n_events_on_support": _i(r["n_events_on_support"]),
        "mean": _f(r["mean"]), "mean_sd": _f(r["mean_sd"]),
        "mean_ci": [_f(r["mean_ci_lo"]), _f(r["mean_ci_hi"])],
        "median": _f(r["median"]),
        "p10": _f(r["p10"]), "p25": _f(r["p25"]),
        "p75": _f(r["p75"]), "p90": _f(r["p90"]),
        "frac_negative": _f(r["frac_negative"]),
        "sum": _f(r["sum"])}
        for r in _csv(analysis_dir, "phaseB4A_ptQ_opposition.csv")
        if (cell is None or r["cell"] == cell)
        and (arm is None or r["arm"] == arm)]
    data = {"rows": rows,
            "ptQ_rule": _meta(analysis_dir)["pTQ"]}
    summary = f"{len(rows)} pT-weighted opposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "arm": arm}})


def fixed_b(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen fixed-b bundle: the REAL-minus-null contrasts
    (delta_C1_label primary, delta_Delta120_label secondary) for every
    cell (minbias, pooled_b3, bins 0/1/2) and null, the per-cell
    proton mobility for each null, and the per-cell REAL and N1
    per-class C1_c with CIs, so the centrality trend, the contrast and
    the mobility restriction can be read together."""
    con = [_contrast_row(r)
           for r in _csv(analysis_dir, "phaseB4A_real_null_contrasts.csv")]
    mob = [_mobility_row(r)
           for r in _csv(analysis_dir, "phaseB4A_permutation_mobility.csv")
           if r["sample"] == "proton"]
    real = [_pair_row(r)
            for r in _csv(analysis_dir, "phaseB4A_real_pair_structure.csv")
            if r["width_deg"] == "120.0"]
    n1 = [_pair_row(r)
          for r in _csv(analysis_dir, "phaseB4A_N1_pair_structure.csv")
          if r["width_deg"] == "120.0"]
    data = {"contrasts_per_cell": con,
            "mobility_per_cell": mob,
            "real_C1_w120_per_cell": real,
            "n1_C1_w120_per_cell": n1,
            "bin2_note": ("bin2 contrast CIs include zero for every "
                          "null in the frozen table"),
            "mobility_caveat": _mobility_caveat(analysis_dir)["note"]}
    summary = (f"{len(con)} contrast row(s), {len(mob)} mobility "
               f"row(s), {len(real)}+{len(n1)} w=120 pair row(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b4a.fixed_b", "inputs": {}})


def baryon_corroboration(cell: Optional[str] = None,
                         section: Optional[str] = None,
                         analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """The frozen all-B=+1 corroboration table: the pair_structure
    section (REAL/N0/N1 per cell and class: F, C1_c, Delta120_c and
    the additive contributions with bootstrap CIs and support flags;
    N1 strata = species group x pT x y) and the contrast section
    (delta_C1_label / delta_Delta120_label vs N0 and N1 per cell).
    cell and section are optional filters."""
    tool = "b4a.baryon_corroboration"
    _check_cell(cell, tool)
    if section is not None and section not in ("pair_structure", "contrast"):
        raise ToolError("section must be pair_structure or contrast",
                        provenance={"tool": tool})
    rows = [{
        "section": r["section"], "cell": r["cell"],
        "arm_or_null": r["arm_or_null"], "quantity": r["quantity"],
        "class": r["class"] if r["class"] else None,
        "point": _f(r["point"]), "sd": _f(r["sd"]),
        "ci": [_f(r["ci_lo"]), _f(r["ci_hi"])],
        "support_or_note": r["support_or_note"]}
        for r in _csv(analysis_dir, "phaseB4A_baryon_corroboration.csv")
        if (cell is None or r["cell"] == cell)
        and (section is None or r["section"] == section)]
    data = {"rows": rows,
            "baryon_rule": _meta(analysis_dir)["baryon_corroboration"],
            "note": ("all accepted B=+1 particles (not only accepted "
                     "protons); same frozen null definitions")}
    summary = f"{len(rows)} baryon corroboration row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "section": section}})


def mechanism_evidence(analysis_dir: Optional[str] = None
                       ) -> ToolResult:
    """A bundled read-only summary of the frozen B4-A outputs: the
    hypotheses lock reference, the analytic null-check verdict, the
    REAL minbias w=120 DD/DA/AA C1_c and Delta_c with CIs, the primary
    delta_C1_label contrast vs each null in minbias and pooled_b3 with
    CIs, the N1/N2 retained fractions of the REAL C1_DA, the additive
    DA-sole-negative-carrier flags per arm, the N1 mobility caveat,
    and the frozen B3-B anchors (minbias w=120 DD/DA/AA contributions
    with the negative-carrier list). Data only."""
    meta = _meta(analysis_dir)
    chk = _json(analysis_dir, "phaseB4A_analytic_null_check.json")
    real = {r["class"]: r
            for r in _csv(analysis_dir, "phaseB4A_real_pair_structure.csv")
            if r["cell"] == "minbias" and r["width_deg"] == "120.0"}
    con = [_contrast_row(r)
           for r in _csv(analysis_dir, "phaseB4A_real_null_contrasts.csv")
           if r["cell"] in ("minbias", "pooled_b3")
           and r["quantity"] == "delta_C1_label"]
    retained = {}
    for n in NULLS:
        row = next(r for r in
                   _csv(analysis_dir, "phaseB4A_real_null_contrasts.csv")
                   if r["cell"] == "minbias" and r["null"] == n
                   and r["quantity"] == "delta_C1_label")
        retained[n] = {
            "null_C1_DA_minbias": _f(row["null_point"]),
            "retained_fraction_vs_real":
                float(row["null_point"]) / float(row["real_point"])}
    add = [_additive_row(r)
           for r in _csv(analysis_dir, "phaseB4A_additive_contributions.csv")
           if r["cell"] == "minbias"]
    anch = [r for r in _b3b_csv("phaseB3B_proton_pair_decomposition.csv")
            if r["cell"] == "minbias" and r["width_deg"] == "120.0"
            and r["class"] in CLS3]
    neg = [r["class"] for r in anch if float(r["contribution"]) < 0]
    data = {
        "hypotheses": meta["hypotheses"],
        "analytic_null_check_overall": chk["overall"],
        "real_minbias_w120": [{
            "class": c,
            "C1_c": _f(real[c]["C1_c"]),
            "C1_c_ci": [_f(real[c]["C1_c_ci_lo"]),
                        _f(real[c]["C1_c_ci_hi"])],
            "Delta_c": _f(real[c]["Delta_c"]),
            "Delta_c_ci": [_f(real[c]["Delta_c_ci_lo"]),
                           _f(real[c]["Delta_c_ci_hi"])],
            "support": real[c]["support"]} for c in CLS3],
        "primary_contrast_delta_C1_label": con,
        "retained_fraction_minbias": retained,
        "additive_carrier_flags_minbias": [{
            "arm": r["arm"], "quantity": r["quantity"],
            "DA_sole_negative_carrier": r["DA_sole_negative_carrier"],
            "contribution_DA": r["contribution_DA"]} for r in add],
        "mobility_caveat": _mobility_caveat(analysis_dir),
        "b3b_anchors": {
            "minbias_w120_DD_DA_AA_contributions": [{
                "class": r["class"], "contribution": _f(r["contribution"]),
                "contribution_ci": [_f(r["contribution_ci_lo"]),
                                    _f(r["contribution_ci_hi"])],
                "support": r["support"]} for r in anch],
            "negative_contribution_classes": neg},
        "discipline_note": (
            "azimuth-blind label permutations on frozen events; no "
            "dynamical intervention; attribution is not causation; "
            "mechanism-language prohibitions per hypotheses.md")}
    summary = ("B4-A bundle: REAL DD/DA/AA structure, delta_C1_label "
               "vs nulls, retained fractions, mobility caveat, B3-B "
               "anchors")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b4a.mechanism_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B4-A "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "frozen outputs)"}}
_CELL_PROP = {"cell": {"type": "string", "enum": list(CELLS)}}
_NULL_PROP = {"null": {"type": "string", "enum": list(NULLS)}}
_ARM_PROP = {"arm": {"type": "string", "enum": list(ARMS)}}

register(ToolSpec(
    name="b4a.null_status",
    description=(
        "The frozen B4-A null status: hypotheses-lock reference and "
        "sha256, N0/N1/N2 definitions with seeds and R, estimator and "
        "shared-index bootstrap, support rule, totals-invariance check "
        "across arms, analytic N0 check verdict, and the N1 mobility "
        "caveat."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=null_status))

register(ToolSpec(
    name="b4a.permutation_mobility",
    description=(
        "The frozen permutation-mobility table per sample, cell and "
        "null (cell and null optional): exchangeable/frozen particle "
        "fractions, mean effective swaps per event, fully-frozen event "
        "fraction and mean strata per event."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_NULL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=permutation_mobility))

register(ToolSpec(
    name="b4a.real_pair_structure",
    description=(
        "The frozen REAL-arm accepted-proton pair structure per cell, "
        "kernel width and pair class (cell and width_deg optional): "
        "pair counts, support flags, F, class-level Delta_c and C1_c, "
        "and additive Delta(w)/C1 contributions with bootstrap CIs."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP,
        "width_deg": {"type": "number", "enum": [60, 90, 120, 180]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=real_pair_structure))

register(ToolSpec(
    name="b4a.null_pair_structure",
    description=(
        "The frozen null-arm (N0/N1/N2) accepted-proton pair structure "
        "(null, cell and width_deg optional): same columns as the REAL "
        "arm; null values are per-event permutation means with "
        "physical-event bootstrap. N1 mobility caveat attached."),
    input_schema={"type": "object", "properties": {
        **_NULL_PROP, **_CELL_PROP,
        "width_deg": {"type": "number", "enum": [60, 90, 120, 180]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=null_pair_structure))

register(ToolSpec(
    name="b4a.real_null_contrast",
    description=(
        "The frozen REAL-minus-null contrast table (cell and null "
        "optional): primary delta_C1_label and secondary "
        "delta_Delta120_label with shared-index bootstrap CIs, "
        "CI-excludes-zero flags, both arm values, and the N1 mobility "
        "caveat."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_NULL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=real_null_contrast))

register(ToolSpec(
    name="b4a.unitQ_opposition",
    description=(
        "The frozen unit-vector D-A opposition summary per cell and "
        "arm (both optional): per-event cosTheta_DA distribution "
        "statistics (mean with bootstrap CI, median, percentiles, "
        "negative fraction)."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_ARM_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=unitQ_opposition))

register(ToolSpec(
    name="b4a.ptQ_opposition",
    description=(
        "The frozen pT-weighted Q-vector D-A opposition summary per "
        "cell, arm and quantity (cosThetaQ, negQdot; cell and arm "
        "optional). Diagnostic only, never a replacement for the "
        "unweighted endpoints."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_ARM_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=ptQ_opposition))

register(ToolSpec(
    name="b4a.fixed_b",
    description=(
        "The frozen fixed-b bundle: REAL-minus-null contrasts for "
        "every cell and null, per-cell proton mobility for each null, "
        "and per-cell REAL and N1 per-class C1_c with CIs."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=fixed_b))

register(ToolSpec(
    name="b4a.baryon_corroboration",
    description=(
        "The frozen all-B=+1 corroboration table (cell and section "
        "optional): pair_structure section (REAL/N0/N1 per cell and "
        "class with bootstrap CIs; N1 strata = species x pT x y) and "
        "contrast section (delta_C1_label / delta_Delta120_label vs "
        "N0 and N1 per cell)."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP,
        "section": {"type": "string",
                    "enum": ["pair_structure", "contrast"]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=baryon_corroboration))

register(ToolSpec(
    name="b4a.mechanism_evidence",
    description=(
        "A bundled read-only summary of the frozen B4-A outputs: "
        "hypotheses lock, analytic check verdict, REAL minbias w=120 "
        "DD/DA/AA structure, primary delta_C1_label contrasts, "
        "retained fractions, additive carrier flags, N1 mobility "
        "caveat, and the frozen B3-B anchors. Data only."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=mechanism_evidence))


# ----------------------------------------------------------------------
# minimal CLI (see module docstring for why cli/main.py is not extended)
# ----------------------------------------------------------------------

def _cli(argv) -> int:
    from ..agent.tool_runner import call_tool
    from .registry import REGISTRY

    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "list":
        for name in sorted(n for n in REGISTRY if n.startswith("b4a.")):
            spec = REGISTRY[name]
            first = spec.description.strip().splitlines()[0]
            print(f"{name:38s} {spec.risk_level:10s} {first}")
        return 0
    if argv[0] == "call":
        if len(argv) < 2:
            print("usage: call <tool_name> ['<json_args>']",
                  file=sys.stderr)
            return 2
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        result = call_tool(argv[1], args)
        print(json.dumps(result.to_dict(), indent=2))
        return {"ok": 0, "blocked": 2}.get(result.status, 1)
    print(f"unknown command {argv[0]!r}; expected list|call",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
