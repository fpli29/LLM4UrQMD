"""Strict parser for UrQMD 4.0 file15 collision-history output.

The records are parsed according to the exact fixed-width Fortran formats
verified against the UrQMD 4.0 source in Phase 0 (NOT by whitespace split):

    header   (format 502, output.f:139):  i8, i8, i4, i7, f8.3, 4e12.4
    particle (format 501, output.f:122):  i5, 9e16.8, i11, 2i3, i9, i5, i3, i15

Malformed input raises ParseError with the source line number; nothing is
silently skipped or repaired (project constraint 10).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Union

from .schema import (
    DECAY_PROCESS_ID,
    EVENT_HEADER_MARKER,
    EventHeader,
    HistoryEvent,
    Interaction,
    ParticleSnapshot,
    Role,
)

# Fixed field widths derived from the Fortran formats.
_HEADER_WIDTHS = (8, 8, 4, 7, 8, 12, 12, 12, 12)          # 502
_PARTICLE_WIDTHS = (5, 16, 16, 16, 16, 16, 16, 16, 16, 16, 11, 3, 3, 9, 5, 3, 15)  # 501

HEADER_LEN = sum(_HEADER_WIDTHS)       # 71
PARTICLE_LEN = sum(_PARTICLE_WIDTHS)   # 198


class ParseError(Exception):
    """Malformed file15 record. Carries the 1-based source line number."""

    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        if line_number is not None:
            message = f"line {line_number}: {message}"
        super().__init__(message)


_FLOAT_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eEdD][+-]?\d+)?$")
_INT_RE = re.compile(r"^[+-]?\d+$")


def _slice_fields(line: str, widths: tuple[int, ...], line_number: int) -> List[str]:
    """Cut a record into its fixed-width fields; raise on truncation/overflow."""
    if line.endswith("\n"):
        line = line[:-1]
    expected = sum(widths)
    if len(line) < expected:
        raise ParseError(
            f"truncated record: got {len(line)} chars, expected {expected}",
            line_number,
        )
    if len(line) > expected:
        # Fortran formats have fixed widths; trailing garbage means either a
        # format/version mismatch or a corrupted file. Never ignore it.
        raise ParseError(
            f"record longer than expected: got {len(line)} chars, expected {expected}",
            line_number,
        )
    if "*" in line:
        raise ParseError("field overflow marker '*' in record", line_number)
    fields, pos = [], 0
    for w in widths:
        fields.append(line[pos : pos + w])
        pos += w
    return fields


def _parse_int(field: str, line_number: int, name: str) -> int:
    text = field.strip()
    if not _INT_RE.match(text):
        raise ParseError(f"invalid integer for {name}: {field!r}", line_number)
    return int(text)


def _parse_float(field: str, line_number: int, name: str) -> float:
    text = field.strip()
    if not _FLOAT_RE.match(text):
        raise ParseError(f"invalid float for {name}: {field!r}", line_number)
    # Fortran may print D exponents; normalize.
    return float(text.replace("D", "E").replace("d", "E"))


_HEADER_NAMES = ("nin", "nexit", "iline", "ctag", "acttime",
                 "sqrts", "sigtot", "sigpart", "cdens")
_PARTICLE_NAMES = ("iid", "r0", "rx", "ry", "rz", "p0", "px", "py", "pz",
                   "m", "ityp", "iso3", "charge", "lstcoll", "ncoll",
                   "strangeness", "origin")


def _parse_header(line: str, line_number: int):
    fields = _slice_fields(line, _HEADER_WIDTHS, line_number)
    values = []
    for i, (f, name) in enumerate(zip(fields, _HEADER_NAMES)):
        if i < 4:
            values.append(_parse_int(f, line_number, name))
        else:
            values.append(_parse_float(f, line_number, name))
    return values


def _parse_particle(line: str, line_number: int):
    fields = _slice_fields(line, _PARTICLE_WIDTHS, line_number)
    values = []
    for i, (f, name) in enumerate(zip(fields, _PARTICLE_NAMES)):
        if 1 <= i <= 9:
            values.append(_parse_float(f, line_number, name))
        else:
            values.append(_parse_int(f, line_number, name))
    return values


def parse_f15(path: Union[str, Path]) -> HistoryEvent:
    """Parse one UrQMD 4.0 file15 history file into a HistoryEvent.

    Strict rules (any violation raises ParseError with a line number):
      - first record must be the event header (marker -1)
      - every interaction header must have nin >= 1, nout >= 0
      - exactly nin+nout particle records must follow each header
      - no truncated, over-long, or unexplained records
      - integer fields must be integer-valid (this covers UID validity)
      - exactly one event header per file
    """
    path = Path(path)
    if not path.is_file():
        raise ParseError(f"file not found: {path}")

    with path.open("r") as fh:
        raw_lines = fh.readlines()

    if not raw_lines:
        raise ParseError("empty file")

    header: EventHeader | None = None
    interactions: List[Interaction] = []
    idx = 0
    n_lines = len(raw_lines)

    # --- first record: event header -------------------------------------
    values = _parse_header(raw_lines[0], 1)
    if values[0] != EVENT_HEADER_MARKER:
        raise ParseError(
            f"first record is not an event header: marker={values[0]}, "
            f"expected {EVENT_HEADER_MARKER}", 1)
    header = EventHeader(
        marker=values[0], event=values[1], ap=values[2], at=values[3],
        bimp=values[4], ecm=values[5], sigmatot=values[6],
        ebeam=values[7], pbeam=values[8], line_number=1)
    idx = 1

    # --- interaction records --------------------------------------------
    while idx < n_lines:
        line_number = idx + 1
        values = _parse_header(raw_lines[idx], line_number)
        nin, nout, process_id, ctag = values[0], values[1], values[2], values[3]

        if nin == EVENT_HEADER_MARKER:
            raise ParseError(
                "unexpected second event header (one event per file expected)",
                line_number)
        if nin < 1:
            raise ParseError(f"invalid nin={nin} (must be >= 1)", line_number)
        if nout < 0:
            raise ParseError(f"invalid nexit={nout} (must be >= 0)", line_number)
        if process_id == DECAY_PROCESS_ID and nin != 1:
            raise ParseError(
                f"decay process id {DECAY_PROCESS_ID} with nin={nin} != 1",
                line_number)

        needed = nin + nout
        if idx + 1 + needed > n_lines:
            raise ParseError(
                f"interaction declares {needed} particle rows "
                f"(nin={nin}+nexit={nout}) but only {n_lines - idx - 1} "
                f"lines remain", line_number)

        incoming: List[ParticleSnapshot] = []
        outgoing: List[ParticleSnapshot] = []
        for k in range(needed):
            p_line_number = idx + k + 2
            pv = _parse_particle(raw_lines[idx + 1 + k], p_line_number)
            role = Role.INCOMING if k < nin else Role.OUTGOING
            snap = ParticleSnapshot(
                uid=pv[0], r0=pv[1], rx=pv[2], ry=pv[3], rz=pv[4],
                p0=pv[5], px=pv[6], py=pv[7], pz=pv[8], mass=pv[9],
                ityp=pv[10], iso3=pv[11], charge=pv[12], lstcoll=pv[13],
                ncoll=pv[14], strangeness=pv[15], origin=pv[16],
                interaction_ctag=ctag, role=role,
                ordinal=k if k < nin else k - nin,
                line_number=p_line_number)
            (incoming if k < nin else outgoing).append(snap)

        interactions.append(Interaction(
            nin=nin, nout=nout, process_id=process_id, ctag=ctag,
            time=values[4], sqrts=values[5], sigma_total=values[6],
            sigma_partial=values[7], baryon_density=values[8],
            incoming=tuple(incoming), outgoing=tuple(outgoing),
            line_number=line_number))
        idx += 1 + needed

    if not interactions:
        raise ParseError("no interaction records found")

    return HistoryEvent(header=header, interactions=tuple(interactions),
                        source_path=str(path))
