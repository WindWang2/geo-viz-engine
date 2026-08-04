"""Build the map_edit_core pybind11 extension.

Source lives in the geo-viz-engine submodule; the consumer (paleo-workbench
or well_log_workstation) builds it. Install from the repo root that pins the
geo-viz-engine submodule::

    python -m pip install -e geo-viz-engine/native/map_edit_core

Or build in-place::

    cd geo-viz-engine/native/map_edit_core && python setup.py build_ext --inplace
"""

from __future__ import annotations

from pathlib import Path

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

import sys

HERE = Path(__file__).resolve().parent

def _compile_args() -> list[str]:
    """Return compiler flags, detecting MSVC vs GCC/Clang on all platforms."""
    try:
        from setuptools.command.build_ext import build_ext as _be
        compiler = getattr(_be, 'compiler_type', None)
    except Exception:
        compiler = None
    # On Windows default to MSVC unless evidence of GCC/MinGW
    if sys.platform == "win32" and compiler != "unix":
        return ["/O2", "/fp:fast"]
    # -ffast-math implies -fno-finite-math-only, which lets the compiler assume
    # NaN/Inf never occur - optimising std::isnan/std::isinf to constant false.
    # Re-enable finite-math handling with -fno-finite-math-only (geometry code
    # compares coordinates that may legitimately be NaN/Inf from upstream) while
    # keeping the rest of -ffast-math's wins.
    return ["-O3", "-ffast-math", "-fno-finite-math-only"]

extra_compile_args = _compile_args()

ext_modules = [
    Pybind11Extension(
        "map_edit_core",
        [str(HERE / "src" / "map_edit_core.cpp")],
        cxx_std=17,
        extra_compile_args=extra_compile_args,
    ),
]

setup(
    name="map_edit_core",
    version="0.1.0",
    description="Native geometry hot path for paleo mapping editor",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.12",
)
