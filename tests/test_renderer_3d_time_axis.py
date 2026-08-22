"""Seismic 3D time-axis direction tests (time-down convention).

The 2D profile panels draw sample-0 at the top (industry standard). The 3D
orthogonal slice walls must match: sample-0 at world Z top, time increasing
downward. Regression tests for the seismic-axis-flip fix.
"""

import numpy as np
import pytest
from PySide6.QtGui import QVector3D


NT, ST = 12, 2.0  # small volume time samples / sample spacing


@pytest.fixture
def loaded_renderer(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(8, 9, NT).astype(np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, ST))
    return widget


# ---------------------------------------------------------------------------
# Pure coordinate mapping helpers
# ---------------------------------------------------------------------------

def test_sample_to_z_sample0_at_top():
    from geoviz_seismic.renderer_3d import sample_to_z

    assert sample_to_z(0, NT, ST) == pytest.approx(NT * ST)


def test_compute_balanced_spacing_maps_each_axis_to_target():
    from geoviz_seismic.renderer_3d import compute_balanced_spacing

    si, sx, st = compute_balanced_spacing((10, 20, 40), target=200.0)
    assert (si * 10, sx * 20, st * 40) == pytest.approx((200.0, 200.0, 200.0))


def test_sample_to_z_last_sample_near_bottom():
    from geoviz_seismic.renderer_3d import sample_to_z

    assert sample_to_z(NT - 1, NT, ST) == pytest.approx(ST)


def test_sample_to_z_monotonically_decreasing():
    from geoviz_seismic.renderer_3d import sample_to_z

    zs = [sample_to_z(s, NT, ST) for s in range(NT)]
    assert all(z_hi > z_lo for z_hi, z_lo in zip(zs, zs[1:]))


def test_z_to_sample_round_trip():
    from geoviz_seismic.renderer_3d import sample_to_z, z_to_sample

    for s in range(NT):
        assert z_to_sample(sample_to_z(s, NT, ST), NT, ST) == pytest.approx(s)


# ---------------------------------------------------------------------------
# Behavioural: renderer items follow the time-down convention
# ---------------------------------------------------------------------------

def _map_point(item, x, y, z=0.0):
    return item.transform().map(QVector3D(x, y, z))


def test_volume_visual_sample0_at_box_top(loaded_renderer):
    """Volume-render brick must occupy the same time-down box as slice planes."""
    from geoviz_seismic.renderer_3d import sample_to_z

    widget = loaded_renderer
    vis = widget._volume_visual
    assert vis is not None
    matrix = vis.transform()
    origin = matrix.map(QVector3D(0, 0, 0))
    far = matrix.map(QVector3D(0, 0, vis.data.shape[2]))
    assert origin.z() == pytest.approx(sample_to_z(0, NT, ST))
    assert far.z() == pytest.approx(0.0)
    assert origin.z() > far.z()


def test_time_plane_translated_to_mirrored_height(loaded_renderer):
    widget = loaded_renderer
    position = int(widget._active_time_pos)
    expected_z = (NT - position) * ST
    matrix = widget._img_t.transform()
    assert matrix.map(QVector3D(0, 0, 0)).z() == pytest.approx(expected_z)


def test_inline_wall_texture_top_is_late_world_z_bottom(loaded_renderer):
    """Inline wall: texture row 0 (sample-0) must land at world Z top."""
    widget = loaded_renderer
    img = widget._img_il
    il_si = widget._il_pos * 1.0

    origin = _map_point(img, 0, 0)          # texture corner (col=0, row=0)
    bottom = _map_point(img, 0, NT)         # last time sample

    assert origin.x() == pytest.approx(il_si)
    assert origin.z() == pytest.approx(NT * ST)   # sample-0 at top
    assert bottom.z() == pytest.approx(0.0)       # max time at bottom
    # Wall occupies the full vertical extent of the box
    assert origin.y() == pytest.approx(bottom.y())


def test_crossline_wall_texture_top_is_late_world_z_bottom(loaded_renderer):
    """Crossline wall: same time-down convention as inline wall."""
    widget = loaded_renderer
    img = widget._img_xl
    xl_sx = widget._xl_pos * 1.0

    origin = _map_point(img, 0, 0)
    bottom = _map_point(img, 0, NT)

    assert origin.y() == pytest.approx(xl_sx)
    assert origin.z() == pytest.approx(NT * ST)
    assert bottom.z() == pytest.approx(0.0)


def test_inline_border_follows_flipped_wall(loaded_renderer):
    """Border polyline must hug the flipped wall corners."""
    widget = loaded_renderer
    line = widget._line_il
    # Border vertices live in the geometry (pos); the item transform carries
    # the inline offset. Rendered corner = transform ∘ vertex.
    v0 = line.pos[0]
    pts = line.transform().map(QVector3D(float(v0[0]), float(v0[1]), float(v0[2])))

    assert pts.z() == pytest.approx(NT * ST)
    assert pts.x() == pytest.approx(widget._il_pos * 1.0)


def test_cursor_position_uses_time_down_mapping(qtbot, loaded_renderer):
    from geoviz_seismic.renderer_3d import sample_to_z

    widget = loaded_renderer
    t_idx = NT - 1  # deepest sample -> near bottom of box
    widget.set_cursor_position(1.0, 2.0, float(t_idx))
    pos = widget._cursor_sphere.pos[0]
    assert pos[2] == pytest.approx(sample_to_z(t_idx, NT, ST))


def test_ray_cast_inverse_round_trips_time_index(loaded_renderer):
    from geoviz_seismic.renderer_3d import sample_to_z, z_to_sample

    widget = loaded_renderer
    nt = widget._volume_data_cpu.shape[2]
    st = widget._volume_spacing[2]
    for t in (0.0, 5.5, float(nt - 1)):
        z = sample_to_z(t, nt, st)
        assert widget._z_to_sample_index(z) == pytest.approx(t)


def test_horizon_picks_use_time_down_mapping(qtbot, loaded_renderer):
    from geoviz_seismic.renderer_3d import sample_to_z

    widget = loaded_renderer
    widget.set_horizon_picks([(2.0, 3.0, 4.0)])
    pos = widget._picks_visual.pos[0]
    assert pos[2] == pytest.approx(sample_to_z(4.0, NT, ST))


def test_add_horizon_ms_uses_time_down_mapping(qtbot):
    """TWT-ms horizon must land mirrored: 200ms of a 200-sample cube
    (sample 50) sits at (nt-50)*st from the bottom, NOT at 50*st."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((40, 50, 200), dtype=np.float32)
    widget.load_volume(data, spacing=(5.0, 4.0, 1.0))
    widget.set_survey_mapping(t0_ms=0.0, dt_ms=4.0, ds_factor=(1, 1, 1))

    grid_ms = np.full((40, 50), 200.0, dtype=np.float32)  # sample 50 of 200
    widget.add_horizon(grid_ms, name="h", z_unit="ms")
    verts = np.asarray(widget._horizons["h"].opts["meshdata"].vertexes())
    st = widget._volume_spacing[2]
    assert np.allclose(verts[:, 2], (200 - 50) * st, atol=1e-4)


def test_slice_planes_use_smooth_filtering(qtbot):
    """The three orthogonal walls must use bilinear texture filtering —
    nearest-neighbour on a ~5x4x6 downsampled preview looks blocky."""
    widget = loaded_renderer_factory(qtbot)

    assert widget._img_il.smooth is True
    assert widget._img_xl.smooth is True
    for image, _line in widget._time_plane_items.values():
        assert image.smooth is True


def loaded_renderer_factory(qtbot):
    import geoviz_seismic.renderer_3d as m
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(8, 9, NT).astype(np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, ST))
    return widget


def test_default_camera_reads_walls_like_panels(qtbot):
    """Default view must sit in the azimuth quadrant where BOTH orthogonal
    walls read left-to-right like their 2D panels (the +X/-Y corner,
    azimuth ≈ -45), otherwise the crossline wall appears mirrored."""
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(8, 9, NT).astype(np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, ST))

    az = float(widget._view.opts["azimuth"]) % 360
    assert 290 <= az <= 340, f"default azimuth {az} not in the panel-like quadrant"
    assert abs(float(widget._view.opts["elevation"])) > 5


def test_time_axis_ticks_run_top_down(loaded_renderer):
    """Tick labelled '0' must sit at the top of the time axis."""
    from pyqtgraph.opengl import GLTextItem

    widget = loaded_renderer
    texts = [
        item for item in widget._axis_labels
        if isinstance(item, GLTextItem)
    ]
    zero_ticks = [
        item for item in texts
        if item.text == "0"
        and item.pos[0] < 0 and item.pos[1] < 0  # time-tick corner offset
    ]
    assert zero_ticks, "no time tick '0' found among axis labels"
    assert float(zero_ticks[0].pos[2]) == pytest.approx(NT * ST)


def test_time_axis_ticks_show_milliseconds(qtbot):
    """With a survey mapping, Z ticks must read TWT ms (t0 + s*ft*dt),
    matching the 2D panels' 'Time (ms)' axis — not raw sample indices."""
    from pyqtgraph.opengl import GLTextItem

    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((4, 4, NT), dtype=np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, ST))
    widget.set_survey_mapping(t0_ms=100.0, dt_ms=4.0, ds_factor=(1, 1, 6))
    ni, nx, nt = data.shape
    widget._create_axis_labels(ni, nx, nt, (1.0, 1.0, ST))

    tick_texts = [
        item.text for item in widget._axis_labels
        if isinstance(item, GLTextItem)
        and item.pos[0] < 0 and item.pos[1] < 0
    ]
    assert tick_texts, "no time tick labels created"
    # sample 0 -> t0 = 100 ms must appear; raw sample indices must not
    assert "100" in tick_texts
    assert "0" not in tick_texts


def test_time_axis_endpoint_label_shows_ms_range(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.zeros((4, 4, NT), dtype=np.float32)
    widget.load_volume(data, spacing=(1.0, 1.0, ST))
    widget.set_survey_mapping(t0_ms=100.0, dt_ms=4.0, ds_factor=(1, 1, 6))
    widget._create_axis_labels(4, 4, NT, (1.0, 1.0, ST))

    from pyqtgraph.opengl import GLTextItem
    labels = [it.text for it in widget._axis_labels if isinstance(it, GLTextItem)]
    # last preview sample s=11 -> 100 + 11*6*4 = 364 ms
    assert any("ms" in t for t in labels), f"no ms endpoint label in {labels}"
    assert any("364" in t for t in labels)


def test_panel_slice_info_full_res_time_axis_is_native_twt(qtbot):
    """SEGY 2D panels are native resolution (one row = one sample).

    Multiplying TWT by the 3D preview stride ft stretched 1800 ms to
    10800 ms on 200P (Image #1: 2D 0–10800 vs 3D T=900 mid of 1800 ms).
    """
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    data = np.zeros((8, 8, 16), dtype=np.float32)
    view.load_demo(data)
    view._meta.n_samples = 901
    view._meta.dt_ms = 2.0
    view._meta.t0_ms = 0.0
    view._ds_factor = (5, 4, 6)  # 3D preview stride, must NOT scale 2D full-res

    info = view._build_slice_info("inline", 4485, (901, 411))
    assert info.axis_v_label == "Time (ms)"
    assert len(info.axis_v_values) == 901
    assert info.axis_v_values[0] == pytest.approx(0.0)
    assert info.axis_v_values[1] == pytest.approx(2.0)
    assert info.axis_v_values[-1] == pytest.approx(1800.0)


def test_panel_slice_info_preview_rows_scale_by_downsample(qtbot):
    """Preview-shaped panels (n_rows != native n_samples): row r is
    TWT = t0 + r*ft*dt_ms so the axis still spans the full survey."""
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    data = np.zeros((80, 80, 250), dtype=np.float32)
    view.load_demo(data)
    view._meta.n_samples = 250 * 6  # native sample count
    view._meta.dt_ms = 4.0
    view._meta.t0_ms = 0.0
    view._ds_factor = (1, 1, 6)

    info = view._build_slice_info("inline", 40, (250, 80))  # preview rows
    assert info.axis_v_label == "Time (ms)"
    assert len(info.axis_v_values) == 250
    assert info.axis_v_values[1] == pytest.approx(6 * 4.0)
    assert info.axis_v_values[-1] == pytest.approx(249 * 6 * 4.0)


def _gl_read_r8_with_alignment(packed, width, height, alignment):
    """Replicate glTexImage2D row start for a tightly packed R8 buffer."""
    stride = (width + alignment - 1) // alignment * alignment
    buf = np.ascontiguousarray(packed).reshape(-1)
    out = np.zeros((height, width), dtype=packed.dtype)
    for y in range(height):
        start = y * stride
        end = start + width
        if end <= buf.size:
            out[y] = buf[start:end]
        elif start < buf.size:
            n = buf.size - start
            out[y, :n] = buf[start:]
    return out


def test_r8_time_plane_width_shears_under_gl_align4():
    """3D and 2D time slices are the same array (corr=1 when strided).

    Image #2's diagonal stripes are GL reading the 129-wide R8 upload with
    default UNPACK_ALIGNMENT=4. RGBA uploads are immune (4 bytes/pixel).
    """
    from geoviz_seismic.renderer_3d import GLImageLutItem

    rng = np.random.default_rng(0)
    idx = rng.integers(0, 256, (129, 103), dtype=np.uint8)  # 200P time-plane shape
    upload, width, height = GLImageLutItem.prepare_r8_upload(idx)
    assert (width, height) == (129, 103)
    assert width % 4 == 1

    sheared = _gl_read_r8_with_alignment(upload, width, height, alignment=4)
    tight = _gl_read_r8_with_alignment(upload, width, height, alignment=1)
    c_bad = float(np.corrcoef(sheared.ravel().astype(float), upload.ravel().astype(float))[0, 1])
    c_ok = float(np.corrcoef(tight.ravel().astype(float), upload.ravel().astype(float))[0, 1])
    assert c_bad < 0.2
    assert c_ok == pytest.approx(1.0)

    import inspect
    src = inspect.getsource(GLImageLutItem._uploadIndexTexture)
    assert "GL_UNPACK_ALIGNMENT" in src, (
        "R8 upload must set GL_UNPACK_ALIGNMENT=1 or 129-wide time planes stripe"
    )
