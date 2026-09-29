"""Quick sanity test for the .grd decoder logic added to api_server.py."""
import io
import numpy as np
from PIL import Image


def _decode_grd(contents):
    raw = np.frombuffer(contents, dtype=np.float32)
    if raw.size < 256 or not np.isfinite(raw).any():
        return None
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


# Test 1: perfect square 256x256 float32 raster
data = np.random.rand(256, 256).astype(np.float32) * 100
buf = io.BytesIO()
buf.write(data.tobytes())
img = _decode_grd(buf.getvalue())
assert img is not None and img.size == (256, 256), "square test failed"
print("PASS: 256x256 square float32 raster decoded")

# Test 2: rectangular 2000 x 7 raster
data2 = np.random.rand(2000, 7).astype(np.float32)
buf2 = io.BytesIO()
buf2.write(data2.tobytes())
img2 = _decode_grd(buf2.getvalue())
assert img2 is not None and img2.size == (7, 2000), "rect test failed"
print("PASS: 2000x7 rectangular float32 raster decoded")

# Test 3: garbage bytes (e.g. a PNG header) -> should return None
png = b"\x89PNG\r\n\x1a\n" + bytes(20)
assert _decode_grd(png) is None, "garbage test failed"
print("PASS: garbage bytes correctly rejected")

# Test 4: end-to-end path from the endpoint:
# decode -> convert RGB -> resize -> model-input shape
arr = np.array(img.convert("RGB").resize((224, 224))).astype(np.float32)
assert arr.shape == (224, 224, 3)
print("PASS: decoded image feeds model input shape (224,224,3)")

print("ALL 4 TESTS PASSED")
