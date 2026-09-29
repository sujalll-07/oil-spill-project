import React, { useState } from 'react';
import { X, ShieldAlert, AlertTriangle, Crosshair, MapPin, CheckCircle2, ChevronRight, BarChart3, Info } from 'lucide-react';

const FACTOR_INFO = {
  'Spatial Proximity': {
    weight: '18%',
    category: 'Geographic Assessment',
    description: 'Evaluates spatial distance between the vessel and the detected oil spill location. Vessels closer to the spill origin receive significantly higher attribution weights based on exponential decay functions.',
  },
  'Temporal Compatibility': {
    weight: '15%',
    category: 'Time Window Analysis',
    description: 'Calculates the estimated vessel position at the exact time of spill detection using AIS velocity and course data. Measures time alignment with discharge onset.',
  },
  'Trajectory Intersection': {
    weight: '15%',
    category: 'Track Analysis',
    description: 'Analyzes the historical 12-hour AIS track of the vessel to check for spatial intersection or close approach along the back-projected spill path.',
  },
  'AIS Reporting Gap': {
    weight: '14%',
    category: 'Anomalous AIS Behavior',
    description: 'Detects transponder silence or dark periods in AIS broadcasts. Silence during passage through the spill region is a strong indicator of deliberate evasion.',
  },
  'Vessel Type': {
    weight: '8%',
    category: 'Cargo & Risk Classification',
    description: 'Classifies vessel hazard level. Crude oil tankers, chemical carriers, and oil product tankers carry the highest risk profile for operational or accidental discharge.',
  },
  'Behaviour Anomalies': {
    weight: '15%',
    category: 'Navigation Pattern',
    description: 'Identifies suspicious maneuvering such as loitering, sudden speed drops, sharp course deviations, or slow speed drifting typical of tank washing operations.',
  },
  'Hindcast Proximity': {
    weight: '10%',
    category: 'Lagrangian Back-Drift',
    description: 'Measures distance between the vessel path and the reverse Lagrangian particle drift origin cloud computed from ocean current and wind vectors.',
  },
  'Radar Confirmation': {
    weight: '5%',
    category: 'SAR Target Match',
    description: 'Cross-references Synthetic Aperture Radar (SAR) hard target reflections with broadcast AIS positions to verify vessel presence at satellite image acquisition time.',
  },
};

export default function EvidenceFactorModal({ vessel, suspectRank, initialFactor, onClose, onLocateVessel }) {
  if (!vessel) return null;

  const factors = vessel.attributionFactors || [];
  const [selectedFactorName, setSelectedFactorName] = useState(
    initialFactor?.factor || (factors.length > 0 ? factors[0].factor : null)
  );

  const activeFactorObj = factors.find(f => f.factor === selectedFactorName) || factors[0];
  const activeFactorMeta = activeFactorObj ? (FACTOR_INFO[activeFactorObj.factor] || {
    weight: '—',
    category: 'Evidence Factor',
    description: 'Multi-factor evidence contribution calculated by vessel attribution engine.'
  }) : null;

  const score = vessel.attributionScore ?? vessel.suspicionScore ?? 0;
  const isHighRisk = score >= 75;

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md z-[9999] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200">
      <div className="bg-[#0b1220] border border-red-900/60 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl text-slate-200">
        
        {/* Top Header Banner */}
        <div className="px-6 py-4 bg-gradient-to-r from-red-950/80 via-[#0d1627] to-[#0b1220] border-b border-red-900/40 flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="flex flex-col items-center justify-center bg-red-950/90 border border-red-700/60 rounded-xl px-3.5 py-2 text-center min-w-[90px]">
              <span className="text-[10px] font-bold text-red-400 uppercase tracking-widest">RANK</span>
              <span className="text-2xl font-black text-red-200 font-mono leading-none mt-0.5">
                #{suspectRank || 1}
              </span>
              <span className="text-[9px] text-red-300/80 uppercase font-semibold mt-1">SUSPECT</span>
            </div>

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-extrabold text-slate-100 tracking-tight">{vessel.name || 'UNKNOWN VESSEL'}</h2>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-red-900/40 border border-red-700/50 text-red-300 font-bold uppercase tracking-wider">
                  ⚑ Suspect #{suspectRank || 1}
                </span>
              </div>

              <p className="text-xs text-slate-400 mt-1 flex items-center gap-3 flex-wrap">
                <span><strong className="text-slate-300">Type:</strong> {vessel.type || 'Vessel'}</span>
                <span>•</span>
                <span><strong className="text-slate-300">MMSI:</strong> <code className="font-mono text-slate-300">{vessel.mmsi || '—'}</code></span>
                {vessel.imo && vessel.imo !== 'N/A' && (
                  <>
                    <span>•</span>
                    <span><strong className="text-slate-300">IMO:</strong> <code className="font-mono text-slate-300">{vessel.imo}</code></span>
                  </>
                )}
                <span>•</span>
                <span><strong className="text-slate-300">Speed:</strong> {vessel.sog != null ? `${vessel.sog} kn` : '—'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="text-right">
              <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Attribution Match Score</div>
              <div className={`text-2xl font-black font-mono ${isHighRisk ? 'text-red-400' : 'text-amber-400'}`}>
                {score.toFixed(1)}%
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 rounded-xl transition-colors cursor-pointer"
              title="Close Evidence Factors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content Body: Left Column List of Factors, Right Column Deep Dive Details */}
        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-slate-800/80 overflow-hidden">
          
          {/* Left Panel: Factor Selector List */}
          <div className="md:col-span-5 flex flex-col h-full bg-[#080d17] overflow-y-auto p-4 space-y-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/60 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5 text-cyan-400" /> Evidence Factor Breakdown
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{factors.length} Factors Evaluated</span>
            </div>

            {factors.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">No individual evidence factors recorded.</div>
            ) : (
              factors.map((f, i) => {
                const isSelected = f.factor === selectedFactorName;
                const meta = FACTOR_INFO[f.factor] || {};
                const scoreColor = !f.data_available 
                  ? 'bg-slate-700 text-slate-500' 
                  : f.score >= 70 ? 'bg-red-500 text-white' : f.score >= 40 ? 'bg-amber-500 text-black' : 'bg-slate-600 text-slate-200';
                const barColor = !f.data_available
                  ? 'bg-slate-800'
                  : f.score >= 70 ? 'bg-red-500' : f.score >= 40 ? 'bg-amber-500' : 'bg-cyan-600';

                return (
                  <button
                    key={i}
                    onClick={() => setSelectedFactorName(f.factor)}
                    className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-red-950/40 border-red-500/70 shadow-lg shadow-red-950/30'
                        : 'bg-slate-900/50 border-slate-800/80 hover:bg-slate-800/60 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`text-xs font-semibold truncate ${isSelected ? 'text-red-200 font-bold' : 'text-slate-300'}`}>
                          {f.factor}
                        </span>
                        {meta.weight && (
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                            {meta.weight}
                          </span>
                        )}
                      </div>
                      <span className={`text-[10px] font-mono font-extrabold px-1.5 py-0.5 rounded flex-shrink-0 ${scoreColor}`}>
                        {f.data_available ? Math.round(f.score) : 'N/A'}
                      </span>
                    </div>

                    <div className="h-1 bg-slate-800 rounded-full overflow-hidden w-full">
                      <div className={`h-full rounded-full transition-all duration-300 ${barColor}`} style={{ width: f.data_available ? `${f.score}%` : '0%' }} />
                    </div>

                    <p className="text-[10px] text-slate-400 truncate leading-snug">
                      {f.detail || 'Data analyzed'}
                    </p>
                  </button>
                );
              })
            )}
          </div>

          {/* Right Panel: Selected Evidence Factor Deep Dive */}
          <div className="md:col-span-7 flex flex-col h-full bg-[#0b1220] p-6 overflow-y-auto">
            {activeFactorObj ? (
              <div className="space-y-6">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-1">
                    <Info className="w-3.5 h-3.5" />
                    <span>{activeFactorMeta.category}</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-400 font-mono">Weight: {activeFactorMeta.weight}</span>
                  </div>
                  <h3 className="text-xl font-bold text-slate-100">{activeFactorObj.factor}</h3>
                </div>

                {/* Score Banner */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4">
                  <div>
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Factor Match Confidence</div>
                    <div className="text-sm text-slate-200 mt-0.5 font-medium">
                      {activeFactorObj.data_available ? (
                        activeFactorObj.score >= 70 
                          ? 'HIGH CORRELATION — Strong Evidence of Oil Spill Attribution'
                          : activeFactorObj.score >= 40
                          ? 'MODERATE CORRELATION — Secondary Contributing Factor'
                          : 'LOW CORRELATION — Minor Indicator'
                      ) : 'DATA UNAVAILABLE'}
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0">
                    <div className="text-3xl font-black font-mono text-slate-100">
                      {activeFactorObj.data_available ? `${Math.round(activeFactorObj.score)}/100` : 'N/A'}
                    </div>
                  </div>
                </div>

                {/* Detailed Findings */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">Empirical Findings &amp; Detail</h4>
                  <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-4">
                    <p className="text-sm font-mono text-red-200 leading-relaxed">
                      "{activeFactorObj.detail}"
                    </p>
                  </div>
                </div>

                {/* Methodology & Context */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">Attribution Methodology &amp; Risk Context</h4>
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/40 border border-slate-800/80 rounded-xl p-4">
                    {activeFactorMeta.description}
                  </p>
                </div>

                {/* Vessel Position Summary */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-xs space-y-2">
                  <div className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">Suspect Position Summary</div>
                  <div className="grid grid-cols-2 gap-3 text-slate-400">
                    <div>Coordinates: <span className="font-mono text-slate-200">{vessel.lat?.toFixed(4)}°N, {vessel.lng?.toFixed(4)}°E</span></div>
                    <div>Distance to Spill: <span className="font-mono text-slate-200">{vessel.distanceKm} km</span></div>
                    <div>Navigational Status: <span className="text-slate-200">{vessel.navStatus || '—'}</span></div>
                    <div>Course / Speed: <span className="font-mono text-slate-200">{vessel.cog}° / {vessel.sog} kn</span></div>
                  </div>
                </div>

              </div>
            ) : (
              <div className="text-slate-500 text-sm py-12 text-center">Select an evidence factor from the left list to view details.</div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3 bg-[#080d17] border-t border-slate-800/80 flex items-center justify-between">
          <button
            onClick={() => {
              if (onLocateVessel) onLocateVessel(vessel);
              onClose();
            }}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700/80 text-xs font-bold px-4 py-2 rounded-xl transition-colors cursor-pointer"
          >
            <Crosshair className="w-4 h-4" /> Locate Suspect #{suspectRank || 1} on Map
          </button>

          <button
            onClick={onClose}
            className="bg-red-950/80 hover:bg-red-900 border border-red-700/60 text-red-200 text-xs font-bold px-5 py-2 rounded-xl transition-colors cursor-pointer"
          >
            Close Front Screen Details
          </button>
        </div>

      </div>
    </div>
  );
}
