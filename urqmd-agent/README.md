# UrQMD Agent Skill & Tool Layer

A deterministic, source-verified tool layer and LLM skill for scientific
use of the hadronic transport code **UrQMD 4.0**. The layer lets an LLM
agent (or a human) build input decks, run event-capped simulations, parse
final-state (`file13`) and microscopic interaction-history (`file15`)
output, trace particle ancestry, and plan controlled transport
interventions — with every numerical observable produced by deterministic
code and every option semantics claim anchored to `file:line` references
in the UrQMD Fortran source.

This repository contains **only** the tool layer and the skill. The UrQMD
4.0 source code is **not** included and must be obtained separately (see
below); it is subject to its own license.

## Contents

| path | role |
|---|---|
| `urqmd_agent/skills/urqmd/` | the LLM skill: `SKILL.md` + source-verified reference notes |
| `urqmd_agent/cli/` | `urqmd-agent` argparse CLI (entry point to all tools) |
| `urqmd_agent/tools/` | tool registry: environment, simulation, source search, observables, history, genealogy, interventions, validation |
| `urqmd_agent/history/` | `file15` parser, reaction graph, provenance, genealogy, taxonomy, validation |
| `urqmd_agent/final_state/` | `file13` parser and per-event observables |
| `urqmd_agent/analysis/` | centrality binning, participant-scaling fits, provenance/genealogy statistics, azimuthal pair-kernel analysis, robustness |
| `urqmd_agent/production/` | validated run drivers (input template, per-event closure) |
| `urqmd_agent/knowledge/` | human-reviewed, source-verified knowledge catalog (`urqmd_v4.json`) |
| `urqmd_agent/agent/` | guardrails + trajectory logging (deterministic, no LLM calls) |
| `docs/` | architecture, output formats, taxonomy, guardrails, tool contracts |
| `bin/urqmd-agent` | convenience wrapper for `python3 -m urqmd_agent.cli` |

## Requirements

- An **UrQMD 4.0 source tree** (not redistributed here), compiled so that
  the tree contains the executable `urqmd.<arch>` (e.g. `urqmd.arm64`,
  `urqmd.x86_64`) and the collision tables file `tables.dat`.
- Python ≥ 3.9 with `numpy` (`pip install -r requirements.txt`).

## Setup

```bash
git clone <this repo> && cd urqmd-agent
pip install -r requirements.txt          # or: pip install -e .

# Point the tool layer at your UrQMD 4.0 tree:
export URQMD_HOME=/path/to/urqmd-4.0
# Optional overrides:
# export URQMD_EXE=urqmd.x86_64                    # executable name/path
# export URQMD_AGENT_OUTPUT_DIRS=/path/to/runs     # extra allowed output dirs

bin/urqmd-agent doctor
```

`doctor` reports the resolved UrQMD tree, executable, tables, compiler,
and whether the Fortran source differs from its git state. The tool layer
also works when placed directly inside the UrQMD tree (then `URQMD_HOME`
defaults to that tree and no environment variable is needed).

## Quickstart

```bash
# 1. Render a validated input deck (never executes anything)
bin/urqmd-agent make-input --ecm 7.7 --nev 1 --seed 12345

# 2. Run one event (default event cap: 100; per-event parse + closure checks)
bin/urqmd-agent run --ecm 7.7 --nev 1 --seed 12345 \
    --run-dir $URQMD_HOME/physics_gate/agent_runs/test --keep-raw

# 3. Inspect outputs and trace microscopic histories
bin/urqmd-agent final-state path/to/out.f13
bin/urqmd-agent trace-uid path/to/out.f15 <uid>
bin/urqmd-agent trace-final-particle path/to/out.f15 --species lambda

# 4. Verify option/process semantics against the source before using them
bin/urqmd-agent describe-option 56
bin/urqmd-agent describe-process 27 --nout 2
bin/urqmd-agent source-search "CTOption(56)"
```

Add `--json` to any command for the full machine-readable `ToolResult`
(status/summary/data/evidence/warnings/provenance). `bin/urqmd-agent
list-tools` prints the full tool registry with risk levels.

## Guardrails (deterministic, enforced before any tool body runs)

- Default event cap of 100 per run; larger runs require an explicit
  `--authorized-cap`.
- Run/output directories must live inside whitelisted output directories.
- No UrQMD source modification through the tool layer.
- Physics interventions are *planning-only*
  (`list-interventions` / `validate-intervention` / `plan-intervention`);
  execution is blocked except for frozen, preregistered conditions behind
  explicit human authorization tokens.
- Input-deck keywords `f13`…`f20` **suppress** output (counter-intuitive,
  source-verified); output is enabled via `ftnNN` environment variables.
  The run drivers handle this for you.
- `CTOption(56)=1` (unique particle IDs in `file15`) is pinned by the
  validated template so histories are always traceable.

## The skill

`urqmd_agent/skills/urqmd/SKILL.md` is a standalone agent skill (YAML
frontmatter + progressive-disclosure references under `references/`).
Copy the `urqmd` directory into your agent environment's skills path.
The skill teaches: safe run construction, the `fNN`/`ftnNN` inversion,
`CTOption(56)=1`, particle/process mapping via tools only, reaction-graph
semantics (particle *states*, not uids), provenance vs genealogy, and the
intervention guardrails. All factual claims are cross-checked against the
Fortran source and recorded with `file:line` references in
`references/source_semantics.md`.

## License and citation

This tool layer and skill are released under the MIT License (see
`LICENSE`). UrQMD itself is © its authors and distributed separately
under the UrQMD license; see https://urqmd.org/.

If you use this tool layer or skill in academic work, please cite the
associated manuscript (citation entry to be added upon publication).
