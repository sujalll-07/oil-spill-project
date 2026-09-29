import React from 'react';
import { AlertTriangle, ShieldCheck, Navigation, MapPin } from 'lucide-react';

export default function CoastalThreatPanel({ spill }) {
  if (!spill) return null;

  const nearestCoast = spill.nearestCoast;
  const trajectoryLandmasses = spill.trajectoryLandmasses || [];
  const landfall = spill.landfall;

  const isSafe = !landfall || landfall.threat_level === 'SAFE' || landfall.threat_level === 'LOW';
  const badgeColor = !landfall ? 'text-slate-400 border-slate-700/50 bg-slate-900/30'
    : isSafe ? 'text-emerald-400 border-emerald-900/50 bg-emerald-950/30'
    : (landfall.threat_level === 'CRITICAL' || landfall.threat_level === 'HIGH')
      ? 'text-red-400 border-red-900/50 bg-red-950/30'
      : 'text-amber-400 border-amber-900/50 bg-amber-950/30';

  return (
    <div className="bg-[#0b1220] border-b border-slate-800/80">
      <div className="px-4 py-2 border-b border-slate-800/80 bg-slate-900/40 flex items-center gap-2">
        <h2 className="text-[10px] font-bold text-slate-100 uppercase tracking-widest">Coastal Threat Assessment</h2>
      </div>

      <div className="px-4 py-3 space-y-3">
        {/* Nearest current landmass — derived from spill lat/lon, not hardcoded */}
        {nearestCoast && (
          <div className="bg-slate-900/40 rounded p-2.5 space-y-1">
            <div className="flex items-center gap-1.5">
              <MapPin className="w-3 h-3 text-cyan-500 flex-shrink-0" />
              <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Nearest Landmass (Current Position)</span>
            </div>
            <div className="text-cyan-300 text-[11px] font-semibold">{nearestCoast.countryName}</div>
            {nearestCoast.regionDescription && nearestCoast.regionDescription !== nearestCoast.countryName && (
              <div className="text-slate-400 text-[10px]">{nearestCoast.regionDescription}</div>
            )}
            <div className="text-slate-400 text-[10px] font-mono">
              {nearestCoast.distanceKm > 0 ? `${nearestCoast.distanceKm} km away` : 'Distance unavailable'}
            </div>
          </div>
        )}

        {/* Trajectory-affected landmasses */}
        {trajectoryLandmasses.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Navigation className="w-3 h-3 text-amber-500 flex-shrink-0" />
              <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Trajectory — At-Risk Landmasses</span>
            </div>
            {trajectoryLandmasses.map((lm, idx) => (
              <div key={idx} className="bg-amber-950/20 border border-amber-800/30 rounded px-2.5 py-1.5">
                <div className="text-amber-300 text-[10px] font-semibold">{lm.country_name}</div>
                <div className="text-slate-400 text-[10px] flex justify-between mt-0.5">
                  <span>{lm.approach_distance_km} km approach distance</span>
                  <span className="font-mono">T+{lm.eta_hours}h ETA</span>
                </div>
                {lm.already_crossed && (
                  <div className="text-red-400 text-[9px] font-semibold mt-0.5">⚠ Particles already ashore</div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Threat badge */}
        {landfall && (
          <>
            <div className={`px-2 py-1.5 border rounded flex items-center gap-2 ${badgeColor}`}>
              {isSafe ? <ShieldCheck className="w-4 h-4 flex-shrink-0" /> : <AlertTriangle className="w-4 h-4 flex-shrink-0" />}
              <span className="text-[10px] font-bold uppercase tracking-wider">
                {landfall.threat_badge?.replace(/\[|\]/g, '') || landfall.threat_level}
              </span>
            </div>

            <div>
              <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Advisory</dt>
              <dd className="text-slate-300 text-[10px] mt-1 leading-relaxed">{landfall.threat_description}</dd>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              <div>
                <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Classification</dt>
                <dd className="text-slate-300 text-[10px] font-medium mt-0.5">{landfall.drift_classification?.replace(/_/g, ' ')}</dd>
              </div>
              <div>
                <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Dist to Coast</dt>
                <dd className="text-slate-300 text-[10px] font-medium mt-0.5">{landfall.final_distance_to_coast_km} km</dd>
              </div>
              {landfall.has_beached && (
                <>
                  <div>
                    <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">ETA</dt>
                    <dd className="text-red-400 text-[11px] font-bold mt-0.5">{landfall.first_landfall_hours} hrs</dd>
                  </div>
                  <div>
                    <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Beached Mass</dt>
                    <dd className="text-slate-100 text-[11px] font-semibold mt-0.5">{landfall.beached_percentage}%</dd>
                  </div>
                </>
              )}
            </div>

            {landfall.has_beached && landfall.landfall_location && (
              <div className="pt-2 border-t border-slate-800/60">
                <dt className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold mb-1">Impact Region</dt>
                <dd className="text-amber-400 text-[10px] font-semibold">{landfall.landfall_location.region_name}</dd>
                <dd className="text-slate-400 text-[10px] font-mono mt-0.5">
                  {landfall.landfall_location.latitude?.toFixed(4)}° / {landfall.landfall_location.longitude?.toFixed(4)}°
                </dd>
              </div>
            )}
          </>
        )}

        {!nearestCoast && !landfall && (
          <div className="text-slate-600 text-[10px] text-center py-2">Coastal analysis available after drift run</div>
        )}
      </div>
    </div>
  );
}
