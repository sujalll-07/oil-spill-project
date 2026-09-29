import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { MapContainer, TileLayer, ScaleControl, useMap, Popup } from 'react-leaflet';
import L from 'leaflet';
import { Search, X, Play, Loader2, AlertTriangle, CheckCircle2, WifiOff, MapPin, Crosshair } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

import LayerControlPanel from './LayerControlPanel';
import DetectedSpillPanel from './DetectedSpillPanel';
import CoastalThreatPanel from './CoastalThreatPanel';
import NearbyVesselsPanel from './NearbyVesselsPanel';
import EvidenceFactorModal from './EvidenceFactorModal';
import VesselMarker from './VesselMarker';
import PlatformMarker from './PlatformMarker';
import OilSpillLayer from './OilSpillLayer';
import { mockPlatforms } from '../../data/mockOilSpillData';
import { getVessels, checkStatus, analyzeSarImage, runDriftAnalysisFromSpill } from '../../services/api';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Workflow states
const WORKFLOW = {
  IDLE: 'IDLE',
  SAR_UPLOADING: 'SAR_UPLOADING',
  SPILL_CONFIRMED: 'SPILL_CONFIRMED',    // spill detected, need coords
  NO_SPILL: 'NO_SPILL',                  // SAR says no spill
  RUNNING_DRIFT: 'RUNNING_DRIFT',        // drift analysis in progress
  RESULTS_READY: 'RESULTS_READY',
};

function MapController({ selectedVessel, activeSpill }) {
  const map = useMap();
  useEffect(() => {
    if (selectedVessel) {
      map.flyTo([selectedVessel.lat, selectedVessel.lng], 12);
    } else if (activeSpill) {
      map.flyTo([activeSpill.lat, activeSpill.lng], 8);
    }
  }, [selectedVessel, activeSpill, map]);
  return null;
}

export default function MapView() {
  const [layers, setLayers] = useState({
    spill: true,
    ais: true,
    platforms: true,
    platformsIndia: true,
    platformsIOR: true,
  });
  const [baseMap, setBaseMap] = useState('satellite');
  const [selectedVessel, setSelectedVessel] = useState(null);
  const [activeEvidenceModal, setActiveEvidenceModal] = useState(null);
  const [isVesselListOpen, setIsVesselListOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState('distanceKm');
  const [sortOrder, setSortOrder] = useState('asc');

  // Backend / workflow state
  const [backendOnline, setBackendOnline] = useState(null);
  const [workflowState, setWorkflowState] = useState(WORKFLOW.IDLE);
  const [analysisData, setAnalysisData] = useState(null);
  const [aisVessels, setAisVessels] = useState([]);       // always-live AIS layer
  const [aisLoading, setAisLoading] = useState(false);
  const [driftLoading, setDriftLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  // SAR upload state
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const [imageAnalysisResult, setImageAnalysisResult] = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState(null);

  // Spill coordinate capture (shown after spill confirmed but no EXIF)
  const [pendingSpillCoords, setPendingSpillCoords] = useState(null); // { lat, lon } from EXIF or null
  const [coordInputLat, setCoordInputLat] = useState('');
  const [coordInputLon, setCoordInputLon] = useState('');
  const [coordInputError, setCoordInputError] = useState('');

  // Derived data
  const activeSpill = analysisData?.spill ?? null;
  // Merge AIS layer with suspect data from analysis
  const activeVessels = useMemo(() => {
    if (analysisData?.vessels?.length > 0) return analysisData.vessels;
    return aisVessels;
  }, [analysisData, aisVessels]);

  const indianPlatforms = useMemo(
    () => mockPlatforms.filter((platform) => platform.isIndiaEEZ !== false),
    [],
  );

  const iorPlatforms = useMemo(
    () => mockPlatforms.filter((platform) => platform.isIndiaEEZ === false),
    [],
  );

  // Health check
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try { await checkStatus(); if (mounted) setBackendOnline(true); }
      catch { if (mounted) setBackendOnline(false); }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  // Auto-load AIS vessels on startup
  useEffect(() => {
    if (backendOnline) handleLoadAis();
  }, [backendOnline]);

  // Handlers
  const handleToggleLayer = useCallback((key) => setLayers(prev => ({ ...prev, [key]: !prev[key] })), []);
  const handleBaseMapChange = useCallback((v) => setBaseMap(v), []);
  const handleSelectVessel = useCallback((v) => setSelectedVessel(v), []);
  const handleSelectEvidenceFactor = useCallback((vessel, suspectRank, factor) => {
    setActiveEvidenceModal({ vessel, suspectRank, factor });
  }, []);

  // Load AIS vessels (always-live, decoupled from spill)
  const handleLoadAis = useCallback(async () => {
    if (aisLoading) return;
    setAisLoading(true);
    try {
      const res = await getVessels(585);
      if (res.status === 'success') {
        setAisVessels(res.vessels);
        setBackendOnline(true);
      }
    } catch (err) {
      setBackendOnline(false);
    } finally {
      setAisLoading(false);
    }
  }, [aisLoading]);

  // SAR image upload and analysis
  const handleImageUpload = useCallback(async (file) => {
    setIsAnalyzingImage(true);
    setImageAnalysisResult(null);
    setAnalysisError(null);
    setUploadedFileName(file.name);
    setPendingSpillCoords(null);
    setCoordInputLat('');
    setCoordInputLon('');
    setCoordInputError('');
    setWorkflowState(WORKFLOW.SAR_UPLOADING);
    try {
      const result = await analyzeSarImage(file);
      setImageAnalysisResult(result);
      if (result.is_spill) {
        if (result.geolocation_available && result.geolocation) {
          // SAR image has embedded GPS — use it directly
          setPendingSpillCoords({ lat: result.geolocation.lat, lon: result.geolocation.lon });
          setCoordInputLat(String(result.geolocation.lat));
          setCoordInputLon(String(result.geolocation.lon));
        }
        setWorkflowState(WORKFLOW.SPILL_CONFIRMED);
      } else {
        setWorkflowState(WORKFLOW.NO_SPILL);
      }
    } catch (err) {
      setAnalysisError(err.message || 'Image analysis failed.');
      setWorkflowState(WORKFLOW.IDLE);
    } finally {
      setIsAnalyzingImage(false);
    }
  }, []);

  // Validate and run drift analysis with confirmed coordinates
  const handleRunDriftAnalysis = useCallback(async () => {
    const lat = parseFloat(coordInputLat);
    const lon = parseFloat(coordInputLon);
    if (isNaN(lat) || lat < -90 || lat > 90) {
      setCoordInputError('Latitude must be a number between -90 and 90');
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setCoordInputError('Longitude must be a number between -180 and 180');
      return;
    }
    setCoordInputError('');
    setDriftLoading(true);
    setAnalysisError(null);
    setWorkflowState(WORKFLOW.RUNNING_DRIFT);
    try {
      const geolocSource = (imageAnalysisResult?.geolocation_available && imageAnalysisResult?.geolocation)
        ? 'SAR Image Metadata' : 'User Provided';
      const spillTimeIso = new Date().toISOString();
      const result = await runDriftAnalysisFromSpill(
        lat, lon, spillTimeIso,
        'Sentinel-1A SAR',
        imageAnalysisResult?.confidence_pct ?? 92.0,
        geolocSource,
      );
      if (result.status === 'success') {
        setAnalysisData(result);
        setWorkflowState(WORKFLOW.RESULTS_READY);
      } else {
        throw new Error(result.message || 'Drift analysis returned unexpected status');
      }
    } catch (err) {
      setAnalysisError(err.message || 'Drift analysis failed.');
      setWorkflowState(WORKFLOW.SPILL_CONFIRMED);
    } finally {
      setDriftLoading(false);
    }
  }, [coordInputLat, coordInputLon, imageAnalysisResult]);

  const handleResetWorkflow = useCallback(() => {
    setWorkflowState(WORKFLOW.IDLE);
    setAnalysisData(null);
    setImageAnalysisResult(null);
    setUploadedFileName(null);
    setPendingSpillCoords(null);
    setCoordInputLat('');
    setCoordInputLon('');
    setCoordInputError('');
    setAnalysisError(null);
    setSelectedVessel(null);
    setActiveEvidenceModal(null);
  }, []);

  const filteredVessels = useMemo(() => {
    return activeVessels
      .filter((v) => {
        const q = searchQuery.toLowerCase();
        return (
          (v.name || '').toLowerCase().includes(q) ||
          (v.type || '').toLowerCase().includes(q) ||
          (v.mmsi || '').toString().includes(q) ||
          (v.imo && v.imo.toString().includes(q))
        );
      })
      .sort((a, b) => {
        let valA = a[sortField]; let valB = b[sortField];
        if (typeof valA === 'string') { valA = valA.toLowerCase(); valB = (valB || '').toLowerCase(); }
        if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
        if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
        return 0;
      });
  }, [activeVessels, searchQuery, sortField, sortOrder]);

  const toggleSort = (field) => {
    if (sortField === field) setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortOrder('asc'); }
  };

  const mapCenter = [activeSpill?.lat ?? 20.0, activeSpill?.lng ?? 60.0];
  const mapZoom = activeSpill ? 8 : 4;

  return (
    <div className="flex h-screen w-full min-h-0 bg-slate-950 text-slate-200 overflow-hidden relative">
      <LayerControlPanel
        layers={layers}
        onToggleLayer={handleToggleLayer}
        baseMap={baseMap}
        onBaseMapChange={handleBaseMapChange}
        onImageUpload={handleImageUpload}
        isAnalyzingImage={isAnalyzingImage}
        imageAnalysisResult={imageAnalysisResult}
        backendOnline={backendOnline}
        analysisData={analysisData}
        uploadedFileName={uploadedFileName}
        workflowState={workflowState}
        aisVessels={aisVessels}
        platformsCount={{ india: indianPlatforms.length, ior: iorPlatforms.length }}
      />

      <div className="flex-1 min-w-0 relative h-full">
        {/* ── Top toolbar ─────────────────────────────────────── */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[1000] flex items-center gap-2 flex-wrap justify-center">
          {backendOnline === false && (
            <div className="flex items-center gap-1.5 bg-[#0b1220]/95 border border-slate-700/60 text-slate-400 text-[10px] font-semibold px-3 py-1.5 rounded shadow-lg backdrop-blur-sm">
              <WifiOff className="w-3 h-3" /> BACKEND OFFLINE
            </div>
          )}

          {/* Always-live AIS load button */}
          {backendOnline !== false && (
            <button
              onClick={handleLoadAis}
              disabled={aisLoading}
              className="flex items-center gap-2 bg-[#0b1220]/95 border border-cyan-700/60 hover:border-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-cyan-400 text-[10px] font-bold px-3 py-1.5 rounded shadow-lg transition-colors cursor-pointer backdrop-blur-sm"
            >
              {aisLoading ? <><Loader2 className="w-3 h-3 animate-spin" />Fetching AIS…</> : <><Play className="w-3 h-3" />Load Live AIS Data</>}
            </button>
          )}

          {aisVessels.length > 0 && !aisLoading && (
            <div className="flex items-center gap-1.5 bg-[#0b1220]/95 border border-emerald-700/50 text-emerald-400 text-[10px] font-semibold px-3 py-1.5 rounded shadow-lg backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              AIS LIVE · {aisVessels.length} vessels
            </div>
          )}

          {workflowState === WORKFLOW.RESULTS_READY && (
            <button
              onClick={handleResetWorkflow}
              className="flex items-center gap-1.5 bg-[#0b1220]/95 border border-slate-600/60 text-slate-400 text-[10px] font-semibold px-3 py-1.5 rounded shadow-lg hover:border-slate-500 transition-colors cursor-pointer backdrop-blur-sm"
            >
              <X className="w-3 h-3" /> Clear Spill
            </button>
          )}
        </div>

        {/* ── Spill coordinate input panel (shown after spill confirmed) ── */}
        {(workflowState === WORKFLOW.SPILL_CONFIRMED || workflowState === WORKFLOW.RUNNING_DRIFT) && (
          <div className="absolute top-12 left-1/2 -translate-x-1/2 z-[1000] w-[420px] bg-[#0b1220]/98 border border-amber-600/50 rounded-xl shadow-2xl backdrop-blur-sm p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-amber-400 text-[11px] font-bold uppercase tracking-wider">Oil Spill Confirmed</span>
              {imageAnalysisResult && <span className="ml-auto text-[10px] text-slate-400">ML Confidence: {imageAnalysisResult.oil_spill_pct?.toFixed(1)}%</span>}
            </div>

            {!imageAnalysisResult?.geolocation_available && (
              <p className="text-[10px] text-slate-400 mb-3 leading-relaxed">
                {imageAnalysisResult?.geolocation_message || 'No GPS location found in image metadata. Enter the spill coordinates to proceed with drift analysis.'}
              </p>
            )}

            <div className="flex gap-2 mb-2">
              <div className="flex-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Latitude (°N / °S)</label>
                <input
                  type="number"
                  placeholder="e.g. 15.500"
                  value={coordInputLat}
                  onChange={(e) => setCoordInputLat(e.target.value)}
                  disabled={driftLoading}
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-[11px] font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500"
                />
              </div>
              <div className="flex-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Longitude (°E / °W)</label>
                <input
                  type="number"
                  placeholder="e.g. 69.500"
                  value={coordInputLon}
                  onChange={(e) => setCoordInputLon(e.target.value)}
                  disabled={driftLoading}
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-[11px] font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            {coordInputError && (
              <p className="text-[10px] text-red-400 mb-2">{coordInputError}</p>
            )}

            <button
              onClick={handleRunDriftAnalysis}
              disabled={driftLoading}
              className="w-full flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-bold py-2 rounded transition-colors cursor-pointer"
            >
              {driftLoading ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />Running Drift &amp; Vessel Attribution…</> : <><Crosshair className="w-3.5 h-3.5" />Run Drift &amp; Vessel Attribution</>}
            </button>
          </div>
        )}

        {/* ── No spill banner ──────────────────────────────────── */}
        {workflowState === WORKFLOW.NO_SPILL && (
          <div className="absolute top-12 left-1/2 -translate-x-1/2 z-[1000] flex items-center gap-2 bg-[#0b1220]/95 border border-emerald-700/60 text-emerald-400 text-[10px] font-semibold px-4 py-2 rounded shadow-lg backdrop-blur-sm">
            <CheckCircle2 className="w-4 h-4" />
            No oil spill detected in this SAR image
            <button onClick={handleResetWorkflow} className="ml-2 text-slate-500 hover:text-slate-300"><X className="w-3 h-3" /></button>
          </div>
        )}

        {/* ── Error toast ──────────────────────────────────────── */}
        {analysisError && (
          <div className="absolute top-12 left-1/2 -translate-x-1/2 z-[1000] flex items-center gap-2 bg-red-950/90 border border-red-700/60 text-red-400 text-[10px] font-semibold px-3 py-1.5 rounded shadow-lg backdrop-blur-sm max-w-sm text-center">
            <AlertTriangle className="w-3 h-3 flex-shrink-0" />
            {analysisError}
            <button onClick={() => setAnalysisError(null)} className="ml-1"><X className="w-3 h-3" /></button>
          </div>
        )}

        <MapContainer
          center={mapCenter}
          zoom={mapZoom}
          className="h-full w-full"
          zoomControl={true}
          minZoom={3}
          maxZoom={11}
          maxBounds={[[-90, -180], [90, 180]]}
          maxBoundsViscosity={1.0}
          worldCopyJump={false}
        >
          <TileLayer
            url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
            maxNativeZoom={20}
            maxZoom={12}
            noWrap={true}
          />
          <ScaleControl position="bottomleft" imperial={false} />
          <MapController selectedVessel={selectedVessel} activeSpill={activeSpill} />

          {layers.spill && <OilSpillLayer spill={activeSpill} />}

          {layers.ais && activeVessels.map((vessel) => (
            <VesselMarker key={vessel.id} vessel={vessel} onSelect={handleSelectVessel} />
          ))}

          {layers.platformsIndia && indianPlatforms.map((platform) => (
            <PlatformMarker key={platform.id} platform={platform} />
          ))}

          {layers.platformsIOR && iorPlatforms.map((platform) => (
            <PlatformMarker key={platform.id} platform={platform} />
          ))}

          {selectedVessel && (
            <Popup position={[selectedVessel.lat, selectedVessel.lng]} onClose={() => setSelectedVessel(null)}>
              <div className="bg-[#0d1929] text-slate-200 rounded border border-slate-700/80 w-[260px] -m-3 shadow-2xl select-text overflow-hidden">
                <div className={`px-3 py-2 border-b ${selectedVessel.isSuspect ? 'border-red-800/50 bg-red-950/30' : 'border-slate-800/80 bg-slate-900/60'}`}>
                  {selectedVessel.isSuspect && <div className="text-[9px] text-red-400 font-bold uppercase tracking-wider mb-0.5">⚑ Suspect Vessel</div>}
                  <div className="font-bold text-[13px] text-slate-100 truncate">{selectedVessel.name || 'UNKNOWN'}</div>
                  <div className="text-[10px] text-slate-500">{selectedVessel.type || 'Vessel'}</div>
                </div>
                <div className="px-3 py-2.5 space-y-2 text-[10px]">
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                    <div><span className="text-slate-600">MMSI </span><span className="text-slate-300 font-mono">{selectedVessel.mmsi || '—'}</span></div>
                    {selectedVessel.imo && selectedVessel.imo !== 'N/A' && <div><span className="text-slate-600">IMO </span><span className="text-slate-300 font-mono">{selectedVessel.imo}</span></div>}
                  </div>
                  <div className="text-slate-300 font-mono">
                    {selectedVessel.lat?.toFixed(4)}° {selectedVessel.lat >= 0 ? 'N' : 'S'} / {selectedVessel.lng?.toFixed(4)}° {selectedVessel.lng >= 0 ? 'E' : 'W'}
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                    <div><span className="text-slate-600">Speed </span><span className="text-slate-300">{selectedVessel.sog != null ? `${selectedVessel.sog} kn` : '—'}</span></div>
                    <div><span className="text-slate-600">Course </span><span className="text-slate-300">{selectedVessel.cog != null ? `${selectedVessel.cog}°` : '—'}</span></div>
                    <div className="col-span-2"><span className="text-slate-600">Status </span><span className="text-slate-300">{selectedVessel.navStatus || '—'}</span></div>
                  </div>
                  {selectedVessel.isSuspect && selectedVessel.attributionScore != null && (
                    <div className="pt-2 border-t border-red-900/40">
                      <div className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold mb-1">Attribution Score</div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Composite</span>
                        <span className="text-red-300 font-bold font-mono">{selectedVessel.attributionScore?.toFixed(1)}%</span>
                      </div>
                      {selectedVessel.distanceKm < 900 && (
                        <div className="flex justify-between mt-0.5">
                          <span className="text-slate-500">Distance from spill</span>
                          <span className="text-slate-300 font-mono">{selectedVessel.distanceKm} km</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Popup>
          )}
        </MapContainer>
      </div>

      {/* ── Right sidebar ────────────────────────────────────── */}
      <div className="w-[300px] min-h-0 border-l border-slate-800/80 flex flex-col overflow-y-auto bg-[#0b1220]">
        <DetectedSpillPanel spill={activeSpill} />
        <CoastalThreatPanel spill={activeSpill} />
        <div className="flex-none min-h-[320px] h-[min(55vh,520px)]">
          <NearbyVesselsPanel
            vessels={activeVessels}
            suspects={analysisData?.suspects ?? []}
            onSelectVessel={handleSelectVessel}
            onSelectEvidenceFactor={handleSelectEvidenceFactor}
            onViewFullList={() => setIsVesselListOpen(true)}
            activeSpill={activeSpill}
            hasSpillResults={workflowState === WORKFLOW.RESULTS_READY}
          />
        </div>
      </div>

      {/* ── Full AIS list modal ──────────────────────────────── */}
      {isVesselListOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-4xl w-full max-h-[80vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-slate-100 text-base">AIS REGISTERED VESSELS</h3>
                <p className="text-xs text-slate-400">
                  {activeVessels.length} vessels in monitoring area
                  {analysisData && ` · ${analysisData.total_vessels} total from live feed`}
                </p>
              </div>
              <button onClick={() => setIsVesselListOpen(false)} className="text-slate-400 hover:text-slate-200 p-1 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 bg-slate-950/40 border-b border-slate-800 flex gap-4">
              <div className="relative flex-1 max-w-xs">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input type="text" placeholder="Search name, MMSI, type..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500" />
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="bg-slate-950/60 text-slate-400 font-semibold uppercase tracking-wider sticky top-0 border-b border-slate-800">
                  <tr>
                    <th className="p-3 cursor-pointer select-none hover:text-slate-200" onClick={() => toggleSort('name')}>Vessel Name {sortField === 'name' && (sortOrder === 'asc' ? '▲' : '▼')}</th>
                    <th className="p-3 cursor-pointer select-none hover:text-slate-200" onClick={() => toggleSort('type')}>Type {sortField === 'type' && (sortOrder === 'asc' ? '▲' : '▼')}</th>
                    <th className="p-3">MMSI / IMO</th>
                    <th className="p-3 text-right">SOG</th>
                    <th className="p-3 text-right">COG</th>
                    <th className="p-3">Destination</th>
                    <th className="p-3 cursor-pointer select-none hover:text-slate-200 text-right" onClick={() => toggleSort('distanceKm')}>Distance {sortField === 'distanceKm' && (sortOrder === 'asc' ? '▲' : '▼')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {filteredVessels.length === 0 ? (
                    <tr><td colSpan="7" className="text-center p-8 text-slate-500">No vessels matching query.</td></tr>
                  ) : filteredVessels.map((v) => (
                    <tr key={v.id} onClick={() => { handleSelectVessel(v); setIsVesselListOpen(false); }}
                      className={`hover:bg-slate-800/30 cursor-pointer transition-colors ${v.isSuspect ? 'bg-amber-500/5' : ''}`}>
                      <td className="p-3 font-semibold text-slate-200">
                        <div className="flex items-center gap-2">
                          <span className={`w-1.5 h-1.5 rounded-full ${v.isSuspect ? 'bg-amber-500 animate-pulse' : 'bg-cyan-500'}`} />
                          {v.name}
                        </div>
                      </td>
                      <td className="p-3 text-slate-300">{v.type}</td>
                      <td className="p-3 text-slate-400 font-mono">M: {v.mmsi} {v.imo && v.imo !== 'N/A' && `/ I: ${v.imo}`}</td>
                      <td className="p-3 text-slate-200 text-right">{v.sog} kn</td>
                      <td className="p-3 text-slate-400 text-right">{v.cog}°</td>
                      <td className="p-3 text-slate-300 truncate max-w-[120px]">{v.destination}</td>
                      <td className="p-3 text-slate-200 text-right font-semibold">{v.distanceKm < 900 ? `${v.distanceKm} km` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 bg-slate-950/40 border-t border-slate-800 text-right text-[10px] text-slate-500">
              Showing {filteredVessels.length} of {activeVessels.length} vessels · Click row to track
            </div>
          </div>
        </div>
      )}

      {/* ── Front Screen Evidence Factor Details Modal ───────────── */}
      {activeEvidenceModal && (
        <EvidenceFactorModal
          vessel={activeEvidenceModal.vessel}
          suspectRank={activeEvidenceModal.suspectRank}
          initialFactor={activeEvidenceModal.factor}
          onClose={() => setActiveEvidenceModal(null)}
          onLocateVessel={(v) => handleSelectVessel(v)}
        />
      )}
    </div>
  );
}
