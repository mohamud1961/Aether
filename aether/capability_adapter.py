from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .artifact_store import ArtifactStore
from .pattern_library import PatternLibrary
from .policy_config import PolicyConfig


@dataclass(frozen=True)
class InstallPlan:
    manager: str
    package: str
    version: str
    install_command: List[str]
    is_workspace_scoped: bool = True


@dataclass(frozen=True)
class DetectionResult:
    missing_dependency: bool
    reason_code: Optional[str] = None
    dependency_class: Optional[str] = None
    module_or_binary: Optional[str] = None
    install_plan: Optional[InstallPlan] = None


class CapabilityAdapter:
    # Static Mapping Tables (Deterministic, Pinned)
    PYTHON_PACKAGE_MAP: Dict[str, Tuple[str, str]] = {
        "PIL": ("pillow", "10.2.0"),
        "cv2": ("opencv-python-headless", "4.9.0.80"),
        "numpy": ("numpy", "1.26.4"),
        "pandas": ("pandas", "2.2.1"),
        "requests": ("requests", "2.31.0"),
        "yaml": ("PyYAML", "6.0.1"),
    }

    NODE_PACKAGE_MAP: Dict[str, Tuple[str, str]] = {
        "left-pad": ("left-pad", "1.3.0"),
        "express": ("express", "4.18.3"),
        "lodash": ("lodash", "4.17.21"),
    }

    BINARY_PACKAGE_MAP: Dict[str, Tuple[str, str, str]] = {
        # binary -> (manager, package, version)
        # Empty by default to be safe. Add explicit mappings as needed.
    }

    def __init__(
        self,
        artifact_store: ArtifactStore,
        workspace_root: Path,
        policy_config: Optional[PolicyConfig] = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.workspace_root = workspace_root
        self.policy_config = policy_config or PolicyConfig.from_env()

    def detect_and_plan(
        self,
        *,
        tool_name: str,
        exit_code: int,
        stderr_ref: Optional[str],
        truncation: Optional[Dict[str, Any]],
        tool_args: Dict[str, Any],
    ) -> DetectionResult:
        # Pre-flight checks: Fail closed on invalid input
        if exit_code == 0:
            return DetectionResult(missing_dependency=False, reason_code="exit_code_zero")
        
        if not self.policy_config.feature_flags.ff_capability_adapter:
            return DetectionResult(missing_dependency=False, reason_code="adapter_disabled")

        if not stderr_ref:
            return DetectionResult(missing_dependency=False, reason_code="no_stderr")

        if truncation and (truncation.get("unknown") or truncation.get("truncated")):
            return DetectionResult(missing_dependency=False, reason_code="stderr_truncated")

        # Fetch stderr content
        try:
            stderr_bytes = self.artifact_store.read_bytes(stderr_ref)
            stderr_text = stderr_bytes.decode("utf-8")
        except Exception:
            return DetectionResult(missing_dependency=False, reason_code="read_error")

        # Scan for patterns line by line
        for line in stderr_text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check Python
            py_mod = PatternLibrary.match_python_missing(line)
            if py_mod:
                return self._plan_python(py_mod)

            # Check Node
            node_mod = PatternLibrary.match_node_missing(line)
            if node_mod:
                return self._plan_node(node_mod)

            # Check Binary (must match argv[0])
            binary = PatternLibrary.match_binary_missing(line)
            if binary:
                argv = tool_args.get("command", [])
                if not argv:
                     continue
                # Strict check: command basename must match reported binary
                cmd_basename = Path(str(argv[0])).name
                if cmd_basename == binary:
                     return self._plan_binary(binary)
                # Else: mismatch, likely unrelated error, keep scanning or ignore

            # Check System (Fail Closed)
            sys_dep = PatternLibrary.match_system_missing(line)
            if sys_dep:
                return DetectionResult(
                    missing_dependency=True,
                    reason_code="system_dependency_missing",
                    dependency_class="system_dependency",
                    module_or_binary=sys_dep,
                    install_plan=None,
                )

        return DetectionResult(missing_dependency=False, reason_code="no_pattern_match")

    def _plan_python(self, module: str) -> DetectionResult:
        mapping = self.PYTHON_PACKAGE_MAP.get(module)
        if not mapping:
            return DetectionResult(
                missing_dependency=True,
                reason_code="map_miss_python",
                dependency_class="python_module",
                module_or_binary=module,
                install_plan=None,
            )
        
        pkg, ver = mapping
        # Plan: python3 -m pip install --target <WORKDIR>/.harness_deps/python <pkg>==<ver>
        target_dir = self.workspace_root / ".harness_deps" / "python"
        
        # Ensure we use string path for command construction
        cmd = [
            "python3", "-m", "pip", "install",
            "--target", str(target_dir),
            f"{pkg}=={ver}"
        ]
        
        return DetectionResult(
            missing_dependency=True,
            reason_code="install_plan_generated",
            dependency_class="python_module",
            module_or_binary=module,
            install_plan=InstallPlan(
                manager="pip",
                package=pkg,
                version=ver,
                install_command=cmd,
                is_workspace_scoped=True
            )
        )

    def _plan_node(self, module: str) -> DetectionResult:
        mapping = self.NODE_PACKAGE_MAP.get(module)
        if not mapping:
             return DetectionResult(
                missing_dependency=True,
                reason_code="map_miss_node",
                dependency_class="node_module",
                module_or_binary=module,
                install_plan=None,
            )
        
        pkg, ver = mapping
        # Plan: npm install --ignore-scripts --no-save --no-audit --no-fund <pkg>@<ver>
        cmd = [
            "npm", "install",
            "--ignore-scripts", "--no-save", "--no-audit", "--no-fund",
            f"{pkg}@{ver}"
        ]

        return DetectionResult(
            missing_dependency=True,
            reason_code="install_plan_generated",
            dependency_class="node_module",
            module_or_binary=module,
            install_plan=InstallPlan(
                manager="npm",
                package=pkg,
                version=ver,
                install_command=cmd,
                is_workspace_scoped=True
            )
        )

    def _plan_binary(self, binary: str) -> DetectionResult:
        mapping = self.BINARY_PACKAGE_MAP.get(binary)
        if not mapping:
            return DetectionResult(
                missing_dependency=True,
                reason_code="map_miss_binary",
                dependency_class="binary",
                module_or_binary=binary,
                install_plan=None,
            )
        
        manager, pkg, ver = mapping
        # Binaries require specific per-manager logic which we don't have safe general user-space forms for yet
        # beyond what we might add later. For now, even if mapped, we might need custom logic.
        # But failing closed if no logic implemented.
        return DetectionResult(
             missing_dependency=True,
             reason_code="binary_install_not_implemented",
             dependency_class="binary",
             module_or_binary=binary,
             install_plan=None
        )
