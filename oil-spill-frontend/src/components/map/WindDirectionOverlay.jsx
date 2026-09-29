import React, { useMemo } from 'react';
import { Marker } from 'react-leaflet';
import L from 'leaflet';

export default function WindDirectionOverlay({ center, directionDeg, count = 15 }) {
  const points = useMemo(() => {
    if (!center) return [];
    const [lat, lng] = center;
    const list = [];
    for (let i = 0; i < count; i++) {
      const latOffset = (Math.random() - 0.5) * 0.1; // ±0.05
      const lngOffset = (Math.random() - 0.5) * 0.1; // ±0.05
      list.push([lat + latOffset, lng + lngOffset]);
    }
    return list;
  }, [center, count]);

  const windIcon = useMemo(() => {
    const iconHtml = `
      <div style="display: flex; justify-content: center; align-items: center; width: 24px; height: 24px;">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="transform: rotate(${directionDeg}deg); transform-origin: center;">
          <path d="M12 19V5M5 12l7-7 7 7"/>
        </svg>
      </div>
    `;
    return L.divIcon({
      html: iconHtml,
      className: 'wind-div-icon',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }, [directionDeg]);

  return (
    <>
      {points.map((pos, idx) => (
        <Marker key={idx} position={pos} icon={windIcon} interactive={false} />
      ))}
    </>
  );
}
