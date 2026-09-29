import React, { useMemo, useState } from 'react';

function FactorRow({ factor, onClick }) {
  const color = factor.data_available
    ? factor.score >= 70 ? 'bg-red-500' : factor.score >= 40 ? 'bg-amber-500' : 'bg-slate-600'
    : 'bg-slate-800';
  return (
    <div
      onClick={onClick}
      className="space-y-0.5 group cursor-pointer hover:bg-slate-800/80 p-1.5 rounded transition-colors border border-transparent hover:border-slate-700/60"
      title="Click to view full details of this evidence factor on the front screen"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-slate-300 group-hover:text-cyan-400 group-hover:underline truncate flex-1 font-medium">
          {factor.factor}
        </span>
        {factor.data_available ? (
          <span className="text-[9px] font-mono font-semibold text-slate-300 group-hover:text-cyan-300 flex-shrink-0 w-8 text-right">
            {Math.round(factor.score)}
          </span>
        ) : (
          <span className="text-[9px] text-slate-600 flex-shrink-0">N/A</span>
        )}
      </div>
      <div className="h-0.5 bg-slate-800 rounded">
        <div className={`h-full rounded transition-all ${color}`} style={{ width: factor.data_available ? `${factor.score}%` : '0%' }} />
      </div>
      {factor.data_available && (
        <p className="text-[9px] text-slate-500 group-hover:text-slate-300 leading-tight truncate" title={factor.detail}>
          {factor.detail}
        </p>
      )}
    </div>
  );
}

function VesselCard({ vessel, suspectRank, onSelectVessel, onSelectEvidenceFactor, hasSpillResults }) {
  const [showFactors, setShowFactors] = useState(true);
  const isSuspect = vessel.isSuspect;
  const statusLabel = (vessel.navStatus || '').toLowerCase();
  let statusBadgeClass = 'text-slate-500';
  if (statusLabel.includes('underway')) statusBadgeClass = 'text-emerald-400';
  else if (statusLabel.includes('anchor') || statusLabel.includes('moor')) statusBadgeClass = 'text-amber-400';
  else if (statusLabel.includes('fishing')) statusBadgeClass = 'text-purple-400';

  const handleCardClick = () => {
    if (isSuspect && hasSpillResults && onSelectEvidenceFactor) {
      // Go directly to front screen evidence factor details, NOT vessel info map popup
      onSelectEvidenceFactor(vessel, suspectRank, null);
    } else if (onSelectVessel) {
      onSelectVessel(vessel);
    }
  };

  return (
    <div className={`rounded-xl border transition-colors ${
      isSuspect && hasSpillResults
        ? 'bg-red-950/20 border-red-700/50 shadow-md shadow-red-950/20'
        : 'bg-slate-900/60 border-slate-800/60'
    } p-3`}>
      <button
        className="w-full text-left cursor-pointer group"
        onClick={handleCardClick}
        title={isSuspect && hasSpillResults ? 'Click to view front screen evidence details' : 'Click to locate vessel on map'}
      >
        <div className="flex items-start justify-between gap-1 mb-1.5">
          <div className="flex-1 min-w-0">
            {isSuspect && hasSpillResults && (
              <div className="text-[9px] font-extrabold text-red-400 uppercase tracking-wider mb-0.5 flex items-center gap-1">
                <span>⚑ SUSPECT #{suspectRank || 1}</span>
              </div>
            )}
            <div className={`font-semibold text-[11px] truncate leading-tight group-hover:underline ${
              isSuspect && hasSpillResults ? 'text-red-200 group-hover:text-red-100' : 'text-slate-200 group-hover:text-cyan-300'
            }`}>
              {vessel.name || 'UNKNOWN'}
            </div>
            <div className="text-[10px] text-slate-500 truncate mt-0.5">{vessel.type || 'Vessel'}</div>
          </div>
          {vessel.distanceKm < 900 && (
            <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded flex-shrink-0 ${
              isSuspect && hasSpillResults
                ? 'bg-red-900/40 text-red-300 border border-red-700/40'
                : 'bg-slate-800 text-slate-400 border border-slate-700/60'
            }`}>{vessel.distanceKm} km</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
          <div className="flex gap-1"><span className="text-slate-600">MMSI</span><span className="text-slate-400 font-mono">{vessel.mmsi || '—'}</span></div>
          <div className="flex gap-1"><span className="text-slate-600">Spd</span><span className="text-slate-300 font-mono">{vessel.sog != null ? `${vessel.sog} kn` : '—'}</span></div>
          <div className={`flex gap-1 col-span-2 ${statusBadgeClass}`}><span className="text-slate-600">Nav</span><span className="truncate">{vessel.navStatus || '—'}</span></div>
          {isSuspect && hasSpillResults && vessel.attributionScore != null && (
            <div className="flex justify-between col-span-2 mt-1 pt-1 border-t border-red-900/30">
              <span className="text-slate-500">Attribution score</span>
              <span className="text-red-300 font-bold font-mono">{vessel.attributionScore?.toFixed(1)}%</span>
            </div>
          )}
        </div>
      </button>

      {/* Attribution factor breakdown — suspects only, when results available */}
      {isSuspect && hasSpillResults && vessel.attributionFactors?.length > 0 && (
        <div className="mt-2 pt-2 border-t border-red-900/30">
          <div className="flex items-center justify-between mb-1">
            <button
              className="text-[9px] text-slate-500 hover:text-slate-300 uppercase tracking-wider font-semibold cursor-pointer"
              onClick={() => setShowFactors(f => !f)}
            >
              {showFactors ? '▲ Hide' : '▼ Show'} Evidence Factors
            </button>
            <span className="text-[8px] text-cyan-400 font-semibold tracking-tight">Click factor for front screen</span>
          </div>

          {showFactors && (
            <div className="mt-1.5 space-y-1">
              {vessel.attributionFactors.map((f, i) => (
                <FactorRow
                  key={i}
                  factor={f}
                  onClick={() => onSelectEvidenceFactor && onSelectEvidenceFactor(vessel, suspectRank, f)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function NearbyVesselsPanel({
  vessels = [],
  suspects = [],
  onSelectVessel,
  onSelectEvidenceFactor,
  onViewFullList,
  activeSpill,
  hasSpillResults
}) {
  const sortedVessels = useMemo(() => {
    if (hasSpillResults) {
      // Suspects first (by attribution score), then others by distance
      const susp = [...vessels].filter(v => v.isSuspect).sort((a, b) => (b.attributionScore ?? 0) - (a.attributionScore ?? 0));
      const others = [...vessels].filter(v => !v.isSuspect).sort((a, b) => a.distanceKm - b.distanceKm);
      return [...susp, ...others];
    }
    return [...vessels].sort((a, b) => a.distanceKm - b.distanceKm);
  }, [vessels, hasSpillResults]);

  const stats = useMemo(() => ({
    underway: vessels.filter(v => (v.navStatus || '').toLowerCase().includes('underway')).length,
    anchored: vessels.filter(v => { const s = (v.navStatus || '').toLowerCase(); return s.includes('anchor') || s.includes('moor'); }).length,
    suspects: vessels.filter(v => v.isSuspect).length,
  }), [vessels]);

  let suspectCounter = 0;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#0b1220]">
      <div className="px-4 py-2.5 border-b border-slate-800/80">
        <div className="flex items-center justify-between">
          <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            {hasSpillResults ? 'Vessel Attribution' : 'Nearby Vessels'}
          </h2>
          {vessels.length > 0 && <span className="text-[10px] text-slate-500 font-mono">{vessels.length} tracked</span>}
        </div>
      </div>

      {!hasSpillResults && !activeSpill && (
        <div className="px-4 py-3 border-b border-slate-800/40 bg-slate-900/20">
          <p className="text-[10px] text-slate-600 leading-relaxed">
            Vessel attribution and suspicion ranking are available after an oil spill is detected via SAR and drift analysis is run.
          </p>
        </div>
      )}

      {vessels.length > 0 && (
        <div className="px-4 py-2 border-b border-slate-800/60 bg-slate-900/40">
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
            {hasSpillResults && stats.suspects > 0 && (
              <div className="flex justify-between col-span-2">
                <span className="text-red-400 font-semibold">⚑ Suspects</span>
                <span className="text-red-300 font-bold">{stats.suspects}</span>
              </div>
            )}
            <div className="flex justify-between"><span className="text-slate-500">Underway</span><span className="text-emerald-400 font-semibold">{stats.underway}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Anchored</span><span className="text-amber-400 font-semibold">{stats.anchored}</span></div>
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-2">
        {vessels.length === 0 ? (
          <div className="text-center py-10 px-4">
            <div className="text-slate-500 text-[11px]">NO VESSELS TRACKED</div>
            <div className="text-slate-600 text-[10px] mt-2">Click "Load Live AIS Data" in the top bar to fetch AIS vessel traffic.</div>
          </div>
        ) : (
          sortedVessels.map((vessel) => {
            let rank = null;
            if (vessel.isSuspect && hasSpillResults) {
              suspectCounter++;
              rank = suspectCounter;
            }
            return (
              <VesselCard
                key={vessel.id}
                vessel={vessel}
                suspectRank={rank}
                onSelectVessel={onSelectVessel}
                onSelectEvidenceFactor={onSelectEvidenceFactor}
                hasSpillResults={hasSpillResults}
              />
            );
          })
        )}
      </div>

      <div className="px-3 py-2 border-t border-slate-800/80">
        <button onClick={onViewFullList}
          className="w-full border border-slate-700/60 hover:border-slate-600 hover:bg-slate-800/30 text-slate-500 hover:text-slate-300 text-[10px] font-semibold py-1.5 px-4 rounded transition-colors text-center uppercase tracking-wider cursor-pointer">
          View Full AIS Registry →
        </button>
      </div>
    </div>
  );
}
