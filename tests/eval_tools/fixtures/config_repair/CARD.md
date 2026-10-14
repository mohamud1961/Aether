# Task card: config repair

Admission: **smoke**. Reference/floor/known-bad controls test the declared port; they do not establish parity with the original trace contract.

## Check disposition

| Port check | Source relationship | Known-bad controls |
|---|---|---:|
| config_not_json | ported/strengthened state check; inspect source disposition | 0 |
| config_not_object | ported/strengthened state check; inspect source disposition | 0 |
| log_level_not_info | ported/strengthened state check; inspect source disposition | 1 |
| port_not_integer_8080 | ported/strengthened state check; inspect source disposition | 1 |



Original source identity: `synthetic example; no historical source`. Grader-source content hashes: . Per-requirement semantic review remains pending.
