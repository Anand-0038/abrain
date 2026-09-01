from datetime import UTC, datetime

from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app
from abrain_api.modules.memory import MemoryRecord


def _settings(tmp_path, enabled: bool = True) -> Settings:
    return Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED=enabled,
        ABRAIN_SIBYL_DB_PATH=tmp_path / "tasks.sqlite3",
        ABRAIN_CORS_ORIGINS="http://testserver",
    )


def _npc_and_session(client: TestClient, owner_id: str = "owner-task") -> tuple[str, str]:
    npc_response = client.post(
        "/api/npcs",
        json={"owner_id": owner_id, "name": "Task NPC"},
    )
    assert npc_response.status_code == 201
    npc_id = npc_response.json()["npc"]["npc_id"]
    session_response = client.post(
        "/api/sessions",
        json={"owner_id": owner_id, "npc_id": npc_id},
    )
    assert session_response.status_code == 201
    return npc_id, session_response.json()["session"]["session_id"]


def test_arbitrary_task_runs_through_sibyl_hot_state_and_provenance(tmp_path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        npc_id, session_id = _npc_and_session(client)
        adapter = client.app.state.memory_adapter
        adapter.write(
            MemoryRecord(
                memory_id="task-dark-preference",
                owner_id="owner-task",
                npc_id=npc_id,
                source_session_id=session_id,
                concept="preference",
                key="workspace_style",
                value="dark interfaces with restrained motion",
                confidence=0.99,
                created_at=datetime.now(UTC),
                evidence_ref="turn-preference",
            )
        )
        unrelated = MemoryRecord(
            memory_id="task-travel-goal",
            owner_id="owner-task",
            npc_id=npc_id,
            source_session_id=session_id,
            concept="goal",
            key="travel",
            value="visit Japan next spring",
            confidence=0.96,
            created_at=datetime.now(UTC),
            evidence_ref="turn-travel",
        )
        adapter.write(unrelated)

        created = client.post(
            "/api/tasks",
            json={
                "owner_id": "owner-task",
                "assigned_agent_id": npc_id,
                "objective": "Plan a dark interfaces workspace with restrained motion.",
            },
        )
        assert created.status_code == 201
        task = created.json()["task"]
        assert task["status"] == "queued"

        result = client.post(
            f"/api/tasks/{task['task_id']}/run",
            json={"owner_id": "owner-task", "session_id": session_id},
        )
        assert result.status_code == 200
        body = result.json()
        assert body["task"]["status"] == "completed"
        assert body["task"]["relevant_memory_ids"] == ["task-dark-preference"]
        assert body["agent_run"]["used_memory_ids"] == ["task-dark-preference"]
        assert body["persisted_result_memory_id"] == f"task_result_{task['task_id']}"
        assert unrelated.memory_id not in body["task"]["relevant_memory_ids"]
        assert "dark interfaces" in body["task"]["result"]

        hot_state = adapter.get_task_state("owner-task", task["task_id"])
        assert hot_state is not None
        assert hot_state.status == "completed"
        assert hot_state.result == body["task"]["result"]

        events = client.get(
            "/api/events/recent",
            params={"owner_id": "owner-task", "npc_id": npc_id},
        ).json()["events"]
        task_events = [
            event["event_type"] for event in events if event["event_type"].startswith("task.")
        ]
        assert task_events == [
            "task.created",
            "task.started",
            "task.step_changed",
            "task.step_changed",
            "task.completed",
        ]


def test_task_without_memory_still_returns_a_real_generic_result(tmp_path) -> None:
    with TestClient(create_app(_settings(tmp_path, enabled=False))) as client:
        npc_id, session_id = _npc_and_session(client, owner_id="owner-no-memory")
        created = client.post(
            "/api/tasks",
            json={
                "owner_id": "owner-no-memory",
                "assigned_agent_id": npc_id,
                "title": "Organize the next steps",
                "objective": "Organize the next three steps for an unfinished project.",
            },
        )
        assert created.status_code == 201
        task_id = created.json()["task"]["task_id"]

        result = client.post(
            f"/api/tasks/{task_id}/run",
            json={"owner_id": "owner-no-memory", "session_id": session_id},
        )
        assert result.status_code == 200
        body = result.json()
        assert body["task"]["status"] == "review"
        assert body["task"]["relevant_memory_ids"] == []
        assert body["persisted_result_memory_id"] is None
        assert body["agent_run"]["memory_effect"] == "none"
        assert "did not call external tools" in body["task"]["result"]


def test_task_owner_scope_is_enforced(tmp_path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        npc_id, _ = _npc_and_session(client, owner_id="owner-private")
        created = client.post(
            "/api/tasks",
            json={
                "owner_id": "owner-private",
                "assigned_agent_id": npc_id,
                "objective": "Review this private task.",
            },
        )
        task_id = created.json()["task"]["task_id"]
        assert (
            client.get(f"/api/tasks/{task_id}", params={"owner_id": "another-owner"}).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/tasks/{task_id}/run",
                json={"owner_id": "another-owner"},
            ).status_code
            == 403
        )
