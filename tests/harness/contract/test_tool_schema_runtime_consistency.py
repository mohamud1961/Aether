import unittest

from aether.tool_schema_translator import ToolSchemaTranslator


class TestToolSchemaruntimeConsistency(unittest.TestCase):
    def test_declared_schema_tools_are_runtime_supported(self) -> None:
        translator = ToolSchemaTranslator()
        declared = [tool["name"] for tool in translator.get_harness_tools()]
        self.assertIn("run", declared)
        self.assertIn("read_file", declared)
        self.assertIn("write_file", declared)
        self.assertIn("search_files", declared)
        self.assertIn("request_phase_transition", declared)
        self.assertEqual(len(declared), len(set(declared)))

    def test_from_gateway_exposes_full_registry(self) -> None:
        run_tool = ToolSchemaTranslator().get_harness_tools()[0]
        fake_tool = {
            "name": "fake_tool",
            "description": "Synthetic registry tool for contract validation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        }

        class FakeGateway:
            def get_tool_definitions(self):
                return [run_tool, fake_tool]

        translator = ToolSchemaTranslator.from_gateway(FakeGateway())
        declared = [tool["name"] for tool in translator.get_harness_tools()]
        self.assertEqual(declared, ["run", "fake_tool"])

    def test_run_tool_schema_is_valid(self) -> None:
        translator = ToolSchemaTranslator()
        self.assertTrue(translator.validate_tool_call("run", {"command": ["echo", "ok"]}))

    def test_request_phase_transition_schema_is_valid(self) -> None:
        translator = ToolSchemaTranslator()
        self.assertTrue(
            translator.validate_tool_call(
                "request_phase_transition",
                {"to_phase": "Review", "phase_reason_code": "manual_request"},
            )
        )

    def test_run_schema_includes_cwd_guidance(self) -> None:
        translator = ToolSchemaTranslator()
        run_tool = translator.get_harness_tools()[0]
        self.assertIn("cwd", run_tool["parameters"]["properties"])
        self.assertIn(
            "Use `cwd` instead of `cd ... && ...`",
            run_tool["description"],
        )
        self.assertIn(
            "Use this instead of cd",
            run_tool["parameters"]["properties"]["cwd"]["description"],
        )
        claude_run = translator.to_claude_tools()[0]
        gemini_run = translator.to_gemini_tools()[0]
        openai_run = translator.to_openai_tools()[0]
        self.assertIn("cwd", claude_run["input_schema"]["properties"])
        self.assertIn("cwd", gemini_run["parameters"]["properties"])
        self.assertIn("cwd", openai_run["function"]["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
