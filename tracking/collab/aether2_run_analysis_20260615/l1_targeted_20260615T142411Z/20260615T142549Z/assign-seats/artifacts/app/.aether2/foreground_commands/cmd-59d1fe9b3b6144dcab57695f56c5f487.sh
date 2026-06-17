python3 - <<'PY'
import os
for root, dirs, files in os.walk('/app'):
    for f in files:
        if f.endswith(('.pkl','.b64','.txt')):
            print(os.path.join(root,f))
PY