# Trajectory Support Long-Horizon Failure Timeline (Wave 04)

## BigAI extract-moves-from-video (`953d...`)
- Repeated long-running phases with poll loops at ~30-second intervals (`process has not exited yet and is still running`) during setup, OCR, and extraction stages.
  - Evidence: `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
- Explicit signal intervention after ~300 seconds in one long-running command phase.
  - Evidence phrase: `signal successfully delivered ... after ... 300.348493 seconds`.
- Later phase repeats similar pattern with additional long-running OCR/tool loops and another signal intervention near ~292 seconds.
  - Evidence phrase: `signal successfully delivered ... after ... 292.024762 seconds`.

## Terminus-KIRA extract-moves-from-video (`3df8...`)
- Tool/command pipeline destabilization during long manual extraction script assembly:
  - batched-command concatenation leads to parse/syntax cascades,
  - missing script targets (`can't open file`) follow malformed command episodes.
- OCR phase interruption includes explicit `KeyboardInterrupt` in pytesseract timeout manager stack.
  - Evidence: `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`

## BigAI timeout concentration anchor
- `answered_questions.md` attributes timeout exceptions as dominant explicit exception mode and concentrates failures on hard systems/long-run tasks.
  - Key tasks called out: `torch-pipeline-parallelism`, `train-fasttext`, `caffe-cifar-10`, `qemu-startup`.
  - Evidence: `research/analysis/bigai_trace_layer/output/answered_questions.md`

## Interpretation boundary
- This support timeline is behavioral and event-sequenced; it does not attribute hidden controller causality.
- BigAI entries remain behavioral reconstruction only.
