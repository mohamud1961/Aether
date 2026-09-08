"""Generic read-only verifier probes: service/port/process and media/artifact.

These are capability classes, not task hooks: every probe takes typed fields
(host, port, url, pattern, path), composes a quoted command, and executes it
through the run's executor substrate so the probe observes the same world the
solver acted in (inside the container for docker runs).  Probes never mutate
state and never assert an environment fact they did not observe: a missing
tool is reported as ``tool_missing``, not silently skipped.
"""
from __future__ import annotations

from typing import Any


_PROBE_TIMEOUT_S = 30


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _run(executor: Any, command: str, *, timeout_s: int = _PROBE_TIMEOUT_S) -> Any:
    return executor.run_command(command, timeout_s=timeout_s)


def _process_listing_unavailable(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(
        marker in lowered
        for marker in (
            "command not found",
            "cannot get process list",
            "operation not permitted",
            "permission denied",
            "sysmond service not found",
            "procfs",
        )
    )


def probe_port(executor: Any, target: str) -> dict[str, Any]:
    """TCP connect probe. ``target`` is ``host:port`` or ``port`` (localhost)."""
    raw = target.strip()
    if ":" in raw:
        host, _, port_text = raw.rpartition(":")
    else:
        host, port_text = "127.0.0.1", raw
    host = host.strip() or "127.0.0.1"
    try:
        port = int(port_text)
    except ValueError:
        return {"error": f"invalid port in target: {target!r}"}
    code = (
        "import socket,sys\n"
        "s=socket.socket()\n"
        "s.settimeout(5)\n"
        f"rc=s.connect_ex(({host!r},{port}))\n"
        "s.close()\n"
        "print('open' if rc==0 else f'closed rc={rc}')\n"
    )
    result = _run(executor, f"python3 -c {_quote(code)}")
    if result.exit_code != 0:
        detail = (result.stderr or result.stdout)[:500]
        return {
            "host": host, "port": port, "state": "unknown",
            "error": detail,
            "probe_namespace": "executor_environment",
            "failure_class": _http_transport_failure_class(detail),
        }
    state = "open" if "open" in result.stdout else "closed"
    return {
        "host": host, "port": port, "state": state,
        "detail": result.stdout.strip()[:200],
        "probe_namespace": "executor_environment",
        "failure_class": "",
    }


def _http_transport_failure_class(detail: str) -> str:
    """Classify only mechanical HTTP transport failures, never task meaning."""
    lowered = str(detail or "").lower()
    if any(marker in lowered for marker in (
        "temporary failure in name resolution",
        "name or service not known",
        "nodename nor servname provided",
        "getaddrinfo failed",
    )):
        return "dns_resolution"
    if "connection refused" in lowered:
        return "connection_refused"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if any(marker in lowered for marker in ("certificate verify failed", "ssl:", "tls")):
        return "tls_error"
    return "transport_error"


def probe_http(executor: Any, url: str) -> dict[str, Any]:
    """HTTP GET probe: status code + response head from the executor namespace."""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        return {"error": f"probe_http requires an http(s) URL, got {url!r}"}
    code = (
        "import urllib.request,urllib.error,sys\n"
        f"req=urllib.request.Request({clean!r}, method='GET')\n"
        "try:\n"
        "    with urllib.request.urlopen(req, timeout=10) as resp:\n"
        "        body=resp.read(2000)\n"
        "        print('STATUS', resp.status)\n"
        "        print(body.decode('utf-8','replace'))\n"
        "except urllib.error.HTTPError as exc:\n"
        "    body=exc.read(2000)\n"
        "    print('STATUS', exc.code)\n"
        "    print(body.decode('utf-8','replace'))\n"
        "except Exception as exc:\n"
        "    print('ERROR', exc)\n"
        "    sys.exit(3)\n"
    )
    result = _run(executor, f"python3 -c {_quote(code)}")
    stdout = result.stdout
    if result.exit_code == 0 and stdout.startswith("STATUS "):
        first, _, rest = stdout.partition("\n")
        return {
            "url": clean,
            "reachable": True,
            "status": int(first.split()[1]),
            "response_observed": True,
            "body_head": rest[:2000],
            "probe_namespace": "executor_environment",
            "failure_class": "",
        }
    detail = (stdout or result.stderr)[:500]
    return {
        "url": clean,
        "reachable": False,
        "response_observed": False,
        "detail": detail,
        "probe_namespace": "executor_environment",
        "failure_class": _http_transport_failure_class(detail),
    }


def probe_process(executor: Any, pattern: str) -> dict[str, Any]:
    """List live processes whose command line matches ``pattern`` (read-only)."""
    clean = pattern.strip()
    if not clean:
        return {"error": "probe_process requires a pattern"}
    # Bracket the first character so the probe's own command line (which
    # contains the literal pattern) never matches itself.
    if clean[0].isalnum():
        regex = f"[{clean[0]}]{clean[1:]}"
    else:
        regex = clean
    result = _run(executor, f"pgrep -fal {_quote(regex)} || true")
    # Harbor/container transports may surface shell diagnostics on stdout even
    # when a local shell would write them to stderr.  Treat either stream as
    # probe-tool telemetry so "command not found" can never become a process
    # match merely because the transport merged streams.
    if _process_listing_unavailable((result.stdout or "") + "\n" + (result.stderr or "")):
        # Fall back to ps parsing when pgrep is absent or host policy denies it.
        result = _run(executor, f"ps ax -o pid=,command= | grep -e {_quote(regex)} || true")
        if _process_listing_unavailable((result.stdout or "") + "\n" + (result.stderr or "")):
            # Minimal Linux task images may intentionally omit both pgrep and ps
            # while still exposing the authoritative process table through procfs.
            # Use the same Python runtime already required by the port/http probes,
            # and exclude the probe process plus its ancestor shell chain so the
            # literal regex embedded in this command can never self-match.
            proc_code = (
                "import os,re,sys\n"
                f"pattern={clean!r}\n"
                "try:\n"
                "    matcher=re.compile(pattern)\n"
                "except re.error as exc:\n"
                "    print('AETHER_REGEX_ERROR', str(exc))\n"
                "    sys.exit(4)\n"
                "if not os.path.isdir('/proc'):\n"
                "    print('AETHER_PROC_UNAVAILABLE')\n"
                "    sys.exit(5)\n"
                "ancestors=set()\n"
                "pid=os.getpid()\n"
                "while pid > 1 and pid not in ancestors:\n"
                "    ancestors.add(pid)\n"
                "    try:\n"
                "        stat=open(f'/proc/{pid}/stat','r',encoding='utf-8',errors='replace').read()\n"
                "        tail=stat[stat.rfind(')')+1:].split()\n"
                "        pid=int(tail[1]) if len(tail) > 1 else 0\n"
                "    except Exception:\n"
                "        break\n"
                "readable=0\n"
                "matches=[]\n"
                "for name in os.listdir('/proc'):\n"
                "    if not name.isdigit():\n"
                "        continue\n"
                "    proc_pid=int(name)\n"
                "    if proc_pid in ancestors:\n"
                "        continue\n"
                "    try:\n"
                "        raw=open(f'/proc/{name}/cmdline','rb').read()\n"
                "    except (FileNotFoundError, PermissionError, ProcessLookupError):\n"
                "        continue\n"
                "    readable += 1\n"
                "    command=raw.replace(b'\\x00', b' ').decode('utf-8','replace').strip()\n"
                "    if command and matcher.search(command):\n"
                "        matches.append(f'{name} {command}')\n"
                "if readable == 0:\n"
                "    print('AETHER_PROC_UNAVAILABLE')\n"
                "    sys.exit(5)\n"
                "for row in matches[:10]:\n"
                "    print(row)\n"
            )
            result = _run(executor, f"python3 -c {_quote(proc_code)}")
            if result.exit_code != 0:
                detail = (result.stdout or result.stderr).strip()
                if result.exit_code == 4 and detail.startswith("AETHER_REGEX_ERROR"):
                    return {
                        "pattern": clean,
                        "state": "unknown",
                        "running": False,
                        "match_count": 0,
                        "matches": [],
                        "error": "invalid process regex: " + detail.partition(" ")[2][:300],
                    }
                return {
                    "pattern": clean,
                    "state": "unknown",
                    "running": False,
                    "match_count": 0,
                    "matches": [],
                    "error": "tool_unavailable: process listing unavailable",
                }
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {
        "pattern": clean,
        "running": bool(lines),
        "match_count": len(lines),
        "matches": lines[:10],
    }


def probe_job(executor: Any, target: str) -> dict[str, Any]:
    """Observe one harness-registered managed job generation and terminal code."""
    clean = target.strip()
    if not clean:
        return {"error": "probe_job requires a job_id or registered job name"}
    probe = executor.probe_job(clean)
    if not probe.found:
        return {
            "target": clean, "found": False, "status": "unknown",
            "completed": False, "success": False,
            "outcome_detail": probe.detail or "job not found", "error": "",
        }
    return {
        "target": clean,
        "found": True,
        "job_id": probe.job_id,
        "process_id": probe.process_id,
        "status": probe.status,
        "completed": probe.completed,
        "job_succeeded": probe.succeeded,
        "job_exit_code": probe.exit_code,
        "detail": probe.detail,
        "process_generation": probe.process_generation,
        "process_generation_verified": probe.process_generation_verified,
        "lifecycle_authority": probe.lifecycle_authority,
        "pid": probe.pid,
        "success": True,
    }


def inspect_artifact_probe(executor: Any, path: str) -> dict[str, Any]:
    """Generic artifact/media inspection: type, size, hash, type-appropriate metadata.

    Uses `file`/`stat`/`sha256sum` plus best-effort media metadata (`ffprobe`
    for audio/video, `pdftotext` head for PDFs).  Missing tools are reported
    truthfully; nothing is mutated.
    """
    clean = path.strip()
    if not clean:
        return {"error": "inspect_artifact requires a path"}
    q = _quote(clean)
    exists = _run(executor, f"test -e {q} && echo yes || echo no")
    if "yes" not in exists.stdout:
        return {"path": clean, "exists": False}
    row: dict[str, Any] = {"path": clean, "exists": True}

    file_out = _run(executor, f"file -b {q} 2>/dev/null || echo tool_missing:file")
    row["file_type"] = file_out.stdout.strip()[:300]

    size_out = _run(
        executor,
        f"stat -c %s {q} 2>/dev/null || stat -f %z {q} 2>/dev/null || echo unknown",
    )
    row["size_bytes"] = size_out.stdout.strip()[:40]

    # File metadata is first-class verifiable state: permissions, owner, and
    # mtime.  (Observed live: a correct openssl task could not be verified
    # because no read-only surface exposed the key file's mode.)
    meta_out = _run(
        executor,
        f"stat -c '%a %U %Y' {q} 2>/dev/null || stat -f '%Lp %Su %m' {q} 2>/dev/null || echo unknown",
    )
    meta_fields = meta_out.stdout.strip().split()
    if len(meta_fields) >= 3 and meta_fields[0] != "unknown":
        row["mode"] = meta_fields[0][:8]
        row["owner"] = meta_fields[1][:40]
        row["mtime_epoch"] = meta_fields[2][:20]
    else:
        row["mode"] = "unknown"

    lowered = row["file_type"].lower()
    if "directory" in lowered:
        # A directory's presence/type/metadata is useful, but hashing or reading
        # its raw bytes is neither a semantic directory-content observation nor
        # a portable operation. Keep this route explicitly metadata-only.
        row["sha256"] = "not_applicable:directory"
        row["semantic_content_available"] = False
        row["semantic_content_status"] = "metadata_only: directory contents were not traversed"
        return row

    hash_out = _run(
        executor,
        f"sha256sum {q} 2>/dev/null || shasum -a 256 {q} 2>/dev/null || echo tool_missing",
    )
    row["sha256"] = hash_out.stdout.strip().split()[0][:64] if hash_out.stdout.strip() else "unknown"

    if any(token in lowered for token in ("video", "audio", "mp4", "matroska", "webm")):
        ff = _run(
            executor,
            f"ffprobe -v error -show_format -show_streams {q} 2>&1 | head -60 || echo tool_missing:ffprobe",
        )
        row["media_metadata"] = ff.stdout.strip()[:3000] or "tool_missing:ffprobe"
    elif "pdf" in lowered:
        pdf = _run(
            executor,
            f"pdftotext -l 1 {q} - 2>/dev/null | head -40 || echo tool_missing:pdftotext",
        )
        row["pdf_text_head"] = pdf.stdout.strip()[:2000] or "tool_missing:pdftotext"
    elif any(token in lowered for token in ("image", "png", "jpeg", "bitmap")):
        dims = _run(
            executor,
            f"identify {q} 2>/dev/null | head -3 || python3 -c \"import struct,sys;print('no_image_tool')\"",
        )
        row["image_metadata"] = dims.stdout.strip()[:500] or "tool_missing:identify"
        row["semantic_content_available"] = False
        row["semantic_content_status"] = (
            "metadata_only: verifier artifact probe does not extract image semantics"
        )
    else:
        head = _run(executor, f"head -c 4000 {q} | tr -d '\\000' | head -40")
        row["content_head"] = head.stdout[:2000]
    return row
