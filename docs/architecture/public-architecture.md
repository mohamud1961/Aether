# Public Architecture

HarnessEng is organized around a canonical public Python namespace plus a set
of evaluation and workflow surfaces around it.

## Canonical Layout

```mermaid
flowchart LR
  Root["HarnessEng repo"]

  subgraph Canonical["Canonical public Python harness"]
    Runtime["harness.aether2.runtime"]
    Control["harness.aether2.control"]
    Tools["harness.aether2.tools"]
    Traces["harness.aether2.traces"]
    Packages["harness.aether2 package exports"]
  end

  subgraph Navigation["Public navigation-only subpackages"]
    Agents["harness.aether2.agents"]
    CLI["harness.aether2.cli"]
    Env["harness.aether2.env"]
    Hooks["harness.aether2.hooks"]
    Monitoring["harness.aether2.monitoring"]
    Skills["harness.aether2.skills"]
    Verification["harness.aether2.verification"]
  end

  subgraph Surrounding["Public engineering surfaces"]
    EvalSuite["eval_suite/"]
    Variants["variants/"]
    Workflows["workflows/"]
    Docs["docs/"]
    Tests["tests/"]
  end

  NavStub["Navigation-only subpackages"]
  Runner["runner.aether2 compatibility"]

  Root --> Packages
  Packages --> Runtime
  Packages --> Control
  Packages --> Tools
  Packages --> Traces
  Packages -. legacy import compatibility .-> Runner
  Runner -. re-exports canonical objects .-> Packages

  Workflows --> Runtime
  Workflows --> Control
  Workflows --> EvalSuite
  Variants --> EvalSuite
  EvalSuite --> Runtime
  EvalSuite --> Tools
  EvalSuite --> Traces
  Docs --> Root
  Tests --> Packages
  NavStub -. currently stubbed public directories .-> Packages
```

## Runtime

`harness.aether2.runtime` contains workspace execution and support plumbing:

- `bridge_harbor.py`
- `cleanup_accounting.py`
- `compactor.py`
- `context.py`
- `escalation.py`
- `executor.py`
- `jobs.py`
- `metrics.py`
- `model_client.py`
- `orientation.py`
- `prompts.py`
- `sessions.py`
- `verify.py`

## Control

`harness.aether2.control` contains the loop and orchestration boundary. The
implemented module is `loop.py`.

## Tools

`harness.aether2.tools` currently surfaces the canonical tool schema and
dispatch implementation in `native.py`.

## Traces

`harness.aether2.traces` contains the evidence and decision artifacts:

- `decision_trace.py`
- `delta.py`
- `envelope.py`
- `mirror.py`
- `receipts.py`

## Navigation-Only Subpackages

The following directories are part of the public package map but do not yet
contain separate Python implementations:

- `harness/aether2/agents/`
- `harness/aether2/cli/`
- `harness/aether2/env/`
- `harness/aether2/hooks/`
- `harness/aether2/monitoring/`
- `harness/aether2/skills/`
- `harness/aether2/verification/`

## Eval Suite

`eval_suite/` is the public home for task packs, graders, adapters, boards,
fixtures, sentinels, and scoreboards. It is the evaluation layer around the
runtime, not the runtime itself.

The public eval map now has dedicated family, harness, calibration, and
adapted-pressure layers:

- `eval_suite/families/`
- `eval_suite/whole_harness/`
- `eval_suite/calibration_lanes/`
- `eval_suite/benchmark_derived_families/`

The concrete executable smoke packs still live under
`eval_suite/custom/public_manifest_repair_smoke/` and
`eval_suite/custom/homolog_contract_smoke/`, with matching boards in
`eval_suite/boards/` and example scoreboards in `eval_suite/scoreboards/`.

## Workflows

`workflows/` documents the AI-native engineering system used to build the
harness: governed multi-agent work, analysis, synthesis, evaluation governance,
and publication procedures.

## Variants

`variants/` records mechanism families and shared scoreboards. It is the public
surface for hypothesis tracking, not a production runtime entrypoint.

## Compatibility Boundary

`runner.aether2` stays available for existing imports and tests, but it is not
the canonical ownership boundary. New public references should use
`harness.aether2` first.
