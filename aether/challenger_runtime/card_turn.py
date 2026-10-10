"""One card turn with exactly one repair turn on a parse or validation error."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence, TypeVar

from .cards import CardError
from .state import FlowContext

T = TypeVar("T")

REPAIR_PROMPT = """\
Your card could not be used: {error}
Return the corrected card only, as ONE JSON object and nothing else. Required schema:
{schema}
"""


def obtain_card(
    fc: FlowContext, messages: Sequence[Mapping[str, Any]], prompt: str, label: str, schema: str,
    parse: Callable[[str], T],
) -> T:
    """Ask for the card; on CardError show the exact error and schema once, then parse again.

    A second failure raises the second CardError, which the controller degrades to control.
    """
    text = fc.ask_card_model(messages, prompt, label)
    fc.log.append("card_response", card=label, attempt=1, text=text)
    try:
        return parse(text)
    except CardError as first:
        fc.log.append("card_invalid", card=label, attempt=1, error=str(first))
        repair = REPAIR_PROMPT.format(error=first, schema=schema)
        extra = [{"role": "assistant", "content": text}, {"role": "user", "content": repair}]
        text = fc.ask_card_model(messages, prompt, label + " (corrected)", extra=extra)
        fc.log.append("card_response", card=label, attempt=2, text=text)
        try:
            return parse(text)
        except CardError as second:
            fc.log.append("card_invalid", card=label, attempt=2, error=str(second))
            raise
