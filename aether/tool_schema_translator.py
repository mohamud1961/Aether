"""
MAD-002: Tool Schema Translator

Converts ToolGateway registry to model-specific tool formats.
Single source of truth: ToolGateway's tool definitions.
Never hardcodes tool definitions.
"""
from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING
import json

from .tool_gateway import (
    APPLY_PATCH_TOOL_DEFINITION,
    DIFF_FILES_TOOL_DEFINITION,
    LIST_DIR_TOOL_DEFINITION,
    PIPELINE_RUN_TOOL_DEFINITION,
    READ_FILE_TOOL_DEFINITION,
    REQUEST_PHASE_TRANSITION_DEFINITION,
    RUN_TOOL_DEFINITION,
    SEARCH_FILES_TOOL_DEFINITION,
    STAT_PATHS_TOOL_DEFINITION,
    WRITE_FILE_TOOL_DEFINITION,
)

if TYPE_CHECKING:
    from .tool_gateway import ToolGateway


# harness canonical tool definitions
# These are the tools our harness supports - defined here as the reference
# The translator reads from this registry (or ToolGateway can expose it)
harness_TOOL_REGISTRY: List[Dict[str, Any]] = [
    json.loads(json.dumps(RUN_TOOL_DEFINITION)),
    json.loads(json.dumps(READ_FILE_TOOL_DEFINITION)),
    json.loads(json.dumps(WRITE_FILE_TOOL_DEFINITION)),
    json.loads(json.dumps(SEARCH_FILES_TOOL_DEFINITION)),
    json.loads(json.dumps(LIST_DIR_TOOL_DEFINITION)),
    json.loads(json.dumps(STAT_PATHS_TOOL_DEFINITION)),
    json.loads(json.dumps(DIFF_FILES_TOOL_DEFINITION)),
    json.loads(json.dumps(APPLY_PATCH_TOOL_DEFINITION)),
    json.loads(json.dumps(PIPELINE_RUN_TOOL_DEFINITION)),
    json.loads(json.dumps(REQUEST_PHASE_TRANSITION_DEFINITION)),
]


class ToolSchemaTranslator:
    """
    Translates harness tool definitions to model-specific formats.
    
    Anthropic (Claude) format:
    - tools: [{name, description, input_schema: {type, properties, required}}]
    
    Google (Gemini) format:
    - function_declarations: [{name, description, parameters: {type, properties, required}}]
    """
    
    def __init__(self, tool_registry: List[Dict[str, Any]] | None = None):
        """
        Initialize with tool registry.
        
        Args:
            tool_registry: List of harness tool definitions.
                           If None, uses harness_TOOL_REGISTRY.
        """
        self.tool_registry = tool_registry or harness_TOOL_REGISTRY
    
    @classmethod
    def from_gateway(cls, tool_gateway: "ToolGateway") -> "ToolSchemaTranslator":
        """
        Create translator from ToolGateway's registry.
        This is the preferred way to construct the translator.
        """
        if hasattr(tool_gateway, "get_tool_definitions"):
            tools = tool_gateway.get_tool_definitions()
            if isinstance(tools, list) and tools:
                return cls([dict(tool) for tool in tools])
        return cls(harness_TOOL_REGISTRY)
    
    def get_harness_tools(self) -> List[Dict[str, Any]]:
        """Return the canonical harness tool definitions."""
        return self.tool_registry
    
    def to_claude_tools(self) -> List[Dict[str, Any]]:
        """
        Convert to Anthropic tool_use format.
        
        Claude format:
        {
            "name": "tool_name",
            "description": "Tool description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        claude_tools = []
        for tool in self.tool_registry:
            claude_tool = {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            claude_tools.append(claude_tool)
        return claude_tools
    
    def to_gemini_tools(self) -> List[Dict[str, Any]]:
        """
        Convert to Gemini function_declarations format.
        
        Gemini format (for google-genai SDK):
        {
            "name": "tool_name",
            "description": "Tool description", 
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        
        The SDK wraps these in Tool(function_declarations=[...])
        """
        gemini_tools = []
        for tool in self.tool_registry:
            gemini_tool = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": self._convert_to_openapi_schema(tool["parameters"]),
            }
            gemini_tools.append(gemini_tool)
        return gemini_tools

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        Convert to OpenAI Chat Completions tools format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "Tool description",
                "parameters": {...}
            }
        }
        """
        openai_tools = []
        for tool in self.tool_registry:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            openai_tools.append(openai_tool)
        return openai_tools
    
    def _convert_to_openapi_schema(self, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert JSON Schema to OpenAPI-style schema (Gemini's format).
        
        Main differences:
        - Some keywords may differ
        - For now, they're largely compatible
        """
        # For most cases, JSON Schema and OpenAPI Schema are compatible
        # This method exists for future edge case handling
        return json_schema
    
    def validate_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """
        Validate tool call arguments against harness schema.
        
        Returns:
            True if valid, raises ValueError if invalid.
        """
        tool_def = None
        for tool in self.tool_registry:
            if tool["name"] == tool_name:
                tool_def = tool
                break
        
        if tool_def is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        params = tool_def["parameters"]
        required = params.get("required", [])
        properties = params.get("properties", {})
        
        # Check required fields
        for req in required:
            if req not in tool_args:
                raise ValueError(f"Missing required argument: {req} for tool {tool_name}")
        
        # Check types (basic validation)
        for arg_name, arg_value in tool_args.items():
            if arg_name in properties:
                schema = properties[arg_name]
                expected_type = schema.get("type")
                if expected_type and not self._check_type(arg_value, expected_type):
                    raise ValueError(
                        f"Invalid type for {arg_name}: expected {expected_type}, "
                        f"got {type(arg_value).__name__}"
                    )
                enum_values = schema.get("enum")
                if isinstance(enum_values, list) and enum_values and arg_value not in enum_values:
                    raise ValueError(
                        f"Invalid value for {arg_name}: expected one of {enum_values}, got {arg_value}"
                    )
        
        return True
    
    def _check_type(self, value: Any, expected_type: Any) -> bool:
        """Basic type checking."""
        if isinstance(expected_type, list):
            return any(self._check_type(value, str(type_name)) for type_name in expected_type)
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow
        return isinstance(value, expected)
