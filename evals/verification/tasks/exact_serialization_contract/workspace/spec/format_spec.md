# Output Format Specification (v2, 2026-10)

Output file: `out/canonical.json`

This version supersedes `format_spec.v1.md`. Where they differ, this file governs.

## Structure

- Root: JSON array of objects.
- One object per CSV record.

## Key order per object

Keys must appear in exactly this order:

1. `id`
2. `name`
3. `balance`
4. `active`
5. `tags`

## Type rules

- `id`: integer (not string). Example: `1` not `"1"`.
- `name`: string, JSON-escaped (quotes and commas inside a name are kept as text).
- `balance`: number with exactly 2 decimal places. Example: `1234.50` not `1234.5`.
- `active`: boolean. Example: `true` not `"true"`.
- `tags`: array of strings. For empty tags, use an empty array `[]`, not `null`.

## Sorting

Root array sorted by `id` ascending.

## Formatting

- 2-space indentation for the root array and for each object.
- Each array of strings is written inline, with `, ` between items. Example: `["admin", "user"]`.
- Trailing newline (single `\n` at end of file).
- No trailing commas.
