import os
import numpy as np
import tensorflow as tf

# Use tf.keras references directly to satisfy static type checkers (Pylance/Pyright)
layers = tf.keras.layers
models = tf.keras.models
MobileNetV2 = tf.keras.applications.MobileNetV2
ModelCheckpoint = tf.keras.callbacks.ModelCheckpoint
EarlyStopping = tf.keras.callbacks.EarlyStopping
ReduceLROnPlateau = tf.keras.callbacks.ReduceLROnPlateau

from sklearn.model_selection import train_test_split


# ============================================================
# SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH = 224

DATASET_DIR = "dataset"

MODEL_PATH = "oil_spill_classifier.keras"

BATCH_SIZE = 16
EPOCHS = 30


# ============================================================
# GET IMAGE FILES AND LABELS
# ============================================================

image_files = []
labels = []


# ---------------- CLASS 0: NO OIL SPILL ----------------

class_0_dir = os.path.join(
    DATASET_DIR,
    "class_0"
)

for file_name in os.listdir(class_0_dir):

    if file_name.lower().endswith(
        (".png", ".jpg", ".jpeg")
    ):

        image_files.append(
            os.path.join(
                class_0_dir,
                file_name
            )
        )

        labels.append(0)


# ---------------- CLASS 1: OIL SPILL ----------------

class_1_dir = os.path.join(
    DATASET_DIR,
    "class_1"
)

for file_name in os.listdir(class_1_dir):

    if file_name.lower().endswith(
        (".png", ".jpg", ".jpeg")
    ):

        image_files.append(
            os.path.join(
                class_1_dir,
                file_name
            )
        )

        labels.append(1)


image_files = np.array(image_files)
labels = np.array(labels)


print("Total images:", len(image_files))
print(
    "No oil spill (class 0):",
    np.sum(labels == 0)
)
print(
    "Oil spill (class 1):",
    np.sum(labels == 1)
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

print(
    "Training   :",
    len(X_train)
)

print(
    "Validation :",
    len(X_val)
)

print(
    "Testing    :",
    len(X_test)
)


# ============================================================
# DATASET LOADER
# ============================================================

def load_image(file_path, label):

    image = tf.io.read_file(
        file_path
    )

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

    image = tf.keras.applications.mobilenet_v2.preprocess_input(
        image
    )

    return image, label


# ============================================================
# CREATE TRAIN DATASET
# ============================================================

train_dataset = tf.data.Dataset.from_tensor_slices(
    (X_train, y_train)
)

train_dataset = train_dataset.map(
    load_image,
    num_parallel_calls=tf.data.AUTOTUNE
)

train_dataset = train_dataset.shuffle(
    len(X_train)
)

train_dataset = train_dataset.batch(
    BATCH_SIZE
)

train_dataset = train_dataset.prefetch(
    tf.data.AUTOTUNE
)


# ============================================================
# CREATE VALIDATION DATASET
# ============================================================

val_dataset = tf.data.Dataset.from_tensor_slices(
    (X_val, y_val)
)

val_dataset = val_dataset.map(
    load_image,
    num_parallel_calls=tf.data.AUTOTUNE
)

val_dataset = val_dataset.batch(
    BATCH_SIZE
)

val_dataset = val_dataset.prefetch(
    tf.data.AUTOTUNE
)


# ============================================================
# CREATE TEST DATASET
# ============================================================

test_dataset = tf.data.Dataset.from_tensor_slices(
    (X_test, y_test)
)

test_dataset = test_dataset.map(
    load_image,
    num_parallel_calls=tf.data.AUTOTUNE
)

test_dataset = test_dataset.batch(
    BATCH_SIZE
)

test_dataset = test_dataset.prefetch(
    tf.data.AUTOTUNE
)


# ============================================================
# DATA AUGMENTATION
# ============================================================

data_augmentation = tf.keras.Sequential([

    layers.RandomFlip(
        "horizontal"
    ),

    layers.RandomRotation(
        0.05
    ),

    layers.RandomZoom(
        0.10
    )

])


# ============================================================
# CREATE MOBILENETV2 MODEL
# ============================================================

base_model = MobileNetV2(

    input_shape=(
        IMG_HEIGHT,
        IMG_WIDTH,
        3
    ),

    include_top=False,

    weights="imagenet"
)


# Freeze pretrained layers initially

base_model.trainable = False


inputs = layers.Input(
    shape=(
        IMG_HEIGHT,
        IMG_WIDTH,
        3
    )
)


x = data_augmentation(
    inputs
)


x = base_model(
    x,
    training=False
)


x = layers.GlobalAveragePooling2D()(
    x
)


x = layers.Dropout(
    0.3
)(x)


outputs = layers.Dense(
    1,
    activation="sigmoid"
)(x)


model = models.Model(
    inputs,
    outputs
)


# ============================================================
# COMPILE MODEL
# ============================================================

model.compile(

    optimizer=tf.keras.optimizers.Adam(
        learning_rate=0.0001
    ),

    loss="binary_crossentropy",

    metrics=[

        "accuracy",

        tf.keras.metrics.AUC(
            name="auc"
        )

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

print(
    "\nStarting training...\n"
)


history = model.fit(

    train_dataset,

    validation_data=val_dataset,

    epochs=EPOCHS,

    callbacks=callbacks

)


# ============================================================
# FINE-TUNING
# ============================================================

print(
    "\nStarting fine-tuning...\n"
)


base_model.trainable = True


# Freeze most layers

for layer in base_model.layers[:-30]:

    layer.trainable = False


model.compile(

    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-5
    ),

    loss="binary_crossentropy",

    metrics=[

        "accuracy",

        tf.keras.metrics.AUC(
            name="auc"
        )

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

print(
    "\nEvaluating on test data...\n"
)


test_results = model.evaluate(

    test_dataset,

    verbose=1

)


print(
    "\nTest results:"
)


print(
    "Loss     :",
    test_results[0]
)


print(
    "Accuracy :",
    test_results[1]
)


print(
    "AUC      :",
    test_results[2]
)


# ============================================================
# SAVE MODEL
# ============================================================

model.save(
    MODEL_PATH
)


print(
    "\nModel saved as:",
    MODEL_PATH
)