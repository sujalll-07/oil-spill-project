import React, { useState, useEffect } from 'react';
import { Waves, ChevronDown, ChevronRight } from 'lucide-react';

function formatUTC(date) {
  return date.toUTCString().replace(' GMT', ' UTC').split(' ').slice(4).join(' ');
}

export default function LayerControlPanel({
  layers,
  onToggleLayer,
  baseMap,
  onBaseMapChange,
  onImageUpload,
  isAnalyzingImage,
  imageAnalysisResult,
  backendOnline,
  analysisData,
  uploadedFileName,
  workflowState,
  aisVessels,
  platformsCount = { india: 0, ior: 0 },
}) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [aisLoadedAt, setAisLoadedAt] = useState(null);
  const [isLegendOpen, setIsLegendOpen] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (analysisData?.vessels?.length > 0) {
      setAisLoadedAt(new Date());
    }
  }, [analysisData]);

  const layerMeta = {
    spill:     { label: 'Oil Spill Layer',    color: 'bg-red-500' },
    ais:       { label: 'AIS Vessels',        color: 'bg-cyan-500' },
    platforms: { label: 'Suspect Vessels',    color: 'bg-red-400' },
    platformsIndia: { label: 'India EEZ Rigs/Platforms', color: 'bg-amber-400', badge: `${platformsCount.india}` },
    platformsIOR: { label: 'Regional IOR Rigs', color: 'bg-purple-400', badge: `${platformsCount.ior}` },
  };

  const vesselCount = analysisData?.vessels?.length ?? 0;

  // Compute stale status (>5 min)
  const isAisStale = aisLoadedAt
    ? (currentTime - aisLoadedAt) > 5 * 60 * 1000
    : false;

  let aisStatus = 'OFFLINE';
  let aisStatusColor = 'text-slate-400';
  let aisDotColor = 'bg-slate-500';
  if (backendOnline === null) {
    aisStatus = 'CHECKING'; aisStatusColor = 'text-slate-400'; aisDotColor = 'bg-slate-500';
  } else if (backendOnline === false) {
    aisStatus = 'OFFLINE'; aisStatusColor = 'text-red-400'; aisDotColor = 'bg-red-500';
  } else if (backendOnline === true && vesselCount > 0 && isAisStale) {
    aisStatus = 'STALE'; aisStatusColor = 'text-amber-400'; aisDotColor = 'bg-amber-500';
  } else if (backendOnline === true && vesselCount > 0) {
    aisStatus = 'LIVE'; aisStatusColor = 'text-emerald-400'; aisDotColor = 'bg-emerald-400';
  } else if (backendOnline === true) {
    aisStatus = 'READY'; aisStatusColor = 'text-cyan-400'; aisDotColor = 'bg-cyan-400';
  }

  const sarStatus = backendOnline ? 'READY' : 'OFFLINE';

  return (
    <div className="w-[240px] h-full overflow-y-auto no-scrollbar bg-[#0b1220] border-r border-slate-800/80 flex flex-col select-none text-slate-300">

      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800/80 flex items-center gap-2">
        <Waves className="h-4 w-4 text-cyan-500 flex-shrink-0" />
        <div>
          <h1 className="text-[11px] font-bold text-slate-100 uppercase tracking-widest leading-tight">
            Maritime OilScan
          </h1>
        </div>
      </div>

      {/* System clock */}
      <div className="px-4 py-2 border-b border-slate-800/60 bg-slate-950/40">
        <div className="text-[10px] text-slate-500 uppercase tracking-wider">System Time</div>
        <div className="text-xs font-mono text-slate-300 mt-0.5">{formatUTC(currentTime)}</div>
      </div>

      {/* Workflow progress indicator */}
      {workflowState && workflowState !== 'IDLE' && (
        <div className="px-4 py-2 border-b border-slate-800/60 bg-amber-950/20">
          <div className="text-[9px] text-slate-500 uppercase tracking-wider mb-1.5">Workflow Status</div>
          <div className="space-y-1">
            {[
              { key: 'SAR_UPLOADING', label: 'SAR Analysis',        done: ['SPILL_CONFIRMED','NO_SPILL','RUNNING_DRIFT','RESULTS_READY'].includes(workflowState) },
              { key: 'SPILL_CONFIRMED', label: 'Spill Confirmed',   done: ['RUNNING_DRIFT','RESULTS_READY'].includes(workflowState) },
              { key: 'RUNNING_DRIFT', label: 'Drift + Attribution', done: workflowState === 'RESULTS_READY' },
              { key: 'RESULTS_READY', label: 'Results Ready',       done: workflowState === 'RESULTS_READY' },
            ].map(({ key, label, done }) => {
              const active = workflowState === key;
              return (
                <div key={key} className="flex items-center gap-1.5 text-[9px]">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    done ? 'bg-emerald-400' : active ? 'bg-amber-400 animate-pulse' : 'bg-slate-700'
                  }`} />
                  <span className={done ? 'text-emerald-400' : active ? 'text-amber-300' : 'text-slate-600'}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto no-scrollbar">

        {/* System Status */}
        <div className="px-4 py-3 border-b border-slate-800/60">
          <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            System Status
          </h2>
          <div className="space-y-1.5">
            {[
              { label: 'AIS',            status: aisStatus, color: aisStatusColor, dot: aisDotColor },
              { label: 'SAR Processing', status: sarStatus, color: backendOnline ? 'text-cyan-400' : 'text-red-400', dot: backendOnline ? 'bg-cyan-400' : 'bg-red-500' },
              { label: 'Drift Model',    status: backendOnline ? 'READY' : 'OFFLINE', color: backendOnline ? 'text-cyan-400' : 'text-slate-500', dot: backendOnline ? 'bg-cyan-400' : 'bg-slate-600' },
              { label: 'Offshore Rigs',  status: 'LOADED', color: 'text-amber-400', dot: 'bg-amber-400' },
            ].map(({ label, status, color, dot }) => (
              <div key={label} className="flex items-center justify-between text-[10px]">
                <span className="text-slate-500">{label}</span>
                <span className={`flex items-center gap-1.5 font-semibold ${color}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${dot} flex-shrink-0`} />
                  {status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* AIS Status block */}
        {backendOnline && (
          <div className="px-4 py-3 border-b border-slate-800/60 bg-slate-900/40">
            <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
              AIS Data Feed
            </h2>
            <div className="space-y-1 text-[10px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <span className={`font-semibold ${aisStatusColor}`}>{aisStatus}</span>
              </div>
              {aisLoadedAt && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Last update</span>
                  <span className="text-slate-300 font-mono">{formatUTC(aisLoadedAt)}</span>
                </div>
              )}
              {vesselCount > 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Vessels tracked</span>
                  <span className="text-slate-200 font-semibold">{vesselCount}</span>
                </div>
              )}

            </div>
          </div>
        )}

        {/* Layer Controls */}
        <div className="px-4 py-3 border-b border-slate-800/60">
          <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Map Layers
          </h2>
          <div className="space-y-1">
            {Object.entries(layerMeta).map(([key, meta]) => (
              <label
                key={key}
                className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-slate-800/40 cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-2 truncate pr-1">
                  <span className="text-[11px] text-slate-400">{meta.label}</span>
                  {meta.badge && <span className="text-[9px] px-1 py-0.2 bg-slate-800 text-slate-400 rounded font-mono">{meta.badge}</span>}
                </div>
                <input
                  type="checkbox"
                  checked={!!layers[key]}
                  onChange={() => onToggleLayer(key)}
                  className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-900 h-3.5 w-3.5"
                />
              </label>
            ))}
          </div>
        </div>



        {/* SAR Image Analysis */}
        <div className="px-4 py-3 border-b border-slate-800/60">
          <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            SAR Image Analysis
          </h2>

          <div className="space-y-2">
            <div className="text-[10px] text-slate-500 space-y-1">
              <div className="flex justify-between">
                <span>Sensor</span><span className="text-slate-400">Sentinel-1 SAR</span>
              </div>
              <div className="flex justify-between">
                <span>Mode</span><span className="text-slate-400">IW</span>
              </div>
              <div className="flex justify-between">
                <span>Polarization</span><span className="text-slate-400">VV/VH</span>
              </div>
            </div>

            <label className="block">
              <span className="sr-only">Upload SAR Image</span>
              <input
                type="file"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    onImageUpload(e.target.files[0]);
                  }
                }}
                disabled={isAnalyzingImage}
                className="block w-full text-[10px] text-slate-400 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-semibold file:bg-slate-800 file:text-slate-300 hover:file:bg-slate-700 disabled:opacity-50 cursor-pointer"
              />
            </label>

            {uploadedFileName && !isAnalyzingImage && (
              <div className="text-[10px] text-slate-500 truncate" title={uploadedFileName}>
                File: <span className="text-slate-400">{uploadedFileName}</span>
              </div>
            )}

            {isAnalyzingImage && (
              <div className="flex items-center gap-1.5 text-[10px] text-cyan-400">
                <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing SAR image…
              </div>
            )}

            {imageAnalysisResult && !isAnalyzingImage && (
              <div className={`p-2 rounded text-[10px] border space-y-1.5 ${
                imageAnalysisResult.is_spill
                  ? 'bg-red-950/30 border-red-800/50'
                  : 'bg-slate-900/60 border-slate-700/50'
              }`}>
                <div className={`font-bold text-[11px] uppercase tracking-wide ${
                  imageAnalysisResult.is_spill ? 'text-red-300' : 'text-slate-300'
                }`}>
                  {imageAnalysisResult.is_spill
                    ? '⚠ Potential Slick Detected'
                    : '✓ No Slick Detected'}
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Oil-spill probability</span>
                  <span className="font-mono text-slate-300">{imageAnalysisResult.oil_spill_pct?.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Model confidence</span>
                  <span className="font-mono text-slate-300">
                    {imageAnalysisResult.is_spill
                      ? imageAnalysisResult.oil_spill_pct?.toFixed(2)
                      : imageAnalysisResult.no_oil_spill_pct?.toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Processing</span>
                  <span className="text-emerald-400">Complete</span>
                </div>
                {imageAnalysisResult.is_spill && imageAnalysisResult.lat != null && (
                  <div className="pt-1 border-t border-slate-700/50 space-y-1">
                    <div className="flex justify-between text-slate-500">
                      <span>Centroid</span>
                      <span className="font-mono text-slate-300 text-right">
                        {Math.abs(imageAnalysisResult.lat).toFixed(4)}° {imageAnalysisResult.lat >= 0 ? 'N' : 'S'}<br />
                        {Math.abs(imageAnalysisResult.lng).toFixed(4)}° {imageAnalysisResult.lng >= 0 ? 'E' : 'W'}
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-500">
                      <span>Detection time</span>
                      <span className="text-slate-300">{formatUTC(new Date())}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Data Sources */}
        <div className="px-4 py-3 border-b border-slate-800/60">
          <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Data Sources
          </h2>
          <div className="space-y-1.5 text-[10px]">
            {[
              { label: 'Sentinel-1 SAR', status: backendOnline ? 'CONNECTED' : 'UNAVAILABLE', ok: !!backendOnline },
              { label: 'AIS (AISStream)', status: backendOnline ? 'CONNECTED' : 'UNAVAILABLE', ok: !!backendOnline },
              { label: 'Offshore Rigs (DGH/ONGC)', status: 'VERIFIED', ok: true },
            ].map(({ label, status, ok }) => (
              <div key={label} className="flex justify-between items-center">
                <span className="text-slate-500">{label}</span>
                <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase ${
                  ok ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                     : status === 'SIMULATED'
                       ? 'bg-amber-950/40 text-amber-500 border border-amber-800/40'
                       : 'bg-slate-800 text-slate-500 border border-slate-700'
                }`}>
                  {status}
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Legend */}
      <div className="border-t border-slate-800/80 bg-slate-950/50">
        <button
          onClick={() => setIsLegendOpen(!isLegendOpen)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-900/50 transition-colors focus:outline-none cursor-pointer"
        >
          <h2 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Legend</h2>
          {isLegendOpen ? (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-500" />
          )}
        </button>
        {isLegendOpen && (
          <div className="px-4 pb-3 space-y-1.5 text-[10px] text-slate-500">
            <div className="flex items-center gap-2.5">
              <span className="w-3 h-3 border border-dashed border-red-500 bg-red-950/30 rounded-sm flex-shrink-0" />
              <span>Oil Spill Polygon</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
              <span>Suspect Vessel</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
              <span>Underway</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
              <span>Anchored / Moored</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 flex-shrink-0" />
              <span>AIS Vessel</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-3.5 h-3.5 rounded bg-sky-950/60 border border-sky-400 flex items-center justify-center text-[9px] text-sky-400 flex-shrink-0">🛢</span>
              <span>India EEZ Oil Platform (Fixed)</span>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="w-3.5 h-3.5 rounded bg-purple-950/60 border border-purple-400 flex items-center justify-center text-[9px] text-purple-300 flex-shrink-0">🛢</span>
              <span>Regional IOR Platform (Fixed)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
