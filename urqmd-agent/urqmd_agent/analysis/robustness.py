"""Phase-1A-R robustness engine: predeclared analysis variants A-E.

All variants operate ONLY on the Phase-1A compact event summaries.
No new UrQMD events, no physics changes, no mechanism inference.

Variants (physics_gate/robustness_protocol.md):
    A original        - Phase-1A integer-threshold centrality, 6 bins
    B fractional      - fractional-tie centrality, 6 bins
    C fractional_0-60 - fractional-tie, bins 0-10..40-60
    D fractional_0-40 - fractional-tie, bins 0-10..30-40 (diagnostic)
    E detrank         - deterministic-rank exact-count centrality, 6 bins

FIT 1: unweighted log-log OLS (fit_alpha from scaling.py).
FIT 2: full-pipeline event bootstrap (centrality reassigned per replicate),
       seed 20260917, >= 1000 replicates; Delta_alpha per replicate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from .centrality import (deterministic_rank_indices, fractional_tie_weights,
                         weighted_bin_means)
from .scaling import (CENTRALITY_BINS, BinResult, EventRow, assign_centrality,
                      bin_means, fit_alpha)

VARIANTS = ("A", "B", "C", "D", "E")
VARIANT_LABELS = {
    "A": "original",
    "B": "fractional-tie",
    "C": "fractional-tie 0-60%",
    "D": "fractional-tie 0-40%",
    "E": "deterministic-rank",
}
FIT_BINS = {"A": 6, "B": 6, "C": 5, "D": 4, "E": 6}

ROBUSTNESS_SEED = 20260916        # deterministic-rank central seed
BOOTSTRAP_SEED = 20260917         # FIT-2 bootstrap
N_BOOTSTRAP = 1000
N_TIE_SEEDS = 200


def _n_ch(rows: Sequence[EventRow]) -> np.ndarray:
    return np.array([r.n_ch for r in rows], dtype=np.int64)


def variant_bin_results(rows: Sequence[EventRow], variant: str,
                        tie_seed: int = ROBUSTNESS_SEED
                        ) -> List[BinResult]:
    """Centrality assignment + bin means for one variant (all 6 bins;
    the fit stage decides how many bins to use)."""
    if variant in ("A",):
        return bin_means(rows, assign_centrality(_n_ch(rows)))
    if variant in ("B", "C", "D"):
        return weighted_bin_means(rows, fractional_tie_weights(_n_ch(rows)))
    if variant == "E":
        idx = deterministic_rank_indices(
            _n_ch(rows), [r.event_id for r in rows],
            [r.seed for r in rows], tie_seed)
        return bin_means(rows, idx)
    raise ValueError(f"unknown variant {variant}")


@dataclass(frozen=True)
class FitTriple:
    alpha_lambda: float
    alpha_kaon: float
    delta_alpha: float


def fit_variant(bin_res: Sequence[BinResult], variant: str) -> FitTriple:
    """FIT 1 (unweighted log-log OLS) on the variant's declared bins."""
    keep = bin_res[:FIT_BINS[variant]]
    aL, _ = fit_alpha(keep, "lambda")
    aK, _ = fit_alpha(keep, "kaon")
    return FitTriple(aL, aK, aL - aK)


def _finite(t: FitTriple) -> bool:
    return all(math.isfinite(v) for v in
               (t.alpha_lambda, t.alpha_kaon, t.delta_alpha))


@dataclass(frozen=True)
class BootStats:
    n_ok: int
    median: float
    std: float
    p16: float
    p84: float


def _stats(arr: np.ndarray, n_total: int) -> BootStats:
    if len(arr) < 2:
        nan = float("nan")
        return BootStats(len(arr), nan, nan, nan, nan)
    return BootStats(int(len(arr)), float(np.median(arr)),
                     float(arr.std(ddof=1)),
                     float(np.percentile(arr, 16)),
                     float(np.percentile(arr, 84)))


@dataclass(frozen=True)
class VariantResult:
    variant: str
    label: str
    central: FitTriple                 # FIT 1 on the real sample
    boot_lambda: BootStats             # FIT 2
    boot_kaon: BootStats
    boot_delta: BootStats
    bins: tuple


def analyze_variant(rows: Sequence[EventRow], variant: str,
                    boot_cache: Optional[dict] = None) -> VariantResult:
    """Central FIT-1 values plus FIT-2 bootstrap stats.

    boot_cache: optional dict from bootstrap_all() so that all variants
    share identical bootstrap replicates (computed once per energy)."""
    bins = variant_bin_results(rows, variant)
    central = fit_variant(bins, variant)
    if boot_cache is None:
        boot_cache = bootstrap_all(rows)
    aL, aK, d = boot_cache[variant]
    return VariantResult(
        variant=variant, label=VARIANT_LABELS[variant], central=central,
        boot_lambda=_stats(aL, len(aL)), boot_kaon=_stats(aK, len(aK)),
        boot_delta=_stats(d, len(d)), bins=tuple(bins))


def bootstrap_all(rows: Sequence[EventRow],
                  n_bootstrap: int = N_BOOTSTRAP,
                  seed: int = BOOTSTRAP_SEED,
                  tie_seed: int = ROBUSTNESS_SEED
                  ) -> Dict[str, tuple]:
    """One shared bootstrap: every variant is evaluated on the SAME event
    resample in each replicate. Returns variant -> (aL, aK, dAlpha) arrays
    of successful replicates."""
    n = len(rows)
    rng = np.random.default_rng(seed)
    out = {v: [[], [], []] for v in VARIANTS}
    for _ in range(n_bootstrap):
        samp = [rows[i] for i in rng.integers(0, n, n)]
        # fractional-tie assignment shared by B, C, D
        frac_bins = weighted_bin_means(samp, fractional_tie_weights(_n_ch(samp)))
        per_variant = {
            "A": bin_means(samp, assign_centrality(_n_ch(samp))),
            "B": frac_bins, "C": frac_bins, "D": frac_bins,
            "E": bin_means(samp, deterministic_rank_indices(
                _n_ch(samp), [r.event_id for r in samp],
                [r.seed for r in samp], tie_seed)),
        }
        for v in VARIANTS:
            t = fit_variant(per_variant[v], v)
            if _finite(t):
                out[v][0].append(t.alpha_lambda)
                out[v][1].append(t.alpha_kaon)
                out[v][2].append(t.delta_alpha)
    return {v: (np.array(a[0]), np.array(a[1]), np.array(a[2]))
            for v, a in out.items()}


def tie_ensemble(rows: Sequence[EventRow],
                 n_seeds: int = N_TIE_SEEDS,
                 base_seed: int = ROBUSTNESS_SEED) -> Dict[str, np.ndarray]:
    """200 deterministic tie-break realizations (NOT a physics bootstrap):
    how much do alpha_Lambda, alpha_K, Delta_alpha move solely because
    events inside identical-N_ch tie groups are exchangeable."""
    aL, aK, d = [], [], []
    for i in range(n_seeds):
        t = fit_variant(variant_bin_results(rows, "E",
                                            tie_seed=base_seed + i), "E")
        if _finite(t):
            aL.append(t.alpha_lambda)
            aK.append(t.alpha_kaon)
            d.append(t.delta_alpha)
    return {"alpha_lambda": np.array(aL), "alpha_kaon": np.array(aK),
            "delta_alpha": np.array(d)}


def leave_one_bin_out(rows: Sequence[EventRow], variant: str = "B"
                      ) -> Dict[str, FitTriple]:
    """Refit after removing each centrality bin one at a time.

    Returns {"full": FitTriple, "<bin label>": FitTriple, ...} using the
    variant's own bin count (6 for B) as the reference set."""
    bins = variant_bin_results(rows, variant)
    n_use = FIT_BINS[variant]
    res = {"full": fit_variant(bins, variant)}
    for j in range(n_use):
        sub = [b for k, b in enumerate(bins) if k != j]
        aL, _ = fit_alpha(sub, "lambda")
        aK, _ = fit_alpha(sub, "kaon")
        res[bins[j].bin_label] = FitTriple(aL, aK, aL - aK)
    return res


def local_slopes(bin_res: Sequence[BinResult], n_bins: int = 6
                 ) -> Dict[str, list]:
    """Adjacent-bin local slopes alpha_local(i,j) for Lambda and kaons."""
    out = {"lambda": [], "kaon": [], "labels": []}
    bs = [b for b in bin_res[:n_bins]]
    for i in range(len(bs) - 1):
        b1, b2 = bs[i], bs[i + 1]
        if min(b1.mean_lambda, b2.mean_lambda, b1.mean_neutral_kaon,
               b2.mean_neutral_kaon) <= 0:
            out["lambda"].append(float("nan"))
            out["kaon"].append(float("nan"))
        else:
            dx = math.log(b2.mean_npart) - math.log(b1.mean_npart)
            out["lambda"].append(
                (math.log(b2.mean_lambda) - math.log(b1.mean_lambda)) / dx)
            out["kaon"].append(
                (math.log(b2.mean_neutral_kaon)
                 - math.log(b1.mean_neutral_kaon)) / dx)
        out["labels"].append(f"{b1.bin_label}->{b2.bin_label}")
    return out
