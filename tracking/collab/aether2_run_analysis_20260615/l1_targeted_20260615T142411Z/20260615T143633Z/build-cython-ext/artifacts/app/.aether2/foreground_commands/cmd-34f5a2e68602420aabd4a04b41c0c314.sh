python3 - <<'PY'
import numpy as np
print('numpy', np.__version__)
import pyknotid
from pyknotid.spacecurves import Knot
import pyknotid.make as mk
import pyknotid.spacecurves as sp

k = sp.Knot(mk.three_twist(num_points=100))
out = k.alexander_polynomial(-1)
print('ok', type(out).__name__)
print(out)
PY