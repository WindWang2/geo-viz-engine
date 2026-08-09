"""Tests for the three-way GL clipping items promoted into geoviz_seismic.

阶段 1 engine sink-down: previously ``paleo_workbench/viz/geomodel/engine.py``.
These only exercise the clip *state machine* plus construction — the actual
``glClipPlane`` calls need a live GL context and are covered by the renderer's
integration tests.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pyqtgraph.opengl")

from geoviz_seismic import ClippedGLMeshItem, ClippedGLVolumeItem
from geoviz_seismic.gl_clipping import ThreeWayClipMixin

ITEM_CLASSES = [ClippedGLMeshItem, ClippedGLVolumeItem]


def _make(cls):
    if cls is ClippedGLVolumeItem:
        return cls(data=np.zeros((4, 4, 4, 4), dtype=np.ubyte))
    return cls(
        vertexes=np.zeros((3, 3), dtype=np.float32),
        faces=np.array([[0, 1, 2]], dtype=np.int32),
    )


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_defaults_to_no_clipping(qapp, cls):
    item = _make(cls)
    for axis in "xyz":
        assert item.clipping(axis) == (False, 0.0, 1.0)


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_set_clipping_records_state_per_axis(qapp, cls):
    item = _make(cls)
    item.set_clipping("y", enabled=True, val=-42.5, direction=-1.0)
    assert item.clipping("y") == (True, -42.5, -1.0)
    # The other two axes are untouched.
    assert item.clipping("x") == (False, 0.0, 1.0)
    assert item.clipping("z") == (False, 0.0, 1.0)


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_clipping_can_be_disabled_again(qapp, cls):
    item = _make(cls)
    item.set_clipping("z", enabled=True, val=10.0)
    item.set_clipping("z", enabled=False, val=10.0)
    assert item.clipping("z")[0] is False


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_unknown_axis_is_ignored(qapp, cls):
    item = _make(cls)
    item.set_clipping("w", enabled=True, val=1.0)  # must not raise
    for axis in "xyz":
        assert item.clipping(axis) == (False, 0.0, 1.0)


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_values_are_coerced(qapp, cls):
    item = _make(cls)
    item.set_clipping("x", enabled=1, val=7, direction=-1)
    enabled, val, direction = item.clipping("x")
    assert enabled is True
    assert isinstance(val, float) and val == 7.0
    assert isinstance(direction, float) and direction == -1.0


@pytest.mark.parametrize("cls", ITEM_CLASSES)
def test_mixin_precedes_the_pyqtgraph_item_in_the_mro(cls):
    """paint() must resolve to the mixin, otherwise clipping silently does nothing."""
    mro = cls.__mro__
    assert mro.index(ThreeWayClipMixin) < mro.index(mro[2])
    assert cls.paint is ThreeWayClipMixin.paint
