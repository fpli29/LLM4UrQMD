"""Single-event history tracing tools (file15).

All tracing goes through history.parse_f15 / reaction_graph / provenance /
genealogy. The state -> interaction -> state semantics of the reaction
graph is preserved verbatim; no uid self-cycles are ever produced.
"""

from __future__ import annotations

from typing import Optional

from ..core.errors import ToolError
from ..core.result import ToolResult
from ..history.genealogy import (decay_mother_of_formation,
                                 production_interaction_of, strangeness_root)
from ..history.parse_f15 import parse_f15
from ..history.provenance import (ANTIKAON0, KAON0, LAMBDA,
                                  find_species_formation, species_changes,
                                  uid_final_states)
from ..history.reaction_graph import build_graph
from ..history.schema import DECAY_PROCESS_ID, Role
from ..history.taxonomy import classify, coarse_class
from ._common import resolve_repo_path
from .registry import ANALYSIS, ToolSpec, register

_SPECIES_KEYS = {
    "lambda": LAMBDA,
    "kaon": KAON0, "kaon0": KAON0, "k0": KAON0,
    "antikaon": ANTIKAON0, "antikaon0": ANTIKAON0, "antik0": ANTIKAON0,
}


def _snapshot_dict(snap) -> dict:
    return {
        "uid": snap.uid, "ctag": snap.interaction_ctag,
        "role": snap.role.value, "ordinal": snap.ordinal,
        "time": snap.r0,
        "position": [snap.rx, snap.ry, snap.rz],
        "four_momentum": list(snap.four_momentum()),
        "mass": snap.mass, "ityp": snap.ityp, "iso3": snap.iso3,
        "charge": snap.charge, "strangeness": snap.strangeness,
        "origin": snap.origin, "lstcoll": snap.lstcoll, "ncoll": snap.ncoll,
    }


def _interaction_dict(inter) -> dict:
    cls, is_el = classify(inter.process_id, inter.nout)
    return {
        "ctag": inter.ctag, "process_id": inter.process_id,
        "class": cls, "is_elastic": is_el, "is_decay": inter.is_decay,
        "nin": inter.nin, "nout": inter.nout,
        "pauli_blocked": inter.nout == 0,
        "identity_preserving": inter.is_identity_preserving,
        "time": inter.time, "sqrts": inter.sqrts,
        "baryon_density": inter.baryon_density,
    }


def trace_uid(f15_path: str, uid: int) -> ToolResult:
    """Chronological worldline of one uid: states interleaved with their
    interactions (particle-state -> interaction -> particle-state)."""
    path = resolve_repo_path(f15_path)
    event = parse_f15(path)
    graph = build_graph(event)
    states = graph.worldline(uid)
    if not states:
        return ToolResult.error(
            f"uid {uid} not present in {f15_path} "
            f"({len(graph.uids())} uids in event)",
            provenance={"tool": "urqmd.trace_uid"})

    # chronological interleaving per interaction: incoming states, the
    # interaction node, then the outgoing states (blocked records with
    # nout==0 keep their incoming states and the interaction node)
    by_ctag = {}
    for sid, snap in states:
        by_ctag.setdefault(sid.ctag, []).append((sid, snap))
    sequence = []
    for ctag in sorted(by_ctag):
        group = by_ctag[ctag]
        for sid, snap in group:
            if snap.role is Role.INCOMING:
                sequence.append({"type": "state", **_snapshot_dict(snap)})
        sequence.append({"type": "interaction",
                         **_interaction_dict(graph.interaction(ctag))})
        for sid, snap in group:
            if snap.role is Role.OUTGOING:
                sequence.append({"type": "state", **_snapshot_dict(snap)})
    n_identity = len(graph.identity_passages_for(uid))
    summary = (f"uid {uid} in {f15_path}: {len(states)} states across "
               f"{len({s.interaction_ctag for _, s in states})} "
               f"interaction(s), {n_identity} identity-preserving "
               f"passage(s); no uid self-cycles")
    return ToolResult.ok(summary, {
        "f15_path": f15_path, "uid": uid,
        "event": {"ap": event.header.ap, "at": event.header.at,
                  "bimp": event.header.bimp, "ecm": event.header.ecm},
        "sequence": sequence,
        "n_states": len(states),
        "n_identity_passages": n_identity,
    }, provenance={"tool": "urqmd.trace_uid"})


def trace_final_particle(f15_path: str, uid: Optional[int] = None,
                         species: Optional[str] = None) -> ToolResult:
    """Full provenance of one final-state particle: producer, species
    formation, post-formation transport, decay mother and upstream
    strangeness origin."""
    path = resolve_repo_path(f15_path)
    event = parse_f15(path)
    graph = build_graph(event)
    finals = uid_final_states(graph)

    if uid is None:
        if species is None:
            raise ToolError("trace_final_particle needs uid or species")
        key = _SPECIES_KEYS.get(species.strip().lower())
        if key is None:
            raise ToolError(
                f"unknown species {species!r}; choose from "
                f"{sorted(_SPECIES_KEYS)}")
        candidates = sorted(u for u, s in finals.items()
                            if (s.ityp, s.iso3) == key)
        if not candidates:
            return ToolResult.error(
                f"no final-state {species} particle in {f15_path}",
                provenance={"tool": "urqmd.trace_final_particle"})
        uid = candidates[0]   # deterministic: smallest uid
    if uid not in finals:
        return ToolResult.error(
            f"uid {uid} is not a final-state particle in {f15_path}",
            provenance={"tool": "urqmd.trace_final_particle"})

    final_snap = finals[uid]
    key = (final_snap.ityp, final_snap.iso3)

    producers = graph.producers(uid)
    producer = _interaction_dict(producers[0]) if producers else None

    formation = find_species_formation(graph, uid, key)
    f_inter = graph.interaction(formation.interaction_ctag)
    formation_d = _interaction_dict(f_inter)

    post = []
    for change in species_changes(graph, uid):
        if change.ctag <= formation.interaction_ctag or change.blocked:
            continue
        inter = graph.interaction(change.ctag)
        post.append({"ctag": change.ctag, "process_id": inter.process_id,
                     "class": coarse_class(inter.process_id, inter.nout),
                     "time": inter.time,
                     "identity_preserving": change.identity_preserving})

    decay_mother = None
    mother_production = None
    if f_inter.process_id == DECAY_PROCESS_ID:
        mother = decay_mother_of_formation(graph, formation)
        if mother is not None:
            decay_mother = _snapshot_dict(mother)
            prod = production_interaction_of(graph, mother.uid)
            mother_production = (_interaction_dict(prod)
                                 if prod is not None else "INITIAL_STATE")

    root = strangeness_root(graph, uid, key, classify)
    root_d = {
        "outcome": root.outcome,
        "n_candidates": len(root.candidates),
        "preexisting_branch": root.preexisting_branch,
        "note": root.note,
        "candidates": [
            {"ctag": c.ctag, "time": c.time, "process_id": c.process_id,
             "class": c.coarse_class, "sqrts": c.sqrts, "rhob": c.rhob}
            for c in root.candidates],
    }

    data = {
        "f15_path": f15_path, "uid": uid,
        "final_state": _snapshot_dict(final_snap),
        "producer": producer,
        "formation": formation_d,
        "n_postformation_interactions": len(post),
        "postformation": post,
        "decay_mother": decay_mother,
        "mother_production": mother_production,
        "strangeness_root": root_d,
    }
    summary = (f"uid {uid} final (ityp={key[0]}, iso3={key[1]}): formed in "
               f"{formation_d['class']} (process {formation_d['process_id']}"
               f", ctag {formation_d['ctag']}, t={formation_d['time']:.2f} "
               f"fm/c), {len(post)} post-formation interaction(s), "
               f"decay mother: {'yes' if decay_mother else 'no'}, "
               f"strangeness origin: {root.outcome}")
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.trace_final_particle"})


register(ToolSpec(
    name="urqmd.trace_uid",
    description=(
        "Trace one particle uid through a file15 history: the chronological "
        "state -> interaction -> state sequence with process classes, times "
        "and four-momenta. Identity-preserving passages are marked; no uid "
        "self-cycles are produced. uid not present -> error."),
    input_schema={"type": "object", "properties": {
        "f15_path": {"type": "string"},
        "uid": {"type": "integer"}},
        "required": ["f15_path", "uid"]},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=trace_uid,
))

register(ToolSpec(
    name="urqmd.trace_final_particle",
    description=(
        "Full microscopic provenance of one final-state particle in a "
        "file15 history: final state, producer interaction, "
        "species-forming interaction, post-formation transport, decay "
        "mother (if decay-formed) and strangeness-root outcome. If uid is "
        "omitted, species ('lambda', 'kaon', 'antikaon') selects the "
        "first (smallest-uid) final particle of that species "
        "deterministically."),
    input_schema={"type": "object", "properties": {
        "f15_path": {"type": "string"},
        "uid": {"type": "integer"},
        "species": {"type": "string",
                    "enum": ["lambda", "kaon", "antikaon"]}},
        "required": ["f15_path"]},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=trace_final_particle,
))
