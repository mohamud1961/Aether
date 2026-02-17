"""
Claude Adapter - Stateless Messages API Wrapper

Wraps Anthropic's stateless Messages API (NOT SDK session objects).
Every call passes full context from ContextPack.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .model_adapter import ModelAdapter, ModelRequest, ModelResponse, NormalizedToolCall
from .response_normalizer import ResponseNormalizer, NormalizationError
from .tool_schema_translator import ToolSchemaTranslator

if TYPE_CHECKING:
    from .context_compiler import ContextPack


logger = logging.getLogger(__name__)

# Deterministic retry schedule (fixed delays for reproducibility)
RETRY_DELAYS_SEC = [1.0, 2.0, 4.0]
STABLE_SECTION_MARKERS = ("[CONTRACTS]", "[TASK]", "[EVIDENCE]")


class ClaudeAdapter(ModelAdapter):
    """
    Stateless adapter for Anthropic Claude models.
    
    Uses the raw Messages API, NOT agent/session objects.
    Every call is independent and receives full context.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        schema_translator: Optional[ToolSchemaTranslator] = None,
    ):
        """
        Initialize Claude adapter.
        
        Args:
            model: Claude model identifier
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
            schema_translator: Tool schema translator (creates default if None)
        """
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.schema_translator = schema_translator or ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.schema_translator)
        
        # Lazily import anthropic to avoid hard dependency
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client
    
    def get_model_identifier(self) -> str:
        """Return stable model identifier for logging."""
        return self.model
    
    def format_context(self, context_pack: "ContextPack") -> ModelRequest:
        """
        Convert ContextPack to ModelRequest.
        
        Must be deterministic: same context_pack → same request_bytes
        """
        # Extract system prompt from doctrine tier
        system_prompt = self._extract_system_prompt(context_pack)
        
        # Extract messages from conversation history
        messages = self._extract_messages(context_pack)
        
        # Get Claude-format tools
        tools = self.schema_translator.to_claude_tools()
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
        """
        Call Claude Messages API.
        
        Implements retry with deterministic backoff.
        """
        client = self._get_client()
        
        # Build API request
        api_messages = self._format_api_messages(request)
        
        last_error = None
        for attempt, delay in enumerate([0] + RETRY_DELAYS_SEC):
            if delay > 0:
                logger.info(f"Retry attempt {attempt + 1} after {delay}s delay")
                time.sleep(delay)
            
            try:
                response = client.messages.create(
                    model=self.model,
                    system=self._format_system_prompt(request),
                    messages=api_messages,
                    tools=request.tools,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )
                
                # Convert to bytes for artifact storage
                raw_bytes = response.model_dump_json().encode("utf-8")
                usage = getattr(response, "usage", None)
                cache_creation = self._safe_int(
                    getattr(usage, "cache_creation_input_tokens", None),
                    default=0,
                )
                cache_read = self._safe_int(
                    getattr(usage, "cache_read_input_tokens", None),
                    default=0,
                )
                
                # Normalize response
                normalized = self.normalizer.normalize_claude(raw_bytes)
                usage_payload = dict(normalized.usage) if isinstance(normalized.usage, dict) else {}
                usage_payload.setdefault("cache_creation_input_tokens", cache_creation)
                usage_payload.setdefault("cache_read_input_tokens", cache_read)
                cache_creation = self._safe_int(
                    usage_payload.get("cache_creation_input_tokens", cache_creation),
                    default=cache_creation,
                )
                cache_read = self._safe_int(
                    usage_payload.get("cache_read_input_tokens", cache_read),
                    default=cache_read,
                )
                usage_payload["cache_creation_tokens"] = cache_creation
                usage_payload["cache_read_tokens"] = cache_read
                return replace(
                    normalized,
                    usage=usage_payload,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                )
                
            except Exception as e:
                last_error = e
                # Check if retryable (rate limit, server error)
                if self._is_retryable(e):
                    continue
                raise
        
        # All retries exhausted
        raise last_error or RuntimeError("Claude API call failed")
    
    def _extract_system_prompt(self, context_pack: "ContextPack") -> str:
        """Extract system prompt from ContextPack doctrine tier."""
        # ContextPack has tiers: DOCTRINE, WORKSPACE, CONVERSATION, ARTIFACTS
        # System prompt comes from DOCTRINE tier items
        doctrine_items = context_pack.get_tier_items("DOCTRINE")
        if doctrine_items:
            return "\n\n".join(item.get("content", "") for item in doctrine_items)
        return ""
    
    def _extract_messages(self, context_pack: "ContextPack") -> List[Dict[str, Any]]:
        """Extract conversation messages from ContextPack."""
        # CONVERSATION tier contains the message history
        conversation_items = context_pack.get_tier_items("CONVERSATION")
        messages = []
        for item in conversation_items:
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.append({"role": role, "content": content})
        return messages
    
    def _format_system_prompt(self, request: ModelRequest) -> List[Dict[str, Any]]:
        # Apply cache_control on the system prompt block to guarantee the stable
        # prefix is always served from cache, independent of conversation growth.
        # This works in tandem with the top-level cache_control in invoke().
        content: Dict[str, Any] = {
            "type": "text",
            "text": request.system_prompt,
        }
        if request.cache_stable_prefix:
            content["cache_control"] = {"type": "ephemeral"}
        return [content]

    def _format_api_messages(self, request: ModelRequest) -> List[Dict[str, Any]]:
        """Format messages for Claude API."""
        # Claude expects: [{"role": "user"|"assistant", "content": str|list}]
        # Manual cache injection is removed in favor of top-level `cache_control`
        formatted = []
        for msg in request.messages:
            content = msg.get("content", "")
            formatted.append({
                "role": msg.get("role", "user"),
                "content": content,
            })
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
    def _safe_int(value: Any, *, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable (rate limit, server error)."""
        error_str = str(error).lower()
        retryable_indicators = [
            "rate_limit",
            "overloaded",
            "503",
            "529",
            "timeout",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)


class MockClaudeAdapter(ModelAdapter):
    """
    Mock Claude adapter for testing.
    
    Returns predetermined responses without calling the API.
    """
    
    def __init__(
        self,
        responses: List[Dict[str, Any]] | None = None,
        schema_translator: Optional[ToolSchemaTranslator] = None,
    ):
        self.responses = responses or []
        self.response_index = 0
        self.schema_translator = schema_translator or ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.schema_translator)
        self.calls: List[ModelRequest] = []
    
    def get_model_identifier(self) -> str:
        return "mock-claude"
    
    def format_context(self, context_pack: "ContextPack") -> ModelRequest:
        # Simplified version for testing
        return ModelRequest(
            system_prompt="test system",
            messages=[],
            tools=self.schema_translator.to_claude_tools(),
            model_identifier="mock-claude",
            max_tokens=4096,
            temperature=0.0,
        )
    
    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        
        if self.response_index >= len(self.responses):
            # Return empty response
            raw = json.dumps({
                "content": [{"type": "text", "text": "No more mock responses"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }).encode("utf-8")
        else:
            response_data = self.responses[self.response_index]
            self.response_index += 1
            raw = json.dumps(response_data).encode("utf-8")
        
        return self.normalizer.normalize_claude(raw)
