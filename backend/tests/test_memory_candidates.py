import pytest

from abrain_api.modules.memory_candidates import (
    MemoryCandidate,
    candidate_to_record,
    decide_promotion,
)


def candidate(**overrides: object) -> MemoryCandidate:
    values: dict[str, object] = {
        "candidate_id": "candidate-1",
        "owner_id": "owner-a",
        "npc_id": "nova",
        "source_session_id": "session-1",
        "source_turn_id": "turn-1",
        "concept": "preference",
        "key": "interface_style",
        "value": "dark interfaces",
        "confidence": 0.95,
    }
    values.update(overrides)
    return MemoryCandidate.model_validate(values)


def test_explicit_memory_promotes_even_when_confidence_is_low() -> None:
    item = candidate(confidence=0.4, explicit_remember=True)

    assert decide_promotion(item).disposition == "promote"
    assert candidate_to_record(item).evidence_ref == "turn-1"


def test_transient_context_is_rejected() -> None:
    assert decide_promotion(candidate(transient=True)).disposition == "reject"


def test_sensitive_or_uncertain_context_requires_confirmation() -> None:
    assert decide_promotion(candidate(sensitive=True)).disposition == "confirm"
    assert decide_promotion(candidate(confidence=0.5)).disposition == "confirm"


def test_only_promoted_candidates_can_become_records() -> None:
    with pytest.raises(ValueError, match="confirmation"):
        candidate_to_record(candidate(confidence=0.2))
