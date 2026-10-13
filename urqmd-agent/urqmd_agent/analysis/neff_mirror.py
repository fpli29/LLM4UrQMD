"""Phase A5.5 Neff-thesis exact-method mirror: pure numerical helpers.

Implements the thesis-mirror definitions (Dylan Neff, UCLA 2023) on top of
the frozen azimuthal-partition machinery:

- Variance estimator: Fisher k2, the unbiased sample variance (ddof=1)
  over the pooled partition counts,
      k2 = sum_i (x_i - x_mean)^2 / (M - 1),   M >= 2,
  computed from sufficient statistics s1 = sum(x), s2 = sum(x^2).
      Delta_sigma2(N, w) = [k2 - N P0 (1-P0)] / [N (N-1)],  P0 = w/(2 pi).
- Poisson EVENT-block bootstrap: each replica assigns one weight
  r_e ~ Poisson(1) to every event; ALL partition samples of an event share
  that weight (blocks are never split). A replica is invalid when the total
  weighted number of pooled entries M_b < 2 (k2 undefined) and is masked.
- Inverse-variance N-averaging with per-N bootstrap standard deviations;
  bins with undefined weights are excluded and reported explicitly.

This module is analysis-only: no UrQMD events are generated and nothing in
the frozen module urqmd_agent/analysis/azimuthal_partition.py is modified.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

import numpy as np

TWO_PI = 2.0 * math.pi

#: frozen number of partition orientations per event (same as A5)
N_PARTITION_SAMPLES = 72

#: thesis w grid in degrees
THESIS_W_GRID_DEG: Tuple[int, ...] = (60, 72, 90, 120, 180, 240, 270, 288, 300)

#: complement symmetry pairs w <-> 360 - w (180 deg is self-complement)
THESIS_COMPLEMENT_PAIRS: Tuple[Tuple[int, int], ...] = (
    (60, 300), (72, 288), (90, 270), (120, 240))
THESIS_SELF_COMPLEMENT_DEG = 180

#: frozen bootstrap stream seed and replica counts
POISSON_BOOT_SEED = 20261025
N_BOOT_PRIMARY = 250
N_BOOT_FULL = 1000
#: minimum number of valid primary replicas for a defined inverse weight
MIN_VALID_PRIMARY = 200

WEIGHT_DOMINATED_THRESHOLD = 0.5


def p0_of_w(w_rad: float) -> float:
    """P0 = w / (2*pi)."""
    return float(w_rad) / TWO_PI


def complement_w(w_deg: float) -> float:
    """Complement partition width 360 - w (degrees)."""
    return 360.0 - float(w_deg)


def fisher_k2(s1: float, s2: float, m: int) -> float:
    """Unbiased sample variance (ddof=1) from sufficient statistics.

    k2 = (s2 - s1^2 / M) / (M - 1). NaN when M < 2 (mathematically
    undefined). Equivalent to numpy.var(x, ddof=1) and to
    M/(M-1) times the population (ddof=0) variance.
    """
    m = int(m)
    if m < 2:
        return float("nan")
    s1 = float(s1)
    s2 = float(s2)
    return (s2 - s1 * s1 / m) / (m - 1.0)


def delta_from_k2(k2: float, n: int, p0: float) -> float:
    """Delta_sigma2(N, w) = [k2 - N P0 (1-P0)] / [N (N-1)]. NaN for N < 2."""
    if int(n) < 2 or not math.isfinite(k2):
        return float("nan")
    n = int(n)
    return (k2 - n * p0 * (1.0 - p0)) / (n * (n - 1.0))


def poisson_weights(rng: np.random.Generator, n_events: int,
                    n_replicas: int) -> np.ndarray:
    """(n_replicas, n_events) array of iid Poisson(1) event weights.

    Exactly ONE weight is drawn per event per replica; the caller applies it
    to the event's whole partition-count block.
    """
    return rng.poisson(1.0, size=(int(n_replicas), int(n_events)))


def fixedN_mirror_from_sums(s1: np.ndarray, s2: np.ndarray, n: int,
                            p0: float, rng: np.random.Generator,
                            n_boot: int = N_BOOT_FULL,
                            n_samples: int = N_PARTITION_SAMPLES
                            ) -> Tuple[float, np.ndarray]:
    """Nominal mirror Delta and Poisson-bootstrap replicas for one N bin.

    s1[e] = sum of the event's n_samples partition counts,
    s2[e] = sum of squared counts (sufficient statistics; all events in the
    bin have the same proton multiplicity N = n >= 2).

    Returns (delta_nominal, replicas) with replicas shape (n_boot,);
    invalid replicas (weighted entries M_b < 2) are NaN.
    """
    s1 = np.asarray(s1, dtype=np.float64)
    s2 = np.asarray(s2, dtype=np.float64)
    if s1.shape != s2.shape:
        raise ValueError("s1 and s2 must have identical shapes")
    n_ev = int(s1.size)
    if int(n) < 2 or n_ev < 1:
        return float("nan"), np.full(int(n_boot), np.nan)

    m_nom = n_samples * n_ev
    k2_nom = fisher_k2(s1.sum(), s2.sum(), m_nom)
    d_nom = delta_from_k2(k2_nom, n, p0)

    w = poisson_weights(rng, n_ev, n_boot)
    ws = w.sum(axis=1)                      # total event weight per replica
    mb = n_samples * ws                     # total weighted entries
    t1 = w @ s1
    t2 = w @ s2
    valid = mb >= 2.0
    k2 = np.full(int(n_boot), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        k2[valid] = ((t2[valid] - t1[valid] ** 2 / mb[valid])
                     / (mb[valid] - 1.0))
    reps = (k2 - n * p0 * (1.0 - p0)) / (n * (n - 1.0))
    reps[~valid] = np.nan
    return float(d_nom), reps


def fixedN_mirror(counts_matrix: np.ndarray, n: int, p0: float,
                  rng: np.random.Generator,
                  n_boot: int = N_BOOT_FULL
                  ) -> Tuple[float, np.ndarray]:
    """Mirror Delta from the raw (n_events, n_samples) count matrix.

    Thin wrapper over fixedN_mirror_from_sums; the weighting is applied at
    the EVENT level (one Poisson weight multiplies the event's whole row).
    """
    cm = np.asarray(counts_matrix, dtype=np.float64)
    if cm.ndim != 2:
        raise ValueError("counts_matrix must be 2-D (n_events, n_samples)")
    s1 = cm.sum(axis=1)
    s2 = (cm * cm).sum(axis=1)
    return fixedN_mirror_from_sums(s1, s2, n, p0, rng, n_boot=n_boot,
                                   n_samples=cm.shape[1])


def summarize_replicas(replicas: np.ndarray) -> Dict[str, float]:
    """Summary of a bootstrap replica array (NaN replicas ignored).

    Returns dict with n_valid, std (ddof=1), std_ddof0, p16, p84. std is
    NaN when fewer than 2 valid replicas exist.
    """
    arr = np.asarray(replicas, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    n_valid = int(arr.size)
    out = {"n_valid": n_valid,
           "std": float("nan"), "std_ddof0": float("nan"),
           "p16": float("nan"), "p84": float("nan")}
    if n_valid >= 1:
        out["std_ddof0"] = float(arr.std(ddof=0))
        p16, p84 = np.percentile(arr, [16.0, 84.0])
        out["p16"] = float(p16)
        out["p84"] = float(p84)
    if n_valid >= 2:
        out["std"] = float(arr.std(ddof=1))
    return out


def primary_sigma_ok(summary: Dict[str, float],
                     min_valid: int = MIN_VALID_PRIMARY) -> bool:
    """An N bin's inverse weight is defined iff >= min_valid of the primary
    replicas are valid AND the ddof=1 std is finite and > 0."""
    return (summary["n_valid"] >= int(min_valid)
            and math.isfinite(summary["std"]) and summary["std"] > 0.0)


def inverse_variance_mean(deltas: Sequence[float],
                          sigmas: Sequence[float],
                          dominance_threshold: float
                          = WEIGHT_DOMINATED_THRESHOLD) -> Dict[str, object]:
    """Inverse-variance weighted mean with explicit undefined-weight audit.

    Bins with non-finite delta or non-finite / non-positive sigma are
    excluded and reported in flags["undefined_bins"] (index list). Returns
    dict with mean, err = sqrt(1/sum(1/sigma^2)), norm_weights (aligned to
    the input, NaN for excluded bins), max_weight, and flags with keys
    "weight_dominated" (max normalized weight > threshold) and
    "undefined_bins".
    """
    d = np.asarray(deltas, dtype=np.float64)
    s = np.asarray(sigmas, dtype=np.float64)
    if d.shape != s.shape:
        raise ValueError("deltas and sigmas must have identical shapes")
    ok = np.isfinite(d) & np.isfinite(s) & (s > 0.0)
    undefined = [int(i) for i in np.nonzero(~ok)[0]]
    norm_w = np.full(d.shape, np.nan)
    flags: Dict[str, object] = {"weight_dominated": False,
                                "undefined_bins": undefined}
    if not np.any(ok):
        return {"mean": float("nan"), "err": float("nan"),
                "norm_weights": norm_w, "max_weight": float("nan"),
                "n_used": 0, "flags": flags}
    inv = np.zeros(d.shape)
    inv[ok] = 1.0 / (s[ok] ** 2)
    sw = inv.sum()
    norm_w[ok] = inv[ok] / sw
    mean = float(np.dot(norm_w[ok], d[ok]))
    err = float(math.sqrt(1.0 / sw))
    max_w = float(norm_w[ok].max())
    flags["weight_dominated"] = bool(max_w > dominance_threshold)
    return {"mean": mean, "err": err, "norm_weights": norm_w,
            "max_weight": max_w, "n_used": int(ok.sum()), "flags": flags}


# --- Phase A5.6 forensic helpers (additive; A5.5 definitions unchanged) ---------

def k2_delta_to_ddof0_delta(delta_k2: float, n: int, p0: float,
                            m: int) -> float:
    """Recover the ddof=0 (population-variance) Delta_sigma2 from a
    Fisher-k2 Delta_sigma2 for the same pooled sample.

    Exact algebra: k2 = M/(M-1) * var0, so
    var0 = k2 * (M-1)/M with k2 = delta_k2 * N(N-1) + N P0 (1-P0).
    NaN when M < 2, N < 2, or the input is non-finite.
    """
    if int(m) < 2 or int(n) < 2 or not math.isfinite(delta_k2):
        return float("nan")
    n = int(n)
    binom = n * p0 * (1.0 - p0)
    k2 = delta_k2 * n * (n - 1.0) + binom
    var0 = k2 * (int(m) - 1.0) / int(m)
    return (var0 - binom) / (n * (n - 1.0))


def normalized_fractions(weights: Sequence[float]) -> np.ndarray:
    """weights / sum(weights); non-finite or non-positive entries -> NaN.

    Only finite positive entries participate in the normalization.
    """
    w = np.asarray(weights, dtype=np.float64)
    ok = np.isfinite(w) & (w > 0.0)
    out = np.full(w.shape, np.nan)
    sw = w[ok].sum()
    if np.any(ok) and sw > 0.0:
        out[ok] = w[ok] / sw
    return out


def leave_one_out_weighted(values: Sequence[float],
                           weights: Sequence[float]
                           ) -> Tuple[float, np.ndarray, np.ndarray]:
    """Leave-one-out weighted means with explicit exclusion audit.

    Entries with non-finite value or non-finite / non-positive weight are
    excluded globally (their LOO rows are NaN). Returns
    (full_mean, loo_means, influences) aligned to the input, where
    influence_j = full_mean - loo_mean_j. loo_mean_j is NaN when removing
    j leaves no weight.
    """
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if v.shape != w.shape:
        raise ValueError("values and weights must have identical shapes")
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0.0)
    loo = np.full(v.shape, np.nan)
    infl = np.full(v.shape, np.nan)
    if not np.any(ok):
        return float("nan"), loo, infl
    wsum = w[ok].sum()
    vsum = float(np.dot(w[ok], v[ok]))
    full = vsum / wsum
    idx = np.nonzero(ok)[0]
    for j in idx:
        wj = wsum - w[j]
        if wj > 0.0:
            loo[j] = (vsum - w[j] * v[j]) / wj
            infl[j] = full - loo[j]
    return float(full), loo, infl


def shortest_covering_interval(n_values: Sequence[int],
                               counts: Sequence[float],
                               fraction: float = 0.9
                               ) -> Tuple[int, int]:
    """Shortest contiguous integer-N interval [lo, hi] (inclusive) covering
    >= `fraction` of the total event counts.

    `n_values` must be sorted unique integers, `counts` aligned. Among
    intervals of equal minimal length hi - lo the LOWEST lo is chosen
    (deterministic tie break). Raises on empty input or empty counts.
    """
    nv = [int(v) for v in n_values]
    c = np.asarray(counts, dtype=np.float64)
    if len(nv) == 0 or len(nv) != c.size:
        raise ValueError("n_values and counts must be non-empty and aligned")
    if nv != sorted(nv) or len(set(nv)) != len(nv):
        raise ValueError("n_values must be sorted and unique")
    total = c.sum()
    if total <= 0.0:
        raise ValueError("total counts must be positive")
    need = float(fraction) * total
    best = None
    for i in range(len(nv)):
        acc = 0.0
        for j in range(i, len(nv)):
            acc += c[j]
            if acc >= need:
                length = nv[j] - nv[i]
                if best is None or length < best[1] - best[0]:
                    best = (nv[i], nv[j])
                break
    if best is None:
        raise ValueError("no interval reaches the requested coverage")
    return best


def event_id_parity_mask(event_ids: Sequence[int]) -> np.ndarray:
    """True where event_id is even (half A of the cross-fit split);
    deterministic and physics-observable-free."""
    return (np.asarray(event_ids, dtype=np.int64) % 2) == 0


# --- Phase A5.7: literature quadratic w-shape fits (additive) -------------------

def quadratic_eq8_curve(w_deg: Sequence[float], b: float, z: float
                        ) -> np.ndarray:
    """Literature compression shape b * [1 - ((w - 180)/z)^2], w in deg."""
    w = np.asarray(w_deg, dtype=np.float64)
    return b * (1.0 - ((w - 180.0) / float(z)) ** 2)


def pseudoinverse_clipped(cov: np.ndarray, rcond: float = 1e-10
                          ) -> np.ndarray:
    """Eigenvalue-clipped Moore-Penrose pseudoinverse of a symmetric
    covariance matrix: eigenvalues below rcond * lambda_max are treated as
    zero (their inverse is set to zero). Raises for non-square input."""
    c = np.asarray(cov, dtype=np.float64)
    if c.ndim != 2 or c.shape[0] != c.shape[1]:
        raise ValueError("covariance must be square")
    c = 0.5 * (c + c.T)
    lam, vec = np.linalg.eigh(c)
    lam_max = float(lam.max()) if lam.size else 0.0
    inv = np.zeros_like(lam)
    keep = lam > rcond * lam_max
    inv[keep] = 1.0 / lam[keep]
    return (vec * inv[None, :]) @ vec.T


def quadratic_eq8_fit(w_deg: Sequence[float], y: Sequence[float],
                      cov: np.ndarray | None = None,
                      sigma: Sequence[float] | None = None
                      ) -> Dict[str, float]:
    """GLS / diagonal fit of the literature shape Eq. (8).

    Exact linear reparametrization: f(w) = b - c*(w-180)^2 with
    c = b / z^2, so z = sqrt(b/c) is real (and > 0) iff b*c > 0. Fits are
    linear least squares in (b, c): GLS with the full covariance
    (chi2 = r^T C+ r, C+ from pseudoinverse_clipped) when `cov` is given,
    or diagonal weighting with 1/sigma^2 when `sigma` is given instead.

    z-parameter uncertainties come from the multivariate delta method on
    z(b, c) = sqrt(b/c): dz/db = z/(2b), dz/dc = -z/(2c).

    Returns dict with b, c, z, sigma_b, sigma_c, sigma_z, cov_bc,
    cov_bz, corr_bz, chi2, ndof, p, max_abs_standardized_residual,
    converged, note. converged is False (and z NaN) when z is not real
    (b*c <= 0) or the problem is underdetermined; b and c are still
    reported. Failed fits are never silently altered.
    """
    w = np.asarray(w_deg, dtype=np.float64)
    yv = np.asarray(y, dtype=np.float64)
    u = (w - 180.0) ** 2
    X = np.column_stack([np.ones_like(w), -u])  # f = b*1 + c*(-u)
    ok = np.isfinite(yv)
    out: Dict[str, float] = {"b": float("nan"), "c": float("nan"),
                             "z": float("nan"), "sigma_b": float("nan"),
                             "sigma_c": float("nan"),
                             "sigma_z": float("nan"),
                             "cov_bc": float("nan"),
                             "cov_bz": float("nan"),
                             "corr_bz": float("nan"),
                             "chi2": float("nan"), "ndof": 0,
                             "p": float("nan"),
                             "max_abs_standardized_residual": float("nan"),
                             "converged": False, "note": ""}
    if ok.sum() < 3:
        out["note"] = "fewer than 3 finite points"
        return out
    Xo, yo, wo = X[ok], yv[ok], w[ok]
    if cov is not None:
        c_full = np.asarray(cov, dtype=np.float64)[np.ix_(ok, ok)]
        prec = pseudoinverse_clipped(c_full)
        var_diag = np.diag(c_full)
    elif sigma is not None:
        s = np.asarray(sigma, dtype=np.float64)[ok]
        sok = np.isfinite(s) & (s > 0)
        if sok.sum() < 3:
            out["note"] = "fewer than 3 points with positive sigma"
            return out
        Xo, yo, wo = Xo[sok], yo[sok], wo[sok]
        prec = np.diag(1.0 / s[sok] ** 2)
        var_diag = s[sok] ** 2
    else:
        raise ValueError("provide either cov or sigma")
    A = Xo.T @ prec @ Xo
    try:
        Ainv = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        out["note"] = "singular design matrix"
        return out
    h = Xo.T @ prec @ yo
    beta = Ainv @ h
    b, c = float(beta[0]), float(beta[1])
    resid = yo - Xo @ beta
    chi2 = float(resid @ prec @ resid)
    ndof = int(len(yo) - 2)
    from scipy import stats as _st
    out.update({"b": b, "c": c, "sigma_b": float(math.sqrt(Ainv[0, 0])),
                "sigma_c": float(math.sqrt(Ainv[1, 1])),
                "cov_bc": float(Ainv[0, 1]), "chi2": chi2, "ndof": ndof,
                "p": float(_st.chi2.sf(chi2, ndof)) if ndof > 0
                else float("nan"),
                "max_abs_standardized_residual":
                    float(np.max(np.abs(resid / np.sqrt(var_diag))))
                    if np.all(var_diag > 0) else float("nan")})
    if b * c > 0.0:
        z = math.sqrt(b / c)
        gz = np.array([z / (2.0 * b), -z / (2.0 * c)])
        var_z = float(gz @ Ainv @ gz)
        sigma_z = math.sqrt(var_z) if var_z > 0 else float("nan")
        cov_bz = float(gz @ Ainv[:, 0])
        corr_bz = (cov_bz / (out["sigma_b"] * sigma_z)
                   if sigma_z and np.isfinite(sigma_z)
                   and out["sigma_b"] * sigma_z > 0 else float("nan"))
        out.update({"z": z, "sigma_z": sigma_z, "cov_bz": cov_bz,
                    "corr_bz": corr_bz, "converged": True})
    else:
        out["note"] = ("z not real (b*c <= 0): b=%.3e c=%.3e" % (b, c))
    return out
