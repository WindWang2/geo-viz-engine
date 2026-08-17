"""Cache size helpers for settings page and status bar."""
from __future__ import annotations

import os
from pathlib import Path

from src.utils.paths import get_data_dir


def _user_cache_root() -> Path:
    return Path.home() / ".cache" / "geoviz"


def _registry_path() -> Path:
    return _user_cache_root() / "well_cache_dirs.txt"


def register_well_cache_dir(path: Path) -> None:
    """Remember a well-adjacent `.cache` dir so stats/purge can find it."""
    resolved = Path(path).resolve()
    try:
        registry = _registry_path()
        registry.parent.mkdir(parents=True, exist_ok=True)
        existing: set[str] = set()
        if registry.exists():
            existing = {
                line.strip()
                for line in registry.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        key = str(resolved)
        if key not in existing:
            with registry.open("a", encoding="utf-8") as fh:
                fh.write(key + "\n")
    except OSError:
        pass


def _registered_well_cache_dirs() -> list[Path]:
    registry = _registry_path()
    if not registry.exists():
        return []
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [Path(line.strip()) for line in lines if line.strip()]


def _cache_roots() -> list[Path]:
    roots: list[Path] = [_user_cache_root(), get_data_dir() / ".cache"]
    seen = {p.resolve() for p in roots}
    for extra in _registered_well_cache_dirs():
        try:
            resolved = extra.resolve()
        except OSError:
            continue
        if resolved not in seen:
            roots.append(extra)
            seen.add(resolved)
    return roots


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
    """Sum user cache, data-dir cache, and registered well-adjacent caches."""
    return sum(_dir_size_bytes(r) for r in _cache_roots()) / (1024 * 1024)


def _purge_tree(root: Path) -> None:
    if not root.exists():
        return
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


def purge_all_caches() -> float:
    """Remove all known cache directories; return MB released."""
    released = compute_total_cache_mb()
    fixed = {_user_cache_root().resolve(), (get_data_dir() / ".cache").resolve()}
    for root in _cache_roots():
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in fixed:
            _purge_tree(root)
            continue
        # Well-adjacent `.cache` may contain unrelated files — only ours.
        if not root.exists():
            continue
        for pattern in ("*.json", "*.pkl"):
            for item in root.glob(pattern):
                try:
                    item.unlink()
                except OSError:
                    pass
    return released