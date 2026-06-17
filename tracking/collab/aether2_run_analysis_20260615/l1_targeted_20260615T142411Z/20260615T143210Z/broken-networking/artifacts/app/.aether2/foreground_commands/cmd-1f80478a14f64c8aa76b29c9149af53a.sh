sh -lc 'python3 - <<"PY"
import urllib.request
with urllib.request.urlopen("https://example.com", timeout=10) as r:
    print(r.status)
    print(r.read(120).decode("utf-8", "replace"))
PY'