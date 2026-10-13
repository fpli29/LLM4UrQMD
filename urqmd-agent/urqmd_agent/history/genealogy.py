"""Parent-resonance genealogy and strangeness-origin tracing (Phase 1B2).

Implements the frozen definitions of physics_gate/phase1b2/protocol.md:

- decay mother: unique incoming particle of a 1->n decay (process_id=20,
  nin=1). This is the ONLY context in which a particle-level parent is
  ever assigned; generic 2->n reactions keep reaction-hyperedge semantics.
- mother production interaction: first physical (nout>0) interaction where
  the mother UID appears as outgoing; INITIAL_STATE if none exists.
- strangeness origin: conservative reaction-level definition. An
  interaction is a strangeness-creation candidate iff all incoming
  particles have S=0, at least one outgoing has S!=0, and total
  strangeness is conserved. Interactions with pre-existing incoming
  strangeness are transport/exchange, never creation; their strange
  incoming carriers are followed upstream instead. The outcome is
  UNIQUE_ROOT / MULTIPLE_COMPATIBLE_ROOTS / PREEXISTING_STRANGENESS /
  UNRESOLVED; no root is ever selected by hand.

All tracing is deterministic. Blocked/aborted records (nout==0) are
no-ops everywhere (see provenance.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .provenance import (OBSERVABLE_WEIGHT, SPECIES_NAMES,
                         find_species_formation, pT, rapidity,
                         species_changes, uid_final_states)
from .reaction_graph import ReactionGraph
from .schema import Interaction, ParticleSnapshot, Role

#: strangeness-root outcomes (protocol Step 5 / definition G)
UNIQUE_ROOT = "UNIQUE_ROOT"
MULTIPLE_ROOTS = "MULTIPLE_COMPATIBLE_ROOTS"
PREEXISTING = "PREEXISTING_STRANGENESS"
UNRESOLVED = "UNRESOLVED"

#: family_of(ityp, iso3) -> resonance-family label (source-verified, see
#: urqmd_agent/particles/resonance_families.py and docs/resonance_families.md)
FamilyOf = Callable[[int, int], str]


@dataclass(frozen=True)
class RootCandidate:
    ctag: int
    time: float
    process_id: int
    coarse_class: str
    sqrts: float
    rhob: float


@dataclass(frozen=True)
class RootResult:
    outcome: str                       # one of the four outcome constants
    candidates: Tuple[RootCandidate, ...]
    preexisting_branch: bool = False
    note: str = ""


@dataclass(frozen=True)
class GenealogyRecord:
    """One row per final Lambda / K0 / anti-K0 (|y|<0.5)."""

    event_id: int
    final_uid: int
    final_species: str
    final_weight: float
    final_ityp: int
    final_iso3: int
    final_y: float
    final_pT: float

    n_ch: int
    npart_glauber: float
    npart_actual: int
    bimp: float

    # level 1: final-species formation (identical to Phase 1B)
    formation_ctag: int
    formation_time: float
    formation_process_id: int
    formation_class: str

    # level 2: decay mother (only when formation is a 1->n decay)
    mother_uid: int                    # -1 when not decay-formed
    mother_ityp: int
    mother_iso3: int
    mother_strangeness: int
    mother_mass: float
    mother_family: str                 # "" when not decay-formed
    mother_creation_ctag: int          # -1 when not decay-formed
    mother_creation_time: float
    mother_creation_process_id: int
    mother_creation_class: str         # INITIAL_STATE if mother has no producer
    mother_creation_sqrts: float
    mother_creation_rhob: float
    mother_n_interactions_before_decay: int   # between creation and decay
    mother_n_elastic_before_decay: int
    mother_n_inelastic_before_decay: int
    mother_identity_changes_before_decay: int
    mother_lifetime: float             # t_decay - t_creation

    # strangeness origin (reaction level)
    root_outcome: str
    root_ctag: int                     # -1 unless UNIQUE_ROOT (first candidate otherwise)
    root_time: float
    root_process_id: int
    root_class: str
    root_sqrts: float
    root_rhob: float
    root_n_candidates: int
    root_all_ctags: str                # ";"-joined candidate ctags


# ----------------------------------------------------------------------
# decay mother / mother production
# ----------------------------------------------------------------------

def decay_mother_of_formation(graph: ReactionGraph,
                              formation: ParticleSnapshot
                              ) -> Optional[ParticleSnapshot]:
    """The unique incoming state of the formation interaction, iff it is a
    verified 1->n decay (process_id=20, nin=1). None otherwise."""
    inter = graph.interaction(formation.interaction_ctag)
    if not inter.is_decay:
        return None
    return inter.incoming[0]


def production_interaction_of(graph: ReactionGraph,
                              uid: int) -> Optional[Interaction]:
    """First physical (nout>0) interaction where `uid` appears as outgoing.
    None iff the uid never appears as outgoing (initial-state particle)."""
    for _, snap in graph.worldline(uid):
        if snap.role is Role.OUTGOING:
            inter = graph.interaction(snap.interaction_ctag)
            if inter.nout > 0:
                return inter
    return None


def mother_transport(graph: ReactionGraph, mother_uid: int,
                     decay_ctag: int, classify
                     ) -> Tuple[int, int, int, int]:
    """(n_interactions, n_elastic, n_inelastic, n_identity_changes) of the
    mother strictly BEFORE the decay.

    Interaction counts exclude the creation passage itself: a mother that
    is created and decays without further interaction has
    n_interactions = 0. Identity changes are counted over all physical
    passages before the decay. Blocked records are no-ops.
    """
    n_between = n_el = n_inel = n_idchange = 0
    for change in species_changes(graph, mother_uid):
        if change.blocked or change.ctag >= decay_ctag:
            continue
        if change.ityp_changed or change.iso3_changed:
            n_idchange += 1
        if change.created:
            continue  # the creation passage is not "transport"
        n_between += 1
        inter = graph.interaction(change.ctag)
        _, is_el = classify(inter.process_id, inter.nout)
        if is_el:
            n_el += 1
        else:
            n_inel += 1
    return n_between, n_el, n_inel, n_idchange


# ----------------------------------------------------------------------
# strangeness origin (protocol definition G)
# ----------------------------------------------------------------------

def strangeness_root(graph: ReactionGraph, uid: int,
                     final_key: Tuple[int, int], classify) -> RootResult:
    """Trace the strangeness of the final particle `uid` backward through
    the reaction hypergraph and classify its origin.

    Never assigns particle-level parents inside 2->n reactions: at each
    non-decay interaction with pre-existing incoming strangeness, ALL
    strange incoming carriers are followed upstream; the collected roots
    are reported as a set.
    """
    candidates: Dict[int, RootCandidate] = {}
    notes: List[str] = []
    preexisting = False
    visited_inter: set = set()
    visited_uid: set = set()

    def trace_particle(p_uid: int) -> None:
        nonlocal preexisting
        if p_uid in visited_uid:
            return
        visited_uid.add(p_uid)
        prod = production_interaction_of(graph, p_uid)
        if prod is None:
            _, first = graph.worldline(p_uid)[0]
            if first.origin == 0:
                preexisting = True
            else:
                notes.append(f"uid {p_uid}: no producer interaction but "
                             f"origin={first.origin}")
            return
        trace_interaction(prod)

    def trace_interaction(inter: Interaction) -> None:
        if inter.ctag in visited_inter:
            return
        visited_inter.add(inter.ctag)
        if inter.is_decay:
            # 1->n decay of a STRANGE mother: strangeness passes through
            # the unique mother (never creation - protocol Step 6 case 3)
            if inter.incoming[0].strangeness != 0:
                trace_particle(inter.incoming[0].uid)
                return
            # Non-strange mother with strange daughters (e.g. N*/Delta ->
            # Lambda + K): the decay vertex itself pair-creates the
            # strangeness. Fall through to the generic creation test.
        s_in = sum(s.strangeness for s in inter.incoming)
        s_out = sum(s.strangeness for s in inter.outgoing)
        if s_in != s_out:
            notes.append(f"ctag {inter.ctag}: strangeness not conserved "
                         f"(S_in={s_in}, S_out={s_out})")
            return
        strange_in = [s for s in inter.incoming if s.strangeness != 0]
        if not strange_in:
            if any(s.strangeness != 0 for s in inter.outgoing):
                cls, _ = classify(inter.process_id, inter.nout)
                candidates[inter.ctag] = RootCandidate(
                    ctag=inter.ctag, time=inter.time,
                    process_id=inter.process_id, coarse_class=cls,
                    sqrts=inter.sqrts, rhob=inter.baryon_density)
            else:
                notes.append(f"ctag {inter.ctag}: no strangeness anywhere "
                             f"on a traced ancestry branch")
            return
        # pre-existing strangeness: transport/exchange/conversion - follow
        # every strange incoming carrier upstream (hyperedge semantics)
        for s in strange_in:
            trace_particle(s.uid)

    try:
        formation = find_species_formation(graph, uid, final_key)
    except ValueError:
        # no formation point: the particle carried its final species from
        # the initial state (origin=0, never created in an interaction)
        _, first = graph.worldline(uid)[0]
        if first.origin == 0 and (first.ityp, first.iso3) == final_key:
            return RootResult(PREEXISTING, (), True)
        raise
    trace_interaction(graph.interaction(formation.interaction_ctag))

    cands = tuple(candidates[c] for c in sorted(candidates))
    if notes:
        return RootResult(UNRESOLVED, cands, preexisting,
                          "; ".join(notes))
    if preexisting and cands:
        return RootResult(MULTIPLE_ROOTS, cands, True,
                          "creation candidate(s) plus pre-existing "
                          "strangeness branch")
    if preexisting:
        return RootResult(PREEXISTING, (), True)
    if len(cands) == 1:
        return RootResult(UNIQUE_ROOT, cands)
    if len(cands) > 1:
        return RootResult(MULTIPLE_ROOTS, cands)
    return RootResult(UNRESOLVED, (), False,
                      "no creation candidate and no pre-existing branch")


# ----------------------------------------------------------------------
# per-event extraction
# ----------------------------------------------------------------------

def extract_event_genealogy(graph: ReactionGraph, event_id: int, n_ch: int,
                            npart_glauber: float, npart_actual: int,
                            bimp: float, classify, family_of: FamilyOf,
                            y_max: float = 0.5) -> List[GenealogyRecord]:
    """Genealogy rows for all final Lambda/K0/anti-K0 with |y| < y_max."""
    records: List[GenealogyRecord] = []
    finals = uid_final_states(graph)
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

        # --- level 2: decay mother -------------------------------------
        m_uid = m_ityp = m_iso3 = m_str = -1
        m_mass = 0.0
        m_family = ""
        mc_ctag = -1
        mc_time = mc_sqrts = mc_rhob = 0.0
        mc_pid = 0
        mc_class = ""
        m_n = m_el = m_inel = m_idchange = 0
        m_lifetime = 0.0
        mother = decay_mother_of_formation(graph, formation)
        if mother is not None:
            m_uid = mother.uid
            m_ityp = mother.ityp
            m_iso3 = mother.iso3
            m_str = mother.strangeness
            m_mass = mother.mass
            m_family = family_of(mother.ityp, mother.iso3)
            prod = production_interaction_of(graph, mother.uid)
            if prod is None:
                mc_class = "INITIAL_STATE"
                _, first = graph.worldline(mother.uid)[0]
                mc_time = first.r0
            else:
                mc_ctag = prod.ctag
                mc_time = prod.time
                mc_pid = prod.process_id
                mc_class, _ = classify(prod.process_id, prod.nout)
                mc_sqrts = prod.sqrts
                mc_rhob = prod.baryon_density
            m_n, m_el, m_inel, m_idchange = mother_transport(
                graph, mother.uid, f_inter.ctag, classify)
            m_lifetime = f_inter.time - mc_time

        # --- strangeness origin ----------------------------------------
        root = strangeness_root(graph, uid, key, classify)
        if root.candidates:
            first_c = root.candidates[0]
            r_ctag, r_time = first_c.ctag, first_c.time
            r_pid, r_class = first_c.process_id, first_c.coarse_class
            r_sqrts, r_rhob = first_c.sqrts, first_c.rhob
        else:
            r_ctag, r_time, r_pid = -1, 0.0, 0
            r_class, r_sqrts, r_rhob = "", 0.0, 0.0

        records.append(GenealogyRecord(
            event_id=event_id, final_uid=uid, final_species=species,
            final_weight=OBSERVABLE_WEIGHT[species],
            final_ityp=snap.ityp, final_iso3=snap.iso3,
            final_y=y, final_pT=pT(snap),
            n_ch=n_ch, npart_glauber=npart_glauber,
            npart_actual=npart_actual, bimp=bimp,
            formation_ctag=formation.interaction_ctag,
            formation_time=f_inter.time,
            formation_process_id=f_inter.process_id,
            formation_class=f_class,
            mother_uid=m_uid, mother_ityp=m_ityp, mother_iso3=m_iso3,
            mother_strangeness=m_str, mother_mass=m_mass,
            mother_family=m_family,
            mother_creation_ctag=mc_ctag, mother_creation_time=mc_time,
            mother_creation_process_id=mc_pid,
            mother_creation_class=mc_class,
            mother_creation_sqrts=mc_sqrts, mother_creation_rhob=mc_rhob,
            mother_n_interactions_before_decay=m_n,
            mother_n_elastic_before_decay=m_el,
            mother_n_inelastic_before_decay=m_inel,
            mother_identity_changes_before_decay=m_idchange,
            mother_lifetime=m_lifetime,
            root_outcome=root.outcome,
            root_ctag=r_ctag, root_time=r_time,
            root_process_id=r_pid, root_class=r_class,
            root_sqrts=r_sqrts, root_rhob=r_rhob,
            root_n_candidates=len(root.candidates),
            root_all_ctags=";".join(str(c.ctag) for c in root.candidates),
        ))
    return records
