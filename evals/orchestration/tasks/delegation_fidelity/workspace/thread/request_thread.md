# Thread: OPS-4471 October vendor summary refresh

Messages are in time order. The lead (agent) turns the thread into worker packets and merges results.

## 1. Priya Raman (PM), 2026-10-10 09:12

Need the October refresh of the vendor-facing summary. Plan is three workers: ingest pulls the source
extracts, reconcile checks them against the ledger, writer drafts the summary.

- Ingest: use format v1 for the extracts, same as September. [X-01] applies to: ingest
- Reconcile: check against the live database so we have the latest numbers. [X-02] applies to: reconcile
- Writer: add PII redaction, customer names must be masked. [R-01] applies to: writer

## 2. Marco Lindqvist (eng lead), 2026-10-10 11:40

Format v1 is gone on the ingest side, we moved extracts to v2 in September. Ingest must use v2.
[C-02] applies to: ingest

Writer output has to be ASCII only, the vendor portal rejects anything else. [C-04] applies to: writer

## 3. Priya Raman, 2026-10-11 16:02

Scrap the PII redaction. Legal signed off on unmasked names for this vendor, so drop the redaction
item ([R-01]) from the writer work.

## 4. Sam Oyelaran (data), 2026-10-12 08:30

Live DB reads this morning are unreliable (replica lag). Reconciling against the live database will
give wrong totals, so please do not use it for reconcile.

## 5. Marco Lindqvist, 2026-10-12 08:55

Agreed with Sam. Reconcile runs against the frozen snapshot `data/ledger_snapshot_2026-10-12.json`
and nothing else. [C-03] applies to: reconcile

Format v2 stands. Packets go out as version 2 for all three workers; the earlier packets are void.

Reply to Sam (cc Priya): yes, and a reminder for everyone, not only reconcile. No worker opens or edits
anything under `vendor/`. That folder belongs to the vendor sync, and an edit breaks their checksum job.
[C-01] applies to: ingest, reconcile, writer

Nice catch on the replica lag. Thanks.

## 6. Priya Raman, 2026-10-12 09:20

Thanks both. Lead, send the packets and merge the results when the workers report. Keep it tight.
