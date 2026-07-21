# Reconstructed role-board source gate

- Certified base: `aa800976fe862af3cbdf3c10c13a8fd3254a1228`.
- Manifest comparison: all 85 production-source files matched the prior VM certification manifest before applying the later generic role-route fixes.
- Qualified integration commit: `20367a15b919cc82dae0adcc17ef1826874f3773`.
- Tree: `f32652cf58195ba74a3061f7f5b10a126d67ae28`.
- Focused production-path tests: 98 passed.
- Clean committed-source deterministic certification: 17/17 passed; aggregate SHA-256 `4618c7323d1a30728441ff0e9cc1429049823376d4e66c3283ffc6533a200839`; final-marker SHA-256 `d0612879a3700bdafd6959556be56cb572c874bbdf2a1746274146f2a0096a51`.

The deterministic evidence is retained outside the source worktree at
`/private/tmp/aether-qualified-certification-20367a15/` to keep the source
clean for the VM certification. The earlier sandbox-only three-test failure is
classified as environment invalid: the same loopback service tests passed in
the unrestricted local certification.

## Review

`codex review --uncommitted` could not run because the local Codex state
database is readonly. This is a review-tool environment limitation, not a
clean review. Manual adversarial review is required before role-board
promotion.
