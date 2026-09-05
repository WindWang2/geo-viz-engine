"""Deferred GL delete queue lifecycle (#140)."""

from __future__ import annotations

import gc

from PySide6.QtGui import QOpenGLContext


def test_pending_deletes_dropped_on_context_teardown():
    """Queued handles for a destroyed context must be dropped, not retained —
    strong context keys grew the dicts on every 3D-page open/close cycle."""
    from geoviz_seismic.renderer_3d import (
        _CONTEXT_PENDING_TEXTURE_DELETES,
        drop_pending_gl_deletes,
        queue_gl_texture_delete,
    )

    ctx = QOpenGLContext()  # not created — no real GL needed for the queue
    queue_gl_texture_delete(12345, context=ctx)
    assert 12345 in list(_CONTEXT_PENDING_TEXTURE_DELETES.get(ctx, []))

    drop_pending_gl_deletes(ctx)
    assert _CONTEXT_PENDING_TEXTURE_DELETES.get(ctx) is None


def test_context_key_is_none_for_unhashable():
    """The old id() fallback let a recycled address delete another context's
    handles; unhashable contexts must route to None (unassociated queue)."""
    from geoviz_seismic.renderer_3d import _get_context_key

    class _Unhashable:
        __hash__ = None  # type: ignore[assignment]

    assert _get_context_key(_Unhashable()) is None
