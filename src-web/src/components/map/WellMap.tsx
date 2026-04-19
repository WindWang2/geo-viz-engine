import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { WellMetadata } from '../well-log/types';

interface RealWell {
  well_name: string;
  longitude: number;
  latitude: number;
}

interface WellMapProps {
  wells: WellMetadata[];
  realWells?: RealWell[];
  onWellClick: (wellId: string) => void;
  selectedWellId?: string | null;
}

const DFLT_CENTER: [number, number] = [107.0, 29.0];
const DFLT_ZOOM = 7;

export default function WellMap({ wells, realWells, onWellClick, selectedWellId }: WellMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: DFLT_CENTER,
      zoom: DFLT_ZOOM,
    });

    mapRef.current = map;

    // Cleanup
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Add / update synthetic well markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.loaded()) return;

    // Clear old markers
    const markers = (map as any)._markers || [];
    markers.forEach((m: any) => m.remove());
    (map as any)._markers = [];

    wells.forEach((well) => {
      if (well.longitude == null || well.latitude == null) return;

      const el = document.createElement('div');
      el.className = 'well-marker';
      el.style.cssText = `
        width: 12px; height: 12px;
        background: ${well.well_id === selectedWellId ? '#ef4444' : '#3b82f6'};
        border-radius: 50%;
        border: 2px solid white;
        cursor: pointer;
        box-shadow: 0 1px 4px rgba(0,0,0,0.3);
      `;
      el.title = well.well_name;

      new maplibregl.Marker(el)
        .setLngLat([well.longitude, well.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 15 }).setHTML(
            `<b>${well.well_name}</b><br/><small>${well.well_id}</small>`
          )
        )
        .addTo(map);

      el.addEventListener('click', () => onWellClick(well.well_id));

      (map as any)._markers = [(map as any)._markers || [], markers].flat();
    });
  }, [wells, selectedWellId]);

  // Add / update real well GeoJSON layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.loaded() || !realWells || realWells.length === 0) return;

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: realWells
        .filter(w => w.longitude != null && w.latitude != null)
        .map(w => ({
          type: 'Feature' as const,
          geometry: {
            type: 'Point' as const,
            coordinates: [w.longitude, w.latitude],
          },
          properties: { well_name: w.well_name },
        })),
    };

    // Remove old layer/source if present
    if (map.getLayer('real-wells-circle')) map.removeLayer('real-wells-circle');
    if (map.getLayer('real-wells-label')) map.removeLayer('real-wells-label');
    if (map.getSource('real-wells')) map.removeSource('real-wells');

    map.addSource('real-wells', {
      type: 'geojson',
      data: geojson,
    });

    map.addLayer({
      id: 'real-wells-circle',
      type: 'circle',
      source: 'real-wells',
      paint: {
        'circle-radius': 6,
        'circle-color': '#16a34a',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
      },
    });

    map.addLayer({
      id: 'real-wells-label',
      type: 'symbol',
      source: 'real-wells',
      layout: {
        'text-field': ['get', 'well_name'],
        'text-size': 10,
        'text-offset': [0, 1.2],
        'text-anchor': 'top',
      },
      paint: {
        'text-color': '#15803d',
        'text-halo-color': '#ffffff',
        'text-halo-width': 1,
      },
    });

    // Popup on click
    map.on('click', 'real-wells-circle', (e) => {
      const props = e.features?.[0]?.properties;
      if (!props) return;
      const coords = e.lngLat;
      new maplibregl.Popup({ offset: 10 })
        .setLngLat(coords)
        .setHTML(`<b>${props.well_name}</b><br/><small>Real Well</small>`)
        .addTo(map);
    });

    // Auto-fit to real wells if no synthetic wells
    if (wells.length === 0 && geojson.features.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      geojson.features.forEach(f => {
        const c = (f.geometry as GeoJSON.Point).coordinates;
        bounds.extend([c[0], c[1]] as [number, number]);
      });
      map.fitBounds(bounds, { padding: 50, maxZoom: 12 });
    }
  }, [realWells, wells.length]);

  return (
    <div
      ref={mapContainer}
      className="w-full h-full"
      style={{ minHeight: '400px' }}
    />
  );
}
