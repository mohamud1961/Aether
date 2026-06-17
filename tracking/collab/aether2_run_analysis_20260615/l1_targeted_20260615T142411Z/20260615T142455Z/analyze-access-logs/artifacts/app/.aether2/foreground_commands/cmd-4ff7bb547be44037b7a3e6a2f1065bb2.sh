sh -lc 'python3 - <<"PY"
from pathlib import Path
text = Path("/app/report.txt").read_text()
lines = text.splitlines()
print("line_count", len(lines))
print("top_header", lines[2])
print("top_lines", lines[3:6])
PY'