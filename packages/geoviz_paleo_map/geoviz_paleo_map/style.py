"""FaciesStyleResolver — facies name → base color + composite brush.

Caches per facies name; multiple polygons of the same facies share one
FaciesStyle instance, and the underlying composite brush is cached inside
PatternEngine itself.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

from geoviz_well_log.renderer.pattern_engine import PatternEngine

from geoviz_paleo_map.models import FaciesStyle, VectorPattern


DEFAULT_BASE_COLOR = QColor("#d9d4c8")

FACIES_PATTERNS = {
    # 1. Continental (陆相)
    "冲积扇": "alluvial_fan",
    "洪积扇": "alluvial_fan",
    "扇根": "alluvial_fan",
    "扇中": "alluvial_fan",
    "扇缘": "alluvial_fan",
    "泥石流": "alluvial_fan",
    "片流沉积": "alluvial_fan",
    "河流": "fluvial",
    "河流相": "fluvial",
    "分流河道": "fluvial",
    "辫状河道": "fluvial",
    "天然堤": "fluvial",
    "湖泊": "lacustrine",
    "湖泊相": "lacustrine",
    "盐湖": "lacustrine",
    "滨湖": "lacustrine",
    "浅湖": "lacustrine",
    "半深湖": "lacustrine",
    "深湖": "lacustrine",
    "湖底泥": "lacustrine",
    "沼泽": "swamp",
    "沙漠": "desert",
    "沙漠相": "desert",

    # 2. Transitional (海陆过渡相)
    "三角洲": "delta",
    "三角洲前缘": "delta",
    "三角洲平原": "delta",
    "前三角洲": "delta",
    "河口湾": "estuary",
    "潟湖": "lagoon",
    "半咸水潟湖": "lagoon",
    "超咸水潟湖": "lagoon",
    "障壁岛": "barrier_island",
    "潮坪": "tidal_flat",
    "泥坪": "tidal_flat",
    "混合坪": "tidal_flat",
    "砂坪": "tidal_flat",
    "潮汐水道": "tidal_flat",
    "潮汐砂脊": "tidal_flat",
    "潮沟": "tidal_flat",
    "潮道": "tidal_flat",
    "泥裂": "tidal_flat",
    "藻席": "tidal_flat",

    # 3. Marine (海相)
    "滨岸": "shoreface",
    "前滨": "shoreface",
    "临滨": "shoreface",
    "后滨": "shoreface",
    "沿岸坝": "shoreface",
    "海滩砂": "shoreface",
    "冲越扇": "shoreface",
    "浅海": "shallow_marine",
    "浅海相": "shallow_marine",
    "陆棚": "shelf",
    "泥质陆棚": "shelf",
    "砂质陆棚": "shelf",
    "砂泥质陆棚": "shelf",
    "混积浅水陆棚": "shelf",
    "陆棚泥": "shelf",
    "陆棚砂": "shelf",
    "风暴沉积": "shelf",
    "半深海": "deep_marine",
    "海底扇": "deep_marine",
    "浊积岩": "deep_marine",
    "等深积岩": "deep_marine",
    "碎屑流": "deep_marine",
    "深海": "abyssal",
    "深海相": "abyssal",
    "深水盆地": "abyssal",
    "深海平原": "abyssal",
    "深海泥": "abyssal",

    # 4. Carbonate Platform (碳酸盐台地)
    "碳酸盐台地": "carbonate_platform",
    "开阔台地": "carbonate_platform",
    "局限台地": "carbonate_platform",
    "台地边缘": "carbonate_platform",
    "生物礁": "carbonate_platform",
    "礁": "carbonate_platform",
    "粒屑滩": "carbonate_platform",

    # 5. Evaporites (蒸发岩类)
    "蒸发岩": "evaporite",
    "蒸发盐": "evaporite",
}


class FaciesStyleResolver:
    def __init__(self, pattern_engine: PatternEngine):
        self._engine = pattern_engine
        self._cache: dict[str, FaciesStyle] = {}

    def resolve(self, facies_name: str) -> FaciesStyle:
        if facies_name in self._cache:
            return self._cache[facies_name]
        base = self._engine.get_color_fuzzy(facies_name) or QColor(DEFAULT_BASE_COLOR)
        
        # Exact match or fuzzy fallback mapping lookup
        pattern_id = FACIES_PATTERNS.get(facies_name)
        if pattern_id is None:
            sorted_keys = sorted(FACIES_PATTERNS.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k in facies_name:
                    pattern_id = FACIES_PATTERNS[k]
                    break
                    
        if pattern_id is not None:
            brush = self._engine.get_facies_brush(pattern_id, base)
            if brush is None:
                brush = self._engine.get_composite_brush(facies_name, base)
            if brush is None:
                brush = QBrush(base)
        else:
            brush = self._engine.get_composite_brush(facies_name, base)
            if brush is None:
                brush = QBrush(base)
        style = FaciesStyle(base_color=base, brush=brush, pattern_id=pattern_id)
        self._cache[facies_name] = style
        return style

    def get_adaptive_brush(self, facies_name: str, scale: float) -> QBrush:
        """Return a QBrush with transformed pattern size based on viewport scale.
        Grains scale slower than the map (sqrt of scale) to maintain readability.
        """
        import math
        from PySide6.QtGui import QTransform
        style = self.resolve(facies_name)
        if style.brush.style() == Qt.BrushStyle.SolidPattern:
            return style.brush

        brush = QBrush(style.brush)
        # Adaptive scaling: grains scale by sqrt(scale)
        # If scale=4 (zoomed in), grains are 2x larger than base.
        # If scale=0.25 (zoomed out), grains are 0.5x smaller than base.
        grain_scale = math.sqrt(max(1e-6, scale))
        t = QTransform()
        t.scale(grain_scale, grain_scale)
        brush.setTransform(t)
        return brush

    def get_vector_pattern(self, facies_name: str) -> VectorPattern | None:
        """Return a VectorPattern for crisp vector tiling, or None if no pattern."""
        style = self.resolve(facies_name)
        if style.pattern_id is None:
            return None
        picture = self._engine.get_picture(style.pattern_id)
        if picture is None:
            return None
        return VectorPattern(
            picture=picture,
            base_color=style.base_color,
            alpha=0.4,
            tile_size=float(self._engine._tile_size),
        )



def boundary_pen(kind: str | None) -> QPen:
    """Return the QPen for a polygon boundary type."""
    if kind == "inferred":
        pen = QPen(QColor("#555555"), 1.5)
        pen.setDashPattern([6.0, 3.0])
        return pen
    if kind == "fault":
        return QPen(QColor("#e53e3e"), 2.0)
    if kind == "confirmed":
        return QPen(QColor("#555555"), 1.5)
    return QPen(QColor("#555555"), 1.0)
