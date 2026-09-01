"""Optional structured memory extraction with an explicit provider boundary."""

from __future__ import annotations

import json
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .gemini_transport import post_json_with_retry
from .memory import MemoryConcept
from .memory_candidates import MemoryCandidate


class ExtractionError(RuntimeError):
    """Raised when a configured extraction provider cannot produce valid output."""


class ExtractionUnavailable(ExtractionError):
    """Raised when no model provider is configured."""


class CandidateDraft(BaseModel):
    """The only shape accepted from a model before server provenance is attached."""

    model_config = ConfigDict(extra="forbid")

    concept: MemoryConcept
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    explicit_remember: bool = False
    sensitive: bool = False
    transient: bool = False


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[CandidateDraft] = Field(default_factory=list, max_length=8)


class CandidateExtractor(Protocol):
    async def extract(
        self, *, text: str, owner_id: str, npc_id: str, session_id: str, turn_id: str
    ) -> list[MemoryCandidate]: ...


def candidate_schema() -> dict[str, object]:
    """Return a provider-neutral JSON schema for structured generation."""

    # Gemini's REST responseSchema accepts a deliberately small JSON Schema subset and
    # rejects Pydantic's $defs/$ref/additionalProperties output. Keep this wire schema
    # explicit, then validate the returned JSON again with CandidateBatch.
    draft = {
        "type": "object",
        "properties": {
            "concept": {
                "type": "string",
                "enum": [
                    "person",
                    "preference",
                    "relationship",
                    "habit",
                    "decision",
                    "constraint",
                    "value",
                    "goal",
                    "project",
                    "event",
                ],
            },
            "key": {"type": "string"},
            "value": {"type": "string"},
            "confidence": {"type": "number"},
            "explicit_remember": {"type": "boolean"},
            "sensitive": {"type": "boolean"},
            "transient": {"type": "boolean"},
        },
        "required": [
            "concept",
            "key",
            "value",
            "confidence",
            "explicit_remember",
            "sensitive",
            "transient",
        ],
    }
    return {
        "type": "object",
        "properties": {"candidates": {"type": "array", "items": draft}},
        "required": ["candidates"],
    }


def parse_gemini_response(payload: object) -> CandidateBatch:
    """Validate Gemini's response envelope and then validate the candidate schema."""

    if not isinstance(payload, dict):
        raise ExtractionError("model response was not an object")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ExtractionError("model response contained no candidates")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ExtractionError("model candidate was malformed")
    content = first.get("content")
    if not isinstance(content, dict):
        raise ExtractionError("model content was malformed")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], dict):
        raise ExtractionError("model content contained no text part")
    text = parts[0].get("text")
    if not isinstance(text, str):
        raise ExtractionError("model content text was missing")
    try:
        decoded = json.loads(text)
        return CandidateBatch.model_validate(decoded)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ExtractionError("model output did not match the candidate schema") from exc


class GeminiCandidateExtractor:
    """Gemini REST adapter; no response is promoted without Pydantic validation."""

    def __init__(self, api_key: SecretStr, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def extract(
        self, *, text: str, owner_id: str, npc_id: str, session_id: str, turn_id: str
    ) -> list[MemoryCandidate]:
        prompt = (
            "Extract only durable owner context from this single conversation turn. "
            "Do not copy the transcript. Return an empty list for greetings, temporary plans, "
            "questions, or unsupported inferences. Keep sensitive facts marked sensitive and "
            "never invent values. Explicit 'remember this' requests must set explicit_remember. "
            f"Conversation turn:\n{text}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": candidate_schema(),
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await post_json_with_retry(
                    client,
                    url,
                    headers={"x-goog-api-key": self._api_key.get_secret_value()},
                    payload=body,
                )
                batch = parse_gemini_response(response.json())
        except (httpx.HTTPError, ValueError, ExtractionError) as exc:
            if isinstance(exc, ExtractionError):
                raise
            raise ExtractionError("configured model extraction request failed") from exc

        return [
            MemoryCandidate(
                candidate_id=f"candidate-{uuid4().hex}",
                owner_id=owner_id,
                npc_id=npc_id,
                source_session_id=session_id,
                source_turn_id=turn_id,
                **draft.model_dump(),
            )
            for draft in batch.candidates
        ]
