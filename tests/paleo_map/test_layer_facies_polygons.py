from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


SAND_FEATURE = {
    "type": "Feature",
    "properties": {"name": "西部滨岸相", "facies": "砂岩"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
        ]],
    },
}

FAULTED_FEATURE = {
    "type": "Feature",
    "properties": {"name": "断裂带", "facies": "灰岩", "boundary_type": "fault"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [114.0, 22.0], [116.0, 22.0], [116.0, 24.0], [114.0, 24.0], [114.0, 22.0]
        ]],
    },
}


def _setup():
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    return img, vp, resolver


def test_polygon_renders_visible_pixels_in_viewport():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center pixel must be non-white (polygon covers full viewport)
    c = img.pixelColor(200, 200)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF)


def test_polygon_outside_viewport_culled():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # All pixels still white
    for y in range(0, 400, 20):
        for x in range(0, 400, 20):
            c = img.pixelColor(x, y)
            assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF


def test_hit_test_returns_facies_name_inside_polygon():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center of viewport falls inside the polygon (110..120, 20..30)
    hit = layer.hit_test_polygon(QPointF(200, 200), vp)
    assert hit == "砂岩"


def test_hit_test_miss_returns_none():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None


def test_skips_non_polygon_geometries():
    img, vp, resolver = _setup()
    point_feature = {
        "type": "Feature",
        "properties": {"name": "p", "facies": "砂岩"},
        "geometry": {"type": "Point", "coordinates": [115.0, 25.0]},
    }
    layer = FaciesPolygonsLayer([point_feature], resolver)
    # Should construct without error and paint as no-op
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None


def test_hierarchical_borders_painting():
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode
    img, vp, resolver = _setup()
    f1 = FaciesFeature(id="f1", facies_name="砂岩", display_name="f", level="facies", period="P", parent_id=None, geometry=SAND_FEATURE["geometry"])
    f2 = FaciesFeature(id="f2", facies_name="粉砂岩", display_name="sf", level="sub_facies", parent_id="f1", period="P", geometry=SAND_FEATURE["geometry"])
    hier = FaciesHierarchy(roots=[], by_id={"f1": FaciesNode(f1), "f2": FaciesNode(f2)})
    hier._by_id["f1"].children.append(hier._by_id["f2"])

    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level="sub_facies")
    assert "facies" in layer._level_quadtrees
    assert "sub_facies" in layer._level_quadtrees
    assert layer._level_quadtrees["facies"] is not None

    p = QPainter(img)
    layer.paint(p, vp)
    p.end()


def test_hierarchical_borders_levels():
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode
    img, vp, resolver = _setup()
    f1 = FaciesFeature(id="f1", facies_name="砂岩", display_name="f", level="facies", period="P", parent_id=None, geometry=SAND_FEATURE["geometry"])
    f2 = FaciesFeature(id="f2", facies_name="粉砂岩", display_name="sf", level="sub_facies", parent_id="f1", period="P", geometry=SAND_FEATURE["geometry"])
    f3 = FaciesFeature(id="f3", facies_name="细粉砂岩", display_name="mf", level="micro_facies", parent_id="f2", period="P", geometry=SAND_FEATURE["geometry"])
    hier = FaciesHierarchy(roots=[], by_id={"f1": FaciesNode(f1), "f2": FaciesNode(f2), "f3": FaciesNode(f3)})
    hier._by_id["f1"].children.append(hier._by_id["f2"])
    hier._by_id["f2"].children.append(hier._by_id["f3"])

    for lvl in ["facies", "sub_facies", "micro_facies"]:
        layer = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level=lvl)
        assert layer._level_quadtrees["facies"] is not None
        assert layer._level_quadtrees["sub_facies"] is not None
        assert layer._level_quadtrees["micro_facies"] is not None

        p = QPainter(img)
        layer.paint(p, vp)
        p.end()


def test_locked_borders_enforced_at_shallow_active_level():
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode
    img, vp, resolver = _setup()
    
    # We have parent f1 (facies) -> child f2 (sub_facies) -> grandchild f3 (micro_facies)
    f1 = FaciesFeature(id="f1", facies_name="砂岩", display_name="f", level="facies", period="P", parent_id=None, geometry=SAND_FEATURE["geometry"])
    f2 = FaciesFeature(id="f2", facies_name="粉砂岩", display_name="sf", level="sub_facies", parent_id="f1", period="P", geometry=SAND_FEATURE["geometry"])
    f3 = FaciesFeature(id="f3", facies_name="细粉砂岩", display_name="mf", level="micro_facies", parent_id="f2", period="P", geometry=SAND_FEATURE["geometry"])
    
    hier = FaciesHierarchy(roots=[FaciesNode(f1)], by_id={"f1": FaciesNode(f1), "f2": FaciesNode(f2), "f3": FaciesNode(f3)})
    hier._by_id["f1"].children.append(hier._by_id["f2"])
    hier._by_id["f2"].children.append(hier._by_id["f3"])

    class MockPainter:
        def __init__(self):
            self.drawn_pens = []
            self.current_pen = None
            self._render_hints = {}
        def setRenderHint(self, hint, on):
            self._render_hints[hint] = on
        def save(self): pass
        def translate(self, x, y): pass
        def scale(self, sx, sy): pass
        def restore(self): pass
        def setPen(self, pen):
            self.current_pen = pen
        def setBrush(self, brush): pass
        def drawPath(self, path):
            from PySide6.QtCore import Qt
            if self.current_pen is not None and self.current_pen.style() != Qt.PenStyle.NoPen:
                from PySide6.QtGui import QPen
                self.drawn_pens.append(QPen(self.current_pen))

    # Case 1: active_level is "facies", locked to "sub_facies"
    # We should paint "facies" and "sub_facies" borders, but NOT "micro_facies".
    layer1 = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level="facies", locked_ids={"f1": "sub_facies"})
    p1 = MockPainter()
    layer1.paint(p1, vp)
    
    widths1 = [pen.widthF() for pen in p1.drawn_pens]
    # facies: 2.0, sub_facies: 1.5, micro_facies: 1.0. Order of drawing is thinnest to thickest: ["sub_facies", "facies"]
    # So width list should contain 1.5 and 2.0. No 1.0 (micro_facies).
    assert 2.0 in widths1
    assert 1.5 in widths1
    assert 1.0 not in widths1

    # Case 2: active_level is "facies", locked to "micro_facies"
    # We should paint "facies", "sub_facies", and "micro_facies" borders.
    layer2 = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level="facies", locked_ids={"f1": "micro_facies"})
    p2 = MockPainter()
    layer2.paint(p2, vp)
    
    widths2 = [pen.widthF() for pen in p2.drawn_pens]
    assert 2.0 in widths2
    assert 1.5 in widths2
    assert 1.0 in widths2

    # Case 3: active_level is "facies", NOT locked.
    # We should paint ONLY "facies" borders (2.0).
    layer3 = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level="facies", locked_ids={})
    p3 = MockPainter()
    layer3.paint(p3, vp)
    
    widths3 = [pen.widthF() for pen in p3.drawn_pens]
    assert 2.0 in widths3
    assert 1.5 not in widths3
    assert 1.0 not in widths3


def test_locked_geometry_border_only_marks_facies_boundary_red():
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode
    img, vp, resolver = _setup()
    f1 = FaciesFeature(id="f1", facies_name="砂岩", display_name="f", level="facies", period="P", parent_id=None, geometry=SAND_FEATURE["geometry"])
    f2 = FaciesFeature(id="f2", facies_name="粉砂岩", display_name="sf", level="sub_facies", parent_id="f1", period="P", geometry=SAND_FEATURE["geometry"])
    f3 = FaciesFeature(id="f3", facies_name="细粉砂岩", display_name="mf", level="micro_facies", parent_id="f2", period="P", geometry=SAND_FEATURE["geometry"])
    hier = FaciesHierarchy(roots=[FaciesNode(f1)], by_id={"f1": FaciesNode(f1), "f2": FaciesNode(f2), "f3": FaciesNode(f3)})
    hier._by_id["f1"].children.append(hier._by_id["f2"])
    hier._by_id["f2"].children.append(hier._by_id["f3"])

    class MockPainter:
        def __init__(self):
            self.drawn_pens = []
            self.current_pen = None
            self._render_hints = {}
        def setRenderHint(self, hint, on):
            self._render_hints[hint] = on
        def save(self): pass
        def translate(self, x, y): pass
        def scale(self, sx, sy): pass
        def restore(self): pass
        def setPen(self, pen):
            self.current_pen = pen
        def setBrush(self, brush): pass
        def drawPath(self, path):
            from PySide6.QtCore import Qt
            if self.current_pen is not None and self.current_pen.style() != Qt.PenStyle.NoPen:
                from PySide6.QtGui import QPen
                self.drawn_pens.append(QPen(self.current_pen))

    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier, active_level="facies", locked_ids={"f1": "micro_facies"})
    painter = MockPainter()
    layer.paint(painter, vp)

    red_pens = [pen for pen in painter.drawn_pens if pen.color().red() > 180 and pen.color().green() < 80 and pen.color().blue() < 80]
    assert len(red_pens) == 1
    assert red_pens[0].widthF() > 2.0


def _make_mock_painter_cls():
    class MockPainter:
        def __init__(self):
            self.drawn_pens = []
            self.current_pen = None
            self._render_hints = {}
        def setRenderHint(self, hint, on):
            self._render_hints[hint] = on
        def save(self): pass
        def translate(self, x, y): pass
        def scale(self, sx, sy): pass
        def restore(self): pass
        def setPen(self, pen):
            self.current_pen = pen
        def setBrush(self, brush): pass
        def drawPath(self, path):
            from PySide6.QtCore import Qt
            if self.current_pen is not None and self.current_pen.style() != Qt.PenStyle.NoPen:
                from PySide6.QtGui import QPen
                self.drawn_pens.append(QPen(self.current_pen))
    return MockPainter


def _three_level_hier():
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode
    f1 = FaciesFeature(id="f1", facies_name="砂岩", display_name="f", level="facies", period="P", parent_id=None, geometry=SAND_FEATURE["geometry"])
    f2 = FaciesFeature(id="f2", facies_name="粉砂岩", display_name="sf", level="sub_facies", parent_id="f1", period="P", geometry=SAND_FEATURE["geometry"])
    f3 = FaciesFeature(id="f3", facies_name="细粉砂岩", display_name="mf", level="micro_facies", parent_id="f2", period="P", geometry=SAND_FEATURE["geometry"])
    hier = FaciesHierarchy(roots=[FaciesNode(f1)], by_id={"f1": FaciesNode(f1), "f2": FaciesNode(f2), "f3": FaciesNode(f3)})
    hier._by_id["f1"].children.append(hier._by_id["f2"])
    hier._by_id["f2"].children.append(hier._by_id["f3"])
    return hier


def _red_pens(painter):
    return [pen for pen in painter.drawn_pens
            if pen.color().red() > 180 and pen.color().green() < 80 and pen.color().blue() < 80]


def test_locked_sub_facies_boundary_marked_red(qtbot):
    """Locking a 亚相 feature must mark ITS boundary red+bold, not only 相."""
    img, vp, resolver = _setup()
    hier = _three_level_hier()
    # Display expanded to sub_facies, lock applied to the sub_facies feature f2.
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier,
                                active_level="sub_facies", locked_ids={"f2": "sub_facies"})
    MockPainter = _make_mock_painter_cls()
    painter = MockPainter()
    layer.paint(painter, vp)

    red = _red_pens(painter)
    assert len(red) == 1, "locked sub_facies boundary should be drawn red exactly once"
    assert red[0].widthF() > 2.0, "locked boundary should be bold"


def test_locked_micro_facies_boundary_marked_red(qtbot):
    """Locking a 微相 feature must mark ITS boundary red+bold."""
    img, vp, resolver = _setup()
    hier = _three_level_hier()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver, hierarchy=hier,
                                active_level="micro_facies", locked_ids={"f3": "micro_facies"})
    MockPainter = _make_mock_painter_cls()
    painter = MockPainter()
    layer.paint(painter, vp)

    red = _red_pens(painter)
    assert len(red) == 1, "locked micro_facies boundary should be drawn red exactly once"
    assert red[0].widthF() > 2.0





def test_vector_pattern_fill_pre_render_not_per_tile_playback(monkeypatch):
    """#505 lock: the tiled vector fill must paint via one cached pre-rendered
    QPixmap tile per (pattern, tile, dpr) — never replay the QPicture per
    visible tile cell (the old double loop cost 38k-150k play() calls per
    zoom tick at ordinary viewports)."""
    import time

    lake_feature = {
        "type": "Feature",
        "properties": {"name": "湖盆", "facies": "湖泊"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [105.0, 15.0], [125.0, 15.0], [125.0, 35.0], [105.0, 35.0], [105.0, 15.0]
            ]],
        },
    }
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    assert resolver.get_vector_pattern("湖泊") is not None

    import geoviz_paleo_map.layers.facies_polygons as fp_mod

    real_cache = fp_mod.QPixmapCache

    class CountingCache:
        renders = 0

        @staticmethod
        def find(key, pm):
            return real_cache.find(key, pm)

        @staticmethod
        def insert(key, pm):
            CountingCache.renders += 1
            return real_cache.insert(key, pm)

    monkeypatch.setattr(fp_mod, "QPixmapCache", CountingCache)

    layer = FaciesPolygonsLayer([lake_feature], resolver)
    t0 = time.perf_counter()
    for w, h in ((800, 600), (2400, 1600)):
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(0xFFFFFFFF)
        vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=w, height=h)
        p = QPainter(img)
        layer.paint(p, vp)
        p.end()
    dt = time.perf_counter() - t0

    # 9x the pixel area must not multiply the render count: exactly one
    # pre-render per distinct (pattern, tile, dpr) key, served from
    # QPixmapCache afterwards — never a replay per visible tile cell.
    assert CountingCache.renders <= 1, CountingCache.renders
    # Generous CI bound: both full paints together stay well under a
    # second (the per-tile loop measured 0.2-1 s per zoom tick alone).
    assert dt < 2.0, f"pattern fill paint took {dt:.2f}s for two frames"
