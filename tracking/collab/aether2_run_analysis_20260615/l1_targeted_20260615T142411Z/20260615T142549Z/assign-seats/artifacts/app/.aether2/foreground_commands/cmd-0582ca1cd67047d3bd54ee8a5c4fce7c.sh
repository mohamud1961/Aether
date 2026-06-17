python3 - <<'PY'
import pickle, base64, pathlib
for p in [pathlib.Path('/app/deps/ask_alice.pkl'), pathlib.Path('/app/deps/ask_bob.pkl')]:
    print(f'--- {p.name} ---')
    obj = pickle.load(open(p,'rb'))
    print(repr(obj))
for p in [pathlib.Path('/app/deps/ask_charlie.b64')]:
    print(f'--- {p.name} ---')
    data = base64.b64decode(p.read_text())
    try:
        print(data.decode())
    except Exception:
        print(repr(data))
PY