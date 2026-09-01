import pytest
from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


@pytest.fixture(autouse=True)
def isolate_tests_from_local_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's ignored .env must never turn deterministic tests into live provider tests."""

    monkeypatch.setenv("ABRAIN_MODEL_PROVIDER", "disabled")
    monkeypatch.setenv("ABRAIN_AGENT_PROVIDER", "local")
    monkeypatch.setenv("ABRAIN_GEMINI_API_KEY", "")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                ABRAIN_ENV="test",
                ABRAIN_CORS_ORIGINS="http://testserver",
                _env_file=None,
            )
        )
    )
