#!/usr/bin/env python3
"""Deterministic fixture task byte for provenance-contract tests."""

from pathlib import Path


Path("/app/task-complete.txt").write_text("task complete\n", encoding="utf-8")
