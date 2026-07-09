"""Azure OpenAI model provider using the Responses API in background mode.

This is the ONLY module allowed to ``import openai``.  It builds a
``ModelCallable`` that the kernel's ``ModelHooks`` layer can consume.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any, Callable
from urllib.parse import urlparse

from .model_retry import (
    DEFAULT_BACKOFF_BASE_S,
    DEFAULT_BACKOFF_CAP_S,
    DEFAULT_BACKOFF_MAX_TOTAL_S,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_RPM,
    RateLimiter,
    _retry_call,
    get_rate_limiter_for_deployment,
)

try:
    import openai
except ModuleNotFoundError:  # pragma: no cover - provider construction requires dependency.
    openai = None  # type: ignore[assignment]


class AzureModelError(Exception):
    """Raised when the Azure Responses API returns an unrecoverable error."""


# Background-job error codes (``job.error.code``, an openai
# ``ResponseError``) that represent a transient, Azure-side condition worth
# retrying. Every other code (invalid_prompt, image_*, vector_store_timeout,
# …) is a genuine request problem — retrying it just burns the retry budget
# on a call that will never succeed.
_RETRYABLE_JOB_ERROR_CODES = frozenset({"rate_limit_exceeded", "server_error"})


class _JobStatusFailure(Exception):
    """Internal marker: a background job reached a terminal failure status.

    Carries the job's ``error.code`` (e.g. ``"rate_limit_exceeded"``, per
    the ``ResponseError`` shape observed in the 15-agent batch rate-limit
    storm) so :func:`is_retryable_azure_error` can classify it without
    re-parsing the formatted error string. Raised only as the ``__cause__``
    of an :class:`AzureModelError` — never surfaced directly.
    """

    def __init__(self, code: str | None) -> None:
        super().__init__(code or "unknown")
        self.code = code


def is_retryable_azure_error(exc: BaseException) -> bool:
    """Classify an exception from a single Azure model-call attempt as transient.

    Transient (worth retrying): HTTP 429 (rate limit) or 5xx from the SDK,
    an SDK-level connection/timeout error, or a background job that ended
    with a retryable ``error.code`` (``rate_limit_exceeded`` /
    ``server_error``).

    Non-transient (must raise immediately): auth failures, bad requests,
    content filter rejections, and any other 4xx or unrecognized job error
    code. These will never succeed no matter how many times they're retried,
    so retrying them would only waste the retry budget and delay a real
    failure signal.

    Looks at ``exc.__cause__`` first because both HTTP-layer failures
    (``responses.create``/``responses.retrieve`` wrap the raw openai/httpx
    exception via ``raise AzureModelError(...) from exc``) and job-status
    failures (wrapped via ``from _JobStatusFailure(code)``) preserve the
    original signal there; falls back to *exc* itself for anything raised
    without a cause.
    """
    cause = exc.__cause__ if exc.__cause__ is not None else exc

    if isinstance(cause, _JobStatusFailure):
        return cause.code in _RETRYABLE_JOB_ERROR_CODES

    status_code = getattr(cause, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 429 or 500 <= status_code < 600

    # SDK connection/timeout errors carry no HTTP status at all but are
    # transient by nature (openai.APITimeoutError subclasses this too).
    if openai is not None and isinstance(cause, openai.APIConnectionError):
        return True

    return False


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
    max_retries: int | None = None,
    backoff_base_s: float | None = None,
    backoff_cap_s: float | None = None,
    backoff_max_total_s: float | None = None,
    max_rpm: float | None = None,
) -> "AzureModelCallable":
    """Build a ``ModelCallable`` backed by an Azure OpenAI deployment.

    Env vars are read at *build time* (not per-call), so a missing var
    raises immediately rather than mid-run.

    The callable uses the Responses API in **background mode**: create
    with ``background=True``, then poll ``retrieve`` until the status
    leaves ``queued`` / ``in_progress``.  This avoids stream-hang issues
    on long generations while remaining correct for short solver turns.

    Transient failures (HTTP 429/5xx, connection errors, or a background
    job that ends with a retryable error code) are retried in place with
    exponential backoff + jitter — see ``providers/model_retry.py``. Every
    retry/backoff knob below falls back to an ``AETHER_MODEL_*`` env var
    when left ``None``, matching the existing ``poll_interval_s`` /
    ``poll_timeout_s`` pattern, and every default preserves prior behavior
    at low volume (a handful of bounded retries) while an optional
    requests-per-minute gate (``max_rpm`` / ``AETHER_MODEL_MAX_RPM``,
    default unlimited) can pace bursts client-side.
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
    resolved_max_retries = (
        int(os.environ.get("AETHER_MODEL_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
        if max_retries is None
        else max_retries
    )
    resolved_backoff_base_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_BASE_S", str(DEFAULT_BACKOFF_BASE_S)))
        if backoff_base_s is None
        else backoff_base_s
    )
    resolved_backoff_cap_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_CAP_S", str(DEFAULT_BACKOFF_CAP_S)))
        if backoff_cap_s is None
        else backoff_cap_s
    )
    resolved_backoff_max_total_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_MAX_TOTAL_S", str(DEFAULT_BACKOFF_MAX_TOTAL_S)))
        if backoff_max_total_s is None
        else backoff_max_total_s
    )
    resolved_max_rpm = (
        float(os.environ.get("AETHER_MODEL_MAX_RPM", str(DEFAULT_MAX_RPM)))
        if max_rpm is None
        else max_rpm
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
        max_retries=resolved_max_retries,
        backoff_base_s=resolved_backoff_base_s,
        backoff_cap_s=resolved_backoff_cap_s,
        backoff_max_total_s=resolved_backoff_max_total_s,
        rate_limiter=get_rate_limiter_for_deployment(deployment, resolved_max_rpm),
    )


class AzureModelCallable:
    """A ``ModelCallable`` wrapping Azure OpenAI Responses API (background).

    Transient failures (HTTP 429/5xx, SDK connection errors, or a
    background job that ends with a retryable error code) are retried in
    place with exponential backoff + jitter via ``_retry_call`` — see
    :func:`is_retryable_azure_error` for the exact classification. Every
    other failure (auth, bad request, content filter, an unrecognized job
    error code) raises :class:`AzureModelError` on the first attempt with no
    retry.
    """

    def __init__(
        self,
        *,
        client: openai.OpenAI,
        deployment: str,
        effort: str,
        poll_interval_s: float,
        poll_timeout_s: float,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
        backoff_max_total_s: float | None = DEFAULT_BACKOFF_MAX_TOTAL_S,
        rate_limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._effort = effort
        self._poll_interval_s = max(1.0, poll_interval_s)
        self._poll_timeout_s = max(30.0, poll_timeout_s)
        self._max_retries = max(0, max_retries)
        self._backoff_base_s = max(0.0, backoff_base_s)
        self._backoff_cap_s = max(0.0, backoff_cap_s)
        self._backoff_max_total_s = backoff_max_total_s
        self._rate_limiter = rate_limiter
        # Injectable for tests only; production callers get real time.sleep
        # / random.random via the defaults above.
        self._retry_sleep = sleep
        self._rand = rand

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        """Send *messages* and return the model's output text.

        Maps the ``messages`` list (with ``role``/``content`` dicts) to the
        Responses API ``instructions`` + ``input`` parameters via
        :func:`_split_messages`, which guarantees a non-empty ``input``, then
        drives one create+poll attempt at a time through ``_retry_call``: a
        transient failure starts a fresh attempt (a new background job —
        a failed job cannot be resumed) after a bounded, jittered backoff;
        a non-transient failure or retry exhaustion propagates the same
        :class:`AzureModelError` a caller would see without retry at all.
        """
        instructions, user_input = _split_messages(messages)

        def _attempt() -> str:
            return self._call_once(instructions, user_input, max_output_tokens)

        return _retry_call(
            _attempt,
            is_retryable=is_retryable_azure_error,
            max_retries=self._max_retries,
            base_s=self._backoff_base_s,
            cap_s=self._backoff_cap_s,
            max_total_s=self._backoff_max_total_s,
            sleep=self._retry_sleep,
            rand=self._rand,
        )

    def _call_once(self, instructions: str, user_input: str, max_output_tokens: int) -> str:
        """Run exactly one create+poll attempt. Never retries internally —
        that's ``__call__``'s job via ``_retry_call``."""
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()

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

        # Any other terminal status (failed, expired, cancelled, …). Carry
        # the job's error code (if any) as the __cause__ so
        # is_retryable_azure_error can tell a transient Azure-side failure
        # (rate_limit_exceeded, server_error) from a genuine one.
        error_obj = getattr(job, "error", None)
        detail = error_obj or getattr(job, "incomplete_details", None) or ""
        code = getattr(error_obj, "code", None)
        raise AzureModelError(
            f"background job {job_id} ended with status={status}: {detail}"
        ) from _JobStatusFailure(code)


class AzureVisionCallable:
    """Vision transcription callable: (prompt, image_b64, media_type) -> text.

    Sends a multimodal Responses API request with an inline data-URL image.
    """

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    def __call__(self, prompt: str, image_b64: str, media_type: str) -> str:
        response = self._client.responses.create(
            model=self._deployment,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{media_type};base64,{image_b64}",
                    },
                ],
            }],
            max_output_tokens=8000,
        )
        return _extract_output_text(response)


def make_azure_vision_callable(
    *,
    deployment_env: str,
    key_env: str,
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
) -> AzureVisionCallable:
    """Build a vision transcription callable from Azure env vars (build-time)."""
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    api_key = os.environ[key_env]
    deployment = os.environ[deployment_env]
    if openai is None:
        raise AzureModelError("openai package is required for AzureVisionCallable")
    client = openai.OpenAI(
        api_key=api_key,
        base_url=f"{endpoint}/openai/v1/",
        timeout=300,
        max_retries=2,
    )
    return AzureVisionCallable(client, deployment)
