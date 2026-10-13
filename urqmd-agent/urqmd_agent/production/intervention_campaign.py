"""Preregistered Phase-1C intervention campaign (execution side).

The whitelist below is FROZEN by the Phase-1C-0 preregistration
(physics_gate/phase1c0/phase1c_preregistration.md, including the
2026-09-16 amendment) and the Phase-2C execution instruction. Nothing
outside these five conditions may be executed through this module:
MB_ONLY_PATCH stays DESIGNED_NOT_IMPLEMENTED, and any deviation in the
deck edit, seed set, event count, or energy raises GuardrailError.

Conditions:
    baseline   — standard Phase-1B2 configuration (tim 200 200); the
                 existing Phase-1B2 dataset, re-used after a regression
                 check (bit-reproducible by seeds).
    cto15_1    — CTOption(15)=1: removes MB (iline 10) AND MM (iline 11)
                 s-channel resonance formation. PARTIAL intervention.
    cto59_0    — CTOption(59)=0: removes STRX channels iline 57-62.
                 NEGATIVE CONTROL.
    tim12      — tim 12 12: evolution-time truncation (ORTHOGONAL, broad).
    tim8       — tim 8 8: evolution-time truncation (ORTHOGONAL, broad).
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from ..agent.guardrails import GuardrailError
from ..particles.resonance_families import family_of
from .campaign import INPUT_TEMPLATE
from .genealogy_campaign import GENEALOGY_COLUMNS
from .provenance_campaign import (PROVENANCE_COLUMNS, SUMMARY_COLUMNS,
                                  run_one_event)

FROZEN_ECM = 7.7


def _relative_workdir(workdir: Path) -> Path:
    """UrQMD reads ftnNN paths into character*77 buffers (input.f:23), so
    the workdir must be short: convert to repo-root-relative."""
    from .campaign import REPO_ROOT
    workdir = Path(workdir)
    if workdir.is_absolute():
        workdir = Path(os.path.relpath(workdir, REPO_ROOT))
    if len(str(workdir)) > 55:
        raise GuardrailError(
            f"workdir path too long for UrQMD ftn buffers: {workdir}")
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir
FROZEN_SEED_BLOCKS: Tuple[Tuple[int, int], ...] = ((780000, 100),
                                                   (790000, 1000))
FROZEN_NEV = sum(n for _, n in FROZEN_SEED_BLOCKS)  # 1100
#: preselected, content-blind audit events: the FIRST 20 seeds of the
#: 780000 block (identical choice to Phase 1B/1B2)
N_AUDIT = 20

_F15_STRIP = ("f15               # suppress unit 15 history output "
              "in production runs\n")


@dataclass(frozen=True)
class InterventionSpec:
    name: str
    kind: str                 # CHANNEL REMOVAL / EVOLUTION-TIME TRUNCATION
    deck_add: Tuple[str, ...] = ()
    deck_replace: Tuple[Tuple[str, str], ...] = ()
    description: str = ""


WHITELIST: Dict[str, InterventionSpec] = {
    "baseline": InterventionSpec(
        "baseline", "BASELINE",
        description="standard Phase-1B2 configuration, tim 200 200"),
    "cto15_1": InterventionSpec(
        "cto15_1", "CHANNEL REMOVAL (PARTIAL: MB+MM)",
        deck_add=("cto 15 1          # CTOption(15)=1: remove s-channel "
                  "resonance formation, MB iline=10 AND MM iline=11 "
                  "(anndec.f:53-64)",),
        description="primary partial intervention (preregistration sec. "
                    "'Selected primary intervention')"),
    "cto59_0": InterventionSpec(
        "cto59_0", "CHANNEL REMOVAL (STRX iline 57-62)",
        deck_add=("cto 59 0          # CTOption(59)=0: remove STRX channels "
                  "iline 57-62 (make22.f:6132-6183)",),
        description="negative control"),
    "tim12": InterventionSpec(
        "tim12", "EVOLUTION-TIME TRUNCATION",
        deck_replace=(("tim 200 200", "tim 12 12"),),
        description="orthogonal temporal test 1 (frozen cut time)"),
    "tim8": InterventionSpec(
        "tim8", "EVOLUTION-TIME TRUNCATION",
        deck_replace=(("tim 200 200", "tim 8 8"),),
        description="orthogonal temporal test 2 (frozen cut time)"),
}


def condition_deck_text(name: str, ecm: float, rsd: int) -> str:
    """Render the input deck for a whitelisted condition (history ON)."""
    try:
        spec = WHITELIST[name]
    except KeyError:
        raise GuardrailError(
            f"intervention {name!r} is not in the preregistered whitelist; "
            f"allowed: {sorted(WHITELIST)}"
        ) from None
    if ecm != FROZEN_ECM:
        raise GuardrailError(f"energy {ecm} != frozen {FROZEN_ECM} GeV")
    text = INPUT_TEMPLATE.format(ecm=ecm, nev=1, rsd=rsd)
    text = text.replace(_F15_STRIP, "")
    for old, new in spec.deck_replace:
        if old not in text:
            raise GuardrailError(f"deck line {old!r} not found for {name}")
        text = text.replace(old, new)
    if spec.deck_add:
        lines = text.splitlines(keepends=True)
        idx = next(i for i, ln in enumerate(lines) if ln.startswith("xxx"))
        text = "".join(lines[:idx]) + "\n".join(spec.deck_add) + "\n" + \
            "".join(lines[idx:])
    return text


def validate_preregistered_intervention(
    name: str,
    nev: int = FROZEN_NEV,
    seed_blocks: Tuple[Tuple[int, int], ...] = FROZEN_SEED_BLOCKS,
    ecm: float = FROZEN_ECM,
) -> InterventionSpec:
    """Hard gate: only the exact preregistered execution may proceed."""
    spec = WHITELIST.get(name)
    if spec is None:
        raise GuardrailError(
            f"intervention {name!r} not whitelisted; allowed: "
            f"{sorted(WHITELIST)}. MB_ONLY_PATCH is DESIGNED_NOT_IMPLEMENTED "
            "and remains blocked.")
    if nev != FROZEN_NEV:
        raise GuardrailError(f"nev {nev} != frozen {FROZEN_NEV}")
    if tuple(seed_blocks) != FROZEN_SEED_BLOCKS:
        raise GuardrailError(
            f"seed blocks {seed_blocks} != frozen {FROZEN_SEED_BLOCKS}")
    if ecm != FROZEN_ECM:
        raise GuardrailError(f"ecm {ecm} != frozen {FROZEN_ECM}")
    return spec


def run_condition(name: str, workdir: Path, n_audit: int = N_AUDIT,
                  progress=print) -> dict:
    """Execute one whitelisted condition over both frozen seed blocks.

    Streaming: run -> parse -> provenance + genealogy extraction -> closure
    validation -> delete raw f13/f15, except the FIRST n_audit events of the
    780000 block (preselected, content-blind).
    """
    spec = validate_preregistered_intervention(name)
    workdir = _relative_workdir(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    rows_summary: List[dict] = []
    t0 = time.time()
    csvs = {}
    ordinal = 0
    for seed0, nev in FROZEN_SEED_BLOCKS:
        tag = f"{name}_ecm{FROZEN_ECM}_rsd{seed0}_nev{nev}"
        summary_csv = workdir / f"summary_{tag}.csv"
        prov_csv = workdir / f"provenance_{tag}.csv"
        gen_csv = workdir / f"genealogy_{tag}.csv"
        with summary_csv.open("w", newline="") as sf, \
                prov_csv.open("w", newline="") as pf, \
                gen_csv.open("w", newline="") as gf:
            sw = csv.DictWriter(sf, fieldnames=list(SUMMARY_COLUMNS))
            pw = csv.DictWriter(pf, fieldnames=list(PROVENANCE_COLUMNS))
            gw = csv.DictWriter(gf, fieldnames=list(GENEALOGY_COLUMNS))
            sw.writeheader()
            pw.writeheader()
            gw.writeheader()
            for i in range(nev):
                rsd = seed0 + i
                ordinal += 1
                keep = (seed0 == FROZEN_SEED_BLOCKS[0][0]) and i < n_audit
                deck = condition_deck_text(name, FROZEN_ECM, rsd)
                summary, records, genealogy, _audit, _wall = run_one_event(
                    FROZEN_ECM, rsd, workdir, keep_raw=keep,
                    event_ordinal=ordinal, family_of=family_of,
                    deck_text=deck)
                sw.writerow(summary)
                rows_summary.append(summary)
                for rec in records:
                    pw.writerow({k: getattr(rec, k)
                                 for k in PROVENANCE_COLUMNS})
                for rec in genealogy or ():
                    gw.writerow({k: getattr(rec, k)
                                 for k in GENEALOGY_COLUMNS})
                if ordinal % 25 == 0:
                    progress(f"  [{name} {ordinal}/{FROZEN_NEV}] seed={rsd} "
                             f"({(time.time() - t0) / ordinal:.2f}s/event)")
        csvs[seed0] = (summary_csv, prov_csv, gen_csv)
    return {
        "condition": name, "kind": spec.kind, "n_events": ordinal,
        "wall_seconds": round(time.time() - t0, 1),
        "csv_blocks": {str(k): [str(p) for p in v] for k, v in csvs.items()},
        "audit_seeds": [FROZEN_SEED_BLOCKS[0][0] + i for i in range(n_audit)],
    }


def baseline_regression_check(workdir: Path, phase1b2_smoke: Path) -> dict:
    """Reproduce baseline seed 780000 and diff against the Phase-1B2 row."""
    workdir = _relative_workdir(workdir)
    deck = condition_deck_text("baseline", FROZEN_ECM, 780000)
    summary, records, genealogy, _a, _w = run_one_event(
        FROZEN_ECM, 780000, workdir, keep_raw=False, event_ordinal=1,
        family_of=family_of, deck_text=deck)
    ref_csv = Path(phase1b2_smoke) / "summary_ecm7.7_rsd780000_nev100.csv"
    ref = None
    with ref_csv.open() as fh:
        for row in csv.DictReader(fh):
            if int(row["seed"]) == 780000:
                ref = row
                break
    if ref is None:
        raise GuardrailError(f"seed 780000 not found in {ref_csv}")
    keys = ("sqrt_sNN_actual", "bimp_fm", "n_part_glauber", "n_part_actual",
            "n_ch", "n_lambda_y05", "n_kaon0_y05", "n_antikaon0_y05",
            "n_interactions", "n_provenance_records", "max_dE", "max_dp",
            "n_charge_mismatch", "n_strangeness_mismatch")
    diffs = {k: (ref[k], summary[k]) for k in keys
             if str(ref[k]) != str(summary[k])}
    return {"seed": 780000, "match": not diffs, "diffs": diffs,
            "n_provenance_rows": len(records),
            "n_genealogy_rows": len(genealogy or [])}
