"""Source-verified resonance-family classification for UrQMD 4.0 (Phase 1B2).

Every rule below cites the UrQMD 4.0 source; see docs/resonance_families.md
for the full derivation.

ityp ranges (comres.f:12-60):
    1           nucleon (minnuc=1)
    2-23        N* resonances
    24-40       Delta + Delta*
    41-53       Lambda + Lambda*
    54-62       Sigma + Sigma*
    63-68       Xi + Xi*
    69          Omega
    70          Lambda_c
    1-70        all baryons (minbar..maxbar, comres.f:59-60)
    100-139     all mesons (minmes..maxmes, comres.f:13-16)
    |ityp|>1000 PYTHIA/PDG particles (ityp2pdg.f:174-181)

Strangeness: strit(i) (blockres.f:1038-1062) looks up strres/strmes at |i|
and flips sign for antiparticles (is*iabs(i)/i). strres (blockres.f:192-194):
ityp 1-40 -> 0; 41-53 -> 1; 54-62 -> 1; 63-68 -> 2; 69 -> 3; 70 -> 0.
strmes (blockres.f:197-201): -1 at 106,108,110,113,117,121,125,129;
+1 at 138,139 (D_s); 0 elsewhere. NOTE: strit counts strange quarks, so
physical S = -strit (fchg comment, blockres.f:1117); all comparisons in the
history layer use the raw strit convention consistently.

Ground state vs resonance: a particle is a resonance iff widit(ityp) > 0
(blockres.f:1173-1189; stability test dectim.f:61 "if(WID .GT. 1.d-10)").
Zero-width baryons (widres, blockres.f:56-81): 1, 41, 54, 63, 69, 70.
Zero-width mesons (widmes, blockres.f:104-121): 100, 101, 102, 106, 107 and
the charm/charmonium states 133, 135, 136, 137, 138, 139 (kept stable,
blockres.f:120). PYTHIA particles (|ityp|>1000) are forced stable
(dectim.f:37-46).
"""

from __future__ import annotations

#: strmes table entries with nonzero strangeness (blockres.f:197-201)
_STRANGE_MESONS = frozenset({106, 108, 110, 113, 117, 121, 125, 129})
_CHARM_STRANGE_MESONS = frozenset({138, 139})  # D_s, D_s* (strmes=+1)

_ZERO_WIDTH_BARYONS = frozenset({1, 41, 54, 63, 69, 70})
_ZERO_WIDTH_MESONS = frozenset(
    {100, 101, 102, 106, 107, 133, 135, 136, 137, 138, 139})


def is_baryon(ityp: int) -> bool:
    """comres.f:59-60 (minbar=1, maxbar=70)."""
    return 1 <= abs(ityp) <= 70


def is_meson(ityp: int) -> bool:
    """comres.f:13-16 (minmes=100, maxmes=139)."""
    return 100 <= abs(ityp) <= 139


def is_pythia(ityp: int) -> bool:
    """ityp2pdg.f:174-181 (pdgid = ityp - 1000)."""
    return abs(ityp) > 1000


def strit(ityp: int) -> int:
    """strit(i), blockres.f:1038-1062: table lookup at |ityp|, sign flip
    for antiparticles. Physical strangeness S = -strit (blockres.f:1117)."""
    if ityp == 0:
        raise ValueError("ityp 0 is not a particle")
    a = abs(ityp)
    if 41 <= a <= 62:
        s = 1                       # Lambda*/Sigma* families (strres)
    elif 63 <= a <= 68:
        s = 2                       # Xi family
    elif a == 69:
        s = 3                       # Omega
    elif a in _STRANGE_MESONS:
        s = -1                      # strange mesons (strmes)
    elif a in _CHARM_STRANGE_MESONS:
        s = 1                       # D_s family (strmes, charm sector)
    else:
        s = 0
    return s if ityp > 0 else -s


def is_resonance(ityp: int) -> bool:
    """Resonance iff widit(ityp) > 0 (blockres.f:1173-1189, dectim.f:61)."""
    a = abs(ityp)
    if is_pythia(ityp):
        return False                # forced stable (dectim.f:37-46)
    if is_baryon(ityp):
        return a not in _ZERO_WIDTH_BARYONS
    if is_meson(ityp):
        return a not in _ZERO_WIDTH_MESONS
    raise ValueError(f"unknown ityp {ityp}")


def is_charm(ityp: int) -> bool:
    """Lambda_c (70, comres.f:53-55) and charm mesons 133-139
    (blockres.f:12-13)."""
    a = abs(ityp)
    return a == 70 or 133 <= a <= 139


def multiplet_of(ityp: int) -> str:
    """Named ityp multiplet (comres.f:12-60; names ityp2pdg.f:277-390)."""
    a = abs(ityp)
    if a == 1:
        return "N"
    if 2 <= a <= 23:
        return "N*"
    if 24 <= a <= 40:
        return "Delta"
    if a == 41:
        return "Lambda"
    if 42 <= a <= 53:
        return "Lambda*"
    if a == 54:
        return "Sigma"
    if 55 <= a <= 62:
        return "Sigma*"
    if a == 63:
        return "Xi"
    if 64 <= a <= 68:
        return "Xi*"
    if a == 69:
        return "Omega"
    if a == 70:
        return "Lambda_c"
    if 100 <= a <= 139:
        return f"meson_{a}"
    if a > 1000:
        return f"pythia_{a - 1000}"
    raise ValueError(f"unknown ityp {ityp}")


def family_of(ityp: int, iso3: int = 0) -> str:
    """Coarse resonance family of (ityp, iso3).

    Labels: STRANGE/NONSTRANGE x BARYON/MESON x RESONANCE/GROUND, plus
    CHARM_BARYON / CHARM_MESON and PYTHIA. iso3 is unused for the family
    (multiplet membership is iso3-independent) but kept in the signature
    for a uniform callable interface.
    """
    a = abs(ityp)
    if is_pythia(ityp):
        return "PYTHIA"
    if is_baryon(ityp):
        if is_charm(ityp):
            return "CHARM_BARYON"
        s = "STRANGE" if strit(ityp) != 0 else "NONSTRANGE"
        r = "RESONANCE" if is_resonance(ityp) else "GROUND"
        return f"{s}_BARYON_{r}"
    if is_meson(ityp):
        if is_charm(ityp):
            return "CHARM_MESON"
        s = "STRANGE" if strit(ityp) != 0 else "NONSTRANGE"
        r = "RESONANCE" if is_resonance(ityp) else "GROUND"
        return f"{s}_MESON_{r}"
    raise ValueError(f"unknown ityp {ityp}")
