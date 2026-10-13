"""Temporal bipartite reaction graph over a parsed UrQMD file15 event.

Conceptual model (see docs/reaction_graph.md):

    particle-state  ->  interaction  ->  particle-state

- A *particle state* node is identified by StateId(ctag, role, ordinal),
  never by uid alone. The uid links multiple states along one worldline.
- An *interaction* node is keyed by its UrQMD collision tag (ctag).
- Edges: incoming state -> interaction -> outgoing state.
- Worldline relation: the same uid appearing as an outgoing state of an
  earlier interaction and as an incoming state of a later interaction.
- Identity-preserving transport: the same uid appearing as incoming AND
  outgoing of the SAME interaction. This is recorded explicitly; the two
  states remain distinct nodes, so no artificial self-cycle is created.
- Generic 2->n reactions are many-body hyperedges: no arbitrary one-to-one
  parent-child assignment between individual incoming and outgoing particles.
- Only for 1->n decays (process_id=20, nin=1, verified in Phase 0) are
  mother/daughter relations exposed.

Deterministic, standard-library only; no NetworkX dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .schema import (
    DECAY_PROCESS_ID,
    HistoryEvent,
    Interaction,
    ParticleSnapshot,
    Role,
    StateId,
)


@dataclass(frozen=True)
class WorldlineLink:
    """Temporal same-particle relation: outgoing state -> later incoming state."""

    uid: int
    from_state: StateId   # outgoing state (earlier interaction)
    to_state: StateId     # incoming state (later interaction)
    from_ctag: int
    to_ctag: int


@dataclass(frozen=True)
class IdentityPassage:
    """Same uid as incoming and outgoing of the SAME interaction.

    Recorded as a relation between two distinct states; NOT a graph cycle.
    """

    uid: int
    ctag: int
    in_state: StateId
    out_state: StateId


class ReactionGraph:
    """Deterministic temporal bipartite reaction graph for one event."""

    def __init__(self, event: HistoryEvent):
        self.event = event
        self.interactions: Dict[int, Interaction] = {}
        self.states: Dict[StateId, ParticleSnapshot] = {}
        # adjacency
        self._in_states: Dict[int, Tuple[StateId, ...]] = {}   # ctag -> incoming states
        self._out_states: Dict[int, Tuple[StateId, ...]] = {}  # ctag -> outgoing states
        # uid index: uid -> chronologically sorted state list
        self._uid_states: Dict[int, List[StateId]] = {}
        self.worldline_links: List[WorldlineLink] = []
        self.identity_passages: List[IdentityPassage] = []
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        for inter in self.event.interactions:
            if inter.ctag in self.interactions:
                raise ValueError(f"duplicate ctag {inter.ctag}")
            self.interactions[inter.ctag] = inter
            in_ids, out_ids = [], []
            for snap in inter.incoming:
                sid = snap.state_id
                if sid in self.states:
                    raise ValueError(f"duplicate state id {sid}")
                self.states[sid] = snap
                in_ids.append(sid)
            for snap in inter.outgoing:
                sid = snap.state_id
                if sid in self.states:
                    raise ValueError(f"duplicate state id {sid}")
                self.states[sid] = snap
                out_ids.append(sid)
            self._in_states[inter.ctag] = tuple(in_ids)
            self._out_states[inter.ctag] = tuple(out_ids)

            # identity-preserving passages within this interaction
            in_by_uid: Dict[int, List[StateId]] = {}
            for sid in in_ids:
                in_by_uid.setdefault(self.states[sid].uid, []).append(sid)
            for sid in out_ids:
                uid = self.states[sid].uid
                for in_sid in in_by_uid.get(uid, ()):
                    self.identity_passages.append(
                        IdentityPassage(uid=uid, ctag=inter.ctag,
                                        in_state=in_sid, out_state=sid))

        # uid index, chronologically ordered by (interaction ctag, role, ordinal)
        for sid, snap in self.states.items():
            self._uid_states.setdefault(snap.uid, []).append(sid)
        for uid in self._uid_states:
            self._uid_states[uid].sort()

        # worldline links: every outgoing state connected to the next
        # incoming state(s) of the same uid at a LATER interaction
        for uid, sids in self._uid_states.items():
            outs = [s for s in sids if s.role is Role.OUTGOING]
            ins = [s for s in sids if s.role is Role.INCOMING]
            for o in outs:
                for i in ins:
                    if i.ctag > o.ctag:
                        self.worldline_links.append(WorldlineLink(
                            uid=uid, from_state=o, to_state=i,
                            from_ctag=o.ctag, to_ctag=i.ctag))
        self.worldline_links.sort(key=lambda l: (l.uid, l.from_ctag, l.to_ctag))

    # ------------------------------------------------------------------
    # basic lookups
    def interaction(self, ctag: int) -> Interaction:
        return self.interactions[ctag]

    def state(self, state_id: StateId) -> ParticleSnapshot:
        return self.states[state_id]

    def incoming_states(self, ctag: int) -> Tuple[StateId, ...]:
        return self._in_states[ctag]

    def outgoing_states(self, ctag: int) -> Tuple[StateId, ...]:
        return self._out_states[ctag]

    def states_for_uid(self, uid: int) -> List[ParticleSnapshot]:
        """All snapshots of this uid, chronological (by ctag, role, ordinal)."""
        return [self.states[s] for s in self._uid_states.get(uid, [])]

    def worldline(self, uid: int) -> List[Tuple[StateId, ParticleSnapshot]]:
        """Chronological (state_id, snapshot) sequence of one uid worldline."""
        return [(s, self.states[s]) for s in self._uid_states.get(uid, [])]

    def uids(self) -> List[int]:
        return sorted(self._uid_states)

    # ------------------------------------------------------------------
    # reaction-level ancestry (NO arbitrary 1-to-1 parent matching)
    def producers(self, uid: int) -> List[Interaction]:
        """Interactions that have this uid in their OUTGOING set."""
        out = []
        for s in self._uid_states.get(uid, []):
            if s.role is Role.OUTGOING:
                out.append(self.interactions[s.ctag])
        return out

    def consumers(self, uid: int) -> List[Interaction]:
        """Interactions that have this uid in their INCOMING set."""
        out = []
        for s in self._uid_states.get(uid, []):
            if s.role is Role.INCOMING:
                out.append(self.interactions[s.ctag])
        return out

    def reaction_reactants(self, ctag: int) -> Tuple[ParticleSnapshot, ...]:
        """The incoming particle SET of a reaction (hyperedge tail)."""
        return tuple(self.states[s] for s in self._in_states[ctag])

    def reaction_products(self, ctag: int) -> Tuple[ParticleSnapshot, ...]:
        """The outgoing particle SET of a reaction (hyperedge head)."""
        return tuple(self.states[s] for s in self._out_states[ctag])

    # ------------------------------------------------------------------
    # decay-specific semantics (process_id=20, nin=1; verified Phase 0)
    def decay_mother(self, state_id: StateId) -> Optional[ParticleSnapshot]:
        """For an OUTGOING state of a 1->n decay: the unique incoming state."""
        snap = self.states[state_id]
        if snap.role is not Role.OUTGOING:
            return None
        inter = self.interactions[snap.interaction_ctag]
        if not inter.is_decay:
            return None
        return inter.incoming[0]

    def decay_daughters(self, state_id: StateId) -> Tuple[ParticleSnapshot, ...]:
        """For the INCOMING state of a 1->n decay: all outgoing daughters."""
        snap = self.states[state_id]
        if snap.role is not Role.INCOMING:
            return ()
        inter = self.interactions[snap.interaction_ctag]
        if not inter.is_decay:
            return ()
        return inter.outgoing

    # ------------------------------------------------------------------
    # graph walks (state level, deterministic)
    def ancestors_of_state(self, state_id: StateId) -> Tuple[frozenset, frozenset]:
        """All ancestor (states, interactions) of a state.

        Walk: state -> its interaction (if outgoing) -> incoming states ->
        worldline back to earlier outgoing states / identity passages -> ...
        Returns (state_ids, ctags) as frozensets.
        """
        seen_states: set = set()
        seen_ctags: set = set()
        stack = [state_id]
        while stack:
            sid = stack.pop()
            if sid in seen_states:
                continue
            seen_states.add(sid)
            snap = self.states[sid]
            ctag = snap.interaction_ctag
            if snap.role is Role.OUTGOING:
                # reaction ancestry: the full incoming SET of this interaction
                # (guard against reprocessing the same interaction node)
                if ctag in seen_ctags:
                    continue
                seen_ctags.add(ctag)
                for in_sid in self._in_states[ctag]:
                    if in_sid not in seen_states:
                        stack.append(in_sid)
            else:
                # incoming state: same particle may continue from an earlier
                # outgoing state (worldline) or from an identity passage
                for link in self.worldline_links_for(snap.uid):
                    if link.to_state == sid:
                        stack.append(link.from_state)
                for ip in self.identity_passages:
                    if ip.in_state == sid:
                        stack.append(ip.out_state)
        seen_states.discard(state_id)
        return frozenset(seen_states), frozenset(seen_ctags)

    def descendants_of_state(self, state_id: StateId) -> Tuple[frozenset, frozenset]:
        """All descendant (states, interactions) of a state."""
        seen_states: set = set()
        seen_ctags: set = set()
        stack = [state_id]
        while stack:
            sid = stack.pop()
            if sid in seen_states:
                continue
            seen_states.add(sid)
            snap = self.states[sid]
            ctag = snap.interaction_ctag
            if snap.role is Role.INCOMING:
                if ctag not in seen_ctags:
                    seen_ctags.add(ctag)
                    for out_sid in self._out_states[ctag]:
                        if out_sid not in seen_states:
                            stack.append(out_sid)
            else:
                for link in self.worldline_links_for(snap.uid):
                    if link.from_state == sid:
                        stack.append(link.to_state)
                for ip in self.identity_passages:
                    if ip.out_state == sid:
                        stack.append(ip.in_state)
        seen_states.discard(state_id)
        return frozenset(seen_states), frozenset(seen_ctags)

    def worldline_links_for(self, uid: int) -> List[WorldlineLink]:
        return [l for l in self.worldline_links if l.uid == uid]

    def identity_passages_for(self, uid: int) -> List[IdentityPassage]:
        return [p for p in self.identity_passages if p.uid == uid]

    # ------------------------------------------------------------------
    # human-oriented traces
    def trace_back(self, state_id: StateId) -> List[ParticleSnapshot]:
        """Ancestor snapshots sorted chronologically (deterministic)."""
        states, _ = self.ancestors_of_state(state_id)
        return [self.states[s] for s in sorted(states)]

    def trace_forward(self, state_id: StateId) -> List[ParticleSnapshot]:
        """Descendant snapshots sorted chronologically (deterministic)."""
        states, _ = self.descendants_of_state(state_id)
        return [self.states[s] for s in sorted(states)]

    # ------------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "interactions": len(self.interactions),
            "states": len(self.states),
            "unique_uids": len(self._uid_states),
            "multi_record_uids": sum(
                1 for s in self._uid_states.values() if len(s) > 1),
            "worldline_links": len(self.worldline_links),
            "identity_preserving_interactions": len(
                {p.ctag for p in self.identity_passages}),
            "identity_passages": len(self.identity_passages),
        }


def build_graph(event: HistoryEvent) -> ReactionGraph:
    return ReactionGraph(event)
