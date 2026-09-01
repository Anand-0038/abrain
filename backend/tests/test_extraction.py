import pytest

from abrain_api.modules.extraction import ExtractionError, parse_gemini_response


def test_gemini_structured_response_is_validated_into_generic_drafts() -> None:
    batch = parse_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"candidates":[{"concept":"preference",'
                                    '"key":"ui_style","value":"calm interfaces",'
                                    '"confidence":0.94,"explicit_remember":false,'
                                    '"sensitive":false,"transient":false}]}'
                                )
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert batch.candidates[0].concept == "preference"
    assert batch.candidates[0].key == "ui_style"
    assert batch.candidates[0].confidence == 0.94


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"candidates": []},
        {"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]},
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"candidates":[{"concept":"unsupported",'
                                    '"key":"x","value":"y","confidence":1}]}'
                                )
                            }
                        ]
                    }
                }
            ]
        },
    ],
)
def test_malformed_model_output_is_rejected(payload: object) -> None:
    with pytest.raises(ExtractionError):
        parse_gemini_response(payload)
