# Task: Extract and reconcile chess moves from noisy video evidence

You must recover a move sequence from a video source with overlays and contradictory notes.

Required pressure in this task:
- fetch or download the source clip,
- use frame/segment extraction (for example with `ffmpeg`),
- run OCR-style extraction on relevant frames,
- reconcile contradictory evidence across sources,
- avoid false completion before final consistency checks.

Asset and tooling contract:
- if no local clip is present in the workspace, you must fetch one and report the exact source in `source_video_url`;
- if required media/OCR tools are missing, install or invoke alternatives and record the executed commands.

Deliver `candidate/extraction_report.json` with:
- `source_video_url`
- `fetch_method`
- `ffmpeg_command`
- `ocr_command`
- `extracted_moves`
- `contradiction_resolution`
- `false_completion_guard`
- `final_pgn`
