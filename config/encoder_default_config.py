VERBOSE = 1
PATIENCE = 30
EPOCHS = 30
BATCH_SIZE = 256
PREFETCH = 8

IMAGE_SHAPE = [224, 224, 3]
FILTER_SIZE = 23

PROJECTOR_DIMENSIONALITY = 1024
LEARNING_RATE_BASE = 1e-4

PREPROCESSING_CONFIG = {
    'horizontal_flip': True,
    'vertical_flip': True,
    'color_jittering': 0.8,
    'color_dropping_probability': 0.2,
    'brightness_adjustment_max_intensity': 0.4,
    'contrast_adjustment_max_intensity': 0.4,
    'color_adjustment_max_intensity': 0.2,
    'hue_adjustment_max_intensity': 0.1,
    'gaussian_blurring_probability': [1, 0.1],
    'solarization_probability': [0, 0.2]
}

MODEL_WEIGHTS = None
ROOT_SAVE_DIR = 'trained_models/encoders'

DATASET_CONFIG = {
    'split_file_path': 'tissue_classification/fold_test.csv',
    'dataset_dir': 'tissue_classification/tissue_classification'
}

RANDOM_SEED = 42