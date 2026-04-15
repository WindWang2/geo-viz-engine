import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { WellMetadata } from '../well-log/types';

interface WellMapProps {
  wells: WellMetadata[];
  onWellClick: (wellId: string) => void;
  selectedWellId?: string | null;
}

const DFLT_CENTER: [number, number] = [107.0, 29.0];
const DFLT_ZOOM = 7;

export default function WellMap({ wells, onWellClick, selectedWellId }: WellMapProps) {
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

  // Add / update markers whenever wells prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.loaded()) return;

    // Clear old markers
    const markers = (map as any)._markers || [];
    markers.forEach((m: any) => m.remove());
    (map as any)._markers = [];

    wells.forEach((well) => {
      if (well.longitude == null || well.latitude == null) return;

      // Color by selection
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

  return (
    <div
      ref={mapContainer}
      className="w-full h-full"
      style={{ minHeight: '400px' }}
    />
  );
}