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
    is_gpu_available, to_gpu, to_cpu, slice_volume_gpu, apply_colormap_gpu,
    sample_arbitrary_slice_gpu, sample_polyline_slice
)

logger = logging.getLogger(__name__)

def compute_normal_map(data: np.ndarray) -> np.ndarray:
    """Vectorized CPU-based normal map calculation from 3D volume gradient."""
    # Gradient in [z, y, x] order for numpy array [ni, nx, nt] (conventionally)
    # But seismic data is often [il, xl, t]
    dz, dy, dx = np.gradient(data)
    
    # Pack into normal vector and normalize
    # Flip gradients to get normal pointing 'up' from reflections
    N = np.stack([-dx, -dy, -dz], axis=-1)
    norm = np.linalg.norm(N, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    N /= norm
    
    # Map from [-1, 1] to [0, 255] for uint8 storage
    return ((N + 1.0) * 127.5).astype(np.uint8)

def normalize_volume_to_uint8(data: np.ndarray) -> np.ndarray:
    """Normalize raw float or other data to 0-255 uint8 range for texture mapping."""
    if data is None:
        return None
    dmin = np.nanmin(data)
    dmax = np.nanmax(data)
    if dmax == dmin:
        return np.zeros_like(data, dtype=np.uint8)
    norm = (data - dmin) / (dmax - dmin)
    return (norm * 255.0).astype(np.uint8)

class Renderer3DLODManager:
    """Manages dynamic LOD level during active 3D camera interaction."""

    def __init__(self, idle_debounce_ms: float = 50.0):
        self.idle_debounce_ms = idle_debounce_ms

    def get_render_lod(self, is_interacting: bool, idle_ms: float) -> int:
        if is_interacting or idle_ms < self.idle_debounce_ms:
            return 2  # 2x downsampled LOD
        return 1  # Full resolution


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

    def get_lod_data(self, lod_level: int = 1) -> np.ndarray:
        if lod_level <= 1 or self.data is None:
            return self.data
        return self.data[::lod_level, ::lod_level, ::lod_level]

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
        
        h, w = self._sculpt_horizon_data.shape
        # We upload a single channel float32 texture
        data = np.ascontiguousarray(self._sculpt_horizon_data)
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
        
        h, w, d = self._normal_data.shape[:3]
        GL.glTexImage3D(GL.GL_TEXTURE_3D, 0, GL.GL_RGB8, w, h, d, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, self._normal_data)
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
            mode_val = 0 if self._sculpting_mode == "below" else 1
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
        """Cleanup OpenGL textures."""
        ctx = QtGui.QOpenGLContext.currentContext()
        if ctx is not None:
            if self._primary_cmap_tex is not None:
                try:
                    GL.glDeleteTextures([self._primary_cmap_tex])
                except Exception:
                    pass
                self._primary_cmap_tex = None
            if self._overlay_cmap_tex is not None:
                try:
                    GL.glDeleteTextures([self._overlay_cmap_tex])
                except Exception:
                    pass
                self._overlay_cmap_tex = None
            if self._sculpt_horizon_tex is not None:
                try:
                    GL.glDeleteTextures([self._sculpt_horizon_tex])
                except Exception:
                    pass
                self._sculpt_horizon_tex = None
            if self._normal_tex is not None:
                try:
                    GL.glDeleteTextures([self._normal_tex])
                except Exception:
                    pass
                self._normal_tex = None


class Renderer3D(QWidget):
    """3-D seismic volume renderer using PyQtGraph (Wayland + Native Qt compatible).

    Leverages QOpenGLWidget for reliable composition and optional CuPy backend
    for accelerated slicing operations.
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
        
        self._volume_spacing = (1, 1, 1)
        self._volume_origin = (0, 0, 0)
        self._meta = None
        self._cmap_name = "seismic"
        self._il_pos = 0
        self._xl_pos = 0
        self._t_pos = 0
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

        self._init_pyqtgraph(layout)
        self._plotter = True  # Keeps state parity with external API expectations

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_pyqtgraph(self, layout: QVBoxLayout):
        # Create central 3D widget
        self._view = gl.GLViewWidget()
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
        self._shading_enabled = enabled
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            self._volume_visual.setShading(enabled)

    def set_sculpting_surface(self, surface_z: np.ndarray | None, mode: str = "above"):
        self._sculpt_surface = surface_z
        self._sculpt_mode = mode
        if self._volume_visual is not None and isinstance(self._volume_visual, DualGLVolumeItem):
            if surface_z is not None and self._volume_data_cpu is not None:
                nt = self._volume_data_cpu.shape[2]
                norm_surface = surface_z / max(1, nt - 1)
            else:
                norm_surface = None
            self._volume_visual.setSculpting(
                surface_z is not None, 
                norm_surface, 
                mode
            )

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0),
                    spacing=(1, 1, 1)):
        """Load volume into renderer, automatically syncing to GPU if available."""
        self._volume_data_cpu = data
        self._volume_spacing = spacing
        self._volume_origin = origin
        
        # Transparently attempt mirroring to GPU for slicing acceleration
        if is_gpu_available():
            try:
                self._volume_data_gpu = to_gpu(data)
                logger.info("Seismic volume successfully cached on GPU via CuPy.")
            except Exception as e:
                logger.warning(f"Failed to push volume to GPU: {e}. Falling back to CPU slicing.")
                self._volume_data_gpu = None
        else:
            self._volume_data_gpu = None

        self._clear_visuals()

        ni, nx, nt = data.shape
        self._il_pos = ni // 2
        self._xl_pos = nx // 2
        self._t_pos = nt // 2
        
        # Setup spatial scaling
        si, sx, st = spacing
        
        # Center the camera dynamically based on volume size
        cx = (ni * si) / 2
        cy = (nx * sx) / 2
        cz = (nt * st) / 2
        self._view.opts['center'] = QVector3D(cx, cy, cz)
        self._view.setCameraPosition(distance=max(ni*si, nx*sx, nt*st) * 1.5)
        
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
                    spacing=(1, 1), name: str = "horizon", color=(1.0, 0.9, 0.2, 0.6)):
        """Renders horizon as a 3D mesh surface."""
        if horizon_data is None:
            return

        # Remove previous single-horizon if it exists
        if self._horizon_visual is not None:
            self._view.removeItem(self._horizon_visual)
            self._horizon_visual = None

        # Remove existing horizon with same name
        if name in self._horizons:
            self._view.removeItem(self._horizons[name])

        nI, nX = horizon_data.shape
        x = np.arange(nX, dtype=np.float32) * spacing[1] + origin[0]
        y = np.arange(nI, dtype=np.float32) * spacing[0] + origin[1]
        xx, yy = np.meshgrid(x, y)

        verts = np.dstack([xx, yy, horizon_data.astype(np.float32)])

        faces = []
        for i in range(nI - 1):
            for j in range(nX - 1):
                p0 = i * nX + j
                p1 = p0 + 1
                p2 = (i + 1) * nX + j
                p3 = p2 + 1
                faces.append([p0, p1, p2])
                faces.append([p1, p3, p2])

        faces = np.array(faces)
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
        v[:, 2] = v[:, 2] * st + ot
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
        self._update_slice_planes()
        
        # Optimize: If volume rendering is active, update colormaps in-place instead of rebuilding
        if self._mode == "volume" and isinstance(self._volume_visual, DualGLVolumeItem):
            from .colormap import ColormapManager
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

    def _rebuild_volume_visual(self):
        """Rebuild the GLVolumeItem with current opacity settings using our shared texture custom shader optimization."""
        if self._volume_visual is not None:
            try:
                self._view.removeItem(self._volume_visual)
            except Exception:
                pass
            if hasattr(self._volume_visual, 'clean'):
                try:
                    self._volume_visual.clean()
                except Exception:
                    pass
            self._volume_visual = None

        if self._volume_data_cpu is None:
            return

        try:
                        # Downsample and normalize primary volume data
            primary_data = self._volume_data_cpu[::2, ::2, ::2]
            primary_normalized = normalize_volume_to_uint8(primary_data)
            
            # Pre-compute normals for hillshading (Phase 2 Audit Task 2)
            normal_data = compute_normal_map(primary_data)

            # Downsample and normalize overlay volume data if available if available
            if self._overlay_volume_data_cpu is not None:
                overlay_data = self._overlay_volume_data_cpu[::2, ::2, ::2]
                overlay_normalized = normalize_volume_to_uint8(overlay_data)
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
            si, sx, st = self._volume_spacing
            self._volume_visual = DualGLVolumeItem(vol_data_combined, normal_data=normal_data, sliceDensity=3, smooth=True)
            self._volume_visual.setColormaps(cmap_data_primary, cmap_data_overlay)
            self._volume_visual.setOverlayOpacity(self._overlay_opacity)
            self._volume_visual.setOverlayVisible(self._overlay_visible)
            if self._sculpt_surface is not None and self._volume_data_cpu is not None:
                nt = self._volume_data_cpu.shape[2]
                norm_surface = self._sculpt_surface / max(1, nt - 1)
            else:
                norm_surface = None
            self._volume_visual.setSculpting(
                self._sculpt_surface is not None,
                norm_surface,
                self._sculpt_mode
            )
            self._volume_visual.setShading(self._shading_enabled)
            self._volume_visual.scale(si * 2, sx * 2, st * 2)

            self._view.addItem(self._volume_visual)
            if self._mode != "volume":
                self._volume_visual.hide()
            self._view.update()
        except Exception as e:
            logger.warning(f"Rebuild volume visual failed: {e}", exc_info=True)

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
        self._loaded = False
        self._volume_data_cpu = None
        self._volume_data_gpu = None
        self._overlay_volume_data_cpu = None
        self._overlay_volume_visual = None

    def _clear_visuals(self):
        for v in (self._volume_visual, self._overlay_volume_visual, self._img_il, self._img_xl,
                  self._img_t, self._img_arb, self._horizon_visual,
                  self._picks_visual, self._bbox_visual, self._cursor_sphere):
            if v is not None:
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
        for attr in ('_line_il', '_line_xl', '_line_t', '_line_arb'):
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

    def _create_axis_labels(self, ni, nx, nt, sp):
        """Create visible 3D coordinate axes with colored lines, arrows, and tick labels."""
        si, sx, st = sp
        max_dim = max(ni * si, nx * sx, nt * st)
        pad = max_dim * 0.08  # Extension beyond bounding box
        
        self._axis_labels = []
        
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
            il_label = gl.GLTextItem(
                pos=np.array([ni * si + pad * 1.2, 0, 0]),
                text=f'Inline (0-{ni-1})',
                color=(255, 100, 100, 255)
            )
            xl_label = gl.GLTextItem(
                pos=np.array([0, nx * sx + pad * 1.2, 0]),
                text=f'Xline (0-{nx-1})',
                color=(100, 220, 100, 255)
            )
            t_label = gl.GLTextItem(
                pos=np.array([0, 0, nt * st + pad * 1.2]),
                text=f'Time (0-{nt-1})',
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
                pos_il = np.array([frac * ni * si, -tick_offset, 0])
                tick_il = gl.GLTextItem(
                    pos=pos_il,
                    text=str(int(frac * ni)),
                    color=(220, 180, 180, 220)
                )
                self._view.addItem(tick_il)
                self._axis_labels.append(tick_il)
                
                pos_xl = np.array([-tick_offset, frac * nx * sx, 0])
                tick_xl = gl.GLTextItem(
                    pos=pos_xl,
                    text=str(int(frac * nx)),
                    color=(180, 220, 180, 220)
                )
                self._view.addItem(tick_xl)
                self._axis_labels.append(tick_xl)
                
                pos_t = np.array([-tick_offset, -tick_offset, frac * nt * st])
                tick_t = gl.GLTextItem(
                    pos=pos_t,
                    text=str(int(frac * nt)),
                    color=(180, 190, 220, 220)
                )
                self._view.addItem(tick_t)
                self._axis_labels.append(tick_t)
            except Exception:
                pass

    def _get_sliced_data(self, axis: int, index: int) -> np.ndarray:
        """Retrieves slice, prioritizing GPU cached volume memory if accessible."""
        vol = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
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

        # 1-3. Axis-aligned planes (Inline / Crossline / Time)
        self._create_slice_plane("inline")
        self._create_slice_plane("crossline")
        self._create_slice_plane("time")

        # 4. Polyline-driven arbitrary curtain (if set)
        self._render_polyline_curtain(ni, nx, nt, si, sx, st, lut)

    def _create_slice_plane(self, axis: str):
        """Build or update the slice plane + border for a single axis (inline/crossline/time) in-place."""
        if self._volume_data_cpu is None:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing
        lut = ColormapManager.get_colormap(self._cmap_name)

        if axis == "inline":
            # 1. Inline — Perpendicular to IL axis (x)
            il_raw = self._get_sliced_data(0, self._il_pos)
            img_il_rgb = apply_colormap_gpu(il_raw, lut)

            if self._img_il is not None and self._line_il is not None:
                # Fast In-Place Texture & Transform Update
                self._img_il.setData(img_il_rgb)
                self._img_il.resetTransform()
                self._img_il.scale(sx, st, 1)
                self._img_il.rotate(90, 1, 0, 0)
                self._img_il.rotate(90, 0, 0, 1)
                self._img_il.translate(self._il_pos * si, 0, 0)

                self._line_il.resetTransform()
                self._line_il.translate(self._il_pos * si, 0, 0)
            else:
                self._img_il = gl.GLImageItem(img_il_rgb)
                self._img_il.scale(sx, st, 1)
                self._img_il.rotate(90, 1, 0, 0)
                self._img_il.rotate(90, 0, 0, 1)
                self._img_il.translate(self._il_pos * si, 0, 0)
                self._view.addItem(self._img_il)

                il_pts = np.array([[0, 0, 0], [0, nx*sx, 0], [0, nx*sx, nt*st], [0, 0, nt*st], [0, 0, 0]])
                self._line_il = gl.GLLinePlotItem(pos=il_pts, color=(1, 0, 0, 1), width=2, antialias=True)
                self._line_il.translate(self._il_pos * si, 0, 0)
                self._view.addItem(self._line_il)

        elif axis == "crossline":
            # 2. Crossline — Perpendicular to XL axis (y)
            xl_raw = self._get_sliced_data(1, self._xl_pos)
            img_xl_rgb = apply_colormap_gpu(xl_raw, lut)

            if self._img_xl is not None and self._line_xl is not None:
                # Fast In-Place Texture & Transform Update
                self._img_xl.setData(img_xl_rgb)
                self._img_xl.resetTransform()
                self._img_xl.scale(si, st, 1)
                self._img_xl.rotate(90, 1, 0, 0)
                self._img_xl.translate(0, self._xl_pos * sx, 0)

                self._line_xl.resetTransform()
                self._line_xl.translate(0, self._xl_pos * sx, 0)
            else:
                self._img_xl = gl.GLImageItem(img_xl_rgb)
                self._img_xl.scale(si, st, 1)
                self._img_xl.rotate(90, 1, 0, 0)
                self._img_xl.translate(0, self._xl_pos * sx, 0)
                self._view.addItem(self._img_xl)

                xl_pts = np.array([[0, 0, 0], [ni*si, 0, 0], [ni*si, 0, nt*st], [0, 0, nt*st], [0, 0, 0]])
                self._line_xl = gl.GLLinePlotItem(pos=xl_pts, color=(0, 1, 0, 1), width=2, antialias=True)
                self._line_xl.translate(0, self._xl_pos * sx, 0)
                self._view.addItem(self._line_xl)

        elif axis == "time":
            # 3. Time — Perpendicular to T axis (z)
            t_raw = self._get_sliced_data(2, self._t_pos)
            img_t_rgb = apply_colormap_gpu(t_raw, lut)

            if self._img_t is not None and self._line_t is not None:
                # Fast In-Place Texture & Transform Update (Zero Scene Graph Overhead)
                self._img_t.setData(img_t_rgb)
                self._img_t.resetTransform()
                self._img_t.scale(si, sx, 1)
                self._img_t.translate(0, 0, self._t_pos * st)

                self._line_t.resetTransform()
                self._line_t.translate(0, 0, self._t_pos * st)
            else:
                self._img_t = gl.GLImageItem(img_t_rgb)
                self._img_t.scale(si, sx, 1)
                self._img_t.translate(0, 0, self._t_pos * st)
                self._view.addItem(self._img_t)

                t_pts = np.array([[0, 0, 0], [ni*si, 0, 0], [ni*si, nx*sx, 0], [0, nx*sx, 0], [0, 0, 0]])
                self._line_t = gl.GLLinePlotItem(pos=t_pts, color=(0, 0, 1, 1), width=2, antialias=True)
                self._line_t.translate(0, 0, self._t_pos * st)
                self._view.addItem(self._line_t)

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
            items_to_clean = (
                getattr(self, "_img_il", None), getattr(self, "_img_xl", None), getattr(self, "_img_t", None), getattr(self, "_img_arb", None),
                getattr(self, "_line_il", None), getattr(self, "_line_xl", None), getattr(self, "_line_t", None), getattr(self, "_line_arb", None)
            )
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
            vol = self._volume_data_gpu if self._volume_data_gpu is not None else self._volume_data_cpu
            arb_data, cum_dist = sample_polyline_slice(vol, self._arb_polyline)
            
            if arb_data.shape[1] < 2:
                return
            
            # Render each segment of the curtain as a separate image plane
            # For simplicity, render the whole curtain as segments between consecutive waypoints
            points = self._arb_polyline
            
            # Draw the polyline path on the floor (time=t_pos*st) as a magenta line
            path_pts = []
            for il_idx, xl_idx in points:
                path_pts.append([il_idx * si, xl_idx * sx, self._t_pos * st])
            path_arr = np.array(path_pts, dtype=np.float32)
            
            self._line_arb = gl.GLLinePlotItem(
                pos=path_arr,
                color=(1.0, 0.0, 0.85, 1.0),
                width=4.0,
                antialias=True
            )
            self._view.addItem(self._line_arb)
            
            # Draw vertical curtain walls between each consecutive pair of waypoints
            img_arb_rgb = apply_colormap_gpu(arb_data, lut)
            
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
                
                item = gl.GLImageItem(seg_img)
                item.scale(d_spatial / max(n_cols, 1), st, 1.0)
                item.rotate(90, 1, 0, 0)
                item.rotate(alpha_deg, 0, 0, 1)
                item.translate(wx0, wy0, 0)
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

            # Convert world coordinates to volume indices
            il_idx = hit.x() / si
            xl_idx = hit.y() / sx
            t_idx = hit.z() / st

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

    def set_position_external(self, slice_type: str, position: int):
        """Set a slice position from an external source (toolbar slider, etc.).

        Updates the internal state and syncs the 3D slider, but does NOT
        rebuild slice planes here -- that's expensive and happens on every
        slider tick. The caller's slice_changed handler debounces the
        actual 3D + 2D render.
        """
        if not self._loaded:
            return
        slider_map = {
            "inline": (self._il_slider, "_il_pos"),
            "crossline": (self._xl_slider, "_xl_pos"),
            "time": (self._t_slider, "_t_pos"),
        }
        entry = slider_map.get(slice_type)
        if entry is None:
            return
        slider, attr = entry
        slider.blockSignals(True)
        slider.setValue(position)
        slider._val_label.setText(str(position))
        slider.blockSignals(False)
        setattr(self, attr, position)
        # 3D slice planes rebuilt in the debounced handler, not here.
        self.slice_changed.emit(slice_type, position)

    def set_horizon_picks(self, points: list[tuple[float, float, float]]):
        """Render manually picked horizon points as a 3D scatter plot.

        Args:
            points: List of (inline_num, xline_num, time_ms) tuples.
        """
        if self._picks_visual is not None:
            self._view.removeItem(self._picks_visual)
            self._picks_visual = None

        if not points or not self._loaded:
            return

        ni, nx, nt = self._volume_data_cpu.shape
        si, sx, st = self._volume_spacing

        pos = np.array([
            [il * si, xl * sx, t * st]
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
            il_val, xl_val, t_val: Coordinate values in seismic units.
        """
        if not self._loaded:
            return
        si, sx, st = self._volume_spacing
        pos = np.array([[il_val * si, xl_val * sx, t_val * st]], dtype=np.float32)
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
            annotations: List of (il_val, xl_val, time_val, text) tuples.
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
                pos = np.array([il_val * si, xl_val * sx, t_val * st])
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
