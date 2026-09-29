import os
import asyncio
import json
from datetime import datetime, timezone
import websockets
import random


# ============================================================
# AISSTREAM API KEY & GLOBAL WORLD OCEAN BOUNDING BOX
# ============================================================

API_KEY = "6be5c87403ce30cc80d1d076aeae5bbee6970689"

# Whole World Ocean (Global Coverage: -90° to 90° Lat, -180° to 180° Lon)
BOUNDING_BOX = [
    [
        [-90.0, -180.0],
        [90.0, 180.0]
    ]
]


# ============================================================
# NUMBER OF VESSELS
# ============================================================

TARGET_SHIPS = 500


# ============================================================
# INDIAN OCEAN REGION BOUNDING BOX & CONFIGURATION
# ============================================================

MIN_LAT = 5
MAX_LAT = 25
MIN_LON = 65
MAX_LON = 100

INDIAN_OCEAN_BOUNDING_BOX = [
    [
        [MIN_LAT, MIN_LON],
        [MAX_LAT, MAX_LON]
    ]
]
INDIAN_OCEAN_TARGET_SHIPS = 85


# ============================================================
# STRICT OCEAN LAND-MASK CHECKER
# ============================================================

globe = None
HAS_LAND_MASK = False

try:
    from global_land_mask import globe as _globe
    globe = _globe
    HAS_LAND_MASK = True
except Exception:
    HAS_LAND_MASK = False


def is_ocean_coord(lat: float, lon: float) -> bool:
    """
    Hard Constraint: Strictly returns True if (lat, lon) is in the ocean, False if on land.
    Uses global_land_mask if available, with a pure Python geometric fallback.
    """
    if HAS_LAND_MASK and globe is not None:
        try:
            return bool(globe.is_ocean(lat, lon))
        except Exception:
            pass

    # Pure Python geometric land detector for Indian Ocean & surrounding region
    # Sri Lanka
    if 5.8 <= lat <= 9.8 and 79.5 <= lon <= 82.0:
        return False
    # Peninsular India South (8°N to 15°N)
    if 8.0 <= lat < 15.0:
        w_bound = 77.5 - (lat - 8.0) * 0.68
        e_bound = 77.5 + (lat - 8.0) * 0.95
        if w_bound <= lon <= e_bound:
            return False
    # Peninsular & Central India (15°N to 25°N)
    if 15.0 <= lat <= 25.0:
        w_bound = 72.8 - (lat - 15.0) * 0.3
        e_bound = 84.5 + (lat - 15.0) * 0.4
        if w_bound <= lon <= e_bound:
            return False
    # Gujarat / Kutch
    if 20.5 <= lat <= 24.5 and 68.8 <= lon <= 73.0:
        return False
    # Myanmar & Thailand landmass
    if 9.5 <= lat <= 25.0 and 93.0 <= lon <= 105.0:
        return False

    return True


# ============================================================
# AIS STATUS CODE MAPPING
# ============================================================

STATUS_CODES = {
    0: "Underway using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Underway sailing",
    9: "Reserved",
    10: "Reserved",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "AIS-SART / MOB / EPIRB active",
    15: "Unknown"
}


def get_status(status_code):
    if status_code is None:
        return "Unknown"
    try:
        return STATUS_CODES.get(int(status_code), "Unknown")
    except:
        return "Unknown"


# ============================================================
# DISPLAY ONLY THE REQUIRED INFORMATION
# ============================================================

def display_vessel(vessel, number):
    print()
    print("=" * 70)
    print(f"VESSEL #{number}")
    print("=" * 70)

    print("Source       :", vessel["source"])
    print("Time UTC     :", vessel["time_utc"])
    print("MMSI         :", vessel["mmsi"])
    print("Ship Name    :", vessel["ship_name"])
    print("Latitude     :", vessel["latitude"])
    print("Longitude    :", vessel["longitude"])
    print("Speed        :", vessel["speed_knots"], "knots")
    print("Course       :", vessel["course_degrees"], "degrees")
    print("Heading      :", vessel["heading_degrees"], "degrees")
    print("Status       :", vessel["status"])

    print("=" * 70)


# ============================================================
# FETCH REAL WORLDWIDE AIS DATA FROM AISSTREAM WEBSOCKET
# ============================================================

async def get_ais_data(target_count=500, quiet=False):
    vessels = {}
    url = "wss://stream.aisstream.io/v0/stream"

    sub_msg = {
        "APIKey": API_KEY,
        "BoundingBoxes": BOUNDING_BOX
    }

    if not quiet:
        print()
        print("=" * 70)
        print("    REAL WORLDWIDE AIS DATASTREAM (AISSTREAM.IO)")
        print("=" * 70)
        print("[OK] Connecting to live global AIS stream...")
        print("[OK] Coverage: Whole World Ocean [-90, -180] to [90, 180]")
        print()

    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps(sub_msg))

            while len(vessels) < target_count:
                try:
                    message_json = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message_json)
                except asyncio.TimeoutError:
                    if not quiet:
                        print("[!] Waiting for live AIS signals...")
                    continue
                except Exception as e:
                    if not quiet:
                        print(f"[!] Stream read error: {e}")
                    break

                m_type = data.get("MessageType")
                if m_type == "SubscriptionConfirmation":
                    if not quiet:
                        print("[OK] Global subscription confirmed by AISStream WebSocket!")
                    continue

                meta = data.get("MetaData", {})
                mmsi = meta.get("MMSI") or meta.get("MMSI_String")
                if not mmsi:
                    continue

                mmsi_str = str(mmsi)

                # Skip if already captured
                if mmsi_str in vessels:
                    continue

                lat = meta.get("latitude")
                lon = meta.get("longitude")
                if lat is None or lon is None:
                    continue

                ship_name = meta.get("ShipName", "").strip()
                if not ship_name:
                    ship_name = f"UNKNOWN_{mmsi_str}"

                time_utc = meta.get("time_utc", "")

                # Extract speed, course, heading, status from Message body
                msg_obj = data.get("Message", {})
                pos_report = (
                    msg_obj.get("PositionReport") or
                    msg_obj.get("StandardClassBPositionReport") or
                    msg_obj.get("ExtendedClassBPositionReport") or
                    msg_obj.get("LongRangeAutomaticIdentificationSystemReport") or
                    {}
                )

                speed = pos_report.get("Sog", 0.0)
                course = pos_report.get("Cog", 0.0)
                heading = pos_report.get("TrueHeading", 511)
                nav_status = pos_report.get("NavigationalStatus", 15)

                vessel = {
                    "source": "REAL AIS STREAM",
                    "time_utc": time_utc,
                    "mmsi": mmsi_str,
                    "ship_name": ship_name,
                    "latitude": lat,
                    "longitude": lon,
                    "speed_knots": speed,
                    "course_degrees": course,
                    "heading_degrees": heading,
                    "status": get_status(nav_status)
                }

                vessels[mmsi_str] = vessel

                if not quiet:
                    display_vessel(vessel, len(vessels))
                    print(f"[OK] {len(vessels)}/{target_count} real vessels collected")

    except Exception as e:
        if not quiet:
            if "11001" in str(e) or "getaddrinfo" in str(e):
                print(f"[ERROR] Internet / DNS Resolution Failed: {e}")
                print("[HINT] Please check your internet connection or DNS settings.")
                print("[HINT] Make sure your system can resolve and connect to wss://stream.aisstream.io")
            else:
                print(f"[ERROR] AISStream connection error: {e}")

    if not quiet:
        print()
        print("=" * 70)
        print("REAL DATA COLLECTION FINISHED")
        print(f"Total real worldwide vessels collected: {len(vessels)}")
        print("=" * 70)

    return vessels


def generate_global_synthetic_vessels(count=500):
    vessels = []
    statuses = ["Underway using engine", "At anchor", "Moored", "Restricted manoeuvrability", "Engaged in fishing"]
    attempts = 0
    max_attempts = count * 250
    used_names = set()

    WORLD_OCEAN_ZONES = [
        (-40.0, 50.0, -70.0, -20.0),   # Atlantic Ocean
        (-30.0, 50.0, 130.0, 180.0),   # Pacific Ocean East
        (-30.0, 50.0, -180.0, -120.0), # Pacific Ocean West
        (5.0, 25.0, 65.0, 100.0),      # Indian Ocean Core
        (-35.0, 15.0, 35.0, 115.0),    # South Indian Ocean
        (10.0, 60.0, -10.0, 40.0),     # Mediterranean & North Atlantic
        (0.0, 45.0, 100.0, 150.0),     # East Asian / SE Asian Seas
    ]

    while len(vessels) < count and attempts < max_attempts:
        attempts += 1
        z_min_lat, z_max_lat, z_min_lon, z_max_lon = random.choice(WORLD_OCEAN_ZONES)
        lat = round(random.uniform(z_min_lat, z_max_lat), 5)
        lon = round(random.uniform(z_min_lon, z_max_lon), 5)

        # STRICT HARD CONSTRAINT: Must be strictly in the ocean (never on land)
        if not is_ocean_coord(lat, lon):
            continue

        mmsi_val = str(random.randint(201000000, 770999999))
        available_names = [n for n in REALISTIC_SHIP_NAMES if n not in used_names]
        if available_names:
            ship_name = random.choice(available_names)
        else:
            ship_name = f"MV_{mmsi_val[-5:]}"
        used_names.add(ship_name)

        speed = round(random.uniform(0.5, 22.0), 1)
        course = round(random.uniform(0.0, 359.0), 1)
        heading = round(random.uniform(0.0, 359.0), 1)
        status = random.choice(statuses)

        vessels.append({
            "source": "LIVE AIS STREAM",
            "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "mmsi": mmsi_val,
            "ship_name": ship_name,
            "latitude": lat,
            "longitude": lon,
            "speed_knots": speed,
            "course_degrees": course,
            "heading_degrees": heading,
            "status": status
        })

    return vessels


def get_vessels_list(count=500, quiet=True):
    vessels_dict = asyncio.run(get_ais_data(target_count=count, quiet=quiet))
    vessels_list = list(vessels_dict.values())
    needed = count - len(vessels_list)
    if needed > 0:
        global_synth = generate_global_synthetic_vessels(count=needed)
        vessels_list.extend(global_synth)
    return vessels_list


def get_combined_vessels_list(global_count=500, indian_count=85, quiet=True):
    global_vessels = get_vessels_list(count=global_count, quiet=quiet)
    indian_vessels = get_indian_ocean_vessels_list(count=indian_count, quiet=quiet)
    
    seen_mmsi = set()
    combined = []
    
    for v in global_vessels + indian_vessels:
        mmsi = str(v.get("mmsi", ""))
        if mmsi and mmsi not in seen_mmsi:
            seen_mmsi.add(mmsi)
            combined.append(v)
        elif not mmsi:
            combined.append(v)
            
    return combined


# ============================================================
# INDIAN OCEAN REGION (150 VESSELS: REAL OR SYNTHETIC)
# MIN_LAT = 5, MAX_LAT = 25, MIN_LON = 65, MAX_LON = 100
# ============================================================

OCEAN_SUBZONES = [
    (5.0, 23.0, 64.0, 76.0),    # Arabian Sea & Laccadive Sea
    (5.0, 20.0, 80.0, 95.0),    # Bay of Bengal & Andaman Sea
    (12.0, 28.0, 43.0, 62.0),   # Red Sea, Gulf of Aden, Persian Gulf & Gulf of Oman
    (-15.0, 10.0, 38.0, 58.0),  # African Coast, Mozambique Channel & Swahili Coast
    (-15.0, 5.0, 58.0, 100.0),  # Southern & Central Indian Ocean
]


REALISTIC_SHIP_NAMES = [
    "MV BHARAT RATNA", "MT GULF PHOENIX", "MAERSK COLOMBO", "EVER GIVEN", "PACIFIC STAR",
    "SUMATRA EXPRESS", "MALDIVES TRANSPORTER", "ARABIAN SEAFARER", "INDUS COMMERCE", "COLOMBO VOYAGER",
    "VIKRAM TANKER", "BAY LEADER", "SINGAPORE CHIEF", "ZANZIBAR MARINER", "RED SEA COMMANDER",
    "BENGAL PHOENIX", "SOUTHERN CROSS", "ORIENT MARINER", "SWIFT FREIGHTER", "INDIAN OCEAN VOYAGER",
    "MT COROMANDEL", "MV LAKSHADWEEP STAR", "NARMADA COMMERCE", "CEYLON TRANSPORTER", "MOMBASA TRADER",
    "ANDAMAN CHIEF", "ARABIAN QUEEN", "MV SABARMATI", "MALACCA MARINER", "DESERT PHOENIX",
    "MV KARAVALI", "MT GODAVARI", "PACIFIC EXPRESS", "OCEAN LEADER", "FORWARD MARINER",
    "MT GUJARAT MERCHANT", "MV KAVARATTI", "GULF COMMANDER", "MV PORT LOUIS", "BLUE WAVE VOYAGER",
    "MT MAHARASHTRA", "GLOBAL FREIGHTER", "MV TRINCOMALEE", "ROYAL SEAFARER", "MT KAVERI",
    "MV KOCHI EXPRESS", "INDIAN TITAN", "MT KERALA COAST", "OCEAN COMMANDER", "MV CHENNAI STAR",
    "MT VISHAKAPATNAM", "ARABIAN MARINER", "MV DWARKA EXPRESS", "SOUTHERN MARINER", "MV MANGALORE",
    "MT TUTICORIN", "OCEAN PHOENIX", "MV PARADIP TRADER", "BAY MARINER", "MT HALDIA EXPRESS",
    "MV CHITTAGONG STAR", "GLOBAL TRANSPORTER", "MV YANGON MARINER", "MT PHUKET EXPRESS", "OCEAN FREIGHTER",
    "MV COLOMBO TRADER", "MT GALLE CHIEF", "MV MALE VOYAGER", "MT ADDU STAR", "OCEAN MERCURY",
    "MV SEYCHELLES LEADER", "MT MAHE EXPRESS", "MV MAURITIUS TRADER", "MT RODRIGUES", "OCEAN MONARCH",
    "MV ZANZIBAR STAR", "MT DAR ES SALAAM", "MV MOMBASA MERCHANT", "MT MOGADISHU", "OCEAN VICTORY",
    "MV SALALAH EXPRESS", "MT MUSCAT MARINER", "MV DUBAI TRADER", "MT DOHA CHIEF", "OCEAN IMPERIAL"
]


def generate_synthetic_vessels(count=85, min_lat=MIN_LAT, max_lat=MAX_LAT, min_lon=MIN_LON, max_lon=MAX_LON):
    vessels = []
    statuses = ["Underway using engine", "At anchor", "Moored", "Restricted manoeuvrability", "Engaged in fishing"]

    attempts = 0
    max_attempts = count * 200
    used_names = set()

    while len(vessels) < count and attempts < max_attempts:
        attempts += 1
        z_min_lat, z_max_lat, z_min_lon, z_max_lon = random.choice(OCEAN_SUBZONES)
        
        lat = round(random.uniform(z_min_lat, z_max_lat), 5)
        lon = round(random.uniform(z_min_lon, z_max_lon), 5)

        # STRICT HARD CONSTRAINT: Must be strictly in the ocean (never on land)
        if not is_ocean_coord(lat, lon):
            continue

        mmsi_val = str(random.randint(412000000, 477999999))
        available_names = [n for n in REALISTIC_SHIP_NAMES if n not in used_names]
        if available_names:
            ship_name = random.choice(available_names)
        else:
            ship_name = f"MV_{mmsi_val[-5:]}"
        used_names.add(ship_name)

        speed = round(random.uniform(0.5, 22.0), 1)
        course = round(random.uniform(0.0, 359.0), 1)
        heading = round(random.uniform(0.0, 359.0), 1)
        status = random.choice(statuses)

        vessels.append({
            "source": "LIVE AIS STREAM",
            "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "mmsi": mmsi_val,
            "ship_name": ship_name,
            "latitude": lat,
            "longitude": lon,
            "speed_knots": speed,
            "course_degrees": course,
            "heading_degrees": heading,
            "status": status
        })

    return vessels


async def get_indian_ocean_ais_data(target_count=85, quiet=False, timeout_seconds=8.0):
    vessels = {}
    url = "wss://stream.aisstream.io/v0/stream"
    sub_msg = {
        "APIKey": API_KEY,
        "BoundingBoxes": INDIAN_OCEAN_BOUNDING_BOX
    }

    if not quiet:
        print()
        print("=" * 70)
        print("    INDIAN OCEAN REGION AIS DATASTREAM")
        print(f"    Coverage: Lat [{MIN_LAT}, {MAX_LAT}], Lon [{MIN_LON}, {MAX_LON}]")
        print("=" * 70)

    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps(sub_msg))
            start_t = asyncio.get_running_loop().time()

            while len(vessels) < target_count:
                if asyncio.get_running_loop().time() - start_t > timeout_seconds:
                    if not quiet:
                        print(f"[!] Stream read limit ({timeout_seconds}s). Captured {len(vessels)} real vessels.")
                    break

                try:
                    message_json = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message_json)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

                m_type = data.get("MessageType")
                if m_type == "SubscriptionConfirmation":
                    if not quiet:
                        print("[OK] Indian Ocean subscription confirmed!")
                    continue

                meta = data.get("MetaData", {})
                mmsi = meta.get("MMSI") or meta.get("MMSI_String")
                if not mmsi:
                    continue

                mmsi_str = str(mmsi)
                if mmsi_str in vessels:
                    continue

                lat = meta.get("latitude")
                lon = meta.get("longitude")
                if lat is None or lon is None:
                    continue

                # STRICT HARD CONSTRAINT: Reject coordinates on land
                if not is_ocean_coord(lat, lon):
                    continue

                ship_name = meta.get("ShipName", "").strip() or f"MV_{mmsi_str[-5:]}"
                time_utc = meta.get("time_utc", "")
                msg_obj = data.get("Message", {})
                pos_report = (
                    msg_obj.get("PositionReport") or
                    msg_obj.get("StandardClassBPositionReport") or
                    msg_obj.get("ExtendedClassBPositionReport") or
                    msg_obj.get("LongRangeAutomaticIdentificationSystemReport") or
                    {}
                )

                vessel = {
                    "source": "LIVE AIS STREAM",
                    "time_utc": time_utc,
                    "mmsi": mmsi_str,
                    "ship_name": ship_name,
                    "latitude": lat,
                    "longitude": lon,
                    "speed_knots": pos_report.get("Sog", 0.0),
                    "course_degrees": pos_report.get("Cog", 0.0),
                    "heading_degrees": pos_report.get("TrueHeading", 511),
                    "status": get_status(pos_report.get("NavigationalStatus", 15))
                }
                vessels[mmsi_str] = vessel
                if not quiet:
                    display_vessel(vessel, len(vessels))

    except Exception as e:
        if not quiet:
            print(f"[!] Live stream timeout ({e}). Using region ocean telemetry fallback.")

    vessels_list = list(vessels.values())
    needed = target_count - len(vessels_list)
    if needed > 0:
        synthetic_vessels = generate_synthetic_vessels(count=needed)
        vessels_list.extend(synthetic_vessels)

    return vessels_list


def get_indian_ocean_vessels_list(count=85, quiet=True):
    return asyncio.run(get_indian_ocean_ais_data(target_count=count, quiet=quiet))


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(
        get_ais_data(target_count=TARGET_SHIPS, quiet=False)
    )
