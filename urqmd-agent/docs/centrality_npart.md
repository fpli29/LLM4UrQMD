# Centrality and N_part definitions (Phase 1A, frozen in physics_gate/protocol.md)

## Centrality estimator (primary)

Per-event charged-hadron multiplicity

    N_ch = #(pi+) + #(pi-) + #(K+) + #(K-) + #(p) + #(anti-p)

over full phase space (no acceptance cut), with species identified by the
source-verified ityp/iso3 mapping (docs/particle_mapping.md):

- pi±:  ityp=101, |iso3|=2
- K±:   (ityp=106, iso3=+1) / (ityp=-106, iso3=-1)
- p/p̄:  (ityp=1, iso3=+1) / (ityp=-1, iso3=-1)

Centrality bins are percentiles of the N_ch distribution *within each energy
sample* (0-10% = highest N_ch). Impact parameter is not used for the primary
classification. This mirrors the published UrQMD comparison, which determines
centrality from percentiles of charged pi/K/p multiplicity.

Bins: 0-10, 10-20, 20-30, 30-40, 40-60, 60-80 %.

## N_part (primary)

Taken directly from the UrQMD event header:
`Participants_Glauber (Nuc_part,prot_part,neut_part):` (output.f:264-266,
format 1010).

Source verification — `init.f`, subroutine `init_eccentricity`
(init.f:644-717): after the nuclei are initialized and displaced by the
sampled impact parameter, every projectile nucleon i is compared with every
target nucleon j in the transverse plane; pairs with
sqrt((x_i-x_j)^2+(y_i-y_j)^2) <= d0 = 1.13 fm (= sqrt(sigma_el/pi),
init.f:657) flag both nucleons as participants. `num_part` counts all flagged
nucleons. This is UrQMD's own Glauber-like participant count, computed
deterministically at initialization and available in every event header, so
no history-derived reconstruction is needed for the primary analysis.

(The alternative definition — initial nucleons with at least one physical
interaction, derivable from file15 UIDs — remains a possible secondary
cross-check, not used for the primary result.)

## Minimum-bias sampling

Verified in `init.f:425-434` (note: the `CTOStrng(5)` label is misleading,
the code semantics are inverted relative to the naive reading):

- `CTOption(5)=0` (default): bimp = bdist, FIXED, no cap.
- `CTOption(5)=1`: bimp = sqrt(bmin^2 + ranf*(bdist^2-bmin^2)), uniform in
  b^2 (correct minimum-bias), with bdist capped at
  nucrad(Ap)+nucrad(At)+2*CTParam(30) (init.f:428-429; CTParam(30)=1.5 fm,
  input.f:157; nucrad from cascinit.f:231,
  r_0*(0.5*(A+(A^(1/3)-1)^3))^(1/3) ≈ 6.2 fm for Au → cap ≈ 15.4 fm).

We therefore run with `imp 40.` + `cto 5 1` (the source caps bdist at the
geometry limit). Equivalently `imp -40.` sets CTOption(5)=1 internally
(input.f:727-731). The sampled bimp of every event is recorded and the
b^2-uniformity is verified on the dry-run sample.
