sh -lc 'cd /app/pyknotid && python3 -m pip install -e . --no-build-isolation >/tmp/pyknotid_reinstall3.log && tail -n 10 /tmp/pyknotid_reinstall3.log && cd /app && python3 - <<"PY"
import numpy as np
print("numpy", np.__version__)
import pyknotid
import pyknotid.make as mk
import pyknotid.spacecurves as sp
k = sp.Knot(mk.three_twist(num_points=100))
out = k.alexander_polynomial(-1)
print("ok", type(out).__name__)
print(out)
PY'