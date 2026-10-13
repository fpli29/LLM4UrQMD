# UrQMD Agent — architecture

## Layer diagram

```
+-------------------------------------------------------------+
| General-purpose LLM agent                                   |
| (Codex CLI, Claude Code, Kimi CLI, any shell-capable agent) |
| understands the question, plans the investigation, chooses  |
| tools, formulates hypotheses, decides what evidence is needed|
+---------------------------+---------------------------------+
                            |
+-------------------------------------------------------------+
| Skill / tool interface                                      |
| urqmd_agent/skills/urqmd/SKILL.md + references/             |
| CLI: bin/urqmd-agent (python3 -m urqmd_agent.cli)           |
| [later: optional MCP adapter — urqmd_agent/mcp/server.py]   |
+---------------------------+---------------------------------+
                            |
+-------------------------------------------------------------+
| Deterministic scientific tool layer                         |
| urqmd_agent/tools/*  — ToolSpecs in tools/registry.py       |
| urqmd_agent/agent/   — guardrails, tool_runner, trajectory  |
| urqmd_agent/core/    — ToolResult envelope, paths, config   |
| parses files, species identity, centrality, fits/bootstrap, |
| reaction history, genealogy, conservation checks, source    |
| semantics, intervention validation                          |
+---------------------------+---------------------------------+
                            |
+-------------------------------------------------------------+
| UrQMD 4.0 (Fortran binary + tables.dat + campaign data)     |
+-------------------------------------------------------------+
```

## Split of responsibilities

**LLM** — understand the physics question; plan the investigation; choose
and sequence tools; formulate falsifiable hypotheses; decide what evidence
is needed next; preserve ambiguity instead of inventing answers; write the
report. The LLM never computes numerical observables ad hoc.

**Deterministic layer** — parse file13/file15 strictly (no silent
recovery); species identity via source-verified mappings; centrality
binning; scaling fits and bootstrap uncertainties; reaction-history graph
and genealogy; conservation checks; source semantics with file:line
evidence; intervention validation. Every result is a `ToolResult`
envelope; every call passes the guardrails and is logged to the
trajectory.

**UrQMD 4.0** — the simulator itself, run only through `urqmd.run` with
the event cap and allowed-output-directory guardrails.

## MCP adapter (deferred)

Design: a thin mapping from each registered `ToolSpec` to one MCP tool
using the official `mcp` package — `name` → tool name, `description` →
tool description, `input_schema` → inputSchema verbatim, wire payload =
`ToolResult.to_dict()`. Dispatch would go through
`agent/tool_runner.call_tool`, so guardrails and trajectory logging are
identical to the CLI path.

Why deferred: the scientific core must stay dependency-light and must
never import MCP; the `mcp` dependency is not yet accepted. In the MVP,
execution is via the CLI, which already exposes the full registry with
the same JSON schemas. Adding the adapter later touches only
`urqmd_agent/mcp/server.py`.

## Vendor neutrality

The interface surface is plain files (SKILL.md), a shell CLI, and JSON.
Any shell-capable agent — Codex CLI, Claude Code, Kimi CLI, or others —
can operate the layer without vendor-specific integration.
