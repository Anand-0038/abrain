from datetime import UTC, datetime

from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app
from abrain_api.modules.memory import MemoryRecord


def _settings(tmp_path) -> Settings:
    return Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED=True,
        ABRAIN_SIBYL_DB_PATH=tmp_path / "handoffs.sqlite3",
        ABRAIN_CORS_ORIGINS="http://testserver",
    )


def _create_npc(client: TestClient, owner_id: str, name: str) -> tuple[str, str]:
    created = client.post("/api/npcs", json={"owner_id": owner_id, "name": name})
    assert created.status_code == 201
    npc_id = created.json()["npc"]["npc_id"]
    session = client.post("/api/sessions", json={"owner_id": owner_id, "npc_id": npc_id})
    assert session.status_code == 201
    return npc_id, session.json()["session"]["session_id"]


def _memory(memory_id: str, owner_id: str, npc_id: str, session_id: str, key: str, value: str):
    return MemoryRecord(
        memory_id=memory_id,
        owner_id=owner_id,
        npc_id=npc_id,
        source_session_id=session_id,
        concept="preference",
        key=key,
        value=value,
        confidence=0.98,
        created_at=datetime.now(UTC),
        evidence_ref=f"turn-{memory_id}",
    )


def test_primary_delegates_only_selected_context_to_worker(tmp_path) -> None:
    owner_id = "owner-delegation"
    with TestClient(create_app(_settings(tmp_path))) as client:
        primary_id, primary_session_id = _create_npc(client, owner_id, "Atlas")
        worker_response = client.post(
            "/api/npcs/workers",
            json={
                "owner_id": owner_id,
                "primary_agent_id": primary_id,
                "name": "Forge",
                "specialization": "worker",
            },
        )
        assert worker_response.status_code == 201
        worker_id = worker_response.json()["npc"]["npc_id"]
        reviewer_response = client.post(
            "/api/npcs/workers",
            json={
                "owner_id": owner_id,
                "primary_agent_id": primary_id,
                "name": "Sentinel",
                "specialization": "reviewer",
            },
        )
        assert reviewer_response.status_code == 201
        reviewer_id = reviewer_response.json()["npc"]["npc_id"]

        adapter = client.app.state.memory_adapter
        selected = _memory(
            "handoff-selected",
            owner_id,
            primary_id,
            primary_session_id,
            "workspace_style",
            "dark interfaces with restrained motion",
        )
        unrelated = _memory(
            "handoff-unrelated",
            owner_id,
            primary_id,
            primary_session_id,
            "travel_goal",
            "visit Japan next spring",
        )
        worker_private = _memory(
            "worker-private",
            owner_id,
            worker_id,
            primary_session_id,
            "worker_note",
            "private worker context",
        )
        adapter.write(selected)
        adapter.write(unrelated)
        adapter.write(worker_private)

        parent = client.post(
            "/api/tasks",
            json={
                "owner_id": owner_id,
                "assigned_agent_id": primary_id,
                "objective": "Plan the workspace implementation.",
            },
        )
        assert parent.status_code == 201
        parent_task_id = parent.json()["task"]["task_id"]

        handoff_response = client.post(
            f"/api/tasks/{parent_task_id}/handoffs",
            json={
                "owner_id": owner_id,
                "source_agent_id": primary_id,
                "target_agent_id": worker_id,
                "objective": "Turn the workspace decision into an implementation plan.",
                "selected_memory_ids": [selected.memory_id],
            },
        )
        assert handoff_response.status_code == 201
        handoff_body = handoff_response.json()
        handoff = handoff_body["handoff"]
        child_task = handoff_body["task"]
        assert handoff["selected_memory_ids"] == [selected.memory_id]
        assert [item["memory_id"] for item in handoff["selected_context"]] == [selected.memory_id]
        assert child_task["parent_task_id"] == parent_task_id
        assert child_task["assigned_agent_id"] == worker_id

        worker_run = client.post(
            f"/api/tasks/{child_task['task_id']}/run",
            json={"owner_id": owner_id, "handoff_id": handoff["handoff_id"]},
        )
        assert worker_run.status_code == 200
        body = worker_run.json()
        assert body["task"]["status"] == "completed"
        assert body["task"]["assigned_agent_id"] == worker_id
        assert body["task"]["relevant_memory_ids"] == [selected.memory_id]
        assert body["agent_run"]["used_memory_ids"] == [selected.memory_id]
        assert [item["record"]["memory_id"] for item in body["retrievals"]] == [selected.memory_id]
        assert unrelated.memory_id not in body["agent_run"]["response"]
        assert worker_private.memory_id not in body["agent_run"]["response"]
        assert body["handoff"]["status"] == "completed"

        worker_result = adapter.get(owner_id, f"task_result_{child_task['task_id']}")
        assert worker_result is not None
        assert worker_result.npc_id == worker_id

        review_handoff_response = client.post(
            f"/api/tasks/{child_task['task_id']}/handoffs",
            json={
                "owner_id": owner_id,
                "source_agent_id": worker_id,
                "target_agent_id": reviewer_id,
                "objective": "Review the worker's implementation plan for consistency.",
                "selected_memory_ids": [worker_result.memory_id],
            },
        )
        assert review_handoff_response.status_code == 201
        review_handoff_body = review_handoff_response.json()
        review_run = client.post(
            f"/api/tasks/{review_handoff_body['task']['task_id']}/run",
            json={
                "owner_id": owner_id,
                "handoff_id": review_handoff_body["handoff"]["handoff_id"],
            },
        )
        assert review_run.status_code == 200
        review_body = review_run.json()
        assert review_body["task"]["assigned_agent_id"] == reviewer_id
        assert review_body["agent_run"]["used_memory_ids"] == [worker_result.memory_id]
        assert review_body["handoff"]["status"] == "completed"

        events = client.get("/api/events/recent", params={"owner_id": owner_id}).json()["events"]
        handoff_events = [
            event["event_type"] for event in events if event["event_type"].startswith("handoff.")
        ]
        assert handoff_events == [
            "handoff.created",
            "handoff.accepted",
            "handoff.started",
            "handoff.completed",
            "handoff.created",
            "handoff.accepted",
            "handoff.started",
            "handoff.completed",
        ]

        forbidden = client.post(
            f"/api/tasks/{parent_task_id}/handoffs",
            json={
                "owner_id": owner_id,
                "source_agent_id": primary_id,
                "target_agent_id": worker_id,
                "objective": "Try to leak worker context.",
                "selected_memory_ids": [worker_private.memory_id],
            },
        )
        assert forbidden.status_code == 403


def test_owner_cannot_read_handoff_and_roster_stays_bounded(tmp_path) -> None:
    owner_id = "owner-roster"
    with TestClient(create_app(_settings(tmp_path))) as client:
        primary_id, _ = _create_npc(client, owner_id, "Atlas")
        first = client.post(
            "/api/npcs/workers",
            json={
                "owner_id": owner_id,
                "primary_agent_id": primary_id,
                "name": "Forge",
                "specialization": "worker",
            },
        )
        second = client.post(
            "/api/npcs/workers",
            json={
                "owner_id": owner_id,
                "primary_agent_id": primary_id,
                "name": "Sentinel",
                "specialization": "reviewer",
            },
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert (
            client.post(
                "/api/npcs/workers",
                json={
                    "owner_id": owner_id,
                    "primary_agent_id": primary_id,
                    "name": "Extra",
                    "specialization": "planner",
                },
            ).status_code
            == 409
        )
        assert len(client.get("/api/npcs", params={"owner_id": owner_id}).json()["npcs"]) == 3
        assert (
            client.get("/api/handoffs/no-such", params={"owner_id": "other-owner"}).status_code
            == 404
        )
