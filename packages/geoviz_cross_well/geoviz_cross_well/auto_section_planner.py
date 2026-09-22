"""Geometric planning algorithms for automatically routing and sorting well sections."""

from typing import Any, List, Union, Tuple
import numpy as np

def _extract_coords(well: Any) -> Tuple[str, float, float]:
    """Extract name, longitude, and latitude from a well object, dict, or tuple.
    
    Supports:
    - Tuple: (name, lng, lat) or (name, (lng, lat))
    - Dict: keys like 'name', 'longitude'/'lng'/'x', 'latitude'/'lat'/'y'
    - Object: attributes like .name, .longitude/.lng/.x, .latitude/.lat/.y
    """
    if isinstance(well, tuple):
        if len(well) == 3:
            return str(well[0]), float(well[1]), float(well[2])
        elif len(well) == 2:
            name, coords = well
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                return str(name), float(coords[0]), float(coords[1])
            raise ValueError(f"Invalid coordinate tuple format: {well}")
        raise ValueError(f"Invalid tuple size for well: {well}")
    
    if isinstance(well, dict):
        name = well.get("name") or well.get("well_name") or well.get("id") or ""
        lng = well.get("longitude")
        if lng is None:
            lng = well.get("lng")
        if lng is None:
            lng = well.get("x")
            
        lat = well.get("latitude")
        if lat is None:
            lat = well.get("lat")
        if lat is None:
            lat = well.get("y")
            
        if lng is None or lat is None:
            raise ValueError(f"Missing coordinate keys in dict well: {well}")
        return str(name), float(lng), float(lat)
        
    # Duck-typing attributes
    name = getattr(well, "name", None) or getattr(well, "well_name", None) or ""
    lng = getattr(well, "longitude", None)
    if lng is None:
        lng = getattr(well, "lng", None)
    if lng is None:
        lng = getattr(well, "x", None)
        
    lat = getattr(well, "latitude", None)
    if lat is None:
        lat = getattr(well, "lat", None)
    if lat is None:
        lat = getattr(well, "y", None)
    
    if lng is None or lat is None:
        raise ValueError(f"Could not extract coordinates from object well: {well}")
        
    return str(name), float(lng), float(lat)


def plan_section_pca(wells: List[Any]) -> List[Any]:
    """Sort wells along the first principal component (PCA) of their geographic coordinates.
    
    This is best for sections that roughly follow a straight trend in any orientation
    (e.g., diagonal, east-west, north-south).
    
    Args:
        wells: A list of well objects, dicts, or tuples.
        
    Returns:
        The sorted list of well objects.
    """
    if len(wells) <= 2:
        return list(wells)
        
    parsed = [_extract_coords(w) for w in wells]
    coords = np.array([[p[1], p[2]] for p in parsed])  # shape (N, 2)
    
    # Compute centroid and center coords
    centroid = np.mean(coords, axis=0)
    centered = coords - centroid
    
    # SVD to get principal components
    # centered = U * S * Vt
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    v1 = Vt[0]  # First principal component direction vector
    
    # Project each centered coordinate onto v1 (scalar dot product)
    projections = np.dot(centered, v1)
    
    # Sort indices by projection value
    sorted_indices = np.argsort(projections)
    
    return [wells[idx] for idx in sorted_indices]


def plan_section_nearest_neighbor(wells: List[Any]) -> List[Any]:
    """Sort wells using a greedy Nearest Neighbor (TSP heuristic) starting from an extreme endpoint.
    
    First runs PCA to locate an extreme edge endpoint of the well collection,
    then builds a contiguous path by repeatedly adding the nearest unvisited well.
    This is best for winding, non-linear, or 'dog-leg' well sections.
    
    Args:
        wells: A list of well objects, dicts, or tuples.
        
    Returns:
        The sorted list of well objects forming a path.
    """
    if len(wells) <= 2:
        return list(wells)
        
    # First, run PCA to find the extreme endpoints
    pca_sorted = plan_section_pca(wells)
    
    # Lookup by INDEX, not name: duplicate well names (two laterals of one
    # field, repeated CSV rows) collapsed the name-keyed dict and silently
    # dropped every duplicate from the planned section (ISSUE-014).
    entries: list[tuple[float, float, Any]] = []
    for w in wells:
        _, lng, lat = _extract_coords(w)
        entries.append((lng, lat, w))

    # Start at one of the outer PCA endpoints — locate it by identity, then
    # by name (the PCA list may hold copies).
    start_well = pca_sorted[0]
    start_idx = next(
        (i for i, (_, _, w) in enumerate(entries) if w is start_well), None
    )
    if start_idx is None:
        start_name = _extract_coords(start_well)[0]
        start_idx = next(
            (
                i
                for i, (_, _, w) in enumerate(entries)
                if _extract_coords(w)[0] == start_name
            ),
            0,
        )

    path = [entries[start_idx][2]]
    visited = {start_idx}

    current = start_idx
    while len(path) < len(entries):
        curr_lng, curr_lat, _ = entries[current]

        nearest = None
        min_dist = float("inf")

        for i, (lng, lat, _) in enumerate(entries):
            if i in visited:
                continue
            # Euclidean distance squared (sufficient for sorting)
            dist = (lng - curr_lng) ** 2 + (lat - curr_lat) ** 2
            if dist < min_dist:
                min_dist = dist
                nearest = i

        if nearest is None:
            break

        path.append(entries[nearest][2])
        visited.add(nearest)
        current = nearest

    return path


def plan_section(wells: List[Any], method: str = "pca") -> List[Any]:
    """Plan a contiguous well section path from a list of wells.
    
    Args:
        wells: A list of well objects, dicts, or tuples.
        method: The sorting method, either 'pca' (projection) or 'nearest_neighbor' (greedy path).
        
    Returns:
        The sorted list of well objects.
    """
    method_lower = method.lower().strip()
    if method_lower == "pca":
        return plan_section_pca(wells)
    elif method_lower in ("nearest_neighbor", "nn", "tsp"):
        return plan_section_nearest_neighbor(wells)
    else:
        raise ValueError(f"Unknown planning method: {method}. Use 'pca' or 'nearest_neighbor'.")
