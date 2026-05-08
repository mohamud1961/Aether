# Eval Benchmark Dossiers

This directory holds structured dossiers for benchmark contracts, verifier logic, grader and judge structure, replay logic, and local eval hooks.

The purpose is to make eval depth explicit instead of treating benchmark familiarity as actual evaluator understanding.

## What belongs here

- benchmark-contract dossiers
- verifier or grader dossiers
- replay or state-diff dossiers
- judge-model risk dossiers
- local eval hook dossiers under `evals/`

## Default structure

```text
EVAL_BENCHMARK_DOSSIER
- dossier_type:
- target:
- source_scope:
- contract_or_logic:
- verifier_or_grader_structure:
- replay_or_state_logic:
- judge_risk_or_gaming_surface:
- local_eval_links:
- mechanism_relevance:
- failure_relevance:
- contradictions:
- confidence_notes:
```

## Operating rules

1. Benchmark names are not enough.
2. Public benchmark captures, mirrored eval code, and local eval code should stay distinct.
3. Dossiers support mechanism, failure, and eval implication work; they do not replace them.
