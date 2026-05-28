"""Tests for ScreenPathCache."""
import pytest
from PySide6.QtGui import QPainterPath


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
