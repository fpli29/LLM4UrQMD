# Particle semantics (UrQMD 4.0, source-verified)

Authoritative mapping table: `ityp2pdg.f` (`function pdgid(ityp, iso3)`).
Antiparticle convention (ityp2pdg.f:183-201): ityp < 0 → antiparticle;
look up with abs(ityp) and norm_iso3 = −iso3; PDG id negated.

## Key mappings

| species | ityp | iso3 | charge | PDG | source |
|---|---|---|---|---|---|
| proton | 1 | +1 | +1 | 2212 | ityp2pdg.f:35 |
| neutron | 1 | −1 | 0 | 2112 | ityp2pdg.f:34 |
| Λ | 41 | 0 | 0 | 3122 | ityp2pdg.f:61-62 |
| anti-Λ | −41 | 0 | 0 | −3122 | anti convention |
| π+ / π0 / π− | 101 | +2 / 0 / −2 | +1 / 0 / −1 | 211 / 111 / −211 | ityp2pdg.f:96 |
| K+ | 106 | +1 | +1 | 321 | ityp2pdg.f:106 |
| K0 | 106 | −1 | 0 | 311 | ityp2pdg.f:106 |
| K− | −106 | −1 | −1 | −321 | anti convention |
| anti-K0 | −106 | +1 | 0 | −311 | anti convention |

Neutral kaons: UrQMD 4.0 transports the strangeness eigenstates K0 and
anti-K0 only (no K_S/K_L species in the cascade). The neutral-kaon
observable is N(K0) + N(anti-K0).

Always resolve identities through `urqmd-agent describe-particle`
(`--ityp/--iso3` or `--pdg`); never hand-map from memory.

## Strangeness sign convention

`strit(ityp)` (blockres.f:1038-1060) returns the number of strange quarks
times the particle/antiparticle sign. Because the s quark carries S = −1
(blockres.f:1117, charge formula `fchg = (i3 + b − s + cc)/2`), the
**physical strangeness is S = −strit(ityp)**. Examples: Λ has S = −1,
K0(=d s̄) has S = +1, anti-K0 has S = −1.

## Resonance = width > 0

A species is a resonance iff its (strong) decay width is positive.
Zero-width species get an infinite lifetime (dectim.f:89-92) and appear
stable in file13; UrQMD performs strong decays only, so Λ, K0, anti-K0
appear directly in the final state.

## Resonance families / multiplets

For grouping resonances into multiplets (e.g. by quark content or
isospin family), use the helper `urqmd_agent/particles/resonance_families.py`
rather than ad-hoc lists. See also `docs/resonance_families.md` and
`docs/particle_mapping.md`.
