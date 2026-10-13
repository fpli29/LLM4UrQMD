# Safety and guardrails

All guardrails are enforced deterministically — none consults the LLM or
its prose. Enforcement points: `urqmd_agent/agent/guardrails.py` (raises
`GuardrailError`), the registry flags in
`urqmd_agent/tools/registry.py` (`execution_enabled`, `risk_level`,
`physics_changing`), and `urqmd_agent/agent/tool_runner.py` (converts
guardrail rejections to `status=blocked`, exceptions to `status=error`).

1. **Event-count cap (100 default).** `guardrails.check_event_count`
   refuses `nev > DEFAULT_EVENT_CAP` (100, `core/config.py`) unless the
   caller passes an explicit `authorized_cap`. A larger cap is an
   authorization act, not a default.
2. **Allowed output directories only.** `guardrails.check_output_dir`
   restricts run directories to `agent_eval/blind_workspace/outputs` and
   `physics_gate/agent_runs` (`core/paths.py: ALLOWED_OUTPUT_DIRS`), and
   rejects paths too long for the Fortran `ftnNN` character*77 buffers.
3. **No arbitrary shell strings through scientific tools.** Tools accept
   typed arguments per their JSON schema; nothing is interpolated into a
   shell command. Path arguments are validated, not concatenated into
   commands.
4. **No source modification through the Agent.**
   `guardrails.check_no_source_modification` always raises; the registry
   refuses any SOURCE_MODIFICATION tool with `execution_enabled=True`.
5. **No intervention execution.** `urqmd.run_intervention` is
   interface-only: registered `execution_enabled=False`, so the tool
   runner returns `status=blocked`; `guardrails
   .check_no_intervention_execution` backs this up inside the handler
   layer.
6. **No deletion of raw outputs before parse/validation succeeds.**
   `urqmd.run` keeps raw f13/f15/log files until the strict parsers have
   succeeded; `keep_raw=False` cleans up only after validation.
7. **No arbitrary CTOption values without a prior describe step.**
   `guardrails.check_ctoption` requires `described=True`, obtainable only
   from a prior `urqmd.describe_option` / `validate_intervention` result
   (labels are known to be misleading, e.g. CTOption(10)).
8. **No unsupported species mapping.** Species identity goes through
   `urqmd.describe_particle` (source-verified tables) or the call fails
   with `status=error`; hand-mapped ityp/PDG pairs are never accepted.
9. **No silent parser recovery.** The file13/file15 parsers are strict:
   malformed records raise, and the tool layer surfaces them as
   `status=error` with the diagnostic in `warnings`. A partially parsed
   file is never presented as a clean result.
10. **Expert-reference material never readable from blind mode.** The
    leakage scanner (`urqmd_agent/cli/leakage.py:
    scan_blind_workspace`) recursively checks
    `agent_eval/blind_workspace` filenames and content for expert-report
    names, mechanism vocabulary, and headline numbers;
    `agent_eval/blind_workspace/LEAKAGE_CHECK.md` documents the pattern
    list, exemptions, and the latest PASS result.

Violations of 1–2 and 7 produce `status=blocked`; violations of 8–9
produce `status=error`; 4–5 are blocked unconditionally.
