"""Genealogy / provenance aggregation tools over Phase-1B/1B2 CSVs.

Everything dispatches to urqmd_agent/analysis/provenance_analysis.py and
genealogy_analysis.py. Ambiguous strangeness roots are never resolved by
hand; the outcome fractions are reported as traced.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..analysis import genealogy_analysis as ga
from ..analysis import provenance_analysis as pa
from ..analysis.provenance_analysis import MIN_SHARE
from ..analysis.scaling import CENTRALITY_BINS
from ..core import config
from ..core.errors import ToolError
from ..core.result import ToolResult
from ..history.parse_f15 import parse_f15
from ..history.reaction_graph import build_graph
from ..history.genealogy import strangeness_root, UNIQUE_ROOT
from ..history.provenance import uid_final_states
from ..history.taxonomy import classify
from ._common import (resolve_phase1b_pairs, resolve_phase1b2_triples,
                      resolve_repo_path)
from .registry import ANALYSIS, ToolSpec, register

_BIN_LABELS = [f"{lo}-{hi}%" for lo, hi in CENTRALITY_BINS]


def _group(species: str) -> str:
    s = species.strip().lower()
    if s == "lambda":
        return "Lambda"
    if s in ("kaon", "k"):
        return "K"
    raise ToolError(f"unknown species {species!r}; choose 'lambda' or 'kaon'")


def _shares_per_bin(y_cls, y_tot, group):
    raw = pa.class_shares(y_cls, y_tot, group)
    return {c: [float(x) for x in arr] for c, arr in raw.items()}


def formation_provenance(dataset: str = "phase1b", species: str = "lambda",
                         with_scaling: bool = True) -> ToolResult:
    """Formation-class decomposition of midrapidity Lambda or K yields."""
    group = _group(species)
    if dataset == "phase1b":
        pairs = resolve_phase1b_pairs()
    elif dataset == "phase1b2":
        pairs = [(s, p) for s, p, _ in resolve_phase1b2_triples()]
    else:
        raise ToolError(f"unknown dataset {dataset!r}")
    events, rows = pa.load_phase1b(pairs)
    sample_idx = np.arange(len(events))
    mean_npart, y_cls, y_tot = pa.class_yields(events, rows, sample_idx)

    shares_bin = _shares_per_bin(y_cls, y_tot, group)
    integrated = {c: pa.integrated_share(y_cls, y_tot, group, c)
                  for c in pa.CLASSES}
    fittable = pa.fittable_classes(y_cls, y_tot, group)

    alphas = {}
    if with_scaling:
        for c in fittable:
            alphas[c] = pa.fit_alpha_bins(mean_npart, y_cls[(group, c)])
        alphas["TOTAL"] = pa.fit_alpha_bins(mean_npart, y_tot[group])

    closure = {"sector": [], "reconstructed": [], "abs_diff": []}
    for b in range(len(mean_npart)):
        sec = float(y_tot[group][b])
        rec = float(sum(y_cls.get((group, c), np.zeros(6))[b]
                        for c in pa.CLASSES))
        closure["sector"].append(sec)
        closure["reconstructed"].append(rec)
        closure["abs_diff"].append(abs(sec - rec))
    max_diff = max(closure["abs_diff"])

    data = {
        "dataset": dataset, "species_group": group,
        "n_events": len(events), "n_provenance_rows": len(rows),
        "bins": _BIN_LABELS,
        "mean_npart": [float(x) for x in mean_npart],
        "total_yield_per_bin": [float(x) for x in y_tot[group]],
        "class_shares_per_bin": shares_bin,
        "integrated_shares": integrated,
        "fittable_classes": fittable,
        "alphas": alphas,
        "closure": closure,
        "closure_max_abs_diff": max_diff,
        "method": "fractional-tie centrality bins; obs weights Lambda 1.0, "
                  "K0/antiK0 0.5; alphas from log-log fits of class yields "
                  f"vs <Npart>; fittability share threshold {MIN_SHARE}",
        "source_csvs": [str(p) for pair in pairs for p in pair],
    }
    top = max(integrated, key=integrated.get)
    summary = (f"{dataset} {group}: dominant formation class {top} "
               f"(integrated share {integrated[top]:.3f}); "
               f"alpha_total = {alphas.get('TOTAL', float('nan')):.4f}; "
               f"closure max |diff| = {max_diff:.2e}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.formation_provenance"})


_DECAY_SECTOR_KEY = ga.MOTHER_FAMILY_NONE  # "NOT_DECAY_FORMED"


def _decay_sector_yields(events, rows, group):
    """Per-bin yield of the DECAY-formed sector for `group`."""
    keyfn = lambda r: r.formation_class
    _, y_fc, _ = ga.category_yields(events, rows, keyfn,
                                    np.arange(len(events)))
    return y_fc.get((group, "DECAY"), np.zeros(6))


def parent_genealogy(dataset: str = "phase1b2",
                     species: str = "lambda") -> ToolResult:
    """Mother-resonance genealogy of decay-formed Lambda/K: family and
    mother-production-mechanism shares, mother creation time/density."""
    group = _group(species)
    if dataset != "phase1b2":
        raise ToolError("parent_genealogy requires the phase1b2 dataset "
                        "(genealogy CSVs)")
    triples = resolve_phase1b2_triples()
    events, rows = ga.load_phase1b2(triples)
    sector = _decay_sector_yields(events, rows, group)

    fam_keyfn = lambda r: (r.mother_family if r.formation_class == "DECAY"
                           else _DECAY_SECTOR_KEY)
    prod_keyfn = lambda r: (r.mother_creation_class
                            if r.formation_class == "DECAY"
                            else _DECAY_SECTOR_KEY)

    mean_npart, y_fam, _ = ga.category_yields(events, rows, fam_keyfn,
                                              np.arange(len(events)))
    _, y_prod, _ = ga.category_yields(events, rows, prod_keyfn,
                                      np.arange(len(events)))

    fam_cats = sorted({r.mother_family for r in rows
                       if r.species_group == group
                       and r.formation_class == "DECAY"})
    prod_cats = sorted({r.mother_creation_class for r in rows
                        if r.species_group == group
                        and r.formation_class == "DECAY"})

    def _shares(y_cat, cats):
        integ = {c: ga.integrated_share(y_cat, sector, group, c)
                 for c in cats}
        per_bin = {c: [float(y_cat.get((group, c), np.zeros(6))[b]
                            / sector[b]) if sector[b] > 0 else 0.0
                       for b in range(6)] for c in cats}
        return integ, per_bin

    fam_integrated, fam_per_bin = _shares(y_fam, fam_cats)
    prod_integrated, prod_per_bin = _shares(y_prod, prod_cats)

    decayed = lambda r: r.formation_class == "DECAY"
    mother_creation_time = ga.weighted_mean_per_bin(
        events, rows, lambda r: r.mother_creation_time, group, decayed)
    mother_creation_rhob = ga.weighted_mean_per_bin(
        events, rows, lambda r: r.mother_creation_rhob, group, decayed)

    fam_fittable = ga.fittable_categories(y_fam, sector, group, fam_cats)
    alphas = {c: pa.fit_alpha_bins(mean_npart, y_fam[(group, c)])
              for c in fam_fittable}

    closure = ga.closure_by_bin(y_fam, sector, group, fam_cats)
    max_diff = max(closure["abs_diff"]) if closure["abs_diff"] else 0.0

    data = {
        "dataset": dataset, "species_group": group,
        "n_events": len(events), "n_genealogy_rows": len(rows),
        "bins": _BIN_LABELS,
        "sector": "DECAY-formed (final-species formation is a 1->n decay)",
        "decay_sector_yield_per_bin": [float(x) for x in sector],
        "mother_family": {"integrated_shares": fam_integrated,
                          "shares_per_bin": fam_per_bin},
        "mother_production": {"integrated_shares": prod_integrated,
                              "shares_per_bin": prod_per_bin},
        "mother_creation_time_per_bin": mother_creation_time,
        "mother_creation_rhob_per_bin": mother_creation_rhob,
        "fittable_mother_families": fam_fittable,
        "mother_family_alphas": alphas,
        "closure": closure, "closure_max_abs_diff": max_diff,
        "method": "fractional-tie bins; shares relative to the DECAY "
                  "sector; mother production = first physical interaction "
                  "where the mother uid is outgoing (INITIAL_STATE if none)",
        "source_csvs": [str(p) for t in triples for p in t],
    }
    top = max(fam_integrated, key=fam_integrated.get) if fam_integrated \
        else None
    summary = (f"{dataset} {group}: dominant mother family {top} "
               f"(share {fam_integrated[top]:.4f} of the DECAY sector); "
               f"closure max |diff| = {max_diff:.2e}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.parent_genealogy"})


def strangeness_origin(dataset: str = "phase1b2",
                       species: Optional[str] = None,
                       f15_path: Optional[str] = None,
                       uid: Optional[int] = None) -> ToolResult:
    """Strangeness-origin classification. Dataset mode aggregates the
    Phase-1B2 root outcomes; single-event mode (f15_path + uid) traces one
    particle. Ambiguous roots are NEVER resolved arbitrarily."""
    if f15_path is not None:
        if uid is None:
            raise ToolError("single-event mode needs uid")
        path = resolve_repo_path(f15_path)
        event = parse_f15(path)
        graph = build_graph(event)
        finals = uid_final_states(graph)
        if uid not in finals:
            return ToolResult.error(
                f"uid {uid} is not a final-state particle in {f15_path}",
                provenance={"tool": "urqmd.strangeness_origin"})
        snap = finals[uid]
        root = strangeness_root(graph, uid, (snap.ityp, snap.iso3), classify)
        data = {
            "mode": "single_event", "f15_path": f15_path, "uid": uid,
            "final_species": [snap.ityp, snap.iso3],
            "outcome": root.outcome,
            "preexisting_branch": root.preexisting_branch,
            "note": root.note,
            "candidates": [
                {"ctag": c.ctag, "time": c.time, "process_id": c.process_id,
                 "class": c.coarse_class, "sqrts": c.sqrts, "rhob": c.rhob}
                for c in root.candidates],
        }
        summary = (f"uid {uid}: strangeness origin {root.outcome} "
                   f"({len(root.candidates)} candidate root(s))")
        return ToolResult.ok(summary, data,
                             provenance={"tool": "urqmd.strangeness_origin"})

    if dataset != "phase1b2":
        raise ToolError("strangeness_origin dataset mode requires the "
                        "phase1b2 dataset (genealogy CSVs carry the traced "
                        "root outcomes)")
    triples = resolve_phase1b2_triples()
    events, rows = ga.load_phase1b2(triples)
    groups = [_group(species)] if species else ["Lambda", "K"]
    out = {}
    for g in groups:
        g_rows = [r for r in rows if r.species_group == g]
        tot = sum(r.weight for r in g_rows)
        outcomes = {}
        for r in g_rows:
            outcomes[r.root_outcome] = outcomes.get(r.root_outcome, 0.0) \
                + r.weight
        fractions = {k: v / tot for k, v in sorted(outcomes.items())} \
            if tot > 0 else {}
        unique_rows = [r for r in g_rows if r.root_outcome == UNIQUE_ROOT]
        u_tot = sum(r.weight for r in unique_rows)
        mech = {}
        for r in unique_rows:
            mech[r.root_class] = mech.get(r.root_class, 0.0) + r.weight
        mech_shares = {k: v / u_tot for k, v in sorted(mech.items())} \
            if u_tot > 0 else {}
        out[g] = {"outcome_fractions": fractions,
                  "mechanism_shares_of_unique": mech_shares,
                  "total_weight": tot}
    summary = "; ".join(
        f"{g}: UNIQUE_ROOT {out[g]['outcome_fractions'].get(UNIQUE_ROOT, 0.0):.3f}"
        for g in out)
    return ToolResult.ok(
        f"phase1b2 strangeness origin — {summary}",
        {"mode": "dataset", "dataset": dataset, "groups": out,
         "source_csvs": [str(p) for t in triples for p in t]},
        provenance={"tool": "urqmd.strangeness_origin"})


_ROOT_MECHANISM_SENTINEL = "NON_UNIQUE"


def channel_scaling(dataset: str, species: str, category: str,
                    n_bootstrap: int = 500) -> ToolResult:
    """Participant scaling per formation/genealogy category."""
    group = _group(species)

    if dataset == "phase1b":
        if category != "formation_class":
            return ToolResult.error(
                f"category {category!r} needs the phase1b2 genealogy CSVs; "
                "phase1b only carries formation_class",
                provenance={"tool": "urqmd.channel_scaling"})
        base = formation_provenance(dataset="phase1b", species=species,
                                    with_scaling=True)
        if base.status != "ok":
            return base
        base.data["category"] = "formation_class"
        base.data["alpha_bootstrap"] = None
        base.warnings.append(
            "bootstrap errors are not available for the phase1b formation "
            "classes from the validated modules; full-sample alphas only")
        return base

    if dataset != "phase1b2":
        raise ToolError(f"unknown dataset {dataset!r}")

    keyfns = {
        "formation_class": lambda r: r.formation_class,
        "mother_family": lambda r: (r.mother_family
                                    if r.formation_class == "DECAY"
                                    else _DECAY_SECTOR_KEY),
        "mother_production": lambda r: (r.mother_creation_class
                                        if r.formation_class == "DECAY"
                                        else _DECAY_SECTOR_KEY),
        "root_mechanism": lambda r: (r.root_class
                                     if r.root_outcome == UNIQUE_ROOT
                                     else _ROOT_MECHANISM_SENTINEL),
    }
    if category not in keyfns:
        return ToolResult.error(
            f"unknown category {category!r}; choose from "
            f"{sorted(keyfns)}",
            provenance={"tool": "urqmd.channel_scaling"})
    keyfn = keyfns[category]

    triples = resolve_phase1b2_triples()
    events, rows = ga.load_phase1b2(triples)
    mean_npart, y_cat, y_tot = ga.category_yields(
        events, rows, keyfn, np.arange(len(events)))

    # sector definition per category
    if category == "formation_class":
        sector = y_tot[group]
        cats = sorted({c for (g, c) in y_cat if g == group})
    elif category in ("mother_family", "mother_production"):
        sector = _decay_sector_yields(events, rows, group)
        cats = sorted({c for (g, c) in y_cat
                       if g == group and c != _DECAY_SECTOR_KEY})
    else:  # root_mechanism
        _, y_outcome, _ = ga.category_yields(
            events, rows, lambda r: r.root_outcome, np.arange(len(events)))
        sector = y_outcome.get((group, UNIQUE_ROOT), np.zeros(6))
        cats = sorted({c for (g, c) in y_cat
                       if g == group and c != _ROOT_MECHANISM_SENTINEL})

    fractions = {c: ga.integrated_share(y_cat, sector, group, c)
                 for c in cats}
    yields_per_bin = {c: [float(x) for x in y_cat[(group, c)]]
                      for c in cats}
    fittable = ga.fittable_categories(y_cat, sector, group, cats)
    alpha_full = {c: pa.fit_alpha_bins(mean_npart, y_cat[(group, c)])
                  for c in fittable}

    targets = [(group, c) for c in fittable]
    if targets:
        boot = ga.bootstrap_alphas(events, rows, keyfn, targets,
                                   n_boot=n_bootstrap,
                                   seed=config.BOOTSTRAP_SEED_REPRO)
        alpha_boot = {c: ga.alpha_stats(boot[(group, c)]) for c in fittable}
    else:
        alpha_boot = {}

    closure = ga.closure_by_bin(y_cat, sector, group, cats)
    max_diff = max(closure["abs_diff"]) if closure["abs_diff"] else 0.0

    data = {
        "dataset": dataset, "species_group": group, "category": category,
        "bins": _BIN_LABELS,
        "sector": {"formation_class": "total species yield",
                   "mother_family": "DECAY-formed sector",
                   "mother_production": "DECAY-formed sector",
                   "root_mechanism": "UNIQUE_ROOT sector"}[category],
        "fractions": fractions,
        "yields_per_bin": yields_per_bin,
        "fittable": fittable,
        "alpha_full_sample": alpha_full,
        "alpha_bootstrap": alpha_boot,
        "bootstrap": {"n_boot": n_bootstrap,
                      "seed": config.BOOTSTRAP_SEED_REPRO},
        "closure": closure, "closure_max_abs_diff": max_diff,
        "source_csvs": [str(p) for t in triples for p in t],
    }
    summary = (f"{dataset} {group} {category}: {len(cats)} categories, "
               f"fittable: {fittable}; closure max |diff| = {max_diff:.2e}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.channel_scaling"})


register(ToolSpec(
    name="urqmd.formation_provenance",
    description=(
        "Formation-class decomposition of midrapidity Lambda or K yields "
        "over the Phase-1B (or 1B2) provenance CSVs: integrated and per-bin "
        "class shares, per-class yields, fitted power-law exponents of "
        "fittable classes, and exact closure (class yields sum to the "
        "total) per centrality bin. Descriptive; analysis of existing CSVs."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b", "phase1b2"],
                    "default": "phase1b"},
        "species": {"type": "string", "enum": ["lambda", "kaon"],
                    "default": "lambda"},
        "with_scaling": {"type": "boolean", "default": True}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=formation_provenance,
))

register(ToolSpec(
    name="urqmd.parent_genealogy",
    description=(
        "Parent-resonance genealogy of decay-formed Lambda/K (phase1b2 "
        "only): mother resonance-family shares, mother production-mechanism "
        "shares, weighted mother creation time/density per bin, and "
        "closure against the DECAY sector."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b2"],
                    "default": "phase1b2"},
        "species": {"type": "string", "enum": ["lambda", "kaon"],
                    "default": "lambda"}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=parent_genealogy,
))

register(ToolSpec(
    name="urqmd.strangeness_origin",
    description=(
        "Strangeness-origin classification. Dataset mode (default "
        "phase1b2): weighted fractions of UNIQUE_ROOT / "
        "MULTIPLE_COMPATIBLE_ROOTS / PREEXISTING_STRANGENESS / UNRESOLVED "
        "plus mechanism shares among unique roots. Single-event mode "
        "(f15_path + uid): trace one final particle's strangeness root. "
        "Ambiguous roots are reported as sets, never resolved by hand."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b2"],
                    "default": "phase1b2"},
        "species": {"type": "string", "enum": ["lambda", "kaon"]},
        "f15_path": {"type": "string"},
        "uid": {"type": "integer"}},
        "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=strangeness_origin,
))

register(ToolSpec(
    name="urqmd.channel_scaling",
    description=(
        "Participant scaling of one genealogy category: fractions, per-bin "
        "yields and alpha with bootstrap errors (shared event bootstrap, "
        "seed 20260919). category: 'formation_class', 'mother_family', "
        "'mother_production' or 'root_mechanism'. phase1b supports only "
        "formation_class (no bootstrap errors there)."),
    input_schema={"type": "object", "properties": {
        "dataset": {"type": "string", "enum": ["phase1b", "phase1b2"]},
        "species": {"type": "string", "enum": ["lambda", "kaon"]},
        "category": {"type": "string",
                     "enum": ["formation_class", "mother_family",
                              "mother_production", "root_mechanism"]},
        "n_bootstrap": {"type": "integer", "default": 500}},
        "required": ["dataset", "species", "category"]},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=channel_scaling,
))
