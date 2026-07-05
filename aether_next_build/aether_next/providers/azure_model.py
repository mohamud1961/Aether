"""Azure OpenAI model provider using the Responses API in background mode.

This is the ONLY module allowed to ``import openai``.  It builds a
``ModelCallable`` that the kernel's ``ModelHooks`` layer can consume.
"""
from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlparse

try:
    import openai
except ModuleNotFoundError:  # pragma: no cover - provider construction requires dependency.
    openai = None  # type: ignore[assignment]


class AzureModelError(Exception):
    """Raised when the Azure Responses API returns an unrecoverable error."""


def _normalize_endpoint(raw: str) -> str:
    """Strip a full Azure endpoint URL down to ``scheme://host``.

    The env var may be ``https://host/openai/responses?api-version=...``;
    the working call uses ``{host}/openai/v1/``.
    """
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value.rstrip("/")


def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Return (instructions, input_text) for the Responses API.

    Guarantees *input_text* is non-empty whenever there is any message
    content, because the Responses API requires a non-empty ``input``.

    Mapping rules:

    * ``role:system`` messages → ``instructions`` (joined with blank lines).
    * All other roles → ``input`` (joined with blank lines).
    * If ``input`` is empty but system messages exist, the **last** system
      message is promoted to ``input`` and the earlier ones stay in
      ``instructions``.  (In the solver flow the appended solver prompt is
      last — this keeps it as the actual ask while the prefix sections
      become standing context.)
    * A single system message with no other content goes entirely into
      ``input`` with a minimal generic instruction.
    * An empty *messages* list returns a safe fallback so the API never
      receives an empty ``input``.
    """
    system_parts: list[str] = []
    input_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            input_parts.append(content)

    instructions = "\n\n".join(system_parts)
    input_text = "\n\n".join(input_parts)

    if input_text:
        # Happy path: non-system messages produced input.
        return instructions or "You are a helpful assistant.", input_text

    if len(system_parts) > 1:
        # All-system case (the solver bug): promote the last system message
        # to input; the rest remain as instructions.
        return "\n\n".join(system_parts[:-1]), system_parts[-1]

    if len(system_parts) == 1:
        # Exactly one system message and nothing else.
        return "You are a helpful assistant.", system_parts[0]

    # No messages at all — return safe minimal values.
    return "You are a helpful assistant.", "Proceed."


def _extract_output_text(response: Any) -> str:
    """Pull the output text from a completed Responses API object."""
    # Prefer .output_text convenience accessor.
    try:
        text = response.output_text
        if text:
            return str(text)
    except (AttributeError, TypeError):
        pass
    # Fall back to walking the output items manually.
    for item in getattr(response, "output", None) or []:
        for chunk in getattr(item, "content", None) or []:
            piece = getattr(chunk, "text", None)
            if piece:
                return str(piece)
    return ""


def make_azure_callable(
    *,
    deployment_env: str,
    key_env: str,
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
    effort: str = "medium",
    poll_interval_s: float | None = None,
    poll_timeout_s: float | None = None,
) -> "AzureModelCallable":
    """Build a ``ModelCallable`` backed by an Azure OpenAI deployment.

    Env vars are read at *build time* (not per-call), so a missing var
    raises immediately rather than mid-run.

    The callable uses the Responses API in **background mode**: create
    with ``background=True``, then poll ``retrieve`` until the status
    leaves ``queued`` / ``in_progress``.  This avoids stream-hang issues
    on long generations while remaining correct for short solver turns.
    """
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    deployment = os.environ[deployment_env]
    api_key = os.environ[key_env]
    resolved_poll_interval_s = (
        float(os.environ.get("AETHER_MODEL_POLL_INTERVAL_S", "10"))
        if poll_interval_s is None
        else poll_interval_s
    )
    resolved_poll_timeout_s = (
        float(os.environ.get("AETHER_MODEL_POLL_TIMEOUT_S", "1200"))
        if poll_timeout_s is None
        else poll_timeout_s
    )

    if openai is None:
        raise AzureModelError("openai package is required for AzureModelCallable")
    client = openai.OpenAI(
        api_key=api_key,
        base_url=f"{endpoint}/openai/v1/",
        timeout=resolved_poll_timeout_s + 60,
        max_retries=2,
    )

    return AzureModelCallable(
        client=client,
        deployment=deployment,
        effort=effort,
        poll_interval_s=resolved_poll_interval_s,
        poll_timeout_s=resolved_poll_timeout_s,
    )


class AzureModelCallable:
    """A ``ModelCallable`` wrapping Azure OpenAI Responses API (background)."""

    def __init__(
        self,
        *,
        client: openai.OpenAI,
        deployment: str,
        effort: str,
        poll_interval_s: float,
        poll_timeout_s: float,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._effort = effort
        self._poll_interval_s = max(1.0, poll_interval_s)
        self._poll_timeout_s = max(30.0, poll_timeout_s)

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        """Send *messages* and return the model's output text.

        Maps the ``messages`` list (with ``role``/``content`` dicts) to the
        Responses API ``instructions`` + ``input`` parameters via
        :func:`_split_messages`, which guarantees a non-empty ``input``.
        """
        instructions, user_input = _split_messages(messages)

        try:
            job = self._client.responses.create(
                model=self._deployment,
                instructions=instructions,
                input=user_input,
                reasoning={"effort": self._effort},
                max_output_tokens=max_output_tokens,
                background=True,
            )
        except Exception as exc:
            raise AzureModelError(f"responses.create failed: {exc}") from exc

        job_id = getattr(job, "id", None)
        if not job_id:
            raise AzureModelError("responses.create returned no job id")

        # Poll until terminal status.
        elapsed = 0.0
        while getattr(job, "status", None) in ("queued", "in_progress"):
            if elapsed >= self._poll_timeout_s:
                raise AzureModelError(
                    f"background job {job_id} timed out after {elapsed:.0f}s "
                    f"(status={getattr(job, 'status', None)})"
                )
            time.sleep(self._poll_interval_s)
            elapsed += self._poll_interval_s
            try:
                job = self._client.responses.retrieve(job_id)
            except Exception as exc:
                raise AzureModelError(
                    f"responses.retrieve failed for {job_id}: {exc}"
                ) from exc

        status = getattr(job, "status", None)
        if status == "completed":
            text = _extract_output_text(job)
            if not text:
                raise AzureModelError(
                    f"background job {job_id} completed but produced no output text"
                )
            return text

        if status == "incomplete":
            # max_output_tokens or other soft limits: return partial text if
            # available so the caller's parser/fallback can handle it.
            partial = _extract_output_text(job)
            if partial:
                return partial
            detail = (
                getattr(job, "incomplete_details", None)
                or getattr(job, "error", None)
                or ""
            )
            raise AzureModelError(
                f"background job {job_id} incomplete with no usable text: {detail}"
            )

        # Any other terminal status (failed, expired, cancelled, …).
        detail = (
            getattr(job, "incomplete_details", None)
            or getattr(job, "error", None)
            or ""
        )
        raise AzureModelError(
            f"background job {job_id} ended with status={status}: {detail}"
        )
