from __future__ import annotations

import asyncio
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import zlib
from dataclasses import dataclass
from pathlib import Path

from aether.rfb_computer_client import RFBClient


@dataclass
class _Completed:
    return_code: int
    stdout: str = ""
    stderr: str = ""


class _LocalAsyncEnvironment:
    async def exec(self, *, command: str, cwd: str | None, env: dict[str,str] | None, timeout_sec: int) -> _Completed:
        def _run() -> _Completed:
            row=subprocess.run(["/bin/sh","-lc",command],cwd=cwd,text=True,capture_output=True,timeout=timeout_sec)
            return _Completed(row.returncode,row.stdout,row.stderr)
        return await asyncio.to_thread(_run)
    async def upload_file(self, source: Path, destination: str) -> None:
        await asyncio.to_thread(shutil.copyfile,source,destination)
    async def download_file(self, source: str, destination: Path) -> None:
        await asyncio.to_thread(shutil.copyfile,source,destination)


def _run_scenario(callback):
    from aether.harbor_executor import HarborEnvironmentExecutor
    async def _main():
        with tempfile.TemporaryDirectory(prefix="aether-rfb-harbor-") as tmp:
            root=Path(tmp)/"workspace"; state=Path(tmp)/"state"; root.mkdir()
            executor=HarborEnvironmentExecutor(_LocalAsyncEnvironment(),event_loop=asyncio.get_running_loop(),workspace_root=str(root),local_state_dir=state)
            try: return await asyncio.to_thread(callback,executor,root)
            finally: await asyncio.to_thread(executor.close)
    return asyncio.run(_main())


class _RFBServer:
    def __init__(self, *, vnc_range: bool = False) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if vnc_range:
            for port in range(5999, 5899, -1):
                try:
                    self.sock.bind(("127.0.0.1", port)); break
                except OSError:
                    continue
            else:
                raise RuntimeError("no test RFB port available")
        else:
            self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(8); self.sock.settimeout(0.2)
        self.stop = threading.Event()
        self.events: list[tuple] = []
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> bytes:
        out=b""
        while len(out) < n:
            chunk=conn.recv(n-len(out))
            if not chunk: raise ConnectionError("peer closed")
            out += chunk
        return out

    def _serve(self) -> None:
        while not self.stop.is_set():
            try: conn,_addr=self.sock.accept()
            except socket.timeout: continue
            except OSError: break
            conn.settimeout(1.5)
            try:
                conn.sendall(b"RFB 003.008\n")
                version=self._recv_exact(conn,12)
                if not version.startswith(b"RFB "): continue
                conn.sendall(b"\x01\x01")
                if self._recv_exact(conn,1) != b"\x01": continue
                conn.sendall(b"\x00\x00\x00\x00")
                self._recv_exact(conn,1)  # ClientInit
                width,height=2,1
                server_pf=struct.pack(">BBBBHHHBBB3x",32,24,0,1,255,255,255,16,8,0)
                name=b"aether-test-rfb"
                conn.sendall(struct.pack(">HH",width,height)+server_pf+struct.pack(">I",len(name))+name)
                self._recv_exact(conn,20)  # SetPixelFormat
                enc_header=self._recv_exact(conn,4)
                count=struct.unpack(">H",enc_header[2:4])[0]
                self._recv_exact(conn,4*count)
                while True:
                    kind=self._recv_exact(conn,1)[0]
                    if kind == 4:
                        rest=self._recv_exact(conn,7)
                        down=bool(rest[0]); keysym=struct.unpack(">I",rest[3:7])[0]
                        self.events.append(("key",down,keysym))
                    elif kind == 5:
                        rest=self._recv_exact(conn,5)
                        mask=rest[0]; x,y=struct.unpack(">HH",rest[1:5])
                        self.events.append(("pointer",mask,x,y))
                    elif kind == 3:
                        rest=self._recv_exact(conn,9)
                        incremental=rest[0]
                        x,y,w,h=struct.unpack(">HHHH",rest[1:9])
                        self.events.append(("frame_request",incremental,x,y,w,h))
                        # Pixel 0 red, pixel 1 green in forced B,G,R,pad layout.
                        raw=b"\x00\x00\xff\x00\x00\xff\x00\x00"
                        conn.sendall(b"\x00\x00\x00\x01" + struct.pack(">HHHHi",0,0,2,1,0) + raw)
                        break
                    else:
                        raise RuntimeError(f"unexpected client message {kind}")
            except (ConnectionError, socket.timeout, OSError):
                pass
            finally:
                try: conn.close()
                except Exception: pass

    def close(self) -> None:
        self.stop.set()
        try: self.sock.close()
        except Exception: pass
        self.thread.join(timeout=2)


def _png_rgb(raw: bytes) -> tuple[int,int,bytes]:
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    pos=8; width=height=0; data=b""
    while pos < len(raw):
        n=struct.unpack(">I",raw[pos:pos+4])[0]; kind=raw[pos+4:pos+8]; payload=raw[pos+8:pos+8+n]; pos += 12+n
        if kind == b"IHDR": width,height=struct.unpack(">II",payload[:8])
        elif kind == b"IDAT": data += payload
        elif kind == b"IEND": break
    scan=zlib.decompress(data)
    assert scan[0] == 0
    return width,height,scan[1:]


def test_stdlib_rfb_client_executes_input_and_returns_exact_png() -> None:
    server=_RFBServer()
    try:
        client=RFBClient("127.0.0.1",server.port,timeout_s=2)
        try:
            client.apply({"type":"click","button":"left","x":1,"y":0})
            client.apply({"type":"keypress","keys":["CTRL","A"]})
            client.apply({"type":"keypress","keys":["ARROWLEFT"]})
            raw=client.screenshot_png()
        finally:
            client.close()
        width,height,rgb=_png_rgb(raw)
        assert (width,height)==(2,1)
        assert rgb == b"\xff\x00\x00\x00\xff\x00"
        assert ("pointer",1,1,0) in server.events
        assert ("key",True,0xFFE3) in server.events
        assert ("key",True,ord("A")) in server.events
        assert ("key",True,0xFF51) in server.events
        assert any(row[0] == "frame_request" for row in server.events)
    finally:
        server.close()


def test_harbor_computer_backend_discovers_live_rfb_and_preserves_fresh_pixels() -> None:
    from aether.harbor_executor import HarborEnvironmentExecutor
    server=_RFBServer(vnc_range=True)
    try:
        def scenario(executor: HarborEnvironmentExecutor, _root) -> None:
            info=executor.computer_backend_info()
            assert info["available"] is True
            assert info["backend"] == f"rfb:127.0.0.1:{server.port}"
            result=executor.computer_action({"actions":[
                {"type":"move","x":1,"y":0},
                {"type":"click","button":"left","x":1,"y":0},
                {"type":"type","text":"A"},
            ]})
            assert result.success is True
            assert (result.width,result.height)==(2,1)
            width,height,rgb=_png_rgb(result.screenshot_bytes)
            assert (width,height)==(2,1)
            assert rgb == b"\xff\x00\x00\x00\xff\x00"
            assert result.state_delta["computer_backend"] == f"rfb:127.0.0.1:{server.port}"
            assert result.state_delta["computer_action_count"] == 3
        _run_scenario(scenario)
    finally:
        server.close()

def test_harbor_rfb_discovery_uses_socket_inventory_not_vnc_port_range(monkeypatch) -> None:
    from aether.harbor_executor import HarborEnvironmentExecutor
    import os
    server=_RFBServer(vnc_range=False)
    # Ensure the chosen ephemeral port is actually outside the conventional VNC range.
    if 5900 <= server.port <= 5999:
        server.close(); server=_RFBServer(vnc_range=False)
    assert not (5900 <= server.port <= 5999)
    try:
        def scenario(executor: HarborEnvironmentExecutor, root: Path) -> None:
            bindir=root/'bin'; bindir.mkdir()
            ss=bindir/'ss'
            ss.write_text('#!/bin/sh\nprintf %s\\n '+repr(f'LISTEN 0 8 127.0.0.1:{server.port} 0.0.0.0:*')+'\n',encoding='utf-8')
            ss.chmod(0o755)
            old=os.environ.get('PATH','')
            os.environ['PATH']=str(bindir)+os.pathsep+old
            try:
                info=executor.computer_backend_info()
            finally:
                os.environ['PATH']=old
            assert info['available'] is True
            assert info['backend'] == f'rfb:127.0.0.1:{server.port}'
        _run_scenario(scenario)
    finally:
        server.close()
