"""Phase-1B2 genealogy analysis (Steps 7-16).

Inputs: replayed Phase-1B2 compact CSVs (summary + genealogy). Centrality:
fractional-tie (Phase 1A-R). Observable weights: Lambda 1.0, K0/antiK0 0.5.
Shared event bootstrap: 500 replicates, seed 20260919 (protocol).

No additive percentage decomposition of global OLS exponents is quoted
(protocol): exponents are compared per category, and totals are always
reconstructed explicitly from category yields.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

from .centrality import fractional_tie_weights
from .provenance_analysis import EventSummary1B, fit_alpha_bins
from .scaling import CENTRALITY_BINS

BOOTSTRAP_SEED_1B2 = 20260919
N_BOOTSTRAP_1B2 = 500

#: predefined population criterion (protocol): fittable iff weighted yield
#: > 0 in all six bins AND integrated share of its sector >= 2%
MIN_SHARE = 0.02

MOTHER_FAMILY_NONE = "NOT_DECAY_FORMED"


@dataclass(frozen=True)
class GenRow:
    event_idx: int              # 0-based global event index
    species_group: str          # "Lambda" or "K"
    weight: float
    formation_class: str
    formation_time: float
    formation_sqrts: float
    formation_rhob: float
    mother_family: str          # "" when not decay-formed
    mother_creation_class: str
    mother_creation_time: float
    mother_creation_sqrts: float
    mother_creation_rhob: float
    mother_lifetime: float
    mother_n_int: int
    mother_n_elastic: int
    mother_n_inelastic: int
    mother_id_changes: int
    root_outcome: str
    root_class: str
    root_time: float
    root_sqrts: float
    root_rhob: float
    root_n_candidates: int


def load_phase1b2(pairs: Sequence[Tuple[Path, Path, Path]]
                  ) -> Tuple[List[EventSummary1B], List[GenRow]]:
    """Load (summary_csv, provenance_csv, genealogy_csv) triples with
    GLOBAL event indices. formation_sqrts/rhob are joined from the
    provenance CSV on (event_id, final_uid)."""
    events: List[EventSummary1B] = []
    rows: List[GenRow] = []
    for summary_csv, prov_csv, gen_csv in pairs:
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
        prov = {}
        with open(prov_csv) as fh:
            for rec in csv.DictReader(fh):
                prov[(int(rec["event_id"]), int(rec["final_uid"]))] = rec
        with open(gen_csv) as fh:
            for rec in csv.DictReader(fh):
                grp = "Lambda" if rec["final_species"] == "Lambda" else "K"
                p = prov[(int(rec["event_id"]), int(rec["final_uid"]))]
                rows.append(GenRow(
                    event_idx=offset + int(rec["event_id"]) - 1,
                    species_group=grp,
                    weight=float(rec["final_weight"]),
                    formation_class=rec["formation_class"],
                    formation_time=float(rec["formation_time"]),
                    formation_sqrts=float(p["formation_sqrts"]),
                    formation_rhob=float(p["formation_rhob"]),
                    mother_family=rec["mother_family"],
                    mother_creation_class=rec["mother_creation_class"],
                    mother_creation_time=float(rec["mother_creation_time"]),
                    mother_creation_sqrts=float(rec["mother_creation_sqrts"]),
                    mother_creation_rhob=float(rec["mother_creation_rhob"]),
                    mother_lifetime=float(rec["mother_lifetime"]),
                    mother_n_int=int(rec["mother_n_interactions_before_decay"]),
                    mother_n_elastic=int(rec["mother_n_elastic_before_decay"]),
                    mother_n_inelastic=int(
                        rec["mother_n_inelastic_before_decay"]),
                    mother_id_changes=int(
                        rec["mother_identity_changes_before_decay"]),
                    root_outcome=rec["root_outcome"],
                    root_class=rec["root_class"],
                    root_time=float(rec["root_time"]),
                    root_sqrts=float(rec["root_sqrts"]),
                    root_rhob=float(rec["root_rhob"]),
                    root_n_candidates=int(rec["root_n_candidates"])))
    return events, rows


# ----------------------------------------------------------------------
# generic category yields (same algorithm as Phase-1B class_yields)
# ----------------------------------------------------------------------

KeyFn = Callable[[GenRow], str]


def category_yields(events: Sequence[EventSummary1B],
                    rows: Sequence[GenRow], keyfn: KeyFn,
                    sample_idx: np.ndarray
                    ) -> Tuple[np.ndarray, Dict[Tuple[str, str], np.ndarray],
                               Dict[str, np.ndarray]]:
    """Fractional-tie weighted yields per bin for a row category.

    Returns (mean_npart[bin], Y[(group, category)][bin], Y_tot[group][bin]).
    """
    n_ch = np.array([events[i].n_ch for i in sample_idx], dtype=np.int64)
    weights = fractional_tie_weights(n_ch)
    uniq, mult = np.unique(sample_idx, return_counts=True)
    mult_map = dict(zip(uniq.tolist(), mult.tolist()))
    npart = np.array([events[i].n_part for i in sample_idx])

    mean_npart = np.zeros(len(CENTRALITY_BINS))
    for bi, w in enumerate(weights):
        wsum = w.sum()
        mean_npart[bi] = float((w * npart).sum() / wsum) if wsum > 0 \
            else float("nan")

    y_cat: Dict[Tuple[str, str], np.ndarray] = {}
    y_tot: Dict[str, np.ndarray] = {"Lambda": np.zeros(len(CENTRALITY_BINS)),
                                    "K": np.zeros(len(CENTRALITY_BINS))}
    pos = {int(ev_i): k for k, ev_i in enumerate(sample_idx)}
    for r in rows:
        k = pos.get(r.event_idx)
        if k is None:
            continue
        m = mult_map.get(r.event_idx, 0)
        if m == 0:
            continue
        key = (r.species_group, keyfn(r))
        if key not in y_cat:
            y_cat[key] = np.zeros(len(CENTRALITY_BINS))
        contrib = np.array([r.weight * w[k] * m for w in weights])
        y_cat[key] += contrib
        y_tot[r.species_group] += contrib
    for bi, w in enumerate(weights):
        wsum = w.sum()
        if wsum <= 0:
            continue
        for arr in y_cat.values():
            arr[bi] /= wsum
        for g in y_tot:
            y_tot[g][bi] /= wsum
    return mean_npart, y_cat, y_tot


def integrated_share(y_cat, y_sector: np.ndarray, group: str,
                     cat: str) -> float:
    num = float(np.nansum(y_cat.get((group, cat), np.zeros(6))))
    den = float(np.nansum(y_sector))
    return num / den if den > 0 else 0.0


def fittable_categories(y_cat, y_sector: np.ndarray, group: str,
                        cats: Sequence[str]) -> List[str]:
    out = []
    for c in cats:
        y = y_cat.get((group, c))
        if y is None:
            continue
        if np.all(y > 0) and integrated_share(y_cat, y_sector, group, c) \
                >= MIN_SHARE:
            out.append(c)
    return out


# ----------------------------------------------------------------------
# bootstrap driver
# ----------------------------------------------------------------------

def bootstrap_alphas(events: Sequence[EventSummary1B], rows: Sequence[GenRow],
                     keyfn: KeyFn, targets: Sequence[Tuple[str, str]],
                     n_boot: int = N_BOOTSTRAP_1B2,
                     seed: int = BOOTSTRAP_SEED_1B2) -> Dict[Tuple[str, str],
                                                            np.ndarray]:
    """Shared event bootstrap of per-category power-law exponents.

    `targets` = (group, category) pairs to fit in every replicate (chosen
    on the full sample beforehand). Returns (group, cat) -> array of
    replicate alphas."""
    rng = np.random.default_rng(seed)
    n = len(events)
    out: Dict[Tuple[str, str], List[float]] = {t: [] for t in targets}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        npart, y_cat, _ = category_yields(events, rows, keyfn, idx)
        for t in targets:
            y = y_cat.get(t)
            out[t].append(fit_alpha_bins(npart, y) if y is not None
                          else float("nan"))
    return {t: np.array(v) for t, v in out.items()}


def alpha_stats(alphas: np.ndarray) -> Dict[str, float]:
    a = alphas[np.isfinite(alphas)]
    if len(a) == 0:
        return {"median": float("nan"), "std": float("nan"),
                "p16": float("nan"), "p84": float("nan"), "n_ok": 0}
    return {"median": float(np.median(a)), "std": float(a.std(ddof=1)),
            "p16": float(np.percentile(a, 16)),
            "p84": float(np.percentile(a, 84)), "n_ok": int(len(a))}


# ----------------------------------------------------------------------
# closure accounting (Step 7)
# ----------------------------------------------------------------------

def closure_by_bin(y_cat, y_sector: np.ndarray, group: str,
                   cats: Sequence[str]) -> Dict[str, list]:
    """Per-bin: sector yield, sum of category yields, absolute difference."""
    out = {"sector": [], "reconstructed": [], "abs_diff": []}
    for b in range(len(CENTRALITY_BINS)):
        sec = y_sector[b]
        rec = sum(y_cat.get((group, c), np.zeros(6))[b] for c in cats)
        out["sector"].append(float(sec))
        out["reconstructed"].append(float(rec))
        out["abs_diff"].append(float(abs(sec - rec)))
    return out


# ----------------------------------------------------------------------
# timing / transport summaries (Steps 12-13)
# ----------------------------------------------------------------------

def weighted_mean_per_bin(events, rows, value: Callable[[GenRow], float],
                          group: str, pred: Callable[[GenRow], bool]
                          ) -> List[float]:
    n_ch = np.array([e.n_ch for e in events], dtype=np.int64)
    weights = fractional_tie_weights(n_ch)
    out = []
    for w in weights:
        num = den = 0.0
        for r in rows:
            if r.species_group != group or not pred(r):
                continue
            wt = r.weight * w[r.event_idx]
            if wt <= 0:
                continue
            num += wt * value(r)
            den += wt
        out.append(num / den if den > 0 else float("nan"))
    return out


def weighted_fraction_per_bin(events, rows, pred: Callable[[GenRow], bool],
                              group: str,
                              base: Callable[[GenRow], bool]) -> List[float]:
    return weighted_mean_per_bin(
        events, rows, lambda r: 1.0 if pred(r) else 0.0, group, base)
