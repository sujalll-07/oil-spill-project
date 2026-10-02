# 🌊 Marine Sentinel: AI-Driven Oil Spill Intelligence & Vessel Attribution System

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React_19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Bundler-Vite_6-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS_v4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![PyTorch](https://img.shields.io/badge/ML-PyTorch_ResNet18-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![TensorFlow](https://img.shields.io/badge/ML-TensorFlow_MobileNetV2-FF6F00?style=flat-square&logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![Leaflet](https://img.shields.io/badge/GIS-Leaflet-199900?style=flat-square&logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)

An enterprise-grade, maritime intelligence and environmental monitoring platform designed to detect marine oil slicks from satellite **Synthetic Aperture Radar (SAR)** imagery, model their spatiotemporal dispersion via **2D Lagrangian ocean drift physics**, calculate **worldwide coastal landfall hazards**, and mathematically attribute liability to culprit ships using **multi-factor AIS forensic analysis**.

---

## 📌 Table of Contents

- [Overview & Core Philosophy](#-overview--core-philosophy)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
  - [1. SAR Satellite Detection Pipeline](#1-sar-satellite-detection-pipeline)
  - [2. Lagrangian 2D Drift & Hindcast Engine](#2-lagrangian-2d-drift--hindcast-engine)
  - [3. Dynamic Global Coastal Landfall Predictor](#3-dynamic-global-coastal-landfall-predictor)
  - [4. Multi-Factor Evidence-Based Vessel Attribution (v2.1)](#4-multi-factor-evidence-based-vessel-attribution-v21)
  - [5. Live AIS Telemetry & Ocean Land-Masking](#5-live-ais-telemetry--ocean-land-masking)
  - [6. Tactical Maritime GIS Operations Dashboard](#6-tactical-maritime-gis-operations-dashboard)
- [Repository Structure](#-repository-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup (FastAPI & ML)](#backend-setup-fastapi--ml)
  - [Frontend Setup (React + Vite)](#frontend-setup-react--vite)
  - [Streamlit Operator Dashboard (Alternative)](#streamlit-operator-dashboard-alternative)
- [API Reference](#-api-reference)
- [The 8 Attribution Forensic Factors](#️-the-8-attribution-forensic-factors)
- [Data Sources & Acknowledgements](#-data-sources--acknowledgements)
- [License](#-license)

---

## 🧭 Overview & Core Philosophy

Marine oil spills from deliberate bilge discharging, tank washing, or maritime casualties cause irreversible marine ecocide. Identifying culprits at sea has historically been difficult due to rapid ocean dispersion and intentional AIS transponder silencing ("dark vessels").

**Marine Sentinel** operates on a **strict SAR-First Invariant**:

1. **SAR Ground Truth**: AIS telemetry alone never creates a spill incident. Detection strictly begins from high-resolution satellite radar observation.
2. **Dual Lagrangian Simulation**: Using verified detection coordinates, the physics engine runs a **12-hour reverse hindcast** (to establish discharge origin) and a **72-hour forward forecast** (to project drift trajectory and coastal collision).
3. **Forensic Attribution**: AIS trajectories are correlated against the back-projected origin cloud across 8 physical, navigational, and behavioural criteria to isolate the highest-probability suspect vessels.
4. **Global Dynamic Reach**: Shoreline impact analysis is completely global and not hardcoded to single territories, dynamically identifying at-risk coastlines, beaching mass percentages, and ETAs anywhere on Earth.

---

## 🏗 System Architecture

```text
               ┌────────────────────────────────────────────────────────┐
               │    Satellite SAR Imagery (Sentinel-1 / UAVSAR / TIFF)   │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │    FastAPI Neural Inference Engine (MobileNetV2/ResNet) │
               │   • Decodes float32 .grd / GeoTIFF / Standard Rasters  │
               │   • Extracts embedded GPS EXIF metadata                 │
               └───────────────────────────┬────────────────────────────┘
                                           │ Confirmed Spill Coordinates
                                           ▼
       ┌───────────────────────────────────┴───────────────────────────────────┐
       │                                                                       │
       ▼                                                                       ▼
┌──────────────────────────────┐                             ┌──────────────────────────────────┐
│  Lagrangian Drift Engine     │                             │  Global Coastline Engine         │
│  • RK4 Numerical Advection   │                             │  • High-res global_land_mask     │
│  • Current + Wind (3%)       │                             │  • Adaptive outward grid search  │
│  • Ekman Deflection (12°)    │                             │  • Nominatim Reverse Geocoding   │
│  • Turbulent Diffusion (1.0) │                             └─────────────────┬────────────────┘
└──────────────┬───────────────┘                                               │
               │                                                               │
               ├───────────────────────┬───────────────────────────────────────┘
               │                       │
               ▼                       ▼
┌──────────────────────────────┐ ┌──────────────────────────────────────────────────────────────┐
│  12h Hindcast Origin Cloud   │ │  72h Forward Drift & Landfall Threat Prediction              │
│  & 72h Forward Particles     │ │  • Coastal Country/Region Identification                     │
└──────────────┬───────────────┘ │  • ETA to Landfall, Impact Coordinates, % Beached Mass        │
               │                 └──────────────────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│  Multi-Factor Vessel Attribution Engine (v2.1)                                                │
│  • Ingests Live AIS Feed (AISStream.io WebSockets + Land Masking)                             │
│  • Evaluates 8 Forensic Weighted Evidence Vectors:                                            │
│    [F1] Spatial Proximity         [F2] Temporal Alignment     [F3] Track Intersection         │
│    [F4] AIS Silence / Dark Period [F5] Vessel Risk Profile     [F6] Manoeuvre / Speed Anomalies│
│    [F7] Hindcast Cloud Proximity  [F8] Radar Cross-Check                                      │
└──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                               │
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│  React 19 + Leaflet Operations GIS Dashboard                                                  │
│  • Dark tactical maritime UI with interactive polygon envelopes & drift vectors               │
│  • Offshore platform databases (Indian EEZ & Global IOR oil rigs)                             │
│  • Suspect vessel ranking cards with drill-down forensic factor modal                         │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Features

### 1. SAR Satellite Detection Pipeline

- **Multi-Format Processing**: Natively ingests raw Little-Endian float32 UAVSAR binary raster grids (`.grd`), GeoTIFFs (`.tif`/`.tiff`), and high-resolution optical/radar imagery (`.png`, `.jpg`).
- **Deep Learning Classification**:
  - **MobileNetV2** (TensorFlow/Keras): Fast, edge-optimized binary classification model trained to distinguish oil slicks from natural biogenic look-alikes, calm waters, and wind shadows.
  - **ResNet18** (PyTorch): Feature-rich deep convolutional backbone pipeline for high-precision satellite tile evaluation.
- **EXIF Geolocation Extraction**: Automatically inspects embedded EXIF GPS tags to auto-geolocate spill incidents without manual operator entry.

### 2. Lagrangian 2D Drift & Hindcast Engine

- **Runge-Kutta 4th Order (RK4)**: High-fidelity numerical integration modeling movement of 1,000+ stochastic particles.
- **Environmental Drift Physics**:
  - Surface current advection vector $(u_c, v_c)$.
  - 3% windage transfer efficiency factor.
  - 12° Ekman deflection angle accounting for planetary Coriolis rotation.
  - Random-walk turbulent horizontal diffusivity parameter ($1.0\ \text{m}^2/\text{s}$).
- **12-Hour Reverse Hindcast**: Calculates the back-projected origin cloud to identify the exact coordinates where the oil discharge originated.
- **72-Hour Forward Forecast**: Predicts slick spreading, dynamic area expansion in $\text{km}^2$, and outer boundary convex hulls.

### 3. Dynamic Global Coastal Landfall Predictor

- **Worldwide Shoreline Interception**: Powered by pixel-level `global_land_mask` validation; functions dynamically across the Arabian Sea, Bay of Bengal, Mediterranean, North Sea, Persian Gulf, or Pacific.
- **Adaptive Grid Search**: Evaluates land proximity starting from coarse $1.0^\circ$ resolution down to fine $0.05^\circ$ coastal bounds.
- **Automated Geocoding**: Integrates OpenStreetMap Nominatim reverse geocoding to identify coastal administrative regions and nations without hardcoded tables.
- **Impact Hazard Metrics**: Reports earliest impact ETA, median landfall timeline, total shoreline beached particle percentage, and threat classifications (`SAFE`, `LOW`, `MODERATE`, `HIGH`, `CRITICAL`).

### 4. Multi-Factor Evidence-Based Vessel Attribution (v2.1)

Mathematically computes attribution confidence across 8 distinct forensic factors:

- **Spatial Proximity (18%)**: Exponential decay distance between ship and spill site.
- **Temporal Compatibility (15%)**: Interpolated vessel location at estimated discharge timestamp.
- **Trajectory Intersection (15%)**: Historical AIS passage through back-projected spill zones.
- **AIS Reporting Gaps (14%)**: Flags intentional transponder dropouts or dark periods.
- **Vessel Risk Profile (8%)**: Weights crude tankers, chemical carriers, and bunkering vessels higher than bulkers or container vessels.
- **Behavioural Anomalies (15%)**: Identifies speed reductions, zig-zag loitering, or maneuvers indicative of tank purging.
- **Hindcast Proximity (10%)**: Spatial correlation with the backwards Lagrangian origin envelope.
- **SAR Radar Confirmation (5%)**: Correlates SAR hard-target radar reflections with AIS coordinates.

### 5. Live AIS Telemetry & Ocean Land-Masking

- **Real-Time Streaming**: Integrated with `aisstream.io` WebSockets to stream live commercial maritime traffic across global bounding boxes.
- **Strict Ocean Filtering**: Prevents false positive attributions by filtering out corrupted coordinates or ghost vessels transmitting from landmasses.

### 6. Tactical Maritime GIS Operations Dashboard

- **React 19 + Tailwind CSS v4 + Leaflet**: Clean dark-mode GIS workstation built for maritime patrol and coast guard command centers.
- **Interactive Map Layers**:
  - Live vessel markers with heading indicators, nav status badges, and speed logs.
  - Offshore drilling rigs database (covering ONGC Mumbai High, Bassein, Krishna-Godavari Basin, and broader Indian Ocean Region installations).
  - Slick polygons, 12h hindcast dispersion envelopes, and 72h forward drift vectors.
  - Dynamic ocean currents and wind direction overlays.
- **Suspect Inspection Modal**: Click on any suspect vessel to open a deep-dive forensic breakdown visualizing the individual score of every attribution factor.

---

## 📂 Repository Structure

```text
oil-spill-project/
├── .gitignore                        # Excludes .env, node_modules, __pycache__, dist
├── oil-spill-backend/
│   ├── api_server.py                 # Core FastAPI backend (v2 REST API)
│   ├── app.py                        # Alternative Streamlit operational dashboard
│   ├── ais_real_test.py              # Live AISStream WebSocket client & land filtering
│   ├── coastal_landfall_engine.py    # RK4 coastal impact & beaching predictor
│   ├── global_coastline_engine.py    # Global nearest-coastline & Nominatim geocoder
│   ├── lagrangian_drift.py           # Lagrangian drift equations & environmental fields
│   ├── lagrangian_engine.py          # Dual hindcast/forecast particle simulation
│   ├── model.py                      # PyTorch ResNet18 classifier training routine
│   ├── predict.py                    # Standalone CLI inference utility
│   ├── requirements.txt              # Backend Python dependencies
│   ├── sar_pipeline.py               # UAVSAR .grd binary & GeoTIFF decoder
│   ├── test_grd_decode.py            # Unit test for raw float32 radar decoding
│   ├── train_model.py                # MobileNetV2 TensorFlow training routine
│   ├── vessel_attribution_engine.py  # 8-factor multi-evidence attribution engine
│   ├── .env.example                  # Template for required environment variables
│   ├── oil_spill_classifier.keras    # Trained MobileNetV2 model weights
│   └── oil_spill_classifier.pth      # Trained ResNet18 model weights
│
└── oil-spill-frontend/
    ├── src/
    │   ├── components/
    │   │   └── map/
    │   │       ├── CoastalThreatPanel.jsx    # Landfall hazard & ETA summary HUD
    │   │       ├── DetectedSpillPanel.jsx    # Active spill metrics & area readout
    │   │       ├── DynamicCurrentsOverlay.jsx# Ocean current particle vectors
    │   │       ├── EvidenceFactorModal.jsx   # Deep-dive 8-factor forensic breakdown
    │   │       ├── LayerControlPanel.jsx     # Basemap & layer toggle panel
    │   │       ├── MapView.jsx               # Main interactive Leaflet map controller
    │   │       ├── NearbyVesselsPanel.jsx    # Ranked suspect vessel sidebar
    │   │       ├── OilSpillLayer.jsx         # Slick polygons & drift trajectory lines
    │   │       ├── PlatformMarker.jsx        # Offshore oil rig markers & details
    │   │       ├── VesselMarker.jsx          # AIS vessel markers & speed/status popups
    │   │       └── WindDirectionOverlay.jsx  # Atmospheric wind vector indicators
    │   ├── data/
    │   │   ├── mockOilSpillData.js           # Fallback testing fixtures
    │   │   ├── offshoreRigs.geojson          # Geographic features for oil platforms
    │   │   └── offshoreRigsData.js           # Verified Indian EEZ & IOR offshore rigs
    │   ├── services/
    │   │   └── api.js                        # Axios/fetch communication layer
    │   ├── App.jsx                           # Root layout
    │   ├── main.jsx                          # React DOM entry point
    │   └── index.css                         # Tailwind CSS v4 styling rules
    ├── package.json                          # Frontend dependencies & scripts
    ├── vite.config.js                        # Vite bundler configuration
    └── .env                                  # Environment variables (API base URL, not committed)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: Version `3.10` or higher
- **Node.js**: Version `18.0.0` or higher (`npm` included)
- **Git**
- **AISStream.io API key**: Free key from [aisstream.io](https://aisstream.io/)

---

### Backend Setup (FastAPI & ML)

1. **Navigate to the backend directory**:

```bash
   cd oil-spill-backend
```

2. **Create and activate a virtual environment**:

   - On Windows (PowerShell):

```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
```

   - On Linux / macOS:

```bash
     python3 -m venv venv
     source venv/bin/activate
```

3. **Install dependencies**:

```bash
   pip install -r requirements.txt
```

4. **Configure your AISStream API key**: Copy the example file and add your own key. The `.env` file is git-ignored and never committed.

```bash
   cp .env.example .env
```

   Then edit `.env`:

```env
   AISSTREAM_API_KEY=your_aisstream_key_here
```

5. **Launch the FastAPI Server**:

```bash
   python api_server.py
```

   *The server starts at `http://localhost:8000`. Interactive OpenAPI documentation will be accessible at `http://localhost:8000/docs`.*

---

### Frontend Setup (React + Vite)

1. **Open a new terminal and navigate to the frontend directory**:

```bash
   cd oil-spill-frontend
```

2. **Configure environment variables**: Create a `.env` file that points to your running FastAPI backend:

```env
   VITE_API_URL=http://localhost:8000
```

3. **Install Node packages**:

```bash
   npm install
```

4. **Start the development server**:

```bash
   npm run dev
```

   *The application will open at `http://localhost:5173`.*

---

### Streamlit Operator Dashboard (Alternative)

For lightweight fieldwork or rapid prototyping without the Node frontend, run the included Streamlit GIS app:

```bash
cd oil-spill-backend
streamlit run app.py
```

*The Streamlit web UI will launch automatically in your browser at `http://localhost:8501`.*

---

## 📡 API Reference

### Health Check

`GET /api/status`

Verifies server health and confirms whether neural models are initialized.

### 1. Analyze SAR Imagery

`POST /api/analyze-sar`

- **Body**: `multipart/form-data` containing `file` (`.grd`, `.tif`, `.png`, `.jpg`).
- **Description**: Evaluates image with the deep learning model. Extracts embedded GPS EXIF tags if present.
- **Response**:

```json
  {
    "status": "success",
    "result": "OIL SPILL DETECTED",
    "is_spill": true,
    "probability": 0.942,
    "confidence_pct": 94.2,
    "geolocation_available": true,
    "geolocation": { "lat": 18.921, "lon": 72.834, "source": "EXIF/GPS" }
  }
```

### 2. Execute Drift & Attribution from Spill Coordinates

`POST /api/run-analysis-from-spill`

- **Body** (`application/json`):

```json
  {
    "spill_lat": 18.921,
    "spill_lon": 72.834,
    "spill_time": "2026-09-29T12:00:00Z",
    "sensor_name": "Sentinel-1A SAR",
    "confidence_pct": 94.2
  }
```

- **Description**: Triggers 12h RK4 hindcast, 72h forward drift simulation, coastal threat analysis, live AIS queries, and the 8-factor attribution ranking.
- **Response**: Returns full incident metadata, spill polygons, candidate vessels, and ranked suspects with composite evidence matrices.

### 3. Live Vessel Traffic Layer

`GET /api/vessels?count=100`

- **Query Params**: `count` (integer, max 585).
- **Description**: Returns live ocean-validated AIS vessel locations without triggering any spill analysis.

---

## ⚖️ The 8 Attribution Forensic Factors

| **Factor ID** | **Forensic Name** | **Weight** | **Evaluation Method & Rationale** |
| ------------- | ----------------- | ---------- | --------------------------------- |
| **F1** | **Spatial Proximity** | **18%** | Measures spatial separation between vessel location and spill site using an exponential decay distance penalty function. |
| **F2** | **Temporal Compatibility** | **15%** | Dead-reckons vessel position at the exact time of slick discharge based on historical speed and course. |
| **F3** | **Trajectory Intersection** | **15%** | Evaluates whether the historical 12-hour AIS track intersects or closely skirts the back-projected spill corridor. |
| **F4** | **AIS Reporting Gap** | **14%** | Detects transponder silent intervals ("going dark") while in proximity to the spill zone, a frequent indicator of deliberate dumping. |
| **F5** | **Vessel Risk Profile** | **8%** | Assesses cargo hazard index: crude tankers, product carriers, chemical tankers, and bunkering vessels receive top risk weighting. |
| **F6** | **Behavioural Anomalies** | **15%** | Detects abnormal navigational patterns including drastic speed drops, sharp course deviations, or slow loitering typical of tank washing. |
| **F7** | **Hindcast Proximity** | **10%** | Calculates minimum distance between the ship's track and the Lagrangian reverse-drift origin particle cloud. |
| **F8** | **Radar Confirmation** | **5%** | Cross-validates satellite SAR hard-target radar echoes against broadcast AIS positions to verify vessel presence at image acquisition. |


---

## 🌐 Data Sources & Acknowledgements

- **Satellite SAR Imagery**: European Space Agency (ESA) Copernicus Sentinel-1 via CDSE & NASA Earthdata UAVSAR missions.
- **Live Maritime Telemetry**: Real-time AIS stream ingestion supported via [AISStream.io](https://aisstream.io/).
- **Land & Shoreline Masking**: High-precision planetary ocean-land boundaries provided by `global_land_mask`.
- **Geocoding & Cartography**: Coastline and territory reverse geocoding via OpenStreetMap Nominatim. Basemaps provided by CartoDB, OpenStreetMap, and ESRI World Imagery.
- **Offshore Infrastructure Data**: Verified navigational disclosures from ONGC, Directorate General of Hydrocarbons (DGH) India, and International Maritime Hydrographic Notices.

---

## 📄 License

This project is licensed under the **MIT License**. You are free to use, modify, and distribute this software for educational, research, and environmental protection initiatives.
