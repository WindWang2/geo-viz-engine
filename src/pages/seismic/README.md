# Seismic Page

This module provides the UI orchestration for the seismic 3D visualization.

## Architecture

The core rendering logic is delegated to the `geoviz-seismic` package:
- `geoviz_seismic.SeismicView`: The main visualization component.
- `geoviz_seismic.Renderer3D`: The underlying OpenGL renderer using PyQtGraph.

## Usage

This page is responsible for:
1. Instantiating the `SeismicView`.
2. Handling file open dialogs for SEGY data.
3. Managing the integration with the application-wide sidebar and status bar.
