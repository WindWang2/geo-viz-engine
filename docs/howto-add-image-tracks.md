# How to add image tracks

This guide shows you how to display high-resolution core photos alongside your curve data in a well log visualization.

## Prerequisites

- A PySide6 `QApplication` must be initialized before creating Qt widgets or pixmaps.
- Image files (e.g., JPEG, PNG) representing core sections.

## Steps

1. Import the necessary components:

   ```python
   from geoviz_well_log.tracks.image_track import ImageTrack, CorePhotoSegment
   ```

2. Create an instance of the `ImageTrack`:

   ```python
   image_track = ImageTrack(name="Core Photography", width=200)
   
   # Tell the track what depth range to draw
   image_track.set_depth_range(min_depth=1500.0, max_depth=1520.0)
   ```

3. Create segments for each photo and specify their exact depth intervals:

   ```python
   box_1 = CorePhotoSegment(
       depth_top=1500.0,
       depth_bottom=1505.0,
       image_path="/path/to/core_1500_1505.jpg",
       title="Box 1 (Sandstone)"
   )
   
   box_2 = CorePhotoSegment(
       depth_top=1505.0,
       depth_bottom=1510.0,
       image_path="/path/to/core_1505_1510.jpg",
       title="Box 2 (Shale)"
   )
   ```

4. Add the segments to the track:

   ```python
   # The track will automatically load the images into QPixmaps
   image_track.add_core_photo(box_1)
   image_track.add_core_photo(box_2)
   ```

5. (Optional) If you are using `Coordinator` or `WellLogPage`, add the track to the layout:
   
   ```python
   # Example integration with the main renderer
   coordinator.add_track(image_track)
   ```

## Verification

If the images are properly loaded, they will render precisely within the bounds of `[depth_top, depth_bottom]`. 

If an image fails to load (or the `image_path` is invalid), the track will draw a fallback placeholder box with a dashed blue border containing the camera emoji 📷 and the depth range.

## Troubleshooting

- **"QPixmap: Must construct a QGuiApplication before a QPixmap"**: You attempted to instantiate a `CorePhotoSegment` and call `load_pixmap()` (or added it to the track) before creating your main `QApplication`.
- **Placeholder is rendering instead of image**: Check that `os.path.exists(image_path)` returns True. The path must be valid and the image must be readable by Qt.
- **Images are overlapping**: Ensure your `depth_top` and `depth_bottom` ranges for multiple segments do not conflict, as they are drawn in the order they were added.

## Related
- [Image Track Reference](file:///home/kevin/projects/geo-viz-engine/docs/reference-image-track.md)
