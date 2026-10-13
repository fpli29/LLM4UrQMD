"""Shared helpers for the tool layer: knowledge catalog + dataset resolution.

Internal module; not a tool itself. Nothing here imports matplotlib or runs
UrQMD.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

from ..core import paths
from ..core.errors import ToolError

_CAMPAIGN_RE = re.compile(
    r"^(summary|provenance|genealogy)_ecm(?P<ecm>[\d.]+)_rsd(?P<seed>\d+)"
    r"_nev(?P<nev>\d+)\.csv$")


@lru_cache(maxsize=1)
def load_catalog() -> Dict:
    """Load the human-reviewed knowledge snapshot (read-only)."""
    if not paths.KNOWLEDGE_SNAPSHOT.is_file():
        raise ToolError(
            f"knowledge snapshot missing: {paths.KNOWLEDGE_SNAPSHOT}")
    with paths.KNOWLEDGE_SNAPSHOT.open() as fh:
        return json.load(fh)


def _campaign_files(root: Path, kind: str) -> Dict[str, Path]:
    """kind -> {match_key: path} for campaign CSVs directly under root."""
    out: Dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.glob(f"{kind}_*.csv")):
        m = _CAMPAIGN_RE.match(p.name)
        if m:
            out[f"{m.group('ecm')}_{m.group('seed')}_{m.group('nev')}"] = p
    return out


def resolve_phase1b_pairs() -> List[Tuple[Path, Path]]:
    """(summary_csv, provenance_csv) pairs from all Phase-1B data dirs,
    matched by campaign key (ecm/seed/nev) in the filename."""
    pairs: List[Tuple[Path, Path]] = []
    for sub in ("smoke", "pilot"):
        root = paths.PHASE1B_DATA / sub
        summaries = _campaign_files(root, "summary")
        provenance = _campaign_files(root, "provenance")
        for key in sorted(summaries):
            if key not in provenance:
                raise ToolError(
                    f"phase1b {sub}: summary {summaries[key].name} has no "
                    f"matching provenance CSV")
            pairs.append((summaries[key], provenance[key]))
    if not pairs:
        raise ToolError(f"no phase1b campaign CSVs found under "
                        f"{paths.PHASE1B_DATA}")
    return pairs


def resolve_phase1b2_triples() -> List[Tuple[Path, Path, Path]]:
    """(summary_csv, provenance_csv, genealogy_csv) triples from all
    Phase-1B2 data dirs, matched by campaign key."""
    triples: List[Tuple[Path, Path, Path]] = []
    for sub in ("smoke", "pilot"):
        root = paths.PHASE1B2_DATA / sub
        summaries = _campaign_files(root, "summary")
        provenance = _campaign_files(root, "provenance")
        genealogy = _campaign_files(root, "genealogy")
        for key in sorted(summaries):
            if key not in provenance or key not in genealogy:
                raise ToolError(
                    f"phase1b2 {sub}: incomplete triple for campaign {key}")
            triples.append((summaries[key], provenance[key],
                            genealogy[key]))
    if not triples:
        raise ToolError(f"no phase1b2 campaign CSVs found under "
                        f"{paths.PHASE1B2_DATA}")
    return triples


def resolve_summary_csvs(dataset: str) -> List[Path]:
    """Summary CSVs for scaling/centrality tools."""
    if dataset == "phase1b":
        return [s for s, _ in resolve_phase1b_pairs()]
    if dataset == "phase1b2":
        return [s for s, _, _ in resolve_phase1b2_triples()]
    raise ToolError(
        f"unknown dataset {dataset!r}; known datasets: 'phase1b', 'phase1b2'")


def load_event_rows(csvs: List[Path]):
    """Load campaign summary CSVs into scaling.EventRow lists.

    Thin format adapter only: Phase-1A summaries carry n_neutral_kaon_y05;
    Phase-1B/1B2 summaries carry n_kaon0_y05 + n_antikaon0_y05, which sum
    to the same quantity. No analysis logic lives here."""
    import csv as _csv

    from ..analysis.scaling import EventRow
    rows = []
    for path in csvs:
        with open(path) as fh:
            for rec in _csv.DictReader(fh):
                if "n_neutral_kaon_y05" in rec:
                    n_k = int(rec["n_neutral_kaon_y05"])
                else:
                    n_k = int(rec["n_kaon0_y05"]) + int(rec["n_antikaon0_y05"])
                rows.append(EventRow(
                    n_ch=int(rec["n_ch"]),
                    n_part=float(rec["n_part_glauber"]),
                    n_lambda=int(rec["n_lambda_y05"]),
                    n_neutral_kaon=n_k,
                    event_id=int(rec["event_id"]),
                    seed=int(rec["seed"])))
    if not rows:
        raise ToolError(f"no events loaded from {csvs}")
    return rows


def resolve_repo_path(p: str) -> Path:
    """Resolve a user-supplied path (repo-relative or absolute) to an
    existing file."""
    path = Path(p)
    if not path.is_absolute():
        path = paths.REPO_ROOT / path
    if not path.is_file():
        raise ToolError(f"file not found: {path}")
    return path
