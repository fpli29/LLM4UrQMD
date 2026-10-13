"""Deterministic knowledge-builder for the UrQMD Agent.

Scans the UrQMD 4.0 Fortran source for machine-generated facts, compares
them against the human-reviewed snapshot ``urqmd_agent/knowledge/
urqmd_v4.json``, and writes the scan result to
``urqmd_agent/knowledge/urqmd_v4_scan.json``.

This module NEVER writes to ``urqmd_v4.json`` or to anything under
``urqmd_agent/skills/`` — the human-reviewed semantics are only read here.
Pure stdlib (pathlib + re); no shell.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.paths import KNOWLEDGE_SNAPSHOT, REPO_ROOT

SCAN_OUTPUT = KNOWLEDGE_SNAPSHOT.parent / "urqmd_v4_scan.json"

# Source files that must exist for the scan to be meaningful.
EXPECTED_SOURCES = (
    "input.f", "output.f", "scatter.f", "make22.f", "anndec.f",
    "blockres.f", "options.f", "urqmd.f", "coms.f",
)

_CTOPTION_RE = re.compile(r"^\s+CTOption\((\d+)\)\s*=\s*(-?\d+)\s*$",
                          re.IGNORECASE)
_CTOLABEL_RE = re.compile(r"^\s+CTO\w*ng\((\d+)\)\s*=\s*'(.*)'\s*$",
                          re.IGNORECASE)
_NUMCTO_RE = re.compile(r"parameter\s*\(\s*numcto\s*=\s*(\d+)", re.IGNORECASE)
_NUMCTP_RE = re.compile(r"parameter\s*\(\s*numctp\s*=\s*(\d+)", re.IGNORECASE)
# Channel-dispatch computed gotos span continuation lines; the final one in
# make22.f is the crossx channel table.
_GOTO_RE = re.compile(r"goto\s*\(([\d,\s]+)\)\s*io\b",
                      re.IGNORECASE | re.DOTALL)


def _check_sources() -> List[str]:
    warnings = []
    for name in EXPECTED_SOURCES:
        if not (REPO_ROOT / name).is_file():
            warnings.append(f"expected source file missing: {name}")
    return warnings


def _ctoption_defaults(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    """Parse the contiguous CTOption default block in input.f.

    The block runs from the first ``CTOption(1)=...`` assignment to the
    ``CTOption(68)=...`` assignment (the last default with a code label).
    Later conditional overrides elsewhere in the file are excluded by that
    bound.
    """
    lines = path.read_text().splitlines()
    start = end = None
    for idx, line in enumerate(lines):
        m = _CTOPTION_RE.match(line)
        if m and start is None and int(m.group(1)) == 1:
            start = idx
        if m and int(m.group(1)) == 68:
            end = idx
            break
    facts: Dict[str, Any] = {}
    warnings: List[str] = []
    if start is None or end is None:
        warnings.append("could not locate the CTOption default block in input.f")
        return facts, warnings
    for idx in range(start, end + 1):
        line = lines[idx]
        m = _CTOPTION_RE.match(line)
        if m:
            i, value = int(m.group(1)), int(m.group(2))
            facts[f"ctoption_default.{i}"] = {
                "value": value,
                "evidence": f"input.f:{idx + 1}",
            }
            continue
        m = _CTOLABEL_RE.match(line)
        if m:
            i, label = int(m.group(1)), m.group(2).strip()
            facts[f"ctoption_label.{i}"] = {
                "value": label,
                "evidence": f"input.f:{idx + 1}",
            }
    return facts, warnings


def _numcto_numctp(path: Path) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    for idx, line in enumerate(path.read_text().splitlines()):
        m = _NUMCTO_RE.search(line)
        if m:
            facts["numcto"] = {"value": int(m.group(1)),
                               "evidence": f"options.f:{idx + 1}"}
        m = _NUMCTP_RE.search(line)
        if m:
            facts["numctp"] = {"value": int(m.group(1)),
                               "evidence": f"options.f:{idx + 1}"}
    return facts


def _iline_case_count(path: Path) -> Dict[str, Any]:
    """Count entries of the crossx channel-dispatch computed goto in make22.f."""
    text = path.read_text()
    matches = list(_GOTO_RE.finditer(text))
    if not matches:
        return {}
    match = matches[-1]
    count = len([tok for tok in match.group(1).split(",") if tok.strip()])
    line_no = text.count("\n", 0, match.start()) + 1
    return {
        "iline_dispatch_count": {
            "value": count,
            "evidence": f"make22.f:{line_no}",
        }
    }


def _extract() -> Tuple[Dict[str, Any], List[str]]:
    facts: Dict[str, Any] = {}
    warnings = _check_sources()
    input_f = REPO_ROOT / "input.f"
    if input_f.is_file():
        f, w = _ctoption_defaults(input_f)
        facts.update(f)
        warnings.extend(w)
    options_f = REPO_ROOT / "options.f"
    if options_f.is_file():
        facts.update(_numcto_numctp(options_f))
    make22_f = REPO_ROOT / "make22.f"
    if make22_f.is_file():
        facts.update(_iline_case_count(make22_f))
    return facts, warnings


_OPTION_KEY_RE = re.compile(r"^CTOption\((\d+)\)$")


def _snapshot_facts() -> Optional[Dict[str, Any]]:
    """Load the human-reviewed snapshot's fact map, if it exists.

    Two fact sources are recognised:
    * a top-level "facts" mapping keyed by the same fact ids this scanner
      emits, each entry carrying a "value";
    * the "options" catalog: entries keyed ``CTOption(i)`` with a
      ``default`` field map onto the scanner's ``ctoption_default.i``.

    A missing snapshot or missing key marks the fact UNVERIFIED.
    """
    if not KNOWLEDGE_SNAPSHOT.is_file():
        return None
    try:
        data = json.loads(KNOWLEDGE_SNAPSHOT.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    facts: Dict[str, Any] = {}
    raw_facts = data.get("facts")
    if isinstance(raw_facts, dict):
        facts.update(raw_facts)
    options = data.get("options")
    if isinstance(options, dict):
        for key, entry in options.items():
            m = _OPTION_KEY_RE.match(key)
            if m and isinstance(entry, dict) and "default" in entry:
                facts[f"ctoption_default.{int(m.group(1))}"] = {
                    "value": entry["default"]
                }
    return facts if facts else None


def _compare(facts: Dict[str, Any], snapshot: Optional[Dict[str, Any]]) -> None:
    for fact_id, entry in facts.items():
        if snapshot is None:
            entry["verdict"] = "unverified"
            entry["note"] = "knowledge snapshot urqmd_v4.json not available"
            continue
        snap = snapshot.get(fact_id)
        if not isinstance(snap, dict) or "value" not in snap:
            entry["verdict"] = "unverified"
            continue
        if snap["value"] == entry["value"]:
            entry["verdict"] = "verified"
        else:
            entry["verdict"] = "changed"
            entry["snapshot_value"] = snap["value"]


def build_knowledge(json_mode: bool = False) -> int:
    facts, warnings = _extract()
    snapshot = _snapshot_facts()
    if snapshot is None:
        warnings.append(
            "knowledge snapshot urqmd_v4.json missing or unreadable; "
            "all facts marked UNVERIFIED"
        )
    _compare(facts, snapshot)

    document = {
        "meta": {
            "generated": True,
            "date": date.today().isoformat(),
            "generator": "build-knowledge",
        },
        "facts": facts,
    }
    SCAN_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SCAN_OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")

    verdicts: Dict[str, int] = {}
    for entry in facts.values():
        verdicts[entry["verdict"]] = verdicts.get(entry["verdict"], 0) + 1
    summary = (
        f"build-knowledge: extracted {len(facts)} facts "
        f"({', '.join(f'{k}={v}' for k, v in sorted(verdicts.items()))}); "
        f"scan written to {SCAN_OUTPUT.relative_to(REPO_ROOT)}"
    )
    untouched = (
        "human-reviewed semantics NOT modified: urqmd_v4.json and "
        "urqmd_agent/skills/ were left untouched"
    )
    if json_mode:
        print(json.dumps({
            "status": "ok",
            "summary": summary,
            "data": {
                "facts_extracted": len(facts),
                "verdicts": verdicts,
                "scan_output": str(SCAN_OUTPUT),
                "snapshot_present": snapshot is not None,
            },
            "warnings": warnings,
        }, indent=2))
    else:
        print(summary)
        for warning in warnings:
            print(f"WARNING: {warning}")
        print(untouched)
    return 0
