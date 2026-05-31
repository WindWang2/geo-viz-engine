"""Single source of truth for the attribute combo + dispatch.

Replaces the hardcoded ``_FN`` lists and ``if idx >= 8`` magic in
``seismic_view.py``.  Adding a new attribute means appending one
``AttributeSpec`` to ``ATTRIBUTES`` — the UI labels, dispatch and RGB
channel options all derive from this list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from . import attributes as _attr


@dataclass(frozen=True)
class AttributeSpec:
    """One attribute entry.

    Attributes:
        label: Combo box label.
        kind: ``"raw"`` (passthrough), ``"trace"`` (per-trace fn along
            time axis), ``"curvature"`` (slope-gradient family),
            ``"rgb"`` (handled by ``_apply_rgb_fusion``).
        compute: For ``"trace"`` — the attribute function. For
            ``"curvature"`` — a small helper that takes the 2-D slice
            and returns the displayed field. Unused for ``"raw"`` /
            ``"rgb"``.
        needs_sample_interval: True when ``compute`` takes a
            ``sample_interval`` kwarg.
        rgb_channel: True when this attribute can drive an RGB channel
            (used to build the channel combos).
    """

    label: str
    kind: str
    compute: Callable | None = None
    needs_sample_interval: bool = False
    rgb_channel: bool = False


def _curvature_dip_il(data: np.ndarray) -> np.ndarray:
    return _attr.compute_dip(data)[0]


def _curvature_dip_xl(data: np.ndarray) -> np.ndarray:
    return _attr.compute_dip(data)[1]


def _curvature_azimuth(data: np.ndarray) -> np.ndarray:
    dip_il, dip_xl = _attr.compute_dip(data)
    return _attr.compute_azimuth(dip_il, dip_xl)


def _curvature_mean(data: np.ndarray) -> np.ndarray:
    return _attr.compute_curvature(data, kind="mean")


def _curvature_gaussian(data: np.ndarray) -> np.ndarray:
    return _attr.compute_curvature(data, kind="gaussian")


def _curvature_max(data: np.ndarray) -> np.ndarray:
    return _attr.compute_curvature(data, kind="max")


ATTRIBUTES: Sequence[AttributeSpec] = (
    AttributeSpec("振幅", "raw"),
    AttributeSpec("包络", "trace", _attr.compute_envelope, rgb_channel=True),
    AttributeSpec("瞬时相位", "trace", _attr.compute_instantaneous_phase),
    AttributeSpec("瞬时频率", "trace", _attr.compute_instantaneous_frequency,
                  needs_sample_interval=True, rgb_channel=True),
    AttributeSpec("RMS振幅", "trace", _attr.compute_rms_amplitude, rgb_channel=True),
    AttributeSpec("甜点", "trace", _attr.compute_sweetness,
                  needs_sample_interval=True, rgb_channel=True),
    AttributeSpec("相对阻抗", "trace", _attr.compute_relative_impedance, rgb_channel=True),
    AttributeSpec("RGB融合", "rgb"),
    AttributeSpec("Dip_IL", "curvature", _curvature_dip_il),
    AttributeSpec("Dip_XL", "curvature", _curvature_dip_xl),
    AttributeSpec("方位角", "curvature", _curvature_azimuth),
    AttributeSpec("平均曲率", "curvature", _curvature_mean),
    AttributeSpec("高斯曲率", "curvature", _curvature_gaussian),
    AttributeSpec("最大曲率", "curvature", _curvature_max),
)


def labels() -> list[str]:
    return [spec.label for spec in ATTRIBUTES]


def rgb_index() -> int:
    """Index of the RGB-fusion entry in ATTRIBUTES."""
    for i, s in enumerate(ATTRIBUTES):
        if s.kind == "rgb":
            return i
    raise ValueError("No RGB attribute spec found")


def rgb_channel_indices() -> list[int]:
    """Indices in ATTRIBUTES that may serve as RGB channels."""
    return [i for i, s in enumerate(ATTRIBUTES) if s.rgb_channel]


def apply(idx: int, data: np.ndarray, sample_interval_s: float = 1.0) -> np.ndarray:
    """Apply the attribute at index ``idx`` to ``data`` (2-D slice).

    Returns the displayed field. For ``"raw"`` returns ``data`` unchanged.
    For ``"rgb"`` returns ``data`` unchanged (caller must invoke
    ``_apply_rgb_fusion`` separately).
    """
    spec = ATTRIBUTES[idx]
    if spec.kind in ("raw", "rgb"):
        return data
    if spec.kind == "curvature":
        return spec.compute(data)
    # trace
    kwargs: dict = {"axis": 0}
    if spec.needs_sample_interval:
        kwargs["sample_interval"] = sample_interval_s
    return spec.compute(data, **kwargs)
