"""Strict streaming parser for UrQMD 4.0 file13 final-state output.

Supports multi-event files. Records are matched by the exact source-verified
structure documented in urqmd_agent/final_state/schema.py; particle rows are
parsed by the fixed-width format 213. Malformed input raises F13ParseError
with the 1-based source line number; nothing is silently skipped.

The parser streams line-by-line (`iter_f13` is a generator) so
production-scale files can be processed event-by-event without loading the
whole file into memory.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, List, Union

from .schema import PARTICLE_ROW_LEN, F13EventHeader, FinalParticle, FinalStateEvent


class F13ParseError(Exception):
    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        if line_number is not None:
            message = f"line {line_number}: {message}"
        super().__init__(message)


# anchored patterns mirroring the Fortran formatted header lines
_RE_VERSION = re.compile(r"^UQMD   version:\s+(\d+)\s+(\d+)\s+(\d+)\s+output_file\s+13\s*$")
_RE_PROJ = re.compile(
    r"^projectile:\s+\(mass, char\)\s+(\d+)\s+(\d+)\s+target:\s+\(mass, char\)\s+(\d+)\s+(\d+)\s*$")
_RE_BETAS = re.compile(
    r"^transformation betas \(NN,lab,pro\)\s+(\S+)\s+(\S+)\s+(\S+)\s*$")
_RE_IMP = re.compile(
    r"^impact_parameter_real/min/max\(fm\):\s+(\S+)\s+(\S+)\s+(\S+)"
    r"\s+total_cross_section\(mbarn\):\s+(\S+)\s*$")
_RE_GLAUBER = re.compile(
    r"^Participants_Glauber \(Nuc_part,prot_part,neut_part\):\s+(\S+)\s+(\S+)\s+(\S+)"
    r"\s+Eccentricities_Glauber.*$")
_RE_EOS = re.compile(
    r"^equation_of_state:\s+(\d+)\s+E_lab\(GeV/u\):\s+(\S+)\s+sqrt\(s\)\(GeV\):\s+(\S+)"
    r"\s+p_lab\(GeV/u\):\s+(\S+)\s*$")
_RE_EVENT = re.compile(
    r"^event#\s+(\d+)\s+random seed:\s+(-?\d+)\s+\((fixed|auto)\)\s+"
    r"total_time\(fm/c\):\s+(\d+)\s+Delta\(t\)_O\(fm/c\):\s+(\S+)\s*$")
_RE_NPART = re.compile(r"^\s*(\d+)\s+(\d+)\s*$")

_FLOAT_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eEdD][+-]?\d+)?$")
_INT_RE = re.compile(r"^[+-]?\d+$")


def _f(text: str, line_number: int, name: str) -> float:
    t = text.strip()
    if not _FLOAT_RE.match(t):
        raise F13ParseError(f"invalid float for {name}: {text!r}", line_number)
    return float(t.replace("D", "E").replace("d", "E"))


def _i(text: str, line_number: int, name: str) -> int:
    t = text.strip()
    if not _INT_RE.match(t):
        raise F13ParseError(f"invalid integer for {name}: {text!r}", line_number)
    return int(t)


def _match(rx, line, line_number, what):
    m = rx.match(line)
    if not m:
        raise F13ParseError(f"expected {what}, got: {line.rstrip()!r}", line_number)
    return m


class _LineReader:
    """One-line-lookahead reader over a line iterator (streaming)."""

    def __init__(self, line_iter):
        self._iter = iter(line_iter)
        self.pos = 0
        self._buffer = None
        self._eof = False

    def next(self):
        if self._buffer is not None:
            line, self._buffer = self._buffer, None
        else:
            try:
                line = next(self._iter)
            except StopIteration:
                raise F13ParseError("unexpected end of file", self.pos)
        self.pos += 1
        return line, self.pos  # 1-based line number

    def peek(self):
        if self._buffer is None and not self._eof:
            try:
                self._buffer = next(self._iter)
            except StopIteration:
                self._eof = True
        return self._buffer

    def done(self) -> bool:
        return self.peek() is None


def _parse_particle_row(line: str, ln: int) -> FinalParticle:
    """format 213 = (9e16.8, i11, 2i3, i9, i5, i4, 8e16.8), width 307."""
    rec = line.rstrip("\n")
    if len(rec) != PARTICLE_ROW_LEN:
        raise F13ParseError(
            f"particle record width {len(rec)} != {PARTICLE_ROW_LEN}", ln)
    if "*" in rec:
        raise F13ParseError("field overflow marker '*' in record", ln)
    vals = [_f(rec[16 * k : 16 * (k + 1)], ln, f"real{k}") for k in range(9)]
    ityp = _i(rec[144:155], ln, "ityp")
    iso3 = _i(rec[155:158], ln, "iso3")
    chg = _i(rec[158:161], ln, "charge")
    lstcoll = _i(rec[161:170], ln, "lstcoll")
    ncoll = _i(rec[170:175], ln, "ncoll")
    origin = _i(rec[175:179], ln, "origin")
    # freeze-out copies at rec[179:307] are not needed for observables
    return FinalParticle(
        r0=vals[0], rx=vals[1], ry=vals[2], rz=vals[3],
        p0=vals[4], px=vals[5], py=vals[6], pz=vals[7], mass=vals[8],
        ityp=ityp, iso3=iso3, charge=chg,
        lstcoll=lstcoll, ncoll=ncoll, origin=origin, line_number=ln)


def _iter_events(lr: _LineReader) -> Iterator[FinalStateEvent]:
    while not lr.done():
        # --- header block -------------------------------------------------
        line, ln = lr.next()
        _match(_RE_VERSION, line, ln, "'UQMD version' record")

        line, ln2 = lr.next()
        m = _match(_RE_PROJ, line, ln2, "projectile/target record")
        ap, zp, at, zt = (int(m.group(k)) for k in range(1, 5))

        line, ln3 = lr.next()
        m = _match(_RE_BETAS, line, ln3, "transformation betas record")
        betann = _f(m.group(1), ln3, "betann")
        betatar = _f(m.group(2), ln3, "betatar")
        betapro = _f(m.group(3), ln3, "betapro")

        line, ln4 = lr.next()
        m = _match(_RE_IMP, line, ln4, "impact parameter record")
        bimp = _f(m.group(1), ln4, "bimp")
        bmin = _f(m.group(2), ln4, "bmin")
        bmax = _f(m.group(3), ln4, "bmax")
        sigmatot = _f(m.group(4), ln4, "sigmatot")

        line, ln5 = lr.next()
        m = _match(_RE_GLAUBER, line, ln5, "Participants_Glauber record")
        num_part = _f(m.group(1), ln5, "num_part")
        proton_part = _f(m.group(2), ln5, "proton_part")
        neutron_part = _f(m.group(3), ln5, "neutron_part")

        line, ln6 = lr.next()
        m = _match(_RE_EOS, line, ln6, "equation_of_state record")
        eos = int(m.group(1))
        ebeam = _f(m.group(2), ln6, "ebeam")
        sqrts = _f(m.group(3), ln6, "sqrts")
        pbeam = _f(m.group(4), ln6, "pbeam")

        line, ln7 = lr.next()
        m = _match(_RE_EVENT, line, ln7, "event# record")
        event = int(m.group(1))
        ranseed = int(m.group(2))

        # CTOption/CTParam dump: 4 'op' + 7 'pa' lines, then 'pvec' header
        # (defaults CTOption(41)=0, CTOption(57)=1, output.f:253-259)
        for _ in range(4):
            line, lno = lr.next()
            if not line.startswith("op"):
                raise F13ParseError(
                    f"expected 'op' CTOption line, got {line.rstrip()!r}", lno)
        for _ in range(7):
            line, lnp_ = lr.next()
            if not line.startswith("pa"):
                raise F13ParseError(
                    f"expected 'pa' CTParam line, got {line.rstrip()!r}", lnp_)
        line, lnpv = lr.next()
        if not line.startswith("pvec:"):
            raise F13ParseError(
                f"expected 'pvec:' column header, got {line.rstrip()!r}", lnpv)

        # --- npart / statistics / particle rows ---------------------------
        line, lnn = lr.next()
        m = _match(_RE_NPART, line, lnn, "list-directed 'npart ttime' record")
        npart, ttime = int(m.group(1)), int(m.group(2))

        line, lns = lr.next()
        stats = line.split()
        if len(stats) != 8 or not all(_INT_RE.match(x) for x in stats):
            raise F13ParseError(
                f"expected 8-integer statistics record, got {line.rstrip()!r}", lns)
        (itotcoll, nelcoll, iinelcoll, nblcoll,
         dectag, nhardres, nsoftres, ndecres) = (int(x) for x in stats)

        particles: List[FinalParticle] = []
        for _ in range(npart):
            line, lnp2 = lr.next()
            particles.append(_parse_particle_row(line, lnp2))

        # frame assertion: with CTOption(27)=0 the output frame is the NN
        # center-of-mass frame, i.e. betann must be zero, otherwise the
        # midrapidity acceptance would be invalid
        if abs(betann) > 1e-9:
            raise F13ParseError(
                f"betann={betann} != 0: output not in NN c.m. frame; "
                f"rapidity acceptance would be invalid", ln3)

        hdr = F13EventHeader(
            event=event, ranseed=ranseed, ap=ap, zp=zp, at=at, zt=zt,
            bimp=bimp, bmin=bmin, bmax=bmax, sigmatot=sigmatot,
            betann=betann, betatar=betatar, betapro=betapro,
            eos=eos, ebeam=ebeam, sqrts=sqrts, pbeam=pbeam,
            num_part=num_part, proton_part=proton_part,
            neutron_part=neutron_part, npart=npart, ttime=ttime,
            itotcoll=itotcoll, nelcoll=nelcoll, iinelcoll=iinelcoll,
            nblcoll=nblcoll, dectag=dectag, nhardres=nhardres,
            nsoftres=nsoftres, ndecres=ndecres, line_number=ln)

        yield FinalStateEvent(header=hdr, particles=tuple(particles))


def iter_f13(path: Union[str, Path]) -> Iterator[FinalStateEvent]:
    """Iterate over all events in a file13 file (strict, streaming)."""
    path = Path(path)
    if not path.is_file():
        raise F13ParseError(f"file not found: {path}")
    with path.open("r") as fh:
        yield from _iter_events(_LineReader(fh))


def parse_f13(path: Union[str, Path]) -> List[FinalStateEvent]:
    """Parse all events of a file13 file into a list (small files only)."""
    return list(iter_f13(path))
