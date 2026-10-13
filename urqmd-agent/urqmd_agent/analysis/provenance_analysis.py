"""Phase-1B provenance analysis (Steps 10-14).

All inputs are the Phase-1B compact CSVs (summary + provenance); no raw
histories are needed. Centrality: fractional-tie (Phase 1A-R). Observable
weights: Lambda 1.0, K0/antiK0 0.5 each.

Mathematical note (Step 12): for adjacent centrality bins i,j with
R_N = N_j/N_i and class ratios R_c = Y_c^j/Y_c^i, the EXACT discrete
identity is the log-sum-exp form

    alpha_local = ln( sum_c f_c^i * R_c ) / ln(R_N)
              = ln( sum_c f_c^i * R_N^{alpha_c} ) / ln(R_N),

because Y_j/Y_i = sum_c f_c^i R_c exactly, with f_c^i = Y_c^i/Y^i.
The commonly used linear form  alpha ~ sum_c f_c alpha_c  is only an
approximation for small ln-changes; we report both and their difference.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .centrality import fractional_tie_weights
from .scaling import CENTRALITY_BINS

BOOTSTRAP_SEED_1B = 20260918
N_BOOTSTRAP_1B = 500

#: coarse classes in fixed report order
CLASSES = ("STRING", "DECAY", "BB", "MB", "MM", "STRX", "ANNIHILATION",
           "ELASTIC", "OTHER")

#: predefined population criterion (protocol): fittable iff weighted yield
#: > 0 in all six bins AND centrality-integrated share >= 2%
MIN_SHARE = 0.02


@dataclass(frozen=True)
class ProvRow:
    event_idx: int              # 0-based position in the summary file
    species_group: str          # "Lambda" or "K" (K0 + antiK0, weight 0.5)
    obs_weight: float
    formation_class: str
    formation_process_id: int
    formation_time: float
    formation_sqrts: float
    formation_rhob: float
    n_postformation: int
    n_post_elastic: int
    n_post_inelastic: int


@dataclass(frozen=True)
class EventSummary1B:
    n_ch: int
    n_part: float
    n_part_actual: int
    bimp: float
    n_lambda: int
    n_kaon0: int
    n_antikaon0: int


def load_phase1b(pairs: Sequence[Tuple[Path, Path]]
                 ) -> Tuple[List[EventSummary1B], List[ProvRow]]:
    """Load (summary_csv, provenance_csv) pairs and merge them with GLOBAL
    event indices (event_id restarts at 1 in every campaign file; the
    merged index is offset + event_id - 1, in file order)."""
    events: List[EventSummary1B] = []
    rows: List[ProvRow] = []
    for summary_csv, provenance_csv in pairs:
        offset = len(events)
        with open(summary_csv) as fh:
            for rec in csv.DictReader(fh):
                events.append(EventSummary1B(
                    n_ch=int(rec["n_ch"]),
                    n_part=float(rec["n_part_glauber"]),
                    n_part_actual=int(rec["n_part_actual"]),
                    bimp=float(rec["bimp_fm"]),
                    n_lambda=int(rec["n_lambda_y05"]),
                    n_kaon0=int(rec["n_kaon0_y05"]),
                    n_antikaon0=int(rec["n_antikaon0_y05"])))
        with open(provenance_csv) as fh:
            for rec in csv.DictReader(fh):
                grp = "Lambda" if rec["final_species"] == "Lambda" else "K"
                rows.append(ProvRow(
                    event_idx=offset + int(rec["event_id"]) - 1,
                    species_group=grp,
                    obs_weight=float(rec["obs_weight"]),
                    formation_class=rec["formation_class"],
                    formation_process_id=int(rec["formation_process_id"]),
                    formation_time=float(rec["formation_time"]),
                    formation_sqrts=float(rec["formation_sqrts"]),
                    formation_rhob=float(rec["formation_rhob"]),
                    n_postformation=int(rec["n_postformation"]),
                    n_post_elastic=int(rec["n_post_elastic"]),
                    n_post_inelastic=int(rec["n_post_inelastic"])))
    return events, rows


def _species_totals(events: Sequence[EventSummary1B], idx: np.ndarray
                    ) -> Tuple[float, float]:
    lam = sum(events[i].n_lambda for i in idx)
    k = 0.5 * sum(events[i].n_kaon0 + events[i].n_antikaon0 for i in idx)
    return float(lam), float(k)


def class_yields(events: Sequence[EventSummary1B],
                 rows: Sequence[ProvRow],
                 sample_idx: np.ndarray
                 ) -> Tuple[np.ndarray, Dict[Tuple[str, str], np.ndarray],
                            Dict[str, np.ndarray]]:
    """Fractional-tie weighted yields per bin.

    Returns (mean_npart[bin], Y[(group, class)][bin], Y_tot[group][bin]).
    A provenance row contributes obs_weight * (fractional bin weight of its
    event) * (multiplicity of the event in the bootstrap sample)."""
    n_ch = np.array([events[i].n_ch for i in sample_idx], dtype=np.int64)
    weights = fractional_tie_weights(n_ch)
    # event multiplicity in the resample (1 for the plain sample)
    uniq, mult = np.unique(sample_idx, return_counts=True)
    mult_map = dict(zip(uniq.tolist(), mult.tolist()))

    mean_npart = np.zeros(len(CENTRALITY_BINS))
    for bi, w in enumerate(weights):
        wsum = w.sum()
        if wsum > 0:
            npart = np.array([events[i].n_part for i in sample_idx])
            mean_npart[bi] = float((w * npart).sum() / wsum)
        else:
            mean_npart[bi] = float("nan")

    y_cls: Dict[Tuple[str, str], np.ndarray] = {}
    y_tot: Dict[str, np.ndarray] = {"Lambda": np.zeros(len(CENTRALITY_BINS)),
                                    "K": np.zeros(len(CENTRALITY_BINS))}
    # event position within the sample for provenance lookup
    pos = {int(ev_i): k for k, ev_i in enumerate(sample_idx)}
    for r in rows:
        if r.event_idx not in pos:
            continue
        k = pos[r.event_idx]
        m = mult_map.get(r.event_idx, 0)
        if m == 0:
            continue
        key = (r.species_group, r.formation_class)
        if key not in y_cls:
            y_cls[key] = np.zeros(len(CENTRALITY_BINS))
        contrib = np.array([r.obs_weight * w[k] * m for w in weights])
        y_cls[key] += contrib
        y_tot[r.species_group] += contrib
    # normalize: fractional weights already carry the bin probability mass;
    # divide by bin weight sum to get mean yield per event in the bin
    for bi, w in enumerate(weights):
        wsum = w.sum()
        if wsum <= 0:
            continue
        for arr in y_cls.values():
            arr[bi] /= wsum
        for g in y_tot:
            y_tot[g][bi] /= wsum
    return mean_npart, y_cls, y_tot


def fit_alpha_bins(npart: np.ndarray, y: np.ndarray) -> float:
    xs = [math.log(npart[b]) for b in range(len(y))
          if y[b] > 0 and npart[b] > 0]
    ys = [math.log(y[b]) for b in range(len(y)) if y[b] > 0 and npart[b] > 0]
    if len(xs) < 2:
        return float("nan")
    return float(np.polyfit(np.array(xs), np.array(ys), 1)[0])


def class_shares(y_cls: Dict[Tuple[str, str], np.ndarray],
                 y_tot: Dict[str, np.ndarray], group: str
                 ) -> Dict[str, np.ndarray]:
    """f_h^c per bin."""
    return {c: np.divide(y_cls.get((group, c), np.zeros(6)), y_tot[group],
                         out=np.zeros(6), where=y_tot[group] > 0)
            for c in CLASSES}


def integrated_share(y_cls: Dict[Tuple[str, str], np.ndarray],
                     y_tot: Dict[str, np.ndarray], group: str,
                     cls: str) -> float:
    num = float(np.nansum(y_cls.get((group, cls), np.zeros(6))))
    den = float(np.nansum(y_tot[group]))
    return num / den if den > 0 else 0.0


def fittable_classes(y_cls, y_tot, group: str) -> List[str]:
    out = []
    for c in CLASSES:
        y = y_cls.get((group, c))
        if y is None:
            continue
        if np.all(y > 0) and integrated_share(y_cls, y_tot, group, c) >= MIN_SHARE:
            out.append(c)
    return out


def local_slope_decomposition(npart: np.ndarray,
                              y_cls: Dict[Tuple[str, str], np.ndarray],
                              y_tot: np.ndarray, group: str
                              ) -> List[dict]:
    """Step 12: exact log-sum-exp decomposition of adjacent-bin local slopes
    plus the linear approximation sum_c mean(f_c) * alpha_c."""
    out = []
    shares = class_shares(y_cls, {group: y_tot}, group)
    for b in range(len(npart) - 1):
        n1, n2 = npart[b], npart[b + 1]
        y1, y2 = y_tot[b], y_tot[b + 1]
        if min(n1, n2, y1, y2) <= 0:
            out.append({"interval": f"{b}->{b+1}", "alpha_local": float("nan")})
            continue
        ln_rn = math.log(n2 / n1)
        alpha_tot = math.log(y2 / y1) / ln_rn
        per_class = {}
        lse = 0.0
        lin = 0.0
        for c in CLASSES:
            yc = y_cls.get((group, c))
            if yc is None or yc[b] <= 0 or yc[b + 1] <= 0:
                continue
            r_c = yc[b + 1] / yc[b]
            f_i = yc[b] / y1
            f_j = yc[b + 1] / y2
            a_c = math.log(r_c) / ln_rn
            lse += f_i * r_c
            lin += 0.5 * (f_i + f_j) * a_c
            per_class[c] = {"alpha_local": a_c, "f_i": f_i, "f_j": f_j}
        alpha_lse = math.log(lse) / ln_rn if lse > 0 else float("nan")
        out.append({
            "interval": f"{CENTRALITY_BINS[b][0]}-{CENTRALITY_BINS[b][1]}%"
                        f"->{CENTRALITY_BINS[b+1][0]}-{CENTRALITY_BINS[b+1][1]}%",
            "alpha_local": alpha_tot,
            "alpha_lse_reconstruction": alpha_lse,
            "lse_residual": alpha_tot - alpha_lse,
            "alpha_linear_approx": lin,
            "linear_deviation": alpha_tot - lin,
            "per_class": per_class,
        })
    return out


def formation_transport_stats(events: Sequence[EventSummary1B],
                              rows: Sequence[ProvRow],
                              group: str) -> Dict[str, Dict[str, float]]:
    """Step 13: formation-time/density and post-formation stats per
    centrality bin (fractional-tie weighted)."""
    n_ch = np.array([e.n_ch for e in events], dtype=np.int64)
    weights = fractional_tie_weights(n_ch)
    out: Dict[str, Dict[str, float]] = {}
    grp_rows = [r for r in rows if r.species_group == group]
    for bi, w in enumerate(weights):
        label = f"{CENTRALITY_BINS[bi][0]}-{CENTRALITY_BINS[bi][1]}%"
        tot = 0.0
        acc = {"t_form": 0.0, "rhob": 0.0, "sqrts": 0.0, "n_post": 0.0,
               "zero_post": 0.0, "ge1_elastic": 0.0, "ge1_inelastic": 0.0}
        for r in grp_rows:
            wt = r.obs_weight * w[r.event_idx]
            if wt <= 0:
                continue
            tot += wt
            acc["t_form"] += wt * r.formation_time
            acc["rhob"] += wt * r.formation_rhob
            acc["sqrts"] += wt * r.formation_sqrts
            acc["n_post"] += wt * r.n_postformation
            acc["zero_post"] += wt * (r.n_postformation == 0)
            acc["ge1_elastic"] += wt * (r.n_post_elastic >= 1)
            acc["ge1_inelastic"] += wt * (r.n_post_inelastic >= 1)
        if tot > 0:
            out[label] = {k: v / tot for k, v in acc.items()}
        else:
            out[label] = {k: float("nan") for k in acc}
    return out
