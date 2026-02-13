from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from .event_log import EventLog
from .hash_chain import verify_event_chain
from .policy_config import PolicyConfig

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class RecoveryResult:
    events: List[Dict[str, Any]]
    last_step_id: int
    last_fingerprint_hash: Optional[str]
    last_working_directory: Optional[str]

class SessionRecovery:
    """
    PRM-011: Session Recovery.
    Verifies event stream integrity and restores harness state.
    """
    def __init__(self, policy: PolicyConfig) -> None:
        self.policy = policy

    def recover(self, event_log_path: Path) -> RecoveryResult:
        if not event_log_path.exists():
            return RecoveryResult([], 0, None, None)

        if not self.policy.feature_flags.ff_session_recovery:
             # If disabled, maybe return empty? Or just load without verify?
             # Spec says fail closed if integrity check required?
             # But if FF disabled, we might skip recovery or skip verification?
             # Usually FF implies we DO NOT recover (start fresh/overwrite).
             # But if the file exists, we might overwrite it if we don't recover.
             # Let's assume FF=False means "Don't recover, treat as new session".
             # But caller checks this. Here we verify if asked.
             # Actually, if FF is False, we shouldn't be called? 
             # Or we return "No Recovery".
             logger.warning("Session recovery disabled by feature flag.")
             return RecoveryResult([], 0, None, None)

        events = EventLog.load_events(event_log_path)
        if not events:
            return RecoveryResult([], 0, None, None)

        # Verify Integrity
        report = verify_event_chain(events)
        if not report["ok"]:
            raise IntegrityError(
                f"Event log integrity check failed: {report['reason_code']} at index {report['failure_index']}",
                report=report
            )

        # Extract State
        last_event = events[-1]
        last_step_id = last_event.get("step_id", 0)
        last_cwd = last_event.get("cwd")
        
        # Find last fingerprint
        last_fp = None
        for e in reversed(events):
            if "workspace_fingerprint_hash" in e and e["workspace_fingerprint_hash"]:
                last_fp = e["workspace_fingerprint_hash"]
                break
        
        return RecoveryResult(
            events=events,
            last_step_id=last_step_id,
            last_fingerprint_hash=last_fp,
            last_working_directory=last_cwd
        )

    def recover_and_hydrate(self, event_log: EventLog) -> RecoveryResult:
        result = self.recover(event_log.path)
        if result.events:
            event_log.hydrate(result.events)
        return result

class IntegrityError(Exception):
    def __init__(self, message: str, report: Dict[str, Any]) -> None:
        super().__init__(message)
        self.report = report
