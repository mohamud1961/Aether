"""
Contract Tests: Response Normalizer Parity

Verifies that the normalizer:
1. Produces consistent output for same input
2. Handles edge cases (multi-candidate, text+tool, invalid args)
3. Synthesizes call IDs deterministically for Gemini
"""
import unittest
import json
import hashlib

from aether.response_normalizer import (
    ResponseNormalizer,
    NormalizationError,
)
from aether.tool_schema_translator import ToolSchemaTranslator


class TestNormalizerParity(unittest.TestCase):
    """Test normalizer produces consistent output."""
    
    def setUp(self):
        self.translator = ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.translator)
    
    def test_claude_same_input_same_output(self):
        """Same Claude response produces same normalized output."""
        response = {
            "content": [
                {"type": "tool_use", "id": "call_1", "name": "run", "input": {"command": ["ls"]}}
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        raw = json.dumps(response).encode("utf-8")
        
        result1 = self.normalizer.normalize_claude(raw)
        result2 = self.normalizer.normalize_claude(raw)
        
        self.assertEqual(result1.raw_hash, result2.raw_hash)
        self.assertEqual(len(result1.tool_calls), len(result2.tool_calls))
        self.assertEqual(result1.tool_calls[0].call_id, result2.tool_calls[0].call_id)
    
    def test_gemini_same_input_same_output(self):
        """Same Gemini response produces same normalized output."""
        response = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"functionCall": {"name": "run", "args": {"command": ["ls"]}}}
                    ]
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        raw = json.dumps(response).encode("utf-8")
        
        result1 = self.normalizer.normalize_gemini(raw)
        result2 = self.normalizer.normalize_gemini(raw)
        
        self.assertEqual(result1.raw_hash, result2.raw_hash)
        self.assertEqual(len(result1.tool_calls), len(result2.tool_calls))
        # Call IDs should be synthesized deterministically
        self.assertEqual(result1.tool_calls[0].call_id, result2.tool_calls[0].call_id)

    def test_openai_same_input_same_output(self):
        """Same OpenAI response produces same normalized output."""
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "run",
                                "arguments": "{\"command\":[\"ls\"]}",
                            },
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 3},
            },
        }
        raw = json.dumps(response).encode("utf-8")

        result1 = self.normalizer.normalize_openai(raw)
        result2 = self.normalizer.normalize_openai(raw)

        self.assertEqual(result1.raw_hash, result2.raw_hash)
        self.assertEqual(len(result1.tool_calls), len(result2.tool_calls))
        self.assertEqual(result1.tool_calls[0].call_id, result2.tool_calls[0].call_id)
        self.assertEqual(result1.cache_read_tokens, 3)


class TestNormalizerMultiCandidate(unittest.TestCase):
    """Test multi-candidate response handling."""
    
    def setUp(self):
        self.translator = ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.translator)
    
    def test_gemini_multi_candidate_uses_index_0(self):
        """Multi-candidate response should use index 0 and warn."""
        response = {
            "candidates": [
                {"content": {"parts": [{"functionCall": {"name": "run", "args": {"command": ["ls"]}}}]}, "finishReason": "STOP"},
                {"content": {"parts": [{"functionCall": {"name": "run", "args": {"command": ["pwd"]}}}]}, "finishReason": "STOP"},
            ],
            "usageMetadata": {},
        }
        raw = json.dumps(response).encode("utf-8")
        
        result = self.normalizer.normalize_gemini(raw)
        
        # Should use first candidate
        self.assertEqual(result.tool_calls[0].tool_args["command"], ["ls"])
        self.assertEqual(result.candidate_count, 2)
        
        # Should have warning
        self.assertTrue(any("Multi-candidate" in w for w in result.normalization_warnings))


class TestNormalizerTextPlusTool(unittest.TestCase):
    """Test handling of responses with both text and tool calls."""
    
    def setUp(self):
        self.translator = ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.translator)
    
    def test_claude_text_plus_tool_warns(self):
        """Text content alongside tool calls should be logged but not acted on."""
        response = {
            "content": [
                {"type": "text", "text": "Let me run a command..."},
                {"type": "tool_use", "id": "call_1", "name": "run", "input": {"command": ["ls"]}}
            ],
            "stop_reason": "tool_use",
            "usage": {},
        }
        raw = json.dumps(response).encode("utf-8")
        
        result = self.normalizer.normalize_claude(raw)
        
        # Should have tool calls
        self.assertEqual(len(result.tool_calls), 1)
        
        # Should have warning about text content
        self.assertTrue(any("text ignored" in w.lower() for w in result.normalization_warnings))


class TestNormalizerInvalidArgs(unittest.TestCase):
    """Test fail-closed behavior on invalid arguments."""
    
    def setUp(self):
        self.translator = ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.translator)
    
    def test_claude_invalid_args_raises(self):
        """Invalid tool args should raise NormalizationError."""
        response = {
            "content": [
                {"type": "tool_use", "id": "call_1", "name": "run", "input": {}}  # Missing 'command'
            ],
            "stop_reason": "tool_use",
            "usage": {},
        }
        raw = json.dumps(response).encode("utf-8")
        
        with self.assertRaises(NormalizationError) as ctx:
            self.normalizer.normalize_claude(raw)
        
        self.assertIn("validation failed", str(ctx.exception).lower())
    
    def test_gemini_unknown_tool_raises(self):
        """Unknown tool should raise NormalizationError."""
        response = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"functionCall": {"name": "unknown_tool", "args": {}}}
                    ]
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {},
        }
        raw = json.dumps(response).encode("utf-8")
        
        with self.assertRaises(NormalizationError) as ctx:
            self.normalizer.normalize_gemini(raw)
        
        self.assertIn("Unknown tool", str(ctx.exception))

    def test_openai_invalid_args_json_raises(self):
        """Invalid OpenAI function arguments JSON should raise NormalizationError."""
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "run",
                                "arguments": "{not-json}",
                            },
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {},
        }
        raw = json.dumps(response).encode("utf-8")

        with self.assertRaises(NormalizationError) as ctx:
            self.normalizer.normalize_openai(raw)

        self.assertIn("arguments", str(ctx.exception).lower())


class TestNormalizerGeminiCallId(unittest.TestCase):
    """Test deterministic call ID synthesis for Gemini."""
    
    def setUp(self):
        self.translator = ToolSchemaTranslator()
        self.normalizer = ResponseNormalizer(self.translator)
    
    def test_call_id_deterministic(self):
        """Synthesized call ID should be deterministic."""
        call_id1 = self.normalizer._synthesize_call_id("run", {"command": ["ls"]}, 0)
        call_id2 = self.normalizer._synthesize_call_id("run", {"command": ["ls"]}, 0)
        
        self.assertEqual(call_id1, call_id2)
        self.assertEqual(len(call_id1), 16)  # Truncated to 16 chars
    
    def test_call_id_differs_for_different_args(self):
        """Different args should produce different call IDs."""
        call_id1 = self.normalizer._synthesize_call_id("run", {"command": ["ls"]}, 0)
        call_id2 = self.normalizer._synthesize_call_id("run", {"command": ["pwd"]}, 0)
        
        self.assertNotEqual(call_id1, call_id2)
    
    def test_call_id_differs_for_different_index(self):
        """Different index should produce different call IDs."""
        call_id1 = self.normalizer._synthesize_call_id("run", {"command": ["ls"]}, 0)
        call_id2 = self.normalizer._synthesize_call_id("run", {"command": ["ls"]}, 1)
        
        self.assertNotEqual(call_id1, call_id2)


if __name__ == "__main__":
    unittest.main()
