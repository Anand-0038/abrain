"""Small resilient transport shared by Gemini extraction and agent execution."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


async def post_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    attempts: int = 3,
) -> httpx.Response:
    """Retry only transient Gemini failures and preserve permanent fail-closed behavior."""

    if attempts < 1:
        raise ValueError("attempts must be positive")

    last_request_error: httpx.RequestError | None = None
    for attempt in range(attempts):
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            last_request_error = exc
            if attempt == attempts - 1:
                raise
        else:
            transient_status = response.status_code == 429 or response.status_code >= 500
            if not transient_status or attempt == attempts - 1:
                response.raise_for_status()
                return response

        await asyncio.sleep(0.35 * (2**attempt))

    assert last_request_error is not None
    raise last_request_error
