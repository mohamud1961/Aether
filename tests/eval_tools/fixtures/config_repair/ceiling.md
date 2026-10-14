# Ceiling: config_repair

## What a perfect solution does

Edits `config.json` in the working directory so that `port` is the JSON number `8080` and
`log_level` is the string `"info"`. The other keys (`service`, `shutdown_timeout_s`) are left
unchanged. The file stays valid JSON.

## Why each known-bad state is wrong

- `fix_port_only.sh`: `port` is correct, but `log_level` is still `"WARN"`. The grader reports
  `log_level_not_info`. The task asked for both fields.
- `fix_log_level_only.sh`: `log_level` is correct, but `port` is still the string `"8080"`.
  The grader reports `port_not_integer_8080`. A string is not the integer the task asked for.

Both known-bads are plausible partial edits: each repairs one of the two defects and stops.
Together they test that the grader checks both fields and does not pass on either alone.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, reasons `port_not_integer_8080` and `log_level_not_info`.
