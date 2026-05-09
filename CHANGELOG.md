# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-05-09

### Added
- **Paleogeography Map Visualization**: A new targeted, high-aesthetics map rendering module for ancient geography.
- Zero-friction GeoJSON loading via drag-and-drop or file picker.
- Instant high-resolution static PNG export capability.
- Support for rendering arbitrary geological facies using existing SVG rock patterns seamlessly via ECharts.
- Async loading of massive GeoJSON files using PySide6 localfile interception to prevent UI freezing.

### Changed
- Centralized facies to SVG pattern mapping in `src/utils/constants.py` to remove DRY violations across modules.
