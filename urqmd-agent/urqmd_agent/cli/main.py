"""argparse CLI for the UrQMD Agent tool layer.

Every subcommand maps onto a tool registered in
``urqmd_agent.tools.registry`` and is dispatched by name through
``urqmd_agent.agent.tool_runner.call_tool``. Tool handlers are never
imported directly here; ``urqmd_agent.tools`` is imported lazily inside
the dispatch path so that ``--help`` stays fast.

Exit codes: 0 = status ok, 2 = status blocked, 1 = status error.
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

EXIT_BY_STATUS = {"ok": 0, "blocked": 2, "error": 1}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="urqmd-agent",
        description=(
            "UrQMD Agent CLI: deterministic scientific tools for "
            "UrQMD 4.0. All results follow the ToolResult envelope "
            "(status/summary/data/evidence/warnings/provenance)."
        ),
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        help="print the full ToolResult as JSON (indent=2)",
    )
    common.add_argument(
        "--session",
        default=None,
        help="session ID for scientific trajectory logging (JSONL)",
    )
    common.add_argument(
        "--agent-note",
        default=None,
        help="short user-visible note recorded in the trajectory log",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def cmd(name, tool, help_text, **kwargs):
        p = sub.add_parser(name, parents=[common], help=help_text, **kwargs)
        p.set_defaults(tool=tool)
        return p

    cmd("doctor", "urqmd.doctor",
        "environment/build/tables sanity check (URQMD_HOME, exe, tables.dat)")

    p = cmd("describe-option", "urqmd.describe_option",
            "source-verified semantics of an input option")
    p.add_argument("option", help='option name, e.g. "15" or "tim"')

    p = cmd("describe-process", "urqmd.describe_process",
            "source-verified semantics of a file15 process ID (iline)")
    p.add_argument("process_id", type=int, help="iline process ID")
    p.add_argument("--nout", type=int, default=None,
                   help="outgoing multiplicity (disambiguates iline=27)")

    p = cmd("describe-particle", "urqmd.describe_particle",
            "source-verified particle identity mapping")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ityp", type=int, help="UrQMD ityp (requires --iso3)")
    grp.add_argument("--pdg", type=int, help="PDG Monte Carlo ID")
    p.add_argument("--iso3", type=int, default=None,
                   help="2*I3 isospin projection (with --ityp)")

    p = cmd("source-search", "urqmd.source_search",
            "grep the UrQMD source for a term, with file:line evidence")
    p.add_argument("term", help="search term")
    p.add_argument("--file-filter", default=None, help="glob, e.g. 'make22.f'")
    p.add_argument("--max-hits", type=int, default=None)

    p = cmd("make-input", "urqmd.make_input",
            "construct an UrQMD input deck (inspect before urqmd.run)")
    p.add_argument("--ecm", type=float, required=True, help="sqrt(s_NN) in GeV")
    p.add_argument("--nev", type=int, required=True, help="number of events")
    p.add_argument("--seed", type=int, required=True, help="random seed")
    p.add_argument("--history", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="request file15 history output (ftn15) [default]")
    p.add_argument("--out", default=None, help="write the deck to this path")

    p = cmd("run", "urqmd.run",
            "launch an event-capped UrQMD run from a constructed deck")
    p.add_argument("--ecm", type=float, required=True)
    p.add_argument("--nev", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--run-dir", required=True,
                   help="must be inside an allowed output directory")
    p.add_argument("--keep-raw", action="store_true",
                   help="retain raw outputs after successful parsing")
    p.add_argument("--authorized-cap", type=int, default=None,
                   help="explicitly authorized event cap (default 100)")

    p = cmd("run-status", "urqmd.run_status", "status of a launched run")
    p.add_argument("--run-id", default=None)

    p = cmd("final-state", "urqmd.final_state_summary",
            "summary of a file13 final-state particle file")
    p.add_argument("f13_path", help="path to a .f13 file")

    p = cmd("centrality", "urqmd.centrality",
            "fractional-tie N_ch centrality binning of a campaign dataset")
    p.add_argument("--dataset", default="phase1b")

    p = cmd("scaling", "urqmd.scaling",
            "participant-scaling exponent fit with bootstrap uncertainties")
    p.add_argument("--dataset", default="phase1b")
    p.add_argument("--species", default=None, choices=["lambda", "kaon"])

    p = cmd("compare", "urqmd.compare",
            "compare scaling results between two datasets")
    p.add_argument("--dataset-a", required=True)
    p.add_argument("--dataset-b", required=True)
    p.add_argument("--species", default=None)

    p = cmd("trace-uid", "urqmd.trace_uid",
            "full interaction history of one unique particle ID in file15")
    p.add_argument("f15_path")
    p.add_argument("uid", type=int)

    p = cmd("trace-final-particle", "urqmd.trace_final_particle",
            "trace a final-state particle back through file15 history")
    p.add_argument("f15_path")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--uid", type=int)
    grp.add_argument("--species", default=None)

    p = cmd("provenance", "urqmd.formation_provenance",
            "formation-channel decomposition of final-state particles")
    p.add_argument("--dataset", default="phase1b")
    p.add_argument("--species", default=None)

    p = cmd("genealogy", "urqmd.parent_genealogy",
            "decay-ancestry decomposition of final-state particles")
    p.add_argument("--dataset", default="phase1b2")
    p.add_argument("--species", default=None)

    p = cmd("strangeness-origin", "urqmd.strangeness_origin",
            "origin of the strange quark content of final-state particles")
    p.add_argument("--dataset", default="phase1b2")
    p.add_argument("--species", default=None)
    p.add_argument("--f15-path", default=None,
                   help="single-history mode (with --uid)")
    p.add_argument("--uid", type=int, default=None)

    p = cmd("channel-scaling", "urqmd.channel_scaling",
            "participant scaling restricted to one formation/reaction class")
    p.add_argument("--dataset", required=True)
    p.add_argument("--species", required=True)
    p.add_argument("--category", required=True,
                   help="coarse reaction class, e.g. DECAY, STRING, MB")

    cmd("list-interventions", "urqmd.list_interventions",
        "catalog of source-verified intervention candidates")

    p = cmd("validate-intervention", "urqmd.validate_intervention",
            "check an intervention candidate against source semantics")
    p.add_argument("intervention", help='e.g. "CTOption(15)", "CTOption(59)", "tim"')
    p.add_argument("--target-mediator", default=None)
    p.add_argument("--hypothesis", default=None)

    p = cmd("plan-intervention", "urqmd.plan_intervention",
            "design (never execute) an intervention test of a hypothesis")
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--mediator", required=True)
    p.add_argument("--desired-perturbation", default=None)

    p = sub.add_parser("list-tools", parents=[common],
                       help="list the tool registry")
    p.set_defaults(tool=None)

    p = sub.add_parser("build-knowledge", parents=[common],
                       help="rescan UrQMD source, diff against the knowledge "
                            "snapshot, write urqmd_v4_scan.json")
    p.set_defaults(tool=None)

    return parser


def _arguments(args: argparse.Namespace) -> Dict[str, Any]:
    """Map parsed CLI arguments onto the tool's argument names."""
    if args.command == "doctor":
        return {}
    if args.command == "describe-option":
        return {"option": args.option}
    if args.command == "describe-process":
        out = {"process_id": args.process_id}
        if args.nout is not None:
            out["nout"] = args.nout
        return out
    if args.command == "describe-particle":
        if args.ityp is not None and args.iso3 is None:
            raise SystemExit("describe-particle: --ityp requires --iso3")
        if args.pdg is not None:
            return {"pdg": args.pdg}
        return {"ityp": args.ityp, "iso3": args.iso3}
    if args.command == "source-search":
        out = {"term": args.term}
        if args.file_filter is not None:
            out["file_filter"] = args.file_filter
        if args.max_hits is not None:
            out["max_hits"] = args.max_hits
        return out
    if args.command == "make-input":
        out = {"ecm": args.ecm, "nev": args.nev, "seed": args.seed,
               "history": args.history}
        if args.out is not None:
            out["out"] = args.out
        return out
    if args.command == "run":
        out = {"ecm": args.ecm, "nev": args.nev, "seed": args.seed,
               "run_dir": args.run_dir, "keep_raw": args.keep_raw}
        if args.authorized_cap is not None:
            out["authorized_cap"] = args.authorized_cap
        return out
    if args.command == "run-status":
        out = {}
        if args.run_id is not None:
            out["run_id"] = args.run_id
        return out
    if args.command == "final-state":
        return {"f13_path": args.f13_path}
    if args.command == "centrality":
        return {"dataset": args.dataset}
    if args.command == "scaling":
        out = {"dataset": args.dataset}
        if args.species is not None:
            out["species"] = args.species
        return out
    if args.command == "compare":
        out = {"dataset_a": args.dataset_a, "dataset_b": args.dataset_b}
        if args.species is not None:
            out["species"] = args.species
        return out
    if args.command == "trace-uid":
        return {"f15_path": args.f15_path, "uid": args.uid}
    if args.command == "trace-final-particle":
        out = {"f15_path": args.f15_path}
        if args.uid is not None:
            out["uid"] = args.uid
        if args.species is not None:
            out["species"] = args.species
        return out
    if args.command == "provenance":
        out = {"dataset": args.dataset}
        if args.species is not None:
            out["species"] = args.species
        return out
    if args.command == "genealogy":
        out = {"dataset": args.dataset}
        if args.species is not None:
            out["species"] = args.species
        return out
    if args.command == "strangeness-origin":
        out = {"dataset": args.dataset}
        if args.species is not None:
            out["species"] = args.species
        if args.f15_path is not None:
            out["f15_path"] = args.f15_path
        if args.uid is not None:
            out["uid"] = args.uid
        return out
    if args.command == "channel-scaling":
        return {"dataset": args.dataset, "species": args.species,
                "category": args.category}
    if args.command == "list-interventions":
        return {}
    if args.command == "validate-intervention":
        out = {"intervention": args.intervention}
        if args.target_mediator is not None:
            out["target_mediator"] = args.target_mediator
        if args.hypothesis is not None:
            out["hypothesis"] = args.hypothesis
        return out
    if args.command == "plan-intervention":
        out = {"hypothesis": args.hypothesis, "mediator": args.mediator}
        if args.desired_perturbation is not None:
            out["desired_perturbation"] = args.desired_perturbation
        return out
    raise SystemExit(f"no argument mapping for command {args.command!r}")


def _emit(result, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(result.to_dict(), indent=2))
        return
    print(result.summary)
    for key, value in result.data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            print(f"  {key}: {value}")
        elif isinstance(value, list) and all(
            isinstance(v, (str, int, float)) for v in value
        ):
            print(f"  {key}: {', '.join(str(v) for v in value)}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")


def _dispatch(tool: str, arguments: Dict[str, Any], json_mode: bool,
              session_id: Optional[str] = None,
              agent_note: Optional[str] = None) -> int:
    from ..core.result import ToolResult

    try:
        import urqmd_agent.tools  # noqa: F401  (populates the registry)
        from ..agent.tool_runner import call_tool
    except ImportError as exc:
        result = ToolResult.error(f"tool layer unavailable: {exc}")
        _emit(result, json_mode)
        return EXIT_BY_STATUS["error"]
    result = call_tool(tool, arguments, session_id=session_id,
                       agent_note=agent_note)
    _emit(result, json_mode)
    return EXIT_BY_STATUS.get(result.status, 1)


def _list_tools(json_mode: bool) -> int:
    try:
        import urqmd_agent.tools  # noqa: F401  (populates the registry)
        from ..tools.registry import REGISTRY
    except ImportError as exc:
        print(f"error: tool layer unavailable: {exc}", file=sys.stderr)
        return 1
    specs = [REGISTRY[name] for name in sorted(REGISTRY)]
    if json_mode:
        print(json.dumps([spec.to_dict() for spec in specs], indent=2))
        return 0
    for spec in specs:
        first_line = spec.description.strip().splitlines()[0]
        enabled = "enabled" if spec.execution_enabled else "DISABLED"
        print(f"{spec.name:32s} {spec.risk_level:22s} {enabled:9s} {first_line}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list-tools":
        return _list_tools(args.json)
    if args.command == "build-knowledge":
        from .knowledge import build_knowledge

        return build_knowledge(json_mode=args.json)
    return _dispatch(args.tool, _arguments(args), args.json,
                     session_id=getattr(args, "session", None),
                     agent_note=getattr(args, "agent_note", None))


if __name__ == "__main__":
    sys.exit(main())
