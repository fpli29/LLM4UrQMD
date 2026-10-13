"""Deterministic azimuthal-partition proton fluctuation analysis (Delta sigma^2).

Implements the observable of Neff et al., PRC 110, 064905 (2024),
arXiv:2406.00072, for UrQMD 4.0 file13 final states:

    P0 = w / (2*pi)
    sigma2_binomial = N * P0 * (1 - P0)
    Delta_sigma2(N, w) = [ Var(N_w) - sigma2_binomial ] / [ N*(N-1) ]

Frozen conventions (see physics_gate/azimuthal_partition/protocol.md):

- Protons ONLY: ityp=1, iso3=+1 (PDG 2212, source-verified mapping in
  urqmd_agent/particles/properties.py). Anti-protons are NOT included
  (the paper analyzes proton multiplicity, not net-proton).
- Acceptance: |y_cm| < 0.5, 0.4 < pT < 2.0 GeV/c (paper Sec. II).
  Output frame is the NN c.m. frame (betann==0 asserted by the parser).
- Var(N_w) is the variance of the pooled N_w distribution over ALL events
  and ALL partition samples in one fixed-N class (population variance,
  ddof=0), per paper Eq. (1)-(3). A per-event variance averaged afterwards
  is mathematically NOT the same quantity and is not used.
- Partition placement: n_samples orientations psi drawn uniformly from
  [0, 2*pi) with a caller-supplied seed (paper Sec. II.4 defaults to 72
  samples/event). Reproducible: same seed -> identical orientations.
- Weighted average over N: the paper shows "weighted averages" (Fig. 5)
  without specifying the weights numerically. The default here is the
  "pairs" weighting, w_N = n_samples(N) * N * (N-1), i.e. the pooled
  excess-variance estimator; an unweighted ("equal") option is provided
  for sensitivity checks. This choice is FLAGGED as a paper ambiguity in
  protocol.md, not presented as the paper's prescription.
- Elliptic-flow correction (paper Eq. 6): Delta_sigma2_vn =
  2*v_n^2/(pi^2*n^2) * sin^2(n*w/2). v2 is never assumed: it is either
  supplied by the caller or estimated with estimate_v2, which uses the
  TRUE reaction plane Psi_RP = 0 (UrQMD places the impact parameter along
  +x: cascinit.f:268-270, "projectile hits at POSITIVE x"). The paper's v2
  is measured w.r.t. the reconstructed event plane; the difference
  (resolution effects) is flagged in protocol.md.
- Reference multiplicity: ALL final-state charged hadrons (charge != 0,
  source-verified file13 charge field) with |eta| < 0.5 — Phase A2 default,
  the paper's "charged hadrons" definition (Fig. 7 caption). The A1-era
  restricted pi/K/p whitelist is kept as the diagnostic variant
  `refmult_pikp_like` (mode="pikp"). The paper does not itemize species
  (flagged in source_notes.md).
- Statistical uncertainties: EVENT-BLOCK bootstrap (>= 500 replicas,
  seeded); the bootstrap unit is the EVENT carrying its full block of 72
  correlated partition samples — individual N_w entries are never
  resampled.
- Mixed events: OPTIONAL diagnostic only. Ideal model events do not need
  the detector-effect mixed-event correction (paper Sec. II.2, III.2).

All angles are radians internally; degrees are accepted only through the
explicit `unit="deg"` conversion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..final_state.schema import FinalStateEvent, FinalParticle
from ..particles import identify as pid
from ..particles import properties as P

TWO_PI = 2.0 * math.pi

#: frozen proton acceptance (paper Sec. II)
Y_CM_MAX = 0.5
PT_MIN = 0.4          # GeV/c
PT_MAX = 2.0          # GeV/c

#: paper default (Sec. II.4): 72 partition samples per event
DEFAULT_N_SAMPLES = 72

#: reference-multiplicity defaults (paper Fig. 7 caption): |eta| < 0.5
REF_ETA_MAX = 0.5
#: Phase A2 primary centrality estimator: ALL final-state charged hadrons
#: (charge != 0 from the source-verified file13 charge field) at |eta| < 0.5.
REF_MODE_DEFAULT = "all_charged"
#: A1-era restricted diagnostic variant: pi+-, K+-, p, anti-p only.
REF_MODE_PIKP = "pikp"
REF_SPECIES_PIKP = ("pi", "K", "p")
REF_MODES = (REF_MODE_DEFAULT, REF_MODE_PIKP)


def _to_radians(w: float, unit: str) -> float:
    if unit == "rad":
        return float(w)
    if unit == "deg":
        return math.radians(float(w))
    raise ValueError(f"unit must be 'rad' or 'deg', got {unit!r}")


def azimuth(px: float, py: float) -> float:
    """phi = atan2(py, px) folded into [0, 2*pi)."""
    return math.atan2(py, px) % TWO_PI


def pseudorapidity(px: float, py: float, pz: float) -> float:
    """eta = 1/2 ln((|p|+pz)/(|p|-pz)); raises for |p| == |pz| (eta infinite)."""
    pabs = math.sqrt(px * px + py * py + pz * pz)
    if pabs - abs(pz) <= 0.0:
        raise ValueError("pseudorapidity undefined for |p| == |pz|")
    return 0.5 * math.log((pabs + pz) / (pabs - pz))


def _is_proton(p: FinalParticle) -> bool:
    """Proton only (PDG 2212): ityp=1, iso3=+1. Anti-protons excluded."""
    return p.ityp == P.ITYP_NUCLEON and p.iso3 == P.ISO3_PROTON


@dataclass(frozen=True)
class ProtonSelection:
    """Event-level proton selection result."""
    event_id: int
    seed: int
    sqrts: float
    bimp: float
    n_ref: int                 # reference multiplicity (see reference_multiplicity)
    n_proton: int              # accepted protons
    phi: Tuple[float, ...]     # azimuth in [0, 2*pi)
    pt: Tuple[float, ...]
    y: Tuple[float, ...]
    px: Tuple[float, ...]      # kept for validation only
    py: Tuple[float, ...]
    pz: Tuple[float, ...]
    energy: Tuple[float, ...]


def select_protons(ev: FinalStateEvent,
                   y_max: float = Y_CM_MAX,
                   pt_min: float = PT_MIN,
                   pt_max: float = PT_MAX,
                   ref_eta_max: float = REF_ETA_MAX,
                   refmult_mode: str = REF_MODE_DEFAULT
                   ) -> ProtonSelection:
    """Select protons with |y_cm| < y_max and pt_min < pT < pt_max."""
    phi: List[float] = []
    pt: List[float] = []
    y: List[float] = []
    px: List[float] = []
    py: List[float] = []
    pz: List[float] = []
    en: List[float] = []
    for p in ev.particles:
        if not _is_proton(p):
            continue
        y_cm = p.rapidity_cm()
        if abs(y_cm) >= y_max:
            continue
        p_t = math.hypot(p.px, p.py)
        if not (pt_min < p_t < pt_max):
            continue
        phi.append(azimuth(p.px, p.py))
        pt.append(p_t)
        y.append(y_cm)
        px.append(p.px)
        py.append(p.py)
        pz.append(p.pz)
        en.append(p.p0)
    h = ev.header
    return ProtonSelection(
        event_id=h.event, seed=h.ranseed, sqrts=h.sqrts, bimp=h.bimp,
        n_ref=reference_multiplicity(ev, eta_max=ref_eta_max,
                                     mode=refmult_mode),
        n_proton=len(phi),
        phi=tuple(phi), pt=tuple(pt), y=tuple(y),
        px=tuple(px), py=tuple(py), pz=tuple(pz), energy=tuple(en))


def reference_multiplicity(ev: FinalStateEvent,
                           eta_max: float = REF_ETA_MAX,
                           mode: str = REF_MODE_DEFAULT) -> int:
    """Reference multiplicity: charged hadrons with |eta| < eta_max.

    mode="all_charged" (Phase A2 default): EVERY final-state particle with
    charge != 0, using the source-verified file13 charge field (format 213,
    output.f). This is the paper's "charged hadrons" definition (Fig. 7
    caption) at model truth level: the UrQMD cascade final state contains
    only hadrons, so charge != 0 selects exactly the charged hadrons.

    mode="pikp" (diagnostic variant `refmult_pikp_like`): the A1-era
    restricted whitelist pi+-, K+-, p, anti-p. Kept for comparison only;
    NOT the Phase A2 centrality estimator.

    This helper is independent of the old Lambda/K centrality estimator
    (which uses full phase space); it is not reused here.
    """
    if mode not in REF_MODES:
        raise ValueError(f"unknown refmult mode {mode!r}, "
                         f"expected one of {REF_MODES}")
    n = 0
    for p in ev.particles:
        if mode == REF_MODE_DEFAULT:
            if p.charge == 0:
                continue
        else:  # pikp diagnostic whitelist
            if not (pid.is_charged_pion(p.ityp, p.iso3)
                    or pid.is_charged_kaon(p.ityp, p.iso3)
                    or pid.is_proton_or_antiproton(p.ityp, p.iso3)):
                continue
        if abs(pseudorapidity(p.px, p.py, p.pz)) < eta_max:
            n += 1
    return n


def refmult_pikp_like(ev: FinalStateEvent, eta_max: float = REF_ETA_MAX
                      ) -> int:
    """A1-era restricted reference multiplicity (pi/K/p only). Diagnostic."""
    return reference_multiplicity(ev, eta_max=eta_max, mode=REF_MODE_PIKP)


def count_in_partition(phi: Sequence[float], psi: float, w: float,
                       unit: str = "rad") -> int:
    """Number of particles in the half-open partition [psi, psi+w).

    Exact periodic wrapping on [0, 2*pi): a particle is inside iff
    (phi - psi) mod 2*pi < w. phi values outside [0, 2*pi) are folded.
    Boundary convention: lower edge inclusive, upper edge exclusive.
    """
    w_rad = _to_radians(w, unit)
    if not (0.0 < w_rad < TWO_PI):
        raise ValueError(f"partition width must be in (0, 2*pi), got {w_rad}")
    arr = np.asarray(phi, dtype=np.float64)
    rel = np.mod(arr - psi, TWO_PI)
    return int(np.count_nonzero(rel < w_rad))


def partition_orientations(n_samples: int = DEFAULT_N_SAMPLES,
                           seed: int = 0) -> np.ndarray:
    """Deterministic uniform psi samples in [0, 2*pi) from the given seed."""
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1")
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, TWO_PI, size=int(n_samples))


def sample_partition_counts(phi: Sequence[float], w: float,
                            n_samples: int = DEFAULT_N_SAMPLES,
                            seed: int = 0, unit: str = "rad") -> np.ndarray:
    """N_w counts for one event over `n_samples` deterministic orientations."""
    w_rad = _to_radians(w, unit)
    psis = partition_orientations(n_samples, seed)
    arr = np.asarray(phi, dtype=np.float64)
    rel = np.mod(arr[None, :] - psis[:, None], TWO_PI)  # (n_samples, N)
    return np.count_nonzero(rel < w_rad, axis=1).astype(np.int64)


def sigma2_binomial(n: int, w: float, unit: str = "rad") -> float:
    """Binomial baseline N*P0*(1-P0) with P0 = w/(2*pi)."""
    w_rad = _to_radians(w, unit)
    p0 = w_rad / TWO_PI
    return float(n) * p0 * (1.0 - p0)


@dataclass(frozen=True)
class NClassResult:
    """Delta sigma^2 for one fixed-N class at one width w."""
    n: int
    w: float                     # radians
    n_events: int
    n_samples: int               # total N_w entries pooled in this class
    mean_nw: float
    var_nw: float                # population variance (ddof=0)
    sigma2_binomial: float
    delta_sigma2: float          # NaN if invalid (N < 2 or no samples)
    valid: bool
    note: str = ""


def delta_sigma2_class(nw_samples: Sequence[int], n: int, w: float,
                       n_events: int, unit: str = "rad",
                       ddof: int = 0) -> NClassResult:
    """Delta sigma^2 from the pooled N_w samples of one fixed-N class.

    N < 2 is mathematically invalid (normalization N*(N-1)) and returns
    `valid=False` with NaN rather than raising, so aggregation can mark it.
    """
    w_rad = _to_radians(w, unit)
    arr = np.asarray(list(nw_samples), dtype=np.float64)
    base = sigma2_binomial(n, w_rad)
    if n < 2:
        return NClassResult(n=n, w=w_rad, n_events=n_events,
                            n_samples=int(arr.size),
                            mean_nw=float("nan"), var_nw=float("nan"),
                            sigma2_binomial=base, delta_sigma2=float("nan"),
                            valid=False, note="N < 2: invalid")
    if arr.size < 2:
        return NClassResult(n=n, w=w_rad, n_events=n_events,
                            n_samples=int(arr.size),
                            mean_nw=float(arr.mean()) if arr.size else float("nan"),
                            var_nw=float("nan"), sigma2_binomial=base,
                            delta_sigma2=float("nan"), valid=False,
                            note="fewer than 2 samples")
    var = float(arr.var(ddof=ddof))
    delta = (var - base) / (n * (n - 1))
    return NClassResult(n=n, w=w_rad, n_events=n_events,
                        n_samples=int(arr.size), mean_nw=float(arr.mean()),
                        var_nw=var, sigma2_binomial=base,
                        delta_sigma2=delta, valid=True)


def per_event_sample_seed(analysis_seed: int, event_seed: int,
                          event_id: int) -> int:
    """Deterministic per-event psi-sampling seed derived ONLY from
    (analysis_seed, event seed, event_id) via SeedSequence hashing —
    never from physics observables (same rule as analysis/centrality.py)."""
    ss = np.random.SeedSequence([int(analysis_seed), int(event_seed),
                                 int(event_id)])
    return int(np.random.default_rng(ss).integers(0, 2**63 - 1))


def aggregate_by_n(selections: Sequence[ProtonSelection], w: float,
                   n_samples: int = DEFAULT_N_SAMPLES,
                   analysis_seed: int = 0, unit: str = "rad"
                   ) -> Dict[int, NClassResult]:
    """Delta sigma^2(N, w) for every proton-multiplicity class.

    The N_w samples of ALL events with the same N are pooled before the
    variance is taken (paper Eq. 1-3); classes with N < 2 are marked
    invalid and excluded from averaging.
    """
    w_rad = _to_radians(w, unit)
    by_n: Dict[int, List[ProtonSelection]] = {}
    for sel in selections:
        by_n.setdefault(sel.n_proton, []).append(sel)
    out: Dict[int, NClassResult] = {}
    for n in sorted(by_n):
        evs = by_n[n]
        if n < 2:
            out[n] = delta_sigma2_class([], n, w_rad, len(evs))
            continue
        counts: List[int] = []
        for sel in evs:
            seed = per_event_sample_seed(analysis_seed, sel.seed,
                                         sel.event_id)
            counts.extend(sample_partition_counts(sel.phi, w_rad,
                                                  n_samples, seed).tolist())
        out[n] = delta_sigma2_class(counts, n, w_rad, len(evs))
    return out


def average_delta_sigma2(class_results: Dict[int, NClassResult],
                         weighting: str = "pairs") -> Tuple[float, float]:
    """<Delta sigma^2> averaged over valid N classes.

    weighting="pairs" (default): w_N = n_samples * N * (N-1); this is the
    pooled estimator sum_C n_C*(var_C - base_C) / sum_C n_C*N_C*(N_C-1).
    weighting="equal": unweighted mean over classes.

    NOTE: the paper (Fig. 5) shows "weighted averages" without specifying
    the weights; "pairs" is our documented choice, not the paper's
    prescription. Returns (value, total_weight_or_nan).
    """
    valid = [r for r in class_results.values() if r.valid]
    if not valid:
        return float("nan"), float("nan")
    if weighting == "pairs":
        num = sum(r.n_samples * (r.var_nw - r.sigma2_binomial) for r in valid)
        den = sum(r.n_samples * r.n * (r.n - 1) for r in valid)
        return num / den, float(den)
    if weighting == "equal":
        return (sum(r.delta_sigma2 for r in valid) / len(valid),
                float(len(valid)))
    raise ValueError(f"unknown weighting {weighting!r}")


def delta_sigma2_vn(vn: float, w: float, n: int = 2,
                    unit: str = "rad") -> float:
    """Analytic v_n contribution, paper Eq. (6):
    2*v_n^2/(pi^2*n^2) * sin^2(n*w/2). Vanishes at w = pi for n=2."""
    w_rad = _to_radians(w, unit)
    return 2.0 * vn * vn / (math.pi ** 2 * n * n) * math.sin(n * w_rad / 2.0) ** 2


def estimate_v2(selections: Sequence[ProtonSelection]) -> float:
    """v2 = <cos(2*phi)> pooled over all accepted protons, w.r.t. the TRUE
    reaction plane Psi_RP = 0 (impact parameter along +x,
    cascinit.f:268-270). Deterministic; no v2 value is ever assumed."""
    cos2: List[float] = []
    for sel in selections:
        for ph in sel.phi:
            cos2.append(math.cos(2.0 * ph))
    if not cos2:
        raise ValueError("no accepted protons in sample")
    return float(np.mean(cos2))


def flow_corrected(result: NClassResult, v2: float, n: int = 2
                   ) -> Tuple[float, float, float]:
    """Return (raw, v_n contribution, flow-corrected) for a class result."""
    raw = result.delta_sigma2
    dv = delta_sigma2_vn(v2, result.w, n)
    return raw, dv, raw - dv


def mixed_event_phis(event_phis: Sequence[Sequence[float]],
                     mix_index_offset: int = 1
                     ) -> List[np.ndarray]:
    """OPTIONAL mixed-event diagnostic (paper Sec. II.2).

    Given the per-event phi lists of one fixed-N class (all length N),
    build M mixed events (M = number of same events): mixed event k takes
    its j-th proton azimuth from same event (k + j*mix_index_offset) mod M.
    Deterministic, no RNG. Requires >= 2 events per class to mix across.
    """
    m = len(event_phis)
    if m < 2:
        raise ValueError("need >= 2 events in a class to build mixed events")
    n = len(event_phis[0])
    if any(len(e) != n for e in event_phis):
        raise ValueError("mixed-event construction requires a fixed-N class")
    arrs = [np.asarray(e, dtype=np.float64) for e in event_phis]
    mixed = []
    for k in range(m):
        mixed.append(np.array([arrs[(k + j * mix_index_offset) % m][j]
                               for j in range(n)]))
    return mixed


# --- event-block bootstrap (Phase A2) ---------------------------------------

@dataclass(frozen=True)
class EventBlock:
    """One event's correlated block of N_w partition samples."""
    event_id: int
    seed: int
    n_proton: int
    counts: np.ndarray           # shape (n_samples,), dtype int64


def build_event_blocks(selections: Sequence[ProtonSelection], w: float,
                       n_samples: int = DEFAULT_N_SAMPLES,
                       analysis_seed: int = 0, unit: str = "rad"
                       ) -> List[EventBlock]:
    """Precompute each event's full block of N_w samples (deterministic).

    The per-event psi orientations are drawn ONCE from the deterministic
    seed (analysis_seed, event seed, event_id); the bootstrap below
    resamples whole blocks, never individual N_w entries.
    """
    w_rad = _to_radians(w, unit)
    blocks: List[EventBlock] = []
    for sel in selections:
        seed = per_event_sample_seed(analysis_seed, sel.seed, sel.event_id)
        counts = sample_partition_counts(sel.phi, w_rad, n_samples, seed)
        blocks.append(EventBlock(event_id=sel.event_id, seed=sel.seed,
                                 n_proton=sel.n_proton, counts=counts))
    return blocks


def _class_delta(counts_pool: np.ndarray, n: int, w_rad: float) -> float:
    """Delta sigma^2 for one pooled N_w array of class n (NaN if invalid)."""
    if n < 2 or counts_pool.size < 2:
        return float("nan")
    var = float(counts_pool.var(ddof=0))
    return (var - sigma2_binomial(n, w_rad)) / (n * (n - 1))


def _replica_averages(deltas: Dict[int, float],
                      pairs_den: Dict[int, float],
                      invvar_w: Dict[int, float] | None = None
                      ) -> Dict[str, float]:
    """N-averaged Delta sigma^2 for one replica, three weightings."""
    valid = {n: d for n, d in deltas.items() if not math.isnan(d)}
    out = {"equal": float("nan"), "pairs": float("nan"),
           "invvar": float("nan")}
    if not valid:
        return out
    out["equal"] = float(np.mean(list(valid.values())))
    num = sum((deltas[n] * pairs_den[n]) for n in valid)
    den = sum(pairs_den[n] for n in valid)
    out["pairs"] = num / den if den > 0 else float("nan")
    if invvar_w is not None:
        sw = sum(invvar_w[n] for n in valid)
        if sw > 0:
            out["invvar"] = sum(invvar_w[n] * d
                                for n, d in valid.items()) / sw
    return out


def bootstrap_delta_sigma2(blocks: Sequence[EventBlock], w: float,
                           n_bootstrap: int = 500, seed: int = 0,
                           unit: str = "rad",
                           return_indices: bool = False) -> dict:
    """EVENT-BLOCK bootstrap of Delta sigma^2(N, w) and N-averages.

    Each replica resamples EVENTS with replacement (all events of the input
    sample); every selected event contributes its ENTIRE precomputed block
    of partition samples. Fixed-N classes are rebuilt per replica, so class
    occupancies fluctuate as they would in a real resampling. No individual
    N_w entry is ever resampled independently.

    Returns dict with:
      "by_n":   {n: np.ndarray (n_bootstrap,) of replica Delta sigma^2}
      "avg":    {weighting: np.ndarray (n_bootstrap,)} for
                "equal", "pairs", "invvar" (fixed inverse-bootstrap-variance
                weights, documented in protocol.md)
      "indices": (only if return_indices) np.ndarray (n_bootstrap, M) of the
                resampled event indices — exposes the block structure for
                tests.
    """
    w_rad = _to_radians(w, unit)
    blocks = list(blocks)
    m = len(blocks)
    if m == 0:
        raise ValueError("empty event sample")
    rng = np.random.default_rng(seed)
    idx_all = rng.integers(0, m, size=(int(n_bootstrap), m))

    ns = sorted({b.n_proton for b in blocks if b.n_proton >= 2})
    counts_by_n = {n: [b.counts for b in blocks if b.n_proton == n]
                   for n in ns}
    n_of = np.array([b.n_proton for b in blocks])

    # pairs-weight denominators per replica depend on class occupancy;
    # n*(n-1)*n_samples per selected event of class n.
    pair_unit = {n: n * (n - 1) * blocks[0].counts.size for n in ns}

    rep_by_n: Dict[int, List[float]] = {n: [] for n in ns}
    rep_avg: Dict[str, List[float]] = {"equal": [], "pairs": [], "invvar": []}
    for rep in range(int(n_bootstrap)):
        sel_idx = idx_all[rep]
        deltas: Dict[int, float] = {}
        den: Dict[int, float] = {}
        for n in ns:
            take = sel_idx[n_of[sel_idx] == n]
            if take.size == 0:
                deltas[n] = float("nan")
                continue
            pool = np.concatenate([blocks[i].counts for i in take])
            deltas[n] = _class_delta(pool, n, w_rad)
            den[n] = pair_unit[n] * take.size
        for n in ns:
            rep_by_n[n].append(deltas.get(n, float("nan")))
        avgs = _replica_averages(deltas, den)
        for k in rep_avg:
            rep_avg[k].append(avgs[k])

    by_n = {n: np.array(v) for n, v in rep_by_n.items()}
    # inverse-variance weights: fixed at 1/bootstrap-variance per class
    invvar_w = {}
    for n in ns:
        v = np.nanvar(by_n[n], ddof=1)
        if np.isfinite(v) and v > 0:
            invvar_w[n] = 1.0 / v
    if invvar_w:
        inv = []
        for rep in range(int(n_bootstrap)):
            vals = {n: rep_by_n[n][rep] for n in invvar_w}
            vals = {n: d for n, d in vals.items() if not math.isnan(d)}
            if vals:
                sw = sum(invvar_w[n] for n in vals)
                inv.append(sum(invvar_w[n] * d for n, d in vals.items()) / sw)
            else:
                inv.append(float("nan"))
        rep_avg["invvar"] = inv

    out = {"by_n": by_n,
           "avg": {k: np.array(v) for k, v in rep_avg.items()},
           "n_bootstrap": int(n_bootstrap), "seed": int(seed)}
    if return_indices:
        out["indices"] = idx_all
    return out


def bootstrap_summary(replicas: np.ndarray) -> Tuple[float, float, float]:
    """(median, 16th, 84th percentile) of a replica array (NaNs ignored)."""
    arr = np.asarray(replicas, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    med, p16, p84 = np.percentile(arr, [50.0, 16.0, 84.0])
    return float(med), float(p16), float(p84)
