import React from 'react';

function formatDetectionTime(dateStr) {
  try {
    const d = new Date(dateStr);
    return d.toUTCString().replace(' GMT', ' UTC');
  } catch {
    return dateStr || '—';
  }
}

export default function DetectedSpillPanel({ spill }) {
  if (!spill) return null;

  // Generate a deterministic incident ID from lat/lng/time to avoid random re-renders
  const incidentId = spill.id
    ? spill.id.replace('SPILL-DETECTED-', 'SPILL-').replace(/\d{13}/,
        () => new Date(parseInt(spill.id.split('-').pop() || Date.now()))
          .toISOString().slice(0,10).replace(/-/g,''))
    : `SPILL-${new Date(spill.detectionTime).toISOString().slice(0,10).replace(/-/g,'')}`;

  return (
    <div className="bg-[#0b1220] border-b border-slate-800/80">
      {/* Header band */}
      <div className="px-4 py-2 border-b border-slate-800/80 bg-slate-900/40 flex items-center gap-2">
        <h2 className="text-[10px] font-bold text-slate-100 uppercase tracking-widest">
          Oil Spill Detection
        </h2>
      </div>

      <div className="px-4 py-3 space-y-3">
        {/* Incident ID */}
        <div>
          <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Incident ID</dt>
          <dd className="text-slate-200 text-[11px] font-mono font-semibold mt-0.5 truncate" title={incidentId}>
            {incidentId}
          </dd>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Detection</dt>
            <dd className="text-slate-300 text-[10px] font-medium mt-0.5">
              {spill.detectionTime ? formatDetectionTime(spill.detectionTime) : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Sensor</dt>
            <dd className="text-slate-300 text-[10px] font-medium mt-0.5">{spill.satellite || '—'}</dd>
          </div>
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Est. Area</dt>
            <dd className="text-slate-100 text-[11px] font-semibold mt-0.5">{spill.areaKm2} km²</dd>
          </div>
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Confidence</dt>
            <dd className="mt-0.5">
              <span className="text-[11px] font-bold text-slate-100">
                {spill.confidencePct}%
              </span>
            </dd>
          </div>
        </div>

        {/* Centroid */}
        <div>
          <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Centroid</dt>
          <dd className="text-slate-300 text-[10px] font-mono mt-0.5">
            {spill.lat >= 0 ? spill.lat.toFixed(4) + '° N' : Math.abs(spill.lat).toFixed(4) + '° S'}
            {' / '}
            {spill.lng >= 0 ? spill.lng.toFixed(4) + '° E' : Math.abs(spill.lng).toFixed(4) + '° W'}
          </dd>
        </div>

        {Number.isFinite(spill.forecast12hLat) && Number.isFinite(spill.forecast12hLon) && (
          <div className="border-t border-cyan-900/50 pt-2">
            <dt className="text-[9px] text-cyan-400 uppercase tracking-wider font-semibold">Predicted Site (+12h)</dt>
            <dd className="text-cyan-100 text-[10px] font-mono mt-0.5">
              {spill.forecast12hLat >= 0 ? spill.forecast12hLat.toFixed(4) + '° N' : Math.abs(spill.forecast12hLat).toFixed(4) + '° S'}
              {' / '}
              {spill.forecast12hLon >= 0 ? spill.forecast12hLon.toFixed(4) + '° E' : Math.abs(spill.forecast12hLon).toFixed(4) + '° W'}
            </dd>
            {spill.forecast12hTime && (
              <dd className="text-slate-400 text-[9px] mt-0.5">
                {new Date(spill.forecast12hTime).toUTCString().replace(' GMT', ' UTC')}
              </dd>
            )}
          </div>
        )}

        {/* Geolocation source badge */}
        {spill.geolocation_source && (
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Location Source</dt>
            <dd className={`text-[10px] font-semibold mt-0.5 ${
              spill.geolocation_source === 'SAR Image Metadata' ? 'text-cyan-400' :
              spill.geolocation_source === 'User Provided' ? 'text-amber-400' : 'text-emerald-400'
            }`}>{spill.geolocation_source}</dd>
          </div>
        )}

        {/* Nearest vessel */}
        {spill.nearVesselName && (
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Nearest Vessel</dt>
            <dd className="text-amber-400 text-[10px] font-semibold mt-0.5">{spill.nearVesselName}</dd>
          </div>
        )}

        {/* Oil type */}
        {spill.oilType && (
          <div>
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Classification</dt>
            <dd className="text-slate-400 text-[10px] mt-0.5">{spill.oilType}</dd>
          </div>
        )}

        {/* Wind */}
        {spill.windSpeedKmh != null && (
          <div className="pt-2 border-t border-slate-800/60">
            <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold mb-1">Environmental</dt>
            <div className="text-[10px] text-slate-400 flex justify-between">
              <span>Wind</span>
              <span className="text-slate-300">{spill.windSpeedKmh} km/h {spill.windDirectionLabel}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
