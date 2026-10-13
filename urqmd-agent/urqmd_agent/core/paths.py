"""Canonical paths for the Agent tool layer.

Two roots are distinguished:

* ``PACKAGE_ROOT`` — the directory that contains the ``urqmd_agent``
  package itself (this repository checkout). Package-shipped resources
  (knowledge snapshot, skill files) are anchored here.
* ``URQMD_HOME`` — the UrQMD 4.0 source tree: the directory holding the
  compiled executable and ``tables.dat``. Defaults to ``PACKAGE_ROOT``
  (i.e. the tool layer sits inside the UrQMD repository); override with
  the ``URQMD_HOME`` environment variable when the tool layer is checked
  out separately from UrQMD.

The UrQMD executable defaults to ``urqmd.<machine-arch>`` inside
URQMD_HOME (e.g. ``urqmd.arm64``, ``urqmd.x86_64``); override with the
``URQMD_EXE`` environment variable (absolute path, or relative to
URQMD_HOME).
"""

import os
import platform
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

_urqmd_home = os.environ.get("URQMD_HOME")
URQMD_HOME = Path(_urqmd_home).resolve() if _urqmd_home else PACKAGE_ROOT

# The UrQMD source tree: executable, tables.dat, campaign output areas.
REPO_ROOT = URQMD_HOME

_exe_env = os.environ.get("URQMD_EXE")
if _exe_env:
    EXE = Path(_exe_env)
    if not EXE.is_absolute():
        EXE = URQMD_HOME / EXE
else:
    EXE = URQMD_HOME / f"urqmd.{platform.machine()}"
TABLES = URQMD_HOME / "tables.dat"

PHYSICS_GATE = REPO_ROOT / "physics_gate"
PHASE1B_DATA = PHYSICS_GATE / "phase1b" / "data"
PHASE1B2_DATA = PHYSICS_GATE / "phase1b2" / "data"

AGENT_EVAL = REPO_ROOT / "agent_eval"
BLIND_WORKSPACE = AGENT_EVAL / "blind_workspace"
EXPERT_REFERENCE = AGENT_EVAL / "expert_reference"
TRAJECTORIES = AGENT_EVAL / "trajectories"

# Directories the Agent layer is allowed to write run output into.
# Additional directories can be whitelisted with the environment variable
# URQMD_AGENT_OUTPUT_DIRS (os.pathsep-separated list of directories).
ALLOWED_OUTPUT_DIRS = (
    BLIND_WORKSPACE / "outputs",
    PHYSICS_GATE / "agent_runs",
) + tuple(
    Path(p).expanduser()
    for p in os.environ.get("URQMD_AGENT_OUTPUT_DIRS", "").split(os.pathsep)
    if p.strip()
)

KNOWLEDGE_SNAPSHOT = PACKAGE_ROOT / "urqmd_agent" / "knowledge" / "urqmd_v4.json"
SKILL_DIR = PACKAGE_ROOT / "urqmd_agent" / "skills" / "urqmd"
