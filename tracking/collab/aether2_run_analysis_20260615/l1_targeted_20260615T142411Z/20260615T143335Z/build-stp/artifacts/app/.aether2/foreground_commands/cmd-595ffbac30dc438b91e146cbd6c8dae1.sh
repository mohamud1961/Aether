sh -lc 'python3 - <<"PY"
from pathlib import Path
p = Path("include/stp/AST/ASTNode.h")
text = p.read_text()
needle = "#include \"stp/Globals/Globals.h\"\n"
if "#include <cstdint>" not in text:
    text = text.replace(needle, needle + "#include <cstdint>\n")
    p.write_text(text)
    print("patched")
else:
    print("already patched")
PY
cmake --build build -j2 && cmake --install build'