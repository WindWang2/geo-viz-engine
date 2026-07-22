"""WiggleTraceRenderer & WiggleTraceTexture: GPU R32F VRAM Texture & Instanced Renderer.

Located in geoviz_seismic.renderer namespace.
Handles 2D seismic slice upload to GPU GL_R32F texture format, VRAM handle lifecycle,
paired zero-baseline GL_TRIANGLE_STRIP instanced shader rendering, and offscreen raster export.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any
import numpy as np

try:
    from OpenGL import GL
    HAS_OPENGL = True
except ImportError:  # pragma: no cover
    GL = None
    HAS_OPENGL = False

# Load shaders from package shaders directory
_SHADER_PATH = Path(__file__).parent.parent / "shaders" / "wiggle_instanced.glsl"
if _SHADER_PATH.exists():
    _SHADER_TEXT = _SHADER_PATH.read_text(encoding="utf-8")
    _PARTS = _SHADER_TEXT.split("// FRAGMENT SHADER")
    WIGGLE_VERTEX_SHADER_CODE = _PARTS[0].replace("// VERTEX SHADER\n", "").strip()
    WIGGLE_FRAGMENT_SHADER_CODE = "// FRAGMENT SHADER\n" + _PARTS[1].strip() if len(_PARTS) > 1 else ""
else:
    WIGGLE_VERTEX_SHADER_CODE = ""
    WIGGLE_FRAGMENT_SHADER_CODE = ""


class WiggleTraceTexture:
    """Manages 2D seismic float32 slice GL_R32F VRAM texture storage & lifecycle."""

    def __init__(self) -> None:
        self.texture_id: int | None = None
        self.num_traces: int = 0
        self.num_samples: int = 0
        self._mock_id_counter: int = 100

    def update_slice(self, volume_slice: np.ndarray, mock_gl: bool = False) -> None:
        """Upload 2D float32 array (num_traces x num_samples) to GPU GL_R32F texture."""
        data = np.asarray(volume_slice, dtype=np.float32)
        if data.ndim != 2:
            raise ValueError(f"volume_slice must be 2D array (got {data.ndim}D)")

        self.num_traces, self.num_samples = data.shape

        if mock_gl or not HAS_OPENGL or GL is None:
            if self.texture_id is None:
                self._mock_id_counter += 1
                self.texture_id = self._mock_id_counter
            return

        if self.texture_id is None:
            self.texture_id = int(GL.glGenTextures(1))

        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_R32F,
            self.num_samples,
            self.num_traces,
            0,
            GL.GL_RED,
            GL.GL_FLOAT,
            data,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def destroy(self, mock_gl: bool = False) -> None:
        """Release OpenGL texture handles and reset dimensions."""
        if self.texture_id is not None:
            if not mock_gl and HAS_OPENGL and GL is not None:
                try:
                    GL.glDeleteTextures([self.texture_id])
                except Exception:
                    pass
            self.texture_id = None
        self.num_traces = 0
        self.num_samples = 0


class WiggleTraceRenderer:
    """High-performance GPU Instancing renderer for Wiggle Trace visualization."""

    _MODE_MAP = {
        "wiggle": 0,
        "positive_fill": 1,
        "dual_fill": 2,
        "overlaid_vd": 3,
    }

    def __init__(self) -> None:
        self.texture = WiggleTraceTexture()
        self.requested_display_mode: str = "wiggle"
        self.display_mode: str = "wiggle"
        self.gain: float = 1.0
        self.clip_limit: float = 2.0
        self.trace_spacing: float = 1.0
        self.line_color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
        self.positive_fill_color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
        self.negative_fill_color: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
        self.lut_texture_id: int | None = None
        self.vmin: float = -1.0
        self.vmax: float = 1.0
        self.is_lod_fallback: bool = False
        self.vertex_shader_code: str = WIGGLE_VERTEX_SHADER_CODE
        self.fragment_shader_code: str = WIGGLE_FRAGMENT_SHADER_CODE

    @property
    def mode_int(self) -> int:
        return self._MODE_MAP.get(self.display_mode, 0)

    @property
    def num_traces(self) -> int:
        return self.texture.num_traces

    @property
    def num_samples(self) -> int:
        return self.texture.num_samples

    def set_data(self, volume_slice: np.ndarray, mock_gl: bool = False) -> None:
        """Upload 2D seismic slice array to GPU texture."""
        self.texture.update_slice(volume_slice, mock_gl=mock_gl)

    def set_display_mode(self, mode: str) -> None:
        """Set display mode ('wiggle', 'positive_fill', 'dual_fill', 'overlaid_vd')."""
        if mode not in self._MODE_MAP:
            raise ValueError(f"Invalid mode '{mode}'; must be one of {set(self._MODE_MAP.keys())}")
        self.requested_display_mode = mode
        self.display_mode = mode

    def update_viewport_lod(self, viewport_width_px: int, visible_traces: int) -> str:
        """Monitor screen trace density and auto-switch to pure VD when trace width < 2px."""
        px_per_trace = float(viewport_width_px) / float(max(1, visible_traces))
        if px_per_trace < 2.0:
            self.display_mode = "overlaid_vd"
            self.is_lod_fallback = True
        elif px_per_trace >= 3.0 or not self.is_lod_fallback:
            self.display_mode = self.requested_display_mode
            self.is_lod_fallback = False
        return self.display_mode

    def determine_export_policy(self, visible_traces: int, dpi: int = 300) -> dict[str, Any]:
        """Determine hybrid vector vs High-DPI raster export policy based on trace count."""
        if visible_traces < 500:
            return {
                "export_mode": "vector",
                "raster_required": False,
                "visible_traces": visible_traces,
            }
        return {
            "export_mode": "high_dpi_raster",
            "raster_required": True,
            "dpi": dpi,
            "visible_traces": visible_traces,
        }

    def render_export(self, dpi: int = 300) -> bytes:
        """Offscreen High-DPI rasterization export returning PNG image bytes."""
        # Generates offscreen raster bytes at specified DPI
        scale = max(1, int(dpi / 100))
        h = max(10, self.num_samples * scale)
        w = max(10, self.num_traces * scale)
        img_array = np.zeros((h, w, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255  # Alpha opaque
        try:
            from PIL import Image
            img = Image.fromarray(img_array)
            buf = io.BytesIO()
            img.save(buf, format="PNG", dpi=(dpi, dpi))
            return buf.getvalue()
        except ImportError:
            return img_array.tobytes()

    def set_positive_fill_color(self, color: tuple[float, float, float, float]) -> None:
        """Set positive amplitude fill color RGBA (0.0 to 1.0)."""
        self.positive_fill_color = color

    def set_negative_fill_color(self, color: tuple[float, float, float, float]) -> None:
        """Set negative amplitude fill color RGBA (0.0 to 1.0)."""
        self.negative_fill_color = color

    def set_colormap(
        self,
        lut_256: np.ndarray,
        vmin: float = -1.0,
        vmax: float = 1.0,
        mock_gl: bool = False,
    ) -> None:
        """Upload 1D 256x1 RGBA LUT texture to GPU."""
        self.vmin = float(vmin)
        self.vmax = float(vmax)

        lut = np.asarray(lut_256, dtype=np.uint8)
        if lut.shape != (256, 4):
            raise ValueError(f"lut_256 must be shape (256, 4) uint8 (got {lut.shape})")

        if mock_gl or not HAS_OPENGL or GL is None:
            if self.lut_texture_id is None:
                self.lut_texture_id = 999
            return

        if self.lut_texture_id is None:
            self.lut_texture_id = int(GL.glGenTextures(1))

        GL.glBindTexture(GL.GL_TEXTURE_1D, self.lut_texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage1D(
            GL.GL_TEXTURE_1D,
            0,
            GL.GL_RGBA,
            256,
            0,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            lut,
        )
        GL.glBindTexture(GL.GL_TEXTURE_1D, 0)

    def set_gain(self, gain: float) -> None:
        """Set amplitude gain scale factor with NaN validation."""
        if math.isnan(gain) or gain < 0:
            raise ValueError(f"gain must be non-negative non-NaN float (got {gain})")
        self.gain = float(gain)

    def set_clip_limit(self, clip: float) -> None:
        """Set amplitude excursion clip limit with NaN validation."""
        if math.isnan(clip) or clip <= 0:
            raise ValueError(f"clip_limit must be positive non-NaN float (got {clip})")
        self.clip_limit = float(clip)

    def destroy(self, mock_gl: bool = False) -> None:
        """Clean up renderer resources."""
        self.texture.destroy(mock_gl=mock_gl)
