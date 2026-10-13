"""Phase-1B streaming provenance production (Step 7).

Per event:
    UrQMD (nev=1, f13+f15) -> strict parse -> reaction graph
    -> provenance extraction -> compact CSV rows -> per-event validation
    -> delete raw f13/f15 (unless the event index is in the preselected
    audit set, chosen BEFORE any microscopic content is inspected).

Zero-interaction peripheral events (empty file15) are valid minimum-bias
physics: they are recorded with zero provenance after verifying that the
f13 final state contains no Lambda/K0/anti-K0 (impossible without
collisions). Anything else raises.

Closure (per event, exact):
    #Lambda records            == f13 n_lambda (|y|<0.5)
    #K0 records                == f13 n_kaon0
    #antiK0 records            == f13 n_antikaon0
    sum of obs weights over K  == 0.5*(N_K0 + N_antiK0)
"""

from __future__ import annotations

import csv
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..final_state.observables import event_observables
from ..final_state.parse_f13 import parse_f13
from ..history.parse_f15 import ParseError, parse_f15
from ..history.provenance import (ProvenanceRecord,
                                  extract_event_provenance, npart_actual)
from ..history.reaction_graph import build_graph
from ..history.taxonomy import classify
from ..history.validate import conservation_diagnostics, validate_structure
from .campaign import EXE, INPUT_TEMPLATE, REPO_ROOT, _check_environment

SUMMARY_COLUMNS = (
    "event_id", "seed", "sqrt_sNN_actual", "bimp_fm", "n_part_glauber",
    "n_part_actual", "n_ch", "n_lambda_y05", "n_kaon0_y05",
    "n_antikaon0_y05", "n_interactions", "n_provenance_records",
    "max_dE", "max_dp", "n_charge_mismatch", "n_strangeness_mismatch",
)

PROVENANCE_COLUMNS = tuple(ProvenanceRecord.__dataclass_fields__)


class ProvenanceValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CampaignResult:
    n_events: int
    wall_seconds: float
    summary_csv: Path
    provenance_csv: Path
    audit_files: tuple


def _write_input(ecm: float, rsd: int, path: Path) -> None:
    text = INPUT_TEMPLATE.format(ecm=ecm, nev=1, rsd=rsd).replace(
        "f15               # suppress unit 15 history output in production runs\n",
        "")
    path.write_text(text)


def run_one_event(ecm: float, rsd: int, workdir: Path, keep_raw: bool,
                  event_ordinal: int | None = None, family_of=None,
                  deck_text: str | None = None,
                  exe: Path | None = None):
    """Run one event, extract provenance, validate, clean up.

    When `family_of` (a source-verified ityp/iso3 -> family classifier) is
    given, Phase-1B2 genealogy records are extracted as well.

    `deck_text`, when given, replaces the default input deck verbatim
    (used by the preregistered Phase-1C intervention campaign; callers must
    pass text from intervention_campaign.condition_deck_text, which enforces
    the frozen whitelist).

    `exe`, when given, replaces the default UrQMD executable (used by the
    Phase-1D confirmatory campaign with the locally patched
    MB_ONLY_PATCH binary; callers must go through
    mbonly_campaign, which enforces the frozen whitelist).

    Returns (summary_row_dict, [ProvenanceRecord], [GenealogyRecord]|None,
    audit_paths_or_None, wall_seconds)."""
    _check_environment()
    tag = f"ecm{ecm}_rsd{rsd}"
    inputfile = workdir / f"input_{tag}"
    f13 = workdir / f"{tag}.f13"
    f15 = workdir / f"{tag}.f15"
    log = workdir / f"{tag}.log"
    if deck_text is None:
        _write_input(ecm, rsd, inputfile)
    else:
        inputfile.write_text(deck_text)

    env = dict(os.environ)
    env["ftn09"] = str(inputfile)
    env["ftn13"] = str(f13)
    env["ftn15"] = str(f15)
    for k in ("ftn14", "ftn16", "ftn19", "ftn20"):
        env.pop(k, None)

    t0 = time.time()
    with log.open("w") as lf:
        proc = subprocess.run([str(exe if exe is not None else EXE)],
                              cwd=REPO_ROOT, env=env,
                              stdout=lf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"run failed (exit {proc.returncode}), see {log}")

    ev13 = parse_f13(f13)
    if len(ev13) != 1:
        raise ProvenanceValidationError(f"expected 1 f13 event in {f13}")
    obs = event_observables(ev13[0])
    if abs(obs.sqrts - ecm) > 1e-3:
        raise ProvenanceValidationError(
            f"sqrt(s) mismatch: target {ecm}, got {obs.sqrts}")

    n_inter = 0
    max_dE = max_dp = 0.0
    n_q_mis = n_s_mis = 0
    npa = 0
    records: List[ProvenanceRecord] = []
    genealogy = None
    empty_history = (not f15.is_file()) or f15.stat().st_size == 0
    if not empty_history:
        try:
            ev15 = parse_f15(f15)
        except ParseError as exc:
            if "no interaction records" in str(exc):
                empty_history = True
            else:
                raise
    if empty_history:
        if obs.n_lambda or obs.n_kaon0 or obs.n_antikaon0:
            raise ProvenanceValidationError(
                f"zero-interaction event with strange final state: "
                f"lam={obs.n_lambda} k0={obs.n_kaon0} ak0={obs.n_antikaon0}")
    else:
        struct = validate_structure(ev15)
        if not struct.ok:
            raise ProvenanceValidationError(f"structure errors: {struct}")
        cons = conservation_diagnostics(ev15)
        max_dE = cons.max_dE
        max_dp = max(cons.max_dpx, cons.max_dpy, cons.max_dpz)
        n_q_mis = len(cons.charge_mismatches)
        n_s_mis = len(cons.strangeness_mismatches)
        graph = build_graph(ev15)
        n_inter = len(ev15.interactions)
        npa = npart_actual(graph, ev15.header.ap, ev15.header.at)
        records = extract_event_provenance(
            graph, event_id=event_ordinal or obs.event, n_ch=obs.n_ch,
            npart_glauber=obs.n_part, bimp=obs.bimp, classify=classify,
            ap=ev15.header.ap, at=ev15.header.at)
        if family_of is not None:
            from ..history.genealogy import extract_event_genealogy
            genealogy = extract_event_genealogy(
                graph, event_id=event_ordinal or obs.event, n_ch=obs.n_ch,
                npart_glauber=obs.n_part, npart_actual=npa, bimp=obs.bimp,
                classify=classify, family_of=family_of)

    # --- exact closure -------------------------------------------------
    n_lam_rec = sum(1 for r in records if r.final_species == "Lambda")
    n_k0_rec = sum(1 for r in records if r.final_species == "K0")
    n_ak0_rec = sum(1 for r in records if r.final_species == "antiK0")
    if n_lam_rec != obs.n_lambda:
        raise ProvenanceValidationError(
            f"Lambda closure failed: {n_lam_rec} records vs {obs.n_lambda}")
    if n_k0_rec != obs.n_kaon0 or n_ak0_rec != obs.n_antikaon0:
        raise ProvenanceValidationError(
            f"K0 closure failed: {n_k0_rec}+{n_ak0_rec} records vs "
            f"{obs.n_kaon0}+{obs.n_antikaon0}")
    w_lam = sum(r.obs_weight for r in records if r.final_species == "Lambda")
    w_k = sum(r.obs_weight for r in records if r.final_species != "Lambda")
    if abs(w_lam - obs.n_lambda) > 1e-12:
        raise ProvenanceValidationError("Lambda weight closure failed")
    if abs(w_k - 0.5 * (obs.n_kaon0 + obs.n_antikaon0)) > 1e-12:
        raise ProvenanceValidationError("K0 weight closure failed")
    if genealogy is not None:
        if len(genealogy) != len(records):
            raise ProvenanceValidationError(
                f"genealogy/provenance row mismatch: {len(genealogy)} vs "
                f"{len(records)}")
        gw_k = sum(r.final_weight for r in genealogy
                   if r.final_species != "Lambda")
        if abs(gw_k - w_k) > 1e-12:
            raise ProvenanceValidationError("genealogy K0 weight closure failed")

    summary = {
        "event_id": event_ordinal or obs.event,
        "seed": obs.ranseed,
        "sqrt_sNN_actual": f"{obs.sqrts:.4f}", "bimp_fm": f"{obs.bimp:.4f}",
        "n_part_glauber": f"{obs.n_part:.1f}", "n_part_actual": npa,
        "n_ch": obs.n_ch, "n_lambda_y05": obs.n_lambda,
        "n_kaon0_y05": obs.n_kaon0, "n_antikaon0_y05": obs.n_antikaon0,
        "n_interactions": n_inter, "n_provenance_records": len(records),
        "max_dE": f"{max_dE:.3e}", "max_dp": f"{max_dp:.3e}",
        "n_charge_mismatch": n_q_mis, "n_strangeness_mismatch": n_s_mis,
    }

    audit = None
    if keep_raw:
        audit = (f13, f15)
    else:
        # delete ONLY after successful parse + validation (all checks above)
        _cleanup_raw([f13, f15, log, inputfile], validated=True)
    return summary, records, genealogy, audit, wall


def _cleanup_raw(paths, validated: bool) -> None:
    """Remove raw run files only when validation succeeded; never delete
    anything after a failed validation (evidence preserved)."""
    if not validated:
        return
    for p in paths:
        Path(p).unlink(missing_ok=True)


def run_campaign(ecm: float, nev: int, seed0: int, workdir: Path,
                 n_audit: int = 20) -> CampaignResult:
    """Stream `nev` single events; audit = the FIRST n_audit event indices
    (preselected before any microscopic content is seen)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    summary_csv = workdir / f"summary_ecm{ecm}_rsd{seed0}_nev{nev}.csv"
    prov_csv = workdir / f"provenance_ecm{ecm}_rsd{seed0}_nev{nev}.csv"
    audit_files: List[Path] = []

    t0 = time.time()
    with summary_csv.open("w", newline="") as sf, \
            prov_csv.open("w", newline="") as pf:
        sw = csv.DictWriter(sf, fieldnames=list(SUMMARY_COLUMNS))
        pw = csv.DictWriter(pf, fieldnames=list(PROVENANCE_COLUMNS))
        sw.writeheader()
        pw.writeheader()
        for i in range(nev):
            rsd = seed0 + i
            summary, records, _gen, audit, wall = run_one_event(
                ecm, rsd, workdir, keep_raw=(i < n_audit),
                event_ordinal=i + 1)
            sw.writerow(summary)
            for rec in records:
                pw.writerow({k: getattr(rec, k) for k in PROVENANCE_COLUMNS})
            if audit:
                audit_files.extend(audit)
            if (i + 1) % 25 == 0:
                print(f"  [{i + 1}/{nev}] seed={rsd} "
                      f"({(time.time() - t0) / (i + 1):.2f}s/event)",
                      flush=True)
    return CampaignResult(n_events=nev, wall_seconds=time.time() - t0,
                          summary_csv=summary_csv, provenance_csv=prov_csv,
                          audit_files=tuple(audit_files))
