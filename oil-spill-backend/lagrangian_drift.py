"""
Global Lagrangian 2D Oil Spill Drift & AIS Correlation Engine
--------------------------------------------------------------

Synthetic prototype version.

Features:
- Works worldwide.
- Uses vessel coordinates supplied by ais_real_test.py.
- Automatically selects a valid AIS vessel location as the
  synthetic oil-spill detection location.
- Creates synthetic oil particles around that location.
- Performs 12-hour backward RK4 hindcast.
- Uses synthetic current and wind fields.
- Correlates the estimated origin with 100 AIS vessels.
- Returns the top 3 suspect vessels.
"""

import numpy as np

from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Optional, Callable

from ais_real_test import get_vessels_list, is_ocean_coord


# ============================================================
# CONSTANTS
# ============================================================

EARTH_RADIUS_METERS = 6371000.0
EARTH_RADIUS_KM = 6371.0


# ============================================================
# METERS TO LAT/LON
# ============================================================

def meters_to_latlon(
    dx: np.ndarray,
    dy: np.ndarray,
    lat: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:

    dlat = (
        dy / EARTH_RADIUS_METERS
    ) * (
        180.0 / np.pi
    )

    cos_lat = np.cos(
        np.radians(lat)
    )

    # Prevent division problems near the poles
    cos_lat = np.where(
        np.abs(cos_lat) < 1e-8,
        1e-8,
        cos_lat
    )

    dlon = (
        dx / (
            EARTH_RADIUS_METERS * cos_lat
        )
    ) * (
        180.0 / np.pi
    )

    return dlon, dlat


# ============================================================
# ROTATE WIND VECTOR
# ============================================================

def rotate_vector(
    u: np.ndarray,
    v: np.ndarray,
    angle_deg: float
) -> Tuple[np.ndarray, np.ndarray]:

    rad = np.radians(
        angle_deg
    )

    cos_a = np.cos(rad)
    sin_a = np.sin(rad)

    u_rot = (
        u * cos_a +
        v * sin_a
    )

    v_rot = (
        -u * sin_a +
        v * cos_a
    )

    return u_rot, v_rot


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:

    dlat = np.radians(
        lat2 - lat1
    )

    dlon = np.radians(
        lon2 - lon1
    )

    a = (
        np.sin(dlat / 2.0) ** 2
        +
        np.cos(np.radians(lat1))
        *
        np.cos(np.radians(lat2))
        *
        np.sin(dlon / 2.0) ** 2
    )

    return float(
        2.0
        * EARTH_RADIUS_KM
        * np.arcsin(
            np.sqrt(
                np.clip(a, 0, 1)
            )
        )
    )


# ============================================================
# ENVIRONMENTAL FIELD
# ============================================================

class EnvironmentalField:

    def __init__(
        self,
        current_func: Optional[
            Callable[
                [np.ndarray, np.ndarray, datetime],
                Tuple[np.ndarray, np.ndarray]
            ]
        ] = None,

        wind_func: Optional[
            Callable[
                [np.ndarray, np.ndarray, datetime],
                Tuple[np.ndarray, np.ndarray]
            ]
        ] = None,

        default_current: Tuple[
            float,
            float
        ] = (0.20, -0.10),

        default_wind: Tuple[
            float,
            float
        ] = (5.0, 3.0)
    ):

        self.current_func = current_func
        self.wind_func = wind_func

        self.default_current = (
            default_current
        )

        self.default_wind = (
            default_wind
        )


    def get_current(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t: datetime
    ) -> Tuple[np.ndarray, np.ndarray]:

        if self.current_func:

            return self.current_func(
                lons,
                lats,
                t
            )

        u = np.full_like(
            lons,
            self.default_current[0],
            dtype=float
        )

        v = np.full_like(
            lats,
            self.default_current[1],
            dtype=float
        )

        return u, v


    def get_wind(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t: datetime
    ) -> Tuple[np.ndarray, np.ndarray]:

        if self.wind_func:

            return self.wind_func(
                lons,
                lats,
                t
            )

        u = np.full_like(
            lons,
            self.default_wind[0],
            dtype=float
        )

        v = np.full_like(
            lats,
            self.default_wind[1],
            dtype=float
        )

        return u, v


# ============================================================
# LAGRANGIAN DRIFT MODEL
# ============================================================

class LagrangianDriftModel:

    def __init__(
        self,
        env: EnvironmentalField,
        wind_drift_factor: float = 0.03,
        wind_deflection_angle: float = 10.0,
        horizontal_diffusivity: float = 1.0
    ):

        self.env = env

        self.wind_drift_factor = (
            wind_drift_factor
        )

        self.wind_deflection_angle = (
            wind_deflection_angle
        )

        self.horizontal_diffusivity = (
            horizontal_diffusivity
        )


    # --------------------------------------------------------
    # DRIFT VELOCITY
    # --------------------------------------------------------

    def compute_drift_velocity(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t: datetime
    ) -> Tuple[np.ndarray, np.ndarray]:

        u_curr, v_curr = (
            self.env.get_current(
                lons,
                lats,
                t
            )
        )

        u_wind, v_wind = (
            self.env.get_wind(
                lons,
                lats,
                t
            )
        )

        u_wind_rot, v_wind_rot = (
            rotate_vector(
                u_wind,
                v_wind,
                self.wind_deflection_angle
            )
        )

        u_drift = (
            u_curr
            +
            self.wind_drift_factor
            *
            u_wind_rot
        )

        v_drift = (
            v_curr
            +
            self.wind_drift_factor
            *
            v_wind_rot
        )

        return u_drift, v_drift


    # --------------------------------------------------------
    # BACKWARD HINDCAST
    # --------------------------------------------------------

    def run_hindcast(
        self,
        initial_lons: np.ndarray,
        initial_lats: np.ndarray,
        start_time: datetime,
        duration: timedelta,
        time_step: timedelta = timedelta(
            minutes=15
        ),
        method: str = "rk4"
    ) -> Dict[str, np.ndarray]:

        dt_sec = (
            time_step.total_seconds()
        )

        total_steps = int(
            duration.total_seconds()
            /
            dt_sec
        )

        num_particles = len(
            initial_lons
        )

        lons_history = np.zeros(
            (
                total_steps + 1,
                num_particles
            )
        )

        lats_history = np.zeros(
            (
                total_steps + 1,
                num_particles
            )
        )

        times_history = []

        curr_lons = (
            initial_lons.copy()
        )

        curr_lats = (
            initial_lats.copy()
        )

        curr_time = start_time

        lons_history[0] = curr_lons
        lats_history[0] = curr_lats

        times_history.append(
            curr_time
        )


        # ----------------------------------------------------
        # TIME LOOP
        # ----------------------------------------------------

        for step in range(
            1,
            total_steps + 1
        ):

            if method.lower() == "rk4":

                u1, v1 = (
                    self.compute_drift_velocity(
                        curr_lons,
                        curr_lats,
                        curr_time
                    )
                )

                dlon1, dlat1 = (
                    meters_to_latlon(
                        u1 * -dt_sec,
                        v1 * -dt_sec,
                        curr_lats
                    )
                )


                u2, v2 = (
                    self.compute_drift_velocity(
                        curr_lons + 0.5 * dlon1,
                        curr_lats + 0.5 * dlat1,
                        curr_time - time_step / 2
                    )
                )

                dlon2, dlat2 = (
                    meters_to_latlon(
                        u2 * -dt_sec,
                        v2 * -dt_sec,
                        curr_lats + 0.5 * dlat1
                    )
                )


                u3, v3 = (
                    self.compute_drift_velocity(
                        curr_lons + 0.5 * dlon2,
                        curr_lats + 0.5 * dlat2,
                        curr_time - time_step / 2
                    )
                )

                dlon3, dlat3 = (
                    meters_to_latlon(
                        u3 * -dt_sec,
                        v3 * -dt_sec,
                        curr_lats + 0.5 * dlat2
                    )
                )


                u4, v4 = (
                    self.compute_drift_velocity(
                        curr_lons + dlon3,
                        curr_lats + dlat3,
                        curr_time - time_step
                    )
                )

                dlon4, dlat4 = (
                    meters_to_latlon(
                        u4 * -dt_sec,
                        v4 * -dt_sec,
                        curr_lats + dlat3
                    )
                )


                dlon_adv = (
                    dlon1
                    +
                    2 * dlon2
                    +
                    2 * dlon3
                    +
                    dlon4
                ) / 6.0


                dlat_adv = (
                    dlat1
                    +
                    2 * dlat2
                    +
                    2 * dlat3
                    +
                    dlat4
                ) / 6.0


            else:

                u, v = (
                    self.compute_drift_velocity(
                        curr_lons,
                        curr_lats,
                        curr_time
                    )
                )

                dlon_adv, dlat_adv = (
                    meters_to_latlon(
                        u * -dt_sec,
                        v * -dt_sec,
                        curr_lats
                    )
                )


            # ------------------------------------------------
            # TURBULENT DIFFUSION
            # ------------------------------------------------

            if self.horizontal_diffusivity > 0:

                diff_scale = np.sqrt(
                    2.0
                    *
                    self.horizontal_diffusivity
                    *
                    dt_sec
                )

                dx_diff = np.random.normal(
                    0.0,
                    diff_scale,
                    size=num_particles
                )

                dy_diff = np.random.normal(
                    0.0,
                    diff_scale,
                    size=num_particles
                )

                dlon_diff, dlat_diff = (
                    meters_to_latlon(
                        dx_diff,
                        dy_diff,
                        curr_lats
                    )
                )

            else:

                dlon_diff = 0.0
                dlat_diff = 0.0


            prev_lons = curr_lons.copy()
            prev_lats = curr_lats.copy()

            curr_lons += (
                dlon_adv
                +
                dlon_diff
            )

            curr_lats += (
                dlat_adv
                +
                dlat_diff
            )


            # Keep latitude valid worldwide
            curr_lats = np.clip(
                curr_lats,
                -89.9,
                89.9
            )

            # Keep longitude inside [-180, 180]
            curr_lons = (
                (curr_lons + 180.0)
                % 360.0
            ) - 180.0

            # Strict ocean constraint: prevent particles from drifting onto land
            ocean_mask = is_ocean_coord(curr_lats, curr_lons)
            if not np.all(ocean_mask):
                curr_lons = np.where(ocean_mask, curr_lons, prev_lons)
                curr_lats = np.where(ocean_mask, curr_lats, prev_lats)


            curr_time -= time_step

            lons_history[step] = (
                curr_lons
            )

            lats_history[step] = (
                curr_lats
            )

            times_history.append(
                curr_time
            )


        return {

            "times":
                times_history,

            "lons":
                lons_history,

            "lats":
                lats_history
        }


# ============================================================
# CREATE SYNTHETIC SPILL AROUND AIS VESSEL
# ============================================================

def create_synthetic_spill_from_vessel(
    vessel: Dict,
    num_points: int = 1000,
    radius_km: float = 2.0
) -> Tuple[np.ndarray, np.ndarray]:

    center_lat = float(
        vessel["latitude"]
    )

    center_lon = float(
        vessel["longitude"]
    )


    # Random points in a circular area
    angles = np.random.uniform(
        0,
        2 * np.pi,
        num_points
    )

    distances = (
        np.sqrt(
            np.random.uniform(
                0,
                1,
                num_points
            )
        )
        *
        radius_km
    )


    # Convert km to meters
    distances_m = (
        distances * 1000.0
    )


    dx = (
        distances_m
        *
        np.cos(angles)
    )

    dy = (
        distances_m
        *
        np.sin(angles)
    )


    lons, lats = meters_to_latlon(
        dx,
        dy,
        np.full(
            num_points,
            center_lat
        )
    )


    lons += center_lon
    lats += center_lat


    # Worldwide boundaries
    lats = np.clip(
        lats,
        -89.9,
        89.9
    )

    lons = (
        (lons + 180.0)
        % 360.0
    ) - 180.0

    # STRICT OCEAN CONSTRAINT: Ensure all oil spill particles are strictly in the sea region
    ocean_mask = is_ocean_coord(lats, lons)
    max_iter = 25
    iter_count = 0
    while not np.all(ocean_mask) and iter_count < max_iter:
        land_idx = np.where(~ocean_mask)[0]
        # Contract land particles 50% closer to center_lat, center_lon (sea location)
        lats[land_idx] = 0.5 * (lats[land_idx] + center_lat)
        lons[land_idx] = 0.5 * (lons[land_idx] + center_lon)
        ocean_mask = is_ocean_coord(lats, lons)
        iter_count += 1

    return lons, lats


# ============================================================
# CORRELATE WITH AIS VESSELS
# ============================================================

def correlate_with_vessel_tracks(
    hindcast_results: Dict[str, np.ndarray],
    vessels: List[Dict],
    top_k: int = 3
) -> List[Dict]:

    origin_lons = (
        hindcast_results["lons"][-1]
    )

    origin_lats = (
        hindcast_results["lats"][-1]
    )


    origin_center_lon = float(
        np.mean(origin_lons)
    )

    origin_center_lat = float(
        np.mean(origin_lats)
    )


    scored_vessels = []


    # --------------------------------------------------------
    # CHECK EVERY VESSEL
    # --------------------------------------------------------

    for vessel in vessels:

        try:

            v_lat = float(
                vessel["latitude"]
            )

            v_lon = float(
                vessel["longitude"]
            )

        except (
            TypeError,
            ValueError,
            KeyError
        ):

            continue


        # Distance to estimated origin
        dist_to_origin_km = (
            haversine_km(
                v_lat,
                v_lon,
                origin_center_lat,
                origin_center_lon
            )
        )


        # Distance from vessel to every
        # hindcast particle
        dlat_orig = np.radians(
            origin_lats - v_lat
        )

        dlon_orig = np.radians(
            origin_lons - v_lon
        )


        a_orig = (
            np.sin(
                dlat_orig / 2.0
            ) ** 2

            +

            np.cos(
                np.radians(v_lat)
            )

            *

            np.cos(
                np.radians(origin_lats)
            )

            *

            np.sin(
                dlon_orig / 2.0
            ) ** 2
        )


        dists_to_cluster = (
            2
            *
            EARTH_RADIUS_KM
            *
            np.arcsin(
                np.sqrt(
                    np.clip(
                        a_orig,
                        0,
                        1
                    )
                )
            )
        )


        min_cluster_dist_km = float(
            np.min(
                dists_to_cluster
            )
        )


        vessel_entry = vessel.copy()


        vessel_entry[
            "closest_distance_km"
        ] = round(
            min_cluster_dist_km,
            2
        )


        vessel_entry[
            "dist_to_origin_km"
        ] = round(
            dist_to_origin_km,
            2
        )


        scored_vessels.append(
            vessel_entry
        )


    # --------------------------------------------------------
    # SORT BY DISTANCE
    # --------------------------------------------------------

    scored_vessels.sort(
        key=lambda x:
        x["closest_distance_km"]
    )


    top_vessels = (
        scored_vessels[:top_k]
    )


    # --------------------------------------------------------
    # SYNTHETIC CORRELATION SCORE
    # --------------------------------------------------------

    used_scores = set()


    for vessel in top_vessels:

        dist = vessel[
            "closest_distance_km"
        ]


        raw_score = round(
            max(
                5.0,
                98.5
                *
                np.exp(
                    -dist / 8.0
                )
            ),
            1
        )


        # Ensure distinct scores
        while raw_score in used_scores:

            raw_score = round(
                max(
                    1.0,
                    raw_score - 2.5
                ),
                1
            )


        vessel[
            "match_percentage"
        ] = raw_score


        used_scores.add(
            raw_score
        )


    return top_vessels


# ============================================================
# SELECT VALID GLOBAL AIS VESSEL
# ============================================================

def select_global_spill_location(
    vessels: List[Dict]
) -> Dict:

    valid_vessels = []


    for vessel in vessels:

        try:

            lat = float(
                vessel["latitude"]
            )

            lon = float(
                vessel["longitude"]
            )

            if (
                -90 <= lat <= 90
                and
                -180 <= lon <= 180
                and
                is_ocean_coord(lat, lon)
            ):

                valid_vessels.append(
                    vessel
                )

        except (
            TypeError,
            ValueError,
            KeyError
        ):

            continue


    if not valid_vessels:

        raise ValueError(
            "No valid AIS vessel coordinates found."
        )


    # Randomly choose one valid vessel
    # as the synthetic spill location
    selected = np.random.choice(
        valid_vessels
    )


    return selected


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 75)

    print(
        "       GLOBAL LAGRANGIAN OIL SPILL"
    )

    print(
        "       DRIFT + AIS CORRELATION ENGINE"
    )

    print("=" * 75)


    # --------------------------------------------------------
    # 1. FETCH 100 WORLDWIDE AIS VESSELS
    # --------------------------------------------------------

    print(
        "\n[1] Fetching 100 worldwide AIS vessels..."
    )


    ais_vessels = get_vessels_list(
        count=100,
        quiet=True
    )


    print(
        f"[OK] Loaded {len(ais_vessels)} AIS vessels."
    )


    if len(ais_vessels) == 0:

        raise RuntimeError(
            "No AIS vessels were received."
        )


    # --------------------------------------------------------
    # 2. SELECT GLOBAL SYNTHETIC SPILL LOCATION
    # --------------------------------------------------------

    selected_vessel = (
        select_global_spill_location(
            ais_vessels
        )
    )


    spill_lat = float(
        selected_vessel["latitude"]
    )

    spill_lon = float(
        selected_vessel["longitude"]
    )


    print(
        "\n[2] Synthetic spill location:"
    )

    print(
        f"    Latitude  : {spill_lat:.5f}"
    )

    print(
        f"    Longitude : {spill_lon:.5f}"
    )

    print(
        f"    Based on vessel: "
        f"{selected_vessel.get('ship_name', 'UNKNOWN')}"
    )


    # --------------------------------------------------------
    # 3. CREATE SYNTHETIC OIL PARTICLES
    # --------------------------------------------------------

    num_particles = 1000


    print(
        f"\n[3] Creating {num_particles} "
        "synthetic oil particles..."
    )


    lons, lats = (
        create_synthetic_spill_from_vessel(
            selected_vessel,
            num_points=num_particles,
            radius_km=2.0
        )
    )


    detection_center_lon = float(
        np.mean(lons)
    )

    detection_center_lat = float(
        np.mean(lats)
    )


    # --------------------------------------------------------
    # 4. SYNTHETIC ENVIRONMENT
    # --------------------------------------------------------

    env = EnvironmentalField(

        default_current=(
            0.20,
            -0.10
        ),

        default_wind=(
            5.0,
            3.0
        )
    )


    # --------------------------------------------------------
    # 5. CREATE LAGRANGIAN MODEL
    # --------------------------------------------------------

    model = LagrangianDriftModel(

        env=env,

        wind_drift_factor=0.03,

        wind_deflection_angle=12.0,

        horizontal_diffusivity=1.0
    )


    # --------------------------------------------------------
    # 6. RUN 12-HOUR HINDCAST
    # --------------------------------------------------------

    detection_time = datetime.now(
        timezone.utc
    )


    hindcast_duration = timedelta(
        hours=12
    )


    print(
        "\n[4] Running 12-hour "
        "backward RK4 hindcast..."
    )


    results = model.run_hindcast(

        initial_lons=lons,

        initial_lats=lats,

        start_time=detection_time,

        duration=hindcast_duration,

        time_step=timedelta(
            minutes=15
        ),

        method="rk4"
    )


    # --------------------------------------------------------
    # 7. ESTIMATED ORIGIN
    # --------------------------------------------------------

    origin_center_lon = float(
        np.mean(
            results["lons"][-1]
        )
    )

    origin_center_lat = float(
        np.mean(
            results["lats"][-1]
        )
    )


    print(
        "\n" + "=" * 75
    )

    print(
        "                 OIL SPILL ANALYSIS"
    )

    print(
        "=" * 75
    )


    print(
        f"\nDetection Latitude  : "
        f"{detection_center_lat:.5f}"
    )

    print(
        f"Detection Longitude : "
        f"{detection_center_lon:.5f}"
    )


    print(
        f"\n12-Hour Origin Latitude  : "
        f"{origin_center_lat:.5f}"
    )

    print(
        f"12-Hour Origin Longitude : "
        f"{origin_center_lon:.5f}"
    )


    print(
        f"\nDetection Time : "
        f"{detection_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )


    print(
        f"Estimated Discharge Time : "
        f"{(
            detection_time -
            hindcast_duration
        ).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )


    # --------------------------------------------------------
    # 8. CORRELATE WITH 100 AIS VESSELS
    # --------------------------------------------------------

    print(
        "\n[5] Correlating with "
        f"{len(ais_vessels)} AIS vessels..."
    )


    top_suspects = (
        correlate_with_vessel_tracks(
            results,
            ais_vessels,
            top_k=3
        )
    )


    # --------------------------------------------------------
    # 9. DISPLAY TOP SUSPECTS
    # --------------------------------------------------------

    print(
        "\n" + "=" * 75
    )

    print(
        "              TOP 3 SUSPECT VESSELS"
    )

    print(
        "=" * 75
    )


    for rank, vessel in enumerate(
        top_suspects,
        1
    ):

        print(
            "\n" + "-" * 75
        )

        print(
            f"SUSPECT #{rank}"
        )

        print(
            "-" * 75
        )

        print(
            f"Ship Name          : "
            f"{vessel.get('ship_name', 'UNKNOWN')}"
        )

        print(
            f"MMSI               : "
            f"{vessel.get('mmsi', 'UNKNOWN')}"
        )

        print(
            f"Latitude           : "
            f"{vessel.get('latitude')}"
        )

        print(
            f"Longitude          : "
            f"{vessel.get('longitude')}"
        )

        print(
            f"Speed              : "
            f"{vessel.get('speed_knots')} knots"
        )

        print(
            f"Course             : "
            f"{vessel.get('course_degrees')}°"
        )

        print(
            f"Heading            : "
            f"{vessel.get('heading_degrees')}°"
        )

        print(
            f"Status             : "
            f"{vessel.get('status')}"
        )

        print(
            f"Closest Distance   : "
            f"{vessel.get('closest_distance_km')} km"
        )

        print(
            f"Distance to Origin : "
            f"{vessel.get('dist_to_origin_km')} km"
        )

        print(
            f"Correlation Score  : "
            f"{vessel.get('match_percentage')}%"
        )


    print(
        "\n" + "=" * 75
    )

    print(
        "GLOBAL AIS + LAGRANGIAN ANALYSIS COMPLETE"
    )

    print(
        "=" * 75
    )