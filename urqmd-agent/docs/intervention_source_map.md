# UrQMD 4.0 — Intervention source map: meson-baryon (MB) transport pathway

Compiled 2026-09-16 for Phase 1C-0. Every entry verified against the local
UrQMD 4.0 source. Note: `make22.f` contains BOTH the final-state generator
`make22` (lines 3-3213) and the cross-section routines `crossx/crossz`
(lines 4165-6607); line numbers below distinguish them.

## Pipeline overview

| step | file:line | routine | controlling condition | BB/MB/MM distinguished | elastic vs inelastic | resonance vs string |
|---|---|---|---|---|---|---|
| collision search | coload.f:212-251, 254-467 | `coload`/`collupd` | `tcoll<tmin`, hit sphere, `sigt/CTParam(67) > 10*pi*dst2` (coload.f:401-448) | via sigtot -> collclass | no | no |
| pair classification | scatter.f:1129-1263 | `collclass` | ityp ranges (comres.f:12-16, 58-60) | YES (classes 1-15) | no | no |
| channel table | blockres.f:806-853 | `SigmaLn` data | row = collision class | YES | elastic = first partial (blockres.f:800-801) | channels listed per class |
| partial cross sections | make22.f:4165-4305 | `crossx`/`crossz` | computed goto on `io` (4301-4305) | YES | YES | YES |
| unitarize + channel pick | scatter.f:247-266 | `normit` (anndec.f:716) + `getbran` (anndec.f:612-677) | roulette on partial sigmas; forced elastic iline=13 if sigsum<1d-10 (scatter.f:252-262) | — | YES | YES |
| final-state generation | scatter.f:382-390 -> make22.f:107-114 | `make22` | computed goto on `io` | YES | YES | YES |
| Pauli blocking | scatter.f:900-981 | `scatFinal`/`paulibl` | outgoing nucleons only; nexit=0 at scatter.f:977 | — | — | — |
| decay time | scatter.f:1005, dectim.f:51-97 | `dectim` | mass-dependent width | — | — | — |
| decay | coload.f:316-330, scatter.f:153-173, make22.f:705-750 | `anndec`/`anndex` | dectime entry = collision with partner 0 | — | — | — |

## Pair classification (BB/MB/MM)

`collclass(ityp1,iso31,ityp2,iso32)` (scatter.f:1129), called at
scatter.f:219, returns the `SigmaLn` row `isigline`:

- bbar-B: class 11, disabled entirely if CTOption(19)!=0 (scatter.f:1178-1182)
- pp/nn: 2; pn: 1; ND: 3; N*N: 4; D*N: 5; DD: 6; DN*: 7; DD*: 8 (scatter.f:1185-1225)
- **MB ("Boson-Baryon"): class 9** — one hadron in [minmes,133), other
  <= maxbar (scatter.f:1226-1229)
- **MM ("Boson-Boson"): class 10** (scatter.f:1230-1234)
- D*D*/D*N*/N*N*: 12; all remaining BB: 13; charm classes 14/15 (1235-1252)
- photons (ityp=minmes) never collide (scatter.f:1169-1172)

Elastic vs inelastic is NOT decided up front: all partial channels of the
SigmaLn row get cross sections from `crossx` (scatter.f:224-240), partials
are unitarized to the total by `normit` (scatter.f:247), and the exit
channel (elastic is always the first partial) is drawn by `getbran`
roulette (scatter.f:250-266). Fallback: sum sigma < 1d-10 -> forced
elastic, iline=13 (scatter.f:252-262).

## Process IDs (iline) relevant to MB

MB partial channels (SigmaLn row 9, blockres.f:834): 26 (elastic),
10 (s-channel resonance formation), 27 (1-string), 28 (2-string),
36 (forward delay, only CTOption(34)>=2), 57-62 (strangeness exchange).

| iline | meaning | make22 label | crossx label |
|---|---|---|---|
| 10 | **MB s-channel resonance formation** (2->1 via `anndec`, nexit=1); also charmonium-baryon class; sigma=0 above mresmax=6 GeV (make22.f:4397-4400) | 231-235 | 4395-4404 |
| 11 | MM -> M* resonance formation (2->1) | 238-242 | 4406-4409 |
| 26 | MB elastic (AQM-scaled pi-p elastic) | 816-866 | 4819-4834 |
| 27 | MB s-channel one-string; **splits inside make22 label 27 (868-1014)**: ms1 > CTParam(60)=3 GeV -> string fragmentation (nexit>1); else collapse to a single resonance via `anndec` (<1.67 GeV) or continuous spectra (1.67-3 GeV) -> nexit=1 | 868-1014 | 4836-4880 |
| 28 | MB -> 2 strings (t-channel) | -> label 15 | 4882-4920 |
| 13 | generic AQM elastic (fallback) | 251-272 | 4460-4486 |
| 14 | inelastic resonance excitation (BB rows only — NOT in the MB SigmaLn row) | 274-342 | 4488-4514 |
| 15 | XX -> 2 strings; NN string threshold e > 2*(1.08+CTParam(2)) = 3.7 GeV (make22.f:4529-4535) | 345-... | 4516-4543 |
| 23 | BBbar annihilation -> 2 strings | 752-814 | 4588-4601 |
| 36,37 | MB->B' / MM->M' with Danielewicz forward time-delay (only CTOption(34)=2,3,4) | 1062-1065 | 5034-5080 |
| 38 | MM elastic (5 mb constant) | -> 13 | 5081-5094 |
| 57-62 | strangeness exchange (see below) | 1661-2890 | 6132-6183 |
| 63,64 | YY->XiN and inverse (BB class; need CTOption(59)>=2) | 2791-... | 6185-6200 |

MB total cross section = iline 25 (SigmaLn row 9 col 2, blockres.f:834):
crossx label 25 (make22.f:4627-4817). Measured channels (pi+-p, K+-p, K0N,
gamma-p) use HERA fits; the generic MB total melts the `anndec` resonance
sum (sigmb) below meltpoint with AQM-scaled HERA pi-p above (4683-4770);
strangeness-exchange sigma is added into the MB total at make22.f:4750-4762.

Resonance-vs-string decision for MB: no single decision routine — it is the
competition of partial cross sections. iline 10 sigma: Breit-Wigner sum in
`anndex` (anndec.f:503-538), zero above 6 GeV. iline 27 sigma: xmelt ramp
3-6 GeV, zero below 1.7 GeV, quark-annihilation topology required
(make22.f:4836-4880). iline 28: xmelt 0->full 3-6 GeV (make22.f:4917).

## Strangeness exchange 57-62 (CTOption(59) gating)

Gating in crossx at make22.f:6132-6183: each of 57-62 returns 0 if
`CTOption(59).lt.1` (6136, 6146, 6155, 6163, 6172, 6181); 63/64 need
`CTOption(59).ge.2` (6190, 6198). Default CTOption(59)=1 (input.f:383).
Channels: 57 = K-N/aK0N -> Y+pi (Lambda vs Sigma0 split by CTParam(72)=0.55,
make22.f:1685-1687); 58 = pi+Y -> K+N (inverse); 59 = KY -> Xi+pi;
60 = Xi+pi -> KY; 61 = Xi+K -> Omega+pi; 62 = Omega+pi -> Xi+K.
63/64 = YY <-> Xi+N (BB class, added to BB totals at make22.f:4438-4454).
All 57-62 live in the MB SigmaLn row — they ARE MB-class channels.

## Resonance propagation and decay

Decay time set at production: `dectime = dectim(...) + tform`
(scatter.f:1005); tau = -ln(1-r)/Gamma, Lorentz-dilated (dectim.f:63,96-97);
stable particles get 1.d34 (dectim.f:89-92). Decays are collision-table
entries with partner 0 (coload.f:316-330), executed as iline=20
(scatter.f:173) via make22 label 20 (make22.f:705-750) -> `anndec(1,...)`.
Resonances CAN re-scatter before decay: normal entries in the collision
search (coload.f:302-330); no special suppression except formation-time
sigma reduction for string-fragmentation leading hadrons (coload.f:411-422).
`stb` input pins listed ityps stable in final decays (input.f:771-778).

## The `tim` input (verified semantics)

`tim A B` reads caltim=A, outtim=B (input.f:767-769). Without `cdt` and with
eos=0: dtimestep = outtim (fast cascade, input.f:827). nsteps =
caltim/dtimestep (input.f:829). Collision searching is bounded by the
current timestep end (coload.f:302-403); the loop processes entries
chronologically (urqmd.f:142-246). **The only stopping condition is
t = caltim** (urqmd.f:142). End of evolution (urqmd.f:351-403): with
CTOption(18)=0 (default), ALL remaining unstable particles are force-decayed
via `scatter(i,0,...)` with the Pauli blocker temporarily disabled
(CTOption(10)=1, urqmd.f:359-361, restored 386), `stb`-listed ityps
skipped, unstable daughters decayed iteratively (urqmd.f:378-380). With
CTOption(18)!=0, undecayed resonances are written out as-is (warning
input.f:890-893). The cutoff is purely temporal: it acts identically on all
channels, stops collision searching globally, and — by default — applies a
final decay sweep to undecayed resonances. With a single timestep
(dtimestep = outtim = caltim, our configuration) the dynamics up to caltim
is bit-identical to a longer run with the same seed.

## Existing switches altering MB treatment (verified)

| control | effect | source |
|---|---|---|
| CTOption(15)!=0 | `anndec` returns sigma=0 (anndec.f:52-64, inside io=0 branch): kills ALL MB and MM s-channel resonance formation (io=10, 11, 36, 37) and the resonant part of the MB total (label 25). Decays (io=1) UNAFFECTED. Label 'allow mm&mb-scattering', default 0 (input.f:297-298) | anndec.f:64; make22.f:4402, 4408, 4684, 4700, 5038-5073 |
| CTOption(12)!=0 | ALL string cross sections zero (io=15, 23, 24, 27, 28, 39); runtime stop if a string exit is still drawn | make22.f:347-351, 4518, 4591, 4606, 4618, 4849, 4894, 5016 |
| CTOption(34)=2,3,4 | Danielewicz-Pratt forward time-delay: modifies MB resonant sigma, enables io=36/37, changes decay-time law | dectim.f:61-88; make22.f:4707-4721, 5034-5080 |
| CTOption(59) | >=1: STREX 57-62 on; >=2: adds 63/64 + hyperon-pair totals | make22.f:4438-4454, 6136-6199 |
| CTOption(61)=1 | NN inelastic off (BB only) | make22.f:4283-4292 |
| CTOption(7) | =1: NN elastic re-drawn; =-1: all inelastic partials zero (elastic only) | scatter.f:269-276; anndec.f:807-811 |
| CTOption(19)!=0 | no bbar collisions at all | scatter.f:1180 |
| CTParam(60)=3.0 | MB single-string -> resonance collapse threshold | make22.f:935-940; input.f:217 |
| CTParam(72)=0.55 | Sigma0/(Sigma0+Lambda) ratio in STREX channel 57 | make22.f:1685; input.f:241 |
| CTParam(1)=1.0 | global decay-width (lifetime) scale | dectim.f:53-56 |

## Verified negative results

- NO runtime control disables MB collisions only, or MB inelastic only
  (collclass 9/10 assigned unconditionally, scatter.f:1226-1234).
- NO runtime control selects resonance-vs-string treatment for MB
  specifically (only global CTOption(12), CTParam(60), hardcoded meltpoints).
- NO channel-threshold keywords (meltpoints hardcoded; only CTParam(2),
  (4), (34), (60) are runtime-accessible).
- Dead CTOptions (label but no code usage): 26, 43, 66; 51 does not exist.
  CTOption indices >68 are accepted by `cto` but are no-ops
  (numcto=400, options.f:3-12; parsing input.f:780-786).
