"""Alternative centrality assignments for the Phase-1A-R robustness gate.

Two deterministic methods beyond the Phase-1A integer-threshold assignment:

fractional_tie_weights
    N_ch tie groups are split fractionally across bin boundaries so every
    bin carries EXACTLY its requested percentile mass. No randomness.

deterministic_rank_indices
    exact-count bins; ties inside an N_ch group are ordered by a
    pseudo-random key derived ONLY from (event_id, event seed, robustness
    seed). Physics observables (N_part, yields, bimp) are never used.

Both operate on numpy arrays and are side-effect free.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from .scaling import CENTRALITY_BINS


def fractional_tie_weights(n_ch: np.ndarray,
                           bins: Sequence[Tuple[int, int]] = CENTRALITY_BINS
                           ) -> List[np.ndarray]:
    """Return per-bin event-weight arrays with exact percentile mass.

    Events are grouped by identical N_ch; groups are ordered by N_ch
    descending (most central first). Each group carries probability mass
    n_group / N_total. A group straddling a bin boundary is split: every
    event in the group receives weight = overlap_fraction in each adjacent
    bin. Bin (lo, hi) in percent centrality must receive total weight
    (hi - lo)/100 * N_total (up to floating-point rounding).
    """
    n_ch = np.asarray(n_ch, dtype=np.int64)
    n_total = len(n_ch)
    if n_total == 0:
        raise ValueError("empty event sample")

    # group by identical N_ch, ordered descending
    values, first_idx, counts = np.unique(
        n_ch, return_index=True, return_counts=True)
    order = np.argsort(-values)          # descending N_ch
    values, counts = values[order], counts[order]

    # group index per event, aligned with the descending ordering
    group_of = np.empty(n_total, dtype=np.int64)
    for gi, v in enumerate(values):
        group_of[n_ch == v] = gi

    weights = [np.zeros(n_total) for _ in bins]
    cum = 0.0                            # cumulative fraction from the top
    for gi in range(len(values)):
        mass = counts[gi] / n_total
        g_lo, g_hi = cum, cum + mass     # centrality-fraction interval
        for bi, (lo, hi) in enumerate(bins):
            b_lo, b_hi = lo / 100.0, hi / 100.0
            overlap = min(g_hi, b_hi) - max(g_lo, b_lo)
            if overlap > 0.0:
                weights[bi][group_of == gi] = overlap / mass
        cum = g_hi
    return weights


def deterministic_rank_indices(
        n_ch: np.ndarray,
        event_ids: Sequence[int],
        event_seeds: Sequence[int],
        robustness_seed: int,
        bins: Sequence[Tuple[int, int]] = CENTRALITY_BINS
        ) -> List[np.ndarray]:
    """Exact-count percentile bins with deterministic tie breaking.

    Events are sorted by N_ch descending; ties are ordered by a
    pseudo-random rank derived ONLY from (robustness_seed, event seed,
    event_id) via numpy SeedSequence hashing. Bin (lo, hi) receives exactly
    round((hi-lo)/100 * N) events; any rounding remainder goes to the last
    bin so that all events up to the largest `hi` are assigned exactly once.
    """
    n_ch = np.asarray(n_ch, dtype=np.int64)
    n_total = len(n_ch)
    if not (len(event_ids) == len(event_seeds) == n_total):
        raise ValueError("event_ids/event_seeds length mismatch")

    # deterministic per-event tie key: no physics observable involved
    keys = np.empty(n_total, dtype=np.uint64)
    for i in range(n_total):
        ss = np.random.SeedSequence(
            [robustness_seed, int(event_seeds[i]), int(event_ids[i])])
        keys[i] = np.random.default_rng(ss).integers(0, 2**63,
                                                     dtype=np.int64)
    # sort by N_ch descending, ties by key
    order = sorted(range(n_total), key=lambda i: (-n_ch[i], keys[i]))

    out: List[np.ndarray] = []
    start = 0
    for bi, (lo, hi) in enumerate(bins):
        count = int(round((hi - lo) / 100.0 * n_total))
        if bi == len(bins) - 1:
            count = int(round(hi / 100.0 * n_total)) - start
        out.append(np.array(order[start:start + count], dtype=np.int64))
        start += count
    return out


def weighted_bin_means(rows, bin_weights: Sequence[np.ndarray],
                       bins=CENTRALITY_BINS):
    """BinResult list from per-bin event weights (fractional or 0/1)."""
    from .scaling import BinResult
    out = []
    for (lo, hi), w in zip(bins, bin_weights):
        w = np.asarray(w, dtype=float)
        wsum = w.sum()
        if wsum <= 0.0:
            out.append(BinResult(f"{lo}-{hi}%", 0, float("nan"),
                                 float("nan"), float("nan")))
            continue
        npart = np.array([r.n_part for r in rows])
        lam = np.array([r.n_lambda for r in rows], dtype=float)
        kaon = np.array([r.n_neutral_kaon for r in rows], dtype=float)
        out.append(BinResult(
            f"{lo}-{hi}%", int(round(wsum)),
            float((w * npart).sum() / wsum),
            float((w * lam).sum() / wsum),
            float((w * kaon).sum() / wsum)))
    return out
