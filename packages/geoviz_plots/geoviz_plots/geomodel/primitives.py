"""Parametric mesh primitives for 3D geological models (headless numpy).

Promoted from ``paleo_workbench/viz/geomodel/engine.py``, which mixed these pure
generators with Qt/OpenGL item subclasses. Only the generators live here; the GL
items moved to :mod:`geoviz_seismic.gl_clipping`.

Every function returns a ``(vertices, faces, face_colors)`` triple ready to hand to
``pyqtgraph.opengl.GLMeshItem(vertexes=..., faces=..., faceColors=...)``. No Qt /
OpenGL import — safe to call from worker threads.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "generate_cylinder_geometry",
    "generate_tube_geometry",
    "generate_fault_geometry",
]

_EMPTY = (
    np.zeros((0, 3), dtype=np.float32),
    np.zeros((0, 3), dtype=np.int32),
    np.zeros((0, 4), dtype=np.float32),
)


def _orthonormal_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two unit vectors spanning the plane perpendicular to ``axis`` (already unit)."""
    seed = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
    ortho1 = np.cross(axis, seed)
    ortho1 = ortho1 / np.linalg.norm(ortho1)
    return ortho1, np.cross(axis, ortho1)


def generate_cylinder_geometry(
    p1,
    p2,
    radius: float = 2.0,
    color=(1.0, 0.0, 0.0, 1.0),
    resolution: int = 12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Capped cylinder spanning ``p1``→``p2``.

    Returns ``(verts, faces, face_colors)``; empty arrays when the two points coincide.
    """
    p1 = np.array(p1, dtype=np.float32)
    p2 = np.array(p2, dtype=np.float32)
    axis = p2 - p1
    length = np.linalg.norm(axis)
    if length == 0:
        return _EMPTY

    ortho1, ortho2 = _orthonormal_basis(axis / length)

    vertices = []
    for i in range(resolution):
        theta = 2 * np.pi * i / resolution
        offset = np.cos(theta) * radius * ortho1 + np.sin(theta) * radius * ortho2
        vertices.append(p1 + offset)
        vertices.append(p2 + offset)

    # Cap centres, appended last so the tube indices stay at 2*i / 2*i+1.
    vertices.append(p1)
    vertices.append(p2)
    idx_p1 = len(vertices) - 2
    idx_p2 = len(vertices) - 1

    faces = []
    for i in range(resolution):
        next_i = (i + 1) % resolution
        faces.append([2 * i, 2 * next_i, 2 * i + 1])
        faces.append([2 * next_i, 2 * next_i + 1, 2 * i + 1])
        faces.append([idx_p1, 2 * next_i, 2 * i])
        faces.append([idx_p2, 2 * i + 1, 2 * next_i + 1])

    return _finish(vertices, faces, color)


def generate_tube_geometry(
    path,
    radius: float = 3.0,
    color=(0.8, 0.8, 0.8, 1.0),
    resolution: int = 12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tube swept along a polyline, using a per-station central-difference tangent.

    For a twist-free frame along strongly curved paths prefer
    :meth:`geoviz_plots.geomodel.borehole_tunnel.TunnelMeshGenerator.generate_tube`,
    which propagates a rotation-minimizing frame.
    """
    path = [np.array(p, dtype=np.float32) for p in path]
    if len(path) < 2:
        return _EMPTY

    vertices = []
    for j, p in enumerate(path):
        if j == 0:
            tangent = path[1] - path[0]
        elif j == len(path) - 1:
            tangent = path[-1] - path[-2]
        else:
            tangent = path[j + 1] - path[j - 1]

        tang_len = np.linalg.norm(tangent)
        tangent = np.array([0.0, 0.0, 1.0], dtype=np.float32) if tang_len == 0 else tangent / tang_len
        ortho1, ortho2 = _orthonormal_basis(tangent)

        for i in range(resolution):
            theta = 2 * np.pi * i / resolution
            vertices.append(p + np.cos(theta) * radius * ortho1 + np.sin(theta) * radius * ortho2)

    faces = []
    for j in range(len(path) - 1):
        ring = j * resolution
        next_ring = (j + 1) * resolution
        for i in range(resolution):
            next_i = (i + 1) % resolution
            faces.append([ring + i, ring + next_i, next_ring + i])
            faces.append([ring + next_i, next_ring + next_i, next_ring + i])

    return _finish(vertices, faces, color)


def generate_fault_geometry(
    xlim=(-100, 100),
    ylim=(-100, 100),
    nx: int = 40,
    ny: int = 40,
    color=(0.1, 0.6, 0.8, 0.8),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Demo dome surface offset by a synthetic fault throw along ``Y = 0.5*X + 10``.

    Kept for the modelling page's placeholder scene; real structural surfaces should
    come from horizon grids plus
    :meth:`geoviz_plots.geomodel.fault_dislocation.FaultCuttingEngine.apply_dislocation`.
    """
    xs = np.linspace(xlim[0], xlim[1], nx)
    ys = np.linspace(ylim[0], ylim[1], ny)
    grid_x, grid_y = np.meshgrid(xs, ys)

    grid_z = 15.0 * np.sin(grid_x / 50.0) * np.cos(grid_y / 50.0)
    grid_z[grid_y > (0.5 * grid_x + 10.0)] += 25.0

    vertices = np.column_stack([grid_x.ravel(), grid_y.ravel(), grid_z.ravel()])

    faces = []
    for r in range(ny - 1):
        for c in range(nx - 1):
            v0 = r * nx + c
            v1 = v0 + 1
            v2 = (r + 1) * nx + c
            v3 = v2 + 1
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    return _finish(vertices, faces, color)


def _finish(vertices, faces, color) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    verts = np.asarray(vertices, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int32)
    colors = np.tile(color, (len(faces), 1)).astype(np.float32)
    return verts, faces, colors
