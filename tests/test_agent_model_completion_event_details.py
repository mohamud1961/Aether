from runner.agent import _build_model_completion_event_details


def test_build_model_completion_event_details_logs_provider_visible_reasoning_fields():
    details = _build_model_completion_event_details(
        {
            "step": 2,
            "status": "completed",
            "completion": {
                "text": "final answer",
                "reasoning_summary": "Checked verifier output before proposing patch.",
                "reasoning_token_count": 9,
                "provider_reasoning": {
                    "source": "responses.output.reasoning",
                    "summary_count": 1,
                    "encrypted_item_count": 2,
                    "ignored_nested": {"a": 1},
                },
                "reasoning_artifact": {
                    "type": "encrypted_reasoning_continuity",
                    "encoding": "provider_encrypted",
                    "encrypted_content_char_count": 1800,
                    "encrypted_content_hashes": [
                        "hash_a",
                        "hash_b",
                        "hash_c",
                        "hash_d",
                    ],
                    "encrypted_content": "not_logged",
                },
                "tool_calls": [
                    {"id": "call_1", "name": "raw_bash", "arguments": {"command": "pwd"}},
                ],
            },
        }
    )

    assert details is not None
    assert details["assistant_text"] == "final answer"
    assert details["assistant_text_char_count"] == len("final answer")
    assert details["reasoning_summary"] == "Checked verifier output before proposing patch."
    assert details["reasoning_summary_char_count"] == len("Checked verifier output before proposing patch.")
    assert details["reasoning_token_count"] == 9
    assert details["provider_reasoning"] == {
        "source": "responses.output.reasoning",
        "summary_count": 1,
        "encrypted_item_count": 2,
    }
    assert details["reasoning_artifact"] == {
        "type": "encrypted_reasoning_continuity",
        "encoding": "provider_encrypted",
        "encrypted_content_char_count": 1800,
        "encrypted_content_hash_count": 4,
        "encrypted_content_hashes_preview": ["hash_a", "hash_b", "hash_c"],
    }
    assert details["tool_call_count"] == 1
