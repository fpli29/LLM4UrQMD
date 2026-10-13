# UrQMD 4.0 reaction taxonomy (source-derived, Phase 1B)

The process ID in a file15 interaction header is the variable `iline`
(common block `/inewpart/`, newpart.f:46,58), set in scatter.f
(scatter.f:226,265 after channel selection; `iline=20` for decays at
scatter.f:173; `iline=13` forced-elastic fallback at scatter.f:262) and
written verbatim at output.f:601. Positive IDs are dispatched to `crossx`
(make22.f:4165, computed goto at make22.f:4301-4305); negative IDs go to
`crossz` (detailed balance, make22.f:4262, `excl=.true.`, DB factor at
make22.f:4355-4361). Exit channels are built by `make22` (computed goto at
make22.f:111-114). Cross-section channel tables: sigmaLN pointer arrays,
blockres.f:806-853.

The UrQMD manual PDF was not consulted (no PDF text extraction tool
available); every entry below is verified from source alone.

## Verified process-ID table (IDs observed in 7.7 GeV Au+Au histories)

| ID | meaning | incoming class | string exit? | inverse of | source |
|---|---|---|---|---|---|
| -2 | N* N -> N N (detailed balance) | N*+N | no | 2 | blockres.f:818-820; make22.f:4262,4355,1041-1059 |
| -3 | Delta* N -> N N (detailed balance) | Delta*+N | no | 3 | blockres.f:821-823; make22.f:4262,4355,1041 |
| -5 | Delta N* -> N N (detailed balance) | Delta+N* | no | 5 | blockres.f:827-829; make22.f:4262,4355,1041 |
| -6 | Delta Delta* -> N N (detailed balance) | Delta+Delta* | no | 6 | blockres.f:830-832; make22.f:4262,4355,1041 |
| -7 | B* B* -> N N (detailed balance) | two high resonances | no | 7 | blockres.f:842-844; make22.f:4262,4355,1041 |
| 1 | NN -> N Delta | NN | no | — | blockres.f:809,813; make22.f:4313,120-130 |
| 2 | NN -> N N* | NN | no | — | blockres.f:809,813; make22.f:4313,132-141 |
| 3 | NN -> N Delta* | NN | no | — | blockres.f:809,813; make22.f:4313,143-152 |
| 4 | NN -> Delta Delta | NN | no | — | blockres.f:809,813; make22.f:4313,154-164 |
| 5 | NN -> Delta N* | NN | no | — | blockres.f:809,813; make22.f:4313,166-176 |
| 6 | NN -> Delta Delta* | NN | no | — | blockres.f:809,813; make22.f:4313,178-188 |
| 7 | NN -> B* B* (N*N*, N*Delta*, Delta*Delta*) | NN | no | — | blockres.f:809,813; make22.f:4313,190-213 |
| 8 | N Delta -> Delta Delta (isospin-summed) | Delta+N | no | — | blockres.f:816; make22.f:4370-4389,215-225 |
| 10 | M B -> B' (s-channel resonance formation) | meson-baryon | no | — | blockres.f:834; make22.f:4395-4404,231-236 |
| 11 | M M -> M' (s-channel resonance formation) | meson-meson | no | — | blockres.f:837; make22.f:4406-4409,238-243 |
| 13 | generic elastic (AQM); forced-elastic fallback | any | no | — | make22.f:4460-4486,251-272; scatter.f:262 |
| 14 | AQM inelastic 2->2 resonance excitation | resonance+N/Delta, generic BB | no | — | make22.f:4488-4514,274-342 |
| 15 | string excitation/fragmentation (XX -> 2 strings) | NN, resonance-B, MB (via 28), bbar (via 24) | YES | — | blockres.f:809,813; make22.f:4516-4543,345-679 |
| 17 | p n elastic (tables + fit) | pn | no | — | blockres.f:809; make22.f:4550-4553,686-703; scatter.f:269 |
| 19 | p p / n n elastic | pp, nn | no | — | blockres.f:813; make22.f:4560-4563,686-703 |
| 20 | decay 1->n (no cross section; sigpart=0) | any unstable | no | — | scatter.f:173,281; make22.f:705-749; anndec.f:3-28; decay tables blockres.f:724-784 |
| 22 | bbar-b elastic | bbar-b | no | — | blockres.f:840; make22.f:4581-4586 |
| 23 | bbar-b annihilation -> 2 strings | bbar-b | YES | — | blockres.f:840; make22.f:4588-4601,752-814 |
| 24 | bbar-b diffractive string excitation | bbar-b | YES | — | blockres.f:840; make22.f:4603-4613 (-> label 15) |
| 26 | M B elastic (pi+p fit, AQM-scaled) | meson-baryon | no | — | blockres.f:834; make22.f:4819-4834,816-866 |
| 27 | M B -> 1 string (s-channel); nout=1 -> resonance via anndec fallback | meson-baryon | YES (nout>1) | — | blockres.f:834; make22.f:4836-4880,868-1014 (fallback make22.f:942) |
| 28 | M B -> 2 strings (t-channel) | meson-baryon | YES | — | blockres.f:834; make22.f:4882-4920 (-> label 15) |
| 30 | N Delta -> N N (parameterized detailed balance) | Delta+N | no | (param. of 1) | blockres.f:816; make22.f:4935-4953 |
| 31 | Delta Delta -> Delta N (parameterized DB) | Delta+Delta | no | (param. of 5) | blockres.f:825; make22.f:4955-4978 |
| 32 | Delta Delta -> N N (parameterized DB) | Delta+Delta | no | (param. of 4) | blockres.f:825; make22.f:4980-4997 |
| 35 | N Delta inelastic resonance excitation (AQM) | Delta+N | no | — | blockres.f:816; make22.f:5028-5032 (-> label 14) |
| 38 | meson-meson elastic, constant 5 mb | meson-meson | no | — | blockres.f:837; make22.f:5081-5094 (-> label 13) |
| 39 | bbar-b inelastic (non-annihilation) | bbar-b | no | — | blockres.f:840; make22.f:4615-4624 (-> label 14) |
| 57 | strangeness exchange K N -> Y pi | meson-baryon | no | 58 | blockres.f:834; make22.f:6132-6138; requires CTOption(59)>=1 |
| 58 | strangeness exchange pi Y -> K N (inverse of 57) | meson-baryon | no | 57 | blockres.f:834; make22.f:6142-6149 |
| 59 | strangeness exchange K Y -> Xi pi | meson-baryon | no | 60 | blockres.f:834; make22.f:6151-6157 |
| 60 | strangeness exchange Xi pi -> Y K (inverse of 59) | meson-baryon | no | 59 | make22.f:6159-6165, 7437+ |
| 61 | strangeness exchange Xi K -> Omega pi | meson-baryon | no | 62 | make22.f:6167-6173 |
| 62 | strangeness exchange Omega pi -> Xi K (inverse of 61) | meson-baryon | no | 61 | make22.f:6175+ |

CTOption(59)=1 by default (input.f:383, "activate Baryon-Baryon
strangeness exchange"; the crossx gates at make22.f:6136,6146,6155 enable
the meson-baryon channels 57/58/59 in sigmaLN line 9). All Phase 0/1A/1B
runs used this default — strangeness exchange was always active.

Process 27 is classed by outgoing multiplicity: nout==1 -> anndec
resonance fallback (class MB), nout>1 -> string (class STRING)
(make22.f:868-1014, fallback at make22.f:942).

## Coarse classes (used in all Phase-1B outputs; fine process_id always kept)

| coarse class | process IDs |
|---|---|
| DECAY | 20 |
| STRING | 15, 24, 27 (nout>1), 28 |
| ANNIHILATION | 23 |
| BB | 1-8, 14, 35, 39, 30, 31, 32, -2, -3, -5, -6, -7 |
| MB | 10, 27 (nout==1) |
| MM | 11 |
| STRX | 57, 58, 59, 60, 61, 62 |
| ELASTIC | 13, 17, 19, 22, 26, 38 |
| OTHER | anything else (unexpected; raises attention via counts) |

Box-mode IDs 80/81 (scatter.f:76,92) and hydro ID 91 (output.f:645) never
occur in collision-mode cascade runs.

## Observed anomaly — RESOLVED

Audit histories contain rare records with nout=0 (e.g. one process_id=13
2->0 record in ~12000 audited interactions; also 17 2->0 and 20 1->0).
Source resolution: scatfinal restores the incoming particles and sets
nexit=0 when a collision/decay is Pauli-blocked or rejected
(scatter.f:905-983, `nexit=0` at scatter.f:977 — the ONLY cascade-mode path
producing nout=0; the other nexit=0 site, output.f:643, is hydro-only
process 91). Therefore nout==0 marks an aborted interaction: the particles
survive unchanged. Phase-1B provenance treats such records as no-ops
(excluded from final-state membership, formation tracing, N_part^actual,
and post-formation counting; flagged `blocked` in species_changes).
