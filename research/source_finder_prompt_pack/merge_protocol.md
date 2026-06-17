# Merge Protocol

1. Run one source-finder per bucket using `prompts/canonical_source_finder_template.md` plus the matching bucket file in `prompts/buckets/`.
2. Save each raw bucket batch unchanged to `research/intake/inbox/<run_date>__<agent_id>__<bucket_slug>__raw.json`.
3. Capture or download each accepted source artifact into the matching lifecycle-independent artifact folder under `research/sources/`.
4. Run `prompts/dedup_normalization.md` across all raw bucket outputs plus any preexisting accepted records.
5. Finalize canonical URL or locator, `dedupe_key`, artifact class, and stable `source_id`.
6. Write one authoritative metadata record per accepted source to `research/intake/records/<source_id>.json`.
7. Write dedupe decisions and bucket manifests under `research/intake/normalized/`.
8. Run `prompts/quality_control.md` against the raw batches, normalized records, and dedupe decisions.
9. Remove or block any record that fails QC, and update bucket manifests and the corpus manifest.
10. Publish only `research/intake/normalized/manifests/corpus__deduped.json` as the ready-for-review corpus index.

Merge rules

- Never merge by bucket. Merge by canonical source identity only.
- Bucket associations survive as metadata tags, not as duplicate files.
- Rejected candidates and QC-blocked items remain auditable in `research/intake/rejected/`.
- Claims never move across sources. A merged record may union claims from duplicate discoveries only when they point to the same source.
- If canonical identity is unchanged and artifact class is unchanged, preserve the same `source_id`.
- If canonical identity changes materially, mint a new `source_id` and log the remap in the dedupe decisions file.
