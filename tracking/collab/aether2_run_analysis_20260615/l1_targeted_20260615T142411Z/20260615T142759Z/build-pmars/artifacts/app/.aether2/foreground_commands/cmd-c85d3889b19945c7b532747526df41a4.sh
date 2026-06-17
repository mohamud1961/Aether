sh -lc 'cd /app/pmars-0.9.4 && python3 - <<"PY"
from pathlib import Path
p=Path("src/Makefile")
text=p.read_text()
text=text.replace("CFLAGS += -O -DEXT94 -DXWINGRAPHX -DPERMUTATE -DRWLIMIT ", "CFLAGS += -O -DEXT94 -DPERMUTATE -DRWLIMIT ")
text=text.replace("LIB = -L/usr/X11R6/lib -lX11\t\t# enable this one for X11\n", "LIB =\n")
text=text.replace("sim.o: curdisp.c uidisp.c lnxdisp.c xwindisp.c\n", "sim.o: curdisp.c uidisp.c lnxdisp.c\n")
text=text.replace("xwindisp.c: xwindisp.h pmarsicn.h\n\n", "")
p.write_text(text)
print(text)
PY
make -C src clean && make -C src && install -m 0755 src/pmars /usr/local/bin/pmars && echo INSTALLED && ldd /usr/local/bin/pmars | grep -i X11 || true && /usr/local/bin/pmars -b -r 50 -f flashpaper.red rave.red | tail -n 1'