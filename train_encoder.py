from silence_tensorflow import silence_tensorflow
silence_tensorflow()

from utils import image_augmentation
from utils.train import lr_scheduler
from utils.models import resnet20
from utils.models.barlow_twins import BarlowTwins
from utils.datasets import get_dataset_df
import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping, Callback
import pickle
import os


# ==================================================================================================================== #
# Configuration
# ==================================================================================================================== #
# region

VERBOSE = 1
BATCH_SIZE = 64
PATIENCE = 30
EPOCHS = 100
IMAGE_SHAPE = [112, 112, 3]
PROJECTOR_DIMENSIONALITY = 2048

PREPROCESSING_CONFIG = {
    'color_jittering': 0.8,
    'color_dropping_probability': 0.2,
    'brightness_adjustment_max_intensity': 0.4,
    'contrast_adjustment_max_intensity': 0.4,
    'color_adjustment_max_intensity': 0.2,
    'hue_adjustment_max_intensity': 0.1,
    'gaussian_blurring_probability': [1.0, 0.1],
    'solarization_probability': [0, 0.2]
}
RANDOM_SEED = 42

MODEL_WEIGHTS = None  # 'trained_models/encoder_2048.h5'
SAVE_DIR = ''  # 'trained_models'

DATASET_CONFIG = {
    'split': 'tissue_classification/fold_test.csv',
    'train_split': 1,
    'validation_split': 0,
    'dataset_dir': 'tissue_classification/tissue_classification',
    'groups': {},
    'major_groups': []
}
# endregion


# ==================================================================================================================== #
# Load data generators
# P.S. Current implementation is a little hacky
# ==================================================================================================================== #
# region

# Only using training set (and no validation set)
df = get_dataset_df(DATASET_CONFIG, RANDOM_SEED)

datagen_a = image_augmentation.get_generator(
    PREPROCESSING_CONFIG, view=0
).flow_from_dataframe(
    df[df['split'] == 'train'],
    seed=RANDOM_SEED,
    target_size=IMAGE_SHAPE[:2], batch_size=BATCH_SIZE
)

datagen_b = image_augmentation.get_generator(
    PREPROCESSING_CONFIG, view=1
).flow_from_dataframe(
    df[df['split'] == 'train'],
    seed=RANDOM_SEED,
    target_size=IMAGE_SHAPE[:2], batch_size=BATCH_SIZE
)


def create_dataset(datagen):
    def generator():
        while True:
            # Retrieve the images
            yield datagen.next()[0]
    return tf.data.Dataset.from_generator(generator, output_types='float32')


dataset = tf.data.Dataset.zip((
    create_dataset(datagen_a),
    create_dataset(datagen_b)
))

STEPS_PER_EPOCH = len(datagen_a)
TOTAL_STEPS = STEPS_PER_EPOCH * EPOCHS
# endregion


# ==================================================================================================================== #
# Load model
# ==================================================================================================================== #
# region

strategy = tf.distribute.MirroredStrategy()
print('Number of devices:', strategy.num_replicas_in_sync)

with strategy.scope():
    # Make sure later that this is the correct model
    resnet_enc = resnet20.get_network(
        hidden_dim=PROJECTOR_DIMENSIONALITY,
        use_pred=False,
        return_before_head=False,
        input_shape=IMAGE_SHAPE
    )
    if MODEL_WEIGHTS:
        resnet_enc.load_weights(MODEL_WEIGHTS)
        if VERBOSE:
            print('Using (pretrained) model weights')

    # Load optimizer
    WARMUP_EPOCHS = int(EPOCHS * 0.1)
    WARMUP_STEPS = int(WARMUP_EPOCHS * STEPS_PER_EPOCH)

    lr_decay_fn = lr_scheduler.WarmUpCosine(
        learning_rate_base=1e-3,
        total_steps=EPOCHS * STEPS_PER_EPOCH,
        warmup_learning_rate=0.0,
        warmup_steps=WARMUP_STEPS
    )
    optimizer = tf.keras.optimizers.Adam(learning_rate=lr_decay_fn)


    # Get model
    resnet_enc.trainable = True
    barlow_twins = BarlowTwins(resnet_enc)
    barlow_twins.compile(optimizer=optimizer)
# endregion


# ==================================================================================================================== #
# Train model
# ==================================================================================================================== #
# region

# Saves the weights for the encoder only
class ModelCheckpoint(Callback):
    def __init__(self):
        super().__init__()
        self.save_dir = os.path.join(SAVE_DIR, f'encoder_{PROJECTOR_DIMENSIONALITY}.h5')
        self.min_loss = 1e5

    def on_epoch_end(self, epoch, logs=None):
        if logs['loss'] < self.min_loss:
            self.min_loss = logs['loss']
            print('\nSaving model, new lowest loss:', self.min_loss)
            resnet_enc.save_weights(self.save_dir)


# Might not be the best approach
es = EarlyStopping(monitor='loss', mode='min', verbose=1, patience=PATIENCE)
mc = ModelCheckpoint()

history = barlow_twins.fit(
    dataset,
    epochs=EPOCHS,
    steps_per_epoch=STEPS_PER_EPOCH,
    callbacks=[es, mc]
)

with open('trained_models/resnet_classifiers/1024/history.pickle', 'wb') as file:
    pickle.dump(history.history, file)
# endregion
