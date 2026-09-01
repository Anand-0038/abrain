from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_probe(*arguments: str) -> None:
    project_backend = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(project_backend / "src"),
            "ABRAIN_MODEL_PROVIDER": "disabled",
            "ABRAIN_AGENT_PROVIDER": "local",
            "ABRAIN_GEMINI_API_KEY": "",
        }
    )
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("process_boundary_probe.py")), *arguments],
        cwd=project_backend.parent,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_fresh_process_reopens_sibyl_and_changes_action(tmp_path: Path) -> None:
    database = tmp_path / "process-boundary.sqlite3"
    seeded_path = tmp_path / "seeded.json"
    recalled_path = tmp_path / "recalled.json"

    run_probe("seed", str(database), str(seeded_path))
    seeded = json.loads(seeded_path.read_text(encoding="utf-8"))

    run_probe("recall", str(database), str(seeded_path), str(recalled_path))
    recalled = json.loads(recalled_path.read_text(encoding="utf-8"))

    assert recalled["fresh_session_id"] != seeded["first_session_id"]
    assert recalled["transient_turns"] == 0
    assert recalled["recalled_memory_ids"] == [seeded["memory_id"]]
    assert recalled["used_memory_ids"] == [seeded["memory_id"]]
    assert recalled["memory_effect"] == "influenced"
    assert "Hold the request" in recalled["proposed_action"]
    assert "security review" in recalled["proposed_action"]
