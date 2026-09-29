import os
import sys
import tensorflow as tf


# ============================================================
# SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH = 224

MODEL_PATH = "oil_spill_classifier.keras"


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

print("Loading trained model...")

model = tf.keras.models.load_model(
    MODEL_PATH
)

print("Model loaded successfully!\n")


# ============================================================
# PREDICT ONE IMAGE
# ============================================================

def predict_image(image_path):

    if not os.path.exists(image_path):

        print("Image not found:", image_path)

        return


    # Read image
    image = tf.io.read_file(
        image_path
    )

    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )


    # Resize
    image = tf.image.resize(
        image,
        [IMG_HEIGHT, IMG_WIDTH]
    )


    # Convert to float
    image = tf.cast(
        image,
        tf.float32
    )


    # IMPORTANT:
    # Same preprocessing used during training
    image = tf.keras.applications.mobilenet_v2.preprocess_input(
        image
    )


    # Add batch dimension
    image = tf.expand_dims(
        image,
        axis=0
    )


    # Prediction
    probability = model.predict(
        image,
        verbose=0
    )[0][0]


    # ========================================================
    # RESULT
    # ========================================================

    if probability >= 0.5:

        prediction = "OIL SPILL DETECTED"

    else:

        prediction = "NO OIL SPILL DETECTED"


    print("----------------------------------------")

    print(
        "Image:",
        os.path.basename(image_path)
    )

    print(
        "Prediction:",
        prediction
    )

    print(
        f"Oil Spill Probability: "
        f"{probability * 100:.2f}%"
    )

    print(
        f"No Oil Spill Probability: "
        f"{(1 - probability) * 100:.2f}%"
    )

    print("----------------------------------------\n")


# ============================================================
# MAIN
# ============================================================

if len(sys.argv) < 2:

    print(
        "Usage:"
    )

    print(
        "python predict.py sample_images/sample1.png"
    )

    sys.exit()


image_path = sys.argv[1]

predict_image(image_path)