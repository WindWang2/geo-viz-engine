# Image Track Reference

The Image Track provides capabilities for rendering high-resolution 2D image data directly onto a well log depth track. It supports core photos (segmented by depth) and Borehole Imaging (FMI) data arrays with customizable colormaps.

## API / Interface

### `ImageTrack`
Inherits from `BaseTrack` (which is a PySide6 `QWidget`). It manages collections of core photos and FMI segments within a specific depth viewport.

**Constructor:**
- `__init__(self, name: str = "Core Photos", width: int = 160, parent=None)`
  Creates a new track with the specified label and width.

**Methods:**
- `set_depth_range(self, min_depth: float, max_depth: float)`: Updates the visible depth viewport and triggers a repaint.
- `add_core_photo(self, photo: CorePhotoSegment)`: Adds a core photo. Triggers `photo.load_pixmap()` automatically.
- `add_fmi_segment(self, fmi: BoreholeImageSegment)`: Adds an FMI data matrix segment.
- `paint_content(self, painter: QPainter, rect: QRectF)`: Override of `BaseTrack.paint_content`. Renders all visible photos and FMI segments into the target `rect` with proper depth scaling.

### `CorePhotoSegment` (Dataclass)
Represents a single core photo tied to a specific depth interval.

**Fields:**
- `depth_top` (`float`): Top depth of the photo segment.
- `depth_bottom` (`float`): Bottom depth of the photo segment.
- `image_path` (`str`): Absolute or relative path to the image file (defaults to `""`).
- `title` (`str`): Display title for the segment (defaults to `"Core Photo"`).
- `pixmap` (`Optional[QPixmap]`): The cached PySide6 pixmap. Populated via `load_pixmap()`.

**Methods:**
- `load_pixmap(self)`: Loads the file at `image_path` into `pixmap` if it hasn't been loaded already.

### `BoreholeImageSegment` (Dataclass)
Represents a 2D array of electrical or acoustic borehole imaging data.

**Fields:**
- `depth_top` (`float`): Top depth of the logged interval.
- `depth_bottom` (`float`): Bottom depth of the logged interval.
- `data_matrix` (`Optional[np.ndarray]`): 2D float array containing `[N_depth, N_azimuth]` image data.
- `colormap_name` (`str`): Name of the colormap to apply (defaults to `"thermal"`).

## Examples

```python
from geoviz_well_log.tracks.image_track import ImageTrack, CorePhotoSegment
from PySide6.QtWidgets import QApplication

app = QApplication([])

# Initialize track
track = ImageTrack(name="Well 1 Core")
track.set_depth_range(2000.0, 2010.0)

# Add a core photo segment
photo = CorePhotoSegment(
    depth_top=2002.5,
    depth_bottom=2003.5,
    image_path="data/core_box_1.jpg",
    title="Box 1"
)
track.add_core_photo(photo)
```

## Related
- [How to add image tracks](file:///home/kevin/projects/geo-viz-engine/docs/howto-add-image-tracks.md)
