"""Phase-1B2 genealogy replay campaign (Step 0 data-sufficiency verdict).

Replays the EXACT Phase-1B event campaign (same seeds, same settings — this
is NOT a new statistical sample) and additionally extracts one compact
genealogy row per final strange hadron. After the campaigns, the replayed
summaries are compared row-by-row against the original Phase-1B summary
CSVs (reproducibility gate; any mismatch is a STOP condition).
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from ..history.genealogy import GenealogyRecord
from ..particles.resonance_families import family_of
from .provenance_campaign import (PROVENANCE_COLUMNS, SUMMARY_COLUMNS,
                                  CampaignResult, run_one_event)

GENEALOGY_COLUMNS = tuple(GenealogyRecord.__dataclass_fields__)

#: summary columns that must reproduce the original campaign exactly
_REPRO_COLUMNS = ("seed", "bimp_fm", "n_part_glauber", "n_part_actual",
                  "n_ch", "n_lambda_y05", "n_kaon0_y05", "n_antikaon0_y05",
                  "n_interactions", "n_provenance_records")


@dataclass(frozen=True)
class GenealogyCampaignResult:
    n_events: int
    wall_seconds: float
    summary_csv: Path
    provenance_csv: Path
    genealogy_csv: Path
    audit_files: tuple


def run_campaign_1b2(ecm: float, nev: int, seed0: int, workdir: Path,
                     n_audit: int = 0) -> GenealogyCampaignResult:
    """Stream `nev` single events with genealogy extraction; audit = the
    FIRST n_audit event indices (preselected, content-blind)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tag = f"ecm{ecm}_rsd{seed0}_nev{nev}"
    summary_csv = workdir / f"summary_{tag}.csv"
    prov_csv = workdir / f"provenance_{tag}.csv"
    gen_csv = workdir / f"genealogy_{tag}.csv"
    audit_files: List[Path] = []

    t0 = time.time()
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
            summary, records, genealogy, audit, wall = run_one_event(
                ecm, rsd, workdir, keep_raw=(i < n_audit),
                event_ordinal=i + 1, family_of=family_of)
            sw.writerow(summary)
            for rec in records:
                pw.writerow({k: getattr(rec, k) for k in PROVENANCE_COLUMNS})
            for rec in genealogy or ():
                gw.writerow({k: getattr(rec, k) for k in GENEALOGY_COLUMNS})
            if audit:
                audit_files.extend(audit)
            if (i + 1) % 25 == 0:
                print(f"  [{i + 1}/{nev}] seed={rsd} "
                      f"({(time.time() - t0) / (i + 1):.2f}s/event)",
                      flush=True)
    return GenealogyCampaignResult(
        n_events=nev, wall_seconds=time.time() - t0,
        summary_csv=summary_csv, provenance_csv=prov_csv,
        genealogy_csv=gen_csv, audit_files=tuple(audit_files))


def _load_summaries(path: Path) -> Dict[str, Dict[str, str]]:
    with Path(path).open() as f:
        return {row["seed"]: row for row in csv.DictReader(f)}


def check_replay_reproducibility(original_csvs: Sequence[Path],
                                 replay_csvs: Sequence[Path]) -> List[str]:
    """Row-by-row comparison of replayed vs original Phase-1B summaries
    (matched on seed). Returns a list of discrepancy strings; empty means
    the replay reproduces the original campaign exactly (gate PASSED)."""
    original: Dict[str, Dict[str, str]] = {}
    for p in original_csvs:
        for seed, row in _load_summaries(Path(p)).items():
            if seed in original:
                raise ValueError(f"duplicate seed {seed} in original CSVs")
            original[seed] = row
    replay: Dict[str, Dict[str, str]] = {}
    for p in replay_csvs:
        for seed, row in _load_summaries(Path(p)).items():
            if seed in replay:
                raise ValueError(f"duplicate seed {seed} in replay CSVs")
            replay[seed] = row

    problems: List[str] = []
    missing = sorted(set(original) - set(replay))
    extra = sorted(set(replay) - set(original))
    if missing:
        problems.append(f"{len(missing)} original seeds missing in replay: "
                        f"{missing[:5]}")
    if extra:
        problems.append(f"{len(extra)} replay seeds not in original: "
                        f"{extra[:5]}")
    for seed in sorted(set(original) & set(replay)):
        o, r = original[seed], replay[seed]
        for col in _REPRO_COLUMNS:
            if o[col] != r[col]:
                problems.append(
                    f"seed {seed}: {col} original={o[col]} replay={r[col]}")
    return problems
