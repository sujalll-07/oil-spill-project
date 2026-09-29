import React, { useMemo, useState, useEffect } from 'react';
import { Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';

export default function PlatformMarker({ platform }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    const onZoom = () => setZoom(map.getZoom());
    map.on('zoomend', onZoom);
    return () => {
      map.off('zoomend', onZoom);
    };
  }, [map]);

  const isIndia = platform.isIndiaEEZ !== false;
  const isActive = platform.status?.toLowerCase() === 'active';

  // Primary color: Cyan/Blue (matching image), Purple for IOR, Muted for Inactive
  const themeColor = !isActive
    ? '#94a3b8'
    : isIndia
    ? '#0284c7'
    : '#a855f7';

  const accentColor = !isActive
    ? '#64748b'
    : isIndia
    ? '#38bdf8'
    : '#c084fc';

  const customIcon = useMemo(() => {
    // Dynamic sizing scaled by zoom level (very small & sharp at overview, slightly larger when zooming into field):
    // Zoom <= 5: 16px container, 13px SVG
    // Zoom 6-8:  20px container, 16px SVG
    // Zoom >= 9: 24px container, 20px SVG
    const containerSize = zoom <= 5 ? 16 : zoom <= 8 ? 20 : 24;
    const svgSize = zoom <= 5 ? 13 : zoom <= 8 ? 16 : 20;

    const iconHtml = `
      <div style="position: relative; display: flex; justify-content: center; align-items: center; width: ${containerSize}px; height: ${containerSize}px; cursor: pointer;">
        <div style="width: ${containerSize}px; height: ${containerSize}px; border-radius: 3px; background: rgba(11, 18, 32, 0.90); border: 1px solid ${accentColor}90; box-shadow: 0 0 4px ${accentColor}30; display: flex; align-items: center; justify-content: center;">
          <svg width="${svgSize}" height="${svgSize}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- 3 Lower Support Columns (Pillars) in water -->
            <rect x="17" y="38" width="5.5" height="14" fill="${themeColor}" rx="1" />
            <rect x="29.25" y="38" width="5.5" height="14" fill="${themeColor}" rx="1" />
            <rect x="41.5" y="38" width="5.5" height="14" fill="${themeColor}" rx="1" />

            <!-- Main Horizontal Deck Hull Platform -->
            <rect x="10" y="34" width="44" height="4.5" fill="${themeColor}" rx="1" />

            <!-- Deck Housing / Modules Blocks -->
            <rect x="15" y="27" width="8" height="7" fill="${themeColor}" />
            <rect x="23" y="24" width="6" height="10" fill="${themeColor}" />
            <rect x="30.5" y="25" width="9.5" height="9" fill="${themeColor}" />
            <rect x="40" y="28" width="7" height="6" fill="${themeColor}" />
            <!-- Helideck / Rooftop plate -->
            <rect x="30" y="23" width="11" height="2" fill="${accentColor}" />

            <!-- Smaller Secondary Derrick (Left) -->
            <path d="M18 27L20 18H22L24 27" stroke="${themeColor}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            <line x1="19" y1="21" x2="23" y2="21" stroke="${themeColor}" stroke-width="1" />
            <line x1="18.5" y1="24.5" x2="23.5" y2="24.5" stroke="${themeColor}" stroke-width="1" />

            <!-- Tall Main Drilling Lattice Derrick (Center-Right) -->
            <path d="M33 23L36 5H38L41 23" stroke="${themeColor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            <!-- Derrick Crown Block Top -->
            <rect x="35.5" y="3.5" width="3" height="2" fill="${accentColor}" />
            <!-- Derrick Cross-Lattice Braces -->
            <line x1="34" y1="19" x2="40" y2="19" stroke="${themeColor}" stroke-width="1.1" />
            <line x1="34.5" y1="14" x2="39.5" y2="14" stroke="${themeColor}" stroke-width="1.1" />
            <line x1="35.5" y1="9" x2="38.5" y2="9" stroke="${themeColor}" stroke-width="1.1" />
            <line x1="34" y1="19" x2="39.5" y2="14" stroke="${themeColor}" stroke-width="0.8" />
            <line x1="40" y1="19" x2="34.5" y2="14" stroke="${themeColor}" stroke-width="0.8" />

            <!-- Offshore Pedestal Deck Crane (Right) -->
            <rect x="43" y="26" width="4" height="8" fill="${themeColor}" />
            <path d="M44 26L57 19" stroke="${accentColor}" stroke-width="1.8" stroke-linecap="round" />
            <path d="M47 29L57 19" stroke="${accentColor}" stroke-width="1" />
            <!-- Crane Hoist Hook Line -->
            <circle cx="57" cy="19" r="1" fill="${accentColor}" />
            <line x1="57" y1="20" x2="57" y2="25" stroke="${accentColor}" stroke-width="1.1" stroke-linecap="round" />

            <!-- Ocean Water Surface Waves -->
            <path d="M7 54C11 52 14 56 18 54C22 52 25 56 29 54C33 52 36 56 40 54C44 52 47 56 51 54C54 52 57 55 60 54" stroke="${accentColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        ${
          isActive
            ? `<div style="position: absolute; top: -1px; right: -1px; width: 4.5px; height: 4.5px; border-radius: 50%; background: ${isIndia ? '#38bdf8' : '#c084fc'}; box-shadow: 0 0 3px ${isIndia ? '#38bdf8' : '#c084fc'};"></div>`
            : ''
        }
      </div>
    `;
    return L.divIcon({
      html: iconHtml,
      className: 'platform-div-icon',
      iconSize: [containerSize, containerSize],
      iconAnchor: [containerSize / 2, containerSize / 2],
      popupAnchor: [0, -containerSize / 2],
    });
  }, [themeColor, accentColor, isActive, isIndia, zoom]);

  return (
    <Marker position={[platform.lat, platform.lng]} icon={customIcon}>
      <Popup className="platform-popup-container">
        <div className="bg-[#0b1220] text-slate-200 p-3 rounded-lg border border-slate-700/90 w-[260px] -m-3 shadow-2xl select-text overflow-hidden">
          {/* Header */}
          <div className="border-b border-slate-800/80 pb-2 mb-2">
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${
                isIndia 
                  ? 'bg-cyan-950/60 text-cyan-300 border-cyan-800/50' 
                  : 'bg-purple-950/60 text-purple-300 border-purple-800/50'
              }`}>
                {platform.jurisdiction || (isIndia ? 'India EEZ' : 'International')}
              </span>
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                isActive 
                  ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50' 
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {platform.status || 'Active'}
              </span>
            </div>
            <h3 className="font-bold text-xs text-slate-100 leading-tight">
              {platform.name}
            </h3>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {platform.field} · <span className="text-slate-300 font-medium">{platform.operator}</span>
            </p>
          </div>

          {/* Details */}
          <div className="space-y-1.5 text-[10px]">
            <div className="flex justify-between">
              <span className="text-slate-500">Basin</span>
              <span className="text-slate-300 text-right truncate max-w-[140px]">{platform.basin || '—'}</span>
            </div>
            {platform.type && (
              <div className="flex justify-between">
                <span className="text-slate-500">Facility Type</span>
                <span className="text-slate-300 text-right truncate max-w-[140px]">{platform.type}</span>
              </div>
            )}
            {platform.waterDepthM && (
              <div className="flex justify-between">
                <span className="text-slate-500">Water Depth</span>
                <span className="text-slate-300 font-mono">{platform.waterDepthM} m</span>
              </div>
            )}
            <div className="flex justify-between pt-1 border-t border-slate-800/60">
              <span className="text-slate-500">Coordinates</span>
              <span className="font-mono text-slate-300 text-right">
                {platform.lat.toFixed(4)}° N, {platform.lng.toFixed(4)}° E
              </span>
            </div>
            {platform.coordinateSource && (
              <div className="pt-1.5 border-t border-slate-800/60 text-[9px] text-slate-500 leading-tight">
                <span className="text-slate-400 font-semibold">Source: </span>
                {platform.coordinateSource}
              </div>
            )}
            {!platform.coordinatesVerified && (
              <div className="text-[9px] text-amber-400/90 font-medium italic">
                ⚠ Preliminary coordinate — verify before production
              </div>
            )}
          </div>
        </div>
      </Popup>

      <Tooltip
        direction="bottom"
        className="!bg-[#0b1220] !border-cyan-700/60 !text-cyan-200 !shadow-md !rounded !px-1.5 !py-0.5 text-[10px] !mt-2 font-medium"
      >
        🏗 {platform.name} ({platform.operator})
      </Tooltip>
    </Marker>
  );
}
