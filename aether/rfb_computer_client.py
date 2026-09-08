"""Minimal stdlib RFB 3.x client for Aether native Computer Use.

This bridge is execution infrastructure. It knows only the RFB protocol and the
provider-native computer action vocabulary; it contains no task/UI semantics.
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import time
import zlib
from pathlib import Path
from typing import Any, Mapping


_KEYSYMS = {
    "BACKSPACE": 0xFF08, "TAB": 0xFF09, "ENTER": 0xFF0D, "RETURN": 0xFF0D,
    "ESC": 0xFF1B, "ESCAPE": 0xFF1B, "DELETE": 0xFFFF,
    "HOME": 0xFF50, "LEFT": 0xFF51, "UP": 0xFF52, "RIGHT": 0xFF53,
    "DOWN": 0xFF54, "PAGEUP": 0xFF55, "PAGEDOWN": 0xFF56, "END": 0xFF57,
    "SHIFT": 0xFFE1, "LSHIFT": 0xFFE1, "RSHIFT": 0xFFE2,
    "CTRL": 0xFFE3, "CONTROL": 0xFFE3, "LCTRL": 0xFFE3, "RCTRL": 0xFFE4,
    "ALT": 0xFFE9, "LALT": 0xFFE9, "RALT": 0xFFEA,
    "META": 0xFFE7, "LMETA": 0xFFE7, "RMETA": 0xFFE8,
    "SUPER": 0xFFEB, "WIN": 0xFFEB, "CMD": 0xFFEB,
    "SPACE": 0x20,
}
for _i in range(1, 13):
    _KEYSYMS[f"F{_i}"] = 0xFFBD + _i


def _keysym(value: str) -> int:
    raw = str(value)
    upper = raw.strip().upper().replace("_", "").replace("-", "")
    upper = {
        "ARROWLEFT": "LEFT", "ARROWRIGHT": "RIGHT",
        "ARROWUP": "UP", "ARROWDOWN": "DOWN",
        "COMMAND": "CMD", "OPTION": "ALT",
    }.get(upper, upper)
    if upper in _KEYSYMS:
        return _KEYSYMS[upper]
    if len(raw) == 1:
        return ord(raw)
    raise ValueError(f"unsupported RFB key: {value}")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = int(size)
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError(f"RFB peer closed with {remaining} bytes pending")
        chunks.append(chunk); remaining -= len(chunk)
    return b"".join(chunks)


def _png_rgb(width: int, height: int, rgb: bytes) -> bytes:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB framebuffer size mismatch")
    signature = b"\x89PNG\r\n\x1a\n"
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    scan = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    return signature + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scan, 6)) + chunk(b"IEND", b"")


class RFBClient:
    def __init__(self, host: str, port: int, *, timeout_s: float = 10.0) -> None:
        self.host, self.port = host, int(port)
        self.sock = socket.create_connection((host, int(port)), timeout=max(1.0, float(timeout_s)))
        self.sock.settimeout(max(1.0, float(timeout_s)))
        self.width = self.height = 0
        self._connect()

    def close(self) -> None:
        try: self.sock.close()
        except Exception: pass

    def _connect(self) -> None:
        banner = _recv_exact(self.sock, 12)
        if not banner.startswith(b"RFB "):
            raise RuntimeError(f"not an RFB server: {banner!r}")
        try:
            server_minor = int(banner[8:11])
        except ValueError as exc:
            raise RuntimeError(f"invalid RFB banner: {banner!r}") from exc
        minor = 8 if server_minor >= 8 else (7 if server_minor >= 7 else 3)
        self.sock.sendall(f"RFB 003.{minor:03d}\n".encode("ascii"))
        if minor >= 7:
            count = _recv_exact(self.sock, 1)[0]
            if count == 0:
                reason_len = struct.unpack(">I", _recv_exact(self.sock, 4))[0]
                raise RuntimeError(_recv_exact(self.sock, reason_len).decode("utf-8", "replace"))
            security = _recv_exact(self.sock, count)
            if 1 not in security:
                raise RuntimeError(f"RFB server requires unsupported security types: {list(security)}")
            self.sock.sendall(b"\x01")
            result = struct.unpack(">I", _recv_exact(self.sock, 4))[0]
            if result != 0:
                if minor >= 8:
                    reason_len = struct.unpack(">I", _recv_exact(self.sock, 4))[0]
                    reason = _recv_exact(self.sock, reason_len).decode("utf-8", "replace")
                else:
                    reason = f"security result {result}"
                raise RuntimeError(f"RFB authentication failed: {reason}")
        else:
            security = struct.unpack(">I", _recv_exact(self.sock, 4))[0]
            if security != 1:
                raise RuntimeError(f"RFB 3.3 requires unsupported security type: {security}")
        self.sock.sendall(b"\x01")  # shared session
        init = _recv_exact(self.sock, 24)
        self.width, self.height = struct.unpack(">HH", init[:4])
        name_len = struct.unpack(">I", init[20:24])[0]
        _recv_exact(self.sock, name_len)
        # Force a simple true-colour little-endian 32-bit pixel format so raw
        # framebuffer bytes have a deterministic B,G,R,pad layout.
        pf = struct.pack(">BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        self.sock.sendall(b"\x00\x00\x00\x00" + pf)
        # Raw encoding only. Servers may still send pseudo-encodings, which are
        # rejected rather than silently misdecoded.
        self.sock.sendall(struct.pack(">BBH i", 2, 0, 1, 0))

    def key(self, keysym: int, down: bool) -> None:
        self.sock.sendall(struct.pack(">BBHI", 4, 1 if down else 0, 0, int(keysym)))

    def pointer(self, x: int, y: int, mask: int = 0) -> None:
        x = max(0, min(int(x), max(0, self.width - 1)))
        y = max(0, min(int(y), max(0, self.height - 1)))
        self.sock.sendall(struct.pack(">BBHH", 5, int(mask) & 0xFF, x, y))

    def _with_modifiers(self, keys: list[str], callback: Any) -> None:
        syms = [_keysym(key) for key in keys]
        for sym in syms: self.key(sym, True)
        try: callback()
        finally:
            for sym in reversed(syms): self.key(sym, False)

    def apply(self, action: Mapping[str, Any]) -> None:
        kind = str(action.get("type") or "")
        keys = [str(key) for key in list(action.get("keys") or ())]
        if kind == "screenshot":
            return
        if kind == "wait":
            time.sleep(1.0); return
        if kind == "type":
            for char in str(action.get("text") or ""):
                sym = {"\n": 0xFF0D, "\r": 0xFF0D, "\t": 0xFF09, "\b": 0xFF08}.get(char, ord(char))
                self.key(sym, True); self.key(sym, False)
            return
        if kind == "keypress":
            syms = [_keysym(key) for key in keys]
            for sym in syms: self.key(sym, True)
            for sym in reversed(syms): self.key(sym, False)
            return
        x, y = int(action.get("x", 0)), int(action.get("y", 0))
        def mouse() -> None:
            if kind == "move":
                self.pointer(x, y, 0); return
            if kind in {"click", "double_click"}:
                button = str(action.get("button") or "left")
                mask = {"left": 1, "wheel": 2, "right": 4, "back": 128}.get(button)
                if mask is None:
                    raise ValueError(f"unsupported RFB click button: {button}")
                self.pointer(x, y, 0)
                for _ in range(2 if kind == "double_click" else 1):
                    self.pointer(x, y, mask); self.pointer(x, y, 0)
                return
            if kind == "scroll":
                self.pointer(x, y, 0)
                sx, sy = int(action.get("scroll_x", 0)), int(action.get("scroll_y", 0))
                def ticks(value: int) -> int: return max(0, (abs(value) + 99) // 100)
                for _ in range(ticks(sy)):
                    mask = 16 if sy > 0 else 8
                    self.pointer(x, y, mask); self.pointer(x, y, 0)
                for _ in range(ticks(sx)):
                    mask = 64 if sx > 0 else 32
                    self.pointer(x, y, mask); self.pointer(x, y, 0)
                return
            if kind == "drag":
                path = [dict(point) for point in list(action.get("path") or ())]
                if not path: raise ValueError("RFB drag path is empty")
                self.pointer(int(path[0]["x"]), int(path[0]["y"]), 0)
                self.pointer(int(path[0]["x"]), int(path[0]["y"]), 1)
                for point in path[1:]: self.pointer(int(point["x"]), int(point["y"]), 1)
                self.pointer(int(path[-1]["x"]), int(path[-1]["y"]), 0)
                return
            raise ValueError(f"unsupported RFB computer action: {kind}")
        self._with_modifiers(keys, mouse)

    def screenshot_png(self) -> bytes:
        self.sock.sendall(struct.pack(">BBHHHH", 3, 0, 0, 0, self.width, self.height))
        # Assemble the requested full framebuffer. Raw rectangles may arrive as
        # tiles, so copy each tile into one RGB buffer.
        rgb = bytearray(self.width * self.height * 3)
        while True:
            msg = _recv_exact(self.sock, 1)[0]
            if msg == 0:  # FramebufferUpdate
                _recv_exact(self.sock, 1)
                count = struct.unpack(">H", _recv_exact(self.sock, 2))[0]
                for _ in range(count):
                    x, y, w, h, encoding = struct.unpack(">HHHHi", _recv_exact(self.sock, 12))
                    if encoding != 0:
                        raise RuntimeError(f"unsupported RFB framebuffer encoding: {encoding}")
                    raw = _recv_exact(self.sock, w * h * 4)
                    for row in range(h):
                        src = raw[row * w * 4:(row + 1) * w * 4]
                        dst_base = ((y + row) * self.width + x) * 3
                        for col in range(w):
                            b, g, r = src[col * 4:col * 4 + 3]
                            dst = dst_base + col * 3
                            rgb[dst:dst + 3] = bytes((r, g, b))
                return _png_rgb(self.width, self.height, bytes(rgb))
            if msg == 2:  # Bell
                continue
            if msg == 3:  # ServerCutText
                _recv_exact(self.sock, 3); size = struct.unpack(">I", _recv_exact(self.sock, 4))[0]; _recv_exact(self.sock, size); continue
            raise RuntimeError(f"unsupported RFB server message type: {msg}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--actions-json", required=True)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    args = parser.parse_args()
    actions = json.loads(args.actions_json)
    if not isinstance(actions, list) or not actions:
        raise SystemExit("actions-json must be a non-empty list")
    client = RFBClient(args.host, args.port, timeout_s=args.timeout_s)
    action_error = ""
    try:
        for action in actions:
            try:
                if not isinstance(action, dict):
                    raise ValueError("computer action must be an object")
                client.apply(action)
            except Exception as exc:
                action_error = f"{type(exc).__name__}: {exc}"
                break
        raw = client.screenshot_png()
        Path(args.screenshot).write_bytes(raw)
        print(json.dumps({"ok": not bool(action_error), "width": client.width, "height": client.height, "bytes": len(raw), "action_error": action_error}, sort_keys=True))
    finally:
        client.close()
    return 1 if action_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
