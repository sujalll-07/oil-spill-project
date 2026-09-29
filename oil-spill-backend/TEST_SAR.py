import os
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.callbacks import (
    ModelCheckpoint,
    EarlyStopping,
    ReduceLROnPlateau
)
from sklearn.model_selection import train_test_split

# ============================================================
# SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH = 224

# Points directly to your 'data' folder
DATASET_DIR = r"C:\Tevin Projects\Code Projects\SIH\data"

# Saves the trained model directly inside your main SIH folder
MODEL_PATH = r"C:\Tevin Projects\Code Projects\SIH\oil_spill_classifier.keras"

BATCH_SIZE = 16
EPOCHS = 30


# ============================================================
# GET IMAGE FILES AND LABELS (Folder-based approach)
# ============================================================

image_files = []
labels = []

# Paths to your subfolders
class_0_dir = os.path.join(DATASET_DIR, "Class_0")
class_1_dir = os.path.join(DATASET_DIR, "Class_1")

# Load Class 0 (No Oil Spill)
if os.path.exists(class_0_dir):
    for file_name in os.listdir(class_0_dir):
        if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
            image_files.append(os.path.join(class_0_dir, file_name))
            labels.append(0)

# Load Class 1 (Oil Spill)
if os.path.exists(class_1_dir):
    for file_name in os.listdir(class_1_dir):
        if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
            image_files.append(os.path.join(class_1_dir, file_name))
            labels.append(1)

image_files = np.array(image_files)
labels = np.array(labels)

print("Total images found:", len(image_files))
print("No oil spill (Class 0):", np.sum(labels == 0))
print("Oil spill (Class 1):", np.sum(labels == 1))

if len(image_files) == 0:
    raise ValueError(
        f"0 images found! Check if your folders are named 'Class_0' and 'Class_1' inside: {DATASET_DIR}"
    )


# ============================================================
# TRAIN / VALIDATION / TEST SPLIT
# ============================================================

X_train, X_temp, y_train, y_temp = train_test_split(
    image_files,
    labels,
    test_size=0.20,
    random_state=42,
    stratify=labels
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp,
    y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp
)

print("\nDataset split:")
print("Training   :", len(X_train))
print("Validation :", len(X_val))
print("Testing    :", len(X_test))


# ============================================================
# DATASET LOADER
# ============================================================

def load_image(file_path, label):
    image = tf.io.read_file(file_path)
    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )
    image = tf.image.resize(
        image,
        [IMG_HEIGHT, IMG_WIDTH]
    )
    image = tf.cast(
        image,
        tf.float32
    )
    # MobileNetV2 preprocessing
    image = tf.keras.applications.mobilenet_v2.preprocess_input(
        image
    )
    return image, label


# ============================================================
# CREATE TF DATASETS
# ============================================================

train_dataset = tf.data.Dataset.from_tensor_slices((X_train, y_train))
train_dataset = train_dataset.map(load_image, num_parallel_calls=tf.data.AUTOTUNE)
train_dataset = train_dataset.shuffle(len(X_train))
train_dataset = train_dataset.batch(BATCH_SIZE)
train_dataset = train_dataset.prefetch(tf.data.AUTOTUNE)

val_dataset = tf.data.Dataset.from_tensor_slices((X_val, y_val))
val_dataset = val_dataset.map(load_image, num_parallel_calls=tf.data.AUTOTUNE)
val_dataset = val_dataset.batch(BATCH_SIZE)
val_dataset = val_dataset.prefetch(tf.data.AUTOTUNE)

test_dataset = tf.data.Dataset.from_tensor_slices((X_test, y_test))
test_dataset = test_dataset.map(load_image, num_parallel_calls=tf.data.AUTOTUNE)
test_dataset = test_dataset.batch(BATCH_SIZE)
test_dataset = test_dataset.prefetch(tf.data.AUTOTUNE)


# ============================================================
# DATA AUGMENTATION
# ============================================================

data_augmentation = tf.keras.Sequential([
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.05),
    layers.RandomZoom(0.10),
])


# ============================================================
# CREATE MODEL
# ============================================================

base_model = MobileNetV2(
    input_shape=(IMG_HEIGHT, IMG_WIDTH, 3),
    include_top=False,
    weights="imagenet"
)

# Initially freeze pretrained model
base_model.trainable = False

inputs = layers.Input(shape=(IMG_HEIGHT, IMG_WIDTH, 3))
x = data_augmentation(inputs)
x = base_model(x, training=False)
x = layers.GlobalAveragePooling2D()(x)
x = layers.Dropout(0.3)(x)
outputs = layers.Dense(1, activation="sigmoid")(x)

model = models.Model(inputs, outputs)


# ============================================================
# COMPILE
# ============================================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        tf.keras.metrics.AUC(name="auc")
    ]
)

model.summary()


# ============================================================
# CALLBACKS
# ============================================================

callbacks = [
    ModelCheckpoint(
        MODEL_PATH,
        monitor="val_auc",
        mode="max",
        save_best_only=True,
        verbose=1
    ),
    EarlyStopping(
        monitor="val_auc",
        mode="max",
        patience=7,
        restore_best_weights=True,
        verbose=1
    ),
    ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=3,
        min_lr=1e-7,
        verbose=1
    )
]


# ============================================================
# TRAIN MODEL
# ============================================================

print("\nStarting training...\n")

history = model.fit(
    train_dataset,
    validation_data=val_dataset,
    epochs=EPOCHS,
    callbacks=callbacks
)


# ============================================================
# FINE-TUNING
# ============================================================

print("\nStarting fine-tuning...\n")

base_model.trainable = True

# Keep most layers frozen
for layer in base_model.layers[:-30]:
    layer.trainable = False

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        tf.keras.metrics.AUC(name="auc")
    ]
)

model.fit(
    train_dataset,
    validation_data=val_dataset,
    epochs=15,
    callbacks=callbacks
)


# ============================================================
# FINAL TEST
# ============================================================

print("\nEvaluating on test data...\n")

test_results = model.evaluate(test_dataset, verbose=1)

print("\nTest results:")
print("Loss     :", test_results[0])
print("Accuracy :", test_results[1])
print("AUC      :", test_results[2])


# ============================================================
# SAVE MODEL
# ============================================================

model.save(MODEL_PATH)
print("\nModel saved as:", MODEL_PATH)