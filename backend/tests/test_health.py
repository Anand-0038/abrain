import pytest
from fastapi.testclient import TestClient


def test_health_reports_local_boundary(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["service"] == "abrain-runtime"
    assert response.json()["status"] == "ok"
    assert response.json()["memory_boundary"] == "not_configured"


def test_health_rejects_unknown_route(client: TestClient) -> None:
    assert client.get("/api/unknown").status_code == 404


def test_settings_accept_local_sibyl_configuration() -> None:
    from abrain_api.config import Settings

    settings = Settings(ABRAIN_MEMORY_ENABLED="true", ABRAIN_SIBYL_DB_PATH=".data/test.db")

    assert settings.memory_enabled is True
    assert str(settings.sibyl_db_path) == ".data/test.db"


def test_gemini_provider_rejects_blank_api_key() -> None:
    from abrain_api.config import Settings
    from abrain_api.main import create_app

    settings = Settings(
        ABRAIN_MODEL_PROVIDER="gemini",
        ABRAIN_GEMINI_API_KEY="",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="requires ABRAIN_GEMINI_API_KEY"):
        with TestClient(create_app(settings)):
            pass


def test_settings_parse_comma_separated_cors_from_environment(monkeypatch) -> None:
    from abrain_api.config import Settings

    monkeypatch.setenv("ABRAIN_CORS_ORIGINS", "http://127.0.0.1:3125,http://localhost:3125")
    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://127.0.0.1:3125", "http://localhost:3125"]


def test_cors_allows_frontend_mutation_requests(client: TestClient) -> None:
    response = client.options(
        "/api/npcs",
        headers={
            "Origin": "http://testserver",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://testserver"
    assert "POST" in response.headers["access-control-allow-methods"]
