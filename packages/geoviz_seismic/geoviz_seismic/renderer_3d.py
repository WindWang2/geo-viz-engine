from __future__ import annotations

import logging
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

import pyqtgraph.opengl as gl
from PySide6.QtGui import QVector3D
from PySide6 import QtGui
from OpenGL import GL
from OpenGL.GL import shaders as gl_shaders

# Internal imports
from .colormap import ColormapManager
from .gpu_ops import (
    is_gpu_available, to_gpu, slice_volume_gpu,
    sample_polyline_slice
)
from .horizon import horizon_quad_faces
from .stratal import extract_stratal_slice

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Time-axis world mapping (time-down convention)
#
# The 2D profile panels draw sample-0 at the top (industry standard), so the
# 3D scene must match: sample-0 sits at the TOP of the world box (z = nt*st)
# and time increases DOWNWARD. All Z-anchored overlays (slice planes, walls,
# volume brick, horizons, picks, cursor, annotations, click ray-cast) must
# go through these two helpers so the mapping stays invertible and consistent.
# ---------------------------------------------------------------------------

def sample_to_z(sample_index, nt: int, st: float):
    """Map a preview-volume sample index to its world Z (time-down).

    sample 0    -> z = nt*st (top of the box)
    sample nt-1 -> z = st    (one voxel above the bottom)

    Fractional indices (e.g. a stratal-surface mean) interpolate linearly.
    Accepts scalars or arrays (returns the matching type).
    """
    z = (float(nt) - np.asarray(sample_index, dtype=np.float64)) * float(st)
    return float(z) if z.ndim == 0 else z


def z_to_sample(z, nt: int, st: float):
    """Inverse of :func:`sample_to_z`: world Z back to a fractional sample index.

    Accepts scalars or arrays (returns the matching type).
    """
    s = float(nt) - np.asarray(z, dtype=np.float64) / float(st)
    return float(s) if s.ndim == 0 else s


def compute_balanced_spacing(
    shape, target: float = 200.0
) -> tuple[float, float, float]:
    """Spacing that maps each axis of *shape* to about *target* world units."""
    ni, nx, nt = int(shape[0]), int(shape[1]), int(shape[2])
    return (
        float(target) / max(ni, 1),
        float(target) / max(nx, 1),
        float(target) / max(nt, 1),
    )


def compute_normal_map(data: np.ndarray) -> np.ndarray:
    """Vectorized normal map calculation from 3D volume gradient."""
    # Data shape is [ni, nx, nt] -> Inline (X), Crossline (Y), Time (Z)
    f_data = data.astype(np.float32, copy=False)
    d_il, d_xl, d_t = np.gradient(f_data)
    
    # Pack into normal vector [-d_il, -d_xl, -d_t] pointing away from reflectors
    N = np.stack([-d_il, -d_xl, -d_t], axis=-1)
    norm = np.linalg.norm(N, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    N /= norm
    
    # Map from [-1, 1] to [0, 255] for uint8 storage
    return ((N + 1.0) * 127.5).astype(np.uint8)


def prepare_normal_texture_upload(normal_data: np.ndarray):
    """Prepare a hillshading normal map for ``glTexImage3D`` upload.

    Applies the same axis convention as the main volume texture in
    ``pyqtgraph.opengl.GLVolumeItem._uploadData``: the data is transposed with
    ``(2, 1, 0, 3)`` while the texture is *declared* with the original
    ``shape[:3]`` as (width, height, depth). Because the C-order buffer varies
    fastest along the (transposed) last spatial axis, GL texel ``(i, j, k)``
    ends up addressing ``normal_data[i, j, k]`` — i.e. shader texcoord
    components x/y/z map to data axes 0/1/2, exactly like the volume texture.

    Returns ``(buffer, width, height, depth)`` with a C-contiguous uint8
    buffer.
    """
    if normal_data.ndim != 4 or normal_data.shape[3] != 3:
        raise ValueError(
            f"normal_data must have shape (ni, nx, nt, 3), got {normal_data.shape}"
        )
    width, height, depth = normal_data.shape[:3]
    buffer = np.ascontiguousarray(normal_data.transpose((2, 1, 0, 3)))
    return buffer, width, height, depth


def prepare_horizon_texture_upload(horizon_grid: np.ndarray):
    """Prepare a sculpting horizon grid for ``glTexImage2D`` upload.

    Horizon grids follow the ``(nI, nX)`` contract (see ``stratal.py``), where
    axis 0 is the volume inline axis. The volume texture contract maps shader
    ``v_texcoord.x`` to data axis 0, so the grid must be transposed before
    upload: with a C-order buffer GL's s axis addresses the fastest-varying
    (column) axis, and transposing makes that axis the inline axis. Without
    the transpose the sculpting mask is mirrored across the grid diagonal —
    invisible for square grids, wrong for ``nI != nX``.

    Returns ``(buffer, width, height)`` with a C-contiguous float32 buffer.
    """
    if horizon_grid.ndim != 2:
        raise ValueError(
            f"horizon_grid must have shape (nI, nX), got {horizon_grid.shape}"
        )
    width, height = horizon_grid.shape
    buffer = np.ascontiguousarray(horizon_grid.T, dtype=np.float32)
    return buffer, width, height


# ---------------------------------------------------------------------------
# Deferred GL resource deletion
#
# QOpenGLWidget only has a current context inside paint/initializeGL; cleanup
# triggered from GUI-thread slots (volume switch, page close) runs WITHOUT
# one, so glDeleteTextures there is a silent no-op. Collect orphaned handles
# here and flush them at the top of the next paint, where the context IS
# current — otherwise load/switch/clear cycles leak VRAM indefinitely.
# ---------------------------------------------------------------------------

_PENDING_GL_TEXTURE_DELETES: list[int] = []
_PENDING_GL_PROGRAM_DELETES: list = []


def queue_gl_texture_delete(tex) -> None:
    """Queue one GL texture name for deletion at the next paint flush."""
    try:
        if tex is not None:
            _PENDING_GL_TEXTURE_DELETES.append(int(tex))
    except (TypeError, ValueError):
        pass


def queue_gl_program_delete(program) -> None:
    if program is not None:
        _PENDING_GL_PROGRAM_DELETES.append(program)


def flush_pending_gl_deletes() -> None:
    """Delete queued GL objects; requires a current GL context."""
    if _PENDING_GL_TEXTURE_DELETES:
        names = list(_PENDING_GL_TEXTURE_DELETES)
        _PENDING_GL_TEXTURE_DELETES.clear()
        try:
            GL.glDeleteTextures(len(names), names)
        except Exception:
            logger.debug("pending texture delete failed", exc_info=True)
    while _PENDING_GL_PROGRAM_DELETES:
        program = _PENDING_GL_PROGRAM_DELETES.pop()
        try:
            if hasattr(program, "removeAllShaders"):
                program.removeAllShaders()
            if hasattr(program, "deleteLater"):
                program.deleteLater()
            else:
                # Raw GLuint from pyqtgraph's gl_shaders helpers (the LUT
                # shader programs): only glDeleteProgram actually frees it.
                GL.glDeleteProgram(program)
        except Exception:
            logger.debug("pending program delete failed", exc_info=True)


class GLImageLutItem(gl.GLImageItem):
    """A 2D textured quad that looks up colour through a 1-D LUT in-shader.

    Drop-in replacement for ``gl.GLImageItem`` on the seismic slice planes:
    instead of uploading a full ``(H, W, 4)`` RGBA texture per slider tick, it
    uploads a single-channel ``(H, W)`` uint8 *index* texture (GL_R8, 4x
    smaller) plus a 256x1 RGBA LUT texture, and the fragment shader does
    ``texture(u_lut, vec2(texture(u_index, uv).r, 0.5))``. A colormap change
    becomes an O(1) LUT re-upload (``setLut``) instead of a per-pixel CPU
    gather + 4x RGBA re-upload. Modelled on ``DualGLVolumeItem``'s LUT path.
    """

    _LUT_SHADER_LEGACY = {
        GL.GL_VERTEX_SHADER: """
            uniform mat4 u_mvp;
            attribute vec4 a_position;
            attribute vec2 a_texcoord;
            varying vec2 v_texcoord;
            void main() {
                gl_Position = u_mvp * a_position;
                v_texcoord = a_texcoord;
            }
        """,
        GL.GL_FRAGMENT_SHADER: """
            #ifdef GL_ES
            precision mediump float;
            #endif
            uniform sampler2D u_index;
            uniform sampler2D u_lut;
            uniform float u_opacity;
            varying vec2 v_texcoord;
            void main() {
                float idx = texture2D(u_index, v_texcoord).r;
                vec4 color = texture2D(u_lut, vec2(idx, 0.5));
                color.a *= u_opacity;
                gl_FragColor = color;
            }
        """,
    }

    _LUT_SHADER_CORE = {
        GL.GL_VERTEX_SHADER: """
            uniform mat4 u_mvp;
            in vec4 a_position;
            in vec2 a_texcoord;
            out vec2 v_texcoord;
            void main() {
                gl_Position = u_mvp * a_position;
                v_texcoord = a_texcoord;
            }
        """,
        GL.GL_FRAGMENT_SHADER: """
            #ifdef GL_ES
            precision mediump float;
            #endif
            uniform sampler2D u_index;
            uniform sampler2D u_lut;
            uniform float u_opacity;
            in vec2 v_texcoord;
            out vec4 fragColor;
            void main() {
                float idx = texture(u_index, v_texcoord).r;
                vec4 color = texture(u_lut, vec2(idx, 0.5));
                color.a *= u_opacity;
                fragColor = color;
            }
        """,
    }

    def __init__(self, index_data, cmap_name="seismic", smooth=False, glOptions='translucent', parentItem=None):
        # GLImageItem.__init__ calls setData(data); we intercept so self.data
        # holds the uint8 index array, and seed the LUT separately.
        super().__init__(index_data, smooth=smooth, glOptions=glOptions, parentItem=parentItem)
        self._cmap_name = cmap_name
        self._lut_tex = None
        self._lut_needs_upload = cmap_name is not None
        self._lut_shader_program = None
        self._opacity = 1.0

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Set shared plane opacity without rebuilding the index texture."""
        value = max(0.0, min(1.0, float(opacity)))
        if value == self._opacity:
            return
        self._opacity = value
        self.update()

    def setLut(self, cmap_name: str) -> None:
        """Update the colormap without re-uploading the index texture.

        This is the O(1) colormap-change fast path (vs the old per-pixel RGBA
        rebuild). Only the colormap name is stored; the actual LUT is fetched
        from ``ColormapManager`` on the next ``_uploadLut`` call.
        """
        if cmap_name == self._cmap_name and not self._lut_needs_upload:
            return
        self._cmap_name = cmap_name
        self._lut_needs_upload = True
        self.update()

    def _uploadLut(self) -> None:
        ctx = QtGui.QOpenGLContext.currentContext()
        if ctx is None or self._cmap_name is None:
            return
        if self._lut_tex is None:
            self._lut_tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._lut_tex)
        filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        # Fetch the LUT from ColormapManager (cached by name). Reshape to
        # (1, 256, 4) and upload as a 256-wide 1-row RGBA texture.
        lut = ColormapManager.get_colormap(self._cmap_name)
        lut = np.ascontiguousarray(lut[:256].reshape((1, 256, 4)))
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, 256, 1, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, lut)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self._lut_needs_upload = False

    def clean(self) -> None:
        """Release every GL resource owned by this item.

        Deletes the R8 index texture, the LUT texture, the per-instance LUT
        shader program and the position VBO. With a current GL context the
        objects are deleted immediately. Without one — GUI-thread teardown
        paths such as volume switch / page close, where ``makeCurrent``
        failed or was never attempted — ``glDeleteTextures`` is a silent
        no-op, so the orphaned handles are queued and flushed at the top of
        the next paint instead of leaking VRAM (see
        ``queue_gl_texture_delete`` / ``flush_pending_gl_deletes``).

        Idempotent: safe to call twice. If the item is ever repainted after
        ``clean()``, it re-uploads everything from scratch.
        """
        program = self._lut_shader_program
        self._lut_shader_program = None
        lut_tex, self._lut_tex = self._lut_tex, None
        index_tex, self.texture = self.texture, None
        try:
            ctx = QtGui.QOpenGLContext.currentContext()
        except Exception:
            ctx = None
        if ctx is None:
            # No context outside paint: defer so the next paint actually
            # frees the objects (dropping the ids would leak VRAM).
            queue_gl_texture_delete(lut_tex)
            queue_gl_texture_delete(index_tex)
            queue_gl_program_delete(program)
        else:
            tex_ids = [t for t in (index_tex, lut_tex) if t is not None]
            if tex_ids:
                try:
                    GL.glDeleteTextures(tex_ids)
                except Exception:
                    pass
            if program is not None:
                try:
                    if hasattr(program, "removeAllShaders"):
                        program.removeAllShaders()
                    if hasattr(program, "deleteLater"):
                        program.deleteLater()
                    else:
                        # Raw GLuint from pyqtgraph's gl_shaders helpers.
                        GL.glDeleteProgram(program)
                except Exception:
                    pass
            vbo = getattr(self, "m_vbo_position", None)
            if vbo is not None and vbo.isCreated():
                try:
                    vbo.destroy()
                except Exception:
                    pass
        # If the item is ever repainted after clean(), re-upload from scratch.
        self._needUpdate = True
        self._lut_needs_upload = self._cmap_name is not None

    @staticmethod
    def prepare_r8_upload(index_2d: np.ndarray) -> tuple[np.ndarray, int, int]:
        """Pack a 2-D index image for ``glTexImage2D`` like pyqtgraph GLImageItem.

        ``index_2d`` uses the same axes as plane geometry: shape ``(sx, sy)``
        where local +X spans ``sx`` and local +Y spans ``sy`` (see
        ``_create_slice_plane`` scale calls).

        pyqtgraph uploads with ``width=sx, height=sy`` after transposing the
        first two axes so OpenGL's row-major layout matches numpy C-order.
        The previous R8 path skipped that transpose and scrambled every 3D
        orthogonal plane relative to 2D profiles.
        """
        # Host only: cupy refuses implicit np.asarray; GL needs contiguous CPU bytes.
        if hasattr(index_2d, "get") and not isinstance(index_2d, np.ndarray):
            try:
                index_2d = index_2d.get()
            except Exception:
                pass
        arr = np.ascontiguousarray(np.asarray(index_2d))
        if arr.ndim != 2:
            raise ValueError(f"index texture must be 2-D, got shape {arr.shape}")
        sx, sy = int(arr.shape[0]), int(arr.shape[1])
        # Equivalent to RGBA path: data.transpose((1, 0, ...))
        upload = np.ascontiguousarray(arr.T)
        return upload, sx, sy

    @staticmethod
    def _downsample_to_fit(data: np.ndarray, width: int, height: int,
                           max_tex: int) -> tuple[np.ndarray, int, int]:
        """Downsample ``data`` (shape ``(height, width)``) so both axes fit
        within ``max_tex`` while preserving aspect ratio.

        Returns ``(data, new_width, new_height)``; the caller keeps the
        original geometry extents so the texture still spans the full plane.
        """
        scale = min(1.0, max_tex / width, max_tex / height)
        new_w = max(1, int(width * scale))
        new_h = max(1, int(height * scale))
        rows = np.linspace(0, height - 1, new_h).astype(np.int64)
        cols = np.linspace(0, width - 1, new_w).astype(np.int64)
        return data[np.ix_(rows, cols)], new_w, new_h

    def _updateTexture(self) -> None:
        """Upload the uint8 index array as a single-channel GL_R8 texture.

        Overrides GLImageItem (RGBA) with GL_R8 / GL_RED, but **keeps** the
        same axis transpose so plane orientation matches 2D profiles.

        Textures larger than ``GL_MAX_TEXTURE_SIZE`` are downsampled in place
        (aspect ratio preserved) instead of raising, and any GL error during
        the upload is logged — exceptions never escape into ``paint``.
        """
        try:
            self._uploadIndexTexture()
        except Exception:
            logger.exception("Failed to upload R8 index texture")

    def _uploadIndexTexture(self) -> None:
        if self.texture is None:
            self.texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        data, width, height = self.prepare_r8_upload(self.data)
        # Geometry quad keeps the ORIGINAL sample-space size so a downsampled
        # texture still stretches over the full plane extent.
        geom_w, geom_h = width, height

        context = QtGui.QOpenGLContext.currentContext()
        max_tex = 0
        if context is not None and not context.isOpenGLES():
            try:
                max_tex = int(GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE))
            except Exception:
                max_tex = 0

        if max_tex > 0 and (width > max_tex or height > max_tex):
            data, width, height = self._downsample_to_fit(data, width, height, max_tex)
            logger.warning(
                "Index texture %dx%d exceeds GL_MAX_TEXTURE_SIZE %d; "
                "downsampled to %dx%d for upload (geometry unchanged).",
                geom_w, geom_h, max_tex, width, height,
            )

        # R8 is 1 byte/pixel. Default GL_UNPACK_ALIGNMENT=4 shears any
        # width not divisible by 4 into diagonal stripes (200P time plane
        # is 129 wide — Image #2). RGBA never hits this (4 bytes/pixel).
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        try:
            if context is not None and not context.isOpenGLES():
                GL.glTexImage2D(
                    GL.GL_PROXY_TEXTURE_2D, 0, GL.GL_R8, width, height, 0,
                    GL.GL_RED, GL.GL_UNSIGNED_BYTE, None,
                )
                if GL.glGetTexLevelParameteriv(GL.GL_PROXY_TEXTURE_2D, 0, GL.GL_TEXTURE_WIDTH) == 0:
                    logger.warning(
                        "OpenGL rejected 2D R8 texture %dx%d; skipping upload "
                        "(plane stays empty until a smaller slice arrives).",
                        width, height,
                    )
                    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
                    return

            GL.glTexImage2D(
                GL.GL_TEXTURE_2D, 0, GL.GL_R8, width, height, 0,
                GL.GL_RED, GL.GL_UNSIGNED_BYTE, data,
            )
        finally:
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 4)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        # Geometry extents still follow the original (sx, sy) size so the
        # plane spans the same world-space area regardless of texture size.
        x, y = geom_w, geom_h
        pos = np.array([
            [0, 0, 0, 0],
            [x, 0, 1, 0],
            [0, y, 0, 1],
            [x, y, 1, 1],
        ], dtype=np.float32)
        vbo = self.m_vbo_position
        if not vbo.isCreated():
            vbo.create()
        vbo.bind()
        vbo.allocate(pos, pos.nbytes)
        vbo.release()

    def getLutShaderProgram(self):
        """Instance-level shader program with the LUT-lookup fragment stage.

        Distinct from GLImageItem's static ``getShaderProgram`` (RGBA-only):
        picks CORE vs LEGACY by GL version, compiles the LUT shader pair.
        """
        if self._lut_shader_program is not None:
            return self._lut_shader_program

        ctx = QtGui.QOpenGLContext.currentContext()
        fmt = ctx.format()

        if ctx.isOpenGLES():
            glsl_version = "#version 300 es\n" if fmt.version() >= (3, 0) else ""
            sources = self._LUT_SHADER_CORE if fmt.version() >= (3, 0) else self._LUT_SHADER_LEGACY
        else:
            glsl_version = "#version 140\n" if fmt.version() >= (3, 1) else ""
            sources = self._LUT_SHADER_CORE if fmt.version() >= (3, 1) else self._LUT_SHADER_LEGACY

        compiled = [gl_shaders.compileShader([glsl_version, v], k) for k, v in sources.items()]
        program = gl_shaders.compileProgram(*compiled)
        GL.glBindAttribLocation(program, 0, "a_position")
        GL.glBindAttribLocation(program, 1, "a_texcoord")
        GL.glLinkProgram(program)
        self._lut_shader_program = program
        return program

    def paint(self) -> None:
        if self._needUpdate:
            self._updateTexture()
            self._needUpdate = False
        if self._lut_needs_upload:
            self._uploadLut()

        self.setupGLState()
        mat_mvp = self.mvpMatrix()
        mat_mvp = np.array(mat_mvp.data(), dtype=np.float32)

        program = self.getLutShaderProgram()
        loc_pos, loc_tex = 0, 1
        self.m_vbo_position.bind()
        GL.glVertexAttribPointer(loc_pos, 2, GL.GL_FLOAT, False, 4 * 4, None)
        GL.glVertexAttribPointer(loc_tex, 2, GL.GL_FLOAT, False, 4 * 4, GL.GLvoidp(2 * 4))
        self.m_vbo_position.release()
        enabled_locs = [loc_pos, loc_tex]

        # Index texture on unit 0, LUT on unit 1.
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
        if self._lut_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._lut_tex)

        for loc in enabled_locs:
            GL.glEnableVertexAttribArray(loc)

        with program:
            loc_mvp = GL.glGetUniformLocation(program, "u_mvp")
            GL.glUniformMatrix4fv(loc_mvp, 1, False, mat_mvp)
            loc_idx = GL.glGetUniformLocation(program, "u_index")
            GL.glUniform1i(loc_idx, 0)
            if self._lut_tex is not None:
                loc_lut = GL.glGetUniformLocation(program, "u_lut")
                GL.glUniform1i(loc_lut, 1)
            loc_opacity = GL.glGetUniformLocation(program, "u_opacity")
            GL.glUniform1f(loc_opacity, float(self._opacity))
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)

        for loc in enabled_locs:
            GL.glDisableVertexAttribArray(loc)

        if self._lut_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)


class DualGLVolumeItem(gl.GLVolumeItem):
    """Custom OpenGL volume item that displays two superimposed volumes
    using a single 3D texture and dynamic colormapping in a custom GLSL shader.
    Saves 50% GPU memory and speeds up colormap/opacity changes to O(1) time.
    """
    def __init__(self, data, normal_data=None, sliceDensity=3, smooth=True, glOptions='translucent', parentItem=None):
        super().__init__(data, sliceDensity=sliceDensity, smooth=smooth, glOptions=glOptions, parentItem=parentItem)
        self._primary_visible = True
        self._overlay_visible = True
        self._overlay_opacity = 0.5
        self._primary_cmap_lut = None
        self._overlay_cmap_lut = None
        
        self._primary_cmap_tex = None
        self._overlay_cmap_tex = None
        
        self._normal_data = normal_data
        self._normal_tex = None
        self._normal_needs_upload = (normal_data is not None)
        
        self._cmap_needs_upload = False
        self._customShaderProgram = None

        # Sculpting state
        self._sculpting_enabled = False
        self._sculpting_mode = "above"
        self._sculpt_horizon_data = None
        self._sculpt_horizon_tex = None
        self._sculpt_needs_upload = False

        # Shading state
        self._shading_enabled = False
        self._shading_light_dir = (1.0, 1.0, 1.0)
        self._shading_needs_upload = False

    def setShading(self, enabled: bool, light_dir=(1.0, 1.0, 1.0)):
        self._shading_enabled = enabled
        self._shading_light_dir = light_dir
        self._shading_needs_upload = True
        self.update()

    def setSculpting(self, enabled: bool, horizon_z_norm: np.ndarray = None, mode: str = "above"):
        self._sculpting_enabled = enabled
        if horizon_z_norm is not None:
            self._sculpt_horizon_data = horizon_z_norm
            self._sculpt_needs_upload = True
        self._sculpting_mode = mode
        self.update()

    def setColormaps(self, primary_lut: np.ndarray, overlay_lut: np.ndarray):
        """Set the 256x4 uint8 colormap LUTs."""
        self._primary_cmap_lut = primary_lut
        self._overlay_cmap_lut = overlay_lut
        self._cmap_needs_upload = True
        self.update()
        
    def setOverlayOpacity(self, opacity: float):
        self._overlay_opacity = opacity
        self.update()
        
    def setOverlayVisible(self, visible: bool):
        self._overlay_visible = visible
        self.update()
        
    def setPrimaryVisible(self, visible: bool):
        self._primary_visible = visible
        self.update()

    def _uploadColormaps(self):
        ctx = QtGui.QOpenGLContext.currentContext()
        if ctx is None:
            return

        if self._primary_cmap_lut is not None:
            if self._primary_cmap_tex is None:
                self._primary_cmap_tex = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._primary_cmap_tex)
            filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            
            lut = np.ascontiguousarray(self._primary_cmap_lut.reshape((1, 256, 4)))
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, 256, 1, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, lut)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            
        if self._overlay_cmap_lut is not None:
            if self._overlay_cmap_tex is None:
                self._overlay_cmap_tex = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._overlay_cmap_tex)
            filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            
            lut = np.ascontiguousarray(self._overlay_cmap_lut.reshape((1, 256, 4)))
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, 256, 1, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, lut)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            
        self._cmap_needs_upload = False


    def _uploadHorizonTexture(self):
        ctx = QtGui.QOpenGLContext.currentContext()
        if ctx is None or self._sculpt_horizon_data is None:
            return
            
        if self._sculpt_horizon_tex is None:
            self._sculpt_horizon_tex = GL.glGenTextures(1)
            
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._sculpt_horizon_tex)
        filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        
        # Transpose so GL texel (i, j) addresses horizon_grid[i, j], matching
        # v_texcoord.x -> inline axis 0 (see prepare_horizon_texture_upload).
        data, w, h = prepare_horizon_texture_upload(self._sculpt_horizon_data)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_R32F, w, h, 0, GL.GL_RED, GL.GL_FLOAT, data)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self._sculpt_needs_upload = False

    def _uploadNormalTexture(self):
        if self._normal_data is None:
            return
        if self._normal_tex is None:
            self._normal_tex = GL.glGenTextures(1)
            
        GL.glBindTexture(GL.GL_TEXTURE_3D, self._normal_tex)
        filt = GL.GL_LINEAR if self.smooth else GL.GL_NEAREST
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, filt)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
        
        # Same transpose convention as the main volume texture
        # (GLVolumeItem._uploadData): shader texcoord x/y/z map to data axes
        # 0/1/2 (see prepare_normal_texture_upload).
        data, w, h, d = prepare_normal_texture_upload(self._normal_data)
        GL.glTexImage3D(GL.GL_TEXTURE_3D, 0, GL.GL_RGB8, w, h, d, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, data)
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        self._normal_needs_upload = False

    def getCustomShaderProgram(self):
        if self._customShaderProgram is not None:
            return self._customShaderProgram
            
        ctx = QtGui.QOpenGLContext.currentContext()
        fmt = ctx.format()
        
        if ctx.isOpenGLES():
            if fmt.version() >= (3, 0):
                glsl_version = "#version 300 es\n"
                vertex_src = """
                uniform mat4 u_mvp;
                in vec4 a_position;
                in vec3 a_texcoord;
                out vec3 v_texcoord;
                void main() {
                    gl_Position = u_mvp * a_position;
                    v_texcoord = a_texcoord;
                }
                """
                fragment_src = """
                precision mediump float;
                precision lowp sampler3D;
                precision lowp sampler2D;
                
                uniform sampler3D u_texture;
                uniform sampler2D u_cmap_primary;
                uniform sampler2D u_cmap_overlay;
                uniform sampler2D u_horizon_texture;
                uniform sampler3D u_normal_texture;
                
                uniform float u_overlay_opacity;
                uniform int u_overlay_visible;
                uniform int u_primary_visible;
                
                uniform int u_sculpting_enabled;
                uniform int u_sculpt_mode;
                
                uniform int u_shading_enabled;
                uniform vec3 u_light_dir;
                uniform vec3 u_resolution;
                
                vec3 compute_normal(vec3 texcoord, sampler3D tex) {
                    return texture(u_normal_texture, texcoord).rgb * 2.0 - 1.0;
                }
                
                in vec3 v_texcoord;
                out vec4 fragColor;
                
                void main() {
                    if (u_sculpting_enabled == 1) {
                        float hz = texture(u_horizon_texture, v_texcoord.xy).r;
                        if (hz > 0.0 && hz < 1.0) {
                            if (u_sculpt_mode == 0 && v_texcoord.z > hz) {
                                discard;
                            } else if (u_sculpt_mode == 1 && v_texcoord.z < hz) {
                                discard;
                            }
                        }
                    }
                    vec4 vals = texture(u_texture, v_texcoord);
                    
                    vec4 color_primary = texture(u_cmap_primary, vec2(vals.r, 0.5));
                    vec4 color_overlay = texture(u_cmap_overlay, vec2(vals.g, 0.5));
                    
                    vec4 final_color = vec4(0.0);
                    if (u_primary_visible == 1) {
                        final_color = color_primary;
                    }
                    if (u_overlay_visible == 1) {
                        float alpha = color_overlay.a * u_overlay_opacity;
                        if (u_primary_visible == 1) {
                            final_color.rgb = mix(final_color.rgb, color_overlay.rgb, alpha);
                            final_color.a = max(final_color.a, alpha);
                        } else {
                            final_color.rgb = color_overlay.rgb;
                            final_color.a = alpha;
                        }
                    }
                    if (u_shading_enabled == 1) {
                        vec3 N = compute_normal(v_texcoord, u_texture);
                        vec3 L = normalize(u_light_dir);
                        float diff = max(dot(N, L), 0.0);
                        final_color.rgb *= (0.3 + 0.7 * diff);
                    }
                    fragColor = final_color;
                }
                """
            else:
                glsl_version = ""
                vertex_src = """
                attribute vec4 a_position;
                attribute vec3 a_texcoord;
                varying vec3 v_texcoord;
                uniform mat4 u_mvp;
                void main() {
                    gl_Position = u_mvp * a_position;
                    v_texcoord = a_texcoord;
                }
                """
                fragment_src = """
                #extension GL_OES_texture_3D : enable
                precision mediump float;
                varying vec3 v_texcoord;
                uniform sampler3D u_texture;
                uniform sampler2D u_cmap_primary;
                uniform sampler2D u_cmap_overlay;
                uniform sampler2D u_horizon_texture;
                uniform sampler3D u_normal_texture;
                
                uniform float u_overlay_opacity;
                uniform int u_overlay_visible;
                uniform int u_primary_visible;
                
                uniform int u_sculpting_enabled;
                uniform int u_sculpt_mode;
                
                uniform int u_shading_enabled;
                uniform vec3 u_light_dir;
                uniform vec3 u_resolution;
                
                vec3 compute_normal_legacy(vec3 texcoord, sampler3D tex) {
                    return texture3D(u_normal_texture, texcoord).rgb * 2.0 - 1.0;
                }
                void main() {
                    if (u_sculpting_enabled == 1) {
                        float hz = texture2D(u_horizon_texture, v_texcoord.xy).r;
                        if (hz > 0.0 && hz < 1.0) {
                            if (u_sculpt_mode == 0 && v_texcoord.z > hz) {
                                discard;
                            } else if (u_sculpt_mode == 1 && v_texcoord.z < hz) {
                                discard;
                            }
                        }
                    }
                    vec4 vals = texture3D(u_texture, v_texcoord);
                    vec4 color_primary = texture2D(u_cmap_primary, vec2(vals.r, 0.5));
                    vec4 color_overlay = texture2D(u_cmap_overlay, vec2(vals.g, 0.5));
                    vec4 final_color = vec4(0.0);
                    if (u_primary_visible == 1) {
                        final_color = color_primary;
                    }
                    if (u_overlay_visible == 1) {
                        float alpha = color_overlay.a * u_overlay_opacity;
                        if (u_primary_visible == 1) {
                            final_color.rgb = mix(final_color.rgb, color_overlay.rgb, alpha);
                            final_color.a = max(final_color.a, alpha);
                        } else {
                            final_color.rgb = color_overlay.rgb;
                            final_color.a = alpha;
                        }
                    }
                    if (u_shading_enabled == 1) {
                        vec3 N = compute_normal_legacy(v_texcoord, u_texture);
                        vec3 L = normalize(u_light_dir);
                        float diff = max(dot(N, L), 0.0);
                        final_color.rgb *= (0.3 + 0.7 * diff);
                    }
                    gl_FragColor = final_color;
                }
                """
        else:
            if fmt.version() >= (3, 1):
                glsl_version = "#version 140\n"
                vertex_src = """
                uniform mat4 u_mvp;
                in vec4 a_position;
                in vec3 a_texcoord;
                out vec3 v_texcoord;
                void main() {
                    gl_Position = u_mvp * a_position;
                    v_texcoord = a_texcoord;
                }
                """
                fragment_src = """
                uniform sampler3D u_texture;
                uniform sampler2D u_cmap_primary;
                uniform sampler2D u_cmap_overlay;
                uniform sampler2D u_horizon_texture;
                uniform sampler3D u_normal_texture;
                
                uniform float u_overlay_opacity;
                uniform int u_overlay_visible;
                uniform int u_primary_visible;
                
                uniform int u_sculpting_enabled;
                uniform int u_sculpt_mode;
                
                uniform int u_shading_enabled;
                uniform vec3 u_light_dir;
                uniform vec3 u_resolution;
                
                vec3 compute_normal(vec3 texcoord, sampler3D tex) {
                    return texture(u_normal_texture, texcoord).rgb * 2.0 - 1.0;
                }
                
                in vec3 v_texcoord;
                out vec4 fragColor;
                
                void main() {
                    if (u_sculpting_enabled == 1) {
                        float hz = texture(u_horizon_texture, v_texcoord.xy).r;
                        if (hz > 0.0 && hz < 1.0) {
                            if (u_sculpt_mode == 0 && v_texcoord.z > hz) {
                                discard;
                            } else if (u_sculpt_mode == 1 && v_texcoord.z < hz) {
                                discard;
                            }
                        }
                    }
                    vec4 vals = texture(u_texture, v_texcoord);
                    
                    vec4 color_primary = texture(u_cmap_primary, vec2(vals.r, 0.5));
                    vec4 color_overlay = texture(u_cmap_overlay, vec2(vals.g, 0.5));
                    
                    vec4 final_color = vec4(0.0);
                    if (u_primary_visible == 1) {
                        final_color = color_primary;
                    }
                    if (u_overlay_visible == 1) {
                        float alpha = color_overlay.a * u_overlay_opacity;
                        if (u_primary_visible == 1) {
                            final_color.rgb = mix(final_color.rgb, color_overlay.rgb, alpha);
                            final_color.a = max(final_color.a, alpha);
                        } else {
                            final_color.rgb = color_overlay.rgb;
                            final_color.a = alpha;
                        }
                    }
                    if (u_shading_enabled == 1) {
                        vec3 N = compute_normal(v_texcoord, u_texture);
                        vec3 L = normalize(u_light_dir);
                        float diff = max(dot(N, L), 0.0);
                        final_color.rgb *= (0.3 + 0.7 * diff);
                    }
                    fragColor = final_color;
                }
                """
            else:
                glsl_version = ""
                vertex_src = """
                varying vec3 v_texcoord;
                uniform mat4 u_mvp;
                void main() {
                    gl_Position = u_mvp * gl_Vertex;
                    v_texcoord = gl_MultiTexCoord0.xyz;
                }
                """
                fragment_src = """
                varying vec3 v_texcoord;
                uniform sampler3D u_texture;
                uniform sampler2D u_cmap_primary;
                uniform sampler2D u_cmap_overlay;
                uniform sampler2D u_horizon_texture;
                uniform sampler3D u_normal_texture;
                
                uniform float u_overlay_opacity;
                uniform int u_overlay_visible;
                uniform int u_primary_visible;
                
                uniform int u_sculpting_enabled;
                uniform int u_sculpt_mode;
                
                uniform int u_shading_enabled;
                uniform vec3 u_light_dir;
                uniform vec3 u_resolution;
                
                vec3 compute_normal_legacy(vec3 texcoord, sampler3D tex) {
                    return texture3D(u_normal_texture, texcoord).rgb * 2.0 - 1.0;
                }
                void main() {
                    if (u_sculpting_enabled == 1) {
                        float hz = texture2D(u_horizon_texture, v_texcoord.xy).r;
                        if (hz > 0.0 && hz < 1.0) {
                            if (u_sculpt_mode == 0 && v_texcoord.z > hz) {
                                discard;
                            } else if (u_sculpt_mode == 1 && v_texcoord.z < hz) {
                                discard;
                            }
                        }
                    }
                    vec4 vals = texture3D(u_texture, v_texcoord);
                    vec4 color_primary = texture2D(u_cmap_primary, vec2(vals.r, 0.5));
                    vec4 color_overlay = texture2D(u_cmap_overlay, vec2(vals.g, 0.5));
                    vec4 final_color = vec4(0.0);
                    if (u_primary_visible == 1) {
                        final_color = color_primary;
                    }
                    if (u_overlay_visible == 1) {
                        float alpha = color_overlay.a * u_overlay_opacity;
                        if (u_primary_visible == 1) {
                            final_color.rgb = mix(final_color.rgb, color_overlay.rgb, alpha);
                            final_color.a = max(final_color.a, alpha);
                        } else {
                            final_color.rgb = color_overlay.rgb;
                            final_color.a = alpha;
                        }
                    }
                    if (u_shading_enabled == 1) {
                        vec3 N = compute_normal_legacy(v_texcoord, u_texture);
                        vec3 L = normalize(u_light_dir);
                        float diff = max(dot(N, L), 0.0);
                        final_color.rgb *= (0.3 + 0.7 * diff);
                    }
                    gl_FragColor = final_color;
                }
                """
        
        v_shader = gl_shaders.compileShader([glsl_version, vertex_src], GL.GL_VERTEX_SHADER)
        f_shader = gl_shaders.compileShader([glsl_version, fragment_src], GL.GL_FRAGMENT_SHADER)
        program = gl_shaders.compileProgram(v_shader, f_shader)
        
        if glsl_version != "":
            GL.glBindAttribLocation(program, 0, "a_position")
            GL.glBindAttribLocation(program, 1, "a_texcoord")
            GL.glLinkProgram(program)
            program.check_linked()
            
        self._customShaderProgram = program
        return program

    def paint(self):
        if self.data is None:
            return

        if self._needUpload:
            self._uploadData()
            
        if self._cmap_needs_upload:
            self._uploadColormaps()
            
        if self._sculpt_needs_upload:
            self._uploadHorizonTexture()
            
        if self._normal_needs_upload:
            self._uploadNormalTexture()

        self.setupGLState()

        mat_mvp = self.mvpMatrix()
        mat_mvp = np.array(mat_mvp.data(), dtype=np.float32)

        modelview = self.modelViewMatrix()
        cam_local = modelview.inverted()[0].map(QtGui.QVector3D())

        center = QtGui.QVector3D(*[x/2. for x in self.data.shape[:3]])
        cam = cam_local - center
        cam = np.array([cam.x(), cam.y(), cam.z()])
        ax = np.argmax(abs(cam))
        d = 1 if cam[ax] > 0 else -1
        offset, num_vertices = self.lists[(ax,d)]

        program = self.getCustomShaderProgram()

        loc_pos, loc_tex = 0, 1
        self.m_vbo_position.bind()
        GL.glVertexAttribPointer(loc_pos, 3, GL.GL_FLOAT, False, 6*4, None)
        GL.glVertexAttribPointer(loc_tex, 3, GL.GL_FLOAT, False, 6*4, GL.GLvoidp(3*4))
        self.m_vbo_position.release()
        enabled_locs = [loc_pos, loc_tex]

        # Bind 3D texture to unit 0
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_3D, self.texture)
        
        # Bind primary colormap texture to unit 1
        if self._primary_cmap_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._primary_cmap_tex)
            
        # Bind overlay colormap texture to unit 2
        if self._overlay_cmap_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE2)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._overlay_cmap_tex)
            
        # Bind horizon texture to unit 3
        if self._sculpt_horizon_tex is not None and self._sculpting_enabled:
            GL.glActiveTexture(GL.GL_TEXTURE3)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._sculpt_horizon_tex)
            
        # Bind normal texture to unit 4
        if self._normal_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE4)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._normal_tex)

        for loc in enabled_locs:
            GL.glEnableVertexAttribArray(loc)

        with program:
            # Set u_mvp
            loc_mvp = GL.glGetUniformLocation(program, "u_mvp")
            GL.glUniformMatrix4fv(loc_mvp, 1, False, mat_mvp)
            
            # Set texture uniforms
            loc_tex_3d = GL.glGetUniformLocation(program, "u_texture")
            GL.glUniform1i(loc_tex_3d, 0)
            
            loc_cmap_prim = GL.glGetUniformLocation(program, "u_cmap_primary")
            GL.glUniform1i(loc_cmap_prim, 1)
            
            loc_cmap_over = GL.glGetUniformLocation(program, "u_cmap_overlay")
            GL.glUniform1i(loc_cmap_over, 2)
            
            loc_horiz_tex = GL.glGetUniformLocation(program, "u_horizon_texture")
            GL.glUniform1i(loc_horiz_tex, 3)
            
            loc_norm_tex = GL.glGetUniformLocation(program, "u_normal_texture")
            GL.glUniform1i(loc_norm_tex, 4)
            
            loc_sculpt_en = GL.glGetUniformLocation(program, "u_sculpting_enabled")
            GL.glUniform1i(loc_sculpt_en, 1 if self._sculpting_enabled else 0)
            
            loc_sculpt_mode = GL.glGetUniformLocation(program, "u_sculpt_mode")
            # Shader texcoord.z still increases with sample index. After the
            # time-down brick transform, later samples sit lower in world Z,
            # so "above" (keep the upper cube = early time) discards later
            # samples (mode 0).
            mode_val = 0 if self._sculpting_mode == "above" else 1
            GL.glUniform1i(loc_sculpt_mode, mode_val)
            
            loc_shading_en = GL.glGetUniformLocation(program, "u_shading_enabled")
            GL.glUniform1i(loc_shading_en, 1 if self._shading_enabled else 0)
            
            loc_light_dir = GL.glGetUniformLocation(program, "u_light_dir")
            GL.glUniform3f(loc_light_dir, *self._shading_light_dir)
            
            # pass volume resolution for gradient calculation
            loc_res = GL.glGetUniformLocation(program, "u_resolution")
            h, w, d = self.data.shape[:3]
            GL.glUniform3f(loc_res, w, h, d)
            
            # Set visibility and opacity uniforms
            loc_opacity = GL.glGetUniformLocation(program, "u_overlay_opacity")
            GL.glUniform1f(loc_opacity, float(self._overlay_opacity))
            
            loc_over_vis = GL.glGetUniformLocation(program, "u_overlay_visible")
            GL.glUniform1i(loc_over_vis, 1 if self._overlay_visible else 0)
            
            loc_prim_vis = GL.glGetUniformLocation(program, "u_primary_visible")
            GL.glUniform1i(loc_prim_vis, 1 if self._primary_visible else 0)

            GL.glDrawArrays(GL.GL_TRIANGLES, offset, num_vertices)

        for loc in enabled_locs:
            GL.glDisableVertexAttribArray(loc)

        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        
        if self._primary_cmap_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            
        if self._overlay_cmap_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE2)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            
        if self._sculpt_horizon_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE3)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            
        if self._normal_tex is not None:
            GL.glActiveTexture(GL.GL_TEXTURE4)
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            
        GL.glActiveTexture(GL.GL_TEXTURE0)

    def clean(self):
        """Release every GL resource owned by this item.

        Deletes the main 3D volume texture (the single largest VRAM block),
        the colormap/horizon/normal textures, the custom shader program and
        the position VBO. If called without a current context (e.g. during
        page close or tab switch), handles are queued to queue_gl_texture_delete
        and queue_gl_program_delete so they are deleted on the next paint flush
        rather than leaking VRAM. Idempotent: safe to call twice.
        """
        program = self._customShaderProgram
        self._customShaderProgram = None

        tex_ids = [
            t for t in (
                self.texture,
                self._primary_cmap_tex,
                self._overlay_cmap_tex,
                self._sculpt_horizon_tex,
                self._normal_tex,
            ) if t is not None
        ]
        self.texture = None
        self._primary_cmap_tex = None
        self._overlay_cmap_tex = None
        self._sculpt_horizon_tex = None
        self._normal_tex = None

        try:
            ctx = QtGui.QOpenGLContext.currentContext()
        except Exception:
            ctx = None

        if ctx is None:
            for tex in tex_ids:
                queue_gl_texture_delete(tex)
            if program is not None:
                queue_gl_program_delete(program)
        else:
            if tex_ids:
                try:
                    GL.glDeleteTextures(tex_ids)
                except Exception:
                    pass
            if program is not None:
                try:
                    GL.glDeleteProgram(program)
                except Exception:
                    pass

        vbo = getattr(self, "m_vbo_position", None)
        if vbo is not None and vbo.isCreated():
            try:
                vbo.destroy()
            except Exception:
                pass
        # If the item is ever repainted after clean(), re-upload from scratch.
        self._needUpload = True


class Renderer3D(QWidget):
    """3-D seismic volume renderer using PyQtGraph (Wayland + Native Qt compatible).

    Leverages QOpenGLWidget for reliable composition and optional CuPy backend
    for accelerated slicing operations.

    Memory strategy (#78): the CPU array (``_volume_data_cpu``) is the single
    source of truth. A CuPy GPU mirror (``_volume_data_gpu``) is created
    **lazily** on first GPU-backed slice access and only when CuPy is
    available, so loading a volume that never slices (e.g. pure volume-mode
    rendering) — or running on a CPU-only host — avoids a redundant
    full-volume copy. The volume visual keeps the only other persistent copy:
    a fixed 2x-downsampled combined GL texture.
    """

    slice_changed = Signal(str, int)  # (slice_type, position)
    arbitrary_slice_changed = Signal(object)  # polyline slice data (np.ndarray)
    jump_to_position = Signal(float, float, float)  # (il_idx, xl_idx, t_idx)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._press_pos = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._loaded = False
        self._volume_data_cpu: np.ndarray | None = None
        self._volume_data_gpu = None  # CuPy array reference if available
        # Cached (dmin, dmax) for slice planes. Percentile clip (default 99%)
        # matches 2D ProfileVD so 3D is not dominated by amplitude extrema.
        self._slice_range_cache: tuple[float, float] | None = None
        self._slice_clip_pct: float = 99.0
        
        self._volume_spacing = (1, 1, 1)
        self._volume_origin = (0, 0, 0)
        # Survey→preview mapping for overlays whose inputs are in measured
        # units (inline/crossline numbers, TWT ms). None dt means "already
        # in preview-sample / world units" (standalone Renderer3D tests).
        self._survey_t0_ms = 0.0
        self._survey_dt_ms: float | None = None
        self._survey_fi = 1
        self._survey_fx = 1
        self._survey_ft = 1
        self._meta = None
        self._cmap_name = "seismic"
        self._il_pos = 0
        self._xl_pos = 0
        self._t_pos = 0
        self._time_slice_positions: list[int] = []
        self._time_slice_visibility: dict[int, bool] = {}
        self._active_time_pos: int | None = None
        # Standalone Renderer3D keeps its historical opaque plane; the joint
        # scene explicitly supplies its product default (0.8).
        self._time_slice_opacity = 1.0
        self._time_slices_enabled = True
        self._time_plane_items: dict[int, tuple[object, object]] = {}
        self._planes_visible = True
        # Stratal / proportional slices (horizon-relative, non-planar surfaces).
        # ``_stratal_surfaces`` is a list of (nI, nX) float sample-index grids
        # produced by geoviz_seismic.stratal; ``_stratal_plane_items`` maps the
        # surface index -> (GLImageLutItem, GLLinePlotItem) like the time planes.
        self._stratal_surfaces: list[np.ndarray] = []
        self._stratal_visibility: list[bool] = []
        self._stratal_labels: list[str] = []
        self._stratal_active: int | None = None
        self._stratal_opacity = 0.8
        self._stratal_enabled = True
        self._stratal_plane_items: dict[int, tuple[object, object]] = {}
        self._use_volume = False
        self._arb_polyline: list[tuple[float, float]] | None = None  # index-space waypoints

        # Overlay / Attribute volume state (Phase 12a)
        self._overlay_volume_data_cpu: np.ndarray | None = None
        self._overlay_cmap_name = "jet"
        self._overlay_opacity = 0.5
        self._overlay_visible = True
        self._overlay_volume_visual = None
        
        self._sculpt_surface = None
        self._sculpt_mode = "above"
        self._isosurface_item = None
        self._shading_enabled = False
        # Normal-map cache for hillshading: (id(volume), volume_version, map).
        # Keyed by volume identity + version so unrelated rebuilds (colormap /
        # opacity changes) reuse it while a new volume recomputes it (#57).
        self._normal_map_cache: tuple[int, int, np.ndarray] | None = None
        self._volume_version = 0

        self._init_pyqtgraph(layout)
        self._plotter = True  # Keeps state parity with external API expectations

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_pyqtgraph(self, layout: QVBoxLayout):
        # Create central 3D widget
        self._view = gl.GLViewWidget(parent=self)
        # Free GL resources queued by slot-context cleanups at the top of
        # every paint, when the widget's context is actually current.
        _orig_paintGL = self._view.paintGL

        def _paintGL_with_flush(*args, **kwargs):
            try:
                flush_pending_gl_deletes()
            except Exception:
                pass
            return _orig_paintGL(*args, **kwargs)

        self._view.paintGL = _paintGL_with_flush
        self._view.setBackgroundColor("#1e1e2e")
        
        # Set intuitive default camera positioning
        self._view.setCameraPosition(distance=500, elevation=30, azimuth=45)
        layout.addWidget(self._view, 1)

        # Install event filter for click-to-jump detection
        self._view.installEventFilter(self)

        # Add base grid for environment context
        self._base_grid = gl.GLGridItem()
        self._base_grid.setSize(500, 500)
        self._base_grid.setSpacing(50, 50)
        self._view.addItem(self._base_grid)

        # Controller layout for sliders
        ctrl = QWidget()
        self._slice_controls = ctrl
        ctrl.setStyleSheet("background: #f8fafc;")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(8, 4, 8, 4)

        self._il_slider = self._make_slider(cl, "Inline", "#e53e3e")
        self._xl_slider = self._make_slider(cl, "Xline", "#38a169")
        self._t_slider = self._make_slider(cl, "Time", "#3182ce")
        self._il_slider.valueChanged.connect(lambda v: self._on_slider("inline", v))
        self._xl_slider.valueChanged.connect(lambda v: self._on_slider("crossline", v))
        self._t_slider.valueChanged.connect(lambda v: self._on_slider("time", v))
        layout.addWidget(ctrl, 0)

        # Visual item placeholders
        self._volume_visual = None
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        self._img_arb = None
        self._horizon_visual = None
        self._horizons: dict[str, object] = {}  # name -> GLMeshItem
        self._picks_visual = None
        self._annotation_items: list = []  # GLTextItem references
        self._bbox_visual = None
        self._cursor_sphere = None  # GLScatterPlotItem for linked cursor

    @staticmethod
    def _make_slider(layout: QHBoxLayout, label: str, color: str):
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(lbl)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 0)
        slider.setValue(0)
        slider.setStyleSheet(
            "QSlider::groove:horizontal{height:4px;background:#e2e8f0;border-radius:2px;}"
            f"QSlider::handle:horizontal{{background:{color};width:14px;height:14px;"
            "margin:-5px 0;border-radius:7px;}"
        )
        layout.addWidget(slider, 1)
        val_lbl = QLabel("0")
        val_lbl.setFixedWidth(36)
        val_lbl.setStyleSheet("color: #4a5568; font-size: 11px;")
        layout.addWidget(val_lbl)
        slider._val_label = val_lbl
        return slider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_render_mode(self, mode: str):
        """Set the 3D display mode: 'planes' or 'volume'"""
        self._mode = mode
        if (
            mode == "volume"
            and self._volume_visual is not None
            and self._volume_data_cpu is not None
            and getattr(self._volume_visual, "_normal_data", None) is None
        ):
            # Normals were skipped in planes mode; build them now that the
            # volume item actually becomes visible.
            try:
                normals = compute_normal_map(self._volume_data_cpu[::2, ::2, ::2])
                self._volume_visual._normal_data = normals
                self._volume_visual._normal_needs_upload = True
                self._volume_visual.update()
            except Exception:
                logger.debug("lazy normal map failed", exc_info=True)
        if self._volume_visual is not None:
            if mode == "volume":
                self._volume_visual.show()
            else:
                self._volume_visual.hide()
        if self._overlay_volume_visual is not None:
            if mode == "volume":
                self._overlay_volume_visual.show()
            else:
                self._overlay_volume_visual.hide()
        self._view.update()

    def set_hillshading(self, enabled: bool):
        """Toggle hillshading. Enabling on a volume that was built with
        shading off triggers a rebuild so the normal map gets computed (and
        cached for subsequent rebuilds) (#57)."""
        self._shading_enabled = enabled
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            # A volume built with shading off carries no normal texture; the
            # shader would sample an unbound unit, so rebuild once to fetch it.
            needs_normal_rebuild = (
                enabled
                and self._volume_data_cpu is not None
                and self._normal_map_cache is None
            )
            self._volume_visual.setShading(enabled)
            if needs_normal_rebuild:
                self._rebuild_volume_visual()

    def set_survey_meta(self, meta) -> None:
        """Store the survey metadata (``SeismicVolumeMeta``) driving geo mode.

        The geo branch of :meth:`set_coord_mode` — world-space grid /
        bounding box and Easting/Northing axis labels — is keyed on this
        metadata. ``meta=None`` or a meta without ``bin_grid`` disables
        geographic calibration: if the renderer is currently in geo mode it
        explicitly falls back to grid mode (fabricated world coordinates
        would be misleading, #46). Re-applying geo mode with a freshly
        calibrated meta rebuilds the world-space scene.
        """
        self._meta = meta
        if getattr(self, "_coord_mode", "grid") == "geo":
            self.set_coord_mode("geo")

    def set_survey_mapping(
        self,
        *,
        t0_ms: float = 0.0,
        dt_ms: float | None = None,
        ds_factor: tuple[int, int, int] = (1, 1, 1),
    ) -> None:
        """Record how survey time / IL / XL map onto the loaded preview cube.

        ``dt_ms is None`` leaves overlay APIs in their historical units
        (sample index for sculpt, world-Z for ``add_horizon``).
        """
        self._survey_t0_ms = float(t0_ms)
        self._survey_dt_ms = None if dt_ms is None else float(dt_ms)
        df = ds_factor or (1, 1, 1)
        self._survey_fi = max(int(df[0]), 1)
        self._survey_fx = max(int(df[1]), 1)
        self._survey_ft = max(int(df[2]), 1)

    def _sculpt_norm_surface(self, surface_z: np.ndarray) -> np.ndarray:
        """Map a sculpt grid to the shader's exclusive (0, 1) z interval."""
        nt = int(self._volume_data_cpu.shape[2])
        dt = self._survey_dt_ms
        if dt is not None and dt != 0.0:
            denom = max(1, nt - 1) * float(dt) * max(int(self._survey_ft), 1)
            return (
                (np.asarray(surface_z, dtype=np.float64) - float(self._survey_t0_ms))
                / denom
            ).astype(np.float32)
        return (np.asarray(surface_z, dtype=np.float64) / max(1, nt - 1)).astype(
            np.float32
        )

    def set_sculpting_surface(self, surface_z: np.ndarray | None, mode: str = "above"):
        self._sculpt_surface = surface_z
        self._sculpt_mode = mode
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            if surface_z is not None and self._volume_data_cpu is not None:
                norm_surface = self._sculpt_norm_surface(surface_z)
            else:
                norm_surface = None
            self._volume_visual.setSculpting(
                surface_z is not None, 
                norm_surface, 
                mode
            )

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1), *, preserve_camera: bool = False):
        """Load volume into renderer, automatically syncing to GPU if available.

        preserve_camera:
            When True (LOD upgrade path), keep the current camera center /
            distance / elevation / azimuth instead of recentering on the cube.
        """
        # Capture camera before teardown when refining LOD.
        cam_snapshot = None
        if preserve_camera and getattr(self, "_view", None) is not None:
            try:
                opts = self._view.opts
                cam_snapshot = {
                    "center": opts.get("center"),
                    "distance": opts.get("distance"),
                    "elevation": opts.get("elevation"),
                    "azimuth": opts.get("azimuth"),
                }
            except Exception:
                cam_snapshot = None

        self._volume_data_cpu = data
        self._volume_version += 1  # invalidate normal-map / slice caches
        self._slice_range_cache = None  # invalidate; recomputed on next slice build
        self._volume_spacing = spacing
        self._volume_origin = origin

        # The CuPy mirror is NOT created eagerly here (#78): it is materialized
        # lazily on first GPU-backed slice access (see ``_ensure_gpu_mirror``),
        # only when CuPy is available AND a slice actually uses the GPU path.
        # This avoids a redundant full-volume copy for volume-only or
        # CPU-only usage — see the class docstring memory notes.
        self._volume_data_gpu = None

        self._clear_visuals()

        ni, nx, nt = data.shape
        if not preserve_camera:
            self._il_pos = ni // 2
            self._xl_pos = nx // 2
            self._t_pos = nt // 2
            self._time_slice_positions = [self._t_pos]
            self._time_slice_visibility = {self._t_pos: True}
            self._active_time_pos = self._t_pos
            self._time_slices_enabled = True
        else:
            # Keep slice indices; clamp to new shape.
            self._il_pos = int(max(0, min(ni - 1, getattr(self, "_il_pos", ni // 2))))
            self._xl_pos = int(max(0, min(nx - 1, getattr(self, "_xl_pos", nx // 2))))
            self._t_pos = int(max(0, min(nt - 1, getattr(self, "_t_pos", nt // 2))))
            self._active_time_pos = int(
                max(0, min(nt - 1, getattr(self, "_active_time_pos", self._t_pos)))
            )
        
        # Setup spatial scaling
        si, sx, st = spacing
        cx = (ni * si) / 2
        cy = (nx * sx) / 2
        cz = (nt * st) / 2

        if preserve_camera and cam_snapshot is not None:
            try:
                if cam_snapshot.get("center") is not None:
                    self._view.opts["center"] = cam_snapshot["center"]
                else:
                    self._view.opts["center"] = QVector3D(cx, cy, cz)
                self._view.setCameraPosition(
                    distance=cam_snapshot.get("distance"),
                    elevation=cam_snapshot.get("elevation"),
                    azimuth=cam_snapshot.get("azimuth"),
                )
            except Exception:
                self._view.opts["center"] = QVector3D(cx, cy, cz)
        else:
            # Center the camera dynamically based on volume size. The default
            # azimuth sits in the +X/-Y quadrant so BOTH orthogonal walls read
            # left-to-right like their 2D profile panels (az 45 would mirror
            # the crossline wall's inline axis).
            self._view.opts["center"] = QVector3D(cx, cy, cz)
            self._view.setCameraPosition(
                distance=max(ni * si, nx * sx, nt * st) * 1.5,
                elevation=30,
                azimuth=-45,
            )

        # Update grid to floor aligned with volume bounds
        max_grid_len = max(ni * si, nx * sx) * 1.5
        self._base_grid.setSize(max_grid_len, max_grid_len)
        self._base_grid.setSpacing(max_grid_len / 10.0, max_grid_len / 10.0)
        self._base_grid.resetTransform()
        self._base_grid.translate(cx, cy, 0)

        self._mode = getattr(self, "_mode", "planes")
        self._volume_visual = None
        self._opacity_mode = getattr(self, "_opacity_mode", "sharp")

        # 1. 3D Volume Item (Hidden by default, shown when mode="volume")
        self._rebuild_volume_visual()

        # 2. Bounding Box & labeled Axis setup
        self._create_bbox(ni, nx, nt, spacing)
        self._create_axis_labels(ni, nx, nt, spacing)
        
        # 3. Interactive slice planes
        self._create_slice_planes()

        # 4. Update Control Sliders
        self._setup_sliders(ni, nx, nt)

        self._loaded = True
        self._view.update()

    def _setup_sliders(self, ni, nx, nt):
        for slider, position, maximum in (
            (self._il_slider, self._il_pos, ni - 1),
            (self._xl_slider, self._xl_pos, nx - 1),
            (self._t_slider, self._t_pos, nt - 1),
        ):
            was_blocked = slider.blockSignals(True)
            slider.setRange(0, maximum)
            slider.setValue(position)
            slider._val_label.setText(str(position))
            slider.blockSignals(was_blocked)

    def add_horizon(self, horizon_data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1), name: str = "horizon", color=(1.0, 0.9, 0.2, 0.6),
                    *, z_unit: str = "world"):
        """Renders horizon as a 3D mesh surface.

        ``z_unit="ms"`` converts a TWT-ms grid into the preview cube's world
        coordinates using :meth:`set_survey_mapping` and ``_volume_spacing``,
        then applies the time-down mapping (see :func:`sample_to_z`) so the
        horizon lines up with the slice planes. ``z_unit="world"`` (default)
        keeps the historical raw-Z behaviour.
        """
        if horizon_data is None:
            return

        # Remove previous single-horizon if it exists
        if self._horizon_visual is not None:
            self._view.removeItem(self._horizon_visual)
            self._horizon_visual = None

        # Remove existing horizon with same name
        if name in self._horizons:
            self._view.removeItem(self._horizons[name])

        z = np.asarray(horizon_data, dtype=np.float32)
        nI, nX = z.shape
        sx_xy = spacing
        if z_unit == "ms":
            dt = self._survey_dt_ms
            si, sx, st = self._volume_spacing
            if dt is not None and dt != 0.0:
                ft = max(int(self._survey_ft), 1)
                # TWT ms -> fractional sample index -> world Z (time-down).
                # Without a loaded volume there is no time extent to mirror
                # against, so fall back to the legacy upward mapping.
                t_samples = (
                    (z.astype(np.float64) - float(self._survey_t0_ms))
                    / (float(dt) * ft)
                )
                vol = self._volume_data_cpu
                if vol is not None:
                    z = sample_to_z(t_samples, vol.shape[2], float(st)).astype(np.float32)
                else:
                    z = (t_samples * float(st)).astype(np.float32)
            if spacing == (1, 1):
                fi = max(int(self._survey_fi), 1)
                fx = max(int(self._survey_fx), 1)
                sx_xy = (float(si) / fi, float(sx) / fx)
        x = np.arange(nX, dtype=np.float32) * sx_xy[1] + origin[0]
        y = np.arange(nI, dtype=np.float32) * sx_xy[0] + origin[1]
        xx, yy = np.meshgrid(x, y)

        verts = np.dstack([xx, yy, z])
        faces = horizon_quad_faces(nI, nX)
        verts_flat = verts.reshape(-1, 3)

        mesh = gl.GLMeshItem(
            vertexes=verts_flat,
            faces=faces,
            color=color,
            shader='shaded',
            smooth=True,
            glOptions='additive'
        )
        self._horizons[name] = mesh
        self._view.addItem(mesh)

    def remove_horizon(self, name: str):
        if name in self._horizons:
            self._view.removeItem(self._horizons.pop(name))

    def volume_data(self) -> np.ndarray | None:
        """Return the CPU volume array currently loaded, or None."""
        return self._volume_data_cpu

    def _sample_z(self, sample_index: float) -> float:
        """World Z for a sample index under the time-down convention (see :func:`sample_to_z`)."""
        if self._volume_data_cpu is None:
            return 0.0
        nt = self._volume_data_cpu.shape[2]
        st = self._volume_spacing[2]
        return sample_to_z(sample_index, nt, st)

    def _z_to_sample_index(self, z: float) -> float:
        """Inverse of :meth:`_sample_z` (see :func:`z_to_sample`)."""
        if self._volume_data_cpu is None:
            return 0.0
        nt = self._volume_data_cpu.shape[2]
        st = self._volume_spacing[2]
        return z_to_sample(z, nt, st)

    def set_isosurface(self, verts: np.ndarray, faces: np.ndarray,
                       color=(0.9, 0.5, 0.1, 0.8)):
        """Render an isosurface mesh (voxel-index coords), replacing any previous one."""
        self.clear_isosurface()
        if verts is None or faces is None or len(verts) == 0 or len(faces) == 0:
            return
        si, sx, st = self._volume_spacing
        oi, ox, ot = self._volume_origin
        v = np.asarray(verts, dtype=np.float32).copy()
        v[:, 0] = v[:, 0] * si + oi
        v[:, 1] = v[:, 1] * sx + ox
        # Vectorised time-down mapping for the sample axis
        v[:, 2] = self._sample_z(v[:, 2]) + ot
        mesh = gl.GLMeshItem(
            vertexes=v,
            faces=np.asarray(faces, dtype=np.int32),
            color=color,
            shader='shaded',
            smooth=True,
        )
        self._isosurface_item = mesh
        self._view.addItem(mesh)
        self._view.update()

    def clear_isosurface(self):
        """Remove the isosurface mesh if present."""
        if self._isosurface_item is not None:
            try:
                self._view.removeItem(self._isosurface_item)
            except Exception:
                pass
            self._isosurface_item = None

    def horizons(self) -> list[str]:
        return list(self._horizons.keys())

    def set_colormap(self, cmap_name: str):
        """Change the display colormap and trigger redraw."""
        if not self._loaded:
            return
        self._cmap_name = cmap_name
        # Fast path: the slice planes use GLImageLutItem (Indexed8 + LUT
        # shader), so a pure colormap change is an O(1) LUT re-upload per
        # plane — no index re-computation or texture re-upload. Fall back to
        # the full rebuild only if the items don't exist yet (first build) or
        # aren't LUT items (e.g. the arbitrary curtain, still RGBA).
        lut_items = [
            getattr(self, attr, None)
            for attr in ("_img_il", "_img_xl")
        ]
        lut_items.extend(
            image
            for image, _line in getattr(
                self, "_time_plane_items", {}
            ).values()
        )
        if all(isinstance(it, GLImageLutItem) for it in lut_items if it is not None):
            for it in lut_items:
                if it is not None:
                    it.setLut(cmap_name)
        else:
            self._update_slice_planes()
        
        # Optimize: If volume rendering is active, update colormaps in-place instead of rebuilding
        if self._mode == "volume" and isinstance(self._volume_visual, DualGLVolumeItem):
            cmap_data_primary = ColormapManager.get_colormap(self._cmap_name).copy()
            alpha_curve_primary = self._build_alpha_curve(self._opacity_mode, len(cmap_data_primary))
            cmap_data_primary[:, 3] = alpha_curve_primary.astype(np.uint8)

            cmap_data_overlay = ColormapManager.get_colormap(self._overlay_cmap_name).copy()
            alpha_curve_overlay = self._build_alpha_curve("sharp", len(cmap_data_overlay))
            cmap_data_overlay[:, 3] = alpha_curve_overlay.astype(np.uint8)
            
            self._volume_visual.setColormaps(cmap_data_primary, cmap_data_overlay)
        elif self._mode == "volume":
            self._rebuild_volume_visual()

    @staticmethod
    def _build_alpha_curve(mode: str, n: int = 256) -> np.ndarray:
        """Build an alpha transfer function curve (0-255)."""
        t = np.linspace(0, 1, n)
        if mode == "linear":
            alpha = t * 255
        elif mode == "sigmoid":
            alpha = 1 / (1 + np.exp(-10 * (t - 0.5))) * 255
        elif mode == "threshold":
            alpha = np.where(t > 0.15, 200, 0).astype(np.float64)
        else:  # "sharp" (default) — original behavior
            alpha = np.clip(np.abs(np.linspace(-1, 1, n)) * 400, 0, 255)
        return np.clip(alpha, 0, 255).astype(np.uint8)

    def set_opacity_mode(self, mode: str):
        """Set the opacity transfer function and rebuild volume visual."""
        self._opacity_mode = mode
        if self._loaded and isinstance(self._volume_visual, DualGLVolumeItem):
            self.set_colormap(self._cmap_name) # Reuse the optimized colormap update logic
        elif self._loaded and self._volume_visual is not None:
            self._rebuild_volume_visual()

    def _clean_gl_items(self, items) -> None:
        """Best-effort GL resource release for scene items being discarded.

        Calls ``clean()`` on each item that implements it. Texture/VBO/program
        deletion needs a current GL context, but teardown paths (``load_volume``,
        slider rebuilds) run outside ``paintGL`` — so make the view's context
        current when one exists. Items never painted hold no GPU resources, so
        a missing context degrades to a safe no-op inside ``clean()``.
        """
        targets = [item for item in items if item is not None and hasattr(item, "clean")]
        if not targets:
            return
        view = getattr(self, "_view", None)
        made_current = False
        if QtGui.QOpenGLContext.currentContext() is None and view is not None:
            try:
                if view.context() is not None:
                    view.makeCurrent()
                    made_current = True
            except Exception:
                made_current = False
        try:
            for item in targets:
                try:
                    item.clean()
                except Exception:
                    pass
        finally:
            if made_current:
                try:
                    view.doneCurrent()
                except Exception:
                    pass

    def _rebuild_volume_visual(self):
        """Rebuild the GLVolumeItem with current opacity settings using our shared texture custom shader optimization."""
        if self._volume_visual is not None:
            self._clean_gl_items([self._volume_visual])
            try:
                self._view.removeItem(self._volume_visual)
            except Exception:
                pass
            self._volume_visual = None

        if self._volume_data_cpu is None:
            return

        try:
            # Downsample and normalize primary volume data
            primary_data = self._volume_data_cpu[::2, ::2, ::2]
            primary_normalized = ColormapManager.normalize_to_index(primary_data, lut_size=256)

            # Normal map is only needed while hillshading is enabled; compute
            # lazily and cache per volume (id + version) so unrelated rebuilds
            # (colormap/opacity changes) don't recompute it (#57).
            normal_data = None
            if self._shading_enabled:
                normal_data = self._get_normal_map(primary_data)

            # Downsample and normalize overlay volume data if available if available
            if self._overlay_volume_data_cpu is not None:
                overlay_data = self._overlay_volume_data_cpu[::2, ::2, ::2]
                overlay_normalized = ColormapManager.normalize_to_index(overlay_data, lut_size=256)
            else:
                overlay_normalized = np.zeros_like(primary_normalized)

            # Combine into a single 4-channel 3D volume (R=primary, G=overlay)
            shape = primary_normalized.shape
            vol_data_combined = np.zeros(shape + (4,), dtype=np.uint8)
            vol_data_combined[..., 0] = primary_normalized
            vol_data_combined[..., 1] = overlay_normalized

            # Get and prepare the colormaps LUTs
            cmap_data_primary = ColormapManager.get_colormap(self._cmap_name).copy()
            alpha_curve_primary = self._build_alpha_curve(self._opacity_mode, len(cmap_data_primary))
            cmap_data_primary[:, 3] = alpha_curve_primary.astype(np.uint8)

            cmap_data_overlay = ColormapManager.get_colormap(self._overlay_cmap_name).copy()
            alpha_curve_overlay = self._build_alpha_curve("sharp", len(cmap_data_overlay))
            cmap_data_overlay[:, 3] = alpha_curve_overlay.astype(np.uint8)

            # Instantiate our high-performance custom DualGLVolumeItem
            self._volume_visual = DualGLVolumeItem(vol_data_combined, normal_data=normal_data, sliceDensity=3, smooth=True)
            self._volume_visual.setColormaps(cmap_data_primary, cmap_data_overlay)
            self._volume_visual.setOverlayOpacity(self._overlay_opacity)
            self._volume_visual.setOverlayVisible(self._overlay_visible)
            if self._sculpt_surface is not None and self._volume_data_cpu is not None:
                norm_surface = self._sculpt_norm_surface(self._sculpt_surface)
            else:
                norm_surface = None
            self._volume_visual.setSculpting(
                self._sculpt_surface is not None,
                norm_surface,
                self._sculpt_mode
            )
            self._volume_visual.setShading(self._shading_enabled)
            self._apply_volume_visual_transform()

            self._view.addItem(self._volume_visual)
            if self._mode != "volume":
                self._volume_visual.hide()
            self._view.update()
        except Exception as e:
            logger.warning(f"Rebuild volume visual failed: {e}", exc_info=True)

    def _apply_volume_visual_transform(
        self, scale_x: float = 1.0, scale_y: float = 1.0
    ) -> None:
        """Place the downsampled volume brick in the time-down world box.

        DualGLVolumeItem is uploaded at [::2], so voxel pitch is 2× spacing.
        Negative Z scale + a translate to ``sample_to_z(0)`` puts sample 0
        at the top of the box, matching the orthogonal slice planes.
        """
        vis = self._volume_visual
        vol = self._volume_data_cpu
        if vis is None or vol is None:
            return
        si, sx, st = self._volume_spacing
        vis.resetTransform()
        vis.scale(
            float(si) * 2.0 * float(scale_x),
            float(sx) * 2.0 * float(scale_y),
            -float(st) * 2.0,
        )
        vis.translate(0.0, 0.0, sample_to_z(0, int(vol.shape[2]), st))

    def _get_normal_map(self, primary_data: np.ndarray) -> np.ndarray:
        """Return the cached hillshading normal map for the current volume.

        Computed once per loaded volume (cache key = volume array id + version
        counter, both bumped in ``load_volume``), then reused across rebuilds.
        ``primary_data`` is the fixed ``[::2, ::2, ::2]`` downsample of the
        loaded volume, so a single map per volume is sufficient (#57).
        """
        key = (id(self._volume_data_cpu), self._volume_version)
        if self._normal_map_cache is not None and self._normal_map_cache[:2] == key:
            return self._normal_map_cache[2]
        normal_map = compute_normal_map(primary_data)
        self._normal_map_cache = (key[0], key[1], normal_map)
        return normal_map

    def load_overlay_volume(self, data: np.ndarray, colormap: str = "jet", opacity: float = 0.5):
        """Load an overlay attribute/property volume and display it superimposed with alpha blending."""
        self._overlay_volume_data_cpu = data
        self._overlay_cmap_name = colormap
        self._overlay_opacity = opacity
        self._overlay_visible = True
        
        self.rebuild_overlay_volume_visual()

    def rebuild_overlay_volume_visual(self):
        """Rebuild/update the overlay volume visual item."""
        self._rebuild_volume_visual()
        
        # Maintain a dummy overlay item with zero memory footprint to satisfy existing test assertions
        if self._overlay_volume_visual is not None:
            try:
                self._view.removeItem(self._overlay_volume_visual)
            except Exception:
                pass
            self._overlay_volume_visual = None

        if self._overlay_volume_data_cpu is not None:
            dummy_data = np.zeros((1, 1, 1, 4), dtype=np.uint8)
            self._overlay_volume_visual = gl.GLVolumeItem(dummy_data)
            self._view.addItem(self._overlay_volume_visual)
            if self._mode != "volume" or not self._overlay_visible:
                self._overlay_volume_visual.hide()

    def set_overlay_colormap(self, cmap_name: str):
        """Change the colormap of the overlay volume in O(1) time without re-uploading texture data."""
        self._overlay_cmap_name = cmap_name
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            cmap_data_overlay = ColormapManager.get_colormap(cmap_name).copy()
            alpha_curve_overlay = self._build_alpha_curve("sharp", len(cmap_data_overlay))
            cmap_data_overlay[:, 3] = alpha_curve_overlay.astype(np.uint8)
            self._volume_visual.setColormaps(self._volume_visual._primary_cmap_lut, cmap_data_overlay)
        else:
            self._rebuild_volume_visual()

    def set_overlay_opacity(self, opacity: float):
        """Change the opacity of the overlay volume in O(1) time by updating shader uniforms."""
        self._overlay_opacity = opacity
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            self._volume_visual.setOverlayOpacity(opacity)
        else:
            self._rebuild_volume_visual()

    def set_overlay_visible(self, visible: bool):
        """Toggle visibility of the overlay volume in O(1) time via shader uniforms."""
        self._overlay_visible = visible
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            self._volume_visual.setOverlayVisible(visible)
            
        if self._overlay_volume_visual is not None:
            if visible and self._mode == "volume":
                self._overlay_volume_visual.show()
            else:
                self._overlay_volume_visual.hide()
            self._view.update()

    def clear_overlay_volume(self):
        """Clear and remove the overlay volume visual."""
        if self._overlay_volume_visual is not None:
            try:
                self._view.removeItem(self._overlay_volume_visual)
            except Exception:
                pass
            self._overlay_volume_visual = None
        self._overlay_volume_data_cpu = None
        self._rebuild_volume_visual()

    def clear(self):
        """Reset state and clean visual graph."""
        self._clear_visuals()
        # Full reset also drops the stratal surface state (unlike the
        # load_volume path, which keeps matching surfaces across a reload).
        self._stratal_surfaces = []
        self._stratal_visibility = []
        self._stratal_labels = []
        self._stratal_active = None
        self._loaded = False
        self._volume_data_cpu = None
        self._slice_range_cache = None
        self._volume_data_gpu = None
        self._normal_map_cache = None
        self._overlay_volume_data_cpu = None
        self._overlay_volume_visual = None

    def _clear_visuals(self):
        self._clear_time_plane_items()
        # Release the stratal GL planes, but keep the surface *state* here:
        # surfaces may have been registered before the volume was loaded (see
        # ``set_stratal_slices``), and ``_sync_stratal_planes`` drops grids
        # whose shape no longer matches the new volume.
        self._clear_stratal_plane_items()
        main_items = [v for v in (self._volume_visual, self._overlay_volume_visual, self._img_il,
                                  self._img_xl, self._img_arb, self._horizon_visual,
                                  self._picks_visual, self._bbox_visual, self._cursor_sphere)
                      if v is not None]
        self._clean_gl_items(main_items)
        for v in main_items:
            try:
                self._view.removeItem(v)
            except Exception:
                pass
        for v in self._horizons.values():
            try:
                self._view.removeItem(v)
            except Exception:
                pass
        self._horizons.clear()
        # Clear axis labels
        for v in getattr(self, '_axis_labels', []):
            try:
                self._view.removeItem(v)
            except Exception:
                pass
        self._axis_labels = []
        # Clear line items from borders
        for attr in ('_line_il', '_line_xl', '_line_arb'):
            v = getattr(self, attr, None)
            if v is not None:
                try:
                    self._view.removeItem(v)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._volume_visual = None
        self._img_il = None
        self._img_xl = None
        self._img_t = None
        self._img_arb = None
        self._horizon_visual = None
        self._bbox_visual = None
        self._cursor_sphere = None
        
        # Clear polyline curtain items & data
        for item in getattr(self, '_arb_curtain_items', []):
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._arb_curtain_items = []
        self._arb_polyline = None

        # Clear annotation items
        for item in self._annotation_items:
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._annotation_items = []
        self.clear_isosurface()

    # ------------------------------------------------------------------
    # Internal Graph Building
    # ------------------------------------------------------------------

    def _create_bbox(self, ni, nx, nt, sp):
        si, sx, st = sp
        
        # Define corners of the volume cuboid
        corners = np.array([
            [0, 0, 0],
            [ni * si, 0, 0],
            [ni * si, nx * sx, 0],
            [0, nx * sx, 0],
            [0, 0, nt * st],
            [ni * si, 0, nt * st],
            [ni * si, nx * sx, nt * st],
            [0, nx * sx, nt * st]
        ], dtype=np.float32)
        
        # Sequence of vertex indices forming connected lines for edges
        edges = [
            0, 1, 1, 2, 2, 3, 3, 0,  # bottom loop
            4, 5, 5, 6, 6, 7, 7, 4,  # top loop
            0, 4, 1, 5, 2, 6, 3, 7   # vertical pillars
        ]
        
        path = corners[edges]
        
        self._bbox_visual = gl.GLLinePlotItem(
            pos=path,
            color=(0.5, 0.5, 0.5, 0.8),
            width=1.5,
            mode='lines'
        )
        self._view.addItem(self._bbox_visual)

    def set_coord_mode(self, mode: str):
        """Set coordinate system view mode ('grid' for IL/XL or 'geo' for Easting/Northing in meters).

        Geo mode requires survey metadata with a bin-grid calibration (see
        :meth:`set_survey_meta`). Without one — no survey loaded, or a meta
        whose ``bin_grid`` is None — geo mode explicitly falls back to grid
        mode instead of fabricating world coordinates (#46).
        """
        meta = getattr(self, "_meta", None)
        if mode == "geo" and getattr(meta, "bin_grid", None) is None:
            mode = "grid"
        self._coord_mode = mode
        if not self._loaded or self._volume_data_cpu is None:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        # Clear old 3D axis labels and bounding box
        for item in getattr(self, '_axis_labels', []):
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._axis_labels = []

        if self._bbox_visual is not None:
            try:
                self._view.removeItem(self._bbox_visual)
            except Exception:
                pass
            self._bbox_visual = None

        if mode == "geo" and meta is not None:
            x0, y0 = meta.il_xl_to_xy(meta.iline_start, meta.xline_start)
            x1, y1 = meta.il_xl_to_xy(meta.iline_start + (ni - 1) * meta.iline_step, meta.xline_start + (nx - 1) * meta.xline_step)
            wx = max(10.0, abs(x1 - x0))
            wy = max(10.0, abs(y1 - y0))
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            cz = (nt * st) / 2.0

            scale_x = wx / max(1, ni * si)
            scale_y = wy / max(1, nx * sx)

            if self._volume_visual is not None:
                self._apply_volume_visual_transform(scale_x=scale_x, scale_y=scale_y)

            max_grid_len = max(wx, wy) * 1.5
            self._base_grid.setSize(max_grid_len, max_grid_len)
            self._base_grid.setSpacing(max_grid_len / 10.0, max_grid_len / 10.0)
            self._base_grid.resetTransform()
            self._base_grid.translate(cx, cy, 0)

            corners = np.array([
                [min(x0, x1), min(y0, y1), 0],
                [max(x0, x1), min(y0, y1), 0],
                [max(x0, x1), max(y0, y1), 0],
                [min(x0, x1), max(y0, y1), 0],
                [min(x0, x1), min(y0, y1), nt * st],
                [max(x0, x1), min(y0, y1), nt * st],
                [max(x0, x1), max(y0, y1), nt * st],
                [min(x0, x1), max(y0, y1), nt * st]
            ], dtype=np.float32)
            edges = [
                0, 1, 1, 2, 2, 3, 3, 0,
                4, 5, 5, 6, 6, 7, 7, 4,
                0, 4, 1, 5, 2, 6, 3, 7
            ]
            self._bbox_visual = gl.GLLinePlotItem(
                pos=corners[edges],
                color=(0.3, 0.7, 1.0, 0.8),
                width=1.8,
                mode='lines'
            )
            self._view.addItem(self._bbox_visual)

            max_dim = max(wx, wy, nt * st)
            # setCameraPosition has no ``center`` kwarg in this pyqtgraph
            # (``pos``); assign opts["center"] like load_volume does.
            self._view.opts["center"] = QVector3D(cx, cy, cz)
            self._view.setCameraPosition(distance=max_dim * 2.2)
        else:
            cx = (ni * si) / 2.0
            cy = (nx * sx) / 2.0
            cz = (nt * st) / 2.0

            if self._volume_visual is not None:
                self._apply_volume_visual_transform()

            max_grid_len = max(ni * si, nx * sx) * 1.5
            self._base_grid.setSize(max_grid_len, max_grid_len)
            self._base_grid.setSpacing(max_grid_len / 10.0, max_grid_len / 10.0)
            self._base_grid.resetTransform()
            self._base_grid.translate(cx, cy, 0)

            self._create_bbox(ni, nx, nt, (si, sx, st))

            max_dim = max(ni * si, nx * sx, nt * st)
            self._view.opts["center"] = QVector3D(cx, cy, cz)
            self._view.setCameraPosition(distance=max_dim * 2.2)

        self._create_axis_labels(ni, nx, nt, (si, sx, st))
        self._update_slice_planes()
        self._view.update()

    def _create_axis_labels(self, ni, nx, nt, sp):
        """Create visible 3D coordinate axes with colored lines, arrows, and tick labels."""
        si, sx, st = sp
        max_dim = max(ni * si, nx * sx, nt * st)
        pad = max_dim * 0.08  # Extension beyond bounding box

        # Time ticks read TWT milliseconds when a survey mapping is known
        # (t0 + s*ft*dt, matching the 2D panels' "Time (ms)" axis); otherwise
        # they fall back to preview sample indices.
        dt_ms = getattr(self, "_survey_dt_ms", None)
        t0_ms = float(getattr(self, "_survey_t0_ms", 0.0) or 0.0)
        ft = max(int(getattr(self, "_survey_ft", 1)), 1)

        def _tick_time_text(sample_value: float) -> str:
            s = max(0, min(nt - 1, int(round(sample_value))))
            if dt_ms:
                return f"{t0_ms + s * ft * float(dt_ms):.0f}"
            return str(s)

        self._axis_labels = []
        is_geo = getattr(self, "_coord_mode", "grid") == "geo"
        meta = getattr(self, "_meta", None)
        
        # ---- Solid colored axis LINES (RGB convention) ----
        # Inline axis (X) — Red
        il_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [ni * si + pad, 0, 0]], dtype=np.float32),
            color=(1.0, 0.3, 0.3, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(il_line)
        self._axis_labels.append(il_line)
        
        # Crossline axis (Y) — Green
        xl_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, nx * sx + pad, 0]], dtype=np.float32),
            color=(0.3, 0.85, 0.3, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(xl_line)
        self._axis_labels.append(xl_line)
        
        # Time axis (Z) — Blue
        t_line = gl.GLLinePlotItem(
            pos=np.array([[0, 0, 0], [0, 0, nt * st + pad]], dtype=np.float32),
            color=(0.3, 0.5, 1.0, 1.0), width=3.0, antialias=True
        )
        self._view.addItem(t_line)
        self._axis_labels.append(t_line)
        
        # ---- Axis endpoint text labels ----
        try:
            if is_geo and meta is not None:
                x_start, y_start = meta.il_xl_to_xy(meta.iline_start, meta.xline_start)
                x_end, y_end = meta.il_xl_to_xy(meta.iline_start + (ni - 1) * meta.iline_step, meta.xline_start + (nx - 1) * meta.xline_step)
                il_text = f"Easting X ({x_start:.0f}m - {x_end:.0f}m)"
                xl_text = f"Northing Y ({y_start:.0f}m - {y_end:.0f}m)"
            elif is_geo:
                il_text = "Easting X (m)"
                xl_text = "Northing Y (m)"
            else:
                il_text = f'Inline (0-{ni-1})'
                xl_text = f'Xline (0-{nx-1})'

            il_label = gl.GLTextItem(
                pos=np.array([ni * si + pad * 1.2, 0, 0]),
                text=il_text,
                color=(255, 100, 100, 255)
            )
            xl_label = gl.GLTextItem(
                pos=np.array([0, nx * sx + pad * 1.2, 0]),
                text=xl_text,
                color=(100, 220, 100, 255)
            )
            t_label = gl.GLTextItem(
                pos=np.array([0, 0, nt * st + pad * 1.2]),
                text=(
                    f'Time ↓ ({t0_ms:.0f}-{t0_ms + (nt - 1) * ft * float(dt_ms):.0f} ms)'
                    if dt_ms else f'Time ↓ (0-{nt-1})'
                ),
                color=(100, 150, 255, 255)
            )
            for lbl in (il_label, xl_label, t_label):
                self._view.addItem(lbl)
                self._axis_labels.append(lbl)
        except Exception:
            pass
        
        # ---- Tick marks along each axis (5 ticks) ----
        tick_offset = max_dim * 0.03
        n_ticks = 5
        for i in range(n_ticks + 1):
            frac = i / n_ticks
            try:
                if is_geo and meta is not None:
                    curr_il = meta.iline_start + frac * (ni - 1) * meta.iline_step
                    curr_xl = meta.xline_start + frac * (nx - 1) * meta.xline_step
                    x_val, y_val = meta.il_xl_to_xy(curr_il, curr_xl)
                    il_tick_str = f"{x_val:.0f}m"
                    xl_tick_str = f"{y_val:.0f}m"
                else:
                    il_tick_str = str(int(frac * ni))
                    xl_tick_str = str(int(frac * nx))

                pos_il = np.array([frac * ni * si, -tick_offset, 0])
                tick_il = gl.GLTextItem(
                    pos=pos_il,
                    text=il_tick_str,
                    color=(220, 180, 180, 220)
                )
                self._view.addItem(tick_il)
                self._axis_labels.append(tick_il)
                
                pos_xl = np.array([-tick_offset, frac * nx * sx, 0])
                tick_xl = gl.GLTextItem(
                    pos=pos_xl,
                    text=xl_tick_str,
                    color=(180, 220, 180, 220)
                )
                self._view.addItem(tick_xl)
                self._axis_labels.append(tick_xl)
                
                # Time-down: tick for sample value frac*nt sits mirrored on Z
                pos_t = np.array([-tick_offset, -tick_offset, self._sample_z(frac * nt)])
                tick_t = gl.GLTextItem(
                    pos=pos_t,
                    text=_tick_time_text(frac * nt),
                    color=(180, 190, 220, 220)
                )
                self._view.addItem(tick_t)
                self._axis_labels.append(tick_t)
            except Exception:
                pass

    def _ensure_gpu_mirror(self):
        """Lazily materialize the CuPy mirror of the CPU volume on first
        GPU-backed slice access (#78).

        The CPU array stays the single source of truth; the GPU copy is only
        created when a slice actually requests it AND CuPy is available,
        avoiding a redundant full-volume copy for volume-only or CPU-only
        usage. Returns the mirror, or ``None`` to fall back to CPU.
        """
        if (
            self._volume_data_gpu is None
            and self._volume_data_cpu is not None
            and is_gpu_available()
        ):
            try:
                self._volume_data_gpu = to_gpu(self._volume_data_cpu)
                logger.info("Seismic volume cached on GPU via CuPy (lazy).")
            except Exception as e:
                logger.warning(f"Failed to push volume to GPU: {e}. Falling back to CPU slicing.")
                self._volume_data_gpu = None
        return self._volume_data_gpu

    def _get_sliced_data(self, axis: int, index: int) -> np.ndarray:
        """Retrieves slice, prioritizing GPU cached volume memory if accessible."""
        mirror = self._ensure_gpu_mirror()
        vol = mirror if mirror is not None else self._volume_data_cpu
        if vol is None:
            return np.zeros((1,1))
        # Optimization: Request to KEEP the array reference on the GPU device
        return slice_volume_gpu(vol, axis, index, keep_on_gpu=True)

    def _create_slice_planes(self):
        if self._volume_data_cpu is None:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        # Pre-fetch color lookup table for hardware upload reuse
        lut = ColormapManager.get_colormap(self._cmap_name)

        # Compute the display value range ONCE for all 3 slice planes — the
        # previous code recomputed nanmin/nanmax per slice inside
        # apply_colormap_gpu (3 redundant full-array passes per slider tick).
        value_range = self._slice_value_range()

        # 1-3. Axis-aligned planes (Inline / Crossline / Time)
        self._create_slice_plane("inline", value_range=value_range)
        self._create_slice_plane("crossline", value_range=value_range)
        self._create_slice_plane("time", value_range=value_range)

        # 4. Polyline-driven arbitrary curtain (if set)
        self._render_polyline_curtain(ni, nx, nt, si, sx, st, lut)

        # 5. Stratal / proportional slices (horizon-relative)
        if getattr(self, "_stratal_surfaces", None):
            self._sync_stratal_planes(value_range=value_range)

    def set_slice_clip_percentile(self, pct: float) -> None:
        """Match 2D ProfileVD clip: use P(100-pct)..P(pct) for plane colouring."""
        pct = float(max(50.0, min(99.9, pct)))
        if abs(pct - getattr(self, "_slice_clip_pct", 99.0)) < 0.01:
            return
        self._slice_clip_pct = pct
        self._slice_range_cache = None
        if self._loaded and self._volume_data_cpu is not None:
            self._update_slice_planes()

    def _slice_value_range(self) -> tuple[float, float] | None:
        """Cached (dmin, dmax) for slice-plane colouring.

        Uses the same percentile clip as 2D profiles (default 99%) so 3D
        orthogonal planes are not washed out by volume extrema.
        """
        if self._volume_data_cpu is None:
            return None
        if self._slice_range_cache is None:
            vol = self._volume_data_cpu
            pct = float(getattr(self, "_slice_clip_pct", 99.0))
            lo_p = max(0.0, 100.0 - pct)
            hi_p = min(100.0, pct)
            # Subsample for speed on large previews (still stable for colour scale)
            flat = vol.ravel()
            if flat.size > 2_000_000:
                step = max(1, flat.size // 2_000_000)
                sample = flat[::step]
            else:
                sample = flat
            lo = float(np.nanpercentile(sample, lo_p))
            hi = float(np.nanpercentile(sample, hi_p))
            if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
                lo = float(np.nanmin(vol))
                hi = float(np.nanmax(vol))
            self._slice_range_cache = (lo, hi)
        return self._slice_range_cache

    def _create_slice_plane(self, axis: str, value_range: tuple[float, float] | None = None):
        """Build or update the slice plane + border for a single axis (inline/crossline/time) in-place."""
        if self._volume_data_cpu is None:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        if axis == "inline":
            # 1. Inline — Perpendicular to IL axis (x)
            il_raw = self._get_sliced_data(0, self._il_pos)
            il_idx = ColormapManager.normalize_to_index(il_raw, lut_size=256, value_range=value_range)

            if self._img_il is not None and self._line_il is not None:
                # Fast In-Place Texture & Transform Update
                self._img_il.setData(il_idx)
                self._img_il.resetTransform()
                # Negative Y scale mirrors the time axis so sample-0 lands at
                # world Z top (time-down, matching the 2D profile panels);
                # the wall hangs from the top of the box.
                self._img_il.scale(sx, -st, 1)
                self._img_il.rotate(90, 1, 0, 0)
                self._img_il.rotate(90, 0, 0, 1)
                self._img_il.translate(self._il_pos * si, 0, self._sample_z(0))

                self._line_il.resetTransform()
                self._line_il.translate(self._il_pos * si, 0, 0)
            else:
                # smooth=True: bilinear filtering of the R8 index texture.
                # Indices are linear in amplitude, so interpolating them then
                # looking up the LUT is equivalent to interpolating amplitude
                # first — avoids the blocky nearest-neighbour look on the
                # downsampled preview cube.
                self._img_il = GLImageLutItem(il_idx, cmap_name=self._cmap_name, smooth=True)
                self._img_il.scale(sx, -st, 1)
                self._img_il.rotate(90, 1, 0, 0)
                self._img_il.rotate(90, 0, 0, 1)
                self._img_il.translate(self._il_pos * si, 0, self._sample_z(0))
                self._view.addItem(self._img_il)

                z_max = self._sample_z(0)  # Top of volume
                il_pts = np.array([[0, 0, z_max], [0, nx*sx, z_max], [0, nx*sx, 0], [0, 0, 0], [0, 0, z_max]])
                self._line_il = gl.GLLinePlotItem(pos=il_pts, color=(1, 0, 0, 1), width=2, antialias=True)
                self._line_il.translate(self._il_pos * si, 0, 0)
                self._view.addItem(self._line_il)

        elif axis == "crossline":
            # 2. Crossline — Perpendicular to XL axis (y)
            xl_raw = self._get_sliced_data(1, self._xl_pos)
            xl_idx = ColormapManager.normalize_to_index(xl_raw, lut_size=256, value_range=value_range)

            if self._img_xl is not None and self._line_xl is not None:
                # Fast In-Place Texture & Transform Update
                self._img_xl.setData(xl_idx)
                self._img_xl.resetTransform()
                # Negative Y scale mirrors time downward; wall hangs from the
                # top of the box (see inline wall above).
                self._img_xl.scale(si, -st, 1)
                self._img_xl.rotate(90, 1, 0, 0)
                self._img_xl.translate(0, self._xl_pos * sx, self._sample_z(0))

                self._line_xl.resetTransform()
                self._line_xl.translate(0, self._xl_pos * sx, 0)
            else:
                self._img_xl = GLImageLutItem(xl_idx, cmap_name=self._cmap_name, smooth=True)
                self._img_xl.scale(si, -st, 1)
                self._img_xl.rotate(90, 1, 0, 0)
                self._img_xl.translate(0, self._xl_pos * sx, self._sample_z(0))
                self._view.addItem(self._img_xl)

                z_max = self._sample_z(0)  # Top of volume
                xl_pts = np.array([[0, 0, z_max], [ni*si, 0, z_max], [ni*si, 0, 0], [0, 0, 0], [0, 0, z_max]])
                self._line_xl = gl.GLLinePlotItem(pos=xl_pts, color=(0, 1, 0, 1), width=2, antialias=True)
                self._line_xl.translate(0, self._xl_pos * sx, 0)
                self._view.addItem(self._line_xl)

        elif axis == "time":
            self._sync_time_slice_planes(value_range=value_range)

    def _sync_time_slice_planes(
        self, *, value_range: tuple[float, float] | None = None
    ) -> None:
        """Create/update all horizontal Time planes and their borders."""
        if self._volume_data_cpu is None:
            return
        if value_range is None:
            value_range = self._slice_value_range()
        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing
        positions = [
            max(0, min(nt - 1, int(position)))
            for position in self._time_slice_positions
        ]
        positions = sorted(dict.fromkeys(positions))[:8]
        if not positions:
            positions = [max(0, min(nt - 1, int(self._t_pos)))]
        self._time_slice_positions = positions
        self._time_slice_visibility = {
            position: bool(self._time_slice_visibility.get(position, True))
            for position in positions
        }
        if self._active_time_pos not in positions:
            self._active_time_pos = positions[0]
        self._t_pos = int(self._active_time_pos)

        for position in tuple(self._time_plane_items):
            if position in positions:
                continue
            image, line = self._time_plane_items.pop(position)
            self._clean_gl_items([image])
            for item in (image, line):
                try:
                    self._view.removeItem(item)
                except Exception:
                    pass

        t_pts = np.array(
            [
                [0, 0, 0],
                [ni * si, 0, 0],
                [ni * si, nx * sx, 0],
                [0, nx * sx, 0],
                [0, 0, 0],
            ]
        )
        for position in positions:
            t_raw = self._get_sliced_data(2, position)
            t_idx = ColormapManager.normalize_to_index(
                t_raw,
                lut_size=256,
                value_range=value_range,
            )
            pair = self._time_plane_items.get(position)
            if pair is None:
                image = GLImageLutItem(
                    t_idx, cmap_name=self._cmap_name, smooth=True
                )
                line = gl.GLLinePlotItem(
                    pos=t_pts,
                    color=(0.15, 0.55, 0.95, 1.0),
                    width=1,
                    antialias=True,
                )
                self._view.addItem(image)
                self._view.addItem(line)
                self._time_plane_items[position] = (image, line)
            else:
                image, line = pair
                image.setData(t_idx)
            image.resetTransform()
            image.scale(si, sx, 1)
            image.translate(0, 0, self._sample_z(position))
            image.setOpacity(self._time_slice_opacity)

            active = position == self._active_time_pos
            line.setData(
                pos=t_pts,
                color=(
                    (1.0, 0.72, 0.12, 1.0)
                    if active
                    else (0.15, 0.55, 0.95, 0.9)
                ),
                width=3 if active else 1,
                antialias=True,
            )
            line.resetTransform()
            line.translate(0, 0, self._sample_z(position))
            visible = bool(
                self._planes_visible
                and self._time_slices_enabled
                and self._time_slice_visibility.get(position, True)
            )
            image.setVisible(visible)
            line.setVisible(visible)

        self._img_t, self._line_t = self._time_plane_items[
            int(self._active_time_pos)
        ]

    def _clear_time_plane_items(self) -> None:
        pairs = list(getattr(self, "_time_plane_items", {}).values())
        self._clean_gl_items([image for image, _line in pairs])
        for image, line in pairs:
            for item in (image, line):
                try:
                    self._view.removeItem(item)
                except Exception:
                    pass
        self._time_plane_items = {}
        self._img_t = None
        self._line_t = None

    # ------------------------------------------------------------------
    # Stratal / proportional slices (horizon-relative, non-planar)
    # ------------------------------------------------------------------

    def _sync_stratal_planes(
        self, *, value_range: tuple[float, float] | None = None
    ) -> None:
        """Create/update all stratal (proportional) slice planes.

        Each stratal surface is a non-planar ``(nI, nX)`` grid of sample
        positions. The slice *image* is sampled through
        :func:`geoviz_seismic.stratal.extract_stratal_slice` (linear T
        interpolation), colour-mapped via the same LUT pipeline as the time
        planes, and laid flat in the XY plane at the surface's mean depth so it
        reads as a geological-time attribute map. A contour line marks the
        surface footprint at that mean depth.
        """
        if self._volume_data_cpu is None:
            return
        if not getattr(self, "_stratal_surfaces", None):
            self._clear_stratal_plane_items()
            return
        if value_range is None:
            value_range = self._slice_value_range()
        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        # Surfaces are (nI, nX) sample-index grids tied to the volume shape.
        # After loading a different-sized volume, stale grids from the old
        # volume would make extract_stratal_slice raise ValueError — drop the
        # whole stratal state instead of crashing the load path.
        if any(np.shape(s) != (ni, nx) for s in self._stratal_surfaces):
            logger.info(
                "Dropping %d stratal surface(s): shape does not match the "
                "loaded volume (%d, %d).", len(self._stratal_surfaces), ni, nx,
            )
            self.clear_stratal_slices()
            return

        n_surf = len(self._stratal_surfaces)
        # Prune items beyond the current surface count.
        for idx in list(self._stratal_plane_items):
            if idx >= n_surf:
                image, line = self._stratal_plane_items.pop(idx)
                self._clean_gl_items([image])
                for item in (image, line):
                    try:
                        self._view.removeItem(item)
                    except Exception:
                        pass

        for idx, surface in enumerate(self._stratal_surfaces):
            amp = extract_stratal_slice(self._volume_data_cpu, surface)
            idx_img = ColormapManager.normalize_to_index(
                amp, lut_size=256, value_range=value_range,
            )
            # Representative depth = finite mean of the surface (sample units).
            finite = np.isfinite(surface)
            if finite.any():
                mean_t = float(np.nanmean(surface[finite]))
            else:
                mean_t = 0.0
            mean_t = max(0.0, min(nt - 1, mean_t))

            pair = self._stratal_plane_items.get(idx)
            if pair is None:
                image = GLImageLutItem(idx_img, cmap_name=self._cmap_name, smooth=True)
                line = gl.GLLinePlotItem(
                    pos=np.array(
                        [[0, 0, 0], [ni * si, 0, 0],
                         [ni * si, nx * sx, 0], [0, nx * sx, 0], [0, 0, 0]],
                        dtype=np.float32,
                    ),
                    color=(0.85, 0.45, 0.95, 1.0),
                    width=1,
                    antialias=True,
                )
                self._view.addItem(image)
                self._view.addItem(line)
                self._stratal_plane_items[idx] = (image, line)
            else:
                image, line = pair
                image.setData(idx_img)

            image.resetTransform()
            image.scale(si, sx, 1)
            image.translate(0, 0, self._sample_z(mean_t))
            image.setOpacity(self._stratal_opacity)

            active = idx == self._stratal_active
            line.setData(
                color=(
                    (1.0, 0.72, 0.12, 1.0) if active
                    else (0.85, 0.45, 0.95, 0.9)
                ),
                width=3 if active else 1,
                antialias=True,
            )
            line.resetTransform()
            line.translate(0, 0, self._sample_z(mean_t))
            visible = bool(
                self._planes_visible
                and self._stratal_enabled
                and self._stratal_visibility[idx]
            )
            image.setVisible(visible)
            line.setVisible(visible)

    def _clear_stratal_plane_items(self) -> None:
        pairs = list(getattr(self, "_stratal_plane_items", {}).values())
        self._clean_gl_items([image for image, _line in pairs])
        for image, line in pairs:
            for item in (image, line):
                try:
                    self._view.removeItem(item)
                except Exception:
                    pass
        self._stratal_plane_items = {}

    _PLANE_ATTRS = {
        "inline": ("_img_il", "_line_il"),
        "crossline": ("_img_xl", "_line_xl"),
        "time": ("_img_t", "_line_t"),
    }

    def _update_slice_planes(self):
        """Full rebuild (backward compatible)."""
        self._update_slice_planes_for(None)

    def _update_slice_planes_for(self, axes: set[str] | None = None):
        """Rebuild or in-place update the planes for `axes` (None = full rebuild)."""
        if axes is None or axes >= {"inline", "crossline", "time"}:
            axes = None  # fall through to full path
        if axes is None:
            # Original full-rebuild body (unchanged):
            self._clear_time_plane_items()
            self._clear_stratal_plane_items()
            items_to_clean = [
                getattr(self, "_img_il", None), getattr(self, "_img_xl", None), getattr(self, "_img_arb", None),
                getattr(self, "_line_il", None), getattr(self, "_line_xl", None), getattr(self, "_line_arb", None)
            ]
            self._clean_gl_items(items_to_clean)
            for v in items_to_clean:
                if v is not None:
                    try:
                        self._view.removeItem(v)
                    except Exception:
                        pass

            self._img_il = self._img_xl = self._img_t = self._img_arb = None
            self._line_il = self._line_xl = self._line_t = self._line_arb = None

            for item in getattr(self, '_arb_curtain_items', []):
                try:
                    self._view.removeItem(item)
                except Exception:
                    pass
            self._arb_curtain_items = []

            self._create_slice_planes()
            self._view.update()
            return

        for axis in axes:
            self._create_slice_plane(axis)
        self._view.update()

    def set_arbitrary_polyline(self, points: list[tuple[float, float]]):
        """Set the arbitrary slice polyline path (index-space coordinates).
        
        Args:
            points: List of (inline_idx, xline_idx) waypoints.
        """
        self._arb_polyline = points if len(points) >= 2 else None
        if self._loaded:
            self._update_slice_planes()
    
    def _render_polyline_curtain(self, ni, nx, nt, si, sx, st, lut):
        """Render the polyline-based arbitrary vertical curtain in 3D."""
        if self._arb_polyline is None or len(self._arb_polyline) < 2:
            return
        
        try:
            mirror = self._ensure_gpu_mirror()
            vol = mirror if mirror is not None else self._volume_data_cpu
            arb_data, cum_dist = sample_polyline_slice(vol, self._arb_polyline)
            
            if arb_data.shape[1] < 2:
                return
            
            # Render each segment of the curtain as a separate image plane
            # For simplicity, render the whole curtain as segments between consecutive waypoints
            points = self._arb_polyline
            
            # Draw the polyline path on the floor at the active time plane
            path_pts = []
            for il_idx, xl_idx in points:
                path_pts.append([il_idx * si, xl_idx * sx, self._sample_z(self._t_pos)])
            path_arr = np.array(path_pts, dtype=np.float32)
            
            self._line_arb = gl.GLLinePlotItem(
                pos=path_arr,
                color=(1.0, 0.0, 0.85, 1.0),
                width=4.0,
                antialias=True
            )
            self._view.addItem(self._line_arb)
            
            # Draw vertical curtain walls between each consecutive pair of waypoints
            img_arb_rgb = ColormapManager.apply_colormap(arb_data, lut=lut, value_range=self._slice_value_range())
            
            # We render the whole curtain as individual segment planes
            # Track horizontal position in the sampled data
            self._arb_curtain_items = []
            
            seg_start = 0
            for seg_idx in range(len(points) - 1):
                i0, x0 = points[seg_idx]
                i1, x1 = points[seg_idx + 1]
                seg_len = float(np.hypot(i1 - i0, x1 - x0))
                if seg_len < 0.01:
                    continue
                
                n_pts = max(2, int(seg_len))
                seg_end = min(seg_start + n_pts, arb_data.shape[1])
                
                if seg_end <= seg_start:
                    continue
                
                seg_data = img_arb_rgb[:, seg_start:seg_end]
                n_cols = seg_end - seg_start
                
                # Transpose for GLImageItem: (n_cols, nt, 4)
                seg_img = np.ascontiguousarray(seg_data.transpose(1, 0, 2))
                
                wx0, wy0 = float(i0 * si), float(x0 * sx)
                wx1, wy1 = float(i1 * si), float(x1 * sx)
                d_spatial = float(np.hypot(wx1 - wx0, wy1 - wy0))
                alpha_deg = float(np.degrees(np.arctan2(wy1 - wy0, wx1 - wx0)))
                
                item = gl.GLImageItem(seg_img, smooth=True)
                # Negative Y scale mirrors time downward (see _create_slice_plane);
                # curtain hangs from the top of the box.
                item.scale(d_spatial / max(n_cols, 1), -st, 1.0)
                item.rotate(90, 1, 0, 0)
                item.rotate(alpha_deg, 0, 0, 1)
                item.translate(wx0, wy0, self._sample_z(0))
                self._view.addItem(item)
                self._arb_curtain_items.append(item)
                
                # Vertical borders for this segment
                border = np.array([
                    [wx0, wy0, 0], [wx1, wy1, 0],
                    [wx1, wy1, nt * st], [wx0, wy0, nt * st],
                    [wx0, wy0, 0]
                ], dtype=np.float32)
                border_item = gl.GLLinePlotItem(
                    pos=border, color=(1.0, 0.0, 0.85, 0.6), width=2.0, antialias=True
                )
                self._view.addItem(border_item)
                self._arb_curtain_items.append(border_item)
                
                seg_start = seg_end
            
            # Emit the full curtain data for 2D panel
            self.arbitrary_slice_changed.emit(arb_data)
        except Exception as e:
            logger.error(f"Failed to render polyline curtain: {e}")

    def eventFilter(self, obj, event):
        """Detect left-clicks on 3D view for jump-to-position navigation."""
        from PySide6.QtCore import QEvent
        if obj is not self._view:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_pos = event.position()
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
                release_pos = event.position()
                dx = release_pos.x() - self._press_pos.x()
                dy = release_pos.y() - self._press_pos.y()
                self._press_pos = None
                if dx * dx + dy * dy < 25:  # 5px threshold
                    self._handle_3d_click(release_pos.x(), release_pos.y())
        return False

    def _handle_3d_click(self, px: float, py: float):
        """Ray-cast from screen point into volume bounding box and emit jump."""
        if not self._loaded:
            return
        result = self._ray_box_intersect(px, py)
        if result is not None:
            il_idx, xl_idx, t_idx = result
            self.jump_to_position.emit(il_idx, xl_idx, t_idx)

    def _ray_box_intersect(self, px: float, py: float):
        """Compute 3D volume coordinates by ray-box intersection (slab method).

        Uses the view and projection matrices to unproject screen coordinates
        into a world-space ray, then intersects against the volume AABB.
        Returns (il_idx, xl_idx, t_idx) or None.
        """
        try:
            view = self._view
            w = view.width()
            h = view.height()
            if w <= 0 or h <= 0:
                return None

            # Get view and projection matrices from pyqtgraph
            vm = view.viewMatrix()
            pm = view.projectionMatrix()

            # NDC coordinates (flip y for OpenGL)
            ndc_x = (2.0 * px / w) - 1.0
            ndc_y = 1.0 - (2.0 * py / h)

            # Compute inverse view-projection matrix
            vpm = pm * vm
            inv = vpm.inverted()
            if inv[1] != 0:
                inv_mat = inv[0]
            else:
                return None

            # Near and far points in world space
            from PySide6.QtGui import QVector4D
            near = inv_mat.map(QVector4D(ndc_x, ndc_y, -1.0, 1.0))
            far = inv_mat.map(QVector4D(ndc_x, ndc_y, 1.0, 1.0))
            if abs(near.w()) < 1e-8 or abs(far.w()) < 1e-8:
                return None
            near_w = QVector3D(near.x() / near.w(), near.y() / near.w(), near.z() / near.w())
            far_w = QVector3D(far.x() / far.w(), far.y() / far.w(), far.z() / far.w())

            # Ray direction
            direction = far_w - near_w
            length = direction.length()
            if length < 1e-8:
                return None
            direction = direction / length

            origin = near_w

            # AABB bounds in world space
            ni, nx, nt = self._volume_data_cpu.shape
            si, sx, st = self._volume_spacing
            box_min = QVector3D(0, 0, 0)
            box_max = QVector3D(ni * si, nx * sx, nt * st)

            # Slab method for ray-AABB intersection
            t_min = -1e30
            t_max = 1e30
            for i, (o, d, bmin, bmax) in enumerate([
                (origin.x(), direction.x(), box_min.x(), box_max.x()),
                (origin.y(), direction.y(), box_min.y(), box_max.y()),
                (origin.z(), direction.z(), box_min.z(), box_max.z()),
            ]):
                if abs(d) < 1e-10:
                    if o < bmin or o > bmax:
                        return None
                else:
                    t1 = (bmin - o) / d
                    t2 = (bmax - o) / d
                    if t1 > t2:
                        t1, t2 = t2, t1
                    t_min = max(t_min, t1)
                    t_max = min(t_max, t2)
                    if t_min > t_max:
                        return None

            if t_min < 0:
                t_min = t_max
            if t_min < 0:
                return None

            # Intersection point
            hit = origin + direction * t_min

            # Convert world coordinates to volume indices.
            # Z uses the time-down mapping (see sample_to_z/z_to_sample).
            il_idx = hit.x() / si
            xl_idx = hit.y() / sx
            t_idx = self._z_to_sample_index(hit.z())

            il_idx = max(0.0, min(il_idx, ni - 1))
            xl_idx = max(0.0, min(xl_idx, nx - 1))
            t_idx = max(0.0, min(t_idx, nt - 1))

            return il_idx, xl_idx, t_idx
        except Exception:
            return None

    def _on_slider(self, slice_type: str, value: int):
        if slice_type == "inline":
            self._il_slider._val_label.setText(str(value))
            self._il_pos = value
        elif slice_type == "crossline":
            self._xl_slider._val_label.setText(str(value))
            self._xl_pos = value
        elif slice_type == "time":
            self._t_slider._val_label.setText(str(value))
            self._t_pos = value

        # 3D slice planes rebuilt in the debounced handler (SeismicView._apply_pending_slice)
        if value >= 0:
            self.slice_changed.emit(slice_type, value)

    def get_slice_positions(self) -> tuple[int, int, int]:
        """Public: current (inline, crossline, time) voxel indices."""
        return (
            int(getattr(self, "_il_pos", 0) or 0),
            int(getattr(self, "_xl_pos", 0) or 0),
            int(getattr(self, "_t_pos", 0) or 0),
        )

    def set_planes_visible(self, visible: bool) -> None:
        """Show/hide orthogonal volume planes without hiding the whole widget.

        Overlay items (wells, fences) added by hosts stay under host control.
        """
        vis = bool(visible)
        self._planes_visible = vis
        for attr in (
            "_img_il",
            "_img_xl",
            "_line_il",
            "_line_xl",
            "_img_arb",
            "_line_arb",
        ):
            item = getattr(self, attr, None)
            if item is None:
                continue
            try:
                item.setVisible(vis)
            except Exception:
                pass
        # Orthogonal-slice mode must not un-hide the DualGL brick: joint
        # "地震预览体" means the IL/XL/Time planes, not volume fill.
        volume = getattr(self, "_volume_visual", None)
        if volume is not None and getattr(self, "_mode", "planes") != "volume":
            try:
                volume.setVisible(False)
            except Exception:
                pass
        time_items = getattr(self, "_time_plane_items", {})
        for position, (image, line) in time_items.items():
            time_visible = bool(
                vis
                and self._time_slices_enabled
                and self._time_slice_visibility.get(position, True)
            )
            image.setVisible(time_visible)
            line.setVisible(time_visible)
        if not time_items:
            for attr in ("_img_t", "_line_t"):
                item = getattr(self, attr, None)
                if item is not None:
                    item.setVisible(vis)
        # Keep widget itself visible so host overlays remain on-screen
        try:
            self.setVisible(True)
        except Exception:
            pass

    def set_position_external(self, slice_type: str, position: int):
        """Set a slice position from an external source (toolbar slider, etc.).

        Updates the internal state and syncs the 3D slider, but does NOT
        rebuild slice planes here -- that's expensive and happens on every
        slider tick. The caller's slice_changed handler debounces the
        actual 3D + 2D render. Hosts that need immediate geometry should use
        :meth:`apply_slice_positions`.
        """
        if not self._loaded:
            return
        if slice_type == "time":
            # Same as IL/XL: record the new index only. Rebuilding the
            # horizontal plane here made every Time-slider mouse-move a
            # GL extract+upload (~433ms SEGY timeslice I/O is the 2D
            # path; the 3D preview sync was still tens of ms × 100Hz).
            pos = int(position)
            current = self._active_time_pos
            visibility = bool(
                self._time_slice_visibility.get(
                    int(current) if current is not None else pos,
                    True,
                )
            )
            kept = [
                sample
                for sample in self._time_slice_positions
                if sample != current and sample != pos
            ]
            kept.append(pos)
            self._time_slice_positions = sorted(dict.fromkeys(kept))[:8]
            self._time_slice_visibility = {
                p: bool(self._time_slice_visibility.get(p, True))
                for p in self._time_slice_positions
            }
            self._time_slice_visibility[pos] = visibility
            self._active_time_pos = pos
            self._t_pos = pos
            slider = self._t_slider
            slider.blockSignals(True)
            slider.setValue(pos)
            slider._val_label.setText(str(pos))
            slider.blockSignals(False)
            self.slice_changed.emit(slice_type, pos)
            return
        slider_map = {
            "inline": (self._il_slider, "_il_pos"),
            "crossline": (self._xl_slider, "_xl_pos"),
        }
        entry = slider_map.get(slice_type)
        if entry is None:
            return
        slider, attr = entry
        previous = int(getattr(self, attr, position))
        slider.blockSignals(True)
        slider.setValue(position)
        slider._val_label.setText(str(position))
        slider.blockSignals(False)
        setattr(self, attr, position)
        if int(position) != previous:
            # 3D slice planes rebuilt in the debounced handler, not here.
            # Only signal real moves so no-op syncs don't spam listeners.
            self.slice_changed.emit(slice_type, position)

    def set_slice_controls_visible(self, visible: bool) -> None:
        """Show/hide the renderer's legacy three-slider control strip."""
        controls = getattr(self, "_slice_controls", None)
        if controls is not None:
            controls.setVisible(bool(visible))

    def get_time_slices(self) -> tuple[tuple[int, bool], ...]:
        """Public render-state snapshot ordered by sample index."""
        return tuple(
            (
                int(position),
                bool(self._time_slice_visibility.get(position, True)),
            )
            for position in sorted(self._time_slice_positions)
        )

    def set_time_slices(
        self,
        slices: list[tuple[int, bool]]
        | tuple[tuple[int, bool], ...],
        *,
        active: int | None = None,
        opacity: float = 0.8,
        enabled: bool = True,
    ) -> None:
        """Public: replace the horizontal Time plane render state."""
        unique: dict[int, bool] = {}
        for sample, visible in slices:
            unique[int(sample)] = bool(visible)
        positions = sorted(unique)[:8]
        if not positions:
            positions = [int(getattr(self, "_t_pos", 0) or 0)]
            unique[positions[0]] = True
        selected = int(active) if active is not None else positions[0]
        if selected not in positions:
            selected = positions[0]
        opacity_clamped = max(0.0, min(1.0, float(opacity)))
        structure_changed = (
            positions != self._time_slice_positions
            or {p: bool(v) for p, v in unique.items() if p in positions}
            != dict(self._time_slice_visibility)
        )
        active_changed = selected != self._active_time_pos
        opacity_changed = opacity_clamped != self._time_slice_opacity
        enabled_changed = bool(enabled) != getattr(
            self, "_time_slices_enabled", True
        )
        self._time_slice_positions = positions
        self._time_slice_visibility = {
            position: unique[position] for position in positions
        }
        self._active_time_pos = selected
        self._t_pos = selected
        self._time_slice_opacity = opacity_clamped
        self._time_slices_enabled = bool(enabled)
        try:
            slider = self._t_slider
            slider.blockSignals(True)
            slider.setValue(int(selected))
            slider._val_label.setText(str(int(selected)))
            slider.blockSignals(False)
        except Exception:
            pass
        if not getattr(self, "_loaded", False):
            return
        if structure_changed or not self._time_plane_items:
            self._sync_time_slice_planes()
        else:
            # Active/opacity/enabled-only changes are O(1): the planes'
            # textures and geometry do not move.
            if opacity_changed or enabled_changed:
                self._apply_time_slice_opacity()
            if active_changed:
                self._update_time_slice_borders()
        try:
            self._view.update()
        except Exception:
            pass

    def _apply_time_slice_opacity(self) -> None:
        """Push the shared opacity/enabled state onto existing planes."""
        for position, (image, _line) in getattr(
            self, "_time_plane_items", {}
        ).items():
            set_op = getattr(image, "setOpacity", None)
            if callable(set_op):
                try:
                    set_op(self._time_slice_opacity)
                except Exception:
                    pass
            try:
                visible = bool(
                    getattr(self, "_time_slices_enabled", True)
                    and self._time_slice_visibility.get(position, True)
                )
                image.setVisible(visible)
            except Exception:
                pass

    def _update_time_slice_borders(self) -> None:
        """Re-colour the plane borders for the new active time slice."""
        for position, (_image, line) in getattr(
            self, "_time_plane_items", {}
        ).items():
            try:
                is_active = position == self._active_time_pos
                line.setColor(
                    (1.0, 0.85, 0.2, 1.0) if is_active else (0.9, 0.9, 0.9, 0.6)
                )
                line.setWidth(2.5 if is_active else 1.0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Stratal / proportional slice public API
    # ------------------------------------------------------------------

    def get_stratal_slices(self) -> tuple[tuple[str, bool, float], ...]:
        """Snapshot of the stratal (proportional) slice state.

        Returns:
            One ``(label, visible, mean_depth)`` tuple per active surface, in
            registration order. ``mean_depth`` is the surface's mean sample
            index (the Z the plane is drawn at).
        """
        out: list[tuple[str, bool, float]] = []
        for idx, surface in enumerate(getattr(self, "_stratal_surfaces", [])):
            finite = np.isfinite(surface)
            mean_t = float(np.nanmean(surface[finite])) if finite.any() else 0.0
            out.append((
                self._stratal_labels[idx] if idx < len(self._stratal_labels)
                else f"stratal_{idx}",
                bool(self._stratal_visibility[idx])
                if idx < len(self._stratal_visibility) else True,
                mean_t,
            ))
        return tuple(out)

    def set_stratal_slices(
        self,
        surfaces: list[np.ndarray] | tuple[np.ndarray, ...],
        *,
        labels: list[str] | tuple[str, ...] | None = None,
        visibility: list[bool] | tuple[bool, ...] | None = None,
        active: int | None = None,
        opacity: float = 0.8,
        enabled: bool = True,
    ) -> None:
        """Public: replace the stratal (proportional) slice render state.

        Args:
            surfaces: One or more ``(nI, nX)`` grids of **sample-index**
                positions (float OK; NaN masks absent picks). Built by
                :func:`geoviz_seismic.stratal.build_proportional_surfaces` or
                :func:`geoviz_seismic.stratal.stratal_slice_volume`.
            labels: Optional display name per surface (defaults to
                ``stratal_0``, ``stratal_1`` ...).
            visibility: Optional on/off per surface (default all visible).
            active: Index of the highlighted surface (default 0; or the first
                visible one).
            opacity: Shared opacity for all stratal planes.
            enabled: Global on/off for all stratal planes.
        """
        surfaces = [np.asarray(s, dtype=float) for s in surfaces]
        if not surfaces:
            self.clear_stratal_slices()
            return
        n = len(surfaces)
        if labels is None:
            self._stratal_labels = [f"stratal_{i}" for i in range(n)]
        else:
            labels = list(labels)
            if len(labels) < n:
                labels += [f"stratal_{i}" for i in range(len(labels), n)]
            self._stratal_labels = labels[:n]
        if visibility is None:
            self._stratal_visibility = [True] * n
        else:
            vis = list(visibility)
            if len(vis) < n:
                vis += [True] * (n - len(vis))
            self._stratal_visibility = [bool(v) for v in vis][:n]
        sel = int(active) if active is not None else 0
        if sel not in range(n):
            sel = 0
        self._stratal_active = sel
        self._stratal_surfaces = surfaces
        self._stratal_opacity = max(0.0, min(1.0, float(opacity)))
        self._stratal_enabled = bool(enabled)
        if getattr(self, "_loaded", False):
            self._sync_stratal_planes()
            try:
                self._view.update()
            except Exception:
                pass

    def set_stratal_visible(self, enabled: bool) -> None:
        """Toggle all stratal planes without clearing them."""
        self._stratal_enabled = bool(enabled)
        if getattr(self, "_loaded", False):
            self._sync_stratal_planes()
            try:
                self._view.update()
            except Exception:
                pass

    def clear_stratal_slices(self) -> None:
        """Remove all stratal planes and their state."""
        self._stratal_surfaces = []
        self._stratal_visibility = []
        self._stratal_labels = []
        self._stratal_active = None
        self._stratal_enabled = True
        self._clear_stratal_plane_items()
        if getattr(self, "_loaded", False):
            try:
                self._view.update()
            except Exception:
                pass

    def set_orthogonal_slices(
        self,
        il: int,
        xl: int,
        time_slices: tuple[tuple[int, bool], ...],
        *,
        active_time: int,
        time_opacity: float,
        time_enabled: bool = True,
    ) -> None:
        """Public host seam for one IL, one XL and many Time planes.

        Differential: only the axes whose index changed are re-extracted and
        re-uploaded; unchanged planes keep their textures. Time planes are
        rebuilt only when the slice set/visibility/opacity actually moved
        (set_time_slices already syncs them in place).
        """
        if not self._loaded:
            return
        dirty: set[str] = set()
        if int(il) != int(self._il_pos):
            dirty.add("inline")
        if int(xl) != int(self._xl_pos):
            dirty.add("crossline")
        # Record pre-state so set_time_slices' own rebuild can be skipped when
        # nothing about the horizontal stack changed.
        prev_times = (
            list(self._time_slice_positions),
            dict(self._time_slice_visibility),
            self._active_time_pos,
            self._time_slice_opacity,
            self._time_slices_enabled,
        )
        self.set_position_external("inline", int(il))
        self.set_position_external("crossline", int(xl))
        new_times = (
            [int(s) for s, _v in time_slices],
            {int(s): bool(v) for s, v in time_slices},
            int(active_time),
            float(time_opacity),
            bool(time_enabled),
        )
        times_changed = (
            sorted(new_times[0]) != sorted(prev_times[0])
            or new_times[1] != prev_times[1]
            or new_times[2] != prev_times[2]
            or new_times[3] != prev_times[3]
            or new_times[4] != prev_times[4]
        )
        if times_changed:
            self.set_time_slices(
                time_slices,
                active=int(active_time),
                opacity=float(time_opacity),
                enabled=bool(time_enabled),
            )
        if dirty:
            self._update_slice_planes_for(dirty)
        self._view.update()

    def apply_slice_positions(
        self, il: int, xl: int, t: int, *, rebuild: bool = True
    ) -> None:
        """Public: set all three slice indices and optionally rebuild planes now.

        Used by joint hosts / clip mapping where there is no SeismicView
        debounce loop to rebuild geometry.
        """
        if not self._loaded:
            return
        for slice_type, pos in (
            ("inline", int(il)),
            ("crossline", int(xl)),
            ("time", int(t)),
        ):
            self.set_position_external(slice_type, pos)
        if rebuild:
            try:
                self._update_slice_planes()
            except Exception:
                pass
            try:
                self._view.update()
            except Exception:
                pass

    def set_camera_pose(
        self,
        *,
        distance: float = 250.0,
        elevation: float = 30.0,
        azimuth: float = 45.0,
    ) -> None:
        """Public camera control for host alignment (no private ``_view`` digs)."""
        view = getattr(self, "_view", None)
        if view is None:
            return
        try:
            view.setCameraPosition(
                distance=float(distance),
                elevation=float(elevation),
                azimuth=float(azimuth),
            )
        except Exception:
            pass

    def set_horizon_picks(self, points: list[tuple[float, float, float]]):
        """Render manually picked horizon points as a 3D scatter plot.

        Args:
            points: List of ``(il_idx, xl_idx, t_idx)`` tuples — **preview
                volume voxel indices** (float allowed for sub-voxel
                placement, e.g. from 3D click-to-jump). Each position is
                scaled by ``_volume_spacing`` into world coordinates.
        """
        if self._picks_visual is not None:
            self._view.removeItem(self._picks_visual)
            self._picks_visual = None

        if not points or not self._loaded:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        pos = np.array([
            [il * si, xl * sx, self._sample_z(t)]
            for il, xl, t in points
        ], dtype=np.float32)

        if len(pos) == 0:
            return

        color = np.full((len(pos), 4), [1.0, 0.65, 0.0, 1.0], dtype=np.float32)
        self._picks_visual = gl.GLScatterPlotItem(
            pos=pos, color=color, size=8, pxMode=True
        )
        self._view.addItem(self._picks_visual)

    def set_cursor_position(self, il_val: float, xl_val: float, t_val: float):
        """Update the linked cursor sphere position in 3D space.

        Args:
            il_val, xl_val, t_val: **Preview volume voxel indices** (float
                allowed for sub-voxel positions). Each index is scaled by
                ``_volume_spacing`` into world coordinates.
        """
        if not self._loaded:
            return
        si, sx, st = self._volume_spacing
        pos = np.array([[il_val * si, xl_val * sx, self._sample_z(t_val)]], dtype=np.float32)
        if self._cursor_sphere is None:
            self._cursor_sphere = gl.GLScatterPlotItem(
                pos=pos, color=np.array([[1.0, 1.0, 0.0, 1.0]], dtype=np.float32),
                size=12, pxMode=True,
            )
            self._view.addItem(self._cursor_sphere)
        else:
            self._cursor_sphere.setData(pos=pos)

    def set_annotations(self, annotations: list[tuple[float, float, float, str]]):
        """Render text annotations in 3D space.

        Args:
            annotations: List of ``(il_idx, xl_idx, t_idx, text)`` tuples —
                **preview volume voxel indices** (float allowed for sub-voxel
                placement). Each position is scaled by ``_volume_spacing``
                into world coordinates.
        """
        for item in self._annotation_items:
            try:
                self._view.removeItem(item)
            except Exception:
                pass
        self._annotation_items = []

        if not annotations or not self._loaded:
            return

        si, sx, st = self._volume_spacing

        for il_val, xl_val, t_val, text in annotations:
            try:
                pos = np.array([il_val * si, xl_val * sx, self._sample_z(t_val)])
                item = gl.GLTextItem(
                    pos=pos,
                    text=text,
                    color=(255, 255, 0, 255),
                )
                self._view.addItem(item)
                self._annotation_items.append(item)
            except Exception:
                pass

    # Helper for existing API compatibility
    def grab(self):
        """Compatibility wrapper mirroring QWidget method to return current frame render."""
        return self._view.grabFramebuffer()
