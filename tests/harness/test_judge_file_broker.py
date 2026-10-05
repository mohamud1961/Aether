from __future__ import annotations

import json
from pathlib import Path
import threading
import time

from aether.providers.judge_broker import FileBrokerEvaluator, REQUEST_SCHEMA, RESPONSE_SCHEMA


def _typed_provider_result(request: dict) -> dict:
    answers = {}
    for qid, spec in request["questions"].items():
        choices = list(spec["criteria"])
        selected = choices[0]
        answers[qid] = {
            "type": "choice",
            "choice": selected,
            "confidence": 1.0,
            "probabilities": {choice: (1.0 if choice == selected else 0.0) for choice in choices},
        }
    return {
        "model": "judge-latest",
        "ok": True,
        "provider": "judge",
        "result": {
            "answers": answers,
            "model": "judge-1.13.0",
            "usage": {"input_tokens": 500, "output_tokens": 60},
        },
    }


def test_file_broker_round_trip_and_model_identity(tmp_path: Path) -> None:
    evaluator = FileBrokerEvaluator(
        broker_dir=tmp_path / "broker",
        journal=tmp_path / "judge_provider.jsonl",
        expected_result_model="judge-1.13.0",
        max_calls=1,
        cap_gbp="0.01",
        timeout_s=5,
        poll_s=0.01,
    )
    request = {
        "model": "judge-1.13.0",
        "state": {"public": True},
        "questions": {
            "q": {
                "type": "choice",
                "instructions": "Choose.",
                "criteria": {"a": "A", "b": "B"},
            }
        },
    }

    def respond() -> None:
        path = tmp_path / "broker" / "request_001.json"
        for _ in range(500):
            if path.exists():
                break
            time.sleep(0.01)
        envelope = json.loads(path.read_text())
        assert envelope["schema"] == REQUEST_SCHEMA
        provider_result = _typed_provider_result(envelope["request"])
        response = {
            "schema": RESPONSE_SCHEMA,
            "request_sha256": envelope["request_sha256"],
            "gateway_request_id": "test-request",
            "provider_result": provider_result,
        }
        target = tmp_path / "broker" / "response_001.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(response))
        tmp.replace(target)

    thread = threading.Thread(target=respond)
    thread.start()
    result = evaluator(request)
    thread.join(timeout=2)
    assert result["result"]["model"] == "judge-1.13.0"
    assert evaluator.calls == 1
    journal = (tmp_path / "judge_provider.jsonl").read_text()
    assert "broker_request" in journal
    assert "broker_response" in journal


def test_file_broker_rejects_wrong_underlying_model(tmp_path: Path) -> None:
    evaluator = FileBrokerEvaluator(
        broker_dir=tmp_path / "broker",
        journal=tmp_path / "judge_provider.jsonl",
        expected_result_model="judge-1.13.0",
        max_calls=1,
        timeout_s=5,
        poll_s=0.01,
    )
    request = {
        "model": "judge-1.13.0",
        "state": {},
        "questions": {"q": {"type": "choice", "instructions": "x", "criteria": {"a": "A"}}},
    }

    def respond() -> None:
        path = tmp_path / "broker" / "request_001.json"
        for _ in range(500):
            if path.exists():
                break
            time.sleep(0.01)
        envelope = json.loads(path.read_text())
        provider_result = _typed_provider_result(envelope["request"])
        provider_result["result"]["model"] = "wrong-model"
        (tmp_path / "broker" / "response_001.json").write_text(json.dumps({
            "schema": RESPONSE_SCHEMA,
            "request_sha256": envelope["request_sha256"],
            "provider_result": provider_result,
        }))

    thread = threading.Thread(target=respond)
    thread.start()
    try:
        evaluator(request)
    except ValueError as exc:
        assert "model identity mismatch" in str(exc)
    else:
        raise AssertionError("wrong model was accepted")
    thread.join(timeout=2)

def test_file_broker_supports_multiple_hash_bound_rounds(tmp_path: Path) -> None:
    evaluator = FileBrokerEvaluator(
        broker_dir=tmp_path / "broker",
        journal=tmp_path / "judge_provider.jsonl",
        expected_result_model="judge-1.13.0",
        max_calls=3,
        cap_gbp="0.01",
        timeout_s=5,
        poll_s=0.01,
    )

    requests = [
        {
            "model": "judge-1.13.0",
            "state": {"round": index},
            "questions": {
                "q": {
                    "type": "choice",
                    "instructions": "Choose.",
                    "criteria": {"a": "A", "b": "B"},
                }
            },
        }
        for index in (1, 2, 3)
    ]

    def respond() -> None:
        for index in (1, 2, 3):
            request_path = tmp_path / "broker" / f"request_{index:03d}.json"
            for _ in range(500):
                if request_path.exists():
                    break
                time.sleep(0.01)
            envelope = json.loads(request_path.read_text())
            assert envelope["call"] == index
            provider_result = _typed_provider_result(envelope["request"])
            target = tmp_path / "broker" / f"response_{index:03d}.json"
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({
                "schema": RESPONSE_SCHEMA,
                "request_sha256": envelope["request_sha256"],
                "gateway_request_id": f"test-request-{index}",
                "provider_result": provider_result,
            }))
            tmp.replace(target)

    thread = threading.Thread(target=respond)
    thread.start()
    results = [evaluator(request) for request in requests]
    thread.join(timeout=2)

    assert [row["result"]["model"] for row in results] == ["judge-1.13.0"] * 3
    assert evaluator.calls == 3
    journal_rows = [
        json.loads(line)
        for line in (tmp_path / "judge_provider.jsonl").read_text().splitlines()
    ]
    requests_seen = [row for row in journal_rows if row.get("event") == "broker_request"]
    responses_seen = [row for row in journal_rows if row.get("event") == "broker_response"]
    assert [row["call"] for row in requests_seen] == [1, 2, 3]
    assert [row["call"] for row in responses_seen] == [1, 2, 3]
    assert len({row["request_sha256"] for row in requests_seen}) == 3


def test_file_broker_rejects_invalid_multi_call_bounds(tmp_path: Path) -> None:
    for value in (0, 65):
        try:
            FileBrokerEvaluator(
                broker_dir=tmp_path / f"broker-{value}",
                journal=tmp_path / f"judge-{value}.jsonl",
                expected_result_model="judge-1.13.0",
                max_calls=value,
            )
        except ValueError as exc:
            assert "invalid JUDGE file-broker configuration" in str(exc)
        else:
            raise AssertionError(f"max_calls={value} unexpectedly accepted")

