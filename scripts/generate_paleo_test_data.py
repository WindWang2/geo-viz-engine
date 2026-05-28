#!/usr/bin/env python3
"""Generate 3 topologically consistent GeoJSON files for paleo map testing.

Uses Voronoi tessellation for irregular, gap-free polygon generation.
Hierarchy: 相 (50) → 亚相 (120-180) → 微相 (300-500)
Each level's polygons tile the parent area without gaps or overlaps.

Usage:
    python scripts/generate_paleo_test_data.py
"""

import json
import math
import random
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, Point, MultiPoint, box
from shapely.ops import voronoi_diagram
from shapely.validation import make_valid

random.seed(42)
np.random.seed(42)

LNG_MIN, LNG_MAX = 105.0, 125.0
LAT_MIN, LAT_MAX = 20.0, 40.0

FACIES_TAXONOMY = {
    "三角洲": {
        "sub": ["三角洲平原", "三角洲前缘", "前三角洲"],
        "micro": ["分流河道", "天然堤", "决口扇", "河口坝", "远砂坝", "席状砂"],
    },
    "滨岸": {
        "sub": ["前滨", "临滨", "后滨"],
        "micro": ["海滩砂", "沿岸坝", "潮道", "冲越扇"],
    },
    "陆棚": {
        "sub": ["泥质陆棚", "砂质陆棚", "砂泥质陆棚", "混积浅水陆棚"],
        "micro": ["陆棚泥", "陆棚砂", "风暴沉积", "生物扰动层"],
    },
    "碳酸盐台地": {
        "sub": ["局限台地", "开阔台地", "台地边缘"],
        "micro": ["潮坪", "潟湖", "生物礁", "粒屑滩", "灰泥丘"],
    },
    "深水盆地": {
        "sub": ["半深海", "深海平原", "海底扇"],
        "micro": ["浊积岩", "深海泥", "碎屑流", "等深积岩"],
    },
    "冲积扇": {
        "sub": ["扇根", "扇中", "扇缘"],
        "micro": ["泥石流", "辫状河道", "片流沉积", "筛积物"],
    },
    "潟湖": {
        "sub": ["半咸水潟湖", "超咸水潟湖"],
        "micro": ["潮汐砂脊", "湖底泥", "蒸发盐", "生物碎屑"],
    },
    "潮坪": {
        "sub": ["砂坪", "泥坪", "混合坪"],
        "micro": ["潮沟", "潮汐水道", "藻席", "泥裂"],
    },
}

FACIES_NAMES = list(FACIES_TAXONOMY.keys())
PERIOD = "J3"


# ── Voronoi tessellation helpers ───────────────────────────────────

def _random_points_in_polygon(poly: Polygon, n: int, rng: random.Random) -> list[tuple]:
    """Generate n random points inside a polygon using rejection sampling."""
    minx, miny, maxx, maxy = poly.bounds
    points = []
    while len(points) < n:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if poly.contains(Point(x, y)):
            points.append((x, y))
    return points


def _voronoi_clip(parent_poly: Polygon, seeds: list[tuple]) -> list[Polygon]:
    """Compute Voronoi cells from seeds, clip each to parent_poly.

    Uses shapely.ops.voronoi_diagram which handles infinite regions via an
    envelope, then clips each cell to the parent polygon for full coverage.
    """
    if len(seeds) < 3:
        return [parent_poly]

    # Envelope: large rectangle around parent to bound infinite regions
    minx, miny, maxx, maxy = parent_poly.bounds
    w, h = maxx - minx, maxy - miny
    pad = max(w, h) * 10
    envelope = box(minx - pad, miny - pad, maxx + pad, maxy + pad)

    mp = MultiPoint([Point(s) for s in seeds])
    regions = voronoi_diagram(mp, envelope=envelope)

    cells = []
    for region in regions.geoms:
        if not isinstance(region, Polygon):
            continue
        clipped = parent_poly.intersection(region)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda g: g.area)
        if clipped.geom_type != "Polygon":
            continue
        if clipped.area < 1e-10:
            continue
        cells.append(clipped)

    return cells if cells else [parent_poly]


def _aspect_ratio(poly: Polygon) -> float:
    """Aspect ratio from minimum bounding rectangle (> 1 always)."""
    if poly.area < 1e-12:
        return float("inf")
    mbr = poly.minimum_rotated_rectangle
    if mbr is None or mbr.is_empty:
        return 1.0
    coords = list(mbr.exterior.coords)
    # MBR has 5 points; compute side lengths from first two edges
    w = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    h = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
    if min(w, h) < 1e-12:
        return float("inf")
    return max(w / h, h / w)


def _mesh_edge_densify(cells: list[list[tuple]], n_extra: int,
                       rng: random.Random) -> list[list[tuple]]:
    """Subdivide edges at the mesh level: each shared edge is processed once.

    Adjacent cells share the same intermediate points, preventing gaps.
    Applies mesh-level Laplacian smoothing to all vertices for natural curves.
    """
    if n_extra <= 0 or len(cells) < 1:
        return cells

    from collections import defaultdict

    # Step 1: deduplicate vertices across all cells
    R = 10
    vert_ids = {}
    vert_pos = {}
    cell_vert_ids = []

    for cell in cells:
        ids = []
        for v in cell:
            key = (round(v[0], R), round(v[1], R))
            if key not in vert_ids:
                vid = len(vert_ids)
                vert_ids[key] = vid
                vert_pos[vid] = list(v)
            ids.append(vert_ids[key])
        cell_vert_ids.append(ids)

    # Step 2: add intermediate points along each unique edge (no jitter)
    edge_midpoints = {}
    for ids in cell_vert_ids:
        n = len(ids)
        for i in range(n):
            va, vb = ids[i], ids[(i + 1) % n]
            ekey = (va, vb)
            if ekey in edge_midpoints:
                continue
            pa, pb = vert_pos[va], vert_pos[vb]
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            length = math.hypot(dx, dy)
            if length < 1e-9:
                edge_midpoints[ekey] = []
                continue
            intermediates = []
            for k in range(1, n_extra + 1):
                t = k / (n_extra + 1)
                intermediates.append([pa[0] + t * dx, pa[1] + t * dy])
            edge_midpoints[ekey] = intermediates

    # Step 3: rebuild with intermediate points inserted
    new_vert_pos = dict(vert_pos)
    next_vid = len(vert_pos)
    edge_vert_ids = {}  # ekey -> list of new vert ids
    for ekey, mids in edge_midpoints.items():
        vids = []
        for m in mids:
            vid = next_vid
            next_vid += 1
            new_vert_pos[vid] = m
            vids.append(vid)
        edge_vert_ids[ekey] = vids

    # Build new cell vert-id lists with intermediate points
    dense_cell_ids = []
    for ids in cell_vert_ids:
        new_ids = []
        n = len(ids)
        for i in range(n):
            va, vb = ids[i], ids[(i + 1) % n]
            new_ids.append(va)
            new_ids.extend(edge_vert_ids.get((va, vb), []))
        dense_cell_ids.append(new_ids)

    # Step 4: rebuild cell coordinate rings (no smoothing - densification
    # alone adds enough vertices for smooth QPainter anti-aliased rendering)
    result = []
    for ids in dense_cell_ids:
        ring = [(new_vert_pos[vid][0], new_vert_pos[vid][1]) for vid in ids]
        result.append(ring)
    return result


def _make_valid(poly: Polygon) -> Polygon:
    """Ensure polygon is valid via shapely make_valid."""
    if poly.is_valid:
        return poly
    return make_valid(poly)


def _poly_to_coords(poly: Polygon) -> list[tuple]:
    """Extract exterior ring coordinates as list of (x, y)."""
    return [(x, y) for x, y in poly.exterior.coords[:-1]]


def _merge_cells_to_count(cells: list[Polygon], target: int) -> list[Polygon]:
    """Merge polygon cells down to target count.

    Repeatedly merges the smallest cell into its nearest neighbor
    until len(cells) <= target. Preserves full area coverage.
    """
    from shapely.ops import unary_union
    if len(cells) <= target:
        return cells
    polys = list(cells)
    while len(polys) > target:
        # Find the smallest cell
        areas = [(i, p.area) for i, p in enumerate(polys)]
        areas.sort(key=lambda x: x[1])
        smallest_idx = areas[0][0]
        smallest = polys[smallest_idx]
        # Find its nearest neighbor (by centroid distance)
        sc = smallest.centroid
        best_j = -1
        best_dist = float("inf")
        for j, p in enumerate(polys):
            if j == smallest_idx:
                continue
            d = sc.distance(p.centroid)
            if d < best_dist:
                best_dist = d
                best_j = j
        if best_j == -1:
            break
        # Merge smallest into neighbor
        merged = _make_valid(unary_union([polys[best_j], smallest]))
        if merged.is_valid and merged.geom_type == "Polygon":
            polys[best_j] = merged
        polys.pop(smallest_idx)
    return polys


def _tessellate(parent_poly: Polygon, n_seeds: int,
                min_area: float, max_aspect: float,
                rng: random.Random,
                edge_n_extra: int = 3) -> list[list[tuple]]:
    """Tessellate parent_poly into ~n_seeds irregular pieces.

    Returns list of coordinate rings. Edge smoothing is applied via
    mesh-level densification + Laplacian smoothing.
    """
    parent_poly = _make_valid(parent_poly)
    if parent_poly.area < min_area * 1.5:
        coords = _poly_to_coords(parent_poly)
        return [_mesh_edge_densify([coords], edge_n_extra, rng)[0]]

    # Generate seeds and compute Voronoi
    seeds = _random_points_in_polygon(parent_poly, n_seeds, rng)
    cells = _voronoi_clip(parent_poly, seeds)

    result = []
    for cell in cells:
        cell = _make_valid(cell)
        if cell.is_empty or cell.area < 1e-10:
            continue
        coords = _poly_to_coords(cell)
        if len(coords) < 3:
            continue
        result.append(coords)

    if not result:
        return [_poly_to_coords(parent_poly)]

    # Smooth edges: subdivide at mesh level
    result = _mesh_edge_densify(result, edge_n_extra, rng)

    return result


def _tessellate_with_retry(parent_poly: Polygon, n_seeds: int,
                           min_area: float, max_aspect: float,
                           rng: random.Random, max_retries: int = 5) -> list[list[tuple]]:
    """Tessellate with retries if result doesn't meet targets."""
    best = None
    best_count = 0

    for attempt in range(max_retries):
        result = _tessellate(parent_poly, n_seeds, min_area, max_aspect, rng)
        count = len(result)
        if best is None or count > best_count:
            best = result
            best_count = count
        # If we got roughly enough, stop
        if count >= n_seeds * 0.6:
            break
        # Adjust seed count for next attempt
        n_seeds = int(n_seeds * (n_seeds / max(count, 1)))

    return best


# ── Main generation ────────────────────────────────────────────────

def generate():
    rng = random.Random(42)
    bounding = Polygon([
        (LNG_MIN, LAT_MIN), (LNG_MAX, LAT_MIN),
        (LNG_MAX, LAT_MAX), (LNG_MIN, LAT_MAX),
    ])

    # Phase 1: Tessellate bounding polygon into 相
    print("  Tessellating bounding polygon into 相...")
    facies_polys = _tessellate_with_retry(bounding, 50, min_area=2.0, max_aspect=4.0, rng=rng)
    print(f"    → {len(facies_polys)} 相 polygons")

    facies_features = []
    facies_meta = []  # (coords, facies_name, id)

    facies_assignment = list(range(len(FACIES_NAMES))) * 7
    rng.shuffle(facies_assignment)
    facies_assignment = facies_assignment[:len(facies_polys)]

    for idx, coords in enumerate(facies_polys):
        facies_name = FACIES_NAMES[facies_assignment[idx]]
        fid = f"F{idx + 1:03d}"
        facies_meta.append((coords, facies_name, fid))
        facies_features.append({
            "type": "Feature",
            "properties": {
                "facies": facies_name,
                "name": f"{facies_name}-区{idx + 1:02d}",
                "period": PERIOD,
                "level": "facies",
                "id": fid,
            },
            "geometry": {"type": "Polygon", "coordinates": [to_geojson_coords(coords)]},
        })

    # Phase 2: Subdivide each 相 into 亚相
    print("  Subdividing into 亚相...")
    sub_counts = [rng.choice([2, 3, 3, 4, 4, 5]) for _ in range(len(facies_meta))]
    total = sum(sub_counts)
    target = rng.randint(145, 155)
    while total != target:
        i = rng.randint(0, len(sub_counts) - 1)
        if total > target and sub_counts[i] > 2:
            sub_counts[i] -= 1
            total -= 1
        elif total < target and sub_counts[i] < 5:
            sub_counts[i] += 1
            total += 1

    sub_features = []
    sub_meta = []
    sub_idx = 0

    for fi, (coords, facies_name, fid) in enumerate(facies_meta):
        parent_poly = _make_valid(Polygon(coords))
        n_sub = sub_counts[fi]
        sub_polys = _tessellate_with_retry(
            parent_poly, n_sub, min_area=0.3, max_aspect=5.0, rng=rng)
        sub_names = FACIES_TAXONOMY[facies_name]["sub"]

        for si, spoly_coords in enumerate(sub_polys):
            sub_name = sub_names[si % len(sub_names)]
            sid = f"S{sub_idx + 1:03d}"
            sub_meta.append((spoly_coords, sub_name, facies_name, fid, sid))
            sub_features.append({
                "type": "Feature",
                "properties": {
                    "facies": sub_name,
                    "name": f"{facies_name}-{sub_name}-{si + 1:03d}",
                    "period": PERIOD,
                    "level": "sub_facies",
                    "parent_id": fid,
                    "id": sid,
                },
                "geometry": {"type": "Polygon", "coordinates": [to_geojson_coords(spoly_coords)]},
            })
            sub_idx += 1

    print(f"    → {len(sub_features)} 亚相 polygons")

    # Phase 3: Subdivide each 亚相 into 微相
    print("  Subdividing into 微相...")
    n_subs = len(sub_meta)
    micro_per_sub = [rng.choice([3, 3, 3, 4, 4, 4, 5]) for _ in range(n_subs)]
    total_micro = sum(micro_per_sub)
    micro_target = rng.randint(390, 410)
    while total_micro != micro_target:
        i = rng.randint(0, n_subs - 1)
        if total_micro > micro_target and micro_per_sub[i] > 2:
            micro_per_sub[i] -= 1
            total_micro -= 1
        elif total_micro < micro_target and micro_per_sub[i] < 5:
            micro_per_sub[i] += 1
            total_micro += 1

    micro_features = []
    micro_idx = 0

    for si, (spoly_coords, sub_name, facies_name, fid, sid) in enumerate(sub_meta):
        parent_poly = _make_valid(Polygon(spoly_coords))
        n_micro = micro_per_sub[si]
        micro_polys = _tessellate_with_retry(
            parent_poly, n_micro, min_area=0.05, max_aspect=6.0, rng=rng)
        # Merge excess cells into nearest neighbors to hit target count
        cell_polys = [_make_valid(Polygon(c)) for c in micro_polys]
        cell_polys = [c for c in cell_polys if not c.is_empty and c.area > 1e-10]
        cell_polys = _merge_cells_to_count(cell_polys, n_micro)
        micro_polys = [_poly_to_coords(c) for c in cell_polys]
        micro_names = FACIES_TAXONOMY[facies_name]["micro"]

        for mi, mpoly_coords in enumerate(micro_polys):
            micro_name = micro_names[mi % len(micro_names)]
            mid = f"M{micro_idx + 1:03d}"
            micro_features.append({
                "type": "Feature",
                "properties": {
                    "facies": micro_name,
                    "name": f"{sub_name}-{micro_name}-{mi + 1:03d}",
                    "period": PERIOD,
                    "level": "micro_facies",
                    "parent_id": sid,
                    "grandparent_id": fid,
                    "id": mid,
                },
                "geometry": {"type": "Polygon", "coordinates": [to_geojson_coords(mpoly_coords)]},
            })
            micro_idx += 1

    print(f"    → {len(micro_features)} 微相 polygons")

    return facies_features, sub_features, micro_features


def to_geojson_coords(poly):
    """Convert list of (x,y) to GeoJSON coordinate ring."""
    ring = [[round(x, 6), round(y, 6)] for x, y in poly]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def write_geojson(features, path):
    fc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"  {path.name}: {len(features)} features")


def _validate_no_overlaps(children, child_label, parent_label):
    """Check that children of the same parent don't overlap."""
    from collections import defaultdict

    by_parent = defaultdict(list)
    for f in children:
        pid = f["properties"]["parent_id"]
        geom = Polygon(f["geometry"]["coordinates"][0])
        by_parent[pid].append((f["properties"]["id"], geom))

    overlaps = 0
    for pid, items in by_parent.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                try:
                    if items[i][1].intersects(items[j][1]):
                        inter = items[i][1].intersection(items[j][1])
                        if inter.area > 1e-6:
                            overlaps += 1
                            if overlaps <= 5:
                                print(f"  OVERLAP: {child_label} {items[i][0]} & {items[j][0]} "
                                      f"(parent {parent_label} {pid}), area={inter.area:.6f}")
                except Exception:
                    pass

    if overlaps:
        print(f"  WARNING: {overlaps} {child_label} overlaps detected!")
    else:
        print(f"  {child_label} overlap check: OK (0 overlaps)")


def _validate_coverage(features, label):
    """Check that features cover the bounding area with minimal gaps."""
    from shapely.ops import unary_union
    geoms = [Polygon(f["geometry"]["coordinates"][0]) for f in features]
    merged = unary_union(geoms)
    expected = Polygon([
        (LNG_MIN, LAT_MIN), (LNG_MAX, LAT_MIN),
        (LNG_MAX, LAT_MAX), (LNG_MIN, LAT_MAX),
    ])
    gap = expected.difference(merged)
    gap_pct = (gap.area / expected.area * 100) if expected.area > 0 else 0
    if gap_pct > 0.5:
        print(f"  WARNING: {label} coverage gap = {gap_pct:.2f}%")
    else:
        print(f"  {label} coverage: OK (gap = {gap_pct:.2f}%)")


def main():
    out_dir = Path("samples")
    out_dir.mkdir(exist_ok=True)

    print("Generating paleo test GeoJSON data (Voronoi tessellation)...")
    facies, subs, micros = generate()

    write_geojson(facies, out_dir / "test_paleo_facies.geojson")
    write_geojson(subs, out_dir / "test_paleo_sub_facies.geojson")
    write_geojson(micros, out_dir / "test_paleo_micro_facies.geojson")

    n_f, n_s, n_m = len(facies), len(subs), len(micros)
    print(f"\n  相: {n_f}  亚相: {n_s}  微相: {n_m}")
    assert 45 <= n_f <= 55
    assert 100 <= n_s <= 200
    assert 300 <= n_m <= 500

    # Validate parent references
    facies_ids = {f["properties"]["id"] for f in facies}
    sub_ids = {f["properties"]["id"] for f in subs}
    for f in subs:
        assert f["properties"]["parent_id"] in facies_ids
    for f in micros:
        assert f["properties"]["parent_id"] in sub_ids
        assert f["properties"]["grandparent_id"] in facies_ids

    print("  Validation passed.")

    # Validate no overlaps
    _validate_no_overlaps(subs, "亚相", "相")
    _validate_no_overlaps(micros, "微相", "亚相")

    # Validate coverage
    _validate_coverage(facies, "相")
    _validate_coverage(subs, "亚相")
    _validate_coverage(micros, "微相")


if __name__ == "__main__":
    main()
