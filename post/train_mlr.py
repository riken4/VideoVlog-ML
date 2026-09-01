# ============================================================
# train_mlr.py
# Multiple Linear Regression Recommendation Model Training
# ============================================================

import os
import sys
import pickle
import django
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.metrics.pairwise import linear_kernel

# Set up Django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser, Follow
from post.models import Post, Like, Comment, WatchHistory
from post.mlr_features import (
    FEATURE_NAMES,
    clean_post_text,
    fit_or_load_tfidf,
    build_features_for_user,
    build_collaborative_scores,
    compute_user_content_scores
)

MODEL_DIR = os.path.join(BASE_DIR, "ml_models")
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, "mlr_model.pkl")
MODEL_INFO_PATH = os.path.join(MODEL_DIR, "mlr_model_info.pkl")
TFIDF_PATH = os.path.join(MODEL_DIR, "mlr_tfidf_vectorizer.pkl")


def build_training_dataset():
    """
    Build the full (User x Post) interaction dataset for MLR training.
    """
    users = list(CustomUser.objects.all())
    posts = list(Post.objects.select_related("author").all())

    if not users or not posts:
        raise ValueError("Database must contain users and posts to train recommendation model.")

    print(f"Building training dataset from {len(users)} users and {len(posts)} posts...")

    # 1. Fit TF-IDF Vectorizer on all posts
    vectorizer = fit_or_load_tfidf(posts, force_refit=True)

    # 2. Pre-fetch interaction lookups
    all_watches = {
        (w["user_id"], w["post_id"]): w
        for w in WatchHistory.objects.values("user_id", "post_id", "watch_duration", "completed")
    }
    all_likes = set(Like.objects.values_list("user_id", "post_id"))
    all_comments = set(Comment.objects.values_list("author_id", "post_id"))
    all_follows = set(Follow.objects.values_list("follower_id", "following_id"))

    # 3. Collaborative filtering lookup
    collab_lookup = build_collaborative_scores(users, posts)

    data = []
    for user in users:
        # Precompute content scores for this user across all posts
        content_scores = compute_user_content_scores(user, posts, vectorizer)
        user_collab = collab_lookup.get(user.id, {})

        for post in posts:
            key = (user.id, post.id)
            watch = all_watches.get(key)

            user_watched = 1.0 if watch else 0.0
            watch_dur = float(np.log1p(watch["watch_duration"])) if watch else 0.0
            completed = 1.0 if (watch and watch["completed"]) else 0.0

            user_liked = 1.0 if key in all_likes else 0.0
            user_commented = 1.0 if key in all_comments else 0.0
            following_author = 1.0 if (user.id, post.author_id) in all_follows else 0.0

            content_score = content_scores.get(post.id, 0.0)
            collab_score = float(user_collab.get(post.id, 0.0))

            post_likes = float(np.log1p(post.total_likes))
            post_comments = float(np.log1p(post.total_comments))
            # Total views for post
            post_views = float(np.log1p(
                WatchHistory.objects.filter(post_id=post.id).count()
            ))

            # Target: Interest Score representing real user engagement
            # Viewed (+1), Watch Duration (+min(dur/10, 5)), Liked (+3), Commented (+4), Completed (+5), Following creator (+2)
            raw_dur = float(watch["watch_duration"]) if watch else 0.0
            dur_bonus = min(raw_dur / 10.0, 5.0)

            interest_score = (
                user_watched * 1.0 +
                dur_bonus +
                user_liked * 3.0 +
                user_commented * 4.0 +
                completed * 5.0 +
                following_author * 2.0
            )

            data.append({
                "user_id": user.id,
                "post_id": post.id,
                "content_score": content_score,
                "post_likes": post_likes,
                "post_comments": post_comments,
                "post_views": post_views,
                "user_liked": user_liked,
                "user_commented": user_commented,
                "watch_duration": watch_dur,
                "completed": completed,
                "following_author": following_author,
                "collaborative_score": collab_score,
                "interest_score": interest_score,
            })

    df = pd.DataFrame(data)
    return df, vectorizer


def train():
    """
    Train the Multiple Linear Regression recommendation model and save all artifacts.
    """
    print("\n" + "=" * 55)
    print("STARTING MLR RECOMMENDATION MODEL TRAINING")
    print("=" * 55)

    df, vectorizer = build_training_dataset()

    X = df[FEATURE_NAMES].fillna(0.0)
    y = df["interest_score"].fillna(0.0)

    print(f"Total training samples: {len(df)}")
    print(f"Target Interest Score summary: min={y.min():.2f}, max={y.max():.2f}, mean={y.mean():.2f}")

    # Train / Test split if dataset is sufficient
    if len(df) >= 20:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    # Train Ridge Regression (MLR with L2 regularizer for stability)
    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predictions))
    mse = float(mean_squared_error(y_test, predictions))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_test, predictions)) if len(y_test) > 1 else 1.0

    print("\n--- MODEL EVALUATION ---")
    print(f"MAE  : {mae:.4f}")
    print(f"MSE  : {mse:.4f}")
    print(f"RMSE : {rmse:.4f}")
    print(f"R²   : {r2:.4f}")
    print(f"Intercept : {model.intercept_:.4f}")
    print("\n--- FEATURE COEFFICIENTS ---")
    coef_dict = {}
    for feat, coef in zip(FEATURE_NAMES, model.coef_):
        coef_dict[feat] = float(coef)
        print(f"  {feat:<22} : {coef:+.4f}")

    # 1. Save MLR model
    model_data = {
        "model": model,
        "features": FEATURE_NAMES,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model_data, f)
    # Also save to root if needed
    with open(os.path.join(BASE_DIR, "mlr_model.pkl"), "wb") as f:
        pickle.dump(model_data, f)

    # 2. Save MLR model metadata
    model_info = {
        "features": FEATURE_NAMES,
        "target": "interest_score",
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "r2_score": r2,
        "intercept": float(model.intercept_),
        "coefficients": coef_dict,
    }
    with open(MODEL_INFO_PATH, "wb") as f:
        pickle.dump(model_info, f)

    # 3. Save TF-IDF Vectorizer
    with open(TFIDF_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    # 4. Save legacy compatibility artifacts (for post-level cosine similarity)
    posts = list(Post.objects.all())
    post_texts = [clean_post_text(p) for p in posts]
    tfidf_mat = vectorizer.transform(post_texts)
    cosine_sim = linear_kernel(tfidf_mat, tfidf_mat)
    indices = pd.Series(range(len(posts)), index=[p.id for p in posts])
    legacy_df = pd.DataFrame([{
        "id": p.id,
        "author": p.author.username,
        "title": p.title or "",
        "content": p.content or "",
        "likes": p.total_likes,
        "comments": p.total_comments,
    } for p in posts])

    with open(os.path.join(BASE_DIR, "recommendation_model.pkl"), "wb") as f:
        pickle.dump(cosine_sim, f)
    with open(os.path.join(BASE_DIR, "video_data.pkl"), "wb") as f:
        pickle.dump(legacy_df, f)
    with open(os.path.join(BASE_DIR, "indices.pkl"), "wb") as f:
        pickle.dump(indices, f)
    with open(os.path.join(BASE_DIR, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(vectorizer, f)

    print("\n" + "=" * 55)
    print("RECOMMENDATION TRAINING COMPLETED SUCCESSFULLY")
    print("=" * 55 + "\n")
    return model, model_info


if __name__ == "__main__":
    train()