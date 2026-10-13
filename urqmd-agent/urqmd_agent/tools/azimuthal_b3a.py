"""Phase B3-A (baryon-only vs meson-only pseudo-proton counterfactual
and its diagnostics) read-only tools.

These tools expose the persisted Phase B3-A deliverables
(physics_gate/phaseB3A/analysis/*.csv and *.json) and, for one
descriptive reference row, the frozen Phase B2-B deliverables quoted
inside them. They never run UrQMD, never open raw file13/file15
output, and never execute user-supplied code. Every number they
report is copied from the frozen analysis CSVs/JSON at call time, so
the tools and the CSV deliverables agree by construction.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b3a`` registers the eight ``b3a.*``
tools in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b3a list
    python3 -m urqmd_agent.tools.azimuthal_b3a call \\
        b3a.compare_real_baryon_meson '{"cell": "minbias"}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis drivers (survival gate strings, sector notes, verdict
labels, caveat text) are passed through verbatim as data.
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
B3A_DIR = REPO_ROOT / "physics_gate" / "phaseB3A"
DEFAULT_ANALYSIS_DIR = B3A_DIR / "analysis"
HYPOTHESES_FREEZE = B3A_DIR / "data" / "hypotheses_freeze.json"

CELLS = ("minbias", "pooled_0.000-12.255", "0.000-7.075",
         "7.075-10.006", "10.006-12.255")
SAMPLES = ("REAL", "B", "M")

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


_HINT = ("run the Phase B3-A drivers (physics_gate/phaseB3A/analysis/"
         "run_phaseB3A_counterfactual.py and run_phaseB3A_diagnostics.py) "
         "first")


def _csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_csv(d / fname, _HINT)


def _json(analysis_dir: Optional[str], fname: str) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_json(d / fname, _HINT)


def _f(x: str):
    if x is None or x == "":
        return None
    return float(x)


def _i(x: str):
    if x is None or x == "":
        return None
    return int(x)


def _ci(x: str):
    """Parse a frozen CI cell of the form '[lo, hi]' -> [lo, hi]."""
    if x is None or x == "":
        return None
    return [float(t) for t in x.strip().lstrip("[").rstrip("]").split(",")]


def _check_cell(cell: Optional[str], tool: str) -> None:
    if cell is not None and cell not in CELLS:
        raise ToolError(f"cell must be one of {CELLS}",
                        provenance={"tool": tool})


def _compare_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "w_deg": _i(r["w_deg"]),
        "delta_real_full": _f(r["delta_real_full"]),
        "delta_real_full_err": _f(r["delta_real_full_err"]),
        "delta_real_common": _f(r["delta_real_common"]),
        "delta_B": _f(r["delta_B"]), "delta_B_sd": _f(r["delta_B_sd"]),
        "delta_B_ci": _ci(r["delta_B_ci"]),
        "delta_M": _f(r["delta_M"]), "delta_M_sd": _f(r["delta_M_sd"]),
        "delta_M_ci": _ci(r["delta_M_ci"]),
        "delta_BM": _f(r["delta_BM"]), "delta_BM_sd": _f(r["delta_BM_sd"]),
        "delta_BM_ci": _ci(r["delta_BM_ci"]),
        "S_B": _f(r["S_B"]), "S_B_sd": _f(r["S_B_sd"]),
        "S_B_ci": _ci(r["S_B_ci"]),
        "S_M": _f(r["S_M"]), "S_M_sd": _f(r["S_M_sd"]),
        "S_M_ci": _ci(r["S_M_ci"]),
        "S_B_minus_S_M": _f(r["S_B_minus_S_M"]),
        "S_B_minus_S_M_sd": _f(r["S_B_minus_S_M_sd"]),
        "S_B_minus_S_M_ci": _ci(r["S_B_minus_S_M_ci"]),
        "generic_B2_frozen": ({
            "delta_pseudo": _f(r["generic_B2_frozen_delta_pseudo"]),
            "survival": _f(r["generic_B2_frozen_survival"]),
            "note": r["generic_B2_note"]}
            if r["generic_B2_frozen_delta_pseudo"] else None)}


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def sample_definition(analysis_dir: Optional[str] = None) -> ToolResult:
    """Sample construction of the three B3-A samples (REAL accepted
    protons; BARYON-pool and MESON-pool pseudo-protons): acceptance,
    pool definitions, stratification, frozen seeds, replica count and
    the preregistered escalation that was applied, pool-insufficiency
    counts, anchor cross-check differences, and the hypotheses-freeze
    reference (file, sha256, frozen-before statement)."""
    cs = _json(analysis_dir, "phaseB3A_counterfactual_summary.json")
    ds = _json(analysis_dir, "phaseB3A_diagnostics_summary.json")
    hyp = _read_json(HYPOTHESES_FREEZE,
                     "the B3-A hypotheses freeze record is missing")
    data = {
        "samples": {
            "REAL": ("accepted protons from the frozen B1 shards "
                     "(|y|<0.5, 0.4<pT<2.0 GeV/c); events with Np>=2"),
            "B": ("pseudo-protons drawn phi-blind, without replacement, "
                  "exactly Np per event, from final B=+1 particles "
                  "excluding the real accepted-proton uids; no "
                  "real-proton re-inclusion; events with insufficient "
                  "pool are excluded from the arm"),
            "M": ("same procedure from final B=0 UrQMD mesons")},
        "stratification": cs["stratification"],
        "neighbor_order_rule": cs["neighbor_order_rule"],
        "frozen_seeds": cs["frozen_seeds"],
        "r_used": cs["r_used"],
        "escalation_triggered": cs["escalation_triggered"],
        "convergence_rule": cs["convergence_rule"],
        "insufficiency": cs["insufficiency"],
        "anchors_crosscheck": cs["anchors_crosscheck"],
        "shared_bootstrap_note": cs["shared_bootstrap_note"],
        "diagnostics_frozen_inputs": ds["frozen_inputs"],
        "hypotheses_freeze": {
            "file": hyp["file"], "sha256": hyp["sha256"],
            "frozen_utc": hyp["frozen_utc"],
            "frozen_before": hyp["frozen_before"]}}
    summary = (f"sample definitions; R={cs['r_used']} after escalation "
               f"={cs['escalation_triggered']}; insufficiency "
               f"{cs['insufficiency']}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.sample_definition", "inputs": {}})


def pseudo_pool_diagnostics(analysis_dir: Optional[str] = None
                            ) -> ToolResult:
    """The frozen pool diagnostics table per pseudo arm and cell:
    eligible/insufficient event counts, relaxation counts, rank-paired
    pT/y residual means and SDs of selected vs real momenta, the Np
    equality flag, and the species-composition fractions."""
    rows = [{
        "pseudo_type": r["pseudo_type"], "cell": r["cell"],
        "n_cell_events": _i(r["n_cell_events"]),
        "n_Np_ge2": _i(r["n_Np_ge2"]),
        "n_eligible": _i(r["n_eligible"]),
        "n_insufficient": _i(r["n_insufficient"]),
        "n_relaxed_events": _i(r["n_relaxed_events"]),
        "n_relaxed_slots_total": _i(r["n_relaxed_slots_total"]),
        "pt_resid_mean": _f(r["pt_resid_mean"]),
        "pt_resid_sd": _f(r["pt_resid_sd"]),
        "y_resid_mean": _f(r["y_resid_mean"]),
        "y_resid_sd": _f(r["y_resid_sd"]),
        "np_equality_ok": r["np_equality_ok"],
        "fractions": {k[len("frac_"):]: _f(r[k]) for k in r
                      if k.startswith("frac_") and r[k] != ""}}
        for r in _csv(analysis_dir, "phaseB3A_pool_diagnostics.csv")]
    data = {"rows": rows,
            "residual_note": ("rank-paired descriptive residuals: sorted "
                              "selected pseudo momenta vs sorted real "
                              "momenta within each event and replica")}
    summary = f"{len(rows)} pool diagnostic row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.pseudo_pool_diagnostics", "inputs": {}})


def compare_real_baryon_meson(cell: Optional[str] = None,
                              analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """The frozen counterfactual compare table at w=120 per cell:
    Delta_real (full and common sets), Delta_B, Delta_M, Delta_BM,
    S_B, S_M and S_B - S_M with shared-event bootstrap SDs and 95%
    CIs; the minbias row carries the frozen B2-B generic-charged
    reference values flagged descriptive-only. cell selects one row;
    omitting it returns all five."""
    _check_cell(cell, "b3a.compare_real_baryon_meson")
    rows = [_compare_row(r)
            for r in _csv(analysis_dir,
                          "phaseB3A_counterfactual_compare.csv")
            if cell is None or r["cell"] == cell]
    data = {"w_deg": 120,
            "estimator_note": ("central values and CIs are the "
                               "shared-event bootstrap quantities over "
                               "the common eligible set (one resample "
                               "through REAL/B/M); delta_real_full is "
                               "the full-set REAL value"),
            "b2b_reference_note": ("generic_B2_frozen is a read-only "
                                   "frozen B2-B reference (different "
                                   "pool, stratification and fallback "
                                   "rules); descriptive only"),
            "rows": rows}
    summary = f"{len(rows)} compare row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.compare_real_baryon_meson",
                    "inputs": {"cell": cell}})


def harmonic_decomposition(cell: Optional[str] = None,
                           analysis_dir: Optional[str] = None
                           ) -> ToolResult:
    """The frozen harmonic fingerprint: pair harmonics C_1..C_12 per
    sample (REAL/B/M) and cell with event-block bootstrap SDs, and the
    signed contributions D_n(w) = (2/pi^2) sin^2(nw/2)/n^2 C_n with
    the truncated n=1..12 sum, the exact pair-kernel Delta and the
    reconstruction residual per sample/cell/width. cell selects one
    cell; omitting it returns all five."""
    _check_cell(cell, "b3a.harmonic_decomposition")
    cn = [{"sample": r["sample"], "cell": r["cell"], "n": _i(r["n"]),
           "C_n": _f(r["C_n"]), "C_n_err": _f(r["C_n_err"])}
          for r in _csv(analysis_dir, "phaseB3A_harmonics.csv")
          if cell is None or r["cell"] == cell]
    rec = []
    for r in _csv(analysis_dir, "phaseB3A_harmonic_reconstruction.csv"):
        if cell is not None and r["cell"] != cell:
            continue
        rec.append({"sample": r["sample"], "cell": r["cell"],
                    "w_deg": _i(r["w_deg"]),
                    "D_n": {n: _f(r[f"D_{n}"]) for n in range(1, 13)},
                    "sum_D_n": _f(r["sum_D_n"]),
                    "exact_delta": _f(r["exact_delta"]),
                    "residual": _f(r["residual"])})
    data = {"truncation_note": ("D_n sums are truncated at n=12; the "
                                "reconstruction residual vs the exact "
                                "pair-kernel Delta is tabulated per row "
                                "and is not claimed to vanish"),
            "C_n": cn, "reconstruction": rec}
    summary = f"{len(cn)} C_n row(s), {len(rec)} reconstruction row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.harmonic_decomposition",
                    "inputs": {"cell": cell}})


def sector_recoil_budget(analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """The frozen sector recoil budget per cell: F_S =
    -sum(Q_P.Q_S)/sum|Q_P|^2 per mutually exclusive sector (S1 other
    B=+1 with ncoll>0; S2 B=+1 ncoll==0; S3 antibaryons; S4 mesons;
    S5 other verified) with event-block bootstrap SDs, the per-event
    mean f_S, the sum-over-sectors residual vs 1, and the closure
    metadata (internal closure, spectator momentum, sector caveats)."""
    ds = _json(analysis_dir, "phaseB3A_diagnostics_summary.json")
    rows = [{"cell": r["cell"], "sector": r["sector"],
             "F_S": _f(r["F_S"]), "F_S_err": _f(r["F_S_err"]),
             "mean_f_S": _f(r["mean_f_S"]),
             "n_events_used": _i(r["n_events_used"])}
            for r in _csv(analysis_dir, "phaseB3A_recoil_budget.csv")]
    data = {"rows": rows, "closure_metadata": ds["step13"]}
    summary = f"{len(rows)} recoil row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.sector_recoil_budget", "inputs": {}})


def sector_pair_harmonics(cell: Optional[str] = None,
                          analysis_dir: Optional[str] = None
                          ) -> ToolResult:
    """The frozen proton-sector pair harmonics per cell and pair class
    (pp, p-S1, p-S2, p-S3, p-S4): unweighted and pT-weighted
    <cos(n dphi)> for n=1 (primary, with event-block bootstrap SDs)
    and n=2,3 (diagnostics), plus the total pair counts."""
    _check_cell(cell, "b3a.sector_pair_harmonics")
    rows = [{"cell": r["cell"], "pair_class": r["pair_class"],
             "n": _i(r["n"]),
             "C_n_unweighted": _f(r["C_n_unweighted"]),
             "C_n_pT_weighted": _f(r["C_n_pT_weighted"]),
             "C_n_err": _f(r["C_n_err"]),
             "C_n_pT_weighted_err": _f(r["C_n_pT_weighted_err"]),
             "n_pairs_total": _i(r["n_pairs_total"])}
            for r in _csv(analysis_dir,
                          "phaseB3A_sector_pair_harmonics.csv")
            if cell is None or r["cell"] == cell]
    data = {"pairing_note": ("pairs of an accepted proton with another "
                             "accepted proton (pp) or with a particle "
                             "of one sector; pT-weighted values use "
                             "sum(pTi pTj cos)/sum(pTi pTj)"),
            "rows": rows}
    summary = f"{len(rows)} sector pair-harmonic row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.sector_pair_harmonics",
                    "inputs": {"cell": cell}})


def lineage_sufficiency(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen Step-16 lineage data-sufficiency verdicts (per
    required variable, from the structured sidecar of the sufficiency
    report), the Step-17 consequence, and the frozen antiproton
    support verdicts per cell (counts and the adequacy rule)."""
    side = _json(analysis_dir, "phaseB3A_lineage_sufficiency.json")
    ds = _json(analysis_dir, "phaseB3A_diagnostics_summary.json")
    data = {"lineage": side, "antiproton": ds["step18"]}
    summary = (f"lineage {side['overall']}; antiproton verdicts for "
               f"{len(ds['step18'])} cell(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.lineage_sufficiency", "inputs": {}})


def mechanism_evidence(analysis_dir: Optional[str] = None) -> ToolResult:
    """A bundled read-only summary of the frozen B3-A outputs: the
    minbias and pooled compare rows (headline Deltas, survivals,
    Delta_BM with CIs), the S_B - S_M CIs per cell, the largest-|D_n|
    harmonic per sample at w=120 minbias (selected deterministically
    from the frozen D_n table), the minbias recoil split, the frozen
    B2-B reference row, and the lineage/antiproton verdicts. Data
    only."""
    cmp_rows = {r["cell"]: r
                for r in _csv(analysis_dir,
                              "phaseB3A_counterfactual_compare.csv")}
    rec = [r for r in _csv(analysis_dir,
                           "phaseB3A_harmonic_reconstruction.csv")
           if r["cell"] == "minbias" and r["w_deg"] == "120"]
    dominant = {}
    for r in rec:
        dn = {n: _f(r[f"D_{n}"]) for n in range(1, 13)}
        n_dom = min(dn, key=lambda n: dn[n])
        dominant[r["sample"]] = {
            "most_negative_contribution": f"D_{n_dom}",
            "value": dn[n_dom],
            "share_note": ("selected as the most negative D_n of the "
                           "frozen w=120 minbias row; shares are not "
                           "normalized (unstable denominators possible)")}
    rb = [r for r in _csv(analysis_dir, "phaseB3A_recoil_budget.csv")
          if r["cell"] == "minbias"]
    side = _json(analysis_dir, "phaseB3A_lineage_sufficiency.json")
    ds = _json(analysis_dir, "phaseB3A_diagnostics_summary.json")
    data = {
        "headline": {c: _compare_row(cmp_rows[c])
                     for c in ("minbias", "pooled_0.000-12.255")},
        "S_B_minus_S_M_per_cell": {
            c: {"value": _f(cmp_rows[c]["S_B_minus_S_M"]),
                "ci": _ci(cmp_rows[c]["S_B_minus_S_M_ci"])}
            for c in CELLS},
        "dominant_harmonic_w120_minbias": dominant,
        "recoil_split_minbias": [
            {"sector": r["sector"], "F_S": _f(r["F_S"]),
             "F_S_err": _f(r["F_S_err"])} for r in rb],
        "recoil_metadata": ds["step13"],
        "lineage_overall": side["overall"],
        "step17_consequence": side["step17_consequence"],
        "antiproton_verdicts": {c: v["adequate"]
                                for c, v in ds["step18"].items()}}
    summary = ("B3-A bundle: headline rows, S_B-S_M CIs, dominant "
               "harmonics, recoil split, verdicts")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3a.mechanism_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B3-A "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "frozen outputs)"}}
_CELL_PROP = {"cell": {"type": "string", "enum": list(CELLS)}}

register(ToolSpec(
    name="b3a.sample_definition",
    description=(
        "Sample construction of the three B3-A samples (REAL accepted "
        "protons; BARYON-pool and MESON-pool pseudo-protons): "
        "acceptance, pool definitions, stratification, frozen seeds, "
        "replica count and the preregistered escalation applied, "
        "pool-insufficiency counts, anchor cross-checks, and the "
        "hypotheses-freeze reference."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=sample_definition))

register(ToolSpec(
    name="b3a.pseudo_pool_diagnostics",
    description=(
        "The frozen pool diagnostics table per pseudo arm and cell: "
        "eligible/insufficient event counts, relaxation counts, "
        "rank-paired pT/y residuals of selected vs real momenta, the "
        "Np equality flag, and species-composition fractions."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=pseudo_pool_diagnostics))

register(ToolSpec(
    name="b3a.compare_real_baryon_meson",
    description=(
        "The frozen counterfactual compare table at w=120 per cell "
        "(cell optional): Delta_real, Delta_B, Delta_M, Delta_BM, "
        "S_B, S_M and S_B - S_M with shared-event bootstrap SDs and "
        "95% CIs; the minbias row carries the frozen B2-B "
        "generic-charged reference flagged descriptive-only."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=compare_real_baryon_meson))

register(ToolSpec(
    name="b3a.harmonic_decomposition",
    description=(
        "The frozen harmonic fingerprint (cell optional): pair "
        "harmonics C_1..C_12 per sample and cell with bootstrap SDs, "
        "and the signed contributions D_n(w) with the truncated "
        "n=1..12 sum, the exact pair-kernel Delta and the "
        "reconstruction residual per sample/cell/width."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=harmonic_decomposition))

register(ToolSpec(
    name="b3a.sector_recoil_budget",
    description=(
        "The frozen sector recoil budget per cell: F_S per mutually "
        "exclusive sector with bootstrap SDs, per-event mean f_S, the "
        "sum residual vs 1, and the closure metadata including the "
        "spectator-absence caveat."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=sector_recoil_budget))

register(ToolSpec(
    name="b3a.sector_pair_harmonics",
    description=(
        "The frozen proton-sector pair harmonics per cell and pair "
        "class (cell optional): unweighted and pT-weighted "
        "<cos(n dphi)> for n=1 (with bootstrap SDs) and n=2,3, plus "
        "total pair counts."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=sector_pair_harmonics))

register(ToolSpec(
    name="b3a.lineage_sufficiency",
    description=(
        "The frozen Step-16 lineage data-sufficiency verdicts per "
        "required variable, the Step-17 consequence, and the frozen "
        "antiproton support verdicts per cell (counts and the "
        "adequacy rule)."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=lineage_sufficiency))

register(ToolSpec(
    name="b3a.mechanism_evidence",
    description=(
        "A bundled read-only summary of the frozen B3-A outputs: "
        "headline compare rows, S_B - S_M CIs per cell, the "
        "most-negative D_n harmonic per sample at w=120 minbias, the "
        "minbias recoil split, the frozen B2-B reference row, and "
        "the lineage/antiproton verdicts. Data only."),
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
        for name in sorted(n for n in REGISTRY if n.startswith("b3a.")):
            spec = REGISTRY[name]
            first = spec.description.strip().splitlines()[0]
            print(f"{name:34s} {spec.risk_level:10s} {first}")
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
