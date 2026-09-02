# ============================================================
# colab_mlr.py
# Load and use the MLR model trained in Google Colab
# ============================================================

import os
import pickle
import numpy as np


# ============================================================
# PROJECT BASE DIRECTORY
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


# ============================================================
# MODEL PATHS
# ============================================================

MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml_models",
    "colab_mlr_model.pkl"
)

MODEL_INFO_PATH = os.path.join(
    BASE_DIR,
    "ml_models",
    "colab_mlr_model_info.pkl"
)

TFIDF_PATH = os.path.join(
    BASE_DIR,
    "ml_models",
    "colab_mlr_tfidf_vectorizer.pkl"
)


# ============================================================
# LOAD MLR MODEL
# ============================================================

with open(
    MODEL_PATH,
    "rb"
) as f:

    model_data = pickle.load(f)


# ============================================================
# EXTRACT MODEL
# ============================================================

model = model_data["model"]

features = model_data["features"]


# ============================================================
# LOAD MODEL INFORMATION
# ============================================================

with open(
    MODEL_INFO_PATH,
    "rb"
) as f:

    model_info = pickle.load(f)


# ============================================================
# LOAD TF-IDF VECTORIZER
# ============================================================

with open(
    TFIDF_PATH,
    "rb"
) as f:

    tfidf_vectorizer = pickle.load(f)


# ============================================================
# DISPLAY MODEL INFORMATION
# ============================================================

print(
    "Colab MLR model loaded successfully."
)

print(
    "Features:",
    features
)

print(
    "Target:",
    model_info.get(
        "target"
    )
)


# ============================================================
# CONTENT SCORE
# ============================================================

def calculate_content_score(text):
    """
    Convert video text into TF-IDF representation
    and calculate a content score.

    IMPORTANT:
    This function assumes the Colab model's content_score
    was derived from the TF-IDF representation.
    """

    if not text:

        return 0.0

    text = str(text)

    tfidf_matrix = (
        tfidf_vectorizer.transform(
            [text]
        )
    )

    # Sum of TF-IDF values
    content_score = (
        tfidf_matrix.sum()
    )

    return float(
        content_score
    )


# ============================================================
# MLR PREDICTION
# ============================================================

def predict_video_engagement(
    log_views,
    category_id,
    video_age_days,
    content_score,
    log_channel_avg_views
):
    """
    Predict video engagement using the
    MLR model trained in Google Colab.
    """

    X = np.array([

        [
            log_views,
            category_id,
            video_age_days,
            content_score,
            log_channel_avg_views
        ]

    ])

    prediction = model.predict(
        X
    )

    return float(
        prediction[0]
    )