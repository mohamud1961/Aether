# Real runs

Each run below is one real Core run with `gpt-6-luna`, on a task graded afterwards by hidden tests the agent never
saw. All eight passed. The tasks come from Terminal-Bench 2.1 and 4, public sets of realistic computer tasks. Task
wording is paraphrased here, because benchmark text is not republished.

Time is from first request to finish. Cost is model usage priced at $0.25 / $0.025 / $0.90 per million input /
cached / output tokens. Steps are model turns.

These are chosen successful runs, not success rates. On the hardest tasks Core does not succeed on every attempt.

## Bank capital calculation (Terminal-Bench 4)

**The job:** a risk team needs counterparty credit risk capital recalculated for two netting sets under the EU
rules (SA-CCR as implemented in CRR3). One is an uncollateralised US corporate with 8 trades, including a new
option not yet in the system. The other is a Spanish bank under a collateral agreement with amended terms, 5
trades across interest rates, a cross-currency swap and credit, plus three margin disputes that ran past the
standard period. Output: a results file and a workbook showing the calculation.

**What Core did:**
1. Read every input file: portfolio, counterparties, collateral terms, dispute log, FX, supervisory factors,
   holiday calendars.
2. Wrote a calculation script, then corrected it step by step as the details came out: date formats, the
   cross-currency swap's treatment, commodity fields.
3. Checked the regulation text for the parameters it needed.
4. Built the full calculation: replacement cost, potential future exposure by hedging set, exposure at default,
   risk-weighted assets and capital.
5. Wrote the results CSV, and an Excel workbook with trade-level workings and formula-driven roll-ups.
6. Reopened both files and checked their contents before finishing.

**Result:** passed. 17m 15s, 33 steps, $0.18.

## Design file from a picture (Terminal-Bench 4)

**The job:** a finished graphic and the image pieces it was made from. Work out the layout, meaning each element's
position, size, layer order, mirroring and opacity, plus every text element's font, size, colour and spacing.
Write it as a JSON layout config that a provided renderer turns back into the graphic.

**What Core did:** inspected the renderer and every component image, measured where each piece sits in the final
graphic, identified the text styling, wrote the config, rendered it, compared the render with the original pixel
by pixel, and adjusted until they matched.

**Result:** passed. The final render was pixel-identical to the original. 26m 42s, 63 steps, $0.19.

## 3D part from an engineering drawing (Terminal-Bench 4)

**The job:** the only source is a PNG of an engineering drawing. Write a FreeCAD Python script that builds the
part as a real parametric model (one PartDesign body with a named feature tree, not a baked shape), honouring
every labelled dimension, radius and angle.

**What Core did:**
1. Looked at the drawing, then cropped and enlarged each view (side, section, front, plan) to read the small
   dimension labels.
2. Wrote `build_part.py` and ran it in FreeCAD.
3. Reopened the saved file and checked the feature tree: exactly one body, no baked shapes, one valid solid.
4. Exported a mesh and rendered it to check the shape visually.
5. Removed its own scratch files and finished.

**Result:** passed. 12m 34s, 30 steps, $0.11.

## Invoices from a folder of scans (Terminal-Bench 2.1)

**The job:** a folder of 17 mixed documents, PDFs and photographed pages. Move the invoices into their own
folder, the rest into another, and write a summary of each invoice's total and VAT.

**What Core did:**
1. Listed the documents and installed a PDF reader and OCR.
2. Read every page. Opened the one scan OCR could not read and read it as an image.
3. Sorted the documents: 10 invoices, 7 other.
4. Wrote `summary.csv`, with totals of 81,315.20 and VAT of 5,402.48.
5. Checked the row count, the sums and that nothing was left behind.

**Result:** passed. 5m 44s, 12 steps, $0.03.

## COBOL to Python (Terminal-Bench 2.1)

**The job:** rewrite a COBOL program that updates account, book and transaction files, so that it behaves exactly
the same.

**What Core did:**
1. Read the program and its data files.
2. Compiled and ran the original, and probed how it updates balances.
3. Wrote `program.py`.
4. Ran both versions on the same six inputs and compared the output files.
5. Tested overflow and edge cases, and ran it again from another folder.

**Result:** passed. Every case matched byte for byte. 4m 20s, 18 steps, $0.03.

## Robot trajectories in PyDrake (Terminal-Bench 4)

**The job:** write a trajectory generator for a simulated biped robot that produces walking, jumping and running
motions that obey contact and friction physics. It must read its settings from a config file, because it is
re-run on hidden configs.

**What Core did:** built a config-driven PyDrake generator, produced the three trajectories, and checked them on
the visible config and two varied configs for schema, gait modes, contact and friction, integration and
smoothness, and inverse dynamics.

**Result:** passed, including the hidden configs. 33m 45s, 101 steps, $0.44.

## Leaked secret in git history (Terminal-Bench 2.1)

**The job:** a secret was committed and then hidden from the branch history. Recover it into a file, then make
sure it is gone from the repository.

**What Core did:** read the history and reflog, found the unreachable commit holding the secret, saved the
secret where asked, purged the commit and every stale reference, and scanned the repository again: the commit
was absent and the scan was clear.

**Result:** passed. 1m 23s, 9 steps, $0.01.

## Lost database records (Terminal-Bench 2.1)

**The job:** a database looks empty because its write-ahead log is damaged. Recover every record into a JSON
file.

**What Core did:** inspected the database and the log header, found the log was XOR-scrambled with one byte,
decoded it on a copy first, checked integrity, restored the real log, and exported all 11 records.

**Result:** passed. 48s, 8 steps, $0.005.
