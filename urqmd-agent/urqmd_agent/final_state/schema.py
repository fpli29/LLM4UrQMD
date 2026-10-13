"""Immutable schemas for UrQMD 4.0 file13 final-state events.

Format verified against output.f (Phase 0 + Phase 1A source inspection):

Per event the file contains (output.f: entry `output`, formats 101/301/305/
304/1010/303/302/102/103/306, and entry `file13out`, output.f:341-413):

  1. `UQMD   version:` line (101)                      — version info
  2. `projectile:` / `target:` line (301)              — Ap,Zp,At,Zt
  3. `transformation betas (NN,lab,pro)` line (305)    — betann, betatar, betapro
  4. `impact_parameter_real/min/max(fm):` line (304)   — bimp, bmin, bmax, sigmatot
  5. `Participants_Glauber` / `Eccentricities` line (1010) — N_part etc.
  6. `equation_of_state:` line (303)                   — eos, ebeam, sqrt(s), pbeam
  7. `event#` line (302)                               — event, ranseed, times
  8. 4 `op` lines (102) + 7 `pa` lines (103)           — CTOption/CTParam dump
     (defaults CTOption(41)=0, CTOption(57)=1 -> 4 op lines, 7 pa lines,
      output.f:253-259)
  9. `pvec: r0 ...` column header (306)
 10. list-directed `npart ttime` line (output.f:359)
 11. collision-statistics line (202 = 8i8, output.f:362)
 12. npart particle rows, format 213 (output.f:130):
     9e16.8, i11, 2i3, i9, i5, i4, 8e16.8  (total width 307)
     = r0,rx,ry,rz,p0,px,py,pz,m, ityp,iso3,charge, lstcoll,ncoll,origin,
       fr_r0,fr_rx,fr_ry,fr_rz, fr_p0,fr_px,fr_py,fr_pz  (freeze-out copies)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

#: width of a format-213 particle row (chars, without newline)
PARTICLE_ROW_LEN = 9 * 16 + 11 + 3 + 3 + 9 + 5 + 4 + 8 * 16  # 307


@dataclass(frozen=True)
class F13EventHeader:
    event: int
    ranseed: int
    ap: int
    zp: int
    at: int
    zt: int
    bimp: float           # real impact parameter of this event [fm]
    bmin: float
    bmax: float
    sigmatot: float       # mb (0.0 for A+A in this version, see Phase 0)
    betann: float         # must be 0: output momenta are in the NN c.m. frame
    betatar: float
    betapro: float
    eos: int
    ebeam: float          # GeV/u (0 when ecm input is used)
    sqrts: float          # sqrt(s_NN) [GeV] actually simulated
    pbeam: float          # GeV/c per nucleon
    num_part: float       # Glauber participants (init.f init_eccentricity)
    proton_part: float
    neutron_part: float
    npart: int            # final particle count
    ttime: int            # total time [fm/c]
    # collision statistics (format 202)
    itotcoll: int
    nelcoll: int
    iinelcoll: int
    nblcoll: int
    dectag: int
    nhardres: int
    nsoftres: int
    ndecres: int
    line_number: int      # line of the `UQMD version` record


@dataclass(frozen=True)
class FinalParticle:
    r0: float
    rx: float
    ry: float
    rz: float
    p0: float             # energy [GeV] (NN c.m. frame, Fermi momentum included)
    px: float
    py: float
    pz: float
    mass: float
    ityp: int
    iso3: int
    charge: int
    lstcoll: int
    ncoll: int
    origin: int
    line_number: int

    def rapidity_cm(self) -> float:
        """y = 1/2 ln((E+pz)/(E-pz)); valid as c.m. rapidity because the
        output frame is the NN c.m. frame (betann=0, asserted by parser)."""
        import math
        return 0.5 * math.log((self.p0 + self.pz) / (self.p0 - self.pz))


@dataclass(frozen=True)
class FinalStateEvent:
    header: F13EventHeader
    particles: Tuple[FinalParticle, ...]
