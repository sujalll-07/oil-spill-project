/**
 * api.js — Centralized API service for Oil Spill Intelligence System
 *
 * All backend communication goes through this module.
 * The base URL is configured via the VITE_API_URL environment variable.
 * Defaults to http://localhost:8000 in development.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ============================================================
// HELPERS
// ============================================================

async function handleResponse(response) {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    try {
      const errData = await response.json();
      errorMessage = errData.detail || errData.message || errorMessage;
    } catch (_) {
      // ignore json parse errors on error responses
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

// ============================================================
// HEALTH CHECK
// ============================================================

/**
 * Check if the Python backend is reachable and the model is loaded.
 * @returns {Promise<{status: string, model_loaded: boolean, timestamp: string}>}
 */
export async function checkStatus() {
  const response = await fetch(`${API_BASE_URL}/api/status`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(response);
}

// ============================================================
// SAR IMAGE ANALYSIS
// ============================================================

/**
 * Upload a SAR image to the Python backend for ML oil spill detection.
 * Uses the existing predict_oil_spill() TensorFlow function.
 *
 * @param {File} imageFile - The SAR image file to analyze
 * @returns {Promise<{
 *   status: string,
 *   is_spill: boolean,
 *   probability: number,
 *   confidence_pct: number,
 *   oil_spill_pct: number,
 *   no_oil_spill_pct: number,
 *   geolocation_available: boolean,
 *   geolocation: {lat: number, lon: number} | null,
 *   geolocation_message: string
 * }>}
 */
export async function analyzeSarImage(imageFile) {
  const formData = new FormData();
  formData.append('file', imageFile);

  const response = await fetch(`${API_BASE_URL}/api/analyze-sar`, {
    method: 'POST',
    body: formData,
    // Do NOT set Content-Type header manually — browser sets it with boundary
  });
  return handleResponse(response);
}

// ============================================================
// FULL DRIFT + VESSEL ATTRIBUTION ANALYSIS FROM SPILL COORDS
// ============================================================

/**
 * Run the full drift + vessel attribution analysis pipeline from confirmed spill coordinates.
 *
 * This runs:
 *  1. Lagrangian forward drift simulation from the spill point
 *  2. Vessel attribution / suspicion scoring
 *  3. Coastal threat assessment
 *
 * @param {number} spillLat - Spill latitude in decimal degrees
 * @param {number} spillLon - Spill longitude in decimal degrees
 * @param {string} spillTimeIso - ISO 8601 timestamp of spill detection
 * @param {string} [sensorName] - Sensor that detected the spill
 * @param {number} [confidencePct] - ML model confidence percentage
 * @param {string} [geolocSource] - Source of the spill geolocation
 * @returns {Promise<{
 *   status: string,
 *   spill: object,
 *   vessels: Array,
 *   suspects: Array,
 *   total_vessels: number,
 *   total_suspects: number
 * }>}
 */
export async function runDriftAnalysisFromSpill(
  spillLat,
  spillLon,
  spillTimeIso,
  sensorName = 'Sentinel-1A SAR',
  confidencePct = 92.0,
  geolocSource = 'SAR Detection',
) {
  const response = await fetch(`${API_BASE_URL}/api/run-analysis-from-spill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spill_lat: spillLat,
      spill_lon: spillLon,
      spill_time: spillTimeIso,
      sensor_name: sensorName,
      confidence_pct: confidencePct,
      geolocation_source: geolocSource,
    }),
  });
  return handleResponse(response);
}

// ============================================================
// DEPRECATED — LEGACY DRIFT ANALYSIS
// ============================================================

/**
 * @deprecated Use runDriftAnalysisFromSpill() instead.
 * This endpoint no longer exists on the backend. Kept for backward
 * compatibility — falls back to getVessels() so call sites don't crash.
 */
export async function runDriftAnalysis() {
  console.warn(
    '[api.js] runDriftAnalysis() is deprecated and the /api/run-analysis endpoint ' +
      'has been removed. Use runDriftAnalysisFromSpill() instead. ' +
      'Falling back to getVessels() for backward compatibility.',
  );
  return getVessels(585);
}

// ============================================================
// VESSEL LIST ONLY
// ============================================================

/**
 * Fetch AIS vessels without running drift analysis.
 *
 * @param {number} count - Number of vessels to fetch (max 585)
 * @returns {Promise<{status: string, vessels: Array, total: number}>}
 */
export async function getVessels(count = 100) {
  const response = await fetch(`${API_BASE_URL}/api/vessels?count=${count}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(response);
}
