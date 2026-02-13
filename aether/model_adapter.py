"""
MAD-001: Model Adapter Abstract Interface

Stateless contract for model adapters. All adapters must:
1. Be stateless - every call passes full message list from ContextPack
2. Log both request artifact (bytes + hash) and response artifact (bytes + hash)
3. Use identical request for identical ContextPack (golden serialization)
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .context_compiler import ContextPack


@dataclass(frozen=True)
class NormalizedToolCall:
    """Canonical tool call extracted from model response."""
    tool_name: str
    tool_args: Dict[str, Any]
    call_id: str  # Anthropic: from API; Gemini: synthesized from hash
    index: int    # Position in response


@dataclass(frozen=True)
class ModelRequest:
    """
    Canonical request format.
    Logged as artifact for audit and replay disputes.
    """
    system_prompt: str
    messages: List[Dict[str, Any]]
    tools: List[Dict[str, Any]]
    model_identifier: str
    max_tokens: int = 4096
    temperature: float = 0.0
    cache_stable_prefix: bool = True
    stable_prefix_end_index: int = -1
    
    @property
    def request_bytes(self) -> bytes:
        """Deterministic serialization of request."""
        payload = {
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "tools": self.tools,
            "model_identifier": self.model_identifier,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "cache_stable_prefix": self.cache_stable_prefix,
            "stable_prefix_end_index": self.stable_prefix_end_index,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    
    @property
    def request_hash(self) -> str:
        """SHA256 of request_bytes for logging."""
        return hashlib.sha256(self.request_bytes).hexdigest()


@dataclass
class ModelResponse:
    """
    Parsed model response.
    Raw bytes logged as artifact for audit.
    """
    raw_bytes: bytes
    raw_hash: str
    tool_calls: List[NormalizedToolCall]
    text_content: Optional[str]
    finish_reason: str
    usage: Dict[str, int] = field(default_factory=dict)
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    candidate_count: int = 1
    normalization_warnings: List[str] = field(default_factory=list)


class ModelAdapter(ABC):
    """
    Abstract base class for model adapters.
    
    All implementations must be stateless:
    - Every call receives full context from ContextPack
    - No reliance on SDK session/conversation state
    - Identical ContextPack must produce identical ModelRequest
    """
    
    @abstractmethod
    def format_context(self, context_pack: "ContextPack") -> ModelRequest:
        """
        Convert harness ContextPack to model-specific request.
        
        Must be deterministic: same context_pack → same request_bytes
        """
        pass
    
    @abstractmethod
    def invoke(self, request: ModelRequest) -> ModelResponse:
        """
        Call the model API and return parsed response.
        
        Must:
        - Log request artifact before calling
        - Log response artifact after calling
        - Apply retry with deterministic backoff on transient errors
        """
        pass
    
    @abstractmethod
    def get_model_identifier(self) -> str:
        """Return stable model identifier for logging (e.g., 'gemini-3.0-flash')."""
        pass
    
    def validate_statelessness(self, context_pack: "ContextPack") -> bool:
        """
        Verify adapter produces identical requests for identical input.
        Used in contract tests.
        """
        req1 = self.format_context(context_pack)
        req2 = self.format_context(context_pack)
        return req1.request_hash == req2.request_hash
