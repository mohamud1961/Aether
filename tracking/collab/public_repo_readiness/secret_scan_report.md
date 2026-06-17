# Secret Scan Report

- Generated: `2026-06-15T16:09:56Z`
- Files scanned as text: `107`
- Scope: the current non-ignored changed/untracked file set from `git ls-files -m -o --exclude-standard`.
- High-confidence secret signatures checked: private key headers, AWS access key formats, GitHub PAT shapes, and common `sk-` style API keys.

## Findings

- No high-confidence secret signatures were found in the scanned text files.

## Caveat

- This is a targeted signature scan, not a full DLP product. It is good for catching obvious credential leaks, not for proving the absence of every sensitive string.
