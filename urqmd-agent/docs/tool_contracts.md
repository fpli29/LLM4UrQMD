# Tool contracts

## ToolResult envelope (`urqmd_agent/core/result.py`)

Every tool call returns one envelope:

| field | type | meaning |
|---|---|---|
| `status` | str | `ok` / `blocked` / `error` |
| `summary` | str | one-paragraph human summary |
| `data` | dict | machine-readable payload (trustworthy only when status=ok) |
| `evidence` | list[str] | file:line or dataset citations backing the result |
| `warnings` | list[str] | diagnostics; on `error` they carry the failure cause |
| `provenance` | dict | run/tool lineage |

Status semantics: `ok` = completed and `data` trustworthy; `blocked` = a
guardrail refused the request, no partial side effects; `error` = the tool
failed. **An error is never silently converted to success** — the tool
runner wraps unexpected exceptions as `status=error` results, and strict
parsers raise rather than recover.

## ToolSpec (`urqmd_agent/tools/registry.py`)

Fields: `name`, `description`, `input_schema` (JSON Schema),
`output_schema`, `risk_level`, `requires_urqmd`, `physics_changing`,
`execution_enabled`, `handler`; `to_dict()` serializes everything except
the handler.

### Risk levels and MVP enablement matrix

| risk level | meaning | MVP |
|---|---|---|
| READ_ONLY | inspects source/knowledge, never runs UrQMD | enabled |
| ANALYSIS | deterministic computation over existing data | enabled |
| SIMULATION | launches UrQMD | enabled, event cap 100 (explicit authorization raises it) |
| PHYSICS_INTERVENTION | changes transport physics | DISABLED |
| SOURCE_MODIFICATION | would edit UrQMD source | DISABLED |

The registry rejects any physics-changing tool registered with
`execution_enabled=True`.

## Tools (23)

| tool | semantics | risk level |
|---|---|---|
| urqmd.doctor | environment/build/tables sanity check (URQMD_HOME, binary, tables.dat) | READ_ONLY |
| urqmd.source_search | grep the Fortran source, file:line evidence | READ_ONLY |
| urqmd.describe_option | source-verified semantics of an input option (CTOption/CTParam/keywords) | READ_ONLY |
| urqmd.describe_particle | source-verified ityp/iso3 ↔ PDG identity mapping | READ_ONLY |
| urqmd.describe_process | source-verified semantics of a file15 process ID (iline) | READ_ONLY |
| urqmd.list_interventions | catalog of source-verified intervention candidates | READ_ONLY |
| urqmd.validate_intervention | check a candidate intervention against source semantics | READ_ONLY |
| urqmd.plan_intervention | design (never execute) an intervention test | READ_ONLY |
| urqmd.validate_tools | registry self-check (specs well-formed) | READ_ONLY |
| urqmd.make_input | construct an input deck for inspection | ANALYSIS |
| urqmd.final_state_summary | summary of a file13 final-state file | ANALYSIS |
| urqmd.centrality | fractional-tie N_ch centrality binning | ANALYSIS |
| urqmd.scaling | participant-scaling exponent fit + bootstrap | ANALYSIS |
| urqmd.compare | compare scaling results between datasets | ANALYSIS |
| urqmd.trace_uid | interaction history of one unique particle id | ANALYSIS |
| urqmd.trace_final_particle | trace a final-state particle through file15 | ANALYSIS |
| urqmd.formation_provenance | formation-channel decomposition of final particles | ANALYSIS |
| urqmd.parent_genealogy | decay-ancestry decomposition | ANALYSIS |
| urqmd.strangeness_origin | origin of strange-quark content | ANALYSIS |
| urqmd.channel_scaling | scaling restricted to one reaction class | ANALYSIS |
| urqmd.run | launch an event-capped UrQMD run in an allowed directory | SIMULATION |
| urqmd.run_status | status of a launched run | SIMULATION |
| urqmd.run_intervention | interface-only; always blocked in the MVP | PHYSICS_INTERVENTION (disabled) |
