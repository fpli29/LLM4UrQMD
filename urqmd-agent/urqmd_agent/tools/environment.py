"""urqmd.doctor — environment health check (read-only)."""

from __future__ import annotations

import platform
import subprocess

from ..core import paths
from ..core.result import ToolResult
from .registry import READ_ONLY, ToolSpec, register

URQMD_VERSION = "4.0"  # from the source tree / user manual (doc/)


def doctor() -> ToolResult:
    warnings = []
    data = {
        "repo_root": str(paths.REPO_ROOT),
        "urqmd_version": URQMD_VERSION,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }

    try:
        out = subprocess.run(["gfortran", "--version"], capture_output=True,
                             text=True, timeout=30)
        data["gfortran"] = out.stdout.splitlines()[0] if out.stdout else None
        if out.returncode != 0:
            warnings.append(f"gfortran --version exited {out.returncode}")
    except FileNotFoundError:
        data["gfortran"] = None
        warnings.append("gfortran not found on PATH")
    except subprocess.TimeoutExpired:
        data["gfortran"] = None
        warnings.append("gfortran --version timed out")

    exe = paths.EXE
    data["executable"] = str(exe)
    data["executable_present"] = exe.is_file()
    if exe.is_file():
        data["executable_mtime"] = exe.stat().st_mtime
    else:
        warnings.append(f"UrQMD executable missing: {exe}")

    data["tables_dat_present"] = paths.TABLES.is_file()
    if not paths.TABLES.is_file():
        warnings.append(f"tables.dat missing: {paths.TABLES}")

    try:
        out = subprocess.run(
            ["git", "-C", str(paths.REPO_ROOT), "status", "--porcelain",
             "--", "*.f", "*.mk", "Makefile"],
            capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip() or "git status failed")
        modified = [l for l in out.stdout.splitlines() if l.strip()]
        data["source_modified"] = bool(modified)
        data["modified_files"] = modified
        if modified:
            warnings.append(
                f"{len(modified)} Fortran/make source file(s) modified "
                "relative to git")
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        data["source_modified"] = None
        warnings.append(f"could not check git source state: {exc}")

    data["agent_tests"] = "not run by doctor"

    summary = (
        f"UrQMD {URQMD_VERSION} at {paths.REPO_ROOT}; "
        f"executable {'present' if data['executable_present'] else 'MISSING'}; "
        f"tables.dat {'present' if data['tables_dat_present'] else 'MISSING'}; "
        f"gfortran: {data['gfortran'] or 'not found'}; "
        f"source modified: {data['source_modified']}")
    return ToolResult.ok(summary, data, warnings=warnings,
                         provenance={"tool": "urqmd.doctor"})


register(ToolSpec(
    name="urqmd.doctor",
    description=(
        "Environment health check: repo root, UrQMD version, gfortran, "
        "executable and tables.dat presence, platform, Fortran source "
        "modification state via git. Read-only; does NOT run UrQMD or the "
        "test suite."),
    input_schema={"type": "object", "properties": {}, "required": []},
    output_schema={"type": "object", "description": "ToolResult with data "
                   "fields repo_root, urqmd_version, gfortran, "
                   "executable_present, tables_dat_present, source_modified"},
    risk_level=READ_ONLY,
    requires_urqmd=False,
    handler=doctor,
))
