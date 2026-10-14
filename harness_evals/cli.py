"""Command-line entry point.

Subcommands are discovered from harness_evals/commands/*.py. Each command module exposes
register(subparsers), which adds its parser and sets func=handler, where handler(args) -> int.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
from collections.abc import Sequence
from types import ModuleType

COMMANDS_PACKAGE = "harness_evals.commands"


def build_parser(package: str = COMMANDS_PACKAGE) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-evals",
        description="Run agents on eval tasks, validate graders and summarise trials.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for module in load_command_modules(package):
        module.register(subparsers)
    return parser


def load_command_modules(package: str) -> list[ModuleType]:
    package_module = importlib.import_module(package)
    modules: list[ModuleType] = []
    for info in sorted(
        pkgutil.iter_modules(package_module.__path__), key=lambda item: item.name
    ):
        if info.ispkg or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{info.name}")
        if not callable(getattr(module, "register", None)):
            raise RuntimeError(
                f"command module {module.__name__} does not define register()"
            )
        modules.append(module)
    return modules


def main(argv: Sequence[str] | None = None, package: str = COMMANDS_PACKAGE) -> int:
    parser = build_parser(package)
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))
