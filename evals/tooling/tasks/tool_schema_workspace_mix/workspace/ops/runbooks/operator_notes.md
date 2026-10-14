# Operator notes

- Fast path (old): read the cache under tmp/tool_cache first. It is only a hint.
- Correct path: the contract, then the live snapshot, latest row per ticket wins.
- Production means the prefix the environments file names for production, not an older file.
- Priority 1 is more urgent than priority 9. Ties go to the lower workspace id.
