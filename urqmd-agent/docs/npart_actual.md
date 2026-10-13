# N_part^actual — history-derived participant count (Phase 1B, secondary)

## Definition

N_part^actual = number of distinct initial projectile/target nucleons that
appear as INCOMING in at least one two-body collision record (nin=2) in
file15.

## Source assumptions (verified)

- Initial nucleons are assigned UIDs 1..Ap+At in order at initialization
  (init.f:543-544, `uid(npart)=uid_cnt`), and their `origin` tag is 0
  (init.f:184). Verified on audit data: all UIDs <= 394 appearing in
  histories have ityp=1 (nucleon) and origin=0 at first appearance; all
  created particles have UID >= 395.
- Created particles carry `origin = iline` of the creating process
  (scatter.f:1026-1038), so origin=0 uniquely tags initial nucleons.
- Decays (process 20) are one-body and cannot involve an initial nucleon as
  the decaying particle (nucleons are stable in transport; dectim.f:89-92
  assigns zero width to stable states).
- Pauli-blocked/aborted records (nout=0, scatter.f:977) are NOT physical
  interactions and are excluded.
- Identity-preserving elastic collisions DO count: they are physical
  transport interactions.
- Box/wall markers (80/81) never occur in collision-mode runs.

## Cross-check expectations

N_part^actual >= N_part^Glauber is typical: the Glauber count uses a fixed
geometric transverse-distance criterion d0 = 1.13 fm (init.f:657), while
actual transport collisions happen whenever the collision algorithm finds
an overlapping pair (which includes density-dependent cross sections and
stochastic wounding). Example (7.7 GeV audit, bimp=5.71 fm):
N_part^Glauber = 230, N_part^actual = 325. A peripheral zero-interaction
event has N_part^actual = 0 by construction.

## Role in the analysis

SECONDARY diagnostic only. The primary scaling variable remains
<N_part^Glauber>, to stay consistent with the reproduced published effect
and the Phase-1A/1A-R analysis chain.
