"""urqmd.validate_tools — known-answer checks over the frozen datasets.

Reproduces the published Phase-1B/1B2 headline numbers through the tool
layer. Every check records {name, passed, detail}; the overall status is
'ok' only if ALL checks pass. A check that raises is recorded as failed
with the exception text, and the overall result is then 'error'.
"""

from __future__ import annotations

import json

from ..core import paths
from ..core.errors import ToolError
from ..core.result import ToolResult
from . import genealogy as gen_tools
from . import source as source_tools
from .registry import ANALYSIS, ToolSpec, register

_EXPECTED_FILE = paths.EXPERT_REFERENCE / "expected_values.json"


def _load_expected() -> dict:
    """Known-answer reference values live in expert-reference storage.

    They are quarantined during blind runs; validate_tools then fails
    closed (status=error) instead of exposing the values or passing
    vacuously.
    """
    if not _EXPECTED_FILE.is_file():
        raise ToolError(
            f"known-answer reference values unavailable: {_EXPECTED_FILE} "
            "(quarantined during blind evaluation?)"
        )
    return json.loads(_EXPECTED_FILE.read_text())


def _check_close(actual: float, expected: float, tol: float) -> bool:
    return abs(actual - expected) <= tol


def validate_tools() -> ToolResult:
    checks = []
    expected = _load_expected()  # fails closed when quarantined
    p1b_shares = [tuple(x) for x in expected["p1b_shares"]]
    p1b_alphas = [tuple(x) for x in expected["p1b_alphas"]]
    p1b2_mother = [tuple(x) for x in expected["p1b2_mother"]]
    p1b2_unique = [tuple(x) for x in expected["p1b2_unique"]]

    def record(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed),
                       "detail": str(detail)})

    def guarded(name, fn):
        try:
            fn()
        except Exception as exc:  # failure, never success
            record(name, False, f"{type(exc).__name__}: {exc}")

    # --- 1/2: option semantics from the verified catalog ------------------
    def c1():
        r = source_tools.describe_option("15")
        assert r.status == "ok", r.summary
        chans = " ".join(r.data.get("affected_channels", []))
        cav = " ".join(r.data.get("caveats", [])) + r.data.get(
            "description", "")
        ok = ("MB" in chans and "MM" in chans
              and "PARTIAL" in cav and "MB-only" in cav)
        record("describe_option(15) removes MB+MM, not MB-only", ok,
               f"affected_channels={r.data.get('affected_channels')}")
    guarded("describe_option_15", c1)

    def c2():
        r = source_tools.describe_option("59")
        assert r.status == "ok", r.summary
        chans = " ".join(r.data.get("affected_channels", []))
        ok = "57-62" in chans and "STRX" in chans
        record("describe_option(59) STRX 57-62 scope", ok,
               f"affected_channels={r.data.get('affected_channels')}")
    guarded("describe_option_59", c2)

    # --- 3: particle mapping ------------------------------------------------
    def c3():
        r = source_tools.describe_particle(ityp=41, iso3=0)
        assert r.status == "ok", r.summary
        ok = (r.data["canonical_species"] == "Lambda"
              and r.data["ityp"] == 41 and r.data["iso3"] == 0
              and r.data["physical_strangeness"] == -1)
        record("describe_particle Lambda = (41, 0)", ok, str(r.data.get(
            "canonical_species")))
    guarded("describe_particle_lambda", c3)

    # --- 4: Phase-1B formation provenance headline numbers -----------------
    fp_cache = {}

    def c4():
        for group, species in (("Lambda", "lambda"), ("K", "kaon")):
            r = gen_tools.formation_provenance(dataset="phase1b",
                                               species=species)
            assert r.status == "ok", r.summary
            fp_cache[group] = r.data
        details = []
        ok = True
        for group, cls, exp, tol in p1b_shares:
            got = fp_cache[group]["integrated_shares"][cls]
            good = _check_close(got, exp, tol)
            ok &= good
            details.append(f"{group}/{cls}={got:.4f} (expect {exp}+/-{tol})")
        for group, exp, tol in p1b_alphas:
            got = fp_cache[group]["alphas"]["TOTAL"]
            good = _check_close(got, exp, tol)
            ok &= good
            details.append(f"alpha_{group}={got:.4f} (expect {exp}+/-{tol})")
        record("phase1b integrated shares and alphas reproduced", ok,
               "; ".join(details))
    guarded("phase1b_formation_provenance", c4)

    # --- 5: Phase-1B2 mother-family shares ----------------------------------
    pg_cache = {}

    def c5():
        for group, species in (("Lambda", "lambda"), ("K", "kaon")):
            r = gen_tools.parent_genealogy(dataset="phase1b2",
                                           species=species)
            assert r.status == "ok", r.summary
            pg_cache[group] = r.data
        details = []
        ok = True
        for group, fam, exp, tol in p1b2_mother:
            got = pg_cache[group]["mother_family"]["integrated_shares"][fam]
            good = _check_close(got, exp, tol)
            ok &= good
            details.append(f"{group}/{fam}={got:.4f} (expect {exp}+/-{tol})")
        record("phase1b2 mother-family shares reproduced", ok,
               "; ".join(details))
    guarded("phase1b2_parent_genealogy", c5)

    # --- 6: strangeness-origin UNIQUE_ROOT fractions ------------------------
    def c6():
        r = gen_tools.strangeness_origin(dataset="phase1b2")
        assert r.status == "ok", r.summary
        details = []
        ok = True
        for group, exp, tol in p1b2_unique:
            got = r.data["groups"][group]["outcome_fractions"].get(
                "UNIQUE_ROOT", 0.0)
            good = _check_close(got, exp, tol)
            ok &= good
            details.append(f"{group} UNIQUE={got:.4f} (expect {exp}+/-{tol})")
        record("phase1b2 UNIQUE_ROOT fractions reproduced", ok,
               "; ".join(details))
    guarded("phase1b2_strangeness_origin", c6)

    # --- 7: closure ----------------------------------------------------------
    def c7():
        tol = 1e-6
        details = []
        ok = True
        for cache, label in ((fp_cache, "formation"),
                             (pg_cache, "mother_family")):
            for group, data in cache.items():
                diff = data["closure_max_abs_diff"]
                good = diff < tol
                ok &= good
                details.append(f"{label}/{group} max|diff|={diff:.2e}")
        record("closure checks pass (max |diff| < 1e-6)", ok,
               "; ".join(details))
    guarded("closure", c7)

    n_pass = sum(1 for c in checks if c["passed"])
    n_fail = len(checks) - n_pass
    warnings = [f"FAILED: {c['name']} — {c['detail']}"
                for c in checks if not c["passed"]]
    data = {"checks": checks, "n_passed": n_pass, "n_failed": n_fail,
            "references": {
                "phase1b": "physics_gate/phase1b/results.json",
                "phase1b2": "physics_gate/phase1b2/results.json"},
            "tolerance_note": "share tolerances 0.01-0.03, alpha tolerances "
                              "0.02 (~3x published statistical errors)"}
    summary = (f"validate_tools: {n_pass}/{len(checks)} known-answer checks "
               f"passed")
    if n_fail:
        return ToolResult.error(summary + f"; failures: "
                                + ", ".join(c["name"] for c in checks
                                            if not c["passed"]),
                                data=data, warnings=warnings,
                                provenance={"tool": "urqmd.validate_tools"})
    return ToolResult.ok(summary, data,
                         provenance={"tool": "urqmd.validate_tools"})


register(ToolSpec(
    name="urqmd.validate_tools",
    description=(
        "Run the known-answer test battery: catalog semantics of "
        "CTOption(15)/(59), the Lambda particle mapping, reproduction of "
        "the published Phase-1B integrated formation shares and scaling "
        "exponents, Phase-1B2 mother-family shares and strangeness-root "
        "UNIQUE fractions, and closure checks. Overall status is 'ok' only "
        "if every check passes. Slow (loads the 1100-event CSVs)."),
    input_schema={"type": "object", "properties": {}, "required": []},
    output_schema={"type": "object"},
    risk_level=ANALYSIS,
    handler=validate_tools,
))
