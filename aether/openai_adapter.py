"""
OpenAI Adapter - Stateless Chat Completions Wrapper

Wraps OpenAI Chat Completions API with deterministic request shaping and
normalization compatible with harness ModelAdapter contracts.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .model_adapter import ModelAdapter, ModelRequest, ModelResponse
from .response_normalizer import ResponseNormalizer
from .tool_schema_translator import ToolSchemaTranslator

if TYPE_CHECKING:
    from .context_compiler import ContextPack


logger = logging.getLogger(__name__)

# Deterministic retry schedule (fixed delays for reproducibility)
RETRY_DELAYS_SEC = [1.0, 2.0, 4.0]
STABLE_SECTION_MARKERS = ("[CONTRACTS]", "[TASK]", "[EVIDENCE]")


class OpenAIAdapter(ModelAdapter):
    """
    Stateless adapter for OpenAI Chat Completions models.
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        api_key: Optional[str] = None,
        schema_translator: Optional[ToolSchemaTranslator] = None,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.schema_translator = schema_translator or ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.schema_translator)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def get_model_identifier(self) -> str:
        return self.model

    def format_context(self, context_pack: "ContextPack") -> ModelRequest:
        system_prompt = self._extract_system_prompt(context_pack)
        messages = self._extract_messages(context_pack)
        tools = self.schema_translator.to_openai_tools()
        stable_prefix_end_index = self._infer_stable_prefix_end_index(
            messages,
            context_pack=context_pack,
        )
        return ModelRequest(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            model_identifier=self.model,
            max_tokens=4096,
            temperature=0.0,
            cache_stable_prefix=True,
            stable_prefix_end_index=stable_prefix_end_index,
        )

    def invoke(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Set OPENAI_API_KEY before invoking OpenAIAdapter."
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("OpenAI model name is empty.")

        client = self._get_client()
        api_messages = self._format_api_messages(request)
        tools = request.tools if request.tools else None

        last_error: Optional[Exception] = None
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS_SEC):
            if delay > 0:
                logger.info("Retry attempt %s after %.1fs delay", attempt + 1, delay)
                time.sleep(delay)
            try:
                response = self._create_completion(
                    client=client,
                    model=self.model,
                    messages=api_messages,
                    tools=tools,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                raw_dict = self._to_raw_dict(response)
                raw_bytes = json.dumps(raw_dict, sort_keys=True).encode("utf-8")
                normalized = self.normalizer.normalize_openai(raw_bytes)
                usage_payload = dict(normalized.usage) if isinstance(normalized.usage, dict) else {}
                cache_creation = self._safe_int(
                    usage_payload.get("cache_creation_tokens", usage_payload.get("cache_creation_input_tokens")),
                    default=0,
                )
                cache_read = self._safe_int(
                    usage_payload.get("cache_read_tokens", usage_payload.get("cache_read_input_tokens")),
                    default=0,
                )
                usage_payload["cache_creation_tokens"] = cache_creation
                usage_payload["cache_read_tokens"] = cache_read
                usage_payload["cache_creation_input_tokens"] = cache_creation
                usage_payload["cache_read_input_tokens"] = cache_read
                return replace(
                    normalized,
                    usage=usage_payload,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                )
            except Exception as exc:
                last_error = exc
                if self._is_retryable(exc):
                    continue
                raise

        raise last_error or RuntimeError("OpenAI API call failed")

    def _create_completion(
        self,
        *,
        client,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: int,
    ):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Prefer max_completion_tokens for modern models, with deterministic fallback.
        try:
            return client.chat.completions.create(
                **kwargs,
                max_completion_tokens=max_tokens,
            )
        except Exception as exc:
            if not self._is_max_completion_tokens_unsupported(exc):
                raise
            return client.chat.completions.create(
                **kwargs,
                max_tokens=max_tokens,
            )

    def _extract_system_prompt(self, context_pack: "ContextPack") -> str:
        doctrine_items = context_pack.get_tier_items("DOCTRINE")
        if doctrine_items:
            return "\n\n".join(item.get("content", "") for item in doctrine_items)
        return ""

    def _extract_messages(self, context_pack: "ContextPack") -> List[Dict[str, Any]]:
        conversation_items = context_pack.get_tier_items("CONVERSATION")
        messages = []
        for item in conversation_items:
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.append({"role": role, "content": content})
        return messages

    def _format_api_messages(self, request: ModelRequest) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        if request.system_prompt:
            formatted.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            formatted.append(
                {
                    "role": msg.get("role", "user"),
                    "content": content,
                }
            )
        return formatted

    def _infer_stable_prefix_end_index(
        self,
        messages: List[Dict[str, Any]],
        *,
        context_pack: Optional["ContextPack"] = None,
    ) -> int:
        if not messages:
            return -1
        first_content = messages[0].get("content", "")
        if not isinstance(first_content, str) or not first_content:
            return -1
        stable_prefix_bytes = getattr(context_pack, "stable_prefix_bytes", None)
        if isinstance(stable_prefix_bytes, (bytes, bytearray)):
            try:
                stable_prefix_text = bytes(stable_prefix_bytes).decode("utf-8")
            except Exception:
                stable_prefix_text = ""
            if stable_prefix_text and first_content == stable_prefix_text:
                return 0
        if any(marker in first_content for marker in STABLE_SECTION_MARKERS):
            return 0
        return -1

    @staticmethod
    def _to_raw_dict(response: Any) -> Dict[str, Any]:
        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
            if isinstance(dumped, dict):
                return dumped
        if hasattr(response, "to_dict"):
            dumped = response.to_dict()
            if isinstance(dumped, dict):
                return dumped
        if hasattr(response, "model_dump_json"):
            raw_json = response.model_dump_json()
            if isinstance(raw_json, str):
                return json.loads(raw_json)
        raise RuntimeError("OpenAI response object could not be converted to dict")

    @staticmethod
    def _safe_int(value: Any, *, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def _is_retryable(self, error: Exception) -> bool:
        error_str = str(error).lower()
        non_retryable_indicators = [
            "api key",
            "authentication",
            "unauthorized",
            "permission",
            "invalid_request_error",
            "unsupported",
            "not found",
            "400",
            "401",
            "403",
            "404",
        ]
        if any(indicator in error_str for indicator in non_retryable_indicators):
            return False
        retryable_indicators = [
            "rate limit",
            "429",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "connection",
            "temporarily unavailable",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _is_max_completion_tokens_unsupported(self, error: Exception) -> bool:
        error_str = str(error).lower()
        return (
            "max_completion_tokens" in error_str
            and (
                "unknown" in error_str
                or "unexpected" in error_str
                or "unsupported" in error_str
                or "extra fields" in error_str
            )
        )
