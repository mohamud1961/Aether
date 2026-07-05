"""Generic task-surface capability classification for EnvMap/audit.

This module intentionally does not recognize benchmark task names.  It uses
public task metadata, instructions, and visible file extensions as a coverage
corpus to expose generic workbench needs to the architect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import re


@dataclass(frozen=True)
class CapabilityNeed:
    capability: str
    confidence: str
    source: str
    required_tools: tuple[str, ...] = ()
    verifier_needs: tuple[str, ...] = ()
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["inferred_not_fact"] = True
        return data


_TOOL_BY_CAPABILITY: dict[str, tuple[str, ...]] = {
    "long_running_command": ("bash", "make", "cmake", "gcc", "g++", "cargo", "python", "python3"),
    "background_service": ("curl", "wget", "ss", "netstat", "lsof"),
    "http_service": ("curl", "wget", "nginx"),
    "ssh_or_telnet_service": ("ssh", "sshd", "telnet"),
    "qemu_vm": ("qemu-system-i386", "qemu-system-x86_64", "qemu-img", "expect"),
    "image_processing": ("python", "python3", "ffmpeg", "ffprobe", "tesseract", "pdftotext", "convert", "magick"),
    "video_processing": ("ffmpeg", "ffprobe", "python", "python3"),
    "ocr_pdf_document": ("tesseract", "pdftotext", "python", "python3", "convert", "magick"),
    "ml_training_or_inference": ("python", "python3", "pip", "uv", "R", "Rscript"),
    "scientific_computing": ("python", "python3", "R", "Rscript", "julia", "octave"),
    "database": ("sqlite3", "psql", "mysql"),
    "compiler_build": ("make", "cmake", "gcc", "g++", "clang", "clang++", "pkg-config"),
    "rust_build": ("cargo", "rustc"),
    "ocaml_coq_build": ("ocaml", "opam", "dune", "coqtop", "coqc"),
    "binary_reverse_engineering": ("file", "strings", "readelf", "objdump", "gdb", "xxd", "hexdump"),
    "crypto_security": ("openssl", "python", "python3", "john", "hashcat"),
    "network_download": ("curl", "wget", "git", "pip", "uv"),
}
_VERIFIER_BY_CAPABILITY: dict[str, tuple[str, ...]] = {
    "long_running_command": ("sandboxed_execution", "log_tail_handles"),
    "background_service": ("process_probe", "service_log_tail", "sandboxed_execution"),
    "http_service": ("http_probe", "port_probe", "sandboxed_execution"),
    "ssh_or_telnet_service": ("port_probe", "interactive_probe"),
    "qemu_vm": ("background_process_probe", "port_probe", "interactive_or_vnc_probe"),
    "image_processing": ("artifact_preview", "image_metadata", "sandboxed_execution"),
    "video_processing": ("sample_video_frames", "media_metadata", "sandboxed_execution"),
    "ocr_pdf_document": ("ocr_or_pdf_text_probe", "artifact_preview"),
    "ml_training_or_inference": ("sandboxed_execution", "metric_artifact_inspection"),
    "scientific_computing": ("sandboxed_execution", "numeric_output_check"),
    "database": ("database_file_or_service_probe", "sandboxed_execution"),
    "compiler_build": ("sandboxed_execution", "build_log_handles"),
    "rust_build": ("sandboxed_execution", "build_log_handles"),
    "ocaml_coq_build": ("sandboxed_execution", "build_log_handles"),
    "binary_reverse_engineering": ("binary_artifact_probe", "sandboxed_execution"),
    "crypto_security": ("sandboxed_execution", "artifact_probe"),
    "network_download": ("network_fact_probe",),
}

_KEYWORDS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("video_processing", ("video", "mp4", "ffmpeg", "frame", "fps"), ("video-processing", "video")),
    ("image_processing", ("image", "png", "jpeg", "jpg", "render", "screenshot", "pixel", "segmentation"), ("images", "image")),
    ("ocr_pdf_document", ("ocr", "pdf", "document", "tesseract", "invoice", "receipt"), ("ocr", "pdf")),
    ("qemu_vm", ("qemu", "vnc", "virtual machine", "vm", "boot", "bios"), ("qemu", "vm")),
    ("background_service", ("server", "daemon", "background", "service", "listen", "port"), ("service", "server")),
    ("http_service", ("http", "nginx", "webserver", "curl", "localhost", "port 80"), ("web", "http")),
    ("ssh_or_telnet_service", ("ssh", "telnet", "login prompt"), ("ssh", "telnet")),
    ("ml_training_or_inference", ("train", "model", "neural", "torch", "tensorflow", "sklearn", "fasttext", "caffe", "inference"), ("machine-learning", "ml", "model")),
    ("scientific_computing", ("stan", "mcmc", "eigenvalue", "raman", "simulation", "numeric", "numpy", "scipy", "biology", "dna"), ("scientific-computing", "biology")),
    ("database", ("sqlite", "database", "sql", ".db"), ("database", "sql")),
    ("compiler_build", ("compile", "build", "make", "cmake", "gcc", "clang", "coverage", "gcov"), ("compiler", "build")),
    ("rust_build", ("cargo", "rustc", "rust"), ("rust",)),
    ("ocaml_coq_build", ("ocaml", "opam", "coq", "compcert", "dune"), ("ocaml", "coq")),
    ("binary_reverse_engineering", ("elf", "binary", "reverse", "disassemble", "objdump", "readelf", "mips"), ("binary", "reverse-engineering", "security")),
    ("crypto_security", ("openssl", "certificate", "crypto", "hash", "cipher", "cryptanalysis", "feal"), ("security", "crypto")),
    ("network_download", ("download", "install", "pip install", "apt-get", "git clone", "fetch"), ("network",)),
)
_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "image_processing": (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".ppm"),
    "video_processing": (".mp4", ".mov", ".avi", ".mkv", ".webm"),
    "ocr_pdf_document": (".pdf",),
    "database": (".db", ".sqlite", ".sqlite3", ".sql"),
    "compiler_build": (".c", ".cc", ".cpp", ".h", ".hpp", ".cmake", ".mk"),
    "rust_build": (".rs",),
    "ocaml_coq_build": (".ml", ".mli", ".v"),
    "scientific_computing": (".R", ".r", ".stan", ".npy", ".npz", ".mat"),
    "binary_reverse_engineering": (".elf", ".bin", ".o", ".so", ".a"),
}


def flatten_task_toml(task_toml: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(task_toml or {})
    metadata = data.get("metadata") if isinstance(data.get("metadata"), Mapping) else {}
    agent = data.get("agent") if isinstance(data.get("agent"), Mapping) else {}
    verifier = data.get("verifier") if isinstance(data.get("verifier"), Mapping) else {}
    environment = data.get("environment") if isinstance(data.get("environment"), Mapping) else {}
    tags = tuple(str(tag) for tag in metadata.get("tags", ()) if str(tag).strip())
    return {
        "task_version": data.get("version", ""),
        "category": str(metadata.get("category", "")),
        "difficulty": str(metadata.get("difficulty", "")),
        "tags": tags,
        "expert_time_estimate_min": metadata.get("expert_time_estimate_min"),
        "junior_time_estimate_min": metadata.get("junior_time_estimate_min"),
        "agent_timeout_sec": agent.get("timeout_sec"),
        "verifier_timeout_sec": verifier.get("timeout_sec"),
        "environment": dict(environment),
        "resource_budget": {
            "agent_timeout_sec": agent.get("timeout_sec"),
            "verifier_timeout_sec": verifier.get("timeout_sec"),
            "build_timeout_sec": environment.get("build_timeout_sec"),
            "cpus": environment.get("cpus"),
            "memory": environment.get("memory"),
            "storage": environment.get("storage"),
            "docker_image": environment.get("docker_image"),
        },
    }


def classify_capability_needs(
    instruction_text: str,
    *,
    task_metadata: Mapping[str, Any] | None = None,
    visible_files: Iterable[str] = (),
) -> tuple[CapabilityNeed, ...]:
    metadata = task_metadata or {}
    category = str(metadata.get("category", ""))
    tags = tuple(str(tag) for tag in metadata.get("tags", ()) or ())
    haystack = "\n".join([instruction_text, category, " ".join(tags)]).lower()
    by_capability: dict[str, CapabilityNeed] = {}

    def add(capability: str, confidence: str, source: str, notes: str = "") -> None:
        existing = by_capability.get(capability)
        if existing is not None and existing.confidence == "high":
            return
        by_capability[capability] = CapabilityNeed(
            capability=capability,
            confidence=confidence,
            source=source if existing is None else existing.source + "+" + source,
            required_tools=_TOOL_BY_CAPABILITY.get(capability, ()),
            verifier_needs=_VERIFIER_BY_CAPABILITY.get(capability, ()),
            notes=notes,
        )

    for capability, words, tag_words in _KEYWORDS:
        if any(word in haystack for word in words) or any(tag.lower() in tag_words for tag in tags):
            add(capability, "high" if any(tag.lower() in tag_words for tag in tags) else "medium", "instruction_or_metadata")

    lower_files = [str(path).lower() for path in visible_files]
    for capability, extensions in _EXTENSIONS.items():
        if any(path.endswith(extensions) or Path(path).name.lower() in {"makefile", "cmakelists.txt", "cargo.toml", "dune", "coq_makefile"} for path in lower_files):
            add(capability, "medium", "visible_file_extensions")

    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), Mapping) else metadata
    for key in ("agent_timeout_sec", "verifier_timeout_sec", "build_timeout_sec"):
        try:
            value = float(budget.get(key, 0) or 0)  # type: ignore[union-attr]
        except (TypeError, ValueError, AttributeError):
            value = 0
        if value >= 900:
            add("long_running_command", "high", "task_timeout_metadata", f"{key}={value:g}")
            break

    return tuple(sorted(by_capability.values(), key=lambda item: item.capability))


def required_tool_hints(needs: Iterable[CapabilityNeed], existing_tool_hints: Iterable[str] = ()) -> tuple[str, ...]:
    tools: list[str] = []
    seen: set[str] = set()
    for tool in existing_tool_hints:
        name = str(tool).strip()
        if name and name not in seen:
            seen.add(name); tools.append(name)
    for need in needs:
        for tool in need.required_tools:
            if tool and tool not in seen:
                seen.add(tool); tools.append(tool)
    return tuple(tools)
