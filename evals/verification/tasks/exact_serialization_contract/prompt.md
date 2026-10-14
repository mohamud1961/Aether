# Render the current customer export as canonical JSON

Billing needs the current customer export as canonical JSON. You are in the workspace root (the current
directory). The `data/` folder holds the exports and a pointer to the current one; `spec/` holds the format
spec. Work out which export is current and follow the current spec exactly.

Write `out/canonical.json` (create `out/` if needed). Its bytes must match the spec, so key order, number
formatting, indentation and the trailing newline all count. Do not change anything under `data/`, `spec/` or
`checks/`.

When the file is written, run the visible check from the workspace root:

```
python3 checks/visible_check.py --candidate out/canonical.json
```

It only checks the file shape, so it does not confirm the output. Finish when the file matches the spec.

Public dataset identifier: harness-evals-public-8919c6a654338eab.
