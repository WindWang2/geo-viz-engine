"""Tests for PaintScheduler, LayerPixmapCache, and ScreenPathCache."""
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class TestPaintScheduler:
    def test_coalesces_multiple_schedule_calls(self, qtbot):
        """Multiple schedule() calls before timer fires should produce one update."""
        from geoviz_paleo_map.paint_scheduler import PaintScheduler

        widget = QWidget()
        qtbot.addWidget(widget)
        widget.resize(100, 100)
        widget.show()

        update_count = 0
        original_update = widget.update

        def counting_update():
            nonlocal update_count
            update_count += 1
            original_update()

        widget.update = counting_update
        scheduler = PaintScheduler(widget)

        for _ in range(5):
            scheduler.schedule()

        qtbot.wait(50)
        assert update_count == 1

    def test_schedule_after_fire_allows_new_update(self, qtbot):
        """After timer fires, a new schedule() should work."""
        from geoviz_paleo_map.paint_scheduler import PaintScheduler

        widget = QWidget()
        qtbot.addWidget(widget)
        widget.resize(100, 100)
        widget.show()

        update_count = 0
        original_update = widget.update

        def counting_update():
            nonlocal update_count
            update_count += 1
            original_update()

        widget.update = counting_update
        scheduler = PaintScheduler(widget)

        scheduler.schedule()
        qtbot.wait(50)
        assert update_count == 1

        scheduler.schedule()
        qtbot.wait(50)
        assert update_count == 2


class TestLayerPixmapCache:
    def test_first_paint_renders_layer(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        class StubLayer:
            painted = False
            def paint(self, painter, viewport):
                self.painted = True

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        painter = QPainter(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)
        cache.paint(painter, vp)
        painter.end()
        assert layer.painted

    def test_second_paint_uses_cache(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

    def test_zoom_change_triggers_rerender(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp1 = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                               zoom=2.0, width=400, height=300)
        vp2 = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                               zoom=3.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp1)
        painter.end()

        painter = QPainter(widget)
        cache.paint(painter, vp2)
        painter.end()
        assert render_count == 2

    def test_viewport_grow_triggers_rerender(self, qtbot):
        """11.7-A: cache rendered for a small viewport must rebuild when the
        live viewport grows. Without this, _blit reads a small rect from the
        cached pixmap into the new larger canvas, compressing all data into
        the upper-left."""
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        cache = LayerPixmapCache(StubLayer())
        widget = QWidget()
        qtbot.addWidget(widget)
        vp_small = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                                    zoom=2.0, width=400, height=300)
        vp_large = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                                    zoom=2.0, width=1200, height=800)

        painter = QPainter(widget)
        cache.paint(painter, vp_small)
        painter.end()
        assert render_count == 1

        painter = QPainter(widget)
        cache.paint(painter, vp_large)
        painter.end()
        assert render_count == 2

    def test_mark_dirty_triggers_rerender(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)

        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

        cache.mark_dirty()
        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 2

    def test_pixmap_dpr_matches_painter_device(self, qtbot):
        """11.6-D: cached pixmap must carry the painter's devicePixelRatio
        so text/lines render at native HiDPI density instead of being
        upscaled (blurred) at blit time."""
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        class StubLayer:
            def paint(self, painter, viewport):
                pass

        cache = LayerPixmapCache(StubLayer())
        widget = QWidget()
        qtbot.addWidget(widget)

        painter = QPainter(widget)
        dpr = painter.device().devicePixelRatioF()
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)
        cache.paint(painter, vp)
        painter.end()

        assert cache._pixmap is not None
        assert cache._pixmap.devicePixelRatio() == pytest.approx(dpr)
        # Physical pixel dimensions = logical * dpr
        assert cache._pixmap.width() == int(round(400 * 2 * dpr))
        assert cache._pixmap.height() == int(round(300 * 2 * dpr))

    def test_dpr_change_triggers_rerender(self, qtbot):
        """If the painter device's DPR changes (e.g. window moves to a
        different monitor), the cache must rebuild to keep text sharp."""
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        cache = LayerPixmapCache(StubLayer())
        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0,
                              zoom=2.0, width=400, height=300)

        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 1

        # Simulate DPR change by mutating the recorded value
        cache._dpr = cache._dpr + 1.0
        painter = QPainter(widget)
        cache.paint(painter, vp)
        painter.end()
        assert render_count == 2


class TestScreenPathCache:
    def test_returns_screen_space_path(self, qtbot):
        """Cached path should be in screen coordinates, not world."""
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.lineTo(0, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        screen_path = cache.get_or_build("f1", world_path, vp)

        bounds = screen_path.boundingRect()
        assert bounds.width() > 0
        assert bounds.height() > 0
        # The path should be roughly centered around (200, 150)
        assert 180 < bounds.center().x() < 220
        assert 140 < bounds.center().y() < 170

    def test_cache_hit_returns_same_object(self, qtbot):
        """Same zoom + feature_id should return cached path (same object)."""
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp)
        p2 = cache.get_or_build("f1", world_path, vp)
        assert p1 is p2

    def test_dirty_feature_rebuilds_path(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                              zoom=2.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp)

        cache.mark_dirty("f1")
        p2 = cache.get_or_build("f1", world_path, vp)
        assert p1 is not p2

    def test_zoom_change_builds_new_path(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        vp1 = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                               zoom=2.0, width=400, height=300)
        vp2 = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                               zoom=3.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp1)
        p2 = cache.get_or_build("f1", world_path, vp2)
        assert p1 is not p2

    def test_pan_invalidates_screen_path(self, qtbot):
        """11.7-B: panning (center change at same zoom) must rebuild the
        cached screen path. Otherwise FaciesPolygons paint at the previous
        center while RegionLabels (which transform live each frame) paint
        at the new center — visible as labels drifting off their polygons."""
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache()
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.lineTo(0, 10)
        world_path.closeSubpath()

        vp1 = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                               zoom=2.0, width=400, height=300)
        vp2 = PaleoMapViewport(center_lng=8.0, center_lat=5.0,
                               zoom=2.0, width=400, height=300)
        p1 = cache.get_or_build("f1", world_path, vp1)
        p2 = cache.get_or_build("f1", world_path, vp2)

        # Different center → screen positions must differ
        assert p1.boundingRect().center().x() != pytest.approx(
            p2.boundingRect().center().x())

    def test_eviction_limits_zoom_levels(self, qtbot):
        from geoviz_paleo_map.screen_path_cache import ScreenPathCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        cache = ScreenPathCache(max_levels=2)
        world_path = QPainterPath()
        world_path.moveTo(0, 0)
        world_path.lineTo(10, 0)
        world_path.lineTo(10, 10)
        world_path.closeSubpath()

        for zoom in [1.0, 1.5, 2.0, 2.5]:
            vp = PaleoMapViewport(center_lng=5.0, center_lat=5.0,
                                  zoom=zoom, width=400, height=300)
            cache.get_or_build("f1", world_path, vp)

        # Should only have 2 zoom levels worth of entries
        zooms = set(k[0] for k in cache._cache)
        assert len(zooms) <= 2


class TestLayerPixmapCacheVisibility:
    def test_hidden_layer_not_blitted_and_reshow_rerenders(self, qtbot):
        from geoviz_paleo_map.paint_scheduler import LayerPixmapCache
        from geoviz_paleo_map.viewport import PaleoMapViewport

        render_count = 0

        class StubLayer:
            visible = True

            def paint(self, painter, viewport):
                nonlocal render_count
                render_count += 1

        layer = StubLayer()
        cache = LayerPixmapCache(layer)
        widget = QWidget()
        qtbot.addWidget(widget)
        vp = PaleoMapViewport(
            center_lng=115.0, center_lat=30.0, zoom=2.0, width=400, height=300
        )

        cache.paint(QPainter(widget), vp)
        assert render_count == 1
        assert cache._pixmap is not None

        # Hiding the layer must clear the stale pixmap: a subsequent pan-blit
        # would otherwise keep the layer on screen (#546).
        layer.visible = False
        cache.paint(QPainter(widget), vp)
        assert render_count == 1
        assert cache._pixmap is None

        # Re-showing forces a fresh render (not a blit of nothing).
        layer.visible = True
        cache.paint(QPainter(widget), vp)
        assert render_count == 2
