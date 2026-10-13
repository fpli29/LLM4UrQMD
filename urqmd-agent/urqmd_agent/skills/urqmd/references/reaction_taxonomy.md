# Reaction taxonomy (UrQMD 4.0, source-verified)

The process ID in a file15 interaction header is `iline`, set in
scatter.f after channel selection (scatter.f:226, 265; decays set 20 at
scatter.f:173; forced-elastic fallback 13 at scatter.f:262) and written
verbatim at output.f:601. Full per-ID table with line references:
`docs/reaction_taxonomy.md`. Pair classification: MB = collision class 9
("Boson-Baryon"), MM = class 10 ("Boson-Boson"), assigned unconditionally
in `collclass` (scatter.f:1226-1234).

## iline → coarse class

| coarse class | process IDs |
|---|---|
| DECAY | 20 |
| MB | 10 (s-channel resonance formation), 27 with nout=1 |
| MM | 11 |
| STRING | 15, 24, 27 with nout>1, 28 |
| ANNIHILATION | 23 |
| STRX (strangeness exchange) | 57, 58, 59, 60, 61, 62 |
| ELASTIC | 13, 17, 19, 22, 26, 38 |
| BB | 1-8, 14, 35, 39, 30, 31, 32, −2, −3, −5, −6, −7 |
| OTHER | anything else (unexpected; investigate) |

## Notes

- **iline=27 splits at CTParam(60)=3.0 GeV** (make22.f:935-940): above
  the threshold the channel fragments into a string (nout>1, class
  STRING); below, it collapses to a single resonance (nout=1, class MB).
  Always pass `--nout` to `describe-process 27` — the ID alone is
  ambiguous.
- Negative IDs are detailed-balance (inverse) channels handled by
  `crossz`.
- Rare nout=0 records are aborted (Pauli-blocked/rejected) interactions:
  the incoming particles survive unchanged; treat such records as no-ops.
- Box-mode IDs 80/81 and hydro ID 91 never occur in collision-mode
  cascade runs.
