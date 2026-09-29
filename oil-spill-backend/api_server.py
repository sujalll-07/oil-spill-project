"""
Oil Spill Intelligence System - FastAPI Integration Layer
---------------------------------------------------------
CORRECTED WORKFLOW (v2):

  SAR IMAGE INPUT
    → POST /api/analyze-sar          — ML oil-spill detection + optional geolocation extraction
    → (if spill confirmed, coordinates known)
    → POST /api/run-analysis-from-spill  — Lagrangian drift + global landmass + vessel attribution
    → GET  /api/vessels              — AIS vessel layer (always live, independent of spill state)
    → GET  /api/status               — Health check

CRITICAL INVARIANTS:
  - AIS data alone NEVER creates a spill, drift run, or suspect ranking.
  - The Lagrangian model ALWAYS starts from SAR-detected spill coordinates.
  - Nearest-landmass analysis is GLOBAL (not India-only).
  - Vessel attribution uses multi-factor scoring (spatial + temporal + trajectory
    + AIS gap + vessel type + behaviour + hindcast proximity).
  - All geographic output derives from the same confirmed lat/lon coordinates.
"""

import asyncio
import io
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import tensorflow as tf

from ais_real_test import (
    get_combined_vessels_list,
    is_ocean_coord,
)

from lagrangian_engine import (
    EnvironmentalField,
    LagrangianDriftModel,
    create_spill_particle_cloud,        # ← SAR-coordinates-first particle init
    create_synthetic_spill_from_vessel, # ← DEMO ONLY (kept for CLI)
    correlate_with_vessel_tracks,       # ← kept for backward compat
)

from coastal_landfall_engine import predict_oil_spill_landfall
from global_coastline_engine import (
    find_nearest_coastline,
    find_landmasses_in_drift_path,
)
from vessel_attribution_engine import rank_vessels_by_attribution


# ============================================================
# SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH  = 224
MODEL_PATH = "oil_spill_classifier.keras"


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Oil Spill Intelligence API (v2)",
    description=(
        "REST API for SAR-first oil spill detection, "
        "global Lagrangian drift modelling, and multi-factor vessel attribution."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODEL LOADER
# ============================================================

_model = None

def get_model():
    global _model
    if _model is None:
        print("[API] Loading TensorFlow model...")
        _model = tf.keras.models.load_model(MODEL_PATH)
        print("[API] Model loaded.")
    return _model


# ============================================================
# ML INFERENCE (unchanged from original)
# ============================================================

def predict_oil_spill(image: Image.Image) -> float:
    """Returns probability (0–1) that image contains an oil spill."""
    image = image.convert("RGB").resize((IMG_WIDTH, IMG_HEIGHT))
    arr = np.array(image).astype(np.float32)
    arr = tf.keras.applications.mobilenet_v2.preprocess_input(arr)
    arr = np.expand_dims(arr, axis=0)
    return float(get_model().predict(arr, verbose=0)[0][0])


# ============================================================
# RAW UAVSAR .grd DECODER
# ============================================================

def _decode_grd(contents: bytes) -> Optional[Image.Image]:
    """
    Decode a raw UAVSAR .grd binary (little-endian float32 raster) into a
    PIL grayscale image, matching the logic in sar_pipeline.py.
    Returns None if the data doesn't look like a float32 raster.
    """
    raw = np.frombuffer(contents, dtype=np.float32)
    # Real UAVSAR .grd rasters are large; tiny buffers mean this isn't one
    if raw.size < 256 or not np.isfinite(raw).any():
        return None

    # Reshape to 2D: square if possible, otherwise approximate rectangular
    total = raw.size
    side = int(np.sqrt(total))
    if side * side == total:
        band = raw.reshape((side, side))
    elif total >= 2000:
        rows = 2000
        cols = max(total // rows, 1)
        band = raw[: rows * cols].reshape((rows, cols))
    else:
        band = raw.reshape((1, total))

    b_min, b_max = np.nanmin(band), np.nanmax(band)
    normalized = np.nan_to_num(((band - b_min) / (b_max - b_min + 1e-5)) * 255.0)
    return Image.fromarray(normalized.astype(np.uint8)).convert("L")


# ============================================================
# EXIF / GEOLOCATION EXTRACTION FROM SAR IMAGE
# ============================================================

def _extract_gps_from_exif(image: Image.Image) -> Optional[dict]:
    """
    Attempt to extract GPS coordinates embedded in the image EXIF metadata.
    Returns {"lat": float, "lon": float, "source": "EXIF/GPS"} or None.
    """
    try:
        exif_data = image._getexif()  # returns None if no EXIF
        if not exif_data:
            return None

        gps_info_raw = None
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps_info_raw = value
                break

        if not gps_info_raw:
            return None

        gps = {}
        for key, val in gps_info_raw.items():
            gps[GPSTAGS.get(key, key)] = val

        def _dms_to_dd(dms, ref):
            d, m, s = dms
            dd = float(d) + float(m) / 60.0 + float(s) / 3600.0
            if ref in ("S", "W"):
                dd = -dd
            return dd

        lat = _dms_to_dd(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        lon = _dms_to_dd(gps["GPSLongitude"], gps["GPSLongitudeRef"])

        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return {"lat": round(lat, 6), "lon": round(lon, 6), "source": "EXIF/GPS"}

    except Exception:
        pass

    return None


# ============================================================
# GEOMETRY HELPERS
# ============================================================

def _haversine_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2.0 * 6371.0 * math.asin(math.sqrt(max(0, min(1, a))))


def build_spill_polygon_from_particles(
    lons_final: np.ndarray,
    lats_final: np.ndarray,
    center_lat: float,
    center_lng: float,
) -> list:
    """Convex-hull-style polygon from the Lagrangian particle cloud."""
    n = min(len(lons_final), 500)
    idx = np.random.choice(len(lons_final), size=n, replace=False)
    sample_lons = lons_final[idx]
    sample_lats = lats_final[idx]

    angles = np.arctan2(sample_lats - center_lat, sample_lons - center_lng)
    sorted_idx = np.argsort(angles)
    step = max(1, len(sorted_idx) // 20)
    hull_idx = sorted_idx[::step]

    polygon = []
    for i in hull_idx:
        p_lat = float(sample_lats[i])
        p_lon = float(sample_lons[i])
        step_count = 0
        while not is_ocean_coord(p_lat, p_lon) and step_count < 10:
            p_lat = 0.8 * p_lat + 0.2 * center_lat
            p_lon = 0.8 * p_lon + 0.2 * center_lng
            step_count += 1
        polygon.append([p_lat, p_lon])

    return polygon


def estimate_area_km2(lons: np.ndarray, lats: np.ndarray) -> float:
    lat_range = float(np.max(lats) - np.min(lats))
    lon_range = float(np.max(lons) - np.min(lons))
    mean_lat = float(np.mean(lats))
    height_km = lat_range * 111.0
    width_km = lon_range * 111.0 * abs(math.cos(math.radians(mean_lat)))
    area = math.pi * (height_km / 2) * (width_km / 2)
    return round(max(0.5, area), 1)


# ============================================================
# CORE: DRIFT ANALYSIS FROM CONFIRMED SPILL COORDINATES
# ============================================================

def run_drift_analysis_from_spill(
    spill_lat: float,
    spill_lon: float,
    spill_time: datetime,
    vessels: list,
    sensor_name: str = "Sentinel-1A SAR",
    confidence_pct: float = 92.0,
    geolocation_source: str = "SAR Detection",
) -> dict:
    """
    Run the full Lagrangian drift + landmass + vessel attribution pipeline
    starting from a CONFIRMED, SAR-detected spill location.

    This function NEVER invents a spill site.  The coordinates supplied
    are the single source of truth for all downstream analysis.
    """

    # ── 1. Validate coordinates ──────────────────────────────────
    if not (-90 <= spill_lat <= 90 and -180 <= spill_lon <= 180):
        raise ValueError(f"Invalid spill coordinates: ({spill_lat}, {spill_lon})")

    num_particles = 1000

    # ── 2. Create particle cloud at CONFIRMED spill location ──────
    lons, lats = create_spill_particle_cloud(
        center_lat=spill_lat,
        center_lon=spill_lon,
        num_points=num_particles,
        radius_km=2.0,
    )

    detection_center_lon = float(np.mean(lons))
    detection_center_lat = float(np.mean(lats))

    # ── 3. Environmental field (auto-fetched by coastal engine) ───
    env = EnvironmentalField(
        default_current=(0.20, -0.10),
        default_wind=(5.0, 3.0),
    )

    drift_model = LagrangianDriftModel(
        env=env,
        wind_drift_factor=0.03,
        wind_deflection_angle=12.0,
        horizontal_diffusivity=1.0,
    )

    # ── 4. 12-hour backward hindcast ─────────────────────────────
    hindcast_duration = timedelta(hours=12)
    hindcast_results = drift_model.run_hindcast(
        initial_lons=lons,
        initial_lats=lats,
        start_time=spill_time,
        duration=hindcast_duration,
        time_step=timedelta(minutes=15),
        method="rk4",
    )

    origin_center_lon = float(np.mean(hindcast_results["lons"][-1]))
    origin_center_lat = float(np.mean(hindcast_results["lats"][-1]))
    if not is_ocean_coord(origin_center_lat, origin_center_lon):
        dists = (
            (hindcast_results["lats"][-1] - origin_center_lat) ** 2
            + (hindcast_results["lons"][-1] - origin_center_lon) ** 2
        )
        ci = int(np.argmin(dists))
        origin_center_lat = float(hindcast_results["lats"][-1][ci])
        origin_center_lon = float(hindcast_results["lons"][-1][ci])

    # ── 5. 72-hour forward forecast ───────────────────────────────
    forecast_duration = timedelta(hours=72)
    forecast_results = drift_model.run_forecast(
        initial_lons=lons,
        initial_lats=lats,
        start_time=spill_time,
        duration=forecast_duration,
        time_step=timedelta(minutes=15),
        method="rk4",
    )

    forecast_12h_time = spill_time + timedelta(hours=12)
    forecast_12h_index = min(
        range(len(forecast_results["times"])),
        key=lambda index: abs(
            (forecast_results["times"][index] - forecast_12h_time).total_seconds()
        ),
    )
    forecast_12h_lons = forecast_results["lons"][forecast_12h_index]
    forecast_12h_lats = forecast_results["lats"][forecast_12h_index]
    forecast_12h_lat = float(np.mean(forecast_12h_lats))
    forecast_12h_lon = float(np.degrees(np.arctan2(
        np.mean(np.sin(np.radians(forecast_12h_lons))),
        np.mean(np.cos(np.radians(forecast_12h_lons))),
    )))
    if not is_ocean_coord(forecast_12h_lat, forecast_12h_lon):
        lon_offsets = (
            (forecast_12h_lons - forecast_12h_lon + 180.0) % 360.0
        ) - 180.0
        dists = (
            (forecast_12h_lats - forecast_12h_lat) ** 2
            + (lon_offsets * math.cos(math.radians(forecast_12h_lat))) ** 2
        )
        ci = int(np.argmin(dists))
        forecast_12h_lat = float(forecast_12h_lats[ci])
        forecast_12h_lon = float(forecast_12h_lons[ci])

    # ── 6. Global nearest coastline (current spill position) ─────
    nearest_coast = find_nearest_coastline(spill_lat, spill_lon)

    # ── 7. Landmasses in drift path ───────────────────────────────
    try:
        trajectory_landmasses = find_landmasses_in_drift_path(
            trajectory_lats=forecast_results["lats"],
            trajectory_lons=forecast_results["lons"],
            trajectory_times=forecast_results["times"],
            approach_threshold_km=80.0,
            spill_lat=spill_lat,
            spill_lon=spill_lon,
        )
    except Exception as e:
        print(f"[WARN] Trajectory landmass scan failed: {e}")
        trajectory_landmasses = []

    # ── 8. Coastal landfall prediction ───────────────────────────
    try:
        landfall_results = predict_oil_spill_landfall(
            lat=spill_lat,
            lon=spill_lon,
            forecast_hours=72,
            num_particles=500,
        )
    except Exception as e:
        print(f"[WARN] Landfall prediction failed: {e}")
        landfall_results = None

    # ── 9. Multi-factor vessel attribution ───────────────────────
    suspects = rank_vessels_by_attribution(
        vessels=vessels,
        spill_lat=spill_lat,
        spill_lon=spill_lon,
        spill_time=spill_time,
        hindcast_results=hindcast_results,
        top_k=5,
        lookback_hours=12.0,
    )

    suspect_mmsis = {str(s.get("mmsi", "")) for s in suspects}
    all_candidate_vessels = list(suspects) + [v for v in vessels if str(v.get("mmsi", "")) not in suspect_mmsis]

    return {
        "detection_center_lat": detection_center_lat,
        "detection_center_lon": detection_center_lon,
        "origin_lat":  origin_center_lat,
        "origin_lon":  origin_center_lon,
        "detection_time": spill_time,
        "vessels": all_candidate_vessels,
        "suspects": suspects,
        "hindcast_results": hindcast_results,
        "forecast_results": forecast_results,
        "forecast_12h_lat": forecast_12h_lat,
        "forecast_12h_lon": forecast_12h_lon,
        "forecast_12h_time": forecast_results["times"][forecast_12h_index],
        "forecast_12h_lons": forecast_12h_lons,
        "forecast_12h_lats": forecast_12h_lats,
        "nearest_coast": nearest_coast,
        "trajectory_landmasses": trajectory_landmasses,
        "landfall_results": landfall_results,
        "sensor_name": sensor_name,
        "confidence_pct": confidence_pct,
        "geolocation_source": geolocation_source,
        "spill_lat": spill_lat,
        "spill_lon": spill_lon,
    }


# ============================================================
# SERIALIZERS
# ============================================================

def serialize_vessel_for_frontend(vessel: dict, index: int, suspects_mmsi: set) -> dict:
    mmsi = str(vessel.get("mmsi", ""))
    is_suspect = mmsi in suspects_mmsi

    distance_km = vessel.get("closest_distance_km", None)
    if distance_km is None:
        distance_km = round(vessel.get("dist_to_origin_km", 999.0), 2)

    heading = vessel.get("heading_degrees", 0)
    if heading == 511:
        heading = vessel.get("course_degrees", 0)

    return {
        "id": f"v-{mmsi}-{index}",
        "name": vessel.get("ship_name", f"UNKNOWN_{mmsi}"),
        "mmsi": mmsi,
        "imo": vessel.get("imo", "N/A"),
        "callsign": vessel.get("callsign", "N/A"),
        "flag": vessel.get("flag", "N/A"),
        "type": vessel.get("ship_type", "Vessel"),
        "navStatus": vessel.get("status", "Unknown"),
        "sog": round(float(vessel.get("speed_knots", 0)), 1),
        "cog": round(float(vessel.get("course_degrees", 0)), 1),
        "heading": round(float(heading), 1),
        "lat": float(vessel.get("latitude", 0)),
        "lng": float(vessel.get("longitude", 0)),
        "lengthM": vessel.get("length_m", "N/A"),
        "beamM": vessel.get("beam_m", "N/A"),
        "draftM": vessel.get("draft_m", "N/A"),
        "destination": vessel.get("destination", "N/A"),
        "eta": vessel.get("eta", "N/A"),
        "distanceKm": round(float(distance_km), 2) if distance_km is not None else 999.0,
        "isSuspect": is_suspect,
        "suspicionScore": vessel.get("attribution_score", vessel.get("match_percentage", 0)) if is_suspect else None,
        "attributionFactors": vessel.get("attribution_factors", []) if is_suspect else [],
        "trajectory": vessel.get("trajectory", None),
    }


def build_spill_polygon_for_spill(lons, lats, center_lat, center_lon):
    return build_spill_polygon_from_particles(lons, lats, center_lat, center_lon)


def serialize_spill(analysis: dict) -> dict:
    spill_lat = analysis["spill_lat"]
    spill_lon = analysis["spill_lon"]
    det_lat   = analysis["detection_center_lat"]
    det_lon   = analysis["detection_center_lon"]
    detection_time = analysis["detection_time"]
    hindcast = analysis["hindcast_results"]

    detection_lons = hindcast["lons"][0]
    detection_lats = hindcast["lats"][0]

    polygon = build_spill_polygon_from_particles(
        detection_lons, detection_lats, det_lat, det_lon
    )

    origin_lons = hindcast["lons"][-1]
    origin_lats = hindcast["lats"][-1]
    origin_lat  = analysis["origin_lat"]
    origin_lon  = analysis["origin_lon"]

    drift_polygon = build_spill_polygon_from_particles(
        origin_lons, origin_lats, origin_lat, origin_lon
    )

    area_km2 = estimate_area_km2(detection_lons, detection_lats)

    nearest_coast = analysis.get("nearest_coast", {})
    trajectory_landmasses = analysis.get("trajectory_landmasses", [])

    spill_obj = {
        "id": f"SPILL-{detection_time.strftime('%Y-%m-%d-%H%M')}",
        "detectionTime": detection_time.strftime("%d %b %Y %H:%M UTC"),
        "satellite": analysis.get("sensor_name", "Sentinel-1A SAR"),
        "sensorType": "C-Band Synthetic Aperture Radar",
        "geolocation_source": analysis.get("geolocation_source", "SAR Detection"),
        "lat": round(spill_lat, 4),
        "lng": round(spill_lon, 4),
        "areaKm2": area_km2,
        "confidencePct": round(analysis.get("confidence_pct", 92.0), 1),
        "oilType": "Unknown (Heavy Crude suspected)",
        "windSpeedKmh": 16,
        "windDirectionDeg": 292,
        "windDirectionLabel": "WNW (292°)",
        "polygon": polygon,
        "driftPolygon": drift_polygon,
        "originLat": round(origin_lat, 4),
        "originLon": round(origin_lon, 4),
        "forecast12hLat": round(analysis["forecast_12h_lat"], 4),
        "forecast12hLon": round(analysis["forecast_12h_lon"], 4),
        "forecast12hTime": analysis["forecast_12h_time"].isoformat(),
        "forecast12hPolygon": build_spill_polygon_from_particles(
            analysis["forecast_12h_lons"],
            analysis["forecast_12h_lats"],
            analysis["forecast_12h_lat"],
            analysis["forecast_12h_lon"],
        ),
        # Global nearest coastline (replaces India-only)
        "nearestCoast": {
            "countryName":       nearest_coast.get("country_name", "Unknown"),
            "regionDescription": nearest_coast.get("region_description", "Unknown"),
            "distanceKm":        nearest_coast.get("distance_km", -1),
            "coastLat":          nearest_coast.get("coast_lat", spill_lat),
            "coastLon":          nearest_coast.get("coast_lon", spill_lon),
        },
        # Landmasses that the drift trajectory approaches
        "trajectoryLandmasses": trajectory_landmasses,
    }

    # Nearest vessel name from top suspect
    top_suspects = analysis.get("suspects", [])
    if top_suspects:
        spill_obj["nearVesselName"] = top_suspects[0].get("ship_name", "Unknown")

    # Coastal landfall prediction data
    landfall = analysis.get("landfall_results")
    if landfall:
        spill_obj["landfall"] = {
            "drift_classification":   landfall.get("drift_classification"),
            "threat_level":           landfall.get("threat_level"),
            "threat_badge":           landfall.get("threat_badge"),
            "threat_description":     landfall.get("threat_description"),
            "is_moving_towards_coast":landfall.get("is_moving_towards_coast"),
            "has_beached":            landfall.get("has_beached"),
            "beached_percentage":     landfall.get("beached_percentage"),
            "first_landfall_hours":   landfall.get("first_landfall_hours"),
            "first_landfall_time":    landfall.get("first_landfall_time"),
            "median_landfall_hours":  landfall.get("median_landfall_hours"),
            "landfall_location":      landfall.get("landfall_location"),
            "final_distance_to_coast_km": landfall.get("final_distance_to_coast_km"),
            "trajectory_timeline":    landfall.get("trajectory_timeline"),
            "initial_site":           landfall.get("initial_site"),
            # Global nearest coastline (consistent with spill data above)
            "nearest_current_landmass": {
                "country_name":       nearest_coast.get("country_name", "Unknown"),
                "region_description": nearest_coast.get("region_description", "Unknown"),
                "distance_km":        nearest_coast.get("distance_km", -1),
                "coast_lat":          nearest_coast.get("coast_lat", spill_lat),
                "coast_lon":          nearest_coast.get("coast_lon", spill_lon),
            },
            "trajectory_affected_landmasses": trajectory_landmasses,
        }

    return spill_obj


# ============================================================
# REQUEST MODELS
# ============================================================

class SpillAnalysisRequest(BaseModel):
    spill_lat: float
    spill_lon: float
    spill_time: Optional[str] = None          # ISO-8601 UTC; defaults to now
    sensor_name: Optional[str] = "Sentinel-1A SAR"
    confidence_pct: Optional[float] = 92.0
    geolocation_source: Optional[str] = "SAR Detection"


# ============================================================
# ROUTES
# ============================================================

@app.get("/api/status")
async def status():
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
    }


@app.post("/api/analyze-sar")
async def analyze_sar(file: UploadFile = File(...)):
    """
    Step 1 of the pipeline: Upload a SAR image for oil-spill detection.

    Returns ML probability + whether a spill is detected.
    Also attempts to extract GPS geolocation from image EXIF metadata.
    If geolocation is not available in the image, explicitly reports this
    so the frontend can ask the user for coordinates.
    """
    # Accept any file type (images, raw datasets, etc.) — no extension restriction.
    # Downstream parsing will handle format-specific content.
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    try:
        contents = await file.read()

        # Route by format: raw .grd binaries can't go through PIL directly
        name_lower = (file.filename or "").lower()
        if name_lower.endswith(".grd"):
            image = _decode_grd(contents)
            if image is None:
                raise HTTPException(
                    status_code=400,
                    detail="Could not decode .grd file — not a valid float32 raster.",
                )
        else:
            image = Image.open(io.BytesIO(contents))

        probability = predict_oil_spill(image)
        is_spill = probability >= 0.5
        confidence = probability if is_spill else (1.0 - probability)

        # Attempt geolocation extraction from EXIF
        geolocation = _extract_gps_from_exif(image)

        response = {
            "status": "success",
            "result": "OIL SPILL DETECTED" if is_spill else "NO OIL SPILL DETECTED",
            "is_spill": is_spill,
            "probability": round(probability, 4),
            "confidence": round(confidence, 4),
            "confidence_pct": round(confidence * 100, 2),
            "oil_spill_pct": round(probability * 100, 2),
            "no_oil_spill_pct": round((1 - probability) * 100, 2),
            "geolocation_available": geolocation is not None,
            "geolocation": geolocation,
        }

        if not geolocation:
            response["geolocation_message"] = (
                "Spill location cannot be reliably established from image metadata. "
                "Please provide the spill coordinates manually."
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/run-analysis-from-spill")
async def run_analysis_from_spill(request: SpillAnalysisRequest):
    """
    Step 2 of the pipeline: Run full Lagrangian drift + vessel attribution
    analysis from a CONFIRMED, SAR-detected spill location.

    Requires: spill_lat, spill_lon (from SAR detection or user-provided coords).
    Optional: spill_time (ISO-8601 UTC), sensor_name, confidence_pct.

    This is the ONLY legitimate trigger for drift modelling and suspect ranking.
    AIS vessels are fetched internally as part of this call.
    """
    # Parse spill time
    if request.spill_time:
        try:
            spill_time = datetime.fromisoformat(
                request.spill_time.replace("Z", "+00:00")
            )
            if spill_time.tzinfo is None:
                spill_time = spill_time.replace(tzinfo=timezone.utc)
        except ValueError:
            spill_time = datetime.now(timezone.utc)
    else:
        spill_time = datetime.now(timezone.utc)

    # Validate coordinates
    if not (-90 <= request.spill_lat <= 90):
        raise HTTPException(status_code=400, detail="spill_lat must be between -90 and 90")
    if not (-180 <= request.spill_lon <= 180):
        raise HTTPException(status_code=400, detail="spill_lon must be between -180 and 180")

    try:
        # ── Fetch AIS vessels ──────────────────────────────────────
        vessels = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_combined_vessels_list(
                global_count=500, indian_count=85, quiet=True
            ),
        )

        if not vessels:
            raise RuntimeError("No AIS vessels were received from the data feed.")

        # Filter to valid ocean coordinates
        valid_vessels = []
        for v in vessels:
            try:
                lat = float(v["latitude"])
                lon = float(v["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180 and is_ocean_coord(lat, lon):
                    valid_vessels.append(v)
            except (ValueError, TypeError, KeyError):
                continue

        # ── Run drift + attribution pipeline ──────────────────────
        analysis = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_drift_analysis_from_spill(
                spill_lat=request.spill_lat,
                spill_lon=request.spill_lon,
                spill_time=spill_time,
                vessels=valid_vessels,
                sensor_name=request.sensor_name or "Sentinel-1A SAR",
                confidence_pct=request.confidence_pct or 92.0,
                geolocation_source=request.geolocation_source or "SAR Detection",
            ),
        )

        suspects = analysis["suspects"]
        suspects_mmsi = {str(s.get("mmsi", "")) for s in suspects}

        spill = serialize_spill(analysis)

        # Limit to 200 vessels for map performance (suspects always included)
        all_vessels = analysis["vessels"]
        suspect_vessels     = [v for v in all_vessels if str(v.get("mmsi", "")) in suspects_mmsi]
        non_suspect_vessels = [v for v in all_vessels if str(v.get("mmsi", "")) not in suspects_mmsi]
        display_vessels = suspect_vessels + non_suspect_vessels[:197]

        serialized_vessels = []
        for i, v in enumerate(display_vessels):
            try:
                serialized_vessels.append(serialize_vessel_for_frontend(v, i, suspects_mmsi))
            except Exception:
                continue

        serialized_suspects = []
        for i, s in enumerate(suspects):
            try:
                sv = serialize_vessel_for_frontend(s, i, suspects_mmsi)
                # Attach full attribution factor breakdown for the panel
                sv["attributionFactors"] = s.get("attribution_factors", [])
                sv["attributionScore"]   = s.get("attribution_score", 0)
                serialized_suspects.append(sv)
            except Exception:
                continue

        return {
            "status": "success",
            "spill": spill,
            "vessels": serialized_vessels,
            "suspects": serialized_suspects,
            "total_vessels": len(all_vessels),
            "total_suspects": len(suspects),
            "detection_time": analysis["detection_time"].isoformat(),
            "spill_lat": round(analysis["spill_lat"], 5),
            "spill_lon": round(analysis["spill_lon"], 5),
            "origin_lat": round(analysis["origin_lat"], 5),
            "origin_lon": round(analysis["origin_lon"], 5),
            "nearest_coast": analysis.get("nearest_coast", {}),
            "trajectory_landmasses": analysis.get("trajectory_landmasses", []),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/run-analysis")
async def run_analysis_deprecated():
    """
    DEPRECATED in v2. This endpoint previously invented a synthetic spill from
    a random AIS vessel — which is incorrect behaviour.

    Use POST /api/run-analysis-from-spill with confirmed SAR spill coordinates.
    """
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": (
                "POST /api/run-analysis is deprecated. "
                "Spill coordinates must come from SAR detection. "
                "Use POST /api/run-analysis-from-spill with "
                "{spill_lat, spill_lon, spill_time} from the SAR analysis result."
            ),
        },
    )


@app.get("/api/vessels")
async def get_vessels(count: int = 100):
    """
    Fetch AIS vessel layer independently of spill state.
    This endpoint powers the always-live AIS overlay on the map.
    It does NOT trigger any spill detection, drift modelling, or suspect ranking.
    """
    try:
        count = min(count, 585)
        global_count  = min(count, 500)
        indian_count  = max(0, count - global_count)

        vessels = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_combined_vessels_list(
                global_count=global_count,
                indian_count=indian_count,
                quiet=True,
            ),
        )

        valid_vessels = []
        for v in vessels:
            try:
                lat = float(v.get("latitude", 0))
                lon = float(v.get("longitude", 0))
                if -90 <= lat <= 90 and -180 <= lon <= 180 and is_ocean_coord(lat, lon):
                    valid_vessels.append(v)
            except (ValueError, TypeError):
                continue

        serialized = []
        for i, v in enumerate(valid_vessels):
            try:
                serialized.append(serialize_vessel_for_frontend(v, i, set()))
            except Exception:
                continue

        return {
            "status": "success",
            "vessels": serialized,
            "total": len(serialized),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
