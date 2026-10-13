"""Fourier (harmonic) representation of the azimuthal-partition kernel.

Phase B3-A. Companion to urqmd_agent/analysis/pair_kernel.py: the exact
pair kernel K_w(d) = q_w(d) - P0^2 (P0 = w/(2*pi), d the circular
separation in [0, pi]) admits a cosine series on the circle, so the
observable Delta_sigma^2 decomposes additively over azimuthal harmonics
C_n = <cos(n * dphi)>_pairs.

Analytic derivation
-------------------
For 0 < w <= pi the common-window overlap (pair_kernel.py docstring) is
triangular in d:

    q_w(d) = max(w - d, 0) / (2*pi),        d in [0, pi].

K_w(d) = q_w(d) - P0^2 has zero mean over d in [0, pi]:

    (1/pi) * int_0^pi q_w(d) dd = (1/pi) * w^2/(4*pi) = P0^2,

so its cosine series K_w(d) = sum_{n>=1} a_n cos(n d) (no constant term)
has coefficients

    a_n = (2/pi) int_0^pi K_w(d) cos(n d) dd
        = (2/pi) int_0^w (w - d)/(2*pi) cos(n d) dd
        = (2/pi) * (1 - cos(n w)) / (2*pi*n^2)
        = (2/pi^2) * sin^2(n w/2) / n^2,

using int_0^w (w-d) cos(n d) dd = (1 - cos(n w))/n^2. Hence

    K_w(d) = (2/pi^2) * sum_{n=1}^inf [ sin^2(n w/2) / n^2 ] cos(n d).

For pi < w < 2*pi the exact symmetry K_w(d) = K_{2*pi - w}(d)
(pair_kernel.py) gives the same series, because
sin^2(n (2*pi - w)/2) = sin^2(n*pi - n w/2) = sin^2(n w/2). The
coefficient (2/pi^2) sin^2(n w/2)/n^2 is therefore valid for all
w in (0, 2*pi). Note the w = pi (180 deg) pattern: sin^2(n*pi/2)
vanishes for even n and equals 1 for odd n, so K_pi is carried by odd
harmonics only.

Consequently, with C_n = pair average of cos(n*dphi) over the same
unordered pairs that enter event_delta,

    Delta_sigma^2(event, w) = (2/pi^2) sum_{n=1}^inf
        [ sin^2(n w/2)/n^2 ] C_n.

TRUNCATION CAVEAT (frozen): the series converges like 1/n^2 pointwise
but the kernel is a sharp triangle for small w, so an n = 1..12
truncation does NOT reproduce Delta to high relative precision for
narrow windows; the full-series identity is exact and is verified
numerically at large nmax. Production aggregates in Phase B3-A always
REPORT the n=1..12 reconstruction residual explicitly alongside the
truncated sum; the residual is never claimed to vanish.
"""

from __future__ import annotations

import math
from typing import Dict, Mapping, Sequence

import numpy as np

TWO_PI = 2.0 * math.pi


def harmonic_coeffs(w: float, nmax: int) -> np.ndarray:
    """a_n = (2/pi^2) * sin^2(n w/2)/n^2 for n = 1..nmax (radians)."""
    n = np.arange(1, nmax + 1, dtype=np.float64)
    return (2.0 / math.pi ** 2) * np.sin(n * w / 2.0) ** 2 / n ** 2


def kernel_harmonic(d: np.ndarray, w: float, nmax: int) -> np.ndarray:
    """Truncated cosine-series reconstruction of K_w(d).

    d may be any array of circular separations in [0, pi]; returns the
    partial sum (2/pi^2) sum_{n=1..nmax} sin^2(n w/2)/n^2 cos(n d).
    """
    d = np.asarray(d, dtype=np.float64)
    n = np.arange(1, nmax + 1, dtype=np.float64)
    a = harmonic_coeffs(w, nmax)
    return (a[None, :] * np.cos(d[..., None] * n[None, :])).sum(axis=-1)


def pair_harmonics(phis: Sequence[float], nmax: int = 12) -> Dict[int, float]:
    """C_n = pair average of cos(n * dphi), n = 1..nmax.

    Exact all-pairs average with the pair_kernel normalization
    N*(N-1)/2. cos(n*dphi) is invariant under the circular folding
    d -> 2*pi - d, so the folded separation may be used directly.
    Returns 0.0 for N < 2 (consistent with pair_kernel.event_delta).
    """
    phis = np.asarray(phis, dtype=np.float64)
    n = len(phis)
    out = {k: 0.0 for k in range(1, nmax + 1)}
    if n < 2:
        return out
    iu0, iu1 = np.triu_indices(n, k=1)
    d = np.abs(phis[iu0] - phis[iu1]) % TWO_PI
    d = np.minimum(d, TWO_PI - d)
    n_pairs = n * (n - 1) / 2.0
    for k in range(1, nmax + 1):
        out[k] = float(np.cos(k * d).sum() / n_pairs)
    return out


def pair_harmonic_sums(d: np.ndarray, nmax: int = 12) -> np.ndarray:
    """sum_{pairs} cos(n d) for n = 1..nmax given a folded-separation
    array d (any shape, summed over the last axis). Vectorized helper
    for per-replica ensembles: returns shape (..., nmax)."""
    d = np.asarray(d, dtype=np.float64)
    n = np.arange(1, nmax + 1, dtype=np.float64)
    return np.cos(d[..., None] * n[None, :]).sum(axis=-2)


def delta_from_harmonics(cn: Mapping[int, float], w: float) -> float:
    """Delta(w) = (2/pi^2) sum_n sin^2(n w/2)/n^2 C_n over the keys of
    `cn` (n = 1..nmax truncation as provided)."""
    n = np.array(sorted(cn.keys()), dtype=np.float64)
    c = np.array([cn[int(k)] for k in n], dtype=np.float64)
    a = (2.0 / math.pi ** 2) * np.sin(n * w / 2.0) ** 2 / n ** 2
    return float((a * c).sum())
