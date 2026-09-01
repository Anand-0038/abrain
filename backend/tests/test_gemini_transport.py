from __future__ import annotations

import httpx
import pytest

from abrain_api.modules.gemini_transport import post_json_with_retry


@pytest.mark.anyio
async def test_retries_transient_response_then_returns_success(monkeypatch) -> None:
    statuses = iter([503, 429, 200])

    async def no_sleep(_: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), request=request, json={"ok": True})

    monkeypatch.setattr("abrain_api.modules.gemini_transport.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await post_json_with_retry(
            client,
            "https://provider.test/generate",
            headers={"x-goog-api-key": "test-only"},
            payload={"contents": []},
        )

    assert response.status_code == 200


@pytest.mark.anyio
async def test_does_not_retry_permanent_client_error(monkeypatch) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=request, json={"error": "bad request"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await post_json_with_retry(
                client,
                "https://provider.test/generate",
                headers={"x-goog-api-key": "test-only"},
                payload={"contents": []},
            )

    assert calls == 1
