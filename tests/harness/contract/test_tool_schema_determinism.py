"""
Contract Tests: Tool Schema Determinism

Verifies that tool schema translation is deterministic.
"""
import unittest

from aether.tool_schema_translator import (
    ToolSchemaTranslator,
    harness_TOOL_REGISTRY,
)


class TestToolSchemaDeterminism(unittest.TestCase):
    """Test that tool schema translation is deterministic."""
    
    def test_claude_schema_deterministic(self):
        """Multiple calls produce identical Claude schemas."""
        translator = ToolSchemaTranslator()
        
        schema1 = translator.to_claude_tools()
        schema2 = translator.to_claude_tools()
        
        self.assertEqual(schema1, schema2)
    
    def test_gemini_schema_deterministic(self):
        """Multiple calls produce identical Gemini schemas."""
        translator = ToolSchemaTranslator()
        
        schema1 = translator.to_gemini_tools()
        schema2 = translator.to_gemini_tools()
        
        self.assertEqual(schema1, schema2)
    
    def test_registry_not_hardcoded_in_translator(self):
        """Translator should accept custom registry."""
        custom_registry = [
            {
                "name": "custom_tool",
                "description": "A custom tool",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
        
        translator = ToolSchemaTranslator(custom_registry)
        tools = translator.get_harness_tools()
        
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "custom_tool")


class TestToolSchemavalidation(unittest.TestCase):
    """Test tool argument validation."""
    
    def test_validate_run_command_valid(self):
        """Valid run command passes validation."""
        translator = ToolSchemaTranslator()
        
        result = translator.validate_tool_call(
            "run", 
            {"command": ["ls", "-la"]}
        )
        self.assertTrue(result)
    
    def test_validate_run_command_missing_required(self):
        """Missing required arg fails validation."""
        translator = ToolSchemaTranslator()
        
        with self.assertRaises(ValueError) as ctx:
            translator.validate_tool_call("run", {})
        
        self.assertIn("Missing required argument", str(ctx.exception))
    
    def test_validate_unknown_tool(self):
        """Unknown tool fails validation."""
        translator = ToolSchemaTranslator()
        
        with self.assertRaises(ValueError) as ctx:
            translator.validate_tool_call("unknown_tool", {})
        
        self.assertIn("Unknown tool", str(ctx.exception))
    
    def test_validate_wrong_type(self):
        """Wrong argument type fails validation."""
        translator = ToolSchemaTranslator()
        
        with self.assertRaises(ValueError) as ctx:
            translator.validate_tool_call("run", {"command": "not an array"})
        
        self.assertIn("Invalid type", str(ctx.exception))


class TestClaudeSchemaFormat(unittest.TestCase):
    """Test Claude schema format is valid."""
    
    def test_claude_schema_has_input_schema(self):
        """Claude tools use 'input_schema' key."""
        translator = ToolSchemaTranslator()
        tools = translator.to_claude_tools()
        
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("input_schema", tool)
            self.assertIn("type", tool["input_schema"])


class TestGeminiSchemaFormat(unittest.TestCase):
    """Test Gemini schema format is valid."""
    
    def test_gemini_schema_has_parameters(self):
        """Gemini tools use 'parameters' key."""
        translator = ToolSchemaTranslator()
        tools = translator.to_gemini_tools()
        
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("parameters", tool)
            self.assertIn("type", tool["parameters"])


if __name__ == "__main__":
    unittest.main()
