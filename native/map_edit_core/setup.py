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

def _compile_args(compiler_type: str | None = None) -> list[str]:
    """Return compiler flags for the selected compiler (MSVC vs GCC/Clang)."""
    # On Windows default to MSVC unless the chosen compiler is the unix/MinGW one.
    if sys.platform == "win32" and compiler_type != "unix":
        return ["/O2", "/fp:fast"]
    # -ffast-math implies -fno-finite-math-only, which lets the compiler assume
    # NaN/Inf never occur - optimising std::isnan/std::isinf to constant false.
    # Re-enable finite-math handling with -fno-finite-math-only (geometry code
    # compares coordinates that may legitimately be NaN/Inf from upstream) while
    # keeping the rest of -ffast-math's wins.
    return ["-O3", "-ffast-math", "-fno-finite-math-only"]


class BuildExt(build_ext):
    """Choose flags from the instance compiler, not a missing class attribute."""

    def build_extension(self, ext):
        compiler_type = getattr(getattr(self, "compiler", None), "compiler_type", None)
        ext.extra_compile_args = list(_compile_args(compiler_type))
        super().build_extension(ext)


ext_modules = [
    Pybind11Extension(
        "map_edit_core",
        [str(HERE / "src" / "map_edit_core.cpp")],
        cxx_std=17,
        extra_compile_args=[],
    ),
]

setup(
    name="map_edit_core",
    version="0.1.0",
    description="Native geometry hot path for paleo mapping editor",
    ext_modules=ext_modules,
    cmdclass={"build_ext": BuildExt},
    zip_safe=False,
    python_requires=">=3.12,<3.13",
)
