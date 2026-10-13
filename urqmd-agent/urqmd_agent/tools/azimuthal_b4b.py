"""Phase B4-B (BES energies 11.5/19.6/27/39 GeV, azimuth-blind
within-event label-permutation nulls for the D-A cross-dipole)
read-only tools.

These tools expose the persisted Phase B4-B deliverables
(physics_gate/phaseB4B/analysis/*.csv and *.json plus the frozen
history/provenance records under physics_gate/phaseB4B/data/). They
never run UrQMD, never open raw shards, never permute anything, and
never execute user-supplied code. Every number they report is copied
from the frozen analysis CSVs/JSON at call time, so the tools and the
CSV deliverables agree by construction.

Null-semantics discipline (frozen): N0/N1 are azimuth-blind
within-event label permutations on frozen B4-B events. The physical
event — momenta, multiplicities, population sizes and the set totals —
is preserved exactly; only the microscopic D/A labels are permuted.
N1 additionally preserves pT-y composition; stratification restricts
label mobility, which is reported via the frozen mobility table and
never relaxed. All quantities are attribution-level tabulations, not
mechanism statements.

Registry note: ``urqmd_agent/tools/__init__.py`` and ``urqmd_agent/cli``
are frozen (Phase B change policy), so this module is NOT auto-imported
by ``import urqmd_agent.tools``. Importing
``urqmd_agent.tools.azimuthal_b4b`` registers the ten ``b4b.*`` tools
in the shared registry, after which ``agent.tool_runner.call_tool``
can dispatch them. A minimal CLI is provided by this module itself:

    python3 -m urqmd_agent.tools.azimuthal_b4b list
    python3 -m urqmd_agent.tools.azimuthal_b4b call \\
        b4b.real_null_contrast '{"energy": "11.5", "cell": "minbias"}'

Tool names, descriptions and JSON field text describe what is
tabulated and how it was computed. Frozen label strings produced by
the analysis drivers (support flags, retention labels, rule text,
history gate text) are passed through verbatim as data.
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
B4B_DIR = REPO_ROOT / "physics_gate" / "phaseB4B"
B4A_DIR = REPO_ROOT / "physics_gate" / "phaseB4A"
DEFAULT_ANALYSIS_DIR = B4B_DIR / "analysis"
DATA_DIR = B4B_DIR / "data"
HYP_MD = B4A_DIR / "hypotheses.md"

ENERGIES = ("11.5", "19.6", "27", "39")
ENERGIES_WITH_B4A = ("7.7",) + ENERGIES
HIST_LABEL = {"11.5": "11p5", "19.6": "19p6", "27": "27", "39": "39"}
CELLS = ("minbias", "pooled_b3", "bin0", "bin1", "bin2")
NULLS = ("N0", "N1")
ARMS = ("REAL", "N0", "N1")
CLS3 = ("DD", "DA", "AA")
WIDTHS = ("60.0", "90.0", "120.0", "180.0")
QUANTITIES = ("delta_C1_label", "delta_Delta120_label", "retention_C1_DA")
SAMPLES = ("proton", "baryon")

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


_HINT = ("the frozen Phase B4-B deliverables are missing; the null "
         "driver outputs under physics_gate/phaseB4B/analysis/ must "
         "exist first")
_DATA_HINT = ("the frozen Phase B4-B history/provenance records under "
              "physics_gate/phaseB4B/data/ must exist first")


def _csv(analysis_dir: Optional[str], fname: str) -> List[Dict[str, str]]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_csv(d / fname, _HINT)


def _json(analysis_dir: Optional[str], fname: str) -> Dict[str, Any]:
    d = Path(analysis_dir) if analysis_dir else DEFAULT_ANALYSIS_DIR
    return _read_json(d / fname, _HINT)


def _data_json(fname: str) -> Dict[str, Any]:
    return _read_json(DATA_DIR / fname, _DATA_HINT)


def _f(x: str):
    if x is None or x == "":
        return None
    return float(x)


def _i(x: str):
    if x is None or x == "":
        return None
    return int(x)


def _check_energy(energy: Optional[str], tool: str,
                  allowed=ENERGIES) -> None:
    if energy is not None and energy not in allowed:
        raise ToolError(f"energy must be one of {allowed}",
                        provenance={"tool": tool})


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


def _check_width(width_deg: Optional[float], tool: str) -> None:
    if width_deg is not None and f"{float(width_deg)}" not in WIDTHS:
        raise ToolError(f"width_deg must be one of {WIDTHS}",
                        provenance={"tool": tool})


def _meta(analysis_dir: Optional[str]) -> Dict[str, Any]:
    return _json(analysis_dir, "phaseB4B_null_metadata.json")


def _pair_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "cell": r["cell"],
        "width_deg": _f(r["width_deg"]),
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
    point = _f(r["point"])
    lo, hi = _f(r["ci_lo"]), _f(r["ci_hi"])
    return {
        "energy": r["energy"], "cell": r["cell"], "null": r["null"],
        "quantity": r["quantity"],
        "point": point, "sd": _f(r["sd"]),
        "ci": [lo, hi],
        "ci_excludes_zero": (None if lo is None or hi is None
                             else not (lo < 0 < hi)),
        "real_point": _f(r["real_point"]), "real_sd": _f(r["real_sd"]),
        "null_point": _f(r["null_point"]), "null_sd": _f(r["null_sd"]),
        "label": r["label"] if r["label"] else None}


def _mobility_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "sample": r["sample"], "cell": r["cell"],
        "null": r["null"],
        "n_events": _i(r["n_events"]),
        "n_particles": _i(r["n_particles"]),
        "frac_particles_exchangeable": _f(r["frac_particles_exchangeable"]),
        "frac_particles_frozen": _f(r["frac_particles_frozen"]),
        "mean_effective_swaps_per_event":
            _f(r["mean_effective_swaps_per_event"]),
        "frac_events_fully_frozen": _f(r["frac_events_fully_frozen"]),
        "mean_strata_per_event": _f(r["mean_strata_per_event"])}


def _pop_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "cell": r["cell"], "arm": r["arm"],
        "n_events_on_support": _i(r["n_events_on_support"]),
        "mean": _f(r["mean"]), "mean_sd": _f(r["mean_sd"]),
        "mean_ci": [_f(r["mean_ci_lo"]), _f(r["mean_ci_hi"])],
        "median": _f(r["median"]),
        "p10": _f(r["p10"]), "p25": _f(r["p25"]),
        "p75": _f(r["p75"]), "p90": _f(r["p90"]),
        "frac_negative": _f(r["frac_negative"])}


def _baryon_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "section": r["section"], "cell": r["cell"],
        "arm_or_null": r["arm_or_null"], "quantity": r["quantity"],
        "class": r["class"] if r["class"] else None,
        "point": _f(r["point"]), "sd": _f(r["sd"]),
        "ci": [_f(r["ci_lo"]), _f(r["ci_hi"])],
        "support_or_note": r["support_or_note"]}


def _energy_row(r: Dict[str, str]) -> Dict[str, Any]:
    lo, hi = _f(r["delta_C1_N1_ci_lo"]), _f(r["delta_C1_N1_ci_hi"])
    return {
        "energy": r["energy"], "sqrt_s": _f(r["sqrt_s"]),
        "N_events": _i(r["N_events"]),
        "N_accepted_protons": _i(r["N_accepted_protons"]),
        "f_D": _f(r["f_D"]), "f_A": _f(r["f_A"]),
        "F_DD": _f(r["F_DD"]), "F_DA": _f(r["F_DA"]),
        "F_AA": _f(r["F_AA"]),
        "C1_total": _f(r["C1_total"]),
        "C1_DD": _f(r["C1_DD"]), "C1_DA": _f(r["C1_DA"]),
        "C1_AA": _f(r["C1_AA"]),
        "C1_DA_contribution": _f(r["C1_DA_contribution"]),
        "Delta120_total": _f(r["Delta120_total"]),
        "Delta120_contribution_DD": _f(r["Delta120_contribution_DD"]),
        "Delta120_contribution_DA": _f(r["Delta120_contribution_DA"]),
        "Delta120_contribution_AA": _f(r["Delta120_contribution_AA"]),
        "C1_DA_N0": _f(r["C1_DA_N0"]), "C1_DA_N1": _f(r["C1_DA_N1"]),
        "delta_C1_N1": _f(r["delta_C1_N1"]),
        "delta_C1_N1_ci": [lo, hi],
        "delta_C1_N1_ci_excludes_zero": (None if lo is None or hi is None
                                         else not (lo < 0 < hi)),
        "N0_frac_exchangeable": _f(r["N0_frac_exchangeable"]),
        "N0_mean_swaps": _f(r["N0_mean_swaps"]),
        "N0_frac_fully_frozen": _f(r["N0_frac_fully_frozen"]),
        "N1_frac_exchangeable": _f(r["N1_frac_exchangeable"]),
        "N1_mean_swaps": _f(r["N1_mean_swaps"]),
        "N1_frac_fully_frozen": _f(r["N1_frac_fully_frozen"]),
        "support": r["support"], "source": r["source"]}


def _hist_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "all_pass": r["all_pass"],
        "n_events": _i(r["n_events"]),
        "n_accepted_protons": _i(r["n_accepted_protons"]),
        "sentinel_pass": r["sentinel_pass"],
        "counts_5000": r["counts_5000"],
        "seed_ordinal_match": r["seed_ordinal_match"],
        "persisted_field_reproduction": r["persisted_field_reproduction"],
        "zero_unexplained_BQS_violations":
            r["zero_unexplained_BQS_violations"],
        "uid_worldline_validation": r["uid_worldline_validation"],
        "f13_f15_matching": r["f13_f15_matching"],
        "lineage_classification_complete":
            r["lineage_classification_complete"],
        "audit_pairs_20": r["audit_pairs_20"],
        "no_source_or_executable_modification":
            r["no_source_or_executable_modification"]}


def _lineage_row(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "energy": r["energy"], "sample": r["sample"],
        "n_events": _i(r["n_events"]),
        "n_labeled_particles": _i(r["n_labeled_particles"]),
        "n_D1": _i(r["n_D1"]), "n_D2": _i(r["n_D2"]),
        "n_D": _i(r["n_D"]), "n_A": _i(r["n_A"]),
        "n_P": _i(r["n_P"]), "n_U": _i(r["n_U"]),
        "f_D": _f(r["f_D"]), "f_A": _f(r["f_A"])}


def _composite_note() -> Optional[str]:
    prov = _data_json("phaseB4B_BES_provenance.json")
    return prov["energies"]["39"].get("first5000_composite_note")


def _b4a_anchors() -> Dict[str, Any]:
    man = _data_json("phaseB4A_freeze_manifest.json")
    av = man["anchors_verified"]
    return {
        "manifest_n_files": man["n_files"],
        "all_anchors_pass": all(a["pass"] for a in av.values()),
        "B4A_verdict_line": av["B4A_verdict_line"]["found"],
        "B4A_minbias_REAL_C1_DD": _f(av["B4A_minbias_REAL_C1_DD"]["found"]),
        "B4A_minbias_REAL_C1_DA": _f(av["B4A_minbias_REAL_C1_DA"]["found"]),
        "B4A_minbias_REAL_C1_AA": _f(av["B4A_minbias_REAL_C1_AA"]["found"]),
        "B4A_delta_C1_label_vs_N1_minbias":
            av["B4A_delta_C1_label_vs_N1_minbias"]["found"],
        "note": ("the 7.7 GeV row of the frozen energy summary is read "
                 "from the frozen B4-A outputs, not recomputed")}


def _pcms_clamp_note() -> str:
    return ("history-recovery note (frozen "
            "physics_gate/phaseB4B/reports/"
            "phaseB4B_history_recovery_log.md): the explained "
            "deterministic class is sub-threshold elastic scatterings "
            "where pcms clamps the CM momentum to 0 "
            "(whichres.f:241-243); a violation is excused only when "
            "the vertex matches the exact pcms=0 boost prediction "
            "(observed mismatch <= 2.2e-6); production counts: one "
            "event / one vertex at 19.6, one event / one vertex at "
            "27, none at 11.5 or 39")


def _predeclared_outcomes() -> str:
    """The frozen Pattern A-D criteria, extracted verbatim from the
    fenced block under the 'Predeclared outcomes (spec Step 20,
    verbatim)' heading of the locked B4-A hypotheses file."""
    if not HYP_MD.is_file():
        raise ToolError(f"{HYP_MD} not found; the locked B4-A "
                        "hypotheses file must exist first")
    text = HYP_MD.read_text()
    head = "## Predeclared outcomes (spec Step 20, verbatim)"
    start = text.index(head) + len(head)
    rest = text[start:]
    fence1 = rest.index("```") + 3
    fence2 = rest.index("```", fence1)
    return rest[fence1:fence2].strip("\n")


# ----------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------

def history_status(energy: Optional[str] = None,
                   analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen B4-B history status per energy: the history-gate row
    (all ten gates plus all_pass), the sentinel verdict (exact
    reproduction on all historically persisted fields), the analytic
    N0 null-check verdict, the per-energy seeds and R from the frozen
    metadata, and the provenance record (including the 39 GeV
    first-5000 composite note). energy is an optional filter."""
    tool = "b4b.history_status"
    _check_energy(energy, tool)
    use = ENERGIES if energy is None else (energy,)
    gates = {r["energy"]: _hist_row(r)
             for r in _csv(analysis_dir, "phaseB4B_history_gates.csv")}
    sent = {e: _json(analysis_dir,
                     f"phaseB4B_sentinel_{HIST_LABEL[e]}.json")
            for e in use}
    chk = _json(analysis_dir, "phaseB4B_analytic_null_check.json")
    meta = _meta(analysis_dir)
    prov = _data_json("phaseB4B_BES_provenance.json")
    per = {}
    for e in use:
        lab = HIST_LABEL[e]
        per[e] = {
            "history_label": lab,
            "gates": gates[lab],
            "sentinel": {"result": sent[e]["result"],
                         "n_events": sent[e]["n_events"],
                         "seed": sent[e]["seed"]},
            "analytic_null_check_overall":
                chk["per_energy"][e]["overall"],
            "seeds": {"N0": meta["energies"][e]["seed_N0"],
                      "N1": meta["energies"][e]["seed_N1"],
                      "boot": meta["energies"][e]["seed_boot"]},
            "first5000_composite_note":
                prov["energies"][e].get("first5000_composite_note")}
    data = {
        "phase": meta["phase"], "steps": meta["steps"],
        "machinery": meta["machinery"],
        "R": meta["R"], "seed_rule": meta["seed_rule"],
        "per_energy": per,
        "analytic_null_check": {"null": chk["null"],
                                "overall": chk["overall"],
                                "z_threshold": chk["z_threshold"]},
        "hard_gates": meta["hard_gates"],
        "pcms_clamp_note": _pcms_clamp_note(),
        "language_discipline_note": (
            "the frozen discipline text lives in null_metadata.json "
            "(azimuth-blind label permutations on frozen events; no "
            "dynamical intervention; attribution is not causation; "
            "possible-sources only; further mechanism-language "
            "prohibitions verbatim there)")}
    n_pass = sum(1 for e in use if gates[HIST_LABEL[e]]["all_pass"]
                 == "PASS")
    summary = (f"{len(use)} energ(ies); history gates PASS for "
               f"{n_pass}/{len(use)}; analytic check {chk['overall']}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool, "inputs": {"energy": energy}})


def energy_summary(energy: Optional[str] = None,
                   analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen per-energy summary table (7.7 GeV row read from the
    frozen B4-A outputs plus the four B4-B energies): event and
    accepted-proton counts, lineage fractions f_D/f_A, pair-class
    fractions F_DD/F_DA/F_AA, C1 per class and the DA contribution,
    Delta120 total and per-class contributions, N0/N1 C1_DA, the
    primary delta_C1_N1 with bootstrap 95% CI and a CI-excludes-zero
    flag, N0/N1 mobility columns, and the support flag with its
    source string. energy is an optional filter."""
    tool = "b4b.energy_summary"
    _check_energy(energy, tool, allowed=ENERGIES_WITH_B4A)
    rows = [_energy_row(r)
            for r in _csv(analysis_dir, "phaseB4B_energy_summary.csv")
            if energy is None or r["energy"] == energy]
    data = {"rows": rows,
            "contrasts": _meta(analysis_dir)["contrasts"],
            "note": ("the 7.7 row is read from frozen B4-A outputs "
                     "(source column says so verbatim); the other four "
                     "rows are from the frozen B4-B shards of this run")}
    summary = f"{len(rows)} energy-summary row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool, "inputs": {"energy": energy}})


def lineage_coverage(energy: Optional[str] = None,
                     sample: Optional[str] = None,
                     analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen lineage-coverage table per energy and sample
    (proton / all-B=+1 baryon): labeled-particle count and the
    D1/D2/D/A/P/U class counts with f_D and f_A. P and U are reported
    as counts only and are excluded from inference (frozen domain
    rule). energy and sample are optional filters."""
    tool = "b4b.lineage_coverage"
    _check_energy(energy, tool)
    if sample is not None and sample not in SAMPLES:
        raise ToolError(f"sample must be one of {SAMPLES}",
                        provenance={"tool": tool})
    rows = [_lineage_row(r)
            for r in _csv(analysis_dir, "phaseB4B_lineage_coverage.csv")
            if (energy is None or r["energy"] == energy)
            and (sample is None or r["sample"] == sample)]
    data = {"rows": rows,
            "domain": _meta(analysis_dir)["domain"]}
    summary = f"{len(rows)} lineage-coverage row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"energy": energy, "sample": sample}})


def real_pair_structure(energy: Optional[str] = None,
                        cell: Optional[str] = None,
                        width_deg: Optional[float] = None,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen REAL-arm accepted-proton pair structure per energy,
    cell, kernel width and pair class (DD/DA/AA): pair counts and
    frozen support flags, pair-fraction F, class-level Delta_c and
    C1_c, and the additive contributions to the set Delta(w) and C1
    with bootstrap SDs and 95% CIs. energy, cell and width_deg
    (60/90/120/180) are optional filters."""
    tool = "b4b.real_pair_structure"
    _check_energy(energy, tool)
    _check_cell(cell, tool)
    _check_width(width_deg, tool)
    rows = [_pair_row(r)
            for r in _csv(analysis_dir, "phaseB4B_real_pair_structure.csv")
            if (energy is None or r["energy"] == energy)
            and (cell is None or r["cell"] == cell)
            and (width_deg is None
                 or r["width_deg"] == f"{float(width_deg)}")]
    meta = _meta(analysis_dir)
    data = {"rows": rows, "estimator": meta["estimator"],
            "support_rule": meta["support_rule"],
            "note": ("REAL arm recomputes the frozen DD/DA/AA "
                     "decomposition on the frozen B4-B events with the "
                     "same estimator as B4-A")}
    summary = f"{len(rows)} REAL pair-structure row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"energy": energy, "cell": cell,
                               "width_deg": width_deg}})


def null_pair_structure(null: Optional[str] = None,
                        energy: Optional[str] = None,
                        cell: Optional[str] = None,
                        width_deg: Optional[float] = None,
                        analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen null-arm (N0/N1) accepted-proton pair structure per
    energy, cell, kernel width and pair class, with the same columns
    as the REAL arm; null-arm values are per-event permutation means
    first, physical-event bootstrap second (frozen rule). null,
    energy, cell and width_deg are optional filters; omitting null
    returns both null arms."""
    tool = "b4b.null_pair_structure"
    _check_energy(energy, tool)
    _check_cell(cell, tool)
    _check_null(null, tool)
    _check_width(width_deg, tool)
    use = NULLS if null is None else (null,)
    rows = []
    for n in use:
        for r in _csv(analysis_dir, f"phaseB4B_{n}_pair_structure.csv"):
            if (energy is not None and r["energy"] != energy) or \
                    (cell is not None and r["cell"] != cell) or \
                    (width_deg is not None
                     and r["width_deg"] != f"{float(width_deg)}"):
                continue
            rows.append({"null": n, **_pair_row(r)})
    meta = _meta(analysis_dir)
    data = {"rows": rows, "estimator": meta["estimator"],
            "nulls": meta["nulls"],
            "support_rule": meta["support_rule"],
            "mobility_note": ("stratification restricts label mobility: "
                              "the N1 exchangeable-particle fraction is "
                              "well below N0 at every energy; the frozen "
                              "rule reports mobility and never relaxes "
                              "it")}
    summary = f"{len(rows)} null pair-structure row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"null": null, "energy": energy,
                               "cell": cell, "width_deg": width_deg}})


def real_null_contrast(energy: Optional[str] = None,
                       cell: Optional[str] = None,
                       null: Optional[str] = None,
                       quantity: Optional[str] = None,
                       analysis_dir: Optional[str] = None) -> ToolResult:
    """The frozen REAL-minus-null contrast table per energy, cell and
    null: the primary delta_C1_label = C1_DA_REAL - C1_DA_null
    (negative = REAL more negative), the secondary
    delta_Delta120_label, and the retention_C1_DA ratio rows, each
    with shared-index bootstrap SD and 95% CI, a CI-excludes-zero
    flag where a point is reported, both arm values, and the frozen
    label string verbatim (retention rows carry the frozen
    random-split / composition-retention labels, including the
    'not reported' variants where the frozen rule withholds the
    ratio). All filters are optional."""
    tool = "b4b.real_null_contrast"
    _check_energy(energy, tool)
    _check_cell(cell, tool)
    _check_null(null, tool)
    if quantity is not None and quantity not in QUANTITIES:
        raise ToolError(f"quantity must be one of {QUANTITIES}",
                        provenance={"tool": tool})
    rows = [_contrast_row(r)
            for r in _csv(analysis_dir, "phaseB4B_real_null_contrasts.csv")
            if (energy is None or r["energy"] == energy)
            and (cell is None or r["cell"] == cell)
            and (null is None or r["null"] == null)
            and (quantity is None or r["quantity"] == quantity)]
    meta = _meta(analysis_dir)
    data = {"rows": rows,
            "contrasts": meta["contrasts"],
            "bootstrap": meta["bootstrap"],
            "mobility_note": ("REAL-vs-N1 is a conservative comparison "
                              "against a partially composition-"
                              "preserving null with restricted "
                              "permutation support; mobility is "
                              "reported, never relaxed")}
    summary = f"{len(rows)} real-null contrast row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"energy": energy, "cell": cell,
                               "null": null, "quantity": quantity}})


def population_opposition(energy: Optional[str] = None,
                          cell: Optional[str] = None,
                          arm: Optional[str] = None,
                          analysis_dir: Optional[str] = None
                          ) -> ToolResult:
    """The frozen unit-vector D-A opposition table per energy, cell
    and arm (REAL/N0/N1): the per-event cosTheta_DA distribution
    summary (events on support, mean with bootstrap 95% CI, median,
    p10/p25/p75/p90, and the fraction of events with negative
    cosTheta_DA). energy, cell and arm are optional filters."""
    tool = "b4b.population_opposition"
    _check_energy(energy, tool)
    _check_cell(cell, tool)
    _check_arm(arm, tool)
    rows = [_pop_row(r)
            for r in _csv(analysis_dir,
                          "phaseB4B_population_opposition.csv")
            if (energy is None or r["energy"] == energy)
            and (cell is None or r["cell"] == cell)
            and (arm is None or r["arm"] == arm)]
    data = {"rows": rows,
            "note": ("unit-Q opposition of the D and A populations; "
                     "attribution-level tabulation on frozen events")}
    summary = f"{len(rows)} population-opposition row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"energy": energy, "cell": cell,
                               "arm": arm}})


def baryon_corroboration(energy: Optional[str] = None,
                         cell: Optional[str] = None,
                         section: Optional[str] = None,
                         analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """The frozen all-B=+1 corroboration table per energy: the
    pair_structure section (REAL/N0/N1 per cell and class with
    bootstrap CIs and support flags; N1 strata = species group x pT x
    y) and the contrast section (delta_C1_label /
    delta_Delta120_label vs N0 and N1 per cell). energy, cell and
    section are optional filters."""
    tool = "b4b.baryon_corroboration"
    _check_energy(energy, tool)
    _check_cell(cell, tool)
    if section is not None and section not in ("pair_structure", "contrast"):
        raise ToolError("section must be pair_structure or contrast",
                        provenance={"tool": tool})
    rows = [_baryon_row(r)
            for r in _csv(analysis_dir,
                          "phaseB4B_baryon_corroboration.csv")
            if (energy is None or r["energy"] == energy)
            and (cell is None or r["cell"] == cell)
            and (section is None or r["section"] == section)]
    data = {"rows": rows,
            "note": ("all accepted B=+1 particles (not only accepted "
                     "protons); same frozen null definitions")}
    summary = f"{len(rows)} baryon corroboration row(s)"
    return ToolResult.ok(
        summary, data,
        provenance={"tool": tool,
                    "inputs": {"energy": energy, "cell": cell,
                               "section": section}})


def cross_energy_summary(analysis_dir: Optional[str] = None
                         ) -> ToolResult:
    """A bundled read-only cross-energy view of the frozen summary
    table: per energy (7.7 from frozen B4-A, then 11.5/19.6/27/39)
    the lineage fraction f_D, pair-class fractions, C1_DD/C1_DA/C1_AA,
    the N0/N1 C1_DA, and the primary delta_C1_N1 with its bootstrap
    95% CI and CI-excludes-zero flag, plus the support flag and the
    per-energy sign pattern of the REAL DD/DA/AA C1_c at minbias
    w=120 (from the frozen pair-structure tables). Data only."""
    esum = [_energy_row(r)
            for r in _csv(analysis_dir, "phaseB4B_energy_summary.csv")]
    real = [_pair_row(r)
            for r in _csv(analysis_dir, "phaseB4B_real_pair_structure.csv")
            if r["cell"] == "minbias" and r["width_deg"] == "120.0"]
    pat = {}
    for r in real:
        e = r["energy"]
        lo, hi = r["C1_c_ci"]
        pat.setdefault(e, {})[r["class"]] = {
            "C1_c": r["C1_c"],
            "sign": "+" if r["C1_c"] > 0 else "-",
            "ci": [lo, hi],
            "ci_excludes_zero": not (lo < 0 < hi)}
    data = {
        "per_energy": [{
            "energy": r["energy"], "sqrt_s": r["sqrt_s"],
            "f_D": r["f_D"], "f_A": r["f_A"],
            "F_DD": r["F_DD"], "F_DA": r["F_DA"], "F_AA": r["F_AA"],
            "C1_DD": r["C1_DD"], "C1_DA": r["C1_DA"],
            "C1_AA": r["C1_AA"],
            "C1_DA_N0": r["C1_DA_N0"], "C1_DA_N1": r["C1_DA_N1"],
            "delta_C1_N1": r["delta_C1_N1"],
            "delta_C1_N1_ci": r["delta_C1_N1_ci"],
            "delta_C1_N1_ci_excludes_zero":
                r["delta_C1_N1_ci_excludes_zero"],
            "support": r["support"], "source": r["source"]}
            for r in esum],
        "real_minbias_w120_sign_pattern": pat,
        "sign_pattern_note": (
            "the frozen 7.7 GeV sign pattern (DD +, DA -, AA +) is "
            "carried by the B4-A anchors; at 39 GeV the REAL C1_DA "
            "point is positive, so the DA-negative arm of the pattern "
            "does not hold there"),
        "contrasts": _meta(analysis_dir)["contrasts"]}
    n_excl = sum(1 for r in esum if r["delta_C1_N1_ci_excludes_zero"])
    summary = (f"{len(esum)} energies; delta_C1_N1 CI excludes 0 at "
               f"{n_excl}/{len(esum)}")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b4b.cross_energy_summary", "inputs": {}})


def mechanism_evidence(analysis_dir: Optional[str] = None
                       ) -> ToolResult:
    """A bundled read-only summary of the frozen B4-B outputs: the
    B4-A anchors (verdict line and 7.7 GeV C1_DD/DA/AA plus the 7.7
    delta_C1_label vs N1) from the frozen step-0 manifest, the
    per-energy support flags, the per-energy REAL minbias w=120
    DD/DA/AA sign pattern with CIs, the primary delta_C1_N1 with
    bootstrap CIs per energy, the minbias retention_C1_DA ratios with
    their frozen label strings verbatim (including 'not reported'
    variants), the predeclared Pattern A-D criteria verbatim from the
    locked hypotheses file, and the caveats (N1 mobility per energy,
    the pcms-clamp history note, the 39 GeV first-5000 composite
    note, the positive 39 GeV REAL C1_DA). Data only."""
    meta = _meta(analysis_dir)
    esum = [_energy_row(r)
            for r in _csv(analysis_dir, "phaseB4B_energy_summary.csv")]
    b4b = {r["energy"]: r for r in esum if r["energy"] in ENERGIES}
    real = [_pair_row(r)
            for r in _csv(analysis_dir, "phaseB4B_real_pair_structure.csv")
            if r["cell"] == "minbias" and r["width_deg"] == "120.0"]
    pat = {}
    for r in real:
        lo, hi = r["C1_c_ci"]
        pat.setdefault(r["energy"], {})[r["class"]] = {
            "C1_c": r["C1_c"], "C1_c_ci": [lo, hi],
            "ci_excludes_zero": not (lo < 0 < hi),
            "support": r["support"]}
    con = _csv(analysis_dir, "phaseB4B_real_null_contrasts.csv")
    retention = {}
    for e in ENERGIES:
        retention[e] = {}
        for n in NULLS:
            row = next(r for r in con
                       if r["energy"] == e and r["cell"] == "minbias"
                       and r["null"] == n
                       and r["quantity"] == "retention_C1_DA")
            lo, hi = _f(row["ci_lo"]), _f(row["ci_hi"])
            retention[e][n] = {
                "point": _f(row["point"]), "sd": _f(row["sd"]),
                "ci": [lo, hi],
                "real_C1_DA": _f(row["real_point"]),
                "null_C1_DA": _f(row["null_point"]),
                "label": row["label"]}
    data = {
        "b4a_anchors": _b4a_anchors(),
        "per_energy_support": {e: b4b[e]["support"] for e in ENERGIES},
        "real_minbias_w120_sign_pattern": pat,
        "delta_C1_N1_per_energy": {
            e: {"point": b4b[e]["delta_C1_N1"],
                "ci": b4b[e]["delta_C1_N1_ci"],
                "ci_excludes_zero":
                    b4b[e]["delta_C1_N1_ci_excludes_zero"]}
            for e in ENERGIES},
        "retention_C1_DA_minbias": retention,
        "retention_rule": meta["contrasts"]["retention"],
        "predeclared_outcomes_step20_verbatim": _predeclared_outcomes(),
        "caveats": {
            "N1_frac_exchangeable_per_energy":
                {e: b4b[e]["N1_frac_exchangeable"] for e in ENERGIES},
            "mobility_note": ("stratification restricts label mobility "
                              "and the restriction grows with energy; "
                              "mobility is reported, never relaxed, so "
                              "REAL-vs-N1 is a conservative comparison"),
            "pcms_clamp_note": _pcms_clamp_note(),
            "first5000_composite_note_39": _composite_note(),
            "c1_da_sign_note": ("at 39 GeV the REAL C1_DA point is "
                                "positive, so no retention ratio is "
                                "reported there and the DA-negative "
                                "sign pattern does not hold at that "
                                "energy")},
        "discipline_note": (
            "azimuth-blind label permutations on frozen events; no "
            "dynamical intervention; attribution is not causation; "
            "mechanism-language prohibitions verbatim in "
            "null_metadata.json and the locked hypotheses file")}
    summary = ("B4-B bundle: B4-A anchors, per-energy sign patterns, "
               "delta_C1_N1 CIs, retention ratios, Pattern A-D "
               "criteria, caveats")
    return ToolResult.ok(
        summary, data,
        provenance={"tool": "b4b.mechanism_evidence", "inputs": {}})


# ----------------------------------------------------------------------
# registration
# ----------------------------------------------------------------------

_OBJ = {"type": "object"}
_DIR_PROP = {"analysis_dir": {"type": "string",
                              "description": "override the Phase B4-B "
                                             "analysis directory "
                                             "(default: the persisted "
                                             "frozen outputs)"}}
_EN_PROP = {"energy": {"type": "string", "enum": list(ENERGIES)}}
_EN_ALL_PROP = {"energy": {"type": "string",
                           "enum": list(ENERGIES_WITH_B4A)}}
_CELL_PROP = {"cell": {"type": "string", "enum": list(CELLS)}}
_NULL_PROP = {"null": {"type": "string", "enum": list(NULLS)}}
_ARM_PROP = {"arm": {"type": "string", "enum": list(ARMS)}}
_W_PROP = {"width_deg": {"type": "number", "enum": [60, 90, 120, 180]}}

register(ToolSpec(
    name="b4b.history_status",
    description=(
        "The frozen B4-B history status (energy optional): history-"
        "gate rows (all ten gates), sentinel exact-reproduction "
        "verdicts, analytic N0 null-check verdicts, per-energy seeds "
        "and R, provenance including the 39 GeV first-5000 composite "
        "note, and the pcms-clamp history note."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=history_status))

register(ToolSpec(
    name="b4b.energy_summary",
    description=(
        "The frozen per-energy summary table (energy optional; 7.7 "
        "row read from frozen B4-A outputs): counts, lineage and "
        "pair-class fractions, C1 per class, Delta120 decomposition, "
        "N0/N1 C1_DA, primary delta_C1_N1 with bootstrap CI and "
        "CI-excludes-zero flag, mobility columns, support flags."),
    input_schema={"type": "object", "properties": {
        **_EN_ALL_PROP, **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=energy_summary))

register(ToolSpec(
    name="b4b.lineage_coverage",
    description=(
        "The frozen lineage-coverage table per energy and sample "
        "(proton / all-B=+1 baryon; both optional): labeled-particle "
        "count, D1/D2/D/A/P/U class counts, f_D and f_A. P/U are "
        "counts only, excluded from inference."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP,
        "sample": {"type": "string", "enum": list(SAMPLES)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=lineage_coverage))

register(ToolSpec(
    name="b4b.real_pair_structure",
    description=(
        "The frozen REAL-arm accepted-proton pair structure per "
        "energy, cell, kernel width and pair class (energy, cell and "
        "width_deg optional): pair counts, support flags, F, "
        "class-level Delta_c and C1_c, and additive Delta(w)/C1 "
        "contributions with bootstrap CIs."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP, **_CELL_PROP, **_W_PROP, **_DIR_PROP},
        "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=real_pair_structure))

register(ToolSpec(
    name="b4b.null_pair_structure",
    description=(
        "The frozen null-arm (N0/N1) accepted-proton pair structure "
        "(null, energy, cell and width_deg optional): same columns as "
        "the REAL arm; null values are per-event permutation means "
        "with physical-event bootstrap."),
    input_schema={"type": "object", "properties": {
        **_NULL_PROP, **_EN_PROP, **_CELL_PROP, **_W_PROP, **_DIR_PROP},
        "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=null_pair_structure))

register(ToolSpec(
    name="b4b.real_null_contrast",
    description=(
        "The frozen REAL-minus-null contrast table (energy, cell, "
        "null and quantity optional): primary delta_C1_label, "
        "secondary delta_Delta120_label and retention_C1_DA ratio "
        "rows with shared-index bootstrap CIs, CI-excludes-zero "
        "flags, both arm values, and frozen retention label strings "
        "verbatim."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP, **_CELL_PROP, **_NULL_PROP,
        "quantity": {"type": "string", "enum": list(QUANTITIES)},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=real_null_contrast))

register(ToolSpec(
    name="b4b.population_opposition",
    description=(
        "The frozen unit-vector D-A opposition summary per energy, "
        "cell and arm (all optional): per-event cosTheta_DA "
        "distribution statistics (mean with bootstrap CI, median, "
        "percentiles, negative fraction)."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP, **_CELL_PROP, **_ARM_PROP, **_DIR_PROP},
        "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=population_opposition))

register(ToolSpec(
    name="b4b.baryon_corroboration",
    description=(
        "The frozen all-B=+1 corroboration table (energy, cell and "
        "section optional): pair_structure section (REAL/N0/N1 per "
        "cell and class with bootstrap CIs; N1 strata = species x pT "
        "x y) and contrast section (delta_C1_label / "
        "delta_Delta120_label vs N0 and N1 per cell)."),
    input_schema={"type": "object", "properties": {
        **_EN_PROP, **_CELL_PROP,
        "section": {"type": "string",
                    "enum": ["pair_structure", "contrast"]},
        **_DIR_PROP}, "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=baryon_corroboration))

register(ToolSpec(
    name="b4b.cross_energy_summary",
    description=(
        "A bundled read-only cross-energy view: per energy (7.7 from "
        "frozen B4-A, then 11.5/19.6/27/39) f_D, pair-class "
        "fractions, C1_DD/C1_DA/C1_AA, N0/N1 C1_DA, primary "
        "delta_C1_N1 with CI and CI-excludes-zero flag, support "
        "flags, and the REAL minbias w=120 DD/DA/AA sign pattern. "
        "Data only."),
    input_schema={"type": "object", "properties": {**_DIR_PROP},
                  "required": []},
    output_schema=_OBJ, risk_level=ANALYSIS,
    handler=cross_energy_summary))

register(ToolSpec(
    name="b4b.mechanism_evidence",
    description=(
        "A bundled read-only summary of the frozen B4-B outputs: "
        "B4-A anchors from the step-0 manifest, per-energy support "
        "flags and REAL minbias w=120 sign patterns, primary "
        "delta_C1_N1 CIs, minbias retention ratios with frozen labels "
        "verbatim, the predeclared Pattern A-D criteria verbatim, and "
        "caveats (N1 mobility, pcms-clamp history note, 39 GeV "
        "composite note, positive 39 GeV C1_DA). Data only."),
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
        for name in sorted(n for n in REGISTRY if n.startswith("b4b.")):
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
