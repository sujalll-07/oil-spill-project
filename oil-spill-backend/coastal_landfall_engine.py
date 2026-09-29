"""
Forward Lagrangian Oil Spill Drift & Global Coastal Landfall Predictor
-----------------------------------------------------------------------
Features:
- Models forward particle advection using Runge-Kutta 4 (RK4) integration.
- Accounts for Ocean Currents + Wind Drag (3% factor) + Ekman Deflection + Turbulent Diffusion.
- Uses global_coastline_engine for DYNAMIC worldwide nearest-coastline detection.
  Works for any spill location worldwide (Mediterranean, North Sea, Arabian Sea,
  Pacific, Atlantic, Indian Ocean, etc.) — NOT restricted to India only.
- Integrates `global_land_mask` for pixel-level shoreline hit detection.
- Determines whether the slick is:
    1. Drifting towards the nearest coastline (calculates ETA, landfall coordinates,
       coastal country/region, beached particle mass %).
    2. Drifting offshore into open ocean (flags 'No coastal landfall threat').
"""

import numpy as np
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Optional, Callable
from global_land_mask import globe

# ============================================================
# CONSTANTS
# ============================================================
EARTH_RADIUS_METERS = 6371000.0
EARTH_RADIUS_KM = 6371.0





# ============================================================
# GEOMETRY HELPERS
# ============================================================
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(np.radians(lat1))
        * np.cos(np.radians(lat2))
        * np.sin(dlon / 2.0) ** 2
    )
    return float(2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1))))


def meters_to_latlon(dx: np.ndarray, dy: np.ndarray, lat: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    dlat = (dy / EARTH_RADIUS_METERS) * (180.0 / np.pi)
    cos_lat = np.cos(np.radians(lat))
    cos_lat = np.where(np.abs(cos_lat) < 1e-8, 1e-8, cos_lat)
    dlon = (dx / (EARTH_RADIUS_METERS * cos_lat)) * (180.0 / np.pi)
    return dlon, dlat


def rotate_vector(u: np.ndarray, v: np.ndarray, angle_deg: float) -> Tuple[np.ndarray, np.ndarray]:
    rad = np.radians(angle_deg)
    cos_a = np.cos(rad)
    sin_a = np.sin(rad)
    u_rot = u * cos_a + v * sin_a
    v_rot = -u * sin_a + v * cos_a
    return u_rot, v_rot


# ============================================================
# GLOBAL NEAREST COASTLINE (replaces hardcoded INDIAN_COAST_POINTS)
# ============================================================
from global_coastline_engine import find_nearest_coastline as _find_nearest_coastline_global


def find_nearest_coastal_point(lat: float, lon: float) -> Tuple[float, float, str, float]:
    """
    Finds the nearest coastline/landmass to (lat, lon) GLOBALLY.
    Returns (coast_lat, coast_lon, region_name, distance_km).

    Drop-in replacement for the old India-only find_nearest_indian_coastal_point().
    Works for ANY spill location worldwide.
    """
    result = _find_nearest_coastline_global(lat, lon)
    return (
        result["coast_lat"],
        result["coast_lon"],
        result["region_description"],
        result["distance_km"],
    )


# Backward-compatible alias
find_nearest_indian_coastal_point = find_nearest_coastal_point


# ============================================================
# FORWARD LAGRANGIAN DRIFT & LANDFALL ENGINE
# ============================================================
class CoastalLandfallPredictor:
    def __init__(
        self,
        current_velocity: Tuple[float, float],  # (u, v) in m/s (East, North)
        wind_velocity: Tuple[float, float],     # (u, v) in m/s (East, North)
        wind_drift_factor: float = 0.03,
        wind_deflection_angle: float = 12.0,    # Ekman deflection degrees
        horizontal_diffusivity: float = 1.0     # m^2/s
    ):
        self.u_curr, self.v_curr = current_velocity
        self.u_wind, self.v_wind = wind_velocity
        self.wind_drift_factor = wind_drift_factor
        self.wind_deflection_angle = wind_deflection_angle
        self.horizontal_diffusivity = horizontal_diffusivity

    def compute_drift_velocity(self, lons: np.ndarray, lats: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        u_w = np.full_like(lons, self.u_wind, dtype=float)
        v_w = np.full_like(lats, self.v_wind, dtype=float)
        u_w_rot, v_w_rot = rotate_vector(u_w, v_w, self.wind_deflection_angle)
        
        u_drift = self.u_curr + self.wind_drift_factor * u_w_rot
        v_drift = self.v_curr + self.wind_drift_factor * v_w_rot
        return u_drift, v_drift

    def run_forward_prediction(
        self,
        start_lat: float,
        start_lon: float,
        spill_time: datetime,
        max_forecast_hours: int = 120,    # Up to 5 days
        time_step_minutes: int = 15,
        num_particles: int = 500,
        cluster_radius_km: float = 1.5
    ) -> Dict:
        """
        Runs forward RK4 integration to determine if and when the spill hits the Indian coast.
        """
        # 1. Initialize particle cluster around current spill site
        angles = np.random.uniform(0, 2 * np.pi, num_particles)
        radii = np.sqrt(np.random.uniform(0, 1, num_particles)) * (cluster_radius_km * 1000.0)
        dx_init = radii * np.cos(angles)
        dy_init = radii * np.sin(angles)
        
        dlon_init, dlat_init = meters_to_latlon(dx_init, dy_init, np.full(num_particles, start_lat))
        lons = start_lon + dlon_init
        lats = start_lat + dlat_init
        
        # Track particles that have beached (stay locked on land once hit)
        beached_mask = np.zeros(num_particles, dtype=bool)
        beached_times = [None] * num_particles
        beached_coords = [None] * num_particles
        
        dt_sec = time_step_minutes * 60.0
        total_steps = int((max_forecast_hours * 3600) / dt_sec)
        
        curr_time = spill_time
        hourly_tracking = []
        
        initial_nearest_coast = find_nearest_coastal_point(start_lat, start_lon)
        initial_distance_km = initial_nearest_coast[3]
        
        for step in range(1, total_steps + 1):
            curr_time += timedelta(minutes=time_step_minutes)
            
            # Active (unbeached) particles continue to drift
            active_indices = np.where(~beached_mask)[0]
            if len(active_indices) == 0:
                # All particles have made landfall
                break
                
            active_lons = lons[active_indices]
            active_lats = lats[active_indices]
            
            # Forward RK4 Step (+dt_sec)
            u1, v1 = self.compute_drift_velocity(active_lons, active_lats)
            dlon1, dlat1 = meters_to_latlon(u1 * dt_sec, v1 * dt_sec, active_lats)
            
            u2, v2 = self.compute_drift_velocity(active_lons + 0.5 * dlon1, active_lats + 0.5 * dlat1)
            dlon2, dlat2 = meters_to_latlon(u2 * dt_sec, v2 * dt_sec, active_lats + 0.5 * dlat1)
            
            u3, v3 = self.compute_drift_velocity(active_lons + 0.5 * dlon2, active_lats + 0.5 * dlat2)
            dlon3, dlat3 = meters_to_latlon(u3 * dt_sec, v3 * dt_sec, active_lats + 0.5 * dlat2)
            
            u4, v4 = self.compute_drift_velocity(active_lons + dlon3, active_lats + dlat3)
            dlon4, dlat4 = meters_to_latlon(u4 * dt_sec, v4 * dt_sec, active_lats + dlat3)
            
            dlon_adv = (dlon1 + 2 * dlon2 + 2 * dlon3 + dlon4) / 6.0
            dlat_adv = (dlat1 + 2 * dlat2 + 2 * dlat3 + dlat4) / 6.0
            
            # Turbulent Diffusion
            diff_scale = np.sqrt(2.0 * self.horizontal_diffusivity * dt_sec)
            dx_diff = np.random.normal(0.0, diff_scale, size=len(active_indices))
            dy_diff = np.random.normal(0.0, diff_scale, size=len(active_indices))
            dlon_diff, dlat_diff = meters_to_latlon(dx_diff, dy_diff, active_lats)
            
            new_lons = active_lons + dlon_adv + dlon_diff
            new_lats = active_lats + dlat_adv + dlat_diff
            
            # Check for land collision on new positions
            is_on_land = globe.is_land(new_lats, new_lons)
            
            # Also check if within 1.5 km of known Indian coastline coordinates
            for idx_local, global_idx in enumerate(active_indices):
                if is_on_land[idx_local]:
                    beached_mask[global_idx] = True
                    beached_times[global_idx] = curr_time
                    beached_coords[global_idx] = (new_lats[idx_local], new_lons[idx_local])
                else:
                    # Update active coordinate
                    lons[global_idx] = new_lons[idx_local]
                    lats[global_idx] = new_lats[idx_local]
            
            # Record status every 6 hours
            elapsed_hours = step * (time_step_minutes / 60.0)
            if step % int(360 / time_step_minutes) == 0 or len(np.where(~beached_mask)[0]) == 0:
                active_remaining = np.sum(~beached_mask)
                beached_count = np.sum(beached_mask)
                active_lat_mean = float(np.mean(lats[~beached_mask])) if active_remaining > 0 else float(np.mean(lats))
                active_lon_mean = float(np.mean(lons[~beached_mask])) if active_remaining > 0 else float(np.mean(lons))
                coast_info = find_nearest_coastal_point(active_lat_mean, active_lon_mean)
                
                hourly_tracking.append({
                    "forecast_hour": round(elapsed_hours, 1),
                    "forecast_time": curr_time.strftime("%Y-%m-%d %H:%M UTC"),
                    "center_lat": round(active_lat_mean, 4),
                    "center_lon": round(active_lon_mean, 4),
                    "dist_to_coast_km": round(coast_info[3], 2),
                    "nearest_region": coast_info[2],
                    "beached_percent": round((beached_count / num_particles) * 100.0, 1)
                })

        # ============================================================
        # DRIFT DIRECTION & MULTI-TIER COASTAL THREAT ASSESSMENT
        # ============================================================
        beached_count = int(np.sum(beached_mask))
        beached_percentage = (beached_count / num_particles) * 100.0
        
        final_lat_mean = float(np.mean(lats))
        final_lon_mean = float(np.mean(lons))
        final_coast_info = find_nearest_coastal_point(final_lat_mean, final_lon_mean)
        final_distance_km = final_coast_info[3]
        
        # Determine if moving towards or away from coast
        is_moving_towards_coast = (final_distance_km < initial_distance_km) or (beached_count > 0)
        
        # Calculate Landfall ETA
        first_landfall_time = None
        first_landfall_hours = None
        median_landfall_hours = None
        landfall_location = None
        
        if beached_count > 0:
            valid_times = [t for t in beached_times if t is not None]
            first_landfall_time = min(valid_times)
            first_landfall_hours = round((first_landfall_time - spill_time).total_seconds() / 3600.0, 1)
            
            sorted_times = sorted(valid_times)
            median_time = sorted_times[len(sorted_times) // 2]
            median_landfall_hours = round((median_time - spill_time).total_seconds() / 3600.0, 1)
            
            first_idx = beached_times.index(first_landfall_time)
            hit_lat, hit_lon = beached_coords[first_idx]
            nearest_hit_coast = find_nearest_coastal_point(hit_lat, hit_lon)
            landfall_location = {
                "latitude": round(hit_lat, 4),
                "longitude": round(hit_lon, 4),
                "region_name": nearest_hit_coast[2],
                "distance_to_ref_port_km": round(nearest_hit_coast[3], 2)
            }

        # ------------------------------------------------------------
        # Standardized Graded Threat Level Calculation
        # ------------------------------------------------------------
        if not is_moving_towards_coast:
            threat_level = "SAFE"
            threat_badge = "[STATUS: SAFE - NO COASTAL THREAT]"
            threat_desc = "Oil slick is advecting offshore into open oceanic waters. Distance to shoreline is increasing."
        elif first_landfall_hours is not None:
            if first_landfall_hours <= 12 or initial_distance_km <= 20:
                threat_level = "CRITICAL"
                threat_badge = "[THREAT STATUS: CRITICAL - IMMINENT LANDFALL]"
                threat_desc = f"Imminent shoreline impact within {first_landfall_hours} hours. Immediate coastal defense and containment required."
            elif first_landfall_hours <= 36 or initial_distance_km <= 60:
                threat_level = "HIGH"
                threat_badge = "[THREAT STATUS: HIGH - HIGH RISK OF LANDFALL]"
                threat_desc = f"Direct landfall projected in {first_landfall_hours} hours ({first_landfall_time.strftime('%Y-%m-%d %H:%M UTC')}). Urgent deployment recommended."
            elif first_landfall_hours <= 72:
                threat_level = "MODERATE"
                threat_badge = "[THREAT STATUS: MODERATE - COASTAL WATCH / ADVISORY]"
                threat_desc = f"Landfall projected in {first_landfall_hours} hours. Coastal sectors on alert."
            else:
                threat_level = "LOW"
                threat_badge = "[THREAT STATUS: LOW - EXTENDED TIMELINE]"
                threat_desc = f"Long-range landfall potential (ETA: {first_landfall_hours}h). Continued tracking required."
        else:
            # Moving towards coast but hasn't beached within the forecast horizon
            if final_distance_km <= 30:
                threat_level = "MODERATE"
                threat_badge = "[THREAT STATUS: MODERATE - APPROACHING SHORELINE]"
                threat_desc = f"Slick is closing in on the coast (reduced to {round(final_distance_km, 1)} km from shore). Landfall possible with sustained winds."
            else:
                threat_level = "LOW"
                threat_badge = "[THREAT STATUS: LOW - DISTANT APPROACH]"
                threat_desc = f"Slick is drifting slowly towards the coast but remains {round(final_distance_km, 1)} km offshore."

        return {
            "initial_site": {
                "latitude": start_lat,
                "longitude": start_lon,
                "nearest_coast_point": initial_nearest_coast[2],
                "initial_distance_to_coast_km": round(initial_distance_km, 2)
            },
            "forcing_parameters": {
                "current_speed_knots": round(np.hypot(self.u_curr, self.v_curr) * 1.94384, 2),
                "current_direction_deg": round((np.degrees(np.arctan2(self.u_curr, self.v_curr)) + 360) % 360, 1),
                "wind_speed_knots": round(np.hypot(self.u_wind, self.v_wind) * 1.94384, 2),
                "wind_direction_deg": round((np.degrees(np.arctan2(self.u_wind, self.v_wind)) + 360) % 360, 1),
            },
            "drift_classification": "DRIFTING_TOWARDS_COAST" if is_moving_towards_coast else "DRIFTING_OFFSHORE",
            "threat_level": threat_level,
            "threat_badge": threat_badge,
            "threat_description": threat_desc,
            "is_moving_towards_coast": is_moving_towards_coast,
            "has_beached": beached_count > 0,
            "beached_percentage": round(beached_percentage, 1),
            "first_landfall_hours": first_landfall_hours,
            "first_landfall_time": first_landfall_time.strftime("%Y-%m-%d %H:%M UTC") if first_landfall_time else None,
            "median_landfall_hours": median_landfall_hours,
            "landfall_location": landfall_location,
            "final_distance_to_coast_km": round(final_distance_km, 2),
            "trajectory_timeline": hourly_tracking
        }


# ============================================================
# LIVE MARINE WEATHER & OCEAN CURRENT FETCHER (API)
# ============================================================
def fetch_live_marine_forcing(lat: float, lon: float) -> Dict:
    """
    Automatically fetches real-time ocean surface currents and 10m marine winds
    from global meteorological and hydrodynamic APIs (Open-Meteo Marine & GFS/ECMWF)
    for the exact spill GPS coordinates.
    """
    import urllib.request
    import json

    # Default fallbacks if offline
    forcing = {
        "wind_speed_knots": 12.0,
        "wind_from_dir_deg": 240.0,
        "current_speed_knots": 0.5,
        "current_to_dir_deg": 75.0,
        "source": "Fallback Defaults (Offline Mode)"
    }

    try:
        # 1. Fetch live 10m surface winds
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=kn"
        req = urllib.request.Request(w_url, headers={"User-Agent": "LagrangianOilSpill/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            w_data = json.loads(resp.read().decode())
            if "current" in w_data:
                forcing["wind_speed_knots"] = float(w_data["current"].get("wind_speed_10m", 12.0))
                forcing["wind_from_dir_deg"] = float(w_data["current"].get("wind_direction_10m", 240.0))

        # 2. Fetch live hydrodynamic ocean current velocity & direction
        m_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=ocean_current_velocity,ocean_current_direction,wind_wave_height"
        m_req = urllib.request.Request(m_url, headers={"User-Agent": "LagrangianOilSpill/1.0"})
        with urllib.request.urlopen(m_req, timeout=6) as resp:
            m_data = json.loads(resp.read().decode())
            if "current" in m_data:
                curr_kmh = m_data["current"].get("ocean_current_velocity")
                curr_dir = m_data["current"].get("ocean_current_direction")
                if curr_kmh is not None:
                    forcing["current_speed_knots"] = round(float(curr_kmh) * 0.539957, 2)
                if curr_dir is not None:
                    forcing["current_to_dir_deg"] = float(curr_dir)
                wave_h = m_data["current"].get("wind_wave_height")
                if wave_h is not None:
                    forcing["wave_height_meters"] = float(wave_h)

        forcing["source"] = "Live Global Hydrodynamic & Meteorological API (Open-Meteo / ECMWF / NOAA)"
    except Exception as e:
        forcing["source"] = f"Fallback Defaults (API Error: {str(e)})"

    return forcing


# ============================================================
# CONVENIENCE WRAPPER & CLI INTERFACE
# ============================================================
def predict_oil_spill_landfall(
    lat: float,
    lon: float,
    wind_speed_knots: Optional[float] = None,
    wind_from_dir_deg: Optional[float] = None,
    current_speed_knots: Optional[float] = None,
    current_to_dir_deg: Optional[float] = None,
    forecast_hours: int = 72,
    num_particles: int = 500
) -> Dict:
    """
    Evaluates an oil spill input. If wind/currents are omitted, it automatically
    fetches live real-time marine meteorological and ocean current data for (lat, lon).
    """
    # Auto-fetch if any forcing parameter is not provided
    live_data = None
    if any(p is None for p in [wind_speed_knots, wind_from_dir_deg, current_speed_knots, current_to_dir_deg]):
        live_data = fetch_live_marine_forcing(lat, lon)
        if wind_speed_knots is None:
            wind_speed_knots = live_data["wind_speed_knots"]
        if wind_from_dir_deg is None:
            wind_from_dir_deg = live_data["wind_from_dir_deg"]
        if current_speed_knots is None:
            current_speed_knots = live_data["current_speed_knots"]
        if current_to_dir_deg is None:
            current_to_dir_deg = live_data["current_to_dir_deg"]

    # Convert wind meteorological 'from' direction (towards direction is from + 180)
    wind_to_rad = np.radians((wind_from_dir_deg + 180.0) % 360.0)
    wind_speed_ms = wind_speed_knots * 0.514444
    u_wind = wind_speed_ms * np.sin(wind_to_rad)
    v_wind = wind_speed_ms * np.cos(wind_to_rad)

    # Convert ocean current 'to' direction
    curr_to_rad = np.radians(current_to_dir_deg % 360.0)
    curr_speed_ms = current_speed_knots * 0.514444
    u_curr = curr_speed_ms * np.sin(curr_to_rad)
    v_curr = curr_speed_ms * np.cos(curr_to_rad)

    predictor = CoastalLandfallPredictor(
        current_velocity=(u_curr, v_curr),
        wind_velocity=(u_wind, v_wind),
        wind_drift_factor=0.03,
        wind_deflection_angle=12.0
    )

    now_utc = datetime.now(timezone.utc)
    res = predictor.run_forward_prediction(
        start_lat=lat,
        start_lon=lon,
        spill_time=now_utc,
        max_forecast_hours=forecast_hours,
        time_step_minutes=15,
        num_particles=num_particles
    )

    if live_data:
        res["forcing_source"] = live_data.get("source", "Live API")
    else:
        res["forcing_source"] = "Manual User Input"

    return res


def print_landfall_report(result: Dict):
    """Prints a clean, single report with standardized Threat Status."""
    init_site = result["initial_site"]
    forcing = result["forcing_parameters"]
    source = result.get("forcing_source", "Auto / Live API")
    
    print("\n" + "=" * 75)
    print("       GLOBAL COASTLINE OIL SPILL FORWARD DRIFT REPORT")
    print("=" * 75)
    print(f"Detected Spill Coordinates : {init_site['latitude']:.4f}°N, {init_site['longitude']:.4f}°E")
    print(f"Nearest Coastline Segment   : {init_site['nearest_coast_point']}")
    print(f"Initial Distance to Shore  : {init_site['initial_distance_to_coast_km']} km")
    print("-" * 75)
    print(f"Environmental Data Source  : {source}")
    print(f"Live Surface Wind Forcing  : {forcing['wind_speed_knots']} kts @ {forcing['wind_direction_deg']}° (Towards)")
    print(f"Live Ocean Current Forcing : {forcing['current_speed_knots']} kts @ {forcing['current_direction_deg']}° (Towards)")
    print("-" * 75)
    print(f"Drift Classification       : >>> {result['drift_classification']} <<<")
    print(f"Coastal Threat Status      : {result['threat_badge']}")
    print(f"Threat Advisory            : {result['threat_description']}")
    
    if result["has_beached"]:
        loc = result["landfall_location"]
        print("-" * 75)
        print("LANDFALL IMPACT DETAILS:")
        print(f"  • Estimated First Landfall (ETA) : {result['first_landfall_hours']} hours ({result['first_landfall_time']})")
        print(f"  • 50% Mass Landfall Time         : {result['median_landfall_hours']} hours")
        print(f"  • Impact Coastal Region          : {loc['region_name']}")
        print(f"  • Landfall GPS Coordinates       : {loc['latitude']}°N, {loc['longitude']}°E")
        print(f"  • Total Beached Mass             : {result['beached_percentage']}% of slick")
        
        print("\n--- Drift Timeline (Approaching Shore) ---")
        for log in result["trajectory_timeline"]:
            print(f"  T+{log['forecast_hour']:>4}h | Dist to Shore: {log['dist_to_coast_km']:>6.1f} km | Beached: {log['beached_percent']:>5.1f}% | Target: {log['nearest_region']}")
    else:
        print("-" * 75)
        print("OFFSHORE TRACKING DETAILS:")
        print(f"  • Distance to coast at T+{len(result['trajectory_timeline'])*6}h : {result['final_distance_to_coast_km']} km")
        print(f"  • No shoreline interception detected within the forecast horizon.")
    
    print("=" * 75 + "\n")


# ============================================================
# MAIN EXECUTION (Single Input - Auto-fetching APIs)
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predict Global Coastline Landfall for an Oil Spill (Auto-fetches live winds and currents)")
    parser.add_argument("--lat", type=float, default=18.95, help="Spill Latitude (default: 18.95 - off Mumbai)")
    parser.add_argument("--lon", type=float, default=72.10, help="Spill Longitude (default: 72.10 - off Mumbai)")
    parser.add_argument("--wind-speed", type=float, default=None, help="Wind speed in knots (Optional, auto-fetched if omitted)")
    parser.add_argument("--wind-from", type=float, default=None, help="Wind FROM direction in degrees (Optional, auto-fetched if omitted)")
    parser.add_argument("--current-speed", type=float, default=None, help="Ocean current speed in knots (Optional, auto-fetched if omitted)")
    parser.add_argument("--current-to", type=float, default=None, help="Ocean current TO direction in degrees (Optional, auto-fetched if omitted)")
    parser.add_argument("--hours", type=int, default=72, help="Forecast horizon in hours (default: 72)")

    args = parser.parse_args()

    # Run single forecast - automatically pulls live API data if winds/currents are omitted!
    result = predict_oil_spill_landfall(
        lat=args.lat,
        lon=args.lon,
        wind_speed_knots=args.wind_speed,
        wind_from_dir_deg=args.wind_from,
        current_speed_knots=args.current_speed,
        current_to_dir_deg=args.current_to,
        forecast_hours=args.hours
    )

    print_landfall_report(result)

