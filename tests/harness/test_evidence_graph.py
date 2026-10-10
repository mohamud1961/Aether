from __future__ import annotations

import copy

import pytest

from aether.evidence_graph import (
    EvidenceGraph,
    Hypothesis,
    Observation,
    ProvenanceEdge,
    Relation,
    Requirement,
)


def _graph() -> EvidenceGraph:
    graph = EvidenceGraph(task_id="task", run_id="run", task_sha256="a" * 64)
    graph.add_requirement(Requirement("req", "must be correct", "a" * 64, "0:15"))
    graph.add_hypothesis(Hypothesis("hyp", "connectivity is broken", 1))
    return graph


def _observation(
    receipt_id: str,
    generation: int | None,
    *,
    origin: str = "probe",
) -> Observation:
    return Observation(
        receipt_id=receipt_id,
        task_id="task",
        run_id="run",
        task_state_generation=generation,
        origin_id=origin,
        kind="check_result",
        summary=receipt_id,
    )


def test_mutation_makes_old_relation_historical_without_deleting_it() -> None:
    graph = _graph()
    graph.add_observation(_observation("old", 0))
    graph.add_relation(Relation("hyp", "old", "contradicts", "fixture"))
    assert graph.relation_rows("hyp")[0]["freshness"] == "current"

    graph.mutate(1)

    row = graph.relation_rows("hyp")[0]
    assert row["freshness"] == "historical"
    assert row["invalidated"] is False


def test_unknown_generation_never_becomes_current() -> None:
    graph = _graph()
    graph.add_observation(_observation("legacy", None))
    graph.add_relation(Relation("hyp", "legacy", "uncertain", "fixture"))
    assert graph.relation_rows("hyp")[0]["freshness"] == "unknown_generation"


def test_future_and_cross_scope_observations_fail_closed() -> None:
    graph = _graph()
    with pytest.raises(ValueError, match="future observation"):
        graph.add_observation(_observation("future", 1))
    with pytest.raises(ValueError, match="cross-scope"):
        graph.add_observation(
            Observation(
                receipt_id="wrong-run",
                task_id="task",
                run_id="other",
                task_state_generation=0,
                origin_id="probe",
                kind="check_result",
                summary="bad",
            )
        )


def test_duplicate_receipt_is_idempotent_but_collision_rejected() -> None:
    graph = _graph()
    observation = _observation("same", 0)
    graph.add_observation(observation)
    graph.add_observation(observation)
    assert len(graph.observations) == 1
    with pytest.raises(ValueError, match="receipt identity collision"):
        graph.add_observation(_observation("same", 0, origin="different"))


def test_shared_origin_is_preserved_instead_of_counted_as_independent() -> None:
    graph = _graph()
    graph.add_observation(_observation("one", 0, origin="command-1"))
    graph.add_observation(_observation("two", 0, origin="command-1"))
    graph.add_relation(Relation("hyp", "one", "supports", "fixture"))
    graph.add_relation(Relation("hyp", "two", "supports", "fixture"))
    assert graph.independent_origin_count("hyp") == 1


def test_superseding_requirement_invalidates_old_edges_but_keeps_history() -> None:
    graph = _graph()
    graph.add_observation(_observation("proof", 0))
    graph.add_provenance_edge(ProvenanceEdge("req", "proof"))
    graph.add_relation(Relation("req", "proof", "relevant", "fixture", head="ranking"))

    graph.supersede_requirement(
        "req",
        Requirement("req-v2", "must be correct under v2", "a" * 64, "16:40"),
    )

    assert graph.requirements["req"].status == "superseded"
    assert graph.requirements["req-v2"].status == "current"
    assert graph.relation_rows("req")[0]["invalidated"] is True
    assert graph.provenance_rows("req")[0]["invalidated"] is True


def test_probabilities_are_complete_bounded_and_normalized() -> None:
    graph = _graph()
    graph.add_observation(_observation("obs", 0))
    graph.add_relation(
        Relation(
            "hyp",
            "obs",
            "supports",
            "judge",
            probabilities={
                "supports": 0.7,
                "contradicts": 0.1,
                "irrelevant": 0.1,
                "uncertain": 0.1,
            },
        )
    )
    with pytest.raises(ValueError, match="incomplete probability"):
        graph.add_relation(
            Relation(
                "hyp",
                "obs",
                "supports",
                "bad",
                probabilities={"supports": 1.0},
            )
        )


def test_snapshot_round_trip_preserves_freshness_and_integrity() -> None:
    graph = _graph()
    graph.add_observation(_observation("old", 0))
    graph.add_relation(Relation("hyp", "old", "contradicts", "fixture"))
    graph.mutate(1)
    graph.add_observation(_observation("current", 1))
    graph.add_relation(Relation("hyp", "current", "supports", "fixture"))

    snapshot = graph.snapshot()
    restored = EvidenceGraph.from_snapshot(snapshot)

    assert restored.snapshot() == snapshot
    rows = restored.relation_rows("hyp")
    assert [row["freshness"] for row in rows] == ["current", "historical"]

    tampered = copy.deepcopy(snapshot)
    tampered["body"]["task_state_generation"] = 0
    with pytest.raises(ValueError, match="integrity mismatch"):
        EvidenceGraph.from_snapshot(tampered)


def test_generation_cannot_move_backwards() -> None:
    graph = _graph()
    graph.mutate(2)
    with pytest.raises(ValueError, match="must advance"):
        graph.mutate(1)


def test_compact_summary_keeps_active_hypothesis_visible_after_many_revisions() -> None:
    graph = EvidenceGraph(task_id="task", run_id="run", task_sha256="a" * 64)
    graph.add_requirement(Requirement("task:raw", "raw contract", "a" * 64, "0:12"))
    for index in range(10):
        hypothesis = Hypothesis(f"old:{index}", f"old hypothesis {index}", index)
        graph.add_hypothesis(hypothesis)
        graph.retire_hypothesis(hypothesis.hypothesis_id)
    graph.add_hypothesis(Hypothesis("active:now", "current live hypothesis", 11))

    summary = graph.compact_summary(max_items=8)
    visible = [row["subject_id"] for row in summary["subjects"]]

    assert "active:now" in visible
    assert visible.index("active:now") < next(
        (index for index, row in enumerate(summary["subjects"]) if row["status"] == "retired"),
        len(visible),
    )


def test_compact_summary_collapses_only_same_origin_same_exact_version() -> None:
    graph = _graph()
    graph.add_observation(Observation(
        receipt_id="read-1", task_id="task", run_id="run", task_state_generation=0,
        origin_id="path:workspace/spec.md", kind="read_file", summary="first read",
        step=1, artifact_sha256="a" * 64, payload_sha256="1" * 64,
    ))
    graph.add_observation(Observation(
        receipt_id="read-2", task_id="task", run_id="run", task_state_generation=0,
        origin_id="path:workspace/spec.md", kind="read_file", summary="same bytes again",
        step=2, artifact_sha256="a" * 64, payload_sha256="2" * 64,
    ))
    graph.add_observation(Observation(
        receipt_id="read-3", task_id="task", run_id="run", task_state_generation=0,
        origin_id="path:workspace/spec.md", kind="read_file", summary="changed bytes",
        step=3, artifact_sha256="b" * 64, payload_sha256="3" * 64,
    ))
    graph.add_observation(Observation(
        receipt_id="read-other", task_id="task", run_id="run", task_state_generation=0,
        origin_id="path:workspace/other.md", kind="read_file", summary="different file",
        step=4, artifact_sha256="a" * 64, payload_sha256="4" * 64,
    ))

    summary = graph.compact_summary(max_items=8)

    assert len(graph.observations) == 4
    assert [row["receipt_id"] for row in summary["observations"]] == [
        "read-other", "read-3", "read-2"
    ]
    assert summary["observation_rendering"] == {
        "durable_receipts": 4,
        "distinct_versions": 3,
        "rendered": 3,
        "duplicate_receipts_collapsed": 1,
        "distinct_versions_omitted": 0,
    }
    snapshot = graph.snapshot()
    assert len(snapshot["body"]["observations"]) == 4
