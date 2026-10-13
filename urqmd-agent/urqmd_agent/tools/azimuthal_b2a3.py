"""Phase B2-A3 (final 5000-event veto-arm causal analysis) read-only tools.

These tools expose the persisted Phase B2-A3 STAGE 2 deliverables
(physics_gate/phaseB2A3/analysis/*.csv and *.json) and, where a
comparison requires it, the frozen Phase B1 baseline
(physics_gate/phaseB1/analysis/*.csv) and the frozen Phase B2-B
deliverables (physics_gate/phaseB2/analysis/*.csv), all read-only.
They never run UrQMD, never open raw file13/file15 output, and never
execute user-supplied code. Every number they report is copied from
the frozen analysis CSVs/JSON, so the tools and the CSV deliverables
agree by construction. The single exception is the refmult rank
correlation in ``b2a3.centrality_migration``, which is computed
deterministically at call time from two frozen per-event files (the
computation and its inputs are documented in that tool's output); it
is not itself a frozen deliverable number.

The intervention arm everywhere is the "CTOption(101)
both-previously-interacted collision veto" (ON) versus the frozen B1
baseline (base). The same 5000 ordinals/seeds appear in both arms and
Delta b_imp == 0 was enforced at join time.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b2a3`` registers the eight ``b2a3.*``
tools in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b2a3 list
    python3 -m urqmd_agent.tools.azimuthal_b2a3 call \\
        b2a3.fixed_b_compare '{"bin_index": 0}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis driver (support labels, survival flags, N-mixture
language labels, outcome letters, expected-note strings, and the
verbatim protocol section 12 text) are passed through verbatim as
data.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.errors import ToolError
from ..core.result import ToolResult
from .registry import ANALYSIS, ToolSpec, register

REPO_ROOT = Path(__file__).resolve().parents[2]
A3_DIR = REPO_ROOT / "physics_gate" / "phaseB2A3"
B1_DIR = REPO_ROOT / "physics_gate" / "phaseB1"
B2_DIR = REPO_ROOT / "physics_gate" / "phaseB2"
DEFAULT_A3_ANALYSIS_DIR = A3_DIR / "analysis"
DEFAULT_B1_ANALYSIS_DIR = B1_DIR / "analysis"
DEFAULT_B2_ANALYSIS_DIR = B2_DIR / "analysis"
PROTOCOL_PATH = A3_DIR / "final_analysis_protocol.md"

INTERVENTION = "CTOption(101) both-previously-interacted collision veto"

FIXED_B_CELLS = ("0.000-7.075", "7.075-10.006", "10.006-12.255",
                 "12.255-14.151", "14.151-15.821")
POOLED_CELL = "pooled_0.000-12.255"
COMMONN_CELLS = ("0.000-7.075", "7.075-10.006", "10.006-12.255",
                 POOLED_CELL)
DPHI_CELLS = ("minbias", POOLED_CELL) + FIXED_B_CELLS[:3]

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


def _a3csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_A3_ANALYSIS_DIR
    return _read_csv(d / fname,
                     "run the Phase B2-A3 STAGE 2 driver "
                     "(physics_gate/phaseB2A3/analysis/"
                     "analyze_phaseB2A3.py) first")


def _a3json(analysis_dir: Optional[str], fname: str) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_A3_ANALYSIS_DIR
    return _read_json(d / fname,
                      "run the Phase B2-A3 STAGE 2 driver first")


def _f(x: str):
    """Parse a CSV float cell; '' -> None."""
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


def _effect_row(r: Dict[str, str]) -> Dict[str, Any]:
    """One row of phaseB2A3_effect_sizes.csv / pooled_geometry.csv."""
    out = {
        "organization": r["organization"], "cell": r["cell"],
        "w_deg": _i(r["w_deg"]), "support": r["support"],
        "n_events_base": _i(r["n_events_base"]),
        "n_events_on": _i(r["n_events_on"]),
        "n_np2_base": _i(r["n_np2_base"]),
        "n_np2_on": _i(r["n_np2_on"]),
        "n_pairs_base": _i(r["n_pairs_base"]),
        "n_pairs_on": _i(r["n_pairs_on"]),
        "mean_np_base": _f(r["mean_np_base"]),
        "mean_np_on": _f(r["mean_np_on"]),
        "refmult_mean_base": _f(r["refmult_mean_base"]),
        "refmult_mean_on": _f(r["refmult_mean_on"]),
        "delta_base": _f(r["delta_base"]),
        "delta_base_sd": _f(r["delta_base_sd"]),
        "delta_base_ci": _ci(r["delta_base_ci"]),
        "delta_on": _f(r["delta_on"]),
        "delta_on_sd": _f(r["delta_on_sd"]),
        "delta_on_ci": _ci(r["delta_on_ci"]),
        "shift": _f(r["shift"]),
        "shift_boot_sd": _f(r["shift_boot_sd"]),
        "shift_ci": _ci(r["shift_ci"]),
        "survival": _f(r["survival"]),
        "survival_flag": r.get("survival_flag") or None}
    if "paired_diag_mean" in r:
        out["paired_diagnostic"] = {
            "mean": _f(r["paired_diag_mean"]),
            "sd": _f(r["paired_diag_sd"]),
            "ci": _ci(r["paired_diag_ci"]),
            "note": r["paired_diag_note"]}
    return out


def _arm_row(r: Dict[str, str]) -> Dict[str, Any]:
    """One per-arm row (support/fixed_b_delta/percentile/fixedN schema)."""
    return {"organization": r["organization"], "cell": r["cell"],
            "arm": r["arm"], "w_deg": _i(r["w_deg"]),
            "n_events": _i(r["n_events"]),
            "n_np2": _i(r["n_np2"]),
            "n_pairs": _i(r["n_pairs"]),
            "mean_np": _f(r["mean_np"]),
            "refmult_mean": _f(r["refmult_mean"]),
            "refmult_sd": _f(r["refmult_sd"]),
            "delta": _f(r["delta"]), "support": r["support"]}


def _damage_rows(analysis_dir: Optional[str]) -> List[Dict[str, Any]]:
    return [{"section": r["section"], "metric": r["metric"],
             "base": _f(r["base"]), "on": _f(r["on"]),
             "ratio": _f(r["ratio"]), "note": r["note"]}
            for r in _a3csv(analysis_dir, "phaseB2A3_dynamical_damage.csv")]


def _geometry_rows(analysis_dir: Optional[str]) -> List[Dict[str, Any]]:
    return [{"quantity": r["quantity"], "arm": r["arm"],
             "delta_bin1": _f(r["delta_bin1"]),
             "delta_bin3": _f(r["delta_bin3"]),
             "C_geom": _f(r["C_geom"]),
             "boot_sd": _f(r["boot_sd"]), "ci": _ci(r["ci"])}
            for r in _a3csv(analysis_dir, "phaseB2A3_geometry_contrast.csv")]


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def final_summary(analysis_dir: Optional[str] = None) -> ToolResult:
    """Join status, production gate statuses, the w=120 support table,
    and the pooled + minbias headline rows (per-arm Delta with bootstrap
    SDs and 95% CIs, shift, survival) from the frozen STAGE 2 outputs,
    plus the frozen protocol sha256."""
    sj = _a3json(analysis_dir, "phaseB2A3_analysis_summary.json")
    gates = _a3json(analysis_dir, "phaseB2A3_production_gates.json")
    gate_status = {name: g["status"] for name, g in gates["gates"].items()}
    support = [_arm_row(r) for r in _a3csv(analysis_dir,
                                           "phaseB2A3_support.csv")
               if r["w_deg"] == "120"]
    eff = _a3csv(analysis_dir, "phaseB2A3_effect_sizes.csv")
    headline = {r["cell"]: _effect_row(r) for r in eff
                if r["cell"] in ("minbias", POOLED_CELL)}
    data = {"intervention": INTERVENTION,
            "join": sj["join"],
            "join_note": ("Delta b_imp == 0 enforced for every joined "
                          "ordinal; see the STAGE 2 driver"),
            "production_gates": gate_status,
            "bootstrap": sj["bootstrap"],
            "support_rule": sj["support_rule"],
            "fixed_b_edges_fm": sj["fixed_b_edges_fm"],
            "protocol_file": sj["protocol"],
            "protocol_sha256": sj["protocol_sha256"],
            "runtime_seconds_driver": sj["runtime_seconds"],
            "support_table_w120": support,
            "headline": headline}
    summary = (f"join {sj['join']['n_joined']}/{sj['join']['n_base']}; "
               f"gates {sorted(set(gate_status.values()))}; "
               f"pooled outcome row present: {POOLED_CELL in headline}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.final_summary", "inputs": {}})


def fixed_b_compare(bin_index: Optional[int] = None,
                    analysis_dir: Optional[str] = None) -> ToolResult:
    """Per frozen fixed-b bin: the w=120 effect row (native Delta per
    arm with CIs, shift, survival value and flag, support, mean Np and
    refmult per arm) plus the w=60/90/180 native per-arm Delta
    diagnostics. Bins are the five frozen edges intervals; bin_index
    0..4 selects one, omitting it returns all five."""
    if bin_index is not None:
        if not isinstance(bin_index, int) or not 0 <= bin_index <= 4:
            raise ToolError("bin_index must be an integer in 0..4",
                            provenance={"tool": "b2a3.fixed_b_compare"})
        cells = [FIXED_B_CELLS[bin_index]]
    else:
        cells = list(FIXED_B_CELLS)
    eff = {r["cell"]: r for r in _a3csv(analysis_dir,
                                        "phaseB2A3_effect_sizes.csv")
           if r["organization"] == "fixed_b"}
    diag_rows = [r for r in _a3csv(analysis_dir,
                                   "phaseB2A3_fixed_b_delta.csv")
                 if r["w_deg"] != "120"]
    bins = []
    for idx, cell in enumerate(FIXED_B_CELLS):
        if cell not in cells:
            continue
        bins.append({
            "bin_index": idx, "cell": cell,
            "w120": _effect_row(eff[cell]),
            "w_diagnostics_native_delta": [
                {"w_deg": _i(r["w_deg"]), "arm": r["arm"],
                 "delta": _f(r["delta"]), "n_pairs": _i(r["n_pairs"])}
                for r in diag_rows if r["cell"] == cell]})
    data = {"intervention": INTERVENTION,
            "fixed_b_edges_note": ("edges frozen from B1; see "
                                   "b2a3.final_summary fixed_b_edges_fm"),
            "bins": bins}
    summary = f"{len(bins)} fixed-b bin row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.fixed_b_compare",
                    "inputs": {"bin_index": bin_index}})


def pooled_geometry_compare(analysis_dir: Optional[str] = None
                            ) -> ToolResult:
    """The pooled b < b3 primary endpoint (per-arm Delta with CIs,
    shift, survival, support) plus the w=60/90/180 diagnostics, and the
    geometry contrast C_geom = Delta_bin3 - Delta_bin1 per arm with the
    shift of the contrast and its bootstrap CI."""
    rows = [r for r in _a3csv(analysis_dir, "phaseB2A3_pooled_geometry.csv")]
    primary = _effect_row(next(r for r in rows if r["w_deg"] == "120"))
    diagnostics = [{"w_deg": _i(r["w_deg"]),
                    "delta_base": _f(r["delta_base"]),
                    "delta_on": _f(r["delta_on"]),
                    "shift": _f(r["shift"])}
                   for r in rows if r["w_deg"] != "120"]
    data = {"intervention": INTERVENTION,
            "pooled_endpoint_w120": primary,
            "pooled_w_diagnostics": diagnostics,
            "geometry_contrast": _geometry_rows(analysis_dir),
            "geometry_contrast_definition": "C_geom = delta_bin3 - delta_bin1"}
    summary = (f"pooled w=120 row + {len(diagnostics)} w diagnostics + "
               f"3 contrast rows")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.pooled_geometry_compare", "inputs": {}})


def commonN_standardized(cell: Optional[str] = None,
                         analysis_dir: Optional[str] = None) -> ToolResult:
    """Native vs common-N standardized comparison per cell: the weight
    definition, the common support range (N tabulated with n_base >= 20
    and n_on >= 20), the per-N weights and per-N per-arm Delta values,
    the standardized Delta per arm, shift_std with its bootstrap CI,
    and the frozen language label and note verbatim as data."""
    if cell is not None and cell not in COMMONN_CELLS:
        raise ToolError(f"cell must be one of {COMMONN_CELLS}",
                        provenance={"tool": "b2a3.commonN_standardized"})
    cells = [cell] if cell else list(COMMONN_CELLS)
    decomp = {r["cell"]: r for r in _a3csv(
        analysis_dir, "phaseB2A3_N_mixture_decomposition.csv")}
    weight_rows = _a3csv(analysis_dir, "phaseB2A3_commonN_standardized.csv")
    out = []
    for c in cells:
        d = decomp[c]
        weights = [{"N": _i(r["N"]), "n_base": _i(r["n_base"]),
                    "n_on": _i(r["n_on"]), "W_N": _f(r["W_N"]),
                    "delta_base_N": _f(r["delta_base_N"]),
                    "delta_on_N": _f(r["delta_on_N"])}
                   for r in weight_rows if r["cell"] == c]
        out.append({
            "cell": c,
            "commonN_count": _i(d["commonN_count"]),
            "commonN_values": [int(t) for t in
                               d["commonN_values"].split()],
            "delta_native_base": _f(d["delta_native_base"]),
            "delta_native_on": _f(d["delta_native_on"]),
            "shift_native": _f(d["shift_native"]),
            "delta_std_base": _f(d["delta_std_base"]),
            "delta_std_on": _f(d["delta_std_on"]),
            "shift_std": _f(d["shift_std"]),
            "shift_std_boot_sd": _f(d["shift_std_boot_sd"]),
            "shift_std_ci": _ci(d["shift_std_ci"]),
            "mixture_effect_on": _f(d["mixture_effect_on"]),
            "within_N_shift": _f(d["within_N_shift"]),
            "language_label_frozen_verbatim": d["language"],
            "note_frozen_verbatim": d["note"],
            "weights": weights})
    data = {"intervention": INTERVENTION,
            "W_N_definition": ("W_N proportional to n_base(N)*N*(N-1) "
                               "over the common support, normalized to "
                               "sum 1; baseline-only weights, identical "
                               "in both arms (frozen protocol)"),
            "common_support_rule": "n_base(N) >= 20 AND n_on(N) >= 20",
            "cells": out}
    summary = f"{len(out)} cell row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.commonN_standardized",
                    "inputs": {"cell": cell}})


def fixedN_compare(n: Optional[int] = None,
                   analysis_dir: Optional[str] = None) -> ToolResult:
    """Fixed-N Delta table at w=120: for each tabulated N (the driver
    tabulated only N with at least 20 events in both arms) the per-arm
    event counts, pair counts, Delta and support label. n selects one
    value of N; omitting it returns all tabulated N."""
    rows = [r for r in _a3csv(analysis_dir, "phaseB2A3_fixedN_delta.csv")
            if r["w_deg"] == "120"]
    by_n: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        nv = int(r["cell"].split("=")[1])
        by_n.setdefault(nv, {})[r["arm"]] = _arm_row(r)
    if n is not None:
        if n not in by_n:
            raise ToolError(
                f"N={n} not tabulated (tabulated: {sorted(by_n)})",
                provenance={"tool": "b2a3.fixedN_compare"})
        keep = [n]
    else:
        keep = sorted(by_n)
    table = [{"N": nv, "base": by_n[nv].get("base"),
              "on": by_n[nv].get("on")} for nv in keep]
    data = {"intervention": INTERVENTION,
            "tabulation_rule": ("only N with >= 20 events in both arms "
                                "were tabulated by the driver"),
            "rows": table}
    summary = f"{len(table)} fixed-N row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.fixedN_compare", "inputs": {"n": n}})


def delta_phi_compare(cell: Optional[str] = None,
                      analysis_dir: Optional[str] = None) -> ToolResult:
    """Per-pair NORMALIZED Delta-phi densities and K_120 near/away
    per-pair contributions for minbias, the pooled endpoint and the
    three adequate fixed-b bins, both arms. All densities and K_120
    values are normalized per pair (divided by the cell's total pair
    count), never raw K sums, so the two arms with very different pair
    counts are directly comparable."""
    if cell is not None and cell not in DPHI_CELLS:
        raise ToolError(f"cell must be one of {DPHI_CELLS}",
                        provenance={"tool": "b2a3.delta_phi_compare"})
    cells = [cell] if cell else list(DPHI_CELLS)
    rows = _a3csv(analysis_dir, "phaseB2A3_delta_phi.csv")
    out = []
    for c in cells:
        sub = [r for r in rows if r["cell"] == c]
        dist = [{"arm": r["arm"], "region": r["region"],
                 "dphi_lo": _f(r["dphi_lo"]), "dphi_hi": _f(r["dphi_hi"]),
                 "pair_density_per_pair": _f(r["pair_density"]),
                 "k120_per_pair": _f(r["k120_per_pair"])}
                for r in sub
                if r["region"] in ("near", "away")]
        summaries = [{"arm": r["arm"], "region": r["region"],
                      "pair_density_per_pair": _f(r["pair_density"]),
                      "k120_per_pair": _f(r["k120_per_pair"])}
                     for r in sub if r["region"].endswith("_summary")]
        out.append({"cell": c,
                    "n_pairs_total": {r["arm"]: _f(r["n_pairs_total"])
                                      for r in sub
                                      if r["region"] == "near_summary"},
                    "distribution": dist, "near_away_summary": summaries})
    data = {"intervention": INTERVENTION,
            "normalization": ("all pair_density and k120 values are "
                              "per-pair normalized by the cell's total "
                              "pair count; never raw K sums"),
            "cells": out}
    summary = f"{len(out)} cell(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.delta_phi_compare",
                    "inputs": {"cell": cell}})


def _ranks(vals: List[float]) -> List[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def _pearson(x: List[float], y: List[float]) -> float:
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return cov / math.sqrt(vx * vy)


def _refmult_rank_correlation(analysis_dir: Optional[str]) -> Dict[str, Any]:
    """Spearman rank correlation between baseline and ON refmult over
    the joined ordinals, computed at call time from two frozen
    per-event files (average ranks for ties)."""
    base = {int(r["event_id"]): float(r["refmult"]) for r in _read_csv(
        DEFAULT_B1_ANALYSIS_DIR / "phaseB1_event_summary.csv",
        "the frozen Phase B1 analysis outputs are missing")}
    on = {int(r["ordinal"]): float(r["refmult"])
          for r in _a3csv(analysis_dir, "phaseB2A3_per_event.csv")
          if r["arm"] == "on"}
    common = sorted(set(base) & set(on))
    x = [base[o] for o in common]
    y = [on[o] for o in common]
    rho = _pearson(_ranks(x), _ranks(y))
    return {"spearman_rho": rho, "n_joined": len(common),
            "method": ("computed deterministically at call time from "
                       "the frozen per-event files "
                       "phaseB1_event_summary.csv (baseline refmult by "
                       "event_id) and phaseB2A3_per_event.csv (ON "
                       "refmult by ordinal), average ranks for ties; "
                       "not itself a frozen deliverable number")}


def centrality_migration(analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """Baseline-boundary migration matrix (baseline refmult-percentile
    class vs the class an event falls into when the ON refmult is
    placed on the baseline boundaries), the self-consistent percentile
    boundaries and per-class per-arm Delta table at w=120, the refmult
    rank correlation over joined ordinals, and the frozen refmult
    shift statistics from the damage table."""
    sj = _a3json(analysis_dir, "phaseB2A3_analysis_summary.json")
    matrix = [{"class_base_baseline_boundaries":
               r["class_base_baseline_boundaries"],
               "class_on_at_baseline_boundaries":
               r["class_on_at_baseline_boundaries"],
               "n_events": _i(r["n_events"])}
              for r in _a3csv(analysis_dir,
                              "phaseB2A3_baseline_boundary_migration.csv")]
    pct = [_arm_row(r) for r in _a3csv(analysis_dir,
                                       "phaseB2A3_percentile_delta.csv")
           if r["w_deg"] == "120"]
    refmult_shift = [d for d in _damage_rows(analysis_dir)
                     if d["section"] == "full_5000"
                     and "refmult" in d["metric"]]
    data = {"intervention": INTERVENTION,
            "percentile_base_boundaries_refmult":
                sj["percentile_base_boundaries_refmult"],
            "migration_matrix": matrix,
            "percentile_delta_w120": pct,
            "refmult_rank_correlation":
                _refmult_rank_correlation(analysis_dir),
            "refmult_shift_stats_damage_table": refmult_shift}
    summary = (f"{len(matrix)} migration row(s), {len(pct)} percentile "
               f"row(s)")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.centrality_migration", "inputs": {}})


def _protocol_section_12() -> str:
    if not PROTOCOL_PATH.is_file():
        raise ToolError(f"{PROTOCOL_PATH} not found; the frozen "
                        "final_analysis_protocol.md is missing")
    text = PROTOCOL_PATH.read_text()
    start = text.index("## 12.")
    end = text.index("## 13.")
    return text[start:end].strip()


def causal_evidence(analysis_dir: Optional[str] = None) -> ToolResult:
    """Structured bundle of frozen numbers filed under the necessity
    question (Question A) and the geometry question (Question B): the
    pooled endpoint rows for both arms with CIs, the shift and
    survival, the verbatim preregistered outcome definitions (protocol
    section 12, quoted as data), the frozen evaluation result, the
    dynamical-damage table, the geometry contrast, and pointers into
    the frozen Phase B2-B deliverables (pseudo-proton survival, mixed
    null validation, permutation invariance). Data only."""
    eff = _a3csv(analysis_dir, "phaseB2A3_effect_sizes.csv")
    pooled = _effect_row(next(r for r in eff if r["cell"] == POOLED_CELL))
    minbias = _effect_row(next(r for r in eff if r["cell"] == "minbias"))
    sj = _a3json(analysis_dir, "phaseB2A3_analysis_summary.json")

    pseudo = next(r for r in _read_csv(
        DEFAULT_B2_ANALYSIS_DIR / "phaseB2_pseudo_proton_counterfactual.csv",
        "the frozen Phase B2-B analysis outputs are missing")
        if r["set"] == "minbias" and r["w_deg"] == "120")
    mixed = next(r for r in _read_csv(
        DEFAULT_B2_ANALYSIS_DIR / "phaseB2_event_mixed_counterfactual.csv",
        "the frozen Phase B2-B analysis outputs are missing")
        if r["set"] == "minbias" and r["w_deg"] == "120")
    perm_rows = [r for r in _read_csv(
        DEFAULT_B2_ANALYSIS_DIR / "phaseB2_history_label_permutation.csv",
        "the frozen Phase B2-B analysis outputs are missing")
        if r["set"] == "minbias"]
    devs = [_f(r["total_delta_perm_max_abs_dev"]) for r in perm_rows
            if r["total_delta_perm_max_abs_dev"]]

    data = {
        "intervention": INTERVENTION,
        "pooled_endpoint_evidence": {"pooled": pooled, "minbias": minbias},
        "outcome_definitions_protocol_section_12_verbatim":
            _protocol_section_12(),
        "evaluation_result_frozen": {
            "outcomes": sj["outcomes"],
            "question_A": sj["question_A"],
            "question_B": sj["question_B"]},
        "dynamical_damage": _damage_rows(analysis_dir),
        "geometry_contrast": _geometry_rows(analysis_dir),
        "b2b_frozen_pointers": {
            "files": ["physics_gate/phaseB2/analysis/"
                      "phaseB2_pseudo_proton_counterfactual.csv",
                      "physics_gate/phaseB2/analysis/"
                      "phaseB2_event_mixed_counterfactual.csv",
                      "physics_gate/phaseB2/analysis/"
                      "phaseB2_history_label_permutation.csv"],
            "pseudo_minbias_w120": {
                "delta_real": _f(pseudo["delta_real"]),
                "delta_real_err": _f(pseudo["delta_real_err"]),
                "delta_pseudo": _f(pseudo["delta_pseudo"]),
                "delta_pseudo_err": _f(pseudo["delta_pseudo_err"]),
                "pseudo_survival": _f(pseudo["pseudo_survival"]),
                "survival_gate": pseudo["survival_gate"]},
            "mixed_minbias_w120": {
                "delta_mixed": _f(mixed["delta_mixed"]),
                "delta_mixed_err": _f(mixed["delta_mixed_err"]),
                "null_z": _f(mixed["null_z"]),
                "expected_note_frozen_verbatim": mixed["expected_note"]},
            "permutation_minbias": {
                "n_rows": len(perm_rows),
                "total_delta_perm_max_abs_dev_max": max(devs),
                "total_delta_invariant": bool(devs) and max(devs) == 0.0}}}
    summary = ("necessity/geometry bundle: pooled + minbias rows, "
               "protocol section 12 verbatim, damage table, contrast, "
               "B2-B pointers")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b2a3.causal_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B2-A3 "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "STAGE 2 outputs)"}}

register(ToolSpec(
    name="b2a3.final_summary",
    description=(
        "Join status (5000/5000, Delta b_imp == 0), production gate "
        "A-M statuses, the w=120 support table, and the pooled + "
        "minbias headline rows (per-arm Delta with bootstrap SDs and "
        "95% CIs, shift, survival) plus the frozen protocol sha256."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=final_summary))

register(ToolSpec(
    name="b2a3.fixed_b_compare",
    description=(
        "Per frozen fixed-b bin (bin_index 0-4, or all): the w=120 "
        "effect row (native Delta per arm with CIs, shift, survival "
        "value/flag, support, mean Np and refmult per arm) plus the "
        "w=60/90/180 native per-arm Delta diagnostics."),
    input_schema={"type": "object", "properties": {
        "bin_index": {"type": "integer", "minimum": 0, "maximum": 4},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=fixed_b_compare))

register(ToolSpec(
    name="b2a3.pooled_geometry_compare",
    description=(
        "The pooled b < b3 primary endpoint at w=120 (per-arm Delta "
        "with CIs, shift, survival, support) with w=60/90/180 "
        "diagnostics, plus the geometry contrast C_geom = Delta_bin3 "
        "- Delta_bin1 per arm and the shift of the contrast with its "
        "bootstrap CI."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=pooled_geometry_compare))

register(ToolSpec(
    name="b2a3.commonN_standardized",
    description=(
        "Native vs common-N standardized comparison per cell: the W_N "
        "weight definition, the common support range, the per-N "
        "weights and per-arm per-N Delta values, the standardized "
        "Delta per arm, shift_std with its bootstrap CI, and the "
        "frozen language label and no-unique-mediation note verbatim "
        "as data."),
    input_schema={"type": "object", "properties": {
        "cell": {"type": "string", "enum": list(COMMONN_CELLS)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=commonN_standardized))

register(ToolSpec(
    name="b2a3.fixedN_compare",
    description=(
        "Fixed-N Delta table at w=120 (only N tabulated by the driver, "
        "i.e. N with at least 20 events in both arms): per-arm event "
        "counts, pair counts, Delta and support label per N."),
    input_schema={"type": "object", "properties": {
        "n": {"type": "integer"}, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=fixedN_compare))

register(ToolSpec(
    name="b2a3.delta_phi_compare",
    description=(
        "Per-pair NORMALIZED Delta-phi densities (18 bins, near/away) "
        "and K_120 near/away per-pair contributions for minbias, the "
        "pooled endpoint and the three adequate fixed-b bins, both "
        "arms. All values are per-pair normalized by the cell's total "
        "pair count, never raw K sums."),
    input_schema={"type": "object", "properties": {
        "cell": {"type": "string", "enum": list(DPHI_CELLS)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=delta_phi_compare))

register(ToolSpec(
    name="b2a3.centrality_migration",
    description=(
        "Baseline-boundary migration matrix, the self-consistent "
        "percentile boundaries and per-class per-arm Delta table at "
        "w=120, the refmult rank correlation over the 5000 joined "
        "ordinals (computed at call time from frozen per-event "
        "files), and the frozen refmult shift statistics from the "
        "damage table."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=centrality_migration))

register(ToolSpec(
    name="b2a3.causal_evidence",
    description=(
        "Structured bundle of frozen numbers for the necessity "
        "question: the pooled endpoint and minbias rows for both arms "
        "with CIs, shift and survival, the verbatim preregistered "
        "outcome definitions (protocol section 12, quoted as data) "
        "and their frozen evaluation result, the dynamical-damage "
        "table, the geometry contrast, and pointers into the frozen "
        "Phase B2-B deliverables (pseudo-proton survival, mixed null "
        "validation, permutation invariance). Data only."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=causal_evidence))


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
        for name in sorted(n for n in REGISTRY if n.startswith("b2a3.")):
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
