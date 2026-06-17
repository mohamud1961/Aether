import inspect
import importlib


delta_module = importlib.import_module("harness.aether2.traces.delta")
mirror_module = importlib.import_module("harness.aether2.traces.mirror")
delta_compat_module = importlib.import_module("runner.aether2.delta")
mirror_compat_module = importlib.import_module("runner.aether2.mirror")

assert delta_compat_module is delta_module
assert mirror_compat_module is mirror_module

DeltaReport = delta_module.DeltaReport
Mirror = mirror_module.Mirror
MirrorNote = mirror_module.MirrorNote
SemanticObservation = mirror_module.SemanticObservation


def _empty_delta() -> DeltaReport:
    return DeltaReport(
        workspace_root="/workspace",
        captured_at=0.0,
        files_changed=[],
        artifact_registry_changed=False,
        service_registry_changed=False,
        process_registry_changed=False,
        job_registry_changed=False,
        session_registry_changed=False,
        added_paths=(),
        modified_paths=(),
        deleted_paths=(),
    )


def _changed_delta() -> DeltaReport:
    return DeltaReport(
        workspace_root="/workspace",
        captured_at=1.0,
        files_changed=[],
        artifact_registry_changed=True,
        service_registry_changed=False,
        process_registry_changed=False,
        job_registry_changed=False,
        session_registry_changed=False,
        added_paths=(),
        modified_paths=(),
        deleted_paths=(),
    )


def test_mirror_emits_on_third_identical_zero_delta_action() -> None:
    mirror = Mirror()
    delta = _empty_delta()

    assert mirror.observe("run_command:echo", delta) is None
    assert mirror.observe("run_command:echo", delta) is None

    note = mirror.observe("run_command:echo", delta)
    assert isinstance(note, MirrorNote)
    assert note.streak == 3
    assert note.action_signature == "run_command:echo"
    assert note.fuel_gauge_text is None
    assert note.note_type == "no_delta_progress"
    assert note.text == (
        "Steps in this streak produced no state change. "
        "Already established: none recorded. "
        "Not yet tried: none recorded."
    )
    assert "should" not in note.text.lower()
    assert "next" not in note.text.lower()


def test_mirror_emits_on_sixth_identical_zero_delta_action_with_fuel_gauge() -> None:
    mirror = Mirror()
    delta = _empty_delta()

    notes = [mirror.observe("run_command:echo", delta) for _ in range(6)]
    third_note = notes[2]
    sixth_note = notes[5]

    assert isinstance(third_note, MirrorNote)
    assert third_note.streak == 3
    assert third_note.fuel_gauge_text is None

    assert isinstance(sixth_note, MirrorNote)
    assert sixth_note.streak == 6
    assert sixth_note.action_signature == "run_command:echo"
    assert sixth_note.fuel_gauge_text == "elapsed/remaining time"
    assert sixth_note.text == (
        "Steps in this streak produced no state change. "
        "Already established: none recorded. "
        "Not yet tried: none recorded."
    )
    assert "should" not in sixth_note.text.lower()
    assert "next" not in sixth_note.text.lower()


def test_mirror_resets_on_delta() -> None:
    mirror = Mirror()
    empty = _empty_delta()
    changed = _changed_delta()

    assert mirror.observe("run_command:echo", empty) is None
    assert mirror.observe("run_command:echo", empty) is None
    assert mirror.observe("run_command:echo", changed) is None
    assert mirror.observe("run_command:echo", empty) is None
    assert mirror.observe("run_command:echo", empty) is None

    note = mirror.observe("run_command:echo", empty)
    assert isinstance(note, MirrorNote)
    assert note.streak == 3


def test_mirror_resets_on_action_change() -> None:
    mirror = Mirror()
    delta = _empty_delta()

    assert mirror.observe("run_command:echo", delta) is None
    assert mirror.observe("run_command:echo", delta) is None
    assert mirror.observe("run_command:printf", delta) is None
    assert mirror.observe("run_command:printf", delta) is None

    note = mirror.observe("run_command:printf", delta)
    assert isinstance(note, MirrorNote)
    assert note.streak == 3
    assert note.action_signature == "run_command:printf"


def test_semantic_mirror_emits_on_third_repeated_failed_strategy() -> None:
    mirror = Mirror()
    delta = _empty_delta()
    semantic = SemanticObservation(
        action_family=" Inspect Logs ",
        target="./Logs/App.log/",
        target_kind="path",
        failure_class_before="Missing Dependency",
        failure_class_after="Missing Dependency",
    )

    assert mirror.observe("run_command:grep logs", delta, semantic_observation=semantic) is None
    assert mirror.observe("run_command:grep logs", delta, semantic_observation=semantic) is None

    note = mirror.observe("run_command:grep logs", delta, semantic_observation=semantic)
    assert isinstance(note, MirrorNote)
    assert note.note_type == "semantic_no_progress"
    assert note.streak == 3
    assert note.action_signature == "inspect logs"
    assert note.strategy_family == "inspect logs"
    assert note.target == "logs/app.log"
    assert note.target_kind == "path"
    assert note.failure_class_before == "missing dependency"
    assert note.failure_class_after == "missing dependency"
    assert mirror.repeated_failed_strategy_count == 3
    assert "repeated failed attempts" in note.text.lower()
    assert 'failure class remained "missing dependency"' in note.text.lower()
    assert "new hypothesis" in note.text.lower()
    assert "different strategy family" in note.text.lower()
    assert "should" not in note.text.lower()


def test_semantic_mirror_resets_on_meaningful_progress() -> None:
    mirror = Mirror()
    delta = _empty_delta()
    repeated = SemanticObservation(
        action_family="check package",
        target="ffmpeg",
        target_kind="package",
        failure_class_before="missing package",
        failure_class_after="missing package",
    )
    progress = SemanticObservation(
        action_family="check package",
        target="ffmpeg",
        target_kind="package",
        failure_class_before="missing package",
        failure_class_after="missing package",
        stronger_evidence_added=True,
        artifact_evidence=("logs/install.log",),
        meaningful_artifact_change=True,
    )

    assert mirror.observe("run_command:check", delta, semantic_observation=repeated) is None
    assert mirror.observe("run_command:check", delta, semantic_observation=repeated) is None
    assert mirror.repeated_failed_strategy_count == 2

    assert mirror.observe("run_command:check", delta, semantic_observation=progress) is None
    assert mirror.repeated_failed_strategy_count == 0

    assert mirror.observe("run_command:check", delta, semantic_observation=repeated) is None
    assert mirror.observe("run_command:check", delta, semantic_observation=repeated) is None

    note = mirror.observe("run_command:check", delta, semantic_observation=repeated)
    assert isinstance(note, MirrorNote)
    assert note.streak == 3


def test_semantic_mirror_does_not_trigger_for_legitimate_polling() -> None:
    mirror = Mirror()
    delta = _empty_delta()
    polling = SemanticObservation(
        action_family="poll service",
        target="api",
        target_kind="service",
        failure_class_before="service starting",
        failure_class_after="service starting",
        legitimate_polling=True,
    )

    for _ in range(5):
        assert mirror.observe("run_command:poll", delta, semantic_observation=polling) is None

    assert mirror.repeated_failed_strategy_count == 0
    assert mirror.observe("run_command:poll", delta) is None
    assert mirror.observe("run_command:poll", delta) is None
    note = mirror.observe("run_command:poll", delta)
    assert isinstance(note, MirrorNote)
    assert note.note_type == "no_delta_progress"


def test_semantic_mirror_does_not_trigger_for_bounded_retry() -> None:
    mirror = Mirror()
    delta = _empty_delta()
    bounded_retry = SemanticObservation(
        action_family="restart process",
        target="worker",
        target_kind="process",
        failure_class_before="timeout",
        failure_class_after="timeout",
        bounded_retry=True,
    )

    for _ in range(4):
        assert mirror.observe("run_command:restart", delta, semantic_observation=bounded_retry) is None

    assert mirror.repeated_failed_strategy_count == 0


def test_mirror_module_is_generic_and_model_invisible() -> None:
    source = inspect.getsource(mirror_module).lower()
    banned_terms = {
        "terminal-bench",
        "terminalbench",
        "tb2",
        "tb2.0",
        "search_receipts",
        "view_receipt",
        "view_file_cache",
        "search_files",
        "probe_service",
    }

    assert set(getattr(mirror_module, "__all__", ())) == {"Mirror", "MirrorNote", "SemanticObservation"}
    for term in banned_terms:
        assert term not in source
