"""Leakage scanner for the agent_eval blind workspace.

Recursively scans every file under ``agent_eval/blind_workspace`` —
filenames AND text content — for banned patterns that would leak the
expert-reference mechanism into the blind evaluation.

The banned-pattern list itself contains mechanism hints, so it is stored
outside the tool layer in ``agent_eval/expert_reference/leakage_patterns.json``
(quarantined during blind runs; the scanner then refuses to run rather than
returning a meaningless PASS).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import paths
from ..core.errors import ToolError

# Files excluded from content scanning entirely: the scanner's own report
# necessarily quotes the banned pattern list.
EXCLUDED_FILES = {"LEAKAGE_CHECK.md"}

_PATTERNS_FILE = paths.EXPERT_REFERENCE / "leakage_patterns.json"


def _load_patterns():
    """Load banned patterns/exemptions from expert-reference storage.

    The pattern list itself contains mechanism hints, so it is kept outside
    the tool layer and is quarantined during blind runs. If it is missing
    the scanner refuses to run rather than silently scanning with an empty
    list (which would produce a meaningless PASS).
    """
    if not _PATTERNS_FILE.is_file():
        raise ToolError(
            f"leakage pattern list unavailable: {_PATTERNS_FILE} "
            "(quarantined during blind evaluation?)"
        )
    payload = json.loads(_PATTERNS_FILE.read_text())
    return (tuple(payload["banned_patterns"]),
            {k: set(v) for k, v in payload["content_exemptions"].items()})


def scan_blind_workspace(root: Optional[Path] = None) -> Dict[str, Any]:
    root = Path(root) if root is not None else paths.BLIND_WORKSPACE
    hits: List[Dict[str, Any]] = []
    if not root.is_dir():
        return {"passed": False, "hits": hits,
                "error": f"blind workspace not found: {root}"}
    banned, content_exemptions = _load_patterns()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        name_lower = path.name.lower()
        for pattern in banned:
            if pattern.lower() in name_lower:
                hits.append({"path": rel, "pattern": pattern,
                             "where": "filename", "line": None})
        if rel in EXCLUDED_FILES:
            continue
        try:
            text = path.read_text(errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        exemptions = {p.lower() for p in content_exemptions.get(rel, set())}
        for lineno, line in enumerate(text.splitlines(), start=1):
            line_lower = line.lower()
            for pattern in banned:
                if pattern.lower() in exemptions:
                    continue
                if pattern.lower() in line_lower:
                    hits.append({"path": rel, "pattern": pattern,
                                 "where": "content", "line": lineno})
    return {"passed": not hits, "hits": hits}
