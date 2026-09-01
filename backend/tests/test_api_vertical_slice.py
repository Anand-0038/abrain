from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


def test_conversation_transcript_is_ephemeral_and_restart_creates_new_session(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_CORS_ORIGINS="http://testserver",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        started = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        )
        session_id = started.json()["session"]["session_id"]
        turn_response = client.post(
            "/api/conversations/turns",
            json={"owner_id": "owner-a", "session_id": session_id, "text": "I like dark UI"},
        )
        assert turn_response.json()["extraction_status"] == "disabled"
        assert turn_response.json()["candidates"] == []
        assert turn_response.json()["agent_run"]["needs_more_context"] is True
        assert "owner context" in turn_response.json()["agent_response"]
        assert (
            len(
                client.get(
                    f"/api/sessions/{session_id}/turns", params={"owner_id": "owner-a"}
                ).json()
            )
            == 1
        )

        restarted = client.post(
            f"/api/sessions/{session_id}/restart", params={"owner_id": "owner-a"}
        )
        body = restarted.json()
        assert body["terminated"]["session_id"] == session_id
        assert body["fresh"]["session_id"] != session_id
        assert body["transient_turns_after_restart"] == 0
        assert (
            client.get(
                f"/api/sessions/{body['fresh']['session_id']}/turns",
                params={"owner_id": "owner-a"},
            ).json()
            == []
        )


def test_candidate_promotion_writes_real_sibyl_and_emits_events(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_CORS_ORIGINS="http://testserver",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    candidate = {
        "candidate_id": "memory-dark-ui",
        "owner_id": "owner-a",
        "npc_id": "nova",
        "source_session_id": "session-a",
        "source_turn_id": "turn-a",
        "concept": "preference",
        "key": "interface_style",
        "value": "dark interfaces",
        "confidence": 0.96,
    }
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        candidate["npc_id"] = npc["npc_id"]
        candidate["source_session_id"] = session["session_id"]
        response = client.post("/api/memory/candidates/promote", json={"candidate": candidate})
        assert response.status_code == 201
        assert response.json()["record"]["memory_id"] == "memory-dark-ui"
        event_types = [
            event["event_type"]
            for event in client.get(
                "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
            ).json()["events"]
        ]
        assert "memory.write_succeeded" in event_types
        assert "memory.object_materialized" in event_types


def test_uncertain_candidate_requires_confirmation_and_memory_disabled_fails_closed() -> None:
    candidate = {
        "candidate_id": "memory-uncertain",
        "owner_id": "owner-a",
        "npc_id": "nova",
        "source_session_id": "session-a",
        "source_turn_id": "turn-a",
        "concept": "goal",
        "key": "travel_goal",
        "value": "visit Japan",
        "confidence": 0.4,
    }
    with TestClient(
        create_app(Settings(ABRAIN_ENV="test", ABRAIN_MEMORY_ENABLED="false", _env_file=None))
    ) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        candidate["npc_id"] = npc["npc_id"]
        candidate["source_session_id"] = session["session_id"]
        response = client.post("/api/memory/candidates/promote", json={"candidate": candidate})
        assert response.status_code == 409
        confirmed = client.post(
            "/api/memory/candidates/promote",
            json={"candidate": candidate, "confirm": True},
        )
        assert confirmed.status_code == 503
        assert "memory is not enabled" in confirmed.json()["detail"]
