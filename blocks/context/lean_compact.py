"""Lean Context Block: Minifies codebase file reads and compacts execution logs.

Interface: manage(history: list[dict], new_observation: dict) -> list[dict]
"""

from __future__ import annotations
import re
from typing import Any

def minify_source_code(content: str, filename_hint: str = "") -> str:
    """Strips comments and collapses excess whitespace to preserve token cache density."""
    if not isinstance(content, str):
        return content
        
    ext = filename_hint.split(".")[-1].lower() if "." in filename_hint else ""
    
    # Strip comments based on language
    if ext in ("py", "sh"):
        content = re.sub(r'(?m)^(?!\s*#!/)\s*#.*$', '', content)
    elif ext in ("js", "ts", "go", "c", "cpp", "java"):
        content = re.sub(r'/\*[\s\S]*?\*/|//.*$', '', content, flags=re.MULTILINE)
        
    # Collapse multiple spaces and linebreaks
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n\s*\n', '\n', content)
    return content.strip()

def compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Compacts raw terminal outputs into highly dense semantic cards."""
    obs = dict(observation)
    content = obs.get("content")
    if not isinstance(content, str):
        return obs
        
    # If stdout is massive, truncate the middle and keep only the critical heads and tails
    if len(content) > 1500:
        lines = content.splitlines()
        if len(lines) > 40:
            head = "\n".join(lines[:15])
            tail = "\n".join(lines[-25:])
            content = f"{head}\n\n... [TRUNCATED {len(lines) - 40} LINES OF COMPLETED OUTPUT FOR CACHE FRESHNESS] ...\n\n{tail}"
            
    # Apply source minification if we detect standard source file read output in trace
    if "cat " in content or "stdout:" in content:
        content = minify_source_code(content)
        
    obs["content"] = content
    return obs

def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Appends observations while compacting history and preserving the target anchor."""
    updated = list(history)
    
    # Process and compact the new observation
    processed_obs = compact_observation(new_observation)
    updated.append(processed_obs)
    
    # Enforce Target Anchor integrity on the very first user message
    if len(updated) > 1 and updated[1]["role"] == "user":
        user_msg = updated[1]
        content = user_msg.get("content", "")
        if "=== TARGET ANCHOR STATE ===" not in content:
            user_msg["content"] = "=== TARGET ANCHOR STATE ===\n- CWD: /workspace\n===========================\n\n" + content
            
    return updated
