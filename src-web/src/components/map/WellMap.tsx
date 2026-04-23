import { useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface RealWell {
  well_name: string;
  longitude: number;
  latitude: number;
}

interface WellMapProps {
  realWells?: RealWell[];
  onWellClick?: (wellName: string) => void;
}

const DFLT_CENTER: [number, number] = [115.14, 21.31];
const DFLT_ZOOM = 9;

/**
 * Return true if the well has actual well log data available (will show as red star).
 * Add wells here after converting data to the expected format.
 */
const hasWellData = (name: string) => {
  // LaoLong1 and any well converted to our XLS format
  return (
    name === '老龙1' || name === '老龙1井' || name.toLowerCase().includes('laolong') ||
    name === 'HZ25-10-1' || name.startsWith('HZ25') // All converted HZ wells have data
  );
};

function createStarImageData(color: string, size = 24): { width: number; height: number; data: Uint8Array } {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;

  const cx = size / 2, cy = size / 2;
  const outerR = size / 2 - 2;
  const innerR = outerR * 0.4;

  ctx.beginPath();
  for (let i = 0; i < 10; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = -(Math.PI / 2) + (Math.PI / 5) * i;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const imageData = ctx.getImageData(0, 0, size, size);
  return { width: size, height: size, data: new Uint8Array(imageData.data.buffer) };
}

export default function WellMap({ realWells, onWellClick }: WellMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pendingWellsRef = useRef<RealWell[] | null>(null);
  const onWellClickRef = useRef(onWellClick);
  onWellClickRef.current = onWellClick;

  // Resize map when container size changes
  useEffect(() => {
    if (!mapContainer.current || !mapRef.current) return;

    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current && mapContainer.current) {
        // If container has non-zero height now, trigger map resize
        if (mapContainer.current.clientHeight > 0) {
          mapRef.current.resize();
        }
      }
    });

    resizeObserver.observe(mapContainer.current);
    return () => resizeObserver.disconnect();
  }, []);

  const addWells = useCallback((map: maplibregl.Map, wells: RealWell[]) => {
    // Add star icons as raw pixel data (synchronous, no load timing issues)
    const redStar = createStarImageData('#ef4444');
    const grayStar = createStarImageData('#9ca3af');
    map.addImage('star-red', redStar);
    map.addImage('star-gray', grayStar);

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: wells
        .filter(w => w.longitude != null && w.latitude != null)
        .map(w => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: [w.longitude, w.latitude] },
          properties: { well_name: w.well_name, has_data: hasWellData(w.well_name) },
        })),
    };

    // Cleanup old layers/sources
    for (const id of ['wells-star', 'wells-label']) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource('real-wells')) map.removeSource('real-wells');

    map.addSource('real-wells', { type: 'geojson', data: geojson });

    // Star markers
    map.addLayer({
      id: 'wells-star',
      type: 'symbol',
      source: 'real-wells',
      layout: {
        'icon-image': ['case', ['get', 'has_data'], 'star-red', 'star-gray'],
        'icon-size': 1,
        'icon-allow-overlap': true,
        'icon-anchor': 'center',
      },
    });

    // Labels
    map.addLayer({
      id: 'wells-label',
      type: 'symbol',
      source: 'real-wells',
      layout: {
        'text-field': ['get', 'well_name'],
        'text-size': 9,
        'text-offset': [0, 1.4],
        'text-anchor': 'top',
        'text-allow-overlap': false,
      },
      paint: {
        'text-color': ['case', ['get', 'has_data'], '#ef4444', '#6b7280'],
        'text-halo-color': '#ffffff',
        'text-halo-width': 1,
      },
    });

    // Click handler for red stars
    map.on('click', 'wells-star', (e) => {
      const props = e.features?.[0]?.properties as any;
      if (!props) return;
      if (props.has_data && onWellClickRef.current) {
        onWellClickRef.current(props.well_name);
      } else {
        new maplibregl.Popup({ offset: 10 })
          .setLngLat(e.lngLat)
          .setHTML(`<b>${props.well_name}</b><br/><small style="color:#9ca3af">暂无数据</small>`)
          .addTo(map);
      }
    });

    // Cursor style
    map.on('mouseenter', 'wells-star', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'wells-star', () => { map.getCanvas().style.cursor = ''; });

    // Auto-fit
    if (geojson.features.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      geojson.features.forEach(f => {
        const c = (f.geometry as GeoJSON.Point).coordinates;
        bounds.extend([c[0], c[1]] as [number, number]);
      });
      map.fitBounds(bounds, { padding: 60, maxZoom: 12 });
    }
  }, []);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'otm': {
            type: 'raster',
            tiles: [
              'https://tile.opentopomap.org/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '© OpenTopoMap contributors',
          },
        },
        layers: [{ id: 'otm', type: 'raster', source: 'otm', minzoom: 0, maxzoom: 17 }],
      },
      center: DFLT_CENTER,
      zoom: DFLT_ZOOM,
    });

    map.on('load', () => {
      mapRef.current = map;
      if (pendingWellsRef.current && pendingWellsRef.current.length > 0) {
        addWells(map, pendingWellsRef.current);
        pendingWellsRef.current = null;
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [addWells]);

  useEffect(() => {
    if (!realWells || realWells.length === 0) return;
    const map = mapRef.current;
    if (map && map.loaded()) {
      addWells(map, realWells);
    } else {
      pendingWellsRef.current = realWells;
    }
  }, [realWells, addWells]);

  return (
    <div ref={mapContainer} className="w-full h-full" style={{ minHeight: '400px' }} />
  );
}
