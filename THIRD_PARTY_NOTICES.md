# Third-party notices

## Prime Agent compaction prompts

`aether/core/compaction.py` contains context-compaction prompts derived from Prime Agent, from
`PrimeIntellect-ai/prime-agent` at commit `3e0893260eefdab3c8391dab9b7386d6cc864a62`
(`crates/pa-core/src/session_engine/compaction.rs` and `compaction_utils.rs`). Public curation normalizes terminology (including “user” to “principal”), so these are adapted
prompts rather than byte-identical copies. The source module’s historical “verbatim” description
refers to its original research version. They are used under the MIT licence:

```
MIT License

Copyright (c) 2025-2026 Prime Intellect Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Context-limit method (CLM)

`aether/core/clm.py` implements the model-managed context method described in the README of Meta's
context-language-models `clm_harness`. It was written clean-room from that description; no CLM code or text is
included (CLM is licensed CC BY-NC 4.0).
