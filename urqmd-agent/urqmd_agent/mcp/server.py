"""MCP server adapter for the UrQMD Agent tool layer — DESIGN STUB.

Design
------
Each ToolSpec registered in ``urqmd_agent.tools.registry`` would be exposed
as one MCP tool via the official ``mcp`` package (FastMCP):

    ToolSpec.name          -> MCP tool name
    ToolSpec.description   -> MCP tool description
    ToolSpec.input_schema  -> MCP inputSchema (JSON Schema, verbatim)
    ToolSpec.output_schema -> documented result shape; the wire payload is
                              ToolResult.to_dict() (status/summary/data/
                              evidence/warnings/provenance)

The adapter would be a *thin mapping only*: it would call
``urqmd_agent.agent.tool_runner.call_tool`` so that guardrails and
trajectory logging behave identically to the CLI path. No physics, parsing,
or guardrail logic would live here.

Why deferred
------------
* The scientific core must stay dependency-light; importing the ``mcp``
  package would add a hard dependency for every analysis user.
* The scientific core must never depend on MCP: nothing under
  ``urqmd_agent/{core,analysis,history,particles,final_state,production,
  tools}`` imports this package.
* In the MVP, agents execute tools through the CLI
  (``python3 -m urqmd_agent.cli ...``), which already exposes the full
  registry with the same JSON schemas. The MCP adapter can be added later
  without touching the core once the ``mcp`` dependency is accepted.

See docs/agent_architecture.md for the full architecture.
"""


def serve():
    raise NotImplementedError(
        "MCP adapter deferred: see docs/agent_architecture.md"
    )
