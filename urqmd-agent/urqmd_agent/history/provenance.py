"""Microscopic provenance for final-state hadrons (Phase 1B).

Implements the frozen definitions of physics_gate/phase1b/protocol.md:

- producer interaction: first interaction where a UID appears as outgoing
- species-forming interaction: LAST interaction that created the UID or
  changed (ityp, iso3) into the final species; elastic/identity-preserving
  collisions are never formation
- post-formation transport: later interactions of the UID
- final-state membership from file15 alone: a UID is final iff its
  chronologically last snapshot (highest ctag) is an OUTGOING state.
  Closure against file13 yields is checked by the caller (smoke test).

All tracing is deterministic and reaction-set based; no 2->n parent
assignment is ever invented.

Pauli-blocked / aborted interactions: scatfinal restores the incoming
particles and sets nexit=0 (scatter.f:905-983; the only cascade-mode
path that yields nout=0). Such records are NO-OPS: their states are
excluded from final-state membership, formation tracing and
N_part^actual, and marked `blocked=True` in species_changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .reaction_graph import ReactionGraph
from .schema import DECAY_PROCESS_ID, ParticleSnapshot, Role

#: species identity = (ityp, iso3), per Phase-1A verified mapping
LAMBDA = (41, 0)
KAON0 = (106, -1)
ANTIKAON0 = (-106, 1)

SPECIES_NAMES = {LAMBDA: "Lambda", KAON0: "K0", ANTIKAON0: "antiK0"}

#: observable weights (protocol Step 5): K_S0-equivalent keeps K0/anti-K0
#: discrete with weight 1/2; Lambda weight 1
OBSERVABLE_WEIGHT = {"Lambda": 1.0, "K0": 0.5, "antiK0": 0.5}


@dataclass(frozen=True)
class SpeciesChange:
    """One passage of a UID through an interaction (Step 3 diagnostics)."""

    uid: int
    ctag: int
    created: bool            # UID first appears here (outgoing only)
    consumed: bool           # UID appears as incoming only
    identity_preserving: bool  # same UID in and out
    blocked: bool            # Pauli-blocked/aborted record (nout==0)
    ityp_changed: bool
    iso3_changed: bool
    charge_changed: bool
    strangeness_changed: bool
    species_in: Optional[Tuple[int, int]]
    species_out: Optional[Tuple[int, int]]


def species_changes(graph: ReactionGraph, uid: int) -> List[SpeciesChange]:
    """Classify every interaction passage of `uid` (chronological)."""
    out: List[SpeciesChange] = []
    states = graph.worldline(uid)  # sorted (ctag, role, ordinal)
    by_ctag: Dict[int, List[ParticleSnapshot]] = {}
    first_ctag = states[0][0].ctag if states else None
    for _, snap in states:
        by_ctag.setdefault(snap.interaction_ctag, []).append(snap)
    for ctag in sorted(by_ctag):
        snaps = by_ctag[ctag]
        ins = [s for s in snaps if s.role is Role.INCOMING]
        outs = [s for s in snaps if s.role is Role.OUTGOING]
        sin = ins[0] if ins else None
        sout = outs[0] if outs else None
        blocked = graph.interaction(ctag).nout == 0
        out.append(SpeciesChange(
            uid=uid, ctag=ctag, blocked=blocked,
            created=(ctag == first_ctag and sin is None),
            consumed=(sout is None),
            identity_preserving=(sin is not None and sout is not None),
            ityp_changed=(sin is not None and sout is not None
                          and sin.ityp != sout.ityp),
            iso3_changed=(sin is not None and sout is not None
                          and sin.iso3 != sout.iso3),
            charge_changed=(sin is not None and sout is not None
                            and sin.charge != sout.charge),
            strangeness_changed=(sin is not None and sout is not None
                                 and sin.strangeness != sout.strangeness),
            species_in=(sin.ityp, sin.iso3) if sin else None,
            species_out=(sout.ityp, sout.iso3) if sout else None,
        ))
    return out


def _physical_states(graph: ReactionGraph, uid: int
                     ) -> List[ParticleSnapshot]:
    """Worldline snapshots excluding Pauli-blocked/aborted records
    (nout==0, scatter.f:977): those interactions never happened."""
    return [snap for _, snap in graph.worldline(uid)
            if graph.interaction(snap.interaction_ctag).nout > 0]


def uid_final_states(graph: ReactionGraph) -> Dict[int, ParticleSnapshot]:
    """uid -> last snapshot, for UIDs whose last state is OUTGOING (alive
    at freeze-out). Deterministic: ctag order is chronological (Phase 0B
    verified non-decreasing interaction times)."""
    finals: Dict[int, ParticleSnapshot] = {}
    for uid in graph.uids():
        states = _physical_states(graph, uid)
        if states and states[-1].role is Role.OUTGOING:
            finals[uid] = states[-1]
    return finals


def find_species_formation(graph: ReactionGraph, uid: int,
                           final_key: Tuple[int, int]) -> ParticleSnapshot:
    """The species-forming OUTGOING state of `uid` for final species
    `final_key` = (ityp, iso3).

    Walk the worldline backward: the formation interaction is the LAST one
    that created the UID or changed its (ityp, iso3) into final_key.
    Raises ValueError if no consistent formation point exists.
    """
    raw = graph.worldline(uid)
    if not raw:
        raise ValueError(f"uid {uid} has no states")
    states = [(None, s) for s in _physical_states(graph, uid)]
    # must end in final species as outgoing
    _, last = states[-1]
    if last.role is not Role.OUTGOING or (last.ityp, last.iso3) != final_key:
        raise ValueError(
            f"uid {uid}: last state is not outgoing final species "
            f"{final_key} (got role={last.role}, "
            f"ityp={last.ityp}, iso3={last.iso3})")
    by_ctag: Dict[int, List[ParticleSnapshot]] = {}
    for _, snap in states:
        by_ctag.setdefault(snap.interaction_ctag, []).append(snap)
    ctags = sorted(by_ctag, reverse=True)
    for ctag in ctags:
        snaps = by_ctag[ctag]
        ins = [s for s in snaps if s.role is Role.INCOMING]
        outs = [s for s in snaps if s.role is Role.OUTGOING]
        sout = outs[0] if outs else None
        sin = ins[0] if ins else None
        if sout is None:
            # consumed after being final? cannot happen for a final particle
            raise ValueError(f"uid {uid}: consumed at ctag {ctag} but final")
        if (sout.ityp, sout.iso3) != final_key:
            raise ValueError(
                f"uid {uid}: outgoing species {(sout.ityp, sout.iso3)} at "
                f"ctag {ctag} differs from final {final_key} AFTER the "
                f"claimed formation point - inconsistent worldline")
        if sin is None:
            return sout                      # UID created here as final species
        if (sin.ityp, sin.iso3) != final_key:
            return sout                      # species changed here (same UID)
        # identity preserved: keep walking back
    raise ValueError(f"uid {uid}: no formation point found")


def npart_actual(graph: ReactionGraph, ap: int, at: int) -> int:
    """Distinct initial nucleons (uid <= ap+at, origin==0 at first
    appearance, ityp==1) appearing as INCOMING in >=1 two-body collision
    (nin=2). Secondary diagnostic only (docs/npart_actual.md)."""
    n_initial = ap + at
    participants = set()
    for inter in graph.event.interactions:
        if inter.nin != 2 or inter.process_id == DECAY_PROCESS_ID:
            continue
        if inter.nout == 0:
            continue  # Pauli-blocked/aborted: not a physical interaction
        for s in inter.incoming:
            if 1 <= s.uid <= n_initial:
                participants.add(s.uid)
    # source-consistency check: those UIDs must be ityp=1, origin=0 at
    # their first appearance (init.f:184,544)
    for uid in participants:
        _, first = graph.worldline(uid)[0]
        if first.origin != 0 or first.ityp != 1:
            raise ValueError(
                f"initial-nucleon assumption violated for uid {uid}: "
                f"origin={first.origin}, ityp={first.ityp}")
    return len(participants)


# ----------------------------------------------------------------------
# provenance records (Step 4)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class ProvenanceRecord:
    """Compact provenance of one final Lambda / K0 / anti-K0 (|y|<0.5)."""

    event_id: int
    final_uid: int
    final_species: str          # "Lambda" | "K0" | "antiK0"
    ityp: int
    iso3: int
    final_y: float
    final_pT: float
    obs_weight: float           # 1.0 Lambda, 0.5 per K0/antiK0

    n_ch: int                   # centrality estimator multiplicity (f13)
    npart_glauber: float        # f13 header
    npart_actual: int           # history-derived (secondary)
    bimp: float

    producer_ctag: int
    producer_time: float
    producer_process_id: int
    producer_class: str
    producer_sqrts: float
    producer_rhob: float

    formation_ctag: int
    formation_time: float
    formation_process_id: int
    formation_class: str
    formation_sqrts: float
    formation_rhob: float

    n_postformation: int
    n_post_elastic: int
    n_post_inelastic: int
    n_post_identity_preserving: int

    last_ctag: int
    last_time: float
    created_at_formation: bool


def rapidity(snap: ParticleSnapshot) -> float:
    import math
    e, pz = snap.p0, snap.pz
    if e - pz <= 0.0:
        return math.copysign(float("inf"), pz)
    return 0.5 * math.log((e + pz) / (e - pz))


def pT(snap: ParticleSnapshot) -> float:
    return (snap.px ** 2 + snap.py ** 2) ** 0.5


def extract_event_provenance(graph: ReactionGraph, event_id: int, n_ch: int,
                             npart_glauber: float, bimp: float,
                             classify, ap: int, at: int,
                             y_max: float = 0.5) -> List[ProvenanceRecord]:
    """Extract provenance records for all final Lambda/K0/anti-K0 with
    |y| < y_max. `classify(process_id) -> (coarse_class, is_elastic)`.
    """
    records: List[ProvenanceRecord] = []
    finals = uid_final_states(graph)
    npa = npart_actual(graph, ap, at)
    for uid in sorted(finals):
        snap = finals[uid]
        key = (snap.ityp, snap.iso3)
        if key not in SPECIES_NAMES:
            continue
        y = rapidity(snap)
        if abs(y) >= y_max:
            continue
        species = SPECIES_NAMES[key]

        formation = find_species_formation(graph, uid, key)
        f_inter = graph.interaction(formation.interaction_ctag)
        f_class, _ = classify(f_inter.process_id, f_inter.nout)

        producer_ctag = graph.worldline(uid)[0][1].interaction_ctag
        p_inter = graph.interaction(producer_ctag)
        p_class, _ = classify(p_inter.process_id, p_inter.nout)

        n_post = n_el = n_inel = n_idp = 0
        for change in species_changes(graph, uid):
            if change.ctag <= formation.interaction_ctag or change.blocked:
                continue
            n_post += 1
            inter = graph.interaction(change.ctag)
            _, is_el = classify(inter.process_id, inter.nout)
            if is_el:
                n_el += 1
            elif inter.process_id != DECAY_PROCESS_ID:
                n_inel += 1
            if change.identity_preserving:
                n_idp += 1

        _, last = graph.worldline(uid)[-1]
        l_inter = graph.interaction(last.interaction_ctag)
        records.append(ProvenanceRecord(
            event_id=event_id, final_uid=uid, final_species=species,
            ityp=snap.ityp, iso3=snap.iso3, final_y=y, final_pT=pT(snap),
            obs_weight=OBSERVABLE_WEIGHT[species],
            n_ch=n_ch, npart_glauber=npart_glauber, npart_actual=npa,
            bimp=bimp,
            producer_ctag=producer_ctag, producer_time=p_inter.time,
            producer_process_id=p_inter.process_id, producer_class=p_class,
            producer_sqrts=p_inter.sqrts,
            producer_rhob=p_inter.baryon_density,
            formation_ctag=formation.interaction_ctag,
            formation_time=f_inter.time,
            formation_process_id=f_inter.process_id,
            formation_class=f_class, formation_sqrts=f_inter.sqrts,
            formation_rhob=f_inter.baryon_density,
            n_postformation=n_post, n_post_elastic=n_el,
            n_post_inelastic=n_inel, n_post_identity_preserving=n_idp,
            last_ctag=last.interaction_ctag, last_time=l_inter.time,
            created_at_formation=(producer_ctag == formation.interaction_ctag),
        ))
    return records
