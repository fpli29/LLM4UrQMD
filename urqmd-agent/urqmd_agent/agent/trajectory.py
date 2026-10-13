"""Scientific trajectory logging (JSONL).

Logs tool calls and their visible inputs/outputs — never hidden
chain-of-thought. One file per session:
agent_eval/trajectories/<session>.jsonl
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..core import paths


class TrajectoryLogger:
    def __init__(self, session_id: str, directory: Optional[Path] = None):
        self.session_id = session_id
        self.directory = Path(directory) if directory else paths.TRAJECTORIES
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"{session_id}.jsonl"

    def log_call(
        self,
        tool: str,
        arguments: Dict[str, Any],
        result_status: str,
        result_summary: str,
        warnings=None,
        artifacts=None,
        run_id: Optional[str] = None,
        agent_note: Optional[str] = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "tool": tool,
            "arguments": arguments,
            "result_status": result_status,
            "result_summary": result_summary,
            "warnings": list(warnings or []),
            "artifacts": list(artifacts or []),
            "run_id": run_id,
            "agent_note": agent_note,
        }
        with self.path.open("a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
