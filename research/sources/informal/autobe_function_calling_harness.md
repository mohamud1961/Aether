# Function Calling Harness: From 6.75% to 100% (Summary)

**Source:** https://autobe.dev/blog/function-calling-harness-qwen-meetup-korea/
**Date:** 2026-03-29 (Extraction)

## Core Thesis
The "probabilistic" nature of LLMs can be countered by a "deterministic" harness. The blog demonstrates a jump from 6.75% to 100% success in complex function calling by treating correctness as an engineering problem rather than a prompting problem.

## Key Mechanisms
1. **Typia-Driven Schema**: Converts TypeScript types into JSON Schemas. This provides a single source of truth for the type, the validator, and the prompt.
2. **Lenient JSON Parsing**: Automatically recovers from broken JSON or double-stringified output (common in weaker models).
3. **Precise Validation Feedback**: When a call fails validation, the harness generates structured feedback with inline comments (e.g., `// ❌ price: must be positive`). 
4. **Self-Healing Loop**: The "Correct Agent" receives the original output + diagnostic feedback and makes targeted fixes to failing fields only.

## Performance Outcomes
- **Model Neutrality**: The same schema and pipeline achieved 100% compilation across Qwen (35B to 397B), GLM, DeepSeek, and OpenAI.
- **Efficiency**: Prompt fragility is eliminated; the validation loop absorbs differences in model capability.
- **Convergence**: Most models converge in 1-2 attempts; weaker ones 3-4.
