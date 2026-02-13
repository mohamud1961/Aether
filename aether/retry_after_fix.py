from dataclasses import dataclass
from typing import Dict, Optional, Set

@dataclass
class RetryState:
    retried_events: Set[str]
    executed_plans: Set[str]

    def __init__(self):
        self.retried_events = set()
        self.executed_plans = set()

    def can_retry(self, failure_event_id: str, plan_signature: str) -> bool:
        if failure_event_id in self.retried_events:
            return False
        if plan_signature in self.executed_plans:
            return False
        return True

    def mark_retried(self, failure_event_id: str, plan_signature: str) -> None:
        self.retried_events.add(failure_event_id)
        self.executed_plans.add(plan_signature)
