"""Phase B3-C0 (first-touch STRING product-provenance tagging of the DA
cross-class contribution) read-only tools.

These tools expose the persisted Phase B3-C0 deliverables
(physics_gate/phaseB3C0/analysis/*.csv and *.json). They never run
UrQMD, never open raw file13/file15 output, never touch the shards,
and never execute user-supplied code. Every number they report is
copied from the frozen analysis CSVs/JSON at call time, so the tools
and the CSV deliverables agree by construction.

Provenance-semantics discipline (frozen): the tags carry conservative
possible/definite semantics only. S = every production step of the line
traces to a direct product of a first-touch STRING vertex; N = no
possible path to one; X = at least one possible path but no definite
path — X is reported as its own class and is never merged into S or N;
no parent identity is invented for X. All quantities are
attribution-level tabulations, not mechanism statements. The B3-C0 run
is a provenance-recovery rerun on the same frozen B1 seeds, binary and
deck; no physics change, no patch.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b3c0`` registers the ten ``b3c0.*`` tools
in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b3c0 list
    python3 -m urqmd_agent.tools.azimuthal_b3c0 call \\
        b3c0.da_pair_decomposition '{"cell": "minbias"}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis drivers (support flags, gate details, definition text)
are passed through verbatim as data.
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
B3C0_DIR = REPO_ROOT / "physics_gate" / "phaseB3C0"
B3B_DIR = REPO_ROOT / "physics_gate" / "phaseB3B"
DEFAULT_ANALYSIS_DIR = B3C0_DIR / "analysis"
B3B_ANALYSIS_DIR = B3B_DIR / "analysis"

CELLS = ("minbias", "pooled_b3", "bin0", "bin1", "bin2")
SAMPLES = ("proton", "baryon_Bplus")
SUBCLASSES = ("DA_SS", "DA_SN", "DA_NN", "DA_SX", "DA_NX", "DA_XX",
              "DA_anyU")
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


_HINT = ("the frozen Phase B3-C0 deliverables are missing; the "
         "provenance-tag driver outputs under "
         "physics_gate/phaseB3C0/analysis/ must exist first")


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


def _check_sample(sample: Optional[str], tool: str) -> None:
    if sample is not None and sample not in SAMPLES:
        raise ToolError(f"sample must be one of {SAMPLES}",
                        provenance={"tool": tool})


def _sem(analysis_dir: Optional[str]) -> Dict[str, Any]:
    return _json(analysis_dir, "phaseB3C0_tag_semantics.json")


def _pd_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "sample": r["sample"], "subclass": r["subclass"],
        "n_events": _i(r["n_events"]),
        "n_contributing_events": _i(r["n_contributing_events"]),
        "n_pairs": _i(r["n_pairs"]),
        "support": r["support"],
        "F_within_DA": _f(r["F_within_DA"]),
        "F_within_DA_sd": _f(r["F_within_DA_sd"]),
        "F_within_DA_ci": [_f(r["F_within_DA_ci_lo"]),
                           _f(r["F_within_DA_ci_hi"])],
        "support_DA_total": r["support_DA_total"],
        "n_pairs_DA_total": _i(r["n_pairs_DA_total"])}


def _c1_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "sample": r["sample"], "subclass": r["subclass"],
        "n_events": _i(r["n_events"]),
        "n_contributing_events": _i(r["n_contributing_events"]),
        "n_pairs": _i(r["n_pairs"]),
        "support": r["support"],
        "C1_c": _f(r["C1_c"]), "C1_c_sd": _f(r["C1_c_sd"]),
        "C1_c_ci": [_f(r["C1_c_ci_lo"]), _f(r["C1_c_ci_hi"])],
        "C1_contribution_within_DA": _f(r["C1_contribution_within_DA"]),
        "C1_contribution_within_DA_sd":
            _f(r["C1_contribution_within_DA_sd"]),
        "C1_contribution_within_DA_ci":
            [_f(r["C1_contribution_within_DA_ci_lo"]),
             _f(r["C1_contribution_within_DA_ci_hi"])],
        "C1_contribution_to_total": _f(r["C1_contribution_to_total"]),
        "C1_contribution_to_total_sd": _f(r["C1_contribution_to_total_sd"]),
        "C2_c": _f(r["C2_c"]), "C3_c": _f(r["C3_c"]),
        "C2_contribution_within_DA": _f(r["C2_contribution_within_DA"]),
        "C3_contribution_within_DA": _f(r["C3_contribution_within_DA"])}


def _dl_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "sample": r["sample"], "subclass": r["subclass"],
        "width_deg": _f(r["width_deg"]),
        "n_events": _i(r["n_events"]),
        "n_contributing_events": _i(r["n_contributing_events"]),
        "n_pairs": _i(r["n_pairs"]),
        "support": r["support"],
        "Delta_c": _f(r["Delta_c"]), "Delta_c_sd": _f(r["Delta_c_sd"]),
        "Delta_c_ci": [_f(r["Delta_c_ci_lo"]), _f(r["Delta_c_ci_hi"])],
        "contribution_to_DA": _f(r["contribution_to_DA"]),
        "contribution_to_DA_sd": _f(r["contribution_to_DA_sd"]),
        "contribution_to_DA_ci": [_f(r["contribution_to_DA_ci_lo"]),
                                  _f(r["contribution_to_DA_ci_hi"])],
        "contribution_to_total": _f(r["contribution_to_total"]),
        "contribution_to_total_sd": _f(r["contribution_to_total_sd"]),
        "closure_residual_vs_frozen_Delta_DA":
            _f(r["closure_residual_vs_frozen_Delta_DA"]),
        "closure_residual_vs_frozen_contrib_DA":
            _f(r["closure_residual_vs_frozen_contrib_DA"])}


def _con_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "cell": r["cell"], "sample": r["sample"], "quantity": r["quantity"],
        "definition": r["definition"],
        "n_pairs_withS": _i(r["n_pairs_withS"]),
        "n_events_withS": _i(r["n_events_withS"]),
        "support_withS": r["support_withS"],
        "n_pairs_NN": _i(r["n_pairs_NN"]),
        "n_events_NN": _i(r["n_events_NN"]),
        "support_NN": r["support_NN"],
        "value_withS": _f(r["value_withS"]),
        "value_withS_sd": _f(r["value_withS_sd"]),
        "value_withS_ci": [_f(r["value_withS_ci_lo"]),
                           _f(r["value_withS_ci_hi"])],
        "value_NN": _f(r["value_NN"]), "value_NN_sd": _f(r["value_NN_sd"]),
        "value_NN_ci": [_f(r["value_NN_ci_lo"]), _f(r["value_NN_ci_hi"])],
        "contrast": _f(r["contrast"]),
        "contrast_sd": _f(r["contrast_sd"]),
        "contrast_ci": [_f(r["contrast_ci_lo"]), _f(r["contrast_ci_hi"])]}


def _localization_status(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    prim = [r for r in rows
            if r["quantity"] in ("C1", "Delta120")
            and "excluded from BOTH sides" in r["definition"]]
    both_flagged = all(r["support_withS"] != "ADEQUATE"
                       and r["support_NN"] != "ADEQUATE" for r in prim)
    lstr = [r for r in rows if r["quantity"].startswith("L_STRING")]
    frac_reported = any(r["contrast"] != "" for r in lstr)
    return {
        "primary_contrast_rows": len(prim),
        "both_arms_below_adequacy_everywhere": both_flagged,
        "l_string_fraction_reported_anywhere": frac_reported,
        "statement": (
            "the primary contrast C1(DA_with_S) - C1(DA_NN) carries a "
            "non-ADEQUATE frozen support flag on BOTH arms in every cell "
            "and sample, so the string-localization question is NOT "
            "computable at the frozen support rule from this ensemble; "
            "X-involving pairs are reported separately and are excluded "
            "from both arms; the L_STRING fraction is not reported in "
            "any frozen row — the signed numerator and denominator "
            "contributions are given directly instead")}


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def data_sufficiency(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen B3-C0 Step-1 data-sufficiency verdict: whether the
    existing B3-B shards alone could carry a first-touch STRING
    product-provenance test — the verdict string, the shard scan
    (files, events scanned, per-record key lists), the list of what is
    missing for product provenance, what is usable from the shards, the
    per-item consequences, and the available alternative source."""
    d = _json(analysis_dir, "phaseB3C0_data_sufficiency.json")
    data = {
        "phase": d["phase"], "step": d["step"], "question": d["question"],
        "verdict": d["verdict"],
        "scan": d["scan"],
        "missing_for_product_provenance":
            d["missing_for_product_provenance"],
        "usable_from_shards": d["usable_from_shards"],
        "consequences": d["consequences"],
        "available_alternative_source": d["available_alternative_source"]}
    summary = (f"verdict={d['verdict']}; "
               f"{d['scan']['events_scanned']} events scanned")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3c0.data_sufficiency", "inputs": {}})


def tag_semantics(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen B3-C0 tag semantics and analysis metadata: the S/N/X/U
    provenance-class definitions and flag propagation rules, the frozen
    rules (first-touch vertex, iline-to-STRING map, engine/lineage/
    binary/deck hashes, D grouping), the set estimator, kernel widths,
    the support-adequacy rule, the bootstrap protocol, the cells, the
    pair-class lists, the primary-contrast definition, the L_STRING
    sign-stable-denominator rule, the language discipline, the audit
    selection, and the rerun statement."""
    d = _sem(analysis_dir)
    data = {k: d[k] for k in
            ("phase", "kind", "question", "provenance_classes", "flags",
             "frozen_rules", "estimator", "widths_deg", "support_rule",
             "bootstrap", "cells", "pair_classes", "primary_contrast",
             "L_STRING", "language_discipline", "audit_selection",
             "rerun")}
    summary = "frozen S/N/X/U tag semantics and analysis metadata"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3c0.tag_semantics", "inputs": {}})


def tag_coverage(cell: Optional[str] = None, sample: Optional[str] = None,
                 analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen provenance-tag coverage table per cell, sample
    (proton / baryon_Bplus) and class (S/N/X/U): counts, fractions of
    the accepted sample, and ambiguity-depth statistics (mean, median,
    max). cell and sample are optional filters; omitting both returns
    the full table."""
    tool = "b3c0.tag_coverage"
    _check_cell(cell, tool)
    _check_sample(sample, tool)
    rows = [{
        "cell": r["cell"], "sample": r["sample"],
        "prov_class": r["prov_class"],
        "count": _i(r["count"]), "frac": _f(r["frac"]),
        "depth_mean": _f(r["depth_mean"]),
        "depth_median": _f(r["depth_median"]),
        "depth_max": _i(r["depth_max"])}
        for r in _csv(analysis_dir, "phaseB3C0_tag_coverage.csv")
        if (cell is None or r["cell"] == cell)
        and (sample is None or r["sample"] == sample)]
    sem = _sem(analysis_dir)
    data = {"rows": rows,
            "provenance_classes": sem["provenance_classes"],
            "depth_definition": sem["flags"]["fts_depth"],
            "cells": sem["cells"]}
    summary = f"{len(rows)} tag-coverage row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "sample": sample}})


def da_pair_decomposition(cell: Optional[str] = None,
                          sample: Optional[str] = None,
                          analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen DA provenance-subclass pair decomposition per cell and
    sample (proton / baryon_Bplus): pair counts and frozen support flags
    per subclass (DA_SS/DA_SN/DA_NN/DA_SX/DA_NX/DA_XX/DA_anyU), the
    within-DA pair fraction F with bootstrap SD and 95% CI, and the
    DA-total support flag and pair count. cell and sample are optional
    filters."""
    tool = "b3c0.da_pair_decomposition"
    _check_cell(cell, tool)
    _check_sample(sample, tool)
    rows = [_pd_row(r)
            for r in _csv(analysis_dir, "phaseB3C0_DA_pair_decomposition.csv")
            if (cell is None or r["cell"] == cell)
            and (sample is None or r["sample"] == sample)]
    sem = _sem(analysis_dir)
    data = {"rows": rows,
            "support_rule": sem["support_rule"],
            "subclass_rule": sem["pair_classes"]["rule"],
            "subclasses": sem["pair_classes"]["provenance_within_DA"]}
    summary = f"{len(rows)} DA pair-decomposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "sample": sample}})


def da_c1_decomposition(cell: Optional[str] = None,
                        sample: Optional[str] = None,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen per-subclass C1 decomposition of the DA cross class
    per cell and sample: class-level C1_c with bootstrap SD and 95% CI,
    the additive C1 contribution within DA (with SD and CI) and to the
    set total (with SD), and the C2/C3 diagnostics. CIs are tabulated
    for every subclass; the frozen support flag says which subclasses
    meet the adequacy rule. cell and sample are optional filters."""
    tool = "b3c0.da_c1_decomposition"
    _check_cell(cell, tool)
    _check_sample(sample, tool)
    rows = [_c1_row(r)
            for r in _csv(analysis_dir, "phaseB3C0_DA_C1_decomposition.csv")
            if (cell is None or r["cell"] == cell)
            and (sample is None or r["sample"] == sample)]
    sem = _sem(analysis_dir)
    data = {"rows": rows, "estimator": sem["estimator"],
            "support_rule": sem["support_rule"],
            "bootstrap": sem["bootstrap"]}
    summary = f"{len(rows)} DA C1-decomposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "sample": sample}})


def da_delta_decomposition(cell: Optional[str] = None,
                           sample: Optional[str] = None,
                           width_deg: Optional[float] = None,
                           analysis_dir: Optional[str] = None
                           ) -> ToolResult:
    """The frozen per-subclass Delta(w) decomposition of the DA cross
    class per cell, sample and kernel width (60/90/120/180; 120 is the
    primary width): class-level Delta_c with bootstrap SD and 95% CI,
    the additive contributions to the DA Delta (with SD and CI) and to
    the set total (with SD), and the closure residuals against the
    frozen DA Delta and DA contribution (populated for the proton
    sample; empty for the baryon sample in the frozen CSV). cell,
    sample and width_deg are optional filters."""
    tool = "b3c0.da_delta_decomposition"
    _check_cell(cell, tool)
    _check_sample(sample, tool)
    if width_deg is not None and f"{float(width_deg)}" not in WIDTHS:
        raise ToolError(f"width_deg must be one of {WIDTHS}",
                        provenance={"tool": tool})
    rows = [_dl_row(r)
            for r in _csv(analysis_dir, "phaseB3C0_DA_delta_decomposition.csv")
            if (cell is None or r["cell"] == cell)
            and (sample is None or r["sample"] == sample)
            and (width_deg is None or r["width_deg"] == f"{float(width_deg)}")]
    sem = _sem(analysis_dir)
    data = {"rows": rows, "estimator": sem["estimator"],
            "widths_deg": sem["widths_deg"],
            "support_rule": sem["support_rule"],
            "closure_note": ("subclass decomposition exact by "
                             "construction; closure residuals asserted "
                             "per cell in the frozen driver and recorded "
                             "for the proton sample")}
    summary = f"{len(rows)} DA Delta-decomposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "sample": sample,
                               "width_deg": width_deg}})


def string_localization_contrast(cell: Optional[str] = None,
                                 sample: Optional[str] = None,
                                 analysis_dir: Optional[str] = None
                                 ) -> ToolResult:
    """The frozen string-localization contrast table per cell and
    sample: the primary C1(DA_with_S) - C1(DA_NN) contrast and the
    secondary Delta120 version (both arms with pair/event counts,
    frozen support flags, bootstrap SDs and 95% CIs), the separately
    reported X-involving C1 rows, and the L_STRING numerator and
    denominator rows with the frozen sign-stable-denominator rule.
    Includes an explicit NOT-computable status statement derived from
    the frozen support flags. cell and sample are optional filters."""
    tool = "b3c0.string_localization_contrast"
    _check_cell(cell, tool)
    _check_sample(sample, tool)
    raw = _csv(analysis_dir, "phaseB3C0_string_localization_contrast.csv")
    rows = [_con_row(r) for r in raw
            if (cell is None or r["cell"] == cell)
            and (sample is None or r["sample"] == sample)]
    sem = _sem(analysis_dir)
    data = {"rows": rows,
            "primary_contrast": sem["primary_contrast"],
            "L_STRING_rule": sem["L_STRING"],
            "localization_status": _localization_status(raw)}
    summary = f"{len(rows)} string-localization contrast row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"cell": cell, "sample": sample}})


def baryon_corroboration(cell: Optional[str] = None,
                         analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen all-B=+1 corroboration tables per cell: the species
    composition (proton / neutron / strange_verified / other_verified)
    within each endpoint group (A-N, A-S, A-X, D-N, D-S, D-X, P-X) with
    counts and within-group fractions, plus the endpoint cross-class
    counts per lineage group (A/D/P/U) and provenance class. cell is an
    optional filter."""
    tool = "b3c0.baryon_corroboration"
    _check_cell(cell, tool)
    comp = [{"cell": r["cell"], "endpoint_group": r["endpoint_group"],
             "species": r["species"], "count": _i(r["count"]),
             "frac_within_group": _f(r["frac_within_group"])}
            for r in _csv(analysis_dir, "phaseB3C0_baryon_corroboration.csv")
            if cell is None or r["cell"] == cell]
    cross = [{"cell": r["cell"], "lineage_group": r["lineage_group"],
              "prov_class": r["prov_class"],
              "n_endpoints": _i(r["n_endpoints"])}
             for r in _csv(analysis_dir,
                           "phaseB3C0_endpoint_crossclasses.csv")
             if cell is None or r["cell"] == cell]
    sem = _sem(analysis_dir)
    data = {"species_composition": comp,
            "endpoint_crossclasses": cross,
            "note": ("all interacting B=+1 particles (not only accepted "
                     "protons); species labels as frozen in the driver "
                     "output"),
            "provenance_classes": sem["provenance_classes"]}
    summary = (f"{len(comp)} species-composition row(s), "
               f"{len(cross)} cross-class row(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool, "inputs": {"cell": cell}})


def invariance_gates(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen B3-C0 gate table (all production gates with status and
    detail strings, n_fail and the overall verdict) and the two frozen
    invariance reports: uid relabeling invariance and row-order
    permutation invariance on the audit events (event counts,
    relabeling/permutation counts per event, failure counts, per-event
    pass flags)."""
    gates = _json(analysis_dir, "phaseB3C0_gates.json")
    uid = _json(analysis_dir, "phaseB3C0_uid_invariance.json")
    ro = _json(analysis_dir, "phaseB3C0_roworder_invariance.json")

    def _inv(d, fail_key):
        return {
            "n_events": d["n_events"],
            "n_relabelings_per_event": d["n_relabelings_per_event"],
            "n_row_perms_per_event": d["n_row_perms_per_event"],
            "n_ctag_order_violations": d["n_ctag_order_violations"],
            "gate": d["gate"],
            "n_fail": d[fail_key],
            "events": [{
                "source": Path(e["source"]).name,
                "audit_set": e["audit_set"],
                "n_interactions": e["n_interactions"],
                "n_final": e["n_final"],
                "uid_invariance": e["uid_invariance"],
                "roworder_invariance": e["roworder_invariance"],
                "n_relabelings": e["n_relabelings"],
                "n_row_perms": e["n_row_perms"]}
                for e in d["events"]]}

    data = {
        "overall": gates["overall"],
        "n_gates": gates["n_gates"], "n_fail": gates["n_fail"],
        "gates": gates["gates"],
        "uid_invariance": _inv(uid, "n_uid_invariance_fail"),
        "roworder_invariance": _inv(ro, "n_roworder_invariance_fail"),
        "rerun_note": _sem(analysis_dir)["rerun"]}
    summary = (f"overall={gates['overall']} ({gates['n_gates']} gates, "
               f"{gates['n_fail']} fail); uid gate={uid['gate']}, "
               f"roworder gate={ro['gate']}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3c0.invariance_gates", "inputs": {}})


def mechanism_evidence(analysis_dir: Optional[str] = None
                       ) -> ToolResult:
    """A bundled read-only summary of the frozen B3-C0 outputs: the gate
    verdict, the X-saturation coverage headline (minbias and central
    bin0), the minbias w=120 DA subclass contributions with support
    flags and the XX pair fraction, the minbias primary
    string-localization contrast with its NOT-computable status, and
    the frozen B3-B anchors (the minbias w=120 DD/DA/AA additive Delta
    contributions, the minbias R_Bplus_STRING alignment, and the minbias
    initial interacting-nucleon C1 context). Data only."""
    gates = _json(analysis_dir, "phaseB3C0_gates.json")
    cov = _csv(analysis_dir, "phaseB3C0_tag_coverage.csv")

    def _cov_x(c):
        r = next(r for r in cov if r["cell"] == c
                 and r["sample"] == "proton" and r["prov_class"] == "X")
        return {"frac_X": _f(r["frac"]),
                "depth_mean_X": _f(r["depth_mean"])}

    dl = [r for r in _csv(analysis_dir,
                          "phaseB3C0_DA_delta_decomposition.csv")
          if r["cell"] == "minbias" and r["sample"] == "proton"
          and r["width_deg"] == "120.0"]
    pd_xx = next(r for r in
                 _csv(analysis_dir, "phaseB3C0_DA_pair_decomposition.csv")
                 if r["cell"] == "minbias" and r["sample"] == "proton"
                 and r["subclass"] == "DA_XX")
    raw_con = _csv(analysis_dir, "phaseB3C0_string_localization_contrast.csv")
    con_c1 = next(r for r in raw_con
                  if r["cell"] == "minbias" and r["sample"] == "proton"
                  and r["quantity"] == "C1"
                  and "excluded from BOTH sides" in r["definition"])
    anch = [r for r in _b3b_csv("phaseB3B_proton_pair_decomposition.csv")
            if r["cell"] == "minbias" and r["width_deg"] == "120.0"
            and r["class"] in ("DD", "DA", "AA")]
    neg = [r["class"] for r in anch if _f(r["contribution"]) is not None
           and float(r["contribution"]) < 0]
    al = next(r for r in _b3b_csv("phaseB3B_first_touch_alignment.csv")
              if r["cell"] == "minbias" and r["quantity"] == "R_Bplus_STRING")
    ih = next(r for r in _b3b_csv("phaseB3B_initial_nucleon_harmonics.csv")
              if r["cell"] == "minbias")
    sem = _sem(analysis_dir)
    data = {
        "gates_overall": gates["overall"], "n_fail": gates["n_fail"],
        "x_saturation_protons": {"minbias": _cov_x("minbias"),
                                 "bin0_central": _cov_x("bin0")},
        "minbias_w120_DA_subclass_contributions": [{
            "subclass": r["subclass"], "n_pairs": _i(r["n_pairs"]),
            "support": r["support"],
            "contribution_to_DA": _f(r["contribution_to_DA"]),
            "contribution_to_DA_ci":
                [_f(r["contribution_to_DA_ci_lo"]),
                 _f(r["contribution_to_DA_ci_hi"])]} for r in dl],
        "da_xx_pair_fraction_minbias_proton": {
            "F_within_DA": _f(pd_xx["F_within_DA"]),
            "F_within_DA_ci": [_f(pd_xx["F_within_DA_ci_lo"]),
                               _f(pd_xx["F_within_DA_ci_hi"])],
            "support": pd_xx["support"]},
        "minbias_primary_contrast_C1": _con_row(con_c1),
        "localization_status": _localization_status(raw_con),
        "b3b_anchors": {
            "minbias_w120_DD_DA_AA_contributions": [{
                "class": r["class"], "contribution": _f(r["contribution"]),
                "contribution_ci": [_f(r["contribution_ci_lo"]),
                                    _f(r["contribution_ci_hi"])],
                "support": r["support"]} for r in anch],
            "negative_contribution_classes": neg,
            "R_Bplus_STRING_minbias": {
                "R": _f(al["R"]),
                "R_ci": [_f(al["R_ci_lo"]), _f(al["R_ci_hi"])],
                "support": al["support"],
                "n_support_events": _i(al["n_support_events"])},
            "initial_nucleon_C1_minbias": {
                "source": "frozen B3-B "
                          "(phaseB3B_initial_nucleon_harmonics.csv)",
                "label": "frozen B3-B evidence, diagnostic only",
                "C1_initial": _f(ih["C1_initial"]),
                "C1_initial_pT_weighted": _f(ih["C1_initial_pT_weighted"]),
                "n_events": _i(ih["n_events"]),
                "n_pairs": _i(ih["n_pairs"]),
                "caveat": ("a nonzero initial dipole pre-exists in the "
                           "incoming transverse momenta; even positive "
                           "localization could not mean strings generate "
                           "the dipole from zero, and a null here would "
                           "not be proof of dynamical generation")}},
        "language_discipline": sem["language_discipline"],
        "rerun": sem["rerun"]}
    summary = ("B3-C0 bundle: gates, X-saturation, minbias DA subclass "
               "contributions, primary contrast status, B3-B anchors")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3c0.mechanism_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B3-C0 "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "frozen outputs)"}}
_CELL_PROP = {"cell": {"type": "string", "enum": list(CELLS)}}
_SAMPLE_PROP = {"sample": {"type": "string", "enum": list(SAMPLES)}}

register(ToolSpec(
    name="b3c0.data_sufficiency",
    description=(
        "The frozen B3-C0 Step-1 data-sufficiency verdict: whether the "
        "existing B3-B shards alone could carry a first-touch STRING "
        "product-provenance test — shard scan, missing items, usable "
        "items, consequences, and the alternative source."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=data_sufficiency))

register(ToolSpec(
    name="b3c0.tag_semantics",
    description=(
        "The frozen B3-C0 tag semantics: S/N/X/U provenance-class "
        "definitions, flag propagation rules, frozen rules (vertex "
        "definition, iline map, engine/binary/deck hashes), estimator, "
        "widths, support rule, bootstrap protocol, cells, pair classes, "
        "primary contrast, L_STRING rule, language discipline, audit "
        "selection and rerun statement."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=tag_semantics))

register(ToolSpec(
    name="b3c0.tag_coverage",
    description=(
        "The frozen provenance-tag coverage per cell, sample and class "
        "(S/N/X/U; cell and sample optional): counts, fractions of the "
        "accepted sample, and ambiguity-depth statistics."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_SAMPLE_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=tag_coverage))

register(ToolSpec(
    name="b3c0.da_pair_decomposition",
    description=(
        "The frozen DA provenance-subclass pair decomposition per cell "
        "and sample (both optional): pair counts, frozen support flags, "
        "within-DA pair fractions with bootstrap CIs, and the DA-total "
        "support flag and pair count."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_SAMPLE_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=da_pair_decomposition))

register(ToolSpec(
    name="b3c0.da_c1_decomposition",
    description=(
        "The frozen per-subclass C1 decomposition of the DA cross class "
        "per cell and sample (both optional): class-level C1_c with "
        "bootstrap CIs, additive C1 contributions within DA and to the "
        "set total, and C2/C3 diagnostics."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_SAMPLE_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=da_c1_decomposition))

register(ToolSpec(
    name="b3c0.da_delta_decomposition",
    description=(
        "The frozen per-subclass Delta(w) decomposition of the DA cross "
        "class per cell, sample and kernel width (all optional; 60/90/"
        "120/180, primary 120): class-level Delta_c with bootstrap CIs, "
        "additive contributions to the DA Delta and the set total, and "
        "closure residuals against the frozen DA values."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_SAMPLE_PROP,
        "width_deg": {"type": "number", "enum": [60, 90, 120, 180]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=da_delta_decomposition))

register(ToolSpec(
    name="b3c0.string_localization_contrast",
    description=(
        "The frozen string-localization contrast table per cell and "
        "sample (both optional): the primary C1(DA_with_S) - C1(DA_NN) "
        "contrast and its Delta120 secondary with frozen support flags "
        "and bootstrap CIs, the separately reported X-involving rows, "
        "the L_STRING numerator/denominator rows, and an explicit "
        "NOT-computable status statement from the frozen flags."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_SAMPLE_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=string_localization_contrast))

register(ToolSpec(
    name="b3c0.baryon_corroboration",
    description=(
        "The frozen all-B=+1 corroboration tables (cell optional): "
        "species composition within each endpoint group (A-N, A-S, A-X, "
        "D-N, D-S, D-X, P-X) with counts and within-group fractions, "
        "plus endpoint cross-class counts per lineage group and "
        "provenance class."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=baryon_corroboration))

register(ToolSpec(
    name="b3c0.invariance_gates",
    description=(
        "The frozen B3-C0 gate table (status and detail per gate, "
        "n_fail, overall verdict) and the uid-relabeling and row-order "
        "permutation invariance reports on the audit events."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=invariance_gates))

register(ToolSpec(
    name="b3c0.mechanism_evidence",
    description=(
        "A bundled read-only summary of the frozen B3-C0 outputs: gate "
        "verdict, X-saturation coverage headline, minbias w=120 DA "
        "subclass contributions with support flags and the XX pair "
        "fraction, minbias primary contrast with its NOT-computable "
        "status, and the frozen B3-B anchors (DD/DA/AA contributions, "
        "R_Bplus_STRING). Data only."),
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
        for name in sorted(n for n in REGISTRY if n.startswith("b3c0.")):
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
