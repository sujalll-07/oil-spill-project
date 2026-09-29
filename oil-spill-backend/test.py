from sar_pipeline import preprocess_sar_chip, run_model_inference

# 1. Path to your downloaded UAVSAR file
file_path = "NISARP_09065_19071_001_191001_L090HHHV_CX_129A_02.grd"

print("Preprocessing SAR raster file...")
tensor_input = preprocess_sar_chip(file_path)
print(f"Tensor generated successfully with shape: {tensor_input.shape}")

print("Running model inference...")
pred_class, confidence = run_model_inference(tensor_input)

print("\n--- Model Output Result ---")
print(f"Prediction Class: {'🚨 Oil Spill Detected' if pred_class == 1 else '✅ Clean Water'}")
print(f"Confidence Score: {confidence:.2f}%")