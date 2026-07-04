# LAS Parser Reference

The LAS Parser provides industry-standard reading capabilities for LAS 2.0 and LAS 3.0 well log formats. It translates the ASCII format into structured NumPy arrays suitable for direct rendering and cross-plotting in GeoViz Engine.

## API / Interface

### `parse_las_text(text: str) -> LASParseResult`
Parses a raw LAS format string into a structured result.

**Parameters:**
- `text` (`str`): The complete contents of an LAS file as a string.

**Returns:** 
- `LASParseResult`: A dataclass containing the parsed arrays and metadata.

### `parse_las_file(filepath: str) -> LASParseResult`
Helper function to load and parse an LAS file from disk.

**Parameters:**
- `filepath` (`str`): Absolute or relative path to the `.las` file. Uses UTF-8 encoding, ignoring errors.

**Returns:**
- `LASParseResult`: A dataclass containing the parsed arrays and metadata.

### `LASParseResult` (Dataclass)
The structured output of a parsing operation.

**Fields:**
- `well_name` (`str`): The name of the well (defaults to `"UNKNOWN"`).
- `depth_name` (`str`): The exact name of the depth column (defaults to `"DEPT"`).
- `depth` (`np.ndarray`): 1D float64 array of depth values.
- `curves` (`Dict[str, np.ndarray]`): Dictionary mapping curve names to 1D float64 arrays of values.
- `units` (`Dict[str, str]`): Dictionary mapping curve names to unit strings.
- `descriptions` (`Dict[str, str]`): Dictionary mapping curve names to description strings.

## Options / Configuration

There is no global configuration. The parser automatically detects `WELL.WELL` for the well name, `WELL.NULL` for the null sentinel (defaulting to `-999.25`), and dynamically infers the depth column based on common names (`DEPT`, `DEPTH`).

## Examples

```python
from geoviz_well_log.las_parser import parse_las_file

# Parse file
result = parse_las_file("data/well_1.las")

print(f"Well: {result.well_name}")
print(f"Depth column: {result.depth_name}, points: {len(result.depth)}")
print(f"Available curves: {list(result.curves.keys())}")

# Access gamma ray data
if "GR" in result.curves:
    gr_data = result.curves["GR"]
    print(f"Max GR: {gr_data.max()}")
```

## Related
- [How to import LAS data](file:///home/kevin/projects/geo-viz-engine/docs/howto-import-las-data.md)
- [Explanation: LAS Null Handling](file:///home/kevin/projects/geo-viz-engine/docs/explanation-las-null-handling.md)
