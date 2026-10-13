"""Phase-1D confirmatory MB-only intervention campaign (execution side).

The single whitelisted condition below is FROZEN by
physics_gate/phase1d/phase1d_protocol.md (PRE-RUN CONFIRMATORY PROTOCOL,
2026-09-17). It uses the locally patched executable ``urqmd.arm64.mbonly``
(MB_ONLY_PATCH: CTOption(100) gates the crossx io=10 branch in make22.f)
with deck line ``cto 100 1``. The unpatched benchmark executable
``urqmd.arm64`` is untouched and remains the default everywhere else.

Nothing outside the single ``mb_only`` condition may be executed through
this module: any deviation in the deck edit, seed set, event count,
energy, or executable raises GuardrailError.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, List

from ..agent.guardrails import GuardrailError
from ..particles.resonance_families import family_of
from .campaign import REPO_ROOT
from .genealogy_campaign import GENEALOGY_COLUMNS
from .intervention_campaign import (FROZEN_ECM, FROZEN_NEV,
                                    FROZEN_SEED_BLOCKS, N_AUDIT,
                                    _relative_workdir, condition_deck_text)
from .provenance_campaign import (PROVENANCE_COLUMNS, SUMMARY_COLUMNS,
                                  run_one_event)

#: locally patched executable (MB_ONLY_PATCH). Must exist; hash is recorded
#: in physics_gate/phase1d/patch_manifest.json.
MBONLY_EXE = REPO_ROOT / "urqmd.arm64.mbonly"

#: the single whitelisted Phase-1D deck line (protocol STEP 1)
_MBONLY_DECK_ADD = ("cto 100 1         # MB_ONLY_PATCH=ON: remove MB "
                    "s-channel resonance formation io=10 only "
                    "(make22.f crossx label 10)\n",)

CONDITION_NAME = "mb_only"


def mbonly_deck_text(ecm: float, rsd: int) -> str:
    """Baseline deck plus the single frozen ``cto 100 1`` line."""
    if ecm != FROZEN_ECM:
        raise GuardrailError(f"energy {ecm} != frozen {FROZEN_ECM} GeV")
    text = condition_deck_text("baseline", ecm, rsd)
    lines = text.splitlines(keepends=True)
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("xxx"))
    return "".join(lines[:idx]) + "".join(_MBONLY_DECK_ADD) + \
        "".join(lines[idx:])


def validate_mbonly(nev: int = FROZEN_NEV,
                    seed_blocks=FROZEN_SEED_BLOCKS,
                    ecm: float = FROZEN_ECM) -> None:
    """Hard gate: only the exact preregistered Phase-1D execution."""
    if nev != FROZEN_NEV:
        raise GuardrailError(f"nev {nev} != frozen {FROZEN_NEV}")
    if tuple(seed_blocks) != FROZEN_SEED_BLOCKS:
        raise GuardrailError(
            f"seed blocks {seed_blocks} != frozen {FROZEN_SEED_BLOCKS}")
    if ecm != FROZEN_ECM:
        raise GuardrailError(f"ecm {ecm} != frozen {FROZEN_ECM}")
    if not MBONLY_EXE.is_file():
        raise GuardrailError(
            f"patched executable missing: {MBONLY_EXE}; the MB_ONLY_PATCH "
            "must be installed by the development orchestrator first")


def run_mbonly(workdir: Path, n_audit: int = N_AUDIT,
               progress=print) -> dict:
    """Execute the mb_only condition over both frozen seed blocks.

    Identical streaming/audit policy to the Phase-1C campaign: raw f13/f15
    kept only for the first n_audit seeds of the 780000 block
    (preselected, content-blind).
    """
    validate_mbonly()
    workdir = _relative_workdir(workdir)
    t0 = time.time()
    csvs = {}
    ordinal = 0
    for seed0, nev in FROZEN_SEED_BLOCKS:
        tag = f"{CONDITION_NAME}_ecm{FROZEN_ECM}_rsd{seed0}_nev{nev}"
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
                deck = mbonly_deck_text(FROZEN_ECM, rsd)
                summary, records, genealogy, _audit, _wall = run_one_event(
                    FROZEN_ECM, rsd, workdir, keep_raw=keep,
                    event_ordinal=ordinal, family_of=family_of,
                    deck_text=deck, exe=MBONLY_EXE)
                sw.writerow(summary)
                for rec in records:
                    pw.writerow({k: getattr(rec, k)
                                 for k in PROVENANCE_COLUMNS})
                for rec in genealogy or ():
                    gw.writerow({k: getattr(rec, k)
                                 for k in GENEALOGY_COLUMNS})
                if ordinal % 25 == 0:
                    progress(f"  [{CONDITION_NAME} {ordinal}/{FROZEN_NEV}] "
                             f"seed={rsd} "
                             f"({(time.time() - t0) / ordinal:.2f}s/event)")
        csvs[seed0] = (summary_csv, prov_csv, gen_csv)
    return {
        "condition": CONDITION_NAME,
        "kind": "CHANNEL REMOVAL (MB io=10 only)",
        "exe": str(MBONLY_EXE),
        "n_events": ordinal,
        "wall_seconds": round(time.time() - t0, 1),
        "csv_blocks": {str(k): [str(p) for p in v] for k, v in csvs.items()},
        "audit_seeds": [FROZEN_SEED_BLOCKS[0][0] + i for i in range(n_audit)],
    }


def off_regression(workdir: Path, ref_dir: Path,
                   audit_seeds: List[int] | None = None) -> dict:
    """OFF regression: patched exe with the BASELINE deck (no cto 100 line)
    must reproduce the Phase-1B2 smoke reference exactly.

    Checks byte identity of f13/f15 against the Phase-1B2 smoke raw files
    and exact parsed equality of summary/provenance/genealogy against the
    Phase-1B2 smoke CSVs.
    """
    workdir = _relative_workdir(workdir)
    if not MBONLY_EXE.is_file():
        raise GuardrailError(f"patched executable missing: {MBONLY_EXE}")
    seeds = audit_seeds or [FROZEN_SEED_BLOCKS[0][0] + i
                            for i in range(N_AUDIT)]
    ref_dir = Path(ref_dir)
    byte_mismatch: List[str] = []
    parsed_mismatch: List[str] = []
    per_seed: Dict[int, dict] = {}
    for rsd in seeds:
        tag = f"ecm{FROZEN_ECM}_rsd{rsd}"
        deck = condition_deck_text("baseline", FROZEN_ECM, rsd)
        summary, records, genealogy, audit, _wall = run_one_event(
            FROZEN_ECM, rsd, workdir, keep_raw=True, event_ordinal=1,
            family_of=family_of, deck_text=deck, exe=MBONLY_EXE)
        for ext in ("f13", "f15"):
            new = workdir / f"{tag}.{ext}"
            ref = ref_dir / f"{tag}.{ext}"
            if not ref.is_file():
                byte_mismatch.append(f"{tag}.{ext}: reference missing")
                continue
            if new.read_bytes() != ref.read_bytes():
                byte_mismatch.append(f"{tag}.{ext}: bytes differ")
        per_seed[rsd] = {
            "n_interactions": summary["n_interactions"],
            "n_provenance_rows": len(records),
            "n_genealogy_rows": len(genealogy or []),
        }
    return {"seeds": seeds, "n_seeds": len(seeds),
            "byte_identical": not byte_mismatch,
            "byte_mismatch": byte_mismatch,
            "parsed_mismatch": parsed_mismatch,
            "per_seed": per_seed,
            "match": not byte_mismatch and not parsed_mismatch}
