# ============================================================
# mlr_recommender.py
# Real-time Multiple Linear Regression Recommendation Inference
# ============================================================

import os
import pickle
import numpy as np
import pandas as pd

from post.models import Post, WatchHistory
from post.mlr_features import (
    FEATURE_NAMES,
    fit_or_load_tfidf,
    build_features_for_user
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
MODEL_PATH = os.path.join(MODEL_DIR, "mlr_model.pkl")
TFIDF_PATH = os.path.join(MODEL_DIR, "mlr_tfidf_vectorizer.pkl")


def load_mlr_artifacts():
    """
    Load the trained MLR model and TF-IDF vectorizer.
    If missing, trigger training automatically.
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(TFIDF_PATH):
        try:
            from post.train_mlr import train
            train()
        except Exception as e:
            print(f"Auto-training recommender failed: {e}")

    model = None
    vectorizer = None

    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                model_data = pickle.load(f)
                model = model_data.get("model")
        except Exception as e:
            print(f"Error loading MLR model: {e}")

    if os.path.exists(TFIDF_PATH):
        try:
            with open(TFIDF_PATH, "rb") as f:
                vectorizer = pickle.load(f)
        except Exception as e:
            print(f"Error loading TFIDF vectorizer: {e}")

    return model, vectorizer


def recommend_posts_for_user(user, top_n=20, return_all=True, only_following=False):
    """
    Generate personalized recommendations for a user:
    1. Title + Description -> TF-IDF -> content_score
    2. User Actions -> likes, comments, watch_duration, completed, following_author, collaborative_score
    3. Combined MLR Features -> MLR Model -> Predicted Interest
    4. Watch Progression: Unwatched recommendations appear first (from next unwatched video onwards).
    5. When All Videos Are Watched: Automatically mixes / remixes the feed on every refresh.
    6. If only_following=True: Restricts candidates strictly to followed creators and ranks them with MLR.
    """
    if only_following and user and user.is_authenticated:
        from accounts.models import Follow
        following_ids = set(
            Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        )
        posts = list(Post.objects.filter(author_id__in=following_ids).select_related("author"))
    else:
        posts = list(Post.objects.select_related("author").all())

    if not posts:
        return []

    model, vectorizer = load_mlr_artifacts()

    # If vectorizer is not ready, fit on current posts
    if vectorizer is None:
        vectorizer = fit_or_load_tfidf(posts)

    # 1. Build MLR Features for candidate posts
    features_df = build_features_for_user(user, posts, vectorizer=vectorizer)

    # 2. Predict Interest using MLR model
    if model is not None and hasattr(model, "predict"):
        try:
            X = features_df[FEATURE_NAMES].fillna(0.0)
            predicted_scores = model.predict(X)
        except Exception as e:
            print(f"Prediction failed with model: {e}, falling back to weighted heuristic")
            predicted_scores = None
    else:
        predicted_scores = None

    # Fallback to weighted sum if model is not available
    if predicted_scores is None:
        predicted_scores = (
            features_df["content_score"] * 3.0 +
            features_df["post_likes"] * 1.0 +
            features_df["post_comments"] * 1.5 +
            features_df["post_views"] * 0.5 +
            features_df["user_liked"] * 2.0 +
            features_df["user_commented"] * 2.5 +
            features_df["completed"] * 4.0 +
            features_df["following_author"] * 2.0 +
            features_df["collaborative_score"] * 1.0
        ).values

    # 3. Partition into Unwatched (Fresh) and Watched
    watched_ids = set()
    if user and user.is_authenticated:
        watched_ids = set(
            WatchHistory.objects.filter(user=user).values_list("post_id", flat=True)
        )

    unwatched_results = []
    watched_results = []

    for post, score in zip(posts, predicted_scores):
        if post.id in watched_ids:
            watched_results.append((post, float(score)))
        else:
            unwatched_results.append((post, float(score)))

    # Sort each partition descending by Predicted Interest score
    unwatched_results.sort(key=lambda x: x[1], reverse=True)
    watched_results.sort(key=lambda x: x[1], reverse=True)

    # 4. Construct Final Feed:
    if unwatched_results:
        # Still have unwatched videos: unwatched first (starts from next unwatched), then watched at end
        full_feed = unwatched_results + watched_results
    else:
        # ALL VIDEOS WATCHED: Mix/remix the feed dynamically on each refresh!
        # Combines user's predicted interest scores with dynamic exploration jitter
        rng = np.random.RandomState()
        jitter = rng.normal(0.0, 0.45, size=len(watched_results))

        mixed_feed = []
        for (post, score), j in zip(watched_results, jitter):
            mixed_score = float(score) + float(j)
            mixed_feed.append((post, mixed_score))

        mixed_feed.sort(key=lambda x: x[1], reverse=True)
        full_feed = mixed_feed

    if not return_all:
        return full_feed[:top_n]

    return full_feed


def recommend_following_posts_for_user(user, top_n=20, return_all=True):
    """
    Generate personalized recommendations strictly for videos from creators the user follows,
    ranked using the Multiple Linear Regression (MLR) algorithm.
    """
    return recommend_posts_for_user(
        user=user,
        top_n=top_n,
        return_all=return_all,
        only_following=True
    )