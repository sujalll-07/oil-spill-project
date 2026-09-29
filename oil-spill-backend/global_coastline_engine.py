"""
Global Dynamic Coastline & Landmass Analysis Engine
----------------------------------------------------
Replaces the hardcoded INDIAN_COAST_POINTS approach with a fully dynamic
global nearest-coastline calculation that works anywhere in the world.

Strategy:
  1. Uses global_land_mask for pixel-level ocean/land detection (already installed).
  2. Performs an adaptive outward grid search from the spill point to find the
     nearest land cell (starts coarse at 1.0° resolution, refines to 0.05°).
  3. Reverse-geocodes the found land cell via the Nominatim API (OpenStreetMap,
     free, no key required) to obtain a human-readable country/region name.
  4. Results are cached in-memory to avoid redundant API calls.

Public API:
  find_nearest_coastline(lat, lon) -> Dict
  find_landmasses_in_drift_path(trajectory_lats, trajectory_lons,
                                trajectory_times) -> List[Dict]
"""

import numpy as np
import urllib.request
import json
import time
import math
from typing import Dict, List, Optional, Tuple

# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_KM = 6371.0

# Nominatim rate-limit: max 1 request/sec (we stay well below)
_NOMINATIM_DELAY_SEC = 1.1
_last_nominatim_call_ts: float = 0.0

# In-memory reverse-geocode cache keyed on rounded (lat, lon)
_geocode_cache: Dict[str, dict] = {}

# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _haversine_km_vectorized(
    spill_lat: float,
    spill_lon: float,
    lats: np.ndarray,
    lons: np.ndarray,
) -> np.ndarray:
    dlat = np.radians(lats - spill_lat)
    dlon = np.radians(lons - spill_lon)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(spill_lat))
        * np.cos(np.radians(lats))
        * np.sin(dlon / 2) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ============================================================
# NOMINATIM REVERSE GEOCODE
# ============================================================

def _reverse_geocode(lat: float, lon: float) -> dict:
    """
    Reverse-geocode a land coordinate to a place name using Nominatim.
    Rounds to 2 decimal places for cache efficiency.
    Respects Nominatim's 1 req/sec rate limit.
    Falls back gracefully when offline.
    """
    global _last_nominatim_call_ts

    cache_key = f"{round(lat, 2)},{round(lon, 2)}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    # Rate-limit enforcement
    elapsed = time.time() - _last_nominatim_call_ts
    if elapsed < _NOMINATIM_DELAY_SEC:
        time.sleep(_NOMINATIM_DELAY_SEC - elapsed)

    result: dict = {}
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?format=json&lat={lat}&lon={lon}&zoom=8&addressdetails=1"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "OilSpillMonitor/2.0 (research prototype)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception:
        # Offline or rate-limited — use empty result; will be named "Unknown"
        result = {}
    finally:
        _last_nominatim_call_ts = time.time()

    _geocode_cache[cache_key] = result
    return result


def _extract_place_name(geocode_result: dict, lat: float, lon: float) -> str:
    """
    Derive a readable coastline region name from a Nominatim reverse-geocode result.
    Returns something like "Sicily, Italy" or "North Sea Coast, Netherlands".
    """
    if not geocode_result:
        # Fallback: describe by hemisphere quadrant
        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"
        return f"Coastline at {abs(round(lat,1))}°{ns} {abs(round(lon,1))}°{ew}"

    addr = geocode_result.get("address", {})
    country = addr.get("country", "")
    state = addr.get("state", addr.get("state_district", addr.get("region", "")))
    county = addr.get("county", addr.get("municipality", ""))

    # Build a meaningful description
    parts = []
    if county and county != state:
        parts.append(county)
    if state and state != country:
        parts.append(state)
    if country:
        parts.append(country)

    if not parts:
        # Fall back to display_name first segment
        display = geocode_result.get("display_name", "")
        parts = [display.split(",")[0].strip()] if display else []

    return ", ".join(parts) if parts else "Unknown Coastline"


# ============================================================
# CORE: FIND NEAREST COASTLINE
# ============================================================

def find_nearest_coastline(
    spill_lat: float,
    spill_lon: float,
    max_search_deg: float = 20.0,
) -> Dict:
    """
    Find the nearest coastline/landmass to a given ocean position.

    Parameters
    ----------
    spill_lat, spill_lon : float
        Ocean coordinates of the oil spill (or any offshore point).
    max_search_deg : float
        Maximum search radius in degrees (default 20° ≈ 2200 km).

    Returns
    -------
    dict with keys:
        distance_km         : float  — straight-line distance to nearest coast
        country_name        : str    — e.g. "Sicily, Italy"
        coast_lat           : float  — lat of nearest land point found
        coast_lon           : float  — lon of nearest land point found
        region_description  : str    — same as country_name (for compatibility)
    """
    try:
        from global_land_mask import globe
    except ImportError:
        return _fallback_coastline_result(spill_lat, spill_lon)

    best_dist_km = float("inf")
    best_lat: Optional[float] = None
    best_lon: Optional[float] = None

    # Multi-resolution search: coarse → medium → fine
    # Each pass narrows the search window around the best candidate found so far.
    resolutions = [1.0, 0.25, 0.05]

    for resolution in resolutions:
        if best_dist_km < float("inf"):
            # Shrink search window to 2× current best distance + 1 buffer degree
            window_deg = min(max_search_deg, (best_dist_km / 111.0) + 1.5)
        else:
            window_deg = max_search_deg

        lat_min = max(-89.9, spill_lat - window_deg)
        lat_max = min(89.9, spill_lat + window_deg)
        lon_min = spill_lon - window_deg
        lon_max = spill_lon + window_deg

        lat_range = np.arange(lat_min, lat_max + resolution, resolution)
        lon_range = np.arange(lon_min, lon_max + resolution, resolution)

        lat_grid, lon_grid = np.meshgrid(lat_range, lon_range, indexing="ij")
        lat_flat = lat_grid.flatten()
        lon_flat = lon_grid.flatten()

        # Normalise longitudes to [-180, 180]
        lon_flat = ((lon_flat + 180.0) % 360.0) - 180.0

        # Land mask (vectorised)
        try:
            is_land = globe.is_land(lat_flat, lon_flat)
        except Exception:
            continue

        land_lats = lat_flat[is_land]
        land_lons = lon_flat[is_land]

        if len(land_lats) == 0:
            continue

        dists = _haversine_km_vectorized(spill_lat, spill_lon, land_lats, land_lons)
        min_idx = int(np.argmin(dists))

        if dists[min_idx] < best_dist_km:
            best_dist_km = float(dists[min_idx])
            best_lat = float(land_lats[min_idx])
            best_lon = float(land_lons[min_idx])

    if best_lat is None:
        return _fallback_coastline_result(spill_lat, spill_lon)

    # Reverse-geocode the found land point
    geocode_result = _reverse_geocode(best_lat, best_lon)
    place_name = _extract_place_name(geocode_result, best_lat, best_lon)

    return {
        "distance_km": round(best_dist_km, 2),
        "country_name": place_name,
        "coast_lat": round(best_lat, 4),
        "coast_lon": round(best_lon, 4),
        "region_description": place_name,
    }


def _fallback_coastline_result(lat: float, lon: float) -> Dict:
    """Graceful fallback when global_land_mask is unavailable."""
    return {
        "distance_km": -1.0,
        "country_name": "Unknown (land mask unavailable)",
        "coast_lat": lat,
        "coast_lon": lon,
        "region_description": "Unknown (land mask unavailable)",
    }


# ============================================================
# CORE: FIND LANDMASSES IN DRIFT PATH
# ============================================================

def find_landmasses_in_drift_path(
    trajectory_lats: np.ndarray,
    trajectory_lons: np.ndarray,
    trajectory_times: list,
    approach_threshold_km: float = 80.0,
    spill_lat: Optional[float] = None,
    spill_lon: Optional[float] = None,
) -> List[Dict]:
    """
    Scan a Lagrangian drift trajectory and identify landmasses that the
    particle cloud approaches or intersects.

    Parameters
    ----------
    trajectory_lats, trajectory_lons : np.ndarray  shape (timesteps, particles)
    trajectory_times                 : list of datetime objects, len == timesteps
    approach_threshold_km            : flag coastlines within this distance (km)
    spill_lat, spill_lon             : original spill position (for reference)

    Returns
    -------
    List of dicts, ordered by ETA (soonest first), each containing:
        country_name        : str
        region_description  : str
        approach_distance_km: float — minimum distance reached
        eta_hours           : float — hours from start when threshold was crossed
        trajectory_hour     : int   — the forecast hour index
        coast_lat           : float
        coast_lon           : float
        already_crossed     : bool  — True if slick has already beached
    """
    try:
        from global_land_mask import globe
    except ImportError:
        return []

    timesteps = trajectory_lats.shape[0]
    affected: List[Dict] = []
    seen_regions: set = set()  # De-duplicate nearby regions

    start_time = trajectory_times[0] if trajectory_times else None

    for step_idx in range(timesteps):
        step_lats = trajectory_lats[step_idx]
        step_lons = trajectory_lons[step_idx]

        # Compute centroid of active particle cloud at this time step
        centroid_lat = float(np.mean(step_lats))
        centroid_lon = float(np.mean(step_lons))

        # Quick check: is the centroid near land?
        coast_info = find_nearest_coastline(centroid_lat, centroid_lon, max_search_deg=5.0)
        dist_km = coast_info["distance_km"]

        if dist_km < 0:
            continue  # land mask unavailable

        if dist_km > approach_threshold_km:
            continue  # Too far from any coast at this step

        # Check if particles have already landed
        try:
            particle_on_land = globe.is_land(step_lats, step_lons)
            beached_pct = float(np.mean(particle_on_land)) * 100.0
        except Exception:
            beached_pct = 0.0

        region_key = coast_info["country_name"]

        # Only record each region once (nearest approach)
        if region_key in seen_regions:
            # Update the record if we're now closer
            for existing in affected:
                if existing["country_name"] == region_key:
                    if dist_km < existing["approach_distance_km"]:
                        existing["approach_distance_km"] = round(dist_km, 2)
            continue

        seen_regions.add(region_key)

        # Compute ETA in hours from simulation start
        if start_time is not None and step_idx < len(trajectory_times):
            step_time = trajectory_times[step_idx]
            try:
                eta_hours = round(
                    (step_time - start_time).total_seconds() / 3600.0, 1
                )
            except Exception:
                eta_hours = round(step_idx * 0.25, 1)  # assume 15-min steps
        else:
            eta_hours = round(step_idx * 0.25, 1)

        affected.append(
            {
                "country_name": coast_info["country_name"],
                "region_description": coast_info["region_description"],
                "approach_distance_km": round(dist_km, 2),
                "eta_hours": eta_hours,
                "trajectory_hour": step_idx,
                "coast_lat": coast_info["coast_lat"],
                "coast_lon": coast_info["coast_lon"],
                "already_crossed": beached_pct > 5.0,
                "beached_percentage": round(beached_pct, 1),
            }
        )

        # Limit to 5 distinct regions to keep output manageable
        if len(affected) >= 5:
            break

    # Sort by ETA (soonest first)
    affected.sort(key=lambda x: x["eta_hours"])
    return affected


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    test_coords = [
        ("Mediterranean (Sicily)", 37.5, 14.5),
        ("North Sea", 55.5, 3.0),
        ("Arabian Sea", 15.0, 67.0),
        ("Gulf of Mexico", 25.0, -90.0),
        ("Bay of Bengal", 15.0, 87.0),
        ("South China Sea", 12.0, 115.0),
    ]

    print("\n" + "=" * 65)
    print("  GLOBAL COASTLINE ENGINE — NEAREST LANDMASS TEST")
    print("=" * 65)

    for label, lat, lon in test_coords:
        result = find_nearest_coastline(lat, lon)
        print(f"\n[{label}]  ({lat:.1f}°N, {lon:.1f}°E)")
        print(f"  Nearest coast : {result['country_name']}")
        print(f"  Distance      : {result['distance_km']} km")
        print(f"  Coast coords  : {result['coast_lat']}°N, {result['coast_lon']}°E")

    print("\n" + "=" * 65 + "\n")
