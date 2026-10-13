# Resonance-family classification in UrQMD 4.0 (Phase 1B2, Step 2)

Every rule below was verified directly against the local UrQMD 4.0 source.
The implementation is `urqmd_agent/particles/resonance_families.py`.
Nothing here is assumed from physics memory.

## ityp numbering scheme (comres.f:12-60)

| ityp range | family | source |
|---|---|---|
| 1 | nucleon N (ground state) | `minnuc=1`, comres.f:12,77 |
| 2-23 | N* resonances | `numnuc=23`, comres.f:19,22 |
| 24-40 | Delta + Delta* | `mindel=24, numdel=17`, comres.f:20,23-24 |
| 41-53 | Lambda + Lambda* | `minlam=41, numlam=13`, comres.f:36,40-41 |
| 54-62 | Sigma + Sigma* | `minsig=54, numsig=9`, comres.f:37,42-43 |
| 63-68 | Xi + Xi* | `mincas=63, numcas=6`, comres.f:38,44-45 |
| 69 | Omega | `minome=69`, comres.f:39,46-47 |
| 70 | Lambda_c | `minlamc=70`, comres.f:53-55 |
| 1-70 | all baryons | `minbar/maxbar`, comres.f:59-60 |
| 100-139 | all mesons | `minmes=100, maxmes=139`, comres.f:13-16 |
| \|ityp\|>1000 | PYTHIA/PDG particles (`pdgid = ityp-1000`) | ityp2pdg.f:174-181 |

Negative ityp = antiparticle; tables are indexed by |ityp| and the flavor
sign is restored by `iabs(i)/i` (e.g. strit, blockres.f:1058-1060). Meson
multiplets with even 2*I (eta, omega, phi, f0, ...) are self-conjugate and
have no negative ityp (ityp2pdg.f:189-196).

Names per multiplet (N(1440)=2 ..., Lambda=41, L(1405)=42 ..., Sigma=54,
S(1385)=55 ..., Xi=63, X(1530)=64 ..., Omega=69, K*=108): `partname`,
ityp2pdg.f:257-411.

## Strangeness (strit)

`strit(i)` (blockres.f:1038-1062): table lookup at |ityp|, sign flip for
antiparticles.

- `strres` (blockres.f:192-194): ityp 1-40 -> 0; 41-53 -> 1; 54-62 -> 1;
  63-68 -> 2; 69 -> 3; 70 -> 0.
- `strmes` (blockres.f:197-201): -1 at 106 (K), 108 (K*), 110, 113, 117,
  121, 125, 129; +1 at 138, 139 (D_s, charm sector); 0 elsewhere.

IMPORTANT SIGN CONVENTION: strit counts strange quarks, so the physical
strangeness is S = -strit (stated in the `fchg` comment, blockres.f:1117:
"s(s)=-1"). Checks: strit(41) = +1 -> Lambda S=-1; strit(106) = -1 -> K0
S=+1; strit(-106) = +1 -> anti-K0 S=-1; strit(69) = 3 -> Omega S=-3.
The file15 `strangeness` field carries the raw strit convention; all
zero/nonzero and conservation tests in the history layer are
convention-independent, and physical S quoted in reports uses S = -strit.

## Ground state vs resonance

There is no separate "stable ityp" cutoff: a particle is a resonance iff
its width is nonzero. Stability test: `if(WID .GT. 1.d-10)` (dectim.f:61);
width-zero particles never decay. `widit(i)` dispatches to
`widmes(|i|)`/`widres(|i|)` (blockres.f:1173-1189).

- Zero-width baryons (widres, blockres.f:56-81): 1 (N), 41 (Lambda),
  54 (Sigma), 63 (Xi), 69 (Omega), 70 (Lambda_c). Everything else -
  including Delta(1232) (width 0.120 GeV, blockres.f:66) - is a resonance.
- Zero-width mesons (widmes, blockres.f:104-121): 100 (gamma), 101 (pi),
  102 (eta), 106 (K), 107 (eta'), plus charm/charmonium 133, 135-139 kept
  stable (blockres.f:120). D* (134) has width 0.002.
- PYTHIA particles (|ityp|>1000) and charm mesons |ityp|>=133 are forced
  stable (`dectim=1.d34`, dectim.f:37-46).

Note: `minres=2, maxres=40` (comres.f:26-30) is only the range of
"nonstable & nonstrange baryons"; it does NOT cover strange resonances and
is not used as a resonance test.

## iso3 and charge

iso3 = 2*I3 everywhere (iso.f:13-16; blockres.f:868,1117). Charge:
`Q = (iso3 + b - strit + chrmit)/2` with b = sign(ityp) for baryons, 0 for
mesons (`fchg`, blockres.f:1092-1124). Checks: proton (1,+1) -> 1;
Lambda (41,0) -> 0; Sigma+ (54,+2) -> 1; K0 (106,-1) -> 0;
anti-K0 (-106,+1) -> 0.

## ityp -> PDG

`pdgid(ityp, iso3)` (ityp2pdg.f:2-253) via table `idtab(3,181)`.
Anchors: (41,0) -> 3122; (106,-1) -> 311 (K0); (106,+1) -> 321 (K+);
(1,+1) -> 2212; (24,-3..+3) -> 1114/2114/2214/2224 (Delta);
(55,-2/0/+2) -> 3114/3214/3224 (Sigma(1385)); (108) -> 313/323 (K*);
(64) -> 3314/3324 (Xi(1530)); (69) -> 3334 (Omega).
Known table gaps (pdgid returns 0): N* ityp 11-13, 15-22; Delta* 34-39;
Xi* 65, 67, 68 (ityp2pdg.f:218-222). Family classification never depends
on PDG; raw ityp/iso3 are kept in every output row for audit.

## Decay handling (process 20)

Decay slots have `iline=20` (scatter.f:152-173). The decay time is sampled
from the mass-dependent width (`dectim`, dectim.f:49-66); the decay itself
is performed by `anndex` (anndec.f:192-217) with branching fractions from
`branres/branmes/...` (data blockres.f:380-507, channel itypes
blockres.f:724-784).

## Family labels used in Phase 1B2

`family_of(ityp, iso3)` returns one of:

    STRANGE_BARYON_RESONANCE      (e.g. Lambda* 42-53, Sigma* 55-62, Xi* 64-68)
    NONSTRANGE_BARYON_RESONANCE   (N* 2-23, Delta 24-40)
    STRANGE_MESON_RESONANCE       (K* 108, 110, 113, 117, 121, 125, 129)
    NONSTRANGE_MESON_RESONANCE    (other mesons with widmes > 0)
    STRANGE_BARYON_GROUND         (41, 54, 63, 69 and antiparticles)
    NONSTRANGE_BARYON_GROUND      (1)
    STRANGE_MESON_GROUND          (106)
    NONSTRANGE_MESON_GROUND       (100, 101, 102, 107)
    CHARM_BARYON / CHARM_MESON    (70, 133-139)
    PYTHIA                        (|ityp| > 1000)

A decay mother is always a resonance by construction (zero-width particles
never reach `dectim` with WID > 1.d-10), but ground-state labels are kept
for completeness and for non-decay contexts.
