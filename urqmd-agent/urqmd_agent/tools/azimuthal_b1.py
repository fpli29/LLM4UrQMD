"""Phase B1 (azimuthal pair-kernel attribution) read-only analysis tools.

These tools expose the persisted Phase B1 deliverables
(physics_gate/phaseB1/analysis/*.csv and phaseB1_analysis_summary.json)
to the agent. They are strictly read-only: they never run UrQMD, never
open raw file13/file15 output, and never execute user-supplied code.
Every number they report is copied from the frozen analysis CSVs, so the
tools and the CSV deliverables agree by construction.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B1 change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b1`` registers the eight ``b1.*`` tools in
the shared registry, after which ``agent.tool_runner.call_tool`` can
dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b1 list
    python3 -m urqmd_agent.tools.azimuthal_b1 call b1.kernel_curve \\
        '{"set_label": "minbias", "w_deg": 120}'

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
DEFAULT_ANALYSIS_DIR = B1_DIR / "analysis"

SET_LABELS = ("minbias", "0-5", "5-10", "10-20", "20-30", "30-40",
              "40-50", "50-60", "60-70", "70-80")
AXES = ("A", "B", "C", "D")
AXIS_FILES = {
    "A": "phaseB1_pair_history_decomposition.csv",   # holds axes A and D
    "D": "phaseB1_pair_history_decomposition.csv",
    "B": "phaseB1_rescattering_decomposition.csv",
    "C": "phaseB1_formation_decomposition.csv",
}
W_DEGS = (60, 90, 120, 180)
MAX_ROWS = 500

_cache: Dict[str, Any] = {}


def _adir(analysis_dir: Optional[str]) -> Path:
    return Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR


def _read_csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    path = _adir(analysis_dir) / fname
    if not path.is_file():
        raise ToolError(
            f"{path} not found; run the Phase B1 analysis driver "
            f"(physics_gate/phaseB1/analysis/analyze_phaseB1.py) first")
    key = f"csv:{path}:{path.stat().st_mtime_ns}"
    if key not in _cache:
        _cache.clear()
        with path.open(newline="") as fh:
            _cache[key] = list(csv.DictReader(fh))
    return _cache[key]


def _read_summary(analysis_dir: Optional[str]) -> Dict[str, Any]:
    path = _adir(analysis_dir) / "phaseB1_analysis_summary.json"
    if not path.is_file():
        raise ToolError(
            f"{path} not found; run the Phase B1 analysis driver "
            f"(physics_gate/phaseB1/analysis/analyze_phaseB1.py) first")
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


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def event_lookup(event_id: int, analysis_dir: Optional[str] = None
                 ) -> ToolResult:
    """Per-event record of one B1 event (kinematics, centrality,
    per-event kernel values, proton-history counts)."""
    ev_rows = _read_csv(analysis_dir, "phaseB1_event_summary.csv")
    ph_rows = _read_csv(analysis_dir, "phaseB1_proton_history.csv")
    ev = next((r for r in ev_rows if int(r["event_id"]) == event_id), None)
    if ev is None:
        return ToolResult.error(
            f"event_id {event_id} not in phaseB1_event_summary.csv",
            provenance={"tool": "b1.event_lookup"})
    hist = next((r for r in ph_rows if int(r["event_id"]) == event_id), None)
    data = {"event": {k: _f(v) if k in ("bimp",) else v for k, v in
                      ev.items()},
            "proton_history": hist}
    summary = (f"B1 event {event_id}: refmult={ev['refmult']}, "
               f"n_coll={ev['n_coll']}, centrality={ev['centrality']}, "
               f"N_proton={ev['n_proton_accepted']}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "b1.event_lookup",
                                     "inputs": {"event_id": event_id}})


def centrality_classes(analysis_dir: Optional[str] = None) -> ToolResult:
    """Frozen centrality-class definition and per-class event counts."""
    s = _read_summary(analysis_dir)
    classes = [{"class": k, "n_events": v}
               for k, v in s["class_sizes"].items()]
    valid = s.get("class_valid_events", {})
    for c in classes:
        c["n_events_N_ge_2"] = valid.get(c["class"])
    data = {"definition": ("refmult percentile classes over interacting "
                           "(n_coll > 0) events; deterministic tie breaking "
                           "(robustness_seed=20260919); minbias = all "
                           "interacting events"),
            "n_events_total": s["n_events_total"],
            "n_events_interacting": s["n_events_interacting"],
            "classes": classes}
    summary = (f"{s['n_events_interacting']} interacting events in "
               f"{len(classes)} classes")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "b1.centrality_classes"})


def kernel_curve(set_label: str = "minbias", w_deg: int = 120,
                 pooling: str = "fixed_n",
                 analysis_dir: Optional[str] = None) -> ToolResult:
    """Exact pair-kernel Delta values: fixed-N curve or pairs/equal-N
    aggregates for one set and window width, with bootstrap SDs."""
    if set_label not in SET_LABELS:
        return ToolResult.error(f"unknown set {set_label!r}; one of "
                                f"{SET_LABELS}",
                                provenance={"tool": "b1.kernel_curve"})
    if w_deg not in W_DEGS:
        return ToolResult.error(f"w_deg must be one of {W_DEGS}",
                                provenance={"tool": "b1.kernel_curve"})
    rows = _read_csv(analysis_dir, "phaseB1_pair_kernel_summary.csv")
    rows = [r for r in rows if r["set"] == set_label
            and int(r["w_deg"]) == w_deg]
    if pooling == "fixed_n":
        rows = [r for r in rows if r["section"] == "FIXED_N"]
        table = [{"N": _i(r["n_proton_class"]),
                  "n_events": _i(r["n_events_class"]),
                  "delta": _f(r["delta"]), "delta_err": _f(r["delta_err"]),
                  "support": r["support"]} for r in rows]
    elif pooling in ("pairs", "equal_n"):
        sec = "AGGREGATE_PAIRS" if pooling == "pairs" else "AGGREGATE_EQUAL_N"
        rows = [r for r in rows if r["section"] == sec]
        table = [{"set": r["set"], "n_events_used": _i(r["n_events_class"]),
                  "delta": _f(r["delta"]), "delta_err": _f(r["delta_err"]),
                  "support": r["support"]} for r in rows]
    else:
        return ToolResult.error(
            "pooling must be 'fixed_n', 'pairs' or 'equal_n'",
            provenance={"tool": "b1.kernel_curve"})
    table, note = _rows(table, MAX_ROWS)
    data = {"set": set_label, "w_deg": w_deg, "pooling": pooling,
            "rows": table}
    warnings = [note] if note else []
    summary = (f"{set_label} w={w_deg} pooling={pooling}: "
               f"{len(table)} row(s)")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "b1.kernel_curve",
                                     "inputs": {"set_label": set_label,
                                                "w_deg": w_deg,
                                                "pooling": pooling}})


def pair_decomposition(axis: str, set_label: str = "minbias",
                       w_deg: int = 120,
                       analysis_dir: Optional[str] = None) -> ToolResult:
    """Additive pair-category decomposition (F_c, Delta_c, contribution)
    for one axis/set/width. Axes: A direct-interaction history, B
    post-formation rescattering, C formation channel, D post-scatter
    counts."""
    axis = axis.upper()
    if axis not in AXES:
        return ToolResult.error(f"axis must be one of {AXES}",
                                provenance={"tool": "b1.pair_decomposition"})
    rows = _read_csv(analysis_dir, AXIS_FILES[axis])
    rows = [r for r in rows if r["axis"] == axis
            and r["set"] == set_label and r["w_deg"] == str(w_deg)]
    if not rows:
        return ToolResult.error(
            f"no rows for axis={axis} set={set_label} w={w_deg}",
            provenance={"tool": "b1.pair_decomposition"})
    table = [{"category": r["category"], "n_pairs": _i(r["n_pairs"]),
              "F_c": _f(r["F_c"]), "F_c_err": _f(r["F_c_err"]),
              "delta_c": _f(r["delta_c"]),
              "delta_c_err": _f(r["delta_c_err"]),
              "contribution": _f(r["contribution"]),
              "contribution_err": _f(r["contribution_err"]),
              "closure_residual": _f(r["closure_residual"]),
              "support": r["support"]} for r in rows]
    table, note = _rows(table, MAX_ROWS)
    warnings = [note] if note else []
    merge_log = rows[0].get("merge_log") or None
    data = {"axis": axis, "set": set_label, "w_deg": w_deg, "rows": table}
    if merge_log:
        data["merge_log"] = merge_log
    summary = (f"axis {axis} {set_label} w={w_deg}: "
               f"{len(table)} categor(ies)")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "b1.pair_decomposition",
                                     "inputs": {"axis": axis,
                                                "set_label": set_label,
                                                "w_deg": w_deg}})


def delta_phi(set_label: str = "minbias",
              analysis_dir: Optional[str] = None) -> ToolResult:
    """18-bin Delta-phi table for one set: same-event and mixed-event
    normalized distributions, their ratio, and the kernel-weighted bin
    contributions at w=120."""
    rows = _read_csv(analysis_dir, "phaseB1_delta_phi_decomposition.csv")
    rows = [r for r in rows if r["set"] == set_label]
    if not rows:
        return ToolResult.error(f"no rows for set {set_label!r}",
                                provenance={"tool": "b1.delta_phi"})
    table = [{"bin_lo_deg": _f(r["bin_lo_deg"]),
              "bin_hi_deg": _f(r["bin_hi_deg"]),
              "same_pairs": _i(r["same_pairs"]),
              "same_frac": _f(r["same_frac"]),
              "mixed_pairs": _i(r["mixed_pairs"]),
              "mixed_frac": _f(r["mixed_frac"]),
              "ratio": _f(r["ratio"]), "ratio_err": _f(r["ratio_err"]),
              "ksum_w120_over_DEN": _f(r["ksum_w120_over_DEN"]),
              "ksum_w120_err": _f(r["ksum_w120_err"]),
              "share_of_total_w120": _f(r["share_of_total_w120"]),
              "support": r["support"]} for r in rows]
    summary = f"Delta-phi table for {set_label}: {len(table)} bins"
    return ToolResult.ok(summary, {"set": set_label, "bins": table},
                         provenance={"tool": "b1.delta_phi",
                                     "inputs": {"set_label": set_label}})


def momentum_balance(set_label: str = "minbias",
                     analysis_dir: Optional[str] = None) -> ToolResult:
    """Momentum-balance observables (eps for all/midrapidity/proton
    scopes, recoil_cos): per-set means and Pearson/Spearman correlations
    with the per-event Delta(120) and with refmult."""
    rows = _read_csv(analysis_dir, "phaseB1_momentum_balance.csv")
    rows = [r for r in rows if r["set"] == set_label]
    if not rows:
        return ToolResult.error(f"no rows for set {set_label!r}",
                                provenance={"tool": "b1.momentum_balance"})
    means = [{"quantity": r["quantity"], "n_events_used":
              _i(r["n_events_used"]), "mean": _f(r["value"]),
              "err": _f(r["err"])} for r in rows if r["section"] == "MEAN"]
    corrs = [{"x_var": r["x_var"], "y_var": r["y_var"],
              "method": r["method"], "n_events_used":
              _i(r["n_events_used"]), "value": _f(r["value"]),
              "err": _f(r["err"])}
             for r in rows if r["section"] == "CORRELATION"]
    summary = (f"momentum balance for {set_label}: {len(means)} means, "
               f"{len(corrs)} correlations")
    return ToolResult.ok(summary, {"set": set_label, "means": means,
                                   "correlations": corrs},
                         provenance={"tool": "b1.momentum_balance",
                                     "inputs": {"set_label": set_label}})


def mixture_vs_strength(axis: str, class_label: str,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """Kitagawa two-factor split (mixture vs within-category strength) of
    the difference Delta(class) - Delta(minbias) at w=120, per category
    and in total; reference = minbias."""
    axis = axis.upper()
    rows = _read_csv(analysis_dir, "phaseB1_mixture_vs_strength.csv")
    rows = [r for r in rows if r["axis"] == axis
            and r["class"] == class_label]
    if not rows:
        return ToolResult.error(
            f"no rows for axis={axis} class={class_label!r}",
            provenance={"tool": "b1.mixture_vs_strength"})
    table = [{"category": r["category"], "F_ref": _f(r["F_ref"]),
              "F_k": _f(r["F_k"]), "D_ref": _f(r["D_ref"]),
              "D_k": _f(r["D_k"]), "mixture_c": _f(r["mixture_c"]),
              "within_c": _f(r["within_c"]),
              "total_diff_c": _f(r["total_diff_c"]),
              "closure": _f(r["closure"])} for r in rows]
    total = next((r for r in table if r["category"] == "__TOTAL__"), None)
    summary = (f"mixture-vs-strength axis {axis} class {class_label}: "
               + (f"mixture={total['mixture_c']:.6g}, "
                  f"within={total['within_c']:.6g}" if total else
                  f"{len(table)} rows"))
    return ToolResult.ok(summary, {"axis": axis, "class": class_label,
                                   "rows": table},
                         provenance={"tool": "b1.mixture_vs_strength",
                                     "inputs": {"axis": axis,
                                                "class_label": class_label}})


def mechanism_evidence_summary(analysis_dir: Optional[str] = None
                               ) -> ToolResult:
    """Headline numbers of the B1 attribution in one call: per-set
    Delta_pairs(120) with bootstrap SDs, axis-A category table at w=120,
    the axis-C merge log, and the Step-13 baseline-gate check table.
    Values are read from the same CSVs/JSON the other b1.* tools
    expose."""
    s = _read_summary(analysis_dir)
    deltas = {k: v for k, v in s["delta_pairs_w120"].items()}
    axis_a = s.get("axis_A_w120", {})
    a_table = {set_label: {"total": blk["total"],
                           "categories": blk["categories"]}
               for set_label, blk in axis_a.items()}
    gate = {k: v.get("passed") for k, v in s["baseline_gate"].items()}
    gate_rows = _read_csv(analysis_dir,
                          "phaseB1_baseline_reproduction.csv")
    gate_table = [{"check": r["check"], "quantity": r["quantity"],
                   "value": _f(r["value"]), "err": _f(r["err"]),
                   "passed": r["passed"]} for r in gate_rows]
    data = {"delta_pairs_w120": deltas,
            "axis_A_w120": a_table,
            "axis_c_merge_log": s.get("axis_c_merge_log", []),
            "baseline_gate_passed": gate,
            "baseline_gate_table": gate_table,
            "n_events_interacting": s["n_events_interacting"]}
    mb = deltas.get("minbias", {})
    summary = (f"B1 evidence summary over {s['n_events_interacting']} "
               f"interacting events; minbias Delta_pairs(120) = "
               f"{mb.get('value'):.6g} +/- {mb.get('err'):.2g}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "b1.mechanism_evidence_summary"})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_SET_PROP = {"set_label": {"type": "string", "enum": list(SET_LABELS),
                           "default": "minbias"}}
_W_PROP = {"w_deg": {"type": "integer", "enum": list(W_DEGS),
                     "default": 120}}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override analysis directory "
                                             "(default: the persisted B1 "
                                             "analysis outputs)"}}

register(ToolSpec(
    name="b1.event_lookup",
    description=(
        "Per-event record of one Phase B1 event: kinematics (bimp, "
        "n_coll, refmult), centrality class, accepted-proton count, "
        "momentum-balance observables, per-event kernel values at "
        "w=60/90/120/180, and per-event proton-history counts. Read from "
        "the persisted B1 CSVs; never touches raw UrQMD output."),
    input_schema={"type": "object", "properties": {
        "event_id": {"type": "integer"}, **_DIR_PROP},
        "required": ["event_id"]},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=event_lookup))

register(ToolSpec(
    name="b1.centrality_classes",
    description=(
        "Frozen Phase B1 centrality-class definition (refmult percentiles "
        "over interacting events, deterministic tie breaking) with "
        "per-class event counts."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=centrality_classes))

register(ToolSpec(
    name="b1.kernel_curve",
    description=(
        "Exact pair-kernel Delta_sigma^2 for one set and window width: "
        "the fixed-N curve (pooling='fixed_n') or the pairs-weighted / "
        "equal-N aggregates (pooling='pairs'/'equal_n'), with event-block "
        "bootstrap SDs and support flags."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_W_PROP,
        "pooling": {"type": "string",
                    "enum": ["fixed_n", "pairs", "equal_n"],
                    "default": "fixed_n"}, **_DIR_PROP},
        "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=kernel_curve))

register(ToolSpec(
    name="b1.pair_decomposition",
    description=(
        "Additive pair-category decomposition of Delta_sigma^2 for one "
        "axis (A direct-interaction history / B post-formation "
        "rescattering / C formation channel / D post-scatter counts), "
        "set and width: pair fraction F_c, per-category strength "
        "Delta_c, and additive contribution, with bootstrap SDs and the "
        "exact closure residual."),
    input_schema={"type": "object", "properties": {
        "axis": {"type": "string", "enum": list(AXES)},
        **_SET_PROP, **_W_PROP, **_DIR_PROP},
        "required": ["axis"]},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=pair_decomposition))

register(ToolSpec(
    name="b1.delta_phi",
    description=(
        "18-bin Delta-phi table for one set: normalized same-event and "
        "mixed-event pair distributions, their ratio (with bootstrap "
        "SD), and the kernel-weighted bin contributions at w=120 "
        "(which bins carry the total)."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=delta_phi))

register(ToolSpec(
    name="b1.momentum_balance",
    description=(
        "Momentum-balance observables for one set: means of eps "
        "(all/midrapidity/proton scopes) and recoil_cos, plus their "
        "Pearson/Spearman correlations with the per-event Delta(120) "
        "and with refmult, with bootstrap SDs."),
    input_schema={"type": "object", "properties": {
        **_SET_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=momentum_balance))

register(ToolSpec(
    name="b1.mixture_vs_strength",
    description=(
        "Kitagawa two-factor split of Delta(class) - Delta(minbias) at "
        "w=120 for one axis and centrality class: the mixture component "
        "(category fraction change) and the within component "
        "(per-category strength change), per category and in total. "
        "Reference = minbias; the split is an exact identity."),
    input_schema={"type": "object", "properties": {
        "axis": {"type": "string", "enum": list(AXES)},
        "class_label": {"type": "string"}, **_DIR_PROP},
        "required": ["axis", "class_label"]},
    output_schema=_OBJ, risk_level=ANALYSIS, handler=mixture_vs_strength))

register(ToolSpec(
    name="b1.mechanism_evidence_summary",
    description=(
        "One-call headline table of the Phase B1 attribution: per-set "
        "Delta_pairs(120) with bootstrap SDs, the axis-A category table "
        "at w=120, the axis-C merge log, and the Step-13 "
        "baseline-reproduction gate table. Values are identical to the "
        "CSV deliverables."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=mechanism_evidence_summary))


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
        for name in sorted(n for n in REGISTRY if n.startswith("b1.")):
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
