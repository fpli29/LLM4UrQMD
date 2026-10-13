# Intervention catalog (UrQMD 4.0)

Source-verified intervention candidates. **Execution is disabled in the
MVP**: `urqmd.run_intervention` is interface-only and returns
status `blocked`. Use `urqmd-agent list-interventions`,
`validate-intervention`, and `plan-intervention` for planning. Detailed
line references: `references/source_semantics.md` and
`docs/intervention_source_map.md`.

| intervention | type | scope / role | notes |
|---|---|---|---|
| CTOption(15)≠0 | CHANNEL REMOVAL | partial primary candidate | Zeroes **all** s-channel resonance formation: the meson-baryon channel (io=10) **and** the meson-meson channel (io=11), plus io=36/37 and the resonant part of the meson-baryon total cross section. Decays unaffected. It is **not** an MB-only switch. Guard in anndec.f:53-64. |
| CTOption(59)=0 | CHANNEL REMOVAL | negative-control candidate | Gates **only** the strangeness-exchange (STRX) channels 57-62 (and 63/64 at ≥2). Leaves all other MB and MM channels untouched. Gates in make22.f:6132-6183; default 1 (input.f:383). |
| tim truncation | EVOLUTION-TIME TRUNCATION | broad | `tim A B` stops all dynamics at t=A (the only stopping condition, urqmd.f:142), acting identically on every channel; undecayed resonances are then force-decayed by default. A broad temporal probe, orthogonal to any channel-specific switch. |
| CTOption(18)≠0 | FINAL-DECAY MODIFICATION | diagnostic | Disables the forced final decay sweep (urqmd.f:351-386): undecayed resonances are written to the final state as-is. Changes what is counted as final, not the dynamics. |
| MB_ONLY_PATCH | CHANNEL REMOVAL (Phase 1D: IMPLEMENTED, local confirmatory) | gates only iline=10 | No runtime switch removes MB-only inelastic/resonant channels; a source patch is required. Phase 1D implemented it locally as CTOption(100) (default 0 = bit-for-bit baseline; ON gates only the crossx io=10 branch, make22.f label 10, MB-class pairs; MM io=11 untouched; MB total sigma unchanged, normit redistributes). Protocol and hashes: physics_gate/phase1d/. Executable only as whitelisted condition `mb_only` with authorization `phase1d-confirmatory`; never redistributed as source. |

## Rules

- An intervention hypothesis must state the target mediator and the
  expected direction of the effect before planning.
- Prefer controls whose mechanical scope is disjoint from the primary
  candidate (e.g. a STRX-only switch vs. a resonance-formation switch)
  and orthogonal broad probes (time truncation) to bound systematics.
- Never propose editing the Fortran source through the Agent.
