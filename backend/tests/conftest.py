import pytest
from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                ABRAIN_ENV="test",
                ABRAIN_CORS_ORIGINS="http://testserver",
            )
        )
    )
