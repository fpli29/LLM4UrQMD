"""Participant-scaling analysis for the Phase-1A reproduction gate.

Implements exactly the frozen protocol (physics_gate/protocol.md):

- centrality bins = percentiles of per-event N_ch (charged pi/K/p, full
  phase space) within each energy sample; 0-10% = highest N_ch
- <N_part> and mean yields (Lambda, neutral kaons) per centrality bin
- power-law fit  Yield = C * <N_part>^alpha  as a linear fit in log-log
- event-level bootstrap for uncertainties on alpha and Delta_alpha

No NetworkX, no fitting black boxes beyond numpy least squares; deterministic
bootstrap with a recorded seed.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

#: frozen centrality bin edges (percent), 0-10% = most central (highest N_ch)
CENTRALITY_BINS = ((0, 10), (10, 20), (20, 30), (30, 40), (40, 60), (60, 80))

BOOTSTRAP_SEED = 20260916
N_BOOTSTRAP = 500


@dataclass(frozen=True)
class EventRow:
    n_ch: int
    n_part: float
    n_lambda: int
    n_neutral_kaon: int
    event_id: int = 0
    seed: int = 0


def load_summary(csv_path: Path) -> List[EventRow]:
    rows: List[EventRow] = []
    with open(csv_path) as fh:
        for rec in csv.DictReader(fh):
            rows.append(EventRow(
                n_ch=int(rec["n_ch"]),
                n_part=float(rec["n_part_glauber"]),
                n_lambda=int(rec["n_lambda_y05"]),
                n_neutral_kaon=int(rec["n_neutral_kaon_y05"]),
                event_id=int(rec["event_id"]),
                seed=int(rec["seed"])))
    if not rows:
        raise ValueError(f"empty summary file: {csv_path}")
    return rows


def merge_summaries(paths: Sequence[Path]) -> List[EventRow]:
    rows: List[EventRow] = []
    for p in paths:
        rows.extend(load_summary(p))
    return rows


def assign_centrality(n_ch_values: np.ndarray,
                      bins=CENTRALITY_BINS) -> List[List[int]]:
    """Percentile binning on N_ch; returns event indices per bin.

    Bin (lo, hi) in percent centrality contains events whose N_ch lies
    between the (100-hi)-th and (100-lo)-th percentile of the sample.
    """
    out: List[List[int]] = []
    for lo, hi in bins:
        q_hi = np.percentile(n_ch_values, 100.0 - lo)  # upper N_ch edge
        q_lo = np.percentile(n_ch_values, 100.0 - hi)  # lower N_ch edge
        if lo == 0:
            idx = list(np.nonzero(n_ch_values >= q_lo)[0])
        else:
            idx = [i for i in range(len(n_ch_values))
                   if q_lo <= n_ch_values[i] < q_hi]
        out.append(sorted(idx))
    return out


@dataclass(frozen=True)
class BinResult:
    bin_label: str
    n_events: int
    mean_npart: float
    mean_lambda: float
    mean_neutral_kaon: float


def bin_means(rows: Sequence[EventRow],
              bin_indices: Sequence[Sequence[int]]) -> List[BinResult]:
    out = []
    for (lo, hi), idx in zip(CENTRALITY_BINS, bin_indices):
        sel = [rows[i] for i in idx]
        if not sel:
            out.append(BinResult(f"{lo}-{hi}%", 0, float("nan"),
                                 float("nan"), float("nan")))
            continue
        out.append(BinResult(
            f"{lo}-{hi}%", len(sel),
            float(np.mean([r.n_part for r in sel])),
            float(np.mean([r.n_lambda for r in sel])),
            float(np.mean([r.n_neutral_kaon for r in sel]))))
    return out


def fit_alpha(bin_res: Sequence[BinResult], which: str) -> tuple[float, float]:
    """Linear fit ln(Yield) = ln C + alpha ln<N_part>.

    Returns (alpha, lnC). Bins with nonpositive yield or N_part are skipped.
    `which` is 'lambda' or 'kaon'.
    """
    xs, ys = [], []
    for b in bin_res:
        y = b.mean_lambda if which == "lambda" else b.mean_neutral_kaon
        if b.n_events > 0 and y > 0 and b.mean_npart > 0:
            xs.append(math.log(b.mean_npart))
            ys.append(math.log(y))
    if len(xs) < 2:
        return float("nan"), float("nan")
    coeff = np.polyfit(np.array(xs), np.array(ys), 1)
    return float(coeff[0]), float(coeff[1])


@dataclass(frozen=True)
class ScalingResult:
    n_events: int
    bins: Tuple[BinResult, ...]
    alpha_lambda: float
    alpha_kaon: float
    delta_alpha: float
    alpha_lambda_err: float
    alpha_kaon_err: float
    delta_alpha_err: float
    n_bootstrap: int
    n_bootstrap_ok: int


def analyze_energy(rows: Sequence[EventRow],
                   n_bootstrap: int = N_BOOTSTRAP,
                   seed: int = BOOTSTRAP_SEED) -> ScalingResult:
    n_ch = np.array([r.n_ch for r in rows])
    bins = assign_centrality(n_ch)
    base = bin_means(rows, bins)
    aL, _ = fit_alpha(base, "lambda")
    aK, _ = fit_alpha(base, "kaon")

    rng = np.random.default_rng(seed)
    boot_L, boot_K = [], []
    n = len(rows)
    for _ in range(n_bootstrap):
        samp = [rows[i] for i in rng.integers(0, n, n)]
        n_ch_b = np.array([r.n_ch for r in samp])
        bb = bin_means(samp, assign_centrality(n_ch_b))
        bL, _ = fit_alpha(bb, "lambda")
        bK, _ = fit_alpha(bb, "kaon")
        if math.isfinite(bL) and math.isfinite(bK):
            boot_L.append(bL)
            boot_K.append(bK)
    arr_L = np.array(boot_L)
    arr_K = np.array(boot_K)
    d = arr_L - arr_K
    return ScalingResult(
        n_events=len(rows), bins=tuple(base),
        alpha_lambda=aL, alpha_kaon=aK, delta_alpha=aL - aK,
        alpha_lambda_err=float(arr_L.std(ddof=1)) if len(arr_L) > 1 else float("nan"),
        alpha_kaon_err=float(arr_K.std(ddof=1)) if len(arr_K) > 1 else float("nan"),
        delta_alpha_err=float(d.std(ddof=1)) if len(d) > 1 else float("nan"),
        n_bootstrap=n_bootstrap, n_bootstrap_ok=len(boot_L))
