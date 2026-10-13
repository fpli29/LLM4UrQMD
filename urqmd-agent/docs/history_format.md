# UrQMD 4.0 file15 collision-history format (verified)

Ground truth: UrQMD 4.0 source code of this repository, verified in Phase 0
(`phase0/source_map.md`). Where intuition/manual and source disagree, the
source is followed.

## Enabling the output

- Unit 15 is opened **only** if the environment variable `ftn15` is set
  (`input.f:427,469-471`).
- The input keyword `f15` **suppresses** unit-15 output (`input.f:801-803` sets
  `bf15=.true.`; `output.f:154` and `output.f:596` skip all writes when set).
  To enable history output: export `ftn15` and do **not** put `f15` in the
  input file.
- With `cto 56 1` (CTOption(56)=1, default 0) the first field of each particle
  record is the unique lifetime particle ID `uid` instead of the particle slot
  index (`input.f:377-378`, `output.f:606-624`). All UrQMD-Agent parsing
  assumes CTOption(56)=1.

## Record types

### Event header — one per event (first record)

Fortran format 502 `(i8,i8,i4,i7,f8.3,4e12.4)` (output.f:139), written at
output.f:246-248 (abbreviated default because CTOption(58)=0):

| # | field | meaning |
|---|-------|---------|
| 1 | -1 | event-header marker |
| 2 | event | event number |
| 3 | Ap | projectile mass number |
| 4 | At | target mass number |
| 5 | bimp | impact parameter [fm] |
| 6 | ecm | sqrt(s_NN) [GeV] |
| 7 | sigmatot | projectile-target total cross section [mb] (observed 0.0 for A+A) |
| 8 | ebeam | beam energy per nucleon [GeV/u] |
| 9 | pbeam | beam momentum per nucleon [GeV/c] |

### Interaction header — one per collision/decay

Same format 502, written at output.f:601-602:

| # | field | meaning |
|---|-------|---------|
| 1 | nin | number of incoming particles (1 = decay, 2 = collision) |
| 2 | nexit | number of outgoing particles (0 possible: Pauli-blocked) |
| 3 | iline | process/channel ID (from SigmaLn; 20 = decay, scatter.f:173) |
| 4 | ctag | collision tag: sequential interaction counter |
| 5 | acttime | interaction time [fm/c] |
| 6 | sqrts | sqrt(s) of the collision [GeV] |
| 7 | sigtot | total cross section [mb] (0 for decays) |
| 8 | sigpart | selected-channel (partial) cross section [mb] (0 for decays) |
| 9 | cdens | local baryon density at the collision point |

### Particle record — nin incoming rows, then nexit outgoing rows

Format 501 `(i5,9e16.8,i11,2i3,i9,i5,i3,i15)` (output.f:122), written at
output.f:603-629:

| # | field | meaning |
|---|-------|---------|
| 1 | uid | unique lifetime particle ID (CTOption(56)=1) |
| 2-5 | r0, rx, ry, rz | time/position [fm] |
| 6-9 | p0, px, py, pz | four-momentum [GeV] |
| 10 | m | mass [GeV] |
| 11 | ityp | UrQMD particle type ID (raw integer) |
| 12 | iso3 | 2 * isospin 3rd component |
| 13 | charge | electric charge [e] |
| 14 | lstcoll | last collision number |
| 15 | ncoll | collision count of this particle |
| 16 | strangeness | strit(ityp) |
| 17 | origin | origin tag |

Note: no parent/child pointers are written. Ancestry must be reconstructed
from uid matching across interaction records (see `docs/reaction_graph.md`).

## Source quirks (documented, not "fixed")

- The write lists at output.f:247 and output.f:601-602 contain an empty list
  item (`, ,`); the emitted records match format 502 exactly (9 values ↔ 9
  descriptors).
- Fixed-width fields: parse by column, not by whitespace. Fortran may emit
  `D` exponents; the parser accepts both `E` and `D`.
- Interaction times are monotonically non-decreasing within an event in all
  events validated so far (collisions are processed in time order via the
  collision table).
