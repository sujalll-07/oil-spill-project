import asyncio
from ais_real_test import (
    API_KEY,
    BOUNDING_BOX,
    TARGET_SHIPS,
    STATUS_CODES,
    get_status,
    display_vessel,
    get_ais_data,
    get_vessels_list
)

if __name__ == "__main__":
    asyncio.run(
        get_ais_data(target_count=TARGET_SHIPS, quiet=False)
    )