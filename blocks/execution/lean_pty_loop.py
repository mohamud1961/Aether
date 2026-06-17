"""Lean PTY Execution Block: Manages persistent shell state and self-checks.

Interface: run_loop(model, tools, context, max_steps, tool_definitions) -> dict
"""

from __future__ import annotations
import re
import os
import json
from typing import Any, Callable
from blocks.execution.flat_loop import _init_lifecycle_state, _record_lifecycle_event, _write_terminal_outcome, _export_lifecycle_summary, _finalize_cleanup_state

# Helper script for Service Probing
SERVICE_PROBER_CODE = """
import socket, sys, subprocess, os
def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        return False

def check_vnc(display):
    try:
        res = subprocess.run([
            "vncsnapshot", "-allowblank", f"localhost:{display}", "/tmp/probe_vnc.png"
        ], capture_output=True, timeout=10)
        return res.returncode == 0
    except Exception:
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 check_service.py <port> [display_index]")
        sys.exit(1)
    port = int(sys.argv[1])
    display = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    port_ok = check_port(port)
    vnc_ok = check_vnc(display) if display is not None else True
    
    import json
    print(json.dumps({
        "port": port,
        "port_listening": port_ok,
        "vnc_display": display,
        "vnc_handshake_successful": vnc_ok,
        "status": "READY" if (port_ok and vnc_ok) else "FAILED"
    }, indent=2))
"""

def parse_state_mutations(command: str, current_cwd: str) -> tuple[str, dict[str, str]]:
    """Parses CWD and exports to maintain terminal state persistence manually."""
    new_cwd = current_cwd
    env_updates = {}
    
    # Check for simple directory changes
    cd_match = re.search(r'\bcd\s+([^\s;&|]+)', command)
    if cd_match:
        target_dir = cd_match.group(1).strip("'\"")
        if target_dir == "..":
            parts = current_cwd.rstrip("/").split("/")
            if len(parts) > 1:
                new_cwd = "/".join(parts[:-1]) or "/"
        elif target_dir.startswith("/"):
            new_cwd = target_dir
        else:
            new_cwd = f"{current_cwd.rstrip('/')}/{target_dir}"
            
    # Check for export statements
    export_matches = re.finditer(r'\bexport\s+([A-Za-z_][A-Za-z0-9_]*)=([^\s;&|]+)', command)
    for m in export_matches:
        key = m.group(1)
        val = m.group(2).strip("'\"")
        env_updates[key] = val
        
    return new_cwd, env_updates

def run_preflight(tools: dict, task_prompt: str) -> tuple[str | None, str | None, dict[str, Any]]:
    """Runs a generic environment probe inside the container using raw_bash."""
    probes = [
        "for x in python3 python qemu-system-i386 qemu-system-x86_64 ffmpeg ffprobe tesseract yt-dlp nginx websockify novnc vncsnapshot socat; do command -v $x >/dev/null 2>&1 && echo \"bin:$x=yes\" || echo \"bin:$x=no\"; done",
        "find /app -maxdepth 3 \\( -name '*.img' -o -name '*.iso' -o -name '*.mp4' -o -name '*.mkv' -o -name 'win311.img' \\) -print 2>/dev/null || true",
        "curl -I -s --max-time 5 https://www.google.com >/dev/null && echo 'net:ok' || echo 'net:offline'"
    ]
    probe_cmd = "\n".join(probes)
    tool_call = {
        "name": "raw_bash",
        "arguments": {"command": f"cd /app && {probe_cmd}"}
    }
    
    try:
        res = tools["raw_bash"](tool_call)
        stdout = res.get("stdout", "")
    except Exception:
        stdout = ""
        
    report = {
        "has_qemu": "bin:qemu-system-i386=yes" in stdout or "bin:qemu-system-x86_64=yes" in stdout,
        "has_ffmpeg": "bin:ffmpeg=yes" in stdout,
        "has_ytdlp": "bin:yt-dlp=yes" in stdout,
        "has_net": "net:ok" in stdout,
        "has_images": any(ext in stdout for ext in [".img", ".iso", ".mp4", ".mkv", "win311.img"])
    }
    
    # Generic asset and dependency checks based on prompt triggers
    if "win311.img" in task_prompt.lower() or "qemu" in task_prompt.lower():
        if not report["has_images"]:
            return "invalid_due_to_environment", "Missing required disk image (win311.img) in sandbox", report
            
    return None, None, report

def get_autopsy_card(tool_name: str, exit_code: int, stdout: str, stderr: str) -> str | None:
    """Parses failures into structured diagnostic cards for the active context."""
    if exit_code == 0:
        return None
        
    error_content = f"{stdout}\n{stderr}".lower()
    
    if "connection refused" in error_content or "unable to connect" in error_content:
        return (
            "=== SERVICE AUTOPSY ===\n"
            "- Diagnosis: Port connection refused.\n"
            "- Advice: Ensure the background process (QEMU/nginx) launched successfully, check display index bindings, and verify using `python3 /app/check_service.py`."
        )
    elif "command not found" in error_content or "not found" in error_content:
        return (
            "=== TOOLCHAIN AUTOPSY ===\n"
            "- Diagnosis: A required command was not found.\n"
            "- Advice: Install missing packages using `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y <package>`."
        )
    elif "no such file" in error_content or "does not exist" in error_content:
        return (
            "=== FILE AUTOPSY ===\n"
            "- Diagnosis: A required disk image, file, or script path is missing.\n"
            "- Advice: Verify absolute/relative file paths and check directory structure using `find /app -maxdepth 3`."
        )
    return None

def run_loop(
    model: Any,
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Runs the PTY execution loop with environment preflight, service readiness, and failure autopsies."""
    if max_steps <= 0:
        raise ValueError("max_steps must be >= 1")
        
    history = list(context.get("history", []))
    manage_history = context["manage_history"]
    env_info = context.get("env_info", {})
    task_prompt = context.get("task_prompt", "")
    
    steps: list[dict[str, Any]] = []
    status = "max_steps_exhausted"
    last_completion: dict[str, Any] = {}
    terminal_reason = "step_budget_exhausted"
    terminal_step = max_steps - 1
    
    lifecycle = _init_lifecycle_state()
    _record_lifecycle_event(lifecycle, "loop_entered")
    
    # 1. Start Persistent Shell State
    current_cwd = env_info.get("cwd", "/workspace")
    active_env: dict[str, str] = {}
    
    try:
        # 2. RUN GENERIC PREFLIGHT PROBES
        preflight_status, preflight_msg, preflight_report = run_preflight(tools, task_prompt)
        if preflight_status:
            status = preflight_status
            terminal_reason = preflight_msg
            _record_lifecycle_event(lifecycle, "preflight_not_successful")
            return {
                "status": status,
                "history": history,
                "steps": [],
                "step_count": 0,
                "last_completion": {},
                "preflight_failed": True,
                "preflight_reason": preflight_msg
            }
            
        # 3. Preload the Service Prober utility into the container
        write_prober_call = {
            "name": "raw_bash",
            "arguments": {
                "command": f"cat <<'EOF' > /app/check_service.py\n{SERVICE_PROBER_CODE.strip()}\nEOF\nchmod +x /app/check_service.py"
            }
        }
        tools["raw_bash"](write_prober_call)
        
        for step in range(max_steps):
            terminal_step = step
            complete_kwargs = {}
            if tool_definitions:
                complete_kwargs["tools"] = tool_definitions
                
            completion = model.complete(history, **complete_kwargs)
            last_completion = completion
            
            assistant_text = completion.get("text") or ""
            tool_calls = completion.get("tool_calls")
            
            if "[TASK_COMPLETE]" in assistant_text or not tool_calls:
                status = "completed"
                terminal_reason = "no_tool_calls"
                history = manage_history(history, {"role": "assistant", "content": assistant_text})
                steps.append({
                    "step": step,
                    "tool_calls": 0,
                    "status": "completed",
                    "completion": completion
                })
                break
                
            history = manage_history(
                history,
                {
                    "role": "assistant",
                    "content": assistant_text if assistant_text else None,
                    "tool_calls": tool_calls,
                }
            )
            
            step_result = {
                "step": step,
                "tool_calls": len(tool_calls),
                "results": [],
                "completion": completion,
            }
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                
                if tool_name == "raw_bash":
                    args = tool_call.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {"command": args}
                            
                    cmd = args.get("command", "")
                    
                    # Update shell state
                    new_cwd, env_updates = parse_state_mutations(cmd, current_cwd)
                    active_env.update(env_updates)
                    
                    env_prefix = " ".join(f"export {k}={v} &&" for k, v in active_env.items())
                    cmd_with_state = f"cd {current_cwd} && {env_prefix} {cmd}".strip(" &&")
                    
                    args["command"] = cmd_with_state
                    tool_call["arguments"] = args
                    
                    result = tools["raw_bash"](tool_call)
                    current_cwd = new_cwd
                else:
                    result = {"error": f"unsupported_tool:{tool_name}"}
                    
                exit_code = result.get("exit_code", 0)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                
                obs_content = f"{tool_name or 'unknown'} exit={exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}".strip()
                
                # 4. RUN RUNTIME FAILURE AUTOPSY
                autopsy = get_autopsy_card(tool_name, exit_code, stdout, stderr)
                if autopsy:
                    obs_content += f"\n\n{autopsy}"
                    
                history = manage_history(
                    history,
                    {
                        "role": "tool",
                        "name": tool_name or "unknown",
                        "tool_call_id": tool_call.get("id"),
                        "content": obs_content,
                    }
                )
                step_result["results"].append(result)
                
            steps.append(step_result)
            
    except Exception as err:
        status = "error"
        terminal_reason = "loop_exception"
        _record_lifecycle_event(lifecycle, "execution_error")
        raise err
    finally:
        _finalize_cleanup_state(lifecycle, reason_codes=["loop_cleanup_completed"])
        _write_terminal_outcome(lifecycle, terminal_status=status, reason_code=terminal_reason, step=terminal_step)
        _record_lifecycle_event(lifecycle, "cleanup_completed")
        _record_lifecycle_event(lifecycle, "loop_exited")
        
    result = {
        "status": status,
        "history": history,
        "steps": steps,
        "step_count": len(steps),
        "last_completion": last_completion,
    }
    result.update(_export_lifecycle_summary(lifecycle))
    return result
