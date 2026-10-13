"""Phase B2 (counterfactual arms) read-only analysis tools.

These tools expose the persisted Phase B2-B deliverables
(physics_gate/phaseB2/analysis/*.csv and phaseB2B_summary.json) and,
where a comparison requires it, the frozen Phase B1 baseline
(physics_gate/phaseB1/analysis/*.csv, read-only). They are strictly
read-only: they never run UrQMD, never open raw file13/file15 output,
and never execute user-supplied code. Every number they report is
copied from the frozen analysis CSVs/JSON, so the tools and the CSV
deliverables agree by construction. The Phase B2-A rescattering-off
intervention arm is BLOCKED (no clean runtime option in the frozen
build); the tools expose only its persisted STATUS rows and never carry
numeric B2-A values.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b2`` registers the six ``b2.*`` tools in
the shared registry, after which ``agent.tool_runner.call_tool`` can
dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b2 list
    python3 -m urqmd_agent.tools.azimuthal_b2 call \\
        b2.pseudo_proton_counterfactual '{"set_label": "minbias"}'

Tool names and descriptions are deliberately neutral: they describe
what is tabulated, not what it means.
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
B1_DIR = REPO_ROOT / "physics_gate" / "phaseB1"
B2_DIR = REPO_ROOT / "physics_gate" / "phaseB2"
DEFAULT_B2_ANALYSIS_DIR = B2_DIR / "analysis"
DEFAULT_B1_ANALYSIS_DIR = B1_DIR / "analysis"

SET_LABELS = ("minbias", "0-5", "5-10", "10-20", "20-30", "30-40",
              "40-50", "50-60", "60-70", "70-80")
AXES = ("A", "B", "C", "D")
W_DEGS = (60, 90, 120, 180)
SAMPLES = ("REAL", "PSEUDO", "MIXED")
MAX_ROWS = 500

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


def _b2csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_B2_ANALYSIS_DIR
    return _read_csv(d / fname,
                     "run the Phase B2-B driver "
                     "(physics_gate/phaseB2/analysis/run_phaseB2B.py) first")


def _b1csv(fname: str) -> List[Dict[str, str]]:
    return _read_csv(DEFAULT_B1_ANALYSIS_DIR / fname,
                     "the frozen Phase B1 analysis outputs are missing")


def _b2summary(analysis_dir: Optional[str]) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_B2_ANALYSIS_DIR
    path = d / "phaseB2B_summary.json"
    if not path.is_file():
        raise ToolError(
            f"{path} not found; run the Phase B2-B driver first")
    key = f"json:{path}:{path.stat().st_mtime_ns}"
    if key not in _cache:
        _cache.clear()
        _cache[key] = json.loads(path.read_text())
    return _cache[key]


def _f(x: str):
    """Parse a CSV float cell; '' -> None."""
    if x is None or x == "":
        return None
    return float(x)


def _i(x: str):
    if x is None or x == "":
        return None
    return int(x)


def _rows(rows, max_rows):
    if len(rows) > max_rows:
        return rows[:max_rows], (f"truncated to first {max_rows} of "
                                 f"{len(rows)} rows")
    return rows, None


def _check_set(set_label: str, tool: str):
    if set_label not in SET_LABELS:
        raise ToolError(f"unknown set {set_label!r}; one of {SET_LABELS}",
                        provenance={"tool": tool})


def _b2a_status_rows(analysis_dir: Optional[str]) -> Dict[str, Any]:
    """STATUS rows of the blocked B2-A arm (no numeric values)."""
    interv = [{"intervention": r["intervention"], "status": r["status"],
               "n_events": _i(r["n_events"]), "note": r["note"]}
              for r in _b2csv(analysis_dir,
                              "phaseB2_rescattering_intervention.csv")]
    effects = [{"intervention": r["intervention"], "metric": r["metric"],
                "set": r["set"], "w_deg": _i(r["w_deg"]),
                "value": _f(r["value"]), "error": _f(r["error"]),
                "status": r["status"], "note": r["note"]}
               for r in _b2csv(analysis_dir,
                               "phaseB2_intervention_effect_sizes.csv")]
    audit = B2_DIR / "reports" / "phaseB2_rescattering_switch_audit.md"
    proposal = B2_DIR / "reports" / "phaseB2_rescattering_patch_proposal.md"
    return {"intervention_rows": interv, "effect_size_rows": effects,
            "switch_audit_md_present": audit.is_file(),
            "patch_proposal_md_present": proposal.is_file(),
            "patch_proposal_state": "awaiting human approval"}


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def compare_intervention_baseline(set_label: str = "minbias",
                                  analysis_dir: Optional[str] = None
                                  ) -> ToolResult:
    """Frozen B1 baseline anchors (pairs-weighted Delta at each window
    width, event counts) for one set, alongside the persisted B2-A
    intervention STATUS rows (the B2-A arm is blocked; no B2-A numeric
    values exist)."""
    _check_set(set_label, "b2.compare_intervention_baseline")
    rows = [r for r in _b1csv("phaseB1_pair_kernel_summary.csv")
            if r["section"] == "AGGREGATE_PAIRS" and r["set"] == set_label]
    baseline = [{"w_deg": _i(r["w_deg"]),
                 "n_events_set": _i(r["n_events_set"]),
                 "n_events_N_ge_2": _i(r["n_events_class"]),
                 "delta_real": _f(r["delta"]),
                 "delta_real_err": _f(r["delta_err"]),
                 "support": r["support"]} for r in rows]
    baseline.sort(key=lambda r: r["w_deg"])
    data = {"set": set_label,
            "b1_baseline_pairs_weighted": baseline,
            "b2a_intervention_status": _b2a_status_rows(analysis_dir)}
    summary = (f"{set_label}: {len(baseline)} B1 baseline anchor row(s); "
               f"B2-A status "
               f"{data['b2a_intervention_status']['intervention_rows'][0]['status']}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2.compare_intervention_baseline",
                    "inputs": {"set_label": set_label}})


def pseudo_proton_counterfactual(set_label: str = "minbias",
                                 analysis_dir: Optional[str] = None
                                 ) -> ToolResult:
    """Per-window real vs pseudo-proton Delta table for one set:
    bootstrap errors, survival value and gating label, convergence
    checkpoints (R=100/250/500 drift, flag), replica count used, and
    POOL_FALLBACK / relaxed-slot event counts."""
    _check_set(set_label, "b2.pseudo_proton_counterfactual")
    rows = [r for r in _b2csv(analysis_dir,
                              "phaseB2_pseudo_proton_counterfactual.csv")
            if r["set"] == set_label]
    table = [{"w_deg": _i(r["w_deg"]),
              "delta_real": _f(r["delta_real"]),
              "delta_real_err": _f(r["delta_real_err"]),
              "delta_pseudo": _f(r["delta_pseudo"]),
              "delta_pseudo_err": _f(r["delta_pseudo_err"]),
              "pseudo_survival": _f(r["pseudo_survival"]),
              "survival_gate": r["survival_gate"],
              "delta_pseudo_R100": _f(r["delta_pseudo_R100"]),
              "delta_pseudo_R250": _f(r["delta_pseudo_R250"]),
              "drift_R250_R500": _f(r["drift_R250_R500"]),
              "convergence_flag": r["convergence_flag"] == "True"}
             for r in rows]
    table.sort(key=lambda r: r["w_deg"])
    sj = _b2summary(analysis_dir)
    flags = sj["flag_by_set"][set_label]
    data = {"set": set_label, "r_replicas_used": sj["r_used"],
            "escalation_triggered": sj["escalate"],
            "n_events_set": flags["n_set"],
            "n_events_Np_ge_2": flags["n_valid"],
            "n_pool_fallback": flags["n_fallback"],
            "n_strat_relaxed": flags["n_relaxed"],
            "n_relaxed_slots_total": flags["n_slots"],
            "rows": table}
    summary = (f"{set_label}: {len(table)} w row(s), R={sj['r_used']}, "
               f"fallback={flags['n_fallback']}, "
               f"relaxed={flags['n_relaxed']}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2.pseudo_proton_counterfactual",
                    "inputs": {"set_label": set_label}})


def mixed_event_counterfactual(set_label: str = "minbias",
                               analysis_dir: Optional[str] = None
                               ) -> ToolResult:
    """Event-mixed Delta table for one set: mixed-event count, excluded
    singleton cells, same-source pair fraction, bootstrap error, and the
    preregistered null-validation z value (w=120 only)."""
    _check_set(set_label, "b2.mixed_event_counterfactual")
    rows = [r for r in _b2csv(analysis_dir,
                              "phaseB2_event_mixed_counterfactual.csv")
            if r["set"] == set_label]
    table = [{"w_deg": _i(r["w_deg"]),
              "n_cells_total": _i(r["n_cells_total"]),
              "n_cells_used": _i(r["n_cells_used"]),
              "n_mixed_events": _i(r["n_mixed_events"]),
              "excluded_singleton_events":
                  _i(r["excluded_singleton_events"]),
              "mixed_pairs_total": _i(r["mixed_pairs_total"]),
              "same_source_pair_frac": _f(r["same_source_pair_frac"]),
              "delta_mixed": _f(r["delta_mixed"]),
              "delta_mixed_err": _f(r["delta_mixed_err"]),
              "null_z": _f(r["null_z"]),
              "expected_note": r["expected_note"]} for r in rows]
    table.sort(key=lambda r: r["w_deg"])
    primary = next((r for r in table if r["w_deg"] == 120), None)
    data = {"set": set_label, "rows": table}
    summary = (f"{set_label}: {len(table)} w row(s)"
               + (f", w=120 null_z={primary['null_z']:.3g}"
                  if primary and primary["null_z"] is not None else ""))
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2.mixed_event_counterfactual",
                    "inputs": {"set_label": set_label}})


def history_label_permutation(set_label: str = "minbias",
                              axis: Optional[str] = None,
                              analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """History-label permutation table (w=120): per axis/category the
    real pair fraction and per-category Delta, the permuted mean/SD,
    the enrichment values and their ratio, and the per-permutation
    total-Delta maximum absolute deviation (invariance check)."""
    _check_set(set_label, "b2.history_label_permutation")
    if axis is not None:
        axis = axis.upper()
        if axis not in AXES:
            raise ToolError(f"axis must be one of {AXES}",
                            provenance={"tool": "b2.history_label_permutation"})
    rows = [r for r in _b2csv(analysis_dir,
                              "phaseB2_history_label_permutation.csv")
            if r["set"] == set_label
            and (axis is None or r["axis"] == axis)]
    table = [{"axis": r["axis"], "category": r["category"],
              "F_real": _f(r["F_real"]),
              "delta_c_real": _f(r["delta_c_real"]),
              "delta_total_real": _f(r["delta_total_real"]),
              "F_perm_mean": _f(r["F_perm_mean"]),
              "F_perm_sd": _f(r["F_perm_sd"]),
              "delta_c_perm_mean": _f(r["delta_c_perm_mean"]),
              "delta_c_perm_sd": _f(r["delta_c_perm_sd"]),
              "enrichment_real": _f(r["enrichment_real"]),
              "enrichment_perm_mean": _f(r["enrichment_perm_mean"]),
              "collapse_ratio": _f(r["collapse_ratio"]),
              "total_delta_perm_max_abs_dev":
                  _f(r["total_delta_perm_max_abs_dev"]),
              "n_perm": _i(r["n_perm"])} for r in rows]
    table, note = _rows(table, MAX_ROWS)
    devs = [r["total_delta_perm_max_abs_dev"] for r in table
            if r["total_delta_perm_max_abs_dev"] is not None]
    data = {"set": set_label, "axis": axis,
            "total_delta_invariant": bool(devs) and max(devs) == 0.0,
            "rows": table}
    warnings = [note] if note else []
    summary = f"{set_label} axis={axis or 'ALL'}: {len(table)} row(s)"
    return ToolResult.ok(
        summary, data, warnings=warnings,
        provenance={"tool": "b2.history_label_permutation",
                    "inputs": {"set_label": set_label, "axis": axis}})


def intervention_delta_phi(set_label: str = "minbias",
                           sample: Optional[str] = None,
                           analysis_dir: Optional[str] = None
                           ) -> ToolResult:
    """18-bin Delta-phi comparison for one set across the REAL, PSEUDO
    and MIXED samples: normalized pair densities per bin (with
    event-block bootstrap SDs where tabulated) and the K_120-weighted
    near-side / away-side / total sums per sample."""
    _check_set(set_label, "b2.intervention_delta_phi")
    if sample is not None:
        sample = sample.upper()
        if sample not in SAMPLES:
            raise ToolError(f"sample must be one of {SAMPLES}",
                            provenance={"tool": "b2.intervention_delta_phi"})
    rows = [r for r in _b2csv(analysis_dir,
                              "phaseB2_delta_phi_comparison.csv")
            if r["set"] == set_label
            and (sample is None or r["sample"] == sample)]
    dist = [{"sample": r["sample"], "bin_lo_deg": _f(r["bin_lo_deg"]),
             "bin_hi_deg": _f(r["bin_hi_deg"]),
             "pairs_frac": _f(r["pairs_frac"]),
             "pairs_frac_err": _f(r["pairs_frac_err"])}
            for r in rows if r["section"] == "DIST"]
    awaynear = [{"sample": r["sample"],
                 "ksum_near_w120": _f(r["ksum_near_w120"]),
                 "ksum_away_w120": _f(r["ksum_away_w120"]),
                 "ksum_total_w120": _f(r["ksum_total_w120"]),
                 "pair_frac_away": _f(r["pair_frac_away"])}
                for r in rows if r["section"] == "AWAY_NEAR"]
    data = {"set": set_label, "sample": sample,
            "distribution": dist, "away_near_w120": awaynear}
    summary = (f"{set_label}: {len(dist)} dist bins, "
               f"{len(awaynear)} away/near rows")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2.intervention_delta_phi",
                    "inputs": {"set_label": set_label, "sample": sample}})


_MECHANISM_CLASSES = ("event_wide_kinematic_constraint",
                      "local_hadronic_rescattering",
                      "decay_feeddown",
                      "string_production")


def _b1_axis_rows(axis: str, set_label: str,
                  categories: Optional[tuple] = None) -> List[Dict[str, Any]]:
    fname = {"B": "phaseB1_rescattering_decomposition.csv",
             "C": "phaseB1_formation_decomposition.csv"}[axis]
    rows = [r for r in _b1csv(fname)
            if r["axis"] == axis and r["set"] == set_label
            and r["w_deg"] == "120"
            and (categories is None
                 or any(c in r["category"] for c in categories))]
    return [{"category": r["category"], "n_pairs": _i(r["n_pairs"]),
             "F_c": _f(r["F_c"]), "F_c_err": _f(r["F_c_err"]),
             "delta_c": _f(r["delta_c"]),
             "delta_c_err": _f(r["delta_c_err"]),
             "contribution": _f(r["contribution"]),
             "contribution_err": _f(r["contribution_err"]),
             "support": r["support"]} for r in rows]


def _perm_rows(analysis_dir: Optional[str], set_label: str, axis: str,
               contains: Optional[tuple] = None) -> List[Dict[str, Any]]:
    rows = [r for r in _b2csv(analysis_dir,
                              "phaseB2_history_label_permutation.csv")
            if r["set"] == set_label and r["axis"] == axis
            and (contains is None
                 or any(c in r["category"] for c in contains))]
    return [{"category": r["category"],
             "F_real": _f(r["F_real"]),
             "delta_c_real": _f(r["delta_c_real"]),
             "delta_c_perm_mean": _f(r["delta_c_perm_mean"]),
             "delta_c_perm_sd": _f(r["delta_c_perm_sd"]),
             "enrichment_real": _f(r["enrichment_real"]),
             "enrichment_perm_mean": _f(r["enrichment_perm_mean"]),
             "collapse_ratio": _f(r["collapse_ratio"])} for r in rows]


def mechanism_causal_evidence(set_label: str = "minbias",
                              analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """Structured bundle of the frozen numbers filed under each
    candidate mechanism class, plus the evidence-level ceiling.

    Classes: event-wide kinematic constraint (B1 momentum-balance
    observables, B2-B momentum-scaling correlations), local hadronic
    rescattering (B1 axis-B decomposition, B2-B axis-B permutation
    rows, B2-A status), decay feeddown and string production (B1 axis-C
    decomposition rows, B2-B axis-C permutation rows), each with the
    B2-B pseudo-survival and mixed-null values of the set. Evidence
    ceiling: LEVEL 1 (association) tabulated; LEVEL 2 (necessity)
    unavailable because the B2-A arm is blocked."""
    _check_set(set_label, "b2.mechanism_causal_evidence")

    mb_rows = [r for r in _b1csv("phaseB1_momentum_balance.csv")
               if r["set"] == set_label]
    mb_means = [{"quantity": r["quantity"], "mean": _f(r["value"]),
                 "err": _f(r["err"])}
                for r in mb_rows if r["section"] == "MEAN"]
    mb_corrs = [{"x_var": r["x_var"], "y_var": r["y_var"],
                 "method": r["method"], "value": _f(r["value"]),
                 "err": _f(r["err"])}
                for r in mb_rows if r["section"] == "CORRELATION"]
    ms_rows = [r for r in _b2csv(analysis_dir,
                                 "phaseB2_momentum_scaling.csv")
               if r["set"] == set_label]
    ms_means = [{"quantity": r["quantity"], "mean": _f(r["value"]),
                 "err": _f(r["err"])}
                for r in ms_rows if r["section"] == "MEAN"]
    ms_corrs = [{"x_var": r["x_var"], "method": r["method"],
                 "value": _f(r["value"]), "err": _f(r["err"])}
                for r in ms_rows if r["section"] == "CORR_ABS_DELTA_EV_120"]

    pseudo = [r for r in _b2csv(analysis_dir,
                                "phaseB2_pseudo_proton_counterfactual.csv")
              if r["set"] == set_label and r["w_deg"] == "120"]
    pseudo120 = {"delta_real": _f(pseudo[0]["delta_real"]),
                 "delta_real_err": _f(pseudo[0]["delta_real_err"]),
                 "delta_pseudo": _f(pseudo[0]["delta_pseudo"]),
                 "delta_pseudo_err": _f(pseudo[0]["delta_pseudo_err"]),
                 "pseudo_survival": _f(pseudo[0]["pseudo_survival"]),
                 "survival_gate": pseudo[0]["survival_gate"]} if pseudo else None
    mixed = [r for r in _b2csv(analysis_dir,
                               "phaseB2_event_mixed_counterfactual.csv")
             if r["set"] == set_label and r["w_deg"] == "120"]
    mixed120 = {"delta_mixed": _f(mixed[0]["delta_mixed"]),
                "delta_mixed_err": _f(mixed[0]["delta_mixed_err"]),
                "null_z": _f(mixed[0]["null_z"]),
                "same_source_pair_frac":
                    _f(mixed[0]["same_source_pair_frac"]),
                "expected_note": mixed[0]["expected_note"]} if mixed else None

    bundle = {
        "event_wide_kinematic_constraint": {
            "b1_momentum_balance_means": mb_means,
            "b1_momentum_balance_correlations": mb_corrs,
            "b2_momentum_scaling_means": ms_means,
            "b2_abs_delta_vs_inverse_scale_correlations": ms_corrs},
        "local_hadronic_rescattering": {
            "b1_axisB_decomposition_w120":
                _b1_axis_rows("B", set_label),
            "b2_permutation_axisB":
                _perm_rows(analysis_dir, set_label, "B"),
            "b2a_intervention_status": _b2a_status_rows(analysis_dir)},
        "decay_feeddown": {
            "b1_axisC_decomposition_w120":
                _b1_axis_rows("C", set_label, ("DECAY_PRODUCT",)),
            "b2_permutation_axisC_decay":
                _perm_rows(analysis_dir, set_label, "C",
                           ("DECAY_PRODUCT",))},
        "string_production": {
            "b1_axisC_decomposition_w120":
                _b1_axis_rows("C", set_label, ("STRING_PRODUCT",)),
            "b2_permutation_axisC_string":
                _perm_rows(analysis_dir, set_label, "C",
                           ("STRING_PRODUCT",))},
        "set_level_b2b_values_w120": {"pseudo": pseudo120,
                                      "mixed": mixed120}}
    ceiling = {
        "level_1_association": ("available: tabulated frozen B1 and "
                                "B2-B values above"),
        "level_2_necessity": ("unavailable: the B2-A rescattering-off "
                              "intervention arm is "
                              "BLOCKED_NO_CLEAN_RUNTIME_OPTION; no "
                              "numeric B2-A values exist"),
        "b2a_status": _b2a_status_rows(analysis_dir)["intervention_rows"]}
    data = {"set": set_label, "mechanism_classes": bundle,
            "evidence_level_ceiling": ceiling}
    summary = (f"mechanism bundle for {set_label}: "
               f"{len(_MECHANISM_CLASSES)} classes; LEVEL 2 unavailable "
               f"(B2-A blocked)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2.mechanism_causal_evidence",
                    "inputs": {"set_label": set_label}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_SET_PROP = {"set_label": {"type": "string", "enum": list(SET_LABELS),
                           "default": "minbias"}}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B2 "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "B2-B outputs)"}}

register(ToolSpec(
    name="b2.compare_intervention_baseline",
    description=(
        "Frozen B1 baseline anchors for one set (pairs-weighted Delta "
        "at w=60/90/120/180 with bootstrap SDs and event counts) "
        "alongside the persisted B2-A intervention STATUS rows. The "
        "B2-A arm is blocked; its rows carry status text only, never "
        "numeric values."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=compare_intervention_baseline))

register(ToolSpec(
    name="b2.pseudo_proton_counterfactual",
    description=(
        "Real vs pseudo-proton counterfactual Delta table for one set "
        "and each window width: bootstrap errors, survival value with "
        "its gating label, convergence checkpoints (R=100/250, "
        "R250->R500 drift, flag), replica count used, and POOL_FALLBACK "
        "/ stratified-relaxation event counts."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=pseudo_proton_counterfactual))

register(ToolSpec(
    name="b2.mixed_event_counterfactual",
    description=(
        "Event-mixed counterfactual Delta table for one set and each "
        "window width: mixed-event counts, excluded singleton cells, "
        "same-source pair fraction (leakage), bootstrap error, and the "
        "preregistered null-validation z value (tabulated at w=120)."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=mixed_event_counterfactual))

register(ToolSpec(
    name="b2.history_label_permutation",
    description=(
        "History-label permutation table at w=120 for one set "
        "(optionally one axis A/B/C/D): per category the real pair "
        "fraction and per-category Delta, the 500-permutation mean/SD, "
        "the enrichment values and their ratio, and the per-permutation "
        "total-Delta maximum absolute deviation (invariance check)."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP,
        "axis": {"type": "string", "enum": list(AXES)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=history_label_permutation))

register(ToolSpec(
    name="b2.intervention_delta_phi",
    description=(
        "18-bin Delta-phi comparison for one set across the REAL, "
        "PSEUDO and MIXED samples: normalized per-bin pair densities "
        "(with bootstrap SDs where tabulated) and the K_120-weighted "
        "near-side / away-side / total sums per sample."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP,
        "sample": {"type": "string", "enum": list(SAMPLES)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=intervention_delta_phi))

register(ToolSpec(
    name="b2.mechanism_causal_evidence",
    description=(
        "Structured bundle of the frozen numbers filed under each "
        "candidate mechanism class (event-wide kinematic constraint / "
        "local hadronic rescattering / decay feeddown / string "
        "production): the relevant B1 decomposition and "
        "momentum-balance rows, the B2-B permutation, survival, "
        "null-test and momentum-scaling rows, and the evidence-level "
        "ceiling (LEVEL 2 necessity unavailable because the B2-A arm "
        "is blocked). Values are identical to the CSV deliverables."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=mechanism_causal_evidence))


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
        for name in sorted(n for n in REGISTRY if n.startswith("b2.")):
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
