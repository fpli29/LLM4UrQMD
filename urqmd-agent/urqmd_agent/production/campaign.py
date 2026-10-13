"""Production driver: run UrQMD events, extract compact summaries, discard raw.

Flow per run (project Step 5/6):
    UrQMD run -> stream-parse f13 event-wise -> validate each event
    -> append compact CSV row -> delete raw f13 only after the whole file
    parsed and validated successfully.

Raw file15 histories are NEVER produced in production runs (ftn15 unset).
Audit histories come from dedicated single-event runs (audit_event).
"""

from __future__ import annotations

import csv
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..core.paths import EXE, REPO_ROOT
from ..final_state.observables import CSV_COLUMNS, event_observables, to_csv_row
from ..final_state.parse_f13 import F13ParseError, iter_f13

INPUT_TEMPLATE = """\
# UrQMD-Agent Phase 1A production input (auto-generated, see physics_gate/protocol.md)
pro 197 79        # Au
tar 197 79        # Au
ecm {ecm}         # sqrt(s_NN) [GeV] - fixed CM energy (input.f:684-700)
imp 40.           # bdist; capped by source at nucrad(Ap)+nucrad(At)+2*CTParam(30)
cto 5 1           # CTOption(5)=1: random bimp uniform in b^2 (init.f:425-434)
nev {nev}
rsd {rsd}         # fixed seed
tim 200 200
cto 56 1          # unique particle IDs in file15 (used by audit runs)
f15               # suppress unit 15 history output in production runs
f14
f16
f19
f20
xxx
"""


@dataclass(frozen=True)
class RunResult:
    n_events: int
    wall_seconds: float
    f13_bytes: int
    csv_path: Path
    deleted_raw: bool


def _check_environment() -> None:
    if not EXE.is_file():
        raise RuntimeError(f"UrQMD executable missing: {EXE}")
    if not (REPO_ROOT / "tables.dat").is_file():
        raise RuntimeError("tables.dat missing - run the build first")


def run_production(ecm: float, nev: int, rsd: int, workdir: Path,
                   keep_raw: bool = False) -> RunResult:
    """Run `nev` minimum-bias Au+Au events at sqrt(s_NN)=ecm and write one
    compact CSV row per event. Raw f13 is deleted after successful parsing
    unless keep_raw=True. Never deletes before successful validation."""
    _check_environment()
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    inputfile = workdir / f"input_ecm{ecm}_rsd{rsd}_nev{nev}"
    f13 = workdir / f"out_ecm{ecm}_rsd{rsd}_nev{nev}.f13"
    csv_path = workdir / f"summary_ecm{ecm}_rsd{rsd}_nev{nev}.csv"
    log = workdir / f"run_ecm{ecm}_rsd{rsd}_nev{nev}.log"

    inputfile.write_text(INPUT_TEMPLATE.format(ecm=ecm, nev=nev, rsd=rsd))

    env = dict(os.environ)
    env["ftn09"] = str(inputfile)
    env["ftn13"] = str(f13)
    for k in ("ftn14", "ftn15", "ftn16", "ftn19", "ftn20"):
        env.pop(k, None)

    t0 = time.time()
    with log.open("w") as lf:
        proc = subprocess.run([str(EXE)], cwd=REPO_ROOT, env=env,
                              stdout=lf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"UrQMD run failed (exit {proc.returncode}), see {log}")
    if not f13.is_file() or f13.stat().st_size == 0:
        raise RuntimeError(f"f13 output missing/empty: {f13}")
    f13_bytes = f13.stat().st_size

    # --- event-wise parse + validate + summarize --------------------------
    n_events = 0
    with csv_path.open("w", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["sqrt_sNN_target"] + list(CSV_COLUMNS))
        for ev in iter_f13(f13):
            hdr = ev.header
            if abs(hdr.sqrts - ecm) > 1e-3:
                raise F13ParseError(
                    f"sqrt(s) mismatch: target {ecm}, got {hdr.sqrts}",
                    hdr.line_number)
            if hdr.ap != 197 or hdr.at != 197:
                raise F13ParseError("unexpected collision system",
                                    hdr.line_number)
            obs = event_observables(ev)
            writer.writerow([f"{ecm:.4f}"] + to_csv_row(obs).split(","))
            n_events += 1
    if n_events != nev:
        raise F13ParseError(f"expected {nev} events, parsed {n_events}")

    deleted = False
    if not keep_raw:
        f13.unlink()          # only after full successful parse+validation
        deleted = True
    return RunResult(n_events=n_events, wall_seconds=wall,
                     f13_bytes=f13_bytes, csv_path=csv_path,
                     deleted_raw=deleted)


def audit_event(ecm: float, rsd: int, workdir: Path,
                max_retries: int = 20) -> dict:
    """Run ONE event with file15 history kept for microscopic audit.

    Minimum-bias sampling can draw a peripheral event with zero collisions;
    file15 then contains an event header but no interaction records. That is
    legitimate physics but useless as a history audit fixture, so the seed is
    advanced until an event with >= 1 interaction is found. The actual seed
    used is reported."""
    from ..history.parse_f15 import ParseError
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return _audit_single(ecm, rsd + attempt, workdir)
        except ParseError as exc:
            if "no interaction records" in str(exc):
                last_exc = exc
                continue
            raise
    raise RuntimeError(
        f"audit_event: {max_retries} consecutive zero-interaction events "
        f"from seed {rsd} at ecm={ecm}") from last_exc


def _audit_single(ecm: float, rsd: int, workdir: Path) -> dict:
    from ..history.parse_f15 import parse_f15, ParseError
    _check_environment()
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tag = f"ecm{ecm}_rsd{rsd}_audit"
    inputfile = workdir / f"input_{tag}"
    f13 = workdir / f"{tag}.f13"
    f15 = workdir / f"{tag}.f15"
    log = workdir / f"{tag}.log"

    text = INPUT_TEMPLATE.format(ecm=ecm, nev=1, rsd=rsd).replace(
        "f15               # suppress unit 15 history output in production runs\n", "")
    inputfile.write_text(text)

    env = dict(os.environ)
    env["ftn09"] = str(inputfile)
    env["ftn13"] = str(f13)
    env["ftn15"] = str(f15)
    for k in ("ftn14", "ftn16", "ftn19", "ftn20"):
        env.pop(k, None)

    t0 = time.time()
    with log.open("w") as lf:
        proc = subprocess.run([str(EXE)], cwd=REPO_ROOT, env=env,
                              stdout=lf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"audit run failed (exit {proc.returncode}), see {log}")

    from ..final_state.parse_f13 import parse_f13 as p13
    ev15 = parse_f15(f15)   # validate before anything else
    ev13 = p13(f13)
    f13.unlink()            # f13 not needed for audit; f15 retained
    return {
        "f15_path": str(f15), "f15_bytes": f15.stat().st_size,
        "wall_seconds": wall, "n_interactions": ev15.n_interactions,
        "n_final": ev13[0].header.npart, "bimp": ev13[0].header.bimp,
        "n_part": ev13[0].header.num_part, "seed_used": rsd,
    }
