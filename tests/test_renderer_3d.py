import numpy as np
import pytest
import warnings
from PySide6.QtCore import Signal

def test_renderer_3d_init(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    # Ensure core 3D view initialized
    assert widget._view is not None
    assert widget._plotter is True

def test_renderer_3d_load_volume(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)
    assert widget._loaded
    # Ensure basic visual items added to view
    assert len(widget._view.items) > 0

def test_renderer_3d_load_volume_does_not_warn_on_slider_connections(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        widget.load_volume(data)
        widget.load_volume(data)

    disconnect_warnings = [
        warning
        for warning in caught
        if "Failed to disconnect" in str(warning.message)
    ]
    assert disconnect_warnings == []


def test_renderer_3d_base_grid_position_and_reset(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(100, 100, 50).astype(np.float32)

    # First load
    widget.load_volume(data, spacing=(2.0, 2.0, 1.0))
    t1 = widget._base_grid.transform().matrix()
    pos1_x = t1[0, 3]  # Translation X element
    pos1_y = t1[1, 3]  # Translation Y element

    # Expected cx = (100 * 2.0)/2 = 100.0, cy = (100 * 2.0)/2 = 100.0
    assert abs(pos1_x - 100.0) < 1e-3
    assert abs(pos1_y - 100.0) < 1e-3

    # Second load with same data
    widget.load_volume(data, spacing=(2.0, 2.0, 1.0))
    t2 = widget._base_grid.transform().matrix()
    pos2_x = t2[0, 3]
    pos2_y = t2[1, 3]

    # Translation X/Y should remain 100.0, NOT accumulate to 200.0!
    assert abs(pos2_x - 100.0) < 1e-3
    assert abs(pos2_y - 100.0) < 1e-3

def test_renderer_3d_signals():
    """Verify Renderer3D class exposes the expected signal."""
    from geoviz_seismic.renderer_3d import Renderer3D

    assert hasattr(Renderer3D, "slice_changed")
    assert isinstance(Renderer3D.slice_changed, Signal)

def test_renderer_3d_add_horizon(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    h_data = np.zeros((5, 5), dtype=np.float32)
    widget.add_horizon(h_data, name="test_horizon")
    assert "test_horizon" in widget._horizons
    assert widget._horizons["test_horizon"] is not None

def test_renderer_3d_dual_volume(qtbot):
    """Verify that Renderer3D supports loading and managing a dual-volume overlay (amplitude + attribute)."""
    from geoviz_seismic.renderer_3d import Renderer3D
    
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    # 1. Load primary volume
    primary_data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(primary_data)
    assert widget._loaded
    widget.set_render_mode("volume")
    
    # 2. Load overlay/attribute volume
    overlay_data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_overlay_volume(overlay_data, colormap="jet", opacity=0.6)
    
    # Ensure overlay visual item created and added
    assert widget._overlay_volume_visual is not None
    assert widget._overlay_volume_visual in widget._view.items
    
    # 3. Test changing overlay properties
    widget.set_overlay_colormap("seismic")
    assert widget._overlay_cmap_name == "seismic"
    
    widget.set_overlay_opacity(0.8)
    assert widget._overlay_opacity == 0.8
    
    # 4. Test visibility toggle
    widget.set_overlay_visible(False)
    assert widget._overlay_volume_visual.visible() is False
    
    widget.set_overlay_visible(True)
    assert widget._overlay_volume_visual.visible() is True
    
    # 5. Clear overlay
    widget.clear_overlay_volume()
    assert widget._overlay_volume_visual is None

def test_dual_gl_volume_item_unit(qtbot):
    """Verify that the custom DualGLVolumeItem compiled program and uniforms behave correctly."""
    from geoviz_seismic.renderer_3d import DualGLVolumeItem, Renderer3D
    
    # Initialize Renderer3D (to establish standard Qt OpenGL context)
    widget = Renderer3D()
    qtbot.addWidget(widget)
    
    mock_data = np.zeros((4, 4, 4, 4), dtype=np.uint8)
    item = DualGLVolumeItem(mock_data)
    
    # Check initial values
    assert item._primary_visible is True
    assert item._overlay_visible is True
    assert item._overlay_opacity == 0.5
    
    # Check setters
    item.setOverlayOpacity(0.7)
    assert item._overlay_opacity == 0.7
    
    item.setOverlayVisible(False)
    assert item._overlay_visible is False
    
    item.setPrimaryVisible(False)
    assert item._primary_visible is False
    
    # Check colormap setup
    primary_lut = np.ones((256, 4), dtype=np.uint8) * 10
    overlay_lut = np.ones((256, 4), dtype=np.uint8) * 20
    item.setColormaps(primary_lut, overlay_lut)
    
    assert item._primary_cmap_lut is primary_lut
    assert item._overlay_cmap_lut is overlay_lut
    assert item._cmap_needs_upload is True


def test_dual_gl_volume_item_uses_pyopengl_compiler_and_clean_gles3_source(
    monkeypatch,
):
    import geoviz_seismic.renderer_3d as renderer
    from OpenGL.GL import shaders as pyopengl_shaders

    compiler = getattr(renderer, "gl_shaders", None)
    assert compiler is pyopengl_shaders

    class FakeFormat:
        @staticmethod
        def version():
            return (3, 2)

    class FakeContext:
        @staticmethod
        def format():
            return FakeFormat()

        @staticmethod
        def isOpenGLES():
            return True

    class FakeQOpenGLContext:
        @staticmethod
        def currentContext():
            return FakeContext()

    captured_sources = []

    class FakeProgram(int):
        def __new__(cls, value):
            instance = super().__new__(cls, value)
            instance.link_checks = 0
            return instance

        def check_linked(self):
            self.link_checks += 1

    class FakeCompiler:
        program_calls = 0
        program = FakeProgram(97)

        @staticmethod
        def compileShader(sources, shader_type):
            captured_sources.append((tuple(sources), shader_type))
            return len(captured_sources)

        @classmethod
        def compileProgram(cls, *_shaders):
            cls.program_calls += 1
            return cls.program

    monkeypatch.setattr(renderer, "gl_shaders", FakeCompiler)
    monkeypatch.setattr(renderer.QtGui, "QOpenGLContext", FakeQOpenGLContext)
    monkeypatch.setattr(renderer.GL, "glBindAttribLocation", lambda *_args: None)
    monkeypatch.setattr(renderer.GL, "glLinkProgram", lambda *_args: None)

    item = renderer.DualGLVolumeItem(
        np.zeros((4, 4, 4, 4), dtype=np.uint8)
    )
    first = item.getCustomShaderProgram()
    second = item.getCustomShaderProgram()

    fragment_source = "".join(captured_sources[1][0])
    assert first == 97
    assert second is first
    assert len(captured_sources) == 2
    assert FakeCompiler.program_calls == 1
    assert first.link_checks == 1
    assert "#version 300 es" in fragment_source
    assert "texture3D(" not in fragment_source
    assert "texture2D(" not in fragment_source


@pytest.mark.parametrize(
    ("is_gles", "version"),
    [(True, (2, 0)), (False, (2, 1))],
    ids=["gles2", "desktop-legacy"],
)
def test_dual_gl_volume_item_legacy_shaders_use_legacy_texture_functions(
    monkeypatch,
    is_gles,
    version,
):
    import geoviz_seismic.renderer_3d as renderer

    class FakeFormat:
        @staticmethod
        def version():
            return version

    class FakeContext:
        @staticmethod
        def format():
            return FakeFormat()

        @staticmethod
        def isOpenGLES():
            return is_gles

    class FakeQOpenGLContext:
        @staticmethod
        def currentContext():
            return FakeContext()

    captured_sources = []

    class FakeCompiler:
        @staticmethod
        def compileShader(sources, shader_type):
            captured_sources.append((tuple(sources), shader_type))
            return len(captured_sources)

        @staticmethod
        def compileProgram(*_shaders):
            return object()

    monkeypatch.setattr(renderer, "gl_shaders", FakeCompiler)
    monkeypatch.setattr(renderer.QtGui, "QOpenGLContext", FakeQOpenGLContext)

    item = renderer.DualGLVolumeItem(
        np.zeros((4, 4, 4, 4), dtype=np.uint8)
    )
    item.getCustomShaderProgram()

    fragment_source = "".join(captured_sources[1][0])
    assert "texture3D(u_texture" in fragment_source
    assert "texture2D(u_horizon_texture" in fragment_source
    assert "texture(u_horizon_texture" not in fragment_source


def test_gl_image_lut_item_shader_has_lut_lookup_and_compiles(monkeypatch):
    """GLImageLutItem's shader must compile via PyOpenGL and contain the
    Indexed8+LUT lookup (``texture(u_lut, vec2(texture(u_index, uv).r, 0.5))``).
    Primary CI gate for the slice-plane LUT path — runs with zero GL hardware
    via the compiler-monkeypatch pattern copied from the DualGLVolumeItem test.
    """
    import geoviz_seismic.renderer_3d as renderer
    from OpenGL.GL import shaders as pyopengl_shaders

    assert getattr(renderer, "gl_shaders", None) is pyopengl_shaders

    class FakeFormat:
        @staticmethod
        def version():
            return (3, 2)

    class FakeContext:
        @staticmethod
        def format():
            return FakeFormat()

        @staticmethod
        def isOpenGLES():
            return True

    class FakeQOpenGLContext:
        @staticmethod
        def currentContext():
            return FakeContext()

    captured_sources = []

    class FakeProgram(int):
        def __new__(cls, value):
            return super().__new__(cls, value)

    class FakeCompiler:
        program = FakeProgram(101)

        @staticmethod
        def compileShader(sources, shader_type):
            captured_sources.append((tuple(sources), shader_type))
            return len(captured_sources)

        @classmethod
        def compileProgram(cls, *_shaders):
            return cls.program

    monkeypatch.setattr(renderer, "gl_shaders", FakeCompiler)
    monkeypatch.setattr(renderer.QtGui, "QOpenGLContext", FakeQOpenGLContext)
    monkeypatch.setattr(renderer.GL, "glBindAttribLocation", lambda *_args: None)
    monkeypatch.setattr(renderer.GL, "glLinkProgram", lambda *_args: None)

    # GLES3 >= 3.0 -> CORE shader path.
    lut = np.zeros((256, 4), dtype=np.uint8)
    item = renderer.GLImageLutItem(np.zeros((4, 4), dtype=np.uint8), cmap_name="seismic")
    first = item.getLutShaderProgram()
    second = item.getLutShaderProgram()

    assert first == 101
    assert second is first  # cached — compiled once
    assert len(captured_sources) == 2  # vertex + fragment
    fragment_source = "".join(captured_sources[1][0])
    assert "#version 300 es" in fragment_source
    # The LUT-lookup core: sample index texture .r, look up colour in u_lut.
    assert "uniform sampler2D u_index" in fragment_source
    assert "uniform sampler2D u_lut" in fragment_source
    assert "texture(u_index" in fragment_source
    assert "texture(u_lut" in fragment_source


@pytest.mark.parametrize(
    ("is_gles", "version"),
    [(True, (2, 0)), (False, (2, 1))],
    ids=["gles2", "desktop-legacy"],
)
def test_gl_image_lut_item_legacy_shader_uses_texture2d(monkeypatch, is_gles, version):
    """Legacy GL path must use texture2D (not texture())."""
    import geoviz_seismic.renderer_3d as renderer

    class FakeFormat:
        @staticmethod
        def version():
            return version

    class FakeContext:
        @staticmethod
        def format():
            return FakeFormat()

        @staticmethod
        def isOpenGLES():
            return is_gles

    class FakeQOpenGLContext:
        @staticmethod
        def currentContext():
            return FakeContext()

    captured_sources = []

    class FakeCompiler:
        @staticmethod
        def compileShader(sources, shader_type):
            captured_sources.append((tuple(sources), shader_type))
            return len(captured_sources)

        @staticmethod
        def compileProgram(*_shaders):
            return object()

    monkeypatch.setattr(renderer, "gl_shaders", FakeCompiler)
    monkeypatch.setattr(renderer.QtGui, "QOpenGLContext", FakeQOpenGLContext)
    monkeypatch.setattr(renderer.GL, "glBindAttribLocation", lambda *_args: None)
    monkeypatch.setattr(renderer.GL, "glLinkProgram", lambda *_args: None)

    item = renderer.GLImageLutItem(np.zeros((4, 4), dtype=np.uint8), cmap_name="seismic")
    item.getLutShaderProgram()

    fragment_source = "".join(captured_sources[1][0])
    assert "texture2D(u_index" in fragment_source
    assert "texture2D(u_lut" in fragment_source
    assert "texture(u_index" not in fragment_source


def test_normalize_to_index_parity_with_apply_colormap():
    """ColormapManager.normalize_to_index produces a uint8 index whose lut[idx]
    is byte-identical to ColormapManager.apply_colormap's RGBA output -
    guarantees the Indexed8 shader path renders the same pixels as the RGBA path."""
    from geoviz_seismic.colormap import ColormapManager

    rng = np.random.default_rng(7)
    data = (rng.standard_normal((100, 150)) * 10).astype(np.float32)
    vr = (float(np.nanmin(data)), float(np.nanmax(data)))

    rgba = ColormapManager.apply_colormap(data, name="seismic", value_range=vr)
    idx = ColormapManager.normalize_to_index(data, lut_size=256, value_range=vr)
    lut = ColormapManager.get_colormap("seismic")

    assert idx.dtype == np.uint8
    assert idx.shape == data.shape
    np.testing.assert_array_equal(rgba, lut[idx])


# ---------------------------------------------------------------------------
# Geo coordinate mode (#116): the world-space branch needs survey meta wired
# in — Renderer3D._meta was previously only ever assigned None, so the whole
# geo branch (grid/bbox/axis labels, ~120 lines) was dead code.
# ---------------------------------------------------------------------------

def _geo_meta(with_bin_grid: bool = True):
    from geoviz_seismic.models import BinGridGeometry, SeismicVolumeMeta

    return SeismicVolumeMeta(
        filename="test.sgy",
        n_inlines=8,
        n_crosslines=9,
        n_samples=10,
        sample_interval=4.0,
        iline_start=100,
        iline_step=2,
        xline_start=200,
        xline_step=2,
        dt_ms=4.0,
        bin_grid=(
            BinGridGeometry(
                x_origin=500000.0,
                y_origin=4400000.0,
                il_azimuth_deg=0.0,
                il_spacing_m=25.0,
                xl_spacing_m=50.0,
            )
            if with_bin_grid
            else None
        ),
    )


def _label_texts(widget):
    return [getattr(item, "text", "") for item in widget._axis_labels]


def test_renderer_3d_geo_coord_mode_uses_survey_meta(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    widget.load_volume(np.random.randn(8, 9, 10).astype(np.float32))

    widget.set_survey_meta(_geo_meta(with_bin_grid=True))
    widget.set_coord_mode("geo")

    assert widget._coord_mode == "geo"
    texts = _label_texts(widget)
    assert any("Easting" in t for t in texts)
    assert any("Northing" in t for t in texts)
    # Calibrated geo labels carry the real world extents, not placeholders.
    il_text = next(t for t in texts if "Easting" in t)
    assert "500000" in il_text

    meta = widget._meta
    x0, y0 = meta.il_xl_to_xy(meta.iline_start, meta.xline_start)
    x1, y1 = meta.il_xl_to_xy(
        meta.iline_start + 7 * meta.iline_step,
        meta.xline_start + 8 * meta.xline_step,
    )
    center = widget._view.opts["center"]
    assert center.x() == pytest.approx((x0 + x1) / 2.0)
    assert center.y() == pytest.approx((y0 + y1) / 2.0)


def test_renderer_3d_geo_coord_mode_falls_back_without_bin_grid(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    widget.load_volume(np.random.randn(8, 9, 10).astype(np.float32))

    # Meta without a bin grid (e.g. demo volume / uncalibrated survey).
    widget.set_survey_meta(_geo_meta(with_bin_grid=False))
    widget.set_coord_mode("geo")
    assert widget._coord_mode == "grid"
    texts = _label_texts(widget)
    assert any("Inline" in t for t in texts)
    assert not any("Easting" in t for t in texts)

    # No meta at all (old projects / standalone renderer).
    widget.set_survey_meta(None)
    widget.set_coord_mode("geo")
    assert widget._coord_mode == "grid"
    assert any("Inline" in t for t in _label_texts(widget))


def test_renderer_3d_set_survey_meta_reapplies_geo_mode(qtbot):
    """Switching to an uncalibrated survey while geo mode is active must
    explicitly fall back to grid instead of showing fabricated coordinates."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    widget.load_volume(np.random.randn(8, 9, 10).astype(np.float32))

    widget.set_survey_meta(_geo_meta(with_bin_grid=True))
    widget.set_coord_mode("geo")
    assert widget._coord_mode == "geo"

    # Re-sync with a meta lacking bin_grid (SEGY ready without calibration).
    widget.set_survey_meta(_geo_meta(with_bin_grid=False))
    assert widget._coord_mode == "grid"
    assert any("Inline" in t for t in _label_texts(widget))
