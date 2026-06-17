# CLAUDE.md

## Development Commands

- **Install Package (Editable Mode)**: `pip install -e .`
- **Run Public Readiness Checks**: `make public-readiness`
- **Run Focused pytest Slice**: `make public-tests` or `pytest tests/test_public_manifest_repair_smoke.py tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py`
- **Build Wheel**: `python3 -m pip wheel --no-deps -w /private/tmp/harnesseng_wheels .`
- **Clean Temp Build Files**: `rm -rf build/ dist/ *.egg-info`
