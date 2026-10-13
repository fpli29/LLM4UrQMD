"""Particle species identification from (ityp, iso3, charge).

Only source-verified mappings from urqmd_agent/particles/properties.py are
used. Species are identified by exact ityp/iso3 integers — never by
approximate mass (project rule).
"""

from __future__ import annotations

from . import properties as P


def is_lambda(ityp: int, iso3: int) -> bool:
    """Lambda baryon: ityp=41, iso3=0 (-> PDG 3122)."""
    return ityp == P.ITYP_LAMBDA and iso3 == 0


def is_antilambda(ityp: int, iso3: int) -> bool:
    """Anti-Lambda: ityp=-41, iso3=0 (-> PDG -3122)."""
    return ityp == -P.ITYP_LAMBDA and iso3 == 0


def is_kaon0(ityp: int, iso3: int) -> bool:
    """K0: ityp=106, iso3=-1 (-> PDG 311)."""
    return ityp == P.ITYP_KAON and iso3 == -1


def is_antikaon0(ityp: int, iso3: int) -> bool:
    """anti-K0: ityp=-106, iso3=+1 (-> PDG -311)."""
    return ityp == -P.ITYP_KAON and iso3 == 1


def is_neutral_kaon(ityp: int, iso3: int) -> bool:
    """K0 or anti-K0 (the K_S^0-equivalent base, see docs/particle_mapping.md)."""
    return is_kaon0(ityp, iso3) or is_antikaon0(ityp, iso3)


def is_charged_pion(ityp: int, iso3: int) -> bool:
    """pi+/pi-: ityp=101, |iso3|=2 (-> PDG +/-211)."""
    return ityp == P.ITYP_PION and abs(iso3) == 2


def is_charged_kaon(ityp: int, iso3: int) -> bool:
    """K+ (106,+1 -> 321) or K- (-106,-1 -> -321)."""
    return (ityp == P.ITYP_KAON and iso3 == 1) or \
           (ityp == -P.ITYP_KAON and iso3 == -1)


def is_proton_or_antiproton(ityp: int, iso3: int) -> bool:
    """p (1,+1 -> 2212) or anti-p (-1,-1 -> -2212)."""
    return (ityp == P.ITYP_NUCLEON and iso3 == P.ISO3_PROTON) or \
           (ityp == -P.ITYP_NUCLEON and iso3 == P.ISO3_NEUTRON)
