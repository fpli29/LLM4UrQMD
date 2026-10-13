"""Verified UrQMD 4.0 particle species constants.

All mappings are taken from the local source table `ityp2pdg.f`
(function `pdgid(ityp, iso3)`), NOT from memory:

- ityp2pdg.f:33-36   ityp=1:   iso3=-1 -> 2112 (n),      iso3=+1 -> 2212 (p)
- ityp2pdg.f:95-96   ityp=101: iso3=-2 -> -211 (pi-),    iso3=0 -> 111 (pi0),
                                iso3=+2 -> 211 (pi+)
- ityp2pdg.f:105-106 ityp=106: iso3=-1 -> 311 (K0),      iso3=+1 -> 321 (K+)
- ityp2pdg.f:61-62   ityp=41:  iso3=0  -> 3122 (Lambda)
- Antiparticle convention (ityp2pdg.f:183-201): ityp < 0 selects the
  antiparticle: abs(ityp) is looked up with norm_iso3 = -iso3 and the PDG id
  is negated. Hence:
      ityp=-1   iso3=-1 -> -2212 (anti-p)      [norm_iso3=+1 -> 2212, negated]
      ityp=-41  iso3=0  -> -3122 (anti-Lambda)
      ityp=-106 iso3=+1 -> -311 (anti-K0)      [norm_iso3=-1 -> 311, negated]
      ityp=-106 iso3=-1 -> -321 (K-)

There is NO explicit K_S^0 (PDG 310) or K_L^0 (PDG 130) transport species in
UrQMD 4.0: 310/130 appear only inside the embedded PYTHIA decay tables
(pythia6409.f) which are not part of the cascade final state.

Weak decays are not simulated: dectim.f:89-92 assigns infinite lifetime to
particles with zero strong-decay width, so Lambda and K0/anti-K0 are stable
in the final state.
"""

# --- baryons -------------------------------------------------------------
ITYP_NUCLEON = 1        # n (iso3=-1) / p (iso3=+1)
ITYP_LAMBDA = 41        # Lambda (iso3=0)
ISO3_PROTON = 1
ISO3_NEUTRON = -1

# --- mesons --------------------------------------------------------------
ITYP_PION = 101         # iso3 in {-2, 0, +2}
ITYP_KAON = 106         # iso3=-1 -> K0, iso3=+1 -> K+

# PDG ids (for documentation/assertions only)
PDG_PROTON = 2212
PDG_PION_PLUS = 211
PDG_KAON_PLUS = 321
PDG_KAON_ZERO = 311
PDG_LAMBDA = 3122
