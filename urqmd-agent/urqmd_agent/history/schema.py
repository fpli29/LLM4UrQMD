"""Immutable data schemas for UrQMD 4.0 file15 collision-history records.

Ground truth (verified against the UrQMD 4.0 source in Phase 0, see
phase0/source_map.md and docs/history_format.md):

- event header / interaction header: Fortran format 502 = (i8,i8,i4,i7,f8.3,4e12.4)
- particle record:                   Fortran format 501 = (i5,9e16.8,i11,2i3,i9,i5,i3,i15)

All numerical values are stored exactly as parsed from the fixed-width record.
No particle names are inferred here: `ityp`/`iso3` are kept as raw UrQMD
integers because no verified local mapping table has been parsed yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Role(Enum):
    """Role of a particle snapshot within an interaction record."""

    INCOMING = "in"
    OUTGOING = "out"


#: UrQMD process ID written for decays (scatter.f:173, iline=20). Verified in
#: phase0/source_map.md. Wall collisions (80/81) only occur in box mode and do
#: not appear in collision (non-box) runs.
DECAY_PROCESS_ID = 20

#: Marker written as the first field of the per-event header record
#: (output.f:247 writes -1, event, Ap, At, bimp, ecm, sigmatot, ebeam, pbeam).
EVENT_HEADER_MARKER = -1


@dataclass(frozen=True)
class EventHeader:
    """Per-event header record of file15 (format 502 with nin = -1 marker).

    Field mapping from output.f:247:
        write(iou(15),502) -1, event, Ap, At, bimp, ecm, sigmatot, ebeam, pbeam
    """

    marker: int          # always -1 (EVENT_HEADER_MARKER)
    event: int           # event number
    ap: int              # projectile mass number
    at: int              # target mass number
    bimp: float          # impact parameter [fm]
    ecm: float           # sqrt(s_NN) [GeV]
    sigmatot: float      # total projectile-target cross section [mb] (0.0 in A+A, see Phase 0 report)
    ebeam: float         # beam energy per nucleon [GeV/u]
    pbeam: float         # beam momentum per nucleon [GeV/c]
    line_number: int     # 1-based line number in the source file


@dataclass(frozen=True)
class ParticleSnapshot:
    """One particle record of file15 (format 501).

    This is a *state* of a particle (identified by `uid`) immediately before
    (role=INCOMING) or after (role=OUTGOING) the interaction identified by
    `interaction_ctag`. It is NOT the particle identity itself: the same uid
    appears in multiple snapshots along its worldline, and may even appear as
    both incoming and outgoing of the same interaction (identity-preserving
    scattering).

    Field mapping from output.f:613-616 / 625-628 (with CTOption(56)=1 the
    first field is the unique lifetime ID `uid`, not the slot index):
        uid, r0, rx, ry, rz, p0, px, py, pz, m, ityp, iso3, charge,
        lstcoll, ncoll, strangeness, origin
    """

    uid: int             # unique lifetime particle ID (CTOption(56)=1)
    r0: float            # time coordinate [fm/c]
    rx: float            # position x [fm]
    ry: float            # position y [fm]
    rz: float            # position z [fm]
    p0: float            # energy [GeV]
    px: float            # momentum x [GeV/c]
    py: float            # momentum y [GeV/c]
    pz: float            # momentum z [GeV/c]
    mass: float          # mass [GeV/c^2]
    ityp: int            # UrQMD particle type ID (raw integer, no name mapping)
    iso3: int            # 2 * isospin 3rd component
    charge: int          # electric charge [e]
    lstcoll: int         # last collision number of this particle
    ncoll: int           # collision count of this particle
    strangeness: int     # strangeness strit(ityp)
    origin: int          # origin tag
    interaction_ctag: int  # ctag of the interaction this snapshot belongs to
    role: Role           # incoming or outgoing
    ordinal: int         # 0-based position within its incoming/outgoing set
    line_number: int     # 1-based line number in the source file

    @property
    def state_id(self) -> "StateId":
        """Stable identity of this snapshot: (ctag, role, ordinal).

        Deliberately NOT the uid: see docs/reaction_graph.md.
        """
        return StateId(self.interaction_ctag, self.role, self.ordinal)

    def four_momentum(self) -> Tuple[float, float, float, float]:
        return (self.p0, self.px, self.py, self.pz)


@dataclass(frozen=True)
class StateId:
    """Stable identifier of a particle *state* node in the reaction graph.

    (ctag, role, ordinal) is unique within one event: an interaction writes
    each incoming/outgoing slot exactly once, in order. The uid is carried by
    the ParticleSnapshot, not by the StateId, so that identity-preserving
    scattering (same uid in and out of the same interaction) produces two
    distinct nodes and never an artificial self-cycle.
    """

    ctag: int
    role: Role
    ordinal: int

    def sort_key(self):
        # "in" < "out" alphabetically: within one interaction the incoming
        # state precedes the outgoing state chronologically.
        return (self.ctag, self.role.value, self.ordinal)

    def __lt__(self, other: "StateId") -> bool:
        return self.sort_key() < other.sort_key()

    def __str__(self) -> str:
        return f"ctag={self.ctag}:{self.role.value}[{self.ordinal}]"


@dataclass(frozen=True)
class Interaction:
    """One UrQMD collision/decay record (header format 502 + particle rows).

    Field mapping from output.f:601-602:
        nin, nexit, iline, ctag, acttime, tsqrts, tstot, tsigpart, cdens
    """

    nin: int             # number of incoming particles (1 = decay, 2 = collision)
    nout: int            # number of outgoing particles (0 allowed: Pauli-blocked)
    process_id: int      # iline: channel/process ID (20 = decay, verified scatter.f:173)
    ctag: int            # collision tag: sequential interaction counter
    time: float          # interaction time acttime [fm/c]
    sqrts: float         # sqrt(s) of the collision [GeV]
    sigma_total: float   # total cross section [mb] (0 for decays)
    sigma_partial: float # selected-channel cross section [mb] (0 for decays)
    baryon_density: float  # local baryon density cdens at the collision point
    incoming: Tuple[ParticleSnapshot, ...]
    outgoing: Tuple[ParticleSnapshot, ...]
    line_number: int     # 1-based line number of the header record

    @property
    def is_decay(self) -> bool:
        """1 -> n decay, verified classification: process_id 20 with nin == 1."""
        return self.process_id == DECAY_PROCESS_ID and self.nin == 1

    @property
    def is_identity_preserving(self) -> bool:
        """True if at least one uid appears in both the incoming and the
        outgoing set of this interaction (e.g. elastic scattering).

        Such interactions must NOT be modeled as uid -> interaction -> uid
        self-loops; incoming and outgoing are distinct particle states.
        """
        in_uids = {s.uid for s in self.incoming}
        return any(s.uid in in_uids for s in self.outgoing)


@dataclass(frozen=True)
class HistoryEvent:
    """One complete UrQMD event: event header plus all interaction records."""

    header: EventHeader
    interactions: Tuple[Interaction, ...]
    source_path: str = ""

    @property
    def n_interactions(self) -> int:
        return len(self.interactions)

    @property
    def n_particle_rows(self) -> int:
        return sum(i.nin + i.nout for i in self.interactions)
