---
name: urqmd
description: Scientific use of UrQMD 4.0 through the validated urqmd_agent tool layer — environment checks, safe run construction, final-state and history analysis, reaction genealogy, intervention planning (execution disabled).
---

# UrQMD 4.0 Agent Skill

Use the `urqmd-agent` CLI (`bin/urqmd-agent`, or `python3 -m urqmd_agent.cli`
from the repo root) for everything below. Add `--json` for machine-readable
output. Exit codes: 0 ok, 2 blocked (guardrail), 1 error.

## 1. What UrQMD is, operationally

UrQMD is an event-by-event hadronic transport code: a cascade (collision
search + stochastic 2→n scatterings and 1→n decays) with optional mean-field
propagation. Runs are configured by an input deck read on stdin; **the
working directory must be the repository root** (the binary reads
`tables.dat` from cwd). Output files are selected by `ftnNN` environment
variables: `ftn13`, `ftn14`, `ftn15`, `ftn16`, `ftn19`, `ftn20` each name
the file written on Fortran unit NN; a unit without an `ftnNN` variable is
not written.

## 2. Locating URQMD_HOME

URQMD_HOME is the UrQMD repository root (the directory containing the
compiled `urqmd.<arch>` executable and `tables.dat`). When this tool layer
is checked out separately from UrQMD, point the environment variable
`URQMD_HOME` at the UrQMD tree; `URQMD_EXE` overrides the executable name
and `URQMD_AGENT_OUTPUT_DIRS` whitelists additional run-output
directories. `urqmd-agent doctor` reports the resolved paths, the binary
path, and table availability.

## 3. Version / build / tables check

Always run `urqmd-agent doctor` first. `tables.dat` must exist at the repo
root; the binary must exist and match the host architecture.

## 4. Safe run construction

1. `urqmd-agent make-input --ecm 7.7 --nev 20 --seed 12345 --out deck.in`
2. Inspect the deck.
3. `urqmd-agent run --ecm 7.7 --nev 20 --seed 12345 --run-dir <allowed dir>`

The default event cap is 100; larger runs need an explicit
`--authorized-cap`. Run directories must live inside the allowed output
directories (see `urqmd_agent/core/paths.py: ALLOWED_OUTPUT_DIRS`).

## 5. Output roles

- **file13 (`*.f13`)**: final-state particle list — one line per stable
  particle after the last timestep and final decays. It carries **no
  unique particle id**; identity beyond the species is not recoverable
  from file13 alone.
- **file15 (`*.f15`)**: microscopic interaction history — every collision
  and decay with incoming/outgoing particle records. This is the basis of
  all tracing tools.

## 6. CTOption(56)=1

With `cto 56 1`, file15 particle records carry a **unique lifetime id**
(output.f:609-611, 622-624) instead of a slot index. Without it, tracing
across interactions is ambiguous. All validated campaigns set it.

## 7. WARNING — inverted output-keyword logic

The input-deck keywords `f13 f14 f15 f16 f19 f20` **SUPPRESS** the
corresponding output file (input.f:795-816, "no output on unit NN"). The
environment variables `ftn13` … `ftn20` **ENABLE** the output by naming
the target file (input.f:425-427). Putting `f15` in a deck *removes* the
history output. Never use the `fNN` keywords; always set `ftnNN`.

## 8. Particle mapping

- Lambda = (ityp 41, iso3 0, PDG 3122); K0 = (106, −1, 311);
  anti-K0 = (−106, +1, −311).
- Physical strangeness is S = −strit(ityp): `strit` counts strange quarks
  with the particle/antiparticle sign (blockres.f:1038-1060); the s quark
  carries S = −1 (blockres.f:1117). A Lambda has S = −1, a K0 has S = +1.
- A particle is a **resonance iff its width > 0**; zero-width species are
  stable in the final state.
- Never hand-map species. Always use `urqmd-agent describe-particle`.

## 9. Centrality convention

Centrality classes are defined by the **fractional-tie N_ch binning**:
0–10 / 10–20 / 20–30 / 30–40 / 40–60 / 60–80 %. Obtain them only via
`urqmd-agent centrality`; never invent impact-parameter cuts.

## 10. Reaction-history graph semantics

The history is a bipartite graph of particle-states ↔ interactions. A
particle-**state** is identified by (ctag, role, ordinal) — **not** by
uid: an identity-preserving elastic scattering keeps the uid, so a
uid-keyed graph would contain self-cycles. One uid spans a chain of
states connected by interactions.

## 11. Provenance vs genealogy

- **Provenance** (`urqmd-agent provenance`): the formation class of a
  final particle — through which channel it last came into existence.
- **Genealogy** (`urqmd-agent genealogy`, `strangeness-origin`): for a
  particle produced by a 1→n decay, the unique incoming particle of that
  decay; then the production process of that ancestor; then the earliest
  carrier of the strange-quark content. Use provenance for channel
  decomposition, genealogy for ancestry questions.

## 12. Generic 2→n reactions

NEVER assign a unique particle-to-particle ancestor within a 2→n
reaction. Both incoming particles contribute; keep reaction-hyperedge
semantics (an outgoing particle's origin is the interaction, not one of
the two inputs).

## 13. Ambiguous ancestry

Report ancestry verdicts as one of: UNIQUE_ROOT /
MULTIPLE_COMPATIBLE_ROOTS / PREEXISTING_STRANGENESS / UNRESOLVED.
Never resolve an ambiguous ancestry arbitrarily to make a cleaner story.

## 14. Intervention guardrails

Intervention **execution is disabled** in this build. Planning only, via
`urqmd-agent list-interventions`, `validate-intervention`,
`plan-intervention`. `urqmd.run_intervention` exists as an interface but
always returns status `blocked`.

## 15. Numerical observables come from tools only

Yields, centrality binning, scaling-exponent fits, and bootstrap
uncertainties come ONLY from the deterministic tools (`centrality`,
`scaling`, `compare`, `channel-scaling`, `provenance`, `genealogy`). The
LLM never computes them ad hoc from raw files and never paraphrases an
error bar.

## 16. Cite source semantics before touching options

Before setting any CTOption/CTParam or interpreting a process ID, cite
the source via `urqmd-agent describe-option`, `describe-process`, or
`source-search`. Labels in the deck can be misleading; only the code
semantics count.

## Reference files

- `references/source_semantics.md` — switch semantics verified against
  the Fortran source (suppression inversion, CTOption default array,
  decay-sweep and output-stage switches, dead options).
- `references/particle_semantics.md` — ityp/iso3/PDG mapping, strangeness
  sign, resonance-by-width, resonance families.
- `references/reaction_taxonomy.md` — iline → coarse class table.
- `references/intervention_catalog.md` — intervention candidates and
  their source-verified scope (planning only; execution disabled).
