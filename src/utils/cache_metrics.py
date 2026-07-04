"""Cache size helpers for settings page and status bar."""
from __future__ import annotations

import os
from pathlib import Path

from src.utils.paths import get_data_dir


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


def compute_total_cache_mb() -> float:
    """Sum user cache (~/.cache/geoviz) and per-dataset Excel JSON caches."""
    roots = [Path.home() / ".cache" / "geoviz", get_data_dir() / ".cache"]
    return sum(_dir_size_bytes(r) for r in roots) / (1024 * 1024)


def purge_all_caches() -> float:
    """Remove all known cache directories; return MB released."""
    released = compute_total_cache_mb()
    for root in (Path.home() / ".cache" / "geoviz", get_data_dir() / ".cache"):
        if not root.exists():
            continue
        for dirpath, _dirs, files in os.walk(root, topdown=False):
            for name in files:
                try:
                    os.remove(os.path.join(dirpath, name))
                except OSError:
                    pass
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    return released