"""
Gemini Adapter - google-genai SDK Wrapper

Wraps Google's genai SDK for Gemini 3 models.
Synthesizes call IDs deterministically (Gemini doesn't provide stable IDs).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import traceback
from multiprocessing import get_context
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
DEFAULT_EXPLICIT_CACHE_TTL = "3600s"


def _gemini_worker(payload: Dict[str, Any], queue) -> None:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        queue.put({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        return

    try:
        client = genai.Client(api_key=payload.get("api_key"))

        tool_declarations = []
        for tool in payload.get("tools", []):
            tool_declarations.append(types.FunctionDeclaration(
                name=tool.get("name"),
                description=tool.get("description", ""),
                parameters=tool.get("parameters"),
            ))

        tools_config = [types.Tool(function_declarations=tool_declarations)] if tool_declarations else None

        config_kwargs: Dict[str, Any] = {
            "tools": tools_config,
            "temperature": payload.get("temperature", 0.0),
            "max_output_tokens": payload.get("max_tokens", 4096),
        }
        cached_content_name = payload.get("cached_content_name")
        if cached_content_name:
            config_kwargs["cached_content"] = cached_content_name
        else:
            config_kwargs["system_instruction"] = payload.get("system_prompt") or None

        response = client.models.generate_content(
            model=payload.get("model"),
            contents=payload.get("contents"),
            config=types.GenerateContentConfig(**config_kwargs),
        )

        queue.put({"ok": True, "raw": _gemini_response_to_dict(response)})
    except Exception as exc:
        queue.put({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })


def _gemini_response_to_dict(response) -> Dict[str, Any]:
    candidates = []
    for candidate in response.candidates:
        parts = []
        parts_list = []
        if candidate.content and candidate.content.parts:
            parts_list = candidate.content.parts
        for part in parts_list:
            if hasattr(part, "text") and part.text:
                parts.append({"text": part.text})
            if hasattr(part, "function_call") and part.function_call:
                parts.append({
                    "functionCall": {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args) if part.function_call.args else {},
                    }
                })

        candidates.append({
            "content": {"parts": parts},
            "finishReason": str(getattr(candidate, "finish_reason", "STOP")),
        })

    usage_meta = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage_meta = {
            "promptTokenCount": getattr(response.usage_metadata, "prompt_token_count", 0),
            "candidatesTokenCount": getattr(response.usage_metadata, "candidates_token_count", 0),
        }

    return {
        "candidates": candidates,
        "usageMetadata": usage_meta,
    }


class GeminiAdapter(ModelAdapter):
    """
    Stateless adapter for Google Gemini models.
    
    Uses google-genai SDK. Synthesizes call IDs deterministically.
    """
    
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        api_key: Optional[str] = None,
        schema_translator: Optional[ToolSchemaTranslator] = None,
        timeout_seconds: Optional[float] = None,
    ):
        """
        Initialize Gemini adapter.
        
        Args:
            model: Gemini model identifier (e.g., gemini-3-flash-preview)
            api_key: API key (defaults to GOOGLE_API_KEY env var)
            schema_translator: Tool schema translator (creates default if None)
        """
        # Accept both "gemini-*" and "models/gemini-*" forms and normalize.
        self.model = model.removeprefix("models/")
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.schema_translator = schema_translator or ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.schema_translator)
        self.timeout_seconds = self._resolve_timeout(timeout_seconds)
        
        # Lazily import google.genai to avoid hard dependency
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            try:
                from google import genai
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. "
                    "Install with: pip install google-genai"
                )
            self._client = genai.Client(api_key=self.api_key)
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
        
        # Get Gemini-format tools
        tools = self.schema_translator.to_gemini_tools()
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
        Call Gemini API.
        
        Implements retry with deterministic backoff.
        """
        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is missing. Set GOOGLE_API_KEY before invoking GeminiAdapter."
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Gemini model name is empty.")
        if not self.model.startswith("gemini-"):
            raise ValueError(
                f"Unsupported Gemini model '{self.model}'. Expected a model like 'gemini-3-flash-preview'."
            )

        client = self._get_client()
        
        try:
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai package not installed")
        
        # Build API request
        contents = self._format_contents(request.messages)
        explicit_cached_content_name: Optional[str] = None
        send_contents = contents
        if request.cache_stable_prefix and self._explicit_cache_enabled():
            explicit_cached_content_name, send_contents = self._prepare_explicit_cache(
                client=client,
                types=types,
                request=request,
                contents=contents,
            )
        
        # Build tool config
        tool_declarations = []
        for tool in request.tools:
            tool_declarations.append(types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool.get("parameters"),
            ))
        
        tools_config = [types.Tool(function_declarations=tool_declarations)] if tool_declarations else None
        
        max_attempts = len(RETRY_DELAYS_SEC) + 1
        retry_delay_sec = 0.0
        last_error = None
        for attempt in range(max_attempts):
            if retry_delay_sec > 0:
                logger.info(
                    "Retry attempt %s after %.1fs delay",
                    attempt + 1,
                    retry_delay_sec,
                )
                time.sleep(retry_delay_sec)

            try:
                raw_dict = self._call_with_timeout(
                    client=client,
                    types=types,
                    contents=send_contents,
                    tools_config=tools_config,
                    request=request,
                    cached_content_name=explicit_cached_content_name,
                )
                
                # Convert to raw bytes for artifact storage
                raw_bytes = json.dumps(raw_dict, sort_keys=True).encode("utf-8")
                
                # Normalize response
                return self.normalizer.normalize_gemini(raw_bytes)
                
            except Exception as e:
                last_error = e
                # Check if retryable (rate limit, server error)
                if self._is_retryable(e) and attempt < (max_attempts - 1):
                    retry_delay_sec = self._compute_retry_delay(attempt=attempt, error=e)
                    continue
                raise
        
        # All retries exhausted
        raise last_error or RuntimeError("Gemini API call failed")

    def _resolve_timeout(self, timeout_seconds: Optional[float]) -> Optional[float]:
        if timeout_seconds is not None:
            return timeout_seconds
        env_value = os.getenv("GEMINI_TIMEOUT_SECONDS")
        if env_value is None or env_value.strip() == "":
            return 120.0
        try:
            return float(env_value)
        except ValueError:
            raise ValueError(f"Invalid GEMINI_TIMEOUT_SECONDS: {env_value}")

    def _call_with_timeout(
        self,
        *,
        client,
        types,
        contents: List[Dict[str, Any]],
        tools_config,
        request: ModelRequest,
        cached_content_name: Optional[str] = None,
    ):
        config_kwargs: Dict[str, Any] = {
            "tools": tools_config,
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        if cached_content_name:
            config_kwargs["cached_content"] = cached_content_name
        else:
            config_kwargs["system_instruction"] = request.system_prompt or None

        if self.timeout_seconds is None:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            return _gemini_response_to_dict(response)

        payload = {
            "api_key": self.api_key,
            "model": self.model,
            "contents": contents,
            "tools": request.tools,
            "system_prompt": request.system_prompt,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "cached_content_name": cached_content_name,
        }

        ctx = get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(
            target=_gemini_worker,
            args=(payload, queue),
        )
        proc.start()
        
        try:
            result = queue.get(timeout=self.timeout_seconds)
        except Exception:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
            raise TimeoutError(f"gemini_timeout_seconds={self.timeout_seconds}")

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)

        if not result.get("ok"):
            error_type = result.get("error_type", "RuntimeError")
            error_msg = result.get("error", "unknown")
            tb = result.get("traceback", "")
            raise RuntimeError(f"gemini_worker_error[{error_type}]: {error_msg}\n{tb}")

        return result["raw"]

    def _explicit_cache_enabled(self) -> bool:
        return os.getenv("GEMINI_EXPLICIT_CACHE", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _prepare_explicit_cache(
        self,
        *,
        client,
        types,
        request: ModelRequest,
        contents: List[Dict[str, Any]],
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        # Free-tier projects may not support explicit cache creation; this stays best-effort.
        stable_end = request.stable_prefix_end_index
        if stable_end < 0:
            return None, contents
        if stable_end >= len(contents):
            return None, contents
        stable_contents = contents[: stable_end + 1]
        live_contents = contents[stable_end + 1 :]
        if not stable_contents or not live_contents:
            return None, contents
        ttl = os.getenv("GEMINI_EXPLICIT_CACHE_TTL", DEFAULT_EXPLICIT_CACHE_TTL)
        try:
            cache = client.caches.create(
                model=self.model,
                config=types.CreateCachedContentConfig(
                    system_instruction=request.system_prompt or None,
                    contents=stable_contents,
                    ttl=ttl,
                ),
            )
        except Exception as exc:
            logger.warning(
                "Gemini explicit cache unavailable; falling back to implicit caching. error=%s",
                exc,
            )
            return None, contents
        cache_name = getattr(cache, "name", None)
        if not isinstance(cache_name, str) or not cache_name:
            logger.warning(
                "Gemini explicit cache did not return a cache name; falling back to implicit caching."
            )
            return None, contents
        return cache_name, live_contents
    
    def _extract_system_prompt(self, context_pack: "ContextPack") -> str:
        """Extract system prompt from ContextPack doctrine tier."""
        doctrine_items = context_pack.get_tier_items("DOCTRINE")
        if doctrine_items:
            return "\n\n".join(item.get("content", "") for item in doctrine_items)
        return ""
    
    def _extract_messages(self, context_pack: "ContextPack") -> List[Dict[str, Any]]:
        """Extract conversation messages from ContextPack."""
        conversation_items = context_pack.get_tier_items("CONVERSATION")
        messages = []
        for item in conversation_items:
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.append({"role": role, "content": content})
        return messages
    
    def _format_contents(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format messages for Gemini API."""
        # Gemini expects: [{"role": "user"|"model", "parts": [{"text": "..."}]}]
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Map "assistant" to "model" for Gemini
            if role == "assistant":
                role = "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}],
            })
        return contents

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
    
    def _response_to_dict(self, response) -> Dict[str, Any]:
        """Convert Gemini response to dictionary for serialization."""
        # Handle google-genai response object
        candidates = []
        for candidate in response.candidates:
            parts = []
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    parts.append({"text": part.text})
                if hasattr(part, "function_call") and part.function_call:
                    parts.append({
                        "functionCall": {
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        }
                    })
            
            candidates.append({
                "content": {"parts": parts},
                "finishReason": str(getattr(candidate, "finish_reason", "STOP")),
            })
        
        usage_meta = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage_meta = {
                "promptTokenCount": getattr(response.usage_metadata, "prompt_token_count", 0),
                "candidatesTokenCount": getattr(response.usage_metadata, "candidates_token_count", 0),
            }
        
        return {
            "candidates": candidates,
            "usageMetadata": usage_meta,
        }
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable (rate limit, server error)."""
        error_str = str(error).lower()
        non_retryable_indicators = [
            "api key",
            "permission denied",
            "unauthorized",
            "401",
            "403",
            "not found",
            "model not found",
        ]
        if any(indicator in error_str for indicator in non_retryable_indicators):
            return False

        retryable_indicators = [
            "rate_limit",
            "quota",
            "resource_exhausted",
            "429",
            "503",
            "500",
            "timeout",
            "deadline",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _compute_retry_delay(self, *, attempt: int, error: Exception) -> float:
        base_delay = RETRY_DELAYS_SEC[min(attempt, len(RETRY_DELAYS_SEC) - 1)]
        server_delay = self._extract_retry_delay_seconds(error)
        if server_delay is None:
            return base_delay
        return max(base_delay, server_delay)

    def _extract_retry_delay_seconds(self, error: Exception) -> Optional[float]:
        for candidate in self._iter_error_payload_candidates(error):
            delay = self._extract_retry_delay_from_candidate(candidate)
            if delay is not None:
                return delay
        return None

    def _iter_error_payload_candidates(self, error: Exception) -> List[Any]:
        candidates: List[Any] = [str(error), repr(error)]
        for arg in getattr(error, "args", ()):
            candidates.append(arg)
        for attr in ("response", "body", "error", "details", "message"):
            value = getattr(error, attr, None)
            if value is not None:
                candidates.append(value)
        response_obj = getattr(error, "response", None)
        if response_obj is not None:
            for attr in ("text", "content", "reason"):
                value = getattr(response_obj, attr, None)
                if value is not None:
                    candidates.append(value)
            json_method = getattr(response_obj, "json", None)
            if callable(json_method):
                try:
                    candidates.append(json_method())
                except Exception:
                    pass
        return candidates

    def _extract_retry_delay_from_candidate(self, candidate: Any) -> Optional[float]:
        if isinstance(candidate, (int, float)):
            return self._parse_retry_delay_value(candidate)
        if isinstance(candidate, bytes):
            return self._extract_retry_delay_from_candidate(candidate.decode("utf-8", errors="ignore"))
        if isinstance(candidate, dict):
            for key, value in candidate.items():
                key_l = str(key).lower()
                if key_l in {"retrydelay", "retry_delay", "retry-after", "retry_after"}:
                    parsed = self._parse_retry_delay_value(value)
                    if parsed is not None:
                        return parsed
                nested = self._extract_retry_delay_from_candidate(value)
                if nested is not None:
                    return nested
            return None
        if isinstance(candidate, list):
            for item in candidate:
                nested = self._extract_retry_delay_from_candidate(item)
                if nested is not None:
                    return nested
            return None
        if isinstance(candidate, str):
            stripped = candidate.strip()
            if not stripped:
                return None
            try:
                parsed_json = json.loads(stripped)
            except Exception:
                parsed_json = None
            if parsed_json is not None:
                nested = self._extract_retry_delay_from_candidate(parsed_json)
                if nested is not None:
                    return nested
            for pattern in (
                r'"retryDelay"\s*:\s*"?(?P<delay>[0-9]+(?:\.[0-9]+)?(?:ms|s)?)"?',
                r"retry(?:ing)?\s+(?:in|after)\s+(?P<delay>[0-9]+(?:\.[0-9]+)?)\s*s",
            ):
                match = re.search(pattern, stripped, flags=re.IGNORECASE)
                if not match:
                    continue
                parsed = self._parse_retry_delay_value(match.group("delay"))
                if parsed is not None:
                    return parsed
        return None

    def _parse_retry_delay_value(self, value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            delay = float(value)
            return delay if delay > 0 else None
        if not isinstance(value, str):
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        multiplier = 1.0
        if cleaned.endswith("ms"):
            cleaned = cleaned[:-2]
            multiplier = 0.001
        elif cleaned.endswith("s"):
            cleaned = cleaned[:-1]
        try:
            delay = float(cleaned) * multiplier
        except ValueError:
            return None
        return delay if delay > 0 else None


class MockGeminiAdapter(ModelAdapter):
    """
    Mock Gemini adapter for testing.
    
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
        return "mock-gemini"
    
    def format_context(self, context_pack: "ContextPack") -> ModelRequest:
        # Simplified version for testing
        return ModelRequest(
            system_prompt="test system",
            messages=[],
            tools=self.schema_translator.to_gemini_tools(),
            model_identifier="mock-gemini",
            max_tokens=4096,
            temperature=0.0,
        )
    
    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        
        if self.response_index >= len(self.responses):
            # Return empty response
            raw = json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": "No more mock responses"}]},
                    "finishReason": "STOP",
                }],
                "usageMetadata": {"promptTokenCount": 0, "candidatesTokenCount": 0},
            }).encode("utf-8")
        else:
            response_data = self.responses[self.response_index]
            self.response_index += 1
            raw = json.dumps(response_data).encode("utf-8")
        
        return self.normalizer.normalize_gemini(raw)
