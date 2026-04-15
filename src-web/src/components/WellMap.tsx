'use client';

import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapStore } from '../stores/useMapStore';
import type { WellLocation } from '../types/coordinate';
import { useApi } from '../hooks/useApi';

// MapLibre style — using free OSM raster tiles
const MAP_STYLE = 'https://basemaps.cartocdn.com/glpositron-gl-style/style.json';

const WELL_LAYER_ID = 'wells-circle';
const WELL_SOURCE_ID = 'wells';

export default function WellMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const { selectedWellId, setSelectedWellId } = useMapStore();
  const { request } = useApi();

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [107, 29],   // 川东片区中心
      zoom: 5,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');
map.current.on('load', () => {
      const mapInstance = map.current!;

      // Add wells GeoJSON source (empty initially)
      mapInstance.addSource(WELL_SOURCE_ID, {

        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Circle layer for well markers
      mapInstance.addLayer({
        id: WELL_LAYER_ID,
        type: 'circle',
        source: WELL_SOURCE_ID,
        paint: {
          'circle-color': '#3b82f6',   // blue-500
          'circle-radius': 6,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.9,
        },
      });

      // Hover effect: change cursor
      mapInstance.on('mouseenter', WELL_LAYER_ID, () => {
        mapInstance.getCanvas().style.cursor = 'pointer';
      });
      mapInstance.on('mouseleave', WELL_LAYER_ID, () => {
        mapInstance.getCanvas().style.cursor = '';
      });

      // Popup on hover
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 15,
      });

      mapInstance.on('mouseenter', WELL_LAYER_ID, (e) => {
        if (!e.features?.length) return;
        const feat = e.features[0];
        const props = feat.properties!;
        const coords = (feat.geometry as GeoJSON.Point).coordinates as [number, number];

        popup
          .setLngLat(coords)
          .setHTML(`<div class="text-sm"><strong>${props.name ?? props.well_id}</strong><br/>${props.longitude?.toFixed(4)}°E&nbsp;&nbsp;${props.latitude?.toFixed(4)}°N</div>`)
          .addTo(mapInstance);
      });
      mapInstance.on('mouseleave', WELL_LAYER_ID, () => popup.remove());

      // Click → select well
      mapInstance.on('click', WELL_LAYER_ID, (e) => {
        if (!e.features?.length) return;
        const props = e.features[0].properties!;
        setSelectedWellId(props.well_id);
      });

      setMapLoaded(true);
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [setSelectedWellId]);

  // Fetch wells data once map is ready
  useEffect(() => {
    if (!mapLoaded || !map.current) return;

    async function loadWells() {
      try {
        const data = await request<WellLocation[]>('/api/data/wells');
        if (!map.current) return;
        const features = data.map((well) => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: [well.longitude, well.latitude] },
          properties: { well_id: well.well_id, name: well.well_name, longitude: well.longitude, latitude: well.latitude },
        }));
        const source = map.current!.getSource(WELL_SOURCE_ID) as maplibregl.GeoJSONSource;
        source.setData({ type: 'FeatureCollection', features });
      } catch (e) {
        console.error('Failed to load wells:', e);
      }
    }
    loadWells();
  }, [mapLoaded, request]);

  // Highlight selected well: update paint property
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const newRadius = selectedWellId != null ? 9 : 6;
    const newColor = selectedWellId != null ? '#f59e0b' : '#3b82f6'; // amber-500 vs blue-500
    map.current.setPaintProperty(WELL_LAYER_ID, 'circle-radius', newRadius);
    map.current.setPaintProperty(WELL_LAYER_ID, 'circle-color', newColor);
  }, [selectedWellId, mapLoaded]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapContainer} className="h-full w-full" />
    </div>
  );
}