import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import WellMap from '../components/map/WellMap';

export default function MapHomePage() {
  const { request } = useApi();
  const navigate = useNavigate();
  const [realWells, setRealWells] = useState<Array<{well_name: string; longitude: number; latitude: number}>>([]);

  useEffect(() => {
    (async () => {
      try {
        const data = await request<Array<{well_name: string; longitude: number; latitude: number}>>('/api/data/real-wells');
        if (Array.isArray(data) && data.length > 0) {
          setRealWells(data);
        }
      } catch {
        // Silently fail
      }
    })();
  }, [request]);

  return (
    <div className="relative w-full h-full overflow-hidden">
      <WellMap
        realWells={realWells}
        onWellClick={(wellName) => navigate(`/well-detail/${encodeURIComponent(wellName)}`)}
      />
    </div>
  );
}
