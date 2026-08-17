"""#580: slow-marker policy — hardware-free gates stay in the fast job."""

from tests.conftest import is_slow_test


def test_shader_lut_source_gate_is_not_slow():
    assert not is_slow_test(
        "test_renderer_3d",
        "test_gl_image_lut_item_shader_has_lut_lookup_and_compiles",
    )


def test_shader_compiler_source_tests_are_not_slow():
    assert not is_slow_test(
        "test_renderer_3d",
        "test_dual_gl_volume_item_uses_pyopengl_compiler_and_clean_gles3_source",
    )
    assert not is_slow_test(
        "test_renderer_3d",
        "test_gl_image_lut_item_legacy_shader_uses_texture2d",
    )


def test_numpy_sculpting_is_not_slow():
    assert not is_slow_test("test_seismic_3d_sculpting", "test_gaussian_sculpting_math")
    assert not is_slow_test("test_seismic_3d_sculpting", "test_interactive_horizon_gl_item")


def test_per_axis_renderer_tests_are_not_slow():
    assert not is_slow_test(
        "test_renderer_3d_per_axis",
        "test_update_slice_planes_for_only_replaces_changed_axis",
    )


def test_well_log_visual_parity_is_not_slow():
    assert not is_slow_test("test_visual_parity_perf", "test_track_build_speed")
    assert not is_slow_test("test_visual_parity_curve", "test_curve_track_pixels")


def test_gl_webengine_golden_modules_are_slow():
    assert is_slow_test("test_renderer_3d", "test_renderer_3d_init")
    assert is_slow_test("test_chart_engine", "test_chart_engine_creates_webengine")
    assert is_slow_test("test_map_visual_parity", "test_map_canvas_matches_golden")
    assert is_slow_test("test_paleo_map_visual_parity", "test_paleo_map_matches_golden")


def test_chart_engine_js_queue_module_is_not_slow():
    assert not is_slow_test(
        "test_chart_engine_js_queue",
        "test_render_data_queues_js_until_web_ready",
    )
    assert not is_slow_test(
        "test_chart_engine_js_queue",
        "test_export_svg_queues_until_web_ready",
    )
