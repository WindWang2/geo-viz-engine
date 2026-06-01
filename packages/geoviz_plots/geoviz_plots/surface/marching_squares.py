"""Vector contour line and filled polygon extraction using contourpy."""
import numpy as np
import contourpy

def extract_contour_lines(grid_x, grid_y, grid_z, levels) -> dict[float, list[np.ndarray]]:
    """Extract vector contour lines for each level using contourpy.
    
    Handles NaNs automatically by converting to a masked array.
    
    Args:
        grid_x, grid_y: 1D grid coordinate arrays.
        grid_z: 2D grid value array of shape (len(grid_y), len(grid_x)).
        levels: List of contour levels to extract.
        
    Returns:
        A dict mapping level (float) to a list of lines (each line is a 2D numpy array of points).
    """
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    grid_z = np.asarray(grid_z, dtype=np.float64)
    
    # Mask NaNs & Infinities
    masked_z = np.ma.masked_invalid(grid_z)
    
    # Create contour generator using serial algorithm and separate line lists
    cg = contourpy.contour_generator(
        x=grid_x, y=grid_y, z=masked_z,
        name="serial", line_type="Separate"
    )
    
    lines_dict = {}
    for lv in levels:
        lines_dict[float(lv)] = cg.lines(float(lv))
        
    return lines_dict


def extract_filled_contours(grid_x, grid_y, grid_z, levels) -> list[tuple[float, float, list[np.ndarray], list[np.ndarray]]]:
    """Extract vector filled contour polygons between adjacent levels.
    
    Args:
        grid_x, grid_y: 1D grid coordinate arrays.
        grid_z: 2D grid value array of shape (len(grid_y), len(grid_x)).
        levels: Sorted list of contour interval boundary values.
        
    Returns:
        List of tuples: (level_min, level_max, polygons, offsets).
        polygons is a list of concatenated ring coordinates.
        offsets is a list of offset indices specifying where each outer/inner ring starts.
    """
    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)
    grid_z = np.asarray(grid_z, dtype=np.float64)
    
    # Mask NaNs & Infinities
    masked_z = np.ma.masked_invalid(grid_z)
    
    cg = contourpy.contour_generator(
        x=grid_x, y=grid_y, z=masked_z,
        name="serial", fill_type="OuterOffset"
    )
    
    filled_list = []
    sorted_levels = sorted(levels)
    for i in range(len(sorted_levels) - 1):
        lv_min = sorted_levels[i]
        lv_max = sorted_levels[i+1]
        polys, offsets = cg.filled(float(lv_min), float(lv_max))
        filled_list.append((float(lv_min), float(lv_max), polys, offsets))
        
    return filled_list
