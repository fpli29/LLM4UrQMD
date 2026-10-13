"""Final-state observables, centrality and participant-scaling tools.

All computation goes through the validated analysis modules
(urqmd_agent/final_state, urqmd_agent/analysis). Comparisons are
descriptive only — these tools never claim causal interpretations.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..analysis import centrality as cent
from ..analysis import scaling as sc
from ..core import config
from ..core.errors import ToolError
from ..core.result import ToolResult
from ..final_state.observables import event_observables
from ..final_state.parse_f13 import iter_f13
from ._common import load_event_rows, resolve_repo_path, resolve_summary_csvs
from .registry import ANALYSIS, ToolSpec, register

_SPECIES = ("lambda", "kaon")


def final_state_summary(f13_path: str) -> ToolResult:
    """Per-event species yields of one file13 file (multi-event aware)."""
    path = resolve_repo_path(f13_path)
    events = []
    totals = {"n_ch": 0, "n_lambda": 0, "n_antilambda": 0, "n_kaon0": 0,
              "n_antikaon0": 0}
    for ev in iter_f13(path):
        obs = event_observables(ev)
        events.append({
            "event": obs.event, "ranseed": obs.ranseed,
            "sqrts": obs.sqrts, "bimp": obs.bimp, "n_part": obs.n_part,
            "n_ch": obs.n_ch, "n_lambda": obs.n_lambda,
            "n_antilambda": obs.n_antilambda, "n_kaon0": obs.n_kaon0,
            "n_antikaon0": obs.n_antikaon0,
            "n_neutral_kaon": obs.n_neutral_kaon,
            "npart_final": obs.npart_final, "itotcoll": obs.itotcoll,
        })
        totals["n_ch"] += obs.n_ch
        totals["n_lambda"] += obs.n_lambda
        totals["n_antilambda"] += obs.n_antilambda
        totals["n_kaon0"] += obs.n_kaon0
        totals["n_antikaon0"] += obs.n_antikaon0
    if not events:
        raise ToolError(f"no events parsed from {f13_path}")
    summary = (f"{len(events)} event(s) in {f13_path}: total n_ch="
               f"{totals['n_ch']}, Lambda={totals['n_lambda']}, K0="
               f"{totals['n_kaon0']}, antiK0={totals['n_antikaon0']} "
               "(|y_cm|<0.5)")
    return ToolResult.ok(summary, {"path": f13_path, "events": events,
                                   "totals": totals,
                                   "acceptance": "|y_cm| < 0.5"},
                         provenance={"tool": "urqmd.final_state_summary"})


def _load_rows(dataset: str):
    csvs = resolve_summary_csvs(dataset)
    rows = load_event_rows(csvs)
    return csvs, rows


def _fractional_bin_table(rows):
    n_ch = np.array([r.n_ch for r in rows], dtype=np.int64)
    weights = cent.fractional_tie_weights(n_ch)
    bins = cent.weighted_bin_means(rows, weights)
    return [{
        "bin": b.bin_label, "n_events": b.n_events,
        "mean_npart": b.mean_npart, "mean_lambda": b.mean_lambda,
        "mean_neutral_kaon": b.mean_neutral_kaon,
    } for b in bins]


def centrality(dataset: str = "phase1b") -> ToolResult:
    """Fractional-tie centrality bin membership and per-bin <Npart>."""
    csvs, rows = _load_rows(dataset)
    table = _fractional_bin_table(rows)
    summary = (f"{dataset}: {len(rows)} events, fractional-tie bins; "
               f"<Npart> 0-10% = {table[0]['mean_npart']:.1f}, "
               f"60-80% = {table[-1]['mean_npart']:.1f}")
    return ToolResult.ok(summary, {
        "dataset": dataset, "n_events": len(rows),
        "method": "fractional-tie percentile bins on N_ch (0-10% most "
                  "central = highest N_ch)",
        "bins": sc.CENTRALITY_BINS, "bin_table": table,
        "source_csvs": [str(p) for p in csvs],
    }, provenance={"tool": "urqmd.centrality"})


def _scaling_result(dataset: str, species: str) -> dict:
    csvs, rows = _load_rows(dataset)
    n_ch = np.array([r.n_ch for r in rows], dtype=np.int64)
    weights = cent.fractional_tie_weights(n_ch)
    bin_res = cent.weighted_bin_means(rows, weights)
    which = "lambda" if species == "lambda" else "kaon"
    alpha, _ln_c = sc.fit_alpha(bin_res, which)
    # bootstrap uncertainty from the validated pipeline (integer-bin
    # assignment inside analyze_energy; documented in `method`)
    boot = sc.analyze_energy(rows, seed=config.BOOTSTRAP_SEED_REPRO)
    alpha_err = boot.alpha_lambda_err if which == "lambda" \
        else boot.alpha_kaon_err
    table = [{
        "bin": b.bin_label, "n_events": b.n_events,
        "mean_npart": b.mean_npart,
        "mean_yield": b.mean_lambda if which == "lambda"
                      else b.mean_neutral_kaon,
    } for b in bin_res]
    return {
        "dataset": dataset, "species": species, "n_events": len(rows),
        "alpha": alpha, "alpha_err": alpha_err,
        "n_bootstrap": boot.n_bootstrap,
        "n_bootstrap_ok": boot.n_bootstrap_ok,
        "bin_table": table,
        "method": ("fractional-tie centrality bins; alpha from log-log "
                   "linear fit of bin yields vs <Npart>; bootstrap error "
                   "from the validated scaling pipeline "
                   "(analysis.scaling.analyze_energy)"),
        "source_csvs": [str(p) for p in csvs],
    }


def scaling(dataset: str = "phase1b", species: str = "lambda") -> ToolResult:
    """Per-bin midrapidity yields and participant-scaling exponent alpha."""
    if species not in _SPECIES:
        return ToolResult.error(
            f"unknown species {species!r}; choose from {_SPECIES}",
            provenance={"tool": "urqmd.scaling"})
    data = _scaling_result(dataset, species)
    summary = (f"{dataset} {species}: alpha = {data['alpha']:.4f} +/- "
               f"{data['alpha_err']:.4f} over {data['n_events']} events "
               "(fractional-tie bins)")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.scaling"})


def compare(dataset_a: str, dataset_b: str,
            species: str = "lambda") -> ToolResult:
    """Structured descriptive comparison of the scaling of two datasets."""
    if species not in _SPECIES:
        return ToolResult.error(
            f"unknown species {species!r}; choose from {_SPECIES}",
            provenance={"tool": "urqmd.compare"})
    ra = _scaling_result(dataset_a, species)
    rb = _scaling_result(dataset_b, species)
    per_bin = []
    for ba, bb in zip(ra["bin_table"], rb["bin_table"]):
        ya, yb = ba["mean_yield"], bb["mean_yield"]
        per_bin.append({
            "bin": ba["bin"],
            "yield_a": ya, "yield_b": yb,
            "ratio_a_over_b": (ya / yb) if yb else None,
            "mean_npart_a": ba["mean_npart"],
            "mean_npart_b": bb["mean_npart"],
        })
    data = {
        "species": species,
        "dataset_a": ra, "dataset_b": rb,
        "alpha_a": ra["alpha"], "alpha_b": rb["alpha"],
        "delta_alpha": ra["alpha"] - rb["alpha"],
        "per_bin": per_bin,
    }
    summary = (f"descriptive comparison only; no causal interpretation — "
               f"{dataset_a} vs {dataset_b} ({species}): alpha "
               f"{ra['alpha']:.4f} vs {rb['alpha']:.4f} "
               f"(delta {data['delta_alpha']:+.4f})")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.compare"})


register(ToolSpec(
    name="urqmd.final_state_summary",
    description=(
        "Parse one file13 final-state file and report per-event species "
        "yields (n_ch, Lambda/anti-Lambda/K0/anti-K0 within |y_cm|<0.5, "
        "N_part, bimp, sqrts, ranseed) plus totals. Analysis of existing "
        "output only; never runs UrQMD."),
    input_schema={"type": "object", "properties": {
        "f13_path": {"type": "string",
                     "description": "repo-relative or absolute path to a "
                                    "file13 file"}},
        "required": ["f13_path"]},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=final_state_summary,
))

register(ToolSpec(
    name="urqmd.centrality",
    description=(
        "Fractional-tie centrality binning of a dataset ('phase1b' or "
        "'phase1b2') on per-event N_ch, with per-bin <Npart>. Analysis of "
        "existing campaign CSVs only."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b", "phase1b2"],
                    "default": "phase1b"}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=centrality,
))

register(ToolSpec(
    name="urqmd.scaling",
    description=(
        "Participant-scaling analysis of a dataset: per-bin mean yields "
        "and the power-law exponent alpha (Yield ~ <Npart>^alpha) with a "
        "bootstrap uncertainty. species: 'lambda' or 'kaon' (neutral kaons, "
        "K0+anti-K0). Descriptive only."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b", "phase1b2"],
                    "default": "phase1b"},
        "species": {"type": "string", "enum": ["lambda", "kaon"],
                    "default": "lambda"}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=scaling,
))

register(ToolSpec(
    name="urqmd.compare",
    description=(
        "Structured comparison of the participant scaling of two datasets "
        "(per-bin yield ratios and alpha difference). The result is a "
        "descriptive comparison only; no causal interpretation."),
    input_schema={"type": "object", "properties": {
        "dataset_a": {"type": "string", "enum": ["phase1b", "phase1b2"]},
        "dataset_b": {"type": "string", "enum": ["phase1b", "phase1b2"]},
        "species": {"type": "string", "enum": ["lambda", "kaon"],
                    "default": "lambda"}},
        "required": ["dataset_a", "dataset_b"]},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=compare,
))
