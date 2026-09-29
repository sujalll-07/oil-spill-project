import React, { useState, useEffect } from 'react';
import { Polygon, Polyline, CircleMarker, Tooltip, useMap } from 'react-leaflet';

export default function OilSpillLayer({ spill }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());

  useEffect(() => {
    const onZoom = () => setZoom(map.getZoom());
    map.on('zoomend', onZoom);
    return () => {
      map.off('zoomend', onZoom);
    };
  }, [map]);

  if (!spill || !spill.polygon) return null;

  const hasOrigin = spill.originLat != null && spill.originLon != null;
  const has12hForecast = Number.isFinite(spill.forecast12hLat) && Number.isFinite(spill.forecast12hLon);
  const driftVector = hasOrigin ? [
    [spill.originLat, spill.originLon],
    [spill.lat, spill.lng]
  ] : null;
  const forecast12hVector = has12hForecast
    ? [[spill.lat, spill.lng], [spill.forecast12hLat, spill.forecast12hLon]]
    : null;

  const hasLandfall = spill.landfall && spill.landfall.trajectory_timeline && spill.landfall.trajectory_timeline.length > 0;
  const forwardTrajectory = hasLandfall 
    ? [[spill.lat, spill.lng], ...spill.landfall.trajectory_timeline.map(t => [t.center_lat, t.center_lon])]
    : null;

  return (
    <>
      {/* Detected Slick Boundary */}
      <Polygon
        positions={spill.polygon}
        pathOptions={{
          color: '#ef4444',
          weight: 2,
          dashArray: '6 6',
          fillColor: '#7f1d1d',
          fillOpacity: 0.4,
        }}
      >
        {zoom >= 7 && (
          <Tooltip
            permanent
            direction="center"
            className="!bg-slate-950/90 !border-red-500/40 !text-red-400 !font-semibold !shadow-lg !rounded !px-2 !py-1 text-xs whitespace-nowrap"
          >
            Detected Oil Spill - Area: {spill.areaKm2} km²
          </Tooltip>
        )}
      </Polygon>

      {/* 12-Hour Lagrangian Hindcast / Drift Dispersion Envelope */}
      {spill.driftPolygon && (
        <Polygon
          positions={spill.driftPolygon}
          pathOptions={{
            color: '#f59e0b',
            weight: 2,
            dashArray: '4 4',
            fillColor: '#b45309',
            fillOpacity: 0.3,
          }}
        >
          {zoom >= 7 && (
            <Tooltip
              permanent
              direction="center"
              className="!bg-slate-950/90 !border-amber-500/40 !text-amber-400 !font-semibold !shadow-lg !rounded !px-2 !py-1 text-xs whitespace-nowrap"
            >
              12-Hour Lagrangian Drift Hindcast
            </Tooltip>
          )}
        </Polygon>
      )}

      {/* 12-Hour Forward Lagrangian Dispersion Envelope */}
      {has12hForecast && spill.forecast12hPolygon && (
        <Polygon
          positions={spill.forecast12hPolygon}
          pathOptions={{
            color: '#22d3ee',
            weight: 2,
            dashArray: '4 4',
            fillColor: '#0891b2',
            fillOpacity: 0.25,
          }}
        >
          {zoom >= 7 && (
            <Tooltip
              permanent
              direction="center"
              className="!bg-slate-950/90 !border-cyan-500/40 !text-cyan-300 !font-semibold !shadow-lg !rounded !px-2 !py-1 text-xs whitespace-nowrap"
            >
              12-Hour Forward Drift Forecast
            </Tooltip>
          )}
        </Polygon>
      )}

      {/* Drift Advection Vector (Origin to Detection) */}
      {driftVector && (
        <Polyline
          positions={driftVector}
          pathOptions={{
            color: '#fbbf24',
            weight: 2,
            dashArray: '4 6',
            opacity: 0.85
          }}
        />
      )}

      {forecast12hVector && (
        <Polyline
          positions={forecast12hVector}
          pathOptions={{ color: '#22d3ee', weight: 2, dashArray: '5 6', opacity: 0.9 }}
        />
      )}

      {/* Lagrangian Origin Estimate Centroid */}
      {hasOrigin && (
        <CircleMarker
          center={[spill.originLat, spill.originLon]}
          radius={6}
          pathOptions={{
            color: '#f59e0b',
            fillColor: '#fbbf24',
            fillOpacity: 0.9,
            weight: 2
          }}
        >
          {zoom >= 7 && (
            <Tooltip
              permanent
              direction="bottom"
              className="!bg-[#0b1220] !border-amber-500/50 !text-amber-300 !font-mono !text-[10px] !shadow-lg !rounded !px-2 !py-0.5 whitespace-nowrap"
            >
              Estimated Spill Origin (-12h)
            </Tooltip>
          )}
        </CircleMarker>
      )}

      {has12hForecast && (
        <CircleMarker
          center={[spill.forecast12hLat, spill.forecast12hLon]}
          radius={7}
          pathOptions={{ color: '#06b6d4', fillColor: '#67e8f9', fillOpacity: 0.95, weight: 2 }}
        >
          {zoom >= 6 && (
            <Tooltip
              permanent
              direction="bottom"
              className="!bg-[#0b1220] !border-cyan-500/50 !text-cyan-200 !font-mono !text-[10px] !shadow-lg !rounded !px-2 !py-0.5 whitespace-nowrap"
            >
              Predicted Spill Position (+12h)
            </Tooltip>
          )}
        </CircleMarker>
      )}

      {/* Forward Prediction Trajectory */}
      {forwardTrajectory && (
        <Polyline
          positions={forwardTrajectory}
          pathOptions={{
            color: '#f43f5e',
            weight: 2,
            dashArray: '3 5',
            opacity: 0.9
          }}
        />
      )}

      {/* Predicted Landfall Marker */}
      {hasLandfall && spill.landfall.has_beached && spill.landfall.landfall_location && (
        <CircleMarker
          center={[spill.landfall.landfall_location.latitude, spill.landfall.landfall_location.longitude]}
          radius={6}
          pathOptions={{
            color: '#ef4444',
            fillColor: '#b91c1c',
            fillOpacity: 0.9,
            weight: 2
          }}
        >
          {zoom >= 6 && (
            <Tooltip
              permanent
              direction="bottom"
              className="!bg-[#0b1220] !border-red-500/50 !text-red-300 !font-mono !text-[10px] !shadow-lg !rounded !px-2 !py-0.5 whitespace-nowrap"
            >
              Predicted Landfall
            </Tooltip>
          )}
        </CircleMarker>
      )}
    </>
  );
}
