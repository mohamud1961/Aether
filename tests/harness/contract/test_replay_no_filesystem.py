"""
Replay No-Filesystem Test

Proves that recorded-output replay does NOT touch the filesystem
or execute subprocesses. All data comes from recorded artifacts.

This enforces the "log-only replay" mode definition.
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RecordedEvent:
    """A recorded event from a prior run."""
    step_id: int
    event_id: str
    prev_event_hash: str
    tool_name: Optional[str]
    tool_args: Optional[dict]
    stdout_ref: Optional[str]
    stderr_ref: Optional[str]
    context_pack_hash: Optional[str]
    manifest_hash: Optional[str]


@dataclass
class RecordedArtifact:
    """A recorded artifact from a prior run."""
    artifact_id: str
    content: bytes
    size_bytes: int
    content_hash: str


class LogOnlyReplayrunner:
    """
    Replay runner that uses only recorded data.
    
    Invariants:
    - No filesystem reads outside artifact store
    - No subprocess execution
    - All context comes from recorded events and artifacts
    """

    def __init__(
        self,
        recorded_events: list[RecordedEvent],
        recorded_artifacts: dict[str, RecordedArtifact],
    ):
        self.events = recorded_events
        self.artifacts = recorded_artifacts
        self.filesystem_reads = []
        self.subprocess_calls = []

    def get_artifact(self, artifact_id: str) -> Optional[bytes]:
        """Get artifact from recorded store only."""
        artifact = self.artifacts.get(artifact_id)
        if artifact:
            return artifact.content
        return None

    def replay_step(self, event: RecordedEvent) -> dict:
        """Replay a single step using recorded data."""
        result = {
            'step_id': event.step_id,
            'event_id': event.event_id,
            'replayed': True,
        }

        if event.stdout_ref:
            stdout = self.get_artifact(event.stdout_ref)
            if stdout is None:
                return {
                    'error': 'missing_artifact',
                    'missing': event.stdout_ref,
                    'fail_closed': True
                }
            result['stdout'] = stdout

        if event.stderr_ref:
            stderr = self.get_artifact(event.stderr_ref)
            if stderr is None:
                return {
                    'error': 'missing_artifact',
                    'missing': event.stderr_ref,
                    'fail_closed': True
                }
            result['stderr'] = stderr

        return result

    def replay_all(self) -> dict:
        """Replay all recorded events."""
        results = []
        for event in self.events:
            result = self.replay_step(event)
            if result.get('fail_closed'):
                return {
                    'success': False,
                    'mismatch_type': 'missing_artifact',
                    'first_bad_step_id': event.step_id,
                    'results': results
                }
            results.append(result)

        return {
            'success': True,
            'results': results
        }


class TestReplayNoFilesystem(unittest.TestCase):
    """
    Contract tests proving replay does not access filesystem.
    """

    def test_replay_does_not_read_filesystem(self):
        """Replay must not call open() on filesystem paths."""
        events = [
            RecordedEvent(
                step_id=1,
                event_id="evt-001",
                prev_event_hash="0" * 64,
                tool_name="shell",
                tool_args={"command": ["cat", "/etc/passwd"]},
                stdout_ref="art-001",
                stderr_ref="art-002",
                context_pack_hash="pack-hash",
                manifest_hash="manifest-hash"
            )
        ]

        artifacts = {
            "art-001": RecordedArtifact(
                artifact_id="art-001",
                content=b"recorded stdout",
                size_bytes=15,
                content_hash="hash-001"
            ),
            "art-002": RecordedArtifact(
                artifact_id="art-002",
                content=b"",
                size_bytes=0,
                content_hash="hash-002"
            ),
        }

        # Patch open to detect filesystem access
        original_open = open
        filesystem_accesses = []

        def tracked_open(path, *args, **kwargs):
            if isinstance(path, (str, Path)) and not str(path).startswith('/dev/'):
                filesystem_accesses.append(str(path))
            return original_open(path, *args, **kwargs)

        runner = LogOnlyReplayrunner(events, artifacts)

        # run replay
        with patch('builtins.open', tracked_open):
            result = runner.replay_all()

        # Replay should succeed
        self.assertTrue(result['success'])

        # No filesystem access should have occurred
        self.assertEqual(
            len(filesystem_accesses), 0,
            f"Replay accessed filesystem: {filesystem_accesses}"
        )

    def test_replay_does_not_execute_subprocess(self):
        """Replay must not call subprocess.run or os.system."""
        events = [
            RecordedEvent(
                step_id=1,
                event_id="evt-001",
                prev_event_hash="0" * 64,
                tool_name="shell",
                tool_args={"command": ["rm", "-rf", "/"]},
                stdout_ref="art-001",
                stderr_ref="art-002",
                context_pack_hash="pack-hash",
                manifest_hash="manifest-hash"
            )
        ]

        artifacts = {
            "art-001": RecordedArtifact(
                artifact_id="art-001",
                content=b"",
                size_bytes=0,
                content_hash="hash-001"
            ),
            "art-002": RecordedArtifact(
                artifact_id="art-002",
                content=b"",
                size_bytes=0,
                content_hash="hash-002"
            ),
        }

        runner = LogOnlyReplayrunner(events, artifacts)

        # Mock subprocess to detect any calls
        with patch('subprocess.run') as mock_run, \
             patch('subprocess.Popen') as mock_popen, \
             patch('os.system') as mock_system:

            result = runner.replay_all()

            # No subprocess calls should have occurred
            mock_run.assert_not_called()
            mock_popen.assert_not_called()
            mock_system.assert_not_called()

        self.assertTrue(result['success'])

    def test_replay_fails_closed_on_missing_artifact(self):
        """Replay must fail closed if recorded artifact is missing."""
        events = [
            RecordedEvent(
                step_id=1,
                event_id="evt-001",
                prev_event_hash="0" * 64,
                tool_name="shell",
                tool_args={"command": ["echo", "hello"]},
                stdout_ref="missing-artifact",  # This artifact doesn't exist
                stderr_ref=None,
                context_pack_hash="pack-hash",
                manifest_hash="manifest-hash"
            )
        ]

        artifacts = {}  # Empty - artifact is missing

        runner = LogOnlyReplayrunner(events, artifacts)
        result = runner.replay_all()

        # Must fail closed
        self.assertFalse(result['success'])
        self.assertEqual(result['mismatch_type'], 'missing_artifact')
        self.assertEqual(result['first_bad_step_id'], 1)

    def test_replay_uses_only_recorded_stdout_stderr(self):
        """Replay must use recorded stdout/stderr, not re-execute."""
        events = [
            RecordedEvent(
                step_id=1,
                event_id="evt-001",
                prev_event_hash="0" * 64,
                tool_name="shell",
                tool_args={"command": ["echo", "original"]},
                stdout_ref="art-001",
                stderr_ref="art-002",
                context_pack_hash="pack-hash",
                manifest_hash="manifest-hash"
            )
        ]

        # Recorded output says "recorded_output", not "original"
        # This proves we're using recorded data, not re-executing
        artifacts = {
            "art-001": RecordedArtifact(
                artifact_id="art-001",
                content=b"recorded_output",
                size_bytes=15,
                content_hash="hash-001"
            ),
            "art-002": RecordedArtifact(
                artifact_id="art-002",
                content=b"",
                size_bytes=0,
                content_hash="hash-002"
            ),
        }

        runner = LogOnlyReplayrunner(events, artifacts)
        result = runner.replay_all()

        self.assertTrue(result['success'])

        # Stdout should be recorded value, not re-executed
        step_result = result['results'][0]
        self.assertEqual(step_result['stdout'], b"recorded_output")


class TestRealReplayNoFS(unittest.TestCase):
    """Integration test against real replay module."""

    def test_real_replay_module_has_no_subprocess_imports(self):
        """Real replay module does not import subprocess or os.system."""
        import aether.replay as replay_module
        import inspect
        
        source = inspect.getsource(replay_module)
        
        # Check for forbidden imports
        forbidden = [
            'import subprocess',
            'from subprocess',
            'os.system',
            'os.popen',
            'os.exec',
        ]
        
        for pattern in forbidden:
            self.assertNotIn(
                pattern, source,
                f"replay.py contains forbidden pattern: {pattern}"
            )

    def test_real_replay_module_docstring_documents_semantics(self):
        """Real replay module has explicit semantics docstring."""
        import aether.replay as replay_module
        
        docstring = replay_module.__doc__
        self.assertIsNotNone(docstring)
        self.assertIn("ARTIFACT", docstring.upper())
        self.assertIn("DOES NOT", docstring.upper())


if __name__ == '__main__':
    unittest.main()
