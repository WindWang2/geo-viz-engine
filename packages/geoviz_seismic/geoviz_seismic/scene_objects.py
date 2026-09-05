"""Named scene objects: the renderer-side registry for host-driven overlays.

Hosts (the workbench geological scene adapter) push prepared **engine-space**
meshes under stable object names. The renderer owns GL item lifetime; this
manager is the single mutation point so hosts never reach into the private
``GLViewWidget`` or item internals.

Design contracts:

* **Replace-on-add.** ``add_object`` with an existing name atomically replaces
  the previous item, so a host re-sync is deterministic (same input → same
  scene) and object-level incremental updates are just add + remove.
* **Engine stays CRS-agnostic.** Meshes arrive already transformed into
  renderer space by the host; the manager never interprets units.
* **GL-free core.** Item creation goes through a tiny view protocol with a
  lazily imported ``pyqtgraph.opengl`` module, so the registry state machine
  and the pick math are unit-testable without an OpenGL context.
* **Clipping planes are per-object** fixed-function ``GL_CLIP_PLANE0..n``
  enabled only inside the item's own ``paint()`` (same pattern as
  :mod:`geoviz_seismic.gl_clipping`), so unrelated items are unaffected.
  Core-profile contexts skip clipping with the shared one-shot warning.
* **Picking is CPU ray-triangle** (Möller–Trumbore, vectorised). Mesh payloads
  are kept by reference — the host is expected to reuse the same arrays it
  built, not to duplicate geometry per frame.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import numpy as np

logger = logging.getLogger(__name__)

__all__ = [
    "OBJECT_MODES",
    "OBJECT_KINDS",
    "PickHit",
    "SceneObject",
    "SceneObjectManager",
    "ray_triangles_first_hit",
    "screen_point_to_ray",
]

OBJECT_MODES = ("mesh", "lines", "points", "text")
OBJECT_KINDS = (
    "generic",
    "well",
    "horizon",
    "fault",
    "volume",
    "annotation",
    "measurement",
)

# Fixed-function clip plane slots available for per-object clipping. Slots
# 0..2 are ALSO used by ThreeWayClipMixin items during their own paint, but
# the enable/disable windows never overlap (each item's planes are active
# only inside its paint call), so the slots can be shared safely.
_MAX_CLIP_PLANES = 6


class SceneObjectError(ValueError):
    """Raised for invalid scene-object payloads (fail-loud host bugs)."""


def _validate_mesh_arrays(
    verts: np.ndarray, faces: np.ndarray | None
) -> tuple[np.ndarray, np.ndarray | None]:
    v = np.asarray(verts, dtype=np.float32)
    if v.ndim != 2 or v.shape[1] != 3:
        raise SceneObjectError(
            f"verts must have shape (N, 3), got {v.shape}"
        )
    if v.size and not np.all(np.isfinite(v)):
        # NaN vertices render as holes and poison picking; the host should
        # mask degenerate geometry before submitting (fail-loud, not silent).
        raise SceneObjectError("verts contain non-finite coordinates")
    if faces is None:
        return v, None
    f = np.asarray(faces)
    if f.ndim != 2 or f.shape[1] < 3:
        raise SceneObjectError(f"faces must have shape (M, >=3), got {f.shape}")
    if f.size:
        if f.min() < 0 or f.max() >= max(len(v), 1):
            raise SceneObjectError(
                f"faces reference vertex index out of range "
                f"[{f.min()}, {f.max()}] with {len(v)} vertices"
            )
        if not np.all(np.isfinite(f.astype(np.float64))):
            raise SceneObjectError("faces contain non-finite indices")
    return v, f


def _validate_clip_planes(planes: Sequence[Sequence[float]] | None):
    if planes is None:
        return None
    out = []
    for plane in planes:
        eq = tuple(float(c) for c in plane)
        if len(eq) != 4:
            raise SceneObjectError(
                f"clip planes must be (a, b, c, d) tuples, got {plane!r}"
            )
        if not any(abs(c) > 0.0 for c in eq[:3]):
            raise SceneObjectError(
                f"clip plane normal is zero: {plane!r}"
            )
        out.append(eq)
    if len(out) > _MAX_CLIP_PLANES:
        raise SceneObjectError(
            f"at most {_MAX_CLIP_PLANES} clip planes per object, got {len(out)}"
        )
    return tuple(out)


@dataclass(frozen=True)
class PickHit:
    """Nearest ray-mesh intersection on one named object."""

    name: str
    kind: str
    point: tuple[float, float, float]
    distance: float
    face_index: int


@dataclass
class SceneObject:
    """Registry entry for one named overlay object."""

    name: str
    kind: str
    mode: str
    pickable: bool
    visible: bool
    opacity: float
    # Geometry kept by reference for picking / bounds / rebuilds. For
    # lines/points modes ``verts`` doubles as the polyline / point list.
    verts: np.ndarray
    faces: np.ndarray | None
    face_colors: np.ndarray | None
    vertex_colors: np.ndarray | None
    color: tuple[float, float, float, float]
    # Alpha as submitted (before the opacity multiplier), so set_opacity can
    # rescale from the base instead of compounding on the previous value.
    base_alpha: float = 1.0
    clip_planes: tuple | None = None
    extra: dict = field(default_factory=dict)
    item: object | None = None

    @property
    def bounds(self) -> np.ndarray | None:
        if len(self.verts) == 0:
            return None
        return np.array([self.verts.min(axis=0), self.verts.max(axis=0)])


def ray_triangles_first_hit(
    origin: np.ndarray,
    direction: np.ndarray,
    verts: np.ndarray,
    faces: np.ndarray,
    *,
    max_distance: float | None = None,
) -> tuple[float, int] | None:
    """Nearest ray-triangle hit (Möller–Trumbore, vectorised over faces).

    ``verts`` is (N, 3) float, ``faces`` is (M, 3) int. Returns
    ``(distance, face_index)`` for the closest front hit with
    ``distance >= 0``, or ``None``. Degenerate triangles are skipped.
    """
    if len(faces) == 0 or len(verts) == 0:
        return None
    tri = verts[faces[:, :3].astype(np.int64)]  # (M, 3, 3)
    a, b, c = tri[:, 0, :], tri[:, 1, :], tri[:, 2, :]
    e1 = b - a
    e2 = c - a
    pvec = np.cross(np.broadcast_to(direction, (len(faces), 3)), e2)
    det = np.einsum("ij,ij->i", e1, pvec)
    eps = 1e-12
    ok = np.abs(det) > eps
    if not np.any(ok):
        return None
    inv_det = np.zeros_like(det)
    inv_det[ok] = 1.0 / det[ok]
    tvec = np.broadcast_to(origin, (len(faces), 3)) - a
    u = np.einsum("ij,ij->i", tvec, pvec) * inv_det
    qvec = np.cross(tvec, e1)
    v = np.einsum("ij,ij->i", np.broadcast_to(direction, (len(faces), 3)), qvec) * inv_det
    t = np.einsum("ij,ij->i", e2, qvec) * inv_det
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1.0 + 1e-9) & (t >= 0.0)
    if max_distance is not None:
        hit &= t <= float(max_distance)
    if not np.any(hit):
        return None
    idx = np.flatnonzero(hit)
    best = idx[np.argmin(t[idx])]
    return float(t[best]), int(best)


def screen_point_to_ray(
    px: float,
    py: float,
    width: float,
    height: float,
    view_matrix,
    proj_matrix,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Unproject a widget-space point into a (origin, direction) world ray.

    Uses the pyqtgraph ``GLViewWidget`` matrix convention (see also
    ``Renderer3D._ray_box_intersect``): matrices are QMatrix4x4, y is flipped
    between widget and NDC, and the ray spans the NDC near/far planes.
    """
    if width <= 0 or height <= 0:
        return None
    from PySide6.QtGui import QVector3D, QVector4D

    ndc_x = (2.0 * px / width) - 1.0
    ndc_y = 1.0 - (2.0 * py / height)
    inv, ok = (proj_matrix * view_matrix).inverted()
    if not ok:
        return None
    near = inv.map(QVector4D(ndc_x, ndc_y, -1.0, 1.0))
    far = inv.map(QVector4D(ndc_x, ndc_y, 1.0, 1.0))
    if abs(near.w()) < 1e-8 or abs(far.w()) < 1e-8:
        return None
    near_w = np.array(
        [near.x() / near.w(), near.y() / near.w(), near.z() / near.w()],
        dtype=np.float64,
    )
    far_w = np.array(
        [far.x() / far.w(), far.y() / far.w(), far.z() / far.w()],
        dtype=np.float64,
    )
    direction = far_w - near_w
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        return None
    return near_w, direction / norm


class _PlaneClipMixin:
    """Applies the owning object's clip planes during this item's paint."""

    _scene_clip_planes: tuple = ()

    def set_scene_clip_planes(self, planes: tuple | None) -> None:
        self._scene_clip_planes = tuple(planes or ())
        self.update()

    def paint(self):  # noqa: N802 - matches pyqtgraph item API
        planes = getattr(self, "_scene_clip_planes", ())
        from PySide6.QtGui import QOpenGLContext

        if (
            not planes
            or QOpenGLContext.currentContext() is None
            or _core_profile_context()
        ):
            if planes and _core_profile_context():
                _warn_core_profile_once()
            super().paint()
            return
        from OpenGL import GL

        enabled = []
        try:
            for i, (a, b, c, d) in enumerate(planes):
                slot = GL.GL_CLIP_PLANE0 + i
                GL.glEnable(slot)
                GL.glClipPlane(slot, (a, b, c, d))
                enabled.append(slot)
        except Exception:
            logger.debug("glClipPlane failed", exc_info=True)
        try:
            super().paint()
        finally:
            for slot in enabled:
                try:
                    GL.glDisable(slot)
                except Exception:
                    pass


_CORE_WARNED = {"flag": False}


def _core_profile_context() -> bool:
    from PySide6.QtGui import QOpenGLContext, QSurfaceFormat

    ctx = QOpenGLContext.currentContext()
    if ctx is None:
        return False
    return ctx.format().profile() == QSurfaceFormat.OpenGLContextProfile.CoreProfile


def _warn_core_profile_once() -> None:
    if _CORE_WARNED["flag"]:
        return
    _CORE_WARNED["flag"] = True
    logger.warning(
        "Core-profile GL context: fixed-function clip planes are unavailable; "
        "per-object clipping is disabled."
    )


class SceneObjectManager:
    """Registry of named overlay objects rendered into one GL view.

    ``view_provider`` returns the current ``GLViewWidget`` (may return ``None``
    while the renderer is torn down); ``gl_module_provider`` lazily imports
    ``pyqtgraph.opengl`` so headless tests can inject stub items.
    """

    def __init__(
        self,
        view_provider: Callable[[], object | None],
        gl_module_provider: Callable[[], object] | None = None,
    ) -> None:
        self._view_provider = view_provider
        self._gl_module_provider = gl_module_provider or self._default_gl_provider
        self._objects: dict[str, SceneObject] = {}

    @staticmethod
    def _default_gl_provider():
        import pyqtgraph.opengl as gl

        return gl

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def names(self, kind: str | None = None) -> list[str]:
        if kind is None:
            return list(self._objects)
        return [n for n, o in self._objects.items() if o.kind == kind]

    def get(self, name: str) -> SceneObject | None:
        return self._objects.get(name)

    def __len__(self) -> int:
        return len(self._objects)

    def __contains__(self, name: str) -> bool:
        return name in self._objects

    def object_bounds(self, name: str) -> np.ndarray | None:
        obj = self._objects.get(name)
        return None if obj is None else obj.bounds

    def bounds(
        self,
        *,
        kinds: Iterable[str] | None = None,
        visible_only: bool = True,
    ) -> np.ndarray | None:
        """Union AABB of (optionally filtered) objects, or ``None`` if empty."""
        kind_set = None if kinds is None else set(kinds)
        mins: list[np.ndarray] = []
        maxs: list[np.ndarray] = []
        for obj in self._objects.values():
            if kind_set is not None and obj.kind not in kind_set:
                continue
            if visible_only and not obj.visible:
                continue
            b = obj.bounds
            if b is None:
                continue
            mins.append(b[0])
            maxs.append(b[1])
        if not mins:
            return None
        return np.array([np.min(mins, axis=0), np.max(maxs, axis=0)])

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_object(
        self,
        name: str,
        *,
        verts: np.ndarray,
        faces: np.ndarray | None = None,
        face_colors: np.ndarray | None = None,
        vertex_colors: np.ndarray | None = None,
        mode: str = "mesh",
        color: Sequence[float] = (1.0, 1.0, 1.0, 1.0),
        opacity: float = 1.0,
        visible: bool = True,
        pickable: bool = False,
        kind: str = "generic",
        clip_planes: Sequence[Sequence[float]] | None = None,
        width: float = 1.0,
        size: float = 6.0,
        text: str = "",
        smooth: bool = True,
    ) -> SceneObject:
        """Create or atomically replace the named object."""
        if not name:
            raise SceneObjectError("object name must be non-empty")
        if mode not in OBJECT_MODES:
            raise SceneObjectError(
                f"mode must be one of {OBJECT_MODES}, got {mode!r}"
            )
        if kind not in OBJECT_KINDS:
            raise SceneObjectError(f"unknown object kind {kind!r}")
        opacity = float(min(max(float(opacity), 0.0), 1.0))
        col = tuple(float(c) for c in color)
        if len(col) not in (3, 4):
            raise SceneObjectError(f"color must be RGB(A), got {color!r}")
        if len(col) == 3:
            col = (*col, 1.0)
        base_alpha = col[3]
        v, f = _validate_mesh_arrays(verts, faces)
        if face_colors is not None:
            fc = np.asarray(face_colors, dtype=np.float32).copy()
            if len(fc) and fc.shape[1] == 4:
                # Registry copy keeps the submitted (base) alpha; the current
                # opacity multiplier is applied only on upload so repeated
                # set_opacity calls never compound.
                fc[:, 3] = fc[:, 3] * base_alpha
        else:
            fc = None
        vc = None if vertex_colors is None else np.asarray(vertex_colors, dtype=np.float32)
        planes = _validate_clip_planes(clip_planes)

        if mode == "mesh" and f is None and len(v):
            raise SceneObjectError("mesh objects require faces (or empty verts)")

        obj = SceneObject(
            name=name,
            kind=kind,
            mode=mode,
            pickable=bool(pickable),
            visible=bool(visible),
            opacity=opacity,
            verts=v,
            faces=f,
            face_colors=fc,
            vertex_colors=vc,
            color=(*col[:3], base_alpha * opacity),
            base_alpha=base_alpha,
            clip_planes=planes,
            extra={"width": float(width), "size": float(size), "text": str(text), "smooth": bool(smooth)},
        )
        old = self._objects.get(name)
        item = self._build_item(obj)
        self._destroy_item(old)
        obj.item = item
        self._objects[name] = obj
        return obj

    def remove_object(self, name: str) -> bool:
        obj = self._objects.pop(name, None)
        if obj is None:
            return False
        self._destroy_item(obj)
        return True

    def clear(self, kind: str | None = None) -> int:
        """Remove all objects (optionally one kind); returns removed count."""
        doomed = [
            n for n, o in self._objects.items() if kind is None or o.kind == kind
        ]
        for n in doomed:
            self.remove_object(n)
        return len(doomed)

    def set_visibility(self, name: str, visible: bool) -> None:
        obj = self._require(name)
        obj.visible = bool(visible)
        if obj.item is not None:
            try:
                if obj.visible:
                    obj.item.show()
                else:
                    obj.item.hide()
            except Exception:
                logger.debug("set_visibility failed for %s", name, exc_info=True)

    def set_opacity(self, name: str, opacity: float) -> None:
        obj = self._require(name)
        opacity = float(min(max(float(opacity), 0.0), 1.0))
        obj.opacity = opacity
        obj.color = (*obj.color[:3], obj.base_alpha * opacity)
        if obj.item is None:
            return
        try:
            item = obj.item
            if obj.mode == "mesh":
                gloptions = "opaque" if opacity >= 0.999 else "translucent"
                if hasattr(item, "setGLOptions"):
                    item.setGLOptions(gloptions)
                if obj.face_colors is not None:
                    fc = self._upload_face_colors(obj)
                    item.setMeshData(meshdata=self._meshdata(obj.verts, obj.faces, face_colors=fc))
                elif hasattr(item, "setColor"):
                    item.setColor(obj.color)
            elif obj.mode == "lines" and hasattr(item, "setData"):
                item.setData(color=obj.color)
            elif obj.mode == "points" and hasattr(item, "setData"):
                item.setData(color=obj.color)
            elif obj.mode == "text" and hasattr(item, "setData"):
                item.setData(color=obj.color)
        except Exception:
            logger.debug("set_opacity failed for %s", name, exc_info=True)

    def set_color(self, name: str, color: Sequence[float]) -> None:
        obj = self._require(name)
        col = tuple(float(c) for c in color)
        if len(col) == 3:
            col = (*col, obj.base_alpha)
        obj.base_alpha = col[3]
        obj.color = (*col[:3], col[3] * obj.opacity)
        if obj.item is not None:
            try:
                if obj.mode == "mesh" and obj.face_colors is None and hasattr(obj.item, "setColor"):
                    obj.item.setColor(obj.color)
                elif obj.mode != "mesh" and hasattr(obj.item, "setData"):
                    obj.item.setData(color=obj.color)
            except Exception:
                logger.debug("set_color failed for %s", name, exc_info=True)

    def set_pickable(self, name: str, pickable: bool) -> None:
        self._require(name).pickable = bool(pickable)

    def set_clip_planes(self, name: str, planes: Sequence[Sequence[float]] | None) -> None:
        obj = self._require(name)
        obj.clip_planes = _validate_clip_planes(planes)
        if obj.item is not None and hasattr(obj.item, "set_scene_clip_planes"):
            try:
                obj.item.set_scene_clip_planes(obj.clip_planes)
            except Exception:
                logger.debug("set_clip_planes failed for %s", name, exc_info=True)

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------

    def pick(
        self,
        origin: Sequence[float],
        direction: Sequence[float],
        *,
        kinds: Iterable[str] | None = None,
        max_distance: float | None = None,
    ) -> PickHit | None:
        """Nearest ray hit over visible, pickable mesh objects (engine space)."""
        origin = np.asarray(origin, dtype=np.float64)
        direction = np.asarray(direction, dtype=np.float64)
        norm = float(np.linalg.norm(direction))
        if norm < 1e-12:
            return None
        direction = direction / norm
        kind_set = None if kinds is None else set(kinds)
        best: PickHit | None = None
        for obj in self._objects.values():
            if not (obj.pickable and obj.visible and obj.mode == "mesh"):
                continue
            if kind_set is not None and obj.kind not in kind_set:
                continue
            if obj.faces is None or len(obj.faces) == 0:
                continue
            hit = ray_triangles_first_hit(
                origin, direction, obj.verts, obj.faces, max_distance=max_distance
            )
            if hit is None:
                continue
            dist, face_index = hit
            if best is not None and dist >= best.distance:
                continue
            point = origin + direction * dist
            best = PickHit(
                name=obj.name,
                kind=obj.kind,
                point=(float(point[0]), float(point[1]), float(point[2])),
                distance=dist,
                face_index=face_index,
            )
        return best

    def pick_at(
        self,
        px: float,
        py: float,
        *,
        kinds: Iterable[str] | None = None,
        view=None,
    ) -> PickHit | None:
        """Screen-space pick using the GLViewWidget camera (if available)."""
        v = view if view is not None else self._view_provider()
        if v is None:
            return None
        ray = screen_point_to_ray(
            px, py, v.width(), v.height(), v.viewMatrix(), v.projectionMatrix()
        )
        if ray is None:
            return None
        origin, direction = ray
        return self.pick(origin, direction, kinds=kinds)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, name: str) -> SceneObject:
        obj = self._objects.get(name)
        if obj is None:
            raise KeyError(f"unknown scene object {name!r}")
        return obj

    def _build_item(self, obj: SceneObject):
        gl = self._gl_module_provider()
        view = self._view_provider()
        if gl is None or view is None:
            return None
        try:
            if obj.mode == "mesh":
                item = self._build_mesh_item(gl, obj)
            elif obj.mode == "lines":
                item = gl.GLLinePlotItem(
                    pos=obj.verts,
                    color=obj.color,
                    width=obj.extra.get("width", 1.0),
                    mode="lines",
                    antialias=True,
                )
            elif obj.mode == "points":
                item = gl.GLScatterPlotItem(
                    pos=obj.verts,
                    color=obj.color,
                    size=obj.extra.get("size", 6.0),
                )
            elif obj.mode == "text":
                item = gl.GLTextItem(
                    pos=obj.verts[0] if len(obj.verts) else np.zeros(3, dtype=np.float32),
                    text=obj.extra.get("text", ""),
                    color=tuple(int(c * 255) for c in obj.color[:3]) + (255,),
                )
            else:  # pragma: no cover - guarded by add_object
                raise SceneObjectError(f"unsupported mode {obj.mode!r}")
        except Exception:
            logger.warning(
                "scene object %s: GL item creation failed", obj.name, exc_info=True
            )
            return None
        if obj.clip_planes and hasattr(item, "set_scene_clip_planes"):
            item.set_scene_clip_planes(obj.clip_planes)
        if not obj.visible:
            item.hide()
        try:
            view.addItem(item)
        except Exception:
            logger.warning(
                "scene object %s: addItem failed", obj.name, exc_info=True
            )
            return None
        return item

    def _meshdata(self, verts, faces, face_colors=None, vertex_colors=None):
        from pyqtgraph.opengl import MeshData

        if vertex_colors is not None:
            return MeshData(vertexes=verts, faces=faces, vertexColors=vertex_colors)
        if face_colors is not None:
            return MeshData(vertexes=verts, faces=faces, faceColors=face_colors)
        return MeshData(vertexes=verts, faces=faces)

    def _upload_face_colors(self, obj: SceneObject) -> np.ndarray:
        """Registry alphas scaled to the current effective opacity."""
        fc = obj.face_colors
        if fc is None:
            return None
        out = fc.copy()
        if len(out) and out.shape[1] == 4 and obj.opacity < 0.999:
            out[:, 3] = out[:, 3] * obj.opacity
        return out

    def _build_mesh_item(self, gl, obj: SceneObject):
        base = gl.GLMeshItem
        cls = getattr(gl, "__scene_clip_mesh_item", None)
        if cls is None:
            cls = type("_SceneClipGLMeshItem", (_PlaneClipMixin, base), {})
            try:
                gl.__scene_clip_mesh_item = cls
            except Exception:
                pass
        gloptions = "opaque" if obj.opacity >= 0.999 else "translucent"
        kwargs = dict(
            meshdata=self._meshdata(
                obj.verts, obj.faces,
                face_colors=self._upload_face_colors(obj),
                vertex_colors=obj.vertex_colors,
            ),
            smooth=obj.extra.get("smooth", True),
            glOptions=gloptions,
        )
        if obj.face_colors is None and obj.vertex_colors is None:
            kwargs["color"] = obj.color
            kwargs["shader"] = "shaded"
        else:
            kwargs["shader"] = None
        return cls(**kwargs)

    def _destroy_item(self, obj: SceneObject | None) -> None:
        if obj is None or obj.item is None:
            return
        view = self._view_provider()
        try:
            if view is not None:
                view.removeItem(obj.item)
        except Exception:
            logger.debug(
                "removeItem failed for %s (view torn down?)", obj.name, exc_info=True
            )
        # Drop our reference; the GL item destructor runs on the Qt side and
        # the deferred-delete queue drains on the next paint (see
        # flush_pending_gl_deletes wired in Renderer3D).
        obj.item = None
