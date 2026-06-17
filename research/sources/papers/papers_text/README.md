# Paper Text Surface

This directory is the canonical repo-local paper surface for Deep Synthesis and related research work.

- Source PDFs live under `research/sources/papers/`.
- Extracted text lives as `<paper_key>.txt`.
- Extraction metadata lives as `<paper_key>.meta.json`.
- `manifest.json` summarizes the latest bulk extraction pass, readability counts, and rescue queue.
- `review_summary.md` records the current extraction-quality rule and the caveated or unread papers.

Run the bulk extractor with:

```bash
.venv/bin/python research/tools/extract_papers_text.py
```

Quality flags:

- `clean`: text extracted without parser or page-level errors
- `usable_with_caveats`: text is readable enough to count as read, but parser warnings, character corruption, low text density, or similar artifacts mean claims should weaken confidence where damaged sections matter
- `ocr_needed`: extraction produced too little usable text for reliable reading
- `failed`: the PDF could not be opened or processed at all

Deep Synthesis rule:

- `clean`: counts as read and supports full formal-source use
- `usable_with_caveats`: counts as read, but only with caveats
- `ocr_needed`: does not count as substantively read yet
- `failed`: does not count as substantively read yet
