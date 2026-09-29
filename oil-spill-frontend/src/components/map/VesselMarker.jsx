import React, { useMemo, useState, useEffect } from 'react';
import { Marker, Polyline, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';

/**
 * Maps a Leaflet zoom level to a continuous SVG pixel size.
 * Zoom 3-4  → ~7-8 px  (wide-area view, very small)
 * Zoom 6-7  → ~11-13px (regional, clearly visible)
 * Zoom 10+  → ~18-22px (close-up, easy to identify)
 * Clamped to [6, 22] so icons never disappear or become huge.
 */
function svgSizeFromZoom(zoom) {
  // Linear interpolation: base size 6px at zoom 2, grows by 1.4px per zoom level
  const raw = 6 + (zoom - 2) * 1.4;
  return Math.round(Math.min(Math.max(raw, 6), 22));
}

/**
 * Creates a Mapbox GL or Leaflet compatible DOM element/marker instance
 * following the requested cinematic radar ship marker style.
 */
export function createShipMarker(shipData) {
  const el = document.createElement('div');
  el.className = 'ship-marker-container';

  const core = document.createElement('div');
  core.className = 'ship-core';

  if (shipData.is_suspected || shipData.isSuspect) {
    core.classList.add('suspected');
  }

  el.appendChild(core);

  // Return Mapbox GL marker instance if Mapbox is loaded in global scope
  if (typeof window !== 'undefined' && window.mapboxgl && window.mapboxgl.Marker) {
    const lng = shipData.longitude ?? shipData.lng ?? 0;
    const lat = shipData.latitude ?? shipData.lat ?? 0;
    return new window.mapboxgl.Marker(el).setLngLat([lng, lat]);
  }

  return el;
}

export default function VesselMarker({ vessel, onSelect }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    const onZoom = () => setZoom(map.getZoom());
    map.on('zoomend', onZoom);
    return () => {
      map.off('zoomend', onZoom);
    };
  }, [map]);

  // Clamp heading to 0-360; use cog as fallback
  const heading = useMemo(() => {
    const h = vessel.heading;
    const c = vessel.cog;
    if (h != null && h !== 511 && h >= 0 && h <= 360) return h;
    if (c != null && c >= 0 && c <= 360) return c;
    return null;
  }, [vessel.heading, vessel.cog]);

  const customIcon = useMemo(() => {
    const isSuspect = vessel.isSuspect || vessel.is_suspected;
    const status = (vessel.navStatus || '').toLowerCase();

    let statusClass = '';
    if (isSuspect) {
      statusClass = 'suspected';
    } else if (status.includes('underway')) {
      statusClass = 'underway';
    } else if (status.includes('anchor') || status.includes('moor')) {
      statusClass = 'anchored';
    } else if (status.includes('fishing')) {
      statusClass = 'fishing';
    }

    const headingTransform = heading != null ? `transform: rotate(${heading}deg); transform-origin: center;` : '';

    // Zoom-scaled SVG dimensions — proportional height keeps the silhouette ratio (12:20 ≈ 0.6)
    const svgW = svgSizeFromZoom(zoom);
    const svgH = Math.round(svgW * (20 / 12));

    // Ship silhouette SVG: top-down view, pointed bow (top), rounded stern (bottom)
    const shipSvg = `
      <svg class="ship-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 20" width="${svgW}" height="${svgH}">
        <path d="M6 0 L11 7 L10 14 Q9 18 6 20 Q3 18 2 14 L1 7 Z" fill="currentColor" stroke="rgba(255,255,255,0.6)" stroke-width="0.8"/>
        <rect x="4.5" y="8" width="3" height="4" rx="0.5" fill="rgba(0,0,0,0.25)"/>
      </svg>
    `;

    // Container snaps to the scaled SVG size so the anchor remains centred
    const ctrW = svgW + 12;  // extra pixels for the glow ring to breathe
    const ctrH = svgH + 12;

    const html = `
      <div class="ship-marker-container" style="${headingTransform} width:${ctrW}px; height:${ctrH}px;">
        <div class="ship-core ${statusClass}">${shipSvg}</div>
      </div>
    `;

    return L.divIcon({
      html: html,
      className: 'vessel-div-icon',
      iconSize: [ctrW, ctrH],
      iconAnchor: [ctrW / 2, ctrH / 2],
      popupAnchor: [0, -(ctrH / 2)],
    });
  }, [vessel.isSuspect, vessel.is_suspected, vessel.navStatus, heading, zoom]);

  return (
    <>
      <Marker
        position={[vessel.lat, vessel.lng]}
        icon={customIcon}
        eventHandlers={{ click: () => onSelect && onSelect(vessel) }}
      >
        {/* Tooltip: for suspects when zoomed in */}
        {(vessel.isSuspect || vessel.is_suspected) && zoom >= 8 && (
          <Tooltip
            permanent
            direction="top"
            className="!bg-[#0b1220] !border-red-700/50 !text-red-300 !font-mono !text-[10px] !shadow-lg !rounded !px-2 !py-0.5"
          >
            {vessel.name} · {vessel.sog} kn
          </Tooltip>
        )}
      </Marker>

      {/* Trajectory line — for suspects with trajectory data */}
      {(vessel.isSuspect || vessel.is_suspected) && vessel.trajectory && (
        <Polyline
          positions={vessel.trajectory}
          pathOptions={{ color: '#ef4444', dashArray: '5 5', weight: 1.5, opacity: 0.7 }}
        />
      )}
    </>
  );
}
