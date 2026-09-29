import streamlit as st
import tensorflow as tf
import numpy as np
import pandas as pd

from PIL import Image
from datetime import datetime, timezone, timedelta

from streamlit_folium import st_folium
import folium

from ais_real_test import get_vessels_list, get_indian_ocean_vessels_list, get_combined_vessels_list, is_ocean_coord

from lagrangian_drift import (
    EnvironmentalField,
    LagrangianDriftModel,
    create_synthetic_spill_from_vessel,
    correlate_with_vessel_tracks
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Oil Spill Intelligence System",
    page_icon="🌊",
    layout="wide"
)


# ============================================================
# SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH = 224

MODEL_PATH = "oil_spill_classifier.keras"


# ============================================================
# LOAD TRAINED AI MODEL
# ============================================================

@st.cache_resource
def load_ai_model():

    return tf.keras.models.load_model(
        MODEL_PATH
    )


model = load_ai_model()


# ============================================================
# AI OIL SPILL PREDICTION
# ============================================================

def predict_oil_spill(image):

    image = image.convert("RGB")

    image = image.resize(
        (IMG_WIDTH, IMG_HEIGHT)
    )

    image_array = np.array(
        image
    ).astype(
        np.float32
    )

    image_array = (
        tf.keras.applications.mobilenet_v2
        .preprocess_input(
            image_array
        )
    )

    image_array = np.expand_dims(
        image_array,
        axis=0
    )

    probability = model.predict(
        image_array,
        verbose=0
    )[0][0]

    return float(probability)


# ============================================================
# RUN LAGRANGIAN + AIS ANALYSIS
# ============================================================

def run_drift_analysis():

    # --------------------------------------------------------
    # GET 585 VESSELS (500 GLOBAL + 85 INDIAN OCEAN REGION)
    # --------------------------------------------------------

    vessels = get_combined_vessels_list(
        global_count=500,
        indian_count=85,
        quiet=False
    )

    if not vessels:

        raise RuntimeError(
            "No AIS vessels were received."
        )


    # --------------------------------------------------------
    # KEEP ONLY VALID OCEAN COORDINATES (STRICT LAND MASK)
    # --------------------------------------------------------

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
            ValueError,
            TypeError,
            KeyError
        ):

            continue


    if not valid_vessels:

        raise RuntimeError(
            "No valid AIS coordinates found."
        )


    # --------------------------------------------------------
    # SELECT ONE AIS VESSEL
    # AS SYNTHETIC SPILL LOCATION
    # --------------------------------------------------------

    selected_vessel = np.random.choice(
        valid_vessels
    )


    # --------------------------------------------------------
    # CREATE SYNTHETIC OIL SPILL
    # AROUND SELECTED AIS LOCATION
    # --------------------------------------------------------

    num_particles = 1000

    lons, lats = (
        create_synthetic_spill_from_vessel(
            selected_vessel,
            num_points=num_particles,
            radius_km=2.0
        )
    )


    # --------------------------------------------------------
    # DETECTION CENTER
    # --------------------------------------------------------

    detection_center_lon = float(
        np.mean(lons)
    )

    detection_center_lat = float(
        np.mean(lats)
    )


    # --------------------------------------------------------
    # ENVIRONMENT
    # CURRENTLY SYNTHETIC
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
    # LAGRANGIAN MODEL
    # --------------------------------------------------------

    drift_model = LagrangianDriftModel(

        env=env,

        wind_drift_factor=0.03,

        wind_deflection_angle=12.0,

        horizontal_diffusivity=1.0
    )


    # --------------------------------------------------------
    # DETECTION TIME
    # --------------------------------------------------------

    detection_time = datetime.now(
        timezone.utc
    )


    # --------------------------------------------------------
    # 12-HOUR BACKWARD HINDCAST
    # --------------------------------------------------------

    hindcast_duration = timedelta(
        hours=12
    )


    results = drift_model.run_hindcast(

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
    # ESTIMATED OIL ORIGIN
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


    # --------------------------------------------------------
    # CORRELATE WITH AIS VESSELS
    # --------------------------------------------------------

    suspects = correlate_with_vessel_tracks(

        results,

        vessels,

        top_k=3
    )


    return {

        "detection_center_lat":
            detection_center_lat,

        "detection_center_lon":
            detection_center_lon,

        "origin_lat":
            origin_center_lat,

        "origin_lon":
            origin_center_lon,

        "detection_time":
            detection_time,

        "vessels":
            vessels,

        "suspects":
            suspects,

        "results":
            results,

        "selected_vessel":
            selected_vessel
    }


# ============================================================
# HEADER
# ============================================================

st.title(
    "🌊 Oil Spill Intelligence & Vessel Correlation System"
)

st.markdown(
    """
    **AI-based SAR detection + Lagrangian drift hindcast +
    live AIS vessel correlation**
    """
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "System Status"
    )

    st.success(
        "AI Model: Loaded"
    )

    st.success(
        "AIS: Live"
    )

    st.warning(
        "Lagrangian: Synthetic Environment"
    )

    st.divider()

    st.write(
        "Current prototype uses synthetic "
        "ocean current and wind values."
    )


# ============================================================
# 1. SAR IMAGE ANALYSIS
# ============================================================

st.header(
    "1. SAR Image Analysis"
)

upload_col, image_col = st.columns(
    [1, 1]
)


with upload_col:

    uploaded_file = st.file_uploader(

        "Upload SAR Image",

        type=[
            "png",
            "jpg",
            "jpeg",
            "tif",
            "tiff"
        ]
    )


with image_col:

    if uploaded_file is not None:

        image = Image.open(
            uploaded_file
        )

        st.image(
            image,
            caption="Uploaded SAR Image",
            use_container_width=True
        )


# ============================================================
# AI ANALYSIS BUTTON
# ============================================================

if uploaded_file is not None:

    if st.button(
        "🔍 Analyze SAR Image",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "AI is analyzing the SAR image..."
        ):

            probability = predict_oil_spill(
                image
            )


        if probability >= 0.5:

            result = (
                "OIL SPILL DETECTED"
            )

            confidence = probability

            st.error(
                f"🚨 {result}"
            )

        else:

            result = (
                "NO OIL SPILL DETECTED"
            )

            confidence = 1 - probability

            st.success(
                f"✅ {result}"
            )


        # ----------------------------------------------------
        # AI RESULTS
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "AI Confidence",
                f"{confidence * 100:.2f}%"
            )


        with col2:

            st.metric(
                "Oil Spill",
                f"{probability * 100:.2f}%"
            )


        with col3:

            st.metric(
                "No Oil Spill",
                f"{(1 - probability) * 100:.2f}%"
            )


        st.progress(
            probability
        )


        # Save result
        st.session_state[
            "ai_probability"
        ] = probability


st.divider()


# ============================================================
# 2. AIS + LAGRANGIAN ANALYSIS
# ============================================================

st.header(
    "2. AIS & Lagrangian Analysis"
)

st.write(
    """
    Click the button below to fetch **585 vessels** (500 Global Ocean + 85 Indian Ocean region vessels),
    perform a 12-hour backward Lagrangian hindcast, and correlate the spill origin with surrounding vessels.
    """
)


if st.button(
    "🚢 Run AIS + Drift Analysis",
    type="primary",
    use_container_width=True
):

    with st.spinner(
        "Fetching live AIS vessel telemetry across global & Indian Ocean regions (585 vessels)..."
    ):

        try:

            analysis = run_drift_analysis()

            st.session_state[
                "analysis"
            ] = analysis

            st.success(
                "AIS + Lagrangian analysis completed for 585 Global & Indian Ocean Vessels."
            )

        except Exception as e:

            st.error(
                f"Analysis failed: {e}"
            )


# ============================================================
# DISPLAY ANALYSIS
# ============================================================

if "analysis" in st.session_state:

    analysis = st.session_state[
        "analysis"
    ]


    # ========================================================
    # 3. SPILL COORDINATES
    # ========================================================

    st.header(
        "3. Oil Spill Drift Analysis"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "Detection Latitude",
            f"{analysis['detection_center_lat']:.5f}"
        )

        st.metric(
            "Detection Longitude",
            f"{analysis['detection_center_lon']:.5f}"
        )


    with col2:

        st.metric(
            "Estimated Origin Latitude",
            f"{analysis['origin_lat']:.5f}"
        )

        st.metric(
            "Estimated Origin Longitude",
            f"{analysis['origin_lon']:.5f}"
        )


    with col3:

        st.metric(
            "Total AIS Vessels",
            len(analysis["vessels"])
        )

        st.metric(
            "Hindcast Duration",
            "12 Hours"
        )


    # ========================================================
    # SELECTED SPILL LOCATION
    # ========================================================

    selected_vessel = analysis[
        "selected_vessel"
    ]


    st.info(
        f"""
        Spill location identified near:

        **{selected_vessel.get('ship_name', 'UNKNOWN')}**

        Latitude: **{selected_vessel['latitude']}**

        Longitude: **{selected_vessel['longitude']}**
        """
    )


    # ========================================================
    # 4. MAP
    # ========================================================

    st.header(
        "4. Global & Indian Ocean Spill & Vessel Map"
    )


    map_center = [

        analysis[
            "detection_center_lat"
        ],

        analysis[
            "detection_center_lon"
        ]

    ]


    m = folium.Map(

        location=map_center,

        zoom_start=7
    )


    # --------------------------------------------------------
    # SPILL DETECTION CENTER
    # --------------------------------------------------------

    folium.Marker(

        [

            analysis[
                "detection_center_lat"
            ],

            analysis[
                "detection_center_lon"
            ]

        ],

        popup="Oil Spill Detection Center",

        tooltip="Oil Spill Detection",

        icon=folium.Icon(
            color="red",
            icon="warning-sign"
        )

    ).add_to(m)


    # --------------------------------------------------------
    # ESTIMATED ORIGIN
    # --------------------------------------------------------

    folium.Marker(

        [

            analysis[
                "origin_lat"
            ],

            analysis[
                "origin_lon"
            ]

        ],

        popup="12-Hour Estimated Oil Origin",

        tooltip="Estimated Origin",

        icon=folium.Icon(
            color="orange",
            icon="info-sign"
        )

    ).add_to(m)


    # --------------------------------------------------------
    # MAP LEGEND & AIS VESSELS
    # --------------------------------------------------------

    st.markdown(
        """
        <div style="background-color: #111827; padding: 10px 16px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #374151; font-size: 14px;">
            <span style="margin-right: 20px; color: #f9fafb;"><b>Vessel Map Legend:</b></span>
            <span style="color: #3b82f6; font-weight: bold; margin-right: 18px;">🔵 Live AIS Stream Vessel</span>
            <span style="color: #ef4444; font-weight: bold; margin-right: 18px;">⚠️ Spill Detection Center</span>
            <span style="color: #f59e0b; font-weight: bold;">ℹ️ Estimated Spill Origin</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    for vessel in analysis[
        "vessels"
    ]:

        try:

            vessel_lat = float(
                vessel["latitude"]
            )

            vessel_lon = float(
                vessel["longitude"]
            )


            vessel_name = vessel.get(
                "ship_name",
                "UNKNOWN"
            )


            popup_text = (

                f"<b>{vessel_name}</b><br>"

                f"<b>Data Source:</b> Live AIS Stream<br>"

                f"MMSI: "
                f"{vessel.get('mmsi', 'N/A')}<br>"

                f"Speed: "
                f"{vessel.get('speed_knots', 'N/A')} knots<br>"

                f"Course: "
                f"{vessel.get('course_degrees', 'N/A')}°<br>"

                f"Heading: "
                f"{vessel.get('heading_degrees', 'N/A')}°<br>"

                f"Status: "
                f"{vessel.get('status', 'Unknown')}"
            )


            folium.CircleMarker(

                location=[
                    vessel_lat,
                    vessel_lon
                ],

                radius=5,

                color="#2563eb",

                fill_color="#3b82f6",

                fill_opacity=0.85,

                popup=folium.Popup(
                    popup_text,
                    max_width=320
                ),

                tooltip=vessel_name,

                fill=True

            ).add_to(m)


        except (
            ValueError,
            TypeError,
            KeyError
        ):

            continue


    # --------------------------------------------------------
    # DISPLAY MAP
    # --------------------------------------------------------

    st_folium(

        m,

        width=None,

        height=600
    )


    # ========================================================
    # 5. TOP SUSPECT VESSELS
    # ========================================================

    st.header(
        "5. Top Suspect Vessels"
    )


    suspects = analysis[
        "suspects"
    ]


    if suspects:

        rows = []


        for rank, vessel in enumerate(
            suspects,
            1
        ):

            rows.append({

                "Rank":
                    rank,

                "Ship Name":
                    vessel.get(
                        "ship_name",
                        "UNKNOWN"
                    ),

                "MMSI":
                    vessel.get(
                        "mmsi",
                        "UNKNOWN"
                    ),

                "Latitude":
                    vessel.get(
                        "latitude"
                    ),

                "Longitude":
                    vessel.get(
                        "longitude"
                    ),

                "Speed (knots)":
                    vessel.get(
                        "speed_knots"
                    ),

                "Course":
                    vessel.get(
                        "course_degrees"
                    ),

                "Heading":
                    vessel.get(
                        "heading_degrees"
                    ),

                "Status":
                    vessel.get(
                        "status"
                    ),

                "Closest Distance (km)":
                    vessel.get(
                        "closest_distance_km"
                    ),

                "Correlation Score":
                    vessel.get(
                        "match_percentage"
                    )

            })


        df = pd.DataFrame(
            rows
        )


        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True
        )


        # ====================================================
        # TOP SUSPECT
        # ====================================================

        st.subheader(
            "Highest-Ranked Suspect"
        )


        top = suspects[0]


        c1, c2, c3, c4 = st.columns(4)


        with c1:

            st.metric(
                "Vessel",
                top.get(
                    "ship_name",
                    "UNKNOWN"
                )
            )


        with c2:

            st.metric(
                "Correlation Score",
                f"{top.get('match_percentage', 0)}%"
            )


        with c3:

            st.metric(
                "Distance",
                f"{top.get('closest_distance_km', 0)} km"
            )


        with c4:

            st.metric(
                "Speed",
                f"{top.get('speed_knots', 0)} kn"
            )


    else:

        st.warning(
            "No suspect vessels found."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Prototype: AI SAR Detection + "
    "Worldwide Live AIS + Synthetic Lagrangian Hindcast"
)