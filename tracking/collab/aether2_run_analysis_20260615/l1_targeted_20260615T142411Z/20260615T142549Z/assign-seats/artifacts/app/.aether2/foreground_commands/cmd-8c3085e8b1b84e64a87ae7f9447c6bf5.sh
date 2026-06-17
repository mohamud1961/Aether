python3 - <<'PY'
import pickle, base64, pathlib
print(pathlib.Path('/app/deps/clue.txt').read_text().strip())
print(pathlib.Path('/app/deps/frankie_preferences.txt').read_text().strip())
print(pickle.load(open('/app/deps/ask_alice.pkl','rb')))
print(pickle.load(open('/app/deps/ask_bob.pkl','rb')))
print(base64.b64decode(pathlib.Path('/app/deps/ask_charlie.b64').read_text()).decode().strip())
PY