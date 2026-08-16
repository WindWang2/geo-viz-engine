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
        supports_2d: False when the attribute is undefined for 2-D slices
            (e.g. Gaussian/max curvature need a non-degenerate inline
            slope, which is identically zero on 2-D input).  ``apply``
            rejects such combinations and UI consumers should disable
            the corresponding combo entries.
    """

    label: str
    kind: str
    compute: Callable | None = None
    needs_sample_interval: bool = False
    rgb_channel: bool = False
    supports_2d: bool = True


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
    AttributeSpec("高斯曲率", "curvature", _curvature_gaussian, supports_2d=False),
    AttributeSpec("最大曲率", "curvature", _curvature_max, supports_2d=False),
    AttributeSpec("相干性(C3)", "curvature", _attr.compute_coherence_c3),
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

    Raises:
        ValueError: If ``data`` is 2-D and the attribute does not support
            2-D input (``AttributeSpec.supports_2d`` is False) — e.g.
            Gaussian/max/min curvature degenerate to an all-zero map on
            2-D slices because the inline slope is identically zero.
    """
    spec = ATTRIBUTES[idx]
    if data.ndim == 2 and not spec.supports_2d:
        raise ValueError(
            f"Attribute {spec.label!r} does not support 2-D slices "
            "(inline slope is identically zero, so the result would be an "
            "all-zero map); compute it on a 3-D volume instead."
        )
    if spec.kind in ("raw", "rgb"):
        return data
    if spec.kind == "curvature":
        return spec.compute(data)
    # trace
    kwargs: dict = {"axis": 0}
    if spec.needs_sample_interval:
        kwargs["sample_interval"] = sample_interval_s
    return spec.compute(data, **kwargs)
