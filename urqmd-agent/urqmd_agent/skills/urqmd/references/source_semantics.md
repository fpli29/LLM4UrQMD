# Source-verified switch semantics (UrQMD 4.0)

Distilled from `docs/intervention_source_map.md`; every line number below
was re-verified against the local source on 2026-09-16. Option indices are
written as `CTOption[15]` here (rather than the Fortran syntax) to keep the
blind-workspace text neutral; the meaning is identical.

## Output-file keyword inversion

Input keywords `f13`, `f14`, `f15`, `f16`, `f19`, `f20` **suppress** the
matching output unit: each sets a `bfNN=.true.` flag and prints
"no output on unit NN" (input.f:795-816: f13→795, f14→798, f15→801,
f16→808, f19→811, f20→814). Output is **enabled** by the environment
variables `ftn13` … `ftn20`, read with `getenv` to obtain the target
filename (input.f:425-427). A unit with no `ftnNN` variable is not
written.

## CTOption default array

- `numcto = numctp = 400` (options.f:4-5); the arrays and default labels
  are declared at options.f:3-12.
- Defaults and labels are set pairwise (`CTOption[i]=value` /
  `CTOStrng(i)='label'`) in input.f:269-403; indices defined: 1-50,
  52-68. Index 51 does not exist (no default, no label, no code usage).
- `cto i v` / `ctp i v` input parsing: input.f:780-794. Indices beyond
  68 are accepted silently by `cto` but are **no-ops** — no code reads
  them.
- Dead CTOptions (label exists, no code usage): 26, 43, 66.
- Labels can be misleading. Only code semantics count; e.g.
  `CTOption[10]` is labelled "enable Pauli Blocker" (input.f:287-288) but
  `=1` **disables** Pauli blocking — the final-decay sweep sets
  `CTOption[10]=1` exactly for that purpose (urqmd.f:359-360).

## CTOption[15] — s-channel resonance-formation removal

Check inside the annihilation/formation (`io=0`) branch of `anndec`
(anndec.f:53-64): an early return with zero cross section when the option
is nonzero (guard at anndec.f:64). Effect:
returns zero cross section for **all** s-channel resonance formation —
the MB channel (io=10) **and** the MM channel (io=11), plus the
forward-delay variants io=36/37 — and for the resonant part of the MB
total cross section (label 25, make22.f:4684-4700). Decays (`io=1`) are
UNAFFECTED. Label: "allow mm&mb-scattering", default 0
(input.f:297-298). It is **not** an MB-only switch.

## CTOption[59] — strangeness exchange (STRX) gating

In `crossx` (make22.f:6132-6183): each STRX channel 57-62 returns zero
when the option is `< 1` (gates at 6136, 6146, 6155, 6163, 6172, 6181);
channels 63/64 additionally require the option to be `>= 2`
(make22.f:6190, 6198). Default is 1 (input.f:383). The STRX cross
sections are added into the MB total (make22.f:4748-4762). Channels
57-62 live in the MB SigmaLn row — they are MB-class channels; 63/64 are
BB-class. This switch touches only strangeness-exchange channels.

## CTOption[18] — forced final decay sweep

At end of evolution (urqmd.f:351-386): with the default
`CTOption[18]=0`, all remaining unstable particles are force-decayed via
`scatter(i,0,...)` with the Pauli blocker temporarily disabled
(`CTOption[10]=1` at urqmd.f:359-360, restored at urqmd.f:386);
`stb`-listed species are skipped; unstable daughters are decayed
iteratively. With `CTOption[18]≠0`, undecayed resonances are written to
the final state as-is.

## CTOption[62] — output-stage decay on a saved copy

Intermediate-output stages (urqmd.f:333-341): `prepout` decays unstable
particles on a saved copy of the state before `file14out`/`file13out`,
then `restore` + `colload` resume the undecayed evolution. Affects only
what intermediate output shows, not the dynamics.

## `tim` — evolution-time truncation

`tim A B` reads `caltim=A`, `outtim=B` (input.f:767-769). Without `cdt`
and with `eos=0`, `dtimestep = outtim` (input.f:827) and
`nsteps = caltim/dtimestep` (input.f:829). The only stopping condition is
`t = caltim` (urqmd.f:142). The cutoff is purely temporal: it acts
identically on all channels and stops collision searching globally; by
default the final decay sweep above is then applied. With a single
timestep (`dtimestep = outtim = caltim`) the dynamics up to `caltim` is
bit-identical to a longer run with the same seed.

## Collision classes and the iline=27 split

- `collclass` assigns collision classes in scatter.f:1129-1263;
  class 9 = "Boson-Baryon" (MB), class 10 = "Boson-Boson" (MM)
  (scatter.f:1226-1234), assigned unconditionally.
- iline=27 (MB one-string channel) splits at `CTParam(60)=3.0 GeV`
  (make22.f:935-940): above → string fragmentation (nout>1); below →
  collapse to a single resonance (nout=1).

## Verified absences

- No runtime switch disables MB collisions only, or MB inelastic only.
- No runtime switch selects resonance-vs-string treatment for MB
  specifically.
- No channel-threshold keywords (melt points are hardcoded).
