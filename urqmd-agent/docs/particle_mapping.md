# UrQMD 4.0 particle mapping for Phase 1A (source-verified)

All mappings come from the local source table `ityp2pdg.f`
(`function pdgid(ityp, iso3)`), with the antiparticle convention of
`ityp2pdg.f:183-201` (ityp < 0 → antiparticle; lookup with abs(ityp) and
norm_iso3 = −iso3; PDG id negated).

| species | ityp | iso3 | charge | PDG | source line |
|---|---|---|---|---|---|
| proton | 1 | +1 | +1 | 2212 | ityp2pdg.f:35 |
| neutron | 1 | −1 | 0 | 2112 | ityp2pdg.f:34 |
| anti-proton | −1 | −1 | −1 | −2212 | anti convention |
| Λ | 41 | 0 | 0 | 3122 | ityp2pdg.f:61-62 |
| anti-Λ | −41 | 0 | 0 | −3122 | anti convention |
| π+ | 101 | +2 | +1 | 211 | ityp2pdg.f:96 |
| π0 | 101 | 0 | 0 | 111 | ityp2pdg.f:96 |
| π− | 101 | −2 | −1 | −211 | ityp2pdg.f:96 |
| K+ | 106 | +1 | +1 | 321 | ityp2pdg.f:106 |
| K0 | 106 | −1 | 0 | 311 | ityp2pdg.f:106 |
| K− | −106 | −1 | −1 | −321 | anti convention |
| anti-K0 | −106 | +1 | 0 | −311 | anti convention |

## Neutral kaons and K_S^0

- UrQMD 4.0 has **no K_S^0 (PDG 310) or K_L^0 (PDG 130) transport species**.
  310/130 appear only inside the embedded PYTHIA decay tables
  (`pythia6409.f`), which are not used for the cascade final state.
- Strong production creates the strangeness eigenstates K0 (S=+1) and
  anti-K0 (S=−1). The physical weak eigenstates are equal admixtures
  K_{S,L} = (K0 ± anti-K0)/√2 (up to the small CP-violation parameter ε).
- Primary observable (frozen in `physics_gate/protocol.md`):
  **N_neutralKaon = N(K0) + N(anti-K0)**;
  K_S^0-equivalent = N_neutralKaon / 2.
- The participant-scaling exponent α is invariant under the overall factor
  1/2, so the Phase-1A gate does not depend on this normalization.

## Weak decays

UrQMD simulates strong (resonance) decays only. `dectim.f:89-92`: particles
with zero strong width get an infinite lifetime and are stable in the final
state. Λ, K0 and anti-K0 therefore appear directly in file13; no weak-decay
reconstruction is needed or applied.
