"""
MAD-003: Response Normalizer

Strict, fail-closed parsing of model responses into canonical format.
- Multi-candidate: use index 0, log warning
- Tool call ordering: preserve deterministically
- Call ID synthesis: hash(canonical_json + index) for Gemini
- validation: fail closed on schema violations
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .model_adapter import ModelResponse, NormalizedToolCall
from .tool_schema_translator import ToolSchemaTranslator


class NormalizationError(Exception):
    """Raised when response cannot be parsed or validated."""
    pass


class ResponseNormalizer:
    """
    Normalizes model responses to canonical format.
    Strict, deterministic, fail-closed.
    """
    
    def __init__(self, schema_translator: ToolSchemaTranslator):
        self.schema_translator = schema_translator
    
    def normalize_claude(self, raw_bytes: bytes) -> ModelResponse:
        """
        Parse Claude (Anthropic) response.
        
        Expected format:
        {
            "content": [
                {"type": "text", "text": "..."},
                {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            ],
            "stop_reason": "tool_use" | "end_turn",
            "usage": {"input_tokens": N, "output_tokens": N}
        }
        """
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        warnings: List[str] = []
        
        try:
            data = json.loads(raw_bytes)
        except json.JSONDecodeError as e:
            raise NormalizationError(f"Invalid JSON in Claude response: {e}")
        
        content_blocks = data.get("content", [])
        stop_reason = data.get("stop_reason", "unknown")
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        cache_creation_tokens = self._to_int(
            usage.get("cache_creation_tokens", usage.get("cache_creation_input_tokens")),
            default=0,
        )
        cache_read_tokens = self._to_int(
            usage.get("cache_read_tokens", usage.get("cache_read_input_tokens")),
            default=0,
        )
        
        tool_calls: List[NormalizedToolCall] = []
        text_content: Optional[str] = None
        
        for idx, block in enumerate(content_blocks):
            block_type = block.get("type")
            
            if block_type == "text":
                text_content = block.get("text", "")
                
            elif block_type == "tool_use":
                tool_name = block.get("name")
                tool_args = block.get("input", {})
                call_id = block.get("id", self._synthesize_call_id(tool_name, tool_args, idx))
                
                # Validate against schema
                try:
                    self.schema_translator.validate_tool_call(tool_name, tool_args)
                except ValueError as e:
                    raise NormalizationError(f"Tool validation failed: {e}")
                
                tool_calls.append(NormalizedToolCall(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    call_id=call_id,
                    index=len(tool_calls),
                ))
        
        # If we have both text and tool calls, tool calls win (text logged but not acted on)
        if text_content and tool_calls:
            warnings.append("Text content present alongside tool calls; text ignored for action")
        
        return ModelResponse(
            raw_bytes=raw_bytes,
            raw_hash=raw_hash,
            tool_calls=tool_calls,
            text_content=text_content,
            finish_reason=stop_reason,
            usage=usage,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            candidate_count=1,
            normalization_warnings=warnings,
        )
    
    def normalize_gemini(self, raw_bytes: bytes) -> ModelResponse:
        """
        Parse Gemini (Google) response.
        
        Expected format (google-genai SDK):
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "..."},
                            {"functionCall": {"name": "...", "args": {...}}}
                        ]
                    },
                    "finishReason": "STOP" | "TOOL_CALLS"
                }
            ],
            "usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": N}
        }
        """
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        warnings: List[str] = []
        
        try:
            data = json.loads(raw_bytes)
        except json.JSONDecodeError as e:
            raise NormalizationError(f"Invalid JSON in Gemini response: {e}")
        
        candidates = data.get("candidates", [])
        usage_meta = data.get("usageMetadata", {})
        
        if not candidates:
            raise NormalizationError("No candidates in Gemini response")
        
        # Use index 0 only for multi-candidate
        candidate_count = len(candidates)
        if candidate_count > 1:
            warnings.append(f"Multi-candidate response ({candidate_count}); using index 0")
        
        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        finish_reason = candidate.get("finishReason", "unknown")
        
        tool_calls: List[NormalizedToolCall] = []
        text_content: Optional[str] = None
        
        for idx, part in enumerate(parts):
            if "text" in part:
                text_content = part["text"]
                
            elif "functionCall" in part:
                func_call = part["functionCall"]
                tool_name = func_call.get("name")
                tool_args = func_call.get("args", {})
                
                # Gemini doesn't provide stable call ID, synthesize deterministically
                call_id = self._synthesize_call_id(tool_name, tool_args, idx)
                
                # Validate against schema
                try:
                    self.schema_translator.validate_tool_call(tool_name, tool_args)
                except ValueError as e:
                    raise NormalizationError(f"Tool validation failed: {e}")
                
                tool_calls.append(NormalizedToolCall(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    call_id=call_id,
                    index=len(tool_calls),
                ))
        
        # If we have both text and tool calls, tool calls win
        if text_content and tool_calls:
            warnings.append("Text content present alongside tool calls; text ignored for action")
        
        # Convert usage metadata
        usage = {
            "input_tokens": usage_meta.get("promptTokenCount", 0),
            "output_tokens": usage_meta.get("candidatesTokenCount", 0),
        }
        cache_read_tokens = self._to_int(usage_meta.get("cachedContentTokenCount"), default=0)
        
        return ModelResponse(
            raw_bytes=raw_bytes,
            raw_hash=raw_hash,
            tool_calls=tool_calls,
            text_content=text_content,
            finish_reason=finish_reason,
            usage=usage,
            cache_creation_tokens=0,
            cache_read_tokens=cache_read_tokens,
            candidate_count=candidate_count,
            normalization_warnings=warnings,
        )

    def normalize_openai(self, raw_bytes: bytes) -> ModelResponse:
        """
        Parse OpenAI Chat Completions response.

        Expected format:
        {
            "choices": [
                {
                    "message": {
                        "content": "...",
                        "tool_calls": [
                            {
                                "id": "call_...",
                                "type": "function",
                                "function": {"name": "...", "arguments": "{\"k\":\"v\"}"}
                            }
                        ]
                    },
                    "finish_reason": "tool_calls" | "stop"
                }
            ],
            "usage": {
                "prompt_tokens": N,
                "completion_tokens": N,
                "prompt_tokens_details": {"cached_tokens": N}
            }
        }
        """
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        warnings: List[str] = []

        try:
            data = json.loads(raw_bytes)
        except json.JSONDecodeError as e:
            raise NormalizationError(f"Invalid JSON in OpenAI response: {e}")

        choices = data.get("choices", [])
        if not choices:
            raise NormalizationError("No choices in OpenAI response")

        candidate_count = len(choices)
        if candidate_count > 1:
            warnings.append(f"Multi-candidate response ({candidate_count}); using index 0")

        choice = choices[0]
        message = choice.get("message", {}) if isinstance(choice.get("message", {}), dict) else {}
        finish_reason = str(choice.get("finish_reason", "unknown"))

        text_content = self._extract_openai_text_content(message.get("content"))
        tool_calls: List[NormalizedToolCall] = []

        for idx, tool_entry in enumerate(message.get("tool_calls", [])):
            if not isinstance(tool_entry, dict):
                raise NormalizationError("Invalid OpenAI tool call payload (expected object)")
            function_payload = (
                tool_entry.get("function", {})
                if isinstance(tool_entry.get("function", {}), dict)
                else {}
            )
            tool_name = function_payload.get("name")
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise NormalizationError("OpenAI tool call missing function.name")

            tool_args = self._parse_openai_tool_args(function_payload.get("arguments", "{}"))
            call_id = str(
                tool_entry.get("id")
                or self._synthesize_call_id(tool_name, tool_args, idx)
            )

            try:
                self.schema_translator.validate_tool_call(tool_name, tool_args)
            except ValueError as e:
                raise NormalizationError(f"Tool validation failed: {e}")

            tool_calls.append(
                NormalizedToolCall(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    call_id=call_id,
                    index=len(tool_calls),
                )
            )

        if text_content and tool_calls:
            warnings.append("Text content present alongside tool calls; text ignored for action")

        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        prompt_details = usage.get("prompt_tokens_details", {})
        if not isinstance(prompt_details, dict):
            prompt_details = {}

        input_tokens = self._to_int(
            usage.get("input_tokens", usage.get("prompt_tokens")),
            default=0,
        )
        output_tokens = self._to_int(
            usage.get("output_tokens", usage.get("completion_tokens")),
            default=0,
        )
        cache_creation_tokens = self._to_int(
            usage.get("cache_creation_tokens", usage.get("cache_creation_input_tokens")),
            default=0,
        )
        cache_read_tokens = self._to_int(
            prompt_details.get(
                "cached_tokens",
                usage.get("cache_read_tokens", usage.get("cache_read_input_tokens")),
            ),
            default=0,
        )

        usage_payload = dict(usage)
        usage_payload["input_tokens"] = input_tokens
        usage_payload["output_tokens"] = output_tokens
        usage_payload["cache_creation_tokens"] = cache_creation_tokens
        usage_payload["cache_read_tokens"] = cache_read_tokens
        usage_payload["cache_creation_input_tokens"] = cache_creation_tokens
        usage_payload["cache_read_input_tokens"] = cache_read_tokens

        return ModelResponse(
            raw_bytes=raw_bytes,
            raw_hash=raw_hash,
            tool_calls=tool_calls,
            text_content=text_content,
            finish_reason=finish_reason,
            usage=usage_payload,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            candidate_count=candidate_count,
            normalization_warnings=warnings,
        )
    
    def normalize_responses_api(self, raw_bytes: bytes) -> ModelResponse:
        """
        Parse OpenAI Responses API response (used by Codex OAuth backend).

        Expected format:
        {
            "id": "resp_...",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "..."},
                        {"type": "tool_use", "id": "...", "name": "...", "input": "..."}
                    ]
                },
                {
                    "type": "function_call",
                    "id": "fc_...",
                    "name": "...",
                    "arguments": "{...}"
                }
            ],
            "status": "completed",
            "usage": {
                "input_tokens": N,
                "output_tokens": N
            }
        }
        """
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        warnings: List[str] = []

        try:
            data = json.loads(raw_bytes)
        except json.JSONDecodeError as e:
            raise NormalizationError(f"Invalid JSON in Responses API response: {e}")

        output_items = data.get("output", [])
        status = str(data.get("status", "unknown"))
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}

        tool_calls: List[NormalizedToolCall] = []
        text_content: Optional[str] = None

        for item in output_items:
            item_type = item.get("type", "")

            # Top-level function_call items
            if item_type == "function_call":
                tool_name = item.get("name")
                if not isinstance(tool_name, str) or not tool_name.strip():
                    raise NormalizationError(
                        "Responses API function_call missing name"
                    )
                tool_args = self._parse_openai_tool_args(
                    item.get("arguments", "{}")
                )
                call_id = str(
                    item.get("call_id")
                    or item.get("id")
                    or self._synthesize_call_id(
                        tool_name, tool_args, len(tool_calls)
                    )
                )
                try:
                    self.schema_translator.validate_tool_call(
                        tool_name, tool_args
                    )
                except ValueError as e:
                    raise NormalizationError(
                        f"Tool validation failed: {e}"
                    )
                tool_calls.append(
                    NormalizedToolCall(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        call_id=call_id,
                        index=len(tool_calls),
                    )
                )

            # Message items contain content blocks
            elif item_type == "message":
                for block in item.get("content", []):
                    block_type = block.get("type", "")
                    if block_type == "output_text":
                        block_text = block.get("text", "")
                        if block_text:
                            text_content = (
                                (text_content + "\n" + block_text)
                                if text_content
                                else block_text
                            )
                    elif block_type in ("text",):
                        block_text = block.get("text", "")
                        if block_text:
                            text_content = (
                                (text_content + "\n" + block_text)
                                if text_content
                                else block_text
                            )

        if text_content and tool_calls:
            warnings.append(
                "Text content present alongside tool calls; text ignored for action"
            )

        # Map status to finish_reason
        finish_reason_map = {
            "completed": "stop",
            "incomplete": "length",
            "failed": "error",
        }
        finish_reason = finish_reason_map.get(status, status)
        if tool_calls and finish_reason == "stop":
            finish_reason = "tool_calls"

        input_tokens = self._to_int(
            usage.get("input_tokens"), default=0
        )
        output_tokens = self._to_int(
            usage.get("output_tokens"), default=0
        )

        usage_payload = dict(usage)
        usage_payload["input_tokens"] = input_tokens
        usage_payload["output_tokens"] = output_tokens

        return ModelResponse(
            raw_bytes=raw_bytes,
            raw_hash=raw_hash,
            tool_calls=tool_calls,
            text_content=text_content,
            finish_reason=finish_reason,
            usage=usage_payload,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            candidate_count=1,
            normalization_warnings=warnings,
        )

    def normalize(self, raw_bytes: bytes, model_type: str) -> ModelResponse:
        """
        Normalize response based on model type.
        
        Args:
            raw_bytes: Raw response bytes
            model_type: "claude", "gemini", "openai", or "codex_oauth"
        
        Returns:
            ModelResponse with normalized tool calls
        
        Raises:
            NormalizationError: If parsing or validation fails
        """
        if model_type == "claude":
            return self.normalize_claude(raw_bytes)
        elif model_type == "gemini":
            return self.normalize_gemini(raw_bytes)
        elif model_type == "openai":
            return self.normalize_openai(raw_bytes)
        elif model_type == "codex_oauth":
            return self.normalize_responses_api(raw_bytes)
        else:
            raise NormalizationError(f"Unknown model type: {model_type}")
    
    def _synthesize_call_id(self, tool_name: str, tool_args: Dict[str, Any], index: int) -> str:
        """
        Synthesize deterministic call ID for models that don't provide one.
        
        Uses: sha256(canonical_json(call) + str(index))[:16]
        """
        canonical = json.dumps(
            {"name": tool_name, "args": tool_args, "index": index},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @staticmethod
    def _to_int(value: Any, *, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_openai_text_content(content: Any) -> Optional[str]:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
            if parts:
                return "\n".join(parts)
        return None

    @staticmethod
    def _parse_openai_tool_args(raw_args: Any) -> Dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError as exc:
                raise NormalizationError(f"Invalid OpenAI function arguments JSON: {exc}") from exc
            if isinstance(parsed, dict):
                return parsed
            raise NormalizationError("OpenAI function arguments must decode to an object")
        raise NormalizationError("OpenAI function arguments must be string or object")
