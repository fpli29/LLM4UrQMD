"""Phase B3-B (history-recovery lineage attribution of the proton
azimuthal-partition signal) read-only tools.

These tools expose the persisted Phase B3-B deliverables
(physics_gate/phaseB3B/analysis/*.csv and *.json, plus the recovery
manifests under physics_gate/phaseB3B/data/). They never run UrQMD,
never open raw file13/file15 output, never touch the recovered-history
shards, and never execute user-supplied code. Every number they report
is copied from the frozen analysis CSVs/JSON at call time, so the
tools and the CSV deliverables agree by construction.

Lineage-semantics discipline (repaired B3-B0R semantics, frozen): the
lineage classes carry possible-sources information only; there is no
unique ancestry for class D2; class A is the initial-or-pair ambiguous
class and is never labeled as newly created. All quantities are
attribution-level tabulations, not mechanism statements.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b3b`` registers the ten ``b3b.*`` tools
in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b3b list
    python3 -m urqmd_agent.tools.azimuthal_b3b call \\
        b3b.proton_pair_decomposition '{"cell": "minbias"}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis drivers (support flags, gate details, question text) are
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
B3B_DIR = REPO_ROOT / "physics_gate" / "phaseB3B"
DEFAULT_ANALYSIS_DIR = B3B_DIR / "analysis"
DEFAULT_DATA_DIR = B3B_DIR / "data"

CELLS = ("minbias", "pooled_b3", "bin0", "bin1", "bin2")
PAIR_CLASSES = ("DD", "DA", "AA", "DP", "AP", "PP", "any-U")
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


_HINT = ("the frozen Phase B3-B deliverables are missing; the "
         "attribution driver outputs under "
         "physics_gate/phaseB3B/analysis/ must exist first")


def _csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_csv(d / fname, _HINT)


def _json(analysis_dir: Optional[str], fname: str) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_json(d / fname, _HINT)


def _data_json(fname: str) -> Dict[str, Any]:
    return _read_json(DEFAULT_DATA_DIR / fname, _HINT)


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


def _meta(analysis_dir: Optional[str]) -> Dict[str, Any]:
    return _json(analysis_dir, "phaseB3B_attribution_metadata.json")


def _pd_row(r: Dict[str, str]) -> Dict[str, Any]:
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
        "C2_c": _f(r["C2_c"]), "C3_c": _f(r["C3_c"]),
        "C2_contribution": _f(r["C2_contribution"]),
        "C3_contribution": _f(r["C3_contribution"])}


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def history_recovery_status(analysis_dir: Optional[str] = None
                            ) -> ToolResult:
    """The frozen B3-B history-recovery status: the Step-5 production
    gates A-N (all pass flags and detail strings), the sentinel-chunk
    record (chunk k000, ordinals 1-100, class counts, timings,
    result), and the recovery manifest/index counts (n_shards,
    n_events, n_audit, audit rule, frozen binary and engine hashes)."""
    gates = _json(analysis_dir, "phaseB3B_history_recovery_gates.json")
    sent = _json(analysis_dir, "phaseB3B_sentinel.json")
    man = _data_json("phaseB3B_history_recovery_manifest.json")
    idx = _data_json("phaseB3B_history_recovery_index.json")
    data = {
        "all_gates_pass": gates["all_pass"],
        "gates": gates["gates"],
        "definitions": gates["definitions"],
        "sentinel": {
            "chunk": sent["chunk"], "ordinals": sent["ordinals"],
            "n_events": sent["n_events"],
            "n_b1_exact": sent["n_b1_exact"],
            "n_validation_pass": sent["n_validation_pass"],
            "n_lineage_violations": sent["n_lineage_violations"],
            "classes_protons": sent["classes_protons"],
            "classes_baryons": sent["classes_baryons"],
            "result": sent["result"]},
        "recovery_counts": {
            "n_shards": man["n_shards"],
            "frozen_binary_sha256": man["frozen_binary_sha256"],
            "engine_sha256": man["engine_sha256"],
            "n_events": idx["n_events"],
            "n_audit": idx["n_audit"],
            "audit_rule": idx["audit_rule"]},
        "rerun_note": ("the history recovery is a rerun on the same "
                       "frozen B1 seeds with full f13/f15 retention; "
                       "the frozen binary hash is unchanged")}
    summary = (f"recovery gates all_pass={gates['all_pass']}; "
               f"{man['n_shards']} shards, {idx['n_events']} events")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.history_recovery_status", "inputs": {}})


def lineage_coverage(analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen lineage coverage table per sample (protons /
    all-B=+1) and slice: class counts and fractions for D1 (unique
    connection to an incoming initial nucleon), D2 (definite but
    non-unique connection), D = D1 + D2, A (initial-or-pair
    ambiguous), P and U; with the frozen D-grouping definition."""
    rows = [{
        "sample": r["sample"], "slice": r["slice"],
        "N_events": _i(r["N_events"]), "N_total": _i(r["N_total"]),
        "N_D1": _i(r["N_D1"]), "N_D2": _i(r["N_D2"]),
        "N_D": _i(r["N_D"]), "N_A": _i(r["N_A"]),
        "N_P": _i(r["N_P"]), "N_U": _i(r["N_U"]),
        "frac_D1": _f(r["frac_D1"]), "frac_D2": _f(r["frac_D2"]),
        "frac_D": _f(r["frac_D"]), "frac_A": _f(r["frac_A"]),
        "frac_P": _f(r["frac_P"]), "frac_U": _f(r["frac_U"])}
        for r in _csv(analysis_dir, "phaseB3B_lineage_coverage.csv")]
    data = {"rows": rows,
            "D_grouping": _meta(analysis_dir)["D_grouping"],
            "audit_reference": _meta(analysis_dir)["audit_reference"]}
    summary = f"{len(rows)} coverage row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.lineage_coverage", "inputs": {}})


def proton_pair_decomposition(cell: Optional[str] = None,
                              width_deg: Optional[float] = None,
                              analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """The frozen accepted-proton pair decomposition per cell, kernel
    width and pair class (DD/DA/AA/DP/AP/PP/any-U): pair counts and
    frozen support flags, pair-fraction F, class-level Delta_c and
    C1_c, and the additive contributions to the set Delta(w) and C1
    with bootstrap SDs and 95% CIs. cell and width_deg (60/90/120/180)
    are optional filters; omitting both returns the full table."""
    _check_cell(cell, "b3b.proton_pair_decomposition")
    if width_deg is not None and f"{float(width_deg)}" not in WIDTHS:
        raise ToolError(f"width_deg must be one of {WIDTHS}",
                        provenance={"tool": "b3b.proton_pair_decomposition"})
    rows = [_pd_row(r)
            for r in _csv(analysis_dir, "phaseB3B_proton_pair_decomposition.csv")
            if (cell is None or r["cell"] == cell)
            and (width_deg is None
                 or r["width_deg"] == f"{float(width_deg)}")]
    data = {"estimator": _meta(analysis_dir)["estimator"],
            "support_rule": _meta(analysis_dir)["support_rule"],
            "pair_categories": _meta(analysis_dir)["pair_categories"],
            "rows": rows}
    summary = f"{len(rows)} proton pair-decomposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.proton_pair_decomposition",
                    "inputs": {"cell": cell, "width_deg": width_deg}})


def baryon_pair_decomposition(cell: Optional[str] = None,
                              analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """The frozen all-B=+1 (interacting baryon) corroboration table per
    cell: C1 decomposition by the same pair classes (pair counts,
    support flags, F, class-level C1_c and C1 contribution with
    bootstrap SDs and 95% CIs, C2/C3 diagnostics), plus the frozen
    species-composition rows within the D and A endpoint classes.
    cell is an optional filter."""
    _check_cell(cell, "b3b.baryon_pair_decomposition")
    dec, comp = [], []
    for r in _csv(analysis_dir, "phaseB3B_baryon_pair_decomposition.csv"):
        if cell is not None and r["cell"] != cell:
            continue
        if r["record_type"] == "C1_decomposition":
            dec.append({
                "cell": r["cell"], "class": r["class"],
                "n_events": _i(r["n_events"]),
                "n_contributing_events": _i(r["n_contributing_events"]),
                "n_pairs": _i(r["n_pairs"]), "support": r["support"],
                "F": _f(r["F"]),
                "C1_c": _f(r["C1_c"]), "C1_c_sd": _f(r["C1_c_sd"]),
                "C1_c_ci": [_f(r["C1_c_ci_lo"]), _f(r["C1_c_ci_hi"])],
                "C1_contribution": _f(r["C1_contribution"]),
                "C1_contribution_sd": _f(r["C1_contribution_sd"]),
                "C1_contribution_ci": [_f(r["C1_contribution_ci_lo"]),
                                       _f(r["C1_contribution_ci_hi"])],
                "C2_c": _f(r["C2_c"]), "C3_c": _f(r["C3_c"]),
                "C2_contribution": _f(r["C2_contribution"]),
                "C3_contribution": _f(r["C3_contribution"])})
        else:
            comp.append({
                "cell": r["cell"], "endpoint_class": r["class"],
                "species": r["species"],
                "species_count": _i(r["species_count"]),
                "species_frac": _f(r["species_frac"]),
                "class_total": _i(r["n_pairs"])})
    data = {"C1_decomposition": dec, "species_composition": comp,
            "note": ("all interacting B=+1 particles (not only accepted "
                     "protons); same frozen class definitions")}
    summary = (f"{len(dec)} baryon C1-decomposition row(s), "
               f"{len(comp)} species row(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.baryon_pair_decomposition",
                    "inputs": {"cell": cell}})


def initial_nucleon_harmonics(analysis_dir: Optional[str] = None
                              ) -> ToolResult:
    """The frozen initial interacting-nucleon pair harmonics per cell
    (unweighted and pT-weighted C1, unweighted C2, pair counts), with
    the frozen attribution-diagnostic question text, and the frozen
    final-state accepted-proton total C1 per cell for juxtaposition."""
    init = [{"cell": r["cell"], "n_events": _i(r["n_events"]),
             "n_pairs": _i(r["n_pairs"]),
             "C1_initial": _f(r["C1_initial"]),
             "C2_initial": _f(r["C2_initial"]),
             "C1_initial_pT_weighted": _f(r["C1_initial_pT_weighted"]),
             "question": r["question"]}
            for r in _csv(analysis_dir,
                          "phaseB3B_initial_nucleon_harmonics.csv")]
    final_p = [{"cell": r["cell"], "C1_total": _f(r["total"]),
                "C1_total_sd": _f(r["total_sd"]),
                "C1_total_ci": [_f(r["total_ci_lo"]),
                                _f(r["total_ci_hi"])]}
               for r in _csv(analysis_dir, "phaseB3B_C1_decomposition.csv")
               if r["harmonic"] == "C1"]
    data = {"initial": init, "final_proton_C1": final_p,
            "reading_note": ("attribution diagnostic only: it compares "
                             "the dipole of incoming transverse momenta "
                             "with the final-state dipole; a null initial "
                             "value would not establish dynamical "
                             "generation")}
    summary = f"{len(init)} initial-harmonic row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.initial_nucleon_harmonics",
                    "inputs": {}})


def first_touch_summary(analysis_dir: Optional[str] = None
                        ) -> ToolResult:
    """The frozen first-touch vertex tables: vertex counts per cell,
    broad process class and vertex class (OLD_VIRGIN /
    PRIMARY_PRIMARY), and the frozen iline process map (broad class,
    source citation, mapped flag, vertex and initial-nucleon counts
    per iline)."""
    vtx = [{"cell": r["cell"], "process_class": r["process_class"],
            "vertex_class": r["vertex_class"],
            "n_events": _i(r["n_events"]),
            "n_vertices": _i(r["n_vertices"])}
           for r in _csv(analysis_dir, "phaseB3B_first_touch_vertices.csv")]
    pm = [{"iline": _i(r["iline"]), "nout_rule": r["nout_rule"],
           "taxonomy_coarse": r["taxonomy_coarse"],
           "broad_class": r["broad_class"], "citation": r["citation"],
           "n_first_touch_vertices": _i(r["n_first_touch_vertices"]),
           "n_initial_nucleons": _i(r["n_initial_nucleons"]),
           "mapped": r["mapped"]}
          for r in _csv(analysis_dir, "phaseB3B_first_process_map.csv")]
    data = {"vertices": vtx, "process_map": pm,
            "process_map_source": _meta(analysis_dir)["process_map_source"],
            "broad_process_classes":
                _meta(analysis_dir)["broad_process_classes"]}
    summary = f"{len(vtx)} vertex row(s), {len(pm)} process-map row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.first_touch_summary", "inputs": {}})


def first_touch_impulse(analysis_dir: Optional[str] = None
                        ) -> ToolResult:
    """The frozen first-touch impulse table per cell, sector (bp =
    B=+1, bm = B=-1, mes = mesons, oth = other, ALL) and broad process
    class: event and vertex counts, mean impulse components and
    magnitudes, and the momentum-closure statistics of the impulse
    bookkeeping."""
    rows = [{"cell": r["cell"], "sector": r["sector"],
             "process_class": r["process_class"],
             "n_events": _i(r["n_events"]),
             "n_vertices": _i(r["n_vertices"]),
             "mean_impulse_x": _f(r["mean_impulse_x"]),
             "mean_impulse_y": _f(r["mean_impulse_y"]),
             "mean_impulse_mag": _f(r["mean_impulse_mag"]),
             "sd_impulse_mag": _f(r["sd_impulse_mag"]),
             "closure_mean_abs": _f(r["closure_mean_abs"]),
             "closure_max_abs": _f(r["closure_max_abs"]),
             "closure_mean_rel": _f(r["closure_mean_rel"]),
             "closure_max_rel": _f(r["closure_max_rel"])}
            for r in _csv(analysis_dir,
                          "phaseB3B_first_touch_impulse.csv")]
    data = {"rows": rows,
            "note": ("impulse bookkeeping on the frozen first-touch "
                     "vertices; closure columns quantify the identity, "
                     "they do not interpret it")}
    summary = f"{len(rows)} impulse row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.first_touch_impulse", "inputs": {}})


def first_touch_process_alignment(analysis_dir: Optional[str] = None
                                  ) -> ToolResult:
    """The frozen first-touch alignment table per cell: R_Bplus, R_M
    and R_Bplus_minus_R_M, and the per-broad-process-class R_Bplus
    slices, each with event counts, frozen support flags, bootstrap
    SDs and 95% CIs, mean cosines, and the Qp floor."""
    meta = _meta(analysis_dir)
    rows = [{"cell": r["cell"], "quantity": r["quantity"],
             "n_events_cell": _i(r["n_events_cell"]),
             "n_support_events": _i(r["n_support_events"]),
             "support": r["support"],
             "R": _f(r["R"]), "R_sd": _f(r["R_sd"]),
             "R_ci": [_f(r["R_ci_lo"]), _f(r["R_ci_hi"])],
             "mean_cos": _f(r["mean_cos"]),
             "mean_cos_sd": _f(r["mean_cos_sd"]),
             "mean_cos_ci": [_f(r["mean_cos_ci_lo"]),
                             _f(r["mean_cos_ci_hi"])],
             "qp_floor": _f(r["qp_floor"])}
            for r in _csv(analysis_dir,
                          "phaseB3B_first_touch_alignment.csv")]
    data = {"rows": rows, "qp_floor": meta["qp_floor"],
            "qp_note": meta["qp_note"],
            "sign_note": ("R > 0 tabulated convention: the sector "
                          "first-touch impulse opposes the final proton "
                          "Qp; R is a pT-weighted diagnostic")}
    summary = f"{len(rows)} alignment row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.first_touch_process_alignment",
                    "inputs": {}})


def definite_first_process(analysis_dir: Optional[str] = None
                           ) -> ToolResult:
    """The frozen definite-first-process tables: per cell and endpoint
    class (D1/D2), the counts and fractions of particles whose first
    touch maps to a single broad process class (and the per-class
    breakdown), plus the process-conditioned Delta(w=120) and C1
    table with its frozen support verdict for every group."""
    dfp = [{
        "cell": r["cell"], "class": r["class"],
        "n_protons": _i(r["n_protons"]),
        "n_definite": _i(r["n_definite"]),
        "frac_definite": _f(r["frac_definite"]),
        "n_mixed_or_ambiguous": _i(r["n_mixed_or_ambiguous"]),
        "n_definite_by_class": {
            k[len("n_definite_"):]: _i(r[k]) for k in r
            if k.startswith("n_definite_") and k != "n_definite"
            and r[k] != ""}}
        for r in _csv(analysis_dir, "phaseB3B_definite_first_process.csv")]
    pcd = [{"cell": r["cell"], "group": r["group"],
            "n_events": _i(r["n_events"]), "n_pairs": _i(r["n_pairs"]),
            "support": r["support"],
            "Delta120": _f(r["Delta120"]),
            "Delta120_sd": _f(r["Delta120_sd"]),
            "Delta120_ci": [_f(r["Delta120_ci_lo"]),
                            _f(r["Delta120_ci_hi"])],
            "C1": _f(r["C1"]), "C1_sd": _f(r["C1_sd"]),
            "C1_ci": [_f(r["C1_ci_lo"]), _f(r["C1_ci_hi"])]}
           for r in _csv(analysis_dir,
                         "phaseB3B_process_conditioned_delta.csv")]
    data = {"definite_first_process": dfp,
            "process_conditioned_delta": pcd,
            "support_rule": _meta(analysis_dir)["support_rule"],
            "support_verdicts": sorted({r["support"] for r in pcd})}
    summary = (f"{len(dfp)} definite-first-process row(s), "
               f"{len(pcd)} process-conditioned row(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.definite_first_process", "inputs": {}})


def mechanism_evidence(analysis_dir: Optional[str] = None
                       ) -> ToolResult:
    """A bundled read-only summary of the frozen B3-B outputs: the
    recovery gate status, the pooled coverage fractions, the minbias
    w=120 DD/DA/AA additive Delta contributions with CIs, the
    DD-vs-AA contrasts per cell (C1 primary, Delta120 secondary) with
    support flags, the minbias first-touch alignment headline, the
    minbias definite-first-process fractions, and the
    process-conditioned support verdicts. Data only."""
    gates = _json(analysis_dir, "phaseB3B_history_recovery_gates.json")
    cov = [r for r in _csv(analysis_dir, "phaseB3B_lineage_coverage.csv")
           if r["sample"] == "protons" and r["slice"] == "pooled_b3"][0]
    pd120 = [r for r in _csv(analysis_dir,
                             "phaseB3B_proton_pair_decomposition.csv")
             if r["cell"] == "minbias" and r["width_deg"] == "120.0"
             and r["class"] in ("DD", "DA", "AA")]
    eff = _csv(analysis_dir, "phaseB3B_effect_sizes.csv")
    contrasts = {}
    for r in eff:
        if (r["rank"] == "primary" and r["quantity"] == "C1_DD_minus_C1_AA") \
                or (r["rank"] == "secondary"
                    and r["quantity"] == "Delta_DD_minus_Delta_AA"
                    and r["width_deg"] == "120.0"):
            contrasts.setdefault(r["cell"], {})[
                "C1_DD_minus_C1_AA" if r["rank"] == "primary"
                else "Delta120_DD_minus_Delta_AA"] = {
                "point": _f(r["point"]), "sd": _f(r["sd"]),
                "ci": [_f(r["ci_lo"]), _f(r["ci_hi"])],
                "support_DD": r["support_DD"],
                "support_AA": r["support_AA"]}
    al = [r for r in _csv(analysis_dir, "phaseB3B_first_touch_alignment.csv")
          if r["cell"] == "minbias" and r["quantity"]
          in ("R_Bplus", "R_M", "R_Bplus_minus_R_M")]
    dfp = [r for r in _csv(analysis_dir, "phaseB3B_definite_first_process.csv")
           if r["cell"] == "minbias"]
    pcd = _csv(analysis_dir, "phaseB3B_process_conditioned_delta.csv")
    data = {
        "recovery_all_gates_pass": gates["all_pass"],
        "coverage_pooled_protons": {
            "frac_D1": _f(cov["frac_D1"]), "frac_D2": _f(cov["frac_D2"]),
            "frac_D": _f(cov["frac_D"]), "frac_A": _f(cov["frac_A"]),
            "frac_P": _f(cov["frac_P"]), "frac_U": _f(cov["frac_U"])},
        "minbias_w120_contributions": [{
            "class": r["class"],
            "contribution": _f(r["contribution"]),
            "contribution_ci": [_f(r["contribution_ci_lo"]),
                                _f(r["contribution_ci_hi"])],
            "C1_contribution": _f(r["C1_contribution"]),
            "support": r["support"]} for r in pd120],
        "DD_vs_AA_contrasts_per_cell": contrasts,
        "first_touch_alignment_minbias": [{
            "quantity": r["quantity"], "R": _f(r["R"]),
            "R_ci": [_f(r["R_ci_lo"]), _f(r["R_ci_hi"])],
            "support": r["support"]} for r in al],
        "definite_first_process_minbias": [{
            "class": r["class"], "n_protons": _i(r["n_protons"]),
            "frac_definite": _f(r["frac_definite"])} for r in dfp],
        "process_conditioned_support_verdicts":
            sorted({r["support"] for r in pcd}),
        "semantics": {
            "D_grouping": _meta(analysis_dir)["D_grouping"],
            "class_A": "initial-or-pair ambiguous"},
        "discipline": _meta(analysis_dir)["step25_discipline"]}
    summary = ("B3-B bundle: recovery status, coverage, minbias "
               "contributions, DD-vs-AA contrasts, alignment, "
               "definite-first-process")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b3b.mechanism_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B3-B "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "frozen outputs)"}}
_CELL_PROP = {"cell": {"type": "string", "enum": list(CELLS)}}

register(ToolSpec(
    name="b3b.history_recovery_status",
    description=(
        "The frozen B3-B history-recovery status: Step-5 production "
        "gates A-N, the sentinel-chunk record, and the recovery "
        "manifest/index counts (shards, events, audit rule, frozen "
        "binary and engine hashes)."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=history_recovery_status))

register(ToolSpec(
    name="b3b.lineage_coverage",
    description=(
        "The frozen lineage coverage table per sample and slice: class "
        "counts and fractions for D1, D2, D = D1+D2, A "
        "(initial-or-pair ambiguous), P and U, with the frozen "
        "D-grouping definition."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=lineage_coverage))

register(ToolSpec(
    name="b3b.proton_pair_decomposition",
    description=(
        "The frozen accepted-proton pair decomposition per cell, "
        "kernel width and pair class (cell and width_deg optional): "
        "pair counts, support flags, F, class-level Delta_c and C1_c, "
        "and additive Delta(w)/C1 contributions with bootstrap SDs "
        "and 95% CIs."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP,
        "width_deg": {"type": "number", "enum": [60, 90, 120, 180]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=proton_pair_decomposition))

register(ToolSpec(
    name="b3b.baryon_pair_decomposition",
    description=(
        "The frozen all-B=+1 corroboration table (cell optional): C1 "
        "decomposition by the same pair classes with support flags "
        "and bootstrap CIs, plus species composition within the D and "
        "A endpoint classes."),
    input_schema={"type": "object", "properties": {
        **_CELL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=baryon_pair_decomposition))

register(ToolSpec(
    name="b3b.initial_nucleon_harmonics",
    description=(
        "The frozen initial interacting-nucleon pair harmonics per "
        "cell (unweighted and pT-weighted C1, unweighted C2, pair "
        "counts), the frozen attribution-diagnostic question text, "
        "and the frozen final proton total C1 per cell."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=initial_nucleon_harmonics))

register(ToolSpec(
    name="b3b.first_touch_summary",
    description=(
        "The frozen first-touch vertex counts per cell, broad process "
        "class and vertex class, and the frozen iline process map "
        "with source citations and mapped flags."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=first_touch_summary))

register(ToolSpec(
    name="b3b.first_touch_impulse",
    description=(
        "The frozen first-touch impulse table per cell, sector and "
        "broad process class: impulse component/magnitude means and "
        "the momentum-closure statistics of the impulse bookkeeping."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=first_touch_impulse))

register(ToolSpec(
    name="b3b.first_touch_process_alignment",
    description=(
        "The frozen first-touch alignment table per cell: R_Bplus, "
        "R_M, R_Bplus_minus_R_M and per-process-class R_Bplus slices "
        "with support flags, bootstrap CIs, mean cosines and the Qp "
        "floor."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=first_touch_process_alignment))

register(ToolSpec(
    name="b3b.definite_first_process",
    description=(
        "The frozen definite-first-process counts and fractions per "
        "cell and endpoint class with per-class breakdown, and the "
        "process-conditioned Delta(w=120)/C1 table with its frozen "
        "support verdicts."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=definite_first_process))

register(ToolSpec(
    name="b3b.mechanism_evidence",
    description=(
        "A bundled read-only summary of the frozen B3-B outputs: "
        "recovery gate status, pooled coverage fractions, minbias "
        "w=120 DD/DA/AA contributions, DD-vs-AA contrasts per cell, "
        "minbias first-touch alignment, definite-first-process "
        "fractions, and process-conditioned support verdicts. "
        "Data only."),
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
        for name in sorted(n for n in REGISTRY if n.startswith("b3b.")):
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
