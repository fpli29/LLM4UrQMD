"""Proton history extraction from a UrQMD file15 reaction graph (Phase B1).

Proton definition is the frozen one of
urqmd_agent/analysis/azimuthal_partition.py (`_is_proton`): ityp == 1 and
iso3 == +1 (PDG 2212); anti-protons are never included.

Formation (per proton uid)
--------------------------
The formation interaction is the FIRST physical (nout > 0) interaction with
the uid in its OUTGOING set (`genealogy.production_interaction_of`); a uid
with no such interaction is INITIAL_CARRIED (initial-state nucleon that was
never produced inside the event). Blocked/aborted records (nout == 0,
Pauli-blocked, scatter.f:977) are no-ops everywhere, matching
`provenance._physical_states`.

Formation class is mapped from the source-verified taxonomy
(`history/taxonomy.py: classify(process_id, nout)` -> coarse class) as:

    DECAY                                  -> DECAY_PRODUCT
    STRING                                 -> STRING_PRODUCT
    BB / MB / MM / STRX / ANNIHILATION     -> COLLISION_PRODUCT
    ELASTIC (at formation)                 -> OTHER_VERIFIED  (flag: should
                                             not occur - a uid incoming to
                                             its own first outgoing record
                                             would be identity-preserving)
    no production interaction              -> INITIAL_CARRIED
    anything else (coarse OTHER)           -> UNKNOWN

Merge rule (DECLARED HERE, before any Delta is computed; Phase B1 step 9
axis C): OTHER_VERIFIED and UNKNOWN are always merged into OTHER_UNKNOWN.
In addition, any formation class covering < 1% of the pairs of the full B1
sample is merged into OTHER_UNKNOWN at analysis time, with the merge
logged. `merged_formation_class` implements the unconditional part.

Descriptors (all source-verifiable from file15 alone)
-----------------------------------------------------
See ProtonHistory. "Physical" always means nout > 0. Interaction membership
means the uid appears in the incoming or outgoing set.

Pair classification (Phase B1 step 9 axes)
------------------------------------------
A: SAME_PRODUCTION_INTERACTION (both formation ctags identical and >= 0) /
   DIRECT_COLLISION_PARTNERS (both uids co-incoming in >= 1 common physical
   interaction node with ctag strictly greater than BOTH formation ctags
   (INITIAL_CARRIED counts as -1)) / NO_DIRECT_SHARED_INTERACTION.
B: BOTH_NO_POST_FORMATION_SCATTER / ONE_RESCATTERED / BOTH_RESCATTERED from
   n_post_scatter == 0 per proton.
C: sorted formation-class pair label (merged classes).
D: per-proton post-formation collision-count bins {0, 1, 2-3, >=4}, as a
   sorted pair label.

Ancestry flags use an INDEXED ancestor walk (`_AncestryIndex`) that
replicates `ReactionGraph.ancestors_of_state` semantics exactly (same
states, same ctag set) but with O(1) edge lookups built once per graph.
The unindexed graph method scans all worldline links and identity
passages per visited state, which is prohibitively slow on central
Au+Au events (~10^8 operations per proton). The indexed walk is a pure
performance change: equivalence is pinned by tests against
`ancestors_of_state` on the fixtures. The walk includes the formation
interaction itself, so DECAY_PRODUCT implies ancestry_decay=True and
STRING_PRODUCT implies ancestry_string=True by construction
(documented, not a bug).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple

from .genealogy import production_interaction_of
from .provenance import uid_final_states
from .reaction_graph import ReactionGraph
from .schema import ParticleSnapshot, Role, StateId
from .taxonomy import classify

#: frozen proton id (PDG 2212); same as azimuthal_partition._is_proton
ITYP_PROTON = 1
ISO3_PROTON = 1

# formation classes
INITIAL_CARRIED = "INITIAL_CARRIED"
DECAY_PRODUCT = "DECAY_PRODUCT"
STRING_PRODUCT = "STRING_PRODUCT"
COLLISION_PRODUCT = "COLLISION_PRODUCT"
OTHER_VERIFIED = "OTHER_VERIFIED"
UNKNOWN = "UNKNOWN"
OTHER_UNKNOWN = "OTHER_UNKNOWN"

FORMATION_CLASSES = (INITIAL_CARRIED, DECAY_PRODUCT, STRING_PRODUCT,
                     COLLISION_PRODUCT, OTHER_VERIFIED, UNKNOWN)

_COLLISION_CLASSES = frozenset({"BB", "MB", "MM", "STRX", "ANNIHILATION"})

#: pair axis labels
A_SAME_PRODUCTION = "SAME_PRODUCTION_INTERACTION"
A_DIRECT_PARTNERS = "DIRECT_COLLISION_PARTNERS"
A_NO_DIRECT = "NO_DIRECT_SHARED_INTERACTION"
B_NEITHER = "BOTH_NO_POST_FORMATION_SCATTER"
B_ONE = "ONE_RESCATTERED"
B_BOTH = "BOTH_RESCATTERED"


def is_proton_snapshot(snap: ParticleSnapshot) -> bool:
    return snap.ityp == ITYP_PROTON and snap.iso3 == ISO3_PROTON


def merged_formation_class(cls: str) -> str:
    """Unconditional part of the declared merge rule (module docstring)."""
    if cls in (OTHER_VERIFIED, UNKNOWN):
        return OTHER_UNKNOWN
    return cls


def post_scatter_bin(n_post_scatter: int) -> str:
    """Axis D bin for one proton: {0, 1, 2-3, >=4}."""
    if n_post_scatter <= 0:
        return "0"
    if n_post_scatter == 1:
        return "1"
    if n_post_scatter <= 3:
        return "2-3"
    return ">=4"


@dataclass(frozen=True)
class ProtonHistory:
    """History descriptor set of one final-state proton (see module docs)."""

    uid: int
    formation_class: str
    formation_ctag: int          # -1 for INITIAL_CARRIED
    formation_time: float        # -1.0 for INITIAL_CARRIED
    formation_process: int       # file15 iline; -1 for INITIAL_CARRIED
    n_interactions: int          # physical interactions involving uid (in|out)
    n_post_scatter: int          # post-formation non-decay physical
                                 # interactions with uid INCOMING
    last_process: int            # process id of last physical interaction
    last_time: float             # time of last physical interaction
    first_time: float            # formation time; for INITIAL_CARRIED the
                                 # first physical interaction time (-1 if none)
    ever_elastic: bool           # any elastic-class physical interaction
    ever_inelastic: bool         # any non-elastic physical interaction
    ever_identity_rescatter: bool  # post-formation identity-preserving
                                   # interaction with uid in AND out
    ancestry_decay: bool         # decay edge anywhere in the ancestor walk
    ancestry_string: bool        # string-class interaction in ancestor walk
    incoming_ctags: Tuple[int, ...]  # physical interactions with uid INCOMING
                                     # (chronological; needed for pair axis A)


def _formation_class(graph: ReactionGraph, uid: int) -> Tuple[str, int, float, int]:
    """(formation_class, ctag, time, process_id); (-1, -1.0, -1) if initial."""
    prod = production_interaction_of(graph, uid)
    if prod is None:
        return INITIAL_CARRIED, -1, -1.0, -1
    coarse, is_elastic = classify(prod.process_id, prod.nout)
    if is_elastic or coarse == "ELASTIC":
        cls = OTHER_VERIFIED
    elif coarse == "DECAY":
        cls = DECAY_PRODUCT
    elif coarse == "STRING":
        cls = STRING_PRODUCT
    elif coarse in _COLLISION_CLASSES:
        cls = COLLISION_PRODUCT
    else:
        cls = UNKNOWN
    return cls, prod.ctag, prod.time, prod.process_id


class _AncestryIndex:
    """Precomputed predecessor lookups for the ancestor walk of one graph.

    Semantics copied from ReactionGraph.ancestors_of_state: an OUTGOING
    state's predecessors are the full incoming set of its interaction; an
    INCOMING state's predecessors are the earlier outgoing states of the
    same uid (worldline links) and the outgoing state of an identity
    passage of the same interaction.
    """

    def __init__(self, graph: ReactionGraph):
        self.graph = graph
        self.pred_worldline: Dict[StateId, List[StateId]] = {}
        for link in graph.worldline_links:
            self.pred_worldline.setdefault(link.to_state, []).append(
                link.from_state)
        self.pred_identity: Dict[StateId, List[StateId]] = {}
        for ip in graph.identity_passages:
            self.pred_identity.setdefault(ip.in_state, []).append(
                ip.out_state)

    def ancestor_ctags(self, start: StateId) -> FrozenSet[int]:
        """Same ctag set as ReactionGraph.ancestors_of_state(start)[1]."""
        graph = self.graph
        seen_states: set = set()
        seen_ctags: set = set()
        stack = [start]
        while stack:
            sid = stack.pop()
            if sid in seen_states:
                continue
            seen_states.add(sid)
            snap = graph.states[sid]
            ctag = snap.interaction_ctag
            if snap.role is Role.OUTGOING:
                if ctag in seen_ctags:
                    continue
                seen_ctags.add(ctag)
                for in_sid in graph.incoming_states(ctag):
                    if in_sid not in seen_states:
                        stack.append(in_sid)
            else:
                for s in self.pred_worldline.get(sid, ()):
                    stack.append(s)
                for s in self.pred_identity.get(sid, ()):
                    stack.append(s)
        return frozenset(seen_ctags)


def proton_history(graph: ReactionGraph, uid: int,
                   final_state: ParticleSnapshot,
                   anc_index: Optional[_AncestryIndex] = None
                   ) -> ProtonHistory:
    """Extract the full descriptor set of one final proton."""
    fcls, fctag, ftime, fproc = _formation_class(graph, uid)

    n_inter = 0
    n_post = 0
    last_proc, last_time = -1, -1.0
    first_time = -1.0
    ever_el = ever_inel = ever_id_resc = False
    incoming = []
    seen_ctags = set()
    for _, snap in graph.worldline(uid):
        inter = graph.interaction(snap.interaction_ctag)
        if inter.nout == 0:
            continue                      # blocked/aborted: no-op
        if inter.ctag in seen_ctags:
            continue                      # count each interaction once
        seen_ctags.add(inter.ctag)
        n_inter += 1
        if first_time < 0.0:
            first_time = inter.time
        last_proc, last_time = inter.process_id, inter.time
        _, is_el = classify(inter.process_id, inter.nout)
        if is_el:
            ever_el = True
        else:
            ever_inel = True
        if snap.role is Role.INCOMING:
            incoming.append(inter.ctag)
            if not inter.is_decay and inter.ctag > fctag:
                n_post += 1
        if (inter.ctag > fctag and inter.is_identity_preserving
                and any(s.uid == uid for s in inter.incoming)
                and any(s.uid == uid for s in inter.outgoing)):
            ever_id_resc = True
    if fcls is not INITIAL_CARRIED:
        first_time = ftime

    # ancestry walk from the final state (includes the formation interaction)
    if anc_index is None:
        anc_index = _AncestryIndex(graph)
    anc_ctags = anc_index.ancestor_ctags(final_state.state_id)
    anc_decay = anc_string = False
    for ctag in anc_ctags:
        inter = graph.interaction(ctag)
        if inter.nout == 0:
            continue
        if inter.is_decay:
            anc_decay = True
        coarse, _ = classify(inter.process_id, inter.nout)
        if coarse == "STRING":
            anc_string = True

    return ProtonHistory(
        uid=uid, formation_class=fcls, formation_ctag=fctag,
        formation_time=ftime, formation_process=fproc,
        n_interactions=n_inter, n_post_scatter=n_post,
        last_process=last_proc, last_time=last_time, first_time=first_time,
        ever_elastic=ever_el, ever_inelastic=ever_inel,
        ever_identity_rescatter=ever_id_resc,
        ancestry_decay=anc_decay, ancestry_string=anc_string,
        incoming_ctags=tuple(incoming))


def final_protons(graph: ReactionGraph) -> Dict[int, ParticleSnapshot]:
    """Final-state protons reconstructed from file15 alone
    (uid_final_states pattern, provenance.py, filtered to protons)."""
    return {u: s for u, s in uid_final_states(graph).items()
            if is_proton_snapshot(s)}


def proton_histories(graph: ReactionGraph) -> Dict[int, ProtonHistory]:
    """uid -> ProtonHistory for every final-state proton of the event."""
    idx = _AncestryIndex(graph)
    return {u: proton_history(graph, u, s, anc_index=idx)
            for u, s in final_protons(graph).items()}


# ----------------------------------------------------------------------
# pair classification (step 9 axes)
# ----------------------------------------------------------------------

def pair_axis_a(h1: ProtonHistory, h2: ProtonHistory) -> str:
    """Axis A from the two histories (see module docstring)."""
    if h1.formation_ctag >= 0 and h1.formation_ctag == h2.formation_ctag:
        return A_SAME_PRODUCTION
    later = max(h1.formation_ctag, h2.formation_ctag)
    common = set(h1.incoming_ctags) & set(h2.incoming_ctags)
    if any(c > later for c in common):
        return A_DIRECT_PARTNERS
    return A_NO_DIRECT


def pair_axis_b(h1: ProtonHistory, h2: ProtonHistory) -> str:
    n1 = h1.n_post_scatter > 0
    n2 = h2.n_post_scatter > 0
    if n1 and n2:
        return B_BOTH
    if n1 or n2:
        return B_ONE
    return B_NEITHER


def pair_axis_c(h1: ProtonHistory, h2: ProtonHistory) -> str:
    """Sorted merged-formation-class pair label, e.g.
    'DECAY_PRODUCT|STRING_PRODUCT'."""
    a, b = sorted((merged_formation_class(h1.formation_class),
                   merged_formation_class(h2.formation_class)))
    return f"{a}|{b}"


def pair_axis_d(h1: ProtonHistory, h2: ProtonHistory) -> str:
    """Sorted pair of per-proton post-scatter bins, e.g. '0|2-3'."""
    a, b = sorted((post_scatter_bin(h1.n_post_scatter),
                   post_scatter_bin(h2.n_post_scatter)))
    return f"{a}|{b}"


def classify_pair(h1: ProtonHistory, h2: ProtonHistory) -> Dict[str, str]:
    return {"A": pair_axis_a(h1, h2), "B": pair_axis_b(h1, h2),
            "C": pair_axis_c(h1, h2), "D": pair_axis_d(h1, h2)}
