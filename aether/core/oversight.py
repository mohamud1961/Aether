"""When the reviewer reviews the work, and what the model is told.

- finish: a claim-free advisory review, recorded without blocking the finish.
- progress: claim-free state reviews at fixed fractions of the time limit, so a wrong
  direction is visible while there is still time to act (finish-only review never fired
  on the long C1 rows, which ran out of time first).
- final: one review when the remaining time drops below FINAL_WINDOW, reporting what the
  reviewer cannot yet see in the state, so deliverables are put in final form.

All reviews are advisory; they never block anything. Every review,
including errors, is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Awaitable, Callable, Sequence

from .questionnaire import FAILURE_DETAILS
from .env import CONTROL_DIR, Environment
from .review import Transport, Verdict, review

FINISH_MIN_REMAINING_FRACTION = 0.15
FINISH_MIN_REMAINING_S = 90.0
FINAL_WINDOW_FRACTION = 0.10
FINAL_WINDOW_MIN_S = 120.0


@dataclass(frozen=True)
class ReviewPlan:
    finish: bool = True
    progress_at: tuple[float, ...] = ()  # fractions of the time limit
    final: bool = False


def _state_lines(v: Verdict) -> list[str]:
    if v.status == "error":
        return [
            f"Review unavailable: {v.reason}. No reviewer conclusion about the task was obtained."
        ]
    lines = [
        f"Its reading of the current state: {FAILURE_DETAILS.get(v.mode, v.mode)} "
        f"(confidence {v.confidence:.2f})."
    ]
    if v.unmet:
        lines.append("Requirements it cannot yet confirm from the real state:")
        lines += [f"- {u}" for u in v.unmet[:6]]
    if v.malfunction_line():
        lines.append(v.malfunction_line())
    return lines


def progress_feedback(v: Verdict, elapsed: float, timeout: float) -> str:
    return "\n".join(
        [
            f"[progress review at {elapsed:.0f}s of {timeout:.0f}s] An independent reviewer examined the workspace "
            "and your recent outputs (not your reasoning).",
            *_state_lines(v),
            "Use this to check your direction; it does not stop you.",
        ]
    )


def final_feedback(v: Verdict, remaining: float) -> str:
    return "\n".join(
        [
            f"[final review: about {remaining:.0f}s left] An independent reviewer examined the workspace.",
            *_state_lines(v),
            "Make sure every required deliverable exists now in its final form and location; then finish.",
        ]
    )


class Oversight:
    def __init__(
        self,
        plan: ReviewPlan,
        transport: Transport | None,
        call: Callable[..., Awaitable[Any]] | None,
        timeout_s: float,
        control_dir: str = CONTROL_DIR,
    ) -> None:
        self._control_dir = control_dir
        self.plan = (
            plan
            if transport is not None and call is not None
            else ReviewPlan(finish=False)
        )
        self._transport, self._call, self._timeout = transport, call, timeout_s
        self._done: set[str] = set()
        self.rows: list[dict[str, Any]] = []

    def due(self, elapsed: float, remaining: float) -> str | None:
        final_window = max(FINAL_WINDOW_MIN_S, FINAL_WINDOW_FRACTION * self._timeout)
        if (
            self.plan.final
            and "final" not in self._done
            and remaining <= final_window
            and remaining > 30
        ):
            return "final"
        for frac in self.plan.progress_at:
            key = f"progress@{frac:g}"
            if (
                key not in self._done
                and elapsed >= frac * self._timeout
                and remaining > final_window
            ):
                return key
        return None

    def finish_gate(self, remaining: float) -> str | None:
        """None if a finish review should run now; otherwise the reason it is skipped."""
        if not self.plan.finish:
            return "review_off"
        if remaining <= max(
            FINISH_MIN_REMAINING_S, FINISH_MIN_REMAINING_FRACTION * self._timeout
        ):
            return "low_time"
        return None

    async def run(
        self,
        kind: str,
        env: Environment,
        *,
        task: str,
        workdir: str,
        actions: Sequence[str],
        written: Sequence[str],
    ) -> tuple[Verdict, dict[str, Any]]:
        self._done.add(kind)
        t0 = time.monotonic()
        verdict = await review(
            self._transport,
            env,
            task=task,
            workdir=workdir,
            actions=actions,
            written=written,
            call=self._call,
            control_dir=self._control_dir,
        )
        row = {
            "kind": kind.split("@")[0],
            "at": kind,
            "status": verdict.status,
            "mode": verdict.mode,
            "confidence": verdict.confidence,
            "unmet": verdict.unmet,
            "verified": verdict.status == "pass" and not verdict.unmet,
            "reason": verdict.reason,
            "malfunction": verdict.malfunction,
            "malfunction_confidence": verdict.malfunction_confidence,
            "request_bytes": verdict.request_bytes,
            "latency_s": round(time.monotonic() - t0, 2),
        }
        self.rows.append(row)
        return verdict, row
