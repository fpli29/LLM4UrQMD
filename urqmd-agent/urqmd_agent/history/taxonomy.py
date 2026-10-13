"""Source-derived reaction taxonomy for UrQMD 4.0 file15 process IDs.

Every entry below was verified against the local source (see
docs/reaction_taxonomy.md for the full citation table). The process ID in
file15 is the variable `iline` (common /inewpart/, newpart.f:46,58; written
at output.f:601; set at scatter.f:226,265 and scatter.f:173 for decays).

Coarse classes (conservative, source-supported):

    DECAY       process 20: 1->n decay (scatter.f:173; make22.f:705-749)
    STRING      string excitation/fragmentation exit channels:
                15 (XX->2 strings, make22.f:345-679), 24 (bbar diffractive
                string, ->label 15), 27 with nout>1 (MB->1 string,
                make22.f:868-1014), 28 (MB->2 strings, ->label 15)
    ANNIHILATION
                23: bbar-b annihilation -> 2 strings (make22.f:752-814)
    BB          baryon-baryon / baryon-resonance non-string channels:
                1-8 (NN->N/Delta resonance production, make22.f:4313 label 1),
                14 (AQM inelastic 2->2 resonance excitation,
                make22.f:4488-4514), 35 (N-Delta inelastic excitation),
                30/31/32 (parameterized detailed-balance absorption,
                make22.f:4935-4997), -2/-3/-5/-6/-7 (detailed-balance
                B*B* -> NN via crossz, make22.f:4262,4355),
                39 (bbar-b inelastic, -> label 14)
    MB          meson-baryon non-string resonance formation:
                10 (MB->B' s-channel, make22.f:4395-4404),
                27 with nout==1 (anndec resonance fallback, make22.f:942)
    MM          11: meson-meson -> M' s-channel resonance (make22.f:4406-4409)
    STRX        strangeness exchange (require CTOption(59)>=1, default 1,
                input.f:383):
                57 (K N -> Y pi, make22.f:6132-6138),
                58 (pi Y -> K N, make22.f:6142-6149),
                59 (K Y -> Xi pi, make22.f:6151-6157),
                60 (Xi pi -> Y K, make22.f:6159-6165),
                61 (Xi K -> Omega pi, make22.f:6167-6173),
                62 (Omega pi -> Xi K, inverse of 61)
    ELASTIC     13 (generic AQM elastic + forced-elastic fallback,
                make22.f:4460-4486, scatter.f:262), 17 (pn elastic),
                19 (pp/nn elastic), 22 (bbar-b elastic), 26 (MB elastic),
                38 (MM elastic, constant 5 mb)
    OTHER       anything else (none expected in cascade Au+Au at 7.7 GeV
                beyond the verified list; 80/81 box-wall and 91 hydro never
                occur in collision-mode cascade runs)

`is_elastic` is used only for post-formation transport bookkeeping; species
changes are always detected directly from (ityp, iso3) comparisons, never
inferred from the class.
"""

from __future__ import annotations

from typing import Dict, Tuple

#: process_id -> (coarse_class, is_elastic)
PROCESS_INFO: Dict[int, Tuple[str, bool]] = {
    # decays
    20: ("DECAY", False),
    # string exit channels
    15: ("STRING", False),
    24: ("STRING", False),
    28: ("STRING", False),
    # bbar-b annihilation to strings
    23: ("ANNIHILATION", False),
    # baryon-baryon / resonance non-string
    1: ("BB", False), 2: ("BB", False), 3: ("BB", False), 4: ("BB", False),
    5: ("BB", False), 6: ("BB", False), 7: ("BB", False), 8: ("BB", False),
    14: ("BB", False), 35: ("BB", False), 39: ("BB", False),
    30: ("BB", False), 31: ("BB", False), 32: ("BB", False),
    -2: ("BB", False), -3: ("BB", False), -5: ("BB", False),
    -6: ("BB", False), -7: ("BB", False),
    # meson-baryon resonance formation (10; 27 with nout==1 handled below)
    10: ("MB", False),
    # meson-meson resonance formation
    11: ("MM", False),
    # strangeness exchange
    57: ("STRX", False), 58: ("STRX", False), 59: ("STRX", False),
    60: ("STRX", False), 61: ("STRX", False), 62: ("STRX", False),
    # elastic
    13: ("ELASTIC", True), 17: ("ELASTIC", True), 19: ("ELASTIC", True),
    22: ("ELASTIC", True), 26: ("ELASTIC", True), 38: ("ELASTIC", True),
}

#: process 27 is classed by its outgoing multiplicity (source-verified:
#: nout==1 -> anndec resonance fallback; nout>1 -> string)
_SPLIT_BY_NOUT = {27: ("MB", "STRING")}


def classify(process_id: int, nout: int) -> Tuple[str, bool]:
    """Return (coarse_class, is_elastic) for a file15 process ID."""
    if process_id in _SPLIT_BY_NOUT:
        mb, string = _SPLIT_BY_NOUT[process_id]
        return (mb, False) if nout == 1 else (string, False)
    if process_id in PROCESS_INFO:
        return PROCESS_INFO[process_id]
    return ("OTHER", False)


def coarse_class(process_id: int, nout: int) -> str:
    return classify(process_id, nout)[0]
