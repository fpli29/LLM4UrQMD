"""Phase B2-B analysis-level counterfactuals on the frozen B1 events.

Implements the frozen rules of physics_gate/phaseB2/protocol.md
("B2-B rules") — no UrQMD runs, no new events, no modification of any
frozen A/B1 output:

- MOMENTUM_PRESERVING_PSEUDO_PROTONS: pool = charged final-state hadrons
  with |y| < 0.5, 0.4 < pT < 2.0 GeV/c excluding the real accepted
  protons; POOL_FALLBACK (include the real protons, flag the event) when
  the pool is smaller than Np. Exactly Np pseudo-protons per event are
  drawn without replacement, phi-blind (selection never looks at phi),
  stratified in the FROZEN pT bins {0.4,0.6,0.8,1.0,1.2,1.6,2.0}:
  take[b] = min(real_count[b], available[b]); each deficit slot is
  filled from the nearest pT bin with remaining candidates, lower
  neighbor first then higher (events with any such relaxation are
  flagged STRAT_RELAXED). R = 500 replicas per event, per-(event,
  replica) seeds SeedSequence([20261102, event_ordinal, replica]).
  Convergence reported at R = 100/250/500.

- EVENT_MIXED_COUNTERFACTUAL: per (centrality class, Np) cell with
  M >= 2 events, mixed event k takes accepted-proton momentum j of
  physical event (k + j) mod M (the B1 deterministic offset rule,
  azimuthal_partition.mixed_event_phis applied to momenta). Cells with
  M < 2 cannot draw from OTHER events at the same (class, Np) and are
  EXCLUDED from the mixed sample and counted (no relaxation invented —
  the B1 construction has the same M >= 2 requirement). Same-source
  pairs are unavoidable exactly when M < Np (pigeonhole); their
  fraction is computed exactly and reported, never fabricated as zero.

- HISTORY_LABEL_PERMUTATION: real accepted-proton momenta fixed; the B1
  history descriptors are permuted within (centrality, Np) cells; 500
  permutations, per-(permutation, cell) seeds
  SeedSequence([20261103, permutation, cell]); total Delta is bitwise
  unchanged (per-event pair-kernel sums are computed once from the
  fixed momenta and only re-summed by category).

Comparison bootstrap: event-block, ordinary with-replacement, 500
replicas, streams SeedSequence([20261101, tag]) with tags enumerated in
fixed order (the protocol's seed 20261101).

The exact pair kernel is reused from urqmd_agent.analysis.pair_kernel;
the vectorized replica path below is algebraically identical (verified
against pk.event_delta in the B2 tests).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .analysis import pair_kernel as pk

TWO_PI = 2.0 * math.pi

#: frozen acceptance (identical to the B1 accepted-proton acceptance)
Y_MAX = 0.5
PT_MIN = 0.4
PT_MAX = 2.0

#: frozen stratification bins (protocol, "B2-B rules")
PT_BIN_EDGES = (0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0)
N_PT_BINS = len(PT_BIN_EDGES) - 1

#: frozen seeds / replica counts (protocol)
PSEUDO_SEED_ROOT = 20261102
PERM_SEED_ROOT = 20261103
BOOT_SEED = 20261101
R_REPLICAS = 500
N_BOOT = 500
CONV_CHECKPOINTS = (100, 250, 500)

N_DPHI_BINS = 18
DPHI_EDGES = np.linspace(0.0, math.pi, N_DPHI_BINS + 1)
#: away/near split at pi/2 (bin 9), as in B1
NEAR_BINS = slice(0, 9)
AWAY_BINS = slice(9, 18)

W_DEG_LIST = (60, 90, 120, 180)
W_LIST = tuple(math.radians(w) for w in W_DEG_LIST)
W_PRIMARY_IDX = W_DEG_LIST.index(120)


# ----------------------------------------------------------------------
# pT binning + pool
# ----------------------------------------------------------------------

def pt_bin_index(pt: float) -> int:
    """Frozen bin of one pT value: [0.4,0.6), ..., [1.2,1.6), [1.6,2.0).

    Returns -1 outside the acceptance (0.4, 2.0) — inputs are
    pre-filtered, so this is a guard, not a selection rule. Edge values
    belong to the upper bin (measure zero; convention fixed here)."""
    if not (PT_MIN < pt < PT_MAX):
        return -1
    for b in range(N_PT_BINS):
        if pt < PT_BIN_EDGES[b + 1]:
            return b
    return N_PT_BINS - 1  # pt == PT_MAX guard (unreachable for strict <)


def build_pool(charge: np.ndarray, y: np.ndarray, pt: np.ndarray,
               proton_uids: Sequence[int], uid: np.ndarray):
    """Eligible-pool mask (protocol B2-B rules).

    Pool = charged final-state hadrons (charge != 0; the UrQMD cascade
    final state contains only hadrons) with |y| < 0.5 and
    0.4 < pT < 2.0, EXCLUDING the real accepted protons. Returns the
    boolean mask over the particle array plus the fallback flag:
    fallback=True means len(pool) < Np and the real protons must be
    added to the pool (event flagged POOL_FALLBACK)."""
    mask = ((charge != 0) & (np.abs(y) < Y_MAX)
            & (pt > PT_MIN) & (pt < PT_MAX))
    if len(proton_uids):
        pset = set(int(u) for u in proton_uids)
        excl = np.array([int(u) in pset for u in uid])
        mask = mask & ~excl
    return mask


def bin_count_vector(pt: np.ndarray) -> np.ndarray:
    """Count per frozen pT bin for one momentum array."""
    out = np.zeros(N_PT_BINS, dtype=np.int64)
    for v in pt:
        b = pt_bin_index(float(v))
        if b >= 0:
            out[b] += 1
    return out


# ----------------------------------------------------------------------
# stratified selection (phi-blind)
# ----------------------------------------------------------------------

def stratified_take(real_counts: np.ndarray, avail_counts: np.ndarray
                    ) -> Tuple[np.ndarray, int, List[Tuple[int, int]]]:
    """Frozen stratified-matching rule.

    take[b] = min(real[b], avail[b]); each deficit slot of a bin b is
    filled from the nearest bin with remaining candidates, lower
    neighbor first, then higher (distance ascending). Returns
    (take, n_relaxed_slots, relaxations) where relaxations lists
    (deficit_bin, donor_bin) per relaxed slot in the order applied
    (deterministic: deficit bins processed in frozen bin order)."""
    take = np.minimum(real_counts, avail_counts).astype(np.int64)
    remaining = (avail_counts - take).astype(np.int64)
    relaxations: List[Tuple[int, int]] = []
    for b in range(N_PT_BINS):
        deficit = int(real_counts[b] - take[b])
        for _ in range(deficit):
            placed = False
            for dist in range(1, N_PT_BINS):
                for cand in (b - dist, b + dist):  # lower neighbor first
                    if 0 <= cand < N_PT_BINS and remaining[cand] > 0:
                        take[cand] += 1
                        remaining[cand] -= 1
                        relaxations.append((b, cand))
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                raise ValueError(
                    "stratified_take: cannot fill deficit — total "
                    "available < Np (POOL_FALLBACK must be applied first)")
    return take, len(relaxations), relaxations


def pseudo_seed(event_ordinal: int, replica: int) -> np.random.SeedSequence:
    """Frozen per-(event, replica) seed."""
    return np.random.SeedSequence(
        [PSEUDO_SEED_ROOT, int(event_ordinal), int(replica)])


def select_within_bins(rng: np.random.Generator,
                       cand_lists: Sequence[Sequence[int]],
                       take: np.ndarray) -> np.ndarray:
    """Uniform without-replacement selection of take[b] candidates from
    each bin's candidate list, in frozen bin order. phi is never
    consulted (phi-blind by construction)."""
    parts = []
    for b, cands in enumerate(cand_lists):
        t = int(take[b])
        if t > 0:
            parts.append(rng.choice(len(cands), size=t, replace=False))
    if not parts:
        return np.empty(0, dtype=np.int64)
    pos = np.concatenate(parts)
    # map bin-local positions back to pool positions
    out = np.empty(pos.size, dtype=np.int64)
    k = 0
    for b, cands in enumerate(cand_lists):
        t = int(take[b])
        if t > 0:
            cidx = np.asarray(cands, dtype=np.int64)
            out[k:k + t] = cidx[pos[k:k + t]]
            k += t
    return out


# ----------------------------------------------------------------------
# vectorized pair-kernel quantities (replica path)
# ----------------------------------------------------------------------

def pair_d_matrix(phis: np.ndarray) -> np.ndarray:
    """(R, N) or (N,) phi array -> folded pair separations.

    Returns (d, iu0, iu1) with d shape (..., P), P = N(N-1)/2."""
    arr = np.asarray(phis, dtype=np.float64)
    n = arr.shape[-1]
    iu0, iu1 = np.triu_indices(n, k=1)
    d = np.abs(arr[..., iu0] - arr[..., iu1]) % TWO_PI
    return np.minimum(d, TWO_PI - d), iu0, iu1


def sum2K_from_d(d: np.ndarray, w: float) -> np.ndarray:
    """sum_{i<j} 2*K_w(d_ij) along the last axis (exact kernel, w <= pi).

    Algebraically identical to 2*sum pk.kernel(d, w): for w <= pi,
    q_w(d) = max(w - d, 0)/(2*pi), so sum 2K = sum max(w-d,0)/pi
    - 2*P*P0^2 with P0 = w/(2*pi)."""
    p = d.shape[-1]
    p0 = w / TWO_PI
    return np.maximum(w - d, 0.0).sum(axis=-1) / math.pi - 2.0 * p * p0 * p0


def dphi_bin_index(d: np.ndarray) -> np.ndarray:
    return np.minimum((d / math.pi * N_DPHI_BINS).astype(np.int64),
                      N_DPHI_BINS - 1)


def replica_quantities(phi_sel: np.ndarray, w_list: Sequence[float],
                       checkpoints: Sequence[int] = CONV_CHECKPOINTS):
    """All per-event replica quantities in one pass.

    phi_sel: (R, Np) selected pseudo-proton azimuths. Returns dict with
    cum2K: (n_checkpoints, n_w) cumulative sum over replicas of
    sum_{i<j} 2K at each checkpoint; sum2K_total: (n_w,); hist_sum:
    (18,) pair-dphi counts summed over replicas; ksum_sum: (n_w, 18)
    sum 2K per dphi bin summed over replicas."""
    r, n = phi_sel.shape
    d, _, _ = pair_d_matrix(phi_sel)                    # (R, P)
    bins = dphi_bin_index(d)                            # (R, P)
    r_off = (np.arange(r)[:, None] * N_DPHI_BINS)
    hist_sum = np.bincount((bins + r_off).ravel(),
                           minlength=r * N_DPHI_BINS).reshape(
                               r, N_DPHI_BINS).sum(axis=0)
    cums = []
    totals = []
    ks = []
    for w in w_list:
        p0 = w / TWO_PI
        q = np.maximum(w - d, 0.0) / math.pi            # 2*q_w(d) per pair
        s = q.sum(axis=-1) - 2.0 * d.shape[-1] * p0 * p0  # per-replica sum 2K
        c = np.cumsum(s)
        cums.append([c[cp - 1] for cp in checkpoints])
        totals.append(c[-1])
        w2k = q - 2.0 * p0 * p0                          # 2*K_w(d) per pair
        ks.append(np.bincount((bins + r_off).ravel(),
                              weights=w2k.ravel(),
                              minlength=r * N_DPHI_BINS).reshape(
                                  r, N_DPHI_BINS).sum(axis=0))
    return {
        "cum2K": np.array(cums).T,                       # (n_cp, n_w)
        "sum2K_total": np.array(totals),                 # (n_w,)
        "hist_sum": hist_sum.astype(np.float64),
        "ksum_sum": np.array(ks),                        # (n_w, 18)
    }


# ----------------------------------------------------------------------
# event-mixed construction (B1 offset rule on momenta)
# ----------------------------------------------------------------------

def mixed_source_indices(m: int, n: int, offset: int = 1) -> np.ndarray:
    """(M, N) source-event index matrix: mixed event k takes slot j from
    physical event (k + j*offset) mod M — the B1 offset rule
    (azimuthal_partition.mixed_event_phis) applied to momenta."""
    rows = (np.arange(m)[:, None] + offset * np.arange(n)[None, :]) % m
    return rows.astype(np.int64)


def count_same_source_pairs(m: int, n: int, offset: int = 1) -> int:
    """Per mixed event, number of pairs (j1 < j2) whose two slots come
    from the SAME physical event. Zero when M >= N (offset 1);
    unavoidable by pigeonhole when M < N — quantified, never hidden."""
    iu0, iu1 = np.triu_indices(n, k=1)
    src = mixed_source_indices(m, n, offset)
    return int(np.count_nonzero(src[0, iu0] == src[0, iu1]))


# ----------------------------------------------------------------------
# permutation machinery (history labels within (centrality, Np) cells)
# ----------------------------------------------------------------------

def perm_seed(permutation: int, cell: int) -> np.random.SeedSequence:
    """Frozen per-(permutation, cell) seed (root 20261103)."""
    return np.random.SeedSequence(
        [PERM_SEED_ROOT, int(permutation), int(cell)])


def axis_b_pair_codes(ps: np.ndarray, iu0, iu1) -> np.ndarray:
    """ps (..., N) 0/1 post-scatter flags -> codes 0 NEITHER / 1 ONE /
    2 BOTH per pair."""
    return ps[..., iu0] + ps[..., iu1]


def axis_d_pair_codes(pb: np.ndarray, iu0, iu1) -> np.ndarray:
    """pb (..., N) per-proton post-scatter bins {0,1,2,3} -> sorted pair
    code lo*4+hi (lo <= hi)."""
    a = pb[..., iu0]
    b = pb[..., iu1]
    lo = np.minimum(a, b)
    hi = np.maximum(a, b)
    return lo * 4 + hi


def axis_c_pair_codes(fc: np.ndarray, iu0, iu1) -> np.ndarray:
    """fc (..., N) formation-class codes (< 8) -> sorted pair code
    lo*8+hi (lo <= hi)."""
    a = fc[..., iu0]
    b = fc[..., iu1]
    lo = np.minimum(a, b)
    hi = np.maximum(a, b)
    return lo * 8 + hi


def axis_a_pair_codes(fctag: np.ndarray,
                      incoming: Sequence[Tuple[int, ...]],
                      pair_index: np.ndarray) -> np.ndarray:
    """Axis A codes for ONE event under one label assignment.

    fctag: (N,) formation ctags (-1 = INITIAL_CARRIED);
    incoming: per-slot tuple of incoming physical ctags;
    pair_index: (N, N) matrix with pair_index[i, j] = flat pair index
    (i < j), -1 elsewhere. Codes: 0 NO_DIRECT_SHARED_INTERACTION,
    1 DIRECT_COLLISION_PARTNERS, 2 SAME_PRODUCTION_INTERACTION.
    Same semantics as proton_history.pair_axis_a."""
    n = len(fctag)
    codes = np.zeros(n * (n - 1) // 2, dtype=np.int64)
    groups: Dict[int, List[int]] = defaultdict(list)
    for s, tags in enumerate(incoming):
        for c in tags:
            groups[c].append(s)
    for c, slots in groups.items():
        for x in range(len(slots)):
            sx = slots[x]
            for y in range(x + 1, len(slots)):
                sy = slots[y]
                if c > max(fctag[sx], fctag[sy]):
                    i, j = (sx, sy) if sx < sy else (sy, sx)
                    codes[pair_index[i, j]] = 1
    iu0, iu1 = np.triu_indices(n, k=1)
    same = (fctag[iu0] == fctag[iu1]) & (fctag[iu0] >= 0)
    codes[same] = 2
    return codes


def pair_index_matrix(n: int) -> np.ndarray:
    """(N, N) matrix: [i, j] -> flat upper-triangle pair index, -1 else."""
    out = np.full((n, n), -1, dtype=np.int64)
    iu0, iu1 = np.triu_indices(n, k=1)
    out[iu0, iu1] = np.arange(len(iu0))
    return out


# ----------------------------------------------------------------------
# comparison bootstrap (protocol seed 20261101)
# ----------------------------------------------------------------------

def boot_replicas(stat_fn, n_events: int, tag: int) -> np.ndarray:
    """Event-block bootstrap, ordinary with-replacement over the events
    of one aggregation set, N_BOOT replicas, stream
    SeedSequence([20261101, tag])."""
    rng = np.random.default_rng(np.random.SeedSequence([BOOT_SEED,
                                                        int(tag)]))
    reps = np.empty(N_BOOT)
    for r in range(N_BOOT):
        reps[r] = stat_fn(rng.integers(0, n_events, size=n_events))
    return reps


def boot_sd(stat_fn, n_events: int, tag: int) -> float:
    return float(np.std(boot_replicas(stat_fn, n_events, tag), ddof=1))
