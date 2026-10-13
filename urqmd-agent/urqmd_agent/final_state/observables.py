"""Event-level observables from parsed file13 final states.

All species use the source-verified ityp/iso3 mapping
(urqmd_agent/particles). Definitions frozen in physics_gate/protocol.md:

- acceptance: |y_cm| < 0.5 (output frame is NN c.m., betann==0 asserted)
- N_ch centrality estimator: #(pi±) + #(K±) + #(p,anti-p), full phase space
- N_part: Glauber participant count from the UrQMD event header
"""

from __future__ import annotations

from dataclasses import dataclass

from ..particles import identify as pid
from .schema import FinalStateEvent

#: frozen primary acceptance
Y_CM_MAX = 0.5


@dataclass(frozen=True)
class EventObservables:
    event: int
    ranseed: int
    sqrts: float
    bimp: float
    n_part: float          # Glauber participants (from header)
    n_ch: int              # charged pi/K/p multiplicity, full phase space
    n_lambda: int          # |y_cm| < 0.5
    n_antilambda: int      # |y_cm| < 0.5 (sanity quantity)
    n_kaon0: int           # |y_cm| < 0.5
    n_antikaon0: int       # |y_cm| < 0.5
    npart_final: int
    itotcoll: int

    @property
    def n_neutral_kaon(self) -> int:
        return self.n_kaon0 + self.n_antikaon0

    @property
    def n_ks0_equiv(self) -> float:
        """K_S^0-equivalent = (N(K0)+N(anti-K0))/2; see docs/particle_mapping.md.
        (alpha fits are invariant under this factor.)"""
        return 0.5 * self.n_neutral_kaon


def event_observables(ev: FinalStateEvent,
                      y_max: float = Y_CM_MAX) -> EventObservables:
    n_lambda = n_anti = n_k0 = n_k0bar = n_ch = 0
    for p in ev.particles:
        if pid.is_charged_pion(p.ityp, p.iso3) or \
           pid.is_charged_kaon(p.ityp, p.iso3) or \
           pid.is_proton_or_antiproton(p.ityp, p.iso3):
            n_ch += 1
        if abs(p.rapidity_cm()) >= y_max:
            continue
        if pid.is_lambda(p.ityp, p.iso3):
            n_lambda += 1
        elif pid.is_antilambda(p.ityp, p.iso3):
            n_anti += 1
        elif pid.is_kaon0(p.ityp, p.iso3):
            n_k0 += 1
        elif pid.is_antikaon0(p.ityp, p.iso3):
            n_k0bar += 1
    h = ev.header
    return EventObservables(
        event=h.event, ranseed=h.ranseed, sqrts=h.sqrts, bimp=h.bimp,
        n_part=h.num_part, n_ch=n_ch,
        n_lambda=n_lambda, n_antilambda=n_anti,
        n_kaon0=n_k0, n_antikaon0=n_k0bar,
        npart_final=h.npart, itotcoll=h.itotcoll)


CSV_COLUMNS = (
    "event_id", "seed", "sqrt_sNN_actual", "bimp_fm", "n_part_glauber",
    "n_ch", "n_lambda_y05", "n_antilambda_y05", "n_kaon0_y05",
    "n_antikaon0_y05", "n_neutral_kaon_y05", "n_ks0_equiv_y05",
    "npart_final", "itotcoll",
)


def to_csv_row(obs: EventObservables) -> str:
    return ",".join(str(x) for x in (
        obs.event, obs.ranseed, f"{obs.sqrts:.4f}", f"{obs.bimp:.4f}",
        f"{obs.n_part:.1f}", obs.n_ch, obs.n_lambda, obs.n_antilambda,
        obs.n_kaon0, obs.n_antikaon0, obs.n_neutral_kaon,
        f"{obs.n_ks0_equiv:.1f}", obs.npart_final, obs.itotcoll))
