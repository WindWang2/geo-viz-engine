"""#708: native compile flags must follow the selected compiler, not a missing class attr."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_setup(monkeypatch):
    import setuptools

    monkeypatch.setattr(setuptools, "setup", lambda **_kwargs: None)
    path = Path(__file__).resolve().parents[1] / "native" / "map_edit_core" / "setup.py"
    spec = importlib.util.spec_from_file_location("map_edit_core_setup", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compile_args_unix_on_win32_emits_gcc_flags(monkeypatch):
    setup_mod = _load_setup(monkeypatch)
    monkeypatch.setattr(setup_mod.sys, "platform", "win32")
    unix = setup_mod._compile_args("unix")
    assert "-O3" in unix
    assert "-ffast-math" in unix
    msvc = setup_mod._compile_args("msvc")
    assert "/O2" in msvc
    missing = setup_mod._compile_args(None)
    assert "/O2" in missing


def test_compile_args_linux_stays_gcc(monkeypatch):
    setup_mod = _load_setup(monkeypatch)
    monkeypatch.setattr(setup_mod.sys, "platform", "linux")
    flags = setup_mod._compile_args(None)
    assert "-O3" in flags
    assert "/O2" not in flags
