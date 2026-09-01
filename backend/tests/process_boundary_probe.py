"""Helper executed in separate OS processes by the continuity integration test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


def settings(db_path: Path) -> Settings:
    return Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(db_path),
        ABRAIN_MODEL_PROVIDER="disabled",
        ABRAIN_AGENT_PROVIDER="local",
        ABRAIN_GEMINI_API_KEY="",
        _env_file=None,
    )


def seed(db_path: Path, result_path: Path) -> None:
    with TestClient(create_app(settings(db_path))) as client:
        npc = client.post(
            "/api/npcs",
            json={"owner_id": "owner-process", "name": "Continuity Agent"},
        ).json()["npc"]
        session = client.post(
            "/api/sessions",
            json={"owner_id": "owner-process", "npc_id": npc["npc_id"]},
        ).json()["session"]
        candidate = {
            "candidate_id": "memory-release-constraint",
            "owner_id": "owner-process",
            "npc_id": npc["npc_id"],
            "source_session_id": session["session_id"],
            "source_turn_id": "turn-release-constraint",
            "concept": "constraint",
            "key": "release_gate",
            "value": "staging security review must be approved before shipping",
            "confidence": 1.0,
        }
        promoted = client.post(
            "/api/memory/candidates/promote",
            json={"candidate": candidate, "confirm": True},
        )
        promoted.raise_for_status()
        result_path.write_text(
            json.dumps(
                {
                    "npc_id": npc["npc_id"],
                    "first_session_id": session["session_id"],
                    "memory_id": promoted.json()["record"]["memory_id"],
                }
            ),
            encoding="utf-8",
        )


def recall(db_path: Path, seed_path: Path, result_path: Path) -> None:
    seeded = json.loads(seed_path.read_text(encoding="utf-8"))
    with TestClient(create_app(settings(db_path))) as client:
        listed = client.get("/api/npcs", params={"owner_id": "owner-process"})
        listed.raise_for_status()
        assert [npc["npc_id"] for npc in listed.json()["npcs"]] == [seeded["npc_id"]]

        session_response = client.post(
            "/api/sessions",
            json={"owner_id": "owner-process", "npc_id": seeded["npc_id"]},
        )
        session_response.raise_for_status()
        session = session_response.json()["session"]
        turns = client.get(
            f"/api/sessions/{session['session_id']}/turns",
            params={"owner_id": "owner-process"},
        )
        turns.raise_for_status()
        assert turns.json() == []

        continuity = client.post(
            f"/api/sessions/{session['session_id']}/continuity",
            json={
                "owner_id": "owner-process",
                "npc_id": seeded["npc_id"],
                "query": "Continue the release and decide whether it is safe to ship.",
            },
        )
        continuity.raise_for_status()
        body = continuity.json()
        result_path.write_text(
            json.dumps(
                {
                    "fresh_session_id": session["session_id"],
                    "transient_turns": len(turns.json()),
                    "recalled_memory_ids": body["recalled_memory_ids"],
                    "used_memory_ids": body["agent_run"]["used_memory_ids"],
                    "memory_effect": body["agent_run"]["memory_effect"],
                    "proposed_action": body["agent_run"]["proposed_action"],
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "seed":
        seed(Path(sys.argv[2]), Path(sys.argv[3]))
    elif mode == "recall":
        recall(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        raise SystemExit(f"unknown mode: {mode}")
