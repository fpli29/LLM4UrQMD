"""Human-readable chronological UID worldline traces.

Usage:
    python -m urqmd_agent.history.trace <file15> --uid 28
    python -m urqmd_agent.history.trace <file15> --summary

Raw UrQMD ityp integers are shown; no particle names are invented.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from .parse_f15 import parse_f15
from .reaction_graph import ReactionGraph
from .schema import DECAY_PROCESS_ID, Role


def classify(graph: ReactionGraph, uid: int, ctag: int) -> str:
    """How the interaction at ctag relates to this uid's worldline."""
    inter = graph.interaction(ctag)
    in_uids = [s.uid for s in inter.incoming]
    out_uids = [s.uid for s in inter.outgoing]
    is_in = uid in in_uids
    is_out = uid in out_uids
    decay = inter.process_id == DECAY_PROCESS_ID and inter.nin == 1

    if is_in and is_out:
        return "preserves UID (identity-preserving transport)"
    if is_in and not is_out:
        if decay:
            return f"consumes UID (1->{inter.nout} decay, mother)"
        return f"consumes UID ({inter.nin}->{inter.nout} reaction)"
    if is_out and not is_in:
        if decay:
            return f"creates UID (1->{inter.nout} decay daughter)"
        return f"creates UID ({inter.nin}->{inter.nout} reaction)"
    return "not involved"


def trace_uid(graph: ReactionGraph, uid: int) -> str:
    lines: List[str] = []
    entries = graph.worldline(uid)
    if not entries:
        return f"UID {uid}: not present in this event"

    lines.append(f"UID {uid} worldline ({len(entries)} state records):")
    lines.append(
        f"{'time[fm/c]':>10} {'ctag':>5} {'proc':>4} {'role':>4} {'uid':>6} "
        f"{'ityp':>5} {'chg':>4} {'str':>4}  relation")
    for sid, snap in entries:
        inter = graph.interaction(sid.ctag)
        lines.append(
            f"{inter.time:10.3f} {sid.ctag:5d} {inter.process_id:4d} "
            f"{snap.role.value:>4} {snap.uid:6d} {snap.ityp:5d} "
            f"{snap.charge:4d} {snap.strangeness:4d}  "
            f"{classify(graph, uid, sid.ctag)}")
    passages = graph.identity_passages_for(uid)
    if passages:
        lines.append(
            f"identity-preserving passages: {len(passages)} "
            f"(ctags: {', '.join(str(p.ctag) for p in passages)})")
        lines.append(
            "note: incoming and outgoing states of these interactions are "
            "distinct graph nodes; no self-cycle is created.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="urqmd_agent.history.trace",
        description="Chronological UID worldline trace from UrQMD 4.0 file15")
    ap.add_argument("file15", help="path to the file15 history file")
    ap.add_argument("--uid", type=int, help="UID to trace")
    ap.add_argument("--summary", action="store_true",
                    help="print event/graph summary instead of a UID trace")
    args = ap.parse_args(argv)

    event = parse_f15(args.file15)
    graph = ReactionGraph(event)

    if args.summary:
        h = event.header
        print(f"file: {args.file15}")
        print(f"event {h.event}: Ap={h.ap} At={h.at} elab={h.ebeam} AGeV "
              f"ecm={h.ecm} GeV b={h.bimp} fm")
        for k, v in graph.summary().items():
            print(f"{k}: {v}")
        return 0

    if args.uid is None:
        ap.error("either --uid or --summary is required")
    print(trace_uid(graph, args.uid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
