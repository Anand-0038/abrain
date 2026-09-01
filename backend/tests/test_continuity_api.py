from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app
from abrain_api.memory import MemoryAdapterError
from abrain_api.modules.agent_runner import AgentRunResult


class NonUsingRunner:
    async def run(self, request: object) -> AgentRunResult:
        return AgentRunResult(
            response="I can answer generally without applying persistent context.",
            plan=["Answer without using memory."],
            proposed_action="answer_without_memory",
            memory_effect="none",
            needs_more_context=False,
        )


def _candidate(npc_id: str, source_session_id: str) -> dict[str, object]:
    return {
        "candidate_id": "m-dark",
        "owner_id": "owner-a",
        "npc_id": npc_id,
        "source_session_id": source_session_id,
        "source_turn_id": "turn-1",
        "concept": "preference",
        "key": "interface_style",
        "value": "dark interfaces",
        "confidence": 0.98,
    }


def test_fresh_session_recalls_sibyl_memory_and_changes_action(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        old = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        promote = client.post(
            "/api/memory/candidates/promote",
            json={"candidate": _candidate(npc["npc_id"], old["session_id"])},
        )
        assert promote.status_code == 201
        fresh = client.post(
            f"/api/sessions/{old['session_id']}/restart", params={"owner_id": "owner-a"}
        ).json()["fresh"]
        lineage = client.get(
            "/api/sessions", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        )
        assert lineage.status_code == 200
        assert {item["session_id"] for item in lineage.json()["sessions"]} == {
            old["session_id"],
            fresh["session_id"],
        }
        assert (
            client.get(
                "/api/sessions", params={"owner_id": "owner-b", "npc_id": npc["npc_id"]}
            ).status_code
            == 403
        )
        response = client.post(
            f"/api/sessions/{fresh['session_id']}/continuity",
            json={"owner_id": "owner-a", "npc_id": npc["npc_id"], "query": "interface"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "context_restored"
        assert body["action"].startswith("Use dark interfaces")
        assert body["recalled_memory_ids"] == ["m-dark"]
        assert body["retrievals"][0]["source"] == "sibyl_search"
        assert body["retrievals"][0]["tier"] == "entity"
        assert body["retrievals"][0]["query"] == "interface"
        assert "Sibyl search returned" in body["retrievals"][0]["relevance_reason"]
        assert body["agent_run"]["used_memory_ids"] == ["m-dark"]
        assert "dark interfaces" in body["agent_response"]
        event_types = [
            event["event_type"]
            for event in client.get(
                "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
            ).json()["events"]
        ]
        assert "memory.recall_succeeded" in event_types
        assert "behavior.changed_by_memory" in event_types


def test_continuity_comparison_runs_real_enabled_and_disabled_lanes(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        first = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        promoted = client.post(
            "/api/memory/candidates/promote",
            json={"candidate": _candidate(npc["npc_id"], first["session_id"])},
        )
        assert promoted.status_code == 201
        fresh = client.post(
            f"/api/sessions/{first['session_id']}/restart", params={"owner_id": "owner-a"}
        ).json()["fresh"]

        comparison = client.post(
            "/api/continuity/compare",
            json={
                "owner_id": "owner-a",
                "npc_id": npc["npc_id"],
                "session_id": fresh["session_id"],
                "query": "How should I set up my interface?",
            },
        )

        assert comparison.status_code == 200
        body = comparison.json()
        assert body["diverged"] is True
        assert body["memory_lane"]["session_id"] == fresh["session_id"]
        assert body["memory_lane"]["decision"]["influenced_by_memory"] is True
        assert body["memory_disabled_lane"]["decision"]["memory_enabled"] is False
        assert body["memory_disabled_lane"]["decision"]["action"] == "request_missing_context"
        disabled_id = body["memory_disabled_lane"]["session_id"]
        disabled_read = client.get(f"/api/sessions/{disabled_id}", params={"owner_id": "owner-a"})
        assert disabled_read.status_code == 200
        assert disabled_read.json()["session"]["status"] == "terminated"


def test_continuity_comparison_requires_a_clean_session(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        turn = client.post(
            "/api/conversations/turns",
            json={
                "owner_id": "owner-a",
                "session_id": session["session_id"],
                "text": "A transient turn",
            },
        )
        assert turn.status_code == 201
        comparison = client.post(
            "/api/continuity/compare",
            json={
                "owner_id": "owner-a",
                "npc_id": npc["npc_id"],
                "session_id": session["session_id"],
                "query": "What should carry forward?",
            },
        )
        assert comparison.status_code == 409
        assert "clean fresh session" in comparison.json()["detail"]


def test_fresh_conversation_turn_automatically_uses_recalled_context(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        old = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        promoted = client.post(
            "/api/memory/candidates/promote",
            json={"candidate": _candidate(npc["npc_id"], old["session_id"])},
        )
        assert promoted.status_code == 201
        fresh = client.post(
            f"/api/sessions/{old['session_id']}/restart", params={"owner_id": "owner-a"}
        ).json()["fresh"]

        response = client.post(
            "/api/conversations/turns",
            json={
                "owner_id": "owner-a",
                "session_id": fresh["session_id"],
                "text": "How should I set up my interface?",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["memory_influenced"] is True
        assert body["recalled_memory_ids"] == ["m-dark"]
        assert body["retrievals"][0]["source"] == "sibyl_search"
        assert body["agent_run"]["used_memory_ids"] == ["m-dark"]
        assert "dark interfaces" in body["agent_response"]
        event_types = [
            event["event_type"]
            for event in client.get(
                "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
            ).json()["events"]
        ]
        assert "memory.recall_succeeded" in event_types
        assert "behavior.changed_by_memory" in event_types


def test_failed_fresh_recall_does_not_record_a_transient_turn(tmp_path, monkeypatch) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        adapter = client.app.state.memory_adapter

        def fail_recall(*args: object, **kwargs: object) -> list[object]:
            raise MemoryAdapterError("simulated local provider read failure")

        monkeypatch.setattr(adapter, "recall_with_metadata", fail_recall)
        response = client.post(
            "/api/conversations/turns",
            json={
                "owner_id": "owner-a",
                "session_id": session["session_id"],
                "text": "This must not be stored when recall fails",
            },
        )

        assert response.status_code == 503
        assert (
            client.get(
                f"/api/sessions/{session['session_id']}/turns",
                params={"owner_id": "owner-a"},
            ).json()
            == []
        )
        event_types = [
            event["event_type"]
            for event in client.get(
                "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
            ).json()["events"]
        ]
        assert "memory.recall_failed" in event_types
        assert "conversation.turn_recorded" not in event_types


def test_fresh_session_without_memory_fails_safe() -> None:
    with TestClient(
        create_app(Settings(ABRAIN_ENV="test", ABRAIN_MEMORY_ENABLED="false", _env_file=None))
    ) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        response = client.post(
            f"/api/sessions/{session['session_id']}/continuity",
            json={"owner_id": "owner-a", "npc_id": npc["npc_id"], "query": "workspace"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "continuity_unavailable"
        assert response.json()["action"] == "request_missing_context"
        assert response.json()["agent_run"]["needs_more_context"] is True
        assert "owner context" in response.json()["agent_response"]


def test_empty_sibyl_recall_returns_a_safe_provider_verdict(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        response = client.post(
            f"/api/sessions/{session['session_id']}/continuity",
            json={"owner_id": "owner-a", "npc_id": npc["npc_id"], "query": "unknown context"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "no_relevant_memory"
        assert body["search_verdict"]["code"] in {
            "empty_store",
            "no_match",
            "abstained_on",
            "no_scoped_match",
        }
        assert body["search_verdict"]["returned"] == 0
        assert body["agent_run"]["needs_more_context"] is True


def test_behavior_event_requires_runner_used_memory_ids(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings, agent_runner=NonUsingRunner())) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        old = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        assert (
            client.post(
                "/api/memory/candidates/promote",
                json={"candidate": _candidate(npc["npc_id"], old["session_id"])},
            ).status_code
            == 201
        )
        fresh = client.post(
            f"/api/sessions/{old['session_id']}/restart", params={"owner_id": "owner-a"}
        ).json()["fresh"]
        response = client.post(
            f"/api/sessions/{fresh['session_id']}/continuity",
            json={"owner_id": "owner-a", "npc_id": npc["npc_id"], "query": "interface"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["recalled_memory_ids"] == ["m-dark"]
        assert body["agent_run"]["used_memory_ids"] == []
        assert body["influenced_by_memory"] is False
        event_types = [
            event["event_type"]
            for event in client.get(
                "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
            ).json()["events"]
        ]
        assert "behavior.changed_by_memory" not in event_types


def test_continuity_and_restart_require_the_npc_owner(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]

        continuity = client.post(
            f"/api/sessions/{session['session_id']}/continuity",
            json={"owner_id": "owner-b", "npc_id": npc["npc_id"], "query": "workspace"},
        )
        restart = client.post(
            f"/api/sessions/{session['session_id']}/restart", params={"owner_id": "owner-b"}
        )

        assert continuity.status_code == 403
        assert restart.status_code == 403

        session_read = client.get(
            f"/api/sessions/{session['session_id']}", params={"owner_id": "owner-b"}
        )
        turns_read = client.get(
            f"/api/sessions/{session['session_id']}/turns", params={"owner_id": "owner-b"}
        )
        assert session_read.status_code == 403
        assert turns_read.status_code == 403

        turn = client.post(
            "/api/conversations/turns",
            json={
                "owner_id": "owner-b",
                "session_id": session["session_id"],
                "text": "private turn",
            },
        )
        assert turn.status_code == 403

        foreign_candidate = _candidate(npc["npc_id"], session["session_id"])
        foreign_candidate["owner_id"] = "owner-b"
        promotion = client.post(
            "/api/memory/candidates/promote", json={"candidate": foreign_candidate}
        )
        assert promotion.status_code == 403

        owner_events = client.get(
            "/api/events/recent", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        )
        foreign_events = client.get(
            "/api/events/recent", params={"owner_id": "owner-b", "npc_id": npc["npc_id"]}
        )
        unscoped_events = client.get("/api/events/recent")
        assert owner_events.status_code == 200
        assert foreign_events.status_code == 200
        assert unscoped_events.status_code == 200
        assert any(event["event_type"] == "npc.created" for event in owner_events.json()["events"])
        assert not foreign_events.json()["events"]
        assert all(
            event["event_type"].startswith("system.") for event in unscoped_events.json()["events"]
        )
