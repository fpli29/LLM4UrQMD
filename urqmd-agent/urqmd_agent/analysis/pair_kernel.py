"""Exact pair kernel for the azimuthal-partition observable (Delta sigma^2).

Phase B1 (microscopic attribution). This module gives the EXACT,
sampling-free per-event value of the same observable implemented in
urqmd_agent/analysis/azimuthal_partition.py (Neff et al., PRC 110, 064905
(2024)):

    P0 = w / (2*pi)
    Delta_sigma2(N, w) = [ Var(N_w) - N*P0*(1-P0) ] / [ N*(N-1) ]

and decomposes it additively over unordered proton pairs so that the
contributions of microscopically classified pair categories sum EXACTLY to
the event value.

Derivation of the pair kernel
-----------------------------

Place a window W_psi = [psi, psi+w) (mod 2*pi) with psi uniform on
[0, 2*pi). For one event with N protons at azimuths phi_i,

    N_w = sum_i 1[phi_i in W_psi]

so  E_psi[N_w]     = N * P0
    E_psi[N_w^2]   = sum_i P(psi covers i) + sum_{i != j} P(psi covers i and j)
                   = N*P0 + 2 * sum_{i<j} q_w(d_ij)

where d_ij = min(|phi_i-phi_j|, 2*pi-|phi_i-phi_j|) in [0, pi] is the
circular separation and q_w(d) is the probability that BOTH particles fall
in some common window of width w over uniform window placement:

  * 0 <= w <= pi: psi must start early enough to cover the shorter arc of
    length d joining the two points, and may start anywhere in an interval
    of length w-d (zero if d > w):

        q_w(d) = max(w - d, 0) / (2*pi)

  * pi < w <= 2*pi: write the window as the complement of a gap G of width
    ell = 2*pi - w (< pi). Both particles are inside the window iff NEITHER
    is inside G. With P(i in G) = ell/(2*pi) and P(both in G) =
    max(ell - d, 0)/(2*pi) (the ell <= pi case above applied to the gap),
    inclusion-exclusion gives

        q_w(d) = 1 - [ 2*ell - max(ell - d, 0) ] / (2*pi)

Then, with Var_psi(N_w) = E[N_w^2] - E[N_w]^2,

    Var_psi(N_w) - N*P0*(1-P0)
        = N*P0 + 2*sum_{i<j} q_w(d_ij) - N^2*P0^2 - N*P0 + N*P0^2
        = 2*sum_{i<j} [ q_w(d_ij) - P0^2 ]

so the EXACT event value is

    Delta_sigma2(event, w) = 2 * sum_{i<j} K_w(d_ij) / [N*(N-1)],
    K_w(d) = q_w(d) - P0^2.

This is the infinite-orientation limit of the 72-sample partition
estimator of azimuthal_partition.py (population variance over sampled
orientations converges to Var_psi); the finite-72 estimator differs only
by orientation-sampling noise.

Exact w <-> 2*pi - w symmetry
-----------------------------

For w > pi with ell = 2*pi - w:

    q_w(d) - q_{2*pi - w}(d)
        = (1 - [2*ell - max(ell-d,0)]/(2*pi)) - max(2*pi - ell - d, 0)/(2*pi)
        = 1 - 2*ell/(2*pi) = 1 - 2*(2*pi - w)/(2*pi) = 2*P0 - 1

and  P0^2 - (1-P0)^2 = 2*P0 - 1, hence

    K_w(d) = K_{2*pi - w}(d)   identically, for every d in [0, pi].

Additive decomposition
----------------------

For ANY partition of the unordered pairs into disjoint classes c with
pair counts n_c (sum_c n_c = N*(N-1)/2),

    Delta_total = sum_c F_c * Delta_c,
    F_c     = n_c / (N*(N-1)/2),
    Delta_c = (1/n_c) * sum_{(i<j) in c} 2*K_w(d_ij) / [N*(N-1)] / F_c
            = sum over class pairs of the per-pair contribution, divided by F_c,

i.e. with per-pair contribution x_ij = 2*K_w(d_ij)/[N*(N-1)] one has
Delta_c = (sum_{c} x_ij) / F_c and the identity closes by construction to
machine precision: sum_c F_c*Delta_c = sum_c sum_{ij in c} x_ij =
sum_{all ij} x_ij = Delta_total. Classes with n_c = 0 carry F_c = 0 and
contribute exactly 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Hashable, Iterable, List, Sequence, Tuple

TWO_PI = 2.0 * math.pi


def circular_separation(phi1: float, phi2: float) -> float:
    """d = min(|dphi|, 2*pi - |dphi|) in [0, pi]."""
    d = abs(phi1 - phi2) % TWO_PI
    return min(d, TWO_PI - d)


def q_common_window(d: float, w: float) -> float:
    """q_w(d): probability that two particles at circular separation d both
    fall inside a uniformly placed window of width w (see module docstring)."""
    if not (0.0 < w < TWO_PI):
        raise ValueError(f"w must be in (0, 2*pi), got {w}")
    if not (0.0 <= d <= math.pi + 1e-12):
        raise ValueError(f"d must be in [0, pi], got {d}")
    if w <= math.pi:
        return max(w - d, 0.0) / TWO_PI
    ell = TWO_PI - w
    return 1.0 - (2.0 * ell - max(ell - d, 0.0)) / TWO_PI


def kernel(d: float, w: float) -> float:
    """K_w(d) = q_w(d) - P0^2 with P0 = w/(2*pi)."""
    p0 = w / TWO_PI
    return q_common_window(d, w) - p0 * p0


def event_delta(phis: Sequence[float], w: float) -> float:
    """Exact per-event Delta_sigma^2 at width w (radians).

    Returns 0.0 for N < 2 (no pairs; the class is invalid in the pooled
    estimator, and an empty pair sum is the consistent convention here).
    """
    n = len(phis)
    if n < 2:
        return 0.0
    s = 0.0
    for i in range(n):
        pi_ = phis[i]
        for j in range(i + 1, n):
            s += kernel(circular_separation(pi_, phis[j]), w)
    return 2.0 * s / (n * (n - 1))


@dataclass(frozen=True)
class ClassContribution:
    """Additive contribution of one pair class (see module docstring)."""
    cls: Hashable
    n_pairs: int
    frac_pairs: float          # F_c
    delta: float               # Delta_c (0.0 if n_pairs == 0)
    contribution: float        # F_c * Delta_c (exact share of Delta_total)


def decompose_pairs(phis: Sequence[float], pair_classes: Sequence[Hashable],
                    w: float) -> Tuple[float, Dict[Hashable, ClassContribution]]:
    """Exact event Delta_sigma^2 plus its additive pair-class decomposition.

    `pair_classes` must have one label per unordered pair, ordered as
    (0,1), (0,2), ..., (0,N-1), (1,2), ..., (N-2,N-1) — the same order
    `pair_indices` yields. Returns (delta_total, {cls: ClassContribution}).
    The closure sum_c F_c*Delta_c == delta_total holds to machine precision.
    """
    n = len(phis)
    n_pairs = n * (n - 1) // 2
    if n < 2:
        if pair_classes:
            raise ValueError("pair_classes given but N < 2")
        return 0.0, {}
    if len(pair_classes) != n_pairs:
        raise ValueError(
            f"expected {n_pairs} pair labels, got {len(pair_classes)}")
    sums: Dict[Hashable, float] = {}
    counts: Dict[Hashable, int] = {}
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            x = 2.0 * kernel(circular_separation(phis[i], phis[j]), w) \
                / (n * (n - 1))
            c = pair_classes[k]
            sums[c] = sums.get(c, 0.0) + x
            counts[c] = counts.get(c, 0) + 1
            k += 1
    out: Dict[Hashable, ClassContribution] = {}
    total = 0.0
    for c in sorted(counts, key=repr):
        frac = counts[c] / n_pairs
        delta = sums[c] / frac          # per-class mean pair contribution / F_c
        out[c] = ClassContribution(cls=c, n_pairs=counts[c], frac_pairs=frac,
                                   delta=delta, contribution=sums[c])
        total += sums[c]
    return total, out


def pair_indices(n: int) -> List[Tuple[int, int]]:
    """Unordered pair index list in the canonical order used everywhere here."""
    return [(i, j) for i in range(n) for j in range(i + 1, n)]
