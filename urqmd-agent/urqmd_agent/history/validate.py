"""Validation and physics-independent conservation diagnostics for file15.

Two layers:

1. Structural validation of a parsed HistoryEvent: ctag behavior, time
   ordering, snapshot bookkeeping. Violations are reported, not silently
   repaired.

2. Conservation diagnostics per interaction, using ONLY quantities directly
   present in file15 (project constraint: no inferred baryon number yet):
     - total electric charge  (exact integer comparison)
     - total strangeness      (exact integer comparison)
     - four-momentum sums     (residual magnitudes reported, not asserted zero,
                               because the file carries finite printed precision
                               e16.8)
   Interactions with nexit=0 (e.g. Pauli-blocked) trivially "violate" the
   naive checks by construction of the output format; they are counted and
   reported separately, never forced to pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .schema import HistoryEvent, Interaction


@dataclass(frozen=True)
class MomentumResidual:
    ctag: int
    process_id: int
    nin: int
    nout: int
    dE: float
    dpx: float
    dpy: float
    dpz: float

    @property
    def max_abs(self) -> float:
        return max(abs(self.dE), abs(self.dpx), abs(self.dpy), abs(self.dpz))


@dataclass
class ConservationReport:
    n_interactions: int = 0
    n_checked: int = 0                # interactions with nout > 0
    n_blocked_or_empty: int = 0       # nout == 0 records (e.g. Pauli-blocked)
    charge_mismatches: List[Tuple[int, int, int]] = field(default_factory=list)
    strangeness_mismatches: List[Tuple[int, int, int]] = field(default_factory=list)
    momentum_residuals: List[MomentumResidual] = field(default_factory=list)

    @property
    def max_dE(self) -> float:
        return max((abs(r.dE) for r in self.momentum_residuals), default=0.0)

    @property
    def max_dpx(self) -> float:
        return max((abs(r.dpx) for r in self.momentum_residuals), default=0.0)

    @property
    def max_dpy(self) -> float:
        return max((abs(r.dpy) for r in self.momentum_residuals), default=0.0)

    @property
    def max_dpz(self) -> float:
        return max((abs(r.dpz) for r in self.momentum_residuals), default=0.0)

    @property
    def max_residual(self) -> float:
        return max((r.max_abs for r in self.momentum_residuals), default=0.0)


@dataclass
class StructuralReport:
    n_interactions: int
    n_particle_rows: int
    ctag_sequence: List[int]
    ctag_strictly_increasing: bool
    ctag_first: int
    ctag_last: int
    time_first: float
    time_last: float
    time_non_decreasing: bool
    time_violations: List[Tuple[int, float, float]]  # (ctag, t_prev, t)
    n_decays: int
    n_collisions: int
    n_blocked: int                    # nout == 0
    n_identity_preserving: int
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_structure(event: HistoryEvent) -> StructuralReport:
    """Check ctag bookkeeping and interaction time ordering."""
    ctags = [i.ctag for i in event.interactions]
    times = [i.time for i in event.interactions]

    errors: List[str] = []
    seen = set()
    for c in ctags:
        if c in seen:
            errors.append(f"duplicate ctag {c}")
        seen.add(c)

    time_violations = [
        (ctags[k + 1], times[k], times[k + 1])
        for k in range(len(times) - 1)
        if times[k + 1] < times[k] - 1e-9
    ]

    return StructuralReport(
        n_interactions=len(event.interactions),
        n_particle_rows=event.n_particle_rows,
        ctag_sequence=ctags,
        ctag_strictly_increasing=all(
            ctags[k + 1] > ctags[k] for k in range(len(ctags) - 1)),
        ctag_first=ctags[0],
        ctag_last=ctags[-1],
        time_first=times[0],
        time_last=times[-1],
        time_non_decreasing=not time_violations,
        time_violations=time_violations,
        n_decays=sum(1 for i in event.interactions if i.is_decay),
        n_collisions=sum(1 for i in event.interactions if not i.is_decay),
        n_blocked=sum(1 for i in event.interactions if i.nout == 0),
        n_identity_preserving=sum(
            1 for i in event.interactions if i.is_identity_preserving),
        errors=errors,
    )


def conservation_diagnostics(event: HistoryEvent) -> ConservationReport:
    """Charge / strangeness / four-momentum checks per interaction.

    Only exact-integer mismatches (charge, strangeness) are hard anomalies.
    Momentum residuals are distributions over finite-precision printout.
    Records with nout==0 (Pauli-blocked: incoming written, no outgoing) are
    excluded from the comparisons and counted separately.
    """
    rep = ConservationReport(n_interactions=len(event.interactions))
    for inter in event.interactions:
        if inter.nout == 0:
            rep.n_blocked_or_empty += 1
            continue
        rep.n_checked += 1

        q_in = sum(s.charge for s in inter.incoming)
        q_out = sum(s.charge for s in inter.outgoing)
        if q_in != q_out:
            rep.charge_mismatches.append((inter.ctag, q_in, q_out))

        s_in = sum(s.strangeness for s in inter.incoming)
        s_out = sum(s.strangeness for s in inter.outgoing)
        if s_in != s_out:
            rep.strangeness_mismatches.append((inter.ctag, s_in, s_out))

        pin = [sum(s.four_momentum()[k] for s in inter.incoming) for k in range(4)]
        pout = [sum(s.four_momentum()[k] for s in inter.outgoing) for k in range(4)]
        rep.momentum_residuals.append(MomentumResidual(
            ctag=inter.ctag, process_id=inter.process_id,
            nin=inter.nin, nout=inter.nout,
            dE=pout[0] - pin[0], dpx=pout[1] - pin[1],
            dpy=pout[2] - pin[2], dpz=pout[3] - pin[3]))
    return rep
